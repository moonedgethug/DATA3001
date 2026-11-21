import unittest
from pathlib import Path
import json
import numpy as np
import pandas as pd
from data3001.modelling.baselines.local_endpoint_adaptive_s3_e2 import (
    fit_bases,vector,local_weight,neighbours,specifications,candidate_units,select_parameters,
    forecasts,diagnostic_scores,score_units,summarize_units,uncertainty,MODELS,attach_primary_weights,
)
from data3001.modelling.baselines.local_endpoint_adaptive_s3_e2_audit import rebuild,probability
from data3001.modelling.common.prediction_regions import probability_region
from data3001.modelling.baselines.spatial_borrowing_s3_e1 import fit_bases as fit_old,vector as old_vector


def fixture():
    rows=[]
    for h in (7,30):
        rows += [[1,h,370,20,9],[2,h,370,30,1],[2,h,371,30,3],[2,h,730,20,2],
                 [4,h,371,-2,1],[5,h,370,30,2],[5,h,400,20,1]]
    return pd.DataFrame(rows,columns=['id','horizon_days','origin_cell_1','destination_cell_1','pair_count'])


class LocalAdaptiveTests(unittest.TestCase):
    def base(self):
        c=fixture();b=fit_bases(c,[1,2,4],[370,371,730,400],[-2,20,30,370,371,400,730]);return c,b

    def test_distinct_union_overlap_and_raw_distribution(self):
        c,b=self.base();s=b.support_lookup[(7,370)]
        self.assertEqual(s['local_ids'],2);self.assertEqual(s['neighbour_ids'],2)
        self.assertEqual(s['neighbour_pairs'],6);self.assertEqual(s['overlap_local_neighbour_IDs'],1)
        np.testing.assert_allclose(b.rows[(7,370)],[0,.9,.1,0,0,0,0])
        np.testing.assert_allclose(b.endpoint_rows[(7,370)],[1/6,2/6,3/6,0,0,0,0])
        self.assertEqual(json.loads(s['neighbour_ID_set']),[2,4])

    def test_neighbour_geometry_wrap_self_and_latitude(self):
        n=neighbours(370);self.assertEqual(len(n),8);self.assertNotIn(370,n)
        self.assertIn(359,neighbours(360));self.assertTrue(all(0<=i<64800 for i in neighbours(0)+neighbours(64799)))

    def test_hand_calculation_endpoints_and_typical_ratio(self):
        for L,w in [(5,.8),(20,.5),(80,.2)]:self.assertAlmostEqual(local_weight(.5,1,L,40,2),w)
        for a in (0,.25,.65,1):
            self.assertEqual(local_weight(a,0,2,1,.2),a)
            self.assertAlmostEqual(local_weight(a,2,2,4,2),a)
        self.assertEqual(local_weight(.9,2,2,0,1),0.)

    def test_monotonic_support(self):
        self.assertGreater(local_weight(.5,2,2,10,1),local_weight(.5,2,20,10,1))
        self.assertLess(local_weight(.5,2,2,1,1),local_weight(.5,2,2,10,1))

    def test_invalid_support_or_parameters(self):
        for args in [(.5,1,0,2,1),(.5,1,2,-1,1),(.5,1,2,2,0),(1.1,1,2,2,1),(.5,-1,2,2,1),(.5,1,2,np.nan,1)]:
            with self.assertRaises(ValueError):local_weight(*args)

    def test_gamma_zero_exactly_nests_existing_endpoint(self):
        c,b=self.base()
        for h in (7,30):
            for o in (370,371,730):
                for a in (0,.05,.65,.95,1):
                    np.testing.assert_array_equal(vector(b,h,o,'LocalEndpoint',a),vector(b,h,o,'LocalEndpointAdaptive',a,0))

    def test_no_donor_and_common_unsupported(self):
        c=fixture();b=fit_bases(c,[1],[370,371,730,400],[-2,20,30,370,371,400,730])
        self.assertEqual(b.ratio_medians,{7:1.,30:1.})
        self.assertTrue(b.neighbour_support.no_positive_support_ratio.all())
        for m,a,g in specifications():
            np.testing.assert_array_equal(vector(b,7,370,m,a,g),b.rows[(7,370)])
            self.assertIsNone(vector(b,7,400,m,a,g))
        selected,_=select_parameters(candidate_units(b,c[c.origin_cell_1.isin([370,400])],[5]))
        self.assertTrue(selected.parameter_a.eq(0).all());self.assertTrue(selected.parameter_gamma.eq(0).all())

    def test_held_out_ID_does_not_affect_reference_or_scale(self):
        c,b=self.base();c.loc[c.id.eq(5),'pair_count']*=10000
        changed=fit_bases(c,[1,2,4],[370,371,730,400],[-2,20,30,370,371,400,730])
        pd.testing.assert_frame_equal(b.neighbour_support,changed.neighbour_support)
        for key in b.rows:np.testing.assert_array_equal(b.endpoint_rows[key],changed.endpoint_rows[key])
        with self.assertRaises(ValueError):candidate_units(b,c,[1,5])

    def test_pair_replication_changes_frequency_not_ID_support(self):
        c,b=self.base();c.loc[c.id.eq(1),'pair_count']*=10
        changed=fit_bases(c,[1,2,4],[370,371,730,400],[-2,20,30,370,371,400,730])
        self.assertEqual(b.support_lookup[(7,370)]['support_ratio'],changed.support_lookup[(7,370)]['support_ratio'])
        self.assertNotEqual(b.rows[(7,370)][1],changed.rows[(7,370)][1])

    def test_all_candidates_direct_scores_and_nesting(self):
        c,b=self.base();u=candidate_units(b,c,[5]);self.assertEqual(len(specifications()),148)
        for r in u.itertuples(index=False):
            p=vector(b,r.horizon_days,r.origin_cell_1,r.model,r.parameter_a,r.parameter_gamma)
            if p is None:self.assertFalse(r.supported);continue
            truth=np.array([0,0,1,0,0,0,0]);self.assertAlmostEqual(r.brier,float(np.square(p-truth).sum()))
        choice,pool=select_parameters(u);self.assertEqual(len(choice),8)
        for h in (7,30):
            old=pool[(pool.horizon_days==h)&(pool.model=='LocalEndpoint')].brier.min()
            new=pool[(pool.horizon_days==h)&(pool.model=='LocalEndpointAdaptive')].brier.min()
            self.assertLessEqual(new,old+1e-12)

    def test_independent_rebuild_and_probability(self):
        c,b=self.base();folds=pd.DataFrame({'id':[1,2,4,5],'outer_fold':[1,1,1,0]})
        roles={'outer_0':dict(training_ids=[1,2,4],evaluation_ids=[5],outer_fold=0,inner_fold=-1)}
        independent=rebuild(c,folds,roles,b.states)['outer_0']
        for key in b.rows:
            for model,a,g in specifications():np.testing.assert_allclose(vector(b,*key,model,a,g),probability(independent,*key,model,a,g),rtol=0,atol=1e-12)

    def test_existing_four_controls(self):
        c,b=self.base();trans=[]
        for h in (7,30):
            for o in (370,371,730):
                for r in c[(c.horizon_days==h)&c.origin_cell_1.isin(neighbours(o))].itertuples(index=False):
                    trans.append([r.id,h,o,r.origin_cell_1,r.destination_cell_1,0,r.pair_count])
        t=pd.DataFrame(trans,columns=['id','horizon_days','origin_cell_1','donor_cell_1','destination_cell_1','reason_code','pair_count'])
        old=fit_old(c,t,[1,2,4],[370,371,730,400],[-2,20,30,370,371,400,730])
        for key in b.rows:
            for m in MODELS[:4]:
                for a in (0,.35,1):np.testing.assert_allclose(vector(b,*key,m,a),old_vector(old,*key,m,a),rtol=0,atol=1e-12)

    def test_regions_preserve_E_and_ties(self):
        p=np.array([.1,.45,.45]);reg,meta=probability_region(p,np.array([-2,20,30]))
        self.assertEqual(meta['region90_cells'],2);self.assertAlmostEqual(meta['region90_mass'],.9)
        reg,meta=probability_region(np.array([.95,.025,.025]),np.array([-2,20,30]))
        self.assertEqual(meta['region90_cells'],0);self.assertTrue(reg[0])

    def test_score_weights_union_and_reproducible_uncertainty(self):
        c,b=self.base();selected,_=select_parameters(candidate_units(b,c,[5]));parts=[]
        for m in MODELS:
            v,s=forecasts(b,m,selected);f,_=diagnostic_scores(b,v,c,[5],m);parts.append(f)
            self.assertNotIn((7,400),v)
        scores=attach_primary_weights(pd.concat(parts));units=score_units(scores);summary=summarize_units(units)
        self.assertTrue(summary.evaluable_id_cells.eq(1).all());self.assertTrue(summary.unsupported_id_cells.eq(1).all())
        self.assertTrue(units.loc[units.supported,'outside_local_union'].eq(0).all())
        draws,ci,diff,dec,meta=uncertainty(units,[1,2,4,5],replicates=30)
        again,*_=uncertainty(units,[1,2,4,5],replicates=30);pd.testing.assert_frame_equal(draws,again)
        self.assertEqual(len(dec),4);self.assertEqual(meta['directional_comparisons'],12)
        self.assertEqual(meta['seed'],20261031)

if __name__=='__main__':unittest.main()
