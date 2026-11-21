"""Verified exact coordinates, with held-out endpoints released only to scoring."""
import json
import numpy as np
import pandas as pd
import shapely as sh
from shapely.geometry import shape

from data3001.paths import file_sha256
from data3001.feature_pruning import qualification_arrays
from data3001.preprocessing.prep_core import cells
from data3001.modelling.baselines.seasonal_conditioning_s4_e1_inputs import KEY
from data3001.modelling.baselines.seasonal_information_s4_e3_pipeline import permitted as role_inputs

ORIGIN = ['id', 'origin_source_obs']
TRACK = ['id', 'source_obs', 'time', 'cell_1', 'lon_normalized', 'lat']
FLAGS = ['analytical_row', 'position_ok', 'mapping_ok']
REFERENCE_FILES = ['summary.csv', 'outer_roster.parquet', 'C_outer_donors.parquet', 'case_scores.parquet']


def permitted(paths, cfg):
    base = paths.root / 'results/runs' / cfg['reference_e4']
    return role_inputs(paths, cfg) + [base / f for f in REFERENCE_FILES] + [paths.root / 'provenance/runs' / base.name / 'outputs.json']


def verify_reference(paths, cfg):
    base = paths.root / 'results/runs' / cfg['reference_e4']
    receipt = json.loads((paths.root / 'provenance/runs' / base.name / 'outputs.json').read_text())
    assert receipt['completed'] and not receipt['final_test_access']
    inventory = {}
    for name in REFERENCE_FILES:
        f = base / name
        rel = f.relative_to(paths.root).as_posix()
        digest = file_sha256(f)
        assert receipt['output_sha256'][rel] == digest
        inventory[rel] = digest
    return base, inventory


def coordinates(paths, guard, keys, inventory):
    """Return only requested source rows; no labels enter this function."""
    assert set(keys.columns) == {'id', 'source_obs'} and not keys.duplicated().any()
    if keys.empty:
        return pd.DataFrame({name:pd.Series(dtype='int64' if name in ['id','source_obs','cell_1'] else 'float64') for name in TRACK})
    mp = paths.asset('current_dataset_manifest', verify=True)
    qp = paths.asset('current_qualification_manifest', verify=True)
    manifest, qualification = json.loads(mp.read_text()), json.loads(qp.read_text())
    for f in [mp, qp]:
        inventory[f.relative_to(paths.root).as_posix()] = file_sha256(f)
    parts = []
    for ident, group in keys.groupby('id', sort=True):
        sid = str(int(ident))
        record, side = manifest['records'][sid], qualification['records'][sid]
        assert record['pool'] == side['pool'] == 'train'
        canonical, quality = paths._resolve(record['path']), paths._resolve(side['path'])
        assert canonical == paths.data_root / 'train' / (sid + '.parquet')
        guard.input_files.update([canonical, quality])
        assert file_sha256(canonical) == record['sha256']
        with canonical.open('rb') as stream:
            frame = pd.read_parquet(stream, columns=TRACK)
        assert len(frame) == record['rows'] and frame.id.eq(ident).all() and not frame.source_obs.duplicated().any()
        frame.attrs['data3001'] = {'pool': 'train'}
        flags = qualification_arrays(ident, frame, FLAGS, allow_test=False)
        pos = pd.Index(frame.source_obs).get_indexer(group.source_obs)
        assert (pos >= 0).all()
        for name in FLAGS:
            assert np.asarray(flags[name])[pos].all(), (ident, name)
        selected = frame.iloc[pos].copy()
        assert np.isfinite(selected[['lon_normalized', 'lat', 'time']]).all().all()
        assert selected.lat.between(-90, 90, inclusive='left').all()
        assert np.array_equal(cells(selected.lon_normalized.to_numpy(), selected.lat.to_numpy()), selected.cell_1)
        parts.append(selected)
        inventory[record['path']], inventory[side['path']] = record['sha256'], side['sha256']
    return pd.concat(parts, ignore_index=True).sort_values(['id', 'source_obs']).reset_index(drop=True)


def attach_starts(frame, positions):
    p = positions.rename(columns={'source_obs': 'origin_source_obs', 'lon_normalized': 'lon', 'cell_1': 'source_cell', 'time': 'source_epoch'})
    out = frame.merge(p, on=ORIGIN, how='left', validate='many_to_one', sort=False)
    epoch = (out.origin_time_UTC - pd.Timestamp('1970-01-01', tz='UTC')).dt.total_seconds()
    assert len(out) == len(frame) and np.array_equal(out.source_epoch, epoch)
    assert np.array_equal(out.source_cell, out.origin_cell_1)
    return out.drop(columns=['source_cell', 'source_epoch'])


def attach_endpoints(frame, positions):
    out = frame.copy()
    out['endpoint_lon'] = np.nan
    out['endpoint_lat'] = np.nan
    out['destination_cell_05'] = -2
    sel = ~out.outside
    p = positions.rename(columns={'source_obs': 'endpoint_source_obs'})
    z = out.loc[sel, ['id', 'endpoint_source_obs', 'target_epoch', 'destination_cell_1']].merge(
        p, on=['id', 'endpoint_source_obs'], validate='many_to_one', how='left', sort=False)
    assert np.array_equal(z.time, z.target_epoch) and np.array_equal(z.cell_1, z.destination_cell_1)
    fine = cells(z.lon_normalized.to_numpy(), z.lat.to_numpy(), res=.5)
    parent = ((fine // 720) // 2) * 360 + ((fine % 720) // 2)
    assert np.array_equal(parent, z.destination_cell_1)
    out.loc[sel, 'endpoint_lon'] = z.lon_normalized.to_numpy()
    out.loc[sel, 'endpoint_lat'] = z.lat.to_numpy()
    out.loc[sel, 'destination_cell_05'] = fine
    out['destination_cell_05'] = out.destination_cell_05.astype('int64')
    assert np.array_equal(out.destination_cell_1.eq(-2), out.outside)
    return out


def prepare_positions(paths, guard, outer, inventory):
    """Training endpoints and all query starts; never request outer endpoint keys."""
    train = outer['train'].query('horizon_days == 7').sort_values(KEY).reset_index(drop=True)
    valid = outer['validation'].query('horizon_days == 7').sort_values(KEY).reset_index(drop=True)
    starts = pd.concat([train, valid], ignore_index=True)[ORIGIN].drop_duplicates().rename(columns={'origin_source_obs': 'source_obs'})
    ends = train.loc[~train.outside, ['id', 'endpoint_source_obs']].rename(columns={'endpoint_source_obs': 'source_obs'})
    keys = pd.concat([starts, ends], ignore_index=True).drop_duplicates()
    coords = coordinates(paths, guard, keys, inventory)
    train = attach_endpoints(attach_starts(train, coords), coords)
    # Only origin information can cross the forecast interface.
    query_columns = KEY + ['origin_cell_1', 'origin_time_UTC']
    queries = attach_starts(valid[query_columns], coords)
    region = shape(json.loads(paths.asset('release_R', verify=True).read_text())['features'][0]['geometry'])
    domain = shape(json.loads(paths.asset('transport_D', verify=True).read_text())['features'][0]['geometry'])
    for f in [train, queries]:
        assert sh.intersects_xy(region, f.lon.to_numpy(), f.lat.to_numpy()).all()
        assert sh.intersects_xy(domain, f.lon.to_numpy(), f.lat.to_numpy()).all()
    return train, queries


def outer_targets(paths, guard, validation, inventory):
    labels = validation.query('horizon_days == 7').sort_values(KEY).reset_index(drop=True)
    keys = labels.loc[~labels.outside, ['id', 'endpoint_source_obs']].rename(columns={'endpoint_source_obs': 'source_obs'}).drop_duplicates()
    coords = coordinates(paths, guard, keys, inventory)
    return attach_endpoints(labels, coords)
