const {chromium}=require('../frontend/node_modules/playwright');
const assert=require('node:assert/strict');
const {spawn,spawnSync}=require('node:child_process');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
(async()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'certificate-controls-'));
 const db=path.join(tmp,'db.sqlite3'),port=process.env.UI_TEST_PORT||'8021',base=`http://127.0.0.1:${port}`;
 const seed=spawnSync(path.resolve('.venv/bin/python'),['-c',`from backend.database import initialize,connect
import sys
initialize(sys.argv[1])
db=connect(sys.argv[1])
with db:
 for i in range(30):
  name=f'Control Learner {i:02}'
  db.execute('INSERT INTO learners VALUES(?,?,?,?)',(100+i,1,name,name.casefold()))
  db.execute('INSERT INTO enrollments VALUES(1,3,?,1)',(100+i,))
db.close()`,db],{encoding:'utf8'});
 assert.equal(seed.status,0,seed.stderr);
 const server=spawn(path.resolve('.venv/bin/python'),['-m','uvicorn','backend.app:create_app','--factory','--host','127.0.0.1','--port',port,'--log-level','error'],{env:{...process.env,DB_PATH:db},stdio:'ignore'});
 let browser;
 try{
  for(let i=0;i<100;i++){try{if((await fetch(base+'/api/demo-actors')).ok)break}catch{}await new Promise(r=>setTimeout(r,50))}
  browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(8000);
  const failed=[],passed=[];
  async function check(name,fn){try{await fn();passed.push(name);console.log('PASS',name)}catch(e){failed.push(name);console.error('FAIL',name,e.message)}}
  const settle=async()=>{await page.locator('.ant-spin-spinning').waitFor({state:'hidden'});await page.locator('.ant-spin-blur').waitFor({state:'hidden'})};
  const search=page.getByRole('searchbox',{name:'Search certificates'});
  const apiError={status:503,contentType:'application/json',body:JSON.stringify({error:{message:'Injected temporary failure'}})};
  await page.goto(base);await page.getByText('Jordan Chen',{exact:true}).waitFor();await settle();
  await check('Issue date toggles ascending',async()=>{
   const response=page.waitForResponse(r=>r.url().includes('/api/certificates?')&&r.status()===200);
   await page.getByRole('columnheader',{name:'Issue date'}).click();
   const url=new URL((await response).url());assert.equal(url.searchParams.get('sort'),'issue_date');assert.equal(url.searchParams.get('order'),'asc');
   await settle();assert.match(await page.locator('.records tbody tr.ant-table-row').first().innerText(),/Date Later/);
  });
  await check('All five sort columns send ascending and descending',async()=>{
   for(const [label,key] of [['Learner','learner_name'],['Course','course_title'],['Serial number','serial_number'],['Status','status'],['Issue date','issue_date']]){
    const values=[];
    for(let i=0;i<2;i++){
     const response=page.waitForResponse(r=>r.url().includes('/api/certificates?')&&r.status()===200);
     await page.getByRole('columnheader',{name:label,exact:true}).click();
     const url=new URL((await response).url());assert.equal(url.searchParams.get('sort'),key);values.push(url.searchParams.get('order'));await settle();
    }
    assert.equal(new Set(values).size,2);
   }
  });
  await check('Search button and clear control',async()=>{
   await search.fill('Jordan');await page.locator('.ant-input-search-button').click();await settle();
   await page.getByText('1 matching records',{exact:false}).waitFor();
   await page.locator('.ant-input-clear-icon').click();await settle();
   await page.getByText('3 matching records',{exact:false}).waitFor();
  });
  await check('Cancel revocation preserves ACTIVE',async()=>{
   await page.getByRole('button',{name:'View DEMO-0001',exact:true}).click();
   await page.getByRole('button',{name:'Revoke certificate',exact:true}).click();
   await page.locator('.ant-modal-confirm').getByRole('button',{name:'Cancel',exact:true}).click();
   await page.locator('.ant-modal-confirm:visible').waitFor({state:'hidden'});
   assert.equal(await page.locator('.ant-drawer').getByText('ACTIVE',{exact:true}).count(),1);
   await page.getByRole('button',{name:'Close',exact:true}).click();
  });
  await check('List error Retry',async()=>{
   let once=true;await page.route(/\/api\/certificates\?/,async r=>{if(once){once=false;await r.fulfill(apiError)}else await r.continue()});
   await search.fill('Jordan');await search.press('Enter');await page.getByText('Injected temporary failure',{exact:true}).waitFor();
   await page.getByRole('button',{name:'Retry',exact:true}).click();await page.getByText('Jordan Chen',{exact:true}).waitFor();await settle();
   await page.unroute(/\/api\/certificates\?/);await page.locator('.ant-input-clear-icon').click();await settle();
  });
  await check('Detail error Retry detail',async()=>{
   let once=true;await page.route('**/api/certificates/1',async r=>{if(once){once=false;await r.fulfill(apiError)}else await r.continue()});
   await page.getByRole('button',{name:'View DEMO-0001',exact:true}).click();await page.getByRole('button',{name:'Retry detail',exact:true}).click();
   await page.locator('.ant-drawer').getByText('Jordan Chen',{exact:true}).waitFor();await page.getByRole('button',{name:'Close',exact:true}).click();await page.unroute('**/api/certificates/1');
  });
  await check('Course error Retry courses',async()=>{
   let fail=true;await page.route('**/api/courses',async r=>fail?r.fulfill(apiError):r.continue());await page.reload();
   await page.getByRole('button',{name:'Retry courses',exact:true}).waitFor();fail=false;await page.getByRole('button',{name:'Retry courses',exact:true}).click();
   await page.getByRole('button',{name:'Retry courses',exact:true}).waitFor({state:'hidden'});await page.unroute('**/api/courses');
  });
  await check('Export error retries actual download',async()=>{
   let calls=0;await page.route('**/api/certificates/export.csv?**',async r=>{calls++;if(calls===1)await r.fulfill(apiError);else await r.continue()});
   await page.getByRole('button',{name:'Export CSV',exact:true}).click();await page.getByText('Injected temporary failure',{exact:true}).waitFor();
   const download=page.waitForEvent('download',{timeout:4000});
   await page.getByRole('button',{name:/^Retry( export)?$/}).click();await download;assert.equal(calls,2);await page.unroute('**/api/certificates/export.csv?**');
  });
  await page.unroute('**/api/certificates/export.csv?**');
  await check('Uncertain issuance retry keeps the key and avoids duplicates',async()=>{
   const keys=[];let first=true;
   await page.route('**/api/certificate-issuances',async r=>{keys.push((await r.request().allHeaders())['idempotency-key']);if(first){first=false;await r.fetch();await r.abort('failed')}else await r.continue()});
   await page.locator('.issue-controls .ant-select-selector').click();await page.getByText('First Aid · 30 completed / 0 incomplete',{exact:true}).click();
   await page.getByRole('button',{name:'Issue certificates',exact:true}).click();await page.getByRole('button',{name:'Retry same operation',exact:true}).click();
   await page.getByText('Operation completed: 30 issued, 0 skipped, 0 failed.',{exact:true}).waitFor();assert.equal(keys.length,2);assert.equal(keys[0],keys[1]);await page.unroute('**/api/certificate-issuances');
  });
  await check('Record pagination next, previous, and page size',async()=>{
   const rows=async n=>page.waitForFunction(n=>document.querySelectorAll('.records tbody tr.ant-table-row').length===n,n);
   await rows(20);
   await page.locator('.records .ant-pagination-next button').click();await rows(13);
   await page.locator('.records .ant-pagination-prev button').click();await rows(20);
   await page.locator('.records .ant-pagination-options .ant-select-selector').click();await page.getByText('50 / page',{exact:true}).last().click();await rows(33);
  });
  await check('Outcome pagination next and previous',async()=>{
   assert.match(await page.locator('.operation-result tbody tr').first().innerText(),/Control Learner 00/);
   await page.locator('.operation-result .ant-pagination-next button').click();assert.match(await page.locator('.operation-result tbody tr').first().innerText(),/Control Learner 10/);
   await page.locator('.operation-result .ant-pagination-prev button').click();assert.match(await page.locator('.operation-result tbody tr').first().innerText(),/Control Learner 00/);
  });
  await check('Initial actor loading error Retry',async()=>{
   let fail=true;await page.route('**/api/demo-actors',async r=>fail?r.fulfill(apiError):r.continue());await page.reload();await page.getByRole('button',{name:'Retry',exact:true}).waitFor();fail=false;
   await page.getByRole('button',{name:'Retry',exact:true}).click();await page.getByText('East tenant',{exact:true}).waitFor();await page.unroute('**/api/demo-actors');
  });
  await check('Late revoke failure cannot overwrite another detail',async()=>{
   let release,started;const gate=new Promise(resolve=>release=resolve),received=new Promise(resolve=>started=resolve);
   await page.route('**/api/certificates/1/revoke',async r=>{started();await gate;await r.fulfill(apiError)});
   await search.fill('Jordan');await search.press('Enter');await page.getByRole('button',{name:'View DEMO-0001',exact:true}).click();
   await page.getByRole('button',{name:'Revoke certificate',exact:true}).click();
   await page.locator('.ant-modal-confirm').getByRole('button',{name:'Revoke certificate',exact:true}).click();await received;
   await page.locator('.ant-modal-confirm').getByRole('button',{name:'Cancel',exact:true}).click();
   await page.locator('.ant-modal-confirm:visible').waitFor({state:'hidden'});await page.getByRole('button',{name:'Close',exact:true}).click();
   await search.fill('Date Later');await search.press('Enter');await page.getByRole('button',{name:'View DEMO-0003',exact:true}).click();
   await page.locator('.ant-drawer').getByText('Date Later',{exact:true}).waitFor();
   const completed=page.waitForResponse('**/api/certificates/1/revoke');release();await completed;await settle();
   await page.waitForFunction(()=>!document.querySelector('.ant-drawer .ant-btn-loading'));
   assert.equal(await page.locator('.ant-drawer').getByText('Injected temporary failure',{exact:true}).count(),0);
   await page.unroute('**/api/certificates/1/revoke');
  });
  console.log(JSON.stringify({passed,failed},null,2));if(failed.length)process.exitCode=1;
 }finally{await browser?.close();server.kill();fs.rmSync(tmp,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exit(1)});
