#!/usr/bin/env python3
"""Export published development evidence; no model fitting or score recomputation.

Run with work_place/.venv/bin/python. Continuous displays sample stored forecasts,
not networks. Source hashes and display seed are exported for reproducibility.
"""
import argparse
import copy
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Geod, Transformer

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=Path('/Users/moonedgethug/Documents/UNSW/DATA3001/work_place'))
parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'dist/assets/pt3')
args = parser.parse_args()
ROOT, OUT = args.root, args.output
OUT.mkdir(parents=True, exist_ok=True)
sources = {}
MODELS = ['b1', 'b2', 'fixed', 'adaptive', 'local-endpoint', 'local-displacement',
          'seasonal', 'exact-point', 'endpoint-ci', 'local-gaussian', 'local-gmm', 'mdn1', 'mdn22']
data = {'version': 1, 'horizonDays': 7, 'models': {}}
for name in MODELS:
    data['models'][name] = {'metrics': {'score': None, 'scoreName': 'Brier', 'h90': None,
        'size': None, 'sizeUnit': 'cells', 'cohortLabel': 'Metric export pending'},
        'map': None, 'gap': 'Map export pending — no illustrative result substituted.', 'source': [], 'finding': ''}


def source(path):
    path = Path(path)
    relative = path.relative_to(ROOT).as_posix()
    if relative not in sources:
        sources[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return relative


def table(path):
    source(path)
    return pd.read_csv(path)


def metric(row, cohort, continuous=False):
    return {'score': float(row['energy_km' if continuous else 'brier']),
        'scoreName': 'Energy Score' if continuous else 'Brier',
        'h90': float(row.get('h90', row.get('region90_hit'))) * 100,
        'size': float(row['area90_km2'] if continuous else row.get('k90', row.get('region90_cells'))),
        'sizeUnit': 'km²' if continuous else 'cells', 'cohortLabel': cohort}


def cell_map(states, probabilities, origin, run, source_model, label, region=None):
    states, p = np.asarray(states, int), np.asarray(probabilities, float)
    if not np.isclose(p.sum(), 1, atol=1e-10):
        raise ValueError(f'Incomplete probability vector: {source_model} {p.sum()}')
    if region is None:
        descending = np.sort(p)[::-1]
        cutoff = descending[np.searchsorted(np.cumsum(descending), .9)]
        region = p >= cutoff - 1e-14
    cells = [[int(c % 360 - 180), int(c // 360 - 90), float(v)] for c, v in zip(states, p) if c >= 0 and v > 0]
    boundary = [[int(c % 360 - 180), int(c // 360 - 90)] for c, yes in zip(states, region) if c >= 0 and yes]
    extent = [-83, 22, -55, 44]
    off = sum(v for x, y, v in cells if not (extent[0] <= x and x + 1 <= extent[2] and extent[1] <= y and y + 1 <= extent[3]))
    return {'gridSize': 1, 'cells': cells, 'origin': origin, 'originKind': 'cell-centre', 'truth': None,
        'region90': None, 'regionCells90': boundary, 'kind': 'fitted', 'label': label, 'extent': extent,
        'source': run, 'sourceModel': source_model, 'displayScale': 'sqrt', 'outsideViewportMass': off,
        'exitMass': float(p[states == -2].sum()), 'displayMass': float(sum(c[2] for c in cells)),
        'probabilityLabel': 'Probability per 1° model cell', 'regionLabel': 'Nominal 90% cell set'}


# S2 all-development fitted illustrations, not held-out examples.
s2 = ROOT / 'results/runs/adaptive_b2_b1_20261030T044950_931787Z'
s2summary = table(s2 / 'summary.csv')
origin_cell = 44744
origin = [origin_cell % 360 - 179.5, origin_cell // 360 - 89.5]
for ident, name in [('b2', 'B2'), ('fixed', 'Fixed'), ('adaptive', 'Adaptive'), ('b1', 'B1')]:
    path = s2 / ('bases/all_development_candidate_b1.parquet' if ident == 'b1' else f'matrices/all_development_candidate_{name}.parquet')
    source(path)
    frame = pd.read_parquet(path)
    frame = frame[frame.horizon_days.eq(7)]
    if 'origin_cell_1' in frame:
        frame = frame[frame.origin_cell_1.eq(origin_cell)]
    item = data['models'][ident]
    item['map'] = cell_map(frame.destination_cell_1, frame.probability, origin, s2.name, name,
        'All-development fitted illustration · not a held-out case')
    item['source'] = [source(path), source(s2 / 'summary.csv')]
    if ident != 'b1':
        row = s2summary[(s2summary.horizon_days == 7) & (s2summary.model == name)].iloc[0]
        item['metrics'] = metric(row, 'S2 · 385 drifters · whole-ID CV · pair-weighted')
        item['gap'] = None
    else:
        item['gap'] = 'B1 standalone scores are not reported in this S2 comparison.'
        item['metrics']['cohortLabel'] = 'B1 fitted reference · standalone scores not reported'

# S3 has a different evaluation weighting; retain that identity.
s3 = ROOT / 'results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z'
s3summary = table(s3 / 'summary.csv')
for ident, name in [('local-endpoint', 'LocalEndpoint'), ('local-displacement', 'LocalDisplacement')]:
    path = s3 / f'matrices/all_development_candidate_{name}.parquet'
    source(path)
    frame = pd.read_parquet(path)
    frame = frame[(frame.horizon_days == 7) & (frame.origin_cell_1 == origin_cell)]
    item = data['models'][ident]
    item['map'] = cell_map(frame.destination_cell_1, frame.probability, origin, s3.name, name,
        'S3 fitted illustration · not a held-out case')
    row = s3summary[(s3summary.horizon_days == 7) & (s3summary.model == name)].iloc[0]
    item['metrics'] = metric(row, 'S3 · 385 drifters · equal cells / IDs within cell')
    item['source'] = [source(path), source(s3 / 'summary.csv')]
    item['gap'] = None

# Stage 4 branches: concrete Adjusted variants, never unnamed composites.
for ident, folder in [('seasonal', 'seasonal_information_s4_e3')]:
    run = ROOT / 'results/deliverables' / folder
    rows = table(run / 'summary.csv')
    row = rows[(rows.horizon_days == 7) & (rows.model == 'Adjusted')].iloc[0]
    item = data['models'][ident]
    item['metrics'] = metric(row, '2020–2022 · 45 drifters · equal origins / IDs')
    item['source'] = [source(run / 'summary.csv')]
    if ident == 'seasonal':
        keys = table(run / 'forecast_keys.csv')
        select = keys[(keys.model == 'Adjusted') & (keys.horizon_days == 7) & (keys.origin_cell_1 == origin_cell) & (keys.departure_season == 0)]
        index = int(select.index[0])
        for file in ['forecast_vectors.npy', 'states.npy', 'region_masks.npy']:
            source(run / file)
        p = np.load(run / 'forecast_vectors.npy', mmap_mode='r')[index]
        states = np.load(run / 'states.npy')
        mask = np.load(run / 'region_masks.npy', mmap_mode='r')[index]
        item['map'] = cell_map(states, p, origin, folder, 'Adjusted',
            'Winter-conditioned fitted forecast · cell 44744', mask)
        item['source'] += [source(run / x) for x in ['forecast_keys.csv', 'forecast_vectors.npy', 'states.npy', 'region_masks.npy']]
        item['gap'] = None

# E7 exported evidence already carries source hashes and fixed demonstration cases.
e7path = ROOT / 'results/deliverables/exact_origin_s4_e7_visual_report/src/data.json'
source(e7path)
e7 = json.loads(e7path.read_text())['queries']
row = next(x for x in e7['summary']['rows'] if x['resolution'] == 1 and x['model'] == 'Exact')
example = next(x for x in e7['examples']['rows'] if x['case'] == 'case-1' and x['resolution'] == 1)
cells = [x for x in e7['maps']['rows'] if x['case'] == 'case-1' and x['model'] == 'Exact' and x['resolution'] == 1]
item = data['models']['exact-point']
item['metrics'] = metric(row, 'E7 · 2020–2022 · 45 drifters · equal origins / IDs')
item['map'] = {'gridSize': 1, 'cells': [[x['lon'], x['lat'], x['probability']] for x in cells if x['probability'] > 0],
    'origin': [example['lon'], example['lat']], 'originKind': 'exact', 'truth': [example['endpointLon'], example['endpointLat']],
    'region90': None, 'regionCells90': [[x['lon'], x['lat']] for x in cells if x['inRegion']],
    'kind': 'validation', 'label': 'E7 saved validation example · case 1', 'extent': [-83, 22, -55, 44],
    'source': 'exact_origin_s4_e7_primary_20261105T074326_829211Z', 'sourceModel': 'Exact',
    'displayScale': 'sqrt', 'displayMass': sum(x['probability'] for x in cells),
    'probabilityLabel': 'Probability per 1° output cell', 'regionLabel': 'Nominal 90% cell set'}
item['source'] = [source(e7path)]
item['gap'] = None

# Complete-law stage 5 evaluation copied from frozen summaries.
mdn = ROOT / 'results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1'
summary = table(mdn / 'summary.csv')
gmm = ROOT / 'results/runs/local_gmm_s5_e2_vector_20261107T133426Z'
gmm_summary = table(gmm / 'summary.csv')
for ident, name in [('endpoint-ci', 'EndpointCI'), ('local-gaussian', 'LocalGaussian'), ('local-gmm', 'LocalGMM'), ('mdn1', 'MDN1'), ('mdn22', 'MDN22')]:
    frame = gmm_summary if ident == 'local-gmm' else summary
    row = frame[frame.model.eq(name)].iloc[0]
    item = data['models'][ident]
    item['metrics'] = metric(row, '2020–2022 · 45 drifters · equal-ID evaluation', True)
    item['source'] = [source(gmm / 'summary.csv') if ident == 'local-gmm' else source(mdn / 'summary.csv')]

# Real frozen conditional distributions: deterministic DISPLAY-ONLY sampling.
# No parameters fitted, network run, score recalculated, or final-test data opened.
COUNT, SEED = 65536, 20261116
geod = Geod(ellps='WGS84')
inverse = Transformer.from_crs('+proj=laea +lon_0=-75 +lat_0=35 +ellps=WGS84 +units=m', 'EPSG:4326', always_xy=True)
key = [300234063731750, 139319181, 7]  # First original fixed E3 source-order example.
target_path = ROOT / 'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/outer_targets.parquet'
source(target_path)
target = pd.read_parquet(target_path, columns=['id','origin_source_obs','horizon_days','outside','endpoint_lon','endpoint_lat'],
    filters=[('id', '=', key[0]), ('origin_source_obs', '=', key[1]), ('horizon_days', '=', 7)])
assert len(target) == 1 and not bool(target.iloc[0].outside)
truth = target[['endpoint_lon', 'endpoint_lat']].iloc[0].tolist()


def boundary(region):
    angles = np.linspace(0, 2*np.pi, 193)
    axes = np.sqrt(np.maximum(region['eigenvalues'], 0) * region['cutoff'])
    points = np.asarray(region['centre']) + (np.column_stack([np.cos(angles),np.sin(angles)]) * axes) @ np.asarray(region['eigenvectors']).T
    return np.column_stack(inverse.transform(points[:,0]*1000, points[:,1]*1000)).tolist()


def sampled_map(origin, weights, means, chol, region, name, run, seed):
    rng = np.random.default_rng(seed)
    labels = rng.choice(len(weights), size=COUNT, p=weights)
    z = rng.standard_normal((COUNT,2))
    vectors = means[labels] + np.einsum('nij,nj->ni',chol[labels],z)
    radii = np.linalg.norm(vectors,axis=1)
    lon,lat,_ = geod.fwd(np.full(COUNT, origin[0]),np.full(COUNT,origin[1]),np.degrees(np.arctan2(vectors[:,0], vectors[:,1])),radii*1000)
    bins,counts = np.unique(np.floor(np.column_stack([lon,lat])*2).astype(int),axis=0,return_counts=True)
    cells = [[float(x)/2,float(y)/2,int(n)/COUNT] for (x,y),n in zip(bins,counts)]
    extent = [-83,22,-55,44]
    off = sum(p for x,y,p in cells if not (extent[0] <= x and x+.5 <= extent[2] and extent[1] <= y and y+.5 <= extent[3]))
    return {'gridSize': .5, 'cells': cells, 'origin': list(origin), 'originKind': 'exact', 'truth': truth,
        'region90': boundary(region), 'regionCells90': None, 'kind': 'validation',
        'label': 'Frozen development case · source-order example 1', 'extent':extent,
        'source':run, 'sourceModel':name, 'displayScale':'sqrt', 'displayCount':COUNT, 'displaySeed':seed,
        'displayMass':sum(c[2] for c in cells), 'outsideViewportMass':off, 'sourceKey':key,
        'probabilityLabel':'Probability per 0.5° display cell', 'regionLabel':'Saved nominal 90% quantile ellipse',
        'displayNote':'Continuous forecast; 0.5° bins from fixed display-only samples. Scores and ellipse are unchanged.'}


score_path = mdn / 'C_outer/outer_score/N65536_M65536/scores.parquet'
source(score_path)
scores = pd.read_parquet(score_path, columns=['position','K','id','origin_source_obs','region_json'],filters=[('position','=',0),('K','in',[1,22])])
for k in [1,22]:
    path = mdn / f'C_outer/K{k}/parameters.npz'
    source(path)
    with np.load(path, allow_pickle=False) as packet:
        assert packet['query_keys'][0].tolist() == key
        origin = packet['origins'][0].copy()
        w,m,c = [packet[n][0].copy() for n in ['pi','mu','cov']]
    scored = scores[scores.K.eq(k)].iloc[0]
    assert int(scored.id) == key[0] and int(scored.origin_source_obs) == key[1]
    region = json.loads(scored.region_json)['region']
    item = data['models'][f'mdn{k}']
    item['map'] = sampled_map(origin,w,m,np.linalg.cholesky(c),region,f'MDN{k}',mdn.parent.name,SEED+k)
    item['source'] += [source(path),source(score_path),source(target_path)]
    item['gap'] = 'MDN22 paired uncertainty intervals and whole-R synthesis remain pending.' if k == 22 else None

parameter_path = gmm / 'C_outer/parameters/00000.json.gz'
region_path = gmm / 'C_outer/regions/00000.json.gz'
source(parameter_path); source(region_path)
record = json.loads(gzip.decompress(parameter_path.read_bytes()))[0]
saved_regions = json.loads(gzip.decompress(region_path.read_bytes()))[0]['regions']
assert [record[x] for x in ['id','origin_source_obs','horizon_days']] == key
packet = record['models']['1']
gaussian_map = sampled_map(record['origin'],np.asarray(packet['weights']),np.asarray(packet['means']),np.asarray(packet['cholesky']),
    saved_regions['1']['region'],'LocalGaussian',gmm.name,SEED+100)
for ident in ['local-gaussian','local-gmm']:
    item=data['models'][ident]
    item['map']=copy.deepcopy(gaussian_map)
    if ident=='local-gmm':
        item['map']['sourceModel']='LocalGMM (selected K=1)'
        item['map']['displayNote'] += ' Selected LocalGMM K=1 is identical to LocalGaussian.'
    item['source'] += [source(parameter_path),source(region_path),source(target_path)]
    item['gap']=None

# EndpointCI reuses the exact saved donor lineage and historical error kernels.
# Only selected fitting endpoints are joined; held-out endpoint errors are not read.
lineage_path = gmm / 'C_outer/lineage/00000.npz'
train_path = ROOT / 'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/training_coordinates.parquet'
repair_path = ROOT / 'provenance/migrations/position_error_repair_20261106T073218_242005Z/full/error_overlay.parquet'
kernel_path = ROOT / 'src/data3001/modelling/baselines/position_error_s4_e8.py'
for path in [lineage_path, train_path, repair_path, kernel_path]:
    source(path)
assert sources[source(repair_path)] == 'cf77af02d7af69b255d84b40f49bd5d7c4ad41f35816e00a58926ad6f47dd8f3'
with np.load(lineage_path, allow_pickle=False) as lineage:
    donor_indices = lineage['indices'][lineage['offsets'][0]:lineage['offsets'][1]].astype(np.int64)
training = pd.read_parquet(train_path).sort_values(['id','origin_source_obs','horizon_days']).reset_index(drop=True)
assert len(training) == 265393 and training.id.nunique() == 338
donors = training.iloc[donor_indices].copy()
assert len(donors) == 8000 and donors.id.nunique() == 70 and not donors.outside.any()
assert not (donors.id == key[0]).any()
filters = [[('id', '=', int(ident)), ('source_obs', 'in', frame.endpoint_source_obs.astype(int).unique().tolist())]
           for ident, frame in donors.groupby('id')]
overlay = pd.read_parquet(repair_path,
    columns=['id','source_obs','time','lon','lat','repaired_err_lon','repaired_err_lat','ci_2d_usable','base_version'],
    filters=filters)
overlay = overlay.rename(columns={'source_obs':'endpoint_source_obs','time':'verified_epoch',
                                 'lon':'verified_lon','lat':'verified_lat'})
donors = donors.merge(overlay, on=['id','endpoint_source_obs'], how='left', validate='many_to_one', indicator=True)
assert donors._merge.eq('both').all()
assert donors.base_version.eq('per-drifter-cleaned-20261017-v7').all()
assert np.array_equal(donors.target_epoch, donors.verified_epoch)
assert np.array_equal(donors.endpoint_lon, donors.verified_lon)
assert np.array_equal(donors.endpoint_lat, donors.verified_lat)
usable = donors.ci_2d_usable.to_numpy(bool)
assert int(usable.sum()) == 7487
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'src'))
from data3001.modelling.baselines.position_error_s4_e8 import equivalent_sd, component_cloud
points = donors[['endpoint_lon','endpoint_lat']].to_numpy(float)
sd = equivalent_sd(points, donors[['repaired_err_lon','repaired_err_lat']].to_numpy(float), usable)
ci_seed, ci_budget = 20261126, 32768  # Original E3 report display recipe.
cloud, weights, labels = component_cloud(points, sd, usable, ci_budget,
    ('mdn_s5_e3_display_only', ci_seed, *key, 'EndpointCI'))
assert np.allclose(np.bincount(labels, weights=weights, minlength=len(donors)), 1/len(donors), rtol=0, atol=1e-15)
bins, index = np.unique(np.floor(cloud*2).astype(int), axis=0, return_inverse=True)
mass = np.bincount(index, weights=weights, minlength=len(bins))
cells = [[float(x)/2, float(y)/2, float(p)] for (x,y),p in zip(bins,mass)]
extent = [-83,22,-55,44]
off = sum(p for x,y,p in cells if not (extent[0] <= x and x+.5 <= extent[2] and extent[1] <= y and y+.5 <= extent[3]))
item = data['models']['endpoint-ci']
item['map'] = {
    'gridSize': .5, 'cells': cells, 'origin': record['origin'], 'originKind':'exact', 'truth': truth,
    'region90': boundary(saved_regions['EndpointCI']['region']), 'regionCells90': None,
    'kind':'validation', 'label':'Frozen development case · source-order example 1', 'extent':extent,
    'source':gmm.name, 'sourceModel':'EndpointCI', 'displayScale':'sqrt',
    'displayCount':len(cloud), 'displayBudget':ci_budget, 'displaySeed':ci_seed,
    'displayMass':float(weights.sum()), 'outsideViewportMass':off, 'sourceKey':key,
    'probabilityLabel':'Probability per 0.5° display cell', 'regionLabel':'Saved nominal 90% quantile ellipse',
    'displayNote':'Historical endpoint-error mixture; display-only weighted samples. All donor votes and the saved ellipse are retained.',
    'donorCount':len(donors), 'usableErrorDonors':int(usable.sum()), 'pointFallbackDonors':int((~usable).sum()),
    'donorWeight':1/len(donors), 'caseSelection':'Position 0 of the original 12 source-order cases; selected independently of outcomes.',
    'errorMeaning':'Repaired 95% marginal position half-widths are matched to a fixed independent normal kernel. Unavailable errors retain point mass; this is not a parameter confidence interval.'}
item['source'] += [source(path) for path in [parameter_path,region_path,lineage_path,train_path,repair_path,kernel_path,target_path]]
item['gap'] = None

findings = {
 'b1':'Pooling all origins provides a shared empirical destination distribution.',
 'b2':'Conditioning on the origin cell preserves local information but leaves unobserved outcomes at zero.',
 'fixed':'Global borrowing trades local detail for a broader empirical reference.',
 'adaptive':'The tested adaptive rule did not establish a dependable Brier advantage over Fixed.',
 'local-endpoint':'Lower Brier and a smaller region came with lower observed coverage than Fixed.',
 'local-displacement':'Whole-path transfer did not qualify as an improvement over Fixed.',
 'seasonal':'The adjusted seasonal model did not establish a stable Brier gain.',
 'heading':'Departure heading showed a small supported seven-day Brier improvement.',
 'exact-point':'Exact-origin neighbour selection improved Brier and coverage, with a larger region.',
 'endpoint-ci':'Historical endpoint-error spreading showed no practically useful improvement.',
 'local-gaussian':'A continuous local distribution summarizes nearby historical endpoints.',
 'local-gmm':'Training-only selection chose K=1, identical to LocalGaussian in this experiment.',
 'mdn1':'A shared conditional network with one mixture component remains the simpler comparator.',
 'mdn22':'Recommended after development review; original strict acceptance was not passed.'}
for name,item in data['models'].items():
    item['finding']=findings[name]
    if item['map']:
        assert all(c[2]>=0 for c in item['map']['cells'])
        assert abs(sum(c[2] for c in item['map']['cells'])+item['map'].get('exitMass',0)-1)<1e-8
        item['map']['maxProbability']=max(c[2] for c in item['map']['cells'])

data['sources']=sources
data['evidenceNotes']=[
    'S2 maps are all-development fitted illustrations; metric cards summarize held-out whole-ID CV.',
    'S3 metrics use equal cells and equal IDs within cell, unlike S2 pair weighting.',
    'E7 ExactPoint is the 1° stopped-target experiment, not the later continuous ES control.',
    'MDN22 map is newly exported from saved forecasts for the original first fixed case; it is not a new model run.',
    'EndpointCI uses the saved 8,000-donor lineage: 7,487 usable historical error kernels and 513 unchanged point masses. Each donor retains 1/8,000 weight.',
    'All continuous displayed maps use deterministic display-only samples; original scores and saved ellipses are retained.',
    'Different targets, grids and aggregation weights cannot be pooled into a universal model ranking.',
    'No locked final-test data, refitting, model selection or recomputed scores were used.'
]
(OUT/'data.json').write_text(json.dumps(data,separators=(',',':'),allow_nan=False)+'\n')
(OUT/'SOURCES.md').write_text('# Part 3 source-backed visualization export\n\n'+
    '\n'.join('- '+x for x in data['evidenceNotes'])+'\n\n## Reproduction\n\n'+
    'Run `work_place/.venv/bin/python scripts/export-part3-data.py --root <work_place>` from the Site checkout. Requires numpy, pandas, pyarrow and pyproj already present in the research environment.\n\n'+
    'MDN/Gaussian display sample count: 65,536. Seeds: 20261116 plus 1, 22 or 100. Mixture parameters describe east/north geodesic displacements in km; WGS84 forward geodesics yield endpoints. Saved 90% ellipses use the original LAEA projection centered on 75°W, 35°N. Binning does not renormalize viewports.\n\n'+
    'EndpointCI reproduces the original E3 display recipe with budget 32,768 and seed 20261126: the native antithetic component_cloud produces 30,461 weighted nodes (7,487 usable donors × 4 nodes, plus 513 point fallbacks). Each donor keeps exactly 1/8,000 total weight. The saved region is copied, not refitted. Errors are repaired historical 95% marginal half-widths, matched to independent normal kernels using 1.9599639845; they are not model-parameter confidence intervals. No held-out endpoint-error fields were read. The fixed example key is [300234063731750,139319181,7], position 0 of the original 12 outcome-independent source-order cases.\n\n'+
    'Latest MDN22 interval and whole-R gaps remain. Departure heading is omitted from the presentation at user request; research artifacts are preserved. B1 standalone metrics were not reported by the S2 comparison.\n\n## Source SHA256\n\n'+
    '\n'.join(f'- `{path}` — `{digest}`' for path,digest in sources.items())+'\n')
print(json.dumps({'models':len(data['models']),'maps':sum(x['map'] is not None for x in data['models'].values()),
    'json_bytes':(OUT/'data.json').stat().st_size,'sources':len(sources)}))
