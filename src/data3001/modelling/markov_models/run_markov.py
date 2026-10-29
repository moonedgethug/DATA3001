"""Guarded fixed-one-day M1 preparation and outer-ID validation.

python -B -m data3001.modelling.markov_models.run_markov --prepare-only --pilot
python -B -m data3001.modelling.markov_models.run_markov --prepare-only
python -B -m data3001.modelling.markov_models.run_markov --input-run <full_preparation_run>
"""
import argparse
from datetime import datetime, timezone
import json
from importlib.metadata import version
from pathlib import Path
import resource
import sys
import time

import numpy as np
import pandas as pd
from scipy.sparse import save_npz

from data3001.dataset import manifest, track_path
from data3001.modelling.baselines.cv import fit_baselines, probability_region
from data3001.modelling.common.experiment import make_nested_folds, fold_digest
from data3001.modelling.markov_models.markov import fit_operator, forecast
from data3001.modelling.markov_models.markov_inputs import collect_inputs
from data3001.modelling.common.markov_scoring import SpatialScorer, score_distribution
from data3001.modelling.common.runtime import ReadOnlyInputs, save_frame, save_json
from data3001.modelling.baselines.run_neighbourhood import _identity, scientific_environment
from data3001.modelling.common.runtime import _source_hashes, _seal, verified_run
from data3001.paths import project_paths, file_sha256

MODELS = ('B0', 'B1', 'B2', 'M1')
CONFIG_PATH = Path('configs/markov_m1.json')


def forecast_table(predictions):
    """Export every distribution, including an explicit unresolved-state row."""
    rows = []
    for fold, mapping in predictions.items():
        for (h, origin, model), (p, u) in mapping.items():
            if -3 in p:
                raise ValueError('Unresolved mass must be separate from physical probabilities')
            score_distribution(p, -1, unresolved=u)
            mass = dict(p)
            if u > 0:
                mass[-3] = u
            for destination, probability in mass.items():
                rows.append((fold, h, origin, model, destination, probability, u))
    return pd.DataFrame(rows, columns=[
        'outer_fold', 'horizon_days', 'origin_cell_1', 'model',
        'destination_cell_1', 'probability', 'unresolved_mass'])


def score_forecast(group, p, u, model, outer_fold, scorer, wet_areas=None):
    """Shared unchanged categorical and conditional spatial score calculation."""
    blank = score_distribution(p, -1, unresolved=u)
    region = probability_region(p, u)
    physical = {c: v for c, v in p.items() if c >= 0}
    geo_region = probability_region(physical, u + p.get(-2, 0.))
    spatial = scorer.prepare(p, unresolved=u)
    frame = group.copy()
    true = frame.destination_cell_1.map(p).fillna(0.).to_numpy()
    frame['outer_fold'], frame['model'] = outer_fold, model
    frame['true_probability'], frame['unresolved_mass'] = true, u
    frame['outside_probability'] = p.get(-2, 0.)
    frame['complete'] = u == 0
    frame['brier_failure_penalized'] = blank['brier_failure_penalized'] - 2*true
    frame['brier'] = blank['brier'] - 2*true
    with np.errstate(divide='ignore'):
        frame['log_loss_upper'] = -np.log(true)
        frame['log_loss_lower'] = -np.log(true+u)
    frame['log_loss'] = frame.log_loss_upper if u == 0 else np.nan
    frame['region90_available'] = region['available']
    frame['region90_hit'] = frame.destination_cell_1.isin(region['states'])
    frame['region90_mass'], frame['region90_cells'] = region['mass'], region['cells']
    frame['geo90_available'] = geo_region['available']
    frame['geo90_hit'] = frame.destination_cell_1.isin(geo_region['states'])
    frame['geo90_mass'], frame['geo90_cells'] = geo_region['mass'], geo_region['cells']
    frame['geo90_wet_area_km2'] = (sum(wet_areas[c] for c in geo_region['states'])
                                   if geo_region['available'] and wet_areas is not None else np.nan)
    spatial_rows = pd.DataFrame([spatial(int(y)) for y in frame.destination_cell_1], index=frame.index)
    frame = pd.concat([frame, spatial_rows], axis=1)
    return frame


def tag_common(scores, models):
    keys = ['outer_fold', 'id', 'horizon_days', 'origin_cell_1', 'destination_cell_1']
    grouped = scores.groupby(keys)
    if (scores.duplicated(keys + ['model']).any()
            or not grouped.model.nunique().eq(len(models)).all()
            or set(scores.model) != set(models)
            or not grouped.pair_count.nunique().eq(1).all()):
        raise ValueError('Models do not share identical held-out cases and weights')
    scores['spatial_status_complete'] = scores.spatial_status.eq('complete_in_domain')
    scores['spatial_common'] = scores.spatial_status_complete.groupby([scores[k] for k in keys]).transform('all')
    scores['complete_common'] = scores.complete.groupby([scores[k] for k in keys]).transform('all')
    return scores


def evaluate_fold(counts, releases, fitting_ids, evaluation_ids, state_cells, scorer, *, outer_fold, wet_areas=None):
    fitting_ids, evaluation_ids = set(fitting_ids), set(evaluation_ids)
    if fitting_ids & evaluation_ids:
        raise ValueError('Fitting and held-out instruments overlap')
    op = fit_operator(counts, fitting_ids, state_cells, 1)
    controls = fit_baselines(releases, fitting_ids)
    held = releases.loc[releases.id.isin(evaluation_ids)]
    if held.empty:
        raise ValueError('No eligible held-out R cases; do not silently change folds')
    frames, predictions = [], {}
    for (h, origin), group in held.groupby(['horizon_days', 'origin_cell_1'], sort=True):
        h, origin = int(h), int(origin)
        b1, b2 = controls['B1'].get(h), controls['B2'].get((h, origin))
        m1 = forecast(op, origin, h)
        variants = {'B0': ({origin: 1.}, 0.), 'B1': (b1 or {}, 0. if b1 else 1.),
                    'B2': (b2 or {}, 0. if b2 else 1.), 'M1': m1}
        for model, (p, u) in variants.items():
            predictions[(h, origin, model)] = (p, u)
            frames.append(score_forecast(group, p, u, model, outer_fold, scorer, wet_areas))
    scores = pd.concat(frames, ignore_index=True)
    scores = tag_common(scores, MODELS)
    train = releases.loc[releases.id.isin(fitting_ids)]
    support = train.groupby(['horizon_days', 'origin_cell_1'], as_index=False).agg(
        pair_count=('pair_count', 'sum'), independent_ids=('id', 'nunique'))
    support['outer_fold'] = outer_fold
    return {'scores': scores, 'operator': op, 'forecasts': predictions, 'support': support}


def summarize(scores):
    rows = []
    for (h, model), g in scores.groupby(['horizon_days', 'model'], sort=True):
        w = g.pair_count.to_numpy(float)
        def avg(column, mask=None):
            mask = np.ones(len(g), bool) if mask is None else np.asarray(mask, bool)
            return float(np.average(g.loc[mask, column].to_numpy(float), weights=w[mask])) if mask.any() else np.nan
        complete = g.complete.to_numpy(bool)
        spatial = g.spatial_common.to_numpy(bool)
        row = {'horizon_days': int(h), 'model': model, 'eligible_pairs': int(w.sum()),
               'independent_ids': int(g.id.nunique()),
               'complete_forecast_pct': 100*float(w[complete].sum()/w.sum()),
               'mean_unresolved_mass': avg('unresolved_mass'), 'max_unresolved_mass': float(g.unresolved_mass.max()),
               'mean_outside_probability': avg('outside_probability'),
               'observed_outside_pairs': int(w[g.destination_cell_1.eq(-2)].sum()),
               'zero_probability_pct': 100*float(w[g.true_probability.eq(0)].sum()/w.sum()),
               'brier': avg('brier') if complete.all() else np.nan,
               'brier_common_complete': avg('brier', g.complete_common),
               'brier_failure_penalized': avg('brier_failure_penalized'),
               'log_loss': avg('log_loss') if complete.all() else np.nan,
               'log_loss_lower': avg('log_loss_lower'), 'log_loss_upper': avg('log_loss_upper'),
               'region90_available_pct': 100*avg('region90_available'),
               'region90_hit_pct_all_cases': 100*avg('region90_hit'),
               'region90_hit_pct_available': 100*avg('region90_hit', g.region90_available),
               'mean_region90_mass': avg('region90_mass', g.region90_available),
               'mean_region90_cells': avg('region90_cells', g.region90_available),
               'geo90_available_pct': 100*avg('geo90_available'),
               'geo90_hit_pct_available': 100*avg('geo90_hit', g.geo90_available),
               'mean_geo90_mass': avg('geo90_mass', g.geo90_available),
               'mean_geo90_wet_area_km2': avg('geo90_wet_area_km2', g.geo90_available),
               'spatial_individual_available_pct': 100*avg('spatial_status_complete'),
               'spatial_common_pairs': int(w[spatial].sum())}
        for c in ('energy_km', 'mean_squared_km2', 'linear_quadratic_reference'):
            row[c+'_common'] = avg(c, spatial)
        rows.append(row)
    return pd.DataFrame(rows)


def paired_intervals(scores, replicates=200, comparisons=None):
    rows = []
    for h, g in scores.groupby('horizon_days'):
        part = g.assign(total_loss=g.pair_count*g.brier_failure_penalized).groupby(
            ['outer_fold', 'id', 'model'], as_index=False).agg(loss=('total_loss', 'sum'), n=('pair_count', 'sum'))
        loss = part.pivot(index=['outer_fold', 'id'], columns='model', values='loss')
        ns = part.pivot(index=['outer_fold', 'id'], columns='model', values='n')
        if not ns.eq(ns.B2, axis=0).all().all() or loss.isna().any().any():
            raise ValueError('Unmatched bootstrap cases')
        n = ns.B2.to_numpy(float)
        rng = np.random.default_rng(20261004 + int(h))
        folds = [np.flatnonzero(loss.index.get_level_values(0) == f)
                 for f in sorted(loss.index.get_level_values(0).unique())]
        draws = [np.concatenate([rng.choice(ix, len(ix), replace=True) for ix in folds]) for _ in range(replicates)]
        for a, b in (comparisons or [('M1', 'B2'), ('M1', 'B1'), ('B2', 'B1')]):
            delta = (loss[a]-loss[b]).to_numpy()
            estimates = np.array([delta[ix].sum()/n[ix].sum() for ix in draws])
            low, high = np.quantile(estimates, [.025, .975])
            rows.append({'horizon_days': int(h), 'comparison': a+' minus '+b,
                         'delta_S': delta.sum()/n.sum(), 'lower_95': low, 'upper_95': high,
                         'replicates': replicates, 'scope': 'conditional_on_fixed_outer_fits'})
    return pd.DataFrame(rows)


def configuration(paths):
    config = json.loads((paths.root/CONFIG_PATH).read_text())
    if (config['lag_days'] != 1 or config['destination_prior_epsilon'] != 0
            or config['target'] != 'stopped' or config['scenario'] != 'pooled'
            or config['final_test_access'] is not False or config['horizons_days'] != [7, 30]
            or config['predictors'] != ['origin_cell_1'] or config['tolerance_hours'] != 0):
        raise ValueError('Configuration exceeds the fixed prototype scope')
    return config


def identity(paths):
    data, bound = _identity(paths)
    for k in ('state_index', 'land_mask_intermediate'):
        p = paths.asset(k, verify=True)
        bound[p.relative_to(paths.root).as_posix()] = file_sha256(p)
    bound[CONFIG_PATH.as_posix()] = file_sha256(paths.root/CONFIG_PATH)
    return data, bound


def environment():
    info = scientific_environment()
    info['packages']['scipy'] = version('scipy')
    info['numeric_workers'] = 1
    return info


def prepare(paths, *, pilot=False):
    config = configuration(paths)
    data, bound = identity(paths)
    ids = sorted(int(sid) for sid, record in data['records'].items() if record['pool'] == 'train')
    if pilot:
        index = pd.read_csv(paths.asset('current_dataset_index', verify=True))
        r = set(index.loc[index.in_R.eq(True), 'id'].astype(int))
        ids = sorted([i for i in ids if i in r][:10] + [i for i in ids if i not in r][:10])
    run_id = datetime.now(timezone.utc).strftime(('markov_pilot_' if pilot else 'markov_input_')+'%Y%m%dT%H%M%S_%fZ')
    sources = _source_hashes(paths)
    run = paths.create_run(run_id, {**config, 'pilot': pilot, 'development_IDs': ids,
                                    'input_sha256': bound, 'source_sha256': sources})
    guard = ReadOnlyInputs(paths.root, run, data_root=paths.data_root)
    sys.addaudithook(guard)
    try:
        summary = collect_inputs(paths, run, ids)
        if guard.read_ids != set(ids):
            raise ValueError('Canonical read population mismatch')
        for sid in ids:
            track_path(sid, allow_test=False)
        verify_bound(paths, bound, sources)
        summary.update(pilot=pilot, final_test_trajectories_read=0, canonical_changed=False,
                       max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       environment=environment(), denied_operations=guard.denied)
        _seal(paths, run, summary)
        print('PREPARED_INPUT_RUN='+run_id, flush=True)
        print(json.dumps({k:v for k,v in summary.items() if k not in ('environment',)}, indent=2), flush=True)
    except Exception as e:
        save_json(paths, run['provenance']/'FAILED.json', {'error': repr(e), 'completed': False})
        raise
    finally:
        guard.active = False


def verify_bound(paths, bound, sources):
    for relative, checksum in {**bound, **sources}.items():
        if file_sha256(paths.root/relative) != checksum:
            raise ValueError('An input/source changed during the run: '+relative)


def evaluate(paths, input_run):
    config = configuration(paths)
    data, bound = identity(paths)
    receipt = verified_run(paths, input_run)
    parent = json.loads((receipt.parent/'run.json').read_text())['config']
    expected = {int(sid) for sid, record in data['records'].items() if record['pool'] == 'train'}
    if parent.get('pilot') is not False or set(parent['development_IDs']) != expected:
        raise ValueError('Only the full development input may enter formal evaluation')
    for relative, checksum in parent['input_sha256'].items():
        if file_sha256(paths.root/relative) != checksum:
            raise ValueError('Prepared input identity changed: '+relative)
    bound[receipt.relative_to(paths.root).as_posix()] = file_sha256(receipt)
    sources = _source_hashes(paths)
    run_id = datetime.now(timezone.utc).strftime('markov_m1_1d_%Y%m%dT%H%M%S_%fZ')
    run = paths.create_run(run_id, {**config, 'input_run': input_run, 'input_sha256': bound, 'source_sha256': sources})
    guard = ReadOnlyInputs(paths.root, run, data_root=paths.data_root)
    sys.addaudithook(guard)
    start = time.monotonic()
    try:
        inputs = paths.root/'results/runs'/input_run
        counts = pd.read_parquet(inputs/'transition_counts_by_id.parquet')
        releases = pd.read_parquet(inputs/'release_counts_by_id.parquet')
        if not set(counts.id).issubset(expected) or not set(releases.id).issubset(expected):
            raise ValueError('Non-development ID in input counts')
        index = pd.read_parquet(paths.asset('state_index', verify=True))
        index = index.loc[index.resolution.eq(1)].sort_values('cell')
        cells = index.cell.astype(int).tolist()
        wet_areas = dict(zip(cells, index.wet_area_in_D.to_numpy(float)))
        scorer = SpatialScorer(cells, scale_km=config['auxiliary_spatial']['scale_km'])
        outer, inner = make_nested_folds(sorted(expected))
        save_frame(paths, run['results']/'folds.csv', pd.DataFrame(sorted(outer.items()), columns=['id', 'outer_fold']))
        score_parts, support_parts, predictions = [], [], {}
        for fold in range(5):
            held = {sid for sid, f in outer.items() if f == fold}
            result = evaluate_fold(counts, releases, expected-held, held, cells, scorer,
                                   outer_fold=fold, wet_areas=wet_areas)
            result['scores']['spatial_status_complete'] = result['scores'].spatial_status.eq('complete_in_domain')
            score_parts.append(result['scores'])
            support_parts.append(result['support'])
            predictions[fold] = result['forecasts']
            operator = result['operator']
            paths.publish(run['results']/f'operators/outer_{fold}.npz', lambda stream: save_npz(stream, operator.matrix))
            save_json(paths, run['results']/f'operators/outer_{fold}.json', {
                'cell_ids': cells, 'special_states': [-2, -3], 'lag_days': 1,
                'training_ids': sorted(operator.training_ids),
                'supported_geographic_rows': int((operator.row_pair_counts[:-2] > 0).sum())})
            print(f'Outer fold {fold+1}/5 complete; {len(result["scores"])} score groups', flush=True)
        scores = pd.concat(score_parts, ignore_index=True)
        summary = summarize(scores)
        support = pd.concat(support_parts, ignore_index=True)
        intervals = paired_intervals(scores, config['bootstrap_replicates'])
        for name, table in [('scores.parquet', scores), ('summary.csv', summary),
                            ('training_R_support.csv', support), ('paired_intervals.csv', intervals)]:
            save_frame(paths, run['results']/name, table)
        save_frame(paths, run['results']/'forecasts.parquet', forecast_table(predictions))
        from data3001.modelling.markov_models.markov_report import write_report
        write_report(paths, run, summary, intervals, scores, predictions, support, releases, outer, inputs)
        verify_bound(paths, bound, sources)
        _seal(paths, run, {'completed_folds': 5, 'fold_digest': fold_digest(outer, inner),
                           'fixed_configuration_no_hyperparameter_selection': True,
                           'final_test_trajectories_read': 0, 'canonical_tracks_read_in_evaluation': len(guard.read_ids),
                           'denied_operations': guard.denied, 'elapsed_seconds': time.monotonic()-start,
                           'max_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                           'environment': environment()})
        print('\n'+summary[['horizon_days', 'model', 'eligible_pairs', 'independent_ids',
                              'brier_failure_penalized', 'mean_unresolved_mass', 'spatial_common_pairs']].to_string(index=False))
        print('RESULTS_RUN='+run_id, flush=True)
    except Exception as e:
        save_json(paths, run['provenance']/'FAILED.json', {'error': repr(e), 'completed': False})
        raise
    finally:
        guard.active = False


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--input-run')
    args = parser.parse_args()
    if args.prepare_only and not args.input_run:
        prepare(project_paths(), pilot=args.pilot)
    elif args.input_run and not args.prepare_only and not args.pilot:
        evaluate(project_paths(), args.input_run)
    else:
        parser.error('Choose preparation (optionally pilot) or a full input run')


if __name__ == '__main__':
    main()
