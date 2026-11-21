"""S3 E3: fitting-only neighbour overlap and weak-unseen endpoint shrinkage."""
from dataclasses import dataclass
import hashlib
import json
import numpy as np
import pandas as pd
from data3001.modelling.baselines import local_endpoint_adaptive_s3_e2 as control
from data3001.modelling.baselines.empirical_b2 import checked_ids
from data3001.modelling.common.qualified_count_inputs import ROW, DEST, HORIZONS, EXIT
from data3001.modelling.common.prediction_regions import checked_distribution, probability_region

METRICS=control.METRICS
UNIT=control.UNIT
TOL=control.TOL
MODELS=(*control.MODELS,'LocalEndpointQuality')
ABLATIONS=('QualitySimilarityOnly','QualityGateOnly')
OUTPUT_MODELS=(*MODELS,*ABLATIONS)
ETAS=(0.,.5,.9)
RHOS=(1.,.5,0.)
PARAMETERS=['parameter_a','parameter_gamma','parameter_eta','parameter_rho']
IDENTITY=['horizon_days','model',*PARAMETERS]
CATEGORIES=('shared_rare','shared_common','local_only','weak_unseen','other_neighbour_only','outside_union','exit')
EXTRAS=[f'category_{c}_{m}' for c in CATEGORIES for m in ('probability','observed','hit','brier')]
summarize_units=control.summarize_units
attach_primary_weights=control.attach_primary_weights


@dataclass
class QualityBases(control.LocalBases):
    quality: dict
    donor_quality: pd.DataFrame
    endpoint_evidence: pd.DataFrame


def fit_bases(counts,training_ids,origins,destinations):
    base=control.fit_bases(counts,training_ids,origins,destinations)
    fitting=counts[counts.id.isin(base.b2.training_ids)]
    geographic=base.states>=0
    raw={};endpoint_ids={}
    for key,g in fitting.groupby(ROW,sort=True):
        v=np.zeros(len(base.states),dtype=np.int64);idsets={}
        for j,z in g.groupby(DEST):
            v[base.index[j]]=int(z.pair_count.sum());idsets[int(j)]=set(map(int,z.id))
        raw[key]=v;endpoint_ids[key]=idsets
    quality={};donor_rows=[];evidence=[]
    for (h,i),p in base.rows.items():
        own=raw[(h,i)];local_D=int(own[geographic].sum())
        pD=own/local_D if local_D else np.zeros(len(p));pD=pD.astype(float);pD[~geographic]=0
        donors=[k for k in control.neighbours(i) if (h,k) in raw]
        donor_counts=sum((raw[(h,k)] for k in donors),start=np.zeros(len(p),dtype=np.int64))
        donor_D=int(donor_counts[geographic].sum());q=base.endpoint_rows[(h,i)]
        union={}
        for k in donors:
            for j,ids in endpoint_ids[(h,k)].items():union.setdefault(j,set()).update(ids)
        C=np.array([len(union.get(int(j),set())) for j in base.states],dtype=np.int64)
        weak=geographic&(own==0)&(donor_counts>0)&(100*donor_counts<donor_D)&(C<3)
        reason='no_neighbours' if not donors else 'local_D_empty' if not local_D else 'neighbour_D_empty' if not donor_D else ''
        if reason:weak[:]=False
        groups=np.full(len(p),5,dtype=np.int8)
        seen=(own>0)&geographic;shared=seen&(donor_counts>0)
        groups[shared&(100*own<local_D)]=0;groups[shared&(100*own>=local_D)]=1
        groups[seen&(donor_counts==0)]=2
        groups[weak]=3;groups[geographic&(own==0)&(donor_counts>0)&~weak]=4
        groups[~geographic]=6
        donor_info=[]
        for k in donors:
            nD=int(raw[(h,k)][geographic].sum());pk=raw[(h,k)]/nD if nD else np.zeros(len(p));pk=pk.astype(float);pk[~geographic]=0
            similarity=float(np.minimum(pD,pk).sum()) if local_D and nD else np.nan
            donor_info.append((k,nD,pk,similarity))
        references={}
        for eta in ETAS:
            scores=np.array([nD*((1-eta)+eta*s) if nD and not reason else float(nD) for k,nD,pk,s in donor_info])
            weights=scores/scores.sum() if scores.sum()>0 else np.zeros(len(scores))
            adjusted=q.copy()
            if not reason and eta:
                adjusted[geographic]=(1-q[base.index[EXIT]])*sum((w*pk[geographic] for w,(k,nD,pk,s) in zip(weights,donor_info)),start=np.zeros(geographic.sum()))
            checked_distribution(adjusted,base.states);references[eta]=adjusted
            for w,(k,nD,pk,s) in zip(weights,donor_info):
                own_ids=set().union(*endpoint_ids[(h,k)].values())
                donor_rows.append(dict(horizon_days=h,origin_cell_1=i,donor_cell_1=k,parameter_eta=eta,
                    donor_pairs=int(raw[(h,k)].sum()),donor_D_pairs=nD,donor_ids=len(own_ids),
                    similarity=s,original_D_weight=nD/donor_D if donor_D else 0.,reweighted_D_weight=w,
                    applied_quality=not bool(reason),fallback_reason=reason))
        quality[(h,i)]=dict(pD=pD,weak=weak,category=groups,references=references,reason=reason,local_D_pairs=local_D,
            donor_D_pairs=donor_D,original_weak_mass=float(q[weak].sum()),endpoint_ID_counts=C)
        for j in np.flatnonzero((own>0)|(donor_counts>0)):
            state=int(base.states[j])
            evidence.append(dict(horizon_days=h,origin_cell_1=i,destination_cell_1=state,local_pairs=int(own[j]),
                neighbour_pairs=int(donor_counts[j]),local_endpoint_ids=len(endpoint_ids[(h,i)].get(state,set())),
                neighbour_endpoint_ids=int(C[j]),local_D_probability=float(pD[j]),
                original_neighbour_D_probability=float(donor_counts[j]/donor_D) if donor_D and state>=0 else 0.,
                weak_unseen=bool(weak[j]),category=CATEGORIES[groups[j]],fallback_reason=reason))
    return QualityBases(**vars(base),quality=quality,donor_quality=pd.DataFrame(donor_rows),endpoint_evidence=pd.DataFrame(evidence))


def quality_reference(base,h,i,eta,rho):
    if eta not in ETAS or rho not in RHOS:raise ValueError('Unapproved quality parameter')
    data=base.quality[(h,i)];q=data['references'][eta]
    delta=(1-rho)*float(q[data['weak']].sum())
    adjusted=q.copy();adjusted[data['weak']]*=rho;adjusted+=delta*data['pD']
    checked_distribution(adjusted,base.states)
    if abs(adjusted[base.index[EXIT]]-base.endpoint_rows[(h,i)][base.index[EXIT]])>TOL:raise ValueError('Exit mass changed')
    return adjusted,delta


def vector(base,h,i,model,a=0.,gamma=0.,eta=0.,rho=1.):
    if model in control.MODELS:return control.vector(base,h,i,model,a,gamma)
    if model not in ('LocalEndpointQuality',*ABLATIONS):raise ValueError('Unknown model')
    if (h,i) not in base.rows:return None
    q,delta=quality_reference(base,h,i,eta,rho)
    w=control.applied_weight(base,h,i,'LocalEndpointAdaptive',a,gamma)
    return (1-w)*base.rows[(h,i)]+w*q


def control_candidates(base,counts,ids):
    return control.candidate_units(base,counts,ids).assign(parameter_eta=0.,parameter_rho=1.)


def select_controls(units):
    chosen,pool=control.select_parameters(units)
    return chosen.assign(parameter_eta=0.,parameter_rho=1.),pool.assign(parameter_eta=0.,parameter_rho=1.)


def quality_candidates(base,counts,evaluation_ids,anchor):
    ids=checked_ids(evaluation_ids)
    if set(ids)&set(base.b2.training_ids):raise ValueError('Quality validation ID leakage')
    pars=anchor[anchor.model.eq('LocalEndpointAdaptive')].set_index('horizon_days')
    result=[];spec=[(e,r) for e in ETAS for r in RHOS]
    for (h,o),g in counts[counts.id.isin(ids)].groupby(ROW,sort=True):
        ident=np.sort(g.id.unique());n=g.groupby('id').pair_count.sum().reindex(ident).to_numpy()
        a,gamma=float(pars.loc[h,'parameter_a']),float(pars.loc[h,'parameter_gamma'])
        common=dict(horizon_days=h,origin_cell_1=o,id=ident,eligible_pairs=n,model='LocalEndpointQuality',parameter_a=a,parameter_gamma=gamma)
        if (h,o) not in base.rows:
            result.extend(pd.DataFrame({**common,'parameter_eta':e,'parameter_rho':r,'supported':False,**{k:np.nan for k in METRICS}}) for e,r in spec)
            continue
        observed=np.zeros((len(ident),len(base.states)));ix={d:k for k,d in enumerate(ident)}
        for row in g.itertuples(index=False):observed[ix[row.id],base.index[row.destination_cell_1]]=row.pair_count
        observed/=n[:,None]
        vectors=np.array([vector(base,h,o,'LocalEndpointQuality',a,gamma,e,r) for e,r in spec])
        regions=np.array([probability_region(p,base.states)[0] for p in vectors])
        bs=1+np.square(vectors).sum(axis=1)[None,:]-2*observed@vectors.T
        hit=observed@regions.T.astype(float);size=np.sum(regions&(base.states[None,:]>=0),axis=1)
        for k,(eta,rho) in enumerate(spec):result.append(pd.DataFrame({**common,'parameter_eta':eta,'parameter_rho':rho,'supported':True,
            'brier':bs[:,k],'region90_cells':size[k],'region90_hit':hit[:,k]}))
    if not result:raise ValueError('Empty quality validation population')
    return pd.concat(result,ignore_index=True)


def select_quality(units):
    pool=summarize_units(units,IDENTITY);pool['selected']=False;pool['within_tie']=False;chosen=[]
    for h in HORIZONS:
        g=pool[pool.horizon_days.eq(h)]
        if g.brier.isna().any() or len(g)!=9 or g.parameter_a.nunique()!=1 or g.parameter_gamma.nunique()!=1:raise ValueError('Quality grid or anchor mismatch')
        if set(g[['parameter_eta','parameter_rho']].itertuples(index=False,name=None))!={(e,r) for e in ETAS for r in RHOS}:raise ValueError('Incomplete quality grid')
        if any(g[c].nunique()!=1 for c in ('eligible_pairs','evaluable_pairs','evaluable_id_cells','evaluable_cells')):raise ValueError('Quality availability mismatch')
        tied=g[g.brier<=g.brier.min()+TOL];best=tied.sort_values(['parameter_eta','parameter_rho'],ascending=[True,False]).iloc[0]
        pool.loc[tied.index,'within_tie']=True;pool.loc[best.name,'selected']=True
        chosen.append({**best.to_dict(),'selected':True,'within_tie':True,'selection_status':'anchor_then_Brier_smaller_eta_larger_rho'})
    return pd.DataFrame(chosen),pool


def add_ablations(selected):
    quality=selected[selected.model.eq('LocalEndpointQuality')];parts=[selected]
    for name in ABLATIONS:
        v=quality.copy();v['model']=name;v['selection_status']='derived_ablation_no_selection'
        v['parameter_rho' if name=='QualitySimilarityOnly' else 'parameter_eta']=1. if name=='QualitySimilarityOnly' else 0.
        parts.append(v)
    return pd.concat(parts,ignore_index=True)


def forecasts(base,model,selected):
    if model in control.MODELS:
        vectors,support=control.forecasts(base,model,selected)
        return vectors,support.assign(parameter_eta=0.,parameter_rho=1.,quality_total_variation=0.,redirected_D_mass=0.,mixed_redirected_D_mass=0.,quality_fallback_reason='')
    pars=selected[selected.model.eq(model)].set_index('horizon_days');vectors={};rows=[]
    for r in base.b2.support.itertuples(index=False):
        h,i=r.horizon_days,r.origin_cell_1;a,gamma,eta,rho=[float(pars.loc[h,k]) for k in PARAMETERS]
        p=vector(base,h,i,model,a,gamma,eta,rho)
        row={**r._asdict(),'model':model,**dict(zip(PARAMETERS,(a,gamma,eta,rho))),'median_pair_count':base.medians[h],
            'borrowing_weight':np.nan,'effective_borrowing_weight':np.nan,'total_B2_weight':np.nan,
            'adaptation_total_variation':np.nan,'quality_total_variation':np.nan,'redirected_D_mass':np.nan,'mixed_redirected_D_mass':np.nan,'quality_fallback_reason':''}
        if p is not None:
            checked_distribution(p,base.states);vectors[(h,i)]=p;row.update(base.support_lookup[(h,i)])
            w=control.applied_weight(base,h,i,'LocalEndpointAdaptive',a,gamma);q,delta=quality_reference(base,h,i,eta,rho)
            original=control.vector(base,h,i,'LocalEndpointAdaptive',a,gamma)
            # Endpoint-specific D return has its own accounting; lambda remains the nominal outer weight.
            row.update(borrowing_weight=w,effective_borrowing_weight=w,total_B2_weight=1-w,
                adaptation_total_variation=float(np.abs(original-control.vector(base,h,i,'LocalEndpoint',a)).sum()/2),
                quality_total_variation=float(np.abs(p-original).sum()/2),redirected_D_mass=delta,mixed_redirected_D_mass=w*delta,
                quality_fallback_reason=base.quality[(h,i)]['reason'])
        rows.append(row)
    return vectors,pd.DataFrame(rows)


def diagnostic_scores(base,vectors,counts,ids,model):
    scores,boundaries=control.diagnostic_scores(base,vectors,counts,ids,model)
    extras=pd.DataFrame(np.nan,index=scores.index,columns=EXTRAS)
    for key,ix in scores.groupby(ROW).groups.items():
        if key not in vectors:continue
        p=vectors[key];groups=base.quality[key]['category'];truth=np.array([base.index[v] for v in scores.loc[ix,DEST]])
        reg=probability_region(p,base.states)[0]
        for k,c in enumerate(CATEGORIES):
            mask=groups==k;event=(groups[truth]==k).astype(float)
            extras.loc[ix,f'category_{c}_probability']=p[mask].sum()
            extras.loc[ix,f'category_{c}_observed']=event
            extras.loc[ix,f'category_{c}_hit']=event*reg[truth]
            extras.loc[ix,f'category_{c}_brier']=float(p[mask]@p[mask])+event*(1-2*p[truth])
    return pd.concat([scores,extras],axis=1),boundaries


def metric_columns(scores):return [*control.metric_columns(scores),*[k for k in EXTRAS if k in scores]]


def score_units(scores):
    units=control.score_units(scores);keys=['model',*UNIT]
    grouped=scores.groupby(keys,sort=True);totals=grouped.pair_count.sum();extra=pd.DataFrame(index=totals.index)
    for m in EXTRAS:
        v=scores[keys].copy();v['numerator']=scores[m].fillna(0)*scores.pair_count;v['mass']=scores[m].notna()*scores.pair_count
        g=v.groupby(keys).sum();extra[m]=g.numerator/totals;extra[m+'__mass']=g.mass/totals
    return units.merge(extra.reset_index(),on=keys,validate='one_to_one')


def uncertainty(units,development_ids,replicates=20000,seed=20261031):
    ids=checked_ids(development_ids)
    if not units.id.isin(ids).all():raise ValueError('Unknown resampled ID')
    multipliers=np.random.Generator(np.random.PCG64(seed)).exponential(1.,(replicates,len(ids)))
    lookup={d:k for k,d in enumerate(ids)};draws=[]
    for (h,m),g in units[units.supported].groupby(['horizon_days','model']):
        agg=np.zeros((replicates,len(METRICS)));n=g.origin_cell_1.nunique()
        for o,c in g.groupby('origin_cell_1'):
            if c.id.duplicated().any():raise ValueError('Duplicate multiplier unit')
            w=multipliers[:,[lookup[d] for d in c.id]]
            agg+=(w@c[list(METRICS)].to_numpy(float))/w.sum(axis=1)[:,None]/n
        draws.append(pd.DataFrame(dict(horizon_days=h,model=m,replicate=np.arange(replicates),**{k:agg[:,j] for j,k in enumerate(METRICS)})))
    draws=pd.concat(draws,ignore_index=True);intervals=[];diffs=[];decisions=[]
    points=summarize_units(units).set_index(['horizon_days','model'])
    for (h,m),g in draws.groupby(['horizon_days','model']):
        for metric in METRICS:intervals.append(dict(horizon_days=h,model=m,metric=metric,lower_95=g[metric].quantile(.025),upper_95=g[metric].quantile(.975),defined_replicates=len(g),undefined_replicates=0))
    for h in HORIZONS:
        wide=draws[draws.horizon_days.eq(h)].set_index(['replicate','model'])
        for ref in (*control.MODELS,*ABLATIONS):
            changes={};bounds={};primary=ref in ('Fixed','LocalEndpoint','LocalEndpointAdaptive')
            for metric in METRICS:
                d=wide.xs('LocalEndpointQuality',level='model')[metric]-wide.xs(ref,level='model')[metric]
                delta=float(points.loc[(h,'LocalEndpointQuality'),metric]-points.loc[(h,ref),metric]);changes[metric]=delta
                bound=float(d.quantile(.05/18 if metric=='region90_hit' else 1-.05/18)) if primary else np.nan;bounds[metric]=bound
                diffs.append(dict(horizon_days=h,model='LocalEndpointQuality',reference=ref,metric=metric,difference=delta,lower_95=d.quantile(.025),upper_95=d.quantile(.975),adjusted_directional_bound=bound,primary_comparison=primary,defined_replicates=replicates))
            if primary:
                b=changes['brier']<-TOL and bounds['brier']<-TOL
                coverage=b and changes['region90_hit']>=-TOL and bounds['region90_hit']>=-TOL
                quality=coverage and changes['region90_cells']<=TOL and bounds['region90_cells']<=TOL
                decisions.append(dict(horizon_days=h,model='LocalEndpointQuality',reference=ref,point_Brier_gain=changes['brier']<-TOL,
                    conditional_Brier_support=b,conditional_coverage_preserving=coverage,conditional_quality_preserving=quality,
                    conditional_smaller_region=quality and changes['region90_cells']<-TOL and bounds['region90_cells']<-TOL,
                    joint_point_benefit=changes['brier']<-TOL and changes['region90_hit']>=-TOL and changes['region90_cells']<=TOL,
                    application_tradeoff=changes['region90_hit']<-TOL or changes['region90_cells']>TOL,**{'delta_'+k:v for k,v in changes.items()}))
    meta=dict(generator='NumPy Generator PCG64',distribution='Exp(1)',seed=seed,shape=list(multipliers.shape),sorted_development_ids=list(ids),little_endian_float64_sha256=hashlib.sha256(multipliers.astype('<f8').tobytes()).hexdigest(),fixed_cell_set=True,fixed_fits=True,quantile_method='linear',directional_comparisons=18)
    return draws,pd.DataFrame(intervals),pd.DataFrame(diffs),pd.DataFrame(decisions),meta
