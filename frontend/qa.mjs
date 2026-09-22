import net from 'node:net';
import {spawn} from 'node:child_process';
import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import http from 'node:http';import fs from 'node:fs';import path from 'node:path';
// Refuse to reuse or stop a server belonging to the user.
for(const port of [8000,18800]){await new Promise((resolve,reject)=>{const probe=net.createServer();probe.once('error',()=>reject(new Error(`Port ${port} is in use; stop your development server before QA`)));probe.listen(port,'127.0.0.1',()=>probe.close(resolve));});}
const backend=spawn(path.resolve('../.venv/Scripts/python.exe'),['-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8000','--no-access-log'],{cwd:'..',env:{...process.env,LH_ENABLE_PROBE:'0',LH_ENABLE_LIST:'0'},stdio:'ignore'});
for(let i=0;i<50;i++){try{const r=await fetch('http://127.0.0.1:8000/health');if(r.ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
const root=path.resolve('dist');const server=http.createServer((req,res)=>{const file=path.resolve(root,'.'+(req.url==='/'?'/index.html':req.url));if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}try{res.setHeader('Content-Type',file.endsWith('.js')?'application/javascript':'text/html');res.end(fs.readFileSync(file));}catch{res.writeHead(404);res.end();}});
await new Promise(r=>server.listen(18800,'127.0.0.1',r));const browser=await chromium.launch({channel:'chrome',headless:true});const context=await browser.newContext({viewport:{width:390,height:844}});const page=await context.newPage();const checks=[];fs.mkdirSync('qa',{recursive:true});
async function scan(name){const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();checks.push({name,violations:r.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}))});await page.screenshot({path:`qa/${name}.png`});}
try{await page.goto('http://127.0.0.1:18800');await page.getByRole('button',{name:'서울 공고 찾아보기'}).waitFor();await scan('live-search');await page.getByRole('button',{name:'서울 공고 찾아보기'}).click();await page.getByText('공고 조회 서비스가 아직 준비되지 않았습니다. 공고가 없다는 의미는 아닙니다').waitFor();await scan('live-server-response');await page.getByRole('button',{name:'다시 조사하기',exact:true}).click();await page.getByText('공고 조회 서비스가 아직 준비되지 않았습니다. 공고가 없다는 의미는 아닙니다').waitFor();await page.getByRole('button',{name:'지역 검색으로 돌아가기'}).click();let synthetic={id:'synthetic-job',revision:1,status:'researching',sources:[],notices:[]};await page.route('**/v1/search-jobs**',async route=>{if(route.request().url().endsWith('/cancel'))return route.fulfill({json:{...synthetic,revision:3,status:'cancelled'}});if(route.request().method()==='GET')await new Promise(r=>setTimeout(r,1000));await route.fulfill({json:synthetic});});await page.getByRole('button',{name:'서울 공고 찾아보기'}).click();await page.waitForTimeout(850);await page.getByRole('button',{name:'조사 취소'}).click();await page.getByText('조사를 취소했습니다',{exact:true}).waitFor();await page.waitForTimeout(1300);await scan('api-cancel-late-response');await page.getByRole('button',{name:'지역 검색으로 돌아가기'}).click();await page.unroute('**/v1/search-jobs**');await page.route('**/v1/search-jobs**',r=>r.abort());await page.getByRole('button',{name:'서울 공고 찾아보기'}).click();await page.getByText('서버 응답을 확인하지 못했습니다. 입력한 지역을 유지한 채 다시 시도할 수 있습니다').waitFor();await scan('api-network-failure');await page.getByRole('button',{name:'지역 검색으로 돌아가기'}).click();await page.unroute('**/v1/search-jobs**');
const listFixture=JSON.parse(fs.readFileSync('../shared/contracts/list_review.json','utf8'));
await page.route('**/v1/search-jobs**',r=>r.fulfill({json:listFixture}));
await page.getByRole('button',{name:'서울 공고 찾아보기'}).click();
await page.getByRole('button',{name:'확인 필요 공고 1건',exact:true}).waitFor();
await scan('list-verified-empty');
await page.getByRole('button',{name:'확인 필요 공고 1건',exact:true}).click();
await scan('list-review');
await page.getByRole('button',{name:'합성 확인 필요 행복주택 상세 보기',exact:true}).click();
await scan('list-detail');
// Supply states use synthetic fixtures; never spend live API calls in this suite.
const supplyFixture=JSON.parse(fs.readFileSync('fixtures/supply.json','utf8'));
let supplyMode='available',supplyCalls=0;
await page.route('**/v1/search-jobs/*/notices/*/supply',async route=>{
 supplyCalls++;
 if(supplyMode==='delay'){await new Promise(r=>setTimeout(r,1200));return route.fulfill({json:supplyFixture});}
 if(supplyMode==='malformed')return route.fulfill({json:{...supplyFixture,notice_id:'wrong-notice'}});
 const r=structuredClone(supplyFixture);
 if(supplyMode==='empty'){r.status='empty';r.units=[];}
 if(supplyMode==='failed'){r.status='failed';r.error_code='API_KEY_NOT_REGISTERED';r.units=[];}
 return route.fulfill({json:r});
});
await page.getByRole('button',{name:'공급정보 조회',exact:true}).click();
await page.getByText('보증금: 10,000,000 원',{exact:true}).waitFor();
checks.push({name:'supply-area-precision',passed:await page.getByText('전용면적: 26.12345678 ㎡',{exact:true}).count()===1});
checks.push({name:'supply-unknown-not-zero',passed:await page.getByText('월 임대료: 미확인 · API 표시: 공고문 참조 · 공고문 확인 필요',{exact:true}).count()===1});
await page.getByText('보증금: 10,000,000 원',{exact:true}).scrollIntoViewIfNeeded();
await scan('supply-available');
await page.setViewportSize({width:320,height:640});await scan('supply-narrow');
checks.push({name:'supply-no-overflow',passed:await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)});
await page.setViewportSize({width:390,height:844});
for(const mode of ['empty','failed','malformed','delay']){
 await page.getByRole('button',{name:'검색 결과로 돌아가기'}).click();
 await page.getByRole('button',{name:'합성 확인 필요 행복주택 상세 보기',exact:true}).click();supplyMode=mode;
 await page.getByRole('button',{name:'공급정보 조회',exact:true}).click();
 if(mode==='empty')await page.getByText('공급정보 조회는 완료됐지만 반환된 주택형이 없습니다.',{exact:false}).waitFor();
 if(mode==='failed')await page.getByText('공급정보 서비스의 활용승인을 확인해 주세요.',{exact:false}).waitFor();
 if(mode==='malformed')await page.getByText('공급정보 응답을 확인하지 못했습니다. 다시 조회해 주세요.',{exact:true}).waitFor();
 if(mode==='delay'){
  await scan('supply-loading');await page.getByRole('button',{name:'검색 결과로 돌아가기'}).click();await page.waitForTimeout(1500);
  checks.push({name:'supply-late-response-ignored',passed:await page.getByText('보증금: 10,000,000 원',{exact:true}).count()===0});
  await page.getByRole('button',{name:'합성 확인 필요 행복주택 상세 보기',exact:true}).click();
 }else await scan('supply-'+mode);
}
await page.unroute('**/v1/search-jobs/*/notices/*/supply');
const documentFixture=JSON.parse(fs.readFileSync('fixtures/document.json','utf8'));
let documentMode='reviewed';
await page.route('**/v1/search-jobs/*/notices/*/document',async route=>{
 const r=structuredClone(documentFixture);
 if(documentMode==='delay')await new Promise(resolve=>setTimeout(resolve,1200));
 if(documentMode==='changed'){r.reviewed=false;r.facts=[];r.warnings=['문서 또는 정정 관계가 검토 기록과 달라 기존 확인값을 보류했습니다. 재검토가 필요합니다.'];}
 if(documentMode==='failed'){r.status='failed';r.error_code='DOCUMENT_ACCESS_DENIED';r.reviewed=false;r.facts=[];r.pdf_url=null;}
 if(documentMode==='malformed')r.notice_id='wrong';
 return route.fulfill({json:r});
});
for(const mode of ['reviewed','changed','failed','malformed','delay']){
 documentMode=mode;
 await page.getByRole('button',{name:'공고문 항목 확인',exact:true}).click();
 if(mode==='reviewed'){
  await page.getByText('21A · 청년(소득 있음) 기본 임대조건',{exact:true}).waitFor();
  const amount=page.getByText('보증금 50,400,000원 · 월 임대료 214,200원. 보증금 원문 단위 천원을 원으로 환산',{exact:true});
  checks.push({name:'document-conditional-rent',passed:await amount.count()===1});
  await amount.scrollIntoViewIfNeeded();await scan('document-reviewed');
  await page.setViewportSize({width:320,height:640});await scan('document-narrow');
  checks.push({name:'document-no-overflow',passed:await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)});
  await page.setViewportSize({width:390,height:844});
 }else if(mode==='delay'){
  await scan('document-loading');await page.getByRole('button',{name:'검색 결과로 돌아가기'}).click();await page.waitForTimeout(1500);
  checks.push({name:'document-late-response-ignored',passed:await page.getByText('21A · 청년(소득 있음) 기본 임대조건',{exact:true}).count()===0});
  await page.getByRole('button',{name:'합성 확인 필요 행복주택 상세 보기',exact:true}).click();
  break;
 }else{
  const message=mode==='changed'?'PDF는 확보했지만 항목 검토가 필요합니다. 이전 확인값은 표시하지 않습니다.':mode==='failed'?'공식 공고문을 확인하지 못했습니다. 원문 링크에서 직접 확인해 주세요.':'공고문 응답을 확인하지 못했습니다. 다시 시도해 주세요.';
  await page.getByText(message,{exact:true}).waitFor();await scan('document-'+mode);
  checks.push({name:'document-'+mode+'-no-facts',passed:await page.getByText('21A · 청년(소득 있음) 기본 임대조건',{exact:true}).count()===0});
 }
 await page.getByRole('button',{name:'검색 결과로 돌아가기'}).click();
 await page.getByRole('button',{name:'합성 확인 필요 행복주택 상세 보기',exact:true}).click();
}
await page.unroute('**/v1/search-jobs/*/notices/*/document');
checks.push({name:'official-link-present',passed:await page.getByRole('button',{name:'LH 공식 원문 열기 · 외부 브라우저로 이동'}).count()===1});
await context.route('https://apply.lh.or.kr/**',r=>r.fulfill({contentType:'text/html',body:'<html lang="ko"><title>Official link test</title><body>Synthetic external destination</body></html>'}));
const popupPromise=page.waitForEvent('popup');
await page.getByRole('button',{name:'LH 공식 원문 열기 · 외부 브라우저로 이동'}).click();
const popup=await popupPromise;await popup.waitForLoadState();
checks.push({name:'official-link-destination',passed:new URL(popup.url()).hostname==='apply.lh.or.kr'});
await popup.close();await page.bringToFront();
await page.getByRole('button',{name:'검색 결과로 돌아가기'}).click();await page.waitForTimeout(200);
checks.push({name:'list-return-focus',passed:await page.getByRole('button',{name:'합성 확인 필요 행복주택 상세 보기'}).evaluate(el=>el===document.activeElement)});
await page.getByRole('button',{name:'마감·취소로 제외된 공고 1건',exact:true}).click();
checks.push({name:'closed-not-in-review-tab',passed:await page.getByRole('button',{name:'합성 확인 필요 행복주택 상세 보기'}).count()===0});
await scan('list-excluded');
await page.getByRole('button',{name:'합성 마감 행복주택 상세 보기',exact:true}).click();await scan('list-excluded-detail');

await page.getByRole('button',{name:'검색 결과로 돌아가기'}).click();
await page.getByRole('button',{name:'지역 검색으로 돌아가기'}).click();
await page.unroute('**/v1/search-jobs**');
const partialList=structuredClone(listFixture);partialList.collection.list_complete=false;partialList.sources[0].error_code='PAGE_LIMIT_REACHED';
await page.route('**/v1/search-jobs**',r=>r.fulfill({json:partialList}));
await page.getByRole('button',{name:'서울 공고 찾아보기'}).click();
await page.getByText('목록 일부만 확인했습니다. 누락 가능성이 있어 전체 결과로 볼 수 없습니다').waitFor();
await scan('list-page-limit');
await page.getByRole('button',{name:'지역 검색으로 돌아가기'}).click();await page.unroute('**/v1/search-jobs**');

for(const [name,url,expectLink] of [
 ['legacy-official-link','https://apply.lh.or.kr/LH/index.html?gv_url=SIL%3A%3ACLCC_SIL_0050.xfdl&gv_menuId=1010202&gv_param=CCR_CNNT_SYS_DS_CD%3A03%2CPAN_ID%3A10001%2CLCC%3AY',true],
 ['missing-official-link',null,false],
 ['unsafe-official-link','https://untrusted.example/document',false]]){
 const response=structuredClone(listFixture);response.notices[0].listing.official_url=url;
 await page.route('**/v1/search-jobs**',r=>r.fulfill({json:response}));
 await page.getByRole('button',{name:'서울 공고 찾아보기'}).click();await page.getByRole('button',{name:'확인 필요 공고 1건',exact:true}).click();
 await page.getByRole('button',{name:'합성 확인 필요 행복주택 상세 보기',exact:true}).click();
 checks.push({name,passed:(await page.getByRole('button',{name:'LH 공식 원문 열기 · 외부 브라우저로 이동'}).count()===1)===expectLink});await scan(name+'-screen');
 await page.getByRole('button',{name:'검색 결과로 돌아가기'}).click();await page.getByRole('button',{name:'지역 검색으로 돌아가기'}).click();await page.unroute('**/v1/search-jobs**');
}
const expired=structuredClone(listFixture);expired.status='failed';expired.notices=[];expired.excluded_notices=[];delete expired.collection;expired.sources[0].error_code='API_KEY_EXPIRED';
await page.route('**/v1/search-jobs**',r=>r.fulfill({json:expired}));await page.getByRole('button',{name:'서울 공고 찾아보기'}).click();
await page.getByText('LH 승인키의 사용 기간이 만료됐습니다. 발급 포털에서 갱신한 뒤 저장해 주세요.').waitFor();await scan('api-key-expired');
await page.getByRole('button',{name:'지역 검색으로 돌아가기'}).click();await page.unroute('**/v1/search-jobs**');
await page.getByRole('button',{name:'가상 화면 미리보기로 전환'}).click();await scan('search');await page.getByRole('textbox').fill('중구');await page.getByRole('button',{name:'서울 공고 찾아보기'}).click();await scan('invalid-region');await page.getByRole('textbox').fill('서울시');await page.getByRole('button',{name:'서울 공고 찾아보기'}).click();await page.getByRole('button',{name:'예시 행복주택 상세 보기'}).waitFor();await scan('results');await page.getByRole('button',{name:'예시 행복주택 상세 보기'}).click();await scan('detail');await page.getByRole('button',{name:'검색 결과로 돌아가기'}).click();await page.waitForTimeout(200);checks.push({name:'return-focus',passed:await page.getByRole('button',{name:'예시 행복주택 상세 보기'}).evaluate(el=>el===document.activeElement)});await page.getByRole('button',{name:'확인 필요 예시 1건'}).click();await scan('review');await page.getByRole('button',{name:'지역 검색으로 돌아가기'}).click();for(const label of ['전체 조사 실패','결과 없음','일부 출처 실패']){await page.getByRole('button',{name:label,exact:true}).click();await page.getByRole('button',{name:'서울 공고 찾아보기'}).click();await page.waitForTimeout(1200);await scan(label);await page.getByRole('button',{name:'지역 검색으로 돌아가기'}).click();}await page.getByRole('button',{name:'서울 공고 찾아보기'}).click();await page.getByRole('button',{name:'조사 취소'}).click();await scan('cancelled');await page.getByRole('button',{name:'지역 검색으로 돌아가기'}).click();await page.setViewportSize({width:320,height:640});await scan('narrow');fs.writeFileSync('qa/results.json',JSON.stringify(checks,null,2));console.log(JSON.stringify(checks));if(checks.some(c=>c.violations?.length||c.passed===false))process.exitCode=1;}finally{await browser.close();server.close();backend.kill();}





