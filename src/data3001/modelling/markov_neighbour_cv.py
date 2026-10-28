"""Same-case grouped-ID CV with fresh joint proposals at every precision call."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import threading
import numpy as np
import pandas as pd
from data3001.modelling.markov_neighbour import candidates,schedules,prepare_neighbours
from data3001.modelling.markov_neighbour_native import score_counts
from data3001.modelling.markov_neighbour_integration import (
    proposal_forecast,likelihood_weights,weighted_scores,query_seeds,
    weight_table,
)

IDENTITY=['candidate','path','alpha','lambda_value']
TOTALS=['case_count','loss_sum_0','loss_sum_1','repeat_diff_square']


def combine(tables):
    if not tables:raise ValueError('No CV roles')
    base=tables[0][IDENTITY].reset_index(drop=True);totals=None
    for t in tables:
        if not t[IDENTITY].reset_index(drop=True).equals(base):raise ValueError('Candidate definitions differ across roles')
        if not t.case_count.nunique()==1 or (t.case_count<=0).any():raise ValueError('Unequal/empty candidate cases')
        totals=t[TOTALS].reset_index(drop=True).copy() if totals is None else totals+t[TOTALS].reset_index(drop=True)
    result=pd.concat([base,totals],axis=1)
    result['S']=(result.loss_sum_0+result.loss_sum_1)/(2*result.case_count)
    result['MC_SE']=np.sqrt(result.repeat_diff_square)/(2*result.case_count)
    result['unverified_zero_MC']=result.MC_SE.eq(0)
    return result


def score_role(pools,obs,bins,part,horizon,indices,r,mapper,role,nonce,*,method='centred',workers=4,batch_size=32,
               engineering_profile=False,progress=print):
    if method not in ['centred','uncentred'] or part.empty or part.duplicated(['id','origin_source_obs']).any():raise ValueError('Invalid CV queries')
    fit=next(iter(pools.values())).fitting_ids;held=set(part.id)
    if any(p.fitting_ids!=fit for p in pools.values()):raise ValueError('Kernel fitting rosters differ')
    if engineering_profile:
        if not held<=fit:raise ValueError('Resource profile must use fitting IDs')
    elif fit&held:raise ValueError('Held-out IDs appear in donor pools')
    grid=candidates(horizon);groups={}
    prepare_neighbours(pools)
    for i in indices:
        path,a,l=grid[i];groups.setdefault(path,[]).append((i,a,l))
    part=part.sort_values(['id','origin_source_obs']).reset_index(drop=True);local=threading.local()
    def task(start):
        if not hasattr(local,'mapper'):local.mapper=mapper.worker_copy()
        batch=part.iloc[start:start+batch_size];ix=batch.origin.to_numpy();truth=batch.destination_cell_1.to_numpy()
        rows=[];idrows=[];audits={};precision=[]
        for path,items in groups.items():
            targets=[(a,l) for _,a,l in items];seq=schedules(horizon)[path]
            numerical_grid=[0.,.1,.3,.5,.7,.9,1.]
            proposal=[(a,l) for a in numerical_grid for l in numerical_grid] if r==2 and nonce==0 and len(targets)==121 else targets
            actual_r=max(r,int(np.ceil((64*r if r>2 else 0)/len(proposal))))
            layout=hashlib.sha256(repr((proposal,actual_r,nonce)).encode()).hexdigest()[:20]
            values=[];other=[]
            for repeat in range(2):
                seed=query_seeds(role+f'|{horizon}|{path}',batch.id,batch.origin_source_obs,repeat,layout)
                draw,k,l,record=proposal_forecast(pools,obs['lon'][ix],obs['lat'][ix],bins[ix],seq,proposal,actual_r,seed,local.mapper)
                s=score_counts(draw,truth,k,l,len(seq),proposal,actual_r,targets=targets)
                values.append(s['S_integration' if method=='centred' else 'S_uncentred'])
                other.append(s['S_uncentred' if method=='centred' else 'S_integration'])
                bound=float(weight_table(len(seq),tuple(proposal),tuple(targets)).max())
                precision.append({'path':path,'repeat':repeat,'max_weight_bound':bound,'target_count':len(targets),
                    'mean_mass_estimate':float(s['mass_estimate'].mean()),'proposal_components':len(proposal),'per_component':actual_r})
                for key,v in record.items():audits[key]=audits.get(key,0)+v
            a,b=values;oa,ob=other;delta=a-b
            id_groups=[(int(sid),batch.id.eq(sid).to_numpy()) for sid in batch.id.unique()]
            for j,(candidate,alpha,lam) in enumerate(items):
                rows.append((candidate,path,alpha,lam,len(batch),float(a[:,j].sum()),float(b[:,j].sum()),float((delta[:,j]**2).sum())))
            for sid,mask in id_groups:
                sa=a[mask].sum(axis=0);sb=b[mask].sum(axis=0);n=int(mask.sum())
                idrows.extend((sid,candidate,n,float(sa[j]),float(sb[j])) for j,(candidate,_,_) in enumerate(items))
            audits['centred_repeat_difference_square']=audits.get('centred_repeat_difference_square',0.)+float(((a-b if method=='centred' else oa-ob)**2).sum())
            audits['uncentred_repeat_difference_square']=audits.get('uncentred_repeat_difference_square',0.)+float(((oa-ob if method=='centred' else a-b)**2).sum())
        table=pd.DataFrame(rows,columns=IDENTITY+TOTALS).sort_values('candidate').reset_index(drop=True)
        return table,idrows,audits,precision
    tables=[];idrows=[];audits={};precision=[];starts=list(range(0,len(part),batch_size))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for number,(table,ids,a,p) in enumerate(executor.map(task,starts),1):
            tables.append(table);idrows.extend(ids);precision.extend(p)
            for key,value in a.items():audits[key]=audits.get(key,0)+value
            if number%100==0 or number==len(starts):progress(f'{role} H{horizon}: {number}/{len(starts)} batches; {len(indices)} candidates; r{r}',flush=True)
    total=combine(tables)
    ids=pd.DataFrame(idrows,columns=['id','candidate','case_count','loss_sum_0','loss_sum_1']).groupby(['id','candidate'],as_index=False).sum()
    return total,ids,{'sampler_counts_not_target_mass':audits,'precision':precision,
        'query_rng':'native-ID/source-key keyed, batch/worker invariant','engineering_profile_not_CV':engineering_profile}
