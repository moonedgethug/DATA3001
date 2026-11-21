"""Untouched outer-case evaluation after schedule/lambda choices are locked."""
from concurrent.futures import ThreadPoolExecutor
import threading
import numpy as np
import pandas as pd
from data3001.modelling.markov_models.markov_iteration import SCHEDULES, forecast_schedule
from data3001.modelling.markov_models.markov_iteration_cv import seed_for
from data3001.modelling.common.markov_position_scores import ensemble_scores
from data3001.modelling.markov_models.markov_iteration_coarse import coarse_predictions


def precise_outer(pools,obs,bins,part,variants,fold,mapper,*,particles=64,workers=4,batch_size=256,example_key=None):
    if any(set(part.id)&set(p.fitting_ids) for p in pools.values()):raise ValueError('Outer IDs appear in fitting pools')
    if part.empty or part.duplicated(['id','origin_source_obs']).any():raise ValueError('Outer cases missing/ambiguous')
    part=part.sort_values(['id','origin_source_obs']).reset_index(drop=True);local=threading.local()
    unique={}
    for model,value in variants.items():unique.setdefault(tuple(value),[]).append(model)
    def calculate(start):
        if not hasattr(local,'mapper'):local.mapper=mapper.worker_copy()
        batch=part.iloc[start:start+batch_size];idx=batch.origin.to_numpy();frames=[];audit=[];examples=[]
        for (path,lam),models in unique.items():
            for rep in range(2):
                seed=seed_for(f'outer_{fold}',int(batch.id.iloc[0]),int(batch.origin_source_obs.iloc[0]),rep,particles)
                def trace(day,codes,record):
                    for model in models:audit.append({'outer_fold':fold,'model':model,'repeat':rep,'day':day,
                        'particles':codes.size,'U_particles':int((codes==-3).sum()),'E_particles':int((codes==-2).sum()),
                        **{'step_'+key:int(value) for key,value in record.items()}})
                draw,record=forecast_schedule(pools,obs['lon'][idx],obs['lat'][idx],bins[idx],SCHEDULES[path],lam,
                    particles,seed,local.mapper,precise=True,trace=trace)
                base=ensemble_scores(draw,batch.destination_cell_1.to_numpy())
                for key in ['id','origin_source_obs','origin_cell_1','origin_velocity_bin','destination_cell_1']:
                    base[key]=batch[key].to_numpy()
                base['outer_fold']=fold;base['horizon_days']=30;base['repeat']=rep
                base['path']=path;base['lambda_value']=lam
                for model in models:frames.append(base.assign(model=model))
                if example_key is not None:
                    use=batch.origin_cell_1.eq(example_key[0])&batch.origin_velocity_bin.eq(example_key[1])
                    if use.any():
                        keys,count=np.unique(draw[use],return_counts=True)
                        for model in models:examples.extend((model,rep,int(k),int(n)) for k,n in zip(keys,count))
        return pd.concat(frames,ignore_index=True),audit,examples
    frames=[];audit=[];examples=[]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for number,(frame,a,e) in enumerate(executor.map(calculate,range(0,len(part),batch_size)),1):
            frames.append(frame);audit.extend(a);examples.extend(e)
            if number%40==0:print(f'Outer{fold+1}: {number*batch_size}/{len(part)} origin cases scored',flush=True)
    result=pd.concat(frames,ignore_index=True).sort_values(['model','repeat','id','origin_source_obs']).reset_index(drop=True)
    return result,pd.DataFrame(audit),pd.DataFrame(examples,columns=['model','repeat','destination_cell_1','particles'])


def coarse_outer(kernels,part,variants,fold):
    origins=sorted(set(zip(part.origin_cell_1.astype(int),part.origin_velocity_bin.astype(int))))
    cache={};frames=[];mapping={}
    for model,(path,lam) in variants.items():
        if (path,lam) not in cache:cache[path,lam]=dict(zip(origins,coarse_predictions(kernels,origins,SCHEDULES[path],lam)))
        laws=cache[path,lam]
        for (cell,b),g in part.groupby(['origin_cell_1','origin_velocity_bin'],sort=True):
            p,u=laws[int(cell),int(b)];mapping[model,int(cell),int(b)]=(p,u)
            frame=g.copy();true=frame.destination_cell_1.map(p).fillna(0).to_numpy()
            frame['S_integration']=1-2*true+sum(v*v for v in p.values())+u*u
            frame['S_issued']=frame.S_integration;frame['true_probability_issued']=true
            frame['U_mass']=u;frame['E_mass']=p.get(-2,0.)
            frame['sampled_zero']=np.nan  # analytic structural zero is a different diagnostic
            available=sum(p.values())>=.9-1e-12
            region=set();mass=np.nan;size=np.nan
            if available:
                values=sorted(p.values(),reverse=True);cut=values[min(np.searchsorted(np.cumsum(values),.9-1e-12),len(values)-1)]
                region={k for k,v in p.items() if v>=cut-1e-15};mass=sum(p[k] for k in region);size=sum(k>=0 for k in region)
            frame['region90_available']=available;frame['region90_hit']=frame.destination_cell_1.isin(region)
            frame['region90_cells']=size;frame['region90_mass']=mass
            for key in ['energy_km_issued','mean_squared_km2_issued','linear_quadratic_issued']:frame[key]=np.nan
            frame['outer_fold']=fold;frame['repeat']=0;frame['model']=model;frame['path']=path;frame['lambda_value']=lam
            frames.append(frame)
    return pd.concat(frames,ignore_index=True),mapping


def comparison_intervals(idscores,replicates=200):
    mean=idscores.groupby(['outer_fold','id','model'],as_index=False)[['S_integration_sum','pairs']].mean()
    loss=mean.pivot(index=['outer_fold','id'],columns='model',values='S_integration_sum')
    ns=mean.pivot(index=['outer_fold','id'],columns='model',values='pairs')
    if loss.isna().any().any() or not ns.eq(ns.iloc[:,0],axis=0).all().all():raise ValueError('Outer candidate case sets differ')
    groups=[np.flatnonzero(loss.index.get_level_values(0)==f) for f in sorted(set(loss.index.get_level_values(0)))]
    rng=np.random.default_rng(20261027);draws=[np.concatenate([rng.choice(ix,len(ix),replace=True) for ix in groups]) for _ in range(replicates)]
    rows=[]
    for a,b in [('position-CV','coarse-CV'),('position-CV','position-frozen'),('position-CV','coarse-frozen'),
                ('position-CV','coarse-at-position-settings'),('position-at-coarse-settings','coarse-CV')]:
        delta=(loss[a]-loss[b]).to_numpy();n=ns[a].to_numpy();values=[delta[ix].sum()/n[ix].sum() for ix in draws]
        lo,hi=np.quantile(values,[.025,.975]);rows.append({'comparison':a+' minus '+b,'delta_S':delta.sum()/n.sum(),
            'lower_95':lo,'upper_95':hi,'scope':'fixed_outer_fits_and_selection; adaptive_development; MC separate'})
    return pd.DataFrame(rows)


MC_COMPARISONS=[('position-CV','coarse-CV'),('position-CV','position-frozen'),
    ('position-CV','coarse-frozen'),('position-CV','coarse-at-position-settings'),
    ('position-at-coarse-settings','coarse-CV')]


def outer_MC(scores,comparisons=None):
    comparisons=MC_COMPARISONS if comparisons is None else comparisons
    p=scores.pivot(index=['id','origin_source_obs'],columns=['model','repeat'],values='S_integration');rows=[]
    for a,b in comparisons:
        columns=[(a,0),(a,1) if (a,1) in p else (a,0),(b,0),(b,1) if (b,1) in p else (b,0)]
        if any(c not in p for c in columns) or p[columns].isna().any().any():raise ValueError('MC contrasts have unmatched cases')
        d0=(p[columns[0]]-p[columns[2]]).to_numpy();d1=(p[columns[1]]-p[columns[3]]).to_numpy();n=len(p)
        sumsq=float(np.dot(d0-d1,d0-d1));delta=float((d0+d1).sum()/(2*n));se=np.sqrt(sumsq)/(2*n)
        rows.append({'comparison':a+' minus '+b,'case_count':n,'difference_sum_0':float(d0.sum()),
            'difference_sum_1':float(d1.sum()),'repeat_difference_squares':sumsq,'delta_S':delta,
            'MC_SE':se,'MC_only_lower_95':delta-1.96*se,'MC_only_upper_95':delta+1.96*se,
            'scope':'fixed_queries_and_fits; independent_query_RNG; numerical_only'})
    return pd.DataFrame(rows)
