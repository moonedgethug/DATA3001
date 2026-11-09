"""Read selected training observations from official archives via byte ranges.

Source audit only. Does not fit a model, edit canonical data, or read final-test
observations. Reads trajectory ID/count metadata, then three approved IDs only.
Temporary h5py dependency: /tmp/data3001-error-trace-deps.
"""
import sys
sys.path.insert(0, '/tmp/data3001-error-trace-deps')
import json
import time
from pathlib import Path
import aiohttp
import fsspec
import h5py
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
VERSION = sys.argv[1]
FILENAME = 'gdp_v2.00.nc' if VERSION == '1.1' else 'gdp_hourly.nc'
URL = f'https://www.ncei.noaa.gov/data/oceans/archive/arc0199/0248584/{VERSION}/data/0-data/{FILENAME}'
PAIRS = ROOT / 'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/training_coordinates.parquet'
IDS = [7647, 99004, 300234066710170]


def attrs(obj):
    return {k: str(v) for k, v in obj.attrs.items()
            if k not in ['DIMENSION_LIST', '_Netcdf4Coordinates', 'REFERENCE_LIST']}


def main():
    started = time.monotonic()
    pairs = pd.read_parquet(PAIRS)
    assert set(IDS) <= set(pairs.id.unique())
    record = {'url': URL, 'archive_version': VERSION, 'scope': 'training IDs only',
              'global_attributes': {}, 'variables': {}, 'comparisons': []}
    with fsspec.open(URL, 'rb', block_size=262144, cache_type='blockcache',
                    client_kwargs={'timeout': aiohttp.ClientTimeout(total=30)}).open() as stream:
        record['remote_size_bytes'] = stream.size
        with h5py.File(stream, 'r') as h:
            record['keys'] = list(h.keys())
            record['global_attributes'] = attrs(h)
            for name in ['ID', 'id', 'rowsize', 'time', 'err_lon', 'err_lat', 'lon', 'lat', 'longitude', 'latitude']:
                if name in h:
                    record['variables'][name] = {'shape': h[name].shape,
                        'dtype': str(h[name].dtype), 'attributes': attrs(h[name])}
            print(VERSION, 'metadata read', flush=True)
            id_name = 'ID' if 'ID' in h else 'id'
            ids = h[id_name][:].ravel().astype('int64')
            sizes = h['rowsize'][:].ravel().astype('int64')
            offsets = np.r_[0, np.cumsum(sizes)]
            for ident in IDS:
                matches = np.where(ids == ident)[0]
                assert len(matches) == 1
                a, b = offsets[matches[0]:matches[0] + 2]
                times = h['time'][a:b].ravel()
                candidates = pairs[pairs.id == ident]
                chosen = candidates.iloc[np.unique(np.linspace(0, len(candidates)-1, 20).astype(int))]
                source = pd.read_parquet(ROOT / f'data/train/{ident}.parquet',
                    columns=['source_obs', 'time', 'err_lon', 'err_lat', 'lon', 'lat'],
                    filters=[('source_obs', 'in', chosen.endpoint_source_obs.tolist())])
                sample = []
                for row in source.itertuples(index=False):
                    hit = np.flatnonzero(times == row.time)
                    result = {'source_obs': int(row.source_obs), 'epoch': float(row.time),
                              'timestamp_matches': len(hit)}
                    if len(hit) == 1:
                        j = int(a + hit[0])
                        result['archive_index'] = j
                        for var in ['lon', 'lat', 'err_lon', 'err_lat']:
                            name = var if var in h else {'lon': 'longitude', 'lat': 'latitude'}[var]
                            value = float(h[name][j])
                            local = float(getattr(row, var))
                            result[var] = {'archive_raw': value, 'canonical': local,
                                'ratio_archive_to_canonical': value/local if local != 0 else None}
                    sample.append(result)
                record['comparisons'].append({'id': ident, 'archive_trajectory_index': int(matches[0]),
                    'archive_start': int(a), 'archive_count': int(b-a), 'samples': sample})
                print(VERSION, ident, 'samples', len(sample), 'example', sample[0], flush=True)
        record['range_cache_stats'] = {'blocks': stream.cache.cache_info().currsize,
                                       'block_size': 262144} if hasattr(stream.cache, 'cache_info') else {}
    record['elapsed_seconds'] = time.monotonic() - started
    (OUT / f'ncei_{VERSION.replace(".", "_")}_comparison.json').write_text(
        json.dumps(record, indent=2, default=str, allow_nan=True) + '\n')
    print(VERSION, 'saved', record['elapsed_seconds'], flush=True)


if __name__ == '__main__':
    main()
