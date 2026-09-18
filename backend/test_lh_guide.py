import json
import unittest
from unittest.mock import Mock,patch
from urllib.parse import parse_qs,urlsplit
from backend.lh_probe import request_url,probe
from backend.lh_errors import ERROR_CODES,decode_response
from backend.lh_response import normalize_row,safe_official_url
from backend.test_lh_list import row

class GuideTests(unittest.TestCase):
    def test_document_request_parameters(self):
        params=parse_qs(urlsplit(request_url('synthetic+/=','2026.08.01','2026.09.16','11','06',page=2,size=10,name='서울번동3',status='접수마감',closing_start='2026.09.01',closing_end='2026.09.30')).query)
        self.assertEqual(params,{'serviceKey':['synthetic+/='],'PAN_ST_DT':['20260801'],'PAN_ED_DT':['20260916'],'PG_SZ':['10'],'PAGE':['2'],'CNP_CD':['11'],'UPP_AIS_TP_CD':['06'],'PAN_NM':['서울번동3'],'PAN_SS':['접수마감'],'CLSG_ST_DT':['20260901'],'CLSG_ED_DT':['20260930']})
    def test_invalid_inputs_do_not_call(self):
        for options in [{'page':0},{'size':10000},{'status':'invalid'},{'name':'x'*51},{'closing_start':'2026.10.01','closing_end':'2026.09.01'}]:
            opener=Mock();result=probe('synthetic','2026.08.01','2026.09.16',opener=opener,**options)
            self.assertEqual(result['result'],'not_called');opener.open.assert_not_called()
    def test_all_documented_error_codes_json_and_xml(self):
        for code,expected in ERROR_CODES.items():
            xml=f'<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SYNTHETIC_SECRET</errMsg><returnReasonCode>{int(code):02d}</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>'.encode()
            json_body=json.dumps({'response':{'header':{'resultCode':code,'resultMsg':'SYNTHETIC_SECRET'}}}).encode()
            for body in (xml,json_body):
                payload,error=decode_response(body);self.assertIsNone(payload);self.assertEqual(error,expected)
                self.assertNotIn('SYNTHETIC_SECRET',str((payload,error)))
    def test_no_data_code_not_successful_empty(self):
        payload,error=decode_response(b'{"response":{"header":{"resultCode":"03"}}}')
        self.assertIsNone(payload);self.assertEqual(error,'API_NO_DATA')
    def test_unknown_code_never_echoed(self):
        self.assertEqual(decode_response(b'{"response":{"header":{"resultCode":"PRIVATE_VALUE"}}}'),(None,'API_UNKNOWN_ERROR'))
    def test_xml_dtd_rejected(self):
        self.assertEqual(decode_response(b'<!DOCTYPE a [<!ENTITY x "secret">]><a>&x;</a>')[1],'SOURCE_RESPONSE_UNCONFIRMED')
    def test_required_detail_keys_and_optional_date(self):
        r=row();r.pop('PAN_DT');result=normalize_row(r,'synthetic-secret')
        self.assertEqual(result['SPL_INF_TP_CD'],'010');self.assertIsNone(result['PAN_DT'])
        self.assertEqual(result['CCR_CNNT_SYS_DS_CD'],'03')
    def test_whitespace_status_normalized(self):
        r=row(status=' 접수마감 ');self.assertEqual(normalize_row(r,'synthetic-secret')['PAN_SS'],'접수마감')
    def test_official_response_url_preserves_menu(self):
        r=row();r['DTL_URL']=r['DTL_URL'].replace('mi=1026','mi=1027')
        self.assertIn('mi=1027',normalize_row(r,'synthetic-secret')['DTL_URL'])
    def test_link_mismatch_missing_or_host_rejected(self):
        r=row()
        for url in [None,r['DTL_URL'].replace('10001','99999'),r['DTL_URL'].replace('apply.lh.or.kr','evil.example'),r['DTL_URL']+'&serviceKey=PRIVATE',r['DTL_URL']+'&mi=999']:
            self.assertIsNone(safe_official_url(url,r))
    def test_document_legacy_url(self):
        r=row();url=f"https://apply.lh.or.kr/LH/index.html?gv_url=SIL::CLCC_SIL_0050.xfdl&gv_menuId=1010202&gv_param=CCR_CNNT_SYS_DS_CD:03,PAN_ID:{r['PAN_ID']},LCC:Y"
        clean=safe_official_url(url,r);self.assertIsNotNone(clean);self.assertEqual(urlsplit(clean).hostname,'apply.lh.or.kr')
    def test_encoded_secret_reflection_rejected(self):
        r=row();r['PAN_NM']='SYNTHETIC%2BSECRET'
        with self.assertRaises(ValueError):normalize_row(r,'SYNTHETIC+SECRET')
    def test_missing_url_not_fabricated(self):
        r=row();r.pop('DTL_URL');result=normalize_row(r,'synthetic-secret')
        self.assertIsNone(result['DTL_URL']);self.assertIsNone(result['DTL_URL_MOB'])

if __name__=='__main__':unittest.main()
