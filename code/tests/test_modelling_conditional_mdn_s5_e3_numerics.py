"""Numerical identities and distribution checks, using synthetic inputs only."""
import importlib
import unittest
import numpy as np
from scipy.stats import ncx2


def module():
    try:
        return importlib.import_module('data3001.modelling.continuous_models.conditional_mdn_s5_e3_numerics')
    except ModuleNotFoundError:
        raise AssertionError('MDN full-mixture scoring is not implemented')


def packet(k=1):
    return dict(origin=[-75.,35.],weights=np.full(k,1/k),means=np.zeros((k,2)),
                cholesky=np.repeat((np.eye(2)*10)[None],k,axis=0))


class MixtureNumericsTests(unittest.TestCase):
    def test_tiny_weight_near_floor_and_remote_geographic_tail(self):
        m=module();p=packet(2);p['origin']=[179.9,79.8]
        p['weights']=np.array([1e-12,1-1e-12]);p['means']=np.array([[8000.,1000.],[0,0]])
        p['cholesky']=np.repeat((np.eye(2)*np.sqrt(.001))[None],2,axis=0)
        v=m.draw_vectors(p,np.array([[5e-13,0.,0.],[.5,0.,0.]]))
        np.testing.assert_array_equal(v,p['means'])
        self.assertTrue(np.isfinite(m.to_geographic(p['origin'],v)).all())
        scored=m.score_es(p,[-179.9,79.7],65536,(1,2,7),'C_T0')
        self.assertTrue(np.isfinite(scored['replicates']).all())

    def test_geographic_boundaries_preserve_displacement_and_endpoint(self):
        m=module();v=np.array([[100.,50.],[-80.,-60.],[0,0]])
        for origin in ([179.9,0.],[-179.9,0.],[20.,89.8],[-20.,-89.8]):
            points=m.to_geographic(origin,v)
            np.testing.assert_allclose(m.to_vectors(origin,points),v,atol=1e-6)

    def test_component_permutation_preserves_density(self):
        import torch
        from data3001.modelling.continuous_models.conditional_mdn_s5_e3 import mixture_nll
        logits=torch.tensor([[0.,-27.,3.]],dtype=torch.float64)
        mu=torch.tensor([[[0.,0.],[1000.,800.],[-20.,10.]]],dtype=torch.float64)
        cov=torch.tensor([[[[.001,0],[0,.001]],[[10.,3.],[3.,5.]],[[2.,.3],[.3,1.]]]],dtype=torch.float64)
        obs=torch.tensor([[.1,.2]],dtype=torch.float64)
        order=[2,0,1];pi=torch.log_softmax(logits,-1)
        np.testing.assert_allclose(mixture_nll((pi,mu,cov),obs),mixture_nll((pi[:,order],mu[:,order],cov[:,order]),obs),rtol=0,atol=1e-12)

    def test_shared_nodes_are_immutable_and_can_be_reused(self):
        m=module();u=m.uniforms(1024,6,'ES',0,('1','2','7'))
        self.assertFalse(u.flags.writeable)
        self.assertIs(u,m.uniforms(1024,6,'ES',0,('1','2','7')))
    def test_component_draw_retains_small_component_and_pair_independence(self):
        m=module();p=packet(2);p['weights']=np.array([.999,.001]);p['means'][1]=[1000,0]
        u=np.array([[.1,0.,.2],[.9999,0.,.2]])
        np.testing.assert_allclose(m.draw_vectors(p,u),[[0,0],[1000,0]])
        a=np.array([[1.,2.,3.],[3.,4.,5.]])
        b=np.array([[9.,8.,7.],[6.,5.,4.]])
        y=np.array([.4,.3,.2])
        np.testing.assert_allclose(m.integrands(a,b,y),np.linalg.norm(a-y,axis=1)-.5*np.linalg.norm(a-b,axis=1))

    def test_identical_components_match_single_law_and_analytic_local_es(self):
        m=module();p=packet();q=packet(32)
        first=m.uniforms(65536,6,'ES',0,('1','2','7'))
        a=m.draw_vectors(p,first[:,:3]);b=m.draw_vectors(q,first[:,:3])
        np.testing.assert_array_equal(a,b)
        # At a zero truth, 2D isotropic Gaussian ES is sigma*sqrt(pi)*(1/sqrt(2)-.5).
        got=m.integrands(np.column_stack([a,np.zeros(len(a))]),
                         np.column_stack([m.draw_vectors(p,first[:,3:]),np.zeros(len(a))]),np.zeros(3)).mean()
        expected=10*np.sqrt(np.pi)*(1/np.sqrt(2)-.5)
        self.assertAlmostEqual(got,expected,delta=.01)

    def test_ecef_matches_independent_ellipsoid_formula(self):
        m=module();lonlat=np.array([[-75,35],[0,0],[179.9,89.9],[-179.9,-89.9]])
        lo,la=np.deg2rad(lonlat).T;a=6378.137;e2=1-(6356.752314245179/a)**2
        n=a/np.sqrt(1-e2*np.sin(la)**2)
        expected=np.column_stack([n*np.cos(la)*np.cos(lo),n*np.cos(la)*np.sin(lo),n*(1-e2)*np.sin(la)])
        np.testing.assert_allclose(m.xyz(lonlat),expected,atol=1e-9)

    def test_round_trip_and_region_mass(self):
        m=module();p=packet(4);p['means']=np.array([[-100,0],[100,0],[0,-80],[0,80]],float)
        v=np.array([[0,0],[100,150],[-200,-50]],float)
        np.testing.assert_allclose(m.to_vectors(p['origin'],m.to_geographic(p['origin'],v)),v,atol=1e-6)
        r=m.build_region(p,65536,('1','2','7'),'test',geography=None)
        self.assertEqual(r['region']['rank'],2)
        self.assertLess(r['mass_check']['radius'],.005)
        self.assertLess(r['mass_check']['diagnostic'],.005)
        self.assertGreater(r['region']['area_km2'],0)

    def test_six_dimensional_stream_deterministic_distinct_halves(self):
        m=module();a=m.uniforms(1024,6,'ES',2,('1','2','7'))
        np.testing.assert_array_equal(a,m.uniforms(1024,6,'ES',2,('1','2','7')))
        self.assertFalse(np.array_equal(a[:,:3],a[:,3:]))
        self.assertFalse(np.array_equal(a,m.uniforms(1024,6,'ES',3,('1','2','7'))))

    def test_score_reference_consistency_and_repeatability(self):
        m=module();p=packet(2);p['means']=np.array([[-50.,-20.],[50,30]])
        a=m.score_es(p,[-74.8,35.2],65536,('1','2','7'),'C_T0')
        b=m.score_es(p,[-74.8,35.2],65536,('1','2','7'),'C_T0')
        self.assertEqual(a,b)
        self.assertEqual(len(a['replicates']),8)
        self.assertGreater(a['variance'],0)
        ref=m.reference_component_es(p,[-74.8,35.2],8192,('1','2','7'),'C_T0')
        self.assertLess(abs(a['energy_km']-ref['energy_km']),3*np.sqrt(a['variance']+ref['variance']))

    def test_invalid_probabilities_cannot_be_silently_normalized(self):
        m=module();p=packet(2);p['weights']=np.array([.2,.3])
        with self.assertRaises(ValueError):m.draw_vectors(p,np.zeros((1,3)))

