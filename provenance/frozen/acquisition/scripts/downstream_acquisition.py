"""Retrieve downstream candidate training support from development-only paths.

This chooses a conservative DATA ACQUISITION envelope, not final model D.
All candidate D extents, support and stopped-domain semantics remain auditable.
"""
import argparse
import math
import time
import numpy as np
import pandas as pd
from shapely import box, intersects_xy
from shapely.geometry import mapping
from acquire_hourly import ROOT, Snapshot, metadata, trajectory, freeze_geometry, json_save, discover, retrieve, sha


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=12)
    parser.add_argument('--geometry-only',action='store_true')
    args=parser.parse_args()
    snap=Snapshot();meta,offsets,frame=metadata(snap)
    region=freeze_geometry()
    Rids=pd.read_csv(ROOT/'manifests/R_ids.csv',dtype={'id':str})
    development=Rids[Rids.split!='test']
    out=ROOT/'geometry/acquisition_envelope.geojson'
    started=time.monotonic()
    if not out.exists():
        extrema=np.array([np.inf,np.inf,-np.inf,-np.inf])
        counts=[]
        observed_cells=set()
        for done,row in enumerate(development.itertuples(),1):
            a=trajectory(snap,row,['time','lon','lat'])
            t=a['time'];lon=(a['lon']+180)%360-180;lat=a['lat']
            valid=np.isfinite(t)&np.isfinite(lon)&np.isfinite(lat)&(lat>=-90)&(lat<90)
            origins=np.zeros(len(t),dtype=bool)
            origins[valid]=intersects_xy(region,lon[valid],lat[valid])
            last_origin=np.maximum.accumulate(np.where(origins,t,-np.inf))
            selected=valid&np.isfinite(last_origin)&(t-last_origin<=365*86400)&(t>=last_origin)
            x=lon[selected];y=lat[selected]
            if len(x):
                extrema[:2]=np.minimum(extrema[:2],[x.min(),y.min()])
                extrema[2:]=np.maximum(extrema[2:],[x.max(),y.max()])
                observed_cells.update(zip(np.floor(x).astype(int).tolist(),np.floor(y).astype(int).tolist()))
            counts.append({'id':row.id,'split':row.split,'R_origins':int(origins.sum()),
                'positions_in_union_of_365_day_future_windows':int(selected.sum()),
                'missing_time_or_position':int((~valid).sum()),
                'duplicate_or_nonincreasing_time_steps':int(np.count_nonzero(np.diff(t)<=0))})
            if done%100==0:
                print(f'Development path extent {done}/{len(development)} IDs',flush=True)
        if not np.isfinite(extrema).all():
            raise RuntimeError('No development path extent')
        # Contract leaves domain selection empirical. These are retrieval candidates only.
        rounded=np.array([math.floor(extrema[0]),math.floor(extrema[1]),math.ceil(extrema[2]),math.ceil(extrema[3])],dtype=float)
        candidates=[]
        for padding in [0,2,5]:
            bounds=[max(-180,rounded[0]-padding),max(-90,rounded[1]-padding),min(180,rounded[2]+padding),min(90,rounded[3]+padding)]
            candidates.append({'padding_degrees':padding,'bounds_lon_lat':bounds,'purpose':'nested development acquisition candidate; no claim of optimal model boundary'})
        envelope=box(*candidates[-1]['bounds_lon_lat'])
        json_save(out, {'type':'FeatureCollection','name':'provisional_acquisition_envelope',
            'crs':{'type':'name','properties':{'name':'urn:ogc:def:crs:OGC:1.3:CRS84'}},
            'features':[{'type':'Feature','properties':{'role':'DATA ACQUISITION ONLY; FINAL D NOT FROZEN',
                'basis':'All finite development positions within 365 days after any hourly R origin; whole trajectory still retained',
                'used_splits':['train','validation'],'test_IDs_used':0,'development_IDs':len(development),
                'selected_retrieval_padding_degrees':5,'coordinate_order':'longitude,latitude'},'geometry':mapping(envelope)}]})
        pd.DataFrame(counts).to_csv(ROOT/'audit/development_path_coverage.csv',index=False)
        pd.DataFrame(sorted(observed_cells),columns=['cell_west_longitude','cell_south_latitude']).to_csv(ROOT/'audit/development_observed_path_cells.csv',index=False)
        json_save(ROOT/'audit/acquisition_domain_candidates.json', {'observed_coordinate_extrema_lon_lat':extrema.tolist(),
            'observed_one_degree_cells':len(observed_cells),'candidates':candidates,'acquired_envelope_padding':5,
            'selection_reason':'A conservative outer acquisition envelope enables subsequent nested boundary/support comparisons without consulting test endpoints. Padding is an engineering retrieval allowance, not an estimated transport confidence bound.',
            'fixed_regime_eligibility_used':False,'positions_with_gaps':'Retained for conservative acquisition; does not make first-exit labels valid',
            'test_IDs_used':0,'R_IDs_withheld':int((Rids.split=='test').sum()),'development_IDs':len(development),
            'split_manifest_sha256':sha(ROOT/'manifests/global_id_split.csv'),'elapsed_seconds':round(time.monotonic()-started,2),
            'final_D_frozen':False})
        print('Development extrema',extrema.tolist(),'Acquisition envelope',list(envelope.bounds),flush=True)
    else:
        import json
        from shapely.geometry import shape
        envelope=shape(json.loads(out.read_text())['features'][0]['geometry'])
    if args.geometry_only:
        return
    selected=discover(snap,envelope,offsets,frame,'downstream',args.workers)
    selected['also_visits_R']=selected.id.isin(Rids.id)
    selected.to_csv(ROOT/'manifests/downstream_ids.csv',index=False)
    union=pd.concat([Rids,selected],ignore_index=True).drop_duplicates('id').sort_values('source_traj_index')
    union['also_visits_R']=union.id.isin(Rids.id)
    union.to_csv(ROOT/'manifests/acquired_ids.csv',index=False)
    retrieve(snap,union,frame,'expanded',args.workers)
    print('Expanded full trajectories',len(union),'including downstream-only',int((~union.also_visits_R).sum()),flush=True)


if __name__=='__main__':
    main()
