"""Geography and aggregation of frozen score rows, not new forecast scores."""
import json,time
import numpy as np
import pandas as pd
import shapely as sh
from shapely.geometry import shape
from coast import CoastIndex
from diagnostic import *
from runtime import *

MODELS=['MDN22','MDN1','LocalGaussian','ExactPoint','EndpointCI']
METRICS=['energy_km','h90','area90_km2','land_mass','outside_D_mass']

def geographic_phase(s,check):
    t=time.monotonic()
    a=pd.read_parquet(RES/'origin_availability.parquet')
    evidence=pd.read_csv(RES/'id_evidence.csv')
    target=s.frame(E7/'outer_targets.parquet',columns=KEY+['endpoint_lon','endpoint_lat','outside'])
    assert not target.outside.any()
    ends=evidence[['id','official_end_lon','official_end_lat']].rename(columns={'official_end_lon':'lon','official_end_lat':'lat'})
    ends.lon=(ends.lon+180)%360-180
    ends=ends[np.isfinite(ends[['lon','lat']]).all(axis=1)&ends.lat.between(-80,80)]
    tp=target.rename(columns={'endpoint_lon':'lon','endpoint_lat':'lat'})
    points=pd.concat([a[['lon','lat']],ends[['lon','lat']],tp[['lon','lat']]],ignore_index=True).drop_duplicates().reset_index(drop=True)
    catalog=s.json(ROOT/'configs/assets.json')['assets'];asset=catalog['land_mask_high']
    land=sh.from_wkb(s.verified(ROOT/asset['path'],asset['sha256']).read_bytes())
    index=CoastIndex(land,points.to_numpy())
    test_ix=np.unique(np.linspace(0,len(points)-1,200).astype(int))
    z,ref=index.distances(points.iloc[test_ix].to_numpy(),check)
    sample_seconds=time.monotonic()-t
    estimate=sample_seconds+max(.001,sample_seconds/200)*len(points)
    # Building the shared index is a fixed cost, measured separately below.
    trial=time.monotonic();z,ref=index.distances(points.iloc[:min(10000,len(points))].to_numpy(),check)
    per_point=(time.monotonic()-trial)/min(10000,len(points))
    estimate=sample_seconds+per_point*len(points)*2
    json_write(LOG/'geometry_projection.json',{'unique_points':len(points),'shoreline_nodes':index.node_count,
        'bounds':index.bounds,'precheck_seconds':sample_seconds,'seconds_per_point':per_point,
        'projected_seconds_twofold_margin':estimate,'stage_budget_seconds':2100,
        'strategy':'WGS84 chord/geodesic interval checks for ALL unique points, not an unproved projection error bound',
        'max_dense_step_m':55.85,'far_distance_note':'Nearest local shoreline upper distance only if crop bound is below it; groups still proved by lower bounds.'})
    if estimate>2100:raise RuntimeError('Geometry projection exceeds approved budget')
    pieces=[];refinements=[]
    for offset in range(0,len(points),10000):
        block=points.iloc[offset:offset+10000]
        z,ref=index.distances(block.to_numpy(),check)
        f=pd.DataFrame(z);f[['lon','lat']]=block.to_numpy();pieces.append(f)
        refinements.extend([{**r,'position':r['position']+offset} for r in ref])
        if offset%50000==0:print('Coast unique positions',offset,'/',len(points),flush=True)
        check()
    distances=pd.concat(pieces,ignore_index=True)
    assert not distances.duplicated(['lon','lat']).any()
    distances['coastal_group']=distances.group.map({'<=10km':'near_50km','10_50km':'near_50km','>50km':'offshore','land_or_boundary':'land_or_boundary'})
    origin=a[KEY+['cohort','lon','lat','used_by_original','risk_set','missing_endpoint','official_typedeath']].merge(distances,on=['lon','lat'],how='left',validate='many_to_one')
    assert len(origin)==len(a) and origin.group.notna().all()
    save_frame('coastal_groups.parquet',origin)
    save_frame('coastal_distances.parquet',distances)
    enddist=ends.merge(distances,on=['lon','lat'],validate='many_to_one',how='left')
    R=shape(s.json(ROOT/catalog['release_R']['path'],catalog['release_R']['sha256'])['features'][0]['geometry'])
    D=shape(s.json(ROOT/catalog['transport_D']['path'],catalog['transport_D']['sha256'])['features'][0]['geometry'])
    enddist['event_location']=np.select([sh.intersects_xy(R,enddist.lon,enddist.lat),sh.intersects_xy(D,enddist.lon,enddist.lat)],['R','D_outside_R'],default='outside_D')
    enddist['end_near_5km']=enddist.distance_upper_m.le(5000)
    evidence=evidence.merge(enddist[['id','lon','lat','distance_lower_m','distance_upper_m','group','end_near_5km','event_location']],on='id',validate='one_to_one',how='left')
    evidence['event_location']=evidence.event_location.fillna('unknown')
    save_frame('id_evidence.csv',evidence)
    endpoint=tp[KEY+['lon','lat']].merge(distances,on=['lon','lat'],how='left',validate='many_to_one')
    save_frame('observed_endpoint_coast.parquet',endpoint)
    cross=origin.groupby(['cohort','coastal_group','official_typedeath']).agg(candidates=('id','size'),ids=('id','nunique'),used=('used_by_original','sum'),risk=('risk_set','sum'),missing=('missing_endpoint','sum')).reset_index()
    save_frame('availability_coastal_cross.csv',cross)
    # Independent of outcome scores; compare projection to bounded geodesic values.
    fixed=distances.iloc[test_ix].copy()
    fixed['projection_below_interval_m']=np.maximum(0,fixed.distance_lower_m-fixed.projected_distance_m)
    fixed['projection_above_interval_m']=np.maximum(0,fixed.projected_distance_m-fixed.distance_upper_m)
    save_frame('geometry_200_checks.csv',fixed)
    json_write(LOG/'geometry_checks.json',{'passed':True,'all_unique_points_geodesically_classified':len(points),
        'refined_points':len(refinements),'refinements':refinements,'land_origins':int(origin.land_or_boundary.sum()),
        'unknown_origin_groups':int(origin.coastal_group.isna().sum()),'elapsed_seconds':time.monotonic()-t})
    return origin

def summarise_phase(s,origin,check):
    rows=s.frame(MDN/'outer_complete.parquet')
    rows=rows[rows.model.isin(MODELS)].copy()
    groups=origin[origin.cohort.eq('validation')&origin.used_by_original][KEY+['group','coastal_group']]
    assert len(groups)==33971 and not groups.duplicated(KEY).any()
    rows=rows.merge(groups,on=KEY,how='left',validate='many_to_one')
    assert rows.group.notna().all() and len(rows)==33971*5
    group_order=['all','near_50km','offshore','<=10km','10_50km','>50km','land_or_boundary']
    per=[];summaries=[]
    for label in group_order:
        f=rows if label=='all' else rows[(rows.coastal_group==label)|(rows.group==label)]
        if f.empty:continue
        idmeans=f.groupby(['model','id'])[METRICS].mean().reset_index()
        size=f.groupby(['model','id']).size().rename('queries').reset_index()
        idmeans=idmeans.merge(size,on=['model','id']).assign(group=label);per.append(idmeans)
        for model,g in f.groupby('model'):
            unit=idmeans[idmeans.model==model]
            record=dict(group=label,model=model,pairs=len(g),ids=g.id.nunique(),largest_id_pair_share=float(g.groupby('id').size().max()/len(g)),interval_supported=supports_interval(g.id.nunique()))
            for metric in METRICS:
                record[metric]=float(unit[metric].mean())
                audit='audit_'+metric
                record['audit_delta_'+metric]=float(g.groupby('id')[audit].mean().mean()-record[metric]) if audit in g and g[audit].notna().all() else np.nan
            summaries.append(record)
    per=pd.concat(per,ignore_index=True);summary=pd.DataFrame(summaries)
    save_frame('coastal_per_id.csv',per)
    ids=np.sort(rows.id.unique());draws=bootstrap_draws(len(ids),5000,20261110)
    supported=summary[summary.interval_supported].group.unique()
    # One shared draw sequence; if any reported group empty, reject entire draw.
    valid=np.ones(len(draws),bool)
    for group in supported:
        present=np.isin(ids,per[per.group.eq(group)].id.unique())
        valid&=present[draws].any(axis=1)
    if not valid.all():raise RuntimeError('Shared bootstrap has an empty reported group; controlled redraw required')
    intervals=[];contrasts=[]
    for group in supported:
        block=per[per.group.eq(group)]
        samples={}
        for model in MODELS:
            a=block[block.model.eq(model)].set_index('id').reindex(ids)
            for metric in METRICS:
                v=a[metric].to_numpy();picked=v[draws]
                den=np.isfinite(picked).sum(axis=1)
                means=np.nansum(picked,axis=1)/den
                samples[model,metric]=means
                lo,hi=np.quantile(means,[.025,.975])
                intervals.append(dict(group=group,model=model,metric=metric,lower=lo,upper=hi))
        for a,b in [('MDN22','LocalGaussian'),('LocalGaussian','ExactPoint'),('MDN22','MDN1')]:
            for metric in METRICS:
                diff=samples[a,metric]-samples[b,metric];lo,hi=np.quantile(diff,[.025,.975])
                pa=summary[(summary.group==group)&(summary.model==a)].iloc[0]
                pb=summary[(summary.group==group)&(summary.model==b)].iloc[0]
                delta=pa[metric]-pb[metric]
                numerical=abs(pa['audit_delta_'+metric]-pb['audit_delta_'+metric])
                contrasts.append(dict(group=group,model_a=a,model_b=b,metric=metric,delta=delta,lower=lo,upper=hi,
                    audit_contrast_difference=numerical,numerically_direction_stable=bool(abs(delta)>numerical) if np.isfinite(numerical) else None))
        check()
    save_frame('coastal_summary.csv',summary);save_frame('coastal_intervals.csv',pd.DataFrame(intervals));save_frame('coastal_comparisons.csv',pd.DataFrame(contrasts))
    within=[]
    for model in MODELS:
        near=per[(per.group=='near_50km')&(per.model==model)].set_index('id')
        far=per[(per.group=='offshore')&(per.model==model)].set_index('id')
        common=near.index.intersection(far.index)
        for metric in METRICS:
            diff=near.loc[common,metric]-far.loc[common,metric]
            rec=dict(model=model,metric=metric,common_ids=len(common),near_minus_offshore=float(diff.mean()) if len(common) else np.nan,
                lower=np.nan,upper=np.nan,interval_supported=supports_interval(len(common)))
            if len(common)>=10:
                v=diff.reindex(ids).to_numpy();z=v[draws]
                if (np.isfinite(z).sum(axis=1)==0).any():raise RuntimeError('Empty common-ID bootstrap draw')
                lo,hi=np.quantile(np.nansum(z,axis=1)/np.isfinite(z).sum(axis=1),[.025,.975]);rec.update(lower=lo,upper=hi)
            within.append(rec)
    save_frame('within_id_coastal_difference.csv',pd.DataFrame(within))
    np.save(RES/'bootstrap_draws.npy',draws)
    json_write(LOG/'scoring_reuse.json',{'passed':True,'models':MODELS,'queries_per_model':33971,'ids':45,'new_model_predictions':0,'new_ES_integrations':0,'bootstrap_draws':5000,'bootstrap_seed':20261110,'empty_draw_retries':0})
    print(summary[['group','model','ids','pairs','energy_km','h90','area90_km2','land_mass']].to_string(index=False),flush=True)

def main():
    s,roster=start()
    try:
      with stage('coastal') as check:
        if (RES/'coastal_groups.parquet').exists() and (LOG/'geometry_checks.json').exists():
            origin=pd.read_parquet(RES/'coastal_groups.parquet')
        else:origin=geographic_phase(s,check)
        summarise_phase(s,origin,check)
    finally:s.save()

if __name__=='__main__':main()
