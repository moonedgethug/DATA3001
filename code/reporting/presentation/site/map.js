const ns='http://www.w3.org/2000/svg';
const merc=lat=>Math.log(Math.tan(Math.PI/4+lat*Math.PI/360));
const bounds={west:-90,east:-65,north:41,south:21};
const W=1600,H=(merc(bounds.north)-merc(bounds.south))/((bounds.east-bounds.west)*Math.PI/180)*W;
function xy([lon,lat]){return [(lon-bounds.west)/(bounds.east-bounds.west)*W,(merc(bounds.north)-merc(lat))/(merc(bounds.north)-merc(bounds.south))*H];}
function path(points){return points.map((p,i)=>`${i?'L':'M'}${xy(p).map(x=>x.toFixed(2)).join(',')}`).join('')+'Z';}
export async function createMap(host){
 const data=await fetch('./assets/geography.json').then(r=>{if(!r.ok)throw new Error('Map data failed');return r.json();});
 const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('preserveAspectRatio','xMidYMid slice');svg.setAttribute('role','img');svg.setAttribute('aria-label','美国东南海岸与南段湾流项目释放区域R');
 function add(type,attrs,parent=svg){const n=document.createElementNS(ns,type);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);parent.appendChild(n);return n;}
 const group=add('g',{});
 for(let lon=-90;lon<=-65;lon+=5){const [x]=xy([lon,30]);add('path',{d:`M${x},0V${H}`,class:'graticule'},group);}
 for(let lat=20;lat<=45;lat+=5){const [,y]=xy([-80,lat]);add('path',{d:`M0,${y}H${W}`,class:'graticule'},group);}
 for(const p of data.land)add('path',{d:path(p),class:'coast'},group);
 const region=add('path',{d:path(data.region),class:'region'},group);
 function label(text,lon,lat,size=15,cl='map-label',rotate=0){const [x,y]=xy([lon,lat]);const t=add('text',{x,y,class:cl,'font-size':size,'text-anchor':'middle',transform:`rotate(${rotate} ${x} ${y})`},group);t.textContent=text;}
 label('FLORIDA',-82.1,28.0,17,'map-label',65);
 label('BAHAMAS',-76.4,24.9,13);
 label('CUBA',-79.5,22.0,17);
 label('NORTH ATLANTIC',-74.0,27.4,20,'map-water-label');
 label('CAPE HATTERAS',-74.8,36.2,12);
 label('研究区域 R',-76.0,33.2,18);
 label('SOUTHERN GULF STREAM',-75.9,32.6,10);
 const [px,py]=xy([-77,32]);
 add('circle',{cx:px,cy:py,r:5,fill:'#f0ad67',stroke:'#ffe5bd','stroke-width':1},group);
 add('circle',{cx:px,cy:py,r:13,fill:'none',stroke:'#f0ad67','stroke-opacity':.45},group);
 const t=add('text',{x:px+25,y:py+7,fill:'#e7c797','font-size':12,'font-family':'sans-serif'},group);t.textContent='示意起点';
 svg.style.overflow='visible';host.appendChild(svg);
 function update(p){
   const small=innerWidth<700;
   // Camera-scale handoff is illustrative. The map itself remains georeferenced.
   const z=1+Math.pow(1-p,3)*13;
   group.setAttribute('transform',`translate(${px*(1-z)} ${py*(1-z)}) scale(${z})`);
   svg.setAttribute('viewBox',small?'410 350 850 850':`0 0 ${W} ${H}`);
   svg.setAttribute('preserveAspectRatio',small?'xMidYMid meet':'xMidYMid slice');
   svg.style.transform=small?'translateY(19%)':'translate(17%,0) scale(1.05)';
   region.style.fillOpacity=.1+.035*Math.sin(p*Math.PI);
 }
 update(0);return {update};
}
