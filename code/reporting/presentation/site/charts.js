// All numerical charts are drawn from packaged, unchanged frozen CSV values.
export const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const number=(v,d=0)=>Number(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
export const pct=v=>(v*100).toFixed(2)+'%';
const svg=(label,w,h,body)=>`<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title>${body}</svg>`;
const text=(x,y,t,cls='',anchor='start')=>`<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}">${esc(t)}</text>`;
export function regionChart(rows){
 const names=['南段','Cape Hatteras','北部延伸'],scale=v=>v/900*250;let b='';
 for(let v=0;v<=900;v+=300){let y=310-scale(v);b+=`<line class="grid-line" x1="55" x2="650" y1="${y}" y2="${y}"/>`+text(44,y+4,v,'axis-text','end');}
 rows.forEach((r,i)=>{let x=115+i*200;for(const [key,dx,color] of [['entering_trajectories',0,'#b8c8cf'],['valid_7d_trajectories',51,'#087e7d']]){const v=+r[key],h=scale(v);b+=`<rect x="${x+dx}" y="${310-h}" width="39" height="${h}" fill="${color}" rx="2"/>`+text(x+dx+19.5,300-h,v,'','middle');}b+=text(x+45,336,names[i],'','middle');});
 b+=text(55,25,'独立轨迹数','axis-text')+`<rect x="225" y="368" width="12" height="12" fill="#b8c8cf"/>`+text(245,379,'进入轨迹','axis-text')+`<rect x="365" y="368" width="12" height="12" fill="#087e7d"/>`+text(385,379,'有七天配对','axis-text');
 return svg('历史六小时筛选：南段621/605，Cape Hatteras784/766，北部688/678，分别为进入轨迹和有七天配对的轨迹。',700,400,b);
}
export function modelTable(models,all=false){const rows=all?models: ['ExactPoint','LocalGaussian','MDN1','MDN22'].map(n=>models.find(r=>r.model===n));return `<div class="table-scroll"><table class="data-table mono"><thead><tr><th>模型</th><th>ES（km）↓</th><th>实际 H90</th><th>90%面积（km²）</th></tr></thead><tbody>${rows.map(r=>`<tr class="${r.model==='MDN22'?'highlight':''}"><td>${esc(r.model)}</td><td>${number(r.energy_km,3)}</td><td>${pct(r.h90)}</td><td>${number(r.area90_km2)}</td></tr>`).join('')}</tbody></table></div>`;}
export function comparisonChart(models){
 const rows=['ExactPoint','LocalGaussian','MDN1','MDN22'].map(n=>models.find(r=>r.model===n));let b=`<rect x="0" y="173" width="1020" height="42" rx="5" fill="#e2efea"/>`;
 const metrics=[{k:'energy_km',label:'ES（km）↓',lo:127,hi:137,ticks:[128,132,136],format:v=>number(v,3)},{k:'h90',label:'实际 H90 · 名义90%',lo:.865,hi:.935,ticks:[.87,.90,.93],format:pct},{k:'area90_km2',label:'平均90%面积（千km²）',lo:165000,hi:230000,ticks:[170000,195000,220000],format:v=>number(v/1000,1)}];
 rows.forEach((r,i)=>b+=text(10,62+i*45,r.model,r.model==='MDN22'?'label-strong':''));
 metrics.forEach((m,j)=>{const left=175+j*285,width=240,x=v=>left+(v-m.lo)/(m.hi-m.lo)*width;b+=text(left+width/2,20,m.label,'','middle');
 m.ticks.forEach(v=>{b+=`<line class="grid-line" x1="${x(v)}" x2="${x(v)}" y1="36" y2="218"/>`+text(x(v),239,m.k==='h90'?Math.round(v*100)+'%':m.k==='area90_km2'?v/1000:v,'axis-text','middle');});
 if(m.k==='h90')b+=`<line x1="${x(.9)}" x2="${x(.9)}" y1="36" y2="218" stroke="#087e7d" stroke-dasharray="4 5" opacity=".65"/>`;
 rows.forEach((r,i)=>{let y=58+i*45;const color=r.model==='MDN22'?'#087e7d':r.model==='MDN1'?'#213d4b':'#8ca4ae';b+=`<circle cx="${x(r[m.k])}" cy="${y}" r="6.5" fill="${color}"/>`+text(x(r[m.k]),y-13,m.format(r[m.k]),r.model==='MDN22'?'label-strong':'','middle');});});
 return svg('四模型在同一开发集的能量分数、90%预测椭圆实际覆盖率和平均面积。精确数值可打开完整数值表。',1035,255,b);
}
export function candidateChart(models){
 const rows=models.filter(r=>/^MDN\d+$/.test(r.model)),x=v=>72+(v/1000-172)/28*630,y=v=>335-(v-.87)/.05*285;let b='';
 for(let v=87;v<=92;v++){let yy=y(v/100);b+=`<line class="grid-line" x1="72" x2="702" y1="${yy}" y2="${yy}"/>`+text(58,yy+4,v+'%','axis-text','end');}
 [172,179,186,193,200].forEach(v=>b+=text(x(v*1000),360,v,'axis-text','middle'));
 b+=`<line x1="72" x2="702" y1="${y(.9)}" y2="${y(.9)}" stroke="#618785" stroke-dasharray="5 5"/>`+text(700,y(.9)-9,'名义90%','axis-text','end');
 rows.forEach(r=>{const special=['MDN1','MDN16','MDN22'].includes(r.model);const color=r.model==='MDN22'?'#087e7d':r.model==='MDN1'?'#183746':r.model==='MDN16'?'#508ba3':'#b9c7cc';b+=`<circle cx="${x(r.area90_km2)}" cy="${y(r.h90)}" r="${special?7:4.5}" fill="${color}" stroke="white" stroke-width="1"><title>${r.model}：H90 ${pct(r.h90)}，面积 ${number(r.area90_km2)} km²</title></circle>`;if(special)b+=text(x(r.area90_km2)+(r.model==='MDN16'?-10:11),y(r.h90)+(r.model==='MDN16'?19:5),r.model,r.model==='MDN22'?'label-strong':'',r.model==='MDN16'?'end':'start');});
 b+=text(72,25,'实际 H90','axis-text')+text(390,394,'平均90%区域面积（千km²）','axis-text','middle');return svg('12个MDN候选的覆盖与面积取舍，突出MDN1、MDN16、MDN22。平均覆盖不等于全面校准。',750,410,b);
}
export function scopeMap(g){
 const W=680,H=470,rad=Math.PI/180,merc=lat=>Math.log(Math.tan(Math.PI/4+lat*rad/2));
 const lon0=-85,lon1=-67,lat0=24,lat1=38,scale=Math.min((W-60)/((lon1-lon0)*rad),(H-40)/(merc(lat1)-merc(lat0)));
 const ox=(W-(lon1-lon0)*rad*scale)/2,oy=(H-(merc(lat1)-merc(lat0))*scale)/2;
 const xy=([lon,lat])=>[ox+(lon-lon0)*rad*scale,oy+(merc(lat1)-merc(lat))*scale];
 const path=points=>points.map((p,i)=>{const [x,y]=xy(p);return `${i?'L':'M'}${x.toFixed(2)},${y.toFixed(2)}`;}).join(' ')+'Z';
 let b=`<defs><clipPath id="map-clip"><rect width="680" height="470" rx="8"/></clipPath></defs><g clip-path="url(#map-clip)"><rect width="680" height="470" fill="#e6efee"/>`;
 for(const lon of [-84,-80,-76,-72,-68]){let xx=xy([lon,30])[0];b+=`<line x1="${xx}" x2="${xx}" y1="0" y2="470" stroke="#cfdddd"/>`+text(xx,455,Math.abs(lon)+'°W','axis-text','middle');}
 for(const lat of [25,30,35]){let yy=xy([-80,lat])[1];b+=`<line x1="0" x2="680" y1="${yy}" y2="${yy}" stroke="#cfdddd"/>`+text(11,yy-6,lat+'°N','axis-text');}
 b+=g.land.map(r=>`<path d="${path(r)}" fill="#ccd7ce" stroke="#8fa69c" stroke-width=".8"/>`).join('');
 b+=`<path d="${path(g.region)}" fill="#087e7d26" stroke="#087e7d" stroke-width="3"/>`;
 for(const [p,label,color] of [[[ -81.4,28.6],'Florida','#4d6866'],[[-76.4,32.9],'研究区域 R','#087e7d'],[[-74,27],'大西洋','#779591']]){const [x,y]=xy(p);b+=`<text x="${x}" y="${y}" text-anchor="middle" fill="${color}" font-size="15">${label}</text>`;}
 b+='</g>';return `<svg class="scope-map" viewBox="0 0 ${W} ${H}" role="img" aria-label="南段湾流研究释放区域R，使用项目冻结GeoJSON和Natural Earth陆地边界，Mercator等比例投影"><title>冻结研究区域 R，边界未经沿海裁剪</title>${b}</svg>`;
}
