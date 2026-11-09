"""Read-only lifecycle metadata and existing cleanup-boundary inspection."""
from collections import Counter
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
import csv
import hashlib
import json
import math
import re

import numpy as np
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
FIELDS = ('deploy_date', 'deploy_lat', 'deploy_lon', 'start_date', 'start_lat',
          'start_lon', 'end_date', 'end_lat', 'end_lon', 'typedeath')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value):
    return value is not None and math.isfinite(value)


def check_deployment_candidates(manifest, lifecycle_records):
    path = RUN/'deployment_source_candidates.json'
    if not path.exists():
        return None
    candidates = json.loads(path.read_text())
    source = RUN/'sources/deployment_log.html'
    receipt = json.loads((RUN/'sources/deployment_log.receipt.json').read_text())
    assert sha(source) == receipt['sha256']
    assert source.stat().st_size == receipt['bytes']
    missing = {row['id'] for row in lifecycle_records if row['deploy_date'] is None}
    assert set(candidates['raw_matches']) == missing
    found = {sid: [] for sid in missing}
    text = unescape(re.sub('<[^>]+>', '', source.read_text()))
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[0] in missing:
            found[parts[0]].append(line.strip())
    assert found == candidates['raw_matches']
    lookup = {row['id']: row for row in lifecycle_records}
    chronology = {row['id']: row for row in candidates['chronology_comparison']}
    totals = Counter()
    for sid, lines in found.items():
        if len(lines) != 1:
            continue
        parts = lines[0].split()
        date = datetime(*map(int, parts[2:5]), tzinfo=timezone.utc)
        life = lookup[sid]
        delta_qc = (date.timestamp()-life['start_date'])/86400
        delta_hour = (date.timestamp()-life['first_retained_hour'])/86400
        recorded = chronology[sid]
        assert recorded['days_after_QC_start'] == delta_qc
        assert recorded['days_after_first_retained_hour'] == delta_hour
        native = next(pq.ParquetFile(ROOT/manifest['records'][sid]['path']).iter_batches(
            batch_size=1, columns=list(recorded['native_identity']))).to_pylist()[0]
        assert native == recorded['native_identity']
        assert recorded['experiment_agreement'] == (native['expno'] == int(parts[-1]))
        assert recorded['positive_WMO_agreement'] == (native['WMO'] > 0 and native['WMO'] == int(parts[1]))
        lat = (float(parts[5])+float(parts[6][:-1])/60)*(-1 if parts[6][-1] == 'S' else 1)
        lon = (float(parts[7])+float(parts[8][:-1])/60)*(-1 if parts[8][-1] == 'W' else 1)
        assert lat == recorded['official_deploy_lat'] and lon == recorded['official_deploy_lon']
        consistent = abs(lat-native['deploy_lat']) <= 0.00135 and abs(lon-native['deploy_lon']) <= 0.00135
        assert consistent == recorded['coordinate_rounding_consistent']
        totals['exact_ID_log_candidates'] += 1
        totals['dates_after_first_QC_date'] += delta_qc > 0
        totals['dates_after_first_retained_hour'] += delta_hour > 0
        totals['matching_experiment_numbers'] += recorded['experiment_agreement']
        totals['matching_positive_WMO_numbers'] += recorded['positive_WMO_agreement']
        totals['coordinate_rounding_consistent'] += consistent
    assert len(missing) == 44 and totals['exact_ID_log_candidates'] == 30
    assert totals['dates_after_first_QC_date'] == 30 and totals['dates_after_first_retained_hour'] == 26
    assert candidates['accepted_data_changes'] == 0
    return {'scope_IDs': len(missing), **dict(totals),
            'no_exact_ID_log_match': sum(not v for v in found.values()),
            'source_receipt_and_current_native_metadata_reverified': True,
            'calendar_dates_are_not_precise_event_hours': True,
            'accepted_data_changes': 0}


def main():
    manifest = json.loads((ROOT/'configs/dataset_manifest.json').read_text())
    receipts = {p: sha(ROOT/p) for p in ['configs/dataset_manifest.json',
        'configs/dataset_schema.json', 'docs/contract/data_contract_v1.0.xlsx']}
    assert receipts['docs/contract/data_contract_v1.0.xlsx'] == manifest['contract_sha256']
    records = []
    baseline = {}
    for number, (sid, entry) in enumerate(manifest['records'].items(), 1):
        path = ROOT/entry['path']
        st = path.stat()
        baseline[entry['path']] = {'size': st.st_size, 'mtime_ns': st.st_mtime_ns}
        file = pq.ParquetFile(path)
        assert file.metadata.num_rows == entry['rows']
        assert file.metadata.num_columns == manifest['fields']
        table = file.read(columns=list(FIELDS)+['time', 'in_R', 'sst'])
        record = {'id': sid, 'pool': entry['pool'], 'rows': entry['rows']}
        for field in FIELDS:
            values = pc.unique(table[field]).to_pylist()
            assert len(values) == 1, (sid, field, 'not constant within ID')
            value = values[0]
            record[field] = value if finite(value) else None
        time = table['time'].to_numpy()
        in_r = table['in_R'].to_numpy()
        record['R_rows'] = int(in_r.sum())
        record['visits_R'] = bool(record['R_rows'])
        record['first_retained_hour'] = float(time.min())
        record['last_retained_hour'] = float(time.max())
        end = record['end_date']
        cutoff_valid = finite(end) and end > 0
        after = time > end if cutoff_valid else np.zeros(len(time), dtype=bool)
        record['hours_after_last_good_date'] = int(after.sum())
        record['R_hours_after_last_good_date'] = int((after & in_r).sum())
        record['sst_available_after_grounding_related_bound'] = 0
        if record['typedeath'] == 1 and cutoff_valid:
            record['sst_available_after_grounding_related_bound'] = int(
                (after & np.isfinite(table['sst'].to_numpy())).sum())
            assert record['sst_available_after_grounding_related_bound'] == 0, sid
        if record['typedeath'] == 2 and cutoff_valid:
            assert record['hours_after_last_good_date'] == 0, sid
        for prefix in ('deploy', 'start', 'end'):
            vals = [record[prefix+'_'+suffix] for suffix in ('date', 'lat', 'lon')]
            record[prefix+'_partial_triplet'] = any(v is None for v in vals) and any(v is not None for v in vals)
        records.append(record)
        if number % 500 == 0:
            print('Lifecycle records inspected', number, flush=True)
    assert len(records) == manifest['IDs']
    assert sum(r['rows'] for r in records) == manifest['rows']
    populations = {'all_IDs': records,
        'development_IDs': [r for r in records if r['pool'] == 'train'],
        'development_R_visiting_IDs': [r for r in records if r['pool'] == 'train' and r['visits_R']]}
    profiles = {}
    for field in FIELDS:
        profiles[field] = {}
        for name, population in populations.items():
            valid = [r[field] for r in population if r[field] is not None]
            missing = [r['id'] for r in population if r[field] is None]
            if field.endswith('_date'):
                invalid = [r['id'] for r in population if r[field] is not None and r[field] <= 0]
            elif field.endswith('_lat'):
                invalid = [r['id'] for r in population if r[field] is not None and not -90 <= r[field] <= 90]
            elif field.endswith('_lon'):
                invalid = [r['id'] for r in population if r[field] is not None and not -180 <= r[field] <= 180]
            else:
                invalid = [r['id'] for r in population if r[field] not in range(7)]
            result = {'IDs': len(population), 'missing_IDs': len(missing),
                'missing_ID_list': missing, 'invalid_IDs': len(invalid),
                'invalid_ID_list': invalid,
                'min': min(valid) if valid else None, 'max': max(valid) if valid else None}
            if field.endswith('_date') and valid:
                result['min_UTC'] = datetime.fromtimestamp(min(valid), timezone.utc).isoformat()
                result['max_UTC'] = datetime.fromtimestamp(max(valid), timezone.utc).isoformat()
            if field == 'typedeath':
                result['value_counts'] = dict(Counter(r[field] for r in population))
            profiles[field][name] = result
    cross_checks = {}
    global_last_retained_hour = max(r['last_retained_hour'] for r in records)
    for name, population in populations.items():
        missing_end = [r for r in population if r['end_date'] is None]
        cross_checks[name] = {
            'missing_end_typedeath_counts': dict(Counter(r['typedeath'] for r in missing_end)),
            'partial_triplet_IDs': {p: [r['id'] for r in population if r[p+'_partial_triplet']] for p in ('deploy','start','end')},
            'start_after_finite_end_IDs': [r['id'] for r in population if finite(r['end_date']) and finite(r['start_date']) and r['start_date'] > r['end_date']],
            'deploy_after_first_QC_IDs': [r['id'] for r in population if finite(r['deploy_date']) and finite(r['start_date']) and r['deploy_date'] > r['start_date']],
            'first_hour_differs_from_QC_start_IDs': sum(r['first_retained_hour'] != r['start_date'] for r in population),
            'grounding_related_bound_tail_hours': sum(r['hours_after_last_good_date'] for r in population if r['typedeath'] == 1),
            'grounding_related_bound_tail_R_hours': sum(r['R_hours_after_last_good_date'] for r in population if r['typedeath'] == 1),
            'recovery_tail_hours_remaining': sum(r['hours_after_last_good_date'] for r in population if r['typedeath'] == 2),
            'finite_sst_after_grounding_related_bound': sum(r['sst_available_after_grounding_related_bound'] for r in population),
            'finite_end_after_global_observed_cutoff_IDs': [r['id'] for r in population if finite(r['end_date']) and r['end_date'] > global_last_retained_hour],
        }
    for path, state in baseline.items():
        current = (ROOT/path).stat()
        assert current.st_size == state['size'] and current.st_mtime_ns == state['mtime_ns']
    for path, digest in receipts.items():
        assert sha(ROOT/path) == digest
    result = {'release': manifest['version'], 'IDs': manifest['IDs'],
        'rows': manifest['rows'], 'columns': manifest['fields'],
        'population_ID_counts': {k: len(v) for k,v in populations.items()},
        'global_last_retained_hour_UTC': datetime.fromtimestamp(global_last_retained_hour, timezone.utc).isoformat(),
        'source_hashes': receipts, 'data_sizes_and_mtimes_unchanged': True,
        'all_ten_fields_constant_within_ID': True,
        'model_predictions_or_horizon_labels_read': False,
        'metadata_on_final_test_read_for_preprocessing_audit_only': True,
        'predictive_accuracy_evaluated': False, 'fields': profiles,
        'cross_checks': cross_checks,
        'deployment_source_checks': check_deployment_candidates(manifest, records),
        'interpretation': 'End metadata describes the last-good observation and eventual fate, not the first exact physical grounding/recovery time or a fixed-horizon endpoint. No values were imputed or changed.'}
    (RUN/'profile.json').write_text(json.dumps(result, indent=2)+'\n')
    (RUN/'data_file_stats_before.json').write_text(json.dumps(baseline, indent=2)+'\n')
    with (RUN/'per_ID_metadata.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader(); writer.writerows(records)
    print(json.dumps({k:v for k,v in result.items() if k not in ('fields','cross_checks')},indent=2))
    for field, data in profiles.items():
        print(field, 'development missing:', data['development_IDs']['missing_IDs'],
              'R missing:',data['development_R_visiting_IDs']['missing_IDs'])
    print('development cross checks', json.dumps(cross_checks['development_IDs']))


if __name__ == '__main__':
    main()
