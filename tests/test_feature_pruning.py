"""An approved column projection must never change retained research evidence."""
import importlib.util
import json
import unittest

import numpy as np
import pyarrow as pa

from data3001.recovery_storage import tables_equal


class FeaturePruning(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('data3001.feature_pruning'),
                             'Approved feature projection is not implemented')
        from data3001 import feature_pruning
        return feature_pruning

    def source(self):
        t = pa.table({'id': [7, 7, 7], 'source_obs': [10, 11, 13],
                      'sst': pa.array([np.nan, None, 301.], from_pandas=False),
                      'in_R': [True, True, False],
                      'err_lat': pa.array([.1, np.nan, None], type=pa.float32(), from_pandas=False),
                      'err_lon': [.2, .3, .4], 'err_ve': [.1, .2, .3],
                      'err_vn': [.2, .3, .4], 'WMO': [42, 42, 42]})
        f = t.schema.field('err_lat').with_metadata({b'unit': b'degrees_north'})
        t = t.set_column(t.schema.get_field_index('err_lat'), f, t['err_lat'])
        return t.replace_schema_metadata({
            b'data3001': json.dumps({'id': '7', 'pool': 'train', 'release': 'parent',
                'prepared_field_names': ['sst', 'in_R', 'err_lat'],
                'native_field_names': ['id', 'sst', 'WMO'],
                'regime_context': {'proof': 'unchanged'}}).encode(),
            b'pandas': json.dumps({'index_columns': [], 'columns': [
                {'field_name': n, 'name': n} for n in t.column_names],
                'attributes': {'existing': 'unchanged'}}).encode(),
            b'other': b'unchanged'})

    def test_projection_preserves_retained_values_nulls_order_types_and_attributes(self):
        # A dropped surviving field, reset index or NaN-to-null change must fail.
        m = self.module(); old = self.source(); out = m.prune_table(old, ['in_R', 'WMO'])
        names = ['id', 'source_obs', 'sst', 'err_lat', 'err_lon', 'err_ve', 'err_vn']
        self.assertEqual(out.column_names, names)
        self.assertTrue(tables_equal(out.replace_schema_metadata(None),
                                    old.select(names).replace_schema_metadata(None)))
        self.assertEqual(out.schema.metadata[b'other'], b'unchanged')
        self.assertEqual(out['source_obs'].to_pylist(), [10, 11, 13])
        self.assertEqual(out['sst'].is_null().to_pylist(), [False, True, False])

    def test_metadata_describes_only_current_columns_without_erasing_source_evidence(self):
        # Stale column declarations must not mislead pandas or provenance readers.
        m = self.module(); out = m.prune_table(self.source(), ['in_R', 'WMO'])
        meta = out.schema.metadata; ctx = json.loads(meta[b'data3001'])
        self.assertEqual(ctx['prepared_field_names'], ['sst', 'err_lat'])
        self.assertEqual(ctx['native_field_names'], ['id', 'sst'])
        self.assertEqual(ctx['regime_context'], {'proof': 'unchanged'})
        self.assertEqual(ctx['release'], m.VERSION)
        self.assertEqual([x['field_name'] for x in json.loads(meta[b'pandas'])['columns']],
                         out.column_names)

    def test_protected_uncertainties_and_unexpected_names_are_rejected(self):
        # An overbroad drop list must stop before any data file is written.
        m = self.module()
        for fields in [['err_lat'], ['err_lon'], ['err_ve'], ['err_vn'],
                       ['absent'], ['WMO', 'WMO']]:
            with self.assertRaises(ValueError): m.prune_table(self.source(), fields)


if __name__ == '__main__': unittest.main()
