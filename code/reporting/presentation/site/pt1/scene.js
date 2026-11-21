import * as THREE from "three";
import { Water } from "../assets/vendor/Water.js";
import { HDRLoader } from "../assets/vendor/HDRLoader.js";
import {
  makeBuoy,
  makeBottle,
  makeBook,
  makeRaft,
  makeCargo,
  makeSlick,
  mesh,
} from "./objects.js?v=transitions3";
import { createShore } from "./shore.js?v=transitions3";
import { sample, glWave } from "./waves.js?v=transitions3";
const W = 1920,
  H = 1080;
const merc = (lat) =>
  (Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) * 180) / Math.PI;
export const mapPoint = (lon, lat, y = 0.3) =>
  new THREE.Vector3((lon + 77) * 3, y, -(merc(lat) - merc(32.5)) * 3);
function mapGeometry(data) {
  const g = new THREE.Group();
  const landMat = new THREE.MeshStandardMaterial({
    color: "#e5dcc5",
    roughness: 0.93,
    metalness: 0,
  });
  for (const ring of data.land) {
    if (ring.length < 3) continue;
    const shape = new THREE.Shape();
    ring.forEach(([lon, lat], i) => {
      const p = mapPoint(lon, lat);
      i ? shape.lineTo(p.x, -p.z) : shape.moveTo(p.x, -p.z);
    });
    const geo = new THREE.ExtrudeGeometry(shape, {
      depth: 0.12,
      bevelEnabled: false,
    });
    const m = mesh(geo, landMat, g);
    m.rotation.x = -Math.PI / 2;
    m.position.y = 0.14;
  }
  const s = new THREE.Shape();
  data.region.forEach(([lon, lat], i) => {
    const p = mapPoint(lon, lat);
    i ? s.lineTo(p.x, -p.z) : s.moveTo(p.x, -p.z);
  });
  const fill = mesh(
    new THREE.ShapeGeometry(s),
    new THREE.MeshBasicMaterial({
      color: "#18b4a8",
      transparent: true,
      opacity: 0.22,
      depthWrite: false,
      side: THREE.DoubleSide,
    }),
    g,
    [0, 0.31, 0],
  );
  fill.rotation.x = -Math.PI / 2;
  fill.renderOrder = 4;
  g.userData.regionFill = fill;
  const points = data.region.map(([lon, lat]) => mapPoint(lon, lat, 0.36));
  for (let i = 1; i < points.length; i++) {
    const curve = new THREE.LineCurve3(points[i - 1], points[i]);
    mesh(
      new THREE.TubeGeometry(curve, 1, 0.045, 8, false),
      new THREE.MeshBasicMaterial({ color: "#f1d99d" }),
      g,
    );
  }
  // Sparse, subdued geographic grid only; no invented probability field.
  const gridMat = new THREE.LineBasicMaterial({
    color: "#8bcbc5",
    transparent: true,
    opacity: 0.2,
  });
  for (let lon = -96; lon <= -64; lon += 4) {
    const pts = [mapPoint(lon, 20, 0.05), mapPoint(lon, 41, 0.05)];
    g.add(
      new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), gridMat),
    );
  }
  for (let lat = 22; lat <= 40; lat += 4) {
    const pts = [mapPoint(-99, lat, 0.05), mapPoint(-63, lat, 0.05)];
    g.add(
      new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), gridMat),
    );
  }
  return g;
}
export async function createStage(
  host,
  data,
  onFrame = () => {},
  onSettled = () => {},
) {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: false,
    powerPreference: "high-performance",
    preserveDrawingBuffer: false,
  });
  renderer.setPixelRatio(1);
  renderer.setSize(W, H);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.9;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 14000);
  const beachOffset = new THREE.Vector3(160, 0, -120);
  const sky = await new HDRLoader().loadAsync(
    "./assets/pt1/daylight-sky.hdr?v=2",
  );
  sky.mapping = THREE.EquirectangularReflectionMapping;
  scene.background = sky;
  scene.backgroundRotation.y = 0.7;
  scene.backgroundIntensity = 0.9;
  // Keep the photographed cloud field while grading the daylight sky for projection.
  const skyMaterial = new THREE.ShaderMaterial({
    uniforms: { sky: { value: sky } },
    side: THREE.BackSide,
    depthWrite: false,
    vertexShader: `varying vec3 direction;void main(){direction=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader: `uniform sampler2D sky;varying vec3 direction;void main(){vec3 d=normalize(direction);vec2 uv=vec2(atan(d.z,d.x)/6.2831853+.5,asin(d.y)/3.14159265+.5);vec3 c=texture2D(sky,uv).rgb;float l=dot(c,vec3(.2126,.7152,.0722));c=max(vec3(0.0),mix(vec3(l),c,1.55));gl_FragColor=vec4(c*1.5,1.0);
#include <tonemapping_fragment>
#include <colorspace_fragment>
}`,
  });
  const skyDome = new THREE.Mesh(
    new THREE.SphereGeometry(8000, 48, 32),
    skyMaterial,
  );
  skyDome.rotation.y = 0.7;
  skyDome.renderOrder = -10;
  scene.add(skyDome);
  const pm = new THREE.PMREMGenerator(renderer);
  const env = pm.fromEquirectangular(sky);
  scene.environment = env.texture;
  scene.environmentRotation.y = 0.7;
  scene.environmentIntensity = 0.6;
  pm.dispose();
  scene.add(new THREE.HemisphereLight("#d6ebff", "#c8b58b", 0.8));
  const sun = new THREE.DirectionalLight("#fff9e9", 2.6);
  sun.position.set(-16, 26, -10);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -22;
  sun.shadow.camera.right = 22;
  sun.shadow.camera.top = 22;
  sun.shadow.camera.bottom = -22;
  sun.shadow.normalBias = 0.025;
  sun.shadow.bias = -0.0004;
  sun.shadow.camera.far = 90;
  sun.position.add(beachOffset);
  sun.target.position.copy(beachOffset);
  scene.add(sun, sun.target);
  const fillLight = new THREE.DirectionalLight("#eef7ff", 0.85);
  fillLight.position.set(4, 14, 18);
  scene.add(fillLight);
  const normal = await new THREE.TextureLoader().loadAsync(
    "./assets/waternormals.jpg",
  );
  normal.wrapS = normal.wrapT = THREE.RepeatWrapping;
  const geo = new THREE.PlaneGeometry(2, 2, 256, 256),
    v = geo.attributes.position;
  for (let i = 0; i < v.count; i++) {
    for (const axis of ["X", "Y"]) {
      const p = v["get" + axis](i);
      v["set" + axis](i, Math.sign(p) * Math.pow(Math.abs(p), 2.7) * 6500);
    }
  }
  geo.computeBoundingSphere();
  const water = new Water(geo, {
    textureWidth: 512,
    textureHeight: 512,
    waterNormals: normal,
    sunDirection: sun.position.clone().sub(sun.target.position).normalize(),
    sunColor: "#fff7dd",
    waterColor: "#087b94",
    distortionScale: 0.3,
  });
  water.rotation.x = -Math.PI / 2;
  scene.add(water);
  const mat = water.material;
  mat.uniforms.size.value = 18;
  mat.uniforms.waveScale = { value: 1 };
  mat.uniforms.reflectionTint = { value: new THREE.Vector3(0.25, 0.62, 0.95) };
  mat.uniforms.time.value = 4.1;
  mat.vertexShader = mat.vertexShader
    .replace(
      "void main() {",
      `${glWave}\nuniform float waveScale;varying vec3 waveNormal;void main(){vec3 sampled=waveAt(vec2(position.x,-position.y),time)*waveScale;vec3 displaced=position+vec3(0.0,0.0,sampled.x);waveNormal=normalize(vec3(-sampled.y,1.0,-sampled.z));`,
    )
    .replaceAll("vec4( position, 1.0 )", "vec4( displaced, 1.0 )");
  mat.fragmentShader = mat.fragmentShader
    .replace(
      "void main() {",
      "varying vec3 waveNormal;uniform vec3 reflectionTint;void main() {",
    )
    .replace(
      "normalize( noise.xzy * vec3( 1.5, 1.0, 1.5 ) )",
      "normalize(waveNormal+vec3(noise.x*.58,0.0,noise.y*.58))",
    )
    .replace("float rf0 = 0.3;", "float rf0 = 0.045;")
    .replace(
      "sunColor * diffuseLight * 0.3 + scatter",
      "sunColor * diffuseLight * 0.025 + scatter * 1.4",
    )
    .replace(
      "vec3( 0.1 ) + reflectionSample * 0.9 + reflectionSample * specularLight",
      "reflectionSample * reflectionTint + reflectionSample * specularLight * 0.55",
    );
  mat.needsUpdate = true;
  const shore = await createShore();
  const buoy = makeBuoy(),
    bottle = makeBottle(),
    book = makeBook(),
    raft = makeRaft(),
    cargo = makeCargo(),
    slick = makeSlick(),
    map = mapGeometry(data);
  const beach = new THREE.Group();
  beach.position.copy(beachOffset);
  beach.add(book, shore.group);
  const props = [buoy, bottle, beach, raft, cargo, slick, map];
  props.forEach((p) => scene.add(p));
  buoy.scale.setScalar(1.6);
  bottle.scale.setScalar(1.45);
  book.position.set(0, 0.3, 0);
  book.scale.setScalar(1.04);
  const filmTime = { value: 0 },
    filmSpread = { value: 0.22 };
  slick.children.forEach((layer) => {
    layer.material.onBeforeCompile = (shader) => {
      shader.uniforms.motionTime = filmTime;
      shader.uniforms.spread = filmSpread;
      shader.vertexShader = shader.vertexShader
        .replace(
          "#include <common>",
          `#include <common>\nuniform float motionTime;${glWave}`,
        )
        .replace(
          "#include <begin_vertex>",
          "vec3 transformed=position;vec3 wp=(modelMatrix*vec4(position,1.0)).xyz;transformed.y=waveAt(wp.xz,motionTime).x+.12;",
        );
      shader.fragmentShader = shader.fragmentShader
        .replace(
          "#include <common>",
          "#include <common>\nuniform float spread;",
        )
        .replace(
          "#include <alphamap_fragment>",
          "diffuseColor.a *= texture2D(alphaMap,(vAlphaMapUv-.5)/spread+.5).g;",
        );
    };
  });
  book.userData.pages.forEach((page) => {
    page.material.onBeforeCompile = (shader) => {
      shader.uniforms.motionTime = filmTime;
      shader.vertexShader = shader.vertexShader
        .replace(
          "#include <common>",
          "#include <common>\nuniform float motionTime;",
        )
        .replace(
          "#include <begin_vertex>",
          "vec3 transformed=position;transformed.z+=.018*sin(position.y*2.4+motionTime)*pow(abs(position.x)/3.625,10.0);",
        );
    };
  });
  const cargoOrigins = cargo.children.map((p) => ({
    x: p.position.x,
    z: p.position.z,
    ry: p.rotation.y,
    rz: p.rotation.z,
  }));
  const up = new THREE.Vector3(0, 1, 0),
    normalVector = new THREE.Vector3();
  function float(object, x, z, time, rotation = 0, offset = 0) {
    const wave = sample(x, z, time);
    object.position.set(x, wave.h + offset, z);
    object.quaternion.setFromUnitVectors(
      up,
      normalVector.set(-wave.dx, 1, -wave.dz).normalize(),
    );
    object.rotateY(rotation);
  }
  const poses = {
    1: { position: [7, 2.9, 15], look: [-4, 4, 0], fov: 45 },
    2: { position: [-23, 62, 13], look: [-23, 0, 0], fov: 45 },
    3: { position: [0, 3.1, 14], look: [0, 3.2, 0], fov: 45 },
    4: { position: [160.8, 4.8, -103.5], look: [160, 4.3, -120], fov: 41 },
    5: { position: [7, 6, 17], look: [0, 3, 0], fov: 45 },
  };
  let active = 1,
    previous = 1,
    transition = null,
    time = 4.1,
    sceneTime = 0,
    playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  let lastStamp = 0,
    lastDraw = 0,
    dirty = true,
    frames = 0;
  const look = new THREE.Vector3(...poses[1].look);
  camera.position.set(...poses[1].position);
  camera.lookAt(look);
  const ease = (p) => p * p * p * (p * (p * 6 - 15) + 10);
  const interval = (value, start, end) =>
    ease(THREE.MathUtils.clamp((value - start) / (end - start), 0, 1));
  // Dither coverage fades geometry without a transparent sorting or depth pop.
  function fadeGroup(group) {
    const uniform = { value: 1 };
    const materials = new Set();
    group.traverse((o) => {
      if (o.material)
        (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) =>
          materials.add(m),
        );
    });
    materials.forEach((material) => {
      const before = material.onBeforeCompile;
      const key = material.customProgramCacheKey();
      material.onBeforeCompile = function (shader, renderer) {
        before.call(this, shader, renderer);
        shader.uniforms.sceneVisibility = uniform;
        shader.fragmentShader = shader.fragmentShader
          .replace(
            "#include <common>",
            "#include <common>\nuniform float sceneVisibility;",
          )
          .replace(
            "#include <clipping_planes_fragment>",
            "#include <clipping_planes_fragment>\nif(sceneVisibility < 1.0 && fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233)))*43758.5453) > sceneVisibility) discard;",
          );
      };
      material.customProgramCacheKey = () => key + ":scene-visibility";
      material.needsUpdate = true;
    });
    return (value) => {
      uniform.value = value;
      group.visible = value > 0.001;
    };
  }
  const fadeBuoy = fadeGroup(buoy),
    fadeBottle = fadeGroup(bottle),
    fadeMap = fadeGroup(map);
  const waterStates = {
    1: { wave: 1, size: 18, color: new THREE.Color("#087b94"), exposure: 0.9 },
    2: {
      wave: 0.1,
      size: 0.8,
      color: new THREE.Color("#176d95"),
      exposure: 0.9,
    },
    3: { wave: 1, size: 18, color: new THREE.Color("#087b94"), exposure: 0.9 },
    4: {
      wave: 0.45,
      size: 18,
      color: new THREE.Color("#087b94"),
      exposure: 0.93,
    },
    5: { wave: 1, size: 18, color: new THREE.Color("#087b94"), exposure: 0.9 },
  };
  const targetPosition = new THREE.Vector3(),
    targetLook = new THREE.Vector3();
  const panelCameras = Array.from(
    { length: 3 },
    () => new THREE.PerspectiveCamera(45, W / H, 0.1, 14000),
  );
  let flightFrames = [],
    lastFlightStamp = 0;
  function setScene(n, immediate = false) {
    previous = active;
    active = n;
    sceneTime = 0;
    transition = {
      start: performance.now(),
      duration:
        immediate || !playing
          ? 0
          : n === 4 || previous === 4
            ? 3100
            : n === 2 || previous === 2
              ? 2600
              : 2100,
      position: camera.position.clone(),
      look: look.clone(),
      fov: camera.fov,
    };
    flightFrames = [];
    lastFlightStamp = 0;
    dirty = true;
  }
  function screenPoint(point) {
    const p = point.clone().project(camera);
    return { x: ((p.x + 1) * W) / 2, y: ((1 - p.y) * H) / 2 };
  }
  function pageCorners(page) {
    return [
      [-3.625, 3.6],
      [3.625, 3.6],
      [3.625, -3.6],
      [-3.625, -3.6],
    ].map(([x, y]) =>
      screenPoint(page.localToWorld(new THREE.Vector3(x, y, 0.19))),
    );
  }
  function updateObjects() {
    skyDome.rotation.y = 0.7 + time * 0.001;
    float(buoy, 2 + 0.12 * Math.sin(time * 0.16), -7, time, 0.18);
    bottle.position.set(
      -5.75 + 0.13 * Math.sin(time * 0.3),
      sample(-5.75, 2, time).h * 0.65,
      2,
    );
    bottle.rotation.set(
      0.18 + 0.035 * Math.sin(time * 0.8),
      0.2,
      -0.91 + 0.06 * Math.sin(time * 0.65),
    );
    bottle.userData.cork.position.y = 3.25 + 0.075 * Math.sin(time * 1.1);
    float(raft, 0, 0, time, -0.1, 0.25);
    cargo.children.forEach((item, i) => {
      const p = cargoOrigins[i];
      float(
        item,
        p.x + 0.1 * Math.sin(time * 0.25 + i),
        p.z,
        time + i * 0.17,
        p.ry,
        0.1 - i * 0.05,
      );
      item.rotateZ(p.rz);
    });
    shore.update(time);
    filmTime.value = time;
    map.userData.regionFill.material.opacity =
      0.2 + 0.035 * Math.sin(time * 0.9);
    filmSpread.value = 0.22 + 0.78 * (1 - Math.exp(-sceneTime / 13));
  }
  function selectProps(progress) {
    props.forEach((p) => (p.visible = false));
    const inFlight = progress < 1;
    const departing = 1 - interval(progress, 0.08, 0.42);
    const arriving = interval(progress, 0.42, 0.9);
    let buoyAmount =
      active === 1
        ? inFlight
          ? arriving
          : 1
        : previous === 1 && inFlight
          ? departing
          : 0;
    if (active === 2 && previous === 1 && inFlight) {
      // The drifter shrinks in perspective first; only fades once the camera is high.
      buoyAmount = 1 - interval(camera.position.y, 25, 52);
    }
    if (active === 1 && previous === 2 && inFlight)
      buoyAmount = 1 - interval(camera.position.y, 25, 52);
    fadeBuoy(buoyAmount);
    fadeBottle(
      active === 3
        ? inFlight
          ? arriving
          : 1
        : previous === 3 && inFlight
          ? active === 4
            ? 1 - interval(progress, 0.75, 1)
            : departing
          : 0,
    );
    fadeMap(
      active === 2
        ? inFlight
          ? interval(progress, 0.32, 0.88)
          : 1
        : previous === 2 && inFlight
          ? 1 - interval(progress, 0.08, 0.58)
          : 0,
    );
    // The beach has a real, distant world position: it enters the camera frustum naturally.
    beach.visible = active === 4 || (previous === 4 && inFlight);
    raft.visible = active === 5 || (previous === 5 && inFlight);
  }
  function baseWater(progress) {
    const from = waterStates[previous],
      to = waterStates[active],
      p = ease(progress);
    mat.uniforms.time.value = time;
    mat.uniforms.waveScale.value = THREE.MathUtils.lerp(from.wave, to.wave, p);
    mat.uniforms.size.value = THREE.MathUtils.lerp(from.size, to.size, p);
    mat.uniforms.waterColor.value.copy(from.color).lerp(to.color, p);
    mat.uniforms.reflectionTint.value.set(0.25, 0.62, 0.95);
    renderer.setScissorTest(false);
    renderer.setViewport(0, 0, W, H);
    renderer.toneMappingExposure = THREE.MathUtils.lerp(
      from.exposure,
      to.exposure,
      p,
    );
  }
  function drawTriptych(blend) {
    props.forEach((p) => (p.visible = false));
    renderer.setScissorTest(true);
    const groups = [raft, cargo, slick],
      positions = [
        [6, 4, 12.8],
        [7, 5, 14],
        [7, 7, 13],
      ],
      targets = [
        [0, 1.7, 0],
        [0, 1.5, -1],
        [0, 1.3, -2],
      ];
    const side = Math.round(640 * blend),
      widths = [W - 2 * side, side, side];
    let x = 0;
    for (let i = 0; i < 3; i++) {
      const width = widths[i];
      if (!width) continue;
      groups.forEach((g) => (g.visible = false));
      groups[i].visible = true;
      renderer.setViewport(x, 0, width, H);
      renderer.setScissor(x, 0, width, H);
      const panel = panelCameras[i];
      panel.aspect = width / H;
      panel.fov = THREE.MathUtils.lerp(camera.fov, 45, blend);
      panel.position
        .copy(camera.position)
        .lerp(targetPosition.set(...positions[i]), blend);
      panel.lookAt(
        targetLook.copy(look).lerp(new THREE.Vector3(...targets[i]), blend),
      );
      panel.updateProjectionMatrix();
      mat.uniforms.waterColor.value.set(i === 2 ? "#138a83" : "#087b94");
      mat.uniforms.reflectionTint.value.set(
        ...(i === 2 ? [0.22, 0.83, 0.63] : [0.25, 0.62, 0.95]),
      );
      renderer.render(scene, panel);
      x += width;
    }
    renderer.setScissorTest(false);
    renderer.setViewport(0, 0, W, H);
  }
  function frame(stamp) {
    requestAnimationFrame(frame);
    if (!lastStamp) lastStamp = stamp;
    const delta = Math.min((stamp - lastStamp) / 1000, 0.05);
    lastStamp = stamp;
    if (document.hidden) return;
    if (playing) {
      time += delta * 0.72;
      sceneTime += delta;
    }
    if (!playing && !transition && !dirty) return;
    const frameBudget = 1000 / 60;
    if (stamp - lastDraw < frameBudget && !dirty) return;
    lastDraw = stamp - ((stamp - lastDraw) % frameBudget);
    dirty = false;
    let progress = 1;
    if (transition) {
      progress = transition.duration
        ? Math.min(1, (stamp - transition.start) / transition.duration)
        : 1;
      const p = ease(progress),
        target = poses[active];
      camera.position.lerpVectors(
        transition.position,
        targetPosition.set(...target.position),
        p,
      );
      look.lerpVectors(transition.look, targetLook.set(...target.look), p);
      // Physical travel to the remote beach; zero velocity at each endpoint.
      if (active !== 2 && previous !== 2)
        camera.position.y +=
          Math.sin(progress * Math.PI) ** 2 *
          (active === 4 || previous === 4 ? 18 : 3);
      camera.fov = THREE.MathUtils.lerp(transition.fov, target.fov, p);
    } else {
      camera.position.set(...poses[active].position);
      look.set(...poses[active].look);
      camera.fov = poses[active].fov;
    }
    camera.aspect = W / H;
    camera.lookAt(look);
    camera.updateProjectionMatrix();
    baseWater(progress);
    updateObjects();
    selectProps(progress);
    renderer.shadowMap.autoUpdate = beach.visible && frames % 2 === 0;
    if (active === 5 && progress >= 0.68)
      drawTriptych(interval(progress, 0.68, 1));
    else if (previous === 5 && progress < 0.32)
      drawTriptych(1 - interval(progress, 0, 0.32));
    else renderer.render(scene, camera);
    const anchors =
      active === 2 && progress === 1
        ? ["Florida", "R", "Atlantic"].map((name, i) => ({
            name,
            ...screenPoint(
              [
                mapPoint(-82.5, 27.5, 1),
                mapPoint(-76.4, 32.9, 1),
                mapPoint(-71, 28.1, 1),
              ][i],
            ),
          }))
        : [];
    const pages =
      active === 4 && progress === 1
        ? book.userData.pages.map(pageCorners)
        : [];
    frames++;
    renderer.domElement.dataset.renderFrame = String(frames);
    onFrame({ scene: active, anchors, pages, progress, playing });
    if (transition && transition.duration) {
      if (lastFlightStamp) flightFrames.push(stamp - lastFlightStamp);
      lastFlightStamp = stamp;
    }
    renderer.domElement.dataset.cameraMoving = String(progress < 1);
    renderer.domElement.dataset.flightStage =
      progress < 0.3
        ? "departing"
        : progress < 0.7
          ? "midflight"
          : progress < 1
            ? "landing"
            : "landed";
    if (transition && progress === 1) {
      if (flightFrames.length) {
        const sorted = [...flightFrames].sort((a, b) => a - b);
        renderer.domElement.dataset.transitionStats = JSON.stringify({
          from: previous,
          to: active,
          frames: flightFrames.length,
          meanMs: Math.round(
            flightFrames.reduce((a, b) => a + b, 0) / flightFrames.length,
          ),
          p95Ms: Math.round(sorted[Math.floor(sorted.length * 0.95)]),
          maxMs: Math.round(sorted.at(-1)),
        });
      }
      transition = null;
      onSettled(active);
    }
  }
  // Compile and upload every scene behind the loading screen, not during the first flight.
  props.forEach((p) => (p.visible = true));
  scene.updateMatrixWorld(true);
  await renderer.compileAsync(scene, camera);
  const textures = new Set();
  scene.traverse((o) => {
    if (o.material)
      for (const material of Array.isArray(o.material)
        ? o.material
        : [o.material])
        for (const value of Object.values(material))
          if (value?.isTexture) textures.add(value);
  });
  textures.forEach((texture) => renderer.initTexture(texture));
  for (const n of [1, 2, 3, 4, 5]) {
    active = previous = n;
    camera.position.set(...poses[n].position);
    look.set(...poses[n].look);
    camera.fov = poses[n].fov;
    camera.lookAt(look);
    camera.updateProjectionMatrix();
    baseWater(1);
    updateObjects();
    selectProps(1);
    renderer.shadowMap.autoUpdate = true;
    if (n === 5) drawTriptych(1);
    else renderer.render(scene, camera);
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  active = previous = 1;
  camera.position.set(...poses[1].position);
  look.set(...poses[1].look);
  camera.fov = poses[1].fov;
  renderer.shadowMap.autoUpdate = false;
  requestAnimationFrame(frame);
  return {
    setScene,
    canvas: renderer.domElement,
    isPlaying: () => playing,
    toggle() {
      playing = !playing;
      if (!playing && transition) transition.duration = 0;
      dirty = true;
      return playing;
    },
    replay() {
      sceneTime = 0;
      dirty = true;
    },
  };
}
