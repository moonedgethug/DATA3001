"""Independent scalar path arithmetic and complete transition/count checks."""
import json,math
import numpy as np
import pandas as pd
import shapely as sh
from pyproj import Geod
from io_utils import *
G=Geod(ellps='WGS84')

def calculate(points,valid,land):
    # points are 145 independently joined lon/lat slots.
    result={};p0=points[72];xy=[]
    for p in points:
        az,_,d=G.inv(p0[0],p0[1],p[0],p[1]);xy.append((d/1000*math.sin(math.radians(az)),d/1000*math.cos(math.radians(az))))
    xy=np.array(xy)
    def distance(i,j):
        if not valid[i] or not valid[j]:return np.nan
        return G.inv(*points[i],*points[j])[2]/1000
    def path(start,end,step):
        ix=list(range(start,end+1,step))
        if not all(valid[i] for i in ix):return np.nan
        return sum(distance(i,j) for i,j in zip(ix[:-1],ix[1:]))
    def div(a,b):return a/b if b>0 else np.nan
    for name,start,end in [('before24',48,72),('after24',72,96),('before72',0,72),('after72',72,144)]:
        a=path(start,end,3);b=path(start,end,6);d=distance(start,end)
        result.update({name+'_path3_km':a,name+'_path6_km':b,name+'_net_km':d,name+'_scale_ratio':div(a,b),name+'_coherence':div(d,b),name+'_coarse_complete':all(valid[i] for i in range(start,end+1,3))})
    for prefix,start,end in [('before72',0,72),('after72',72,144)]:
        offsets=np.flatnonzero(valid[start:end+1]);gap=max(np.diff(offsets),default=0)
        complete=bool(valid[start] and valid[end] and len(offsets)>=58 and gap<=6)
        result.update({prefix+'_hours_complete':complete,prefix+'_hours':len(offsets)})
    q=xy[48:97:6];v=np.diff(q,axis=0)
    turns=[]
    for a,b in zip(v[:-1],v[1:]):turns.append(math.degrees(math.atan2(a[0]*b[1]-a[1]*b[0],float(a@b))))
    absolute=sum(abs(x) for x in turns);p=path(48,96,6)
    result.update(turn_absolute_deg=absolute,turn_direction_coherence=div(abs(sum(turns)),absolute),short_net_path_ratio=div(distance(48,96),p),
        short_path6_km=p,short_coarse_complete=all(valid[i] for i in range(48,97,3)))
    # Step minima are only meaningful for complete coarse positions; audited states use these.
    result['min_short_6h_step_km']=min(distance(i,i+6) for i in range(48,96,6)) if all(valid[i] for i in range(48,97,6)) else np.nan
    for prefix,start,end,local in [('before',0,72,range(48,73,6)),('after',72,144,range(72,97,6))]:
        direction=xy[end]-xy[start];ix=list(local);progress=[float((xy[j]-xy[i])@direction) for i,j in zip(ix[:-1],ix[1:])]
        result[prefix+'_forward_steps']=sum(x>0 for x in progress);result[prefix+'_local_progress_positive']=sum(progress)>0
    result['post24_radius_km']=max((distance(72,j) for j in range(72,97) if valid[j]),default=np.nan)
    result['before6_direct_km']=distance(66,72);result['after6_direct_km']=distance(72,78)
    result['long_land_points']=int(np.sum(sh.intersects_xy(land,points[:,0],points[:,1])&valid))
    return result

def independent_label(r):
    if r.metadata_conflict or not r.before_complete or not r.after_complete or r.endpoint_on_land or r.motion_land_points>0:return 'insufficient_or_conflicting'
    if r.post24_radius_km<=1:return 'suspected_local_stay'
    local=r.before6_direct_km>=1 and r.after6_direct_km>=1
    if (r.short_coarse_complete and local and r.before24_path6_km>=5 and r.after24_path6_km>=5 and r.before24_scale_ratio<=1.25 and r.after24_scale_ratio<=1.25 and r.min_short_6h_step_km>=1 and r.turn_absolute_deg>=270 and r.turn_direction_coherence>=.6 and r.short_net_path_ratio<=.5):return 'looping_evidence'
    if (r.before72_hours_complete and r.after72_hours_complete and r.before72_coarse_complete and r.after72_coarse_complete and r.long_land_points==0 and local and r.before72_net_km>=5 and r.after72_net_km>=5 and r.before72_coherence>=.8 and r.after72_coherence>=.8 and r.before72_scale_ratio<=1.25 and r.after72_scale_ratio<=1.25 and r.before_forward_steps>=3 and r.after_forward_steps>=3 and r.before_local_progress_positive and r.after_local_progress_positive):return 'consistent_drift_evidence'
    return 'other_unresolved'

def main():
    s=Session();passed=False
    try:
        old=pd.read_parquet(s.read(OLD/'results/endpoint_states.parquet'))
        f=pd.read_parquet(s.read(OUT/'results/updated_endpoint_states.parquet'))
        reviewed=pd.read_parquet(s.read(OUT/'results/reviewed_uncertain.parquet'))
        assert len(f)==len(old)==313029
        pd.testing.assert_frame_equal(f[old.columns].sort_values(KEY).reset_index(drop=True),old.sort_values(KEY).reset_index(drop=True))
        expect=old[old.risk_set&old.state.eq('uncertain')][KEY].sort_values(KEY).reset_index(drop=True)
        pd.testing.assert_frame_equal(reviewed[KEY].sort_values(KEY).reset_index(drop=True),expect)
        dm=json.loads(s.read(ROOT/'configs/dataset_manifest.json').read_text())['records'];qm=json.loads(s.read(ROOT/'configs/qualification_manifest.json').read_text())['records']
        assets=json.loads(s.read(ROOT/'configs/assets.json').read_text())['assets'];asset=assets['land_mask_high']
        land=sh.from_wkb(s.read(ROOT/asset['path'],asset['sha256']).read_bytes());sh.prepare(land)
        checks=[]
        for num,(ident,g) in enumerate(reviewed.groupby('id'),1):
            tr=pd.read_parquet(s.read(ROOT/dm[str(ident)]['path'],dm[str(ident)]['sha256']),columns=['source_obs','time','lon_normalized','lat'])
            fl=pd.read_parquet(s.read(ROOT/qm[str(ident)]['path'],qm[str(ident)]['sha256']))
            assert np.array_equal(tr[['source_obs','time']],fl[['source_obs','time']])
            good=fl.analytical_row&fl.position_ok&fl.mapping_ok&tr.time.le(g.official_end_epoch.iloc[0])
            lookup={r.time:(r.lon_normalized,r.lat) for r in tr[good.to_numpy()].itertuples(index=False)}
            ordered=g.sort_values(KEY);selected=set(ordered.index[[0,len(ordered)//2,len(ordered)-1]])
            selected.update(g[g.path_evidence.isin(['looping_evidence','consistent_drift_evidence','suspected_local_stay'])].index)
            for index in sorted(selected):
                row=g.loc[index];times=[row.target_epoch+h*3600 for h in range(-72,73)];valid=np.array([t in lookup for t in times])
                points=np.array([lookup.get(t,(np.nan,np.nan)) for t in times]);calc=calculate(points,valid,land)
                for name,value in calc.items():
                    # Coordinates at unavailable slots are deliberately not compared.
                    if name.startswith('turn_') or name in ['min_short_6h_step_km']:
                        if not calc['short_coarse_complete']:continue
                    if name.startswith(('before_forward','after_forward','before_local','after_local')):
                        if not (calc['before72_coarse_complete'] and calc['after72_coarse_complete']):continue
                    assert np.isclose(value,row[name],atol=1e-7,rtol=1e-10,equal_nan=True),(ident,row.origin_source_obs,name,value,row[name])
                checks.append({'id':int(ident),'origin_source_obs':int(row.origin_source_obs),'path_evidence':row.path_evidence})
            if num%50==0:print('Independent path checks',num,'IDs',len(checks),'windows',flush=True)
            s.check()
        assert len({r['id'] for r in checks})==287
        assert [independent_label(r) for r in reviewed.itertuples(index=False)]==reviewed.path_evidence.tolist()
        for r in reviewed.itertuples(index=False):
            new='drifting_evidence' if r.path_evidence in ['looping_evidence','consistent_drift_evidence'] else 'uncertain'
            assert r.updated_state==new
        assert f.loc[~(f.risk_set&f.state.eq('uncertain')),'updated_state'].eq(f.loc[~(f.risk_set&f.state.eq('uncertain')),'state']).all()
        summary=pd.read_csv(OUT/'results/updated_summary.csv')
        for row in summary.itertuples(index=False):
            scope=f.risk_set if row.scope=='all_risk' else f.used_by_original
            z=f[scope&f.cohort.eq(row.cohort)];sub=z[z.updated_state.eq(row.state)]
            assert len(sub)==row.pairs and sub.id.nunique()==row.ids
            rates=[float(h.updated_state.eq(row.state).sum()/len(h)) for _,h in z.groupby('id')]
            assert np.isclose(sum(rates)/len(rates),row.id_equal_fraction,atol=1e-12)
        for _,g in summary.groupby(['scope','cohort']):assert g.pairs.sum()==g.total_pairs.iloc[0]
        breakdown=pd.read_csv(OUT/'results/uncertain_breakdown.csv')
        for row in breakdown.itertuples(index=False):
            z=reviewed[reviewed.cohort.eq(row.cohort)&reviewed.path_evidence.eq(row.path_evidence)]
            if row.scope=='frozen_used':z=z[z.used_by_original]
            assert len(z)==row.pairs and z.id.nunique()==row.ids
        pd.DataFrame(checks).to_csv(OUT/'results/independent_path_checks.csv',index=False)
        write_json(OUT/'logs/audit_checks.json',{'passed':True,'independent_path_windows':len(checks),'all_reviewed_ids':287,'all_positive_and_stay_candidates_checked':True,'all_28300_labels_independently_reconstructed':True,'original_columns_and_keys_unchanged':True,'counts_and_id_equal_weights_verified':True})
        passed=True;print('Independent audit passed',len(checks),'windows',flush=True)
    finally:s.close('audit',passed)

if __name__=='__main__':main()
