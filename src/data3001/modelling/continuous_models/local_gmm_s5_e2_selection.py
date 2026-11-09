"""Predeclared temporal/whole-ID complexity selection. No model fitting."""
import numpy as np
import pandas as pd
from . import local_gmm_s5_e2 as model


def pooled_id_means(table, field):
    per_role=table.groupby(['id','role','model'])[field].mean()
    return per_role.groupby(['id','model']).mean().unstack('model').sort_index()


def query_weights(table):
    """One vote per ID, divided across its roles, then times in each role."""
    n=table.groupby(['id','role'])['id'].transform('size').to_numpy()
    roles=table.groupby('id')['role'].transform('nunique').to_numpy()
    return 1/(table.id.nunique()*roles*n)


def paired_numerics(table, first, second):
    key=['role','id','query_position']
    a=table[table.model.eq(first)].sort_values(key)
    b=table[table.model.eq(second)].sort_values(key)
    if not np.array_equal(a[key].to_numpy(),b[key].to_numpy()):raise ValueError('Unmatched candidate rosters')
    w=query_weights(a)
    if 'replicate_means' in table:
        diff=np.asarray(a.replicate_means.tolist())-np.asarray(b.replicate_means.tolist())
        variances=diff.var(axis=1,ddof=1)/8
    else:variances=a.variance.to_numpy()+b.variance.to_numpy()
    return float(3*np.sqrt(w*w@variances))


def select_k(inner_metrics, diagnostics=None, spec=None):
    cfg={} if spec is None else spec
    t=inner_metrics.copy(); roles=sorted(t.role.unique())
    if roles!=['C_T0','C_T1'] or set(t.model)!=set([1,2,3]):raise ValueError('All registered roles/candidates required')
    ids=pooled_id_means(t,'energy_km'); scores=ids.mean()
    if ids.isna().any().any():raise ValueError('Unequal ID support across candidates')
    role_scores=t.groupby(['role','id','model']).energy_km.mean().groupby(['role','model']).mean()
    fallback=t.groupby(['role','id','model']).fallback.mean().groupby(['role','model']).mean()
    eligible=[1]; reasons={1:[]}; numerical={}
    for k in [2,3]:
        why=[]
        for role in roles:
            sub=t[t.role.eq(role)];se=paired_numerics(sub,k,1)
            numerical[f'{role}:{k}-1']=se
            base=float(role_scores.loc[(role,1)]);delta=float(role_scores.loc[(role,k)]-base)
            if se>.0001*base:raise ArithmeticError('Basic inner ES precision failed')
            if delta>0 or (delta!=0 and se>.1*abs(delta)):why.append(role+':ES_NOT_STABLE')
            if fallback.loc[(role,k)]>cfg.get('max_fallback',.05):why.append(role+':FALLBACK')
        effect=float(scores[1]-scores[k]);se=paired_numerics(t,k,1)
        numerical[f'pooled:{k}-1']=se
        if effect<.001*scores[1] or se>.1*abs(effect):why.append('INSUFFICIENT_POOLED_GAIN')
        reasons[k]=why
        if not why:eligible.append(k)
    # Numerical ties are resolved toward simplicity, never a favourable stream.
    best=eligible[0]
    for k in eligible[1:]:
        err=paired_numerics(t,k,best)
        if scores[k]<scores[best]-err:best=k
    rng=np.random.default_rng(cfg.get('selection_seed',20261110))
    draws=rng.integers(len(ids),size=(cfg.get('bootstrap_draws',10000),len(ids)))
    one_se={};chosen=best
    for k in sorted(eligible):
        differences=(ids[k]-ids[best]).to_numpy()
        se=float(differences[draws].mean(axis=1).std(ddof=1))
        one_se[k]=dict(mean_difference=float(differences.mean()),paired_bootstrap_se=se)
        if differences.mean()<=se:
            chosen=k;break
    return dict(provisional_k=int(chosen),best_es_k=int(best),eligible=eligible,
        ineligibility={str(k):v for k,v in reasons.items()},pooled_scores={str(k):float(v) for k,v in scores.items()},
        role_scores={f'{a}:{b}':float(v) for (a,b),v in role_scores.items()},
        fallback_rates={f'{a}:{b}':float(v) for (a,b),v in fallback.items()},
        paired_numerical_three_se=numerical,one_se_rule=one_se,unique_validation_ids=len(ids))


def apply_quality(choice, region_metrics):
    k=choice['provisional_k']
    if k==1:return dict(choice,selected_k=1,quality_gate='IDENTICAL_SINGLE_GAUSSIAN')
    fields=['h90','area90_km2','land_mass','outside_D_mass','hit_disagreement','area_replica_km2','land_variance','outside_variance']
    means=region_metrics.groupby(['role','id','model'])[fields].mean().groupby(['role','model']).mean()
    gates={}
    for role in ['C_T0','C_T1']:
        a=means.loc[(role,k)];b=means.loc[(role,1)]
        hit=float(a.h90-b.h90);area=float(a.area90_km2/b.area90_km2-1)
        hit_error=float(a.hit_disagreement+b.hit_disagreement)
        area_error=float(abs(a.area_replica_km2-a.area90_km2)/a.area90_km2+abs(b.area_replica_km2-b.area90_km2)/b.area90_km2)
        sub=region_metrics[region_metrics.role.eq(role)]
        geography=geographic_guard(sub,k,1)
        passed=(hit>=0 and area<=0 and geography['passed'])
        # If no membership changes between numerical reconstructions, exact zero is resolvable.
        passed=passed and hit_error<=.1*abs(hit) and area_error<=.1*abs(area)
        gates[role]=dict(passed=bool(passed),hit_difference=hit,area_ratio=1+area,
            hit_numerical_disagreement=hit_error,area_numerical_relative_drift=area_error,geography=geography)
    return dict(choice,selected_k=k if all(g['passed'] for g in gates.values()) else 1,quality_gate=gates)


def geographic_guard(table, candidate, baseline):
    key=['id']+(['query_position'] if 'query_position' in table else [])
    a=table[table.model.eq(candidate)].sort_values(key);b=table[table.model.eq(baseline)].sort_values(key)
    if not np.array_equal(a[key].to_numpy(),b[key].to_numpy()):raise ValueError('Geographic guard roster mismatch')
    _,inv,counts=np.unique(a.id,return_inverse=True,return_counts=True);w=1/(len(counts)*counts[inv])
    result={}
    for field,variance in [('land_mass','land_variance'),('outside_D_mass','outside_variance')]:
        delta=float(w@(a[field].to_numpy()-b[field].to_numpy()))
        # Shared streams may correlate indicators; sum of SD is a safe covariance bound.
        var=(np.sqrt(a[variance].to_numpy())+np.sqrt(b[variance].to_numpy()))**2
        error=float(3*np.sqrt(w*w@var))
        result[field]=dict(delta=delta,three_se_bound=error,passed=delta+error<=.01)
    result['passed']=all(r['passed'] for r in result.values())
    return result
