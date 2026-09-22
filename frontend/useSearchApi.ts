import {useCallback,useEffect,useRef,useState} from 'react';
import {Platform} from 'react-native';
import * as Crypto from 'expo-crypto';
declare const process:{env:{EXPO_PUBLIC_API_URL?:string}};
const base=(process.env.EXPO_PUBLIC_API_URL || (Platform.OS==='web'?'http://127.0.0.1:8000':'')).replace(/\/$/,'');
const terminal=new Set(['completed','partial','failed','cancelled']);
export type Notice={id:string;title:string;housing_type:string;checked_at:string;checked_in_job_id:string;
 recruitment_status:string;verification_status:string;review_reasons:string[];
 listing?:{status:string;posted_date:string;closing_date:string;official_url:string|null}};
export type Collection={source:string;housing_type:string;posted_filter:string;closing_filter:string;pages_fetched:number;page_limit:number;rows_fetched:number;list_complete:boolean;date_filter_verified:boolean;scope_mismatch_count:number};
type Job={id:string;revision:number;status:string;sources:{error_code:string|null}[];notices:Notice[];excluded_notices?:Notice[];collection?:Collection};
function validNotice(n:any,id:string){return n&&typeof n.id==='string'&&typeof n.title==='string'&&typeof n.housing_type==='string'&&typeof n.checked_at==='string'&&n.checked_in_job_id===id&&['verified','needs_review'].includes(n.verification_status)&&['scheduled','open','closed','cancelled','unknown'].includes(n.recruitment_status)&&Array.isArray(n.review_reasons)&&n.review_reasons.every((s:unknown)=>typeof s==='string')&&(!n.listing||(['status','posted_date','closing_date'].every(k=>typeof n.listing[k]==='string')&&(n.listing.official_url===null||typeof n.listing.official_url==='string')));}
const sourceErrors:Record<string,string>={
 API_KEY_NOT_REGISTERED:'LH 승인키가 등록되지 않았다는 응답을 받았습니다. 활용신청과 키를 확인해 주세요.',
 API_KEY_EXPIRED:'LH 승인키의 사용 기간이 만료됐습니다. 발급 포털에서 갱신한 뒤 저장해 주세요.',
 API_KEY_TEMPORARILY_DISABLED:'LH 승인키를 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.',
 API_ACCESS_DENIED:'LH 서비스 접근이 거부됐습니다. 해당 API의 활용승인 상태를 확인해 주세요.',
 API_IP_NOT_REGISTERED:'LH 서비스에 등록되지 않은 IP라는 응답을 받았습니다.',
 API_INVALID_PARAMETERS:'LH 요청 조건을 처리하지 못했습니다. 조회 조건을 확인해 주세요.',
 API_MISSING_PARAMETERS:'LH 요청에 필수 조건이 누락됐습니다.',
 API_NO_DATA:'LH에서 데이터 없음 오류를 반환했습니다. 정상 조회가 완료된 빈 목록과는 구분해 확인해야 합니다.',
 RATE_LIMITED:'LH 호출 한도를 초과했습니다. 반복 조회를 멈추고 한도를 확인해 주세요.',
 SOURCE_TIMEOUT:'LH 응답 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요.',
};
function message(j:Job){
 const code=j.sources.find(s=>s.error_code)?.error_code;
 if(j.status==='cancelled')return '조사를 취소했습니다';
 if(j.status==='failed'){
  if(code&&sourceErrors[code])return sourceErrors[code];
  if(code==='ADAPTER_NOT_CONFIGURED'||code==='MISSING_API_KEY')return '공고 조회 서비스가 아직 준비되지 않았습니다. 공고가 없다는 의미는 아닙니다';
  if(code==='RESPONSE_VERIFICATION_PENDING')return '출처 연결은 확인했지만 공고 검증이 아직 끝나지 않았습니다';
  return '출처를 확인하지 못했습니다. 다시 시도해 주세요';
 }
 if(j.collection){
  if(!j.collection.list_complete)return '목록 일부만 확인했습니다. 누락 가능성이 있어 전체 결과로 볼 수 없습니다';
  return `LH 목록 조회를 마쳤습니다. 확인 필요 ${j.notices.length}건, 마감·취소로 제외 ${j.excluded_notices?.length||0}건. 원문 검증이 남아 있습니다`;
 }
 if(j.status==='partial')return '일부 출처 확인에 실패했습니다';
 if(j.status==='completed')return j.notices.length?'공고 응답을 받았습니다':'연결된 출처에서 확인된 공고가 없습니다';
 return '서울특별시 조사 중';
}
export function useSearchApi(){
 const [status,setStatus]=useState(''),[busy,setBusy]=useState(false),[job,setJob]=useState<Job|null>(null);
 const generation=useRef(0),session=useRef(''),active=useRef<Job|null>(null);
 async function request(path:string,method='GET',body?:object,key?:string){
  if(!base)throw new Error('configuration');
  const abort=new AbortController();const timer=setTimeout(()=>abort.abort(),10000);
  try{
   const r=await fetch(base+path,{method,signal:abort.signal,headers:{'Content-Type':'application/json','X-Session-Token':session.current,...(key?{'Idempotency-Key':key}:{})},body:body?JSON.stringify(body):undefined});
   if(!r.ok)throw new Error('request');const j=await r.json();
   if(typeof j.id!=='string'||!Number.isInteger(j.revision)||!['queued','researching','verifying',...terminal].includes(j.status)||!Array.isArray(j.sources)||!j.sources.every((s:any)=>s&&(s.error_code===null||typeof s.error_code==='string'))||!Array.isArray(j.notices)||!j.notices.every((n:any)=>validNotice(n,j.id))||(j.excluded_notices!==undefined&&(!Array.isArray(j.excluded_notices)||!j.excluded_notices.every((n:any)=>validNotice(n,j.id)))))throw new Error('shape');
   if(j.collection&&(!['source','housing_type','posted_filter','closing_filter'].every(k=>typeof j.collection[k]==='string')||!['pages_fetched','page_limit','rows_fetched','scope_mismatch_count'].every(k=>Number.isInteger(j.collection[k])&&j.collection[k]>=0)||typeof j.collection.list_complete!=='boolean'||typeof j.collection.date_filter_verified!=='boolean'))throw new Error('shape');
   return j as Job;
  }finally{clearTimeout(timer);}
 }
 function stop(){generation.current++;const previous=active.current;active.current=null;setBusy(false);if(previous&&!terminal.has(previous.status))void request('/v1/search-jobs/'+previous.id+'/cancel','POST').catch(()=>{});}
 async function cancel(){
  const j=active.current;const g=++generation.current;setBusy(true);setStatus('조사 취소를 요청하고 있습니다');
  try{if(!j)throw new Error('pending');const r=await request('/v1/search-jobs/'+j.id+'/cancel','POST');if(g!==generation.current)return;if(r.id!==j.id||r.revision<j.revision)throw new Error('stale');active.current=r;setJob(r);setStatus(message(r));}
  catch{if(g===generation.current)setStatus('취소 여부를 확인하지 못했습니다. 서버 작업은 계속될 수 있습니다');}
  finally{if(g===generation.current)setBusy(false);}
 }
 async function start(){
  const old=active.current;const g=++generation.current;active.current=null;setJob(null);
  if(old&&!terminal.has(old.status))void request('/v1/search-jobs/'+old.id+'/cancel','POST').catch(()=>{});
  setBusy(true);setStatus('서울특별시 조사를 요청하고 있습니다');
  try{
   if(!session.current)session.current=Crypto.randomUUID();
   let j=await request('/v1/search-jobs','POST',{region:'서울특별시'},Crypto.randomUUID());
   if(g!==generation.current){void request('/v1/search-jobs/'+j.id+'/cancel','POST').catch(()=>{});return;}
   active.current=j;const deadline=Date.now()+60000;
   while(g===generation.current){
    setJob(j);setStatus(message(j));if(terminal.has(j.status))break;if(Date.now()>deadline)throw new Error('timeout');
    await new Promise(r=>setTimeout(r,750));if(g!==generation.current)return;
    const next=await request('/v1/search-jobs/'+j.id);if(g!==generation.current)return;
    if(next.id!==j.id)throw new Error('wrong job');if(next.revision>=j.revision){j=next;active.current=j;}
   }
  }catch{if(g===generation.current)setStatus(base?'서버 응답을 확인하지 못했습니다. 입력한 지역을 유지한 채 다시 시도할 수 있습니다':'서버 주소 설정이 필요합니다');}
  finally{if(g===generation.current)setBusy(false);}
 }
 useEffect(()=>()=>{generation.current++;const j=active.current;if(j&&!terminal.has(j.status))void request('/v1/search-jobs/'+j.id+'/cancel','POST').catch(()=>{});},[]);
 const loadSupply=useCallback(async(noticeId:string,signal:AbortSignal):Promise<SupplyResult>=>{
  const current=active.current,g=generation.current;if(!current)throw new Error('stale');
  const path='/v1/search-jobs/'+encodeURIComponent(current.id)+'/notices/'+encodeURIComponent(noticeId)+'/supply';
  const abort=new AbortController(),cancel=()=>abort.abort();signal.addEventListener('abort',cancel);
  if(signal.aborted)abort.abort();const timer=setTimeout(cancel,25000);
  try{
   let method='POST';
   while(!abort.signal.aborted){
    const r=await fetch(base+path,{method,signal:abort.signal,headers:{'X-Session-Token':session.current}});
    if(!r.ok)throw new Error('request');const result=await r.json();
    if(g!==generation.current||active.current?.id!==current.id)throw new Error('stale');
    if(!validSupply(result,current.id,noticeId))throw new Error('shape');
    if(result.status!=='researching')return result;
    await new Promise<void>(resolve=>setTimeout(resolve,400));method='GET';
   }
   throw new Error('timeout');
  }finally{clearTimeout(timer);signal.removeEventListener('abort',cancel);}
 },[]);
 const loadDocument=useCallback(async(noticeId:string,signal:AbortSignal):Promise<DocumentResult>=>{
  const current=active.current,g=generation.current;if(!current)throw new Error('stale');
  const path='/v1/search-jobs/'+encodeURIComponent(current.id)+'/notices/'+encodeURIComponent(noticeId)+'/document';
  const abort=new AbortController(),cancel=()=>abort.abort();signal.addEventListener('abort',cancel);
  if(signal.aborted)abort.abort();const timer=setTimeout(cancel,35000);
  try{
   let method='POST';
   while(!abort.signal.aborted){
    const r=await fetch(base+path,{method,signal:abort.signal,headers:{'X-Session-Token':session.current}});
    if(!r.ok)throw new Error('request');const result=await r.json();
    if(g!==generation.current||active.current?.id!==current.id)throw new Error('stale');
    if(!validDocument(result,current.id,noticeId))throw new Error('shape');
    if(result.status!=='researching')return result;
    await new Promise<void>(resolve=>setTimeout(resolve,400));method='GET';
   }
   throw new Error('timeout');
  }finally{clearTimeout(timer);signal.removeEventListener('abort',cancel);}
 },[]);
 return {start,cancel,stop,status,busy,job,loadSupply,loadDocument};
}

export type SupplyFact={state:string;value:string|number|boolean|null;unit:string|null;reason:string|null;evidence_ids:string[]};
export type SupplyUnit={id:string;label:string;deposit:SupplyFact;monthly_rent:SupplyFact;exclusive_area?:SupplyFact;supply_area?:SupplyFact;total_households?:SupplyFact;offered_households?:SupplyFact};
export type SupplyResult={job_id:string;notice_id:string;status:'researching'|'available'|'empty'|'failed';error_code:string|null;checked_at:string|null;units:SupplyUnit[];evidence:{id:string;url:string;locator:string;checked_at:string}[]};
function validSupply(x:any,jobId:string,noticeId:string):x is SupplyResult{
 if(!x||x.job_id!==jobId||x.notice_id!==noticeId||!['researching','available','empty','failed'].includes(x.status)||!(x.error_code===null||typeof x.error_code==='string')||!Array.isArray(x.units)||x.units.length>100||!Array.isArray(x.evidence))return false;
 if(x.status!=='researching'&&(typeof x.checked_at!=='string'||!Number.isFinite(Date.parse(x.checked_at))))return false;
 if((x.status==='failed')!==(x.error_code!==null)||(x.status==='available')!==(x.units.length>0))return false;
 if(!x.evidence.every((e:any)=>e&&['id','url','locator','checked_at'].every(k=>typeof e[k]==='string')))return false;
 const evidence=new Set(x.evidence.map((e:any)=>e.id));
 return x.units.every((u:any)=>u&&typeof u.id==='string'&&typeof u.label==='string'&&['deposit','monthly_rent','exclusive_area','supply_area','total_households','offered_households'].every(k=>{
 const f=u[k];if(f===undefined)return !['deposit','monthly_rent'].includes(k);
 return f&&['known','unknown'].includes(f.state)&&(f.unit===null||typeof f.unit==='string')&&Array.isArray(f.evidence_ids)&&f.evidence_ids.every((id:any)=>typeof id==='string'&&evidence.has(id))&&(f.state==='known'?typeof f.value==='number'&&Number.isFinite(f.value)&&f.value>=0&&f.evidence_ids.length>0:f.value===null&&typeof f.reason==='string'&&f.reason.length>0);
 }));
}

export type DocumentResult={job_id:string;notice_id:string;status:'researching'|'partial'|'failed';error_code:string|null;checked_at:string|null;source_url:string|null;pdf_url:string|null;filename:string|null;sha256:string|null;current_id:string|null;original_id:string|null;reviewed:boolean;facts:{category:string;label:string;value:string;page:number}[];warnings:string[]};
function validDocument(x:any,jobId:string,noticeId:string):x is DocumentResult{
 if(!x||x.job_id!==jobId||x.notice_id!==noticeId||!['researching','partial','failed'].includes(x.status)||typeof x.reviewed!=='boolean'||!Array.isArray(x.facts)||x.facts.length>100||!Array.isArray(x.warnings)||!x.warnings.every((w:any)=>typeof w==='string'))return false;
 if(!(x.error_code===null||typeof x.error_code==='string')||(x.status==='failed')!==(x.error_code!==null)||x.reviewed!==(x.facts.length>0))return false;
 if(x.status!=='researching'&&(typeof x.checked_at!=='string'||!Number.isFinite(Date.parse(x.checked_at))))return false;
 if(x.status!=='partial'&&(x.reviewed||x.facts.length))return false;
 if(x.status==='partial'&&(!/^https:\/\/apply\.lh\.or\.kr\/lhapply\/lhFile\.do\?fileid=[0-9]{1,16}$/.test(x.pdf_url)||typeof x.filename!=='string'||!/^[a-f0-9]{64}$/.test(x.sha256)))return false;
 return x.facts.every((f:any)=>f&&['address','schedule','rent','eligibility','correction'].includes(f.category)&&typeof f.label==='string'&&typeof f.value==='string'&&Number.isInteger(f.page)&&f.page>=1&&f.page<=200);
}
