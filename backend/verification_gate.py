"""Local readiness assessment; never promotes a notice or evaluates an applicant."""
import argparse
import json

from backend.document_review import validate_pdf
from backend.eligibility_conditions import load_eligibility
from backend.external_legal import load_external_legal
from backend.separate_notice import load_snapshot
from backend.reviewed_tables import load_reviewed_tables


def assess(conditions_path, review_path, pdf_path, separate_notice_path=None, artifact_dir=None,
           reviewed_tables_path=None, external_legal_path=None):
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
    if reviewed_tables_path is not None:
        try:
            tables = load_reviewed_tables(reviewed_tables_path, pdf_path, review_path)
            result['reviewed_tables'] = {'status': 'valid_partial',
                                         'income_amount_count': sum(len(row) for row in tables['income_amounts']['amounts_won']),
                                         'renewal_page_count': len(tables['renewal']['pages'])}
        except (OSError, ValueError, TypeError, KeyError):
            result['reviewed_tables'] = {'status': 'invalid', 'income_amount_count': 0,
                                         'renewal_page_count': 0}
            reasons.append({'code': 'REVIEWED_TABLES_ARTIFACT_INVALID', 'dimension': None})
    if external_legal_path is not None:
        try:
            if artifact_dir is None:
                raise ValueError('missing artifact directory')
            legal = load_external_legal(external_legal_path, artifact_dir, record['official_id'])
            result['external_legal'] = {'status': 'valid_partial',
                                        'source_count': len(legal['sources']),
                                        'aligned_check_count': sum(value == 'aligned' for value in legal['checks'].values()),
                                        'unresolved_check_count': sum(value == 'unresolved' for value in legal['checks'].values())}
        except (OSError, ValueError, TypeError, KeyError):
            result['external_legal'] = {'status': 'invalid', 'source_count': 0,
                                        'aligned_check_count': 0, 'unresolved_check_count': 0}
            reasons.append({'code': 'EXTERNAL_LEGAL_ARTIFACT_INVALID', 'dimension': None})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Assess local evidence readiness without promotion.')
    for name in ('conditions', 'review', 'pdf'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--separate-notice')
    parser.add_argument('--artifact-dir')
    parser.add_argument('--reviewed-tables')
    parser.add_argument('--external-legal')
    args = parser.parse_args(argv)
    if bool(args.artifact_dir) != bool(args.separate_notice or args.external_legal):
        parser.error('--artifact-dir must be provided with --separate-notice or --external-legal')
    result = assess(args.conditions, args.review, args.pdf, args.separate_notice, args.artifact_dir,
                    args.reviewed_tables, args.external_legal)
    print(json.dumps(result, ensure_ascii=False))
    # Exit 1 means valid but incomplete; 2 means invalid input. Never exit 0 yet.
    return 2 if any(r['code'] in ('ARTIFACT_INVALID', 'SEPARATE_NOTICE_ARTIFACT_INVALID',
                                 'REVIEWED_TABLES_ARTIFACT_INVALID', 'EXTERNAL_LEGAL_ARTIFACT_INVALID')
                    for r in result['reasons']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
