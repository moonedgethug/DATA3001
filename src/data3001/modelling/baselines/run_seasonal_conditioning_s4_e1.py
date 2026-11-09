"""Approved, bounded pilot / primary / fresh replay for S4 E1 v2."""
import time
START=time.monotonic()
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import signal
import sys
import threading
import numpy as np
import pandas as pd

from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import save_frame, save_json, _seal
from data3001.modelling.common.qualified_count_inputs import ExperimentGuard
from data3001.modelling.baselines import seasonal_conditioning_s4_e1_inputs as inputs
from data3001.modelling.baselines import seasonal_conditioning_s4_e1 as model
from data3001.modelling.baselines.seasonal_conditioning_s4_e1_audit import audit_prepared, audit_scored
from data3001.modelling.baselines.seasonal_conditioning_s4_e1_report import write_report

FREEZE='provenance/reviews/seasonal_conditioning_s4_e1_v2_execution_freeze.json'
THREAD_VARS=['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS']


def environment():
    return {'python':platform.python_version(),'platform':platform.platform(),
            'packages':{n:importlib.metadata.version(n) for n in ['numpy','pandas','pyarrow','matplotlib','shapely']},
            'threads':{n:os.environ.get(n) for n in THREAD_VARS}}


def fingerprint(paths,config):
    approval=json.loads((paths.root/config['approval']).read_text())
    assert approval['approved'] is True and approval['contract_sha256']==config['approved_plan_sha256']
    assert file_sha256(paths.root/config['approved_plan'])==config['approved_plan_sha256']
    freeze=json.loads((paths.root/FREEZE).read_text())
    assert freeze['config_sha256']==file_sha256(paths.root/'configs/seasonal_conditioning_s4_e1.json')
    for rel,digest in freeze['source_sha256'].items():
        assert file_sha256(paths.root/rel)==digest,rel
    assert freeze['environment']==environment()
    assert all(os.environ.get(n)=='1' for n in THREAD_VARS)
    assert config['final_test_access'] is False
    return freeze


def array_file(paths,p,array):
    paths.publish(p,lambda f:np.save(f,array,allow_pickle=False))


def metadata_hash(frame,columns):
    return hashlib.sha256(frame[columns].sort_values(columns).to_csv(index=False).encode()).hexdigest()


def persist_inputs(paths,run,bundle):
    q=bundle['qualified']
    tables={'origin_features.parquet':q[inputs.FEATURES],
            'targets.parquet':q[inputs.KEY+['destination_cell_1','target_epoch','required_interval_end_epoch','outside','first_exit_source_obs']],
            'role_membership.parquet':bundle['roles'],
            'training_counts_by_id_annual.parquet':bundle['annual_counts'],
            'training_counts_by_id_season.parquet':bundle['seasonal_counts'],
            'validation_denominators.parquet':bundle['validation'][inputs.FEATURES+['times_per_id_origin','ids_per_origin','origins_per_horizon','weight']],
            'roster.csv':bundle['roster'], 'state_index.parquet':bundle['state_index']}
    for name,frame in tables.items():save_frame(paths,run['results']/name,frame)
    ids={'validation_union':bundle['validation_ids'],
         'training_by_horizon':{str(h):sorted(bundle['train'].loc[bundle['train'].horizon_days.eq(h),'id'].unique().tolist()) for h in [7,30]},
         'training_source_key_sha256':metadata_hash(bundle['train'],inputs.KEY),
         'validation_source_key_sha256':metadata_hash(bundle['validation'],inputs.KEY)}
    save_json(paths,run['results']/'id_roles.json',ids)
    save_json(paths,run['provenance']/'input_inventory.json',bundle['inventory'])


def persist_forecasts(paths,run,bundle,matrices,support,meta,entries,freeze):
    save_frame(paths,run['results']/'training_support.csv',support)
    keys=sorted(matrices)
    save_frame(paths,run['results']/'matrix_keys.csv',pd.DataFrame(keys,columns=['horizon_days','origin_cell_1','departure_season']))
    array_file(paths,run['results']/'matrix_vectors.npy',np.array([np.zeros(len(bundle['states'])) if matrices[k] is None else matrices[k] for k in keys]))
    array_file(paths,run['results']/'destination_states.npy',bundle['states'])
    save_frame(paths,run['results']/'forecast_metadata.csv',meta)
    save_frame(paths,run['results']/'predictions.parquet',entries)
    files=['id_roles.json','validation_denominators.parquet','matrix_keys.csv','matrix_vectors.npy','destination_states.npy','training_support.csv','forecast_metadata.csv','predictions.parquet']
    save_json(paths,run['provenance']/'validation_forecast_freeze.json',{
        'stage':'FORECASTS_FROZEN_BEFORE_SCORING','created_UTC':datetime.now(timezone.utc).isoformat(),
        'scientific_definition_sha256':freeze['config_sha256'],
        'files':{n:file_sha256(run['results']/n) for n in files}})


def persist_scores(paths,run,cases,idmeans,summary,slices,multipliers,draws,intervals,flags):
    for n,f in [('case_scores.parquet',cases),('scores_by_id_origin.csv',idmeans),('summary.csv',summary),
                ('descriptive_slices.csv',slices),('uncertainty.csv',intervals),('contrasts.csv',flags)]:save_frame(paths,run['results']/n,f)
    array_file(paths,run['results']/'id_multipliers.npy',multipliers)
    array_file(paths,run['results']/'paired_draws.npy',draws)


def verify_replay(paths,run,prior):
    previous=paths.root/'results/runs'/prior
    receipt=json.loads((paths.root/'provenance/runs'/prior/'outputs.json').read_text())
    assert receipt['completed'] is True and receipt['final_test_access'] is False
    scientific=json.loads((paths.root/'provenance/runs'/prior/'scientific_files.json').read_text())['files']
    for name in scientific:
        p=previous/name;fresh=run['results']/name
        assert file_sha256(p)==receipt['output_sha256'][p.relative_to(paths.root).as_posix()]
        if p.suffix in ['.csv','.parquet']:
            a=pd.read_parquet(p) if p.suffix=='.parquet' else pd.read_csv(p)
            b=pd.read_parquet(fresh) if p.suffix=='.parquet' else pd.read_csv(fresh)
            pd.testing.assert_frame_equal(a,b,check_dtype=True,check_exact=False,atol=1e-12,rtol=0)
        elif p.suffix=='.npy':
            a=np.load(p,allow_pickle=False);b=np.load(fresh,allow_pickle=False)
            assert a.shape==b.shape and a.dtype==b.dtype
            assert np.allclose(a,b,atol=1e-12,rtol=0) if np.issubdtype(a.dtype,np.floating) else np.array_equal(a,b)
        else:assert file_sha256(p)==file_sha256(fresh),name
    return {'replay_of':prior,'scientific_files_compared':len(scientific),'passed':True,'numeric_atol':1e-12,'figures_byte_identical':True}


def run_stage(args):
    paths=project_paths();config=json.loads((paths.root/'configs/seasonal_conditioning_s4_e1.json').read_text())
    freeze=fingerprint(paths,config)
    cap=config['budget_seconds'][args.stage]
    previous=[];prior_elapsed=0.;allow=[]
    if args.stage!='pilot':
        assert args.pilot
        pp=paths.root/'provenance/runs'/args.pilot
        gate=json.loads((pp/'pilot_gate.json').read_text());assert gate['passed'] is True
        assert gate['execution_fingerprint']==file_sha256(paths.root/FREEZE)
        previous.append(args.pilot)
    if args.stage=='replay':
        assert args.replay_of;previous.append(args.replay_of)
    for rid in previous:
        assert Path(rid).name==rid
        for base in ['results/runs','provenance/runs']:
            allow.extend(p for p in (paths.root/base/rid).rglob('*') if p.is_file())
        receipt=json.loads((paths.root/'provenance/runs'/rid/'outputs.json').read_text())
        assert receipt['completed'] and not receipt['final_test_access']
        for rel,digest in receipt['output_sha256'].items():assert file_sha256(paths.root/rel)==digest
        prior_elapsed+=json.loads((paths.root/'provenance/runs'/rid/'resource_final.json').read_text())['accounted_seconds']
    assert prior_elapsed+cap<=config['budget_seconds']['total']+1e-9
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    rid=f'seasonal_conditioning_s4_e1_{args.stage}_{stamp}'
    run=paths.create_run(rid,config)
    guard=ExperimentGuard(paths,run,inputs.allowed_inputs(paths,config)+allow)
    sys.addaudithook(guard)
    timed={};done=threading.Event();resource_errors=[]
    def elapsed():return time.monotonic()-START
    def expired(signum,frame):raise TimeoutError('Stage resource deadline exceeded')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,max(.01,cap-elapsed()))
    def usage():
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return rss/(1024**3) if sys.platform=='darwin' else rss/(1024**2)
    def artifacts():
        dirs=[*run.values(),*[paths.root/b/r for r in previous for b in ['results/runs','provenance/runs']]]
        return sum(p.stat().st_size for d in dirs for p in d.rglob('*') if p.is_file())
    def watch():
        k=0
        while not done.wait(2):
            try:
                rss=usage();size=artifacts()
                save_json(paths,run['provenance']/f'resource_{k:04d}.json',{'elapsed_seconds':elapsed(),'peak_rss_gib':rss,'artifact_bytes_total':size})
                k+=1
                if rss>config['rss_limit_gib'] or size>config['artifact_limit_gib']*1024**3:
                    resource_errors.append('RSS/storage cap exceeded');os.kill(os.getpid(),signal.SIGALRM);return
            except Exception as ex:
                resource_errors.append(str(ex));os.kill(os.getpid(),signal.SIGALRM);return
    watcher=threading.Thread(target=watch,daemon=True);watcher.start()
    def measure(name,fn):
        start=time.monotonic();result=fn();timed[name]=time.monotonic()-start
        save_json(paths,run['provenance']/('stage_'+name+'.json'),{'elapsed_seconds':elapsed(),'component_seconds':timed[name]})
        return result
    try:
        save_json(paths,run['provenance']/'execution_fingerprint.json',freeze)
        save_json(paths,run['results']/'config.json',config)
        print(f'{args.stage}: started {rid}',flush=True)
        bundle=measure('inputs',lambda:inputs.load_inputs(paths,config))
        matrices,support=measure('fit',lambda:model.fit(bundle['train'],bundle['origins'],bundle['states'],config,bundle['validation_ids']))
        cache,meta,entries=measure('predict',lambda:model.predict(matrices,bundle['validation'][inputs.FEATURES],bundle['states']))
        reference,preaudit=measure('audit_pre',lambda:audit_prepared(bundle,matrices,support,cache,config))
        measure('save_inputs',lambda:persist_inputs(paths,run,bundle))
        measure('save_forecasts',lambda:persist_forecasts(paths,run,bundle,matrices,support,meta,entries,freeze))
        scorebundle=bundle
        if args.stage=='pilot':
            scorebundle=dict(bundle);scorebundle['validation']=bundle['validation'].copy()
            # Only deterministic synthetic targets, never actual validation outcomes.
            n=len(scorebundle['validation']);scorebundle['validation']['destination_cell_1']=bundle['states'][(np.arange(n)*17)%len(bundle['states'])]
        cases,idmeans,summary,slices=measure('score',lambda:model.score(cache,scorebundle['validation'],support,bundle['states']))
        multipliers,draws,intervals=measure('uncertainty',lambda:model.paired_uncertainty(idmeans,bundle['validation_ids'],config))
        flags=model.decisions(summary,intervals)
        postaudit=measure('audit_post',lambda:audit_scored(scorebundle,reference,cases,idmeans,summary,multipliers,draws,intervals,flags,config))
        outputrun=run
        if args.stage=='pilot':
            outputrun={'results':run['results']/'timing_fixture','provenance':run['provenance']}
            outputrun['results'].mkdir()
            save_json(paths,run['provenance']/'timing_fixture.json',{'synthetic_targets':True,'validation_skill_calculated':False,'cases':len(cases),'multiplier_shape':list(multipliers.shape),'target_rule':'states[(row_index*17)%state_count]','purpose':'capacity only'})
        measure('save_scores',lambda:persist_scores(paths,outputrun,cases,idmeans,summary,slices,multipliers,draws,intervals,flags))
        audit={**preaudit,**postaudit,'synthetic_targets':args.stage=='pilot'}
        names=measure('report',lambda:write_report(paths,outputrun,scorebundle,matrices,support,summary,intervals,flags,slices,audit,timing_only=args.stage=='pilot'))
        if args.stage=='pilot':
            measured=sum(timed.values())
            # Include whole interpreter/startup work and a bounded duplicate-I/O replay allowance.
            base_projection=elapsed()+timed['save_inputs']+timed['save_scores']+timed['report']
            projected=2*base_projection
            passed=projected<=min(config['budget_seconds']['primary'],config['budget_seconds']['replay']) and usage()<=config['rss_limit_gib'] and artifacts()*3<=config['artifact_limit_gib']*1024**3
            gate={'passed':bool(passed),'execution_fingerprint':file_sha256(paths.root/FREEZE),'projection_per_complete_run_seconds_with_2x_reserve':projected,'measured_components':timed,'unmeasured_material_components':[],
                  'role':'complete chronological roster','validation_skill_calculated':False,'measured_component_seconds':measured,'workload':{'qualified_pairs':len(bundle['qualified']),'training_pairs':len(bundle['train']),'validation_pairs':len(bundle['validation']),'forecast_keys':len(meta),'model_horizon_results':4,'multiplier_replicates':10000,'figures':10}}
            save_json(paths,run['provenance']/'pilot_gate.json',gate)
            if not passed:raise RuntimeError('Capacity not established; no primary run authorised')
            print('Pilot passed; projected complete run including reserve:',round(projected,2),'seconds',flush=True)
        else:
            scientific=[p.name for p in run['results'].iterdir() if p.is_file() and p.suffix in ['.csv','.parquet','.npy','.png','.json']]
            save_json(paths,run['provenance']/'scientific_files.json',{'files':sorted(scientific)})
            if args.stage=='replay':
                audit['replay']=measure('replay_compare',lambda:verify_replay(paths,run,args.replay_of))
        assert not guard.denied and not resource_errors
        assert elapsed()<=cap and prior_elapsed+elapsed()<=config['budget_seconds']['total']
        assert usage()<=config['rss_limit_gib'] and artifacts()<=config['artifact_limit_gib']*1024**3
        assert fingerprint(paths,config)==freeze
        done.set();watcher.join(timeout=3)
        accounted=float(np.ceil(elapsed()+10.))
        assert accounted<=cap and prior_elapsed+accounted<=config['budget_seconds']['total']
        save_json(paths,run['provenance']/'resource_final.json',{'stage':args.stage,'elapsed_seconds_before_sealing':elapsed(),'accounted_seconds':accounted,'closeout_reserve_seconds':10,'prior_accounted_seconds':prior_elapsed,'cumulative_accounted_seconds':prior_elapsed+accounted,'cap_seconds':cap,'peak_rss_gib':usage(),'artifact_bytes_total':artifacts(),'components':timed})
        save_json(paths,run['provenance']/'access.json',{'denied':guard.denied,'opened_inputs':sorted(str(p.relative_to(paths.root)) for p in guard.opened_inputs),'canonical_trajectory_reads':sorted(guard.read_ids),'final_test_access':False})
        _seal(paths,run,{**audit,'stage':args.stage,'completed_experiment':args.stage!='pilot','contract_sha256':config['approved_plan_sha256'],'input_sha256':bundle['inventory']})
        assert elapsed()<=accounted,'Sealing exceeded conservative closeout accounting'
        print(json.dumps({'run_id':rid,'stage':args.stage,'elapsed_seconds':elapsed(),'peak_rss_gib':usage(),'status':'PASSED'}),flush=True)
        if args.stage!='pilot':print(summary[['model','horizon_days','brier','k90','h90','fallback_pairs','annual_fallback']].to_string(index=False),flush=True)
    except BaseException as ex:
        done.set();watcher.join(timeout=3)
        signal.setitimer(signal.ITIMER_REAL,0)
        save_json(paths,run['provenance']/'failure.json',{'stage':args.stage,'completed':False,'error':repr(ex),'elapsed_seconds':elapsed(),'prior_elapsed_seconds':prior_elapsed,'components':timed,'denied':guard.denied,'resource_errors':resource_errors})
        raise
    finally:
        done.set();signal.setitimer(signal.ITIMER_REAL,0);guard.active=False


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',required=True,choices=['pilot','primary','replay'])
    parser.add_argument('--pilot');parser.add_argument('--replay-of');run_stage(parser.parse_args())


if __name__=='__main__':main()
