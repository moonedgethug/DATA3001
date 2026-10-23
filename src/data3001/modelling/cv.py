"""Whole-instrument nested CV for a fixed B2/B1 probability blend.

Each count represents an equal-weight eligible hourly endpoint pair. Counts
are aggregated only to avoid repeating identical arithmetic; they are never
treated as independent instruments for confidence intervals.
"""
import numpy as np
import pandas as pd

from data3001.modelling.blend import brier_terms, mix_forecasts, select_lambdas
from data3001.modelling.evaluate import score_distribution

KEYS = ["id", "horizon_days", "origin_cell_1", "destination_cell_1"]


def fit_baselines(counts, training_ids):
    """Fit empirical B1/B2 using precisely the supplied instrument IDs."""
    training_ids = {int(sid) for sid in training_ids}
    part = counts.loc[counts["id"].isin(training_ids)]
    if part.empty or not part["pair_count"].gt(0).all():
        raise ValueError("Fitting requires positive eligible counts.")
    if part["destination_cell_1"].eq(-1).any():
        raise ValueError("An ineligible sentinel cannot be a destination.")
    result = {"training_ids": training_ids, "B1": {}, "B2": {}}
    for kind, conditions in (("B1", ["horizon_days"]),
                              ("B2", ["horizon_days", "origin_cell_1"])):
        table = part.groupby(conditions + ["destination_cell_1"], as_index=False)["pair_count"].sum()
        for key, group in table.groupby(conditions):
            key = key if isinstance(key, tuple) else (key,)
            key = tuple(int(value) for value in key)
            p = dict(zip(group["destination_cell_1"].astype(int),
                         group["pair_count"] / group["pair_count"].sum()))
            score_distribution(p, -1)
            result[kind][key[0] if kind == "B1" else key] = p
    return result


def _heldout(counts, model, evaluation_ids):
    evaluation_ids = {int(sid) for sid in evaluation_ids}
    if evaluation_ids & model["training_ids"]:
        raise ValueError("Fitting instruments cannot be scored as held out.")
    return counts.loc[counts["id"].isin(evaluation_ids)].copy()


def coefficient_cases(counts, model, evaluation_ids):
    """Return per-case quadratic Brier terms on genuinely held-out IDs."""
    part = _heldout(counts, model, evaluation_ids)
    chunks = []
    for (h, origin), group in part.groupby(["horizon_days", "origin_cell_1"]):
        if int(h) not in model["B1"]:
            raise ValueError("No B1 support at a required horizon.")
        q = model["B2"].get((int(h), int(origin)), {})
        r = model["B1"][int(h)]
        # Sentinel -1 is not a physical outcome. Its terms omit the truth
        # contribution, which is then added for each actual destination.
        A, B0, C0 = brier_terms(q, r, -1, u2=0.0 if q else 1.0)
        group = group.copy()
        q_true = group["destination_cell_1"].map(q).fillna(0.0)
        r_true = group["destination_cell_1"].map(r).fillna(0.0)
        group["A"] = A
        group["B"] = B0 - 2.0 * (r_true - q_true)
        group["C"] = C0 - 2.0 * q_true
        chunks.append(group)
    if not chunks:
        raise ValueError("No eligible held-out pairs.")
    return pd.concat(chunks, ignore_index=True)


def probability_region(probabilities, unresolved=0.0, mass=0.9):
    """Rank physical outcomes; retain cutoff ties, never renormalize unknowns."""
    score_distribution(probabilities, -1, unresolved=unresolved)
    positive = {int(k): float(v) for k, v in probabilities.items() if v > 0}
    if sum(positive.values()) < mass - 1e-12:
        return {"states": set(), "mass": np.nan, "cells": 0, "available": False}
    values = sorted(positive.values(), reverse=True)
    cumulative = np.cumsum(values)
    cutoff = values[min(int(np.searchsorted(cumulative + 1e-12, mass)), len(values) - 1)]
    states = {k for k, v in positive.items() if v >= cutoff - 1e-12}
    return {"states": states, "mass": sum(positive[k] for k in states),
            "cells": sum(k >= 0 for k in states), "available": True}


def score_groups(counts, model, evaluation_ids, lambdas, *, outer_fold):
    """Score five forecasts on exactly the same grouped held-out cases."""
    part = _heldout(counts, model, evaluation_ids)
    chunks = []
    for (h, origin), group in part.groupby(["horizon_days", "origin_cell_1"]):
        h, origin = int(h), int(origin)
        b1 = model["B1"][h]
        b2 = model["B2"].get((h, origin), {})
        forecasts = {"B0": ({origin: 1.0}, 0.0, np.nan),
                     "B1": (b1, 0.0, np.nan),
                     "B2": (b2, 0.0 if b2 else 1.0, np.nan)}
        for name in ("Grid", "Analytic"):
            lam = float(lambdas[name][h])
            p, u = mix_forecasts(b2, b1, lam, u2=0.0 if b2 else 1.0)
            forecasts[name] = (p, u, lam)
        for name, (p, u, lam) in forecasts.items():
            frame = group.copy()
            frame["outer_fold"] = int(outer_fold)
            frame["model"] = name
            frame["lambda_value"] = lam
            blank = score_distribution(p, -1, unresolved=u)
            true_p = frame["destination_cell_1"].map(p).fillna(0.0).to_numpy()
            frame["complete"] = blank["complete"]
            frame["true_probability"] = true_p
            frame["unresolved_mass"] = u
            frame["brier_failure_penalized"] = blank["brier_failure_penalized"] - 2 * true_p
            frame["brier"] = blank["brier"] - 2 * true_p
            with np.errstate(divide="ignore"):
                upper = -np.log(true_p)
                lower = -np.log(true_p + u)
            frame["log_loss"] = upper if u == 0.0 else np.nan
            frame["log_loss_lower"] = lower
            frame["log_loss_upper"] = upper
            region = probability_region(p, u)
            frame["region90_available"] = region["available"]
            frame["region90_hit"] = frame["destination_cell_1"].isin(region["states"])
            frame["region90_mass"] = region["mass"]
            frame["region90_cells"] = region["cells"]
            maximum = max(p.values(), default=0.0)
            top = min((k for k, v in p.items() if abs(v - maximum) <= 1e-12), default=-1) if maximum > 0 else -1
            frame["top_cell_hit"] = frame["destination_cell_1"].eq(top)
            frame["outside_probability"] = p.get(-2, 0.0)
            chunks.append(frame)
    return pd.concat(chunks, ignore_index=True)


def serializable_model(model):
    return {"B1": {str(h): {str(k): float(v) for k, v in p.items()}
                    for h, p in model["B1"].items()},
            "B2": {f"{h}:{o}": {str(k): float(v) for k, v in p.items()}
                    for (h, o), p in model["B2"].items()}}


def evaluate_nested(counts, outer, inner, progress=print):
    """Select inside each outer training pool; score IDs only out of fold."""
    if not set(counts["id"].astype(int)).issubset(outer):
        raise ValueError("An eligible instrument has no frozen outer assignment.")
    scores, selections, grids, terms, supports = [], [], [], [], []
    models = {}
    for fold in sorted(set(outer.values())):
        heldout = {sid for sid, f in outer.items() if f == fold}
        fitting = set(outer) - heldout
        if set(inner[fold]) != fitting:
            raise ValueError("Inner membership differs from outer training pool.")
        inner_cases = []
        for inner_fold in sorted(set(inner[fold].values())):
            tuning = {sid for sid, f in inner[fold].items() if f == inner_fold}
            model = fit_baselines(counts, fitting - tuning)
            inner_cases.append(coefficient_cases(counts, model, tuning))
        inner_cases = pd.concat(inner_cases, ignore_index=True)
        lambdas = {"Grid": {}, "Analytic": {}}
        for h, group in inner_cases.groupby("horizon_days"):
            choice = select_lambdas(group[["A", "B", "C"]], group["pair_count"])
            for name, key in (("Grid", "grid"), ("Analytic", "analytic")):
                lambdas[name][int(h)] = choice[f"{key}_lambda"]
                selections.append({"outer_fold": fold, "horizon_days": int(h),
                                   "method": name, "lambda_value": choice[f"{key}_lambda"],
                                   "inner_brier": choice[f"{key}_brier"],
                                   "inner_pairs": int(group["pair_count"].sum()),
                                   "inner_independent_ids": int(group["id"].nunique())})
            grids.extend({"outer_fold": fold, "horizon_days": int(h),
                          "lambda_value": row["lambda"], "selection_brier": row["selection_brier"]}
                         for row in choice["grid_scores"])
        model = fit_baselines(counts, fitting)
        scores.append(score_groups(counts, model, heldout, lambdas, outer_fold=fold))
        base = coefficient_cases(counts, model, heldout)
        base["outer_fold"] = fold
        terms.append(base)
        models[str(fold)] = serializable_model(model)
        support = counts.loc[counts["id"].isin(fitting)].groupby(
            ["horizon_days", "origin_cell_1"], as_index=False).agg(
                pair_count=("pair_count", "sum"), independent_ids=("id", "nunique"))
        support["outer_fold"] = fold
        supports.append(support)
        progress(f"Outer fold {fold + 1}/5 scored; weights selected on inner OOF only.")
    return {"scores": pd.concat(scores, ignore_index=True),
            "lambda_selection": pd.DataFrame(selections), "lambda_grid_scores": pd.DataFrame(grids),
            "base_terms": pd.concat(terms, ignore_index=True), "outer_models": models,
            "training_support": pd.concat(supports, ignore_index=True)}


def summarize_scores(scores, *, by_fold=False):
    keys = (["outer_fold"] if by_fold else []) + ["horizon_days", "model"]
    rows = []
    for key, g in scores.groupby(keys):
        row = dict(zip(keys, key))
        w = g["pair_count"].to_numpy(dtype=float)
        def avg(column):
            return float(np.average(g[column].to_numpy(dtype=float), weights=w))
        available = g["region90_available"].to_numpy(dtype=bool)
        complete = g["complete"].to_numpy(dtype=bool)
        row.update(eligible_pairs=int(w.sum()), independent_ids=int(g["id"].nunique()),
                   forecast_coverage=float(w[complete].sum() / w.sum()),
                   unresolved_pairs=int(w[~complete].sum()),
                   zero_probability_pairs=int(w[g["true_probability"].eq(0)].sum()),
                   region90_hit_pct=100 * avg("region90_hit"),
                   region90_available_pct=100 * avg("region90_available"),
                   top_cell_hit_pct=100 * avg("top_cell_hit"))
        for name in ("brier", "log_loss"):
            row[name] = avg(name) if complete.all() else np.nan
        for name in ("brier_failure_penalized", "log_loss_lower", "log_loss_upper"):
            row[name] = avg(name)
        for name in ("region90_mass", "region90_cells"):
            row["mean_" + name] = float(np.average(g.loc[available, name], weights=w[available])) if available.any() else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_differences(scores, replicates=200, seed=20261004):
    """Paired ID bootstrap conditional on saved OOF fits; no refitting."""
    rows = []
    for h, group in scores.groupby("horizon_days"):
        g = group.assign(total_loss=group["pair_count"] * group["brier_failure_penalized"])
        ids = g.groupby(["outer_fold", "id", "model"], as_index=False).agg(
            total_loss=("total_loss", "sum"), pair_count=("pair_count", "sum"))
        losses = ids.pivot(index=["outer_fold", "id"], columns="model", values="total_loss")
        denom = ids.loc[ids["model"].eq("B2")].set_index(["outer_fold", "id"])["pair_count"].reindex(losses.index).to_numpy()
        rng = np.random.default_rng(seed + int(h))
        fold_indices = [np.flatnonzero(losses.index.get_level_values(0) == f)
                        for f in sorted(losses.index.get_level_values(0).unique())]
        draws = [np.concatenate([rng.choice(ix, len(ix), replace=True) for ix in fold_indices])
                 for _ in range(replicates)]
        for left, right in (("Grid", "B2"), ("Analytic", "B2"), ("Analytic", "Grid")):
            delta = (losses[left] - losses[right]).to_numpy()
            estimates = [delta[ix].sum() / denom[ix].sum() for ix in draws]
            lower, upper = np.quantile(estimates, [0.025, 0.975])
            rows.append({"horizon_days": int(h), "comparison": f"{left} - {right}",
                         "delta_brier": delta.sum() / denom.sum(), "lower": lower, "upper": upper,
                         "replicates": replicates,
                         "scope": "Paired ID bootstrap within fixed outer folds; conditional on saved OOF predictions; no refitting"})
    return pd.DataFrame(rows)
