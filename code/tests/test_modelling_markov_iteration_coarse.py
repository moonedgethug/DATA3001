import unittest
import numpy as np
import pandas as pd
from data3001.modelling.markov_position import OBS_DTYPE,fit_pool
from data3001.preprocessing.prep_core import cells
from data3001.modelling.markov_velocity import fit_joint_operator,location_forecasts
from data3001.modelling.markov_iteration_coarse import coarse_kernel,coarse_scores


class CoarseIterationTests(unittest.TestCase):
    def test_direct_donor_matrix_equals_old_atomic_matrix_and_schedule_scores(self):
        a=np.zeros(74,dtype=OBS_DTYPE);a['id']=1;a['time']=np.arange(74)*3600
        a['lon']=-76.5;a['lat']=33.2;a['cell']=cells(a['lon'],a['lat'])
        a['lon'][72]=-75.5;a['cell'][72]=a['cell'][0]+1
        a['id'][73]=2;b=np.ones(74,dtype='int8');b[72]=8;b[73]=2
        c=int(a['cell'][0]);state=[c,c+1,c+6];kernels={};old={};records=[]
        for lag in [1,3]:
            o=np.array([0,73]);e=np.array([24*lag,-2]);p=fit_pool(a,o,e,b,{1,2},lag)
            kernels[lag]=coarse_kernel(p,state)
            records.extend([(int(a['id'][i]),lag,c,int(a['cell'][j]) if j>=0 else -2,
                             int(b[i]),int(b[j]) if j>=0 else -2,1) for i,j in zip(o,e)])
        count=pd.DataFrame(records,columns=['id','horizon_days','origin_cell_1','destination_cell_1','origin_atom','destination_atom','pair_count'])
        old={lag:fit_joint_operator(count,{1,2},state,[.5],.5,lag) for lag in [1,3]}
        for lam in [0,.2,1]:
            for lag in [1,3]:np.testing.assert_allclose(kernels[lag].matrix(lam).toarray(),old[lag].matrix(lam).toarray(),atol=1e-15,rtol=0)
        part=pd.DataFrame({'id':[3,3,4],'origin_cell_1':[c,c,c+6],
            'origin_velocity_bin':[1,5,8],'destination_cell_1':[c+1,-2,c]})
        # 3+3+1=7 tests a nontrivial remainder with unseen rows/cells.
        result=coarse_scores(kernels,part,[('probe',.2)],{'probe':(3,3,1)})
        parallel=coarse_scores(kernels,part,[('probe',.2)],{'probe':(3,3,1)},workers=2)
        pd.testing.assert_frame_equal(result,parallel)
        laws=location_forecasts(old[3],list(zip(part.origin_cell_1,part.origin_velocity_bin)),7,.2,old[1])
        expected=np.mean([1-2*p.get(y,0)+sum(v*v for v in p.values())+u*u
                          for (p,u),y in zip(laws,part.destination_cell_1)])
        self.assertAlmostEqual(result.S.iloc[0],expected,places=14)


if __name__=='__main__':unittest.main()
