"""Scientific invariants for the approved continuous E8 experiment."""
import unittest
import numpy as np

from data3001.modelling.baselines import position_error_s4_e8 as e


class ContinuousErrorTests(unittest.TestCase):
    def setUp(self):
        self.p=np.array([[-75.,35.],[-74.,36.],[-73.,35.],[-74.,34.]])
        self.h=np.full((4,2),.002)
        self.ok=np.array([True,False,True,True])
        self.sd=e.equivalent_sd(self.p,self.h,self.ok)

    def test_width_units_and_missing_mask(self):
        sd=e.equivalent_sd(np.array([[0.,0.],[0.,60.]]),np.ones((2,2)),np.ones(2,bool))
        self.assertAlmostEqual(sd[0,0]*e.Z95,111.31949,places=4)
        self.assertLess(sd[1,0],.51*sd[0,0])
        np.testing.assert_array_equal(self.sd[1],0)
        with self.assertRaises(ValueError):e.equivalent_sd(self.p,-self.h,self.ok)

    def test_cloud_retains_each_vote(self):
        p,w,labels=e.component_cloud(self.p,self.sd,self.ok,128,('fixture',))
        np.testing.assert_allclose(np.bincount(labels,weights=w),.25,atol=1e-15)
        np.testing.assert_array_equal(p[labels==1],self.p[1:2])
        self.assertLessEqual(len(p),128)

    def test_geodesic_radius_and_point_fallback(self):
        normals=np.array([[1.,0.]]*4)
        p=e.perturbed(self.p,self.sd,normals)
        _,_,d=e.GEOD.inv(self.p[:,0],self.p[:,1],p[:,0],p[:,1])
        np.testing.assert_allclose(d,self.sd[:,0]*1000,atol=1e-8)
        np.testing.assert_array_equal(p[1],self.p[1])

    def test_matched_variance_and_one_usable(self):
        c=e.covariance_matched(self.sd,self.ok)
        np.testing.assert_allclose((c*c).mean(axis=0),(self.sd*self.sd).mean(axis=0))
        one=np.array([True,False,False,False]);s=e.equivalent_sd(self.p,self.h,one)
        np.testing.assert_array_equal(e.covariance_matched(s,one),s)

    def test_quantile_ties(self):
        q=e.weighted_quantile(np.array([0.,1.,1.,2.]),np.array([.1,.4,.4,.1]))
        self.assertEqual(q,1.)

    def test_exact_ninety_percent_uniform_cloud(self):
        for n in [8000,16000,16384,32768]:
            expected=(9*n+9)//10-1
            self.assertEqual(e.weighted_quantile(np.arange(n),np.full(n,1/n)),expected)

    def test_exact_mixed_point_and_cloud_weights(self):
        units=np.tile([1,1,2],4000);w=units/units.sum()
        expected=np.searchsorted(np.cumsum(units),(9*int(units.sum())+9)//10)
        self.assertEqual(e.weighted_quantile(np.arange(len(units)),w),expected)

    def test_quantile_keeps_small_real_mass_gap(self):
        self.assertEqual(e.weighted_quantile(np.arange(3),np.array([.9-1e-10,1e-10,.1])),1.)

    def test_covariance_ellipse_and_area(self):
        theta=np.linspace(0,2*np.pi,10000,endpoint=False)
        xy=np.column_stack([2*np.cos(theta),3*np.sin(theta)])
        r=e.fit_region(xy)
        self.assertAlmostEqual(r['area_km2'],6*np.pi,places=8)
        self.assertTrue(e.inside_region(np.array([[0.,0.]]),r)[0])
        self.assertFalse(e.inside_region(np.array([[4.,0.]]),r)[0])

    def test_degenerate_region_is_not_strip(self):
        r=e.fit_region(np.array([[0.,0.],[1.,0.],[2.,0.]]))
        self.assertEqual(r['rank'],1);self.assertEqual(r['area_km2'],0)
        self.assertFalse(e.inside_region(np.array([[1.,1.]]),r)[0])
        r=e.fit_region(np.array([[3.,4.]]));self.assertEqual(r['rank'],0)
        self.assertFalse(e.inside_region(np.array([[3.,4.1]]),r)[0])

    def test_all_missing_equals_point_measure(self):
        no=np.zeros(4,bool);sd=np.zeros((4,2))
        f,_=e.predict(self.p,sd,no,energy_count=128,region_count=128,key=('missing',))
        score=e.evaluate(self.p,sd,no,f,[-74.,35.],key=('missing',))
        for name in ['EndpointCI','MatchedSpread']:
            self.assertEqual(f[name]['region'],f['ExactPoint']['region'])
            self.assertEqual(score[name]['energy_km'],score['ExactPoint']['energy_km'])

    def test_single_atom_energy_is_distance(self):
        p=self.p[:1];sd=np.zeros((1,2));no=np.zeros(1,bool)
        f,_=e.predict(p,sd,no,energy_count=64,region_count=64,key=('atom',))
        score=e.evaluate(p,sd,no,f,[-74.,35.],key=('atom',))
        xyz,_=e.coordinates(np.array([p[0],[-74.,35.]]))
        self.assertAlmostEqual(score['ExactPoint']['energy_km'],np.linalg.norm(xyz[0]-xyz[1]))

    def test_point_energy_matches_small_exact_sum(self):
        f=e.point_forecast(self.p,count=65536,key=('score',));y=np.array([-74.,35.])
        got=e.evaluate_point(self.p,f,y)['energy_km']
        xyz,_=e.coordinates(self.p);truth,_=e.coordinates(y[None,:])
        exact=np.linalg.norm(xyz-truth,axis=1).mean()-.5*np.linalg.norm(xyz[:,None,:]-xyz[None,:,:],axis=2).mean()
        self.assertLess(abs(got-exact),4*f['correction_se'])

    def test_random_streams_reproducible(self):
        a=e.rng_for('role',3,7).standard_normal(20);b=e.rng_for('role',3,7).standard_normal(20)
        np.testing.assert_array_equal(a,b)
        self.assertFalse(np.array_equal(a,e.rng_for('role',3,8).standard_normal(20)))

    def test_forecast_does_not_depend_on_validation_outcome(self):
        f,_=e.predict(self.p,self.sd,self.ok,energy_count=64,region_count=128,key=('freeze',))
        before=repr(f)
        e.evaluate(self.p,self.sd,self.ok,f,[-74.,35.],key=('freeze',))
        e.evaluate(self.p,self.sd,self.ok,f,[-70.,38.],key=('freeze',))
        self.assertEqual(repr(f),before)

if __name__=='__main__':unittest.main()
