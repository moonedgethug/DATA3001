import { connectFlow, goPart, setSceneHash } from "../flow/bridge.js?v=flow1";
import { createOcean } from "./scene.js?v=p4v1";
const $ = (id) => document.getElementById(id),
  stage = $("stage"),
  esc = (x) =>
    String(x ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
const num = (n, d = 2) =>
  Number(n).toLocaleString("en-AU", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const names = [
  "Brier comparisons",
  "Energy Score",
  "The horizon limit",
  "What comes next",
];
let data,
  world,
  shown = 0,
  desired = 1,
  busy = false,
  energy = "final",
  allMDN = false,
  early = 0;
function fit() {
  const s = Math.min(innerWidth / 1920, innerHeight / 1080);
  stage.style.transform = `scale(${s})`;
  stage.style.left = `${(innerWidth - 1920 * s) / 2}px`;
  stage.style.top = `${(innerHeight - 1080 * s) / 2}px`;
}
fit();
addEventListener("resize", fit);
$("scene-nav").innerHTML = names
  .map((x, i) => `<a href="#0${i + 1}"><b>0${i + 1}</b>${x}</a>`)
  .join("");
function header(n, title, lead) {
  return `<p class="eyebrow">PART 04 / RESULTS & NEXT STEPS · 0${n}</p><h1>${title}</h1><p class="lead">${lead}</p>`;
}
function plot(groups, { energy = false, compact = false } = {}) {
  const W = 1168,
    H = energy ? 510 : 540,
    left = 270,
    right = energy ? 875 : 1000,
    top = 16,
    bottom = energy ? 472 : 506;
  const rows = groups
    .flatMap((g) => g.rows)
    .filter((r) => Number.isFinite(r.score));
  const max = energy
    ? Math.ceil(Math.max(...rows.map((r) => r.score)) / 25) * 25
    : 1.1;
  const tick = energy ? 50 : 0.25,
    scale = (v) => left + ((right - left) * v) / max;
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${energy ? "Energy Score" : "Brier"} horizontal bar plot. Lower is better; rankings are within each named evaluation group."><title>${energy ? "Energy Score" : "Brier"} comparison</title>`;
  for (let v = 0; v <= max + 0.00001; v += tick)
    svg += `<line x1="${scale(v)}" x2="${scale(v)}" y1="${top}" y2="${bottom}" stroke="#bccbc5" stroke-width="${v === 0 ? 1.5 : 1}" opacity="${v === 0 ? 1 : 0.5}"/><text class="axis-label" x="${scale(v)}" y="${H - 9}" text-anchor="middle">${energy ? v : num(v, 2)}</text>`;
  if (energy)
    svg +=
      '<text class="group-label" x="997" y="16" text-anchor="end">H90</text><text class="group-label" x="1163" y="16" text-anchor="end">90% AREA · km²</text>';
  const count = rows.length,
    groupHead = energy ? 25 : 28,
    rowHeight = Math.min(
      energy ? (compact ? 27 : 59) : 31,
      (bottom - top - (energy ? 22 : 0) - groups.length * (groupHead + 8)) /
        Math.max(count, 1),
    );
  let y = top + (energy ? 22 : 0),
    index = 0;
  for (const g of groups) {
    svg += `<text class="group-label" x="0" y="${y + 13}">${esc(g.label)}</text>`;
    y += groupHead;
    const sorted = g.rows
      .filter((r) => Number.isFinite(r.score))
      .slice()
      .sort((a, b) => a.score - b.score);
    for (let i = 0; i < sorted.length; i++) {
      const r = sorted[i],
        rank =
          sorted.filter(
            (x) =>
              Number(x.score.toFixed(energy ? 3 : 4)) <
              Number(r.score.toFixed(energy ? 3 : 4)),
          ).length + 1,
        barH = Math.min(compact ? 16 : 21, rowHeight * 0.65),
        mid = y + rowHeight * 0.48,
        fill =
          r.id === "mdn22"
            ? "#bd9250"
            : r.id === "mdn1"
              ? "#568993"
              : "#6d999e";
      svg += `<g data-model="${esc(r.id)}"><title>${esc(r.label)}: ${num(r.score, 6)}; ${esc(g.cohortLabel)}</title><text class="rank" x="0" y="${mid + 7}">${rank}</text><text class="bar-label" x="31" y="${mid + 7}">${esc(r.label)}</text><rect class="bar" style="--i:${index++}" x="${left}" y="${mid - barH / 2}" width="${scale(r.score) - left}" height="${barH}" rx="2" fill="${fill}"/><text class="bar-value" x="${scale(r.score) + 10}" y="${mid + 7}">${num(r.score, energy ? 3 : 4)}</text>${energy ? `<text class="bar-value" x="997" y="${mid + 7}" text-anchor="end">${r.h90 == null ? "—" : num(r.h90, 2) + "%"}</text><text class="bar-value" x="1163" y="${mid + 7}" text-anchor="end">${r.size == null ? "—" : num(r.size, 0)}</text>` : ""}</g>`;
      y += rowHeight;
    }
    y += energy ? 0 : 8;
  }
  return svg + "</svg>";
}
function brier() {
  return (
    header(
      1,
      "Which refinements helped?",
      "Brier Score ↓ · Seven-day forecasts · Ranks within matched experiments · Repeated controls connect the research stages.",
    ) +
    `<div class="layout"><div class="plot-wrap"><div class="plot-title"><strong>Discrete destination probabilities</strong><span>Zero-based axis · lower is better</span></div>${plot(data.brierGroups)}<p class="chart-note">Repeated B2 / Fixed rows are matched controls. Different groups use different evaluation populations or weights.</p></div><aside class="summary"><span class="scope-tag">MATCHED COMPARISONS</span><h2>Better scores.<br>Different trade-offs.</h2><p>Blending and spatial borrowing changed the balance between probability quality, coverage and region size.</p><p class="rule">Seasonal conditioning did not establish a stable improvement.</p><p class="small">Ranks use displayed precision; ties share a rank. Point estimates do not establish significant differences.</p><p class="small">This chart ends at Seasonal. Exact-origin and continuous forecasts follow in the Energy Score comparison.</p></aside></div>`
  );
}
function energyContent() {
  const group = data.energyGroups.find((g) => g.id === energy),
    rows = group.rows.filter((r) => energy !== "final" || allMDN || r.headline),
    g = { ...group, rows };
  const mdn = data.energyGroups
    .find((g) => g.id === "final")
    .rows.find((r) => r.id === "mdn22");
  const body =
    energy === "final"
      ? `<span class="scope-tag">DEVELOPMENT RECOMMENDATION</span><h2>MDN22</h2><div class="key-number">${num(mdn.score, 3)}<small> km ES</small></div><div class="score-metrics"><div><span>Observed 90% coverage</span><b>${num(mdn.h90, 2)}%</b></div><div><span>Mean 90% area</span><b>${num(mdn.size, 0)} km²</b></div></div><p>Lowest mean ES among the frozen MDN candidates; coverage and area remain part of the decision.</p><p class="small rule">Chosen after development review. Original strict acceptance was not passed; MDN22 paired intervals are still pending.</p>`
      : `<span class="scope-tag">SEPARATE EVALUATION GROUP</span><h2>${energy === "e8" ? "From cells to endpoints." : "The earlier B1 benchmark."}</h2><p>${esc(group.comparability)}</p><p class="small rule">${esc(group.cohortLabel)}</p><p class="small">These scores are kept with their original matched controls. They are not inserted into the final MDN ranking.</p>`;
  return (
    header(
      2,
      "How good is the final distribution?",
      "Energy Score ↓ · Compare probability quality, actual coverage and the size of the prediction region together.",
    ) +
    `<div class="mode-switch" aria-label="Energy Score evaluation group">${[
      ["final", "Final comparison"],
      ["e8", "B2Point bridge"],
      ["historical", "Historical B1 / B2"],
    ]
      .map(
        ([id, label]) =>
          `<button data-energy="${id}" aria-pressed="${energy === id}">${label}</button>`,
      )
      .join(
        "",
      )}${energy === "final" ? `<button id="all-mdn" aria-pressed="${allMDN}">${allMDN ? "Show main models" : "Show all 12 MDNs"}</button>` : ""}</div><div class="layout es-layout"><div class="plot-wrap"><div class="plot-title"><strong>Energy Score · km</strong><span>Lower is better · point-estimate order</span></div>${plot([g], { energy: true, compact: allMDN && energy === "final" })}<p class="chart-note">${energy === "final" ? "Same 33,971 queries / 45 drifters · equal-ID evaluation. Local GMM selected K=1: the same law as Local Gaussian." : esc(group.cohortLabel)}</p></div><aside class="summary">${body}</aside></div><p class="fineprint">${energy === "final" ? "B1 and B2Point have no matched score in this final group; see their original experiments above. ES is not a point forecast’s mean distance error." : "Changing the experiment changes the meaning of the score. The horizontal axis always starts at zero."}</p>`
  );
}
function horizon() {
  return (
    header(
      3,
      "A shorter horizon. A clearer answer.",
      "The original ambition was up to 365 days. The completed study focuses on seven-day endpoint distributions.",
    ) +
    `<div class="horizon-layout"><div><div class="research-path"><div class="stop"><b>365 days</b><span>Original ambition<br>Arbitrary forecast intervals</span></div><span class="path-arrow">→</span><div class="stop"><b>30 days</b><span>Iterative experiments<br>Performance diagnosed</span></div><span class="path-arrow">→</span><div class="stop active"><b>7 days</b><span>Completed focus<br>Direct endpoint prediction</span></div></div><div class="operator"><p class="eyebrow" style="color:#55767b">OPERATOR COMPOSITION · SCHEMATIC</p><div class="chain"><b>P<sub>Δt</sub></b><span>×</span><b>P<sub>Δt</sub></b><span>× ··· ×</span><b>P<sub>Δt</sub></b><span>→</span><small>A longer-horizon<br>distribution</small></div><h2>Each step carries its assumptions forward.</h2><p>Repeated discretisation, support gaps and unresolved probability can affect the propagated forecast. Smaller steps did not guarantee better results.</p></div><p class="fineprint">This diagram explains composition. It is not a predicted drifter trajectory.</p></div><aside class="summary"><span class="scope-tag">OBSERVED LIMIT / FUTURE TEST</span><h2>The 365-day goal remains open.</h2><p>Thirty-day iterative methods were explored. A tuned exact-position refinement did not show a reliable gain over its coarse counterpart.</p><div class="rule"><p class="small">30-day refinement · ΔS (lower is better)</p><p class="claim">−0.00012</p><p class="small">95% interval: −0.00121 to +0.00125</p></div><p>Next: compare direct and iterated forecasts at the same horizon, on matched cases, while retaining unresolved and exit mass.</p><p class="small">Time and compute constrained further model ideas. The seven-day result does not establish arbitrary-interval or 365-day forecasting skill.</p></aside></div>`
  );
}
function nextSteps() {
  return (
    header(
      4,
      "The next questions are at the boundaries.",
      "From a seven-day research model toward broader, independently tested ocean predictions.",
    ) +
    `<div class="next-layout"><div class="next-list"><article class="next-item"><span class="index">01</span><div><h2>Bring the coastline into the outcome.</h2><p>No grounding event was clearly confirmed within the used seven-day windows. Some endpoint states remain unresolved. Model grounding, recovery and missing follow-up explicitly.</p></div></article><article class="next-item"><span class="index">02</span><div><h2>Let the evidence change with time.</h2><p>Test temporal downweighting of older observations. Explore a longer memory when recent support is weak, with the rule selected inside training data.</p><p class="fineprint">Inspired by Pope et al. (2020); support-adaptive memory is our proposed extension, not an implemented result.</p></div></article><article class="next-item"><span class="index">03</span><div><h2>Test beyond the development sample.</h2><p>Add MDN22 paired uncertainty, spatial and support-stratified calibration, then an independently controlled evaluation. Preserve the frozen model-selection history.</p></div></article></div><aside class="closing"><span class="scope-tag">WHAT WE CAN CLAIM TODAY</span><h2>A probability<br>distribution.<br>Seven days ahead.</h2><p>We built and compared a sequence of empirical and continuous models for the Southern Gulf Stream Corridor.</p><p class="small">Rescue, pollution and debris transport motivate the work. Those applications need additional validation and object-specific physics.</p><a href="./pt3.html#model/mdn22">Revisit the final model ↗</a><a href="./pt1.html#01">Return to the research question ↗</a></aside></div>`
  );
}
function mount(n) {
  $("content").innerHTML = [brier, energyContent, horizon, nextSteps][n - 1]();
  document.title = `Part 4 · ${names[n - 1]} | Where Things End Up`;
  document.querySelectorAll("[data-energy]").forEach(
    (b) =>
      (b.onclick = () => {
        energy = b.dataset.energy;
        refresh();
      }),
  );
  if ($("all-mdn"))
    $("all-mdn").onclick = () => {
      allMDN = !allMDN;
      refresh();
    };
}
let refreshing = false;
async function refresh() {
  if (busy || refreshing) return;
  refreshing = true;
  stage.dataset.phase = "leaving";
  if (world?.isPlaying()) await sleep(230);
  mount(shown);
  stage.dataset.phase = "arriving";
  if (world?.isPlaying()) await sleep(30);
  stage.dataset.phase = "reading";
  refreshing = false;
  if (desired !== shown) transition();
}
function nav() {
  $("count").textContent = `0${desired} / 04`;
  $("prev").disabled = false;
  $("next").disabled = desired === 4;
  document
    .querySelectorAll("#scene-nav a")
    .forEach((a, i) =>
      a.setAttribute("aria-current", i + 1 === desired ? "step" : "false"),
    );
}
async function transition() {
  if (busy || refreshing || !world) return;
  busy = true;
  while (shown !== desired) {
    const target = desired;
    nav();
    stage.dataset.phase = "leaving";
    if (shown && world.isPlaying()) await sleep(260);
    stage.dataset.phase = "travelling";
    mount(target);
    await world.fly(target);
    shown = target;
    stage.dataset.scene = String(target);
    if (target !== desired) continue;
    stage.dataset.phase = "arriving";
    if (world.isPlaying()) await sleep(80);
    stage.dataset.phase = "reading";
  }
  busy = false;
}
function request() {
  const n = Number(location.hash.slice(1));
  desired = n >= 1 && n <= 4 && Number.isInteger(n) ? n : 1;
  transition();
}
function go(n) {
  if (n < 1) {
    goPart(3, "model/mdn22");
    return;
  }
  if (n > 4) return;
  desired = n;
  setSceneHash(`0${n}`);
  transition();
}
$("prev").onclick = () => go(desired - 1);
$("next").onclick = () => go(desired + 1);
function motion() {
  const playing = world.isPlaying();
  $("motion").textContent = playing ? "Ⅱ Pause" : "▷ Play";
  $("motion-status").textContent = playing ? "LIVE OCEAN" : "MOTION PAUSED";
  document.body.classList.toggle("motion-paused", !playing);
}
$("motion").onclick = () => {
  if (world) {
    world.toggle();
    motion();
  }
};
addEventListener("keydown", (e) => {
  if ($("notes").open || !world || e.altKey || e.ctrlKey || e.metaKey) return;
  if (["ArrowRight", "PageDown"].includes(e.key)) {
    e.preventDefault();
    go(desired + 1);
  }
  if (["ArrowLeft", "PageUp"].includes(e.key)) {
    e.preventDefault();
    go(desired - 1);
  }
  if (
    e.code === "Space" &&
    !["BUTTON", "A"].includes(document.activeElement.tagName)
  ) {
    e.preventDefault();
    world.toggle();
    motion();
  }
});
$("evidence").onclick = () => {
  if (!data) return;
  const groups = [...data.brierGroups, ...data.energyGroups];
  $("notes-body").innerHTML =
    `<p class="eyebrow" style="color:#52737a">PART 04 / SCIENTIFIC RECORD</p><h2 id="notes-title">What these comparisons mean</h2><p>Both bar plots use zero-based axes. Ranks are descriptive, within the named experiment. Brier and Energy Score have different units and cannot form one numerical leaderboard. Coverage and region size must accompany a score.</p><h3>Evaluation groups</h3>${groups.map((g) => `<p><strong>${esc(g.label)}.</strong> ${esc(g.cohortLabel)} ${esc(g.comparability)}</p>`).join("")}<h3>Missing matched scores</h3><p>B1 has a historical Energy Score diagnostic, but no score on the final continuous-model cohort. B2Point has its matched E8 comparison. Neither is silently assigned a final rank or a zero score.</p><h3>Grounding: unconfirmed is not absent</h3><p>The official evidence did not clearly confirm grounding within the seven-day windows actually used. The follow-up review still left 3,022 validation pairs with unconfirmed day-seven state; 167 other candidate windows from ultimately grounded drifters crossed their official end boundary and had missing endpoints, so were not scored. These counts are not counts of confirmed grounding events.</p><h3>Long horizons and memory</h3><p>Thirty-day iterative studies and error diagnoses exist. Historical 30-day M1 S was 0.988099 versus 0.994751 for direct B2, so iteration was not uniformly worse. The tuned position-minus-coarse contrast was −0.000121, with a conditional whole-ID 95% interval [−0.001213, +0.001254]. Repeated discretisation and support loss are plausible contributors; the experiments do not establish small-step error accumulation as the sole cause. The original up-to-365-day objective remains incomplete.</p><p><a href="https://doi.org/10.1175/JTECH-D-22-0070.1" target="_blank" rel="noopener">Chamberlain et al. (2023), Using Existing Argo Trajectories to Statistically Predict Future Float Positions with a Transition Matrix</a>, provides a related transition-matrix reference; it is not evidence for our model's numerical performance.</p><p><a href="https://doi.org/10.1175/MWR-D-19-0239.1" target="_blank" rel="noopener">Pope, Stephenson & Jackson (2020), An Adaptive Markov Chain Approach for Probabilistic Forecasting of Categorical Events</a>, motivates temporal discounting. Adapting memory to sparse recent support is a proposed extension here, still to be specified and tested.</p><h3>Final choice and evidence boundaries</h3><p>MDN22 was recommended after development review; original strict acceptance was not passed. Its paired uncertainty intervals are still pending. This repeatedly examined development cohort is not an independent final test. Local GMM selected K=1 and equals Local Gaussian in this experiment. Departure heading was removed from the presentation at the user's request; its completed research record remains intact.</p><p><a href="./assets/pt4/SOURCES.md" target="_blank" rel="noopener">Sources and data provenance ↗</a> · <a href="./assets/pt4/data.json" download>Download chart data ↓</a></p>`;
  $("notes").showModal();
};
document.querySelector(".close").onclick = () => $("notes").close();
function watch() {
  requestAnimationFrame(watch);
  if (world?.canvas.dataset.cameraMoving === "true") {
    const s = getComputedStyle($("content"));
    if (s.visibility !== "hidden" && Number(s.opacity) > 0.001)
      stage.dataset.earlyTextFrames = String(++early);
  }
}
try {
  const r = await fetch("./assets/pt4/data.json?v=p4v1");
  if (!r.ok) throw Error("Part 4 data unavailable");
  data = await r.json();
  world = await createOcean($("world"));
  connectFlow(4, world, motion);
  $("loading").hidden = true;
  request();
  addEventListener("hashchange", request);
  requestAnimationFrame(watch);
} catch (e) {
  $("loading").hidden = true;
  $("error").hidden = false;
  console.error("Part 4 initialization", e);
}
