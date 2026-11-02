"""Source-backed capacity review; no forecast experiment is executed here."""
import argparse,json,html
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from data3001.paths import project_paths,file_sha256
from data3001.modelling.common.runtime import save_json,_seal


def markdown_table(frame):
    values=frame.round(5).astype(str)
    clean=lambda x:str(x).replace('|','\\|').replace('\n',' ')
    lines=['| '+' | '.join(map(clean,frame.columns))+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    lines.extend('| '+' | '.join(map(clean,row))+' |' for row in values.itertuples(index=False,name=None))
    return '\n'.join(lines)


def run_report(run_id):
    paths=project_paths();root=paths.root/'results/runs'/run_id
    receipt=paths.root/'provenance/runs'/run_id/'outputs.json'
    sealed=json.loads(receipt.read_text())
    for rel,sha in sealed['output_sha256'].items():
        if file_sha256(paths.root/rel)!=sha:raise ValueError('Trial output changed: '+rel)
    read=lambda name:json.loads((root/(name+'.json')).read_text()) if (root/(name+'.json')).exists() else None
    trial=read('trial');times=pd.read_csv(root/'timings.csv');selection=read('configuration_freeze');projection=read('projection');validation=read('validation');parallel=read('parallel');geometry_only=read('geometry_only_projection')
    review_id='actual_origin_disp_s3_e5_o1_review_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run=paths.create_run(review_id,dict(experiment='E5_O1_capacity_review',source_run=run_id,full_experiment_started=False))
    profiles=[json.loads(p.read_text()) for p in sorted(root.glob('profile_*.json'))]
    group={'Whole-path land certificates':0.,'Hourly land points':0.,'Hourly land segments':0.,'Other / overhead':0.}
    for r in profiles:
        used=0.
        for k,v in r['exclusive'].items():
            key=None
            if k.startswith('certificates:sh.intersects:'):key='Whole-path land certificates'
            elif k in ('classify:sh.intersects_xy:g.high','classify:sh.intersects_xy:g.intermediate'):key='Hourly land points'
            elif k in ('classify:sh.intersects:g.high_D','classify:sh.intersects:g.intermediate_D'):key='Hourly land segments'
            if key:group[key]+=v['seconds'];used+=v['seconds']
        group['Other / overhead']+=r['instrumented_seconds']-used
    paired=None
    if selection:
        s=selection['selected'];a=times[times.variant.eq('reference')].drop_duplicates('query_index')
        b=times[times.variant.eq(s['variant'])&times.batch.eq(s['batch'])].drop_duplicates('query_index')
        paired=a[['query_index','horizon','coastal','seconds']].merge(b[['query_index','seconds']],on='query_index',suffixes=('_old','_new'))
        paired['speedup']=paired.seconds_old/paired.seconds_new
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    names=list(group);values=np.array(list(group.values()))
    axes[0].barh(names,values,color=['#26547c','#ef8354','#4c956c','#94a3b8']);axes[0].invert_yaxis();axes[0].set_xlabel('Seconds across eight instrumented calibration queries');axes[0].set_title('Where the reference spends time')
    for j,x in enumerate(values):axes[0].text(x+.5,j,f'{x:.1f}s ({100*x/values.sum():.1f}%)',va='center',fontsize=9)
    axes[0].set_xlim(0,max(values)*1.35)
    if paired is not None:
        x=np.arange(len(paired));axes[1].bar(x-.2,paired.seconds_old,.4,label='Original',color='#94a3b8');axes[1].bar(x+.2,paired.seconds_new,.4,label=s['variant'],color='#26547c')
        axes[1].set_xticks(x,[f"{int(r.horizon)}d\n{'coast' if r.coastal else 'offshore'}\nQ{int(r.query_index)}" for r in paired.itertuples()],fontsize=8)
        axes[1].set_ylabel('Seconds per complete query');axes[1].legend();axes[1].set_title('Paired, uninstrumented geometry calls')
    else:
        a=times.groupby(['variant','batch']).seconds.agg(['sum','count']).reset_index()
        axes[1].bar(np.arange(len(a)),a['sum']/a['count'],color='#26547c');axes[1].set_xticks(np.arange(len(a)),[f'{r.variant}\n{r.batch}' for r in a.itertuples()]);axes[1].set_title('Available timings; calibration may be incomplete');axes[1].set_ylabel('Mean completed-query seconds')
    fig.suptitle('E5 O1: exact computation capacity, not prediction quality',fontsize=14)
    fig.savefig(run['results']/'geometry_capacity.png',dpi=160);fig.savefig(run['results']/'geometry_capacity.svg');plt.close(fig)
    summary=dict(source_run=run_id,trial_status=trial['status'],seconds=trial['used_seconds'],reference_profile_seconds=group,selection=selection,validation=validation,parallel=parallel,projection=projection,geometry_only_projection=geometry_only,full_experiment_started=False)
    if paired is not None:
        summary['paired']=dict(queries=len(paired),old_seconds=float(paired.seconds_old.sum()),new_seconds=float(paired.seconds_new.sum()),aggregate_speedup=float(paired.seconds_old.sum()/paired.seconds_new.sum()),minimum_speedup=float(paired.speedup.min()),maximum_speedup=float(paired.speedup.max()))
        paired.to_csv(run['results']/'paired_timings.csv',index=False)
    save_json(paths,run['results']/'summary.json',summary)
    lines=['# Step 3 E5 O1: optimisation trial', '', f"Trial status: **{trial['status']}**. Full experiment: **not started**.", '',f"Source: `{run_id}`. This review contains computational evidence only; it does not establish improved Brier, hit rate or prediction-region size.",'','## Execution budget','',markdown_table(pd.DataFrame([dict(stage=k,seconds=v,minutes=v/60) for k,v in trial['used_seconds'].items()])),'','## Bottleneck and acceleration','',markdown_table(pd.DataFrame([dict(component=k,seconds=v) for k,v in group.items()]))]
    if paired is not None:lines+=['',markdown_table(paired),'',f"Aggregate paired acceleration: {summary['paired']['aggregate_speedup']:.3f}x. This excludes cold setup and includes only matched complete calls; whole-run projections include other measured components."]
    lines+=['','## Integrity and limitations','',f"Validation evidence (extended validation incomplete): `{json.dumps(validation)}`.",'',f"Serial / two-worker comparison: `{json.dumps(parallel)}`.",'','True starts, all donor pairs, full-path semantics, failed-mass B2 return and fixed 90% regions are retained. A subset of query starts is used for engineering capacity testing only; the full scientific case population is unchanged. Development-only read guards were enabled. The final access-counter log was not flushed after the native crash.']
    if projection:
        lines+=['','## Conditional complete-run estimate','',f"Measured-component central projection including fresh geometry and scoring replay: **{projection['central_total_seconds']/3600:.2f} hours**. Conservative projection: **{projection['conservative_total_seconds']/3600:.2f} hours**.",'',f"Projected sparse checkpoints, primary plus replay: {projection['projected_sparse_checkpoint_bytes_primary_plus_replay']/2**30:.2f} GiB.",'','These are extrapolations, not completion promises. Remaining unknowns: '+ '; '.join(projection['remaining_unknowns'])+'. Full-run authorisation remains with the user.']
    else:lines+=['','The complete-run projection was not established. Unmeasured stages are not assigned zero cost.']
    if geometry_only:
        lines+=['','## Geometry-only scale warning','',f"Serial primary geometry extrapolation from eight calibration queries: **{geometry_only['primary_geometry_seconds']/3600:.1f} hours** at pooled mean rates, or **{geometry_only['primary_geometry_reserve_seconds']/3600:.1f} hours** at the slowest sampled rates plus a factor-two reserve.",'',f"Including one fresh geometry replay: **{geometry_only['geometry_with_fresh_replay_seconds']/3600:.1f} / {geometry_only['geometry_with_replay_reserve_seconds']/3600:.1f} hours**. Scoring, controls, uncertainty, complete audit and I/O are unmeasured and excluded. These values are neither a confidence interval nor a proven lower bound; engineering validation did not complete.",'','## Native concurrency failure','', 'The process received SIGSEGV while two workers called GEOSPreparedIntersects_r on shared prepared land geometry. The faulting stack includes MCIndexSegmentSetMutualIntersector and SegmentIntersectionDetector. Python-level read-only arrays do not make these GEOS objects thread-safe. This is an engineering design error in the shared-object concurrency experiment. The stack is consistent with the upstream documented limitation: [GEOS issue 825](https://github.com/libgeos/geos/issues/825). No post-failure replay was attempted. The approved stop rule ended the bounded attempt.','', 'All eight calibration queries matched the reference during execution, covering 355,418 donor pairs per variant/batch. Optimised arrays had not yet been persisted; no independent saved-array parity audit is claimed. The remaining 50 engineering queries, 5,000-scalar-transfer target, real-data scorer/selection parity and complete-run capacity gate remain unfinished.']
    lines+=['','## Source artifacts','',f'- [Trial receipt]({root}/trial.json)',f'- [Raw timings]({root}/timings.csv)',f'- [Frozen roster]({root}/roster.csv)',f'- [Sealed outputs]({receipt})']
    report='\n'.join(lines)+'\n';(run['results']/'REPORT.md').write_text(report)
    content='<h1>E5 O1 · Geometry capacity review</h1><p><strong>Full experiment has not started.</strong> These measurements describe exact engineering acceleration, not prediction quality.</p><img alt="Geometry timing comparison" src="geometry_capacity.png">'
    content+='<h2>Execution</h2>'+pd.DataFrame([dict(stage=k,seconds=round(v,2),minutes=round(v/60,2)) for k,v in trial['used_seconds'].items()]).to_html(index=False)
    if paired is not None:content+=f"<p>Paired aggregate speedup: <strong>{summary['paired']['aggregate_speedup']:.2f}×</strong>.</p>"+paired.round(4).to_html(index=False)
    if projection:content+=f"<p>Conditional complete-run projection, including replay: <strong>{projection['central_total_seconds']/3600:.2f} h central; {projection['conservative_total_seconds']/3600:.2f} h conservative</strong>. Full orchestration and reporting costs remain unmeasured; this is not a guaranteed completion time.</p>"
    if geometry_only:
        content+=f"<h2>Incomplete trial: native concurrency crash</h2><p>The shared prepared-geometry thread benchmark crashed inside GEOS. Extended validation and scoring capacity measurements did not complete. No retry or full experiment was launched.</p><p><strong>Geometry only:</strong> about {geometry_only['primary_geometry_seconds']/3600:.0f} h at calibration mean rates; {geometry_only['primary_geometry_reserve_seconds']/3600:.0f} h with slow-rate reserve. Including fresh geometry replay: {geometry_only['geometry_with_fresh_replay_seconds']/3600:.0f} / {geometry_only['geometry_with_replay_reserve_seconds']/3600:.0f} h. These are coarse scale diagnostics, not complete-run estimates or confidence bounds.</p>"
    content+='<h2>Audit</h2><pre>'+html.escape(json.dumps(validation,indent=2))+'</pre><p><a href="REPORT.md">Detailed English report</a> · <a href="summary.json">Machine-readable evidence</a></p>'
    page='<!doctype html><html lang="en"><meta charset="utf-8"><title>E5 O1 capacity</title><style>body{max-width:1200px;margin:36px auto;padding:0 24px;font:16px/1.6 system-ui;color:#172536;background:#f7f9fc}img{width:100%;background:white}table{border-collapse:collapse;background:white;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #d5dce6;text-align:right}h1{font-size:32px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eaf0f6;padding:18px}</style>'+content+'</html>'
    (run['results']/'review.html').write_text(page)
    _seal(paths,run,dict(source_receipt_verified=True,source_files=len(sealed['output_sha256']),full_experiment_started=False))
    link=paths.root/'results/deliverables/actual_origin_displacement_s3_e5_o1'
    if link.exists() or link.is_symlink():raise FileExistsError('Refuse to replace existing deliverable')
    link.symlink_to(run['results']);print(json.dumps(dict(review_run=review_id,path=str(run['results']/'review.html'),summary=summary),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_id');run_report(p.parse_args().run_id)
