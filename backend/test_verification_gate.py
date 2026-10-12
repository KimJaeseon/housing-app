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
TABLES = ROOT / 'backend/reviewed_tables/2015122300020807.json'
LEGAL = ROOT / 'backend/external_legal/2015122300020807.json'
ARTIFACTS = ROOT / 'docs/references'


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

    def test_reviewed_tables_add_partial_evidence_without_promotion(self):
        result = assess(CONDITIONS, REVIEW, PDF, reviewed_tables_path=TABLES)
        self.assertEqual(result['reviewed_tables'], {'status': 'valid_partial',
                                                   'income_amount_count': 104,
                                                   'renewal_page_count': 4})
        self.assertEqual(result['status'], 'needs_review')
        self.assertFalse(result['eligible_for_promotion'])
        self.assertIn('EXTERNAL_LEGAL_EVIDENCE_PENDING', [r['code'] for r in result['reasons']])

    def test_missing_reviewed_tables_is_explicit(self):
        result = assess(CONDITIONS, REVIEW, PDF, reviewed_tables_path=TABLES.with_name('missing.json'))
        self.assertEqual(result['reviewed_tables']['status'], 'invalid')
        self.assertIn('REVIEWED_TABLES_ARTIFACT_INVALID', [r['code'] for r in result['reasons']])

    def test_external_legal_is_partial_and_never_promotes(self):
        result = assess(CONDITIONS, REVIEW, PDF, artifact_dir=ARTIFACTS,
                        external_legal_path=LEGAL)
        self.assertEqual(result['external_legal'], {'status': 'valid_partial',
                          'source_count': 2, 'aligned_check_count': 4,
                          'unresolved_check_count': 2})
        self.assertIn('EXTERNAL_LEGAL_EVIDENCE_PENDING', [r['code'] for r in result['reasons']])
        self.assertFalse(result['eligible_for_promotion'])

    def test_external_legal_wrong_source_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            source = ARTIFACTS / 'law-public-housing-rule-annex-5-2-2025-10-31.pdf'
            destination = Path(directory) / source.name
            destination.write_bytes(source.read_bytes() + b'changed')
            result = assess(CONDITIONS, REVIEW, PDF, artifact_dir=directory,
                            external_legal_path=LEGAL)
        self.assertEqual(result['external_legal']['status'], 'invalid')
        self.assertIn('EXTERNAL_LEGAL_ARTIFACT_INVALID', [r['code'] for r in result['reasons']])

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
