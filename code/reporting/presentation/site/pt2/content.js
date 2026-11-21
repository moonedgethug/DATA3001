import { annualChart, sstDiagram } from "./charts.js?v=p2v1";
export const names = [
  "Candidates",
  "Study corridor",
  "Region R",
  "Preprocessing",
  "Usable support",
];
export const focusNames = ["Drogue", "SST", "Motion", "Lifecycle"];
const header = (n, title, sub) =>
  `<div class="chapter-title"><p class="eyebrow">PART 02 / DATA & RESEARCH DESIGN <span>0${n}</span></p><h1>${title}</h1><p class="subtitle">${sub}</p></div>`;
const source = (s) => `<p class="source-note">${s}</p>`;
function regionRow(key, name, a, b, selected = false) {
  return `<div class="region-row ${selected ? "selected" : ""}" data-region="${key}"><div class="region-name">${name}${selected ? '<span class="selection">SELECTED · R</span>' : ""}</div><div class="row-numbers"><span><b>${a}</b> entering</span><span><b>${b}</b> with a 7-day pair</span></div></div>`;
}
export function focusContent(n) {
  return [
    `<p class="detail-kicker">01 / HARDWARE STATE</p><h2>The drogue matters.</h2><p class="detail-body">Check attachment and loss metadata against official records. Preserve what remains unknown.</p><div class="status-codes"><div><b>1</b><span>Drogued</span></div><div><b>0</b><span>Undrogued</span></div><div><b>−1</b><span>Unknown</span></div></div><p class="detail-note">An unknown loss date does not mean “undrogued”.</p>`,
    `<p class="detail-kicker">02 / SURFACE TEMPERATURE</p><h2>Keep estimates traceable.</h2><p class="detail-body">Preserve observations. Estimate gaps from official date-and-location SST fields.</p>${sstDiagram()}<p class="detail-note">Daily NOAA OISST background; not recovered hourly measurements.</p>`,
    `<p class="detail-kicker">03 / MOTION & TIMING</p><h2>Direction and timing.</h2><p class="detail-body">Retain native eastward <i>ve</i> and northward <i>vn</i>. Derive interval motion using actual timestamps.</p><div class="motion-equation">displacement <span>/</span> elapsed time</div><p class="detail-note">Negative velocity is valid. Do not invent missing positions or a zero first interval.</p>`,
    `<p class="detail-kicker">04 / LIFECYCLE</p><h2>Event-specific handling.</h2><div class="lifecycle-rules"><p><b>Confirmed recovery</b><span>Remove records after the valid last-good boundary.</span></p><p><b>Eventual grounding</b><span>Later SST → NA; retain position/time records for audit.</span></p><p><b>Uncertain state</b><span>Keep uncertainty. Low speed is not proof of grounding.</span></p></div><p class="detail-note">Last-good is not an exact physical event time.</p>`,
  ][n];
}
export function content(n, data) {
  if (n === 1)
    return (
      header(
        1,
        "A world of possible starting points.",
        "From candidate regions to a tractable transport study.",
      ) +
      `<div class="candidate-legend"><span><i class="dot audited"></i>Audited regions</span><span><i class="dot considered"></i>Considered locations</span></div><div class="world-caption"><span>GEOGRAPHIC CONTEXT</span><p>Application relevance.<br>Observational support.<br>A manageable first study.</p></div><div class="evidence-placeholder"><b>Evidence pending</b><span>Comparable quantitative audits for the other early candidates have not been located.</span></div>` +
      source(
        "Candidate locations are schematic. Quantitative screening is available for the Gulf–Bahamas–Gulf Stream corridor.",
      )
    );
  if (n === 2)
    return (
      header(
        2,
        "An application corridor.",
        "An original ambition, assessed against observational support.",
      ) +
      `<div class="region-panel"><p class="panel-label">HISTORICAL REGION SCREENING</p>${regionRow("gulf", "North-Central Gulf of Mexico", "288", "278")}${regionRow("bahamas", "Florida–Bahamas", "782", "736")}${regionRow("stream", "Gulf Stream Corridor", "1,117", "1,092")}<p class="panel-note">Offshore oil-and-gas activity informed the original motivation.</p></div><div class="map-caption"><span class="route-key"></span> Proposed study corridor <small>Scope illustration · not a validated transport path</small></div><div class="domain-caption">D <span>Early grid-model domain</span></div>` +
      source(
        "May 2025 six-hour GDP screening · Counts are distinct trajectories, not pair totals. Regions overlap; counts are not additive or a quality ranking.",
      )
    );
  if (n === 3)
    return (
      header(
        3,
        "A focused pilot in the Southern Corridor.",
        "A deliberate scope choice, supported by usable observations.",
      ) +
      `<div class="region-panel segment-panel"><p class="panel-label">THREE GULF STREAM WINDOWS</p>${regionRow("north", "Northern Offshore Extension", "688", "678")}${regionRow("hatteras", "Cape Hatteras Separation", "784", "766")}${regionRow("south", "Southern Coastal Segment", "621", "605", true)}<p class="panel-note">Chosen for scope, application continuity and support—not the largest sample count.</p></div><div class="region-caption"><b>R</b><div>Our departure region<span>Initial grid: 1° cells</span></div></div>` +
      source(
        "Historical six-hour screening · Real corridor-intersection boundaries. The later models use 0.5° grids and continuous starting positions.",
      )
    );
  if (n === 4)
    return (
      header(
        4,
        "From raw records to traceable observations.",
        "Follow the instrument. Separate observations, estimates and uncertain states.",
      ) +
      `<section class="cleaning-panel" id="cleaning-panel">${focusContent(0)}</section><div class="instrument-caption">SURFACE DRIFTER <span>Illustrative cutaway · not to scale</span></div><div class="cleaning-controls" role="tablist" aria-label="Preprocessing topics">${focusNames.map((s, i) => `<button role="tab" data-focus="${i}" aria-selected="${i === 0}"><span>0${i + 1}</span>${s}</button>`).join("")}</div><div class="quality-strip"><span>ALSO CHECKED</span>Time · Position · Duplicates · Gaps · Measurement uncertainty</div>` +
      source(
        "Cleaning creates a reusable observation record. The final MDN uses starting longitude and latitude only.",
      )
    );
  return (
    header(
      5,
      "How much usable support do we have?",
      "Different drifters and repeated seven-day pairs tell different stories.",
    ) +
    `<section class="chart-surface">${annualChart(data.annual)}<aside class="chart-aside"><p class="panel-label">BEFORE 2001</p><div class="early-number">2 <span>drifters</span></div><p>347 seven-day pairs.<br>Sparse support for this task.</p><div class="chart-legend"><span><i style="background:#94a4aa"></i>Before 2001</span><span><i style="background:#267f95"></i>2001–2019 fit window</span><span><i style="background:#bd8d48"></i>2020–2022 validation</span></div><p class="chart-caveat">2022 is an incomplete year.<br>IDs may recur across years.</p></aside></section><div class="final-split"><div class="split-intro">FINAL CONTINUOUS MODEL<span>After whole-ID separation<br>and boundary exclusions</span></div><div><strong>338</strong><span>fit drifters · 2001–2019<br><b>265,393</b> seven-day pairs</span></div><div><strong>45</strong><span>development-validation drifters<br><b>33,971</b> pairs · 2020–2022</span></div><a href="./pt3.html#gallery/b2" data-part3="true">Next: modelling <span>→</span></a></div>` +
    source(
      "Bars: historical eligible R development labels, before final split exclusions. Final test remains sealed. Sources and aggregate CSVs: Evidence & notes.",
    )
  );
}
export function labels(n) {
  if (n === 1)
    return (
      '<svg id="world-lines" viewBox="0 0 1920 1080" aria-hidden="true"></svg>' +
      [
        ["kuroshio", "Upstream Kuroshio", "Considered"],
        ["california", "California Current", "Considered"],
        ["central", "Central North Atlantic", "Considered"],
        ["sargasso", "Western Sargasso", "Considered"],
        ["florida", "Florida–Bahamas", "Audited"],
        ["gulfstream", "Gulf Stream", "Audited"],
      ]
        .map(
          ([id, name, status]) =>
            `<div class="geo-label ${status.toLowerCase()}" id="label-${id}"><i></i><span>${name}<small>${status}</small></span></div>`,
        )
        .join("")
    );
  if (n === 2 || n === 3)
    return `<svg id="map-lines" viewBox="0 0 1920 1080" aria-hidden="true"></svg><span class="ocean-word">NORTH ATLANTIC</span>`;
  if (n === 4)
    return `<svg id="callout-line" viewBox="0 0 1920 1080" aria-hidden="true"><path/><circle r="7"/></svg><span class="axis-label" id="axis-east">ve · EAST</span><span class="axis-label" id="axis-north">vn · NORTH</span>`;
  return "";
}
