"""Independent selection and same-case scoring fixtures."""
import importlib
import unittest
import numpy as np
import pandas as pd

from data3001.modelling.markov import fit_operator, forecast
from data3001.modelling.markov_velocity import fit_joint_operator
from data3001.modelling.evaluate import score_distribution


def api(): return importlib.import_module('data3001.modelling.markov_velocity_cv')


class CVTests(unittest.TestCase):
    def test_parameter_ties_prefer_shorter_lag_then_more_pooling(self):
        m = api()
        t = pd.DataFrame([[7, 1, 0., .2, 1], [7, 1, 1., .2, 1], [7, 3, 1., .2, 1]],
                         columns=['horizon_days', 'lag_days', 'lambda_value', 'loss_sum', 'pair_count'])
        self.assertEqual(m.choose_parameters(t), {7: (1, 1.)})
        self.assertEqual(m.choose_parameters(t, lambda_restrict=0.), {7: (1, 0.)})

    def data(self):
        columns = ['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1',
                   'origin_atom', 'destination_atom', 'pair_count']
        counts = pd.DataFrame([[1, h, i, j, a, b, w] for h in [1, 2, 3, 5, 7]
                               for i, j, a, b, w in [(10, 10, 1, 1, 1), (10, 20, 8, 8, 3),
                                                     (20, 10, 8, 1, 2), (20, 20, 8, 8, 1)]], columns=columns)
        keys = ['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1']
        plain = counts.groupby(keys, as_index=False).pair_count.sum()
        ops = {h: fit_joint_operator(counts, {1}, [10, 20], [.5], .5, h) for h in [1, 2, 3, 5, 7]}
        old = {h: fit_operator(plain, {1}, [10, 20], h) for h in ops}
        r = pd.DataFrame([[2, h, 10, 10, 1, 2], [2, h, 10, 20, 8, 3]] for h in []) if False else pd.DataFrame(
            [[2, h, 10, 10, 1, 2] for h in [7, 30]]+[[2, h, 10, 20, 8, 3] for h in [7, 30]],
            columns=keys+['origin_velocity_bin', 'pair_count'])
        return ops, old, r

    def test_all_candidates_preserve_cases_and_match_independent_brier(self):
        m = api(); ops, old, r = self.data()
        stats = m.score_candidates(ops, old, r, {2}, lambdas=[0., .5, 1.])
        self.assertEqual(len(stats), 2*4*3)
        self.assertTrue(stats.pair_count.eq(5).all())
        for row in stats.itertuples():
            p = m.predict_locations(ops, [(10, 1), (10, 8)], [row.horizon_days], row.lag_days, row.lambda_value)[row.horizon_days]
            direct = sum(w*score_distribution(q, truth, u)['brier_failure_penalized']
                         for (q, u), truth, w in zip(p, [10, 20], [2, 3]))
            self.assertAlmostEqual(row.loss_sum, direct, places=12)
            if row.lambda_value == 1.:
                lag, h = row.lag_days, row.horizon_days
                q, u = forecast(old[lag], 10, h, old[h % lag] if h % lag else None)
                expected = sum(w*score_distribution(q, truth, u)['brier_failure_penalized']
                               for truth, w in [(10, 2), (20, 3)])
                self.assertAlmostEqual(row.loss_sum, expected, places=12)

    def test_fitting_ids_cannot_be_evaluated(self):
        m = api(); ops, old, r = self.data()
        with self.assertRaises(ValueError): m.score_candidates(ops, old, r, {1, 2})


if __name__ == '__main__': unittest.main()
