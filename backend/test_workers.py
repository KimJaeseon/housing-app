import os,unittest
from unittest.mock import patch
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.test_api import ManualExecutor
from backend.lh_adapter import collect
class WorkerTests(unittest.TestCase):
    def test_cancelled_queue_never_calls(self):
        ex=ManualExecutor();calls=[];c=TestClient(create_app(lambda r:calls.append(r),ex));h={'X-Session-Token':'x'*32,'Idempotency-Key':'x'}
        j=c.post('/v1/search-jobs',json={'region':'서울'},headers=h).json();url='/v1/search-jobs/'+j['id'];c.post(url+'/cancel',headers=h);ex.run();self.assertEqual(calls,[]);self.assertEqual(c.get(url,headers=h).json()['status'],'cancelled')
    def test_late_response_cannot_overwrite_cancel(self):
        entered=Event();release=Event()
        def worker(r):entered.set();release.wait(3);return ('RESPONSE_VERIFICATION_PENDING',False)
        with ThreadPoolExecutor(max_workers=1) as ex:
            c=TestClient(create_app(worker,ex));h={'X-Session-Token':'x'*32,'Idempotency-Key':'x'};j=c.post('/v1/search-jobs',json={'region':'서울'},headers=h).json();url='/v1/search-jobs/'+j['id']
            self.assertTrue(entered.wait(2));a=c.post(url+'/cancel',headers=h).json();release.set()
        self.assertEqual(c.get(url,headers=h).json(),a)
    def test_get_does_not_start_work(self):
        ex=ManualExecutor();c=TestClient(create_app(executor=ex));h={'X-Session-Token':'x'*32,'Idempotency-Key':'x'};j=c.post('/v1/search-jobs',json={'region':'서울'},headers=h).json();self.assertEqual(c.get('/v1/search-jobs/'+j['id'],headers=h).json(),j)
    def test_queue_limit(self):
        ex=ManualExecutor();c=TestClient(create_app(executor=ex));h={'X-Session-Token':'x'*32}
        for i in range(8):self.assertEqual(c.post('/v1/search-jobs',json={'region':'서울'},headers=dict(h,**{'Idempotency-Key':str(i)})).status_code,202)
        self.assertEqual(c.post('/v1/search-jobs',json={'region':'서울'},headers=dict(h,**{'Idempotency-Key':'9'})).status_code,503)
    def test_missing_key_no_call(self):
        with patch.dict(os.environ,{'LH_ENABLE_PROBE':'1'},clear=True),patch('backend.key_store.load_key',return_value=''),patch('backend.lh_adapter.probe') as p:
            self.assertEqual(collect('seoul')[0],'MISSING_API_KEY');p.assert_not_called()
    def test_invalid_date_no_call(self):
        with patch.dict(os.environ,{'LH_ENABLE_PROBE':'1','LH_SERVICE_KEY':'synthetic'},clear=True),patch('backend.lh_adapter.probe') as p:
            self.assertEqual(collect('seoul')[0],'DATE_FILTER_NOT_CONFIGURED');p.assert_not_called()
    def test_success_is_not_verified(self):
        env={'LH_ENABLE_PROBE':'1','LH_SERVICE_KEY':'synthetic','LH_POSTED_DATE':'2026.09.01','LH_CLOSING_DATE':'2026.09.30'}
        with patch.dict(os.environ,env,clear=True),patch('backend.lh_adapter.probe',return_value={'result':'api_success_signal'}):self.assertEqual(collect('seoul')[0],'RESPONSE_VERIFICATION_PENDING')
if __name__=='__main__':unittest.main()
