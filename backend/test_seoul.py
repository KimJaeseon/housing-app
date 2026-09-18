import unittest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.test_api import ManualExecutor
class SeoulTests(unittest.TestCase):
 def test_aliases(self):
  c=TestClient(create_app(executor=ManualExecutor()))
  for i,name in enumerate(['서울','서울시','서울특별시',' 서울 시 ']):
   r=c.post('/v1/search-jobs',json={'region':name},headers={'X-Session-Token':'x'*32,'Idempotency-Key':str(i)})
   self.assertEqual(r.status_code,202);self.assertEqual(r.json()['region']['id'],'seoul')
 def test_district_not_expanded(self):
  c=TestClient(create_app(executor=ManualExecutor()))
  for name in ['중구','서울 중구','강남구','']:
   self.assertEqual(c.post('/v1/search-jobs',json={'region':name},headers={'X-Session-Token':'x'*32,'Idempotency-Key':'x'}).status_code,422)
