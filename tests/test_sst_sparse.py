import importlib
import unittest
import numpy as np
import pandas as pd

try:
    m=importlib.import_module('data3001.sst_sparse')
except ModuleNotFoundError:
    m=None


class SparseSSTTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m,'Sparse source-count estimator is not implemented')
        self.points=np.array([[[0.,0.],[1.,0.],[0.,1.],[1.,1.]]])

    def sample(self,x,y,values):
        return m.sparse_temperature([x],[y],self.points,[values],[x],[y])

    def test_four_and_triangle_reproduce_linear_plane(self):
        for values,code in [([20.,22.,23.,25.],11),([20.,22.,23.,np.nan],12)]:
            r=self.sample(.2,.3,values)
            self.assertEqual(r['method'][0],code)
            self.assertAlmostEqual(r['temperature_C'][0],21.3)

    def test_three_outside_uses_existing_available_bilinear_weights(self):
        r=self.sample(.8,.8,[20.,24.,28.,np.nan])
        self.assertEqual(r['method'][0],13)
        self.assertAlmostEqual(r['temperature_C'][0],228/9)

    def test_two_sources_weight_by_geodesic_distance(self):
        r=self.sample(.25,0.,[20.,30.,np.nan,np.nan])
        self.assertEqual(r['method'][0],14)
        np.testing.assert_allclose(r['weights'][0],[.75,.25,0.,0.],atol=1e-12)
        self.assertAlmostEqual(r['temperature_C'][0],22.5)

    def test_exact_available_source_has_weight_one(self):
        r=self.sample(0.,0.,[20.,30.,np.nan,np.nan])
        self.assertEqual(r['temperature_C'][0],20.)
        np.testing.assert_array_equal(r['weights'][0],[1.,0.,0.,0.])

    def test_one_source_is_approximation_and_zero_is_unknown(self):
        r=self.sample(.25,.5,[np.nan,28.,np.nan,np.nan])
        self.assertEqual(r['method'][0],15)
        self.assertEqual(r['temperature_C'][0],28.)
        r=self.sample(.25,.5,[np.nan]*4)
        self.assertEqual(r['method'][0],3)
        self.assertTrue(np.isnan(r['temperature_C'][0]))

    def test_degenerate_three_source_weights_have_finite_distance_fallback(self):
        r=self.sample(1.,1.,[20.,24.,28.,np.nan])
        self.assertEqual(r['method'][0],16)
        self.assertTrue(np.isfinite(r['temperature_C'][0]))
        self.assertAlmostEqual(r['weights'][0].sum(),1.)
        self.assertTrue(20.<=r['temperature_C'][0]<=28.)

    def test_termination_metadata_do_not_invent_grounding_hour(self):
        day=pd.Timestamp('2020-09-22T00:00:00Z').timestamp()
        c=m.termination_context([day-3600,day+3600,day+90000,day+90000],
                                 [day]*4,[1,1,1,3])
        self.assertEqual(list(c),['before_official_grounding_terminal_day',
          'official_grounding_terminal_day_hour_unknown',
          'after_official_grounding_last_good_day',
          'no_official_grounding_or_recovery_at_observation'])

    def test_patch_preserves_known_values_native_fields_and_order(self):
        f=pd.DataFrame({'id':[1,1],'source_obs':[10,20],'sst_method':[0,3],
                        'sst_use_K':[290.,np.nan],'sst_reason':['native','unknown']})
        p=pd.DataFrame({'id':[1],'source_obs':[20],'sst_method':[15],
                       'sst_use_K':[291.],'sst_reason':['one_source']})
        r=m.apply_sparse_patch(f,p)
        self.assertEqual(r.source_obs.tolist(),[10,20])
        self.assertEqual(r.sst_use_K.tolist(),[290.,291.])
        self.assertTrue(np.isnan(f.sst_use_K.iloc[1]))
        p.source_obs=10
        with self.assertRaises(ValueError):m.apply_sparse_patch(f,p)

    def test_actual_fine_axes_preserve_plane_with_descending_latitude(self):
        x=np.array([0.,1.]);y=np.array([1.,0.]);t=20+2*x[None,:]+3*y[:,None]
        r=m.sample_sparse_grid(.2,.3,x,y,t)
        self.assertEqual(r['method'],11)
        self.assertAlmostEqual(r['temperature_C'],21.3)

    def test_fine_empty_local_cell_can_use_nearest_real_node_in_received_window(self):
        t=np.full((3,3),np.nan);t[2,2]=27.
        r=m.sample_sparse_grid(.2,.3,[0.,1.,2.],[0.,1.,2.],t)
        self.assertEqual(r['method'],15)
        self.assertEqual(r['temperature_C'],27.)
        self.assertEqual(r['route'],'nearest_finite_in_received_window')
        r=m.sample_sparse_grid(.2,.3,[0.,1.],[0.,1.],np.full((2,2),np.nan))
        self.assertEqual(r['method'],3)
