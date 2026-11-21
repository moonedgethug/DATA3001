"""Separate window arithmetic from canonical rows; no production metric functions."""
import numpy as np
import pandas as pd
import shapely as sh
from shapely.geometry import box
from scipy.optimize import minimize_scalar
from pyproj import Transformer
from common import Session,OUT,ROOT,PRIOR,KEY,G,sha,write_json

def main():
    s=Session();passed=False;checks={}
    try:
        f=pd.read_parquet(s.read(OUT/'results/endpoint_states.parquet'))
        original=pd.read_parquet(s.read(PRIOR/'results/origin_availability.parquet'))
        pd.testing.assert_frame_equal(f[KEY].sort_values(KEY).reset_index(drop=True),original[KEY].sort_values(KEY).reset_index(drop=True))
        assert len(f)==313029 and f.id.nunique()==383
        assert f.loc[f.risk_set,'endpoint_available'].eq(~f.loc[f.risk_set,'missing_endpoint']).all()
        dm=__import__('json').loads(s.read(ROOT/'configs/dataset_manifest.json').read_text())['records']
        qm=__import__('json').loads(s.read(ROOT/'configs/qualification_manifest.json').read_text())['records']
        assets=__import__('json').loads(s.read(ROOT/'configs/assets.json').read_text())['assets'];r=assets['land_mask_high']
        land=sh.from_wkb(s.read(ROOT/r['path'],r['sha256']).read_bytes());sh.prepare(land)
        audited=[];stationary=[]
        for number,(ident,group) in enumerate(f.groupby('id'),1):
            tr=pd.read_parquet(s.read(ROOT/dm[str(ident)]['path'],dm[str(ident)]['sha256']),columns=['time','source_obs','lon_normalized','lat'])
            flags=pd.read_parquet(s.read(ROOT/qm[str(ident)]['path'],qm[str(ident)]['sha256']))
            assert np.array_equal(tr[['time','source_obs']],flags[['time','source_obs']])
            mask=flags.analytical_row&flags.position_ok&flags.mapping_ok&tr.time.le(group.official_end_epoch.iloc[0])
            valid=tr[mask.to_numpy()].set_index('time')
            choices=set(group.index[[0,len(group)//2,len(group)-1]])
            for reason,g in group[group.state.eq('uncertain')].groupby('unknown_reason'):choices.add(g.index[0])
            choices.update(group[group.grounding_related_window&group.used_by_original].index)
            def window(target,start,stop,minimum):
                slots=np.arange(start,stop+1)*3600+target
                w=valid.reindex(slots);present=w.lon_normalized.notna()&w.lat.notna()
                times=slots[present.to_numpy()]
                maxgap=float(np.diff(times).max()/3600) if len(times)>1 else 0.
                complete=(bool(present.iloc[0]) and bool(present.iloc[-1]) and int(present.sum())>=minimum and maxgap<=6)
                return w,present,complete,maxgap
            def distance(w,i,j):
                a=w.iloc[i];b=w.iloc[j]
                if pd.isna(a.lon_normalized) or pd.isna(b.lon_normalized):return np.nan
                return G.inv(a.lon_normalized,a.lat,b.lon_normalized,b.lat)[2]/1000
            for ix in sorted(choices):
                row=group.loc[ix];w,p,_,_=window(row.target_epoch,-24,24,40)
                for a,b,field in [(0,24,'before_24h_km'),(24,48,'after_24h_km'),(18,24,'before_6h_km'),(24,30,'after_6h_km')]:
                    actual=distance(w,a,b);assert np.isclose(actual,row[field],atol=1e-9,equal_nan=True), (ident,field)
                for lo,hi,prefix in [(-24,0,'before'),(0,24,'after')]:
                    ww,pp,complete,gap=window(row.target_epoch,lo,hi,20)
                    assert complete==row[prefix+'_complete'] and pp.sum()==row[prefix+'_hours']
                    # Missing endpoints can yield a different diagnostic gap, but never completeness.
                    if pp.iloc[0] and pp.iloc[-1]:assert gap==row[prefix+'_max_gap_h']
                nland=sum(bool(land.intersects(sh.Point(v.lon_normalized,v.lat))) for v in w[p].itertuples())
                assert nland==row.motion_land_points
                audited.append({'id':int(ident),'origin_source_obs':int(row.origin_source_obs),'target_epoch':row.target_epoch,'state':row.state})
            for row in group[group.endpoint_near_5km].itertuples(index=False):
                w,p,complete,gap=window(row.target_epoch,0,168,136)
                if p.iloc[0]:
                    a=w.iloc[0]
                    radius=max(G.inv(a.lon_normalized,a.lat,b.lon_normalized,b.lat)[2]/1000 for b in w[p].itertuples())
                else:radius=np.nan
                assert complete==row.stay_complete and np.isclose(radius,row.stay_radius_km,atol=1e-9,equal_nan=True)
                candidate=complete and radius<=1
                assert candidate==row.nearshore_stay_candidate
                stationary.append({'id':int(ident),'origin_source_obs':int(row.origin_source_obs),'complete':complete,'radius_km':radius})
            if number%100==0:print('Independent endpoint audit',number,'IDs',flush=True)
            s.check()
        assert len({r['id'] for r in audited})==383
        checks['independent_motion_windows']=len(audited);checks['all_nearshore_stay_windows']=len(stationary)
        pd.DataFrame(audited).to_csv(OUT/'results/independent_motion_checks.csv',index=False)
        pd.DataFrame(stationary).to_csv(OUT/'results/independent_stay_checks.csv',index=False)
        assert not f.ground_candidate.any() and not f.nearshore_stay_candidate.any()
        checks['no_unreviewed_grounding_candidates']=True
        for version,col,threshold in [('primary_5km','state',5),('strict_10km','state_strict10',10)]:
            expected=[]
            for row in f.itertuples(index=False):
                if not row.endpoint_available:state='endpoint_missing'
                elif (not row.endpoint_on_land and not row.metadata_conflict and row.before_complete and row.after_complete and row.before_24h_km>=threshold and row.after_24h_km>=threshold and row.before_6h_km>=1 and row.after_6h_km>=1 and row.motion_land_points==0):state='drifting_evidence'
                else:state='uncertain'
                expected.append(state)
            assert np.array_equal(expected,f[col])
        summary=pd.read_csv(OUT/'results/summary.csv')
        for row in summary.itertuples(index=False):
            scope=f.risk_set if row.scope=='all_risk' else f.used_by_original
            g=f[scope&f.cohort.eq(row.cohort)];column='state' if row.version=='primary_5km' else 'state_strict10'
            selected=g[g[column].eq(row.state)];assert len(selected)==row.pairs and selected.id.nunique()==row.ids
            vals=[]
            for ident in g.id.unique():
                h=g[g.id.eq(ident)];vals.append(float(h[column].eq(row.state).sum()/len(h)))
            assert np.isclose(sum(vals)/len(vals),row.id_equal_fraction,atol=1e-12)
        for _,g in summary.groupby(['scope','version','cohort']):assert g.pairs.sum()==g.denominator_pairs.iloc[0]
        checks['all_labels_counts_and_id_equal_fractions']=True
        # Independent continuous shoreline minimization at 200 positions.
        geo=__import__('json').loads((OUT/'logs/geometry.json').read_text())
        boundary=land.boundary.intersection(box(*geo['bounds']))
        segments=[]
        for part in sh.get_parts(boundary):
            coords=np.asarray(part.coords);segments.append(np.stack([coords[:-1],coords[1:]],axis=1))
        seg=np.concatenate(segments)
        proj=Transformer.from_crs('EPSG:4326','+proj=laea +lat_0=35 +lon_0=-75 +datum=WGS84 +units=m',always_xy=True)
        lines=sh.transform(sh.linestrings(seg),proj.transform,interleaved=False);tree=sh.STRtree(lines)
        coast=pd.read_parquet(OUT/'results/endpoint_coast.parquet')
        geo_rows=[]
        for ix in np.unique(np.linspace(0,len(coast)-1,200).astype(int)):
            row=coast.iloc[ix];lon=row.endpoint_lon_observed;lat=row.endpoint_lat_observed
            p=sh.Point(*proj.transform(lon,lat));nearest=int(tree.nearest(p));d=p.distance(lines[nearest]);c=tree.query(p.buffer(d+2000).envelope);c=c[sh.distance(lines[c],p)<=d+2000]
            best=np.inf
            for edge in seg[c]:
                def objective(t):
                    q=edge[0]+t*(edge[1]-edge[0]);return G.inv(lon,lat,q[0],q[1])[2]
                opt=minimize_scalar(objective,bounds=(0,1),method='bounded',options={'xatol':1e-8})
                best=min(best,objective(0),objective(1),float(opt.fun))
            assert row.endpoint_distance_lower_m-.02<=best<=row.endpoint_distance_upper_m+.02
            geo_rows.append({'position':int(ix),'independent_m':best,'lower_m':row.endpoint_distance_lower_m,'upper_m':row.endpoint_distance_upper_m})
        pd.DataFrame(geo_rows).to_csv(OUT/'results/independent_geometry_checks.csv',index=False)
        checks['independent_geodesic_checks']=len(geo_rows)
        checks['all_candidate_keys_and_original_missingness_preserved']=True
        write_json(OUT/'logs/audit_checks.json',checks);passed=True
        print('INDEPENDENT AUDIT PASSED',checks,flush=True)
    finally:s.close('audit',passed)

if __name__=='__main__':main()
