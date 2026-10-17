"""Scientific boundary cases for the authorized recovery/SST amendment."""
import importlib
import unittest
import numpy as np
import pandas as pd

try:
    m = importlib.import_module('data3001.model_input_cleaning')
except ModuleNotFoundError:
    m = None


class ModelInputCleaningTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m, 'Recovery/SST cleaning rules are not implemented')

    def test_recovery_removes_only_tail_and_includes_last_good_time(self):
        f = pd.DataFrame({'time':[1599955200.,1599958800.,1599962400.],
                          'end_date':[1599958800.]*3,'typedeath':[2]*3,
                          'source_obs':[20,21,22],'velocity':[1.,2.,3.]})
        original = f.copy(deep=True)
        out = m.exclude_recovery_tail(f)
        self.assertEqual(out.source_obs.tolist(), [20,21])
        pd.testing.assert_frame_equal(f, original)
        self.assertEqual(out.velocity.tolist(), [1.,2.])

    def test_other_termination_causes_are_not_relabelled_or_removed(self):
        for death in [0,1,3,4,5,6]:
            f = pd.DataFrame({'time':[100.,200.],'end_date':[100.,100.],
                              'typedeath':[death,death]})
            pd.testing.assert_frame_equal(m.exclude_recovery_tail(f), f)

    def test_missing_or_contradictory_recovery_metadata_fail_closed(self):
        for end in [[np.nan,np.nan],[100.,200.]]:
            f=pd.DataFrame({'time':[100.,200.],'end_date':end,'typedeath':[2,2]})
            with self.assertRaises(ValueError): m.exclude_recovery_tail(f)

    def test_review_flags_jump_endpoints_but_not_long_gaps_or_roundoff(self):
        f=pd.DataFrame({'time':[0.,3600.,7200.,20000.,23600.],
                        'sst':np.array([20.,26.,20.,-2.000006,40.])+273.15,
                        'flg_sst':[5,5,5,5,5]})
        self.assertEqual(m.sst_review_mask(f).tolist(),[True,True,True,True,True])
        isolated=pd.DataFrame({'time':[0.,7200.], 'sst':np.array([-2.000006,30.])+273.15,
                               'flg_sst':[5,5]})
        self.assertFalse(m.sst_review_mask(isolated).any())

    def test_range_review_is_not_an_automatic_replacement(self):
        native=np.array([49.13,44.,28.,46.,46.,np.nan])
        bg=np.array([28.13,27.,23.,42.,np.nan,27.])
        self.assertEqual(m.confirmed_high_replacement(native,bg).tolist(),
                         [True,False,False,False,False,False])

    def test_ordinary_native_variability_and_bad_qc_are_separate(self):
        f=pd.DataFrame({'time':[0.,3600.,7200.],
                        'sst':np.array([27.,28.,60.])+273.15,'flg_sst':[5,5,3]})
        self.assertFalse(m.sst_review_mask(f).any())

    def test_current_model_reader_removes_real_recovered_tail(self):
        from pathlib import Path
        if not (Path(__file__).resolve().parents[1]/'data/train/132499.parquet').exists():
            self.skipTest('Complete local data required')
        from data3001.sst_sparse_current import read_sst_track
        frame=read_sst_track(132499)
        self.assertTrue((frame.time <= frame.end_date.astype(float)).all())
        self.assertTrue(len(frame)>0)

    def test_removed_recovery_endpoint_becomes_censored_not_a_destination(self):
        from data3001.preprocessing import prep_core as c
        f=pd.DataFrame({'time':np.arange(25,dtype=float)*3600,
                        'end_date':[23*3600.]*25,'typedeath':[2]*25})
        out=m.exclude_recovery_tail(f)
        n=len(out)
        a={'time':out.time.to_numpy(),'position_ok':np.ones(n,bool),
           'mapping_ok':np.ones(n,bool),'inside_D':np.ones(n,bool),
           'regime':np.ones(n,dtype=np.int8),'lon':np.zeros(n),'lat':np.zeros(n),
           'loss':1e10}
        e,p=c.labels(a,np.array([0]),1,0,'pooled',c.event_bounds(a),cutoff=100*3600)
        self.assertEqual(e['reason'][0],3)
        self.assertEqual(p['reason'][0],3)
        self.assertFalse(p['outside'][0])


if __name__ == '__main__': unittest.main()
