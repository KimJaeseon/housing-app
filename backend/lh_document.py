"""Read an official notice and bind reviewed facts to an exact PDF digest.

No credential is sent to the public site. Unknown PDFs never inherit another
notice's reviewed facts. This is a review registry, not a generic legal verifier.
"""
import hashlib,re
from copy import deepcopy
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
import json
from urllib.request import Request,build_opener
from urllib.error import HTTPError
from backend.lh_probe import NoRedirect
from backend.lh_response import safe_official_url

PROFILE_DIR=Path(__file__).parent/'document_reviews'
MAX_HTML=1024*1024
MAX_PDF=10*1024*1024

class Node:
    def __init__(self,tag='',attrs=()):self.tag=tag;self.attrs=dict(attrs);self.children=[]
    def text(self):return ' '.join(c if isinstance(c,str) else c.text() for c in self.children).strip()
    def all(self,tag):
        found=[]
        for c in self.children:
            if isinstance(c,Node):
                if c.tag==tag:found.append(c)
                found.extend(c.all(tag))
        return found
class Tree(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root]
    def handle_starttag(self,tag,attrs):
        n=Node(tag,attrs);self.stack[-1].children.append(n)
        if tag not in ('input','meta','link','img','br','hr','source','wbr','area','base','embed','param','col'):self.stack.append(n)
    def handle_startendtag(self,tag,attrs):self.stack[-1].children.append(Node(tag,attrs))
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:del self.stack[i:];break
    def handle_data(self,data):self.stack[-1].children.append(data)

def compact(s):return re.sub(r'\s+','',s)
def read_page(body,notice):
    text=body.decode('utf-8');tree=Tree();tree.feed(text)
    containers=[n for n in tree.root.all('div') if 'bbs_ViewA' in n.attrs.get('class','').split()]
    if len(containers)!=1:raise ValueError('DOCUMENT_PAGE_UNCONFIRMED')
    container=containers[0];titles=container.all('h3')
    if not titles or compact(titles[0].text())!=compact(notice['title']):raise ValueError('DOCUMENT_IDENTITY_MISMATCH')
    # Match literal public metadata only; never evaluate website JavaScript.
    def variable(name,allow_empty=False):
        vals=set(re.findall(r'\bvar\s+'+name+r"\s*=\s*'([0-9]*)'\s*;",text))
        if len(vals)!=1 or (not allow_empty and not next(iter(vals))):raise ValueError('DOCUMENT_PAGE_UNCONFIRMED')
        return next(iter(vals)) or None
    if variable('panId')!=notice['official_id']:raise ValueError('DOCUMENT_IDENTITY_MISMATCH')
    current=variable('currPanId');original=variable('sOtxtPanId',True)
    files=[];correction=None
    for dl in container.all('dl'):
        dt=dl.all('dt');dd=dl.all('dd')
        if len(dt)!=1 or not dd:continue
        if dt[0].text()=='정정사유':correction=' '.join(dd[0].text().split())[:1000]
        if dt[0].text()!='공고문':continue
        for a in dd[0].all('a'):
            m=re.fullmatch(r"javascript:fileDownLoad\('([0-9]{1,16})'\);?",a.attrs.get('href',''))
            if m and a.text().lower().endswith('.pdf'):files.append({'file_id':m[1],'name':a.text()[:200]})
    if len(files)!=1:raise ValueError('DOCUMENT_PDF_NOT_UNIQUE')
    return {'attachment':files[0],'current_id':current,'original_id':original,'correction':correction}

def empty_document(status='researching',code=None):
    return {'status':status,'error_code':code,'checked_at':None if status=='researching' else datetime.now(timezone.utc).isoformat(),
            'source_url':None,'pdf_url':None,'sha256':None,'filename':None,'current_id':None,'original_id':None,
            'reviewed':False,'facts':[],'warnings':[]}

def apply_review(result,notice,profile_dir=PROFILE_DIR):
    # Read only a fixed, numeric official-id filename under the review registry.
    ident=notice['official_id']
    if not re.fullmatch(r'[0-9]{1,32}',ident):return result
    path=profile_dir/(ident+'.json')
    if not path.is_file():
        result['warnings'].append('이 PDF의 항목별 검토 기록이 없습니다. 공식 문서를 직접 확인해 주세요.');return result
    profile=json.loads(path.read_text(encoding='utf-8'))
    matches=(profile['official_id']==ident and profile['sha256']==result['sha256'] and result['current_id']==ident
             and result['original_id']==profile['original_id'] and compact(profile['correction'])==compact(result.pop('_correction','') or ''))
    if not matches:
        result['warnings'].append('문서 또는 정정 관계가 검토 기록과 달라 기존 확인값을 보류했습니다. 재검토가 필요합니다.');return result
    result['reviewed']=True;result['facts']=deepcopy(profile['facts']);result['warnings'].extend(profile['warnings'])
    return result

def fetch_document(notice,opener=None,profile_dir=PROFILE_DIR):
    result=empty_document('partial');listing=notice.get('listing') or {}
    row={'PAN_ID':notice.get('official_id'),'AIS_TP_CD':listing.get('detail_type_code'),'UPP_AIS_TP_CD':listing.get('housing_type_code'),'CCR_CNNT_SYS_DS_CD':listing.get('source_system_code')}
    url=safe_official_url(listing.get('official_url'),row)
    if not url or '/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?' not in url:return empty_document('failed','DOCUMENT_LINK_UNSUPPORTED')
    result['source_url']=url
    client=opener or build_opener(NoRedirect())
    def read(url,limit):
        with client.open(Request(url,headers={'Accept':'application/pdf,text/html'}),timeout=10) as response:
            body=response.read(limit+1)
        if len(body)>limit:raise ValueError('DOCUMENT_TOO_LARGE')
        return body
    try:
        meta=read_page(read(url,MAX_HTML),notice)
        result.update(current_id=meta['current_id'],original_id=meta['original_id'],filename=meta['attachment']['name'])
        result['pdf_url']='https://apply.lh.or.kr/lhapply/lhFile.do?fileid='+meta['attachment']['file_id']
        pdf=read(result['pdf_url'],MAX_PDF)
        if not pdf.startswith(b'%PDF-'):raise ValueError('DOCUMENT_NOT_PDF')
        result['sha256']=hashlib.sha256(pdf).hexdigest();result['_correction']=meta['correction']
        result=apply_review(result,notice,profile_dir);result.pop('_correction',None)
        result['warnings'].append('항목별 확인 결과이며 공고 전체 검증이나 신청 자격 판정은 아닙니다. 별도 변경 공지 확인이 남아 있습니다.')
        return result
    except HTTPError as e:
        code='DOCUMENT_ACCESS_DENIED' if e.code in (401,403) else 'DOCUMENT_HTTP_ERROR';e.close();return empty_document('failed',code)
    except ValueError as e:
        allowed={'DOCUMENT_PAGE_UNCONFIRMED','DOCUMENT_IDENTITY_MISMATCH','DOCUMENT_PDF_NOT_UNIQUE','DOCUMENT_TOO_LARGE','DOCUMENT_NOT_PDF'}
        return empty_document('failed',str(e) if str(e) in allowed else 'DOCUMENT_RESPONSE_UNCONFIRMED')
    except Exception:return empty_document('failed','DOCUMENT_RESPONSE_UNCONFIRMED')
