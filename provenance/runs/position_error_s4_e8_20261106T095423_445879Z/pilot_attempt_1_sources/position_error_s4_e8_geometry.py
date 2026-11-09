"""Frozen land/domain diagnostics; never clips the predictive distribution."""
import json
import numpy as np
import shapely as sh
from shapely.geometry import shape, box, Polygon
from shapely.ops import transform

from data3001.modelling.baselines.position_error_s4_e8 import LAEA, INVERSE, ellipse_boundary


class Geography:
    def __init__(self, paths):
        self.land=sh.from_wkb(paths.asset('land_mask_high',verify=True).read_bytes())
        self.domain=shape(json.loads(paths.asset('transport_D',verify=True).read_text())['features'][0]['geometry'])
        sh.prepare(self.land);sh.prepare(self.domain)
        x0,y0,x1,y1=self.domain.bounds
        self.clip_bounds=(x0-15,y0-15,x1+15,y1+15)
        self.clip=box(*self.clip_bounds)
        land_clip=self.land.intersection(self.clip)
        def project(x,y,z=None):
            east,north=LAEA.transform(x,y)
            return np.asarray(east)/1000,np.asarray(north)/1000
        self.land_xy=transform(project,sh.segmentize(land_clip,max_segment_length=.02))
        self.domain_xy=transform(project,sh.segmentize(self.domain,max_segment_length=.02))
        self.cache={}

    def masses(self,points,weights):
        land=sh.intersects_xy(self.land,points[:,0],points[:,1])
        outside=~sh.intersects_xy(self.domain,points[:,0],points[:,1])
        return {'land_mass':float(weights@land),'outside_D_mass':float(weights@outside)}

    def areas(self,region,vertices=512):
        if region['rank']<2:
            return dict(land_area_km2=0.,wet_area_km2=0.,outside_D_area_km2=0.,polygon_relative_error=0.)
        boundary=ellipse_boundary(region,vertices)
        lon,lat=INVERSE.transform(boundary[:,0]*1000,boundary[:,1]*1000)
        x0,y0,x1,y1=self.clip_bounds
        if not ((np.asarray(lon)>x0).all() and (np.asarray(lon)<x1).all()
                and (np.asarray(lat)>y0).all() and (np.asarray(lat)<y1).all()):
            raise ValueError('Ellipse exceeds the exact-intersection land clip; no area may be silently lost')
        polygon=Polygon(boundary)
        if not polygon.is_valid:raise ValueError('Invalid ellipse polygon')
        area=region['area_km2'];approx=polygon.area
        relative=abs(approx-area)/max(area,1e-20)
        if relative>.0001:raise ValueError('Ellipse polygon not converged')
        land=polygon.intersection(self.land_xy).area
        outside=polygon.difference(self.domain_xy).area
        return dict(land_area_km2=float(land),wet_area_km2=float(area-land),
                    outside_D_area_km2=float(outside),polygon_relative_error=float(relative))
