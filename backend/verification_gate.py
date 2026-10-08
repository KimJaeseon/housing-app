"""Local readiness assessment; never promotes a notice or evaluates an applicant."""
import argparse
import json

from backend.document_review import validate_pdf
from backend.eligibility_conditions import load_eligibility


def assess(conditions_path, review_path, pdf_path):
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
    return {'status': 'needs_review', 'eligible_for_promotion': False,
            'applicant_evaluation': False, 'official_id': record['official_id'],
            'validated_rule_count': len(record['rules']), 'reasons': reasons}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Assess local evidence readiness without promotion.')
    for name in ('conditions', 'review', 'pdf'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    result = assess(args.conditions, args.review, args.pdf)
    print(json.dumps(result, ensure_ascii=False))
    # Exit 1 means valid but incomplete; 2 means invalid input. Never exit 0 yet.
    return 2 if result['reasons'][0]['code'] == 'ARTIFACT_INVALID' else 1


if __name__ == '__main__':
    raise SystemExit(main())
