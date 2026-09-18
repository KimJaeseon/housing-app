"""Bounded LH list collection. All notices remain unverified; no raw response logs."""
import os
import time
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from backend.lh_probe import ENDPOINT, MAX_BYTES, NoRedirect, classify, date_value, normalize_key, request_parameters
from backend.key_store import resolve_key, KeyStoreError
from backend.lh_errors import decode_response, RETRYABLE_CODES
from backend.lh_response import normalize_row

PAGE_SIZE = 20
MAX_PAGES = 5
MAX_SECONDS = 35


def fetch_page(key, posted, closing, region, page, size=PAGE_SIZE, timeout=10):
    """Return only allowlisted public fields, never request echoes or upstream URLs."""
    try:
        key = normalize_key(key)
        query = request_parameters(key,posted,closing,region,'06',page=page,size=size)
        request = Request(ENDPOINT+'?'+urlencode(query), headers={'Accept':'application/json'})
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            body = response.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES: return {'error':'SOURCE_RESPONSE_TOO_LARGE'}
        payload,error=decode_response(body)
        if error:return {'error':error}
        outcome = classify(payload)
        if outcome['result']!='api_success_signal': return {'error':'SOURCE_RESPONSE_UNCONFIRMED'}
        echoes=payload[0]['dsSch'][0]
        expected={'PAN_ST_DT':posted.replace('.',''),'PAN_ED_DT':closing.replace('.',''),
                  'CNP_CD':region,'UPP_AIS_TP_CD':'06','PAGE':str(page),'PG_SZ':str(size)}
        if any(echoes.get(k)!=v for k,v in expected.items()):return {'error':'QUERY_FILTER_MISMATCH'}
        rows = []
        for raw in payload[1]['dsList']:
            try:row=normalize_row(raw,key)
            except Exception:return {'error':'SOURCE_ROW_INVALID'}
            if not posted<=row['PAN_NT_ST_DT']<=closing:return {'error':'QUERY_FILTER_MISMATCH'}
            rows.append(row)
        return {'rows':rows,'total':outcome['reported_total_count']}
    except HTTPError as error:
        status=error.code
        code='RATE_LIMITED' if status==429 else 'API_AUTH_FAILED' if status in (401,403) else 'SOURCE_HTTP_ERROR'
        try:
            body=error.read(MAX_BYTES+1)
            if isinstance(body,bytes) and len(body)<=MAX_BYTES:
                _,known=decode_response(body)
                if known and known!='SOURCE_RESPONSE_UNCONFIRMED':code=known
        except Exception:pass
        finally:error.close()
        return {'error':code}
    except Exception:
        return {'error':'SOURCE_TRANSPORT_ERROR'}


def official_url(row):
    return row.get('DTL_URL') or row.get('DTL_URL_MOB')


def to_notice(row, region, checked):
    ident='LH-'+row['PAN_ID']+'-'+row['AIS_TP_CD']+'-'+row['CCR_CNNT_SYS_DS_CD']
    version=ident+'-list'; evidence=ident+'-evidence'
    title=row['PAN_NM']
    cancelled='취소' in row['PAN_SS'] or '취소공고' in title
    closed=row['PAN_SS']=='접수마감'
    reasons=['목록 정보만 확인했습니다. 접수 회차·시간, 금액, 신청 자격은 원문 검증 전입니다.',
             '최종 정정·취소 관계와 공공주택 세부 유형의 확인이 필요합니다.']
    if '정정' in title or '정정' in row['PAN_SS']:
        reasons.append('정정 공고 후보입니다. 원공고와 연결 및 변경 내용 대조가 필요합니다.')
    return {'id':ident,'source_id':'LH','official_id':row['PAN_ID'],'title':title,
            'housing_type':row['AIS_TP_CD_NM'],'region_ids':[region], 'scope':'unknown',
            'versions':[{'id':version,'kind':'unclassified','related_version_ids':[],
                         'changed_fields':[],'relationship_evidence_ids':[],'checked_at':checked}],
            'current_version_id':None,'revision_resolved':False,'checked_in_job_id':'pending',
            'checked_at':checked,'recruitment_status':'cancelled' if cancelled else 'closed' if closed else 'unknown',
            'verification_status':'needs_review','review_reasons':reasons,
            'evidence':[{'id':evidence,'url':ENDPOINT,'document_version_id':version,
                         'locator':'목록 API의 PAN_ID, PAN_NM, PAN_SS, PAN_NT_ST_DT, CLSG_DT. 첨부 검증 전.',
                         'checked_at':checked,'method':'api'}], 'units':[],
            'listing':{'status':row['PAN_SS'],'posted_date':row['PAN_NT_ST_DT'],
                       'closing_date':row['CLSG_DT'],'official_url':official_url(row),
                       'mobile_official_url':row.get('DTL_URL_MOB'),'announcement_date':row.get('PAN_DT'),
                       'supply_info_type':row.get('SPL_INF_TP_CD'),'source_system_code':row['CCR_CNNT_SYS_DS_CD'],
                       'housing_type_code':row['UPP_AIS_TP_CD'],'detail_type_code':row['AIS_TP_CD']}}


def collect_list(region, is_cancelled=lambda:False, fetcher=fetch_page, max_pages=MAX_PAGES, clock=time.monotonic):
    try:key=resolve_key()
    except KeyStoreError:return {'error':'KEY_STORE_UNAVAILABLE','retryable':False}
    if not key:return {'error':'MISSING_API_KEY','retryable':False}
    posted=os.environ.get('LH_POSTED_DATE','');closing=os.environ.get('LH_CLOSING_DATE','')
    try:
        date_value(posted);date_value(closing)
        if posted>closing:raise ValueError('range')
    except Exception:return {'error':'DATE_FILTER_NOT_CONFIGURED','retryable':False}
    start=clock(); rows=[];seen=set();total=None;pages=0;verified_pages=0;complete=False;error=None
    for page in range(1,max_pages+1):
        if is_cancelled():return {'error':'CANCELLED','retryable':False}
        remaining=MAX_SECONDS-(clock()-start)
        if remaining<=0:error='SOURCE_TIME_LIMIT';break
        result=fetcher(key,posted,closing,'11' if region=='seoul' else '28',page,PAGE_SIZE,timeout=min(10,remaining))
        pages+=1
        if result.get('error'):error=result['error'];break
        verified_pages+=1
        batch=result['rows']; observed=result['total']
        if len(batch)>PAGE_SIZE or (observed is not None and total is not None and observed!=total):
            error='PAGINATION_CHANGED';break
        if observed is not None:total=observed
        if not batch:
            if total is not None and len(rows)!=total:error='PAGINATION_INCOMPLETE'
            else:complete=True
            break
        # Validate the whole page before accepting it. Do not silently merge revisions.
        ids=[(r['PAN_ID'],r['AIS_TP_CD'],r['CCR_CNNT_SYS_DS_CD']) for r in batch]
        ordinals=[int(r['RNUM']) for r in batch]
        expected=list(range(len(rows)+1,len(rows)+len(batch)+1))
        if len(set(ids))!=len(ids) or any(i in seen for i in ids) or ordinals!=expected:
            error='PAGINATION_CHANGED';break
        rows.extend(batch);seen.update(ids)
        if total is not None and len(rows)==total:complete=True;break
        if len(batch)<PAGE_SIZE:error='PAGINATION_INCOMPLETE';break
    if not complete and error is None:error='PAGE_LIMIT_REACHED'
    checked=datetime.now(timezone.utc).isoformat()
    notices=[];excluded=[];mismatches=0
    expected_region='서울특별시' if region=='seoul' else '인천광역시'
    for row in rows:
        if row['CNP_CD_NM']!=expected_region or row['UPP_AIS_TP_CD']!='06':
            mismatches+=1;continue
        notice=to_notice(row,region,checked)
        (excluded if notice['recruitment_status'] in ('closed','cancelled') else notices).append(notice)
    if mismatches and error is None:error='SOURCE_SCOPE_MISMATCH'
    code=error or 'DOCUMENT_VERIFICATION_PENDING'
    return {'error':code,'retryable':code in RETRYABLE_CODES,
            'notices':notices,'excluded_notices':excluded,
            'collection':{'source':'LH','housing_type':'임대주택(06)','posted_filter':posted,'closing_filter':closing,
                          'pages_fetched':pages,'page_limit':max_pages,'rows_fetched':len(rows),
                          'list_complete':complete,'date_filter_verified':verified_pages>0 and verified_pages==pages,'scope_mismatch_count':mismatches},
            'checked_at':checked}
