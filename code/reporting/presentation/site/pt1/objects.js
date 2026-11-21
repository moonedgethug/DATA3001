import * as THREE from "three";
const textureCache = new Map();
function rng(seed = 7) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function texture(kind) {
  if (textureCache.has(kind)) return textureCache.get(kind);
  const c = document.createElement("canvas");
  c.width = c.height = 1024;
  const ctx = c.getContext("2d"),
    rand = rng(kind.length * 61);
  ctx.fillStyle =
    { sand: "#e4d4ad", wood: "#827056", cloth: "#253e44", cork: "#9f8159" }[
      kind
    ] || "#eee3c5";
  ctx.fillRect(0, 0, 1024, 1024);
  if (kind === "wood") {
    for (let i = 0; i < 700; i++) {
      ctx.strokeStyle = `rgba(${rand() > 0.5 ? "34,27,16" : "186,161,117"},${rand() * 0.25})`;
      ctx.lineWidth = rand() * 3 + 0.4;
      const y = rand() * 1024;
      ctx.beginPath();
      ctx.moveTo(0, y);
      for (let x = 0; x <= 1024; x += 24)
        ctx.lineTo(x, y + Math.sin(x / 110 + i) * rand() * 9);
      ctx.stroke();
    }
  } else {
    for (let i = 0; i < 115000; i++) {
      const v = rand() > 0.5 ? "255,250,225" : "74,51,32";
      ctx.fillStyle = `rgba(${v},${rand() * (kind === "sand" ? 0.2 : 0.13)})`;
      const z = rand() * 1.8 + 0.3;
      ctx.fillRect(rand() * 1024, rand() * 1024, z, z);
    }
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  textureCache.set(kind, t);
  return t;
}
export function mesh(geo, mat, parent, pos = [0, 0, 0]) {
  const m = new THREE.Mesh(geo, mat);
  m.position.set(...pos);
  m.castShadow = true;
  m.receiveShadow = true;
  parent?.add(m);
  return m;
}
const standard = (color, extra = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.65, ...extra });
function box(parent, size, pos, mat) {
  return mesh(new THREE.BoxGeometry(...size), mat, parent, pos);
}
function rod(parent, a, b, r, mat) {
  const av = new THREE.Vector3(...a),
    bv = new THREE.Vector3(...b),
    d = bv.clone().sub(av);
  const m = mesh(
    new THREE.CylinderGeometry(r, r, d.length(), 12),
    mat,
    parent,
    av.clone().add(bv).multiplyScalar(0.5).toArray(),
  );
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize());
  return m;
}
function sphere(parent, r, pos, mat, scale = [1, 1, 1]) {
  const m = mesh(new THREE.SphereGeometry(r, 32, 24), mat, parent, pos);
  m.scale.set(...scale);
  return m;
}
export function makeBuoy() {
  const g = new THREE.Group(),
    orange = standard("#ec8a33", { roughness: 0.29, metalness: 0.12 }),
    ivory = standard("#e9e6d3", { roughness: 0.38 }),
    rubber = standard("#1c3541"),
    metal = standard("#cedbdc", { metalness: 0.88, roughness: 0.23 });
  sphere(g, 0.76, [0, 0.12, 0], orange, [1, 0.72, 1]);
  const ring = mesh(
    new THREE.TorusGeometry(0.726, 0.05, 18, 90),
    rubber,
    g,
    [0, 0.12, 0],
  );
  ring.rotation.x = Math.PI / 2;
  mesh(
    new THREE.CylinderGeometry(0.51, 0.61, 0.16, 64),
    ivory,
    g,
    [0, 0.55, 0],
  );
  mesh(
    new THREE.CylinderGeometry(0.15, 0.24, 0.3, 48),
    orange,
    g,
    [0, 0.76, 0],
  );
  rod(g, [0, 0.85, 0], [0, 2.02, 0], 0.025, metal);
  mesh(
    new THREE.CylinderGeometry(0.06, 0.06, 0.31, 16),
    rubber,
    g,
    [0, 1.94, 0],
  );
  sphere(g, 0.064, [0, 2.11, 0], ivory);
  for (let i = 0; i < 8; i++) {
    const a = (i * Math.PI) / 4;
    mesh(new THREE.CylinderGeometry(0.026, 0.026, 0.024, 12), metal, g, [
      Math.cos(a) * 0.42,
      0.64,
      Math.sin(a) * 0.42,
    ]);
  }
  const c = document.createElement("canvas");
  c.width = 512;
  c.height = 256;
  const x = c.getContext("2d");
  x.fillStyle = "#ece7d3";
  x.fillRect(0, 0, 512, 256);
  x.fillStyle = "#243f46";
  x.textAlign = "center";
  x.font = "600 52px Arial";
  x.fillText("DRIFTER", 256, 108);
  x.font = "30px Arial";
  x.fillText("WHERE THINGS END UP", 256, 162);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  const label = mesh(
    new THREE.PlaneGeometry(0.54, 0.27),
    new THREE.MeshStandardMaterial({ map: t, roughness: 0.5 }),
    g,
    [0.12, 0.28, 0.714],
  );
  label.rotation.y = 0.16;
  g.scale.setScalar(1.2);
  return g;
}
export function makeBottle() {
  const g = new THREE.Group();
  const profile = [
    [0, 0],
    [0.36, 0],
    [0.51, 0.12],
    [0.55, 0.32],
    [0.55, 1.75],
    [0.52, 1.96],
    [0.34, 2.18],
    [0.2, 2.32],
    [0.2, 2.87],
    [0.24, 2.9],
    [0.24, 3.04],
    [0.17, 3.04],
    [0.17, 2.37],
    [0.31, 2.2],
    [0.48, 1.94],
    [0.51, 1.75],
    [0.51, 0.27],
    [0.34, 0.09],
    [0, 0.09],
  ].map(([x, y]) => new THREE.Vector2(x, y));
  const glass = new THREE.MeshPhysicalMaterial({
    color: "#c9e3d7",
    metalness: 0,
    roughness: 0.065,
    transmission: 1,
    thickness: 0.12,
    ior: 1.46,
    attenuationColor: new THREE.Color("#8eb5a0"),
    attenuationDistance: 2.8,
    transparent: true,
    opacity: 1,
    side: THREE.DoubleSide,
  });
  mesh(new THREE.LatheGeometry(profile, 96), glass, g);
  const lip = mesh(
    new THREE.TorusGeometry(0.205, 0.038, 16, 64),
    glass,
    g,
    [0, 2.94, 0],
  );
  lip.rotation.x = Math.PI / 2;
  const cork = mesh(
    new THREE.CylinderGeometry(0.177, 0.168, 0.3, 32),
    standard("#c4a87a", { map: texture("cork") }),
    g,
    [-0.5, 3.25, 0.13],
  );
  cork.rotation.z = -0.45;
  g.userData.cork = cork;
  g.rotation.set(0.16, 0, -0.82);
  g.scale.setScalar(1.75);
  return g;
}
function pageTexture(side) {
  const c = document.createElement("canvas");
  c.width = 1024;
  c.height = 1024;
  const x = c.getContext("2d");
  x.drawImage(texture("paper").image, 0, 0, 1024, 1024);
  const gradient = x.createLinearGradient(0, 0, 1024, 0);
  gradient.addColorStop(side === "left" ? 0 : 1, "rgba(100,77,42,.08)");
  gradient.addColorStop(0.5, "rgba(100,77,42,0)");
  gradient.addColorStop(side === "left" ? 1 : 0, "rgba(71,47,20,.18)");
  x.fillStyle = gradient;
  x.fillRect(0, 0, 1024, 1024);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 16;
  return t;
}
export function makeBook() {
  const g = new THREE.Group(),
    cover = standard("#375859", { map: texture("cloth"), roughness: 0.94 });
  const pages = standard("#dfd5b9", { roughness: 0.95 }),
    pageWidth = 7.25,
    pageHeight = 7.2;
  g.userData.pages = [];
  for (const side of [-1, 1]) {
    const leaf = new THREE.Group();
    g.add(leaf);
    leaf.position.x = side * 3.695;
    leaf.rotation.y = side * 0.045;
    box(leaf, [7.49, 7.42, 0.15], [0, 3.69, -0.18], cover);
    box(leaf, [pageWidth, pageHeight, 0.22], [0, 3.7, 0], pages);
    const geometry = new THREE.PlaneGeometry(pageWidth, pageHeight, 64, 12),
      p = geometry.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const u = (p.getX(i) + pageWidth / 2) / pageWidth,
        inner = side < 0 ? u : 1 - u;
      p.setZ(
        i,
        0.14 + 0.12 * Math.pow(inner, 10) + 0.04 * Math.pow(1 - inner, 9),
      );
    }
    geometry.computeVertexNormals();
    const page = mesh(
      geometry,
      standard("#fffdf3", {
        map: pageTexture(side < 0 ? "left" : "right"),
        roughness: 0.95,
      }),
      leaf,
      [0, 3.7, 0.04],
    );
    g.userData.pages.push(page);
    for (let j = 0; j < 12; j++) {
      const z = -0.1 + j * 0.019,
        points = [
          new THREE.Vector3(-3.625, 0.1, z),
          new THREE.Vector3(3.625, 0.1, z),
          new THREE.Vector3(3.625, 7.3, z),
        ];
      leaf.add(
        new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(points),
          new THREE.LineBasicMaterial({
            color: "#9e9278",
            transparent: true,
            opacity: 0.32,
          }),
        ),
      );
    }
  }
  mesh(
    new THREE.CylinderGeometry(0.17, 0.17, 7.4, 24),
    cover,
    g,
    [0, 3.7, -0.18],
  );
  const ribbon = box(
    g,
    [0.085, 1.25, 0.025],
    [0.15, 0.05, 0.22],
    standard("#b28a4c"),
  );
  ribbon.rotation.z = -0.1;
  g.rotation.set(-0.045, -0.045, -0.018);
  return g;
}
function person(parent, x, z, scale, shirt, hair) {
  const g = new THREE.Group();
  parent.add(g);
  g.position.set(x, 0.3, z);
  g.scale.setScalar(scale);
  const skin = standard("#bd8d6a"),
    cloth = standard(shirt),
    pants = standard("#253b4a"),
    vest = standard("#d87932"),
    hairMat = standard(hair);
  sphere(g, 0.17, [0, 1.21, 0], skin, [0.9, 1.12, 0.9]);
  sphere(g, 0.173, [0, 1.29, -0.025], hairMat, [0.95, 0.74, 0.91]);
  mesh(new THREE.CapsuleGeometry(0.2, 0.36, 8, 24), cloth, g, [0, 0.79, 0]);
  box(g, [0.39, 0.4, 0.13], [0, 0.81, 0.16], vest);
  rod(g, [-0.17, 0.96, 0], [-0.32, 0.65, 0.15], 0.073, cloth);
  rod(g, [-0.32, 0.65, 0.15], [-0.27, 0.51, 0.39], 0.055, skin);
  rod(g, [0.17, 0.96, 0], [0.31, 0.68, 0.12], 0.073, cloth);
  rod(g, [0.31, 0.68, 0.12], [0.21, 0.52, 0.39], 0.055, skin);
  for (const side of [-1, 1]) {
    rod(g, [side * 0.11, 0.52, 0], [side * 0.19, 0.35, 0.38], 0.1, pants);
    rod(g, [side * 0.19, 0.35, 0.38], [side * 0.2, 0.14, 0.61], 0.075, pants);
    sphere(
      g,
      0.1,
      [side * 0.2, 0.12, 0.7],
      standard("#263332"),
      [0.8, 0.5, 1.4],
    );
  }
  g.rotation.y = -0.25;
  return g;
}
export function makeRaft() {
  const g = new THREE.Group(),
    wood = standard("#a39577", { map: texture("wood"), roughness: 0.95 }),
    rope = standard("#b8a47a");
  for (let i = 0; i < 9; i++) {
    const log = mesh(
      new THREE.CylinderGeometry(0.16, 0.18, 3.9 + (i % 3) * 0.12, 16),
      wood,
      g,
      [0, -0.02, (i - 4) * 0.34],
    );
    log.rotation.z = Math.PI / 2;
  }
  for (const x of [-1.25, 1.25])
    for (const z of [-1.25, 1.25]) {
      const r = mesh(new THREE.TorusGeometry(0.22, 0.025, 8, 36), rope, g, [
        x,
        0,
        z,
      ]);
      r.rotation.x = Math.PI / 2;
    }
  person(g, -0.74, -0.25, 1.15, "#ece8d9", "#554033");
  person(g, 0.55, -0.3, 1.05, "#aec9ce", "#302c29");
  person(g, -0.06, 0.68, 0.72, "#e9c67a", "#4b352b");
  rod(g, [1.7, 0.15, -1.0], [2.1, 0.12, 1.35], 0.04, wood);
  box(g, [0.34, 0.045, 0.76], [2.05, 0.11, 1.19], wood);
  return g;
}
function container(color) {
  const g = new THREE.Group(),
    mat = standard(color, { roughness: 0.62, metalness: 0.35 }),
    rim = standard("#bcc7be", { roughness: 0.48, metalness: 0.6 });
  box(g, [2.6, 1.15, 1.08], [0, 0.0, 0], mat);
  for (let x = -1.2; x <= 1.2; x += 0.13) {
    box(g, [0.035, 1.08, 0.035], [x, 0, 0.56], mat);
    box(g, [0.035, 1.08, 0.035], [x, 0, -0.56], mat);
    box(g, [0.035, 0.035, 1.03], [x, 0.59, 0], mat);
  }
  for (const x of [-1.3, 1.3]) {
    box(g, [0.05, 1.21, 1.15], [x, 0, 0], rim);
    for (const z of [-0.3, 0.3])
      rod(g, [x * 1.01, -0.49, z], [x * 1.01, 0.49, z], 0.018, rim);
  }
  return g;
}
export function makeCargo() {
  const g = new THREE.Group();
  [
    ["#a65c39", -1.2, 0.1, 0.3, -0.17, 0.18],
    ["#718e83", 1.45, -0.13, -1.5, 0.12, -0.4],
    ["#ceb98b", 0.2, -0.32, -4.1, -0.1, 0.4],
  ].forEach(([c, x, y, z, rz, ry]) => {
    const item = container(c);
    item.position.set(x, y, z);
    item.rotation.set(0.08, ry, rz);
    g.add(item);
  });
  return g;
}
export function makeSlick() {
  const g = new THREE.Group(),
    c = document.createElement("canvas");
  c.width = c.height = 1024;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, 1024, 1024);
  // A continuous subdivided film avoids the boundary-only triangles of ShapeGeometry.
  const image = ctx.createImageData(1024, 1024);
  for (let y = 0; y < 1024; y++)
    for (let x = 0; x < 1024; x++) {
      const u = (x - 512) / 370,
        v = (y - 512) / 410,
        a = Math.atan2(v, u),
        r = Math.hypot(u, v),
        edge =
          1 +
          0.12 * Math.sin(a * 5) +
          0.08 * Math.sin(a * 9 + 1.3) +
          0.025 * Math.sin(x * 0.08 + y * 0.055);
      const density = Math.max(0, Math.min(1, (edge - r) * 10));
      const noise =
        0.91 + 0.08 * Math.sin(x * 0.017 + y * 0.031) * Math.sin(y * 0.019);
      const k = (y * 1024 + x) * 4;
      image.data[k] =
        image.data[k + 1] =
        image.data[k + 2] =
          density * noise * 255;
      image.data[k + 3] = 255;
    }
  ctx.putImageData(image, 0, 0);
  const alpha = new THREE.CanvasTexture(c),
    geo = new THREE.PlaneGeometry(14, 20, 160, 200);
  geo.rotateX(-Math.PI / 2);
  const oil = new THREE.MeshPhysicalMaterial({
    color: "#071e1a",
    roughness: 0.27,
    metalness: 0.1,
    transparent: true,
    opacity: 0.91,
    alphaMap: alpha,
    depthWrite: false,
    iridescence: 0.4,
    iridescenceIOR: 1.3,
    side: THREE.DoubleSide,
  });
  mesh(geo, oil, g, [0.5, 0, -2.0]);
  return g;
}
