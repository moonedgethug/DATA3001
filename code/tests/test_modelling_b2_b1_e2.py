import unittest
import json
import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd

from data3001.modelling.baselines.b2_b1_e2 import (
    allocation_reference, weight, specifications, candidate_metrics, select_parameters,
    forecasts, fit_bases, diagnostic_scores, paired_bootstrap, classify, TOL,
)


def counts_fixture():
    rows=[]
    for h in (7,30):
        rows += [[1,h,10,10,6],[1,h,10,-2,2],[2,h,20,20,10],[2,h,20,30,2],
                 [3,h,10,30,2],[3,h,10,40,1],[3,h,30,20,3]]
    return pd.DataFrame(rows,columns=['id','horizon_days','origin_cell_1','destination_cell_1','pair_count'])


class E2Tests(unittest.TestCase):
    def base(self):
        return fit_bases(counts_fixture(),[1,2],[10,20,30],[-2,10,20,30,40])

    def test_allocation_hand_example_preserves_exit_and_support(self):
        states=np.array([-2,10,20,30]); p=np.array([0.,1.,0.,0.]); q=np.array([.2,.3,.5,0.])
        out,z=allocation_reference(p,q,states,.5)
        self.assertAlmostEqual(z,.55)
        np.testing.assert_allclose(out,[.2,.8*.3/.55,.8*.25/.55,0.])
        np.testing.assert_array_equal(out>0,q>0)
        self.assertEqual(out[0],q[0]);self.assertAlmostEqual(out.sum(),1.)
        np.testing.assert_array_equal(allocation_reference(p,q,states,1)[0],q)

    def test_all_seen_all_unseen_and_only_exit(self):
        states=np.array([-2,10,20]);q=np.array([.1,.3,.6])
        for p in [np.array([0.,.5,.5]),np.array([1.,0.,0.])]:
            np.testing.assert_allclose(allocation_reference(p,q,states,2)[0],q)
        q=np.array([1.,0.,0.]);np.testing.assert_array_equal(allocation_reference(q,q,states,.5)[0],q)
        with self.assertRaises(ValueError):allocation_reference(q,q,states,0)

    def test_weight_identities_and_monotonicity(self):
        for beta in [0,.25,.5,.75,1]:
            self.assertEqual(weight(0,beta,3,10),0);self.assertEqual(weight(1,beta,3,10),1)
            self.assertAlmostEqual(weight(.4,beta,10,10),.4)
            self.assertGreaterEqual(weight(.4,beta,2,10),weight(.4,beta,20,10))
        self.assertEqual(weight(.4,0,1,10),.4)
        self.assertAlmostEqual(weight(.4,1,5,10),4/7)
        with self.assertRaises(ValueError):weight(.5,.5,0,10)

    def test_candidate_vectors_scores_regions_and_unseen_validation(self):
        base=self.base(); data=counts_fixture(); table=candidate_metrics(base,data,[3])
        self.assertEqual(len(specifications()),210);self.assertEqual(len(table),504)
        self.assertEqual(base.rows[(7,10)][base.index[30]],0)
        self.assertEqual(base.rows[(7,10)][base.index[40]],0)
        self.assertGreater(base.references[7][base.index[30]],0)
        for r in table.itertuples(index=False):
            selection=pd.DataFrame([dict(horizon_days=h,model=r.model,parameter_a=r.parameter_a,parameter_c=r.parameter_c,
                                         parameter_beta=r.parameter_beta,selection_status='test') for h in (7,30)])
            vectors,_=forecasts(base,r.model,selection)
            p=vectors[(r.horizon_days,10)]
            y1=np.zeros(5);y1[base.index[30]]=1
            y2=np.zeros(5);y2[base.index[40]]=1
            expected=2*np.square(p-y1).sum()+np.square(p-y2).sum()
            self.assertAlmostEqual(r.score_sum,expected,places=12)
            ranked=sorted(p[p>0],reverse=True); total=0
            for cutoff in ranked:
                total+=cutoff
                if total>=.9-1e-12:break
            region=(p>0)&(p>=cutoff-1e-12)
            self.assertEqual(r.cell_sum,3*np.sum(region&(base.states>=0)))
            self.assertEqual(r.hit_sum,2*region[base.index[30]]+region[base.index[40]])
            self.assertEqual(r.evaluable_pairs,3);self.assertEqual(r.eligible_pairs,6)
            self.assertNotIn((r.horizon_days,30),vectors)

    def test_reference_and_seen_mask_ignore_holdout_changes(self):
        a=self.base();d=counts_fixture();d.loc[d.id.eq(3),'pair_count']*=1000
        b=fit_bases(d,[1,2],[10,20,30],[-2,10,20,30,40])
        for key in a.rows:np.testing.assert_array_equal(a.rows[key],b.rows[key])
        for h in (7,30):np.testing.assert_array_equal(a.references[h],b.references[h])
        with self.assertRaises(ValueError):candidate_metrics(a,d,[1,3])
        with self.assertRaises(ValueError):fit_bases(d[d.horizon_days.eq(7)],[1,2],[10,20,30],[-2,10,20,30,40])

    def selector_fixture(self, variation):
        rows=[]
        for h in (7,30):
            for model,a,c,b,B,K,H in [
                ('Fixed',.2,1,0,.9,20,.9),('E1Adaptive',.2,1,1,.9,20,.9),
                ('Info',.2,1,0,.9,20,.9),('Weight',.2,1,0,.9,20,.9),
                ('Info',.2,.5,0,*variation),('Weight',.2,1,.5,*variation)]:
                rows.append(dict(horizon_days=h,model=model,parameter_a=a,parameter_c=c,parameter_beta=b,
                                 score_sum=100*B,cell_sum=100*K,hit_sum=100*H,eligible_pairs=100,evaluable_pairs=100))
        return pd.DataFrame(rows)

    def test_quality_gates_and_strict_gain_fallback(self):
        for B,K,H in [(.91,10,.95),(.89,10,.89),(.89,20,.95)]:
            selected,_=select_parameters(self.selector_fixture((B,K,H)))
            arms=selected[selected.model.isin(['Info','Weight'])]
            self.assertTrue(arms.selection_status.eq('fallback_fixed').all())
            self.assertTrue(arms.parameter_c.eq(1).all());self.assertTrue(arms.parameter_beta.eq(0).all())
        selected,pool=select_parameters(self.selector_fixture((.89,19,.91)))
        self.assertTrue(selected[selected.model.isin(['Info','Weight'])].selection_status.eq('constrained_gain').all())
        self.assertEqual(pool.selected.sum(),8)

    def test_deterministic_ties_and_common_denominator(self):
        data=self.selector_fixture((.89,19,.91))
        more=data[data.model.eq('Info')&data.parameter_c.eq(.5)].assign(parameter_c=.75)
        selected,_=select_parameters(pd.concat([data,more],ignore_index=True).sample(frac=1,random_state=1))
        self.assertTrue(selected[selected.model.eq('Info')].parameter_c.eq(.75).all())
        data.loc[0,'evaluable_pairs']=99
        with self.assertRaises(ValueError):select_parameters(data)

    def test_exact_fallback_predictions_and_full_case_diagnostics(self):
        base=self.base();sel,_=select_parameters(self.selector_fixture((.91,10,.95)))
        fixed,_=forecasts(base,'Fixed',sel)
        for model in ('Info','Weight'):
            v,_=forecasts(base,model,sel)
            for key in v:np.testing.assert_array_equal(v[key],fixed[key])
            scores,_=diagnostic_scores(base,v,counts_fixture(),[3],model)
            self.assertTrue(scores[scores.origin_cell_1.eq(30)].brier.isna().all())
            self.assertTrue(scores[scores.destination_cell_1.eq(40)].true_probability.eq(0).all())
            self.assertTrue(scores[scores.destination_cell_1.eq(40)].brier.ge(1).all())

    def test_paired_bootstrap_and_undefined_draws(self):
        base=self.base();sel,_=select_parameters(self.selector_fixture((.91,10,.95)))
        scores=[]
        for model in ('B2','Fixed','E1Adaptive','Info','Weight'):
            v,_=forecasts(base,model,sel);s,_=diagnostic_scores(base,v,counts_fixture(),[3],model);scores.append(s)
        full=pd.concat(scores,ignore_index=True)
        a=paired_bootstrap(full,[3,4],200,42);b=paired_bootstrap(full,[3,4],200,42)
        pd.testing.assert_frame_equal(a[0],b[0])
        self.assertTrue(a[2].difference.eq(0).all());self.assertTrue(a[3].outcome.eq('no_change').all())
        self.assertGreater(a[1].undefined_replicates.sum(),0)
        self.assertEqual(a[4][a[4].id.eq(3)].den.min(),3)

    def test_uncertainty_gate_not_replaced_by_point_success(self):
        point=dict(brier=-.001,region90_cells=-1,region90_hit=.001)
        low=dict(brier=-.002,region90_cells=-2,region90_hit=-.01)
        high=dict(brier=.001,region90_cells=-.5,region90_hit=.01)
        self.assertEqual(classify(point,low,high,5000,5000)[0],'point_candidate_inconclusive')
        high['brier']=-.0001;low['region90_hit']=0
        self.assertTrue(classify(point,low,high,5000,5000)[2])
        self.assertFalse(classify(point,low,high,4999,5000)[2])

    def test_independent_candidate_and_selector_audits_detect_corruption(self):
        from data3001.modelling.baselines.b2_b1_e2_audit import rebuild,audit_candidates,audit_selection
        data=counts_fixture();base=self.base()
        folds=pd.DataFrame({'id':[1,2,3],'outer_fold':[1,2,0]})
        roles={'outer_0':dict(training_ids=[1,2],evaluation_ids=[3],outer_fold=0,inner_fold=-1)}
        independent=rebuild(data,folds,roles,base.states)
        table=candidate_metrics(base,data,[3]).assign(fit_role='outer_0',selection_role='all_development_candidate')
        self.assertEqual(audit_candidates(data,roles,base.states,independent,table)['candidate_rows_checked'],504)
        selected,_=select_parameters(table);selected['role']='all_development_candidate'
        self.assertTrue(audit_selection(table,selected))
        bad=table.copy();bad.loc[0,'score_sum']+=.1
        with self.assertRaises(AssertionError):audit_candidates(data,roles,base.states,independent,bad)
        selected.loc[0,'parameter_a']=.123
        with self.assertRaises(AssertionError):audit_selection(table,selected)

    def test_bootstrap_keeps_original_pair_weights(self):
        base=self.base();data=counts_fixture()
        extra=pd.DataFrame([[4,h,10,10,9] for h in (7,30)],columns=data.columns)
        data=pd.concat([data,extra],ignore_index=True)
        selected,_=select_parameters(self.selector_fixture((.91,10,.95)))
        parts=[]
        for model in ('B2','Fixed','E1Adaptive','Info','Weight'):
            vectors,_=forecasts(base,model,selected);s,_=diagnostic_scores(base,vectors,data,[3,4],model);parts.append(s)
        full=pd.concat(parts,ignore_index=True);draws,*_=paired_bootstrap(full,[3,4],100,19)
        mult=np.random.default_rng(19).multinomial(2,[.5,.5],size=100)
        p=base.rows[(7,10)];e3=np.zeros(5);e3[base.index[30]]=1;e4=np.zeros(5);e4[base.index[40]]=1;e1=np.zeros(5);e1[base.index[10]]=1
        n3=2*np.square(p-e3).sum()+np.square(p-e4).sum();n4=9*np.square(p-e1).sum()
        expected=(mult[:,0]*n3+mult[:,1]*n4)/(mult[:,0]*3+mult[:,1]*9)
        np.testing.assert_allclose(draws[draws.model.eq('B2')&draws.horizon_days.eq(7)].brier,expected,atol=1e-12,rtol=0)

    def test_config_and_import_isolation(self):
        from data3001.modelling.baselines.run_b2_b1_e2 import validate_config
        config=json.loads((Path(__file__).resolve().parents[1]/'configs/b2_b1_e2.json').read_text());validate_config(config)
        for field,value in [('region_level',.8),('final_test_access',True),('brier_deterioration_margin',.001),
                            ('info_exit_policy','renormalize_all'),('info_c_grid',[0,1]),('weight_beta_grid',[0,1,2])]:
            with self.assertRaises(ValueError):validate_config({**config,field:value})
        code="import sys; import data3001.modelling.baselines.run_b2_b1_e2; assert not any('run_adaptive_b2_b1' in n or 'run_empirical_b2' in n or 'markov_models' in n or 'continuous_models' in n or n == 'torch' for n in sys.modules)"
        subprocess.run([sys.executable,'-B','-c',code],check=True,capture_output=True)


if __name__=='__main__':unittest.main()
