"""Independent fixtures for categorical velocity; no real trajectory reads."""
import importlib
import unittest

import numpy as np
import pandas as pd

from data3001.modelling.markov import fit_operator, forecast


def api():
    return importlib.import_module('data3001.modelling.markov_velocity')


COLS = ['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1',
        'origin_atom', 'destination_atom', 'pair_count']


class VelocityTests(unittest.TestCase):
    def test_zero_quadrants_axes_threshold_and_extreme(self):
        m = api()
        u = np.array([0., -1., 1., -1., 1., 0., .5, 20.])
        v = np.array([0., -1., -1., 1., 1., 1., 0., 0.])
        atoms = m.velocity_atoms(u, v, [.5])
        bins = m.coarse_velocity(atoms, [.5], .5)
        np.testing.assert_array_equal(bins, [0, 2, 4, 6, 8, 8, 7, 8])
        with self.assertRaises(ValueError):
            m.velocity_atoms([np.nan], [1.], [.5])

    def test_extra_cache_cuts_cannot_change_a_fit(self):
        m = api()
        u = np.array([0., -.1, .25, .5, .50001, 1.])
        v = np.array([0., .1, 0., 0., 0., -1.])
        a = m.coarse_velocity(m.velocity_atoms(u, v, [.5]), [.5], .5)
        b = m.coarse_velocity(m.velocity_atoms(u, v, [.05, .2, .5, 2.]), [.05, .2, .5, 2.], .5)
        np.testing.assert_array_equal(a, b)

    def fixture(self):
        return pd.DataFrame([
            [1, 1, 10, 10, 1, 1, 2], [1, 1, 10, 20, 1, 8, 1],
            [1, 1, 10, -2, 1, -2, 1], [1, 1, 10, 20, 8, 8, 4],
            [1, 1, 20, 10, 8, 1, 1],
            [2, 1, 10, 20, 1, 8, 100],
        ], columns=COLS)

    def test_counts_marginalise_and_holdout_ids_do_not_fit(self):
        m = api(); counts = self.fixture()
        coarse = m.coarse_counts(counts, [.5], .5)
        keys = ['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1']
        pd.testing.assert_series_equal(counts.groupby(keys).pair_count.sum(),
                                       coarse.groupby(keys).pair_count.sum())
        op = m.fit_joint_operator(counts, {1}, [10, 20, 30], [.5], .5, 1)
        self.assertEqual(op.training_ids, frozenset({1}))
        self.assertEqual(op.row_pairs[1], 4)

    def test_lambda_one_exactly_restores_old_operator_and_remainders(self):
        m = api(); counts = self.fixture()
        keys = ['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1']
        plain = counts.groupby(keys, as_index=False).pair_count.sum()
        op = m.fit_joint_operator(counts, {1}, [10, 20, 30], [.5], .5, 1)
        old = fit_operator(plain, {1}, [10, 20, 30], 1)
        for h in [1, 2, 7, 30]:
            fresh = m.location_forecasts(op, [(10, 1), (10, 8), (20, 0), (30, 8)], h, 1.)
            for (p, u), cell in zip(fresh, [10, 10, 20, 30]):
                p0, u0 = forecast(old, cell, h)
                np.testing.assert_allclose([p.get(c, 0.) for c in [10, 20, 30, -2]]+[u],
                                           [p0.get(c, 0.) for c in [10, 20, 30, -2]]+[u0], atol=1e-12)
        long = counts.assign(horizon_days=5)
        short = counts.assign(horizon_days=2)
        lop = m.fit_joint_operator(long, {1}, [10, 20, 30], [.5], .5, 5)
        sop = m.fit_joint_operator(short, {1}, [10, 20, 30], [.5], .5, 2)
        p, u = m.location_forecasts(lop, [(10, 1)], 7, 1., sop)[0]
        p0, u0 = forecast(fit_operator(long.groupby(keys, as_index=False).pair_count.sum(), {1}, [10, 20, 30], 5),
                          10, 7, fit_operator(short.groupby(keys, as_index=False).pair_count.sum(), {1}, [10, 20, 30], 2))
        np.testing.assert_allclose([p.get(c, 0.) for c in [10, 20, -2]]+[u],
                                   [p0.get(c, 0.) for c in [10, 20, -2]]+[u0], atol=1e-12)

    def test_conditional_row_backoff_and_absorption(self):
        m = api(); op = m.fit_joint_operator(self.fixture(), {1}, [10, 20, 30], [.5], .5, 1)
        p, u = m.location_forecasts(op, [(10, 0)], 1, 0.)[0]
        np.testing.assert_allclose([p[10], p[20], p[-2], u], [.25, .625, .125, 0.])
        self.assertEqual(m.location_forecasts(op, [(30, 0)], 30, .4), [({}, 1.)])
        matrix = op.matrix(.4)
        self.assertEqual(matrix[-2, -2], 1.)
        self.assertEqual(matrix[-1, -1], 1.)
        np.testing.assert_allclose(np.asarray(matrix.sum(axis=1)).ravel(), 1, atol=1e-12)

    def test_two_step_velocity_memory_is_not_discarded(self):
        m = api()
        # Both histories first reach cell 20, but retain different velocity.
        counts = pd.DataFrame([[1, 1, 10, 20, 1, 1, 1], [1, 1, 10, 20, 8, 8, 1],
                               [1, 1, 20, 10, 1, 1, 1], [1, 1, 20, 30, 8, 8, 1]], columns=COLS)
        op = m.fit_joint_operator(counts, {1}, [10, 20, 30], [.5], .5, 1)
        self.assertEqual(m.location_forecasts(op, [(10, 1), (10, 8)], 2, 0.),
                         [({10: 1.}, 0.), ({30: 1.}, 0.)])

    def test_invalid_lambda_remainder_or_bin_map_rejected(self):
        m = api(); op = m.fit_joint_operator(self.fixture(), {1}, [10, 20], [.5], .5, 1)
        for lam in [-.1, 1.1, np.nan]:
            with self.assertRaises(ValueError): m.location_forecasts(op, [(10, 1)], 7, lam)
        with self.assertRaises(ValueError): m.location_forecasts(op, [(10, 9)], 1, .5)
        with self.assertRaises(ValueError): m.coarse_velocity([1], [.5], .4)
        long = m.fit_joint_operator(self.fixture().assign(horizon_days=5), {1}, [10, 20], [.5], .5, 5)
        with self.assertRaises(ValueError): m.location_forecasts(long, [(10, 1)], 7, .5)


if __name__ == '__main__':
    unittest.main()
