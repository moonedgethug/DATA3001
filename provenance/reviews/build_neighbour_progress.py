"""Read-only, explicitly partial display of one completed neighbour-CV fold."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import numpy as np
import pandas as pd
from shapely import from_wkb
from shapely.geometry import box, mapping

ROOT = Path(__file__).resolve().parents[2]
NAME = 'markov_neighbour_cv_20261028T105824_991491Z'
RUN = ROOT / 'results/runs' / NAME
P = RUN / 'checkpoints/outer_0'
OUT = ROOT / 'results/deliverables/markov_neighbour_progress'
OUT.mkdir(parents=True, exist_ok=True)
sha = lambda p: hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()
record = json.loads((P / 'COMPLETE.json').read_text())
for name, digest in record['files'].items():
    assert sha(P / name) == digest, name
config = json.loads((ROOT / 'provenance/runs' / NAME / 'run.json').read_text())['config']
for key in ['input_sha256', 'source_sha256']:
    for name, digest in config[key].items():
        assert sha(ROOT / name) == digest, name
assert not set(record['role']['fitting_ids']) & set(record['role']['held_ids'])
scores = pd.read_parquet(P / 'scores.parquet')
selected = json.loads((P / 'locked_choices.json').read_text())
payload = {'run': NAME, 'scope': 'Provisional: outer fold 1 of 5 only',
           'snapshot_UTC': datetime.now(timezone.utc).isoformat(),
           'selected': selected, 'horizons': {}}
summaries = []
checked = 0
for h in [7, 30]:
    cases = pd.read_parquet(P / f'H{h}_cases.parquet').sort_values(['id', 'origin_source_obs'])
    assert set(cases.id) <= set(record['role']['held_ids'])
    assert not cases.duplicated(['id', 'origin_source_obs']).any()
    aliases = json.loads((P / f'H{h}_draw_mapping.json').read_text())
    arrays = {name: np.load(P / name, mmap_mode='r') for name in set(aliases.values())}
    local = scores.loc[scores.horizon_days.eq(h)]
    for model in ['self-CV', 'neighbour-CV', 'self-at-neighbour']:
        for repeat in [0, 1]:
            f = local.loc[local.model.eq(model) & local['repeat'].eq(repeat)].sort_values(['id', 'origin_source_obs'])
            assert np.array_equal(f[['id', 'origin_source_obs']].to_numpy(), cases[['id', 'origin_source_obs']].to_numpy())
            draws = arrays[aliases[f'{model}|{repeat}']]
            assert draws.shape == (len(cases), 128)
            for start in range(0, len(cases), 4096):
                d = np.asarray(draws[start:start+4096]); n, m = d.shape
                z = f.iloc[start:start+4096]; truth = z.destination_cell_1.to_numpy()
                assert (((d >= 0) & (d < 64800)) | (d == -2) | (d == -3)).all()
                flat = np.sort(d, axis=1).ravel()
                cut = flat[1:] != flat[:-1]; cut[np.arange(m-1, n*m-1, m)] = True
                edges = np.r_[0, np.flatnonzero(cut)+1, n*m]; counts = np.diff(edges)
                collision = np.bincount(edges[:-1]//m, weights=counts*(counts-1), minlength=n)
                ptrue = (d == truth[:, None]).mean(axis=1)
                expected = {'S_integration': 1-2*ptrue+collision/(m*(m-1)),
                            'U_mass': (d == -3).mean(axis=1), 'E_mass': (d == -2).mean(axis=1),
                            'sampled_zero': ptrue == 0}
                row = edges[:-1]//m; state = flat[edges[:-1]]; physical = state != -3
                hist = np.zeros((n, m+1), dtype=int)
                np.add.at(hist, (row[physical], counts[physical]), 1)
                mass = np.cumsum(hist[:, ::-1]*np.arange(m, -1, -1)[None, :], axis=1)
                threshold = m - np.argmax(mass >= 116, axis=1)
                available = (d != -3).sum(axis=1) >= 116
                hit = available & ((d == truth[:, None]).sum(axis=1) >= threshold)
                keep = physical & (counts >= threshold[row])
                size = np.bincount(row, weights=keep & (state >= 0), minlength=n).astype(float)
                size[~available] = np.nan
                expected.update(region90_available=available, region90_hit=hit, region90_cells=size)
                for key, value in expected.items():
                    np.testing.assert_allclose(value, z[key], rtol=0, atol=4e-12, equal_nan=True)
            checked += len(f)
        g = local.loc[local.model.eq(model)]
        summaries.append({'horizon_days': h, 'model': model, 'eligible_pairs': len(cases),
                          'independent_ids': int(cases.id.nunique()),
                          **{k: float(g[k].mean()) for k in ['S_integration', 'U_mass', 'E_mass',
                            'region90_hit', 'region90_cells', 'region90_available', 'sampled_zero']}})
    cohorts = {}
    for cell, group in cases.groupby('origin_cell_1'):
        mask = cases.origin_cell_1.eq(cell).to_numpy()
        maps = {}
        for model in ['self-CV', 'neighbour-CV', 'observed']:
            if model == 'observed':
                states, counts = np.unique(group.destination_cell_1, return_counts=True)
            else:
                d = np.concatenate([arrays[aliases[f'{model}|{repeat}']][mask].ravel() for repeat in [0, 1]])
                states, counts = np.unique(d, return_counts=True)
            probabilities = counts / counts.sum()
            assert abs(probabilities.sum() - 1) < 1e-12
            maps[model] = [[int(c), float(format(p, '.7g'))] for c, p in zip(states, probabilities)]
        cohorts[str(int(cell))] = {'pairs': len(group), 'IDs': int(group.id.nunique()), 'maps': maps}
    payload['horizons'][str(h)] = {'pairs': len(cases), 'IDs': int(cases.id.nunique()), 'cohorts': cohorts}
summary = pd.DataFrame(summaries)
summary.to_csv(OUT / 'summary_outer_fold_1.csv', index=False)
payload['summary'] = summaries
catalog = json.loads((ROOT / 'configs/assets.json').read_text())['assets']
land_entry = catalog['land_mask_intermediate']; land_file = ROOT / land_entry['path']
assert sha(land_file) == land_entry['sha256']
land = from_wkb(land_file.read_bytes()).intersection(box(-84, 18, -6, 57)).simplify(.08, preserve_topology=True)
payload['coast'] = mapping(land.boundary)
(OUT / 'display_data.json').write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False))

def table(frame):
    cols = list(frame.columns)
    return '\n'.join(['| '+' | '.join(cols)+' |', '| '+' | '.join(['---']*len(cols))+' |'] +
                     ['| '+' | '.join(str(v) if not isinstance(v, float) else f'{v:.8g}' for v in row)+' |'
                      for row in frame.itertuples(index=False, name=None)])

display = summary[['horizon_days', 'model', 'eligible_pairs', 'independent_ids', 'S_integration',
                   'region90_hit', 'region90_cells', 'region90_available', 'U_mass']].copy()
for col in ['region90_hit', 'region90_available', 'U_mass']:
    display[col] *= 100
display.rename(columns={'region90_hit': 'hit90_pct', 'region90_available': 'available90_pct', 'U_mass': 'U_pct'}, inplace=True)
params = pd.DataFrame([{'days': int(h), 'procedure': k, 'path': v['path'],
                       'alpha': v['alpha'], 'lambda': v['lambda_value'],
                       'numerically_unresolved': v['numerically_unresolved']}
                      for h, families in selected.items() for k, v in families.items()])
text = '''# Neighbour Markov experiment: provisional first-fold result

**This is one completed outer fold out of five, not the final experiment result.** Remaining folds are still running. Do not select, stop or change a model using this progress view. The final test is locked. These are adaptively inspected development results.

## Findings supported by this fold

At 7 days, the expanded neighbour search selected alpha=0 and exactly the same path and lambda as the independently tuned no-neighbour control. The issued predictions are identical. This fold provides no realised improvement from neighbour borrowing; it does not prove that neighbouring cells carry no information.

At 30 days, the selected neighbour procedure has a slightly worse held-ID S, slightly lower nominal-90% hit rate, and a slightly larger mean prediction region than the independently tuned self-cell control. The matched-path/lambda control is also retained to separate spatial borrowing from lambda retuning. This fold does not support declaring an improvement. It does not establish a general failure before the full CV and uncertainty analysis finish.

## Held-ID metrics

'''+table(display)+'''

Lower S is better. S is the unchanged augmented-state Brier score, not percentage accuracy. Hit90 is the observed outcome's inclusion rate across all eligible cases; it is not the probability of an arbitrary future forecast being correct. Mean region size is conditional on region availability and counts 1-degree cells, not square kilometres. Larger regions can improve coverage without sharpening predictions. U is unresolved transport mass, not an observed grounding outcome. A finite-particle zero is not proof of a structural zero.

Hourly origins from one drifter are correlated: the independent ID counts are shown, and two simulation repeats do not double the number of observations. All metrics use the same cases for the three procedures within each horizon.

## Inner-selected settings

'''+table(params)+'''

R3 means 1+3+3 days; R7 means 2+7+7+7+7 days. Alpha is the neighbour displacement borrowing weight; lambda is the velocity-category pooling weight. These are fold-specific selections with unresolved numerical near-ties, not unique or universal optimal parameters. Seven-day and thirty-day searches were independent and did not reuse historical winning settings.

## Probability maps

Each release-cell view averages the saved forecasts across that cell's held-out exact positions and initial velocity categories. The observed map uses exactly those same hourly origins. It is a cohort-average illustration, not a forecast from one newly specified point. The default cell is the largest held-out release cohort by count, chosen without looking at model skill; all cells are available. All panels share a fixed logarithmic colour scale for probability per 1-degree cell. E and U remain in the denominator and are listed separately. No mass is renormalised to create a more favourable image. Map probabilities are not continuous density or 90% prediction regions. A cell without an observed endpoint in this finite cohort is not proven impossible.

## Audit boundary

All completed-fold files match their checkpoint hashes. All 115 bound source/input/configuration hashes match. Complete fitting and held-ID rosters are disjoint. S, E/U mass, sampled-zero counts, nominal-90% availability, hits and region size were independently recomputed from the saved 128-particle arrays for each repeat and model alias. Cohort probability mass sums to one before display rounding. No fitting, parameter changes, new predictors or trajectory edits were performed for this report. No final-test trajectory was read. The full five-fold independent audit remains pending.

Source run: `'''+NAME+'''`; source checkpoint: `outer_0`. Display source files and their hashes are recorded in `snapshot_audit.json`.
'''
(OUT / 'REPORT.md').write_text(text)
receipt = {'scope': 'one completed outer fold only; not full experiment audit', 'run': NAME,
           'outer_fold': 0, 'forecast_score_rows_recomputed': checked,
           'checkpoint_hashes_verified': len(record['files']), 'bound_hashes_verified': 115,
           'canonical_modified': False, 'final_test_trajectories_read': 0,
           'source_files': {str((P/k).relative_to(ROOT)): v for k,v in record['files'].items()},
           'display_files': {p.name: sha(p) for p in OUT.iterdir() if p.name in ['REPORT.md', 'display_data.json', 'summary_outer_fold_1.csv']}}
(OUT / 'snapshot_audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(display.to_string(index=False))
print('Independently checked score rows:', checked)
print('Display JSON bytes:', (OUT/'display_data.json').stat().st_size)
