"""Public response fields described in the 20260708 LH guide."""
import html
import re
from urllib.parse import parse_qsl,urlsplit,urlencode,unquote
from backend.lh_probe import date_value

FIELDS=('PAN_ID','AIS_TP_CD','CCR_CNNT_SYS_DS_CD','UPP_AIS_TP_CD','PAN_NM',
        'UPP_AIS_TP_NM','AIS_TP_CD_NM','CNP_CD_NM','PAN_SS','PAN_NT_ST_DT','CLSG_DT',
        'RNUM','ALL_CNT','SPL_INF_TP_CD')


def safe_official_url(value,row):
    if not isinstance(value,str):return None
    try:
        url=urlsplit(html.unescape(value.strip()))
        if url.scheme!='https' or url.netloc!='apply.lh.or.kr' or url.fragment:return None
        pairs=parse_qsl(url.query,keep_blank_values=True)
        params=dict(pairs)
        if len(params)!=len(pairs):return None
        if url.path=='/lhapply/apply/wt/wrtanc/selectWrtancInfo.do':
            expected={'panId':row['PAN_ID'],'aisTpCd':row['AIS_TP_CD'],
                      'uppAisTpCd':row['UPP_AIS_TP_CD'],'ccrCnntSysDsCd':row['CCR_CNNT_SYS_DS_CD']}
            if set(params)-set(expected)-{'mi'} or any(params.get(k)!=v for k,v in expected.items()):return None
            if 'mi' in params and not re.fullmatch(r'[0-9]{1,10}',params['mi']):return None
        elif url.path=='/LH/index.html':
            if set(params)!={'gv_url','gv_menuId','gv_param'}:return None
            if not re.fullmatch(r'SIL::CLCC_SIL_[0-9]{4}\.xfdl',params['gv_url']):return None
            if not re.fullmatch(r'[0-9]{1,10}',params['gv_menuId']):return None
            if params['gv_param']!=f"CCR_CNNT_SYS_DS_CD:{row['CCR_CNNT_SYS_DS_CD']},PAN_ID:{row['PAN_ID']},LCC:Y":return None
        else:return None
        return 'https://apply.lh.or.kr'+url.path+'?'+urlencode(params)
    except (ValueError,KeyError):return None


def normalize_row(raw,key):
    row={}
    for field in FIELDS:
        value=raw.get(field)
        if not isinstance(value,str) or len(value)>500 or key in unquote(html.unescape(value)):
            raise ValueError('SOURCE_ROW_INVALID')
        row[field]=value.strip()
    if any(not re.fullmatch(r'[0-9]{1,32}',row[f]) for f in ('PAN_ID','AIS_TP_CD','CCR_CNNT_SYS_DS_CD','UPP_AIS_TP_CD','SPL_INF_TP_CD')):
        raise ValueError('SOURCE_ROW_INVALID')
    if not row['PAN_NM']:raise ValueError('SOURCE_ROW_INVALID')
    date_value(row['PAN_NT_ST_DT'])
    if row['CLSG_DT']:date_value(row['CLSG_DT'])
    announced=raw.get('PAN_DT')
    if announced is not None and announced!='':
        if not isinstance(announced,str) or not re.fullmatch(r'[0-9]{8}',announced.strip()):raise ValueError('SOURCE_ROW_INVALID')
        announced=announced.strip();date_value(announced[:4]+'.'+announced[4:6]+'.'+announced[6:])
    row['PAN_DT']=announced or None
    for field in ('DTL_URL','DTL_URL_MOB'):
        value=raw.get(field)
        if isinstance(value,str) and key in unquote(html.unescape(value)):raise ValueError('SOURCE_ROW_INVALID')
        row[field]=safe_official_url(value,row)
    return row
