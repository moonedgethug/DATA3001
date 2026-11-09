"""Full numerical gates, independent-replica comparison and scientific readout."""
import time
STARTED=time.monotonic()
import json
import sys
import numpy as np
import pandas as pd

from data3001.modelling.common.runtime import save_frame,save_json
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_inputs as inp
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_numerics as num
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_analysis as analysis
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_full as full


def precision(table,expected_cases=33971):
    groups={model:table[table.model.eq(model)].sort_values('query_position').reset_index(drop=True) for model in num.MODELS}
    roster=groups['ExactPoint'][['query_position','id']].to_numpy()
    if len(roster)!=expected_cases or len(np.unique(roster[:,0]))!=expected_cases:raise ValueError('Incomplete primary roster')
    for model,group in groups.items():full.validate_keys(group[['query_position','id']],roster)
    w=num.id_weights(roster[:,1]);checks={};regions={}
    for model,group in groups.items():
        if not np.isfinite(group[['energy_km','variance','h90','area90_km2','mass_radius','mass_diagnostic']].to_numpy()).all():raise ValueError('Nonfinite primary metrics')
        if (group.variance<0).any():raise ValueError('Negative numerical variance')
        regions[model]=num.region_gate(group,w)
    for base in ['ExactPoint','EndpointCI']:
        baseline=float(w@groups[base].energy_km)
        se=3*np.sqrt(float(w*w@(groups['LocalGaussian'].variance.to_numpy()+groups[base].variance.to_numpy())))
        checks[base]=dict(three_se_km=se,threshold_km=.0001*baseline,passed=bool(se<=.0001*baseline))
    return dict(passed=all(v['passed'] for v in checks.values()) and all(v['passed'] for v in regions.values()),
        cases=expected_cases,ids=len(np.unique(roster[:,1])),energy=checks,regions=regions,
        degenerate_region_cases={m:int((g['rank']<2).sum()) for m,g in groups.items()})


def read_stage(run,stage):
    files=sorted((run['results']/stage).glob('*.parquet'))
    table=pd.concat([pd.read_parquet(f) for f in files],ignore_index=True)
    if len(table)!=33971*3:raise ValueError('Missing full stage results: '+stage)
    return table.sort_values(['query_position','model']).reset_index(drop=True)


def independent_checks(primary,replica):
    full.validate_keys(primary[['query_position','model']].to_numpy(),replica[['query_position','model']].to_numpy())
    pg={m:primary[primary.model.eq(m)].sort_values('query_position') for m in num.MODELS}
    rg={m:replica[replica.model.eq(m)].sort_values('query_position') for m in num.MODELS}
    w=num.id_weights(pg['ExactPoint'].id.to_numpy());models={};contrasts={}
    for m in num.MODELS:
        p,r=pg[m],rg[m];delta=r.energy_km.to_numpy()-p.energy_km.to_numpy()
        es=float(w@delta);three_se=float(3*np.sqrt(w*w@(r.variance.to_numpy()+p.variance.to_numpy())))
        h=float(w@r.hit_disagreement);a=abs(float(w@(r.area90_km2.to_numpy()-p.area90_km2.to_numpy())))/float(w@p.area90_km2)
        models[m]=dict(energy_replication_drift_km=es,energy_difference_three_se_km=three_se,
            hit_disagreement=h,mean_area_relative_drift=a,passed=bool(abs(es)<=three_se and h<=.001 and a<=.005))
    for b in ['ExactPoint','EndpointCI']:
        pdelta=pg['LocalGaussian'].energy_km.to_numpy()-pg[b].energy_km.to_numpy()
        rdelta=rg['LocalGaussian'].energy_km.to_numpy()-rg[b].energy_km.to_numpy()
        effect=float(w@pdelta);drift=float(w@(rdelta-pdelta))
        rse=3*np.sqrt(float(w*w@(rg['LocalGaussian'].variance.to_numpy()+rg[b].variance.to_numpy())))
        baseline=float(w@pg[b].energy_km)
        totalvar=pg['LocalGaussian'].variance.to_numpy()+pg[b].variance.to_numpy()+rg['LocalGaussian'].variance.to_numpy()+rg[b].variance.to_numpy()
        total3=3*np.sqrt(float(w*w@totalvar))
        contrasts[b]=dict(primary_es_delta_km=effect,replica_es_delta_km=float(w@rdelta),contrast_drift_km=drift,
            replica_three_se_km=rse,threshold_km=.0001*baseline,difference_three_se_km=total3,
            passed=bool(rse<=.0001*baseline and abs(drift)<=total3),
            es_improvement_numerically_resolved=bool(effect<0 and abs(drift)<=.1*abs(effect)))
    selected=rg['LocalGaussian'][rg['LocalGaussian'].iid_energy_km.notna()].copy()
    if len(selected)!=128:raise ValueError('Fixed independent IID audit roster incomplete')
    wi=num.id_weights(selected.id.to_numpy());d=selected.iid_energy_km.to_numpy()-selected.energy_km.to_numpy()
    three=3*np.sqrt(float(wi*wi@(selected.iid_variance.to_numpy()+selected.variance.to_numpy())))
    iid=dict(cases=128,weighted_drift_km=float(wi@d),three_se_km=three,passed=bool(abs(wi@d)<=three))
    if not replica.exhaustive_donor_check.groupby(replica.query_position).first().sum()==128:raise ValueError('Exhaustive audit case count mismatch')
    return dict(passed=all(x['passed'] for x in models.values()) and all(x['passed'] for x in contrasts.values()) and iid['passed'],
        models=models,contrasts=contrasts,iid=iid,parameters_reconstructed=33971,
        covariance_max_abs_error_km2=float(replica.parameter_max_error.max()))


def claim_resolution(primary,replica,comparisons,checks,primary_precision):
    p={m:primary[primary.model.eq(m)].sort_values('query_position') for m in num.MODELS}
    r={m:replica[replica.model.eq(m)].sort_values('query_position') for m in num.MODELS}
    w=num.id_weights(p['ExactPoint'].id.to_numpy());result=[]
    for row in comparisons.to_dict('records'):
        base=row['baseline'];g=p['LocalGaussian'];b=p[base]
        primary_disagree=float(w@(g.hit_disagreement.to_numpy()+b.hit_disagreement.to_numpy()))
        audit_disagree=checks['models']['LocalGaussian']['hit_disagreement']+checks['models'][base]['hit_disagreement']
        hit_uncertainty=max(primary_disagree,audit_disagree)
        audit_ratio=float(w@r['LocalGaussian'].area90_km2)/float(w@r[base].area90_km2)
        primary_ratio=float(w@g.area_replica_km2)/float(w@b.area_replica_km2)
        area_drift=max(abs(audit_ratio-row['area_ratio']),abs(primary_ratio-row['area_ratio']))
        h_resolved=bool(hit_uncertainty<=.1*row['hit_delta']) if row['hit_delta']>0 else bool(row['hit_delta']==0 and hit_uncertainty==0)
        a_resolved=bool(area_drift<=.1*(1-row['area_ratio'])) if row['area_ratio']<1 else bool(row['area_ratio']==1 and area_drift==0)
        land_se=3*np.sqrt(float(w*w@(g.land_variance.to_numpy()+b.land_variance.to_numpy())))
        outside_se=3*np.sqrt(float(w*w@(g.outside_variance.to_numpy()+b.outside_variance.to_numpy())))
        geo_resolved=bool(row['land_delta']+land_se<=.01 and row['outside_delta']+outside_se<=.01)
        es_resolved=checks['contrasts'][base]['es_improvement_numerically_resolved']
        rank_ok=not primary_precision['degenerate_region_cases']['LocalGaussian'] and not primary_precision['degenerate_region_cases'][base]
        row.update(hit_numerical_uncertainty=hit_uncertainty,area_ratio_numerical_drift=area_drift,
            land_difference_three_se=land_se,outside_difference_three_se=outside_se,
            es_improvement_numerically_resolved=es_resolved,hit_direction_resolved=h_resolved,
            area_direction_resolved=a_resolved,geographic_guardrails_resolved=geo_resolved,
            regions_nondegenerate=bool(rank_ok))
        row['eligible']=bool(row['eligible'] and h_resolved and a_resolved and geo_resolved and es_resolved and rank_ok)
        result.append(row)
    primary_ok=bool(result[0]['es_benefit'] and result[0]['es_improvement_numerically_resolved'])
    for row in result:row['superiority_claim_allowed']=bool(row['es_benefit'] and row['es_improvement_numerically_resolved'] and (row['baseline']=='ExactPoint' or primary_ok))
    return pd.DataFrame(result)


def verify(name,stage):
    paths,run,cfg,approval,guard=inp.context(name)
    phase='formal' if stage=='primary' else 'audit';budget=inp.Budget(run,cfg,phase,STARTED)
    completed=False
    try:
        inp.freeze_sources(paths,run,'verify_'+stage)
        primary=read_stage(run,'scores');prec=precision(primary)
        if prec['ids']!=45:raise ValueError('Outer ID denominator changed')
        if stage=='primary':
            save_json(paths,run['provenance']/'primary_numerical_checks.json',full.json_ready(prec))
            save_frame(paths,run['results']/'metrics.parquet',primary)
            if not prec['passed']:raise ValueError('Full primary numerical gate failed; no extra integration level authorised')
        else:
            replica=read_stage(run,'audit');checks=independent_checks(primary,replica)
            save_json(paths,run['provenance']/'full_independent_checks.json',full.json_ready(checks))
            if not checks['passed'] or not prec['passed']:raise ValueError('Independent numerical gates failed; scientific comparison remains unresolved')
            summary,per_id,comparison,loo=analysis.compare(primary,numerical_pass=True)
            comparison=claim_resolution(primary,replica,comparison,checks,prec)
            save_frame(paths,run['results']/'summary.csv',summary.reset_index())
            save_frame(paths,run['results']/'per_id.csv',per_id)
            save_frame(paths,run['results']/'comparisons.csv',comparison)
            save_frame(paths,run['results']/'leave_one_id_out.csv',loo)
            strata=[]
            primary['year']=pd.to_datetime(primary.origin_time_UTC,utc=True).dt.year
            primary['support_stratum']=pd.cut(primary.independent_ids,[0,25,50,100,np.inf],labels=['1–25','26–50','51–100','101+'])
            primary['id_share_stratum']=pd.cut(primary.largest_id_share,[0,.1,.25,.5,1],include_lowest=True)
            for factor in ['year','support_stratum','id_share_stratum']:
                for value,group in primary.groupby(factor,observed=True):
                    means,_=analysis.summarize(group)
                    for model,row in means.iterrows():strata.append(dict(factor=factor,stratum=str(value),model=model,cases=len(group[group.model.eq(model)]),ids=group.id.nunique(),**row.to_dict()))
            save_frame(paths,run['results']/'descriptive_strata.csv',pd.DataFrame(strata))
            quantiles=[]
            for model,group in primary.groupby('model'):
                a=group.area90_km2.to_numpy();w=num.id_weights(group.id.to_numpy());order=np.argsort(a);c=np.cumsum(w[order])
                quantiles.append(dict(model=model,**{f'weighted_area_q{int(q*100)}':float(a[order[np.searchsorted(c,q)]]) for q in [.1,.5,.9]}))
            save_frame(paths,run['results']/'area_quantiles.csv',pd.DataFrame(quantiles))
            passed=bool(comparison.eligible.all())
            save_json(paths,run['provenance']/'scientific_decision.json',dict(engineering_complete=True,
                numerical_gates_passed=True,quality_non_degrading_improvement=passed,
                candidate_for_default_discussion=passed,model_default_changed=False,
                decision='SUPPORTED_IMPROVEMENT' if passed else 'NO_SUPPORTED_NONDEGRADING_IMPROVEMENT',
                primary_comparison='LocalGaussian minus ExactPoint',companion='LocalGaussian minus EndpointCI',
                outer_cases=33971,outer_ids=45,development_evidence_only=True,final_test_access=False))
        inp.verify(approval);budget.check();completed=True
        print(json.dumps(dict(stage=stage,completed=True,numerical_pass=True)),flush=True)
    finally:budget.finish(paths,'verify_'+stage,completed,guard)


if __name__=='__main__':verify(sys.argv[1],sys.argv[2])
