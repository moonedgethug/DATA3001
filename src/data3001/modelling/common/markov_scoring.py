"""Separate categorical and conditional spatial scores; canonical data unchanged.

The spatial reference is ES/100 km + squared mean error/(100 km)^2.
It is an auxiliary equal-weight reference, never a replacement selection metric.
OUTSIDE and algorithmic unresolved mass have no invented spatial coordinates.
"""
import numpy as np
from pyproj import Transformer
from scipy.spatial.distance import cdist

from data3001.modelling.common.probability import score_distribution


def cell_coordinates_km(cells):
    cells = np.asarray(cells, dtype=int)
    lon = -180 + cells % 360 + .5
    lat = -90 + cells // 360 + .5
    transform = Transformer.from_crs('EPSG:4979', 'EPSG:4978', always_xy=True)
    return np.column_stack(transform.transform(lon, lat, np.zeros(len(cells)))) / 1000


class SpatialScorer:
    def __init__(self, cells, coordinates_km=None, scale_km=100.0):
        self.cells = tuple(int(c) for c in cells)
        self.index = {c: i for i, c in enumerate(self.cells)}
        self.scale = float(scale_km)
        self.xyz = cell_coordinates_km(self.cells) if coordinates_km is None else np.asarray(coordinates_km, dtype=float)
        if (len(self.index) != len(self.cells) or not self.cells
                or any(c < 0 or c >= 64800 for c in self.cells)
                or self.xyz.shape != (len(self.cells), 3) or not np.isfinite(self.xyz).all()
                or not np.isfinite(self.scale) or self.scale <= 0):
            raise ValueError('Invalid spatial index, coordinates, or reference scale')
        self.distance = cdist(self.xyz, self.xyz)

    def score(self, probabilities, truth, *, unresolved=0.0):
        return self.prepare(probabilities, unresolved=unresolved)(truth)

    def prepare(self, probabilities, *, unresolved=0.0):
        score_distribution(probabilities, -1, unresolved=unresolved)
        if any(c not in self.index and c != -2 for c in probabilities):
            raise ValueError('Unknown spatial state')
        inside = float(sum(p for c, p in probabilities.items() if c >= 0))
        status = 'unresolved_forecast' if unresolved > 0 else 'zero_in_domain_mass' if inside == 0 else None
        q = np.zeros(len(self.cells))
        if status is None:
            for c, p in probabilities.items():
                if c >= 0:
                    q[self.index[c]] = p / inside
            distances = q @ self.distance
            correction = .5 * float(distances @ q)
            mean = q @ self.xyz

        def evaluate(truth):
            if truth != -2 and truth not in self.index:
                raise ValueError('Unknown observed state')
            why = status or ('outside_truth' if truth == -2 else 'complete_in_domain')
            result = {'spatial_status': why, 'in_domain_mass': inside,
                      'energy_km': np.nan, 'mean_squared_km2': np.nan,
                      'linear_quadratic_reference': np.nan}
            if why != 'complete_in_domain':
                return result
            j = self.index[truth]
            energy = float(distances[j] - correction)
            if energy < -1e-8:
                raise ValueError('Negative energy score beyond roundoff')
            squared = float(np.sum((mean - self.xyz[j])**2))
            result.update(energy_km=max(0.0, energy), mean_squared_km2=squared,
                          linear_quadratic_reference=max(0.0, energy)/self.scale + squared/self.scale**2)
            return result
        return evaluate
