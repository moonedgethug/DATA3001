"""Preservation rules for incremental temperature views."""
import importlib
import unittest
import pandas as pd
import numpy as np

try:
    m=importlib.import_module('data3001.sst_completion')
except ModuleNotFoundError:
    m=None


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m,'Incremental SST view is not implemented')

    def test_patch_retains_source_order_other_fields_and_known_values(self):
        old=pd.DataFrame({'id':[1,1], 'source_obs':[10,20], 'sst_method':[0,3],
                          'sst_use_K':[290.,np.nan], 'sst_reason':['native','unknown']})
        patch=pd.DataFrame({'id':[1], 'source_obs':[20], 'sst_method':[6],
                            'sst_use_K':[291.], 'sst_reason':['coastal_bilinear']})
        out=m.patch_temperature(old,patch)
        self.assertEqual(out.source_obs.tolist(),[10,20])
        self.assertEqual(out.sst_use_K.tolist(),[290.,291.])
        self.assertTrue(np.isnan(old.sst_use_K.iloc[1]))

    def test_patch_rejects_known_rows_duplicate_keys_and_unapproved_fields(self):
        old=pd.DataFrame({'id':[1,1], 'source_obs':[10,20], 'sst_method':[0,3],
                          'sst_use_K':[290.,np.nan], 'regime':[1,1]})
        for obs in [[10],[20,20],[30]]:
            patch=pd.DataFrame({'id':[1]*len(obs),'source_obs':obs,
                 'sst_method':[6]*len(obs),'sst_use_K':[291.]*len(obs)})
            with self.assertRaises(ValueError):m.patch_temperature(old,patch)
        bad=pd.DataFrame({'id':[1],'source_obs':[20],'sst_method':[6],
                          'sst_use_K':[291.],'regime':[0]})
        with self.assertRaises(ValueError):m.patch_temperature(old,bad)

    def test_fine_grid_handles_descending_latitude_and_actual_coordinates(self):
        x=np.array([-.05,.05]);y=np.array([.05,-.05])
        t=20+2*x[None,:]+3*y[:,None]
        r=m.grid_temperature(.01,.02,x,y,t)
        self.assertEqual(r['method'],8)
        self.assertAlmostEqual(r['temperature_C'],20.08)

    def test_fine_grid_routes_three_corners_inside_and_outside(self):
        x=np.array([0.,1.]);y=np.array([0.,1.]);t=np.array([[20.,24.],[28.,np.nan]])
        self.assertEqual(m.grid_temperature(.2,.3,x,y,t)['method'],9)
        r=m.grid_temperature(.8,.8,x,y,t)
        self.assertEqual(r['method'],10)
        self.assertAlmostEqual(r['temperature_C'],228/9)

    def test_direct_valid_point_does_not_need_other_corners(self):
        r=m.grid_temperature(0.,0.,[0.,1.],[0.,1.],[[22.,np.nan],[np.nan,np.nan]])
        self.assertEqual(r['method'],7)
        self.assertEqual(r['temperature_C'],22.)

    def test_two_corners_or_unbracketed_point_remain_unresolved(self):
        self.assertEqual(m.grid_temperature(.2,.3,[0.,1.],[0.,1.],
            [[20.,24.],[np.nan,np.nan]])['method'],3)
        self.assertEqual(m.grid_temperature(2.,.3,[0.,1.],[0.,1.],
            [[20.,24.],[22.,23.]])['method'],3)


if __name__=='__main__':unittest.main()
