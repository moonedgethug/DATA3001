"""Equal-pair adjacent-cell displacement kernels; no new predictors.

The donor selector changes only the virtual source cell and its within-cell
rank. All actual-coordinate propagation, joint velocity, and E/U geometry is
delegated to the existing exact-position implementation.
"""
from functools import lru_cache
import numpy as np
from data3001.modelling.markov_position import step, E, U, BINS
from data3001.modelling.markov_iteration import SCHEDULES
from data3001.preprocessing.prep_core import cells

GRID=tuple(i/10 for i in range(11))
SEVEN={'D1':(1,)*7,'D2':(2,2,2,1),'R2':(1,2,2,2),
       'D3':(3,3,1),'R3':(1,3,3),'D5':(5,2),'R5':(2,5),'D7':(7,)}


def schedules(horizon):
    if isinstance(horizon,bool) or horizon not in [7,30]:raise ValueError('Only 7/30-day horizons authorised')
    return dict(SEVEN if horizon==7 else SCHEDULES)


def candidates(horizon):return [(p,a,l) for p in schedules(horizon) for a in GRID for l in GRID]


def donor_support(pool,states):
    import pandas as pd
    rows=[]
    for cell,b in states:
        for scope,cc in [('self',[cell]),('neighbour',adjacency()[cell])]:
            for conditioning in ['conditional','pooled']:
                chunks=[]
                for c in cc:
                    if c<0:continue
                    key=c*BINS+b
                    start=int(pool.conditional_start[key] if conditioning=='conditional' else pool.cell_start[c])
                    n=int(pool.conditional_count[key] if conditioning=='conditional' else pool.cell_count[c])
                    if n:chunks.append(pool.origins[start:start+n])
                source=np.concatenate(chunks) if chunks else np.empty(0,dtype=int)
                rows.append((cell,b,scope,conditioning,len(source),len(np.unique(pool.obs['id'][source]))))
    return pd.DataFrame(rows,columns=['origin_cell_1','origin_velocity_bin','scope','conditioning','pair_count','independent_donor_ids'])


def prepare_neighbours(pools):
    near=adjacency();valid=near>=0;safe=np.maximum(near,0)
    for p in pools.values():
        if hasattr(p,'_neighbour_cumulative'):continue
        pooled=np.cumsum(p.cell_count[safe]*valid,axis=1)
        conditional=np.cumsum(p.conditional_count.reshape(64800,BINS)[safe]*valid[:,:,None],axis=1).transpose(0,2,1).copy()
        pooled.flags.writeable=False;conditional.flags.writeable=False
        p._neighbour_cumulative=(pooled,conditional)


@lru_cache(maxsize=1)
def adjacency():
    c=np.arange(64800);y,x=np.divmod(c,360)
    result=[]
    for dy in [-1,0,1]:
        for dx in [-1,0,1]:
            if dy or dx:result.append(np.where((y+dy>=0)&(y+dy<180),(y+dy)*360+(x+dx)%360,-1))
    result=np.column_stack(result).astype('int32');result.flags.writeable=False;return result


def donor_selection(pool,codes,velocity,borrow,pooled,uniform):
    codes,velocity,borrow,pooled,uniform=map(np.asarray,(codes,velocity,borrow,pooled,uniform))
    if (codes.ndim!=1 or any(a.shape!=codes.shape for a in [velocity,borrow,pooled,uniform])
            or borrow.dtype!=bool or pooled.dtype!=bool
            or ((uniform<0)|(uniform>=1)|~np.isfinite(uniform)).any()):raise ValueError('Invalid donor selection arrays')
    active=codes>=0
    if ((codes[active]>=64800).any() or ((velocity[active]<0)|(velocity[active]>=BINS)).any()
            or not np.isin(codes[~active],[E,U]).all()):raise ValueError('Invalid joint state')
    virtual=codes.astype('int32').copy();u=uniform.astype(float).copy()
    unsupported=np.zeros(len(codes),bool);backoff=unsupported.copy()
    ix=np.flatnonzero(active&borrow)
    if not len(ix):return virtual,u,unsupported,backoff
    near=adjacency()[codes[ix]];valid=near>=0;safe=np.maximum(near,0)
    cached=getattr(pool,'_neighbour_cumulative',None)
    if cached is None:
        specific=pool.conditional_count[safe*BINS+velocity[ix,None]]*valid
        missing=specific.sum(axis=1)==0
        cum=np.cumsum(np.where((pooled[ix]|missing)[:,None],pool.cell_count[safe]*valid,specific),axis=1)
    else:
        pc,cc=cached;specific=cc[codes[ix],velocity[ix]];missing=specific[:,-1]==0
        cum=np.where((pooled[ix]|missing)[:,None],pc[codes[ix]],specific)
    backoff[ix]=missing;total=cum[:,-1];bad=total==0;unsupported[ix[bad]]=True;virtual[ix[bad]]=U
    use=~bad;good=ix[use];cum=cum[use];near=near[use];total=total[use]
    if len(good):
        rank=(uniform[good]*total).astype('int64')
        column=(rank[:,None]>=cum).sum(axis=1)
        before=np.where(column==0,0,cum[np.arange(len(good)),np.maximum(column-1,0)])
        n=cum[np.arange(len(good)),column]-before
        virtual[good]=near[np.arange(len(good)),column]
        u[good]=(rank-before+.5)/n
    return virtual,u,unsupported,backoff


def neighbour_step(pool,lon,lat,codes,velocity,borrow,pooled,uniform,mapper):
    virtual,u,unsupported,backoff=donor_selection(pool,codes,velocity,borrow,pooled,uniform)
    # A missing conditional UNION must use the pooled union. The chosen virtual
    # cell's own conditional availability must not undo that aggregate fallback.
    force_pool=np.asarray(pooled)|backoff
    nb=np.asarray(velocity).copy();nb[unsupported]=U
    result=step(pool,lon,lat,virtual,nb,.5,np.where(force_pool,0.,.75),u,mapper,precise=True)
    record=result[-1]
    record.update(neighbour_active=int(((np.asarray(codes)>=0)&borrow).sum()),
                  neighbour_unsupported=int(unsupported.sum()),neighbour_backoff=int((backoff&~unsupported).sum()))
    record['unsupported_cell']+=int(unsupported.sum())
    record['active']+=int(unsupported.sum())
    return result


def forecast(pools,lon,lat,velocity,sequence,alpha,lam,particles,seed,mapper,trace=None):
    if (sum(sequence) not in [7,30] or any(h not in pools for h in sequence)
            or not 0<=alpha<=1 or not 0<=lam<=1 or particles<2):raise ValueError('Invalid neighbour forecast')
    lon,lat,b=map(np.asarray,(lon,lat,velocity));n=len(lon)
    if lon.ndim!=1 or lat.shape!=lon.shape or b.shape!=lon.shape:raise ValueError('Invalid query arrays')
    x=np.repeat(lon,particles).astype(float);y=np.repeat(lat,particles).astype(float)
    b=np.repeat(b,particles).astype('int8');code=cells(x,y);rng=np.random.default_rng(seed);audit={};day=0
    for h in sequence:
        borrow=rng.random(n*particles)<alpha;pooled=rng.random(n*particles)<lam
        code,x,y,b,record=neighbour_step(pools[h],x,y,code,b,borrow,pooled,rng.random(n*particles),mapper)
        for k,v in record.items():audit[k]=audit.get(k,0)+v
        day+=h
        if trace is not None:trace(day,code.reshape(n,particles),record)
    return code.reshape(n,particles),audit
