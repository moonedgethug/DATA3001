"""Regression checks for E7 reporting on the production score schema."""
import unittest
import numpy as np
import pandas as pd

from data3001.modelling.baselines.exact_origin_s4_e7 import probability_summary
from data3001.modelling.baselines.exact_origin_s4_e7_report import evaluate, METRICS


def check_boolean_exit_region_flags_keep_signed_paired_changes_and_shared_id_draws():
    # ID 10 occurs in both origins; unequal observation counts require the
    # established equal-time, equal-ID, equal-origin evaluation hierarchy.
    ids = [10, 10, 20, 10, 30, 30, 30]
    origins = [100, 100, 100, 200, 200, 200, 200]
    weight = np.array([1 / 8, 1 / 8, 1 / 4, 1 / 4, 1 / 12, 1 / 12, 1 / 12])
    truth = np.array([-2, 10, 11, -2, 10, 11, 10])
    annual = np.array([[.95, .03, .02], [.02, .90, .08], [.02, .90, .08],
                       [.95, .03, .02], [.15, .70, .15], [.05, .20, .75], [.10, .80, .10]])
    exact = np.array([[.02, .90, .08], [.20, .70, .10], [.05, .15, .80],
                      [.70, .20, .10], [.05, .90, .05], [.20, .70, .10], [.15, .80, .05]])
    rows = []
    for resolution in [1., .5]:
        states = np.array([-2, 10, 11]) if resolution == 1. else np.array([-2, 20, 22])
        areas = dict(zip(states, [0., 10000. * resolution ** 2, 12000. * resolution ** 2]))
        for index, ident in enumerate(ids):
            outcome = int(truth[index] if resolution == 1. or truth[index] == -2 else truth[index] * 2)
            row = dict(id=ident, origin_source_obs=index, horizon_days=7, origin_cell_1=origins[index],
                       resolution=resolution, weight=weight[index], observed_exit=outcome == -2)
            for name, probabilities in [('Annual', annual[index]), ('Exact', exact[index])]:
                score = probability_summary(states, probabilities, outcome, areas)
                row.update({name + '_' + metric: score[metric] for metric in METRICS})
            rows.append(row)
    cases = pd.DataFrame(rows)
    assert cases.Annual_exit_in_region.dtype == bool
    assert cases.Exact_exit_in_region.dtype == bool
    cfg = {'bootstrap_seed': 20261105, 'bootstrap_draws': 128}
    tables, multipliers, draws, returned_ids = evaluate(cases, cfg)
    assert returned_ids == [10, 20, 30]
    assert draws.shape == (2, 128, len(METRICS))
    expected_rng = np.random.Generator(np.random.PCG64(cfg['bootstrap_seed'])).exponential(size=(128, 3))
    np.testing.assert_array_equal(multipliers, expected_rng)
    assert set(zip(tables['summary'].resolution, tables['summary'].model)) == {
        (1., 'Annual'), (1., 'Exact'), (.5, 'Annual'), (.5, 'Exact')}
    for resolution in [1., .5]:
        group = cases[cases.resolution.eq(resolution)]
        exit_difference = (group.Exact_exit_in_region.to_numpy(dtype=float)
                           - group.Annual_exit_in_region.to_numpy(dtype=float))
        assert -1 in exit_difference and 1 in exit_difference
        paired = tables['paired'][tables['paired'].resolution.eq(resolution)].iloc[0]
        np.testing.assert_allclose(paired.delta_exit_in_region, weight @ exit_difference, atol=1e-12, rtol=0)
        for model in ['Annual', 'Exact']:
            summary = tables['summary'][tables['summary'].resolution.eq(resolution)
                                         & tables['summary'].model.eq(model)].iloc[0]
            expected = weight @ group[[model + '_' + metric for metric in METRICS]].to_numpy(dtype=float)
            np.testing.assert_allclose(summary[list(METRICS)].to_numpy(dtype=float), expected, atol=1e-12, rtol=0)
    # Identical exit patterns at both resolutions use the same ID draw, not
    # independent resampling merely because the output grid changes.
    metric = METRICS.index('exit_in_region')
    np.testing.assert_array_equal(draws[0, :, metric], draws[1, :, metric])


class ReportRegressionTests(unittest.TestCase):
    def test_boolean_exit_region_flags_and_shared_id_draws(self):
        check_boolean_exit_region_flags_keep_signed_paired_changes_and_shared_id_draws()


if __name__ == '__main__':
    unittest.main()
