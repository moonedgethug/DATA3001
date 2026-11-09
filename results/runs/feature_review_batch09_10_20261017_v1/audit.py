"""Read-only ID-level audit of existing groups 09 and 10; no data writes."""
from collections import Counter, defaultdict
from pathlib import Path
import csv
import hashlib
import json
import math

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def serial(value):
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='strict')
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main():
    registry = list(csv.DictReader((ROOT/'configs/feature_review.csv').open()))
    selected = [r for r in registry if r['review_batch'].startswith(('09_', '10_'))]
    fields = [r['feature'] for r in selected]
    groups = {r['feature']: r['review_batch'] for r in selected}
    manifest = json.loads((ROOT/'configs/dataset_manifest.json').read_text())
    baseline = {}
    records = []
    total_rows = 0
    for number, (sid, rec) in enumerate(manifest['records'].items(), 1):
        path = ROOT/rec['path']
        stat = path.stat()
        baseline[rec['path']] = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
        file = pq.ParquetFile(path)
        assert file.metadata.num_rows == rec['rows']
        assert file.metadata.num_columns == manifest['fields']
        total_rows += rec['rows']
        lookup = {file.metadata.row_group(0).column(i).path_in_schema: i
                  for i in range(file.metadata.num_columns)}
        row = {'id': sid, 'pool': rec['pool'], 'rows': rec['rows']}
        for field in fields:
            values = set()
            nulls = 0
            for rg in range(file.metadata.num_row_groups):
                group = file.metadata.row_group(rg)
                stats = group.column(lookup[field]).statistics
                assert stats is not None, (sid, field)
                nulls += stats.null_count
                if stats.has_min_max:
                    assert stats.min == stats.max, (sid, field, 'not constant')
                    values.add(serial(stats.min))
                else:
                    assert stats.null_count == group.num_rows
            assert len(values) <= 1, (sid, field, 'ID-level variation')
            assert nulls in (0, rec['rows']), (sid, field, 'partial null')
            row[field] = next(iter(values), None)
        row['visits_R'] = any(
            file.metadata.row_group(rg).column(lookup['in_R']).statistics.max
            for rg in range(file.metadata.num_row_groups))
        for field in fields:
            if field.endswith('_text'):
                assert row[field] == row[field[:-5]], (sid, field, 'decode mismatch')
        records.append(row)
        if number % 1000 == 0:
            print('Metadata inspected', number, flush=True)
    assert total_rows == manifest['rows']
    populations = {
        'all_IDs': records,
        'development_IDs': [r for r in records if r['pool'] == 'train'],
        'development_R_visiting_IDs': [r for r in records if r['pool'] == 'train' and r['visits_R']],
    }
    profile = {}
    for field in fields:
        profile[field] = {'group': groups[field], 'populations': {}}
        for name, population in populations.items():
            counts = Counter(r[field] for r in population)
            def text_missing(value):
                return isinstance(value, str) and value.strip().casefold() in ('', 'unknown', 'na', 'n/a', 'none', '?')
            profile[field]['populations'][name] = {
                'IDs': len(population), 'numeric_or_storage_null_IDs': counts.get(None, 0),
                'literal_unknown_or_blank_text_IDs': sum(n for v, n in counts.items() if text_missing(v)),
                'minus_one_code_IDs': counts.get(-1, 0),
                'distinct_nonnull_values': len(counts) - int(None in counts),
                'values': [{'value': v, 'IDs': n} for v, n in counts.most_common()],
            }
    assert all(r['BuoyTypeSensorArray'] == r['ManufactureSensorType'] for r in records)
    source_path = ROOT/'provenance/runs/hardware_source_recovery_20261017_v1/sources/drifter_specifications_csv_retry.txt'
    official = defaultdict(list)
    for record in csv.DictReader(source_path.open()):
        official[record['DirFL ID'].strip()].append(record)
    year_counts = Counter()
    for row in populations['development_IDs']:
        candidates = official.get(row['id'], [])
        if len(candidates) != 1 or not candidates[0]['Manufacture Year'].strip():
            continue
        year_counts['exact_ID_with_official_manufacture_year'] += 1
        if str(row['DeploymentComments']) == candidates[0]['Manufacture Year'].strip():
            year_counts['native_comments_equals_official_manufacture_year'] += 1
    unchanged = all((ROOT/p).stat().st_size == state['size'] and
                    (ROOT/p).stat().st_mtime_ns == state['mtime_ns']
                    for p, state in baseline.items())
    assert unchanged
    result = {
        'release': manifest['version'], 'IDs': len(records), 'rows': total_rows,
        'columns': manifest['fields'],
        'population_ID_counts': {k: len(v) for k, v in populations.items()},
        'metadata_constant_within_each_ID': True,
        'binary_text_decodes_exact': True,
        'sensor_array_and_manufacture_sensor_type_identical': True,
        'all_data_sizes_and_modification_times_unchanged': unchanged,
        'contract_sha256': digest(ROOT/'docs/contract/data_contract_v1.0.xlsx'),
        'dataset_manifest_sha256': digest(ROOT/'configs/dataset_manifest.json'),
        'dataset_schema_sha256': digest(ROOT/'configs/dataset_schema.json'),
        'prediction_labels_read': False, 'predictive_performance_tested': False,
        'deployment_comments_semantic_check': {
            'population': 'development_IDs', 'counts': dict(year_counts),
            'source': str(source_path.relative_to(ROOT)), 'source_sha256': digest(source_path),
            'decision': 'Do not rename, recode or impute this field until the upstream meaning is formally resolved.'},
        'classification_note': 'Text marker counts describe recorded literals only; no source value is recoded. Minus-one codes are reported separately from storage nulls.',
        'fields': profile,
    }
    (OUT/'profile.json').write_text(json.dumps(result, indent=2)+'\n')
    with (OUT/'per_ID_metadata.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['id', 'pool', 'rows', 'visits_R']+fields)
        writer.writeheader()
        writer.writerows(records)
    (OUT/'data_file_stats_before.json').write_text(json.dumps(baseline, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'fields'}, indent=2))
    for field in fields:
        if not field.endswith('_text') and groups[field].startswith('10_'):
            print(field, json.dumps(profile[field]['populations']['development_IDs']))


if __name__ == '__main__':
    main()
