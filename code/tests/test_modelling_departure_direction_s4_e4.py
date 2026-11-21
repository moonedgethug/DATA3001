import unittest

import numpy as np
import pandas as pd
from data3001.preprocessing.prep_core import displacement
from data3001.modelling.baselines.departure_direction_s4_e4_inputs import extract_track
from data3001.modelling.baselines import departure_direction_s4_e4 as e4
from data3001.modelling.baselines.seasonal_information_s4_e3 import choose_weight
from data3001.modelling.baselines.temporal_validation_s4_e2_inputs import temporal_role


def track_fixture():
    time=np.array([0.,3600.,7200.,14400.,18000.])+pd.Timestamp('2019-12-31T23:00Z').timestamp()
    lon=np.array([179.995,-179.995,-179.99,-179.985,-179.985]);lat=np.ones(5)
    _,east,north=displacement(time,lon,lat)
    f=pd.DataFrame(dict(id=11,source_obs=np.arange(5),time=time,lon_normalized=lon,lat=lat,cell_1=[1,2,2,2,2],
                        interval_net_ve=east,interval_net_vn=north,elapsed_seconds_from_previous=np.r_[np.nan,np.diff(time)],
                        analytical_row=True,position_ok=True,mapping_ok=True))
    k=f[['id','source_obs','cell_1']].rename(columns={'source_obs':'origin_source_obs','cell_1':'origin_cell_1'})
    k['origin_time_UTC']=pd.to_datetime(time,unit='s',utc=True)
    return f,k


def paired_fixture():
    return pd.DataFrame(dict(id=np.arange(1,11),origin_source_obs=np.arange(10),origin_cell_1=1,horizon_days=7,
                        interval_reason='valid',east=[1.]*5+[-1.]*5,north=0.,speed=1.,destination_cell_1=[2,2,2,2,-2,2,-2,-2,-2,-2]))


class HeadingTests(unittest.TestCase):
    def test_preceding_interval_crosses_cell_year_and_dateline(self):
        track,keys=track_fixture();got=extract_track(track,keys)
        self.assertEqual(got.interval_reason.tolist(),['first_row','valid','valid','time_gap','valid'])
        self.assertEqual(got.predecessor_obs.tolist(),[-1,0,1,2,3])
        self.assertGreater(got.east.iloc[1],0);self.assertEqual(got.speed.iloc[-1],0)
        track.loc[3:,'lon_normalized']=0
        changed=extract_track(track,keys.iloc[:3])
        np.testing.assert_array_equal(got.east.iloc[:3],changed.east)
        track.loc[0,'mapping_ok']=False
        self.assertEqual(extract_track(track,keys.iloc[[1]]).interval_reason.iloc[0],'position_quality')

    def test_decile_is_fitting_only_deduplicated_and_ties_excluded(self):
        z=paired_fixture();z['speed']=np.r_[1.,1.,np.arange(2.,10.)]
        z['east']=z.speed
        tau=e4.threshold(pd.concat([z,z.iloc[[2,8,9]].assign(horizon_days=30)]))
        self.assertEqual(tau,1.)
        self.assertEqual((e4.classify(z,tau)[0]=='low_speed').sum(),2)
        zero=z.assign(speed=0,east=0)
        self.assertTrue(np.isnan(e4.threshold(zero)));self.assertTrue((e4.classify(zero,np.nan)[0]=='zero_speed').all())

    def test_vote_ratio_missing_donor_neutral_and_fallback(self):
        f=paired_fixture();base,_=e4.fit(f,0.)
        b=base[7,1];query=f.iloc[:1].copy();D,_=e4.predict_basis(b,query,0.)
        self.assertAlmostEqual(D[0,1],.65)
        self.assertAlmostEqual((b.annual+.4*(D[0]-b.annual))[1],.56)
        f.loc[0,'interval_reason']='time_gap';b=e4.fit(f,0.)[0][7,1]
        D,_=e4.predict_basis(b,query,0.)
        e4.direct_donor_check(f,query,b,0.,D)
        q=query.assign(interval_reason='time_gap');D,rs=e4.predict_basis(b,q,0.)
        np.testing.assert_array_equal(D[0],b.annual);self.assertEqual(rs[0],'time_gap')
        empty=e4.fit(f,2.)[0][7,1];D,rs=e4.predict_basis(empty,query.assign(speed=3,east=3),2.)
        self.assertEqual(rs[0],'empty_usable_donor_row');np.testing.assert_array_equal(D[0],empty.annual)
        same=f.assign(east=1,north=0,interval_reason='valid');ident=e4.fit(same,0.)[0][7,1]
        for deg in [1.,359.,180.]:
            rad=np.radians(deg);D,_=e4.predict_basis(ident,query.assign(east=np.cos(rad),north=np.sin(rad)),0.)
            np.testing.assert_allclose(D[0],ident.annual,rtol=0,atol=1e-12)

    def test_time_boundary_and_held_id_across_horizons(self):
        cut=pd.Timestamp('2020-01-01T00:00Z')
        z=pd.DataFrame(dict(id=[1,2,3,3],origin_source_obs=np.arange(4),horizon_days=[7,30,7,30],
             origin_time_UTC=[cut-pd.Timedelta(days=4),cut-pd.Timedelta(days=20),cut-pd.Timedelta(days=8),cut],
             required_interval_end_epoch=[cut.timestamp()-1,cut.timestamp(),cut.timestamp()-1,cut.timestamp()+1]))
        role=temporal_role(z,'2020-01-01','2023-01-01','fixture')
        self.assertEqual(role['train'].id.tolist(),[1]);self.assertEqual(role['validation'].id.tolist(),[3])

    def test_inner_grid_outer_perturbation_and_regions(self):
        train=paired_fixture()
        train.loc[0,['speed','east']]=[.1,.1]
        def pipeline(outer):
            folds=[]
            for k in range(2):
                v=train.iloc[[1,5]].copy();v['id']=[51,52];v['origin_source_obs']+=20*(k+1)
                folds.append((str(k),e4.make_blocks(train,v)[2]))
            lam=e4.selection(folds)[0].lambda_h.iloc[0]
            tau,_,blocks=e4.make_blocks(train,outer.drop(columns='destination_cell_1'))
            _,_,b,D=blocks[0]
            P=b.annual+lam*(D-b.annual)
            return tau,lam,P,e4.regions(P,b.states)
        outer=train.iloc[[2,6]].copy()
        a=pipeline(outer);b=pipeline(outer.assign(destination_cell_1=55))
        for x,y in zip(a,b):np.testing.assert_array_equal(x,y)
        c=pipeline(outer.assign(east=0,north=7.,speed=7.))
        self.assertEqual(a[:2],c[:2])
        self.assertEqual(choose_weight(0,0),0);self.assertEqual(choose_weight(1,2),1)
        self.assertEqual(e4.regions(np.array([[.1,.45,.45],[.1,.45,.45]]),np.array([-2,10,11])).tolist(),[[False,True,True]]*2)
