"""Run the approved exact-coordinate Markov experiment in bounded, isolated stages."""
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
from data3001.modelling.baselines.exact_origin_s4_e7_pipeline import pilot,primary
from data3001.modelling.baselines.exact_origin_s4_e7_inputs import permitted
from data3001.modelling.baselines.exact_origin_s4_e7_report import evaluate,report
from data3001.modelling.baselines.exact_origin_s4_e7_audit import audit_outputs
import pandas as pd
import pyproj

NAME='exact_origin_s4_e7'
CONFIG=f'configs/{NAME}.json'
FREEZE=f'provenance/reviews/{NAME}_execution_freeze.json'


def env_record():
    record=environment();record['packages']['scipy']=importlib.metadata.version('scipy');record['packages']['pyproj']=pyproj.__version__;record['packages']['proj_runtime']=pyproj.proj_version_str
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


def calculate(paths,run,cfg,stage,guard,resume_from=None):
    if stage=='pilot':
        return pilot(paths,run,cfg,guard)
    if resume_from:
        source=paths.root/'results/runs'/resume_from
        provenance=paths.root/'provenance/runs'/resume_from
        old=json.loads((provenance/'execution_freeze.json').read_text())
        current=json.loads((paths.root/FREEZE).read_text())
        assert old['plan_sha256']==current['plan_sha256'] and old['config_sha256']==current['config_sha256']
        reporting_files={'src/data3001/modelling/baselines/exact_origin_s4_e7_report.py',
                         'src/data3001/modelling/baselines/exact_origin_s4_e7_audit.py',
                         'src/data3001/modelling/baselines/run_exact_origin_s4_e7.py'}
        for name,digest in old['source_sha256'].items():
            if name not in reporting_files and not name.startswith('tests/'):
                assert current['source_sha256'][name]==digest, 'Recovery cannot change the estimator or inputs'
        prediction_freeze=json.loads((provenance/'forecast_freeze.json').read_text())
        assert prediction_freeze['status']=='FROZEN_BEFORE_OUTER_SCORING'
        for name,digest in prediction_freeze['files'].items():assert file_sha256(source/name)==digest
        inventory={}
        for original in sorted(source.rglob('*')):
            if original.is_file():
                relative=original.relative_to(source);payload=original.read_bytes()
                inventory[relative.as_posix()]=file_sha256(original)
                destination=run['results']/relative
                if destination.exists():
                    assert file_sha256(destination)==inventory[relative.as_posix()], 'Recovery configuration differs'
                else:
                    paths.publish(destination,lambda f,data=payload:f.write(data))
        for name in ['forecast_freeze.json','input_inventory.json','numerical_checks.json']:
            paths.publish(run['provenance']/name,lambda f,data=(provenance/name).read_bytes():f.write(data))
        print('Reusing verified frozen forecasts; independently auditing all scores.',flush=True)
        independent=audit_outputs(paths,run,cfg)
        save_json(paths,run['provenance']/'independent_audit.json',independent)
        save_json(paths,run['provenance']/'recovery_source.json',{'source_run':resume_from,
            'source_failure':json.loads((provenance/'failure.json').read_text()),'artifact_sha256':inventory,
            'estimator_and_input_code_unchanged':True,'fresh_replay_still_required':True})
        return {'stage':stage,'recovered_from':resume_from,'independent_audit':independent,
                'selected_k':int(pd.read_csv(run['results']/'choices.csv').iloc[0].k),
                'forecast_freeze_before_scoring':True,'B2_scores_reconciled':True}
    cases,choices,curves,examples,geography=primary(paths,run,cfg,guard)
    save_frame(paths,run['results']/'case_scores.parquet',cases)
    tables,multipliers,draws,ids=evaluate(cases,cfg)
    for name,table in tables.items():
        save_frame(paths,run['results']/(name+'.csv'),table)
    array_file(paths,run['results']/'multipliers.npy',multipliers)
    array_file(paths,run['results']/'paired_draws.npy',draws)
    save_json(paths,run['results']/'resampling.json',{'ids':ids,'resolutions':[1.,.5],
        'metrics':['brier','h90','k90','area90','mass','zero','exit','geographic_mass','exit_in_region'],
        'seed':cfg['bootstrap_seed'],'draws':cfg['bootstrap_draws'],'conditional_on_fixed_fits':True})
    import shapely as sh
    land=sh.from_wkb(paths.asset('land_mask_intermediate',verify=True).read_bytes())
    report(paths,run['results'],tables,choices,curves,examples,
           {'radius_m':cfg['radius_m'],'final_test_access':False,'land':land})
    independent=audit_outputs(paths,run,cfg)
    save_json(paths,run['provenance']/'independent_audit.json',independent)
    return {'stage':stage,'outer_cases':int(cases.resolution.eq(1.).sum()),'B2_scores_reconciled':True,
            'forecast_freeze_before_scoring':True,'exhaustive_neighbour_checks':True,'nested_grids_reconciled':True,
            'whole_ID_inference_independently_recomputed':True,'selected_k':int(choices.iloc[0].k),
            'independent_audit':independent}


def compare_replay(paths,run,prior):
    from scipy import sparse
    current=run['results'];previous=paths.root/'results/runs'/prior
    tables=['choices.csv','inner_curves.csv','inner_cases.parquet','outer_roster.parquet','outer_targets.parquet',
            'case_scores.parquet','summary.csv','paired.csv','decision.csv','support.csv','per_origin.csv',
            'id_origin_differences.csv','roles.parquet','training_coordinates.parquet','query_coordinates.parquet']
    for name in tables:
        reader=pd.read_parquet if name.endswith('.parquet') else pd.read_csv
        a,b=reader(current/name),reader(previous/name)
        assert list(a.columns)==list(b.columns) and a.shape==b.shape,name
        for col in a:
            if pd.api.types.is_numeric_dtype(a[col]) and not pd.api.types.is_bool_dtype(a[col]):
                atol=1e-9 if 'area' in col else 1e-12
                assert np.allclose(a[col],b[col],rtol=0,atol=atol,equal_nan=True),(name,col)
            else:pd.testing.assert_series_equal(a[col],b[col],check_exact=True)
    files=[]
    for f in (current/'forecasts').glob('*.npz'):
        other=previous/'forecasts'/f.name;a,b=sparse.load_npz(f),sparse.load_npz(other)
        assert a.shape==b.shape and np.array_equal(a.indices,b.indices) and np.array_equal(a.indptr,b.indptr)
        assert np.allclose(a.data,b.data,rtol=0,atol=1e-12),f.name
        files.append(f.name)
    for f in list((current/'forecasts').glob('*_states.npy'))+[current/'multipliers.npy',current/'paired_draws.npy']:
        a,b=np.load(f),np.load(previous/f.relative_to(current))
        assert np.array_equal(a,b),f.name
    return {'tables_compared':len(tables),'sparse_forecasts_compared':len(files),'discrete_decisions_identical':True,
            'probability_tolerance':1e-12,'area_tolerance_km2':1e-9}


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
    if args.resume_from:
        assert args.stage=='primary' and args.resume_from.startswith(NAME+'_primary_')
        prior_provenance=paths.root/'provenance/runs'/args.resume_from
        assert (prior_provenance/'failure.json').exists()
        assert (prior_provenance/'forecast_freeze.json').exists()
        for area in ['results','provenance']:
            allowed.extend(f for f in (paths.root/area/'runs'/args.resume_from).rglob('*') if f.is_file())
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
    def expire(signum,frame):raise TimeoutError('E7 resource cap')
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
        checks=calculate(paths,run,cfg,args.stage,guard,args.resume_from)
        scientific=sorted(f.relative_to(run['results']).as_posix() for f in run['results'].rglob('*') if f.is_file())
        save_json(paths,run['provenance']/'scientific_files.json',{'files':scientific})
        if args.stage=='pilot':
            projection=2*checks['projected_seconds'];projected_bytes=checks['projected_artifact_bytes']
            projected_rss=rss()+checks['projected_working_bytes']/1024**3
            passed=(projection<=min(cfg['seconds']['primary'],cfg['seconds']['replay']) and 2*projected_bytes<=cfg['storage_gib']*1024**3 and 2*projected_rss<=cfg['rss_gib'])
            save_json(paths,run['provenance']/'pilot_gate.json',{'passed':passed,'projected_seconds_per_run':projection,
                     'projected_total_bytes':projected_bytes,'freeze_sha256':file_sha256(paths.root/FREEZE),
                     'outer_skill_inspected':False,'all_cases_support_checked':True,'selected_k':False,'peak_rss_gib':rss(),'memory_reserved_gib':2*projected_rss})
            assert passed,'Insufficient measured capacity'
        if args.stage=='replay':
            checks['replay']=compare_replay(paths,run,args.replay_of)
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
    parser.add_argument('--pilot');parser.add_argument('--replay-of');parser.add_argument('--resume-from')
    run_stage(parser.parse_args())
