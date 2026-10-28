"""Guarded, resumable all99 schedule/lambda development comparison.

--prepare-geometry; --geometry-run RUN --profile; --geometry-run RUN
--resume-run RUN resumes only identical code/config/input checkpoints.
"""
import argparse
from dataclasses import replace
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

from data3001.modelling.experiment import make_nested_folds
from data3001.modelling.markov_iteration import SCHEDULES,candidates,forecast_schedule
from data3001.modelling.markov_iteration_coarse import coarse_kernel,coarse_scores,coarse_predictions
from data3001.modelling.markov_iteration_cv import combine_roles,select_search,score_stratified_grid,seed_for
from data3001.modelling.markov_iteration_geometry import build_geometry,Geometry,GEO_DTYPE
from data3001.modelling.markov_position_scores import ensemble_scores,aggregate_scores
from data3001.modelling.markov_velocity import coarse_velocity
from data3001.modelling.run_blend_cv import save_frame,save_json,ReadOnlyInputs
from data3001.modelling.run_markov import identity,verify_bound,environment
from data3001.modelling.run_markov_position import load_inputs,fitted_pools,mapper_for,choices_for_fold,verify_old_law
from data3001.modelling.run_neighbourhood import verified_run,_source_hashes,_seal
from data3001.paths import project_paths,file_sha256

CONFIG=Path('configs/markov_m1_iteration.json')


def validate_settings(c):
    required={'kernel_days':[1,2,3,5,7],'paths':list(SCHEDULES),'lambda_grid':[i/10 for i in range(11)],
        'candidate_filter':'none_all_99_inner_CV','predictors':['lon','lat','ve','vn'],'velocity_classes':9,
        'grid_degrees':1,'target':'stopped','scenario':'pooled','departure_seasons':'annual_pooled',
        'horizon_days':30,'time_tolerance_hours':0,'weighting':'equal_eligible_pairs','primary_score':'unbiased_S_integration',
        'inner_integration_target':32,'inner_refinement_targets':[64,128],
        'inner_method':'binomial_component_count_stratification_same_transition_law',
        'outer_particles_per_repeat':64,'independent_repeats':2,'outer_folds':5,'inner_folds':4,
        'batch_origins':256,'final_test_access':False}
    if any(c.get(k)!=v for k,v in required.items()) or c.get('workers') not in [1,2,4]:
        raise ValueError('Configuration exceeds authorised all-path lambda-CV scope')
    return c


def check_role(th,role,fitting,held):
    record=th['roles'][role]
    if set(record['fitting_ids'])!=set(fitting) or set(fitting)&set(held):raise ValueError('Incorrect fitting/held-ID role')
    return record['threshold_m_s']


def cache_rows(native,origins,endpoints,lag,offset):
    return build_geometry(native,np.asarray(origins)-offset,np.asarray(endpoints)-offset,lag,offset)


def start(paths,c,kind,extra,receipts,resume=None):
    data,bound=identity(paths)
    if data['version']!=c['dataset_release'] or bound['docs/contract/data_contract_v1.0.xlsx']!=c['contract_sha256']:
        raise ValueError('Dataset/contract changed')
    bound[CONFIG.as_posix()]=file_sha256(paths.root/CONFIG)
    for r in receipts:bound[r.relative_to(paths.root).as_posix()]=file_sha256(r)
    sources=_source_hashes(paths)
    if resume:
        if Path(resume).name!=resume:raise ValueError('Unsafe resume name')
        previous=paths.root/'provenance/runs'/resume/'run.json'
        meta=json.loads(previous.read_text())['config']
        if (any(meta['input_sha256'].get(k)!=v for k,v in bound.items()) or meta['source_sha256']!=sources
                or meta.get('geometry_run')!=extra.get('geometry_run')):raise ValueError('Resume identity differs')
        extra={**extra,'resume_from':resume};bound[previous.relative_to(paths.root).as_posix()]=file_sha256(previous)
    name=datetime.now(timezone.utc).strftime(kind+'_%Y%m%dT%H%M%S_%fZ')
    run=paths.create_run(name,{**c,**extra,'input_sha256':bound,'source_sha256':sources})
    guard=ReadOnlyInputs(paths.root,run,data_root=paths.data_root);sys.addaudithook(guard)
    print('ACTIVE_RUN='+run['results'].name,flush=True)
    return bound,sources,run,guard


def finish(paths,run,bound,sources,guard,record):
    verify_bound(paths,bound,sources)
    if guard.denied:raise ValueError('Input/final-test guard triggered')
    record.update(final_test_trajectories_read=0,canonical_changed=False,canonical_tracks_read=len(guard.read_ids),
        denied_operations=guard.denied,max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        environment=run_environment(record.get('cache_only',False),json.loads((run['provenance']/'run.json').read_text())['config']['workers']))
    _seal(paths,run,record);print('COMPLETED_RUN='+run['results'].name,flush=True)
    print(json.dumps({k:v for k,v in record.items() if k!='environment'},indent=2),flush=True)


def run_environment(cache_only,workers):
    env=environment();env['numeric_workers']=1 if cache_only else workers
    env['BLAS_threads']=1;env['GEOS_worker_policy']='private mapper per numeric thread'
    return env


def failure(paths,run,error):
    name=datetime.now(timezone.utc).strftime('FAILED_%Y%m%dT%H%M%S_%fZ.json')
    save_json(paths,run['provenance']/name,{'error':repr(error),'completed':False})


def prepare_geometry(paths,c):
    ids,obs,releases,th,outer,receipt=load_inputs(paths,c['input_run'])
    bound,sources,run,guard=start(paths,c,'markov_iteration_geometry',{},[receipt]);begun=time.monotonic()
    try:
        root=paths.root/'results/runs'/c['input_run'];ranges=pd.read_csv(root/'source_ID_summary.csv')
        totals={}
        for lag in c['kernel_days']:
            pairs=pd.read_parquet(root/'donors.parquet',filters=[('lag','==',lag)],columns=['origin','endpoint'])
            pairs=pairs.loc[pairs.endpoint.ge(0)].sort_values('origin');o=pairs.origin.to_numpy();e=pairs.endpoint.to_numpy()
            if len(np.unique(o))!=len(o):raise ValueError('Duplicate native donor origin')
            def writer(stream):
                np.lib.format.write_array_header_2_0(stream,{'descr':GEO_DTYPE.descr,'fortran_order':False,'shape':(len(obs),)})
                for row in ranges.itertuples():
                    lo,hi=np.searchsorted(o,[row.start,row.end]);native=obs[row.start:row.end]
                    block=cache_rows(native,o[lo:hi],e[lo:hi],lag,row.start);stream.write(block.tobytes())
            paths.publish(run['results']/f'geometry_{lag}d.npy',writer)
            totals[str(lag)]=len(o);del pairs,o,e;gc.collect()
            print(f'Geometry cache {lag}d complete; {time.monotonic()-begun:.1f}s',flush=True)
        save_json(paths,run['results']/'cache_identity.json',{'native_rows':len(obs),'lag_days':c['kernel_days'],
            'input_run':c['input_run'],'scope':'deterministic computational geometry, no learned/canonical features',
            'survivor_donors_by_lag':totals})
        finish(paths,run,bound,sources,guard,{'elapsed_seconds':time.monotonic()-begun,'cache_only':True,
            'native_rows':len(obs),'survivor_donors_by_lag':totals})
    except Exception as e:failure(paths,run,e);raise
    finally:guard.active=False


def geometry_inputs(paths,name,c,obs):
    receipt=verified_run(paths,name);root=paths.root/'results/runs'/name
    meta=json.loads((root/'cache_identity.json').read_text())
    if meta['native_rows']!=len(obs) or meta['input_run']!=c['input_run']:raise ValueError('Geometry cache source differs')
    return {h:Geometry(np.load(root/f'geometry_{h}d.npy',mmap_mode='r'),h) for h in c['kernel_days']},receipt


def context(paths,c,obs,th,geometry,fitting,held,role):
    threshold=check_role(th,role,fitting,held);bins=coarse_velocity(obs['atom'],th['cutpoints'],threshold)
    pools=fitted_pools(paths.root/'results/runs'/c['input_run'],obs,bins,fitting,c['kernel_days'])
    for h,p in pools.items():
        pools[h]=replace(p,geometry=geometry[h])
        for a in [p.origins,p.endpoints,p.conditional_count,p.conditional_start,p.cell_count,p.cell_start]:a.flags.writeable=False
    return bins,pools


def eligible(releases,bins,held):
    p=releases.loc[releases.reason_code.eq(0)&releases.horizon_days.eq(30)&releases.id.isin(held)].copy()
    if p.empty:raise ValueError('No held30-day cases; no silent reseeding/filtering')
    p['origin_velocity_bin']=bins[p.origin];return p.sort_values(['id','origin_source_obs']).reset_index(drop=True)


def publish_array(paths,path,array):paths.publish(path,lambda stream:np.save(stream,array,allow_pickle=False))


def input_case_digest(part):
    return hashlib.sha256(part[['id','origin_source_obs','origin_cell_1','origin_velocity_bin','destination_cell_1']].to_numpy(dtype='<i8').tobytes()).hexdigest()


def checkpoint(paths,run,key):
    name=run['results'].name;seen=set();current=json.loads((run['provenance']/'run.json').read_text())['config']
    while name:
        if name in seen or Path(name).name!=name:raise ValueError('Invalid resume lineage')
        seen.add(name);root=paths.root/'results/runs'/name
        source=json.loads((paths.root/'provenance/runs'/name/'run.json').read_text())['config']
        if source.get('source_sha256')!=current.get('source_sha256'):raise ValueError('Checkpoint source code differs')
        for f in sorted((root/'inner').glob(key+'_*/COMPLETE.json')) if (root/'inner').exists() else []:
            meta=json.loads(f.read_text())
            for rel,sha in meta['files'].items():
                path=f.parent/rel
                if path.parent!=f.parent or file_sha256(path)!=sha:raise ValueError('Checkpoint hash differs')
            return f.parent,meta
        name=source.get('resume_from')
    return None,None


def inner_fit(paths,c,run,obs,releases,th,geometry,allids,outer,inner,f,j,indices,target,coarse_too):
    role=f'inner_{f}_{j}';fit_outer={i for i in allids if outer[i]!=f};held={i for i in fit_outer if inner[f][i]==j};fit=fit_outer-held
    signature=hashlib.sha256(np.asarray(indices,dtype='<i4').tobytes()).hexdigest()[:12]
    key=f'{role}_M{target}_{signature}';folder,meta=checkpoint(paths,run,key)
    if folder is not None:
        if meta['indices']!=indices or set(meta['fitting_ids'])!=fit or set(meta['held_ids'])!=held:raise ValueError('Checkpoint role differs')
        print('Reusing '+key,flush=True)
        if not folder.is_relative_to(run['results']):
            target_folder=run['results']/'inner'/folder.name
            for rel,sha in meta['files'].items():
                target_file=target_folder/rel
                if not target_file.exists():
                    source_file=folder/rel
                    def copy(stream,source_file=source_file):
                        with source_file.open('rb') as source:shutil.copyfileobj(source,stream)
                    paths.publish(target_file,copy)
                if file_sha256(target_file)!=sha:raise ValueError('Copied checkpoint differs')
            save_json(paths,target_folder/'COMPLETE.json',{**meta,'reused_from':folder.relative_to(paths.root).as_posix()})
            folder=target_folder
        return pd.read_csv(folder/'scores.csv'),np.load(folder/'mc_crossproducts.npy'),pd.read_csv(folder/'coarse_scores.csv') if coarse_too else None
    bins,pools=context(paths,c,obs,th,geometry,fit,held,role);part=eligible(releases,bins,held)
    begun=time.monotonic();prefix=run['results']/'inner'/(key+'_'+datetime.now(timezone.utc).strftime('%H%M%S_%f'))
    original=pd.read_csv(paths.root/'results/runs'/c['coarse_parent']/'selected_parameters.csv')
    reference_lambda=choices_for_fold(original,f)[30][1]
    print(f'Inner outer{f+1}/5 role{j+1}/4, all{len(indices)}targets at{target}; {len(part)}queries',flush=True)
    table,gram,ids,diag,audit=score_stratified_grid(pools,obs,bins,part,indices,target,mapper_for(paths),role,
        workers=c['workers'],batch_size=c['batch_origins'],diagnostic_lambda=reference_lambda if target==32 else None)
    save_frame(paths,prefix/'scores.csv',table);publish_array(paths,prefix/'mc_crossproducts.npy',gram)
    save_frame(paths,prefix/'ID_scores.csv',ids)
    if len(diag):save_frame(paths,prefix/'fixed_lambda_diagnostic.csv',diag)
    save_json(paths,prefix/'proposal_audit.json',audit)
    coarse=None
    if coarse_too:
        cells=pd.read_parquet(paths.asset('state_index',verify=True));cells=cells.loc[cells.resolution.eq(1)].sort_values('cell').cell.astype(int).tolist()
        kernels={h:coarse_kernel(p,cells) for h,p in pools.items()}
        print(role+': scoring exact coarse99-candidate control',flush=True)
        coarse=coarse_scores(kernels,part,workers=c['workers']);save_frame(paths,prefix/'coarse_scores.csv',coarse)
        del kernels;gc.collect()
    files=[p for p in prefix.iterdir() if p.is_file()]
    meta={'indices':indices,'integration_target':target,'fitting_ids':sorted(fit),'held_ids':sorted(held),
        'role':role,'threshold_m_s':th['roles'][role]['threshold_m_s'],'case_count':len(part),
        'case_digest':input_case_digest(part),'elapsed_seconds':time.monotonic()-begun,
        'files':{p.name:file_sha256(p) for p in files}}
    save_json(paths,prefix/'COMPLETE.json',meta)
    del bins,pools;gc.collect();return table,gram,coarse


def profile(paths,c,name):
    ids,obs,releases,th,outer,receipt=load_inputs(paths,c['input_run']);geometry,geo_receipt=geometry_inputs(paths,name,c,obs)
    bound,sources,run,guard=start(paths,c,'markov_iteration_profile',{'geometry_run':name},[receipt,geo_receipt])
    begun=time.monotonic()
    try:
        outer,inner=make_nested_folds(sorted(ids));fit_outer={i for i in ids if outer[i]!=0}
        held={i for i in fit_outer if inner[0][i]==0};fitting=fit_outer-held
        bins,pools=context(paths,c,obs,th,geometry,fitting,held,'inner_0_0')
        source=eligible(releases,bins,fitting)
        part=source.iloc[np.linspace(0,len(source)-1,min(1024,len(source)),dtype=int)].copy()
        # Runtime only; no validation outcome is inspected or used to choose a model.
        part['destination_cell_1']=part.origin_cell_1
        from data3001.modelling.markov_iteration_strata import weights_for,stratified_forecast
        mapper=mapper_for(paths);ix=part.origin.to_numpy()[:48];agreements=[]
        for path in ['D7','R7','W5','W3','D1']:
            for lam in [0.,.3,1.]:
                fast,_=forecast_schedule(pools,obs['lon'][ix],obs['lat'][ix],bins[ix],SCHEDULES[path],lam,32,71,mapper)
                plain={h:replace(p,geometry=None) for h,p in pools.items()}
                slow,_=forecast_schedule(plain,obs['lon'][ix],obs['lat'][ix],bins[ix],SCHEDULES[path],lam,32,71,mapper)
                np.testing.assert_array_equal(fast,slow);agreements.append((path,lam,len(ix)*32))
                if lam in [0.,1.]:
                    draws,allocation,_=stratified_forecast(pools,obs['lon'][ix],obs['lat'][ix],bins[ix],SCHEDULES[path],
                        weights_for(len(SCHEDULES[path]),[lam]),32,71,mapper)
                    np.testing.assert_array_equal(draws,fast)
        from data3001.modelling.markov_position import GEOD,_transferred_exit
        boundary_cases=0;boundary_exits=0
        for lag,pool in pools.items():
            choices=np.flatnonzero(pool.endpoints>=0)
            take=choices[np.linspace(0,len(choices)-1,min(16,len(choices)),dtype=int)]
            o=np.tile(pool.origins[take],4);e=np.tile(pool.endpoints[take],4);n=len(take)
            x=np.r_[np.full(n,-80.999),np.full(n,-8.001),np.full(2*n,-50.)]
            y=np.r_[obs['lat'][pool.origins[take]],obs['lat'][pool.origins[take]],np.full(n,20.001),np.full(n,54.999)]
            actual,_,_=_transferred_exit(pool,o,e,x,y,mapper.domain.bounds);expected=[]
            for i,j,qx,qy in zip(o,e,x,y):
                track=obs[i:j+1]
                az,_,dist=GEOD.inv(np.full(len(track),obs['lon'][i]),np.full(len(track),obs['lat'][i]),track['lon'],track['lat'])
                xx,yy,_=GEOD.fwd(np.full(len(track),qx),np.full(len(track),qy),az,dist)
                expected.append(np.any((xx<-81)|(xx>-8)|(yy<20)|(yy>55)))
            np.testing.assert_array_equal(actual,expected);boundary_cases+=len(o);boundary_exits+=int(actual.sum())
        t=time.monotonic()
        score_stratified_grid(pools,obs,bins,part,list(range(99)),32,mapper,'engineering_profile',
            workers=c['workers'],batch_size=c['batch_origins'],engineering_profile=True)
        fine_seconds=time.monotonic()-t
        index=pd.read_parquet(paths.asset('state_index',verify=True));cells=index.loc[index.resolution.eq(1)].sort_values('cell').cell.astype(int).tolist()
        t=time.monotonic();kernels={h:coarse_kernel(p,cells) for h,p in pools.items()}
        coarse_scores(kernels,part,workers=c['workers']);coarse_seconds=time.monotonic()-t
        save_frame(paths,run['results']/'reference_agreement.csv',pd.DataFrame(agreements,columns=['path','lambda_value','particles_compared']))
        n=int(releases.reason_code.eq(0).where(releases.horizon_days.eq(30),False).sum())
        result={'scope':'fitting_only_runtime_and_semantic_profile_not_CV','profile_queries':len(part),
            'fitting_IDs_only':True,'dummy_truth_not_used_for_selection':True,'all99targets_scored':True,
            'fine99_seconds':fine_seconds,'coarse99_seconds':coarse_seconds,
            'projected_inner_fine_seconds':fine_seconds/len(part)*(4*n),
            'projected_inner_coarse_seconds':coarse_seconds/len(part)*(4*n),
            'projection_caveat':'linear query extrapolation; fit overhead, support effects and refinement are extra',
            'cached_vs_reference_particles_equal':True,'single_lambda_endpoint_strata_equal':True,
            'boundary_stress_cases':boundary_cases,'boundary_stress_exits':boundary_exits,
            'boundary_stress_matches_independent_hourly_geodesics':True,
            'elapsed_seconds':time.monotonic()-begun}
        save_json(paths,run['results']/'PROFILE.json',result);finish(paths,run,bound,sources,guard,result)
    except Exception as e:failure(paths,run,e);raise
    finally:guard.active=False


def evaluate(paths,c,name,resume=None):
    ids,obs,releases,th,outer,receipt=load_inputs(paths,c['input_run']);geometry,geo_receipt=geometry_inputs(paths,name,c,obs)
    parents=[verified_run(paths,c[k]) for k in ['coarse_parent','position_parent']]
    bound,sources,run,guard=start(paths,c,'markov_iteration_cv',{'geometry_run':name},[receipt,geo_receipt]+parents,resume)
    begun=time.monotonic();outer,inner=make_nested_folds(sorted(ids));choices=[];scores=[];traces=[];examples=[];roles=[]
    try:
        from data3001.modelling.markov_iteration_outer import precise_outer,coarse_outer,comparison_intervals,outer_MC
        from data3001.modelling.markov_position_scores import summarize_scores
        from data3001.modelling.run_markov_position import match_reference
        original=pd.read_csv(paths.root/'results/runs'/c['coarse_parent']/'selected_parameters.csv');grid=candidates()
        case_totals=0;coarse_inner_all=[]
        for fold in range(5):
            outer_done=run['results']/f'outer_{fold}_COMPLETE.json'
            if outer_done.exists():
                m=json.loads(outer_done.read_text())
                for rel,sha in m['files'].items():
                    if file_sha256(run['results']/rel)!=sha:raise ValueError('Outer checkpoint hash differs')
                choices.extend(m['choices']);roles.append(m['role']);case_totals+=m['case_count']
                scores.append(pd.read_csv(run['results']/f'outer_{fold}_ID_scores.csv'))
                print(f'Reusing outer{fold+1}',flush=True);continue
            inner_coarse=[];call_number=0
            def search_eval(indices,target):
                nonlocal call_number
                values=[]
                for j in range(4):
                    table,gram,coarse=inner_fit(paths,c,run,obs,releases,th,geometry,ids,outer,inner,fold,j,indices,target,
                        coarse_too=(indices==list(range(99)) and target==32))
                    values.append((table,gram))
                    if coarse is not None:inner_coarse.append(coarse)
                table,g=combine_roles(values)
                base=run['results']/f'selection/outer_{fold}_call_{call_number}_M{target}'
                save_frame(paths,Path(str(base)+'.csv'),table);publish_array(paths,Path(str(base)+'_mc.npy'),g)
                call_number+=1;return table,g
            selected,history=select_search(search_eval)
            if len(inner_coarse)!=4:raise ValueError('Coarse candidate CV roles incomplete')
            coarse_stats=pd.concat(inner_coarse).groupby(['candidate','path','lambda_value'],as_index=False)[['case_count','loss_sum']].sum()
            coarse_stats['S']=coarse_stats.loss_sum/coarse_stats.case_count
            coarse_stats['steps']=coarse_stats.path.map(lambda p:len(SCHEDULES[p]))
            best=coarse_stats.sort_values(['S','steps','lambda_value','path'],ascending=[True,True,False,True]).iloc[0]
            coarse_choice={'candidate':int(best.candidate),'path':best.path,'lambda_value':float(best.lambda_value),'S':float(best.S)}
            save_json(paths,run['results']/f'outer_{fold}_locked_choices.json',{'position':selected,'coarse':coarse_choice,'refinements':history})
            save_frame(paths,run['results']/f'outer_{fold}_coarse_inner.csv',coarse_stats)
            for family,selection in [('position-CV',selected),('coarse-CV',coarse_choice)]:
                choices.append({'outer_fold':fold,'family':family,**selection})
            held={i for i in ids if outer[i]==fold};fitting=ids-held;role=f'outer_{fold}'
            bins,pools=context(paths,c,obs,th,geometry,fitting,held,role);part=eligible(releases,bins,held)
            oldlag,oldlam=choices_for_fold(original,fold)[30];oldpath='D5' if oldlag==5 else 'D7'
            if oldlag not in [5,7]:raise ValueError('Frozen historical30-day schedule changed')
            ref=pd.read_parquet(paths.root/'results/runs'/c['coarse_parent']/f'outer_{fold}_scores.parquet')
            part=match_reference(part,ref.loc[ref.model.eq('M1vcat-selected')&ref.horizon_days.eq(30)])
            cells=pd.read_parquet(paths.asset('state_index',verify=True));cells=cells.loc[cells.resolution.eq(1)].sort_values('cell').cell.astype(int).tolist()
            kernels={h:coarse_kernel(p,cells) for h,p in pools.items()}
            theta_p=(selected['path'],selected['lambda_value']);theta_c=(coarse_choice['path'],coarse_choice['lambda_value'])
            pvariants={'position-CV':theta_p,'position-at-coarse-settings':theta_c,'position-frozen':(oldpath,oldlam)}
            cvariants={'coarse-CV':theta_c,'coarse-at-position-settings':theta_p,'coarse-frozen':(oldpath,oldlam)}
            example=None
            if fold==0:
                train=eligible(releases,bins,fitting)
                support=train.groupby(['origin_cell_1','origin_velocity_bin']).size().sort_values(ascending=False)
                example=tuple(map(int,support.index[0]));save_json(paths,run['results']/'example_definition.json',
                    {'cell':example[0],'velocity_bin':example[1],'selection':'largest fitting-only30-day R support in fold0'})
            print(f'Outer{fold+1}: locked position{theta_p}, coarse{theta_c}; scoring{len(part)} untouched queries',flush=True)
            fine,trace,ex=precise_outer(pools,obs,bins,part,pvariants,fold,mapper_for(paths),
                particles=c['outer_particles_per_repeat'],workers=c['workers'],batch_size=c['batch_origins'],example_key=example)
            coarse,mapping=coarse_outer(kernels,part,cvariants,fold)
            oldcheck=coarse.loc[coarse.model.eq('coarse-frozen')].set_index(['id','origin_source_obs']).S_integration
            oldexpected=part.set_index(['id','origin_source_obs']).old_S
            np.testing.assert_allclose(oldcheck.sort_index(),oldexpected.sort_index(),atol=3e-13,rtol=0)
            b2=match_reference(part.drop(columns='old_S'),ref.loc[ref.model.eq('B2')&ref.horizon_days.eq(30)])
            b2=b2.assign(model='B2-reference',outer_fold=fold,repeat=0,S_integration=b2.old_S,S_issued=b2.old_S,
                path='direct30',lambda_value=np.nan)
            for key in ['true_probability_issued','U_mass','E_mass','sampled_zero','region90_available','region90_hit',
                'region90_cells','region90_mass','energy_km_issued','mean_squared_km2_issued','linear_quadratic_issued']:b2[key]=np.nan
            allframe=pd.concat([fine,coarse,b2],ignore_index=True);idframe=aggregate_scores(allframe)
            save_frame(paths,run['results']/f'outer_{fold}_MC.csv',outer_MC(allframe))
            save_frame(paths,run['results']/f'outer_{fold}_scores.parquet',allframe)
            save_frame(paths,run['results']/f'outer_{fold}_ID_scores.csv',idframe)
            save_frame(paths,run['results']/f'outer_{fold}_trace.parquet',trace)
            if fold==0:
                save_frame(paths,run['results']/'example_particles.parquet',ex)
                observed=part.loc[part.origin_cell_1.eq(example[0])&part.origin_velocity_bin.eq(example[1])]
                save_frame(paths,run['results']/'example_observed.parquet',observed)
                rows=[]
                for (model,cell,b),(p,u) in mapping.items():
                    if (cell,b)==example:
                        rows.extend((model,int(k),float(v)) for k,v in {**p,-3:u}.items() if v>0)
                save_frame(paths,run['results']/'example_coarse.csv',pd.DataFrame(rows,columns=['model','destination_cell_1','probability']))
            role_record={'role':role,'fitting_ids':sorted(fitting),'evaluation_ids':sorted(held),
                'threshold_m_s':th['roles'][role]['threshold_m_s'],'case_digest':input_case_digest(part)}
            roles.append(role_record);case_totals+=len(part);scores.append(idframe)
            files=[run['results']/f'outer_{fold}_{suffix}' for suffix in ['scores.parquet','ID_scores.csv','trace.parquet','locked_choices.json','coarse_inner.csv','MC.csv']]
            save_json(paths,outer_done,{'case_count':len(part),'role':role_record,
                'choices':[x for x in choices if x['outer_fold']==fold],
                'files':{p.name:file_sha256(p) for p in files}})
            del bins,pools,kernels,part,fine,coarse,allframe;gc.collect()
        if case_totals!=268998:raise ValueError('Primary outer30-day population changed')
        idframe=pd.concat(scores,ignore_index=True);summary=summarize_scores(idframe)
        save_frame(paths,run['results']/'ID_scores.csv',idframe);save_frame(paths,run['results']/'summary.csv',summary)
        save_json(paths,run['results']/'selected_parameters.json',choices)
        save_json(paths,run['provenance']/'outer_ID_roles.json',roles)
        intervals=comparison_intervals(idframe,c['bootstrap_replicates']);save_frame(paths,run['results']/'paired_ID_intervals.csv',intervals)
        mc=pd.concat([pd.read_csv(run['results']/f'outer_{f}_MC.csv') for f in range(5)])
        mc=mc.groupby('comparison',as_index=False)[['case_count','difference_sum_0','difference_sum_1','repeat_difference_squares']].sum()
        mc['delta_S']=(mc.difference_sum_0+mc.difference_sum_1)/(2*mc.case_count)
        mc['MC_SE']=np.sqrt(mc.repeat_difference_squares)/(2*mc.case_count)
        mc['MC_only_lower_95']=mc.delta_S-1.96*mc.MC_SE;mc['MC_only_upper_95']=mc.delta_S+1.96*mc.MC_SE
        save_frame(paths,run['results']/'outer_MC_summary.csv',mc)
        from data3001.modelling.markov_iteration_report import write_report
        write_report(paths,run,c,summary,intervals,choices)
        finish(paths,run,bound,sources,guard,{'elapsed_seconds':time.monotonic()-begun,'outer_folds':5,
            'inner_folds_per_outer':4,'all99_candidates_enter_inner_CV':True,'outer_primary_pairs':case_totals,
            'outer_independent_IDs':int(idframe.id.nunique()),'coarse_independently_optimised':True,
            'inner_numerical_method':c['inner_method'],'outer_numerical_method':'original_iid_particle_estimator64x2',
            'source_input_run':c['input_run'],'geometry_run':name})
    except Exception as e:failure(paths,run,e);raise
    finally:guard.active=False


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare-geometry',action='store_true');p.add_argument('--geometry-run')
    p.add_argument('--profile',action='store_true');p.add_argument('--resume-run');a=p.parse_args()
    paths=project_paths();c=validate_settings(json.loads((paths.root/CONFIG).read_text()))
    if a.prepare_geometry:prepare_geometry(paths,c)
    elif a.geometry_run:
        if a.profile:profile(paths,c,a.geometry_run)
        else:evaluate(paths,c,a.geometry_run,a.resume_run)
    else:p.error('Choose geometry preparation or a geometry run')


if __name__=='__main__':main()
