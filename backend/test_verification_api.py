import unittest
import json
from copy import deepcopy
from fastapi.testclient import TestClient

from backend.app import create_app, verification_result, GANGSEO_ID, GANGSEO_LIST_ID
from backend.document_review import load_review
from backend.test_api import ManualExecutor
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class VerificationApiTests(unittest.TestCase):
    def test_missing_document_never_promotes(self):
        r=verification_result(GANGSEO_LIST_ID,GANGSEO_ID,None)
        self.assertEqual(r['validated_rule_count'],93)
        self.assertFalse(r['live_document_bound'])
        self.assertIn('LIVE_DOCUMENT_BINDING_PENDING',[x['code'] for x in r['reasons']])
        self.assertFalse(r['eligible_for_promotion'])

    def test_matching_document_binds_only_local_review(self):
        source=load_review(ROOT/'backend/eligibility_reviews'/f'{GANGSEO_ID}.json')['source']
        document=dict(status='partial',reviewed=True,current_id=GANGSEO_ID,
                      original_id=source['original_id'],sha256=source['pdf_sha256'])
        r=verification_result(GANGSEO_LIST_ID,GANGSEO_ID,document)
        self.assertTrue(r['live_document_bound'])
        self.assertNotIn('LIVE_DOCUMENT_BINDING_PENDING',[x['code'] for x in r['reasons']])
        self.assertEqual(r['status'],'needs_review')
        self.assertFalse(r['eligible_for_promotion'])
        for field,value in [('sha256','0'*64),('original_id','wrong'),('reviewed',False),('status','failed')]:
            changed=deepcopy(document);changed[field]=value
            self.assertFalse(verification_result(GANGSEO_LIST_ID,GANGSEO_ID,changed)['live_document_bound'])

    def test_other_notice_has_no_reused_rules(self):
        r=verification_result('LH-2015122300020605-48-03','2015122300020605',None)
        self.assertEqual(r['validated_rule_count'],0)
        self.assertEqual(r['reasons'][0]['code'],'ARTIFACT_UNSUPPORTED')
        self.assertEqual(verification_result('LH-'+GANGSEO_ID+'-10-03',GANGSEO_ID,None)['validated_rule_count'],0)

    def test_endpoint_requires_owner_and_existing_notice(self):
        executor=ManualExecutor()
        fixture=json.loads((ROOT/'shared/contracts/list_review.json').read_text(encoding='utf-8'))
        notice=fixture['notices'][0]
        collection=fixture['collection']
        def collector(_):
            return {'error':'ORIGINAL_DOCUMENT_PENDING','retryable':False,
                    'checked_at':'2026-10-12T00:00:00Z','notices':[notice],
                    'excluded_notices':[],'collection':collection}
        c=TestClient(create_app(collector=collector,executor=executor))
        headers={'X-Session-Token':'a'*40,'Idempotency-Key':'verification'}
        ident=c.post('/v1/search-jobs',json={'region':'서울'},headers=headers).json()['id']
        executor.run()
        url=f"/v1/search-jobs/{ident}/notices/{notice['id']}/verification"
        self.assertEqual(c.get(url,headers={'X-Session-Token':'b'*40}).status_code,404)
        self.assertEqual(c.get(url.replace(notice['id'],'unknown'),headers=headers).status_code,404)
        response=c.get(url,headers=headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['status'],'needs_review')
        self.assertFalse(response.json()['live_document_bound'])
        self.assertEqual(response.json()['reasons'][0]['code'],'ARTIFACT_UNSUPPORTED')

    def test_endpoint_resolves_composite_list_id_to_review(self):
        executor=ManualExecutor()
        fixture=(ROOT/'shared/contracts/list_review.json').read_text(encoding='utf-8')
        fixture=json.loads(fixture.replace('LH-10001-10-03',GANGSEO_LIST_ID).replace('10001',GANGSEO_ID))
        notice=fixture['notices'][0]
        def collector(_):
            return {'error':'ORIGINAL_DOCUMENT_PENDING','retryable':False,
                    'checked_at':'2026-10-12T00:00:00Z','notices':[notice],
                    'excluded_notices':[],'collection':fixture['collection']}
        c=TestClient(create_app(collector=collector,executor=executor))
        headers={'X-Session-Token':'a'*40,'Idempotency-Key':'gangseo'}
        ident=c.post('/v1/search-jobs',json={'region':'서울'},headers=headers).json()['id']
        executor.run()
        response=c.get(f'/v1/search-jobs/{ident}/notices/{GANGSEO_LIST_ID}/verification',headers=headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['validated_rule_count'],93)
        self.assertFalse(response.json()['eligible_for_promotion'])
