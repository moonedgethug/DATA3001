#!/usr/bin/env python3
"""Export frozen comparison tables for Part 4; standard-library Python only.

No forecasts, scores, confidence intervals, models or final-test data are computed.
Repeated controls deliberately preserve separate historical evaluation protocols.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=Path('/Users/moonedgethug/Documents/UNSW/DATA3001/work_place'))
parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'dist/assets/pt4')
args = parser.parse_args()
ROOT, OUT = args.root.resolve(), args.output
OUT.mkdir(parents=True, exist_ok=True)
sources = {}


def source(path):
    p = path if isinstance(path, Path) else ROOT / path
    key = p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else '../' + p.relative_to(ROOT.parent).as_posix()
    sources[key] = hashlib.sha256(p.read_bytes()).hexdigest()
    return key


def table(path):
    source(path)
    with (ROOT / path).open() as stream:
        return list(csv.DictReader(stream))


def read_json(path):
    source(path)
    return json.loads((ROOT / path).read_text())


def value(row, *keys):
    for key in keys:
        if row.get(key) not in (None, ''):
            return float(row[key])
    return None


IDS = {'B1': 'b1', 'B2': 'b2', 'Fixed': 'fixed', 'Adaptive': 'adaptive',
       'LocalEndpoint': 'local-endpoint', 'LocalDisplacement': 'local-displacement',
       'Annual': 'annual', 'HardSeason': 'hard-season', 'Adjusted': 'seasonal',
       'B2Point': 'b2-point', 'ExactPoint': 'exact-point', 'EndpointCI': 'endpoint-ci',
       'LocalGaussian': 'local-gaussian', 'LocalGMM': 'local-gmm', 'M1-1d': 'm1-1d'}
LABELS = {'Fixed': 'Fixed blend', 'Adaptive': 'Adaptive blend', 'LocalEndpoint': 'Local endpoint',
          'LocalDisplacement': 'Local displacement', 'Annual': 'Annual B2',
          'HardSeason': 'Hard season', 'Adjusted': 'Seasonal adjustment',
          'B2Point': 'B2Point', 'ExactPoint': 'ExactPoint', 'EndpointCI': 'EndpointCI',
          'LocalGaussian': 'Local Gaussian', 'LocalGMM': 'Local GMM (K=1)'}


def brier_row(row, historical=False):
    name = row['model']
    return {'id': IDS[name], 'label': LABELS.get(name, name), 'sourceModel': name,
            'score': value(row, 'brier'), 'scoreName': 'Brier',
            'h90': value(row, 'region90_hit_pct') if historical else 100 * value(row, 'region90_hit', 'h90'),
            'size': value(row, 'mean_region90_cells', 'region90_cells', 'k90'), 'sizeUnit': 'cells',
            'pairs': int(value(row, 'eligible_pairs', 'pairs')),
            'drifters': int(value(row, 'independent_ids', 'eligible_ids', 'ids'))}


def group(ident, label, cohort, detail, rows, paths):
    return {'id': ident, 'label': label, 'cohortLabel': cohort, 'comparability': detail,
            'rows': sorted(rows, key=lambda x: x['score']), 'source': [source(p) for p in paths]}


historical = 'results/runs/baseline_blend_cv_20261022T160806_056571Z'
s2 = 'results/runs/adaptive_b2_b1_20261030T044950_931787Z'
s3 = 'results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z'
s4 = 'results/deliverables/seasonal_information_s4_e3'
e8 = 'results/deliverables/position_error_s4_e8'
final = 'results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1'
gmm = 'results/runs/local_gmm_s5_e2_vector_20261107T133426Z'
diagnosis = 'results/runs/markov_diagnosis_20261025T114721_490747Z'
iteration = 'results/runs/markov_iteration_cv_20261027T120356_034230Z'

data = {'version': 1, 'horizonDays': 7,
        'evaluationLabel': 'Development evidence; independent final test remains locked',
        'comparisonRule': 'Rank within each matched group only. Cohorts, weights and probability-region definitions differ between groups.',
        'brierGroups': [], 'energyGroups': [], 'gaps': []}

for ident, label, path, models, cohort, detail, old in [
    ('historical', 'Pooled versus local', historical + '/outer_summary.csv', ['B1', 'B2'],
     '387 drifters · 308,312 pairs · pair-weighted CV',
     'Historical endpoint baseline comparison; five whole-ID folds; 1° output cells.', True),
    ('s2', 'Global regularisation', s2 + '/summary.csv', ['B2', 'Fixed', 'Adaptive'],
     '385 drifters · 303,288 pairs · pair-weighted CV',
     'S2 matched controls and two blends. Different eligibility from the earlier B1/B2 experiment.', False),
    ('s3', 'Spatial information', s3 + '/summary.csv', ['B2', 'Fixed', 'Adaptive', 'LocalEndpoint', 'LocalDisplacement'],
     '385 drifters · 37 cells · equal cells / IDs',
     '303,288 pairs; average times within each ID-cell, then IDs within cell, then equal cells. This weighting differs from S2.', False),
    ('s4', 'Seasonal information', s4 + '/summary.csv', ['Annual', 'HardSeason', 'Adjusted'],
     '45 drifters · 33,971 pairs · 2020–2022',
     'Fit 2001–2019; development evaluation 2020–2022; equal origins, IDs within origin, then times. 36 origin cells.', False),
]:
    rows = [brier_row(r, old) for r in table(path) if r['horizon_days'] == '7' and r['model'] in models]
    assert len(rows) == len(models)
    data['brierGroups'].append(group(ident, label, cohort, detail, rows, [path]))


def energy_row(row, headline=False):
    name = row['model']
    return {'id': IDS.get(name, name.lower()), 'label': LABELS.get(name, name), 'sourceModel': name,
            'score': value(row, 'energy_km'), 'scoreName': 'Energy Score',
            'h90': value(row, 'h90') * 100, 'size': value(row, 'area90_km2'), 'sizeUnit': 'km²',
            'pairs': 33971, 'drifters': 45, 'headline': headline,
            'landMass': value(row, 'land_mass'), 'outsideDMass': value(row, 'outside_D_mass')}


rows = [energy_row(r, r['model'] in ['MDN1', 'MDN22', 'ExactPoint', 'EndpointCI', 'LocalGaussian'])
        for r in table(final + '/summary.csv')]
gmm_row = next(r for r in table(gmm + '/summary.csv') if r['model'] == 'LocalGMM')
gmm_metric = energy_row(gmm_row, True)
gaussian_metric = next(r for r in rows if r['id'] == 'local-gaussian')
for key in ['score', 'h90', 'size']:
    assert gmm_metric[key] == gaussian_metric[key], 'LocalGMM is not the same saved Gaussian metric'
gmm_metric.update(aliasOf='local-gaussian', finding='Training-only K selection chose K=1; the selected law is identical to Local Gaussian.',
                  source=[source(gmm + '/summary.csv'), source(gmm + '/technical_report.md')])
rows.append(gmm_metric)
final_group = group('final', 'Continuous models · matched development comparison',
                   '45 drifters · 33,971 pairs · equal-ID evaluation',
                   'Seven-day full endpoint laws. Fit 265,393 pairs / 338 drifters (2001–2019); evaluate all 2020–2022 queries. ECEF chord-km Energy Score and own-law single LAEA 90% ellipse. Local GMM K=1 is the identical Gaussian law, not a distinct improvement.',
                   rows, [final + '/summary.csv', gmm + '/technical_report.md', 'docs/final_mdn_model.md'])
acceptance = read_json(final + '/acceptance.json')
selection = read_json(final + '/selection.json')
final_group.update(originalSelection={'provisionalK': selection['provisional_k'], 'selectedK': selection['selected_k'],
                                     'primaryModel': acceptance['primary_model']},
                   strictAcceptance=acceptance['overall_retention'], recommendedModel='mdn22',
                   recommendationBasis='Frozen post-development review decision; not the original training-only winner and not an independent-test claim.',
                   nominalCoverage=90, fullCandidateKs=[1, 2, 3, 4, 6, 8, 12, 16, 18, 20, 22, 32])
data['energyGroups'].append(final_group)
rows = [energy_row(r, True) for r in table(e8 + '/summary.csv') if r['model'] in ['B2Point', 'ExactPoint', 'EndpointCI']]
data['energyGroups'].append(group('e8', 'Historical bridge · cell conditioning to exact position',
                                  '45 drifters · 33,971 pairs · equal-ID evaluation',
                                  'Matched E8 continuous-space rescoring. Same case cohort as later continuous studies, but a different saved integration/report version. Compare within E8; do not subtract its bars from E4 scores. B2Point is the historical cell-conditioned empirical endpoint law.',
                                  rows, [e8 + '/summary.csv', e8 + '/REPORT.md']))

diagnostic_rows = table(diagnosis + '/summary.csv')
rows = []
for r in diagnostic_rows:
    if r['horizon_days'] == '7' and r['model'] in ['B1', 'B2', 'M1-1d']:
        rows.append({'id': IDS[r['model']], 'label': r['model'], 'sourceModel': r['model'],
                     'score': value(r, 'energy_km_common'), 'scoreName': 'Energy Score',
                     'h90': value(r, 'geo90_hit_pct_available'), 'size': value(r, 'mean_geo90_wet_area_km2'),
                     'sizeUnit': 'km² wet cells', 'pairs': int(r['spatial_common_pairs']),
                     'drifters': int(r['independent_ids']), 'headline': True})
data['energyGroups'].append(group('historical', 'Historical B1 / B2 diagnostic',
                                  '337 drifters · 268,998 common pairs · pair-weighted',
                                  'Seven-day forecasts on the historical common cohort with longer-path eligibility; stopped-target controls. ES uses WGS84 ECEF cell-centre coordinates conditional on complete, in-D predictions and outcomes. 90% regions are wet cell sets, not continuous ellipses. This is not the 45-drifter continuous leaderboard.',
                                  rows, [diagnosis + '/summary.csv', 'src/data3001/modelling/markov_models/markov_report.py']))

data['gaps'] = [
    {'id': 'b1-current-es', 'label': 'B1 · No matched score', 'score': None,
     'reason': 'B1 ES exists in the separate historical diagnostic; no B1 score is reported for the current 45-drifter full-law evaluation.'},
    {'id': 'b2point-final-es', 'label': 'B2Point · Historical matched bridge', 'score': None,
     'reason': 'B2Point belongs to E8; it was not included in the saved E4 final summary.'},
    {'id': 'mdn22-interval', 'label': 'MDN22 paired uncertainty interval', 'score': None,
     'reason': 'No MDN22 paired interval exported; MDN1 intervals cannot be relabelled.'},
    {'id': 'whole-r', 'label': 'Whole-R probability synthesis', 'score': None,
     'reason': 'Single fixed-case maps do not establish whole-region accumulation, loss or physical transport mechanisms.'}]

contrast = next(r for r in table(iteration + '/paired_ID_intervals.csv') if r['comparison'] == 'position-CV minus coarse-CV')
iteration_rows = table(iteration + '/summary.csv')
iteration_values = []
for name in ['B2-reference', 'coarse-CV', 'position-CV']:
    subset = [r for r in iteration_rows if r['model'] == name]
    # Saved independent numerical repeats estimate the same fixed forecast law;
    # averaging existing report values is not recomputing case-level scores.
    entry = {'model': name}
    for dest, key in [('score', 'S_integration'), ('unresolvedMass', 'U_mass'), ('exitMass', 'E_mass')]:
        nums = [value(r, key) for r in subset if value(r, key) is not None]
        entry[dest] = sum(nums) / len(nums) if nums else None
    iteration_values.append(entry)
ground = ROOT.parent / 'additional_research/grounding_scope_conclusion_20261110.md'
literature = 'results/deliverables/presentation_week10_20261109/narrative_audit_20261114.md'
data['evidence'] = {
    'iterations': {
        'title': 'Longer horizons need direct validation', 'horizonDays': 30, 'pairs': 268998, 'drifters': 337,
        'rows': iteration_values,
        'contrast': {'label': contrast['comparison'], 'delta': float(contrast['delta_S']),
                     'lower95': float(contrast['lower_95']), 'upper95': float(contrast['upper_95'])},
        'finding': 'The 30-day tuned exact-position versus tuned coarse contrast did not establish a reliable score gain. Its whole-ID interval crosses zero.',
        'interpretation': 'Repeated short-step forecasts can accumulate bias and support/geometry failures. These experiments do not prove that all iterative models are worse: historical M1 had lower penalized S than direct B2 at 30 days. The target and fitting information also differ.',
        'historical30Day': [{k: value(r, key) if k != 'model' else r['model']
                            for k, key in [('model', 'model'), ('score', 'brier_failure_penalized'),
                                           ('h90', 'region90_hit_pct_all_cases')]}
                           for r in diagnostic_rows if r['horizon_days'] == '30' and r['model'] in ['B1', 'B2', 'M1-1d']],
        'limits': 'Adaptive development comparison. Conditional 200-resample whole-ID intervals exclude refitting and prior research adaptation. U is unresolved numerical/support state, not confirmed grounding.',
        'source': [source(iteration + '/REPORT.md'), source(iteration + '/summary.csv'),
                   source(iteration + '/paired_ID_intervals.csv'), source(diagnosis + '/summary.csv')]},
    'grounding': {
        'title': 'Observed endpoints do not validate grounding risk',
        'finding': 'No used seven-day window has an officially confirmed grounding event; this is absence of confirmation, not evidence of zero events.',
        'trainingPairs': 265393, 'validationPairs': 33971,
        'usedEndpointAfterLastGood': 0, 'usedEndpointAtLastGood': {'train': 1, 'validation': 1},
        'missingEndpointAcrossEndBoundary': {'train': 490, 'validation': 167},
        'day7StateUnconfirmed': {'train': 20202, 'validation': 3022},
        'suspiciousHoldingPairs': 629, 'suspiciousHoldingDrifters': 3,
        'limits': 'Official final grounding status does not date first grounding. The evaluation targets eligible observed endpoints and does not validate grounding or termination-related missingness.',
        'source': [source(ground)]},
    'forgetting': {
        'title': 'Future temporal adaptation',
        'finding': 'Pope-style forgetting downweights older transition evidence to adapt to time-varying probabilities. It is a future method here, not an implemented sparse-location correction.',
        'implemented': False, 'factorConvention': None,
        'limits': 'The exact factor symbol and update convention have not been reverified for this export. Do not claim a numeric optimum or label larger alpha as more forgetting without the paper convention.',
        'reference': {'authors': 'Pope, Stephenson & Jackson', 'year': 2020,
                      'title': 'An Adaptive Markov Chain Approach for Probabilistic Forecasting of Categorical Events',
                      'doi': '10.1175/MWR-D-19-0239.1', 'url': 'https://doi.org/10.1175/MWR-D-19-0239.1'},
        'source': [source(literature)]},
    'smallStepReference': {
        'authors': 'Chamberlain et al.', 'year': 2023,
        'title': 'Using Existing Argo Trajectories to Statistically Predict Future Float Positions with a Transition Matrix',
        'doi': '10.1175/JTECH-D-22-0070.1', 'url': 'https://doi.org/10.1175/JTECH-D-22-0070.1',
        'finding': 'Grid and transition-lag choices trade discretisation bias against sample uncertainty; repeated short-step composition need not outperform a longer directly estimated step.',
        'limits': 'Argo float results motivate a check, not a transferable optimal lag for surface GDP drifters.',
        'source': [source(literature)]}}

data['sources'] = sources
assert [len(g['rows']) for g in data['brierGroups']] == [2, 3, 5, 3]
assert sum(r['headline'] for r in final_group['rows']) == 6
assert sum(r['id'].startswith('mdn') for r in final_group['rows']) == 12
for g in data['brierGroups'] + data['energyGroups']:
    assert all(r['score'] is not None and 0 <= r['h90'] <= 100 and r['size'] > 0 for r in g['rows'])
OUT.joinpath('data.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
OUT.joinpath('SOURCES.md').write_text(
    '# Part 4 frozen comparison evidence\n\n'
    'Generated by `python3 scripts/export-part4-data.py`; standard library only. No fitting, scoring, final-test access or historical edits.\n\n'
    'Brier: four internally matched groups, 2 / 3 / 5 / 3 rows. ES: E4 final full-law evaluation, E8 bridge, and separate historical cell-centre diagnostic. Bars may be ranked only within their group. All H90 values are percentages.\n\n'
    'The E4 headline contains six labels but five distinct laws: Local GMM selected K=1 is identical to Local Gaussian, and its saved scores exactly match. All 12 MDN candidates are retained. MDN22 is the later frozen recommendation; original selected MDN1 failed strict overall acceptance.\n\n'
    'B1 has historical ES, but no matched current-cohort ES. B2Point belongs to E8. MDN22 uncertainty and whole-R synthesis remain explicit gaps. Iteration evidence is 30-day development research; U is not grounding. Grounding evidence concerns confirmation limits, not zero incidence. Pope is a proposed temporal adaptation reference, not an implemented result.\n\n'
    'Source paths are relative to work_place; `../additional_research` is its sibling audit folder. The paper titles/DOIs are taken from the existing verified local literature audit; factor notation is deliberately unspecified.\n\n'
    '## Source SHA256\n\n' + ''.join(f'- `{path}` — `{digest}`\n' for path, digest in sorted(sources.items())))
print(json.dumps({'brierRows': [len(g['rows']) for g in data['brierGroups']],
                  'energyRows': {g['id']: len(g['rows']) for g in data['energyGroups']},
                  'sourceCount': len(sources), 'output': str(OUT)}))
