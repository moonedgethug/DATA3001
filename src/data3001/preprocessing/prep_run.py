"""Per-ID source-linked cleaning, prototype and checkpoints."""
from data3001.paths import legacy_path, asset_path, project_paths, ensure_output_path, frozen_action
import argparse,json,time,resource
import numpy as np
import pandas as pd
import shapely as sh
from data3001.preprocessing import prep_core as c
from data3001.preprocessing.prep_io import BASE, OUT, Source, sha, save_json, parquet, now, code_hash
from data3001.preprocessing.prep_geometry import mask, region_R, water_ok

def clean_track(raw,meta,land,coarse):
    # Raw values remain columns; source references remain even for excluded rows.
    d=pd.DataFrame(raw);n=len(d);d['original_within_traj_obs']=np.arange(n,dtype=np.int32)
    d['source_obs']=int(meta['source_obs_start_global'])+np.arange(n,dtype=np.int64)
    dup,groups=c.duplicates(raw);d['duplicate_status']=dup
    d['time_ok']=np.isfinite(d.time)&(d.time>=-62135596800)&(d.time<=253402300799)
    d['analytical_row']=(dup==0)&d.time_ok
    d=d.sort_values('time',kind='stable',na_position='last').reset_index(drop=True)
    lon,ok=c.coordinates(d.lon.to_numpy(),d.lat.to_numpy());d['lon_normalized']=lon
    d['position_ok']=ok&d.analytical_row.to_numpy()
    d['velocity_ok']=c.velocity_ok(d.ve.to_numpy(),d.vn.to_numpy())
    for k in ('sst','sst1','sst2'):
        d[k+'_ok']=c.sst_ok(d[k].to_numpy(),d['flg_'+k].to_numpy(),anomaly=k=='sst2')
        d[k+'_celsius' if k!='sst2' else k+'_anomaly_K']=d[k].astype(float)-(273.15 if k!='sst2' else 0)
    for k in ('err_lon','err_lat','err_ve','err_vn','err_sst','err_sst1','err_sst2'):
        d[k+'_ok']=c.uncertainty_ok(d[k].to_numpy())
        d[k+'_negative_unresolved']=np.isfinite(d[k])&(d[k]<0)
    d['regime']=c.regimes(d.time.to_numpy(),d.drogue_status.to_numpy(),meta['drogue_lost_date'])
    d['in_R']=sh.intersects_xy(region_R(),lon,d.lat.to_numpy())&d.position_ok
    wet=water_ok(land,lon,d.lat.to_numpy());wet_i=water_ok(coarse,lon,d.lat.to_numpy())
    d['wet_high']=wet;d['coast_resolution_disagreement']=wet!=wet_i
    d['mapping_ok']=wet&~d.coast_resolution_disagreement&d.position_ok
    d['geometry_uncertain']=d.position_ok&~d.mapping_ok
    # Cell computation is position-derived; geometry admissibility remains separate.
    for res,name in [(1,'cell_1'),(.5,'cell_05')]:
        cell=c.cells(lon,d.lat.to_numpy(),res);cell[~d.position_ok]=-1
        d[name]=cell;d['visit_'+name]=c.visits(d.time.to_numpy(),cell)
    km,u,v=c.displacement(d.time.to_numpy(),lon,d.lat.to_numpy())
    d['net_displacement_km']=km;d['interval_net_ve']=u;d['interval_net_vn']=v
    d['elapsed_seconds_from_previous']=d.time.diff()
    dt=d.elapsed_seconds_from_previous.to_numpy();missing=np.full(n,-1,np.int32)
    good=np.isfinite(dt)&(dt>0)&(dt%3600==0);missing[good]=(dt[good]/3600-1).astype(np.int32)
    d['absent_hours_before']=missing
    utc=pd.to_datetime(d.time,unit='s',utc=True,errors='coerce');d['time_UTC']=utc
    m=utc.dt.month.to_numpy();d['season']=np.select([np.isin(m,[12,1,2]),np.isin(m,[3,4,5]),np.isin(m,[6,7,8]),np.isin(m,[9,10,11])],[0,1,2,3],default=-1).astype(np.int8)
    d['departure_day_UTC']=(d.time//86400).astype('Int64');d['departure_year']=utc.dt.year.astype('Int16')
    return d,groups

def directory(split, *, allow_test=False):return legacy_path('preparation', 'restricted_test/cleaned', allow_test=allow_test) if split=='test' else legacy_path('preparation', 'cleaned')

@frozen_action
def clean(split,ids=None):
    s=Source();land=mask('h');coarse=mask('i');start=time.monotonic();rows=[]
    sig={'clean_code':sha(legacy_path('scripts/prep_run.py')),'core_code':sha(legacy_path('scripts/prep_core.py')),
         'geometry_code':sha(legacy_path('scripts/prep_geometry.py')),'input_snapshot':sha(legacy_path('manifests/source_snapshot.json')),
         'mask_h':sha(legacy_path('preparation', 'geometry/gshhg_h_land.wkb')),'mask_i':sha(legacy_path('preparation', 'geometry/gshhg_i_land.wkb')),
         'policy':'positive documented loss + source agreement; zero/NaN unknown; high/intermediate coast disagreement isolated'}
    sig=json.dumps(sig,sort_keys=True)
    available=[int(v) for v in s.ids if (s.cohort.loc[int(v),'split']=='test')==(split=='test')]
    if ids:available=[x for x in available if x in ids]
    # First full required R tracks, then downstream. Both phases in source order.
    available=sorted(available,key=lambda x:(x not in s.R,s.index[x]))
    for k,id in enumerate(available):
        path=directory(split)/f'{id}.parquet';cp=legacy_path('preparation', 'checkpoints', f'clean_{id}.json')
        if cp.exists() and path.exists():
            z=json.loads(cp.read_text())
            if z['signature']==sig and z['output_sha256']==sha(path):rows.append(z['profile']);continue
        raw,meta=s.track(id);t0=time.monotonic();d,groups=clean_track(raw,meta,land,coarse)
        parquet(d,path)
        profile={'id':id,'split':s.cohort.loc[id,'split'],'R_ID':id in s.R,'rows':len(d),'position_usable':int(d.position_ok.sum()),
                 'R_origins':int(d.in_R.sum()),'missing_SST_usable_position':int((~np.isfinite(d.sst)&d.position_ok).sum()),
                 'SST_rejected_position_retained':int((~d.sst_ok&d.position_ok).sum()),'geometry_uncertain':int(d.geometry_uncertain.sum()),
                 'unknown_regime':int((d.regime<0).sum()),'negative_position_uncertainty':int(((d.err_lon<0)|(d.err_lat<0)).sum()),
                 'timestamp_gap_intervals':int((d.absent_hours_before>0).sum()),'absent_hours':int(d.absent_hours_before.clip(lower=0).sum()),
                 'exact_duplicate_rows':int((d.duplicate_status==1).sum()),'conflict_duplicate_rows':int((d.duplicate_status==2).sum()),
                 'first_epoch':float(d.time.min()),'last_epoch':float(d.time.max()),'elapsed_seconds':time.monotonic()-t0}
        save_json(cp,{'signature':sig,'output_sha256':sha(path),'profile':profile,'utc':now(),'duplicate_groups':groups})
        rows.append(profile)
        if k%100==0:print('clean',split,k+1,len(available),profile,flush=True)
    df=pd.DataFrame(rows);parquet(df,legacy_path('preparation', 'restricted_test/profile.parquet' if split=='test' else 'audit/cleaning_profile.parquet'))
    save_json(legacy_path('preparation', 'restricted_test/clean_run.json' if split=='test' else 'audit/clean_run.json'),{'utc':now(),'IDs':len(rows),
               'rows':int(df.rows.sum()),'elapsed_seconds':time.monotonic()-start,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               'source_min_epoch':float(df.first_epoch.min()),'source_max_epoch':float(df.last_epoch.max()),'signature':sig})

@frozen_action
def prototype():
    s=Source();land=mask('h');coarse=mask('i');cases=[];start=time.monotonic()
    specified={9825497:'1998-08-09T07:00Z',17503:'2000-06-26T00:00Z',55353:'2007-07-03T03:00Z',23120:'2002-03-10T15:00Z'}
    for id in [9825497,43869,17503,55353,23120]:
        raw,meta=s.track(id);d,_=clean_track(raw,meta,land,coarse)
        if id==43869:
            j=int(np.nanargmax(d.sst.to_numpy()));assert not d.sst_ok.iloc[j] and d.position_ok.iloc[j]
        else:
            t=pd.Timestamp(specified[id]).timestamp();hits=np.flatnonzero(d.time.to_numpy()==t);assert len(hits)==1;j=int(hits[0])
        v=d.iloc[j];case={'id':id,'source_obs':int(v.source_obs),'UTC':str(v.time_UTC),'position_ok':bool(v.position_ok),'sst_K':float(v.sst),
            'sst_ok':bool(v.sst_ok),'sst2_anomaly_K':float(v.sst2),'sst2_ok':bool(v.sst2_ok),
            'err_lon':float(v.err_lon),'err_lat':float(v.err_lat),'err_lon_ok':bool(v.err_lon_ok),'err_lat_ok':bool(v.err_lat_ok),
            'elapsed_seconds_from_previous':float(v.elapsed_seconds_from_previous),'absent_hours_before':int(v.absent_hours_before),
            'net_displacement_km':float(v.net_displacement_km),'net_speed_m_s':float(np.hypot(v.interval_net_ve,v.interval_net_vn)),
            'source_gap_seconds':float(v.gap),'split':s.cohort.loc[id,'split']}
        if id==9825497:assert np.isnan(v.sst) and v.position_ok
        if id==17503:
            assert v.sst2<0 and v.sst2_anomaly_K==v.sst2 and v.position_ok
            assert bool(v.sst2_ok)==(v.flg_sst2==5)
            case['diurnal_quality_flag']=int(v.flg_sst2)
            case['interpretation']='negative anomaly retained; extension usability follows flag 5, not its sign'
        if id==55353:assert (v.err_lon<0 or v.err_lat<0) and v.position_ok
        if id==23120:
            assert v.elapsed_seconds_from_previous==54000 and v.absent_hours_before==14
            assert abs(v.net_displacement_km-20.607)<.03 and abs(case['net_speed_m_s']-.382)<.002
        cases.append(case)
    save_json(legacy_path('preparation', 'audit/source_case_regressions.json'),{'all_passed':True,'cases':cases,'elapsed_seconds':time.monotonic()-start,
               'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'validation_case_use':'fixed source/geodesic regression only, no learned QC thresholds'})
    print(json.dumps(cases,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prototype','clean']);p.add_argument('--split',default='development',choices=['development','test']);p.add_argument('--ids',nargs='*',type=int)
    a=p.parse_args()
    if a.action=='prototype':prototype()
    else:clean(a.split,a.ids)
