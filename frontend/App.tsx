import React, { useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, BackHandler, findNodeHandle, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Notice, useSearchApi } from './useSearchApi';
import { ScopeSummary, NoticeCard, NoticeDetail } from './LiveNotice';
import { StatusBar } from 'expo-status-bar';
import { normalizeSeoul, scenarios } from './search';
type Screen='search'|'results'|'detail';
type Scenario=keyof typeof scenarios;
const ink='#142F2A', green='#17664F';
function focus(ref:any){ if(!ref)return; if(Platform.OS==='web'){ref.focus?.();}else{const id=findNodeHandle(ref);if(id)AccessibilityInfo.setAccessibilityFocus(id);} }
function Button({label,onPress,secondary=false,selected=false,buttonRef}:any){return <Pressable ref={buttonRef} accessibilityRole="button" accessibilityLabel={label} accessibilityState={{selected}} onPress={onPress} style={({pressed,focused}:any)=>[styles.button,secondary&&styles.secondary,pressed&&{opacity:.8},focused&&{borderColor:'#142F2A',borderWidth:3}]}><Text style={[styles.buttonText,secondary&&{color:ink}]}>{label}</Text></Pressable>}
export default function App(){
 const api=useSearchApi(); const [demo,setDemo]=useState(false); const [selectedNotice,setSelectedNotice]=useState<Notice|null>(null); const [liveTab,setLiveTab]=useState<'review'|'excluded'|'verified'>('verified');
 const [screen,setScreen]=useState<Screen>('search'),[query,setQuery]=useState('서울특별시'),[error,setError]=useState(''),[scenario,setScenario]=useState<Scenario>('completed'),[busy,setBusy]=useState(false),[cancelled,setCancelled]=useState(false),[tab,setTab]=useState<'verified'|'review'>('verified');
 useEffect(()=>{if(Platform.OS==='web'){const d=(globalThis as any).document;d.documentElement.lang='ko';d.title='서울 공공주택 · 화면 초안';}},[]);
 const heading=useRef<any>(null),input=useRef<any>(null),card=useRef<any>(null),timer=useRef<ReturnType<typeof setTimeout>|null>(null),restore=useRef(false);
 const announce=(text:string)=>{if(Platform.OS!=='web')AccessibilityInfo.announceForAccessibility(text);};
 useEffect(()=>{const id=setTimeout(()=>{focus(restore.current?card.current:heading.current);restore.current=false;},120);return()=>clearTimeout(id);},[screen]);
 useEffect(()=>{if(!demo&&api.status)announce(api.status);},[api.status]);
 useEffect(()=>()=>{if(timer.current)clearTimeout(timer.current);},[]);
 const back=()=>{if(screen==='detail'){restore.current=true;setScreen('results');}else{if(!demo)api.stop();if(timer.current)clearTimeout(timer.current);setBusy(false);setScreen('search');}};
 useEffect(()=>{const sub=BackHandler.addEventListener('hardwareBackPress',()=>{if(screen==='search')return false;back();return true;});return()=>sub.remove();},[screen]);
 function search(){if(!normalizeSeoul(query)){setError('서울, 서울시 또는 서울특별시를 입력해 주세요. 현재는 서울 전체 검색을 지원합니다.');focus(input.current);announce('지역 입력을 확인해 주세요');return;}
 if(!demo){setError('');setSelectedNotice(null);setLiveTab('verified');setScreen('results');void api.start();return;}
 setError('');setCancelled(false);setBusy(true);setTab('verified');setScreen('results');announce('서울특별시 예시 조사를 시작합니다');if(timer.current)clearTimeout(timer.current);timer.current=setTimeout(()=>{setBusy(false);announce(scenarios[scenario]);},1000);}
 const status=!demo?api.status:busy?'공식 출처 확인 중 · 화면 동작 예시':cancelled?'조사를 취소했습니다':scenarios[scenario];
 return <View style={styles.root}><StatusBar style="dark"/><ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
 <Text style={styles.brand}>집을 찾는 첫걸음</Text><Text style={styles.prototype}>{demo?'화면 초안 · 모든 공고는 가상 예시입니다':'LH 목록 연결 · 원문 검증 전'}</Text>
 {screen!=='search'&&<Button secondary label={screen==='detail'?'검색 결과로 돌아가기':'지역 검색으로 돌아가기'} onPress={back}/>}
 <Text ref={heading} accessible accessibilityRole="header" {...(Platform.OS==='web'?{tabIndex:-1}:{})} style={styles.title}>{screen==='search'?'서울에서 찾는\n나의 공공주택':screen==='results'?'서울특별시 검색 결과':!demo&&selectedNotice?selectedNotice.title:'예시 행복주택 안내'}</Text>
 {screen==='search'?<>
 <Text style={styles.lead}>서울 전체의 공공 임대·공공분양을 확인하세요. 로그인 없이 검색할 수 있습니다. 현재 연결 범위는 LH 임대주택이며 다른 기관과 유형은 아직 지원하지 않습니다.</Text>
 <View style={styles.panel}><Text nativeID="region-label" style={styles.label}>검색 지역</Text><TextInput ref={input} value={query} onChangeText={setQuery} onSubmitEditing={search} returnKeyType="search" accessibilityLabel="검색 지역, 서울 전체" accessibilityHint="서울, 서울시 또는 서울특별시를 입력하세요" style={styles.input}/>
 <Text style={styles.body}>서울특별시 전체 · 구별 검색은 아직 지원하지 않습니다.</Text>{error!==''&&<Text accessibilityRole="alert" style={styles.error}>{error}</Text>}<Button label="서울 공고 찾아보기" onPress={search}/></View>
 <Text accessibilityRole="header" style={styles.section}>어떤 정보를 확인하나요?</Text><Text style={styles.body}>접수 일정, 보증금과 임대료, 신청 조건을 원문 근거와 함께 제공합니다. 확인이 필요한 정보는 따로 표시합니다.</Text>
 <Button secondary label={demo?"서버 연결 모드로 전환":"가상 화면 미리보기로 전환"} onPress={()=>setDemo(!demo)}/>{demo&&<View style={styles.preview}><Text accessibilityRole="header" style={styles.section}>초안 상태 미리보기</Text><Text style={styles.body}>아래에서 확인할 화면 상태를 선택하세요. 실제 조사는 실행되지 않습니다.</Text>{Object.entries({completed:'조사 완료',partial:'일부 출처 실패',empty:'결과 없음',failed:'전체 조사 실패'}).map(([key,label])=><Button key={key} secondary selected={scenario===key} label={`${label}${scenario===key?' · 선택됨':''}`} onPress={()=>setScenario(key as Scenario)}/>)}</View>}
 </>:screen==='results'?<>
 <View style={styles.panel}><Text accessibilityLiveRegion="polite" style={styles.status}>{status}</Text><Text style={styles.body}>{demo?'예시 범위: LH':'현재 연결 대상: LH'} · SH·GH·iH 및 지자체는 연결되지 않았습니다.</Text>{(demo?busy:api.busy)&&<Button secondary label="조사 취소" onPress={()=>{if(!demo){void api.cancel();return;}if(timer.current)clearTimeout(timer.current);setBusy(false);setCancelled(true);announce('조사를 취소했습니다');}}/>}</View>
 {!demo&&api.job?.collection&&<ScopeSummary collection={api.job.collection}/>}
 {!demo&&api.job&&api.job.status!=='cancelled'&&<>
 <Button secondary selected={liveTab==='verified'} label="확인된 공고 0건" onPress={()=>setLiveTab('verified')}/>
 <Button secondary selected={liveTab==='review'} label={`확인 필요 공고 ${api.job.notices.length}건`} onPress={()=>setLiveTab('review')}/>
 <Button secondary selected={liveTab==='excluded'} label={`마감·취소로 제외된 공고 ${api.job.excluded_notices?.length||0}건`} onPress={()=>setLiveTab('excluded')}/>
 {liveTab==='verified'?<Text style={styles.body}>원문 검증이 완료된 공고만 이 목록에 표시합니다. 현재는 목록 조회 단계입니다.</Text>:
 (liveTab==='review'?api.job.notices:api.job.excluded_notices||[]).map(n=><NoticeCard key={n.id} notice={n} excluded={liveTab==='excluded'} buttonRef={selectedNotice?.id===n.id?card:undefined} onOpen={()=>{setSelectedNotice(n);setScreen('detail');}}/>)}
 </>}
 {demo&&!busy&&!cancelled&&(scenario==='completed'||scenario==='partial')&&<><Button secondary selected={tab==='verified'} label="확인된 예시 공고 1건" onPress={()=>setTab('verified')}/><Button secondary selected={tab==='review'} label="확인 필요 예시 1건" onPress={()=>setTab('review')}/><View style={styles.panel}><Text style={styles.eyebrow}>{tab==='verified'?'접수 예정 · 가상 상태':'확인 필요 · 신청 가능 여부 미확인'}</Text><Text accessibilityRole="header" style={styles.section}>예시 행복주택</Text><Text style={styles.body}>서울특별시 · 행복주택</Text><Text style={styles.body}>{tab==='verified'?'접수 일정은 상세 화면에서 확인하세요.':'첨부 원문을 확인하지 못해 일정과 금액을 확정할 수 없습니다.'}</Text><Button buttonRef={card} label="예시 행복주택 상세 보기" onPress={()=>setScreen('detail')}/></View></>}
 {!(demo?busy:api.busy)&&<Button label={demo?'다시 조사하기 · 예시':'다시 조사하기'} onPress={search}/>}</>:!demo&&selectedNotice?<NoticeDetail key={selectedNotice.id} notice={selectedNotice} loadSupply={api.loadSupply}/>:<>
 <View style={styles.panel}><Text style={styles.eyebrow}>가상 공고 · 실제 신청 대상 아님</Text>{[['위치','서울특별시 · 상세 주소 미확인'],['접수 일정','미확인 · 임의 마감시간을 표시하지 않습니다'],['보증금','미확인'],['월 임대료','미확인'],['신청 조건','공식 원문 확인 필요'],['근거 및 확인 시점','가상 예시이므로 공식 근거와 확인 시점이 없습니다']].map(([label,value])=><View key={label} style={styles.fact}><Text accessibilityRole="header" style={styles.label}>{label}</Text><Text style={styles.body}>{value}</Text></View>)}</View><Text style={styles.body}>실제 공고 연동 후 공식 원문 열기와 관심 공고 저장을 제공합니다.</Text>
 </>}
 <Text style={styles.footer}>공고를 이해하기 쉽게, 확인은 꼼꼼하게.</Text>
 </ScrollView></View>;
}
const styles=StyleSheet.create({root:{flex:1,backgroundColor:'#F5F7F2'},content:{padding:24,paddingTop:56,paddingBottom:48,maxWidth:620,width:'100%',alignSelf:'center',gap:16},brand:{fontSize:15,fontWeight:'700',color:green},prototype:{fontSize:14,color:'#555F59'},title:{fontSize:32,lineHeight:43,fontWeight:'700',color:ink},lead:{fontSize:18,lineHeight:29,color:ink},body:{fontSize:17,lineHeight:27,color:'#34483F'},panel:{backgroundColor:'#FFFFFF',borderColor:'#C7D4CC',borderWidth:1,borderRadius:20,padding:20,gap:16},label:{fontSize:17,fontWeight:'700',color:ink},input:{minHeight:56,borderWidth:2,borderColor:green,borderRadius:12,padding:14,fontSize:19,color:ink,backgroundColor:'#FFF'},button:{minHeight:52,paddingVertical:14,paddingHorizontal:18,backgroundColor:green,borderRadius:12,justifyContent:'center',borderWidth:2,borderColor:green},secondary:{backgroundColor:'#EEF4EE',borderColor:'#82988A'},buttonText:{fontSize:17,fontWeight:'600',color:'#FFFFFF',textAlign:'center'},section:{fontSize:21,lineHeight:30,fontWeight:'700',color:ink},error:{color:'#9A2525',fontSize:16,lineHeight:25},preview:{gap:12,paddingTop:16},status:{fontSize:19,lineHeight:29,fontWeight:'600',color:ink},eyebrow:{fontSize:15,fontWeight:'700',color:green},fact:{gap:7,paddingBottom:12,borderBottomWidth:1,borderBottomColor:'#DCE5DD'},footer:{fontSize:14,color:'#555F59',marginTop:24}});

