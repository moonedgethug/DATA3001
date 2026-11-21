"""Independent arithmetic checks using exported counts, IDs and predictions."""
from collections import Counter

import numpy as np
import pandas as pd


def independent_audit(counts, folds, roles, bases, predictions, scores, candidates, selected):
    keys = ["id", "horizon_days", "origin_cell_1", "destination_cell_1"]
    states = next(iter(bases.values())).states
    index = {int(c): i for i, c in enumerate(states)}
    errors = {"probability": 0., "brier": 0., "candidate_brier": 0.}
    rebuilt = {}
    for role, spec in roles.items():
        training = set(spec["training_ids"])
        if training & set(spec["evaluation_ids"]):
            raise AssertionError("Overlapping fit and evaluation IDs")
        if spec["outer_fold"] >= 0 and spec["inner_fold"] >= 0:
            excluded = set(folds.loc[folds.outer_fold.isin([spec["outer_fold"], spec["inner_fold"]]), "id"])
            if training & excluded:
                raise AssertionError("Inner fit contains an outer or inner holdout")
        counter = Counter()
        for r in counts.itertuples(index=False):
            if r.id in training:
                counter[(r.horizon_days, r.origin_cell_1, r.destination_cell_1)] += r.pair_count
        reference, raw, totals, medians = {}, {}, {}, {}
        for h in (7, 30):
            reference[h] = np.zeros(len(states))
        for (h, origin, dest), n in counter.items():
            raw.setdefault((h, origin), np.zeros(len(states)))[index[dest]] = n
            reference[h][index[dest]] += n
        for key, vector in raw.items():
            totals[key] = vector.sum()
            raw[key] = vector/vector.sum()
        for h in (7, 30):
            reference[h] /= reference[h].sum()
            medians[h] = float(np.median([n for (hh, _), n in totals.items() if hh == h]))
            errors["probability"] = max(errors["probability"], float(np.max(np.abs(reference[h]-bases[role].references[h]))))
            if medians[h] != bases[role].medians[h]:
                raise AssertionError("Reference support median differs")
        expected_counts = {(r.horizon_days, r.origin_cell_1, r.destination_cell_1): r.pair_count
                           for r in bases[role].b2.transitions.itertuples(index=False)}
        if dict(counter) != expected_counts:
            raise AssertionError("Fitting matrix disagrees with independent counts")
        rebuilt[role] = raw, reference, totals, medians

    def reference_vector(role, h, origin, family, a):
        raw, q, totals, med = rebuilt[role]
        if (h, origin) not in raw:
            return None
        if family == "B2" or a == 0:
            lam = 0.
        elif family == "Fixed" or a == 1:
            lam = a
        else:
            pseudo_count = med[h]*a/(1-a)
            lam = pseudo_count/(totals[(h, origin)]+pseudo_count)
        return raw[(h, origin)]*(1-lam)+q[h]*lam

    # Check every candidate score directly, without quadratic coefficient scoring.
    for role, group in candidates.groupby("fit_role"):
        evaluation = counts.loc[counts.id.isin(roles[role]["evaluation_ids"])]
        grouped = list(evaluation.groupby(["horizon_days", "origin_cell_1"]))
        for c in group.itertuples(index=False):
            numerator, denominator = 0., 0
            for (h, origin), cases in grouped:
                if h != c.horizon_days:
                    continue
                p = reference_vector(role, h, origin, c.model, c.parameter_a)
                if p is None:
                    continue
                observed = np.zeros(len(states))
                for r in cases.itertuples(index=False):
                    observed[index[r.destination_cell_1]] += r.pair_count
                total = int(observed.sum())
                numerator += total * np.square(p).sum() + total - 2*np.dot(p, observed)
                denominator += total
            if denominator != c.evaluable_pairs:
                raise AssertionError("Candidate score population differs")
            if denominator:
                errors["candidate_brier"] = max(errors["candidate_brier"], abs(numerator-c.score_sum)/denominator)

    # Independently repeat selection from recorded inner folds.
    for s in selected.itertuples(index=False):
        pool = candidates.loc[candidates.selection_role.eq(s.role) & candidates.horizon_days.eq(s.horizon_days)
                              & candidates.model.eq(s.model)]
        sums = pool.groupby("parameter_a")[["score_sum", "evaluable_pairs"]].sum()
        values = sums.score_sum / sums.evaluable_pairs
        chosen = float(values.loc[values <= values.min()+1e-12].index.min())
        if chosen != s.parameter_a:
            raise AssertionError("Parameter selection differs from declared tie rule")

    expected_cases = counts.sort_values(keys).reset_index(drop=True)
    for model, group in scores.groupby("model"):
        pd.testing.assert_frame_equal(group[keys+["pair_count"]].sort_values(keys).reset_index(drop=True), expected_cases,
                                      check_dtype=False, check_exact=True)
        if not group.outer_fold.eq(group.id.map(folds.set_index("id").outer_fold)).all():
            raise AssertionError("Wrong outer holdout assignment")
    selected_index = selected.set_index(["role", "horizon_days", "model"]).parameter_a
    for role, models in predictions.items():
        for family, vectors in models.items():
            for (h, origin), p in vectors.items():
                a = 0. if family == "B2" else float(selected_index.loc[(role, h, family)])
                ref = reference_vector(role, h, origin, family, a)
                errors["probability"] = max(errors["probability"], float(np.max(np.abs(p-ref))))
                if role == "all_development_candidate":
                    continue
                cases = scores.loc[scores.role.eq(role) & scores.model.eq(family)
                                   & scores.horizon_days.eq(h) & scores.origin_cell_1.eq(origin)]
                budget_refs = {}
                for name in (c for c in cases if c.startswith('hit_k_')):
                    k = int(name[6:])
                    d_values = sorted((float(v) for c, v in zip(states, ref) if c >= 0), reverse=True)
                    boundary = d_values[k-1]
                    high = [i for i,c in enumerate(states) if c >= 0 and ref[i] > boundary+1e-12]
                    tie = [i for i,c in enumerate(states) if c >= 0 and abs(ref[i]-boundary) <= 1e-12]
                    expected = np.zeros(len(states)); expected[high] = 1.
                    expected[tie] = (k-len(high))/len(tie)
                    budget_refs[name] = expected
                for dest, g in cases.groupby("destination_cell_1"):
                    one_hot = np.zeros(len(states)); one_hot[index[dest]] = 1.
                    expected = float(np.square(ref-one_hot).sum())
                    errors["brier"] = max(errors["brier"], float(np.max(np.abs(g.brier-expected))))
                    # Rebuild the 90% set independently, including cutoff ties.
                    ordered = sorted([v for v in ref if v > 0], reverse=True)
                    cumulative = 0.
                    for cutoff in ordered:
                        cumulative += cutoff
                        if cumulative >= .9-1e-12:
                            break
                    region = [i for i, v in enumerate(ref) if v > 0 and v >= cutoff-1e-12]
                    if not g.region90_hit.eq(float(index[dest] in region)).all():
                        raise AssertionError("Region-hit arithmetic differs")
                    if not g.region90_cells.eq(sum(states[i] >= 0 for i in region)).all():
                        raise AssertionError("Region size differs")
                    for name, expected in budget_refs.items():
                        if dest == -2:
                            if not g[name].isna().all():
                                raise AssertionError('Exit counted as a geographic budget hit')
                        elif np.max(np.abs(g[name]-expected[index[dest]])) > 1e-12:
                            raise AssertionError('Exact-budget expected hit differs')
    if max(errors.values()) > 1e-12:
        raise AssertionError(f"Independent arithmetic mismatch: {errors}")
    return {"independent_counts_reconciled": True, "candidate_selection_reproduced": True,
            "matched_heldout_cases_reconciled": True, "region_arithmetic_reproduced": True,
            "budget_arithmetic_reproduced": True,
            "whole_ID_leakage": False, "fitting_roles_checked": len(roles),
            **{f"max_{k}_error": v for k, v in errors.items()}}
