"""Joint endpoint borrowing with prospective dual-reference feasibility and fallback."""
import hashlib
import numpy as np
import pandas as pd
from data3001.modelling.baselines import local_endpoint_quality_s3_e3 as quality
from data3001.modelling.baselines.local_endpoint_adaptive_s3_e2 import GRID,GAMMAS
from data3001.modelling.baselines.empirical_b2 import checked_ids
from data3001.modelling.common.prediction_regions import probability_region
from data3001.modelling.common.qualified_count_inputs import ROW,DEST,HORIZONS

CONTROLS=quality.MODELS
JOINT='LocalEndpointJoint'
PRIMARY='LocalEndpointJointConstrained'
MODELS=(*CONTROLS,JOINT,PRIMARY)
OUTPUT_MODELS=MODELS
METRICS=quality.METRICS
PARAMETERS=quality.PARAMETERS
IDENTITY=quality.IDENTITY
TOL=1e-12
SPECS=tuple((a,g,e,1.) for a in GRID for g in GAMMAS for e in quality.ETAS)
fit_bases=quality.fit_bases
control_candidates=quality.control_candidates
quality_candidates=quality.quality_candidates
select_controls=quality.select_controls
select_quality=quality.select_quality
diagnostic_scores=quality.diagnostic_scores
score_units=quality.score_units
summarize_units=quality.summarize_units
attach_primary_weights=quality.attach_primary_weights
metric_columns=quality.metric_columns
CATEGORIES=quality.CATEGORIES


def vector(base,h,i,model,a=0.,gamma=0.,eta=0.,rho=1.):
    if model not in MODELS:raise ValueError('Unknown E4 model')
    if model in (JOINT,PRIMARY):
        if (a,gamma,eta,rho) not in SPECS:raise ValueError('Unapproved joint parameter')
        model='LocalEndpointQuality'
    return quality.vector(base,h,i,model,a,gamma,eta,rho)


def joint_candidates(base,counts,evaluation_ids):
    ids=checked_ids(evaluation_ids)
    if set(ids)&set(base.b2.training_ids):raise ValueError('Joint validation ID leakage')
    records=[]
    for (h,o),g in counts[counts.id.isin(ids)].groupby(ROW,sort=True):
        ident=np.sort(g.id.unique());n=g.groupby('id').pair_count.sum().reindex(ident).to_numpy()
        common=dict(horizon_days=h,origin_cell_1=o,id=ident,eligible_pairs=n,model=JOINT)
        if (h,o) not in base.rows:
            records.extend(pd.DataFrame({**common,**dict(zip(PARAMETERS,t)),'supported':False,**{k:np.nan for k in METRICS}}) for t in SPECS)
            continue
        observed=np.zeros((len(ident),len(base.states)));index={d:k for k,d in enumerate(ident)}
        for row in g.itertuples(index=False):observed[index[row.id],base.index[row.destination_cell_1]]=row.pair_count
        observed/=n[:,None]
        probabilities=np.array([vector(base,h,o,JOINT,*t) for t in SPECS])
        regions=np.array([probability_region(p,base.states)[0] for p in probabilities])
        brier=1+np.square(probabilities).sum(axis=1)[None,:]-2*observed@probabilities.T
        hits=observed@regions.T.astype(float);sizes=np.sum(regions&(base.states[None,:]>=0),axis=1)
        for k,t in enumerate(SPECS):records.append(pd.DataFrame({**common,**dict(zip(PARAMETERS,t)),'supported':True,
            'brier':brier[:,k],'region90_cells':sizes[k],'region90_hit':hits[:,k]}))
    if not records:raise ValueError('Empty joint validation population')
    return pd.concat(records,ignore_index=True)


def select_joint(units,controls):
    pool=summarize_units(units,IDENTITY)
    chosen,diagnostics=[],[]
    for h in HORIZONS:
        g=pool[pool.horizon_days.eq(h)].copy()
        if g[list(METRICS)].isna().any().any() or len(g)!=252 or set(g[PARAMETERS].itertuples(index=False,name=None))!=set(SPECS):
            raise ValueError('Incomplete or invalid joint candidate grid')
        availability=['eligible_pairs','evaluable_pairs','evaluable_id_cells','evaluable_cells']
        refs=controls[controls.horizon_days.eq(h)&controls.model.isin(('LocalEndpointAdaptive','Fixed'))].set_index('model')
        if set(refs.index)!=set(('LocalEndpointAdaptive','Fixed')):raise ValueError('Missing reference')
        for c in availability:
            if pd.concat([g[c],refs[c]]).nunique()!=1:raise ValueError('Candidate/reference availability mismatch')
        for ref,short in [('LocalEndpointAdaptive','anchor'),('Fixed','fixed')]:
            for metric in METRICS:
                g[f'{short}_{metric}']=refs.loc[ref,metric]
                g[f'delta_{short}_{metric}']=g[metric]-refs.loc[ref,metric]
            g[f'pass_{short}_hit']=g.region90_hit>=refs.loc[ref,'region90_hit']-TOL
            g[f'pass_{short}_size']=g.region90_cells<=refs.loc[ref,'region90_cells']+TOL
            g[f'pass_{short}']=g[f'pass_{short}_hit']&g[f'pass_{short}_size']
        g['feasible']=g.pass_anchor&g.pass_fixed
        g['strict_Brier_gain']=g.brier<min(refs.brier)-TOL
        def best(frame):
            tied=frame[frame.brier<=frame.brier.min()+TOL]
            return tied.sort_values(['parameter_eta','parameter_gamma','parameter_a']).iloc[0],set(tied.index)
        un,ties=best(g);g['within_joint_tie']=g.index.isin(ties);g['selected_joint']=g.index==un.name
        feasible=g[g.feasible];adopt=False;fties=set();proposal=None
        if not len(feasible):status='fallback_no_feasible_candidate'
        else:
            proposal,fties=best(feasible);adopt=bool(proposal.strict_Brier_gain)
            status='adopted_feasible_Brier_gain' if adopt else 'fallback_no_Brier_gain'
        g['within_feasible_tie']=g.index.isin(fties)
        g['selected_constrained']=g.index==proposal.name if adopt else False
        candidate=proposal if adopt else refs.loc['LocalEndpointAdaptive']
        issued=tuple(float(candidate[c]) for c in PARAMETERS)
        g['issued_constrained']=[tuple(t)==issued for t in g[PARAMETERS].itertuples(index=False,name=None)]
        chosen.append({**un.to_dict(),'model':JOINT,'selection_status':'unconstrained_joint_Brier','fallback':False})
        chosen.append({**candidate.to_dict(),'horizon_days':h,'model':PRIMARY,'selection_status':status,'fallback':not adopt})
        record=dict(horizon_days=h,selection_status=status,fallback=not adopt,
            feasible_anchor=int(g.pass_anchor.sum()),feasible_fixed=int(g.pass_fixed.sum()),feasible_both=int(g.feasible.sum()),
            feasible_and_Brier=int((g.feasible&g.strict_Brier_gain).sum()),
            best_rejected_Brier=float(g.loc[~g.feasible,'brier'].min()) if (~g.feasible).any() else np.nan,
            best_feasible_Brier=float(proposal.brier) if proposal is not None else np.nan,
            **{f'issued_{k}':v for k,v in zip(PARAMETERS,issued)})
        issued_row=g[g.issued_constrained].iloc[0]
        record.update({k:issued_row[k] for k in g if k.startswith(('anchor_','fixed_','delta_','pass_'))})
        diagnostics.append(record)
        pool.loc[g.index,g.columns]=g
    return pd.DataFrame(chosen),pool,pd.DataFrame(diagnostics)


def forecasts(base,model,selected):
    if model in CONTROLS:vectors,support=quality.forecasts(base,model,selected)
    else:
        pars=selected[selected.model.eq(model)].copy();pars['model']='LocalEndpointQuality'
        vectors,support=quality.forecasts(base,'LocalEndpointQuality',pars);support['model']=model
    anchor=selected[selected.model.eq('LocalEndpointAdaptive')].set_index('horizon_days')
    support['anchor_total_variation']=np.nan
    support['selection_fallback']=False
    for ix,r in support.iterrows():
        if not r.supported:continue
        h,i=int(r.horizon_days),int(r.origin_cell_1);a=anchor.loc[h]
        reference=quality.vector(base,h,i,'LocalEndpointAdaptive',a.parameter_a,a.parameter_gamma)
        support.loc[ix,'anchor_total_variation']=float(np.abs(vectors[(h,i)]-reference).sum()/2)
        if model==PRIMARY:support.loc[ix,'selection_fallback']=bool(selected[selected.model.eq(model)&selected.horizon_days.eq(h)].iloc[0]['fallback'])
    return vectors,support


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
        for metric in METRICS:intervals.append(dict(horizon_days=h,model=m,metric=metric,lower_95=g[metric].quantile(.025),upper_95=g[metric].quantile(.975),defined_replicates=replicates))
    for h in HORIZONS:
        wide=draws[draws.horizon_days.eq(h)].set_index(['replicate','model'])
        for model in (PRIMARY,JOINT):
            for ref in [m for m in MODELS if m!=model]:
                changes={};bounds={};primary=model==PRIMARY and ref in ('LocalEndpointAdaptive','Fixed')
                for metric in METRICS:
                    d=wide.xs(model,level='model')[metric]-wide.xs(ref,level='model')[metric]
                    delta=float(points.loc[(h,model),metric]-points.loc[(h,ref),metric]);changes[metric]=delta
                    bound=float(d.quantile(.05/12 if metric=='region90_hit' else 1-.05/12)) if primary else np.nan;bounds[metric]=bound
                    diffs.append(dict(horizon_days=h,model=model,reference=ref,metric=metric,difference=delta,lower_95=d.quantile(.025),upper_95=d.quantile(.975),adjusted_directional_bound=bound,primary_comparison=primary,defined_replicates=replicates))
                if primary:
                    b=changes['brier']<-TOL and bounds['brier']<-TOL
                    coverage=b and changes['region90_hit']>=-TOL and bounds['region90_hit']>=-TOL
                    quality_ok=coverage and changes['region90_cells']<=TOL and bounds['region90_cells']<=TOL
                    decisions.append(dict(horizon_days=h,model=model,reference=ref,conditional_Brier_support=b,
                        conditional_coverage_preserving=coverage,conditional_quality_preserving=quality_ok,
                        conditional_smaller_region=quality_ok and changes['region90_cells']<-TOL and bounds['region90_cells']<-TOL,
                        joint_point_benefit=changes['brier']<-TOL and changes['region90_hit']>=-TOL and changes['region90_cells']<=TOL,
                        **{'delta_'+k:v for k,v in changes.items()}))
    meta=dict(generator='NumPy Generator PCG64',distribution='Exp(1)',seed=seed,shape=list(multipliers.shape),sorted_development_ids=list(ids),little_endian_float64_sha256=hashlib.sha256(multipliers.astype('<f8').tobytes()).hexdigest(),fixed_cell_set=True,fixed_fits=True,quantile_method='linear',directional_comparisons=12)
    return draws,pd.DataFrame(intervals),pd.DataFrame(diffs),pd.DataFrame(decisions),meta
