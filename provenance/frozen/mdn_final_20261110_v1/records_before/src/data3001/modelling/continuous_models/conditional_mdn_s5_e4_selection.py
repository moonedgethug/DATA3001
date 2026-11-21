"""Pure, frozen whole-drifter MDN selection and outer development evaluation.

This module consumes already frozen query scores. It never opens data, trains a
model, changes candidates, or substitutes a favourable query/model. Numerical
precision failures are engineering errors; unresolved scientific effects are
reported as failed promotion/acceptance gates.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


CANDIDATES = (1, 2, 3, 4, 6, 8, 12, 16, 18, 20, 22, 32)
INNER_PAIR_COUNTS = {'C_T0': 41761, 'C_T1': 44612}
INNER_ID_COUNTS = {'C_T0': 50, 'C_T1': 58}
INNER_UNIQUE_IDS = 104
OUTER_PAIR_COUNT = 33971
OUTER_ID_COUNT = 45
BOOTSTRAP_DRAWS = 10000
SELECTION_SEED = 20261124
OUTER_SEED = 20261125
CONTROLS = ('LocalGaussian', 'ExactPoint', 'EndpointCI')
OUTER_MODELS = tuple(f'MDN{k}' for k in CANDIDATES) + CONTROLS
REGION_FIELDS = ('h90', 'area90_km2', 'replica_area90_km2', 'land_mass',
                 'outside_D_mass', 'land_variance', 'outside_variance',
                 'hit_disagreement', 'mass_radius', 'mass_diagnostic', 'rank')
METRICS = ('energy_km', 'h90', 'area90_km2', 'land_mass', 'outside_D_mass')


def _at_most(value, limit):
    """Preserve inclusive thresholds under floating-point summation roundoff."""
    tolerance = 32 * np.finfo(float).eps * max(1., abs(value), abs(limit))
    return bool(value <= limit + tolerance)


def _finite(frame, fields):
    missing = [field for field in fields if field not in frame]
    if missing:
        raise ValueError(f'Missing required score fields: {missing}')
    if not np.isfinite(frame[list(fields)].to_numpy(dtype=float)).all():
        raise ValueError(f'Nonfinite score fields: {list(fields)}')


def _roster(frame, model_column, models, *, inner):
    keys = ['role', 'position', 'id']
    missing = [field for field in keys + [model_column] if field not in frame]
    if missing or frame.empty:
        raise ValueError(f'Incomplete query roster: {missing}')
    if frame[keys + [model_column]].isna().any().any():
        raise ValueError('Null query roster identity')
    if set(frame[model_column].unique()) != set(models):
        raise ValueError('All registered candidates are required, with no extra model')
    if frame.duplicated(['role', 'position', model_column]).any():
        raise ValueError('Duplicate candidate/query roster entries')
    reference = None
    for model in models:
        part = frame[frame[model_column].eq(model)].sort_values(keys)
        roster = part[keys].to_numpy()
        if reference is not None and not np.array_equal(roster, reference):
            raise ValueError('Unmatched candidate query rosters')
        reference = roster
        if inner:
            if set(part.role.unique()) != set(INNER_PAIR_COUNTS):
                raise ValueError('Both registered inner roles are required')
            for role, count in INNER_PAIR_COUNTS.items():
                group = part[part.role.eq(role)]
                if len(group) != count or group.id.nunique() != INNER_ID_COUNTS[role]:
                    raise ValueError(f'Frozen inner roster count mismatch: {role}')
            if part.id.nunique() != INNER_UNIQUE_IDS:
                raise ValueError('Frozen pooled inner ID roster count mismatch')
        elif (part.role.nunique() != 1 or len(part) != OUTER_PAIR_COUNT
              or part.id.nunique() != OUTER_ID_COUNT):
            raise ValueError('Frozen outer query/ID roster count mismatch')


def pooled_id_means(table, field, model_column='K'):
    """Average queries within ID/role, then roles within ID; never double-vote."""
    per_role = table.groupby(['id', 'role', model_column], sort=True)[field].mean()
    return per_role.groupby(['id', model_column]).mean().unstack(model_column).sort_index()


def query_weights(table):
    """Weights for one model: equal IDs, equal ID roles, equal role queries."""
    if table.empty or table[['id', 'role']].isna().any().any():
        raise ValueError('Cannot weight an empty or unidentified query roster')
    counts = table.groupby(['id', 'role'])['id'].transform('size').to_numpy()
    roles = table.groupby('id')['role'].transform('nunique').to_numpy()
    return 1. / (table.id.nunique() * roles * counts)


def _aligned(table, candidate, baseline, model_column):
    keys = ['role', 'position', 'id']
    first = table[table[model_column].eq(candidate)].sort_values(keys)
    second = table[table[model_column].eq(baseline)].sort_values(keys)
    if first.empty or first.duplicated(['role', 'position']).any():
        raise ValueError('Empty or duplicate candidate query roster')
    if not np.array_equal(first[keys].to_numpy(), second[keys].to_numpy()):
        raise ValueError('Unmatched paired query rosters')
    return first, second


def _energy_payload(frame, *, audit=False):
    columns = [f'es_{"audit_" if audit else ""}rep{r}' for r in range(8)]
    score_field = 'audit_energy_km' if audit else 'energy_km'
    present = [column in frame for column in columns]
    replicates = None
    if all(present) and not frame[columns].isna().all().all():
        _finite(frame, columns)
        replicates = frame[columns].to_numpy(dtype=float)
        score = replicates.mean(axis=1)
        variance = replicates.var(axis=1, ddof=1) / 8
        if score_field in frame and not frame[score_field].isna().all():
            _finite(frame, [score_field])
            if not np.allclose(frame[score_field], score, atol=1e-10, rtol=1e-12):
                raise ValueError(f'{score_field} does not match its eight replicate means')
    else:
        if any(present) and not all(present):
            raise ValueError('Exactly eight ES replicate columns are required')
        variance_field = 'audit_variance' if audit else ('es_variance' if 'es_variance' in frame else 'variance')
        _finite(frame, [score_field, variance_field])
        score = frame[score_field].to_numpy(dtype=float)
        variance = frame[variance_field].to_numpy(dtype=float)
    if (variance < 0).any():
        raise ValueError('Negative numerical integration variance')
    return score, variance, replicates


def paired_numerics(table, candidate, baseline, model_column='K', shared_streams=True):
    """Aggregate query-level paired replicate variance with squared ID weights.

    Set shared_streams=False for reused historical controls. Their independent
    variances are added even if their table happens to expose replicate arrays.
    """
    first, second = _aligned(table, candidate, baseline, model_column)
    weights = query_weights(first)
    result = {}
    for audit in (False, True):
        a, va, ra = _energy_payload(first, audit=audit)
        b, vb, rb = _energy_payload(second, audit=audit)
        if shared_streams:
            if ra is None or rb is None:
                raise ValueError('Shared-stream differences require both complete replicate arrays')
            variance = (ra - rb).var(axis=1, ddof=1) / 8
        else:
            variance = va + vb
        prefix = 'audit_' if audit else ''
        result[prefix + 'delta'] = float(weights @ (a - b))
        result[prefix + 'three_se'] = float(3 * np.sqrt((weights * weights) @ variance))
    result['independent_delta_drift'] = abs(result['delta'] - result['audit_delta'])
    result['uncertainty_bound'] = max(result['three_se'], result['audit_three_se'],
                                      result['independent_delta_drift'])
    result['shared_streams'] = bool(shared_streams)
    result['scientifically_resolved'] = _at_most(result['uncertainty_bound'], .1 * abs(result['delta']))
    return result


def _check_es_precision(record, baseline, label):
    if not np.isfinite(baseline) or baseline <= 0:
        raise ValueError(f'Positive aggregate baseline energy required: {label}')
    limit = .0001 * baseline
    if not (_at_most(record['three_se'], limit) and _at_most(record['audit_three_se'], limit)):
        raise ArithmeticError(f'Basic ES precision failed: {label}')


def select_k(inner_frame):
    """Select the provisional K using complete inner ES and the fixed 1SE rule."""
    _roster(inner_frame, 'K', CANDIDATES, inner=True)
    _finite(inner_frame, ['energy_km'])
    for k in CANDIDATES:
        rows = inner_frame[inner_frame.K.eq(k)]
        _energy_payload(rows)
        _energy_payload(rows, audit=True)
    ids = pooled_id_means(inner_frame, 'energy_km')
    scores = ids.mean()
    role_scores = inner_frame.groupby(['role', 'id', 'K']).energy_km.mean().groupby(['role', 'K']).mean()
    eligible, reasons, numerical = [1], {'1': []}, {}
    for k in CANDIDATES[1:]:
        failures = []
        for role in INNER_PAIR_COUNTS:
            part = inner_frame[inner_frame.role.eq(role)]
            record = paired_numerics(part, k, 1)
            numerical[f'{role}:{k}-1'] = record
            _check_es_precision(record, float(role_scores.loc[(role, 1)]), f'{role}:{k}-1')
            if not _at_most(record['delta'], 0.):
                failures.append(f'{role}:ES_INCREASE')
            if not record['scientifically_resolved']:
                failures.append(f'{role}:ES_UNRESOLVED')
        record = paired_numerics(inner_frame, k, 1)
        numerical[f'pooled:{k}-1'] = record
        _check_es_precision(record, float(scores[1]), f'pooled:{k}-1')
        if not _at_most(record['delta'], -.001 * float(scores[1])):
            failures.append('INSUFFICIENT_POOLED_GAIN')
        if not record['scientifically_resolved']:
            failures.append('POOLED_ES_UNRESOLVED')
        reasons[str(k)] = failures
        if not failures:
            eligible.append(k)

    minimum = min(eligible, key=lambda k: (float(scores[k]), k))
    best = minimum
    # Compare numerical equivalence against the actual minimum, not chained ties.
    for k in eligible:
        if k >= best:
            continue
        record = paired_numerics(inner_frame, k, minimum)
        numerical[f'best:{k}-{minimum}'] = record
        if _at_most(float(scores[k] - scores[minimum]), record['uncertainty_bound']):
            best = k
    draws = np.random.default_rng(SELECTION_SEED).integers(len(ids), size=(BOOTSTRAP_DRAWS, len(ids)))
    one_se, acceptable = {}, []
    for k in eligible:
        differences = (ids[k] - ids[best]).to_numpy(dtype=float)
        se = float(differences[draws].mean(axis=1).std(ddof=1))
        delta = float(differences.mean())
        within = _at_most(delta, se)
        one_se[str(k)] = dict(mean_difference=delta, paired_bootstrap_se=se, within_one_se=within)
        if within:
            acceptable.append(k)
    return dict(provisional_k=int(min(acceptable)), best_es_k=int(best), eligible=eligible,
                ineligibility=reasons, pooled_scores={str(k): float(scores[k]) for k in CANDIDATES},
                role_scores={f'{role}:{k}': float(value) for (role, k), value in role_scores.items()},
                paired_numerics=numerical, one_se_rule=one_se, unique_validation_ids=len(ids),
                bootstrap_draws=BOOTSTRAP_DRAWS, bootstrap_seed=SELECTION_SEED)


def _region_precision(frame, *, is_mdn, prefix=''):
    fields = [prefix + field for field in REGION_FIELDS]
    _finite(frame, fields)
    weights = query_weights(frame)
    for field in ('h90', 'land_mass', 'outside_D_mass', 'hit_disagreement', 'mass_radius', 'mass_diagnostic'):
        values = frame[prefix + field].to_numpy(dtype=float)
        if (values < 0).any() or (values > 1).any():
            raise ValueError(f'Invalid probability/diagnostic: {prefix + field}')
    for field in ('area90_km2', 'replica_area90_km2', 'land_variance', 'outside_variance'):
        if (frame[prefix + field].to_numpy(dtype=float) < 0).any():
            raise ValueError(f'Invalid nonnegative regional quantity: {prefix + field}')
    area = float(weights @ frame[prefix + 'area90_km2'])
    replica = float(weights @ frame[prefix + 'replica_area90_km2'])
    if area <= 0:
        raise ValueError('Positive aggregate region area required')
    result = dict(max_mass_radius=float(frame[prefix + 'mass_radius'].max()),
                  mass_diagnostic=float(weights @ frame[prefix + 'mass_diagnostic']),
                  hit_disagreement=float(weights @ frame[prefix + 'hit_disagreement']),
                  relative_area_drift=abs(replica - area) / area)
    for mass, variance in [('land', 'land_variance'), ('outside', 'outside_variance')]:
        result[mass + '_three_se'] = float(3 * np.sqrt((weights * weights) @ frame[prefix + variance]))
    ranks = frame[prefix + 'rank'].to_numpy(dtype=float)
    rank_valid = bool(np.isin(ranks, [0, 1, 2]).all() and (not is_mdn or (ranks == 2).all()))
    result['passed'] = bool(rank_valid and _at_most(result['max_mass_radius'], .005)
                            and _at_most(result['mass_diagnostic'], .005)
                            and _at_most(result['hit_disagreement'], .001)
                            and _at_most(result['relative_area_drift'], .005)
                            and _at_most(result['land_three_se'], .001)
                            and _at_most(result['outside_three_se'], .001))
    if not result['passed']:
        raise ArithmeticError('Basic region precision failed')
    return result


def _available(frame, columns):
    return all(column in frame and frame[column].notna().all() for column in columns)


def _region_audits(frame, *, is_mdn):
    result = {'primary': _region_precision(frame, is_mdn=is_mdn)}
    audit_fields = ['audit_' + field for field in REGION_FIELDS]
    # MDN results require their complete independent regional audit. Historical
    # controls have a verified full audit but only partial query audit columns;
    # the caller preserves that provenance outside this module.
    if is_mdn or _available(frame, audit_fields):
        result['audit'] = _region_precision(frame, is_mdn=is_mdn, prefix='audit_')
        weights = query_weights(frame)
        area = float(weights @ frame.area90_km2)
        cross = dict(hit_disagreement=float(weights @ np.abs(
                         frame.h90.to_numpy() - frame.audit_h90.to_numpy())),
                     relative_area_drift=abs(float(weights @ frame.audit_area90_km2) - area) / area)
        cross['passed'] = bool(_at_most(cross['hit_disagreement'], .001)
                               and _at_most(cross['relative_area_drift'], .005))
        if not cross['passed']:
            raise ArithmeticError('Basic region precision failed: primary/audit reconstruction')
        result['cross_reconstruction'] = cross
    return result


def _quality_comparison(table, candidate, baseline, model_column, *, shared_streams):
    first, second = _aligned(table, candidate, baseline, model_column)
    weights = query_weights(first)
    hit = float(weights @ (first.h90.to_numpy() - second.h90.to_numpy()))
    area_first = float(weights @ first.area90_km2)
    area_second = float(weights @ second.area90_km2)
    area_delta = area_first - area_second
    hit_error = float(weights @ (first.hit_disagreement.to_numpy() + second.hit_disagreement.to_numpy()))
    replica_delta = float(weights @ (first.replica_area90_km2.to_numpy() - second.replica_area90_km2.to_numpy()))
    area_error = abs(replica_delta - area_delta)
    if _available(first, ['audit_h90']) and _available(second, ['audit_h90']):
        audit_hit = float(weights @ (first.audit_h90.to_numpy() - second.audit_h90.to_numpy()))
        hit_error = max(hit_error, abs(audit_hit - hit))
    if _available(first, ['audit_hit_disagreement']) and _available(second, ['audit_hit_disagreement']):
        hit_error = max(hit_error, float(weights @ (first.audit_hit_disagreement.to_numpy()
                                                    + second.audit_hit_disagreement.to_numpy())))
    if _available(first, ['audit_area90_km2']) and _available(second, ['audit_area90_km2']):
        audit_delta = float(weights @ (first.audit_area90_km2.to_numpy() - second.audit_area90_km2.to_numpy()))
        area_error = max(area_error, abs(audit_delta - area_delta))
        if _available(first, ['audit_replica_area90_km2']) and _available(second, ['audit_replica_area90_km2']):
            audit_replica = float(weights @ (first.audit_replica_area90_km2.to_numpy()
                                             - second.audit_replica_area90_km2.to_numpy()))
            area_error = max(area_error, abs(audit_replica - audit_delta))
    geography = {}
    for field, variance in [('land_mass', 'land_variance'), ('outside_D_mass', 'outside_variance')]:
        delta = float(weights @ (first[field].to_numpy() - second[field].to_numpy()))
        va, vb = first[variance].to_numpy(), second[variance].to_numpy()
        # Indicator covariance is unavailable; sum of SD is a valid bound for
        # shared streams, whereas reused controls have independent variances.
        variances = (np.sqrt(va) + np.sqrt(vb)) ** 2 if shared_streams else va + vb
        error = float(3 * np.sqrt((weights * weights) @ variances))
        if _available(first, ['audit_' + field]) and _available(second, ['audit_' + field]):
            audit_delta = float(weights @ (first['audit_' + field].to_numpy() - second['audit_' + field].to_numpy()))
            error = max(error, abs(audit_delta - delta))
        geography[field] = dict(delta=delta, uncertainty_bound=error, passed=_at_most(delta + error, .01))
    numerical = bool(_at_most(hit_error, .1 * abs(hit)) and _at_most(area_error, .1 * abs(area_delta)))
    point = bool(_at_most(-hit, 0.) and _at_most(area_delta, 0.))
    geography_pass = all(item['passed'] for item in geography.values())
    return dict(hit_difference=hit, area_ratio=area_first / area_second,
                hit_numerical_disagreement=hit_error, area_numerical_relative_drift=area_error / area_second,
                quality_numerically_resolved=numerical, quality_preserved=point,
                geography=geography, geographic_guardrails=bool(geography_pass),
                passed=bool(numerical and point and geography_pass))


def apply_quality(choice, region_frame):
    """Gate only the provisional K against MDN1; failure goes straight to K=1."""
    chosen = choice['provisional_k']
    if chosen not in CANDIDATES:
        raise ValueError('Unregistered provisional K')
    if chosen == 1:
        return dict(choice, selected_k=1, status='complete', quality_gate='IDENTICAL_SINGLE_GAUSSIAN')
    _roster(region_frame, 'K', (1, chosen), inner=True)
    gates = {}
    for role in INNER_PAIR_COUNTS:
        part = region_frame[region_frame.role.eq(role)]
        precision = {str(k): _region_audits(part[part.K.eq(k)], is_mdn=True) for k in (1, chosen)}
        gates[role] = _quality_comparison(part, chosen, 1, 'K', shared_streams=True)
        gates[role]['precision'] = precision
    selected = chosen if all(gate['passed'] for gate in gates.values()) else 1
    return dict(choice, selected_k=int(selected), status='complete', quality_gate=gates)


def summarize_outer(outer_frame, selected_k):
    """Return nine-model summaries, paired 45-ID intervals and fixed acceptance.

    Returns (summary, per_id, comparisons, acceptance). Bootstrap uncertainty is
    conditional on the trained models; this remains outer development evidence.
    """
    if selected_k not in CANDIDATES:
        raise ValueError('Unregistered selected K')
    _roster(outer_frame, 'model', OUTER_MODELS, inner=False)
    _finite(outer_frame, METRICS)
    precision = {}
    for model in OUTER_MODELS:
        part = outer_frame[outer_frame.model.eq(model)]
        _energy_payload(part)
        _energy_payload(part, audit=True)
        precision[model] = _region_audits(part, is_mdn=model.startswith('MDN'))
    fields = list(METRICS) + [field for field in ('auxiliary_loss', 'model_mass90') if field in outer_frame]
    per_id = outer_frame.groupby(['id', 'model'], sort=True)[fields].mean().reset_index()
    summary = per_id.groupby('model', sort=True)[fields].mean().reindex(OUTER_MODELS)
    ids = sorted(per_id.id.unique())
    by_model = {model: per_id[per_id.model.eq(model)].set_index('id').loc[ids] for model in OUTER_MODELS}
    numerical = {}
    # Unselected K remain complete audited model results, never suppressed as
    # merely exploratory if their required engineering precision fails.
    for k in CANDIDATES:
        candidate = f'MDN{k}'
        for baseline in CONTROLS + (() if k == 1 else ('MDN1',)):
            record = paired_numerics(outer_frame, candidate, baseline, 'model',
                                     shared_streams=baseline.startswith('MDN'))
            _check_es_precision(record, float(summary.loc[baseline, 'energy_km']), f'{candidate}-{baseline}')
            numerical[f'{candidate}-{baseline}'] = record

    draws = np.random.default_rng(OUTER_SEED).integers(len(ids), size=(BOOTSTRAP_DRAWS, len(ids)))
    candidate = f'MDN{selected_k}'
    first = by_model[candidate]
    rows, hierarchy = [], True
    for baseline in CONTROLS + (() if selected_k == 1 else ('MDN1',)):
        second = by_model[baseline]
        es = (first.energy_km - second.energy_km).to_numpy()
        hit = (first.h90 - second.h90).to_numpy()
        area_a, area_b = first.area90_km2.to_numpy(), second.area90_km2.to_numpy()
        bootstrap_denominator = area_b[draws].mean(axis=1)
        if (bootstrap_denominator <= 0).any():
            raise ValueError('Nonpositive bootstrap baseline region area')
        es_ci = np.quantile(es[draws].mean(axis=1), [.025, .975])
        hit_ci = np.quantile(hit[draws].mean(axis=1), [.025, .975])
        area_ci = np.quantile(area_a[draws].mean(axis=1) / bootstrap_denominator, [.025, .975])
        record = numerical[f'{candidate}-{baseline}']
        quality = _quality_comparison(outer_frame, candidate, baseline, 'model',
                                      shared_streams=baseline.startswith('MDN'))
        relative = float(es.mean() / second.energy_km.mean())
        es_benefit = bool(_at_most(relative, -.001) and es_ci[1] < 0 and record['scientifically_resolved'])
        statistical = bool(_at_most(-float(hit_ci[0]), .01) and _at_most(float(area_ci[1]), 1.02))
        eligible = bool(es_benefit and quality['passed'] and statistical)
        if baseline in CONTROLS:
            hierarchy = bool(hierarchy and eligible)
        rows.append(dict(model=candidate, baseline=baseline, es_delta=float(es.mean()), es_relative=relative,
                         es_lower=float(es_ci[0]), es_upper=float(es_ci[1]), hit_delta=float(hit.mean()),
                         hit_lower=float(hit_ci[0]), hit_upper=float(hit_ci[1]), area_ratio=float(area_a.mean() / area_b.mean()),
                         area_lower=float(area_ci[0]), area_upper=float(area_ci[1]),
                         land_delta=quality['geography']['land_mass']['delta'],
                         outside_delta=quality['geography']['outside_D_mass']['delta'],
                         es_benefit=es_benefit, quality_preserved=quality['quality_preserved'],
                         quality_numerically_resolved=quality['quality_numerically_resolved'],
                         statistical_guardrails=statistical, geographic_guardrails=quality['geographic_guardrails'],
                         eligible=eligible, hierarchy_passed=hierarchy if baseline in CONTROLS else eligible,
                         es_three_se=record['three_se'], es_audit_three_se=record['audit_three_se'],
                         es_independent_delta_drift=record['independent_delta_drift'],
                         hit_numerical_disagreement=quality['hit_numerical_disagreement'],
                         area_numerical_relative_drift=quality['area_numerical_relative_drift']))
    comparisons = pd.DataFrame(rows)
    added = bool(selected_k > 1 and comparisons.loc[comparisons.baseline.eq('MDN1'), 'eligible'].iloc[0])
    acceptance = dict(status='complete', selected_k=int(selected_k), primary_model=candidate,
                      overall_retention=bool(hierarchy), supports_added_components=added,
                      unique_models=len(OUTER_MODELS), unique_validation_ids=len(ids),
                      query_count=OUTER_PAIR_COUNT, bootstrap_draws=BOOTSTRAP_DRAWS, bootstrap_seed=OUTER_SEED,
                      numerical_comparisons=numerical, region_precision=precision,
                      interpretation='Outer development validation; intervals condition on fitted models.')
    return summary, per_id, comparisons, acceptance
