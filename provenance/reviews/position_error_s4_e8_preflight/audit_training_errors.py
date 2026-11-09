"""Read-only metadata audit of frozen E7 fitting keys; no forecasts or fitting.

Run from work_place. Writes only this review's aggregate JSON receipt.
Never reads outer labels or files in data/test.
"""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Geod

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = 'exact_origin_s4_e7_primary_20261105T074326_829211Z'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def quantiles(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return {str(q): float(np.quantile(values, q)) for q in
            [0, .01, .05, .5, .9, .95, .99, 1]} if len(values) else {}


def describe(frame):
    result = {'rows': len(frame), 'IDs': int(frame.id.nunique())}
    geod = Geod(ellps='WGS84')
    for axis in ['lon', 'lat']:
        values = frame['err_' + axis].to_numpy(float)
        valid = np.isfinite(values) & (values >= 0)
        positive = valid & (values > 0)
        lon = frame.lon_normalized.to_numpy(float)
        lat = frame.lat.to_numpy(float)
        metres = np.full(len(frame), np.nan)
        ok = valid & (values < (180 if axis == 'lon' else 90))
        if axis == 'lat':
            ok &= np.abs(lat) + values < 90
        _, _, metres[ok] = geod.inv(
            lon[ok], lat[ok],
            lon[ok] + (values[ok] if axis == 'lon' else 0),
            lat[ok] + (values[ok] if axis == 'lat' else 0))
        result[axis] = {
            'negative': int((values < 0).sum()),
            'nonfinite': int((~np.isfinite(values)).sum()),
            'zero': int((values == 0).sum()),
            'positive': int(positive.sum()),
            'nonnegative_degrees_quantiles': quantiles(values[valid]),
            'raw_amplitude_metres_quantiles': quantiles(metres),
            'under_1m': int((metres < 1).sum()),
            'under_10m': int((metres < 10).sum()),
            'over_1000m': int((metres > 1000).sum()),
        }
    result['both_positive'] = int((
        (frame.err_lon > 0) & np.isfinite(frame.err_lon)
        & (frame.err_lat > 0) & np.isfinite(frame.err_lat)).sum())
    return result


def main():
    started = time.monotonic()
    source = ROOT / 'results/runs' / RUN / 'training_coordinates.parquet'
    manifest_path = ROOT / 'configs/dataset_manifest.json'
    pairs = pd.read_parquet(source)
    manifest = json.loads(manifest_path.read_text())
    frames, receipts = [], []
    for ident, group in pairs.groupby('id', sort=True):
        record = manifest['records'][str(ident)]
        assert record['pool'] == 'train'
        assert record['path'].startswith('data/train/')
        path = ROOT / record['path']
        sha = digest(path)
        assert sha == record['sha256']
        keys = np.unique(np.r_[group.origin_source_obs.values,
                               group.endpoint_source_obs.dropna().values]).astype('int64')
        frame = pd.read_parquet(path, columns=[
            'source_obs', 'time', 'lon_normalized', 'lat', 'err_lon', 'err_lat'],
            filters=[('source_obs', 'in', keys.tolist())])
        assert not frame.source_obs.duplicated().any()
        assert len(frame) == len(keys)
        frame['id'] = ident
        frames.append(frame)
        receipts.append({'id': int(ident), 'path': record['path'],
                         'sha256': sha, 'selected_rows': len(frame)})
    observations = pd.concat(frames, ignore_index=True)
    result = {
        'status': 'read_only_metadata_audit_no_model_run', 'date': '2026-11-06',
        'source_run': RUN, 'fit_coordinates_sha256': digest(source),
        'manifest_sha256': digest(manifest_path),
        'source_attributes': {k: manifest['source_field_attributes'][k]
                              for k in ['err_lon', 'err_lat']},
        'training_pairs': len(pairs), 'training_IDs': int(pairs.id.nunique()),
        'unique_selected_training_observations': describe(observations),
        'source_receipts': receipts, 'outer_endpoint_errors_read': False,
        'locked_final_test_read': False,
        'training_exit_count': int(pairs.outside.sum()),
    }
    joined = {}
    for kind, key, loncol, latcol in [
        ('start', 'origin_source_obs', 'lon', 'lat'),
        ('endpoint', 'endpoint_source_obs', 'endpoint_lon', 'endpoint_lat')]:
        frame = pairs.merge(observations, left_on=['id', key],
                            right_on=['id', 'source_obs'], validate='many_to_one',
                            suffixes=('_pair', ''))
        assert len(frame) == len(pairs)
        assert np.allclose(frame[loncol], frame.lon_normalized, rtol=0, atol=1e-12)
        lat = frame.lat_pair if latcol == 'lat' else frame[latcol]
        assert np.allclose(lat, frame.lat, rtol=0, atol=1e-12)
        # Parquet timestamps are milliseconds; normalize units explicitly.
        expected = frame.origin_time_UTC.dt.as_unit('ns').astype('int64').to_numpy() / 1e9
        if kind == 'endpoint':
            expected = frame.matched_endpoint_epoch.to_numpy()
        assert np.array_equal(expected, frame.time.to_numpy())
        result[kind] = describe(frame)
        joined[kind] = frame
    _, _, distance = Geod(ellps='WGS84').inv(
        pairs.lon, pairs.lat, pairs.endpoint_lon, pairs.endpoint_lat)
    result['observed_7day_displacement_km'] = quantiles(np.asarray(distance) / 1000)
    result['by_departure_era'] = {}
    frame = joined['endpoint']
    years = frame.origin_time_UTC.dt.year
    for lo, hi in [(2001, 2006), (2007, 2012), (2013, 2019)]:
        result['by_departure_era'][f'{lo}-{hi}'] = describe(frame.loc[years.between(lo, hi)])
    result['elapsed_seconds'] = time.monotonic() - started
    (OUT / 'training_error_scale_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in [
        'training_pairs', 'training_IDs', 'training_exit_count', 'start', 'endpoint',
        'observed_7day_displacement_km', 'elapsed_seconds']}, indent=2))


if __name__ == '__main__':
    main()
