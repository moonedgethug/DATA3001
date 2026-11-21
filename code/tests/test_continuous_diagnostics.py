import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import torch
from shapely.geometry import box
from data3001.modelling.continuous import TransitionMixture, to_state
from data3001.modelling.continuous_diagnostics import (
    run_lengths, select_queries, physical_moments, failure_reasons, trace,
)
from data3001.modelling.run_continuous import rollout
from data3001.modelling.neighbourhood import EndpointMapper


class DiagnosticTests(unittest.TestCase):
    def test_contiguous_runs_do_not_bridge_gaps(self):
        np.testing.assert_array_equal(run_lengths([3,4,5,8,11,12]), [3,1,2])
        self.assertEqual(len(run_lengths([])),0)
        with self.assertRaises(ValueError): run_lengths([2,2])

    def test_query_weights_recover_ID_population_sizes(self):
        q=pd.DataFrame({'id':[1]*7+[2]*3,'origin':np.arange(10)})
        s=select_queries(q,2,seed=9)
        self.assertEqual(len(s),4)
        np.testing.assert_allclose(s.groupby('id').diagnostic_weight.sum(),[7,3])
        pd.testing.assert_frame_equal(s,select_queries(q,2,seed=9))

    def test_mixture_variance_includes_separated_centres(self):
        lp=torch.log(torch.tensor([[.25,.75]]))
        mu=torch.tensor([[[-1.]*4,[1.]*4]])
        chol=torch.eye(4).expand(1,2,4,4)
        m,v=physical_moments((lp,mu,chol),torch.zeros(8),torch.ones(8))
        np.testing.assert_allclose(m,[[.5]*4])
        np.testing.assert_allclose(v,[[1.75]*4])

    def test_failure_causes_are_exclusive(self):
        s=to_state(np.zeros(5),np.array([30,30,30,91,30]),np.zeros(5),np.zeros(5))
        s[-1,-1]=np.nan
        np.testing.assert_array_equal(failure_reasons(s,[0,-2,-1,-1,-1]),[0,1,2,4,3])

    def test_tracer_reproduces_production_rollout(self):
        torch.manual_seed(3); model=TransitionMixture(3)
        dtype=[('lon','f8'),('lat','f8'),('ve','f8'),('vn','f8'),('id','i8'),('time','i8'),('cell','i4')]
        obs=np.zeros(7,dtype=dtype);obs['lat']=30;obs['ve']=.4;obs['id']=1;obs['time']=np.arange(7)*3600
        mapper=EndpointMapper(box(-.01,29,.015,31),box(.005,29,.009,31))
        obs['cell']=mapper(obs['lon'],obs['lat'])
        q=pd.DataFrame({'id':[1],'origin':[0],'diagnostic_weight':[1.]})
        x=to_state(obs['lon'][:1],obs['lat'][:1],obs['ve'][:1],obs['vn'][:1])
        mean=np.zeros(8,'f4');sd=np.ones(8,'f4')
        with patch('data3001.modelling.continuous_diagnostics.HOURS',(1,3,6)):
            rows,events,saved=trace(model,mean,sd,q,obs,mapper,particles=16,seed=91)
        expected=rollout(model,mean,sd,x,mapper,16,91,(1,3,6))
        for h in (1,3,6):np.testing.assert_array_equal(saved[h],expected[h])
        np.testing.assert_allclose(rows[[f'reason_{j}_fraction' for j in range(5)]].sum(1),1)
        self.assertFalse(events.duplicated(['query','particle']).any())


if __name__=='__main__': unittest.main()
