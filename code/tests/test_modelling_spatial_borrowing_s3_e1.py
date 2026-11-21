import unittest
import numpy as np
import pandas as pd
from data3001.modelling.baselines.spatial_borrowing_s3_e1 import (
    fit_bases,vector,candidate_units,select_parameters,forecasts,specifications,
    diagnostic_scores,score_units,summarize_units,uncertainty,
)


def fixture():
    counts=[];trans=[]
    for h in [7,30]:
        counts += [[1,h,10,20,2],[2,h,11,30,3],[3,h,10,30,1],[3,h,12,40,1]]
        trans += [[2,h,10,11,40,0,2],[2,h,10,11,-3,6,1],[1,h,11,10,20,0,2]]
    return (pd.DataFrame(counts,columns=['id','horizon_days','origin_cell_1','destination_cell_1','pair_count']),
            pd.DataFrame(trans,columns=['id','horizon_days','origin_cell_1','donor_cell_1','destination_cell_1','reason_code','pair_count']))


class SpatialModelTests(unittest.TestCase):
    def base(self):
        c,t=fixture();return c,t,fit_bases(c,t,[1,2],[10,11,12],[-2,10,11,12,20,30,40])

    def test_guarded_reference_preserves_failed_mass(self):
        c,t,b=self.base()
        np.testing.assert_allclose(b.endpoint_rows[(7,10)],[0,0,0,0,0,1,0])
        np.testing.assert_allclose(b.displacement_rows[(7,10)],[0,0,0,0,1/3,0,2/3])
        np.testing.assert_allclose(vector(b,7,10,'LocalDisplacement',.5),[0,0,0,0,2/3,0,1/3])

    def test_no_donor_fallback_is_b2(self):
        c,t=fixture();c=c[c.origin_cell_1.ne(11)];t=t[t.id.ne(2)]
        b=fit_bases(c,t,[1],[10,11,12],[-2,10,11,12,20,30,40])
        np.testing.assert_array_equal(b.rows[(7,10)],b.displacement_rows[(7,10)])

    def test_missing_transfer_count_is_not_silently_renormalised(self):
        c,t=fixture()
        with self.assertRaises(ValueError):fit_bases(c,t[t.destination_cell_1.ne(-3)],[1,2],[10,11],[-2,10,11,12,20,30,40])

    def test_fit_role_isolation(self):
        c,t,b=self.base();c.loc[c.id.eq(3),'pair_count']*=1000
        other=fit_bases(c,t,[1,2],[10,11,12],[-2,10,11,12,20,30,40])
        for key in b.rows:np.testing.assert_array_equal(b.displacement_rows[key],other.displacement_rows[key])
        with self.assertRaises(ValueError):candidate_units(b,c,[1,3])

    def test_all_candidate_scores_match_direct(self):
        c,t,b=self.base();units=candidate_units(b,c,[3]);self.assertEqual(len(specifications()),85)
        for r in units.itertuples(index=False):
            p=vector(b,r.horizon_days,r.origin_cell_1,r.model,r.parameter_a)
            if p is None:self.assertFalse(r.supported);continue
            truth=np.array([0,0,0,0,0,1,0]);self.assertAlmostEqual(r.brier,float(np.square(p-truth).sum()))
        chosen,pool=select_parameters(units);self.assertEqual(len(chosen),8)
        for m in ['B2','Fixed','Adaptive','LocalEndpoint','LocalDisplacement']:
            v,s=forecasts(b,m,chosen);self.assertNotIn((7,12),v)
            if m=='LocalDisplacement':
                z=s[(s.horizon_days==7)&(s.origin_cell_1==10)].iloc[0]
                self.assertAlmostEqual(z.effective_borrowing_weight,z.parameter_a*2/3)

    def test_macro_population_and_uncertainty_identity(self):
        c,t,b=self.base();chosen,_=select_parameters(candidate_units(b,c,[3]));parts=[]
        for m in ['B2','Fixed','Adaptive','LocalEndpoint','LocalDisplacement']:
            v,_=forecasts(b,m,chosen);s,_=diagnostic_scores(b,v,c,[3],m);parts.append(s)
        units=score_units(pd.concat(parts));s=summarize_units(units)
        self.assertTrue(s.evaluable_id_cells.eq(1).all());self.assertTrue(s.unsupported_id_cells.eq(1).all())
        d,i,f,o,meta=uncertainty(units,[1,2,3],replicates=50)
        d2,*_=uncertainty(units,[1,2,3],replicates=50)
        pd.testing.assert_frame_equal(d,d2);self.assertEqual(len(o),2)

if __name__=='__main__':unittest.main()
