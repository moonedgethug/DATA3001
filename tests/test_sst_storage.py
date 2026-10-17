"""SST cleaning changes the existing field without widening current frames."""
import importlib.util
import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import pyarrow as pa


class SSTStorage(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('data3001.sst_storage'),
                             'In-column SST storage is not implemented')
        from data3001 import sst_storage
        return sst_storage

    def source(self):
        table=pa.table({'id':[7,7,7], 'source_obs':[10,20,30],
                        'sst':pa.array([300.,None,319.],type=pa.float32()),
                        'keep':pa.array([np.nan,None,2.],type=pa.float32(),from_pandas=False)})
        table=table.set_column(2,pa.field('sst',pa.float32(),metadata={b'units':b'Kelvin'}),table['sst'])
        return table.replace_schema_metadata({b'data3001':json.dumps({'id':'7','pool':'train'}).encode(),
                                               b'other':b'preserve'})

    def test_approved_values_are_written_to_sst_in_key_order_without_new_columns(self):
        m=self.module();original=self.source()
        side=pd.DataFrame({'id':[7,7,7,7],'source_obs':[30,10,20,999],
                           'sst_use_K':[301.123456789,300.,np.nan,310.]})
        out=m.replace_sst(original,side)
        self.assertEqual(out.column_names,original.column_names)
        self.assertNotIn('sst_use_K',out.column_names)
        np.testing.assert_array_equal(out['sst'].to_numpy(),[300.,np.nan,301.123456789])
        self.assertEqual(out.schema.field('sst').type,pa.float64())
        self.assertEqual(out.schema.field('sst').metadata[b'units'],b'Kelvin')
        from data3001.recovery_storage import tables_equal
        self.assertTrue(tables_equal(out.drop(['sst']).replace_schema_metadata(None),
                                    original.drop(['sst']).replace_schema_metadata(None)))
        self.assertEqual(out.schema.metadata[b'other'],b'preserve')
        self.assertEqual(original['sst'][2].as_py(),319.)

    def test_missing_or_duplicate_evidence_keys_abort_instead_of_partial_fill(self):
        m=self.module();source=self.source()
        with self.assertRaisesRegex(ValueError,'missing'):
            m.replace_sst(source,pd.DataFrame({'id':[7,7],'source_obs':[10,20],'sst_use_K':[300.,301.]}))
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            m.replace_sst(source,pd.DataFrame({'id':[7,7,7,7],'source_obs':[10,20,30,30],
                                             'sst_use_K':[300.,301.,302.,303.]}))

    def test_default_temperature_reader_returns_only_current_stored_columns(self):
        from data3001.sst_sparse_current import read_sst_track
        frame=pd.DataFrame({'id':[7],'sst':[300.],'ve':[.1]})
        with patch('data3001.dataset.read_track',return_value=frame):
            result=read_sst_track(7)
        self.assertEqual(result.columns.tolist(),frame.columns.tolist())
        self.assertEqual(result.sst.tolist(),[300.])


if __name__=='__main__':unittest.main()
