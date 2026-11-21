"""Approved bounded validation of existing models: pilot, primary and replay."""
import time
START=time.monotonic()
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import signal
import sys
import threading
import numpy as np
import pandas as pd
from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import save_frame, save_json, _seal
from data3001.modelling.common.qualified_count_inputs import ExperimentGuard
from data3001.modelling.baselines import temporal_validation_s4_e2_inputs as inputs
from data3001.modelling.baselines import temporal_validation_s4_e2 as val
from data3001.modelling.baselines import temporal_validation_s4_e2_audit as audit
from data3001.modelling.baselines.temporal_validation_s4_e2_report import write_report
from data3001.modelling.baselines.run_seasonal_conditioning_s4_e1 import environment, THREAD_VARS, array_file, verify_replay

CONFIG='configs/temporal_validation_s4_e2.json'
FREEZE='provenance/reviews/temporal_validation_s4_e2_execution_freeze.json'


def fingerprint(paths,config):
    approval=json.loads((paths.root/config['approval']).read_text())
    assert approval['approved'] and approval['plan_sha256']==config['plan_sha256']
    assert file_sha256(paths.root/config['plan'])==config['plan_sha256']
    freeze=json.loads((paths.root/FREEZE).read_text())
    assert freeze['config_sha256']==file_sha256(paths.root/CONFIG)
    for rel,digest in freeze['source_sha256'].items():assert file_sha256(paths.root/rel)==digest,rel
    assert freeze['environment']==environment()
    assert all(os.environ.get(k)=='1' for k in THREAD_VARS)
    assert not config['final_test_access']
    return freeze


def calculate(paths,run,config,freeze,timing_only,measure):
    bundle=measure('inputs',lambda:inputs.load_inputs(paths,config))
    outer,inner,ledger,roster,origin=measure('roles',lambda:inputs.build_roles(bundle,config))
    checks=measure('role_audit',lambda:audit.audit_roles(bundle,outer,inner,config))
    save_json(paths,run['provenance']/'input_inventory.json',bundle['inventory'])
    save_frame(paths,run['results']/'role_membership.parquet',ledger)
    save_frame(paths,run['results']/'role_roster.csv',roster)
    save_frame(paths,run['results']/'excluded_pre2001.parquet',bundle['excluded'])
    save_frame(paths,run['results']/'origin_features.parquet',bundle['q'][inputs.FEATURES])
    save_frame(paths,run['results']/'source_targets.parquet',bundle['q'][inputs.KEY+['destination_cell_1','required_interval_end_epoch','target_epoch','outside']])
    save_frame(paths,run['results']/'specifications.csv',pd.DataFrame(val.SPECS,columns=['model','parameter_a','parameter_gamma']).rename_axis('candidate').reset_index())
    save_frame(paths,run['results']/'state_index.parquet',bundle['state_index'])
    array_file(paths,run['results']/'destination_states.npy',bundle['states'])
    cache={};metas=[];selections=[];audits=[];references={};outer_rosters=[];calendar_parts=[]
    def calendar_composition(role,base):
        v=role['validation'][['id','horizon_days','origin_cell_1','origin_time_UTC']].copy()
        v['year']=v.origin_time_UTC.dt.year
        v['season']=v.origin_time_UTC.dt.month.map({12:'DJF',1:'DJF',2:'DJF',3:'MAM',4:'MAM',5:'MAM',6:'JJA',7:'JJA',8:'JJA',9:'SON',10:'SON',11:'SON'})
        v['supported']=[(h,i) in base.rows for h,i in v[['horizon_days','origin_cell_1']].itertuples(index=False,name=None)]
        z=v.groupby(['horizon_days','year','season'],as_index=False).agg(pairs=('id','size'),ids=('id','nunique'),origins=('origin_cell_1','nunique'),scored_pairs=('supported','sum'))
        calendar_parts.append(z.assign(role_name=role['name']))
    for b in [x['name'] for x in config['blocks']]:
        selected={}
        for policy in ['G','T']:
            parts=[]
            for role in inner[b][policy]:
                name=role['name'];print('Processing existing estimators:',name,flush=True)
                base=measure(name+'_fit',lambda:val.fit_role(role,bundle))
                calendar_composition(role,base)
                reference=measure(name+'_reference',lambda:audit.reference_fit(role['train'],bundle['states']))
                units=measure(name+'_candidates',lambda:val.candidate_brier(base,role['validation']))
                audits.append(measure(name+'_audit',lambda:audit.audit_inner(role,base,units,reference)))
                units['role_name']=name;parts.append(units)
                save_frame(paths,run['results']/f'inner/{name}_units.parquet',units)
                save_frame(paths,run['results']/f'inner/{name}_counts.parquet',inputs.counts(role['train']))
                save_frame(paths,run['results']/f'inner/{name}_support.csv',base.neighbour_support)
            collapsed,pool=val.pool_candidates(parts);chosen=val.select(pool)
            measure(f'{b}_{policy}_selection_audit',lambda:audit.audit_selection(parts,chosen,pool))
            selected[policy]=chosen
            selections.append(chosen.assign(block=b,policy=policy))
            save_frame(paths,run['results']/f'inner/{b}_{policy}_pooled_units.parquet',collapsed)
            save_frame(paths,run['results']/f'inner/{b}_{policy}_candidate_scores.csv',pool)
        role=outer[b]
        base=measure(b+'_outer_fit',lambda:val.fit_role(role,bundle))
        calendar_composition(role,base)
        references[b]=measure(b+'_outer_reference',lambda:audit.reference_fit(role['train'],bundle['states']))
        features=pd.DataFrame([(h,int(i)) for h in [7,30] for i in bundle['origins']],columns=['horizon_days','origin_cell_1'])
        forecasts,meta=val.forecast_block(base,selected,features,b)
        cache.update(forecasts);metas.append(meta)
        save_frame(paths,run['results']/f'outer/{b}_training_counts.parquet',inputs.counts(role['train']))
        save_frame(paths,run['results']/f'outer/{b}_support.csv',base.neighbour_support)
        v=role['validation'][inputs.FEATURES+['destination_cell_1']].copy()
        v['supported']=[(h,i) in base.rows for h,i in v[['horizon_days','origin_cell_1']].itertuples(index=False,name=None)]
        v=inputs.original.validation_weights(v).rename(columns={'weight':'eligible_weight'})
        supported=inputs.original.validation_weights(v.loc[v.supported].copy())
        v['score_weight']=supported.weight.reindex(v.index).fillna(0.)
        outer_rosters.append(v.assign(block=b))
    selections=pd.concat(selections,ignore_index=True);meta=pd.concat(metas,ignore_index=True)
    save_frame(paths,run['results']/'selections.csv',selections)
    save_frame(paths,run['results']/'validation_calendar_composition.csv',pd.concat(calendar_parts,ignore_index=True))
    save_frame(paths,run['results']/'outer_case_roster.parquet',pd.concat(outer_rosters,ignore_index=True))
    save_frame(paths,run['results']/'forecast_metadata.csv',meta)
    keys=sorted(cache)
    save_frame(paths,run['results']/'forecast_keys.csv',pd.DataFrame(keys,columns=['block','policy','model','horizon_days','origin_cell_1']))
    array_file(paths,run['results']/'forecast_vectors.npy',np.array([np.zeros(len(bundle['states'])) if cache[k] is None else cache[k]['p'] for k in keys]))
    save_json(paths,run['results']/'illustration.json',{'origin':origin,'rule':'largest minimum distinct fitting ID support across all block/horizon roles; smallest cell tie'})
    freeze_files={p.relative_to(run['results']).as_posix():file_sha256(p) for p in run['results'].rglob('*') if p.is_file()}
    save_json(paths,run['provenance']/'outer_forecast_freeze.json',{'state':'ALL_OUTER_FORECASTS_FROZEN_BEFORE_SCORING',
        'created_UTC':datetime.now(timezone.utc).isoformat(),'files':freeze_files,'source_freeze':freeze['config_sha256']})
    print('All three blocks frozen; now scoring '+('synthetic pilot targets' if timing_only else 'outer validation targets'),flush=True)
    scoring={};case_parts=[]
    for b,role in outer.items():
        r=dict(role);v=role['validation'].copy()
        if timing_only:v['destination_cell_1']=bundle['states'][(np.arange(len(v))*17)%len(bundle['states'])]
        r['validation']=v;scoring[b]=r
        case_parts.append(measure(b+'_outer_scores',lambda:val.score_block(cache,v,b,bundle['states'])))
    cases=pd.concat(case_parts,ignore_index=True);units,summary=val.summaries(cases)
    for b,r in scoring.items():
        audits.append(measure(b+'_outer_audit',lambda:audit.audit_outer(r,cache,meta[meta.block.eq(b)],cases[cases.block.eq(b)],units,summary,references[b],b)))
    ids,multipliers,draws,intervals=measure('uncertainty',lambda:val.uncertainty(units,config))
    flags=val.decisions(summary,intervals,config)
    checks.update(measure('uncertainty_audit',lambda:audit.audit_uncertainty(units,ids,multipliers,draws,intervals,flags,summary,config)))
    targetrun=run
    if timing_only:
        targetrun={'results':run['results']/'timing_fixture','provenance':run['provenance']};targetrun['results'].mkdir()
    for name,frame in [('case_scores.parquet',cases),('scores_by_ID_origin.parquet',units),('summary.csv',summary),('uncertainty.csv',intervals),('decisions.csv',flags)]:
        save_frame(paths,targetrun['results']/name,frame)
    array_file(paths,targetrun['results']/'multipliers.npy',multipliers)
    array_file(paths,targetrun['results']/'paired_draws.npy',draws)
    save_json(paths,targetrun['results']/'resampling.json',{'sorted_IDs':[int(d) for d in ids],'generator':'PCG64','distribution':'Exp(1)','seed':config['seed'],'replicates':config['replicates'],'fixed_fits':True})
    images=measure('report',lambda:write_report(paths,targetrun,bundle,outer,cache,meta,summary,intervals,flags,selections,roster,config,origin,timing_only))
    checks.update(existing_model_implementations_reused=True,new_estimator_families=False,B2_identical_between_policies=True,
        independent_role_candidate_outer_checks=audits,figures=len(images),synthetic_outer_targets=timing_only,
        primary_equivalence_all_blocks=bool(flags.equivalent_supported.all()),all_outer_forecasts_frozen=True)
    return bundle,checks,summary


def run_stage(args):
    paths=project_paths();config=json.loads((paths.root/CONFIG).read_text());freeze=fingerprint(paths,config)
    prior=0.;stage_prior=0.;allow=[];previous=[]
    # Charge every earlier attempt, including failures, not only successful parents.
    for p in sorted((paths.root/'provenance/runs').glob('temporal_validation_s4_e2_*')):
        receipt=p/'resource_final.json';failure=p/'failure.json'
        if receipt.exists():charged=json.loads(receipt.read_text())['accounted_seconds']
        elif failure.exists():charged=json.loads(failure.read_text())['elapsed_seconds']
        else:raise RuntimeError('Unaccounted previous attempt: '+p.name)
        prior+=charged
        if p.name.startswith(f'temporal_validation_s4_e2_{args.stage}_'):stage_prior+=charged
    if args.stage!='pilot':
        assert args.pilot;pp=paths.root/'provenance/runs'/args.pilot
        gate=json.loads((pp/'pilot_gate.json').read_text())
        assert gate['passed'] and gate['execution_fingerprint']==file_sha256(paths.root/FREEZE)
        previous.append(args.pilot)
    if args.stage=='replay':assert args.replay_of;previous.append(args.replay_of)
    for rid in previous:
        assert Path(rid).name==rid and rid.startswith('temporal_validation_s4_e2_')
        receipt=json.loads((paths.root/'provenance/runs'/rid/'outputs.json').read_text())
        assert receipt['completed'] and not receipt['final_test_access']
        for rel,digest in receipt['output_sha256'].items():assert file_sha256(paths.root/rel)==digest
        for where in ['results/runs','provenance/runs']:allow.extend(p for p in (paths.root/where/rid).rglob('*') if p.is_file())
    cap=config['budget_seconds'][args.stage]-stage_prior
    assert cap>0 and prior+cap<=config['budget_seconds']['total']
    rid=f'temporal_validation_s4_e2_{args.stage}_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run=paths.create_run(rid,config);guard=ExperimentGuard(paths,run,inputs.allowed_inputs(paths,config)+allow)
    sys.addaudithook(guard);done=threading.Event();errors=[];timings={}
    def elapsed():return time.monotonic()-START
    def rss():
        x=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return x/(1024**3) if sys.platform=='darwin' else x/(1024**2)
    def size():return sum(p.stat().st_size for root in ['results/runs','provenance/runs'] for d in (paths.root/root).glob('temporal_validation_s4_e2_*') for p in d.rglob('*') if p.is_file())
    def expired(signum,frame):raise TimeoutError('Resource cap exceeded')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,max(.01,cap-elapsed()))
    def watch():
        k=0
        while not done.wait(3):
            try:
                save_json(paths,run['provenance']/f'resource_{k:04d}.json',{'elapsed_seconds':elapsed(),'peak_rss_gib':rss(),'cumulative_artifact_bytes':size()});k+=1
                if rss()>config['rss_limit_gib'] or size()>config['artifact_limit_gib']*1024**3:
                    errors.append('Memory/storage cap');os.kill(os.getpid(),signal.SIGALRM);return
            except Exception as e:errors.append(repr(e));os.kill(os.getpid(),signal.SIGALRM);return
    watcher=threading.Thread(target=watch,daemon=True);watcher.start()
    def measure(name,fn):
        start=time.monotonic();result=fn();timings[name]=time.monotonic()-start
        save_json(paths,run['provenance']/('stage_'+name+'.json'),{'component_seconds':timings[name],'elapsed_seconds':elapsed()})
        return result
    try:
        print('Started',rid,flush=True)
        save_json(paths,run['results']/'config.json',config);save_json(paths,run['provenance']/'execution_fingerprint.json',freeze)
        bundle,checks,summary=calculate(paths,run,config,freeze,args.stage=='pilot',measure)
        if args.stage=='pilot':
            projection=2*(elapsed()+10)
            passed=projection<=min(config['budget_seconds']['primary'],config['budget_seconds']['replay']) and rss()<=config['rss_limit_gib'] and size()*3<=config['artifact_limit_gib']*1024**3
            save_json(paths,run['provenance']/'pilot_gate.json',{'passed':bool(passed),'execution_fingerprint':file_sha256(paths.root/FREEZE),
                'projected_seconds_per_complete_run_with_2x_reserve':projection,'full_roles':24,'all_samples_used':True,'outer_validation_skill_calculated':False,'synthetic_outer_targets':True,'unmeasured_material_components':[]})
            assert passed,'Pilot did not establish capacity'
        else:
            names=sorted(p.relative_to(run['results']).as_posix() for p in run['results'].rglob('*') if p.is_file() and p.suffix in ['.csv','.parquet','.npy','.png','.json'])
            save_json(paths,run['provenance']/'scientific_files.json',{'files':names})
            if args.stage=='replay':checks['replay']=measure('replay_compare',lambda:verify_replay(paths,run,args.replay_of))
        assert fingerprint(paths,config)==freeze and not guard.denied and not errors
        assert rss()<=config['rss_limit_gib'] and size()<=config['artifact_limit_gib']*1024**3
        done.set();watcher.join(timeout=4);accounted=float(np.ceil(elapsed()+10))
        assert accounted<=cap and prior+accounted<=config['budget_seconds']['total']
        save_json(paths,run['provenance']/'resource_final.json',{'elapsed_seconds_before_sealing':elapsed(),'accounted_seconds':accounted,
            'prior_accounted_seconds':prior,'cumulative_accounted_seconds':prior+accounted,'cap_seconds':cap,'peak_rss_gib':rss(),'cumulative_artifact_bytes':size(),'components':timings})
        save_json(paths,run['provenance']/'access.json',{'denied':guard.denied,'canonical_trajectory_reads':sorted(guard.read_ids),
            'opened_inputs':sorted(str(p.relative_to(paths.root)) for p in guard.opened_inputs),'final_test_access':False})
        _seal(paths,run,{**checks,'input_sha256':bundle['inventory'],'stage':args.stage,'completed_experiment':args.stage!='pilot'})
        assert elapsed()<=accounted
        print(json.dumps({'run_id':rid,'stage':args.stage,'status':'PASSED','elapsed_seconds':elapsed(),'peak_rss_gib':rss()}),flush=True)
        if args.stage!='pilot':print(summary[summary.model=='Selected'][['block','policy','horizon_days','brier','k90','h90','zero_truth']].to_string(index=False),flush=True)
    except BaseException as e:
        done.set();watcher.join(timeout=4);signal.setitimer(signal.ITIMER_REAL,0)
        save_json(paths,run['provenance']/'failure.json',{'error':repr(e),'elapsed_seconds':elapsed(),'denied':guard.denied,'resource_errors':errors,'completed':False})
        raise
    finally:done.set();signal.setitimer(signal.ITIMER_REAL,0);guard.active=False


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['pilot','primary','replay'],required=True)
    p.add_argument('--pilot');p.add_argument('--replay-of');run_stage(p.parse_args())


if __name__=='__main__':main()
