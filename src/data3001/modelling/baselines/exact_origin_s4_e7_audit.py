"""Independent E7 artifact audit without the model's scoring helpers."""
from collections import Counter
import hashlib
import json

import numpy as np
import pandas as pd
from scipy import sparse
from pyproj import Geod

from data3001.paths import file_sha256


KEY = ['id', 'origin_source_obs', 'horizon_days']
METRICS = ['brier', 'h90', 'k90', 'area90', 'mass', 'zero', 'exit', 'geographic_mass', 'exit_in_region']
RESOLUTIONS = (1., .5)
DEST = {1.: 'destination_cell_1', .5: 'destination_cell_05'}
GEOD = Geod(ellps='WGS84')


def independent_weights(frame):
    """Count the hierarchy directly, without the production weighting function."""
    pairs = list(zip(frame.origin_cell_1, frame.id))
    counts = Counter(pairs)
    identities = {}
    for origin, ident in pairs:
        identities.setdefault(origin, set()).add(ident)
    return np.array([1. / (len(identities) * len(identities[origin]) * counts[origin, ident])
                     for origin, ident in pairs])


def independent_metrics(codes, probability, truth, area):
    """Reconstruct the one-hot error and region directly on sparse support."""
    codes = np.asarray(codes)
    p = np.asarray(probability, dtype=float)
    assert len(p) and len(p) == len(codes)
    assert np.isfinite(p).all() and np.all(p > 0)
    assert np.all(np.diff(codes) > 0) and abs(p.sum() - 1) <= 1e-12
    order = np.argsort(-p, kind='stable')
    cumulative = np.cumsum(p[order])
    crossing = np.flatnonzero(cumulative >= .90 - 1e-12)
    assert len(crossing)
    cutoff = p[order[crossing[0]]]
    region = p >= cutoff - 1e-12
    residual = p.copy()
    found = np.flatnonzero(codes == truth)
    if len(found):
        residual[found[0]] -= 1.
    brier = float(sum(value * value for value in residual) + int(not len(found)))
    geographic = codes >= 0
    selected = codes[region]
    values = np.array([
        brier, bool(len(found) and region[found[0]]), int(np.count_nonzero(region & geographic)),
        sum(float(area[int(code)]) for code in selected if code >= 0),
        float(p[region].sum()), not len(found), float(p[codes == -2].sum()),
        float(p[region & geographic].sum()), bool(np.any(region & (codes == -2))),
    ], dtype=float)
    return values, selected


def _check_values(actual, expected):
    tolerance = np.full(len(METRICS), 1e-12)
    tolerance[METRICS.index('area90')] = 1e-9
    assert np.all(np.abs(np.asarray(actual) - np.asarray(expected)) <= tolerance)


def _weighted_metrics(frame, weights):
    """Keep boolean indicators numeric during large weighted reductions."""
    from math import fsum
    values=frame[METRICS].to_numpy(dtype=float)
    weights=np.asarray(weights,dtype=float)
    return np.array([fsum(weights*values[:,i]) for i in range(len(METRICS))])


def _support(frame, k, cfg):
    n = frame.n.to_numpy()
    ids = frame.donor_ids.to_numpy()
    assert np.isfinite(n).all() and np.all(n == n.astype('int64')) and np.all(n >= 1)
    assert np.all(ids >= 1) and np.all(ids <= n) and np.all(ids == ids.astype('int64'))
    share = frame.largest_id_share.to_numpy()
    assert np.isfinite(share).all() and np.all(share <= 1) and np.all(share >= 1 / ids - 1e-12)
    assert np.all(np.abs(share * n - np.round(share * n)) <= 1e-9)
    assert np.isfinite(frame.farthest_m).all() and frame.farthest_m.ge(0).all()
    assert frame.farthest_m.le(cfg['radius_m'] + cfg['distance_tolerance_m']).all()
    assert np.array_equal(frame.tie_extra.to_numpy(), np.maximum(n - k, 0))
    assert np.array_equal(frame.cap_limited.to_numpy(dtype=bool), n < k)
    assert frame.lineage_digest.str.fullmatch('[0-9a-f]{64}').all()


def _inner_selection(directory, cfg):
    inner = pd.read_parquet(directory / 'inner_cases.parquet')
    assert set(inner.k.unique()) == set(cfg['ks']) and not inner.duplicated(KEY + ['k']).any()
    assert inner.horizon_days.eq(7).all()
    common = None
    pooled = {}
    curves = pd.read_csv(directory / 'inner_curves.csv')
    for k, frame in inner.groupby('k', sort=True):
        frame = frame.sort_values(KEY).reset_index(drop=True)
        if common is None:
            common = frame[KEY + ['origin_cell_1', 'role']]
        else:
            pd.testing.assert_frame_equal(common, frame[KEY + ['origin_cell_1', 'role']], check_exact=True)
        weights = independent_weights(frame)
        assert np.allclose(weights, frame.weight, atol=1e-12, rtol=0)
        _support(frame, int(k), cfg)
        pooled[int(k)] = float(weights @ frame.brier.to_numpy())
        for name, subgroup in [('pooled', frame), *list(frame.groupby('role', sort=True))]:
            normalized = subgroup.weight / subgroup.weight.sum()
            expected = _weighted_metrics(subgroup, normalized)
            recorded = curves[curves.fold.eq(name) & curves.k.eq(k)]
            assert len(recorded) == 1
            _check_values(recorded[METRICS].iloc[0].to_numpy(), expected)
    minimum = min(pooled.values())
    selected = max(k for k, value in pooled.items() if value <= minimum + 1e-12)
    choices = pd.read_csv(directory / 'choices.csv')
    assert len(choices) == 1 and int(choices.k.iloc[0]) == selected
    assert abs(float(choices.inner_brier.iloc[0]) - pooled[selected]) <= 1e-12
    assert float(choices.radius_m.iloc[0]) == cfg['radius_m']
    eligible_counts = {}
    for role in ['C_T0', 'C_T1']:
        eligibility = pd.read_parquet(directory / (role + '_eligibility.parquet'))
        assert not eligibility.duplicated(KEY).any()
        assert np.allclose(independent_weights(eligibility), eligibility.weight, atol=1e-12, rtol=0)
        expected = eligibility.loc[eligibility.supported, KEY].sort_values(KEY).reset_index(drop=True)
        actual = common.loc[common.role.eq(role), KEY].sort_values(KEY).reset_index(drop=True)
        pd.testing.assert_frame_equal(actual, expected, check_exact=True)
        eligible_counts[role] = {'eligible': len(eligibility), 'scored': len(actual),
                                 'unsupported': int((~eligibility.supported).sum())}
    return selected, eligible_counts


def _paired_inference(directory, checked, cfg):
    multipliers = np.load(directory / 'multipliers.npy')
    archived = np.load(directory / 'paired_draws.npy')
    ids = sorted(int(ident) for ident in checked[1.].id.unique())
    iid = {ident: index for index, ident in enumerate(ids)}
    expected_rng = np.random.Generator(np.random.PCG64(cfg['bootstrap_seed'])).exponential(
        size=(cfg['bootstrap_draws'], len(ids)))
    assert np.array_equal(multipliers, expected_rng)
    assert archived.shape == (2, cfg['bootstrap_draws'], len(METRICS))
    paired = pd.read_csv(directory / 'paired.csv')
    for resolution_index, resolution in enumerate(RESOLUTIONS):
        frame = checked[resolution]
        columns = ['delta_' + metric for metric in METRICS]
        unit = frame.groupby(['origin_cell_1', 'id'])[columns].mean().reset_index()
        independent = np.zeros((len(multipliers), len(METRICS)))
        point = np.zeros(len(METRICS))
        origins = unit.origin_cell_1.nunique()
        for _, group in unit.groupby('origin_cell_1', sort=True):
            weight = multipliers[:, [iid[int(ident)] for ident in group.id]]
            weight = weight / weight.sum(axis=1, keepdims=True)
            independent += weight @ group[columns].to_numpy() / origins
            point += group[columns].mean().to_numpy() / origins
        _check_values(independent, archived[resolution_index])
        row = paired[paired.resolution.eq(resolution)].iloc[0]
        _check_values(point, row[columns].to_numpy(dtype=float))
        lower, upper = np.quantile(independent, [.025, .975], axis=0, method='linear')
        _check_values(lower, row[[metric + '_lower95' for metric in METRICS]].to_numpy(dtype=float))
        _check_values(upper, row[[metric + '_upper95' for metric in METRICS]].to_numpy(dtype=float))
        primary_bound = float(point[0] - np.quantile(independent[:, 0] - point[0], .05, method='linear'))
        assert abs(primary_bound - row.centered_brier_upper95) <= 1e-12
        supported = bool(resolution == 1. and point[0] < -1e-12 and primary_bound < 0)
        assert bool(row.brier_supported) == supported
    coarse = paired[paired.resolution.eq(1.)].iloc[0]
    fine = paired[paired.resolution.eq(.5)].iloc[0]
    supported = bool(coarse.delta_brier < -1e-12 and coarse.centered_brier_upper95 < 0)
    legacy = bool(coarse.delta_brier < -1e-12 and coarse.delta_h90 >= -1e-12 and coarse.delta_k90 <= 1e-12)
    fine_ok = bool(fine.delta_brier <= 1e-12 and fine.delta_h90 >= -1e-12
                   and fine.delta_k90 <= 1e-12 and fine.delta_area90 <= 1e-9)
    decision = pd.read_csv(directory / 'decision.csv').iloc[0]
    assert bool(decision.primary_brier_supported) == supported
    assert bool(decision.legacy_quality_preserved) == legacy
    assert bool(decision.fine_quality_preserved) == fine_ok
    assert bool(decision.recommend_replacement) == (supported and legacy and fine_ok)
    return {'draws': len(multipliers), 'independent_ids': len(ids), 'primary_brier_supported': supported,
            'legacy_quality_preserved': legacy, 'fine_quality_preserved': fine_ok}


def audit_outputs(paths, run, cfg):
    """Audit saved predictions, scores and decisions before sealing the run."""
    assert cfg['radius_m'] == 100000 and not cfg['final_test_access']
    directory = run['results']
    freeze = json.loads((run['provenance'] / 'forecast_freeze.json').read_text())
    assert freeze['status'] == 'FROZEN_BEFORE_OUTER_SCORING'
    for name, digest in freeze['files'].items():
        path = (directory / name).resolve()
        assert path.is_relative_to(directory.resolve())
        assert file_sha256(path) == digest, name
    selected, inner_counts = _inner_selection(directory, cfg)
    assert int(freeze['selected_k']) == selected
    roster = pd.read_parquet(directory / 'outer_roster.parquet')
    targets = pd.read_parquet(directory / 'outer_targets.parquet')
    cases = pd.read_parquet(directory / 'case_scores.parquet')
    assert len(roster) == 33971 and roster.id.nunique() == 45 and roster.origin_cell_1.nunique() == 36
    assert not roster.duplicated(KEY).any() and roster.supported.all()
    assert not targets.duplicated(KEY).any() and len(targets) == len(roster)
    assert not cases.duplicated(KEY + ['resolution']).any() and len(cases) == 2 * len(roster)
    labels = roster[KEY].merge(targets, on=KEY, validate='one_to_one', sort=False)
    pd.testing.assert_frame_equal(labels[KEY], roster[KEY], check_exact=True)
    weights = independent_weights(roster)
    assert np.allclose(weights, roster.weight, atol=1e-12, rtol=0)
    _support(roster, selected, cfg)
    state_index = pd.read_parquet(paths.asset('state_index', verify=True))
    training = pd.read_parquet(directory / 'training_coordinates.parquet')
    summary = pd.read_csv(directory / 'summary.csv')
    checked, matrices, state_arrays = {}, {}, {}
    for resolution in RESOLUTIONS:
        state = state_index.loc[state_index.resolution.eq(resolution)].set_index('cell')
        area = state.wet_area_km2.to_dict()
        area[-2] = 0.
        current = cases.loc[cases.resolution.eq(resolution)].reset_index(drop=True)
        pd.testing.assert_frame_equal(current[KEY], roster[KEY], check_exact=True)
        assert np.allclose(current.weight, weights, atol=1e-12, rtol=0)
        truth = labels[DEST[resolution]].to_numpy(dtype='int64')
        assert np.array_equal(current.observed_exit.to_numpy(), truth == -2)
        independent = roster[KEY + ['origin_cell_1']].copy()
        independent['weight'] = weights
        for model in ['Annual', 'Exact']:
            prefix = directory / 'forecasts' / f"{model}_{str(resolution).replace('.', 'p')}"
            probabilities = sparse.load_npz(prefix.with_name(prefix.name + '_probabilities.npz')).tocsr()
            regions = sparse.load_npz(prefix.with_name(prefix.name + '_regions.npz')).tocsr()
            states = np.load(prefix.with_name(prefix.name + '_states.npy'))
            assert np.all(np.diff(states) > 0) and set(states) == set(state.index) | {-2}
            assert probabilities.shape == regions.shape == (len(roster), len(states))
            assert probabilities.has_canonical_format and regions.has_canonical_format
            matrices[model, resolution] = probabilities
            state_arrays[model, resolution] = states
            scores = np.empty((len(roster), len(METRICS)))
            baseline_rows = {}
            if model == 'Annual':
                for cell, group in training.groupby('origin_cell_1', sort=True):
                    codes, counts = np.unique(group[DEST[resolution]].to_numpy(), return_counts=True)
                    baseline_rows[int(cell)] = (codes, counts / counts.sum())
            for index in range(len(roster)):
                start, end = probabilities.indptr[index:index + 2]
                codes = states[probabilities.indices[start:end]]
                values = probabilities.data[start:end]
                scores[index], expected_region = independent_metrics(codes, values, truth[index], area)
                a, b = regions.indptr[index:index + 2]
                saved_region = states[regions.indices[a:b][regions.data[a:b].astype(bool)]]
                assert np.array_equal(expected_region, saved_region)
                if model == 'Annual':
                    expected_codes, expected_prob = baseline_rows[int(roster.origin_cell_1.iloc[index])]
                    assert np.array_equal(codes, expected_codes)
                    assert np.allclose(values, expected_prob, atol=1e-12, rtol=0)
            _check_values(scores, current[[model + '_' + metric for metric in METRICS]].to_numpy())
            independent[[model + '_' + metric for metric in METRICS]] = scores
            recorded = summary[summary.resolution.eq(resolution) & summary.model.eq(model)]
            assert len(recorded) == 1
            _check_values(weights @ scores, recorded[METRICS].iloc[0].to_numpy())
        for metric in METRICS:
            independent['delta_' + metric] = (independent['Exact_' + metric].to_numpy(dtype=float)
                                              - independent['Annual_' + metric].to_numpy(dtype=float))
        checked[resolution] = independent
    for model in ['Annual', 'Exact']:
        fine_states = state_arrays[model, .5]
        parent = np.where(fine_states == -2, -2, (fine_states // 720 // 2) * 360 + (fine_states % 720 // 2))
        coarse_states = state_arrays[model, 1.]
        columns = pd.Index(coarse_states).get_indexer(parent)
        assert np.all(columns >= 0)
        aggregation = sparse.csr_matrix((np.ones(len(parent)), (np.arange(len(parent)), columns)),
                                        shape=(len(parent), len(coarse_states)))
        difference = matrices[model, .5] @ aggregation - matrices[model, 1.]
        assert not difference.nnz or np.max(np.abs(difference.data)) <= 1e-12
    source_index = pd.MultiIndex.from_frame(training[KEY])
    examples = json.loads((directory / 'example_selection.json').read_text())
    assert examples['outcomes_used'] is False
    for position in examples['query_positions']:
        donors = pd.read_parquet(directory / f'examples/donors_{position}.parquet')
        indices = source_index.get_indexer(pd.MultiIndex.from_frame(donors[KEY]))
        assert np.all(indices >= 0) and len(np.unique(indices)) == len(indices)
        row = roster.iloc[position]
        digest = hashlib.sha256(np.asarray(indices, dtype='<i8').tobytes()).hexdigest()
        assert digest == row.lineage_digest and len(indices) == row.n
        assert donors.id.nunique() == row.donor_ids
        assert abs(donors.id.value_counts().max() / len(donors) - row.largest_id_share) <= 1e-12
        _, _, distance = GEOD.inv(np.full(len(donors), row.lon), np.full(len(donors), row.lat), donors.lon, donors.lat)
        assert np.max(distance) <= cfg['radius_m'] + cfg['distance_tolerance_m']
        assert abs(float(np.max(distance)) - row.farthest_m) <= 1e-6
        for resolution in RESOLUTIONS:
            states = state_arrays['Exact', resolution]
            codes, counts = np.unique(donors[DEST[resolution]].to_numpy(), return_counts=True)
            vector = matrices['Exact', resolution].getrow(position)
            assert np.array_equal(states[vector.indices], codes)
            assert np.allclose(vector.data, counts / len(donors), atol=1e-12, rtol=0)
    inference = _paired_inference(directory, checked, cfg)
    return {'independent_audit_passed': True, 'outer_cases': len(roster), 'selected_k': selected,
            'radius_m': cfg['radius_m'], 'inner_eligibility': inner_counts,
            'frozen_files_rehashed': len(freeze['files']), 'forecast_vectors_checked': 4 * len(roster),
            'example_donor_lists_checked': len(examples['query_positions']),
            'sparse_regions_and_scores_recomputed': True, 'nested_grids_recomputed': True,
            'baseline_endpoint_counts_recomputed': True, 'no_final_test_access': True, **inference}
