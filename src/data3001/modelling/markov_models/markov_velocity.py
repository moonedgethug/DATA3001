"""Pure categorical-velocity joint Markov operators; no trajectory access."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

E, U, BINS = -2, -3, 9
PLAIN_KEYS = ['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1']
ATOM_KEYS = PLAIN_KEYS + ['origin_atom', 'destination_atom']
JOINT_KEYS = PLAIN_KEYS + ['origin_velocity_bin', 'destination_velocity_bin']


def _cuts(cuts):
    cuts = np.asarray(cuts, dtype=float)
    if (cuts.ndim != 1 or not len(cuts) or not np.isfinite(cuts).all()
            or (cuts < 0).any() or (np.diff(cuts) <= 0).any()):
        raise ValueError('Finite, unique, increasing nonnegative cutpoints required')
    return cuts


def velocity_atoms(ve, vn, cuts):
    """Cache-only exact intervals: (previous_cut, cut], plus separate zero."""
    cuts = _cuts(cuts)
    ve, vn = np.asarray(ve, dtype=float), np.asarray(vn, dtype=float)
    if ve.shape != vn.shape or not np.isfinite(ve).all() or not np.isfinite(vn).all():
        raise ValueError('Finite paired velocity components required; no imputation')
    speed = np.hypot(ve, vn)
    q = 2*(vn >= 0).astype(int)+(ve >= 0).astype(int)
    band = np.searchsorted(cuts, speed, side='left')
    return np.where(speed == 0, 0, 1+q*(len(cuts)+1)+band).astype('int16')


def coarse_velocity(atoms, cuts, threshold):
    cuts = _cuts(cuts)
    threshold = float(threshold)
    ix = np.flatnonzero(cuts == threshold)
    atoms = np.asarray(atoms)
    if (len(ix) != 1 or not np.isfinite(atoms).all()
            or not np.equal(atoms, np.floor(atoms)).all()
            or (atoms < 0).any() or (atoms > 4*(len(cuts)+1)).any()):
        raise ValueError('Invalid atoms or fit threshold absent from cache cuts')
    atom = np.maximum(atoms.astype('int64')-1, 0)
    q, band = np.divmod(atom, len(cuts)+1)
    return np.where(atoms == 0, 0, 1+2*q+(band > ix[0])).astype('int8')


def coarse_counts(counts, cuts, threshold):
    if not set(ATOM_KEYS+['pair_count']).issubset(counts.columns):
        raise ValueError('Missing atomic sufficient-count columns')
    numeric = counts[ATOM_KEYS+['pair_count']].to_numpy(dtype=float)
    if (not np.isfinite(numeric).all() or not np.equal(numeric, np.floor(numeric)).all()
            or (counts.pair_count <= 0).any() or (counts.id <= 0).any()
            or not counts.horizon_days.between(1, 365).all()):
        raise ValueError('Finite integer identities and positive counts required')
    out = counts[PLAIN_KEYS+['pair_count']].copy()
    out['origin_velocity_bin'] = coarse_velocity(counts.origin_atom, cuts, threshold)
    outside = counts.destination_cell_1.eq(E).to_numpy()
    if not np.array_equal(outside, counts.destination_atom.eq(E).to_numpy()):
        raise ValueError('Exit must have its own endpoint atom, not fabricated velocity')
    destination = np.full(len(counts), E, dtype='int8')
    destination[~outside] = coarse_velocity(counts.destination_atom.to_numpy()[~outside], cuts, threshold)
    out['destination_velocity_bin'] = destination
    return out.groupby(JOINT_KEYS, as_index=False, sort=True).pair_count.sum()


@dataclass
class JointOperator:
    cells: tuple
    cuts: tuple
    threshold: float
    lag_days: int
    training_ids: frozenset
    local: csr_matrix
    pooled: csr_matrix
    row_pairs: np.ndarray
    row_ids: np.ndarray
    dominant_id_share: np.ndarray
    _cache: dict = field(default_factory=dict, repr=False)

    def matrix(self, lam):
        lam = float(lam)
        if not np.isfinite(lam) or not 0 <= lam <= 1:
            raise ValueError('Lambda must be in [0,1]')
        if lam not in self._cache:
            n = len(self.cells)*BINS
            weights = lam+(1-lam)*(self.row_pairs[:n] == 0)
            projection = csr_matrix((weights, (np.arange(n), np.arange(n)//BINS)),
                                    shape=(n+2, len(self.cells)))
            absorbers = csr_matrix(([1., 1.], ([n, n+1], [n, n+1])), shape=(n+2, n+2))
            matrix = (1-lam)*self.local + projection@self.pooled + absorbers
            matrix.sum_duplicates(); matrix.eliminate_zeros()
            if not np.isfinite(matrix.data).all() or (matrix.data < 0).any():
                raise ValueError('Invalid joint probability')
            np.testing.assert_allclose(np.asarray(matrix.sum(axis=1)).ravel(), 1., rtol=0, atol=1e-12)
            self._cache[lam] = matrix.tocsr()
        return self._cache[lam]

    def clear_cache(self):
        self._cache.clear()


def fit_joint_operator(counts, fitting_ids, state_cells, cuts, threshold, lag_days):
    ids = frozenset(int(i) for i in fitting_ids)
    cells = tuple(sorted(int(c) for c in state_cells))
    if (not ids or any(i <= 0 for i in ids) or not cells or len(set(cells)) != len(cells)
            or any(c < 0 or c >= 64800 for c in cells)
            or isinstance(lag_days, bool) or int(lag_days) != lag_days or not 1 <= lag_days <= 365):
        raise ValueError('Invalid fitting population, cells or integer lag')
    part = counts.loc[counts.id.isin(ids) & counts.horizon_days.eq(lag_days)]
    part = coarse_counts(part, cuts, threshold)
    if (not part.origin_cell_1.isin(cells).all()
            or not part.destination_cell_1.isin(cells+(E,)).all()):
        raise ValueError('Unknown or ineligible geographic state')
    index = {c: i for i, c in enumerate(cells)}; n = len(cells)*BINS
    source_cell = part.origin_cell_1.map(index).to_numpy(dtype=int)
    row = source_cell*BINS+part.origin_velocity_bin.to_numpy(dtype=int)
    outside = part.destination_cell_1.eq(E).to_numpy()
    dest_cell = part.destination_cell_1.map(index).fillna(0).to_numpy(dtype=int)
    col = np.where(outside, n, dest_cell*BINS+part.destination_velocity_bin.to_numpy(dtype=int))
    w = part.pair_count.to_numpy(dtype=float)
    totals = np.bincount(row, weights=w, minlength=n+2)
    local = csr_matrix((w/totals[row], (row, col)), shape=(n+2, n+2))
    cell_totals = np.bincount(source_cell, weights=w, minlength=len(cells))
    unsupported = np.flatnonzero(cell_totals == 0)
    pooled = csr_matrix((np.r_[w/cell_totals[source_cell], np.ones(len(unsupported))],
                         (np.r_[source_cell, unsupported], np.r_[col, np.repeat(n+1, len(unsupported))])),
                        shape=(len(cells), n+2))
    support = part.assign(row=row).groupby(['row', 'id']).pair_count.sum().reset_index()
    row_ids = np.bincount(support.row.to_numpy(dtype=int), minlength=n+2)
    maximum = support.groupby('row').pair_count.max()
    dominance = np.zeros(n+2)
    ix = maximum.index.to_numpy(dtype=int)
    dominance[ix] = maximum.to_numpy(dtype=float)/totals[ix]
    return JointOperator(cells, tuple(_cuts(cuts)), float(threshold), int(lag_days), ids,
                         local, pooled, totals, row_ids, dominance)


def joint_forecasts(operator, origins, horizon_days, lam, remainder=None):
    if (isinstance(horizon_days, bool) or int(horizon_days) != horizon_days
            or not 1 <= horizon_days <= 365):
        raise ValueError('Integer horizon 1..365 required')
    q, r = divmod(int(horizon_days), operator.lag_days)
    if r and (remainder is None or remainder.lag_days != r
              or remainder.cells != operator.cells or remainder.training_ids != operator.training_ids
              or remainder.cuts != operator.cuts or remainder.threshold != operator.threshold):
        raise ValueError('Identically fitted and encoded exact remainder required')
    index = {c: i for i, c in enumerate(operator.cells)}
    origins = list(origins)
    if any(c not in index or isinstance(b, bool) or int(b) != b or not 0 <= b < BINS for c, b in origins):
        raise ValueError('Invalid origin cell or velocity class')
    columns = np.array([index[c]*BINS+int(b) for c, b in origins], dtype=int)
    p = csr_matrix((np.ones(len(origins)), (np.arange(len(origins)), columns)),
                   shape=(len(origins), len(operator.cells)*BINS+2))
    for _ in range(q):
        p = p@operator.matrix(lam)
    if r: p = p@remainder.matrix(lam)
    if not np.isfinite(p.data).all() or (p.data < 0).any():
        raise ValueError('Invalid propagated probability')
    np.testing.assert_allclose(np.asarray(p.sum(axis=1)).ravel(), 1, rtol=0, atol=1e-10)
    p.data = np.minimum(p.data, 1.)  # upper floating boundary only; no tail pruning
    return p


def marginal_locations(joint, cells):
    n = len(cells)*BINS
    projection = csr_matrix((np.ones(n+2),
                             (np.arange(n+2), np.r_[np.arange(n)//BINS, len(cells), len(cells)+1])),
                            shape=(n+2, len(cells)+2))
    locations = (joint@projection).tocsr()
    states = tuple(cells)+(E, U)
    result = []
    for r in range(locations.shape[0]):
        row = locations.getrow(r)
        values = {states[c]: float(v) for c, v in zip(row.indices, row.data) if v > 0}
        u = values.pop(U, 0.)
        # Summation over nine labels can move an absorber to 1+epsilon.
        values = {c: min(v, 1.) for c, v in values.items()}
        result.append((values, min(u, 1.)))
    return result


def location_forecasts(operator, origins, horizon_days, lam, remainder=None):
    return marginal_locations(joint_forecasts(operator, origins, horizon_days, lam, remainder), operator.cells)
