"""Whole-ID nested development evaluation of two local-sharing hypotheses."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
from numbers import Integral
from threading import local

import numpy as np
import pandas as pd

from data3001.modelling.baselines.blend import brier_terms, mix_forecasts, select_lambdas
from data3001.modelling.baselines.cv import KEYS, fit_baselines, probability_region
from data3001.modelling.common.probability import score_distribution
from data3001.modelling.baselines.neighbourhood import aligned_distribution, neighbour_cells, net_displacements, unaligned_distribution

FAMILIES = ("Global", "Local-U", "Local-A")
MODEL_NAMES = ("B0", "B1", "B2") + tuple(
    f"{family}-{method}" for family in FAMILIES for method in ("Grid", "Analytic"))


def pair_counts(pairs):
    return pairs.groupby(KEYS, as_index=False).size().rename(columns={"size": "pair_count"})


def fit_local_bases(pairs, training_ids, target_cells, mapper, *, fit_tag,
                    integration=None, progress=lambda s: None, workers=4):
    """Fit ALL components, including the anchor prior, from fitting IDs only."""
    ids = {int(sid) for sid in training_ids}
    if isinstance(workers, bool) or not isinstance(workers, Integral) or workers < 1:
        raise ValueError("A positive integer numeric-worker count is required.")
    part = pairs.loc[pairs.id.isin(ids)].copy()
    if part.empty:
        raise ValueError("No fitting pairs.")
    az, dist = net_displacements(part)
    part["displacement_azimuth"], part["net_distance_m"] = az, dist
    model = fit_baselines(pair_counts(part), ids)
    model.update({"Local-U": {}, "Local-A": {}, "support": [], "numerical_audit": []})
    groups = {tuple(map(int, key)): g for key, g in part.groupby(["horizon_days", "origin_cell_1"])}
    empty = part.iloc[:0]
    id_hash = hashlib.sha256(",".join(map(str, sorted(ids))).encode("ascii")).hexdigest()
    for h in sorted(part.horizon_days.unique()):
        horizon_points = 0
        worker_state = local()

        def initialise_worker():
            worker_state.mapper = mapper.worker_copy()

        def fit_row(origin):
            # Build frames inside the worker, limiting live large donor frames
            # to the worker count. No worker mutates shared frames/geometries.
            key = int(h), int(origin)
            own = groups.get(key, empty)
            neighbours = [groups[(int(h), k)] for k in neighbour_cells(int(origin))
                          if (int(h), k) in groups]
            donors = pd.concat(neighbours, ignore_index=True) if neighbours else empty
            unaligned = unaligned_distribution(donors)
            anchors = own[["origin_lon", "origin_lat"]].to_numpy(float)
            seed = int.from_bytes(hashlib.sha256(
                f"20261004:local-integral:{id_hash}:{h}:{origin}".encode("ascii")
            ).digest()[:8], "big")
            base = model["B2"].get(key, {})
            p, u, audit = aligned_distribution(donors, anchors, worker_state.mapper, seed=seed,
                                              base=(base, 0. if base else 1.),
                                              **(integration or {}))
            audit.update(fit_tag=fit_tag, horizon_days=int(h), origin_cell_1=int(origin),
                         fitting_ids_sha256=id_hash, aligned_unresolved_mass=u,
                         aligned_outside_mass=p.get(-2, 0.))
            support = {
                "fit_tag": fit_tag, "horizon_days": int(h), "origin_cell_1": int(origin),
                "origin_pairs": len(own), "origin_independent_ids": own.id.nunique(),
                "donor_pairs": len(donors), "donor_independent_ids_union": donors.id.nunique(),
                "available_neighbour_cells": len(neighbours),
                "origin_dominant_id_share": float(own.id.value_counts().max()/len(own)) if len(own) else np.nan,
                "donor_dominant_id_share": float(donors.id.value_counts().max()/len(donors)) if len(donors) else np.nan,
            }
            return key, unaligned, (p, u), audit, support

        with ThreadPoolExecutor(max_workers=int(workers), initializer=initialise_worker) as executor:
            # map yields in sorted order, so scheduling cannot change sums,
            # seeds, model keys, support rows, or audit row order.
            for row_number, (key, unaligned, aligned, audit, support) in enumerate(
                    executor.map(fit_row, sorted(target_cells)), 1):
                model["Local-U"][key], model["Local-A"][key] = unaligned, aligned
                model["numerical_audit"].append(audit)
                model["support"].append(support)
                horizon_points += audit["integration_points"]
                if row_number % 8 == 0:
                    progress(f"{fit_tag}: {int(h)}d {row_number}/{len(target_cells)} rows; "
                             f"last cell {key[1]}, donors={audit['donor_pairs']}, anchors={audit['anchors']}, "
                             f"couplings={audit['couplings']}, stable={audit['converged']}")
        selected = [a for a in model["numerical_audit"] if a["horizon_days"] == h]
        progress(f"{fit_tag}: {int(h)}d local rows fitted; {horizon_points:,} integration contributions; "
                 f"numerically unsettled rows={sum(not a['converged'] for a in selected)}")
    return model


def forecast(model, name, horizon, origin, alpha=np.nan):
    h, i = int(horizon), int(origin)
    if name == "B0":
        return {i: 1.}, 0.
    if name == "B1":
        p = model["B1"].get(h, {})
        return p, 0. if p else 1.
    q = model["B2"].get((h, i), {})
    uq = 0. if q else 1.
    if name == "B2":
        return q, uq
    family = name.rsplit("-", 1)[0]
    if family == "Global":
        p = model["B1"].get(h, {})
        r, ur = p, 0. if p else 1.
    elif family in ("Local-U", "Local-A"):
        r, ur = model[family].get((h, i), ({}, 1.))
    else:
        raise ValueError("Unknown model family.")
    if alpha == 0.:
        return q, uq
    if alpha == 1.:
        return r, ur
    return mix_forecasts(q, r, alpha, u2=uq, u1=ur)


def _heldout(counts, model, ids):
    if set(ids) & model["training_ids"]:
        raise ValueError("Fitting IDs cannot be used as held out.")
    return counts.loc[counts.id.isin(ids)].copy()


def coefficient_cases(counts, model, evaluation_ids, family):
    chunks = []
    for (h, origin), group in _heldout(counts, model, evaluation_ids).groupby(
            ["horizon_days", "origin_cell_1"]):
        q, uq = forecast(model, "B2", h, origin)
        r, ur = forecast(model, family+"-Grid", h, origin, 1.)
        A, B0, C0 = brier_terms(q, r, -999, u2=uq, u1=ur)
        g = group.copy()
        qt = g.destination_cell_1.map(q).fillna(0.)
        rt = g.destination_cell_1.map(r).fillna(0.)
        g["A"], g["B"], g["C"] = A, B0-2*(rt-qt), C0-2*qt
        g["family"] = family
        chunks.append(g)
    if not chunks:
        raise ValueError("No eligible held-out cases.")
    return pd.concat(chunks, ignore_index=True)


def score_model_groups(counts, model, evaluation_ids, selected, outer_fold):
    chunks = []
    for (h, origin), group in _heldout(counts, model, evaluation_ids).groupby(
            ["horizon_days", "origin_cell_1"]):
        for name in MODEL_NAMES:
            alpha = selected.get((name, int(h)), np.nan)
            p, u = forecast(model, name, h, origin, alpha)
            g = group.copy()
            g["model"], g["outer_fold"], g["alpha_value"] = name, outer_fold, alpha
            blank = score_distribution(p, -999, u)
            truth_p = g.destination_cell_1.map(p).fillna(0.).to_numpy()
            g["true_probability"], g["unresolved_mass"], g["complete"] = truth_p, u, u == 0.
            g["brier_failure_penalized"] = blank["brier_failure_penalized"] - 2*truth_p
            g["brier"] = blank["brier"] - 2*truth_p
            with np.errstate(divide="ignore"):
                upper, lower = -np.log(truth_p), -np.log(truth_p+u)
            g["log_loss"], g["log_loss_lower"], g["log_loss_upper"] = upper if u == 0 else np.nan, lower, upper
            for mass in (.5, .8, .9, .95):
                level = int(round(mass*100))
                region = probability_region(p, u, mass)
                g[f"region{level}_available"] = region["available"]
                g[f"region{level}_hit"] = g.destination_cell_1.isin(region["states"])
                g[f"region{level}_mass"] = region["mass"]
                g[f"region{level}_cells"] = region["cells"]
            maximum = max(p.values(), default=0.)
            top = min((k for k, v in p.items() if abs(v-maximum) <= 1e-12), default=-1) if maximum > 0 else -1
            g["top_cell_hit"] = g.destination_cell_1.eq(top)
            g["outside_probability"] = p.get(-2, 0.)
            chunks.append(g)
    return pd.concat(chunks, ignore_index=True)


def evaluate_local_nested(pairs, outer, inner, target_cells, mapper, *, integration=None,
                          progress=print, fit_callback=None):
    """Select global/local weights ONLY on inner OOF; score same outer cases."""
    counts = pair_counts(pairs)
    if set(pairs.id.unique()) - set(outer):
        raise ValueError("Pair IDs missing from the frozen outer assignment.")
    scores, selection, grids, terms, support, audits, curves = [], [], [], [], [], [], []
    models = {}

    def fit(ids, tag):
        model = fit_local_bases(pairs, ids, target_cells, mapper, fit_tag=tag,
                                integration=integration, progress=progress)
        support.extend(model["support"])
        audits.extend(model["numerical_audit"])
        if fit_callback:
            fit_callback(tag, model)
        return model

    for fold in sorted(set(outer.values())):
        heldout = {sid for sid, f in outer.items() if f == fold}
        fitting = set(outer) - heldout
        if set(inner[fold]) != fitting:
            raise ValueError("Inner membership must equal outer fitting membership.")
        inner_cases = {family: [] for family in FAMILIES}
        for k in sorted(set(inner[fold].values())):
            tuning = {sid for sid, f in inner[fold].items() if f == k}
            model = fit(fitting-tuning, f"outer{fold}_inner{k}")
            for family in FAMILIES:
                inner_cases[family].append(coefficient_cases(counts, model, tuning, family))
        selected = {}
        for family, frames in inner_cases.items():
            cases = pd.concat(frames, ignore_index=True)
            for h, g in cases.groupby("horizon_days"):
                choice = select_lambdas(g[["A", "B", "C"]], g.pair_count)
                for method in ("Grid", "Analytic"):
                    alpha = choice[method.lower()+"_lambda"]
                    selected[(family+"-"+method, int(h))] = alpha
                    selection.append({"outer_fold": fold, "horizon_days": int(h), "family": family,
                                      "method": method, "alpha_value": alpha,
                                      "inner_brier": choice[method.lower()+"_brier"],
                                      "inner_pairs": int(g.pair_count.sum()),
                                      "inner_independent_ids": g.id.nunique()})
                grids.extend({"outer_fold": fold, "horizon_days": int(h), "family": family,
                              "alpha_value": r["lambda"], "selection_brier": r["selection_brier"]}
                             for r in choice["grid_scores"])
        model = fit(fitting, f"outer{fold}_fit")
        models[fold] = model
        scores.append(score_model_groups(counts, model, heldout, selected, fold))
        for family in FAMILIES:
            base = coefficient_cases(counts, model, heldout, family)
            base["outer_fold"] = fold
            terms.append(base)
            for h, g in base.groupby("horizon_days"):
                A, B, C = np.average(g[["A", "B", "C"]], axis=0, weights=g.pair_count)
                curves.extend({"outer_fold": fold, "horizon_days": int(h), "family": family,
                               "alpha_value": k/10, "diagnostic_brier": A*(k/10)**2+B*(k/10)+C,
                               "eligible_pairs": int(g.pair_count.sum()),
                               "scope": "Predeclared fixed-alpha heldout diagnostic; not weight selection"}
                              for k in range(11))
        progress(f"Outer {fold+1}/5 complete: all nine forecasts scored on the same heldout cases.")
    return {"scores": pd.concat(scores, ignore_index=True), "selection": pd.DataFrame(selection),
            "grid_scores": pd.DataFrame(grids), "base_terms": pd.concat(terms, ignore_index=True),
            "support": pd.DataFrame(support), "numerical_audit": pd.DataFrame(audits),
            "models": models, "fixed_alpha_scores": pd.DataFrame(curves)}


def serialize_local_model(model):
    return {"training_ids": sorted(model["training_ids"]),
            "B1": {str(h): {str(j): p for j, p in d.items()} for h, d in model["B1"].items()},
            "B2": {f"{h}:{i}": {str(j): p for j, p in d.items()} for (h, i), d in model["B2"].items()},
            **{kind: {f"{h}:{i}": {"probabilities": {str(j): p for j, p in d.items()}, "unresolved": u}
                       for (h, i), (d, u) in model[kind].items()}
               for kind in ("Local-U", "Local-A")}}
