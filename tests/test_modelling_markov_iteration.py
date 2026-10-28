import unittest
import numpy as np
import pandas as pd

from data3001.modelling.markov_iteration import (
    SCHEDULES,candidates,validate_schedule,fast_scores,forecast_schedule,
    candidate_statistics,near_best,choose_candidate,
)
from data3001.modelling.markov_position_scores import ensemble_scores


class IterationTests(unittest.TestCase):
    def test_grid_contains_every_route_lambda_without_pruning(self):
        self.assertEqual(len(SCHEDULES),9);self.assertEqual(len(candidates()),99)
        self.assertEqual(len({tuple(s) for s in SCHEDULES.values()}),9)
        for s in SCHEDULES.values():self.assertEqual(sum(validate_schedule(s)),30)
        self.assertNotEqual(SCHEDULES['D7'],SCHEDULES['R7'])
        for invalid in [[],[7]*4,[30],[1.5]*20,[True]*30,[0,30]]:
            with self.assertRaises(ValueError):validate_schedule(invalid)

    def test_vectorized_scores_equal_independent_existing_definition(self):
        rng=np.random.default_rng(71)
        for m in [16,32,64,128]:
            a=rng.choice([43000,43001,43002,-2,-3],(37,m));y=rng.choice([43000,43001,-2],37)
            fast=fast_scores(a,y);slow=ensemble_scores(a,y)
            for key in ['S_integration','S_issued','true_probability_issued','U_mass','E_mass']:
                np.testing.assert_allclose(fast[key],slow[key],rtol=0,atol=3e-16)
        with self.assertRaises(ValueError):fast_scores(np.array([[-1,43000]]),np.array([43000]))

    def test_arbitrary_sequence_order_is_preserved(self):
        from unittest.mock import patch
        from shapely.geometry import box
        from data3001.modelling.neighbourhood import EndpointMapper
        calls=[]
        def mock_step(pool,x,y,c,b,lam,u,v,mapper,precise):
            calls.append(pool);return c,x,y,b,{'active':len(c)}
        with patch('data3001.modelling.markov_iteration.step',side_effect=mock_step):
            a,stats=forecast_schedule({h:h for h in [1,2,3,5,7]},[-75.2],[33.2],[8],
                [2,7,7,7,7],.2,16,71,EndpointMapper(box(-81,20,-8,55)),precise=True)
        self.assertEqual(calls,[2,7,7,7,7]);self.assertEqual(a.shape,(1,16));self.assertEqual(stats['active'],80)

    def test_selection_uses_collision_score_and_requires_all_cases(self):
        grid=candidates()[:3];scores=np.zeros((3,2,5));scores[0]=.95;scores[1]=.9;scores[2]=1.1
        stats,gram=candidate_statistics(scores,grid)
        self.assertEqual(choose_candidate(stats,gram,False)['candidate'],1)
        self.assertEqual(near_best(stats,gram),[1])
        self.assertTrue(stats.case_count.eq(5).all())
        scores[0,0]=np.nan
        with self.assertRaises(ValueError):candidate_statistics(scores,grid)

    def test_MC_tie_is_labelled_not_claimed_unique(self):
        grid=[('D1',.2),('D7',.2),('D7',.5)]
        x=np.ones((3,2,5))*.9;stats,gram=candidate_statistics(x,grid)
        result=choose_candidate(stats,gram,True)
        self.assertTrue(result['numerically_unresolved']);self.assertEqual(result['path'],'D7')
        self.assertEqual(result['lambda_value'],.5)


if __name__=='__main__':unittest.main()
