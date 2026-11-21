export const sceneNames = [
  "The question",
  "Research region",
  "Original proposal",
  "Literature",
  "Why it matters",
];
function proposalMap(data) {
  const merc = (lat) =>
    (Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) * 180) / Math.PI;
  const scale = 19.7,
    px = (lon) => (lon + 99) * scale,
    py = (lat) => 282 - (merc(lat) - merc(21)) * scale;
  const path = (ring) =>
    ring
      .map(
        ([lon, lat], i) =>
          `${i ? "L" : "M"}${px(lon).toFixed(1)},${py(lat).toFixed(1)}`,
      )
      .join(" ") + "Z";
  const n = [px(-90), py(28.8)],
    f = [px(-79.8), py(26.4)],
    s = [px(-74.7), py(33)];
  return `<svg viewBox="0 0 880 290" role="img" aria-label="Original research scope: northern Gulf of Mexico, Florida–Bahamas and Gulf Stream; not a predicted trajectory"><defs><clipPath id="proposal-map-clip"><rect width="880" height="290"/></clipPath></defs><g clip-path="url(#proposal-map-clip)"><rect width="880" height="290" fill="#c7d5c7"/>${data.land.map((r) => `<path d="${path(r)}" fill="#e8ddbc" stroke="#a59f7b" stroke-width="1.2"/>`).join("")}<path class="scope-route" d="M ${n} C ${n[0] + 70} ${n[1] + 55},${f[0] - 90} ${f[1] + 45},${f} S ${s[0] - 35} ${s[1] + 55},${s}" fill="none" stroke="#527f77" stroke-width="4" stroke-dasharray="7 7"/><g fill="#8d693a">${[n, f, s].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="6"/>`).join("")}</g><g fill="#465a52" font-size="23" font-family="Arial"><text x="${n[0] + 14}" y="${n[1] - 21}" text-anchor="middle">Northern Gulf of Mexico</text><text x="${f[0] + 45}" y="${f[1] + 57}" text-anchor="middle">Florida–Bahamas</text><text x="${s[0] + 16}" y="${s[1] + 17}">Gulf Stream</text></g></g></svg>`;
}
export function content(n, data) {
  if (n === 1)
    return `<section class="hero-copy"><p class="eyebrow">UNSW DATA3001 · FINAL PRESENTATION</p><h1>Where Things<br>End Up</h1><p class="hero-region">in the Southern<br>Gulf Stream Corridor</p><p class="hero-subtitle">Predicting the 7-day endpoint probability distribution<br>of drifters starting from our research region.</p></section><aside class="team"><p>S01-G04</p><span>Junxi Xiao</span><span>Mingyue Zhu</span><span>Han Wang</span><span>Yicheng Zhang</span></aside><nav class="roadmap" aria-label="Presentation roadmap"><a href="#01"><small>01 / QUESTION</small><strong>Research Aim<br>& Background</strong></a><a href="./pt2.html#01"><small>02 / DATA</small><strong>Data Audit<br>& Research Design</strong></a><a href="./pt3.html#gallery/b2"><small>03 / MODELLING</small><strong>Modelling</strong></a><a href="./pt4.html#01"><small>04 / RESULTS</small><strong>Results & Limitations</strong></a></nav><p class="scene-disclosure">Illustrative sea and drifter · motion is not a model forecast</p>`;
  if (n === 2)
    return `<section class="map-copy"><p class="eyebrow">OUR COMPLETED CORE STUDY</p><h1>Starting from R,<br>where might drifters<br>end up in 7 days?</h1><p>Given the starting location of a single drifter,<br>what is its <strong>endpoint probability distribution</strong><br>after 7 days?</p><p class="scope-note">Southern Gulf Stream Corridor<br>R: the research release region</p></section><div class="map-key"><i></i>Original study boundary R</div><p class="scene-disclosure">Geographic context · probability estimates are presented in the results section</p>`;
  if (n === 3)
    return `<section class="proposal-intro"><p class="eyebrow">WEEK 1 / THE ORIGINAL QUESTION</p><h1>Starting with a<br>bigger question.</h1><p>At first, we wanted to look<br>further ahead.</p><span class="original-scope">Original idea · within 365 days</span></section><article class="proposal-paper"><p class="paper-kicker">THE FIRST PROPOSAL</p><h2>Starting in the northern Gulf of Mexico,</h2><p class="paper-question">where could drifters go<br>within <b>365 days</b>?</p><div class="proposal-map">${proposalMap(data)}</div><span class="paper-caption">Initial research scope · not a predicted trajectory</span><p class="paper-closing">With limited time and computing resources,<br>we focused our core task on <strong>7-day endpoint prediction<br>in the Southern Gulf Stream Corridor.</strong></p></article><p class="scene-disclosure">Reformatted from the confirmed Week 1 idea · not a scan of the original document</p>`;
  if (n === 4)
    return `<section class="book-intro"><p class="eyebrow">THE IDEAS BEHIND OUR STUDY</p><h1>From observed transport to continuous probabilities.</h1></section><div class="book-page" id="left-page"><p class="page-label">CORE REFERENCES</p><article class="core-reference"><p class="reference-author">Brolly · 2023</p><h2><a href="https://arxiv.org/abs/2303.11480" target="_blank" rel="noopener">Inferring Ocean Transport Statistics with Probabilistic Neural Networks</a></h2><p><b>Study</b> Learn surface-drifter transport probabilities from GDP trajectories.</p><p><b>Our use</b> Position-conditioned Gaussian and MDN probability models.</p></article><article class="core-reference"><p class="reference-author">Miron et al. · 2017</p><h2><a href="https://arxiv.org/abs/1703.10684" target="_blank" rel="noopener">Lagrangian Dynamical Geography of the Gulf of Mexico</a></h2><p><b>Study</b> Identify transport provinces and connectivity in the Gulf of Mexico.</p><p><b>Our use</b> Empirical Markov transition matrices from drifter trajectories.</p></article></div><div class="book-page" id="right-page"><p class="page-label">TECHNICAL GUIDES</p><article class="technical-reference"><h2>Chamberlain et al. <span>2023</span></h2><p>Grid size, time step and<br>the accumulation of error.</p></article><article class="technical-reference"><h2>O’Malley et al. <span>2021</span></h2><p>Change grid placement;<br>check sensitivity to boundaries.</p></article><article class="technical-reference"><h2>Pope et al. <span>2020</span></h2><p>Forget older transitions<br>to adapt to temporal change.</p></article><p class="page-footnote">Design references. Unimplemented branches are not reported as completed models.</p></div>`;
  return `<section class="application-title"><p class="eyebrow">WHY DESTINATIONS MATTER</p><h1>Why study where floating objects go?</h1><p>A foundation for ocean search, floating-object prediction and environmental risk research.</p></section><div class="triptych-rule first"></div><div class="triptych-rule second"></div><div class="application-labels"><section><small>SEARCH & RESCUE</small><h2>Humanitarian<br>search & rescue</h2><p>A foundation for understanding<br>possible search areas</p></section><section><small>FLOATING OBJECTS</small><h2>Floating-object<br>prediction</h2><p>Describe where objects<br>may be transported</p></section><section><small>MARINE POLLUTION</small><h2>Pollutant-dispersion<br>research</h2><p>Understand potential impact<br>areas and uncertainty</p></section></div><p class="scene-disclosure">Illustrative applications · current validation concerns drifters</p>`;
}
