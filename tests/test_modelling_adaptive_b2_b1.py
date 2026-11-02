import subprocess
import sys
import unittest

import numpy as np
import pandas as pd

from data3001.modelling.baselines.adaptive_b2_b1 import (
    GRID, borrowing_weight, candidate_scores, coefficient_rows, evaluate, fit_bases,
    forecasts, paired_bootstrap, select_parameters, summarize_scores,
)


def fixture():
    rows = []
    for h in (7, 30):
        rows += [[1, h, 10, 10, 1], [1, h, 10, 20, 3], [2, h, 20, 10, 12],
                 [3, h, 10, 20, 2], [3, h, 30, 20, 1]]
    return pd.DataFrame(rows, columns=['id','horizon_days','origin_cell_1','destination_cell_1','pair_count'])


class AdaptiveTests(unittest.TestCase):
    def base(self):
        return fit_bases(fixture(), [1, 2], [10, 20, 30], [-2, 10, 20, 30])

    def test_reference_and_median_come_only_from_fitting_ids(self):
        base = self.base()
        np.testing.assert_allclose(base.references[7], [0, 13/16, 3/16, 0])
        self.assertEqual(base.medians[7], 8)
        modified = fixture(); modified.loc[modified.id.eq(3), 'pair_count'] *= 10000
        other = fit_bases(modified, [1, 2], [10, 20, 30], [-2, 10, 20, 30])
        np.testing.assert_array_equal(base.references[7], other.references[7])
        self.assertEqual(other.medians, base.medians)

    def test_weight_endpoints_median_and_monotonicity(self):
        self.assertEqual(borrowing_weight('Adaptive', 0, 4, 8), 0)
        self.assertEqual(borrowing_weight('Adaptive', 1, 4, 8), 1)
        self.assertEqual(borrowing_weight('Adaptive', .5, 8, 8), .5)
        self.assertAlmostEqual(borrowing_weight('Adaptive', .5, 4, 8), 2/3)
        self.assertGreater(borrowing_weight('Adaptive', .5, 4, 8), borrowing_weight('Adaptive', .5, 12, 8))

    def test_hand_computed_blend_and_shared_unsupported_mask(self):
        base = self.base()
        p, support = forecasts(base, 'Fixed', {7:.5,30:.5})
        np.testing.assert_allclose(p[(7,10)], [0, .53125, .46875, 0])
        for family in ('B2','Fixed','Adaptive'):
            v, _ = forecasts(base, family, {7:1,30:1})
            self.assertNotIn((7,30), v)
            scores, _ = evaluate(base, v, fixture(), [3], family)
            self.assertTrue(scores.loc[scores.origin_cell_1.eq(30), 'brier'].isna().all())
            if family != 'B2':
                np.testing.assert_array_equal(v[(7,10)], base.references[7])

    def test_candidate_scores_match_direct_scoring_for_entire_grid(self):
        base = self.base()
        candidates = candidate_scores(coefficient_rows(base, fixture(), [3]))
        for c in candidates.itertuples(index=False):
            vectors, _ = forecasts(base, c.model, {7:c.parameter_a,30:c.parameter_a})
            p = vectors[(c.horizon_days,10)]
            truth = np.array([0,0,1,0])
            expected = 2*np.square(p-truth).sum()
            self.assertAlmostEqual(c.score_sum, expected)
            self.assertEqual(c.evaluable_pairs, 2)
            self.assertEqual(c.eligible_pairs, 3)
        selected, _ = select_parameters(candidates)
        self.assertTrue(selected.parameter_a.eq(0).all())

    def test_ties_prefer_no_borrowing(self):
        rows = []
        for h in (7,30):
            for family in ('Fixed','Adaptive'):
                for a in GRID:
                    rows.append(dict(horizon_days=h,model=family,parameter_a=a,
                                     score_sum=1.,eligible_pairs=2,evaluable_pairs=2))
        selected, _ = select_parameters(pd.DataFrame(rows))
        self.assertTrue(selected.parameter_a.eq(0).all())

    def test_whole_id_exclusion_and_empty_horizon(self):
        base = self.base()
        with self.assertRaises(ValueError):
            coefficient_rows(base, fixture(), [1,3])
        with self.assertRaises(ValueError):
            fit_bases(fixture().query('horizon_days == 7'), [1,2], [10,20,30], [-2,10,20,30])

    def test_summary_and_paired_bootstrap_preserve_clusters(self):
        base = self.base(); parts=[]
        for family in ('B2','Fixed','Adaptive'):
            v,_=forecasts(base,family,{7:0,30:0})
            s,_=evaluate(base,v,fixture(),[3],family); parts.append(s)
        scores=pd.concat(parts,ignore_index=True)
        summary=summarize_scores(scores)
        self.assertTrue(summary.evaluable_pairs.eq(2).all())
        self.assertTrue(summary.unsupported_pairs.eq(1).all())
        draws, intervals, diffs=paired_bootstrap(scores,[3,4],seed=42)
        draws2,_,_=paired_bootstrap(scores,[3,4],seed=42)
        pd.testing.assert_frame_equal(draws,draws2)
        self.assertTrue(diffs.difference.eq(0).all())
        self.assertTrue(diffs.lower_95.eq(0).all())
        self.assertGreater(intervals.undefined_replicates.sum(),0)

    def test_import_isolated_from_other_models_and_runners(self):
        code='''
import sys
import data3001.modelling.baselines.adaptive_b2_b1
assert not any('run_empirical_b2' in n or 'markov_models' in n or 'continuous_models' in n or n == 'torch' for n in sys.modules)
'''
        subprocess.run([sys.executable,'-B','-c',code],check=True,capture_output=True)

    def test_config_locks_science_and_runner_stays_isolated(self):
        import json
        from pathlib import Path
        from data3001.modelling.baselines.run_adaptive_b2_b1 import validate_config
        config=json.loads((Path(__file__).resolve().parents[1]/'configs/adaptive_b2_b1.json').read_text())
        validate_config(config)
        for key,value in [('target','endpoint'),('primary_metric','brier_failure_penalized'),
                          ('adaptive_support','unique_ids'),('final_test_access',True),('region_level',.8)]:
            with self.assertRaises(ValueError):
                validate_config({**config,key:value})
        code='''
import sys
import data3001.modelling.baselines.run_adaptive_b2_b1
assert not any('run_empirical_b2' in n or 'markov_models' in n or 'continuous_models' in n or n == 'torch' for n in sys.modules)
'''
        subprocess.run([sys.executable,'-B','-c',code],check=True,capture_output=True)


if __name__ == '__main__':
    unittest.main()
