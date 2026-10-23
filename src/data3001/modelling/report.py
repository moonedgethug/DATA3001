"""Source-backed review of saved developmental nested-CV predictions.

The builder never reads trajectories, the final-test partition, or old model
tables. Its basemap uses the checksum-verified project geometry assets.
All reports are published as new artifacts through ProjectPaths.publish.
"""
from __future__ import annotations

from io import BytesIO
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from data3001.paths import file_sha256, project_paths


MODELS = ("B0", "B1", "B2", "Grid", "Analytic")
HORIZONS = (7, 30)
OUTSIDE = -2
DISPLAY_BOUNDS = (-84, 21, -42, 47)
LAND_SIMPLIFICATION_DEGREES = 0.035
_ROOT_ID = "data3001-nested-blend-review"


def _required(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{name} is missing columns: {sorted(missing)}")


def _json_safe(value):
    """Round display-only floats and reject nonstandard JSON numbers."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return round(float(value), 10) if math.isfinite(float(value)) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _records(frame: pd.DataFrame) -> list[dict]:
    return _json_safe(frame.to_dict("records"))


def _geometry(land_source: Path, region_source: Path) -> dict:
    """Use canonical geometry, simplifying only the clipped display land."""
    from shapely import from_wkb
    from shapely.geometry import MultiPolygon, box, mapping, shape
    from shapely.geometry.polygon import orient

    land = from_wkb(land_source.read_bytes()).intersection(box(*DISPLAY_BOUNDS))
    land = land.simplify(LAND_SIMPLIFICATION_DEGREES, preserve_topology=True)
    source = json.loads(region_source.read_text())
    region = shape(source["features"][0]["geometry"])
    if region.geom_type != "Polygon" or land.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Expected polygonal land and release-region geometry.")

    def geographic_winding(geometry):
        # d3-geo expects clockwise exterior rings for these small polygons.
        if geometry.geom_type == "Polygon":
            return orient(geometry, sign=-1)
        return MultiPolygon([orient(part, sign=-1) for part in geometry.geoms])

    def compact(value):
        if isinstance(value, dict):
            return {key: compact(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [compact(item) for item in value]
        return round(value, 4) if isinstance(value, float) else value

    # Quantization can reverse a very thin triangle or collapse an island.
    # Orienting before rounding is insufficient: d3 would interpret any
    # reversed exterior as a near-whole-globe complement. Apply the final
    # winding after quantization, and remove only zero-area display parts.
    quantized = shape(compact(mapping(land)))
    parts = list(quantized.geoms) if quantized.geom_type == "MultiPolygon" else [quantized]
    retained = []
    for part in parts:
        if part.area <= 1e-8:
            continue
        if not part.is_valid:
            raise ValueError("Coordinate rounding made a nondegenerate display polygon invalid.")
        retained.append(orient(part, sign=-1))
    if not retained:
        raise ValueError("No valid land polygons remain in the map bounds.")
    display_land = retained[0] if len(retained) == 1 else MultiPolygon(retained)
    display_region = geographic_winding(shape(compact(mapping(region))))
    return {
        "land": mapping(display_land),
        "region": mapping(display_region),
        "bounds": list(DISPLAY_BOUNDS),
        "geometry_display": {
            "land_asset": "land_mask_intermediate", "bounds": list(DISPLAY_BOUNDS),
            "land_simplification_degrees": LAND_SIMPLIFICATION_DEGREES,
            "preserve_topology": True, "region_simplified": False,
            "coordinate_decimals": 4, "winding_applied_after_rounding": True,
            "degenerate_land_parts_removed": len(parts) - len(retained),
        },
    }


def _default_origins(support: pd.DataFrame, folds: list[int]) -> dict[str, int]:
    """Choose displays using outer-training ID support, never held-out scores."""
    defaults = {}
    for fold in folds:
        subset = support.loc[support["outer_fold"].eq(fold)]
        pivot = subset.pivot(
            index="origin_cell_1", columns="horizon_days", values="independent_ids"
        ).reindex(columns=HORIZONS).fillna(0)
        if pivot.empty:
            raise ValueError(f"Outer fold {fold} has no training-origin support.")
        minimum = pivot.min(axis=1)
        defaults[str(fold)] = int(minimum.loc[minimum.eq(minimum.max())].index.min())
    return defaults


def _observed(counts: pd.DataFrame, folds: pd.DataFrame) -> dict:
    """Aggregate endpoints only from IDs held out in the displayed outer fold."""
    merged = counts.merge(folds, on="id", how="left", validate="many_to_one")
    if merged["outer_fold"].isna().any():
        raise ValueError("Development counts contain IDs without outer-fold assignments.")
    result = {}
    for (fold, days, origin), group in merged.groupby(
        ["outer_fold", "horizon_days", "origin_cell_1"], sort=True
    ):
        destinations = group.groupby("destination_cell_1")["pair_count"].sum()
        result[f"{int(fold)}:{int(days)}:{int(origin)}"] = {
            "n": int(group["pair_count"].sum()),
            "ids": int(group["id"].nunique()),
            "counts": [[int(cell), int(n)] for cell, n in destinations.items()],
        }
    return result


def _compact_models(models: dict, folds: list[int], support: pd.DataFrame) -> dict:
    """Losslessly pack empirical probabilities as integer counts / support.

    Every reconstructed probability must exactly match the saved forecast.
    This is a display encoding, not a newly fitted or normalized model.
    """
    output = {}
    for fold in folds:
        item = models[str(fold)]
        output[str(fold)] = {}
        for model in ("B1", "B2"):
            output[str(fold)][model] = {}
            for key, distribution in item[model].items():
                horizon = int(key.split(":")[0])
                rows = support.loc[support["outer_fold"].eq(fold) &
                                   support["horizon_days"].eq(horizon)]
                if model == "B2":
                    rows = rows.loc[rows["origin_cell_1"].eq(int(key.split(":")[1]))]
                n = int(rows["pair_count"].sum())
                packed = []
                for cell, probability in sorted(distribution.items(), key=lambda pair: int(pair[0])):
                    count = round(float(probability) * n)
                    if n <= 0 or count / n != float(probability):
                        raise ValueError("Saved empirical model cannot be losslessly encoded from training support.")
                    packed.append([int(cell), int(count)])
                output[str(fold)][model][str(key)] = {"n": n, "counts": packed}
    return output


def _fmt(value, digits=6, *, percent=False) -> str:
    if pd.isna(value):
        return "unavailable"
    if not np.isfinite(float(value)):
        return "infinity" if float(value) > 0 else "-infinity"
    return f"{100 * value:.2f}%" if percent else f"{value:.{digits}f}"


def _markdown_table(frame: pd.DataFrame, columns: list[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = []
    integer_columns = {"horizon_days", "outer_fold", "eligible_pairs", "independent_ids",
                       "unresolved_pairs", "zero_probability_pairs", "replicates"}
    for _, row in frame.iterrows():
        cells = []
        for key, _ in columns:
            value = row.get(key, np.nan)
            if isinstance(value, str):
                cells.append(value.replace("|", "\\|"))
            elif key in integer_columns and pd.notna(value):
                cells.append(str(int(value)))
            elif key == "forecast_coverage":
                cells.append(_fmt(value, percent=True))
            elif key.endswith("_pct"):
                cells.append(_fmt(value, 2) + ("%" if pd.notna(value) else ""))
            else:
                cells.append(_fmt(value))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, separator, *rows])


def _report_text(run_dir, receipt, summary, selection, final_selection,
                 bootstrap, sources, plots_available, defaults) -> str:
    main_columns = [
        ("horizon_days", "Horizon (days)"), ("model", "Model"),
        ("eligible_pairs", "Eligible pairs"), ("independent_ids", "Independent IDs"),
        ("forecast_coverage", "Complete forecast coverage"),
        ("brier_failure_penalized", "Failure-penalized Brier"),
        ("brier", "Ordinary Brier"), ("log_loss", "Log loss"),
        ("region90_hit_pct", "90% set hit rate"),
        ("region90_available_pct", "90% set availability"),
        ("mean_region90_cells", "Mean 90% set geographic cells"),
        ("zero_probability_pairs", "Zero-probability pairs"),
        ("top_cell_hit_pct", "Top-category hit rate"),
    ]
    selections = selection.sort_values(["horizon_days", "outer_fold", "method"])
    tuning_column = "tuning_brier" if "tuning_brier" in final_selection else "inner_brier"
    best_lines = []
    for days in HORIZONS:
        subset = summary.loc[summary["horizon_days"].eq(days)]
        best = subset.sort_values(["brier_failure_penalized", "model"]).iloc[0]
        best_lines.append(
            f"- {days} days: the smallest outer held-out failure-penalized Brier is "
            f"{_fmt(best['brier_failure_penalized'])} ({best['model']})."
        )
    interpretations = []
    for days in HORIZONS:
        by_model = summary.loc[summary["horizon_days"].eq(days)].set_index("model")
        base = by_model.loc["B2"]
        grid_row, analytic_row = by_model.loc["Grid"], by_model.loc["Analytic"]
        intervals = bootstrap.loc[bootstrap["horizon_days"].eq(days) &
                                  bootstrap["comparison"].isin(["Grid - B2", "Analytic - B2"])]
        interval_description = (
            "Both paired fixed-prediction intervals include zero."
            if len(intervals) == 2 and ((intervals["lower"] <= 0) & (intervals["upper"] >= 0)).all()
            else "Review the paired fixed-prediction intervals below for uncertainty."
        )
        relative = 100 * (base["brier_failure_penalized"] - analytic_row["brier_failure_penalized"]) / base["brier_failure_penalized"]
        interpretations.append(
            f"- At {days} days, the Analytic blend changes penalized Brier by "
            f"{analytic_row['brier_failure_penalized'] - base['brier_failure_penalized']:+.6f} "
            f"versus B2 ({relative:.3f}% relative reduction). {interval_description} "
            f"The 90% set hit rate changes from {base['region90_hit_pct']:.2f}% (B2) to "
            f"{grid_row['region90_hit_pct']:.2f}% / {analytic_row['region90_hit_pct']:.2f}% "
            f"(Grid / Analytic), while mean geographic set size changes from "
            f"{base['mean_region90_cells']:.2f} to {grid_row['mean_region90_cells']:.2f} / "
            f"{analytic_row['mean_region90_cells']:.2f} cells. Better set hit rate therefore "
            f"comes with a broader forecast region. The blends still assign zero "
            f"probability to {int(analytic_row['zero_probability_pairs']):,} eligible "
            f"realized endpoint pairs (Analytic), so log loss remains infinite."
        )
    config = receipt.get("config", {})
    text = f"""# Developmental nested-CV B1/B2 blend review

Run: `{run_dir.name}`. Dataset release: `{config.get('dataset_release', 'see run receipt')}`.

This is a developmental nested cross-validation experiment on the development
population. It is not a final-test result. Whole instrument IDs stay together
throughout the outer evaluation and inner weight selection. The final-test
partition was not used. These are nonseasonal pooled endpoint forecasts at
7 and 30 days only; they do not validate seasonal or longer-horizon prediction.
The release input is a 1-degree origin cell with the historical within-cell
release prior. It is not an exact point release, a uniform whole-region wet-area
release, or a rescue deployment forecast.

## Outer held-out comparison

Every model is evaluated on the same eligible outer held-out endpoint pairs.
Pair-count multiplicities retain equal eligible-pair weighting. Scores below
combine all outer held-out folds; IDs are the independent sampling units.
Brier and log loss are losses, so smaller is better. Coverage and set hit rates
are distinct quantities and must not be called predictive accuracy.

{_markdown_table(summary, main_columns)}

{chr(10).join(best_lines)}

{chr(10).join(interpretations)}

The failure-penalized Brier retains every eligible pair and scores unresolved
forecast mass as an explicit failure category. Ordinary Brier and log loss are
unavailable if any forecast in that summary is incomplete. A zero probability
on a realized endpoint gives infinite log loss; the report does not clip it.
The `outer_scores.csv` file retains log-loss bounds for incomplete forecasts.

The nominal 90% prediction set ranks physical outcome categories by probability,
includes all categories tied at the cutoff, and can therefore exceed 90% mass.
OUTSIDE (-2) is a physical category. Unresolved mass is separate. If known
probability mass is below 90%, the set is unavailable. Availability and hit-rate
denominators follow the saved scorer outputs; consult `outer_summary.csv` for
mean set mass and cell counts.

## What the five models mean

- B0 puts all mass on the release-origin cell.
- B1 uses the outer-training endpoint marginal for the chosen horizon, pooled over the historical eligible R-origin mixture.
- B2 also conditions on the release-origin cell; an unsupported origin retains
  unresolved mass rather than silently receiving a fallback distribution.
- Grid and Analytic use `(1 - lambda) * B2 + lambda * B1`. The Grid method
  chooses from 0, 0.1, ..., 1.0. Analytic minimizes the same inner out-of-fold
  quadratic failure-penalized Brier continuously over [0, 1].

The analytic optimum cannot have worse loss than the grid optimum on the same
inner tuning cases, up to numerical tolerance. That guarantee does not apply
to the independent outer held-out folds. A smaller inner loss can lose outside
the tuning sample.

## Weights selected inside each outer training population

These weights were selected without using the corresponding outer held-out IDs.

{_markdown_table(selections, [('outer_fold', 'Outer fold'), ('horizon_days', 'Horizon (days)'), ('method', 'Method'), ('lambda_value', 'Lambda'), ('inner_brier', 'Inner selection Brier')])}

## Final-development weights

These weights use base out-of-fold predictions from all development IDs for
tuning, then accompany bases fitted on all development IDs. Their tuning loss
is not an independent evaluation. The interactive observed panel deliberately
shows outer held-out folds only.

{_markdown_table(final_selection.sort_values(['horizon_days', 'method']), [('horizon_days', 'Horizon (days)'), ('method', 'Method'), ('lambda_value', 'Lambda'), (tuning_column, 'All-development tuning Brier')])}

## Paired uncertainty

The intervals below resample whole IDs and preserve all eligible-pair
multiplicities for each sampled ID. They are conditional on the fixed saved
outer predictions. They do not refit base models or repeat weight selection,
so they do not capture training or tuning variability. Negative deltas favor
the first model named in a comparison; verify the comparison label and saved
scope when interpreting each row.

{_markdown_table(bootstrap, [('horizon_days', 'Horizon (days)'), ('comparison', 'Comparison'), ('delta_brier', 'Brier difference'), ('lower', 'Interval lower'), ('upper', 'Interval upper'), ('replicates', 'Replicates'), ('scope', 'Scope')])}

## Probability maps and diagnostic plots

Open [the interactive comparison](comparison.html) for matched forecast and
held-out observed endpoint maps. Model, horizon, origin, and outer fold change
together. Both maps use one explicit percentage color scale and 1-degree
cells; there is no spatial interpolation. Off-map mass, OUTSIDE probability,
and unresolved mass remain separate from the visible cells. Colors do not
represent shares of a common color total.

The initial origin in each fold maximizes the minimum outer-training
independent-ID support across 7 and 30 days, breaking ties by ascending cell
ID. This choice uses no held-out performance. Defaults: {json.dumps(defaults, sort_keys=True)}.

"""
    if plots_available:
        text += ("![Outer held-out Brier comparison](outer-brier-comparison.png)\n\n"
                 "![Inner selection curves](lambda-selection-curves.png)\n\n")
    else:
        text += "Static PNG plots were omitted because matplotlib is unavailable.\n\n"
    text += """## Evidence and preservation

`report_sources.json` records SHA-256 hashes of the saved run inputs and
checksum-verified project geometry assets. Report generation reads the saved development counts,
fold assignments, model distributions, and score summaries. It does not access
raw tracks or final-test labels. Canonical data and historical model runs are
not modified. Display values are rounded; saved scoring outputs retain their
original precision. Land is clipped to bounds [-84, 21, -42, 47] and simplified
by 0.035 degrees with topology preservation for display only. The release-region
boundary is not simplified. Coordinates are rounded to four decimal places for
compact display; zero-area display fragments are removed and ring winding is
set after rounding. These operations never change scientific classification.

"""
    text += "\n".join(f"- `{name}`: `{details['sha256']}`" for name, details in sources.items())
    return text + "\n"


def _plot_bytes(summary, grid, selection) -> dict[str, bytes]:
    if importlib.util.find_spec("matplotlib") is None:
        return {}
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output = {}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), constrained_layout=True)
    for ax, days in zip(axes, HORIZONS):
        subset = summary.loc[summary["horizon_days"].eq(days)].set_index("model")
        values = [float(subset.loc[model, "brier_failure_penalized"]) for model in MODELS]
        ax.bar(MODELS, values, color="#3573a6")
        ax.set_title(f"{days}-day endpoint")
        ax.set_ylabel("Outer held-out failure-penalized Brier")
        ax.set_xlabel("Model")
        ax.set_ylim(0, max(values) * 1.16 if max(values) > 0 else 1)
        for index, value in enumerate(values):
            ax.annotate(f"{value:.5f}", (index, value), xytext=(0, 5),
                        textcoords="offset points", ha="center", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Developmental nested CV: matched outer held-out pairs")
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=160)
    plt.close(fig)
    output["outer-brier-comparison.png"] = buffer.getvalue()

    folds = sorted(int(value) for value in grid["outer_fold"].unique())
    fig, axes = plt.subplots(2, len(folds), figsize=(3.1 * len(folds), 6.4),
                             squeeze=False, constrained_layout=True)
    for row, days in enumerate(HORIZONS):
        for col, fold in enumerate(folds):
            ax = axes[row, col]
            subset = grid.loc[grid["outer_fold"].eq(fold) &
                              grid["horizon_days"].eq(days)].sort_values("lambda_value")
            ax.plot(subset["lambda_value"], subset["selection_brier"],
                    marker="o", color="#3573a6", label="Grid candidates", markersize=3)
            chosen = selection.loc[selection["outer_fold"].eq(fold) &
                                   selection["horizon_days"].eq(days)]
            for method, marker, color in (("Grid", "s", "#b97824"),
                                          ("Analytic", "D", "#3b8858")):
                selected = chosen.loc[chosen["method"].eq(method)].iloc[0]
                ax.scatter([selected["lambda_value"]], [selected["inner_brier"]],
                           marker=marker, color=color, label=method, zorder=3, s=35)
            ax.set_title(f"{days} days · outer fold {fold}")
            ax.set_xlabel("Lambda (B1 weight)")
            if col == 0:
                ax.set_ylabel("Inner selection Brier")
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax.spines[["top", "right"]].set_visible(False)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=3)
    fig.suptitle("Inner out-of-fold selection; these curves are not held-out evaluation")
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=160)
    plt.close(fig)
    output["lambda-selection-curves.png"] = buffer.getvalue()
    return output


_FRAGMENT = r'''<div id="data3001-nested-blend-review">
<style>
#data3001-nested-blend-review { color:var(--foreground); }
#data3001-nested-blend-review .blend-maps { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1.25rem; }
#data3001-nested-blend-review .blend-plot { min-width:0; }
#data3001-nested-blend-review .blend-map, #data3001-nested-blend-review .blend-curve { display:block; width:100%; overflow:visible; }
#data3001-nested-blend-review .blend-map text, #data3001-nested-blend-review .blend-curve text { fill:var(--foreground); font-size:12px; }
#data3001-nested-blend-review .blend-legend { display:flex; flex-wrap:wrap; gap:1rem; align-items:center; margin:.75rem 0; }
#data3001-nested-blend-review .blend-ramp { display:flex; align-items:center; gap:.35rem; }
#data3001-nested-blend-review .blend-ramp i { display:inline-block; width:1.8rem; height:.7rem; }
#data3001-nested-blend-review .blend-detail { margin:.65rem 0; }
#data3001-nested-blend-review .blend-table { width:100%; border-collapse:collapse; }
#data3001-nested-blend-review .blend-table th, #data3001-nested-blend-review .blend-table td { text-align:right; padding:.45rem .6rem; border-bottom:1px solid var(--border); white-space:nowrap; }
#data3001-nested-blend-review .blend-table th:first-child, #data3001-nested-blend-review .blend-table td:first-child { text-align:left; }
#data3001-nested-blend-review .blend-tooltip { position:absolute; pointer-events:none; padding:.5rem .7rem; color:var(--popover-foreground); background:var(--popover); z-index:2; max-width:18rem; }
#data3001-nested-blend-review .blend-swatch { display:inline-block; width:1.1rem; height:.75rem; vertical-align:middle; margin-right:.3rem; }
#data3001-nested-blend-review .blend-relative { position:relative; }
@media(max-width:680px) { #data3001-nested-blend-review .blend-maps { grid-template-columns:minmax(0,1fr); } }
</style>
<h2>Outer held-out endpoint comparison</h2>
<div class="viz-controls">
<label class="form-label">Model<select class="form-select" data-control="model"><option>B0</option><option>B1</option><option>B2</option><option>Grid</option><option selected>Analytic</option></select></label>
<label class="form-label">Horizon<select class="form-select" data-control="horizon"><option value="7">7 days</option><option value="30">30 days</option></select></label>
<label class="form-label">Outer held-out fold<select class="form-select" data-control="fold"></select></label>
<label class="form-label">Release-origin cell<select class="form-select" data-control="origin"></select></label>
</div>
<div class="blend-detail tabular-nums" data-detail="support" aria-live="polite"></div>
<div class="blend-relative">
<div class="blend-maps">
<section class="blend-plot"><h3 data-heading="forecast">Forecast probability</h3><svg class="blend-map" data-map="forecast" role="img" aria-label="Forecast endpoint probability by one-degree cell"></svg><div class="text-small tabular-nums" data-detail="forecast"></div></section>
<section class="blend-plot"><h3>Observed held-out endpoints</h3><svg class="blend-map" data-map="observed" role="img" aria-label="Endpoint frequency for the same held-out fold, horizon, and origin"></svg><div class="text-small tabular-nums" data-detail="observed"></div></section>
</div>
<div class="blend-tooltip text-small" role="tooltip" hidden></div>
</div>
<div class="blend-legend text-small"><span>Cell probability / frequency</span><span class="blend-ramp" data-legend="scale"></span><span><i class="blend-swatch" style="border:1px solid var(--foreground)"></i>90% set</span><span><i class="blend-swatch" style="border:1px dashed var(--foreground)"></i>Release region</span><span>+ Origin</span></div>
<div class="blend-detail text-small tabular-nums" data-detail="cell" aria-live="polite"></div>
<h3>Matched outer held-out scores</h3>
<div class="table-responsive"><table class="table table-sm blend-table"><caption class="sr-only">Scores for all outer folds at the selected horizon</caption><thead><tr><th>All folds</th><th>Pairs</th><th>IDs</th><th>Complete coverage</th><th>Penalized Brier ↓</th><th>Log loss ↓</th><th>90% set hit</th><th>90% set available</th><th>Mean set cells</th><th>Zero-probability pairs</th></tr></thead><tbody data-table="summary"></tbody></table></div>
<div class="text-small tabular-nums blend-detail" data-detail="fold-score"></div>
<h3>Inner selection curve</h3>
<div class="blend-plot blend-relative"><svg class="blend-curve" role="img" aria-label="Inner out-of-fold selection loss over the B1 mixing weight"></svg></div>
<div class="text-small blend-detail tabular-nums" data-detail="lambda"></div>
<script type="application/json" id="nested-blend-data">__PAYLOAD__</script>
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<script>
(() => {
 const root=document.getElementById('data3001-nested-blend-review');
 const D=JSON.parse(root.querySelector('#nested-blend-data').textContent);
 if(typeof d3==='undefined'){root.querySelector('[data-detail="support"]').textContent='The chart library could not load. Review REPORT.md and the saved CSV tables.';return;}
 const controls=Object.fromEntries(['model','horizon','fold','origin'].map(k=>[k,root.querySelector(`[data-control="${k}"]`)]));
 const percent=x=>Number.isFinite(x)?`${(100*x).toFixed(2)}%`:'unavailable';
 const number=x=>x===null||x===undefined?'unavailable':Number.isFinite(x)?Number(x).toFixed(6):'infinity';
 const coords=c=>[c%360-180,Math.floor(c/360)-90];
 const label=c=>{const [x,y]=coords(c);return `${c} · ${Math.abs(x).toFixed(0)}°${x<0?'W':'E'}, ${Math.abs(y).toFixed(0)}°${y<0?'S':'N'}`;};
 const asMap=item=>new Map((item?.counts||[]).map(([c,n])=>[Number(c),Number(n)/item.n]));
 const sum=m=>Array.from(m.values()).reduce((a,b)=>a+b,0);
 let state={model:'Analytic',horizon:7,fold:D.folds[0],origin:D.defaults[String(D.folds[0])]};
 let selectedCell=null,initial=true;
 controls.fold.replaceChildren(...D.folds.map(v=>new Option(String(v),String(v))));
 controls.origin.replaceChildren(...D.origins.map(v=>new Option(label(v),String(v))));
 function applySaved(saved){const s=saved?.privateContent?.selection||saved?.modelContent?.selection;if(!s)return; if(D.models.includes(s.model))state.model=s.model;if(D.horizons.includes(Number(s.horizon)))state.horizon=Number(s.horizon);if(D.folds.includes(Number(s.fold)))state.fold=Number(s.fold);if(D.origins.includes(Number(s.origin)))state.origin=Number(s.origin);}
 applySaved(window.openai?.widgetState);
 function sync(){Object.entries(state).forEach(([k,v])=>{controls[k].value=String(v);});}
 function save(){if(window.openai?.setWidgetState)window.openai.setWidgetState({modelContent:{selection:{...state},evaluation:'developmental outer held-out nested CV'},privateContent:{selection:{...state}}}).catch(()=>{});}
 function forecast(){const item=D.outerModels[String(state.fold)],b1=asMap(item.B1[String(state.horizon)]),b2=asMap(item.B2[`${state.horizon}:${state.origin}`]);let p,u=0,lambda=null;
  if(state.model==='B0')p=new Map([[state.origin,1]]);
  else if(state.model==='B1')p=b1;
  else if(state.model==='B2'){p=b2;u=Math.max(0,1-sum(b2));}
  else {const selected=D.selection.find(r=>r.outer_fold===state.fold&&r.horizon_days===state.horizon&&r.method===state.model);lambda=selected.lambda_value;p=new Map();for(const c of new Set([...b1.keys(),...b2.keys()]))p.set(c,(1-lambda)*(b2.get(c)||0)+lambda*(b1.get(c)||0));u=Math.max(0,(1-lambda)*(1-sum(b2))+lambda*(1-sum(b1)));}
  return {p,u,lambda};
 }
 function region(p){if(sum(p)<.9-1e-9)return {available:false,cells:new Set(),mass:0};const entries=Array.from(p.entries()).filter(([,v])=>v>0).sort((a,b)=>b[1]-a[1]||a[0]-b[0]);let mass=0,cut=Infinity;for(const [,v] of entries){mass+=v;cut=v;if(mass>=.9-1e-9)break;}const chosen=entries.filter(([,v])=>v>=cut-1e-12);return {available:true,cells:new Set(chosen.map(([c])=>c)),mass:chosen.reduce((s,[,v])=>s+v,0)};}
 function edgePath(cells,projection){const edges=new Map();for(const cell of cells){if(cell<0)continue;const [x,y]=coords(cell),points=[[x,y],[x+1,y],[x+1,y+1],[x,y+1]];for(let i=0;i<4;i++){const a=points[i],b=points[(i+1)%4],key=[a.join(','),b.join(',')].sort().join('|');if(edges.has(key))edges.delete(key);else edges.set(key,[a,b]);}}return Array.from(edges.values()).map(([a,b])=>{const p=projection(a),q=projection(b);return `M${p[0]},${p[1]}L${q[0]},${q[1]}`;}).join('');}
 function within(cell){if(cell<0)return false;const [x,y]=coords(cell),[w,s,e,n]=D.bounds;return x>=w&&x<e&&y>=s&&y<n;}
 function mapStats(p,u,set,observed){const visible=Array.from(p).filter(([c])=>within(c)).reduce((s,[,v])=>s+v,0),outside=p.get(-2)||0,offmap=Math.max(0,sum(p)-visible-outside);return `${observed?'Observed':'Forecast'} mass: visible ${percent(visible)} · off-map cells ${percent(offmap)} · OUTSIDE ${percent(outside)}${observed?'':` · unresolved ${percent(u)} · 90% set ${set.available?`${set.cells.size} categories / ${percent(set.mass)} mass`:'unavailable'}`}`;}
 function drawMap(kind,p,set,max,other){const svg=d3.select(root.querySelector(`[data-map="${kind}"]`)),width=svg.node().parentElement.clientWidth,height=Math.max(240,width*.72),m={left:42,right:10,top:8,bottom:35};svg.attr('viewBox',`0 0 ${width} ${height}`);svg.selectAll('*').remove();svg.append('title').text(kind==='forecast'?'Forecast probability':'Observed held-out endpoint frequency');svg.append('desc').text(`One-degree endpoint cells, same ${state.horizon}-day horizon, origin ${state.origin} and outer fold ${state.fold}. Shared scale from zero to ${percent(max)}. No interpolation.`);
  const [west,south,east,north]=D.bounds,projection=d3.geoMercator().fitExtent([[m.left,m.top],[width-m.right,height-m.bottom]],{type:'MultiPoint',coordinates:[[west,south],[east,north]]}),path=d3.geoPath(projection),[x0,y0]=projection([west,north]),[x1,y1]=projection([east,south]);
  const clip=`blend-clip-${kind}`;svg.append('defs').append('clipPath').attr('id',clip).append('rect').attr('x',x0).attr('y',y0).attr('width',x1-x0).attr('height',y1-y0);const frame=svg.append('g').attr('clip-path',`url(#${clip})`);frame.append('rect').attr('x',x0).attr('y',y0).attr('width',x1-x0).attr('height',y1-y0).attr('fill','var(--background)');frame.append('path').datum(D.land).attr('d',path).attr('fill','var(--muted)').attr('stroke','var(--border)').attr('stroke-width',.7);
  const xt=d3.ticks(west,east,width<380?3:5),yt=d3.ticks(south,north,4);xt.forEach(x=>{const a=projection([x,north]),b=projection([x,south]);frame.append('line').attr('x1',a[0]).attr('x2',b[0]).attr('y1',a[1]).attr('y2',b[1]).attr('stroke','var(--border)').attr('stroke-width',.5);svg.append('text').attr('x',b[0]).attr('y',y1+18).attr('text-anchor','middle').text(`${Math.abs(x)}°W`);});yt.forEach(y=>{const a=projection([west,y]),b=projection([east,y]);frame.append('line').attr('x1',a[0]).attr('x2',b[0]).attr('y1',a[1]).attr('y2',b[1]).attr('stroke','var(--border)').attr('stroke-width',.5);svg.append('text').attr('x',x0-5).attr('y',a[1]+4).attr('text-anchor','end').text(`${y}°N`);});
  frame.selectAll('rect.blend-cell').data(Array.from(p).filter(([c,v])=>within(c)&&v>0)).join('rect').attr('class','blend-cell').attr('x',([c])=>projection(coords(c))[0]).attr('y',([c])=>{const [x,y]=coords(c);return projection([x,y+1])[1];}).attr('width',([c])=>{const [x,y]=coords(c);return projection([x+1,y])[0]-projection([x,y])[0]+.05;}).attr('height',([c])=>{const [x,y]=coords(c);return projection([x,y])[1]-projection([x,y+1])[1]+.05;}).attr('fill','var(--viz-series-1)').attr('fill-opacity',([,v])=>Math.sqrt(v/max)*.9);
  frame.append('path').datum(D.region).attr('d',path).attr('fill','none').attr('stroke','var(--foreground)').attr('stroke-dasharray','4 3').attr('stroke-width',1.3);if(set.available)frame.append('path').attr('d',edgePath(set.cells,projection)).attr('fill','none').attr('stroke','var(--foreground)').attr('stroke-width',1.6);
  const [ox,oy]=coords(state.origin),o=projection([ox+.5,oy+.5]);frame.append('path').attr('d',`M${o[0]-5},${o[1]}h10M${o[0]},${o[1]-5}v10`).attr('stroke','var(--foreground)').attr('stroke-width',2).attr('fill','none');
  if(kind==='observed'&&p.size===0)svg.append('text').attr('x',(x0+x1)/2).attr('y',(y0+y1)/2).attr('text-anchor','middle').text('No eligible held-out endpoints');svg.append('rect').attr('x',x0).attr('y',y0).attr('width',x1-x0).attr('height',y1-y0).attr('fill','none').attr('stroke','var(--border)');svg.append('text').attr('x',(x0+x1)/2).attr('y',height-2).attr('text-anchor','middle').attr('class','axis-title').attr('data-axis','x').text('Longitude');
  const overlay=svg.append('rect').attr('x',x0).attr('y',y0).attr('width',x1-x0).attr('height',y1-y0).attr('fill','transparent').attr('class','cursor-interaction').attr('data-chart-hit','');
  const detail=(event,pin)=>{const ll=projection.invert(d3.pointer(event,svg.node())),cell=Math.floor(ll[1]+90)*360+Math.floor(ll[0]+180);if(pin)selectedCell=cell;const a=p.get(cell)||0,b=other.get(cell)||0;root.querySelector('[data-detail="cell"]').textContent=`Cell ${label(cell)} · ${kind==='forecast'?'forecast':'observed'} ${percent(a)} · ${kind==='forecast'?'observed':'forecast'} ${percent(b)}${set.available?` · ${set.cells.has(cell)?'in':'outside'} forecast 90% set`:''}`;};overlay.on('pointermove',event=>detail(event,false)).on('click',event=>detail(event,true));
 }
 function renderTable(){const rows=D.summary.filter(r=>r.horizon_days===state.horizon).sort((a,b)=>D.models.indexOf(a.model)-D.models.indexOf(b.model)),tbody=root.querySelector('[data-table="summary"]');tbody.replaceChildren(...rows.map(r=>{const tr=document.createElement('tr');[r.model,String(r.eligible_pairs),String(r.independent_ids),percent(r.forecast_coverage),number(r.brier_failure_penalized),r.log_loss===null?(r.zero_probability_pairs>0&&r.forecast_coverage===1?'infinity':'unavailable'):number(r.log_loss),r.region90_hit_pct===null?'unavailable':`${r.region90_hit_pct.toFixed(2)}%`,r.region90_available_pct===null?'unavailable':`${r.region90_available_pct.toFixed(2)}%`,number(r.mean_region90_cells),String(r.zero_probability_pairs)].forEach(value=>{const td=document.createElement('td');td.textContent=value;tr.append(td);});return tr;}));const r=D.foldSummary.find(r=>r.outer_fold===state.fold&&r.horizon_days===state.horizon&&r.model===state.model);root.querySelector('[data-detail="fold-score"]').textContent=r?`Selected fold ${state.fold}, ${state.model}: ${r.eligible_pairs.toLocaleString()} held-out pairs · ${r.independent_ids} IDs · complete coverage ${percent(r.forecast_coverage)} · penalized Brier ${number(r.brier_failure_penalized)}`:'Selected fold summary unavailable.';}
 function curve(){const svg=d3.select(root.querySelector('.blend-curve')),width=svg.node().parentElement.clientWidth,height=240,m={left:78,right:24,top:16,bottom:52},rows=D.grid.filter(r=>r.outer_fold===state.fold&&r.horizon_days===state.horizon).sort((a,b)=>a.lambda_value-b.lambda_value),chosen=D.selection.filter(r=>r.outer_fold===state.fold&&r.horizon_days===state.horizon),all=[...rows.map(r=>r.selection_brier),...chosen.map(r=>r.inner_brier)],extent=d3.extent(all),pad=Math.max((extent[1]-extent[0])*.12,1e-6),x=d3.scaleLinear().domain(d3.extent(rows,r=>r.lambda_value)).range([m.left+5,width-m.right-5]),y=d3.scaleLinear().domain([extent[0]-pad,extent[1]+pad]).range([height-m.bottom-5,m.top+5]);svg.attr('viewBox',`0 0 ${width} ${height}`);svg.selectAll('*').remove();svg.append('title').text('Inner out-of-fold selection loss');svg.append('desc').text(`Outer training fold ${state.fold}, ${state.horizon} days. Candidate grid and continuous analytic optimum on the same tuning cases.`);svg.append('rect').attr('data-chart-frame','').attr('x',m.left).attr('y',m.top).attr('width',width-m.left-m.right).attr('height',height-m.top-m.bottom).attr('fill','none').attr('stroke','var(--border)');svg.append('g').attr('transform',`translate(0,${height-m.bottom})`).call(d3.axisBottom(x).ticks(width<400?4:6));svg.append('g').attr('transform',`translate(${m.left},0)`).call(d3.axisLeft(y).ticks(4).tickFormat(d3.format('.5f')));svg.append('text').attr('class','axis-title').attr('data-axis','x').attr('x',(m.left+width-m.right)/2).attr('y',height-8).attr('text-anchor','middle').text('Lambda · B1 mixing weight');svg.append('text').attr('class','axis-title').attr('data-axis','y').attr('transform','rotate(-90)').attr('x',-(m.top+height-m.bottom)/2).attr('y',15).attr('text-anchor','middle').text('Inner selection Brier');svg.append('path').datum(rows).attr('d',d3.line().x(r=>x(r.lambda_value)).y(r=>y(r.selection_brier))).attr('fill','none').attr('stroke','var(--viz-series-1)').attr('stroke-width',2);svg.selectAll('circle.grid').data(rows).join('circle').attr('cx',r=>x(r.lambda_value)).attr('cy',r=>y(r.selection_brier)).attr('r',3).attr('fill','var(--viz-series-1)');chosen.forEach(r=>svg.append('path').attr('d',d3.symbol().type(r.method==='Analytic'?d3.symbolDiamond:d3.symbolSquare).size(65)()).attr('transform',`translate(${x(r.lambda_value)},${y(r.inner_brier)})`).attr('fill',r.method==='Analytic'?'var(--viz-series-3)':'var(--viz-series-2)'));
  const guide=svg.append('line').attr('y1',m.top).attr('y2',height-m.bottom).attr('stroke','var(--border)').attr('visibility','hidden'),marker=svg.append('circle').attr('r',4).attr('fill','var(--viz-series-1)').attr('visibility','hidden'),tip=root.querySelector('.blend-tooltip');
  const hover=event=>{const px=Math.max(x.range()[0],Math.min(x.range()[1],d3.pointer(event,svg.node())[0])),lambda=x.invert(px),right=d3.bisector(r=>r.lambda_value).right(rows,lambda),a=rows[Math.max(0,right-1)],b=rows[Math.min(rows.length-1,right)],ratio=b.lambda_value===a.lambda_value?0:(lambda-a.lambda_value)/(b.lambda_value-a.lambda_value),value=a.selection_brier+(b.selection_brier-a.selection_brier)*ratio;guide.attr('x1',px).attr('x2',px).attr('visibility','visible');marker.attr('cx',px).attr('cy',y(value)).attr('visibility','visible');root.querySelector('[data-detail="lambda"]').textContent=`Inner curve at lambda ${lambda.toFixed(3)}: interpolated grid Brier ${number(value)} · ${chosen.map(r=>`${r.method}: lambda ${r.lambda_value.toFixed(6)}, Brier ${number(r.inner_brier)}`).join(' · ')}`;};svg.append('rect').attr('x',m.left).attr('y',m.top).attr('width',width-m.left-m.right).attr('height',height-m.top-m.bottom).attr('fill','transparent').attr('data-chart-hit','').attr('data-chart-hover-overlay','cross-series').on('pointermove',hover).on('click',hover).on('pointerleave',()=>{guide.attr('visibility','hidden');marker.attr('visibility','hidden');});guide.attr('data-chart-hover-guide','');marker.attr('data-chart-hover-marker','');root.querySelector('[data-detail="lambda"]').textContent=chosen.map(r=>`${r.method}: lambda ${r.lambda_value.toFixed(6)}, inner Brier ${number(r.inner_brier)}`).join(' · ');
 }
 function render(){sync();const F=forecast(),obs=D.observed[`${state.fold}:${state.horizon}:${state.origin}`]||{n:0,ids:0,counts:[]},O=new Map(obs.counts.map(([c,n])=>[c,n/obs.n])),set=region(F.p),max=Math.max(...F.p.values(),...O.values(),.0001),support=D.support.find(r=>r.outer_fold===state.fold&&r.horizon_days===state.horizon&&r.origin_cell_1===state.origin);root.querySelector('[data-detail="support"]').textContent=`${state.horizon} days · outer fold ${state.fold} · training support ${support?support.pair_count.toLocaleString():0} pairs / ${support?support.independent_ids:0} IDs · matched held-out observations ${obs.n.toLocaleString()} pairs / ${obs.ids} IDs${F.lambda===null?'':` · lambda ${F.lambda.toFixed(6)}`}`;root.querySelector('[data-heading="forecast"]').textContent=`${state.model} forecast probability`;drawMap('forecast',F.p,set,max,O);drawMap('observed',O,set,max,F.p);root.querySelector('[data-detail="forecast"]').textContent=mapStats(F.p,F.u,set,false);root.querySelector('[data-detail="observed"]').textContent=obs.n?mapStats(O,0,set,true):'No eligible held-out endpoints for this fold, horizon and origin.';const legend=root.querySelector('[data-legend="scale"]');legend.replaceChildren(...[0,.04,.16,.36,.64,1].map(r=>{const span=document.createElement('span'),swatch=document.createElement('i');swatch.style.background='var(--viz-series-1)';swatch.style.opacity=String(Math.sqrt(r)*.9);span.append(swatch,document.createTextNode(percent(max*r)));return span;}));if(selectedCell===null)root.querySelector('[data-detail="cell"]').textContent='Select a map cell to compare its forecast probability and held-out frequency.';renderTable();curve();initial=false;}
 Object.entries(controls).forEach(([key,control])=>control.addEventListener('change',()=>{state[key]=key==='model'?control.value:Number(control.value);if(key==='fold')state.origin=D.defaults[String(state.fold)];selectedCell=null;render();save();}));window.addEventListener('openai:set_globals',event=>{if(event.detail?.globals?.widgetState){applySaved(event.detail.globals.widgetState);render();}});new ResizeObserver(()=>render()).observe(root);sync();render();
})();
</script>
</div>
'''


def _standalone(fragment: str) -> str:
    # These fallbacks belong only to the standalone document. The inline body
    # consumes the conversation's own theme tokens and utility classes.
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Developmental nested-CV endpoint comparison</title>
<style>
:root { color-scheme:light dark; --background:light-dark(#fff,#151719); --foreground:light-dark(#202428,#e6e8ea); --muted:light-dark(#e7e9eb,#33383d); --border:light-dark(#ced3d7,#515960); --popover:var(--background); --popover-foreground:var(--foreground); --viz-series-1:light-dark(#236fab,#69b5ef); --viz-series-2:light-dark(#9a5e0d,#e5ae5b); --viz-series-3:light-dark(#267647,#71c38e); }
body { margin:0 auto; padding:1.4rem; max-width:1160px; font-family:system-ui,sans-serif; font-size:14px; line-height:1.5; background:var(--background); color:var(--foreground); }
h2,h3 { font-weight:500; } h2 { font-size:1.3rem; } h3 { font-size:1rem; }
.viz-controls { display:flex; flex-wrap:wrap; gap:.8rem 1.2rem; margin:1rem 0; }
.form-label { display:grid; gap:.3rem; } .form-select { font:inherit; padding:.4rem .6rem; max-width:100%; color:var(--foreground); background:var(--background); border:1px solid var(--border); border-radius:4px; }
.table-responsive { overflow-x:auto; } .text-small { font-size:12px; } .tabular-nums { font-variant-numeric:tabular-nums; }
.sr-only { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; }
@media(pointer:coarse) { .form-select { min-height:44px; font-size:16px; } }
</style></head><body>
''' + fragment + "\n</body></html>\n"


def build_report(run_dir: Path, provenance_dir: Path) -> dict[str, Path]:
    """Build new human, interactive and static reports from one saved run.

    Return keys are ``report``, ``comparison``, ``inline``, ``sources``, and,
    when matplotlib is installed, ``outer_plot`` and ``lambda_plot``. Existing
    artifacts are never overwritten, and both supplied directories must be the
    matching results/provenance namespaces of the configured project.
    """
    paths = project_paths()
    run_dir, provenance_dir = Path(run_dir).resolve(), Path(provenance_dir).resolve()
    if (run_dir.parent != paths.root / "results/runs" or
            provenance_dir != paths.root / "provenance/runs" / run_dir.name):
        raise PermissionError("Reports must use matching fresh result/provenance run directories.")
    if not run_dir.is_dir() or not provenance_dir.is_dir():
        raise FileNotFoundError("Both saved run directories must already exist.")

    source_paths = {
        name: run_dir / name for name in (
            "development_counts.parquet", "outer_scores.csv", "outer_summary.csv",
            "outer_fold_summary.csv", "lambda_selection.csv", "lambda_grid_scores.csv",
            "final_lambda_selection.csv", "final_lambda_grid_scores.csv",
            "outer_models.json", "final_models.json", "training_support.csv",
            "bootstrap_differences.csv",
        )
    }
    source_paths.update({"outer_folds.csv": provenance_dir / "outer_folds.csv",
                         "run.json": provenance_dir / "run.json",
                         "land_mask_intermediate": paths.asset("land_mask_intermediate", verify=True),
                         "release_R": paths.asset("release_R", verify=True)})
    for source in source_paths.values():
        if not source.is_file():
            raise FileNotFoundError(source)
    counts = pd.read_parquet(source_paths["development_counts.parquet"])
    folds = pd.read_csv(source_paths["outer_folds.csv"])
    support = pd.read_csv(source_paths["training_support.csv"])
    summary = pd.read_csv(source_paths["outer_summary.csv"])
    fold_summary = pd.read_csv(source_paths["outer_fold_summary.csv"])
    selection = pd.read_csv(source_paths["lambda_selection.csv"])
    grid = pd.read_csv(source_paths["lambda_grid_scores.csv"])
    final_selection = pd.read_csv(source_paths["final_lambda_selection.csv"])
    bootstrap = pd.read_csv(source_paths["bootstrap_differences.csv"])
    models = json.loads(source_paths["outer_models.json"].read_text())
    receipt = json.loads(source_paths["run.json"].read_text())
    _required(counts, ["id", "horizon_days", "origin_cell_1", "destination_cell_1", "pair_count"], "development_counts")
    _required(folds, ["id", "outer_fold"], "outer_folds")
    _required(support, ["outer_fold", "horizon_days", "origin_cell_1", "pair_count", "independent_ids"], "training_support")
    _required(summary, ["horizon_days", "model", "eligible_pairs", "independent_ids", "forecast_coverage", "brier_failure_penalized", "brier", "log_loss", "region90_hit_pct", "region90_available_pct", "top_cell_hit_pct"], "outer_summary")
    _required(fold_summary, ["outer_fold", "horizon_days", "model", "eligible_pairs", "independent_ids", "forecast_coverage", "brier_failure_penalized"], "outer_fold_summary")
    _required(selection, ["outer_fold", "horizon_days", "method", "lambda_value", "inner_brier"], "lambda_selection")
    _required(grid, ["outer_fold", "horizon_days", "lambda_value", "selection_brier"], "lambda_grid_scores")
    if folds["id"].duplicated().any() or support.duplicated(["outer_fold", "horizon_days", "origin_cell_1"]).any():
        raise ValueError("Duplicated fold IDs or training-support keys.")
    if not counts["pair_count"].gt(0).all() or not counts["horizon_days"].isin(HORIZONS).all():
        raise ValueError("Invalid endpoint multiplicity or unsupported display horizon.")
    if receipt.get("config", {}).get("final_test_access") is not False:
        raise ValueError("The saved run does not explicitly disable final-test access.")
    fold_values = sorted(int(value) for value in folds["outer_fold"].unique())
    defaults = _default_origins(support, fold_values)
    observed = _observed(counts, folds[["id", "outer_fold"]])
    payload = {
        **_geometry(source_paths["land_mask_intermediate"], source_paths["release_R"]),
        "models": list(MODELS), "horizons": list(HORIZONS),
        "folds": fold_values, "origins": sorted(int(value) for value in counts["origin_cell_1"].unique()),
        "defaults": defaults, "observed": observed,
        "outerModels": _compact_models(models, fold_values, support), "support": _records(support),
        "summary": _records(summary), "foldSummary": _records(fold_summary),
        "selection": _records(selection), "grid": _records(grid),
    }
    encoded = json.dumps(_json_safe(payload), separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    fragment = _FRAGMENT.replace("__PAYLOAD__", encoded)
    if len(fragment.encode("utf-8")) >= 1_000_000:
        raise ValueError("The inline report exceeds 1 MB; review display aggregation before publication.")
    plots = _plot_bytes(summary, grid, selection)
    outputs = {"report": run_dir / "REPORT.md", "comparison": run_dir / "comparison.html",
               "inline": run_dir / "comparison-inline.html", "sources": run_dir / "report_sources.json"}
    if plots:
        outputs.update(outer_plot=run_dir / "outer-brier-comparison.png",
                       lambda_plot=run_dir / "lambda-selection-curves.png")
    for output in outputs.values():
        paths.output(output)
    sources = {name: {"path": str(path.relative_to(paths.root)), "sha256": file_sha256(path)}
               for name, path in source_paths.items()}
    report = _report_text(run_dir, receipt, summary, selection, final_selection,
                          bootstrap, sources, bool(plots), defaults)
    artifacts = {
        outputs["report"]: report.encode(), outputs["comparison"]: _standalone(fragment).encode(),
        outputs["inline"]: fragment.encode(),
        outputs["sources"]: (json.dumps({"sources": sources, "display_default_origins": defaults,
                                         "inline_bytes": len(fragment.encode()),
                                         "geometry_display": payload["geometry_display"],
                                         "scope": "developmental nested CV; no final-test evaluation"},
                                        indent=2) + "\n").encode(),
        **{run_dir / name: data for name, data in plots.items()},
    }
    for destination, content in artifacts.items():
        paths.publish(destination, lambda stream, data=content: stream.write(data))
    return outputs
