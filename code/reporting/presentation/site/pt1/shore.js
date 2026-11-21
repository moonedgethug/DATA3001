import * as THREE from "three";
import { mesh } from "./objects.js?v=transitions3";

export function shoreHeight(x, z) {
  return (
    -0.16 +
    (z + 7) * 0.086 +
    0.045 * Math.sin(x * 0.72 + z * 0.4) +
    0.026 * Math.sin(z * 4.8 + x * 0.24)
  );
}
const material = (color, extra = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.9, ...extra });
function ellipsoid(parent, r, xyz, mat, scale = [1, 1, 1]) {
  const m = mesh(new THREE.SphereGeometry(r, 32, 24), mat, parent, xyz);
  m.scale.set(...scale);
  return m;
}
function limb(parent, a, b, r, mat) {
  const v = new THREE.Vector3(...a),
    w = new THREE.Vector3(...b),
    delta = w.clone().sub(v);
  const m = mesh(
    new THREE.CylinderGeometry(r, r * 0.72, delta.length(), 10),
    mat,
    parent,
    v.clone().add(w).multiplyScalar(0.5).toArray(),
  );
  m.quaternion.setFromUnitVectors(
    new THREE.Vector3(0, 1, 0),
    delta.normalize(),
  );
  return m;
}
function coconut(parent, x, z, half = false) {
  const shell = material("#705039", {
      bumpMap: grainTexture(),
      bumpScale: 0.07,
    }),
    g = new THREE.Group();
  parent.add(g);
  g.position.set(x, shoreHeight(x, z) + 0.34, z);
  g.rotation.set(0.2, 0.4, 0.16);
  if (!half) {
    ellipsoid(g, 0.49, [0, 0, 0], shell, [1, 0.86, 1.1]);
    for (const [a, b] of [
      [-0.12, 0.07],
      [0.12, 0.08],
      [0, -0.1],
    ])
      ellipsoid(g, 0.045, [a, 0.41, b], material("#2e271d"), [1, 0.18, 1]);
  } else {
    const bowl = mesh(
      new THREE.SphereGeometry(
        0.49,
        40,
        24,
        0,
        Math.PI * 2,
        Math.PI / 2,
        Math.PI / 2,
      ),
      shell,
      g,
    );
    bowl.rotation.x = 0.25;
    const flesh = mesh(
      new THREE.TorusGeometry(0.407, 0.064, 16, 56),
      material("#f4ebd2"),
      g,
      [0, 0.015, 0],
    );
    flesh.rotation.x = Math.PI / 2 + 0.25;
    const inside = mesh(
      new THREE.CircleGeometry(0.39, 48),
      material("#e9dfc1"),
      g,
      [0, -0.07, 0],
    );
    inside.rotation.x = -Math.PI / 2 + 0.25;
  }
}
function grainTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const x = c.getContext("2d");
  x.fillStyle = "#777";
  x.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 1800; i++) {
    const n = (Math.sin(i * 12.37) * 43758.5453) % 1;
    x.strokeStyle = i % 2 ? "#333" : "#aaa";
    x.beginPath();
    x.moveTo(Math.abs(n) * 256, i % 256);
    x.lineTo(Math.abs(n) * 256 + 22, (i % 256) + 6);
    x.stroke();
  }
  return new THREE.CanvasTexture(c);
}
function crab(parent) {
  const g = new THREE.Group();
  parent.add(g);
  const shell = material("#b66b3b", { roughness: 0.56 }),
    joint = material("#d39a63"),
    dark = material("#283b36");
  ellipsoid(g, 0.28, [0, 0.2, 0], shell, [1.4, 0.6, 1]);
  const legs = [];
  for (const side of [-1, 1])
    for (let i = 0; i < 4; i++) {
      const leg = new THREE.Group();
      g.add(leg);
      leg.position.set(side * 0.24, 0.17, (i - 1.5) * 0.12);
      limb(leg, [0, 0, 0], [side * 0.24, 0.06, 0.07], 0.024, shell);
      limb(
        leg,
        [side * 0.24, 0.06, 0.07],
        [side * 0.4, -0.15, 0.12],
        0.017,
        joint,
      );
      legs.push({ leg, side, index: i });
    }
  for (const side of [-1, 1]) {
    limb(g, [side * 0.18, 0.23, 0.18], [side * 0.29, 0.3, 0.44], 0.037, shell);
    const claw = ellipsoid(
      g,
      0.13,
      [side * 0.31, 0.32, 0.48],
      shell,
      [1, 0.8, 1.3],
    );
    claw.rotation.y = side * 0.4;
    limb(g, [side * 0.12, 0.29, 0.1], [side * 0.15, 0.42, 0.14], 0.019, joint);
    ellipsoid(g, 0.036, [side * 0.15, 0.43, 0.15], dark);
  }
  return { g, legs };
}
export async function createShore() {
  const g = new THREE.Group(),
    loader = new THREE.TextureLoader();
  const [color, normal, roughness, ao, height] = await Promise.all(
    ["color", "normal", "roughness", "ao", "height"].map((name) =>
      loader.loadAsync(`./assets/pt1/sand/${name}.jpg`),
    ),
  );
  for (const tex of [color, normal, roughness, ao, height]) {
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.repeat.set(12, 17);
    tex.anisotropy = 8;
  }
  color.colorSpace = THREE.SRGBColorSpace;
  const sand = material("#f5e4be", {
    map: color,
    normalMap: normal,
    normalScale: new THREE.Vector2(0.8, 0.8),
    roughnessMap: roughness,
    aoMap: ao,
    aoMapIntensity: 0.55,
    displacementMap: height,
    displacementScale: 0.055,
    displacementBias: -0.025,
  });
  const geometry = new THREE.PlaneGeometry(120, 170, 256, 256);
  geometry.rotateX(-Math.PI / 2);
  const p = geometry.attributes.position;
  for (let i = 0; i < p.count; i++)
    p.setY(i, shoreHeight(p.getX(i), p.getZ(i)));
  geometry.computeVertexNormals();
  const ground = mesh(geometry, sand, g);
  ground.castShadow = false;
  // Small grains catch grazing light close to the book; PBR maps carry distant detail.
  const grains = new THREE.InstancedMesh(
      new THREE.IcosahedronGeometry(0.022, 0),
      material("#ccb68a"),
      900,
    ),
    dummy = new THREE.Object3D();
  for (let i = 0; i < 900; i++) {
    const x = Math.sin(i * 19.27) * 12,
      z = 1 + ((i * 1.618) % 1) * 9;
    dummy.position.set(x, shoreHeight(x, z) + 0.015, z);
    dummy.scale.setScalar(0.6 + (i % 6) * 0.19);
    dummy.rotation.set(i, 0.4 * i, 0.2 * i);
    dummy.updateMatrix();
    grains.setMatrixAt(i, dummy.matrix);
  }
  grains.receiveShadow = true;
  g.add(grains);
  coconut(g, -7.7, 2.8);
  coconut(g, -6.7, 3.5, true);
  const animal = crab(g);
  // A soft contact patch grounds the book in addition to its directional cast shadow.
  const contactCanvas = document.createElement("canvas");
  contactCanvas.width = 512;
  contactCanvas.height = 128;
  const context = contactCanvas.getContext("2d");
  const grad = context.createRadialGradient(256, 64, 4, 256, 64, 250);
  grad.addColorStop(0, "rgba(39,31,18,.32)");
  grad.addColorStop(1, "rgba(39,31,18,0)");
  context.fillStyle = grad;
  context.fillRect(0, 0, 512, 128);
  const contact = mesh(
    new THREE.PlaneGeometry(14, 1.5),
    new THREE.MeshBasicMaterial({
      map: new THREE.CanvasTexture(contactCanvas),
      transparent: true,
      depthWrite: false,
    }),
    g,
    [0, shoreHeight(0, 0.5) + 0.07, 0.5],
  );
  contact.rotation.x = -Math.PI / 2;
  contact.castShadow = false;
  const foamGeometry = new THREE.PlaneGeometry(85, 15, 180, 50);
  foamGeometry.rotateX(-Math.PI / 2);
  const fp = foamGeometry.attributes.position;
  for (let i = 0; i < fp.count; i++)
    fp.setY(i, shoreHeight(fp.getX(i), fp.getZ(i)) + 0.065);
  const foamMaterial = new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 } },
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    vertexShader: `varying vec3 point;void main(){point=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `uniform float time;varying vec3 point;void main(){float front=-5.35+1.2*sin(time*.38)+.22*sin(point.x*.62+time*.4);float d=abs(point.z-front);float grain=fract(sin(dot(point.xz,vec2(127.1,311.7)))*43758.5453);float a=(1.0-smoothstep(.02,.48,d))*(.36+grain*.34);gl_FragColor=vec4(.91,.97,.93,a);}`,
  });
  const foam = mesh(foamGeometry, foamMaterial, g);
  foam.castShadow = false;
  return {
    group: g,
    update(time) {
      foamMaterial.uniforms.time.value = time;
      const x = 6.8 + 0.4 * Math.sin(time * 0.24),
        z = 3.2 + 0.18 * Math.sin(time * 0.35);
      animal.g.position.set(x, shoreHeight(x, z) + 0.02, z);
      animal.g.rotation.y = 0.7 + 0.15 * Math.sin(time * 0.24);
      animal.legs.forEach(({ leg, side, index }) => {
        leg.rotation.y =
          0.16 * Math.sin(time * 4 + index * Math.PI * 0.6 + side);
        leg.rotation.z = 0.08 * Math.sin(time * 4 + index);
      });
    },
  };
}
