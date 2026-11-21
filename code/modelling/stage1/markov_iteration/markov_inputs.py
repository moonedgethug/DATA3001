"""Source-keyed stopped labels and sufficient counts; no new cleaning rules."""
import hashlib
import time

import numpy as np
import pandas as pd

from data3001.dataset import PreparedSource, manifest
from data3001.modelling.common.runtime import save_frame
from data3001.preprocessing.prep_core import REASONS, SECONDARY
from data3001.preprocessing.prep_pairs import generate, load_track, origin_indices

KEYS = ['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1']
AUDIT_KEYS = ['id', 'horizon_days', 'departure_season', 'origin_cell_1']
PATH_PREDICATES = ('path_source_position_failure', 'path_geometry_failure', 'path_timestamp_gap')


def _validate(ledger):
    required = KEYS + ['origin_source_obs', 'reason_code', 'target']
    if not set(required).issubset(ledger.columns):
        raise ValueError('Missing stopped ledger fields')
    if not ledger.target.eq('stopped').all():
        raise ValueError('Endpoint and stopped cases cannot share a target table')
    if ledger.duplicated(['id', 'origin_source_obs', 'horizon_days']).any():
        raise ValueError('Duplicate candidate source keys')
    if not ledger.reason_code.isin(REASONS).all():
        raise ValueError('Unknown primary exclusion reason')
    eligible = ledger.loc[ledger.reason_code.eq(0)]
    if (not eligible.origin_cell_1.between(0, 64799).all()
            or not (eligible.destination_cell_1.between(0, 64799)
                    | eligible.destination_cell_1.eq(-2)).all()):
        raise ValueError('An eligible stopped case has an invalid state')
    return eligible


def count_pairs(ledger):
    eligible = _validate(ledger)
    return eligible.groupby(KEYS, as_index=False).size().rename(columns={'size': 'pair_count'}).astype('int64')


def audit_pairs(ledger, population):
    _validate(ledger)
    if population not in ('R', 'D'):
        raise ValueError('Unknown origin population')
    result = ledger.groupby(AUDIT_KEYS + ['reason_code'], as_index=False).size()
    result = result.rename(columns={'size': 'candidate_count'})
    result['population'] = population
    result['reason'] = result.reason_code.map(REASONS)
    if int(result.candidate_count.sum()) != len(ledger):
        raise ValueError('Candidate accounting failed')
    return result


def secondary_audit(ledger, population):
    """Non-disjoint predicate counts; never sum these as primary exclusions."""
    _validate(ledger)
    if population not in ('R', 'D'):
        raise ValueError('Unknown origin population')
    required = {'secondary_predicates', *PATH_PREDICATES}
    if not required.issubset(ledger.columns):
        raise ValueError('Missing secondary/path evidence')
    masks = {name: (ledger.secondary_predicates.to_numpy(dtype=np.uint16) & bit) != 0
             for bit, name in SECONDARY.items()}
    masks.update({name: ledger[name].to_numpy(dtype=bool) for name in PATH_PREDICATES})
    denominator = ledger.groupby(AUDIT_KEYS).size()
    parts = []
    for name, mask in masks.items():
        if not mask.any():
            continue
        flagged = ledger.loc[mask].groupby(AUDIT_KEYS).size()
        if (flagged > denominator.reindex(flagged.index)).any():
            raise ValueError('Secondary predicate exceeds candidate denominator')
        part = flagged.rename('flagged_count').reset_index()
        part['population'], part['predicate'] = population, name
        parts.append(part)
    return (pd.concat(parts, ignore_index=True) if parts else
            pd.DataFrame(columns=AUDIT_KEYS + ['flagged_count', 'population', 'predicate']))


def collect_inputs(paths, run, development_ids, durations=(1,), progress=print):
    data = manifest()
    ids = sorted(development_ids)
    if len(ids) != len(set(ids)) or any(data['records'][str(i)]['pool'] != 'train' for i in ids):
        raise PermissionError('Only unique development IDs may enter input preparation')
    if tuple(durations) != (1,):
        raise ValueError('This first prototype prepares a fixed one-day kernel only')
    source = PreparedSource(allow_test=False)
    count_parts, release_parts, audits, summaries, traces = [], [], [], [], []
    secondary_parts = []
    start = time.monotonic()
    for n, sid in enumerate(ids, 1):
        frame, arrays, events = load_track(source, sid)
        origins = origin_indices(frame, arrays, 'D')
        ro = origin_indices(frame, arrays, 'R')
        summary = {'id': sid, 'retained_rows': len(frame), 'D_origins': len(origins),
                   'R_origins': len(ro), 'source_sha256': data['records'][str(sid)]['sha256']}
        digest = hashlib.sha256()
        if len(origins):
            _, stopped = generate(frame, arrays, events, sid, origins, 1, 'pooled', tolerance=0)
            count_parts.append(count_pairs(stopped))
            audits.append(audit_pairs(stopped, 'D'))
            secondary_parts.append(secondary_audit(stopped, 'D'))
            digest.update(stopped[['origin_source_obs', 'horizon_days', 'destination_cell_1',
                                   'reason_code']].to_numpy(dtype='<i8').tobytes())
            summary['eligible_one_day_pairs'] = int(stopped.reason_code.eq(0).sum())
            if n <= 20:
                traces.append(stopped.groupby('reason_code', sort=True).head(1).assign(population='D'))
        else:
            summary['eligible_one_day_pairs'] = 0
        if len(ro):
            ledgers = []
            for h in (7, 30, 90, 180, 365):
                _, stopped = generate(frame, arrays, events, sid, ro, h, 'pooled', tolerance=0)
                audits.append(audit_pairs(stopped, 'R'))
                secondary_parts.append(secondary_audit(stopped, 'R'))
                digest.update(stopped[['origin_source_obs', 'horizon_days', 'destination_cell_1',
                                       'reason_code']].to_numpy(dtype='<i8').tobytes())
                if h in (7, 30):
                    ledgers.append(stopped)
                    release_parts.append(count_pairs(stopped))
                    if len(traces) < 80:
                        traces.append(stopped.groupby('reason_code', sort=True).head(1).assign(population='R'))
            save_frame(paths, run['results']/'release_labels'/f'{sid}.parquet', pd.concat(ledgers, ignore_index=True))
        summary['candidate_target_reason_digest'] = digest.hexdigest()
        summaries.append(summary)
        if n == 20 or n % 100 == 0 or n == len(ids):
            progress(f'Prepared {n}/{len(ids)} IDs; elapsed {time.monotonic()-start:.1f}s', flush=True)
    if not count_parts or not release_parts:
        raise ValueError('No supported D transitions or R evaluation cases')
    counts = pd.concat(count_parts, ignore_index=True).sort_values(KEYS).reset_index(drop=True)
    releases = pd.concat(release_parts, ignore_index=True).sort_values(KEYS).reset_index(drop=True)
    audit = pd.concat(audits, ignore_index=True)
    eligible_count = int(audit.loc[audit.population.eq('D') & audit.reason_code.eq(0), 'candidate_count'].sum())
    if int(counts.pair_count.sum()) != eligible_count:
        raise ValueError('One-day eligible count reconciliation failed')
    for h, part in releases.groupby('horizon_days'):
        total = int(audit.loc[audit.population.eq('R') & audit.horizon_days.eq(h)
                              & audit.reason_code.eq(0), 'candidate_count'].sum())
        if int(part.pair_count.sum()) != total:
            raise ValueError('Release label reconciliation failed')
    save_frame(paths, run['results']/'transition_counts_by_id.parquet', counts)
    save_frame(paths, run['results']/'release_counts_by_id.parquet', releases)
    save_frame(paths, run['results']/'candidate_reasons.csv', audit)
    save_frame(paths, run['results']/'secondary_predicates.csv', pd.concat(secondary_parts, ignore_index=True))
    save_frame(paths, run['results']/'source_ID_summary.csv', pd.DataFrame(summaries))
    save_frame(paths, run['results']/'trace_examples.parquet', pd.concat(traces, ignore_index=True))
    return {'IDs_read': len(ids), 'retained_rows_read': int(sum(x['retained_rows'] for x in summaries)),
            'D_candidate_origins': int(sum(x['D_origins'] for x in summaries)),
            'eligible_one_day_pairs': int(counts.pair_count.sum()), 'elapsed_seconds': time.monotonic()-start}
