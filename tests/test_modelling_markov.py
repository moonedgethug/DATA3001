"""Independent numerical fixtures; no real trajectory or final-test access."""
import importlib
import importlib.util
import unittest

import numpy as np
import pandas as pd


def api(name):
    full = 'data3001.modelling.' + name
    if importlib.util.find_spec(full) is None:
        raise AssertionError('Required implementation is absent: ' + full)
    return importlib.import_module(full)


class MarkovTests(unittest.TestCase):
    def counts(self):
        return pd.DataFrame([
            [1, 1, 10, 10, 2], [1, 1, 10, 20, 1],
            [1, 1, 10, -2, 1], [2, 1, 10, 20, 100],
        ], columns=['id', 'horizon_days', 'origin_cell_1',
                    'destination_cell_1', 'pair_count'])

    def test_counts_holdout_and_unsupported_absorbing_states(self):
        m = api('markov')
        op = m.fit_operator(self.counts(), {1}, [10, 20], 1)
        p, u = m.forecast(op, 10, 1)
        self.assertEqual(p, {10: .5, 20: .25, -2: .25})
        self.assertEqual(u, 0)
        p, u = m.forecast(op, 10, 2)
        self.assertEqual(p, {10: .25, 20: .125, -2: .375})
        self.assertEqual(u, .25)
        self.assertEqual(m.forecast(op, 20, 30), ({}, 1.0))
        self.assertEqual(m.forecast(op, -2, 30), ({-2: 1.0}, 0.0))
        self.assertEqual(op.training_ids, frozenset({1}))

    def test_two_step_hand_calculation(self):
        m = api('markov')
        counts = pd.DataFrame([[1, 1, 10, 10, 7], [1, 1, 10, 20, 3],
                               [1, 1, 20, 10, 2], [1, 1, 20, 20, 8]],
                              columns=self.counts().columns)
        op = m.fit_operator(counts, {1}, [10, 20], 1)
        p, u = m.forecast(op, 10, 2)
        np.testing.assert_allclose([p[10], p[20], u], [.55, .45, 0], atol=1e-14)

    def test_exact_remainder_and_missing_remainder(self):
        m = api('markov')
        columns = self.counts().columns
        long = pd.DataFrame([[1, 5, 10, 10, 1]], columns=columns)
        short = pd.DataFrame([[1, 2, 10, 20, 1]], columns=columns)
        op = m.fit_operator(long, {1}, [10, 20], 5)
        rem = m.fit_operator(short, {1}, [10, 20], 2)
        self.assertEqual(m.forecast(op, 10, 7, remainder=rem), ({20: 1.0}, 0.0))
        with self.assertRaises(ValueError):
            m.forecast(op, 10, 7)

    def test_invalid_counts_and_forecast_requests_rejected(self):
        m = api('markov')
        for field, value in [('pair_count', -1), ('destination_cell_1', -1),
                             ('origin_cell_1', 999), ('pair_count', 1.5)]:
            bad = self.counts().copy()
            bad[field] = bad[field].astype(float)
            bad.loc[0, field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                m.fit_operator(bad, {1}, [10, 20], 1)
        op = m.fit_operator(self.counts(), {1}, [10, 20], 1)
        for days in [0, 1.5, 366, True]:
            with self.subTest(days=days), self.assertRaises(ValueError):
                m.forecast(op, 10, days)
        with self.assertRaises(ValueError):
            m.forecast(op, 999, 1)

    def test_nine_branch_absorption_roundoff_remains_scoreable(self):
        m = api('markov')
        from data3001.modelling.evaluate import score_distribution
        columns = self.counts().columns
        for outside in (False, True):
            rows = [[1, 1, 10, c, 1] for c in range(11, 20)]
            if outside:
                rows += [[1, 1, c, -2, 1] for c in range(11, 20)]
            op = m.fit_operator(pd.DataFrame(rows, columns=columns), {1}, range(10, 20), 1)
            p, u = m.forecast(op, 10, 7)
            self.assertLessEqual(u, 1)
            self.assertTrue(all(v <= 1 for v in p.values()))
            score_distribution(p, 10, unresolved=u)


class SpatialScoreTests(unittest.TestCase):
    def test_brier_is_probability_sensitive_not_zero_one(self):
        m = api('markov_scoring')
        a = m.score_distribution({1: .1, 2: .8, 3: .1}, 2)
        b = m.score_distribution({1: .4, 2: .5, 3: .1}, 2)
        self.assertAlmostEqual(a['brier'], .06)
        self.assertAlmostEqual(b['brier'], .42)

    def test_point_forecast_linear_and_quadratic_distance(self):
        m = api('markov_scoring')
        scorer = m.SpatialScorer([10, 20], np.array([[0., 0., 0.], [100., 0., 0.]]))
        result = scorer.score({10: 1.0}, 20, unresolved=0)
        self.assertEqual(result['spatial_status'], 'complete_in_domain')
        self.assertAlmostEqual(result['energy_km'], 100)
        self.assertAlmostEqual(result['mean_squared_km2'], 10000)
        self.assertAlmostEqual(result['linear_quadratic_reference'], 2)

    def test_correct_two_branches_beats_false_centre_in_expectation(self):
        m = api('markov_scoring')
        scorer = m.SpatialScorer([10, 20, 30], np.array([[-100., 0., 0.], [0., 0., 0.], [100., 0., 0.]]))
        correct = sum(scorer.score({10: .5, 30: .5}, y, unresolved=0)
                      ['linear_quadratic_reference'] / 2 for y in [10, 30])
        centre = sum(scorer.score({20: 1.0}, y, unresolved=0)
                     ['linear_quadratic_reference'] / 2 for y in [10, 30])
        self.assertAlmostEqual(correct, 1.5)
        self.assertAlmostEqual(centre, 2)
        self.assertLess(correct, centre)

    def test_outside_and_unresolved_are_never_assigned_coordinates(self):
        m = api('markov_scoring')
        scorer = m.SpatialScorer([10, 20], np.array([[0., 0., 0.], [100., 0., 0.]]))
        for p, y, u, status in [({10: .4}, 20, .6, 'unresolved_forecast'),
                                ({10: .4, -2: .6}, -2, 0, 'outside_truth'),
                                ({-2: 1.0}, 20, 0, 'zero_in_domain_mass')]:
            result = scorer.score(p, y, unresolved=u)
            self.assertEqual(result['spatial_status'], status)
            self.assertTrue(np.isnan(result['linear_quadratic_reference']))
        result = scorer.score({10: .25, -2: .75}, 20, unresolved=0)
        self.assertAlmostEqual(result['energy_km'], 100)
        self.assertAlmostEqual(result['in_domain_mass'], .25)

    def test_quadratic_term_does_not_identify_spread_at_same_mean(self):
        m = api('markov_scoring')
        scorer = m.SpatialScorer([10, 20, 30], np.array([[-100., 0., 0.], [0., 0., 0.], [100., 0., 0.]]))
        spread = scorer.score({10: .5, 30: .5}, 30, unresolved=0)
        centre = scorer.score({20: 1.0}, 30, unresolved=0)
        self.assertEqual(spread['mean_squared_km2'], centre['mean_squared_km2'])
        self.assertNotEqual(spread['energy_km'], centre['energy_km'])

    def test_invalid_spatial_inputs_rejected(self):
        m = api('markov_scoring')
        with self.assertRaises(ValueError):
            m.SpatialScorer([10, 10], np.zeros((2, 3)))
        with self.assertRaises(ValueError):
            m.SpatialScorer([10], np.zeros((1, 3)), scale_km=0)


if __name__ == '__main__':
    unittest.main()
