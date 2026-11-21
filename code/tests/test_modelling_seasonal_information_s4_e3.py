"""Semantic fixtures for the approved seasonal selection and matched controls."""
import unittest
import numpy as np
import pandas as pd
from data3001.modelling.baselines import seasonal_information_s4_e3 as e3
from data3001.modelling.baselines import seasonal_information_s4_e3_matching as match
from data3001.modelling.baselines.seasonal_information_s4_e3_inference import multiplier_summary
from data3001.modelling.baselines.temporal_validation_s4_e2_inputs import temporal_role
from data3001.modelling.common.prediction_regions import probability_region


class E3Tests(unittest.TestCase):
    def test_analytic_solutions(self):
        for U,V,want in [(0,0,0),(2,-.1,0),(2,.4,.2),(2,4,1),(1,1e-7,0)]:
            self.assertAlmostEqual(e3.choose_weight(U,V),want)

    def test_inner_pools_recurrent_ID_before_voting(self):
        folds=[]
        states=np.array([-2,10])
        a=np.array([.5,.5]);s=np.array([0.,1.])
        for name,ids,truths in [('first',[1,1],[-2,10]),('second',[1,2],[10,10])]:
            v=pd.DataFrame(dict(id=ids,origin_source_obs=([0,1] if name=='first' else [2,3]),horizon_days=7,
                                origin_cell_1=10,departure_season=0,destination_cell_1=truths,origin_time_UTC=pd.Timestamp('2018-01-01',tz='UTC')))
            folds.append((name,{(7,10,-1):a,(7,10,0):s},v))
        weights,curves,cases=e3.select_weights(folds,states)
        self.assertAlmostEqual(cases[cases.id.eq(1)].weight.sum(),.5)
        self.assertAlmostEqual(weights.c.iloc[0],2/3)
        self.assertAlmostEqual(weights.minimum_loss.iloc[0],curves[curves.fold.eq('pooled')].brier.min())

    def test_sampling_quota_offsets_and_replay(self):
        dates=[];donors=[]
        for donor,month in [(10,1),(20,7),(30,8),(40,6)]:
            for day in [0,1,3]:
                donors.append(donor);dates.append(pd.Timestamp(2016,month,1,tz='UTC')+pd.Timedelta(hours=day))
        f=pd.DataFrame(dict(id=donors,origin_source_obs=np.arange(len(dates)),origin_time_UTC=dates))
        f['departure_season']=((f.origin_time_UTC.dt.month%12)//3)
        args=(f,0,(7,123,0),12,20261106)
        a,ma,_=match.draw_table(*args);b,mb,_=match.draw_table(*args)
        self.assertTrue(np.array_equal(a,b));pd.testing.assert_frame_equal(ma,mb)
        mix,identical=match.audit_draws(f,0,a,ma)
        self.assertGreater(mix.sum(),0)
        self.assertTrue(np.all(mix+identical==1))
        bad=a.copy();bad[0,0]=bad[0,1]
        with self.assertRaises(AssertionError):match.audit_draws(f,0,bad,ma)
        cost=np.array([[1.,1.,2.],[1.,1.,1.]])
        self.assertEqual(match.lexical_assignment(cost).tolist(),[0,1])

    def test_cross_horizon_boundary(self):
        time=pd.to_datetime(['2019-11-01','2019-12-31','2019-11-02','2020-01-01'],utc=True)
        cutoff=pd.Timestamp('2020-01-01',tz='UTC').timestamp()
        z=pd.DataFrame(dict(id=[11,12,13,13],origin_source_obs=range(4),horizon_days=[7,30,7,30],origin_time_UTC=time,
                            required_interval_end_epoch=[cutoff-1,cutoff,cutoff-1,cutoff+86400*30]))
        role=temporal_role(z,'2020-01-01','2023-01-01','fixture')
        self.assertEqual(role['train'].id.tolist(),[11]);self.assertEqual(role['validation'].id.tolist(),[13])

    def test_forecast_isolation_and_E_tie(self):
        key=(7,10,0);p=np.array([.5,.25,.25]);s=np.array([.25,.5,.25])
        states=np.array([-2,10,11]);support=pd.DataFrame([dict(horizon_days=7,origin_cell_1=10,departure_season=0,annual_fallback=False)])
        choices=pd.DataFrame([dict(horizon_days=7,c=.5)]);matrix={(7,10,-1):p,key:s}
        cache,_=e3.make_forecasts(matrix,support,choices,states)
        case=pd.DataFrame([dict(id=11,origin_source_obs=1,horizon_days=7,origin_cell_1=10,departure_season=0,supported=True,weight=1.)])
        draws={key:(states,np.array([[2,1,1],[1,2,1]]),.5)}
        for truth in [-2,11]:
            targets=case[e3.KEY].assign(destination_cell_1=truth)
            scored,_=e3.score_cases(case,targets,cache,draws,states)
            self.assertAlmostEqual(scored.sample(n=1,random_state=11).Matched_brier.iloc[0],np.mean([
                np.square(v-(states==truth)).sum() for v in [p,s]]))
            np.testing.assert_array_equal(cache['Adjusted',*key][0],(p+s)/2)
        mask,region=probability_region(p,states)
        self.assertTrue(mask.all());self.assertEqual(region['region90_cells'],2)
        f,meta=e3.make_forecasts({(7,10,-1):p,key:p},support.assign(annual_fallback=True),choices,states)
        np.testing.assert_array_equal(f['Adjusted',*key][0],p)

    def test_subset_retains_full_roster_weight(self):
        g=pd.DataFrame(dict(id=[1,1,2],origin_cell_1=[5,5,5],weight=[.25,.25,.5],value=[0.,1.,3.]))
        point,draws=multiplier_summary(g,np.ones((2,2)),{1:0,2:1},['value'],np.array([False,True,True]))
        self.assertAlmostEqual(point[0],(.25+1.5)/.75)
        np.testing.assert_allclose(draws[:,0],point[0])
