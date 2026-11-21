import unittest
from dataclasses import replace
import numpy as np
from shapely.geometry import box
from data3001.preprocessing.prep_core import cells
from data3001.modelling.markov_position import OBS_DTYPE,GEOD,fit_pool,step,_transferred_exit
from data3001.modelling.neighbourhood import EndpointMapper
from data3001.modelling.markov_iteration_geometry import build_geometry,Geometry


class GeometryTests(unittest.TestCase):
    def fixture(self,path):
        x=np.asarray(path,float);a=np.zeros(len(x),dtype=OBS_DTYPE)
        a['lon']=x;a['lat']=33.2;a['id']=300534067902500;a['time']=np.arange(len(a))*3600
        a['source_obs']=np.arange(len(a));a['cell']=cells(x,a['lat'])
        _,_,d=GEOD.inv(x[:-1],a['lat'][:-1],x[1:],a['lat'][1:]);a['length']=np.r_[0,np.cumsum(d)]
        b=np.full(len(a),8,dtype='int8');p=fit_pool(a,np.array([0]),np.array([len(a)-1]),b,{300534067902500},1)
        return a,p

    def test_cache_and_accelerated_step_equal_reference(self):
        for x in [np.linspace(-76.9,-76.7,25),np.full(25,-76.9),
                  np.r_[np.linspace(-80.2,-80.4,13),np.linspace(-80.4,-80.2,13)[1:]]]:
            a,p=self.fixture(x);g=Geometry(build_geometry(a,np.array([0]),np.array([24]),1),1)
            fast=replace(p,geometry=g);mapper=EndpointMapper(box(-81,20,-8,55))
            rng=np.random.default_rng(8);qx=rng.uniform(-81,-8,200);qy=rng.uniform(20,55,200)
            c=cells(qx,qy);b=np.full(200,8,dtype='int8');u=rng.random(200);v=rng.random(200)
            # Force the donor source cell so the geometry update itself is exercised.
            c[:]=a['cell'][0]
            old=step(p,qx,qy,c,b,.3,u,v,mapper,precise=True)
            new=step(fast,qx,qy,c,b,.3,u,v,mapper,precise=True)
            for k in range(4):np.testing.assert_array_equal(old[k],new[k])

    def test_eastward_path_can_be_certified_close_to_west_boundary(self):
        a,p=self.fixture(np.linspace(-76.9,-73.9,25))
        g=Geometry(build_geometry(a,np.array([0]),np.array([24]),1),1)
        safe=g.certify(a,np.array([0]),np.array([24]),np.array([-80.999]),np.array([33.2]),(-81,20,-8,55))
        self.assertTrue(safe[0])
        old,_,_=_transferred_exit(p,np.array([0]),np.array([24]),np.array([-80.999]),np.array([33.2]),(-81,20,-8,55))
        self.assertFalse(old[0])

    def test_exit_return_is_not_certified_as_safe(self):
        x=np.r_[np.linspace(-80.2,-80.4,13),np.linspace(-80.4,-80.2,13)[1:]];a,p=self.fixture(x)
        g=Geometry(build_geometry(a,np.array([0]),np.array([24]),1),1)
        self.assertFalse(g.certify(a,np.array([0]),np.array([24]),np.array([-80.999]),np.array([33.2]),(-81,20,-8,55))[0])

    def test_invalid_cache_pairs_fail_not_silently_reused(self):
        a,p=self.fixture(np.linspace(-76.9,-76.7,25))
        g=Geometry(build_geometry(a,np.array([0]),np.array([24]),1),1)
        with self.assertRaises(ValueError):g.displacement(np.array([0]),np.array([23]))
        with self.assertRaises(ValueError):build_geometry(a,np.array([0]),np.array([23]),1)
        bad=a.copy();bad['time'][10]+=1
        with self.assertRaises(ValueError):build_geometry(bad,np.array([0]),np.array([24]),1)


if __name__=='__main__':unittest.main()
