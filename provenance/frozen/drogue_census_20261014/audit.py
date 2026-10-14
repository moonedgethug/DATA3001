"""Read-only census of frozen hourly drogue states; writes separate audit evidence.

This counts observations and IDs. It does not infer missing states, change
eligibility, read forecast endpoints, or fit any model.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import time

import numpy as np
import pyarrow.parquet as pq
import zarr

OUT = Path(__file__).resolve().parent
BASE = OUT.parent
raw = zarr.open_group(str(BASE.parent / 'raw/hourly_subset_v2.01.1.zarr'), mode='r')
raw_ids = np.asarray(raw['id'][:], dtype=np.int64)
raw_sizes = np.asarray(raw['rowsize'][:], dtype=np.int64)
expected_rows = dict(zip(raw_ids.tolist(), raw_sizes.tolist()))
context = pq.read_table(BASE / 'metadata/trajectory_context.parquet').to_pandas()
assert context.id.is_unique
meta = context.set_index('id').to_dict('index')
files = sorted((BASE / 'cleaned').glob('*.parquet')) + sorted((BASE / 'restricted_test/cleaned').glob('*.parquet'))
assert len(files) == len(raw_ids) == len(meta)
assert len({int(p.stem) for p in files}) == len(files)
assert {int(p.stem) for p in files} == set(expected_rows) == set(meta)

states = {1: 'drogued', 0: 'undrogued', -1: 'unknown'}
mask_names = {
    1: 'drogued_only', 2: 'undrogued_only', 3: 'drogued_and_undrogued_without_unknown',
    4: 'unknown_only', 5: 'drogued_and_unknown', 6: 'undrogued_and_unknown',
    7: 'drogued_and_undrogued_and_unknown',
}
totals = Counter()
raw_flags = Counter()
id_sets = {name: set() for name in states.values()}
groups = Counter({name: 0 for name in mask_names.values()})
reason_rows = Counter()
reason_ids = defaultdict(set)
by_split = defaultdict(Counter)
r_rows = Counter()
r_ids = {name: set() for name in states.values()}
records = []
source_manifest = []
started = time.monotonic()
minimum, maximum = np.inf, -np.inf

for number, path in enumerate(files, 1):
    ident = int(path.stem)
    loss = float(meta[ident]['drogue_lost_date'])
    split = str(meta[ident]['split'])
    table = pq.read_table(path, columns=['time', 'drogue_status', 'regime', 'in_R', 'analytical_row'])
    t = table['time'].to_numpy()
    flag = table['drogue_status'].to_numpy()
    regime = table['regime'].to_numpy()
    in_r = table['in_R'].to_numpy()
    analytical = table['analytical_row'].to_numpy()
    assert len(t) == expected_rows[ident], (ident, len(t), expected_rows[ident])
    assert set(np.unique(regime)).issubset(states), (ident, np.unique(regime))
    if np.isfinite(t).any():
        minimum = min(minimum, float(np.nanmin(t)))
        maximum = max(maximum, float(np.nanmax(t)))

    # Independently evaluate the documented finite-positive loss-date rule.
    reproduced = np.full(len(t), -1, dtype=np.int8)
    reason = np.full(len(t), '', dtype=object)
    if not np.isfinite(loss):
        loss_kind = 'nonfinite_loss_date'
        reason[:] = loss_kind
    elif loss == 0:
        loss_kind = 'zero_loss_date'
        reason[:] = loss_kind
    elif loss < 0:
        loss_kind = 'negative_loss_date'
        reason[:] = loss_kind
    else:
        loss_kind = 'finite_positive_loss_date'
        guard = abs(float(np.spacing(np.float32(loss)))) / 2
        before = t < loss - guard
        after = t >= loss + guard
        reproduced[before & (flag == 1)] = 1
        reproduced[after & (flag == 0)] = 0
        reason[(~np.isfinite(t))] = 'invalid_observation_time'
        unknown = reproduced == -1
        unassigned = unknown & (reason == '')
        reason[unassigned & ~np.isin(flag, [0, 1])] = 'unrecognized_source_flag'
        unassigned = unknown & (reason == '')
        reason[unassigned & ~(before | after)] = 'float32_loss_time_guard'
        reason[unknown & (reason == '')] = 'source_flag_loss_date_conflict'
    assert np.array_equal(regime, reproduced), ident
    assert np.array_equal(reason != '', regime == -1), ident

    counts = {name: int(np.count_nonzero(regime == value)) for value, name in states.items()}
    mask = 0
    for value, name in states.items():
        if counts[name]:
            id_sets[name].add(ident)
            mask |= {1: 1, 0: 2, -1: 4}[value]
        totals[name] += counts[name]
        by_split[split][name] += counts[name]
        nr = int(np.count_nonzero(in_r & (regime == value)))
        r_rows[name] += nr
        if nr:
            r_ids[name].add(ident)
    assert mask in mask_names
    groups[mask_names[mask]] += 1
    totals['rows'] += len(t)
    totals['nonanalytical_rows'] += int(np.count_nonzero(~analytical))
    by_split[split]['IDs'] += 1
    by_split[split]['rows'] += len(t)
    for value, count in zip(*np.unique(flag, return_counts=True)):
        raw_flags[str(int(value))] += int(count)
    this_reasons = {}
    for value, count in zip(*np.unique(reason[reason != ''], return_counts=True)):
        reason_rows[str(value)] += int(count)
        reason_ids[str(value)].add(ident)
        this_reasons[str(value)] = int(count)
    records.append({'id': ident, 'split': split, 'hourly_records': len(t), **counts,
                    'source_drogued_rows': int(np.count_nonzero(flag == 1)),
                    'source_undrogued_rows': int(np.count_nonzero(flag == 0)),
                    'state_pattern': mask_names[mask], 'loss_date_kind': loss_kind,
                    'unknown_reasons': json.dumps(this_reasons, sort_keys=True)})
    source_manifest.append({'file': str(path.relative_to(BASE)), 'rows': len(t),
                            'bytes': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns})
    if number % 750 == 0:
        print(json.dumps({'progress_IDs': number, 'rows_counted': totals['rows'],
                          'elapsed_seconds': round(time.monotonic() - started, 1)}), flush=True)

baseline = json.loads((BASE / 'audit/preparation_verification.json').read_text())
native_flags = np.asarray(raw['drogue_status'][:])
native_flag_counts = {str(int(value)): int(count) for value, count in zip(*np.unique(native_flags, return_counts=True))}
assert native_flag_counts == dict(raw_flags)
del native_flags
assert totals['rows'] == int(raw_sizes.sum()) == baseline['source_rows']
assert sum(totals[name] for name in states.values()) == totals['rows']
assert totals['unknown'] == baseline['counts']['unknown_regime_rows']
assert sum(reason_rows.values()) == totals['unknown']
assert sum(groups.values()) == len(raw_ids)
assert totals['nonanalytical_rows'] == 0
authority = BASE.parents[2] / 'outputs/01a09d9c-2168-7d51-8b63-87eb559bf139/data_contract_v1.0.xlsx'
authority_sha = hashlib.sha256(authority.read_bytes()).hexdigest()
assert authority_sha == '6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446'
report = {
    'executed_at_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'All acquired IDs and all retained hourly records, including all splits and full trajectories outside R/D.',
    'authority_sha256': authority_sha,
    'total_IDs': len(raw_ids), 'total_hourly_records': totals['rows'],
    'state_rows': {name: {'rows': totals[name], 'percent_of_all_rows': 100 * totals[name] / totals['rows'],
                        'distinct_IDs_with_any': len(id_sets[name])} for name in states.values()},
    'exclusive_ID_patterns': dict(groups),
    'source_drogue_status_value_counts': dict(raw_flags),
    'priority_whole_unknown_IDs_by_split': {split: sum(row['split'] == split and row['state_pattern'] == 'unknown_only' for row in records) for split in ('train', 'validation', 'test')},
    'priority_whole_unknown_hourly_records': sum(row['unknown'] for row in records if row['state_pattern'] == 'unknown_only'),
    'priority_raw_flags_by_loss_kind': {kind: {
        'IDs': sum(row['loss_date_kind'] == kind and row['state_pattern'] == 'unknown_only' for row in records),
        'raw_drogued_rows': sum(row['source_drogued_rows'] for row in records if row['loss_date_kind'] == kind and row['state_pattern'] == 'unknown_only'),
        'raw_undrogued_rows': sum(row['source_undrogued_rows'] for row in records if row['loss_date_kind'] == kind and row['state_pattern'] == 'unknown_only')}
        for kind in ('nonfinite_loss_date', 'zero_loss_date')},
    'unknown_reasons': {name: {'rows': reason_rows[name], 'distinct_IDs': len(reason_ids[name])}
                        for name in sorted(reason_rows)},
    'by_split': {name: dict(value) for name, value in sorted(by_split.items())},
    'R_observation_state_rows': {name: {'rows': r_rows[name], 'distinct_IDs': len(r_ids[name])}
                                for name in states.values()},
    'data_start_UTC': datetime.fromtimestamp(minimum, timezone.utc).isoformat(),
    'data_end_UTC': datetime.fromtimestamp(maximum, timezone.utc).isoformat(),
    'checks': {'native_ID_inventory_equal': True, 'native_per_ID_row_counts_equal': True,
               'native_source_flag_counts_equal': True,
               'all_row_regimes_independently_reconciled': True,
               'exclusive_ID_patterns_sum_to_total': True,
               'unknown_reason_rows_sum_to_unknown': True,
               'baseline_unknown_count_equal': True, 'contract_hash_unchanged': True,
               'nonanalytical_rows': totals['nonanalytical_rows']},
    'qualifications': [
        'ID counts with any state overlap; exclusive ID patterns do not overlap.',
        'A raw 0/1 source flag is not equivalent to a metadata-confirmed regime.',
        'Unknown includes unresolved metadata, source/date conflict and loss-time precision guards.',
        'Observation-state counts are not fixed-regime interval eligibility counts.',
        'No missing state was inferred and no original data or contract was modified.',
        'Locked-test records were counted only for this descriptive census; forecast ledgers and scores were not read.',
    ],
    'elapsed_seconds': round(time.monotonic() - started, 2),
}
with (OUT / 'per_ID_census.csv').open('w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(records[0]))
    writer.writeheader()
    writer.writerows(sorted(records, key=lambda row: row['id']))
with (OUT / 'priority_unknown_IDs.csv').open('w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(records[0]))
    writer.writeheader()
    writer.writerows(sorted((row for row in records if row['state_pattern'] == 'unknown_only'), key=lambda row: row['id']))
(OUT / 'result.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
(OUT / 'input_inventory.json').write_text(json.dumps(source_manifest, indent=2) + '\n')
print(json.dumps(report, indent=2, ensure_ascii=False))
