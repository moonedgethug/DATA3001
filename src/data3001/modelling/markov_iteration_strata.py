"""Stratified integration of the UNCHANGED affine empirical transition law.

For m ordered substeps, condition on k pooled-component labels. Conditional
label patterns are uniform over choose(m,k) orders, without commuting kernels.
Their exact weights are binomial(m,lambda). Missing local rows already have
L=B; E/U absorb, so dummy labels preserve the same identity in those states.

Each target gets an unbiased squared-probability U-statistic. No trajectory
importance weights, canonical record weights or model parameters are changed.
Outer evaluation continues to use ordinary independent particles.
"""
from math import comb
import numpy as np
from data3001.modelling.markov_iteration import validate_schedule,fast_scores
from data3001.modelling.markov_position import step
from data3001.preprocessing.prep_core import cells


def weights_for(steps,lambdas):
    lam=np.asarray(lambdas,float)
    if steps<1 or int(steps)!=steps or lam.ndim!=1 or not len(lam) or not np.isfinite(lam).all() or ((lam<0)|(lam>1)).any():
        raise ValueError('Invalid binomial integration targets')
    k=np.arange(steps+1)
    return np.array([comb(steps,int(j)) for j in k])*lam[:,None]**k*(1-lam[:,None])**(steps-k)


def allocations(weights,target):
    w=np.asarray(weights,float)
    if w.ndim!=2 or target<2 or not np.isfinite(w).all() or (w<0).any():raise ValueError('Invalid integration weights')
    np.testing.assert_allclose(w.sum(axis=1),1,rtol=0,atol=5e-15)
    maximum=w.max(axis=0)
    # N_k >= target*w_k for every tested lambda. Thus each category's
    # stratified variance is <= its iid-target variance (total variance law).
    return np.where(maximum>0,np.maximum(2,np.ceil(target*maximum)).astype(int),0)


def stratified_forecast(pools,lon,lat,velocity,sequence,weights,target,seed,mapper):
    sequence=validate_schedule(sequence);count=allocations(weights,target)
    if len(count)!=len(sequence)+1 or any(h not in pools for h in sequence):raise ValueError('Strata/schedule mismatch')
    total=int(count.sum());lon,lat,b=map(np.asarray,(lon,lat,velocity))
    if lon.ndim!=1 or lon.shape!=lat.shape or lon.shape!=b.shape:raise ValueError('Unequal origins')
    x=np.repeat(lon,total).astype(float);y=np.repeat(lat,total).astype(float)
    b=np.repeat(b,total).astype('int8');code=cells(x,y)
    remaining=np.tile(np.repeat(np.arange(len(count)),count),len(lon));rng=np.random.default_rng(seed);audit={}
    for number,h in enumerate(sequence):
        choose_pool=rng.random(len(x))<remaining/(len(sequence)-number)
        remaining-=choose_pool
        # Force the selected affine component in the existing, unchanged
        # local/pooled step; its missing-row fallback remains automatic.
        code,x,y,b,record=step(pools[h],x,y,code,b,.5,np.where(choose_pool,0.,.75),rng.random(len(x)),mapper,precise=True)
        for key,v in record.items():audit[key]=audit.get(key,0)+v
    if remaining.any():raise ValueError('Conditional component-count sampler failed')
    return code.reshape(-1,total),count,audit


def substrata(draws,count,subcount):
    if (np.asarray(subcount)>count).any():raise ValueError('Subensemble exceeds available stratum')
    offsets=np.r_[0,np.cumsum(count)]
    keep=np.concatenate([np.arange(offsets[k],offsets[k]+n) for k,n in enumerate(subcount) if n])
    return draws[:,keep]


def stratified_scores(draws,truth,count,weights):
    draws=np.asarray(draws);truth=np.asarray(truth);count=np.asarray(count,int);w=np.asarray(weights,float)
    if (draws.ndim!=2 or truth.shape!=(len(draws),) or count.ndim!=1 or w.ndim!=2
            or w.shape[1]!=len(count) or int(count.sum())!=draws.shape[1]
            or ((count>0)&(count<2)).any() or (count<0).any()
            or (w[:,count==0]!=0).any() or not np.issubdtype(draws.dtype,np.integer)
            or not (((draws>=0)&(draws<64800))|(draws==-2)|(draws==-3)).all()):
        raise ValueError('Invalid stratified ensemble')
    np.testing.assert_allclose(w.sum(axis=1),1,rtol=0,atol=5e-15)
    n,m=draws.shape;part_weight=np.repeat(w[:,count>0]/count[count>0],count[count>0],axis=1).T
    order=np.argsort(draws,axis=1,kind='stable');sorted_=np.take_along_axis(draws,order,axis=1).ravel()
    change=sorted_[1:]!=sorted_[:-1];change[np.arange(m-1,n*m-1,m)]=True
    starts=np.r_[0,np.flatnonzero(change)+1,n*m]
    ordered=part_weight[order].reshape(n*m,len(w));group=np.add.reduceat(ordered,starts[:-1],axis=0)
    rows=starts[:-1]//m
    norm=np.column_stack([np.bincount(rows,weights=group[:,j]**2,minlength=n) for j in range(len(w))])
    p=(draws==truth[:,None])@part_weight;u=(draws==-3)@part_weight;e=(draws==-2)@part_weight
    bias=np.zeros((n,len(w)));offset=0
    for k,number in enumerate(count):
        if not number:continue
        score=fast_scores(draws[:,offset:offset+number],truth);offset+=number
        norm_k=score['S_issued']-1+2*score['true_probability_issued']
        bias+=(1-norm_k)[:,None]*(w[:,k]**2/(number-1))[None,:]
    return {'S_integration':1-2*p+norm-bias,'S_issued':1-2*p+norm,
            'true_probability_issued':p,'U_mass':u,'E_mass':e}
