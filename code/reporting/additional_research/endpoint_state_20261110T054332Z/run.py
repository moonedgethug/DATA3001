import json,time
import numpy as np
import pandas as pd
import shapely as sh
from common import *
from coast import CoastIndex

def main():
    s=Session();passed=False
    try:
        a=pd.read_parquet(s.read(PRIOR/'results/origin_availability.parquet'))
        assert not a.duplicated(KEY).any() and len(a)==313029
        assert a.groupby('cohort').used_by_original.sum().to_dict()=={'train':265393,'validation':33971}
        assert a.groupby('cohort').risk_set.sum().to_dict()=={'train':278001,'validation':34925}
        assets=json.loads(s.read(ROOT/'configs/assets.json').read_text())['assets'];r=assets['land_mask_high']
        land=sh.from_wkb(s.read(ROOT/r['path'],r['sha256']).read_bytes());sh.prepare(land)
        available=a[a.endpoint_available]
        points=available[['endpoint_lon_observed','endpoint_lat_observed']].drop_duplicates().to_numpy()
        geo=CoastIndex(land,points)
        start=time.monotonic();distances,refinements=geo.distances(points,s.check)
        coast=pd.DataFrame({'endpoint_lon_observed':points[:,0],'endpoint_lat_observed':points[:,1],
            'endpoint_distance_lower_m':distances['distance_lower_m'],'endpoint_distance_upper_m':distances['distance_upper_m'],
            'endpoint_on_land':distances['land_or_boundary']})
        coast.to_parquet(OUT/'results/endpoint_coast.parquet',index=False)
        write_json(OUT/'logs/geometry.json',{'positions':len(points),'shore_nodes':geo.node_count,'bounds':geo.bounds,'seconds':time.monotonic()-start,'refined':len(refinements)})
        print('Endpoint geometry complete',len(points),'positions',flush=True)
        del geo
        a=a.merge(coast,on=['endpoint_lon_observed','endpoint_lat_observed'],how='left',validate='many_to_one')
        a['endpoint_on_land']=a.endpoint_on_land.fillna(False).astype(bool)
        a['endpoint_near_5km']=a.endpoint_available&(a.endpoint_distance_upper_m.le(5000)|a.endpoint_on_land)
        dm=json.loads(s.read(ROOT/'configs/dataset_manifest.json').read_text())['records'];qm=json.loads(s.read(ROOT/'configs/qualification_manifest.json').read_text())['records']
        events=s.events.set_index('id');parts=[]
        started=time.monotonic()
        for number,(ident,f) in enumerate(a.groupby('id',sort=True),1):
            sid=str(ident);r=dm[sid];q=qm[sid]
            tr=pd.read_parquet(s.read(ROOT/r['path'],r['sha256']),columns=['id','source_obs','time','lon_normalized','lat'])
            fl=pd.read_parquet(s.read(ROOT/q['path'],q['sha256']))
            assert np.array_equal(tr[['source_obs','time']],fl[['source_obs','time']]) and tr.id.eq(ident).all()
            ev=events.loc[ident];f=f.reset_index(drop=True).copy();f['metadata_conflict']=bool(ev.metadata_conflict)
            m=motion_metrics(tr,fl,f.target_epoch.to_numpy(),float(ev.official_end_epoch),land)
            f=pd.concat([f,m],axis=1)
            f['stay_complete']=False;f['stay_hours']=0;f['stay_max_gap_h']=np.nan;f['stay_radius_km']=np.nan
            ix=np.flatnonzero(f.endpoint_near_5km.to_numpy())
            if len(ix):
                st=stay_metrics(tr,fl,f.target_epoch.to_numpy()[ix],float(ev.official_end_epoch))
                for col in st:f.loc[ix,col]=st[col].to_numpy()
            f['nearshore_stay_candidate']=f.endpoint_near_5km&f.stay_complete&f.stay_radius_km.le(1)
            f['ground_candidate']=f.nearshore_stay_candidate&f.official_typedeath.eq(1)&~f.metadata_conflict
            f['ground_review_passed']=False
            f['state']=classify(f,5);f['state_strict10']=classify(f,10)
            f['unknown_reason']=np.select([~f.endpoint_available,f.metadata_conflict,f.endpoint_on_land,~f.before_complete|~f.after_complete,
                f.motion_land_points.gt(0),f.nearshore_stay_candidate],
                ['endpoint_missing','source_conflict','endpoint_on_mapped_land','insufficient_before_after_observations','motion_window_has_land_positions','nearshore_persistent_stay'],
                default='movement_below_rule_or_turning')
            f.loc[f.state.ne('uncertain'),'unknown_reason']='not_applicable'
            parts.append(f)
            if number==10:
                estimate=(time.monotonic()-started)/10*383
                write_json(OUT/'logs/ten_id_projection.json',{'seconds':time.monotonic()-started,'projected_383_seconds':estimate})
                if estimate>1500:raise RuntimeError('Projected track stage over budget')
            if number%25==0:print('Endpoint track audit',number,'IDs',round(time.monotonic()-started,1),'seconds',flush=True)
            s.check()
        f=pd.concat(parts,ignore_index=True)
        f.to_parquet(OUT/'results/endpoint_states.parquet',index=False)
        f[f.nearshore_stay_candidate].to_csv(OUT/'results/nearshore_stay_candidates.csv',index=False)
        f[f.ground_candidate].to_csv(OUT/'results/grounding_review_candidates.csv',index=False)
        print('Grounding review candidates',int(f.ground_candidate.sum()),'pairs',f[f.ground_candidate].id.nunique(),'IDs',flush=True)
        print('All nearshore stay candidates',int(f.nearshore_stay_candidate.sum()),'pairs',f[f.nearshore_stay_candidate].id.nunique(),'IDs',flush=True)
        passed=True
    finally:s.close('compute',passed)

if __name__=='__main__':main()
