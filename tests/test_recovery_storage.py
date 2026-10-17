import importlib
import json
import tempfile
import unittest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import numpy as np

try:
    m=importlib.import_module('data3001.recovery_storage')
except ModuleNotFoundError:
    m=None


class RecoveryStorage(unittest.TestCase):
    def test_roundtrip_nan_equality_does_not_hide_changed_nulls(self):
        self.assertIsNotNone(m)
        self.assertTrue(hasattr(m,'tables_equal'),'NaN-aware exact comparison is missing')
        table=pa.table({'x':pa.array([np.nan,None,1.],type=pa.float32(),from_pandas=False)})
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'roundtrip.parquet';pq.write_table(table,path)
            self.assertTrue(m.tables_equal(table,pq.read_table(path)))
        changed=pa.table({'x':pa.array([np.nan,np.nan,1.],type=pa.float32(),from_pandas=False)})
        self.assertFalse(m.tables_equal(table,changed))

    def test_filter_preserves_every_field_value_type_and_metadata_on_retained_rows(self):
        self.assertIsNotNone(m,'Storage-level recovery cleaning is not implemented')
        table=pa.table({'id':pa.array([1,1,1],type=pa.int64()),
                        'time':[100.,200.,300.], 'end_date':pa.array([200.,200.,200.],type=pa.float32()),
                        'typedeath':pa.array([2,2,2],type=pa.int8()),
                        'source_obs':[10,11,12], 'sst':pa.array([None,300.,302.],type=pa.float32()),
                        'feature_to_keep':pa.array([b'a',b'b',b'c'])})
        table=table.replace_schema_metadata({b'original':b'untouched'})
        cleaned,removed=m.clean_table(table)
        self.assertTrue(cleaned.equals(table.slice(0,2),check_metadata=True))
        self.assertTrue(removed.equals(table.slice(2,1),check_metadata=True))
        self.assertEqual(len(table),3)

    def test_other_termination_causes_remain_unchanged(self):
        self.assertIsNotNone(m,'Storage-level recovery cleaning is not implemented')
        t=pa.table({'time':[100.,300.],'end_date':[200.,200.],'typedeath':[1,1]})
        cleaned,removed=m.clean_table(t)
        self.assertTrue(cleaned.equals(t,check_metadata=True));self.assertEqual(len(removed),0)

    def test_reader_accepts_a_versioned_cleaning_release(self):
        from data3001.dataset import _manifest
        from data3001.paths import file_sha256
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'manifest.json'
            p.write_text(json.dumps({'version':'per-drifter-cleaned-20261017-v2','IDs':1,'rows':2,
                 'cleaning':{'policy':'vessel_recovery_last_good_cutoff','removed_rows':1},
                 'records':{'1':{'pool':'train','historical_split':'train','rows':2,'path':'data/train/1.parquet'}}}))
            self.assertEqual(_manifest(p,file_sha256(p))['rows'],2)


if __name__=='__main__':unittest.main()
