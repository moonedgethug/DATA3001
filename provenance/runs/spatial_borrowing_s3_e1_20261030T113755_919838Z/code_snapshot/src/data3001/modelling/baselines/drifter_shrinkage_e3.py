"""E3 v2: equal-ID conditional estimates and location-balanced evaluation."""
from dataclasses import dataclass
import hashlib

import numpy as np
import pandas as pd

from data3001.modelling.baselines.adaptive_b2_b1 import Bases, fit_bases as fit_raw, evaluate
from data3001.modelling.baselines.empirical_b2 import checked_ids
from data3001.modelling.common.qualified_count_inputs import ROW, KEYS, DEST, EXIT, HORIZONS
from data3001.modelling.common.prediction_regions import checked_distribution, probability_region

MODELS = ("B2", "EqualID", "Fixed")
GRID = tuple(k / 20 for k in range(21))
METRICS = ("brier", "region90_cells", "region90_hit")
TOL = 1e-12
UNIT = ["horizon_days", "origin_cell_1", "id"]
IDENTITY = ["horizon_days", "model", "parameter_a"]


@dataclass
class E3Bases(Bases):
    equal_rows: dict
    contributions: pd.DataFrame
    local_distributions: pd.DataFrame


def fit_bases(counts, training_ids, origins, destinations):
    raw = fit_raw(counts, training_ids, origins, destinations)
    local = counts[counts.id.isin(raw.b2.training_ids)].copy()
    local["local_pair_count"] = local.groupby(UNIT).pair_count.transform("sum")
    local["within_id_probability"] = local.pair_count / local.local_pair_count
    contributions = local[UNIT + ["local_pair_count"]].drop_duplicates().sort_values(UNIT)
    contributions["row_pair_count"] = contributions.groupby(ROW).local_pair_count.transform("sum")
    contributions["row_id_count"] = contributions.groupby(ROW).id.transform("size")
    contributions["raw_share"] = contributions.local_pair_count / contributions.row_pair_count
    contributions["equal_share"] = 1. / contributions.row_id_count
    local = local.merge(contributions[UNIT + ["equal_share"]], on=UNIT, validate="many_to_one")
    local["fitting_group_weight"] = local.within_id_probability * local.equal_share
    rows = {}
    for key, g in local.groupby(ROW, sort=True):
        p = np.zeros(len(raw.states))
        for j, amount in g.groupby(DEST).fitting_group_weight.sum().items():
            p[raw.index[j]] = amount
        checked_distribution(p, raw.states)
        if not np.array_equal(p > 0, raw.rows[key] > 0):
            raise AssertionError("EqualID changed B2 support")
        rows[key] = p
    return E3Bases(**vars(raw), equal_rows=rows,
                   contributions=contributions.reset_index(drop=True),
                   local_distributions=local.sort_values(KEYS).reset_index(drop=True))


def vector(base, h, origin, model, a=0.):
    if model not in MODELS or not np.isfinite(a) or not 0 <= a <= 1:
        raise ValueError("Invalid E3 model or Fixed weight")
    if (h, origin) not in base.rows:
        return None
    if model == "EqualID":
        return base.equal_rows[(h, origin)]
    if model == "B2":
        return base.rows[(h, origin)]
    p = (1-a)*base.rows[(h, origin)] + a*base.references[h]
    checked_distribution(p, base.states)
    return p


def forecasts(base, model, selected):
    params = selected.set_index("horizon_days").parameter_a if model == "Fixed" else None
    vectors, rows = {}, []
    for r in base.b2.support.itertuples(index=False):
        h, origin = r.horizon_days, r.origin_cell_1
        a = float(params.loc[h]) if params is not None else 0.
        p = vector(base, h, origin, model, a)
        rows.append({**r._asdict(), "model": model, "parameter_a": a,
                     "training_weighting": "equal_ID_within_cell" if model == "EqualID" else "equal_pairs"})
        if p is not None:
            vectors[(h, origin)] = p
    return vectors, pd.DataFrame(rows)


def specifications():
    return [("B2", 0.), ("EqualID", 0.), *[("Fixed", a) for a in GRID]]


def candidate_units(base, counts, evaluation_ids):
    """Keep ID-cell sufficient scores, so pooling folds preserves the target."""
    ids = checked_ids(evaluation_ids)
    if set(ids) & set(base.b2.training_ids):
        raise ValueError("Evaluation ID leakage")
    part = counts[counts.id.isin(ids)]
    result = []
    spec = specifications()
    for (h, origin), g in part.groupby(ROW, sort=True):
        ident = np.sort(g.id.unique())
        numbers = g.groupby("id").pair_count.sum().reindex(ident).to_numpy()
        common = dict(horizon_days=h, origin_cell_1=origin)
        if (h, origin) not in base.rows:
            for model, a in spec:
                result.append(pd.DataFrame({**common, "id": ident, "eligible_pairs": numbers,
                                            "model": model, "parameter_a": a, "supported": False,
                                            **{m: np.nan for m in METRICS}}))
            continue
        observed = np.zeros((len(ident), len(base.states)))
        lookup = {d: k for k, d in enumerate(ident)}
        for r in g.itertuples(index=False):
            observed[lookup[r.id], base.index[r.destination_cell_1]] = r.pair_count
        observed /= numbers[:, None]
        vectors = np.array([vector(base, h, origin, model, a) for model, a in spec])
        regions = np.array([probability_region(p, base.states)[0] for p in vectors])
        bs = 1 + np.square(vectors).sum(axis=1)[None, :] - 2*(observed @ vectors.T)
        hits = observed @ regions.T.astype(float)
        sizes = np.sum(regions & (base.states[None, :] >= 0), axis=1)
        for k, (model, a) in enumerate(spec):
            result.append(pd.DataFrame({**common, "id": ident, "eligible_pairs": numbers,
                                        "model": model, "parameter_a": a, "supported": True,
                                        "brier": bs[:, k], "region90_cells": sizes[k],
                                        "region90_hit": hits[:, k]}))
    if not result:
        raise ValueError("Empty evaluation role")
    return pd.concat(result, ignore_index=True)


def metric_columns(scores):
    names = [*METRICS, "region90_mass", "region90_exit_included", "positive_cells",
             "true_probability", "predicted_exit_probability", "observed_exit",
             "zero_true_probability", "squared_probability_sum", "seen_D_probability",
             "unseen_D_probability", "true_seen_D", "true_unseen_D", "D_region_hit"]
    return [m for m in names if m in scores] + sorted(c for c in scores if c.startswith("hit_k_"))


def summarize_units(units, group_columns=("horizon_days", "model"), metrics=METRICS, pair_weighted=False):
    """For conditional diagnostics, average numerator/mass with the same base weights."""
    output = []
    for key, g in units.groupby(list(group_columns), sort=True):
        key = key if isinstance(key, tuple) else (key,)
        if g.duplicated(UNIT).any():
            raise ValueError("Duplicate ID-cell unit: pool distinct validation groups before aggregation")
        row = dict(zip(group_columns, key))
        good = g[g.supported]
        membership = g.groupby("origin_cell_1").supported.agg(["size", "sum"])
        row.update(eligible_pairs=int(g.eligible_pairs.sum()), evaluable_pairs=int(good.eligible_pairs.sum()),
                   eligible_ids=int(g.id.nunique()), evaluable_ids=int(good.id.nunique()),
                   eligible_id_cells=len(g), evaluable_id_cells=len(good),
                   eligible_cells=len(membership), evaluable_cells=int(good.origin_cell_1.nunique()),
                   unsupported_pairs=int(g.loc[~g.supported, "eligible_pairs"].sum()),
                   unsupported_ids=int(g.loc[~g.supported, "id"].nunique()),
                   unsupported_id_cells=int((~g.supported).sum()),
                   target_availability=float((membership["sum"]/membership["size"]).mean()),
                   pair_availability=float(good.eligible_pairs.sum()/g.eligible_pairs.sum()),
                   aggregation="equal_pairs_secondary" if pair_weighted else "equal_cell_equal_ID")
        if good.empty:
            row.update({m: np.nan for m in metrics})
            output.append(row)
            continue
        if pair_weighted:
            weights = good.eligible_pairs.to_numpy(float)
        else:
            per_cell = good.groupby("origin_cell_1").id.transform("size")
            weights = 1. / (good.origin_cell_1.nunique()*per_cell.to_numpy(float))
        for m in metrics:
            mass = good[m+"__mass"].to_numpy(float) if m+"__mass" in good else good[m].notna().to_numpy(float)
            numerator = good[m].fillna(0).to_numpy(float)
            den = float(weights @ mass)
            row[m] = float(weights @ numerator / den) if den > 0 else np.nan
            row[m+"__denominator"] = den
        output.append(row)
    return pd.DataFrame(output)


def select_parameters(units):
    pool = summarize_units(units, IDENTITY)
    if set(pool.horizon_days) != set(HORIZONS) or pool.brier.isna().any():
        raise ValueError("No supported validation population at a required horizon")
    pool["selected"] = False
    pool["within_tie"] = False
    chosen = []
    for h in HORIZONS:
        section = pool[pool.horizon_days.eq(h)]
        if any(section[f].nunique() != 1 for f in ("eligible_pairs", "evaluable_pairs", "evaluable_id_cells", "evaluable_cells")):
            raise ValueError("Candidate population mismatch")
        fixed = section[section.model.eq("Fixed")]
        if tuple(sorted(fixed.parameter_a)) != GRID:
            raise ValueError("Incomplete fixed grid")
        minimum = fixed.brier.min()
        tied = fixed[fixed.brier <= minimum + TOL]
        best = tied.sort_values("parameter_a").iloc[0]
        pool.loc[tied.index, "within_tie"] = True
        pool.loc[best.name, "selected"] = True
        row = best.to_dict()
        row.update(selected=True, within_tie=True, selection_status="new_target_Brier_minimum")
        chosen.append(row)
    return pd.DataFrame(chosen), pool


def diagnostic_scores(base, vectors, counts, ids, model):
    scores, boundaries = evaluate(base, vectors, counts, ids, model)
    fields = ["observed_exit", "zero_true_probability", "squared_probability_sum",
              "seen_D_probability", "unseen_D_probability", "true_seen_D", "true_unseen_D", "D_region_hit"]
    for field in fields:
        scores[field] = np.nan
    for (h, origin), idx in scores.groupby(ROW).groups.items():
        if (h, origin) not in vectors:
            continue
        p, b2 = vectors[(h, origin)], base.rows[(h, origin)]
        truth = scores.loc[idx, DEST]
        seen = (base.states >= 0) & (b2 > 0)
        unseen = (base.states >= 0) & (b2 == 0)
        scores.loc[idx, "observed_exit"] = truth.eq(EXIT).astype(float)
        scores.loc[idx, "zero_true_probability"] = scores.loc[idx, "true_probability"].eq(0).astype(float)
        scores.loc[idx, "squared_probability_sum"] = p @ p
        scores.loc[idx, "seen_D_probability"] = p[seen].sum()
        scores.loc[idx, "unseen_D_probability"] = p[unseen].sum()
        scores.loc[idx, "true_seen_D"] = truth.isin(base.states[seen]).astype(float)
        scores.loc[idx, "true_unseen_D"] = truth.isin(base.states[unseen]).astype(float)
        scores.loc[idx, "D_region_hit"] = scores.loc[idx, "region90_hit"].where(truth.ne(EXIT))
    return scores, boundaries


def score_units(scores):
    metrics = metric_columns(scores)
    group = ["model", *UNIT]
    if scores.duplicated(["model", *KEYS]).any():
        raise ValueError("Repeated held-out case")
    rows = []
    for key, g in scores.groupby(group, sort=True):
        if g.status.nunique() != 1 or ("role" in g and g.role.nunique() != 1):
            raise ValueError("One ID-cell has conflicting fits or support")
        n = int(g.pair_count.sum())
        row = dict(zip(group, key))
        row.update(eligible_pairs=n, supported=g.status.iloc[0] == "evaluable")
        for field in ("role", "outer_fold"):
            if field in g:
                row[field] = g[field].iloc[0]
        for m in metrics:
            row[m] = float(np.dot(g.pair_count, g[m].fillna(0))/n)
            row[m+"__mass"] = float(g.loc[g[m].notna(), "pair_count"].sum()/n)
        rows.append(row)
    return pd.DataFrame(rows)


def attach_primary_weights(scores):
    result = scores.copy()
    result["within_ID_pair_weight"] = 1/result.groupby(["model", *UNIT]).pair_count.transform("sum")
    result["primary_group_weight"] = 0.
    for (h, model), g in result.groupby(["horizon_days", "model"]):
        good = g[g.status.eq("evaluable")]
        if good.empty:
            continue
        numbers = good.groupby("origin_cell_1").id.nunique()
        result.loc[good.index, "primary_group_weight"] = (
            good.pair_count*good.within_ID_pair_weight /
            good.origin_cell_1.map(numbers)/len(numbers))
    return result


def uncertainty(units, development_ids, replicates=5000, seed=20261030):
    ids = checked_ids(development_ids)
    if not units.id.isin(ids).all() or replicates < 1:
        raise ValueError("Invalid resampling inventory")
    rng = np.random.Generator(np.random.PCG64(seed))
    multipliers = rng.exponential(1., size=(replicates, len(ids)))
    if not np.isfinite(multipliers).all() or not (multipliers > 0).all():
        raise ValueError("Nonpositive or nonfinite multiplier")
    lookup = {d: k for k, d in enumerate(ids)}
    draws = []
    for (h, model), g in units[units.supported].groupby(["horizon_days", "model"]):
        aggregate = np.zeros((replicates, len(METRICS)))
        cells = g.origin_cell_1.nunique()
        for origin, cell in g.groupby("origin_cell_1", sort=True):
            if cell.id.duplicated().any():
                raise ValueError("Repeated bootstrap ID-cell")
            weights = multipliers[:, [lookup[d] for d in cell.id]]
            aggregate += (weights @ cell[list(METRICS)].to_numpy(float))/weights.sum(axis=1)[:, None]/cells
        draws.append(pd.DataFrame({"horizon_days": h, "model": model, "replicate": np.arange(replicates),
                                   **{m: aggregate[:, k] for k, m in enumerate(METRICS)}}))
    draws = pd.concat(draws, ignore_index=True)
    intervals = []
    for (h, model), g in draws.groupby(["horizon_days", "model"]):
        for m in METRICS:
            intervals.append(dict(horizon_days=h, model=model, metric=m,
                                  lower_95=g[m].quantile(.025), upper_95=g[m].quantile(.975),
                                  defined_replicates=len(g), undefined_replicates=0))
    points = summarize_units(units).set_index(["horizon_days", "model"])
    differences, decisions = [], []
    for h in HORIZONS:
        wide = draws[draws.horizon_days.eq(h)].set_index(["replicate", "model"])
        for model, reference in [("EqualID", "B2"), ("EqualID", "Fixed"), ("Fixed", "B2")]:
            change, upper = {}, None
            for m in METRICS:
                d = wide.xs(model, level="model")[m] - wide.xs(reference, level="model")[m]
                delta = float(points.loc[(h, model), m]-points.loc[(h, reference), m])
                change[m] = delta
                bound = float(d.quantile(.9875)) if m == "brier" and model == "EqualID" else np.nan
                if m == "brier":
                    upper = bound
                differences.append(dict(horizon_days=h, model=model, reference=reference, metric=m,
                                        difference=delta, lower_95=d.quantile(.025), upper_95=d.quantile(.975),
                                        adjusted_upper=bound, defined_replicates=replicates))
            if model == "EqualID":
                b = change["brier"]
                outcome = ("no_measurable_Brier_gain" if b >= -TOL else
                           "conditional_development_Brier_support" if upper < -TOL else
                           "point_improvement_uncertain")
                decisions.append(dict(horizon_days=h, model=model, reference=reference, outcome=outcome,
                                      application_tradeoff=change["region90_cells"] > TOL or change["region90_hit"] < -TOL,
                                      **{"delta_"+m: v for m, v in change.items()}))
    metadata = dict(generator="NumPy Generator PCG64", distribution="Exp(1)", seed=seed,
                    shape=list(multipliers.shape),
                    sorted_development_ids=list(ids),
                    little_endian_float64_sha256=hashlib.sha256(multipliers.astype("<f8").tobytes()).hexdigest(),
                    fixed_cell_set=True, fixed_fits=True)
    return draws, pd.DataFrame(intervals), pd.DataFrame(differences), pd.DataFrame(decisions), metadata


def region_changes(base, model_vectors, counts, ids):
    rows = []
    for (h, origin), g in counts[counts.id.isin(ids)].groupby(ROW):
        if (h, origin) not in base.rows:
            continue
        new = model_vectors["EqualID"][(h, origin)]
        selected = probability_region(new, base.states)[0]
        for reference in ("B2", "Fixed"):
            old = probability_region(model_vectors[reference][(h, origin)], base.states)[0]
            for part, mask in (("added", selected & ~old), ("removed", old & ~selected)):
                for ident, cases in g.groupby("id"):
                    amount = cases.pair_count.to_numpy(float)
                    hit = mask[[base.index[j] for j in cases[DEST]]]
                    rows.append(dict(horizon_days=h, origin_cell_1=origin, id=ident,
                                     reference=reference, part=part, eligible_pairs=int(amount.sum()),
                                     supported=True, cells=int(np.sum(mask & (base.states >= 0))),
                                     hit=float(amount @ hit/amount.sum()), probability_mass=float(new[mask].sum()),
                                     exit_included=bool(mask[base.index[EXIT]])))
    return pd.DataFrame(rows)
