import copy,json,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from fastapi.testclient import TestClient
from backend.lh_document import fetch_document,read_page,MAX_HTML,MAX_PDF
from backend.validation import validate_document
from backend.app import create_app
from backend.test_api import ManualExecutor
JOB=json.loads(Path('docs/validation/2026-09-16_LH_LIST_RESPONSE.json').read_text(encoding='utf-8'))
NOTICE=JOB['excluded_notices'][0]
NOTICE['listing'].update(detail_type_code='10',housing_type_code='06',source_system_code='03',supply_info_type='063')
HTML=Path('docs/references/lh-detail-2015122300020605.html').read_bytes()
PDF=Path('docs/references/lh-notice-2015122300020605.pdf').read_bytes()
def opener(bodies):
 op=Mock();responses=[]
 for body in bodies:
  response=Mock();response.read.return_value=body;response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);responses.append(response)
 op.open.side_effect=responses;return op
class DocumentTests(unittest.TestCase):
 def test_exact_pdf_review_and_provenance(self):
  r=fetch_document(NOTICE,opener([HTML,PDF]));self.assertTrue(r['reviewed']);self.assertEqual(len(r['facts']),17);validate_document(dict(r,job_id='j',notice_id=NOTICE['id']))
  self.assertTrue(any('50,400,000' in f['value'] for f in r['facts']));self.assertTrue(any('75,400,000' in f['value'] for f in r['facts']))
  self.assertEqual(r['original_id'],'2015122300020577');self.assertNotIn('_correction',r)
 def test_changed_pdf_withholds_review(self):
  r=fetch_document(NOTICE,opener([HTML,PDF+b'changed']));self.assertEqual(r['status'],'partial');self.assertFalse(r['reviewed']);self.assertEqual(r['facts'],[])
 def test_changed_current_notice_withholds_review(self):
  html=HTML.replace(b"var currPanId = '2015122300020605'",b"var currPanId = '2015122300020606'")
  self.assertFalse(fetch_document(NOTICE,opener([html,PDF]))['reviewed'])
 def test_changed_correction_withholds_review(self):
  html=HTML.replace(b'70,320->75,400',b'70,320->76,400');self.assertFalse(fetch_document(NOTICE,opener([html,PDF]))['reviewed'])
 def test_unknown_review(self):
  from tempfile import TemporaryDirectory
  with TemporaryDirectory() as d:r=fetch_document(NOTICE,opener([HTML,PDF]),Path(d))
  self.assertEqual(r['status'],'partial');self.assertEqual(r['facts'],[])
 def test_wrong_title_rejected(self):
  n=copy.deepcopy(NOTICE);n['title']='other';self.assertEqual(fetch_document(n,opener([HTML]))['error_code'],'DOCUMENT_IDENTITY_MISMATCH')
 def test_foreign_url_never_requested(self):
  n=copy.deepcopy(NOTICE);n['listing']['official_url']='https://example.org/';op=opener([]);self.assertEqual(fetch_document(n,op)['status'],'failed');op.open.assert_not_called()
 def test_pdf_disguised_html(self):self.assertEqual(fetch_document(NOTICE,opener([HTML,b'<html>login</html>']))['error_code'],'DOCUMENT_NOT_PDF')
 def test_size_limits(self):
  self.assertEqual(fetch_document(NOTICE,opener([b'x'*(MAX_HTML+1)]))['error_code'],'DOCUMENT_TOO_LARGE')
  self.assertEqual(fetch_document(NOTICE,opener([HTML,b'%PDF-'+b'x'*MAX_PDF]))['error_code'],'DOCUMENT_TOO_LARGE')
 def test_missing_attachment_not_empty_success(self):
  html=HTML.replace(b"javascript:fileDownLoad('68214585');",b'javascript:void(0);')
  self.assertEqual(fetch_document(NOTICE,opener([html]))['error_code'],'DOCUMENT_PDF_NOT_UNIQUE')
 def test_unreviewed_facts_rejected(self):
  r=dict(fetch_document(NOTICE,opener([HTML,PDF])),job_id='j',notice_id='n');r['reviewed']=False
  with self.assertRaises(ValueError):validate_document(r)
 def test_external_pdf_rejected(self):
  r=dict(fetch_document(NOTICE,opener([HTML,PDF])),job_id='j',notice_id='n');r['pdf_url']='https://elsewhere.test/file.pdf'
  with self.assertRaises(ValueError):validate_document(r)
 def test_remote_error_sanitized(self):
  op=Mock();op.open.side_effect=RuntimeError('SECRET');r=fetch_document(NOTICE,op);self.assertNotIn('SECRET',json.dumps(r));self.assertEqual(r['status'],'failed')
class DocumentApiTests(unittest.TestCase):
 def setUp(self):
  self.ex=ManualExecutor();self.provider=Mock(side_effect=lambda n:fetch_document(n,opener([HTML,PDF])))
  outcome={k:copy.deepcopy(JOB[k]) for k in ['collection','notices','excluded_notices']};outcome.update(error='DOCUMENT_VERIFICATION_PENDING',checked_at=JOB['finished_at'])
  self.c=TestClient(create_app(collector=lambda r:copy.deepcopy(outcome),executor=self.ex,documenter=self.provider));self.h={'X-Session-Token':'a'*40,'Idempotency-Key':'doc'}
  job=self.c.post('/v1/search-jobs',json={'region':'서울'},headers=self.h).json();self.path='/v1/search-jobs/'+job['id']+'/notices/'+NOTICE['id']+'/document'
 def test_researching_parent(self):self.assertEqual(self.c.post(self.path,headers=self.h).status_code,409)
 def test_owned_idempotent_and_verified_guard(self):
  self.ex.run();self.assertEqual(self.c.get(self.path,headers=self.h).status_code,404)
  r=self.c.post(self.path,headers=self.h);self.assertEqual(r.status_code,202);self.assertEqual(r.json()['status'],'researching');self.c.post(self.path,headers=self.h);self.assertEqual(len(self.ex.tasks),1);self.ex.run()
  r=self.c.get(self.path,headers=self.h).json();validate_document(r);self.assertTrue(r['reviewed']);self.c.post(self.path,headers=self.h);self.provider.assert_called_once()
  j=self.c.get(self.path.split('/notices/')[0],headers=self.h).json();self.assertEqual(j['excluded_notices'][0]['verification_status'],'needs_review')
 def test_other_session(self):
  self.ex.run()
  for method in [self.c.get,self.c.post]:self.assertEqual(method(self.path,headers={'X-Session-Token':'b'*40}).status_code,404)
 def test_bad_worker_result_sanitized(self):
  self.ex.run();self.provider.side_effect=ValueError('SECRET');self.c.post(self.path,headers=self.h);self.ex.run();r=self.c.get(self.path,headers=self.h);self.assertNotIn('SECRET',r.text);self.assertEqual(r.json()['status'],'failed')
if __name__=='__main__':unittest.main()
