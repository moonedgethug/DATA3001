"""Local real-shoreline index with WGS84 classification bounds, no model geometry changes."""
import time
import numpy as np
import shapely as sh
from shapely.geometry import box
from scipy.spatial import cKDTree
from pyproj import Geod,Transformer
from diagnostic import clipped_real_boundary,distance_class

GEOD=Geod(ellps='WGS84')
ECEF=Transformer.from_crs('EPSG:4979','EPSG:4978',always_xy=True)
LAEA=Transformer.from_crs('EPSG:4326','+proj=laea +lat_0=35 +lon_0=-75 +datum=WGS84 +units=m',always_xy=True)
STEP_DEG=.0005
MAX_STEP_M=STEP_DEG*111700.0

def xyz(points):
    return np.column_stack(ECEF.transform(points[:,0],points[:,1],np.zeros(len(points))))

class CoastIndex:
    def __init__(self,land,points):
        self.land=land;sh.prepare(self.land)
        lo=points.min(axis=0)-5;hi=points.max(axis=0)+5
        if lo[0]<-180 or hi[0]>180 or lo[1]<-80 or hi[1]>80:
            raise ValueError('Local index cannot prove this polar/dateline scope')
        self.bounds=(*lo,*hi)
        coast=clipped_real_boundary(land,box(lo[0],lo[1],hi[0],hi[1]))
        projected=sh.transform(coast,LAEA.transform,interleaved=False)
        segments=[]
        for part in sh.get_parts(projected):
            a=np.asarray(part.coords);segments.append(np.stack([a[:-1],a[1:]],axis=1))
        self.projected_tree=sh.STRtree(sh.linestrings(np.concatenate(segments)))
        dense=sh.segmentize(coast,STEP_DEG)
        coords=[];prev=[];nxt=[];offset=0
        for part in sh.get_parts(dense):
            a=np.asarray(part.coords);n=len(a)
            coords.append(a)
            prev.append(np.r_[-1,np.arange(offset,offset+n-1)])
            nxt.append(np.r_[np.arange(offset+1,offset+n),-1])
            offset+=n
        self.nodes=np.concatenate(coords);self.previous=np.concatenate(prev);self.next=np.concatenate(nxt)
        self.tree=cKDTree(xyz(self.nodes))
        self.node_count=len(self.nodes)
    def crop_distance_lower(self,points):
        # Ellipsoid surface length >= R_min times spherical central angle.
        # R_min=b^2/a > 6335439 m. Latitude edges and full meridians
        # supply conservative bounds to ANY omitted shoreline outside crop.
        xmin,ymin,xmax,ymax=self.bounds
        lon,lat=np.deg2rad(points.T)
        meridians=[np.arcsin(np.clip(np.abs(np.cos(lat)*np.sin(lon-np.deg2rad(x))),0,1)) for x in [xmin,xmax]]
        angles=np.minimum.reduce([np.abs(lat-np.deg2rad(ymin)),np.abs(lat-np.deg2rad(ymax)),*meridians])
        return angles*6335439.
    def refine(self,q,upper):
        # Euclidean chord is a lower bound to surface geodesic distance.
        ix=self.tree.query_ball_point(xyz(np.array([q]))[0],upper+MAX_STEP_M)
        edges=set()
        for j in ix:
            if self.previous[j]>=0:edges.add((int(self.previous[j]),j))
            if self.next[j]>=0:edges.add((j,int(self.next[j])))
        e=np.asarray(sorted(edges),dtype=int)
        if not len(e):raise ValueError('No shoreline segments for refinement')
        a,b=self.nodes[e[:,0]],self.nodes[e[:,1]]
        lengths=np.linalg.norm(b-a,axis=1)*111700.
        for divisions in [64,1024,16384]:
            best=np.inf
            for start in range(0,len(a),32):
                t=np.linspace(0,1,divisions+1)
                p=(a[start:start+32,None,:]*(1-t[None,:,None])+b[start:start+32,None,:]*t[None,:,None]).reshape(-1,2)
                distances=GEOD.inv(np.full(len(p),q[0]),np.full(len(p),q[1]),p[:,0],p[:,1])[2]
                best=min(best,float(distances.min()))
            lower=max(0,best-float(lengths.max())/(2*divisions))
            if np.searchsorted([5000,10000,50000],lower,side='left')==np.searchsorted([5000,10000,50000],best,side='left'):
                return lower,best,divisions,len(edges)
        raise ValueError('Coastal distance remains ambiguous at threshold')
    def distances(self,points,check=lambda:None):
        points=np.asarray(points,float)
        lower_crop=self.crop_distance_lower(points)
        if (lower_crop<50000).any():raise ValueError('Crop cannot guarantee every classification coastline')
        chord,ix=self.tree.query(xyz(points),workers=1)
        n=self.nodes[ix]
        upper=GEOD.inv(points[:,0],points[:,1],n[:,0],n[:,1])[2]
        lower=np.minimum(np.maximum(0,chord-MAX_STEP_M/2),lower_crop)
        land=sh.intersects_xy(self.land,points[:,0],points[:,1])
        ambiguous=(np.searchsorted([5000,10000,50000],lower,side='left')!=np.searchsorted([5000,10000,50000],upper,side='left'))&~land
        refinements=[]
        for count,j in enumerate(np.flatnonzero(ambiguous)):
            lower[j],upper[j],divisions,edges=self.refine(points[j],upper[j])
            refinements.append({'position':int(j),'divisions':divisions,'edges':edges})
            if count%50==0:check()
        x,y=LAEA.transform(points[:,0],points[:,1])
        indices,dist=self.projected_tree.query_nearest(sh.points(x,y),all_matches=False,return_distance=True)
        projected=np.empty(len(points));projected[indices[0]]=dist
        groups=np.array([distance_class(a,b) for a,b in zip(lower,upper)],dtype=object)
        groups[land]='land_or_boundary'
        if (groups=='uncertain').any():raise ValueError('Unresolved coast group')
        return dict(distance_lower_m=lower,distance_upper_m=upper,projected_distance_m=projected,
            land_or_boundary=land,group=groups,crop_distance_lower_m=lower_crop),refinements
