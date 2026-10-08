import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from backend.separate_notice import capture, load_snapshot, parse_page, public_extract, MAX_HTML, MAX_PDF
from urllib.error import HTTPError
from urllib.request import build_opener, Request
from email.message import Message
from backend.lh_probe import NoRedirect
from backend.verification_gate import assess

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'backend/separate_notices/9102835612.json'
ARTIFACTS = ROOT / 'docs/references'
PROFILE = json.loads(RECORD.read_text(encoding='utf-8'))
HTML = (ARTIFACTS / PROFILE['html_artifact']).read_bytes()
PDF = (ARTIFACTS / PROFILE['attachments'][0]['artifact']).read_bytes()


class Opener:
    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        return io.BytesIO(self.bodies.pop(0))


class SeparateNoticeTests(unittest.TestCase):
    def test_saved_real_snapshot(self):
        record = load_snapshot(RECORD, ARTIFACTS, '2015122300020807')
        self.assertEqual(record['relation'], 'candidate')
        self.assertEqual(record['published_on'], '2026-10-01')
        self.assertEqual(record['attachments'][0]['file_id'], '68835087')

    def test_capture_binds_every_artifact(self):
        opener = Opener([HTML, PDF])
        record, bodies = capture(PROFILE['source_url'], PROFILE['title'], '2015122300020807', opener)
        self.assertEqual(opener.calls, [PROFILE['source_url'], PROFILE['attachments'][0]['url']])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for name, body in bodies.items():
                (path / name).write_bytes(body)
            (path / 'record.json').write_text(json.dumps(record), encoding='utf-8')
            self.assertEqual(load_snapshot(path / 'record.json', path, '2015122300020807'), record)

    def test_untrusted_url_is_rejected_before_network(self):
        for url in ('https://evil.example/lhapply/apply/noti/an/view.do?bbsSn=9102835612',
                    PROFILE['source_url'] + '&bbsSn=123', PROFILE['source_url'] + '#fragment',
                    PROFILE['source_url'].replace('https:', 'http:'),
                    PROFILE['source_url'] + '&next=https://evil.example'):
            opener = Opener([])
            with self.subTest(url=url), self.assertRaises(ValueError):
                capture(url, PROFILE['title'], '2015122300020807', opener)
            self.assertEqual(opener.calls, [])

    def test_wrong_identity_and_title(self):
        with self.assertRaises(ValueError):
            parse_page(HTML, PROFILE['source_url'].replace('9102835612', '123'), PROFILE['title'])
        with self.assertRaises(ValueError):
            parse_page(HTML, PROFILE['source_url'], 'other notice')

    def test_unsupported_attachment_is_rejected(self):
        changed = HTML.replace(b'/lhapply/lhFile.do?fileid=68835087', b'https://evil.example/file.pdf')
        with self.assertRaises(ValueError):
            parse_page(changed, PROFILE['source_url'], PROFILE['title'])

    def test_duplicate_attachments_are_rejected(self):
        text = HTML.decode('utf-8')
        link = '<a href="/lhapply/lhFile.do?fileid=68835087">copy.pdf</a>'
        text = text.replace('class="bbsV_atchmnfl">', 'class="bbsV_atchmnfl">' + link)
        with self.assertRaises(ValueError):
            parse_page(text.encode('utf-8'), PROFILE['source_url'], PROFILE['title'])

    def test_size_limit_and_not_pdf(self):
        for bodies in ([b'x' * (MAX_HTML + 1)], [HTML, b'not a PDF'], [HTML, b'%PDF-' + b'x' * MAX_PDF]):
            with self.subTest(size=len(bodies)), self.assertRaises(ValueError):
                capture(PROFILE['source_url'], PROFILE['title'], '2015122300020807', Opener(bodies))

    def test_public_extract_omits_forms_and_session_values(self):
        private = (b'<input name="csrfToken" value="private-value"><script>secret()</script>'
                   b'<style>private-style</style><form>private-form</form>')
        raw = HTML.replace(b'class="bbsV_cont">', b'class="bbsV_cont">' + private)
        self.assertIn(b'private-value', raw)
        extracted = public_extract(raw, PROFILE['source_url'], PROFILE['title'])
        self.assertNotIn(b'private-value', extracted)
        self.assertNotIn(b'secret()', extracted)
        self.assertNotIn(b'private-style', extracted)
        self.assertNotIn(b'private-form', extracted)
        for tag in (b'<input', b'<script', b'<style', b'<form'):
            self.assertNotIn(tag, extracted)
        self.assertEqual(parse_page(extracted, PROFILE['source_url'], PROFILE['title'])['bulletin_id'], '9102835612')

    def test_production_opener_disables_redirects(self):
        # Exercise the handler installed in the real opener, without network access.
        opener = build_opener(NoRedirect())
        handler = next(h for h in opener.handlers if isinstance(h, NoRedirect))
        headers = Message(); headers['Location'] = 'https://evil.example/'
        request = Request(PROFILE['source_url'])
        self.assertIsNone(handler.redirect_request(request, None, 302, 'Found', headers, 'https://evil.example/'))
        with self.assertRaises(HTTPError):
            opener.error('http', request, io.BytesIO(b''), 302, 'Found', headers)

    def test_second_attachment_must_be_present_and_unchanged(self):
        extra = b'<a href="/lhapply/lhFile.do?fileid=123">second.pdf</a>'
        html = HTML.replace(b'class="bbsV_atchmnfl">', b'class="bbsV_atchmnfl">' + extra)
        record, bodies = capture(PROFILE['source_url'], PROFILE['title'], '2015122300020807', Opener([html, PDF, PDF]))
        self.assertEqual(len(record['attachments']), 2)
        for changed in (None, b'%PDF-changed'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                for name, body in bodies.items():
                    if name == record['attachments'][1]['artifact']:
                        if changed is None:
                            continue
                        body = changed
                    (path / name).write_bytes(body)
                manifest = path / 'record.json'
                manifest.write_text(json.dumps(record), encoding='utf-8')
                with self.assertRaises((ValueError, OSError)):
                    load_snapshot(manifest, path, '2015122300020807')

    def test_manifest_tampering_withholds_snapshot(self):
        for key, value in (('relation', 'confirmed'), ('coverage', 'complete'),
                           ('summary', 'changed'), ('html_artifact', '../outside.html'),
                           ('candidate_official_id', '123')):
            record = copy.deepcopy(PROFILE); record[key] = value
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'record.json'
                path.write_text(json.dumps(record), encoding='utf-8')
                with self.subTest(key=key), self.assertRaises(ValueError):
                    load_snapshot(path, ARTIFACTS, '2015122300020807')

    def test_changed_or_missing_artifact(self):
        for body in (None, b'%PDF-changed'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                (path / PROFILE['html_artifact']).write_bytes(HTML)
                if body is not None:
                    (path / PROFILE['attachments'][0]['artifact']).write_bytes(body)
                with self.subTest(body=body), self.assertRaises((ValueError, OSError)):
                    load_snapshot(RECORD, path, '2015122300020807')

    def test_gate_keeps_pending_for_valid_candidate(self):
        result = self.gate(RECORD, ARTIFACTS)
        self.assertEqual(result['separate_notice']['status'], 'valid_candidate')
        codes = [r['code'] for r in result['reasons']]
        self.assertIn('SEPARATE_NOTICES_PENDING', codes)
        self.assertIn('SEPARATE_NOTICE_RELATION_UNCONFIRMED', codes)
        self.assertFalse(result['eligible_for_promotion'])

    def test_gate_invalid_snapshot_does_not_erase_valid_rules(self):
        result = self.gate(RECORD.with_name('missing.json'), ARTIFACTS)
        self.assertEqual(result['separate_notice']['status'], 'invalid')
        self.assertEqual(result['validated_rule_count'], 93)
        self.assertIn('SEPARATE_NOTICE_ARTIFACT_INVALID', [r['code'] for r in result['reasons']])

    @staticmethod
    def gate(record, artifacts):
        return assess(ROOT / 'backend/eligibility_conditions/2015122300020807.json',
                      ROOT / 'backend/eligibility_reviews/2015122300020807.json',
                      ARTIFACTS / 'lh-notice-2015122300020807.pdf', record, artifacts)
