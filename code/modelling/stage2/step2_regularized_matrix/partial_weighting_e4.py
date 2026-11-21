"""E4 fixed power-weighted local estimates; unchanged E3 evaluation target."""
from dataclasses import dataclass
import hashlib
import numpy as np
import pandas as pd

from data3001.modelling.baselines.empirical_b2 import checked_ids
from data3001.modelling.common.qualified_count_inputs import ROW, KEYS, DEST, EXIT, HORIZONS
from data3001.modelling.common.prediction_regions import checked_distribution, probability_region
from data3001.modelling.baselines.drifter_shrinkage_e3 import (
    E3Bases, fit_bases as fit_equal, GRID, METRICS, TOL, UNIT, IDENTITY,
    summarize_units, select_parameters, diagnostic_scores, score_units,
    attach_primary_weights, metric_columns,
)

MODELS = ("B2", "PartialID", "EqualID", "Fixed")
BETA = {"B2": 0., "PartialID": .5, "EqualID": 1.}
BRIER_UPPER_QUANTILE = 1 - .05/6


@dataclass
class E4Bases(E3Bases):
    partial_rows: dict


def fit_bases(counts, training_ids, origins, destinations):
    base = fit_equal(counts, training_ids, origins, destinations)
    contributions = base.contributions.copy()
    contributions["partial_total_weight"] = np.sqrt(contributions.local_pair_count)
    contributions["partial_normalizer"] = contributions.groupby(ROW).partial_total_weight.transform("sum")
    contributions["partial_share"] = contributions.partial_total_weight / contributions.partial_normalizer
    contributions["raw_pair_weight"] = 1. / contributions.row_pair_count
    contributions["partial_pair_weight"] = 1. / (contributions.partial_total_weight*contributions.partial_normalizer)
    contributions["equal_pair_weight"] = 1. / (contributions.local_pair_count*contributions.row_id_count)
    local = base.local_distributions.merge(
        contributions[UNIT+["partial_share", "raw_pair_weight", "partial_pair_weight", "equal_pair_weight"]],
        on=UNIT, validate="many_to_one")
    local["partial_group_weight"] = local.pair_count*local.partial_pair_weight
    rows = {}
    for key, g in local.groupby(ROW, sort=True):
        p = np.zeros(len(base.states))
        for j, amount in g.groupby(DEST).partial_group_weight.sum().items():
            p[base.index[j]] = amount
        checked_distribution(p, base.states)
        if not np.array_equal(p > 0, base.rows[key] > 0):
            raise AssertionError("PartialID changed B2 support")
        rows[key] = p
    values = {**vars(base), "contributions": contributions, "local_distributions": local}
    return E4Bases(**values, partial_rows=rows)


def vector(base, h, origin, model, a=0.):
    if model not in MODELS or not np.isfinite(a) or not 0 <= a <= 1:
        raise ValueError("Invalid E4 model or Fixed weight")
    if (h, origin) not in base.rows:
        return None
    if model == "PartialID":
        return base.partial_rows[(h, origin)]
    if model == "EqualID":
        return base.equal_rows[(h, origin)]
    if model == "B2":
        return base.rows[(h, origin)]
    p = (1-a)*base.rows[(h, origin)] + a*base.references[h]
    checked_distribution(p, base.states)
    return p


def specifications():
    return [(m, 0.) for m in BETA] + [("Fixed", a) for a in GRID]


def forecasts(base, model, selected):
    params = selected.set_index("horizon_days").parameter_a if model == "Fixed" else None
    vectors, rows = {}, []
    for r in base.b2.support.itertuples(index=False):
        h, origin = r.horizon_days, r.origin_cell_1
        a = float(params.loc[h]) if params is not None else 0.
        p = vector(base, h, origin, model, a)
        rows.append({**r._asdict(), "model": model, "parameter_a": a,
                     "training_weighting": "local_pair_power_weight" if model in BETA else "raw_B2_and_raw_B1",
                     "training_beta": BETA.get(model, np.nan)})
        if p is not None:
            vectors[(h, origin)] = p
    return vectors, pd.DataFrame(rows)


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
        for model, reference in [("PartialID", r) for r in ("B2", "EqualID", "Fixed")]:
            change, upper = {}, None
            for m in METRICS:
                d = wide.xs(model, level="model")[m] - wide.xs(reference, level="model")[m]
                delta = float(points.loc[(h, model), m]-points.loc[(h, reference), m])
                change[m] = delta
                bound = float(d.quantile(BRIER_UPPER_QUANTILE)) if m == "brier" and model == "PartialID" else np.nan
                if m == "brier":
                    upper = bound
                differences.append(dict(horizon_days=h, model=model, reference=reference, metric=m,
                                        difference=delta, lower_95=d.quantile(.025), upper_95=d.quantile(.975),
                                        adjusted_upper=bound, defined_replicates=replicates))
            if model == "PartialID":
                b = change["brier"]
                outcome = ("no_measurable_Brier_gain" if b >= -TOL else
                           "conditional_development_Brier_support" if upper < -TOL else
                           "point_improvement_uncertain")
                decisions.append(dict(horizon_days=h, model=model, reference=reference, outcome=outcome,
                                      application_tradeoff=change["region90_cells"] > TOL or change["region90_hit"] < -TOL,
                                      joint_point_benefit=b < -TOL and change["region90_cells"] < -TOL and change["region90_hit"] >= -TOL,
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
        new = model_vectors["PartialID"][(h, origin)]
        selected = probability_region(new, base.states)[0]
        for reference in ("B2", "EqualID", "Fixed"):
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
