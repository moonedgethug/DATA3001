const fmt = (n) => n.toLocaleString("en-US");
export function annualChart(rows) {
  const x0 = 78,
    step = 38,
    w = 24;
  const colors = (y) =>
    y < 2001 ? "#94a4aa" : y < 2020 ? "#267f95" : "#bd8d48";
  const bands = `<rect x="69" y="36" width="418" height="460" fill="#e2e7e5" opacity=".45"/><rect x="487" y="36" width="722" height="460" fill="#dbeeea" opacity=".36"/><rect x="1209" y="36" width="114" height="460" fill="#efe2cb" opacity=".6"/>`;
  const grid = [0, 20, 40, 60]
    .map(
      (n) =>
        `<line x1="69" x2="1323" y1="${248 - (n / 60) * 180}" y2="${248 - (n / 60) * 180}" class="grid"/><text x="52" y="${255 - (n / 60) * 180}" text-anchor="end">${n}</text>`,
    )
    .join("");
  const grid2 = [0, 25000, 50000]
    .map(
      (n) =>
        `<line x1="69" x2="1323" y1="${475 - (n / 55000) * 135}" y2="${475 - (n / 55000) * 135}" class="grid"/><text x="52" y="${482 - (n / 55000) * 135}" text-anchor="end">${n === 0 ? "0" : n / 1000 + "k"}</text>`,
    )
    .join("");
  const bars = rows
    .map((r, i) => {
      const x = x0 + i * step,
        h = (r.ids / 60) * 180,
        h2 = (r.pairs / 55000) * 135,
        desc = `${r.year}: ${r.ids} distinct drifters; ${fmt(r.pairs)} seven-day pairs${r.year === 2022 ? "; incomplete year" : ""}`;
      return `<g class="year-bars" tabindex="0" role="img" aria-label="${desc}"><title>${desc}</title><rect class="bar upper" style="--bar-delay:${i * 12}ms;transform-origin:${x}px 248px" x="${x}" y="${248 - h}" width="${w}" height="${h || 1.4}" rx="2" fill="${colors(r.year)}"/><rect class="bar lower" style="--bar-delay:${i * 12}ms;transform-origin:${x}px 475px" x="${x}" y="${475 - h2}" width="${w}" height="${h2 || 1.4}" rx="2" fill="${colors(r.year)}"/><rect class="hit" x="${x - 4}" y="50" width="32" height="428" fill="transparent"/>${[1990, 1995, 2000, 2001, 2005, 2010, 2015, 2020, 2022].includes(r.year) ? `<text class="year ${r.year === 2001 ? "boundary-year" : ""}" x="${x + w / 2}" y="512" text-anchor="middle">${r.year}</text>` : ""}</g>`;
    })
    .join("");
  return `<svg class="annual-chart" viewBox="0 0 1365 530" role="img" aria-label="Annual distinct drifters and eligible seven-day pairs, 1990 to 2022. Historical development inventory before final exclusions.">${bands}<text class="axis-title" x="69" y="24">DISTINCT DRIFTERS</text><text class="axis-title" x="69" y="309">ELIGIBLE 7-DAY PAIRS</text>${grid}${grid2}${bars}<line class="split" x1="487" x2="487" y1="36" y2="486"/><line class="split" x1="1209" x2="1209" y1="36" y2="486"/><text class="peak" x="888" y="81" text-anchor="middle">51</text><text class="year-note" x="1323" y="24" text-anchor="end">By departure year</text></svg>`;
}
export function sstDiagram() {
  return `<div class="sst-inset"><svg class="sst-diagram" viewBox="0 0 215 155" role="img" aria-label="Illustrative official SST product grid, separate from modelling cells"><path d="M34 30H180V125H34Z M34 30L108 77L180 125 M180 30L108 77L34 125" fill="none" stroke="#5d9ea8" stroke-width="1.5"/><g fill="#398997"><circle cx="34" cy="30" r="6"/><circle cx="180" cy="30" r="6"/><circle cx="34" cy="125" r="6"/><circle cx="180" cy="125" r="6"/></g><circle cx="108" cy="77" r="8" fill="#d89655"/></svg><div class="sst-caption">Official SST grid<span>Date + location<br>→ background estimate</span></div></div>`;
}
