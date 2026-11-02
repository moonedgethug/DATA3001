"""English B2 report and descriptive candidate maps; no model selection."""
from html import escape
import json

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import shape, box

from data3001.modelling.common.plotting import _rings, markdown_table
from data3001.modelling.common.runtime import save_frame


def probability_map(distribution, origin, horizon, support, maximum, land, release, domain):
    width, height = 1200, 740
    left, top, w, h = 65, 145, 1065, 475
    x0, x1, y0, y1 = -83., -6., 19., 56.

    def xy(lon, lat):
        return left + (lon-x0)/(x1-x0)*w, top + (y1-lat)/(y1-y0)*h

    def path(rings):
        return " ".join("M" + " L".join(f"{x:.2f},{y:.2f}" for x,y in [xy(*p) for p in ring]) + " Z" for ring in rings)

    def color(value):
        t = min(1., value / maximum) if maximum else 0.
        return f"rgb({int(238-208*t)},{int(246-151*t)},{int(253-99*t)})"

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="#ffffff"/>',
             '<g font-family="Arial, sans-serif" fill="#17334a">',
             f'<text x="35" y="38" font-size="25">Standard B2 | {horizon}-day destination probabilities</text>',
             '<text x="35" y="65" font-size="15">All-development candidate illustration | annual pooled | stopped first-exit target</text>',
             f'<text x="35" y="91" font-size="14">Origin cell {origin} | {int(support.training_id_count)} contributing IDs | {int(support.training_pair_count):,} eligible pairs</text>',
             '<text x="35" y="116" font-size="13">Descriptive fitted distribution; this map is not held-out validation. Same probability scale for both horizons.</text>',
             f'<rect x="{left}" y="{top}" width="{w}" height="{h}" fill="#f5f9fc" stroke="#a6b8c4"/>']
    for cell, probability in distribution.items():
        if cell < 0 or probability <= 0:
            continue
        lon, lat = cell % 360 - 180, cell // 360 - 90
        x, y = xy(lon, lat+1)
        parts.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w/(x1-x0):.3f}" height="{h/(y1-y0):.3f}" fill="{color(probability)}"/>')
    parts.append(f'<path d="{path(land)}" fill="#e0e3e3" fill-rule="evenodd" stroke="#8c999f" stroke-width="0.5"/>')
    parts.append(f'<path d="{path(domain)}" fill="none" stroke="#708b9c" stroke-dasharray="4 3" stroke-width="1"/>')
    parts.append(f'<path d="{path(release)}" fill="none" stroke="#007847" stroke-width="1.5"/>')
    x, y = xy(origin % 360 - 180, origin // 360 - 90 + 1)
    parts.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w/(x1-x0):.3f}" height="{h/(y1-y0):.3f}" fill="none" stroke="#d84b23" stroke-width="2"/>')
    for lon in [-80, -60, -40, -20, -10]:
        x, y = xy(lon, y0)
        parts.append(f'<text x="{x-14:.1f}" y="{y+20:.1f}" font-size="12">{abs(lon)} W</text>')
    for lat in [20, 30, 40, 50]:
        x, y = xy(x0, lat)
        parts.append(f'<text x="{x-40:.1f}" y="{y+4:.1f}" font-size="12">{lat} N</text>')
    for i in range(100):
        parts.append(f'<rect x="{780+i*3}" y="657" width="3.1" height="12" fill="{color(maximum*i/99)}"/>')
    parts += ['<text x="780" y="690" font-size="12">0</text>',
              f'<text x="1015" y="690" font-size="12">{maximum*100:.2f}% / cell</text>',
              f'<text x="35" y="666" font-size="14">E: {distribution.get(-2,0)*100:.3f}% | unresolved: {support.unresolved_mass*100:.3f}% | in-domain mass: {sum(p for c,p in distribution.items() if c>=0)*100:.3f}%</text>',
              '<text x="35" y="692" font-size="12">Orange: release cell. Green: R. Dashed: D. No probability renormalisation.</text>',
              '<text x="35" y="722" font-size="11">Cell probability, not density or grounding. Equirectangular display; grey land may obscure coastal cell fills.</text>',
              '</g></svg>']
    return "".join(parts)


def write_report(paths, run, config, summary, intervals, candidate, origins, destinations, verification):
    support_rows = []
    for h, part in candidate.support.groupby("horizon_days"):
        details = part.merge(origins[["cell", "R_positive_area", "R_boundary_only"]], left_on="origin_cell_1", right_on="cell", validate="one_to_one")
        support_rows.append({"horizon_days": h, "indexed_source_rows": len(part),
                             "supported_rows": int(part.supported.sum()),
                             "unsupported_rows": int((~part.supported).sum()),
                             "unsupported_positive_area_rows": int((~details.supported & details.R_positive_area).sum()),
                             "boundary_only_rows": int(details.R_boundary_only.sum())})
    support_table = pd.DataFrame(support_rows)
    save_frame(paths, run["results"] / "candidate_support_summary.csv", support_table)
    support_pivot = candidate.support.pivot(index="origin_cell_1", columns="horizon_days", values="training_id_count")
    ranking = support_pivot.min(axis=1).sort_index().sort_values(ascending=False, kind="stable")
    illustrations = []
    chosen = int(ranking.index[0]) if len(ranking) and ranking.iloc[0] > 0 else None
    if chosen is not None:
        selected = candidate.transitions.loc[candidate.transitions.origin_cell_1.eq(chosen)]
        maximum = float(selected.probability.max())
        release = shape(json.loads(paths.asset("release_R").read_text())["features"][0]["geometry"])
        domain = shape(json.loads(paths.asset("transport_D").read_text())["features"][0]["geometry"])
        land = shapely.from_wkb(paths.asset("land_mask_intermediate").read_bytes())
        land = land.intersection(box(-83, 19, -6, 56)).simplify(.025, preserve_topology=True)
        for h in (7, 30):
            row = candidate.support.loc[candidate.support.origin_cell_1.eq(chosen) & candidate.support.horizon_days.eq(h)].iloc[0]
            part = selected.loc[selected.horizon_days.eq(h)]
            svg = probability_map(dict(zip(part.destination_cell_1, part.probability)), chosen, h, row, maximum,
                                  _rings(land), _rings(release), _rings(domain))
            name = f"probability_{h}d.svg"
            paths.publish(run["results"] / name, lambda stream, content=svg: stream.write(content.encode()))
            illustrations.append((h, name))
    view = summary[["horizon_days", "eligible_pairs", "eligible_ids", "evaluable_pairs", "unsupported_pairs", "brier"]].copy()
    ci = intervals.loc[intervals.metric.eq("brier")].set_index("horizon_days")
    view["Brier_95_interval"] = [f"[{ci.loc[h,'lower_95']:.6f}, {ci.loc[h,'upper_95']:.6f}]" for h in view.horizon_days]
    zero_view = summary[["horizon_days", "availability", "zero_true_probability_pairs", "zero_true_probability_fraction", "observed_exit_pairs", "mean_predicted_exit_probability"]]
    narrative = (
        "B2 estimates a separate empirical row for each origin cell and horizon, "
        "P_h(i,j)=N_h(i,j)/sum_k N_h(i,k). Only fitting IDs contribute counts. "
        "There is no smoothing, fallback, optimisation, propagation or velocity/environmental conditioning. "
        "The target is first observed exit from D followed by absorption in E; missing follow-up is not an exit."
    )
    limitations = [
        "These are five-fold whole-ID development results on previously used development data, not an independent final-test evaluation. The final test remains locked.",
        "Brier is the unnormalised multiclass score (range 0 to 2). It is not an accuracy percentage and does not measure geographic distance. No spatial or combined loss is included.",
        "The mean Brier denominator contains only evaluable pairs. Unsupported cases are retained in availability reporting with missing Brier. Zero probability at a true destination is scored normally.",
        "Hourly and overlapping pairs are correlated. Confidence intervals use 200 whole-ID resamples with fixed fitted forecasts; they do not include refitting or model-selection uncertainty.",
        "Sparse empirical zeros mean unobserved transitions in the fitting sample, not physical impossibility. Do not interpret a small training count as strong evidence.",
        "No observed exits means exit calibration cannot be established. E remains in the state universe even if its count is zero.",
        "Source rows include boundary-only R intersections. Empty index rows are distinct from unsupported forecasts on actual held-out cases; neither is hidden.",
        "All-development matrices and maps are fitted candidates. They have no separate validation score and do not demonstrate geographic accuracy or superiority to another model.",
    ]
    artifact_links = ["summary.csv", "cell_summary.csv", "fold_summary.csv", "row_support.csv",
                      "candidate_support_summary.csv", "source_index.csv", "destination_index.csv",
                      "heldout_predictions.parquet", "heldout_scores.parquet", "bootstrap_intervals.csv",
                      "bootstrap_draws.csv", "counts_by_id.parquet", "folds.csv", "fitting_ids.json", "config.json"]
    md = ["# Stage 1 — Independent Standard B2", "",
          f"Run: `{run['results'].name}`. Engineering plan E2. Result submitted for user review; S1 closure is pending.", "",
          "## Model and evaluation", "", narrative, "",
          f"The frozen indexes contain {len(origins)} source rows and {len(destinations)+1} physical destination states ({len(destinations)} D cells plus E). Ten fold matrices and two all-development matrices are saved under `matrices/`. Unresolved is separate metadata, never a physical column.", "",
          "All predictions and scores were generated in this run. Reused artifacts are limited to verified qualified counts/labels, geometry and ID folds; no historical fitted models, predictions or scores were input.", "",
          "## Held-out development results", "", markdown_table(view, list(view.columns)), "",
          "Brier intervals are 2.5/97.5 percentiles of fixed-fit whole-ID bootstrap draws. Pair-weighted scores are pooled across folds, never averaged as five equally weighted fold means.", "",
          markdown_table(zero_view, list(zero_view.columns)), "",
          "Fractions use 0–1 units. Zero-true-probability fractions use evaluable pairs; exit counts cover all eligible pairs. Full denominators, IDs and unavailable counts are in `summary.csv`.", "",
          "## Training support in the all-development candidates", "", markdown_table(support_table, list(support_table.columns)), "",
          "## Descriptive probability maps", "",
          f"Selected origin: {chosen}. Selection used the largest minimum unique-ID support across 7/30 days, then ascending cell ID; no held-out scores were consulted." if chosen is not None else "No origin supports both horizons; paired maps are unavailable.", ""]
    for h, name in illustrations:
        md += [f"![{h}-day fitted candidate probabilities]({name})", ""]
    md += ["## Audit and limitations", "", f"Independent arithmetic audit: {json.dumps(verification, sort_keys=True)}", ""]
    md += [f"- {line}" for line in limitations]
    md += ["", "## Artifacts and reproduction", "", ", ".join(f"[{name}]({name})" for name in artifact_links), "",
           "Grouped held-out score rows retain `pair_count` as multiplicity; they are arithmetically equivalent to scoring every eligible hourly pair. Matrix tables contain positive entries; indexes and row-support masks define zero entries and undefined rows.", "",
           "```sh", ".venv/bin/python -B -m data3001.modelling.baselines.run_empirical_b2", "```", "",
           "To verify a fresh replay, add `--replay-of " + run["results"].name + "`. Each invocation creates a new immutable run. Provenance, input/code hashes and runtime verification are in the matching `provenance/runs/` directory.", ""]
    paths.publish(run["results"] / "REPORT.md", lambda stream: stream.write("\n".join(md).encode()))
    page = ["<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
            "<title>Stage 1 — Independent Standard B2</title><style>body{max-width:1180px;margin:40px auto;padding:0 24px;font:16px/1.55 system-ui;color:#17334a;background:#fff}h1{font-size:32px}h2{margin-top:36px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:9px;border-bottom:1px solid #d8e2e8;text-align:right}th{background:#edf4f8}img{width:100%}code{overflow-wrap:anywhere}.scroll{overflow:auto}li{margin:10px 0}a{color:#126b9d}</style>",
            "<h1>Stage 1 · Independent standard B2</h1>",
            f"<p><code>{escape(run['results'].name)}</code><br>Development validation · User review pending</p>",
            "<p>" + escape(narrative) + "</p><h2>Held-out results</h2><div class='scroll'>" + view.to_html(index=False, border=0) + "</div>",
            "<p>Standard Brier, lower is better. Intervals: 200 whole-ID bootstrap resamples with fixed fitted forecasts.</p>",
            "<div class='scroll'>" + zero_view.to_html(index=False, border=0, float_format=lambda x: f"{x:.6f}") + "</div>",
            "<h2>Candidate row support</h2>" + support_table.to_html(index=False, border=0),
            "<h2>Descriptive candidate maps</h2>"]
    page += [f"<img alt='{h}-day candidate probabilities' src='{name}'>" for h,name in illustrations]
    page += ["<h2>Interpretation and limitations</h2><ul>" + "".join("<li>"+escape(s)+"</li>" for s in limitations)+"</ul>",
             "<p><a href='REPORT.md'>Full report and reproduction</a> · <a href='summary.csv'>Summary CSV</a> · <a href='row_support.csv'>Row support</a></p></html>"]
    paths.publish(run["results"] / "review.html", lambda stream: stream.write("".join(page).encode()))
