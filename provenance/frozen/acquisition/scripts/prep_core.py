"""Source-preserving deterministic rules. Times are UTC epoch seconds.

Retrospective regime/event labels are NOT forecast-time features.
"""
import numpy as np
from pyproj import Geod

GEOD=Geod(ellps='WGS84')
REASONS={0:'eligible',1:'origin_invalid',2:'administrative_immaturity',3:'track_termination',
         4:'unknown_regime',5:'fixed_scenario_mismatch_or_switching',6:'incomplete_path',7:'missing_target_timestamp',
         8:'endpoint_position_invalid',9:'geometry_uncertain'}
SECONDARY={1:'origin_invalid',2:'administrative_immaturity',4:'track_termination',8:'unknown_regime',
           16:'fixed_scenario_mismatch_or_switching',32:'missing_target_timestamp',64:'endpoint_position_invalid',
           128:'incomplete_path',256:'geometry_uncertain'}

def coordinates(lon,lat):
    ok=np.isfinite(lon)&np.isfinite(lat)&(lon>=-180)&(lon<=180)&(lat>=-90)&(lat<=90)
    norm=np.full(len(lon),np.nan);norm[ok]=(lon[ok]+180)%360-180
    return norm,ok

def velocity_ok(u,v):return np.isfinite(u)&np.isfinite(v)
def uncertainty_ok(x):return np.isfinite(x)&(x>=0)
def sst_ok(x,flag,anomaly=False):
    if anomaly:return np.isfinite(x)&(flag==5)
    c=np.asarray(x,dtype=float)-273.15
    return np.isfinite(x)&np.isin(flag,[4,5])&(c>=-2)&(c<=50)

def duplicates(d):
    """0 representative, 1 exact duplicate, 2 conflict. Raw rows retained."""
    t=d['time'];status=np.zeros(len(t),np.int8);groups=[]
    _,inv,counts=np.unique(t[np.isfinite(t)],return_inverse=True,return_counts=True)
    inds=np.flatnonzero(np.isfinite(t))
    for k in np.flatnonzero(counts>1):
        rows=inds[inv==k];groups.append(rows.tolist())
        exact=all(np.array_equal(np.asarray(v)[rows],np.repeat(np.asarray(v)[rows[0]],len(rows)),equal_nan=True)
                  for v in d.values())
        status[rows[1:] if exact else rows]=1 if exact else 2
    return status,groups

def regimes(t,flag,loss):
    """Zero=uncertain. Generic NaN origin in pinned conversion is not proven.

    Positive loss dates independently define intervals; matching source flags are
    required. A half-float32-ULP transition guard prevents false precision.
    """
    r=np.full(len(t),-1,np.int8)
    if not np.isfinite(loss) or loss<=0:return r
    eps=abs(float(np.spacing(np.float32(loss))))/2
    before=t<loss-eps;after=t>=loss+eps
    r[before&(flag==1)]=1;r[after&(flag==0)]=0
    return r

def cells(lon,lat,res=1):
    out=np.full(len(lon),-1,np.int32);valid=np.isfinite(lon)&np.isfinite(lat)&(lat>=-90)&(lat<90)
    nx=int(360/res);out[valid]=(np.floor((lat[valid]+90)/res).astype(np.int32)*nx+
                              np.floor(((lon[valid]+180)%360)/res).astype(np.int32))
    return out

def visits(t,cell):
    if not len(t):return np.array([],np.int32)
    new=np.r_[True,(np.diff(t)!=3600)|(np.diff(cell)!=0)|(cell[1:]<0)]
    return np.cumsum(new,dtype=np.int32)-1

def displacement(t,lon,lat):
    n=len(t);km=np.full(n,np.nan);u=km.copy();v=km.copy()
    if n<2:return km,u,v
    dt=np.diff(t);ok=(dt>0)&np.isfinite(dt)&np.isfinite(lon[:-1])&np.isfinite(lon[1:])&np.isfinite(lat[:-1])&np.isfinite(lat[1:])
    az,_,dist=GEOD.inv(lon[:-1][ok],lat[:-1][ok],lon[1:][ok],lat[1:][ok]);idx=np.flatnonzero(ok)+1
    km[idx]=dist/1000;speed=dist/dt[ok];u[idx]=speed*np.sin(np.deg2rad(az));v[idx]=speed*np.cos(np.deg2rad(az))
    return km,u,v

def next_index(condition):
    n=len(condition);return np.minimum.accumulate(np.where(condition,np.arange(n),n)[::-1])[::-1]

def event_bounds(a):
    t=a['time'];n=len(t);pos=a['position_ok'];mapping=a['mapping_ok']
    nx=next_index(pos&mapping&~a['inside_D'])
    bad=next_index(~pos|~mapping)
    bt=np.r_[t,np.inf][bad]
    # The first absent expected hour is earlier than the next observed timestamp.
    gaps=np.r_[np.diff(t)!=3600,False]
    ng=next_index(gaps)
    gt=np.r_[t+3600,np.inf][ng]
    return {'next_exit_index':nx,'bad_position_or_mapping_time':bt,'first_missing_hour':gt,
            'bad_source_position_time':np.r_[t,np.inf][next_index(~pos)],
            'bad_geometry_time':np.r_[t,np.inf][next_index(pos&~mapping)],
            'next_unknown_index':next_index(a['regime']<0),
            'next_not_drogued_index':next_index(a['regime']!=1),
            'next_not_undrogued_index':next_index(a['regime']!=0)}

def _regime(a,origins,end,scenario,events):
    n=len(a['time']);z=np.zeros(len(origins),bool)
    if scenario=='pooled':return z,z
    want=1 if scenario=='drogued' else 0
    loss=a['loss'];t=a['time'];ext=np.r_[t,np.inf]
    unknown=(a['regime'][origins]<0)|(ext[events['next_unknown_index'][origins]]<=end)
    if not np.isfinite(loss) or loss<=0:unknown[:]=True;return unknown,z
    eps=abs(float(np.spacing(np.float32(loss))))/2
    unknown |= (end>=loss-eps)&(end<loss+eps)
    # Independent recorded loss-date eligibility also spans unobserved hours.
    known_origin=a['regime'][origins]>=0
    switch=known_origin&(a['regime'][origins]!=want)
    switch |= (t[origins]<loss-eps)&(end>=loss+eps)
    # Unknown precision/source status and an independently recorded loss crossing
    # may coexist. Neither predicate erases the other from secondary evidence.
    return unknown,switch

def labels(a,origins,days,tolerance,scenario,events=None,cutoff=np.inf):
    """Vectorized independent endpoint/stopped eligibility for one horizon.

    Nominal path events are never repaired by tolerant endpoint matching.
    The result retains secondary predicates even when known exit overrides them.
    """
    if events is None:events=event_bounds(a)
    t=a['time'];n=len(t);o=np.asarray(origins);target=t[o]+days*86400
    valid=np.flatnonzero(a['position_ok']);vt=t[valid]
    j=np.searchsorted(vt,target);left=np.clip(j-1,0,max(0,len(vt)-1));right=np.clip(j,0,max(0,len(vt)-1))
    if len(vt):
        dl=np.abs(vt[left]-target);dr=np.abs(vt[right]-target)
        ep=valid[np.where(dl<=dr,left,right)];err=t[ep]-target;matched=np.abs(err)<=tolerance*3600
    else:ep=np.zeros(len(o),int);err=np.full(len(o),np.nan);matched=np.zeros(len(o),bool)
    exact=np.searchsorted(t,target);exists=(exact<n)&(t[np.minimum(exact,n-1)]==target)
    invalid=exists&~a['position_ok'][np.minimum(exact,n-1)]&~matched
    required=np.maximum(target,np.where(matched,t[ep],target))
    unknown,switch=_regime(a,o,required,scenario,events)
    origbad=~a['position_ok'][o]
    immature=target>cutoff;terminated=(target>t[-1])&~immature
    # Mapping includes source-position usability upstream. Only a usable
    # position can independently fail the geometric mapping predicate.
    pure_geometry=a['position_ok']&~a['mapping_ok']
    geometry=pure_geometry[o]|(matched&pure_geometry[ep])
    incomplete=(np.minimum(events['bad_position_or_mapping_time'][o],events['first_missing_hour'][o])<=target)
    sec=(origbad.astype(np.uint16)+2*immature+4*terminated+8*unknown+16*switch+
         32*~matched+64*invalid+128*incomplete+256*geometry).astype(np.uint16)
    # Published precedence: origin, immaturity, termination, unknown, switching,
    # geometry, invalid endpoint, absent timestamp, eligible.
    er=np.select([origbad,immature,terminated,unknown,switch,geometry,invalid,~matched],[1,2,3,4,5,9,8,7],default=0).astype(np.int8)
    endpoint={'reason':er,'secondary':sec,'endpoint_index':np.where(matched,ep,-1),
              'time_error_seconds':np.where(matched,err,np.nan),'required_interval_end':required,
              'outside':(er==0)&~a['inside_D'][ep],
              'origin_source_position_failure':origbad,
              'endpoint_source_position_failure':invalid,'geometry_failure':geometry}
    xi=events['next_exit_index'][o];xt=np.r_[t,np.inf][xi]
    need=np.minimum(target,xt)
    pu,ps=_regime(a,o,need,scenario,events)
    pbad=events['bad_position_or_mapping_time'][o]<=need
    gap=events['first_missing_hour'][o]<=need
    xo=(xt<=target)&~origbad&~pu&~ps&~pbad&~gap
    # Only an eligible established exit shortens the required interval. An
    # outside observation after a gap/unknown state leaves the nominal horizon
    # as the requirement and cannot conceal later secondary failures.
    need=np.where(xo,xt,target)
    pu,ps=_regime(a,o,need,scenario,events)
    pbad=events['bad_position_or_mapping_time'][o]<=need
    gap=events['first_missing_hour'][o]<=need
    pj=np.searchsorted(t,target);pexists=(pj<n)&(t[np.minimum(pj,n-1)]==target)
    # Independent bounds retain both failures even if source invalidity occurs
    # before a later pure geometry failure. Source invalidity alone is reason 6.
    pathsource=events['bad_source_position_time'][o]<=need
    pathgeom=events['bad_geometry_time'][o]<=need
    sr=np.select([origbad,pu,ps,pathgeom,pbad|gap,immature,terminated,~pexists],[1,4,5,9,6,2,3,7],default=0).astype(np.int8)
    sr[xo]=0
    ssec=(origbad.astype(np.uint16)+2*immature+4*terminated+8*pu+16*ps+32*~pexists+
          128*(pbad|gap)+256*pathgeom).astype(np.uint16)
    stopped={'reason':sr,'secondary':ssec,'outside':xo,'first_exit_index':np.where(xo,xi,-1),
             'required_interval_end':need,'endpoint_index':np.where((sr==0)&~xo,pj,-1),
             'path_source_position_failure':pathsource,'path_geometry_failure':pathgeom,
             'path_timestamp_gap':gap}
    return endpoint,stopped
