"""Independent arithmetic/geometry/integrity audit; no production aggregation calls."""
import json,stat,time
import numpy as np
import pandas as pd
import shapely as sh
from shapely.geometry import box
from scipy.optimize import minimize_scalar
from pyproj import Geod,Transformer
from runtime import *

GEOD=Geod(ellps='WGS84')
METRICS=['energy_km','h90','area90_km2','land_mass','outside_D_mass']
KEY=['id','origin_source_obs','horizon_days']

def main():
    s,roster=start()
    checks={}
    try:
      with stage('audit') as check:
        a=pd.read_parquet(RES/'origin_availability.parquet')
        assert not a.duplicated(KEY).any() and set(a.id)==set(roster.id)
        train=s.frame(E7/'training_coordinates.parquet',columns=KEY)
        valid=s.frame(E7/'query_coordinates.parquet',columns=KEY)
        for cohort,expected in [('train',train),('validation',valid)]:
            got=a[a.cohort.eq(cohort)&a.used_by_original][KEY].sort_values(KEY).reset_index(drop=True)
            pd.testing.assert_frame_equal(got,expected.sort_values(KEY).reset_index(drop=True))
        checks['frozen_pair_keys_unchanged']=True
        # Read every source track independently; infer availability by a time dictionary.
        dm=s.json(ROOT/'configs/dataset_manifest.json');qm=s.json(ROOT/'configs/qualification_manifest.json')
        counts=[]
        for number,row in enumerate(roster.itertuples(index=False),1):
            sid=str(row.id);r=dm['records'][sid];q=qm['records'][sid]
            tr=s.frame(ROOT/r['path'],r['sha256'],columns=['source_obs','time'])
            fl=s.frame(ROOT/q['path'],q['sha256'],columns=['source_obs','time','analytical_row','position_ok','mapping_ok','in_R'])
            assert np.array_equal(tr[['source_obs','time']],fl[['source_obs','time']])
            f=a[a.id.eq(row.id)]
            good_times=set(tr.loc[(fl.analytical_row&fl.position_ok&fl.mapping_ok).to_numpy(),'time'])
            available=np.array([float(t) in good_times for t in f.target_epoch])
            assert np.array_equal(available,f.endpoint_available)
            administrative=((f.secondary_predicates.astype('int64').to_numpy()&2)>0)|f.role_excluded.to_numpy()
            invalid=((f.secondary_predicates.astype('int64').to_numpy()&1)>0)|f.reason_code.eq(1).to_numpy()
            exit=(f.reason_code.eq(0)&f.outside).to_numpy()
            risk=~(administrative|invalid|exit);missing=risk&~available
            assert np.array_equal(risk,f.risk_set) and np.array_equal(missing,f.missing_endpoint)
            counts.append((int(row.id),int(risk.sum()),int(missing.sum())))
            if number%100==0:check();print('Independent track checks',number,flush=True)
        checks['all_383_endpoint_availability_independent']=True
        result=pd.read_csv(RES/'availability_summary.csv').set_index('cohort')
        values={i:(n,m) for i,n,m in counts}
        for cohort,group in roster.groupby('cohort'):
            pairs=[values[int(i)] for i in group.id]
            risk=sum(n for n,m in pairs);miss=sum(m for n,m in pairs)
            rates=[m/n for n,m in pairs if n]
            assert result.loc[cohort,'risk']==risk and result.loc[cohort,'missing']==miss
            assert abs(result.loc[cohort,'missing_id_equal_rate']-sum(rates)/len(rates))<1e-12
        reasons=pd.read_csv(RES/'original_reason_counts.csv')
        for row in reasons.itertuples(index=False):
            g=a[(a.cohort==row.cohort)&(a.reason_code==row.reason_code)]
            assert len(g)==row.origins and g.id.nunique()==row.ids
        checks['missing_denominators_and_reasons_conserved']=True
        coastal_keys=pd.read_parquet(RES/'coastal_groups.parquet',columns=KEY+['coastal_group','group'])
        assoc=a.merge(coastal_keys,on=KEY,validate='one_to_one')
        for filename,keys in [('availability_by_death.csv',['cohort','official_typedeath']),
            ('availability_coastal_cross.csv',['cohort','coastal_group','official_typedeath']),
            ('availability_coastal_summary.csv',['cohort','coastal_group']),
            ('availability_coastal_fine_summary.csv',['cohort','group'])]:
            tab=pd.read_csv(RES/filename)
            for rec in tab.to_dict('records'):
                mask=np.ones(len(assoc),dtype=bool)
                for key in keys:mask&=assoc[key].eq(rec[key]).to_numpy()
                f=assoc.loc[mask];rates=[];positive=0;missing_ids=0;zero=0
                for ident in f.id.unique():
                    g=f[f.id.eq(ident)];n=int(g.risk_set.sum());m=int(g.missing_endpoint.sum())
                    if n:rates.append(m/n);positive+=1
                    else:zero+=1
                    missing_ids+=int(m>0)
                assert rec['risk_ids']==positive and rec['missing_ids']==missing_ids and rec['zero_denominator_ids']==zero
                assert rec['risk']==int(f.risk_set.sum()) and rec['missing']==int(f.missing_endpoint.sum())
                if rates:assert np.isclose(rec['missing_id_equal_rate'],sum(rates)/len(rates),atol=1e-12,rtol=0)
                else:assert pd.isna(rec['missing_id_equal_rate'])
        checks['all_association_strata_independent_id_denominators']=True
        ev=pd.read_csv(RES/'id_evidence.csv');cases=pd.read_csv(RES/'case_review.csv')
        assert len(ev)==383 and not ev.id.duplicated().any() and len(cases)==12
        assert set(cases.id)==set(ev[ev.manual_reviewed].id)
        boundary=s.frame(AUDIT/'boundary_assessment.csv').set_index('id')
        assert np.array_equal(ev.sort_values('id').official_typedeath,boundary.sort_index().official_typedeath)
        assert ev.event_lower_epoch.isna().all() and ev.event_upper_epoch.isna().all()
        assert cases.event_lower_epoch.isna().all() and cases.event_upper_epoch.isna().all()
        decisions=json.loads((LOG/'case_review_decisions.json').read_text())
        assert set(map(int,decisions['decisions']))==set(cases.id)
        for row in cases.itertuples(index=False):
            assert row.review_status=='individually_reviewed_records_only'
            assert row.review_note==decisions['decisions'][str(row.id)]
        # Deterministic review selection independent of scores.
        selected=[];already=set()
        for category,mask in [('official_grounding',ev.official_typedeath.eq(1)),
            ('unknown_coastal',ev.official_typedeath.isin([3,4])&ev.distance_upper_m.le(5000)),('conflict',ev.metadata_conflict)]:
            f=ev[mask&~ev.id.isin(already)].copy();f['related']=f.official_end_windows.gt(0)
            ids=f.sort_values(['related','id'],ascending=[False,True]).id.head(4).tolist()
            selected.extend((i,category) for i in ids);already.update(ids)
        assert list(zip(cases.id,cases.review_category))==selected
        tails=pd.read_parquet(RES/'terminal_windows.parquet')
        for row in cases.itertuples(index=False):
            t=tails[tails.id.eq(row.id)]
            tail=t[t.analytical_row&t.position_ok&t.time.le(row.official_end_epoch)].sort_values('time').iloc[-1]
            assert int(tail.source_obs)==row.last_retained_before_source_obs
        checks['official_categories_and_12_cases_checked']=True
        scores=s.frame(MDN/'outer_complete.parquet')
        groups=pd.read_parquet(RES/'coastal_groups.parquet')
        g=groups[(groups.cohort=='validation')&groups.used_by_original]
        assert len(g)==33971 and g.id.nunique()==45
        metrics=pd.read_csv(RES/'coastal_summary.csv')
        original=s.frame(MDN/'summary.csv').set_index('model')
        for record in metrics.itertuples(index=False):
            if record.group=='all':selected_keys=set(g.origin_source_obs)
            else:selected_keys=set(g[(g.coastal_group==record.group)|(g.group==record.group)].origin_source_obs)
            f=scores[(scores.model==record.model)&scores.origin_source_obs.isin(selected_keys)]
            assert len(f)==record.pairs and f.id.nunique()==record.ids
            for metric in METRICS:
                means=[]
                for ident in sorted(set(f.id)):
                    vals=f.loc[f.id.eq(ident),metric].to_numpy();means.append(float(vals.sum()/len(vals)))
                actual=sum(means)/len(means)
                assert np.isclose(actual,getattr(record,metric),atol=1e-8,rtol=1e-10)
                if record.group=='all':assert np.isclose(actual,original.loc[record.model,metric],atol=1e-8,rtol=1e-10)
            assert record.interval_supported==(record.ids>=10)
        ci=pd.read_csv(RES/'coastal_intervals.csv')
        assert not ci.group.isin(['near_50km','<=10km','10_50km']).any()
        draws=np.load(RES/'bootstrap_draws.npy')
        assert np.array_equal(draws,np.random.default_rng(20261110).integers(0,45,size=(5000,45)))
        ids=np.sort(g.id.unique())
        for row in ci.itertuples(index=False):
            gg=g if row.group=='all' else g[(g.coastal_group==row.group)|(g.group==row.group)]
            f=scores[(scores.model==row.model)&scores.origin_source_obs.isin(gg.origin_source_obs)]
            unit=np.array([f.loc[f.id.eq(i),row.metric].mean() if f.id.eq(i).any() else np.nan for i in ids])
            z=unit[draws];m=np.nansum(z,axis=1)/np.isfinite(z).sum(axis=1)
            lo,hi=np.quantile(m,[.025,.975])
            assert np.isclose(lo,row.lower,atol=1e-8,rtol=1e-10) and np.isclose(hi,row.upper,atol=1e-8,rtol=1e-10)
        checks['global_subgroup_metrics_and_bootstrap_reproduced']=True
        # Separate method: nearest projected ORIGINAL segments, scalar geodesic minimization.
        cat=s.json(ROOT/'configs/assets.json')['assets'];r=cat['land_mask_high']
        land=sh.from_wkb(s.verified(ROOT/r['path'],r['sha256']).read_bytes())
        point_table=pd.read_parquet(RES/'coastal_distances.parquet')
        geo=json.loads((LOG/'geometry_projection.json').read_text())
        xmin,ymin,xmax,ymax=geo['bounds']
        boundary_geom=land.boundary.intersection(box(xmin,ymin,xmax,ymax))
        segments=[]
        for part in sh.get_parts(boundary_geom):
            coord=np.asarray(part.coords);segments.append(np.stack([coord[:-1],coord[1:]],axis=1))
        seg=np.concatenate(segments)
        projection=Transformer.from_crs('EPSG:4326','+proj=laea +lat_0=35 +lon_0=-75 +datum=WGS84 +units=m',always_xy=True)
        lines=sh.linestrings(seg);projected=sh.transform(lines,projection.transform,interleaved=False);tree=sh.STRtree(projected)
        ix=np.unique(np.linspace(0,len(point_table)-1,200).astype(int));audit_rows=[]
        for index in ix:
            row=point_table.iloc[index];x,y=projection.transform(row.lon,row.lat)
            p=sh.Point(x,y);j=int(tree.nearest(p));dist=p.distance(projected[j])
            candidates=tree.query(p.buffer(dist+2000).envelope)
            distances=sh.distance(projected[candidates],p)
            candidates=candidates[distances<=dist+2000]
            best=np.inf
            for edge in seg[candidates]:
                def objective(t):
                    q=edge[0]+t*(edge[1]-edge[0]);return GEOD.inv(row.lon,row.lat,q[0],q[1])[2]
                sol=minimize_scalar(objective,bounds=(0,1),method='bounded',options={'xatol':1e-8})
                best=min(best,objective(0),objective(1),float(sol.fun))
            assert best>=row.distance_lower_m-0.02 and best<=row.distance_upper_m+0.02,(index,best,row.distance_lower_m,row.distance_upper_m)
            audit_rows.append(dict(position=int(index),independent_geodesic_m=best,lower_m=row.distance_lower_m,upper_m=row.distance_upper_m))
            if len(audit_rows)%20==0:check();print('Independent geometry',len(audit_rows),flush=True)
        save_frame('independent_geometry_audit.csv',pd.DataFrame(audit_rows))
        checks['200_points_independent_geodesic_minimization']=True
        # Full protected read set, including every 15,593 frozen payload files.
        before=json.loads((LOG/'input_manifest.json').read_text())
        for number,(name,record) in enumerate(before.items(),1):
            p=Path(name) if name.startswith('/') else ROOT/name
            assert sha(p)==record['sha256'],('final source hash',name)
            if number%2500==0:check()
        freeze=json.loads((FREEZE/'manifest.json').read_text())
        for record in freeze['files']:
            assert stat.S_IMODE((ROOT/record['path']).stat().st_mode)==int(record['expected_mode'],8)
        checks['all_inputs_byte_identical_after_diagnosis']=len(before)
        checks['all_frozen_modes_unchanged']=len(freeze['files'])
        checks['final_test_access']=False
        checks['model_training_or_inference_calls']=0
        checks['new_ES_or_region_integration']=0
        json_write(LOG/'verification.json',{'passed':True,'checks':checks})
        print('INDEPENDENT AUDIT PASSED',checks,flush=True)
    except Exception as e:
        json_write(LOG/'verification.json',{'passed':False,'checks':checks,'error':repr(e)})
        raise
    finally:s.save()

if __name__=='__main__':main()
