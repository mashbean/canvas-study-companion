const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const ROOT=path.resolve(__dirname,'..');
const CODE=fs.readFileSync(path.join(ROOT,'templates/app.js'),'utf8');
const HTML=fs.readFileSync(path.join(ROOT,'templates/index.html'),'utf8');
const PACK=JSON.parse(fs.readFileSync(path.join(ROOT,'examples/demo-pack.json'),'utf8'));
const KEY=`canvas-study:${PACK.project_id}:${PACK.week}:v1`;
function fixture({saved,pack}={}){
 const dom=new JSDOM(HTML,{url:'http://127.0.0.1:8765/demo/#DEMO-01',runScripts:'outside-only'}),w=dom.window;
 w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=function(){};w.alert=()=>{};
 if(saved)w.localStorage.setItem(KEY,saved);
 w.PACK=structuredClone(pack||PACK);w.eval(CODE);
 return {dom,w,d:w.document,root:w.document.querySelectorAll('.pair-en')[1],stored:()=>w.localStorage.getItem(KEY)};
}
function at(f,offset,root=f.root){const walker=f.d.createTreeWalker(root,f.w.NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode()){if(offset<=n.length)return[n,offset];offset-=n.length;}throw Error('Offset');}
function select(f,start,end,root=f.root,endRoot=root){const r=f.d.createRange();r.setStart(...at(f,start,root));r.setEnd(...at(f,end,endRoot));const s=f.w.getSelection();s.removeAllRanges();s.addRange(r);f.d.dispatchEvent(new f.w.Event('selectionchange'));}
function click(f,id){const b=f.d.getElementById(id),ev=new f.w.MouseEvent('pointerdown',{bubbles:true,cancelable:true});if(b.onpointerdown)b.onpointerdown(ev);b.dispatchEvent(ev);b.click();return ev;}
test('selection does not mutate content, steal focus or write progress',()=>{
 const f=fixture(),ref=f.root.querySelector('strong'),before=f.root.innerHTML;f.root.focus();
 const observer=new f.w.MutationObserver(()=>{});observer.observe(f.d.body,{subtree:true,childList:true,attributes:true,characterData:true});
 for(let end=8;end<20;end++)select(f,4,end);
 assert.equal(observer.takeRecords().length,0);assert.equal(f.root.innerHTML,before);assert.equal(f.root.querySelector('strong'),ref);assert.equal(f.d.activeElement,f.root);assert.equal(f.stored(),null);assert.equal(f.d.querySelector('.popup,#lookup-popover'),null);f.dom.window.close();
});
test('nested highlight survives reload, removes cleanly, preserves notes and completion',()=>{
 const f=fixture();f.d.getElementById('doc-notes').value='My explanation';f.d.getElementById('doc-notes').dispatchEvent(new f.w.Event('input'));click(f,'mark-done');
 select(f,4,30);assert.equal(click(f,'lookup-selection').defaultPrevented,true);const saved=f.stored();
 assert.equal(JSON.parse(saved).state.highlights.length,1);assert(f.root.querySelector('mark'));const text=f.root.textContent;
 const next=fixture({saved});assert.equal(next.root.textContent,text);assert(next.root.querySelector('mark'));assert.equal(next.d.getElementById('doc-notes').value,'My explanation');assert.match(next.d.getElementById('mark-done').textContent,/undo/);
 next.root.querySelector('mark').click();click(next,'remove-highlight');assert.equal(next.root.querySelector('mark'),null);assert.equal(next.root.textContent,text);assert(next.root.querySelector('strong'));f.dom.window.close();next.dom.window.close();
});
test('export/import checks project and week and merges notes without executing content',()=>{
 const f=fixture();f.d.getElementById('doc-notes').value='<script>alert(1)</script>';f.d.getElementById('doc-notes').dispatchEvent(new f.w.Event('input'));select(f,4,20);click(f,'lookup-selection');const exported=f.w.StudyProgress.exportData();
 const next=fixture();next.w.StudyProgress.importData(exported);assert.equal(next.d.getElementById('doc-notes').value,'<script>alert(1)</script>');assert(next.d.querySelector('.pair-en mark'));assert.throws(()=>next.w.StudyProgress.importData(JSON.stringify({...JSON.parse(exported),week:'2099-01-05'})),/Wrong project/);f.dom.window.close();next.dom.window.close();
});
test('changed source retains but flags old highlights rather than silently reattaching',()=>{
 const f=fixture();select(f,4,20);click(f,'lookup-selection');const pack=structuredClone(PACK);pack.documents[0].units[0].flow[1].en+='<p>New source sentence.</p>';
 const next=fixture({saved:f.stored(),pack});assert.equal(next.root.querySelector('mark'),null);assert.match(next.d.getElementById('highlight-list').textContent,/source changed/);assert.equal(JSON.parse(next.stored()).state.highlights.length,1);f.dom.window.close();next.dom.window.close();
});
test('invalid cross-paragraph and translation selections clear pending highlights',()=>{
 const f=fixture();select(f,4,20);select(f,4,7,f.root,f.d.querySelectorAll('.pair-en')[2]);click(f,'lookup-selection');assert.equal(f.stored(),null);
 select(f,4,20);select(f,0,3,f.d.querySelector('.pair-translation'));click(f,'lookup-selection');assert.equal(f.stored(),null);f.dom.window.close();
});
test('English-only removes translation controls; RTL applies only to translated text',()=>{
 const p=structuredClone(PACK);p.language.mode='english-only';const f=fixture({pack:p});assert.equal(f.d.querySelector('.pair-translation'),null);assert.equal(f.d.getElementById('toggle-translation'),null);f.dom.window.close();
 p.language={mode:'bilingual-full',name:'العربية',code:'ar',direction:'rtl'};const r=fixture({pack:p});assert.equal(r.d.querySelector('.pair-translation').dir,'rtl');assert.equal(r.root.lang,'en');click(r,'toggle-translation');assert(r.d.querySelector('.reading-flow').classList.contains('hide-translation'));r.dom.window.close();
});
test('updated translations keep English anchors, stable IDs and saved progress',()=>{
 const f=fixture();select(f,4,20);click(f,'lookup-selection');const p=structuredClone(PACK);p.documents[0].units[0].flow[1].translation='<p>Revised translation.</p>';
 const next=fixture({saved:f.stored(),pack:p});assert(next.root.querySelector('mark'));assert.equal(next.root.closest('.reading-pair').dataset.pair,'demo-choice-2');f.dom.window.close();next.dom.window.close();
});
