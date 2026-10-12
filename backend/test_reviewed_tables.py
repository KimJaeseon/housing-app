import copy
import json
import tempfile
import unittest
from pathlib import Path

from backend.reviewed_tables import load_reviewed_tables

ROOT=Path(__file__).resolve().parents[1]
TABLES=ROOT/'backend/reviewed_tables/2015122300020807.json'
REVIEW=ROOT/'backend/eligibility_reviews/2015122300020807.json'
PDF=ROOT/'docs/references/lh-notice-2015122300020807.pdf'


class ReviewedTablesTests(unittest.TestCase):
    def test_exact_income_table_and_renewal_boundaries(self):
        record=load_reviewed_tables(TABLES,PDF,REVIEW)
        income=record['income_amounts']
        self.assertEqual(sum(map(len,income['amounts_won'])),104)
        self.assertEqual(income['amounts_won'][0][3],2564238)
        self.assertEqual(income['amounts_won'][7][-1],20948696)
        renewal=record['renewal']
        self.assertEqual(renewal['income_surcharge']['first_renewal_percent'],[105,110,115])
        self.assertEqual(renewal['income_surcharge']['later_renewal_percent'],[110,120,130])
        self.assertEqual(renewal['overlap']['rule'],'highest_rate_only')
        self.assertEqual(renewal['exceptions']['priority_supply_excludes'],['income_surcharge','asset_surcharge'])
        self.assertFalse(record['applicant_evaluation'])

    def test_changed_amount_or_exception_is_rejected(self):
        original=json.loads(TABLES.read_text(encoding='utf-8'))
        for change in (
            lambda r: r['income_amounts']['amounts_won'][0].__setitem__(3,2564239),
            lambda r: r['renewal']['overlap'].update(rule='add_all_rates'),
            lambda r: r['renewal']['exceptions']['priority_supply_excludes'].pop(),
            lambda r: r.update(applicant_evaluation=True),
        ):
            record=copy.deepcopy(original);change(record)
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'tables.json'
                path.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
                with self.assertRaises(ValueError):load_reviewed_tables(path,PDF,REVIEW)

    def test_other_pdf_is_rejected(self):
        with self.assertRaises(ValueError):
            load_reviewed_tables(TABLES,ROOT/'docs/references/lh-notice-2015122300020605.pdf',REVIEW)
