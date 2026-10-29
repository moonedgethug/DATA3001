"""Guarded diagnosis -> bounded nested lag optimisation.

python -B -m data3001.modelling.markov_models.run_markov_diagnostics --prepare-only [--pilot]
python -B -m data3001.modelling.markov_models.run_markov_diagnostics --input-run <full_input>
python -B -m data3001.modelling.markov_models.run_markov_diagnostics --optimise-run <diagnosis>
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
from data3001.modelling.common.experiment import make_nested_folds, fold_digest
from data3001.modelling.markov_models.markov_diagnostic_inputs import collect_diagnostic_inputs
from data3001.modelling.markov_models.markov_diagnostics import LAGS, CASE_KEYS, fit_kernels, choose_lags, score_outer, nested_evaluate, distribution_diagnostics, controlled_evaluate
from data3001.modelling.common.markov_scoring import SpatialScorer
from data3001.modelling.common.runtime import ReadOnlyInputs, save_frame, save_json
from data3001.modelling.markov_models.run_markov import identity, environment, verify_bound, summarize, paired_intervals, forecast_table
from data3001.modelling.common.runtime import verified_run, _source_hashes, _seal
from data3001.paths import project_paths, file_sha256

CONFIG = Path('configs/markov_m1_diagnostics.json')


def settings(paths):
    config = json.loads((paths.root/CONFIG).read_text())
    if (config['candidate_lags'] != [1, 3, 5, 7] or config['kernel_days'] != [1, 2, 3, 5, 7]
            or config['diagnostic_days'] != [1, 2, 3, 5, 7, 30] or config['evaluation_days'] != [7, 30]
            or config['predictors'] != ['origin_cell_1'] or config['final_test_access'] is not False
            or config['scenario'] != 'pooled' or config['target'] != 'stopped' or config['grid_degrees'] != 1
            or config['tolerance_hours'] != 0 or config['destination_prior_epsilon'] != 0
            or config['selection'] != 'independent_per_horizon_inner_OOF_pair_weighted_S'
            or config['tie_tolerance'] != 1e-12 or config['tie_choice'] != 'shortest_lag'):
        raise ValueError('Configuration exceeds approved bounded scope')
    return config


def start(paths, kind, config, extra, receipts=()):
    data, bound = identity(paths)
    bound[CONFIG.as_posix()] = file_sha256(paths.root/CONFIG)
    for receipt in receipts:
        bound[receipt.relative_to(paths.root).as_posix()] = file_sha256(receipt)
    sources = _source_hashes(paths)
    run_id = datetime.now(timezone.utc).strftime(kind+'_%Y%m%dT%H%M%S_%fZ')
    run = paths.create_run(run_id, {**config, **extra, 'input_sha256': bound, 'source_sha256': sources})
    guard = ReadOnlyInputs(paths.root, run, data_root=paths.data_root)
    sys.addaudithook(guard)
    return data, bound, sources, run, guard


def finish(paths, run, bound, sources, guard, record):
    verify_bound(paths, bound, sources)
    if guard.denied:
        raise ValueError('An input protection guard was triggered')
    record.update(final_test_trajectories_read=0, canonical_changed=False,
                  canonical_tracks_read=len(guard.read_ids), denied_operations=guard.denied,
                  max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, environment=environment())
    _seal(paths, run, record)
    print('COMPLETED_RUN='+run['results'].name, flush=True)
    print(json.dumps({k: v for k, v in record.items() if k != 'environment'}, indent=2), flush=True)


def failure(paths, run, error):
    save_json(paths, run['provenance']/'FAILED.json', {'completed': False, 'error': repr(error)})


def prepare(paths, pilot=False):
    config = settings(paths)
    receipt = verified_run(paths, config['input_parent'])
    data, _ = identity(paths)
    ids = sorted(int(i) for i, r in data['records'].items() if r['pool'] == 'train')
    if pilot:
        index = pd.read_csv(paths.asset('current_dataset_index', verify=True))
        visiting = set(index.loc[index.in_R.eq(True), 'id'])
        ids = sorted([i for i in ids if i in visiting][:10]+[i for i in ids if i not in visiting][:10])
    data, bound, sources, run, guard = start(paths, 'markov_diagnostic_pilot' if pilot else 'markov_diagnostic_input',
                                           config, {'pilot': pilot, 'development_IDs': ids}, (receipt,))
    try:
        record = collect_diagnostic_inputs(paths, run, ids, paths.root/'results/runs'/config['input_parent'])
        if guard.read_ids != set(ids):
            raise ValueError('Canonical read population mismatch')
        for sid in ids:
            track_path(sid, allow_test=False)
        finish(paths, run, bound, sources, guard, {**record, 'pilot': pilot})
    except Exception as e:
        failure(paths, run, e)
        raise
    finally:
        guard.active = False


def load_inputs(paths, input_run):
    receipt = verified_run(paths, input_run)
    parent = json.loads((receipt.parent/'run.json').read_text())['config']
    data, _ = identity(paths)
    ids = {int(i) for i, r in data['records'].items() if r['pool'] == 'train'}
    if parent.get('pilot') is not False or set(parent.get('development_IDs', [])) != ids:
        raise ValueError('A full development-only diagnostic cache is required')
    for relative, digest in parent['input_sha256'].items():
        if file_sha256(paths.root/relative) != digest:
            raise ValueError('Diagnostic input identity changed: '+relative)
    root = paths.root/'results/runs'/input_run
    counts = pd.read_parquet(root/'transition_counts_by_id.parquet')
    release = pd.read_parquet(root/'release_counts_by_id.parquet')
    matched = pd.read_parquet(root/'matched_release_counts.parquet')
    controlled = pd.read_parquet(root/'controlled_counts.parquet')
    if any(not set(t.id).issubset(ids) for t in (counts, release, matched, controlled)):
        raise ValueError('Non-development ID in cache')
    return ids, counts, release, matched, controlled, receipt


def state(paths):
    index = pd.read_parquet(paths.asset('state_index', verify=True))
    index = index.loc[index.resolution.eq(1)].sort_values('cell')
    cells = index.cell.astype(int).tolist()
    return cells, dict(zip(cells, index.wet_area_in_D)), SpatialScorer(cells)


def bias_summary(frame):
    rows = []
    for (h, model), g in frame.groupby(['horizon_days', 'model']):
        row = {'horizon_days': h, 'model': model, 'pairs': int(g.pair_count.sum())}
        available = np.isfinite(g.centre_bias_km)
        row['descriptive_available_pairs'] = int(g.loc[available, 'pair_count'].sum())
        row['descriptive_available_pct'] = 100*row['descriptive_available_pairs']/row['pairs']
        for c in ['centre_bias_km', 'predicted_RMS_km', 'observed_RMS_km', 'known_geographic_mass',
                  'unresolved_mass', 'outside_probability', 'positive_cells', 'mass_per_cell_below_0_0001']:
            ok = np.isfinite(g[c])
            row[c] = float(np.average(g.loc[ok, c], weights=g.loc[ok, 'pair_count'])) if ok.any() else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def diagnose(paths, input_run):
    config = settings(paths)
    ids, counts, release, matched, controlled, receipt = load_inputs(paths, input_run)
    data, bound, sources, run, guard = start(paths, 'markov_diagnosis', config, {'input_run': input_run}, (receipt,))
    begun = time.monotonic()
    try:
        cells, wet, scorer = state(paths)
        outer, inner = make_nested_folds(sorted(ids))
        parts, predictions = [], {}
        for fold in range(5):
            held = {i for i, f in outer.items() if f == fold}
            kernels = fit_kernels(counts, ids-held, cells, (1,))
            scores, mapping = score_outer(kernels, matched, ids-held, held, fold, scorer, lags=(1,), wet_areas=wet)
            parts.append(scores); predictions[fold] = mapping
            print(f'Diagnosis outer {fold+1}/5 complete', flush=True)
        scores = pd.concat(parts, ignore_index=True)
        summary = summarize(scores)
        descriptives = distribution_diagnostics(predictions, matched, outer)
        bias = bias_summary(descriptives)
        ck_scores, ck_distances = controlled_evaluate(controlled, cells, outer)
        ck_summary = ck_scores.assign(total_loss=ck_scores.pair_count*ck_scores.brier_failure_penalized).groupby(
            ['horizon_days', 'model'], as_index=False).agg(total_loss=('total_loss', 'sum'), pairs=('pair_count', 'sum'), independent_ids=('id', 'nunique'))
        ck_summary['S'] = ck_summary.total_loss/ck_summary.pairs
        for name, table in [('scores.parquet', scores), ('summary.csv', summary), ('distribution_diagnostics.csv', descriptives),
                            ('bias_summary.csv', bias), ('controlled_scores.parquet', ck_scores),
                            ('controlled_summary.csv', ck_summary), ('controlled_discrepancies.csv', ck_distances),
                            ('forecasts.parquet', forecast_table(predictions))]:
            save_frame(paths, run['results']/name, table)
        from data3001.modelling.markov_models.markov_diagnostic_report import bias_svg
        svg = bias_svg(bias)
        paths.publish(run['results']/'bias_by_horizon.svg', lambda s: s.write(svg.encode()))
        finish(paths, run, bound, sources, guard, {'elapsed_seconds': time.monotonic()-begun,
               'completed_folds': 5, 'fold_digest': fold_digest(outer, inner), 'matched_pairs_per_horizon': int(matched.loc[matched.horizon_days.eq(30)].pair_count.sum()),
               'score_groups': len(scores), 'scope': 'retrospective_matched_cohort_diagnostics_not_lag_selection'})
        print(summary[['horizon_days', 'model', 'eligible_pairs', 'brier_failure_penalized']].to_string(index=False))
        print(bias[['horizon_days', 'model', 'centre_bias_km', 'predicted_RMS_km', 'observed_RMS_km']].to_string(index=False))
        print(ck_summary.to_string(index=False))
    except Exception as e:
        failure(paths, run, e)
        raise
    finally:
        guard.active = False


def save_kernels(paths, run, kernels, prefix):
    for lag, op in kernels.items():
        paths.publish(run['results']/f'operators/{prefix}_{lag}d.npz', lambda s, op=op: save_npz(s, op.matrix))
        save_json(paths, run['results']/f'operators/{prefix}_{lag}d.json', {
            'lag_days': lag, 'cell_ids': list(op.cells), 'special_states': [-2, -3],
            'training_ids': sorted(op.training_ids),
            'supported_geographic_rows': int((op.row_pair_counts[:-2] > 0).sum())})


def optimise(paths, diagnosis_run):
    config = settings(paths)
    diag_receipt = verified_run(paths, diagnosis_run)
    diag_config = json.loads((diag_receipt.parent/'run.json').read_text())['config']
    input_run = diag_config['input_run']
    ids, counts, all_release, matched, controlled, input_receipt = load_inputs(paths, input_run)
    releases = all_release.loc[all_release.horizon_days.isin([7, 30])]
    fixed_receipt = verified_run(paths, config['fixed_parent'])
    data, bound, sources, run, guard = start(paths, 'markov_lag_cv', config,
                                           {'input_run': input_run, 'diagnosis_run': diagnosis_run},
                                           (diag_receipt, input_receipt, fixed_receipt))
    begun = time.monotonic()
    try:
        cells, wet, scorer = state(paths)
        outer, inner = make_nested_folds(sorted(ids))
        result = nested_evaluate(counts, releases, cells, outer, inner, scorer, wet_areas=wet)
        scores = result['scores']
        # The extension must exactly reproduce the original fixed daily model.
        verified_run(paths, config['fixed_parent'])
        old = pd.read_parquet(paths.root/'results/runs'/config['fixed_parent']/'scores.parquet')
        old.model = old.model.replace({'M1': 'M1-1d'})
        keys = ['outer_fold', 'model']+CASE_KEYS
        columns = keys+['pair_count', 'true_probability', 'unresolved_mass', 'brier_failure_penalized']
        fresh = scores.loc[scores.model.isin(old.model.unique()), columns].sort_values(keys).reset_index(drop=True)
        old = old[columns].sort_values(keys).reset_index(drop=True)
        pd.testing.assert_frame_equal(old, fresh, check_exact=False, rtol=1e-12, atol=1e-13)
        summary = summarize(scores)
        intervals = paired_intervals(scores, config['bootstrap_replicates'],
                                     [('M1-selected', 'M1-1d'), ('M1-selected', 'B2'), ('M1-selected', 'B1')])
        for name, table in [('scores.parquet', scores), ('summary.csv', summary), ('inner_scores.parquet', result['inner_scores']),
                            ('selected_lags.csv', result['choices']), ('paired_intervals.csv', intervals),
                            ('forecasts.parquet', forecast_table(result['predictions'])),
                            ('folds.csv', pd.DataFrame(sorted(outer.items()), columns=['id', 'outer_fold']))]:
            save_frame(paths, run['results']/name, table)
        save_json(paths, run['provenance']/'fit_ID_records.json', result['fit_records'])
        for fold, kernels in result['operators'].items():
            save_kernels(paths, run, kernels, f'outer_{fold}')
        final_selection = choose_lags(scores.loc[scores.model.isin([f'M1-{x}d' for x in LAGS])])
        final = fit_kernels(counts, ids, cells)
        save_kernels(paths, run, final, 'development')
        save_json(paths, run['results']/'development_candidate.json', {
            'selected_lag_by_horizon': {str(k): v for k, v in final_selection.items()},
            'selection_source': 'fixed_candidate_outer_OOF_not_final_test',
            'training_ids': sorted(ids), 'evaluation_claim': 'final_refit_not_independently_scored',
            'target': 'stopped', 'scenario': 'pooled', 'grid_degrees': 1,
            'formula': 'e_origin @ P_lag**(h//lag) @ P_remainder_if_needed'})
        descriptive = distribution_diagnostics(result['predictions'], releases, outer)
        save_frame(paths, run['results']/'distribution_diagnostics.csv', descriptive)
        from data3001.modelling.markov_models.markov_diagnostic_report import write_optimisation_report
        write_optimisation_report(paths, run, summary, intervals, result, releases, outer,
                                   paths.root/'results/runs'/diagnosis_run, final_selection)
        finish(paths, run, bound, sources, guard, {'elapsed_seconds': time.monotonic()-begun, 'completed_outer_folds': 5,
               'completed_inner_fits': 20, 'fold_digest': fold_digest(outer, inner), 'fixed_parent_scores_reproduced': True,
               'final_candidate_lags': {str(h): lag for h, lag in final_selection.items()},
               'selection_scope': 'one_predeclared_lag_grid_per_horizon_nested_whole_ID_CV'})
        print(summary[['horizon_days', 'model', 'brier_failure_penalized', 'region90_hit_pct_available', 'mean_region90_cells']].to_string(index=False))
        print(result['choices'].to_string(index=False))
        print(intervals.to_string(index=False))
    except Exception as e:
        failure(paths, run, e)
        raise
    finally:
        guard.active = False


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--prepare-only', action='store_true'); parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--input-run'); parser.add_argument('--optimise-run')
    args = parser.parse_args(); paths = project_paths()
    if args.prepare_only and not args.input_run and not args.optimise_run:
        prepare(paths, args.pilot)
    elif args.input_run and not args.prepare_only and not args.pilot and not args.optimise_run:
        diagnose(paths, args.input_run)
    elif args.optimise_run and not args.prepare_only and not args.pilot and not args.input_run:
        optimise(paths, args.optimise_run)
    else:
        parser.error('Choose input preparation, diagnosis, or optimisation')


if __name__ == '__main__':
    main()
