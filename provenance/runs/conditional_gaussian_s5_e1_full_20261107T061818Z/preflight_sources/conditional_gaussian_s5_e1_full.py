"""Immutable full-cohort S5 E1 execution, gated before outer outcomes."""
import time
STARTED=time.monotonic()
import concurrent.futures as futures
import gzip
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import sys
import traceback

import numpy as np
import pandas as pd

from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_frame,save_json
from data3001.modelling.baselines import position_error_s4_e8 as old
from data3001.modelling.baselines import position_error_s4_e8_inputs as old_inputs
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
from data3001.modelling.baselines.exact_origin_s4_e7 import NeighbourIndex
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1 as gaussian
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_numerics as num
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_inputs as inp
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_reference as ref
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_analysis as analysis

STATE={}


def pack_lineages(values):
    offsets=np.r_[0,np.cumsum([len(v) for v in values])].astype(np.int64)
    return np.concatenate(values).astype(np.uint32),offsets


def unpack_lineage(flat,offsets,index):return flat[offsets[index]:offsets[index+1]].astype(np.int64)


def validate_keys(actual,expected):
    a,b=np.asarray(actual),np.asarray(expected)
    if a.shape!=b.shape or not np.array_equal(a,b):raise ValueError('Incomplete, duplicate or reordered frozen roster')


def json_ready(value):
    if isinstance(value,dict):return {k:json_ready(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [json_ready(v) for v in value]
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    return value


def write_bundle(paths,path,value):
    payload=json.dumps(json_ready(value),separators=(',',':'),allow_nan=False).encode()
    paths.publish(path,lambda f:f.write(gzip.compress(payload,compresslevel=3,mtime=0)))


def read_bundle(path):
    with gzip.open(path,'rt') as stream:return json.load(stream)


def auxiliary_means(pool,packet,count,key):
    result={'ExactPoint':[pool.xyz.mean(axis=0).tolist()]*2,'EndpointCI':[],'LocalGaussian':[]}
    for rep in (0,1):
        g=gaussian.generator((*key,'auxiliary_ci_mean',rep));ix=g.integers(len(pool.points),size=count)
        z=g.standard_normal((count,2));a=opt.xyz(old.perturbed(pool.points[ix],pool.sd[ix],z))
        b=opt.xyz(old.perturbed(pool.points[ix],pool.sd[ix],-z))
        mean=pool.xyz.mean(axis=0)+(.5*(a+b)-pool.xyz[ix]).mean(axis=0)
        result['EndpointCI'].append(mean.tolist())
        cloud=gaussian.draw(packet,gaussian.sobol_normals(count,2,(*key,'auxiliary_gaussian_mean',rep)))
        result['LocalGaussian'].append(opt.xyz(cloud).mean(axis=0).tolist())
    return result


def parameter_record(context,row,position):
    fit=context['fit'];ix,dist=context['index'].query(float(row.lon),float(row.lat),8000)
    donor=fit.iloc[ix];keys=donor[inp.KEY].to_numpy(dtype=np.int64)
    key=(str(context['role']),int(row.id),int(row.origin_source_obs),7)
    try:packet=gaussian.fit(np.array([row.lon,row.lat]),context['cache'].points[ix])
    except gaussian.SupportError as error:
        raise gaussian.SupportError(str(error),dict(error.diagnostics,query_position=position,key=key,
            donor_indices=ix.tolist(),donor_distances_m=dist.tolist(),donor_keys=keys.tolist())) from error
    _,counts=np.unique(donor.id.to_numpy(),return_counts=True)
    record=dict(query_position=int(position),id=int(row.id),origin_source_obs=int(row.origin_source_obs),horizon_days=7,
        origin=[float(row.lon),float(row.lat)],origin_time_UTC=str(row.origin_time_UTC),key=key,gaussian=packet,
        donor_digest=hashlib.sha256(keys.tobytes()).hexdigest(),pairs=len(ix),vote=1/len(ix),
        independent_ids=len(counts),largest_id_share=float(counts.max()/counts.sum()),
        ci_unavailable_mass=float((~context['cache'].usable[ix]).mean()))
    return record,ix,dist


def construct_regions(context,record,ix,cfg):
    pool=context['cache'].take(ix);key=tuple(record['key'])
    packets=num.build_regions(pool,record['gaussian'],cfg['region_count'],key,STATE['geo'])
    return dict(query_position=record['query_position'],regions=packets,
        means=auxiliary_means(pool,record['gaussian'],cfg['energy_count'],key),
        calibration=opt.calibration(pool,('s5_e1_v1',*key,'empirical_energy',0)))


def score_record(context,record,ix,forecast,truth,cfg):
    pool=context['cache'].take(ix);key=tuple(record['key'])
    energy,_=num.scores(pool,record['gaussian'],forecast['regions'],truth,cfg['energy_count'],key,forecast['calibration'])
    region=num.region_metrics(forecast['regions'],truth);target=opt.xyz(np.asarray(truth)[None,:])[0]
    rows=[]
    for model in num.MODELS:
        es=energy[model];means=forecast['means'][model]
        row={k:record[k] for k in ['query_position','id','origin_source_obs','horizon_days','origin_time_UTC','pairs','independent_ids','largest_id_share','ci_unavailable_mass']}
        row.update(model=model,energy_km=es['energy_km'],variance=es['variance'],energy_count=cfg['energy_count'],
            covariance_condition=record['gaussian']['condition_number'],
            auxiliary_loss=analysis.auxiliary(es['energy_km'],means[0],means[1],target),**region[model])
        rows.append(row)
    return rows


def initialise(name,mode):
    paths,run,cfg,approval,guard=inp.context(name)
    geo=Geography(paths)
    if mode=='pilot':
        contexts,_,_=inp.load(cfg)
    else:
        fit,_=old_inputs.load_training(cfg)
        query=old_inputs.read_frame(inp.ROOT/'results/runs'/cfg['e7_run']/'query_coordinates.parquet',
            columns=inp.KEY+['origin_time_UTC','lon','lat']).sort_values(inp.KEY).reset_index(drop=True)
        if len(query)!=33971 or query.id.nunique()!=45 or set(query.id)&set(fit.id):raise ValueError('Outer roster mismatch')
        contexts={'C_outer':dict(fit=fit,query=query,target=None)}
    for role,context in contexts.items():
        context.update(role=role,cache=opt.cache(context['fit'],geo))
        context['index']=NeighbourIndex(context['fit'].lon.to_numpy(),context['fit'].lat.to_numpy(),radius_m=100000,tolerance_m=1e-6)
    STATE.update(paths=paths,run=run,cfg=cfg,approval=approval,guard=guard,geo=geo,contexts=contexts,mode=mode)
    if mode in ('score','audit'):
        verify_freeze(run,approval)
        guard.outcomes_allowed=True
        target=old_inputs.release_outer_targets(run,cfg,approval).sort_values(inp.KEY).reset_index(drop=True)
        validate_keys(target[inp.KEY],contexts['C_outer']['query'][inp.KEY])
        if target.outside.any():raise ValueError('Unexpected observed exit in outer target roster')
        STATE['contexts']['C_outer']['target']=target


def verify_freeze(run,approval):
    file=run['provenance']/'forecast_freeze.json'
    if not file.exists():raise PermissionError('No complete forecast freeze')
    receipt=json.loads(file.read_text())
    if receipt['cases']!=33971 or receipt['outer_targets_read']:raise ValueError('Invalid freeze receipt')
    for relative,digest in receipt['output_sha256'].items():
        if file_sha256(inp.ROOT/relative)!=digest:raise ValueError('Frozen forecast mismatch: '+relative)


def files_for_batch(run,batch):
    return {name:run['results']/name/f'{batch:04d}{suffix}' for name,suffix in
        [('parameters','.json.gz'),('lineage','.npz'),('forecasts','.json.gz'),('scores','.parquet'),('audit','.parquet')]}


def run_batch(task):
    mode,batch,first,last=task;start=time.monotonic();s=STATE;paths,run,cfg=s['paths'],s['run'],s['cfg']
    context=s['contexts']['C_outer'];files=files_for_batch(run,batch)
    if mode=='parameters':
        records,indices,distances=[],[],[]
        for position in range(first,last):
            record,ix,dist=parameter_record(context,context['query'].iloc[position],position)
            records.append(record);indices.append(ix);distances.append(dist)
        flat,offset=pack_lineages(indices)
        paths.publish(files['lineage'],lambda f:np.savez_compressed(f,indices=flat,offsets=offset,distances_m=np.concatenate(distances)))
        write_bundle(paths,files['parameters'],records)
    else:
        records=read_bundle(files['parameters'])
        with np.load(files['lineage']) as f:flat,offset=f['indices'],f['offsets']
        forecasts=[] if mode=='regions' else read_bundle(files['forecasts'])
        rows=[]
        for j,record in enumerate(records):
            ix=unpack_lineage(flat,offset,j)
            if mode=='regions':forecasts.append(construct_regions(context,record,ix,cfg))
            else:
                truth=context['target'].iloc[record['query_position']][['endpoint_lon','endpoint_lat']].to_numpy(float)
                if mode=='score':rows.extend(score_record(context,record,ix,forecasts[j],truth,cfg))
                elif mode=='audit':rows.extend(audit_record(context,record,ix,forecasts[j],truth,cfg))
                else:raise ValueError('Unknown batch stage')
        if mode=='regions':write_bundle(paths,files['forecasts'],forecasts)
        else:save_frame(paths,files['scores' if mode=='score' else 'audit'],pd.DataFrame(rows))
    return dict(batch=batch,cases=last-first,elapsed_seconds=time.monotonic()-start,
                outer_targets_read=s['guard'].outcomes_read,denied=s['guard'].denied)


def audit_record(context,record,ix,forecast,truth,cfg):
    pool=context['cache'].take(ix);key=tuple(record['key']);packet=ref.fit(record['origin'],pool.points)
    np.testing.assert_allclose(packet['mean'],record['gaussian']['mean'],rtol=1e-10,atol=1e-8)
    np.testing.assert_allclose(packet['covariance'],record['gaussian']['covariance'],rtol=1e-10,atol=1e-7)
    digest=hashlib.sha256(context['fit'].iloc[ix][inp.KEY].to_numpy(dtype=np.int64).tobytes()).hexdigest()
    if digest!=record['donor_digest']:raise ValueError('Independent donor-key identity mismatch')
    regions=ref.regions(pool,packet,cfg['region_count'],key)
    energy=ref.energy(pool,packet,truth,cfg['energy_count'],key)
    target=np.array(ref.MAP.transform(*truth))[None,:]/1000
    selected=set(np.floor(np.arange(128)*(33971-1)/127).astype(int))
    iid=None
    if record['query_position'] in selected:
        # Exhaustive independent donor check on every prespecified audit key.
        fit=context['fit'];_,_,d=ref.GEOD.inv(np.full(len(fit),record['origin'][0]),np.full(len(fit),record['origin'][1]),fit.lon.to_numpy(),fit.lat.to_numpy())
        eligible=np.flatnonzero(d<=100000+1e-6);order=np.lexsort((eligible,d[eligible]));chosen=eligible[order]
        if len(chosen)>8000:chosen=chosen[d[chosen]<=d[chosen[7999]]+1e-6]
        np.testing.assert_array_equal(ix,chosen)
        iid=ref.iid_energy(packet,truth,65536,key)
    rows=[]
    for model in num.MODELS:
        r=regions[model];base=forecast['regions'][model]['region']
        row=dict(query_position=record['query_position'],id=record['id'],model=model,
            energy_km=energy[model]['energy_km'],variance=energy[model]['variance'],
            h90=float(ref.inside(target,r)[0]),area90_km2=r['area_km2'],
            original_h90=float(ref.inside(target,base)[0]),original_area90_km2=base['area_km2'],
            hit_disagreement=float(ref.inside(target,r)[0]!=ref.inside(target,base)[0]),
            parameter_max_error=float(np.max(np.abs(np.asarray(packet['covariance'])-record['gaussian']['covariance']))),
            exhaustive_donor_check=record['query_position'] in selected,
            iid_energy_km=iid['energy_km'] if model=='LocalGaussian' and iid else None,
            iid_variance=iid['variance'] if model=='LocalGaussian' and iid else None)
        rows.append(row)
    return rows


def pilot_worker(task):
    role,position=task;context=STATE['contexts'][role]
    record,ix,_=parameter_record(context,context['query'].iloc[position],position)
    forecast=construct_regions(context,record,ix,STATE['cfg'])
    truth=context['target'].iloc[position][['endpoint_lon','endpoint_lat']].to_numpy(float)
    return json_ready(dict(record=record,forecast=forecast,scores=score_record(context,record,ix,forecast,truth,STATE['cfg'])))


def preflight(paths,run,cfg,approval,guard,budget):
    initialise(run['results'].name,'pilot');cold=time.monotonic()-STARTED
    oldroot=inp.ROOT/'results/runs'/cfg['parent_pilot_run']
    roster=pd.read_parquet(oldroot/'pilot_roster.parquet');previous=pd.read_parquet(oldroot/'pilot_energy.parquet')
    oldgate=json.loads((oldroot/'pilot_gates.json').read_text())
    if oldgate['selected_energy_count']!=cfg['energy_count'] or oldgate['selected_region_count']!=cfg['region_count']:raise ValueError('Numerical level changed')
    times=[];parity={};retained=[]
    for row in roster.itertuples(index=False):
        budget.check();context=STATE['contexts'][row.role];t=time.monotonic()
        record,ix,dist=parameter_record(context,context['query'].iloc[row.query_position],row.query_position);tp=time.monotonic()-t
        t=time.monotonic();forecast=construct_regions(context,record,ix,cfg);tr=time.monotonic()-t
        truth=context['target'].iloc[row.query_position][['endpoint_lon','endpoint_lat']].to_numpy(float)
        t=time.monotonic();scores=score_record(context,record,ix,forecast,truth,cfg);ts=time.monotonic()-t
        expected=previous[previous.pilot_position.eq(row.pilot_position)&previous.level.eq(cfg['energy_count'])].set_index('model')
        for item in scores:np.testing.assert_allclose(item['energy_km'],expected.loc[item['model'],'energy_km'],rtol=0,atol=1e-10)
        # Pilot audit avoids the outer-only fixed-128 logic, while exercising all full replica calculations.
        t=time.monotonic();packet=ref.fit(record['origin'],context['cache'].points[ix]);pool=context['cache'].take(ix)
        ref.regions(pool,packet,cfg['region_count'],tuple(record['key']));ref.energy(pool,packet,truth,cfg['energy_count'],tuple(record['key']))
        ta=time.monotonic()-t
        t=time.monotonic();dest=run['results']/'preflight'/f'{row.pilot_position:03d}.json.gz'
        write_bundle(paths,dest,dict(record=record,forecast=forecast,scores=scores))
        paths.publish(dest.with_suffix('.npz'),lambda f:np.savez_compressed(f,indices=ix.astype(np.uint32),distances_m=dist))
        tio=time.monotonic()-t;retained.append(dest.stat().st_size+dest.with_suffix('.npz').stat().st_size)
        times.append(dict(position=row.pilot_position,parameters=tp,regions=tr,score=ts,audit=ta,io=tio))
        if row.pilot_position in (0,64):parity[(row.role,row.query_position)]=json_ready(dict(record=record,forecast=forecast,scores=scores))
        if (row.pilot_position+1)%16==0:print('PREFLIGHT',row.pilot_position+1,'/128',round(budget.stats()['elapsed_seconds'],1),'seconds',flush=True)
    # Spawned workers have private GEOS objects and independent immutable caches.
    pool=futures.ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('spawn'),initializer=initialise,initargs=(run['results'].name,'pilot'))
    try:
        jobs={pool.submit(pilot_worker,task):task for task in parity}
        for job in futures.as_completed(jobs):
            answer=job.result()
            if answer!=parity[jobs[job]]:raise ValueError('Private-process parity failed')
            budget.check()
    finally:pool.shutdown(wait=True,cancel_futures=True)
    table=pd.DataFrame(times);save_frame(paths,run['results']/'preflight_timings.csv',table)
    components=table[['parameters','regions','score','io']].to_numpy()
    bound=max(np.quantile(components.sum(axis=1),.95),np.quantile(components,.95,axis=0).sum())
    formal=(33971*bound+cold)*1.1
    audit=(33971*(table.audit.quantile(.95)+table.io.quantile(.95))+cold+128*.2)*1.1
    storage=33971*float(np.quantile(retained,.95))*2+100*2**20
    stats=budget.check()
    passed=bool(2*formal<=cfg['seconds']['formal'] and audit<=cfg['seconds']['audit'] and storage<=cfg['storage_preflight_gib']*2**30 and stats['peak_process_tree_rss_bytes']<=4*2**30)
    receipt=dict(passed=passed,formal_seconds=formal,formal_with_reserve_seconds=2*formal,audit_seconds=audit,
        storage_bytes=storage,process_tree_rss_bytes=stats['peak_process_tree_rss_bytes'],private_process_parity=True,
        numerical_pilot=cfg['parent_pilot_run'],energy_count=cfg['energy_count'],region_count=cfg['region_count'],
        all128_control_scores_match=True,outer_targets_read=False,final_test_access=False)
    save_json(paths,run['provenance']/'full_preflight.json',receipt)
    if not passed:raise RuntimeError('Revised resource preflight failed; no formal execution authorised')
    print(json.dumps(receipt),flush=True)


def execute_parallel(name,mode,run,cfg,budget):
    executor=futures.ProcessPoolExecutor(max_workers=cfg['processes'],mp_context=mp.get_context('spawn'),initializer=initialise,initargs=(name,mode))
    tasks=[(mode,b,start,min(start+cfg['batch_size'],33971)) for b,start in enumerate(range(0,33971,cfg['batch_size']))]
    iterator=iter(tasks);pending={};done=0;last_log=0;receipts=[]
    try:
        for _ in range(cfg['processes']*2):
            task=next(iterator,None)
            if task:pending[executor.submit(run_batch,task)]=task
        while pending:
            completed,_=futures.wait(pending,timeout=1,return_when=futures.FIRST_COMPLETED)
            budget.check()
            for job in completed:
                item=job.result();receipts.append(item);done+=item['cases'];del pending[job]
                task=next(iterator,None)
                if task:pending[executor.submit(run_batch,task)]=task
            if time.monotonic()-last_log>=30 or not pending:
                print(mode.upper(),done,'/33971',round(budget.stats()['elapsed_seconds'],1),'seconds',flush=True);last_log=time.monotonic()
        executor.shutdown(wait=True)
    except BaseException:
        for process in list(getattr(executor,'_processes',{}).values()):process.terminate()
        executor.shutdown(wait=True,cancel_futures=True)
        raise
    return receipts


def freeze(paths,run,cfg):
    query=old_inputs.read_frame(inp.ROOT/'results/runs'/cfg['e7_run']/'query_coordinates.parquet',columns=inp.KEY).sort_values(inp.KEY).reset_index(drop=True)
    files=[];keys=[]
    for batch in range((33971+cfg['batch_size']-1)//cfg['batch_size']):
        names=files_for_batch(run,batch);records=read_bundle(names['parameters']);forecasts=read_bundle(names['forecasts'])
        if [r['query_position'] for r in records]!=[r['query_position'] for r in forecasts]:raise ValueError('Forecast batch not aligned')
        keys.extend([[r[k] for k in inp.KEY] for r in records]);files.extend([names['parameters'],names['lineage'],names['forecasts']])
    validate_keys(keys,query[inp.KEY])
    hashes={str(p.relative_to(inp.ROOT)):file_sha256(p) for p in files}
    save_json(paths,run['provenance']/'forecast_freeze.json',dict(cases=33971,models=list(num.MODELS),outer_targets_read=False,
        energy_count=cfg['energy_count'],region_count=cfg['region_count'],output_sha256=hashes,
        mean_method='Two independent full-law numerical means; unbiased cross product for auxiliary loss'))


def main(name,mode):
    paths,run,cfg,approval,guard=inp.context(name)
    phase='pilot' if mode=='preflight' else ('audit' if mode=='audit' else 'formal')
    budget=inp.Budget(run,cfg,phase,STARTED);completed=False
    try:
        inp.freeze_sources(paths,run,mode)
        if mode=='preflight':preflight(paths,run,cfg,approval,guard,budget)
        else:
            gate=json.loads((run['provenance']/'full_preflight.json').read_text())
            if not gate['passed']:raise PermissionError('Full preflight not passed')
            receipts=execute_parallel(name,mode,run,cfg,budget)
            save_json(paths,run['provenance']/(mode+'_batches.json'),receipts)
            if mode=='regions':freeze(paths,run,cfg)
            if mode in ('score','audit'):guard.outcomes_read=any(r['outer_targets_read'] for r in receipts)
        inp.verify(approval);budget.check();completed=True
    except BaseException as error:
        save_json(paths,run['provenance']/(mode+'_stopped.json'),dict(error=repr(error),traceback=traceback.format_exc(),
            diagnostics=getattr(error,'diagnostics',None),outer_targets_read=guard.outcomes_read,final_test_access=False))
        raise
    finally:budget.finish(paths,mode,completed,guard)


if __name__=='__main__':main(sys.argv[1],sys.argv[2])
