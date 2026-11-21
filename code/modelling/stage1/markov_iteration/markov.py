"""Empirical stopped-domain Markov operators; no data access or fitting choices."""
from dataclasses import dataclass
from numbers import Integral

import numpy as np
from scipy.sparse import csr_matrix

OUTSIDE = -2
UNRESOLVED = -3


@dataclass(frozen=True)
class Operator:
    cells: tuple
    matrix: csr_matrix
    lag_days: int
    training_ids: frozenset
    row_pair_counts: np.ndarray


def _integer(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, Integral) or not low <= value <= high:
        raise ValueError('Invalid ' + name)
    return int(value)


def fit_operator(counts, fitting_ids, state_cells, lag_days):
    lag = _integer(lag_days, 1, 365, 'lag')
    ids = frozenset(_integer(i, 1, 2**63-1, 'fitting ID') for i in fitting_ids)
    cells = tuple(sorted(_integer(i, 0, 64800-1, 'state cell') for i in state_cells))
    if not ids or not cells or len(cells) != len(set(cells)):
        raise ValueError('Unique cells and nonempty fitting IDs required')
    keys = ['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1', 'pair_count']
    if not set(keys).issubset(counts.columns):
        raise ValueError('Missing count fields')
    values = counts[keys].to_numpy(dtype=float)
    if (not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all()
            or (values[:, 4] <= 0).any()):
        raise ValueError('Counts must contain finite integer fields and positive frequencies')
    if (not counts.origin_cell_1.isin(cells).all()
            or not counts.destination_cell_1.isin(cells + (OUTSIDE,)).all()):
        raise ValueError('A count contains an unknown or ineligible state')
    part = counts.loc[counts.id.isin(ids) & counts.horizon_days.eq(lag)]
    index = {c: i for i, c in enumerate(cells + (OUTSIDE, UNRESOLVED))}
    rows = np.array([index[int(i)] for i in part.origin_cell_1], dtype=int)
    cols = np.array([index[int(i)] for i in part.destination_cell_1], dtype=int)
    weights = part.pair_count.to_numpy(dtype=float)
    n = len(cells) + 2
    totals = np.bincount(rows, weights=weights, minlength=n)
    data = weights / totals[rows]
    unsupported = np.flatnonzero(totals[:len(cells)] == 0)
    rows = np.r_[rows, unsupported, len(cells), len(cells)+1]
    cols = np.r_[cols, np.repeat(len(cells)+1, len(unsupported)), len(cells), len(cells)+1]
    data = np.r_[data, np.ones(len(unsupported)+2)]
    matrix = csr_matrix((data, (rows, cols)), shape=(n, n))
    matrix.sum_duplicates()
    np.testing.assert_allclose(np.asarray(matrix.sum(axis=1)).ravel(), 1, rtol=0, atol=1e-12)
    if not np.isfinite(matrix.data).all() or (matrix.data < 0).any():
        raise ValueError('Invalid transition probability')
    return Operator(cells, matrix, lag, ids, totals)


def propagate(operator, origin_cell, horizon_days, remainder=None):
    h = _integer(horizon_days, 1, 365, 'horizon')
    index = {c: i for i, c in enumerate(operator.cells + (OUTSIDE, UNRESOLVED))}
    if isinstance(origin_cell, bool) or origin_cell not in index:
        raise ValueError('Release state is not in the frozen state index')
    q, r = divmod(h, operator.lag_days)
    if r and (remainder is None or remainder.lag_days != r
              or remainder.cells != operator.cells
              or remainder.training_ids != operator.training_ids):
        raise ValueError('An aligned, identically fitted exact remainder operator is required')
    p = np.zeros(len(index))
    p[index[origin_cell]] = 1
    for _ in range(q):
        p = operator.matrix.T @ p
    if r:
        p = remainder.matrix.T @ p
    if not np.isfinite(p).all() or (p < 0).any() or not np.isclose(p.sum(), 1, rtol=0, atol=1e-10):
        raise ValueError('Propagation violates probability conservation')
    # Summing sparse branches can produce 1 + machine epsilon in an absorber.
    # Correct only the upper roundoff boundary after conservation validation;
    # do not renormalise physical mass or erase small unresolved probabilities.
    return np.minimum(p, 1.)


def forecast(operator, origin_cell, horizon_days, remainder=None):
    p = propagate(operator, origin_cell, horizon_days, remainder)
    states = operator.cells + (OUTSIDE,)
    return {c: float(p[i]) for i, c in enumerate(states) if p[i] > 0}, float(p[-1])
