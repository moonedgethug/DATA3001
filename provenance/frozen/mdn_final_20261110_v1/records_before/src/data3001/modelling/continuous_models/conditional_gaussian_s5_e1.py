"""Approved query-centred, same-endpoint Gaussian law; no fitted-data I/O."""
import hashlib
import json

import numpy as np
from scipy.stats import qmc

from data3001.modelling.baselines.position_error_s4_e8 import GEOD
from data3001.modelling.baselines.seasonal_exact_position_s4_e9_esopt import xyz


class SupportError(ValueError):
    """A registered support/covariance gate failed; never repair implicitly."""

    def __init__(self, message, diagnostics=None):
        super().__init__(message)
        self.diagnostics = {} if diagnostics is None else diagnostics


def generator(key):
    payload = json.dumps(('s5_e1_v1', *key), separators=(',', ':')).encode()
    seed = int.from_bytes(hashlib.sha256(payload).digest()[:16], 'little')
    return np.random.Generator(np.random.PCG64(seed))


def _points(points):
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError('Expected finite two-coordinate points')
    return points


def to_vectors(origin, points):
    points = _points(points)
    origin = np.asarray(origin, dtype=float)
    if origin.shape != (2,) or not np.isfinite(origin).all():
        raise ValueError('Invalid exact origin')
    azimuth, _, distance = GEOD.inv(np.full(len(points), origin[0]),
                                   np.full(len(points), origin[1]), points[:, 0], points[:, 1])
    angle = np.deg2rad(azimuth)
    vectors = np.column_stack([np.sin(angle), np.cos(angle)]) * np.asarray(distance)[:, None]/1000
    if not np.isfinite(vectors).all(): raise ValueError('Nonfinite inverse geodesic')
    return vectors


def to_geographic(origin, vectors):
    vectors = _points(vectors)
    radius = np.linalg.norm(vectors, axis=1)
    azimuth = np.rad2deg(np.arctan2(vectors[:, 0], vectors[:, 1]))
    lon, lat, _ = GEOD.fwd(np.full(len(vectors), origin[0]), np.full(len(vectors), origin[1]),
                           azimuth, radius*1000)
    points = np.column_stack([lon, lat])
    points[radius == 0] = origin
    if not np.isfinite(points).all(): raise ValueError('Nonfinite direct geodesic')
    return points


def fit_vectors(vectors):
    vectors = _points(vectors)
    n = len(vectors)
    if n < 3: raise SupportError(f'Gaussian needs at least three pairs; got {n}', dict(pairs=n))
    mean = vectors.mean(axis=0)
    residual = vectors-mean
    covariance = residual.T @ residual/n
    covariance = (covariance+covariance.T)/2
    eigenvalues = np.linalg.eigvalsh(covariance)
    diagnostics = dict(pairs=n, mean=mean.tolist(), covariance=covariance.tolist(),
                       eigenvalues=eigenvalues.tolist())
    if not np.isfinite(eigenvalues).all() or eigenvalues[0] <= 0:
        raise SupportError('Nonpositive Gaussian covariance eigenvalue', diagnostics)
    condition = float(eigenvalues[-1]/eigenvalues[0])
    diagnostics['condition_number'] = condition
    if condition > 1e12: raise SupportError(f'Gaussian condition number {condition} exceeds 1e12', diagnostics)
    return dict(mean=mean.tolist(), covariance=covariance.tolist(),
                cholesky=np.linalg.cholesky(covariance).tolist(),
                eigenvalues=eigenvalues.tolist(), condition_number=condition, pairs=n)


def fit(origin, endpoints):
    vectors = to_vectors(origin, endpoints)
    packet = fit_vectors(vectors)
    reconstructed = to_geographic(origin, vectors)
    _, _, error = GEOD.inv(endpoints[:, 0], endpoints[:, 1], reconstructed[:, 0], reconstructed[:, 1])
    maximum = float(np.max(np.abs(error))/1000)
    if maximum > 1e-6: raise ValueError('Endpoint chart round trip exceeds 1e-6 km')
    packet.update(origin=np.asarray(origin).tolist(), roundtrip_max_km=maximum)
    return packet


def sobol_normals(count, dimensions, key):
    if count < 1 or count & (count-1) or dimensions not in (2, 4):
        raise ValueError('Sobol requires a power-of-two count and 2/4 dimensions')
    u = qmc.Sobol(d=dimensions, scramble=True, rng=generator(key), optimization=None).random_base2(count.bit_length()-1)
    normals = np.empty_like(u)
    for col in range(0, dimensions, 2):
        radius = np.sqrt(-2*np.log1p(-u[:, col]))
        angle = 2*np.pi*u[:, col+1]
        normals[:, col] = radius*np.cos(angle)
        normals[:, col+1] = radius*np.sin(angle)
    if not np.isfinite(normals).all(): raise ValueError('Nonfinite Box-Muller draw')
    return normals


def draw(packet, normals):
    vectors = np.asarray(packet['mean']) + normals @ np.asarray(packet['cholesky']).T
    return to_geographic(packet['origin'], vectors)


def energy_integrands(first, second, truth):
    return np.linalg.norm(first-truth, axis=1)-.5*np.linalg.norm(first-second, axis=1)


def replicate_summary(means):
    means = np.asarray(means, float)
    if means.shape != (8,) or not np.isfinite(means).all():
        raise ValueError('Exactly eight finite independent replicate means required')
    variance = float(means.var(ddof=1)/8)
    return dict(energy_km=float(means.mean()), variance=variance,
                energy_mc_se=float(np.sqrt(variance)), replicate_means=means.tolist())


def energy(packet, truth, total_count, key):
    if total_count not in (8192, 16384, 32768, 65536):
        raise ValueError('Unregistered ES integration level')
    target = xyz(np.asarray(truth)[None, :])[0]
    means = []
    for replicate in range(8):
        normal = sobol_normals(total_count//8, 4, (*key, 'gaussian_energy', replicate))
        first, second = xyz(draw(packet, normal[:, :2])), xyz(draw(packet, normal[:, 2:]))
        means.append(float(energy_integrands(first, second, target).mean()))
    return dict(replicate_summary(means), sample_count=total_count)


def mass_diagnostic(hits, total, boundary_atom=0.):
    if not (0 <= hits <= total and total > 0 and 0 <= boundary_atom <= 1):
        raise ValueError('Invalid binomial count or atom mass')
    p = hits/total
    z = 1.9599639845
    denominator = 1+z*z/total
    centre = (p+z*z/(2*total))/denominator
    half = z*np.sqrt(p*(1-p)/total+z*z/(4*total*total))/denominator
    lower, upper = centre-half, centre+half
    radius = max(p-lower, upper-p)
    discrepancy = max(.9-p, p-(.9+boundary_atom), 0.)
    return dict(probability=p, lower=float(lower), upper=float(upper), radius=float(radius),
                boundary_atom=float(boundary_atom), discrepancy=float(discrepancy),
                diagnostic=float(discrepancy+radius))
