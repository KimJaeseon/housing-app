import json
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from backend.verification_gate import assess, main

ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = ROOT / 'backend/eligibility_conditions/2015122300020807.json'
REVIEW = ROOT / 'backend/eligibility_reviews/2015122300020807.json'
PDF = ROOT / 'docs/references/lh-notice-2015122300020807.pdf'


class VerificationGateTests(unittest.TestCase):
    def test_valid_partial_never_promotes(self):
        result = assess(CONDITIONS, REVIEW, PDF)
        self.assertEqual(result['validated_rule_count'], 93)
        self.assertFalse(result['eligible_for_promotion'])
        self.assertEqual(result['status'], 'needs_review')
        self.assertFalse(result['applicant_evaluation'])
        dimensions = [r['dimension'] for r in result['reasons'] if r['code'] == 'DIMENSION_INCOMPLETE']
        self.assertEqual(len(dimensions), 7)
        self.assertIn('latest_changes', dimensions)

    def test_changed_pdf_withholds_validated_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'changed.pdf'
            path.write_bytes(b'%PDF-changed')
            result = assess(CONDITIONS, REVIEW, path)
        self.assertEqual(result['validated_rule_count'], 0)
        self.assertEqual(result['reasons'][0]['code'], 'ARTIFACT_INVALID')

    def test_fabricated_full_coverage_is_invalid(self):
        record = json.loads(CONDITIONS.read_text(encoding='utf-8'))
        record['coverage'] = 'complete'
        record['unreviewed_dimensions'] = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'forged.json'
            path.write_text(json.dumps(record), encoding='utf-8')
            result = assess(path, REVIEW, PDF)
        self.assertEqual(result['reasons'][0]['code'], 'ARTIFACT_INVALID')

    def test_missing_input_is_invalid(self):
        self.assertEqual(assess(CONDITIONS, REVIEW, PDF.with_name('missing.pdf'))['validated_rule_count'], 0)

    def test_wrong_notice_is_invalid(self):
        review = ROOT / 'backend/document_reviews/2015122300020605.json'
        self.assertEqual(assess(CONDITIONS, review, PDF)['reasons'][0]['code'], 'ARTIFACT_INVALID')

    def test_cli_exit_codes_and_machine_readable_output(self):
        for pdf, expected in ((PDF, 1), (PDF.with_name('missing.pdf'), 2)):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(['--conditions', str(CONDITIONS), '--review', str(REVIEW), '--pdf', str(pdf)])
            self.assertEqual(code, expected)
            self.assertEqual(json.loads(output.getvalue())['status'], 'needs_review')
