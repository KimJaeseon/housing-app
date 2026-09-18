import json
from pathlib import Path
P=Path(__file__).resolve().parents[2]/'shared/contracts'
s={'type':'string','minLength':1}
def enum(*x): return {'enum':list(x)}
def arr(x): return {'type':'array','items':x}
def obj(props,required=None): return {'type':'object','properties':props,'required':list(props) if required is None else required,'additionalProperties':False}
def ref(n): return {'$ref':'#/$defs/'+n}
ts={'type':'string','format':'date-time'}
nullable_ts={'anyOf':[ts,{'type':'null'}]}
D={}
D['evidence']=obj({'id':s,'url':{'type':'string','format':'uri'},'document_version_id':s,'locator':s,'checked_at':ts,'method':enum('http','api','manual','synthetic')})
D['fact']=obj({'state':enum('known','unknown','not_stated','not_applicable','announced_later'),'value':{'type':['string','number','boolean','null']},'unit':{'type':['string','null']},'reason':{'type':['string','null']},'evidence_ids':arr(s)})
D['window']=obj({'id':s,'audience':s,'kind':enum('application','documents','results'),'start':nullable_ts,'end':nullable_ts,'raw_schedule':s,'evidence_ids':arr(s)})
D['version']=obj({'id':s,'kind':enum('original','correction','cancellation','repost'),'related_version_ids':arr(s),'changed_fields':arr(s),'relationship_evidence_ids':arr(s),'checked_at':ts})
D['unit']=obj({'id':s,'label':s,'address':ref('fact'),'deposit':ref('fact'),'monthly_rent':ref('fact'),'sale_price':ref('fact'),'eligibility':arr(ref('fact')),'windows':arr(ref('window'))})
D['notice']=obj({'id':s,'source_id':s,'official_id':{'type':['string','null']},'title':s,'housing_type':s,'region_ids':arr(s),'scope':enum('in_scope','out_of_scope','unknown'),'versions':arr(ref('version')),'current_version_id':{'type':['string','null']},'revision_resolved':{'type':'boolean'},'checked_in_job_id':s,'checked_at':ts,'recruitment_status':enum('scheduled','open','closed','cancelled','unknown'),'verification_status':enum('verified','needs_review'),'review_reasons':arr(s),'evidence':arr(ref('evidence')),'units':arr(ref('unit'))})
D['source']=obj({'id':s,'status':enum('queued','researching','verifying','completed','failed','cancelled','unsupported'),'checked_at':nullable_ts,'error_code':{'type':['string','null']},'retryable':{'type':'boolean'}})
D['job']=obj({'schema_version':{'const':'0.1.0'},'id':s,'revision':{'type':'integer','minimum':1},'status':enum('queued','researching','verifying','completed','partial','failed','cancelled'),'region':obj({'id':s,'label':s}),'requested_at':ts,'finished_at':nullable_ts,'sources':arr(ref('source')),'uncovered_source_ids':arr(s),'notices':arr(ref('notice')),'personalization':obj({'enabled':{'type':'boolean'},'result':enum('not_requested','candidate','mismatch','needs_review'),'unresolved_conditions':arr(s)})})
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:housing:search-result:0.1.0','title':'Search result contract (draft)','$ref':'#/$defs/job','$defs':D}
(P/'search-result.schema.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf-8')
job={'schema_version':'0.1.0','id':'synthetic-job-1','revision':1,'status':'completed','region':{'id':'test-seoul','label':'서울특별시 (합성 식별자)'},'requested_at':'2026-09-10T09:00:00+09:00','finished_at':'2026-09-10T09:00:05+09:00','sources':[{'id':'synthetic-source','status':'completed','checked_at':'2026-09-10T09:00:04+09:00','error_code':None,'retryable':False}],'uncovered_source_ids':[],'notices':[],'personalization':{'enabled':False,'result':'not_requested','unresolved_conditions':[]}}
examples={'empty_completed':job}
from copy import deepcopy
j=deepcopy(job);j['status']='partial';j['sources'].append({'id':'synthetic-failed','status':'failed','checked_at':None,'error_code':'ATTACHMENT_FETCH_FAILED','retryable':False});examples['empty_partial']=j
j=deepcopy(job);j['status']='cancelled';j['sources'][0]['status']='cancelled';examples['cancelled']=j
j=deepcopy(job);j['status']='failed';j['sources'][0].update(status='failed',error_code='SOURCE_TIMEOUT',retryable=True);examples['failed']=j
j=deepcopy(job);j['status']='researching';j['finished_at']=None;j['sources'][0].update(status='researching',checked_at=None);examples['researching']=j
for name,j in examples.items(): (P/(name+'.json')).write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
