"""Approved E9 season selection and unchanged E8 point/CI measures.

Only the historical donor pool depends on majority season. No fusion,
movement translation or learned error scale is used.
"""
import numpy as np
import pandas as pd

from data3001.modelling.baselines.exact_origin_s4_e7 import NeighbourIndex
from data3001.modelling.baselines import position_error_s4_e8 as e8

MODELS = ('AnnualExactPoint', 'AnnualEndpointCI',
          'SeasonalExactPoint', 'SeasonalEndpointCI')
SEASONS = ('DJF', 'MAM', 'JJA', 'SON')


def season_labels(times):
    """Elapsed UTC time on [departure, departure + seven days)."""
    t = pd.Series(times).reset_index(drop=True)
    if str(t.dt.tz) != 'UTC' or t.isna().any():
        raise ValueError('Valid UTC departure times are required')
    month = t.dt.month.to_numpy()
    departure = (month % 12) // 3
    next_month = np.select([month < 3, month < 6, month < 9, month < 12],
                           [3, 6, 9, 12], default=3)
    year = t.dt.year.to_numpy() + (month == 12)
    boundary = pd.to_datetime(dict(year=year, month=next_month,
                                  day=np.ones(len(t), dtype=int)), utc=True)
    before = np.minimum((boundary - t).dt.total_seconds().to_numpy(), 604800.)
    if np.any(before <= 0):
        raise ValueError('Invalid next-season boundary')
    after = 604800. - before
    majority = np.where(before >= after, departure, (departure + 1) % 4)
    seconds = np.zeros((len(t), 4))
    seconds[np.arange(len(t)), departure] = before
    seconds[np.arange(len(t)), (departure + 1) % 4] += after
    out = pd.DataFrame(dict(departure_season=departure.astype('int8'),
        majority_season=majority.astype('int8'), cross_season=after > 0,
        season_tie=before == after))
    for j, name in enumerate(SEASONS):
        out[name + '_seconds'] = seconds[:, j]
    return out


class SeasonalNeighbours:
    def __init__(self, fit, *, k=8000, radius_m=100000., tolerance_m=1e-6):
        self.fit = fit
        self.k = k
        self.labels = season_labels(fit.origin_time_UTC)
        self.maps = {'annual': np.arange(len(fit))}
        self.maps.update({int(s): np.flatnonzero(self.labels.majority_season.to_numpy() == s)
                          for s in range(4)})
        self.indices = {s: NeighbourIndex(fit.lon.to_numpy()[ix], fit.lat.to_numpy()[ix],
                                         radius_m, tolerance_m)
                        for s, ix in self.maps.items()}

    def query(self, lon, lat, season, *, exhaustive=False):
        found = {}
        for name in ['annual', int(season)]:
            index = self.indices[name]
            method = index.exhaustive if exhaustive else index.query
            local, distances = method(lon, lat, self.k)
            found[name] = (self.maps[name][local], distances)
        annual, seasonal = found['annual'], found[int(season)]
        if not len(annual[0]):
            raise ValueError('Annual support empty; no substitute or deletion is allowed')
        fallback = not len(seasonal[0])
        return annual, annual if fallback else seasonal, fallback


def arrays(fit):
    return (fit[['endpoint_lon', 'endpoint_lat']].to_numpy(),
            fit[['sd_e_km', 'sd_n_km']].to_numpy(), fit.ci_2d_usable.to_numpy(bool))


def draws(points, sd, count, key):
    """Same E8 independent donor-pair and normal draw ordering; two arms only."""
    g = e8.rng_for(*key, 'energy')
    a = g.integers(len(points), size=count)
    b = g.integers(len(points), size=count)
    z1, z2 = g.standard_normal((count, 2)), g.standard_normal((count, 2))
    xyz, _ = e8.coordinates(points)
    first, _ = e8.coordinates(e8.perturbed(points[a], sd[a], z1))
    second, _ = e8.coordinates(e8.perturbed(points[b], sd[b], z2))
    base_distance = np.linalg.norm(xyz[a] - xyz[b], axis=1)
    changed_distance = np.linalg.norm(first - second, axis=1) - base_distance
    return xyz, xyz[a], first, base_distance, changed_distance


def predict_pool(points, sd, usable, *, key, energy_count=4096, region_count=16384,
                 geography=None):
    if not len(points):
        raise ValueError('A defined donor distribution is required')
    xyz, original, first, distance, delta = draws(points, sd, energy_count, key)
    base = .5 * float(distance.mean())
    packets, clouds = {}, {}
    for ci in [False, True]:
        if ci and usable.any():
            cloud, weight, labels = e8.component_cloud(points, sd, usable, region_count, key)
            if not np.allclose(np.bincount(labels, weights=weight, minlength=len(points)),
                               1 / len(points), rtol=0, atol=1e-12):
                raise ValueError('CI quadrature changed donor votes')
        else:
            cloud, weight = points, np.full(len(points), 1 / len(points))
        _, xy = e8.coordinates(cloud)
        packet = dict(region=e8.fit_region(xy, weight),
            correction=base + (.5 * float(delta.mean()) if ci else 0.),
            correction_se=float(np.std(.5 * (distance + delta if ci else distance),
                                        ddof=1) / np.sqrt(energy_count)),
            energy_count=energy_count, region_count=region_count, particles=len(cloud))
        if geography is not None:
            packet.update(geography.masses(cloud, weight))
            packet.update(geography.areas(packet['region']))
        packets[ci], clouds[ci] = packet, (cloud, weight)
    if not usable.any():
        packets[True] = packets[False]
    return packets, clouds


def score_pool(points, sd, usable, packets, truth, key):
    xyz, original, first, distance, delta_distance = draws(points, sd,
                                                        packets[False]['energy_count'], key)
    target, target_xy = e8.coordinates(np.asarray(truth)[None, :])
    base_first = float(np.linalg.norm(xyz - target[0], axis=1).mean())
    correction_noise = -.5 * distance
    ci_delta = (np.linalg.norm(first - target[0], axis=1)
                - np.linalg.norm(original - target[0], axis=1) - .5 * delta_distance)
    out = {}
    for ci, packet in packets.items():
        samples = correction_noise + (ci_delta if ci else 0.)
        region = packet['region']
        row = dict(energy_km=base_first + float(samples.mean()),
            energy_mc_se=float(samples.std(ddof=1) / np.sqrt(len(samples))),
            ci_delta=float(ci_delta.mean()) if ci else 0.,
            ci_delta_mc_se=float(ci_delta.std(ddof=1) / np.sqrt(len(samples))) if ci else 0.,
            h90=float(e8.inside_region(target_xy, region)[0]),
            area90_km2=region['area_km2'], mass90=region['attained_mass'], rank=region['rank'])
        for name in ['land_mass', 'outside_D_mass', 'land_area_km2', 'wet_area_km2', 'outside_D_area_km2']:
            if name in packet:
                row[name] = packet[name]
        out[ci] = row
    if not usable.any():
        out[True] = out[False].copy()
    return out


def case_weights(frame):
    return 1. / (frame.id.nunique() * frame.groupby('id').id.transform('size').to_numpy())
