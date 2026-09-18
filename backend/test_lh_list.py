import copy
import json
import os
import unittest
from unittest.mock import patch,Mock
from fastapi.testclient import TestClient
from backend.lh_list import collect_list,fetch_page,to_notice
from backend.app import create_app
from backend.test_api import ManualExecutor
from backend.validation import validate_result


def row(number=1,total=1,status='접수중',title='합성 공고'):
    return {'PAN_ID':str(10000+number),'AIS_TP_CD':'10','CCR_CNNT_SYS_DS_CD':'03','UPP_AIS_TP_CD':'06',
            'PAN_NM':title,'UPP_AIS_TP_NM':'임대주택','SPL_INF_TP_CD':'010','PAN_DT':'20260819',
            'DTL_URL':f'https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?panId={10000+number}&aisTpCd=10&uppAisTpCd=06&ccrCnntSysDsCd=03&mi=1026',
            'AIS_TP_CD_NM':'행복주택','CNP_CD_NM':'서울특별시','PAN_SS':status,
            'PAN_NT_ST_DT':'2026.08.21','CLSG_DT':'2026.09.02','RNUM':str(number),'ALL_CNT':str(total)}

class ListTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'LH_POSTED_DATE':'2026.08.01','LH_CLOSING_DATE':'2026.09.30'},clear=True);self.env.start()
        self.key=patch('backend.lh_list.resolve_key',return_value='SYNTHETIC_SECRET');self.key.start()
        self.addCleanup(self.env.stop);self.addCleanup(self.key.stop)
    def run_list(self,rows):return collect_list('seoul',fetcher=lambda *a,**k:{'rows':rows,'total':len(rows)})
    def test_review_never_verified(self):
        result=self.run_list([row()]);n=result['notices'][0]
        self.assertEqual(n['verification_status'],'needs_review');self.assertEqual(n['recruitment_status'],'unknown')
        self.assertFalse(n['revision_resolved']);self.assertIsNone(n['current_version_id'])
    def test_closed_and_cancelled_excluded(self):
        result=self.run_list([row(1,2,'접수마감'),row(2,2,'취소')])
        self.assertEqual(result['notices'],[]);self.assertEqual(len(result['excluded_notices']),2)
    def test_correction_not_merged_by_title(self):
        result=self.run_list([row(1,2,title='합성 공고'),row(2,2,title='[정정공고]합성 공고')])
        self.assertEqual(len(result['notices']),2)
        self.assertTrue(any('정정 공고 후보' in x for x in result['notices'][1]['review_reasons']))
    def test_page_two_then_complete(self):
        fetch=Mock(side_effect=[{'rows':[row(i,21) for i in range(1,21)],'total':21},{'rows':[row(21,21)],'total':21}])
        result=collect_list('seoul',fetcher=fetch)
        self.assertEqual(len(result['notices']),21);self.assertTrue(result['collection']['list_complete']);self.assertEqual(fetch.call_count,2)
    def test_duplicate_page_stops(self):
        rows=[row(i,40) for i in range(1,21)]
        fetch=Mock(return_value={'rows':rows,'total':40})
        result=collect_list('seoul',fetcher=fetch)
        self.assertEqual(result['error'],'PAGINATION_CHANGED');self.assertEqual(len(result['notices']),20)
    def test_count_changes_stops(self):
        fetch=Mock(side_effect=[{'rows':[row(i,21) for i in range(1,21)],'total':21},{'rows':[row(21,22)],'total':22}])
        self.assertEqual(collect_list('seoul',fetcher=fetch)['error'],'PAGINATION_CHANGED')
    def test_empty_before_total_is_not_success(self):
        fetch=Mock(side_effect=[{'rows':[row(i,21) for i in range(1,21)],'total':21},{'rows':[],'total':None}])
        self.assertEqual(collect_list('seoul',fetcher=fetch)['error'],'PAGINATION_INCOMPLETE')
    def test_page_cap(self):
        fetch=Mock(return_value={'rows':[row(i,21) for i in range(1,21)],'total':21})
        result=collect_list('seoul',fetcher=fetch,max_pages=1)
        self.assertEqual(result['error'],'PAGE_LIMIT_REACHED');self.assertFalse(result['collection']['list_complete'])
    def test_cancel_between_requests(self):
        cancelled=Mock(side_effect=[False,True]);fetch=Mock(return_value={'rows':[row(i,21) for i in range(1,21)],'total':21})
        result=collect_list('seoul',fetcher=fetch,is_cancelled=cancelled)
        self.assertEqual(result['error'],'CANCELLED');self.assertEqual(fetch.call_count,1)
    def test_timeout_before_network(self):
        fetch=Mock();clock=Mock(side_effect=[0,36])
        self.assertEqual(collect_list('seoul',fetcher=fetch,clock=clock)['error'],'SOURCE_TIME_LIMIT');fetch.assert_not_called()
    def test_region_mismatch_held(self):
        other=row();other['CNP_CD_NM']='부산광역시'
        result=self.run_list([other]);self.assertEqual(result['notices'],[]);self.assertEqual(result['collection']['scope_mismatch_count'],1)
    def test_failed_query_not_zero_success(self):
        result=collect_list('seoul',fetcher=Mock(return_value={'error':'RATE_LIMITED'}))
        self.assertFalse(result['collection']['list_complete']);self.assertFalse(result['collection']['date_filter_verified'])
    def test_reversed_date_no_request(self):
        with patch.dict(os.environ,{'LH_POSTED_DATE':'2026.10.01'}):
            fetch=Mock();self.assertEqual(collect_list('seoul',fetcher=fetch)['error'],'DATE_FILTER_NOT_CONFIGURED');fetch.assert_not_called()
    def test_server_integration_schema_and_stale_rejected(self):
        outcome=self.run_list([row(1,2),row(2,2,'접수마감')]);ex=ManualExecutor()
        c=TestClient(create_app(collector=lambda r:outcome,executor=ex));h={'X-Session-Token':'x'*32,'Idempotency-Key':'1'}
        j=c.post('/v1/search-jobs',json={'region':'서울'},headers=h).json();ex.run();j=c.get('/v1/search-jobs/'+j['id'],headers=h).json()
        validate_result(j);self.assertEqual(j['status'],'partial');self.assertEqual(len(j['excluded_notices']),1)
        j['notices'][0]['checked_in_job_id']='old'
        with self.assertRaises(ValueError):validate_result(j)
    def test_live_mode_routes_to_list(self):
        ex=ManualExecutor();h={'X-Session-Token':'x'*32,'Idempotency-Key':'1'}
        with patch.dict(os.environ,{'LH_ENABLE_LIST':'1'}),patch('backend.app.collect_list',return_value=self.run_list([])) as collect:
            c=TestClient(create_app(executor=ex));j=c.post('/v1/search-jobs',json={'region':'서울'},headers=h).json();ex.run()
            self.assertEqual(c.get('/v1/search-jobs/'+j['id'],headers=h).json()['status'],'partial');collect.assert_called_once()

class FetchTests(unittest.TestCase):
    def fetch(self,mutate=lambda p:None):
        payload=[{'dsSch':[{'PAN_ST_DT':'20260801','PAN_ED_DT':'20260930','CNP_CD':'11','UPP_AIS_TP_CD':'06','PAGE':'1','PG_SZ':'20','ServiceKey':'SYNTHETIC_SECRET'}]}, {'dsList':[row()],'resHeader':[{'SS_CODE':'Y'}]}]
        mutate(payload)
        response=Mock();response.read.return_value=json.dumps(payload).encode();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=response
        with patch('backend.lh_list.build_opener',return_value=opener):return fetch_page('SYNTHETIC_SECRET','2026.08.01','2026.09.30','11',1)
    def test_request_echo_not_returned(self):
        result=self.fetch();self.assertNotIn('SYNTHETIC_SECRET',json.dumps(result));self.assertEqual(len(result['rows']),1)
    def test_ignored_dates_rejected(self):
        result=self.fetch(lambda p:p[0]['dsSch'][0].update(PAN_ST_DT='20260716'))
        self.assertEqual(result['error'],'QUERY_FILTER_MISMATCH')
    def test_out_of_range_row_rejected(self):
        result=self.fetch(lambda p:p[1]['dsList'][0].update(PAN_NT_ST_DT='2026.01.01'))
        self.assertEqual(result['error'],'QUERY_FILTER_MISMATCH')
    def test_secret_reflection_rejected(self):
        result=self.fetch(lambda p:p[1]['dsList'][0].update(PAN_NM='SYNTHETIC_SECRET'))
        self.assertEqual(result['error'],'SOURCE_ROW_INVALID')

if __name__=='__main__':unittest.main()
