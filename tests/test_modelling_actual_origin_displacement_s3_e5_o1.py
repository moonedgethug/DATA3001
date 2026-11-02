"""Exact O1 rewrite compared with the immutable reference and scalar oracle."""
import unittest
import numpy as np
import shapely as sh
from shapely.geometry import box,GeometryCollection
from test_modelling_actual_origin_displacement_s3_e5 import fixture,cell
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_inputs import Query
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1 import G1Kernel,ExclusiveTimer
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_profile import ProfiledReference
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_audit import literal_transfer


class O1Tests(unittest.TestCase):
    def compare(self,values,**kwargs):
        k,q,d=fixture(values,**kwargs);d['fold']=2
        want=k.classify(q,d,[1])
        pk=ProfiledReference(k.geometry,k.tracks);pk.timer=ExclusiveTimer()
        instrumented=pk.classify(q,d,[1])
        for a,b in zip(want[:2],instrumented[:2]):np.testing.assert_array_equal(a,b)
        for batch in (2048,8192):
            g=G1Kernel(k.geometry,k.tracks,batch_size=batch);c=g.context(d,q,[1],'synthetic')
            got=g.classify_context(q,c)
            for a,b in zip(want[:2],got[:2]):np.testing.assert_array_equal(a,b)
            self.assertEqual((int(got[0][0]),int(got[1][0])),literal_transfer(q,d.iloc[0],k.tracks,k.geometry))
        return g,c,q,d

    def test_semantic_branches(self):
        cases=[(np.linspace(1.2,1.7,169),{}),([1.2,3.2],dict(land=box(.9,0,1.1,1),full=False)),
               ([1.2,3.2],dict(land=box(.9,0,1.1,1),mid=GeometryCollection(),full=False)),
               ([1.2,-4,2],dict(land=box(.9,0,1.1,1),full=False)),
               ([1.2,8],dict(land=box(.9,0,1.1,1),full=False)),
               ([1.2,1.3],dict(times=[0,7200],full=False)),([1.2,1.3],dict(full=False)),
               (np.repeat(1.2,169),dict(land=box(.1,0,.3,1))),
               (np.r_[1.2,np.repeat(3.4,168)],dict(domain=box(-3,-2,1.5,3).union(box(2,-2,6,3))))]
        for values,kw in cases:
            with self.subTest(kwargs=kw):self.compare(values,**kw)

    def test_context_integrity(self):
        g,c,q,d=self.compare(np.linspace(1.2,1.7,169))
        with self.assertRaises(ValueError):c.lon[0]=9
        with self.assertRaises(TypeError):c.arrays['lon']=np.array([9])
        d.loc[0,'lon']=4
        self.assertEqual(c.lon[0],1.2)
        with self.assertRaises(PermissionError):g.classify_context(Query(1,1,7,q.origin,q.lon,q.lat,0,1),c)
        with self.assertRaises(PermissionError):g.classify_context(Query(99,1,7,q.origin,q.lon,q.lat,0,2),c)
        other=G1Kernel(g.geometry,g.tracks)
        with self.assertRaises(ValueError):other.classify_context(q,c)

    def test_numeric_domain_boundary(self):
        k,q,d=fixture(np.repeat(1.2,169));k.geometry.domain=box(-81,20,-8,55)
        g=G1Kernel(k.geometry,k.tracks,rectangular_domain=True)
        xs=np.array([-81.,-8.,np.nextafter(-81.,-np.inf),np.nextafter(-81.,np.inf),np.nextafter(-8.,np.inf)])
        ys=np.array([20.,55.,np.nextafter(20.,-np.inf),np.nextafter(55.,np.inf),30.])
        x,y=np.meshgrid(xs,ys)
        np.testing.assert_array_equal(g.inside_domain(x,y),sh.intersects_xy(k.geometry.domain,x,y))
        k.geometry.domain=box(-80,20,-8,55)
        with self.assertRaises(ValueError):G1Kernel(k.geometry,k.tracks,rectangular_domain=True)

    def test_distinct_true_starts_and_unindexed(self):
        g,c,q,d=self.compare(np.linspace(1.2,1.7,169))
        q2=Query(q.id,2,7,q.origin,.8,.4,0,1)
        self.assertNotEqual(g.classify_context(q,c)[0][0],g.classify_context(q2,c)[0][0])
        k,q,d=fixture(np.linspace(1.2,2.5,169));k.geometry.states.remove(cell(1.5));d['fold']=2
        g=G1Kernel(k.geometry,k.tracks);c=g.context(d,q,[1],'synthetic')
        self.assertEqual(tuple(x[0] for x in g.classify_context(q,c)[:2]),(-3,4))


if __name__=='__main__':unittest.main()

class ScoringParityTests(unittest.TestCase):
    def test_cached_scores_preserve_ties_and_search(self):
        from data3001.modelling.baselines.actual_origin_displacement_s3_e5_selection import ForecastCase,CaseEvaluator,search
        from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_scoring import CachedCaseEvaluator
        rng=np.random.default_rng(41);cases=[];states=np.array([1,2,3,4,-2])
        for j in range(12):
            p=rng.dirichlet(np.ones(5));q=rng.dirichlet(np.ones(5))
            if j==0:p=np.array([.45,.45,0,0,.1])
            if j%4==0:q=p.copy()  # No donors implies the unchanged B2 fallback.
            cases.append(ForecastCase(states,p,q,int(states[j%5]),[0,.1,1,10][j%4],1/12,('role',j%3)))
        old=CaseEvaluator(cases);new=CachedCaseEvaluator(cases)
        for a in np.linspace(0,1,21):
            for gamma in (0,.5,1,2):
                np.testing.assert_allclose(list(old.metrics(a,gamma).values()),list(new.metrics(a,gamma).values()),atol=1e-12,rtol=0)
        refs={m:dict(brier=2.,region90_hit=0.,region90_cells=4.) for m in ('Fixed','LocalEndpointAdaptive')}
        x,y=search(old,refs),search(new,refs)
        self.assertEqual(x['memberships'],y['memberships'])
        for model in x['selections']:
            self.assertEqual(x['selections'][model],y['selections'][model])

class CheckpointTests(unittest.TestCase):
    def test_atomic_complete_chunk_and_stale_rejection(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        import pandas as pd
        from data3001.paths import file_sha256
        from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_checkpoint import read_checkpoint
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'chunk.csv'
            frame=pd.DataFrame(dict(donor_fold=[2,3],destination=[42,-3],reason=[0,5],pair_count=[3,2]));frame.to_csv(path,index=False)
            receipt=dict(context_identity='input-geometry-version',query_coordinate_hex=[float(-75).hex(),float(31).hex()],horizon=7,source_key=[99,123],query_fold=1,algorithm=['G1',2048],sha256=file_sha256(path),donors=5)
            args=('input-geometry-version',receipt['query_coordinate_hex'],7,[99,123],1,['G1',2048])
            pd.testing.assert_frame_equal(frame,read_checkpoint(path,receipt,*args))
            with self.assertRaises(ValueError):read_checkpoint(path,receipt,'changed',*args[1:])
            path.write_text(path.read_text()+'\n')
            with self.assertRaises(ValueError):read_checkpoint(path,receipt,*args)

class G2Tests(unittest.TestCase):
    def test_component_index_and_clipped_mask_equivalence(self):
        from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_g2 import G2Kernel
        shapes=[GeometryCollection(),box(.9,0,1.1,1),box(.9,0,1.1,1).union(box(4,0,5,1)),box(-2,-1,5,2).difference(box(-1,0,4,1))]
        for land in shapes:
            for values in ([1.2,3.2],[1.2,-4,2],np.linspace(1.2,1.7,169)):
                k,q,d=fixture(values,land=land,mid=GeometryCollection(),full=len(values)==169);d['fold']=2
                want=k.classify(q,d,[1]);g=G2Kernel(k.geometry,k.tracks);ctx=g.context(d,q,[1],'synthetic');actual=g.classify_context(q,ctx)
                np.testing.assert_array_equal(want[0],actual[0]);np.testing.assert_array_equal(want[1],actual[1])

class G3Tests(unittest.TestCase):
    def test_time_blocks_preserve_events_and_continuation(self):
        from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_g3 import G3Kernel
        from data3001.modelling.baselines.actual_origin_displacement_s3_e5_inputs import ActualOriginKernel
        from dataclasses import replace
        scenarios=[('safe',169),('safe',721),('gap32',169),('invalid33',169),('missing',80),('land32',169),('exit_return',169),('unindexed',169),('curved_water',169)]
        for name,length in scenarios:
            with self.subTest(name=name,length=length):
                values=np.linspace(1.2,3.2,length);land=box(.9,.0,1.1,.7) if name in ('land32','curved_water') else GeometryCollection()
                if name=='land32':values=np.r_[np.linspace(1.2,1.8,32),3.2,np.repeat(3.2,length-33)]
                if name=='exit_return':values=np.r_[np.repeat(1.2,32),-4.,np.repeat(1.2,length-33)]
                k,q,d=fixture(values,land=land,full=length in (169,721));d['fold']=2
                if length==721:q=replace(q,horizon=30);d['horizon_days']=30;d['full_interval']=True
                if name=='gap32':k.tracks.time=k.tracks.time.copy();k.tracks.time[32:]+=3600;d['full_interval']=False
                if name=='invalid33':k.tracks.valid=k.tracks.valid.copy();k.tracks.valid[33]=False;d['full_interval']=False
                if name=='unindexed':k.geometry.states.remove(cell(1.5))
                if name=='curved_water':
                    k.tracks.lat=.4+.7*np.sin(np.linspace(0,np.pi,length));d['y_min']=k.tracks.lat.min();d['y_max']=k.tracks.lat.max();d['end_lat']=k.tracks.lat[-1]
                reference=ActualOriginKernel(k.geometry,k.tracks);want=reference.classify(q,d,[1])
                g=G3Kernel(k.geometry,k.tracks);ctx=g.context(d,q,[1],'synthetic');got=g.classify_context(q,ctx)
                np.testing.assert_array_equal(want[0],got[0]);np.testing.assert_array_equal(want[1],got[1])
                self.assertEqual((int(got[0][0]),int(got[1][0])),literal_transfer(q,d.iloc[0],k.tracks,k.geometry))
                if name=='curved_water':self.assertGreater(got[2]['proven_hourly_steps'],0)
