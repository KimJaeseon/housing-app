import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from backend import lh_probe as p

class ProbeTests(unittest.TestCase):
    def response(self, body, status=200):
        response = Mock(status=status)
        response.read.return_value = body
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        return opener

    def test_key_is_encoded_once(self):
        url = p.request_url('test+/=', '2026.09.01', '2026.09.30', '11', '06')
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query['serviceKey'], ['test+/='])
        self.assertEqual(query['PAGE'], ['1'])
        self.assertEqual(query['PG_SZ'], ['3'])
        self.assertEqual(query['PAN_ST_DT'], ['20260901'])
        self.assertEqual(query['PAN_ED_DT'], ['20260930'])
        self.assertNotIn('PAN_NT_ST_DT', query)
        self.assertNotIn('CLSG_DT', query)
        self.assertIn('test%2B%2F%3D', url)

    def test_encoded_key_supported(self):
        query = parse_qs(urlsplit(p.request_url('test%2B%2F%3D', '2026.08.01', '2026.09.30', '11', '06')).query)
        self.assertEqual(query['serviceKey'], ['test+/='])

    def test_html_space_and_newline(self):
        self.assertEqual(p.normalize_key('  test%2B%3D\r\n&#x20;'), 'test+=')

    def test_literal_plus_preserved(self):
        self.assertEqual(p.normalize_key('test+/='), 'test+/=')

    def test_invalid_key_not_sent(self):
        for key in ['test%2', 'test%252B', 'test key', '', 'test<script>']:
            opener = Mock()
            self.assertEqual(p.probe(key, '2026.08.01', '2026.09.30', opener=opener)['result'], 'not_called')
            opener.open.assert_not_called()

    def test_redirect_disabled(self):
        self.assertIsNone(p.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com'))

    def test_success_signal_still_unverified(self):
        opener = self.response(json.dumps([{'dsSch':[{}]}, {'dsList':[{'PAN_ID':'synthetic','AIS_TP_CD':'10','CCR_CNNT_SYS_DS_CD':'03','RNUM':'1','ALL_CNT':'1'}], 'resHeader':[{'SS_CODE':'Y'}]}]).encode())
        outcome = p.probe('fake', '2026.08.01', '2026.09.30', opener=opener)
        self.assertEqual(outcome['result'], 'api_success_signal')
        self.assertEqual(outcome['json_shape'], 'list_envelope_validated')
        self.assertEqual(outcome['notice_verification'], 'pending')
        self.assertEqual(outcome['candidate_row_count'], 1)
        opener.open.assert_called_once()

    def test_unknown_json_not_success(self):
        self.assertEqual(p.probe('fake', '2026.08.01', '2026.09.30', opener=self.response(b'{"message":"OK"}'))['result'], 'unconfirmed')

    def test_empty_rows_do_not_establish_no_notices(self):
        result = p.classify([{'dsSch':[{}]}, {'dsList':[], 'resHeader':[{'SS_CODE':'Y'}]}])
        self.assertEqual(result['notice_verification'], 'pending')
        self.assertIsNone(result['reported_total_count'])

    def test_conflicting_codes_not_success(self):
        self.assertEqual(p.classify([{'SS_CODE':'Y'}, {'SS_CODE':'N'}])['result'], 'unconfirmed')

    def test_xml_error_not_success(self):
        self.assertEqual(p.probe('fake', '2026.08.01', '2026.09.30', opener=self.response(b'<error>secret</error>'))['reason'], 'SOURCE_RESPONSE_UNCONFIRMED')

    def test_large_response(self):
        self.assertEqual(p.probe('fake', '2026.08.01', '2026.09.30', opener=self.response(b' ' * (p.MAX_BYTES + 1)))['reason'], 'response_too_large')

    def test_transport_error_does_not_leak(self):
        opener = Mock()
        opener.open.side_effect = RuntimeError('https://example.com?ServiceKey=SECRET')
        result = p.probe('SECRET', '2026.08.01', '2026.09.30', opener=opener)
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertEqual(result['reason'], 'transport_error')

    def test_http_error_does_not_leak(self):
        opener = Mock()
        opener.open.side_effect = HTTPError('https://example.com?key=SECRET', 403, 'SECRET', {}, None)
        result = p.probe('SECRET', '2026.08.01', '2026.09.30', opener=opener)
        self.assertEqual(result['http_status'], 403)
        self.assertNotIn('SECRET', json.dumps(result))

    def test_missing_key_never_calls(self):
        with patch.dict(p.os.environ, {}, clear=True), patch('backend.key_store.load_key', return_value=''), patch.object(p.sys.stdin, 'isatty', return_value=False), patch.object(p, 'probe') as call:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = p.main(['--posted','2026.09.01','--closing','2026.09.30'])
            call.assert_not_called()
            self.assertEqual(result, 2)
            self.assertEqual(json.loads(output.getvalue())['reason'], 'missing_key')

    def test_invalid_date(self):
        with self.assertRaises(p.argparse.ArgumentTypeError):
            p.date_value('2026.02.30')
        with self.assertRaises(p.argparse.ArgumentTypeError):
            p.date_value('2026-09-10')

if __name__ == '__main__':
    unittest.main()

