import unittest
import pandas as pd
import numpy as np

from data3001.modelling.run_markov_position import choices_for_fold, match_reference, validate_settings, particles_for_level


class PositionRunTests(unittest.TestCase):
    def test_original_parameters_are_required_not_reselected(self):
        t=pd.DataFrame([[0,'M1vcat-selected',7,3,.1],[0,'M1vcat-selected',30,7,.2]],
             columns=['outer_fold','model','horizon_days','lag_days','lambda_value'])
        self.assertEqual(choices_for_fold(t,0),{7:(3,.1),30:(7,.2)})
        with self.assertRaises(ValueError):choices_for_fold(pd.concat([t,t]),0)
        with self.assertRaises(ValueError):choices_for_fold(t.iloc[:1],0)

    def test_reference_join_preserves_all_hourly_cases(self):
        p=pd.DataFrame({'id':[1,1], 'horizon_days':[7,7],'origin_cell_1':[43000]*2,
            'origin_velocity_bin':[8]*2,'destination_cell_1':[43001]*2,'origin':[0,1]})
        r=p.iloc[:1].drop(columns='origin').assign(pair_count=2,brier_failure_penalized=.8)
        out=match_reference(p,r)
        self.assertEqual(len(out),2);self.assertTrue(out.old_S.eq(.8).all())
        with self.assertRaises(ValueError):match_reference(p,r.assign(pair_count=3))
        with self.assertRaises(ValueError):match_reference(p,r.assign(destination_cell_1=43002))

    def test_config_rejects_expanded_scope(self):
        from pathlib import Path
        import json
        c=json.loads((Path(__file__).resolve().parents[1]/'configs/markov_m1_position.json').read_text())
        validate_settings(c)
        with self.assertRaises(ValueError):validate_settings({**c,'departure_seasons':'quarterly'})
        with self.assertRaises(ValueError):validate_settings({**c,'final_test_access':True})

    def test_integration_resolution_is_not_hyperparameter_retuning(self):
        self.assertEqual([particles_for_level(i) for i in range(3)],[32,64,128])
        for invalid in [-1,3,True,.5]:
            with self.assertRaises(ValueError):particles_for_level(invalid)


if __name__=='__main__':unittest.main()
