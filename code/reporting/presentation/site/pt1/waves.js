// The same wave field drives the sea, floating objects and surface film.
export const waves = [
  { a: 0.29, k: 0.43, x: 0.94, z: 0.34, s: 1.12, p: 0 },
  { a: 0.15, k: 0.83, x: -0.32, z: 0.95, s: 1.51, p: 1.7 },
  { a: 0.055, k: 1.74, x: 0.74, z: -0.67, s: 1.94, p: 3.1 },
  { a: 0.025, k: 3.2, x: 0.28, z: 0.96, s: 2.6, p: 0.4 },
];
export function sample(x, z, time) {
  let h = 0,
    dx = 0,
    dz = 0;
  for (const w of waves) {
    const phase = w.k * (w.x * x + w.z * z) - w.s * time + w.p;
    h += w.a * Math.sin(phase);
    dx += w.a * w.k * w.x * Math.cos(phase);
    dz += w.a * w.k * w.z * Math.cos(phase);
  }
  return { h, dx, dz };
}
export const glWave = `vec3 waveAt(vec2 p,float t){vec3 w=vec3(0.0);${waves
  .map(
    (v) => `{
 float q=${v.k.toFixed(3)}*dot(vec2(${v.x.toFixed(3)},${v.z.toFixed(3)}),p)-${v.s.toFixed(3)}*t+${v.p.toFixed(3)};
 w+=vec3(${v.a.toFixed(3)}*sin(q),${(v.a * v.k * v.x).toFixed(6)}*cos(q),${(v.a * v.k * v.z).toFixed(6)}*cos(q));
}`,
  )
  .join("")}return w;}`;
