"""Bounded, read-only-model validation; never starts the full experiment."""
import os
for _key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[_key]='1'
import concurrent.futures as futures
import cProfile
import json
import multiprocessing as mp
from pathlib import Path
import pstats
import sys
import time
import numpy as np
import pandas as pd
from data3001.paths import file_sha256
from . import local_gmm_s5_e2_pipeline as pipe
from . import local_gmm_s5_e2_numerics as original
from . import local_gmm_s5_e2_scoreopt as optimized
from . import local_gmm_s5_e2_selection as selection

STATE={}


def compare_scores(old,new):
    assert old['sample_count']==new['sample_count'], 'ES node count changed'
    a=np.asarray(old['replicate_means']);b=np.asarray(new['replicate_means'])
    assert a.shape==b.shape==(8,), 'Replicate roster changed'
    np.testing.assert_allclose(a,b,atol=1e-9,rtol=0)
    np.testing.assert_allclose(old['energy_km'],new['energy_km'],atol=1e-9,rtol=0)
    np.testing.assert_allclose(old['variance'],new['variance'],atol=1e-16,rtol=1e-8)
    return dict(replicate_max_absolute_km=float(np.max(abs(a-b))),
        energy_absolute_km=abs(old['energy_km']-new['energy_km']),
        variance_absolute=abs(old['variance']-new['variance']))


def old_scores(packets,truth,key):
    values={}
    for k,p in sorted(packets.items()):
        values[k]=values[1] if k>1 and p['fallback'] else original.score_es(p,truth,65536,key)
    return values


def initialize(run,targets,library):
    guard=pipe.previous_inputs.Guard(pipe.ROOT,run);sys.addaudithook(guard)
    STATE.update(run=run,targets=targets,library=library,guard=guard)


def one(rec,truth,paired):
    packets={int(k):v for k,v in rec['models'].items()};key=tuple(rec['key']);times={};values={};profile={}
    order=['old','new'] if rec['query_position']%2==0 else ['new','old']
    for name in order if paired else ['new']:
        started=time.monotonic()
        values[name]=old_scores(packets,truth,key) if name=='old' else optimized.score_models(
            packets,truth,65536,key,STATE['library'],profile)
        times[name]=time.monotonic()-started
    return values,times,profile


def worker(task):
    role,batch,positions,paired=task;run=STATE['run']
    records=pipe.previous_io.read_bundle(pipe.batch_paths(run,role,batch)['parameters'])
    stored=None
    if not paired:
        stored=pd.read_parquet(pipe.batch_paths(run,role,batch)['energy']).set_index(['query_position','model'])
    rows=[];started=time.monotonic()
    for rec in records:
        pos=rec['query_position']
        if positions is not None and pos not in positions:continue
        values,times,profile=one(rec,STATE['targets'][role][pos],paired)
        for k,new in values['new'].items():
            if paired:old=values['old'][k]
            else:
                old=stored.loc[(pos,k)].to_dict()
                old['sample_count']=int(old['sample_count'])
            delta=compare_scores(old,new)
            rows.append(dict(role=role,id=rec['id'],query_position=pos,model=k,**delta,
                old=old,new=new,timings=times,profile=profile,fallback=rec['models'][str(k)]['fallback']))
    if STATE['guard'].denied or STATE['guard'].outcomes_read:raise PermissionError('Unexpected data access')
    return dict(rows=rows,elapsed_seconds=time.monotonic()-started,role=role,batch=batch)


def pool_run(tasks,run,targets,library):
    rows=[];seconds=[];started=time.monotonic()
    with futures.ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('spawn'),
            initializer=initialize,initargs=(run,targets,library)) as pool:
        pending={pool.submit(worker,t):t for t in tasks[:2]};todo=iter(tasks[2:]);last=time.monotonic()
        while pending:
            done,_=futures.wait(pending,timeout=10,return_when=futures.FIRST_COMPLETED)
            for job in done:
                result=job.result();rows.extend(result['rows']);seconds.append(result['elapsed_seconds']);del pending[job]
                task=next(todo,None)
                if task is not None:pending[pool.submit(worker,task)]=task
            if time.monotonic()-last>=25:
                print('SCORING_CHECK',len(rows)//3,'queries',round(time.monotonic()-started,2),'seconds',flush=True)
                last=time.monotonic()
    return rows,dict(wall_seconds=time.monotonic()-started,worker_seconds=sum(seconds),batches=len(tasks))


def run(name):
    start=time.monotonic();paths,run,cfg,approval,guard=pipe.context(name)
    folder=run['provenance']/'score_optimization'
    if (folder/'validation.json').exists():raise FileExistsError('Validation already recorded')
    for role in ['C_T0','C_T1']:pipe.verify_freeze(run['provenance'],role,pipe.COUNTS[role],'parameters')
    protected={}
    for p in run['results'].rglob('*'):
        if p.is_file():protected[str(p.relative_to(pipe.ROOT))]=file_sha256(p)
    for p in [run['provenance']/'frozen_config.json',run['provenance']/'source_hashes.json',pipe.ROOT/'configs/local_gmm_s5_e2.json']:
        protected[str(p.relative_to(pipe.ROOT))]=file_sha256(p)
    native=folder/'libe2_score.dylib'
    if not native.exists():optimized.compile_kernel(native)
    targets={};fixed=[];records={}
    for role in ['C_T0','C_T1']:
        fit,query,target=pipe.load_role(cfg,role,True)
        targets[role]=target[['endpoint_lon','endpoint_lat']].to_numpy(float)
        positions=np.floor(np.arange(64)*(len(query)-1)/63).astype(int)
        for batch in sorted(set(positions//32)):
            keep=positions[positions//32==batch].tolist();fixed.append((role,int(batch),keep,True))
            for rec in pipe.previous_io.read_bundle(pipe.batch_paths(run,role,int(batch))['parameters']):
                if rec['query_position'] in keep:records[role,rec['query_position']]=rec
        del fit,query,target
    assert len(records)==128
    print('INPUTS_FROZEN',len(records),'fixed_queries',flush=True)
    fixed_rows,fixed_cost=pool_run(fixed,run,targets,str(native))
    assert len(fixed_rows)==128*3
    # Serial repeat on every prespecified key proves scheduling does not change nodes or values.
    initialize(run,targets,str(native));serial_max=0.;serial_start=time.monotonic()
    paired={(r['role'],r['query_position'],r['model']):r for r in fixed_rows}
    for (role,pos),rec in records.items():
        values,_,_=one(rec,targets[role][pos],False)
        for k,v in values['new'].items():
            previous=paired[role,pos,k]['new'];d=compare_scores(previous,v)
            if previous!=v:raise AssertionError('Serial/spawn output is not identical')
            serial_max=max(serial_max,d['replicate_max_absolute_km'])
    serial_seconds=time.monotonic()-serial_start
    # Profile the untouched old scorer on 16 prespecified records, separate from speed timings.
    profiler=cProfile.Profile()
    for role in ['C_T0','C_T1']:
        for (rr,pos),rec in sorted(records.items()):
            if rr==role and list(sorted(k for k in records if k[0]==role)).index((rr,pos))%8==0:
                profiler.runcall(old_scores,{int(k):p for k,p in rec['models'].items()},targets[role][pos],tuple(rec['key']))
    stats=pstats.Stats(profiler)
    profile=[dict(file=k[0],line=k[1],function=k[2],calls=v[1],self_seconds=v[2],cumulative_seconds=v[3])
        for k,v in sorted(stats.stats.items(),key=lambda kv:kv[1][2],reverse=True)[:30]]
    retained=[];previous_seconds=0.
    for role in ['C_T0','C_T1']:
        for p in sorted((run['provenance']/'batches'/role/'energy').glob('*.json')):
            receipt=json.loads(p.read_text())
            for path,h in receipt['sha256'].items():
                assert file_sha256(pipe.ROOT/path)==h
            retained.append((role,receipt['batch'],None,False));previous_seconds+=receipt['elapsed_seconds']
    assert sum(json.loads(p.read_text())['cases'] for role in ['C_T0','C_T1']
        for p in (run['provenance']/'batches'/role/'energy').glob('*.json'))==2176
    print('FIXED_128_PASSED; START_EXISTING_2176',flush=True)
    retained_rows,retained_cost=pool_run(retained,run,targets,str(native))
    assert len(retained_rows)==2176*3
    # Compare ID-weighted summaries and paired numerical uncertainty without selecting a model.
    aggregation=[]
    for label,rows in [('fixed128',fixed_rows),('retained2176',retained_rows)]:
        frames={side:pd.DataFrame([dict(role=r['role'],id=r['id'],query_position=r['query_position'],model=r['model'],
            energy_km=r[side]['energy_km'],replicate_means=r[side]['replicate_means'],variance=r[side]['variance']) for r in rows])
            for side in ['old','new']}
        a,b=[selection.pooled_id_means(frames[s],'energy_km') for s in ['old','new']]
        np.testing.assert_allclose(a,b,rtol=0,atol=1e-9)
        for k in [2,3]:
            u,v=[selection.paired_numerics(frames[s],k,1) for s in ['old','new']]
            np.testing.assert_allclose(u,v,rtol=1e-8,atol=1e-12)
        aggregation.append(dict(subset=label,unique_ids=int(a.shape[0]),max_id_mean_difference_km=float(np.max(abs(a.to_numpy()-b.to_numpy())))))
    for path,h in protected.items():
        if file_sha256(pipe.ROOT/path)!=h:raise AssertionError('Existing file changed: '+path)
    for path,h in json.loads((run['provenance']/'source_hashes.json').read_text()).items():
        if file_sha256(pipe.ROOT/path)!=h:raise AssertionError('Formal source changed: '+path)
    cases=[r for r in fixed_rows if r['model']==1]
    old_time=sum(r['timings']['old'] for r in cases);new_time=sum(r['timings']['new'] for r in cases)
    all_rows=fixed_rows+retained_rows;profile_new={k:sum(r['profile'].get(k,0.) for r in cases) for k in cases[0]['profile']}
    result=dict(passed=True,run=name,node_count=65536,replicates=8,fixed_queries=128,retained_queries=2176,
        same_workload_speedup=old_time/new_time,matched_old_worker_seconds=old_time,matched_new_worker_seconds=new_time,
        retained_old_worker_seconds=previous_seconds,retained_new_worker_seconds=retained_cost['worker_seconds'],
        historical_batch_speedup=previous_seconds/retained_cost['worker_seconds'],fixed_cost=fixed_cost,retained_cost=retained_cost,
        serial_repeat_seconds=serial_seconds,serial_spawn_bitwise_identical=serial_max==0,
        max_replicate_difference_km=max(r['replicate_max_absolute_km'] for r in all_rows),
        max_score_difference_km=max(r['energy_absolute_km'] for r in all_rows),
        max_variance_difference=max(r['variance_absolute'] for r in all_rows),
        old_profile_16_queries=profile,new_profile_128_queries=profile_new,
        aggregation_checks=aggregation,original_files_verified=len(protected),
        outer_targets_read=guard.outcomes_read,final_test_access=False,full_experiment_resumed=False,
        scientific_models_modified=False,validation_seconds=time.monotonic()-start)
    if guard.denied or guard.outcomes_read:raise PermissionError('Unexpected parent data access')
    pipe.save_json(paths,folder/'validation.json',result)
    # Detailed numeric evidence, not a model-quality result table.
    slim=[{k:r[k] for k in ['role','id','query_position','model','replicate_max_absolute_km','energy_absolute_km','variance_absolute']} for r in all_rows]
    pipe.save_frame(paths,folder/'equivalence.csv',pd.DataFrame(slim))
    pipe.save_json(paths,folder/'preserved_outputs.json',protected)
    print(json.dumps({k:result[k] for k in ['passed','same_workload_speedup','historical_batch_speedup','max_replicate_difference_km','validation_seconds']}),flush=True)


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('run_name required; validation only')
    run(sys.argv[1])
