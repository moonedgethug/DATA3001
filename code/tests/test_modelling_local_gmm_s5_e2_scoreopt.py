"""Scientific equivalence tests for opt-in scoring; no real-data training."""
import copy
import importlib
import importlib.util
import tempfile
import subprocess
import sys
import time
import unittest
from pathlib import Path
import numpy as np

NAME='data3001.modelling.continuous_models.local_gmm_s5_e2_scoreopt'


def packets(origin=(-75.,35.)):
    result={}
    for k in (1,2,3):
        cov=np.array([[[16.+j,2.],[2.,9.+j]] for j in range(k)])
        result[k]=dict(origin=list(origin),K_effective=k,weights=(np.arange(1,k+1)/sum(range(1,k+1))).tolist(),
            means=[[3.*j,-2.*j] for j in range(k)],covariances=cov.tolist(),
            cholesky=np.linalg.cholesky(cov).tolist(),fallback=False)
    return result


class ScoreOptimizationTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec(NAME),'Scoring optimizer not implemented')
        return importlib.import_module(NAME)

    def test_complete_mixture_includes_independent_diagonal_and_both_cross_terms(self):
        m=self.module()
        a=np.array([[[0.,0.,0.]],[[3.,0.,0.]]]);b=np.array([[[2.,0.,0.]],[[7.,0.,0.]]])
        # Truth distance .25*1+.75*2=1.75; self distance .125+1.3125+.1875+2.25=3.875.
        with tempfile.TemporaryDirectory() as d:
            library=m.compile_kernel(Path(d)/'score.dylib')
            np.testing.assert_allclose(m.integrands(a,b,[1.,0.,0.],[.25,.75],library),[-.1875],rtol=0,atol=1e-15)

    def test_replicate_parity_and_no_input_mutation(self):
        m=self.module();from data3001.modelling.continuous_models import local_gmm_s5_e2_numerics as old
        ps=packets();original=copy.deepcopy(ps);key=('fixture',9,12,7)
        with tempfile.TemporaryDirectory() as d:
            library=m.compile_kernel(Path(d)/'score.dylib')
            actual=m.score_models(ps,[-75.1,35.2],8192,key,library)
            for k in ps:
                expected=old.score_es(ps[k],[-75.1,35.2],8192,key)
                np.testing.assert_allclose(actual[k]['replicate_means'],expected['replicate_means'],rtol=0,atol=1e-9)
                self.assertAlmostEqual(actual[k]['variance'],expected['variance'],delta=1e-12)
            self.assertEqual(ps,original)
            self.assertEqual(actual,m.score_models(ps,[-75.1,35.2],8192,key,library))

    def test_fallback_and_single_model_alias_share_exact_values(self):
        m=self.module();ps=packets();ps[3]=dict(copy.deepcopy(ps[1]),fallback=True)
        with tempfile.TemporaryDirectory() as d:
            library=m.compile_kernel(Path(d)/'score.dylib')
            out=m.score_models(ps,[-75.,35.],8192,('fallback',),library)
            self.assertEqual(out[1],out[3])

    def test_geographic_batch_preserves_zero_poles_dateline_and_tails(self):
        m=self.module();from data3001.modelling.continuous_models import conditional_gaussian_s5_e1 as single
        from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
        vectors=np.array([[0.,0.],[1.,2.],[-8000.,6000.],[30000.,-40000.]])
        for origin in [(179.99,80.),(-179.99,-89.),(-75.,35.)]:
            saved=vectors.copy();expected=opt.xyz(single.to_geographic(origin,vectors))
            np.testing.assert_allclose(m.geographic_xyz(origin,vectors),expected,rtol=0,atol=1e-9)
            np.testing.assert_array_equal(vectors,saved)


class ValidationGatesTests(unittest.TestCase):
    def test_changed_replicate_cannot_hide_behind_equal_average(self):
        name=NAME+'_validation'
        self.assertIsNotNone(importlib.util.find_spec(name),'Equivalence gate not implemented')
        m=importlib.import_module(name)
        a=dict(energy_km=1.,replicate_means=[1.]*8,variance=0.,sample_count=65536)
        b=dict(a,replicate_means=[1.01,.99]+[1.]*6)
        with self.assertRaises(AssertionError):m.compare_scores(a,b)
        self.assertEqual(m.compare_scores(a,a)['replicate_max_absolute_km'],0.)

    def test_precision_variance_and_sample_count_are_checked(self):
        name=NAME+'_validation'
        self.assertIsNotNone(importlib.util.find_spec(name),'Equivalence gate not implemented')
        m=importlib.import_module(name)
        a=dict(energy_km=1.,replicate_means=[1.]*8,variance=1e-6,sample_count=65536)
        for b in [dict(a,variance=1e-4),dict(a,sample_count=32768)]:
            with self.assertRaises(AssertionError):m.compare_scores(a,b)


class ProcessBudgetTests(unittest.TestCase):
    def test_cleanup_kills_descendant_after_leader_has_exited(self):
        name=NAME+'_processes'
        self.assertIsNotNone(importlib.util.find_spec(name),'Process-group cleanup missing')
        m=importlib.import_module(name)
        import os,signal,psutil
        with tempfile.TemporaryDirectory() as d:
            pidfile=Path(d)/'pid'
            descendant='import os,signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);open('+repr(str(pidfile))+',"w").write(str(os.getpid()));time.sleep(30)'
            leader=subprocess.Popen([sys.executable,'-c','import subprocess,sys;subprocess.Popen([sys.executable,"-c",'+repr(descendant)+'])'],start_new_session=True)
            try:
                leader.wait(timeout=3)
                limit=time.monotonic()+3
                while (not pidfile.exists() or not pidfile.stat().st_size) and time.monotonic()<limit:time.sleep(.01)
                self.assertTrue(pidfile.exists());pid=int(pidfile.read_text())
                m.stop_group(leader.pid,grace=.1)
                limit=time.monotonic()+1
                while psutil.pid_exists(pid) and psutil.Process(pid).status()!=psutil.STATUS_ZOMBIE and time.monotonic()<limit:time.sleep(.01)
                self.assertTrue(not psutil.pid_exists(pid) or psutil.Process(pid).status()==psutil.STATUS_ZOMBIE)
            finally:
                try:os.killpg(leader.pid,signal.SIGKILL)
                except ProcessLookupError:pass


if __name__=='__main__':unittest.main()
