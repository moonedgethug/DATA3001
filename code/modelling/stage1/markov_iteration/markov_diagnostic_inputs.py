"""Qualified lag counts and retrospective matched cohorts; no new cleaning."""
import hashlib
import time

import numpy as np
import pandas as pd

from data3001.dataset import PreparedSource, manifest
from data3001.modelling.markov_models.markov_inputs import KEYS, _validate, count_pairs, audit_pairs, secondary_audit
from data3001.modelling.common.runtime import save_frame
from data3001.preprocessing.prep_pairs import load_track, origin_indices, generate

KERNEL_DAYS = (1, 2, 3, 5, 7)
DIAGNOSTIC_DAYS = (1, 2, 3, 5, 7, 30)
SOURCE_KEYS = ['id', 'origin_source_obs']


def matched_release_counts(stopped_by_day):
    """Intersect exact source keys across horizons; return counts and keys."""
    if set(stopped_by_day) != set(DIAGNOSTIC_DAYS):
        raise ValueError('All declared diagnostic horizons are required')
    common = None
    eligible = {}
    for h, ledger in sorted(stopped_by_day.items()):
        if not ledger.horizon_days.eq(h).all():
            raise ValueError('Horizon label mismatch')
        eligible[h] = _validate(ledger)
        keys = eligible[h][SOURCE_KEYS]
        common = keys if common is None else common.merge(keys, on=SOURCE_KEYS, validate='one_to_one')
    common = common.sort_values(SOURCE_KEYS).reset_index(drop=True)
    parts = [count_pairs(part.merge(common, on=SOURCE_KEYS, validate='one_to_one'))
             for part in eligible.values()]
    counts = pd.concat(parts, ignore_index=True)
    if not counts.empty and not counts.groupby('horizon_days').pair_count.sum().eq(len(common)).all():
        raise ValueError('Matched horizon counts differ')
    return counts, common


def controlled_counts(stopped_by_day, r_source_obs):
    """Three-day-qualified D windows, with E absorbing after the initial exit.

    Counts are diagnostic window/phase counts, not new production weights.
    Population R means the original release was in R, not every later phase.
    """
    columns = KEYS + ['pair_count', 'kind', 'population']
    common = None
    for h in (1, 2, 3):
        ledger = stopped_by_day[h]
        eligible = _validate(ledger)
        fields = SOURCE_KEYS + ['origin_cell_1', 'destination_cell_1'] if h == 1 else SOURCE_KEYS + ['destination_cell_1']
        part = eligible[fields].rename(columns={'destination_cell_1': f'c{h}'})
        common = part if common is None else common.merge(part, on=SOURCE_KEYS, validate='one_to_one')
    if common.id.nunique() > 1:
        raise ValueError('Controlled adapter requires one source instrument at a time')
    common = common.rename(columns={'origin_cell_1': 'c0'})
    if common.empty:
        return pd.DataFrame(columns=columns)
    if ((common.c1.eq(-2) & (common.c2.ne(-2) | common.c3.ne(-2)))
            | (common.c2.eq(-2) & common.c3.ne(-2))).any():
        raise ValueError('Stopped exit cannot re-enter a controlled phase')
    parts = []
    for population, cohort in [('D', common), ('R', common.loc[common.origin_source_obs.isin(r_source_obs)])]:
        for kind, a, b, lag in [('step0', 0, 1, 1), ('step1', 1, 2, 1),
                               ('step2', 2, 3, 1), ('direct2', 0, 2, 2), ('direct3', 0, 3, 3)]:
            part = cohort[['id', f'c{a}', f'c{b}']].rename(
                columns={f'c{a}': 'origin_cell_1', f'c{b}': 'destination_cell_1'})
            part['horizon_days'] = lag
            grouped = part.groupby(KEYS, as_index=False).size().rename(columns={'size': 'pair_count'})
            if int(grouped.pair_count.sum()) != len(cohort):
                raise ValueError('Controlled phase count mismatch')
            grouped['kind'], grouped['population'] = kind, population
            parts.append(grouped)
    return pd.concat(parts, ignore_index=True)[columns]


def collect_diagnostic_inputs(paths, run, development_ids, parent_inputs, progress=print):
    data = manifest()
    ids = sorted(development_ids)
    if len(ids) != len(set(ids)) or any(data['records'][str(i)]['pool'] != 'train' for i in ids):
        raise PermissionError('Only unique development IDs may enter')
    source = PreparedSource(allow_test=False)
    transitions, releases, matched, controls, audits, secondary, summaries, traces = ([] for _ in range(8))
    start = time.monotonic()
    for n, sid in enumerate(ids, 1):
        frame, arrays, events = load_track(source, sid)
        origins = origin_indices(frame, arrays, 'D')
        ro = origin_indices(frame, arrays, 'R')
        digest = hashlib.sha256()
        daily = {}
        for h in KERNEL_DAYS:
            if not len(origins):
                break
            _, stopped = generate(frame, arrays, events, sid, origins, h, 'pooled', tolerance=0)
            transitions.append(count_pairs(stopped))
            audits.append(audit_pairs(stopped, 'D'))
            secondary.append(secondary_audit(stopped, 'D'))
            digest.update(stopped[['origin_source_obs', 'horizon_days', 'destination_cell_1', 'reason_code']].to_numpy(dtype='<i8').tobytes())
            if h <= 3:
                daily[h] = stopped
            if n <= 10:
                traces.append(stopped.groupby('reason_code').head(1).assign(population='D'))
        if daily:
            controls.append(controlled_counts(daily, set(frame.iloc[ro].source_obs)))
        common_size = 0
        if len(ro):
            ledgers = {}
            for h in DIAGNOSTIC_DAYS:
                _, stopped = generate(frame, arrays, events, sid, ro, h, 'pooled', tolerance=0)
                ledgers[h] = stopped
                releases.append(count_pairs(stopped))
                audits.append(audit_pairs(stopped, 'R'))
                secondary.append(secondary_audit(stopped, 'R'))
                digest.update(stopped[['origin_source_obs', 'horizon_days', 'destination_cell_1', 'reason_code']].to_numpy(dtype='<i8').tobytes())
            counts, common = matched_release_counts(ledgers)
            matched.append(counts)
            common_size = len(common)
            save_frame(paths, run['results']/'release_labels'/f'{sid}.parquet', pd.concat(ledgers.values(), ignore_index=True))
            save_frame(paths, run['results']/'matched_origin_keys'/f'{sid}.parquet', common)
        summaries.append({'id': sid, 'retained_rows': len(frame), 'D_origins': len(origins),
                          'R_origins': len(ro), 'common30_origins': common_size,
                          'source_sha256': data['records'][str(sid)]['sha256'],
                          'target_reason_digest': digest.hexdigest()})
        if n == 20 or n % 200 == 0 or n == len(ids):
            progress(f'Diagnostic input {n}/{len(ids)} IDs; {time.monotonic()-start:.1f}s', flush=True)
    def combined(parts, keys):
        nonempty = [p for p in parts if len(p)]
        if not nonempty:
            raise ValueError('Required diagnostic population has no support')
        return pd.concat(nonempty, ignore_index=True).sort_values(keys).reset_index(drop=True)
    transitions = combined(transitions, KEYS)
    releases = combined(releases, KEYS)
    matched = combined(matched, KEYS)
    controls = combined(controls, ['population', 'kind'] + KEYS)
    audit = pd.concat(audits, ignore_index=True)
    for population, table in [('D', transitions), ('R', releases)]:
        eligible = audit.loc[audit.population.eq(population) & audit.reason_code.eq(0)]
        pd.testing.assert_series_equal(table.groupby('horizon_days').pair_count.sum(),
                                       eligible.groupby('horizon_days').candidate_count.sum(), check_names=False)
    # Input expansion must reproduce the original eligible source population.
    old = pd.read_parquet(parent_inputs/'transition_counts_by_id.parquet')
    old = old.loc[old.id.isin(ids)].sort_values(KEYS).reset_index(drop=True)
    fresh = transitions.loc[transitions.horizon_days.eq(1)].reset_index(drop=True)
    pd.testing.assert_frame_equal(old, fresh)
    old = pd.read_parquet(parent_inputs/'release_counts_by_id.parquet')
    old = old.loc[old.id.isin(ids)].sort_values(KEYS).reset_index(drop=True)
    fresh = releases.loc[releases.horizon_days.isin([7, 30])].reset_index(drop=True)
    pd.testing.assert_frame_equal(old, fresh)
    for name, table in [('transition_counts_by_id.parquet', transitions),
                        ('release_counts_by_id.parquet', releases), ('matched_release_counts.parquet', matched),
                        ('controlled_counts.parquet', controls), ('candidate_reasons.csv', audit),
                        ('secondary_predicates.csv', pd.concat(secondary, ignore_index=True)),
                        ('source_ID_summary.csv', pd.DataFrame(summaries)),
                        ('trace_examples.parquet', pd.concat(traces, ignore_index=True))]:
        save_frame(paths, run['results']/name, table)
    return {'IDs_read': len(ids), 'retained_rows_read': sum(x['retained_rows'] for x in summaries),
            'D_pair_groups': len(transitions), 'common30_origins': sum(x['common30_origins'] for x in summaries),
            'daily_and_7_30_parent_counts_identical': True, 'elapsed_seconds': time.monotonic()-start}
