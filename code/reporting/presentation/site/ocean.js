import * as THREE from 'three';
import { Water } from './assets/vendor/Water.js';
import { Sky } from './assets/vendor/Sky.js';

// The same height function drives water vertices and buoy pose. Artistic waves,
// not a reconstructed sea state, current field, or predicted drifter trajectory.
const WAVES=[
  {a:.35,k:.49,x:.93,z:.37,s:1.28,p:0},
  {a:.19,k:.88,x:-.37,z:.93,s:1.63,p:1.7},
  {a:.075,k:1.81,x:.72,z:-.69,s:2.15,p:3.2},
  {a:.033,k:3.4,x:.28,z:.96,s:2.7,p:.4}
];
export function sampleWave(x,z,time){
  let h=0,dx=0,dz=0;
  for(const w of WAVES){const q=w.k*(w.x*x+w.z*z)-w.s*time+w.p;h+=w.a*Math.sin(q);dx+=w.a*w.k*w.x*Math.cos(q);dz+=w.a*w.k*w.z*Math.cos(q);}
  return {h,dx,dz};
}
const glWave=`vec3 waveAt(vec2 p,float t){vec3 w=vec3(0.0);${WAVES.map(v=>`{float q=${v.k.toFixed(3)}*dot(vec2(${v.x.toFixed(3)},${v.z.toFixed(3)}),p)-${v.s.toFixed(3)}*t+${v.p.toFixed(3)}; w+=vec3(${v.a.toFixed(3)}*sin(q),${(v.a*v.k*v.x).toFixed(6)}*cos(q),${(v.a*v.k*v.z).toFixed(6)}*cos(q));}`).join('')}return w;}`;

export async function createOcean(host){
  const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,1.7));
  renderer.setSize(innerWidth,innerHeight);
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=.65;
  host.appendChild(renderer.domElement);
  const scene=new THREE.Scene();
  const camera=new THREE.PerspectiveCamera(48,innerWidth/innerHeight,.1,40000);
  const sky=new Sky();sky.scale.setScalar(20000);scene.add(sky);
  const sun=new THREE.Vector3().setFromSphericalCoords(1,THREE.MathUtils.degToRad(83),THREE.MathUtils.degToRad(240));
  const u=sky.material.uniforms;u.turbidity.value=7;u.rayleigh.value=2;u.mieCoefficient.value=.004;u.mieDirectionalG.value=.82;u.sunPosition.value.copy(sun);
  const pmrem=new THREE.PMREMGenerator(renderer);
  const env=pmrem.fromScene(scene,.03);scene.environment=env.texture;pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xc4e2f0,0x183741,2.6));
  const sunlight=new THREE.DirectionalLight(0xffd4a0,3.3);sunlight.position.copy(sun).multiplyScalar(100);scene.add(sunlight);
  const normals=await new THREE.TextureLoader().loadAsync('./assets/waternormals.jpg');
  normals.wrapS=normals.wrapT=THREE.RepeatWrapping;
  const geometry=new THREE.PlaneGeometry(2,2,256,256);
  const verts=geometry.attributes.position;
  for(let i=0;i<verts.count;i++){for(const axis of ['X','Y']){const v=verts['get'+axis](i);verts['set'+axis](i,Math.sign(v)*Math.pow(Math.abs(v),2.6)*7000);}}
  geometry.computeBoundingSphere();
  const water=new Water(geometry,{textureWidth:512,textureHeight:512,waterNormals:normals,sunDirection:sun,sunColor:0xffdbb0,waterColor:0x063344,distortionScale:1.4});
  water.rotation.x=-Math.PI/2;scene.add(water);
  const mat=water.material;
  mat.uniforms.size.value=4.2;
  mat.vertexShader=mat.vertexShader.replace('void main() {',`${glWave}\nvarying vec3 waveNormal;\nvoid main() {\nvec3 sampled=waveAt(vec2(position.x,-position.y),time);\nvec3 displaced=position+vec3(0.0,0.0,sampled.x);\nwaveNormal=normalize(vec3(-sampled.y,1.0,-sampled.z));`)
    .replaceAll('vec4( position, 1.0 )','vec4( displaced, 1.0 )');
  mat.fragmentShader=mat.fragmentShader.replace('void main() {','varying vec3 waveNormal;\nvoid main() {')
    .replace('normalize( noise.xzy * vec3( 1.5, 1.0, 1.5 ) )','normalize( waveNormal + vec3(noise.x*.36,0.0,noise.y*.36) )')
    .replace('float rf0 = 0.3;','float rf0 = 0.08;');
  mat.needsUpdate=true;

  const buoy=new THREE.Group();scene.add(buoy);
  const orange=new THREE.MeshStandardMaterial({color:0xf18232,roughness:.34,metalness:.12});
  const ivory=new THREE.MeshStandardMaterial({color:0xeee7cd,roughness:.4,metalness:.14});
  const rubber=new THREE.MeshStandardMaterial({color:0x162d34,roughness:.65});
  const metal=new THREE.MeshStandardMaterial({color:0xb6c8cb,roughness:.25,metalness:.85});
  function mesh(geo,material,y=0){const m=new THREE.Mesh(geo,material);m.position.y=y;buoy.add(m);return m;}
  mesh(new THREE.SphereGeometry(.73,64,40),orange,.02).scale.y=.76;
  const bumper=mesh(new THREE.TorusGeometry(.70,.045,12,80),rubber,.02);bumper.rotation.x=Math.PI/2;
  mesh(new THREE.CylinderGeometry(.46,.57,.16,48),ivory,.49);
  mesh(new THREE.CylinderGeometry(.14,.22,.26,32),orange,.68);
  mesh(new THREE.CylinderGeometry(.022,.029,1.03,12),metal,1.28);
  mesh(new THREE.CylinderGeometry(.055,.055,.30,12),rubber,1.88);
  mesh(new THREE.SphereGeometry(.066,16,12),ivory,2.04);
  for(let i=0;i<4;i++){const a=i*Math.PI/2;const bolt=mesh(new THREE.CylinderGeometry(.027,.027,.035,8),metal,.585);bolt.position.x=Math.cos(a)*.36;bolt.position.z=Math.sin(a)*.36;}
  // Legible small scientific-instrument identifier; intentionally a generic buoy.
  const labelCanvas=document.createElement('canvas');labelCanvas.width=256;labelCanvas.height=128;
  const ctx=labelCanvas.getContext('2d');ctx.fillStyle='#eee7cd';ctx.fillRect(0,0,256,128);ctx.fillStyle='#132d38';ctx.textAlign='center';ctx.font='bold 25px Arial';ctx.fillText('DRIFTER',128,53);ctx.font='20px Arial';ctx.fillText('01 · STUDY',128,88);
  const labelTexture=new THREE.CanvasTexture(labelCanvas);labelTexture.colorSpace=THREE.SRGBColorSpace;
  const label=new THREE.Mesh(new THREE.PlaneGeometry(.42,.21),new THREE.MeshStandardMaterial({map:labelTexture,roughness:.6}));label.position.set(.29,.22,.62);label.rotation.y=.4;buoy.add(label);
  const up=new THREE.Vector3(0,1,0),surfaceNormal=new THREE.Vector3(),target=new THREE.Vector3();
  const pointer={x:0,y:0};
  host.parentElement.addEventListener('pointermove',e=>{pointer.x=(e.clientX/innerWidth-.5)*2;pointer.y=(e.clientY/innerHeight-.5)*2;});
  function resize(){camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);}
  addEventListener('resize',resize);
  const initial=new THREE.Vector3(),high=new THREE.Vector3(),look=new THREE.Vector3();
  function render(time,progress){
    mat.uniforms.time.value=time*.65;
    const x=1.9+Math.sin(time*.075)*.7,z=Math.cos(time*.062)*.5;
    const w=sampleWave(x,z,time*.65);buoy.position.set(x,w.h,z);
    surfaceNormal.set(-w.dx,1,-w.dz).normalize();buoy.quaternion.setFromUnitVectors(up,surfaceNormal);
    buoy.rotateY(.15+Math.sin(time*.09)*.14);
    const mobile=innerWidth<700;
    initial.set(mobile?7.6:7, mobile?5.7:3.7,mobile?12:10);
    high.set(3,200,30);
    const lift=progress*progress;
    camera.position.copy(initial).lerp(high,lift);
    camera.position.x+=pointer.x*.35*(1-progress);
    camera.position.y+=pointer.y*.12*(1-progress);
    look.set(mobile?2.4:-2.6,mobile?3.0:.18,0).lerp(target.set(1.9,0,0),progress);
    camera.lookAt(look);renderer.render(scene,camera);
  }
  return {render,resize,canvas:renderer.domElement};
}
