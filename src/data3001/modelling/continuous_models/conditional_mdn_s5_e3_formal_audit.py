"""Independent, read-only verification of a completed formal MDN experiment.

The reference reductions below deliberately do not call the production selection
or summary functions. They rebuild query weights, ID/window means, numerical
errors, bootstrap draws and the direct K1 fallback from saved query tables.
The all-query numerical recalculation is the frozen ``outer_audit`` stage; its
separate 128-key IID/eigen-root/ECEF/density calculation is checked here at the
registered aggregate level, without adding a per-query three-SE requirement.

No validation target loader, training entry point, or final-test reader is used.
Calling :func:`audit` requires all calculation outputs to be complete first.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import traceback

import numpy as np
import pandas as pd

from data3001.paths import file_sha256
from . import conditional_mdn_s5_e3_inputs as inp
from .conditional_mdn_s5_e3_runtime import ROOT, atomic_json

KS = (1, 2, 4, 8, 16, 32)
SEEDS = (20261121, 20261122, 20261123)
ROLES = ('C_T0', 'C_T1', 'C_outer')
CONTROLS = ('LocalGaussian', 'ExactPoint', 'EndpointCI')
MODELS = tuple(f'MDN{k}' for k in KS) + CONTROLS
METRICS = ('energy_km', 'h90', 'area90_km2', 'land_mass', 'outside_D_mass')
LEVELS = (65536, 131072, 262144)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, label='value', *, rtol=1e-10, atol=1e-10):
    """Compare without replacing, dropping, or coercing failed evidence."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict), f'{label}: expected an object')
        for key, value in expected.items():
            require(key in actual, f'{label}: missing {key}')
            close(actual[key], value, f'{label}.{key}', rtol=rtol, atol=atol)
    elif isinstance(expected, (list, tuple)):
        require(isinstance(actual, (list, tuple)) and len(actual) == len(expected),
                f'{label}: sequence differs')
        for index, value in enumerate(expected):
            close(actual[index], value, f'{label}[{index}]', rtol=rtol, atol=atol)
    elif isinstance(expected, (bool, np.bool_)):
        require(isinstance(actual, (bool, np.bool_)) and bool(actual) == bool(expected),
                f'{label}: boolean differs')
    elif isinstance(expected, (int, np.integer)):
        require(not isinstance(actual, (bool, np.bool_)) and actual == expected,
                f'{label}: integer differs')
    elif isinstance(expected, (float, np.floating)):
        require(np.isfinite(expected) and np.isfinite(actual)
                and np.isclose(actual, expected, rtol=rtol, atol=atol), f'{label}: numeric value differs')
    else:
        require(actual == expected, f'{label}: value differs')


def at_most(value, limit):
    return bool(value <= limit + 32*np.finfo(float).eps*max(1., abs(value), abs(limit)))


def finite(frame, columns):
    require(all(column in frame for column in columns), 'Missing required audit fields')
    values = frame[list(columns)].to_numpy(dtype=np.float64)
    require(np.isfinite(values).all(), 'Nonfinite required audit fields')
    return values


def reference_weights(frame):
    """Explicit counts: equal IDs, then equal windows, then equal queries."""
    require(len(frame) > 0 and not frame[['id', 'role']].isna().any().any(),
            'Empty or null ID/window roster')
    pairs = list(zip(frame.id, frame.role))
    counts = Counter(pairs)
    windows = Counter(identifier for identifier, _ in counts)
    return np.array([1/(len(windows)*windows[identifier]*counts[identifier, role])
                     for identifier, role in pairs], dtype=np.float64)


def reference_id_means(frame, fields, model_column='K'):
    """Rebuild in explicit ID/window loops, independent of chained groupby."""
    finite(frame, fields)
    rows = []
    for (identifier, model), group in frame.groupby(['id', model_column], sort=True):
        window_means = [part[list(fields)].to_numpy(np.float64).mean(axis=0)
                        for _, part in group.groupby('role', sort=True)]
        mean = np.asarray(window_means).mean(axis=0)
        rows.append(dict(id=identifier, **{model_column: model},
                         **dict(zip(fields, mean))))
    return pd.DataFrame(rows)


def aligned(frame, candidate, baseline, model_column):
    keys = ['role', 'position', 'id']
    a = frame[frame[model_column].eq(candidate)].sort_values(keys)
    b = frame[frame[model_column].eq(baseline)].sort_values(keys)
    require(len(a) > 0 and not a.duplicated(['role', 'position']).any()
            and not b.duplicated(['role', 'position']).any(), 'Empty or duplicated paired roster')
    require(np.array_equal(a[keys].to_numpy(), b[keys].to_numpy()), 'Paired query keys differ')
    return a, b


def energy_arrays(frame, audit=False):
    prefix = 'audit_' if audit else ''
    columns = [f'es_{prefix}rep{r}' for r in range(8)]
    populated = [column in frame and frame[column].notna().any() for column in columns]
    if any(populated):
        require(all(populated), 'Incomplete eight-replicate energy evidence')
        replicates = finite(frame, columns)
        means = replicates.sum(axis=1)/8
        variance = np.sum((replicates-means[:, None])**2, axis=1)/56
        if prefix+'energy_km' in frame:
            np.testing.assert_allclose(finite(frame, [prefix+'energy_km'])[:, 0], means,
                                       rtol=1e-12, atol=1e-10)
        if prefix+'variance' in frame:
            np.testing.assert_allclose(finite(frame, [prefix+'variance'])[:, 0], variance,
                                       rtol=1e-10, atol=1e-12)
    else:
        require(not str(frame.model.iloc[0]).startswith('MDN') if 'model' in frame else False,
                'MDN energy requires eight explicit replicates')
        means, variance = finite(frame, [prefix+'energy_km', prefix+'variance']).T
        replicates = None
    require((variance >= 0).all(), 'Negative energy integration variance')
    return means, variance, replicates


def reference_numerics(frame, candidate, baseline, model_column='K', shared=True):
    a, b = aligned(frame, candidate, baseline, model_column)
    weights, result = reference_weights(a), {}
    for audit in (False, True):
        ea, va, ra = energy_arrays(a, audit)
        eb, vb, rb = energy_arrays(b, audit)
        if shared:
            require(ra is not None and rb is not None, 'Missing shared-stream replicate pairs')
            delta_rep = ra-rb
            variance = np.sum((delta_rep-delta_rep.mean(axis=1)[:, None])**2, axis=1)/56
        else:
            variance = va+vb
        prefix = 'audit_' if audit else ''
        result[prefix+'delta'] = float(np.sum(weights*(ea-eb)))
        result[prefix+'three_se'] = float(3*np.sqrt(np.sum(weights**2*variance)))
    result['independent_delta_drift'] = abs(result['delta']-result['audit_delta'])
    result['uncertainty_bound'] = max(result['three_se'], result['audit_three_se'],
                                       result['independent_delta_drift'])
    result['shared_streams'] = shared
    result['scientifically_resolved'] = at_most(result['uncertainty_bound'], .1*abs(result['delta']))
    return result


def es_precision(record, baseline):
    require(np.isfinite(baseline) and baseline > 0, 'Invalid baseline ES')
    require(at_most(record['three_se'], .0001*baseline)
            and at_most(record['audit_three_se'], .0001*baseline), 'Independent basic ES precision failed')


def reference_region(frame, mdn, prefix=''):
    probabilities = ('h90', 'land_mass', 'outside_D_mass', 'hit_disagreement',
                     'mass_radius', 'mass_diagnostic')
    nonnegative = ('area90_km2', 'replica_area90_km2', 'land_variance', 'outside_variance')
    p = finite(frame, [prefix+field for field in probabilities])
    v = finite(frame, [prefix+field for field in nonnegative])
    rank = finite(frame, [prefix+'rank'])[:, 0]
    require(((p >= 0) & (p <= 1)).all() and (v >= 0).all(), 'Invalid region quantities')
    w = reference_weights(frame)
    area, replica, land_var, outside_var = (v*w[:, None]).sum(axis=0)
    require(area > 0, 'Nonpositive mean region area')
    result = dict(max_mass_radius=float(p[:, 4].max()), mass_diagnostic=float(w@p[:, 5]),
                  hit_disagreement=float(w@p[:, 3]), relative_area_drift=float(abs(replica-area)/area),
                  land_three_se=float(3*np.sqrt(np.sum(w*w*v[:, 2]))),
                  outside_three_se=float(3*np.sqrt(np.sum(w*w*v[:, 3]))))
    result['passed'] = bool(np.isin(rank, (0, 1, 2)).all() and (not mdn or (rank == 2).all())
        and all(at_most(result[field], limit) for field, limit in (
            ('max_mass_radius', .005), ('mass_diagnostic', .005), ('hit_disagreement', .001),
            ('relative_area_drift', .005), ('land_three_se', .001), ('outside_three_se', .001))))
    require(result['passed'], 'Independent basic region precision failed')
    return result


def available(frame, fields):
    return all(field in frame and frame[field].notna().all() for field in fields)


def reference_regions(frame, mdn):
    result = {'primary': reference_region(frame, mdn)}
    fields = ['audit_'+field for field in ('h90', 'area90_km2', 'replica_area90_km2',
              'land_mass', 'outside_D_mass', 'land_variance', 'outside_variance',
              'hit_disagreement', 'mass_radius', 'mass_diagnostic', 'rank')]
    if mdn or available(frame, fields):
        result['audit'] = reference_region(frame, mdn, 'audit_')
        w = reference_weights(frame)
        values = finite(frame, ['h90', 'audit_h90', 'area90_km2', 'audit_area90_km2'])
        area = float(np.sum(w*values[:, 2]))
        cross = dict(hit_disagreement=float(np.sum(w*np.abs(values[:, 0]-values[:, 1]))),
                     relative_area_drift=float(abs(np.sum(w*values[:, 3])-area)/area))
        cross['passed'] = at_most(cross['hit_disagreement'], .001) and at_most(cross['relative_area_drift'], .005)
        require(cross['passed'], 'Independent primary/audit region reconstruction differs')
        result['cross_reconstruction'] = cross
    return result


def reference_quality(frame, candidate, baseline, model_column='K', shared=True):
    a, b = aligned(frame, candidate, baseline, model_column)
    w = reference_weights(a)
    mean = lambda rows, field: float(np.sum(w*finite(rows, [field])[:, 0]))
    difference = lambda field: mean(a, field)-mean(b, field)
    hit, area = difference('h90'), difference('area90_km2')
    hit_error = mean(a, 'hit_disagreement')+mean(b, 'hit_disagreement')
    area_error = abs(difference('replica_area90_km2')-area)
    for field in ('audit_h90', 'audit_hit_disagreement', 'audit_area90_km2', 'audit_replica_area90_km2'):
        if not (available(a, [field]) and available(b, [field])):
            continue
        if field == 'audit_h90':
            hit_error = max(hit_error, abs(difference(field)-hit))
        elif field == 'audit_hit_disagreement':
            hit_error = max(hit_error, mean(a, field)+mean(b, field))
        elif field == 'audit_area90_km2':
            area_error = max(area_error, abs(difference(field)-area))
        else:
            area_error = max(area_error, abs(difference(field)-difference('audit_area90_km2')))
    geography = {}
    for field, variance_field in (('land_mass', 'land_variance'), ('outside_D_mass', 'outside_variance')):
        va, vb = finite(a, [variance_field])[:, 0], finite(b, [variance_field])[:, 0]
        require((va >= 0).all() and (vb >= 0).all(), 'Negative geographic variance')
        variance = va+vb+2*np.sqrt(va*vb) if shared else va+vb
        error = float(3*np.sqrt(np.sum(w*w*variance)))
        delta = difference(field)
        if available(a, ['audit_'+field]) and available(b, ['audit_'+field]):
            error = max(error, abs(difference('audit_'+field)-delta))
        geography[field] = dict(delta=delta, uncertainty_bound=error, passed=at_most(delta+error, .01))
    resolved = at_most(hit_error, .1*abs(hit)) and at_most(area_error, .1*abs(area))
    point = at_most(-hit, 0) and at_most(area, 0)
    geo = all(value['passed'] for value in geography.values())
    return dict(hit_difference=hit, area_ratio=mean(a, 'area90_km2')/mean(b, 'area90_km2'),
                hit_numerical_disagreement=hit_error,
                area_numerical_relative_drift=area_error/mean(b, 'area90_km2'),
                quality_numerically_resolved=resolved, quality_preserved=point,
                geography=geography, geographic_guardrails=geo, passed=bool(resolved and point and geo))


def reference_selection(energy, regions=None):
    require(set(energy.K.unique()) == set(KS), 'All six inner candidates required')
    means = reference_id_means(energy, ['energy_km'])
    identifiers = sorted(means.id.unique())
    by_id = {k: means[means.K.eq(k)].set_index('id').loc[identifiers, 'energy_km'].to_numpy()
             for k in KS}
    scores = {k: float(values.mean()) for k, values in by_id.items()}
    role_scores = {}
    for (role, k), group in energy.groupby(['role', 'K']):
        role_scores[f'{role}:{k}'] = float(np.mean([
            rows.energy_km.to_numpy().mean() for _, rows in group.groupby('id')]))
    eligible, reasons, numerical = [1], {'1': []}, {}
    for k in KS[1:]:
        failures = []
        for role in ROLES[:2]:
            record = reference_numerics(energy[energy.role.eq(role)], k, 1)
            numerical[f'{role}:{k}-1'] = record
            es_precision(record, role_scores[f'{role}:1'])
            if not at_most(record['delta'], 0):
                failures.append(f'{role}:ES_INCREASE')
            if not record['scientifically_resolved']:
                failures.append(f'{role}:ES_UNRESOLVED')
        record = reference_numerics(energy, k, 1)
        numerical[f'pooled:{k}-1'] = record
        es_precision(record, scores[1])
        if not at_most(record['delta'], -.001*scores[1]):
            failures.append('INSUFFICIENT_POOLED_GAIN')
        if not record['scientifically_resolved']:
            failures.append('POOLED_ES_UNRESOLVED')
        reasons[str(k)] = failures
        if not failures:
            eligible.append(k)
    minimum = min(eligible, key=lambda k: (scores[k], k))
    best = minimum
    for k in eligible:
        if k < best:
            record = reference_numerics(energy, k, minimum)
            numerical[f'best:{k}-{minimum}'] = record
            if at_most(scores[k]-scores[minimum], record['uncertainty_bound']):
                best = k
    draws = np.random.default_rng(20261124).integers(len(identifiers), size=(10000, len(identifiers)))
    one_se, acceptable = {}, []
    for k in eligible:
        difference = by_id[k]-by_id[best]
        se = float(np.std(np.mean(difference[draws], axis=1), ddof=1))
        delta = float(np.mean(difference))
        within = at_most(delta, se)
        one_se[str(k)] = dict(mean_difference=delta, paired_bootstrap_se=se, within_one_se=within)
        if within:
            acceptable.append(k)
    provisional = min(acceptable)
    selected = provisional
    quality = 'IDENTICAL_SINGLE_GAUSSIAN'
    if provisional > 1:
        require(regions is not None and set(regions.K.unique()) == {1, provisional},
                'Only MDN1 and the provisional candidate may enter quality selection')
        quality = {}
        for role in ROLES[:2]:
            part = regions[regions.role.eq(role)]
            gate = reference_quality(part, provisional, 1)
            gate['precision'] = {str(k): reference_regions(part[part.K.eq(k)], True)
                                 for k in (1, provisional)}
            quality[role] = gate
        if not all(gate['passed'] for gate in quality.values()):
            selected = 1
    return dict(provisional_k=provisional, best_es_k=best, eligible=eligible,
                ineligibility=reasons, pooled_scores={str(k): scores[k] for k in KS},
                role_scores=role_scores, paired_numerics=numerical, one_se_rule=one_se,
                unique_validation_ids=len(identifiers), bootstrap_draws=10000, bootstrap_seed=20261124,
                selected_k=selected, status='complete', quality_gate=quality)


def reference_outer(table, selected_k):
    require(selected_k in KS and set(table.model.unique()) == set(MODELS), 'Invalid outer model roster')
    fields = list(METRICS)+[field for field in ('auxiliary_loss', 'model_mass90') if field in table]
    per_id = reference_id_means(table, fields, 'model')
    identifiers = sorted(per_id.id.unique())
    by_model = {model: per_id[per_id.model.eq(model)].set_index('id').loc[identifiers] for model in MODELS}
    summary = pd.DataFrame([dict(model=model, **{field: float(by_model[model][field].mean())
                                               for field in fields}) for model in MODELS]).set_index('model')
    precision, numerical = {}, {}
    for model in MODELS:
        part = table[table.model.eq(model)]
        energy_arrays(part); energy_arrays(part, True)
        precision[model] = reference_regions(part, model.startswith('MDN'))
    for k in KS:
        model = f'MDN{k}'
        for baseline in CONTROLS+(() if k == 1 else ('MDN1',)):
            record = reference_numerics(table, model, baseline, 'model', baseline.startswith('MDN'))
            es_precision(record, summary.loc[baseline, 'energy_km'])
            numerical[f'{model}-{baseline}'] = record
    draws = np.random.default_rng(20261125).integers(len(identifiers), size=(10000, len(identifiers)))
    model, rows, hierarchy = f'MDN{selected_k}', [], True
    first = by_model[model]
    for baseline in CONTROLS+(() if selected_k == 1 else ('MDN1',)):
        second = by_model[baseline]
        delta = first.energy_km.to_numpy()-second.energy_km.to_numpy()
        hit = first.h90.to_numpy()-second.h90.to_numpy()
        area_a, area_b = first.area90_km2.to_numpy(), second.area90_km2.to_numpy()
        denominator = np.mean(area_b[draws], axis=1)
        require((denominator > 0).all(), 'Nonpositive bootstrap denominator')
        es_ci = np.percentile(np.mean(delta[draws], axis=1), [2.5, 97.5])
        hit_ci = np.percentile(np.mean(hit[draws], axis=1), [2.5, 97.5])
        area_ci = np.percentile(np.mean(area_a[draws], axis=1)/denominator, [2.5, 97.5])
        record = numerical[f'{model}-{baseline}']
        quality = reference_quality(table, model, baseline, 'model', baseline.startswith('MDN'))
        relative = float(delta.mean()/second.energy_km.mean())
        benefit = bool(at_most(relative, -.001) and es_ci[1] < 0 and record['scientifically_resolved'])
        statistical = bool(at_most(-float(hit_ci[0]), .01) and at_most(float(area_ci[1]), 1.02))
        eligible = bool(benefit and quality['passed'] and statistical)
        if baseline in CONTROLS:
            hierarchy = hierarchy and eligible
        rows.append(dict(model=model, baseline=baseline, es_delta=float(delta.mean()), es_relative=relative,
            es_lower=float(es_ci[0]), es_upper=float(es_ci[1]), hit_delta=float(hit.mean()),
            hit_lower=float(hit_ci[0]), hit_upper=float(hit_ci[1]), area_ratio=float(area_a.mean()/area_b.mean()),
            area_lower=float(area_ci[0]), area_upper=float(area_ci[1]),
            land_delta=quality['geography']['land_mass']['delta'],
            outside_delta=quality['geography']['outside_D_mass']['delta'], es_benefit=benefit,
            quality_preserved=quality['quality_preserved'],
            quality_numerically_resolved=quality['quality_numerically_resolved'],
            statistical_guardrails=statistical, geographic_guardrails=quality['geographic_guardrails'],
            eligible=eligible, hierarchy_passed=hierarchy if baseline in CONTROLS else eligible,
            es_three_se=record['three_se'], es_audit_three_se=record['audit_three_se'],
            es_independent_delta_drift=record['independent_delta_drift'],
            hit_numerical_disagreement=quality['hit_numerical_disagreement'],
            area_numerical_relative_drift=quality['area_numerical_relative_drift']))
    comparisons = pd.DataFrame(rows)
    added = bool(selected_k > 1 and comparisons.loc[comparisons.baseline.eq('MDN1'), 'eligible'].iloc[0])
    acceptance = dict(status='complete', selected_k=selected_k, primary_model=model,
        overall_retention=bool(hierarchy), supports_added_components=added, unique_models=len(MODELS),
        unique_validation_ids=len(identifiers), query_count=len(table[table.model.eq('MDN1')]),
        bootstrap_draws=10000, bootstrap_seed=20261125, numerical_comparisons=numerical,
        region_precision=precision,
        interpretation='Outer development validation; intervals condition on fitted models.')
    return summary, per_id, comparisons, acceptance


def verify_iid(table, query_count):
    """Check exactly 128 frozen keys per K and paired aggregate three-SE bounds."""
    positions = np.floor(np.arange(min(128, query_count))*(query_count-1)/max(1, min(128, query_count)-1)).astype(int)
    result = {}
    fields = ['iid_energy_km', 'iid_variance', 'iid_count', 'iid_density_max_abs']
    for k in KS:
        part = table[table.K.eq(k)].sort_values('position')
        require(all(field in part for field in fields), 'Missing independent IID columns')
        present = part[fields].notna()
        require((present.all(axis=1) == present.any(axis=1)).all(), 'Partially missing IID evidence')
        checked = part[present.all(axis=1)]
        require(np.array_equal(checked.position.to_numpy(), positions), 'IID fixed-key roster differs')
        values = finite(checked, fields)
        require((values[:, 1] >= 0).all() and (values[:, 2] == 65536).all()
                and (values[:, 3] >= 0).all() and (values[:, 3] <= 1e-7).all(),
                'IID count, variance or independent density check failed')
        weights, comparisons = reference_weights(checked), {}
        for is_audit, label in ((False, 'primary'), (True, 'audit')):
            es, variance, _ = energy_arrays(checked, is_audit)
            difference = values[:, 0]-es
            bound = float(3*np.sqrt(np.sum(weights**2*(variance+values[:, 1]))))
            delta = float(np.sum(weights*difference))
            passed = at_most(abs(delta), bound)
            comparisons[label] = dict(mean_difference=delta, three_se=bound, passed=passed)
            require(passed, f'Independent aggregate IID three-SE check failed: MDN{k} {label}')
        result[str(k)] = dict(cases=len(checked), query_ids=int(checked.id.nunique()),
            density_max_abs=float(values[:, 3].max()), comparisons=comparisons,
            per_query_three_se_required=False)
    return result


def verify_full_numerical(table):
    """Cross-check all queries of every K, including unselected candidates."""
    result = {}
    for k in KS:
        rows = table[table.K.eq(k)]
        require(len(rows) > 0, 'Missing all-query numerical audit candidate')
        w = reference_weights(rows)
        primary, variance, _ = energy_arrays(rows)
        reference, reference_variance, _ = energy_arrays(rows, True)
        values = finite(rows, ['h90', 'audit_h90', 'area90_km2', 'audit_area90_km2'])
        hit = float(np.sum(w*np.abs(values[:, 0]-values[:, 1])))
        area = float(np.sum(w*values[:, 2]))
        require(area > 0, 'Nonpositive all-query primary region area')
        area_drift = float(abs(np.sum(w*values[:, 3])-area)/area)
        require(at_most(hit, .001) and at_most(area_drift, .005),
                f'Full independent region reconstruction differs: MDN{k}')
        result[str(k)] = dict(query_count=len(rows), query_ids=int(rows.id.nunique()),
            energy_difference=float(np.sum(w*(reference-primary))),
            energy_combined_three_se=float(3*np.sqrt(np.sum(w*w*(variance+reference_variance)))),
            hit_disagreement=hit, area_relative_drift=area_drift, passed=True,
            energy_acceptance='All declared paired contrasts checked independently in outer acceptance.')
    return result


def verify_roster(frame, queries, models, model_column='K'):
    require(set(frame[model_column].unique()) == set(models), 'Missing or extra candidate/model')
    require(not frame.duplicated(['role', 'position', model_column]).any(), 'Duplicated scoring key')
    require(set(frame.role.unique()) == set(queries), 'Scoring role roster differs')
    for model in models:
        for role, query in queries.items():
            rows = frame[frame[model_column].eq(model) & frame.role.eq(role)].sort_values('position')
            require(np.array_equal(rows.position.to_numpy(), np.arange(len(query))), 'Missing scoring position')
            require(np.array_equal(rows[inp.KEY].to_numpy(), query[inp.KEY].to_numpy()), 'Frozen source-key mismatch')
    if 'excluded' in frame:
        require(not frame.excluded.fillna(False).any(), 'Excluded formal query')


def compare_frames(actual, expected, keys, label):
    require(set(actual.columns) == set(expected.columns), f'{label}: columns differ')
    a, b = actual.sort_values(keys).reset_index(drop=True), expected.sort_values(keys).reset_index(drop=True)
    require(len(a) == len(b), f'{label}: row count differs')
    for field in b:
        missing_a, missing_b = a[field].isna().to_numpy(), b[field].isna().to_numpy()
        require(np.array_equal(missing_a, missing_b), f'{label}.{field}: missing-value pattern differs')
        present = ~missing_b
        if pd.api.types.is_numeric_dtype(b[field]) and not pd.api.types.is_bool_dtype(b[field]):
            av, bv = a.loc[present, field].to_numpy(dtype=float), b.loc[present, field].to_numpy(dtype=float)
            require(np.isfinite(av).all() and np.isfinite(bv).all(), f'{label}.{field}: nonfinite values')
            np.testing.assert_allclose(av, bv, rtol=1e-10, atol=1e-10, err_msg=label+'.'+field)
        else:
            require(np.array_equal(a.loc[present, field].to_numpy(), b.loc[present, field].to_numpy()),
                    f'{label}.{field}: values differ')


class Evidence:
    """Record each successfully verified dependency, with root-confined paths."""
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.hashes = {}

    def file(self, path, expected=None):
        path = Path(path).resolve()
        require(path.is_relative_to(self.root), 'Audit evidence escapes the project root')
        require(path.is_file(), 'Missing required audit evidence: '+str(path))
        digest = file_sha256(path)
        require(expected is None or expected == digest, 'Audit evidence checksum differs: '+str(path))
        relative = path.relative_to(self.root).as_posix()
        require(relative not in self.hashes or self.hashes[relative] == digest,
                'Evidence changed during the audit: '+relative)
        self.hashes[relative] = digest
        return path

    def json(self, path, expected=None):
        return json.loads(self.file(path, expected).read_text())

    def mapping(self, values, base=None):
        require(isinstance(values, dict) and bool(values), 'Empty source/hash manifest')
        for name, digest in values.items():
            relative = Path(name)
            require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe evidence path')
            self.file((self.root if base is None else base)/relative, digest)

    def artifact(self, formal_root, record):
        relative = Path(record['path'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe formal artifact path')
        path = (formal_root/relative).resolve()
        require(path.is_relative_to(formal_root.resolve()), 'Formal artifact escapes its run')
        return self.file(path, record['sha256'])


def array_digest(*arrays):
    digest = hashlib.sha256()
    for values in arrays:
        values = np.ascontiguousarray(values)
        digest.update(str(values.dtype).encode('ascii'))
        digest.update(json.dumps(values.shape).encode('ascii'))
        digest.update(values.tobytes())
    return digest.hexdigest()


def partition_reference(ids):
    identifiers = sorted(set(map(int, ids)))
    ordered = sorted(identifiers, key=lambda identifier: (
        hashlib.sha256(f'mdn_s5_e3_stop_v1|{identifier}'.encode()).hexdigest(), identifier))
    stop = ordered[:math.ceil(len(identifiers)/10)]
    return sorted(set(identifiers)-set(stop)), stop


def verify_fit_record(record, role_identity, k, fit, x, y, selected=None):
    """Audit complete epoch coverage, raw best, patience, scaler and stream IDs."""
    ids = fit.id.to_numpy(np.int64)
    full = selected is not None
    purpose = 'full_refit' if full else 'early_stop'
    opt_ids, stop_ids = (sorted(set(ids.tolist())), []) if full else partition_reference(ids)
    mask = np.isin(ids, opt_ids)
    count = int(mask.sum())
    epochs = selected['best_epoch'] if full else 500
    identity = record['identity']
    seed = record['base_seed']
    require(seed in SEEDS and (not full or seed == selected['base_seed']), 'Unexpected fit seed')
    seeds = {purpose_: int.from_bytes(hashlib.sha256(
        f'mdn_s5_e3_v1|{purpose_}|{role_identity["role"]}|{k}|{seed}||'.encode()).digest()[:8], 'little')
        for purpose_ in ('init', 'shuffle')}
    close(identity, dict(checkpoint_version=1, contract_sha256=role_identity['contract_sha256'],
        data_sha256=array_digest(x, y, ids), external=role_identity, k=k, role=role_identity['role'],
        base_seed=seed, purpose=purpose, stream_seeds=seeds, max_epochs=epochs, batch_size=4096,
        architecture='2-64tanh-64tanh-6K', covariance_floor=.001,
        optimizer=dict(name='AdamW', lr=.001, betas=[.9, .999], eps=1e-8,
                       weight_decay_weights_only=1e-4, clip_norm=5.),
        patience=30, min_improvement=1e-4, dtype='float64', device='cpu',
        optimization_ids=opt_ids, stop_ids=stop_ids), 'fit.identity')
    require(str(identity['torch_version']).split('+')[0] == '2.14.1'
            and 1 <= identity['threads'] <= 4, 'Training runtime differs from contract')
    expected_scaler = dict(x_mean=x[mask].mean(axis=0).tolist(), x_std=x[mask].std(axis=0).tolist(),
                           y_mean=y[mask].mean(axis=0).tolist(), y_std=y[mask].std(axis=0).tolist())
    close(record['standardizer'], expected_scaler, 'fit.standardizer', rtol=1e-12, atol=1e-12)
    require(all(value > 0 for name in ('x_std', 'y_std') for value in expected_scaler[name]),
            'Invalid fitted standardizer scale')
    history = record['history']
    require(record['purpose'] == purpose and len(history) == record['epochs_completed']
            and 1 <= len(history) <= epochs, 'Incomplete training history')
    expected_batches = [4096]*(count//4096)+([count % 4096] if count % 4096 else [])
    best, best_epoch, anchor, bad = math.inf, 0, math.inf, 0
    for epoch, row in enumerate(history, 1):
        close(row, dict(epoch=epoch, pairs_seen=count, batch_sizes=expected_batches), 'fit.epoch')
        require(np.isfinite(row['training_nll']) and 0 <= row['clipped_steps'] <= len(expected_batches),
                'Nonfinite training loss or invalid clipping count')
        close(row['gradient_clip_rate'], row['clipped_steps']/len(expected_batches), 'fit.clip_rate')
        if full:
            require(row['stop_nll'] is None, 'Full refit inspected a stopping outcome')
        else:
            score = row['stop_nll']
            require(np.isfinite(score), 'Nonfinite early-stop loss')
            if score < best:
                best, best_epoch = float(score), epoch
            if anchor-score >= 1e-4:
                anchor, bad = float(score), 0
            else:
                bad += 1
            require(bad < 30 or epoch == len(history), 'Training continued after contracted patience')
    if full:
        close(record, dict(status='complete', epochs_completed=epochs, best_epoch=epochs, best_nll=None),
              'full_refit')
    else:
        expected_status = 'early_stopped' if bad >= 30 else 'epoch_cap_reached'
        require(bad >= 30 or len(history) == 500, 'Nonterminal early-stop training')
        close(record, dict(status=expected_status, best_epoch=best_epoch, best_nll=best), 'early_stop')
    return sum(len(row['batch_sizes']) for row in history)


def verify_checkpoint(evidence, base, record, expected_steps):
    import torch
    path = evidence.artifact(base, record['checkpoint'])
    # Checkpoints are current-run local files whose cryptographic identity was
    # verified immediately above; no external pickle is accepted.
    payload = torch.load(path, map_location='cpu', weights_only=False)
    require(payload['identity'] == record['identity'] and payload['standardizer'] == record['standardizer'],
            'Checkpoint metadata differs from training receipt')
    progress = payload['progress']
    require(progress['history'] == record['history'] and progress['status'] == record['status']
            and progress['epoch'] == record['epochs_completed'] and progress['order'] is None,
            'Checkpoint is not the complete recorded training state')
    require(all(torch.isfinite(tensor).all().item() and tensor.dtype == torch.float64
                for tensor in payload['model_state'].values()), 'Invalid saved network weights')
    require(bool(payload['optimizer_state']['state']), 'Missing completed optimizer state')
    for state in payload['optimizer_state']['state'].values():
        require(float(state['step']) == expected_steps, 'Optimizer steps reveal an incomplete or warm-start refit')
        require(all(not isinstance(value, torch.Tensor) or torch.isfinite(value).all().item()
                    for value in state.values()), 'Nonfinite optimizer state')
    if record['purpose'] == 'full_refit':
        require(payload['best_model_state'] is None and payload['tracker']['best_epoch'] == 0,
                'Full refit reused an early-stop tracker or weights')
    else:
        require(payload['best_model_state'] is not None, 'Missing raw-best early-stop checkpoint')
        close(payload['tracker'], {key: record[key] for key in ('best_epoch', 'best_nll')}, 'checkpoint.best')
    return path


def verify_refit_forecasts(checkpoint, query, parameters):
    """Reproduce every scored distribution through the public prediction API."""
    from .conditional_mdn_s5_e3_inference import from_checkpoint
    prediction = from_checkpoint(checkpoint).mixture(query[['lon', 'lat']].to_numpy(np.float64))
    np.testing.assert_array_equal(prediction['origins_lonlat'], parameters['origins'])
    for exported, public in (('pi', 'weights'), ('mu', 'means_km'), ('cov', 'covariances_km2')):
        # The export and this forward pass both use CPU float64 and the saved
        # scaler. This permits rounding only, not a scientifically different fit.
        np.testing.assert_allclose(prediction[public], parameters[exported], rtol=1e-12, atol=1e-12,
                                   err_msg='Full-refit/public inference differs from scored '+exported)


def verify_training(evidence, run, cfg, approval, cohorts, choice):
    from . import conditional_mdn_s5_e3_numerics as numerical_geometry
    from .conditional_mdn_s5_e3_formal_training import _CORE_FILES
    base, prov = run['results']/'formal_v1', run['provenance']/'formal_v1'
    sources = evidence.json(prov/'training_sources/hashes.json')
    require(set(sources) == set(_CORE_FILES), 'Training source freeze omits required dependencies')
    evidence.mapping(sources)
    evidence.mapping(sources, prov/'training_sources')
    evidence.file(Path(__file__).with_name('conditional_mdn_s5_e3_inference.py'))
    access = evidence.json(run['provenance']/'endpoint_access_freeze.json')
    counts = {}
    seen_checkpoints = set()
    for role in ROLES:
        fit, query = cohorts[role]['fit'], cohorts[role]['query']
        x = fit[['lon', 'lat']].to_numpy(np.float64)
        # These are this role's authorized fit-pool endpoints, never validation
        # labels or locked final-test files. No optimization or fitting occurs.
        endpoints = inp.endpoints(cfg, run, role, fit, 'fit')
        y = numerical_geometry.to_vectors(x, endpoints)
        opt_ids, stop_ids = partition_reference(fit.id)
        require(access[role]['optimization_ids'] == opt_ids and access[role]['stop_ids'] == stop_ids,
                'Frozen early-stop ID partition differs')
        identity = evidence.json(prov/role/'training_identity.json')
        selection_hash = evidence.hashes.get((base/'selection.json').relative_to(ROOT).as_posix()) if role == 'C_outer' else None
        close(identity, dict(stage='formal_training_v1', schema_version=1, role=role,
            contract_sha256=cfg['contract_sha256'], source_hashes=sources,
            fit_key_sha256=inp.key_digest(fit), query_key_sha256=inp.key_digest(query),
            fit_origins_sha256=array_digest(x), query_origins_sha256=array_digest(query[['lon', 'lat']].to_numpy(np.float64)),
            fit_pairs=len(fit), fit_ids=int(fit.id.nunique()), optimization_ids=opt_ids, stop_ids=stop_ids,
            selection_sha256=selection_hash,
            input_source_hashes={path: digest for path, digest in approval['protected_files'].items()
                if Path(path).name in ('training_coordinates.parquet', 'query_coordinates.parquet', 'roles.parquet')}),
            role+'.training_identity')
        forecast = evidence.json(prov/role/'forecast_freeze.json')
        close(forecast, dict(status='complete', role=role, identity=identity, query_count=len(query),
            query_id_count=int(query.id.nunique()), query_key_sha256=inp.key_digest(query),
            selected_k=choice['selected_k'] if role == 'C_outer' else None,
            selection_sha256=selection_hash, outer_targets_read=False, final_test_access=False), role+'.freeze')
        require(set(forecast['models']) == set(map(str, KS)), 'Forecast freeze requires all six models')
        close(evidence.json(prov/role/'training_status.json'), dict(status='complete', role=role), role+'.status')
        close(evidence.json(prov/role/'training_access.json'),
              dict(outer_targets_read=False, denied=[], final_test_access=False), role+'.access')
        for k in KS:
            folder = base/role/f'K{k}'
            freeze_model = forecast['models'][str(k)]
            close(freeze_model, dict(manifest=(folder/'manifest.json').relative_to(base).as_posix(),
                  parameters=(folder/'parameters.npz').relative_to(base).as_posix()), role+'.model_paths')
            manifest = evidence.json(folder/'manifest.json', freeze_model['manifest_sha256'])
            close(manifest, dict(status='complete', role=role, k=k, identity=identity,
                query_count=len(query), query_id_count=int(query.id.nunique()), query_key_sha256=inp.key_digest(query),
                parameter_count=4352+390*k, outer_targets_read=False, final_test_access=False), 'model.manifest')
            training_path = evidence.artifact(base, manifest['training_receipt'])
            require(training_path == folder/'training_receipt.json', 'Training receipt path differs')
            receipt = evidence.json(training_path)
            close(receipt, dict(role=role, k=k, requires_pause=False), 'training.receipt')
            require([seed['base_seed'] for seed in receipt['seeds']] == list(SEEDS), 'Missing or extra training seed')
            require(receipt['seeds'] == manifest['seeds'] and receipt['full_refit'] == manifest['full_refit'],
                    'Manifest/receipt fit records differ')
            for record in receipt['seeds']:
                steps = verify_fit_record(record, identity, k, fit, x, y)
                checkpoint = verify_checkpoint(evidence, base, record, steps)
                require(checkpoint == folder/f'seed_{record["base_seed"]}'/'checkpoint.pt', 'Seed checkpoint path differs')
                require(checkpoint not in seen_checkpoints, 'Reused checkpoint across formal fits')
                seen_checkpoints.add(checkpoint)
            selected = min(receipt['seeds'], key=lambda record: (record['best_nll'], record['base_seed']))
            require(not (selected['status'] == 'epoch_cap_reached' and selected['best_epoch'] > 470),
                    'Selected seed requires the contracted cap pause')
            for record in (receipt, manifest, evidence.json(folder/'seed_selection.json')):
                close(record, dict(selected_seed=selected['base_seed'], selected_epoch=selected['best_epoch']), 'seed.choice')
            refit = receipt['full_refit']
            require(isinstance(refit, dict), 'Missing fresh complete-pool refit')
            steps = verify_fit_record(refit, identity, k, fit, x, y, selected)
            checkpoint = verify_checkpoint(evidence, base, refit, steps)
            require(checkpoint == folder/'full_refit/checkpoint.pt' and checkpoint not in seen_checkpoints,
                    'Full refit does not have a distinct checkpoint')
            seen_checkpoints.add(checkpoint)
            parameter_path = evidence.artifact(base, manifest['parameters'])
            require(parameter_path == folder/'parameters.npz'
                    and manifest['parameters']['sha256'] == freeze_model['parameters_sha256'],
                    'Prediction archive identity differs')
            # This validator checks all frozen keys, dtypes, finite parameters,
            # complete probabilities, symmetry, and the standardized floor.
            from .conditional_mdn_s5_e3_formal_scoring import load_parameters
            parameters = load_parameters(parameter_path, query, k)
            np.testing.assert_allclose(parameters['target_scale'], refit['standardizer']['y_std'], rtol=0, atol=0)
            verify_refit_forecasts(checkpoint, query, parameters)
        counts[role] = dict(models=6, early_stop_fits=18, full_refits=6,
            fit_pairs=len(fit), fit_ids=int(fit.id.nunique()), stop_ids=len(stop_ids),
            query_count=len(query), query_ids=int(query.id.nunique()),
            public_inference_verified_forecasts=len(query)*len(KS))
    require(len(seen_checkpoints) == 72, 'Not all 72 formal fits have distinct checkpoints')
    return dict(roles=counts, distinct_checkpoints=72,
        fresh_refit_evidence='Frozen source plus separate purpose/path, full-pool scaler, exact epochs and optimizer steps.')


def read_score_stage(evidence, run, query, role, mode, n, m, ks):
    from .conditional_mdn_s5_e3_formal_context import validate_stream_integrity
    from .conditional_mdn_s5_e3_formal_scoring import _source_hashes
    base, prov = run['results']/'formal_v1', run['provenance']/'formal_v1'
    folder = base/role/mode/f'N{n}_M{m}'
    freeze_path = prov/role/mode/f'inputs_N{n}_M{m}.json'
    freeze = evidence.json(freeze_path)
    receipt = evidence.json(folder/'complete.json')
    for record in (freeze, receipt):
        close(record, dict(status='complete', role=role, mode=mode, k_values=list(ks), count=n,
            region_count=m, query_count=len(query), query_id_count=int(query.id.nunique()),
            query_key_sha256=inp.key_digest(query), excluded_queries=0, final_test_access=False), 'score.identity')
    require(freeze['target_values_accessed'] is False, 'Targets were read before scoring freeze')
    require(receipt['identity_sha256'] == freeze['identity_sha256'], 'Scoring receipt belongs to another freeze')
    forecast_path = prov/role/'forecast_freeze.json'
    validate_stream_integrity(freeze, forecast_path, query, role, mode, ks, n, m)
    require(freeze['source_hashes'] == _source_hashes(), 'Scoring source freeze omits required dependencies')
    evidence.file(forecast_path, freeze['forecast_freeze_sha256'])
    evidence.mapping(freeze['source_hashes'])
    if n != 65536 or m != 65536:
        upgrade = evidence.json(prov/f'precision_upgrade_N{n}_M{m}.json', freeze['precision_upgrade_sha256'])
        close(upgrade, dict(status='approved', global_checks_complete=True, count=n, region_count=m), 'precision.upgrade')
        require(upgrade['previous_count'] in LEVELS and upgrade['previous_region_count'] in LEVELS
                and n >= upgrade['previous_count'] and m >= upgrade['previous_region_count'], 'Invalid precision upgrade')
    for k in ks:
        path = base/freeze['parameter_paths'][str(k)]
        evidence.file(path, freeze['parameter_hashes'][str(k)])
        evidence.file(path.parent/'manifest.json', freeze['parameter_manifest_hashes'][str(k)])
    release = evidence.json(prov/role/mode/f'target_release_N{n}_M{m}.json')
    close(release, dict(status='complete', query_count=len(query), query_key_sha256=inp.key_digest(query),
        forecast_sha256=file_sha256(forecast_path), scoring_freeze_sha256=file_sha256(freeze_path),
        final_test_access=False, denied=[]), 'score.release')
    require(release['outer_targets_read'] == (role == 'C_outer'), 'Target release role differs')
    table = pd.read_parquet(evidence.file(folder/'scores.parquet', receipt['scores_sha256']))
    require(receipt['row_count'] == len(table) == len(query)*len(ks), 'Incomplete scoring row count')
    verify_roster(table, {role: query}, ks)
    require(table.energy_count.eq(n).all() and table.region_count.eq(m).all(), 'Per-query precision changed')
    require(table.excluded.eq(False).all(), 'Missing or true excluded-query flag')
    require((table.model == 'MDN'+table.K.astype(str)).all(), 'Model label differs from candidate')
    return table


def verify_historical_forecasts(evidence, baseline_run, files):
    """Bind report bundles to the historical pre-outcome forecast freeze."""
    base = evidence.root/'results/runs'/baseline_run
    provenance = evidence.root/'provenance/runs'/baseline_run
    forecast_path, config_path = provenance/'forecast_freeze.json', provenance/'run.json'
    for path in (forecast_path, config_path):
        require(path.relative_to(evidence.root).as_posix() in files,
                'Historical freeze omits forecast or configuration evidence')
    forecast = evidence.json(forecast_path, files[forecast_path.relative_to(evidence.root).as_posix()])
    close(forecast, dict(role='C_outer', cases=33971, outer_targets_read=False), 'historical.forecast')
    configuration = evidence.json(config_path, files[config_path.relative_to(evidence.root).as_posix()])
    batch_size = configuration['config']['batch_size']
    require(isinstance(batch_size, int) and not isinstance(batch_size, bool) and batch_size > 0,
            'Invalid historical forecast batch size')
    outputs = forecast['output_sha256']
    require(isinstance(outputs, dict) and bool(outputs), 'Missing historical forecast output hashes')
    artifact_paths = []
    for kind, suffix in (('parameters', '.json.gz'), ('lineage', '.npz'), ('regions', '.json.gz')):
        paths = sorted((base/'C_outer'/kind).glob('*'+suffix))
        require(bool(paths), 'Historical freeze omits '+kind+' bundles')
        artifact_paths.extend(paths)
    required = {path.relative_to(evidence.root).as_posix() for path in artifact_paths}
    require(set(outputs) == required, 'Historical freeze omits or adds forecast bundles')
    require(all(files.get(path) == digest for path, digest in outputs.items()),
            'Historical control receipt omits frozen forecast bundle hashes')
    evidence.mapping(outputs)
    return dict(forecast_freeze_sha256=file_sha256(forecast_path),
                forecast_bundle_count=len(outputs), config_sha256=file_sha256(config_path))


def historical_controls(evidence, run, cfg, query):
    receipt = evidence.json(run['provenance']/'formal_v1/control_sources.json')
    require(receipt['baseline_run'] == cfg['baseline_run'], 'Historical control run differs')
    evidence.mapping(receipt['files'])
    forecasts = verify_historical_forecasts(evidence, cfg['baseline_run'], receipt['files'])
    base = ROOT/'results/runs'/cfg['baseline_run']
    historic_path = ROOT/'provenance/runs'/cfg['baseline_run']/'full_audit.json'
    historic = evidence.json(historic_path)
    close(historic, dict(passed=True, final_test_access=False, complete_cases=33971, ids=45), 'historical.audit')
    require(all(historic['models'][model]['passed'] is True for model in CONTROLS), 'Historical control audit failed')
    paths = {label: sorted((base/'C_outer'/label).glob('*.parquet')) for label in ('score', 'audit')}
    required = [base/'model_manifest.json', historic_path, *paths['score'], *paths['audit']]
    require(all(path.relative_to(ROOT).as_posix() in receipt['files'] for path in required)
            and all(paths.values()), 'Historical freeze omits required control evidence')
    tables = {}
    for label in ('score', 'audit'):
        frame = pd.concat([pd.read_parquet(evidence.file(path)) for path in paths[label]], ignore_index=True)
        frame = frame[frame.model.isin(CONTROLS)].rename(columns={'query_position': 'position'})
        tables[label] = frame
    main = tables['score'].rename(columns={'area_replica_km2': 'replica_area90_km2'})
    audit = tables['audit']
    # Historical audit tables carry source position/ID; their primary table
    # additionally supplies all three source-key fields.
    verify_roster(main, {'C_outer': query}, CONTROLS, 'model')
    keys = ['role', 'position', 'id', 'model']
    fields = ['energy_km', 'variance', 'h90', 'area90_km2', 'hit_disagreement']
    joined = main.merge(audit[keys+fields].rename(columns={field: 'audit_'+field for field in fields}),
                        on=keys, how='outer', validate='one_to_one', indicator=True)
    require(joined._merge.eq('both').all(), 'Incomplete historical primary/audit match')
    return joined.drop(columns=['_merge', 'replicate_means']), dict(run=cfg['baseline_run'], passed=True,
        audit_sha256=file_sha256(historic_path), reused_models=list(CONTROLS), query_count=len(query), **forecasts)


def audit(run_name):
    """Verify completed artifacts; write a failure receipt and re-raise on error."""
    require(Path(run_name).name == run_name and run_name.startswith('conditional_mdn_s5_e3_'), 'Invalid MDN run name')
    run = {part: ROOT/(part+'/runs')/run_name for part in ('results', 'provenance')}
    base, prov = run['results']/'formal_v1', run['provenance']/'formal_v1'
    output = prov/'final_audit.json'
    evidence, guard = Evidence(), None
    checks = {}
    try:
        # Establish completion before reading even a saved validation score.
        calculation = evidence.json(prov/'calculation_complete.json')
        close(calculation, dict(status='complete', final_test_access=False), 'calculation.complete')
        _, run, cfg, approval, guard = inp.context(run_name)
        from .conditional_mdn_s5_e3_formal_context import authorization
        authorization(run, cfg)
        evidence.file(prov/'authorization.json')
        evidence.file(run['provenance']/'run.json')
        evidence.file(run['provenance']/'approval.json')
        evidence.mapping(approval['protected_files'])
        evidence.file(ROOT/cfg['contract'], cfg['contract_sha256'])
        require(cfg['no_final_test'] is True and cfg['candidates'] == list(KS)
                and cfg['initialization_seeds'] == list(SEEDS), 'Approved candidate/access config differs')
        evidence.mapping(evidence.json(prov/'analysis_sources.json'))
        cohorts = inp.cohorts(cfg)
        require(len(set(cohorts['C_T0']['query'].id)|set(cohorts['C_T1']['query'].id)) == 104,
                'Pooled inner roster is not 104 distinct IDs')
        choice = evidence.json(base/'selection.json')
        require(choice['status'] == 'complete' and choice['selected_k'] in KS
                and choice['provisional_k'] in KS, 'Missing completed registered selection')
        evidence.mapping(choice['selection_inputs_sha256'])
        close(choice, dict(source_run_name=run_name, contract_sha256=cfg['contract_sha256']), 'selection.identity')
        checks['training'] = verify_training(evidence, run, cfg, approval, cohorts, choice)
        n, m = choice['energy_count'], choice['region_count']
        require(n in LEVELS and m in LEVELS, 'Unregistered inner precision')
        inner = pd.concat([read_score_stage(evidence, run, cohorts[role]['query'], role,
                    'inner_energy', n, 65536, KS) for role in ROLES[:2]], ignore_index=True)
        regions = None
        if choice['provisional_k'] > 1:
            regions = pd.concat([read_score_stage(evidence, run, cohorts[role]['query'], role,
                'inner_regions', n, m, tuple(sorted((1, choice['provisional_k'])))) for role in ROLES[:2]], ignore_index=True)
        reconstructed = reference_selection(inner, regions)
        close(choice, reconstructed, 'independent.selection')
        provisional = evidence.json(base/'provisional_selection.json')
        close(provisional, {key: value for key, value in reconstructed.items()
                            if key not in ('selected_k', 'quality_gate')}, 'provisional.selection')
        compare_frames(pd.read_parquet(evidence.file(base/'inner_energy.parquet')), inner,
                       ['role', 'position', 'K'], 'inner consolidated energy')
        if regions is not None:
            compare_frames(pd.read_parquet(evidence.file(base/'inner_regions.parquet')), regions,
                           ['role', 'position', 'K'], 'inner consolidated regions')
        checks['selection'] = reconstructed
        acceptance = evidence.json(base/'acceptance.json')
        n, m = acceptance['energy_count'], acceptance['region_count']
        require(n in LEVELS and m in LEVELS, 'Unregistered outer precision')
        query = cohorts['C_outer']['query']
        main = read_score_stage(evidence, run, query, 'C_outer', 'outer_score', n, m, KS)
        audit_scores = read_score_stage(evidence, run, query, 'C_outer', 'outer_audit', n, m, KS)
        keys = ['role', 'position', 'id', 'K']
        columns = [field for field in audit_scores if field.startswith(('audit_', 'es_audit_', 'iid_'))]
        mdn = main.merge(audit_scores[keys+columns], on=keys, how='outer', validate='one_to_one', indicator=True)
        require(mdn._merge.eq('both').all(), 'Incomplete outer primary/audit match')
        mdn = mdn.drop(columns='_merge')
        checks['full_numerical'] = verify_full_numerical(mdn)
        checks['independent_iid'] = verify_iid(mdn, len(query))
        controls, checks['controls'] = historical_controls(evidence, run, cfg, query)
        table = pd.concat([mdn, controls], ignore_index=True)
        verify_roster(table, {'C_outer': query}, MODELS, 'model')
        summary, per_id, comparisons, expected_acceptance = reference_outer(table, reconstructed['selected_k'])
        close(acceptance, expected_acceptance, 'independent.acceptance')
        close(calculation['acceptance'], acceptance, 'calculation.acceptance')
        compare_frames(pd.read_csv(evidence.file(base/'summary.csv')), summary.reset_index(), ['model'], 'summary')
        compare_frames(pd.read_csv(evidence.file(base/'per_id.csv')), per_id, ['id', 'model'], 'per_id')
        compare_frames(pd.read_csv(evidence.file(base/'comparisons.csv')), comparisons, ['model', 'baseline'], 'comparisons')
        consolidated = table.drop(columns=[field for field in table if field.endswith('region_json')])
        compare_frames(pd.read_parquet(evidence.file(base/'outer_complete.parquet')), consolidated,
                       ['model', 'position'], 'outer consolidated table')
        checks['outer'] = expected_acceptance
        # Rehash everything at the end to catch concurrent or late mutation.
        evidence.mapping(dict(evidence.hashes))
        require(not guard.denied and not guard.outer_read, 'Audit read an unexpected target or protected input')
        result = dict(schema_version=1, status='complete', passed=True, run_name=run_name,
            final_test_access=False, outer_validation_target_values_read_by_final_audit=False,
            training_endpoints_read_for_scaler_audit=True,
            checks=checks, evidence_sha256=dict(sorted(evidence.hashes.items())),
            audit_source_sha256=file_sha256(Path(__file__)),
            scope='Full saved training and all-query score evidence; independent aggregation/selection/intervals; fixed IID subset.')
        atomic_json(output, result)
        return result
    except BaseException as error:
        atomic_json(output, dict(schema_version=1, status='failed', passed=False, run_name=run_name,
            final_test_access=False, error_type=type(error).__name__, reason=str(error),
            traceback=traceback.format_exc(), completed_checks=list(checks),
            denied=[] if guard is None else guard.denied,
            evidence_sha256=dict(sorted(evidence.hashes.items())), audit_source_sha256=file_sha256(Path(__file__))))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_name')
    result = audit(parser.parse_args().run_name)
    print(json.dumps({key: result[key] for key in ('status', 'passed', 'run_name', 'final_test_access')}), flush=True)


if __name__ == '__main__':
    main()
