import * as THREE from "three";
import { Water } from "../assets/vendor/Water.js";
import { HDRLoader } from "../assets/vendor/HDRLoader.js";
import { glWave, sample } from "../pt1/waves.js?v=transitions3";
const smooth = (p) => p * p * p * (p * (p * 6 - 15) + 10);
export async function createOcean(host) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setSize(1920, 1080);
  renderer.setPixelRatio(1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene(),
    camera = new THREE.PerspectiveCamera(43, 1920 / 1080, 0.1, 10000),
    look = new THREE.Vector3(0, 0, -45);
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
  scene.add(new THREE.HemisphereLight("#deeff5", "#827b60", 2));
  const sun = new THREE.DirectionalLight("#fff5df", 2);
  sun.position.set(-20, 40, 15);
  scene.add(sun);
  const geo = new THREE.PlaneGeometry(2, 2, 128, 128),
    a = geo.attributes.position;
  for (let i = 0; i < a.count; i++)
    for (const ax of ["X", "Y"]) {
      const p = a["get" + ax](i);
      a["set" + ax](i, Math.sign(p) * Math.abs(p) ** 2.6 * 4000);
    }
  geo.computeBoundingSphere();
  const water = new Water(geo, {
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
  wm.uniforms.waveScale = { value: 0.6 };
  wm.uniforms.size.value = 12;
  wm.vertexShader = wm.vertexShader
    .replace(
      "void main() {",
      `${glWave}\nuniform float waveScale;varying vec3 waveNormal;void main(){vec3 sampled=waveAt(vec2(position.x,-position.y),time)*waveScale;vec3 displaced=position+vec3(0.,0.,sampled.x);waveNormal=normalize(vec3(-sampled.y,1.,-sampled.z));`,
    )
    .replaceAll("vec4( position, 1.0 )", "vec4( displaced, 1.0 )");
  wm.fragmentShader = wm.fragmentShader
    .replace("void main() {", "varying vec3 waveNormal;void main(){")
    .replace(
      "normalize( noise.xzy * vec3( 1.5, 1.0, 1.5 ) )",
      "normalize(waveNormal+vec3(noise.x*.4,0.,noise.y*.4))",
    )
    .replace("float rf0 = 0.3;", "float rf0 = 0.045;")
    .replace(
      "sunColor * diffuseLight * 0.3 + scatter",
      "sunColor * diffuseLight * .025 + scatter * 1.4",
    )
    .replace(
      "vec3( 0.1 ) + reflectionSample * 0.9 + reflectionSample * specularLight",
      "reflectionSample * vec3(.25,.62,.95) + reflectionSample * specularLight * .4",
    );
  const drifter = new THREE.Group();
  const white = new THREE.MeshStandardMaterial({
      color: "#f1ead8",
      roughness: 0.5,
    }),
    red = new THREE.MeshStandardMaterial({ color: "#d7713c", roughness: 0.5 }),
    dark = new THREE.MeshStandardMaterial({ color: "#29414c", roughness: 0.9 });
  const buoy = new THREE.Mesh(new THREE.SphereGeometry(0.75, 24, 14), white);
  buoy.scale.y = 0.6;
  drifter.add(buoy);
  const cap = new THREE.Mesh(
    new THREE.CylinderGeometry(0.45, 0.65, 0.22, 24),
    red,
  );
  cap.position.y = 0.38;
  drifter.add(cap);
  const antenna = new THREE.Mesh(
    new THREE.CylinderGeometry(0.026, 0.026, 1.6, 8),
    dark,
  );
  antenna.position.y = 1.15;
  drifter.add(antenna);
  const rope = new THREE.Mesh(
    new THREE.CylinderGeometry(0.015, 0.015, 4, 6),
    dark,
  );
  rope.position.y = -2;
  drifter.add(rope);
  const drogue = new THREE.Mesh(
    new THREE.CylinderGeometry(0.34, 0.34, 1.7, 12, 1, true),
    dark,
  );
  drogue.position.y = -4;
  drifter.add(drogue);
  drifter.position.set(18, 0, -15);
  scene.add(drifter);
  // A gently submerged, curved shoreline avoids a floating rectangular slab.
  const shoreGeo = new THREE.BufferGeometry(),
    shorePositions = [],
    shoreColors = [];
  const sandAt = (r, a) => {
    const edge = 1 + 0.035 * Math.sin(a * 5) + 0.018 * Math.cos(a * 11);
    const x = 82 + 59 * r * edge * Math.cos(a),
      z = -42 + 110 * r * edge * Math.sin(a);
    const y =
      2.5 * Math.sqrt(Math.max(0, 1 - r)) -
      0.38 +
      0.025 * Math.sin(x * 2.7 + z);
    return [x, y, z];
  };
  const emitSand = (r, a) => {
    shorePositions.push(...sandAt(r, a));
    const c = new THREE.Color(r > 0.93 ? "#a99f80" : "#e1d2ac");
    shoreColors.push(c.r, c.g, c.b);
  };
  for (let ring = 0; ring < 32; ring++)
    for (let sector = 0; sector < 144; sector++) {
      const r = ring / 32,
        q = (ring + 1) / 32,
        a = (sector / 144) * Math.PI * 2,
        b = ((sector + 1) / 144) * Math.PI * 2;
      for (const [rr, aa] of [
        [r, a],
        [q, a],
        [q, b],
        [r, a],
        [q, b],
        [r, b],
      ])
        emitSand(rr, aa);
    }
  shoreGeo.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(shorePositions, 3),
  );
  shoreGeo.setAttribute(
    "color",
    new THREE.Float32BufferAttribute(shoreColors, 3),
  );
  shoreGeo.computeVertexNormals();
  const shoreMat = new THREE.MeshStandardMaterial({
    color: "#ffffff",
    vertexColors: true,
    side: THREE.DoubleSide,
    roughness: 1,
    transparent: true,
    opacity: 0,
  });
  shoreMat.onBeforeCompile = (shader) => {
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        "#include <common>\nfloat grain(vec2 p){return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453);}",
      )
      .replace(
        "#include <color_fragment>",
        "#include <color_fragment>\ndiffuseColor.rgb *= .94 + .12 * grain(gl_FragCoord.xy);",
      );
  };
  const shore = new THREE.Mesh(shoreGeo, shoreMat);
  scene.add(shore);
  const poses = [
    { p: [0, 24, 35], l: [4, 0, -38] },
    { p: [7, 20, 30], l: [9, 0, -40] },
    { p: [3, 4, 20], l: [7, 1, -42] },
    { p: [7, 12, 27], l: [30, 0, -35] },
  ];
  camera.position.set(0, 65, 50);
  camera.lookAt(look);
  let playing = !matchMedia("(prefers-reduced-motion: reduce)").matches,
    time = 5,
    last = 0,
    draw = 0,
    flight = null,
    shoreAlpha = 0,
    dirty = true,
    frames = 0;
  function fly(n, { immediate = false } = {}) {
    const p = poses[n - 1];
    return new Promise((resolve) => {
      flight = {
        from: camera.position.clone(),
        look: look.clone(),
        to: new THREE.Vector3(...p.p),
        target: new THREE.Vector3(...p.l),
        shoreFrom: shoreAlpha,
        shoreTo: n === 4 ? 1 : 0,
        at: performance.now(),
        duration: immediate || !playing ? 0 : 1650,
        resolve,
      };
      dirty = true;
    });
  }
  function frame(t) {
    requestAnimationFrame(frame);
    const dt = Math.min((t - last) / 1000 || 0, 0.05);
    last = t;
    if (document.hidden) return;
    if (!playing && !flight && !dirty) return;
    if (playing) time += dt;
    if (t - draw < 1000 / 60 && !dirty) return;
    draw = t;
    dirty = false;
    let progress = 1;
    if (flight) {
      progress = flight.duration
        ? Math.min((t - flight.at) / flight.duration, 1)
        : 1;
      const e = smooth(progress);
      camera.position.lerpVectors(flight.from, flight.to, e);
      look.lerpVectors(flight.look, flight.target, e);
      shoreAlpha = THREE.MathUtils.lerp(flight.shoreFrom, flight.shoreTo, e);
    }
    camera.lookAt(look);
    shoreMat.opacity = shoreAlpha;
    shore.visible = shoreAlpha > 0.001;
    wm.uniforms.time.value = time * 0.7;
    const w = sample(drifter.position.x, drifter.position.z, time * 0.7);
    drifter.position.y = w.h * 0.6;
    drifter.rotation.x = w.dz * 0.25;
    drifter.rotation.z = -w.dx * 0.25;
    renderer.render(scene, camera);
    renderer.domElement.dataset.renderFrame = String(++frames);
    renderer.domElement.dataset.cameraMoving = String(progress < 1);
    if (flight && progress === 1) {
      const f = flight;
      flight = null;
      f.resolve();
    }
  }
  await renderer.compileAsync(scene, camera);
  renderer.render(scene, camera);
  renderer.getContext().finish();
  requestAnimationFrame(frame);
  return {
    fly,
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
