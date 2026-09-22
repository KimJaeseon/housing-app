import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
SCHEMA=json.loads((Path(__file__).resolve().parents[1]/'shared/contracts/search-result.schema.json').read_text(encoding='utf-8-sig'))
Draft202012Validator.check_schema(SCHEMA)
validator=Draft202012Validator(SCHEMA,format_checker=FormatChecker())

def validate_result(data):
    errors=[f'schema:{list(e.absolute_path)}' for e in validator.iter_errors(data)]
    if errors: raise ValueError(';'.join(errors))
    ids=[x['id'] for x in data['sources']]
    if len(ids)!=len(set(ids)):errors.append('duplicate source')
    if data['status']=='completed' and (not ids or any(x['status']!='completed' for x in data['sources'])):errors.append('false completion')
    if data['status'] in ('completed','partial','failed','cancelled') and data['finished_at'] is None:errors.append('missing finish time')
    notice_ids=set()
    for n in data['notices']:
        if n['recruitment_status'] in ('closed','cancelled') or n['scope']=='out_of_scope':errors.append('excluded notice in active results')
    for n in data.get('excluded_notices',[]):
        if n['recruitment_status'] not in ('closed','cancelled') and n['scope']!='out_of_scope':errors.append('active notice in exclusions')
    for n in data['notices']+data.get('excluded_notices',[]):
        if n['checked_in_job_id']!=data['id']:errors.append('stale notice')
        if n['id'] in notice_ids:errors.append('duplicate notice')
        notice_ids.add(n['id'])
        if n['source_id'] not in ids:errors.append('unknown source')
        evidence={x['id'] for x in n['evidence']};versions={x['id'] for x in n['versions']}
        if len(evidence)!=len(n['evidence']) or len(versions)!=len(n['versions']):errors.append('duplicate evidence/version')
        for e in n['evidence']:
            if e['document_version_id'] not in versions:errors.append('dangling version')
        for v in n['versions']:
            if not set(v['related_version_ids'])<=versions:errors.append('dangling related version')
        if n['current_version_id'] is not None and n['current_version_id'] not in versions:errors.append('unknown current version')
        def walk(x):
            if isinstance(x,dict):
                for k,val in x.items():
                    if k.endswith('evidence_ids') and not set(val)<=evidence:errors.append('dangling evidence')
                    walk(val)
                if 'state' in x and 'value' in x:
                    if x['state']=='known' and (x['value'] is None or not x['evidence_ids']):errors.append('known without value/evidence')
                    if x['state']=='unknown' and (x['value'] is not None or not x['reason']):errors.append('invalid unknown')
                    if x['state'] in ('not_stated','announced_later') and not x['evidence_ids']:errors.append('missing statement evidence')
            elif isinstance(x,list):
                for item in x:walk(item)
        walk(n)
        # No production verifier is connected. Never accept a fabricated verified result.
        if n['verification_status']=='verified':errors.append('verification adapter not implemented')
    if errors:raise ValueError(';'.join(errors))
    return data


def validate_supply(data):
    schema={'$schema':SCHEMA.get('$schema'),'$defs':SCHEMA['$defs'],'$ref':'#/$defs/supply_result'}
    if list(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(data)):
        raise ValueError('invalid supply schema')
    evidence={e['id'] for e in data['evidence']};versions={v['id'] for v in data['versions']}
    if len(evidence)!=len(data['evidence']) or len(versions)!=len(data['versions']):raise ValueError('duplicate supply evidence')
    if any(e['document_version_id'] not in versions for e in data['evidence']):raise ValueError('supply version missing')
    if data['status']!='researching' and not data['checked_at']:raise ValueError('supply check time missing')
    if data['status']=='available' and not data['units']:raise ValueError('supply units missing')
    if data['status'] in ('empty','failed','researching') and data['units']:raise ValueError('unexpected supply units')
    if (data['status']=='failed')!=(data['error_code'] is not None):raise ValueError('invalid supply error state')
    for unit in data['units']:
        facts=[v for v in unit.values() if isinstance(v,dict) and 'state' in v]+unit['eligibility']
        for fact in facts:
            if not set(fact['evidence_ids'])<=evidence:raise ValueError('supply evidence missing')
            if fact['state']=='known' and (fact['value'] is None or not fact['evidence_ids']):raise ValueError('unsupported known supply value')
            if fact['state']=='unknown' and (fact['value'] is not None or not fact['reason']):raise ValueError('invalid unknown supply value')
    return data


def validate_document(data):
    schema={'$defs':SCHEMA['$defs'],'$ref':'#/$defs/document_result'}
    if list(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(data)):raise ValueError('invalid document schema')
    if (data['status']=='failed')!=(data['error_code'] is not None):raise ValueError('invalid document error')
    if data['status']!='researching' and not data['checked_at']:raise ValueError('missing document check time')
    if data['status']!='partial' and (data['reviewed'] or data['facts']):raise ValueError('unexpected document facts')
    if bool(data['facts'])!=data['reviewed']:raise ValueError('unreviewed document facts')
    if data['status']=='partial':
        if not all(data[k] for k in ('source_url','pdf_url','sha256','filename','current_id')):raise ValueError('missing document provenance')
        from urllib.parse import urlsplit,parse_qs
        import re
        url=urlsplit(data['source_url'])
        if url.scheme!='https' or url.netloc!='apply.lh.or.kr' or url.path!='/lhapply/apply/wt/wrtanc/selectWrtancInfo.do' or url.fragment:raise ValueError('invalid document source')
        if not re.fullmatch(r'https://apply\.lh\.or\.kr/lhapply/lhFile\.do\?fileid=[0-9]{1,16}',data['pdf_url']):raise ValueError('invalid PDF source')
        if data['reviewed'] and parse_qs(url.query).get('panId')!=[data['current_id']]:raise ValueError('superseded document')
    return data
