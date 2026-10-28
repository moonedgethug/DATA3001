"""M1vcat empirical displacement refinement. No new statistical estimator.

All donor records keep their equal-pair weights. Coordinates are propagated,
while source/destination velocity labels and frozen mixture settings stay fixed.
"""
from dataclasses import dataclass

import numpy as np
from pyproj import Geod

from data3001.preprocessing.prep_core import cells

GEOD=Geod(ellps='WGS84')
E,U,BINS=-2,-3,9
OBS_DTYPE=np.dtype([('lon','<f8'),('lat','<f8'),('length','<f8'),
                    ('source_obs','<i8'),('time','<i8'),('id','<i8'),('cell','<i4'),
                    ('ve','<f8'),('vn','<f8'),('atom','<i2')])


@dataclass
class DonorPool:
    obs: np.ndarray
    origins: np.ndarray
    endpoints: np.ndarray
    bins: np.ndarray
    conditional_count: np.ndarray
    conditional_start: np.ndarray
    cell_count: np.ndarray
    cell_start: np.ndarray
    fitting_ids: frozenset
    lag_days: int
    geometry: object = None


def fit_pool(obs, origins, endpoints, bins, fitting_ids, lag_days):
    origins,endpoints=np.asarray(origins),np.asarray(endpoints)
    bins=np.asarray(bins);ids=frozenset(int(i) for i in fitting_ids)
    if (origins.ndim!=1 or origins.shape!=endpoints.shape or len(bins)!=len(obs)
            or not ids or isinstance(lag_days,bool) or int(lag_days)!=lag_days or not 1<=lag_days<=365
            or not np.issubdtype(origins.dtype,np.integer) or not np.issubdtype(endpoints.dtype,np.integer)
            or (origins<0).any() or (origins>=len(obs)).any()
            or ((endpoints<0)&(endpoints!=E)).any() or (endpoints>=len(obs)).any()
            or (bins<0).any() or (bins>=BINS).any()):
        raise ValueError('Invalid donor identities, bins, endpoints or lag')
    o=obs[origins];known=endpoints>=0
    if not np.isin(o['id'],list(ids)).all() or not np.isfinite(o['lon']).all() or not np.isfinite(o['lat']).all():
        raise ValueError('Nonfitting or invalid source origin')
    if ((o['cell']<0)|(o['cell']>=64800)).any():raise ValueError('Invalid source cell')
    if known.any():
        end=obs[endpoints[known]]
        if (not np.array_equal(end['id'],o['id'][known])
                or not np.equal(end['time']-o['time'][known],lag_days*86400).all()
                or not np.equal(endpoints[known]-origins[known],lag_days*24).all()
                or not np.isfinite(end['lon']).all() or not np.isfinite(end['lat']).all()
                or not np.isfinite(end['length']-o['length'][known]).all()
                or (end['length']<o['length'][known]).any()):
            raise ValueError('Source path crosses IDs, lacks exact hourly duration or has invalid length')
    key=o['cell'].astype('int64')*BINS+bins[origins]
    order=np.argsort(key,kind='stable')
    origins=origins[order].astype('int32');endpoints=endpoints[order].astype('int32')
    count=np.bincount(key,minlength=64800*BINS)
    cc=count.reshape(-1,BINS).sum(axis=1)
    return DonorPool(obs,origins,endpoints,bins,count,np.r_[0,np.cumsum(count)[:-1]],
                     cc,np.r_[0,np.cumsum(cc)[:-1]],ids,int(lag_days))


def categorical_law(pool, cell, b, lam):
    if not 0<=lam<=1:raise ValueError('Invalid mixture')
    key=cell*BINS+b;n=int(pool.conditional_count[key]);total=int(pool.cell_count[cell])
    if not total:return {(U,U):1.}
    parts=[(int(pool.cell_start[cell]),total,1. if not n else lam)]
    if n:parts.append((int(pool.conditional_start[key]),n,1-lam))
    law={}
    for start,count,mass in parts:
        if not mass:continue
        end=pool.endpoints[start:start+count];known=end>=0
        dest=np.full(count,E,dtype=int);velocity=dest.copy()
        dest[known]=pool.obs['cell'][end[known]];velocity[known]=pool.bins[end[known]]
        keys,counts=np.unique(np.column_stack([dest,velocity]),axis=0,return_counts=True)
        for (c,a),w in zip(keys,counts):law[(int(c),int(a))]=law.get((int(c),int(a)),0.)+mass*w/count
    return law


def interior_certificate(lon,lat,radius_m,bounds):
    """Prove a WGS84 ball is inside a lon/lat rectangle (conservative only).

    b^2/a is <= both meridional and prime-vertical curvature radii. Until a
    path first leaves the rectangle, cos(latitude)>=cos(max|D latitude|).
    These give lower bounds on distance needed to reach any rectangle side.
    """
    x0,y0,x1,y1=bounds
    if not (-180<=x0<x1<180 and x1-x0<180 and -90<y0<y1<90):
        raise ValueError('A non-antimeridian latitude/longitude rectangle is required')
    lon,lat,radius=np.broadcast_arrays(np.asarray(lon,float),np.asarray(lat,float),np.asarray(radius_m,float))
    curvature=GEOD.a*(1-GEOD.f)**2
    cosine=np.cos(np.deg2rad(max(abs(y0),abs(y1))))
    margin=np.minimum.reduce([lat-y0,y1-lat,cosine*(lon-x0),cosine*(x1-lon)])
    return (np.isfinite(lon)&np.isfinite(lat)&np.isfinite(radius)&(radius>=0)
            &(np.deg2rad(margin)*curvature>radius+1e-3))


def _transferred_exit(pool, origin,end,lon,lat,bounds):
    obs=pool.obs;source=obs[origin];target=obs[end]
    radius=target['length']-source['length']
    identity=(lon==source['lon'])&(lat==source['lat'])
    safe=interior_certificate(lon,lat,radius,bounds)|identity
    if pool.geometry is not None:
        safe|=pool.geometry.certify(obs,origin,end,lon,lat,bounds)
    exit_=np.zeros(len(origin),dtype=bool);scan=np.flatnonzero(~safe)
    hours=24*pool.lag_days+1;x0,y0,x1,y1=bounds
    for start in range(0,len(scan),256):
        ix=scan[start:start+256]
        indices=origin[ix,None]+np.arange(hours)
        path=obs[indices]
        if (not np.equal(path['id'],source['id'][ix,None]).all()
                or not np.equal(path['time']-source['time'][ix,None],np.arange(hours)*3600).all()):
            raise ValueError('A donor path is not a complete same-ID hourly interval')
        ox=np.broadcast_to(source['lon'][ix,None],indices.shape)
        oy=np.broadcast_to(source['lat'][ix,None],indices.shape)
        az,_,length=GEOD.inv(ox.ravel(),oy.ravel(),path['lon'].ravel(),path['lat'].ravel())
        qx=np.broadcast_to(lon[ix,None],indices.shape);qy=np.broadcast_to(lat[ix,None],indices.shape)
        xx,yy,_=GEOD.fwd(qx.ravel(),qy.ravel(),az,length)
        xx=((np.asarray(xx)+180)%360-180).reshape(indices.shape);yy=np.asarray(yy).reshape(indices.shape)
        if not np.isfinite(xx).all() or not np.isfinite(yy).all():raise ValueError('Nonfinite transferred path')
        exit_[ix]=((xx<x0)|(xx>x1)|(yy<y0)|(yy>y1)).any(axis=1)
    return exit_,int((~safe).sum()),int(safe.sum())


def step(pool, lon,lat,codes,velocity,lam,mix_uniform,donor_uniform,mapper,*,precise):
    """One coupled-donor step; outputs x/y remain exact between model steps."""
    arrays=[np.asarray(a) for a in (lon,lat,codes,velocity,mix_uniform,donor_uniform)]
    if len({a.shape for a in arrays})!=1 or arrays[0].ndim!=1 or not np.isfinite(lam) or not 0<=lam<=1:
        raise ValueError('Equal one-dimensional particle arrays and valid lambda required')
    lon,lat,codes,velocity,mix,uniform=arrays
    if ((mix<0)|(mix>=1)|~np.isfinite(mix)|(uniform<0)|(uniform>=1)|~np.isfinite(uniform)).any():
        raise ValueError('Uniforms must be finite and in [0,1)')
    active=codes>=0
    if (not np.isin(codes[~active],[E,U]).all() or (codes[active]>=64800).any()
            or not np.isfinite(lon[active]).all() or not np.isfinite(lat[active]).all()
            or ((velocity[active]<0)|(velocity[active]>=BINS)).any()):
        raise ValueError('Invalid live or absorbing particle')
    result=codes.astype('int32').copy();x=lon.astype(float).copy();y=lat.astype(float).copy();b=velocity.astype('int8').copy()
    statistics={k:0 for k in ['active','unsupported_cell','row_backoff','source_exit','survivor',
                            'translated_exit','path_scanned','path_certified','endpoint_geometry_U']}
    ix=np.flatnonzero(active);statistics['active']=len(ix)
    cell=codes[ix].astype(int);key=cell*BINS+velocity[ix]
    count=pool.conditional_count[key];total=pool.cell_count[cell]
    unsupported=total==0;bad=ix[unsupported];result[bad]=U;b[bad]=U
    statistics['unsupported_cell']=len(bad)
    good=~unsupported;ix=ix[good];cell=cell[good];key=key[good];count=count[good];total=total[good]
    pooled=(count==0)|(mix[ix]<lam)
    statistics['row_backoff']=int((count==0).sum())
    start=np.where(pooled,pool.cell_start[cell],pool.conditional_start[key])
    number=np.where(pooled,total,count)
    chosen=start+(uniform[ix]*number).astype('int64')
    origin=pool.origins[chosen];end=pool.endpoints[chosen]
    absorbed=end==E;result[ix[absorbed]]=E;b[ix[absorbed]]=E
    statistics['source_exit']=int(absorbed.sum())
    ix=ix[~absorbed];origin=origin[~absorbed];end=end[~absorbed]
    statistics['survivor']=len(ix)
    if len(ix):
        native=pool.obs[end];source=pool.obs[origin]
        b[ix]=pool.bins[end]
        if not precise:
            x[ix]=native['lon'];y[ix]=native['lat'];result[ix]=native['cell']
        else:
            if pool.geometry is None:
                az,_,distance=GEOD.inv(source['lon'],source['lat'],native['lon'],native['lat'])
            else:
                az,distance=pool.geometry.displacement(origin,end)
            xx,yy,_=GEOD.fwd(lon[ix],lat[ix],az,distance)
            xx=np.asarray(xx);yy=np.asarray(yy)
            zero=distance==0;xx[zero]=lon[ix][zero];yy[zero]=lat[ix][zero]
            identity=(lon[ix]==source['lon'])&(lat[ix]==source['lat'])
            xx[identity]=native['lon'][identity];yy[identity]=native['lat'][identity]
            exited,scanned,certified=_transferred_exit(pool,origin,end,lon[ix],lat[ix],mapper.domain.bounds)
            statistics['translated_exit']=int(exited.sum());statistics['path_scanned']=scanned;statistics['path_certified']=certified
            result[ix[exited]]=E;b[ix[exited]]=E
            keep=~exited;live=ix[keep]
            mapped=np.asarray(mapper(xx[keep],yy[keep]),dtype='int32')
            mapped[mapped==-1]=U
            result[live]=mapped;x[live]=xx[keep];y[live]=yy[keep]
            statistics['endpoint_geometry_U']=int((mapped==U).sum())
            b[live[mapped<0]]=mapped[mapped<0].astype('int8')
    terminal=result<0;x[terminal]=np.nan;y[terminal]=np.nan
    return result,x,y,b,statistics


def forecast_particles(pools,lon,lat,velocity,horizon_days,lag,lam,particles,seed,mapper,*,precise):
    """Independent particles per exact origin; common RNG inputs across controls."""
    if not 1<=int(horizon_days)<=365 or int(horizon_days)!=horizon_days or particles<2:
        raise ValueError('Integer days and at least two particles required')
    q,r=divmod(int(horizon_days),int(lag));schedule=[int(lag)]*q+([r] if r else [])
    if any(h not in pools for h in schedule):raise ValueError('Missing exact remainder')
    lon,lat,velocity=map(np.asarray,(lon,lat,velocity))
    if lon.ndim!=1 or lon.shape!=lat.shape or lon.shape!=velocity.shape:raise ValueError('Invalid origins')
    x=np.repeat(lon,particles).astype(float);y=np.repeat(lat,particles).astype(float)
    b=np.repeat(velocity,particles).astype('int8');code=cells(x,y)
    rng=np.random.default_rng(seed);audit={}
    for h in schedule:
        code,x,y,b,record=step(pools[h],x,y,code,b,lam,rng.random(len(x)),rng.random(len(x)),mapper,precise=precise)
        for key,value in record.items():audit[key]=audit.get(key,0)+value
    return code.reshape(-1,particles),audit
