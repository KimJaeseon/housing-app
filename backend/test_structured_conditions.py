import json
import tempfile
import unittest
from pathlib import Path

from backend.structured_conditions import load_conditions


REVIEW = Path('backend/document_reviews/2015122300020807.json')
CONDITIONS = Path('backend/structured_conditions/2015122300020807.json')


class StructuredConditionsTests(unittest.TestCase):
    def check_changed(self, change):
        record = json.loads(CONDITIONS.read_text(encoding='utf-8'))
        change(record)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'conditions.json'
            path.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_conditions(path, REVIEW)

    def test_reviewed_conditions(self):
        record = load_conditions(CONDITIONS, REVIEW)
        self.assertEqual(len(record['windows']), 2)
        self.assertEqual(len(record['rents']), 6)

    def test_wrong_review_version(self):
        self.check_changed(lambda record: record.update(pdf_sha256='0' * 64))

    def test_crossed_application_audience(self):
        self.check_changed(lambda record: record['windows'][0].update(fact_id='gangseo-05'))

    def test_changed_or_reversed_application_time(self):
        self.check_changed(lambda record: record['windows'][0].update(end='2026-10-02T17:00:00+09:00'))
        self.check_changed(lambda record: record['windows'][0].update(end='2026-09-29T09:00:00+09:00'))
        self.check_changed(lambda record: record['windows'][0].update(start='2026-10-01T10:00:00+09:00'))

    def test_wrong_timezone(self):
        self.check_changed(lambda record: record['windows'][0].update(start='2026-09-29T10:00:00+00:00'))

    def test_wrong_amount_or_income_band(self):
        self.check_changed(lambda record: record['rents'][0].update(deposit_won=90664000))
        self.check_changed(lambda record: record['rents'][0].update(income_band='2구간'))

    def test_conversion_condition_cannot_masquerade_as_basic(self):
        self.check_changed(lambda record: record['rents'][0].update(condition='max_increase'))

    def test_conversion_requires_matching_basic_condition(self):
        self.check_changed(lambda record: record['rents'][2].update(base_rent_id='gangseo-59a-band-2-basic'))

    def test_conversion_delta_and_monthly_direction(self):
        self.check_changed(lambda record: record['rents'][2].update(conversion_delta_won=80000000))
        self.check_changed(lambda record: record['rents'][3].update(conversion_delta_won=69000000))
        self.check_changed(lambda record: record['rents'][2].update(monthly_rent_won=659460))

    def test_conversion_fact_and_duplicate_condition(self):
        self.check_changed(lambda record: record['rents'][2].update(fact_id='gangseo-10'))
        self.check_changed(lambda record: record['rents'][2].update(condition='max_decrease'))


if __name__ == '__main__':
    unittest.main()
