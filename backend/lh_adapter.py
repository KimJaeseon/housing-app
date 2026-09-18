"""Limited LH connectivity adapter; does not claim notice verification."""
import os
from backend.lh_probe import probe,date_value
from backend.lh_errors import ERROR_CODES, RETRYABLE_CODES
from backend.key_store import resolve_key, KeyStoreError

def collect(region):
    if os.environ.get('LH_ENABLE_PROBE')!='1':return ('ADAPTER_NOT_CONFIGURED',False)
    try:key=resolve_key()
    except KeyStoreError:return ('KEY_STORE_UNAVAILABLE',False)
    if not key:return ('MISSING_API_KEY',False)
    posted=os.environ.get('LH_POSTED_DATE','');closing=os.environ.get('LH_CLOSING_DATE','')
    try:date_value(posted);date_value(closing)
    except Exception:return ('DATE_FILTER_NOT_CONFIGURED',False)
    outcome=probe(key,posted,closing,region='11' if region=='seoul' else '28')
    if outcome['result']=='api_success_signal':return ('RESPONSE_VERIFICATION_PENDING',False)
    if outcome.get('reason') in ERROR_CODES.values():return (outcome['reason'],outcome['reason'] in RETRYABLE_CODES)
    if outcome.get('http_status')==429:return ('RATE_LIMITED',True)
    if outcome.get('http_status') in (401,403):return ('API_AUTH_FAILED',False)
    if outcome.get('reason')=='transport_error':return ('SOURCE_TRANSPORT_ERROR',True)
    return ('SOURCE_RESPONSE_UNCONFIRMED',False)
