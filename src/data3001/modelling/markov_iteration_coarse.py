"""Exact coordinate-discarded control from the same fitting donor frequencies."""
from dataclasses import dataclass,field
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix,diags
from data3001.modelling.markov_velocity import marginal_locations
from data3001.modelling.markov_iteration import SCHEDULES,candidates


@dataclass
class CoarseKernel:
    cells:tuple
    local:object
    pooled:object
    row_pairs:np.ndarray
    training_ids:frozenset
    lag_days:int
    cache:dict=field(default_factory=dict)

    def matrix(self,lam):
        if not 0<=lam<=1:raise ValueError('Invalid lambda')
        if lam not in self.cache:
            n=len(self.cells)*9;w=lam+(1-lam)*(self.row_pairs==0)
            projection=csr_matrix((w,(np.arange(n),np.arange(n)//9)),shape=(n+2,len(self.cells)))
            absorbers=csr_matrix(([1.,1.],([n,n+1],[n,n+1])),shape=(n+2,n+2))
            self.cache[lam]=((1-lam)*self.local+projection@self.pooled+absorbers).tocsr()
        return self.cache[lam]


def coarse_kernel(pool,state_cells):
    cells=tuple(int(c) for c in state_cells);n=len(cells)*9
    lookup=np.full(64800,-1,dtype='int32');lookup[list(cells)]=np.arange(len(cells))
    o=pool.origins;e=pool.endpoints
    row=(lookup[pool.obs['cell'][o]]*9+pool.bins[o]).astype('int32')
    col=np.full(len(e),n,dtype='int32');known=e>=0
    col[known]=lookup[pool.obs['cell'][e[known]]]*9+pool.bins[e[known]]
    if (row<0).any() or (col<0).any():raise ValueError('Donor state absent from frozen D index')
    counts=csr_matrix((np.ones(len(o)),(row,col)),shape=(n+2,n+2));del row,col
    totals=np.asarray(counts.sum(axis=1)).ravel();scale=np.zeros(n+2);scale[totals>0]=1/totals[totals>0]
    local=diags(scale)@counts
    aggregate=csr_matrix((np.ones(n),(np.arange(n)//9,np.arange(n))),shape=(len(cells),n+2))
    pooled=aggregate@counts;ct=np.asarray(pooled.sum(axis=1)).ravel();s=np.zeros(len(cells));s[ct>0]=1/ct[ct>0]
    pooled=diags(s)@pooled
    unsupported=np.flatnonzero(ct==0)
    pooled=pooled+csr_matrix((np.ones(len(unsupported)),(unsupported,np.full(len(unsupported),n+1))),shape=pooled.shape)
    np.testing.assert_array_equal(totals[:n],pool.conditional_count[np.repeat(cells,9)*9+np.tile(np.arange(9),len(cells))])
    return CoarseKernel(cells,local.tocsr(),pooled.tocsr(),totals[:n],pool.fitting_ids,pool.lag_days)


def _initial(kernels,origins):
    op=next(iter(kernels.values()));index={c:i for i,c in enumerate(op.cells)};n=len(op.cells)*9
    if any(c not in index or not 0<=b<9 for c,b in origins):raise ValueError('Unknown origin state')
    columns=[index[c]*9+b for c,b in origins]
    return csr_matrix((np.ones(len(origins)),(np.arange(len(origins)),columns)),shape=(len(origins),n+2))


def coarse_predictions(kernels,origins,sequence,lam):
    p=_initial(kernels,origins)
    for h in sequence:p=p@kernels[h].matrix(lam)
    np.testing.assert_allclose(np.asarray(p.sum(axis=1)).ravel(),1,atol=1e-10,rtol=0)
    return marginal_locations(p,next(iter(kernels.values())).cells)


def coarse_scores(kernels,part,grid=None,schedules=None,workers=1):
    grid=candidates() if grid is None else list(grid);schedules=SCHEDULES if schedules is None else schedules
    group=part.groupby(['origin_cell_1','origin_velocity_bin','destination_cell_1'],as_index=False).size()
    origins=sorted(set(zip(group.origin_cell_1.astype(int),group.origin_velocity_bin.astype(int))))
    origin_index={v:i for i,v in enumerate(origins)};op=next(iter(kernels.values()));nc=len(op.cells);n=nc*9
    lookup={c:i for i,c in enumerate(op.cells)};row=np.array([origin_index[int(c),int(b)] for c,b in zip(group.origin_cell_1,group.origin_velocity_bin)])
    dest=np.array([nc if c==-2 else lookup[int(c)] for c in group.destination_cell_1])
    projection=csr_matrix((np.ones(n+2),(np.arange(n+2),np.r_[np.arange(n)//9,nc,nc+1])),shape=(n+2,nc+2))
    initial=_initial(kernels,origins);losses={};case_weight=group['size'].to_numpy()
    def one_lambda(lam):
        result={}
        tree={}
        for i,(path,value) in enumerate(grid):
            if value!=lam:continue
            node=tree
            for h in schedules[path]:node=node.setdefault(h,{})
            node.setdefault('leaves',[]).append(i)
        def walk(q,node):
            if 'leaves' in node:
                loc=(q@projection).tocsr();base=1+np.asarray(loc.multiply(loc).sum(axis=1)).ravel()
                truth=np.asarray(loc[row,dest]).ravel();loss=float(case_weight@(base[row]-2*truth))
                for i in node['leaves']:result[i]=loss
            for h,child in node.items():
                if h!='leaves':walk(q@kernels[h].matrix(lam),child)
        walk(initial,tree)
        return result
    if workers not in [1,2,4]:raise ValueError('Unapproved numerical worker count')
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for result in executor.map(one_lambda,sorted({l for p,l in grid})):losses.update(result)
    return pd.DataFrame([{'candidate':i,'path':path,'lambda_value':lam,'case_count':len(part),
                          'loss_sum':losses[i],'S':losses[i]/len(part)} for i,(path,lam) in enumerate(grid)])
