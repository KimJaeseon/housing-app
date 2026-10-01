"""Validate manually normalized conditions against one reviewed PDF profile.

These are reviewed source data, never applicant eligibility or live-open status.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from backend.document_review import load_review, validate_pdf


def _instant(value):
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError('condition timezone missing')
    return instant


def load_conditions(path, review_path):
    record = json.loads(Path(path).read_text(encoding='utf-8'))
    profile = load_review(review_path)
    if set(record) != {'official_id', 'pdf_sha256', 'windows', 'rents'}:
        raise ValueError('condition fields invalid')
    if record['official_id'] != profile['official_id'] or record['pdf_sha256'] != profile['source']['pdf_sha256']:
        raise ValueError('condition source mismatch')
    facts = {fact['id']: fact for fact in profile['facts']}
    if not isinstance(record['windows'], list) or not isinstance(record['rents'], list):
        raise ValueError('condition collections invalid')
    seen = set()
    for window in record['windows']:
        if set(window) != {'id', 'audience', 'method', 'start', 'end', 'timezone', 'fact_id'}:
            raise ValueError('window fields invalid')
        if window['id'] in seen or window['timezone'] != 'Asia/Seoul' or window['method'] not in ('limited_onsite_other_unreviewed', 'onsite_only'):
            raise ValueError('window identity invalid')
        seen.add(window['id'])
        fact = facts.get(window['fact_id'])
        if not fact or fact['category'] != 'schedule' or window['audience'] not in fact['label']:
            raise ValueError('window evidence mismatch')
        start, end = _instant(window['start']), _instant(window['end'])
        if start >= end or start.utcoffset().total_seconds() != 32400 or end.utcoffset().total_seconds() != 32400:
            raise ValueError('window interval invalid')
        if start.strftime('%Y.%m.%d %H:%M') not in fact['value']:
            raise ValueError('window start absent from evidence')
        end_text = (end.strftime('%Y.%m.%d %H:%M') if start.date() != end.date()
                    else '~ ' + end.strftime('%H:%M'))
        if end_text not in fact['value']:
            raise ValueError('window end absent from evidence')
        if '현장' not in fact['value']:
            raise ValueError('window method absent from evidence')
    rents_by_id = {}
    combinations = set()
    basic_fields = {'id', 'unit', 'income_band', 'condition', 'deposit_unit', 'deposit_raw', 'deposit_won', 'monthly_rent_won', 'fact_id'}
    for rent in record['rents']:
        condition = rent.get('condition')
        required = basic_fields if condition == 'basic' else basic_fields | {'base_rent_id', 'conversion_delta_won'}
        if set(rent) != required:
            raise ValueError('rent fields invalid')
        if rent['id'] in seen or condition not in ('basic', 'max_increase', 'max_decrease') or rent['deposit_unit'] != '원':
            raise ValueError('rent identity invalid')
        seen.add(rent['id'])
        combination = (rent['unit'], rent['income_band'], condition)
        if combination in combinations:
            raise ValueError('duplicate rent condition')
        combinations.add(combination)
        rents_by_id[rent['id']] = rent
        fact = facts.get(rent['fact_id'])
        if not fact or fact['category'] != 'rent' or rent['unit'] not in fact['label'] or rent['income_band'] not in fact['label']:
            raise ValueError('rent evidence mismatch')
        label_fragment = {'basic': '기본', 'max_increase': '최대 증액', 'max_decrease': '최대 감액'}[condition]
        if label_fragment not in fact['label']:
            raise ValueError('rent condition evidence mismatch')
        for key in ('deposit_raw', 'deposit_won', 'monthly_rent_won'):
            if type(rent[key]) is not int or rent[key] < 0:
                raise ValueError('rent amount invalid')
        if rent['deposit_raw'] != rent['deposit_won']:
            raise ValueError('rent conversion mismatch')
        if f"{rent['deposit_won']:,}원" not in fact['value'] or f"{rent['monthly_rent_won']:,}원" not in fact['value']:
            raise ValueError('rent amount absent from evidence')
        if condition != 'basic':
            delta = rent['conversion_delta_won']
            if type(delta) is not int or (condition == 'max_increase' and delta <= 0) or (condition == 'max_decrease' and delta >= 0):
                raise ValueError('rent conversion direction invalid')
            verb = '증액' if delta > 0 else '감액'
            if f'{abs(delta):,}원 {verb}' not in fact['value']:
                raise ValueError('rent conversion absent from evidence')
    for rent in record['rents']:
        if rent['condition'] == 'basic':
            continue
        base = rents_by_id.get(rent['base_rent_id'])
        if not base or base['condition'] != 'basic' or (base['unit'], base['income_band']) != (rent['unit'], rent['income_band']):
            raise ValueError('rent base mismatch')
        if base['deposit_won'] + rent['conversion_delta_won'] != rent['deposit_won']:
            raise ValueError('rent conversion amount mismatch')
        if (rent['conversion_delta_won'] > 0 and rent['monthly_rent_won'] >= base['monthly_rent_won']) or (
                rent['conversion_delta_won'] < 0 and rent['monthly_rent_won'] <= base['monthly_rent_won']):
            raise ValueError('rent monthly direction mismatch')
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validate reviewed windows and rent amounts against one local PDF.')
    parser.add_argument('--conditions', required=True)
    parser.add_argument('--review', required=True)
    parser.add_argument('--pdf', required=True)
    args = parser.parse_args(argv)
    try:
        validate_pdf(args.review, args.pdf)
        record = load_conditions(args.conditions, args.review)
        print(json.dumps({'status': 'valid', 'official_id': record['official_id'],
                          'windows': len(record['windows']), 'rents': len(record['rents'])}))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        print(json.dumps({'status': 'invalid_conditions'}))
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
