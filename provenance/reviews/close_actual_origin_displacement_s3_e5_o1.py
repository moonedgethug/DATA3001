"""Close the crashed attempt from saved metadata only. Never restarts the trial."""
import json,csv,hashlib
from pathlib import Path
from datetime import datetime,timezone
from data3001.paths import project_paths,file_sha256
from data3001.modelling.common.runtime import save_json,_seal

paths=project_paths();run_id='actual_origin_disp_s3_e5_o1_20261031T131701_288861Z'
run={'results':paths.root/'results/runs'/run_id,'provenance':paths.root/'provenance/runs'/run_id}
p=run['results'];prov=run['provenance']
if (prov/'outputs.json').exists():raise FileExistsError('Attempt already sealed')
crash_path=Path('/Users/moonedgethug/Library/Logs/DiagnosticReports/python3.12-2026-11-01-005702.ips')
text=crash_path.read_text();crash=json.loads(text.split('\n',1)[1]);header=json.loads(text.split('\n',1)[0])
frames=[]
for th in crash['threads']:
 symbols=[f.get('symbol','') for f in th.get('frames',[])]
 if any('GEOSPreparedIntersects' in s for s in symbols):frames.append(dict(triggered=bool(th.get('triggered')),symbols=symbols))
start=(prov/'source_C_04.json').stat().st_mtime
end=datetime.strptime(crash['captureTime'],'%Y-%m-%d %H:%M:%S.%f %z').timestamp()
estimated=max(0.,end-start)
evidence=dict(incident=header['incident_id'],timestamp_local=header['timestamp'],exception=crash['exception'],termination=crash['termination'],worker_stacks=frames,source_report_sha256=file_sha256(crash_path),source_report_path=str(crash_path),stage='C_shared_prepared_geometry_thread_benchmark',stage_seconds_wallclock_estimate=estimated,stage_seconds_conservative_accounting=60.,installed=dict(shapely='2.2.0',geos='3.14.1',python='3.12.14'),upstream_issue='https://github.com/libgeos/geos/issues/825',interpretation='Shared prepared geometry is not thread-safe. Native stacks match the documented mutable intersector problem; no exact reproduction was attempted after failure.')
save_json(paths,prov/'native_crash_evidence.json',evidence)
budget=json.loads((p/'budget_04.json').read_text());used=budget['used_seconds'];used['C']=60.
rows=list(csv.DictReader((p/'timings_04.csv').open()));selected=[r for r in rows if r['variant']=='G3' and r['batch']=='2048']
work=list(csv.DictReader((p/'workload.csv').open()));strata=[];central=conservative=0.
for h in ('7','30'):
 for coast in ('False','True'):
  g=[r for r in selected if r['horizon']==h and r['coastal']==coast]
  count=sum(int(r['outer_query_donor_combinations']) for r in work if r['horizon_days']==h and r['coastal']==coast)
  mean=sum(float(r['seconds']) for r in g)/sum(int(r['donors']) for r in g);slow=max(float(r['seconds'])/int(r['donors']) for r in g)
  typical=mean*count;upper=2*slow*count;central+=typical;conservative+=upper
  strata.append(dict(horizon=int(h),coastal=coast=='True',calibration_queries=len(g),measured_origins=1,query_donor_pairs=count,primary_mean_rate_seconds=typical,primary_slow_rate_plus_reserve_seconds=upper))
geo=dict(scope='geometry only; eight calibration queries, no held-out engineering validation',strata=strata,workers=1,primary_geometry_seconds=central,primary_geometry_reserve_seconds=conservative,geometry_with_fresh_replay_seconds=2*central,geometry_with_replay_reserve_seconds=2*conservative,full_experiment_seconds=None,confidence_interval=False,statistical_lower_bound=False,missing_costs=['candidate Brier and 90% region scoring','controls and full fit roles','uncertainty','independent audit','checkpoint I/O and full orchestration/reporting'],parallel_speedup_assumed=False)
save_json(paths,p/'geometry_only_projection.json',geo)
validation=dict(status='INCOMPLETE',calibration_queries=8,in_process_full_pair_comparisons_per_variant_batch=sum(int(r['donors']) for r in selected),variant_batch_comparisons=6,all_completed_calibration_comparisons_matched=True,independent_real_scalar_checks_completed=0,remaining_engineering_validation_queries=50,optimized_raw_arrays_persisted=False,real_data_region_and_selection_parity_completed=False,limitation='Completed benchmark records are written only after in-process array equality assertions. Optimized arrays remained in RAM and were lost; no independent saved-array comparison is claimed.')
save_json(paths,p/'validation.json',validation)
paths.publish(p/'timings.csv',lambda f:f.write((p/'timings_04.csv').read_bytes()))
trial=dict(run_id=run_id,status='CAPACITY_NOT_ESTABLISHED',reason='native_GE0S_SIGSEGV_during_shared_prepared_geometry_thread_benchmark',used_seconds=used,total_execution_seconds_conservative=sum(used.values()),estimated_actual_execution_seconds=used['A']+used['B']+estimated,stage_C_monotonic_end_not_flushed=True,stage_C_wallclock_estimate=estimated,stage_C_budget_charge_seconds=60.,peak_rss_bytes=None,resource_checks_before_crash_passed=True,full_experiment_started=False,scientific_accuracy_results_available=False,final_test_access=False,read_guard_active=True,final_access_counters_flushed=False,canonical_reads=None,denied_accesses=None,restarted_after_failure=False,metadata_recovered_after_native_crash=True)
save_json(paths,p/'trial.json',trial)
# This receipt closes exactly the authorised bounded attempt, not the research stage.
close=dict(run_id=run_id,status=trial['status'],full_experiment_started=False,attempt_closed=True,new_real_data_attempt_requires_review=True,approved_plan_sha256='ebc4efbcb369c947e31a23e5544348762c3b2a9cf3a3e9f3c56c3af0c74c3f4c',stop_rule='No extra attempt, model grid or new geometry variant is added after a failure.')
closepath=paths.root/'provenance/reviews/actual_origin_displacement_s3_e5_o1_execution_closed.json'
closepath.write_text(json.dumps(close,indent=2)+'\n')
_seal(paths,run,dict(capacity_assessment_closed=True,full_experiment_completed=False,capacity_established=False,recovered_after_native_crash=True,final_counter_log_complete=False))
print(json.dumps(dict(trial=trial,validation=validation,geometry_only_projection=geo),indent=2))
