"""A clone must read prepared data and qualifications without private raw caches."""
import json
import os
from pathlib import Path
import tempfile
import unittest

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from data3001.paths import file_sha256, project_paths


class PortableDataset(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); (self.root/'configs').mkdir()
        records = {}; evidence = {}
        for sid, pool, split in [(7, 'train', 'validation'), (9, 'test', 'test')]:
            name = f'data/{pool}/{sid}.parquet'; path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            table = pa.table({'id': [sid, sid], 'source_obs': [10, 11],
                              'time': [100., 3700.]})
            table = table.replace_schema_metadata({b'data3001': json.dumps({
                'id': str(sid), 'pool': pool, 'historical_split': split,
                'release': 'per-drifter-20261016-v1'}).encode()})
            pq.write_table(table, path)
            records[str(sid)] = {'id': str(sid), 'pool': pool, 'historical_split': split,
                                'path': name, 'rows': 2, 'sha256': file_sha256(path)}
            qname = f'provenance/qualification/v7/{"restricted_test" if pool == "test" else "development"}/{sid}.parquet'
            qpath = self.root/qname; qpath.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(table.append_column('in_R', pa.array([True, False])), qpath)
            evidence[str(sid)] = {'path': qname, 'pool': pool, 'rows': 2,
                                  'sha256': file_sha256(qpath), 'parent_sha256': 'parent-'+str(sid)}
        rule = {'policy': 'approved_drop_list_except_four_native_position_velocity_uncertainties',
                'removed_columns': ['in_R'], 'parent_manifest_path': 'absent-parent.json',
                'parent_manifest_sha256': 'absent'}
        m = {'version': 'per-drifter-20261016-v1', 'IDs': 2, 'rows': 4, 'fields': 3,
             'pools': {'train': 1, 'test': 1}, 'records': records,
             'cleaning': {'feature_pruning': rule}}
        mp = self.root/'configs/dataset_manifest.json'; mp.write_text(json.dumps(m))
        qp = self.root/'configs/qualification_manifest.json'
        qp.write_text(json.dumps({'version': 'exact-pre-projection-qualification-v1',
            'dataset_manifest_sha256': file_sha256(mp), 'records': evidence,
            'fields': ['id', 'source_obs', 'time', 'in_R']}))
        sp = self.root/'configs/dataset_schema.json'
        sp.write_text(json.dumps({'version': m['version'], 'fields': [
            {'name': 'id', 'arrow_type': 'int64'}, {'name': 'source_obs', 'arrow_type': 'int64'},
            {'name': 'time', 'arrow_type': 'double'}]}))
        assets = {'current_dataset_manifest': {'path': 'configs/dataset_manifest.json', 'kind': 'file', 'sha256': file_sha256(mp)},
                  'current_dataset_schema': {'path': 'configs/dataset_schema.json', 'kind': 'file', 'sha256': file_sha256(sp)},
                  'current_qualification_manifest': {'path': 'configs/qualification_manifest.json', 'kind': 'file', 'sha256': file_sha256(qp)},
                  'current_train_tracks': {'path': 'data/train', 'kind': 'directory', 'split': 'development'},
                  'current_test_tracks': {'path': 'data/test', 'kind': 'directory', 'split': 'test'}}
        (self.root/'configs/assets.json').write_text(json.dumps({'schema_version': 1, 'assets': assets}))
        self.old = os.environ.get('DATA3001_PROJECT_ROOT')
        os.environ['DATA3001_PROJECT_ROOT'] = str(self.root); project_paths.cache_clear()
        self.addCleanup(self.restore)

    def restore(self):
        if self.old is None: os.environ.pop('DATA3001_PROJECT_ROOT', None)
        else: os.environ['DATA3001_PROJECT_ROOT'] = self.old
        project_paths.cache_clear()

    def test_prepared_source_uses_manifest_assignments_without_raw_zarr(self):
        from data3001 import dataset
        self.assertTrue(hasattr(dataset, 'PreparedSource'), 'Portable prepared source missing')
        s = dataset.PreparedSource()
        self.assertEqual(s.cohort.loc[7, 'split'], 'validation')
        self.assertEqual(s.cohort.loc[9, 'split'], 'test')
        self.assertFalse(s.allow_test)

    def test_qualification_projection_does_not_require_full_parent_or_add_columns(self):
        from data3001.dataset import read_track
        from data3001.feature_pruning import qualification_arrays
        f = read_track(7); before = f.copy(deep=True)
        try: result = qualification_arrays(7, f, ['in_R'])
        except FileNotFoundError as exc: self.fail('Portable qualification still requires private parent: '+str(exc))
        self.assertEqual(result['in_R'].tolist(), [True, False])
        pd.testing.assert_frame_equal(f, before, check_exact=True)

    def test_portable_test_evidence_remains_explicit_opt_in(self):
        from data3001.dataset import read_track
        from data3001.feature_pruning import qualification_arrays
        f = read_track(9, allow_test=True)
        with self.assertRaises(PermissionError): qualification_arrays(9, f, ['in_R'])
        try: result = qualification_arrays(9, f, ['in_R'], allow_test=True)
        except FileNotFoundError as exc: self.fail('Portable test evidence still needs private parent: '+str(exc))
        self.assertEqual(result['in_R'].tolist(), [True, False])

    def test_portable_evidence_refuses_timestamp_changes(self):
        from data3001.dataset import read_track
        from data3001.feature_pruning import qualification_arrays
        f = read_track(7); f.loc[0, 'time'] = 101.
        with self.assertRaises(ValueError): qualification_arrays(7, f, ['in_R'])

    def test_downloaded_dataset_can_be_verified_without_archived_parent(self):
        from data3001 import dataset
        self.assertTrue(hasattr(dataset, 'verify_current_data'), 'Portable data verifier missing')
        result = dataset.verify_current_data()
        self.assertTrue(result['passed']); self.assertEqual(result['IDs'], 2)
        self.assertEqual(result['rows'], 4); self.assertEqual(result['qualification_files'], 2)
        self.assertFalse(result['forecast_accuracy_evaluated'])


if __name__ == '__main__': unittest.main()
