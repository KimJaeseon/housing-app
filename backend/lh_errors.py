"""Documented gateway codes, parsed without propagating upstream text or secrets."""
import json
import re
from xml.etree import ElementTree as ET

ERROR_CODES={
 '1':'API_APPLICATION_ERROR','2':'API_DATABASE_ERROR','3':'API_NO_DATA',
 '4':'SOURCE_HTTP_ERROR','5':'SOURCE_TIMEOUT',
 '10':'API_INVALID_PARAMETERS','11':'API_MISSING_PARAMETERS','12':'API_SERVICE_UNAVAILABLE',
 '20':'API_ACCESS_DENIED','21':'API_KEY_TEMPORARILY_DISABLED','22':'RATE_LIMITED',
 '30':'API_KEY_NOT_REGISTERED','31':'API_KEY_EXPIRED','32':'API_IP_NOT_REGISTERED',
 '33':'API_UNSIGNED_CALL','99':'API_UNKNOWN_ERROR',
}
RETRYABLE_CODES={'API_APPLICATION_ERROR','API_DATABASE_ERROR','SOURCE_HTTP_ERROR',
                 'SOURCE_TIMEOUT','SOURCE_TRANSPORT_ERROR','SOURCE_TIME_LIMIT','RATE_LIMITED'}


def mapped_error(value):
    if not isinstance(value,(str,int)) or isinstance(value,bool):return 'API_UNKNOWN_ERROR'
    code=str(value).strip()
    if not re.fullmatch(r'[0-9]{1,3}',code):return 'API_UNKNOWN_ERROR'
    code=str(int(code))
    return None if code=='0' else ERROR_CODES.get(code,'API_UNKNOWN_ERROR')


def payload_error(payload):
    headers=[]
    if isinstance(payload,dict):
        response=payload.get('response')
        if isinstance(response,dict) and isinstance(response.get('header'),dict):headers.append(response['header'])
        response=payload.get('OpenAPI_ServiceResponse')
        if isinstance(response,dict) and isinstance(response.get('cmmMsgHeader'),dict):headers.append(response['cmmMsgHeader'])
        if isinstance(payload.get('cmmMsgHeader'),dict):headers.append(payload['cmmMsgHeader'])
    elif isinstance(payload,list):
        for part in payload:
            if isinstance(part,dict) and isinstance(part.get('resHeader'),list):headers.extend(h for h in part['resHeader'] if isinstance(h,dict))
    for header in headers:
        for field in ('returnReasonCode','resultCode'):
            if field in header:
                error=mapped_error(header[field])
                if error:return error
        if 'SS_CODE' in header and header['SS_CODE']!='Y':
            return mapped_error(header['SS_CODE']) or 'SOURCE_RESPONSE_UNCONFIRMED'
    return None


def decode_response(body):
    """Read bounded bytes supplied by caller. XML is supported only for gateway errors."""
    try:
        payload=json.loads(body)
        error=payload_error(payload)
        return (None,error) if error else (payload,None)
    except (ValueError,UnicodeError,RecursionError):
        pass
    # No entities or DTDs are needed for the documented gateway error envelope.
    if b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():return None,'SOURCE_RESPONSE_UNCONFIRMED'
    try:
        root=ET.fromstring(body)
        if root.tag.rsplit('}',1)[-1]!='OpenAPI_ServiceResponse':return None,'SOURCE_RESPONSE_UNCONFIRMED'
        values=[e.text for e in root.iter() if e.tag.rsplit('}',1)[-1]=='returnReasonCode']
        if len(values)==1:return None,mapped_error(values[0]) or 'SOURCE_RESPONSE_UNCONFIRMED'
    except (ET.ParseError,ValueError):pass
    return None,'SOURCE_RESPONSE_UNCONFIRMED'
