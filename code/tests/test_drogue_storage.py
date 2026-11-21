"""Completed drogue states move into the existing column without relabelling."""
import importlib.util,json,unittest

import numpy as np
import pandas as pd
import pyarrow as pa

from data3001.recovery_storage import tables_equal


class DrogueStorage(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('data3001.drogue_storage'),
                             'In-column drogue consolidation is not implemented')
        from data3001 import drogue_storage
        return drogue_storage

    def source(self,states=None):
        table=pa.table({'id':[7,7,7],'drogue_status':pa.array([0,0,1],type=pa.int8()),
                         'regime':pa.array([-1,1,0] if states is None else states,type=pa.int8()),
                         'sst':[300.,None,301.],
                         'keep':pa.array([np.nan,None,2.],from_pandas=False)})
        return table.replace_schema_metadata({b'data3001':json.dumps({'id':'7','pool':'train',
              'prepared_field_names':table.column_names,'regime_context':{'proof':'kept'}}).encode(),
                                               b'other':b'unchanged'})

    def test_exact_three_state_transfer_removes_regime_and_preserves_every_other_field(self):
        m=self.module();original=self.source();out=m.materialize_drogue_status(original)
        self.assertEqual(out.column_names,[c for c in original.column_names if c!='regime'])
        self.assertEqual(out['drogue_status'].to_pylist(),[-1,1,0])
        self.assertEqual(out['drogue_status'].type,pa.int8())
        self.assertTrue(tables_equal(out.drop(['drogue_status']).replace_schema_metadata(None),
                                    original.drop(['drogue_status','regime']).replace_schema_metadata(None)))
        self.assertEqual(out.schema.metadata[b'other'],b'unchanged')
        context=json.loads(out.schema.metadata[b'data3001'])
        self.assertEqual(context['regime_context'],{'proof':'kept'})
        self.assertNotIn('regime',context['prepared_field_names'])
        self.assertEqual(original['drogue_status'].to_pylist(),[0,0,1])

    def test_unresolved_nulls_and_unapproved_codes_are_not_silently_transferred(self):
        m=self.module()
        for states in [[1,None,0],[1,2,0]]:
            with self.assertRaises(ValueError):m.materialize_drogue_status(self.source(states))

    def test_current_state_accessor_never_recreates_a_regime_feature(self):
        m=self.module();frame=pd.DataFrame({'drogue_status':[-1,1,0]})
        frame.attrs['data3001']={'drogue_status_cleaning':{'policy':m.POLICY}}
        np.testing.assert_array_equal(m.cleaned_drogue_values(frame),[-1,1,0])
        self.assertEqual(frame.columns.tolist(),['drogue_status'])
        legacy=pd.DataFrame({'drogue_status':[0],'regime':[-1]})
        np.testing.assert_array_equal(m.cleaned_drogue_values(legacy),[-1])


if __name__=='__main__':unittest.main()
