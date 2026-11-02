"""E4 English scientific report and complete-distribution figures."""
from html import escape
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle, Polygon
from matplotlib.colors import Normalize
import shapely
from shapely.geometry import shape, box

from data3001.modelling.baselines.adaptive_b2_b1_report import save_plot
from data3001.modelling.common.plotting import _rings, markdown_table
from data3001.modelling.common.prediction_regions import probability_region
from data3001.modelling.common.qualified_count_inputs import read_frame

COLORS = {"B2": "#657c89", "PartialID": "#7658b2", "EqualID": "#138979", "Fixed": "#bf742d"}


def make_maps(paths, run, base, vectors):
    support = base.b2.support.pivot(index="origin_cell_1", columns="horizon_days", values="training_id_count")
    ranks = support.min(axis=1).sort_index().sort_values(ascending=False, kind="stable")
    origin = int(ranks.index[0])
    release = shape(json.loads(paths.asset("release_R").read_text())["features"][0]["geometry"])
    domain = shape(json.loads(paths.asset("transport_D").read_text())["features"][0]["geometry"])
    land = shapely.from_wkb(paths.asset("land_mask_intermediate").read_bytes()).intersection(box(-83, 19, -6, 56)).simplify(.025)
    polygons = [g for g in getattr(land, "geoms", [land]) if g.geom_type == "Polygon"]
    names = []
    for h in (7, 30):
        norm = Normalize(0, max(vectors[m][(h, origin)].max() for m in COLORS))
        fig, axes = plt.subplots(4, 1, figsize=(13, 15), layout="constrained")
        for ax, model in zip(axes, COLORS):
            p = vectors[model][(h, origin)]
            region, meta = probability_region(p, base.states)
            rectangles, values, outlines = [], [], []
            for j, cell in enumerate(base.states):
                if cell < 0:
                    continue
                x, y = cell % 360-180, cell//360-90
                if p[j] > 0:
                    rectangles.append(Rectangle((x, y), 1, 1)); values.append(p[j])
                if region[j]:
                    outlines.append(Rectangle((x, y), 1, 1))
            pc = PatchCollection(rectangles, cmap="Blues", norm=norm, edgecolor="none")
            pc.set_array(np.asarray(values)); ax.add_collection(pc)
            ax.add_collection(PatchCollection([Polygon(np.asarray(g.exterior.coords)) for g in polygons],
                                             facecolor="#e0e4e5", edgecolor="#9da7aa", linewidth=.3))
            ax.add_collection(PatchCollection(outlines, facecolor="none", edgecolor="#963a88", linewidth=.5))
            for geom, color, style in [(release, "#278457", "-"), (domain, "#657787", "--")]:
                for ring in _rings(geom):
                    a = np.asarray(ring); ax.plot(a[:, 0], a[:, 1], color=color, ls=style, lw=.7)
            ax.add_patch(Rectangle((origin % 360-180, origin//360-90), 1, 1, fill=False, edgecolor="#e45e29", lw=1.5))
            ax.set(xlim=(-83, -6), ylim=(19, 56), xlabel="Longitude", ylabel="Latitude")
            ax.set_title(f"{model} | 90% region: {meta['region90_cells']} cells | issued mass {meta['region90_mass']:.2%} | E {p[base.index[-2]]:.2%}, U 0%", loc="left", fontsize=10)
            ax.set_facecolor("#f6f9fb"); ax.grid(alpha=.12)
        counts = base.b2.support[(base.b2.support.horizon_days == h) & (base.b2.support.origin_cell_1 == origin)].iloc[0]
        fig.colorbar(pc, ax=axes, label="Probability per cell; shared scale across models", shrink=.65)
        fig.suptitle(f"E4 {h}-day fitted candidates | origin {origin} | {int(counts.training_id_count)} IDs, {int(counts.training_pair_count):,} pairs\n"
                     "Purple: 90% region. Orange: origin. All positive probabilities retained; maps are not held-out skill.", fontsize=12)
        name = f"candidate_comparison_{h}d.png"
        save_plot(paths, run, name, fig); names.append(name)
    return origin, names


def diagnostic_plots(paths, run, summary, differences, base):
    names = []
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), layout="constrained")
    labels = {"brier": "Brier difference", "region90_cells": "90% cell-count difference", "region90_hit": "Actual-hit difference (pp)"}
    for row, h in enumerate((7, 30)):
        for col, metric in enumerate(labels):
            ax = axes[row, col]
            for j, reference in enumerate(("B2", "EqualID", "Fixed")):
                r = differences[(differences.horizon_days == h) & (differences.model == "PartialID") &
                                (differences.reference == reference) & (differences.metric == metric)].iloc[0]
                scale = 100 if metric == "region90_hit" else 1
                ax.plot([j, j], scale*np.array([r.lower_95, r.upper_95]), color=COLORS[reference], lw=4)
                ax.scatter(j, scale*r.difference, color=COLORS["PartialID"], s=42, zorder=3)
                if metric == "brier":
                    ax.scatter(j, r.adjusted_upper, marker="_", color="#a33d4a", s=100, zorder=3)
            ax.axhline(0, color="#607780", lw=.8)
            ax.set_xticks([0, 1, 2], ["vs B2", "vs EqualID", "vs Fixed"])
            ax.set_title(f"{h} days: {labels[metric]}", fontsize=10)
            ax.grid(axis="y", alpha=.2)
    fig.suptitle("PartialID (beta = 0.5) differences | equal cells, equal IDs within cell\n95% fixed-fit ID intervals; red marks: adjusted Brier upper bounds", fontsize=12)
    name = "quality_and_region_differences.png"; save_plot(paths, run, name, fig); names.append(name)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
    for ax, h in zip(axes, (7, 30)):
        data = base.contributions[base.contributions.horizon_days == h]
        ax.scatter(data.raw_share, data.equal_share, s=12, alpha=.4, color=COLORS["EqualID"], label="EqualID: beta 1")
        ax.scatter(data.raw_share, data.partial_share, s=12, alpha=.5, color=COLORS["PartialID"], label="PartialID: beta 0.5")
        ax.legend()
        maximum = max(data.raw_share.max(), data.equal_share.max())*1.05
        ax.plot([0, maximum], [0, maximum], "--", color="#87949c", lw=1)
        ax.set(xlabel="Original within-cell ID contribution", ylabel="Adjusted within-cell ID contribution",
               title=f"{h} days", xlim=(0, maximum), ylim=(0, maximum))
        ax.grid(alpha=.15)
    fig.suptitle("Power weighting moderates local record influence | all-development fit")
    name = "drifter_contributions.png"; save_plot(paths, run, name, fig); names.append(name)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
    fields = sorted([c for c in summary if c.startswith("hit_k_") and "__" not in c], key=lambda x: int(x[6:]))
    ks = [int(c[6:]) for c in fields]
    for ax, h in zip(axes, (7, 30)):
        for model, color in COLORS.items():
            r = summary[(summary.horizon_days == h) & (summary.model == model)].iloc[0]
            ax.plot(ks, 100*r[fields].to_numpy(float), ".-", label=model, color=color)
        ax.set(xscale="log", ylim=(0, 101), xlabel="D-cell budget K", ylabel="Weighted actual hits (%)", title=f"{h} days")
        ax.legend(); ax.grid(alpha=.15)
    fig.suptitle("Matched-budget diagnostic | same evaluation weights; expected boundary ties")
    name = "budget_hit_curves.png"; save_plot(paths, run, name, fig); names.append(name)
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5), layout="constrained")
    for row, h in enumerate((7,30)):
        table = summary[summary.horizon_days.eq(h)].set_index("model").loc[list(COLORS)]
        for col, (field, label) in enumerate([( "brier", "Brier (lower is better)"),
                                             ("region90_cells", "Mean 90% region cells"),
                                             ("region90_hit", "Actual hits (%)")]):
            ax = axes[row,col]
            values = table[field].to_numpy(float)*(100 if field == "region90_hit" else 1)
            if field == "brier":
                ax.scatter(range(4),values,c=list(COLORS.values()),s=70,zorder=3)
                ax.set_ylim(values.min()-.008,values.max()+.012)
            else:
                ax.bar(range(4),values,color=list(COLORS.values()),width=.6)
                ax.set_ylim(0,105 if field == "region90_hit" else values.max()*1.18)
            for x,v in enumerate(values):
                ax.annotate(f"{v:.6f}" if field == "brier" else f"{v:.2f}",(x,v),
                            xytext=(0,7),textcoords="offset points",ha="center",fontsize=8)
            ax.set_xticks(range(4),list(COLORS),rotation=20)
            ax.set_title(f"{h} days: {label}",fontsize=10)
            ax.grid(axis="y",alpha=.15)
    fig.suptitle("E4 held-out comparison | fixed E3 evaluation target\nB2: beta 0; PartialID: beta 0.5; EqualID: beta 1; Fixed: raw B2/B1",fontsize=12)
    name="model_comparison.png"; save_plot(paths,run,name,fig); names.append(name)
    cells = read_frame(run["results"]/"cell_summary.csv")
    fig, axes = plt.subplots(1,2,figsize=(13,11),layout="constrained")
    for ax,h in zip(axes,(7,30)):
        wide=cells[cells.horizon_days.eq(h)].pivot(index="origin_cell_1",columns="model",values="brier").sort_index()
        for offset,reference in zip((-.18,0,.18),("B2","EqualID","Fixed")):
            ax.scatter(wide.PartialID-wide[reference],np.arange(len(wide))+offset,
                       color=COLORS[reference],label="vs "+reference,s=18)
        ax.axvline(0,color="#83939c",lw=.8)
        ax.set_yticks(np.arange(len(wide)),wide.index.astype(str),fontsize=7)
        ax.set(xlabel="PartialID minus reference: Brier",ylabel="Origin cell",title=f"{h} days; all evaluable origins")
        ax.grid(axis="x",alpha=.15); ax.legend(fontsize=9)
    fig.suptitle("Per-origin diagnostic | negative values favour PartialID; no cell selection")
    name="per_cell_brier_differences.png"; save_plot(paths,run,name,fig); names.append(name)
    return names


def write_report(paths, run, summary, secondary, differences, decisions, selected, base, vectors, support, verification):
    origin, maps = make_maps(paths, run, base, vectors)
    figures = diagnostic_plots(paths, run, summary, differences, base)+maps
    fields = ["horizon_days", "model", "evaluable_cells", "evaluable_ids", "evaluable_id_cells",
              "evaluable_pairs", "brier", "region90_cells", "region90_hit", "target_availability", "zero_true_probability"]
    view, old = summary[fields].copy(), secondary[fields].copy()
    for table in (view, old):
        table["actual_hits_percent"] = 100*table.pop("region90_hit")
    parameter_view = selected[["role", "horizon_days", "parameter_a", "brier", "selection_status"]]
    narrative = [f"{r.horizon_days} days, PartialID versus {r.reference}: {r.outcome}. "
                 f"Brier change {r.delta_brier:+.8f}; 90% cells {r.delta_region90_cells:+.3f}; "
                 f"actual hits {100*r.delta_region90_hit:+.3f} percentage points. "
                 f"Region/hit trade-off: {bool(r.application_tradeoff)}."
                 for r in decisions.itertuples(index=False)]
    limits = [
        "Where Things End Up: predict the destination distribution from a given current origin cell at 7 or 30 days. The start is not first entry. Exact positions map to 1-degree cells; other elapsed days are not validated here.",
        "PartialID uses per-pair weight n_id^(-0.5), locally within fitting ID/origin/horizon. Beta 0 is raw B2; beta 1 is EqualID. All hourly pairs and internal endpoint proportions remain. Fixed retains raw B2/B1 and selects a by the unchanged E3 score. No beta is selected.",
        "Primary evaluation averages eligible times within ID/cell, then IDs within cell, then cells equally. It conditions on common available support. Secondary original-pair metrics describe a different population and cannot select the model.",
        "These are nested whole-ID development results on previously examined data. Final-test trajectories remain locked. All-development fitted maps are illustrative and cannot establish held-out performance.",
        "The complete probability distribution is retained. Nominal 90% mass need not achieve 90% observed hits; cutoff ties may issue more mass. Cell counts are not physical area.",
        "PartialID and EqualID have exactly B2's positive support. It cannot repair unseen-destination zeros or unsupported origin rows. E means first observed exit; U is unavailable support, not beaching.",
        "5,000 paired Exp(1) whole-ID multiplier resamples keep cells and fits fixed. Intervals omit refitting, shared training and research-adaptation uncertainty. Six-contrast adjusted Brier bounds are conditional evidence, not a guarantee.",
        "Partial weighting is a fitting-population sensitivity experiment under one fixed evaluation target. It is not Bayesian inference or proof that record length measures independent information.",
        "One observed ID in a cell is not sufficient to validate its uncertainty. Cross-ID shared ocean conditions are not captured by ID-level resampling.",
        "No observed exits would leave exit calibration unvalidated. Drifter transport is a proxy for spills/objects; windage, spreading, oil weathering and object-type transfer are outside this experiment.",
        "A Brier gain with lower hits or a larger region is a disclosed application trade-off. A gain against B2 alone does not establish a gain against Fixed. Retention and Step 2 closure await user review.",
    ]
    md = ["# Step 2 — E4 Partial Drifter Contribution Weighting", "",
          f"Run: {run['results'].name}. Executed and independently audited; scientific review pending.", "",
          "## Findings", "", *narrative, "", "## Primary held-out results", "",
          markdown_table(view, list(view.columns)), "",
          "The horizons have distinct eligible populations. Evaluation is equal-cell, equal-ID within each cell.",
          "", "## Paired differences and conditional uncertainty", "",
          markdown_table(differences, list(differences.columns)), "",
          "Hit differences above are fractions; multiply by 100 for percentage points. Brier adjusted_upper is the 99.1667th percentile for the six prespecified PartialID contrasts.",
          "", "## Secondary original-pair sensitivity", "", markdown_table(old, list(old.columns)), "",
          "These scores use the same newly selected predictions; they did not select Fixed's parameter.",
          "", "## Fixed parameter selection", "", markdown_table(parameter_view, list(parameter_view.columns)), "",
          "## Assumptions and interpretation", "", *["- "+s for s in limits], "",
          "## Engineering verification", "", "All 26 fitting roles and 1,200 candidate identities are independently reconstructed; every numerical table is compared in the separate replay.",
          "The current run's verification receipt identifies whether it is the primary run or replay. Source, input and outer-freeze hashes are checked before sealing.",
          "", "## Figures", "", f"Support-only illustration origin: {origin}.", ""]
    for name in figures:
        md.extend([f"![{name}]({name})", ""])
    md.extend(["## Artifact guide", "",
               "summary.csv: primary target; pair_weighted_summary.csv: secondary target; paired_differences.csv: paired comparisons; "
               "heldout_id_cells.parquet: numerator/mass sufficient scores; heldout_scores.parquet: explicit case weights; "
               "candidate_id_cells.parquet: all selection cases; fit_roles.json: whole-ID isolation; "
               "multiplier_identity.json: reproducible resampling; weighting_definitions.json: denominator semantics.", ""])
    paths.publish(run["results"]/"REPORT.md", lambda out: out.write("\n".join(md).encode()))
    html = ["<!doctype html><html lang='en'><meta charset='utf-8'><title>E4 PartialID review</title>",
            "<style>body{font:16px system-ui;max-width:1150px;margin:40px auto;padding:0 20px;color:#243b46}h1,h2{color:#174f5d}table{border-collapse:collapse;font-size:13px}th,td{padding:8px;border-bottom:1px solid #d7e0e3;text-align:right}th{background:#edf5f6}.scroll{overflow:auto}img{width:100%;margin:20px 0}li{margin:9px 0}</style>",
            "<h1>Where Things End Up · E4 PartialID</h1>",
            f"<p>{escape(run['results'].name)} · Development evidence · Review pending</p>",
            *[f"<p>{escape(s)}</p>" for s in narrative],
            "<h2>Primary held-out results</h2><div class='scroll'>"+view.to_html(index=False, border=0, float_format=lambda x: f"{x:.6f}")+"</div>",
            "<h2>Paired differences</h2><div class='scroll'>"+differences.to_html(index=False, border=0, float_format=lambda x: f"{x:.6f}")+"</div>",
            "<p>Hit differences in this table are fractions, not percentage points.</p>",
            *[f"<img src='{name}' alt='{name}'>" for name in figures],
            "<h2>Assumptions and limits</h2><ul>"+"".join(f"<li>{escape(s)}</li>" for s in limits)+"</ul>",
            "<p><a href='REPORT.md'>Full report</a> · <a href='summary.csv'>Primary results</a> · <a href='paired_differences.csv'>Comparisons</a></p></html>"]
    paths.publish(run["results"]/"review.html", lambda out: out.write("".join(html).encode()))
