"""Held-out end-to-end fixtures, independent of any real trajectory."""
import importlib
import importlib.util
import unittest

import numpy as np
import pandas as pd

from data3001.modelling.markov_scoring import SpatialScorer


def api():
    name = 'data3001.modelling.run_markov'
    if importlib.util.find_spec(name) is None:
        raise AssertionError('Required guarded M1 runner is absent')
    return importlib.import_module(name)


class RunTests(unittest.TestCase):
    def fixture(self):
        cols = ['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1', 'pair_count']
        transitions = pd.DataFrame([[1, 1, 10, 10, 7], [1, 1, 10, 20, 3],
                                     [1, 1, 20, 10, 2], [1, 1, 20, 20, 8],
                                     [2, 1, 10, 10, 100000]], columns=cols)
        releases = pd.DataFrame([[1, 7, 10, 10, 2], [1, 30, 10, 10, 2],
                                [2, 7, 10, 20, 1], [2, 30, 10, 20, 1]], columns=cols)
        scorer = SpatialScorer([10, 20], np.array([[0., 0., 0.], [100., 0., 0.]]))
        return transitions, releases, scorer

    def test_unseen_id_forecasts_and_scores_are_independently_correct(self):
        m = api()
        transitions, releases, scorer = self.fixture()
        result = m.evaluate_fold(transitions, releases, {1}, {2}, [10, 20], scorer, outer_fold=0)
        scores = result['scores']
        self.assertEqual(set(scores.model), {'B0', 'B1', 'B2', 'M1'})
        self.assertEqual(set(scores.id), {2})
        row = scores.loc[scores.model.eq('M1') & scores.horizon_days.eq(7)].iloc[0]
        pa = .4 + .6 * .5**7
        self.assertAlmostEqual(row.true_probability, 1-pa)
        self.assertAlmostEqual(row.brier_failure_penalized, 2*pa**2)
        self.assertTrue(scores.spatial_common.all())
        self.assertTrue(scores.loc[scores.model.ne('M1'), 'brier_failure_penalized'].eq(2).all())
        summary = m.summarize(scores)
        self.assertEqual(len(summary), 8)
        self.assertTrue(summary.eligible_pairs.eq(1).all())

    def test_fit_and_evaluation_id_overlap_is_rejected(self):
        m = api()
        transitions, releases, scorer = self.fixture()
        with self.assertRaises(ValueError):
            m.evaluate_fold(transitions, releases, {1, 2}, {2}, [10, 20], scorer, outer_fold=0)

    def test_all_unresolved_forecast_roundtrips_through_export(self):
        m = api()
        self.assertTrue(hasattr(m, 'forecast_table'), 'Missing complete forecast exporter')
        predictions = {0: {(7, 10, 'M1'): ({}, 1.0),
                           (30, 10, 'M1'): ({10: .3, -2: .2}, .5)}}
        table = m.forecast_table(predictions)
        for (h, origin, model), (expected_p, expected_u) in predictions[0].items():
            subset = table.loc[table.horizon_days.eq(h)]
            p = dict(zip(subset.loc[subset.destination_cell_1.ne(-3), 'destination_cell_1'],
                         subset.loc[subset.destination_cell_1.ne(-3), 'probability']))
            u = float(subset.loc[subset.destination_cell_1.eq(-3), 'probability'].sum())
            self.assertEqual(p, expected_p)
            self.assertEqual(u, expected_u)
            self.assertAlmostEqual(subset.probability.sum(), 1)


if __name__ == '__main__':
    unittest.main()
