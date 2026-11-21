import unittest

import numpy as np
from pyproj import Geod
from shapely.geometry import box

from data3001.modelling.neighbourhood import EndpointMapper
from data3001.preprocessing.prep_core import cells


class PositionTests(unittest.TestCase):
    def test_long_native_noaa_ID_is_not_truncated(self):
        from data3001.modelling.markov_position import OBS_DTYPE
        obs=np.zeros(1,dtype=OBS_DTYPE);obs['id']=300534067902500
        self.assertEqual(int(obs['id'][0]),300534067902500)

    def fixtures(self, path=None):
        from data3001.modelling.markov_position import OBS_DTYPE, fit_pool
        x=np.linspace(-76.9,-76.7,25) if path is None else np.asarray(path)
        obs=np.zeros(len(x),dtype=OBS_DTYPE)
        obs['lon']=x;obs['lat']=33.2;obs['id']=1
        obs['time']=np.arange(len(x))*3600;obs['source_obs']=np.arange(len(x))
        obs['cell']=cells(obs['lon'],obs['lat'])
        _,_,distance=Geod(ellps='WGS84').inv(x[:-1],obs['lat'][:-1],x[1:],obs['lat'][1:])
        obs['length']=np.r_[0,np.cumsum(distance)]
        bins=np.ones(len(x),dtype=np.int8);bins[-1]=8
        pool=fit_pool(obs,np.array([0]),np.array([len(x)-1]),bins,{1},1)
        mapper=EndpointMapper(box(-81,20,-8,55))
        return obs,bins,pool,mapper

    def test_same_cell_offsets_rebin_differently_and_preserve_joint_velocity(self):
        from data3001.modelling.markov_position import step
        obs,bins,pool,mapper=self.fixtures()
        x=np.array([-76.9,-76.05]);y=np.array([33.2,33.2]);c=cells(x,y);v=np.ones(2,dtype=np.int8)
        code,nx,ny,b,stats=step(pool,x,y,c,v,0.,np.zeros(2),np.zeros(2),mapper,precise=True)
        self.assertEqual(code[0],c[0]);self.assertEqual(code[1],c[1]+1)
        np.testing.assert_array_equal(b,[8,8])
        self.assertEqual(nx[0],obs['lon'][-1]);self.assertEqual(ny[0],obs['lat'][-1])
        self.assertGreater(nx[1],-76.)

    def test_coordinate_discarded_control_keeps_old_cell_law(self):
        from data3001.modelling.markov_position import step
        obs,bins,pool,mapper=self.fixtures()
        x=np.array([-76.05]);y=np.array([33.2]);c=cells(x,y)
        code,*_=step(pool,x,y,c,np.array([1]),0.,np.zeros(1),np.zeros(1),mapper,precise=False)
        self.assertEqual(code[0],obs['cell'][-1])

    def test_zero_displacement_preserves_different_anchor_and_U_absorbs(self):
        from data3001.modelling.markov_position import step
        obs,bins,pool,mapper=self.fixtures(np.full(25,-76.9))
        x=np.array([-76.1,np.nan]);y=np.array([33.8,np.nan]);c=np.array([obs['cell'][0],-3]);b=np.array([1,-3])
        code,nx,ny,nb,_=step(pool,x,y,c,b,0.,np.zeros(2),np.zeros(2),mapper,precise=True)
        self.assertEqual(nx[0],x[0]);self.assertEqual(ny[0],y[0]);self.assertEqual(nb[0],8)
        self.assertEqual(code[1],-3);self.assertTrue(np.isnan(nx[1]))

    def test_transferred_hourly_exit_and_return_is_absorbing(self):
        from data3001.modelling.markov_position import step
        path=np.r_[np.linspace(-80.2,-80.4,13),np.linspace(-80.4,-80.2,13)[1:]]
        obs,bins,pool,mapper=self.fixtures(path)
        x=np.array([-80.95]);y=np.array([33.2]);c=cells(x,y)
        code,nx,ny,b,stats=step(pool,x,y,c,np.array([1]),0.,np.zeros(1),np.zeros(1),mapper,precise=True)
        self.assertEqual(code[0],-2);self.assertEqual(stats['translated_exit'],1)
        code2,*_=step(pool,nx,ny,code,b,0.,np.zeros(1),np.zeros(1),mapper,precise=True)
        np.testing.assert_array_equal(code2,[-2])

    def test_source_exit_unseen_row_backoff_and_whole_cell_U(self):
        from data3001.modelling.markov_position import fit_pool, step
        obs,bins,_,mapper=self.fixtures()
        pool=fit_pool(obs,np.array([0]),np.array([-2]),bins,{1},1)
        x=np.array([-76.5,-70.5]);y=np.array([33.2,33.2]);c=cells(x,y)
        code,*_,stats=step(pool,x,y,c,np.array([7,7]),.3,np.zeros(2),np.zeros(2),mapper,precise=True)
        np.testing.assert_array_equal(code,[-2,-3]);self.assertEqual(stats['row_backoff'],1)

    def test_synthetic_endpoint_land_is_U_not_exit_or_grounding(self):
        from data3001.modelling.markov_position import step
        obs,bins,pool,_=self.fixtures()
        mapper=EndpointMapper(box(-81,20,-8,55),box(-75.9,33.1,-75.7,33.3))
        x=np.array([-76.05]);y=np.array([33.2]);c=cells(x,y)
        code,*_,stats=step(pool,x,y,c,np.array([1]),0.,np.zeros(1),np.zeros(1),mapper,precise=True)
        self.assertEqual(code[0],-3);self.assertEqual(stats['endpoint_geometry_U'],1)

    def test_interior_certificate_never_skips_a_real_boundary_crossing(self):
        from data3001.modelling.markov_position import interior_certificate
        rng=np.random.default_rng(20261027);x=rng.uniform(-81,-8,1000);y=rng.uniform(20,55,1000)
        radius=rng.uniform(0,1e6,1000)
        safe=interior_certificate(x,y,radius,(-81,20,-8,55))
        self.assertTrue(safe.any())
        for az in range(0,360,15):
            xx,yy,_=Geod(ellps='WGS84').fwd(x[safe],y[safe],np.full(safe.sum(),az),radius[safe])
            self.assertTrue(((xx>=-81)&(xx<=-8)&(yy>=20)&(yy<=55)).all())

    def test_invalid_donor_indices_ids_and_hourly_intervals_rejected(self):
        from data3001.modelling.markov_position import fit_pool
        obs,bins,_,_=self.fixtures()
        for start,end,ids in [([0],[24],{2}),([0],[-3],{1}),([0],[23],{1}),([0],[99],{1})]:
            with self.assertRaises(ValueError):fit_pool(obs,np.array(start),np.array(end),bins,ids,1)

    def test_mixture_and_sampling_match_exact_old_joint_probabilities(self):
        from data3001.modelling.markov_position import fit_pool, step, categorical_law
        obs,bins,_,mapper=self.fixtures()
        # Same native origin cell, distinct source categories and destinations.
        obs=np.r_[obs,obs[:1]];obs['id'][-1]=2;obs['lon'][-1]=-76.8
        bins=np.r_[bins,np.int8(2)]
        pool=fit_pool(obs,np.array([0,25]),np.array([24,-2]),bins,{1,2},1)
        cell=int(obs['cell'][0]);law=categorical_law(pool,cell,1,.4)
        self.assertAlmostEqual(law[(int(obs['cell'][24]),8)],.8)
        self.assertAlmostEqual(law[(-2,-2)],.2)
        rng=np.random.default_rng(42);n=20000
        x=np.full(n,-76.5);y=np.full(n,33.2);c=np.full(n,cell);b=np.ones(n,dtype=np.int8)
        code,*_=step(pool,x,y,c,b,.4,rng.random(n),rng.random(n),mapper,precise=False)
        self.assertAlmostEqual(np.mean(code==-2),.2,delta=.01)

    def test_multistep_remainder_sampler_restores_actual_old_operator(self):
        import pandas as pd
        from data3001.modelling.markov_position import OBS_DTYPE,fit_pool,categorical_law,forecast_particles
        from data3001.modelling.markov_velocity import fit_joint_operator,location_forecasts
        tracks=[];velocity=[]
        for sid,(x0,x1,b0,b1) in enumerate([(-76.9,-75.7,1,8),(-76.8,-76.8,2,2),(-75.7,-76.9,8,1)],1):
            a=np.zeros(73,dtype=OBS_DTYPE);a['id']=sid;a['lon']=np.linspace(x0,x1,73);a['lat']=33.2
            a['time']=np.arange(73)*3600;a['source_obs']=np.arange(73);a['cell']=cells(a['lon'],a['lat'])
            _,_,d=Geod(ellps='WGS84').inv(a['lon'][:-1],a['lat'][:-1],a['lon'][1:],a['lat'][1:])
            a['length']=np.r_[0,np.cumsum(d)];tracks.append(a);b=np.full(73,b0,dtype='int8');b[-1]=b1;velocity.append(b)
        obs=np.concatenate(tracks);bins=np.concatenate(velocity);pools={};ops={};records=[]
        cs=sorted(set(obs['cell'])|{int(cells(np.array([-70.5]),np.array([33.2]))[0])})
        for lag in [1,3]:
            origins=np.array([0,73,146]);ends=np.array([lag*24,-2,146+lag*24])
            pools[lag]=fit_pool(obs,origins,ends,bins,{1,2,3},lag)
            for o,e in zip(origins,ends):
                records.append((int(obs['id'][o]),lag,int(obs['cell'][o]),int(obs['cell'][e]) if e>=0 else -2,
                                int(bins[o]),int(bins[e]) if e>=0 else -2,1))
        count=pd.DataFrame(records,columns=['id','horizon_days','origin_cell_1','destination_cell_1',
                                           'origin_atom','destination_atom','pair_count'])
        ops={lag:fit_joint_operator(count,{1,2,3},cs,[.5],.5,lag) for lag in [1,3]}
        mapper=EndpointMapper(box(-81,20,-8,55));start=int(obs['cell'][0])
        for initial in [(start,1),(start,5),(cs[-1],8)]:
            exact={(initial[0],initial[1]):1.}
            for lag in [3,3,1]:
                updated={}
                for (c,b),w in exact.items():
                    law={(c,c):1.} if c<0 else categorical_law(pools[lag],c,b,.4)
                    for key,p in law.items():updated[key]=updated.get(key,0)+w*p
                exact=updated
            expected,u=location_forecasts(ops[3],[initial],7,.4,ops[1])[0];expected[-3]=u
            actual={}
            for (c,b),v in exact.items():actual[c]=actual.get(c,0)+v
            for c in set(actual)|set(expected):self.assertAlmostEqual(actual.get(c,0),expected.get(c,0),places=13)
            lon=-180+initial[0]%360+.2;lat=-90+initial[0]//360+.2
            draw,_=forecast_particles(pools,[lon],[lat],[initial[1]],7,3,.4,40000,42,mapper,precise=False)
            for c,v in expected.items():self.assertAlmostEqual(np.mean(draw==c),v,delta=.008)


if __name__=='__main__':unittest.main()
