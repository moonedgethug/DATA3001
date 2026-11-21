"""Guarded, resumable 7/30-day neighbour joint CV; final-test access absent."""
import argparse
from datetime import datetime,timezone
import gc
import hashlib
import json
from pathlib import Path
import resource
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import threading
import numpy as np
import pandas as pd
from data3001.paths import project_paths,file_sha256
from data3001.modelling.common.experiment import make_nested_folds
from data3001.modelling.markov_models.markov_neighbour import candidates, schedules, GRID, prepare_neighbours, donor_support
from data3001.modelling.markov_models.markov_neighbour_cv import score_role, combine
from data3001.modelling.markov_models.markov_neighbour_integration import choose, contenders, query_seeds, proposal_forecast
from data3001.modelling.common.markov_position_scores import ensemble_scores, aggregate_scores
from data3001.modelling.markov_models.markov_neighbour_native import SOURCE, LIBRARY
from data3001.modelling.markov_models.run_markov_position import load_inputs
from data3001.modelling.common.geometry import mapper_for
from data3001.modelling.markov_models.run_markov_iteration import context, geometry_inputs, input_case_digest
from data3001.modelling.common.runtime import save_frame, save_json, ReadOnlyInputs
from data3001.modelling.common.runtime import verified_run, _source_hashes, _seal
from data3001.modelling.markov_models.run_markov import identity, verify_bound, environment

CONFIG=Path('configs/markov_m1_neighbour.json')


def validate_profile(meta,record,bound,sources):
    if (meta['source_sha256']!=sources or any(meta['input_sha256'].get(k)!=v for k,v in bound.items())
            or record.get('scope')!='fitting_only_dummy_outcome_runtime_and_precision_profile_not_CV'
            or record.get('chosen_method') not in ['centred','uncentred']):
        raise ValueError('Profile scientific source, native binary, config, input or scope differs')


def validate_settings(c):
    required={'stage':'annual_pooled_displacement_neighbour_joint_nested_CV',
        'kernel_days':[1,2,3,5,7],'horizons':[7,30],'alpha_grid':list(GRID),'lambda_grid':list(GRID),
        'predictors':['lon','lat','ve','vn'],'velocity_classes':9,'grid_degrees':1,'target':'stopped',
        'scenario':'pooled','departure_seasons':'annual_pooled','time_tolerance_hours':0,'weighting':'equal_eligible_pairs',
        'neighbour_law':'eight_cell_union_equal_pairs_displacement_only','historical_optimum':False,
        'outer_folds':5,'inner_folds':4,'initial_r':2,'refinement_r':[4,8,16],
        'inner_method':'deterministic_mixture_MIS_stratified_unbiased_S_pilot_variance_choice',
        'independent_repeats':2,'outer_particles_per_repeat':128,'workers':4,'batch_origins':32,
        'bootstrap_replicates':200,'final_test_access':False}
    if any(c.get(k)!=v for k,v in required.items()):raise ValueError('Settings exceed authorised neighbour comparison')
    return c


def eligible(releases,bins,held,horizon):
    p=releases.loc[releases.reason_code.eq(0)&releases.horizon_days.eq(horizon)&releases.id.isin(held)].copy()
    if p.empty or p.duplicated(['id','origin_source_obs']).any():raise ValueError('Absent/ambiguous eligible cases')
    p['origin_velocity_bin']=bins[p.origin];return p.sort_values(['id','origin_source_obs']).reset_index(drop=True)


def begin(paths,c,kind,profile_run=None,resume=None):
    ids,obs,releases,th,outer,receipt=load_inputs(paths,c['input_run'])
    geometry,geo_receipt=geometry_inputs(paths,c['geometry_run'],c,obs)
    data,bound=identity(paths)
    if data['version']!=c['dataset_release'] or bound['docs/contract/data_contract_v1.0.xlsx']!=c['contract_sha256']:raise ValueError('Data/contract changed')
    bound[CONFIG.as_posix()]=file_sha256(paths.root/CONFIG)
    for path in [SOURCE,LIBRARY]:bound[path.relative_to(paths.root).as_posix()]=file_sha256(path)
    for r in [receipt,geo_receipt]:bound[r.relative_to(paths.root).as_posix()]=file_sha256(r)
    sources=_source_hashes(paths);extra={};profile=None
    if profile_run:
        receipt=verified_run(paths,profile_run)
        profile=json.loads((paths.root/'results/runs'/profile_run/'PROFILE.json').read_text())
        validate_profile(json.loads((receipt.parent/'run.json').read_text())['config'],profile,bound,sources)
        bound[receipt.relative_to(paths.root).as_posix()]=file_sha256(receipt)
        extra={'profile_run':profile_run,'score_integration':profile['chosen_method']}
    if resume:
        if Path(resume).name!=resume:raise ValueError('Unsafe resume run')
        r=paths.root/'provenance/runs'/resume/'run.json';old=json.loads(r.read_text())['config']
        if old['source_sha256']!=sources or old.get('profile_run')!=profile_run or any(old['input_sha256'].get(k)!=v for k,v in bound.items()):raise ValueError('Resume source/input/profile differs')
        extra['resume_from']=resume
    name=datetime.now(timezone.utc).strftime(kind+'_%Y%m%dT%H%M%S_%fZ')
    run=paths.create_run(name,{**c,**extra,'input_sha256':bound,'source_sha256':sources})
    guard=ReadOnlyInputs(paths.root,run,data_root=paths.data_root);sys.addaudithook(guard)
    print('ACTIVE_RUN='+name,flush=True)
    return ids,obs,releases,th,geometry,bound,sources,run,guard,profile


def finish(paths,run,bound,sources,guard,record):
    verify_bound(paths,bound,sources)
    if guard.denied:raise ValueError('Input/test guard triggered')
    record.update(final_test_trajectories_read=0,canonical_changed=False,canonical_tracks_read=len(guard.read_ids),
                  denied_operations=guard.denied,max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  environment={**environment(),'numeric_workers':4,'BLAS_threads':1,'native_score':'clang++ O3 C++17 ffp-contract=off'})
    _seal(paths,run,record);print('COMPLETED_RUN='+run['results'].name,flush=True)


def profile(paths,c):
    ids,obs,releases,th,geometry,bound,sources,run,guard,_=begin(paths,c,'markov_neighbour_profile')
    begun=time.monotonic()
    try:
        outer,inner=make_nested_folds(sorted(ids));train={i for i in ids if outer[i]!=0};held={i for i in train if inner[0][i]==0};fit=train-held
        bins,pools=context(paths,c,obs,th,geometry,fit,held,'inner_0_0');results=[];var={'centred':0.,'uncentred':0.}
        for h in c['horizons']:
            source=eligible(releases,bins,fit,h);p=source.iloc[np.linspace(0,len(source)-1,128,dtype=int)].copy()
            # Fitting-only dummy outcomes, not withheld observed endpoints.
            p['destination_cell_1']=np.where(np.arange(len(p))%3==0,p.origin_cell_1,
                                           np.where(np.arange(len(p))%3==1,-2,50000))
            start=time.monotonic()
            table,idscores,audit=score_role(pools,obs,bins,p,h,list(range(len(candidates(h)))),2,mapper_for(paths),
                'fitting_numerical_profile',0,workers=c['workers'],batch_size=c['batch_origins'],engineering_profile=True)
            elapsed=time.monotonic()-start;a=audit['sampler_counts_not_target_mass']
            for name in var:var[name]+=a[name+'_repeat_difference_square']/len(candidates(h))
            results.append({'horizon_days':h,'queries':len(p),'candidates':len(table),'elapsed_seconds':elapsed,
                            'projected_initial_inner_seconds':elapsed/len(p)*(4*int((releases.reason_code.eq(0)&releases.horizon_days.eq(h)).sum()))})
            save_frame(paths,run['results']/f'profile_H{h}.csv',table);save_json(paths,run['results']/f'profile_H{h}_audit.json',audit)
        method=min(var,key=var.get)
        result={'scope':'fitting_only_dummy_outcome_runtime_and_precision_profile_not_CV','chosen_method':method,
                'choice_rule':'smaller mean repeated numerical variance across all predeclared candidates and horizons, never smaller model score',
                'repeat_difference_squares_per_candidate':var,'horizon_profiles':results,
                'projection_limit':'linear extrapolation only; fitting, refinement and outer evaluation extra',
                'elapsed_seconds':time.monotonic()-begun}
        save_json(paths,run['results']/'PROFILE.json',result);finish(paths,run,bound,sources,guard,result)
    except Exception as e:save_json(paths,run['provenance']/'FAILED.json',{'error':repr(e)});raise
    finally:guard.active=False


def find_checkpoint(paths,run,key):
    name=run['results'].name;seen=set();source=json.loads((run['provenance']/'run.json').read_text())['config']['source_sha256']
    while name:
        if name in seen or Path(name).name!=name:raise ValueError('Invalid resume lineage')
        seen.add(name);root=paths.root/'results/runs'/name;meta=json.loads((paths.root/'provenance/runs'/name/'run.json').read_text())['config']
        if meta['source_sha256']!=source:raise ValueError('Checkpoint code differs')
        candidate=root/'checkpoints'/key/'COMPLETE.json'
        if candidate.exists():
            record=json.loads(candidate.read_text())
            for rel,sha in record['files'].items():
                if Path(rel).name!=rel or file_sha256(candidate.parent/rel)!=sha:raise ValueError('Checkpoint hash differs')
            return candidate.parent,record
        name=meta.get('resume_from')
    return None,None


def inner_call(paths,c,run,obs,releases,th,geometry,ids,outer,inner,fold,indices,r,nonce,method):
    tables=[]
    for j in range(4):
        role=f'inner_{fold}_{j}';train={i for i in ids if outer[i]!=fold};held={i for i in train if inner[fold][i]==j};fit=train-held
        signature=hashlib.sha256(repr((indices,r,nonce,method)).encode()).hexdigest()[:16];key=f'{role}_{signature}'
        cached,meta=find_checkpoint(paths,run,key)
        target=run['results']/'checkpoints'/key
        if cached is not None:
            if set(meta['fitting_ids'])!=fit or set(meta['held_ids'])!=held:raise ValueError('Checkpoint ID role differs')
            if cached!=target:
                for rel in list(meta['files'])+['COMPLETE.json']:
                    def copy(stream,source=cached/rel):
                        with source.open('rb') as f:shutil.copyfileobj(f,stream)
                    paths.publish(target/rel,copy)
            values={h:pd.read_csv(target/f'H{h}.csv') for h in indices};tables.append(values);print('Reused '+key,flush=True);continue
        begun=time.monotonic();bins,pools=context(paths,c,obs,th,geometry,fit,held,role);values={};digests={}
        for h,ix in indices.items():
            part=eligible(releases,bins,held,h);digests[str(h)]=input_case_digest(part)
            print(f'{role} H{h}: {len(part)} origins / {part.id.nunique()}IDs; {len(ix)} candidates at r{r}',flush=True)
            table,idframe,audit=score_role(pools,obs,bins,part,h,ix,r,mapper_for(paths),role,nonce,
                method=method,workers=c['workers'],batch_size=c['batch_origins'])
            save_frame(paths,target/f'H{h}.csv',table);save_frame(paths,target/f'H{h}_ID.csv',idframe)
            save_json(paths,target/f'H{h}_audit.json',audit);values[h]=table
        files=[p for p in target.iterdir() if p.is_file()]
        save_json(paths,target/'COMPLETE.json',{'fitting_ids':sorted(fit),'held_ids':sorted(held),'role':role,
            'indices':indices,'r':r,'nonce':nonce,'threshold_m_s':th['roles'][role]['threshold_m_s'],
            'case_digests':digests,'elapsed_seconds':time.monotonic()-begun,'files':{p.name:file_sha256(p) for p in files}})
        tables.append(values);del bins,pools;gc.collect()
    return {h:combine([v[h] for v in tables]) for h in indices}


def outer_scores(paths,c,prefix,pools,obs,bins,part,h,fold,choices):
    from data3001.modelling.markov_models.markov_iteration_outer import outer_MC
    from data3001.modelling.markov_models.markov_neighbour_report import COMPARISONS
    if any(set(part.id)&set(p.fitting_ids) for p in pools.values()):raise ValueError('Outer IDs in donor pools')
    part=part.sort_values(['id','origin_source_obs']).reset_index(drop=True);prepare_neighbours(pools)
    local=threading.local();s=choices['self'];n=choices['neighbour']
    variants={'self-CV':(s['path'],0.,s['lambda_value']),
              'neighbour-CV':(n['path'],n['alpha'],n['lambda_value']),
              'self-at-neighbour':(n['path'],0.,n['lambda_value'])}
    states=sorted(set(zip(part.origin_cell_1.astype(int),part.origin_velocity_bin.astype(int))))
    support=[]
    for lag in sorted({d for p,a,l in variants.values() for d in schedules(h)[p]}):
        support.append(donor_support(pools[lag],states).assign(lag_days=lag,horizon_days=h,outer_fold=fold))
    save_frame(paths,prefix/f'H{h}_fitting_support.csv',pd.concat(support,ignore_index=True))
    unique={}
    for model,theta in variants.items():unique.setdefault(theta,[]).append(model)
    def calculate(start):
        if not hasattr(local,'mapper'):local.mapper=mapper_for(paths)
        batch=part.iloc[start:start+64];ix=batch.origin.to_numpy();frames=[];traces=[];draws={}
        for (path,a,l),models in unique.items():
            seq=schedules(h)[path]
            for rep in range(2):
                seed=query_seeds(f'outer_{fold}|H{h}|{path}',batch.id,batch.origin_source_obs,rep,'issued_iid128')
                def trace(day,codes,audit):
                    for model in models:traces.append({'horizon_days':h,'model':model,'repeat':rep,'day':day,
                        'particles':codes.size,'U_particles':int((codes==-3).sum()),'E_particles':int((codes==-2).sum()),**audit})
                draw,_,_,audit=proposal_forecast(pools,obs['lon'][ix],obs['lat'][ix],bins[ix],seq,[(a,l)],
                    c['outer_particles_per_repeat'],seed,local.mapper,trace=trace)
                score=ensemble_scores(draw,batch.destination_cell_1.to_numpy())
                for key in ['id','origin_source_obs','origin_cell_1','origin_velocity_bin','destination_cell_1']:
                    score[key]=batch[key].to_numpy()
                score=score.assign(outer_fold=fold,horizon_days=h,repeat=rep,path=path,alpha=a,lambda_value=l)
                for model in models:
                    frames.append(score.assign(model=model))
                draws[models[0],rep]=draw
        return pd.concat(frames,ignore_index=True),traces,draws
    frames=[];traces=[];raw={}
    with ThreadPoolExecutor(max_workers=c['workers']) as executor:
        for number,(f,t,d) in enumerate(executor.map(calculate,range(0,len(part),64)),1):
            frames.append(f);traces.extend(t)
            for key,draw in d.items():raw.setdefault(key,[]).append(draw)
            if number%100==0:print(f'Outer{fold+1} H{h}: {number*64}/{len(part)} scored',flush=True)
    result=pd.concat(frames,ignore_index=True).sort_values(['model','repeat','id','origin_source_obs']).reset_index(drop=True)
    mapping={}
    for (model,rep),blocks in raw.items():
        array=np.concatenate(blocks);filename=f'H{h}_{model}_repeat{rep}_draws.npy'
        paths.publish(prefix/filename,lambda stream,array=array:np.save(stream,array,allow_pickle=False))
        theta=variants[model]
        for alias in unique[theta]:mapping[f'{alias}|{rep}']=filename
    save_json(paths,prefix/f'H{h}_draw_mapping.json',mapping)
    save_frame(paths,prefix/f'H{h}_cases.parquet',part)
    save_frame(paths,prefix/f'H{h}_step_causes.csv',pd.DataFrame(traces).groupby(['horizon_days','model','repeat','day'],as_index=False).sum())
    mc=outer_MC(result,COMPARISONS);mc['horizon_days']=h
    return result,mc


def evaluate(paths,c,profile_run,resume=None):
    ids,obs,releases,th,geometry,bound,sources,run,guard,pilot=begin(paths,c,'markov_neighbour_cv',profile_run,resume)
    begun=time.monotonic();outer,inner=make_nested_folds(sorted(ids));choices=[];scores=[];mcrows=[];roles=[]
    try:
        for fold in range(5):
            key=f'outer_{fold}';cached,record=find_checkpoint(paths,run,key);prefix=run['results']/'checkpoints'/key
            if cached is not None:
                if cached!=prefix:
                    for rel in list(record['files'])+['COMPLETE.json']:
                        def copy(stream,source=cached/rel):
                            with source.open('rb') as f:shutil.copyfileobj(f,stream)
                        paths.publish(prefix/rel,copy)
                choices.extend(record['choices']);roles.append(record['role'])
                scores.append(pd.read_csv(prefix/'ID_scores.csv'));mcrows.append(pd.read_csv(prefix/'MC.csv'))
                print('Reused '+key,flush=True);continue
            initial={h:list(range(len(candidates(h)))) for h in c['horizons']};nonce=0
            latest=inner_call(paths,c,run,obs,releases,th,geometry,ids,outer,inner,fold,initial,2,nonce,pilot['chosen_method'])
            for h,t in latest.items():
                t['precision_r']=2;save_frame(paths,run['results']/f'selection/outer{fold}_H{h}_call{nonce}.csv',t)
            # Refine contenders of BOTH independently selected procedures.
            # Reconsider all original candidates after every changed estimate.
            for r in c['refinement_r']:
                while True:
                    wanted={}
                    for h,t in latest.items():
                        near=sorted(set(contenders(t,'self'))|set(contenders(t,'neighbour')))
                        if any(t.set_index('candidate').loc[i,'precision_r']<r for i in near):wanted[h]=near
                    if not wanted:break
                    nonce+=1;updated=inner_call(paths,c,run,obs,releases,th,geometry,ids,outer,inner,fold,wanted,r,nonce,pilot['chosen_method'])
                    for h,t in updated.items():
                        t['precision_r']=r
                        save_frame(paths,run['results']/f'selection/outer{fold}_H{h}_call{nonce}.csv',t)
                        old=latest[h].set_index('candidate');old.loc[t.candidate,t.columns[1:]]=t.set_index('candidate')[t.columns[1:]]
                        latest[h]=old.reset_index().sort_values('candidate').reset_index(drop=True)
            locked={h:{family:choose(t,h,family) for family in ['self','neighbour']} for h,t in latest.items()}
            for h in c['horizons']:
                if len(latest[h])!=len(candidates(h)):raise ValueError('Original candidates missing after refinement')
                for family,ch in locked[h].items():choices.append({'outer_fold':fold,'horizon_days':h,'family':family,**ch})
                save_frame(paths,run['results']/f'selection/outer{fold}_H{h}_final.csv',latest[h])
            save_json(paths,prefix/'locked_choices.json',locked)
            fitting={i for i in ids if outer[i]!=fold};held=ids-fitting;role=f'outer_{fold}'
            bins,pools=context(paths,c,obs,th,geometry,fitting,held,role)
            frames=[];mcs=[];digest={}
            for h in c['horizons']:
                part=eligible(releases,bins,held,h);digest[str(h)]=input_case_digest(part)
                print(f'Outer{fold+1} H{h}: locked {locked[h]}; {len(part)} untouched queries',flush=True)
                frame,mc=outer_scores(paths,c,prefix,pools,obs,bins,part,h,fold,locked[h])
                frames.append(frame);mcs.append(mc)
            frame=pd.concat(frames,ignore_index=True);idframe=aggregate_scores(frame);mc=pd.concat(mcs,ignore_index=True)
            save_frame(paths,prefix/'scores.parquet',frame);save_frame(paths,prefix/'ID_scores.csv',idframe);save_frame(paths,prefix/'MC.csv',mc)
            role_record={'role':role,'fitting_ids':sorted(fitting),'held_ids':sorted(held),'case_digests':digest,
                         'threshold_m_s':th['roles'][role]['threshold_m_s']}
            roles.append(role_record);scores.append(idframe);mcrows.append(mc)
            files=[p for p in prefix.iterdir() if p.is_file()]
            save_json(paths,prefix/'COMPLETE.json',{'choices':[p for p in choices if p['outer_fold']==fold],
                'role':role_record,'files':{p.name:file_sha256(p) for p in files}})
            del pools,bins,frame,frames;gc.collect()
        idscores=pd.concat(scores,ignore_index=True)
        for h,n,ni in [(7,303288,385),(30,268998,337)]:
            base=idscores.loc[idscores.horizon_days.eq(h)&idscores.model.eq('self-CV')&idscores['repeat'].eq(0)]
            if int(base.pairs.sum())!=n or base.id.nunique()!=ni:raise ValueError('Outer population differs from frozen eligibility')
        mc=pd.concat(mcrows,ignore_index=True).groupby(['horizon_days','comparison'],as_index=False)[
            ['case_count','difference_sum_0','difference_sum_1','repeat_difference_squares']].sum()
        mc['delta_S']=(mc.difference_sum_0+mc.difference_sum_1)/(2*mc.case_count)
        mc['MC_SE']=np.sqrt(mc.repeat_difference_squares)/(2*mc.case_count)
        mc['MC_only_lower_95']=mc.delta_S-1.96*mc.MC_SE;mc['MC_only_upper_95']=mc.delta_S+1.96*mc.MC_SE
        save_frame(paths,run['results']/'ID_scores.csv',idscores);save_json(paths,run['provenance']/'outer_ID_roles.json',roles)
        from data3001.modelling.markov_models.markov_neighbour_report import report
        summary,ci=report(paths,run,c,idscores,choices,mc)
        print(summary[['horizon_days','model','S_integration','U_mass','region90_hit','region90_cells']].to_string(index=False),flush=True)
        finish(paths,run,bound,sources,guard,{'elapsed_seconds':time.monotonic()-begun,'all_candidates_initially_scored':{'7':968,'30':1089},
            'outer_folds':5,'inner_folds_per_outer':4,'outer_primary_pairs':{'7':303288,'30':268998},
            'outer_independent_IDs':{'7':385,'30':337},'historical_optimal_parameters_used':False,
            'score_integration':pilot['chosen_method'],'source_input_run':c['input_run'],'profile_run':profile_run})
    except Exception as e:save_json(paths,run['provenance']/'FAILED.json',{'error':repr(e),'completed':False});raise
    finally:guard.active=False


def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',action='store_true');p.add_argument('--profile-run');p.add_argument('--resume-run');a=p.parse_args()
    paths=project_paths();c=validate_settings(json.loads((paths.root/CONFIG).read_text()))
    if a.profile:profile(paths,c)
    elif a.profile_run:evaluate(paths,c,a.profile_run,a.resume_run)
    else:p.error('Choose --profile or --profile-run RUN')


if __name__=='__main__':main()
