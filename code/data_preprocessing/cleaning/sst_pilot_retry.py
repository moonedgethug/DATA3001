"""Corrected replay of the frozen pilot run; v1 remains preserved as evidence.

The v1 source-decoding failure was local pandas copy-on-write, not missing
official data. Scientific matching and interpolation rules are unchanged.
"""
from pathlib import Path
from datetime import datetime,timezone
import concurrent.futures as cf
import hashlib
import json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import requests
import shapely
from data3001.paths import project_paths,file_sha256,asset_path,ensure_output_path
from data3001.dataset import manifest,track_path
from data3001.sst_reconstruction import bilinear,error_bound,verify_frozen
from data3001.sst_coastal import water_support_hull_ok
from data3001.sst_completion import grid_temperature,patch_temperature,temperature_sidecar
from data3001.sst_source_grid import decode_grid

RUN_ID='sst_pilot_completion_20261017_v2'
PARENT='sst_coastal_extension_20261017_v1'
ORIGINAL='sst_reconstruction_20261016_v1'
KEYS=['id','source_obs']
CONTRACT='6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446'
BASE_URL='https://oceanwatch.pifsc.noaa.gov/erddap/'


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False,default=str)+'\n')


def execute():
    root=project_paths().root;b=root/'results/runs'/ORIGINAL;p=root/'results/runs'/PARENT
    dest=ensure_output_path('results/runs/'+RUN_ID)
    assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx')==CONTRACT
    parent_config=json.loads((p/'config.json').read_text());verify_frozen(root,parent_config['dependencies'])
    for name,digest in json.loads((p/'artifact_manifest.json').read_text()).items():
        assert file_sha256(p/name)==digest
    records=manifest()['records']
    def verify_native(item):
        sid,r=item;path=root/r['path']
        assert file_sha256(path)==r['sha256']
        assert len(pq.read_schema(path).names)==130
        assert pq.ParquetFile(path).metadata.num_rows==r['rows']
        return r['rows']
    print('Verifying canonical input identities',flush=True)
    with cf.ThreadPoolExecutor(max_workers=4) as ex:assert sum(ex.map(verify_native,records.items()))==39107061
    scope=pd.read_parquet(p/'coastal_scope.parquet');changed=pd.read_parquet(p/'changed_keys.parquet')
    remaining=scope[scope.in_R].merge(changed[KEYS],on=KEYS,how='left',indicator=True)
    remaining=remaining[remaining._merge.eq('left_only')].drop(columns='_merge')
    t=pd.read_parquet(b/'targets.parquet')
    target=remaining.merge(t[t.kind.eq('target')].drop(columns=['pool','in_R']),on=KEYS,validate='one_to_one')
    coarse=target[target.finite_source_corners.eq(4)].copy().reset_index(drop=True)
    fine=target[target.finite_source_corners.lt(4)].copy().reset_index(drop=True)
    assert len(coarse)==795 and len(fine)==81 and target.pool.eq('train').all()
    assert set(fine.finite_source_corners)=={2,3} and not target.quarantine.any()
    for sid,g in target.groupby('id'):
        native=pq.read_table(track_path(int(sid)),columns=KEYS+['position_ok','mapping_ok']).to_pandas().set_index('source_obs')
        assert native.loc[g.source_obs,'position_ok'].all() and native.loc[g.source_obs,'mapping_ok'].all()
        previous,_=temperature_sidecar(int(sid),run=PARENT)
        q=previous.set_index('source_obs').loc[g.source_obs]
        assert q.sst_method.eq(3).all() and q.sst_use_K.isna().all()
    # Freeze development-only diagnostics before acquiring their values.
    v=t[t.kind.eq('mask') & t.pool.eq('train') & t.in_R & t.all_water_stencil].copy()
    v['order']=[hashlib.sha256(f'20261017:{int(a)}:{int(c)}'.encode()).hexdigest()
                for a,c in zip(v.id,v.source_obs)]
    v=v.sort_values('order').drop_duplicates(['id','season']).groupby('season').head(4).copy()
    v['case_kind']='validation';fine['case_kind']='target'
    cases=pd.concat([fine,v],ignore_index=True)
    assert len(v)==16 and all(records[str(int(sid))]['pool']=='train' for sid in v.id)
    dependencies={str((p/name).relative_to(root)):file_sha256(p/name) for name in
                  ['config.json','verification.json','output_manifest.json','artifact_manifest.json','coastal_scope.parquet','changed_keys.parquet']}
    dependencies.update({str((b/name).relative_to(root)):file_sha256(b/name) for name in
        ['targets.parquet','nodes.parquet','node_sst.npy','node_err.npy','matched_temperature.parquet']})
    dependencies.update({name:file_sha256(root/name) for name in [
        'src/data3001/sst_completion.py','src/data3001/sst_pilot_run.py',
        'src/data3001/sst_pilot_retry.py','src/data3001/sst_source_grid.py','tests/test_sst_source_grid.py',
        'results/runs/sst_pilot_completion_20261017_v1/artifact_manifest.json',
        'src/data3001/sst_reconstruction.py','src/data3001/sst_coastal.py',
        'tests/test_sst_completion.py','docs/sst_pilot_completion_plan.md',
        'configs/dataset_manifest.json','configs/assets.json']})
    dest.mkdir();(dest/'sources').mkdir()
    target.to_parquet(dest/'frozen_targets.parquet',index=False)
    v.to_parquet(dest/'frozen_development_references.parquet',index=False)
    config={'run_id':RUN_ID,'parent_run':PARENT,'contract_sha256':CONTRACT,
       'created_UTC':datetime.now(timezone.utc).isoformat(),'dependencies':dependencies,
       'geometry_waiver':'User-authorized for exactly 795 qualified pilot-R four-corner OISST rows; retain risk diagnostics',
       'fine_policy':'Actual-coordinate matching; same UTC date daily nighttime background; four/three source corner routes',
       'fixed_test_policy':'No test fitting, scoring or selection; current new keys are development IDs only'}
    write_json(dest/'config.json',config)
    source_receipts=[]
    def save_response(url,response,label):
        digest=hashlib.sha256(response.content).hexdigest();name=label+'_'+digest[:16]+'.bin'
        path=dest/'sources'/name
        if not path.exists():path.write_bytes(response.content)
        source_receipts.append({'url':response.url,'requested_url':url,'status':response.status_code,
            'retrieved_UTC':datetime.now(timezone.utc).isoformat(),'path':'sources/'+name,'sha256':digest})
        return name
    print('Reading official fine-grid metadata and small daily windows',flush=True)
    metadata_url=BASE_URL+'info/CRW_sst_v1_0/index.json'
    response=requests.get(metadata_url,timeout=(5,20));response.raise_for_status()
    save_response(metadata_url,response,'metadata')
    rows=response.json()['table']['rows']
    attrs={(r[1],r[2]):r[4] for r in rows if r[0]=='attribute'}
    assert attrs['NC_GLOBAL','product_version']=='1.0'
    assert attrs['analysed_sst','units']=='degree_C'
    assert float(attrs['analysed_sst','valid_min'])==-2 and float(attrs['analysed_sst','valid_max'])==50
    assert abs(float(attrs['NC_GLOBAL','geospatial_lat_resolution'])-.05)<1e-9
    latitude_desc='averageSpacing=-' in next(r[4] for r in rows if r[0]=='dimension' and r[1]=='latitude')
    config['fine_source']={'provider':'NOAA OceanWatch Pacific Islands','dataset':'CRW_sst_v1_0',
        'declared_product_version':attrs['NC_GLOBAL','product_version'],'variable':'analysed_sst',
        'meaning':'daily nighttime background SST; not GDP hourly measurement',
        'time_coverage_start':attrs['NC_GLOBAL','time_coverage_start'],
        'time_coverage_end':attrs['NC_GLOBAL','time_coverage_end'],'metadata_url':metadata_url,
        'caveat':'Do not relabel this delivered archive as a newly verified v3.1 dataset'}
    write_json(dest/'config.json',config)
    source_grids={};failures=[]
    jobs=[]
    for day,g in cases.groupby('day'):
        lat0=np.floor(g.lat.min()*20)/20-.10;lat1=np.ceil(g.lat.max()*20)/20+.10
        lon=g.lon%360;lon0=np.floor(lon.min()*20)/20-.10;lon1=np.ceil(lon.max()*20)/20+.10
        first,last=(lat1,lat0) if latitude_desc else (lat0,lat1)
        date=pd.to_datetime(int(day),unit='D',utc=True).strftime('%Y-%m-%d')
        query=f'analysed_sst[({date}T12:00:00Z)][({first:.4f}):1:({last:.4f})][({lon0:.4f}):1:({lon1:.4f})]'
        jobs.append((int(day),BASE_URL+'griddap/CRW_sst_v1_0.json?'+query))
    def fetch(job):
        day,url=job
        try:
            r=requests.get(url,timeout=(5,25));r.raise_for_status()
        except requests.RequestException as exc:
            return day,url,None,None,type(exc).__name__+': '+str(exc)[:300]
        # Metadata/decoder/programming failures must abort execution; they must
        # not be misreported as unavailable official observations.
        grid=decode_grid(r.json(),day)
        return day,url,r,grid,None
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        for k,(day,url,r,grid,error) in enumerate(ex.map(fetch,jobs)):
            if error:failures.append({'day':day,'url':url,'reason':error})
            else:
                name=save_response(url,r,'grid');source_grids[day]=(grid,name)
            if (k+1)%5==0:print('Fine-grid daily windows',k+1,'/',len(jobs),flush=True)
    lands=[]
    for name in ['land_mask_high','land_mask_intermediate']:
        path=asset_path(name,verify=True);config.setdefault('mask_hashes',{})[name]=file_sha256(path)
        lands.append(shapely.from_wkb(path.read_bytes()))
    # Compute the 795 explicitly authorized estimates with unchanged four-node equations.
    nodes=np.load(b/'node_sst.npy');errs=np.load(b/'node_err.npy')
    ids=coarse[[f'node{k}' for k in range(4)]].to_numpy();values=nodes[ids]
    assert np.isfinite(values).all()
    estimate,weights=bilinear(coarse.u.to_numpy(),coarse.v.to_numpy(),values)
    coarse['sst_use_K']=estimate+273.15;coarse['new_method']=np.int8(6)
    coarse['sst_source_sd_bound_K']=error_bound(weights,errs[ids])
    coarse['new_reason']='daily_oisst_four_corner_geometry_waiver'
    left=coarse.i.to_numpy()*.25+.125;left=np.where(left>=180,left-360,left)
    bottom=coarse.j.to_numpy()*.25-89.875
    points=np.stack([left[:,None]+[0.,.25,0.,.25],bottom[:,None]+[0.,0.,.25,.25]],axis=2)
    xy=np.column_stack([coarse.lon,coarse.lat]);on_land=np.zeros((len(coarse),4),bool);cross=np.zeros_like(on_land)
    for land in lands:
        shapely.prepare(land)
        on_land |= shapely.intersects(land,shapely.points(points.reshape(-1,2))).reshape(-1,4)
        segments=np.stack([np.repeat(xy,4,axis=0),points.reshape(-1,2)],axis=1)
        cross |= shapely.intersects(land,shapely.linestrings(segments)).reshape(-1,4)
    coarse['geometry_diagnostic']=np.where(on_land.any(axis=1),'source_centre_mask_conflict',
        np.where(cross.any(axis=1),'target_to_source_crosses_land','rectangle_only_land_intersection'))
    coarse['geometry_waiver_authorized']=True
    for k in range(4):
        coarse[f'weight{k}']=weights[:,k];coarse[f'corner{k}_C']=values[:,k]
    coarse.to_parquet(dest/'coarse_795_decisions.parquet',index=False)
    fine_results=[]
    for row in cases.itertuples(index=False):
        record={k:getattr(row,k) for k in KEYS+['pool','in_R','case_kind','season','day','time','lat','lon','reference_K']}
        record.update({'new_method':3,'sst_use_K':np.nan,'decision':'source_unavailable',
                       'source_object':None,'geometry_risk':False,'weights':[],'source_points':[],'source_C':[]})
        if int(row.day) in source_grids:
            (gx,gy,gt),object_name=source_grids[int(row.day)]
            sampled=grid_temperature(row.lon%360,row.lat,gx,gy,gt)
            method=sampled['method'];value=sampled['temperature_C'];w=sampled['weights']
            pts=sampled['source_points'].copy();pts[:,0]=(pts[:,0]+180)%360-180
            valid=np.isfinite(sampled['corners_C'])
            geometry_risk=False
            if method in [9,10]:
                support=pts[valid].reshape(1,3,2)
                geometry_risk=not water_support_hull_ok([[row.lon,row.lat]],support,lands)[0]
                if geometry_risk:method=3;value=np.nan
            elif method in [7,8]:
                hull=shapely.convex_hull(shapely.multipoints(np.vstack([pts[valid],[row.lon,row.lat]])))
                geometry_risk=any(bool(shapely.intersects(land,hull)) for land in lands)
            record.update({'new_method':method,'sst_use_K':value+273.15 if method!=3 else np.nan,
                'decision':sampled['reason'] if method!=3 else ('fine_land_barrier' if geometry_risk else sampled['reason']),
                'source_object':object_name,'geometry_risk':geometry_risk,'weights':w.tolist(),
                'source_points':pts.tolist(),'source_C':sampled['corners_C'].tolist()})
        fine_results.append(record)
    result=pd.DataFrame(fine_results)
    result.to_parquet(dest/'fine_grid_decisions.parquet',index=False)
    actual=result[result.case_kind.eq('target')].copy()
    accepted=actual[actual.new_method.ne(3)].copy()
    coarse['source_family']='OISST_v2.1';accepted['source_family']='CoralTemp_archive_v1.0'
    accepted['sst_source_sd_bound_K']=np.nan
    accepted['new_reason']='coraltemp_night_'+accepted.decision
    patches=pd.concat([coarse,accepted],ignore_index=True)
    output_manifest=[];changes=[]
    for (pool,sid),g in patches.groupby(['pool','id']):
        old,parent_path=temperature_sidecar(int(sid),run=PARENT)
        patch=g[KEYS+['sst_use_K','sst_source_sd_bound_K']].copy()
        patch['sst_method']=g.new_method.to_numpy(np.int8);patch['sst_reason']=g.new_reason.to_numpy()
        patch['sst_total_se_K']=np.nan;patch['availability_scope']='retrospective_only'
        patch['sst_error_kind']=np.where(patch.sst_method.eq(6),'daily_oisst_source_sd_upper_bound','fine_source_uncertainty_unavailable')
        patch['linear_anchor_left_source_obs']=-1;patch['linear_anchor_right_source_obs']=-1
        new=patch_temperature(old,patch)
        changed_mask=old.source_obs.isin(g.source_obs)
        pd.testing.assert_frame_equal(old.loc[~changed_mask],new.loc[~changed_mask],check_exact=True)
        pd.testing.assert_frame_equal(old[KEYS],new[KEYS],check_exact=True)
        file=dest/pool/f'{int(sid)}.parquet';file.parent.mkdir(exist_ok=True);new.to_parquet(file,index=False)
        pd.testing.assert_frame_equal(new,pd.read_parquet(file),check_exact=True)
        output_manifest.append({'id':int(sid),'pool':pool,'path':f'{pool}/{int(sid)}.parquet',
            'rows':len(new),'changed_rows':len(g),'sha256':file_sha256(file),
            'parent_path':str(parent_path.relative_to(root)),'parent_sha256':file_sha256(parent_path)})
        changes.append(g[KEYS+['pool','in_R','new_method','sst_use_K','new_reason','source_family']])
    changed=pd.concat(changes,ignore_index=True)
    changed.to_parquet(dest/'changed_keys.parquet',index=False)
    write_json(dest/'output_manifest.json',output_manifest)
    write_json(dest/'source_receipts.json',source_receipts);write_json(dest/'source_failures.json',failures)
    # Independent value checks for every new row from the retained source objects.
    independent=0
    for row in coarse.itertuples(index=False):
        w=np.array([(1-row.u)*(1-row.v),row.u*(1-row.v),(1-row.u)*row.v,row.u*row.v])
        temperature=np.array([getattr(row,f'corner{k}_C') for k in range(4)])
        assert np.isclose(w@temperature+273.15,row.sst_use_K,atol=1e-10,rtol=0)
        independent+=1
    for row in accepted.itertuples(index=False):
        w=np.asarray(row.weights,float);temp=np.asarray(row.source_C,float)
        assert np.isclose(w.sum(),1.,atol=1e-12) and (w>=0).all()
        assert np.isclose(w@np.where(np.isfinite(temp),temp,0)+273.15,row.sst_use_K,atol=1e-10,rtol=0)
        independent+=1
    diagnostic=result[result.case_kind.eq('validation')].merge(
        v[KEYS+['oisst_K']] if 'oisst_K' in v else
        pd.read_parquet(b/'matched_temperature.parquet').query("kind == 'mask'")[KEYS+['oisst_K']],
        on=KEYS,validate='one_to_one')
    shared=diagnostic.sst_use_K.notna() & diagnostic.oisst_K.notna()
    scores=[]
    for field in ['sst_use_K','oisst_K']:
        d=diagnostic[shared];err=d[field]-d.reference_K
        scores.append({'method':field,'n':len(d),'IDs':int(d.id.nunique()),
            'MAE_K':float(abs(err).mean()) if len(d) else None,
            'RMSE_K':float(np.sqrt((err**2).mean())) if len(d) else None,
            'bias_K':float(err.mean()) if len(d) else None})
    write_json(dest/'development_metrics.json',scores)
    # Preserve all source fields; a trajectory-level grounding cause is not an hourly state.
    grounding=[]
    for sid in sorted(set(target.id.astype(int))|{43869,98975}):
        pool=records[str(sid)]['pool']
        f=pq.read_table(track_path(sid,allow_test=True),columns=['id','typedeath','end_date','time','end_lat','end_lon']).to_pandas()
        grounding.append({'id':sid,'pool':pool,'typedeath':int(f.typedeath.iloc[0]),
            'last_good_metadata_UTC':pd.to_datetime(f.end_date.iloc[0],unit='s',utc=True).isoformat(),
            'last_hourly_UTC':pd.to_datetime(f.time.iloc[-1],unit='s',utc=True).isoformat(),
            'meaning':'eventual termination category; not an hourly grounding timestamp; no rows deleted'})
    write_json(dest/'termination_context.json',grounding)
    write_json(dest/'config.json',config)
    print('Verifying all preserved inputs after completion',flush=True)
    verify_frozen(root,dependencies)
    for name,digest in json.loads((p/'artifact_manifest.json').read_text()).items():assert file_sha256(p/name)==digest
    with cf.ThreadPoolExecutor(max_workers=4) as ex:assert sum(ex.map(verify_native,records.items()))==39107061
    for receipt in source_receipts:assert file_sha256(dest/receipt['path'])==receipt['sha256']
    checks={'status':'passed','canonical_3741_files_130_fields_39107061_rows_preserved':True,
        'parent_runs_unchanged':True,'unmodified_sidecar_rows_exact':True,
        'train_test_assignments_unchanged':True,'coarse_added':795,'fine_added':len(accepted),
        'new_temperatures':len(changed),'independent_formula_checks':independent,
        'remaining_unknown':36860-len(changed),'remaining_unknown_in_R':891-len(changed),
        'fine_unresolved':81-len(accepted),'config_sha256':file_sha256(dest/'config.json')}
    write_json(dest/'verification.json',checks)
    detail=changed.groupby(['source_family','new_method']).size().reset_index(name='hours')
    detail.to_csv(dest/'coverage.csv',index=False)
    table=['| Method | Added pilot hours |','|---|---:|']
    for r in detail.itertuples(index=False):table.append(f'| {r.source_family}, code {r.new_method} | {r.hours} |')
    diagnostics=['| Source | Common development cases | IDs | MAE K | RMSE K | Bias K |','|---|---:|---:|---:|---:|---:|']
    for s in scores:
        if s['n']:diagnostics.append(f"| {s['method']} | {s['n']} | {s['IDs']} | {s['MAE_K']:.4f} | {s['RMSE_K']:.4f} | {s['bias_K']:.4f} |")
    report=f'''# Pilot SST completion (corrected replay)

This run supersedes `sst_pilot_completion_20261017_v1` for reading. The earlier
fine-source stage hit a local read-only-array error; its 23 errors were not
evidence of missing official data. V1 and all earlier sources remain unchanged.
The decoder now owns its validity-mask array and fails loudly on unexpected
metadata or programming errors. All scientific interpolation rules are unchanged.

The user authorized four-corner OISST estimates for exactly 795 pilot-R
unknowns and a fine-source investigation for the remaining 81 coastal rows.
Data Contract v1.0, canonical fields and all prior temperature runs are preserved.

## Added temperatures

{chr(10).join(table)}

Total added: **{len(changed)}**. Remaining unknowns: **{36860-len(changed):,}**
across retained trajectories, **{891-len(changed)}** in R. Fine-grid unresolved
coastal rows: **{81-len(accepted)}**. The 13 pilot high-temperature quarantines
and two position-mapping cases have not been changed. Current additions are all
development IDs; final-test assignments and temperature values are unchanged.

The 795 OISST estimates use the existing four weights and four finite source
temperatures. The previous geometric refusal is explicitly waived for these
keys, as authorized, rather than relabelled as proof of geometry validity.
`coarse_795_decisions.parquet` retains source-centre mask conflicts, cross-land
segments and rectangle-only intersections. No native position or temperature
QC flag was rewritten.

## Finer official source

The delivered source is the **NOAA OceanWatch CoralTemp v1.0 archive**, dataset
`CRW_sst_v1_0`, variable `analysed_sst`, 0.05-degree daily nighttime background
SST. The endpoint declares coverage 1985-01-01 through 2021-03-08, which includes
the requested dates. It is not silently relabelled as a verified current v3.1
asset. Same UTC-date matching uses the actual noon reference coordinate of a
daily analysis, not an instantaneous noon observation. Actual response axes,
units, bounds, fill handling and all returned times were checked.

Raw metadata and small-window JSON responses, exact query URLs, UTC retrieval
times and checksums are in `sources/` and `source_receipts.json`. Source failures
remain explicit in `source_failures.json`. No global temperature archive was
downloaded. Three-corner fine-grid values retain the previous no-cross-land
support gate; four finite source corners retain geometry-risk annotations.
No maximum-corner fill, large-neighbour search or temporal extrapolation occurs.

## Development diagnostic and limitations

{chr(10).join(diagnostics)}

Sixteen known-temperature references were chosen deterministically from the
existing development masking cohort, four per season, before querying fine SST.
Only common qualified comparisons are scored. This small diagnostic is not an
independent coastal accuracy validation: source observations can overlap, the
fine product represents nighttime background, and the missing cases need not
follow the reference distribution. No correction or threshold was fitted from
the scores, and no final-test temperatures were used for selection or scoring.
Additional coverage does not establish better destination forecasts.

## Uncertainty, preservation and reading

Code 6 is the authorized coastal four-corner OISST estimate. Codes 7/8/9/10
denote fine exact-point/bilinear/triangle/outside-normalized routes. OISST retains
a source-only propagated SD bound. Fine-source uncertainty is unavailable from
this source and remains unknown; total reconstruction SE remains unknown.
GDP `sst`, `sst1`, `sst2`, error fields and flags are untouched.

All 3,741 ID files, all 130 original fields and all 39,107,061 rows retain their
hashes. Updated temperature sidecars contain every row for their affected IDs;
other IDs inherit the verified parent view without creating duplicated data.

```python
from data3001.sst_completion import read_sst_track
frame = read_sst_track(9825497, run='sst_pilot_completion_20261017_v2')
# Native sst is retained; reconstructed working temperature is sst_use_K.
```

`verification.json` and `changed_keys.parquet` reconcile the added values;
`output_manifest.json` pins per-ID outputs and parents. No source rows, labels
or features were deleted, and no Git commit or push was performed.

## Grounding policy: discussion only

`typedeath = 1` describes an ID's eventual termination, not its state at every
hour. `end_date` is a last-good metadata date and is not a verified grounding
hour. `termination_context.json` shows why a midnight cutoff would be unsafe.
Retain valid pre-grounding drift and the termination evidence. Confirmed
post-grounding rows should not be ordinary free-drift training samples, while
grounding itself can inform an explicitly defined coastal-outcome extension.
No new beaching state or training exclusion has been implemented here; the
contract distinguishes coastal occupancy, confirmed grounding and disappearance.
'''
    (dest/'REPORT.md').write_text(report)
    write_json(dest/'artifact_manifest.json',{str(x.relative_to(dest)):file_sha256(x)
               for x in dest.rglob('*') if x.is_file()})
    print(json.dumps(checks,indent=2),flush=True)
    print('Report:',dest/'REPORT.md',flush=True)


if __name__=='__main__':execute()
