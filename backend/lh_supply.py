"""On-demand supply facts for documented LH rental layouts; no eligibility approval."""
import html
import re
from datetime import datetime,timezone
from urllib.parse import urlencode,unquote
from urllib.request import Request,build_opener
from urllib.error import HTTPError
from backend.lh_probe import NoRedirect,MAX_BYTES,normalize_key
from backend.key_store import resolve_key,KeyStoreError
from backend.lh_errors import decode_response

ENDPOINT='https://apis.data.go.kr/B552555/lhLeaseNoticeSplInfo1/getLeaseNoticeSplInfo1'
MAX_UNITS=100


def parameters(notice,key):
    listing=notice.get('listing') or {}
    params={'serviceKey':normalize_key(key),'PAN_ID':notice.get('official_id'),
            'SPL_INF_TP_CD':listing.get('supply_info_type'),'CCR_CNNT_SYS_DS_CD':listing.get('source_system_code'),
            'UPP_AIS_TP_CD':listing.get('housing_type_code'),'AIS_TP_CD':listing.get('detail_type_code')}
    if not isinstance(params['PAN_ID'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,30}',params['PAN_ID']):raise ValueError('SUPPLY_REFERENCE_MISSING')
    if any(not isinstance(params[k],str) or not re.fullmatch(r'[0-9]{1,4}',params[k]) for k in ('SPL_INF_TP_CD','CCR_CNNT_SYS_DS_CD','UPP_AIS_TP_CD','AIS_TP_CD')):raise ValueError('SUPPLY_REFERENCE_MISSING')
    if params['SPL_INF_TP_CD'] not in ('061','062','063') or params['UPP_AIS_TP_CD']!='06' or params['CCR_CNNT_SYS_DS_CD']!='03':raise ValueError('UNSUPPORTED_SUPPLY_TYPE')
    return params


def unknown(reason,unit=None):
    return {'state':'unknown','value':None,'unit':unit,'reason':reason,'evidence_ids':[]}


def numeric_fact(raw,unit,evidence,label,accepted_labels,integer=False):
    if label not in accepted_labels:return unknown('API 항목의 단위를 확인하지 못했습니다.',unit)
    cleaned=raw.replace(',','') if re.fullmatch(r'[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?',raw) else raw
    pattern=r'[0-9]+' if integer else r'[0-9]+(?:\.[0-9]{1,8})?'
    if not re.fullmatch(pattern,cleaned):return unknown('API 표시: '+(raw or '값 없음')+' · 공고문 확인 필요',unit)
    value=int(cleaned) if integer else float(cleaned)
    if value>9007199254740991:return unknown('안전하게 표시할 수 있는 수치 범위를 벗어났습니다.',unit)
    return {'state':'known','value':value,'unit':unit,'reason':None,'evidence_ids':[evidence]}


def parse_supply(payload,params,notice,checked,key):
    if not isinstance(payload,list) or len(payload)!=2 or any(not isinstance(x,dict) for x in payload):raise ValueError('SUPPLY_RESPONSE_UNCONFIRMED')
    echo=payload[0].get('dsSch');data=payload[1];headers=data.get('resHeader');rows=data.get('dsList01');labels=data.get('dsList01Nm')
    if not isinstance(echo,list) or len(echo)!=1 or not isinstance(echo[0],dict):raise ValueError('SUPPLY_RESPONSE_UNCONFIRMED')
    if any(echo[0].get(k)!=v for k,v in params.items() if k!='serviceKey'):raise ValueError('SUPPLY_REFERENCE_MISMATCH')
    if not isinstance(headers,list) or len(headers)!=1 or not isinstance(headers[0],dict) or headers[0].get('SS_CODE')!='Y':raise ValueError('SUPPLY_RESPONSE_UNCONFIRMED')
    if not isinstance(rows,list) or not isinstance(labels,list) or len(labels)!=1 or not isinstance(labels[0],dict):raise ValueError('SUPPLY_RESPONSE_UNCONFIRMED')
    if len(rows)>MAX_UNITS:raise ValueError('SUPPLY_ROW_LIMIT')
    version=notice['id']+'-supply';units=[];evidence=[]
    fields=('SBD_LGO_NM','HTY_NNA','DDO_AR','HSH_CNT','NOW_HSH_CNT','LS_GMY','RFE','SPL_AR')
    for index,row in enumerate(rows):
        if not isinstance(row,dict):raise ValueError('SUPPLY_RESPONSE_UNCONFIRMED')
        safe={}
        for field in fields:
            value=row.get(field)
            if not isinstance(value,str) or len(value)>300 or key in unquote(html.unescape(value)):raise ValueError('SUPPLY_RESPONSE_UNCONFIRMED')
            safe[field]=value.strip()
        if not safe['SBD_LGO_NM'] or not safe['HTY_NNA']:raise ValueError('SUPPLY_RESPONSE_UNCONFIRMED')
        ev=version+'-'+str(index+1)
        evidence.append({'id':ev,'url':ENDPOINT,'document_version_id':version,'locator':f"PAN_ID={params['PAN_ID']}; dsList01[{index}] 및 dsList01Nm. 최종 공고문 대조 전.",'checked_at':checked,'method':'api'})
        def fact(field,unit,accepted,integer=False):return numeric_fact(safe[field],unit,ev,labels[0].get(field),accepted,integer)
        units.append({'id':ev+'-unit','label':safe['SBD_LGO_NM']+' · '+safe['HTY_NNA'],
                      'address':unknown('해당 공급정보 응답에서 상세 주소를 확인하지 못했습니다.'),
                      'deposit':fact('LS_GMY','원',{'임대보증금(원)'},True),
                      'monthly_rent':fact('RFE','원/월',{'월임대료(원)'},True),
                      'sale_price':unknown('분양가 확인 대상이 아닌 임대주택 공급정보입니다.'),
                      'eligibility':[unknown('이 API는 주택형 공급정보입니다. 신청 자격은 공식 공고문 검증이 필요합니다.')],
                      'windows':[],
                      'exclusive_area':fact('DDO_AR','㎡',{'전용면적(㎡)'}),
                      'supply_area':fact('SPL_AR','㎡',{'공급면적(㎡)'}),
                      'total_households':fact('HSH_CNT','세대',{'세대수'},True),
                      'offered_households':fact('NOW_HSH_CNT','세대',{'금회공급 세대수','금회공급세대수'},True)})
    return {'status':'available' if units else 'empty','error_code':None,'checked_at':checked,'units':units,'evidence':evidence,
            'versions':[{'id':version,'kind':'unclassified','related_version_ids':[],'changed_fields':[],'relationship_evidence_ids':[],'checked_at':checked}]}


def fetch_supply(notice,opener=None):
    checked=datetime.now(timezone.utc).isoformat()
    def failed(code):return {'status':'failed','error_code':code,'checked_at':checked,'units':[],'evidence':[],'versions':[]}
    try:key=resolve_key()
    except KeyStoreError:return failed('KEY_STORE_UNAVAILABLE')
    if not key:return failed('MISSING_API_KEY')
    try:key=normalize_key(key)
    except ValueError:return failed('INVALID_API_KEY_FORMAT')
    try:params=parameters(notice,key)
    except ValueError as e:return failed(str(e) if str(e) in ('SUPPLY_REFERENCE_MISSING','UNSUPPORTED_SUPPLY_TYPE') else 'SUPPLY_REFERENCE_MISSING')
    try:
        client=opener or build_opener(NoRedirect())
        with client.open(Request(ENDPOINT+'?'+urlencode(params),headers={'Accept':'application/json'}),timeout=10) as response:body=response.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:return failed('SOURCE_RESPONSE_TOO_LARGE')
        payload,error=decode_response(body)
        if error:return failed(error)
        try:return parse_supply(payload,params,notice,checked,key)
        except ValueError as e:
            codes={'SUPPLY_REFERENCE_MISMATCH','SUPPLY_RESPONSE_UNCONFIRMED','SUPPLY_ROW_LIMIT'}
            return failed(str(e) if str(e) in codes else 'SUPPLY_RESPONSE_UNCONFIRMED')
    except HTTPError as error:
        code='RATE_LIMITED' if error.code==429 else 'API_ACCESS_DENIED' if error.code==403 else 'SOURCE_HTTP_ERROR'
        try:
            body=error.read(MAX_BYTES+1)
            if isinstance(body,bytes) and len(body)<=MAX_BYTES:
                _,known=decode_response(body)
                if known and known!='SOURCE_RESPONSE_UNCONFIRMED':code=known
        except Exception:pass
        finally:error.close()
        return failed(code)
    except Exception:return failed('SOURCE_TRANSPORT_ERROR')
