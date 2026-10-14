"""On-demand integer-day paired targets; compact retrospective event ledger."""
import argparse,json
import numpy as np
import pandas as pd
import shapely as sh
from shapely.geometry import shape
import prep_core as c
from prep_io import BASE,OUT,Source,parquet,save_json,sha,now
from prep_run import directory
CUTOFF=float(json.loads((BASE/'metadata/corpus_time_coverage.json').read_text())['end_epoch_seconds'])

def load_track(s,id):
    split=s.cohort.loc[id,'split'];df=pd.read_parquet(directory(split)/f'{id}.parquet')
    df=df[df.analytical_row].reset_index(drop=True)
    dom=shape(json.loads((OUT/'geometry/transport_D.geojson').read_text())['features'][0]['geometry'])
    inside=sh.intersects_xy(dom,df.lon_normalized.to_numpy(),df.lat.to_numpy())&df.position_ok.to_numpy()
    loss=float(s.g['drogue_lost_date'][s.index[id]])
    a={'time':df.time.to_numpy(),'position_ok':df.position_ok.to_numpy(),'mapping_ok':df.mapping_ok.to_numpy(),
       'inside_D':inside,'regime':df.regime.to_numpy(),'lon':df.lon_normalized.to_numpy(),'lat':df.lat.to_numpy(),'loss':loss}
    return df,a,c.event_bounds(a)

def origin_indices(df,a,population):
    return np.flatnonzero(a['position_ok']&(df.in_R.to_numpy() if population=='R' else a['inside_D']))

def generate(df,a,events,id,origins,days,scenario,tolerance=0):
    if not 1<=days<=365 or int(days)!=days:raise ValueError('Integer days 1–365 required')
    e,p=c.labels(a,origins,days,tolerance,scenario,events,cutoff=CUTOFF)
    origin=df.iloc[origins]
    shared={'id':np.repeat(id,len(origins)),'origin_source_obs':origin.source_obs.to_numpy(),
            'origin_time_UTC':origin.time_UTC.to_numpy(),'target_epoch':a['time'][origins]+days*86400,
            'horizon_days':np.repeat(days,len(origins)),'scenario':np.repeat(scenario,len(origins)),
            'tolerance_hours':np.repeat(tolerance,len(origins)),'origin_cell_1':origin.cell_1.to_numpy(),
            'departure_season':origin.season.to_numpy(),'origin_visit_1':origin.visit_cell_1.to_numpy()}
    out=[]
    for target,x in [('endpoint',e),('stopped',p)]:
        ix=x['endpoint_index'];safe=np.clip(ix,0,len(df)-1)
        d=pd.DataFrame(shared);d['target']=target;d['reason_code']=x['reason'];d['secondary_predicates']=x['secondary'];d['outside']=x['outside']
        d['required_interval_end_epoch']=x['required_interval_end']
        d['endpoint_source_obs']=np.where(ix>=0,df.source_obs.to_numpy()[safe],-1)
        d['destination_cell_1']=np.where(x['reason']==0,np.where(x['outside'],-2,df.cell_1.to_numpy()[safe]),-1)
        d['matched_endpoint_epoch']=np.where(ix>=0,a['time'][safe],np.nan)
        d['time_error_seconds']=x.get('time_error_seconds',np.where(ix>=0,a['time'][safe]-d.target_epoch,np.nan))
        d['realized_duration_seconds']=d.matched_endpoint_epoch-a['time'][origins]
        for key in ['origin_source_position_failure','endpoint_source_position_failure','geometry_failure',
                    'path_source_position_failure','path_geometry_failure','path_timestamp_gap']:
            if key in x:d[key]=x[key]
        if target=='stopped':
            ex=x['first_exit_index'];d['first_exit_source_obs']=np.where(ex>=0,df.source_obs.to_numpy()[np.maximum(ex,0)],-1)
        out.append(d)
    return out

def compact(s,id,df,a,events):
    o=origin_indices(df,a,'D');split=s.cohort.loc[id,'split'];root=OUT/'restricted_test' if split=='test' else OUT
    d=df.iloc[o][['source_obs','time_UTC','time','cell_1','cell_05','season','regime','visit_cell_1','visit_cell_05','departure_day_UTC','departure_year','in_R','mapping_ok','sst_ok']].copy()
    d.insert(0,'id',id);parquet(d,root/'origins'/f'{id}.parquet')
    t=np.r_[a['time'],np.inf];n=len(df);ex=events['next_exit_index'][o]
    ev=pd.DataFrame({'id':id,'origin_source_obs':df.source_obs.to_numpy()[o],
                     'next_observed_outside_epoch':t[ex],'first_missing_hour_epoch':events['first_missing_hour'][o],
                     'first_bad_position_or_mapping_epoch':events['bad_position_or_mapping_time'][o],
                     'first_bad_source_position_epoch':events['bad_source_position_time'][o],
                     'first_pure_geometry_failure_epoch':events['bad_geometry_time'][o],
                     'next_unknown_regime_epoch':t[events['next_unknown_index'][o]],
                     'next_not_drogued_epoch':t[events['next_not_drogued_index'][o]],
                     'next_not_undrogued_epoch':t[events['next_not_undrogued_index'][o]]})
    parquet(ev,root/'events'/f'{id}.parquet')

def main():
    p=argparse.ArgumentParser();p.add_argument('--id',required=True,type=int);p.add_argument('--days',required=True,type=int);p.add_argument('--scenario',choices=['drogued','undrogued','pooled'],default='drogued');p.add_argument('--population',choices=['R','D'],default='R');p.add_argument('--tolerance',type=int,choices=[0,1,2,3,6],default=0)
    x=p.parse_args();s=Source();df,a,ev=load_track(s,x.id);o=origin_indices(df,a,x.population);frames=generate(df,a,ev,x.id,o,x.days,x.scenario,x.tolerance)
    root=OUT/'restricted_test' if s.cohort.loc[x.id,'split']=='test' else OUT
    for target,z in zip(['endpoint','stopped'],frames):parquet(z,root/'ledgers/on_demand'/f'{x.id}_{x.population}_{x.days}d_{x.scenario}_{x.tolerance}h_{target}.parquet')
    print('Candidates',len(o),'eligible',[int((z.reason_code==0).sum()) for z in frames])

if __name__=='__main__':main()
