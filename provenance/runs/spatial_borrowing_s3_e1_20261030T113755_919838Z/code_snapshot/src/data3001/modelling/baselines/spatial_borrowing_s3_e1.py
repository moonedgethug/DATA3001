"""Five S3 estimators with raw-pair fitting and the frozen E3 evaluation target."""
from dataclasses import dataclass
import hashlib
import numpy as np
import pandas as pd

from data3001.modelling.baselines.adaptive_b2_b1 import Bases, fit_bases as fit_raw, borrowing_weight
from data3001.modelling.baselines.empirical_b2 import checked_ids
from data3001.modelling.baselines.drifter_shrinkage_e3 import (
    METRICS, UNIT, IDENTITY, GRID, TOL, summarize_units, diagnostic_scores, score_units,
    attach_primary_weights, metric_columns,
)
from data3001.modelling.common.qualified_count_inputs import ROW, DEST, HORIZONS
from data3001.modelling.common.prediction_regions import checked_distribution, probability_region
from data3001.modelling.baselines.spatial_borrowing_s3_e1_inputs import neighbours, FALLBACK

MODELS=('B2','Fixed','Adaptive','LocalEndpoint','LocalDisplacement')


@dataclass
class SpatialBases(Bases):
    endpoint_rows: dict
    displacement_rows: dict
    neighbour_support: pd.DataFrame


def fit_bases(counts,transfers,training_ids,origins,destinations):
    base=fit_raw(counts,training_ids,origins,destinations)
    local=counts[counts.id.isin(base.b2.training_ids)]
    moved=transfers[transfers.id.isin(base.b2.training_ids)]
    endpoint,displacement,diagnostics={},{},[]
    for (h,i),p in base.rows.items():
        donors=local[local.horizon_days.eq(h)&local.origin_cell_1.isin(neighbours(i))]
        trans=moved[moved.horizon_days.eq(h)&moved.origin_cell_1.eq(i)]
        n=int(donors.pair_count.sum()); n2=int(trans.pair_count.sum())
        if n!=n2: raise ValueError('Transfer ledger omitted or duplicated neighbour pairs')
        q=np.zeros(len(base.states)); v=q.copy(); rejected=0
        if n:
            for j,k in donors.groupby(DEST).pair_count.sum().items(): q[base.index[j]]=k/n
            for j,k in trans.groupby(DEST).pair_count.sum().items():
                if j==FALLBACK: rejected+=int(k)
                else: v[base.index[j]]=k/n
            r=rejected/n; d=v+r*p
        else: q=p.copy();d=p.copy();r=1.
        checked_distribution(q,base.states);checked_distribution(d,base.states)
        endpoint[(h,i)]=q;displacement[(h,i)]=d
        per_id=donors.groupby('id').pair_count.sum()
        local_ids=set(local.loc[local.horizon_days.eq(h)&local.origin_cell_1.eq(i),'id'])
        diagnostics.append(dict(horizon_days=h,origin_cell_1=i,neighbour_pairs=n,
            neighbour_ids=len(per_id),neighbour_cells=donors.origin_cell_1.nunique(),
            neighbour_largest_ID_share=float(per_id.max()/n) if n else 0.,
            overlap_local_neighbour_IDs=len(local_ids & set(per_id.index)),fallback_fraction=r,no_neighbour=n==0,
            **{f'reason_{int(code)}_fraction':int(trans.loc[trans.reason_code.eq(code),'pair_count'].sum())/n if n else 0. for code in range(11)}))
    return SpatialBases(**vars(base),endpoint_rows=endpoint,displacement_rows=displacement,neighbour_support=pd.DataFrame(diagnostics))


def vector(base,h,origin,model,a=0.):
    if model not in MODELS or not np.isfinite(a) or not 0<=a<=1: raise ValueError('Invalid S3 model/parameter')
    key=(h,origin)
    if key not in base.rows: return None
    p=base.rows[key]
    if model=='B2': return p
    if model=='Adaptive':
        n=base.b2.support.set_index(ROW).loc[key,'training_pair_count']
        lam=borrowing_weight('Adaptive',a,n,base.medians[h]); q=base.references[h]
    else:
        lam=a
        q=base.references[h] if model=='Fixed' else base.endpoint_rows[key] if model=='LocalEndpoint' else base.displacement_rows[key]
    return (1-lam)*p+lam*q


def specifications(): return [('B2',0.),*[(m,a) for m in MODELS[1:] for a in GRID]]


def candidate_units(base,counts,evaluation_ids):
    ids=checked_ids(evaluation_ids)
    if set(ids)&set(base.b2.training_ids): raise ValueError('Candidate ID leakage')
    result=[];spec=specifications()
    for (h,o),g in counts[counts.id.isin(ids)].groupby(ROW,sort=True):
        ident=np.sort(g.id.unique());n=g.groupby('id').pair_count.sum().reindex(ident).to_numpy()
        common=dict(horizon_days=h,origin_cell_1=o,id=ident,eligible_pairs=n)
        if (h,o) not in base.rows:
            result.extend(pd.DataFrame({**common,'model':m,'parameter_a':a,'supported':False,**{k:np.nan for k in METRICS}}) for m,a in spec)
            continue
        observed=np.zeros((len(ident),len(base.states)));ix={d:k for k,d in enumerate(ident)}
        for r in g.itertuples(index=False): observed[ix[r.id],base.index[r.destination_cell_1]]=r.pair_count
        observed/=n[:,None]
        vectors=np.array([vector(base,h,o,m,a) for m,a in spec])
        regions=np.array([probability_region(p,base.states)[0] for p in vectors])
        bs=1+np.square(vectors).sum(axis=1)[None,:]-2*observed@vectors.T
        hit=observed@regions.T.astype(float);size=np.sum(regions&(base.states[None,:]>=0),axis=1)
        for k,(m,a) in enumerate(spec):
            result.append(pd.DataFrame({**common,'model':m,'parameter_a':a,'supported':True,
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
            if tuple(sorted(g.parameter_a))!=GRID: raise ValueError('Incomplete S3 parameter grid')
            tied=g[g.brier<=g.brier.min()+TOL];best=tied.sort_values('parameter_a').iloc[0]
            pool.loc[tied.index,'within_tie']=True;pool.loc[best.name,'selected']=True
            chosen.append({**best.to_dict(),'selected':True,'within_tie':True,'selection_status':'primary_Brier_then_smaller_a'})
    return pd.DataFrame(chosen),pool


def forecasts(base,model,selected):
    parameters=selected[selected.model.eq(model)].set_index('horizon_days').parameter_a if model!='B2' else None
    vectors={};rows=[];ns=base.neighbour_support.set_index(ROW)
    for r in base.b2.support.itertuples(index=False):
        h,o=r.horizon_days,r.origin_cell_1;a=0. if model=='B2' else float(parameters.loc[h])
        p=vector(base,h,o,model,a)
        row={**r._asdict(),'model':model,'parameter_a':a,'median_pair_count':base.medians[h],
             'borrowing_weight':np.nan,'effective_borrowing_weight':np.nan,'total_B2_weight':np.nan}
        if p is not None:
            checked_distribution(p,base.states);vectors[(h,o)]=p;meta=ns.loc[(h,o)].to_dict();row.update(meta)
            lam=borrowing_weight('Adaptive',a,r.training_pair_count,base.medians[h]) if model=='Adaptive' else a
            effective=lam*(1-meta['fallback_fraction']) if model=='LocalDisplacement' else (0. if model=='LocalEndpoint' and meta['no_neighbour'] else lam)
            row.update(borrowing_weight=lam,effective_borrowing_weight=effective,total_B2_weight=1-effective)
        rows.append(row)
    return vectors,pd.DataFrame(rows)


def uncertainty(units,development_ids,replicates=5000,seed=20261030):
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
    contrasts=[(m,r) for m in ('LocalDisplacement','LocalEndpoint') for r in ('B2','Fixed','Adaptive')]+[('LocalDisplacement','LocalEndpoint')]
    for h in HORIZONS:
        wide=draws[draws.horizon_days.eq(h)].set_index(['replicate','model'])
        for m,ref in contrasts:
            changes={};bounds={}
            primary=m=='LocalDisplacement' and ref=='Fixed'
            for metric in METRICS:
                d=wide.xs(m,level='model')[metric]-wide.xs(ref,level='model')[metric]
                delta=float(points.loc[(h,m),metric]-points.loc[(h,ref),metric]);changes[metric]=delta
                bound=float(d.quantile(.05/6 if metric=='region90_hit' else 1-.05/6)) if primary else np.nan;bounds[metric]=bound
                diffs.append(dict(horizon_days=h,model=m,reference=ref,metric=metric,difference=delta,lower_95=d.quantile(.025),upper_95=d.quantile(.975),adjusted_directional_bound=bound,primary_comparison=primary,defined_replicates=replicates))
            if primary:
                b=changes['brier']<-TOL and bounds['brier']<-TOL
                quality=b and bounds['region90_hit']>=-TOL and bounds['region90_cells']<=TOL
                decisions.append(dict(horizon_days=h,model=m,reference=ref,point_Brier_gain=changes['brier']<-TOL,
                    conditional_Brier_support=b,conditional_quality_preserving=quality,conditional_smaller_region=quality and bounds['region90_cells']<-TOL,
                    joint_point_benefit=changes['brier']<-TOL and changes['region90_hit']>=-TOL and changes['region90_cells']<=TOL,
                    application_tradeoff=changes['region90_hit']<-TOL or changes['region90_cells']>TOL,**{'delta_'+k:v for k,v in changes.items()}))
    meta=dict(generator='NumPy Generator PCG64',distribution='Exp(1)',seed=seed,shape=list(multipliers.shape),sorted_development_ids=list(ids),little_endian_float64_sha256=hashlib.sha256(multipliers.astype('<f8').tobytes()).hexdigest(),fixed_cell_set=True,fixed_fits=True)
    return draws,pd.DataFrame(intervals),pd.DataFrame(diffs),pd.DataFrame(decisions),meta
