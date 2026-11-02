import unittest

import numpy as np

from data3001.modelling.common.prediction_regions import probability_region, budget_inclusion


class PredictionRegionsTests(unittest.TestCase):
    def test_cutoff_ties_and_mass(self):
        mask, meta = probability_region([0, .4, .3, .15, .15], [-2, 10, 20, 30, 40])
        self.assertEqual(mask.tolist(), [False, True, True, True, True])
        self.assertEqual(meta['region90_cells'], 4)
        self.assertAlmostEqual(meta['region90_mass'], 1.)

    def test_exit_is_outcome_not_geographic_cell(self):
        mask, meta = probability_region([.95, .05], [-2, 10])
        self.assertTrue(meta['region90_exit_included'])
        self.assertEqual(meta['region90_cells'], 0)
        inclusion, _ = budget_inclusion([.95, .05], [-2, 10], 1)
        np.testing.assert_array_equal(inclusion, [0, 1])

    def test_budget_ties_have_exact_expected_size(self):
        inc, meta = budget_inclusion([0, .5, .25, .25, 0], [-2, 10, 20, 30, 40], 2)
        np.testing.assert_array_equal(inc, [0, 1, .5, .5, 0])
        self.assertEqual(meta['tie_size'], 2)
        self.assertEqual(inc.sum(), 2)

    def test_zero_ties_are_explicit_uninformed_allocations(self):
        inc, meta = budget_inclusion([0, 1, 0, 0, 0], [-2, 10, 20, 30, 40], 2)
        np.testing.assert_allclose(inc, [0, 1, 1/3, 1/3, 1/3])
        self.assertTrue(meta['zero_probability_tie'])
        self.assertEqual(meta['remaining_slots'], 1)

    def test_boundary_floating_precision_and_zero_mass(self):
        mask, meta = probability_region([0, .3, .3, .3, .1, 0], [-2, 10, 20, 30, 40, 50])
        self.assertEqual(meta['region90_cells'], 3)
        self.assertFalse(mask[-1])

    def test_invalid_inputs(self):
        for p in ([0, .9], [0, float('nan')], [-.1, 1.1]):
            with self.assertRaises(ValueError):
                probability_region(p, [-2, 10])
        for k in (0, 2, 1.5, True):
            with self.assertRaises(ValueError):
                budget_inclusion([0, 1], [-2, 10], k)


if __name__ == '__main__':
    unittest.main()
