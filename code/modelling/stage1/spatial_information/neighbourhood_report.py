"""Independent saved-forecast checks and one readable, non-visual report."""
import json

import numpy as np
import pandas as pd
from pyproj import Geod
import shapely as sh
from shapely.geometry import shape

from data3001.modelling.baselines.cv import KEYS, summarize_scores
from data3001.modelling.common.runtime import save_frame


def independent_quadratic(q, uq, r, ur, truth):
    states = set(q) | set(r)
    d = {j: r.get(j, 0.)-q.get(j, 0.) for j in states}
    A = sum(x*x for x in d.values()) + (ur-uq)**2
    B = 2*(sum(q.get(j, 0.)*d[j] for j in states) + uq*(ur-uq) - d.get(truth, 0.))
    C = 1 + sum(x*x for x in q.values()) + uq*uq - 2*q.get(truth, 0.)
    return np.array([A, B, C], dtype=float)


def _base(model, family, h, i):
    if family == "B1":
        p = {int(j): float(v) for j, v in model["B1"].get(str(h), {}).items()}
        return p, 0. if p else 1.
    if family == "B2":
        p = {int(j): float(v) for j, v in model["B2"].get(f"{h}:{i}", {}).items()}
        return p, 0. if p else 1.
    item = model[family].get(f"{h}:{i}", {"probabilities": {}, "unresolved": 1.})
    return {int(j): float(v) for j, v in item["probabilities"].items()}, float(item["unresolved"])


def _forecast(model, name, h, i, alpha):
    if name == "B0":
        return {i: 1.}, 0.
    if name in ("B1", "B2"):
        return _base(model, name, h, i)
    q, uq = _base(model, "B2", h, i)
    family = name.rsplit("-", 1)[0]
    r, ur = _base(model, "B1" if family == "Global" else family, h, i)
    # Deliberately independent of the production mixing function.
    return ({j: (1-alpha)*q.get(j, 0.)+alpha*r.get(j, 0.) for j in set(q)|set(r)},
            (1-alpha)*uq+alpha*ur)


def audit_score_rows(scores, models):
    maximum = 0.
    for (fold, h, i, name), g in scores.groupby(["outer_fold", "horizon_days", "origin_cell_1", "model"]):
        model = models[int(fold)]
        if set(g.id) & set(model["training_ids"]):
            raise ValueError("Saved model fitted a scored ID.")
        alpha = float(g.alpha_value.iloc[0])
        p, u = _forecast(model, name, int(h), int(i), alpha)
        if abs(sum(p.values())+u-1) > 1e-10 or min([u, *p.values()]) < 0:
            raise ValueError("Saved distribution has invalid probability mass.")
        truth = g.destination_cell_1.map(p).fillna(0.).to_numpy()
        direct = 1 + sum(x*x for x in p.values()) + u*u - 2*truth
        difference = np.max(np.abs(direct-g.brier_failure_penalized.to_numpy()))
        maximum = max(maximum, float(difference))
        if (difference > 1e-11 or not np.allclose(truth, g.true_probability, atol=1e-12, rtol=0)
                or not np.allclose(u, g.unresolved_mass, atol=1e-12, rtol=0)):
            raise ValueError("Independent saved-model score reconstruction failed.")
        expected = {"complete": u == 0., "brier": direct if u == 0. else np.nan,
                    "outside_probability": p.get(-2, 0.)}
        with np.errstate(divide="ignore"):
            expected.update(log_loss=-np.log(truth) if u == 0. else np.nan,
                            log_loss_lower=-np.log(truth+u), log_loss_upper=-np.log(truth))
        # Independently walk ranked states, retaining every cutoff tie.
        ranked = sorted(((v, j) for j, v in p.items() if v > 0), reverse=True)
        for level in (50, 80, 90, 95):
            available = sum(v for v, j in ranked) >= level/100-1e-12
            states, region_mass = set(), np.nan
            if available:
                cumulative, cutoff = 0., None
                for value, state in ranked:
                    cumulative += value
                    if cumulative+1e-12 >= level/100:
                        cutoff = value
                        break
                states = {state for value, state in ranked if value >= cutoff-1e-12}
                region_mass = sum(p[state] for state in states)
            expected.update({f"region{level}_available": available,
                             f"region{level}_mass": region_mass,
                             f"region{level}_cells": sum(state >= 0 for state in states),
                             f"region{level}_hit": g.destination_cell_1.isin(states).to_numpy()})
        maximum_p = max(p.values(), default=0.)
        top = min((j for j, v in p.items() if abs(v-maximum_p) <= 1e-12), default=-1) if maximum_p > 0 else -1
        expected["top_cell_hit"] = g.destination_cell_1.eq(top).to_numpy()
        for field, value in expected.items():
            if not np.allclose(g[field].to_numpy(float), value, rtol=0, atol=1e-11, equal_nan=True):
                raise ValueError("Independent saved-model diagnostic reconstruction failed: "+field)
    return {"score_rows_verified": len(scores), "maximum_score_difference": maximum}


def paired_intervals(scores, comparisons=None, replicates=200, seed=20261004):
    comparisons = comparisons or [
        ("Local-U-Grid", "B2"), ("Local-A-Grid", "B2"),
        ("Local-U-Analytic", "B2"), ("Local-A-Analytic", "B2"),
        ("Local-U-Grid", "Global-Grid"), ("Local-A-Grid", "Global-Grid"),
        ("Local-U-Analytic", "Global-Analytic"), ("Local-A-Analytic", "Global-Analytic"),
        ("Local-A-Grid", "Local-U-Grid"), ("Local-A-Analytic", "Local-U-Analytic")]
    rows = []
    for h, g in scores.groupby("horizon_days"):
        frame = g.assign(loss=g.pair_count*g.brier_failure_penalized)
        totals = frame.groupby(["outer_fold", "id", "model"], as_index=False).agg(
            loss=("loss", "sum"), pair_count=("pair_count", "sum"))
        loss = totals.pivot(index=["outer_fold", "id"], columns="model", values="loss")
        denom = totals.loc[totals.model.eq("B2")].set_index(["outer_fold", "id"]).pair_count.reindex(loss.index).to_numpy()
        rng = np.random.default_rng(seed+int(h))
        units = [np.flatnonzero(loss.index.get_level_values(0) == f)
                 for f in sorted(loss.index.get_level_values(0).unique())]
        draws = [np.concatenate([rng.choice(ix, len(ix), replace=True) for ix in units]) for _ in range(replicates)]
        for left, right in comparisons:
            d = (loss[left]-loss[right]).to_numpy()
            estimates = [d[ix].sum()/denom[ix].sum() for ix in draws]
            low, high = np.quantile(estimates, [.025, .975])
            rows.append({"horizon_days": int(h), "comparison": f"{left} - {right}",
                         "delta_brier": d.sum()/denom.sum(), "lower": low, "upper": high,
                         "replicates": replicates,
                         "scope": "Paired whole-ID within fixed outer folds; conditional on saved fits; no refitting/selection uncertainty; exploratory comparisons"})
    return pd.DataFrame(rows)


def region_summary(scores):
    rows = []
    for (h, model), g in scores.groupby(["horizon_days", "model"]):
        w = g.pair_count.to_numpy()
        for level in (50, 80, 90, 95):
            available = g[f"region{level}_available"].to_numpy(bool)
            rows.append({"horizon_days": int(h), "model": model, "nominal_region_pct": level,
                         "hit_pct": 100*np.average(g[f"region{level}_hit"], weights=w),
                         "available_pct": 100*np.average(available, weights=w),
                         "mean_mass_when_available": np.average(g.loc[available, f"region{level}_mass"], weights=w[available]) if available.any() else np.nan,
                         "mean_cells_when_available": np.average(g.loc[available, f"region{level}_cells"], weights=w[available]) if available.any() else np.nan})
    return pd.DataFrame(rows)


def _independent_selection(counts, checkpoint, evaluation_ids, accum):
    part = counts.loc[counts.id.isin(evaluation_ids)].groupby(
        ["horizon_days", "origin_cell_1", "destination_cell_1"], as_index=False).pair_count.sum()
    for (h, origin), group in part.groupby(["horizon_days", "origin_cell_1"]):
        q, uq = _base(checkpoint, "B2", int(h), int(origin))
        for family in ("Global", "Local-U", "Local-A"):
            r, ur = _base(checkpoint, "B1" if family == "Global" else family, int(h), int(origin))
            coefficients = sum((independent_quadratic(q, uq, r, ur, int(row.destination_cell_1))*row.pair_count
                                for row in group.itertuples()), start=np.zeros(3))
            entry = accum.setdefault((family, int(h)), [np.zeros(3), 0])
            entry[0] += coefficients
            entry[1] += int(group.pair_count.sum())


def audit_selections(paths, run, counts, selections, final_selections, saved_models):
    outer_table = pd.read_csv(run["provenance"]/"outer_folds.csv")
    inner_table = pd.read_csv(run["provenance"]/"inner_folds.csv")
    verified = 0

    def verify(rows, accum):
        nonlocal verified
        for row in rows.itertuples():
            terms, total = accum[(row.family, int(row.horizon_days))]
            A, B, C = terms/total
            values = np.array([A*(k/10)**2+B*(k/10)+C for k in range(11)])
            grid = next(k/10 for k in range(11) if abs(values[k]-values.min()) <= 1e-12)
            analytic = float(np.clip(-B/(2*A), 0, 1)) if A else 0.
            chosen = grid if row.method == "Grid" else analytic
            if abs(chosen-row.alpha_value) > 1e-10:
                raise ValueError("Independent alpha selection disagrees with fitting pipeline.")
            score_name = "inner_brier" if hasattr(row, "inner_brier") else "tuning_brier"
            if abs(A*chosen**2+B*chosen+C-getattr(row, score_name)) > 1e-10:
                raise ValueError("Independent tuning score mismatch.")
            verified += 1

    for fold, group in inner_table.groupby("outer_fold"):
        outer_train = set(outer_table.loc[outer_table.outer_fold.ne(fold), "id"])
        if set(group.id) != outer_train:
            raise ValueError("Saved inner/outer membership mismatch.")
        accum = {}
        for k, held in group.groupby("inner_fold"):
            checkpoint = json.loads((run["results"]/"fit_checkpoints"/f"outer{fold}_inner{k}.json").read_text())
            if set(checkpoint["training_ids"]) != outer_train-set(held.id):
                raise ValueError("Saved inner model membership mismatch.")
            _independent_selection(counts, checkpoint, set(held.id), accum)
        verify(selections.loc[selections.outer_fold.eq(fold)], accum)
    accum = {}
    for fold, held in outer_table.groupby("outer_fold"):
        checkpoint = saved_models[int(fold)]
        if set(checkpoint["training_ids"]) != set(outer_table.id)-set(held.id):
            raise ValueError("Saved outer model membership mismatch.")
        _independent_selection(counts, checkpoint, set(held.id), accum)
    verify(final_selections, accum)
    return verified


def _table(frame, fields):
    def value(x):
        if isinstance(x, (float, np.floating)):
            return f"{x:.6f}" if np.isfinite(x) else str(x)
        return str(x)
    return "\n".join(["| " + " | ".join(fields) + " |",
                       "| " + " | ".join("---" for _ in fields) + " |"] +
                      ["| " + " | ".join(value(getattr(r, k)) for k in fields) + " |" for r in frame[fields].itertuples(index=False)])


def reconstruct_aligned_basis(donors, anchors, domain, land, audit):
    """Independent saved finite-estimator reconstruction, without fit helpers."""
    n, m = len(donors), len(anchors)
    if not n or not m:
        return {}, 1.
    geo = Geod(ellps="WGS84")
    x = donors[["origin_lon", "origin_lat", "endpoint_lon", "endpoint_lat"]].to_numpy(float)
    bearing, _, distance = geo.inv(x[:, 0], x[:, 1], x[:, 2], x[:, 3])
    total = np.zeros(64802, dtype=float)

    def accumulate(di, ai, weight):
        for start in range(0, len(di), 200000):
            d, a = di[start:start+200000], ai[start:start+200000]
            w = weight if np.isscalar(weight) else weight[start:start+200000]
            lon, lat, _ = geo.fwd(anchors[a, 0], anchors[a, 1], bearing[d], distance[d])
            same = (anchors[a, 0] == x[d, 0]) & (anchors[a, 1] == x[d, 1])
            zero = distance[d] == 0
            lon[zero], lat[zero] = anchors[a[zero], 0], anchors[a[zero], 1]
            lon[same], lat[same] = x[d[same], 2], x[d[same], 3]
            lon = (np.asarray(lon)+180) % 360-180
            lat = np.asarray(lat)
            valid = np.isfinite(lon) & np.isfinite(lat) & (lat >= -90) & (lat < 90)
            inside = valid & sh.intersects_xy(domain, lon, lat)
            water = inside & ~sh.intersects_xy(land, lon, lat) if land is not None else inside
            codes = np.full(len(d), -1, dtype=int)
            codes[valid & ~inside] = -2
            codes[water] = np.floor(lat[water]+90).astype(int)*360+np.floor(lon[water]+180).astype(int)
            if np.isscalar(w):
                total[:] += np.bincount(codes+2, minlength=64802)*w
            else:
                total[:] += np.bincount(codes+2, weights=w, minlength=64802)

    if audit["method"] == "exact":
        for start in range(0, n*m, 200000):
            ix = np.arange(start, min(start+200000, n*m), dtype=np.int64)
            accumulate(ix//m, ix % m, 1/(n*m))
    elif audit["method"] == "balanced":
        # Python-set partition construction is deliberately separate from N1.
        boundaries = np.array(sorted(set(range(0, n*m+1, m)) | set(range(0, n*m+1, n))), dtype=np.int64)
        left, weight = boundaries[:-1], np.diff(boundaries)/(n*m*int(audit["couplings"]))
        rng = np.random.default_rng(int(audit["seed"]))
        for _ in range(int(audit["couplings"])):
            accumulate(rng.permutation(n)[left//m], rng.permutation(m)[left//n], weight)
    else:
        raise ValueError("Unexpected saved integration method.")
    return {j-2: float(total[j]) for j in np.flatnonzero(total) if j != 1}, float(total[1])


def audit_fitted_bases(paths, run, pairs, final_model):
    """Rebuild every U base and two representative final A bases from pairs."""
    verified = 0
    saved_final = json.loads((run["results"]/"final_models.json").read_text())
    from data3001.modelling.baselines.neighbourhood_cv import serialize_local_model
    if saved_final != serialize_local_model(final_model):
        raise ValueError("Serialized final model differs from the fitted model.")
    checkpoints = sorted((run["results"]/"fit_checkpoints").glob("*.json")) + [run["results"]/"final_models.json"]
    for path in checkpoints:
        checkpoint = json.loads(path.read_text())
        part = pairs.loc[pairs.id.isin(checkpoint["training_ids"])]
        groups = {tuple(map(int, key)): g for key, g in part.groupby(["horizon_days", "origin_cell_1"])}
        for key in checkpoint["Local-U"]:
            h, origin = map(int, key.split(":"))
            y, x = divmod(origin, 360)
            adjacent = {((y+dy)*360+(x+dx) % 360) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                        if (dx or dy) and 0 <= y+dy < 180}
            donor_groups = [g for (day, cell), g in groups.items() if day == h and cell in adjacent]
            counts = pd.concat(donor_groups).destination_cell_1.value_counts() if donor_groups else pd.Series(dtype=int)
            expected = (counts/counts.sum()).to_dict() if len(counts) else {}
            observed, u = _base(checkpoint, "Local-U", h, origin)
            states = set(expected) | set(observed)
            if (abs(u-(0. if len(counts) else 1.)) > 1e-12 or any(
                    abs(expected.get(j, 0.)-observed.get(j, 0.)) > 1e-12 for j in states)):
                raise ValueError("Independent local-U reconstruction failed: "+path.name+":"+key)
            verified += 1
    domain = shape(json.loads(paths.asset("transport_D").read_text())["features"][0]["geometry"])
    land = sh.from_wkb(paths.asset("land_mask_high").read_bytes())
    sh.prepare(domain)
    sh.prepare(land)
    aligned_checks = []
    for h in (7, 30):
        choices = [a for a in final_model["numerical_audit"] if a["horizon_days"] == h and a["anchors"] and a["donor_pairs"]]
        chosen = min(choices, key=lambda a: a["anchors"]*a["donor_pairs"])
        i = int(chosen["origin_cell_1"])
        y, x = divmod(i, 360)
        local = pairs.loc[pairs.horizon_days.eq(h)]
        source_y = local.origin_cell_1//360
        source_x = local.origin_cell_1 % 360
        dx = abs(source_x-x)
        nearby = (abs(source_y-y) <= 1) & (np.minimum(dx, 360-dx) <= 1) & local.origin_cell_1.ne(i)
        donors = local.loc[nearby].sort_values("origin_cell_1", kind="stable")
        anchors = local.loc[local.origin_cell_1.eq(i), ["origin_lon", "origin_lat"]].to_numpy()
        p, u = reconstruct_aligned_basis(donors, anchors, domain, land, chosen)
        q, uq = _base(saved_final, "Local-A", h, i)
        error = max([abs(u-uq), *[abs(p.get(j, 0.)-q.get(j, 0.)) for j in set(p)|set(q)]])
        if error > 1e-10:
            raise ValueError("Independent local-A source reconstruction failed.")
        aligned_checks.append({"horizon_days": h, "origin_cell_1": i,
                               "donor_pairs": len(donors), "anchors": len(anchors),
                               "method": chosen["method"], "couplings": chosen["couplings"],
                               "maximum_probability_difference": error,
                               "scope": "Reconstruction of saved finite estimator, not certification of exact product integral"})
    evidence = {"unaligned_bases_rebuilt": verified, "aligned_representatives": aligned_checks}
    paths.publish(run["results"]/"fitted_basis_audit.json", lambda stream: stream.write(json.dumps(evidence, indent=2).encode()))
    return evidence


def audit_and_report(paths, run, result, final_selections, final_model, pairs, *, scenario="pooled", control_reference=None):
    # Audit the serialized artifacts actually handed over, not only memory.
    scores = pd.read_parquet(run["results"]/"outer_scores.parquet")
    pd.testing.assert_frame_equal(scores, result["scores"])
    saved_selection = pd.read_csv(run["results"]/"alpha_selection.csv")
    saved_final = pd.read_csv(run["results"]/"final_alpha_selection.csv")
    pd.testing.assert_frame_equal(saved_selection, result["selection"], check_exact=False, atol=1e-12, rtol=0)
    pd.testing.assert_frame_equal(saved_final, final_selections, check_exact=False, atol=1e-12, rtol=0)
    basis_audit = audit_fitted_bases(paths, run, pairs, final_model)
    counts = pairs.groupby(KEYS, as_index=False).size().rename(columns={"size": "pair_count"})
    common = ["outer_fold", *KEYS, "pair_count"]
    expected = scores.loc[scores.model.eq("B2"), common].sort_values(common).reset_index(drop=True)
    for name, group in scores.groupby("model"):
        pd.testing.assert_frame_equal(group[common].sort_values(common).reset_index(drop=True), expected)
    source_counts = counts.sort_values(KEYS).reset_index(drop=True)
    observed = expected.drop(columns="outer_fold").sort_values(KEYS).reset_index(drop=True)
    pd.testing.assert_frame_equal(source_counts.astype("int64"), observed.astype("int64"))
    saved_models = {fold: json.loads((run["results"]/"fit_checkpoints"/f"outer{fold}_fit.json").read_text())
                    for fold in result["models"]}
    independent = audit_score_rows(scores, saved_models)
    selections_verified = audit_selections(paths, run, counts, result["selection"], final_selections, saved_models)

    # All five old controls must reproduce, not merely have a similar mean.
    parent = paths.root/"results/runs/baseline_blend_cv_20261022T160806_056571Z"
    old = pd.read_csv(parent/"outer_scores.csv") if control_reference is None else control_reference.copy()
    old["model"] = old.model.replace({"Grid": "Global-Grid", "Analytic": "Global-Analytic"})
    matching = scores.loc[scores.model.isin(old.model.unique())]
    key = ["outer_fold", *KEYS, "model"]
    old = old.sort_values(key).reset_index(drop=True)
    matching = matching.sort_values(key).reset_index(drop=True)
    pd.testing.assert_frame_equal(matching[key+["pair_count"]], old[key+["pair_count"]], check_dtype=False)
    for field in ("true_probability", "unresolved_mass", "brier_failure_penalized", "region90_hit", "region90_cells"):
        np.testing.assert_allclose(matching[field].to_numpy(float), old[field].to_numpy(float), atol=1e-11, rtol=0, equal_nan=True)

    summary = summarize_scores(scores)
    intervals = paired_intervals(scores)
    regions = region_summary(scores)
    for name, frame in (("paired_ID_intervals.csv", intervals), ("probability_region_summary.csv", regions)):
        save_frame(paths, run["results"]/name, frame)
    breakdowns = {}
    for label, keys in (("cell", ["horizon_days", "origin_cell_1", "model"]),
                        ("ID", ["horizon_days", "id", "model"])):
        frame = scores.assign(weighted_loss=scores.pair_count*scores.brier_failure_penalized).groupby(keys, as_index=False).agg(
            eligible_pairs=("pair_count", "sum"), total_loss=("weighted_loss", "sum"))
        frame["brier_failure_penalized"] = frame.total_loss/frame.eligible_pairs
        unit = keys[:-1]
        baseline = frame.loc[frame.model.eq("B2"), unit+["brier_failure_penalized"]].rename(
            columns={"brier_failure_penalized": "B2_score"})
        frame = frame.merge(baseline, on=unit, validate="many_to_one")
        frame["delta_vs_B2"] = frame.brier_failure_penalized-frame.B2_score
        breakdowns[label] = frame
        save_frame(paths, run["results"]/f"scores_by_{label}.csv", frame)
    all_numeric = pd.concat([result["numerical_audit"], pd.DataFrame(final_model["numerical_audit"])], ignore_index=True)
    unsettled = all_numeric.loc[~all_numeric.converged]
    numerical_status = "PASS_DECLARED_STABILITY_CHECK" if unsettled.empty else "PROVISIONAL_NUMERICAL_ROWS_REMAIN"
    audit = {**independent, "alpha_selections_independently_verified": selections_verified,
             "fitted_basis_audit": basis_audit,
             "all_nine_models_share_exact_cases": True, "independent_five_controls_reproduced_per_case": True,
             "control_reference": "sealed_parent" if control_reference is None else "regime_specific_independent_procedure",
             "numerical_status": numerical_status, "unsettled_fit_rows": len(unsettled),
             "integration_contributions": int(all_numeric.integration_points.sum()),
             "no_visualisation_created": True, "final_test_read": False,
             "inference_scope": "Exploratory development comparison, conditional-ID bootstrap; no causal or universal superiority claim"}
    status = "Completed comparison" if unsettled.empty else "Completed comparison with numerical caveats"
    lines = [f"# {scenario.capitalize()} neighbourhood baseline — {status}", "",
             "This report asks whether borrowing nearby release-cell information helps 7/30-day endpoint forecasts, and whether moving neighbour displacements to the target cell changes that answer. It does not evaluate a one-year Markov model or a grounding predictor. No visualisation is part of this run.", "",
             "## What was fitted", "",
             "B0 predicts no cell change. B1 uses the whole-R destination frequencies. B2 uses the target cell's frequencies. Global mixes B2 with B1. Local-U mixes B2 with the original endpoints of the eight neighbouring origin cells. Local-A mixes B2 with neighbour displacements applied at the target cell's actual empirical fitting-origin positions. Grid and Analytic select the borrowing weight by two declared methods; a larger weight means more borrowing.", "",
             "All donors start inside frozen R. Both local variants use the same equal-weight donor pairs. The aligned calculation uses WGS84 net displacement, not a reconstructed path. A cell centre is not substituted for the empirical release prior. Repeated balanced couplings preserve every donor and anchor's original marginal mass; they approximate independent pairing. Contributions are computational terms, not new observations or IDs.", "",
             "## Held-out development performance", "",
             "Lower comparison score is better. The score below is failure-penalised multiclass Brier. For complete forecasts it equals ordinary Brier; when synthetic positions are unresolved, ordinary Brier is not reported as though the physical distribution were complete. Brier is not a percentage accuracy.", "",
             _table(summary, ["horizon_days", "model", "eligible_pairs", "independent_ids", "brier_failure_penalized", "forecast_coverage", "zero_probability_pairs", "region90_hit_pct", "mean_region90_cells"]), "",
             "`forecast_coverage` means the fraction of eligible pairs receiving a complete probability distribution, not the fraction whose destination has nonzero probability. `region90_hit_pct` is the observed fraction inside the model's at-least-90% region; unavailable regions remain in the denominator. Mean region size is calculated only when the region exists, so read it with region availability in probability_region_summary.csv. Raw log losses remain infinite wherever an observed outcome receives zero probability.", "",
             "## Selected full-development candidate weights", "",
             _table(final_selections, ["family", "horizon_days", "method", "alpha_value", "tuning_brier"]), "",
             "These weights were selected using base out-of-fold predictions and the bases were then refitted on all development IDs. Their tuning scores are not independent assessments of the final refits. The main table assesses the corresponding nested selection procedure. Final-test trajectories remain locked.", "",
             "## Paired differences and practical interpretation", "",
             _table(intervals, ["horizon_days", "comparison", "delta_brier", "lower", "upper"]), "",
             "Negative differences favour the first model. The intervals use 200 paired whole-ID resamples within fixed outer folds. They condition on the saved fits and do not include training refits, weight-selection uncertainty, shared deployment conditions, or numerical integration uncertainty. These are exploratory comparisons, not multiplicity-adjusted confirmatory tests. An interval crossing zero does not establish a dependable improvement. A small score change alone does not establish practical value.", "",
             "## Implementation and scientific audit", "",
             f"- All nine models were scored on exactly the same source-multiplicity cases. Independent arithmetic reproduced {independent['score_rows_verified']:,} score rows; maximum difference {independent['maximum_score_difference']:.3g}.",
             f"- Independent calculations from saved inner models reproduced {selections_verified} weight selections, including the final candidate choices.",
             f"- Raw fitting pairs independently rebuilt {basis_audit['unaligned_bases_rebuilt']} unaligned local bases and representative aligned bases at both horizons. Saved score/weight artifacts were read back and verified. See fitted_basis_audit.json.",
             ("- Original B0/B1/B2 and both global controls reproduce the sealed pooled parent per case. Coordinate preparation reconciled the original pair counts, source keys and exact durations." if control_reference is None else "- Original B0/B1/B2 and both global controls independently reproduce the existing five-model procedure on this regime-specific population, including probability-region diagnostics. Source-keyed interval preparation checked exact pooled coordinates/endpoints before fixed-state qualification."),
             "- In every outer/inner fit, its held-out IDs supply no fitted donors or anchors. No canonical rows/features were changed; no final-test trajectories were opened. Geometry and target definitions are unchanged.",
             f"- Numerical status: **{numerical_status}**; {len(unsettled)} fit rows failed the declared successive-approximation stability criterion. See numerical_audit.csv and final_numerical_audit.csv.",
             "- Exact integration is used for small products. The large-product diagnostic compares the maximum possible blended score change across destinations and weights between successive balanced approximations. Passing it is stability evidence, not a certified bound on the unknown exact integral error.",
             "- Synthetic land/unmappable mass remains unresolved and is not deleted, resampled away, renamed grounding, or renormalised into ocean cells. Known domain exits and unresolved support remain distinct.", "",
             "## What the evidence can and cannot establish", "",
             "Use scores_by_cell.csv and scores_by_ID.csv to check whether gains are broad or dominated by a few origins/instruments. Read probability-region coverage with size: a broad region can achieve a high hit rate without useful concentration, while a narrow region can be overconfident. Hourly pairs are correlated; their large row count is not a large count of independent experiments.", "",
             "The aligned model assumes local transferability of net displacements and averages over subcell origins independently of those displacements. Neighbouring cells can lie on different flow branches or coastal components. Geometry checks do not demonstrate dynamical reachability. Complete-pair estimation conditions on observability. Neither variant includes season, origin velocity, wind, object leeway, or a validated grounding mechanism. The historical mixture cannot establish skill for every object or every release date.", "",
             "## Next checkpoint", "",
             "Review scores, numerical/support limitations and the combined fixed-regime report before the unified visualisation and short-lag Markov experiment. Status-only qualification does not establish homogeneous drogue depth. Fixed-regime intervals condition on persistence through the horizon and are not operational guarantees about future drogue loss. No annual, causal or object-specific accuracy is claimed here.", "",
             "## Reproduction", "",
             "Read provenance/run.json for the input run, code/input hashes, scenario, integration rule and fold digest. The matching runner is run_neighbourhood for pooled and run_regimes for fixed regimes (see --help). Reproduction creates a new immutable run; old evidence cannot be overwritten.", ""]
    paths.publish(run["results"]/"REPORT.md", lambda stream: stream.write("\n".join(lines).encode("utf-8")))
    return audit
