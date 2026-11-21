"""Fixed-cohort diagnostics and whole-ID nested lag selection; no file access."""
import numpy as np
import pandas as pd

from data3001.modelling.baselines.cv import fit_baselines
from data3001.modelling.common.probability import score_distribution
from data3001.modelling.markov_models.markov import fit_operator, forecast
from data3001.modelling.common.markov_scoring import cell_coordinates_km
from data3001.modelling.markov_models.run_markov import score_forecast, tag_common

LAGS = (1, 3, 5, 7)
KERNELS = (1, 2, 3, 5, 7)
CASE_KEYS = ['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1']


def fit_kernels(counts, fitting_ids, cells, durations=KERNELS):
    return {h: fit_operator(counts.loc[counts.horizon_days.eq(h)], fitting_ids, cells, h)
            for h in durations}


def forecast_lag(kernels, origin, horizon, lag):
    r = int(horizon) % int(lag)
    if lag not in kernels or (r and r not in kernels):
        raise ValueError('Missing exact lag/remainder kernel')
    return forecast(kernels[lag], int(origin), int(horizon), kernels[r] if r else None)


def candidate_scores(kernels, releases, evaluation_ids):
    fitting = next(iter(kernels.values())).training_ids
    if fitting & set(evaluation_ids):
        raise ValueError('Fitting and held-out IDs overlap')
    held = releases.loc[releases.id.isin(evaluation_ids)]
    parts = []
    for (h, origin), group in held.groupby(['horizon_days', 'origin_cell_1']):
        for lag in LAGS:
            p, u = forecast_lag(kernels, origin, h, lag)
            blank = score_distribution(p, -1, unresolved=u)
            g = group.copy()
            g['lag_days'], g['unresolved_mass'] = lag, u
            g['brier_failure_penalized'] = blank['brier_failure_penalized'] - 2*g.destination_cell_1.map(p).fillna(0.)
            parts.append(g)
    if not parts:
        raise ValueError('No held-out cases; do not change folds')
    return pd.concat(parts, ignore_index=True)


def choose_lags(scores):
    choices = {}
    for h, part in scores.groupby('horizon_days'):
        if set(part.lag_days) != set(LAGS):
            raise ValueError('Missing lag candidate')
        reference = None
        means = {}
        for lag, g in part.groupby('lag_days'):
            keys = g.set_index(CASE_KEYS).pair_count.sort_index()
            if keys.index.has_duplicates or not np.isfinite(g.brier_failure_penalized).all():
                raise ValueError('Duplicate or unscored selection cases')
            if reference is not None:
                pd.testing.assert_series_equal(reference, keys)
            reference = keys
            means[int(lag)] = float(np.average(g.brier_failure_penalized, weights=g.pair_count))
        best = min(means.values())
        choices[int(h)] = min(k for k, v in means.items() if v <= best + 1e-12)
    if not choices:
        raise ValueError('No selection support')
    return choices


def score_outer(kernels, releases, fitting_ids, evaluation_ids, outer_fold, scorer,
                *, lags=LAGS, selected=None, wet_areas=None):
    if set(fitting_ids) & set(evaluation_ids):
        raise ValueError('Outer ID overlap')
    controls = fit_baselines(releases, fitting_ids)
    parts, predictions = [], {}
    held = releases.loc[releases.id.isin(evaluation_ids)]
    for (h, origin), group in held.groupby(['horizon_days', 'origin_cell_1']):
        h, origin = int(h), int(origin)
        b1, b2 = controls['B1'].get(h), controls['B2'].get((h, origin))
        variants = {'B0': ({origin: 1.}, 0., 0), 'B1': (b1 or {}, 0. if b1 else 1., 0),
                    'B2': (b2 or {}, 0. if b2 else 1., 0)}
        for lag in lags:
            p, u = forecast_lag(kernels, origin, h, lag)
            variants[f'M1-{lag}d'] = (p, u, lag)
        if selected is not None:
            variants['M1-selected'] = variants[f'M1-{selected[h]}d']
        for model, (p, u, lag) in variants.items():
            predictions[(h, origin, model)] = (p, u)
            frame = score_forecast(group, p, u, model, outer_fold, scorer, wet_areas)
            frame['lag_days'] = lag
            parts.append(frame)
    if not parts:
        raise ValueError('No outer held-out support')
    models = ['B0', 'B1', 'B2'] + [f'M1-{lag}d' for lag in lags] + (['M1-selected'] if selected is not None else [])
    return tag_common(pd.concat(parts, ignore_index=True), models), predictions


def nested_evaluate(counts, releases, cells, outer, inner, scorer, *, wet_areas=None, progress=print):
    parts, inner_parts, choices, records, predictions, outer_operators = [], [], [], [], {}, {}
    ids = set(outer)
    for fold in sorted(set(outer.values())):
        held = {i for i in ids if outer[i] == fold}
        fitting = ids-held
        if set(inner[fold]) != fitting:
            raise ValueError('Inner fold map does not equal outer fitting population')
        tuning = []
        for j in sorted(set(inner[fold].values())):
            validation = {i for i in fitting if inner[fold][i] == j}
            train = fitting-validation
            kernels = fit_kernels(counts, train, cells)
            result = candidate_scores(kernels, releases, validation)
            result['outer_fold'], result['inner_fold'] = fold, j
            tuning.append(result)
            records.append({'role': 'inner', 'outer_fold': fold, 'inner_fold': j,
                            'fitting_ids': sorted(train), 'evaluation_ids': sorted(validation)})
        tuning = pd.concat(tuning, ignore_index=True)
        selected = choose_lags(tuning)
        inner_parts.append(tuning)
        choices.extend({'outer_fold': fold, 'horizon_days': h, 'lag_days': lag} for h, lag in selected.items())
        kernels = fit_kernels(counts, fitting, cells)
        scores, prediction = score_outer(kernels, releases, fitting, held, fold, scorer,
                                         selected=selected, wet_areas=wet_areas)
        parts.append(scores)
        predictions[fold], outer_operators[fold] = prediction, kernels
        records.append({'role': 'outer', 'outer_fold': fold,
                        'fitting_ids': sorted(fitting), 'evaluation_ids': sorted(held)})
        progress(f'Lag CV outer {fold+1}/{len(set(outer.values()))}; selected {selected}', flush=True)
    return {'scores': pd.concat(parts, ignore_index=True), 'inner_scores': pd.concat(inner_parts, ignore_index=True),
            'choices': pd.DataFrame(choices), 'fit_records': records,
            'predictions': predictions, 'operators': outer_operators}


def distribution_diagnostics(predictions, observed, outer):
    """Descriptive known-geographic-mass conditioning; not a formal score."""
    rows = []
    for fold, mapping in predictions.items():
        for (h, origin, model), (p, u) in mapping.items():
            obs = observed.loc[observed.id.map(outer).eq(fold) & observed.horizon_days.eq(h)
                               & observed.origin_cell_1.eq(origin)]
            truth = obs.loc[obs.destination_cell_1.ge(0)].groupby('destination_cell_1').pair_count.sum()
            physical = {c: v for c, v in p.items() if c >= 0 and v > 0}
            mass = sum(physical.values())
            row = {'outer_fold': fold, 'horizon_days': h, 'origin_cell_1': origin, 'model': model,
                   'pair_count': int(obs.pair_count.sum()), 'independent_ids': obs.id.nunique(),
                   'known_geographic_mass': mass, 'unresolved_mass': u, 'outside_probability': p.get(-2, 0.),
                   'centre_bias_km': np.nan, 'predicted_RMS_km': np.nan, 'observed_RMS_km': np.nan,
                   'positive_cells': len(physical), 'mass_per_cell_below_0_0001': sum(v for v in physical.values() if v < .0001)}
            if mass > 0 and truth.sum() > 0:
                q = np.array(list(physical.values()))/mass
                xyz = cell_coordinates_km(list(physical))
                mean = q @ xyz
                oq = truth.to_numpy()/truth.sum()
                oxy = cell_coordinates_km(truth.index)
                omean = oq @ oxy
                row.update(centre_bias_km=float(np.linalg.norm(mean-omean)),
                           predicted_RMS_km=float(np.sqrt(q@np.sum((xyz-mean)**2, axis=1))),
                           observed_RMS_km=float(np.sqrt(oq@np.sum((oxy-omean)**2, axis=1))))
            rows.append(row)
    return pd.DataFrame(rows)


def controlled_evaluate(counts, cells, outer):
    """Exploratory matched-three-day phase versus pooled composition."""
    parts, discrepancies = [], []
    for fold in sorted(set(outer.values())):
        held = {i for i, f in outer.items() if f == fold}
        fitting = set(outer)-held
        train = counts.loc[counts.population.eq('D') & counts.origin_cell_1.ge(0)]
        # A phase can contain only E-origin rows. Its empty geographic table
        # still needs an operator with E/U absorbers and unsupported -> U.
        ops = {kind: fit_operator(train.loc[train.kind.eq(kind)], fitting, cells, lag)
               for kind, lag in [('step0', 1), ('step1', 1), ('step2', 1), ('direct2', 2), ('direct3', 3)]}
        pooled = train.loc[train.kind.str.startswith('step')]
        pooled = fit_operator(pooled, fitting, cells, 1)
        for h in (2, 3):
            held_counts = counts.loc[counts.population.eq('R') & counts.kind.eq(f'direct{h}') & counts.id.isin(held)]
            for origin, group in held_counts.groupby('origin_cell_1'):
                direct = forecast(ops[f'direct{h}'], int(origin), h)
                phase = np.zeros(len(cells)+2); phase[ops['step0'].cells.index(int(origin))] = 1.
                for k in range(h):
                    phase = ops[f'step{k}'].matrix.T @ phase
                phase = np.minimum(phase, 1.)
                phase_p = ({c: float(phase[j]) for j, c in enumerate(ops['step0'].cells + (-2,)) if phase[j] > 0}, float(phase[-1]))
                variants = {'Direct': direct, 'Phase-composed': phase_p, 'Pooled-composed': forecast(pooled, int(origin), h)}
                for name, (p, u) in variants.items():
                    g = group[CASE_KEYS+['pair_count']].copy()
                    blank = score_distribution(p, -1, unresolved=u)
                    g['outer_fold'], g['model'], g['unresolved_mass'] = fold, name, u
                    g['brier_failure_penalized'] = blank['brier_failure_penalized']-2*g.destination_cell_1.map(p).fillna(0.)
                    parts.append(g)
                    if name != 'Direct':
                        states = set(p) | set(direct[0])
                        tv = .5*(sum(abs(p.get(c, 0.)-direct[0].get(c, 0.)) for c in states)+abs(u-direct[1]))
                        discrepancies.append({'outer_fold': fold, 'horizon_days': h, 'origin_cell_1': int(origin),
                                              'model': name, 'total_variation_from_direct': tv,
                                              'pair_count': int(group.pair_count.sum()), 'unresolved_mass': u,
                                              'direct_unresolved_mass': direct[1]})
    return pd.concat(parts, ignore_index=True), pd.DataFrame(discrepancies)
