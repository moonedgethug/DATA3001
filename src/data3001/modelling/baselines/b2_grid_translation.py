"""Contract-defined B2 partitions, empirical counts and support; no fallbacks."""
import numpy as np
import pandas as pd

from data3001.preprocessing.prep_core import cells

KEY = ['id', 'origin_source_obs', 'horizon_days']
EXIT = -2


def translated_cells(lon, lat, offset=(0., 0.)):
    lon, lat = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
    if lon.shape != lat.shape or lon.ndim != 1:
        raise ValueError('Expected matching one-dimensional coordinates')
    if not (np.isfinite(lon).all() and np.isfinite(lat).all()
            and ((lat >= -90) & (lat < 90)).all()):
        raise ValueError('Invalid qualified coordinates')
    dx, dy = map(float, offset)
    if not (0 <= dx < 1 and 0 <= dy < 1):
        raise ValueError('Offsets must lie in [0,1) degrees')
    if dx == 0 and dy == 0:
        return cells(lon, lat, res=1)
    ix = np.floor((lon + 180 - dx) % 360).astype(np.int32)
    iy = np.floor(lat + 90 - dy).astype(np.int32)
    return iy * 360 + ix


def translation_table():
    offsets = np.random.Generator(np.random.PCG64(20261107)).random((100, 2))
    table = pd.DataFrame(offsets, columns=['delta_lon', 'delta_lat'])
    table.insert(0, 'grid', np.arange(1, 101, dtype=np.int16))
    for column in ['delta_lon', 'delta_lat']:
        table[column + '_hex'] = table[column].map(float.hex)
    return table


def fitting_counts(train, offset):
    origin = translated_cells(train.lon.to_numpy(), train.lat.to_numpy(), offset)
    destination = np.full(len(train), EXIT, dtype=np.int32)
    inside = ~train.outside.to_numpy(dtype=bool)
    destination[inside] = translated_cells(
        train.loc[inside, 'endpoint_lon'].to_numpy(),
        train.loc[inside, 'endpoint_lat'].to_numpy(), offset)
    pairs = pd.DataFrame({'origin': origin, 'destination': destination,
                          'id': train.id.to_numpy()})
    counts = pairs.groupby(['origin', 'destination'], sort=True).size().rename('count').reset_index()
    by_id = pairs.groupby(['origin', 'id'], sort=True).size().rename('count').reset_index()
    support = by_id.groupby('origin', sort=True).agg(
        pairs=('count', 'sum'), ids=('id', 'size'), largest_id_pairs=('count', 'max'))
    support['largest_id_share'] = support.largest_id_pairs / support.pairs
    support['destinations'] = counts.groupby('origin').size()
    support = support.reset_index()
    totals = support.set_index('origin').pairs
    counts['probability'] = counts['count'] / counts.origin.map(totals)
    if int(counts['count'].sum()) != len(train):
        raise ValueError('Pair counts not conserved')
    sums = counts.groupby('origin').probability.sum().to_numpy()
    if not np.allclose(sums, 1., rtol=0, atol=1e-12):
        raise ValueError('Probability mass not conserved')
    return counts, support


def query_support(query, support, offset):
    origin = translated_cells(query.lon.to_numpy(), query.lat.to_numpy(), offset)
    rows = pd.DataFrame({'origin': origin}).merge(support, on='origin', how='left', sort=False)
    if len(rows) != len(query):
        raise ValueError('Support join changed case count')
    rows['pairs'] = rows.pairs.fillna(0).astype(np.int64)
    rows['ids'] = rows.ids.fillna(0).astype(np.int64)
    rows['supported'] = rows.pairs.gt(0)
    rows['unresolved_mass'] = (~rows.supported).astype(float)
    return rows


def evaluation_weights(query):
    if query.duplicated(KEY).any():
        raise ValueError('Duplicate evaluation keys')
    weights = 1. / (query.id.nunique() * query.groupby('id').id.transform('size'))
    if not np.isclose(weights.sum(), 1., atol=1e-12, rtol=0):
        raise ValueError('Invalid ID-equal weights')
    return weights.to_numpy()


def require_complete_support(support_pairs):
    pairs = np.asarray(support_pairs)
    if pairs.ndim != 2 or pairs.shape[0] != 101:
        raise ValueError('Need original and exactly 100 shifted support rows')
    if (pairs <= 0).any():
        raise ValueError('Unsupported origin: contract prohibits fallback, deletion and reweighting')

