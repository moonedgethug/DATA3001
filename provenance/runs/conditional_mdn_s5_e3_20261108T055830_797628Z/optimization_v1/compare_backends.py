"""Full fixed-pilot equivalence and matched old/new timing, never model fitting."""
import concurrent.futures as cf
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import time

import numpy as np
from data3001.modelling.continuous_models import conditional_mdn_s5_e3_numerics as old
from data3001.modelling.continuous_models import conditional_mdn_s5_e3_optimized as new
from data3001.modelling.continuous_models import conditional_mdn_s5_e3_inputs as inp
from data3001.modelling.continuous_models.conditional_mdn_s5_e3_runtime import atomic_json
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography

HERE=Path(__file__).resolve().parent
PROV=HERE.parent
ROOT=HERE.parents[3]
RESULTS=ROOT/'results/runs'/PROV.name
GEO=None
STOP=None


def initialize(stop=None):
    global GEO,STOP
    STOP=stop
    paths,_,_,_,_=inp.context(PROV.name)
    GEO=Geography(paths)


def require_active():
    if STOP is not None and STOP.is_set():raise InterruptedError('Validation cancelled after worker failure')


def collect_results(pool,futures,stop):
    """Signal running jobs and cancel pending jobs before waiting on shutdown."""
    try:
        for future in cf.as_completed(futures):yield future.result()
    except BaseException:
        stop.set()
        for future in futures:future.cancel()
        raise
    finally:
        pool.shutdown(wait=True,cancel_futures=True)


class GeographyRecorder:
    def __init__(self): self.identities=[]
    def masses(self,points,weights):
        # Identical classification coordinates/weights and geometry imply the
        # same per-point masks; actual resulting masses are compared as well.
        self.identities.append(hashlib.sha256(points.tobytes()+weights.tobytes()).hexdigest())
        return GEO.masses(points,weights)


def evaluate(task,optimized):
    engine=new if optimized else old
    key=tuple(task['key']);role=task['role'];results=[]
    caches={name:new.QueryCache(key,name,max_bytes=32*2**20)
            for name in ('ES','region','audit_ES','audit_region')} if optimized else {}
    peak_bytes=0
    try:
        for k in (1,2,4,8,16,32):
            require_active()
            p=task['packets'][str(k)]
            start=time.perf_counter()
            p=new.prepare_packet(p) if optimized else p
            parameter_seconds=time.perf_counter()-start
            kwargs=lambda scope: {'cache':caches[scope]} if optimized else {}
            row={'K':k};timing={'parameters':parameter_seconds};geo=GeographyRecorder()
            for field,fn in (
                ('energy',lambda:engine.score_es(p,task['target'],65536,key,role,**kwargs('ES'))),
                ('region',lambda:engine.build_region(p,65536,key,role,geo,**kwargs('region'))),
                ('audit_energy',lambda:engine.score_es(p,task['target'],65536,key,role,audit=True,**kwargs('audit_ES'))),
                ('audit_region',lambda:engine.build_region(p,65536,key,role,geo,audit=True,**kwargs('audit_region')))):
                require_active()
                start=time.perf_counter();row[field]=fn();timing[field]=time.perf_counter()-start
            row['metrics']=old.region_metrics(row['region'],task['target'])
            row['audit_metrics']=old.region_metrics(row['audit_region'],task['target'])
            row['geography_input_hashes']=geo.identities
            row['timing']=timing;results.append(row)
            if caches:peak_bytes=max(peak_bytes,sum(c.cache_bytes for c in caches.values()))
    finally:
        for cache in caches.values():cache.close()
    if caches and any(c.cache_bytes for c in caches.values()):raise RuntimeError('Query cache leaked')
    return results,peak_bytes


def without_timings(rows):
    return [{k:v for k,v in r.items() if k!='timing'} for r in rows]


def compare(expected,actual):
    exact=expected==actual
    # Stronger than the permitted rounding tolerance. All region parameters,
    # coordinates and weights are identical, hence deterministic masks are too.
    # Do not call Python numeric equality byte/bit equality.
    if not exact:raise ArithmeticError('Full same-node numerical results are not exactly value-equal')
    for a,b in zip(expected,actual):
        assert a['K']==b['K']
        if a['geography_input_hashes']!=b['geography_input_hashes']:
            raise ArithmeticError('Classification nodes/weights changed')
        for field in ('energy','audit_energy'):
            if np.max(np.abs(np.array(a[field]['replicates'])-b[field]['replicates']))>1e-9:
                raise ArithmeticError('Same-node ES differs')
            np.testing.assert_allclose(a[field]['variance'],b[field]['variance'],rtol=1e-10,atol=1e-18)
        for field in ('region','audit_region'):
            for shape in ('region','replica_region'):
                aa,bb=a[field][shape],b[field][shape]
                if aa['rank']!=bb['rank']:raise ArithmeticError('Region rank changed')
                np.testing.assert_allclose(aa['area_km2'],bb['area_km2'],rtol=1e-10,atol=0)
                for quantity in ('centre','covariance','inverse','cutoff','attained_mass'):
                    np.testing.assert_allclose(aa[quantity],bb[quantity],rtol=1e-12,atol=1e-12)
            for quantity in ('mass_check','land_mass','outside_D_mass'):
                if a[field][quantity]!=b[field][quantity]:raise ArithmeticError('Probability diagnostic changed')
        for field in ('metrics','audit_metrics'):
            for quantity in ('h90','hit_disagreement','rank'):
                if a[field][quantity]!=b[field][quantity]:raise ArithmeticError('Region decision changed')
    return exact


def job(task):
    require_active()
    # Alternate ordering to reduce clock/thermal order bias. No cache crosses queries.
    outputs={};start=time.perf_counter();peak=0
    old.uniforms.cache_clear()
    for backend in (('new','old') if task['ordinal']%2 else ('old','new')):
        require_active()
        outputs[backend],memory=evaluate(task,backend=='new');peak=max(peak,memory)
    old_rows=without_timings(outputs['old']);new_rows=without_timings(outputs['new'])
    exact=compare(old_rows,new_rows)
    saved=json.loads((RESULTS/'pilot_numerics/N65536_M65536'/
                     (task['role']+'_'+str(task['position'])+'.json')).read_text())
    for r,past in zip(old_rows,saved):
        if r['energy']!=past['energy'] or r['region']!=past['regions'] or r['audit_energy']!=past['replica']:
            raise ArithmeticError('Legacy computation no longer reproduces frozen outputs')
    return dict(role=task['role'],position=task['position'],key=task['key'],
                old=outputs['old'],new=outputs['new'],exact_value_equal=exact,
                peak_combined_query_cache_bytes=peak,seconds=time.perf_counter()-start)


def main():
    tasks=json.loads((PROV/'pilot_frozen_tasks.json').read_text())
    for i,t in enumerate(tasks):t['ordinal']=i
    # Single-worker baseline for fixed first query, followed by the full two-worker run.
    ctx=mp.get_context('spawn');stop=ctx.Event()
    pool=cf.ProcessPoolExecutor(max_workers=1,mp_context=ctx,initializer=initialize,initargs=(stop,))
    single=list(collect_results(pool,[pool.submit(job,tasks[0])],stop))[0]
    stop=ctx.Event()
    pool=cf.ProcessPoolExecutor(max_workers=2,mp_context=ctx,initializer=initialize,initargs=(stop,))
    parity=list(collect_results(pool,[pool.submit(job,tasks[0]),pool.submit(job,tasks[0])],stop))
    for first in parity:
        for backend in ('old','new'):
            if without_timings(single[backend])!=without_timings(first[backend]):raise ArithmeticError('Worker-count parity failed')
    folder=HERE/'comparison_rows';folder.mkdir(exist_ok=True)
    start=time.perf_counter();results=[];cold=None
    stop=ctx.Event()
    pool=cf.ProcessPoolExecutor(max_workers=2,mp_context=ctx,initializer=initialize,initargs=(stop,))
    pending=[pool.submit(job,t) for t in tasks]
    for i,row in enumerate(collect_results(pool,pending,stop),1):
        results.append(row)
        if cold is None:cold=time.perf_counter()-start
        atomic_json(folder/f"{row['role']}_{row['position']}.json",row)
        if i%8==0:print(json.dumps({'queries_complete':i,'total':128,'seconds':time.perf_counter()-start}),flush=True)
    timings={}
    for backend in ('old','new'):
        timings[backend]={}
        for k in (1,2,4,8,16,32):
            group=[next(x for x in r[backend] if x['K']==k)['timing'] for r in results]
            timings[backend][str(k)]={field:{'p50':float(np.median([r[field] for r in group])),
                'p95':float(np.quantile([r[field] for r in group],.95)),
                'mean':float(np.mean([r[field] for r in group]))} for field in group[0]}
    summary=dict(queries=len(results),probe_records=len(results)*6,all_equivalent=True,
        all_exact_value_equal=all(r['exact_value_equal'] for r in results),single_two_worker_identical=True,
        old_frozen_results_reproduced=True,timings=timings,wall_seconds=time.perf_counter()-start,
        cold_plus_first_paired_query_seconds=cold,peak_combined_query_cache_bytes=max(r['peak_combined_query_cache_bytes'] for r in results),
        no_formal_training=True,no_new_targets=True)
    atomic_json(HERE/'stage_C.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='timings'}),flush=True)


if __name__=='__main__':main()
