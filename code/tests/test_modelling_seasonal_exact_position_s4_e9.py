"""Independent semantic fixtures for the approved E9 contract."""
import unittest
import numpy as np
import pandas as pd
from data3001.modelling.baselines import seasonal_exact_position_s4_e9 as e
from data3001.modelling.baselines import position_error_s4_e8 as old


class SeasonalTests(unittest.TestCase):
    def test_calendar_duration_tie_and_leap(self):
        dates=['2021-02-26','2021-02-25','2021-02-25 12:00','2020-02-27',
               '2021-03-01','2021-06-01','2021-09-01','2021-12-01','2021-12-29']
        z=e.season_labels(pd.to_datetime(dates,format='mixed',utc=True))
        np.testing.assert_array_equal(z.majority_season,[1,0,0,1,1,2,3,0,0])
        self.assertTrue(z.season_tie.iloc[2]);self.assertFalse(z.cross_season.iloc[-1])
        np.testing.assert_array_equal(z[[s+'_seconds' for s in e.SEASONS]].sum(axis=1),604800.)

    def test_open_right_boundary_and_invalid_time(self):
        z=e.season_labels(pd.to_datetime(['2021-02-22','2021-05-29','2021-08-29','2021-11-28'],utc=True))
        self.assertFalse(z.cross_season.iloc[0]);np.testing.assert_array_equal(z.majority_season,[0,2,3,0])
        with self.assertRaises(ValueError):e.season_labels(pd.to_datetime(['2021-02-01']))

    def fit(self):
        return pd.DataFrame(dict(lon=[-75.,-74.99,-74.98,-74.97],lat=[35.]*4,
            origin_time_UTC=pd.to_datetime(['2021-01-01','2021-01-02','2021-07-01','2021-07-02'],utc=True)))

    def test_filter_before_neighbours(self):
        f=self.fit();index=e.SeasonalNeighbours(f,k=1)
        a,s,fallback=index.query(-75.,35.,2)
        np.testing.assert_array_equal(a[0],[0]);np.testing.assert_array_equal(s[0],[2])
        self.assertFalse(fallback)
        # Annual-k-then-filter would incorrectly yield empty support.
        self.assertFalse(np.any(index.labels.majority_season.iloc[a[0]].eq(2)))

    def test_empty_fallback_and_no_low_support_blend(self):
        index=e.SeasonalNeighbours(self.fit(),k=8000)
        a,s,fallback=index.query(-75.,35.,1)
        self.assertTrue(fallback);np.testing.assert_array_equal(a[0],s[0])
        a,s,fallback=index.query(-75.,35.,2)
        self.assertFalse(fallback);self.assertEqual(len(s[0]),2)

    def test_ties_duplicates_radius_and_exhaustive(self):
        f=self.fit();f.loc[1,['lon','lat']]=f.loc[0,['lon','lat']]
        index=e.SeasonalNeighbours(f,k=1)
        a,_,_=index.query(-75.,35.,0)
        np.testing.assert_array_equal(a[0],[0,1])
        exact,_,_=index.query(-75.,35.,0,exhaustive=True)
        np.testing.assert_array_equal(a[0],exact[0])
        with self.assertRaises(ValueError):index.query(0.,0.,0)

    def test_weights_do_not_equalize_seasons_or_cells(self):
        frame=pd.DataFrame(dict(id=[1,1,1,2],season=[0,0,1,1]))
        np.testing.assert_allclose(e.case_weights(frame),[1/6,1/6,1/6,1/2])

    def test_e8_numerical_parity_and_no_extra_arms(self):
        p=np.array([[-75.,35.],[-74.,36.],[-73.,35.],[-74.,34.]])
        ok=np.array([True,False,True,True]);sd=old.equivalent_sd(p,np.full((4,2),.002),ok)
        key=('fixture',3,8)
        original,_=old.predict(p,sd,ok,key=key,energy_count=1024,region_count=256)
        got,cloud=e.predict_pool(p,sd,ok,key=key,energy_count=1024,region_count=256)
        scores=e.score_pool(p,sd,ok,got,[-74.,35.],key)
        expected=old.evaluate(p,sd,ok,original,[-74.,35.],key=key)
        self.assertEqual(set(got),{False,True})
        for ci,name in [(False,'ExactPoint'),(True,'EndpointCI')]:
            self.assertEqual(got[ci]['region'],original[name]['region'])
            self.assertAlmostEqual(got[ci]['correction'],original[name]['correction'],places=12)
            for metric in ['energy_km','h90','area90_km2']:
                self.assertAlmostEqual(scores[ci][metric],expected[name][metric],places=11)
        # CI absolute uncertainty includes point self-distance uncertainty.
        self.assertGreater(scores[True]['energy_mc_se'],scores[True]['ci_delta_mc_se'])

    def test_missing_ci_is_exact_identity_and_single_atom(self):
        p=np.array([[-75.,35.]])
        f,_=e.predict_pool(p,np.zeros((1,2)),np.zeros(1,bool),key=('atom',),energy_count=64)
        self.assertIs(f[False],f[True]);self.assertEqual(f[False]['region']['area_km2'],0)
        score=e.score_pool(p,np.zeros((1,2)),np.zeros(1,bool),f,[-74.,35.],('atom',))
        self.assertEqual(score[False],score[True])
        xyz,_=old.coordinates(np.array([[-75.,35.],[-74.,35.]]))
        self.assertAlmostEqual(score[False]['energy_km'],np.linalg.norm(xyz[0]-xyz[1]))

    def test_point_es_finite_sum_and_outcome_independence(self):
        p=np.array([[-75.,35.],[-74.,36.],[-73.,35.]])
        f,_=e.predict_pool(p,np.zeros_like(p),np.zeros(3,bool),key=('finite',),energy_count=65536)
        before=repr(f);truth=np.array([-74.,35.])
        scores=e.score_pool(p,np.zeros_like(p),np.zeros(3,bool),f,truth,('finite',))
        xyz,_=old.coordinates(p);y,_=old.coordinates(truth[None,:])
        exact=np.linalg.norm(xyz-y,axis=1).mean()-.5*np.linalg.norm(xyz[:,None]-xyz[None,:],axis=2).mean()
        self.assertLess(abs(scores[False]['energy_km']-exact),4*scores[False]['energy_mc_se'])
        self.assertEqual(before,repr(f))

if __name__=='__main__':unittest.main()
