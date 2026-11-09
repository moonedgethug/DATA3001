"""Regression for nullable IID columns retained as object after batch collection."""
import unittest

import pandas as pd

from data3001.modelling.continuous_models import local_gmm_s5_e2_audit as audit


class IIDNumericColumns(unittest.TestCase):
    def test_object_numeric_scores_keep_the_same_iid_decision(self):
        rows = pd.DataFrame({
            'id': [1, 2, 3], 'energy_km': [2., 2., 2.],
            'variance': [1e-6] * 3,
            'iid_energy_km': [2., 2.001, 1.999],
            'iid_variance': [1e-6] * 3,
        }).astype({'iid_energy_km': object, 'iid_variance': object})
        result = audit.iid_gate(rows)
        self.assertTrue(result['passed'])
        self.assertEqual(result['cases'], 3)
        self.assertAlmostEqual(result['mean_difference'], 0., places=14)
        self.assertAlmostEqual(result['three_se'], .002449489742783178, places=14)
        self.assertAlmostEqual(result['max_standardised_difference'], .7071067811865476, places=12)

    def test_object_numeric_scores_still_reject_iid_disagreement(self):
        rows = pd.DataFrame({
            'id': [1, 2, 3], 'energy_km': [2.] * 3,
            'variance': [1e-6] * 3,
            'iid_energy_km': [200.] * 3,
            'iid_variance': [1e-6] * 3,
        }).astype({'iid_energy_km': object, 'iid_variance': object})
        self.assertFalse(audit.iid_gate(rows)['passed'])
