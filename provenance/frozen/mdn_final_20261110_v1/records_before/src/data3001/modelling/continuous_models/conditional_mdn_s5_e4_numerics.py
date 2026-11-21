"""Complete-law MDN integrals, with no fitting or outcome-dependent regions."""
import math
import time
from functools import lru_cache
import numpy as np
from pyproj import Geod, Transformer
from scipy.stats import qmc

from .conditional_mdn_s5_e4 import stable_seed
from .conditional_gaussian_s5_e1 import mass_diagnostic
from data3001.modelling.baselines import position_error_s4_e8 as region_math

GEOD = Geod(ellps='WGS84')
ECEF = Transformer.from_crs('EPSG:4979', 'EPSG:4978', always_xy=True)
LAEA = Transformer.from_crs('EPSG:4326', '+proj=laea +lon_0=-75 +lat_0=35 +ellps=WGS84 +units=m', always_xy=True)
LEVELS = (65536, 131072, 262144)


def xyz(points):
    p = np.asarray(points, dtype=np.float64)
    result = np.column_stack(ECEF.transform(p[:,0],p[:,1],np.zeros(len(p))))/1000
    if not np.isfinite(result).all(): raise ArithmeticError('Invalid ECEF')
    return result


def xy(points):
    p = np.asarray(points, dtype=np.float64)
    result = np.column_stack(LAEA.transform(p[:,0],p[:,1]))/1000
    if not np.isfinite(result).all(): raise ArithmeticError('Invalid LAEA')
    return result


def to_geographic(origin, vectors):
    v = np.asarray(vectors,dtype=np.float64)
    if v.ndim != 2 or v.shape[1] != 2 or not np.isfinite(v).all(): raise ValueError('Invalid displacement')
    radius = np.hypot(v[:,0],v[:,1])
    lon,lat,_ = GEOD.fwd(np.full(len(v),float(origin[0])),np.full(len(v),float(origin[1])),
                        np.rad2deg(np.arctan2(v[:,0],v[:,1])),radius*1000,inplace=True)
    points = np.column_stack([lon,lat]); points[radius==0] = origin
    if not np.isfinite(points).all(): raise ArithmeticError('Invalid direct geodesic')
    return points


def to_vectors(origin, endpoints):
    p=np.asarray(endpoints,float)
    o=np.asarray(origin,float)
    if o.ndim==1: o=np.broadcast_to(o,p.shape)
    a,_,d=GEOD.inv(o[:,0],o[:,1],p[:,0],p[:,1])
    return np.column_stack([d*np.sin(np.deg2rad(a)),d*np.cos(np.deg2rad(a))])/1000


@lru_cache(maxsize=24)
def uniforms(count, dimensions, purpose, replicate, key, role=''):
    power=int(math.log2(count))
    if 2**power!=count: raise ValueError('Sobol count must be a power of two')
    seed=stable_seed(purpose,role,None,20261121,key,replicate)
    u=qmc.Sobol(dimensions,scramble=True,rng=np.random.default_rng(seed)).random_base2(power)
    u.setflags(write=False)
    return u


def normals(u):
    u=np.asarray(u,float)
    r=np.sqrt(-2*np.log1p(-u[:,0]));angle=2*np.pi*u[:,1]
    return np.column_stack([r*np.cos(angle),r*np.sin(angle)])


def arrays(packet):
    w,m,l=[np.asarray(packet[k],np.float64) for k in ('weights','means','cholesky')]
    if w.ndim!=1 or m.shape!=(len(w),2) or l.shape!=(len(w),2,2): raise ValueError('Invalid mixture shape')
    if not np.isfinite(w).all() or not np.isfinite(m).all() or not np.isfinite(l).all(): raise ValueError('Nonfinite mixture')
    if abs(w.sum()-1)>1e-10 or (w<0).any() or len(w)==0: raise ValueError('Unnormalized mixture')
    if (np.linalg.eigvalsh(l@l.transpose(0,2,1))<=0).any(): raise ValueError('Degenerate covariance')
    return w,m,l


def draw_vectors(packet, uniform):
    w,m,l=arrays(packet);u=np.asarray(uniform,float)
    if u.ndim!=2 or u.shape[1]!=3 or (u<0).any() or (u>=1).any(): raise ValueError('Invalid uniform nodes')
    cdf=np.cumsum(w);cdf[-1]=1.
    selected=np.searchsorted(cdf,u[:,0],side='right')
    z=normals(u[:,1:])
    return m[selected]+np.einsum('nij,nj->ni',l[selected],z)


def draw(packet, uniform):
    return to_geographic(packet['origin'],draw_vectors(packet,uniform))


def integrands(first,second,truth):
    return np.linalg.norm(first-truth,axis=1)-.5*np.linalg.norm(first-second,axis=1)


def summary(values,count):
    a=np.asarray(values,float)
    if len(a)!=8 or not np.isfinite(a).all(): raise ArithmeticError('Invalid integration replicates')
    variance=float(a.var(ddof=1)/8)
    return dict(energy_km=float(a.mean()),variance=variance,energy_mc_se=math.sqrt(variance),
                replicates=a.tolist(),sample_count=count)


def score_es(packet,target,count,key,role,audit=False):
    if count not in LEVELS: raise ValueError('Unregistered MDN energy level')
    truth=xyz(np.asarray(target)[None])[0];means=[]
    for rep in range(8):
        u=uniforms(count//8,6,'audit' if audit else 'ES',rep,key,role)
        first,second=xyz(draw(packet,u[:,:3])),xyz(draw(packet,u[:,3:]))
        means.append(float(integrands(first,second,truth).mean()))
    return summary(means,count)


def draw_iid(packet,count,key,role,rep=0):
    seed=stable_seed('IID',role,None,20261121,key,rep)
    rng=np.random.default_rng(seed)
    w,m,l=arrays(packet)
    choice=rng.choice(len(w),size=count,p=w)
    z=rng.standard_normal((count,2))
    return to_geographic(packet['origin'],m[choice]+np.einsum('nij,nj->ni',l[choice],z))


def build_region(packet,count,key,role,geography=None,audit=False):
    if count not in LEVELS: raise ValueError('Unregistered region level')
    regions=[];means=[]
    for rep in range(2):
        u=uniforms(count,3,'audit' if audit else 'region',100+rep if audit else rep,key,role)
        points=draw(packet,u)
        regions.append(region_math.fit_region(xy(points)))
        means.append(xyz(points).mean(axis=0).tolist())
    points=draw_iid(packet,65536,key,role,rep=1 if audit else 0)
    hits=region_math.inside_region(xy(points),regions[0])
    result=dict(region=regions[0],replica_region=regions[1],means=means,region_count=count,
                mass_check=mass_diagnostic(int(hits.sum()),len(hits),0.))
    if geography is not None:
        result.update(geography.masses(points,np.full(len(points),1/len(points))))
        result['land_variance']=result['land_mass']*(1-result['land_mass'])/len(points)
        result['outside_variance']=result['outside_D_mass']*(1-result['outside_D_mass'])/len(points)
    return result


def region_metrics(regions, target):
    p=xy(np.asarray(target)[None])
    h=[bool(region_math.inside_region(p,regions[k])[0]) for k in ('region','replica_region')]
    return dict(h90=float(h[0]),hit_disagreement=float(h[0]!=h[1]),
                area90_km2=regions['region']['area_km2'],replica_area90_km2=regions['replica_region']['area_km2'],
                mass_radius=regions['mass_check']['radius'],mass_diagnostic=regions['mass_check']['diagnostic'],
                rank=regions['region']['rank'])


def reference_component_es(packet,target,count,key,role):
    """Different integration path: all component pairs including diagonal events."""
    w,m,l=arrays(packet);truth=xyz(np.asarray(target)[None])[0];values=[]
    for rep in range(8):
        u=uniforms(count//8,4,'audit',200+rep,key,role)
        z1,z2=normals(u[:,:2]),normals(u[:,2:])
        a=[xyz(to_geographic(packet['origin'],centre+z1@root.T)) for centre,root in zip(m,l)]
        b=[xyz(to_geographic(packet['origin'],centre+z2@root.T)) for centre,root in zip(m,l)]
        terms=np.zeros(len(z1))
        for i,wi in enumerate(w):
            terms+=wi*np.linalg.norm(a[i]-truth,axis=1)
            for j,wj in enumerate(w):terms-=.5*wi*wj*np.linalg.norm(a[i]-b[j],axis=1)
        values.append(float(terms.mean()))
    return summary(values,count)


def iid_energy(packet,target,key,role,count=65536):
    first=xyz(draw_iid(packet,count,key,role,10));second=xyz(draw_iid(packet,count,key,role,11))
    v=integrands(first,second,xyz(np.asarray(target)[None])[0])
    return dict(energy_km=float(v.mean()),variance=float(v.var(ddof=1)/count))
