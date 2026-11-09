"""Independent, restartable complete E2 run; no resource pilot entry point."""
import concurrent.futures as futures
from datetime import datetime, timezone
import gzip
import hashlib
import json
import multiprocessing as mp
import os
for _thread_variable in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[_thread_variable]='1'
from pathlib import Path
import sys
import time
import traceback
import numpy as np
import pandas as pd

from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import save_json, save_frame
from data3001.modelling.baselines import position_error_s4_e8_inputs as inputs
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
from data3001.modelling.baselines.exact_origin_s4_e7 import NeighbourIndex
from . import conditional_gaussian_s5_e1 as single
from . import conditional_gaussian_s5_e1_inputs as previous_inputs
from . import conditional_gaussian_s5_e1_numerics as previous_num
from . import conditional_gaussian_s5_e1_full as previous_io
from . import conditional_gaussian_s5_e1_analysis as previous_analysis
from . import local_gmm_s5_e2 as model
from . import local_gmm_s5_e2_numerics as num
from . import local_gmm_s5_e2_selection as selection

ROOT=Path(__file__).resolve().parents[4]
KEY=inputs.KEY
COUNTS={'C_T0':41761,'C_T1':44612,'C_outer':33971}
STATE={}
ACTIVE_GUARDS=[]


def validate_keys(actual,expected):
    if np.shape(actual)!=np.shape(expected) or not np.array_equal(actual,expected):
        raise ValueError('Incomplete, duplicated or reordered roster')


def context(name, guarded=True):
    if Path(name).name!=name or not name.startswith('local_gmm_s5_e2_'):raise ValueError('Invalid run')
    run={p:ROOT/p/'runs'/name for p in ['results','provenance']}
    cfg=json.loads((run['provenance']/'run.json').read_text())['config']
    approval=json.loads((run['provenance']/'approval.json').read_text())
    for path,digest in approval['protected_files'].items():
        if file_sha256(ROOT/path)!=digest:raise ValueError('Protected input changed: '+path)
    if file_sha256(ROOT/cfg['contract'])!=cfg['contract_sha256']:raise ValueError('Contract changed')
    if cfg['pilot'] or cfg['components']!=[1,2,3] or cfg['energy_count']!=65536 or cfg['region_count']!=65536:
        raise ValueError('Approved direct-full-run definition changed')
    for key,val in model.DEFAULT.items():
        if cfg[key]!=val:raise ValueError('Scientific fitting parameter changed: '+key)
    if file_sha256(ROOT/'configs/local_gmm_s5_e2.json')!=file_sha256(run['provenance']/'frozen_config.json'):
        raise ValueError('Execution config changed')
    frozen=json.loads((run['provenance']/'source_hashes.json').read_text())
    for path,h in frozen.items():
        if file_sha256(ROOT/path)!=h:raise ValueError('Implementation changed during run: '+path)
    guard=previous_inputs.Guard(ROOT,run)
    if guarded:
        sys.addaudithook(guard);ACTIVE_GUARDS.append(guard)
    return project_paths(),run,cfg,approval,guard


def verify_freeze(provenance,role,cases,kind='forecast'):
    filename='forecast_freeze.json' if role=='C_outer' and kind=='forecast' else f'{role}_{kind}_freeze.json'
    p=Path(provenance)/filename
    if not p.exists():raise PermissionError('Complete forecast freeze required')
    r=json.loads(p.read_text())
    if r['cases']!=cases or r.get('outer_targets_read',False):raise ValueError('Invalid freeze receipt')
    for path,h in r['output_sha256'].items():
        if file_sha256(ROOT/path)!=h:raise ValueError('Frozen output changed: '+path)
    return r


def load_role(cfg,role,release=False):
    for name,h in previous_inputs.HASHES.items():
        if file_sha256(ROOT/'results/runs'/cfg['e7_run']/name)!=h:raise ValueError('Coordinate source changed')
    repair=ROOT/'provenance/migrations'/cfg['repair_run']
    if file_sha256(repair/'manifest.json')!=cfg['repair_manifest_sha256'] or file_sha256(repair/'full/error_overlay.parquet')!=cfg['overlay_sha256']:
        raise ValueError('Repair identity changed')
    train,ledger=inputs.load_training(cfg)
    if role=='C_outer':
        fit=train
        query=inputs.read_frame(ROOT/'results/runs'/cfg['e7_run']/'query_coordinates.parquet',
            columns=KEY+['lon','lat','origin_time_UTC']).sort_values(KEY).reset_index(drop=True)
    else:
        roster=ledger[ledger.role_name.eq(role)&ledger.horizon_days.eq(7)]
        fit=roster[roster.role.eq('train')][KEY].merge(train,on=KEY,validate='one_to_one').sort_values(KEY).reset_index(drop=True)
        query=roster[roster.role.eq('validation')][KEY].merge(train[KEY+['lon','lat','origin_time_UTC']],on=KEY,validate='one_to_one').sort_values(KEY).reset_index(drop=True)
    expected={'C_T0':(170978,234,50,'2014-01-01'),'C_T1':(209934,280,58,'2017-01-01'),
        'C_outer':(265393,338,45,'2020-01-01')}
    nf,ni,nq,boundary=expected[role]
    if (len(fit),fit.id.nunique(),len(query),query.id.nunique())!=(nf,ni,COUNTS[role],nq):raise ValueError('Role counts changed')
    if set(fit.id)&set(query.id) or not (fit.required_interval_end_epoch<pd.Timestamp(boundary,tz='UTC').timestamp()).all():
        raise ValueError('ID or temporal leakage')
    if not (fit.target_epoch-pd.to_datetime(fit.origin_time_UTC,utc=True).dt.as_unit('s').astype(np.int64)).eq(604800).all():
        raise ValueError('Horizon changed')
    target=None
    if release and role!='C_outer':
        target=query[KEY].merge(train[KEY+['endpoint_lon','endpoint_lat','outside']],on=KEY,validate='one_to_one')
        validate_keys(target[KEY],query[KEY])
        if target.outside.any():raise ValueError('Unexpected observed E')
    return fit,query,target


def initialise(name,mode,role,k_values):
    paths,run,cfg,approval,guard=context(name)
    release=mode in ('energy','region_scores','score','audit')
    if release:verify_freeze(run['provenance'],role,COUNTS[role],'forecast' if role=='C_outer' else 'parameters')
    fit,query,target=load_role(cfg,role,release)
    if release and role=='C_outer':
        guard.outcomes_allowed=True
        target=inputs.release_outer_targets(run,cfg,approval).sort_values(KEY).reset_index(drop=True)
        validate_keys(target[KEY],query[KEY])
        if target.outside.any():raise ValueError('Unexpected observed exit')
    geo=Geography(paths)
    pool=opt.cache(fit,geo)
    index=NeighbourIndex(fit.lon.to_numpy(),fit.lat.to_numpy(),radius_m=100000,tolerance_m=1e-6)
    STATE.clear();STATE.update(paths=paths,run=run,cfg=cfg,approval=approval,guard=guard,
        role=role,fit=fit,query=query,target=target,geo=geo,pool=pool,index=index,mode=mode,K=k_values)


def batch_paths(run,role,batch):
    base=run['results']/role
    return {mode:base/mode/f'{batch:05d}{suffix}' for mode,suffix in
        [('parameters','.json.gz'),('lineage','.npz'),('regions','.json.gz'),('energy','.parquet'),
         ('region_scores','.parquet'),('score','.parquet'),('audit','.parquet')]}


def fit_record(position):
    s=STATE;row=s['query'].iloc[position]
    origin=[float(row.lon),float(row.lat)]
    key=(s['role'],int(row.id),int(row.origin_source_obs),7)
    ix,distance=s['index'].query(*origin,8000)
    donor=s['fit'].iloc[ix];points=s['pool'].points[ix]
    v=single.to_vectors(origin,points)
    restored=single.to_geographic(origin,v)
    _,_,error=single.GEOD.inv(points[:,0],points[:,1],restored[:,0],restored[:,1])
    if np.max(np.abs(error))>1e-3:raise ValueError('Original endpoint roundtrip mismatch')
    models={}
    for K in s['K']:
        p=model.fit_local(v,donor.id.to_numpy(),K,key,s['cfg']);p['origin']=origin;models[str(K)]=p
    _,counts=np.unique(donor.id.to_numpy(),return_counts=True)
    rec=dict(role=s['role'],query_position=position,id=int(row.id),origin_source_obs=int(row.origin_source_obs),
        horizon_days=7,origin=origin,origin_time_UTC=str(row.origin_time_UTC),key=key,models=models,pairs=len(ix),
        independent_ids=len(counts),largest_id_share=float(counts.max()/counts.sum()),vote=1/len(ix),
        ci_unavailable_mass=float((~s['pool'].usable[ix]).mean()),
        donor_digest=hashlib.sha256(donor[KEY].to_numpy(np.int64).tobytes()).hexdigest())
    return rec,ix


def build_forecast(rec,ix):
    s=STATE;key=tuple(rec['key']);cfg=s['cfg'];regions={};pool=s['pool'].take(ix)
    regions['1']=num.build_region(rec['models']['1'],cfg['region_count'],key,s['geo'])
    for k in s['K']:
        if k==1:continue
        packet=rec['models'][str(k)]
        regions[str(k)]=regions['1'] if packet['fallback'] else num.build_region(packet,cfg['region_count'],key,s['geo'])
    result=dict(query_position=rec['query_position'],regions=regions)
    if s['role']=='C_outer':
        result['regions'].update(num.empirical_regions(pool,cfg['region_count'],key,s['geo']))
        result['calibration']=opt.calibration(pool,('s5_e2_v1',*key,'empirical_energy'))
    return result


def metadata(rec,model_name):
    return {**{k:rec[k] for k in ['role','query_position','id','origin_source_obs','horizon_days',
        'origin_time_UTC','pairs','independent_ids','largest_id_share','ci_unavailable_mass']},'model':model_name}


def energy_rows(rec,truth):
    key=tuple(rec['key']);cfg=STATE['cfg'];values={}
    for k in STATE['K']:
        packet=rec['models'][str(k)]
        es=values[1] if k>1 and packet['fallback'] else num.score_es(packet,truth,cfg['energy_count'],key)
        values[k]=es
    return [dict(metadata(rec,k),**values[k],fallback=rec['models'][str(k)]['fallback']) for k in STATE['K']]


def score_rows(rec,ix,forecast,truth):
    s=STATE;key=tuple(rec['key']);cfg=s['cfg'];regions=forecast['regions']
    g=energy_rows(rec,truth);scores={str(r['model']):r for r in g}
    scores.update(num.empirical_scores(s['pool'].take(ix),regions,truth,cfg['energy_count'],key,forecast['calibration']))
    metrics=previous_num.region_metrics(regions,truth);target=opt.xyz(np.asarray(truth)[None])[0]
    selected=s['K'][-1];names={'ExactPoint':'ExactPoint','EndpointCI':'EndpointCI','LocalGaussian':'1','LocalGMM':str(selected)}
    out=[]
    for name,label in names.items():
        es=scores[label];r=dict(metadata(rec,name),**metrics[label],energy_km=es['energy_km'],variance=es['variance'],
            energy_count=cfg['energy_count'],replicate_means=es.get('replicate_means'),
            fallback=bool(rec['models'][str(selected)]['fallback']) if name=='LocalGMM' else False,
            auxiliary_loss=previous_analysis.auxiliary(es['energy_km'],*regions[label]['means'],target))
        out.append(r)
    return out


def work_batch(task):
    batch,start,end=task;s=STATE;t=time.monotonic();mode=s['mode'];files=batch_paths(s['run'],s['role'],batch)
    if mode=='parameters':
        records=[];lineage=[]
        for position in range(start,end):
            rec,ix=fit_record(position);records.append(rec);lineage.append(ix)
        flat,offset=previous_io.pack_lineages(lineage)
        s['paths'].publish(files['lineage'],lambda f:np.savez_compressed(f,indices=flat,offsets=offset))
        previous_io.write_bundle(s['paths'],files[mode],records)
        outputs=[files[mode],files['lineage']]
    else:
        records=previous_io.read_bundle(files['parameters'])
        with np.load(files['lineage']) as f:flat,offset=f['indices'],f['offsets']
        forecasts=previous_io.read_bundle(files['regions']) if mode in ('region_scores','score','audit') else None
        rows=[]
        for j,rec in enumerate(records):
            ix=previous_io.unpack_lineage(flat,offset,j)
            if mode=='regions':rows.append(build_forecast(rec,ix));continue
            truth=s['target'].iloc[rec['query_position']][['endpoint_lon','endpoint_lat']].to_numpy(float)
            if mode=='energy':rows.extend(energy_rows(rec,truth))
            elif mode=='region_scores':
                metrics=previous_num.region_metrics(forecasts[j]['regions'],truth)
                rows.extend(dict(metadata(rec,int(k)),**v) for k,v in metrics.items())
            elif mode=='score':rows.extend(score_rows(rec,ix,forecasts[j],truth))
            elif mode=='audit':
                from .local_gmm_s5_e2_audit import audit_record
                rows.extend(audit_record(s,rec,ix,forecasts[j],truth))
            else:raise ValueError('Unknown stage')
        if mode=='regions':previous_io.write_bundle(s['paths'],files[mode],rows)
        else:save_frame(s['paths'],files[mode],pd.DataFrame(rows))
        outputs=[files[mode]]
    receipt=dict(role=s['role'],mode=mode,batch=batch,cases=end-start,elapsed_seconds=time.monotonic()-t,
        outer_targets_read=s['guard'].outcomes_read,denied=s['guard'].denied,
        sha256={str(p.relative_to(ROOT)):file_sha256(p) for p in outputs})
    save_json(s['paths'],s['run']['provenance']/'batches'/s['role']/mode/f'{batch:05d}.json',receipt)
    return receipt


def stop_workers(pool):
    processes=list(getattr(pool,'_processes',{}).values())
    for p in processes:
        if p.is_alive():p.terminate()
    for p in processes:p.join(timeout=3)
    for p in processes:
        if p.is_alive():p.kill()
    pool.shutdown(wait=False,cancel_futures=True)


def family_bytes():
    return sum(p.stat().st_size for folder in [ROOT/'results/runs',ROOT/'provenance/runs']
        for run in folder.iterdir() if run.is_dir() and run.name.startswith(('conditional_gaussian_s5_e1_','local_gmm_s5_e2_'))
        for p in run.rglob('*') if p.is_file() and not p.is_symlink())


def check_family_limit(size,gib):
    if size>gib*2**30:raise OSError('S5 family storage cap reached')


def recover_interrupted_budget(provenance):
    marker=provenance/'active_budget.json'
    if not marker.exists():return
    state=json.loads(marker.read_text());receipt=provenance/state['receipt_name']
    if not receipt.exists():
        elapsed=max(state['elapsed_seconds'],min(time.time()-state['started_epoch'],state['reserved_seconds']))
        state.update(elapsed_seconds=float(elapsed),completed=False,
            interrupted=True,unobserved_interval_charged_conservatively=True)
        receipt.write_text(json.dumps(state,indent=2)+'\n')
    marker.unlink()


class Budget(previous_inputs.Budget):
    def __init__(self,run,cfg,phase,label,started):
        recover_interrupted_budget(run['provenance'])
        self.label=label;self.started_epoch=time.time()-(time.monotonic()-started)
        super().__init__(run,cfg,phase,started)
        self.heartbeat()

    def heartbeat(self):
        record=dict(phase=self.phase,started_epoch=self.started_epoch,
            elapsed_seconds=time.monotonic()-self.started,reserved_seconds=self.deadline-self.started,
            receipt_name=self.label+'_resources.json')
        folder=self.run['provenance'];temporary=folder/'active_budget.tmp'
        temporary.write_text(json.dumps(record)+'\n');os.replace(temporary,folder/'active_budget.json')

    def check(self):
        self.heartbeat();result=super().check();check_family_limit(family_bytes(),self.cfg['family_storage_gib'])
        return result

    def finish(self,paths,label,completed,guard):
        result=super().finish(paths,label,completed,guard)
        (self.run['provenance']/'active_budget.json').unlink(missing_ok=True)
        return result


def run_batches(name,mode,role,K,budget):
    s=STATE;paths,run,cfg=s['paths'],s['run'],s['cfg']
    tasks=[];done=0;n=COUNTS[role]
    for batch,first in enumerate(range(0,n,cfg['batch_size'])):
        last=min(first+cfg['batch_size'],n)
        receipt=run['provenance']/'batches'/role/mode/f'{batch:05d}.json'
        if receipt.exists():
            r=json.loads(receipt.read_text())
            record_worker_access(r,s['guard'])
            for p,h in r['sha256'].items():
                if file_sha256(ROOT/p)!=h:raise ValueError('Checkpoint changed')
            done+=last-first
        else:tasks.append((batch,first,last))
    if not tasks:return
    pool=futures.ProcessPoolExecutor(max_workers=cfg['processes'],mp_context=mp.get_context('spawn'),
        initializer=initialise,initargs=(name,mode,role,K))
    pending={};iterator=iter(tasks);last_report=0.
    try:
        for _ in range(cfg['processes']):
            task=next(iterator,None)
            if task is not None:pending[pool.submit(work_batch,task)]=task
        while pending:
            ready,_=futures.wait(pending,timeout=10,return_when=futures.FIRST_COMPLETED)
            budget.check()
            for job in ready:
                receipt=job.result();done+=receipt['cases'];pending.pop(job)
                record_worker_access(receipt,s['guard'])
                task=next(iterator,None)
                if task is not None:pending[pool.submit(work_batch,task)]=task
            if time.monotonic()-last_report>=30 or not pending:
                stats=budget.stats();print(json.dumps(dict(role=role,mode=mode,done=done,total=n,
                    elapsed_seconds=round(stats['elapsed_seconds'],1),rss_gib=round(stats['peak_process_tree_rss_bytes']/2**30,3))),flush=True)
                last_report=time.monotonic()
    except BaseException:stop_workers(pool);raise
    else:pool.shutdown(wait=True,cancel_futures=True)


def record_worker_access(receipt,guard):
    if receipt.get('outer_targets_read',False):guard.outcomes_read=True


def freeze_role(paths,run,role,kinds,kind):
    out={};positions=[]
    for p in sorted((run['results']/role/'parameters').glob('*.json.gz')):
        positions += [r['query_position'] for r in previous_io.read_bundle(p)]
    validate_keys(positions,np.arange(COUNTS[role]))
    for name in kinds:
        for p in sorted((run['results']/role/name).iterdir()):out[str(p.relative_to(ROOT))]=file_sha256(p)
    receipt=dict(role=role,cases=COUNTS[role],outer_targets_read=False,output_sha256=out)
    name='forecast_freeze.json' if role=='C_outer' and kind=='forecast' else f'{role}_{kind}_freeze.json'
    if not (run['provenance']/name).exists():save_json(paths,run['provenance']/name,receipt)
    else:verify_freeze(run['provenance'],role,COUNTS[role],kind)


def collect(run,role,mode):
    frames=[pd.read_parquet(p) for p in sorted((run['results']/role/mode).glob('*.parquet'))]
    if not frames:raise ValueError('No complete scores')
    table=pd.concat(frames,ignore_index=True)
    for _,sub in table.groupby('model'):
        validate_keys(sub.query_position.to_numpy(),np.arange(COUNTS[role]))
    return table


def check_regions(table):
    checks={}
    for (role,model_name),sub in table.groupby(['role','model']):
        gate=previous_num.region_gate(sub,previous_num.id_weights(sub.id))
        checks[f'{role}:{model_name}']=gate
        if not gate['passed']:raise ArithmeticError('Region precision failed: '+str(checks))
    return checks


def run_phase(name,phase):
    started=time.monotonic();paths,run,cfg,approval,guard=context(name)
    STATE.update(paths=paths,run=run,cfg=cfg,guard=guard)
    label=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')+'_'+phase
    budget=Budget(run,cfg,phase,label,started);completed=False
    try:
        if phase=='inner':
            for role in ['C_T0','C_T1']:
                run_batches(name,'parameters',role,[1,2,3],budget)
                freeze_role(paths,run,role,['parameters','lineage'],'parameters')
            for role in ['C_T0','C_T1']:run_batches(name,'energy',role,[1,2,3],budget)
            metrics=pd.concat([collect(run,r,'energy') for r in ['C_T0','C_T1']],ignore_index=True)
            choice=selection.select_k(metrics,spec=cfg);k=choice['provisional_k']
            if k>1:
                for role in ['C_T0','C_T1']:
                    run_batches(name,'regions',role,[1,k],budget)
                    run_batches(name,'region_scores',role,[1,k],budget)
                regions=pd.concat([collect(run,r,'region_scores') for r in ['C_T0','C_T1']],ignore_index=True)
                gates=check_regions(regions);choice=selection.apply_quality(choice,regions)
                choice['region_precision']=gates
            else:choice=selection.apply_quality(choice,None)
            from .local_gmm_s5_e2_audit import audit_inner
            audit_inner(run,metrics,choice,cfg,budget)
            if not (run['provenance']/'selection.json').exists():save_json(paths,run['provenance']/'selection.json',choice)
            print('SELECTED_K',choice['selected_k'],flush=True)
        elif phase=='outer':
            choice=json.loads((run['provenance']/'selection.json').read_text());K=sorted(set([1,choice['selected_k']]))
            run_batches(name,'parameters','C_outer',K,budget)
            freeze_role(paths,run,'C_outer',['parameters','lineage'],'parameters')
            run_batches(name,'regions','C_outer',K,budget)
            freeze_role(paths,run,'C_outer',['parameters','lineage','regions'],'forecast')
            run_batches(name,'score','C_outer',K,budget)
            metrics=collect(run,'C_outer','score');check_regions(metrics)
            if not (run['results']/'metrics.parquet').exists():save_frame(paths,run['results']/'metrics.parquet',metrics)
        elif phase=='audit':
            choice=json.loads((run['provenance']/'selection.json').read_text());K=sorted(set([1,choice['selected_k']]))
            run_batches(name,'audit','C_outer',K,budget)
            from .local_gmm_s5_e2_audit import verify_full
            verify_full(paths,run,cfg,budget)
        elif phase=='report':
            from .local_gmm_s5_e2_report import report
            report(paths,run,cfg,budget)
        else:raise ValueError('No pilot. Only inner/outer/audit/report.')
        budget.check();completed=True
    except BaseException as e:
        save_json(paths,run['provenance']/(label+'_failure.json'),dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc(),phase=phase))
        raise
    finally:
        receipt=budget.finish(paths,label,completed,guard)
        print('PHASE_END',phase,completed,round(receipt['elapsed_seconds'],2),flush=True)


if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('run_name inner|outer|audit|report|all')
    for phase in (['inner','outer','audit','report'] if sys.argv[2]=='all' else [sys.argv[2]]):
        run_phase(sys.argv[1],phase)
