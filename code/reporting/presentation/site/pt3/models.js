export const stages = [
  "Empirical baseline",
  "Global blending",
  "Spatial borrowing",
  "Exact origins",
  "Conditional density",
];
const defs = [
  [
    "b1",
    1,
    "Pooled baseline",
    "One shared destination distribution.",
    "What if we ignore the departure cell?",
    "Pool eligible historical outcomes across starts in R. Every supported query receives the same reference distribution.",
    "q<sub>j</sub> = ∑<sub>i</sub> N<sub>ij</sub> / ∑<sub>i</sub> N<sub>i</sub>",
    "Pooled evidence trades local detail for broader support.",
  ],
  [
    "b2",
    1,
    "Empirical transitions",
    "Count destinations, conditional on the start.",
    "What do past departures tell us?",
    "Group seven-day pairs by their departure cell. Normalise each row of observed destination counts.",
    "p<sub>ij</sub> = N<sub>ij</sub> / N<sub>i</sub>",
    "An unobserved transition is not a physically impossible destination.",
  ],
  [
    "fixed",
    2,
    "Fixed blend",
    "Balance local evidence and a global reference.",
    "How much information should we borrow?",
    "Blend the origin-specific B2 row with B1. Choose one borrowing weight within training data.",
    "p<sub>i</sub> = (1 − λ) B2<sub>i</sub> + λ B1",
    "The same borrowing weight is applied to supported departure cells.",
  ],
  [
    "adaptive",
    2,
    "Adaptive blend",
    "Let sample support guide the borrowing.",
    "Should sparse cells borrow more?",
    "Use a support-dependent weight: fewer historical pairs mean more borrowing from the pooled reference.",
    "p<sub>i</sub> = (1 − λ<sub>i</sub>) B2<sub>i</sub> + λ<sub>i</sub> B1",
    "No dependable advantage over Fixed; smaller regions also lost coverage.",
  ],
  [
    "local-endpoint",
    3,
    "Local endpoints",
    "Borrow actual destinations from nearby cells.",
    "Can nearby starts provide a better reference?",
    "Pool actual endpoints from eight adjacent departure cells, with donors starting in R. Blend with the local row.",
    "p<sub>i</sub> = (1 − a) B2<sub>i</sub> + a q<sub>neighbours,i</sub>",
    "Better Brier in this comparison came with a coverage trade-off.",
  ],
  [
    "local-displacement",
    3,
    "Path displacement",
    "Translate history, then check its geometry.",
    "Can historical motion transfer between cells?",
    "Translate each donor's whole path. Check land and domain boundaries; invalid transfer weight returns to B2.",
    "p<sub>i</sub> = (1 − a) B2<sub>i</sub><br>+ a (v<sub>i</sub> + r<sub>i</sub> B2<sub>i</sub>)",
    "This transfer rule did not improve on Fixed under the agreed checks.",
  ],
  [
    "seasonal",
    4,
    "Seasonal information",
    "Test when observations are informative.",
    "Does matching the season help?",
    "Compare season-conditioned evidence with the annual reference. A narrower donor pool also changes sample support.",
    "p<sub>i,s</sub> = (1 − α) p<sub>i,annual</sub><br>+ α p<sub>i,season s</sub>",
    "Tested seasonal schemes did not establish a stable benefit.",
  ],
  [
    "exact-point",
    4,
    "Exact origin",
    "Let the coordinate define the neighbourhood.",
    "What is lost inside a departure cell?",
    "Select historical starts within 100 km of the exact coordinate; at most 8,000 records. Retain their actual endpoints.",
    "p<sub>j</sub>(x) = 1/M(x)<br>× ∑<sub>k ∈ N(x)</sub> 𝟙(y<sub>k</sub> = j)",
    "Better probability scores and coverage required a larger search region.",
  ],
  [
    "endpoint-ci",
    4,
    "Endpoint uncertainty",
    "Test historical location-error spreading.",
    "Does accounting for endpoint error help?",
    "Keep historical endpoints and weights. Spread each endpoint using its recorded location error; combine the clouds into a predictive distribution.",
    "f(y | x) = ∑<sub>k</sub> w<sub>k</sub> K<sub>k</sub>(y)",
    "Location-error clouds did not establish a practically useful gain.",
  ],
  [
    "local-gaussian",
    5,
    "Local Gaussian",
    "Fit one continuous local distribution.",
    "Can a smooth density describe the endpoint cloud?",
    "Fit a local mean and covariance in east/north kilometres. Convert the density back to geographic endpoints.",
    "f(Δ | x) = 𝒩(Δ; μ<sub>x</sub>, Σ<sub>x</sub>)",
    "One smooth density provides a simple continuous comparison.",
  ],
  [
    "local-gmm",
    5,
    "Local mixture",
    "Test multiple local density components.",
    "Does a more flexible local mixture help?",
    "Fit local Gaussian mixtures with K = 1, 2 or 3. Training-only selection chose K = 1.",
    "f(Δ | x) = ∑<sub>k</sub> π<sub>k,x</sub><br>× 𝒩(Δ; μ<sub>k,x</sub>, Σ<sub>k,x</sub>)",
    "The selected local mixture equals LocalGaussian in this experiment.",
  ],
  [
    "mdn1",
    5,
    "MDN · one component",
    "Learn a shared position-conditioned distribution.",
    "Can different starts share what they learn?",
    "One network maps departure longitude and latitude to a displacement mean and covariance. Convert the displacement to a geographic endpoint.",
    "f<sub>θ</sub>(Δ | x) = 𝒩(Δ; μ<sub>θ</sub>(x), Σ<sub>θ</sub>(x))",
    "A shared network is different from fitting one Gaussian per query.",
  ],
  [
    "mdn22",
    5,
    "MDN · 22 components",
    "Our frozen development recommendation.",
    "How does the distribution change with location?",
    "One network maps longitude and latitude to mixture weights, means and covariances.",
    "f<sub>θ</sub>(Δ | x) = ∑<sub>k=1</sub><sup>22</sup> π<sub>k</sub>(x)<br>× 𝒩(Δ; μ<sub>k</sub>(x), Σ<sub>k</sub>(x))",
    "A development-review recommendation; original strict acceptance did not pass.",
  ],
];
export const models = defs.map(
  ([id, step, title, tagline, question, description, formula, finding]) => ({
    id,
    step,
    title,
    tagline,
    question,
    description,
    formula,
    finding,
  }),
);
export const mainStops = [
  "b2",
  "fixed",
  "local-endpoint",
  "exact-point",
  "mdn22",
];
export const scoreFormula = (name) =>
  name?.toLowerCase().includes("energy") || name === "ES"
    ? "ES(F,y) = 𝔼 d(X,y)<br>− ½ 𝔼 d(X,X′)"
    : "BS(p,y) = ∑<sub>j</sub> (p<sub>j</sub> − 𝟙{y=j})<sup>2</sup>";
export function art(step, index = 0) {
  const dots = Array.from({ length: 22 }, (_, i) => {
    const a = i * 2.4 + index * 0.15,
      r = 15 + Math.sqrt(i) * 10;
    return `<circle cx="${120 + Math.cos(a) * r}" cy="${70 + Math.sin(a) * r * 0.66}" r="${2 + (i % 3)}" fill="${i % 4 ? "#3f7e85" : "#bf854a"}" opacity="${0.4 + (i % 5) * 0.12}"/>`;
  }).join("");
  const grid = Array.from(
    { length: 7 },
    (_, i) => `<path d="M${45 + i * 25} 12V130 M45 ${15 + i * 19}H195"/>`,
  ).join("");
  const shape =
    step === 1
      ? `<g stroke="#547e7d" stroke-width=".8" opacity=".4">${grid}</g>${dots}`
      : step === 2
        ? `<ellipse cx="98" cy="70" rx="48" ry="43" fill="#428b8a" opacity=".3"/><ellipse cx="145" cy="70" rx="48" ry="43" fill="#cfac62" opacity=".35"/>${dots}`
        : step === 3
          ? `<g stroke="#547e7d" stroke-width=".8" opacity=".3">${grid}</g><path d="M65 107Q90 90 105 72T169 36 M88 123Q110 108 128 88T192 52" fill="none" stroke="#3f7e85" stroke-width="3"/><path d="M103 68l24 17" stroke="#bf854a" stroke-width="2" stroke-dasharray="3 4"/>`
          : step === 4
            ? `<circle cx="120" cy="70" r="53" fill="none" stroke="#438a88" stroke-dasharray="3 5"/><g class="orbit">${dots}</g><circle cx="120" cy="70" r="7" fill="#bf854a"/><path d="M120 7V27M120 113V133M57 70H77M163 70H183" stroke="#438a88"/>`
            : `<g fill="none" stroke="#3d7c83" stroke-width="1.5">${[1, 2, 3, 4].map((i) => `<ellipse cx="${106 + i * 3}" cy="${76 - i * 2}" rx="${i * 15}" ry="${i * 10}" transform="rotate(-24 120 70)"/>`).join("")}</g>${step === 5 && index > 11 ? '<g fill="none" stroke="#b78d55" opacity=".8"><ellipse cx="156" cy="55" rx="33" ry="24"/><ellipse cx="156" cy="55" rx="17" ry="13"/></g>' : ""}<circle cx="110" cy="74" r="4" fill="#315c68"/>`;
  return `<svg viewBox="0 0 240 145" aria-hidden="true">${shape}</svg>`;
}
export const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
