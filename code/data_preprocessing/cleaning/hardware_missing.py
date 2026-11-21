"""Normalize missing hardware values in existing columns; never infer a design."""
import json
from collections import Counter

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from data3001.paths import project_paths, file_sha256

VERSION = 'per-drifter-cleaned-20261017-v6'
POLICY = 'seven_hardware_fields_missing_invalid_to_null_preserve_zero'
FIELDS = ('DragAreaAboveDrogue', 'DragAreaOfDrogue', 'DragAreaRatio',
          'DrogueBallast', 'DrogueCenterDepth', 'DrogueLength', 'FloatDiameter')


def normalize_hardware_missing(table):
    """Typed NA for null/NaN/inf/negative/declared fill; keep zeros and positives.

    No empirical upper cutoff is defensible for mixed instrument designs.
    Source attributes, column names/types/order and all other fields stay exact.
    """
    out = table
    for name in FIELDS:
        field = table.schema.field(name)
        if not pa.types.is_floating(field.type):
            raise ValueError(f'Expected an existing numeric hardware column: {name}')
        values = table[name]
        invalid = pc.or_(pc.invert(pc.is_finite(values)), pc.less(values, 0))
        attrs = json.loads((field.metadata or {}).get(b'source_attributes', b'{}'))
        for key in ('_FillValue', 'missing_value'):
            codes = attrs.get(key, [])
            if not isinstance(codes, list):
                codes = [codes]
            for code in codes:
                try:
                    finite = np.isfinite(float(code))
                except (ValueError, TypeError):
                    continue
                if finite and float(code) != 0:
                    invalid = pc.or_(invalid, pc.equal(values, pa.scalar(code, type=field.type)))
        if pc.any(pc.fill_null(invalid, False)).as_py():
            cleaned = pc.if_else(invalid, pa.scalar(None, type=field.type), values)
            out = out.set_column(out.schema.get_field_index(name), field, cleaned)
    return out


def verify_hardware_release(progress=None):
    """Check every file; compare affected files with exact archived parents."""
    from data3001.dataset import manifest
    from data3001.recovery_storage import tables_equal
    paths = project_paths(); root = paths.root; current = manifest()
    rule = current['cleaning']['hardware_missing']
    assert current['version'] == VERSION and rule['policy'] == POLICY
    assert rule['fields'] == list(FIELDS)
    directory = root/rule['audit_directory']
    receipt = json.loads((directory/'receipt.json').read_text())
    parent_path = root/receipt['parent_manifest_path']
    assert file_sha256(parent_path) == receipt['parent_manifest_sha256']
    parent = json.loads(parent_path.read_text())
    assert parent['version'] == 'per-drifter-cleaned-20261017-v5'
    assert set(current['records']) == set(parent['records'])
    changed = receipt['changed_files']; rows = changed_cells = 0
    nulls = Counter(); missing_ids = Counter(); zeros = Counter()
    index = pd.read_csv(paths.asset('current_dataset_index', verify=True)).set_index('id')
    for n, (sid, record) in enumerate(current['records'].items(), 1):
        before = parent['records'][sid]
        assert {k: v for k, v in record.items() if k != 'sha256'} == {
            k: v for k, v in before.items() if k != 'sha256'}, sid
        path = root/record['path']; assert file_sha256(path) == record['sha256'], sid
        schema = pq.read_schema(path)
        assert len(schema) == 129 and 'regime' not in schema.names and 'sst_use_K' not in schema.names
        values = pq.read_table(path, columns=list(FIELDS))
        assert len(values) == record['rows']
        for name in FIELDS:
            arr = values[name].to_numpy(); finite = arr[np.isfinite(arr)]
            assert not np.isinf(arr).any() and not (finite < 0).any(), (sid, name)
            assert int(np.isnan(arr).sum()) == values[name].null_count, (sid, name)
            nulls[name] += values[name].null_count
            missing_ids[name] += int(values[name].null_count > 0)
            zeros[name] += int((arr == 0).sum())
        if sid in changed:
            item = changed[sid]; backup = root/item['backup_path']
            assert file_sha256(backup) == before['sha256'], sid
            old = pq.read_table(backup); actual = pq.read_table(path)
            assert actual.schema.equals(old.schema, check_metadata=True), sid
            assert tables_equal(actual.drop(FIELDS), old.drop(FIELDS)), sid
            assert tables_equal(actual, normalize_hardware_missing(old)), sid
            # Independent checks: every finite hardware value, null location,
            # zero code and row position must be preserved except invalids.
            for name in FIELDS:
                a = old[name].to_numpy(); b = actual[name].to_numpy()
                good = np.isfinite(a) & (a >= 0)
                assert np.array_equal(a[good], b[good]), (sid, name)
                assert np.array_equal(actual[name].is_null().to_numpy(), np.isnan(a)), (sid, name)
            delta = sum(actual[f].null_count-old[f].null_count for f in FIELDS)
            assert delta == item['new_numeric_NA_cells']; changed_cells += delta
        else:
            assert record['sha256'] == before['sha256'], sid
        entry = index.loc[int(sid)]
        assert (int(entry['rows']), entry['path'], entry['sha256']) == (
            record['rows'], record['path'], record['sha256'])
        rows += len(values)
        if progress and n % 500 == 0:
            progress(f'Verified {n}/{current["IDs"]} files')
    assert rows == current['rows'] == parent['rows'] == 39099193
    assert len(index) == current['IDs'] == 3741
    assert current['fields'] == parent['fields'] == 129
    assert current['pools'] == parent['pools'] == index.groupby('pool').size().to_dict()
    assert current['drogue_status_counts'] == parent['drogue_status_counts']
    assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx') == current['contract_sha256']
    assert changed_cells == receipt['new_numeric_NA_cells']
    schema = json.loads(paths.asset('current_dataset_schema', verify=True).read_text())
    assert schema['fields'] == json.loads((root/receipt['parent_schema_path']).read_text())['fields']
    return {'passed': True, 'release': VERSION, 'IDs': 3741, 'rows': rows, 'fields_per_ID': 129,
            'changed_ID_files': len(changed), 'normalized_NaN_cells': changed_cells,
            'null_cells_by_field': dict(nulls), 'missing_IDs_by_field': dict(missing_ids),
            'preserved_zero_cells_by_field': dict(zeros), 'other_122_columns_unchanged': True,
            'finite_hardware_values_unchanged': True, 'all_schema_metadata_unchanged': True,
            'all_rows_keys_order_and_pools_unchanged': True, 'new_feature_columns': [],
            'drogue_status_and_SST_unchanged': True, 'contract_unchanged': True,
            'forecast_accuracy_evaluated': False}
