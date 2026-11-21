import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
import numpy as np
from shapely.geometry import box,MultiPolygon
from coast import CoastIndex,GEOD

class CoastTests(unittest.TestCase):
    def test_geodesic_bounds_and_real_boundary(self):
        points=np.array([[-74.999,35],[-74.9,35],[-74.4,35],[-75.1,35]])
        land=MultiPolygon([box(-76,34,-75,36)])
        index=CoastIndex(land,points)
        z,refined=index.distances(points)
        self.assertEqual(z['group'].tolist(),['<=10km','<=10km','>50km','land_or_boundary'])
        for i in range(3):
            approx=GEOD.inv(points[i,0],points[i,1],-75,35)[2]
            self.assertLessEqual(z['distance_lower_m'][i],approx+2)
            self.assertGreaterEqual(z['distance_upper_m'][i],approx-2)
    def test_threshold_refinement(self):
        lon,lat,_=GEOD.fwd(-75,35,90,10001)
        index=CoastIndex(MultiPolygon([box(-76,34,-75,36)]),np.array([[lon,lat]]))
        z,refined=index.distances(np.array([[lon,lat]]))
        self.assertTrue(refined)
        self.assertEqual(z['group'][0],'10_50km')

if __name__=='__main__':unittest.main()
