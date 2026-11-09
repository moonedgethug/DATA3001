"""Exact-coordinate empirical seven-day transitions with uniform neighbour votes.

This module is independent of temporal roles and observed validation outcomes.
Neighbour selection uses only fitting/query origins. An empirical distribution
retains observed destination atoms; gridding is a separate counting operation.
"""
from numbers import Integral

import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

from data3001.modelling.common.prediction_regions import probability_region
from data3001.preprocessing.prep_core import GEOD


EXIT = -2
MAX_DISTANCE_BATCH = 1_000_000
_TO_ECEF = Transformer.from_crs("EPSG:4979", "EPSG:4978", always_xy=True)


def _positive_integer(value):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
        raise ValueError("Neighbour count must be a positive integer")
    return int(value)


def _coordinate(lon, lat):
    lon, lat = float(lon), float(lat)
    if not np.isfinite([lon, lat]).all() or not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError("Finite WGS84 longitude/latitude required")
    return lon, lat


class NeighbourIndex:
    """Return exact geodesic neighbours using an admissible chord-distance index.

    ``query`` and ``exhaustive`` return (source indices, distances in metres),
    sorted by distance and original source index. Both include the kth-distance
    tie and respect the radius cap. ``select`` extracts a smaller k from such a
    result, retaining ties. Duplicate coordinates remain separate observations.
    """

    def __init__(self, lon, lat, radius_m=100000., tolerance_m=1e-6):
        lon, lat = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
        if (lon.ndim != 1 or lon.shape != lat.shape or not np.isfinite(lon).all()
                or not np.isfinite(lat).all() or (np.abs(lon) > 180).any()
                or (np.abs(lat) > 90).any()):
            raise ValueError("Fitting coordinates must be paired finite WGS84 vectors")
        if not np.isfinite(radius_m) or radius_m <= 0:
            raise ValueError("A positive finite donor radius is required")
        if not np.isfinite(tolerance_m) or tolerance_m < 0:
            raise ValueError("Distance tolerance must be finite and nonnegative")
        self.lon, self.lat = lon.copy(), lat.copy()
        self.lon.flags.writeable = self.lat.flags.writeable = False
        self.radius_m, self.tolerance_m = float(radius_m), float(tolerance_m)
        xyz = np.column_stack(_TO_ECEF.transform(lon, lat, np.zeros(len(lon))))
        self.tree = cKDTree(xyz, copy_data=True)
        self.last_stats = {}
        self.support_stats = {}

    def support(self, lon, lat):
        """Check complete query support without computing large neighbourhoods.

        A chord-nearest record within the geodesic cap proves support. Only
        failures of that sufficient test need exact one-neighbour refinement.
        All queries are checked, including cases that are not pilot benchmarks.
        """
        lon, lat = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
        if (lon.ndim != 1 or lon.shape != lat.shape or not np.isfinite(lon).all()
                or not np.isfinite(lat).all() or (np.abs(lon) > 180).any()
                or (np.abs(lat) > 90).any()):
            raise ValueError("Query coordinates must be paired finite WGS84 vectors")
        supported = np.zeros(len(lon), dtype=bool)
        refinements = 0
        if len(self.lon):
            for first in range(0, len(lon), min(MAX_DISTANCE_BATCH, 65536)):
                last = min(first + min(MAX_DISTANCE_BATCH, 65536), len(lon))
                x, y = lon[first:last], lat[first:last]
                xyz = np.column_stack(_TO_ECEF.transform(x, y, np.zeros(len(x))))
                _, nearest = self.tree.query(xyz, k=1, workers=1)
                _, _, distance = GEOD.inv(x, y, self.lon[nearest], self.lat[nearest])
                supported[first:last] = np.asarray(distance) <= self.radius_m + self.tolerance_m
                for local in np.flatnonzero(~supported[first:last]):
                    indices, _ = self.query(x[local], y[local], 1)
                    supported[first + local] = bool(len(indices))
                    refinements += 1
        self.support_stats = dict(queries=len(lon), supported=int(supported.sum()),
                                  nearest_evaluations=len(lon) if len(self.lon) else 0,
                                  refined_queries=refinements)
        return supported

    def _distances(self, lon, lat, indices):
        """Bound each geodesic vector call; no full pairwise matrix is built."""
        result = np.empty(len(indices), dtype=float)
        for first in range(0, len(indices), MAX_DISTANCE_BATCH):
            last = min(first + MAX_DISTANCE_BATCH, len(indices))
            ix = indices[first:last]
            _, _, distance = GEOD.inv(np.full(len(ix), lon), np.full(len(ix), lat),
                                      self.lon[ix], self.lat[ix])
            distance = np.asarray(distance, dtype=float)
            same = (self.lon[ix] == lon) & (self.lat[ix] == lat)
            result[first:last] = np.where(same, 0., distance)
        if not np.isfinite(result).all() or (result < 0).any():
            raise ValueError("Geodesic solver returned invalid distances")
        return result

    def _finish(self, indices, distances, max_k):
        keep = distances <= self.radius_m + self.tolerance_m
        indices, distances = indices[keep], distances[keep]
        order = np.lexsort((indices, distances))
        indices, distances = indices[order], distances[order]
        if len(indices) > max_k:
            stop = np.searchsorted(distances, distances[max_k - 1] + self.tolerance_m,
                                   side="right")
            indices, distances = indices[:stop], distances[:stop]
        return indices, distances

    def query(self, lon, lat, max_k):
        """Geodesically exact, radius-limited neighbours without an all-fit scan."""
        lon, lat = _coordinate(lon, lat)
        max_k = _positive_integer(max_k)
        size = len(self.lon)
        if not size:
            self.last_stats = dict(seed_evaluations=0, refinement_evaluations=0,
                                   candidate_count=0, selected_count=0, cap_limited=True)
            return np.empty(0, dtype=np.int64), np.empty(0, dtype=float)
        if size <= max_k:
            indices = np.arange(size, dtype=np.int64)
            distances = self._distances(lon, lat, indices)
            result = self._finish(indices, distances, max_k)
            self.last_stats = dict(seed_evaluations=size, refinement_evaluations=0,
                                   candidate_count=size, selected_count=len(result[0]),
                                   cap_limited=len(result[0]) < max_k)
            return result

        point = np.asarray(_TO_ECEF.transform(lon, lat, 0.), dtype=float)
        _, seed = self.tree.query(point, k=max_k, workers=1)
        seed = np.atleast_1d(seed).astype(np.int64, copy=False)
        seed_distance = self._distances(lon, lat, seed)
        # Any k fitting records provide an upper bound on the kth geodesic
        # distance. Every surface distance is >= its straight ECEF chord.
        upper = min(float(seed_distance.max()), self.radius_m)
        numerical_pad = max(self.tolerance_m, 64 * np.finfo(float).eps * 6378137.)
        radius = upper + self.tolerance_m + numerical_pad
        candidates = np.asarray(self.tree.query_ball_point(point, radius, workers=1,
                                                          return_sorted=True), dtype=np.int64)
        # Reuse the seed solver values. Only genuinely new candidates need a
        # second WGS84 evaluation; labels never enter the spatial calculation.
        seed_order = np.argsort(seed)
        sorted_seed, sorted_distance = seed[seed_order], seed_distance[seed_order]
        at = np.searchsorted(sorted_seed, candidates)
        known = at < len(sorted_seed)
        known[known] &= sorted_seed[at[known]] == candidates[known]
        distances = np.empty(len(candidates), dtype=float)
        distances[known] = sorted_distance[at[known]]
        distances[~known] = self._distances(lon, lat, candidates[~known])
        result = self._finish(candidates, distances, max_k)
        self.last_stats = dict(seed_evaluations=len(seed),
                               refinement_evaluations=int((~known).sum()),
                               candidate_count=len(candidates), selected_count=len(result[0]),
                               cap_limited=len(result[0]) < max_k)
        return result

    def select(self, indices, distances, k):
        """Select a smaller neighbour count, including all numerical cutoff ties."""
        k = _positive_integer(k)
        indices = np.asarray(indices, dtype=np.int64)
        distances = np.asarray(distances, dtype=float)
        if (indices.ndim != 1 or indices.shape != distances.shape
                or not np.isfinite(distances).all() or (distances < 0).any()
                or (np.diff(distances) < 0).any()):
            raise ValueError("Expected paired, nonnegative, sorted neighbour arrays")
        if len(indices) <= k:
            return indices.copy()
        stop = np.searchsorted(distances, distances[k - 1] + self.tolerance_m, side="right")
        return indices[:stop].copy()

    def exhaustive(self, lon, lat, max_k):
        """Independent full-fitting distance scan for small verification workloads."""
        lon, lat = _coordinate(lon, lat)
        max_k = _positive_integer(max_k)
        indices = np.arange(len(self.lon), dtype=np.int64)
        return self._finish(indices, self._distances(lon, lat, indices), max_k)


def sparse_forecast(destination_codes, selected_indices):
    """Count selected original endpoints; always include E, even at zero mass."""
    codes = np.asarray(destination_codes)
    selected = np.asarray(selected_indices)
    if (codes.ndim != 1 or not np.issubdtype(codes.dtype, np.integer)
            or ((codes < 0) & (codes != EXIT)).any()):
        raise ValueError("Expected integer geographic destination codes or E")
    if (selected.ndim != 1 or not np.issubdtype(selected.dtype, np.integer)
            or not len(selected) or (selected < 0).any() or (selected >= len(codes)).any()
            or len(np.unique(selected)) != len(selected)):
        raise ValueError("A supported forecast needs unique selected source indices")
    states, inverse = np.unique(np.r_[codes[selected], EXIT], return_inverse=True)
    counts = np.bincount(inverse[:-1], minlength=len(states))
    probabilities = counts / len(selected)
    return states.astype(np.int64, copy=False), probabilities


def probability_summary(states, probabilities, truth, area_by_state):
    """Score a sparse D-plus-E forecast, including truth outside stored support.

    ``area_by_state`` is a mapping or Series giving frozen geographic wet areas
    in km2. E contributes no geographic area. ``mask`` follows the input states.
    Missing or invalid geographic areas are integrity errors.
    """
    states = np.asarray(states, dtype=np.int64)
    p = np.asarray(probabilities, dtype=float)
    mask, region = probability_region(p, states)
    hit = states == truth
    observed_probability = float(p[hit].sum())
    geographic = states >= 0
    area = np.asarray([area_by_state[int(s)] for s in states[geographic]], dtype=float)
    if not np.isfinite(area).all() or (area < 0).any():
        raise ValueError("Frozen geographic wet areas must be finite and nonnegative")
    return dict(brier=float(1. + p @ p - 2. * observed_probability),
                h90=float(mask[hit].any()), k90=region["region90_cells"],
                area90=float(area[mask[geographic]].sum()), mass=region["region90_mass"],
                zero=float(observed_probability == 0.), exit=float(p[states == EXIT][0]),
                geographic_mass=float(p[mask & geographic].sum()),
                exit_in_region=region["region90_exit_included"], mask=mask)
