"""S3 E2: unchanged frequency references with fitting-ID adaptive local borrowing."""
from dataclasses import dataclass
import hashlib
import json
import numpy as np
import pandas as pd
from data3001.modelling.baselines.adaptive_b2_b1 import Bases, fit_bases as fit_raw, borrowing_weight
from data3001.modelling.baselines.empirical_b2 import checked_ids
from data3001.modelling.baselines.drifter_shrinkage_e3 import (
    METRICS, UNIT, GRID, TOL, summarize_units, diagnostic_scores as raw_diagnostic_scores,
    score_units as raw_score_units, attach_primary_weights, metric_columns as raw_metric_columns,
)
from data3001.modelling.common.qualified_count_inputs import ROW, DEST, HORIZONS
from data3001.modelling.common.prediction_regions import checked_distribution, probability_region

MODELS=('B2','Fixed','Adaptive','LocalEndpoint','LocalEndpointAdaptive')
GAMMAS=(0.,.5,1.,2.)
IDENTITY=['horizon_days','model','parameter_a','parameter_gamma']


def neighbours(origin):
    y,x=divmod(int(origin),360)
    return sorted((y+dy)*360+(x+dx)%360 for dy in (-1,0,1) for dx in (-1,0,1)
                  if (dx or dy) and 0<=y+dy<180)


@dataclass
class LocalBases(Bases):
    endpoint_rows: dict
    neighbour_support: pd.DataFrame
    support_lookup: dict
    ratio_medians: dict


def fit_bases(counts,training_ids,origins,destinations):
    base=fit_raw(counts,training_ids,origins,destinations)
    local=counts[counts.id.isin(base.b2.training_ids)]
    endpoint={};rows=[]
    for (h,i),p in base.rows.items():
        own=local[local.horizon_days.eq(h)&local.origin_cell_1.eq(i)]
        donor=local[local.horizon_days.eq(h)&local.origin_cell_1.isin(neighbours(i))]
        own_ids=set(map(int,own.id));donor_ids=set(map(int,donor.id));L=len(own_ids);M=len(donor_ids)
        n=int(donor.pair_count.sum());q=np.zeros(len(base.states))
        if n:
            for j,v in donor.groupby(DEST).pair_count.sum().items():q[base.index[j]]=v/n
        else:q=p.copy()
        checked_distribution(q,base.states);endpoint[(h,i)]=q
        rows.append(dict(horizon_days=h,origin_cell_1=i,local_ids=L,neighbour_ids=M,
            local_ID_set=json.dumps(sorted(own_ids)),neighbour_ID_set=json.dumps(sorted(donor_ids)),
            local_pairs=int(own.pair_count.sum()),neighbour_pairs=n,neighbour_cells=donor.origin_cell_1.nunique(),
            overlap_local_neighbour_IDs=len(own_ids&donor_ids),jaccard_overlap=len(own_ids&donor_ids)/len(own_ids|donor_ids),
            local_largest_ID_share=float(own.groupby('id').pair_count.sum().max()/own.pair_count.sum()),
            neighbour_largest_ID_share=float(donor.groupby('id').pair_count.sum().max()/n) if n else 0.,
            support_ratio=M/L,no_neighbour=M==0))
    support=pd.DataFrame(rows);medians={}
    for h in HORIZONS:
        active=support.horizon_days.eq(h);good=support.loc[active&support.neighbour_ids.gt(0),'support_ratio']
        median=float(good.median()) if len(good) else 1.;medians[h]=median
        support.loc[active,'median_support_ratio']=median
        support.loc[active,'normalised_support_ratio']=support.loc[active,'support_ratio']/median
        support.loc[active,'no_positive_support_ratio']=len(good)==0
    lookup={tuple(r[k] for k in ROW):r for r in support.to_dict('records')}
    return LocalBases(**vars(base),endpoint_rows=endpoint,neighbour_support=support,support_lookup=lookup,ratio_medians=medians)


def local_weight(a,gamma,L,M,median):
    if not np.isfinite([a,gamma,L,M,median]).all() or not 0<=a<=1 or gamma<0 or L<=0 or M<0 or median<=0:
        raise ValueError('Invalid local adaptive weight/support')
    if M==0 or a==0:return 0.
    if a==1:return 1.
    if gamma==0:return float(a)
    z=(M/L)/median
    # Log odds avoid intermediate overflow without clipping the mathematical rule.
    logodds=np.log(a)-np.log1p(-a)+gamma*np.log(z)
    if logodds>=0:return float(1/(1+np.exp(-logodds)))
    e=np.exp(logodds);return float(e/(1+e))


def applied_weight(base,h,i,model,a,gamma=0.):
    if model=='B2':return 0.
    if model=='Adaptive':
        meta=base.support_lookup[(h,i)]
        return borrowing_weight(model,a,meta['local_pairs'],base.medians[h])
    if model=='Fixed':return float(a)
    meta=base.support_lookup[(h,i)]
    if model=='LocalEndpoint':return 0. if meta['no_neighbour'] else float(a)
    return local_weight(a,gamma,meta['local_ids'],meta['neighbour_ids'],meta['median_support_ratio'])


def vector(base,h,origin,model,a=0.,gamma=0.):
    if model not in MODELS or not np.isfinite([a,gamma]).all() or not 0<=a<=1 or gamma<0:
        raise ValueError('Invalid S3 E2 model/parameter')
    key=(h,origin)
    if key not in base.rows:return None
    p=base.rows[key]
    if model=='B2':return p
    q=base.references[h] if model in ('Fixed','Adaptive') else base.endpoint_rows[key]
    weight=applied_weight(base,h,origin,model,a,gamma)
    return (1-weight)*p+weight*q


def specifications():
    return [('B2',0.,0.),*[(m,a,0.) for m in MODELS[1:4] for a in GRID],
            *[('LocalEndpointAdaptive',a,g) for a in GRID for g in GAMMAS]]


def candidate_units(base,counts,evaluation_ids):
    ids=checked_ids(evaluation_ids)
    if set(ids)&set(base.b2.training_ids): raise ValueError('Candidate ID leakage')
    result=[];spec=specifications()
    for (h,o),g in counts[counts.id.isin(ids)].groupby(ROW,sort=True):
        ident=np.sort(g.id.unique());n=g.groupby('id').pair_count.sum().reindex(ident).to_numpy()
        common=dict(horizon_days=h,origin_cell_1=o,id=ident,eligible_pairs=n)
        if (h,o) not in base.rows:
            result.extend(pd.DataFrame({**common,'model':m,'parameter_a':a,'parameter_gamma':gamma,'supported':False,**{k:np.nan for k in METRICS}}) for m,a,gamma in spec)
            continue
        observed=np.zeros((len(ident),len(base.states)));ix={d:k for k,d in enumerate(ident)}
        for r in g.itertuples(index=False): observed[ix[r.id],base.index[r.destination_cell_1]]=r.pair_count
        observed/=n[:,None]
        vectors=np.array([vector(base,h,o,m,a,gamma) for m,a,gamma in spec])
        regions=np.array([probability_region(p,base.states)[0] for p in vectors])
        bs=1+np.square(vectors).sum(axis=1)[None,:]-2*observed@vectors.T
        hit=observed@regions.T.astype(float);size=np.sum(regions&(base.states[None,:]>=0),axis=1)
        for k,(m,a,gamma) in enumerate(spec):
            result.append(pd.DataFrame({**common,'model':m,'parameter_a':a,'parameter_gamma':gamma,'supported':True,
                'brier':bs[:,k],'region90_cells':size[k],'region90_hit':hit[:,k]}))
    if not result: raise ValueError('Empty candidate evaluation')
    return pd.concat(result,ignore_index=True)


def select_parameters(units):
    pool=summarize_units(units,IDENTITY);pool['selected']=False;pool['within_tie']=False;chosen=[]
    for h in HORIZONS:
        section=pool[pool.horizon_days.eq(h)]
        if section.brier.isna().any() or any(section[c].nunique()!=1 for c in ['eligible_pairs','evaluable_pairs','evaluable_id_cells','evaluable_cells']): raise ValueError('Candidate availability mismatch')
        for model in MODELS[1:]:
            g=section[section.model.eq(model)]
            expected={(a,gamma) for m,a,gamma in specifications() if m==model}
            if set(g[['parameter_a','parameter_gamma']].itertuples(index=False,name=None))!=expected: raise ValueError('Incomplete S3 E2 grid')
            tied=g[g.brier<=g.brier.min()+TOL];best=tied.sort_values(['parameter_gamma','parameter_a']).iloc[0]
            pool.loc[tied.index,'within_tie']=True;pool.loc[best.name,'selected']=True
            chosen.append({**best.to_dict(),'selected':True,'within_tie':True,'selection_status':'primary_Brier_then_smaller_gamma_then_smaller_a'})
    return pd.DataFrame(chosen),pool



def forecasts(base,model,selected):
    params=selected[selected.model.eq(model)].set_index('horizon_days') if model!='B2' else None
    vectors={};rows=[]
    for r in base.b2.support.itertuples(index=False):
        h,i=r.horizon_days,r.origin_cell_1
        a,gamma=(0.,0.) if model=='B2' else (float(params.loc[h,'parameter_a']),float(params.loc[h,'parameter_gamma']))
        p=vector(base,h,i,model,a,gamma)
        row={**r._asdict(),'model':model,'parameter_a':a,'parameter_gamma':gamma,'median_pair_count':base.medians[h],
             'borrowing_weight':np.nan,'effective_borrowing_weight':np.nan,'total_B2_weight':np.nan,
             'adaptation_total_variation':np.nan}
        if p is not None:
            checked_distribution(p,base.states);vectors[(h,i)]=p;row.update(base.support_lookup[(h,i)])
            weight=applied_weight(base,h,i,model,a,gamma)
            constant=vector(base,h,i,'LocalEndpoint',a)
            row.update(borrowing_weight=weight,effective_borrowing_weight=weight,total_B2_weight=1-weight,
                adaptation_total_variation=float(np.abs(p-constant).sum()/2) if model=='LocalEndpointAdaptive' else 0.)
        rows.append(row)
    return vectors,pd.DataFrame(rows)


def diagnostic_scores(base,vectors,counts,ids,model):
    scores,boundaries=raw_diagnostic_scores(base,vectors,counts,ids,model)
    scores['outside_local_union']=np.nan
    for key,ix in scores.groupby(ROW).groups.items():
        if key in vectors:
            support=(base.rows[key]>0)|(base.endpoint_rows[key]>0)
            scores.loc[ix,'outside_local_union']=(~scores.loc[ix,DEST].isin(base.states[support])).astype(float)
    scores['outside_local_union']=scores.outside_local_union.astype(float)
    return scores,boundaries


def metric_columns(scores):return [*raw_metric_columns(scores),*(['outside_local_union'] if 'outside_local_union' in scores else [])]


def score_units(scores):
    # Existing sufficient-score aggregation accepts an explicit metric list.
    units=raw_score_units(scores)
    extra=scores.assign(value=scores.pair_count*scores.outside_local_union.fillna(0),
                        mass=scores.pair_count*scores.outside_local_union.notna()).groupby(['model',*UNIT]).agg(
                            value=('value','sum'),mass=('mass','sum'),n=('pair_count','sum')).reset_index()
    extra['outside_local_union']=extra.value/extra.n
    extra['outside_local_union__mass']=extra.mass/extra.n
    return units.merge(extra[['model',*UNIT,'outside_local_union','outside_local_union__mass']],on=['model',*UNIT],validate='one_to_one')

def uncertainty(units,development_ids,replicates=10000,seed=20261031):
    ids=checked_ids(development_ids)
    if not units.id.isin(ids).all(): raise ValueError('Unknown resampled ID')
    multipliers=np.random.Generator(np.random.PCG64(seed)).exponential(1.,(replicates,len(ids)))
    lookup={d:k for k,d in enumerate(ids)};draws=[]
    for (h,m),g in units[units.supported].groupby(['horizon_days','model']):
        agg=np.zeros((replicates,len(METRICS)));n=g.origin_cell_1.nunique()
        for o,c in g.groupby('origin_cell_1'):
            if c.id.duplicated().any(): raise ValueError('Duplicate multiplier unit')
            w=multipliers[:,[lookup[d] for d in c.id]]
            agg+=(w@c[list(METRICS)].to_numpy(float))/w.sum(axis=1)[:,None]/n
        draws.append(pd.DataFrame(dict(horizon_days=h,model=m,replicate=np.arange(replicates),**{k:agg[:,j] for j,k in enumerate(METRICS)})))
    draws=pd.concat(draws,ignore_index=True);intervals=[];diffs=[];decisions=[]
    points=summarize_units(units).set_index(['horizon_days','model'])
    for (h,m),g in draws.groupby(['horizon_days','model']):
        for metric in METRICS: intervals.append(dict(horizon_days=h,model=m,metric=metric,lower_95=g[metric].quantile(.025),upper_95=g[metric].quantile(.975),defined_replicates=len(g),undefined_replicates=0))
    contrasts=[('LocalEndpointAdaptive',r) for r in ('B2','Fixed','Adaptive','LocalEndpoint')]
    for h in HORIZONS:
        wide=draws[draws.horizon_days.eq(h)].set_index(['replicate','model'])
        for m,ref in contrasts:
            changes={};bounds={}
            primary=ref in ('Fixed','LocalEndpoint')
            for metric in METRICS:
                d=wide.xs(m,level='model')[metric]-wide.xs(ref,level='model')[metric]
                delta=float(points.loc[(h,m),metric]-points.loc[(h,ref),metric]);changes[metric]=delta
                bound=float(d.quantile(.05/12 if metric=='region90_hit' else 1-.05/12)) if primary else np.nan;bounds[metric]=bound
                diffs.append(dict(horizon_days=h,model=m,reference=ref,metric=metric,difference=delta,lower_95=d.quantile(.025),upper_95=d.quantile(.975),adjusted_directional_bound=bound,primary_comparison=primary,defined_replicates=replicates))
            if primary:
                b=changes['brier']<-TOL and bounds['brier']<-TOL
                coverage=b and changes['region90_hit']>=-TOL and bounds['region90_hit']>=-TOL
                quality=coverage and changes['region90_cells']<=TOL and bounds['region90_cells']<=TOL
                decisions.append(dict(horizon_days=h,model=m,reference=ref,point_Brier_gain=changes['brier']<-TOL,
                    conditional_Brier_support=b,conditional_coverage_preserving=coverage,conditional_quality_preserving=quality,conditional_smaller_region=quality and bounds['region90_cells']<-TOL,
                    joint_point_benefit=changes['brier']<-TOL and changes['region90_hit']>=-TOL and changes['region90_cells']<=TOL,
                    application_tradeoff=changes['region90_hit']<-TOL or changes['region90_cells']>TOL,**{'delta_'+k:v for k,v in changes.items()}))
    meta=dict(generator='NumPy Generator PCG64',distribution='Exp(1)',seed=seed,shape=list(multipliers.shape),sorted_development_ids=list(ids),little_endian_float64_sha256=hashlib.sha256(multipliers.astype('<f8').tobytes()).hexdigest(),fixed_cell_set=True,fixed_fits=True,quantile_method='linear',directional_comparisons=12)
    return draws,pd.DataFrame(intervals),pd.DataFrame(diffs),pd.DataFrame(decisions),meta
