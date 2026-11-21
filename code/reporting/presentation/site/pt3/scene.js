import * as THREE from "three";
import { Water } from "../assets/vendor/Water.js";
import { HDRLoader } from "../assets/vendor/HDRLoader.js";
import { glWave } from "../pt1/waves.js?v=transitions3";
const W = 1920,
  H = 1080,
  merc = (lat) =>
    (Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) * 180) / Math.PI;
const point = (lon, lat, y = 0.25) =>
  new THREE.Vector3((lon + 77) * 3, y, -(merc(lat) - merc(32.5)) * 3);
const smooth = (p) => p * p * p * (p * (p * 6 - 15) + 10),
  clamp = THREE.MathUtils.clamp;
function line(ring, color, y = 0.48, opacity = 1) {
  return new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(
      ring.map(([x, z]) => point(x, z, y)),
    ),
    new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity,
      depthWrite: false,
    }),
  );
}
function boundary(ring, color, width = 0.14) {
  const positions = [];
  for (let i = 1; i < ring.length; i++) {
    const a = point(...ring[i - 1], 0.62),
      b = point(...ring[i], 0.62),
      dx = b.x - a.x,
      dz = b.z - a.z,
      len = Math.hypot(dx, dz);
    if (!len) continue;
    const nx = ((-dz / len) * width) / 2,
      nz = ((dx / len) * width) / 2;
    for (const [x, z] of [
      [a.x + nx, a.z + nz],
      [a.x - nx, a.z - nz],
      [b.x - nx, b.z - nz],
      [a.x + nx, a.z + nz],
      [b.x - nx, b.z - nz],
      [b.x + nx, b.z + nz],
    ])
      positions.push(x, 0.62, z);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  return new THREE.Mesh(
    g,
    new THREE.MeshBasicMaterial({
      color,
      side: THREE.DoubleSide,
      transparent: true,
      depthWrite: false,
    }),
  );
}
function landGeometry(rings) {
  const coords = [];
  for (const ring of rings) {
    if (ring.length < 3) continue;
    const shape = new THREE.Shape();
    ring.forEach(([lon, lat], i) => {
      const p = point(lon, lat);
      i ? shape.lineTo(p.x, -p.z) : shape.moveTo(p.x, -p.z);
    });
    const g = new THREE.ShapeGeometry(shape).toNonIndexed(),
      a = g.attributes.position;
    for (let i = 0; i < a.count; i++) coords.push(a.getX(i), 0.12, -a.getY(i));
    g.dispose();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(coords, 3));
  g.computeVertexNormals();
  return g;
}
const palette = ["#34547a", "#488aab", "#81bfc1", "#d5db8a", "#ffe5a0"].map(
  (c) => new THREE.Color(c),
);
function colorAt(p) {
  const t = clamp(p, 0, 1) * 4,
    i = Math.min(3, Math.floor(t));
  return palette[i].clone().lerp(palette[i + 1], t - i);
}
function probabilityLayer(map) {
  const group = new THREE.Group();
  if (!map) return group;
  const pos = [],
    cols = [],
    max = map.maxProbability || Math.max(...map.cells.map((c) => c[2]));
  for (const [x, y, p] of map.cells) {
    if (!(p > 0)) continue;
    const a = point(x, y, 0.31),
      b = point(x + map.gridSize, y + map.gridSize, 0.31),
      color = colorAt(
        map.displayScale === "sqrt" ? Math.sqrt(p / max) : p / max,
      );
    for (const [xx, zz] of [
      [a.x, a.z],
      [b.x, a.z],
      [b.x, b.z],
      [a.x, a.z],
      [b.x, b.z],
      [a.x, b.z],
    ]) {
      pos.push(xx, 0.31, zz);
      cols.push(color.r, color.g, color.b);
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute("color", new THREE.Float32BufferAttribute(cols, 3));
  group.add(
    new THREE.Mesh(
      geo,
      new THREE.MeshBasicMaterial({
        vertexColors: true,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.96,
        depthWrite: false,
      }),
    ),
  );
  if (map.region90?.length > 2)
    group.add(boundary(map.region90, "#ffb2cb", 0.18));
  if (map.regionCells90?.length)
    for (const [x, y] of map.regionCells90) {
      const s = map.gridSize;
      group.add(
        boundary(
          [
            [x, y],
            [x + s, y],
            [x + s, y + s],
            [x, y + s],
            [x, y],
          ],
          "#ecacd1",
          0.09,
        ),
      );
    }
  const marker = (location, color, size, star = false) => {
    if (!location) return;
    const shape = new THREE.Shape();
    if (star) {
      for (let i = 0; i < 10; i++) {
        const a = (i * Math.PI) / 5 - Math.PI / 2,
          r = i % 2 ? size * 0.43 : size;
        i
          ? shape.lineTo(Math.cos(a) * r, Math.sin(a) * r)
          : shape.moveTo(Math.cos(a) * r, Math.sin(a) * r);
      }
      shape.closePath();
    } else shape.absarc(0, 0, size, 0, Math.PI * 2, false);
    const g = new THREE.ShapeGeometry(shape);
    g.rotateX(-Math.PI / 2);
    const obj = new THREE.Mesh(
      g,
      new THREE.MeshBasicMaterial({
        color,
        side: THREE.DoubleSide,
        depthTest: false,
      }),
    );
    obj.position.copy(point(...location, 0.8));
    obj.renderOrder = star ? 13 : 10;
    group.add(obj);
    if (star) {
      const border = new THREE.Mesh(
        g.clone(),
        new THREE.MeshBasicMaterial({
          color: "#073149",
          side: THREE.DoubleSide,
          depthTest: false,
        }),
      );
      border.scale.setScalar(1.28);
      border.position.copy(obj.position);
      border.renderOrder = 12;
      group.add(border);
    }
    if (!star) {
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(size * 0.95, size * 1.35, 32),
        new THREE.MeshBasicMaterial({
          color: "#073149",
          side: THREE.DoubleSide,
          depthTest: false,
        }),
      );
      ring.rotation.x = -Math.PI / 2;
      ring.position.copy(point(...location, 0.82));
      ring.renderOrder = 11;
      group.add(ring);
    }
  };
  marker(map.origin, "#ffffff", 0.36);
  marker(map.truth, "#f4aa4f", 0.65, true);
  return group;
}
export async function createWorld(host, geography, payload) {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    powerPreference: "high-performance",
  });
  renderer.setSize(W, H);
  renderer.setPixelRatio(1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.96;
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene(),
    camera = new THREE.PerspectiveCamera(43, W / H, 0.1, 12000),
    look = new THREE.Vector3(0, 3, -35);
  const [sky, normal] = await Promise.all([
    new HDRLoader().loadAsync("./assets/pt1/daylight-sky.hdr?v=2"),
    new THREE.TextureLoader().loadAsync("./assets/waternormals.jpg"),
  ]);
  sky.mapping = THREE.EquirectangularReflectionMapping;
  scene.background = sky;
  scene.backgroundRotation.y = 0.7;
  normal.wrapS = normal.wrapT = THREE.RepeatWrapping;
  const pm = new THREE.PMREMGenerator(renderer),
    env = pm.fromEquirectangular(sky);
  scene.environment = env.texture;
  pm.dispose();
  scene.add(new THREE.HemisphereLight("#ddf4ff", "#516a70", 2));
  const waterGeo = new THREE.PlaneGeometry(2, 2, 144, 144),
    a = waterGeo.attributes.position;
  for (let i = 0; i < a.count; i++)
    for (const axis of ["X", "Y"]) {
      const p = a["get" + axis](i);
      a["set" + axis](i, Math.sign(p) * Math.pow(Math.abs(p), 2.6) * 5000);
    }
  waterGeo.computeBoundingSphere();
  const water = new Water(waterGeo, {
    textureWidth: 256,
    textureHeight: 256,
    waterNormals: normal,
    sunDirection: new THREE.Vector3(-0.4, 0.8, 0.2),
    sunColor: "#fff4da",
    waterColor: "#1a627f",
    distortionScale: 0.3,
  });
  water.rotation.x = -Math.PI / 2;
  scene.add(water);
  const wm = water.material;
  wm.uniforms.waveScale = { value: 0.2 };
  wm.uniforms.size.value = 12;
  wm.vertexShader = wm.vertexShader
    .replace(
      "void main() {",
      `${glWave}\nuniform float waveScale;varying vec3 waveNormal;void main(){vec3 sampled=waveAt(vec2(position.x,-position.y),time)*waveScale;vec3 displaced=position+vec3(0.0,0.0,sampled.x);waveNormal=normalize(vec3(-sampled.y,1.0,-sampled.z));`,
    )
    .replaceAll("vec4( position, 1.0 )", "vec4( displaced, 1.0 )");
  wm.fragmentShader = wm.fragmentShader
    .replace("void main() {", "varying vec3 waveNormal;void main() {")
    .replace(
      "normalize( noise.xzy * vec3( 1.5, 1.0, 1.5 ) )",
      "normalize(waveNormal+vec3(noise.x*.4,0.0,noise.y*.4))",
    )
    .replace("float rf0 = 0.3;", "float rf0 = 0.045;")
    .replace(
      "sunColor * diffuseLight * 0.3 + scatter",
      "sunColor * diffuseLight * 0.025 + scatter * 1.4",
    )
    .replace(
      "vec3( 0.1 ) + reflectionSample * 0.9 + reflectionSample * specularLight",
      "reflectionSample * vec3(.25,.62,.95) + reflectionSample * specularLight * .4",
    );
  const map = new THREE.Group();
  scene.add(map);
  map.add(
    new THREE.Mesh(
      landGeometry(geography.land),
      new THREE.MeshBasicMaterial({
        color: "#e6dcc3",
        side: THREE.DoubleSide,
        transparent: true,
      }),
    ),
  );
  for (let lon = -90; lon <= -45; lon += 5)
    map.add(
      line(
        [
          [lon, 18],
          [lon, 48],
        ],
        "#b1d5d8",
        0.2,
        0.16,
      ),
    );
  for (let lat = 20; lat <= 45; lat += 5)
    map.add(
      line(
        [
          [-90, lat],
          [-45, lat],
        ],
        "#b1d5d8",
        0.2,
        0.16,
      ),
    );
  map.add(boundary(geography.region, "#9be4ce", 0.15));
  const layers = {};
  for (const [id, m] of Object.entries(payload.models)) {
    const g = probabilityLayer(m.map);
    g.visible = false;
    map.add(g);
    layers[id] = g;
  }
  const materials = [];
  map.traverse((o) => {
    if (o.material) {
      o.material.userData.baseOpacity = o.material.opacity;
      o.material.transparent = true;
      materials.push(o.material);
    }
  });
  // Full-frame refracted ceiling and volumetric light: one lightweight shader, no image/video loop.
  const subScene = new THREE.Scene(),
    subCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const subMaterial = new THREE.ShaderMaterial({
    transparent: true,
    depthTest: false,
    depthWrite: false,
    toneMapped: false,
    uniforms: {
      uTime: { value: 5 },
      uAlpha: { value: 1 },
      uNormal: { value: normal },
    },
    vertexShader:
      "varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}",
    fragmentShader: `
 varying vec2 vUv;uniform float uTime;uniform float uAlpha;uniform sampler2D uNormal;
 float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
 void main(){vec2 uv=vUv;float t=uTime*.055;float ceiling=smoothstep(.28,.97,uv.y);float depth=1.-uv.y;
 vec2 surface=vec2((uv.x-.56)*2.2/(.25+depth),.6/(.2+depth));
 vec3 n=texture2D(uNormal,surface*.48+vec2(t*.3,t*.15)).rgb;vec3 n2=texture2D(uNormal,surface*.96+vec2(-t*.14,t*.24)).rgb;
 float ridge=pow(clamp(1.-abs((n.r+n2.g)*1.3-1.15)*3.5,0.,1.),6.);
 float glint=pow(clamp(n.b*.6+n2.r*.5,0.,1.),9.);float sun=exp(-pow((uv.x-.73)*3.8,2.));
 vec3 col=mix(vec3(.005,.055,.12),vec3(.025,.29,.40),pow(uv.y,.7));
 col+=ceiling*(vec3(.15,.41,.49)*ridge*.6+vec3(.65,.83,.78)*glint*sun*1.8);
 float rays=0.;for(int i=0;i<7;i++){float f=float(i);float slope=(uv.x-(.56+f*.047+sin(t+f)*.008))/(1.05-uv.y+.22);float beam=exp(-pow((slope-(f-3.)*.19)*12.,2.));rays+=beam;}
 col+=vec3(.18,.44,.46)*rays*.16*smoothstep(.05,.8,uv.y)*(1.-ceiling*.7);
 col+=vec3(.35,.51,.44)*sun*pow(uv.y,7.)*.5;
 vec2 dust=uv*vec2(38.,23.)+vec2(t*.08,t*.5);vec2 cell=floor(dust),p=fract(dust);float rnd=hash(cell);float particle=exp(-dot((p-vec2(rnd,hash(cell+9.)))*vec2(140.,100.),(p-vec2(rnd,hash(cell+9.)))*vec2(140.,100.)));col+=particle*step(.73,rnd)*.23;
 col*=1.-.32*pow(abs(uv.x-.5)*1.5,2.);gl_FragColor=vec4(col,uAlpha);}`,
  });
  subScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), subMaterial));
  let playing = !matchMedia("(prefers-reduced-motion: reduce)").matches,
    time = 5,
    last = 0,
    draw = 0,
    flight = null,
    mode = "gallery",
    active = null,
    frameCount = 0,
    dirty = true;
  const history = [];
  let sub = 1,
    mapAlpha = 0;
  camera.position.set(0, -9, 25);
  camera.lookAt(look);
  const poseFor = (kind, id) => {
    if (kind === "gallery")
      return {
        pos: new THREE.Vector3(0, -9, 25),
        look: new THREE.Vector3(0, 3, -35),
        sub: 1,
        map: 0,
      };
    const peers = ["b1", "b2", "fixed", "adaptive"].includes(id)
      ? ["b1", "b2", "fixed", "adaptive"]
      : ["local-endpoint", "local-displacement"].includes(id)
        ? ["local-endpoint", "local-displacement"]
        : [
              "endpoint-ci",
              "local-gaussian",
              "local-gmm",
              "mdn1",
              "mdn22",
            ].includes(id)
          ? ["endpoint-ci", "local-gaussian", "local-gmm", "mdn1", "mdn22"]
          : [id];
    const coords = [...geography.region];
    for (const name of peers) {
      const m = payload.models[name]?.map;
      if (!m) continue;
      for (const [x, y] of m.cells)
        coords.push([x, y], [x + m.gridSize, y + m.gridSize]);
      if (m.region90) coords.push(...m.region90);
    }
    const ext =
        coords.length > geography.region.length
          ? [
              Math.min(...coords.map((p) => p[0])) - 1.2,
              Math.min(...coords.map((p) => p[1])) - 1.2,
              Math.max(...coords.map((p) => p[0])) + 1.2,
              Math.max(...coords.map((p) => p[1])) + 1.2,
            ]
          : [-83, 25, -64, 40],
      a = point(ext[0], ext[1]),
      b = point(ext[2], ext[3]),
      w = b.x - a.x,
      h = a.z - b.z,
      fullH = Math.max(h / 0.62, w / 0.57 / (W / H)),
      center = new THREE.Vector3(
        (a.x + b.x) / 2 + fullH * (W / H) * 0.175,
        0,
        (a.z + b.z) / 2 + fullH * 0.025,
      );
    return {
      pos: center
        .clone()
        .add(
          new THREE.Vector3(
            0,
            fullH / (2 * Math.tan((43 * Math.PI) / 360)),
            fullH * 0.06,
          ),
        ),
      look: center,
      sub: 0,
      map: 1,
    };
  };
  function setMap(id) {
    active = id;
    for (const [k, g] of Object.entries(layers)) g.visible = k === id;
  }
  function fly(kind, id, { immediate = false, intro = false } = {}) {
    const fromId = active;
    active = id;
    mode = kind;
    dirty = true;
    const to = poseFor(kind, id);
    if (intro) {
      camera.position.set(0, 2.5, 25);
      look.set(0, 1, -35);
      sub = 0;
      mapAlpha = 0;
    }
    return new Promise((resolve) => {
      flight = {
        fromId,
        fromPos: camera.position.clone(),
        fromLook: look.clone(),
        fromSub: sub,
        fromMap: mapAlpha,
        to,
        at: performance.now(),
        duration:
          immediate || !playing
            ? 0
            : intro
              ? 2400
              : kind === "gallery"
                ? 2300
                : sub > 0.5
                  ? 2900
                  : 600,
        resolve,
        spans: [],
        last: 0,
      };
    });
  }
  function project(loc) {
    const p = point(...loc, 0.9).project(camera);
    return { x: ((p.x + 1) * W) / 2, y: ((1 - p.y) * H) / 2 };
  }
  function frame(stamp) {
    requestAnimationFrame(frame);
    const dt = Math.min((stamp - last) / 1000 || 0, 0.05);
    last = stamp;
    if (document.hidden) return;
    if (!playing && !flight && !dirty) return;
    if (playing) time += dt;
    if (stamp - draw < 1000 / 60 && !dirty) return;
    draw = stamp - ((stamp - draw) % (1000 / 60));
    dirty = false;
    let p = 1;
    if (flight) {
      p = flight.duration
        ? clamp((stamp - flight.at) / flight.duration, 0, 1)
        : 1;
      const e = smooth(p);
      camera.position.lerpVectors(flight.fromPos, flight.to.pos, e);
      look.lerpVectors(flight.fromLook, flight.to.look, e);
      sub = THREE.MathUtils.lerp(flight.fromSub, flight.to.sub, e);
      mapAlpha = THREE.MathUtils.lerp(
        flight.fromMap,
        flight.to.map,
        smooth(clamp((p - 0.22) / 0.78, 0, 1)),
      );
      if (flight.last) flight.spans.push(stamp - flight.last);
      flight.last = stamp;
    }
    camera.lookAt(look);
    camera.near = Math.max(0.1, camera.position.y * 0.01);
    camera.updateProjectionMatrix();
    wm.uniforms.time.value = time * 0.7;
    wm.uniforms.waveScale.value = 0.04 + 0.26 * sub;
    wm.uniforms.size.value = 0.8 + 15 * sub;
    map.visible = mapAlpha > 0.001;
    materials.forEach((m) => (m.opacity = m.userData.baseOpacity * mapAlpha));
    for (const [id, g] of Object.entries(layers)) {
      const changing = flight && flight.fromId !== active;
      const alpha =
        id === active
          ? changing
            ? smooth(clamp((p - 0.45) / 0.5, 0, 1))
            : 1
          : id === flight?.fromId
            ? 1 - smooth(clamp(p / 0.45, 0, 1))
            : 0;
      g.visible = alpha > 0.001;
      g.traverse((o) => {
        if (o.material)
          o.material.opacity =
            o.material.userData.baseOpacity * mapAlpha * alpha;
      });
    }
    if (sub < 0.999) {
      renderer.autoClear = true;
      renderer.render(scene, camera);
    } else {
      renderer.setClearColor("#052d40");
      renderer.clear();
    }
    if (sub > 0.001) {
      renderer.autoClear = false;
      subMaterial.uniforms.uTime.value = time;
      subMaterial.uniforms.uAlpha.value = sub;
      renderer.render(subScene, subCamera);
    }
    renderer.autoClear = true;
    const canvas = renderer.domElement;
    canvas.dataset.renderFrame = ++frameCount;
    canvas.dataset.cameraMoving = String(p < 1);
    canvas.dataset.progress = p.toFixed(3);
    canvas.dataset.mode = mode;
    canvas.dataset.model = active || "";
    if (flight && p === 1) {
      const f = flight;
      flight = null;
      const a = f.spans.sort((a, b) => a - b);
      if (a.length) {
        history.push({
          to: mode,
          model: active,
          frames: a.length,
          meanMs: Math.round(a.reduce((a, b) => a + b) / a.length),
          p95Ms: Math.round(a[Math.floor(a.length * 0.95)]),
          maxMs: Math.round(a.at(-1)),
        });
        canvas.dataset.transitionHistory = JSON.stringify(history.slice(-12));
      }
      f.resolve();
    }
  }
  // Warm water, map geometry and overlay shaders before interactive travel.
  for (const g of Object.values(layers)) g.visible = true;
  map.visible = true;
  const pose = poseFor("detail", "b2");
  camera.position.copy(pose.pos);
  camera.lookAt(pose.look);
  await renderer.compileAsync(scene, camera);
  renderer.render(scene, camera);
  renderer.autoClear = false;
  renderer.render(subScene, subCamera);
  renderer.autoClear = true;
  renderer.getContext().finish();
  Object.values(layers).forEach((g) => (g.visible = false));
  camera.position.set(0, -9, 25);
  look.set(0, 3, -35);
  requestAnimationFrame(frame);
  return {
    fly,
    project,
    setMap,
    isPlaying: () => playing,
    toggle() {
      playing = !playing;
      dirty = true;
      if (!playing && flight) flight.duration = 0;
      return playing;
    },
    canvas: renderer.domElement,
  };
}
