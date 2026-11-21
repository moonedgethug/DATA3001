"""Only total SST after the approved grounding cutoff becomes numeric NA."""
import importlib.util
import unittest

import numpy as np
import pyarrow as pa

from data3001.recovery_storage import tables_equal


class GroundingSST(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('data3001.grounding_sst'),
                             'The approved grounding SST rule is not implemented')
        from data3001 import grounding_sst
        return grounding_sst

    def test_only_after_cutoff_sst_is_null_and_all_other_data_and_metadata_survive(self):
        m=self.module()
        source=pa.table({'id':[7]*4,'time':[199.,200.,201.,202.],
                         'end_date':[200.]*4,'typedeath':[1]*4,
                         'sst':pa.array([299.,300.,301.,None],type=pa.float64()),
                         'sst1':[298.,299.,300.,301.],
                         'keep':pa.array([np.nan,None,1.,2.],from_pandas=False)})
        source=source.replace_schema_metadata({b'provenance':b'unchanged'})
        result=m.clear_post_grounding_sst(source)
        self.assertEqual(result.column_names,source.column_names)
        self.assertEqual(result['sst'].to_pylist(),[299.,300.,None,None])
        self.assertTrue(result.schema.equals(source.schema,check_metadata=True))
        self.assertTrue(tables_equal(result.drop(['sst']),source.drop(['sst'])))
        self.assertEqual(source['sst'].to_pylist(),[299.,300.,301.,None])

    def test_other_death_types_missing_or_invalid_cutoffs_and_times_are_not_reclassified(self):
        m=self.module()
        source=pa.table({'time':[201.,201.,201.,201.,201.,np.nan],
                         'end_date':[200.,200.,None,0.,-999999.,200.],
                         'typedeath':[2,3,1,1,1,1], 'sst':[300.]*6})
        self.assertTrue(tables_equal(m.clear_post_grounding_sst(source),source))


if __name__=='__main__':unittest.main()
