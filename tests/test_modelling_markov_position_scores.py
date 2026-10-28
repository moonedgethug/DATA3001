import itertools
import unittest

import numpy as np

from data3001.modelling.markov_position_scores import ensemble_scores, validate_comparison, aggregate_scores, summarize_scores


class PositionScoreTests(unittest.TestCase):
    def test_collision_score_is_unbiased_for_original_S(self):
        p={43000:.6,43001:.3,-3:.1};states=list(p)
        values=[];weights=[]
        for draw in itertools.product(states,repeat=3):
            score=ensemble_scores(np.array([draw]),np.array([43001]))
            values.append(score.S_integration.iloc[0]);weights.append(np.prod([p[x] for x in draw]))
        self.assertAlmostEqual(np.dot(values,weights),1-2*.3+sum(v*v for v in p.values()))

    def test_issued_score_and_absorbing_mass_are_not_renormalized(self):
        s=ensemble_scores(np.array([[43000,43000,-2,-3]]),np.array([43000])).iloc[0]
        self.assertAlmostEqual(s.S_issued,.375)
        self.assertAlmostEqual(s.S_integration,1/6)
        self.assertEqual(s.U_mass,.25);self.assertEqual(s.E_mass,.25)
        self.assertFalse(s.region90_available);self.assertTrue(np.isnan(s.energy_km_issued))

    def test_ties_and_observed_endpoint(self):
        s=ensemble_scores(np.array([[43000,43001,43002,43002]]),np.array([43001])).iloc[0]
        self.assertTrue(s.region90_hit);self.assertEqual(s.region90_cells,3)
        self.assertEqual(s.sampled_zero,False)
        with self.assertRaises(ValueError):ensemble_scores(np.array([[43000,-1]]),np.array([43000]))

    def test_comparison_rejects_retuning_and_overlapping_ids(self):
        record={'fitting_ids':[1,2],'threshold_m_s':.2}
        validate_comparison(record,{1,2},{3},3,.2)
        with self.assertRaises(ValueError):validate_comparison(record,{1,2},{2},3,.2)
        with self.assertRaises(ValueError):validate_comparison(record,{1},{3},3,.2)
        with self.assertRaises(ValueError):validate_comparison(record,{1,2},{3},4,.2)

    def test_unavailable_original_diagnostics_remain_NA(self):
        f=ensemble_scores(np.array([[43000,43001]]),np.array([43000]))
        for key in f.columns:
            if key not in ['S_integration','S_issued']:f[key]=np.nan
        f=f.assign(id=1,outer_fold=0,horizon_days=7,repeat=0,model='old-exact')
        summary=summarize_scores(aggregate_scores(f))
        for key in ['U_mass','E_mass','region90_hit','region90_available']:
            self.assertTrue(np.isnan(summary[key].iloc[0]),key)


if __name__=='__main__':unittest.main()
