"""Synthetic, hand-checkable S4 E1 semantics; no released trajectories read."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import box
from data3001.paths import ProjectPaths
from data3001.modelling.common.qualified_count_inputs import ExperimentGuard
from data3001.modelling.common.prediction_regions import probability_region
from data3001.modelling.baselines import seasonal_conditioning_s4_e1_inputs as inp
from data3001.modelling.baselines import seasonal_conditioning_s4_e1 as m
from data3001.modelling.baselines.seasonal_conditioning_s4_e1_audit import audit_prepared
from data3001.modelling.baselines.seasonal_conditioning_s4_e1_report import write_report


def config():
    return {'train_start':'2012-01-01','cutoff':'2020-01-01','validation_end':'2023-01-01',
            'horizons':[7,30],'uncertainty_replicates':10000,'seed':20261102,'screens':6}


def row(d,o,h,t,i,j):
    t=pd.Timestamp(t,tz='UTC')
    return {'id':d,'origin_source_obs':o,'horizon_days':h,'origin_time_UTC':t,'origin_cell_1':i,
            'departure_season':(t.month%12)//3,'destination_cell_1':j,'target_epoch':t.timestamp()+h*86400,
            'required_interval_end_epoch':t.timestamp()+h*86400}


class SeasonalContract(unittest.TestCase):
    def test_utc_season_boundaries(self):
        dates=pd.Series(pd.to_datetime(['2020-02-29T23:00Z','2020-03-01T00:00Z','2020-05-31T23:00Z','2020-06-01T00:00Z','2020-08-31T23:00Z','2020-09-01T00:00Z','2020-11-30T23:00Z','2020-12-01T00:00Z','2021-01-01T00:00Z'],utc=True))
        self.assertEqual(inp.season_code(dates).tolist(),[0,1,1,2,2,3,3,0,0])

    def test_label_cutoff_and_union_ids(self):
        q=pd.DataFrame([row(1,0,7,'2019-12-24',10,10),row(1,1,7,'2019-12-25',10,10),
                        row(2,0,7,'2018-01-01',10,10),row(2,1,30,'2020-01-01',10,10),
                        row(3,0,7,'2011-12-31',10,10),row(4,0,7,'2023-01-01',10,10)])
        roles,ids=inp.assign_roles(q,config())
        self.assertEqual(ids,[2])
        self.assertEqual(roles.role.tolist(),['train','excluded_label_cutoff','excluded_validation_id','validation','outside_training_window','outside_training_window'])

    def test_pair_training_fallback_weights_and_audit(self):
        q=pd.DataFrame([*[row(1,k,7,'2018-01-01',10,10) for k in range(9)],row(2,0,7,'2018-01-01',10,11),
                        row(2,1,7,'2018-04-01',10,11),*[row(3,k,7,'2021-01-01',10,10) for k in range(9)],
                        row(4,0,7,'2021-01-01',10,11),row(4,1,7,'2021-07-01',10,11)])
        cfg=config();cfg['horizons']=[7]
        roles,ids=inp.assign_roles(q,cfg);train=q.loc[roles.role.eq('train')];v=inp.validation_weights(q.loc[roles.role.eq('validation')])
        states=np.array([10,11,-2]);mat,sup=m.fit(train,[10,12],states,cfg,ids)
        np.testing.assert_allclose(mat[(7,10,-1)],[9/11,2/11,0])
        np.testing.assert_allclose(mat[(7,10,0)],[.9,.1,0])
        self.assertIsNone(mat[(7,12,0)])
        np.testing.assert_array_equal(mat[(7,10,2)],mat[(7,10,-1)])
        self.assertAlmostEqual(v.loc[v.id.eq(3),'weight'].sum(),.5)
        self.assertAlmostEqual(v.loc[v.id.eq(4),'weight'].sum(),.5)
        cache,meta,entries=m.predict(mat,v[inp.FEATURES],states)
        bundle={'qualified':q,'roles':roles,'train':train,'validation':v,'validation_ids':ids,'states':states}
        _,audit=audit_prepared(bundle,mat,sup,cache,cfg);self.assertTrue(audit['source_roles_independent'])
        cases,means,summary,slices=m.score(cache,v,sup,states)
        fallback=cases.loc[(cases.model=='B2SeasonalC1')&cases.annual_fallback].iloc[0]
        a=cases.loc[(cases.model=='B2Annual')&(cases.origin_source_obs==1)&(cases.id==4)].iloc[0]
        self.assertEqual(fallback.brier,a.brier)
        self.assertAlmostEqual(summary.loc[summary.model=='B2SeasonalC1','annual_fallback'].iloc[0],.25)
        draws,values,ci=m.paired_uncertainty(means,ids,cfg)
        self.assertEqual(draws.shape,(10000,2));self.assertEqual(values.shape,(10000,1,3))
        # Independent one-origin paired multiplier calculation.
        pivot=means.pivot(index='id',columns='model',values='brier').sort_index()
        delta=(pivot.B2SeasonalC1-pivot.B2Annual).to_numpy()
        np.testing.assert_allclose(values[:,0,0],(draws*delta).sum(1)/draws.sum(1),atol=1e-12,rtol=0)
        changed=q.copy();changed.loc[roles.role.eq('validation'),'destination_cell_1']=-2
        mat2,_=m.fit(changed.loc[roles.role.eq('train')],[10,12],states,cfg,ids)
        for key,p in mat.items():
            if p is not None:np.testing.assert_array_equal(p,mat2[key])

    def test_zero_truth_and_region_ties_exit(self):
        p=np.array([.4,.3,.3,0.]);states=np.array([10,11,-2,12])
        mask,r=probability_region(p,states)
        self.assertEqual(mask.tolist(),[True,True,True,False]);self.assertEqual(r['region90_cells'],2)
        self.assertAlmostEqual(1+np.square(p).sum()-2*p[3],1.34)
        with self.assertRaises(ValueError):probability_region(np.array([.4,.3,.2,0]),states)

    def test_guard_and_atomic_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'configs').mkdir();(root/'configs/assets.json').write_text('{"schema_version":1,"assets":{}}')
            paths=ProjectPaths(root);run=paths.create_run('synthetic',{})
            guard=ExperimentGuard(paths,run,[])
            for p in [root/'data/test/1.parquet',root/'data/train/1.parquet',root/'results/runs/old/model.parquet']:
                with self.assertRaises(PermissionError):guard('open',(str(p),'r',0))
            with self.assertRaises(PermissionError):guard('open',(str(root/'configs/assets.json'),'w',0))
            paths.publish(run['results']/'value.json',lambda f:f.write(b'{}'))
            with self.assertRaises(FileExistsError):paths.publish(run['results']/'value.json',lambda f:f.write(b'new'))

    def test_acceptance_separates_point_and_supported_gain(self):
        summary=pd.DataFrame([{'model':'B2Annual','horizon_days':7,'brier':1.,'h90':.8,'k90':40.,'season_changed':0.},
                              {'model':'B2SeasonalC1','horizon_days':7,'brier':.99,'h90':.81,'k90':39.,'season_changed':1.}])
        ci=pd.DataFrame([{'horizon_days':7,'metric':m,'adjusted_lower':lo,'adjusted_upper':up} for m,lo,up in [('brier',-.04,.02),('h90',-.02,.04),('k90',-3.,1.)]])
        result=m.decisions(summary,ci).iloc[0]
        self.assertTrue(result.QUALITY_POINT_GAIN);self.assertFalse(result.QUALITY_GAIN_SUPPORTED_CONDITIONALLY)
        self.assertEqual(result.status,'QUALITY_NOT_ESTABLISHED')
        summary.loc[summary.model=='B2SeasonalC1','h90']=.79
        self.assertEqual(m.decisions(summary,ci).iloc[0].status,'BRIER_GAIN_WITH_QUALITY_TRADEOFF')

    def test_report_and_repeatable_figures(self):
        rows=[];origins=[44744,44742,44382];counter=0
        for h in [7,30]:
            for i in origins:
                for month in [1,4,7,10]:
                    for d,year in [(1,2018),(2,2019),(3,2021),(4,2022)]:
                        rows.append(row(d,counter,h,f'{year}-{month:02d}-01',i,origins[d%3]));counter+=1
        q=pd.DataFrame(rows);cfg=config();roles,ids=inp.assign_roles(q,cfg)
        train=q.loc[roles.role.eq('train')];v=inp.validation_weights(q.loc[roles.role.eq('validation')]);states=np.array([*origins,-2])
        mat,sup=m.fit(train,origins,states,cfg,ids);cache,_,_=m.predict(mat,v[inp.FEATURES],states)
        cases,means,summary,slices=m.score(cache,v,sup,states);multi,draws,ci=m.paired_uncertainty(means,ids,cfg);flags=m.decisions(summary,ci)
        bundle={'train':train,'validation':v,'states':states}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'configs').mkdir();land=root/'land.wkb';land.write_bytes(shapely.to_wkb(box(-90,20,-82,50)))
            (root/'configs/assets.json').write_text(json.dumps({'schema_version':1,'assets':{'land_mask_intermediate':{'path':'land.wkb'}}}))
            paths=ProjectPaths(root);a=paths.create_run('fixture_a',{});b=paths.create_run('fixture_b',{})
            for run in [a,b]:
                names=write_report(paths,run,bundle,mat,sup,summary,ci,flags,slices,{},timing_only=True)
                self.assertEqual(len(names),10)
            for name in names:self.assertEqual((a['results']/name).read_bytes(),(b['results']/name).read_bytes())
            self.assertIn('TIMING FIXTURE',(a['results']/'review.html').read_text())


if __name__=='__main__':unittest.main()
