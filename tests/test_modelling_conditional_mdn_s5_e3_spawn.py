"""Independent process-count invariance on complete synthetic score rows."""
import concurrent.futures
import multiprocessing
import os
import unittest
import numpy as np


def score_fixture(index):
    import torch
    torch.set_num_threads(1)
    from data3001.paths import project_paths
    from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
    from data3001.modelling.continuous_models.conditional_mdn_s5_e3_formal_scoring import score_query
    packets={}
    for k in (1,2,4,8,16,32):
        packets[k]=dict(origin=[-75.+index*.1,35.],weights=np.full(k,1/k),
                        means=np.column_stack((np.linspace(-10,20,k),np.linspace(-5,10,k))),
                        cholesky=np.tile([[15.,0.],[3.,10.]],(k,1,1)))
    task=dict(role='C_outer',mode='outer_score',position=index,key=(999000+index,index,7),
              target=[-74.9,35.1],packets=packets,count=65536,region_count=65536,iid=False)
    return score_query(task,Geography(project_paths()))


class SpawnTests(unittest.TestCase):
    def test_one_and_two_workers_preserve_all_scores_regions_and_replicates(self):
        context=multiprocessing.get_context('spawn')
        for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
            os.environ[name]='1'
        results=[]
        for workers in (1,2):
            with concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=context) as pool:
                results.append(list(pool.map(score_fixture,[0,1])))
        self.assertEqual(results[0],results[1])
        self.assertEqual(sum(len(x) for x in results[0]),12)


if __name__=='__main__':unittest.main()
