"""Numerical integration of the unchanged categorical S, plus issued-ensemble diagnostics.

Collision counts remove the finite-particle upward bias in squared probability.
They estimate the same limiting-law S; they do not define a different loss.
"""
from functools import lru_cache
import numpy as np
import pandas as pd

from data3001.modelling.markov_scoring import cell_coordinates_km


@lru_cache(maxsize=1)
def _coordinates():
    return cell_coordinates_km(np.arange(64800))


def validate_comparison(record,fitting,held,lag,lam):
    if (set(fitting)&set(held) or set(record['fitting_ids'])!=set(fitting)
            or lag not in [1,3,5,7] or not 0<=lam<=1):
        raise ValueError('Frozen role, fitting IDs, lag or mixture differs')


def ensemble_scores(draws,truth):
    draws=np.asarray(draws);truth=np.asarray(truth)
    if (draws.ndim!=2 or draws.shape[1]<2 or truth.shape!=(len(draws),)
            or not np.issubdtype(draws.dtype,np.integer)
            or not ((draws>=0)&(draws<64800)|(draws==-2)|(draws==-3)).all()
            or not ((truth>=0)&(truth<64800)|(truth==-2)).all()):
        raise ValueError('Invalid particle or observed states')
    m=draws.shape[1];rows=[]
    for a,y in zip(draws,truth):
        keys,cnt=np.unique(a,return_counts=True);freq=cnt/m
        t=int(np.sum(a==y));u=float(np.sum(a==-3)/m);exit_=float(np.sum(a==-2)/m)
        resolved=keys!=-3;k=keys[resolved];p=freq[resolved]
        available=p.sum()>=.9-1e-12;hit=False;size=np.nan;mass=np.nan
        if available:
            order=np.argsort(-p,kind='stable');rank=np.searchsorted(np.cumsum(p[order]),.9-1e-12)
            chosen=p>=p[order[min(rank,len(order)-1)]]-1e-15
            hit=bool(np.any(k[chosen]==y));size=int(np.sum(k[chosen]>=0));mass=float(p[chosen].sum())
        energy=squared=reference=np.nan
        # This describes the issued finite ensemble only. No U hits do not
        # certify completeness of the limiting donor law.
        spatial=(u==0 and y>=0 and (keys>=0).any())
        if spatial:
            mask=keys>=0;q=cnt[mask].astype(float);q/=q.sum()
            xyz=_coordinates()[keys[mask]];target=_coordinates()[y]
            dist=np.linalg.norm(xyz[:,None,:]-xyz[None,:,:],axis=2)
            energy=max(0.,float(q@np.linalg.norm(xyz-target,axis=1)-.5*q@dist@q))
            squared=float(np.sum((q@xyz-target)**2));reference=energy/100+squared/10000
        rows.append((1-2*t/m+np.sum(cnt*(cnt-1))/(m*(m-1)),
                     1-2*t/m+np.sum(freq**2),t/m,u,exit_,t==0,
                     available,hit,size,mass,energy,squared,reference))
    return pd.DataFrame(rows,columns=['S_integration','S_issued','true_probability_issued','U_mass','E_mass',
        'sampled_zero','region90_available','region90_hit','region90_cells','region90_mass',
        'energy_km_issued','mean_squared_km2_issued','linear_quadratic_issued'])


def aggregate_scores(frame):
    rows=[]
    for (fold,h,model,rep,sid),g in frame.groupby(['outer_fold','horizon_days','model','repeat','id'],sort=True):
        row=dict(outer_fold=int(fold),horizon_days=int(h),model=model,repeat=int(rep),id=int(sid),pairs=len(g))
        for col in ['S_integration','S_issued','true_probability_issued','U_mass','E_mass','sampled_zero',
                    'region90_available','region90_hit']:
            row[col+'_sum']=float(g[col].sum(min_count=1))
        for col in ['region90_cells','region90_mass','energy_km_issued','mean_squared_km2_issued','linear_quadratic_issued']:
            row[col+'_sum']=float(g[col].sum());row[col+'_n']=int(g[col].notna().sum())
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_scores(frame):
    rows=[]
    for (h,model,rep),g in frame.groupby(['horizon_days','model','repeat']):
        n=int(g.pairs.sum());row={'horizon_days':int(h),'model':model,'repeat':int(rep),
                               'eligible_pairs':n,'independent_ids':int(g.id.nunique())}
        for col in ['S_integration','S_issued','true_probability_issued','U_mass','E_mass','sampled_zero',
                    'region90_available','region90_hit']:
            row[col]=float(g[col+'_sum'].sum(min_count=1)/n)
        for col in ['region90_cells','region90_mass','energy_km_issued','mean_squared_km2_issued','linear_quadratic_issued']:
            den=int(g[col+'_n'].sum());row[col]=float(g[col+'_sum'].sum()/den) if den else np.nan
            row[col+'_available_pairs']=den
        rows.append(row)
    return pd.DataFrame(rows)


def paired_intervals(frame,replicates=200):
    """Fixed-fit whole-ID bootstrap, stratified by old outer fold. MC stays separate."""
    rows=[]
    for h,g in frame.groupby('horizon_days'):
        mean=g.groupby(['outer_fold','id','model'],as_index=False)[['S_integration_sum','pairs']].mean()
        loss=mean.pivot(index=['outer_fold','id'],columns='model',values='S_integration_sum')
        ns=mean.pivot(index=['outer_fold','id'],columns='model',values='pairs')
        if loss.isna().any().any() or not ns.eq(ns.iloc[:,0],axis=0).all().all():raise ValueError('Unmatched model cases')
        groups=[np.flatnonzero(loss.index.get_level_values(0)==f) for f in sorted(set(loss.index.get_level_values(0)))]
        rng=np.random.default_rng(20261027+int(h));draws=[np.concatenate([rng.choice(ix,len(ix),replace=True) for ix in groups]) for _ in range(replicates)]
        for a,b in [('exact-position','coarse-sampler'),('exact-position','old-exact'),('coarse-sampler','old-exact')]:
            delta=(loss[a]-loss[b]).to_numpy();n=ns[a].to_numpy()
            values=[delta[ix].sum()/n[ix].sum() for ix in draws];lo,hi=np.quantile(values,[.025,.975])
            rows.append({'horizon_days':int(h),'comparison':a+' minus '+b,'delta_S':delta.sum()/n.sum(),
                         'lower_95':lo,'upper_95':hi,'scope':'conditional_on_fixed_outer_fits; MC not removed'})
    return pd.DataFrame(rows)
