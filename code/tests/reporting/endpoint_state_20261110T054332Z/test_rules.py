import unittest
import numpy as np
import pandas as pd
from common import quality,classify

class Rules(unittest.TestCase):
    def test_coverage_and_endpoints(self):
        v=np.ones((3,25),bool);v[1,0]=False;v[2,1:7]=False
        ok,count,gap=quality(v,np.arange(25))
        self.assertEqual(ok.tolist(),[True,False,False]);self.assertEqual(gap[2],7)
    def test_169_hour_coverage(self):
        v=np.ones((2,169),bool);v[1,-1]=False
        self.assertEqual(quality(v,np.arange(169))[0].tolist(),[True,False])
    def test_evidence_not_official_flag_only(self):
        f=pd.DataFrame({'endpoint_available':[True]*5+[False], 'endpoint_on_land':[False]*6,
            'metadata_conflict':[False,True,False,False,False,False], 'before_complete':[True]*6,'after_complete':[True,True,False,True,True,True],
            'before_24h_km':[5]*6,'after_24h_km':[5]*6,'before_6h_km':[1]*6,'after_6h_km':[1]*6,
            'motion_land_points':[0,0,0,1,0,0],'ground_candidate':[False,False,False,False,True,True],
            'ground_review_passed':[False]*6})
        self.assertEqual(classify(f).tolist(),['drifting_evidence','uncertain','uncertain','uncertain','drifting_evidence','endpoint_missing'])
        f.loc[4,'ground_review_passed']=True
        self.assertEqual(classify(f)[4],'grounding_evidence')
        self.assertEqual(classify(f,10)[0],'uncertain')
    def test_exact_six_hour_gap(self):
        v=np.ones((1,25),bool);v[0,1:6]=False
        self.assertTrue(quality(v,np.arange(25))[0][0])
        self.assertEqual(quality(v,np.arange(25))[2][0],6)

if __name__=='__main__':unittest.main()
