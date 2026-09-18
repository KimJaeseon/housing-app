import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from backend import key_store as store
from backend import lh_probe
from backend.lh_adapter import collect

class KeyStoreTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI required')
    def test_encrypted_roundtrip_and_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'key.dpapi'
            for key in ['syntheticONLY+/=123', 'replacementONLY+/=456']:
                store.save_key(key, path)
                self.assertNotIn(key.encode(), path.read_bytes())
                self.assertEqual(store.load_key(path), key)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI required')
    def test_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'key.dpapi'
            store.save_key('syntheticONLY', path)
            data = bytearray(path.read_bytes()); data[-1] ^= 1; path.write_bytes(data)
            with self.assertRaises(store.KeyStoreError): store.load_key(path)

    def test_bad_file_fails_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'key.dpapi'
            path.write_bytes(b'PRIVATE-SYNTHETIC-KEY')
            with self.assertRaises(store.KeyStoreError) as error: store.load_key(path)
            self.assertNotIn('PRIVATE-SYNTHETIC-KEY', str(error.exception))

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(store.load_key(Path(directory) / 'absent'), '')

    def test_invalid_input_keeps_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'key.dpapi'; path.write_bytes(b'existing')
            with self.assertRaises(store.KeyStoreError): store.save_key('bad key!', path)
            self.assertEqual(path.read_bytes(), b'existing')

    def test_environment_override(self):
        with patch.dict(os.environ, {'LH_SERVICE_KEY':'syntheticENV'}, clear=True), patch.object(store,'load_key') as load:
            self.assertEqual(store.resolve_key(),'syntheticENV'); load.assert_not_called()

    def test_file_fallback(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(store,'load_key',return_value='syntheticFILE'):
            self.assertEqual(store.resolve_key(),'syntheticFILE')

    def test_cli_save_hidden_and_no_echo(self):
        with patch.object(store.getpass,'getpass',return_value='syntheticSECRET'), patch.object(store,'save_key') as save, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(store.main(['save']),0)
            save.assert_called_once_with('syntheticSECRET')
            self.assertNotIn('syntheticSECRET',output.getvalue())

    def test_no_visible_input_fallback(self):
        with patch.object(store.getpass,'getpass',side_effect=store.getpass.GetPassWarning), patch.object(store,'save_key') as save, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(store.main(['save']),2); save.assert_not_called()

    def test_status_never_echoes_secret(self):
        with patch.object(store,'load_key',return_value='syntheticSECRET'), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(store.main(['status']),0)
            self.assertNotIn('syntheticSECRET',output.getvalue())

    def test_adapter_uses_file_and_stays_unverified(self):
        env={'LH_ENABLE_PROBE':'1','LH_POSTED_DATE':'2026.09.01','LH_CLOSING_DATE':'2026.09.30'}
        with patch.dict(os.environ,env,clear=True), patch.object(store,'load_key',return_value='syntheticFILE'), patch('backend.lh_adapter.probe',return_value={'result':'api_success_signal'}) as probe:
            self.assertEqual(collect('seoul'),('RESPONSE_VERIFICATION_PENDING',False))
            self.assertEqual(probe.call_args.args[0],'syntheticFILE')

    def test_corrupt_store_never_calls_network(self):
        with patch.dict(os.environ,{'LH_ENABLE_PROBE':'1'},clear=True), patch.object(store,'load_key',side_effect=store.KeyStoreError('unavailable')), patch('backend.lh_adapter.probe') as probe:
            self.assertEqual(collect('seoul'),('KEY_STORE_UNAVAILABLE',False)); probe.assert_not_called()

    def test_probe_file_read_error_is_sanitized(self):
        with patch.object(store,'resolve_key',side_effect=store.KeyStoreError('unavailable')), patch.object(lh_probe,'probe') as probe, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(lh_probe.main(['--posted','2026.09.01','--closing','2026.09.30']),2)
            self.assertIn('key_store_unavailable',output.getvalue()); probe.assert_not_called()

if __name__ == '__main__': unittest.main()
