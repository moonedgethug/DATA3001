"""Fit Gaussian/MDN one-hour kernels with whole-ID parameter CV.

Training/tuning use historical training IDs; previously used historical
validation is the development comparison. No final test trajectory is read.
"""
import argparse
import gc
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from data3001.modelling.continuous_models.continuous import TransitionMixture, mixture_nll, mixture_draw, to_state, to_lonlat, advance, particle_brier
from data3001.modelling.continuous_models.continuous_inputs import PARENT
from data3001.modelling.common.experiment import make_folds
from data3001.modelling.common.runtime import ReadOnlyInputs, save_frame, save_json
from data3001.modelling.markov_models.run_markov import identity, verify_bound
from data3001.modelling.common.geometry import mapper_for
from data3001.modelling.common.runtime import verified_run, _seal
from data3001.paths import project_paths, file_sha256

CONFIG = 'configs/continuous_hourly.json'


def index_for(support, ids):
    parts = [np.arange(r.pair_start,r.pair_end,dtype=np.int32)
             for r in support.loc[support.id.isin(ids)].itertuples() if r.pairs]
    if not parts: raise ValueError('Empty fitting/evaluation population')
    return np.concatenate(parts)


def fit_scaler(values, ix):
    total=np.zeros(8); square=np.zeros(8)
    for start in range(0,len(ix),100000):
        a=values[ix[start:start+100000]].astype(float)
        total+=a.sum(0); square+=(a*a).sum(0)
    mean=total/len(ix); sd=np.sqrt(np.maximum(square/len(ix)-mean**2,1e-16))
    if (sd<=1e-8).any(): raise ValueError('Degenerate fitting scale')
    return mean.astype('float32'),sd.astype('float32')


@torch.no_grad()
def likelihood(model, values, ix, mean, sd, batch):
    model.eval(); total=np.zeros(2)
    for start in range(0,len(ix),batch):
        z=torch.from_numpy((values[ix[start:start+batch]]-mean)/sd)
        out=model(z[:,:4]); target=z[:,4:]
        total[0]+=mixture_nll(out,target).double().sum().item()
        total[1]+=mixture_nll(out,target,2).double().sum().item()
    return total/len(ix)+np.array([np.log(sd[4:]).sum(),np.log(sd[4:6]).sum()])


def fit_model(values, support, fitting, held, candidate, config, seed, epochs=None):
    if set(fitting)&set(held): raise ValueError('ID leakage')
    torch.manual_seed(seed); rng=np.random.default_rng(seed)
    ix=index_for(support,fitting); valid=index_for(support,held) if held else None
    mean,sd=fit_scaler(values,ix)
    model=TransitionMixture(candidate['components'],config['hidden_width'],
                            config['standardized_covariance_floor'])
    optimizer=torch.optim.Adam(model.parameters(),lr=config['learning_rate'])
    logs=[]; best=float('inf'); best_state=None; best_epoch=0; stale=0
    begun=time.monotonic(); maximum=epochs or config['max_epochs']
    for epoch in range(1,maximum+1):
        rng.shuffle(ix); model.train(); total=0.
        for start in range(0,len(ix),config['batch_size']):
            z=torch.from_numpy((values[ix[start:start+config['batch_size']]]-mean)/sd)
            optimizer.zero_grad(set_to_none=True)
            nll=mixture_nll(model(z[:,:4]),z[:,4:]).mean()
            penalty=candidate['l2']*sum(p.square().sum() for name,p in model.named_parameters() if name.endswith('weight'))
            loss=nll+penalty
            if not torch.isfinite(loss): raise ValueError('Nonfinite training objective')
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),10.)
            optimizer.step(); total+=nll.item()*len(z)
        score=likelihood(model,values,valid,mean,sd,config['batch_size']) if valid is not None else None
        current=float(score[0]) if score is not None else float(total/len(ix))
        if current < best-config['early_stop_min_delta'] or score is None:
            best=current; best_epoch=epoch; stale=0
            best_state={k:v.detach().clone() for k,v in model.state_dict().items()}
        else: stale+=1
        logs.append({'epoch':epoch,'training_standardized_NLL':total/len(ix),
                     'held_joint_NLL':float(score[0]) if score is not None else None,
                     'held_position_NLL':float(score[1]) if score is not None else None,
                     'elapsed_seconds':time.monotonic()-begun})
        print(f"  {candidate['name']} epoch {epoch}/{maximum}: train NLL {total/len(ix):.4f}; held {current:.4f}; {time.monotonic()-begun:.1f}s",flush=True)
        if score is not None and stale>=config['early_stop_patience']: break
    model.load_state_dict(best_state); model.eval()
    return model,mean,sd,{'best_epoch':best_epoch,'epochs_executed':epoch,
        'epoch_cap_reached':epoch==maximum,'fitting_pairs':len(ix),
        'held_pairs':len(valid) if valid is not None else 0,'logs':logs,
        'fitting_ids':sorted(map(int,fitting)),'held_ids':sorted(map(int,held)),
        'candidate':candidate,'seed':seed}


def save_model(paths, prefix, model, mean, sd, info):
    paths.publish(prefix.with_suffix('.pt'),lambda f:torch.save({
        'state_dict':model.state_dict(),'mean':torch.from_numpy(mean),'sd':torch.from_numpy(sd),
        'components':model.components,'width':model.width,'floor':model.floor},f))
    save_json(paths,prefix.with_suffix('.json'),info)


def load_model(prefix):
    c=torch.load(prefix.with_suffix('.pt'),map_location='cpu',weights_only=True)
    m=TransitionMixture(c['components'],c['width'],c['floor']);m.load_state_dict(c['state_dict']);m.eval()
    return m,c['mean'].numpy(),c['sd'].numpy()


@torch.no_grad()
def rollout(model, mean, sd, states, mapper, particles, seed, hours=(168,720)):
    """Free rollout: only generated states enter later steps. E and U absorb."""
    if not np.isfinite(states).all(): raise ValueError('Invalid initial state')
    torch.manual_seed(seed)
    n=len(states); s=torch.from_numpy(np.repeat(states.astype('float32'),particles,axis=0))
    mean=torch.from_numpy(mean);sd=torch.from_numpy(sd)
    status=np.zeros(len(s),dtype=np.int32); result={}
    for step in range(1,max(hours)+1):
        active=np.flatnonzero(status==0)
        if len(active):
            state=s[active]; out=model((state-mean[:4])/sd[:4])
            delta=mixture_draw(out)*sd[4:]+mean[4:]
            nxt=advance(state,delta); s[active]=nxt
            xy=to_lonlat(nxt.numpy()); mapped=mapper(xy[:,0],xy[:,1])
            invalid=~np.isfinite(nxt.numpy()).all(axis=1)
            mapped[invalid]=-1
            status[active[mapped==-2]]=-2
            status[active[mapped==-1]]=-3
        if step in hours:
            cells=status.copy(); alive=np.flatnonzero(status==0)
            if len(alive):
                xy=to_lonlat(s[alive].numpy()); cells[alive]=mapper(xy[:,0],xy[:,1])
            if (cells==-1).any(): raise ValueError('Unmapped active state')
            result[step]=cells.reshape(n,particles)
        if not len(active):
            for h in hours:
                if h>=step:result[h]=status.reshape(n,particles).copy()
            break
    return result


def forecast_queries(paths, prefix, model, mean, sd, releases, obs, mapper, particles, seed, config):
    """Every eligible release is evaluated; share simulated path across horizons."""
    if prefix.with_suffix('.parquet').exists():
        return pd.read_parquet(prefix.with_suffix('.parquet'))
    ids=np.sort(releases.origin.unique()); batch=max(1,config['forecast_batch_particles']//particles)
    predictions={7:[],30:[]}; outputs=[]; start=time.monotonic()
    lookup={h:g.set_index('origin') for h,g in releases.groupby('horizon_days')}
    for b in range(0,len(ids),batch):
        ix=ids[b:b+batch]; source=obs[ix]
        states=to_state(source['lon'],source['lat'],source['ve'],source['vn'])
        forecasts=rollout(model,mean,sd,states,mapper,particles,seed+b,(168,720))
        for h in (7,30):
            mask=np.isin(ix,lookup[h].index); draws=forecasts[h*24][mask]
            q=lookup[h].loc[ix[mask]].reset_index()
            q['S']=particle_brier(draws,q.destination_cell_1.to_numpy())
            q['E_mass']=(draws==-2).mean(1); q['U_mass']=(draws==-3).mean(1)
            q['sampled_zero']=(draws==q.destination_cell_1.to_numpy()[:,None]).sum(1)==0
            outputs.append(q)
            predictions[h].append(draws.astype('int32'))
        if b==0 or (b//batch+1)%8==0 or b+batch>=len(ids):
            print(f'  Rollout {prefix.name}: {min(b+batch,len(ids)):,}/{len(ids):,} origins; {time.monotonic()-start:.1f}s',flush=True)
    table=pd.concat(outputs,ignore_index=True).sort_values(['horizon_days','origin']).reset_index(drop=True)
    save_frame(paths,prefix.with_suffix('.parquet'),table)
    for h in (7,30):
        a=np.concatenate(predictions[h]); order=np.concatenate([g.origin.to_numpy() for g in outputs if len(g) and int(g.horizon_days.iloc[0])==h]).argsort()
        a=a[order]
        paths.publish(prefix.parent/(prefix.name+f'_{h}d.npy'),lambda f:np.save(f,a))
    return table


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input-run',required=True)
    parser.add_argument('--resume');parser.add_argument('--benchmark',action='store_true')
    args=parser.parse_args();paths=project_paths();c=json.loads((paths.root/CONFIG).read_text())
    if c['step_hours']!=1 or c['features']!=['lon','lat','ve','vn'] or c['final_test_access']:
        raise ValueError('Frozen continuous scope violated')
    torch.set_num_threads(c['cpu_threads']);torch.use_deterministic_algorithms(True)
    data,bound=identity(paths);receipt=verified_run(paths,args.input_run)
    cache_config=json.loads((receipt.parent/'run.json').read_text())['config']
    for rel,sha in cache_config['input_sha256'].items():
        if file_sha256(paths.root/rel)!=sha:raise ValueError('Prepared input identity changed')
    bound[CONFIG]=file_sha256(paths.root/CONFIG);bound[str(receipt.relative_to(paths.root))]=file_sha256(receipt)
    sources={str(p.relative_to(paths.root)):file_sha256(p) for p in [
        paths.root/'src/data3001/modelling/continuous_models/continuous.py',Path(__file__).resolve()]}
    if args.resume:
        run={'results':paths.root/'results/runs'/args.resume,'provenance':paths.root/'provenance/runs'/args.resume}
        old=json.loads((run['provenance']/'run.json').read_text())['config']
        if old['input_sha256']!=bound or old['source_sha256']!=sources or old['benchmark']!=args.benchmark:
            raise ValueError('Resume must use identical sources and inputs')
    else:
        name=datetime.now(timezone.utc).strftime(('continuous_pilot_' if args.benchmark else 'continuous_cv_')+'%Y%m%dT%H%M%S_%fZ')
        run=paths.create_run(name,{**c,'input_sha256':bound,'source_sha256':sources,
            'input_run':args.input_run,'benchmark':args.benchmark,'torch':torch.__version__})
    print('RUN='+run['results'].name,flush=True)
    guard=ReadOnlyInputs(paths.root,run,data_root=paths.data_root);sys.addaudithook(guard)
    try:
        root=paths.root/'results/runs'/args.input_run
        schema=json.loads((root/'schema.json').read_text());values=np.memmap(root/'pairs.float32',mode='r',dtype='<f4',shape=tuple(schema['shape']))
        support=pd.read_csv(root/'ID_support.csv')
        parent=paths.root/'results/runs'/PARENT
        obs=np.load(parent/'observations.npy',mmap_mode='r')
        releases=pd.read_parquet(parent/'releases.parquet');releases=releases.loc[releases.reason_code.eq(0)].copy()
        train=set(support.loc[support.historical_split.eq('train'),'id']);valid=set(support.loc[support.historical_split.eq('validation'),'id'])
        expected={int(i) for i,r in data['records'].items() if r['pool']=='train'}
        if train&valid or train|valid!=expected:raise ValueError('Development split does not reconcile')
        fold=make_folds(sorted(train),n_splits=c['cv_folds'],tag='continuous-hourly-v1',seed=c['seed'])
        roles=pd.DataFrame([{'id':i,'role':'train_CV' if i in train else 'historical_validation','fold':fold.get(i,-1)} for i in sorted(expected)])
        if not (run['results']/'roles.csv').exists():save_frame(paths,run['results']/'roles.csv',roles)
        mapper=mapper_for(paths)
        if args.benchmark:
            held={i for i in train if fold[i]==0};fitting=train-held
            mc,mu,sd,info=fit_model(values,support,fitting,held,c['candidates'][-1],{**c,'max_epochs':1},c['seed'])
            q=releases.loc[releases.id.isin(held)].copy();chosen=np.sort(q.origin.unique())[:256];q=q.loc[q.origin.isin(chosen)]
            forecast_queries(paths,run['results']/'pilot',mc,mu,sd,q,obs,mapper,c['cv_particles'],c['seed'],c)
            save_json(paths,run['results']/'training.json',info)
        else:
            cv=[];fitinfo=[]
            for k in range(c['cv_folds']):
                held={i for i in train if fold[i]==k};fitting=train-held
                queries=releases.loc[releases.id.isin(held)]
                for candidate in c['candidates']:
                    prefix=run['results']/f"cv{k}_{candidate['name']}"
                    print(f"CV {k+1}/{c['cv_folds']}: {candidate['name']}; fit {len(fitting)} IDs / held {len(held)} IDs",flush=True)
                    if prefix.with_suffix('.pt').exists():
                        model,mu,sd=load_model(prefix);info=json.loads(prefix.with_suffix('.json').read_text())
                    else:
                        model,mu,sd,info=fit_model(values,support,fitting,held,candidate,c,c['seed']+k)
                        save_model(paths,prefix,model,mu,sd,info)
                    fitinfo.append({'fold':k,'candidate':candidate['name'],'best_epoch':info['best_epoch'],
                                    'epoch_cap_reached':info['epoch_cap_reached']})
                    scored=forecast_queries(paths,Path(str(prefix)+'_scores'),model,mu,sd,queries,obs,mapper,c['cv_particles'],c['seed']+k*1000000,c)
                    for h,g in scored.groupby('horizon_days'):
                        cv.append({'fold':k,'candidate':candidate['name'],'horizon_days':int(h),'pairs':len(g),
                                   'IDs':g.id.nunique(),'S_sum':float(g.S.sum()),'S':float(g.S.mean()),
                                   'E_mass':float(g.E_mass.mean()),'U_mass':float(g.U_mass.mean())})
                    del model;gc.collect()
            cv=pd.DataFrame(cv);info_table=pd.DataFrame(fitinfo)
            save_frame(paths,run['results']/'CV_scores.csv',cv);save_frame(paths,run['results']/'fit_budget.csv',info_table)
            ranked=cv.groupby(['candidate','horizon_days'],as_index=False)[['pairs','S_sum']].sum();ranked['S']=ranked.S_sum/ranked.pairs
            choices=[]
            for family in ('G','MDN3'):
                for h in (7,30):
                    a=ranked.loc[ranked.candidate.str.startswith(family+'_')&ranked.horizon_days.eq(h)].sort_values(['S','candidate']).iloc[0]
                    choices.append({'family':family,'horizon_days':h,'candidate':a.candidate,'CV_S':float(a.S)})
            choice=pd.DataFrame(choices);save_frame(paths,run['results']/'selected_parameters.csv',choice)
            save_frame(paths,run['results']/'CV_summary.csv',ranked)
            validation=[]
            for name in sorted(set(choice.candidate)):
                candidate=next(x for x in c['candidates'] if x['name']==name)
                epochs=max(1,int(np.median(info_table.loc[info_table.candidate.eq(name),'best_epoch'])))
                prefix=run['results']/('refit_'+name)
                if prefix.with_suffix('.pt').exists():model,mu,sd=load_model(prefix)
                else:
                    model,mu,sd,info=fit_model(values,support,train,set(),candidate,c,c['seed']+100,epochs=epochs)
                    save_model(paths,prefix,model,mu,sd,info)
                g=forecast_queries(paths,Path(str(prefix)+'_validation'),model,mu,sd,releases.loc[releases.id.isin(valid)],obs,mapper,c['validation_particles'],c['seed']+200,c)
                validation.append(g.assign(candidate=name));del model;gc.collect()
            scores=pd.concat(validation,ignore_index=True)
            summary=[]
            for r in choice.itertuples():
                g=scores.loc[scores.candidate.eq(r.candidate)&scores.horizon_days.eq(r.horizon_days)]
                summary.append({'model':r.family,'horizon_days':r.horizon_days,'candidate':r.candidate,
                    'pairs':len(g),'IDs':g.id.nunique(),'S':float(g.S.mean()),
                    'E_mass':float(g.E_mass.mean()),'U_mass':float(g.U_mass.mean()),
                    'sampled_zero_fraction':float(g.sampled_zero.mean())})
            save_frame(paths,run['results']/'validation_summary.csv',pd.DataFrame(summary))
            print(pd.DataFrame(summary).to_string(index=False),flush=True)
        verify_bound(paths,bound,sources)
        if guard.denied:raise ValueError('Input protection triggered')
        _seal(paths,run,{'completed':True,'benchmark':args.benchmark,'final_test_access':False,
            'canonical_changed':False,'denied_operations':guard.denied,'step_hours':1,
            'historical_validation_independent_of_current_parameter_selection':True,
            'historical_validation_is_not_pristine_final_test':True})
        print('COMPLETED_RUN='+run['results'].name,flush=True)
    finally:guard.active=False


if __name__=='__main__':main()
