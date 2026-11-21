import * as THREE from "three";
import { makeBuoy, mesh } from "../pt1/objects.js?v=transitions3";
const mat = (color, extra = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.6, ...extra });
function rod(g, a, b, r, material) {
  const p = new THREE.Vector3(...a),
    q = new THREE.Vector3(...b),
    d = q.clone().sub(p);
  const o = mesh(
    new THREE.CylinderGeometry(r, r, d.length(), 12),
    material,
    g,
    p.clone().add(q).multiplyScalar(0.5).toArray(),
  );
  o.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize());
  return o;
}
export function makeDrifter() {
  const group = new THREE.Group(),
    buoy = makeBuoy();
  buoy.scale.setScalar(1);
  group.add(buoy);
  const metal = mat("#cfdddd", { metalness: 0.75, roughness: 0.26 }),
    rope = mat("#d1c6a3");
  rod(group, [0, -0.35, 0], [0, -3.1, 0], 0.028, rope);
  const drogue = new THREE.Group();
  drogue.position.y = -5.1;
  group.add(drogue);
  const alpha = document.createElement("canvas");
  alpha.width = 512;
  alpha.height = 1024;
  const c = alpha.getContext("2d");
  c.fillStyle = "white";
  c.fillRect(0, 0, 512, 1024);
  c.fillStyle = "black";
  for (let row = 0; row < 4; row++)
    for (let col = 0; col < 4; col++) {
      c.beginPath();
      c.ellipse(
        64 + col * 128 + (row % 2 ? 32 : 0),
        128 + row * 256,
        35,
        55,
        0,
        0,
        Math.PI * 2,
      );
      c.fill();
    }
  const mask = new THREE.CanvasTexture(alpha);
  const cloth = mat("#315d70", {
    alphaMap: mask,
    alphaTest: 0.5,
    side: THREE.DoubleSide,
    roughness: 0.93,
  });
  mesh(
    new THREE.CylinderGeometry(0.69, 0.69, 4.05, 64, 8, true),
    cloth,
    drogue,
  );
  for (const y of [-2, -1, 0, 1, 2]) {
    const ring = mesh(
      new THREE.TorusGeometry(0.69, 0.025, 8, 48),
      metal,
      drogue,
      [0, y, 0],
    );
    ring.rotation.x = Math.PI / 2;
  }
  for (const x of [-0.49, 0.49])
    rod(group, [0, -2.6, 0], [x, -3.1, x], 0.018, rope);
  const thermo = new THREE.Group();
  thermo.position.set(2.3, 0.25, 0);
  group.add(thermo);
  mesh(
    new THREE.SphereGeometry(0.13, 20, 16),
    mat("#df8d5a"),
    thermo,
    [0, 0.05, 0],
  );
  rod(thermo, [0, 0.1, 0], [0, 1.15, 0], 0.045, metal);
  rod(thermo, [0, 0.1, 0.05], [0, 0.85, 0.05], 0.022, mat("#df8d5a"));
  const axes = new THREE.Group();
  axes.position.set(0, 0.45, 0);
  group.add(axes);
  const east = new THREE.ArrowHelper(
    new THREE.Vector3(1, 0, 0),
    new THREE.Vector3(0, 0, 0),
    4.2,
    0xf4ca7f,
    0.55,
    0.25,
  );
  const north = new THREE.ArrowHelper(
    new THREE.Vector3(0, 0, -1),
    new THREE.Vector3(0, 0, 0),
    4.2,
    0x80ded1,
    0.55,
    0.25,
  );
  axes.add(east, north);
  const anchors = {
    drogue: new THREE.Vector3(0.65, -5, 0),
    sst: new THREE.Vector3(2.3, 0.9, 0),
    motion: new THREE.Vector3(3, 0.45, 0),
    lifecycle: new THREE.Vector3(0, 0.6, 0),
    east: new THREE.Vector3(4.5, 0.45, 0),
    north: new THREE.Vector3(0, 0.45, -4.6),
  };
  return {
    group,
    anchors,
    update(t, focus) {
      group.position.y = Math.sin(t * 0.9) * 0.09;
      group.rotation.z = Math.sin(t * 0.7) * 0.022;
      drogue.rotation.z = Math.sin(t * 0.58 - 0.4) * 0.04;
      cloth.color.set(focus === 0 ? "#17465b" : "#244e60");
      axes.visible = focus === 2;
      thermo.visible = focus === 1;
    },
  };
}
export function underwaterContext() {
  const g = new THREE.Group();
  const wallMat = new THREE.ShaderMaterial({
    uniforms: { t: { value: 0 } },
    side: THREE.DoubleSide,
    vertexShader: `varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `#include <common>
varying vec2 vUv;uniform float t;void main(){
#include <clipping_planes_fragment>
vec3 c=mix(vec3(.01,.035,.07),vec3(.025,.18,.27),pow(vUv.y,2.0));float ray=pow(max(0.,sin(vUv.x*85.+vUv.y*9.+t*.15)),14.)*.023*vUv.y;gl_FragColor=vec4(c+ray,1.);
#include <tonemapping_fragment>
#include <colorspace_fragment>
}`,
  });
  const wall = mesh(
    new THREE.PlaneGeometry(240, 30),
    wallMat,
    g,
    [0, -15, -1.4],
  );
  const positions = new Float32Array(180 * 3);
  let seed = 23;
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  for (let i = 0; i < 180; i++) {
    positions[i * 3] = (random() - 0.5) * 21;
    positions[i * 3 + 1] = -random() * 12;
    positions[i * 3 + 2] = (random() - 0.5) * 8;
  }
  const points = new THREE.Points(
    new THREE.BufferGeometry().setAttribute(
      "position",
      new THREE.BufferAttribute(positions, 3),
    ),
    new THREE.PointsMaterial({
      color: "#bcf2f2",
      size: 0.025,
      transparent: true,
      opacity: 0.45,
    }),
  );
  g.add(points);
  for (const x of [-5, 1, 6]) {
    const ray = mesh(
      new THREE.PlaneGeometry(0.9, 13),
      new THREE.MeshBasicMaterial({
        color: "#b9e8ed",
        transparent: true,
        opacity: 0.035,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
      g,
      [x, -6, -3],
    );
    ray.rotation.z = -0.21;
  }
  return {
    group: g,
    update(t) {
      points.position.y = Math.sin(t * 0.12) * 0.15;
      wallMat.uniforms.t.value = t;
    },
  };
}
