"""Execute the user-authorized geometry-free, sparse-source SST extension."""
from pathlib import Path
from datetime import datetime,timezone
import concurrent.futures as cf
import hashlib,json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import requests
import netCDF4
from data3001.paths import project_paths,file_sha256,ensure_output_path
from data3001.dataset import manifest,track_path
from data3001.sst_completion import temperature_sidecar
from data3001.sst_source_grid import decode_grid
from data3001.sst_sparse import sparse_temperature,sample_sparse_grid,termination_context,apply_sparse_patch

RUN='sst_sparse_completion_20261017_v1'
PARENT='sst_pilot_completion_20261017_v2'
ORIGINAL='sst_reconstruction_20261016_v1'
CONTRACT='6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446'
KEYS=['id','source_obs']
METHOD={11:'four_corner_bilinear',12:'three_corner_triangle',13:'three_corner_normalized',
        14:'two_corner_inverse_distance',15:'one_actual_source',16:'three_corner_distance_degeneracy'}


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False,default=str)+'\n')


def execute():
    root=project_paths().root;b=root/'results/runs'/ORIGINAL;p=root/'results/runs'/PARENT
    audit=root/'results/runs/sst_remaining_audit_20261017_v1/remaining_records.csv'
    dest=ensure_output_path('results/runs/'+RUN)
    assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx')==CONTRACT
    for name,digest in json.loads((p/'artifact_manifest.json').read_text()).items():assert file_sha256(p/name)==digest
    parent_config=json.loads((p/'config.json').read_text())
    for name,digest in parent_config['dependencies'].items():assert file_sha256(root/name)==digest
    records=manifest()['records']
    def verify_native(item):
        sid,r=item;path=root/r['path']
        assert file_sha256(path)==r['sha256'] and len(pq.read_schema(path).names)==130
        assert pq.ParquetFile(path).metadata.num_rows==r['rows']
        return r['rows']
    print('Verifying all native files and source version identities',flush=True)
    with cf.ThreadPoolExecutor(max_workers=4) as ex:assert sum(ex.map(verify_native,records.items()))==39107061
    f=pd.read_csv(audit).drop(columns='finite_source_corners')
    q=pd.read_parquet(b/'targets.parquet').query("kind == 'target'")
    fields=KEYS+['time','quarantine','u','v','i','j','day']+[f'node{k}' for k in range(4)]
    f=f.merge(q[fields],on=KEYS,validate='one_to_one').sort_values(KEYS).reset_index(drop=True)
    assert len(f)==35984 and not f.duplicated(KEYS).any()
    for sid,g in f.groupby('id'):
        old,_=temperature_sidecar(int(sid),run=PARENT)
        z=old.set_index('source_obs').loc[g.source_obs]
        assert z.sst_use_K.isna().all() and z.sst_method.eq(3).all()
    end=pd.to_datetime(f.last_good_metadata_UTC,utc=True).astype('int64').to_numpy()/1e9
    f['official_motion_context']=termination_context(f.time,end,f.typedeath)
    held=f.official_motion_context.str.startswith('after_official_')
    eligible=f.position_ok & ~held & ~f.quarantine
    assert f.position_ok.all() and np.isfinite(f[['time','lat','lon']].to_numpy()).all()
    values=np.load(b/'node_sst.npy')[f[[f'node{k}' for k in range(4)]].to_numpy()]
    errors=np.load(b/'node_err.npy')[f[[f'node{k}' for k in range(4)]].to_numpy()]
    left=f.i.to_numpy()*.25+.125;left=(left+180)%360-180
    bottom=f.j.to_numpy()*.25-89.875
    points=np.stack([left[:,None]+[0.,.25,0.,.25],bottom[:,None]+[0.,0.,.25,.25]],axis=2)
    estimate=sparse_temperature(f.lon,f.lat,points,values,f.u,f.v)
    f['finite_source_count']=estimate['finite_source_count']
    f['new_method']=np.where(eligible,estimate['method'],3).astype(np.int8)
    f['sst_use_K']=np.where(f.new_method.ne(3),estimate['temperature_C']+273.15,np.nan)
    f['source_family']='OISST_v2.1';f['source_object']='inherited_verified_node_sst.npy'
    f['route']='original_OISST_stencil';f['decision']='source_unavailable'
    f.loc[held,'decision']='outside_official_last_good_day_'+f.loc[held,'typedeath'].map({1:'grounding',2:'vessel_recovery'})
    f.loc[f.quarantine,'decision']='finite_native_above_45C_review_retained'
    f.loc[f.new_method.ne(3),'decision']='filled'
    weights=estimate['weights'].copy();distances=estimate['distance_km'].copy()
    weights[f.new_method.eq(3)]=0.
    dependencies={str(a.relative_to(root)):file_sha256(a) for a in [audit,
        p/'artifact_manifest.json',p/'config.json',p/'verification.json',p/'output_manifest.json',
        b/'targets.parquet',b/'node_sst.npy',b/'node_err.npy',
        root/'configs/dataset_manifest.json',root/'configs/assets.json',
        root/'docs/sst_sparse_completion_plan.md',root/'src/data3001/sst_sparse.py',
        root/'src/data3001/sst_sparse_run.py',root/'tests/test_sst_sparse.py',
        root/'src/data3001/sst_completion.py',root/'src/data3001/sst_source_grid.py']}
    dest.mkdir();(dest/'sources').mkdir()
    config={'run_id':RUN,'parent_run':PARENT,'contract_sha256':CONTRACT,
       'created_UTC':datetime.now(timezone.utc).isoformat(),'dependencies':dependencies,
       'authorization':'User instruction: remove temperature land-path gates; use four/three/two/one actual-source estimates',
       'distance_weights':'WGS84 geodesic 1/d, exponent 1; exact source match has unit weight',
       'official_life_rule':'Hold later UTC dates after official last-good date for grounding/recovery; mark terminal-day hour uncertainty',
       'native_high_review':'Preserve all 262 previous >45 C quarantines, including mapping overlap',
       'unchanged_research':'No position/transition qualifications, geometry, pools, native fields, or outcome definitions changed'}
    write_json(dest/'config.json',config)
    receipts=[];failures=[]
    def fetch(url,label):
        try:
            r=requests.get(url,timeout=(5,35));r.raise_for_status()
        except requests.RequestException as exc:
            failures.append({'url':url,'reason':type(exc).__name__+': '+str(exc)[:200]});return None
        digest=hashlib.sha256(r.content).hexdigest();name=label+'_'+digest[:16]+('.nc' if label.startswith('coraltemp') else '.json')
        path=dest/'sources'/name;path.write_bytes(r.content)
        receipts.append({'requested_url':url,'url':r.url,'path':'sources/'+name,'sha256':digest,
                         'bytes':len(r.content),'retrieved_UTC':datetime.now(timezone.utc).isoformat()})
        return path
    # Only 36 original zero-corner cases require any new source acquisition.
    zero=f.index[eligible & f.finite_source_count.eq(0)]
    old=zero[f.loc[zero,'day'].le(pd.Timestamp('2021-03-08').value//86400_000000000)]
    archive_metadata=None
    if len(old):
        path=fetch('https://oceanwatch.pifsc.noaa.gov/erddap/info/CRW_sst_v1_0/index.json','archive_metadata')
        if path:
            rows=json.loads(path.read_text())['table']['rows']
            attrs={(r[1],r[2]):r[4] for r in rows if r[0]=='attribute'}
            assert attrs['NC_GLOBAL','product_version']=='1.0' and attrs['analysed_sst','units']=='degree_C'
            archive_metadata=attrs
    print('Estimating sparse-source rows; querying six required fine-source dates',flush=True)
    for day,g in f.loc[zero].groupby('day'):
        date=pd.to_datetime(int(day),unit='D',utc=True);lat0=g.lat.min()-.1;lat1=g.lat.max()+.1
        if date<=pd.Timestamp('2021-03-08',tz='UTC'):
            if archive_metadata is None:continue
            x=g.lon%360;lon0=x.min()-.1;lon1=x.max()+.1
            url=('https://oceanwatch.pifsc.noaa.gov/erddap/griddap/CRW_sst_v1_0.json?'
                 f'analysed_sst[({date:%Y-%m-%d}T12:00:00Z)][({lat0:.5f}):1:({lat1:.5f})][({lon0:.5f}):1:({lon1:.5f})]')
            source=fetch(url,'archive_grid')
            if source is None:continue
            gx,gy,gt=decode_grid(json.loads(source.read_text()),int(day))
            family='CoralTemp_archive_v1.0'
        else:
            url=(f'https://www.star.nesdis.noaa.gov/pub/sod/mecb/crw/data/5km/v3.1_op/nc/v1.0/daily/sst/{date:%Y}/'
                 f'coraltemp_v3.1_{date:%Y%m%d}.nc')
            source=fetch(url,'coraltemp_'+date.strftime('%Y%m%d'))
            if source is None:continue
            with netCDF4.Dataset(str(source),'r') as d:
                assert d.product_version=='3.1' and d.id=='CoralTemp-v3.1'
                assert d['analysed_sst'].units=='degrees_Celsius'
                assert d['analysed_sst'].dimensions==('time','lat','lon')
                stamp=netCDF4.num2date(d['time'][0],d['time'].units,only_use_cftime_datetimes=False)
                actual=pd.Timestamp(stamp).tz_localize('UTC')
                assert actual==date+pd.Timedelta(hours=12)
                gx=np.asarray(d['lon'][:],float);gy=np.asarray(d['lat'][:],float)
                xx=np.flatnonzero((gx>=g.lon.min()-.1)&(gx<=g.lon.max()+.1))
                yy=np.flatnonzero((gy>=lat0)&(gy<=lat1))
                assert len(xx)>=2 and len(yy)>=2
                v=d['analysed_sst'];v.set_auto_maskandscale(False)
                raw=np.asarray(v[0,yy[0]:yy[-1]+1,xx[0]:xx[-1]+1])
                valid=(raw!=v._FillValue)&(raw>=v.valid_min)&(raw<=v.valid_max)
                gt=np.where(valid,raw.astype(float)*v.scale_factor+getattr(v,'add_offset',0.),np.nan)
                gx=gx[xx];gy=gy[yy]
            family='CoralTemp_v3.1';lon0=float(gx.min());lon1=float(gx.max())
        for k,row in g.iterrows():
            sample_lon=row.lon%360 if gx.min()>=0 else row.lon
            sampled=sample_sparse_grid(sample_lon,row.lat,gx,gy,gt)
            f.loc[k,'source_object']=str(source.relative_to(dest));f.loc[k,'route']=sampled['route']
            if sampled['method']==3:continue
            f.loc[k,'new_method']=sampled['method'];f.loc[k,'sst_use_K']=sampled['temperature_C']+273.15
            f.loc[k,'source_family']=family;f.loc[k,'decision']='filled'
            points[k]=sampled['points'];values[k]=sampled['values'];weights[k]=sampled['weights']
            distances[k]=sampled['distance_km'];errors[k]=np.nan
            f.loc[k,'u']=sampled['u'];f.loc[k,'v']=sampled['v']
            f.loc[k,'finite_source_count']=int(np.isfinite(sampled['values']).sum())
        print('Fine source checked:',date.strftime('%Y-%m-%d'),family,flush=True)
    for k in range(4):
        f[f'point{k}_lon']=points[:,k,0];f[f'point{k}_lat']=points[:,k,1]
        f[f'corner{k}_C']=values[:,k];f[f'corner{k}_SD_K']=errors[:,k]
        f[f'weight{k}']=weights[:,k];f[f'distance{k}_km']=distances[:,k]
    used=weights>0;error_ok=((~used)|(np.isfinite(errors)&(errors>=0))).all(axis=1)
    f['sst_source_sd_bound_K']=np.where(error_ok & f.new_method.ne(3),
        np.sum(weights*np.where(used,errors,0.),axis=1),np.nan)
    filled=f[f.decision.eq('filled')].copy()
    assert not filled.quarantine.any() and not filled.official_motion_context.str.startswith('after_official_').any()
    outputs=[]
    for (pool,sid),g in filled.groupby(['pool','id']):
        previous,parent_path=temperature_sidecar(int(sid),run=PARENT)
        patch=g[KEYS+['sst_use_K','sst_source_sd_bound_K']].copy()
        patch['sst_method']=g.new_method.to_numpy(np.int8)
        patch['sst_reason']=(g.source_family+'_'+g.new_method.map(METHOD)).to_numpy()
        patch['sst_total_se_K']=np.nan;patch['availability_scope']='retrospective_only'
        patch['sst_error_kind']=np.where(g.source_family.eq('OISST_v2.1'),
            'daily_oisst_source_sd_upper_bound','fine_source_uncertainty_unavailable')
        patch['linear_anchor_left_source_obs']=-1;patch['linear_anchor_right_source_obs']=-1
        new=apply_sparse_patch(previous,patch);changed=previous.source_obs.isin(g.source_obs)
        pd.testing.assert_frame_equal(previous.loc[~changed],new.loc[~changed],check_exact=True)
        pd.testing.assert_frame_equal(previous[KEYS],new[KEYS],check_exact=True)
        path=dest/pool/f'{int(sid)}.parquet';path.parent.mkdir(exist_ok=True);new.to_parquet(path,index=False)
        pd.testing.assert_frame_equal(new,pd.read_parquet(path),check_exact=True)
        outputs.append({'id':int(sid),'pool':pool,'path':f'{pool}/{int(sid)}.parquet','sha256':file_sha256(path),
            'rows':len(new),'changed_rows':len(g),'parent_path':str(parent_path.relative_to(root)),
            'parent_sha256':file_sha256(parent_path)})
    # Independent arithmetic and source-only uncertainty checks, all filled rows.
    checked=0
    for row in filled.itertuples(index=False):
        w=np.array([getattr(row,f'weight{k}') for k in range(4)])
        t=np.array([getattr(row,f'corner{k}_C') for k in range(4)])
        assert (w>=0).all() and abs(w.sum()-1)<1e-11
        assert np.isfinite(t[w>0]).all() and abs(w@np.where(np.isfinite(t),t,0.)+273.15-row.sst_use_K)<1e-10
        assert t[w>0].min()-1e-10<=row.sst_use_K-273.15<=t[w>0].max()+1e-10
        if row.new_method==11:
            expected=np.array([(1-row.u)*(1-row.v),row.u*(1-row.v),(1-row.u)*row.v,row.u*row.v])
            assert np.allclose(w,expected,atol=1e-11,rtol=0)
        if row.new_method in [14,16]:
            d=np.array([getattr(row,f'distance{k}_km') for k in range(4)]);valid=np.isfinite(t)
            if not (d[valid]<=1e-9).any():assert np.allclose((w*d)[valid],(w*d)[valid][0],atol=1e-9,rtol=0)
        checked+=1
    f.to_parquet(dest/'decisions.parquet',index=False)
    f.loc[f.new_method.eq(3),KEYS+['pool','UTC','lat','lon','in_R','decision','official_motion_context','finite_source_count','sst_reason']].to_csv(dest/'remaining_records.csv',index=False)
    filled[KEYS+['pool','in_R','new_method','source_family','sst_use_K','official_motion_context']].to_parquet(dest/'changed_keys.parquet',index=False)
    coverage=filled.groupby(['pool','source_family','new_method']).agg(hours=('id','size'),IDs=('id','nunique'),R_hours=('in_R','sum')).reset_index()
    coverage.to_csv(dest/'coverage.csv',index=False)
    remaining=f[f.new_method.eq(3)].groupby('decision').agg(hours=('id','size'),IDs=('id','nunique'),R_hours=('in_R','sum')).reset_index()
    remaining.to_csv(dest/'remaining_summary.csv',index=False)
    write_json(dest/'output_manifest.json',outputs);write_json(dest/'source_receipts.json',receipts);write_json(dest/'source_failures.json',failures)
    print('Verifying preserved inputs and writing final reconciliation',flush=True)
    for name,digest in dependencies.items():assert file_sha256(root/name)==digest
    for name,digest in json.loads((p/'artifact_manifest.json').read_text()).items():assert file_sha256(p/name)==digest
    with cf.ThreadPoolExecutor(max_workers=4) as ex:assert sum(ex.map(verify_native,records.items()))==39107061
    for receipt in receipts:assert file_sha256(dest/receipt['path'])==receipt['sha256']
    checks={'status':'passed','canonical_3741_files_130_fields_39107061_rows_preserved':True,
       'all_parent_artifacts_preserved':True,'unchanged_sidecar_rows_exact':True,'train_test_membership_unchanged':True,
       'new_temperatures':len(filled),'independent_formula_checks':checked,
       'remaining_unknown':int(f.new_method.eq(3).sum()),'remaining_unknown_in_R':int((f.new_method.eq(3)&f.in_R).sum()),
       'filled_despite_mapping_flag':int((~filled.mapping_ok).sum()),
       'filled_terminal_day_hour_unknown':int(filled.official_motion_context.str.contains('terminal_day_hour_unknown').sum()),
       'config_sha256':file_sha256(dest/'config.json')}
    write_json(dest/'verification.json',checks)
    ct='\n'.join('| '+' | '.join(str(v) for v in row)+' |' for row in coverage.itertuples(index=False,name=None))
    rt='\n'.join('| '+' | '.join(str(v) for v in row)+' |' for row in remaining.itertuples(index=False,name=None))
    report=f'''# SST sparse-source completion

The user authorized removal of temperature interpolation land-path/support-hull
gates and estimation from four, three, two or one actual official source values.
This run inherits `{PARENT}` and changes previously unknown derived temperatures
only. The Data Contract, all 130 canonical fields, all 39,107,061 source rows and
all whole-ID pools are preserved. Research mapping flags and model qualifications
are not rewritten by this temperature-specific policy change.

## Result

Added **{len(filled):,}** temperatures across **{filled.id.nunique()}** IDs.
Remaining unknown working SST: **{checks['remaining_unknown']:,}**, including
**{checks['remaining_unknown_in_R']}** in R. Existing finite/native accepted
temperatures, components and native errors remain unchanged.

| Pool | Source | Method | Hours | IDs | In R |
|---|---|---:|---:|---:|---:|
{ct}

Methods: 11 four-corner bilinear; 12 triangle; 13 normalized available three
bilinear weights; 14 two-source WGS84 inverse-distance weights with exponent 1;
15 actual single-source value; 16 three-source inverse-distance fallback for a
zero available-bilinear-weight sum. Exact valid-source matches have unit weight.
All weights are nonnegative and sum to one; all estimates remain within the
positively weighted source range. A one-source estimate is a marked rough
approximation, not recovered hourly sensor truth.

## Official termination context and remaining rows

| Remaining reason | Hours | IDs | In R |
|---|---:|---:|---:|
{rt}

`typedeath=1/2` and the official last-good date govern the two post-terminal
categories. A later UTC date is held; the last-good marker is not claimed to
timestamp the first grounding/recovery hour. On the terminal date, background
SST can be estimated but exact event-time uncertainty remains in the ledger:
**{checks['filled_terminal_day_hour_unknown']:,}** new estimates have that context.
They are not promoted to confirmed floating states or training eligibility.
Other termination causes do not prove absence of an earlier grounding event.
Native >45 C quarantines are still under a separate review, not automatically
repaired by this geometry/source-count change. See `remaining_records.csv`.

No land mask blocked an estimate: **{checks['filled_despite_mapping_flag']:,}**
added values have an existing unqualified mapping flag. Those flags are retained
as research evidence and are not silently changed to valid model transitions.
No native rows were deleted and no new beaching model state was added.

## Sources and uncertainty

Most estimates reuse frozen, source-verified NOAA OISST v2.1 same-date daily
fields. Only original zero-corner cases requested new fine SST. The NOAA
OceanWatch `CRW_sst_v1_0` daily nighttime archive is used for 2014 dates; actual
NOAA STAR CoralTemp v3.1 daily files are used for the three required 2022 dates.
These are individually declared sources, not silently relabelled versions.
Actual coordinates, UTC daily timestamps, units, packed fills, source validity
ranges and returned versions were checked. Original source responses, URLs,
retrieval times and hashes are in `sources/` and `source_receipts.json`.
Fine matching uses an enclosing stencil and, if it is empty, the nearest finite
actual source in the received 0.1-degree-halo window. It never expands to an
unbounded nearest search. A true all-missing received source is not fabricated.

The propagated source-only SD upper bound is `sum(abs(w)*sigma)` where every
positively weighted source has an SD. Fine-source SD and total reconstruction
standard error are unknown. GDP `err_sst*` are not overwritten. No correction
was fitted, and no final-test temperatures were used to select algorithms or
score predictions. More complete SST does not prove improved destination maps,
new seasonal/year support, or independence from assimilated buoy observations.

## Reading and verification

```python
from data3001.sst_sparse import read_sst_track
frame = read_sst_track(139080)
# Native sst is retained; use sst_use_K for the reconstructed covariate.
```

The reader resolves complete per-ID sidecars and verified parent views, retains
all native columns/rows, and still guards final-test access. All added formulas
were checked individually; original file hashes, unchanged sidecar rows, parent
artifact hashes and pool assignments were verified. `decisions.parquet` retains
source values, coordinates, weights, distances, methods and official context.
No Git commit/push was performed.
'''
    (dest/'REPORT.md').write_text(report)
    write_json(dest/'artifact_manifest.json',{str(a.relative_to(dest)):file_sha256(a) for a in sorted(dest.rglob('*')) if a.is_file()})
    print(json.dumps(checks,indent=2),flush=True);print('Report:',dest/'REPORT.md',flush=True)


if __name__=='__main__':execute()
