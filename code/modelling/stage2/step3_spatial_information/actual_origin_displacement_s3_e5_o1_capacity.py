"""Timing-only solver/control/multiplier workload and complete-cost accounting."""
import time,json
import numpy as np
import pandas as pd
from data3001.modelling.baselines.actual_origin_displacement_s3_e5 import primary_query_weights,pilot_references
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_selection import ForecastCase,CaseEvaluator,search
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_scoring import CachedCaseEvaluator
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_audit import audit_search
from data3001.modelling.baselines.local_endpoint_adaptive_s3_e2 import candidate_units,select_parameters
from data3001.modelling.baselines import spatial_borrowing_s3_e1 as spatial
from data3001.modelling.common.qualified_count_inputs import verify_file,read_frame
from data3001.paths import file_sha256


class TimedEvaluator:
    def __init__(self,ev):self.ev=ev;self.fixed=ev.fixed;self.objective_seconds=0.;self.calls=0
    def objective(self,theta):
        start=time.monotonic();result=self.ev.objective(theta);self.objective_seconds+=time.monotonic()-start;self.calls+=1;return result
    def metrics(self,*args):return self.ev.metrics(*args)


def capacity(t):
    t.snapshot('D_body');profiles=[]
    # Original fold-1 roster has the same fixed fitting context (folds 2,3,4).
    base=t.base_cache[(0,1)]
    for h in (7,30):
        t.check();records=[r for r in t.records[h] if r['base_role']==(0,1)]
        weights=primary_query_weights(pd.DataFrame([r['query'] for r in records]));cases=[]
        start=time.monotonic()
        for r,w in zip(records,weights):
            i=r['query']['origin_cell_1'];p=base.rows[(h,i)];q=r['q'];truth=r['truth']
            mask=(p>0)|(q>0)|(base.states==truth)|(base.states==-2)
            cases.append(ForecastCase(base.states[mask],p[mask],q[mask],truth,base.support_lookup[(h,i)]['normalised_support_ratio'],float(w),('pilot_inner_0_1',i)))
        old=CaseEvaluator(cases,t.check);ev=CachedCaseEvaluator(cases,t.check);coefficient_seconds=time.monotonic()-start
        refs=pilot_references(records,base,t.check)
        start=time.monotonic();old_result=search(old,refs,t.check);old_search=time.monotonic()-start
        timed=TimedEvaluator(ev);start=time.monotonic();result=search(timed,refs,t.check);new_search=time.monotonic()-start
        audit_search(result,ev)
        if old_result['memberships']!=result['memberships']:raise AssertionError('Cached scorer altered search pool')
        for x,y in zip(old_result['candidates'],result['candidates']):
            if (x['a'],x['gamma'])!=(y['a'],y['gamma']):raise AssertionError('Candidate ordering changed')
            for key in ('brier','region90_cells','region90_hit','region90_mass'):
                if abs(x[key]-y[key])>1e-12:raise AssertionError('Cached scorer changed '+key)
        for model in result['selections']:
            a=old_result['selections'][model];b=result['selections'][model]
            if (a['status'],a['selected']['a'],a['selected']['gamma'])!=(b['status'],b['selected']['a'],b['selected']['gamma']):raise AssertionError('Candidate choice changed')
        t.write(f'capacity_solver_{h}d',{**result,'capacity_only':True,'full_nested_cv_completed':False,'selection_is_not_model_adoption_evidence':True})
        profiles.append(dict(horizon_days=h,queries=len(cases),blocks=len(ev.keys),coefficient_seconds=coefficient_seconds,old_search_seconds=old_search,new_search_seconds=new_search,objective_seconds=timed.objective_seconds,objective_calls=timed.calls,metric_seconds=sum(x['seconds'] for x in result['metric_timings']),metric_candidates=len(result['candidates']),old_metric_seconds=sum(x['seconds'] for x in old_result['metric_timings']),all_four_solver_selections_identical=True,capacity_only=True))
    t.write('solver_capacity',profiles)
    # Time all six original controls, including the frozen E1 displacement counts.
    start=time.monotonic();units=candidate_units(base,t.counts,t.folds.loc[t.folds.outer_fold.eq(1),'id'].tolist());select_parameters(units)
    endpoint_control_seconds=time.monotonic()-start;t.check()
    root=t.paths._resolve(t.config['prepared_input']);transfer=root/'transfer_counts_by_id.parquet'
    t.guard.input_files.add(transfer.resolve())
    receipt=json.loads((t.paths.root/'provenance/runs'/root.name/'outputs.json').read_text())
    start=time.monotonic();verify_file(t.paths,transfer,receipt['output_sha256'],t.inventory);transfers=read_frame(transfer)
    donor_ids=t.folds.loc[t.folds.outer_fold.isin([2,3,4]),'id'].tolist()
    spatial_base=spatial.fit_bases(t.counts,transfers,donor_ids,t.origins.cell,[*t.destinations.cell,-2])
    spatial_units=spatial.candidate_units(spatial_base,t.counts,t.folds.loc[t.folds.outer_fold.eq(1),'id'].tolist());spatial.select_parameters(spatial_units)
    spatial_control_seconds=time.monotonic()-start;t.check()
    # Pure capacity arithmetic: 50,000 whole-ID multipliers and 72 columns.
    # Deterministic placeholders are NOT forecast evidence or uncertainty intervals.
    membership=t.counts[['id','origin_cell_1']].drop_duplicates();ids=sorted(t.folds.id);ix={d:j for j,d in enumerate(ids)}
    groups=[np.array([ix[x] for x in g.id],int) for _,g in membership.groupby('origin_cell_1')]
    values=[np.linspace(-1,1,len(g)*72).reshape(len(g),72) for g in groups]
    start=time.monotonic();rng=np.random.Generator(np.random.PCG64(20261031));checksum=0.
    for _ in range(100):
        t.check();draw=rng.exponential(size=(500,len(ids)));aggregate=np.zeros((500,72))
        for g,v in zip(groups,values):
            w=draw[:,g];w/=w.sum(axis=1,keepdims=True);aggregate+=w@v/len(groups)
        checksum+=float(aggregate.sum())
    multiplier_seconds=time.monotonic()-start
    controls=dict(endpoint_seconds=endpoint_control_seconds,spatial_control_seconds=spatial_control_seconds,includes_all_six_controls=True,overlap_computation_retained_as_conservative_cost=True,multiplier_seconds=multiplier_seconds,multiplier_replicates=50000,multiplier_columns=72,multiplier_values='deterministic timing placeholders, not forecasts',capacity_checksum=checksum)
    t.write('control_uncertainty_capacity',controls);t.write('complete_input_inventory',t.inventory,True)
    project(t,profiles,controls)
    start=time.monotonic()
    for rel,expected in t.inventory.items():
        t.check()
        if file_sha256(t.paths.root/rel)!=expected:raise AssertionError('Input changed during trial: '+rel)
    t.write('input_integrity_final',dict(verified_inputs=len(t.inventory),seconds=time.monotonic()-start,all_unchanged=True))


def project(t,profiles,controls):
    table=pd.DataFrame(t.timings);s=t.selected
    measured=table[(table.variant==s['variant'])&table.batch.eq(s['batch'])].drop_duplicates('query_index')
    strata=[];missing=[];central=0.;conservative=0.
    speed=t.parallel['effective_speedup']
    for (h,coast),g in t.workload.groupby(['horizon_days','coastal']):
        sample=measured[measured.horizon.eq(h)&measured.coastal.eq(coast)]
        if not len(sample):missing.append([int(h),bool(coast)]);continue
        mean=float(sample.seconds.sum()/sample.donors.sum());slow=float((sample.seconds/sample.donors).max());work=int(g.outer_query_donor_combinations.sum())
        typical=mean*work/speed;upper=2*slow*work/speed;central+=typical;conservative+=upper
        strata.append(dict(horizon=int(h),coastal=bool(coast),sample_queries=len(sample),sample_origins=int(sample.origin.nunique()),all_origins=len(g),query_donor_pairs=work,seconds_per_donor=mean,slowest_seconds_per_donor=slow,primary_central_seconds=typical,primary_conservative_seconds=upper,min_donors=int(sample.donors.min()),max_donors=int(sample.donors.max())))
    t.frame('geometry_projection',pd.DataFrame(strata))
    region=0.;objectives=0.;coefficient=0.
    for p in profiles:
        n=303288 if p['horizon_days']==7 else 268998
        region+=p['metric_seconds']/(p['queries']*p['metric_candidates'])*n*5*252
        # Full coefficients can have more role/origin blocks than the pilot.
        objectives+=p['objective_seconds']/max(1,p['objective_calls'])*6*22000*(4*54/max(1,p['blocks']))
        coefficient+=p['coefficient_seconds']/p['queries']*n*5
    controls_seconds=25*(controls['endpoint_seconds']+controls['spatial_control_seconds'])
    fits=t.validation['control_base_fit_seconds']/len(t.base_cache)*26
    audit=t.validation['scalar_audit_seconds']/t.validation['scalar_checks']*5000
    checkpoint=t.validation['checkpoint_seconds']/58*(303288+268998)
    score=region+objectives+coefficient+controls_seconds+fits+controls['multiplier_seconds']+audit+checkpoint
    setup=t.setup_seconds+s['setup_seconds']+s['context_seconds']
    # Primary + one fresh geometry replay + one fresh scoring replay.
    total=2*central+2*score+3*setup
    upper=2*conservative+4*score+6*setup
    sparse=sum(p.stat().st_size for p in t.run['results'].glob('checkpoint_*'))/58
    footprint=2*sparse*(303288+268998)
    result=dict(geometry_strata=strata,missing_strata=missing,measured_parallel_speedup=speed,primary_geometry_seconds=central,conservative_primary_geometry_seconds=conservative,region_seconds=region,objective_upper_budget_seconds=objectives,coefficient_seconds=coefficient,control_seconds=controls_seconds,fitting_seconds=fits,multiplier_seconds=controls['multiplier_seconds'],scalar_audit_seconds=audit,checkpoint_seconds=checkpoint,central_total_seconds=total,conservative_total_seconds=upper,includes_fresh_geometry_and_scoring_replay=True,projected_sparse_checkpoint_bytes_primary_plus_replay=footprint,query_candidate_upper_bound=721080360,scientific_accuracy_results_available=False,full_experiment_started=False,scope='conditional extrapolation from frozen pilot; complete-CV orchestration/report runtime remains unmeasured',capacity_established=False,remaining_unknowns=['complete orchestration and report-generation cost','timing variation across unmeasured origins within sampled coastal/horizon classes','actual full-case sparse support and coefficient block distribution'],reason='Measured components available; no full-run authorisation or complete execution proof')
    t.write('projection',result)
