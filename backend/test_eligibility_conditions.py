import copy
import json
import tempfile
import unittest
from pathlib import Path

from backend.eligibility_conditions import load_eligibility, main

CONDITIONS = Path('backend/eligibility_conditions/2015122300020807.json')
REVIEW = Path('backend/eligibility_reviews/2015122300020807.json')
PDF = Path('docs/references/lh-notice-2015122300020807.pdf')


class EligibilityTests(unittest.TestCase):
    def reject(self, change):
        record = json.loads(CONDITIONS.read_text(encoding='utf-8'))
        change(record)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'conditions.json'
            path.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_eligibility(path, REVIEW)

    def test_source_bound_partial_model(self):
        record = load_eligibility(CONDITIONS, REVIEW)
        self.assertEqual(len(record['rules']), 46)
        self.assertFalse(record['applicant_evaluation'])
        self.assertEqual(record['rules'][1]['exception_of'], 'age-default')
        self.assertEqual(record['rules'][8]['predicate']['scope'], 'future_household')

    def test_wrong_notice_and_document(self):
        self.reject(lambda r: r.update(official_id='123'))
        self.reject(lambda r: r.update(pdf_sha256='0' * 64))

    def test_wrong_date_and_non_schedule_evidence(self):
        self.reject(lambda r: r['as_of'].update(date='2026-10-08'))
        self.reject(lambda r: r['as_of'].update(fact_id='age-default'))

    def test_missing_condition_cannot_be_complete(self):
        self.reject(lambda r: r.update(coverage='complete'))
        self.reject(lambda r: r.update(applicant_evaluation=True))
        self.reject(lambda r: r['unreviewed_dimensions'].remove('income'))
        self.reject(lambda r: r['rules'].pop(1))

    def test_age_threshold_and_boolean_rejected(self):
        self.reject(lambda r: r['rules'][0]['predicate'].update(years=18))
        self.reject(lambda r: r['rules'][0]['predicate'].update(years=9))
        self.reject(lambda r: r['rules'][0]['predicate'].update(years=True))

    def test_minor_exception_cannot_drop_consent_or_registration(self):
        self.reject(lambda r: r['rules'][1]['predicate']['requirements'].pop(0))
        self.reject(lambda r: r['rules'][1]['predicate']['requirements'].pop())

    def test_elderly_scope_cannot_drop_marital_or_household_qualifier(self):
        self.reject(lambda r: r['rules'][7].update(applies_to='고령자'))
        self.reject(lambda r: r['rules'][7]['predicate'].update(scope='household'))

    def test_cannot_cross_age_and_housing_exceptions(self):
        self.reject(lambda r: r['rules'][1].update(exception_of='housing-default'))
        self.reject(lambda r: r['rules'][6].update(exception_of='age-default'))

    def test_missing_parent_self_reference_and_chains(self):
        self.reject(lambda r: r['rules'][6].update(exception_of=None))
        self.reject(lambda r: r['rules'][0].update(exception_of='housing-default'))
        self.reject(lambda r: r['rules'][5].update(exception_of='age-default'))
        self.reject(lambda r: r['rules'][1].update(exception_of='missing'))
        self.reject(lambda r: r['rules'][1].update(exception_of='age-child'))
        self.reject(lambda r: r['rules'][1].update(exception_of='age-sibling'))

    def test_duplicate_rule_and_evidence_mixup(self):
        self.reject(lambda r: r['rules'].append(copy.deepcopy(r['rules'][0])))
        self.reject(lambda r: r['rules'][1].update(fact_id='age-sibling'))

    def test_source_text_cannot_silently_change(self):
        self.reject(lambda r: r['rules'][1].update(source_text='미성년자 누구나 신청 가능'))

    def test_reviewed_household_registration_and_foreign_spouse_preserved(self):
        self.reject(lambda r: r['rules'][12]['predicate']['requirements'].pop())
        self.reject(lambda r: r['rules'][13]['predicate']['requirements'].pop())

    def test_income_and_asset_scopes_cannot_be_crossed(self):
        self.reject(lambda r: r['rules'][19].update(exception_of='income-scope-default'))
        self.reject(lambda r: r['rules'][19]['predicate'].update(scope='household'))
        self.reject(lambda r: r['rules'][21]['predicate']['requirements'].pop())

    def test_birth_bonus_cannot_drop_cutoff_registration_or_cap(self):
        index = next(i for i, rule in enumerate(load_eligibility(CONDITIONS, REVIEW)['rules']) if rule['id'] == 'child-counting')
        for position in (0, 2, 3):
            self.reject(lambda r: r['rules'][index]['predicate']['requirements'].pop(position))

    def change_rule(self, record, ident, **fields):
        next(rule for rule in record['rules'] if rule['id'] == ident)['predicate'].update(fields)

    def test_asset_table_amounts_not_derived_rounding(self):
        self.reject(lambda r: self.change_rule(r, 'asset-limit-1', total_assets_won=379500000))
        self.reject(lambda r: self.change_rule(r, 'asset-limit-2plus', car_won=54504000))
        self.reject(lambda r: self.change_rule(r, 'asset-limit-1', children_band='0'))
        self.reject(lambda r: self.change_rule(r, 'asset-limit-0', car_won=True))

    def test_child_counting_dependency_required(self):
        self.reject(lambda r: self.change_rule(r, 'asset-limit-1', counting_rule_id='age-default'))
        self.reject(lambda r: self.change_rule(r, 'income-general-2-1', counting_rule_id='missing'))

    def test_income_limits_keep_group_size_and_supply(self):
        self.reject(lambda r: self.change_rule(r, 'income-general-3-0', percent=170))
        self.reject(lambda r: self.change_rule(r, 'income-general-3-0', household_size_max=4))
        self.reject(lambda r: self.change_rule(r, 'income-general-2-1', household_size_max=None))
        self.reject(lambda r: self.change_rule(r, 'income-general-2-1', supply='priority'))
        self.reject(lambda r: self.change_rule(r, 'income-general-2-1', applicant_group='newlyweds'))

    def test_manual_clause_dimension_bound_to_evidence(self):
        self.reject(lambda r: self.change_rule(r, 'household-spouse', dimension='income'))

    def test_category_or_cannot_be_flattened_or_drop_same_spouse_history(self):
        index = next(i for i, rule in enumerate(load_eligibility(CONDITIONS, REVIEW)['rules']) if rule['id'] == 'category-newlywed-alternatives')
        self.reject(lambda r: r['rules'][index]['predicate']['alternatives'].pop())
        self.reject(lambda r: r['rules'][index]['predicate']['alternatives'][0].pop())

    def test_priority_exemption_and_dual_earner_restriction_preserved(self):
        for ident in ('category-priority-demolition', 'income-dual-earner'):
            index = next(i for i, rule in enumerate(load_eligibility(CONDITIONS, REVIEW)['rules']) if rule['id'] == ident)
            self.reject(lambda r: r['rules'][index]['predicate']['requirements'].pop())

    def test_pdf_cli_success_and_changed_bytes(self):
        args = ['--conditions', str(CONDITIONS), '--review', str(REVIEW), '--pdf', str(PDF)]
        self.assertEqual(main(args), 0)
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / 'changed.pdf'
            changed.write_bytes(PDF.read_bytes() + b'changed')
            self.assertEqual(main(args[:-1] + [str(changed)]), 2)


if __name__ == '__main__':
    unittest.main()
