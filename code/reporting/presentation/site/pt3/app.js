import { connectFlow, goPart, setSceneHash } from "../flow/bridge.js?v=flow1";
import { createWorld } from "./scene.js?v=p3v3";
import { createCarousel } from "./carousel.js?v=p3v3";
import {
  models,
  stages,
  mainStops,
  scoreFormula,
  escapeHtml as esc,
} from "./models.js?v=p3v3";
const $ = (id) => document.getElementById(id),
  stage = $("stage"),
  wait = (ms) => new Promise((r) => setTimeout(r, ms));
let world,
  carousel,
  payload,
  current = null,
  desired = null,
  running = false,
  selected = 1,
  errors = 0;
const indexOf = (id) =>
  Math.max(
    0,
    models.findIndex((m) => m.id === id),
  );
function route() {
  const [view, requestedId] = location.hash.slice(1).split("/");
  const id = requestedId === "heading" ? "seasonal" : requestedId;
  return {
    view: view === "model" ? "detail" : "gallery",
    id: models.some((m) => m.id === id) ? id : "b2",
  };
}
const storyStops = [
  "b2",
  "fixed",
  "local-endpoint",
  "exact-point",
  "endpoint-ci",
  "local-gaussian",
  "mdn22",
];
function storyStep(direction) {
  if (!desired || !world) return;
  if (desired.view === "gallery") {
    if (direction < 0) goPart(2, "05");
    else navigate("detail", models[carousel.index()].id);
    return;
  }
  const modelIndex = indexOf(desired.id);
  const next =
    direction > 0
      ? storyStops.find((id) => indexOf(id) > modelIndex)
      : [...storyStops].reverse().find((id) => indexOf(id) < modelIndex);
  if (next) navigate("detail", next);
  else if (direction > 0) goPart(4, "01");
  else navigate("gallery", "b2");
}
function key(r) {
  return `${r.view}/${r.id}`;
}
function navigate(view, id) {
  desired = { view, id };
  setSceneHash(`${view === "detail" ? "model" : "gallery"}/${id}`);
  transition();
}
function fit() {
  const scale = Math.min(innerWidth / 1920, innerHeight / 1080);
  stage.style.transform = `scale(${scale})`;
  stage.style.left = `${(innerWidth - 1920 * scale) / 2}px`;
  stage.style.top = `${(innerHeight - 1080 * scale) / 2}px`;
}
function caption(i) {
  selected = i;
  const m = models[i];
  $("card-step").textContent = `STEP 0${m.step} / ${stages[m.step - 1]}`;
  $("card-title").textContent = m.title;
  $("card-description").textContent = m.tagline;
  document
    .querySelectorAll("#steps button")
    .forEach((b, k) =>
      b.setAttribute("aria-current", k + 1 === m.step ? "step" : "false"),
    );
}
const num = (v, d = 2) =>
  Number(v).toLocaleString("en-AU", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
function metric(label, value, unit = "", digits = 2) {
  return `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value${value == null ? " missing" : ""}">${value == null ? "Not reported" : num(value, digits)}${value != null && unit ? `<small>${unit}</small>` : ""}</div></div>`;
}
function caseCaption(map) {
  if (!map) return "Map evidence pending";
  const [lon, lat] = map.origin;
  const location = `${Math.abs(lon).toFixed(3)}° ${lon < 0 ? "W" : "E"}, ${Math.abs(lat).toFixed(3)}° ${lat < 0 ? "S" : "N"}`;
  if (map.sourceKey) return `Fixed example 1 · start ${location}`;
  if (map.kind === "fitted") return `Cell 44744 · centre ${location}`;
  return `E7 example 1 · start ${location}`;
}
function caseSelection(map) {
  if (!map) return "A matching saved forecast has not yet been exported.";
  if (map.sourceKey)
    return `This is the first of 12 examples fixed by source-key order, independently of observed outcomes or model performance. EndpointCI, Local Gaussian, Local GMM, MDN1 and MDN22 show this same start and observed day-7 endpoint. Source key: ${map.sourceKey.join(" / ")}. Changing the start changes the conditional distribution. This case does not summarize all of R.`;
  if (map.kind === "fitted")
    return "This is the fitted destination distribution for departure cell 44744, selected by historical fitting-ID support under the frozen illustration rule. It is shared across the grid-model illustrations; it is not a randomly selected endpoint or a held-out success case. The scores below come from separate development evaluation.";
  return "This is the saved E7 example 1 from the original exact-origin experiment. Its start differs from the continuous-model example. Do not use these different starts to visually rank the models.";
}
function mountDetail(id) {
  const m = models[indexOf(id)],
    e = payload.models[id],
    v = e.metrics,
    map = e.map,
    isES = v.scoreName === "Energy Score",
    grid = map ? `${map.gridSize}° ${isES ? "display bins" : "cells"}` : "";
  const caption = caseCaption(map);
  $("detail").innerHTML =
    `<div class="detail-heading"><p class="eyebrow">STEP 0${m.step} / ${stages[m.step - 1]}</p><h1>${m.title}</h1><p class="target">${isES ? "Complete seven-day endpoint distribution" : "Seven-day destination states · stopped at observed first exit"}</p></div>
 <div class="map-caption"><span class="pill">${map ? grid : "EVIDENCE GAP"}</span><span>${esc(caption)}</span></div>
 <aside class="method-panel"><p class="eyebrow">THE RESEARCH QUESTION</p><h2>${m.question}</h2><p class="method-copy">${m.description}</p><div><p class="formula-label">Model / estimator</p><div class="formula">${m.formula}</div></div><div><p class="formula-label">${isES ? "Energy Score · km" : "Brier Score · probability error"} ↓</p><div class="formula">${scoreFormula(v.scoreName)}</div><p class="score-note">${m.id.startsWith("mdn") ? "Trained with NLL. Evaluated with Energy Score." : isES ? "Distance-aware distribution score; lower is better." : "Evaluation score, not percentage accuracy."}</p></div><div class="finding"><strong>WHAT WE LEARNED</strong>${m.finding}</div></aside>
 ${map ? `<div class="map-key"><span><i class="r"></i>Release region R</span><span><i></i>${map.originKind === "exact" ? "Start" : "Departure cell"}</span>${map.truth ? '<span><i class="truth"></i>Observed day 7</span>' : ""}${map.region90 || map.regionCells90 ? '<span><i class="region"></i>Nominal 90% region</span>' : ""}</div><div class="scale-bar"><span>Probability per ${map.gridSize}° cell</span><div class="scale-gradient"></div><div class="scale-values"><span>0</span><span>${num(map.maxProbability * 100, 1)}%</span></div><small>Square-root colour scale</small></div><p class="map-note">${map.kind === "fitted" ? (v.score == null ? "Fitted illustration. Standalone validation scores are not reported." : "Fitted illustration. Scores below are from held-out development cases.") : isES ? "One fixed start; scores below cover 45 drifters. No trajectory is predicted." : "One held-out case. The scores below summarise the development cohort."}</p><span class="map-annotation r-label" id="r-label">R</span>` : `<div class="map-gap"><strong>Map export pending</strong><p>${esc(e.gap || "The quantitative results are available. A matching saved map has not yet been exported.")}</p></div>`}
 <div class="metrics">${metric(`${v.scoreName} ↓`, v.score, isES ? "km" : "", isES ? 2 : 4)}${metric("Observed 90% coverage", v.h90, "%")}${metric("Mean 90% region", v.size, v.sizeUnit, v.sizeUnit === "km²" ? 0 : 2)}</div>
 <div class="cohort-label"><strong>DEVELOPMENT EVALUATION · NOT FINAL TEST</strong>${esc(v.cohortLabel)}<br>Compare only within matching experiments.</div>
 <div class="detail-controls"><button id="back-models">↙ Back to models</button><div><button id="previous-model" ${indexOf(id) === 0 ? "disabled" : ""}>← Previous model</button><button id="next-model" ${indexOf(id) === models.length - 1 ? "disabled" : ""}>Next model →</button><button id="next-stage" class="next-stage">${m.step === 5 ? "Results & interpretation →" : `Step 0${m.step + 1} →`}</button></div></div>`;
  $("back-models").onclick = () => navigate("gallery", id);
  $("previous-model").onclick = () =>
    navigate("detail", models[Math.max(0, indexOf(id) - 1)].id);
  $("next-model").onclick = () =>
    navigate("detail", models[Math.min(models.length - 1, indexOf(id) + 1)].id);
  $("next-stage").textContent = "Continue presentation →";
  $("next-stage").onclick = () => storyStep(1);
  document.title = `${m.title} · Part 3 | Where Things End Up`;
}
function annotate() {
  if (!$("r-label")) return;
  const p = world.project([-79.1, 31.3]);
  $("r-label").style.left = `${p.x}px`;
  $("r-label").style.top = `${p.y}px`;
}
async function transition() {
  if (running) return;
  running = true;
  while (!current || key(current) !== key(desired)) {
    const target = { ...desired };
    stage.dataset.phase = "leaving";
    carousel.setEnabled(false);
    if (current && world.isPlaying()) await wait(350);
    // Incoming copy is hidden before its DOM is mounted; queued routes are consumed serially.
    stage.dataset.phase = "travelling";
    stage.dataset.view = target.view;
    $("gallery").hidden = target.view !== "gallery";
    $("detail").hidden = target.view !== "detail";
    if (target.view === "detail") mountDetail(target.id);
    else {
      carousel.select(indexOf(target.id), true);
      caption(indexOf(target.id));
      document.title = "Part 3 · The model collection | Where Things End Up";
    }
    await world.fly(target.view, target.id, {
      intro: !current && target.view === "gallery",
    });
    current = target;
    stage.dataset.model = target.id;
    if (key(target) !== key(desired)) continue;
    stage.dataset.phase = "arriving";
    annotate();
    if (world.isPlaying()) await wait(90);
    if (key(target) !== key(desired)) continue;
    stage.dataset.phase = "reading";
    carousel.setEnabled(target.view === "gallery");
  }
  running = false;
}
function request() {
  desired = route();
  transition();
}
function motion() {
  const p = world.isPlaying();
  $("motion").textContent = p ? "Ⅱ Pause" : "▷ Play";
  $("motion-status").textContent = p ? "LIVE OCEAN" : "MOTION PAUSED";
  document.body.classList.toggle("motion-paused", !p);
  carousel.setPlaying(p);
}
function scoringNotes() {
  const id = current?.view === "detail" ? current.id : models[selected].id,
    m = models[indexOf(id)],
    e = payload.models[id];
  $("notes-body").innerHTML =
    `<p class="eyebrow">PART 03 / EVIDENCE & SCORING</p><h2>${m.title}</h2><p>${m.description}</p><h3>What the map represents</h3><p>${esc(e.map?.label || e.gap)} ${esc(e.map?.displayNote || "")}</p><p>Map example and cohort-wide performance are different summaries. Keep the reported horizon, target, weighting and evaluation population together. Development validation is not an independent final test.</p>
 <h3>Which case is shown?</h3><p>${esc(caseCaption(e.map))}. ${esc(caseSelection(e.map))}</p>
 <h3>Model formula</h3><div class="formula">${m.formula}</div>${id === "endpoint-ci" ? "<p>EndpointCI preserves the historical donor endpoints and weights, spreading usable endpoints with their recorded position-error kernels. Missing or unusable errors retain their point mass. These observation-error clouds are not parameter confidence intervals or estimates of transport uncertainty. The pink boundary is the saved 90% predictive quantile ellipse, not an individual measurement-error contour.</p>" : ""}${id === "heading" ? "<p>Usable donor weights are proportional to 1 + 0.5(u<sub>query</sub> · u<sub>donor</sub>), renormalised within the usable subset. Unheaded donor mass is unchanged, then the annual/direction blend is applied.</p>" : ""}${id === "adaptive" ? "<p>λ<sub>i</sub> = ma / [(1 − a)N<sub>i</sub> + ma], where m is the median positive row count. Pair support is not a count of independent drifters. Unsupported origins do not automatically fall back to B1.</p>" : ""}
 <h3>Brier Score · discrete outcomes</h3><div class="formula">BS(p,y) = ∑<sub>j ∈ J</sub> (p<sub>j</sub> − 𝟙{y=j})<sup>2</sup></div><p>Lower is better; dimensionless. Not percentage accuracy. J includes the physical states of the experiment, including observed first exit E in the stopped grid task. B2 is estimated by count normalisation, not gradient descent on validation Brier.</p><p>Where unresolved prediction mass u is present, the failure-penalised score is S = 1 − 2p<sub>y</sub> + ∑p<sub>j</sub>² + u². It equals standard Brier when u = 0. U is not a physical destination.</p>
 <h3>Energy Score · continuous distributions</h3><div class="formula">ES(F,y) = 𝔼 d(X,y) − ½ 𝔼 d(X,X′)<br><small>X and X′ are independent draws from F.</small></div><p>Distances use WGS84 ECEF chord lengths in km. Lower is better. This is a distribution score, not a point forecast's mean distance error. Brier and ES are not interchangeable units.</p>
 <h3>MDN training objective · negative log-likelihood</h3><div class="formula">ℒ<sub>NLL</sub>(θ) = − 1/N ∑<sub>n</sub> log f<sub>θ</sub>(Δ<sub>n</sub> | x<sub>n</sub>)</div><p>Training uses pair-equal NLL. Continuous evaluation averages within drifter, then gives each drifter equal weight. The input is departure longitude and latitude only. East/north displacements in km become endpoints through the WGS84 forward geodesic; they are not added directly to longitude/latitude.</p>
 <h3>Nominal 90% is not observed 90%</h3><div class="formula">H<sub>90</sub> = ∑<sub>n</sub> w<sub>n</sub> 𝟙{y<sub>n</sub> ∈ A<sub>90</sub>(x<sub>n</sub>)} / ∑<sub>n</sub> w<sub>n</sub></div><p>Read coverage together with region size. Grid cell counts are not square kilometres. Continuous scores use the saved common quantile ellipse, not a highest-density region. Forecast mass over land, outside D and in the tails is retained.</p>
 <h3>Current evidence</h3><p>${esc(e.metrics.cohortLabel)}.</p>${e.gap ? `<p><strong>Remaining evidence:</strong> ${esc(e.gap)}</p>` : ""}<p>MDN22 is the frozen recommendation after development review, with MDN1 retained as comparator. The original strict acceptance did not pass. Its selection history remains unchanged; no further K search is performed.</p><p>These visualisations read existing frozen results. No fitting or final-test access is performed by this website. The 0.5° continuous-model bins come from fixed display-only samples, not a new model resolution.</p><p><a href="./assets/pt3/SOURCES.md" target="_blank" rel="noopener">Scientific sources and export provenance ↗</a> · <a href="./assets/pt3/data.json" download>Download displayed data ↓</a></p>`;
  $("notes").showModal();
}
fit();
addEventListener("resize", fit);
$("steps").innerHTML = stages
  .map((s, i) => `<button data-step="${i}"><b>0${i + 1}</b>${s}</button>`)
  .join("");
carousel = createCarousel($("cards"), caption, (i) =>
  navigate("detail", models[i].id),
);
carousel.setEnabled(false);
document
  .querySelectorAll("#steps button")
  .forEach(
    (b, i) => (b.onclick = () => carousel.select(indexOf(mainStops[i]))),
  );
$("story-prev").onclick = () => storyStep(-1);
$("story-next").onclick = () => storyStep(1);
$("rotate-prev").onclick = () => carousel.step(-1);
$("rotate-next").onclick = () => carousel.step(1);
$("open-model").onclick = () => navigate("detail", models[carousel.index()].id);
$("motion").onclick = () => {
  if (world) {
    world.toggle();
    motion();
  }
};
$("evidence").onclick = () => payload && scoringNotes();
document.querySelector(".dialog-close").onclick = () => $("notes").close();
addEventListener("keydown", (e) => {
  if (!world || $("notes").open || e.ctrlKey || e.metaKey || e.altKey) return;
  if (["ArrowRight", "ArrowLeft", "PageDown", "PageUp"].includes(e.key)) {
    e.preventDefault();
    const d = ["ArrowRight", "PageDown"].includes(e.key) ? 1 : -1;
    storyStep(d);
  } else if (e.key === "Escape") {
    e.preventDefault();
    navigate("gallery", desired.id);
  } else if (
    e.key === "Enter" &&
    desired.view === "gallery" &&
    !["BUTTON", "A"].includes(document.activeElement.tagName)
  ) {
    e.preventDefault();
    navigate("detail", models[carousel.index()].id);
  } else if (
    e.code === "Space" &&
    !["BUTTON", "A"].includes(document.activeElement.tagName)
  ) {
    e.preventDefault();
    world.toggle();
    motion();
  }
});
const clampIndex = (i) => Math.max(0, Math.min(models.length - 1, i));
// Readable transition QA: count incoming visible text only during actual camera travel.
function watch() {
  requestAnimationFrame(watch);
  if (world?.canvas.dataset.cameraMoving === "true") {
    const el = stage.dataset.view === "detail" ? $("detail") : $("gallery"),
      s = getComputedStyle(el);
    if (s.visibility !== "hidden" && Number(s.opacity) > 0.001) {
      stage.dataset.earlyTextFrames = String(++errors);
    }
  }
}
try {
  const [geo, res] = await Promise.all([
    fetch("./assets/pt2/data.json"),
    fetch("./assets/pt3/data.json?v=p3v3"),
  ]);
  if (!geo.ok || !res.ok) throw Error("Scientific payload unavailable");
  const geography = await geo.json();
  payload = await res.json();
  world = await createWorld($("world"), geography, payload);
  connectFlow(3, world, motion);
  $("loading").hidden = true;
  request();
  addEventListener("hashchange", request);
  requestAnimationFrame(watch);
} catch (e) {
  $("loading").hidden = true;
  $("error").hidden = false;
  console.error("Part 3 initialization", e);
}
