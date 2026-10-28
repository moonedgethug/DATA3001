"""All-path lambda CV; no fixed-lambda elimination or held-ID tuning."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import threading
import numpy as np
import pandas as pd
from data3001.modelling.markov_iteration import (
    SCHEDULES,candidates,forecast_schedule,fast_scores,candidate_statistics,
)


def seed_for(role,sid,source_obs,repeat,particles):
    data=f'20261027|{role}|{int(sid)}|{int(source_obs)}|{repeat}|{particles}'.encode()
    return int.from_bytes(hashlib.blake2b(data,digest_size=8).digest(),'little')


def combine_roles(values):
    if not values:raise ValueError('No CV roles')
    base=values[0][0][['candidate','path','lambda_value']].reset_index(drop=True)
    total=None;gram=np.zeros_like(values[0][1],dtype=float)
    for table,g in values:
        if not table[['candidate','path','lambda_value']].reset_index(drop=True).equals(base):
            raise ValueError('Every inner role must score the same candidate grid')
        if not table.case_count.nunique()==1 or (table.case_count<=0).any():raise ValueError('Candidates do not share inner cases')
        cols=table[['case_count','loss_sum_0','loss_sum_1']].reset_index(drop=True)
        total=cols.copy() if total is None else total+cols
        gram+=g
    out=pd.concat([base,total],axis=1);out['S']=(out.loss_sum_0+out.loss_sum_1)/(2*out.case_count)
    return out,gram


def pair_MC_se(a,b,cov):
    if a['m']!=b['m']:return np.sqrt(a['variance']+b['variance'])
    key=(a['call'],int(a['row'].candidate),int(b['row'].candidate))
    if a['call']!=b['call'] or key not in cov:
        return np.sqrt(a['variance'])+np.sqrt(b['variance'])
    return np.sqrt(max(0.,a['variance']+b['variance']-2*cov[key]))


def select_search(evaluator,grid=None):
    """Evaluate all candidates first; refine only numerically unresolved contenders.

    evaluator returns pooled inner-only statistics and paired MC crossproducts.
    No outer observation is an argument to this function.
    """
    grid=candidates() if grid is None else list(grid);pool={};cov={};history=[]
    def evaluate(indices,m):
        table,gram=evaluator(indices,m)
        if table.candidate.tolist()!=indices or len(table)!=len(indices):raise ValueError('Requested candidates missing')
        n=int(table.case_count.iloc[0])
        if not table.case_count.eq(n).all() or not np.isfinite(table.S).all():raise ValueError('Invalid CV scores/cases')
        call=len(history)
        for j,r in enumerate(table.itertuples()):
            pool[int(r.candidate)]={'row':r,'m':m,'call':call,'variance':max(0.,float(gram[j,j]))/(4*n*n)}
        for j,a in enumerate(indices):
            for k,b in enumerate(indices):cov[call,a,b]=float(gram[j,k])/(4*n*n)
        history.append({'particles':m,'candidates':indices.copy()})
    def close_set():
        best=min(pool,key=lambda i:pool[i]['row'].S);b=pool[best];close=[]
        for i,r in pool.items():
            se=pair_MC_se(r,b,cov)
            if r['row'].S-b['row'].S<=2*se+1e-12:close.append(i)
        return sorted(close)
    evaluate(list(range(len(grid))),32)
    for m in [64,128]:
        while True:
            close=close_set()
            if len(close)==1 and pool[close[0]]['m']>=32:break
            if not any(pool[i]['m']<m for i in close):break
            evaluate(close,m)
    close=close_set()
    if len(close)>1:
        best=min(close,key=lambda i:(len(SCHEDULES[grid[i][0]]),-grid[i][1],grid[i][0]))
    else:best=close[0]
    chosen=pool[best]
    return {'candidate':best,'path':grid[best][0],'lambda_value':float(grid[best][1]),
            'S':float(chosen['row'].S),'particles':chosen['m'],'numerically_unresolved':len(close)>1,
            'near_candidates':close,'all_candidates_initially_scored':len(grid)},history


def score_grid(pools,obs,bins,part,indices,particles,mapper,role,*,workers=4,batch_size=512,
               diagnostic_lambda=None,progress=print):
    if workers not in [1,2,4] or particles not in [16,32,64,128]:raise ValueError('Unapproved numerical setting')
    if any(set(part.id)&set(p.fitting_ids) for p in pools.values()):raise ValueError('Held IDs appear in donor pools')
    if part.duplicated(['id','origin_source_obs']).any() or part.empty:raise ValueError('Ambiguous or absent held cases')
    grid=candidates();selected=[grid[i] for i in indices];local=threading.local()
    part=part.sort_values(['id','origin_source_obs']).reset_index(drop=True)
    def calculate(start):
        if not hasattr(local,'mapper'):local.mapper=mapper.worker_copy()
        batch=part.iloc[start:start+batch_size];idx=batch.origin.to_numpy();truth=batch.destination_cell_1.to_numpy()
        values=np.empty((len(indices),2,len(batch)));diag=np.full_like(values,np.nan)
        us=np.zeros((len(indices),2));es=us.copy();audit={}
        for j,(path,lam) in enumerate(selected):
            for rep in range(2):
                seed=seed_for(role,int(batch.id.iloc[0]),int(batch.origin_source_obs.iloc[0]),rep,particles)
                draws,record=forecast_schedule(pools,obs['lon'][idx],obs['lat'][idx],bins[idx],SCHEDULES[path],
                    lam,particles,seed,local.mapper,precise=True)
                scores=fast_scores(draws,truth);values[j,rep]=scores['S_integration']
                us[j,rep]=scores['U_mass'].sum();es[j,rep]=scores['E_mass'].sum()
                for k,v in record.items():audit[k]=audit.get(k,0)+v
                if diagnostic_lambda is not None and lam==diagnostic_lambda and particles>=16:
                    diag[j,rep]=fast_scores(draws[:,:16],truth)['S_integration']
        table,gram=candidate_statistics(values,selected);table['candidate']=indices
        table['U_sum']=(us[:,0]+us[:,1])/2;table['E_sum']=(es[:,0]+es[:,1])/2
        ids=[]
        for sid,g in batch.groupby('id',sort=True):
            mask=batch.id.eq(sid).to_numpy()
            for j,(path,lam) in enumerate(selected):
                ids.append((int(sid),indices[j],int(mask.sum()),float(values[j,0,mask].sum()),float(values[j,1,mask].sum())))
        d=None
        if diagnostic_lambda is not None:
            use=[j for j,(p,l) in enumerate(selected) if l==diagnostic_lambda]
            if use:
                d,_=candidate_statistics(diag[use],[selected[j] for j in use]);d['candidate']=[indices[j] for j in use]
        return table,gram,ids,d,audit
    parts=[];grams=[];idparts=[];diagnostics=[];audits={};chunks=list(range(0,len(part),batch_size))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for number,(table,gram,ids,diag,audit) in enumerate(executor.map(calculate,chunks),1):
            parts.append(table);grams.append(gram);idparts.extend(ids)
            if diag is not None:diagnostics.append(diag)
            for k,v in audit.items():audits[k]=audits.get(k,0)+v
            if number%20==0 or number==len(chunks):progress(f'{role}: {number}/{len(chunks)} batches; {len(indices)} candidates at{particles}x2',flush=True)
    total,g=combine_roles(list(zip(parts,grams)))
    mass=pd.concat(parts).groupby('candidate')[['U_sum','E_sum']].sum();total=total.join(mass,on='candidate')
    ids=pd.DataFrame(idparts,columns=['id','candidate','case_count','loss_sum_0','loss_sum_1']).groupby(['id','candidate'],as_index=False).sum()
    diag=combine_roles([(d,np.zeros((len(d),len(d)))) for d in diagnostics])[0] if diagnostics else pd.DataFrame()
    return total,g,ids,diag,audits


def score_stratified_grid(pools,obs,bins,part,indices,target,mapper,role,*,workers=4,batch_size=256,
                          diagnostic_lambda=None,progress=print,engineering_profile=False):
    """Same99 CV targets, shared count-conditioned integration within each path.

    Different paths/allocation layouts have separate RNG streams. This prevents
    cross-query coupling when particle layouts differ, preserving casewise MCSE.
    """
    from data3001.modelling.markov_iteration_strata import (
        weights_for,allocations,stratified_forecast,stratified_scores,substrata,
    )
    if workers not in [1,2,4] or target not in [32,64,128]:raise ValueError('Invalid numerical profile')
    if engineering_profile:
        if any(not set(part.id)<=set(p.fitting_ids) for p in pools.values()):raise ValueError('Engineering profile must use fitting IDs only')
    elif any(set(part.id)&set(p.fitting_ids) for p in pools.values()):raise ValueError('Fitting/held IDs overlap')
    if part.empty or part.duplicated(['id','origin_source_obs']).any():raise ValueError('Invalid query keys')
    grid=candidates();selected=[grid[i] for i in indices];groups={}
    for j,(path,lam) in enumerate(selected):groups.setdefault(path,[]).append((j,lam))
    local=threading.local();part=part.sort_values(['id','origin_source_obs']).reset_index(drop=True)
    layout={p:allocations(weights_for(len(SCHEDULES[p]),[l for j,l in values]),target).tolist() for p,values in groups.items()}
    def calculate(start):
        if not hasattr(local,'mapper'):local.mapper=mapper.worker_copy()
        batch=part.iloc[start:start+batch_size];idx=batch.origin.to_numpy();truth=batch.destination_cell_1.to_numpy()
        scores=np.empty((len(indices),2,len(batch)));diag=np.full_like(scores,np.nan)
        us=np.zeros((len(indices),2));es=us.copy();audit={}
        for path,items in groups.items():
            positions=[j for j,l in items];lam=[l for j,l in items];w=weights_for(len(SCHEDULES[path]),lam)
            layout_hash=hashlib.sha256(np.asarray(layout[path],dtype='<i4').tobytes()).hexdigest()[:16]
            for rep in range(2):
                seed=seed_for(role+'|'+path+'|'+layout_hash,int(batch.id.iloc[0]),int(batch.origin_source_obs.iloc[0]),rep,target)
                draw,count,record=stratified_forecast(pools,obs['lon'][idx],obs['lat'][idx],bins[idx],SCHEDULES[path],
                    w,target,seed,local.mapper)
                result=stratified_scores(draw,truth,count,w)
                scores[positions,rep]=result['S_integration'].T
                us[positions,rep]=result['U_mass'].sum(axis=0);es[positions,rep]=result['E_mass'].sum(axis=0)
                for key,value in record.items():audit[key]=audit.get(key,0)+value
                if diagnostic_lambda in lam:
                    j=lam.index(diagnostic_lambda);sub_w=w[j:j+1];sub=allocations(sub_w,16)
                    diag[positions[j],rep]=stratified_scores(substrata(draw,count,sub),truth,sub,sub_w)['S_integration'][:,0]
        table,gram=candidate_statistics(scores,selected);table['candidate']=indices
        table['U_sum']=(us[:,0]+us[:,1])/2;table['E_sum']=(es[:,0]+es[:,1])/2
        idrows=[]
        for sid,group in batch.groupby('id',sort=True):
            use=batch.id.eq(sid).to_numpy();sums=scores[:,:,use].sum(axis=2)
            idrows.extend((int(sid),indices[j],int(use.sum()),float(sums[j,0]),float(sums[j,1])) for j in range(len(indices)))
        use=[j for j,(p,l) in enumerate(selected) if l==diagnostic_lambda]
        d=None
        if use:
            d,_=candidate_statistics(diag[use],[selected[j] for j in use]);d['candidate']=[indices[j] for j in use]
        return table,gram,idrows,d,audit
    tables=[];grams=[];idrows=[];diagnostics=[];audits={};starts=list(range(0,len(part),batch_size))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for number,(table,gram,ids,d,audit) in enumerate(executor.map(calculate,starts),1):
            tables.append(table);grams.append(gram);idrows.extend(ids)
            if d is not None:diagnostics.append(d)
            for key,value in audit.items():audits[key]=audits.get(key,0)+value
            if number%20==0 or number==len(starts):progress(f'{role}: {number}/{len(starts)} batches; all{len(indices)} targets, integration target{target}',flush=True)
    total,gram=combine_roles(list(zip(tables,grams)))
    mass=pd.concat(tables).groupby('candidate')[['U_sum','E_sum']].sum();total=total.join(mass,on='candidate')
    ids=pd.DataFrame(idrows,columns=['id','candidate','case_count','loss_sum_0','loss_sum_1']).groupby(['id','candidate'],as_index=False).sum()
    diag=combine_roles([(d,np.zeros((len(d),len(d)))) for d in diagnostics])[0] if diagnostics else pd.DataFrame()
    return total,gram,ids,diag,{'proposal_step_counts_not_target_traffic':audits,'stratum_allocations':layout,
        'query_independence':'different paths/layouts have separate keyed RNG streams',
        'engineering_profile_not_CV':engineering_profile}
