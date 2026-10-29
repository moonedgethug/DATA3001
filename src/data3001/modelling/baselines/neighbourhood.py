"""Local endpoint sharing and empirical-prior WGS84 displacement transfer.

All functions are pure: no trajectory reads, fitted global caches, or writes.
Balanced couplings preserve both empirical marginals exactly. Their average
approximates the independent Cartesian product; a stability diagnostic is not
a certified error bound on that limiting integral.
"""
from data3001.modelling.common.geometry import EndpointMapper
from dataclasses import dataclass
from numbers import Integral

import numpy as np
from pyproj import Geod
import shapely as sh

from data3001.modelling.common.probability import score_distribution
from data3001.preprocessing.prep_core import cells

GEOD = Geod(ellps="WGS84")
OUTSIDE = -2
UNRESOLVED = -1


def neighbour_cells(cell):
    if isinstance(cell, bool) or not isinstance(cell, Integral) or not 0 <= cell < 64800:
        raise ValueError("A valid global one-degree cell is required.")
    y, x = divmod(int(cell), 360)
    return tuple(sorted((y + dy) * 360 + (x + dx) % 360
                        for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                        if (dy or dx) and 0 <= y + dy < 180))




def _distribution(mass):
    # Only repair floating point overshoot at the closed upper endpoint.
    # This never removes land/outside mass or rescales the surviving states.
    def bounded(value):
        value = float(value)
        return 1. if 1. < value <= 1.+1e-10 else value
    p = {int(k): bounded(v) for k, v in mass.items() if k != UNRESOLVED and v > 0}
    u = bounded(mass.get(UNRESOLVED, 0.))
    score_distribution(p, -999, u)
    return p, u


def unaligned_distribution(donors):
    if not len(donors):
        return {}, 1.
    codes = donors["destination_cell_1"].to_numpy(dtype=np.int64)
    if (codes < OUTSIDE).any() or (codes == UNRESOLVED).any():
        raise ValueError("Unaligned donors must be eligible observed endpoints.")
    states, counts = np.unique(codes, return_counts=True)
    return _distribution(dict(zip(states, counts / len(codes))))


def net_displacements(donors):
    if {"displacement_azimuth", "net_distance_m"} <= set(donors.columns):
        az = donors["displacement_azimuth"].to_numpy(dtype=float)
        distance = donors["net_distance_m"].to_numpy(dtype=float)
    else:
        x = donors[["origin_lon", "origin_lat", "endpoint_lon", "endpoint_lat"]].to_numpy(float)
        if not np.isfinite(x).all():
            raise ValueError("Eligible donor coordinates must be finite.")
        az, _, distance = GEOD.inv(x[:, 0], x[:, 1], x[:, 2], x[:, 3])
        az, distance = np.asarray(az), np.asarray(distance)
    if not np.isfinite(az).all() or not np.isfinite(distance).all() or (distance < 0).any():
        raise ValueError("Invalid WGS84 displacement.")
    return az, distance


def balanced_coupling(n, m, rng):
    """Sparse random joint measure with EXACT uniform donor/anchor marginals.

    Intersect partitions of [0,n*m] with widths m and n, then independently
    permute the row/column labels. At most n+m-1 positive contributions remain.
    Expectation over permutations equals the independent product measure.
    """
    if (isinstance(n, bool) or isinstance(m, bool) or not isinstance(n, Integral)
            or not isinstance(m, Integral) or n <= 0 or m <= 0):
        raise ValueError("Positive integer marginal sizes required.")
    starts, weights = _coupling_partition(n, m)
    di = rng.permutation(n)[starts // m]
    ai = rng.permutation(m)[starts // n]
    return di, ai, weights


def _coupling_partition(n, m):
    edges = np.union1d(np.arange(n + 1, dtype=np.int64) * m,
                       np.arange(m + 1, dtype=np.int64) * n)
    return edges[:-1], np.diff(edges).astype(float) / (int(n) * int(m))


def blend_score_envelope(base, ub, p, up, q, uq):
    """Exact maximum score difference between TWO approximations, not truth.

    Maximise |S((1-a)b+a*p,y)-S((1-a)b+a*q,y)| over a in [0,1]
    and every physical outcome (including unseen ones). No labels are used.
    """
    score_distribution(base, -999, ub)
    score_distribution(p, -999, up)
    score_distribution(q, -999, uq)
    states = sorted(set(base) | set(p) | set(q))
    b = np.array([base.get(k, 0.) for k in states])
    r = np.array([p.get(k, 0.) for k in states])
    s = np.array([q.get(k, 0.) for k in states])
    delta = r - s
    common = float(2 * (b @ delta + ub * (up - uq)))
    linear = np.r_[common - 2 * delta, common]  # unseen truth has delta=0
    quadratic = float((r-b) @ (r-b) - (s-b) @ (s-b)
                      + (up-ub)**2 - (uq-ub)**2)
    maximum = float(np.max(np.abs(linear + quadratic)))
    if quadratic != 0.:
        vertex = -linear / (2 * quadratic)
        valid = (vertex > 0) & (vertex < 1)
        if valid.any():
            maximum = max(maximum, float(np.max(np.abs(
                linear[valid]*vertex[valid] + quadratic*vertex[valid]**2))))
    return maximum


def _add(mass, codes, weights):
    keys, inverse = np.unique(codes, return_inverse=True)
    totals = (np.bincount(inverse) * float(weights) if np.isscalar(weights)
              else np.bincount(inverse, weights=weights))
    for key, value in zip(keys, totals):
        mass[int(key)] = mass.get(int(key), 0.) + float(value)


def aligned_distribution(donors, anchors, mapper, *, exact_limit=2_000_000,
                         levels=(8, 32, 128, 512), seed=20261004,
                         tolerance=5e-4, base=None, chunk_size=200_000):
    """Integrate transferred displacements over actual fitting-origin anchors.

    Every donor and anchor record has its original equal marginal mass; repeated
    positions deliberately retain their multiplicity. Never turn contributions
    into source observations. Unsupported and synthetic-land mass remain explicit.
    """
    anchors = np.asarray(anchors, dtype=float)
    if anchors.ndim != 2 or anchors.shape[1] != 2 or not np.isfinite(anchors).all():
        raise ValueError("Finite [lon,lat] anchors required.")
    n, m = len(donors), len(anchors)
    audit = {"donor_pairs": n, "anchors": m, "seed": int(seed),
             "marginals": "All donor/anchor records retain exact equal marginal weight",
             "stability_is_certified_integral_error_bound": False}
    if not n or not m:
        return {}, 1., {**audit, "method": "unsupported", "converged": True,
                         "integration_points": 0, "couplings": 0,
                         "max_blend_score_change": 0., "total_variation_change": 0.}
    levels = tuple(levels)
    if (exact_limit < 0 or tolerance < 0 or chunk_size <= 0
            or len(levels) < 2 or any(not isinstance(r, Integral) or r <= 0 for r in levels)
            or tuple(sorted(set(levels))) != levels):
        raise ValueError("Invalid integration controls.")
    az, distance = net_displacements(donors)
    ox = donors["origin_lon"].to_numpy(float)
    oy = donors["origin_lat"].to_numpy(float)
    ex = donors["endpoint_lon"].to_numpy(float)
    ey = donors["endpoint_lat"].to_numpy(float)
    # Each numeric worker owns its geodesic handle. Geometries are read-only.
    local_geod = Geod(ellps="WGS84")

    def project(di, ai):
        lon, lat, _ = local_geod.fwd(anchors[ai, 0], anchors[ai, 1], az[di], distance[di])
        lon, lat = np.asarray(lon), np.asarray(lat)
        zero = distance[di] == 0
        lon[zero], lat[zero] = anchors[ai[zero], 0], anchors[ai[zero], 1]
        identity = (anchors[ai, 0] == ox[di]) & (anchors[ai, 1] == oy[di])
        lon[identity], lat[identity] = ex[di[identity]], ey[di[identity]]
        return mapper(lon, lat)

    mass, points = {}, 0
    if n*m <= exact_limit:
        for start in range(0, n*m, chunk_size):
            ix = np.arange(start, min(start+chunk_size, n*m), dtype=np.int64)
            _add(mass, project(ix//m, ix % m), 1/(n*m))
            points += len(ix)
        p, u = _distribution(mass)
        return p, u, {**audit, "method": "exact", "converged": True,
                       "integration_points": points, "couplings": 0,
                       "max_blend_score_change": 0., "total_variation_change": 0.}

    rng = np.random.default_rng(seed)
    previous, change, tv = None, np.inf, np.inf
    base, ub = base if base is not None else ({}, 1.)
    completed = 0
    starts, weights = _coupling_partition(n, m)
    for level in levels:
        for _ in range(completed, level):
            di = rng.permutation(n)[starts // m]
            ai = rng.permutation(m)[starts // n]
            for start in range(0, len(weights), chunk_size):
                stop = start + chunk_size
                _add(mass, project(di[start:stop], ai[start:stop]), weights[start:stop])
            points += len(weights)
        completed = level
        p, u = _distribution({k: v/level for k, v in mass.items()})
        if previous is not None:
            old, old_u = previous
            change = blend_score_envelope(base, ub, old, old_u, p, u)
            tv = .5*(sum(abs(old.get(k, 0.)-p.get(k, 0.)) for k in set(old)|set(p)) + abs(old_u-u))
            if change <= tolerance:
                break
        previous = p, u
    return p, u, {**audit, "method": "balanced", "converged": bool(change <= tolerance),
                   "integration_points": points, "couplings": int(completed),
                   "max_blend_score_change": float(change), "total_variation_change": float(tv)}
