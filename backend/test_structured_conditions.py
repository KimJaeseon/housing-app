import json
import tempfile
import unittest
from pathlib import Path

from backend.structured_conditions import load_conditions


REVIEW = Path('backend/document_reviews/2015122300020807.json')
CONDITIONS = Path('backend/structured_conditions/2015122300020807.json')
BUNDONG_REVIEW = Path('backend/document_reviews/2015122300020605.json')
BUNDONG_CONDITIONS = Path('backend/structured_conditions/2015122300020605.json')


class StructuredConditionsTests(unittest.TestCase):
    def check_changed(self, change, conditions=CONDITIONS, review=REVIEW):
        record = json.loads(conditions.read_text(encoding='utf-8'))
        change(record)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'conditions.json'
            path.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_conditions(path, review)

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
        self.check_changed(lambda record: record['rents'][0].update(applicant_group='2구간'))

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

    def test_thousand_won_and_applicant_groups(self):
        record = load_conditions(BUNDONG_CONDITIONS, BUNDONG_REVIEW)
        self.assertEqual(len(record['rents']), 7)
        self.assertEqual(record['rents'][3]['deposit_raw'] * 1000, record['rents'][3]['deposit_won'])
        self.assertEqual(record['rents'][5]['conversion_delta_won'], 25000000)

    def test_thousand_won_unit_or_amount_change(self):
        self.check_changed(lambda record: record['rents'][3].update(deposit_unit='원'), BUNDONG_CONDITIONS, BUNDONG_REVIEW)
        self.check_changed(lambda record: record['rents'][3].update(deposit_raw=50401), BUNDONG_CONDITIONS, BUNDONG_REVIEW)

    def test_thousand_won_conversion_mismatch(self):
        self.check_changed(lambda record: record['rents'][5].update(conversion_delta_raw=25001), BUNDONG_CONDITIONS, BUNDONG_REVIEW)
        self.check_changed(lambda record: record['rents'][5].update(base_rent_id='bundong-21a-youth-no-income-basic'), BUNDONG_CONDITIONS, BUNDONG_REVIEW)

    def test_thousand_won_group_or_fact_mixup(self):
        self.check_changed(lambda record: record['rents'][3].update(applicant_group='청년(소득 없음)'), BUNDONG_CONDITIONS, BUNDONG_REVIEW)
        self.check_changed(lambda record: record['rents'][5].update(fact_id='bundong3-13'), BUNDONG_CONDITIONS, BUNDONG_REVIEW)


if __name__ == '__main__':
    unittest.main()
