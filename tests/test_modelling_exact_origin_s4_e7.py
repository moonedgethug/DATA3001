import unittest

import numpy as np

from data3001.modelling.baselines.exact_origin_s4_e7 import (
    NeighbourIndex, probability_summary, sparse_forecast,
)
from data3001.preprocessing.prep_core import GEOD, cells


class NeighbourTests(unittest.TestCase):
    def assert_exact(self, index, lon, lat, k):
        got = index.query(lon, lat, k)
        expected = index.exhaustive(lon, lat, k)
        np.testing.assert_array_equal(got[0], expected[0])
        np.testing.assert_allclose(got[1], expected[1], atol=1e-9, rtol=0)
        return got

    def test_caps_ties_duplicates_and_source_multiplicity(self):
        distance = np.array([0., 0., 25000., 25000., 100000., 100000.0001, 160000.])
        lon, lat, _ = GEOD.fwd(np.full(len(distance), -75.), np.full(len(distance), 32.),
                               np.full(len(distance), 90.), distance)
        index = NeighbourIndex(lon, lat)
        ix, dist = self.assert_exact(index, -75., 32., 4)
        self.assertEqual(ix.tolist(), [0, 1, 2, 3])
        self.assertEqual(index.select(ix, dist, 1).tolist(), [0, 1])
        ix, dist = self.assert_exact(index, -75., 32., 20)
        self.assertEqual(ix.tolist(), [0, 1, 2, 3, 4])
        states, p = sparse_forecast(np.array([10, 11, 10, 10, -2, 99, 99]), ix)
        np.testing.assert_array_equal(states, [-2, 10, 11])
        np.testing.assert_array_equal(p, [.2, .6, .2])

    def test_exhaustive_equivalence_equator_poles_and_dateline(self):
        rng = np.random.default_rng(9173)
        for x, y in [(-75., 32.), (179.9, 0.), (-179.9, 67.), (30., 89.8)]:
            az = rng.uniform(-180, 180, 1500)
            distance = rng.uniform(0, 180000, len(az))
            lon, lat, _ = GEOD.fwd(np.full(len(az), x), np.full(len(az), y), az, distance)
            index = NeighbourIndex(lon, lat)
            for k in [1, 8, 150, 800, 2000]:
                self.assert_exact(index, x, y, k)

    def test_refinement_can_recover_geodesically_closer_nonseed(self):
        # Equal chord distances need not have equal surface distances on an
        # ellipsoid. Choose a tiny surface-distance separation at a long radius
        # so seed order and geodesic order demonstrably differ.
        x, y = -75., 0.
        az = np.arange(0., 360., 1.)
        lon, lat, _ = GEOD.fwd(np.full(len(az), x), np.full(len(az), y), az,
                               np.full(len(az), 99000.))
        index = NeighbourIndex(lon, lat)
        ix, distances = self.assert_exact(index, x, y, 1)
        self.assertEqual(len(ix), len(az))
        self.assertGreater(index.last_stats["refinement_evaluations"], 0)
        self.assertLessEqual(np.ptp(distances), 1e-6)

    def test_cell_boundary_does_not_restrict_neighbours(self):
        lon = np.array([-75.0001, -74.9999, -75.01])
        lat = np.full(3, 32.2)
        self.assertNotEqual(cells(lon, lat)[0], cells(lon, lat)[1])
        index = NeighbourIndex(lon, lat)
        ix, _ = self.assert_exact(index, -75., 32.2, 2)
        self.assertEqual(set(ix), {0, 1})

    def test_no_support_and_invalid_inputs(self):
        for index in [NeighbourIndex([], []), NeighbourIndex([-75.], [32.])]:
            ix, d = self.assert_exact(index, 0., 0., 5)
            self.assertEqual(len(ix), 0)
            self.assertEqual(len(d), 0)
        with self.assertRaises(ValueError):
            NeighbourIndex([np.nan], [0.])
        with self.assertRaises(ValueError):
            NeighbourIndex([0.], [95.])
        with self.assertRaises(ValueError):
            NeighbourIndex([0.], [0.]).query(0., 0., 0)
        with self.assertRaises(ValueError):
            sparse_forecast(np.array([5]), np.array([], dtype=int))

    def test_complete_support_check_including_chord_order_refinement(self):
        lon, lat, _ = GEOD.fwd(np.array([0., 0.]), np.array([0., 0.]),
                               np.array([0., 90.]), np.array([100000.002, 99999.998]))
        index = NeighbourIndex(lon, lat)
        got = index.support(np.array([0., lon[0], 60.]), np.array([0., lat[0], 60.]))
        np.testing.assert_array_equal(got, [True, True, False])
        self.assertGreaterEqual(index.support_stats["refined_queries"], 2)
        for x, y, present in zip([0., lon[0], 60.], [0., lat[0], 60.], got):
            self.assertEqual(present, bool(len(index.exhaustive(x, y, 1)[0])))
        np.testing.assert_array_equal(NeighbourIndex([], []).support([0., 1.], [0., 1.]),
                                      [False, False])

    def test_distance_calls_obey_batch_limit(self):
        # Lower the chunk size for a synthetic fixture, exercising the exact
        # production path without creating a large resource workload.
        from unittest.mock import patch
        import data3001.modelling.baselines.exact_origin_s4_e7 as module
        index = NeighbourIndex(np.linspace(-75.1, -74.9, 41), np.full(41, 32.))
        with patch.object(module, "MAX_DISTANCE_BATCH", 7):
            self.assert_exact(index, -75., 32., 30)


class ForecastTests(unittest.TestCase):
    def test_sparse_truth_outside_support_and_exit(self):
        states, p = sparse_forecast(np.array([10, 10, -2, 11]), np.arange(4))
        areas = {10: 3., 11: 5.}
        summary = probability_summary(states, p, 99, areas)
        self.assertAlmostEqual(summary["brier"], 1.375)
        self.assertEqual(summary["zero"], 1.)
        self.assertEqual(summary["h90"], 0.)
        self.assertEqual(summary["k90"], 2)
        self.assertEqual(summary["area90"], 8.)
        self.assertEqual(summary["exit"], .25)
        self.assertTrue(summary["exit_in_region"])
        self.assertEqual(summary["geographic_mass"], .75)
        self.assertEqual(probability_summary(states, p, -2, areas)["h90"], 1.)
        self.assertAlmostEqual(probability_summary(states, p, -2, areas)["brier"], .875)

    def test_zero_exit_and_positive_region_ties(self):
        codes = np.array([10] * 45 + [11] * 45 + [12] * 10)
        states, p = sparse_forecast(codes, np.arange(100))
        summary = probability_summary(states, p, 12, {10: 2., 11: 3., 12: 7.})
        self.assertEqual(states[0], -2)
        self.assertEqual(p[0], 0.)
        np.testing.assert_array_equal(summary["mask"], [False, True, True, False])
        self.assertEqual(summary["area90"], 5.)
        self.assertAlmostEqual(summary["mass"], .9)
        self.assertFalse(summary["exit_in_region"])

    def test_fine_endpoint_counts_coarsen_without_uniform_splitting(self):
        lon = np.array([-75.9, -75.8, -75.7, -75.2, -74.8])
        lat = np.array([32.1, 32.1, 32.1, 32.6, 32.6])
        coarse, fine = cells(lon, lat, 1), cells(lon, lat, .5)
        states, p = sparse_forecast(fine, np.arange(len(fine)))
        parent = np.where(states >= 0, ((states // 720) // 2) * 360 + (states % 720) // 2, -2)
        direct_states, direct_p = sparse_forecast(coarse, np.arange(len(coarse)))
        coarsened = np.array([p[parent == s].sum() for s in direct_states])
        np.testing.assert_allclose(coarsened, direct_p, atol=1e-12, rtol=0)
        positive = p[states >= 0]
        self.assertEqual(sorted(positive.tolist()), [.2, .2, .6])

    def test_missing_areas_or_unsupported_negative_states_fail(self):
        with self.assertRaises(KeyError):
            probability_summary(np.array([-2, 1]), np.array([0., 1.]), 1, {})
        with self.assertRaises(ValueError):
            sparse_forecast(np.array([-1, 1]), np.arange(2))
        with self.assertRaises(ValueError):
            sparse_forecast(np.array([1]), np.array([0, 0]))


if __name__ == "__main__":
    unittest.main()
