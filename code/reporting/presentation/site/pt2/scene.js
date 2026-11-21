import * as THREE from "three";
import { Water } from "../assets/vendor/Water.js";
import { HDRLoader } from "../assets/vendor/HDRLoader.js";
import { glWave } from "../pt1/waves.js?v=transitions3";
import { makeDrifter, underwaterContext } from "./objects.js?v=p2v1";
const W = 1920,
  H = 1080;
const merc = (lat) =>
  (Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) * 180) / Math.PI;
export const point = (lon, lat, y = 0.35) =>
  new THREE.Vector3((lon + 77) * 3, y, -(merc(lat) - merc(32.5)) * 3);
const smooth = (p) => p * p * p * (p * (p * 6 - 15) + 10);
const between = (p, a, b) =>
  smooth(THREE.MathUtils.clamp((p - a) / (b - a), 0, 1));
function polygon(ring, color, opacity = 0.22) {
  const g = new THREE.Group(),
    s = new THREE.Shape();
  ring.forEach(([x, y], i) => {
    const p = point(x, y);
    i ? s.lineTo(p.x, -p.z) : s.moveTo(p.x, -p.z);
  });
  const fill = new THREE.Mesh(
    new THREE.ShapeGeometry(s),
    new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity,
      depthWrite: false,
      side: THREE.DoubleSide,
    }),
  );
  fill.rotation.x = -Math.PI / 2;
  fill.position.y = 0.3;
  g.add(fill);
  const line = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(
      ring.map(([x, y]) => point(x, y, 0.45)),
    ),
    new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.95 }),
  );
  g.add(line);
  return g;
}
function landGeometry(rings) {
  const coords = [];
  for (const ring of rings) {
    if (ring.length < 3) continue;
    const s = new THREE.Shape();
    ring.forEach(([lon, lat], i) => {
      const p = point(lon, lat);
      i ? s.lineTo(p.x, -p.z) : s.moveTo(p.x, -p.z);
    });
    const geo = new THREE.ShapeGeometry(s).toNonIndexed();
    const a = geo.attributes.position;
    for (let i = 0; i < a.count; i++) coords.push(a.getX(i), 0.13, -a.getY(i));
    geo.dispose();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(coords, 3));
  g.computeVertexNormals();
  return g;
}
function fadeGroup(group) {
  const uniforms = [];
  const seen = new Set();
  group.traverse((o) => {
    if (!o.material) return;
    for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
      if (seen.has(m)) continue;
      seen.add(m);
      const u = { value: 1 };
      uniforms.push(u);
      const old = m.onBeforeCompile,
        key = m.customProgramCacheKey();
      m.onBeforeCompile = function (shader, renderer) {
        old.call(this, shader, renderer);
        shader.uniforms.sceneVisibility = u;
        shader.fragmentShader = shader.fragmentShader
          .replace(
            "#include <common>",
            "#include <common>\nuniform float sceneVisibility;",
          )
          .replace(
            "#include <clipping_planes_fragment>",
            "#include <clipping_planes_fragment>\nif(sceneVisibility<1.0 && fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233)))*43758.5453)>sceneVisibility) discard;",
          );
      };
      m.customProgramCacheKey = () => key + ":p2-fade";
      m.needsUpdate = true;
    }
  });
  return (v) => {
    group.visible = v > 0.001;
    uniforms.forEach((u) => (u.value = v));
  };
}
export async function createStage(host, data, onFrame, onSettled) {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    powerPreference: "high-performance",
  });
  renderer.setSize(W, H);
  renderer.setPixelRatio(1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.94;
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene(),
    camera = new THREE.PerspectiveCamera(43, W / H, 0.1, 14000);
  const sky = await new HDRLoader().loadAsync(
    "./assets/pt1/daylight-sky.hdr?v=2",
  );
  sky.mapping = THREE.EquirectangularReflectionMapping;
  scene.background = sky;
  scene.backgroundRotation.y = 0.7;
  scene.backgroundIntensity = 1;
  const pm = new THREE.PMREMGenerator(renderer);
  const env = pm.fromEquirectangular(sky);
  scene.environment = env.texture;
  scene.environmentIntensity = 0.65;
  pm.dispose();
  scene.add(new THREE.HemisphereLight("#deefff", "#8ba2a7", 2));
  const sun = new THREE.DirectionalLight("#fff7e8", 3);
  sun.position.set(-16, 26, 12);
  scene.add(sun);
  const front = new THREE.DirectionalLight("#d1f5ff", 1.8);
  front.position.set(10, 3, 20);
  scene.add(front);
  const normal = await new THREE.TextureLoader().loadAsync(
    "./assets/waternormals.jpg",
  );
  normal.wrapS = normal.wrapT = THREE.RepeatWrapping;
  const waterGeo = new THREE.PlaneGeometry(2, 2, 192, 192),
    wv = waterGeo.attributes.position;
  for (let i = 0; i < wv.count; i++) {
    for (const axis of ["X", "Y"]) {
      const p = wv["get" + axis](i);
      wv["set" + axis](i, Math.sign(p) * Math.pow(Math.abs(p), 2.7) * 6500);
    }
  }
  waterGeo.computeBoundingSphere();
  const water = new Water(waterGeo, {
    textureWidth: 256,
    textureHeight: 256,
    waterNormals: normal,
    sunDirection: sun.position.clone().normalize(),
    sunColor: "#fff7dd",
    waterColor: "#1b6c91",
    distortionScale: 0.3,
  });
  water.rotation.x = -Math.PI / 2;
  scene.add(water);
  const m = water.material;
  m.uniforms.waveScale = { value: 0.07 };
  m.uniforms.cutaway = { value: 0 };
  const at = point(-77.3, 32.5, 0);
  m.uniforms.cutCenter = { value: at };
  m.uniforms.size.value = 0.8;
  m.vertexShader = m.vertexShader
    .replace(
      "void main() {",
      `${glWave}\nuniform float waveScale;varying vec3 waveNormal;varying vec3 worldWater;void main(){vec3 sampled=waveAt(vec2(position.x,-position.y),time)*waveScale;vec3 displaced=position+vec3(0.0,0.0,sampled.x);waveNormal=normalize(vec3(-sampled.y,1.0,-sampled.z));worldWater=(modelMatrix*vec4(displaced,1.0)).xyz;`,
    )
    .replaceAll("vec4( position, 1.0 )", "vec4( displaced, 1.0 )");
  m.fragmentShader = m.fragmentShader
    .replace(
      "void main() {",
      "varying vec3 waveNormal;varying vec3 worldWater;uniform float cutaway;uniform vec3 cutCenter;void main() {\nif(cutaway>.001 && worldWater.z>cutCenter.z-1.3 && fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233)))*43758.5453)<cutaway)discard;",
    )
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
      "reflectionSample * vec3(.25,.62,.95) + reflectionSample * specularLight * .45",
    );
  const map = new THREE.Group();
  map.add(
    new THREE.Mesh(
      landGeometry(data.land),
      new THREE.MeshBasicMaterial({ color: "#e1d6ba", side: THREE.DoubleSide }),
    ),
  );
  scene.add(map);
  const grids = new THREE.Group(),
    lineMat = new THREE.LineBasicMaterial({
      color: "#b6e2e1",
      transparent: true,
      opacity: 0.13,
    });
  for (let lon = -180; lon <= 180; lon += 20)
    grids.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          point(lon, -55, 0.03),
          point(lon, 75, 0.03),
        ]),
        lineMat,
      ),
    );
  for (let lat = -40; lat < 80; lat += 20)
    grids.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          point(-180, lat, 0.03),
          point(180, lat, 0.03),
        ]),
        lineMat,
      ),
    );
  map.add(grids);
  const regions = new THREE.Group();
  Object.values(data.regions).forEach((r, i) =>
    regions.add(polygon(r, ["#f3c577", "#7fe3cc", "#9ed8ff"][i])),
  );
  map.add(regions);
  const segments = new THREE.Group();
  data.segments.forEach((r, i) =>
    segments.add(
      polygon(r, ["#a6f6dc", "#edd3a2", "#b6c6de"][i], i === 0 ? 0.4 : 0.2),
    ),
  );
  map.add(segments);
  const rGrid = new THREE.Group();
  for (const ring of data.rGrid)
    rGrid.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(
          ring.map(([x, y]) => point(x, y, 0.52)),
        ),
        new THREE.LineBasicMaterial({
          color: "#d9fff3",
          transparent: true,
          opacity: 0.3,
        }),
      ),
    );
  map.add(rGrid);
  const domain = polygon(data.D, "#eef0d6", 0.012);
  map.add(domain);
  const routePoints = [
    [-89, 28],
    [-86, 24.6],
    [-82, 23.5],
    [-79.8, 26.5],
    [-77, 32],
    [-69, 38],
  ].map(([x, y]) => point(x, y, 0.65));
  const curve = new THREE.CatmullRomCurve3(routePoints);
  const route = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(curve.getPoints(160)),
    new THREE.LineDashedMaterial({
      color: "#ffe2a4",
      dashSize: 0.55,
      gapSize: 0.55,
      transparent: true,
      opacity: 0.8,
    }),
  );
  route.computeLineDistances();
  map.add(route);
  const drifter = makeDrifter(),
    cut = underwaterContext(),
    anatomy = new THREE.Group();
  anatomy.position.copy(at);
  anatomy.add(cut.group, drifter.group);
  scene.add(anatomy);
  const fadeMap = fadeGroup(map),
    fadeAnatomy = fadeGroup(anatomy);
  const poses = {
    0: { pos: [at.x, 5.3, 25], look: [at.x, 4, -55] },
    1: { pos: [175, 920, 430], look: [175, 0, -25] },
    2: { pos: [-33, 140, 80], look: [-33, 0, -2] },
    3: { pos: [-7, 87, 37], look: [-7, 0, -20] },
    4: { pos: [at.x + 10, 3.5, 24], look: [at.x - 3, -2.5, 0] },
    5: { pos: [at.x, 16, 44], look: [at.x, 4, -55] },
  };
  let active = 1,
    previous = 1,
    focus = 0,
    time = 4.1,
    playing = !matchMedia("(prefers-reduced-motion: reduce)").matches,
    flight = null,
    dirty = true,
    last = 0,
    draw = 0,
    frames = 0;
  const look = new THREE.Vector3(...poses[1].look),
    pTarget = new THREE.Vector3(),
    lTarget = new THREE.Vector3();
  camera.position.set(...poses[1].pos);
  camera.lookAt(look);
  let spans = [],
    lastFlight = 0;
  const history = [];
  function setScene(n, immediate = false) {
    previous = active;
    active = n;
    const duration =
      immediate || !playing ? 0 : n === 4 || previous === 4 ? 2700 : 2300;
    flight = {
      at: performance.now(),
      duration,
      pos: camera.position.clone(),
      look: look.clone(),
    };
    spans = [];
    lastFlight = 0;
    dirty = true;
  }
  function projection(p) {
    const v = p.clone().project(camera);
    return { x: ((v.x + 1) * W) / 2, y: ((1 - v.y) * H) / 2, visible: v.z < 1 };
  }
  function layerAlpha(group, value) {
    group.visible = value > 0.001;
    group.traverse((o) => {
      if (!o.material) return;
      const mat = o.material;
      if (mat.userData.baseOpacity === undefined)
        mat.userData.baseOpacity = mat.opacity;
      mat.opacity = mat.userData.baseOpacity * value;
    });
  }
  function select(p) {
    const flying = p < 1;
    const maps = (n) => n >= 1 && n <= 3;
    const mapOpacity = maps(active)
      ? maps(previous)
        ? 1
        : between(p, 0.1, 0.72)
      : maps(previous)
        ? 1 - between(p, 0.05, 0.62)
        : 0;
    const anatomyOpacity =
      active === 4
        ? between(p, 0.48, 0.98)
        : previous === 4
          ? 1 - between(p, 0, 0.55)
          : 0;
    fadeMap(mapOpacity);
    fadeAnatomy(anatomyOpacity);
    regions.visible = active === 2 || (previous === 2 && flying);
    segments.visible = active === 3 || (previous === 3 && flying);
    route.visible = active === 2 || (previous === 2 && flying);
    rGrid.visible = active === 3;
    domain.visible = active === 2;
    grids.visible = active === 1;
    m.uniforms.cutaway.value = anatomyOpacity;
    const p2 =
      active === 2
        ? between(p, 0.1, 0.85)
        : previous === 2
          ? 1 - between(p, 0, 0.65)
          : 0;
    const p3 =
      active === 3
        ? between(p, 0.15, 0.9)
        : previous === 3
          ? 1 - between(p, 0, 0.65)
          : 0;
    layerAlpha(regions, p2);
    layerAlpha(domain, p2);
    layerAlpha(segments, p3);
    layerAlpha(rGrid, p3);
    route.visible = p2 > 0.001;
    route.material.opacity = 0.8 * p2;
    m.uniforms.waveScale.value = THREE.MathUtils.lerp(
      maps(previous) ? 0.06 : 0.35,
      maps(active) ? 0.06 : 0.35,
      smooth(p),
    );
    m.uniforms.size.value = THREE.MathUtils.lerp(
      maps(previous) ? 0.8 : 18,
      maps(active) ? 0.8 : 18,
      smooth(p),
    );
    return anatomyOpacity;
  }
  function frame(stamp) {
    requestAnimationFrame(frame);
    const delta = Math.min((stamp - last) / 1000 || 0, 0.05);
    last = stamp;
    if (document.hidden) return;
    if (playing) time += delta * 0.7;
    if (!playing && !flight && !dirty) return;
    if (stamp - draw < 1000 / 60 && !dirty) return;
    draw = stamp - ((stamp - draw) % (1000 / 60));
    dirty = false;
    let p = 1;
    if (flight) {
      p = flight.duration
        ? Math.min(1, (stamp - flight.at) / flight.duration)
        : 1;
      const e = smooth(p);
      camera.position.lerpVectors(
        flight.pos,
        pTarget.set(...poses[active].pos),
        e,
      );
      look.lerpVectors(flight.look, lTarget.set(...poses[active].look), e);
    }
    camera.near = Math.max(0.1, camera.position.y * 0.012);
    camera.lookAt(look);
    camera.updateProjectionMatrix();
    select(p);
    m.uniforms.time.value = time;
    drifter.update(time, focus);
    cut.update(time);
    scene.backgroundRotation.y = 0.7 + time * 0.0008;
    renderer.render(scene, camera);
    frames++;
    const canvas = renderer.domElement;
    canvas.dataset.renderFrame = frames;
    canvas.dataset.cameraMoving = String(p < 1);
    canvas.dataset.scene = active;
    const anchors = {};
    if (p === 1) {
      if (active === 1) {
        [
          ["kuroshio", 136, 26],
          ["california", -125, 33],
          ["central", -37, 37],
          ["sargasso", -59, 25],
          ["florida", -79, 25.5],
          ["gulfstream", -70, 38],
        ].forEach(
          ([name, x, y]) => (anchors[name] = projection(point(x, y, 1))),
        );
      } else if (active === 2) {
        [
          ["gulf", -89, 27.5],
          ["bahamas", -79.5, 26],
          ["stream", -69, 37],
        ].forEach(
          ([name, x, y]) => (anchors[name] = projection(point(x, y, 1))),
        );
      } else if (active === 3) {
        [
          ["south", -77, 32.7],
          ["hatteras", -71.5, 37],
          ["north", -65, 40.5],
        ].forEach(
          ([name, x, y]) => (anchors[name] = projection(point(x, y, 1))),
        );
      } else if (active === 4) {
        for (const [name, p] of Object.entries(drifter.anchors))
          anchors[name] = projection(drifter.group.localToWorld(p.clone()));
      }
    }
    onFrame({
      scene: active,
      progress: p,
      anchors,
      time,
      chartBlend:
        active === 5
          ? between(p, 0.15, 0.9)
          : previous === 5
            ? 1 - between(p, 0.05, 0.8)
            : 0,
    });
    if (flight && flight.duration) {
      if (lastFlight) spans.push(stamp - lastFlight);
      lastFlight = stamp;
    }
    if (flight && p === 1) {
      if (spans.length) {
        const a = [...spans].sort((x, y) => x - y),
          stats = {
            from: previous,
            to: active,
            frames: a.length,
            meanMs: Math.round(spans.reduce((a, b) => a + b) / a.length),
            p95Ms: Math.round(a[Math.floor(a.length * 0.95)]),
            maxMs: Math.round(a.at(-1)),
          };
        history.push(stats);
        canvas.dataset.transitionStats = JSON.stringify(stats);
        canvas.dataset.transitionHistory = JSON.stringify(history.slice(-15));
      }
      flight = null;
      onSettled(active);
    }
  }
  // Compile/upload both scenes under the loader, including transparency and the cutaway.
  map.visible = anatomy.visible = true;
  regions.visible = segments.visible = domain.visible = route.visible = true;
  drifter.update(4, 1);
  scene.updateMatrixWorld(true);
  await renderer.compileAsync(scene, camera);
  for (const n of [1, 2, 3, 4, 5]) {
    active = previous = n;
    camera.position.set(...poses[n].pos);
    camera.lookAt(lTarget.set(...poses[n].look));
    camera.updateProjectionMatrix();
    select(1);
    m.uniforms.time.value = time;
    renderer.render(scene, camera);
    await new Promise((r) => requestAnimationFrame(r));
  }
  // Finish the warm renders before the loading screen yields to navigation.
  renderer.getContext().finish();
  active = previous = 1;
  camera.position.set(...poses[1].pos);
  look.set(...poses[1].look);
  requestAnimationFrame(frame);
  return {
    setScene,
    startOverview() {
      active = previous = 0;
      camera.position.set(...poses[0].pos);
      look.set(...poses[0].look);
      setScene(1, false);
      flight.duration = 3200;
    },
    setFocus(i) {
      focus = i;
      renderer.domElement.dataset.focus = String(i);
      dirty = true;
    },
    isPlaying: () => playing,
    toggle() {
      playing = !playing;
      if (!playing && flight) flight.duration = 0;
      dirty = true;
      return playing;
    },
    canvas: renderer.domElement,
  };
}
