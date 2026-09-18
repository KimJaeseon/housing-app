import net from 'node:net';
import {spawn} from 'node:child_process';
import {chromium} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
// Explicit live integration test: one real LH search; no response interception.
// Refuse to reuse or stop a server belonging to the user.
for(const port of [8000,18800]){await new Promise((resolve,reject)=>{const probe=net.createServer();probe.once('error',()=>reject(new Error(`Port ${port} is in use; stop your development server before QA`)));probe.listen(port,'127.0.0.1',()=>probe.close(resolve));});}
const env={...process.env,LH_ENABLE_LIST:'1',LH_POSTED_DATE:'2026.08.01',LH_CLOSING_DATE:'2026.09.16'};
const backend=spawn(path.resolve('../.venv/Scripts/python.exe'),['-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8000','--no-access-log'],{cwd:'..',env,stdio:'ignore'});
let server,browser;
try{
 let ready=false;for(let i=0;i<50;i++){if(backend.exitCode!==null)throw new Error('Test server could not start; check port 8000');try{const r=await fetch('http://127.0.0.1:8000/health');const h=await r.json();if(h.mode==='list_review'){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}if(!ready)throw new Error('Server not ready');
 const root=path.resolve('dist');server=http.createServer((req,res)=>{const file=path.resolve(root,'.'+(req.url==='/'?'/index.html':req.url));if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}try{res.setHeader('Content-Type',file.endsWith('.js')?'application/javascript':'text/html');res.end(fs.readFileSync(file));}catch{res.writeHead(404);res.end();}});
 await new Promise(r=>server.listen(18800,'127.0.0.1',r));browser=await chromium.launch({channel:'chrome',headless:true});const context=await browser.newContext({viewport:{width:390,height:844}});const page=await context.newPage();const checks=[];
 async function scan(name){const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();checks.push({name,violations:r.violations.map(v=>v.id)});await page.screenshot({path:`qa/${name}.png`,fullPage:true});}
 await page.goto('http://127.0.0.1:18800');await page.getByRole('button',{name:'서울 공고 찾아보기'}).click();
 await page.getByRole('button',{name:'마감·취소로 제외된 공고 2건',exact:true}).waitFor({timeout:45000});await scan('actual-lh-list');
 await page.getByRole('button',{name:'마감·취소로 제외된 공고 2건',exact:true}).click();await scan('actual-lh-excluded');
 const detail=page.getByRole('button',{name:'[정정공고]서울번동3 행복주택 예비입주자 모집 상세 보기',exact:true});await detail.click();await scan('actual-lh-detail');
 await page.setViewportSize({width:320,height:640});await scan('actual-lh-detail-narrow');
 await page.getByRole('button',{name:'LH 공식 원문 열기 · 외부 브라우저로 이동'}).scrollIntoViewIfNeeded();await page.screenshot({path:'qa/actual-lh-detail-bottom.png'});
 checks.push({name:'narrow-no-horizontal-overflow',passed:await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)});
 await page.getByRole('button',{name:'검색 결과로 돌아가기'}).click();await page.waitForTimeout(200);checks.push({name:'actual-return-focus',passed:await detail.evaluate(el=>el===document.activeElement)});
 fs.writeFileSync('qa/live-results.json',JSON.stringify(checks,null,2));console.log(JSON.stringify(checks));if(checks.some(c=>c.violations?.length||c.passed===false))process.exitCode=1;
}finally{if(browser)await browser.close();if(server)server.close();backend.kill();}


