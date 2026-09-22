"""Local single-process search jobs with bounded background execution."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
from threading import RLock,BoundedSemaphore
from uuid import uuid4
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI,Header,HTTPException
from pydantic import BaseModel,ConfigDict
from backend.validation import validate_result, validate_supply, validate_document
from backend.lh_document import fetch_document, empty_document
from backend.lh_supply import fetch_supply
from backend.lh_adapter import collect
from backend.lh_list import collect_list
import os

class Search(BaseModel):
    model_config=ConfigDict(extra='forbid')
    region:str
REGIONS={'서울':'서울특별시','서울시':'서울특별시','서울특별시':'서울특별시','인천':'인천광역시','인천광역시':'인천광역시'}
def now():return datetime.now(timezone.utc).isoformat()
def create_app(collector=collect,executor=None,supplier=fetch_supply,documenter=fetch_document):
    pool=executor or ThreadPoolExecutor(max_workers=2,thread_name_prefix='housing')
    @asynccontextmanager
    async def lifespan(app):
        yield
        if executor is None:pool.shutdown(wait=True,cancel_futures=True)
    app=FastAPI(title='Housing local search adapter',version='0.2.0',lifespan=lifespan)
    app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:8081','http://127.0.0.1:8081','http://127.0.0.1:18800'],allow_methods=['GET','POST'],allow_headers=['Content-Type','X-Session-Token','Idempotency-Key'])
    jobs={};keys={};supplies={};documents={};lock=RLock();slots=BoundedSemaphore(8)
    def owner(token):
        if not token or len(token)<32 or len(token)>128:raise HTTPException(401,'SESSION_TOKEN_REQUIRED')
        return sha256(token.encode()).hexdigest()
    def work(ident):
        try:
            with lock:
                r=jobs[ident][1]
                if r['status']=='cancelled':return
                r.update(status='researching',revision=r['revision']+1)
                r['sources'][0]['status']='researching'
                region=r['region']['id']
            def stopped():
                with lock:return jobs[ident][1]['status']=='cancelled'
            try:
                outcome=collect_list(region,stopped) if collector is collect and os.environ.get('LH_ENABLE_LIST')=='1' else collector(region)
                if isinstance(outcome,dict):code,retryable=outcome['error'],outcome.get('retryable',False)
                else:code,retryable=outcome;outcome={}
            except Exception:code,retryable='SOURCE_INTERNAL_ERROR',False;outcome={}
            with lock:
                r=jobs[ident][1]
                if r['status']=='cancelled':return
                candidate=deepcopy(r)
                # A successful list fetch is partial research, never verified completion.
                candidate.update(status='partial' if 'collection' in outcome and outcome.get('checked_at') and (outcome['collection']['list_complete'] or outcome['collection']['rows_fetched']>0) else 'failed',revision=r['revision']+1,finished_at=now())
                candidate['sources'][0].update(status='failed',error_code=code,retryable=retryable,checked_at=outcome.get('checked_at'))
                for field in ('notices','excluded_notices','collection'):
                    if field in outcome:candidate[field]=deepcopy(outcome[field])
                for notice in candidate['notices']+candidate.get('excluded_notices',[]):notice['checked_in_job_id']=ident
                try:validate_result(candidate)
                except Exception:
                    r.update(status='failed',revision=r['revision']+1,finished_at=now())
                    r['sources'][0].update(status='failed',error_code='SOURCE_VALIDATION_FAILED',retryable=False)
                else:r.clear();r.update(candidate)
        finally:slots.release()
    @app.get('/health')
    def health():return {'status':'ok','mode':'list_review' if os.environ.get('LH_ENABLE_LIST')=='1' else 'connectivity_adapter','live_collection':os.environ.get('LH_ENABLE_LIST')=='1','workers':2,'max_pending':8}
    @app.post('/v1/search-jobs',status_code=202)
    def create(req:Search,x_session_token:str=Header(default=''),idempotency_key:str=Header(min_length=1,max_length=128)):
        uid=owner(x_session_token);region=REGIONS.get(''.join(req.region.split()))
        if region is None:raise HTTPException(422,'REGION_NOT_IMPLEMENTED')
        with lock:
            k=(uid,idempotency_key)
            if k in keys:
                old=jobs[keys[k]][1]
                if old['region']['label']!=region:raise HTTPException(409,'IDEMPOTENCY_CONFLICT')
                return deepcopy(old)
            if len(jobs)>=1000 or not slots.acquire(blocking=False):raise HTTPException(503,'LOCAL_CAPACITY_REACHED')
            ident=str(uuid4());t=now()
            result={'schema_version':'0.1.0','id':ident,'revision':1,'status':'queued','region':{'id':'seoul' if region=='서울특별시' else 'incheon','label':region},'requested_at':t,'finished_at':None,'sources':[{'id':'LH','status':'queued','checked_at':None,'error_code':None,'retryable':False}],'uncovered_source_ids':['SH','GH','iH','municipalities'],'notices':[],'personalization':{'enabled':False,'result':'not_requested','unresolved_conditions':[]}}
            validate_result(result);jobs[ident]=(uid,result);keys[k]=ident
            response=deepcopy(result)
            try:pool.submit(work,ident)
            except Exception:
                del jobs[ident];del keys[k];slots.release();raise HTTPException(503,'WORKER_UNAVAILABLE') from None
            return response
    def owned(ident,token):
        uid=owner(token)
        if ident not in jobs or jobs[ident][0]!=uid:raise HTTPException(404,'JOB_NOT_FOUND')
        return jobs[ident][1]
    @app.get('/v1/search-jobs/{ident}')
    def get(ident:str,x_session_token:str=Header(default='')):
        with lock:return deepcopy(validate_result(owned(ident,x_session_token)))
    @app.post('/v1/search-jobs/{ident}/cancel')
    def cancel(ident:str,x_session_token:str=Header(default='')):
        with lock:
            r=owned(ident,x_session_token)
            if r['status'] not in ('completed','partial','failed','cancelled'):
                r.update(status='cancelled',revision=r['revision']+1,finished_at=now());r['sources'][0]['status']='cancelled'
            return deepcopy(validate_result(r))
    def supply_notice(ident,notice_id,token):
        job=owned(ident,token)
        if job['status'] not in ('partial','completed'):raise HTTPException(409,'SEARCH_NOT_FINISHED')
        notice=next((n for n in job['notices']+job.get('excluded_notices',[]) if n['id']==notice_id),None)
        if notice is None:raise HTTPException(404,'NOTICE_NOT_FOUND')
        return notice
    def supply_failure(ident,notice_id,code):
        return {'job_id':ident,'notice_id':notice_id,'status':'failed','error_code':code,'checked_at':now(),'units':[],'evidence':[],'versions':[]}
    def supply_work(ident,notice):
        key=(ident,notice['id'])
        try:
            try:
                result=supplier(notice)
                result.update(job_id=ident,notice_id=notice['id'])
                validate_supply(result)
            except Exception:result=supply_failure(ident,notice['id'],'SUPPLY_RESPONSE_UNCONFIRMED')
            with lock:supplies[key]=result
        finally:slots.release()
    @app.post('/v1/search-jobs/{ident}/notices/{notice_id}/supply',status_code=202)
    def supply_create(ident:str,notice_id:str,x_session_token:str=Header(default='')):
        with lock:
            notice=supply_notice(ident,notice_id,x_session_token);key=(ident,notice_id)
            if key in supplies:return deepcopy(supplies[key])
            if supplier is fetch_supply and os.environ.get('LH_ENABLE_SUPPLY')!='1':
                return supply_failure(ident,notice_id,'SUPPLY_NOT_ENABLED')
            if not slots.acquire(blocking=False):raise HTTPException(503,'LOCAL_CAPACITY_REACHED')
            result={'job_id':ident,'notice_id':notice_id,'status':'researching','error_code':None,'checked_at':None,'units':[],'evidence':[],'versions':[]}
            supplies[key]=result
            try:pool.submit(supply_work,ident,deepcopy(notice))
            except Exception:
                supplies.pop(key,None);slots.release();raise HTTPException(503,'WORKER_UNAVAILABLE') from None
            return deepcopy(result)
    @app.get('/v1/search-jobs/{ident}/notices/{notice_id}/supply')
    def supply_get(ident:str,notice_id:str,x_session_token:str=Header(default='')):
        with lock:
            supply_notice(ident,notice_id,x_session_token)
            if (ident,notice_id) not in supplies:raise HTTPException(404,'SUPPLY_NOT_REQUESTED')
            return deepcopy(supplies[(ident,notice_id)])
    def document_work(ident,notice):
        try:
            try:
                result=documenter(notice);result.update(job_id=ident,notice_id=notice['id']);validate_document(result)
            except Exception:result=dict(empty_document('failed','DOCUMENT_RESPONSE_UNCONFIRMED'),job_id=ident,notice_id=notice['id'])
            with lock:documents[(ident,notice['id'])]=result
        finally:slots.release()
    @app.post('/v1/search-jobs/{ident}/notices/{notice_id}/document',status_code=202)
    def document_create(ident:str,notice_id:str,x_session_token:str=Header(default='')):
        with lock:
            notice=supply_notice(ident,notice_id,x_session_token);key=(ident,notice_id)
            if key in documents:return deepcopy(documents[key])
            if documenter is fetch_document and os.environ.get('LH_ENABLE_DOCUMENT')!='1':return dict(empty_document('failed','DOCUMENT_NOT_ENABLED'),job_id=ident,notice_id=notice_id)
            if not slots.acquire(blocking=False):raise HTTPException(503,'LOCAL_CAPACITY_REACHED')
            documents[key]=dict(empty_document(),job_id=ident,notice_id=notice_id)
            try:pool.submit(document_work,ident,deepcopy(notice))
            except Exception:
                documents.pop(key,None);slots.release();raise HTTPException(503,'WORKER_UNAVAILABLE') from None
            return deepcopy(documents[key])
    @app.get('/v1/search-jobs/{ident}/notices/{notice_id}/document')
    def document_get(ident:str,notice_id:str,x_session_token:str=Header(default='')):
        with lock:
            supply_notice(ident,notice_id,x_session_token)
            if (ident,notice_id) not in documents:raise HTTPException(404,'DOCUMENT_NOT_REQUESTED')
            return deepcopy(documents[(ident,notice_id)])
    return app
app=create_app()

