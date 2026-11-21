import unittest
import numpy as np
import pandas as pd
import shapely as sh
from path_rules import G,OFFSETS,path_features,decide

def frame(x,y,valid=None):
    radius=np.hypot(x,y)*1000;az=np.rad2deg(np.arctan2(x,y))
    lon,lat,_=G.fwd(np.full(145,-75.),np.full(145,35.),az,radius)
    if valid is None:valid=np.ones((1,145),bool)
    f,_=path_features(lon[None,:],lat[None,:],valid,sh.Polygon())
    for col,val in {'metadata_conflict':False,'before_complete':True,'after_complete':True,'endpoint_on_land':False,'motion_land_points':0}.items():f[col]=val
    return f

class Rules(unittest.TestCase):
    def test_small_net_real_loop(self):
        theta=2*np.pi*OFFSETS/24
        f=frame(10*np.cos(theta),10*np.sin(theta))
        self.assertLess(f.before24_net_km.iloc[0],1e-6)
        self.assertEqual(decide(f)[0],'looping_evidence')
    def test_slow_multiday_progress(self):
        f=frame(OFFSETS*.18,np.zeros(145))
        self.assertLess(f.before24_net_km.iloc[0],5)
        self.assertEqual(decide(f)[0],'consistent_drift_evidence')
    def test_stationary_after_arrival(self):
        f=frame(np.minimum(OFFSETS,0)*.5,np.zeros(145))
        self.assertEqual(decide(f)[0],'suspected_local_stay')
    def test_noise_does_not_become_path_motion(self):
        f=frame(2*np.cos(np.pi*OFFSETS/3),np.zeros(145))
        self.assertNotIn(decide(f)[0],['looping_evidence','consistent_drift_evidence'])
    def test_missing_coarse_point_blocks_motion(self):
        theta=2*np.pi*OFFSETS/24;valid=np.ones((1,145),bool);valid[0,75]=False
        f=frame(10*np.cos(theta),10*np.sin(theta),valid)
        self.assertEqual(decide(f)[0],'other_unresolved')
    def test_source_conflict_and_missing_local_window(self):
        f=frame(OFFSETS*.18,np.zeros(145));f['metadata_conflict']=True
        self.assertEqual(decide(f)[0],'insufficient_or_conflicting')
        f['metadata_conflict']=False;f['after_complete']=False
        self.assertEqual(decide(f)[0],'insufficient_or_conflicting')

if __name__=='__main__':unittest.main()
