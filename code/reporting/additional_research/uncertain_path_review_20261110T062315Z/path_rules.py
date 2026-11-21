import numpy as np
import pandas as pd
from pyproj import Geod
G=Geod(ellps='WGS84')
OFFSETS=np.arange(-72,73)

def ratio(a,b):return np.divide(a,b,out=np.full_like(np.asarray(a,dtype=float),np.nan),where=np.asarray(b)>0)
def quality(valid,minimum):
    offsets=np.arange(valid.shape[1]);last=np.zeros(len(valid),int);gap=np.zeros(len(valid),int)
    for j in offsets:
        here=valid[:,j];gap=np.maximum(gap,np.where(here,j-last,0));last=np.where(here,j,last)
    return valid[:,0]&valid[:,-1]&(valid.sum(axis=1)>=minimum)&(gap<=6),valid.sum(axis=1),gap

def coordinates(track,flags,targets,end):
    t=track[flags.analytical_row.to_numpy()];f=flags[flags.analytical_row.to_numpy()]
    assert not t.time.duplicated().any()
    idx=pd.Index(t.time).get_indexer((targets[:,None]+OFFSETS[None,:]*3600).ravel()).reshape(len(targets),145)
    safe=np.maximum(idx,0)
    valid=(idx>=0)&((f.position_ok&f.mapping_ok).to_numpy()&t.time.le(end).to_numpy())[safe]
    return t.lon_normalized.to_numpy()[safe],t.lat.to_numpy()[safe],valid

def path_features(lon,lat,valid,land):
    import shapely as sh
    n=len(lon);result={}
    target_lon=lon[:,72];target_lat=lat[:,72]
    az,_,r=G.inv(np.broadcast_to(target_lon[:,None],lon.shape).ravel(),np.broadcast_to(target_lat[:,None],lat.shape).ravel(),lon.ravel(),lat.ravel())
    az=np.deg2rad(az.reshape(lon.shape));r=r.reshape(lon.shape)/1000
    xy=np.stack([r*np.sin(az),r*np.cos(az)],axis=-1)
    on_land=sh.intersects_xy(land,lon,lat)&valid
    result['long_land_points']=on_land.sum(axis=1)
    def paths(indices):
        indices=np.asarray(indices)
        qlon=lon[:,indices];qlat=lat[:,indices]
        d=G.inv(qlon[:,:-1].ravel(),qlat[:,:-1].ravel(),qlon[:,1:].ravel(),qlat[:,1:].ravel())[2].reshape(n,len(indices)-1)/1000
        total=d.sum(axis=1);complete=valid[:,indices].all(axis=1)
        return np.where(complete,total,np.nan),complete,d
    def net(i,j):
        d=G.inv(lon[:,i],lat[:,i],lon[:,j],lat[:,j])[2]/1000
        return np.where(valid[:,i]&valid[:,j],d,np.nan)
    for name,start,end in [('before24',48,72),('after24',72,96),('before72',0,72),('after72',72,144)]:
        p3,c3,_=paths(np.arange(start,end+1,3));p6,c6,_=paths(np.arange(start,end+1,6))
        result[name+'_path3_km']=p3;result[name+'_path6_km']=p6;result[name+'_scale_ratio']=ratio(p3,p6)
        result[name+'_net_km']=net(start,end);result[name+'_coherence']=ratio(result[name+'_net_km'],p6)
        result[name+'_coarse_complete']=c3&c6
    for name,start,end in [('before72',0,72),('after72',72,144)]:
        complete,count,gap=quality(valid[:,start:end+1],58)
        result[name+'_hours_complete']=complete;result[name+'_hours']=count;result[name+'_maxgap_h']=gap
    q=xy[:,np.arange(48,97,6),:];v=np.diff(q,axis=1)
    cross=v[:,:-1,0]*v[:,1:,1]-v[:,:-1,1]*v[:,1:,0]
    dot=(v[:,:-1]*v[:,1:]).sum(axis=-1)
    turns=np.rad2deg(np.arctan2(cross,dot));abs_turn=np.abs(turns).sum(axis=1)
    p,complete,d=paths(np.arange(48,97,6))
    result['turn_absolute_deg']=abs_turn;result['turn_direction_coherence']=ratio(np.abs(turns.sum(axis=1)),abs_turn)
    result['short_net_path_ratio']=ratio(net(48,96),p)
    result['min_short_6h_step_km']=d.min(axis=1)
    result['short_path6_km']=p;result['short_coarse_complete']=complete&valid[:,np.arange(48,97,3)].all(axis=1)
    for prefix,start,end,local in [('before',0,72,np.arange(48,73,6)),('after',72,144,np.arange(72,97,6))]:
        direction=xy[:,end]-xy[:,start];steps=np.diff(xy[:,local],axis=1)
        progress=(steps*direction[:,None,:]).sum(axis=-1)
        result[prefix+'_forward_steps']=np.sum(progress>0,axis=1)
        result[prefix+'_local_progress_positive']=progress.sum(axis=1)>0
    post_radius=np.max(np.where(valid[:,72:97],r[:,72:97],-np.inf),axis=1)
    result['post24_radius_km']=np.where(valid[:,72],post_radius,np.nan)
    result['before6_direct_km']=net(66,72);result['after6_direct_km']=net(72,78)
    return pd.DataFrame(result),xy

def decide(f):
    insufficient=f.metadata_conflict|~f.before_complete|~f.after_complete|f.endpoint_on_land|f.motion_land_points.gt(0)
    local_sustain=f.before6_direct_km.ge(1)&f.after6_direct_km.ge(1)
    stay=~insufficient&f.post24_radius_km.le(1)
    loops=(~insufficient&~stay&f.short_coarse_complete&local_sustain&f.before24_path6_km.ge(5)&f.after24_path6_km.ge(5)&
       f.before24_scale_ratio.le(1.25)&f.after24_scale_ratio.le(1.25)&f.min_short_6h_step_km.ge(1)&
       f.turn_absolute_deg.ge(270)&f.turn_direction_coherence.ge(.6)&f.short_net_path_ratio.le(.5))
    long_complete=f.before72_hours_complete&f.after72_hours_complete&f.before72_coarse_complete&f.after72_coarse_complete&f.long_land_points.eq(0)
    consistent=(~insufficient&~stay&~loops&long_complete&local_sustain&f.before72_net_km.ge(5)&f.after72_net_km.ge(5)&
       f.before72_coherence.ge(.8)&f.after72_coherence.ge(.8)&f.before72_scale_ratio.le(1.25)&f.after72_scale_ratio.le(1.25)&
       f.before_forward_steps.ge(3)&f.after_forward_steps.ge(3)&f.before_local_progress_positive&f.after_local_progress_positive)
    return np.select([insufficient,stay,loops,consistent],['insufficient_or_conflicting','suspected_local_stay','looping_evidence','consistent_drift_evidence'],default='other_unresolved')
