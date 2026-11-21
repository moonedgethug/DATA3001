"""Prespecified paired, equal-drifter E9 summaries. No model selection."""
import json
import numpy as np
import pandas as pd
from data3001.modelling.common.runtime import save_json, save_frame
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_formal_io as fio

METRICS=['energy_km','h90','area90_km2']
CONTRASTS=[('SeasonalEndpointCI','AnnualEndpointCI'),('SeasonalExactPoint','AnnualExactPoint'),
           ('SeasonalEndpointCI','SeasonalExactPoint'),('AnnualEndpointCI','AnnualExactPoint'),
           ('SeasonalEndpointCI','AnnualExactPoint')]


def weighted_quantile(values,weights,q):
    order=np.argsort(np.asarray(values));return float(np.asarray(values)[order[np.searchsorted(np.cumsum(np.asarray(weights)[order]),q*sum(weights))]])


def infer(cases):
    per_id=cases.groupby(['id','model'],sort=True)[METRICS].mean().reset_index()
    ids=np.sort(cases.id.unique())
    stack=np.array([per_id[per_id.model.eq(m)].set_index('id').loc[ids,METRICS].to_numpy() for m in fio.MODELS]).transpose(1,0,2)
    draws=np.random.Generator(np.random.PCG64(20261106)).integers(len(ids),size=(10000,len(ids)))
    boot=stack[draws].mean(axis=1);means=stack.mean(axis=0);rows=[]
    for candidate,reference in CONTRASTS:
        a,b=fio.MODELS.index(candidate),fio.MODELS.index(reference)
        delta=means[a]-means[b];sample=boot[:,a]-boot[:,b]
        ratio=means[a,2]/means[b,2];ratios=boot[:,a,2]/boot[:,b,2]
        row=dict(candidate=candidate,reference=reference,es_difference_km=delta[0],
            es_relative_difference=delta[0]/means[b,0],h90_difference=delta[1],area_difference_km2=delta[2],area_ratio=ratio)
        for metric,j in [('es',0),('h90',1)]:
            lo,hi=np.quantile(sample[:,j],[.025,.975]);row[metric+'_low']=lo;row[metric+'_high']=hi
        row['area_ratio_low'],row['area_ratio_high']=np.quantile(ratios,[.025,.975])
        row['supported_es_reduction']=bool(row['es_high']<0)
        row['practical_es_reduction']=bool(row['es_relative_difference']<=-.001)
        row['observed_no_degradation']=bool(row['h90_difference']>=0 and row['area_ratio']<=1)
        row['interval_guardrails']=bool(row['h90_low']>=-.01 and row['area_ratio_high']<=1.02)
        row['statistical_quality_criteria']=bool(all(row[n] for n in ['supported_es_reduction','practical_es_reduction','observed_no_degradation','interval_guardrails']))
        rows.append(row)
    return per_id,stack,boot,pd.DataFrame(rows)


def precision(cases):
    by={m:g.sort_values('query_position') for m,g in cases.groupby('model')};rows=[]
    for a,b in CONTRASTS:
        ca,cb=by[a],by[b];w=ca.weight.to_numpy()
        same_pool=a.startswith('Annual')==b.startswith('Annual')
        if same_pool:variance=ca.ci_delta_mc_se.to_numpy()**2
        else:
            variance=ca.energy_mc_se.to_numpy()**2+cb.energy_mc_se.to_numpy()**2
            fallback=ca.seasonal_fallback.to_numpy()
            variance[fallback]=0 if a.endswith('EndpointCI')==b.endswith('EndpointCI') else ca.ci_delta_mc_se.to_numpy()[fallback]**2
        se=float(np.sqrt(w*w@variance));ref=float(w@cb.energy_km)
        rows.append(dict(candidate=a,reference=b,three_se_km=3*se,threshold_km=.0001*ref,passed=3*se<=.0001*ref))
    return pd.DataFrame(rows)


def analyze(paths,run,cases):
    per_id,stack,boot,contrasts=infer(cases)
    save_frame(paths,run['results']/'per_id_scores.csv',per_id)
    save_frame(paths,run['results']/'contrasts.csv',contrasts)
    save_frame(paths,run['results']/'energy_precision.csv',precision(cases))
    extra=['mass90','land_mass','outside_D_mass','land_area_km2','wet_area_km2','outside_D_area_km2','error_fallback_mass']
    summaries=[]
    for mi,name in enumerate(fio.MODELS):
        g=cases[cases.model.eq(name)].sort_values('query_position');w=g.weight.to_numpy();assert abs(w.sum()-1)<1e-12
        row=dict(model=name,cases=len(g),IDs=g.id.nunique())
        for col in METRICS+extra:row[col]=float(w@g[col])
        for j,col in enumerate(METRICS):
            row[col+'_low'],row[col+'_high']=np.quantile(boot[:,mi,j],[.025,.975])
        for q in [.1,.5,.9]:row[f'area_q{int(q*100)}']=weighted_quantile(g.area90_km2,w,q)
        row['h90_minus_nominal']=row['h90']-.9;row['degenerate_weight']=float(w@(g['rank'].to_numpy()<2))
        summaries.append(row)
    save_frame(paths,run['results']/'summary.csv',pd.DataFrame(summaries))
    subgroup=[]
    for col in ['year','majority_season','cross_season','seasonal_fallback']:
        for (name,value),g in cases.groupby(['model',col],sort=True):
            w=g.weight.to_numpy();share=float(w.sum());w=w/share
            subgroup.append(dict(model=name,group=col,value=value,cases=len(g),IDs=g.id.nunique(),evaluation_weight=share,
                                 **{metric:float(w@g[metric]) for metric in METRICS}))
    support_bin=pd.cut(cases.donor_IDs,[0,10,30,100,np.inf],labels=['1-10','11-30','31-100','101+'])
    for (name,value),g in cases.groupby([cases.model,support_bin],observed=True):
        w=g.weight.to_numpy();share=float(w.sum());w=w/share
        subgroup.append(dict(model=name,group='donor_IDs',value=str(value),cases=len(g),IDs=g.id.nunique(),evaluation_weight=share,
                             **{metric:float(w@g[metric]) for metric in METRICS}))
    save_frame(paths,run['results']/'subgroups.csv',pd.DataFrame(subgroup))
    loo=[];ids=np.sort(cases.id.unique())
    for i,id_value in enumerate(ids):
        means=(stack.sum(axis=0)-stack[i])/(len(ids)-1)
        for a,b in CONTRASTS[:2]:
            x,y=fio.MODELS.index(a),fio.MODELS.index(b)
            loo.append(dict(omitted_id=int(id_value),candidate=a,reference=b,es_difference_km=means[x,0]-means[y,0],
                            h90_difference=means[x,1]-means[y,1],area_ratio=means[x,2]/means[y,2]))
    save_frame(paths,run['results']/'leave_one_id_out.csv',pd.DataFrame(loo))
    support=pd.read_parquet(run['results']/'support.parquet');roster=pd.read_parquet(run['results']/'roster.parquet')
    fallback=[]
    for pool,g in support.groupby('pool'):
        g=g.sort_values('query_position');mask=g.seasonal_fallback.to_numpy(bool);w=roster.weight.to_numpy()
        fallback.append(dict(pool=pool,queries=len(g),seasonal_fallback_count=int(mask.sum()),seasonal_fallback_fraction=float(mask.mean()),
            seasonal_fallback_weight=float(w@mask),seasonal_fallback_IDs=int(roster.loc[mask,'id'].nunique()),
            weighted_error_fallback_mass=float(w@g.error_fallback_mass),selected_donor_occurrences=int(g.donors.sum()),
            error_fallback_occurrences=int(g.error_fallback_pairs.sum()),overlap_weighted_error_mass=float(w@(mask*g.error_fallback_mass.to_numpy())),
            donor_pairs_min=int(g.donors.min()),donor_pairs_max=int(g.donors.max()),donor_IDs_min=int(g.donor_IDs.min()),donor_IDs_max=int(g.donor_IDs.max())))
    save_frame(paths,run['results']/'fallback_summary.csv',pd.DataFrame(fallback))
    save_json(paths,run['provenance']/'analysis.json',dict(complete_cases=True,per_case_records=len(cases),IDs=45,
        evaluation='Equal times within ID, then equal IDs; original weights renormalized in subgroups',bootstrap_draws=10000,
        bootstrap_seed=20261106,season_claims=2,nominal_family_alpha=.05,independent_audit_pending=True,final_test_access=False))
