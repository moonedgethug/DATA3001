"""Refinement invariants; no scientific-cohort fitting in unit tests."""
import unittest
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import numpy as np
import pandas as pd
import torch

from data3001.modelling.continuous_models import conditional_mdn_s5_e3 as old
from data3001.modelling.continuous_models import conditional_mdn_s5_e4 as new
from data3001.modelling.continuous_models import conditional_mdn_s5_e4_reuse as reuse


class CandidateAndEquivalenceTests(unittest.TestCase):
    def test_exact_registered_candidates(self):
        self.assertEqual(new.K_CANDIDATES, (1,2,3,4,6,8,12,16,18,20,22,32))
        self.assertEqual(reuse.NEW_KS, (3,6,12,18,20,22))
        self.assertEqual(reuse.PARENT_KS, old.K_CANDIDATES)
        for k in (0,5,14,24,64):
            with self.assertRaises(ValueError): new.MDN(k, 1)

    def test_shared_models_exact_forward_and_gradient(self):
        x=torch.tensor([[0.,1.],[-.3,.2],[1.2,-2.]], dtype=torch.float64)
        y=torch.tensor([[.1,.2],[-.2,1.],[3.,-2.]], dtype=torch.float64)
        for k in old.K_CANDIDATES:
            a,b=old.MDN(k, 20261121),new.MDN(k, 20261121)
            for left,right in zip(a(x), b(x)): torch.testing.assert_close(left,right,rtol=0,atol=0)
            old.mixture_nll(a(x),y).mean().backward()
            new.mixture_nll(b(x),y).mean().backward()
            for left,right in zip(a.parameters(),b.parameters()):
                torch.testing.assert_close(left.grad,right.grad,rtol=0,atol=0)

    def test_new_models_valid_full_covariance(self):
        x=torch.zeros((3,2),dtype=torch.float64)
        for k in reuse.NEW_KS:
            model=new.MDN(k, 42);logp,mu,cov=model(x)
            self.assertEqual(model.parameter_count,4352+390*k)
            self.assertEqual(mu.shape,(3,k,2))
            np.testing.assert_allclose(logp.exp().detach().sum(1),1.)
            self.assertGreaterEqual(float(torch.linalg.eigvalsh(cov).min().detach()),.001)

    def test_seed_namespace_unchanged(self):
        for purpose in ('init','shuffle','ES','audit','region','IID'):
            self.assertEqual(old.stable_seed(purpose,'C_T0',2,20261121),
                             new.stable_seed(purpose,'C_T0',2,20261121))


class ReuseTests(unittest.TestCase):
    def packet(self):
        return dict(query_keys=np.array([[1,2,7]],dtype=np.int64),
                    origins=np.array([[-75.,30.]]),pi=np.array([[1.]]),
                    mu=np.array([[[2.,3.]]]),cov=np.eye(2)[None,None],target_scale=np.ones(2))

    def test_parameter_reuse_requires_exact_arrays(self):
        a=self.packet();b={k:v.copy() for k,v in a.items()}
        reuse.validate_compatible_forecast(a,b)
        b['mu'][0,0,0]+=1e-12
        with self.assertRaises(ValueError):reuse.validate_compatible_forecast(a,b)

    def test_reuse_rejects_missing_or_reordered_keys(self):
        a=self.packet();b=self.packet();b['query_keys'][0,1]=3
        with self.assertRaises(ValueError):reuse.validate_compatible_forecast(a,b)
        b=self.packet();del b['cov']
        with self.assertRaises(ValueError):reuse.validate_compatible_forecast(a,b)

    def test_stream_reuse_ignores_source_names_but_not_math(self):
        fields=dict(role='C_T0',mode='inner_energy',count=65536,region_count=65536,
                    query_key_sha256='keys',streams={'seed_scheme':'mdn_s5_e3_v1','node_key_sha256':'nodes'})
        reuse.validate_reuse_streams(fields,{**fields,'source_hashes':{'parent':'old'}})
        for key,value in [('count',131072),('mode','outer_score'),('query_key_sha256','changed'),
                          ('streams',{'node_key_sha256':'changed'})]:
            with self.assertRaises(ValueError):reuse.validate_reuse_streams(fields,{**fields,key:value})

    def test_combination_keeps_every_candidate_and_query(self):
        keys=np.array([[11,21,7],[12,22,7]],dtype=np.int64)
        def rows(ks):return pd.DataFrame([dict(position=i,id=int(x[0]),origin_source_obs=int(x[1]),
            horizon_days=7,K=k,energy_km=float(k+i),excluded=False) for i,x in enumerate(keys) for k in ks])
        a,b=rows([1,2]),rows([3,6])
        result=reuse.merge_rows(b,a,keys,[1,2,3,6],0,2)
        self.assertEqual(len(result),8)
        pd.testing.assert_frame_equal(result[result.K.isin([1,2])].reset_index(drop=True),a)
        with self.assertRaises(ValueError):reuse.merge_rows(b.iloc[:-1],a,keys,[1,2,3,6],0,2)
        with self.assertRaises(ValueError):reuse.merge_rows(pd.concat([b,a.iloc[:1]]),a,keys,[1,2,3,6],0,2)


class IntegrationTests(unittest.TestCase):
    def test_new_candidate_selection_matches_independent_reconstruction(self):
        from contextlib import ExitStack
        from data3001.modelling.continuous_models import conditional_mdn_s5_e4_selection as s
        from data3001.modelling.continuous_models import conditional_mdn_s5_e4_formal_audit as a
        rows=[]
        for role,ids in [('C_T0',[1,1,1,2,2,3]),('C_T1',[2,2,3,4,4,4])]:
            for i,identifier in enumerate(ids):
                for k in new.K_CANDIDATES:
                    value={3:97.,6:94.}.get(k,100.)
                    row=dict(role=role,position=i,id=identifier,origin_source_obs=i+100,
                             horizon_days=7,K=k,model=f'MDN{k}',energy_km=value,variance=0.,
                             audit_energy_km=value,audit_variance=0.,excluded=False)
                    for r in range(8):row[f'es_rep{r}']=row[f'es_audit_rep{r}']=value
                    rows.append(row)
        frame=pd.DataFrame(rows);regions=frame[frame.K.isin([1,6])].copy()
        for prefix in ('','audit_'):
            regions[prefix+'h90']=np.where(regions.K.eq(6),.95,.9)
            regions[prefix+'area90_km2']=np.where(regions.K.eq(6),95.,100.)
            regions[prefix+'replica_area90_km2']=regions[prefix+'area90_km2']
            for field in ('land_mass','outside_D_mass'):regions[prefix+field]=.02
            for field in ('land_variance','outside_variance','hit_disagreement'):regions[prefix+field]=0.
            for field in ('mass_radius','mass_diagnostic'):regions[prefix+field]=.003
            regions[prefix+'rank']=2
        with ExitStack() as stack:
            for name,value in {'INNER_PAIR_COUNTS':{'C_T0':6,'C_T1':6},
                               'INNER_ID_COUNTS':{'C_T0':3,'C_T1':3},'INNER_UNIQUE_IDS':4}.items():
                stack.enter_context(patch.object(s,name,value))
            result=s.apply_quality(s.select_k(frame),regions)
        reference=a.reference_selection(frame,regions)
        a.close(result,reference)
        self.assertEqual(result['selected_k'],6)
        self.assertEqual(result['eligible'],[1,3,6])

    def test_identical_training_updates_and_checkpoint_inference(self):
        from data3001.modelling.continuous_models import conditional_mdn_s5_e3_training as a
        from data3001.modelling.continuous_models import conditional_mdn_s5_e4_training as b
        from data3001.modelling.continuous_models.conditional_mdn_s5_e4_inference import from_checkpoint
        rng=np.random.default_rng(5)
        x=rng.normal(size=(40,2))+[-75.,32.]; y=rng.normal(size=(40,2))*30
        ids=np.repeat(np.arange(10),4)
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as d:
            oldfit=a.train_fixed_epochs(x,y,ids,2,'C_T0',20261121,Path(d)/'old',2)
            newfit=b.train_fixed_epochs(x,y,ids,2,'C_T0',20261121,Path(d)/'new',2)
            for name,value in oldfit.model.state_dict().items():
                torch.testing.assert_close(value,newfit.model.state_dict()[name],rtol=0,atol=0)
            first=from_checkpoint(oldfit.checkpoint_path).mixture(x)
            second=from_checkpoint(newfit.checkpoint_path).mixture(x)
            for name in first:np.testing.assert_array_equal(first[name],second[name])
            with self.assertRaises(ValueError):from_checkpoint(oldfit.checkpoint_path,sha256='bad')

    def test_formal_registry_guards_and_stream_equivalence(self):
        from data3001.modelling.continuous_models import conditional_mdn_s5_e4_formal_scoring as m
        from data3001.modelling.continuous_models import conditional_mdn_s5_e3_formal_scoring as p
        query=pd.DataFrame(dict(id=[11,22],origin_source_obs=[31,42],horizon_days=[7,7]))
        for role,mode in [('C_T0','inner_energy'),('C_outer','outer_score'),('C_outer','outer_audit')]:
            self.assertEqual(m.validate_request(role,mode,new.K_CANDIDATES,65536,65536),new.K_CANDIDATES)
            with self.assertRaises(ValueError):m.validate_request(role,mode,old.K_CANDIDATES,65536,65536)
            self.assertEqual(m.stream_manifest(query,role,mode,65536,65536),
                             p.stream_manifest(query,role,mode,65536,65536))

    def test_audited_parent_copy_resume_and_tamper_rejection(self):
        from data3001.modelling.continuous_models import conditional_mdn_s5_e4_inputs as inp
        cfg=json.loads((inp.ROOT/'configs/conditional_mdn_s5_e4.json').read_text())
        query=inp.cohorts(cfg)['C_T0']['query']
        source=reuse._parent_base()/'C_T0/K1/manifest.json'
        identity=json.loads(source.read_text())['identity']
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            receipt=reuse.import_model(root,'C_T0',1,identity,query)
            self.assertEqual(receipt,reuse.verify_import(root,'C_T0',1,identity,query))
            self.assertEqual((root/'C_T0/K1/manifest.json').read_bytes(),source.read_bytes())
            bad=dict(identity,fit_pairs=identity['fit_pairs']+1)
            with self.assertRaises(ValueError):reuse.verify_import(root,'C_T0',1,bad,query)
            (root/'C_T0/K1/full_refit/checkpoint.pt').write_bytes(b'changed')
            with self.assertRaises(ValueError):reuse.verify_import(root,'C_T0',1,identity,query)

    def test_interrupted_parent_copy_can_resume_without_partial_public_artifact(self):
        from data3001.modelling.continuous_models import conditional_mdn_s5_e4_inputs as inp
        cfg=json.loads((inp.ROOT/'configs/conditional_mdn_s5_e4.json').read_text())
        query=inp.cohorts(cfg)['C_T0']['query']
        source=reuse._parent_base()/'C_T0/K1/manifest.json'
        identity=json.loads(source.read_text())['identity']
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def interrupted(source,target):
                Path(target).write_bytes(b'partial')
                raise InterruptedError('Synthetic interrupted copy')
            with patch.object(reuse.shutil,'copyfile',side_effect=interrupted):
                with self.assertRaises(InterruptedError):reuse.import_model(root,'C_T0',1,identity,query)
            self.assertFalse((root/'C_T0/K1/manifest.json').exists())
            receipt=reuse.import_model(root,'C_T0',1,identity,query)
            self.assertEqual(receipt,reuse.verify_import(root,'C_T0',1,identity,query))

    def test_full_precision_scoring_matches_parent_with_new_k(self):
        from data3001.modelling.continuous_models import conditional_mdn_s5_e4_formal_scoring as m
        from data3001.modelling.continuous_models import conditional_mdn_s5_e3_formal_scoring as p
        packet=dict(origin=np.array([-75.,35.]),weights=np.ones(3)/3,
                    means=np.array([[0.,0.],[3.,15.],[-20.,-4.]]),
                    cholesky=np.tile(np.eye(2)*10,(3,1,1)))
        task=dict(role='C_T0',mode='inner_energy',key=(1,2,7),position=0,
                  target=np.array([-74.8,35.2]),packets={3:packet},count=65536,region_count=65536,iid=False)
        left=pd.DataFrame(p.score_query(task,None,None));right=pd.DataFrame(m.score_query(task,None,None))
        pd.testing.assert_frame_equal(left,right,check_exact=True)


if __name__=='__main__':unittest.main()
