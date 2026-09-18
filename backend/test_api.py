import json,unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.validation import validate_result
class ManualExecutor:
    def __init__(self): self.tasks=[]
    def submit(self,fn,*args): self.tasks.append((fn,args))
    def run(self):
        fn,args=self.tasks.pop(0);fn(*args)
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.executor=ManualExecutor();self.c=TestClient(create_app(collector=lambda region:('ADAPTER_NOT_CONFIGURED',False),executor=self.executor));self.h={'X-Session-Token':'a'*40,'Idempotency-Key':'test'}
    def make(self):return self.c.post('/v1/search-jobs',json={'region':'서울'},headers=self.h)
    def test_create_schema(self):
        r=self.make();self.assertEqual(r.status_code,202);validate_result(r.json())
    def test_no_false_empty(self):
        r=self.make().json();self.executor.run();x=self.c.get('/v1/search-jobs/'+r['id'],headers=self.h).json();self.assertEqual(x['status'],'failed');self.assertEqual(x['sources'][0]['error_code'],'ADAPTER_NOT_CONFIGURED')
    def test_idempotent(self):self.assertEqual(self.make().json()['id'],self.make().json()['id'])
    def test_conflict(self):
        self.make();self.assertEqual(self.c.post('/v1/search-jobs',json={'region':'인천'},headers=self.h).status_code,409)
    def test_new_request(self):
        a=self.make().json()['id'];self.h['Idempotency-Key']='new';self.assertNotEqual(a,self.make().json()['id'])
    def test_owner(self):
        ident=self.make().json()['id'];h={'X-Session-Token':'b'*40}
        self.assertEqual(self.c.get('/v1/search-jobs/'+ident,headers=h).status_code,404)
        self.assertEqual(self.c.post('/v1/search-jobs/'+ident+'/cancel',headers=h).status_code,404)
    def test_cancel_terminal(self):
        ident=self.make().json()['id'];a=self.c.post('/v1/search-jobs/'+ident+'/cancel',headers=self.h).json();b=self.c.get('/v1/search-jobs/'+ident,headers=self.h).json();self.assertEqual(a,b);self.assertEqual(a['status'],'cancelled')
    def test_no_session(self):self.assertEqual(self.c.post('/v1/search-jobs',json={'region':'서울'},headers={'Idempotency-Key':'x'}).status_code,401)
    def test_unknown_region(self):self.assertEqual(self.c.post('/v1/search-jobs',json={'region':'경기'},headers=self.h).status_code,422)
    def test_extra_private_fields_rejected(self):self.assertEqual(self.c.post('/v1/search-jobs',json={'region':'서울','income':100},headers=self.h).status_code,422)
    def test_examples_schema(self):
        for p in Path('shared/contracts').glob('*.json'):
            if p.name.endswith('schema.json'):continue
            validate_result(json.loads(p.read_text(encoding='utf-8-sig')))
    def test_false_completed_rejected(self):
        r=self.make().json();r.update(status='completed',finished_at=r['requested_at'])
        with self.assertRaises(ValueError):validate_result(r)
    def test_schema_wrong_timestamp(self):
        r=self.make().json();r['requested_at']='yesterday'
        with self.assertRaises(ValueError):validate_result(r)
    def test_schema_missing_field(self):
        r=self.make().json();del r['sources']
        with self.assertRaises(ValueError):validate_result(r)
if __name__=='__main__':unittest.main(verbosity=2)

