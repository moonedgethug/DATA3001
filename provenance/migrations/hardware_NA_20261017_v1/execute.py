"""Scoped, resumable in-place normalization of seven hardware columns."""
import copy
import json
import os
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from data3001.hardware_missing import FIELDS, POLICY, VERSION, normalize_hardware_missing
from data3001.paths import file_sha256, project_paths
from data3001.recovery_storage import tables_equal

root = project_paths().root
audit = root/'provenance/migrations/hardware_NA_20261017_v1'
archive = root/'archive/hardware_NA_20261017_v1'
parent_path = archive/'configs/dataset_manifest.json'
parent = json.loads(parent_path.read_text())
assert parent['version'] == 'per-drifter-cleaned-20261017-v5'
assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx') == parent['contract_sha256']


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    os.replace(temporary, path)


journal = audit/'staging.jsonl'
done = {}
if journal.exists():
    for line in journal.read_text().splitlines():
        item = json.loads(line); done[item['id']] = item

for n, (sid, record) in enumerate(parent['records'].items(), 1):
    current = root/record['path']; staged = audit/'staged'/record['path']
    if sid in done:
        assert file_sha256(staged if staged.exists() else current) == done[sid]['sha256'], sid
        continue
    assert file_sha256(current) == record['sha256'], sid
    values = pq.read_table(current, columns=list(FIELDS))
    normalized = normalize_hardware_missing(values)
    delta = {name: normalized[name].null_count-values[name].null_count for name in FIELDS}
    total = sum(delta.values())
    item = {'id': sid, 'path': record['path'], 'rows': record['rows'],
            'sha256': record['sha256'], 'new_numeric_NA_cells': total,
            'new_numeric_NA_by_field': delta}
    if total:
        backup = archive/record['path']; backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            os.link(current, backup)
        assert file_sha256(backup) == record['sha256'], sid
        old = pq.read_table(backup); new = normalize_hardware_missing(old)
        assert new.schema.equals(old.schema, check_metadata=True), sid
        assert tables_equal(new.drop(FIELDS), old.drop(FIELDS)), sid
        for name in FIELDS:
            arr = old[name].to_numpy()
            # Preflight found NaN only: retain this strict cohort-specific gate.
            assert not np.isinf(arr).any() and not (arr[np.isfinite(arr)] < 0).any(), (sid, name)
            assert np.array_equal(new[name].is_null().to_numpy(), np.isnan(arr)), (sid, name)
        staged.parent.mkdir(parents=True, exist_ok=True)
        temporary = staged.with_suffix('.tmp')
        pq.write_table(new, temporary, compression='zstd', compression_level=3)
        assert tables_equal(new, pq.read_table(temporary)), sid
        os.replace(temporary, staged)
        item.update(backup_path=str(backup.relative_to(root)), sha256=file_sha256(staged))
    with journal.open('a') as stream:
        stream.write(json.dumps(item)+'\n'); stream.flush(); os.fsync(stream.fileno())
    done[sid] = item
    if n % 500 == 0:
        print(f'Inspected/staged {n}/{parent["IDs"]} files', flush=True)

assert len(done) == parent['IDs']
changed = {sid: item for sid, item in done.items() if item['new_numeric_NA_cells']}
assert len(changed) == 210
receipt = {'policy': POLICY, 'fields': list(FIELDS),
           'parent_manifest_path': str(parent_path.relative_to(root)),
           'parent_manifest_sha256': file_sha256(parent_path),
           'parent_schema_path': str((archive/'configs/dataset_schema.json').relative_to(root)),
           'parent_schema_sha256': file_sha256(archive/'configs/dataset_schema.json'),
           'changed_files': changed,
           'new_numeric_NA_cells': sum(item['new_numeric_NA_cells'] for item in changed.values()),
           'existing_zero_codes_preserved': True, 'new_feature_columns': []}
write_json(audit/'receipt.json', receipt)

manifest = copy.deepcopy(parent); manifest['version'] = VERSION
manifest['cleaning']['hardware_missing'] = {'policy': POLICY, 'fields': list(FIELDS),
    'audit_directory': str(audit.relative_to(root)),
    'representation': 'Arrow numeric null; not the literal string NA',
    'zero_policy': 'Preserve all recorded zeros; semantics not reinterpreted',
    'imputation': 'None; no physical specification inferred',
    'observed_changes': 'NaN-to-null only; no infinity, negative or finite missing code found'}
for sid, item in changed.items():
    manifest['records'][sid]['sha256'] = item['sha256']
schema = json.loads((archive/'configs/dataset_schema.json').read_text()); schema['version'] = VERSION
index = pd.read_csv(archive/'configs/dataset_index.csv')
index['sha256'] = index.id.astype(str).map(lambda sid: done[sid]['sha256'])
index.to_csv(audit/'next_dataset_index.csv', index=False)
write_json(audit/'next_dataset_manifest.json', manifest)
write_json(audit/'next_dataset_schema.json', schema)
assets = json.loads((archive/'configs/assets.json').read_text())
assets['layout_version'] = 'per-drifter-cleaned-1.4'
assets['current_data_status'] = ('129 columns; seven hardware fields use numeric null for missing values; '
    'all finite hardware values and zeros preserved; original-column SST and drogue status unchanged')
for key in ('current_train_tracks', 'current_test_tracks'):
    assets['assets'][key]['version'] = VERSION
    assets['assets'][key]['role'] = assets['current_data_status']
for key, name in [('current_dataset_manifest', 'dataset_manifest.json'),
                  ('current_dataset_schema', 'dataset_schema.json'),
                  ('current_dataset_index', 'dataset_index.csv')]:
    assets['assets'][key]['sha256'] = file_sha256(audit/('next_'+name))
write_json(audit/'next_assets.json', assets)

for n, (sid, item) in enumerate(changed.items(), 1):
    source = audit/'staged'/item['path']; destination = root/item['path']
    if source.exists():
        assert file_sha256(source) == item['sha256']
        assert file_sha256(destination) in [parent['records'][sid]['sha256'], item['sha256']]
        os.replace(source, destination)
        with (audit/'activation.jsonl').open('a') as stream:
            stream.write(json.dumps({'id': sid, 'sha256': item['sha256']})+'\n')
            stream.flush(); os.fsync(stream.fileno())
    else:
        assert file_sha256(destination) == item['sha256']
    if n % 50 == 0:
        print(f'Activated {n}/{len(changed)} affected files', flush=True)
for name in ('dataset_manifest.json', 'dataset_index.csv', 'dataset_schema.json', 'assets.json'):
    temporary = root/'configs'/('.'+name+'.tmp')
    shutil.copy2(audit/('next_'+name), temporary); os.replace(temporary, root/'configs'/name)
print(json.dumps({'release': VERSION, 'changed_ID_files': len(changed),
                  'normalized_NaN_cells': receipt['new_numeric_NA_cells'],
                  'rows': manifest['rows'], 'fields': manifest['fields']}), flush=True)
