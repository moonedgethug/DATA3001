"""Selection, quadrature and orchestration invariants on synthetic cases."""
import importlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import json
import time
import concurrent.futures as futures
import multiprocessing as mp

P='data3001.modelling.continuous_models.local_gmm_s5_e2'


def parallel_fit_fixture(seed):
    m=importlib.import_module(P);rng=np.random.default_rng(seed)
    x=np.r_[rng.normal([-4.,0.],.5,(120,2)),rng.normal([4.,0.],.5,(120,2))]
    return m.fit_local(x,np.tile(np.arange(12),20),2,('parallel',seed))


class SelectionTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec(P+'_selection'), 'Selection module missing')
        return importlib.import_module(P+'_selection')

    @staticmethod
    def data():
        return pd.DataFrame([dict(role=f,id=d,query_position=d,model=k,energy_km=e,
            variance=0.,replicate_means=[e]*8,fallback=False)
            for f in ['C_T0','C_T1'] for d in range(12) for k,e in [(1,10.),(2,9.),(3,9.)]])

    def test_equal_performance_selects_simpler(self):
        r=self.module().select_k(self.data())
        self.assertEqual(r['provisional_k'],2)

    def test_bad_second_window_rejects_complex_candidate(self):
        x=self.data();x.loc[(x.role=='C_T1')&(x.model>1),'energy_km']=11
        x['replicate_means']=x.energy_km.map(lambda v:[v]*8)
        self.assertEqual(self.module().select_k(x)['provisional_k'],1)

    def test_repeated_id_gets_one_pooled_vote(self):
        x=pd.DataFrame({'role':['a','b','a'],'id':[1,1,2],'model':[1]*3,'energy_km':[2.,4.,9.]})
        out=self.module().pooled_id_means(x,'energy_km')
        self.assertEqual(out.loc[1,1],3.);self.assertEqual(out[1].mean(),6.)

    def test_fallback_threshold_keeps_failed_cases_in_score(self):
        x=self.data();x.loc[(x.id==0)&(x.model>1),'fallback']=True
        self.assertEqual(self.module().select_k(x)['provisional_k'],1)

    def test_quality_failure_returns_one_without_trying_other_k(self):
        m=self.module();choice={'provisional_k':3}
        rows=[]
        for f in ['C_T0','C_T1']:
            for d in range(10):
                for k in [1,3]:rows.append(dict(role=f,id=d,model=k,h90=.9 if k==1 else .8,
                    area90_km2=10.,land_mass=0.,outside_D_mass=0.,hit_disagreement=0.,area_replica_km2=10.,
                    land_variance=0.,outside_variance=0.))
        self.assertEqual(m.apply_quality(choice,pd.DataFrame(rows))['selected_k'],1)

    def test_geographic_threshold_requires_resolved_uncertainty(self):
        rows=[]
        for f in ['C_T0','C_T1']:
            for d in range(10):
                for k in [1,2]:rows.append(dict(role=f,id=d,query_position=d,model=k,h90=.9 if k==1 else .95,
                    area90_km2=10. if k==1 else 9.,area_replica_km2=10. if k==1 else 9.,
                    land_mass=.1 if k==1 else .109999,outside_D_mass=0.,hit_disagreement=0.,
                    land_variance=1e-6,outside_variance=0.))
        r=self.module().apply_quality({'provisional_k':2},pd.DataFrame(rows))
        self.assertEqual(r['selected_k'],1)


class NumericsTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec(P+'_numerics'),'Numerics missing')
        return importlib.import_module(P+'_numerics')

    def test_all_component_pairs_and_diagonal_are_included(self):
        m=self.module();a=np.array([[[0.,0.,0.]],[[4.,0.,0.]]]);b=a.copy()
        # Empirical mixture: E|X-1|=1.5, E|X-X'|=1.5, ES=.75.
        np.testing.assert_allclose(m.mixture_integrands(a,b,np.array([1.,0.,0.]),np.array([.75,.25])), [.75])

    def test_splitting_identical_component_does_not_change_integrand(self):
        m=self.module();r=np.random.default_rng(9);a=r.normal(size=(1,20,3));b=r.normal(size=(1,20,3));y=np.ones(3)
        one=m.mixture_integrands(a,b,y,np.ones(1))
        two=m.mixture_integrands(np.repeat(a,2,0),np.repeat(b,2,0),y,np.array([.2,.8]))
        np.testing.assert_allclose(one,two,atol=1e-14)

    def test_common_stream_same_law_is_identical_energy(self):
        m=self.module();base=dict(K_effective=1,weights=[1.],means=[[0.,0.]],covariances=[np.eye(2).tolist()],
            cholesky=[np.eye(2).tolist()],origin=[-75.,35.])
        a=m.score_es(base,[-75.,35.],8192,('test',))
        b=m.score_es(base,[-75.,35.],8192,('test',))
        self.assertEqual(a,b);self.assertGreater(a['energy_km'],0.)


class PipelineTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec(P+'_pipeline'),'Pipeline missing')
        return importlib.import_module(P+'_pipeline')

    def test_no_target_release_without_full_freeze(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PermissionError):m.verify_freeze(Path(d),'C_outer',33971)

    def test_roster_reordering_duplicates_and_missing_are_rejected(self):
        m=self.module();keys=np.arange(12).reshape(4,3)
        m.validate_keys(keys,keys)
        for other in [keys[::-1],keys[:3],np.repeat(keys[:1],4,axis=0)]:
            with self.assertRaises(ValueError):m.validate_keys(other,keys)

    def test_one_and_two_spawn_workers_are_identical(self):
        expected=[parallel_fit_fixture(i) for i in [1,2]]
        for count in [1,2]:
            with futures.ProcessPoolExecutor(max_workers=count,mp_context=mp.get_context('spawn')) as pool:
                self.assertEqual(expected,list(pool.map(parallel_fit_fixture,[1,2])))

    def test_interrupted_budget_charges_unknown_interval_conservatively(self):
        m=self.module();self.assertTrue(hasattr(m,'recover_interrupted_budget'))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r=dict(phase='inner',started_epoch=time.time()-120,elapsed_seconds=45.,reserved_seconds=100.,
                receipt_name='attempt_resources.json')
            (p/'active_budget.json').write_text(json.dumps(r))
            m.recover_interrupted_budget(p)
            charged=json.loads((p/'attempt_resources.json').read_text())
            self.assertEqual(charged['elapsed_seconds'],100.)
            self.assertFalse((p/'active_budget.json').exists())
            m.recover_interrupted_budget(p)
            self.assertEqual(len(list(p.glob('*resources.json'))),1)

    def test_family_limit_is_checked_outside_worker_loop(self):
        m=self.module();self.assertTrue(hasattr(m,'check_family_limit'))
        with self.assertRaises(OSError):m.check_family_limit(11*2**30,10)

    def test_worker_target_access_is_reflected_in_parent_receipt(self):
        from types import SimpleNamespace
        m=self.module();self.assertTrue(hasattr(m,'record_worker_access'))
        guard=SimpleNamespace(outcomes_read=False)
        m.record_worker_access({'outer_targets_read':True},guard)
        self.assertTrue(guard.outcomes_read)


class IndependentAuditTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec(P+'_audit'),'Independent audit missing')
        return importlib.import_module(P+'_audit')

    def test_reference_em_arithmetic_agrees_on_soft_responsibilities(self):
        m=self.module();fit=importlib.import_module(P);rng=np.random.default_rng(33)
        z=rng.normal(size=(200,2));w=np.array([.4,.6]);a=np.array([[-1.,0],[1.,.5]])
        b=np.array([[[1.,.2],[.2,2.]],[[.5,0],[0,1.]]])
        ll,r=fit.expectation(z,w,a,b);lr,rr=m.reference_e(z,w,a,b)
        self.assertAlmostEqual(ll,lr,places=12);np.testing.assert_allclose(r,rr,atol=1e-12)
        for x,y in zip(fit.maximize(z,r),m.reference_m(z,r)):np.testing.assert_allclose(x,y,atol=1e-12)

    def test_weighted_region_accepts_nonrational_mixture_probabilities(self):
        m=self.module();rng=np.random.default_rng(4);p=rng.normal(size=(100,2))
        w=np.r_[np.full(50,np.sqrt(2)/200),np.full(50,(1-np.sqrt(2)/4)/50)]
        r=m.reference_region_xy(p,w)
        self.assertGreater(r['area_km2'],0)
        d=p-r['centre'];s=np.einsum('ij,jk,ik->i',d,r['inverse'],d)
        self.assertGreaterEqual(w[s<=r['cutoff']+1e-12].sum(),.9-1e-12)

    def test_iid_disagreement_fails_independent_audit_gate(self):
        m=self.module();self.assertTrue(hasattr(m,'iid_gate'))
        ref=pd.DataFrame({'id':[1,2,3],'energy_km':[2.,2.,2.],'variance':[1e-6]*3,
            'iid_energy_km':[200.,200.,200.],'iid_variance':[1e-6]*3})
        self.assertFalse(m.iid_gate(ref)['passed'])

    def test_selected_forecast_parameters_are_verified_not_just_restart(self):
        m=self.module();fit=importlib.import_module(P);rng=np.random.default_rng(12)
        points=np.array([-75.,35.])+rng.normal(0,.02,(120,2))
        from data3001.modelling.continuous_models import conditional_gaussian_s5_e1 as single
        v=single.to_vectors([-75.,35.],points)
        packet=fit.fit_local(v,np.tile(np.arange(12),10),1,('audit_fixture',))
        packet['means'][0][0]+=100
        with self.assertRaises((ValueError,AssertionError)):
            m.audit_parameters({'origin':[-75.,35.],'models':{'1':packet}},pd.DataFrame({'id':np.tile(np.arange(12),10)}),points)


class ReportDecisionTests(unittest.TestCase):
    def test_lower_coverage_never_called_quality_preserved(self):
        name=P+'_report';self.assertIsNotNone(importlib.util.find_spec(name),'Report missing')
        m=importlib.import_module(name)
        table=pd.DataFrame([dict(id=d,model=k,energy_km=e,h90=h,area90_km2=10.,land_mass=0.,outside_D_mass=0.,
            fallback=False,variance=0.,hit_disagreement=0.,area_replica_km2=10.,land_variance=0.,outside_variance=0.)
            for d in range(10) for k,e,h in [('ExactPoint',10,.9),('EndpointCI',10,.9),('LocalGaussian',10,.9),('LocalGMM',9,.8)]])
        _,_,comparisons=m.compare(table,True)
        self.assertFalse(comparisons.quality_preserved.any())


if __name__=='__main__': unittest.main()
