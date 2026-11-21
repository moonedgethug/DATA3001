"""Opt-in, same-node MDN numerics with bounded query-local caches.

The original numerical implementation remains the reference. This module keeps
its stream identities, sampling order, geometric transformations, and reduction
order. Only packet validation, uniform/normal generation, and the equal-weight
region order statistic are reused or accelerated. No endpoints are cached.

Reuse a ``QueryCache`` across candidate mixtures for one query and one purpose,
then exit its context before moving to another query or purpose. Main energy,
main region, audit energy, and audit region use separate scopes. Without an
explicit cache, each scoring call owns and closes its own scope.
"""
from collections import OrderedDict
from dataclasses import dataclass
import math

import numpy as np
from scipy.stats import qmc

from . import conditional_mdn_s5_e4_numerics as legacy
from .conditional_gaussian_s5_e1 import mass_diagnostic
from .conditional_mdn_s5_e4 import stable_seed
from data3001.modelling.baselines import position_error_s4_e8 as region_math


MAX_CACHE_BYTES = 128 * 1024**2
LEVELS = legacy.LEVELS


def _immutable_array(value):
    """Copy into immutable backing bytes, including protection from setflags."""
    array = np.asarray(value, dtype=np.float64)
    return np.frombuffer(array.tobytes(), dtype=np.float64).reshape(array.shape)


@dataclass(frozen=True, eq=False)
class PreparedPacket:
    """A validated, immutable snapshot of one mixture and its component CDF."""
    origin: np.ndarray
    weights: np.ndarray
    means: np.ndarray
    cholesky: np.ndarray
    cdf: np.ndarray


def prepare_packet(packet):
    if isinstance(packet, PreparedPacket):
        return packet
    copied = {name: _immutable_array(packet[name])
              for name in ('origin', 'weights', 'means', 'cholesky')}
    weights, means, cholesky = legacy.arrays(copied)
    origin = copied['origin']
    if origin.shape != (2,) or not np.isfinite(origin).all():
        raise ValueError('Invalid mixture origin')
    cdf = np.cumsum(weights)
    cdf[-1] = 1.
    return PreparedPacket(origin, weights, means, cholesky, _immutable_array(cdf))


class QueryCache:
    """A bounded LRU of immutable nodes for exactly one query/purpose scope.

    ``purpose`` is one of ``ES``, ``region``, ``audit_ES``, or ``audit_region``.
    The two audit scopes retain the legacy ``audit`` seed label. Cache keys also
    include the full stream identity and, for normals, their source columns.
    Instances belong to one worker; no process-wide or module cache is changed.
    """
    def __init__(self, key, purpose, max_bytes=MAX_CACHE_BYTES):
        if purpose not in ('ES', 'region', 'audit_ES', 'audit_region'):
            raise ValueError('Unknown numerical cache purpose')
        if not isinstance(max_bytes, int) or not 0 < max_bytes <= MAX_CACHE_BYTES:
            raise ValueError('Query cache limit must be in (0, 128 MiB]')
        hash(key)
        self.key = key
        self.purpose = purpose
        self.max_bytes = max_bytes
        self._entries = OrderedDict()
        self._bytes = 0
        self._peak_bytes = 0
        self._closed = False

    @property
    def cache_bytes(self):
        return self._bytes

    @property
    def peak_cache_bytes(self):
        return self._peak_bytes

    def __enter__(self):
        self._require_open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def clear(self):
        self._entries.clear()
        self._bytes = 0

    def close(self):
        self.clear()
        self._closed = True

    def _require_open(self):
        if self._closed:
            raise RuntimeError('Numerical cache scope is closed')

    def require_scope(self, key, purpose):
        self._require_open()
        if key != self.key or purpose != self.purpose:
            raise ValueError('Numerical cache belongs to a different query or purpose')

    def _stream_key(self, count, dimensions, purpose, replicate, key, role):
        self._require_open()
        stream_purpose = 'audit' if self.purpose.startswith('audit_') else self.purpose
        if key != self.key or purpose != stream_purpose:
            raise ValueError('Nodes belong to a different query or purpose')
        return (count, dimensions, purpose, role, key, replicate)

    def _get(self, key):
        value = self._entries.get(key)
        if value is not None:
            self._entries.move_to_end(key)
        return value

    def _put(self, key, value):
        value = _immutable_array(value)
        if value.nbytes > self.max_bytes:
            return value
        while self._bytes + value.nbytes > self.max_bytes:
            _, removed = self._entries.popitem(last=False)
            self._bytes -= removed.nbytes
        self._entries[key] = value
        self._bytes += value.nbytes
        self._peak_bytes = max(self._peak_bytes, self._bytes)
        return value

    def uniforms(self, count, dimensions, purpose, replicate, key, role=''):
        stream = self._stream_key(count, dimensions, purpose, replicate, key, role)
        cache_key = ('uniform',) + stream
        cached = self._get(cache_key)
        if cached is not None:
            return cached
        power = int(math.log2(count))
        if 2**power != count:
            raise ValueError('Sobol count must be a power of two')
        seed = stable_seed(purpose, role, None, 20261121, key, replicate)
        values = qmc.Sobol(dimensions, scramble=True, rng=np.random.default_rng(seed)).random_base2(power)
        return self._put(cache_key, values)

    def normals(self, count, dimensions, purpose, replicate, key, role='', *, offset):
        stream = self._stream_key(count, dimensions, purpose, replicate, key, role)
        if not isinstance(offset, int) or offset < 0 or offset+2 > dimensions:
            raise ValueError('Invalid normal source columns')
        cache_key = ('normal',) + stream + (offset,)
        cached = self._get(cache_key)
        if cached is not None:
            return cached
        uniform = self.uniforms(count, dimensions, purpose, replicate, key, role)
        return self._put(cache_key, legacy.normals(uniform[:, offset:offset+2]))


def _draw_vectors(packet, uniform, normal):
    selected = np.searchsorted(packet.cdf, uniform[:, 0], side='right')
    return packet.means[selected] + np.einsum('nij,nj->ni', packet.cholesky[selected], normal)


def draw_vectors(packet, uniform):
    prepared = prepare_packet(packet)
    values = np.asarray(uniform, float)
    if values.ndim != 2 or values.shape[1] != 3 or (values < 0).any() or (values >= 1).any():
        raise ValueError('Invalid uniform nodes')
    return _draw_vectors(prepared, values, legacy.normals(values[:, 1:]))


def draw(packet, uniform):
    prepared = prepare_packet(packet)
    return legacy.to_geographic(prepared.origin, draw_vectors(prepared, uniform))


def draw_iid(packet, count, key, role, rep=0):
    prepared = prepare_packet(packet)
    seed = stable_seed('IID', role, None, 20261121, key, rep)
    rng = np.random.default_rng(seed)
    choice = rng.choice(len(prepared.weights), size=count, p=prepared.weights)
    normal = rng.standard_normal((count, 2))
    vectors = prepared.means[choice] + np.einsum('nij,nj->ni', prepared.cholesky[choice], normal)
    return legacy.to_geographic(prepared.origin, vectors)


def score_es(packet, target, count, key, role, audit=False, *, cache=None):
    if count not in LEVELS:
        raise ValueError('Unregistered MDN energy level')
    scope = 'audit_ES' if audit else 'ES'
    if cache is None:
        with QueryCache(key, scope) as owned:
            return score_es(packet, target, count, key, role, audit, cache=owned)
    cache.require_scope(key, scope)
    prepared = prepare_packet(packet)
    truth = legacy.xyz(np.asarray(target)[None])[0]
    means = []
    purpose = 'audit' if audit else 'ES'
    for rep in range(8):
        stream = (count//8, 6, purpose, rep, key, role)
        uniform = cache.uniforms(*stream)
        first_normal = cache.normals(*stream, offset=1)
        second_normal = cache.normals(*stream, offset=4)
        # Keep the reference geodesic calls, ordering, and reductions intact.
        first = legacy.xyz(legacy.to_geographic(
            prepared.origin, _draw_vectors(prepared, uniform[:, :3], first_normal)))
        second = legacy.xyz(legacy.to_geographic(
            prepared.origin, _draw_vectors(prepared, uniform[:, 3:], second_normal)))
        means.append(float(legacy.integrands(first, second, truth).mean()))
    return legacy.summary(means, count)


def fit_region_uniform(xy):
    """Reference region math with an exact equal-weight 90% order statistic."""
    p = np.asarray(xy, float)
    w = np.full(len(p), 1/len(p))
    if len(p) == 0 or abs(w.sum()-1) > 1e-10 or (w <= 0).any():
        raise ValueError('Region requires a normalized positive measure')
    centre = w @ p
    delta = p-centre
    covariance = delta.T @ (delta*w[:, None])
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    largest = max(float(eigenvalues.max()), 0.)
    keep = eigenvalues > 64*np.finfo(float).eps*largest if largest else np.zeros(2, bool)
    rank = int(keep.sum())
    inverse = (eigenvectors[:, keep] / eigenvalues[keep]) @ eigenvectors[:, keep].T if rank else np.zeros((2, 2))
    distance = np.einsum('ij,jk,ik->i', delta, inverse, delta)
    # The reference uniform weights become integer units of one. Its rational
    # 9/10 threshold is ceil(9*n/10), so ties retain the identical cutoff value.
    kth = (9*len(p)+9)//10-1
    cutoff = float(np.partition(distance, kth)[kth])
    included = distance <= cutoff+1e-12
    area = np.pi*cutoff*np.sqrt(np.prod(eigenvalues)) if rank == 2 else 0.
    return dict(centre=centre.tolist(), covariance=covariance.tolist(), inverse=inverse.tolist(),
                eigenvalues=eigenvalues.tolist(), eigenvectors=eigenvectors.tolist(), rank=rank,
                cutoff=cutoff, area_km2=float(area), attained_mass=float(w[included].sum()),
                null_tolerance_km=float(64*np.finfo(float).eps*max(1., np.linalg.norm(centre), np.sqrt(largest))))


def build_region(packet, count, key, role, geography=None, audit=False, *, cache=None):
    if count not in LEVELS:
        raise ValueError('Unregistered region level')
    scope = 'audit_region' if audit else 'region'
    if cache is None:
        with QueryCache(key, scope) as owned:
            return build_region(packet, count, key, role, geography, audit, cache=owned)
    cache.require_scope(key, scope)
    prepared = prepare_packet(packet)
    regions, means = [], []
    purpose = 'audit' if audit else 'region'
    for rep in range(2):
        stream = (count, 3, purpose, 100+rep if audit else rep, key, role)
        uniform = cache.uniforms(*stream)
        normal = cache.normals(*stream, offset=1)
        points = legacy.to_geographic(prepared.origin, _draw_vectors(prepared, uniform, normal))
        regions.append(fit_region_uniform(legacy.xy(points)))
        means.append(legacy.xyz(points).mean(axis=0).tolist())
    points = draw_iid(prepared, 65536, key, role, rep=1 if audit else 0)
    hits = region_math.inside_region(legacy.xy(points), regions[0])
    result = dict(region=regions[0], replica_region=regions[1], means=means, region_count=count,
                  mass_check=mass_diagnostic(int(hits.sum()), len(hits), 0.))
    if geography is not None:
        result.update(geography.masses(points, np.full(len(points), 1/len(points))))
        result['land_variance'] = result['land_mass']*(1-result['land_mass'])/len(points)
        result['outside_variance'] = result['outside_D_mass']*(1-result['outside_D_mass'])/len(points)
    return result


region_metrics = legacy.region_metrics
