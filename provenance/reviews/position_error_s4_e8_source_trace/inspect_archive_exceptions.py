"""Source audit of selected frozen training endpoints, including invalid errors.

No forecasts, fitting, validation labels, or canonical writes. The selector is
used for keys only; values are reloaded at full precision from canonical files.
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


def main():
    started = time.monotonic()
    selection = pd.read_json(OUT / 'selected_training_keys.json')
    pairs = pd.read_parquet(ROOT / 'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/training_coordinates.parquet')
    valid_keys = set(zip(pairs.id, pairs.endpoint_source_obs))
    assert set(zip(selection.id, selection.source_obs)) <= valid_keys
    manifest = json.loads((ROOT / 'configs/dataset_manifest.json').read_text())
    result = {'url': URL, 'scope': 'selected frozen training endpoints only',
              'selection_note': 'Spread observations plus all negative and large endpoint-error anomalies; not a random population estimate.',
              'samples': [], 'unmatched': []}
    with fsspec.open(URL, 'rb', block_size=262144, cache_type='blockcache',
                    client_kwargs={'timeout': aiohttp.ClientTimeout(total=30)}).open() as stream:
        with h5py.File(stream, 'r') as h:
            ids = h['ID' if 'ID' in h else 'id'][:].ravel().astype('int64')
            sizes = h['rowsize'][:].ravel().astype('int64')
            offsets = np.r_[0, np.cumsum(sizes)]
            for ident, group in selection.groupby('id', sort=True):
                entry = manifest['records'][str(ident)]
                assert entry['pool'] == 'train'
                local = pd.read_parquet(ROOT / entry['path'],
                    columns=['source_obs', 'time', 'lon', 'lat', 'err_lon', 'err_lat'],
                    filters=[('source_obs', 'in', group.source_obs.tolist())])
                assert len(local) == len(group)
                found = np.flatnonzero(ids == ident)
                if len(found) != 1:
                    result['unmatched'].append({'id': int(ident), 'reason': 'ID absent or duplicate', 'rows': len(local)})
                    continue
                a, b = offsets[found[0]:found[0] + 2]
                times = h['time'][a:b].ravel()
                for row in local.itertuples(index=False):
                    hit = np.flatnonzero(times == row.time)
                    if len(hit) != 1:
                        result['unmatched'].append({'id': int(ident), 'source_obs': int(row.source_obs), 'reason': 'timestamp absent or duplicate'})
                        continue
                    j = int(a + hit[0])
                    item = {'id': int(ident), 'source_obs': int(row.source_obs),
                            'epoch': float(row.time), 'archive_index': j}
                    for var in ['lon', 'lat', 'err_lon', 'err_lat']:
                        name = var if var in h else {'lon': 'longitude', 'lat': 'latitude'}[var]
                        value = float(h[name][j]); canonical = float(getattr(row, var))
                        item[var] = {'archive_raw': value, 'canonical': canonical,
                            'ratio': value / canonical if np.isfinite(canonical) and canonical != 0 else None}
                    result['samples'].append(item)
                print(VERSION, 'completed ID', ident, len(local), flush=True)
    result['elapsed_seconds'] = time.monotonic() - started
    (OUT / f'ncei_{VERSION.replace(".", "_")}_exceptions.json').write_text(json.dumps(result, indent=2, allow_nan=True) + '\n')
    print('saved', len(result['samples']), 'matched', len(result['unmatched']), 'unmatched', flush=True)


if __name__ == '__main__':
    main()
