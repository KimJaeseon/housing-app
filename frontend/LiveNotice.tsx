import React,{useEffect,useRef,useState} from 'react';
import {AccessibilityInfo,Linking,Platform,Pressable,StyleSheet,Text,View} from 'react-native';
import {Collection,Notice,SupplyResult,SupplyFact} from './useSearchApi';
const s=StyleSheet.create({panel:{backgroundColor:'#FFFFFF',borderWidth:1,borderColor:'#C7D4CC',borderRadius:20,padding:20,gap:14},title:{fontSize:21,lineHeight:30,fontWeight:'700',color:'#142F2A'},body:{fontSize:17,lineHeight:27,color:'#34483F'},button:{minHeight:52,padding:14,backgroundColor:'#EEF4EE',borderColor:'#17664F',borderWidth:2,borderRadius:12,justifyContent:'center'},buttonText:{fontSize:17,lineHeight:26,fontWeight:'600',color:'#142F2A'},error:{fontSize:17,lineHeight:27,color:'#9A2525'}});
export function LiveButton({label,onPress,buttonRef}:any){return <Pressable ref={buttonRef} accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={({focused}:any)=>[s.button,focused&&{borderWidth:3,borderColor:'#142F2A'}]}><Text style={s.buttonText}>{label}</Text></Pressable>;}
export function ScopeSummary({collection:c}:{collection:Collection}){return <View style={s.panel}><Text accessibilityRole="header" style={s.title}>이번 조회 범위</Text><Text style={s.body}>LH · 서울특별시 · {c.housing_type}</Text><Text style={s.body}>게시일 조회 기간: {c.posted_filter} ~ {c.closing_filter}. 이 기간 밖의 공고는 조사하지 않았습니다.</Text><Text style={s.body}>목록 {c.pages_fetched}페이지, {c.rows_fetched}건 확인. {c.list_complete?'반환된 총건수까지 조회했습니다.':'페이지 제한 또는 오류로 목록 일부만 조회했습니다.'}</Text><Text style={s.body}>{c.date_filter_verified?'요청한 게시일 기간이 응답에 반영됐습니다.':'조회 기간의 적용을 확인하지 못했습니다.'} 원문 검증은 남아 있습니다. 확인된 공고가 0건이어도 서울에 모집 공고가 없다는 의미는 아닙니다.</Text>{c.scope_mismatch_count>0&&<Text style={s.body}>지역·유형이 다른 응답 {c.scope_mismatch_count}건을 보류했습니다.</Text>}</View>;}
export function NoticeCard({notice:n,onOpen,buttonRef,excluded=false}:{notice:Notice;onOpen:()=>void;buttonRef:any;excluded?:boolean}){return <View style={s.panel}><Text accessibilityRole="header" style={s.title}>{n.title}</Text><Text style={s.body}>서울특별시 · {n.housing_type}</Text><Text style={s.body}>{excluded?'검색 대상에서 제외됨 · 마감 또는 취소':'확인 필요 · 신청 가능 여부 미확인'}</Text><Text style={s.body}>LH 목록 표시: {n.listing?.status||'미확인'}</Text><Text style={s.body}>접수 일정·금액·자격: 원문 확인 필요</Text><LiveButton buttonRef={buttonRef} label={`${n.title} 상세 보기`} onPress={onOpen}/></View>;}
export function NoticeDetail({notice:n,loadSupply}:{notice:Notice;loadSupply:(id:string,signal:AbortSignal)=>Promise<SupplyResult>}){
 const [linkError,setLinkError]=useState('');const url=n.listing?.official_url;
 const safe=(()=>{if(!url)return false;try{const parsed=new URL(url);if(parsed.origin!=='https://apply.lh.or.kr'||parsed.hash||parsed.username||parsed.password)return false;
 const keys=Array.from(parsed.searchParams.keys());if(new Set(keys).size!==keys.length)return false;
 if(parsed.pathname==='/lhapply/apply/wt/wrtanc/selectWrtancInfo.do')return keys.every(k=>['panId','aisTpCd','uppAisTpCd','ccrCnntSysDsCd','mi'].includes(k)&&/^[0-9]+$/.test(parsed.searchParams.get(k)||''))&&['panId','aisTpCd','uppAisTpCd','ccrCnntSysDsCd'].every(k=>parsed.searchParams.has(k));
 if(parsed.pathname==='/LH/index.html')return keys.length===3&&/^SIL::CLCC_SIL_[0-9]{4}\.xfdl$/.test(parsed.searchParams.get('gv_url')||'')&&/^[0-9]+$/.test(parsed.searchParams.get('gv_menuId')||'')&&/^CCR_CNNT_SYS_DS_CD:[0-9]+,PAN_ID:[0-9]+,LCC:Y$/.test(parsed.searchParams.get('gv_param')||'');return false;}catch{return false;}})();

 async function open(){setLinkError('');try{if(!safe||!url)throw new Error('url');await Linking.openURL(url);}catch{setLinkError('공식 원문을 열지 못했습니다. 연결을 확인하고 다시 시도해 주세요.');}}
 return <View style={s.panel}><Text style={s.body}>원문 검증 전 · 이 화면으로 신청 자격을 확정하지 마세요.</Text>{[
 ['지역·유형',`서울특별시 · ${n.housing_type}`],['목록 상태',n.listing?.status||'미확인'],
 ['목록 게시일',n.listing?.posted_date||'미확인'],['목록 마감일',n.listing?.closing_date||'미확인'],
 ['실제 신청 접수 일정','미확인 · 목록 마감일을 접수 종료시각으로 사용하지 않습니다'],['보증금·월 임대료','미확인 · 0원이 아닙니다'],['신청 자격','공식 원문 검증 전'],
 ['확인 시점',new Date(n.checked_at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})+' (한국 시간)'],
 ['확인 근거','LH 공식 목록 API. 첨부 공고문·금액·자격·최종 정정 관계는 미검증']
 ].map(([label,value])=><View key={label}><Text accessibilityRole="header" style={s.title}>{label}</Text><Text style={s.body}>{value}</Text></View>)}
 <Text accessibilityRole="header" style={s.title}>확인이 필요한 이유</Text>{n.review_reasons.map((reason,index)=><Text key={index} style={s.body}>{reason}</Text>)}
 {safe?<LiveButton label="LH 공식 원문 열기 · 외부 브라우저로 이동" onPress={()=>void open()}/>:<Text style={s.body}>안전한 공식 원문 링크를 확인하지 못했습니다.</Text>}
 <SupplyPanel noticeId={n.id} loadSupply={loadSupply}/>
 {!!linkError&&<Text accessibilityRole="alert" style={s.error}>{linkError}</Text>}
 </View>;
}


function SupplyPanel({noticeId,loadSupply}:{noticeId:string;loadSupply:(id:string,signal:AbortSignal)=>Promise<SupplyResult>}){
 const [result,setResult]=useState<SupplyResult|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const active=useRef<AbortController|null>(null);
 useEffect(()=>()=>{active.current?.abort();},[]);
 async function load(){
  if(active.current)return;const abort=new AbortController();active.current=abort;setBusy(true);setError('');
  try{const r=await loadSupply(noticeId,abort.signal);if(!abort.signal.aborted)setResult(r);}
  catch{if(!abort.signal.aborted)setError('공급정보 응답을 확인하지 못했습니다. 다시 조회해 주세요.');}
  finally{if(!abort.signal.aborted){setBusy(false);active.current=null;}}
 }
 const errors:Record<string,string>={
 API_KEY_NOT_REGISTERED:'공급정보 서비스의 활용승인을 확인해 주세요. 목록 조회와 별도 서비스입니다. 승인 반영 후 목록을 다시 조사하고 공급정보를 조회해 주세요.',
 API_ACCESS_DENIED:'공급정보 서비스 접근이 거부됐습니다. 활용승인 상태를 확인한 뒤 목록을 다시 조사해 주세요.',
 UNSUPPORTED_SUPPLY_TYPE:'이 유형의 공급정보는 아직 연결하지 않았습니다. LH 공식 원문에서 확인해 주세요.',
 SUPPLY_NOT_ENABLED:'공급정보 조회가 서버에서 활성화되지 않았습니다. 실행 안내에 따라 서버를 시작해 주세요.',
 API_NO_DATA:'LH에서 데이터 없음 오류를 반환했습니다. 정상 조회된 빈 공급정보와는 다릅니다.',
 RATE_LIMITED:'호출 한도를 초과했습니다. 잠시 후 목록을 다시 조사해 주세요.'};
 function value(f?:SupplyFact){return !f?'미확인':f.state==='known'?`${Number(f.value).toLocaleString('ko-KR',{maximumFractionDigits:8})} ${f.unit||''}`:`미확인 · ${f.reason}`;}
 const status=busy?'공급정보 조회 중':error||(result?.status==='failed'?(errors[result.error_code||'']||'공급정보 확인에 실패했습니다. LH 공식 원문을 확인하거나 목록을 다시 조사해 주세요.'):result?.status==='empty'?'공급정보 조회는 완료됐지만 반환된 주택형이 없습니다. 공급 세대수가 0이라는 의미는 아닙니다.':result?.status==='available'?`주택형 ${result.units.length}건의 공급정보를 받았습니다. 공고문 대조가 남아 있습니다.`:'');
 useEffect(()=>{if(status&&Platform.OS==='ios')AccessibilityInfo.announceForAccessibilityWithOptions(status,{queue:true});},[status]);
 return <View style={{gap:14}}><Text accessibilityRole="header" style={s.title}>주택형별 공급정보</Text>
 <Text style={s.body}>주택형·면적·보증금·월 임대료를 추가 조회합니다. 신청 자격과 접수 일정은 공식 공고문 확인이 필요합니다.</Text>
 <Pressable accessibilityRole="button" accessibilityLabel="공급정보 조회" accessibilityState={{disabled:busy,busy}} disabled={busy} onPress={()=>void load()} style={({focused}:any)=>[s.button,focused&&{borderWidth:3,borderColor:'#142F2A'}]}><Text style={s.buttonText}>{busy?'공급정보 조회 중':'공급정보 조회'}</Text></Pressable>
 <Text accessibilityLiveRegion="polite" style={s.body}>{status}</Text>
 {result?.checked_at&&<Text style={s.body}>공급정보 확인: {new Date(result.checked_at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'})} (한국 시간)</Text>}
 {result?.units.map(u=><View key={u.id} style={s.panel}><Text accessibilityRole="header" style={s.title}>{u.label}</Text>{([
 ['전용면적',u.exclusive_area],['공급면적',u.supply_area],['전체 세대수',u.total_households],['금회 공급 세대수',u.offered_households],['보증금',u.deposit],['월 임대료',u.monthly_rent]
 ] as [string,SupplyFact|undefined][]).map(([label,f])=><Text key={label} style={s.body}>{label}: {value(f)}</Text>)}
 <Text style={s.body}>근거: LH 공고별 공급정보 API · 최종 정정 공고문 대조 전</Text>
 {result.evidence.filter(e=>u.deposit.evidence_ids.includes(e.id)||u.monthly_rent.evidence_ids.includes(e.id)||u.exclusive_area?.evidence_ids.includes(e.id)).map(e=><Text key={e.id} style={s.body}>{e.locator}</Text>)}
 </View>)}
 </View>;
}
