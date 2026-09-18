import json, unittest
from pathlib import Path
from reference_rules import recruitment, placement, job_status, result_message, personalization
P=Path(__file__).resolve().parents[2]/'shared/contracts'
NOW='2026-09-10T10:00:00+09:00'
def w(start='2026-09-10T09:00:00+09:00',end='2026-09-10T11:00:00+09:00',kind='application'):
    return dict(start=start,end=end,kind=kind)
class ContractCases(unittest.TestCase):
    def test_start_inclusive(self):self.assertEqual(recruitment([w(start=NOW)],NOW),'open')
    def test_end_exclusive(self):self.assertEqual(recruitment([w(end=NOW)],NOW),'closed')
    def test_missing_end(self):self.assertEqual(recruitment([w(end=None)],NOW),'unknown')
    def test_missing_start(self):self.assertEqual(recruitment([w(start=None)],NOW),'unknown')
    def test_no_windows(self):self.assertEqual(recruitment([],NOW),'unknown')
    def test_reversed_window(self):self.assertEqual(recruitment([w(start='2026-09-11T09:00:00+09:00')],NOW),'unknown')
    def test_cancelled(self):self.assertEqual(recruitment([w()],NOW,True),'cancelled')
    def test_multiple_rounds(self):self.assertEqual(recruitment([w(end=NOW),w(start='2026-09-11T09:00:00+09:00',end='2026-09-11T11:00:00+09:00')],NOW),'scheduled')
    def test_documents_are_not_application(self):self.assertEqual(recruitment([w(end=NOW),w(kind='documents')],NOW),'closed')
    def test_timezone_equivalence(self):self.assertEqual(recruitment([w()], '2026-09-10T01:00:00+00:00'),'open')
    def test_naive_rejected(self):
        with self.assertRaises(ValueError):recruitment([w()], '2026-09-10T10:00:00')
    def test_correction_unresolved(self):self.assertEqual(placement('in_scope','open',True,False,True),'needs_review')
    def test_stale_result(self):self.assertEqual(placement('in_scope','open',True,True,False),'needs_review')
    def test_private_excluded(self):self.assertEqual(placement('out_of_scope','open',True,True,True),'excluded')
    def test_closed_excluded_even_unverified(self):self.assertEqual(placement('in_scope','closed',False,False,True),'excluded')
    def test_verified_open(self):self.assertEqual(placement('in_scope','open',True,True,True),'default')
    def test_attachment_missing(self):self.assertEqual(placement('in_scope','open',False,True,True),'needs_review')
    def test_partial(self):self.assertEqual(job_status([{'status':'completed'},{'status':'failed'}]),'partial')
    def test_all_failed(self):self.assertEqual(job_status([{'status':'failed'}]),'failed')
    def test_no_sources(self):self.assertEqual(job_status([]),'failed')
    def test_cancelled_cannot_be_completed(self):self.assertEqual(job_status([{'status':'completed'}],True),'cancelled')
    def test_missing_condition(self):self.assertEqual(personalization(True,['match','unknown']),'needs_review')
    def test_no_conditions(self):self.assertEqual(personalization(True,[]),'needs_review')
    def test_personalization_optional(self):self.assertEqual(personalization(False,[]),'not_requested')
    def test_examples(self):
        for name,expected in [('empty_completed','empty_completed'),('empty_partial','empty_partial'),('cancelled','cancelled'),('failed','failed'),('researching','in_progress')]:
            j=json.loads((P/(name+'.json')).read_text(encoding='utf-8'));self.assertEqual(result_message(j),expected)
    def test_uncovered_scope(self):
        j=json.loads((P/'empty_completed.json').read_text(encoding='utf-8'));j['uncovered_source_ids']=['unconnected'];self.assertEqual(result_message(j),'empty_supported_scope')
if __name__=='__main__':unittest.main(verbosity=2)
