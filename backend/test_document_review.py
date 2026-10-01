import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.document_review import load_review, validate_pdf


PROFILE = Path('backend/document_reviews/2015122300020605.json')
PDF = Path('docs/references/lh-notice-2015122300020605.pdf')


class ReviewRecordTests(unittest.TestCase):
    def test_known_pdf(self):
        result = validate_pdf(PROFILE, PDF)
        self.assertEqual(result['facts'], 17)
        self.assertEqual(result['reviewed_at'], '2026-09-17')

    def test_invalid_review_records(self):
        source = json.loads(PROFILE.read_text(encoding='utf-8'))
        for change in ('identity', 'page', 'locator', 'duplicate', 'evidence'):
            with self.subTest(change=change), TemporaryDirectory() as directory:
                record = copy.deepcopy(source)
                if change == 'identity':
                    record['source']['current_id'] = '123'
                elif change == 'page':
                    record['facts'][0]['page'] = 30
                elif change == 'locator':
                    record['facts'][0]['source_locator'] = 'p.2 다른 항목'
                elif change == 'duplicate':
                    record['facts'][1]['id'] = record['facts'][0]['id']
                else:
                    record['facts'][0]['source_locator'] = ''
                path = Path(directory) / 'review.json'
                path.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_review(path)

    def test_changed_pdf(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'changed.pdf'
            path.write_bytes(PDF.read_bytes() + b'changed')
            with self.assertRaises(ValueError):
                validate_pdf(PROFILE, path)


if __name__ == '__main__':
    unittest.main()
