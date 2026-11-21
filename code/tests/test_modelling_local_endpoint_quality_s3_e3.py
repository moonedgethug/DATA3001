import unittest
import numpy as np
import pandas as pd
from data3001.modelling.baselines import local_endpoint_quality_s3_e3 as model
from data3001.modelling.baselines import local_endpoint_adaptive_s3_e2 as control


def counts_fixture():
    records=[]
    # T=50 is unseen and weak; 60 is exactly 1%; 70 has three donor IDs;
    # C=40 is locally rare. One ID visits two donor origins.
    for h in (7,30):
        for d,o,j,n in [(1,370,20,700),(1,370,30,295),(2,370,40,5),
                        (3,371,20,600),(3,371,30,370),(3,371,40,5),(3,371,50,2),
                        (4,371,50,3),(3,371,60,10),(3,371,70,1),(4,371,70,1),(5,371,70,1),
                        (3,731,30,7),(8,370,50,1),(8,400,60,1)]:
            records.append((d,h,o,j,n))
    return pd.DataFrame(records,columns=['id','horizon_days','origin_cell_1','destination_cell_1','pair_count'])


class EndpointQualityTests(unittest.TestCase):
    def base(self):
        c=counts_fixture();return c,model.fit_bases(c,[1,2,3,4,5],[370,371,731,400],[-2,20,30,40,50,60,70,370,371,400,731])

    def test_endpoint_union_and_exact_weak_thresholds(self):
        c,b=self.base();e=b.endpoint_evidence.query('horizon_days==7 and origin_cell_1==370').set_index('destination_cell_1')
        self.assertEqual(e.loc[30,'neighbour_endpoint_ids'],1)
        self.assertEqual(e.loc[50,'neighbour_endpoint_ids'],2)
        self.assertTrue(e.loc[50,'weak_unseen']);self.assertFalse(e.loc[40,'weak_unseen'])
        self.assertFalse(e.loc[60,'weak_unseen']);self.assertEqual(e.loc[60,'original_neighbour_D_probability'],.01)
        self.assertEqual(e.loc[70,'neighbour_endpoint_ids'],3);self.assertFalse(e.loc[70,'weak_unseen'])

    def test_hand_mass_return_and_local_rare_protection(self):
        c,b=self.base();p=b.rows[(7,370)];q=b.endpoint_rows[(7,370)]
        new,delta=model.quality_reference(b,7,370,0,0)
        self.assertAlmostEqual(delta,.005);self.assertEqual(new[b.index[50]],0.)
        self.assertAlmostEqual(new[b.index[40]],q[b.index[40]]+delta*.005)
        self.assertAlmostEqual(new.sum(),1.)
        np.testing.assert_allclose(new[[b.index[20],b.index[30]]],q[[b.index[20],b.index[30]]]+delta*p[[b.index[20],b.index[30]]])

    def test_neutral_exact_anchor_and_all_controls(self):
        c,b=self.base();old=control.fit_bases(c,[1,2,3,4,5],[370,371,731,400],b.states)
        for key in b.rows:
            for m,a,g in control.specifications():
                np.testing.assert_array_equal(model.vector(b,*key,m,a,g),control.vector(old,*key,m,a,g))
            for a,g in [(0,0),(.65,0),(.85,2),(1,2)]:
                np.testing.assert_array_equal(model.vector(b,*key,'LocalEndpointQuality',a,g,0,1),control.vector(old,*key,'LocalEndpointAdaptive',a,g))

    def test_exit_preserved_with_unequal_donor_exit_rates(self):
        c=counts_fixture();extra=pd.DataFrame([(6,h,371,-2,300) for h in (7,30)],columns=c.columns);c=pd.concat([c,extra],ignore_index=True)
        b=model.fit_bases(c,[1,2,3,4,5,6],[370,371,731,400],[-2,20,30,40,50,60,70,370,371,400,731])
        for eta in model.ETAS:
            for rho in model.RHOS:
                q,d=model.quality_reference(b,7,370,eta,rho)
                self.assertEqual(q[b.index[-2]],b.endpoint_rows[(7,370)][b.index[-2]])
                self.assertAlmostEqual(q.sum(),1.);self.assertTrue((q>=0).all())
                p=model.vector(b,7,370,'LocalEndpointQuality',.7,2,eta,rho)
                self.assertEqual(p[b.index[-2]],control.vector(b,7,370,'LocalEndpointAdaptive',.7,2)[b.index[-2]])

    def test_similarity_floor_and_original_pair_pooling(self):
        c,b=self.base();t=b.donor_quality.query('horizon_days==7 and origin_cell_1==370')
        neutral=t[t.parameter_eta.eq(0)]
        np.testing.assert_allclose(neutral.original_D_weight,neutral.reweighted_D_weight)
        self.assertTrue(t.similarity.between(0,1).all())
        self.assertTrue((t.reweighted_D_weight>=.1*t.original_D_weight-1e-12).all())

    def test_held_out_changes_do_not_affect_quality(self):
        c,b=self.base();c.loc[c.id.eq(8),'pair_count']*=10000;c.loc[c.id.eq(8),'destination_cell_1']=20
        changed=model.fit_bases(c,[1,2,3,4,5],[370,371,731,400],b.states)
        pd.testing.assert_frame_equal(b.endpoint_evidence,changed.endpoint_evidence)
        pd.testing.assert_frame_equal(b.donor_quality,changed.donor_quality)
        anchor,_=model.select_controls(model.control_candidates(b,c,[8]))
        with self.assertRaises(ValueError):model.quality_candidates(b,c,[1,8],anchor)

    def test_no_donors_and_unsupported(self):
        c=counts_fixture();b=model.fit_bases(c,[1,2],[370,371,731,400],[-2,20,30,40,50,60,70,370,371,400,731])
        for eta in model.ETAS:
            for rho in model.RHOS:
                np.testing.assert_array_equal(model.vector(b,7,370,'LocalEndpointQuality',.9,2,eta,rho),b.rows[(7,370)])
                self.assertIsNone(model.vector(b,7,400,'LocalEndpointQuality',.9,2,eta,rho))

    def test_all_E_and_no_neighbour_D_bypass(self):
        for own_exit in (True,False):
            c=pd.DataFrame([(1,h,370,-2 if own_exit else 20,3) for h in (7,30)]+[(2,h,371,20 if own_exit else -2,4) for h in (7,30)],columns=counts_fixture().columns)
            b=model.fit_bases(c,[1,2],[370,371],[-2,20,30,370,371])
            self.assertEqual(b.quality[(7,370)]['reason'],'local_D_empty' if own_exit else 'neighbour_D_empty')
            for e in model.ETAS:
                for r in model.RHOS:
                    q,d=model.quality_reference(b,7,370,e,r);np.testing.assert_array_equal(q,b.endpoint_rows[(7,370)]);self.assertEqual(d,0)

    def test_anchor_grid_selection_and_neutral_ties(self):
        c,b=self.base();cu=model.control_candidates(b,c,[8]);anchor,_=model.select_controls(cu)
        qu=model.quality_candidates(b,c,[8],anchor)
        self.assertEqual(len(cu[['model','parameter_a','parameter_gamma']].drop_duplicates()),148)
        self.assertEqual(len(qu[['parameter_eta','parameter_rho']].drop_duplicates()),9)
        chosen,_=model.select_quality(qu)
        for h in (7,30):
            expected=anchor[(anchor.model=='LocalEndpointAdaptive')&(anchor.horizon_days==h)].iloc[0]
            self.assertTrue(qu[qu.horizon_days.eq(h)].parameter_a.eq(expected.parameter_a).all())
            self.assertTrue(qu[qu.horizon_days.eq(h)].parameter_gamma.eq(expected.parameter_gamma).all())
        tied=qu.copy();tied.loc[tied.supported,'brier']=.8
        best,_=model.select_quality(tied);self.assertTrue(best.parameter_eta.eq(0).all());self.assertTrue(best.parameter_rho.eq(1).all())
        derived=model.add_ablations(pd.concat([anchor,chosen]));self.assertEqual(len(derived),14)

    def test_zero_truth_still_scored_and_categories_reconcile(self):
        c,b=self.base();anchor,_=model.select_controls(model.control_candidates(b,c,[8]));q,_=model.select_quality(model.quality_candidates(b,c,[8],anchor))
        q['parameter_a']=1.;q['parameter_gamma']=0.;q['parameter_eta']=0.;q['parameter_rho']=0.
        selected=model.add_ablations(pd.concat([anchor,q]));parts=[]
        for m in model.OUTPUT_MODELS:
            vectors,s=model.forecasts(b,m,selected);sc,bounds=model.diagnostic_scores(b,vectors,c,[8],m);parts.append(sc)
        scores=model.attach_primary_weights(pd.concat(parts,ignore_index=True));good=scores[scores.status.eq('evaluable')]
        for suffix,target in [('probability',np.ones(len(good))),('observed',np.ones(len(good))),('hit',good.region90_hit),('brier',good.brier)]:
            np.testing.assert_allclose(good[[f'category_{z}_{suffix}' for z in model.CATEGORIES]].sum(axis=1),target,atol=1e-12)
        qscore=good[good.model.eq('LocalEndpointQuality')]
        self.assertTrue(qscore.zero_true_probability.eq(1).all());self.assertTrue(qscore.brier.ge(1).all())
        units=model.score_units(scores);summary=model.summarize_units(units,metrics=model.metric_columns(scores))
        self.assertTrue(summary.unsupported_id_cells.eq(1).all())
        draws,ci,diff,dec,meta=model.uncertainty(units,[1,2,3,4,5,8],replicates=20)
        self.assertEqual(meta['directional_comparisons'],18);self.assertEqual(len(dec),6)
        self.assertEqual(len(diff[diff.primary_comparison]),18)

    def test_invalid_quality_parameter(self):
        c,b=self.base()
        for eta,rho in [(1,1),(.1,1),(0,2),(0,np.nan)]:
            with self.assertRaises(ValueError):model.quality_reference(b,7,370,eta,rho)

    def test_independent_reconstruction(self):
        from data3001.modelling.baselines.local_endpoint_quality_s3_e3_audit import rebuild,probability
        c,b=self.base();folds=pd.DataFrame({'id':[1,2,3,4,5,8],'outer_fold':[1,1,1,1,1,0]})
        roles={'outer_0':dict(training_ids=[1,2,3,4,5],evaluation_ids=[8],outer_fold=0,inner_fold=-1)}
        independent=rebuild(c,folds,roles,b.states)['outer_0']
        for key in b.rows:
            for eta in model.ETAS:
                for rho in model.RHOS:
                    np.testing.assert_allclose(model.vector(b,*key,'LocalEndpointQuality',.65,2,eta,rho),
                        probability(independent,*key,'LocalEndpointQuality',.65,2,eta,rho),atol=1e-12,rtol=0)
        for name,columns in [('donor_quality',['horizon_days','origin_cell_1','donor_cell_1','parameter_eta']),('endpoint_evidence',['horizon_days','origin_cell_1','destination_cell_1'])]:
            left=getattr(b,name).sort_values(columns).reset_index(drop=True)
            right=independent[name].sort_values(columns).reset_index(drop=True)
            pd.testing.assert_frame_equal(left,right,check_dtype=False,check_exact=False,atol=1e-12,rtol=0)

    def test_locked_runner_configuration(self):
        from pathlib import Path
        import json
        from data3001.modelling.baselines.run_local_endpoint_quality_s3_e3 import validate_config
        config=json.loads(Path('configs/local_endpoint_quality_s3_e3.json').read_text());validate_config(config)
        config['weak_ID_threshold']=4
        with self.assertRaises(ValueError):validate_config(config)

if __name__=='__main__':unittest.main()
