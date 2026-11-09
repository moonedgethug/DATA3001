"""Lossless lineage and inferential fixtures for the isolated E9 formal runner."""
import unittest
import numpy as np
import pandas as pd
from data3001.modelling.baselines.seasonal_exact_position_s4_e9_formal_io import encode_selection, decode_selection
from data3001.modelling.baselines.seasonal_exact_position_s4_e9_formal_analysis import infer, precision
from data3001.modelling.baselines.seasonal_exact_position_s4_e9_formal_io import MODELS


class LineageTests(unittest.TestCase):
    def test_bitwise_roundtrip_duplicate_distances_and_source_order(self):
        g=np.random.default_rng(42)
        for n in [1,2,7,8000,8003]:
            ix=g.choice(265393,n,replace=False);d=g.uniform(0,100000,n)
            d[:min(5,n)]=0.;o=np.lexsort((ix,d));a=(ix[o],d[o])
            s=(np.array([3,9,200001]),np.array([0.,100000.,100000.+1e-7]))
            for fallback in [False,True]:
                x,y,f=decode_selection(encode_selection(a,s,fallback))
                self.assertEqual(f,fallback)
                for expected,actual in [(a,x),(a if fallback else s,y)]:
                    np.testing.assert_array_equal(expected[0],actual[0])
                    self.assertEqual(expected[1].astype('<f8').tobytes(),actual[1].tobytes())

    def test_source_duplicates_are_rejected(self):
        a=(np.array([1,1]),np.array([0.,1.]))
        with self.assertRaises(ValueError): encode_selection(a,a,False)

    def test_equal_id_inference_and_exact_fallback_covariance(self):
        records=[];position=0
        for identity,n in enumerate([1,2,4]):
            for t in range(n):
                for name in MODELS:
                    records.append(dict(id=identity,query_position=position,model=name,weight=1/(3*n),
                        energy_km=float(identity+1),h90=1.,area90_km2=10.+identity,seasonal_fallback=True,
                        energy_mc_se=1.,ci_delta_mc_se=0.))
                position+=1
        frame=pd.DataFrame(records);ids,cube,boot,contrasts=infer(frame)
        np.testing.assert_allclose(cube.mean(axis=0)[:,0],2.)
        np.testing.assert_array_equal(contrasts.es_difference_km,0.)
        np.testing.assert_array_equal(contrasts.es_high,0.)
        np.testing.assert_array_equal(contrasts.area_ratio,1.)
        np.testing.assert_array_equal(precision(frame).three_se_km,0.)


if __name__=='__main__':unittest.main()
