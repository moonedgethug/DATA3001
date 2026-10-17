"""User-authorized SST estimates by actual source count; no land-path veto."""
import numpy as np
from pyproj import Geod
from data3001.sst_reconstruction import bilinear
from data3001.sst_coastal import three_corner_temperature


def sparse_temperature(lon,lat,source_points,values,u,v):
    lon,lat=np.asarray(lon,float),np.asarray(lat,float)
    points=np.asarray(source_points,float);t=np.asarray(values,float)
    u,v=np.asarray(u,float),np.asarray(v,float)
    n=len(lon)
    if (lat.shape!=(n,) or points.shape!=(n,4,2) or t.shape!=(n,4)
            or u.shape!=(n,) or v.shape!=(n,)):
        raise ValueError('Expected aligned target and four-corner arrays')
    if not (np.isfinite(points).all() and np.isfinite(lon).all() and np.isfinite(lat).all()):
        raise ValueError('Nonfinite position/source coordinates')
    if not ((u>=0)&(u<=1)&(v>=0)&(v<=1)).all():
        raise ValueError('Target outside original source stencil')
    valid=np.isfinite(t);count=valid.sum(axis=1)
    weights=np.zeros((n,4));method=np.full(n,3,np.int8)
    distance=Geod(ellps='WGS84').inv(np.repeat(lon,4),np.repeat(lat,4),
        points[:,:,0].reshape(-1),points[:,:,1].reshape(-1))[2].reshape(n,4)/1000.
    four=count==4
    if four.any():
        _,weights[four]=bilinear(u[four],v[four],t[four]);method[four]=11
    three=count==3
    if three.any():
        r=three_corner_temperature(u[three],v[three],t[three])
        weights[three]=r['weights']
        method[three]=np.array([{4:12,5:13,3:16}[int(c)] for c in r['method']],np.int8)
    fallback=(count==2)|(count==1)|(method==16)
    for k in np.flatnonzero(fallback):
        use=valid[k];d=distance[k,use]
        exact=d<=1e-9
        if exact.any():
            w=exact.astype(float)/exact.sum()
        else:
            inv=1./d;w=inv/inv.sum()
        weights[k,use]=w
        if count[k]==2:method[k]=14
        elif count[k]==1:method[k]=15
    temperature=np.sum(weights*np.where(valid,t,0.),axis=1)
    temperature[method==3]=np.nan
    return {'temperature_C':temperature,'weights':weights,'method':method,
            'finite_source_count':count,'distance_km':distance}


def termination_context(time,end_date,typedeath):
    time,end,death=np.asarray(time,float),np.asarray(end_date,float),np.asarray(typedeath,int)
    if time.shape!=end.shape or time.shape!=death.shape:raise ValueError('Unaligned official metadata')
    context=np.full(time.shape,'no_official_grounding_or_recovery_at_observation',object)
    for code,name in [(1,'grounding'),(2,'vessel_recovery')]:
        selected=death==code;known=np.isfinite(end)&(end>0)
        day=np.floor(time/86400);last=np.floor(end/86400)
        context[selected & ~known]='official_'+name+'_terminal_date_unknown'
        context[selected & known & (day<last)]='before_official_'+name+'_terminal_day'
        context[selected & known & (day==last)]='official_'+name+'_terminal_day_hour_unknown'
        context[selected & known & (day>last)]='after_official_'+name+'_last_good_day'
    return context


def sample_sparse_grid(lon,lat,longitudes,latitudes,temperature):
    x=np.asarray(longitudes,float);y=np.asarray(latitudes,float);t=np.asarray(temperature,float)
    if t.shape!=(len(y),len(x)) or len(x)<2 or len(y)<2:raise ValueError('Invalid source window')
    if x[0]>x[-1]:x=x[::-1];t=t[:,::-1]
    if y[0]>y[-1]:y=y[::-1];t=t[::-1]
    if not (np.diff(x)>0).all() or not (np.diff(y)>0).all():raise ValueError('Nonmonotone axes')
    empty={'method':3,'temperature_C':np.nan,'route':'no_finite_source_in_received_window'}
    if not (x[0]<=lon<=x[-1] and y[0]<=lat<=y[-1]):
        return {**empty,'route':'source_window_does_not_bracket_target'}
    i=min(max(np.searchsorted(x,lon,side='right')-1,0),len(x)-2)
    j=min(max(np.searchsorted(y,lat,side='right')-1,0),len(y)-2)
    points=np.array([[x[i],y[j]],[x[i+1],y[j]],[x[i],y[j+1]],[x[i+1],y[j+1]]])
    values=np.array([t[j,i],t[j,i+1],t[j+1,i],t[j+1,i+1]])
    u=(lon-x[i])/(x[i+1]-x[i]);v=(lat-y[j])/(y[j+1]-y[j]);route='enclosing_fine_stencil'
    if not np.isfinite(values).any():
        jy,ix=np.where(np.isfinite(t))
        if not len(jy):return empty
        d=Geod(ellps='WGS84').inv(np.full(len(ix),lon),np.full(len(ix),lat),x[ix],y[jy])[2]
        k=int(np.argmin(d));points[0]=[x[ix[k]],y[jy[k]]]
        values[0]=t[jy[k],ix[k]];route='nearest_finite_in_received_window'
    r=sparse_temperature([lon],[lat],points[None,:,:],values[None,:],[u],[v])
    return {'method':int(r['method'][0]),'temperature_C':float(r['temperature_C'][0]),
            'weights':r['weights'][0],'distance_km':r['distance_km'][0],
            'points':points,'values':values,'route':route,'u':u,'v':v}


def apply_sparse_patch(base,patch):
    keys=['id','source_obs']
    allowed={'sst_use_K','sst_method','sst_reason','availability_scope',
             'linear_anchor_left_source_obs','linear_anchor_right_source_obs',
             'sst_source_sd_bound_K','sst_total_se_K','sst_error_kind'}
    if not set(keys).issubset(patch) or not set(patch).issubset(base) or not set(patch).difference(keys).issubset(allowed):
        raise ValueError('Only existing temperature-sidecar fields may change')
    if base.duplicated(keys).any() or patch.duplicated(keys).any():raise ValueError('Duplicate temperature keys')
    import pandas as pd
    loc=pd.MultiIndex.from_frame(base[keys]).get_indexer(pd.MultiIndex.from_frame(patch[keys]))
    if (loc<0).any():raise ValueError('Patch key absent from parent')
    old=base.iloc[loc]
    if not old.sst_method.eq(3).all() or not old.sst_use_K.isna().all():
        raise ValueError('Accepted existing temperature must remain unchanged')
    if not patch.sst_method.isin(range(11,17)).all() or not np.isfinite(patch.sst_use_K).all():
        raise ValueError('Unapproved sparse estimate')
    out=base.copy(deep=True)
    for field in patch.columns.difference(keys):out.iloc[loc,out.columns.get_loc(field)]=patch[field].to_numpy()
    return out


def read_sst_track(id, *, run='sst_sparse_completion_20261017_v1', allow_test=False):
    from data3001.sst_completion import read_sst_track as read_versioned
    return read_versioned(id,run=run,allow_test=allow_test)
