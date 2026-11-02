"""Frozen O1 validation, exact fold-count checkpoints and scalar cross-checks."""
import time,json,hashlib
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from data3001.paths import file_sha256
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_inputs import as_query,reference_distribution
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_audit import audit_transfers
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_trial import context
from data3001.modelling.baselines.local_endpoint_adaptive_s3_e2 import fit_bases
from data3001.modelling.common.prediction_regions import probability_region
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_checkpoint import read_checkpoint


def counts_distribution(table,p,states):
    """Independent integer-count reconstruction, retaining failed donor mass."""
    n=int(table.pair_count.sum());v=np.zeros(len(states));lookup={int(x):j for j,x in enumerate(states)}
    if not n:return p.copy()
    for r in table.itertuples(index=False):
        if r.destination==-3:v+=r.pair_count*p/n
        else:v[lookup[int(r.destination)]]+=r.pair_count/n
    return v


def validate(t):
    t.snapshot('C_body')
    candidates=sorted(t.variant_scores,key=lambda r:(r['total_seconds'],r['variant'],r['batch']))
    best=candidates[0]['total_seconds']
    chosen=min((r for r in candidates if r['total_seconds']<=best*1.05),key=lambda r:(r['variant'],r['batch']))
    t.selected=dict(chosen);t.write('configuration_freeze',dict(selected=chosen,source='calibration_only',before_validation=True))
    label,batch=chosen['variant'],chosen['batch'];k=t.kernels[(label,batch)]
    # Contexts are immutable and constructed on the main thread before concurrency.
    calibration=list(t.roster[t.roster.calibration].itertuples(index=False))
    for row in calibration:context(t,k,row)
    def calculate(row):
        ctx,_,_=context(t,k,row)
        return row.query_index,k.classify_context(as_query(row),ctx,check=t.check)
    start=time.monotonic()
    serial=[calculate(row) for row in calibration];serial_s=time.monotonic()-start;t.check()
    start=time.monotonic()
    pool=ThreadPoolExecutor(max_workers=2)
    try:parallel=list(pool.map(calculate,calibration))
    finally:pool.shutdown(wait=True,cancel_futures=True)
    parallel_s=time.monotonic()-start;t.check()
    for (ia,a),(ib,b) in zip(serial,parallel):
        if ia!=ib:raise AssertionError('Concurrent ordering changed')
        for x,y in zip(a[:2],b[:2]):np.testing.assert_array_equal(x,y)
    workers=2 if parallel_s<serial_s/1.05 else 1
    t.parallel=dict(serial_seconds=serial_s,two_worker_seconds=parallel_s,speedup=serial_s/parallel_s,selected_workers=workers,effective_speedup=serial_s/parallel_s if workers==2 else 1.)
    t.write('parallel',t.parallel)
    t.validated={};t.records={7:[],30:[]};t.base_cache={};t.scalar_checks=[];t.parity_count=0
    truth=t.donors.set_index(['id','origin_source_obs','horizon_days']).destination_cell_1.to_dict()
    checkpoint_seconds=0.;audit_seconds=0.;fit_seconds=0.;region_checks=0
    coordinate_cache={};coordinate_cache_hits=0
    for row in t.roster.itertuples(index=False):
        t.check();q=as_query(row);ctx,d,ctx_seconds=context(t,k,row)
        coordinate_key=(ctx.identity,q.lon.hex(),q.lat.hex(),q.horizon)
        if q.id in ctx.fitting_ids or q.fold in ctx.donor_folds:raise PermissionError('Cached coordinate role leakage')
        k.query_safe(q)  # Validate the actual coordinate even on a cache hit.
        if row.calibration:
            out,why=t.results[(label,batch,row.query_index)]
        elif coordinate_key in coordinate_cache:
            out,why=coordinate_cache[coordinate_key];coordinate_cache_hits+=1
        else:
            start=time.monotonic();out,why,counts=k.classify_context(q,ctx,check=t.check);elapsed=time.monotonic()-start
            r=dict(stage='C',variant=label,batch=batch,query_index=row.query_index,horizon=q.horizon,origin=q.origin,coastal=row.coastal,seconds=elapsed,**counts)
            t.timings.append(r);t.write(f'validation_{row.query_index:03d}',r)
        coordinate_cache[coordinate_key]=(out,why)
        if row.parity_validation:
            start=time.monotonic();a,b,_=t.reference_kernel.classify(q,d,t.fitting(row),check=t.check)
            old_seconds=time.monotonic()-start
            t.timings.append(dict(stage='C',variant='reference',batch=2048,query_index=row.query_index,horizon=q.horizon,origin=q.origin,coastal=row.coastal,seconds=old_seconds,donors=len(d)))
            np.testing.assert_array_equal(out,a);np.testing.assert_array_equal(why,b)
            t.reference[row.query_index]=(a,b)
            t.save_outcomes(f'reference_{row.query_index:03d}',a,b)
        if row.query_index in t.reference:
            np.testing.assert_array_equal(out,t.reference[row.query_index][0]);np.testing.assert_array_equal(why,t.reference[row.query_index][1]);t.parity_count+=len(d)
            t.save_outcomes(f'selected_{row.query_index:03d}',out,why)
        t.validated[row.query_index]=(out,why)
        start=time.monotonic()
        audits=audit_transfers(q,d,t.tracks,t.geometry,out,why,maximum=87)
        audit_seconds+=time.monotonic()-start
        t.scalar_checks.extend(dict(query_index=row.query_index,horizon=q.horizon,coastal=row.coastal,query_fold=q.fold,**a) for a in audits)
        t.check()
        start=time.monotonic()
        table=pd.DataFrame(dict(donor_fold=d.fold.to_numpy(),destination=out,reason=why)).value_counts().reset_index(name='pair_count')
        t.frame(f'checkpoint_{row.query_index:03d}',table)
        path=t.run['results']/f'checkpoint_{row.query_index:03d}.csv'
        receipt=dict(context_identity=ctx.identity,query_coordinate_hex=[q.lon.hex(),q.lat.hex()],horizon=q.horizon,source_key=[q.id,q.source_obs],query_fold=q.fold,sha256=file_sha256(path),donors=len(d),algorithm=[label,batch])
        t.write(f'checkpoint_{row.query_index:03d}_receipt',receipt)
        # Read-back simulates resuming a fully committed atomic chunk.
        loaded=read_checkpoint(path,receipt,ctx.identity,[q.lon.hex(),q.lat.hex()],q.horizon,[q.id,q.source_obs],q.fold,[label,batch])
        pd.testing.assert_frame_equal(table,loaded,check_dtype=False)
        if int(table.pair_count.sum())!=len(d) or set(table.donor_fold)&{q.fold}:raise AssertionError('Checkpoint mass/role violation')
        checkpoint_seconds+=time.monotonic()-start
        # Reconstruct every permitted inner role independently from fold counts.
        for outer in sorted(ctx.donor_folds):
            ids=t.folds.loc[~t.folds.outer_fold.isin([q.fold,outer]),'id'].tolist()
            mask=d.id.isin(ids).to_numpy()
            direct=pd.Series(out[mask]).value_counts().sort_index()
            from_blocks=table[table.donor_fold.ne(outer)].groupby('destination').pair_count.sum().sort_index()
            np.testing.assert_array_equal(direct.index,from_blocks.index);np.testing.assert_array_equal(direct.values,from_blocks.values)
        outer=0 if q.fold!=0 else 1;role=(outer,q.fold)
        if role not in t.base_cache:
            start=time.monotonic();ids=t.folds.loc[~t.folds.outer_fold.isin(role),'id'].tolist()
            t.base_cache[role]=fit_bases(t.counts,ids,t.origins.cell,[*t.destinations.cell,-2]);fit_seconds+=time.monotonic()-start
        base=t.base_cache[role];p=base.rows[(q.horizon,q.origin)];mask=d.fold.ne(outer).to_numpy()
        v,r=reference_distribution(out[mask],p,base.states)
        v2=counts_distribution(loaded[loaded.donor_fold.ne(outer)],p,base.states)
        if np.max(np.abs(v-v2))>1e-12:raise AssertionError('Resumed probabilities changed')
        for a in np.linspace(0,1,21):
            prob=(1-a)*p+a*v;prob2=(1-a)*p+a*v2
            region,m=probability_region(prob,base.states);region2,m2=probability_region(prob2,base.states)
            np.testing.assert_array_equal(region,region2)
            y=base.index[truth[(q.id,q.source_obs,q.horizon)]]
            if abs((1+prob@prob-2*prob[y])-(1+prob2@prob2-2*prob2[y]))>1e-12:raise AssertionError('Resumed Brier changed')
            region_checks+=1
        t.records[q.horizon].append(dict(query=row._asdict(),q=v,fallback=r,truth=int(truth[(q.id,q.source_obs,q.horizon)]),base_role=role))
        print(json.dumps(dict(validation_query=row.query_index,scalar_checks=len(t.scalar_checks))),flush=True)
    if len(t.scalar_checks)<5000:raise AssertionError('Insufficient independent scalar checks')
    t.frame('scalar_checks',pd.DataFrame(t.scalar_checks))
    t.validation=dict(queries=len(t.validated),complete_pair_parity=t.parity_count,scalar_checks=len(t.scalar_checks),probability_region_comparisons=region_checks,checkpoint_seconds=checkpoint_seconds,scalar_audit_seconds=audit_seconds,control_base_fit_seconds=fit_seconds,exact_coordinate_cache_hits=coordinate_cache_hits,all_donors_retained=True,full_scientific_population_unchanged=True)
    t.write('validation',t.validation)
