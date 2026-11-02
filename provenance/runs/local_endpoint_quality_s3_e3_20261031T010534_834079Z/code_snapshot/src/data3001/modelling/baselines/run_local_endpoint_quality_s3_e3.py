"""Isolated S3 E3 runner; anchor-first quality selection, audit and replay."""
import argparse
from datetime import datetime,timezone
import gc
import hashlib
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

from data3001.paths import project_paths,file_sha256
from data3001.modelling.common.runtime import save_frame,save_json,_seal,verified_run
from data3001.modelling.common.qualified_count_inputs import ExperimentGuard,load_inputs,read_frame,KEYS,EXIT
from data3001.modelling.baselines.spatial_borrowing_s3_e1_inputs import base_allowlist,source_hashes,budget_check
from data3001.modelling.baselines.local_endpoint_quality_s3_e3 import (
    MODELS,OUTPUT_MODELS,METRICS,IDENTITY,fit_bases,control_candidates,quality_candidates,select_controls,select_quality,add_ablations,forecasts,
    diagnostic_scores,score_units,summarize_units,attach_primary_weights,metric_columns,uncertainty,
)
from data3001.modelling.baselines.local_endpoint_quality_s3_e3_audit import independent_audit,audit_uncertainty
from data3001.modelling.baselines.local_endpoint_quality_s3_e3_report import write_report,geometry,freeze_roster

EXPECTED_CONFIG_SHA='a104411161b3795af0c9de6ac0081286f859f5c7ad97e1182c671c07f396bfbc'


def validate_config(config):
    if hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()!=EXPECTED_CONFIG_SHA:
        raise ValueError('Configuration differs from approved S3 E3')


def matrix_frame(base,vectors):
    return pd.concat([pd.DataFrame(dict(horizon_days=h,origin_cell_1=o,destination_cell_1=base.states[p>0],probability=p[p>0])) for (h,o),p in sorted(vectors.items())],ignore_index=True)


def allow_run(paths,guard,name):
    if Path(name).name!=name:raise ValueError('Unsafe run ID')
    for kind in ('results','provenance'):
        guard.input_files.update(p.resolve() for p in (paths.root/kind/'runs'/name).rglob('*') if p.is_file())
    verified_run(paths,name)
    return paths.root/'results/runs'/name


def regress_controls(paths,guard,run,config):
    previous=allow_run(paths,guard,config['frozen_s3_e2_run']);checked=[]
    for role in [f'outer_{k}' for k in range(5)]+['all_development_candidate']:
        for model in ('B2','Fixed','Adaptive','LocalEndpoint','LocalEndpointAdaptive'):
            name=f'matrices/{role}_{model}.parquet'
            pd.testing.assert_frame_equal(read_frame(run['results']/name),read_frame(previous/name),check_exact=False,rtol=0,atol=1e-12)
            checked.append(name)
    keys=['model',*KEYS]
    now=read_frame(run['results']/'heldout_scores.parquet');old=read_frame(previous/'heldout_scores.parquet')
    columns=[*keys,'pair_count','status',*METRICS,'region90_mass','primary_group_weight']
    for model in ('B2','Fixed','Adaptive','LocalEndpoint','LocalEndpointAdaptive'):
        a=now[now.model.eq(model)][columns].sort_values(keys).reset_index(drop=True)
        b=old[old.model.eq(model)][columns].sort_values(keys).reset_index(drop=True)
        pd.testing.assert_frame_equal(a,b,check_exact=False,rtol=0,atol=1e-12)
    new_selection=read_frame(run['results']/'selected_parameters.csv')
    old_selection=read_frame(previous/'selected_parameters.csv')
    keep=['role','horizon_days','model','parameter_a','parameter_gamma']
    a=new_selection[new_selection.model.isin(('Fixed','Adaptive','LocalEndpoint','LocalEndpointAdaptive'))][keep].sort_values(keep[:3]).reset_index(drop=True)
    b=old_selection[keep].sort_values(keep[:3]).reset_index(drop=True)
    pd.testing.assert_frame_equal(a,b,check_exact=False,rtol=0,atol=1e-12)
    return dict(passed=True,selected_parameters_reproduced=True,reference=config['frozen_s3_e2_run'],matrices=checked,per_case_weights_and_metrics_reproduced=True)


def execute(paths,config,run_id,pilot_run=None,replay_of=None,preflight=False):
    validate_config(config);start=time.monotonic()
    if file_sha256(paths._resolve(config['approved_plan']))!=config['approved_plan_sha256']:raise ValueError('Approved plan changed')
    run=paths.create_run(run_id,{**config,'pilot_run':pilot_run,'replay_of':replay_of,'preflight':preflight})
    allowed=base_allowlist(paths,config)
    guard=ExperimentGuard(paths,run,allowed);sys.addaudithook(guard)
    try:
        counts,folds,origins,destinations,reasons,inventory=load_inputs(paths,config)
        assert len(folds)==3224 and len(origins)==54
        for h,expected in [(7,(303288,385,4451,37)),(30,(268998,337,3974,37))]:
            c=counts[counts.horizon_days.eq(h)]
            assert (int(c.pair_count.sum()),c.id.nunique(),len(c[['id','origin_cell_1']].drop_duplicates()),c.origin_cell_1.nunique())==expected
        config_path=paths.root/'configs/local_endpoint_quality_s3_e3.json'
        inventory[config_path.relative_to(paths.root).as_posix()]=file_sha256(config_path)
        code=source_hashes(paths)
        for name,val in [('source_sha256.json',code),('input_inventory.json',inventory)]:save_json(paths,run['provenance']/name,val)
        for rel in code:
            paths.publish(run['provenance']/'code_snapshot'/rel,lambda out,rel=rel:out.write((paths.root/rel).read_bytes()))
        paths.publish(run['provenance']/'approved_plan.md',lambda out:out.write(paths._resolve(config['approved_plan']).read_bytes()))
        save_json(paths,run['results']/'config.json',config)
        save_json(paths,run['provenance']/'environment.json',dict(python=sys.version,platform=platform.platform(),packages={k:importlib.metadata.version(k) for k in ['numpy','pandas','pyarrow','shapely','pyproj','matplotlib']}))
        for name,df in [('counts_by_id.parquet',counts),('folds.csv',folds),('source_index.csv',origins),('destination_cells.csv',destinations),('qualification_reasons.csv',reasons)]:save_frame(paths,run['results']/name,df)
        states=[*destinations.cell,EXIT];bases={};roles={};predictions={};candidates=[];selections=[];searches=[];score_parts=[];supports=[];boundaries=[]
        def fit(role,train,held,outer=-1,inner=-1):
            base=fit_bases(counts,train,origins.cell,states);bases[role]=base
            roles[role]=dict(training_ids=list(map(int,train)),evaluation_ids=list(map(int,held)),outer_fold=outer,inner_fold=inner)
            b1=pd.concat([pd.DataFrame(dict(horizon_days=h,destination_cell_1=base.states[q>0],probability=q[q>0])) for h,q in base.references.items()],ignore_index=True)
            for name,df in [('b2.parquet',base.b2.transitions),('b1.parquet',b1),('support.csv',base.b2.support),('endpoint.parquet',matrix_frame(base,base.endpoint_rows)),('neighbour_support.csv',base.neighbour_support),('donor_quality.csv',base.donor_quality),('endpoint_evidence.parquet',base.endpoint_evidence)]:save_frame(paths,run['results']/'bases'/f'{role}_{name}',df)
            return base
        def tune(base,role,target,ids):
            table=control_candidates(base,counts,ids).assign(fit_role=role,selection_role=target);candidates.append(table);return table
        def select(parts,role,fit_roles):
            chosen,pool=select_controls(pd.concat(parts,ignore_index=True));pool['role']=role;searches.append(pool)
            quality_parts=[]
            for fr in fit_roles:
                table=quality_candidates(bases[fr],counts,roles[fr]['evaluation_ids'],chosen).assign(fit_role=fr,selection_role=role)
                candidates.append(table);quality_parts.append(table)
            quality,search=select_quality(pd.concat(quality_parts,ignore_index=True));search['role']=role;searches.append(search)
            chosen=add_ablations(pd.concat([chosen,quality],ignore_index=True));chosen['role']=role;selections.append(chosen)
            return chosen
        def export(base,role,chosen,ids=None,outer=-1):
            predictions[role]={}
            for model in OUTPUT_MODELS:
                vectors,support=forecasts(base,model,chosen);predictions[role][model]=vectors;supports.append(support.assign(role=role,outer_fold=outer))
                save_frame(paths,run['results']/'matrices'/f'{role}_{model}.parquet',matrix_frame(base,vectors))
                if ids is not None:
                    scores,bounds=diagnostic_scores(base,vectors,counts,ids,model)
                    score_parts.append(scores.assign(role=role,outer_fold=outer));boundaries.append(bounds.assign(role=role,outer_fold=outer))
        geoms=geometry(paths)
        save_json(paths,run['provenance']/'illustration_roster_freeze.json',dict(phase='before_outer_fitting',roster=freeze_roster(counts,geoms[2])))
        if preflight:
            tick=time.monotonic();train=folds.loc[~folds.outer_fold.isin([0,1]),'id'].tolist();ids=folds.loc[folds.outer_fold.eq(1),'id'].tolist()
            testbase=fit_bases(counts,train,origins.cell,states);table=control_candidates(testbase,counts,ids);anchor,_=select_controls(table);quality=quality_candidates(testbase,counts,ids,anchor)
            elapsed=time.monotonic()-tick;projected=elapsed*25+600
            assert table[['model','parameter_a','parameter_gamma']].drop_duplicates().shape[0]==148
            assert quality[['horizon_days','parameter_eta','parameter_rho']].drop_duplicates().shape[0]==18
            rss,size=budget_check(run,config,start,config['preflight_cap_seconds'])
            if projected>=config['compute_cap_seconds']:raise TimeoutError('Projected CV/audit exceeds approved cap')
            verification=dict(passed=True,preflight_only=True,first_role_seconds=elapsed,projected_complete_seconds=projected,
                elapsed_seconds=time.monotonic()-start,max_rss_bytes=rss,artifact_bytes=size,final_test_trajectories_read=0,
                canonical_trajectory_files_read=len(guard.read_ids),denied_operations=guard.denied)
            for p,d in {**inventory,**code}.items():assert file_sha256(paths.root/p)==d,p
            _seal(paths,run,verification);print(json.dumps(dict(run_id=run_id,**verification)),flush=True);return run
        if not pilot_run or not pilot_run.startswith('local_endpoint_quality_s3_e3_pilot_'):raise ValueError('A sealed E3 resource pilot is required')
        pilot=allow_run(paths,guard,pilot_run)
        pv=json.loads((paths.root/'provenance/runs'/pilot_run/'verification.json').read_text())
        assert pv['passed'] and pv['preflight_only'] and pv['projected_complete_seconds']<config['compute_cap_seconds']
        assert json.loads((paths.root/'provenance/runs'/pilot_run/'source_sha256.json').read_text())==code
        assert json.loads((pilot/'config.json').read_text())==config
        for outer in range(5):
            role=f'outer_{outer}';parts=[]
            for inner in range(5):
                if outer==inner:continue
                tick=time.monotonic();train=folds.loc[~folds.outer_fold.isin([outer,inner]),'id'].tolist();ids=folds.loc[folds.outer_fold.eq(inner),'id'].tolist()
                fit_role=f'outer_{outer}_inner_{inner}';base=fit(fit_role,train,ids,outer,inner);parts.append(tune(base,fit_role,role,ids))
                if outer==0 and inner==1:
                    projected=(time.monotonic()-tick)*25+600
                    save_json(paths,run['provenance']/'fitting_resource_check.json',dict(first_role_seconds=time.monotonic()-tick,projected_complete_seconds=projected))
                    if projected>=config['compute_cap_seconds']:raise TimeoutError('Projected CV exceeds approved cap')
                budget_check(run,config,start,config['compute_cap_seconds'])
            chosen=select(parts,role,[f'outer_{outer}_inner_{k}' for k in range(5) if k!=outer]);base=fit(role,folds.loc[folds.outer_fold.ne(outer),'id'].tolist(),folds.loc[folds.outer_fold.eq(outer),'id'].tolist(),outer)
            export(base,role,chosen,roles[role]['evaluation_ids'],outer)
            print(f'Completed outer {outer}: '+chosen[['horizon_days','model','parameter_a','parameter_gamma','parameter_eta','parameter_rho']].to_json(orient='records'),flush=True)
        scores=attach_primary_weights(pd.concat(score_parts,ignore_index=True).sort_values(['outer_fold','model',*KEYS]).reset_index(drop=True));units=score_units(scores)
        for name,df in [('heldout_scores.parquet',scores),('heldout_id_cells.parquet',units),('selected_outer_parameters.csv',pd.concat(selections,ignore_index=True))]:save_frame(paths,run['results']/name,df)
        save_frame(paths,run['results']/'outer_support.csv',pd.concat(supports,ignore_index=True))
        frozen_paths=[run['results']/k for k in ['heldout_scores.parquet','heldout_id_cells.parquet','selected_outer_parameters.csv','outer_support.csv']]+sorted((run['results']/'matrices').glob('*.parquet'))
        frozen={p.relative_to(paths.root).as_posix():file_sha256(p) for p in frozen_paths}
        save_json(paths,run['provenance']/'outer_freeze.json',dict(phase='before_all_development_tuning',sha256=frozen))
        final='all_development_candidate';parts=[tune(bases[f'outer_{k}'],f'outer_{k}',final,roles[f'outer_{k}']['evaluation_ids']) for k in range(5)]
        chosen=select(parts,final,[f'outer_{k}' for k in range(5)]);base=fit(final,folds.id.tolist(),[]);export(base,final,chosen)
        metrics=metric_columns(scores);summary=summarize_units(units,metrics=metrics);secondary=summarize_units(units,metrics=metrics,pair_weighted=True)
        print('Calculating paired whole-ID uncertainty',flush=True)
        draws,intervals,differences,decisions,meta=uncertainty(units,folds.id.tolist(),config['bootstrap_replicates'],config['bootstrap_seed'])
        all_candidates=pd.concat(candidates,ignore_index=True);all_support=pd.concat(supports,ignore_index=True);all_selected=pd.concat(selections,ignore_index=True)
        tables={'row_support.csv':all_support,'summary.csv':summary,'pair_weighted_summary.csv':secondary,
            'cell_summary.csv':summarize_units(units,('horizon_days','model','origin_cell_1'),metrics),
            'fold_summary.csv':summarize_units(units,('outer_fold','horizon_days','model'),metrics),
            'candidate_id_cells.parquet':all_candidates,'candidate_scores.csv':summarize_units(all_candidates,('fit_role',*IDENTITY)),
            'selected_parameters.csv':all_selected,'parameter_search.csv':pd.concat(searches,ignore_index=True),
            'budget_boundaries.parquet':pd.concat(boundaries,ignore_index=True),'bootstrap_draws.csv':draws,
            'bootstrap_intervals.csv':intervals,'paired_differences.csv':differences,'decisions.csv':decisions}
        for name,df in tables.items():save_frame(paths,run['results']/name,df)
        save_json(paths,run['results']/'fit_roles.json',roles);save_json(paths,run['results']/'multiplier_identity.json',meta)
        # Large candidate tables have now been exported; free them before independent audit.
        del all_candidates,candidates,tables,parts;gc.collect()
        print('Independently auditing ID sets, weights, every candidate and held-out scores',flush=True)
        verification=independent_audit(paths,run,counts,folds,roles,base.states)
        verification['uncertainty']=audit_uncertainty(run['results'],folds,config['bootstrap_replicates'],config['bootstrap_seed'])
        verification['control_regression']=regress_controls(paths,guard,run,config)
        write_report(paths,run,summary,secondary,differences,decisions,all_selected,base,predictions[final],all_support,verification)
        if replay_of:
            previous=allow_run(paths,guard,replay_of);compared=[]
            for p in sorted(run['results'].rglob('*')):
                if p.suffix in ('.csv','.parquet'):
                    pd.testing.assert_frame_equal(read_frame(p),read_frame(previous/p.relative_to(run['results'])),check_exact=False,rtol=0,atol=1e-12)
                    compared.append(p.relative_to(run['results']).as_posix())
            assert json.loads((previous/'multiplier_identity.json').read_text())==meta
            images=[]
            for p in sorted(run['results'].glob('*.png')):
                assert file_sha256(p)==file_sha256(previous/p.name),p.name
                images.append(p.name)
            verification['replay']=dict(passed=True,reference_run=replay_of,numerical_tables_compared=compared,identical_figures=images)
            previous_size=sum(p.stat().st_size for kind in ('results','provenance') for p in (paths.root/kind/'runs'/replay_of).rglob('*') if p.is_file())
            current_size=sum(p.stat().st_size for d in run.values() for p in d.rglob('*') if p.is_file())
            assert previous_size+current_size<=config['max_new_artifact_bytes']
        for p,d in {**inventory,**code,**frozen}.items():assert file_sha256(paths.root/p)==d,p
        rss,size=budget_check(run,config,start,config['compute_cap_seconds'])
        verification.update(elapsed_seconds=time.monotonic()-start,max_rss_bytes=rss,artifact_bytes=size,
            pilot_run=pilot_run,canonical_trajectory_files_read=len(guard.read_ids),final_test_trajectories_read=0,
            denied_operations=guard.denied,input_hashes_unchanged=True,code_hashes_unchanged=True,
            outer_predictions_unchanged_after_all_development_tuning=True,historical_outputs_used_for_fitting=False)
        _seal(paths,run,verification)
        print(json.dumps(dict(run_id=run_id,elapsed_seconds=verification['elapsed_seconds'],summary=summary[['horizon_days','model',*METRICS]].to_dict('records'),decisions=decisions.to_dict('records'))),flush=True)
        return run
    except Exception as error:
        save_json(paths,run['provenance']/'FAILED.json',dict(type=type(error).__name__,message=str(error),denied_operations=guard.denied));raise
    finally:guard.active=False


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pilot-run');p.add_argument('--preflight',action='store_true');p.add_argument('--replay-of');p.add_argument('--run-id');args=p.parse_args()
    paths=project_paths();config=json.loads((paths.root/'configs/local_endpoint_quality_s3_e3.json').read_text());validate_config(config)
    run_id=args.run_id or ('local_endpoint_quality_s3_e3_pilot_' if args.preflight else 'local_endpoint_quality_s3_e3_')+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    if not run_id.startswith('local_endpoint_quality_s3_e3_') or 'input_' in run_id:raise ValueError('Wrong experiment namespace')
    def timeout(*a):raise TimeoutError('Approved S3 execution cap reached')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(config['preflight_cap_seconds'] if args.preflight else config['compute_cap_seconds'])
    try:execute(paths,config,run_id,args.pilot_run,args.replay_of,args.preflight)
    finally:signal.alarm(0)

if __name__=='__main__':main()
