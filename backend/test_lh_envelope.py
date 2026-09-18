import copy
import json
import unittest
from backend.lh_probe import classify

class LiveEnvelopeTests(unittest.TestCase):
    def sample(self):
        return [{'dsSch':[{'PAGE':'1','PG_SZ':'3'}]}, {'dsList':[{'PAN_ID':'synthetic-1','AIS_TP_CD':'10','CCR_CNNT_SYS_DS_CD':'03','ALL_CNT':'2','RNUM':'1'},{'PAN_ID':'synthetic-2','AIS_TP_CD':'10','CCR_CNNT_SYS_DS_CD':'03','ALL_CNT':'2','RNUM':'2'}], 'resHeader':[{'SS_CODE':'Y','RS_DTTM':'synthetic'}]}]

    def test_actual_envelope_shape(self):
        result=classify(self.sample())
        self.assertEqual(result['candidate_row_count'],2)
        self.assertEqual(result['reported_total_count'],2)
        self.assertEqual(result['notice_verification'],'pending')

    def test_nested_success_is_not_enough(self):
        self.assertEqual(classify({'unrelated':{'SS_CODE':'Y'}})['result'],'unconfirmed')

    def test_echo_never_leaves_classifier(self):
        payload=self.sample();payload[0]['dsSch'][0]['ServiceKey']='SYNTHETIC-SECRET'
        result=json.dumps(classify(payload))
        self.assertNotIn('SYNTHETIC-SECRET',result);self.assertNotIn('ServiceKey',result)

    def test_duplicates_rejected(self):
        payload=self.sample();payload[1]['dsList'][1]=copy.deepcopy(payload[1]['dsList'][0])
        self.assertEqual(classify(payload)['result'],'unconfirmed')

    def test_conflicting_totals_rejected(self):
        payload=self.sample();payload[1]['dsList'][1]['ALL_CNT']='3'
        self.assertEqual(classify(payload)['result'],'unconfirmed')

    def test_invalid_rows_rejected(self):
        for value in [None,'unexpected',{}, {'PAN_ID':'synthetic'}]:
            payload=self.sample();payload[1]['dsList']=[value]
            self.assertEqual(classify(payload)['result'],'unconfirmed')

    def test_header_failures(self):
        for value in [[],[{'SS_CODE':'N'}],[{'SS_CODE':'Y'},{'SS_CODE':'N'}],None]:
            payload=self.sample();payload[1]['resHeader']=value
            self.assertEqual(classify(payload)['result'],'unconfirmed')

    def test_empty_rows_do_not_verify_search(self):
        payload=self.sample();payload[1]['dsList']=[]
        result=classify(payload)
        self.assertEqual(result['candidate_row_count'],0)
        self.assertIsNone(result['reported_total_count'])
        self.assertEqual(result['notice_verification'],'pending')

if __name__=='__main__':unittest.main()
