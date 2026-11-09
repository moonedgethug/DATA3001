import concurrent.futures as cf
import multiprocessing as mp
import time
import unittest

import compare_backends as target

STOP=None


def worker_init(event):
    global STOP
    STOP=event


def failing_worker(index):
    if index==0:raise RuntimeError('intentional-worker-failure')
    if not STOP.wait(5):raise RuntimeError('cancellation-was-not-signalled')
    return index


class ValidationGuardTests(unittest.TestCase):
    def test_exact_comparison_rejects_unchecked_mean_or_variance_fields(self):
        a=[{'K':1,'geography_input_hashes':[],
            'energy':{'replicates':[1.]*8,'variance':0.,'energy_km':1.},
            'audit_energy':{'replicates':[1.]*8,'variance':0.},
            'region':{'region':{'rank':2,'area_km2':1.,'centre':[0.,0.],'covariance':[[1.,0.],[0.,1.]],'inverse':[[1.,0.],[0.,1.]],'cutoff':1.,'attained_mass':.9},
                      'replica_region':{'rank':2,'area_km2':1.,'centre':[0.,0.],'covariance':[[1.,0.],[0.,1.]],'inverse':[[1.,0.],[0.,1.]],'cutoff':1.,'attained_mass':.9},
                      'mass_check':{},'land_mass':0.,'outside_D_mass':0.},
            'metrics':{'h90':1.,'hit_disagreement':0.,'rank':2},
            'audit_metrics':{'h90':1.,'hit_disagreement':0.,'rank':2}}]
        import copy
        a[0]['audit_region']=copy.deepcopy(a[0]['region'])
        b=copy.deepcopy(a);b[0]['energy']['energy_km']=999.
        with self.assertRaises(ArithmeticError):target.compare(a,b)

    def test_worker_failure_signals_cancellation_instead_of_draining_full_queue(self):
        self.assertTrue(hasattr(target,'collect_results'),'Fail-fast collection is missing')
        ctx=mp.get_context('spawn');event=ctx.Event()
        pool=cf.ProcessPoolExecutor(max_workers=2,mp_context=ctx,initializer=worker_init,initargs=(event,))
        futures=[pool.submit(failing_worker,i) for i in range(8)]
        start=time.monotonic()
        with self.assertRaisesRegex(RuntimeError,'intentional-worker-failure'):
            list(target.collect_results(pool,futures,event))
        self.assertTrue(event.is_set())
        self.assertLess(time.monotonic()-start,4.)
