"""Audited, additive MDN delivery; report code never fits or selects a model.

Only ``build_report`` reads run results. Importing this module or testing its
pure helpers does not expose outcomes. The final audit and audited checksums
are verified before any result values or validation endpoints are opened.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd

from data3001.paths import file_sha256
from . import conditional_mdn_s5_e3_inputs as inp
from .conditional_mdn_s5_e3_runtime import ROOT, atomic_json

KS = (1, 2, 4, 8, 16, 32)
MODELS = ["ExactPoint", "EndpointCI", "LocalGaussian"] + [f"MDN{k}" for k in KS]
METRICS = ["energy_km", "h90", "area90_km2", "land_mass", "outside_D_mass"]
DISPLAY_COUNT = 32768
DISPLAY_SEED = 20261126
BROLLY_URL = "https://arxiv.org/html/2303.11480v2"


def fixed_case_positions():
    """Twelve source-key-order positions, fixed before inspecting outcomes."""
    return np.floor(np.arange(12) * (33971 - 1) / 11).astype(int)


def require_completed_audit(run, root=ROOT):
    root = Path(root).resolve()
    folder = run["provenance"] / "formal_v1"
    path = folder / "final_audit.json"
    if not path.is_file():
        raise PermissionError("Final audit is required before reading report results")
    audit = json.loads(path.read_text())
    if (audit.get("status") != "complete" or audit.get("passed") is not True
            or audit.get("final_test_access") is not False):
        raise PermissionError("A complete passing final audit is required")
    calculation = json.loads((folder / "calculation_complete.json").read_text())
    if calculation.get("status") != "complete":
        raise PermissionError("Complete calculation receipt is required")
    evidence = audit.get("evidence_sha256")
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError("Audit has no frozen evidence checksums")
    for relative, digest in evidence.items():
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or file_sha256(source) != digest:
            raise ValueError("Audited report input changed: " + str(relative))
    return audit


def require_audited_file(path, audit, root=ROOT):
    """Require evidence coverage before opening a report source's contents."""
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Report input escapes the audited root")
    relative = path.relative_to(root).as_posix()
    digest = audit.get("evidence_sha256", {}).get(relative)
    if digest is None:
        raise ValueError("Report input is not covered by final audit: " + relative)
    if file_sha256(path) != digest:
        raise ValueError("Audited report input changed: " + relative)
    return path


def validate_summary(summary, selected_k):
    if (summary.index.has_duplicates or set(summary.index) != set(MODELS)
            or selected_k not in KS):
        raise ValueError("Report requires exactly nine unique models and a registered K")
    if not set(METRICS) <= set(summary.columns):
        raise ValueError("Missing primary report metrics")
    if not np.isfinite(summary[METRICS].to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite report metrics")


def display_histograms(clouds, extent):
    x0, y0, x1, y1 = extent
    xb = np.arange(x0, x1 + .25, .5)
    yb = np.arange(y0, y1 + .25, .5)
    histograms = {}
    for name, (points, weights) in clouds.items():
        values = np.histogram2d(points[:, 0], points[:, 1], bins=(xb, yb), weights=weights)[0].T
        if not np.isclose(weights.sum(), 1., atol=1e-10, rtol=0):
            raise ValueError("Display distribution is not normalized")
        if not np.isclose(values.sum(), 1., atol=1e-10, rtol=0):
            raise ValueError("Display view dropped probability mass")
        histograms[name] = values
    return (xb, yb), histograms


def _display_seed(key, name):
    identity = f"mdn_s5_e3_display_only|{DISPLAY_SEED}|{name}|" + "|".join(map(str, key))
    return int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8], "little")


def _markdown(frame):
    """Dependency-free Markdown table with exact column names and six decimals."""
    frame = frame.reset_index() if frame.index.name or not isinstance(frame.index, pd.RangeIndex) else frame
    def cell(value):
        if isinstance(value, (float, np.floating)):
            return f"{value:,.6f}"
        return str(value).replace("|", "\\|").replace("\n", " ")
    rows = ["| " + " | ".join(map(str, frame.columns)) + " |",
            "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    rows += ["| " + " | ".join(cell(v) for v in row) + " |" for row in frame.itertuples(index=False, name=None)]
    return "\n".join(rows)


def _training_manifests(base):
    manifests, rows = {}, []
    for role in ("C_T0", "C_T1", "C_outer"):
        for k in KS:
            manifest = json.loads((base / role / f"K{k}" / "manifest.json").read_text())
            if (manifest.get("status") != "complete" or manifest.get("role") != role
                    or manifest.get("k") != k or manifest["full_refit"]["purpose"] != "full_refit"):
                raise ValueError("Incomplete saved full-refit manifest")
            manifests[role, k] = manifest
            diagnostic = manifest["diagnostics"]
            rows.append(dict(role=role, K=k, parameters=manifest["parameter_count"],
                             selected_seed=manifest["selected_seed"], selected_epoch=manifest["selected_epoch"],
                             seed_cap_count=sum(s["status"] == "epoch_cap_reached" for s in manifest["seeds"]),
                             mixture_entropy_mean_nats=diagnostic["mixture_entropy_mean_nats"],
                             mixture_entropy_min_nats=diagnostic["mixture_entropy_min_nats"],
                             mixture_entropy_max_nats=diagnostic["mixture_entropy_max_nats"],
                             effective_components_mean=diagnostic["effective_components_mean"],
                             near_floor_probability_mass=diagnostic["near_floor_probability_mass_query_mean"],
                             gradient_clip_rate=diagnostic["full_refit_gradient_clip_rate"],
                             fit_epoch_seconds=sum(r["seconds"] for fit in [*manifest["seeds"], manifest["full_refit"]]
                                                   for r in fit["history"])))
    return manifests, pd.DataFrame(rows)


def _plot_metrics(summary, comparisons, per_id, choice, manifests, figures):
    import matplotlib.pyplot as plt
    selected = f"MDN{choice['selected_k']}"
    colours = ["#758699", "#3b9b94", "#d98b37"] + ["#6038ad" if name == selected else "#b3a2d3" for name in MODELS[3:]]
    files = []
    def save(fig, filename):
        fig.savefig(figures / filename, dpi=160, bbox_inches="tight")
        plt.close(fig)
        files.append(filename)
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.4), layout="constrained")
    for ax, field, title in zip(axes, METRICS[:3], ["Energy Score (km); lower is better", "Observed hit rate of 90% ellipse", "Mean 90% ellipse area (km²)"]):
        ax.bar(MODELS, summary.loc[MODELS, field], color=colours)
        ax.set_title(title, fontsize=10)
        ax.tick_params(axis="x", rotation=55)
        ax.grid(axis="y", alpha=.2)
    axes[1].axhline(.9, color="#444", ls="--", lw=.8)
    save(fig, "outer_comparison.png")
    fig, axes = plt.subplots(1, 3, figsize=(15, 4), layout="constrained")
    for ax, field, lo, hi, reference, title in zip(axes, ["es_delta", "hit_delta", "area_ratio"],
            ["es_lower", "hit_lower", "area_lower"], ["es_upper", "hit_upper", "area_upper"],
            [0, 0, 1], [f"{selected} − control ES (km)", f"{selected} − control hit rate", f"{selected} / control area"]):
        ypos = np.arange(len(comparisons))
        ax.hlines(ypos, comparisons[lo], comparisons[hi], color="#6038ad", lw=2)
        ax.scatter(comparisons[field], ypos, color="#6038ad")
        ax.axvline(reference, color="#777", lw=.8)
        ax.set_yticks(ypos, comparisons.baseline)
        ax.set_title(title, fontsize=10)
    save(fig, "paired_effects.png")
    pivot = per_id.pivot(index="id", columns="model", values="energy_km").sort_index()
    fig, axes = plt.subplots(3, 1, figsize=(15, 9), sharex=True, layout="constrained")
    for ax, baseline in zip(axes, MODELS[:3]):
        difference = pivot[selected] - pivot[baseline]
        ax.bar(np.arange(len(difference)), difference, color=np.where(difference < 0, "#3b9b94", "#d98b37"))
        ax.axhline(0, color="#777", lw=.8)
        ax.set_ylabel(f"{selected} − {baseline}\nES (km)")
    axes[-1].set_xticks(np.arange(len(pivot)), [str(i) for i in pivot.index], rotation=90, fontsize=7)
    axes[-1].set_xlabel("All outer development drifter IDs; fixed numerical order")
    save(fig, "per_id_effects.png")
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), layout="constrained")
    for role in ("C_T0", "C_T1"):
        axes[0].plot(KS, [choice["role_scores"][f"{role}:{k}"] for k in KS], marker="o", label=role)
    pooled = [choice["pooled_scores"][str(k)] for k in KS]
    axes[0].plot(KS, pooled, "o-", color="#6038ad", lw=2, label="104-ID pooled")
    axes[0].axvline(choice["selected_k"], color="#777", ls="--", lw=.8)
    axes[0].set(xscale="log", xticks=KS, xticklabels=list(map(str, KS)), xlabel="Mixture components K", ylabel="Inner Energy Score (km)")
    axes[0].legend()
    axes[1].plot([4352 + 390*k for k in KS], pooled, "o-", color="#6038ad")
    for k, score in zip(KS, pooled):
        axes[1].annotate(f"K={k}", (4352+390*k, score), xytext=(4, 5), textcoords="offset points", fontsize=8)
    axes[1].set(xlabel="Trainable parameters", ylabel="104-ID pooled inner Energy Score (km)")
    save(fig, "inner_es_complexity.png")
    for role in ("C_T0", "C_T1", "C_outer"):
        fig, axes = plt.subplots(2, 3, figsize=(15, 8), layout="constrained")
        for ax, k in zip(axes.flat, KS):
            manifest = manifests[role, k]
            for seed, colour in zip(manifest["seeds"], ("#3b9b94", "#d98b37", "#6038ad")):
                curve = pd.DataFrame(seed["history"])
                ax.plot(curve.epoch, curve.stop_nll, color=colour, label=f"{seed['base_seed']} stop")
                ax.plot(curve.epoch, curve.training_nll, color=colour, ls=":", alpha=.6)
                ax.scatter([seed["best_epoch"]], [seed["best_nll"]], color=colour, s=18)
            ax.set_title(f"K={k}; chosen {manifest['selected_seed']} / epoch {manifest['selected_epoch']}", fontsize=9)
            ax.set(xlabel="Epoch", ylabel="Standardized-displacement NLL")
            ax.legend(fontsize=7)
        fig.suptitle(f"{role}: three seeds; solid=ID-equal stop NLL, dotted=pair-equal train NLL")
        save(fig, f"training_curves_{role}.png")
    return files


def _support_diagnostics(fit, query):
    """Complete source-only support; no neighbour cap, deletion, or fallback."""
    from scipy.spatial import Delaunay
    from data3001.modelling.baselines.exact_origin_s4_e7 import NeighbourIndex
    from .conditional_mdn_s5_e3_numerics import xyz
    index = NeighbourIndex(fit.lon.to_numpy(), fit.lat.to_numpy())
    positions = xyz(query[["lon", "lat"]].to_numpy()) * 1000
    _, nearest = index.tree.query(positions, k=1, workers=1)
    train_ids = fit.id.to_numpy()
    near_distances, local_ids = [], []
    for position, (lon, lat), candidate in zip(positions, query[["lon", "lat"]].to_numpy(), nearest):
        upper = index._distances(lon, lat, np.asarray([candidate]))[0]
        possible = np.asarray(index.tree.query_ball_point(position, upper + 1e-6), dtype=int)
        near_distances.append(float(index._distances(lon, lat, possible).min() / 1000))
        possible = np.asarray(index.tree.query_ball_point(position, 100000 + 1e-6), dtype=int)
        distances = index._distances(lon, lat, possible)
        local_ids.append(len(np.unique(train_ids[possible[distances <= 100000 + 1e-6]])))
    hull = Delaunay(np.unique(fit[["lon", "lat"]].to_numpy(), axis=0))
    outside = hull.find_simplex(query[["lon", "lat"]].to_numpy()) < 0
    table = query[inp.KEY].copy()
    table["nearest_training_start_km"] = near_distances
    table["distinct_training_ids_within_100km"] = local_ids
    table["outside_training_lonlat_convex_hull"] = outside
    fields = list(table.columns[3:])
    summary = dict(query_equal_means=table[fields].mean().to_dict(),
                   drifter_equal_means=table.groupby("id")[fields].mean().mean().to_dict(),
                   nearest_distance_max_km=float(table.nearest_training_start_km.max()),
                   local_id_count_min=int(table.distinct_training_ids_within_100km.min()),
                   convex_hull_definition="Planar longitude/latitude convex hull of all outer training starts",
                   exclusion_or_fallback=False)
    return table, summary


def _selected_targets(run, cfg, guard, query):
    from .conditional_mdn_s5_e3_formal_context import authorization
    auth = authorization(run, cfg)
    source = ROOT / auth["deferred_target_path"]
    previous = guard.outer_allowed
    try:
        guard.outer_allowed = True
        if file_sha256(source) != auth["deferred_target_sha256"]:
            raise ValueError("Outer target source changed after final audit")
        targets = inp.read_frame(source, columns=inp.KEY + ["endpoint_lon", "endpoint_lat", "outside"],
                                 filters=[("id", "in", query.id.astype(int).unique().tolist()),
                                          ("origin_source_obs", "in", query.origin_source_obs.astype(int).tolist())])
    finally:
        guard.outer_allowed = previous
    selected = query[inp.KEY].merge(targets, on=inp.KEY, validate="one_to_one", how="left", indicator=True)
    if (not selected._merge.eq("both").all() or selected.outside.any()
            or not np.isfinite(selected[["endpoint_lon", "endpoint_lat"]]).all().all()):
        raise ValueError("Selected display target roster changed")
    return selected[["endpoint_lon", "endpoint_lat"]].to_numpy()


def _maps(paths, run, cfg, guard, base, acceptance, cohorts, figures, audit):
    """Nine models × twelve fixed keys; saved regions and separate display RNG."""
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import PowerNorm
    import shapely
    from shapely.geometry import box
    from data3001.modelling.baselines import position_error_s4_e8 as geometry
    from data3001.modelling.baselines import position_error_s4_e8_inputs as old_inputs
    from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
    from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
    from . import conditional_gaussian_s5_e1_full as old_io
    from . import local_gmm_s5_e2 as old_model
    from . import conditional_mdn_s5_e3_numerics as num
    positions = fixed_case_positions()
    query = cohorts["C_outer"]["query"]
    if len(query) != 33971 or not query[inp.KEY].equals(query.sort_values(inp.KEY)[inp.KEY]):
        raise ValueError("Map source-key order changed")
    selected = query.iloc[positions].copy()
    targets = _selected_targets(run, cfg, guard, selected)
    geo = Geography(paths)
    train, _ = old_inputs.load_training(cfg)
    pool = opt.cache(train, geo)
    controls = ROOT / "results/runs" / cfg["baseline_run"]
    old_config_path = require_audited_file(ROOT / "provenance/runs" / cfg["baseline_run"] / "run.json", audit)
    old_cfg = json.loads(old_config_path.read_text())["config"]
    n, m = acceptance["energy_count"], acceptance["region_count"]
    region_path = base / f"C_outer/outer_score/N{n}_M{m}/scores.parquet"
    scores = pd.read_parquet(require_audited_file(region_path, audit), columns=["position", "K", "region_json"],
                             filters=[("position", "in", positions.tolist())])
    if scores.duplicated(["position", "K"]).any() or len(scores) != 12 * 6:
        raise ValueError("Missing fixed-example saved MDN regions")
    scores = scores.set_index(["position", "K"])
    parameters = {}
    for k in KS:
        with np.load(require_audited_file(base / "C_outer" / f"K{k}" / "parameters.npz", audit), allow_pickle=False) as archive:
            if not np.array_equal(archive["query_keys"][positions], selected[inp.KEY].to_numpy(np.int64)):
                raise ValueError("Fixed example forecast keys differ")
            parameters[k] = {name: archive[name][positions].copy() for name in ("pi", "mu", "cov", "origins")}
    examples, extents = [], []
    for case, (position, target) in enumerate(zip(positions, targets)):
        row = selected.iloc[case]
        key = tuple(int(row[name]) for name in inp.KEY)
        batch, offset = divmod(int(position), int(old_cfg["batch_size"]))
        stem = f"{batch:05d}"
        old = old_io.read_bundle(require_audited_file(controls / "C_outer/parameters" / f"{stem}.json.gz", audit))[offset]
        regions = old_io.read_bundle(require_audited_file(controls / "C_outer/regions" / f"{stem}.json.gz", audit))[offset]["regions"]
        if tuple(int(old[name]) for name in inp.KEY) != key:
            raise ValueError("Historical-control display source key differs")
        with np.load(require_audited_file(controls / "C_outer/lineage" / f"{stem}.npz", audit), allow_pickle=False) as archive:
            lineage = old_io.unpack_lineage(archive["indices"], archive["offsets"], offset)
        donor = pool.take(lineage)
        clouds = {"ExactPoint": (donor.points, np.full(len(donor.points), 1/len(donor.points)))}
        cloud, weight, _ = geometry.component_cloud(donor.points, donor.sd, donor.usable, DISPLAY_COUNT,
                                                    ("mdn_s5_e3_display_only", DISPLAY_SEED, *key, "EndpointCI"))
        clouds["EndpointCI"] = (cloud, weight)
        cloud = np.concatenate(old_model.draw_components(old["models"]["1"], old_model.normals(DISPLAY_COUNT, 2,
                                ("mdn_s5_e3_display_only", DISPLAY_SEED, *key, "LocalGaussian"))))
        clouds["LocalGaussian"] = (cloud, np.full(len(cloud), 1/len(cloud)))
        boundaries = {}
        for name, label in (("ExactPoint", "ExactPoint"), ("EndpointCI", "EndpointCI"), ("LocalGaussian", "1")):
            boundary = geometry.ellipse_boundary(regions[label]["region"])
            boundaries[name] = np.column_stack(geometry.INVERSE.transform(boundary[:, 0]*1000, boundary[:, 1]*1000))
        for k in KS:
            p = parameters[k]
            packet = dict(origin=p["origins"][case], weights=p["pi"][case], means=p["mu"][case],
                          cholesky=np.linalg.cholesky(p["cov"][case]))
            cloud = num.draw(packet, np.random.default_rng(_display_seed(key, f"MDN{k}")).random((DISPLAY_COUNT, 3)))
            clouds[f"MDN{k}"] = (cloud, np.full(DISPLAY_COUNT, 1/DISPLAY_COUNT))
            region = json.loads(scores.loc[(int(position), k), "region_json"])["region"]
            boundary = geometry.ellipse_boundary(region)
            boundaries[f"MDN{k}"] = np.column_stack(geometry.INVERSE.transform(boundary[:, 0]*1000, boundary[:, 1]*1000))
        origin = np.asarray([row.lon, row.lat])
        allpoints = np.vstack([value[0] for value in clouds.values()] + list(boundaries.values()) + [origin[None], target[None]])
        extents.append([*allpoints.min(axis=0), *allpoints.max(axis=0)])
        examples.append(dict(position=int(position), key=key, origin=origin, target=target,
                             clouds=clouds, boundaries=boundaries))
    extents = np.asarray(extents)
    extent = [np.floor(extents[:, 0].min()*2)/2-.5, np.floor(extents[:, 1].min()*2)/2-.5,
              np.ceil(extents[:, 2].max()*2)/2+.5, np.ceil(extents[:, 3].max()*2)/2+.5]
    maximum = 0.
    for example in examples:
        edges, histogram = display_histograms(example["clouds"], extent)
        example["histogram"] = histogram
        maximum = max(maximum, max(value.max() for value in histogram.values()))
    lines = []
    for part in shapely.get_parts(geo.land.intersection(box(*extent))):
        if part.geom_type == "Polygon":
            lines.append(np.asarray(part.exterior.coords))
    normalization = PowerNorm(gamma=.5, vmin=0, vmax=maximum)
    files, roster = [], []
    for number, example in enumerate(examples, 1):
        fig, axes = plt.subplots(3, 3, figsize=(16, 13), sharex=True, sharey=True, layout="constrained")
        for ax, name in zip(axes.flat, MODELS):
            mesh = ax.pcolormesh(*edges, np.ma.masked_equal(example["histogram"][name], 0), norm=normalization, cmap="viridis", rasterized=True)
            ax.add_collection(LineCollection(lines, colors="#34485e", linewidths=.5))
            ax.plot(*example["boundaries"][name].T, color="#e64f87", lw=1.1)
            ax.scatter(*example["origin"], s=24, facecolor="white", edgecolor="black", zorder=5)
            ax.scatter(*example["target"], marker="*", s=65, color="#ff9b55", edgecolor="black", zorder=5)
            label = name + (" (selected)" if name == acceptance["primary_model"] else "")
            ax.set_title(label, fontsize=10)
            ax.set(xlim=(extent[0], extent[2]), ylim=(extent[1], extent[3]), xlabel="Longitude", ylabel="Latitude")
            ax.set_aspect(1/max(np.cos(np.deg2rad((extent[1]+extent[3])/2)), .1))
        fig.colorbar(mesh, ax=axes.ravel().tolist(), shrink=.6,
                     label="Probability per 0.5° display cell (shared square-root colour scale)")
        fig.suptitle(f"Fixed case {number}/12 · source position {example['position']} · key {example['key']} · day 7")
        name = f"fixed_case_{number:02d}.png"
        fig.savefig(figures / name, dpi=140, bbox_inches="tight")
        plt.close(fig)
        files.append(name)
        roster.append(dict(number=number, position=example["position"], key=list(example["key"])))
    return files, dict(examples=roster, selection="floor(j * (33971-1) / 11), j=0,...,11; source-key order",
                      common_extent=extent, common_vmax=float(maximum), display_cell_degrees=.5,
                      display_samples=DISPLAY_COUNT, display_seed=DISPLAY_SEED, samples_used_for_metrics=False,
                      region_source=str(region_path.relative_to(ROOT)), complete_display_cloud_mass_preserved=True)


def _runtime(run):
    path = run["provenance"] / "formal_v1/resource_ledger.json"
    if not path.exists():
        return dict(record_available=False)
    ledger = json.loads(path.read_text())
    entries = ledger.get("entries", [])
    active = ledger.get("active")
    tracked = entries + ([active] if active else [])
    return dict(record_available=True, completed_supervised_task_wall_seconds=sum(r["elapsed_seconds"] for r in entries),
                prior_supervised_task_wall_seconds=ledger.get("prior_compute_seconds", 0),
                active_snapshot_seconds=active.get("elapsed_seconds", 0) if active else 0,
                peak_process_tree_rss_gib=max((r.get("peak_process_tree_rss_bytes", 0) for r in tracked), default=0)/2**30,
                peak_run_storage_gib=max((r.get("peak_storage_bytes", 0) for r in tracked), default=0)/2**30,
                active_stage=active.get("label") if active else None,
                resource_limit_seconds=ledger.get("resource_limit_seconds"),
                note="Recorded supervised-task wall time only. Unsupervised checks and calendar gaps are excluded; "
                     "these sums are not total CPU time or full calendar duration. Prior time includes pilot/optimization. "
                     "The time ceiling was explicitly waived. Active entry is provisional.")


def _write_documents(output, run, summary, comparisons, choice, acceptance, diagnostics, support,
                     runtime, charts, maps, report_seconds):
    selected = acceptance["primary_model"]
    verdict = "达到预先规定的整体保留标准" if acceptance["overall_retention"] else "未达到预先规定的整体保留标准"
    added = ("本轮选择不支持增加成分；K*=1 不证明真实落点分布单峰。" if choice["selected_k"] == 1 else
             f"K*={choice['selected_k']}；相对 MDN1 的外层增成分验收：{'通过' if acceptance['supports_added_components'] else '未通过'}。")
    columns = ["baseline", "es_delta", "es_lower", "es_upper", "hit_delta", "hit_lower", "hit_upper",
               "area_ratio", "area_lower", "area_upper", "eligible"]
    numerical_columns = ["baseline", "es_three_se", "es_audit_three_se", "es_independent_delta_drift",
                         "hit_numerical_disagreement", "area_numerical_relative_drift"]
    summary_table = summary.loc[MODELS, METRICS]
    summary_table.index.name = "model"
    support_text = json.dumps(support, ensure_ascii=False, indent=2)
    runtime_text = json.dumps(dict(runtime, report_generation_seconds=report_seconds), ensure_ascii=False, indent=2)
    body = f"""# Step 5 E3 · 条件 MDN 完整开发验证

事先由内层选择 **{selected}（K*={choice['selected_k']}）**；{verdict}。{added}

最终主模型由内层结果冻结。外层较优的未选 K 只说明复杂度敏感性，不能在本轮改选。九种独特模型完整保留；K*=1 时不额外计入一个 MDN-K* 模型。

## 数据与模型

七天落点分布；全部 265,393 条训练配对 / 338 ID（2001–2019），全部 33,971 条外层开发查询 / 45 ID（2020–2022）。内层两个时间窗口共 86,373 条查询 / 104 个不同 ID；先在 ID/窗口内平均、再在同 ID 的窗口间平均，最后 ID 等权。训练为配对等权，评估为 drifter 等权。外层曾被多次检查，**不是独立最终测试**；517 个 final-test ID 保持锁定。

MDN1/2/4/8/16/32 使用相同 2→64 tanh→64 tanh→6K 网络，全训练区域共享参数；每角色每 K 三种子早停，然后用选定种子从头在完整角色训练池重拟合选定 epoch。经纬度输入，输出自身七天位移混合分布；CPU float64，标准化位移协方差下限 0.001。ExactPoint/EndpointCI/LocalGaussian 仍使用原有 100 km / 最多 8,000 donor 定义。

## 九模型完整结果

{_markdown(summary_table)}

ES 单位 km，越低越好；H90 与面积必须一起看。90% 区域是完整预测分布在固定 LAEA 下的**单个公共分位椭圆**；不是成分椭圆并集或 HDR。陆地、域外和远尾概率完整保留，不能解释为真实搁浅或 observed-E。

## 主模型配对比较与区间

{_markdown(comparisons[columns])}

95% 区间为 10,000 次整条 ID 配对 bootstrap，条件于已拟合预测，不含重新训练的不确定性。eligible 是已冻结的综合验收结果，不能只由 ES 点估计推断成功。验收细节见 [acceptance.json](acceptance.json)。

数值误差与独立重复差异：

{_markdown(comparisons[numerical_columns])}

ES 共 {acceptance['energy_count']:,} 节点、8 次 scramble；区域共 {acceptance['region_count']:,} 节点。完整审计已经通过；统计差异不等于数值误差，二者分别报告。

## 内层选择与训练

在符合预定晋级条件的候选中，内层合并 ES 最优 K={choice['best_es_k']}；1SE 暂选 K={choice['provisional_k']}；按预定质量规则确定 K*={choice['selected_k']}。这不是未加约束的 ES 排名：合并 ES 较低的候选，仍可能因为某个时间窗口退化而被排除。各 K 的窗口得分与淘汰原因见 [selection.json](selection.json)。无外层调参。各角色完整训练诊断：

{_markdown(diagnostics)}

mixture_entropy_*_nats 报告成分概率熵的查询均值、最小值和最大值；effective_components_mean 是 exp(entropy) 的查询均值，不解释成真实洋流条数。near_floor_probability_mass 是最小标准化协方差特征值 ≤1.01×0.001 的成分概率质量（查询等权诊断）。触及 epoch 上限的种子不能声称已经收敛；三种子曲线说明优化敏感性，不提供全量 ES 的种子不确定性。

## 外推与资源

以下支撑诊断覆盖所有外层查询，不据此删样本、改权重或回退。距离为精确 WGS84，100 km 内 ID 计数不采用 8,000 配对截断。

```json
{support_text}
```

```json
{runtime_text}
```

## 12 个预声明地图

按冻结源键排序取 floor(j×(33971−1)/11)，j=0,…,11；没有按命中或改善筛选。九模型、十二案例使用相同视域、0.5° 展示格和色标。白点为真实起点，星号为记录的七天终点，红线来自已保存的评分用 90% 椭圆。云图用独立固定种子的展示抽样，不重新计算指标，不截断后归一化；有限展示抽样不等于全部连续支持。成分是统计近似，不是识别出的洋流。

{chr(10).join(f'![{name}](figures/{name})' for name in charts + maps)}

## 与 Brolly 文献的关系

[Brolly (2023), Table 1]({BROLLY_URL}) 的全球四天验证平均 log score 为 TM/DTMC −1.74、GTGP −1.30、MDN1 −1.14、MDN32 −1.11（越高越好；原经纬度位移单位）。其 TM 全球比较排除了 7% 零概率验证样本。本项目是区域七天、时间划分、整 ID 评价的 Energy Score（越低越好），因此**不能把两组数值并排排名或声称数值复现**。借鉴的是位置条件混合分布方法。

## 可复用预测接口

保存权重和标准化器可直接接受真实 lon/lat，返回全部 K 权重、east/north 均值位移（km）、完整协方差（km²）和 WGS84 落点样本。接口不读取验证落点；样本不裁剪陆地或域外质量。参见 [inference_usage.md](inference_usage.md)。

## English technical summary

The inner-only procedure selected {selected}. The preregistered overall retention gate {'passed' if acceptance['overall_retention'] else 'did not pass'}. All six MDN complexities and three unchanged local controls were evaluated on the same 33,971 seven-day outer-development queries from 45 drifters. Training uses pair-equal NLL; evaluation averages within drifter before equal-ID averaging. Each final network is a full-pool refit at its training-only selected seed and epoch. The fixed small network, covariance floor, AdamW regularisation and ID-held-out early stopping are experimental conditions, not assurances against overfitting. The final audit passed; all original boundaries remain in force.

Energy Score uses WGS84 ECEF chord distances in km. The common 90% region is one LAEA quantile ellipse derived solely from each forecast distribution. Land, outside-domain and tail probability remain in every forecast. Bootstrap intervals condition on fitted models. Unselected outer K values are sensitivity evidence only. K=1 selection does not establish physical unimodality; components do not identify current systems. The 12 source-order displays were fixed independently of outcomes. Support diagnostics do not change forecasts or the cohort. No final-test evidence is claimed.

已保留 12 条边界配对和 ID 75447 的一分钟起点差异：这是用户接受保留的来源备注，不是已经消除的来源冲突。七天位置条件 Markov 核不证明位置过程严格 Markov，也不证明任意时长递推准确，不能作为已验证油污风化模型。

运行：`{run['results'].name}`。完整表格：[summary.csv](summary.csv)、[per_id.csv](per_id.csv)、[comparisons.csv](comparisons.csv)、[selection.json](selection.json)、[final_audit.json](final_audit.json)、[delivery_manifest.json](delivery_manifest.json)。
"""
    (output / "REPORT.md").write_text(body, encoding="utf-8")
    # The HTML uses the same source tables and claims, with links to full detail.
    sections = [f"<section><h2>九模型完整结果</h2>{summary_table.to_html(float_format=lambda x: f'{x:,.6f}')}<img src='figures/outer_comparison.png'></section>",
                f"<section><h2>主模型配对比较</h2>{comparisons[columns].to_html(index=False, float_format=lambda x: f'{x:,.6f}')}<img src='figures/paired_effects.png'><img src='figures/per_id_effects.png'><p>95% 整 ID 配对 bootstrap；区间条件于已拟合模型。</p></section>",
                "<section><h2>内层选择与三种子训练</h2>" + "".join(f"<img src='figures/{name}'>" for name in charts if name.startswith(("inner_", "training_"))) + "</section>",
                "<section><h2>十二个固定源键案例</h2><p>九模型与十二案例共用视域、色标和单椭圆规则；白点起点，星号终点。展示抽样不参与指标。</p>" + "".join(f"<img src='figures/{name}'>" for name in maps) + "</section>"]
    document = f"""<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Step 5 E3 · 条件 MDN</title>
<style>body{{margin:0;background:#f4f6f9;color:#263546;font:16px/1.75 system-ui}}main{{max-width:1300px;margin:auto;padding:32px}}section{{background:white;border-radius:12px;padding:24px;margin:24px 0;overflow:auto}}img{{width:100%;height:auto;margin:12px 0}}table{{border-collapse:collapse;font-size:13px;width:100%}}td,th{{padding:8px;border-bottom:1px solid #ddd;text-align:right}}a{{color:#6040a0}}.note{{color:#536577}}pre{{white-space:pre-wrap}}</style><main>
<h1>Step 5 E3 · 条件 MDN</h1><p><strong>{selected}（内层选定 K*={choice['selected_k']}）</strong>：{verdict}。</p><p>{added}</p>
<p class="note">七天预测；2001–2019 训练，2020–2022 外层开发验证；33,971 查询 / 45 ID；九种独特模型。完整审计通过，final-test 未访问。外层未选 K 不用于改选模型。</p>
<p>ES 越低越好；命中率和区域面积共同判断。完整陆地、域外、远尾概率保留。<a href="REPORT.md">完整中英报告</a> · <a href="per_id.csv">全部逐 ID 指标</a> · <a href="comparisons.csv">配对验收</a> · <a href="inference_usage.md">预测接口</a> · <a href="final_audit.json">审计</a></p>
{''.join(sections)}<section><h2>来源、限制与资源</h2><p>边界配对及 ID 75447 的一分钟差异按决定保留。开发验证曾被多次检查；区间不含重新拟合不确定性。成分不是已识别洋流，单椭圆不是 HDR。</p><p><a href="{BROLLY_URL}">Brolly Table 1</a> 的全球四天 log scores 与本项目区域七天 ES 不可直接排名；其 TM 全球比较另有 7% 零概率样本排除。</p><pre>{html.escape(support_text)}</pre><pre>{html.escape(runtime_text)}</pre></section><footer>{html.escape(run['results'].name)}</footer></main></html>"""
    (output / "review.html").write_text(document, encoding="utf-8")


def build_report(run_name):
    started = time.monotonic()
    # Audit must be read before result tables. The shared guard then protects
    # canonical data and final-test while allowing only this additive delivery.
    run = {part: ROOT / (part + "/runs") / run_name for part in ("results", "provenance")}
    if Path(run_name).name != run_name or not run_name.startswith("conditional_mdn_s5_e3_"):
        raise ValueError("Invalid MDN run name")
    audit = require_completed_audit(run)
    from .conditional_mdn_s5_e3_formal_context import context
    paths, run, cfg, _, guard = context(run_name)
    output = ROOT / "results/deliverables/conditional_mdn_s5_e3"
    guard.allowed.append(output.resolve())
    if (output / "delivery_manifest.json").exists():
        prior = json.loads((output / "delivery_manifest.json").read_text())
        if prior.get("run") != run_name:
            raise FileExistsError("Delivery folder belongs to a different run")
    output.mkdir(parents=True, exist_ok=True)
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(output / ".matplotlib")
    import matplotlib
    matplotlib.use("Agg")
    base = run["results"] / "formal_v1"
    choice = json.loads((base / "selection.json").read_text())
    acceptance = json.loads((base / "acceptance.json").read_text())
    summary = pd.read_csv(base / "summary.csv", index_col=0)
    per_id = pd.read_csv(base / "per_id.csv")
    comparisons = pd.read_csv(base / "comparisons.csv")
    validate_summary(summary, choice["selected_k"])
    if (acceptance.get("status") != "complete" or acceptance["selected_k"] != choice["selected_k"]
            or acceptance["primary_model"] != f"MDN{choice['selected_k']}"
            or acceptance["query_count"] != 33971 or acceptance["unique_validation_ids"] != 45
            or per_id.id.nunique() != 45 or len(per_id) != 45 * 9):
        raise ValueError("Final delivery roster or selected model changed")
    for name in ("summary.csv", "per_id.csv", "comparisons.csv", "selection.json", "acceptance.json"):
        shutil.copyfile(base / name, output / name)
    shutil.copyfile(run["provenance"] / "formal_v1/final_audit.json", output / "final_audit.json")
    manifests, diagnostics = _training_manifests(base)
    diagnostics.to_csv(output / "training_diagnostics.csv", index=False)
    charts = _plot_metrics(summary, comparisons, per_id, choice, manifests, figures)
    cohorts = inp.cohorts(cfg)
    support_table, support = _support_diagnostics(cohorts["C_outer"]["fit"], cohorts["C_outer"]["query"])
    support_table.to_parquet(output / "support_diagnostics.parquet", index=False)
    atomic_json(output / "support_summary.json", support)
    maps, display = _maps(paths, run, cfg, guard, base, acceptance, cohorts, figures, audit)
    atomic_json(output / "fixed_examples.json", display)
    from .conditional_mdn_s5_e3_inference import load_selected_model
    predictor = load_selected_model(run_name)
    # An arbitrary coordinate smoke check uses neither a validation origin nor
    # its target. Saved-model prediction itself remains target independent.
    mixture = predictor.mixture([-75., 35.])
    samples = predictor.sample([-75., 35.], count=16, seed=DISPLAY_SEED)
    if not np.isfinite(samples).all() or not np.isclose(mixture["weights"].sum(), 1):
        raise ValueError("Saved-model inference smoke check failed")
    atomic_json(output / "inference_check.json", dict(passed=True, origin=[-75., 35.],
                sample_shape=list(samples.shape), selected_k=choice["selected_k"], validation_target_dependency=False))
    usage = f"""# Saved MDN prediction

From the work_place Python environment:

```python
from data3001.modelling.continuous_models.conditional_mdn_s5_e3_inference import load_selected_model
model = load_selected_model({run_name!r})
mixture = model.mixture([[-75.0, 35.0]])
endpoints = model.sample([[-75.0, 35.0]], count=1000, seed=20261126)
```

`weights`: Q×K; `means_km`: Q×K×2 east/north geodesic displacement;
`covariances_km2`: Q×K×2×2; samples: Q×count×2 longitude/latitude.
The stored scaler and completed full-refit weights are loaded. No validation
targets, raw training data or validation coordinates are needed by this API.
All components participate; land and outside-domain samples are retained.
This is a seven-day, position-only model. Prediction outside training support
is extrapolation and has not been independently validated.

Selected checkpoint: `{predictor.metadata['checkpoint']}`.
"""
    (output / "inference_usage.md").write_text(usage, encoding="utf-8")
    runtime = _runtime(run)
    _write_documents(output, run, summary, comparisons, choice, acceptance, diagnostics, support,
                     runtime, charts, maps, time.monotonic()-started)
    # Recheck inputs after potentially long plotting and support diagnostics.
    require_completed_audit(run)
    if guard.denied:
        raise PermissionError("Report access guard recorded denied activity")
    manifest = dict(status="complete", run=run_name, selected_k=choice["selected_k"], unique_models=MODELS,
                    source_audit_sha256=file_sha256(run["provenance"] / "formal_v1/final_audit.json"),
                    evidence_sha256=audit["evidence_sha256"], final_test_access=False,
                    display_only=True, scientific_results_recomputed=False,
                    report_seconds=time.monotonic()-started,
                    files_sha256={str(p.relative_to(output)): file_sha256(p) for p in sorted(output.rglob("*"))
                                  if p.is_file() and p.name != "delivery_manifest.json" and ".matplotlib" not in p.parts})
    atomic_json(output / "delivery_manifest.json", manifest)
    return dict(report=str(output / "REPORT.md"), review=str(output / "review.html"),
                selected_k=choice["selected_k"], overall_retention=acceptance["overall_retention"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    args = parser.parse_args()
    print(json.dumps(build_report(args.run), ensure_ascii=False))


if __name__ == "__main__":
    main()
