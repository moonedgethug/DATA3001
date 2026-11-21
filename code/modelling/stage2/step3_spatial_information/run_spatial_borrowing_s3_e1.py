"""Isolated S3 benchmark runner; frozen roles, finite grids, audits and replay."""
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
from data3001.modelling.baselines.spatial_borrowing_s3_e1 import (
    MODELS,METRICS,IDENTITY,fit_bases,candidate_units,select_parameters,forecasts,
    diagnostic_scores,score_units,summarize_units,attach_primary_weights,metric_columns,uncertainty,
)
from data3001.modelling.baselines.spatial_borrowing_s3_e1_audit import independent_audit,audit_preparation,audit_uncertainty
from data3001.modelling.baselines.spatial_borrowing_s3_e1_report import write_report

EXPECTED_CONFIG_SHA='97b92d58fb938c0690bb3608396ffcc969b8d2bc1eebbd78a9d1b1334d2f6a0e'


def validate_config(config):
    if hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()!=EXPECTED_CONFIG_SHA:
        raise ValueError('Configuration differs from approved S3 E1')


def matrix_frame(base,vectors):
    return pd.concat([pd.DataFrame(dict(horizon_days=h,origin_cell_1=o,destination_cell_1=base.states[p>0],probability=p[p>0])) for (h,o),p in sorted(vectors.items())],ignore_index=True)


def allow_run(paths,guard,name):
    if Path(name).name!=name:raise ValueError('Unsafe run ID')
    for kind in ('results','provenance'):
        guard.input_files.update(p.resolve() for p in (paths.root/kind/'runs'/name).rglob('*') if p.is_file())
    verified_run(paths,name)
    return paths.root/'results/runs'/name


def regress_controls(paths,guard,run,config):
    previous=allow_run(paths,guard,config['frozen_e4_run']);checked=[]
    for role in [f'outer_{k}' for k in range(5)]+['all_development_candidate']:
        for model in ('B2','Fixed'):
            name=f'matrices/{role}_{model}.parquet'
            pd.testing.assert_frame_equal(read_frame(run['results']/name),read_frame(previous/name),check_exact=False,rtol=0,atol=1e-12)
            checked.append(name)
    keys=['model',*KEYS]
    now=read_frame(run['results']/'heldout_scores.parquet');old=read_frame(previous/'heldout_scores.parquet')
    columns=[*keys,'pair_count','status',*METRICS,'region90_mass','primary_group_weight']
    for model in ('B2','Fixed'):
        a=now[now.model.eq(model)][columns].sort_values(keys).reset_index(drop=True)
        b=old[old.model.eq(model)][columns].sort_values(keys).reset_index(drop=True)
        pd.testing.assert_frame_equal(a,b,check_exact=False,rtol=0,atol=1e-12)
    return dict(passed=True,reference=config['frozen_e4_run'],matrices=checked,per_case_weights_and_metrics_reproduced=True)


def execute(paths,config,run_id,input_run,replay_of=None):
    validate_config(config);start=time.monotonic()
    if file_sha256(paths._resolve(config['approved_plan']))!=config['approved_plan_sha256']:raise ValueError('Approved plan changed')
    if not input_run.startswith('spatial_borrowing_s3_e1_input_') or 'pilot' in input_run:raise ValueError('A complete S3 prepared input is required')
    run=paths.create_run(run_id,{**config,'input_run':input_run,'replay_of':replay_of})
    allowed=base_allowlist(paths,config)
    allowed += [p for kind in ('results','provenance') for p in (paths.root/kind/'runs'/input_run).rglob('*') if p.is_file()]
    guard=ExperimentGuard(paths,run,allowed);sys.addaudithook(guard)
    try:
        input_root=allow_run(paths,guard,input_run)
        prep=json.loads((paths.root/'provenance/runs'/input_run/'verification.json').read_text())
        assert not prep['preflight_only'] and prep['final_test_trajectories_read']==0
        prep_code=json.loads((paths.root/'provenance/runs'/input_run/'source_sha256.json').read_text())
        for p,digest in prep_code.items():assert file_sha256(paths.root/p)==digest,p
        counts,folds,origins,destinations,reasons,inventory=load_inputs(paths,config)
        transfers=read_frame(input_root/'transfer_counts_by_id.parquet')
        pd.testing.assert_frame_equal(counts,read_frame(input_root/'counts_by_id.parquet'),check_exact=True)
        assert len(folds)==3224 and len(origins)==54
        for h,expected in [(7,(303288,385,4451,37)),(30,(268998,337,3974,37))]:
            c=counts[counts.horizon_days.eq(h)]
            assert (int(c.pair_count.sum()),c.id.nunique(),len(c[['id','origin_cell_1']].drop_duplicates()),c.origin_cell_1.nunique())==expected
        for p in [input_root/'transfer_counts_by_id.parquet',paths.root/'provenance/runs'/input_run/'outputs.json',paths.root/'configs/spatial_borrowing_s3_e1.json']:
            inventory[p.relative_to(paths.root).as_posix()]=file_sha256(p)
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
            base=fit_bases(counts,transfers,train,origins.cell,states);bases[role]=base
            roles[role]=dict(training_ids=list(map(int,train)),evaluation_ids=list(map(int,held)),outer_fold=outer,inner_fold=inner)
            b1=pd.concat([pd.DataFrame(dict(horizon_days=h,destination_cell_1=base.states[q>0],probability=q[q>0])) for h,q in base.references.items()],ignore_index=True)
            for name,df in [('b2.parquet',base.b2.transitions),('b1.parquet',b1),('support.csv',base.b2.support),('endpoint.parquet',matrix_frame(base,base.endpoint_rows)),('displacement.parquet',matrix_frame(base,base.displacement_rows)),('neighbour_support.csv',base.neighbour_support)]:save_frame(paths,run['results']/'bases'/f'{role}_{name}',df)
            return base
        def tune(base,role,target,ids):
            table=candidate_units(base,counts,ids).assign(fit_role=role,selection_role=target);candidates.append(table);return table
        def select(parts,role):
            chosen,pool=select_parameters(pd.concat(parts,ignore_index=True));chosen['role']=role;pool['role']=role
            selections.append(chosen);searches.append(pool);return chosen
        def export(base,role,chosen,ids=None,outer=-1):
            predictions[role]={}
            for model in MODELS:
                vectors,support=forecasts(base,model,chosen);predictions[role][model]=vectors;supports.append(support.assign(role=role,outer_fold=outer))
                save_frame(paths,run['results']/'matrices'/f'{role}_{model}.parquet',matrix_frame(base,vectors))
                if ids is not None:
                    scores,bounds=diagnostic_scores(base,vectors,counts,ids,model)
                    score_parts.append(scores.assign(role=role,outer_fold=outer));boundaries.append(bounds.assign(role=role,outer_fold=outer))
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
            chosen=select(parts,role);base=fit(role,folds.loc[folds.outer_fold.ne(outer),'id'].tolist(),folds.loc[folds.outer_fold.eq(outer),'id'].tolist(),outer)
            export(base,role,chosen,roles[role]['evaluation_ids'],outer)
            print(f'Completed outer {outer}: '+chosen[['horizon_days','model','parameter_a']].to_json(orient='records'),flush=True)
        scores=attach_primary_weights(pd.concat(score_parts,ignore_index=True).sort_values(['outer_fold','model',*KEYS]).reset_index(drop=True));units=score_units(scores)
        for name,df in [('heldout_scores.parquet',scores),('heldout_id_cells.parquet',units),('selected_outer_parameters.csv',pd.concat(selections,ignore_index=True))]:save_frame(paths,run['results']/name,df)
        frozen_paths=[run['results']/k for k in ['heldout_scores.parquet','heldout_id_cells.parquet','selected_outer_parameters.csv']]+sorted((run['results']/'matrices').glob('*.parquet'))
        frozen={p.relative_to(paths.root).as_posix():file_sha256(p) for p in frozen_paths}
        save_json(paths,run['provenance']/'outer_freeze.json',dict(phase='before_all_development_tuning',sha256=frozen))
        final='all_development_candidate';parts=[tune(bases[f'outer_{k}'],f'outer_{k}',final,roles[f'outer_{k}']['evaluation_ids']) for k in range(5)]
        chosen=select(parts,final);base=fit(final,folds.id.tolist(),[]);export(base,final,chosen)
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
        print('Independently auditing path examples, every candidate and held-out scores',flush=True)
        verification=independent_audit(paths,run,counts,transfers,folds,roles,base.states)
        verification['path_and_ledger_audit']=audit_preparation(paths,input_root,base.states)
        verification['uncertainty']=audit_uncertainty(run['results'],folds,config['bootstrap_replicates'],config['bootstrap_seed'])
        verification['control_regression']=regress_controls(paths,guard,run,config)
        write_report(paths,run,input_root,summary,secondary,differences,decisions,all_selected,base,predictions[final],all_support,verification)
        if replay_of:
            previous=allow_run(paths,guard,replay_of);compared=[]
            for p in sorted(run['results'].rglob('*')):
                if p.suffix in ('.csv','.parquet'):
                    pd.testing.assert_frame_equal(read_frame(p),read_frame(previous/p.relative_to(run['results'])),check_exact=False,rtol=0,atol=1e-12)
                    compared.append(p.relative_to(run['results']).as_posix())
            assert json.loads((previous/'multiplier_identity.json').read_text())==meta
            verification['replay']=dict(passed=True,reference_run=replay_of,numerical_tables_compared=compared)
        for p,d in {**inventory,**code,**frozen}.items():assert file_sha256(paths.root/p)==d,p
        rss,size=budget_check(run,config,start,config['compute_cap_seconds'])
        verification.update(elapsed_seconds=time.monotonic()-start,max_rss_bytes=rss,artifact_bytes=size,
            input_run=input_run,canonical_trajectory_files_read=len(guard.read_ids),final_test_trajectories_read=0,
            denied_operations=guard.denied,input_hashes_unchanged=True,code_hashes_unchanged=True,
            outer_predictions_unchanged_after_all_development_tuning=True,historical_outputs_used_for_fitting=False)
        _seal(paths,run,verification)
        print(json.dumps(dict(run_id=run_id,elapsed_seconds=verification['elapsed_seconds'],summary=summary[['horizon_days','model',*METRICS]].to_dict('records'),decisions=decisions.to_dict('records'))),flush=True)
        return run
    except Exception as error:
        save_json(paths,run['provenance']/'FAILED.json',dict(type=type(error).__name__,message=str(error),denied_operations=guard.denied));raise
    finally:guard.active=False


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-run',required=True);p.add_argument('--replay-of');p.add_argument('--run-id');args=p.parse_args()
    paths=project_paths();config=json.loads((paths.root/'configs/spatial_borrowing_s3_e1.json').read_text());validate_config(config)
    run_id=args.run_id or 'spatial_borrowing_s3_e1_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    if not run_id.startswith('spatial_borrowing_s3_e1_') or 'input_' in run_id:raise ValueError('Wrong experiment namespace')
    def timeout(*a):raise TimeoutError('Approved S3 execution cap reached')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(config['compute_cap_seconds'])
    try:execute(paths,config,run_id,args.input_run,args.replay_of)
    finally:signal.alarm(0)

if __name__=='__main__':main()
