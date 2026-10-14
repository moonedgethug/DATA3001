import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prep_core as c

class Preparation(unittest.TestCase):
    def track(self, times, inside=None, usable=None, regime=None):
        t=np.asarray(times,dtype=float)*3600
        n=len(t)
        return dict(time=t,position_ok=np.ones(n,bool) if usable is None else np.array(usable),
                    inside_D=np.ones(n,bool) if inside is None else np.array(inside),
                    mapping_ok=np.ones(n,bool),regime=np.ones(n,dtype=np.int8) if regime is None else np.array(regime),
                    lon=np.zeros(n),lat=np.zeros(n),loss=1e10)

    def test_native_before_wrap(self):
        x,ok=c.coordinates(np.array([9999,180,-180,0,np.nan]),np.zeros(5))
        self.assertEqual(ok.tolist(),[False,True,True,True,False])
        self.assertTrue(np.isnan(x[0]));self.assertEqual(x[1],-180)

    def test_separate_temperature_velocity_uncertainty(self):
        self.assertTrue(c.velocity_ok(np.array([0.,-2]),np.array([0.,1])).all())
        self.assertEqual(c.sst_ok(np.array([300.,500.,np.nan]),np.array([4,5,5])).tolist(),[True,False,False])
        self.assertTrue(c.sst_ok(np.array([-.3]),np.array([5]),anomaly=True)[0])
        self.assertFalse(c.uncertainty_ok(np.array([np.nan,-.2])) .any())

    def test_exact_and_conflicting_duplicates(self):
        d={'time':np.array([1.,1.,2.,2.]),'lon':np.array([0.,0.,0.,1.]),'sst':np.array([np.nan,np.nan,300,300])}
        status,groups=c.duplicates(d)
        self.assertEqual(status.tolist(),[0,1,2,2]);self.assertEqual(groups[0],[0,1])

    def test_early_exit_absorbs_later_death_cutoff_and_loss(self):
        a=self.track(range(121),[True]*120+[False]);a['loss']=121*3600
        p=c.event_bounds(a)
        e,s=c.labels(a,np.array([0]),30,0,'drogued',p,cutoff=200*3600)
        self.assertEqual(s['reason'][0],0);self.assertTrue(s['outside'][0])
        self.assertNotEqual(e['reason'][0],0)

    def test_gap_before_exit(self):
        a=self.track([0,2],[True,False]);p=c.event_bounds(a)
        e,s=c.labels(a,np.array([0]),1,0,'drogued',p,cutoff=100*3600)
        self.assertFalse(s['outside'][0]);self.assertEqual(s['reason'][0],6)
        self.assertEqual(s['required_interval_end'][0],86400)

    def test_unknown_and_switching_predicates_both_retained(self):
        a=self.track([0,12,24],regime=[1,-1,0]);a['loss']=12*3600
        e,p=c.labels(a,np.array([0]),1,0,'drogued',c.event_bounds(a),cutoff=100*3600)
        self.assertTrue(e['secondary'][0]&8);self.assertTrue(e['secondary'][0]&16)

    def test_tolerance_cannot_confirm_nominal_loss_precision_guard(self):
        a=self.track([0,23,25],regime=[1,1,0]);a['loss']=24*3600
        e,_=c.labels(a,np.array([0]),1,1,'drogued',c.event_bounds(a),cutoff=100*3600)
        self.assertNotEqual(e['reason'][0],0);self.assertTrue(e['secondary'][0]&8)

    def test_endpoint_gap_requires_independent_regime(self):
        a=self.track([0,24]);p=c.event_bounds(a)
        e,s=c.labels(a,np.array([0]),1,0,'drogued',p,cutoff=100*3600)
        self.assertEqual(e['reason'][0],0);self.assertEqual(s['reason'][0],6)
        a['loss']=np.nan;a['regime'][:]=-1
        e,s=c.labels(a,np.array([0]),1,0,'drogued',c.event_bounds(a),cutoff=100*3600)
        self.assertNotEqual(e['reason'][0],0)

    def test_tie_and_late_tolerance_regime(self):
        a=self.track([0,23,25]);p=c.event_bounds(a)
        e,_=c.labels(a,np.array([0]),1,1,'drogued',p,cutoff=100*3600)
        self.assertEqual(e['endpoint_index'][0],1);self.assertEqual(e['time_error_seconds'][0],-3600)
        a=self.track([0,25]);a['loss']=24.5*3600;a['regime'][-1]=0
        e,_=c.labels(a,np.array([0]),1,1,'drogued',c.event_bounds(a),cutoff=100*3600)
        self.assertNotEqual(e['reason'][0],0)

    def test_unknown_pooled_retained(self):
        a=self.track([0,24],regime=[-1,-1]);a['loss']=0
        e,_=c.labels(a,np.array([0]),1,0,'pooled',c.event_bounds(a),cutoff=100*3600)
        self.assertEqual(e['reason'][0],0)

    def test_grid_and_visits_break_gap(self):
        self.assertEqual(c.cells(np.array([-180.,-179]),np.array([0.,1.]),1).tolist(),[32400,32761])
        self.assertEqual(c.visits(np.array([0,3600,10800,14400]),np.array([4,4,4,5])).tolist(),[0,0,1,2])

    def test_inclusive_domain_boundary_has_half_open_grid_state(self):
        from prep_geometry import domain_cell_ranges
        for res in [1,.5]:
            xr,yr=domain_cell_ranges([-81,20,-8,55],res)
            cell=int(c.cells(np.array([-8.]),np.array([55.]),res)[0]);nx=int(360/res)
            self.assertIn(cell%nx,xr);self.assertIn(cell//nx,yr)

    def test_similar_ID_cannot_become_checkpoint_owner(self):
        import tempfile
        from prep_support import own_ledger_paths
        from prep_io import OUT
        with tempfile.TemporaryDirectory(dir=OUT/'audit') as p:
            root=Path(p);e=root/'ledgers/endpoint';e.mkdir(parents=True)
            (e/'7647_7_drogued.parquet').touch();(e/'107647_7_drogued.parquet').touch()
            self.assertEqual([x.name for x in own_ledger_paths(root,7647)],['7647_7_drogued.parquet'])

    def test_elapsed_geodesic(self):
        km,u,v=c.displacement(np.array([0.,54000.]),np.array([-75.,-74.8]),np.array([30.,30.]))
        self.assertAlmostEqual(np.hypot(u[1],v[1]),km[1]*1000/54000)

    def test_invalid_endpoint_with_geometry_not_outside(self):
        a=self.track([0,24],[True,False]);a['mapping_ok'][1]=False
        e,s=c.labels(a,np.array([0]),1,0,'pooled',c.event_bounds(a),cutoff=100*3600)
        self.assertNotEqual(e['reason'][0],0);self.assertFalse(e['outside'][0]);self.assertFalse(s['outside'][0])

    def test_invalid_source_position_is_not_geometry_failure(self):
        a=self.track(range(25));a['position_ok'][12]=False;a['mapping_ok'][12]=False
        e,s=c.labels(a,np.array([0]),1,0,'drogued',cutoff=100*3600)
        self.assertEqual(e['reason'][0],0)
        self.assertEqual(s['reason'][0],6)
        self.assertFalse(s['secondary'][0]&256)
        self.assertTrue(s['path_source_position_failure'][0])
        self.assertFalse(s['path_geometry_failure'][0])

    def test_source_and_geometry_path_predicates_are_independent(self):
        a=self.track(range(25));a['position_ok'][5]=False;a['mapping_ok'][5]=False
        a['mapping_ok'][12]=False
        s=c.labels(a,np.array([0]),1,0,'pooled',cutoff=100*3600)[1]
        self.assertEqual(s['reason'][0],9)
        self.assertTrue(s['path_source_position_failure'][0])
        self.assertTrue(s['path_geometry_failure'][0])
        ev=c.event_bounds(a)
        self.assertEqual(ev['bad_source_position_time'][0],5*3600)
        self.assertEqual(ev['bad_geometry_time'][0],12*3600)

    def test_geometry_only_path_failure(self):
        a=self.track(range(25));a['mapping_ok'][12]=False
        s=c.labels(a,np.array([0]),1,0,'drogued',cutoff=100*3600)[1]
        self.assertEqual(s['reason'][0],9)
        self.assertFalse(s['path_source_position_failure'][0])
        self.assertTrue(s['path_geometry_failure'][0])

    def test_source_failure_after_qualified_exit_does_not_cancel_it(self):
        a=self.track(range(25),[True]*5+[False]*20)
        a['position_ok'][12]=False;a['mapping_ok'][12]=False
        s=c.labels(a,np.array([0]),30,0,'drogued',cutoff=100*3600)[1]
        self.assertEqual(s['reason'][0],0);self.assertTrue(s['outside'][0])
        self.assertEqual(s['required_interval_end'][0],5*3600)
        self.assertFalse(s['path_source_position_failure'][0])
        self.assertFalse(s['path_geometry_failure'][0])

    def test_invalid_origin_does_not_add_geometry_secondary_flag(self):
        a=self.track(range(25));a['position_ok'][0]=False;a['mapping_ok'][0]=False
        e,s=c.labels(a,np.array([0]),1,0,'pooled',cutoff=100*3600)
        self.assertEqual(e['reason'][0],1);self.assertEqual(s['reason'][0],1)
        self.assertFalse(e['secondary'][0]&256);self.assertFalse(s['secondary'][0]&256)

    def test_missing_crosscheck_does_not_suppress_review(self):
        from prep_peers import screen_score
        r=screen_score(np.array([4.,np.nan]),np.array([np.nan,6.]),2.,3.)
        self.assertEqual(r.tolist(),[2.,2.])

    def test_random_tracks_against_chronological_scalar_reference(self):
        rng=np.random.default_rng(20261004)
        for trial in range(40):
            t=1e9+np.arange(73)*3600
            keep=rng.random(len(t))>.08;keep[0]=True;t=t[keep]
            n=len(t);loss=1e9+float(rng.integers(8,65))*3600+1800
            reg=np.where(t<loss,1,0).astype(np.int8);reg[rng.random(n)<.03]=-1
            pos=rng.random(n)>.04;pos[0]=True;wet=rng.random(n)>.02;wet[0]=True
            inside=rng.random(n)>.15;inside[0]=True
            a=dict(time=t,position_ok=pos,mapping_ok=wet,regime=reg,inside_D=inside,loss=loss,lon=np.zeros(n),lat=np.zeros(n))
            events=c.event_bounds(a)
            for scenario in ['drogued','undrogued','pooled']:
                want=1 if scenario=='drogued' else 0
                def regime_ok(start,end):
                    if scenario=='pooled':return True
                    if not (end<loss if want else start>=loss):return False
                    q=(t>=start)&(t<=end)
                    return bool((reg[q]==want).all())
                for o in np.flatnonzero(pos&inside)[:8]:
                    for tol in [0,1,3]:
                        target=t[o]+86400
                        eligible_indices=[j for j in range(n) if pos[j] and abs(t[j]-target)<=tol*3600]
                        if eligible_indices:
                            j=min(eligible_indices,key=lambda k:(abs(t[k]-target),t[k]))
                            eok=bool(wet[o] and wet[j] and regime_ok(t[o],max(target,t[j])) and target<=t[-1])
                            eoutside=eok and not inside[j]
                        else:eok=eoutside=False
                        pok=False;poutside=False;prev=None
                        if regime_ok(t[o],t[o]) and wet[o]:
                            for j in range(o,n):
                                if prev is not None and t[j]!=prev+3600:break
                                if not pos[j] or not wet[j] or not regime_ok(t[o],t[j]):break
                                if not inside[j]:pok=poutside=True;break
                                if t[j]>=target:pok=t[j]==target;break
                                prev=t[j]
                        e,p=c.labels(a,np.array([o]),1,tol,scenario,events,cutoff=t[-1])
                        self.assertEqual((e['reason'][0]==0,bool(e['outside'][0])),(eok,eoutside))
                        self.assertEqual((p['reason'][0]==0,bool(p['outside'][0])),(pok,poutside))

if __name__=='__main__':unittest.main()
