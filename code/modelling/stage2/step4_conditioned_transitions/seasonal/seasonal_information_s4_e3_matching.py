"""Endpoint-blind, year- and trajectory-matched seasonal control draws."""
from dataclasses import dataclass
from math import fsum

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

SAMPLE_COLUMNS = ['id', 'origin_source_obs', 'origin_time_UTC', 'departure_season']


@dataclass
class YearTrack:
    hours: np.ndarray
    indices: np.ndarray
    bits: int


def hour_values(times):
    seconds = (times - pd.Timestamp('1970-01-01', tz='UTC')).dt.total_seconds().to_numpy()
    assert np.all(seconds % 3600 == 0)
    return (seconds / 3600).astype('int64')


def feasible_starts(offsets, track):
    """Bits avoid scanning every candidate placement separately for every offset."""
    bits = track.bits
    for offset in offsets[1:]:
        bits &= track.bits >> int(offset)
        if not bits:
            break
    anchors = []
    while bits:
        low = bits & -bits
        anchors.append(track.hours[0] + low.bit_length() - 1)
        bits ^= low
    return np.asarray(anchors, dtype='int64')


def lexical_assignment(cost):
    """Exact integer-valued uniform costs; lowest donor tuple on an optimum tie."""
    rows, chosen = linear_sum_assignment(cost)
    optimum = fsum(cost[rows, chosen])
    available = np.ones(cost.shape[1], dtype=bool)
    fixed = 0.
    for row in rows:
        current = chosen[row]
        while True:
            smaller = available & (np.arange(cost.shape[1]) < current) & np.isfinite(cost[row])
            if not smaller.any():
                break
            donors = np.flatnonzero(available)
            sub = cost[row:, donors].copy()
            sub[0, ~smaller[donors]] = np.inf
            try:
                ii, jj = linear_sum_assignment(sub)
            except ValueError:  # No complete alternative with a smaller donor.
                break
            if fixed + fsum(sub[ii, jj]) != optimum:
                break
            chosen[row:] = donors[jj]
            current = chosen[row]
        available[current] = False
        fixed += cost[row, current]
    return chosen


def draw_table(features, season, row_key, replicates, master_seed):
    """Return compact replayable placements and exact source indices, never outcomes."""
    features = features[SAMPLE_COLUMNS].copy()
    features['year'] = features.origin_time_UTC.dt.year
    features['hour'] = hour_values(features.origin_time_UTC)
    assert not features.duplicated(['id', 'hour']).any()
    donors = sorted(features.id.unique())
    tracks = {}
    for (donor, year), group in features.groupby(['id', 'year']):
        g = group.sort_values('hour')
        hours = g.hour.to_numpy()
        bitmask = sum(1 << int(v) for v in hours - hours[0])
        tracks[donor, year] = YearTrack(hours, g.index.to_numpy(), bitmask)
    target = features[features.departure_season == season]
    templates = {}
    for (source, year), group in target.groupby(['id', 'year']):
        hours = np.sort(group.hour.to_numpy())
        templates.setdefault(source, {})[year] = hours - hours[0]
    sources = sorted(templates)
    edges = np.zeros((len(sources), len(donors)), dtype=bool)
    placements = {}
    for i, source in enumerate(sources):
        for j, donor in enumerate(donors):
            starts = {}
            for year, offsets in templates[source].items():
                track = tracks.get((donor, year))
                if track is None or len(track.hours) < len(offsets):
                    break
                anchors = feasible_starts(offsets, track)
                if not len(anchors):
                    break
                starts[year] = anchors
            else:
                edges[i, j] = True
                placements[i, j] = starts
        assert edges[i, donors.index(source)]
    selected = np.empty((replicates, len(target)), dtype='int32')
    manifests = []
    cached_indices = {}
    horizon, origin, _ = row_key
    for rep in range(replicates):
        rng = np.random.Generator(np.random.PCG64([master_seed, rep, origin, horizon, season]))
        cost = np.full(edges.shape, np.inf)
        cost[edges] = rng.integers(0, 2**40, size=int(edges.sum()))
        assignment = lexical_assignment(cost)
        cursor = 0
        for i, j in enumerate(assignment):
            source, donor = sources[i], donors[j]
            for year, anchors in placements[i, j].items():
                anchor = int(anchors[rng.integers(len(anchors))])
                cache_key = (i, j, year, anchor)
                if cache_key not in cached_indices:
                    hours = anchor + templates[source][year]
                    track = tracks[donor, year]
                    pos = np.searchsorted(track.hours, hours)
                    assert np.array_equal(track.hours[pos], hours)
                    cached_indices[cache_key] = track.indices[pos]
                indices = cached_indices[cache_key]
                selected[rep, cursor:cursor + len(indices)] = indices
                cursor += len(indices)
                manifests.append((rep, source, donor, year, anchor, len(indices)))
        assert cursor == len(target)
    manifest = pd.DataFrame(manifests, columns=['replicate','template_id','donor_id','year','anchor_hour','pairs'])
    return selected, manifest, int(edges.sum())


def audit_draws(features, season, selected, manifest):
    """Rebuild every selected source key from manifests by independent track lookup."""
    f = features[SAMPLE_COLUMNS].copy()
    f['hour'] = hour_values(f.origin_time_UTC)
    f['year'] = f.origin_time_UTC.dt.year
    lookup = dict(zip(zip(f.id, f.hour), f.index))
    target = f[f.departure_season == season]
    offsets = {}
    for key,g in target.groupby(['id','year']):
        times = np.sort(g.hour.to_numpy())
        offsets[key] = times - times.min()
    calendar_year = f.year.to_dict()
    unique = manifest.drop_duplicates(['template_id','donor_id','year','anchor_hour'])
    cache = {}
    for r in unique.itertuples(index=False):
        hours = r.anchor_hour + offsets[r.template_id, r.year]
        indices = np.array([lookup[r.donor_id,t] for t in hours], dtype='int32')
        assert len(indices) == r.pairs
        # Each placement must really stay within its template calendar year.
        assert calendar_year[indices[0]] == r.year == calendar_year[indices[-1]]
        cache[r.template_id, r.donor_id, r.year, r.anchor_hour] = indices
    original = np.sort(target.index.to_numpy())
    raw_seasons = features.departure_season.to_dict()
    dense_seasons = np.zeros(int(features.index.max())+1, dtype='int8')
    dense_seasons[list(raw_seasons)] = list(raw_seasons.values())
    other = (dense_seasons[selected] != season).mean(axis=1)
    identical = []
    for rep,g in manifest.groupby('replicate',sort=True):
        ids = g[['template_id','donor_id']].drop_duplicates()
        assert len(ids) == target.id.nunique() == ids.donor_id.nunique()
        assert set(zip(g.template_id,g.year)) == set(offsets) and len(g) == len(offsets)
        rebuilt = np.concatenate([cache[key] for key in g[['template_id','donor_id','year','anchor_hour']].itertuples(index=False,name=None)])
        assert np.array_equal(rebuilt, selected[rep]) and len(np.unique(rebuilt)) == len(target)
        identical.append(np.array_equal(np.sort(rebuilt), original))
    return other, np.asarray(identical)
