"""Bounded full-training-pool engineering trial. Never selects K."""
import concurrent.futures as cf
import json
import multiprocessing as mp
import time
from pathlib import Path
import numpy as np
import pandas as pd
import torch

from data3001.paths import file_sha256
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
from . import conditional_mdn_s5_e3_inputs as inp
from . import conditional_mdn_s5_e3_numerics as num
from . import conditional_mdn_s5_e3_training as training
from .conditional_mdn_s5_e3_pipeline import pilot_indices,id_weights,packet_at,aggregate_difference,preflight_pass
from .conditional_mdn_s5_e3_runtime import atomic_json,remaining

WORKER={}


def fold_id_weights(frame):
    df=frame.groupby(['role','id']).id.transform('size').to_numpy()
    nf=frame.groupby('id').role.transform('nunique').to_numpy()
    return 1/(frame.id.nunique()*nf*df)


def train_pilot(name):
    paths,run,cfg,approval,guard=inp.context(name)
    torch.set_num_threads(cfg['training_threads'])
    roles=inp.cohorts(cfg);inp.freeze_access(run,roles)
    role=roles['C_T0'];fit=role['fit']
    x=fit[['lon','lat']].to_numpy();v=num.to_vectors(x,inp.endpoints(cfg,run,'C_T0',fit,'fit'))
    if not np.isfinite(v).all():raise FloatingPointError('Invalid own-pair displacement')
    sources=inp.freeze_sources(run,'pilot_train')
    identity={'contract_sha256':cfg['contract_sha256'],'sources':sources,'role':'C_T0',
              'kind':'engineering_pilot_only_full_fit_pool','pairs':len(fit),'ids':fit.id.nunique()}
    out={}
    for k in (1,32):
        start=time.monotonic()
        result=training.train_fixed_epochs(x,v,fit.id.to_numpy(),k,'C_T0',20261121,
            run['results']/f'pilot_training/K{k}',10,purpose='pilot',identity=identity)
        if result.status!='complete':raise RuntimeError('Pilot training did not complete')
        out[str(k)]={'elapsed_seconds':time.monotonic()-start,'epoch_seconds':[h['seconds'] for h in result.history],
                     'training_nll':[h['training_nll'] for h in result.history],
                     'checkpoint':str(result.checkpoint_path.relative_to(inp.ROOT)),
                     'checkpoint_sha256':file_sha256(result.checkpoint_path),
                     'pairs':len(fit),'ids':int(fit.id.nunique()),'epochs':10}
        atomic_json(run['provenance']/'pilot_training_receipt.json',out)
        print(json.dumps({'pilot_training_K':k,'seconds':out[str(k)]['elapsed_seconds'],'epochs':10}),flush=True)
    atomic_json(run['provenance']/'pilot_training_access.json',{'outer_targets_read':guard.outer_read,'denied':guard.denied,'final_test_access':False})


def make_tasks(name):
    _,run,cfg,_,guard=inp.context(name)
    roles=inp.cohorts(cfg);inp.freeze_access(run,roles);models={}
    receipt=json.loads((run['provenance']/'pilot_training_receipt.json').read_text())
    for k in (1,32):
        path=inp.ROOT/receipt[str(k)]['checkpoint']
        if file_sha256(path)!=receipt[str(k)]['checkpoint_sha256']:raise ValueError('Pilot checkpoint changed')
        models[k]=training.load_model(path)
    tasks=[];roster=[];full=[]
    for role in ('C_T0','C_T1'):
        query=roles[role]['query'];indices=pilot_indices(len(query));selected=query.iloc[indices]
        origins=selected[['lon','lat']].to_numpy()
        params={k:model.parameters(origins) for k,model in models.items()}
        truths=inp.endpoints(cfg,run,role,selected,'pilot')
        full.extend({'role':role,'id':int(x)} for x in query.id)
        for j,(position,(_,row)) in enumerate(zip(indices,selected.iterrows())):
            key=tuple(int(row[c]) for c in inp.KEY);packets={}
            for k in (1,32):packets[k]=packet_at(params[k],j,origins[j],models[k].standardizer.y_std)
            # Intermediate K probes are explicitly synthetic stress mixtures,
            # not trained MDN2/4/8/16 predictions or a model-selection shortcut.
            base=packets[1];centre=np.asarray(base['means'])[0];root=np.asarray(base['cholesky'])[0]
            for k in (2,4,8,16):
                angle=2*np.pi*np.arange(k)/k
                offsets=.75*np.column_stack([np.cos(angle),np.sin(angle)])@root.T
                weights=np.arange(1,k+1,dtype=float);weights/=weights.sum()
                packets[k]=dict(origin=base['origin'],weights=weights.tolist(),means=(centre+offsets).tolist(),
                                cholesky=np.repeat(root[None],k,axis=0).tolist(),engineering_fixture=True)
            metadata={'role':role,'position':int(position),'key':key,'id':key[0]}
            roster.append(metadata)
            tasks.append({**metadata,'packets':packets,'target':truths[j].tolist(),
                          'component_check':j in (0,21,42,63)})
    atomic_json(run['provenance']/'pilot_query_whitelist.json',roster)
    atomic_json(run['provenance']/'pilot_stream_manifest.json',{
        'CRN':'K field empty for ES/region/IID; candidates share nodes; role/query/purpose/replicate remain distinct',
        'ES':'six-dimensional Sobol;8scrambles;total N split equally',
        'component_reference':'8192 total nodes per component/pair across8scrambles,1024 each; agrees total N convention',
        'other_K':'synthetic circular stress mixtures from K1 centre/root; uneven positive weights; not learned candidate models',
        'primary_roles':['C_T0','C_T1'],'base_seed':20261121,'outer_outcomes_read':False})
    atomic_json(run['provenance']/'pilot_frozen_tasks.json',tasks)
    full_frame=pd.DataFrame(full);fw=fold_id_weights(full_frame)
    outer=roles['C_outer']['query'];ow=id_weights(outer.id.to_numpy())
    return run,cfg,tasks,{'inner_sum_squared_weights':float(fw@fw),'outer_sum_squared_weights':float(ow@ow)}


def init_worker(name):
    paths,run,cfg,_,guard=inp.context(name)
    torch.set_num_threads(1)
    WORKER.update(run=run,cfg=cfg,guard=guard,geography=Geography(paths))


def numeric_case(task):
    n=task['energy_count'];m=task['region_count'];output=[]
    for k,p in sorted(task['packets'].items()):
        k=int(k);t=time.monotonic()
        energy=num.score_es(p,task['target'],n,tuple(task['key']),task['role'])
        es_seconds=time.monotonic()-t;t=time.monotonic()
        regions=num.build_region(p,m,tuple(task['key']),task['role'],WORKER['geography'])
        region_seconds=time.monotonic()-t;t=time.monotonic()
        replica=num.score_es(p,task['target'],n,tuple(task['key']),task['role'],audit=True)
        audit_seconds=time.monotonic()-t
        metrics=num.region_metrics(regions,task['target'])
        reference=None;iid=None;t=time.monotonic()
        if task['component_check']:
            reference=num.reference_component_es(p,task['target'],8192,tuple(task['key']),task['role'])
            iid=num.iid_energy(p,task['target'],tuple(task['key']),task['role'])
        reference_seconds=time.monotonic()-t
        out={k2:task[k2] for k2 in ('role','position','key','id')}
        out.update(K=k,energy_count=n,region_count=m,energy=energy,replica=replica,reference=reference,iid=iid,regions=regions,
                   metrics=metrics,timing={'energy':es_seconds,'region':region_seconds,'audit':audit_seconds,'reference':reference_seconds})
        output.append(out)
    return output


def strip_timing(rows):
    return [{k:v for k,v in row.items() if k!='timing'} for row in rows]


def measure_level(name,run,tasks,energy_count,region_count):
    folder=run['results']/f'pilot_numerics/N{energy_count}_M{region_count}';folder.mkdir(parents=True,exist_ok=True)
    jobs=[{**t,'energy_count':energy_count,'region_count':region_count} for t in tasks]
    # The first fixed query verifies identical results with1and2spawn workers.
    if not (run['provenance']/'worker_parity.json').exists():
        with cf.ProcessPoolExecutor(max_workers=1,mp_context=mp.get_context('spawn'),initializer=init_worker,initargs=(name,)) as pool:
            single=pool.submit(numeric_case,jobs[0]).result()
        with cf.ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('spawn'),initializer=init_worker,initargs=(name,)) as pool:
            first,second=[x.result() for x in [pool.submit(numeric_case,jobs[0]),pool.submit(numeric_case,jobs[0])]]
        if strip_timing(single)!=strip_timing(first) or strip_timing(first)!=strip_timing(second):raise ArithmeticError('Single/two-worker parity failed')
        atomic_json(run['provenance']/'worker_parity.json',{'passed':True,'query_key':jobs[0]['key'],'energy_count':energy_count,'region_count':region_count,'models':6})
        atomic_json(folder/(jobs[0]['role']+'_'+str(jobs[0]['position'])+'.json'),first)
    pending=[j for j in jobs if not (folder/(j['role']+'_'+str(j['position'])+'.json')).exists()]
    timing_path=folder/'timing.json'
    if not pending:
        if not timing_path.exists():raise RuntimeError('Cached level has no measured timing; cannot invent a resource forecast')
        saved_timing=json.loads(timing_path.read_text());all_rows=[]
        for j in jobs:all_rows.extend(json.loads((folder/(j['role']+'_'+str(j['position'])+'.json')).read_text()))
        return all_rows,saved_timing
    t=time.monotonic();cold=None
    with cf.ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('spawn'),initializer=init_worker,initargs=(name,)) as pool:
        futures={pool.submit(numeric_case,j):j for j in pending}
        for i,f in enumerate(cf.as_completed(futures),1):
            rows=f.result();j=futures[f]
            atomic_json(folder/(j['role']+'_'+str(j['position'])+'.json'),rows)
            if i==1:cold=time.monotonic()-t
            atomic_json(timing_path,{'level_wall_seconds':time.monotonic()-t,'cold_to_first_result_seconds':cold})
            if i%8==0:print(json.dumps({'pilot_N':energy_count,'pilot_M':region_count,'queries_complete':i+(len(jobs)-len(pending)),'total':128,'seconds':time.monotonic()-t}),flush=True)
    all_rows=[]
    for j in jobs:all_rows.extend(json.loads((folder/(j['role']+'_'+str(j['position'])+'.json')).read_text()))
    timing={'level_wall_seconds':time.monotonic()-t,'cold_to_first_result_seconds':cold}
    atomic_json(timing_path,timing)
    return all_rows,timing


def baseline_precision_budget(cfg,run):
    path=inp.ROOT/'provenance/runs'/cfg['baseline_run']/'full_audit.json'
    previous=json.loads(path.read_text())
    if not previous['passed'] or previous['final_test_access']:raise ValueError('Control numerical audit is not sealed/pass')
    # Prior audit's independent primary+replica variance is a conservative
    # upper bound on the retained primary variance alone. No raw outcomes read.
    bound={b:{'variance_upper_bound':(previous['models'][b]['es_three_se']/3)**2,
              'absolute_threshold_km':previous['contrast_precision'][b]['limit']}
           for b in ('ExactPoint','EndpointCI','LocalGaussian')}
    atomic_json(run['provenance']/'baseline_precision_budget.json',{
        'source':str(path.relative_to(inp.ROOT)),'source_sha256':file_sha256(path),
        'basis':'historical numerical audit metadata only; independent variance contributions added', 'controls':bound})
    return bound


def assess(rows,squared_weights,cfg,training_receipt,level_timing,baseline_bounds,run):
    groups={k:sorted([r for r in rows if r['K']==k],key=lambda x:(x['role'],x['position'])) for k in cfg['candidates']}
    frame=pd.DataFrame([{k:r[k] for k in ('role','id','position')} for r in groups[1]])
    w=fold_id_weights(frame);baseline=np.array([r['energy']['replicates'] for r in groups[1]])
    threshold=.0001*float(w@baseline.mean(axis=1));checks={};timing={}
    for k,group in groups.items():
        a=np.array([r['energy']['replicates'] for r in group]);b=np.array([r['replica']['replicates'] for r in group])
        delta_variance=(a-baseline).var(axis=1,ddof=1)/8
        projected=3*np.sqrt(float(delta_variance.max())*squared_weights['inner_sum_squared_weights'])
        absolute_variance=a.var(axis=1,ddof=1)/8
        control_checks={b:{'three_se_km':float(3*np.sqrt(float(absolute_variance.max())*squared_weights['outer_sum_squared_weights']+x['variance_upper_bound'])),
                           'threshold_km':x['absolute_threshold_km']} for b,x in baseline_bounds.items()}
        for x in control_checks.values():x['passed']=x['three_se_km']<=x['threshold_km']
        drift=aggregate_difference(a,b,w)
        area=np.array([r['metrics']['area90_km2'] for r in group]);area2=np.array([r['metrics']['replica_area90_km2'] for r in group])
        h=float(w@np.array([r['metrics']['hit_disagreement'] for r in group]))
        mass=float(w@np.array([r['metrics']['mass_diagnostic'] for r in group]))
        radius=max(r['metrics']['mass_radius'] for r in group)
        relative=abs(float(w@(area2-area)))/float(w@area)
        land=3*np.sqrt(float(w*w@np.array([r['regions']['land_variance'] for r in group])))
        outside=3*np.sqrt(float(w*w@np.array([r['regions']['outside_variance'] for r in group])))
        refs=[r for r in group if r['reference'] is not None]
        reference_checks=[]
        for r in refs:
            for method in ('reference','iid'):
                diff=r['energy']['energy_km']-r[method]['energy_km']
                limit=3*np.sqrt(r['energy']['variance']+r[method]['variance'])
                reference_checks.append({'role':r['role'],'position':r['position'],'method':method,
                    'difference_km':diff,'three_se_km':float(limit),'passed':bool(abs(diff)<=limit)})
        ref_pass=all(r['passed'] for r in reference_checks)
        es_pass=bool(projected<=threshold and all(x['passed'] for x in control_checks.values())
                     and abs(drift['delta_km'])<=drift['three_se_km'] and ref_pass)
        region_pass=bool(h<=.001 and relative<=.005 and mass<=.005 and radius<=.005 and land<=.001 and outside<=.001
                         and all(r['metrics']['rank']==2 for r in group))
        checks[str(k)]=dict(projected_three_se_km=float(projected),threshold_km=threshold,
            pilot_replica_drift=drift,hit_disagreement=h,mass_diagnostic=mass,max_mass_radius=radius,
            area_relative_change=relative,land_three_se=land,outside_three_se=outside,
            independent_control_precision=control_checks,reference_checks=reference_checks,
            component_reference_pass=ref_pass,energy_pass=es_pass,region_pass=region_pass,passed=bool(es_pass and region_pass))
        timing[str(k)]={kind:float(np.quantile([r['timing'][kind] for r in group if kind!='reference' or r['reference'] is not None],.95)) for kind in ('energy','region','audit','reference')}
    # Per-worker p95 operation costs with two measured parity-checked workers.
    es=sum(timing[str(k)]['energy'] for k in cfg['candidates'])
    reg=max(timing[str(k)]['region'] for k in cfg['candidates'])
    audits=sum(timing[str(k)]['audit'] for k in cfg['candidates'])
    cold=level_timing['cold_to_first_result_seconds']
    io_aggregate_allowance=300.
    projected_seconds={
      'inner_scoring':1.5*(cold+86373*(es+2*reg)/2+io_aggregate_allowance),
      'outer_scoring':1.5*(cold+33971*(es+sum(timing[str(k)]['region'] for k in cfg['candidates']))/2+io_aggregate_allowance),
      'audit':1.5*(cold+33971*(audits+sum(timing[str(k)]['region'] for k in cfg['candidates']))/2
                   +128*sum(timing[str(k)]['reference'] for k in cfg['candidates'])/2+io_aggregate_allowance)}
    epoch_max=max(float(np.quantile(v['epoch_seconds'],.95)) for v in training_receipt.values())
    # Full C_T0 ten-epoch fit is a cost probe, not a measured early-stop duration.
    # Include two forward temporal roles, all seeds/refits and data-size ratios.
    worst_training={'inner_training':1.5*epoch_max*500*24*(1+209934/170978),
                    'outer_training':1.5*epoch_max*500*24*(265393/170978)}
    prefix_seconds=1.5*epoch_max*5*6*(1+209934/170978)
    ledger=json.loads((run['provenance']/'resource_ledger.json').read_text())
    spent=sum(x['elapsed_seconds'] for x in ledger['entries'])+(ledger.get('active') or {}).get('elapsed_seconds',0)
    peaks=ledger['entries']+([ledger['active']] if ledger.get('active') else [])
    peak_rss=max(x.get('peak_process_tree_rss_bytes',0) for x in peaks)
    current_bytes=sum(p.stat().st_size for f in run.values() for p in f.rglob('*') if p.is_file())
    checkpoints=[p.stat().st_size for p in run['results'].rglob('checkpoint.pt')]
    row_bytes=max(len(json.dumps(r)) for r in rows)
    projected_bytes=current_bytes+max(checkpoints,default=0)*72+row_bytes*6*(86373+2*33971)+3528*(86373+33971)+512*2**20
    resource_checks={stage:bool(v<=remaining(cfg,ledger,stage)) for stage,v in projected_seconds.items()}
    resource_checks.update(inner_prefix=prefix_seconds<=remaining(cfg,ledger,'inner_training'),
        memory_preflight=peak_rss<=cfg['rss_preflight_gib']*2**30,
        storage_preflight=projected_bytes<=cfg['storage_preflight_gib']*2**30,
        cumulative_prefix_and_scoring=spent+prefix_seconds+sum(projected_seconds.values())<=cfg['seconds']['total'])
    resource_pass=all(resource_checks.values())
    return dict(basic_numerical_pass=all(v['passed'] for v in checks.values()),resource_pass=bool(resource_pass),
                energy_pass=all(v['energy_pass'] for v in checks.values()),region_pass=all(v['region_pass'] for v in checks.values()),
                selected_common_energy_count=rows[0]['energy_count'],selected_common_region_count=rows[0]['region_count'],
                numerical_checks=checks,p95_worker_timing_seconds=timing,projected_phase_seconds=projected_seconds,
                resource_checks=resource_checks,projected_storage_bytes=projected_bytes,pilot_peak_rss_bytes=peak_rss,
                training_500_epoch_upper_sensitivity_seconds=worst_training,training_typical_completion_estimate=None,
                bounded_inner_prefix_seconds=prefix_seconds,allowed_next_stage='inner_training_prefix_only',
                training_projection='500epochK32bound is sensitivity, not expected completion; measure allK5epoch resumable prefixes before a full-training gate',
                projection_limit='Pilot maximum observed variance is not a strict bound for unseen queries; full actual precision must pass.',
                is_model_selection=False,is_full_experiment=False,full_queries_preserved=True,final_test_access=False)


def numeric_pilot(name):
    run,cfg,tasks,squares=make_tasks(name)
    training_receipt=json.loads((run['provenance']/'pilot_training_receipt.json').read_text())
    bounds=baseline_precision_budget(cfg,run)
    inp.freeze_sources(run,'pilot_numeric')
    ni=mi=0
    while True:
        n,m=cfg['integration_levels'][ni],cfg['integration_levels'][mi]
        rows,timing=measure_level(name,run,tasks,n,m)
        receipt=assess(rows,squares,cfg,training_receipt,timing,bounds,run)
        receipt['level_timing']=timing
        atomic_json(run['provenance']/f'pilot_assessment_N{n}_M{m}.json',receipt)
        print(json.dumps({'pilot_N':n,'pilot_M':m,'numerical':receipt['basic_numerical_pass'],'resource':receipt['resource_pass'],
                          'projected_hours':{k:v/3600 for k,v in receipt['projected_phase_seconds'].items()}}),flush=True)
        if receipt['basic_numerical_pass'] or not receipt['resource_pass']:
            receipt['passed']=preflight_pass(receipt)
            receipt['stop_reason']=None if receipt['passed'] else 'resource_projection_exceeds_contract'
            atomic_json(run['provenance']/'pilot_result.json',receipt)
            return
        if (not receipt['energy_pass'] and ni==2) or (not receipt['region_pass'] and mi==2):
            receipt['passed']=False;receipt['stop_reason']='maximum_numerical_level_failed'
            atomic_json(run['provenance']/'pilot_result.json',receipt)
            return
        if not receipt['energy_pass']:ni+=1
        if not receipt['region_pass']:mi+=1


def run_pilot(name,stage):
    if stage=='pilot_train':train_pilot(name)
    elif stage=='pilot_numeric':numeric_pilot(name)
    else:raise ValueError('Unknown pilot stage')
