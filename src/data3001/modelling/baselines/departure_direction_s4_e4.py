"""Direct horizon heading votes on the annual row; no speed or future heading input."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from data3001.modelling.baselines.departure_direction_s4_e4_inputs import ORIGIN
from data3001.modelling.baselines.seasonal_conditioning_s4_e1_inputs import KEY,validation_weights
from data3001.modelling.baselines.seasonal_information_s4_e3 import choose_weight
from data3001.modelling.common.prediction_regions import probability_region

ROW=['horizon_days','origin_cell_1']
FEATURES=['interval_reason','speed','east','north']


def threshold(data):
    origins=data.drop_duplicates(ORIGIN)
    speeds=origins.loc[origins.interval_reason.eq('valid') & origins.speed.gt(0),'speed'].to_numpy()
    if not len(speeds): return np.nan
    tau=float(np.quantile(speeds,.1,method='linear'))
    ordered=np.sort(speeds);rank=(len(ordered)-1)*.1
    check=ordered[int(np.floor(rank))]*(1-rank%1)+ordered[int(np.ceil(rank))]*(rank%1)
    assert abs(tau-check)<1e-12
    return tau


def classify(frame,tau):
    reason=frame.interval_reason.to_numpy(dtype=object).copy()
    speed=frame.speed.to_numpy()
    good=reason=='valid'
    reason[good & (speed==0)]='zero_speed'
    if np.isnan(tau):
        reason[good & (speed>0)]='no_positive_fit_speed'
    else:
        reason[good & (speed>0) & (speed<=tau)]='low_speed'
    usable=reason=='valid'
    uv=np.zeros((len(frame),2))
    uv[usable]=frame[['east','north']].to_numpy()[usable]/speed[usable,None]
    assert np.allclose((uv[usable]**2).sum(axis=1),1,atol=1e-12,rtol=0)
    return reason,uv


@dataclass
class Basis:
    states: np.ndarray
    annual: np.ndarray
    unheaded: np.ndarray
    headed: np.ndarray
    components: np.ndarray


def fit(training,tau):
    reason,uv=classify(training,tau)
    df=training[ROW+['destination_cell_1']].copy()
    df['usable']=reason=='valid';df[['east_unit','north_unit']]=uv
    bases={};support=[]
    for key,g in df.groupby(ROW):
        active,pos=np.unique(np.r_[g.destination_cell_1.to_numpy(),-2],return_inverse=True)
        pos=pos[:-1]
        count=np.bincount(pos,minlength=len(active));headed=np.bincount(pos,weights=g.usable.astype(float),minlength=len(active))
        components=np.stack([np.bincount(pos,weights=g[col],minlength=len(active)) for col in ['east_unit','north_unit']],axis=1)
        alt=g.groupby('destination_cell_1').agg(n=('usable','size'),headed=('usable','sum'),x=('east_unit','sum'),y=('north_unit','sum')).reindex(active,fill_value=0)
        assert np.array_equal(count,alt.n) and np.array_equal(headed,alt.headed)
        assert np.allclose(components,alt[['x','y']],atol=1e-12,rtol=1e-12)
        bases[key]=Basis(active,count/count.sum(),count-headed,headed,components)
        for j,n,k,xy in zip(active,count,headed,components):
            support.append((*key,j,int(n),int(k),int(n-k),xy[0],xy[1]))
    return bases,pd.DataFrame(support,columns=ROW+['destination','pairs','usable_pairs','unusable_pairs','east_sum','north_sum'])


def predict_basis(basis,queries,tau):
    reason,uv=classify(queries,tau)
    fallback=reason!='valid'
    if not basis.headed.sum():
        reason[~fallback]='empty_usable_donor_row'
        fallback[:]=True
    result=np.broadcast_to(basis.annual,(len(queries),len(basis.states))).copy()
    if (~fallback).any():
        raw=basis.headed+0.5*(uv[~fallback]@basis.components.T)
        total=(basis.headed+basis.unheaded).sum()
        result[~fallback]=(basis.unheaded+raw/(raw.sum(axis=1)[:,None]/basis.headed.sum()))/total
    assert np.allclose(result.sum(axis=1),1,rtol=0,atol=1e-12) and np.all(result>=0)
    assert np.all((result>0)==(basis.annual>0))
    return result,reason


def direct_donor_check(training,queries,basis,tau,directional):
    # First/middle/last held-out key in every supported row and role.
    donors=training.sort_values(ORIGIN)
    valid=donors.interval_reason.eq('valid') & donors.speed.gt(tau)
    for j in sorted({0,len(queries)//2,len(queries)-1}):
        query=queries.iloc[j]
        weights=np.ones(len(donors))
        if query.interval_reason=='valid' and query.speed>tau and valid.any():
            angles=np.arctan2(donors.loc[valid,'north'],donors.loc[valid,'east'])
            angle=np.arctan2(query.north,query.east)
            raw=1+.5*np.cos(angles-angle)
            weights[valid.to_numpy()]=raw/raw.mean()
        ix=pd.Index(basis.states).get_indexer(donors.destination_cell_1)
        counts=np.bincount(ix,weights=weights,minlength=len(basis.states))
        assert np.allclose(counts/len(weights),directional[j],rtol=0,atol=1e-12)


def make_blocks(train,queries):
    tau=threshold(train)
    bases,support=fit(train,tau)
    training=train.groupby(ROW)
    blocks=[]
    for key,g in queries.groupby(ROW):
        g=g.sort_values(KEY).reset_index(drop=True)
        basis=bases.get(key)
        if basis is None:
            g['supported']=False;g['fallback_reason']='annual_unsupported'
            blocks.append((key,g,None,None));continue
        D,reason=predict_basis(basis,g,tau)
        direct_donor_check(training.get_group(key),g,basis,tau,D)
        g['supported']=True;g['fallback_reason']=reason
        blocks.append((key,g,basis,D))
    return tau,support,blocks


def at_truth(matrix,pos):
    return np.where(pos>=0,matrix[np.arange(len(pos)),np.maximum(pos,0)],0.)


def selection(folds):
    parts=[]
    for role,blocks in folds:
        for key,g,b,D in blocks:
            z=g[KEY+['origin_cell_1','supported','fallback_reason']].copy()
            z['role']=role;z[['U','V','B0']]=np.nan
            if b is not None:
                pos=pd.Index(b.states).get_indexer(g.destination_cell_1)
                delta=D-b.annual
                z['U']=np.einsum('ij,ij->i',delta,delta)
                z['V']=at_truth(delta,pos)-delta@b.annual
                z['B0']=1+b.annual@b.annual-2*np.where(pos>=0,b.annual[np.maximum(pos,0)],0)
            parts.append(z)
    cases=pd.concat(parts,ignore_index=True)
    assert not cases.duplicated(KEY).any()
    eligible=validation_weights(cases)
    scored=validation_weights(cases[cases.supported])
    cases['eligible_weight']=eligible.weight
    cases['weight']=scored.weight.reindex(cases.index).fillna(0)
    choices=[];curves=[];lookup=cases.set_index(KEY).weight
    for h,g in scored.groupby('horizon_days'):
        U,V,B0=g.weight.to_numpy()@g[['U','V','B0']].to_numpy()
        lam=choose_weight(U,V)
        choices.append(dict(horizon_days=h,lambda_h=lam,U=U,V=V,brier_annual=B0,brier_full=B0-2*V+U,brier_selected=B0-2*lam*V+lam**2*U))
        grid=np.unique(np.r_[np.linspace(0,1,101),lam]);pooled=np.zeros(len(grid))
        for name,blocks in folds:
            direct=np.zeros(len(grid));mass=0.
            for (hh,_),z,b,D in blocks:
                if hh!=h or b is None:continue
                w=lookup.reindex(pd.MultiIndex.from_frame(z[KEY])).to_numpy()
                pos=pd.Index(b.states).get_indexer(z.destination_cell_1)
                # Subtract the one-hot truth explicitly, including truths off the stored support.
                end=D.copy();start=np.broadcast_to(b.annual,D.shape).copy()
                good=np.flatnonzero(pos>=0)
                end[good,pos[good]]-=1;start[good,pos[good]]-=1
                outside=w[pos<0].sum()
                for k,c in enumerate(grid):
                    errors=(1-c)*start+c*end
                    direct[k]+=w@np.einsum('ij,ij->i',errors,errors)+outside
                mass+=w.sum()
            pooled+=direct
            curves.extend((h,name,c,loss/mass) for c,loss in zip(grid,direct))
        assert np.allclose(pooled,B0-2*grid*V+grid**2*U,rtol=0,atol=1e-12)
        assert pooled[grid==lam][0]<=pooled.min()+1e-12
        curves.extend((h,'pooled',c,loss) for c,loss in zip(grid,pooled))
    return pd.DataFrame(choices),pd.DataFrame(curves,columns=['horizon_days','fold','lambda_h','brier']),cases


def regions(probabilities,states):
    ranked=np.sort(probabilities,axis=1)[:,::-1]
    idx=(np.cumsum(ranked,axis=1)<(.90-1e-12)).sum(axis=1)
    cutoff=ranked[np.arange(len(ranked)),idx]
    mask=(probabilities>0)&(probabilities>=cutoff[:,None]-1e-12)
    for k,p in enumerate(probabilities):
        reference,_=probability_region(p,states)
        assert np.array_equal(mask[k],reference)
    return mask
