import copy,json,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from urllib.error import HTTPError
from io import BytesIO
from fastapi.testclient import TestClient
from backend.lh_supply import parameters,parse_supply,fetch_supply
from backend.validation import validate_supply
from backend.test_api import ManualExecutor
from backend.test_lh_list import row
from backend.lh_list import to_notice,collect_list
from backend.app import create_app
STAMP='2026-09-17T00:00:00+00:00'
KEY='SYNTHETIC_SECRET'
def notice():
    r=row();r['SPL_INF_TP_CD']='063'
    return to_notice(r,'seoul',STAMP)
def payload():
    params=parameters(notice(),KEY)
    return [{'dsSch':[params]},{'resHeader':[{'SS_CODE':'Y'}],'dsList01':[{'SBD_LGO_NM':'합성 단지','HTY_NNA':'26A','DDO_AR':'26.55','SPL_AR':'40.2','HSH_CNT':'100','NOW_HSH_CNT':'3','LS_GMY':'10,000,000','RFE':'공고문 참조'}],'dsList01Nm':[{'DDO_AR':'전용면적(㎡)','SPL_AR':'공급면적','HSH_CNT':'세대수','NOW_HSH_CNT':'금회공급 세대수','LS_GMY':'임대보증금(원)','RFE':'월임대료(원)'}]}]
def parsed(p=None):return parse_supply(p if p is not None else payload(),parameters(notice(),KEY),notice(),STAMP,KEY)
class SupplyTests(unittest.TestCase):
    def test_values_and_unknown(self):
        r=parsed();u=r['units'][0];self.assertEqual(u['deposit']['value'],10000000);self.assertIsNone(u['monthly_rent']['value']);self.assertEqual(u['exclusive_area']['value'],26.55);self.assertIsNone(u['supply_area']['value']);self.assertEqual(u['offered_households']['value'],3)
        validate_supply(dict(r,job_id='j',notice_id=notice()['id']))
        self.assertNotIn(KEY,json.dumps(r));self.assertNotIn('serviceKey',json.dumps(r))
    def test_official_guide_example(self):
        lines=Path('docs/references/LH_supply_API_20260202.txt').read_text(encoding='utf-8').splitlines()
        p=json.loads(next(line for line in lines if line.startswith('[{"dsSch"') and '2016122300001530' in line))
        n=notice();n['official_id']='2016122300001530';n['listing']['supply_info_type']='062';n['listing']['detail_type_code']='07'
        r=parse_supply(p,parameters(n,KEY),n,STAMP,KEY)
        self.assertEqual(len(r['units']),5);self.assertTrue(all(u['deposit']['state']=='unknown' and u['monthly_rent']['state']=='unknown' for u in r['units']))
        self.assertEqual(r['units'][0]['exclusive_area']['value'],39.72)
    @patch('backend.lh_supply.resolve_key',return_value=None)
    def test_missing_key(self,_):self.assertEqual(fetch_supply(notice())['error_code'],'MISSING_API_KEY')
    @patch('backend.lh_supply.resolve_key',return_value='bad key')
    def test_invalid_key(self,_):self.assertEqual(fetch_supply(notice())['error_code'],'INVALID_API_KEY_FORMAT')
    @patch('backend.lh_supply.resolve_key',return_value=KEY)
    def test_transport_error_sanitized(self,_):
        op=Mock();op.open.side_effect=TimeoutError(KEY);r=fetch_supply(notice(),op);self.assertNotIn(KEY,json.dumps(r));self.assertEqual(r['status'],'failed')
    def test_empty(self):
        p=payload();p[1]['dsList01']=[];self.assertEqual(parsed(p)['status'],'empty')
    def test_identity_mismatch(self):
        p=payload();p[0]['dsSch'][0]['PAN_ID']='other'
        with self.assertRaisesRegex(ValueError,'MISMATCH'):parsed(p)
    def test_no_success_header(self):
        p=payload();p[1]['resHeader']=[]
        with self.assertRaises(ValueError):parsed(p)
    def test_wrong_units_never_known(self):
        p=payload();p[1]['dsList01Nm'][0]['LS_GMY']='임대보증금(천원)';self.assertIsNone(parsed(p)['units'][0]['deposit']['value'])
    def test_bad_numbers(self):
        for value in ['1,00','-1','1e8','NaN','9007199254740992','약 100만원','']:
            p=payload();p[1]['dsList01'][0]['LS_GMY']=value;self.assertIsNone(parsed(p)['units'][0]['deposit']['value'])
    def test_zero_is_not_missing(self):
        p=payload();p[1]['dsList01'][0]['RFE']='0';self.assertEqual(parsed(p)['units'][0]['monthly_rent']['value'],0)
    def test_reflected_key(self):
        p=payload();p[1]['dsList01'][0]['SBD_LGO_NM']=KEY
        with self.assertRaises(ValueError):parsed(p)
    def test_row_limit(self):
        p=payload();p[1]['dsList01']*=101
        with self.assertRaisesRegex(ValueError,'ROW_LIMIT'):parsed(p)
    @patch('backend.lh_supply.resolve_key',return_value=KEY)
    def test_unsupported_no_network(self,_):
        n=notice();n['listing']['supply_info_type']='010';opener=Mock();self.assertEqual(fetch_supply(n,opener)['error_code'],'UNSUPPORTED_SUPPLY_TYPE');opener.open.assert_not_called()
    @patch('backend.lh_supply.resolve_key',return_value=KEY)
    def test_http_permission_failure(self,_):
        op=Mock();op.open.side_effect=HTTPError('https://unused',403,'Forbidden',{},BytesIO(b'<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>'))
        r=fetch_supply(notice(),op);self.assertEqual(r['error_code'],'API_KEY_NOT_REGISTERED');self.assertEqual(r['units'],[])
    def test_dangling_evidence_rejected(self):
        r=dict(parsed(),job_id='j',notice_id='n');r['evidence']=[]
        with self.assertRaises(ValueError):validate_supply(r)
    def test_failed_not_empty(self):
        r=dict(parsed(),job_id='j',notice_id='n');r['status']='failed';r['error_code']='FAIL'
        with self.assertRaises(ValueError):validate_supply(r)
class SupplyApiTests(unittest.TestCase):
    def setUp(self):
        self.ex=ManualExecutor();self.supplier=Mock(side_effect=lambda n:parsed());r=row();r['SPL_INF_TP_CD']='063'
        with patch('backend.lh_list.resolve_key',return_value=KEY),patch.dict('os.environ',{'LH_POSTED_DATE':'2026.08.01','LH_CLOSING_DATE':'2026.09.30'}):
            outcome=collect_list('seoul',fetcher=lambda *a,**k:{'rows':[r],'total':1})
        self.c=TestClient(create_app(collector=lambda r:copy.deepcopy(outcome),executor=self.ex,supplier=self.supplier));self.h={'X-Session-Token':'a'*40,'Idempotency-Key':'supply'}
        self.j=self.c.post('/v1/search-jobs',json={'region':'서울'},headers=self.h).json();self.path='/v1/search-jobs/'+self.j['id']+'/notices/'+notice()['id']+'/supply'
    def test_pending_rejected(self):self.assertEqual(self.c.post(self.path,headers=self.h).status_code,409)
    def test_idempotent_and_valid(self):
        self.ex.run();self.assertEqual(self.c.get(self.path,headers=self.h).status_code,404)
        self.assertEqual(self.c.post(self.path,headers=self.h).json()['status'],'researching');self.c.post(self.path,headers=self.h);self.assertEqual(len(self.ex.tasks),1);self.ex.run()
        result=self.c.get(self.path,headers=self.h).json();validate_supply(result);self.assertEqual(result['status'],'available');self.supplier.assert_called_once();self.c.post(self.path,headers=self.h);self.assertEqual(len(self.ex.tasks),0)
    def test_ownership_and_missing_notice(self):
        self.ex.run()
        for method in (self.c.get,self.c.post):self.assertEqual(method(self.path,headers={'X-Session-Token':'b'*40}).status_code,404)
        self.assertEqual(self.c.post(self.path.replace(notice()['id'],'missing'),headers=self.h).status_code,404)
    def test_supplier_exception_sanitized(self):
        self.ex.run();self.supplier.side_effect=RuntimeError(KEY);self.c.post(self.path,headers=self.h);self.ex.run();r=self.c.get(self.path,headers=self.h);self.assertNotIn(KEY,r.text);self.assertEqual(r.json()['error_code'],'SUPPLY_RESPONSE_UNCONFIRMED')
    def test_bad_supplier_result_rejected(self):
        self.ex.run();self.supplier.side_effect=None;self.supplier.return_value={'status':'available','units':[]};self.c.post(self.path,headers=self.h);self.ex.run();self.assertEqual(self.c.get(self.path,headers=self.h).json()['status'],'failed')
if __name__=='__main__':unittest.main()
