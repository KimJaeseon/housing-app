"""Offline contract reference rules; no network, credentials or real eligibility decisions."""
from datetime import datetime

def instant(value):
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.utcoffset() is None: raise ValueError('timezone required')
    return d

def recruitment(windows, now, cancelled=False):
    if cancelled: return 'cancelled'
    now=instant(now); states=[]
    for w in windows:
        if w['kind']!='application': continue
        start=instant(w['start']) if w['start'] else None
        end=instant(w['end']) if w['end'] else None
        if start and end and end<=start: states.append('unknown')
        elif end and now>=end: states.append('closed')
        elif start and now<start: states.append('scheduled')
        elif start and end: states.append('open')
        else: states.append('unknown')
    for state in ['open','unknown','scheduled']:
        if state in states: return state
    return 'closed' if states else 'unknown'

def placement(scope, status, verified, revision_resolved, same_job):
    if scope=='out_of_scope' or status in ('closed','cancelled'): return 'excluded'
    if scope!='in_scope' or not verified or not revision_resolved or not same_job or status=='unknown': return 'needs_review'
    return 'default'

def job_status(sources,cancelled=False):
    if cancelled:return 'cancelled'
    states=[s['status'] for s in sources]
    if not states or all(s=='unsupported' for s in states):return 'failed'
    if any(s in ('queued','researching','verifying') for s in states):return 'researching'
    if all(s=='completed' for s in states):return 'completed'
    return 'partial' if 'completed' in states else 'failed'

def result_message(job):
    if job['status']=='cancelled':return 'cancelled'
    if job['status'] in ('queued','researching','verifying'):return 'in_progress'
    if job['status']=='failed':return 'failed'
    if job['status']=='partial':return 'partial_results' if job['notices'] else 'empty_partial'
    if job['notices']:return 'results'
    return 'empty_supported_scope' if job['uncovered_source_ids'] else 'empty_completed'

def personalization(enabled,checks):
    if not enabled:return 'not_requested'
    if not checks or 'unknown' in checks:return 'needs_review'
    return 'mismatch' if 'mismatch' in checks else 'candidate'
