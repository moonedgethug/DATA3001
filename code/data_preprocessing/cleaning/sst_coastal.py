"""Approved three-corner SST estimates, separate from the frozen baseline."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

VERTICES = np.array([[0., 0.], [1., 0.], [0., 1.], [1., 1.]])
TOLERANCE = 1e-12


def water_support_hull_ok(target_xy, three_points, land_masks):
    """Require the target and its available-corner hull to avoid every land mask."""
    import shapely
    target_xy, three_points = np.asarray(target_xy,float), np.asarray(three_points,float)
    if three_points.shape != (len(target_xy),3,2) or target_xy.shape != (len(target_xy),2):
        raise ValueError('Expected a 2-D target and three source points per case')
    if not np.isfinite(target_xy).all() or not np.isfinite(three_points).all():
        raise ValueError('Nonfinite geometry')
    hull = shapely.convex_hull(shapely.multipoints(
        np.concatenate([three_points,target_xy[:,None,:]],axis=1)))
    accepted = np.ones(len(target_xy),bool)
    for land in land_masks:
        shapely.prepare(land)
        accepted &= ~shapely.intersects(land,hull)
    return accepted


def three_corner_temperature(u, v, temperatures):
    """Return inside-triangle linear / outside-triangle normalized estimates.

    Geometry and source admission are separate caller responsibilities. Method
    4 is triangular; 5 is normalized outside support; 3 is numerically unknown.
    This is not a claim that either route recovers a missing sensor reading.
    """
    u, v = np.asarray(u, float).reshape(-1), np.asarray(v, float).reshape(-1)
    values = np.asarray(temperatures, float)
    if values.shape != (len(u), 4) or len(v) != len(u):
        raise ValueError('Expected one four-corner row per target position')
    if (not np.isfinite(u).all() or not np.isfinite(v).all()
            or np.any((u < 0) | (u > 1) | (v < 0) | (v > 1))):
        raise ValueError('Target is outside its original source rectangle')
    valid = np.isfinite(values)
    if np.any(valid.sum(axis=1) != 3):
        raise ValueError('Exactly three finite source corners are required')
    bilinear = np.column_stack([(1-u)*(1-v), u*(1-v), (1-u)*v, u*v])
    restricted = np.where(valid, bilinear, 0.)
    mass = restricted.sum(axis=1)
    weights = np.zeros_like(values)
    inside = np.zeros(len(u), bool)
    method = np.full(len(u), 3, np.int8)
    for missing in range(4):
        take = np.flatnonzero(~valid[:, missing])
        if not len(take):
            continue
        indices = np.flatnonzero(np.arange(4) != missing)
        matrix = np.vstack([VERTICES[indices].T, np.ones(3)])
        barycentric = np.linalg.solve(matrix, np.vstack([u[take], v[take], np.ones(len(take))])).T
        enclosed = (barycentric >= -TOLERANCE).all(axis=1)
        inner = take[enclosed]
        if len(inner):
            clipped = np.maximum(barycentric[enclosed], 0.)
            weights[np.ix_(inner, indices)] = clipped / clipped.sum(axis=1, keepdims=True)
            inside[inner] = True
            method[inner] = 4
        outer = take[~enclosed & (mass[take] > TOLERANCE)]
        weights[outer] = restricted[outer] / mass[outer, None]
        method[outer] = 5
    temperature = np.sum(weights * np.where(valid, values, 0.), axis=1)
    temperature[method == 3] = np.nan
    return {'temperature_C': temperature, 'weights': weights, 'inside': inside,
            'method': method, 'available_weight_mass': mass}


def apply_coastal_patch(base, patch):
    """Update only qualified unknown sidecar keys; preserve all rows/columns."""
    keys = ['id', 'source_obs']
    allowed = {'sst_use_K', 'sst_method', 'sst_reason', 'availability_scope',
               'linear_anchor_left_source_obs', 'linear_anchor_right_source_obs',
               'sst_source_sd_bound_K', 'sst_total_se_K', 'sst_error_kind'}
    if (not set(keys).issubset(base) or not set(keys).issubset(patch)
            or not set(patch).difference(keys).issubset(allowed)
            or not set(patch).issubset(base)):
        raise ValueError('Only existing temperature-sidecar fields may be patched')
    if base.duplicated(keys).any() or patch.duplicated(keys).any():
        raise ValueError('Duplicate temperature keys')
    index = pd.MultiIndex.from_frame(base[keys])
    locations = index.get_indexer(pd.MultiIndex.from_frame(patch[keys]))
    if np.any(locations < 0):
        raise ValueError('Patch contains a key absent from the baseline')
    old = base.iloc[locations]
    if not old.sst_method.eq(3).all() or not old.sst_use_K.isna().all():
        raise ValueError('An accepted existing temperature cannot be overwritten')
    if (not patch.sst_method.isin([4, 5]).all()
            or not np.isfinite(patch.sst_use_K).all()):
        raise ValueError('Patch requires finite estimates from approved routes')
    out = base.copy(deep=True)
    for column in patch.columns.difference(keys):
        out.iloc[locations, out.columns.get_loc(column)] = patch[column].to_numpy()
    return out


def read_sst_track(id, *, run='sst_coastal_extension_20261017_v1', allow_test=False):
    """Read all canonical features plus an explicitly versioned SST sidecar."""
    from data3001.dataset import read_track, manifest
    from data3001.paths import project_paths, file_sha256
    native = read_track(id, allow_test=allow_test)
    root = project_paths().root
    directory = root / 'results/runs' / run
    if not directory.resolve().is_relative_to((root / 'results/runs').resolve()):
        raise ValueError('Temperature view must be a registered local run')
    receipt = json.loads((directory / 'verification.json').read_text())
    if receipt['status'] != 'passed':
        raise ValueError('Temperature view has not passed verification')
    if file_sha256(directory / 'config.json') != receipt['config_sha256']:
        raise ValueError('Temperature-view configuration changed')
    config = json.loads((directory / 'config.json').read_text())
    pool = manifest()['records'][str(int(id))]['pool']
    relative = f'{pool}/{int(id)}.parquet'
    outputs = {r['path']: r for r in json.loads((directory / 'output_manifest.json').read_text())}
    if relative in outputs:
        path = directory / relative
        expected = outputs[relative]['sha256']
    else:
        baseline = root / config['baseline']
        record = next(r for r in json.loads((baseline / 'output_manifest.json').read_text())
                      if r['id'] == int(id))
        path = root / record['path']
        expected = record['sha256']
    if path.is_symlink() or file_sha256(path) != expected:
        raise ValueError('Temperature sidecar changed')
    extra = pd.read_parquet(path)
    out = native.merge(extra, on=['id', 'source_obs'], validate='one_to_one', how='left', indicator=True)
    if len(out) != len(native) or not out['_merge'].eq('both').all():
        raise ValueError('Temperature view does not cover the canonical keys exactly')
    out = out.drop(columns='_merge')
    out.attrs.update(native.attrs)
    out.attrs['temperature_run'] = run
    return out
