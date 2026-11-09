"""Approved E9 numerical reuse and one independent control variate.

Forecast probabilities and region construction are inherited unchanged.
"""
from dataclasses import dataclass
import time
import numpy as np
import shapely as sh
from data3001.modelling.baselines import position_error_s4_e8 as geometry


def xyz(points):
    p = np.asarray(points, float)
    out = np.column_stack(geometry.ECEF.transform(p[:, 0], p[:, 1], np.zeros(len(p)))) / 1000
    if not np.isfinite(out).all(): raise ValueError('Invalid ECEF transform')
    return out


def xy(points):
    p = np.asarray(points, float)
    out = np.column_stack(geometry.LAEA.transform(p[:, 0], p[:, 1])) / 1000
    if not np.isfinite(out).all(): raise ValueError('Invalid LAEA transform')
    return out


def add_time(profile, name, start):
    profile[name] = profile.get(name, 0.) + time.monotonic() - start


@dataclass
class Pool:
    points: np.ndarray
    sd: np.ndarray
    usable: np.ndarray
    xyz: np.ndarray
    xy: np.ndarray
    land: np.ndarray
    outside: np.ndarray

    def take(self, indices):
        out = Pool(*[value[indices] for value in self.__dict__.values()])
        for value in out.__dict__.values(): value.setflags(write=False)
        return out

    @property
    def bytes(self):
        return sum(value.nbytes for value in self.__dict__.values())


def cache(fit, geo):
    p = fit[['endpoint_lon', 'endpoint_lat']].to_numpy()
    x0, y0, x1, y1 = geo.clip_bounds
    local = (p[:, 0]>x0)&(p[:, 0]<x1)&(p[:, 1]>y0)&(p[:, 1]<y1)
    land = np.empty(len(p), bool)
    land[local] = sh.intersects_xy(geo.land_clip, p[local, 0], p[local, 1])
    land[~local] = sh.intersects_xy(geo.land, p[~local, 0], p[~local, 1])
    outside = ~sh.intersects_xy(geo.domain, p[:, 0], p[:, 1])
    out = Pool(p, fit[['sd_e_km', 'sd_n_km']].to_numpy(), fit.ci_2d_usable.to_numpy(bool),
               xyz(p), xy(p), land, outside)
    for value in out.__dict__.values(): value.setflags(write=False)
    return out


def regions(pool, key, count, geo=None, profile=None):
    """Build the frozen regions without doing any ES integration."""
    profile = {} if profile is None else profile
    packets, clouds = {}, {}
    n = len(pool.points)
    if not n: raise ValueError('Empty donor pool')
    for ci in [False, True]:
        started = time.monotonic()
        if ci and pool.usable.any():
            cloud, weight, labels = geometry.component_cloud(pool.points, pool.sd, pool.usable, count, key)
            np.testing.assert_allclose(np.bincount(labels, weights=weight, minlength=n), 1/n, atol=1e-12, rtol=0)
            cloud_xy = xy(cloud)
        else:
            cloud, weight, cloud_xy = pool.points, np.full(n, 1/n), pool.xy
        add_time(profile, 'region_cloud_seconds', started)
        started = time.monotonic()
        packet = dict(region=geometry.fit_region(cloud_xy, weight), region_count=count, particles=len(cloud))
        add_time(profile, 'region_fit_seconds', started)
        if geo is not None:
            started = time.monotonic()
            if ci and pool.usable.any(): packet.update(geo.masses(cloud, weight))
            else: packet.update(land_mass=float(weight @ pool.land), outside_D_mass=float(weight @ pool.outside))
            packet.update(geo.areas(packet['region']))
            add_time(profile, 'geography_seconds', started)
        packets[ci], clouds[ci] = packet, (cloud, weight)
    if not pool.usable.any(): packets[True] = packets[False]
    return packets, clouds


def calibration(pool, base_key):
    """Point-only calibration; no truth argument or scoring-stream access."""
    g = geometry.rng_for(*base_key, 'e9_es_control_calibration_v1')
    a, b = g.integers(len(pool.points), size=1024), g.integers(len(pool.points), size=1024)
    distance = np.linalg.norm(pool.xyz[a]-pool.xyz[b], axis=1)
    squared = distance**2
    centred = squared-squared.mean()
    denominator = float(centred @ centred)
    coefficient = float((distance-distance.mean()) @ centred / denominator) if denominator else 0.
    centre = pool.xyz.mean(axis=0)
    mean_squared = float(2*np.mean(np.sum((pool.xyz-centre)**2, axis=1)))
    if not np.isfinite([coefficient, mean_squared]).all(): raise ValueError('Invalid control calibration')
    return dict(coefficient=coefficient, mean_squared=mean_squared, degenerate=denominator==0., draws=1024)


def score(pool, packets, truth, key, count, control, *, profile=None):
    """One draw generation, with raw parity output and controlled ES output."""
    profile = {} if profile is None else profile
    started = time.monotonic()
    g = geometry.rng_for(*key, 'energy')
    a = g.integers(len(pool.points), size=count)
    b = g.integers(len(pool.points), size=count)
    z1, z2 = g.standard_normal((count, 2)), g.standard_normal((count, 2))
    add_time(profile, 'energy_draw_seconds', started)
    started = time.monotonic()
    first = xyz(geometry.perturbed(pool.points[a], pool.sd[a], z1))
    second = xyz(geometry.perturbed(pool.points[b], pool.sd[b], z2))
    add_time(profile, 'ci_geodesic_seconds', started)
    started = time.monotonic()
    target, target_xy = xyz(np.asarray(truth)[None, :])[0], xy(np.asarray(truth)[None, :])
    original = pool.xyz[a]
    distance = np.linalg.norm(original-pool.xyz[b], axis=1)
    delta_distance = np.linalg.norm(first-second, axis=1)-distance
    increment = np.linalg.norm(first-target, axis=1)-np.linalg.norm(original-target, axis=1)-.5*delta_distance
    base_first = float(np.linalg.norm(pool.xyz-target, axis=1).mean())
    raw_base = -.5*distance
    correction = .5*control['coefficient']*(distance**2-control['mean_squared'])
    rows = {}
    for ci, packet in packets.items():
        raw = raw_base + (increment if ci else 0.)
        controlled = raw+correction
        region = packet['region']
        raw_variance = float(raw.var(ddof=1))
        variance = float(controlled.var(ddof=1))
        rows[ci] = dict(energy_km=base_first+float(controlled.mean()), energy_mc_se=float(np.sqrt(variance/count)),
            raw_energy_km=base_first+float(raw.mean()), raw_energy_mc_se=float(np.sqrt(raw_variance/count)),
            residual_variance_ratio=variance/raw_variance if raw_variance else 0.,
            sample_sum=float(controlled.sum()), sample_sumsq=float(controlled@controlled),
            sample_count=count, base_first_km=base_first,
            ci_delta=float(increment.mean()) if ci else 0.,
            ci_delta_mc_se=float(increment.std(ddof=1)/np.sqrt(count)) if ci else 0.,
            h90=float(geometry.inside_region(target_xy, region)[0]), area90_km2=region['area_km2'],
            mass90=region['attained_mass'], rank=region['rank'])
        for name in ['land_mass','outside_D_mass','land_area_km2','wet_area_km2','outside_D_area_km2']:
            if name in packet: rows[ci][name]=packet[name]
    if not pool.usable.any(): rows[True]=rows[False].copy()
    add_time(profile, 'energy_algebra_seconds', started)
    return rows
