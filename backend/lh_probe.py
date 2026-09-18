"""One-page LH connectivity probe; never emits credentials or upstream bodies."""
import argparse
import getpass
import html
import json
import os
import re
import sys
import warnings
from backend.lh_errors import decode_response, payload_error
from datetime import datetime
from urllib.error import HTTPError
from urllib.parse import urlencode, unquote
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = 'https://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1'
MAX_BYTES = 1024 * 1024

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def date_value(value):
    if not re.fullmatch(r'\d{4}\.\d{2}\.\d{2}', value):
        raise argparse.ArgumentTypeError('Use YYYY.MM.DD')
    try:
        datetime.strptime(value, '%Y.%m.%d')
    except ValueError:
        raise argparse.ArgumentTypeError('Invalid calendar date') from None
    return value

def normalize_key(key):
    # Preserve literal plus signs; unquote_plus would corrupt ordinary keys.
    key = html.unescape(key).strip()
    if '%' in key:
        if re.search(r'%(?![0-9A-Fa-f]{2})', key):
            raise ValueError('invalid_key')
        key = unquote(key, errors='strict').strip()
    if not key or '%' in key or any(c.isspace() for c in key):
        raise ValueError('invalid_key')
    if not re.fullmatch(r'[A-Za-z0-9+/=_-]+', key):
        raise ValueError('invalid_key')
    return key

def request_parameters(key, posted, closing, region, housing_type, *, page=1, size=3,
                       name=None, status=None, closing_start=None, closing_end=None):
    key=normalize_key(key)
    date_value(posted);date_value(closing)
    if posted>closing:raise ValueError('invalid_date_range')
    if type(page) is not int or not 1<=page<=9999 or type(size) is not int or not 1<=size<=9999:
        raise ValueError('invalid_paging')
    if region not in ('11','12','26','27','28','30','31','36110','41','43','44','47','48','50','51','52'):
        raise ValueError('invalid_region')
    if housing_type not in ('01','05','06','13','22','39'):raise ValueError('invalid_type')
    if status is not None and status not in ('공고중','접수중','접수마감','상담요청','정정공고중'):
        raise ValueError('invalid_status')
    if name is not None and (not isinstance(name,str) or not 1<=len(name.strip())<=50 or any(ord(c)<32 for c in name)):
        raise ValueError('invalid_name')
    query={'serviceKey':key,'PG_SZ':str(size),'PAGE':str(page),
           'PAN_ST_DT':posted.replace('.',''),'PAN_ED_DT':closing.replace('.',''),
           'CNP_CD':region,'UPP_AIS_TP_CD':housing_type}
    for field,value in (('CLSG_ST_DT',closing_start),('CLSG_ED_DT',closing_end)):
        if value is not None:date_value(value);query[field]=value.replace('.','')
    if closing_start and closing_end and closing_start>closing_end:raise ValueError('invalid_closing_range')
    if name is not None:query['PAN_NM']=name.strip()
    if status is not None:query['PAN_SS']=status
    return query


def request_url(key, posted, closing, region, housing_type, **options):
    return ENDPOINT+'?'+urlencode(request_parameters(key,posted,closing,region,housing_type,**options))


def classify(payload):
    """Validate the observed list envelope, never the underlying notice facts.

    dsSch echoes request parameters and must never be logged or persisted.
    Only fixed labels and numeric counts leave this function.
    """
    failure = {'result': 'unconfirmed', 'reason': 'json_response_not_verified'}
    error=payload_error(payload)
    if error:return {'result':'unconfirmed','reason':error}
    if not isinstance(payload, list) or len(payload) != 2:
        return failure
    search, data = payload
    if not isinstance(search, dict) or not isinstance(data, dict):
        return failure
    if set(search) != {'dsSch'} or set(data) != {'dsList', 'resHeader'}:
        return failure
    echoed = search['dsSch']
    headers = data['resHeader']
    rows = data['dsList']
    if not isinstance(echoed, list) or len(echoed) != 1 or not isinstance(echoed[0], dict):
        return failure
    if (not isinstance(headers, list) or len(headers) != 1
            or not isinstance(headers[0], dict) or headers[0].get('SS_CODE') != 'Y'
            or not isinstance(rows, list)):
        return failure
    # Fail closed when identity/count fields are missing or conflicting.
    fields = ('PAN_ID', 'AIS_TP_CD', 'CCR_CNNT_SYS_DS_CD', 'RNUM', 'ALL_CNT')
    identities, ordinals, totals = set(), set(), set()
    for row in rows:
        if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k] for k in fields):
            return failure
        if not re.fullmatch(r'[0-9]{1,10}', row['ALL_CNT']) or not re.fullmatch(r'[0-9]{1,10}', row['RNUM']):
            return failure
        identity = tuple(row[k] for k in fields[:3])
        ordinal, total = int(row['RNUM']), int(row['ALL_CNT'])
        if identity in identities or ordinal in ordinals or not 1 <= ordinal <= total:
            return failure
        identities.add(identity); ordinals.add(ordinal); totals.add(total)
    if len(totals) > 1 or (totals and next(iter(totals)) < len(rows)):
        return failure
    return {'result': 'api_success_signal', 'json_shape': 'list_envelope_validated',
            'candidate_row_count': len(rows),
            'reported_total_count': next(iter(totals)) if totals else None,
            'notice_verification': 'pending'}


def probe(key, posted, closing, region='11', housing_type='06', opener=None, **options):
    try:
        url = request_url(key, posted, closing, region, housing_type, **options)
    except (ValueError, argparse.ArgumentTypeError):
        return {'result': 'not_called', 'reason': 'invalid_request_or_key'}
    try:
        client = opener if opener is not None else build_opener(NoRedirect())
        request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'HousingValidation/0.1'})
        with client.open(request, timeout=15) as response:
            status = int(response.status)
            if status != 200:
                return {'result': 'unconfirmed', 'http_status': status}
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            return {'result': 'unconfirmed', 'reason': 'response_too_large', 'http_status': status}
        try:
            payload, error = decode_response(body)
            outcome = {'result':'unconfirmed','reason':error} if error else classify(payload)
        except (ValueError, UnicodeError, RecursionError):
            outcome = {'result': 'unconfirmed', 'reason': 'unrecognized_response'}
        return dict(outcome, http_status=status)
    except HTTPError as error:
        status = error.code if isinstance(error.code, int) else None
        reason='http_error_or_redirect'
        try:
            body=error.read(MAX_BYTES+1)
            if isinstance(body,bytes) and len(body)<=MAX_BYTES:
                _,known=decode_response(body)
                if known and known!='SOURCE_RESPONSE_UNCONFIRMED':reason=known
        except Exception:pass
        finally:error.close()
        return {'result': 'unconfirmed', 'http_status': status, 'reason': reason}
    except Exception:
        # Exception messages can contain the complete URL and credential.
        return {'result': 'unconfirmed', 'reason': 'transport_error'}

def main(argv=None):
    parser = argparse.ArgumentParser(description='One LH request, three rows maximum; no raw response output.')
    parser.add_argument('--start', '--posted', dest='posted', required=True, type=date_value, help='Posting start date, YYYY.MM.DD')
    parser.add_argument('--end', '--closing', dest='closing', required=True, type=date_value, help='Posting end date, YYYY.MM.DD')
    parser.add_argument('--region', choices=['11', '28', '41'], default='11')
    parser.add_argument('--type', choices=['05', '06', '13', '39'], default='06', dest='housing_type')
    parser.add_argument('--page',type=int,default=1)
    parser.add_argument('--page-size',type=int,default=3)
    parser.add_argument('--name')
    parser.add_argument('--status',choices=['공고중','접수중','접수마감','상담요청','정정공고중'])
    parser.add_argument('--closing-start',type=date_value)
    parser.add_argument('--closing-end',type=date_value)
    args = parser.parse_args(argv)
    from backend.key_store import resolve_key, KeyStoreError
    try:
        key = resolve_key()
    except KeyStoreError:
        print(json.dumps({'result': 'not_called', 'reason': 'key_store_unavailable'}))
        return 2
    if not key and sys.stdin.isatty():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                key = getpass.getpass('LH general service key (hidden): ').strip()
        except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
            key = ''
    if not key:
        outcome = {'result': 'not_called', 'reason': 'missing_key'}
    else:
        outcome = probe(key, args.posted, args.closing, args.region, args.housing_type, page=args.page,size=args.page_size,name=args.name,status=args.status,closing_start=args.closing_start,closing_end=args.closing_end)
    print(json.dumps(outcome, ensure_ascii=True))
    return 0 if outcome['result'] == 'api_success_signal' else 2

if __name__ == '__main__':
    raise SystemExit(main())
