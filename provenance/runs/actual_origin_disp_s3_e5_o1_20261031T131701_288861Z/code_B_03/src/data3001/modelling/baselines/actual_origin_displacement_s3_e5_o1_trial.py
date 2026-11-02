"""Finite O1 benchmark stages; imported after input/reference profiling."""
import time,json,hashlib,inspect
import numpy as np
import pandas as pd
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_inputs import as_query
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1 import G1Kernel,ExclusiveTimer
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_profile_g1 import ProfiledG1
from data3001.paths import file_sha256
from pathlib import Path


def context(t,k,row):
    key=(id(k),int(row.horizon_days),int(row.origin_cell_1),int(row.fold))
    if key not in t.contexts:
        tick=time.monotonic();d=t.subset(row)
        lineage=dict(input_inventory=t.inventory,plan=t.config['optimisation_plan_sha256'],
                     sources={str(Path(inspect.getfile(cls)).relative_to(t.paths.root)):file_sha256(Path(inspect.getfile(cls)))
                              for cls in type(k).__mro__ if cls.__module__.startswith('data3001')})
        identity=hashlib.sha256(json.dumps(lineage,sort_keys=True).encode()).hexdigest()
        ctx=k.context(d,as_query(row),t.fitting(row),identity)
        t.contexts[key]=(ctx,d,time.monotonic()-tick)
    return t.contexts[key]


def benchmark(t,label,cls,profile_cls=None):
    for batch in (2048,8192):
        t.check();tick=time.monotonic()
        k=cls(t.geometry,t.tracks,batch_size=batch,rectangular_domain=True)
        setup=time.monotonic()-tick;t.kernels[(label,batch)]=k;total=0.
        for row in t.roster[t.roster.calibration].itertuples(index=False):
            t.check();q=as_query(row);ctx,d,ctx_seconds=context(t,k,row)
            tick=time.monotonic();out,why,counts=k.classify_context(q,ctx,check=t.check);elapsed=time.monotonic()-tick
            expected=t.reference[row.query_index]
            np.testing.assert_array_equal(out,expected[0]);np.testing.assert_array_equal(why,expected[1])
            t.results[(label,batch,row.query_index)]=(out,why)
            r=dict(stage='B',variant=label,batch=batch,query_index=row.query_index,horizon=q.horizon,origin=q.origin,coastal=row.coastal,seconds=elapsed,**counts)
            t.timings.append(r);total+=elapsed
            t.write(f'{label}_{batch}_{row.query_index:03d}',r)
            print(json.dumps(dict(variant=label,batch=batch,query=row.query_index,seconds=elapsed,parity=True)),flush=True)
        context_total=sum(c[2] for key,c in t.contexts.items() if key[0]==id(k))
        t.variant_scores.append(dict(variant=label,batch=batch,kernel_seconds=total,setup_seconds=setup,context_seconds=context_total,total_seconds=total+setup+context_total))
    if profile_cls:
        pk=profile_cls(t.geometry,t.tracks,rectangular_domain=True);pk.timer=ExclusiveTimer()
        times=[]
        for row in t.roster[t.roster.calibration].itertuples(index=False):
            ctx,_,_=context(t,pk,row);tick=time.monotonic()
            out,why,profile=pk.classify_context(as_query(row),ctx,check=t.check)
            np.testing.assert_array_equal(out,t.reference[row.query_index][0]);np.testing.assert_array_equal(why,t.reference[row.query_index][1])
            times.append(time.monotonic()-tick)
        t.write(label+'_exclusive',dict(seconds=sum(times),exclusive=pk.timer.rows))
        return sum(times),pk.timer.rows


def stage_b1(t):
    wall,profile=benchmark(t,'G1',G1Kernel,ProfiledG1)
    # The explicit predicate share is measured, never inferred from certificate count.
    predicates=sum(v['seconds'] for name,v in profile.items() if ':sh.' in name and 'box' not in name and 'linestrings' not in name)
    trigger=predicates/wall>=.3
    t.write('G2_trigger',dict(predicate_seconds=predicates,kernel_seconds=wall,fraction=predicates/wall,trigger=trigger,reason='predicate_fraction_at_least_30_percent' if trigger else 'predicate_fraction_below_threshold'))
    t.write('G1_benchmark_summary',t.variant_scores)


def stage_b2(t):
    from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_g2 import G2Kernel,ProfiledG2
    wall,profile=benchmark(t,'G2',G2Kernel,ProfiledG2)
    hourly=sum(v['seconds'] for name,v in profile.items() if name.startswith(('hourly','classify_context')))
    t.write('G3_trigger',dict(hourly_seconds=hourly,kernel_seconds=wall,fraction=hourly/wall,trigger=hourly/wall>=.2))
    t.write('G2_benchmark_summary',t.variant_scores)


def stage_b3(t):
    from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_g3 import G3Kernel
    benchmark(t,'G3',G3Kernel)
    t.write('G3_benchmark_summary',t.variant_scores)


def stage_c(t):
    from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_validation import validate
    validate(t)


def stage_d(t):
    from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_capacity import capacity
    capacity(t)
