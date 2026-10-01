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
ORYU_HTML=Path('docs/references/lh-detail-2015122300019941.html').read_bytes()
ORYU_PDF=Path('docs/references/lh-notice-2015122300019941.pdf').read_bytes()
GANGSEO_HTML=Path('docs/references/lh-detail-2015122300020807.html').read_bytes()
GANGSEO_PDF=Path('docs/references/lh-notice-2015122300020807.pdf').read_bytes()
GANGSEO_ORIGINAL_HTML=Path('docs/references/lh-detail-2015122300020753.html').read_bytes()
GANGSEO_ORIGINAL_PDF=Path('docs/references/lh-notice-2015122300020753.pdf').read_bytes()
CANCEL_HTML=Path('docs/references/lh-detail-2015122300017563.html').read_bytes()
INCHEON_NEW_HTML=Path('docs/references/lh-detail-2015122300017565.html').read_bytes()
INCHEON_CORRECTED_HTML=Path('docs/references/lh-detail-2015122300017569.html').read_bytes()
GANGSEO_NOTICE={'id':'gangseo','official_id':'2015122300020807','title':'[정정공고][정정공고] 강서염창 통합공공임대주택 최초 입주자 모집공고',
 'listing':{'official_url':'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=2015122300020807&ccrCnntSysDsCd=03&uppAisTpCd=06&aisTpCd=48&mi=1026',
            'detail_type_code':'48','housing_type_code':'06','source_system_code':'03'}}
GANGSEO_ORIGINAL_NOTICE={'id':'gangseo-original','official_id':'2015122300020753','title':'강서염창 통합공공임대주택 최초 입주자 모집공고',
 'listing':{'official_url':'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=2015122300020753&ccrCnntSysDsCd=03&uppAisTpCd=06&aisTpCd=48&mi=1026',
            'detail_type_code':'48','housing_type_code':'06','source_system_code':'03'}}
CANCEL_NOTICE={'id':'cancelled','official_id':'2015122300017563','title':'[취소공고]2025년 인천광역시 영구임대주택 예비입주자 모집(인천권역 3개소)',
 'listing':{'official_url':'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId=2015122300017563&ccrCnntSysDsCd=03&uppAisTpCd=06&aisTpCd=09&mi=1026',
            'detail_type_code':'09','housing_type_code':'06','source_system_code':'03'}}
ORYU_NOTICE={'id':'oryu','official_id':'2015122300019941','title':'서울오류 행복주택 예비입주자 모집공고(2026.05.15)',
 'listing':{'official_url':'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?aisTpCd=10&ccrCnntSysDsCd=03&mi=1026&panId=2015122300019941&uppAisTpCd=06',
            'detail_type_code':'10','housing_type_code':'06','source_system_code':'03'}}
def opener(bodies):
 op=Mock();responses=[]
 for body in bodies:
  response=Mock();response.read.return_value=body;response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);responses.append(response)
 op.open.side_effect=responses;return op
class DocumentTests(unittest.TestCase):
 def test_active_corrected_notice_review(self):
  r=fetch_document(GANGSEO_NOTICE,opener([GANGSEO_HTML,GANGSEO_PDF]))
  self.assertTrue(r['reviewed']);self.assertEqual(r['reviewed_at'],'2026-10-01');self.assertEqual(len(r['facts']),12)
  self.assertEqual(r['original_id'],'2015122300020753');self.assertEqual(r['current_id'],GANGSEO_NOTICE['official_id'])
  self.assertTrue(any('2026.10.01 17:00' in f['value'] for f in r['facts']))
  self.assertTrue(any('90,663,000' in f['value'] for f in r['facts']))
  self.assertTrue(any('169,663,000' in f['value'] for f in r['facts']))
  self.assertTrue(any('21,663,000' in f['value'] for f in r['facts']))
  self.assertTrue(any('2027.02.15' in f['value'] for f in r['facts']))
  validate_document(dict(r,job_id='j',notice_id=GANGSEO_NOTICE['id']))
 def test_original_pdf_never_inherits_correction_review(self):
  r=fetch_document(GANGSEO_NOTICE,opener([GANGSEO_HTML,GANGSEO_ORIGINAL_PDF]))
  self.assertEqual(r['status'],'partial');self.assertFalse(r['reviewed']);self.assertEqual(r['facts'],[])
 def test_superseded_original_page_never_inherits_correction_review(self):
  r=fetch_document(GANGSEO_ORIGINAL_NOTICE,opener([GANGSEO_ORIGINAL_HTML,GANGSEO_ORIGINAL_PDF]))
  self.assertEqual(r['status'],'failed');self.assertFalse(r['reviewed']);self.assertEqual(r['facts'],[])
 def test_cancelled_notice_without_pdf_has_distinct_reason(self):
  r=fetch_document(CANCEL_NOTICE,opener([CANCEL_HTML]))
  self.assertEqual(r['error_code'],'DOCUMENT_CANCELLED_NO_PDF');self.assertFalse(r['reviewed']);self.assertEqual(r['facts'],[])
  validate_document(dict(r,job_id='j',notice_id=CANCEL_NOTICE['id']))
 def test_incheon_new_chain_does_not_inherit_cancelled_original(self):
  from backend.lh_document import Tree
  tree=Tree();tree.feed(INCHEON_CORRECTED_HTML.decode('utf-8'))
  title=[n for n in tree.root.all('div') if 'bbs_ViewA' in n.attrs.get('class','').split()][0].all('h3')[0].text()
  notice={'title':title,'official_id':'2015122300017569'}
  meta=read_page(INCHEON_CORRECTED_HTML,notice)
  self.assertEqual(meta['current_id'],'2015122300017569')
  self.assertEqual(meta['original_id'],'2015122300017565')
  self.assertEqual(meta['attachment']['file_id'],'60700335')
  self.assertIn('신청자격 관련',meta['correction'])
  self.assertNotIn(b'2015122300017558',INCHEON_CORRECTED_HTML)
  self.assertNotIn(b'2015122300017563',INCHEON_CORRECTED_HTML)
  # The superseded original page contains both its own and its correction's
  # IDs. It must not silently inherit the correction's reviewed values.
  original_title=title.removeprefix('[정정공고]')
  with self.assertRaisesRegex(ValueError,'DOCUMENT_PAGE_UNCONFIRMED'):
   read_page(INCHEON_NEW_HTML,{'title':original_title,'official_id':'2015122300017565'})
 def test_active_notice_changed_correction_withholds_facts(self):
  html=GANGSEO_HTML.replace('6P 일반공급 현장접수 설명 추가'.encode(), '6P 일반공급 현장접수 설명 변경'.encode())
  r=fetch_document(GANGSEO_NOTICE,opener([html,GANGSEO_PDF]))
  self.assertFalse(r['reviewed']);self.assertIsNone(r['reviewed_at']);self.assertEqual(r['facts'],[])
 def test_active_notice_changed_pdf_withholds_facts(self):
  r=fetch_document(GANGSEO_NOTICE,opener([GANGSEO_HTML,GANGSEO_PDF+b'changed']))
  self.assertFalse(r['reviewed']);self.assertEqual(r['facts'],[])
 def test_uncorrected_notice_review(self):
  r=fetch_document(ORYU_NOTICE,opener([ORYU_HTML,ORYU_PDF]))
  self.assertTrue(r['reviewed']);self.assertEqual(r['reviewed_at'],'2026-10-01');self.assertEqual(len(r['facts']),8)
  self.assertEqual(r['current_id'],ORYU_NOTICE['official_id']);self.assertIsNone(r['original_id'])
  validate_document(dict(r,job_id='j',notice_id=ORYU_NOTICE['id']))
 def test_uncorrected_notice_relationship_conflict(self):
  html=ORYU_HTML.replace(b"var sOtxtPanId = '';",b"var sOtxtPanId = '123';")
  self.assertEqual(fetch_document(ORYU_NOTICE,opener([html]))['error_code'],'DOCUMENT_PAGE_UNCONFIRMED')
 def test_conflicting_page_ids_rejected(self):
  html=ORYU_HTML+b"<script>var panId = '123';</script>"
  self.assertEqual(fetch_document(ORYU_NOTICE,opener([html]))['error_code'],'DOCUMENT_PAGE_UNCONFIRMED')
 def test_uncorrected_notice_pdf_change(self):
  r=fetch_document(ORYU_NOTICE,opener([ORYU_HTML,ORYU_PDF+b'changed']))
  self.assertFalse(r['reviewed']);self.assertEqual(r['facts'],[])
 def test_exact_pdf_review_and_provenance(self):
  r=fetch_document(NOTICE,opener([HTML,PDF]));self.assertTrue(r['reviewed']);self.assertEqual(r['reviewed_at'],'2026-09-17');self.assertEqual(len(r['facts']),17);validate_document(dict(r,job_id='j',notice_id=NOTICE['id']))
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
 def test_invalid_review_withholds_facts(self):
  from tempfile import TemporaryDirectory
  with TemporaryDirectory() as d:
   p=Path(d)/('2015122300020605.json');p.write_text('{"official_id":"2015122300020605"}',encoding='utf-8')
   r=fetch_document(NOTICE,opener([HTML,PDF]),Path(d))
  self.assertFalse(r['reviewed']);self.assertIsNone(r['reviewed_at']);self.assertEqual(r['facts'],[])
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
 def test_missing_review_date_rejected(self):
  r=dict(fetch_document(NOTICE,opener([HTML,PDF])),job_id='j',notice_id='n');r['reviewed_at']=None
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
