"""Exact numerical cache; not model predictors or altered statistical weights.

For a geodesic on an ellipsoid of revolution, the sign of longitudinal
momentum is conserved away from the poles. A source point west/east of its
origin inside this <180deg rectangle has west/east inverse bearing. For
all west/east source hours, native cumulative path length through the last
such hour bounds each inverse-geodesic distance. Use that one-sided radius
for the corresponding D side; retain the old total-radius N/S bounds.
Before the first boundary crossing, these bounds exclude all four sides.
Uncertified paths still receive the original exact hourly transfer scan.
"""
import numpy as np
from data3001.modelling.markov_position import GEOD

GEO_DTYPE=np.dtype([('endpoint','<i4'),('azimuth','<f8'),('distance','<f8'),
                    ('west_hour','u1'),('east_hour','u1')])


def build_geometry(obs,origins,endpoints,lag,offset=0):
    """Return one native-ID-aligned cache block; no cross-ID path expansion."""
    origins=np.asarray(origins,dtype='int64');ends=np.asarray(endpoints,dtype='int64')
    hours=24*lag
    if (lag not in [1,2,3,5,7] or origins.shape!=ends.shape or origins.ndim!=1
            or (origins<0).any() or (ends>=len(obs)).any() or not np.equal(ends-origins,hours).all()):
        raise ValueError('Cache requires exact same-ID survivor intervals')
    out=np.zeros(len(obs),dtype=GEO_DTYPE);out['endpoint']=-1
    out['azimuth']=np.nan;out['distance']=np.nan;out['west_hour']=255;out['east_hour']=255
    for first in range(0,len(origins),2048):
        o=origins[first:first+2048];e=ends[first:first+2048]
        indices=o[:,None]+np.arange(hours+1)
        if (not np.equal(obs['id'][indices],obs['id'][o,None]).all()
                or not np.equal(obs['time'][indices]-obs['time'][o,None],np.arange(hours+1)*3600).all()):
            raise ValueError('Cached donor lacks a complete same-ID hourly path')
        x=obs['lon'][indices];start=obs['lon'][o,None]
        if not np.isfinite(x).all() or (np.abs(x-start)>=180).any():raise ValueError('Unsupported source longitude path')
        az,_,dist=GEOD.inv(obs['lon'][o],obs['lat'][o],obs['lon'][e],obs['lat'][e])
        out['endpoint'][o]=e+offset;out['azimuth'][o]=az;out['distance'][o]=dist
        out['west_hour'][o]=np.where(x<start,np.arange(hours+1),0).max(axis=1)
        out['east_hour'][o]=np.where(x>start,np.arange(hours+1),0).max(axis=1)
    return out


class Geometry:
    def __init__(self,array,lag):
        if array.dtype!=GEO_DTYPE or lag not in [1,2,3,5,7]:raise ValueError('Invalid geometry cache encoding')
        self.array=array;self.lag=lag

    def _rows(self,origin,end):
        g=self.array[origin]
        if (not np.array_equal(g['endpoint'],end) or not np.isfinite(g['azimuth']).all()
                or not np.isfinite(g['distance']).all() or (g['west_hour']>24*self.lag).any()
                or (g['east_hour']>24*self.lag).any()):raise ValueError('Cache/source donor identity differs')
        return g

    def displacement(self,origin,end):
        g=self._rows(origin,end);return g['azimuth'],g['distance']

    def certify(self,obs,origin,end,lon,lat,bounds):
        x0,y0,x1,y1=bounds
        if not (-180<=x0<x1<180 and x1-x0<180 and -90<y0<y1<90):raise ValueError('Fixed nonpolar rectangle required')
        g=self._rows(origin,end);source=obs['length'][origin]
        total=obs['length'][end]-source
        west=obs['length'][origin+g['west_hour']]-source
        east=obs['length'][origin+g['east_hour']]-source
        curvature=GEOD.a*(1-GEOD.f)**2;cosine=np.cos(np.deg2rad(max(abs(y0),abs(y1))))
        margins=np.deg2rad(np.column_stack([cosine*(lon-x0),cosine*(x1-lon),lat-y0,y1-lat]))*curvature
        radius=np.column_stack([west,east,total,total])
        return (np.isfinite(margins).all(axis=1)&np.isfinite(radius).all(axis=1)
                &(radius>=0).all(axis=1)&(margins>radius+1e-3).all(axis=1))
