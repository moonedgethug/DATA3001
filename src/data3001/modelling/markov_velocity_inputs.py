"""Lossless per-ID velocity count cache; fitting-only median definitions."""
import hashlib
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from data3001.dataset import PreparedSource, manifest
from data3001.modelling.markov_velocity import ATOM_KEYS, PLAIN_KEYS, velocity_atoms
from data3001.modelling.markov_inputs import audit_pairs
from data3001.modelling.run_blend_cv import save_frame, save_json
from data3001.preprocessing.prep_pairs import load_track, origin_indices, generate

KERNELS = (1, 2, 3, 5, 7)


def threshold_records(speeds_by_id, outer, inner):
    """Each role's model median is determined without its held-out features."""
    ids = set(speeds_by_id)
    if not ids or not ids <= set(outer):
        raise ValueError('Invalid threshold population')
    roles = {'development': ids}
    for f in sorted(set(outer.values())):
        fit = {i for i in ids if outer[i] != f}
        if not fit <= set(inner[f]) or set(inner[f]) != {i for i in outer if outer[i] != f}:
            raise ValueError('Inner map differs from outer fitting population')
        roles[f'outer_{f}'] = fit
        for j in sorted(set(inner[f].values())):
            roles[f'inner_{f}_{j}'] = {i for i in fit if inner[f][i] != j}
    result = {}
    for role, fit in roles.items():
        arrays = [np.asarray(speeds_by_id[i], dtype=float) for i in sorted(fit)]
        if (not fit or any(not np.isfinite(x).all() or (x < 0).any() for x in arrays)
                or not sum(len(x) for x in arrays)):
            raise ValueError('Threshold fit has no qualified D observations')
        positive = np.concatenate([x[x > 0] for x in arrays])
        count = len(positive)
        m = float(np.median(positive, overwrite_input=True)) if count else 0.
        result[role] = {'threshold_m_s': m, 'fitting_ids': sorted(fit),
                        'positive_origins': count, 'all_origins': sum(len(x) for x in arrays)}
    return result


def attach_velocity_atoms(ledger, track, cuts, *, endpoint_velocity):
    required = set(PLAIN_KEYS) | {'origin_source_obs', 'endpoint_source_obs', 'reason_code', 'target'}
    if (not required <= set(ledger) or not ledger.target.eq('stopped').all()
            or track.source_obs.duplicated().any()
            or ledger.duplicated(['id', 'horizon_days', 'origin_source_obs']).any()):
        raise ValueError('Ambiguous or invalid stopped/source keys')
    d = ledger.loc[ledger.reason_code.eq(0)].copy().reset_index(drop=True)
    index = pd.Index(track.source_obs)
    oi = index.get_indexer(d.origin_source_obs)
    if (oi < 0).any(): raise ValueError('Origin absent from source')
    origin = track.iloc[oi]
    if (not np.array_equal(origin.id, d.id) or not np.array_equal(origin.cell_1, d.origin_cell_1)
            or not d.horizon_days.between(1, 365).all()):
        raise ValueError('Origin identity, cell or horizon mismatch')
    result = d[PLAIN_KEYS+['origin_source_obs', 'endpoint_source_obs']].copy()
    result['origin_atom'] = velocity_atoms(origin.ve, origin.vn, cuts)
    outside = d.destination_cell_1.eq(-2).to_numpy()
    known = np.flatnonzero(~outside)
    ei = index.get_indexer(d.endpoint_source_obs.iloc[known])
    if (ei < 0).any(): raise ValueError('Nonexit endpoint absent from source')
    end = track.iloc[ei]
    if (not np.array_equal(end.id, d.id.iloc[known])
            or not np.array_equal(end.cell_1, d.destination_cell_1.iloc[known])
            or not np.array_equal(end.time.to_numpy()-origin.time.to_numpy()[known],
                                  d.horizon_days.to_numpy()[known]*86400)):
        raise ValueError('Endpoint identity, cell or exact time mismatch')
    if endpoint_velocity:
        result['destination_atom'] = np.full(len(result), -2, dtype='int16')
        result.loc[known, 'destination_atom'] = velocity_atoms(end.ve, end.vn, cuts)
    return result


def _counts(rows, *, endpoint_velocity):
    keys = ATOM_KEYS if endpoint_velocity else PLAIN_KEYS+['origin_atom']
    return rows.groupby(keys, as_index=False, sort=True).size().rename(columns={'size': 'pair_count'}).astype('int64')


def _plain(counts):
    return counts.groupby(PLAIN_KEYS, as_index=False, sort=True).pair_count.sum().astype('int64')


def collect_velocity_inputs(paths, run, ids, parent_root, outer, inner, progress=print):
    begun = time.monotonic(); ids = sorted(ids); data = manifest()
    if len(ids) != len(set(ids)) or any(data['records'][str(i)]['pool'] != 'train' for i in ids):
        raise PermissionError('Unique development instruments only')
    source = PreparedSource(allow_test=False)
    speeds, summaries = {}, []
    for n, sid in enumerate(ids, 1):
        frame, a, _ = load_track(source, sid)
        q = a['position_ok'] & a['mapping_ok'] & a['inside_D']
        speeds[sid] = np.hypot(frame.ve.to_numpy(float)[q], frame.vn.to_numpy(float)[q])
        summaries.append({'id': sid, 'retained_rows': len(frame), 'qualified_D_observations': int(q.sum()),
                          'source_sha256': data['records'][str(sid)]['sha256']})
        if n % 800 == 0 or n == len(ids): progress(f'Velocity median sources {n}/{len(ids)}', flush=True)
    thresholds = threshold_records(speeds, outer, inner)
    cuts = sorted(set(x['threshold_m_s'] for x in thresholds.values()))
    save_json(paths, run['results']/'thresholds.json', {'cutpoints': cuts, 'roles': thresholds,
              'cache_encoding': 'zero=0; nonzero=1+quadrant*(len(cuts)+1)+searchsorted_left(cuts,speed)',
              'model_encoding': 'zero=0; nonzero=1+2*quadrant+int(speed>fit_median)'})
    del speeds
    old = pd.read_parquet(parent_root/'transition_counts_by_id.parquet')
    old_D = {int(i): g.reset_index(drop=True) for i, g in old.groupby('id') if int(i) in ids}
    old_R_all = pd.read_parquet(parent_root/'release_counts_by_id.parquet')
    old_R = {int(i): g.loc[g.horizon_days.isin([7, 30])].reset_index(drop=True)
             for i, g in old_R_all.groupby('id') if int(i) in ids}
    parent_summary = pd.read_csv(parent_root/'source_ID_summary.csv').set_index('id')
    releases, audits, checks, traces = [], [], [], []
    schema = pa.schema([(k, pa.int64()) for k in ATOM_KEYS+['pair_count']])
    group_total = 0; eligible_total = 0

    def write_transition_cache(stream):
        nonlocal group_total, eligible_total
        with pq.ParquetWriter(stream, schema, compression='zstd') as writer:
            for number, sid in enumerate(ids, 1):
                frame, a, events = load_track(source, sid)
                origins = origin_indices(frame, a, 'D')
                pieces = []; digest = hashlib.sha256()
                for h in KERNELS:
                    if not len(origins): break
                    _, stopped = generate(frame, a, events, sid, origins, h, 'pooled', tolerance=0)
                    digest.update(stopped[['origin_source_obs', 'horizon_days', 'destination_cell_1', 'reason_code']]
                                  .to_numpy(dtype='<i8').tobytes())
                    audits.append(audit_pairs(stopped, 'D'))
                    rows = attach_velocity_atoms(stopped, frame, cuts, endpoint_velocity=True)
                    pieces.append(_counts(rows, endpoint_velocity=True))
                    if number <= 10 and len(rows): traces.append(rows.head(2).assign(population='D'))
                d = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(columns=schema.names).astype('int64')
                expected = old_D.get(sid, pd.DataFrame(columns=PLAIN_KEYS+['pair_count']).astype('int64'))
                pd.testing.assert_frame_equal(_plain(d), expected.sort_values(PLAIN_KEYS).reset_index(drop=True))
                writer.write_table(pa.Table.from_pandas(d, schema=schema, preserve_index=False))
                group_total += len(d); eligible_total += int(d.pair_count.sum())
                rfile = parent_root/'release_labels'/f'{sid}.parquet'
                if rfile.exists():
                    labels = pd.read_parquet(rfile)
                    for _, part in labels.groupby('horizon_days', sort=True):
                        digest.update(part[['origin_source_obs', 'horizon_days', 'destination_cell_1', 'reason_code']]
                                      .to_numpy(dtype='<i8').tobytes())
                    selected = labels.loc[labels.horizon_days.isin([7, 30])]
                    rows = attach_velocity_atoms(selected, frame, cuts, endpoint_velocity=False)
                    r = _counts(rows, endpoint_velocity=False)
                    expected_R = old_R.get(sid, pd.DataFrame(columns=PLAIN_KEYS+['pair_count']).astype('int64'))
                    pd.testing.assert_frame_equal(_plain(r), expected_R.sort_values(PLAIN_KEYS).reset_index(drop=True))
                    releases.append(r); audits.append(audit_pairs(selected, 'R'))
                    if number <= 10 and len(rows): traces.append(rows.head(2).assign(population='R'))
                if digest.hexdigest() != parent_summary.loc[sid, 'target_reason_digest']:
                    raise ValueError(f'Qualified source keys/reasons changed: {sid}')
                checks.append({'id': sid, 'source_target_digest': digest.hexdigest(),
                               'D_pair_count': int(d.pair_count.sum()), 'D_count_groups': len(d),
                               'exact_parent_counts_and_source_keys': True})
                if number % 200 == 0 or number == len(ids):
                    progress(f'Velocity pair cache {number}/{len(ids)}; {time.monotonic()-begun:.1f}s', flush=True)

    paths.publish(run['results']/'transition_counts_by_id.parquet', write_transition_cache)
    if not releases: raise ValueError('No eligible R release support')
    release = pd.concat(releases, ignore_index=True)
    audit = pd.concat(audits, ignore_index=True)
    save_frame(paths, run['results']/'release_counts_by_id.parquet', release)
    save_frame(paths, run['results']/'candidate_reasons.csv', audit)
    save_frame(paths, run['results']/'source_ID_summary.csv', pd.DataFrame(summaries).merge(pd.DataFrame(checks), on='id'))
    save_frame(paths, run['results']/'trace_examples.parquet', pd.concat(traces, ignore_index=True))
    return {'IDs_read': len(ids), 'retained_rows': sum(x['retained_rows'] for x in summaries),
            'D_pair_groups': group_total, 'D_eligible_pairs_all_kernel_days': eligible_total,
            'R_eligible_pairs': {str(int(h)): int(g.pair_count.sum()) for h, g in release.groupby('horizon_days')},
            'unique_cache_cutpoints': len(cuts), 'all_source_keys_and_parent_counts_identical': True,
            'elapsed_seconds': time.monotonic()-begun}
