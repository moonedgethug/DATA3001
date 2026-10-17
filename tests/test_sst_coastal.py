"""Tests for the approved three-corner extension, not forecast accuracy."""
import importlib
import unittest
import numpy as np
import pandas as pd

try:
    m = importlib.import_module('data3001.sst_coastal')
except ModuleNotFoundError:
    m = None


class CoastalSSTTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m, 'Three-corner reconstruction is not implemented')

    def test_inside_reproduces_a_planar_temperature_field(self):
        out = m.three_corner_temperature([.2], [.3], [[20., 24., 28., np.nan]])
        self.assertTrue(out['inside'][0])
        self.assertEqual(out['method'][0], 4)
        self.assertAlmostEqual(out['temperature_C'][0], 23.2)
        np.testing.assert_allclose(out['weights'][0], [.5, .2, .3, 0.])

    def test_outside_uses_restricted_bilinear_weights(self):
        out = m.three_corner_temperature([.8], [.8], [[20., 24., 28., np.nan]])
        self.assertFalse(out['inside'][0])
        self.assertEqual(out['method'][0], 5)
        np.testing.assert_allclose(out['weights'][0], [1/9, 4/9, 4/9, 0.])
        self.assertAlmostEqual(out['available_weight_mass'][0], .36)
        self.assertAlmostEqual(out['temperature_C'][0], 228/9)

    def test_triangle_boundary_is_inside(self):
        out = m.three_corner_temperature([.6], [.4], [[20., 24., 28., np.nan]])
        self.assertTrue(out['inside'][0])
        self.assertEqual(out['method'][0], 4)
        np.testing.assert_allclose(out['weights'][0], [0., .6, .4, 0.], atol=1e-12)

    def test_each_missing_corner_uses_spatially_correct_weights(self):
        vertices = np.array([[0,0], [1,0], [0,1], [1,1]], float)
        for absent in range(4):
            available = np.arange(4) != absent
            xy = vertices[available].mean(axis=0)
            temps = 10 + 2*vertices[:,0] + 3*vertices[:,1]
            temps[absent] = np.nan
            out = m.three_corner_temperature([xy[0]], [xy[1]], [temps])
            self.assertTrue(out['inside'][0])
            self.assertAlmostEqual(out['temperature_C'][0], 10+2*xy[0]+3*xy[1])
            self.assertEqual(out['weights'][0,absent], 0.)

    def test_zero_available_weight_remains_unknown(self):
        out = m.three_corner_temperature([1.], [1.], [[20., 24., 28., np.nan]])
        self.assertTrue(np.isnan(out['temperature_C'][0]))
        self.assertEqual(out['method'][0], 3)

    def test_four_or_two_available_corners_are_out_of_scope(self):
        for row in [[20.,21.,22.,23.], [20.,np.nan,np.nan,23.]]:
            with self.assertRaises(ValueError):
                m.three_corner_temperature([.5], [.5], [row])

    def test_outside_original_rectangle_is_rejected(self):
        with self.assertRaises(ValueError):
            m.three_corner_temperature([1.1], [.5], [[20.,21.,22.,np.nan]])

    def test_water_corners_do_not_permit_an_island_inside_the_support_hull(self):
        import shapely
        function = getattr(m, 'water_support_hull_ok', None)
        self.assertIsNotNone(function, 'The no-cross-land gate is missing')
        points = np.array([[[0.,0.], [1.,0.], [0.,1.]]])
        target = np.array([[.8,.8]])
        island = shapely.box(.4,.4,.5,.5)
        self.assertFalse(function(target,points,[island])[0])

    def test_both_masks_must_allow_the_support_and_shore_touch_is_rejected(self):
        import shapely
        function = getattr(m, 'water_support_hull_ok', None)
        self.assertIsNotNone(function, 'The no-cross-land gate is missing')
        points = np.array([[[0.,0.], [1.,0.], [0.,1.]]])
        target = np.array([[.2,.2]])
        distant_land = shapely.box(2.,2.,3.,3.)
        shore_touch = shapely.box(-1.,-.1,0.,.1)
        self.assertTrue(function(target,points,[distant_land])[0])
        self.assertFalse(function(target,points,[distant_land,shore_touch])[0])

    def test_patch_only_updates_unknown_temperature_without_changing_keys(self):
        base = pd.DataFrame({'id':[1,1], 'source_obs':[0,1],
                             'sst_method':[0,3], 'sst_use_K':[290.,np.nan],
                             'other':['native','unchanged']})
        patch = pd.DataFrame({'id':[1], 'source_obs':[1], 'sst_method':[4],
                              'sst_use_K':[291.]})
        out = m.apply_coastal_patch(base, patch)
        self.assertEqual(out.to_dict('list'), {'id':[1,1], 'source_obs':[0,1],
            'sst_method':[0,4], 'sst_use_K':[290.,291.], 'other':['native','unchanged']})
        self.assertTrue(np.isnan(base.sst_use_K.iloc[1]))

    def test_patch_refuses_known_values_duplicate_keys_and_unknown_rows(self):
        base = pd.DataFrame({'id':[1,1], 'source_obs':[0,1],
                             'sst_method':[0,3], 'sst_use_K':[290.,np.nan]})
        for obs in [[0], [1,1], [2]]:
            patch = pd.DataFrame({'id':[1]*len(obs), 'source_obs':obs,
                'sst_method':[4]*len(obs), 'sst_use_K':[291.]*len(obs)})
            with self.assertRaises(ValueError):
                m.apply_coastal_patch(base, patch)


if __name__ == '__main__':
    unittest.main()
