"""Full-run invariants on small independent fixtures, no project outcomes."""
import importlib
import importlib.util
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import tempfile
import json
import time
import concurrent.futures
import numpy as np
import pandas as pd

BASE='data3001.modelling.continuous_models.conditional_gaussian_s5_e1_'


class FullRunTests(unittest.TestCase):
    def module(self,suffix):
        self.assertIsNotNone(importlib.util.find_spec(BASE+suffix),'Full-run module missing')
        return importlib.import_module(BASE+suffix)

    def test_lineage_roundtrip_preserves_order_ties_and_empty_lists(self):
        m=self.module('full')
        values=[np.array([8,2,5]),np.array([],dtype=int),np.array([12,12])]
        flat,offset=m.pack_lineages(values)
        np.testing.assert_array_equal(flat,[8,2,5,12,12])
        np.testing.assert_array_equal(offset,[0,3,3,5])
        for i,value in enumerate(values):np.testing.assert_array_equal(m.unpack_lineage(flat,offset,i),value)

    def test_complete_freeze_rejects_missing_duplicate_or_reordered_keys(self):
        m=self.module('full')
        expected=np.array([[10,1,7],[10,2,7],[20,1,7]])
        m.validate_keys(expected,expected)
        for keys in [expected[:2],expected[[0,0,2]],expected[[1,0,2]]]:
            with self.assertRaises(ValueError):m.validate_keys(keys,expected)

    def test_equal_id_summary_is_not_pair_weighted(self):
        m=self.module('analysis')
        table=pd.DataFrame(dict(id=[1,1,1,2],model=['A']*4,energy_km=[0.,0.,0.,8.],h90=[1.,1.,1.,0.],area90_km2=[10.]*4))
        summary,per_id=m.summarize(table)
        self.assertAlmostEqual(summary.loc['A','energy_km'],4.)
        self.assertAlmostEqual(summary.loc['A','h90'],.5)
        self.assertEqual(len(per_id),2)

    def test_quality_rule_does_not_hide_observed_hit_degradation(self):
        m=self.module('analysis')
        decision=m.decision(es_delta=-1.,es_relative=-.01,es_upper=-.5,hit_delta=-.001,hit_lower=-.005,
            area_ratio=.99,area_upper=1.,land_delta=0.,outside_delta=0.,numerical=True)
        self.assertFalse(decision['quality_preserved'])
        self.assertFalse(decision['eligible'])
        self.assertTrue(decision['es_benefit'])

    def test_independent_gaussian_covariance_uses_n_and_full_correlation(self):
        m=self.module('reference')
        v=np.array([[0.,0.],[2.,2.],[4.,0.]])
        packet=m.fit_vectors(v)
        np.testing.assert_allclose(packet['mean'],[2.,2/3])
        np.testing.assert_allclose(packet['covariance'],[[8/3,0.],[0.,8/9]])

    def test_independent_region_integer_quantile_and_exact_membership(self):
        m=self.module('reference')
        p=np.array([[-1.,0.],[0.,1.],[1.,0.],[0.,-1.]])
        reg=m.region_xy(p,np.full(4,.25))
        self.assertAlmostEqual(reg['cutoff'],2.)
        self.assertAlmostEqual(reg['area_km2'],np.pi)
        np.testing.assert_array_equal(m.inside(np.array([[0.,0.],[1.,0.],[2.,0.]]),reg),[True,True,False])

    def test_unbiased_auxiliary_uses_independent_mean_cross_product(self):
        m=self.module('analysis')
        self.assertAlmostEqual(m.auxiliary(100.,np.array([2.,0.,0.]),np.array([0.,2.,0.]),np.zeros(3)),1.)

    def test_failed_scoring_never_claims_outer_targets_were_unread(self):
        m=self.module('full')
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);guard=SimpleNamespace(outcomes_read=False,outcomes_allowed=False)
            (folder/'full_preflight.json').write_text('{"passed":true}')
            def publish(path,writer):
                with path.open('wb') as f:writer(f)
            class Budget:
                def __init__(self,*args):pass
                def finish(self,*args):pass
            with patch.object(m.inp,'context',return_value=(SimpleNamespace(publish=publish),{'results':folder,'provenance':folder},{},{},guard)),patch.object(m.inp,'Budget',Budget),patch.object(m.inp,'freeze_sources'),patch.object(m,'verify_freeze'),patch.object(m,'execute_parallel',side_effect=RuntimeError('Worker failed after target release')):
                with self.assertRaises(RuntimeError):m.main('fixture','score')
            receipt=json.loads((folder/'score_stopped.json').read_text())
            self.assertTrue(receipt['outer_targets_read'])

    def test_failed_executor_terminates_its_running_child(self):
        m=self.module('full')
        self.assertTrue(hasattr(m,'stop_workers'))
        pool=concurrent.futures.ProcessPoolExecutor(max_workers=1)
        pool.submit(time.sleep,30)
        started=time.monotonic();m.stop_workers(pool)
        self.assertLess(time.monotonic()-started,3.)

    def test_full_precision_rejects_unresolved_es_variance(self):
        m=self.module('verify')
        rows=[]
        for q in range(2):
            for model in ['ExactPoint','EndpointCI','LocalGaussian']:
                rows.append(dict(query_position=q,id=q,model=model,energy_km=100.,variance=0.,h90=1.,h90_replica=1.,
                    area90_km2=20.,area_replica_km2=20.,hit_disagreement=0.,mass_diagnostic=0.,mass_radius=0.,
                    land_variance=0.,outside_variance=0.,rank=2))
        data=pd.DataFrame(rows)
        self.assertTrue(m.precision(data,expected_cases=2)['passed'])
        data.loc[data.model.eq('LocalGaussian'),'variance']=4.
        self.assertFalse(m.precision(data,expected_cases=2)['passed'])

    def test_full_precision_rejects_model_specific_roster(self):
        m=self.module('verify')
        data=pd.DataFrame(dict(query_position=[0,0,1],id=[1,1,2],model=['ExactPoint','EndpointCI','LocalGaussian']))
        with self.assertRaises(ValueError):m.precision(data,expected_cases=1)

    def test_companion_cannot_pass_claim_hierarchy_when_primary_es_fails(self):
        m=self.module('verify');a=self.module('analysis')
        rows=[]
        for i in [1,2]:
            for model,es,area in [('ExactPoint',100.,20.),('EndpointCI',102.,20.),('LocalGaussian',101.,19.)]:
                rows.append(dict(query_position=i,id=i,model=model,energy_km=es,h90=1.,area90_km2=area,
                    area_replica_km2=area,hit_disagreement=0.,land_mass=0.,outside_D_mass=0.,land_variance=0.,outside_variance=0.))
        primary=pd.DataFrame(rows);_,_,comparison,_=a.compare(primary)
        checks={'models':{name:{'hit_disagreement':0.} for name in ['ExactPoint','EndpointCI','LocalGaussian']},
                'contrasts':{'ExactPoint':{'es_improvement_numerically_resolved':False},'EndpointCI':{'es_improvement_numerically_resolved':True}}}
        precision={'degenerate_region_cases':{name:0 for name in ['ExactPoint','EndpointCI','LocalGaussian']}}
        answer=m.claim_resolution(primary,primary,comparison,checks,precision).set_index('baseline')
        self.assertFalse(answer.loc['EndpointCI','superiority_claim_allowed'])
        self.assertFalse(answer.loc['EndpointCI','eligible'])

    def test_replica_validation_detects_wrong_primary_hit_on_frozen_region(self):
        m=self.module('verify')
        self.assertTrue(hasattr(m,'validate_original_metrics'))
        p=pd.DataFrame(dict(query_position=[0],id=[1],model=['ExactPoint'],h90=[0.],area90_km2=[10.]))
        r=pd.DataFrame(dict(query_position=[0],id=[1],model=['ExactPoint'],original_h90=[1.],original_area90_km2=[10.]))
        with self.assertRaises(ValueError):m.validate_original_metrics(p,r)

    def test_independent_per_id_arithmetic_uses_full_id_denominators(self):
        m=self.module('verify')
        self.assertTrue(hasattr(m,'manual_per_id'))
        p=pd.DataFrame(dict(id=[1,1,2],model=['A']*3,energy_km=[2.,4.,8.],h90=[1.,0.,1.],area90_km2=[10.,20.,30.],variance=[4.,4.,9.]))
        answer=m.manual_per_id(p).set_index('id')
        self.assertEqual(answer.loc[1,'energy_km'],3.)
        self.assertEqual(answer.loc[1,'variance'],2.)
        self.assertEqual(answer.loc[2,'energy_km'],8.)

    def test_failed_report_still_records_execution_budget(self):
        m=self.module('full_report')
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);guard=SimpleNamespace(outcomes_read=False)
            def publish(path,writer):
                with path.open('wb') as f:writer(f)
            class Budget:
                def __init__(self,*args):pass
                def finish(self,*args):
                    (folder/'resource_receipt.json').write_text(json.dumps({'completed':args[2]}))
            with patch.object(m.inp,'context',return_value=(SimpleNamespace(publish=publish),{'results':folder,'provenance':folder},{},{},guard)),patch.object(m.inp,'Budget',Budget):
                with self.assertRaises(FileNotFoundError):m.report('fixture')
            self.assertTrue((folder/'resource_receipt.json').exists())
            self.assertFalse(json.loads((folder/'resource_receipt.json').read_text())['completed'])

    def test_iid_audit_cannot_ignore_a_disagreeing_primary_estimate(self):
        m=self.module('verify')
        self.assertTrue(hasattr(m,'iid_comparison'))
        selected=pd.DataFrame(dict(query_position=[0,1],id=[1,2],energy_km=[0.,0.],variance=[.01,.01],iid_energy_km=[0.,0.],iid_variance=[.01,.01]))
        primary=pd.DataFrame(dict(query_position=[0,1],id=[1,2],energy_km=[10.,10.],variance=[.01,.01]))
        answer=m.iid_comparison(selected,primary)
        self.assertTrue(answer['audit_passed'])
        self.assertFalse(answer['primary_passed'])
        self.assertFalse(answer['passed'])


if __name__=='__main__':unittest.main()
