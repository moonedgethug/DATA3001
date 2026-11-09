"""Approved frozen-packet diagnosis; no training and no new endpoint reads."""
import concurrent.futures as cf
from contextlib import ExitStack
import json
import math
import multiprocessing as mp
from pathlib import Path
import sys
import time
from unittest.mock import patch

import numpy as np
from data3001.modelling.continuous_models import conditional_mdn_s5_e3_numerics as num
from data3001.modelling.continuous_models import conditional_mdn_s5_e3_inputs as inp
from data3001.modelling.continuous_models.conditional_mdn_s5_e3_runtime import atomic_json
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography

HERE=Path(__file__).resolve().parent
PROV=HERE.parent
ROOT=HERE.parents[3]
RESULTS=ROOT/'results/runs'/PROV.name
GEO=None


def initialize():
    global GEO
    paths,_,_,_,_=inp.context(PROV.name)
    GEO=Geography(paths)


def load_tasks():
    value=json.loads((PROV/'pilot_frozen_tasks.json').read_text())
    return [t for t in value if t['component_check']]


def legacy_row(task,k):
    rows=json.loads((RESULTS/'pilot_numerics/N65536_M65536'/
                   (task['role']+'_'+str(task['position'])+'.json')).read_text())
    return next(r for r in rows if r['K']==k)


def matched_node_terms(task,k):
    p=task['packets'][str(k)];key=tuple(task['key'])
    u=num.uniforms(8192,6,'ES',0,key,task['role'])
    truth=num.xyz(np.asarray(task['target'])[None])[0]
    w,m,l=num.arrays(p);cdf=np.cumsum(w);cdf[-1]=1.
    paired=[];max_point=0.
    for nodes in (u[:,:3],u[:,3:]):
        # Per-component evaluation is distinct from the production gathered einsum.
        selected=np.searchsorted(cdf,nodes[:,0],side='right')
        z=num.normals(nodes[:,1:]);vectors=np.empty_like(z)
        for j in range(k):
            at=selected==j
            vectors[at]=m[j]+z[at]@l[j].T
        a=num.xyz(num.to_geographic(p['origin'],vectors))
        b=num.xyz(num.draw(p,nodes))
        max_point=max(max_point,float(np.max(np.abs(a-b))))
        paired.append((a,b))
    first=[float(np.linalg.norm(v-truth,axis=1).mean()) for v in paired[0]]
    second=[float(.5*np.linalg.norm(paired[0][j]-paired[1][j],axis=1).mean()) for j in range(2)]
    error=max(abs(first[0]-first[1]),abs(second[0]-second[1]))
    if error>1e-9 or max_point>1e-9:raise ArithmeticError('Matched-node evaluation differs')
    return dict(K=k,role=task['role'],position=task['position'],first_terms_km=first,
                self_distance_terms_km=second,max_term_difference_km=error,max_point_difference_km=max_point)


def operation_profile(tasks):
    stats={};totals={}
    def timed(name,fn):
        def call(*args,**kwargs):
            t=time.perf_counter()
            try:return fn(*args,**kwargs)
            finally:
                rec=stats.setdefault(name,{'seconds':0.,'calls':0})
                rec['seconds']+=time.perf_counter()-t;rec['calls']+=1
        return call
    with ExitStack() as stack:
        for name in ('uniforms','normals','arrays','to_geographic','xyz','xy'):
            stack.enter_context(patch.object(num,name,timed(name,getattr(num,name))))
        stack.enter_context(patch.object(num.region_math,'fit_region',timed('fit_region',num.region_math.fit_region)))
        stack.enter_context(patch.object(Geography,'masses',timed('geography_masses',Geography.masses)))
        for task in tasks:
            for k in (1,2,4,8,16,32):
                p=task['packets'][str(k)];key=tuple(task['key']);role=task['role']
                for label,fn in [('energy',lambda:num.score_es(p,task['target'],65536,key,role)),
                                 ('region',lambda:num.build_region(p,65536,key,role,GEO)),
                                 ('audit_energy',lambda:num.score_es(p,task['target'],65536,key,role,audit=True))]:
                    t=time.perf_counter();fn();totals[label]=totals.get(label,0.)+time.perf_counter()-t
    return dict(function_timings=stats,operation_totals=totals,
                timing_note='Instrumented single-worker profile; nested function times are not additive. Not a speed benchmark.')


def stage_a():
    initialize();tasks=load_tasks();rows=[]
    for task in tasks:
        for k in (1,2,4,8,16,32):rows.append(matched_node_terms(task,k))
    profile=operation_profile(tasks)
    result={'matched_node_checks':rows,'profile':profile,'all_matched_node_passed':True,
            'training_started':False,'outer_targets_read':False,'full_sample_definition_unchanged':True}
    atomic_json(HERE/'stage_A.json',result)
    print(json.dumps({'stage':'A','matched_checks':len(rows),'max_term_difference_km':max(r['max_term_difference_km'] for r in rows),'profile':profile}),flush=True)


def reference_job(task):
    rows=[]
    for k in (1,2,4,8,16,32):
        p=task['packets'][str(k)];old=legacy_row(task,k)
        for count in (65536,262144):
            start=time.perf_counter()
            reference=num.reference_component_es(p,task['target'],count,tuple(task['key']),task['role'])
            elapsed=time.perf_counter()-start
            delta=old['energy']['energy_km']-reference['energy_km']
            limit=3*math.sqrt(old['energy']['variance']+reference['variance'])
            row=dict(K=k,role=task['role'],position=task['position'],count=count,reference=reference,
                     main=old['energy'],original_reference=old['reference'],difference_km=delta,
                     three_se_km=limit,passed=abs(delta)<=limit,seconds=elapsed)
            rows.append(row)
            atomic_json(HERE/'reference_rows'/f"{task['role']}_{task['position']}_K{k}_N{count}.json",row)
    return rows


def stage_b():
    tasks=load_tasks();rows=[];start=time.perf_counter()
    with cf.ProcessPoolExecutor(max_workers=2,mp_context=mp.get_context('spawn'),initializer=initialize) as pool:
        for i,rs in enumerate(pool.map(reference_job,tasks),1):
            rows.extend(rs);print(json.dumps({'stage':'B','queries_complete':i,'total':8,'seconds':time.perf_counter()-start}),flush=True)
    result={'rows':rows,'counts':{str(n):{'passed':sum(r['passed'] for r in rows if r['count']==n),'total':48}
                                  for n in (65536,262144)},'seconds':time.perf_counter()-start,
            'diagnostic_only':True,'original_reference_gate_preserved':True,
            'no_seed_retries':True,'formal_next_stage':None}
    atomic_json(HERE/'stage_B.json',result)
    print(json.dumps({'stage':'B','counts':result['counts'],'seconds':result['seconds']}),flush=True)


if __name__=='__main__':
    {'A':stage_a,'B':stage_b}[sys.argv[1]]()
