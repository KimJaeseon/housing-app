"""Local readiness assessment; never promotes a notice or evaluates an applicant."""
import argparse
import json

from backend.document_review import validate_pdf
from backend.eligibility_conditions import load_eligibility
from backend.separate_notice import load_snapshot


def assess(conditions_path, review_path, pdf_path, separate_notice_path=None, artifact_dir=None):
    """Validate actual artifacts before reporting partial evidence coverage.

    No caller-supplied completion flags are accepted. External source adapters and
    full coverage validation must be implemented before promotion is possible.
    """
    try:
        validate_pdf(review_path, pdf_path)
        record = load_eligibility(conditions_path, review_path)
    except (OSError, ValueError, TypeError, KeyError):
        return {'status': 'needs_review', 'eligible_for_promotion': False,
                'applicant_evaluation': False, 'official_id': None,
                'validated_rule_count': 0,
                'reasons': [{'code': 'ARTIFACT_INVALID', 'dimension': None}]}
    reasons = [{'code': 'DIMENSION_INCOMPLETE', 'dimension': dimension}
               for dimension in record['unreviewed_dimensions']]
    reasons.extend({'code': code, 'dimension': None} for code in (
        'PARTIAL_COVERAGE', 'EXTERNAL_LEGAL_EVIDENCE_PENDING',
        'SEPARATE_NOTICES_PENDING', 'SOURCE_CONFLICT_REVIEW_PENDING',
        'LIVE_DOCUMENT_BINDING_PENDING', 'PRODUCTION_VERIFIER_PENDING'))
    result = {'status': 'needs_review', 'eligible_for_promotion': False,
            'applicant_evaluation': False, 'official_id': record['official_id'],
            'validated_rule_count': len(record['rules']), 'reasons': reasons}
    if separate_notice_path is not None:
        try:
            if artifact_dir is None:
                raise ValueError('missing artifact directory')
            snapshot = load_snapshot(separate_notice_path, artifact_dir, record['official_id'])
            result['separate_notice'] = {'status': 'valid_candidate',
                                         'bulletin_id': snapshot['bulletin_id'],
                                         'attachment_count': len(snapshot['attachments'])}
            reasons.append({'code': 'SEPARATE_NOTICE_RELATION_UNCONFIRMED', 'dimension': None})
        except (OSError, ValueError, TypeError, KeyError):
            result['separate_notice'] = {'status': 'invalid', 'bulletin_id': None, 'attachment_count': 0}
            reasons.append({'code': 'SEPARATE_NOTICE_ARTIFACT_INVALID', 'dimension': None})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Assess local evidence readiness without promotion.')
    for name in ('conditions', 'review', 'pdf'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--separate-notice')
    parser.add_argument('--artifact-dir')
    args = parser.parse_args(argv)
    if bool(args.separate_notice) != bool(args.artifact_dir):
        parser.error('--separate-notice and --artifact-dir must be provided together')
    result = assess(args.conditions, args.review, args.pdf, args.separate_notice, args.artifact_dir)
    print(json.dumps(result, ensure_ascii=False))
    # Exit 1 means valid but incomplete; 2 means invalid input. Never exit 0 yet.
    return 2 if any(r['code'] in ('ARTIFACT_INVALID', 'SEPARATE_NOTICE_ARTIFACT_INVALID')
                    for r in result['reasons']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
