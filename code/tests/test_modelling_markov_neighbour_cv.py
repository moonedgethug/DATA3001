import unittest
import numpy as np
import pandas as pd


class NeighbourCVTests(unittest.TestCase):
    def test_inner_roles_pool_original_pairs_and_MC_variance_not_fold_means(self):
        from data3001.modelling.markov_neighbour_cv import combine
        a=pd.DataFrame({'candidate':[1],'path':['D7'],'alpha':[.1],'lambda_value':[.3],
                        'case_count':[2],'loss_sum_0':[1.],'loss_sum_1':[1.2],'repeat_diff_square':[.04]})
        b=a.copy();b[['case_count','loss_sum_0','loss_sum_1','repeat_diff_square']]=[8,6,6.4,.16]
        c=combine([a,b]).iloc[0]
        self.assertAlmostEqual(c.S,14.6/20);self.assertAlmostEqual(c.MC_SE,np.sqrt(.2)/20)

    def test_missing_or_changed_candidates_fail_instead_of_silent_partial_CV(self):
        from data3001.modelling.markov_neighbour_cv import combine
        a=pd.DataFrame({'candidate':[1],'path':['D7'],'alpha':[.1],'lambda_value':[.3],
                        'case_count':[2],'loss_sum_0':[1.],'loss_sum_1':[1.2],'repeat_diff_square':[.04]})
        b=a.copy();b['alpha']=.2
        with self.assertRaises(ValueError):combine([a,b])

    def test_new_configuration_has_joint_search_both_horizons_and_no_old_choices(self):
        from data3001.modelling.run_markov_neighbour import validate_settings
        import json
        from pathlib import Path
        c=json.loads((Path(__file__).parents[1]/'configs/markov_m1_neighbour.json').read_text())
        self.assertIs(validate_settings(c),c)
        for key,value in [('final_test_access',True),('predictors',['lon','lat','ve','vn','sst']),('alpha_grid',[.1]),('historical_optimum',True)]:
            bad={**c,key:value}
            with self.assertRaises(ValueError):validate_settings(bad)

    def test_profile_cannot_silently_cross_a_binary_config_or_input_change(self):
        from data3001.modelling.run_markov_neighbour import validate_profile
        bound={'config':'a','cpp':'b','library':'c','contract':'d'};sources={'core.py':'e'}
        meta={'input_sha256':bound.copy(),'source_sha256':sources.copy()}
        record={'scope':'fitting_only_dummy_outcome_runtime_and_precision_profile_not_CV','chosen_method':'uncentred'}
        validate_profile(meta,record,bound,sources)
        for key in bound:
            changed={**bound,key:'changed'}
            with self.assertRaises(ValueError):validate_profile(meta,record,changed,sources)
        for record in [{'scope':'scored_outer','chosen_method':'uncentred'},
                       {'scope':'fitting_only_dummy_outcome_runtime_and_precision_profile_not_CV','chosen_method':'lowest_S'}]:
            with self.assertRaises(ValueError):validate_profile(meta,record,bound,sources)

    def test_query_streams_are_invariant_to_batch_partition(self):
        from data3001.modelling.markov_neighbour_integration import query_seeds,uniform
        s=query_seeds('inner',np.array([1,2,3]),np.array([11,22,33]),0,'layout')
        whole=uniform(s,20,5).reshape(3,20)
        split=np.vstack([uniform(s[:1],20,5).reshape(1,20),uniform(s[1:],20,5).reshape(2,20)])
        np.testing.assert_array_equal(whole,split);self.assertEqual(len(np.unique(s)),3)

    def test_real_role_scoring_preserves_ID_counts_across_batch_sizes(self):
        from test_modelling_markov_neighbour import fixtures
        from data3001.modelling.markov_neighbour_cv import score_role
        from data3001.modelling.markov_neighbour import candidates
        p,m=fixtures();obs=p.obs
        part=pd.DataFrame({'id':[1,2],'origin_source_obs':[0,0],'origin':[0,25],
                           'destination_cell_1':obs['cell'][[0,25]]})
        ix=[i for i,(path,a,l) in enumerate(candidates(7)) if path=='D1' and a in [0,.5] and l==0]
        args=({1:p},obs,p.bins,part,7,ix,2,m,'profile',0)
        a,ids,_=score_role(*args,workers=1,batch_size=1,engineering_profile=True,progress=lambda *a,**k:None)
        b,ids2,_=score_role(*args,workers=2,batch_size=2,engineering_profile=True,progress=lambda *a,**k:None)
        pd.testing.assert_frame_equal(a,b);pd.testing.assert_frame_equal(ids,ids2)


if __name__=='__main__':unittest.main()
