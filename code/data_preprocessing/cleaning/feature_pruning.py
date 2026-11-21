"""Approved storage projection; qualification evidence remains outside active data."""
from functools import lru_cache
import json

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from data3001.paths import file_sha256, project_paths
from data3001.recovery_storage import tables_equal

VERSION = 'per-drifter-cleaned-20261017-v7'
LAYOUT = 'per-drifter-cleaned-1.5'
POLICY = 'approved_drop_list_except_four_native_position_velocity_uncertainties'
AUDIT = 'provenance/migrations/feature_pruning_20261017_v1'
ARCHIVE = 'archive/feature_pruning_20261017_v1'
PROTECTED = ('err_lat', 'err_lon', 'err_ve', 'err_vn')


def prune_table(table, removed):
    """Project existing columns exactly; update only schema-level declarations."""
    removed = list(removed)
    if (len(set(removed)) != len(removed) or set(removed) & set(PROTECTED)
            or not set(removed) <= set(table.column_names)):
        raise ValueError('Unexpected, duplicate or protected removal field')
    out = table.select([n for n in table.column_names if n not in removed])
    metadata = dict(table.schema.metadata or {})
    if b'pandas' in metadata:
        pm = json.loads(metadata[b'pandas'])
        pm['columns'] = [c for c in pm['columns'] if c.get('field_name') not in removed]
        metadata[b'pandas'] = json.dumps(pm).encode()
    if b'data3001' in metadata:
        ctx = json.loads(metadata[b'data3001'])
        ctx['release'] = VERSION
        for name in ('native_field_names', 'prepared_field_names'):
            if name in ctx:
                ctx[name] = [n for n in ctx[name] if n not in removed]
        ctx['feature_pruning'] = {'policy': POLICY, 'audit_directory': AUDIT,
                                  'archive_directory': ARCHIVE}
        metadata[b'data3001'] = json.dumps(ctx, sort_keys=True).encode()
    return out.replace_schema_metadata(metadata)


@lru_cache(maxsize=4)
def _parent(path, checksum):
    if file_sha256(path) != checksum:
        raise ValueError('Archived feature-projection parent manifest changed')
    data = json.loads(path.read_text())
    if data['version'] != 'per-drifter-cleaned-20261017-v6':
        raise ValueError('Unexpected feature-projection parent')
    return data


@lru_cache(maxsize=4)
def _portable(path, checksum):
    if file_sha256(path) != checksum:
        raise ValueError('Portable qualification manifest changed')
    data = json.loads(path.read_text())
    if data['version'] != 'exact-pre-projection-qualification-v1':
        raise ValueError('Unexpected portable qualification version')
    return data


def qualification_arrays(id, frame, names, *, allow_test=False):
    """Read exact archived annotations into arrays, never append feature columns.

    The current source_obs/time keys must exactly match the archived evidence.
    This is a storage adapter, not a recalculation of eligibility or geometry.
    """
    names = list(names)
    result = {n: frame[n].to_numpy() for n in names if n in frame.columns}
    missing = [n for n in names if n not in result]
    if not missing:
        return result
    from data3001.dataset import manifest
    current = manifest(); sid = str(int(id)); record = current['records'][sid]
    if record['pool'] == 'test' and not allow_test:
        raise PermissionError('Final-test qualification evidence requires explicit access')
    rule = current.get('cleaning', {}).get('feature_pruning', {})
    if rule.get('policy') != POLICY or not set(missing) <= set(rule['removed_columns']):
        raise ValueError('No approved archived qualification fields for this frame')
    paths = project_paths(); root = paths.root
    portable = paths.catalog['assets'].get('current_qualification_manifest')
    if portable:
        data = _portable(paths.asset('current_qualification_manifest'), portable['sha256'])
        if data['dataset_manifest_sha256'] != paths.catalog['assets']['current_dataset_manifest']['sha256']:
            raise ValueError('Portable qualification belongs to another data snapshot')
        evidence = data['records'][sid]
        expected_path = ('provenance/qualification/v7/' +
                         ('restricted_test' if record['pool'] == 'test' else 'development') +
                         f'/{sid}.parquet')
        if (evidence['path'] != expected_path or evidence['pool'] != record['pool']
                or evidence['rows'] != record['rows'] or not set(missing) <= set(data['fields'])):
            raise ValueError('Portable qualification scope mismatch')
        backup = root/expected_path; expected_hash = evidence['sha256']
    else:
        parent = _parent(root/rule['parent_manifest_path'], rule['parent_manifest_sha256'])
        backup = root/rule['archive_directory']/('restricted_test' if record['pool'] == 'test'
                                                else 'development')/f'{sid}.parquet'
        expected_hash = parent['records'][sid]['sha256']
    if (backup.is_symlink() or not backup.resolve().is_relative_to(root)
            or file_sha256(backup) != expected_hash):
        raise ValueError('Archived or portable qualification file changed')
    if (not frame.id.eq(int(id)).all() or
            frame.attrs.get('data3001', {}).get('pool') != record['pool']):
        raise ValueError('Qualification frame identity mismatch')
    old = pq.read_table(backup, columns=['source_obs', 'time']+missing).to_pandas()
    if old.source_obs.duplicated().any() or frame.source_obs.duplicated().any():
        raise ValueError('Ambiguous qualification source key')
    ix = pd.Index(old.source_obs).get_indexer(frame.source_obs)
    if (ix < 0).any() or not np.array_equal(old.time.to_numpy()[ix], frame.time.to_numpy()):
        raise ValueError('Qualification source keys or timestamps changed')
    result.update({n: old[n].to_numpy()[ix] for n in missing})
    return result


def verify_feature_release(progress=None):
    """Independently compare every surviving value against the exact parent."""
    from collections import Counter
    from data3001.dataset import manifest
    root = project_paths().root; current = manifest()
    rule = current['cleaning']['feature_pruning']
    assert current['version'] == VERSION and rule['policy'] == POLICY
    parent = _parent(root/rule['parent_manifest_path'], rule['parent_manifest_sha256'])
    assert set(current['records']) == set(parent['records'])
    names = rule['retained_columns']; removed = rule['removed_columns']
    assert len(names) == current['fields'] == 62 and len(removed) == 67
    assert set(PROTECTED) <= set(names) and not set(names) & set(removed)
    index = pd.read_csv(root/'configs/dataset_index.csv')
    previous_index = pd.read_csv(root/ARCHIVE/'configs/dataset_index.csv')
    pd.testing.assert_frame_equal(index.drop(columns='sha256'),
                                  previous_index.drop(columns='sha256'), check_exact=True)
    indexed = index.set_index('id'); rows = 0; counts = Counter(); sst_NA = 0
    for n, (sid, record) in enumerate(current['records'].items(), 1):
        prior = parent['records'][sid]
        assert {k:v for k,v in record.items() if k != 'sha256'} == {
            k:v for k,v in prior.items() if k != 'sha256'}, sid
        path = root/record['path']
        backup = root/ARCHIVE/('restricted_test' if record['pool'] == 'test'
                               else 'development')/f'{sid}.parquet'
        assert not path.is_symlink() and not backup.is_symlink()
        assert file_sha256(path) == record['sha256'], sid
        assert file_sha256(backup) == prior['sha256'], sid
        old = pq.read_table(backup, columns=names); actual = pq.read_table(path)
        assert actual.column_names == names and len(actual) == record['rows'], sid
        assert tables_equal(actual.replace_schema_metadata(None),
                            old.replace_schema_metadata(None)), sid
        ctx = json.loads(actual.schema.metadata[b'data3001'])
        assert ctx['release'] == VERSION and ctx['pool'] == record['pool']
        assert not set(ctx['native_field_names'] + ctx['prepared_field_names']) & set(removed)
        assert int(indexed.loc[int(sid), 'rows']) == record['rows']
        assert indexed.loc[int(sid), 'sha256'] == record['sha256']
        status = actual['drogue_status'].to_numpy()
        counts.update({str(v): int((status == v).sum()) for v in [-1, 0, 1]})
        sst_NA += int(np.isnan(actual['sst'].to_numpy()).sum())
        rows += len(actual)
        if progress and n % 500 == 0:
            progress(f'Compared all retained values in {n}/{current["IDs"]} files')
    assert rows == current['rows'] == parent['rows'] == 39099193
    assert len(index) == current['IDs'] == parent['IDs'] == 3741
    assert current['pools'] == parent['pools'] == index.groupby('pool').size().to_dict()
    assert dict(counts) == current['drogue_status_counts'] == parent['drogue_status_counts']
    assert sst_NA == 16059
    assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx') == current['contract_sha256']
    schema = json.loads(project_paths().asset('current_dataset_schema', verify=True).read_text())
    parent_schema = json.loads((root/ARCHIVE/'configs/dataset_schema.json').read_text())
    assert schema['fields'] == [f for f in parent_schema['fields'] if f['name'] in names]
    return {'passed': True, 'release': VERSION, 'IDs': 3741, 'rows': rows,
            'fields_per_ID': 62, 'physically_removed_columns': removed,
            'preserved_uncertainty_fields': list(PROTECTED),
            'all_retained_values_nulls_types_field_metadata_keys_and_order_unchanged': True,
            'whole_ID_pool_assignments_unchanged': True, 'all_parent_backups_verified': True,
            'drogue_status_counts': dict(counts), 'SST_NA_unchanged': sst_NA,
            'contract_unchanged': True, 'new_feature_columns': [],
            'forecast_accuracy_evaluated': False}
