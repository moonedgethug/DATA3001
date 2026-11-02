"""Approved E2 isolated experiment, bounded preflight and complete-run replay."""
import argparse
from datetime import datetime,timezone
import importlib.metadata
import json
import platform
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path
import pandas as pd

from data3001.paths import project_paths,file_sha256
from data3001.modelling.common.runtime import save_frame,save_json,_seal
from data3001.modelling.common.qualified_count_inputs import ExperimentGuard,load_inputs,read_frame,run_input_paths,KEYS,EXIT
from data3001.modelling.baselines.b2_b1_e2 import (
    A_GRID,C_GRID,BETA_GRID,MODELS,fit_bases,candidate_metrics,select_parameters,forecasts,
    diagnostic_scores,group_diagnostics,region_changes,summarize_scores,paired_bootstrap,
)
from data3001.modelling.baselines.b2_b1_e2_audit import (
    rebuild,audit_candidates,independent_audit,audit_bootstrap,verify_sealed_run,frozen_regressions,
)
from data3001.modelling.baselines.b2_b1_e2_report import write_report


def expected_config():
    return dict(experiment='b2_b1_e2',plan_version='E2_v1',approved_plan='docs/b2_b1_e2_plan.md',
                dataset_release='per-drifter-cleaned-20261017-v7',
                contract_sha256='6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446',
                grid_degrees=1,target='stopped',scenario='pooled',departure_seasons='annual_pooled',origin_population='R',
                horizons_days=[7,30],tolerance_hours=0,predictors=['origin_cell_1'],weighting='equal_eligible_pairs',
                models=list(MODELS),parameter_grid=list(A_GRID),info_c_grid=list(C_GRID),weight_beta_grid=list(BETA_GRID),
                info_exit_policy='preserve_B1_E_mass',adaptive_support='training_pair_count',adaptive_scale='fitting_median_positive_row_count',
                primary_metric='standard_multiclass_brier',selector='Brier_hit_constraints_then_minimum_region90',
                brier_deterioration_margin=0,hit_deterioration_margin=0,unsupported_score='common_B2_mask_missing',
                outer_folds=5,inner_folds=4,bootstrap_replicates=5000,bootstrap_seed=20261030,adjusted_directional_bounds=12,
                region_level=.9,mass_tolerance=1e-12,tie_tolerance=1e-12,compute_cap_seconds=1800,preflight_cap_seconds=300,
                final_test_access=False,counts_path='results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet',
                folds_path='results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv',
                frozen_s1_run='empirical_b2_20261029T121555_976173Z',frozen_e1_run='adaptive_b2_b1_20261030T044950_931787Z',
                source_assets=['english_contract','state_index','release_R','transport_D','land_mask_intermediate'])


def validate_config(config):
    if config!=expected_config():raise ValueError('Configuration differs from approved E2 specification')


def source_hashes(paths):
    files={Path(m.__file__).resolve() for name,m in list(sys.modules.items()) if name.startswith('data3001') and getattr(m,'__file__',None) and str(m.__file__).endswith('.py')}
    files.add(Path(__file__).resolve())
    return {p.relative_to(paths.root).as_posix():file_sha256(p) for p in sorted(files)}


def matrix_frame(base,vectors):
    return pd.concat([pd.DataFrame({'horizon_days':h,'origin_cell_1':o,'destination_cell_1':base.states[p>0],
                                    'probability':p[p>0]}) for (h,o),p in sorted(vectors.items())],ignore_index=True)


def execute(paths,config,config_path,run_id,preflight=False,preflight_run=None,replay_of=None):
    start=time.monotonic();validate_config(config)
    prefix='b2_b1_e2_preflight_' if preflight else 'b2_b1_e2_'
    if not run_id.startswith(prefix) or (not preflight and run_id.startswith('b2_b1_e2_preflight_')):
        raise ValueError('Incorrect isolated run namespace')
    if not preflight and not preflight_run:raise ValueError('A successful approved preflight receipt is required')
    if 'USER APPROVED' not in paths._resolve(config['approved_plan']).read_text():raise ValueError('Plan not approved')
    counts_path,folds_path=run_input_paths(paths,config)
    allowed=[counts_path,folds_path,counts_path.parent/'source_ID_summary.csv',*list((counts_path.parent/'release_labels').glob('*.parquet'))]
    for p in (counts_path,folds_path):allowed.extend([paths.root/'provenance/runs'/p.parent.name/'outputs.json',paths.root/'provenance/runs'/p.parent.name/'run.json'])
    allowed.extend(paths.asset(a) for a in config['source_assets'])
    run=paths.create_run(run_id,{**config,'execution_mode':'preflight' if preflight else 'full'})
    guard=ExperimentGuard(paths,run,allowed);sys.addaudithook(guard)
    try:
        counts,folds,origins,destinations,reasons,inventory=load_inputs(paths,config)
        inventory[config_path.relative_to(paths.root).as_posix()]=file_sha256(config_path);code=source_hashes(paths)
        if not preflight:
            if not preflight_run.startswith('b2_b1_e2_preflight_'):raise ValueError('Wrong preflight namespace')
            verify_sealed_run(paths,preflight_run,guard)
            previous=paths.root/'provenance/runs'/preflight_run
            pre=json.loads((previous/'verification.json').read_text())
            assert pre['preflight_only'] and pre['projected_complete_seconds']<config['compute_cap_seconds']
            assert json.loads((previous/'source_sha256.json').read_text())==code,'Source changed since preflight'
            assert json.loads((previous/'input_inventory.json').read_text())==inventory,'Inputs changed since preflight'
        save_json(paths,run['results']/'config.json',config)
        for name,value in [('input_inventory.json',inventory),('source_sha256.json',code)]:save_json(paths,run['provenance']/name,value)
        paths.publish(run['provenance']/'approved_plan.md',lambda out:out.write(paths._resolve(config['approved_plan']).read_bytes()))
        save_json(paths,run['provenance']/'environment.json',dict(python=sys.version,platform=platform.platform(),
            git_head=subprocess.run(['git','rev-parse','HEAD'],cwd=paths.root,text=True,capture_output=True,check=True).stdout.strip(),
            git_worktree_status=subprocess.run(['git','status','--porcelain'],cwd=paths.root,text=True,capture_output=True,check=True).stdout,
            packages={n:importlib.metadata.version(n) for n in ('numpy','pandas','pyarrow','shapely','matplotlib')}))
        for name,frame in [('counts_by_id.parquet',counts),('folds.csv',folds),('source_index.csv',origins),('destination_cells.csv',destinations),('qualification_reasons_by_id.csv',reasons)]:save_frame(paths,run['results']/name,frame)
        states=[*destinations.cell,EXIT]
        save_frame(paths,run['results']/'destination_index.csv',pd.DataFrame({'destination_cell_1':states,'state_kind':['D_cell']*len(destinations)+['first_exit_E']}))
        bases={};roles={};predictions={};candidates=[];searches=[];selections=[];score_parts=[];weight_parts=[];boundaries=[];changes=[]

        def fit(role,train,heldout,outer=-1,inner=-1):
            b=fit_bases(counts,train,origins.cell,states);bases[role]=b
            roles[role]=dict(training_ids=list(map(int,train)),evaluation_ids=list(map(int,heldout)),outer_fold=outer,inner_fold=inner)
            save_frame(paths,run['results']/'bases'/f'{role}_b2.parquet',b.b2.transitions)
            save_frame(paths,run['results']/'bases'/f'{role}_support.csv',b.b2.support)
            refs=[]
            for h in (7,30):
                active=b.references[h]>0
                refs.append(pd.DataFrame({'horizon_days':h,'destination_cell_1':b.states[active],
                                          'probability':b.references[h][active],'median_pair_count':b.medians[h]}))
            save_frame(paths,run['results']/'bases'/f'{role}_b1.parquet',pd.concat(refs,ignore_index=True))
            return b

        def tune(b,role,target,ids):
            table=candidate_metrics(b,counts,ids).assign(fit_role=role,selection_role=target)
            candidates.append(table);return table

        def select(parts,role):
            chosen,pool=select_parameters(pd.concat(parts,ignore_index=True))
            chosen['role']=role;pool['role']=role;selections.append(chosen);searches.append(pool)
            return chosen

        def export(b,role,chosen,ids=None,outer=-1):
            predictions[role]={};role_scores=[]
            for model in MODELS:
                vectors,weights=forecasts(b,model,chosen);predictions[role][model]=vectors
                weight_parts.append(weights.assign(role=role,outer_fold=outer))
                save_frame(paths,run['results']/'matrices'/f'{role}_{model}.parquet',matrix_frame(b,vectors))
                if ids is not None:
                    s,bounds=diagnostic_scores(b,vectors,counts,ids,model)
                    s=s.assign(role=role,outer_fold=outer);role_scores.append(s);score_parts.append(s)
                    boundaries.append(bounds.assign(role=role,outer_fold=outer))
            if role_scores:changes.append(region_changes(b,predictions[role],pd.concat(role_scores,ignore_index=True)).assign(role=role,outer_fold=outer))

        if preflight:
            role='outer_0_inner_1';train=folds.loc[~folds.outer_fold.isin([0,1]),'id'].tolist();ids=folds.loc[folds.outer_fold.eq(1),'id'].tolist()
            measured=time.monotonic();b=fit(role,train,ids,0,1);table=tune(b,role,'outer_0',ids)
            rebuilt=rebuild(counts,folds,roles,b.states);audit=audit_candidates(counts,roles,b.states,rebuilt,table)
            role_seconds=time.monotonic()-measured
            projected=25*role_seconds+360+(time.monotonic()-start-role_seconds)
            save_frame(paths,run['results']/'candidate_scores.csv',table);save_json(paths,run['results']/'fit_roles.json',roles)
            if projected>=config['compute_cap_seconds']:raise TimeoutError('Preflight projects a run over the approved cap')
            verification=dict(preflight_only=True,role_seconds=role_seconds,projected_complete_seconds=projected,
                              candidate_audit=audit,elapsed_seconds=time.monotonic()-start,final_test_trajectories_read=0,
                              canonical_trajectory_files_read=len(guard.read_ids),denied_operations=guard.denied)
            for relative,digest in {**inventory,**code}.items():assert file_sha256(paths.root/relative)==digest
            _seal(paths,run,verification);print(json.dumps({'run_id':run_id,**verification}),flush=True);return run

        for outer in range(5):
            role=f'outer_{outer}';parts=[]
            for inner in range(5):
                if inner==outer:continue
                train=folds.loc[~folds.outer_fold.isin([outer,inner]),'id'].tolist();ids=folds.loc[folds.outer_fold.eq(inner),'id'].tolist()
                fit_role=f'outer_{outer}_inner_{inner}';b=fit(fit_role,train,ids,outer,inner);parts.append(tune(b,fit_role,role,ids))
            chosen=select(parts,role);train=folds.loc[folds.outer_fold.ne(outer),'id'].tolist();ids=folds.loc[folds.outer_fold.eq(outer),'id'].tolist()
            b=fit(role,train,ids,outer);export(b,role,chosen,ids,outer)
            print('Completed outer fold '+str(outer)+': '+chosen[chosen.model.isin(['Info','Weight'])][['horizon_days','model','parameter_a','parameter_c','parameter_beta','selection_status']].to_json(orient='records'),flush=True)
        scores=pd.concat(score_parts,ignore_index=True).sort_values(['outer_fold','model',*KEYS]).reset_index(drop=True)
        save_frame(paths,run['results']/'heldout_scores.parquet',scores)
        save_frame(paths,run['results']/'selected_outer_parameters.csv',pd.concat(selections,ignore_index=True))
        frozen_files=[run['results']/'heldout_scores.parquet',run['results']/'selected_outer_parameters.csv',*sorted((run['results']/'matrices').glob('*.parquet'))]
        frozen={p.relative_to(paths.root).as_posix():file_sha256(p) for p in frozen_files}
        save_json(paths,run['provenance']/'outer_freeze.json',{'phase':'before_all_development_tuning','sha256':frozen})
        full_parts=[]
        for outer in range(5):
            role=f'outer_{outer}';full_parts.append(tune(bases[role],role,'all_development_candidate',roles[role]['evaluation_ids']))
        final='all_development_candidate';chosen=select(full_parts,final);b=fit(final,folds.id.tolist(),[]);export(b,final,chosen)
        for relative,digest in frozen.items():assert file_sha256(paths.root/relative)==digest,'Outer predictions changed after freezing'
        weights=pd.concat(weight_parts,ignore_index=True);selected=pd.concat(selections,ignore_index=True)
        summary=summarize_scores(scores);diagnostics=group_diagnostics(scores,weights)
        print('Computing paired whole-ID uncertainty (5,000 resamples)',flush=True)
        draws,intervals,diffs,decisions,aggregates=paired_bootstrap(scores,folds.id.tolist(),config['bootstrap_replicates'],config['bootstrap_seed'])
        tables={'row_support.csv':weights,'summary.csv':summary,'diagnostics.csv':diagnostics,
                'cell_summary.csv':summarize_scores(scores,('horizon_days','model','origin_cell_1')),
                'fold_summary.csv':summarize_scores(scores,('outer_fold','horizon_days','model')),
                'candidate_scores.csv':pd.concat(candidates,ignore_index=True),'selected_parameters.csv':selected,
                'parameter_search.csv':pd.concat(searches,ignore_index=True),'region_changes.csv':pd.concat(changes,ignore_index=True),
                'budget_boundaries.parquet':pd.concat(boundaries,ignore_index=True),'bootstrap_draws.csv':draws,
                'bootstrap_intervals.csv':intervals,'paired_differences.csv':diffs,'decisions.csv':decisions,'bootstrap_ID_aggregates.csv':aggregates}
        for name,table in tables.items():save_frame(paths,run['results']/name,table)
        save_json(paths,run['results']/'fit_roles.json',roles)
        print('Independently auditing persisted counts, all candidates, selection and predictions',flush=True)
        verification=independent_audit(paths,run,counts,folds,roles,b.states)
        verification['bootstrap']=audit_bootstrap(paths,run,folds,config['bootstrap_replicates'],config['bootstrap_seed'])
        verification['frozen_regressions']=frozen_regressions(paths,run,guard,config)
        verification['outer_predictions_unchanged_after_all_development_tuning']=True
        if replay_of:
            if not replay_of.startswith('b2_b1_e2_') or replay_of.startswith('b2_b1_e2_preflight_'):raise ValueError('Invalid replay reference')
            verify_sealed_run(paths,replay_of,guard);previous=paths.root/'results/runs'/replay_of;compared=[]
            for path in sorted(run['results'].rglob('*')):
                if path.suffix not in ('.csv','.parquet'):continue
                pd.testing.assert_frame_equal(read_frame(path),read_frame(previous/path.relative_to(run['results'])),check_exact=False,rtol=0,atol=1e-12)
                compared.append(path.relative_to(run['results']).as_posix())
            verification['replay']=dict(reference_run=replay_of,passed=True,tables_compared=compared,absolute_tolerance=1e-12)
        write_report(paths,run,summary,diffs,decisions,selected,diagnostics,b,predictions[final],weights[weights.role.eq(final)],verification)
        for relative,digest in {**inventory,**code,**frozen}.items():assert file_sha256(paths.root/relative)==digest,'Input/code/frozen output changed: '+relative
        verification.update(preflight_only=False,preflight_run=preflight_run,elapsed_seconds=time.monotonic()-start,
                            max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,development_IDs=len(folds),
                            canonical_trajectory_files_read=len(guard.read_ids),final_test_trajectories_read=0,denied_operations=guard.denied,
                            input_hashes_unchanged=True,code_hashes_unchanged=True,historical_outputs_used_for_fitting=False,
                            input_files_opened=sorted(p.relative_to(paths.root).as_posix() for p in guard.opened_inputs))
        _seal(paths,run,verification)
        print(json.dumps({'run_id':run_id,'elapsed_seconds':verification['elapsed_seconds'],'decisions':decisions.to_dict('records')}),flush=True)
        return run
    except Exception as error:
        save_json(paths,run['provenance']/'FAILED.json',{'type':type(error).__name__,'message':str(error),'denied_operations':guard.denied});raise
    finally:guard.active=False


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',default='configs/b2_b1_e2.json')
    parser.add_argument('--run-id');parser.add_argument('--preflight',action='store_true');parser.add_argument('--preflight-run');parser.add_argument('--replay-of')
    args=parser.parse_args();paths=project_paths();config_path=paths._resolve(args.config);config=json.loads(config_path.read_text());validate_config(config)
    if args.preflight and (args.preflight_run or args.replay_of):raise ValueError('Preflight cannot replay or use a prior preflight')
    run_id=args.run_id or ('b2_b1_e2_preflight_' if args.preflight else 'b2_b1_e2_')+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    def timeout(signum,frame):raise TimeoutError('Approved E2 execution cap reached')
    previous=signal.signal(signal.SIGALRM,timeout);signal.alarm(config['preflight_cap_seconds'] if args.preflight else config['compute_cap_seconds'])
    try:execute(paths,config,config_path,run_id,args.preflight,args.preflight_run,args.replay_of)
    finally:signal.alarm(0);signal.signal(signal.SIGALRM,previous)


if __name__=='__main__':main()
