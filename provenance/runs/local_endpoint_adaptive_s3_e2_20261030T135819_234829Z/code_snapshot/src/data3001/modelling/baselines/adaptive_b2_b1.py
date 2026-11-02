"""Count-based B1/B2 shrinkage and isolated, whole-ID parameter selection."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from data3001.modelling.baselines.empirical_b2 import checked_ids, fit_b2, summarise
from data3001.modelling.common.qualified_count_inputs import (
    EXIT, HORIZONS, KEYS, ROW, DEST, TOLERANCE,
)
from data3001.modelling.common.prediction_regions import (
    budgets, budget_inclusion, checked_distribution, probability_region,
)

GRID = tuple(k/20 for k in range(21))
MODELS = ("B2", "Fixed", "Adaptive")


@dataclass
class Bases:
    b2: object
    states: np.ndarray
    index: dict
    rows: dict
    references: dict
    medians: dict


def fit_bases(counts, training_ids, origins, destinations):
    b2 = fit_b2(counts, training_ids, origins, destinations)
    states = np.asarray(b2.destinations, dtype=np.int64)
    index = {int(c): i for i, c in enumerate(states)}
    rows, references, medians = {}, {}, {}
    for h in HORIZONS:
        part = b2.transitions.loc[b2.transitions.horizon_days.eq(h)]
        if part.empty:
            raise ValueError(f"No qualified fitting counts at horizon {h}")
        q = np.zeros(len(states))
        by_destination = part.groupby(DEST).pair_count.sum()
        for c, n in by_destination.items():
            q[index[int(c)]] = n / by_destination.sum()
        references[h] = q
        support = b2.support.loc[b2.support.horizon_days.eq(h) & b2.support.supported]
        medians[h] = float(support.training_pair_count.median())
        for origin, group in part.groupby("origin_cell_1"):
            p = np.zeros(len(states))
            for r in group.itertuples(index=False):
                p[index[r.destination_cell_1]] = r.probability
            rows[(h, int(origin))] = p
    return Bases(b2, states, index, rows, references, medians)


def borrowing_weight(family, a, n, median):
    if family not in MODELS or not np.isfinite([a, n, median]).all() or not 0 <= a <= 1:
        raise ValueError("Invalid family or parameter")
    if n <= 0 or median <= 0:
        raise ValueError("Borrowing requires a supported row and reference scale")
    if family == "B2" or a == 0:
        return 0.
    if family == "Fixed" or a == 1:
        return float(a)
    return float(median*a / ((1-a)*n + median*a))


def forecasts(base, family, selected):
    """Return only complete rows; the shared B2 support mask is never bypassed."""
    vectors, support_rows = {}, []
    for r in base.b2.support.itertuples(index=False):
        h, origin = r.horizon_days, r.origin_cell_1
        a = 0. if family == "B2" else float(selected[h])
        row = r._asdict()
        row.update(model=family, parameter_a=a, median_pair_count=base.medians[h],
                   borrowing_weight=np.nan)
        if r.supported:
            lam = borrowing_weight(family, a, r.training_pair_count, base.medians[h])
            p = (1-lam)*base.rows[(h, origin)] + lam*base.references[h]
            checked_distribution(p, base.states)
            vectors[(h, origin)] = p
            row["borrowing_weight"] = lam
        support_rows.append(row)
    return vectors, pd.DataFrame(support_rows)


def coefficient_rows(base, counts, evaluation_ids):
    ids = checked_ids(evaluation_ids)
    if set(ids) & set(base.b2.training_ids):
        raise ValueError("Evaluation IDs occur in the fit")
    part = counts.loc[counts.id.isin(ids)]
    rows = []
    support = base.b2.support.set_index(ROW)
    for (h, origin), group in part.groupby(ROW):
        weight = group.pair_count.to_numpy(float)
        row = {"horizon_days": int(h), "origin_cell_1": int(origin),
               "eligible_pairs": int(weight.sum()), "eligible_ids": group.id.nunique(),
               "median_pair_count": base.medians[h],
               "training_pair_count": int(support.loc[(h, origin), "training_pair_count"]),
               "evaluable_pairs": 0, "A": 0., "B": 0., "C": 0.}
        if (h, origin) in base.rows:
            p, q = base.rows[(h, origin)], base.references[h]
            delta = q-p
            y = np.array([base.index[c] for c in group[DEST]], dtype=int)
            row.update(evaluable_pairs=int(weight.sum()),
                       A=float(weight.sum()*(delta @ delta)),
                       B=float(np.dot(weight, 2*(p @ delta) - 2*delta[y])),
                       C=float(np.dot(weight, 1 + p @ p - 2*p[y])))
        rows.append(row)
    return pd.DataFrame(rows)


def candidate_scores(terms):
    rows = []
    for h, group in terms.groupby("horizon_days"):
        valid = group.loc[group.evaluable_pairs.gt(0)]
        for family in ("Fixed", "Adaptive"):
            for a in GRID:
                lam = np.array([borrowing_weight(family, a, r.training_pair_count,
                                                 r.median_pair_count)
                                for r in valid.itertuples(index=False)])
                total = float(np.sum(valid.A.to_numpy()*lam**2 + valid.B.to_numpy()*lam
                                     + valid.C.to_numpy()))
                rows.append({"horizon_days": int(h), "model": family, "parameter_a": a,
                             "score_sum": total, "eligible_pairs": int(group.eligible_pairs.sum()),
                             "evaluable_pairs": int(valid.evaluable_pairs.sum())})
    return pd.DataFrame(rows)


def select_parameters(candidates):
    pooled = candidates.groupby(["horizon_days", "model", "parameter_a"], as_index=False)[
        ["score_sum", "eligible_pairs", "evaluable_pairs"]].sum()
    pooled["selection_brier"] = pooled.score_sum / pooled.evaluable_pairs
    selected = []
    for (h, model), group in pooled.groupby(["horizon_days", "model"]):
        if not group.evaluable_pairs.gt(0).all() or group.evaluable_pairs.nunique() != 1:
            raise ValueError("Selection candidates lack a common evaluable population")
        minimum = float(group.selection_brier.min())
        row = group.loc[group.selection_brier.le(minimum + TOLERANCE)].sort_values("parameter_a").iloc[0]
        selected.append(row.to_dict())
    return pd.DataFrame(selected), pooled


def evaluate(base, vectors, counts, evaluation_ids, family):
    ids = checked_ids(evaluation_ids)
    if set(ids) & set(base.b2.training_ids):
        raise ValueError("Held-out IDs leaked into fitted bases")
    part = counts.loc[counts.id.isin(ids)].copy().sort_values(KEYS).reset_index(drop=True)
    k_values = budgets(int(np.sum(base.states >= 0)))
    result, budget_rows = [], []
    for (h, origin), group in part.groupby(ROW, sort=True):
        p = vectors.get((h, origin))
        region, region_meta, inclusions = None, {}, {}
        if p is not None:
            region, region_meta = probability_region(p, base.states)
            for k in k_values:
                inc, meta = budget_inclusion(p, base.states, k)
                inclusions[k] = inc
                budget_rows.append({"model": family, "horizon_days": h,
                                    "origin_cell_1": origin, **meta})
        for r in group.itertuples(index=False):
            row = r._asdict()
            row.update(model=family, status="unsupported_origin", brier=np.nan,
                       true_probability=np.nan, predicted_exit_probability=np.nan,
                       unresolved_mass=1., region90_hit=np.nan, region90_cells=np.nan,
                       region90_mass=np.nan, region90_exit_included=np.nan,
                       region90_cutoff=np.nan, positive_cells=np.nan,
                       **{f"hit_k_{k}": np.nan for k in k_values})
            if p is not None:
                y = base.index[r.destination_cell_1]
                row.update(status="evaluable", unresolved_mass=0.,
                           true_probability=float(p[y]), brier=float(1 + p @ p - 2*p[y]),
                           predicted_exit_probability=float(p[base.index[EXIT]]),
                           region90_hit=float(region[y]),
                           positive_cells=int(np.sum((base.states >= 0) & (p > 0))), **region_meta)
                if r.destination_cell_1 != EXIT:
                    row.update({f"hit_k_{k}": float(inclusions[k][y]) for k in k_values})
            result.append(row)
    return pd.DataFrame(result), pd.DataFrame(budget_rows)


def diagnostic_metrics(scores):
    return ["brier", "region90_cells", "region90_hit", "region90_mass",
            "region90_exit_included", "positive_cells", *sorted(c for c in scores if c.startswith("hit_k_"))]


def summarize_scores(scores, group_columns=("horizon_days", "model")):
    summary = summarise(scores, list(group_columns))
    extra = []
    for key, g in scores.groupby(list(group_columns), sort=True):
        key = key if isinstance(key, tuple) else (key,)
        row = dict(zip(group_columns, key))
        for metric in diagnostic_metrics(scores):
            if metric == "brier":
                continue
            valid = g[metric].notna()
            n = int(g.loc[valid, "pair_count"].sum())
            row[metric] = float(np.dot(g.loc[valid, metric].astype(float), g.loc[valid, "pair_count"])/n) if n else np.nan
        row["budget_evaluable_pairs"] = int(g.loc[g.status.eq("evaluable") & g[DEST].ne(EXIT), "pair_count"].sum())
        extra.append(row)
    return summary.merge(pd.DataFrame(extra), on=list(group_columns), validate="one_to_one")


def paired_bootstrap(scores, development_ids, replicates=200, seed=20261030):
    ids = checked_ids(development_ids)
    if not scores.id.isin(ids).all() or replicates < 1:
        raise ValueError("Invalid bootstrap population")
    rng = np.random.default_rng(seed)
    multiplicities = rng.multinomial(len(ids), np.full(len(ids), 1/len(ids)), size=replicates)
    metrics = diagnostic_metrics(scores)
    draws = []
    for (h, model), g in scores.groupby(["horizon_days", "model"]):
        arrays = []
        for metric in metrics:
            valid = g[metric].notna()
            temp = pd.DataFrame({"id": g.id, "den": g.pair_count.where(valid, 0),
                                 "num": g[metric].fillna(0).astype(float)*g.pair_count})
            grouped = temp.groupby("id")[["num", "den"]].sum().reindex(ids, fill_value=0)
            sampled = multiplicities @ grouped.to_numpy(float)
            values = np.divide(sampled[:, 0], sampled[:, 1], out=np.full(replicates, np.nan), where=sampled[:, 1]>0)
            arrays.append(values)
        for i in range(replicates):
            draws.append({"horizon_days": h, "model": model, "replicate": i,
                          **{m: float(v[i]) for m, v in zip(metrics, arrays)}})
    draws = pd.DataFrame(draws)
    intervals, differences = [], []
    for (h, model), g in draws.groupby(["horizon_days", "model"]):
        for metric in metrics:
            values = g[metric].dropna()
            intervals.append({"horizon_days": h, "model": model, "metric": metric,
                              "lower_95": values.quantile(.025), "upper_95": values.quantile(.975),
                              "defined_replicates": len(values), "undefined_replicates": replicates-len(values)})
    points = summarize_scores(scores).set_index(["horizon_days", "model"])
    for h in HORIZONS:
        wide = draws.loc[draws.horizon_days.eq(h)].set_index(["replicate", "model"])
        for control in ("Fixed", "B2"):
            for metric in metrics:
                delta = (wide.xs("Adaptive", level="model")[metric] - wide.xs(control, level="model")[metric]).dropna()
                differences.append({"horizon_days": h, "comparison": f"Adaptive - {control}", "metric": metric,
                                    "difference": float(points.loc[(h, "Adaptive"), metric]-points.loc[(h, control), metric]),
                                    "lower_95": delta.quantile(.025), "upper_95": delta.quantile(.975),
                                    "defined_replicates": len(delta), "undefined_replicates": replicates-len(delta)})
    return draws, pd.DataFrame(intervals), pd.DataFrame(differences)
