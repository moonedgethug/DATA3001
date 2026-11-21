"""Finite reference checks for numerical reuse, centering and stream isolation."""
import inspect
import unittest
import numpy as np
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
from data3001.modelling.baselines import seasonal_exact_position_s4_e9 as old
from data3001.modelling.baselines import position_error_s4_e8 as geo
from data3001.modelling.baselines.seasonal_exact_position_s4_e9_inputs import Guard


def fixture(missing=False):
    p=np.array([[-75.,35.],[-74.,36.],[-73.,35.],[-75.,35.]])
    ok=np.zeros(4,bool) if missing else np.array([True,False,True,True])
    sd=geo.equivalent_sd(p,np.full((4,2),.002),ok)
    return opt.Pool(p,sd,ok,opt.xyz(p),opt.xy(p),np.zeros(4,bool),np.zeros(4,bool))


class OptimizationTests(unittest.TestCase):
    def test_split_transforms_are_identical(self):
        p=fixture();a,b=geo.coordinates(p.points)
        np.testing.assert_array_equal(a,p.xyz);np.testing.assert_array_equal(b,p.xy)

    def test_exact_squared_distance_mean_and_zero_mean_control(self):
        p=fixture();dist=np.linalg.norm(p.xyz[:,None,:]-p.xyz[None,:,:],axis=2)
        mu=2*np.mean(np.sum((p.xyz-p.xyz.mean(axis=0))**2,axis=1))
        np.testing.assert_allclose(mu,np.mean(dist**2),rtol=1e-13)
        for b in [0.,.0001,.01]:
            np.testing.assert_allclose(np.mean(dist-b*(dist**2-mu)),dist.mean(),atol=1e-10,rtol=0)

    def test_calibration_uses_independent_stream_and_no_target(self):
        p=fixture();base=('s4_e9','fixture',1,2,7,'Annual')
        c=opt.calibration(p,base)
        g=geo.rng_for(*base,'e9_es_control_calibration_v1')
        a,b=g.integers(4,size=1024),g.integers(4,size=1024)
        d=np.linalg.norm(p.xyz[a]-p.xyz[b],axis=1);q=d*d
        expected=np.cov(d,q,ddof=1)[0,1]/np.var(q,ddof=1)
        self.assertAlmostEqual(c['coefficient'],expected,places=13)
        self.assertEqual(c,opt.calibration(p,base))
        self.assertNotIn('truth',inspect.signature(opt.calibration).parameters)
        main=geo.rng_for(*base,0,'energy').integers(4,size=1024)
        self.assertFalse(np.array_equal(a,main))

    def test_exact_reuse_score_and_regions(self):
        p=fixture();key=('reuse',0);truth=[-74.,35.]
        before,_=old.predict_pool(p.points,p.sd,p.usable,key=key,energy_count=4096,region_count=256)
        after,_=opt.regions(p,key,256)
        original=old.score_pool(p.points,p.sd,p.usable,before,truth,key)
        got=opt.score(p,after,truth,key,4096,dict(coefficient=0.,mean_squared=0.))
        for ci in [False,True]:
            self.assertEqual(before[ci]['region'],after[ci]['region'])
            for metric in ['energy_km','energy_mc_se','h90','area90_km2']:
                self.assertAlmostEqual(original[ci][metric],got[ci][metric],places=10)

    def test_controlled_ci_includes_full_covariance(self):
        p=fixture();base=('variance',);key=(*base,0);truth=np.array([-74.,35.])
        c=opt.calibration(p,base);f,_=opt.regions(p,key,256)
        before=repr(f);s=opt.score(p,f,truth,key,4096,c)
        x,original,first,d,dd=old.draws(p.points,p.sd,4096,key)
        y=geo.coordinates(truth[None,:])[0][0]
        inc=np.linalg.norm(first-y,axis=1)-np.linalg.norm(original-y,axis=1)-.5*dd
        z=-.5*(d-c['coefficient']*(d*d-c['mean_squared']))+inc
        expected=np.linalg.norm(x-y,axis=1).mean()+z.mean()
        self.assertAlmostEqual(s[True]['energy_km'],expected,places=11)
        self.assertAlmostEqual(s[True]['energy_mc_se'],z.std(ddof=1)/64,places=11)
        self.assertEqual(before,repr(f))

    def test_missing_ci_and_degenerate_control(self):
        p=fixture(missing=True);f,_=opt.regions(p,('missing',0),256);c=opt.calibration(p,('missing',))
        s=opt.score(p,f,[-74.,35.],('missing',0),4096,c)
        self.assertEqual(s[False],s[True])
        one=p.take(np.array([0]));c=opt.calibration(one,('one',))
        self.assertEqual(c['coefficient'],0.);self.assertTrue(c['degenerate']);self.assertEqual(c['mean_squared'],0.)

    def test_cache_slice_is_immutable(self):
        p=fixture();q=p.take(np.array([3,0,2]))
        np.testing.assert_array_equal(q.xyz,p.xyz[[3,0,2]])
        with self.assertRaises(ValueError):q.xyz[0,0]=0
        self.assertGreater(q.bytes,0)

    def test_outer_endpoints_stay_sealed(self):
        from pathlib import Path
        root=Path('/tmp/e9_guard_fixture')
        guard=Guard(root,dict(results=root/'results/runs/new',provenance=root/'provenance/runs/new'))
        with self.assertRaises(PermissionError):guard('open',(str(root/'outer_targets.parquet'),'rb',0))


if __name__=='__main__':unittest.main()
