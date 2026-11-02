"""Probability regions and exact-budget tie expectations; no model fitting."""
from numbers import Integral

import numpy as np

TOLERANCE = 1e-12


def checked_distribution(probabilities, states, exit_state=-2):
    p = np.asarray(probabilities, dtype=float)
    states = np.asarray(states, dtype=np.int64)
    if (p.ndim != 1 or p.shape != states.shape or len(np.unique(states)) != len(states)
            or not np.isfinite(p).all() or (p < 0).any() or (p > 1).any()
            or not np.isclose(p.sum(), 1., atol=TOLERANCE, rtol=0)
            or np.sum(states == exit_state) != 1 or ((states < 0) & (states != exit_state)).any()):
        raise ValueError("Expected a complete, nonnegative D-plus-E distribution")
    return p, states


def probability_region(probabilities, states, level=.9, exit_state=-2):
    p, states = checked_distribution(probabilities, states, exit_state)
    if not 0 < level <= 1:
        raise ValueError("Region level must be in (0,1]")
    positive = np.sort(p[p > 0])[::-1]
    index = min(int(np.searchsorted(np.cumsum(positive), level - TOLERANCE)), len(positive)-1)
    cutoff = float(positive[index])
    mask = (p > 0) & (p >= cutoff - TOLERANCE)
    return mask, {"region90_cells": int(np.sum(mask & (states >= 0))),
                  "region90_mass": float(p[mask].sum()),
                  "region90_exit_included": bool(mask[states == exit_state][0]),
                  "region90_cutoff": cutoff}


def budget_inclusion(probabilities, states, k, exit_state=-2):
    """Exact K D-cell budget, averaging uniformly over a boundary tie."""
    p, states = checked_distribution(probabilities, states, exit_state)
    d = states >= 0
    if isinstance(k, bool) or not isinstance(k, Integral) or not 1 <= k <= int(d.sum()):
        raise ValueError("K must be a positive integer no larger than the D index")
    boundary = float(np.sort(p[d])[::-1][k-1])
    above = d & (p > boundary + TOLERANCE)
    tied = d & (np.abs(p - boundary) <= TOLERANCE)
    slots, size = int(k - above.sum()), int(tied.sum())
    if not 0 < slots <= size:
        raise AssertionError("Boundary tie does not contain the Kth cell")
    inclusion = above.astype(float) + tied * (slots / size)
    if not np.isclose(inclusion.sum(), k, rtol=0, atol=1e-10):
        raise AssertionError("Expected selected-cell count differs from K")
    return inclusion, {"k": int(k), "boundary_probability": boundary,
                       "tie_size": size, "remaining_slots": slots,
                       "zero_probability_tie": bool(np.any(tied & (p == 0)))}


def budgets(number_of_d_cells):
    return tuple(sorted({k for k in (1, 5, 10, 20, 50, 100, 200, 500, 1000,
                                    number_of_d_cells) if k <= number_of_d_cells}))
