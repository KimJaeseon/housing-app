"""Validate reviewed-official-document profiles without contacting external services."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'shared/contracts/document-review.schema.json').read_text(encoding='utf-8'))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def load_review(path):
    """Return a validated profile. The caller decides whether it matches live metadata."""
    profile = json.loads(Path(path).read_text(encoding='utf-8'))
    errors = list(VALIDATOR.iter_errors(profile))
    if errors:
        raise ValueError('invalid review schema')
    source = profile['source']
    if profile['official_id'] != source['current_id'] or profile['original_id'] != source['original_id']:
        raise ValueError('review identity mismatch')
    fact_ids = [fact['id'] for fact in profile['facts']]
    if len(fact_ids) != len(set(fact_ids)):
        raise ValueError('duplicate review fact')
    for fact in profile['facts']:
        if fact['page'] > source['page_count']:
            raise ValueError('review page outside PDF')
        if not re.search(r'\bp\.?\s*' + str(fact['page']) + r'\b', fact['source_locator'], re.I):
            raise ValueError('review locator page mismatch')
    return profile


def validate_pdf(profile_path, pdf_path):
    """Validate profile structure and bind it to one local PDF without printing contents."""
    profile = load_review(profile_path)
    digest = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
    if digest != profile['source']['pdf_sha256']:
        raise ValueError('review PDF digest mismatch')
    return {'official_id': profile['official_id'], 'facts': len(profile['facts']), 'reviewed_at': profile['review']['reviewed_at']}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validate a reviewed LH notice profile against a local PDF.')
    parser.add_argument('--review', required=True)
    parser.add_argument('--pdf', required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(validate_pdf(args.review, args.pdf), ensure_ascii=False))
    except (OSError, ValueError, json.JSONDecodeError):
        print(json.dumps({'status': 'invalid_review'}, ensure_ascii=False))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
