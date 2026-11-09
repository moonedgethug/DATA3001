"""Report aggregation checks; no fitting or experimental-data access."""
import importlib
import importlib.util
import unittest

import numpy as np
import pandas as pd


class DeliveryTests(unittest.TestCase):
    def module(self):
        name='data3001.modelling.continuous_models.local_gmm_s5_e2_delivery'
        self.assertIsNotNone(importlib.util.find_spec(name))
        return importlib.import_module(name)

    def test_descriptive_groups_keep_equal_drifter_votes(self):
        table=pd.DataFrame([dict(year=2020,id=1,model='A',energy_km=10.,h90=1.,area90_km2=20.)]*9+
                           [dict(year=2020,id=2,model='A',energy_km=0.,h90=0.,area90_km2=10.)])
        result=self.module().descriptive_summary(table,['year']).iloc[0]
        self.assertEqual(result.energy_km,5.)
        self.assertEqual(result.h90,.5)
        self.assertEqual(result.area90_km2,15.)
        self.assertEqual(result.independent_ids,2)

    def test_leave_one_id_out_uses_paired_id_means(self):
        rows=[]
        for identity in [1,2,3]:
            for model in ['LocalGMM','LocalGaussian','ExactPoint','EndpointCI']:
                rows.append(dict(id=identity,model=model,energy_km=float(identity)+(model!='LocalGMM'),
                                 h90=.9,area90_km2=10. if model=='LocalGMM' else 20.))
        result=self.module().leave_one_id_out(pd.DataFrame(rows))
        self.assertEqual(len(result),9)
        np.testing.assert_allclose(result.es_delta,-1.)
        np.testing.assert_allclose(result.hit_delta,0.)
        np.testing.assert_allclose(result.area_ratio,.5)


if __name__=='__main__':unittest.main()
