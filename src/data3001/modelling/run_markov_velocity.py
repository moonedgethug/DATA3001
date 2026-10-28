"""Guarded preparation, pilot and nested M1vcat comparison. Never reads test.

python -B -m data3001.modelling.run_markov_velocity --prepare-only [--pilot]
python -B -m data3001.modelling.run_markov_velocity --input-run RUN [--benchmark]
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
import pandas as pd
from scipy.sparse import save_npz

from data3001.dataset import track_path
from data3001.modelling.cv import fit_baselines
from data3001.modelling.experiment import make_nested_folds, fold_digest
from data3001.modelling.markov_diagnostics import fit_kernels as fit_plain_kernels, forecast_lag
from data3001.modelling.markov_velocity import fit_joint_operator, BINS
from data3001.modelling.markov_velocity_inputs import collect_velocity_inputs, KERNELS
from data3001.modelling.markov_velocity_cv import (
    release_counts, predict_locations, score_candidates, choose_parameters, tag_velocity_common, CASE_KEYS,
)
from data3001.modelling.run_blend_cv import ReadOnlyInputs, save_frame, save_json
from data3001.modelling.run_markov import identity, environment, verify_bound, summarize, paired_intervals, score_forecast
from data3001.modelling.run_markov_diagnostics import state
from data3001.modelling.run_neighbourhood import verified_run, _source_hashes, _seal
from data3001.paths import project_paths, file_sha256

CONFIG = Path('configs/markov_m1_vcat.json')
MODELS = ['B0', 'B1', 'B2', 'M1-selected', 'M1vcat-raw', 'M1vcat-selected']


def validate_settings(c):
    if (c['predictors'] != ['origin_cell_1', 've', 'vn'] or c['velocity_classes'] != 9
            or c['primary_metric'] != 'brier_failure_penalized' or c['target'] != 'stopped'
            or c['scenario'] != 'pooled' or c['departure_seasons'] != 'annual_pooled'
            or c['grid_degrees'] != 1 or c['candidate_lags'] != [1, 3, 5, 7]
            or c['kernel_days'] != [1, 2, 3, 5, 7] or c['lambda_grid'] != [k/10 for k in range(11)]
            or c['evaluation_days'] != [7, 30] or c['final_test_access'] is not False
            or c['tolerance_hours'] != 0 or c['weighting'] != 'equal_eligible_pairs'
            or c['tie_choice'] != 'shorter_lag_then_larger_lambda' or c['tie_tolerance'] != 1e-12
            or c['initial_velocity'] != 'observed_at_origin_only'
            or c['conditional_row_backoff'] != 'cell_pooled_joint_law'):
        raise ValueError('Settings exceed the approved M1vcat experiment')
    return c


def settings(paths): return validate_settings(json.loads((paths.root/CONFIG).read_text()))


def start(paths, kind, c, extra, receipts):
    data, bound = identity(paths)
    if data['version'] != c['dataset_release'] or bound.get('docs/contract/data_contract_v1.0.xlsx') != c['contract_sha256']:
        raise ValueError('Dataset or contract changed')
    bound[CONFIG.as_posix()] = file_sha256(paths.root/CONFIG)
    for path in receipts: bound[path.relative_to(paths.root).as_posix()] = file_sha256(path)
    sources = _source_hashes(paths)
    name = datetime.now(timezone.utc).strftime(kind+'_%Y%m%dT%H%M%S_%fZ')
    run = paths.create_run(name, {**c, **extra, 'input_sha256': bound, 'source_sha256': sources})
    guard = ReadOnlyInputs(paths.root, run, data_root=paths.data_root); sys.addaudithook(guard)
    return data, bound, sources, run, guard


def finish(paths, run, bound, sources, guard, record):
    verify_bound(paths, bound, sources)
    if guard.denied: raise ValueError('Input guard was triggered')
    record.update(canonical_tracks_read=len(guard.read_ids), final_test_trajectories_read=0,
                  canonical_changed=False, denied_operations=guard.denied,
                  max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, environment=environment())
    _seal(paths, run, record)
    print('COMPLETED_RUN='+run['results'].name, flush=True)
    print(json.dumps({k: v for k, v in record.items() if k != 'environment'}, indent=2), flush=True)


def prepare(paths, pilot=False):
    c = settings(paths); receipt = verified_run(paths, c['input_parent']); data, _ = identity(paths)
    all_ids = sorted(int(i) for i, r in data['records'].items() if r['pool'] == 'train')
    outer, inner = make_nested_folds(all_ids); ids = all_ids
    if pilot:
        ix = pd.read_csv(paths.asset('current_dataset_index', verify=True)); visiting = set(ix.loc[ix.in_R.eq(True), 'id'])
        ids = sorted([i for i in all_ids if i in visiting][:10]+[i for i in all_ids if i not in visiting][:10])
    _, bound, sources, run, guard = start(paths, 'markov_vcat_pilot' if pilot else 'markov_vcat_input', c,
           {'pilot': pilot, 'development_IDs': ids, 'fold_digest': fold_digest(outer, inner)}, (receipt,))
    try:
        result = collect_velocity_inputs(paths, run, ids, paths.root/'results/runs'/c['input_parent'], outer, inner)
        if guard.read_ids != set(ids): raise ValueError('Canonical read population mismatch')
        for i in ids: track_path(i, allow_test=False)
        finish(paths, run, bound, sources, guard, {**result, 'pilot': pilot})
    except Exception as e:
        save_json(paths, run['provenance']/'FAILED.json', {'error': repr(e)}); raise
    finally: guard.active = False


def load_inputs(paths, name, allow_pilot=False):
    receipt = verified_run(paths, name)
    parent = json.loads((receipt.parent/'run.json').read_text())['config']
    data, _ = identity(paths)
    all_ids = {int(i) for i, r in data['records'].items() if r['pool'] == 'train'}
    ids = set(parent['development_IDs'])
    if not ids <= all_ids or (not allow_pilot and (parent.get('pilot') is not False or ids != all_ids)):
        raise ValueError('Full development cache required outside the engineering pilot')
    for rel, sha in parent['input_sha256'].items():
        if file_sha256(paths.root/rel) != sha: raise ValueError('Cache input changed: '+rel)
    root = paths.root/'results/runs'/name
    counts = pd.read_parquet(root/'transition_counts_by_id.parquet')
    release = pd.read_parquet(root/'release_counts_by_id.parquet')
    th = json.loads((root/'thresholds.json').read_text())
    plain = pd.read_parquet(paths.root/'results/runs'/parent['input_parent']/'transition_counts_by_id.parquet')
    plain = plain.loc[plain.id.isin(ids)]
    if any(not set(t.id) <= ids for t in (counts, release, plain)): raise ValueError('Nondevelopment cached ID')
    outer, inner = make_nested_folds(sorted(all_ids))
    if parent['fold_digest'] != fold_digest(outer, inner): raise ValueError('Fold map changed')
    return ids, counts, release, th, plain, outer, inner, receipt


def context(counts, releases, th, plain, cells, role, fitting_ids):
    record = th['roles'][role]
    if set(record['fitting_ids']) != set(fitting_ids): raise ValueError('Threshold fitting IDs differ')
    m = record['threshold_m_s']
    kernels = {h: fit_joint_operator(counts, fitting_ids, cells, th['cutpoints'], m, h) for h in KERNELS}
    ordinary = fit_plain_kernels(plain, fitting_ids, cells)
    r = release_counts(releases, th['cutpoints'], m)
    return kernels, ordinary, r


def check_degeneration(kernels, ordinary, releases, held):
    part = releases.loc[releases.id.isin(held)]
    origins = sorted(set(zip(part.origin_cell_1.astype(int), part.origin_velocity_bin.astype(int))))
    maximum = 0.
    for lag in [1, 3, 5, 7]:
        forecasts = predict_locations(kernels, origins, [7, 30], lag, 1.)
        for h, rows in forecasts.items():
            for (cell, _), (p, u) in zip(origins, rows):
                old, u0 = forecast_lag(ordinary, cell, h, lag)
                difference = max([abs(u-u0)]+[abs(p.get(k, 0.)-old.get(k, 0.)) for k in set(p)|set(old)])
                maximum = max(maximum, difference)
        for op in kernels.values(): op.clear_cache()
    if maximum > 1e-12: raise ValueError('Lambda=1 did not restore the old M1')
    return maximum


def benchmark(paths, name):
    c = settings(paths); ids, counts, release, th, plain, outer, inner, receipt = load_inputs(paths, name, True)
    _, bound, sources, run, guard = start(paths, 'markov_vcat_benchmark', c, {'input_run': name}, (receipt,))
    begun = time.monotonic()
    try:
        cells, _, _ = state(paths); held = {i for i in ids if outer[i] == 0}; fit = ids-held
        kernels, ordinary, r = context(counts, release, th, plain, cells, 'outer_0', fit)
        err = check_degeneration(kernels, ordinary, r, held)
        stats = score_candidates(kernels, ordinary, r, held, progress=print)
        save_frame(paths, run['results']/'candidate_scores.csv', stats)
        finish(paths, run, bound, sources, guard, {'elapsed_seconds': time.monotonic()-begun,
               'lambda_one_max_error': err, 'candidate_rows': len(stats), 'scope': 'engineering_profile_not_formal_model_selection'})
    except Exception as e:
        save_json(paths, run['provenance']/'FAILED.json', {'error': repr(e)}); raise
    finally: guard.active = False


def save_components(paths, run, kernels, prefix):
    for lag, op in kernels.items():
        name = f'operators/{prefix}_{lag}d'
        for key, matrix in [('local', op.local), ('pooled', op.pooled)]:
            paths.publish(run['results']/f'{name}_{key}.npz', lambda stream, matrix=matrix: save_npz(stream, matrix))
        save_json(paths, run['results']/f'{name}.json', {'lag_days': lag, 'cells': list(op.cells),
                  'velocity_bins': BINS, 'threshold_m_s': op.threshold, 'cache_cuts': list(op.cuts),
                  'training_ids': sorted(op.training_ids), 'special_states': [-2, -3],
                  'supported_joint_rows': int((op.row_pairs[:-2] > 0).sum())})
        support = pd.DataFrame({'origin_cell_1': np.repeat(op.cells, BINS), 'origin_velocity_bin': np.tile(np.arange(BINS), len(op.cells)),
                  'pair_count': op.row_pairs[:-2].astype('int64'), 'independent_ids': op.row_ids[:-2],
                  'dominant_ID_share': op.dominant_id_share[:-2]})
        save_frame(paths, run['results']/f'{name}_support.parquet', support)


def score_outer(kernels, ordinary, releases, fitting, held, choices, fold, scorer, wet):
    controls = fit_baselines(releases.groupby(['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1'], as_index=False).pair_count.sum(), fitting)
    part = releases.loc[releases.id.isin(held)]
    origins = sorted(set(zip(part.origin_cell_1.astype(int), part.origin_velocity_bin.astype(int))))
    pos = {key: i for i, key in enumerate(origins)}; predicted = {}
    for model in ['M1vcat-raw', 'M1vcat-selected']:
        for h, (lag, lam) in choices[model].items():
            values = predict_locations(kernels, origins, [h], lag, lam)[h]
            for origin, value in zip(origins, values): predicted[(h, *origin, model)] = value
            for op in kernels.values(): op.clear_cache()
    frames = []
    for (h, cell, b), g in part.groupby(['horizon_days', 'origin_cell_1', 'origin_velocity_bin']):
        h, cell, b = int(h), int(cell), int(b)
        b1 = controls['B1'].get(h); b2 = controls['B2'].get((h, cell))
        variants = {'B0': ({cell: 1.}, 0.), 'B1': (b1 or {}, 0. if b1 else 1.),
                    'B2': (b2 or {}, 0. if b2 else 1.),
                    'M1-selected': forecast_lag(ordinary, cell, h, choices['M1-selected'][h][0])}
        variants.update({m: predicted[(h, cell, b, m)] for m in ['M1vcat-raw', 'M1vcat-selected']})
        for model, (p, u) in variants.items():
            predicted[(h, cell, b, model)] = (p, u)
            frame = score_forecast(g, p, u, model, fold, scorer, wet)
            lag, lam = choices.get(model, {}).get(h, (0, np.nan))
            frame['lag_days'], frame['lambda_value'] = lag, lam
            frames.append(frame)
    return tag_velocity_common(pd.concat(frames, ignore_index=True), MODELS), predicted


def prediction_frame(mapping, fold):
    rows = []
    for (h, c, b, model), (p, u) in mapping.items():
        values = dict(p)
        if u > 0: values[-3] = u
        rows.extend((fold, h, c, b, model, y, v, u) for y, v in values.items())
    return pd.DataFrame(rows, columns=['outer_fold', 'horizon_days', 'origin_cell_1',
               'origin_velocity_bin', 'model', 'destination_cell_1', 'probability', 'unresolved_mass'])


def make_example(kernels, ordinary, releases, fitting, held, choices, mapping):
    support = releases.loc[releases.id.isin(fitting) & releases.horizon_days.eq(7)].groupby(
        ['origin_cell_1', 'origin_velocity_bin']).pair_count.sum().sort_values(ascending=False)
    cell, b = (int(v) for v in support.index[0]); panels = {}
    controls = fit_baselines(releases, fitting)
    for h in [7, 30]:
        group = releases.loc[releases.id.isin(held) & releases.horizon_days.eq(h)
                             & releases.origin_cell_1.eq(cell) & releases.origin_velocity_bin.eq(b)]
        selected = mapping.get((h, cell, b, 'M1vcat-selected'))
        if selected is None:
            lag, lam = choices['M1vcat-selected'][h]
            selected = predict_locations(kernels, [(cell, b)], [h], lag, lam)[h][0]
        p, u = selected; lag, lam = choices['M1vcat-selected'][h]
        old, ou = forecast_lag(ordinary, cell, h, choices['M1-selected'][h][0])
        reference = controls['B2'].get((h, cell)); observed = group.groupby('destination_cell_1').pair_count.sum(); n = int(observed.sum())
        panels[h] = [('B2 reference', reference or {}, 0. if reference else 1.), ('M1-selected', old, ou),
                     (f'M1vcat (lag {lag}, lambda {lam:.1f})', p, u),
                     (f'Observed: {n} pairs / {group.id.nunique()} IDs' if n else 'Observed unavailable',
                      {int(c): float(w/n) for c, w in observed.items()} if n else {}, 0.)]
    return {'origin': cell, 'velocity_bin': b, 'threshold': kernels[1].threshold, 'panels': panels}


def evaluate(paths, name):
    c = settings(paths); ids, counts, release, th, plain, outer, inner, receipt = load_inputs(paths, name)
    reference = verified_run(paths, c['comparison_parent'])
    _, bound, sources, run, guard = start(paths, 'markov_vcat_cv', c, {'input_run': name}, (receipt, reference))
    begun = time.monotonic()
    try:
        cells, wet, scorer = state(paths)
        stat_parts, choice_rows, score_parts, roles = [], [], [], []
        max_degeneration = 0.; example = None
        old_choices = pd.read_csv(paths.root/'results/runs'/c['comparison_parent']/'selected_lags.csv')
        for fold in range(5):
            held = {i for i in ids if outer[i] == fold}; fitting = ids-held; inner_parts = []
            for j in range(4):
                val = {i for i in fitting if inner[fold][i] == j}; train = fitting-val
                print(f'Outer {fold+1}/5, inner {j+1}/4: fitting joint kernels', flush=True)
                kernels, ordinary, r = context(counts, release, th, plain, cells, f'inner_{fold}_{j}', train)
                stats = score_candidates(kernels, ordinary, r, val, progress=print)
                stats['outer_fold'], stats['inner_fold'], stats['role'] = fold, j, 'inner'
                save_frame(paths, run['results']/f'inner/outer_{fold}_inner_{j}.csv', stats)
                inner_parts.append(stats); roles.append({'role': 'inner', 'outer_fold': fold, 'inner_fold': j,
                                                        'fitting_ids': sorted(train), 'evaluation_ids': sorted(val)})
            tuning = pd.concat(inner_parts, ignore_index=True)
            choices = {'M1vcat-selected': choose_parameters(tuning),
                       'M1vcat-raw': choose_parameters(tuning, 0.),
                       'M1-selected': choose_parameters(tuning, 1.)}
            for h, (lag, _) in choices['M1-selected'].items():
                expected = int(old_choices.loc[old_choices.outer_fold.eq(fold) & old_choices.horizon_days.eq(h), 'lag_days'].iloc[0])
                if lag != expected: raise ValueError('Old M1 inner lag choice not reproduced')
            for model, by_h in choices.items():
                choice_rows.extend({'outer_fold': fold, 'model': model, 'horizon_days': h,
                                    'lag_days': lag, 'lambda_value': lam} for h, (lag, lam) in by_h.items())
            kernels, ordinary, r = context(counts, release, th, plain, cells, f'outer_{fold}', fitting)
            maximum = check_degeneration(kernels, ordinary, r, held); max_degeneration = max(maximum, max_degeneration)
            print(f'Outer {fold+1}/5: lambda=1 audit error {maximum:.3g}; outer candidates', flush=True)
            stats = score_candidates(kernels, ordinary, r, held, progress=print)
            stats['outer_fold'], stats['role'] = fold, 'outer'; stat_parts.append(stats)
            save_frame(paths, run['results']/f'outer_{fold}_candidate_scores.csv', stats)
            scores, mapping = score_outer(kernels, ordinary, r, fitting, held, choices, fold, scorer, wet)
            save_frame(paths, run['results']/f'outer_{fold}_scores.parquet', scores)
            save_frame(paths, run['results']/f'outer_{fold}_forecasts.parquet', prediction_frame(mapping, fold))
            save_components(paths, run, kernels, f'outer_{fold}')
            score_parts.append(scores)
            if fold == 0: example = make_example(kernels, ordinary, r, fitting, held, choices, mapping)
            roles.append({'role': 'outer', 'outer_fold': fold, 'fitting_ids': sorted(fitting), 'evaluation_ids': sorted(held)})
            print(f'Outer {fold+1}/5 completed; choices {choices}; elapsed {time.monotonic()-begun:.1f}s', flush=True)
        scores = pd.concat(score_parts, ignore_index=True); summary = summarize(scores)
        old = pd.read_csv(paths.root/'results/runs'/c['comparison_parent']/'summary.csv')
        for model in ['B0', 'B1', 'B2', 'M1-selected']:
            fresh = summary.loc[summary.model.eq(model)].sort_values('horizon_days')
            ref = old.loc[old.model.eq(model)].sort_values('horizon_days')
            np.testing.assert_array_equal(fresh.eligible_pairs, ref.eligible_pairs)
            np.testing.assert_allclose(fresh.brier_failure_penalized, ref.brier_failure_penalized, rtol=0, atol=1e-12)
        intervals = paired_intervals(scores, c['bootstrap_replicates'],
                    [('M1vcat-selected', 'M1-selected'), ('M1vcat-selected', 'M1vcat-raw'), ('M1vcat-selected', 'B2')])
        choices = pd.DataFrame(choice_rows); outer_stats = pd.concat(stat_parts, ignore_index=True)
        final = choose_parameters(outer_stats)
        kernels, _, _ = context(counts, release, th, plain, cells, 'development', ids)
        save_components(paths, run, kernels, 'development')
        for filename, table in [('summary.csv', summary), ('paired_intervals.csv', intervals),
                                ('selected_parameters.csv', choices), ('outer_candidate_scores.csv', outer_stats),
                                ('scores.parquet', scores)]: save_frame(paths, run['results']/filename, table)
        save_json(paths, run['results']/'development_candidate.json', {'parameters_by_horizon': {str(h): {'lag_days': lag, 'lambda_value': lam} for h, (lag, lam) in final.items()},
                    'threshold_m_s': th['roles']['development']['threshold_m_s'], 'training_ids': sorted(ids),
                    'selection_source': 'fixed_candidate_outer_OOF', 'evaluation_claim': 'refit_not_independently_scored',
                    'state': 'nine_velocity_labels_per_cell_then_E_U'})
        save_json(paths, run['provenance']/'fit_ID_records.json', roles)
        save_json(paths, run['results']/'thresholds.json', th)
        from data3001.modelling.markov_velocity_report import write_velocity_report
        write_velocity_report(paths, run, summary, intervals, choices, final, th['roles']['development']['threshold_m_s'], example)
        finish(paths, run, bound, sources, guard, {'elapsed_seconds': time.monotonic()-begun,
               'completed_outer_folds': 5, 'completed_inner_fits': 20, 'fold_digest': fold_digest(outer, inner),
               'lambda_one_max_error': max_degeneration, 'old_M1_choices_and_scores_reproduced': True,
               'final_parameters': {str(h): [lag, lam] for h, (lag, lam) in final.items()}})
        print(summary[['horizon_days', 'model', 'brier_failure_penalized', 'region90_hit_pct_available', 'mean_region90_cells']].to_string(index=False))
        print(intervals.to_string(index=False))
    except Exception as e:
        save_json(paths, run['provenance']/'FAILED.json', {'error': repr(e)}); raise
    finally: guard.active = False


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--prepare-only', action='store_true'); p.add_argument('--pilot', action='store_true')
    p.add_argument('--input-run'); p.add_argument('--benchmark', action='store_true'); args = p.parse_args()
    paths = project_paths()
    if args.prepare_only and not args.input_run and not args.benchmark: prepare(paths, args.pilot)
    elif args.input_run and not args.prepare_only and not args.pilot:
        (benchmark if args.benchmark else evaluate)(paths, args.input_run)
    else: p.error('Choose preparation/pilot or one input run, optionally an engineering benchmark')


if __name__ == '__main__': main()
