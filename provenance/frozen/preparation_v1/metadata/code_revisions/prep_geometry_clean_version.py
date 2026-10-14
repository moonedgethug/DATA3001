"""GSHHG ocean mask and empirical development domain audit."""
import argparse,json,time
import numpy as np
import pandas as pd
import shapefile
import shapely as sh
from shapely.geometry import shape,box,mapping
from pyproj import Geod
from prep_io import BASE,OUT,Source,save_json,sha

def region_R():return shape(json.loads((BASE/'geometry/release_R.geojson').read_text())['features'][0]['geometry'])

def mask(res='h'):
    path=OUT/f'geometry/gshhg_{res}_land.wkb'
    if path.exists():land=sh.from_wkb(path.read_bytes())
    else:
        files=list((OUT/'metadata/sources/gshhg').rglob(f'GSHHS_{res}_L1.shp'));assert len(files)==1,files
        r=shapefile.Reader(str(files[0]));polys=[]
        # L1 excludes inland lakes from ocean transport. All source L1 polygons
        # retained; no land-based endpoint deletion or beaching inference.
        for x in r.iterShapes():
            p=shape(x.__geo_interface__)
            if not p.is_valid:p=sh.make_valid(p)
            polys.append(p)
        land=sh.union_all(polys);path.write_bytes(sh.to_wkb(land))
    sh.prepare(land);return land

def water_ok(land,lon,lat):
    finite=np.isfinite(lon)&np.isfinite(lat);wet=np.zeros(len(lon),bool)
    wet[finite]=~sh.intersects_xy(land,lon[finite],lat[finite]);return wet

def candidates():
    return json.loads((BASE/'audit/acquisition_domain_candidates.json').read_text())['candidates']

def audit_domains():
    s=Source();r=region_R();rows=[];paths=[];start=time.monotonic()
    for ci,cand in enumerate(candidates()):
        d=box(*cand['bounds_lon_lat']);assert d.covers(r)
        count=outside=reentry=origins=downonly=0;unique=set();rpath=0;rout=0
        for id in s.ids:
            if s.cohort.loc[int(id),'split']=='test':continue
            f=OUT/'cleaned'/f'{id}.parquet';a=pd.read_parquet(f,columns=['time','lon','lat','position_ok','in_R','regime'])
            ok=a.position_ok.to_numpy();inside=sh.intersects_xy(d,a.lon.to_numpy(),a.lat.to_numpy())&ok
            if inside.any():unique.add(int(id));origins+=int(inside.sum());downonly+=int(id not in s.R)
            dt=np.diff(a.time.to_numpy());ex=inside[:-1]&~inside[1:]&ok[1:]&(dt==3600)
            ret=~inside[:-1]&inside[1:]&ok[:-1]&(dt==3600)
            outside+=int(ex.sum());reentry+=int(ret.sum())
            if id in s.R:
                t=a.time.to_numpy();ro=np.flatnonzero(a.in_R.to_numpy()&ok)
                # Union of 365-day windows starting at ALL R origins, no survival requirement.
                j=np.searchsorted(t,t,side='right')-1
                last=np.maximum.accumulate(np.where(a.in_R.to_numpy()&ok,t,-np.inf))
                covered=ok&(t<=last+365*86400)
                rpath+=int(covered.sum());rout+=int((covered&~inside).sum())
        rows.append({'candidate':ci,'padding_degrees':cand['padding_degrees'],'bounds':cand['bounds_lon_lat'],
                     'grid_cells_1deg':int((d.bounds[2]-d.bounds[0])*(d.bounds[3]-d.bounds[1])),
                     'development_IDs':len(unique),'downstream_only_IDs':downonly,'D_origins':origins,
                     'observed_adjacent_exits':outside,'observed_adjacent_returns':reentry,
                     'R_365_intermediate_positions':rpath,'R_365_intermediate_outside':rout})
        print('domain',rows[-1],flush=True)
    # Smallest candidate already covers every observed development R path and R.
    # Select it as an explicitly stopped-domain preparation; model boundary-map
    # stability is not claimed from this observational coverage.
    selected=next(x for x in rows if x['R_365_intermediate_outside']==0)
    d=box(*selected['bounds']);save_json(OUT/'geometry/transport_D.geojson',{'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'urn:ogc:def:crs:OGC:1.3:CRS84'}},'features':[{'type':'Feature','geometry':mapping(d),'properties':{'boundary':'included','product':'stopped-domain','selection':'smallest audited candidate covering all observed R-development intermediate positions through 365 days','test_IDs_used':0}}]})
    save_json(OUT/'audit/domain_selection.json',{'candidates':rows,'selected_candidate':selected['candidate'],'selected_bounds':selected['bounds'],
               'selection_target':'finite stopped-domain product','test_IDs_used':0,'elapsed_seconds':time.monotonic()-start,
               'anchor_evidence':'All development R intermediate positions and therefore observed anchor endpoints covered; see support and candidate maps.',
               'predictive_boundary_stability':'Deferred to modelling; zero observed R-window exits does not prove unrestricted one-year coverage.',
               'downstream_exits_and_returns':'Descriptive consecutive-hour crossings; not all are fixed-regime eligible events.',
               'geometry_sha256':sha(OUT/'geometry/transport_D.geojson')})
    return d

def state_index():
    land=mask('h');d=shape(json.loads((OUT/'geometry/transport_D.geojson').read_text())['features'][0]['geometry']);g=Geod(ellps='WGS84');rows=[]
    for res in (1,.5):
        nx=int(360/res);x0,y0,x1,y1=d.bounds
        for iy in range(int((y0+90)/res),int((y1+90)/res)):
            for ix in range(int((x0+180)/res),int((x1+180)/res)):
                cell=box(-180+ix*res,-90+iy*res,-180+(ix+1)*res,-90+(iy+1)*res);wet=cell.difference(land)
                area=abs(g.geometry_area_perimeter(cell)[0])/1e6
                pieces=list(wet.geoms) if wet.geom_type=='MultiPolygon' else [wet] if not wet.is_empty else []
                wa=sum(abs(g.geometry_area_perimeter(z)[0]) for z in pieces if z.geom_type=='Polygon')/1e6
                rows.append({'resolution':res,'cell':iy*nx+ix,'ix':ix,'iy':iy,'lon_min':cell.bounds[0],'lat_min':cell.bounds[1],
                             'cell_area_km2':area,'wet_area_km2':wa,'water_components':len(pieces),'R_intersection':cell.intersects(region_R())})
    pd.DataFrame(rows).to_parquet(OUT/'geometry/state_index.parquet',index=False,compression='zstd')
    save_json(OUT/'geometry/grid_water_policy.json',{'grid_origin':[-180,-90],'resolutions':[1,.5],'interval':'half-open; latitude +90 not mapped',
             'D_membership':'actual point, polygon boundary included; cell centres never decide R/D membership',
             'water_source':'GSHHG 2.3.7 high-resolution L1','water':'complement of L1 land; enclosed lakes not part of ocean scenario',
             'coastal_boundary':'uncertain mapping, retained source; never snapped or relabelled physical outside',
             'components':'retain all wet components with count and total area in each cell; state remains geographical cell, connectivity is not inferred from common cell',
             'area_method':'WGS84 geodesic polygon area; no spherical equal-area approximation',
             'special_states':{'outside':'eligible observed first exit / eligible outside endpoint, target specific',
                               'unresolved_support':'reserved for modelling missing operator rows; absent outcomes never transitions'},
             'land_wkb_sha256':sha(OUT/'geometry/gshhg_h_land.wkb'),'archive_sha256':sha(OUT/'metadata/sources/gshhg-shp-2.3.7.zip')})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['mask','domain','states']);a=p.parse_args()
    if a.action=='mask':mask('h');mask('i')
    elif a.action=='domain':audit_domains();state_index()
    else:state_index()
