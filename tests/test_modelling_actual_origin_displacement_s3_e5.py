"""Semantic checks for the approved E5 geometry and bounded solver protocol."""
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from shapely.geometry import box, GeometryCollection
from data3001.preprocessing.prep_core import cells
from data3001.modelling.baselines.spatial_borrowing_s3_e1_inputs import Geometry, FALLBACK
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_inputs import (
    Query, TrackArrays, ActualOriginKernel, reference_distribution,
)
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_selection import (
    weight_gradient, analytic_weight, quadratic_terms, ForecastCase, CaseEvaluator,
    search, select_pool, continuous_minima,
)
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_audit import literal_transfer, audit_search


def cell(x,y=.4):return int(cells(np.array([x]),np.array([y]))[0])


def fixture(values,land=None,mid=None,domain=None,times=None,full=True,query_x=.2):
    x=np.asarray(values,float);y=np.full(len(x),.4)
    t=np.arange(len(x))*3600 if times is None else np.array(times)
    tracks=TrackArrays(x,y,t,np.ones(len(x),bool))
    empty=GeometryCollection();land=empty if land is None else land;mid=land if mid is None else mid
    region=box(-3,-2,6,3);domain=region if domain is None else domain
    states={cell(a+.3,b+.3) for a in range(-3,6) for b in range(-2,3)}
    geo=Geometry(region,domain,land,mid,states)
    donor=pd.DataFrame([dict(id=1,origin_source_obs=10,horizon_days=7,origin_cell_1=cell(x[0]),
        lon=x[0],lat=.4,epoch=0.,start=0,track_end=len(x),full_interval=full and len(x)==169,
        x_min=x.min(),x_max=x.max(),y_min=.4,y_max=.4,end_lon=x[-1],end_lat=.4)])
    query=Query(99,1,7,cell(query_x),query_x,.4,100000.,1)
    return ActualOriginKernel(geo,tracks),query,donor


class TransferTests(unittest.TestCase):
    def compare(self,k,q,d,expected=None):
        out,reason,profile=k.classify(q,d,[1])
        out2,reason2,_=k.classify(q,d,[1],certificates=False)
        oracle=literal_transfer(q,d.iloc[0],k.tracks,k.geometry)
        self.assertEqual((int(out[0]),int(reason[0])),oracle)
        np.testing.assert_array_equal(out,out2);np.testing.assert_array_equal(reason,reason2)
        if expected is not None:self.assertEqual(oracle,expected)
        return profile

    def test_actual_start_and_two_positions_in_same_cell(self):
        k,q,d=fixture(np.linspace(1.2,1.7,169))
        self.assertEqual(self.compare(k,q,d,(cell(.7),0))['certified'],1)
        q2=Query(99,2,7,q.origin,.8,.4,0,1)
        self.compare(k,q2,d,(cell(1.3),0))

    def test_land_segment_with_water_endpoints(self):
        k,q,d=fixture([1.2,3.2],land=box(.9,0,1.1,1),full=False)
        self.compare(k,q,d,(FALLBACK,6))

    def test_mask_disagreement(self):
        k,q,d=fixture([1.2,3.2],land=box(.9,0,1.1,1),mid=GeometryCollection(),full=False)
        self.compare(k,q,d,(FALLBACK,10))

    def test_first_exit_is_absorbing_despite_return_and_later_land(self):
        k,q,d=fixture([1.2,-4,2],land=box(.9,0,1.1,1),full=False)
        self.compare(k,q,d,(-2,0))

    def test_land_before_exit_is_failure(self):
        k,q,d=fixture([1.2,8],land=box(.9,0,1.1,1),full=False)
        self.compare(k,q,d,(FALLBACK,6))

    def test_observed_domain_excursion_only(self):
        domain=box(-3,-2,1.5,3).union(box(2,-2,6,3))
        k,q,d=fixture(np.r_[1.2,np.repeat(3.4,168)],domain=domain)
        self.compare(k,q,d,(cell(2.4),0))

    def test_gap_and_missing_continuation(self):
        k,q,d=fixture([1.2,1.3],times=[0,7200],full=False)
        self.compare(k,q,d,(FALLBACK,5))
        k,q,d=fixture([1.2,1.3],full=False)
        self.compare(k,q,d,(FALLBACK,7))

    def test_unsafe_query_retained_as_fallback(self):
        k,q,d=fixture(np.repeat(1.2,169),land=box(.1,0,.3,1))
        self.compare(k,q,d,(FALLBACK,11))

    def test_query_integrity_and_whole_id_guard(self):
        k,q,d=fixture(np.repeat(1.2,169))
        with self.assertRaises(PermissionError):k.classify(q,d,[1,99])
        with self.assertRaises(PermissionError):k.classify(q,d,[2])
        with self.assertRaises(ValueError):k.classify(Query(99,1,7,q.origin,2.2,.4,0,1),d,[1])
        d.loc[0,'lon']=30
        with self.assertRaises(ValueError):k.classify(q,d,[1])

    def test_unindexed_destination_cannot_be_certified(self):
        k,q,d=fixture(np.linspace(1.2,2.5,169))
        k.geometry.states.remove(cell(1.5));k=ActualOriginKernel(k.geometry,k.tracks)
        self.compare(k,q,d,(FALLBACK,4))

    def test_donor_mass_and_no_donor_fallback(self):
        p=np.array([.4,.6,0.]);states=np.array([1,2,-2])
        q,r=reference_distribution(np.array([1,FALLBACK,-2,FALLBACK]),p,states)
        np.testing.assert_allclose(q,[.45,.3,.25]);self.assertEqual(r,.5)
        np.testing.assert_array_equal(reference_distribution(np.array([],int),p,states)[0],p)


class SyntheticEvaluator:
    def __init__(self,narrow=False):
        self.fixed=np.array([1.,-.74,.37**2+.2]);self.narrow=narrow
    def objective(self,theta):
        a,g=theta;return (a-.37)**2+.2,np.array([2*(a-.37),0.])
    def metrics(self,a,g):
        feasible=(.1234567<a<.1234568) if self.narrow else (.41<=a<=.42)
        return dict(brier=self.objective((a,g))[0],region90_hit=.95 if feasible else .8,region90_cells=9.,region90_mass=.9)


class SolverTests(unittest.TestCase):
    def test_analytic_and_degenerate_cases(self):
        self.assertAlmostEqual(analytic_weight([2,-1,1]),.25)
        self.assertEqual(analytic_weight([1,2,1]),0)
        self.assertEqual(analytic_weight([1,-3,1]),1)
        self.assertEqual(analytic_weight([0,0,1]),0)
        self.assertAlmostEqual(analytic_weight([1e-20,-1e-20,1]),.5)
        with self.assertRaises(ValueError):analytic_weight([0,1e-6,1])
        with self.assertRaises(ValueError):analytic_weight([-1,0,1])

    def test_gradient_matches_differences_and_boundary_limits(self):
        z=np.array([0,.01,1,20.]);a,g=.43,.8
        lam,da,dg=weight_gradient(a,g,z);e=1e-6
        np.testing.assert_allclose(da,(weight_gradient(a+e,g,z)[0]-weight_gradient(a-e,g,z)[0])/(2*e),atol=1e-9)
        np.testing.assert_allclose(dg,(weight_gradient(a,g+e,z)[0]-weight_gradient(a,g-e,z)[0])/(2*e),atol=1e-9)
        np.testing.assert_allclose(weight_gradient(.4,0,z)[0],[0,.4,.4,.4])
        self.assertEqual(weight_gradient(1,2,z)[0][0],0)
        for endpoint in (0,1):self.assertTrue(np.isfinite(weight_gradient(endpoint,2,z)).all())

    def test_coefficients_equal_direct_brier_with_zero_truth(self):
        p=np.array([.7,.3,0]);q=np.array([.1,.8,.1])
        for y in range(3):
            A,B,C=quadratic_terms(p,q,y)
            for a in (0,.317,1):
                v=(1-a)*p+a*q
                self.assertAlmostEqual(A*a*a+B*a+C,1+v@v-2*v[y])

    def test_case_weights_and_region_ties_exit(self):
        states=np.array([1,2,-2]);p=np.array([.45,.45,.1]);q=np.array([.2,.7,.1])
        cases=[ForecastCase(states,p,q,1,2.,.25,('role',1)),ForecastCase(states,p,q,2,2.,.75,('role',1))]
        ev=CaseEvaluator(cases);m=ev.metrics(0,0)
        self.assertEqual(m['region90_cells'],2);self.assertEqual(m['region90_hit'],1)
        self.assertAlmostEqual(m['brier'],ev.objective((0,0))[0])

    def test_finite_search_finds_off_grid_feasible_point(self):
        ev=SyntheticEvaluator();refs={name:dict(brier=.9,region90_hit=.9,region90_cells=10.) for name in ['Fixed','LocalEndpointAdaptive']}
        result=search(ev,refs);audit_search(result,ev)
        self.assertFalse(result['selections']['F_grid']['eligible_for_replacement'])
        self.assertTrue(result['selections']['F_analytic']['eligible_for_replacement'])
        self.assertLessEqual(len(result['candidates']),252)
        self.assertLessEqual(len(result['memberships']['F_analytic']),114)
        self.assertLessEqual(len(result['optimizer_runs']),11)
        self.assertLessEqual(len(result['optimizer_trace']),22000)

    def test_narrow_missed_region_is_only_pool_failure(self):
        ev=SyntheticEvaluator(True);refs={name:dict(brier=.9,region90_hit=.9,region90_cells=10.) for name in ['Fixed','LocalEndpointAdaptive']}
        result=search(ev,refs)
        self.assertEqual(result['selections']['F_analytic']['status'],'no_feasible_candidate_in_searched_pool')

    def test_strict_gate_applies_before_tie(self):
        rows=[dict(a=.1,gamma=0,brier=.5-1.1e-12,feasible=True),
              dict(a=0,gamma=0,brier=.5-.6e-12,feasible=True)]
        result=select_pool(rows,dict(B=.5,H=.9,K=10))
        self.assertTrue(result['eligible_for_replacement']);self.assertEqual(result['selected']['a'],.1)

    def test_hard_optimizer_cap_and_nonconvergence_preserve_seed(self):
        def excessive(fun,*args,**kwargs):
            for _ in range(2001):fun(np.array([.37,0.]))
        with patch('data3001.modelling.baselines.actual_origin_displacement_s3_e5_selection.minimize',excessive):
            points,runs,trace=continuous_minima(SyntheticEvaluator(),dict(a=.35,gamma=0.),.37)
        self.assertTrue(all(not r['success'] and r['calls']==2000 for r in runs))
        self.assertTrue(all(p==(.37,0.) for p in points))


if __name__=='__main__':unittest.main()
