import {chapters,gaps,makeScreens} from './screens.js';
import {esc,modelTable} from './charts.js';
const $=id=>document.getElementById(id);
const route=n=>`#/${String(n).padStart(2,'0')}`;
let current=1,screens=[],data,ocean,oceanStarted=false;
const readJSON=async url=>{const r=await fetch(url);if(!r.ok)throw new Error(`${url}: ${r.status}`);return r.json();};
function navigate(n){if(n>=14&&n<=17){location.assign(`./pt4.html#0${n-13}`);return;}if(current===14&&n===13){location.assign("./pt3.html#model/mdn22");return;}if(n<1||n>17)return;if(location.hash===route(n))render();else location.hash=route(n);}
function render(){
 const match=location.hash.match(/^#\/(\d{1,2})$/);current=match?Math.max(1,Math.min(17,+match[1])):1;
 if(location.hash!==route(current))history.replaceState(null,'',route(current));
 if(current>=14){location.replace(`./pt4.html#0${current-13}`);return;}
 const s=screens[current-1],c=chapters[s.chapter];
 document.body.classList.toggle('cover',current===1);$('static-ocean').hidden=current!==1;
 $('screen').innerHTML=current===1?`<article class="scene" aria-labelledby="scene-title">${s.html.replace('<h1>','<h1 id="scene-title">')}</article>`:`<article class="scene" data-screen="${s.id}" aria-labelledby="scene-title"><header class="screen-head"><div><p class="eyebrow">0${s.chapter+1} / ${c.en} <span aria-hidden="true"> · </span> ${esc(s.status)}</p><h1 id="scene-title">${esc(s.title)}</h1><p class="lead">${esc(s.lead)}</p></div><span class="screen-index" aria-hidden="true">${String(s.id).padStart(2,'0')}</span></header><div class="body-content">${s.html}</div><div class="takeaway">${esc(s.takeaway)}</div><div class="source-line">${s.refs[0]?esc(s.refs[0].title):''} · 详细来源、口径与讲述备注见右上角</div></article>`;
 $('screen').scrollTop=0;
 $('page-number').textContent=`${String(current).padStart(2,'0')} / 17`;
 $('page-time').textContent=`讲述 ${s.time}秒`;
 $('previous').disabled=current===1;$('next').disabled=current===17;
 document.title=`${String(current).padStart(2,'0')} · ${s.title} | Where Things End Up`;
 document.querySelectorAll('[data-page]').forEach(el=>{if(+el.dataset.page===current)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
 document.querySelectorAll('[data-chapter]').forEach(el=>{if(+el.dataset.chapter===s.chapter)el.setAttribute('aria-current','step');else el.removeAttribute('aria-current');});
 $('page-announcement').textContent=`第${current}屏，共17屏。${s.title}`;
 if(current===1)renderOcean();
}
async function renderOcean(){
 if(ocean){ocean.resize();ocean.render(4,0);return;}
 if(oceanStarted)return;oceanStarted=true;
 try{const {createOcean}=await import('./ocean.js');ocean=await createOcean($('static-ocean'));ocean.render(4,0);}
 catch(error){$('static-ocean').dataset.fallback='true';/* All scientific content stays available without WebGL. */}
}
function sources(extra=''){
 const s=screens[current-1];
 $('sources-content').innerHTML=`<span class="badge">${String(current).padStart(2,'0')} / ${esc(s.status)}</span><h3>${esc(s.title)}</h3>${extra}<h3>讲述逻辑与边界</h3><p>${esc(s.notes)}</p><h3>本屏来源</h3><div class="source-list">${s.refs.map(r=>`<p>${r.href?`<a href="${esc(r.href)}" target="_blank" rel="noopener">${esc(r.title)} ↗</a>`:esc(r.title)}<br><code>${esc(r.path)}</code></p>`).join('')}</div>${s.gaps.length?`<h3>本屏证据缺口</h3>${s.gaps.map(id=>`<p><strong class="amber">${id} · ${gaps[id].title}</strong><br>${gaps[id].need}</p>`).join('')}`:'<p class="small" style="margin-top:16px">本屏未新增证据占位；实际结论仍以注明的评价口径为限。</p>'}<details><summary>全部证据交接 E01–E07</summary>${Object.entries(gaps).map(([id,g])=>`<p><strong>${id} · ${g.title}</strong><br>${g.need}</p>`).join('')}</details><p class="small" style="margin-top:25px">图表资产保留原文件，数值来自冻结CSV。<a href="./assets/report/provenance.json" target="_blank" rel="noopener">查看来源与SHA-256清单</a>。本网站不训练模型、不读取封存最终测试。</p>`;
 $('sources-dialog').showModal();
}
function setup(){
 document.querySelector(".skip").addEventListener("click",e=>{e.preventDefault();$("screen").focus();});
 document.querySelector('.chapter-nav').innerHTML=chapters.map((c,i)=>`<a href="${route(c.start)}" data-chapter="${i}"><span class="chapter-no">0${i+1}</span>${c.name}</a>`).join('');
 $('page-dots').innerHTML=screens.map(s=>`<a href="${route(s.id)}" data-page="${s.id}" class="${[4,8,13].includes(s.id)?'chapter-end':''}" aria-label="第${s.id}屏：${esc(s.title)}" title="${s.id}. ${esc(s.title)}"></a>`).join('');
 $('contents-list').innerHTML=chapters.map((c,i)=>`<section class="contents-group"><h3>0${i+1} ${c.name} <span class="small">· ${c.time}</span></h3>${screens.filter(s=>s.chapter===i).map(s=>`<button data-page="${s.id}"><span>${String(s.id).padStart(2,'0')}</span>${esc(s.title)}</button>`).join('')}</section>`).join('');
 $('previous').addEventListener('click',()=>navigate(current-1));$('next').addEventListener('click',()=>navigate(current+1));
 $('contents-button').addEventListener('click',()=>$('contents-dialog').showModal());
 $('sources-button').addEventListener('click',()=>sources());
 $('contents-list').addEventListener('click',e=>{const b=e.target.closest('button[data-page]');if(!b)return;$('contents-dialog').close();navigate(+b.dataset.page);});
 document.querySelectorAll('dialog').forEach(d=>{d.querySelector('.close').addEventListener('click',()=>d.close());d.addEventListener('click',e=>{if(e.target!==d)return;const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();});});
 $('screen').addEventListener('click',e=>{
 const f=e.target.closest('[data-figure]');if(f){$('figure-title').textContent=f.dataset.title;$('figure-content').innerHTML=`<img src="./assets/report/${esc(f.dataset.figure)}" alt="${esc(f.dataset.title)}"><p>${esc(f.dataset.caption)}</p><a href="./assets/report/${esc(f.dataset.figure)}" target="_blank" rel="noopener">打开原始图像 ↗</a>`;$('figure-dialog').showModal();return;}
 const t=e.target.closest('[data-table]');if(t)sources(`<h3>${t.dataset.table==='all'?'完整冻结比较表（含参照）':'四模型同口径比较'}</h3>${modelTable(data.models,t.dataset.table==='all')}<p class="small">开发验证 · 45 IDs / 33,971配对 · drifter等权 · 点估计</p>`);
 });
 addEventListener('keydown',e=>{
 if(document.querySelector('dialog[open]')||e.altKey||e.ctrlKey||e.metaKey||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)||e.target.isContentEditable)return;
 const target={ArrowRight:current+1,PageDown:current+1,ArrowLeft:current-1,PageUp:current-1,Home:1,End:17}[e.key];
 if(target!==undefined){e.preventDefault();navigate(target);}
 });
 addEventListener('hashchange',render);
 addEventListener('resize',()=>{if(ocean&&current===1)ocean.render(4,0);});
 render();
}
try{const results=await Promise.all([readJSON('./assets/report/data.json'),readJSON('./assets/geography.json')]);data=results[0];screens=makeScreens(data,results[1]);setup();}
catch(error){$('screen').innerHTML='<div class="error-notice"><h1>汇报资料暂时未能载入</h1><p>请刷新页面重试。原始海洋原型和数据文件仍可单独打开。</p><p><a href="./ocean.html">海洋原型</a> · <a href="./assets/report/model-summary.csv">冻结模型汇总CSV</a></p></div>';console.error('Report loading failed',error);}
