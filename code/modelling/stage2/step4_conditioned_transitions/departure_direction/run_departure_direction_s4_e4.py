"""Run the approved departure-heading experiment in bounded, isolated stages."""
import time
START=time.monotonic()
import argparse
from datetime import datetime,timezone
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import signal
import sys
import threading
import numpy as np

from data3001.paths import project_paths,file_sha256
from data3001.modelling.common.runtime import save_frame,save_json,verified_run,_seal
from data3001.modelling.common.qualified_count_inputs import ExperimentGuard
from data3001.modelling.baselines.run_seasonal_conditioning_s4_e1 import environment,THREAD_VARS,array_file,verify_replay
from data3001.modelling.baselines.seasonal_conditioning_s4_e1_inputs import KEY
from data3001.modelling.baselines.departure_direction_s4_e4_pipeline import prepare,permitted,score
from data3001.modelling.baselines.departure_direction_s4_e4_report import evaluate,report
import pandas as pd
import pyproj

NAME='departure_direction_s4_e4'
CONFIG=f'configs/{NAME}.json'
FREEZE=f'provenance/reviews/{NAME}_execution_freeze.json'


def env_record():
    record=environment();record['packages']['pyproj']=pyproj.__version__;record['packages']['proj_runtime']=pyproj.proj_version_str
    return record


def fingerprint(paths,cfg):
    freeze=json.loads((paths.root/FREEZE).read_text())
    approval=json.loads((paths.root/cfg['approval']).read_text())
    assert approval['approved'] and file_sha256(paths.root/cfg['plan'])==approval['plan_sha256']==freeze['plan_sha256']
    assert file_sha256(paths.root/CONFIG)==freeze['config_sha256'] and not cfg['final_test_access']
    assert all(os.environ.get(k)=='1' for k in THREAD_VARS) and env_record()==freeze['environment']
    for rel,digest in freeze['source_sha256'].items():
        assert file_sha256(paths.root/rel)==digest,rel
    return freeze


def calculate(paths,run,cfg,stage,guard):
    outer,states,ref,old,choices,curves,thresholds,roster,forecasts=prepare(paths,run,cfg,guard)
    pilot=stage=='pilot'
    directory=run['results']/'timing_fixture' if pilot else run['results']
    print('All outer forecasts and regions frozen. Scoring '+('synthetic' if pilot else 'historical')+' targets.',flush=True)
    targets=outer['validation'][KEY].copy()
    targets['destination_cell_1']=(states[(np.arange(len(targets))*17)%len(states)] if pilot
                                   else outer['validation'].destination_cell_1.to_numpy())
    cases=score(roster,targets,forecasts)
    tables,multipliers,draws,ids=evaluate(cases,roster,cfg)
    if not pilot:
        current=tables['summary'].query("model=='Annual'").sort_values('horizon_days')
        for baseline in [pd.read_csv(ref/'summary.csv').query("block=='C' and policy=='G' and model=='B2'"),
                         pd.read_csv(old/'summary.csv').query("model=='Annual'")]:
            metrics=['brier','h90','k90']
            assert np.allclose(current[metrics],baseline.sort_values('horizon_days')[metrics],rtol=0,atol=1e-12)
    for name,table in tables.items():
        save_frame(paths,directory/(name+'.csv'),table)
    save_frame(paths,directory/'case_scores.parquet',cases)
    array_file(paths,directory/'multipliers.npy',multipliers)
    array_file(paths,directory/'paired_draws.npy',draws)
    save_json(paths,directory/'resampling.json',{'ids':[int(i) for i in ids],'horizons':[7,30],'metrics':['brier','h90','k90'],
              'bootstrap_seed':cfg['bootstrap_seed'],'draws':len(multipliers),'conditional_on_fixed_fits':True})
    report(paths,directory,tables,choices,curves,thresholds,pilot)
    return {'stage':stage,'synthetic_outer_targets':pilot,'B2_scores_reconciled':not pilot,'B2_weights_vectors_regions_reconciled':True,
            'threshold_and_direct_donor_checks':True,'inner_grid_and_solution_recomputed':True,'primary_multiplier_bound_recomputed':True,
            'verified_canonical_IDs':len(guard.read_ids),'outer_cases':len(cases)}


def run_stage(args):
    paths=project_paths();cfg=json.loads((paths.root/CONFIG).read_text());freeze=fingerprint(paths,cfg)
    cap=cfg['seconds'][args.stage]
    prior=0.;stage_used=0.
    for folder in (paths.root/'provenance/runs').glob(NAME+'_*'):
        final=folder/'resource_final.json';failure=folder/'failure.json'
        if final.exists():charge=json.loads(final.read_text())['accounted_seconds']
        elif failure.exists():charge=json.loads(failure.read_text())['elapsed_seconds']
        else:raise RuntimeError('Prior attempt without resource receipt: '+folder.name)
        prior+=charge
        if folder.name.startswith(NAME+'_'+args.stage+'_'):stage_used+=charge
    allowance=min(cap-stage_used,cfg['seconds']['total']-prior)
    assert allowance>0
    allowed=permitted(paths,cfg)
    parents=[]
    if args.stage!='pilot':
        assert args.pilot and args.pilot.startswith(NAME+'_pilot_')
        parents.append(args.pilot)
        gate=json.loads((paths.root/'provenance/runs'/args.pilot/'pilot_gate.json').read_text())
        assert gate['passed'] and gate['freeze_sha256']==file_sha256(paths.root/FREEZE)
    if args.stage=='replay':
        assert args.replay_of and args.replay_of.startswith(NAME+'_primary_')
        parents.append(args.replay_of)
    for parent in parents:
        verified_run(paths,parent)
        assert file_sha256(paths.root/'provenance/runs'/parent/'execution_freeze.json')==file_sha256(paths.root/FREEZE)
        for area in ['results','provenance']:
            allowed.extend(f for f in (paths.root/area/'runs'/parent).rglob('*') if f.is_file())
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    rid=f'{NAME}_{args.stage}_{stamp}'
    run=paths.create_run(rid,cfg);guard=ExperimentGuard(paths,run,allowed);sys.addaudithook(guard)
    stop=threading.Event()
    def elapsed():return time.monotonic()-START
    def rss():
        size=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return size/(1024**3 if sys.platform=='darwin' else 1024**2)
    def storage():
        total=0
        for area in ['results','provenance']:
            for r in (paths.root/area/'runs').glob(NAME+'_*'):
                for f in r.rglob('*'):
                    try:
                        if f.is_file():total+=f.stat().st_size
                    except FileNotFoundError:
                        continue  # An atomic temporary artifact was published during the scan.
        return total
    def expire(signum,frame):raise TimeoutError('E4 resource cap')
    def monitor():
        count=0
        while not stop.wait(5):
            size=storage()
            save_json(paths,run['provenance']/f'heartbeat_{count:03d}.json',{'elapsed':elapsed(),'rss_gib':rss(),'artifact_bytes':size})
            count+=1
            if rss()>cfg['rss_gib'] or size>cfg['storage_gib']*1024**3:
                os.kill(os.getpid(),signal.SIGALRM);return
    signal.signal(signal.SIGALRM,expire);signal.setitimer(signal.ITIMER_REAL,max(.01,allowance-elapsed()))
    watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
    try:
        print('Started',rid,flush=True)
        paths.publish(run['provenance']/'execution_freeze.json',lambda f:f.write((paths.root/FREEZE).read_bytes()))
        save_json(paths,run['results']/'config.json',cfg)
        checks=calculate(paths,run,cfg,args.stage,guard)
        scientific=sorted(f.relative_to(run['results']).as_posix() for f in run['results'].rglob('*') if f.is_file())
        save_json(paths,run['provenance']/'scientific_files.json',{'files':scientific})
        if args.stage=='pilot':
            projection=2*(elapsed()+12);projected_bytes=storage()*3
            passed=projection<=min(cfg['seconds']['primary'],cfg['seconds']['replay']) and projected_bytes<=cfg['storage_gib']*1024**3
            save_json(paths,run['provenance']/'pilot_gate.json',{'passed':passed,'projected_seconds_per_run':projection,
                     'projected_total_bytes':projected_bytes,'freeze_sha256':file_sha256(paths.root/FREEZE),
                     'outer_skill_inspected':False,'all_cases_and_headings':True})
            assert passed,'Insufficient measured capacity'
        if args.stage=='replay':
            checks['replay']=verify_replay(paths,run,args.replay_of)
            prev=json.loads((paths.root/'provenance/runs'/args.replay_of/'scientific_files.json').read_text())['files']
            assert scientific==prev
        assert fingerprint(paths,cfg)==freeze and not guard.denied and set(guard.read_ids)=={int(p.stem) for p in guard.input_files if p.parent==paths.data_root / "train"}
        stop.set();watcher.join();charged=float(np.ceil(elapsed()+12))
        assert charged<=allowance and rss()<=cfg['rss_gib'] and storage()<=cfg['storage_gib']*1024**3
        save_json(paths,run['provenance']/'access.json',{'denied':guard.denied,'canonical_trajectory_reads':sorted(guard.read_ids),
                   'final_test_access':False,'opened_inputs':sorted(p.relative_to(paths.root).as_posix() for p in guard.opened_inputs)})
        save_json(paths,run['provenance']/'resource_final.json',{'elapsed_before_sealing':elapsed(),'accounted_seconds':charged,
                   'prior_seconds':prior,'total_seconds':charged+prior,'rss_gib':rss(),'total_bytes':storage()})
        _seal(paths,run,checks)
        assert elapsed()<=charged
        print('PASSED',rid,'elapsed',round(elapsed(),1),'RSS',round(rss(),2),flush=True)
    except BaseException as e:
        stop.set();watcher.join();signal.setitimer(signal.ITIMER_REAL,0)
        save_json(paths,run['provenance']/'failure.json',{'error':repr(e),'elapsed_seconds':elapsed(),'denied':guard.denied})
        raise
    finally:
        stop.set();signal.setitimer(signal.ITIMER_REAL,0);guard.active=False


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',choices=['pilot','primary','replay'],required=True)
    parser.add_argument('--pilot');parser.add_argument('--replay-of')
    run_stage(parser.parse_args())
