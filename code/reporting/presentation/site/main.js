import {createOcean} from './ocean.js';
import {createMap} from './map.js';
const $=s=>document.querySelector(s);
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
let ocean,map,progress=0,direction=0,time=2,last=performance.now(),paused=matchMedia('(prefers-reduced-motion: reduce)').matches;
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const storyOcean=$('.story-ocean'),storyMap=$('.story-map');
function updatePause(){ $('#pause-icon').textContent=paused?'▷':'Ⅱ';$('#pause-text').textContent=paused?'播放':'暂停';$('#pause').setAttribute('aria-label',paused?'播放动画':'暂停动画');$('#pause').setAttribute('aria-pressed',String(paused));}
function travel(to){if(!map)return;direction=to?1:-1;if(reduced){progress=to?1:0;direction=0;paint();}else if(paused){paused=false;updatePause();}}
$('#ascend').onclick=()=>travel(true);$('#descend').onclick=()=>travel(false);
$('.brand').onclick=e=>{e.preventDefault();travel(false);};
$('#pause').onclick=()=>{paused=!paused;updatePause();};
$('#replay').onclick=()=>{time=2;travel(false);};
$('#fallback-map').onclick=()=>{$('#error').hidden=true;progress=1;direction=0;paint();};
addEventListener('keydown',e=>{if(e.target instanceof HTMLButtonElement||e.target instanceof HTMLInputElement)return;if(e.code==='Space'){e.preventDefault();$('#pause').click();}if(e.key==='ArrowRight')travel(true);if(e.key==='ArrowLeft'||e.key==='Escape')travel(false);});
function paint(){
 const p=smooth(progress),blend=smooth((p-.27)/.56);
 $('#ocean').style.opacity=String(1-blend);$('#map').style.opacity=String(blend);
 const out=1-smooth(p/.27),into=smooth((p-.73)/.27);
 storyOcean.style.opacity=out;storyOcean.style.transform=`translateY(${-20*(1-out)}px)`;
 storyMap.style.opacity=into;storyMap.style.transform=`translateY(${18*(1-into)}px)`;
 storyOcean.inert=out<.5;storyMap.inert=into<.5;
 $('#experience').classList.toggle('is-map',p>.7);
 $('#scene-name').textContent=p>.92?'研究区域':p<.08?'海面视角':'尺度转换';
 $('#stage-number').textContent=p>.5?'02 / 02':'01 / 02';
 $('#progress-fill').style.width=`${p*100}%`;
 $('#disclosure').textContent=p>.9?'示意起点 · 项目真实 R 边界 · Natural Earth 海岸线':'视觉示意 · 非观测航迹或海况重现';
 map?.update(blend);
 if(ocean&&p<.995)ocean.render(time,p);
}
function frame(now){const dt=Math.min((now-last)/1000,.05);last=now;if(!paused&&!document.hidden){time+=dt;if(direction){progress=Math.max(0,Math.min(1,progress+direction*dt/7.6));if(progress===0||progress===1)direction=0;}}paint();requestAnimationFrame(frame);}
updatePause();
try{
 [ocean,map]=await Promise.all([createOcean($('#ocean')),createMap($('#map'))]);
 paint();$('#loading').classList.add('ready');$('#loading').setAttribute('aria-hidden','true');requestAnimationFrame(frame);
}catch(error){console.error(error);try{map=map||await createMap($('#map'));}catch(e){console.error(e);}$('#loading').classList.add('ready');$('#error').hidden=false;requestAnimationFrame(frame);}
