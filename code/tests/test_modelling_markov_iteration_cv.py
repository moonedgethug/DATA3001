import unittest
import numpy as np
import pandas as pd
from data3001.modelling.markov_iteration_cv import combine_roles,select_search,seed_for,score_stratified_grid


class IterationCVTests(unittest.TestCase):
    def test_MC_covariance_cannot_be_reused_after_a_different_refinement_call(self):
        from types import SimpleNamespace
        from data3001.modelling.markov_iteration_cv import pair_MC_se
        a={'m':64,'call':1,'variance':.01,'row':SimpleNamespace(candidate=0)}
        b={'m':64,'call':2,'variance':.01,'row':SimpleNamespace(candidate=1)}
        self.assertAlmostEqual(pair_MC_se(a,b,{(1,0,1):.01}),.2)
        a['call']=2
        self.assertAlmostEqual(pair_MC_se(a,b,{(2,0,1):.005}),.1)
        a['m']=32
        self.assertAlmostEqual(pair_MC_se(a,b,{(2,0,1):.01}),np.sqrt(.02))

    def table(self,delta=0):
        t=pd.DataFrame({'candidate':[0,1,2],'path':['D1','D7','D5'],'lambda_value':[0,.2,.3],
            'case_count':[10]*3,'loss_sum_0':[9,8+delta,10],'loss_sum_1':[9,8+delta,10]})
        t['S']=(t.loss_sum_0+t.loss_sum_1)/(2*t.case_count);return t

    def test_every_candidate_and_case_survives_role_aggregation(self):
        t,g=combine_roles([(self.table(),np.zeros((3,3))),(self.table(1),np.zeros((3,3)))])
        self.assertTrue(t.case_count.eq(20).all());self.assertAlmostEqual(t.S.iloc[1],.85)
        with self.assertRaises(ValueError):combine_roles([(self.table().iloc[:2],np.zeros((2,2))),(self.table(),np.zeros((3,3)))])

    def test_lambda_CV_selection_does_not_accept_a_manual_shortlist(self):
        x=self.table();grid=list(zip(x.path,x.lambda_value));calls=[]
        def evaluator(indices,m):
            calls.append((indices,m));t=x.iloc[indices].reset_index(drop=True)
            return t,np.zeros((len(indices),len(indices)))
        result,history=select_search(evaluator,grid)
        self.assertEqual(calls[0],([0,1,2],32));self.assertEqual(result['candidate'],1)
        self.assertEqual(result['lambda_value'],.2)

    def test_seed_is_structured_reproducible_and_role_separated(self):
        a=seed_for('outer_0_inner_1',300534067902500,41,0,32)
        self.assertEqual(a,seed_for('outer_0_inner_1',300534067902500,41,0,32))
        self.assertNotEqual(a,seed_for('outer_1_inner_1',300534067902500,41,0,32))
        self.assertNotEqual(a,seed_for('outer_0_inner_1',300534067902500,41,1,32))

    def test_all99_targets_same_cases_and_serial_thread_identity(self):
        from shapely.geometry import box
        from data3001.modelling.markov_position import OBS_DTYPE,fit_pool
        from data3001.preprocessing.prep_core import cells
        from data3001.modelling.neighbourhood import EndpointMapper
        a=np.zeros(171,dtype=OBS_DTYPE);a['id'][:169]=1;a['id'][169:]=[2,3]
        a['lon']=-75.5;a['lat']=33.2;a['time'][:169]=np.arange(169)*3600
        a['source_obs']=np.arange(len(a));a['cell']=cells(a['lon'],a['lat']);bins=np.full(len(a),8,dtype='int8')
        pools={h:fit_pool(a,np.array([0]),np.array([h*24]),bins,{1},h) for h in [1,2,3,5,7]}
        p=pd.DataFrame({'id':[2,3],'origin_source_obs':[169,170],'origin':[169,170],
            'origin_cell_1':a['cell'][169:],'origin_velocity_bin':[8,8],'destination_cell_1':a['cell'][169:]})
        mapper=EndpointMapper(box(-81,20,-8,55));outputs=[]
        for workers in [1,2]:
            outputs.append(score_stratified_grid(pools,a,bins,p,list(range(99)),32,mapper,'fixture',
                workers=workers,batch_size=1,diagnostic_lambda=.2,progress=lambda *a,**kw:None))
        pd.testing.assert_frame_equal(outputs[0][0],outputs[1][0]);np.testing.assert_array_equal(outputs[0][1],outputs[1][1])
        self.assertEqual(len(outputs[0][0]),99);self.assertTrue(outputs[0][0].case_count.eq(2).all())
        self.assertTrue((outputs[0][0].S.abs()<1e-12).all());self.assertEqual(len(outputs[0][3]),9)
        self.assertTrue(outputs[0][2].groupby('candidate').case_count.sum().eq(2).all())
        with self.assertRaises(ValueError):score_stratified_grid(pools,a,bins,p.assign(id=1),[0],32,mapper,'bad')


if __name__=='__main__':unittest.main()
