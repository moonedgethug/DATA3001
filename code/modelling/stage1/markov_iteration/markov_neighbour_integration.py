"""Exact-law deterministic-mixture quadrature for joint alpha/lambda CV.

Importance terms are integration estimates, NOT normalised issued forecasts.
Each proposal component has r>=2 independent trajectories. The within-component
sample-variance correction preserves unbiased S for the unchanged target law.
"""
from functools import lru_cache
import hashlib
import numpy as np
from data3001.modelling.markov_models.markov_neighbour import neighbour_step, schedules
from data3001.preprocessing.prep_core import cells


@lru_cache(maxsize=256)
def weight_table(steps,proposal,target):
    p=np.asarray(proposal,float);t=np.asarray(target,float)
    if (steps<1 or p.ndim!=2 or t.ndim!=2 or p.shape[1]!=2 or t.shape[1]!=2
            or not len(p) or not len(t) or len(set(proposal))!=len(p)
            or not np.isfinite(p).all() or not np.isfinite(t).all()
            or ((p<0)|(p>1)).any() or ((t<0)|(t>1)).any()):raise ValueError('Invalid numerical proposals or targets')
    k=np.arange(steps+1)
    pa=p[:,0,None]**k*(1-p[:,0,None])**(steps-k)
    pl=p[:,1,None]**k*(1-p[:,1,None])**(steps-k)
    den=pa.T@pl/len(p)
    ta=t[:,0,None]**k*(1-t[:,0,None])**(steps-k)
    tl=t[:,1,None]**k*(1-t[:,1,None])**(steps-k)
    numerator=np.einsum('tk,tl->klt',ta,tl)
    if ((den[:,:,None]==0)&(numerator>0)).any():raise ValueError('Target label law lacks proposal support')
    out=np.divide(numerator,den[:,:,None],out=np.zeros_like(numerator),where=den[:,:,None]>0)
    if not np.isfinite(out).all() or (out>121+1e-10).any():raise ValueError('Likelihood ratio exceeds predeclared integration bound')
    out=np.ascontiguousarray(out);out.flags.writeable=False;return out


def likelihood_weights(steps,k,l,proposal,target):
    return weight_table(steps,tuple(map(tuple,proposal)),tuple(map(tuple,target)))[k,l]


def _norm(draws,w):
    n,m=draws.shape;t=w.shape[2]
    order=np.argsort(draws,axis=1,kind='stable');d=np.take_along_axis(draws,order,axis=1).ravel()
    ww=np.take_along_axis(w,order[:,:,None],axis=1).reshape(-1,t)
    change=d[1:]!=d[:-1];change[np.arange(m-1,n*m-1,m)]=True
    start=np.r_[0,np.flatnonzero(change)+1];g=np.add.reduceat(ww,start,axis=0)
    rows=start//m
    return np.column_stack([np.bincount(rows,weights=g[:,j]**2,minlength=n) for j in range(t)])


def weighted_scores(draws,truth,w,per_component):
    draws=np.asarray(draws);truth=np.asarray(truth);w=np.asarray(w,float);r=per_component
    if (draws.ndim!=2 or w.ndim!=3 or w.shape[:2]!=draws.shape or truth.shape!=(len(draws),)
            or not isinstance(r,int) or r<2 or draws.shape[1]%r or not np.isfinite(w).all() or (w<0).any()
            or not (((draws>=0)&(draws<64800))|(draws==-2)|(draws==-3)).all()):raise ValueError('Invalid weighted strata')
    n,m=draws.shape;p=m//r;t=w.shape[2];match=draws==truth[:,None]
    mass=w.mean(axis=1);py=(w*match[:,:,None]).mean(axis=1)
    norm=_norm(draws,w)/m**2
    ww=w.reshape(n,p,r,t);dm=draws.reshape(n*p,r)
    mw=ww.mean(axis=2);my=(ww*match.reshape(n,p,r,1)).mean(axis=2)
    norm_s=_norm(dm,ww.reshape(n*p,r,t)).reshape(n,p,t)/r**2
    uncentred_bias=((np.mean(ww**2,axis=2)-norm_s)/(r-1)).sum(axis=1)/p**2
    centred_s=norm_s-2*mw*my+mw**2
    centred_second=np.mean(2*ww**2*(~match).reshape(n,p,r,1),axis=2)
    centred_bias=((centred_second-centred_s)/(r-1)).sum(axis=1)/p**2
    return {'S_integration':norm-2*mass*py+mass**2-centred_bias,
            'S_uncentred':1-2*py+norm-uncentred_bias,
            'mass_estimate':mass,'true_probability_estimate':py,
            'U_mass_estimate':(w*(draws==-3)[:,:,None]).mean(axis=1),
            'E_mass_estimate':(w*(draws==-2)[:,:,None]).mean(axis=1)}


def query_seeds(role,ids,source_obs,repeat,layout):
    return np.array([int.from_bytes(hashlib.blake2b(
        f'20261028|{role}|{int(sid)}|{int(o)}|{repeat}|{layout}'.encode(),digest_size=8).digest(),'little')
        for sid,o in zip(ids,source_obs)],dtype='uint64')


def uniform(seeds,particles,lane):
    with np.errstate(over='ignore'):
        x=np.asarray(seeds,dtype='uint64')[:,None] + np.uint64(0x9e3779b97f4a7c15)*(np.arange(particles,dtype='uint64')[None,:]+np.uint64(lane*particles+1))
        x=(x^(x>>np.uint64(30)))*np.uint64(0xbf58476d1ce4e5b9)
        x=(x^(x>>np.uint64(27)))*np.uint64(0x94d049bb133111eb)
        x=x^(x>>np.uint64(31))
    return ((x>>np.uint64(11)).astype(float)*(1./9007199254740992.)).ravel()


def proposal_forecast(pools,lon,lat,velocity,sequence,proposal,r,seeds,mapper,trace=None):
    if r<2 or not len(proposal):raise ValueError('At least two paths per component required')
    pp=np.asarray(proposal);n=len(lon);total=len(pp)*r
    a=np.tile(np.repeat(pp[:,0],r),n);l=np.tile(np.repeat(pp[:,1],r),n)
    x=np.repeat(lon,total).astype(float);y=np.repeat(lat,total).astype(float)
    b=np.repeat(velocity,total).astype('int8');code=cells(x,y)
    k=np.zeros(len(x),dtype='uint8');v=k.copy();audit={};day=0
    for number,h in enumerate(sequence):
        borrow=uniform(seeds,total,3*number)<a;pooled=uniform(seeds,total,3*number+1)<l
        # Count intended labels even after absorption/fallback.
        k+=borrow;v+=pooled
        code,x,y,b,record=neighbour_step(pools[h],x,y,code,b,borrow,pooled,uniform(seeds,total,3*number+2),mapper)
        for key,value in record.items():audit[key]=audit.get(key,0)+value
        day+=h
        if trace is not None:trace(day,code.reshape(n,total),record)
    return code.reshape(n,total),k.reshape(n,total),v.reshape(n,total),audit


def contenders(table,family):
    t=table if family=='neighbour' else table.loc[table.alpha.eq(0)]
    best=t.loc[t.S.idxmin()]
    # Estimated Cauchy bound on contrast SE, NOT a certified confidence bound.
    zero=t.unverified_zero_MC if 'unverified_zero_MC' in t else False
    return t.loc[(t.S-best.S<=2*(t.MC_SE+best.MC_SE)+1e-12)|zero].candidate.astype(int).tolist()


def choose(table,horizon,family):
    near=contenders(table,family);t=table.set_index('candidate').loc[near].reset_index()
    t['steps']=t.path.map(lambda p:len(schedules(horizon)[p]))
    row=t.sort_values(['steps','alpha','lambda_value','path'],ascending=[True,True,False,True]).iloc[0]
    return {'candidate':int(row.candidate),'path':row.path,'alpha':float(row.alpha),'lambda_value':float(row.lambda_value),
            'S':float(row.S),'MC_SE':float(row.MC_SE),'numerically_unresolved':len(near)>1,'near_candidates':near}
