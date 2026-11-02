"""Independent E3 counters, explicit probability scores and paired resample audit."""
from collections import Counter, defaultdict
import hashlib
import json
import math
import numpy as np
import pandas as pd

from data3001.paths import file_sha256
from data3001.modelling.common.qualified_count_inputs import read_frame
from data3001.modelling.baselines.b2_b1_e2_audit import verify_sealed_run

METRICS = ("brier", "region90_cells", "region90_hit")


def region(p):
    total = 0.
    for cutoff in sorted(p[p > 0], reverse=True):
        total += cutoff
        if total >= .9-1e-12:
            break
    return (p > 0) & (p >= cutoff-1e-12)


def rebuild(counts, folds, roles, states):
    index = {int(c): k for k, c in enumerate(states)}
    result = {}
    for role, spec in roles.items():
        train, evaluation = set(spec["training_ids"]), set(spec["evaluation_ids"])
        outer, inner = spec["outer_fold"], spec["inner_fold"]
        excluded = [v for v in (outer, inner) if v >= 0]
        assert train == set(folds.loc[~folds.outer_fold.isin(excluded), "id"])
        expected = set() if outer < 0 else set(folds.loc[folds.outer_fold.eq(inner if inner >= 0 else outer), "id"])
        assert evaluation == expected and not train & evaluation
        local = defaultdict(Counter)
        for r in counts.itertuples(index=False):
            if r.id in train:
                local[(r.horizon_days, r.origin_cell_1, r.id)][r.destination_cell_1] += r.pair_count
        raw, equal = {}, {}
        number = Counter()
        q = {h: np.zeros(len(states)) for h in (7, 30)}
        for (h, origin, ident), counter in sorted(local.items()):
            key = (h, origin)
            raw.setdefault(key, np.zeros(len(states)))
            equal.setdefault(key, np.zeros(len(states)))
            total = sum(counter.values())
            number[key] += 1
            for j, n in counter.items():
                raw[key][index[j]] += n
                equal[key][index[j]] += n/total
                q[h][index[j]] += n
        p = {k: v/v.sum() for k, v in raw.items()}
        eq = {k: v/number[k] for k, v in equal.items()}
        for h in q:
            q[h] /= q[h].sum()
        result[role] = dict(p=p, eq=eq, q=q, local=local, raw=raw, number=number)
    return result


def probability(base, h, origin, model, a):
    key = (h, origin)
    if key not in base["p"]:
        return None
    if model == "EqualID":
        return base["eq"][key]
    if model == "B2":
        return base["p"][key]
    return base["p"][key] + a*(base["q"][h]-base["p"][key])


def macro(records, fields=METRICS, pair_weighted=False):
    by_cell = defaultdict(list)
    for r in records:
        if r["supported"]:
            by_cell[r["origin_cell_1"]].append(r)
    answer = {}
    for field in fields:
        numerators, denominators = [], []
        for cell in by_cell.values():
            for r in cell:
                weight = r["eligible_pairs"] if pair_weighted else 1/len(cell)/len(by_cell)
                mass = r.get(field+"__mass", float(np.isfinite(r[field])))
                numerators.append(weight*(r[field] if np.isfinite(r[field]) else 0.))
                denominators.append(weight*mass)
        num, den = math.fsum(numerators), math.fsum(denominators)
        answer[field] = num/den if den else np.nan
    return answer


def audit_candidates(counts, roles, states, rebuilt, units, summaries):
    index = {int(c): k for k, c in enumerate(states)}
    observations = {}
    for r in counts.itertuples(index=False):
        observations.setdefault((r.horizon_days, r.origin_cell_1, r.id), Counter())[r.destination_cell_1] += r.pair_count
    cache, error = {}, 0.
    for role, group in units.groupby("fit_role"):
        eligible = counts[counts.id.isin(roles[role]["evaluation_ids"])]
        expected_keys = set(map(tuple, eligible[["horizon_days", "origin_cell_1", "id"]].drop_duplicates().to_numpy()))
        identities = list(group[["model", "parameter_a"]].drop_duplicates().itertuples(index=False, name=None))
        assert set(identities) == {("B2", 0.), ("EqualID", 0.), *[("Fixed", k/20) for k in range(21)]}
        for identity, section in group.groupby(["model", "parameter_a"]):
            actual_keys = list(map(tuple, section[["horizon_days", "origin_cell_1", "id"]].to_numpy()))
            assert len(actual_keys) == len(set(actual_keys)) and set(actual_keys) == expected_keys
    for r in units.itertuples(index=False):
        assert r.id in roles[r.fit_role]["evaluation_ids"]
        key = (r.fit_role, r.horizon_days, r.origin_cell_1, r.model, r.parameter_a)
        if key not in cache:
            p = probability(rebuilt[r.fit_role], *key[1:])
            cache[key] = None if p is None else (p, region(p), float(np.sum(p*p)))
        entry = cache[key]
        counts_id = observations[(r.horizon_days, r.origin_cell_1, r.id)]
        total = sum(counts_id.values())
        assert total == r.eligible_pairs and bool(r.supported) == (entry is not None)
        if entry is None:
            assert all(np.isnan(getattr(r, m)) for m in METRICS)
            continue
        p, selected, norm = entry
        b = sum(n*(1+norm-2*p[index[j]]) for j, n in counts_id.items())/total
        hit = sum(n for j, n in counts_id.items() if selected[index[j]])/total
        values = (b, int(np.sum(selected & (states >= 0))), hit)
        error = max(error, *(abs(v-getattr(r, m)) for v, m in zip(values, METRICS)))
    lookup = summaries.set_index(["fit_role", "horizon_days", "model", "parameter_a"])
    identities = 0
    for key, g in units.groupby(["fit_role", "horizon_days", "model", "parameter_a"], sort=True):
        expected = macro(g.to_dict("records"))
        actual = lookup.loc[key]
        for m in METRICS:
            error = max(error, abs(expected[m]-actual[m]))
        assert int(g.eligible_pairs.sum()) == actual.eligible_pairs
        assert len(g[g.supported]) == actual.evaluable_id_cells
        identities += 1
    assert error <= 1e-12, error
    return dict(candidate_id_cells_checked=len(units), candidate_identities_checked=identities,
                maximum_candidate_metric_error=error)


def audit_selection(units, selected, search):
    maximum = 0.
    for (role, h), g in units.groupby(["selection_role", "horizon_days"]):
        values = []
        for (model, a), candidate in g.groupby(["model", "parameter_a"]):
            assert not candidate.duplicated(["origin_cell_1", "id"]).any()
            expected = macro(candidate.to_dict("records"))
            stored = search[search.role.eq(role) & search.horizon_days.eq(h) &
                            search.model.eq(model) & search.parameter_a.eq(a)].iloc[0]
            maximum = max(maximum, *(abs(expected[m]-stored[m]) for m in METRICS))
            if model == "Fixed":
                values.append((a, expected["brier"]))
        minimum = min(b for a, b in values)
        chosen = min(a for a, b in values if b <= minimum+1e-12)
        actual = selected[selected.role.eq(role) & selected.horizon_days.eq(h)].iloc[0]
        assert actual.parameter_a == chosen
    assert maximum <= 1e-12, maximum
    return dict(passed=True, maximum_pooled_metric_error=maximum)


def independent_audit(paths, run, counts, folds, roles, states):
    root = run["results"]
    rebuilt = rebuild(counts, folds, roles, states)
    units = read_frame(root/"candidate_id_cells.parquet")
    candidates = read_frame(root/"candidate_scores.csv")
    selected = read_frame(root/"selected_parameters.csv")
    result = audit_candidates(counts, roles, states, rebuilt, units, candidates)
    assert len(roles) == 26 and result["candidate_identities_checked"] == 1150
    result["selection"] = audit_selection(units, selected, read_frame(root/"parameter_search.csv"))
    index = {int(c): k for k, c in enumerate(states)}
    max_error = 0.
    for role, base in rebuilt.items():
        support = read_frame(root/"bases"/f"{role}_support.csv")
        for r in support.itertuples(index=False):
            key = (r.horizon_days, r.origin_cell_1)
            number = base["number"][key]
            total = int(base["raw"][key].sum()) if key in base["raw"] else 0
            assert (r.training_id_count, r.training_pair_count, r.supported) == (number, total, total > 0)
        stored = read_frame(root/"bases"/f"{role}_b2.parquet")
        for r in stored.itertuples(index=False):
            assert r.pair_count == base["raw"][(r.horizon_days, r.origin_cell_1)][index[r.destination_cell_1]]
        eq = read_frame(root/"bases"/f"{role}_equal.parquet")
        for r in eq.itertuples(index=False):
            max_error = max(max_error, abs(r.probability-base["eq"][(r.horizon_days, r.origin_cell_1)][index[r.destination_cell_1]]))
        contrib = read_frame(root/"bases"/f"{role}_contributions.parquet")
        assert len(contrib) == len(base["local"])
        for r in contrib.itertuples(index=False):
            n = sum(base["local"][(r.horizon_days, r.origin_cell_1, r.id)].values())
            total = base["raw"][(r.horizon_days, r.origin_cell_1)].sum()
            m = base["number"][(r.horizon_days, r.origin_cell_1)]
            assert (r.local_pair_count, r.row_pair_count, r.row_id_count) == (n, total, m)
            max_error = max(max_error, abs(r.raw_share-n/total), abs(r.equal_share-1/m))
        local = read_frame(root/"bases"/f"{role}_local_distributions.parquet")
        assert len(local) == sum(len(v) for v in base["local"].values())
        for r in local.itertuples(index=False):
            counter = base["local"][(r.horizon_days, r.origin_cell_1, r.id)]
            assert r.pair_count == counter[r.destination_cell_1]
            frac = r.pair_count/sum(counter.values())
            max_error = max(max_error, abs(frac-r.within_id_probability),
                            abs(frac/base["number"][(r.horizon_days, r.origin_cell_1)]-r.fitting_group_weight))
        if "_inner_" in role:
            continue
        for model in ("B2", "EqualID", "Fixed"):
            table = read_frame(root/"matrices"/f"{role}_{model}.parquet")
            for (h, origin), group in table.groupby(["horizon_days", "origin_cell_1"]):
                a = float(selected[selected.role.eq(role) & selected.horizon_days.eq(h)].parameter_a.iloc[0])
                p = probability(base, h, origin, model, a)
                expected = set(states[p > 0])
                assert expected == set(group.destination_cell_1)
                max_error = max(max_error, float(np.max(np.abs(group.probability.to_numpy()-p[[index[j] for j in group.destination_cell_1]]))))
    scores = read_frame(root/"heldout_scores.parquet")
    for role in [f"outer_{k}" for k in range(5)]:
        expected = counts[counts.id.isin(roles[role]["evaluation_ids"])][["id", "horizon_days", "origin_cell_1", "destination_cell_1", "pair_count"]]
        for model in ("B2", "EqualID", "Fixed"):
            actual = scores[(scores.role == role) & (scores.model == model)][expected.columns]
            columns = list(expected.columns[:-1])
            pd.testing.assert_frame_equal(actual.sort_values(columns).reset_index(drop=True),
                                          expected.sort_values(columns).reset_index(drop=True), check_dtype=False)
    independent = defaultdict(lambda: dict(num=Counter(), mass=Counter(), n=0, supported=False))
    cache = {}
    metric_fields = [m for m in scores if m in (*METRICS, "region90_mass", "region90_exit_included", "positive_cells",
                    "true_probability", "predicted_exit_probability", "observed_exit", "zero_true_probability",
                    "squared_probability_sum", "seen_D_probability", "unseen_D_probability", "true_seen_D", "true_unseen_D", "D_region_hit")
                    or m.startswith("hit_k_")]
    for r in scores.itertuples(index=False):
        assert r.id in roles[r.role]["evaluation_ids"]
        a = float(selected[selected.role.eq(r.role) & selected.horizon_days.eq(r.horizon_days)].parameter_a.iloc[0])
        key = (r.role, r.horizon_days, r.origin_cell_1, r.model)
        if key not in cache:
            p = probability(rebuilt[r.role], r.horizon_days, r.origin_cell_1, r.model, a)
            cache[key] = None if p is None else (p, region(p))
        entry = cache[key]
        unit = independent[(r.horizon_days, r.model, r.origin_cell_1, r.id)]
        unit["n"] += r.pair_count
        unit["supported"] = entry is not None
        assert (r.status == "evaluable") == (entry is not None)
        if entry is not None:
            p, mask = entry
            y = index[r.destination_cell_1]
            truth = np.zeros(len(states)); truth[y] = 1
            expected = (float(np.sum((p-truth)**2)), int(np.sum(mask & (states >= 0))), float(mask[y]))
            max_error = max(max_error, *(abs(v-getattr(r, m)) for v, m in zip(expected, METRICS)))
            assert abs(p.sum()-1) <= 1e-12 and np.all(p >= 0) and r.unresolved_mass == 0
            assert (p[y] == 0) == (r.zero_true_probability == 1)
            b2 = rebuilt[r.role]["p"][(r.horizon_days, r.origin_cell_1)]
            seen = (states >= 0) & (b2 > 0)
            unseen = (states >= 0) & (b2 == 0)
            expected_fields = dict(
                true_probability=p[y], predicted_exit_probability=p[index[-2]],
                squared_probability_sum=np.square(p).sum(), region90_mass=p[mask].sum(),
                region90_exit_included=float(mask[index[-2]]),
                positive_cells=float(np.sum((states >= 0) & (p > 0))),
                observed_exit=float(r.destination_cell_1 == -2),
                seen_D_probability=p[seen].sum(), unseen_D_probability=p[unseen].sum(),
                true_seen_D=float(seen[y]), true_unseen_D=float(unseen[y]))
            max_error = max(max_error, *(abs(v-getattr(r, field)) for field, v in expected_fields.items()))
            if r.destination_cell_1 >= 0:
                for field in metric_fields:
                    if not field.startswith("hit_k_"):
                        continue
                    k = int(field[6:])
                    cutoff = np.sort(p[states >= 0])[::-1][k-1]
                    above = (states >= 0) & (p > cutoff+1e-12)
                    tied = (states >= 0) & (np.abs(p-cutoff) <= 1e-12)
                    inclusion = float(above[y]) + float(tied[y])*(k-above.sum())/tied.sum()
                    max_error = max(max_error, abs(inclusion-getattr(r, field)))
        for field in metric_fields:
            value = getattr(r, field)
            if np.isfinite(value):
                unit["num"][field] += r.pair_count*value
                unit["mass"][field] += r.pair_count
    expected_units = []
    for (h, model, origin, ident), value in sorted(independent.items()):
        n = value["n"]
        row = dict(horizon_days=h, model=model, origin_cell_1=origin, id=ident,
                   eligible_pairs=n, supported=value["supported"])
        for field in metric_fields:
            row[field] = value["num"][field]/n
            row[field+"__mass"] = value["mass"][field]/n
        expected_units.append(row)
    expected_units = pd.DataFrame(expected_units)
    actual_units = read_frame(root/"heldout_id_cells.parquet")
    keys = ["horizon_days", "model", "origin_cell_1", "id"]
    pd.testing.assert_frame_equal(expected_units.sort_values(keys).reset_index(drop=True),
                                  actual_units[expected_units.columns].sort_values(keys).reset_index(drop=True),
                                  check_exact=False, check_dtype=False, rtol=0, atol=1e-12)
    for name, grouping, pair in [("summary.csv", ["horizon_days", "model"], False),
                                 ("pair_weighted_summary.csv", ["horizon_days", "model"], True),
                                 ("cell_summary.csv", ["horizon_days", "model", "origin_cell_1"], False),
                                 ("fold_summary.csv", ["outer_fold", "horizon_days", "model"], False)]:
        table = read_frame(root/name).set_index(grouping)
        source = actual_units if "outer_fold" in grouping else expected_units
        for key, group in source.groupby(grouping):
            expected = macro(group.to_dict("records"), metric_fields, pair)
            row = table.loc[key]
            for m in metric_fields:
                if np.isfinite(expected[m]):
                    max_error = max(max_error, abs(expected[m]-row[m]))
            membership = defaultdict(list)
            for r in group.itertuples(index=False):
                membership[r.origin_cell_1].append(r.supported)
            availability = sum(sum(v)/len(v) for v in membership.values())/len(membership)
            assert abs(availability-row.target_availability) <= 1e-12
    for (h, model), g in scores.groupby(["horizon_days", "model"]):
        active = g[g.status.eq("evaluable")]
        M = active.groupby("origin_cell_1").id.nunique().to_dict()
        for r in g.itertuples(index=False):
            n = independent[(h, model, r.origin_cell_1, r.id)]["n"]
            w = r.pair_count/n/M[r.origin_cell_1]/len(M) if r.status == "evaluable" else 0.
            max_error = max(max_error, abs(w-r.primary_group_weight), abs(1/n-r.within_ID_pair_weight))
    changes = read_frame(root/"region_changes.csv")
    for r in changes.itertuples(index=False):
        new = cache[(r.role, r.horizon_days, r.origin_cell_1, "EqualID")][1]
        old = cache[(r.role, r.horizon_days, r.origin_cell_1, r.reference)][1]
        mask = new & ~old if r.part == "added" else old & ~new
        obs = counts[(counts.id == r.id) & (counts.horizon_days == r.horizon_days) & (counts.origin_cell_1 == r.origin_cell_1)]
        hit = sum(t.pair_count for t in obs.itertuples(index=False) if mask[index[t.destination_cell_1]])/obs.pair_count.sum()
        assert r.cells == int(np.sum(mask & (states >= 0)))
        max_error = max(max_error, abs(hit-r.hit))
    b2 = scores[scores.model.eq("B2")].set_index(["role", "id", "horizon_days", "origin_cell_1", "destination_cell_1"])
    eq = scores[scores.model.eq("EqualID")].set_index(b2.index.names)
    np.testing.assert_equal(eq.positive_cells.to_numpy(), b2.positive_cells.to_numpy())
    np.testing.assert_equal(eq.zero_true_probability.to_numpy(), b2.zero_true_probability.to_numpy())
    assert max_error <= 1e-12, max_error
    result.update(fitting_roles_checked=len(roles), heldout_grouped_cases_checked=len(scores),
                  primary_and_secondary_summaries_checked=True, positive_support_invariance=True,
                  maximum_independent_error=max_error)
    return result


def audit_uncertainty(root, folds, replicates, seed):
    ids = sorted(map(int, folds.id)); index = {d: k for k, d in enumerate(ids)}
    rng = np.random.Generator(np.random.PCG64(seed))
    weights = rng.exponential(size=(replicates, len(ids)))
    meta = json.loads((root/"multiplier_identity.json").read_text())
    assert meta["sorted_development_ids"] == ids
    assert hashlib.sha256(weights.astype("<f8").tobytes()).hexdigest() == meta["little_endian_float64_sha256"]
    units = read_frame(root/"heldout_id_cells.parquet")
    draws = read_frame(root/"bootstrap_draws.csv")
    error = 0.
    for (h, model), g in units[units.supported].groupby(["horizon_days", "model"]):
        expected = np.zeros((replicates, 3))
        for origin, cell in g.groupby("origin_cell_1"):
            numerator, denominator = np.zeros((replicates, 3)), np.zeros(replicates)
            for r in cell.itertuples(index=False):
                w = weights[:, index[r.id]]
                denominator += w
                numerator += w[:, None]*np.array([getattr(r, m) for m in METRICS])[None, :]
            expected += numerator/denominator[:, None]/g.origin_cell_1.nunique()
        actual = draws[draws.horizon_days.eq(h) & draws.model.eq(model)].sort_values("replicate")
        error = max(error, float(np.max(np.abs(actual[list(METRICS)].to_numpy()-expected))))
    differences = read_frame(root/"paired_differences.csv")
    points = read_frame(root/"summary.csv").set_index(["horizon_days", "model"])
    for r in differences.itertuples(index=False):
        a = draws[draws.horizon_days.eq(r.horizon_days)].pivot(index="replicate", columns="model", values=r.metric)
        delta = (a[r.model]-a[r.reference]).to_numpy()
        assert abs(np.quantile(delta, .025)-r.lower_95) <= 1e-12
        assert abs(np.quantile(delta, .975)-r.upper_95) <= 1e-12
        assert abs(points.loc[(r.horizon_days, r.model), r.metric]-points.loc[(r.horizon_days, r.reference), r.metric]-r.difference) <= 1e-12
        if r.model == "EqualID" and r.metric == "brier":
            assert abs(np.quantile(delta, .9875)-r.adjusted_upper) <= 1e-12
    for r in read_frame(root/"decisions.csv").itertuples(index=False):
        bound = differences[(differences.horizon_days == r.horizon_days) &
                            (differences.model == r.model) & (differences.reference == r.reference) &
                            (differences.metric == "brier")].adjusted_upper.iloc[0]
        outcome = ("no_measurable_Brier_gain" if r.delta_brier >= -1e-12 else
                   "conditional_development_Brier_support" if bound < -1e-12 else "point_improvement_uncertain")
        assert outcome == r.outcome
    assert error <= 1e-12, error
    return dict(passed=True, all_replicates_checked=replicates, maximum_resample_error=error)


def frozen_regressions(paths, run, guard, config, bases):
    receipts = {config[k]: verify_sealed_run(paths, config[k], guard)
                for k in ("frozen_s1_run", "frozen_e1_run", "frozen_e2_run")}
    current = read_frame(run["results"]/"heldout_scores.parquet")
    old = read_frame(paths.root/"results/runs"/config["frozen_s1_run"]/"heldout_scores.parquet")
    keys = ["id", "horizon_days", "origin_cell_1", "destination_cell_1"]
    new = current[current.model.eq("B2")][old.columns]
    pd.testing.assert_frame_equal(new.sort_values(keys).reset_index(drop=True), old.sort_values(keys).reset_index(drop=True),
                                  check_exact=False, rtol=0, atol=1e-12)
    compared = 0
    for legacy in ("frozen_e1_run", "frozen_e2_run"):
        root = paths.root/"results/runs"/config[legacy]
        params = read_frame(root/"selected_parameters.csv")
        for role in [f"outer_{k}" for k in range(5)] + ["all_development_candidate"]:
            base = bases[role]
            old_b2 = read_frame(root/"bases"/f"{role}_b2.parquet")
            pd.testing.assert_frame_equal(base.b2.transitions, old_b2, check_exact=False, rtol=0, atol=1e-12)
            old_b1 = read_frame(root/"bases"/f"{role}_b1.parquet")
            for r in old_b1.itertuples(index=False):
                assert abs(r.probability-base.references[r.horizon_days][base.index[r.destination_cell_1]]) <= 1e-12
            old_fixed = read_frame(root/"matrices"/f"{role}_Fixed.parquet")
            for (h, origin), group in old_fixed.groupby(["horizon_days", "origin_cell_1"]):
                a = float(params[(params.role == role) & (params.model == "Fixed") & (params.horizon_days == h)].parameter_a.iloc[0])
                p = (1-a)*base.rows[(h, origin)] + a*base.references[h]
                np.testing.assert_allclose(group.probability, p[[base.index[j] for j in group.destination_cell_1]], rtol=0, atol=1e-12)
            compared += 3
    return dict(passed=True, matched_parameter_formula_tables=compared, B2_heldout_regression=True,
                newly_selected_Fixed_parameters_not_required_to_match=True,
                sealed_artifacts_verified={k: len(v["output_sha256"]) for k, v in receipts.items()})
