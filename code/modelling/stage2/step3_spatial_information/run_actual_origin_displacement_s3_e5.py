"""Approved E5 v2 resource gate. Full orchestration follows only a passing pilot."""
import argparse
from datetime import datetime,timezone
import importlib.metadata
import json
import platform
import resource
import signal
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
import shapely as sh

from data3001.paths import project_paths,file_sha256
from data3001.modelling.common.runtime import save_frame,save_json,_seal
from data3001.modelling.common.qualified_count_inputs import ExperimentGuard,load_inputs
from data3001.modelling.baselines.spatial_borrowing_s3_e1_inputs import base_allowlist,source_hashes,Geometry,neighbours
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_inputs import (
    prepared_allowlist,load_prepared,as_query,ActualOriginKernel,reference_distribution,E5_REASONS,
)
from data3001.modelling.baselines.local_endpoint_adaptive_s3_e2 import fit_bases
from data3001.modelling.baselines.actual_origin_displacement_s3_e5 import make_evaluator,pilot_references
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_selection import search
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_audit import audit_transfers,audit_search

CONFIG_SHA='e6c6731bab544b8b9064a4c268728416af96a5443c7b30d46b56884c02717e79'


class CapacityStop(RuntimeError):
    pass


def rss_bytes():
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform=='darwin' else value*1024)


def workload_table(counts,folds,origins,geometry):
    counts=counts.merge(folds,on='id',validate='many_to_one');rows=[]
    originset=set(map(int,origins.cell))
    for h in (7,30):
        c=counts[counts.horizon_days.eq(h)]
        for i in sorted(c.origin_cell_1.unique()):
            own=c[c.origin_cell_1.eq(i)];don=c[c.origin_cell_1.isin(set(neighbours(i))&originset)]
            outer=0
            for fold in range(5):
                outer+=int(own.loc[own.outer_fold.eq(fold),'pair_count'].sum())*int(don.loc[don.outer_fold.ne(fold),'pair_count'].sum())
            fitown=own[own.outer_fold.isin([2,3,4])];fitdon=don[don.outer_fold.isin([2,3,4])]
            nquery=int(own.loc[own.outer_fold.eq(1),'pair_count'].sum());ndonor=int(fitdon.pair_count.sum())
            meta=origins[origins.cell.eq(i)].iloc[0]
            square=sh.box(meta.lon_min,meta.lat_min,meta.lon_min+1,meta.lat_min+1)
            coastal=bool(sh.intersects(geometry.high,square) or sh.intersects(geometry.intermediate,square))
            rows.append(dict(horizon_days=h,origin_cell_1=int(i),outer_query_donor_combinations=outer,
                pilot_query_count=nquery,pilot_donor_count=ndonor,pilot_local_ids=fitown.id.nunique(),
                pilot_work_product=nquery*ndonor,coastal=coastal))
    return pd.DataFrame(rows)


def pilot_roster(queries,workload):
    rows=[];strata=[]
    for h in (7,30):
        eligible=workload[(workload.horizon_days==h)&(workload.pilot_query_count>0)&
                          (workload.pilot_local_ids>0)&(workload.pilot_donor_count>0)]
        choices=[]
        for label,subset,columns,ascending in [
            ('largest_work',eligible,['pilot_work_product','origin_cell_1'],[False,True]),
            ('lowest_local_support',eligible,['pilot_local_ids','origin_cell_1'],[True,True]),
            ('coastal_largest_work',eligible[eligible.coastal],['pilot_work_product','origin_cell_1'],[False,True])]:
            if len(subset):
                chosen=int(subset.sort_values(columns,ascending=ascending).iloc[0].origin_cell_1)
                choices.append(chosen);strata.append(dict(horizon_days=h,stratum=label,cell=chosen,available=True))
            else:strata.append(dict(horizon_days=h,stratum=label,cell=None,available=False))
        ordered=list(dict.fromkeys(choices))
        # Outcome-independent additional coverage permitted by the resource gate:
        # do not extrapolate offshore cost from an early-failing coastal path.
        for coastal in (False,True):
            group=eligible[eligible.coastal.eq(coastal)]
            if len(group) and not set(group.origin_cell_1)&set(ordered):
                extra=int(group.sort_values(['pilot_work_product','origin_cell_1'],ascending=[False,True]).iloc[0].origin_cell_1)
                ordered.append(extra);choices.append(extra)
                strata.append(dict(horizon_days=h,stratum=f'additional_coastal_{coastal}_work_coverage',cell=extra,available=True))
        for i in (44744,44742,44382):
            if i in set(eligible.origin_cell_1) and i not in ordered:ordered.append(i)
        for i in ordered:
            q=queries[(queries.horizon_days==h)&(queries.origin_cell_1==i)&(queries.fold==1)].sort_values(['id','origin_source_obs'])
            n=min(8 if i in choices else 1,len(q))
            selected=q.iloc[np.linspace(0,len(q)-1,n,dtype=int)].copy()
            selected['pilot_cell_queries']=n
            rows.extend(selected.to_dict('records'))
    roster=pd.DataFrame(rows)
    if roster.duplicated(['id','origin_source_obs','horizon_days']).any():raise AssertionError('Duplicate pilot query')
    return roster,strata


def geometry_projection(timings,workload,roster):
    """Measured strata only, with ideal two-worker speedup and the approved reserve."""
    if not timings:return [],0.
    rows=[];table=pd.DataFrame(timings)
    for (h,i),g in table.groupby(['horizon_days','origin_cell_1']):
        planned=int(((roster.horizon_days==h)&(roster.origin_cell_1==i)).sum())
        if len(g)!=planned:continue
        workload_count=int(workload[(workload.horizon_days==h)&(workload.origin_cell_1==i)].iloc[0].outer_query_donor_combinations)
        rate=float(g.seconds.sum()/g.donors.sum())
        # Reserve factor 2 cancels the most optimistic allowed parallelism of 2.
        projection=rate*workload_count*2/2
        rows.append(dict(horizon_days=int(h),origin_cell_1=int(i),measured_queries=len(g),
            seconds_per_donor=rate,outer_combinations=workload_count,
            projected_seconds_with_reserve_and_ideal_two_workers=projection))
    return rows,sum(r['projected_seconds_with_reserve_and_ideal_two_workers'] for r in rows)


def complete_projection(timings,workload,solver_profiles,control_seconds,multiplier_seconds,fit_seconds):
    """Conservative stratum projection; an unmeasured horizon/coast class cannot pass."""
    observed=pd.DataFrame(timings).merge(workload[['horizon_days','origin_cell_1','coastal']],on=['horizon_days','origin_cell_1'],validate='many_to_one')
    geometry_seconds=0.;missing=[]
    for (h,coastal),g in workload.groupby(['horizon_days','coastal']):
        sample=observed[(observed.horizon_days==h)&observed.coastal.eq(coastal)]
        if not len(sample):missing.append([int(h),bool(coastal)]);continue
        rate=float((sample.seconds/sample.donors).max())
        geometry_seconds+=rate*int(g.outer_query_donor_combinations.sum())*2/2
    # 5 aggregate-query passes per horizon cover all inner tasks and final tuning.
    score_seconds=0.
    for p in solver_profiles:
        query_count=303288 if p['horizon_days']==7 else 268998
        per_query_candidate=p['full_metric_seconds']/max(1,p['queries']*p['full_metric_candidates'])
        score_seconds+=per_query_candidate*query_count*5*252*2/2
        per_call=p['coefficient_seconds']/max(1,p['optimizer_calls'])
        score_seconds+=per_call*6*22000*2/2
    # Controls, fit setup and independent audit/report have their own reserve.
    score_seconds+=control_seconds*25*2/2+fit_seconds*26*2/2+multiplier_seconds*2/2
    return dict(geometry_seconds=geometry_seconds,scoring_lower_projection_seconds=score_seconds,
                missing_work_strata=missing,
                capacity_established=not missing and len(solver_profiles)==2 and
                    geometry_seconds<=3600 and score_seconds<=3600)


def run_pilot(paths,config):
    run_id='actual_origin_disp_s3_e5_pilot_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run=paths.create_run(run_id,config)
    allowed=base_allowlist(paths,config)+prepared_allowlist(paths,config)
    guard=ExperimentGuard(paths,run,allowed);sys.addaudithook(guard)
    start=time.monotonic();timings=[];audits=[];solver_profiles=[];projection=[]
    roster=pd.DataFrame();workload=pd.DataFrame();strata=[];inventory={};source={};reason='';status='RUNNING'
    complete_cost=None
    stage='input_verification';last_progress=start;last_resource_check=start-5
    def check():
        nonlocal last_progress,last_resource_check
        elapsed=time.monotonic()-start
        if elapsed>config['preflight_cap_seconds']:raise CapacityStop('pilot_300_second_cap')
        if time.monotonic()-last_resource_check>=5:
            if rss_bytes()>config['max_rss_bytes']:raise CapacityStop('8_GiB_memory_cap')
            artifact_size=sum(p.stat().st_size for d in run.values() for p in d.rglob('*') if p.is_file())
            if artifact_size>config['max_new_artifact_bytes']:raise CapacityStop('5_GiB_artifact_cap')
            last_resource_check=time.monotonic()
        if time.monotonic()-last_progress>15:
            print(json.dumps(dict(stage=stage,elapsed_seconds=round(elapsed,2),completed_queries=len(timings))),flush=True)
            last_progress=time.monotonic()
    def alarm(*_):raise CapacityStop('pilot_300_second_cap')
    oldhandler=signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,300)
    try:
        approval=json.loads(paths._resolve(config['approval']).read_text())
        if not approval['approved'] or approval['plan_sha256']!=config['approved_plan_sha256']:
            raise PermissionError('Missing E5 v2 execution approval')
        if file_sha256(paths._resolve(config['approved_plan']))!=config['approved_plan_sha256']:
            raise ValueError('Approved plan hash changed')
        if importlib.metadata.version('scipy')!=config['installed_scipy']:raise ValueError('Unpinned SciPy runtime')
        counts,folds,origins,destinations,_,inventory=load_inputs(paths,config)
        check();states=[*destinations.cell,-2]
        geometry=Geometry.load(paths,destinations.cell)
        stage='prepared_path_reconciliation'
        tracks,donors,queries=load_prepared(paths,config,counts,folds,geometry,inventory,check)
        check();workload=workload_table(counts,folds,origins,geometry)
        totals=workload.groupby('horizon_days').outer_query_donor_combinations.sum().to_dict()
        if totals!={7:15179967338,30:12193653838}:raise AssertionError('Planning workload no longer reconciles')
        roster,strata=pilot_roster(queries,workload)
        save_frame(paths,run['results']/'pilot_roster.csv',roster)
        save_frame(paths,run['results']/'workload.csv',workload)
        save_json(paths,run['provenance']/'roster_freeze.json',dict(strata=strata,selection_used_outcomes=False,
            roster_sha256=file_sha256(run['results']/'pilot_roster.csv'),phase='before_geometry_timing_and_weight_selection'))
        source=source_hashes(paths)
        save_json(paths,run['provenance']/'source_sha256.json',source)
        save_json(paths,run['provenance']/'input_inventory.json',inventory)
        for rel in source:
            paths.publish(run['provenance']/'code_snapshot'/rel,lambda f,rel=rel:f.write((paths.root/rel).read_bytes()))
        paths.publish(run['provenance']/'approved_plan.md',lambda f:f.write(paths._resolve(config['approved_plan']).read_bytes()))
        save_json(paths,run['provenance']/'approval.json',approval)
        save_json(paths,run['provenance']/'environment.json',dict(python=sys.version,platform=platform.platform(),
            packages={k:importlib.metadata.version(k) for k in ['numpy','pandas','pyarrow','scipy','shapely','pyproj','matplotlib']}))
        train=folds.loc[folds.outer_fold.isin([2,3,4]),'id'].tolist()
        cache_train=folds.loc[folds.outer_fold.ne(1),'id'].tolist()
        stage='pilot_fitting_and_geometry';tick=time.monotonic()
        base=fit_bases(counts,train,origins.cell,states);fit_seconds=time.monotonic()-tick
        kernel=ActualOriginKernel(geometry,tracks);records={7:[],30:[]}
        truth=donors.set_index(['id','origin_source_obs','horizon_days']).destination_cell_1.to_dict()
        for index,row in enumerate(roster.itertuples(index=False)):
            check();q=as_query(row)
            subset=donors[(donors.horizon_days==q.horizon)&donors.origin_cell_1.isin(neighbours(q.origin))&donors.fold.ne(1)]
            tick=time.monotonic();out,why,profile=kernel.classify(q,subset,cache_train,check=check)
            elapsed=time.monotonic()-tick
            record=dict(horizon_days=q.horizon,origin_cell_1=q.origin,id=q.id,origin_source_obs=q.source_obs,
                        seconds=elapsed,**profile)
            counts_out=pd.DataFrame(dict(donor_fold=subset.fold.to_numpy(),destination=out,reason=why)).value_counts().reset_index(name='pair_count')
            save_frame(paths,run['results']/f'query_{index:03d}_outcomes.csv',counts_out)
            audit_tick=time.monotonic()
            independent=audit_transfers(q,subset,tracks,geometry,out,why,maximum=8)
            record['independent_audit_seconds']=time.monotonic()-audit_tick
            timings.append(record)
            save_json(paths,run['results']/f'query_{index:03d}_timing.json',record)
            audits.extend(dict(query_index=index,**a) for a in independent)
            fitting_mask=subset.fold.isin([2,3,4]).to_numpy()
            reference,r=reference_distribution(out[fitting_mask],base.rows[(q.horizon,q.origin)],base.states)
            records[q.horizon].append(dict(query=row._asdict(),q=reference,fallback=r,
                truth=int(truth[(q.id,q.source_obs,q.horizon)])))
            print(json.dumps(dict(completed_query=index+1,horizon=q.horizon,cell=q.origin,
                                  donor_count=len(subset),seconds=round(elapsed,3),certified=profile['certified'])),flush=True)
            projection,total=geometry_projection(timings,workload,roster)
            if total>config['preparation_cap_seconds']:
                raise CapacityStop('measured_completed_strata_geometry_projection_exceeds_3600_seconds')
        # This is capacity instrumentation on the pilot roster, not a new CV experiment.
        stage='pilot_four_solver_capacity'
        for h in (7,30):
            tick=time.monotonic();ev=make_evaluator(records[h],base,check)
            refs=pilot_references(records[h],base,check);result=search(ev,refs,check)
            audit_search(result,ev)
            profile=dict(horizon_days=h,seconds=time.monotonic()-tick,queries=len(records[h]),
                full_metric_candidates=len(result['candidates']),optimizer_calls=len(result['optimizer_trace']),
                optimizer_starts=len(result['optimizer_runs']),selection_for_capacity_only=True,
                full_metric_seconds=sum(t['seconds'] for t in result['metric_timings']))
            profile['coefficient_seconds']=max(0.,profile['seconds']-profile['full_metric_seconds'])
            solver_profiles.append(profile)
            save_json(paths,run['results']/f'pilot_solver_{h}d.json',result)
        # Capacity of retained endpoint/global control fitting and the fixed 50,000-draw
        # ID/origin aggregation is measured without using predictive winners to tune E5.
        from data3001.modelling.baselines.local_endpoint_adaptive_s3_e2 import candidate_units,select_parameters
        tick=time.monotonic()
        control=candidate_units(base,counts,folds.loc[folds.outer_fold.eq(1),'id'].tolist())
        select_parameters(control);control_seconds=time.monotonic()-tick
        check();tick=time.monotonic();rng=np.random.Generator(np.random.PCG64(20261031))
        membership=counts[['id','origin_cell_1']].drop_duplicates()
        idindex={d:k for k,d in enumerate(sorted(folds.id))}
        groups=[np.array([idindex[d] for d in g.id],int) for _,g in membership.groupby('origin_cell_1')]
        for _ in range(100):
            check();draw=rng.exponential(size=(500,len(folds)))
            for ids in groups:
                normalized=draw[:,ids]/draw[:,ids].sum(axis=1,keepdims=True)
                # 10 rows x 3 metrics plus diagnostics; values are synthetic capacity
                # placeholders, not prediction results or model choices.
                normalized@np.ones((len(ids),36))
        multiplier_seconds=time.monotonic()-tick
        complete_cost=complete_projection(timings,workload,solver_profiles,control_seconds,multiplier_seconds,fit_seconds)
        if complete_cost['missing_work_strata']:raise CapacityStop('uncovered_horizon_coastal_work_strata')
        if not complete_cost['capacity_established']:raise CapacityStop('full_geometry_or_scoring_projection_exceeds_cap')
        # Independent scalar audit and old displacement control have not yet been timed
        # by the above kernels. A pass requires an explicit remaining-work reserve.
        remaining=3600-complete_cost['scoring_lower_projection_seconds']
        audit_seconds=sum(r.get('independent_audit_seconds',0.) for r in timings)
        audit_projection=(audit_seconds/max(1,len(audits)))*5000*2+600
        complete_cost['audit_report_and_remaining_control_reserve_seconds']=audit_projection
        if remaining<audit_projection:raise CapacityStop('audit_report_control_reserve_exceeds_remaining_scoring_cap')
        status='CAPACITY_PASSED';reason='bounded_projected_work_within_caps'
    except CapacityStop as exc:
        status='CAPACITY_FAILED';reason=str(exc)
    except Exception as exc:
        status='INTEGRITY_FAILED';reason=f'{type(exc).__name__}: {exc}'
        import traceback
        traceback.print_exc()
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,oldhandler)
    elapsed=time.monotonic()-start
    try:
        if len(workload) and len(roster):projection,_=geometry_projection(timings,workload,roster)
        unchanged=bool(source) and all(file_sha256(paths.root/p)==sha for p,sha in source.items())
        if source and not unchanged:status='INTEGRITY_FAILED';reason='source_changed_during_pilot'
        result=dict(run_id=run_id,status=status,reason=reason,capacity_passed=status=='CAPACITY_PASSED',
            full_experiment_started=False,scientific_accuracy_results_available=False,
            elapsed_seconds=elapsed,peak_rss_bytes=rss_bytes(),completed_queries=len(timings),
            frozen_queries=len(roster),geometry_projection=projection,complete_cost_projection=complete_cost,solver_profiles=solver_profiles,
            independent_transfer_checks=len(audits),final_test_access=False,canonical_train_reads=len(guard.read_ids),
            denied_accesses=guard.denied,meaning='Resource feasibility only; no model-quality conclusion.')
        save_json(paths,run['results']/'capacity.json',result)
        save_frame(paths,run['results']/'completed_query_timings.csv',pd.DataFrame(timings))
        save_frame(paths,run['results']/'independent_transfer_checks.csv',pd.DataFrame(audits))
        save_json(paths,run['provenance']/'opened_inputs.json',sorted(str(p.relative_to(paths.root)) for p in guard.opened_inputs))
        # A sealed completed capacity assessment is distinct from a completed experiment.
        _seal(paths,run,dict(capacity_assessment_completed=True,full_experiment_completed=False,
                             capacity_passed=status=='CAPACITY_PASSED',status=status,source_unchanged=unchanged))
        print(json.dumps(result,indent=2),flush=True)
    finally:guard.active=False
    return run,result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot',action='store_true',required=True)
    parser.parse_args();paths=project_paths();path=paths.root/'configs/actual_origin_displacement_s3_e5.json'
    if file_sha256(path)!=CONFIG_SHA:raise ValueError('Configuration differs from approved E5 v2')
    run_pilot(paths,json.loads(path.read_text()))


if __name__=='__main__':main()
