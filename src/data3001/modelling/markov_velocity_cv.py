"""Same-case, location-marginal selection for categorical velocity kernels."""
import hashlib
import time

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

from data3001.modelling.markov import forecast
from data3001.modelling.markov_velocity import BINS, coarse_velocity, marginal_locations

LAGS = (1, 3, 5, 7)
LAMBDAS = tuple(k/10 for k in range(11))
CASE_KEYS = ['id', 'horizon_days', 'origin_cell_1', 'origin_velocity_bin', 'destination_cell_1']


def release_counts(atoms, cuts, threshold):
    frame = atoms.copy()
    frame['origin_velocity_bin'] = coarse_velocity(frame.origin_atom, cuts, threshold)
    return frame.groupby(CASE_KEYS, as_index=False, sort=True).pair_count.sum()


def predict_locations(kernels, origins, horizons, lag, lam):
    """One shared propagation per lambda/lag; exact saved remainder products."""
    origins = list(origins); horizons = sorted(set(int(h) for h in horizons)); op = kernels[lag]
    if not horizons or any(not 1 <= h <= 365 for h in horizons):
        raise ValueError('Invalid forecast horizons')
    for h in horizons:
        r = h % lag
        if r and (r not in kernels or kernels[r].lag_days != r
                  or kernels[r].training_ids != op.training_ids or kernels[r].cells != op.cells
                  or kernels[r].threshold != op.threshold or kernels[r].cuts != op.cuts):
            raise ValueError('Missing or differently encoded remainder')
    index = {c: i for i, c in enumerate(op.cells)}
    if any(c not in index or isinstance(b, bool) or int(b) != b or not 0 <= b < BINS for c, b in origins):
        raise ValueError('Invalid origin state')
    columns = np.array([index[c]*BINS+int(b) for c, b in origins], dtype=int)
    p = csr_matrix((np.ones(len(origins)), (np.arange(len(origins)), columns)),
                   shape=(len(origins), len(op.cells)*BINS+2))
    result = {}
    for step in range(max(h//lag for h in horizons)+1):
        for h in horizons:
            if h//lag == step:
                r = h % lag
                q = p@kernels[r].matrix(lam) if r else p
                if not np.isfinite(q.data).all() or (q.data < 0).any():
                    raise ValueError('Invalid propagated probability')
                np.testing.assert_allclose(np.asarray(q.sum(axis=1)).ravel(), 1, rtol=0, atol=1e-10)
                result[h] = marginal_locations(q, op.cells)
        if step < max(h//lag for h in horizons): p = p@op.matrix(lam)
    return result


def _loss(group, origins, probabilities):
    index = {key: i for i, key in enumerate(origins)}
    ix = np.array([index[(int(c), int(b))] for c, b in zip(group.origin_cell_1, group.origin_velocity_bin)])
    base = np.array([1+sum(v*v for v in p.values())+u*u for p, u in probabilities])
    true = np.array([probabilities[i][0].get(int(y), 0.) for i, y in zip(ix, group.destination_cell_1)])
    return float(group.pair_count.to_numpy(float)@(base[ix]-2*true))


def score_candidates(kernels, plain_kernels, releases, evaluation_ids, *, lambdas=LAMBDAS, progress=None):
    fit = next(iter(kernels.values())).training_ids
    if fit & set(evaluation_ids): raise ValueError('Fitting and held-out ID overlap')
    held = releases.loc[releases.id.isin(evaluation_ids)]
    if held.empty: raise ValueError('No held-out R support; folds must not be changed')
    groups = {int(h): g for h, g in held.groupby('horizon_days')}
    origins = sorted(set(zip(held.origin_cell_1.astype(int), held.origin_velocity_bin.astype(int))))
    digest = hashlib.sha256(held[CASE_KEYS+['pair_count']].to_numpy(dtype='<i8').tobytes()).hexdigest()
    rows = []
    for lag in LAGS:
        begun = time.monotonic()
        for lam in lambdas:
            if lam == 1.:
                # Exact algebraic degeneration; joint equality is separately
                # audited on all outer evaluation origin states.
                cache = {(h, c): forecast(plain_kernels[lag], c, h,
                         plain_kernels[h % lag] if h % lag else None) for h in groups for c, _ in origins}
                p = {h: [cache[(h, c)] for c, _ in origins] for h in groups}
            else:
                p = predict_locations(kernels, origins, groups, lag, lam)
            for h, g in groups.items():
                loss = _loss(g, origins, p[h])
                rows.append({'horizon_days': h, 'lag_days': lag, 'lambda_value': float(lam),
                             'loss_sum': loss, 'pair_count': int(g.pair_count.sum()),
                             'independent_ids': int(g.id.nunique()), 'S': loss/g.pair_count.sum(),
                             'case_digest': digest})
            for op in kernels.values(): op.clear_cache()
        if progress: progress(f'Candidate lag {lag}: {time.monotonic()-begun:.1f}s', flush=True)
    return pd.DataFrame(rows)


def choose_parameters(stats, lambda_restrict=None):
    part = stats if lambda_restrict is None else stats.loc[stats.lambda_value.eq(lambda_restrict)]
    result = {}
    for h, group in part.groupby('horizon_days'):
        g = group.groupby(['lag_days', 'lambda_value'], as_index=False)[['loss_sum', 'pair_count']].sum()
        if g.empty or (g.pair_count <= 0).any() or g.pair_count.nunique() != 1:
            raise ValueError('Missing or unmatched candidate cases')
        g['S'] = g.loss_sum/g.pair_count
        if not np.isfinite(g.S).all(): raise ValueError('Unscored candidate')
        eligible = g.loc[g.S <= g.S.min()+1e-12].sort_values(['lag_days', 'lambda_value'], ascending=[True, False])
        row = eligible.iloc[0]; result[int(h)] = (int(row.lag_days), float(row.lambda_value))
    if not result: raise ValueError('No parameter selection support')
    return result


def tag_velocity_common(scores, models):
    keys = ['outer_fold']+CASE_KEYS
    grouped = scores.groupby(keys)
    if (scores.duplicated(keys+['model']).any() or set(scores.model) != set(models)
            or not grouped.model.nunique().eq(len(models)).all()
            or not grouped.pair_count.nunique().eq(1).all()):
        raise ValueError('Velocity-aware evaluation cases differ')
    scores['spatial_status_complete'] = scores.spatial_status.eq('complete_in_domain')
    scores['spatial_common'] = scores.spatial_status_complete.groupby([scores[k] for k in keys]).transform('all')
    scores['complete_common'] = scores.complete.groupby([scores[k] for k in keys]).transform('all')
    return scores
