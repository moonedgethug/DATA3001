"""Synthetic checks only: no trajectories, labels or final-test access"""

import importlib
import importlib.util
import unittest

import numpy as np

from data3001.modelling.evaluate import score_distribution


class BlendTests(unittest.TestCase):
    def module(self):
        name = "data3001.modelling.blend"
        self.assertIsNotNone(
            importlib.util.find_spec(name),
            "The new blend module has not been created yet.",
        )
        return importlib.import_module(name)
    
    def test_grid_and_analytic_match_independent_scoring(self):
        m = self.module()
        q, r = {0: 1.0}, {1: 1.0}
        terms = [m.brier_terms(q, r, truth) for truth in (0, 1)]
        result = m.select_lambdas(terms, [63, 37])
        
        self.assertAlmostEqual(result["grid_lambda"], 0.4)
        self.assertAlmostEqual(result["analytic_lambda"], 0.37)
        self.assertAlmostEqual(result["grid_brier"], 0.468)
        self.assertAlmostEqual(result["analytic_brier"], 0.4662)
        
        for row in result["grid_scores"]:
            p, u = m.mix_forecasts(q, r, row["lambda"])
            direct = np.average(
                [
                    score_distribution(p, truth, unresolved=u)
                    ["brier_failure_penalized"]
                    for truth in (0, 1)
                ],
                weights=[63, 37],
            )
            self.assertAlmostEqual(direct, row["selection_brier"])
            
    def test_lambda_endpoints_reproduce_base_forecasts(self):
        m = self.module()
        q = {0: 0.8, 1: 0.2}
        r = {0: 0.2, 1: 0.8}
        
        self.assertEqual(m.mix_forecasts(q, r, 0.0), (q, 0.0))
        self.assertEqual(m.mix_forecasts(q, r, 1.0), (r, 0.0))
        
    def test_unresolved_mass_is_preserved(self):
        m = self.module()
        p, u = m.mix_forecasts({}, {1: 1.0}, 0.3, u2=1.0)
        
        self.assertAlmostEqual(p[1], 0.3)
        self.assertAlmostEqual(u, 0.7)
        self.assertAlmostEqual(
            score_distribution(p, 1, unresolved=u)
            ["brier_failure_penalized"],
            0.98,
        )
        
        result = m.select_lambdas(
            [m.brier_terms({}, {1: 1.0}, 1, u2=1.0)],
            [1],
        )
        self.assertEqual(result["analytic_lambda"], 1.0)
        
    def test_unseen_truth_remains_a_zero_probability_failure(self):
        m = self.module()
        p, u = m.mix_forecasts({0: 1.0}, {1: 1.0}, 0.5)
        score = score_distribution(p, 2, unresolved=u)
        
        self.assertEqual(score["true_probability"], 0.0)
        self.assertTrue(np.isinf(score["log_loss"]))
        self.assertAlmostEqual(score["brier"], 1.5)
        
    def test_identical_forecasts_have_no_unique_optimum(self):
        m = self.module()
        q = {0: 0.2, 1: 0.8}
        result = m.select_lambdas([m.brier_terms(q, q, 1)], [1])
        
        self.assertEqual(result["grid_lambda"], 0.0)
        self.assertEqual(result["analytic_lambda"], 0.0)
        
    def test_invalid_input_is_rejected(self):
        m = self.module()
        
        with self.assertRaises(ValueError):
            m.mix_forecasts({0: 1.0}, {1: 1.0}, 1.1)
            
        with self.assertRaises(ValueError):
            m.select_lambdas([(1.0, 0.0, 0.0)], [0])
            

if __name__ == "__main__":
    unittest.main()