"""Training-only empirical screening and bounded independent peer diagnosis.

Nothing in this module deletes a position, fills a gap or changes a target label.
"""
from data3001.paths import legacy_path, asset_path, project_paths, ensure_output_path, frozen_action
import json,time
import numpy as np
import pandas as pd
import duckdb
import pyarrow as pa
import shapely as sh
from shapely.geometry import Polygon,Point
from data3001.preprocessing.prep_io import BASE, OUT, Source, save_json, parquet, sha, now
from data3001.preprocessing.prep_geometry import mask
from data3001.preprocessing.prep_core import GEOD

def reader(paths):return 'read_parquet(['+','.join("'"+str(p)+"'" for p in paths)+'],filename=true)'
def screen_score(official,interval,qofficial,qinterval):
    # A missing cross-check must not suppress a finite official-speed flag.
    return np.fmax(official/qofficial,interval/qinterval)
def meta(s):
    keys=['id','expno','location_type','typebuoy','DrogueCenterDepth','typedeath','drogue_lost_date']
    d={k:s.g[k][:] for k in keys};d['split']=[s.cohort.loc[int(id),'split'] for id in s.ids]
    d['typebuoy']=[x.decode('utf-8').strip() for x in d['typebuoy']]
    return pd.DataFrame(d)

@frozen_action
def diagnose():
    start=time.monotonic();s=Source();m=meta(s);con=duckdb.connect();con.execute("SET memory_limit='1000MB'");con.execute('SET threads=2')
    spill=legacy_path('preparation', 'audit/peer_spill');spill.mkdir(exist_ok=True);con.execute(f"SET temp_directory='{spill}'")
    paths=[legacy_path('preparation', 'cleaned', f'{id}.parquet') for id in s.ids if s.cohort.loc[int(id),'split']=='train']
    sql=reader(paths);idexpr="CAST(regexp_extract(filename,'/([0-9]+)\\.parquet$',1) AS BIGINT)"
    con.execute(f'CREATE VIEW training AS SELECT {idexpr} id,* EXCLUDE(filename) FROM {sql}')
    q=con.execute('SELECT quantile_cont(sqrt(ve*ve+vn*vn),0.9999),quantile_cont(sqrt(interval_net_ve*interval_net_ve+interval_net_vn*interval_net_vn),0.9999),count(*) FROM training WHERE velocity_ok AND position_ok').fetchone()
    thresholds={'official_speed_m_s':q[0],'interval_net_speed_m_s':q[1],'quantile':.9999,'training_rows':q[2],
                'authority':'engineering development-only review prioritization; no physical deletion ceiling',
                'reference_split':'train only','references_exclude_target_ID':'peer statistics explicitly exclude target ID',
                'action':'retain every source observation and all primary eligibility; annotate review evidence',
                'windows_km_hours':[[25,3],[50,6],[100,12]]}
    save_json(legacy_path('preparation', 'config/diagnostic_screening.json'),thresholds)
    pathsdev=[legacy_path('preparation', 'cleaned', f'{id}.parquet') for id in s.ids if s.cohort.loc[int(id),'split']!='test']
    sql=reader(pathsdev)
    flags=con.execute(f"SELECT {idexpr} id,source_obs,time,lon_normalized lon,lat,ve,vn,interval_net_ve,interval_net_vn,regime,gap,err_lon,err_lat,mapping_ok,velocity_ok,sqrt(ve*ve+vn*vn) official_speed,sqrt(interval_net_ve*interval_net_ve+interval_net_vn*interval_net_vn) interval_speed FROM {sql} WHERE position_ok AND (sqrt(ve*ve+vn*vn)>{q[0]} OR sqrt(interval_net_ve*interval_net_ve+interval_net_vn*interval_net_vn)>{q[1]})").df()
    flags=flags.sort_values(['id','time','source_obs']).reset_index(drop=True)
    new=(flags.id!=flags.id.shift())|(flags.time-flags.time.shift()!=3600)
    flags['event']=new.cumsum().astype(int);flags['review_score']=screen_score(flags.official_speed,flags.interval_speed,q[0],q[1])
    flags['disposition']='retain_flagged';parquet(flags,legacy_path('preparation', 'audit/speed_review_flags.parquet'))
    ix=flags.groupby('event').review_score.idxmax();events=flags.loc[ix].merge(m,on='id').reset_index(drop=True)
    # Arrow boundary avoids DuckDB 1.4's unsupported pandas 3 StringDtype.
    # Retrieve by 1-degree cells and UTC day buckets before geodesic/time tests.
    # Equal-key retrieval avoids a trajectory-by-event Cartesian range join.
    keys=[]
    for _,e in events.iterrows():
        if e.regime<0 or not e.mapping_ok or not np.isfinite(e.DrogueCenterDepth):continue
        dx=1.1/max(abs(np.cos(np.deg2rad(e.lat))),.01)
        iy0=max(0,int(np.floor(e.lat-1.1+90)));iy1=min(179,int(np.floor(e.lat+1.1+90)))
        ix0=int(np.floor(e.lon-dx+180));ix1=int(np.floor(e.lon+dx+180))
        for day in range(int((e.time-43200)//86400),int((e.time+43200)//86400)+1):
            for iy in range(iy0,iy1+1):
                for ix in range(ix0,ix1+1):
                    keys.append((int(e.event),int(e.id),float(e.time),float(e.lon),float(e.lat),int(e.regime),float(e.DrogueCenterDepth),e.typebuoy,iy*360+ix%360,day))
    keydf=pd.DataFrame(keys,columns=['event','id','time','lon','lat','regime','depth','hardware','cell','day'])
    con.register('event_keys',pa.Table.from_pandas(keydf,preserve_index=False))
    cand=con.execute("SELECT e.event,e.time target_time,e.lon target_lon,e.lat target_lat,e.regime target_regime,e.depth target_depth,e.hardware target_type,r.id reference_id,r.source_obs,r.time,r.lon_normalized lon,r.lat,r.ve,r.vn,r.regime,r.gap,r.err_lon,r.err_lat FROM training r JOIN event_keys e ON r.cell_1=e.cell AND r.departure_day_UTC=e.day WHERE r.id!=e.id AND r.time>=e.time-43200 AND r.time<=e.time+43200 AND r.velocity_ok AND r.position_ok AND r.mapping_ok").df()
    print('cell-retrieved candidates',len(cand),'events',len(events),flush=True)
    if len(cand):
        _,_,dist=GEOD.inv(cand.target_lon.to_numpy(),cand.target_lat.to_numpy(),cand.lon.to_numpy(),cand.lat.to_numpy())
        cand['distance_km']=dist/1000;cand['dt_seconds']=cand.time-cand.target_time
        mm=m.rename(columns={'id':'reference_id'});cand=cand.merge(mm[['reference_id','DrogueCenterDepth','typebuoy','location_type','split']],on='reference_id')
        assert (cand.split=='train').all()
        cand=cand[(cand.distance_km<=100)&(cand.regime==cand.target_regime)&(cand.target_regime>=0)&
                  np.isfinite(cand.DrogueCenterDepth)&np.isfinite(cand.target_depth)&(abs(cand.DrogueCenterDepth-cand.target_depth)<.001)&(cand.typebuoy==cand.target_type)]
    land=mask('h');results=[];selected=[];trackcache={}
    for ei,e in events.iterrows():
        peers=cand[cand.event==e.event].copy() if len(cand) else pd.DataFrame()
        if len(peers) and e.mapping_ok:
            az=np.arange(0,360,5);lo,la,_=GEOD.fwd(np.repeat(e.lon,len(az)),np.repeat(e.lat,len(az)),az,np.repeat(100000,len(az)))
            bounded=Polygon(zip(lo,la));wet=bounded.difference(land.intersection(bounded.envelope))
            comps=list(wet.geoms) if wet.geom_type=='MultiPolygon' else [wet]
            containing=[x for x in comps if x.covers(Point(e.lon,e.lat))]
            if containing:
                comp=sh.union_all(containing);peers=peers[sh.intersects_xy(comp,peers.lon.to_numpy(),peers.lat.to_numpy())]
            else:peers=peers.iloc[:0]
        elif not e.mapping_ok:peers=peers.iloc[:0]
        chosen=pd.DataFrame();stage=0
        for k,(radius,hours) in enumerate([(25,3),(50,6),(100,12)],1):
            if len(peers):
                z=peers[(peers.distance_km<=radius)&(abs(peers.dt_seconds)<=hours*3600)].copy()
                if len(z):
                    z['abs_dt']=abs(z.dt_seconds);chosen=z.sort_values(['abs_dt','distance_km','time','source_obs'],kind='stable').drop_duplicates('reference_id');stage=k;break
        id=int(e.id)
        if id not in trackcache:trackcache[id]=pd.read_parquet(legacy_path('preparation', 'cleaned', f'{id}.parquet'),columns=['source_obs','time','lon','lat','ve','vn','interval_net_ve','interval_net_vn','net_displacement_km','gap','err_lon','err_lat'])
        tr=trackcache[id];j=int(np.flatnonzero(tr.source_obs.to_numpy()==e.source_obs)[0]);context=tr.iloc[max(0,j-1):min(len(tr),j+2)].to_dict('records')
        result={'event':int(e.event),'id':id,'target_source_obs':int(e.source_obs),'target_epoch':float(e.time),'source_official_speed':float(e.official_speed),'interval_net_speed':float(e.interval_speed),
                'reference_stage':stage,'reference_IDs':len(chosen),'status':'peer_available' if len(chosen) else 'peer_unavailable',
                'disposition':'retain_flagged','target_regime':int(e.regime),'target_location_type':int(e.location_type),'depth_m':float(e.DrogueCenterDepth),'typebuoy':e.typebuoy,
                'within_track_previous_current_next':context,'retrospective':True,'missing_peer_state':'no observed peers does not verify target state'}
        if 0<j<len(tr)-1:
            current=tr.iloc[j];following=tr.iloc[j+1]
            u0,v0=current.interval_net_ve,current.interval_net_vn;u1,v1=following.interval_net_ve,following.interval_net_vn
            den=np.hypot(u0,v0)*np.hypot(u1,v1)
            result['arrival_departure_vector_cosine']=float((u0*u1+v0*v1)/den) if np.isfinite(den) and den>0 else None
            neighbours=np.hypot(tr.iloc[[j-1,j+1]].ve,tr.iloc[[j-1,j+1]].vn).to_numpy()
            base=np.nanmedian(neighbours)
            result['official_speed_relative_to_neighbours']=float(e.official_speed/base) if np.isfinite(base) and base>0 else None
        if len(chosen):
            assert not (chosen.reference_id==id).any() and (chosen.split=='train').all()
            u=chosen.ve.to_numpy();v=chosen.vn.to_numpy();angles=np.arctan2(v,u)
            result.update(mean_reference_ve=float(u.mean()),mean_reference_vn=float(v.mean()),median_reference_speed=float(np.median(np.hypot(u,v))),
                          circular_mean_direction_rad=float(np.arctan2(np.sin(angles).mean(),np.cos(angles).mean())),direction_resultant=float(np.hypot(np.cos(angles).mean(),np.sin(angles).mean())))
            selected.append(chosen)
        results.append(result)
        if ei%100==0:print('peer events',ei+1,len(events),flush=True)
    save_json(legacy_path('preparation', 'audit/speed_event_diagnostics.json'),{'events':results,'flagged_rows':len(flags),'representative_events':len(events),
       'all_flags_link_to_event':True,'window_extension':'stop at first stage containing comparable peers; disagreement never causes further search',
       'comparability':'known same regime; recorded depth within 0.001m and exact hardware type; wet connected within bounded 100km window; available location_type retained for measurement comparison',
       'limits':'local wet connectivity does not guarantee same front/branch; processed source and coordinate-derived vectors not independent measurements; absence/disagreement never deletes',
       'elapsed_seconds':time.monotonic()-start,'test_IDs_in_reference_or_events':0})
    parquet(pd.concat(selected,ignore_index=True) if selected else pd.DataFrame(columns=['event','reference_id','source_obs']),legacy_path('preparation', 'audit/selected_peer_observations.parquet'))
    print('peer diagnostics',len(flags),len(events),len(cand),flush=True)

if __name__=='__main__':diagnose()
