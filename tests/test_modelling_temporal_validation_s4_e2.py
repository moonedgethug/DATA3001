"""Synthetic semantic checks for validation policies, not a new model."""
import unittest
import json
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from data3001.modelling.baselines import temporal_validation_s4_e2_inputs as inp
from data3001.modelling.baselines import temporal_validation_s4_e2 as v
from data3001.modelling.baselines import temporal_validation_s4_e2_audit as audit
from data3001.modelling.baselines import local_endpoint_adaptive_s3_e2 as old


def row(d,o,h,t,i,j):
    t=pd.Timestamp(t,tz='UTC')
    return dict(id=d,origin_source_obs=o,horizon_days=h,origin_time_UTC=t,origin_cell_1=i,
                destination_cell_1=j,departure_season=(t.month%12)//3,required_interval_end_epoch=t.timestamp()+h*86400)


def fixture():
    rows=[];n=0
    for h in [7,30]:
        for d,t in [(1,'2010-01-01'),(2,'2011-01-01'),(3,'2012-01-01'),(4,'2020-01-01'),(5,'2021-01-01')]:
            for i in [44744,44745]:
                for j in range(d+1):rows.append(row(d,n,h,t,i,44744+(j%2)));n+=1
    q=pd.DataFrame(rows)
    role=inp.temporal_role(q,'2020-01-01','2023-01-01','C_outer')
    bundle={'origins':np.array([44744,44745,45000]),'states':np.array([-2,44744,44745,45000])}
    return q,role,bundle


class ValidationPolicies(unittest.TestCase):
    def test_label_boundary_cross_horizon_ID_and_absorbing_exit(self):
        q=pd.DataFrame([row(1,0,7,'2019-12-24',44744,44744),row(1,1,7,'2019-12-25',44744,44744),
            row(2,0,7,'2018-01-01',44744,44744),row(2,1,30,'2020-01-01',44744,44744),
            row(3,0,30,'2019-12-31',44744,-2)])
        q.loc[4,'required_interval_end_epoch']=pd.Timestamp('2019-12-31T12:00Z').timestamp()
        r=inp.temporal_role(q,'2020-01-01','2023-01-01','test')
        self.assertEqual(r['ledger'].role.tolist(),['train','excluded_label_cutoff','excluded_validation_id','validation','train'])
        self.assertEqual(set(r['train'].id),{1,3})

    def test_adapter_matches_all_legacy_candidate_Brier(self):
        _,r,b=fixture();base=v.fit_role(r,b)
        fresh=v.candidate_brier(base,r['validation']).set_index(v.UNIT)
        legacy=old.candidate_units(base,inp.counts(r['validation']),sorted(r['validation'].id.unique()))
        for k,(m,a,g) in enumerate(v.SPECS):
            z=legacy[(legacy.model==m)&(legacy.parameter_a==a)&(legacy.parameter_gamma==g)].set_index(v.UNIT)
            np.testing.assert_allclose(fresh.loc[z.index,v.SCORE_COLS[k]],z.brier,rtol=0,atol=1e-12)
        ref=audit.reference_fit(r['train'],b['states'])
        self.assertLessEqual(audit.audit_inner(r,base,fresh.reset_index(),ref)['maximum_error'],1e-12)

    def test_pooling_repeated_ID_preserves_times_then_ID_weights(self):
        parts=[]
        for d,n,score in [(1,9,.1),(1,1,.9),(2,3,.7)]:
            parts.append(pd.DataFrame([dict(horizon_days=7,origin_cell_1=44744,id=d,eligible_pairs=n,supported=True,
                **{c:score for c in v.SCORE_COLS})]))
        units,pool=v.pool_candidates(parts)
        self.assertAlmostEqual(units.loc[units.id==1,v.SCORE_COLS[0]].iloc[0],.18)
        self.assertAlmostEqual(pool.brier.iloc[0],.44)
        # An unsupported time window must not turn into an invented zero score.
        parts.append(pd.DataFrame([dict(horizon_days=7,origin_cell_1=44744,id=1,eligible_pairs=100,supported=False,
            **{c:np.nan for c in v.SCORE_COLS})]))
        _,pool=v.pool_candidates(parts)
        self.assertAlmostEqual(pool.brier.iloc[0],.44);self.assertEqual(pool.unsupported_pairs.iloc[0],100)

    def test_same_training_B2_and_winner_freeze(self):
        _,r,b=fixture();base=v.fit_role(r,b);u=v.candidate_brier(base,r['validation'])
        _,pool=v.pool_candidates([u]);chosen=v.select(pool)
        # Synthetic selection values are used only to exercise deterministic ties.
        tied=pool.copy();tied['brier']=1.
        c=v.select(tied);self.assertEqual(c[c.winner].model.tolist(),['B2','B2'])
        choices={'G':chosen,'T':c}
        features=pd.DataFrame([(h,i) for h in [7,30] for i in b['origins']],columns=['horizon_days','origin_cell_1'])
        cache,meta=v.forecast_block(base,choices,features,'C')
        for h in [7,30]:
            np.testing.assert_array_equal(cache[('C','G','B2',h,44744)]['p'],cache[('C','T','B2',h,44744)]['p'])
            self.assertIsNone(cache[('C','G','B2',h,45000)])
        changed=r['validation'].copy();changed['destination_cell_1']=-2
        again,_=v.forecast_block(base,choices,changed[inp.FEATURES],'C')
        np.testing.assert_array_equal(cache[('C','G','Selected',7,44744)]['p'],again[('C','G','Selected',7,44744)]['p'])

    def test_explicit_scoring_and_shared_ID_multiplier(self):
        _,r,b=fixture();base=v.fit_role(r,b);u=v.candidate_brier(base,r['validation'])
        _,pool=v.pool_candidates([u]);c=v.select(pool)
        choices={'G':c.copy(),'T':c.copy()}
        cache,meta=v.forecast_block(base,choices,r['validation'][inp.FEATURES],'C')
        cases=v.score_block(cache,r['validation'],'C',b['states']);units,summary=v.summaries(cases)
        ref=audit.reference_fit(r['train'],b['states'])
        audit.audit_outer(r,cache,meta,cases,units,summary,ref,'C')
        cfg={'replicates':100,'seed':20261103,'blocks':[{'name':'C'}],'tail':.05/36,'equivalence':{'brier':.001,'h90':.01,'relative_k90':.05}}
        ids,mul,draws,ci=v.uncertainty(units,cfg);flags=v.decisions(summary,ci,cfg)
        np.testing.assert_allclose(draws,0,atol=1e-12)
        self.assertTrue(flags.equivalent_supported.all());self.assertFalse(flags.quality_supported.any())
        audit.audit_uncertainty(units,ids,mul,draws,ci,flags,summary,cfg)

    def test_equivalence_requires_interval_inside_all_margins(self):
        summary=pd.DataFrame([dict(block='C',horizon_days=h,policy=p,model='Selected',brier=1.,h90=.8,k90=20.) for h in [7,30] for p in ['G','T']])
        ci=pd.DataFrame([dict(block='C',horizon_days=h,metric=m,adjusted_lower=-.1,adjusted_upper=.1) for h in [7,30] for m in ['brier','h90','k90','relative_k90']])
        cfg={'blocks':[{'name':'C'}],'equivalence':{'brier':.001,'h90':.01,'relative_k90':.05}}
        self.assertFalse(v.decisions(summary,ci,cfg).equivalent_supported.any())

    def test_report_full_layout_and_repeatable_figures(self):
        import shapely
        from shapely.geometry import box
        from data3001.paths import ProjectPaths
        from data3001.modelling.baselines.temporal_validation_s4_e2_report import write_report
        _,role,bundle=fixture();base=v.fit_role(role,bundle)
        u=v.candidate_brier(base,role['validation']);_,pool=v.pool_candidates([u]);chosen=v.select(pool)
        cache={};metas=[];selections=[];parts=[];outer={}
        blocks=[{'name':b,'cutoff':cut,'end':end} for b,cut,end in [('A','2014-01-01','2017-01-01'),('B','2017-01-01','2020-01-01'),('C','2020-01-01','2023-01-01')]]
        for b in ['A','B','C']:
            c,m=v.forecast_block(base,{'G':chosen,'T':chosen},role['validation'][inp.FEATURES],b)
            cache.update(c);metas.append(m);outer[b]=role
            selections.extend(chosen.assign(block=b,policy=p) for p in ['G','T'])
            parts.append(v.score_block(c,role['validation'],b,bundle['states']))
        units,summary=v.summaries(pd.concat(parts,ignore_index=True))
        cfg={'blocks':blocks,'replicates':100,'seed':20261103,'tail':.05/36,'equivalence':{'brier':.001,'h90':.01,'relative_k90':.05}}
        _,_,_,ci=v.uncertainty(units,cfg);flags=v.decisions(summary,ci,cfg)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'configs').mkdir();(root/'land.wkb').write_bytes(shapely.to_wkb(box(-90,20,-82,50)))
            (root/'configs/assets.json').write_text(json.dumps({'schema_version':1,'assets':{'land_mask_intermediate':{'path':'land.wkb'}}}))
            paths=ProjectPaths(root);runs=[paths.create_run('a',{}),paths.create_run('b',{})]
            for run in runs:
                names=write_report(paths,run,bundle,outer,cache,pd.concat(metas),summary,ci,flags,pd.concat(selections),pd.DataFrame({'fixture':[True]}),cfg,44744,True)
                self.assertEqual(len(names),10)
                self.assertIn('SYNTHETIC OUTER TARGETS',(run['results']/'review.html').read_text())
            for name in names:self.assertEqual((runs[0]['results']/name).read_bytes(),(runs[1]['results']/name).read_bytes())


if __name__=='__main__':unittest.main()
