import unittest,json
from pathlib import Path
import numpy as np
import pandas as pd
from test_modelling_local_endpoint_quality_s3_e3 import counts_fixture
from data3001.modelling.baselines import local_endpoint_joint_s3_e4 as m
from data3001.modelling.baselines import local_endpoint_quality_s3_e3 as q
from data3001.modelling.baselines.local_endpoint_joint_s3_e4_audit import independent_selection,rebuild,probability


def selection_fixture():
    rows=[]
    for h in (7,30):
        for t in m.SPECS:rows.append(dict(horizon_days=h,model=m.JOINT,**dict(zip(m.PARAMETERS,t)),id=8,origin_cell_1=370,
            eligible_pairs=1,supported=True,brier=1.,region90_hit=.8,region90_cells=30.))
    units=pd.DataFrame(rows);refs=[]
    for h in (7,30):
        for name,b,hit,size in [('LocalEndpointAdaptive',.9,.85,20.),('Fixed',.95,.9,40.)]:
            row=units[(units.horizon_days==h)&(units.parameter_a==.5)&(units.parameter_gamma==1)&(units.parameter_eta==0)].copy()
            row['model']=name;row['brier']=b;row['region90_hit']=hit;row['region90_cells']=size
            refs.append(m.summarize_units(row,m.IDENTITY))
    return units,pd.concat(refs,ignore_index=True)


def set_candidate(units,params=(.65,1.,.5,1.),b=.8,h=.91,k=19.):
    mask=np.ones(len(units),dtype=bool)
    for c,v in zip(m.PARAMETERS,params):mask &= units[c].eq(v).to_numpy()
    units.loc[mask,['brier','region90_hit','region90_cells']]=[b,h,k]


class JointEndpointTests(unittest.TestCase):
    def base(self):
        counts=counts_fixture();base=m.fit_bases(counts,[1,2,3,4,5],[370,371,731,400],[-2,20,30,40,50,60,70,370,371,400,731]);return counts,base

    def test_grid_and_all_neutral_subfamilies(self):
        c,b=self.base();self.assertEqual(len(set(m.SPECS)),252)
        for key in b.rows:
            for a,g in [(0,0),(.65,0),(.85,2),(1,2)]:
                np.testing.assert_array_equal(m.vector(b,*key,m.JOINT,a,g,0,1),q.vector(b,*key,'LocalEndpointAdaptive',a,g))
            for eta in (0,.5,.9):np.testing.assert_array_equal(m.vector(b,*key,m.JOINT,0,2,eta,1),b.rows[key])

    def test_candidate_score_hand_reconstruction(self):
        c,b=self.base();units=m.joint_candidates(b,c,[8]);good=units[(units.horizon_days==7)&(units.origin_cell_1==370)]
        self.assertEqual(len(good),252)
        independent=rebuild(c,pd.DataFrame({'id':[1,2,3,4,5,8],'outer_fold':[1,1,1,1,1,0]}),
            {'outer_0':dict(training_ids=[1,2,3,4,5],evaluation_ids=[8],outer_fold=0,inner_fold=-1)},b.states)['outer_0']
        for r in good.itertuples(index=False):
            p=probability(independent,7,370,m.JOINT,*[getattr(r,k) for k in m.PARAMETERS])
            self.assertAlmostEqual(r.brier,1+float(p@p)-2*p[b.index[50]],places=12)
        self.assertTrue(units[units.origin_cell_1.eq(400)].brier.isna().all())

    def test_validation_leak_rejected(self):
        c,b=self.base()
        with self.assertRaises(ValueError):m.joint_candidates(b,c,[1,8])

    def test_no_donor_bypass_and_invalid_parameter(self):
        c,b=self.base();b=m.fit_bases(c,[1,2],[370,371,731,400],b.states)
        np.testing.assert_array_equal(m.vector(b,7,370,m.JOINT,.9,2,.9,1),b.rows[(7,370)])
        self.assertIsNone(m.vector(b,7,400,m.PRIMARY,.9,2,.9,1))
        for t in [(1,2,.9,0),(.7,3,.5,1),(.7,1,1,1)]:
            with self.assertRaises(ValueError):m.vector(b,7,370,m.JOINT,*t)

    def test_empty_feasible_fallback(self):
        units,refs=selection_fixture();chosen,pool,d=m.select_joint(units,refs);c=chosen[chosen.model.eq(m.PRIMARY)]
        self.assertTrue(c.fallback.all());self.assertTrue(c.selection_status.eq('fallback_no_feasible_candidate').all())
        self.assertTrue(c.parameter_a.eq(.5).all());self.assertTrue(d.feasible_both.eq(0).all())
        self.assertFalse(pool.selected_constrained.any())

    def test_no_Brier_gain_fallback(self):
        units,refs=selection_fixture();set_candidate(units,b=.91)
        chosen,pool,d=m.select_joint(units,refs)
        self.assertTrue(chosen[chosen.model.eq(m.PRIMARY)].selection_status.eq('fallback_no_Brier_gain').all())
        self.assertTrue(d.feasible_both.eq(1).all())

    def test_valid_candidate_adopted(self):
        units,refs=selection_fixture();set_candidate(units)
        chosen,pool,d=m.select_joint(units,refs)
        self.assertFalse(chosen[chosen.model.eq(m.PRIMARY)].fallback.any());self.assertTrue(d.feasible_and_Brier.eq(1).all())

    def test_lower_Brier_rejected_for_Fixed_hits(self):
        units,refs=selection_fixture();set_candidate(units,b=.1,h=.86)
        chosen,pool,d=m.select_joint(units,refs)
        self.assertTrue(chosen[chosen.model.eq(m.JOINT)].brier.eq(.1).all())
        self.assertTrue(chosen[chosen.model.eq(m.PRIMARY)].fallback.all());self.assertTrue(d.feasible_anchor.eq(1).all())

    def test_each_of_four_guards_operates(self):
        for ref,metric,value,candidate_value in [('Fixed','region90_hit',.93,.92),('LocalEndpointAdaptive','region90_hit',.94,.92),
            ('Fixed','region90_cells',18,19),('LocalEndpointAdaptive','region90_cells',18,19)]:
            with self.subTest(ref=ref,metric=metric):
                units,refs=selection_fixture();refs.loc[refs.model.eq(ref),metric]=value
                set_candidate(units,h=.92,k=19)
                chosen,pool,d=m.select_joint(units,refs);self.assertTrue(d.fallback.all())

    def test_Brier_must_beat_both_references(self):
        units,refs=selection_fixture();refs.loc[refs.model.eq('Fixed'),'brier']=.7;set_candidate(units,b=.8)
        chosen,pool,d=m.select_joint(units,refs);self.assertTrue(d.selection_status.eq('fallback_no_Brier_gain').all())

    def test_neutral_tie_and_determinism(self):
        units,refs=selection_fixture();units['brier']=.8;units['region90_hit']=.95;units['region90_cells']=10.
        chosen,_,_=m.select_joint(units.sample(frac=1,random_state=20),refs)
        for c in ('parameter_a','parameter_gamma','parameter_eta'):self.assertTrue(chosen[c].eq(0).all())

    def test_numerical_tolerance_is_not_scientific_margin(self):
        for diff,expected in [(5e-13,False),(2e-12,True)]:
            units,refs=selection_fixture();set_candidate(units,h=.9-diff)
            _,_,d=m.select_joint(units,refs);self.assertEqual(bool(d.fallback.all()),expected)

    def test_incomplete_grid_and_population_mismatch_rejected(self):
        units,refs=selection_fixture()
        with self.assertRaises(ValueError):m.select_joint(units.iloc[1:],refs)
        refs['eligible_pairs']=2
        with self.assertRaises(ValueError):m.select_joint(units,refs)

    def test_independent_selection_matches_all_branches(self):
        for scenario in ('empty','no_gain','adopt','one_reference'):
            units,refs=selection_fixture()
            if scenario!='empty':set_candidate(units,b=.95 if scenario=='no_gain' else .8,h=.86 if scenario=='one_reference' else .91)
            chosen,pool,d=m.select_joint(units,refs)
            for h in (7,30):
                r=refs[refs.horizon_days.eq(h)].set_index('model')
                un,issued,status,flags,diagnostics=independent_selection(pool[pool.horizon_days.eq(h)].to_dict('records'),r.loc['LocalEndpointAdaptive'],r.loc['Fixed'])
                selected=chosen[(chosen.horizon_days==h)&(chosen.model==m.PRIMARY)].iloc[0]
                self.assertEqual(issued,tuple(selected[k] for k in m.PARAMETERS));self.assertEqual(status,selected.selection_status)

    def test_eight_models_fallback_and_uncertainty(self):
        c,b=self.base();anchor,_=m.select_controls(m.control_candidates(b,c,[8]));quality,_=m.select_quality(m.quality_candidates(b,c,[8],anchor));controls=pd.concat([anchor,quality])
        joint=m.joint_candidates(b,c,[8]);chosen,pool,d=m.select_joint(joint,controls);selected=pd.concat([controls,chosen]);parts=[]
        anchor_vectors,_=m.forecasts(b,'LocalEndpointAdaptive',selected)
        for model in m.MODELS:
            vectors,support=m.forecasts(b,model,selected)
            if model==m.PRIMARY:
                for h in (7,30):
                    if bool(d[d.horizon_days.eq(h)].iloc[0].fallback):
                        for key in vectors:
                            if key[0]==h:np.testing.assert_array_equal(vectors[key],anchor_vectors[key])
            scores,_=m.diagnostic_scores(b,vectors,c,[8],model);parts.append(scores)
        scores=m.attach_primary_weights(pd.concat(parts,ignore_index=True));units=m.score_units(scores)
        draws,ci,diff,dec,meta=m.uncertainty(units,[1,2,3,4,5,8],20)
        self.assertEqual(len(dec),4);self.assertEqual(diff.primary_comparison.sum(),12);self.assertEqual(meta['directional_comparisons'],12)

    def test_locked_config(self):
        from data3001.modelling.baselines.run_local_endpoint_joint_s3_e4 import validate_config
        c=json.loads(Path('configs/local_endpoint_joint_s3_e4.json').read_text());validate_config(c)
        c['joint_rho']=0
        with self.assertRaises(ValueError):validate_config(c)

if __name__=='__main__':unittest.main()
