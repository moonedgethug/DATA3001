"""Same empirical transport law; explicit schedules and unbiased CV scoring."""
from numbers import Integral
import numpy as np
import pandas as pd

from data3001.modelling.markov_position import step
from data3001.preprocessing.prep_core import cells

SCHEDULES={
    'D1':(1,)*30,'D2':(2,)*15,'D3':(3,)*10,'D5':(5,)*6,
    'D7':(7,7,7,7,2),'R7':(2,7,7,7,7),
    'W3':(3,3,1)*4+(2,),'W5':(5,2)*4+(2,),'W5R':(2,5)*4+(2,),
}
LAMBDAS=tuple(i/10 for i in range(11))


def validate_schedule(sequence,horizon=30):
    values=tuple(sequence)
    if (not values or any(isinstance(h,bool) or not isinstance(h,Integral) or h not in [1,2,3,5,7] for h in values)
            or sum(values)!=horizon):
        raise ValueError('Schedule must use cached positive integer lags and sum to the exact horizon')
    return values


def candidates():return [(path,lam) for path in SCHEDULES for lam in LAMBDAS]


def forecast_schedule(pools,lon,lat,velocity,sequence,lam,particles,seed,mapper,*,precise=True,trace=None):
    sequence=validate_schedule(sequence)
    if particles<2 or int(particles)!=particles or not np.isfinite(lam) or not 0<=lam<=1:
        raise ValueError('Invalid integration or mixture setting')
    if any(h not in pools for h in sequence):raise ValueError('Missing schedule kernel')
    lon,lat,b=map(np.asarray,(lon,lat,velocity))
    if lon.ndim!=1 or lon.shape!=lat.shape or lon.shape!=b.shape:raise ValueError('Unequal origin arrays')
    x=np.repeat(lon,particles).astype(float);y=np.repeat(lat,particles).astype(float)
    b=np.repeat(b,particles).astype('int8');code=cells(x,y);rng=np.random.default_rng(seed);audit={};day=0
    for h in sequence:
        code,x,y,b,record=step(pools[h],x,y,code,b,lam,rng.random(len(x)),rng.random(len(x)),mapper,precise=precise)
        day+=h
        for key,value in record.items():audit[key]=audit.get(key,0)+value
        if trace is not None:trace(day,code.reshape(-1,particles),record)
    return code.reshape(-1,particles),audit


def fast_scores(draws,truth):
    draws=np.asarray(draws);truth=np.asarray(truth)
    if (draws.ndim!=2 or draws.shape[1]<2 or truth.shape!=(len(draws),)
            or not np.issubdtype(draws.dtype,np.integer)
            or not (((draws>=0)&(draws<64800))|(draws==-2)|(draws==-3)).all()
            or not (((truth>=0)&(truth<64800))|(truth==-2)).all()):
        raise ValueError('Invalid forecast/observed states')
    n,m=draws.shape
    if not n:return {k:np.empty(0) for k in ['S_integration','S_issued','true_probability_issued','U_mass','E_mass']}
    sorted_=np.sort(draws,axis=1).ravel();change=sorted_[1:]!=sorted_[:-1]
    change[np.arange(m-1,n*m-1,m)]=True
    starts=np.r_[0,np.flatnonzero(change)+1,n*m];cnt=np.diff(starts)
    collision=np.bincount(starts[:-1]//m,weights=cnt*(cnt-1),minlength=n)
    p=np.sum(draws==truth[:,None],axis=1)/m
    return {'S_integration':1-2*p+collision/(m*(m-1)),
            'S_issued':1-2*p+(collision+m)/m**2,'true_probability_issued':p,
            'U_mass':np.sum(draws==-3,axis=1)/m,'E_mass':np.sum(draws==-2,axis=1)/m}


def candidate_statistics(scores,grid=None):
    grid=candidates() if grid is None else list(grid);scores=np.asarray(scores,float)
    if scores.ndim!=3 or scores.shape[:2]!=(len(grid),2) or not scores.shape[2] or not np.isfinite(scores).all():
        raise ValueError('Every candidate needs both independent repeats on identical nonempty cases')
    n=scores.shape[2];difference=scores[:,0]-scores[:,1]
    table=pd.DataFrame({'candidate':np.arange(len(grid)),'path':[p for p,l in grid],
        'lambda_value':[l for p,l in grid],'case_count':n,
        'loss_sum_0':scores[:,0].sum(axis=1),'loss_sum_1':scores[:,1].sum(axis=1)})
    table['S']=(table.loss_sum_0+table.loss_sum_1)/(2*n)
    return table,difference@difference.T


def near_best(stats,gram):
    if not stats.case_count.nunique()==1 or not stats.candidate.is_unique:raise ValueError('Candidate cases differ')
    values=stats.S.to_numpy();gram=np.asarray(gram);n=int(stats.case_count.iloc[0])
    if gram.shape!=(len(stats),len(stats)) or not np.isfinite(gram).all():raise ValueError('Invalid MC crossproducts')
    best=int(np.argmin(values));variance=np.maximum(0,np.diag(gram)+gram[best,best]-2*gram[:,best])
    se=np.sqrt(variance)/(2*n)
    return np.flatnonzero(values-values[best]<=2*se+1e-12).tolist()


def choose_candidate(stats,gram,allow_tie):
    close=near_best(stats,gram);selected=stats.iloc[close].copy()
    if len(close)>1 and not allow_tie:
        selected=stats.loc[stats.S.eq(stats.S.min())].copy()
    selected['steps']=selected.path.map(lambda p:len(SCHEDULES[p]))
    if allow_tie:selected=selected.sort_values(['steps','lambda_value','path'],ascending=[True,False,True])
    else:selected=selected.sort_values(['S','steps','lambda_value','path'],ascending=[True,True,False,True])
    r=selected.iloc[0]
    return {'candidate':int(r.candidate),'path':r.path,'lambda_value':float(r.lambda_value),
            'S':float(r.S),'numerically_unresolved':len(close)>1,'near_candidates':[int(stats.iloc[i].candidate) for i in close]}
