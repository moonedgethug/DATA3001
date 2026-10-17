"""Exact portable projections of existing audit fields; active data are untouched."""
import json
import os
from pathlib import Path

import pyarrow.parquet as pq

from data3001.paths import file_sha256
from data3001.recovery_storage import tables_equal

root = Path(__file__).resolve().parents[3]
run = root/'provenance/runs/data_publish_20261018_v1'
current = json.loads((root/'configs/dataset_manifest.json').read_text())
rule = current['cleaning']['feature_pruning']
parent_path = root/rule['parent_manifest_path']
assert file_sha256(parent_path) == rule['parent_manifest_sha256']
parent = json.loads(parent_path.read_text())
assert set(parent['records']) == set(current['records'])
fields = ['id', 'source_obs', 'time', 'analytical_row', 'position_ok',
          'mapping_ok', 'in_R', 'visit_cell_1']
keys = ['id', 'source_obs', 'time']; records = {}; rows = 0

for n, (sid, record) in enumerate(current['records'].items(), 1):
    partition = 'restricted_test' if record['pool'] == 'test' else 'development'
    before = root/rule['archive_directory']/partition/f'{sid}.parquet'
    assert file_sha256(before) == parent['records'][sid]['sha256'], sid
    actual = root/record['path']; assert file_sha256(actual) == record['sha256'], sid
    selected = pq.read_table(before, columns=fields).replace_schema_metadata(None)
    active_keys = pq.read_table(actual, columns=keys).replace_schema_metadata(None)
    assert tables_equal(selected.select(keys), active_keys), sid
    relative = f'provenance/qualification/v7/{partition}/{sid}.parquet'
    destination = root/relative; destination.parent.mkdir(parents=True, exist_ok=True)
    selected = selected.replace_schema_metadata({b'qualification_provenance': json.dumps({
        'id': sid, 'pool': record['pool'], 'source_parent_sha256': parent['records'][sid]['sha256'],
        'dataset_manifest_sha256': file_sha256(root/'configs/dataset_manifest.json'),
        'method': 'Exact projection of existing audited annotations; no recalculation'}).encode()})
    if destination.exists():
        assert tables_equal(selected, pq.read_table(destination)), sid
    else:
        temporary = destination.with_suffix('.tmp')
        pq.write_table(selected, temporary, compression='zstd', compression_level=3)
        assert tables_equal(selected, pq.read_table(temporary)), sid
        os.replace(temporary, destination)
    records[sid] = {'path': relative, 'pool': record['pool'], 'rows': record['rows'],
                    'sha256': file_sha256(destination),
                    'parent_sha256': parent['records'][sid]['sha256']}
    rows += record['rows']
    if n % 500 == 0: print(f'Exported and exactly verified {n}/{current["IDs"]} qualification files', flush=True)

assert rows == current['rows'] and len(records) == current['IDs']
manifest = {'version': 'exact-pre-projection-qualification-v1', 'dataset_version': current['version'],
            'dataset_manifest_sha256': file_sha256(root/'configs/dataset_manifest.json'),
            'parent_manifest_sha256': file_sha256(parent_path), 'fields': fields,
            'IDs': len(records), 'rows': rows, 'records': records}
target = root/'configs/qualification_manifest.json'
target.write_text(json.dumps(manifest, indent=2)+'\n')
assets_path = root/'configs/assets.json'; assets = json.loads(assets_path.read_text())
assets['assets']['current_qualification_manifest'] = {
    'path': 'configs/qualification_manifest.json', 'kind': 'file', 'split': 'all',
    'sha256': file_sha256(target), 'version': manifest['version'],
    'role': 'Exact source-keyed qualification projections; not predictive features'}
assets_path.write_text(json.dumps(assets, indent=2)+'\n')
receipt = {'passed': True, 'IDs': len(records), 'rows': rows, 'qualification_columns': fields,
           'dataset_version': current['version'], 'active_data_columns': 62,
           'all_exported_values_types_nulls_and_keys_exactly_equal_parent': True,
           'all_keys_exactly_equal_active_tracks': True, 'active_data_values_modified': False,
           'new_active_feature_columns': [], 'qualification_manifest_sha256': file_sha256(target),
           'bytes': sum((root/r['path']).stat().st_size for r in records.values())}
(root/'provenance/qualification/v7/export_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt), flush=True)
