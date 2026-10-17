"""Offline incremental execution and verification of the coastal SST policy."""
from pathlib import Path
from datetime import datetime, timezone
from functools import lru_cache
import concurrent.futures as cf
import gzip
import hashlib
import json
import sqlite3
import sys
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapely
from pyproj import Geod
from data3001.dataset import manifest, track_path
from data3001.paths import project_paths, asset_path, file_sha256, ensure_output_path
from data3001.sst_reconstruction import decode_zarr_chunk, verify_frozen
from data3001.sst_coastal import (three_corner_temperature, apply_coastal_patch,
                                 water_support_hull_ok, VERTICES)

BASELINE = 'results/runs/sst_reconstruction_20261016_v1'
RUN_ID = 'sst_coastal_extension_20261017_v1'
CONTRACT = '6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446'
BUCKET = 'https://noaa-cdr-sea-surface-temp-optimum-interpolation-pds.s3.amazonaws.com/'
KEYS = ['id', 'source_obs']


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False, default=str)+'\n')


def metrics(frame, estimate, reference='reference_K'):
    error = (frame[estimate] - frame[reference]).to_numpy(float)
    good = np.isfinite(error)
    error = error[good]
    return {'n': int(good.sum()), 'IDs': int(frame.loc[good, 'id'].nunique()),
            'MAE_K': float(np.mean(abs(error))) if len(error) else None,
            'RMSE_K': float(np.sqrt(np.mean(error**2))) if len(error) else None,
            'bias_K': float(np.mean(error)) if len(error) else None}


def run():
    root = project_paths().root
    baseline = root / BASELINE
    destination = ensure_output_path('results/runs/'+RUN_ID)
    assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx') == CONTRACT
    plan = json.loads((baseline/'source_plan.json').read_text())
    verify_frozen(root, plan['code_and_evidence_hashes'])
    baseline_config = json.loads((baseline/'config.json').read_text())
    verify_frozen(baseline, baseline_config['frozen_files'])
    assert json.loads((baseline/'verification.json').read_text())['status'] == 'passed'
    records = manifest()['records']
    outputs = {int(r['id']): r for r in json.loads((baseline/'output_manifest.json').read_text())}
    # Hash all canonical inputs and all baseline temperature sidecars, not just candidates.
    def check_id(item):
        sid, record = item
        assert file_sha256(root/record['path']) == record['sha256']
        assert file_sha256(root/outputs[int(sid)]['path']) == outputs[int(sid)]['sha256']
        schema = pq.read_schema(root/record['path'])
        assert len(schema.names) == 130
        assert pq.ParquetFile(root/record['path']).metadata.num_rows == record['rows']
        return record['rows']
    print('Checking all canonical and baseline per-ID files', flush=True)
    with cf.ThreadPoolExecutor(max_workers=4) as executor:
        rows = sum(executor.map(check_id, records.items()))
    assert rows == 39107061 and len(records) == 3741
    evidence_names = ['targets.parquet', 'nodes.parquet', 'node_sst.npy', 'node_err.npy',
                      'matched_temperature.parquet', 'unknown_by_ID_reason.csv',
                      'output_manifest.json', 'verification.json', 'effective_config.json',
                      'source_plan.json', 'node_sst_sources.csv', 'node_err_sources.csv']
    dependencies = {str((baseline/name).relative_to(root)): file_sha256(baseline/name)
                    for name in evidence_names}
    dependencies.update({name: file_sha256(root/name) for name in [
        'configs/dataset_manifest.json', 'configs/assets.json',
        'src/data3001/sst_reconstruction.py', 'src/data3001/sst_coastal.py',
        'src/data3001/sst_coastal_run.py', 'tests/test_sst_coastal.py',
        'docs/sst_coastal_extension_plan.md']})
    print('Selecting only existing coastal unknowns', flush=True)
    ledger = pd.read_csv(baseline/'unknown_by_ID_reason.csv')
    coastal = ledger[ledger.reason.eq('land_barrier_or_coastal_stencil_and_no_local_fallback')]
    unknown_parts = []
    for pool, id in coastal[['pool', 'id']].itertuples(index=False, name=None):
        old = pd.read_parquet(baseline/pool/f'{id}.parquet', columns=KEYS+['sst_method','sst_reason'])
        selected = old.sst_method.eq(3) & old.sst_reason.eq('external_unavailable_and_no_qualified_short_gap')
        unknown_parts.append(old.loc[selected, KEYS])
    unknown = pd.concat(unknown_parts, ignore_index=True)
    targets = pd.read_parquet(baseline/'targets.parquet')
    q = unknown.merge(targets[targets.kind.eq('target')], on=KEYS, validate='one_to_one')
    q = q[~q.all_water_stencil & ~q.quarantine].reset_index(drop=True)
    assert len(q) == int(coastal.hours.sum())
    temperature_nodes = np.load(baseline/'node_sst.npy')
    error_nodes = np.load(baseline/'node_err.npy')
    corner_ids = q[[f'node{k}' for k in range(4)]].to_numpy()
    corner_values = temperature_nodes[corner_ids]
    counts = np.isfinite(corner_values).sum(axis=1)
    count_ledger = q[KEYS+['pool','in_R']].copy()
    count_ledger['finite_source_corners'] = counts
    selected = counts == 3
    candidates = q.loc[selected].reset_index(drop=True)
    corner_ids = corner_ids[selected]
    values = corner_values[selected]
    estimates = three_corner_temperature(candidates.u, candidates.v, values)
    # Same source cell only. At the +/-180 seam do not create a spanning polygon.
    left = candidates.i.to_numpy()*.25 + .125
    left = np.where(left >= 180, left-360, left)
    bottom = candidates.j.to_numpy()*.25 - 89.875
    points = np.stack([left[:,None] + .25*VERTICES[:,0],
                       bottom[:,None] + .25*VERTICES[:,1]], axis=2)
    available = np.isfinite(values)
    three_points = points[available].reshape(-1,3,2)
    target_xy = np.column_stack([((candidates.lon.to_numpy()+180)%360)-180,
                                 candidates.lat.to_numpy()])
    geometry_ok = (left+.25 <= 180)
    mask_hashes = {}
    for name in ['land_mask_high', 'land_mask_intermediate']:
        mask_path = asset_path(name, verify=True)
        mask_hashes[name] = file_sha256(mask_path)
        land = shapely.from_wkb(mask_path.read_bytes())
        geometry_ok &= water_support_hull_ok(target_xy,three_points,[land])
    # Recheck target qualification against canonical tracks, not the old reason alone.
    for id, group in candidates.groupby('id'):
        native = pq.read_table(track_path(int(id), allow_test=True),
            columns=KEYS+['position_ok','mapping_ok']).to_pandas().set_index('source_obs')
        assert native.loc[group.source_obs, 'position_ok'].all()
        assert native.loc[group.source_obs, 'mapping_ok'].all()
    admitted = geometry_ok & np.isfinite(estimates['temperature_C'])
    candidates['inside_triangle'] = estimates['inside']
    candidates['geometry_ok'] = geometry_ok
    candidates['available_weight_mass'] = estimates['available_weight_mass']
    candidates['proposed_method'] = estimates['method']
    candidates['accepted'] = admitted
    candidates['decision'] = np.where(admitted, 'accepted',
        np.where(~geometry_ok, 'land_barrier_or_mask_conflict', 'zero_numeric_support'))
    centroid = np.einsum('ni,nij->nj', estimates['weights'], points)
    distance = Geod(ellps='WGS84').inv(target_xy[:,0], target_xy[:,1], centroid[:,0], centroid[:,1])[2]/1000.
    candidates['weighted_centroid_distance_km'] = distance
    candidates['sst_use_K'] = np.where(admitted, estimates['temperature_C']+273.15, np.nan)
    corner_errors = error_nodes[corner_ids]
    sd_available = ((~available) | (np.isfinite(corner_errors) & (corner_errors >= 0))).all(axis=1)
    bound = np.sum(estimates['weights'] * np.where(available, corner_errors, 0.), axis=1)
    candidates['sst_source_sd_bound_K'] = np.where(admitted & sd_available, bound, np.nan)
    for k in range(4):
        candidates[f'corner{k}_C'] = values[:,k]
        candidates[f'corner{k}_SD_K'] = corner_errors[:,k]
        candidates[f'weight{k}'] = estimates['weights'][:,k]
    # All variants and all references remain in the development pool.
    masked = targets[targets.kind.eq('mask') & targets.pool.eq('train') & targets.all_water_stencil].copy()
    ids = masked[[f'node{k}' for k in range(4)]].to_numpy()
    cv = temperature_nodes[ids]
    good = np.isfinite(cv).all(axis=1) & np.isfinite(masked.reference_K.to_numpy())
    masked = masked.loc[good].reset_index(drop=True)
    ids, cv = ids[good], cv[good]
    assert not set(masked.id).intersection(int(sid) for sid,r in records.items() if r['pool']=='test')
    variants = []
    original_weights = np.column_stack([(1-masked.u)*(1-masked.v), masked.u*(1-masked.v),
                                       (1-masked.u)*masked.v, masked.u*masked.v])
    full = np.sum(original_weights*cv, axis=1)+273.15
    for missing in range(4):
        hidden = cv.copy(); hidden[:,missing] = np.nan
        e = three_corner_temperature(masked.u, masked.v, hidden)
        restricted = original_weights.copy(); restricted[:,missing] = 0
        mass = restricted.sum(axis=1)
        safe = mass > 1e-12
        normalized = np.full(len(masked), np.nan)
        normalized[safe] = np.sum(restricted[safe]*np.where(np.isfinite(hidden[safe]),hidden[safe],0),axis=1)/mass[safe]+273.15
        filled_max = cv.copy(); filled_max[:,missing] = np.nanmax(hidden,axis=1)
        z = masked[KEYS+['season','in_R','reference_K']].copy()
        z['removed_corner'] = missing; z['inside_triangle'] = e['inside']
        z['hybrid_K'] = e['temperature_C']+273.15
        z['normalized_K'] = normalized; z['full_stencil_K'] = full
        z['maximum_fill_K'] = np.sum(original_weights*filled_max,axis=1)+273.15
        variants.append(z)
    validation = pd.concat(variants, ignore_index=True)
    validation['comparison_eligible'] = np.isfinite(validation[
        ['reference_K','hybrid_K','normalized_K','full_stencil_K','maximum_fill_K']]).all(axis=1)
    comparable = validation[validation.comparison_eligible]
    summaries = []
    for scope, frame in [('all_development', comparable), ('pilot_R', comparable[comparable.in_R])]:
        for location, subset in [('inside',frame[frame.inside_triangle]), ('outside',frame[~frame.inside_triangle]), ('all',frame)]:
            for method in ['hybrid_K','normalized_K','full_stencil_K','maximum_fill_K']:
                summaries.append({'scope':scope,'route':location,'method':method, **metrics(subset,method)})
    stratified = []
    for (in_R,season,inside), frame in comparable.groupby(['in_R','season','inside_triangle']):
        for method in ['hybrid_K','normalized_K','full_stencil_K','maximum_fill_K']:
            stratified.append({'in_R':bool(in_R),'season':int(season),'inside':bool(inside),
                               'method':method,**metrics(frame,method)})
    # Independently re-decode every source node used by candidates or diagnostics.
    print('Verifying used grid values against the byte-preserving NOAA cache', flush=True)
    nodes = pd.read_parquet(baseline/'nodes.parquet')
    needed = np.unique(np.concatenate([corner_ids.ravel(), ids.ravel()]))
    source_receipts = []
    with sqlite3.connect('file:'+str(baseline/'external_noaa.sqlite')+'?mode=ro', uri=True) as db:
        @lru_cache(maxsize=64)
        def cached(key):
            row = db.execute('select url,encoding,payload,sha256 from objects where key=?',(key,)).fetchone()
            if row is None:
                raise ValueError('Missing cached source object: '+key)
            raw = gzip.decompress(row[2]) if row[1]=='gzip' else row[2]
            if key.startswith('ncei_original/'):
                date = Path(key).stem
                expected = ('https://www.ncei.noaa.gov/data/sea-surface-temperature-optimum-interpolation/'
                            f'v2.1/access/avhrr/{date[:6]}/oisst-avhrr-v02r01.{date}.nc')
            else:
                expected = BUCKET+key
            assert row[0] == expected and hashlib.sha256(raw).hexdigest() == row[3]
            source_receipts.append({'key':key,'url':row[0],'sha256':row[3]})
            return raw
        for variable, stored in [('sst',temperature_nodes),('err',error_nodes)]:
            backends = pd.read_csv(baseline/f'node_{variable}_sources.csv').set_index('day').backend
            for day, group in nodes.loc[needed].groupby('day'):
                date = pd.to_datetime(int(day),unit='D',utc=True).strftime('%Y%m%d')
                if backends.loc[day] == 'NCEI_original_NetCDF':
                    import netCDF4
                    with netCDF4.Dataset('source',memory=cached('ncei_original/'+date+'.nc')) as nc:
                        decoded = np.ma.filled(nc[variable][0,0],np.nan)
                        found = decoded[group.j.to_numpy(),group.i.to_numpy()]
                        np.testing.assert_allclose(found,stored[group.index],rtol=0,atol=5e-6,equal_nan=True)
                else:
                    prefix = f'data/v2.1/avhrr-zarr/{date[:4]}/{date[4:6]}/oisst-avhrr-v02r01.{date}.zarr/'
                    metadata = json.loads(cached(prefix+'.zmetadata'))['metadata']
                    codes = (group.j//180)*8+group.i//180
                    for code, rows_at_chunk in group.groupby(codes):
                        chunk = decode_zarr_chunk(cached(prefix+f'{variable}/0.0.{int(code)//8}.{int(code)%8}'),
                            metadata[variable+'/.zarray'],metadata[variable+'/.zattrs'])
                        found = chunk[0,0,(rows_at_chunk.j%180).to_numpy(),(rows_at_chunk.i%180).to_numpy()]
                        np.testing.assert_allclose(found,stored[rows_at_chunk.index],rtol=0,atol=5e-6,equal_nan=True)
    # No output publication occurs until source checks and formula tests above pass.
    destination.mkdir()
    config = {'run_id':RUN_ID,'created_UTC':datetime.now(timezone.utc).isoformat(),
              'baseline':BASELINE,'contract_sha256':CONTRACT,'dependencies':dependencies,
              'inside_method':4,'outside_method':5,'numeric_tolerance':1e-12,
              'scope':'baseline coastal unknowns with exactly three finite source corners',
              'geometry':'target plus available-corner convex hull is water in both frozen masks',
              'source_masks':mask_hashes,'availability':'retrospective_only',
              'test_policy':'fixed rule application only; no tuning or test scoring',
              'validation':'four simulated corner removals per frozen accepted development mask'}
    write_json(destination/'config.json',config)
    count_ledger.to_parquet(destination/'coastal_scope.parquet',index=False)
    candidates.to_parquet(destination/'candidate_decisions.parquet',index=False)
    validation.to_parquet(destination/'development_corner_masks.parquet',index=False)
    write_json(destination/'validation_metrics.json',summaries)
    write_json(destination/'validation_strata.json',stratified)
    write_json(destination/'source_receipts.json',list({r['key']:r for r in source_receipts}.values()))
    output_records = []; changed_keys = []; independently_checked = 0
    for (pool,id), group in candidates[candidates.accepted].groupby(['pool','id']):
        old = pd.read_parquet(baseline/pool/f'{id}.parquet')
        patch = group[KEYS+['sst_use_K','sst_source_sd_bound_K']].copy()
        patch['sst_method'] = group.proposed_method.to_numpy(np.int8)
        patch['sst_reason'] = np.where(group.inside_triangle,'daily_oisst_three_corner_triangle',
                                      'daily_oisst_three_corner_outside_normalized')
        patch['sst_total_se_K'] = np.nan
        patch['sst_error_kind'] = np.where(np.isfinite(patch.sst_source_sd_bound_K),
            'daily_oisst_coastal_source_sd_upper_bound','coastal_source_sd_unavailable')
        patch['availability_scope'] = 'retrospective_only'
        patch['linear_anchor_left_source_obs'] = -1; patch['linear_anchor_right_source_obs'] = -1
        new = apply_coastal_patch(old,patch)
        changed = old.source_obs.isin(group.source_obs)
        pd.testing.assert_frame_equal(old.loc[~changed],new.loc[~changed],check_exact=True)
        pd.testing.assert_frame_equal(old[KEYS],new[KEYS],check_exact=True)
        assert list(old.columns) == list(new.columns) and len(new) == len(old)
        path = destination/pool/f'{id}.parquet'; path.parent.mkdir(exist_ok=True)
        new.to_parquet(path,index=False)
        reloaded = pd.read_parquet(path)
        pd.testing.assert_frame_equal(new,reloaded,check_exact=True)
        output_records.append({'id':int(id),'pool':pool,'path':f'{pool}/{id}.parquet',
                               'rows':len(new),'changed_rows':len(group),'sha256':file_sha256(path)})
        changed_keys.append(group[KEYS+['pool','in_R','proposed_method']])
        # Independent per-row equations; do not call the reconstruction primitive.
        for row in group.itertuples(index=False):
            vals = np.array([getattr(row,f'corner{k}_C') for k in range(4)])
            use = np.isfinite(vals)
            if row.inside_triangle:
                matrix = np.column_stack([VERTICES[use],np.ones(3)])
                coefficient = np.linalg.solve(matrix,vals[use])
                expected_C = float(np.dot([row.u,row.v,1.],coefficient))
            else:
                w = np.array([(1-row.u)*(1-row.v),row.u*(1-row.v),(1-row.u)*row.v,row.u*row.v])[use]
                expected_C = float(np.dot(w,vals[use])/w.sum())
            assert np.isclose(expected_C+273.15,row.sst_use_K,rtol=0,atol=1e-10)
            assert vals[use].min()-1e-10 <= expected_C <= vals[use].max()+1e-10
            independently_checked += 1
    changes = (pd.concat(changed_keys,ignore_index=True) if changed_keys else
               pd.DataFrame(columns=KEYS+['pool','in_R','proposed_method']))
    changes.to_parquet(destination/'changed_keys.parquet',index=False)
    write_json(destination/'output_manifest.json',output_records)
    # Reconcile unchanged baseline counts and document remaining causes separately.
    summary = candidates.groupby(['pool','inside_triangle','decision']).agg(
        hours=('id','size'),IDs=('id','nunique'),in_R_hours=('in_R','sum')).reset_index()
    summary.to_csv(destination/'coverage.csv',index=False)
    all_after = pd.read_csv(baseline/'unknown_reasons.csv')
    remaining = []
    for (pool,why), g in all_after.groupby(['pool','reason']):
        subtract = changes[changes.pool.eq(pool)] if why.startswith('land_barrier_or_coastal') else changes.iloc[:0]
        remaining.append({'pool':pool,'reason':why,'hours':int(g.hours.sum())-len(subtract),
                          'in_R_hours':int(g.in_R_hours.sum())-int(subtract.in_R.sum())})
    pd.DataFrame(remaining).to_csv(destination/'remaining_unknown_reasons.csv',index=False)
    examples = []
    for inside in [True,False]:
        for scope in [True,False]:
            example = candidates[candidates.accepted & candidates.inside_triangle.eq(inside) & candidates.in_R.eq(scope)].head(1)
            if len(example):
                row = example.iloc[0]
                examples.append({'id':int(row.id),'source_obs':int(row.source_obs),'pool':row.pool,
                    'in_R':bool(row.in_R),'method':int(row.proposed_method),
                    'UTC':pd.to_datetime(row.time,unit='s',utc=True).isoformat(),
                    'lat':float(row.lat),'lon':float(row.lon),'u':float(row.u),'v':float(row.v),
                    'corners_C':[None if not np.isfinite(row[f'corner{k}_C']) else float(row[f'corner{k}_C']) for k in range(4)],
                    'weights':[float(row[f'weight{k}']) for k in range(4)],
                    'sst_use_K':float(row.sst_use_K),'available_weight_mass':float(row.available_weight_mass)})
    write_json(destination/'worked_examples.json',examples)
    print('Rechecking immutable inputs after output generation',flush=True)
    verify_frozen(root,dependencies)
    with cf.ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(check_id,records.items())) == rows
    verification = {'status':'passed','all_canonical_file_hashes_unchanged':True,
                    'all_130_fields_and_39107061_rows_retained':True,
                    'all_baseline_sidecar_hashes_unchanged':True,
                    'unaffected_sidecar_rows_exactly_preserved':True,
                    'train_test_assignment_unchanged':True,
                    'independent_formula_checks':independently_checked,
                    'decoded_source_nodes_per_variable':len(needed),
                    'source_object_count':len({r['key'] for r in source_receipts}),
                    'additional_temperatures':len(changes),'additional_in_R':int(changes.in_R.sum()),
                    'remaining_unknown':37986-len(changes),'remaining_unknown_in_R':1012-int(changes.in_R.sum()),
                    'config_sha256':file_sha256(destination/'config.json')}
    write_json(destination/'verification.json',verification)
    coverage_lines = ['| Pool | Route | Added temperatures | Added in R |','|---|---|---:|---:|']
    for (pool,inside), g in candidates[candidates.accepted].groupby(['pool','inside_triangle']):
        coverage_lines.append(f"| {pool} | {'Triangle linear' if inside else 'Outside normalized'} | {len(g):,} | {int(g.in_R.sum()):,} |")
    validation_lines = ['| Route | Method | Simulated cases | IDs | MAE K | RMSE K | Bias K |',
                        '|---|---|---:|---:|---:|---:|---:|']
    for s in summaries:
        if s['scope']=='all_development' and s['route'] in ['inside','outside']:
            validation_lines.append(f"| {s['route']} | {s['method']} | {s['n']:,} | {s['IDs']} | {s['MAE_K']:.4f} | {s['RMSE_K']:.4f} | {s['bias_K']:.4f} |")
    report = f'''# Three-corner coastal SST extension

This run executes the user-approved inside-triangle linear / outside-triangle
normalized-weight policy. It is retrospective temperature reconstruction,
not a destination forecast or proof of an optimal imputation method.
Data Contract v1.0 and the canonical release are unchanged.

## Coverage

{chr(10).join(coverage_lines)}

Added **{len(changes):,}** temperature estimates, including **{int(changes.in_R.sum()):,}**
in pilot R. Remaining unknowns: **{37986-len(changes):,}** across retained tracks,
including **{1012-int(changes.in_R.sum()):,}** in R. Only exactly-three-corner
baseline coastal unknowns were considered. Other unresolved classes remain.
`coverage.csv` and `candidate_decisions.parquet` distinguish accepted estimates,
land/mask refusals, geometry, original available weight and centroid displacement.
`coastal_scope.parquet` also records cases outside the three-corner scope.

The target plus its three source centres must have an all-water convex hull
under both frozen masks. This replaces the old full-rectangle test only for
this extension. No cross-land blend, new neighbour search, maximum-temperature
fill or second source acquisition was performed. Boundary points use triangular
weights. Outside estimates use only the original available bilinear weights;
renormalization does not recreate missing spatial information.

## Development diagnostic

{chr(10).join(validation_lines)}

Each eligible frozen development mask is evaluated under four artificial corner
removals. These variants share source hours and IDs and are **not independent
samples**. The references are accepted GDP temperatures; OISST may assimilate
buoys, so they are not independent physical truth. The original stencils pass
the old all-water rule, meaning this diagnostic does **not** reproduce real
coastal land masking, validate all real missing cases or establish coastal
forecast accuracy. Method differences are compared on identical cases within
each route. Seasonal and R strata are in `validation_strata.json`. Final-test
temperatures were not scored or used to select methods or thresholds.

The two routes remain distinctly labelled. A numerical completion is not an
accuracy guarantee; small available weight or displaced weighted centroids
identify weak support for later sensitivity analysis. No fitted bias correction
or post-hoc method selection was made from these diagnostics.

## Preservation, uncertainty and reading

All 3,741 original ID files, all 130 fields and all 39,107,061 records retain
their original hashes. Every baseline temperature-sidecar file retains its
hash. Complete replacement temperature sidecars exist only for the {len(output_records)}
changed IDs; their other rows, keys, fields and pool assignments are exact.
Other IDs inherit their explicitly named baseline sidecar.

Methods 0--3 retain baseline meanings; 4 is three-corner triangular linear and
5 is three-corner outside normalized. Source-only SD upper bounds use the same
three weights. They omit representation/interpolation error. Total reconstructed
SE remains unknown. Original GDP temperatures, components, QC and errors are
never overwritten, and source-only bounds are not relabelled as total SE.
Temperature unknowns do not by themselves disqualify core position pairs.

```python
from data3001.sst_coastal import read_sst_track
track = read_sst_track(22165)
# For authorized fixed-rule inspection only: allow_test=True.
```

This returns every original feature plus the chosen sidecar without requiring
users to select between versions manually. It does not authorize all fields as
forecast-time predictors. Daily final OISST remains retrospective.

`config.json` pins inputs, code, tolerance, source masks and the baseline.
`source_receipts.json` identifies checksum-verified original cached objects;
used node temperatures and source errors were independently decoded offline.
`verification.json`, `changed_keys.parquet`, `output_manifest.json` and
`worked_examples.json` supply preservation and equation checks. No Git commit
or push was performed.
'''
    (destination/'REPORT.md').write_text(report)
    files = [p for p in destination.rglob('*') if p.is_file()]
    write_json(destination/'artifact_manifest.json',
               {str(p.relative_to(destination)):file_sha256(p) for p in files})
    print(json.dumps(verification,indent=2),flush=True)
    print('Report:',destination/'REPORT.md',flush=True)


if __name__ == '__main__':
    run()
