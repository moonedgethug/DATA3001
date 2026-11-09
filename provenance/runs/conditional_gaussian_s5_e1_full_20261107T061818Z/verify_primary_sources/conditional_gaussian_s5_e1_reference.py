"""Independent full-run arithmetic, region reconstruction and ES integration."""
import hashlib
import json
import numpy as np
from pyproj import Geod, Transformer
from scipy.stats import qmc

GEOD=Geod(ellps='WGS84')
MAP=Transformer.from_crs('EPSG:4326','+proj=laea +lon_0=-75 +lat_0=35 +ellps=WGS84 +units=m',always_xy=True)


def rng(key):
    seed=int.from_bytes(hashlib.sha256(json.dumps(('s5_e1_v1',*key),separators=(',',':')).encode()).digest()[:16],'little')
    return np.random.Generator(np.random.PCG64(seed))


def normals(n,dimensions,key):
    u=qmc.Sobol(dimensions,scramble=True,rng=rng(key),optimization=None).random_base2(int(np.log2(n)))
    pairs=[]
    for i in range(0,dimensions,2):
        radius=np.sqrt(-2*np.log1p(-u[:,i]));angle=2*np.pi*u[:,i+1]
        pairs.extend([radius*np.cos(angle),radius*np.sin(angle)])
    return np.array(pairs).T


def xyz(p):
    lon,lat=np.deg2rad(np.asarray(p)).T
    e2=1-(6356752.314245179/6378137.)**2
    radius=6378137/np.sqrt(1-e2*np.sin(lat)**2)
    return np.array([radius*np.cos(lat)*np.cos(lon),radius*np.cos(lat)*np.sin(lon),radius*(1-e2)*np.sin(lat)]).T/1000


def geographic(origin,vectors):
    lon,lat,_=GEOD.fwd(np.full(len(vectors),origin[0]),np.full(len(vectors),origin[1]),
        np.rad2deg(np.arctan2(vectors[:,0],vectors[:,1])),np.hypot(*vectors.T)*1000)
    p=np.array([lon,lat]).T
    p[np.all(vectors==0,axis=1)]=origin
    if not np.isfinite(p).all():raise ValueError('Independent geographic transform failed')
    return p


def fit_vectors(vectors):
    if len(vectors)<3:raise ValueError('Independent insufficient support')
    mean=np.array([np.sum(vectors[:,i],dtype=np.longdouble)/len(vectors) for i in range(2)],float)
    covariance=np.cov(vectors,rowvar=False,bias=True)
    values,axes=np.linalg.eigh(covariance)
    if values[0]<=0 or values[-1]/values[0]>1e12:raise ValueError('Independent covariance gate failed')
    return dict(mean=mean.tolist(),covariance=covariance.tolist(),root=(axes*np.sqrt(values)).tolist())


def fit(origin,endpoints):
    a,_,d=GEOD.inv(np.full(len(endpoints),origin[0]),np.full(len(endpoints),origin[1]),*endpoints.T)
    v=np.array([np.sin(np.deg2rad(a))*d,np.cos(np.deg2rad(a))*d]).T/1000
    return dict(fit_vectors(v),origin=list(origin))


def draw(packet,z):
    return geographic(packet['origin'],np.asarray(packet['mean'])+z@np.asarray(packet['root']).T)


def shift(p,sd,z):
    v=sd*z
    lon,lat,_=GEOD.fwd(*p.T,np.rad2deg(np.arctan2(v[:,0],v[:,1])),np.hypot(*v.T)*1000)
    result=np.array([lon,lat]).T
    result[np.all(v==0,axis=1)]=p[np.all(v==0,axis=1)]
    return result


def ci_cloud(pool,count,key):
    p=pool.points;valid=np.flatnonzero(pool.usable);invalid=np.flatnonzero(~pool.usable);n=len(p)
    if not len(valid):return p,np.full(n,1/n)
    per=2*((count-len(invalid))//(2*len(valid)))
    if per<2:raise ValueError('Independent CI quadrature loses components')
    ix=np.repeat(valid,per//2);z=rng((*key,'audit_ci_cloud',0)).standard_normal((len(ix),2))
    ix=np.concatenate([ix,ix]);z=np.vstack([z,-z])
    cloud=np.vstack([shift(p[ix],pool.sd[ix],z),p[invalid]])
    weights=np.concatenate([np.full(len(ix),1/(n*per)),np.full(len(invalid),1/n)])
    return cloud,weights


def region_xy(xy,weights):
    weights=np.asarray(weights);centre=np.sum(xy*weights[:,None],axis=0)
    covariance=np.cov(xy.T,aweights=weights,bias=True)
    values,axes=np.linalg.eigh(covariance)
    keep=values>64*np.finfo(float).eps*max(values[-1],0.)
    inverse=np.linalg.inv(covariance) if keep.all() else (axes[:,keep]/values[keep])@axes[:,keep].T
    d=xy-centre;distance=np.sum((d@inverse)*d,axis=1)
    units=np.rint(weights/weights.min()).astype(np.int64)
    np.testing.assert_allclose(weights/weights.min(),units,rtol=1e-12,atol=1e-12)
    order=np.argsort(distance,kind='stable');threshold=(9*int(units.sum())+9)//10
    cutoff=distance[order[np.searchsorted(np.cumsum(units[order]),threshold)]]
    area=np.pi*cutoff*np.sqrt(max(np.linalg.det(covariance),0.)) if keep.all() else 0.
    return dict(centre=centre.tolist(),covariance=covariance.tolist(),inverse=inverse.tolist(),
        cutoff=float(cutoff),rank=int(keep.sum()),area_km2=float(area),
        null_tolerance_km=float(64*np.finfo(float).eps*max(1.,np.linalg.norm(centre),np.sqrt(max(values[-1],0.)))))


def inside(xy,region):
    delta=np.asarray(xy)-region['centre'];inv=np.asarray(region['inverse'])
    answer=np.sum((delta@inv)*delta,axis=1)<=region['cutoff']+1e-12
    if region['rank']<2:
        answer &= np.linalg.norm(delta-delta@np.asarray(region['covariance'])@inv,axis=1)<=region['null_tolerance_km']
    return answer


def region(p,w):
    return region_xy(np.array(MAP.transform(*p.T)).T/1000,w)


def regions(pool,packet,count,key):
    result={'ExactPoint':region(pool.points,np.full(len(pool.points),1/len(pool.points)))}
    cloud,w=ci_cloud(pool,count,key);result['EndpointCI']=region(cloud,w)
    cloud=draw(packet,normals(count,2,(*key,'audit_gaussian_region',0)))
    result['LocalGaussian']=region(cloud,np.full(len(cloud),1/len(cloud)))
    return result


def energy(pool,packet,truth,count,key):
    # New independent streams; direct formula with a separately calibrated control.
    target=xyz(np.asarray(truth)[None,:])[0];points=xyz(pool.points);n=len(points)
    calibration=rng((*key,'audit_control',0));ca=calibration.integers(n,size=1024);cb=calibration.integers(n,size=1024)
    distances=np.sqrt(np.sum((points[ca]-points[cb])**2,axis=1));sq=distances**2;sq0=sq-sq.mean()
    coefficient=float(np.dot(distances-distances.mean(),sq0)/np.dot(sq0,sq0)) if np.dot(sq0,sq0)>0 else 0.
    centre=points.mean(axis=0);mean_squared=2*np.mean(np.sum((points-centre)**2,axis=1))
    g=rng((*key,'audit_empirical_energy',0));a=g.integers(n,size=count);b=g.integers(n,size=count)
    za,zb=g.standard_normal((count,2)),g.standard_normal((count,2))
    da=np.sqrt(np.sum((points[a]-points[b])**2,axis=1))
    controlled=-.5*da+.5*coefficient*(da**2-mean_squared)
    first=float(np.sqrt(np.sum((points-target)**2,axis=1)).mean())
    u,v=xyz(shift(pool.points[a],pool.sd[a],za)),xyz(shift(pool.points[b],pool.sd[b],zb))
    change=np.linalg.norm(u-target,axis=1)-np.linalg.norm(points[a]-target,axis=1)-.5*(np.linalg.norm(u-v,axis=1)-da)
    result={}
    for name,term in [('ExactPoint',controlled),('EndpointCI',controlled+change)]:
        result[name]=dict(energy_km=first+float(term.mean()),variance=float(term.var(ddof=1)/count))
    estimates=[]
    for rep in range(8):
        z=normals(count//8,4,(*key,'audit_gaussian_energy',rep))
        u,v=xyz(draw(packet,z[:,:2])),xyz(draw(packet,z[:,2:]))
        estimates.append(float((np.linalg.norm(u-target,axis=1)-.5*np.linalg.norm(u-v,axis=1)).mean()))
    result['LocalGaussian']=dict(energy_km=float(np.mean(estimates)),variance=float(np.var(estimates,ddof=1)/8))
    return result


def iid_energy(packet,truth,count,key):
    z=rng((*key,'audit_iid',0)).standard_normal((count,4));target=xyz(np.asarray(truth)[None,:])[0]
    u,v=xyz(draw(packet,z[:,:2])),xyz(draw(packet,z[:,2:]))
    values=np.linalg.norm(u-target,axis=1)-.5*np.linalg.norm(u-v,axis=1)
    return dict(energy_km=float(values.mean()),variance=float(values.var(ddof=1)/count))
