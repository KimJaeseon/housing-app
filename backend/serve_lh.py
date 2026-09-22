"""Start localhost probe integration with hidden credential entry."""
import argparse,getpass,os,warnings
import uvicorn
from backend.lh_probe import date_value, normalize_key
from backend.key_store import resolve_key, KeyStoreError, save_key

def main():
    p=argparse.ArgumentParser();p.add_argument('--start','--posted',dest='posted',required=True,type=date_value);p.add_argument('--end','--closing',dest='closing',required=True,type=date_value);p.add_argument('--host',default='127.0.0.1');a=p.parse_args()
    try:key=resolve_key()
    except KeyStoreError:
        print('Local encrypted key cannot be read. Run python -m backend.key_store save.');return 2
    if not key:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',getpass.GetPassWarning)
                key=getpass.getpass('LH general service key (hidden): ').strip()
                save_key(key)
        except (EOFError,KeyboardInterrupt,getpass.GetPassWarning,KeyStoreError):return 2
    try:key=normalize_key(key)
    except ValueError:
        print('Invalid general service key');return 2
    settings={'LH_ENABLE_DOCUMENT':'1','LH_ENABLE_SUPPLY':'1','LH_ENABLE_LIST':'1','LH_ENABLE_PROBE':'1','LH_POSTED_DATE':a.posted,'LH_CLOSING_DATE':a.closing}
    previous={name:os.environ.get(name) for name in settings}
    os.environ.update(settings)
    try:uvicorn.run('backend.app:app',host=a.host,port=8000,access_log=False)
    finally:
        for name,value in previous.items():
            if value is None:os.environ.pop(name,None)
            else:os.environ[name]=value
    return 0
if __name__=='__main__':raise SystemExit(main())
