(() => {
'use strict';
const P=window.PACK, main=document.getElementById('main'), KEY=`canvas-study:${P.project_id}:${P.week}:v1`;
const e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const L=P.language, bilingual=L.mode!=='english-only';
let state={done:{},notes:{},pages:{},highlights:[],practice:'',reflection:'',font:19},view='guide',current=P.documents[0].id,hideTranslation=false,pendingSelection=null;
const emptyMap=()=>Object.create(null);
function checkedState(value){
 const result={done:emptyMap(),notes:emptyMap(),pages:emptyMap(),highlights:[],practice:'',reflection:'',font:19};
 if(!value||typeof value!=='object')return result;
 for(const key of ['done','notes','pages'])for(const d of P.documents){
  const v=value[key]?.[d.id];
  if(key==='done'&&typeof v==='boolean')result[key][d.id]=v;
  if(key==='notes'&&typeof v==='string')result[key][d.id]=v.slice(0,100000);
  if(key==='pages'&&typeof v==='string')result[key][d.id]=v;
 }
 if(Array.isArray(value.highlights))result.highlights=value.highlights.filter(validHighlight).slice(0,10000);
 for(const key of ['practice','reflection'])if(typeof value[key]==='string')result[key]=value[key].slice(0,100000);
 if(Number.isFinite(value.font))result.font=Math.max(15,Math.min(28,value.font));
 return result;
}
try{const v=JSON.parse(localStorage.getItem(KEY)||'null');if(v?.project_id===P.project_id&&v.week===P.week)state=checkedState(v.state);}catch{}
function save(){try{localStorage.setItem(KEY,JSON.stringify({project_id:P.project_id,week:P.week,state}));status('Saved in this browser');}catch{status('Storage unavailable: export your progress before leaving.');}}
function status(text){document.getElementById('save-status').textContent=text;}
function link(url,label){if(!url)return '';try{const u=new URL(url,location.href);if(!['http:','https:'].includes(u.protocol))return '';return `<a href="${e(url)}" target="_blank" rel="noreferrer noopener">${e(label)}</a>`;}catch{return '';}}
function translated(text){return bilingual&&text?`<div class="pair-translation" lang="${e(L.code)}" dir="${e(L.direction||'ltr')}">${text}</div>`:'';}
function pair(en,tr){return `<div class="parallel stacked"><div lang="en">${en}</div>${translated(tr)}</div>`;}
function setView(v){pendingSelection=null;view=v;document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===v));render();}
function render(){if(view==='reader')reader();else if(view==='catalog')catalog();else if(view==='practice')practice();else guide();}
function openDoc(id){if(!P.documents.some(d=>d.id===id))return;current=id;history.replaceState(null,'','#'+encodeURIComponent(id));setView('reader');const target=pairNode(state.pages[id]);if(target)setTimeout(()=>target.scrollIntoView({block:'start'}),0);else window.scrollTo({top:0});}
function guide(){
 const g=P.guide,done=P.documents.filter(d=>state.done[d.id]).length;
 main.innerHTML=`<section class="card">${pair(`<h2>${e(g.title||'This week')}</h2><p>${e(g.intro||'')}</p>`,`<p>${e(g.intro_translation||'')}</p>`)}</section>
 <div class="notice">${e(g.verification||'Check sources and gaps before relying on this pack.')}</div>
 <div class="stats card"><div class="stat"><strong>${P.documents.length}</strong>readings and tasks</div><div class="stat"><strong>${done}/${P.documents.length}</strong>marked read by you</div><div class="stat"><strong>${P.documents.filter(d=>d.content_kind!=='full-text').length}</strong>summaries or source-only entries</div></div>
 <div class="toolbar"><button id="start-first" class="active">Start reading →</button><button id="print-guide">Print guide</button></div>
 ${(g.sessions||[]).map(s=>`<section class="card"><h2>${e(s.title)}</h2><p class="subtle">${e(s.when)} · ${e(s.group||'Group not specified')}</p><p>${e(s.preparation)}</p>${translated(`<p>${e(s.translation||'')}</p>`)}</section>`).join('')}
 <section class="card"><h2>Deadlines and next actions</h2>${(g.actions||[]).map(a=>`<p><span class="badge">${e(a.kind)}</span> <strong>${e(a.when)}</strong> — ${e(a.text)} ${link(a.source_url,'Source')}</p>`).join('')||'<p>No verified deadlines recorded.</p>'}</section>
 <section class="card"><h2>Missing material and coverage</h2><ul>${(g.gaps||[]).map(x=>`<li>${e(x)}</li>`).join('')||'<li>No gaps recorded; see individual coverage labels.</li>'}</ul></section>
 <section class="card"><h2>Expressions to use</h2><p class="subtle">Study suggestions, not quotations from the readings.</p><table>${(g.phrases||[]).map(x=>`<tr><td lang="en">${e(x[0])}</td><td lang="${e(L.code)}" dir="${e(L.direction||'ltr')}">${e(x[1])}</td></tr>`).join('')}</table></section>`;
 document.getElementById('start-first').onclick=()=>openDoc(P.documents[0].id);document.getElementById('print-guide').onclick=()=>window.print();
}
function reader(){
 const d=P.documents.find(x=>x.id===current),courses=[...new Set(P.documents.map(x=>x.course))];
 main.innerHTML=`<div class="reader-layout"><aside class="reader-nav" aria-label="Readings">${courses.map(c=>`<h3>${e(c)}</h3>${P.documents.filter(x=>x.course===c).map(x=>`<button class="doc-btn ${x.id===d.id?'active':''}" data-doc="${e(x.id)}"><span class="id">${e(x.id)}</span>${e(x.title)}</button>`).join('')}`).join('')}</aside><article class="flow-article">
 <div class="reader-header"><h2>${e(d.title)}</h2><button id="mark-done">${state.done[d.id]?'✓ Read · undo':'Mark read'}</button></div>
 <p class="subtle">${e(d.author)} · ${e(d.session)} · ${e(d.pages||'Page range not specified')}</p>
 <p><span class="badge">${e(d.status)}</span><span class="badge">${e(d.content_kind)}</span> ${e(d.translation_coverage||'')}</p>
 <div class="source-links">${link(d.source_url,'Original source')}${link(d.download,'Local original')}</div>
 <p class="screen-note">${e(d.requirement_basis||'')} ${e(d.checked_at?'Checked: '+d.checked_at:'')}</p>
 ${d.content_kind!=='full-text'?'<div class="notice">This entry is a summary, study guide, or source reference. It is not the complete reading.</div>':''}
 <div class="flow-toolbar toolbar"><label for="page-select">Jump to</label><select id="page-select">${d.units.map((u,i)=>`<option value="${i}">${e(u.label)}</option>`).join('')}</select>${bilingual?`<button id="toggle-translation" aria-pressed="${hideTranslation}">${hideTranslation?'Show':'Hide'} ${e(L.name)}</button>`:''}<button id="lookup-selection">Highlight</button><button id="remove-highlight">Remove highlight</button><label for="font-size">Text size</label><input id="font-size" type="range" min="15" max="28" value="${state.font}"></div>
 <p class="selection-hint">Select English, then use Highlight. Click a saved mark to remove it. Translations appear below each paragraph.</p>
 <div class="reading-flow ${hideTranslation?'hide-translation':''}">${d.units.map((u,i)=>`<section class="flow-unit" id="unit-${i}"><h3 class="unit-heading">${e(u.label)}</h3>${u.flow.map(p=>`<div class="reading-pair" data-pair="${e(p.id)}" data-unit="${i}"><div class="pair-en" lang="en" tabindex="0">${p.en}</div>${bilingual?(p.translation?translated(p.translation):`<p class="notice">Translation unavailable: ${e(p.translation_gap||'not provided')}</p>`):''}</div>`).join('')}</section>`).join('')}</div>
 <section class="card saved-vocabulary"><h3>Your highlights</h3><div id="highlight-list"></div></section>
 <section class="card"><h3>Questions for discussion</h3><ul>${(d.questions||[]).map(q=>`<li>${e(q)}</li>`).join('')}</ul></section>
 <section class="card notes"><label for="doc-notes">Your own explanation</label><p class="subtle">Claim → reason → assumption → objection → implication.</p><textarea id="doc-notes">${e(state.notes[d.id]||'')}</textarea><p class="screen-note">Notes stay in this browser. Export before changing devices or browser profiles.</p></section></article></div>`;
 document.querySelectorAll('[data-doc]').forEach(b=>b.onclick=()=>openDoc(b.dataset.doc));
 document.getElementById('page-select').onchange=ev=>document.getElementById('unit-'+ev.target.value).scrollIntoView({block:'start',behavior:'smooth'});
 if(bilingual)document.getElementById('toggle-translation').onclick=()=>{hideTranslation=!hideTranslation;document.querySelector('.reading-flow').classList.toggle('hide-translation',hideTranslation);const b=document.getElementById('toggle-translation');b.textContent=(hideTranslation?'Show ':'Hide ')+L.name;b.setAttribute('aria-pressed',String(hideTranslation));};
 document.getElementById('mark-done').onclick=()=>{state.done[d.id]=!state.done[d.id];save();document.getElementById('mark-done').textContent=state.done[d.id]?'✓ Read · undo':'Mark read';};
 document.getElementById('doc-notes').oninput=ev=>{state.notes[d.id]=ev.target.value;save();};
 const size=()=>document.querySelectorAll('.pair-en').forEach(p=>p.style.fontSize=state.font+'px');size();
 document.getElementById('font-size').oninput=ev=>{state.font=Number(ev.target.value);size();save();};
 for(const id of ['lookup-selection','remove-highlight'])document.getElementById(id).onpointerdown=ev=>ev.preventDefault();
 document.getElementById('lookup-selection').onclick=()=>commitHighlight(false);document.getElementById('remove-highlight').onclick=()=>commitHighlight(true);
 applyHighlights();renderHighlights();
}
function catalog(){
 main.innerHTML='<h2>Reading catalogue</h2><div class="toolbar"><input id="search" type="search" aria-label="Search readings" placeholder="Title, author, course…"><select id="status-filter" aria-label="Reading status"><option value="">All statuses</option><option>Required</option><option>Preparation</option><option>Recommended</option><option>Background</option></select></div><div id="results"></div>';
 function filter(){const q=document.getElementById('search').value.toLowerCase(),s=document.getElementById('status-filter').value;document.getElementById('results').innerHTML=P.documents.filter(d=>(!s||d.status===s)&&`${d.title} ${d.author} ${d.course}`.toLowerCase().includes(q)).map(d=>`<section class="card"><h3>${e(d.title)}</h3><p>${e(d.author)} · ${e(d.course)} · ${e(d.session)}</p><p>${e(d.pages||'')} · ${e(d.status)} · ${e(d.source_category||'')} · ${e(d.content_kind)}</p><p>${e(d.access_status||'')} ${e(d.translation_coverage||'')}</p><p>${e(d.requirement_basis||'')}</p><p>${d.official_deadline?'Official deadline: '+e(d.official_deadline):''} ${d.suggested_read_by?'Suggested reading time: '+e(d.suggested_read_by):''}</p><div class="source-links">${link(d.source_url,'Source')}${link(d.download,'Local original')}<button data-open="${e(d.id)}">Read</button></div></section>`).join('');document.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>openDoc(b.dataset.open));}
 document.getElementById('search').oninput=filter;document.getElementById('status-filter').onchange=filter;filter();
}
function practice(){main.innerHTML=`<section class="card"><h2>Your seminar card</h2><p>What is the claim? What supports it? What must be true? What is the strongest objection? What will you ask?</p><label for="practice-note">Your 60–90 second explanation in English</label><textarea id="practice-note">${e(state.practice)}</textarea><p class="subtle">Ask your study assistant to check understanding first, then improve only three important language points.</p><button id="print-card">Print</button></section><section class="card"><h2>Weekly reflection</h2><p>Actual time · A concept you can explain · An expression you used · Where translation helped · One adjustment next week</p><textarea id="reflection" aria-label="Weekly reflection">${e(state.reflection)}</textarea></section>`;document.getElementById('practice-note').oninput=ev=>{state.practice=ev.target.value;save();};document.getElementById('reflection').oninput=ev=>{state.reflection=ev.target.value;save();};document.getElementById('print-card').onclick=()=>window.print();}
function exportData(){return JSON.stringify({project_id:P.project_id,week:P.week,exported:new Date().toISOString(),state},null,2);}
function importData(text){const x=JSON.parse(text);if(x.project_id!==P.project_id||x.week!==P.week||!x.state)throw Error('Wrong project or week');const incoming=checkedState(x.state);for(const k of ['notes','done','pages'])Object.assign(state[k],incoming[k]);const marks=new Map(state.highlights.map(h=>[h.id,h]));for(const h of incoming.highlights)marks.set(h.id,h);state.highlights=[...marks.values()];for(const k of ['practice','reflection'])if(incoming[k])state[k]=incoming[k];save();render();}
window.StudyProgress=Object.freeze({exportData,importData});
for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>setView(b.dataset.view);
 document.getElementById('export').onclick=()=>{const blob=new Blob([exportData()],{type:'application/json'}),u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=`study-progress-${P.week}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};
 document.getElementById('import').onchange=async ev=>{try{const f=ev.target.files[0];if(f)importData(await f.text());}catch{status('Import failed: choose an export from this project and week.');}finally{ev.target.value='';}};

const plain=value=>{const t=document.createElement('template');t.innerHTML=value;return t.content.textContent;};
function validHighlight(h){return h&&typeof h.id==='string'&&typeof h.doc==='string'&&typeof h.pair==='string'&&typeof h.text==='string'&&Number.isInteger(h.start)&&Number.isInteger(h.end)&&h.start>=0&&h.end>h.start&&h.text.length<=3000&&typeof h.sourceText==='string'&&P.documents.some(d=>d.id===h.doc);}
state.highlights=Array.isArray(state.highlights)?state.highlights.filter(validHighlight):[];
function closeLookup(){pendingSelection=null;}
function pairNode(id){return [...document.querySelectorAll('.reading-pair')].find(n=>n.dataset.pair===id);}
function sourcePair(h){const d=P.documents.find(x=>x.id===h.doc);return d?.units.flatMap(u=>u.flow).find(p=>p.id===h.pair);}
function openLookup(h){pendingSelection={...h};}
function commitHighlight(remove){
 captureSelection();const h=pendingSelection;
 if(!h||h.doc!==current){document.getElementById('save-status').textContent='Select English text or click a saved highlight first.';return;}
 const en=pairNode(h.pair)?.querySelector('.pair-en');
 if(!en||en.textContent.slice(h.start,h.end)!==h.text){closeLookup();return;}
 state.highlights=state.highlights.filter(x=>!(x.doc===h.doc&&x.pair===h.pair&&x.start<h.end&&h.start<x.end));
 if(!remove){const context=plain(sourcePair(h)?.translation||'');state.highlights.push({...h,id:`${h.doc}:${h.pair}:${h.start}:${h.end}`,context,created:new Date().toISOString()});}
 save();window.getSelection()?.removeAllRanges();applyHighlights();renderHighlights();closeLookup();
}
function captureSelection(){
 if(view!=='reader')return false;
 const selection=window.getSelection();if(!selection||selection.isCollapsed)return false;
 if(selection.rangeCount!==1){closeLookup();return false;}
 const range=selection.getRangeAt(0),node=range.startContainer.nodeType===1?range.startContainer:range.startContainer.parentElement;
 const en=node?.closest('.pair-en');if(!en||!en.contains(range.endContainer)){closeLookup();return false;}
 const selected=range.toString();if(!/[A-Za-z]/.test(selected)||selected.length>3000){closeLookup();return false;}
 const prefix=document.createRange();prefix.selectNodeContents(en);prefix.setEnd(range.startContainer,range.startOffset);
 const trimStart=selected.length-selected.trimStart().length,trimEnd=selected.length-selected.trimEnd().length;
 const start=prefix.toString().length+trimStart,end=prefix.toString().length+selected.length-trimEnd;
 const p=en.closest('.reading-pair'),h={doc:current,unit:Number(p.dataset.unit),pair:p.dataset.pair,start,end,text:selected.trim(),sourceText:en.textContent};
 if(pendingSelection&&pendingSelection.doc===h.doc&&pendingSelection.pair===h.pair&&pendingSelection.start===start&&pendingSelection.end===end)return true;
 openLookup(h);return true;
}
function applyHighlights(){
 for(const en of document.querySelectorAll('.pair-en')){
  for(const old of en.querySelectorAll('mark.study-highlight'))old.replaceWith(...old.childNodes);
  en.normalize();const pair=en.closest('.reading-pair').dataset.pair;
  const saved=state.highlights.filter(h=>h.doc===current&&h.pair===pair&&en.textContent.slice(h.start,h.end)===h.text&&h.sourceText===en.textContent).sort((a,b)=>b.start-a.start);
  for(const h of saved){
   const walker=document.createTreeWalker(en,NodeFilter.SHOW_TEXT);const nodes=[];let n,offset=0;
   while(n=walker.nextNode()){const end=offset+n.textContent.length;if(end>h.start&&offset<h.end)nodes.push({node:n,start:Math.max(0,h.start-offset),end:Math.min(n.textContent.length,h.end-offset)});offset=end;}
   for(const x of nodes.reverse()){
    const range=document.createRange();range.setStart(x.node,x.start);range.setEnd(x.node,x.end);
    const mark=document.createElement('mark');mark.className='study-highlight';mark.dataset.highlight=h.id;mark.tabIndex=0;mark.setAttribute('role','button');mark.setAttribute('aria-label','Select highlight: '+h.text);range.surroundContents(mark);
    mark.onclick=ev=>{ev.stopPropagation();openLookup(h);};mark.onkeydown=ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();openLookup(h);}};
   }
  }
 }
}
function renderHighlights(){
 const el=document.getElementById('highlight-list');if(!el)return;
 const items=state.highlights.filter(h=>h.doc===current);
 el.innerHTML=items.length?items.map(h=>`<button class="vocab-chip" data-highlight-id="${e(h.id)}">${e(h.text)}${plain(sourcePair(h)?.en||'')!==h.sourceText?' — source changed; review':''}</button>`).join(''):'<p class="subtle">No highlights yet. Select English and press Highlight.</p>';
 for(const b of el.querySelectorAll('[data-highlight-id]'))b.onclick=()=>{const h=items.find(x=>x.id===b.dataset.highlightId),p=pairNode(h.pair);p?.closest('.earlier-pages')?.setAttribute('open','');p?.scrollIntoView({block:'center',behavior:'smooth'});openLookup(h);};
}

// Selection movement records offsets only: do not rebuild the DOM or steal focus.
document.addEventListener('selectionchange',captureSelection);
document.addEventListener('keydown',ev=>{if(ev.key==='Escape')closeLookup();});
document.addEventListener('pointerdown',ev=>{if(!ev.target.closest('.flow-toolbar,.study-highlight,.vocab-chip'))closeLookup();});
let scrollTimer;
window.addEventListener('scroll',()=>{clearTimeout(scrollTimer);scrollTimer=setTimeout(()=>{if(view!=='reader')return;const pairs=[...document.querySelectorAll('.reading-pair')];const found=pairs.find(p=>p.getBoundingClientRect().bottom>170);if(found&&state.pages[current]!==found.dataset.pair){state.pages[current]=found.dataset.pair;save();}},200);},{passive:true});
document.getElementById('site-title').textContent=P.title;
document.getElementById('site-subtitle').textContent=bilingual?'English + '+L.name+' · Your own reading, notes and questions':'English · Your own reading, notes and questions';
document.getElementById('week-label').textContent=P.week_label||P.week;
document.title=P.title;
const initial=decodeURIComponent(location.hash.slice(1));if(P.documents.some(d=>d.id===initial))openDoc(initial);else render();
window.addEventListener('hashchange',()=>{const id=decodeURIComponent(location.hash.slice(1));if(P.documents.some(d=>d.id===id))openDoc(id);});
})();
