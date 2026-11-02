"""Approved E1 independent shrinkage experiment with guarded, sealed output."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time

import numpy as np
import pandas as pd

from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import save_frame, save_json, _seal
from data3001.modelling.common.qualified_count_inputs import (
    ExperimentGuard, load_inputs, read_frame, run_input_paths, verify_file,
    HORIZONS, KEYS, EXIT, TOLERANCE,
)
from data3001.modelling.baselines.adaptive_b2_b1 import (
    GRID, MODELS, fit_bases, coefficient_rows, candidate_scores, select_parameters,
    forecasts, evaluate, summarize_scores, paired_bootstrap,
)
from data3001.modelling.baselines.adaptive_b2_b1_audit import independent_audit
from data3001.modelling.baselines.adaptive_b2_b1_report import write_report


def validate_config(config):
    fixed = {'experiment':'adaptive_b2_b1','plan_version':'E1',
             'approved_plan':'docs/adaptive_b2_b1_plan.md',
             'dataset_release':'per-drifter-cleaned-20261017-v7',
             'contract_sha256':'6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446',
             'grid_degrees':1,'target':'stopped','scenario':'pooled','departure_seasons':'annual_pooled',
             'origin_population':'R','horizons_days':[7,30],'tolerance_hours':0,
             'predictors':['origin_cell_1'],'weighting':'equal_eligible_pairs',
             'models':list(MODELS),'parameter_grid':list(GRID),
             'adaptive_support':'training_pair_count','adaptive_scale':'fitting_median_positive_row_count',
             'primary_metric':'standard_multiclass_brier','unsupported_score':'common_B2_mask_missing',
             'outer_folds':5,'inner_folds':4,'bootstrap_replicates':200,'bootstrap_seed':20261030,
             'region_level':.9,'mass_tolerance':TOLERANCE,'tie_tolerance':TOLERANCE,
             'compute_cap_seconds':1800,'final_test_access':False,
             'counts_path':'results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet',
             'folds_path':'results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv',
             'frozen_s1_run':'empirical_b2_20261029T121555_976173Z',
             'source_assets':['english_contract','state_index','release_R','transport_D','land_mask_intermediate']}
    if config != fixed:
        raise ValueError('Configuration differs from approved E1 settings')


def source_hashes(paths):
    files={Path(m.__file__).resolve() for name,m in list(sys.modules.items())
           if name.startswith('data3001') and getattr(m,'__file__',None) and str(m.__file__).endswith('.py')}
    files.add(Path(__file__).resolve())
    return {p.relative_to(paths.root).as_posix():file_sha256(p) for p in sorted(files)}


def matrix_frame(base, vectors):
    parts=[]
    for (h,origin),p in sorted(vectors.items()):
        active=p>0
        parts.append(pd.DataFrame({'horizon_days':h,'origin_cell_1':origin,
                                   'destination_cell_1':base.states[active],'probability':p[active]}))
    return pd.concat(parts,ignore_index=True)


def verify_sealed_run(paths,run_id,guard):
    """Read a prior run only after fitting, for explicit post-computation audit."""
    if Path(run_id).name != run_id or not run_id:
        raise ValueError('Unsafe audit run ID')
    receipt_path=paths.root/'provenance/runs'/run_id/'outputs.json'
    guard.input_files.add(receipt_path.resolve())
    receipt=json.loads(receipt_path.read_text())
    if receipt.get('completed') is not True or receipt.get('final_test_access') is not False:
        raise ValueError('Audit reference is not a sealed development run')
    files=[]
    for relative,digest in receipt['output_sha256'].items():
        rel=Path(relative)
        if rel.is_absolute() or '..' in rel.parts or rel.parts[:2] not in (('results','runs'),('provenance','runs')) or rel.parts[2]!=run_id:
            raise ValueError('Unsafe receipt path')
        p=paths.root/rel; guard.input_files.add(p.resolve())
        if file_sha256(p)!=digest:
            raise AssertionError('Sealed audit artifact changed: '+relative)
        files.append(p)
    return receipt,files


def regression_s1(paths, config, guard, bases, scores):
    run_id=config['frozen_s1_run']
    receipt,files=verify_sealed_run(paths,run_id,guard)
    root=paths.root/'results/runs'/run_id
    old=read_frame(root/'heldout_scores.parquet').sort_values(KEYS).reset_index(drop=True)
    fresh=scores.loc[scores.model.eq('B2')].sort_values(KEYS).reset_index(drop=True)
    pd.testing.assert_frame_equal(fresh[old.columns],old,check_exact=False,rtol=0,atol=1e-12)
    for role in [*[f'outer_{f}' for f in range(5)],'all_development_candidate']:
        for h in HORIZONS:
            old=read_frame(root/'matrices'/f'{role}_{h}d.parquet')
            new=bases[role].b2.transitions.loc[bases[role].b2.transitions.horizon_days.eq(h)]
            pd.testing.assert_frame_equal(new.reset_index(drop=True),old.reset_index(drop=True),check_exact=False,rtol=0,atol=1e-12)
    return {'reference_run':run_id,'passed':True,'matrix_tables':12,'sealed_artifacts_verified':len(files),
            'phase':'post_computation_audit_only','historical_predictions_used_for_fitting':False}


def execute(paths,config,config_path,run_id,replay_of=None):
    start=time.monotonic(); validate_config(config)
    if not run_id.startswith('adaptive_b2_b1_'):
        raise ValueError('New experiment must use its own run namespace')
    counts_path,folds_path=run_input_paths(paths,config)
    allowed=[counts_path,folds_path,counts_path.parent/'source_ID_summary.csv']
    allowed+=list((counts_path.parent/'release_labels').glob('*.parquet'))
    for p in (counts_path,folds_path):
        allowed += [paths.root/'provenance/runs'/p.parent.name/'outputs.json',
                    paths.root/'provenance/runs'/p.parent.name/'run.json']
    allowed += [paths.asset(a) for a in config['source_assets']]
    run=paths.create_run(run_id,config)
    guard=ExperimentGuard(paths,run,allowed); sys.addaudithook(guard)
    try:
        counts,folds,origins,destinations,reasons,inventory=load_inputs(paths,config)
        inventory[config_path.relative_to(paths.root).as_posix()]=file_sha256(config_path)
        code=source_hashes(paths)
        for name,data in [('config.json',config)]:
            save_json(paths,run['results']/name,data)
        for name,data in [('input_inventory.json',inventory),('source_sha256.json',code)]:
            save_json(paths,run['provenance']/name,data)
        paths.publish(run['provenance']/'approved_plan.md',lambda out:out.write(paths._resolve(config['approved_plan']).read_bytes()))
        save_json(paths,run['provenance']/'environment.json',{
            'python':sys.version,'platform':platform.platform(),
            'git_head':subprocess.run(['git','rev-parse','HEAD'],cwd=paths.root,text=True,capture_output=True,check=True).stdout.strip(),
            'git_worktree_status':subprocess.run(['git','status','--porcelain'],cwd=paths.root,text=True,capture_output=True,check=True).stdout,
            'packages':{n:importlib.metadata.version(n) for n in ('numpy','pandas','pyarrow','shapely','matplotlib')}})
        for name,table in [('counts_by_id.parquet',counts),('folds.csv',folds),('source_index.csv',origins),
                           ('destination_cells.csv',destinations),('qualification_reasons_by_id.csv',reasons)]:
            save_frame(paths,run['results']/name,table)
        save_frame(paths,run['results']/'destination_index.csv',pd.DataFrame({
            'destination_cell_1':[*destinations.cell,EXIT],
            'state_kind':['D_cell']*len(destinations)+['first_exit_E']}))
        roles,bases,predictions={},{},{}
        all_candidates,all_terms,all_pooled,all_selected=[],[],[],[]
        all_scores,all_weights,all_budget=[],[],[]

        def fit(role,training_ids,evaluation_ids,outer=-1,inner=-1):
            b=fit_bases(counts,training_ids,origins.cell,[*destinations.cell,EXIT])
            bases[role]=b
            roles[role]={'training_ids':list(map(int,training_ids)),'evaluation_ids':list(map(int,evaluation_ids)),
                         'outer_fold':outer,'inner_fold':inner}
            save_frame(paths,run['results']/'bases'/f'{role}_b2.parquet',b.b2.transitions)
            save_frame(paths,run['results']/'bases'/f'{role}_support.csv',b.b2.support)
            refs=[]
            for h in HORIZONS:
                active=b.references[h]>0
                refs.append(pd.DataFrame({'horizon_days':h,'destination_cell_1':b.states[active],
                                          'probability':b.references[h][active],'median_pair_count':b.medians[h]}))
            save_frame(paths,run['results']/'bases'/f'{role}_b1.parquet',pd.concat(refs,ignore_index=True))
            return b

        def tune_part(base,role,selection_role,ids):
            terms=coefficient_rows(base,counts,ids)
            all_terms.append(terms.assign(fit_role=role,selection_role=selection_role))
            scores=candidate_scores(terms).assign(fit_role=role,selection_role=selection_role)
            all_candidates.append(scores)
            return scores

        def select(parts,role):
            selected,pooled=select_parameters(pd.concat(parts,ignore_index=True))
            selected['role']=role; pooled['role']=role
            all_selected.append(selected); all_pooled.append(pooled)
            return {model:selected.loc[selected.model.eq(model)].set_index('horizon_days').parameter_a.to_dict()
                    for model in ('Fixed','Adaptive')}

        def export_models(base,role,parameters,heldout=None,outer=-1):
            predictions[role]={}
            for family in MODELS:
                vectors,weights=forecasts(base,family,parameters.get(family,{}))
                predictions[role][family]=vectors
                all_weights.append(weights.assign(role=role,outer_fold=outer))
                save_frame(paths,run['results']/'matrices'/f'{role}_{family}.parquet',matrix_frame(base,vectors))
                if heldout is not None:
                    scores,boundaries=evaluate(base,vectors,counts,heldout,family)
                    all_scores.append(scores.assign(role=role,outer_fold=outer))
                    all_budget.append(boundaries.assign(role=role,outer_fold=outer))

        full_tuning=[]
        for outer in range(5):
            role=f'outer_{outer}'; inner_parts=[]
            train=folds.loc[folds.outer_fold.ne(outer),'id'].tolist()
            heldout=folds.loc[folds.outer_fold.eq(outer),'id'].tolist()
            for inner in range(5):
                if inner==outer:
                    continue
                fit_role=f'outer_{outer}_inner_{inner}'
                inner_train=folds.loc[~folds.outer_fold.isin([outer,inner]),'id'].tolist()
                inner_ids=folds.loc[folds.outer_fold.eq(inner),'id'].tolist()
                base=fit(fit_role,inner_train,inner_ids,outer,inner)
                inner_parts.append(tune_part(base,fit_role,role,inner_ids))
            parameters=select(inner_parts,role)
            base=fit(role,train,heldout,outer)
            export_models(base,role,parameters,heldout,outer)
            full_tuning.append(tune_part(base,role,'all_development_candidate',heldout))
            print(f'Completed outer fold {outer}; selected {parameters}',flush=True)
        final_role='all_development_candidate'
        parameters=select(full_tuning,final_role)
        candidate=fit(final_role,folds.id.tolist(),[])
        export_models(candidate,final_role,parameters)
        scores=pd.concat(all_scores,ignore_index=True).sort_values(['outer_fold','model',*KEYS]).reset_index(drop=True)
        weights=pd.concat(all_weights,ignore_index=True)
        candidates=pd.concat(all_candidates,ignore_index=True)
        selected=pd.concat(all_selected,ignore_index=True)
        summary=summarize_scores(scores)
        draws,intervals,differences=paired_bootstrap(scores,folds.id.tolist(),config['bootstrap_replicates'],config['bootstrap_seed'])
        for name,table in [('heldout_scores.parquet',scores),('row_support.csv',weights),('summary.csv',summary),
                           ('cell_summary.csv',summarize_scores(scores,('horizon_days','model','origin_cell_1'))),
                           ('fold_summary.csv',summarize_scores(scores,('outer_fold','horizon_days','model'))),
                           ('inner_candidate_scores.csv',candidates),('selection_terms.csv',pd.concat(all_terms,ignore_index=True)),
                           ('selected_parameters.csv',selected),('parameter_search.csv',pd.concat(all_pooled,ignore_index=True)),
                           ('budget_boundaries.parquet',pd.concat(all_budget,ignore_index=True)),
                           ('bootstrap_draws.csv',draws),('bootstrap_intervals.csv',intervals),('paired_differences.csv',differences)]:
            save_frame(paths,run['results']/name,table)
        save_json(paths,run['results']/'fit_roles.json',roles)
        print('Auditing independent counts, candidate scores, selection and held-out probability arithmetic',flush=True)
        verification=independent_audit(counts,folds,roles,bases,predictions,scores,candidates,selected)
        verification['frozen_s1_regression']=regression_s1(paths,config,guard,bases,scores)
        if replay_of:
            if not replay_of.startswith('adaptive_b2_b1_'):
                raise ValueError('Replay must use the same experiment namespace')
            receipt,_=verify_sealed_run(paths,replay_of,guard)
            previous=paths.root/'results/runs'/replay_of
            compared=[]
            for p in sorted(run['results'].rglob('*')):
                if p.suffix not in ('.csv','.parquet'):
                    continue
                old=previous/p.relative_to(run['results'])
                pd.testing.assert_frame_equal(read_frame(p),read_frame(old),check_exact=False,rtol=0,atol=1e-12)
                compared.append(p.relative_to(run['results']).as_posix())
            verification['replay']={'reference_run':replay_of,'tables_compared':compared,'tolerance':1e-12,'passed':True}
        write_report(paths,run,config,summary,intervals,differences,selected,candidate,
                     predictions[final_role],weights.loc[weights.role.eq(final_role)],verification)
        for relative,digest in {**inventory,**code}.items():
            if file_sha256(paths.root/relative)!=digest:
                raise AssertionError('Input/code changed during execution: '+relative)
        verification.update(elapsed_seconds=time.monotonic()-start,
                            max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                            development_IDs=len(folds),canonical_trajectory_files_read=len(guard.read_ids),
                            final_test_trajectories_read=0,denied_operations=guard.denied,
                            input_hashes_unchanged=True,code_hashes_unchanged=True,
                            historical_model_outputs_used_for_fitting=False,
                            input_files_opened=sorted(p.relative_to(paths.root).as_posix() for p in guard.opened_inputs))
        _seal(paths,run,verification)
        print(json.dumps({'run_id':run_id,'elapsed_seconds':verification['elapsed_seconds'],
                          'summary':summary[['horizon_days','model','brier','region90_cells','region90_hit']].to_dict('records')}),flush=True)
        return run
    except Exception as error:
        save_json(paths,run['provenance']/'FAILED.json',{'type':type(error).__name__,'message':str(error),'denied_operations':guard.denied})
        raise
    finally:
        guard.active=False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default='configs/adaptive_b2_b1.json')
    parser.add_argument('--run-id')
    parser.add_argument('--replay-of')
    args=parser.parse_args()
    paths=project_paths(); config_path=paths._resolve(args.config)
    config=json.loads(config_path.read_text()); validate_config(config)
    run_id=args.run_id or 'adaptive_b2_b1_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    def timeout(signum,frame):
        raise TimeoutError('Approved 30-minute complete-run cap reached')
    previous=signal.signal(signal.SIGALRM,timeout); signal.alarm(config['compute_cap_seconds'])
    try:
        execute(paths,config,config_path,run_id,args.replay_of)
    finally:
        signal.alarm(0); signal.signal(signal.SIGALRM,previous)


if __name__=='__main__':
    main()
