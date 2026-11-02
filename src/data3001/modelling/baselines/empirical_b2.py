"""Standard empirical B2 and Brier evaluation; no smoothing or legacy runners."""
from dataclasses import dataclass
from itertools import product
from numbers import Integral

import numpy as np
import pandas as pd

from data3001.modelling.common.qualified_count_inputs import (
    KEYS, ROW, DEST, HORIZONS, EXIT, TOLERANCE, validate_counts,
)


def checked_ids(values):
    values = list(values)
    if (not values or any(isinstance(x, bool) or not isinstance(x, Integral) or x <= 0
                          for x in values) or len(set(values)) != len(values)):
        raise ValueError("IDs must be nonempty, unique positive integers")
    return tuple(sorted(int(x) for x in values))



def standard_brier(probabilities, truth):
    values = np.asarray(list(probabilities.values()), dtype=float)
    if (not np.isfinite(values).all() or (values < 0).any() or (values > 1).any()
            or not np.isclose(values.sum(), 1., atol=TOLERANCE, rtol=0)):
        raise ValueError("Standard Brier requires a complete probability distribution")
    return float(1 - 2 * probabilities.get(truth, 0.) + values @ values)


@dataclass
class EmpiricalB2:
    training_ids: tuple
    origins: tuple
    destinations: tuple
    transitions: pd.DataFrame
    support: pd.DataFrame


def fit_b2(counts, training_ids, origins, destinations):
    """Fit direct 7/30-day frequencies using exactly the supplied fitting IDs."""
    training_ids = checked_ids(training_ids)
    origins, destinations = tuple(sorted(origins)), tuple(sorted(destinations))
    if (not origins or len(set(origins)) != len(origins)
            or len(set(destinations)) != len(destinations) or EXIT not in destinations
            or not set(origins).issubset(destinations)
            or any(not isinstance(c, Integral) or c < 0 or c >= 64800 for c in origins)
            or any(not isinstance(c, Integral) or (c != EXIT and not 0 <= c < 64800)
                   for c in destinations)):
        raise ValueError("Invalid fixed source/destination indexes")
    validate_counts(counts, origins, destinations)
    part = counts.loc[counts.id.isin(training_ids)]
    transitions = part.groupby(ROW + [DEST], as_index=False, sort=True).pair_count.sum()
    transitions["probability"] = (transitions.pair_count
                                  / transitions.groupby(ROW).pair_count.transform("sum"))
    by_id = part.groupby(ROW + ["id"], as_index=False).pair_count.sum()
    groups = {tuple(k): g for k, g in by_id.groupby(ROW)}
    destination_counts = transitions.groupby(ROW).size().to_dict()
    rows = []
    for h, cell in product(HORIZONS, origins):
        group = groups.get((h, cell))
        total = int(group.pair_count.sum()) if group is not None else 0
        rows.append({"horizon_days": h, "origin_cell_1": cell,
                     "training_pair_count": total,
                     "training_id_count": len(group) if group is not None else 0,
                     "largest_id_share": float(group.pair_count.max() / total) if total else np.nan,
                     "observed_destination_count": int(destination_counts.get((h, cell), 0)),
                     "supported": total > 0, "unresolved_mass": 0. if total else 1.})
    support = pd.DataFrame(rows)
    sums = transitions.groupby(ROW).probability.sum()
    for row in support.itertuples(index=False):
        mass = float(sums.get((row.horizon_days, row.origin_cell_1), 0.))
        if not np.isclose(mass + row.unresolved_mass, 1., atol=TOLERANCE, rtol=0):
            raise ValueError("Empirical row mass is not conserved")
    return EmpiricalB2(training_ids, origins, destinations, transitions, support)


def evaluate_b2(model, counts, evaluation_ids):
    """Return grouped held-out cases; pair_count is the exact case multiplicity."""
    evaluation_ids = checked_ids(evaluation_ids)
    if set(evaluation_ids) & set(model.training_ids):
        raise ValueError("Fitting and evaluation IDs overlap")
    validate_counts(counts, model.origins, model.destinations)
    part = counts.loc[counts.id.isin(evaluation_ids)].copy()
    distributions = {tuple(k): dict(zip(g[DEST], g.probability))
                     for k, g in model.transitions.groupby(ROW)}
    chunks = []
    for key, group in part.groupby(ROW, sort=True):
        group = group.copy()
        p = distributions.get(tuple(key))
        if p is None:
            group["status"] = "unsupported_origin"
            group["brier"] = np.nan
            group["true_probability"] = np.nan
            group["predicted_exit_probability"] = np.nan
            group["unresolved_mass"] = 1.
        else:
            standard_brier(p, EXIT)  # Validate the entire row, including zero true mass.
            group["status"] = "evaluable"
            group["true_probability"] = group[DEST].map(p).fillna(0.)
            group["brier"] = 1 - 2 * group.true_probability + sum(v*v for v in p.values())
            group["predicted_exit_probability"] = p.get(EXIT, 0.)
            group["unresolved_mass"] = 0.
        chunks.append(group)
    if not chunks:
        return pd.DataFrame(columns=KEYS + ["pair_count", "status", "brier", "true_probability",
                                         "predicted_exit_probability", "unresolved_mass"])
    return pd.concat(chunks, ignore_index=True).sort_values(KEYS).reset_index(drop=True)


def summarise(scores, group_columns=("horizon_days",)):
    rows = []
    for key, group in scores.groupby(list(group_columns), sort=True):
        key = key if isinstance(key, tuple) else (key,)
        valid = group.status.eq("evaluable")
        eligible = int(group.pair_count.sum())
        good = group.loc[valid]
        n = int(good.pair_count.sum())
        zero = int(good.loc[good.true_probability.eq(0), "pair_count"].sum())
        observed_exit = int(group.loc[group[DEST].eq(EXIT), "pair_count"].sum())
        rows.append({**dict(zip(group_columns, key)), "eligible_pairs": eligible,
                     "eligible_ids": group.id.nunique(), "evaluable_pairs": n,
                     "evaluable_ids": good.id.nunique(), "unsupported_pairs": eligible - n,
                     "unsupported_ids": group.loc[~valid, "id"].nunique(),
                     "availability": n / eligible, "unsupported_fraction": 1 - n / eligible,
                     "brier": float((good.brier * good.pair_count).sum() / n) if n else np.nan,
                     "zero_true_probability_pairs": zero,
                     "zero_true_probability_fraction": zero / n if n else np.nan,
                     "observed_exit_pairs": observed_exit,
                     "observed_exit_fraction": observed_exit / eligible,
                     "observed_exit_fraction_evaluable": float(good.loc[good[DEST].eq(EXIT), "pair_count"].sum() / n) if n else np.nan,
                     "mean_predicted_exit_probability": float((good.predicted_exit_probability * good.pair_count).sum() / n) if n else np.nan})
    return pd.DataFrame(rows)


def bootstrap_scores(scores, development_ids, replicates=200, seed=20261029):
    """Resample whole development IDs; fitted forecasts are held fixed."""
    ids = checked_ids(development_ids)
    if replicates < 1 or not scores.id.isin(ids).all():
        raise ValueError("Invalid bootstrap population or replicate count")
    rng = np.random.default_rng(seed)
    multiplicities = rng.multinomial(len(ids), np.full(len(ids), 1 / len(ids)), size=replicates)
    rows = []
    for h in HORIZONS:
        part = scores.loc[scores.horizon_days.eq(h)].copy()
        part["evaluable_weight"] = part.pair_count.where(part.status.eq("evaluable"), 0)
        part["weighted_brier"] = part.brier.fillna(0.) * part.evaluable_weight
        totals = part.groupby("id")[["pair_count", "evaluable_weight", "weighted_brier"]].sum()
        totals = totals.reindex(ids, fill_value=0).to_numpy(dtype=float)
        sampled = multiplicities @ totals
        for r, (total, valid, score_sum) in enumerate(sampled):
            rows.append({"replicate": r, "horizon_days": h,
                         "eligible_pairs": int(total), "evaluable_pairs": int(valid),
                         "availability": valid / total if total else np.nan,
                         "brier": score_sum / valid if valid else np.nan})
    draws = pd.DataFrame(rows)
    intervals = []
    for h, part in draws.groupby("horizon_days"):
        for metric in ("brier", "availability"):
            values = part[metric].dropna()
            intervals.append({"horizon_days": h, "metric": metric,
                              "lower_95": float(values.quantile(.025)) if len(values) else np.nan,
                              "upper_95": float(values.quantile(.975)) if len(values) else np.nan,
                              "defined_replicates": len(values), "undefined_replicates": replicates-len(values)})
    return draws, pd.DataFrame(intervals)
