"""Resumable projection of only the approved registered columns, both pools."""
import copy
import csv
import json
import os
from pathlib import Path
import shutil

import pandas as pd
import pyarrow.parquet as pq

from data3001.feature_pruning import (
    AUDIT, ARCHIVE, LAYOUT, POLICY, PROTECTED, VERSION, prune_table)
from data3001.paths import file_sha256, project_paths
from data3001.recovery_storage import tables_equal

root = project_paths().root; audit = root/AUDIT; archive = root/ARCHIVE
scope = json.loads((audit/'scope.json').read_text())
parent_path = archive/'configs/dataset_manifest.json'
assert file_sha256(parent_path) == scope['parent_manifest_sha256']
parent = json.loads(parent_path.read_text())
assert parent['version'] == scope['parent_version'] == 'per-drifter-cleaned-20261017-v6'
assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx') == scope['contract_sha256']
removed = scope['removed_columns']; retained = scope['retained_columns']
assert len(removed) == 67 and len(retained) == 62
assert not set(removed) & set(PROTECTED)


def write_json(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    os.replace(temporary, path)


done = {}
journal = audit/'staging.jsonl'
if journal.exists():
    for line in journal.read_text().splitlines():
        item = json.loads(line); done[item['id']] = item

for n, (sid, record) in enumerate(parent['records'].items(), 1):
    current = root/record['path']; staged = audit/'staged'/record['path']
    backup = archive/('restricted_test' if record['pool'] == 'test'
                      else 'development')/f'{sid}.parquet'
    if sid in done:
        assert file_sha256(backup) == record['sha256'], sid
        assert file_sha256(staged if staged.exists() else current) == done[sid]['sha256'], sid
        continue
    assert not current.is_symlink() and file_sha256(current) == record['sha256'], sid
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists(): os.link(current, backup)
    assert not backup.is_symlink() and file_sha256(backup) == record['sha256'], sid
    old = pq.read_table(backup)
    assert len(old.schema) == 129 and len(old) == record['rows'], sid
    new = prune_table(old, removed)
    assert new.column_names == retained, sid
    staged.parent.mkdir(parents=True, exist_ok=True)
    temporary = staged.with_suffix('.tmp')
    pq.write_table(new, temporary, compression='zstd', compression_level=3)
    actual = pq.read_table(temporary)
    assert tables_equal(actual, new), sid
    # Independent projection: unchanged columns, dtypes, field metadata,
    # numerical values (including NaNs), null bitmap and row order.
    assert tables_equal(actual.replace_schema_metadata(None),
                        old.select(retained).replace_schema_metadata(None)), sid
    os.replace(temporary, staged)
    item = {'id': sid, 'path': record['path'], 'rows': record['rows'],
            'backup_path': str(backup.relative_to(root)),
            'parent_sha256': record['sha256'], 'sha256': file_sha256(staged)}
    with journal.open('a') as stream:
        stream.write(json.dumps(item)+'\n'); stream.flush(); os.fsync(stream.fileno())
    done[sid] = item
    if n % 250 == 0: print(f'Staged and compared {n}/{parent["IDs"]} IDs', flush=True)

assert set(done) == set(parent['records'])
rule = {'policy': POLICY, 'removed_columns': removed, 'retained_columns': retained,
        'preserved_drop_list_exceptions': list(PROTECTED), 'audit_directory': AUDIT,
        'archive_directory': ARCHIVE,
        'parent_manifest_path': str(parent_path.relative_to(root)),
        'parent_manifest_sha256': file_sha256(parent_path),
        'qualification_policy': 'Read exact archived annotations by source_obs/time; no rule changes'}
manifest = copy.deepcopy(parent); manifest['version'] = VERSION; manifest['fields'] = 62
manifest['cleaning']['feature_pruning'] = rule
for key in ('source_fields', 'prepared_fields'):
    manifest[key] = [name for name in manifest[key] if name in retained]
manifest['source_field_attributes'] = {k:v for k,v in manifest['source_field_attributes'].items()
                                       if k in retained}
manifest['scientific_status'] = ('Approved storage projection only; unchanged records, retained values, '
    'scientific qualification and ID splits; no new imputation, fitted model or accuracy claim')
for sid, item in done.items(): manifest['records'][sid]['sha256'] = item['sha256']
schema = json.loads((archive/'configs/dataset_schema.json').read_text())
schema['version'] = VERSION
schema['fields'] = [field for field in schema['fields'] if field['name'] in retained]
index = pd.read_csv(archive/'configs/dataset_index.csv')
index['sha256'] = index.id.astype(str).map(lambda sid: done[sid]['sha256'])
index.to_csv(audit/'next_dataset_index.csv', index=False)
write_json(audit/'next_dataset_manifest.json', manifest)
write_json(audit/'next_dataset_schema.json', schema)
assets = json.loads((archive/'configs/assets.json').read_text())
assets['layout_version'] = LAYOUT
assets['current_data_status'] = ('62 existing columns after approved 67-column removal; '
    'err_lat/err_lon/err_ve/err_vn retained; all records and remaining values unchanged; '
    'qualification evidence archived outside active train/test')
for key in ('current_train_tracks', 'current_test_tracks'):
    assets['assets'][key]['version'] = VERSION
    assets['assets'][key]['role'] = assets['current_data_status']
for key, name in [('current_dataset_manifest', 'dataset_manifest.json'),
                  ('current_dataset_schema', 'dataset_schema.json'),
                  ('current_dataset_index', 'dataset_index.csv')]:
    assets['assets'][key]['sha256'] = file_sha256(audit/('next_'+name))
write_json(audit/'next_assets.json', assets)

with (archive/'configs/feature_review.csv').open(newline='') as stream:
    reader = csv.DictReader(stream); fieldnames = reader.fieldnames; review = list(reader)
for row in review:
    row['dataset_release'] = VERSION
    if row['feature'] in removed:
        row['source_data_action'] = 'removed_from_active_retained_in_archive'
        row['decision_or_review_note'] += (' USER-APPROVED STORAGE UPDATE: physically removed from '
            'both active pools; exact parent and prior audit evidence retained in '+ARCHIVE+'.')
    elif row['feature'] in PROTECTED:
        row['review_status'] = 'agreed'
        row['model_input_action'] = 'retain_uncertainty_evidence'
        row['source_data_action'] = 'retain_unchanged'
        row['decision_or_review_note'] += (' USER-APPROVED REVISION: retain this original numeric '
            'uncertainty field unchanged. Its predictive-input/uncertainty use requires a stated '
            'model-stage purpose; previous core-input exclusion is superseded by this retention decision.')
with (audit/'next_feature_review.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=fieldnames); writer.writeheader(); writer.writerows(review)

receipt = {'policy': POLICY, 'parent_manifest_path': rule['parent_manifest_path'],
           'parent_manifest_sha256': rule['parent_manifest_sha256'],
           'files': done, 'removed_columns': removed, 'retained_columns': retained,
           'new_feature_columns': [], 'rows_removed': 0, 'values_changed': 0,
           'whole_ID_assignments_changed': 0}
write_json(audit/'receipt.json', receipt)
print('All 3741 projected files passed staging checks; activating.', flush=True)
for n, (sid, item) in enumerate(done.items(), 1):
    staged = audit/'staged'/item['path']; current = root/item['path']
    if staged.exists():
        assert file_sha256(staged) == item['sha256'], sid
        assert file_sha256(current) in (item['parent_sha256'], item['sha256']), sid
        os.replace(staged, current)
        with (audit/'activation.jsonl').open('a') as stream:
            stream.write(json.dumps({'id': sid, 'sha256': item['sha256']})+'\n')
            stream.flush(); os.fsync(stream.fileno())
    else: assert file_sha256(current) == item['sha256'], sid
    if n % 500 == 0: print(f'Activated {n}/{len(done)} IDs', flush=True)
for name in ('dataset_manifest.json', 'dataset_index.csv', 'dataset_schema.json',
             'feature_review.csv', 'assets.json'):
    temporary = root/'configs'/('.'+name+'.tmp')
    shutil.copy2(audit/('next_'+name), temporary); os.replace(temporary, root/'configs'/name)
print(json.dumps({'release': VERSION, 'IDs': manifest['IDs'], 'rows': manifest['rows'],
                  'removed_columns': len(removed), 'remaining_columns': manifest['fields']}), flush=True)
