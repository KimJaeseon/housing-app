"""Source-bound, partial eligibility rules; never evaluate an applicant."""
import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from backend.document_review import ROOT, load_review, validate_pdf

SCHEMA = json.loads((ROOT / 'shared/contracts/eligibility-conditions.schema.json').read_text(encoding='utf-8'))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def predicate_text(predicate):
    """Canonical reviewed wording keeps every normalized field evidence-bound."""
    kind = predicate['kind']
    if kind == 'reviewed_all_of':
        return f"적용 차원 {predicate['dimension']}; " + '; '.join(predicate['requirements'])
    if kind == 'reviewed_any_of':
        return f"적용 차원 {predicate['dimension']}; " + ' [또는] '.join('(' + '; '.join(terms) + ')' for terms in predicate['alternatives'])
    if kind == 'resource_scope':
        resource = {'income': '소득', 'assets': '자산'}[predicate['resource']]
        scope = {'household': '세대구성원 전체', 'applicant': '신청자 본인', 'future_household': '혼인으로 구성될 세대 전체'}[predicate['scope']]
        return f'{resource} 검증 대상: {scope}; ' + '; '.join(predicate['requirements'])
    if kind == 'housing_exception':
        text = '주택소유 인정 예외; ' + '; '.join(predicate['requirements'])
        if predicate['alternatives']:
            text += '; 추가 대안 중 하나: ' + ' [또는] '.join('(' + '; '.join(terms) + ')' for terms in predicate['alternatives'])
        return text + '; 이 예외 자체가 자산가액 면제를 의미하지 않음'
    if kind == 'asset_limits':
        return (f"출산 가산 인정 자녀 구간 {predicate['children_band']}; "
                f"총자산 {predicate['total_assets_won']:,}원 이하; 자동차 {predicate['car_won']:,}원 이하; "
                '출산자녀수 인정 규칙과 자산 검증 대상·산정방법을 함께 확인')
    if kind in ('income_limit', 'family_income_limit'):
        size = str(predicate['household_size_min']) if predicate['household_size_max'] == predicate['household_size_min'] else f"{predicate['household_size_min']}인 이상"
        group = '일반공급 신혼부부·한부모가족 제외 계층'
        if kind == 'family_income_limit':
            group = {'single_parent_under6': '일반공급 6세 이하 자녀 한부모가족',
                     'newlywed_single_parent_other': '일반공급 신혼부부·한부모가족 그 외'}[predicate['applicant_group']]
            group += '; 신혼 맞벌이 우대 ' + ('적용' if predicate['dual_earner_bonus'] else '미적용')
        return (f"{group}; 세대원수 {size}; 출산 가산 인정 자녀 구간 {predicate['children_band']}; "
                f"기준 중위소득 {predicate['percent']}% 이하; 출산자녀수 인정 규칙과 소득 검증 대상·산정방법을 함께 확인")
    raise ValueError('predicate has no canonical wording')


def load_eligibility(path, review_path):
    record = json.loads(Path(path).read_text(encoding='utf-8'))
    if list(VALIDATOR.iter_errors(record)):
        raise ValueError('invalid eligibility schema')
    review = load_review(review_path)
    if record['official_id'] != review['official_id'] or record['pdf_sha256'] != review['source']['pdf_sha256']:
        raise ValueError('eligibility source mismatch')
    facts = {fact['id']: fact for fact in review['facts']}
    date_fact = facts.get(record['as_of']['fact_id'])
    if not date_fact or date_fact['category'] != 'schedule' or record['as_of']['date'].replace('-', '.') not in date_fact['value']:
        raise ValueError('eligibility date evidence mismatch')
    rules = {rule['id']: rule for rule in record['rules']}
    if len(rules) != len(record['rules']):
        raise ValueError('duplicate eligibility rule')
    referenced = [rule['fact_id'] for rule in record['rules']]
    if len(referenced) != len(set(referenced)) or set(referenced) != {fact['id'] for fact in review['facts'] if fact['category'] == 'eligibility'}:
        raise ValueError('eligibility review coverage mismatch')
    for rule in record['rules']:
        fact = facts.get(rule['fact_id'])
        if not fact or fact['category'] != 'eligibility' or rule['applies_to'] != fact['label'] or rule['source_text'] != fact['value']:
            raise ValueError('eligibility evidence mismatch')
        predicate = rule['predicate']
        kind = predicate['kind']
        if kind == 'age_minimum':
            if not re.search(r'(?<!\d)' + str(predicate['years']) + r'세 미만', fact['value']):
                raise ValueError('age evidence mismatch')
        elif kind == 'housing_scope':
            phrase = {'household': '세대구성원 전원', 'applicant': '신청자 본인',
                      'future_household': '혼인으로 구성될 세대'}[predicate['scope']]
            if phrase not in fact['value']:
                raise ValueError('housing scope evidence mismatch')
        elif kind == 'manual_exception':
            if '; '.join(predicate['requirements']) != fact['value']:
                raise ValueError('exception requirements absent from evidence')
        elif predicate_text(predicate) != fact['value']:
            raise ValueError('normalized eligibility evidence mismatch')
        if kind in ('asset_limits', 'income_limit', 'family_income_limit'):
            counting = rules.get(predicate['counting_rule_id'])
            if not counting or counting['predicate']['kind'] != 'reviewed_all_of' or counting['predicate']['dimension'] != 'child_counting':
                raise ValueError('child counting evidence missing')
        if kind in ('income_limit', 'family_income_limit') and predicate['household_size_max'] not in (None, predicate['household_size_min']):
            raise ValueError('unsupported household size interval')
        if kind == 'family_income_limit':
            bonus = rules.get(predicate['bonus_rule_id'])
            if not bonus or bonus['id'] != 'income-dual-earner' or bonus['predicate']['kind'] != 'reviewed_all_of' or bonus['predicate']['dimension'] != 'income':
                raise ValueError('family income bonus evidence missing')
            if predicate['applicant_group'] == 'single_parent_under6' and predicate['dual_earner_bonus']:
                raise ValueError('single parent dual earner bonus forbidden')
        if kind == 'resource_scope':
            parent = rules.get(rule['exception_of'])
            if rule['exception_of'] is not None and (not parent or parent['predicate']['kind'] != kind or parent['predicate']['resource'] != predicate['resource']):
                raise ValueError('resource scope parent mismatch')
        parent_id = rule['exception_of']
        needs_parent = kind in ('manual_exception', 'housing_exception') or (kind in ('housing_scope', 'resource_scope') and predicate['scope'] != 'household')
        if needs_parent != (parent_id is not None):
            raise ValueError('eligibility root or exception mismatch')
        if parent_id is not None:
            parent = rules.get(parent_id)
            if not parent or parent_id == rule['id'] or parent['exception_of'] is not None:
                raise ValueError('invalid eligibility exception relation')
            expected_parent = {'manual_exception': 'age_minimum', 'housing_exception': 'housing_scope'}.get(kind, kind)
            if parent['predicate']['kind'] != expected_parent or (kind in ('housing_scope', 'resource_scope', 'housing_exception') and parent['predicate']['scope'] != 'household'):
                raise ValueError('eligibility exception category mismatch')
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validate partial eligibility rules against a reviewed local PDF.')
    for name in ('conditions', 'review', 'pdf'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    try:
        validate_pdf(args.review, args.pdf)
        record = load_eligibility(args.conditions, args.review)
        print(json.dumps({'status': 'valid_partial', 'official_id': record['official_id'],
                          'rules': len(record['rules']), 'applicant_evaluation': False,
                          'unreviewed_dimensions': record['unreviewed_dimensions']}))
        return 0
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({'status': 'invalid_eligibility'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
