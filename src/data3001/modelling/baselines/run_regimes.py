"""Fixed-regime development baselines. No final-test access or visualisation.

Prepare: python -B -m data3001.modelling.baselines.run_regimes --prepare-only
Fit both: python -B -m data3001.modelling.baselines.run_regimes --input-run <sealed-input>
Report existing fits: add --completed-runs <drogued-run> <undrogued-run>
"""
import argparse
from datetime import datetime, timezone
import json
import sys
import numpy as np
import pandas as pd
from data3001.dataset import PreparedSource, track_path
from data3001.paths import file_sha256, project_paths, legacy_path
from data3001.preprocessing.prep_pairs import load_track, generate
from data3001.preprocessing.prep_core import REASONS
from data3001.modelling.baselines.cv import summarize_scores
from data3001.modelling.common.experiment import make_nested_folds, fold_digest
from data3001.modelling.baselines.neighbourhood_report import _table
from data3001.modelling.baselines.regimes import SCENARIOS, qualify_intervals, preflight
from data3001.modelling.common.runtime import ReadOnlyInputs, save_frame, save_json
from data3001.modelling.baselines.run_neighbourhood import PARENT, CONTRACT_SHA, _identity, join_coordinates, run_models
from data3001.modelling.common.runtime import _source_hashes, _seal, verified_run

POOLED_INPUT = 'neighbour_input_20261024T062737_251970Z'
POOLED_RUN = 'baseline_neighbour_cv_20261024T065917_879042Z'


def check_frozen(paths, bound):
    for relative, checksum in bound.items():
        if file_sha256(paths.root/relative) != checksum:
            raise ValueError('Frozen input/source changed: '+relative)


def prepare_inputs(paths):
    dataset, bound = _identity(paths)
    for prior in (POOLED_INPUT, POOLED_RUN):
        receipt=verified_run(paths,prior)
        bound[receipt.relative_to(paths.root).as_posix()]=file_sha256(receipt)
        cfg=json.loads((receipt.parent/'run.json').read_text())['config']
        check_frozen(paths,cfg['input_sha256'])
    cutoff=legacy_path('metadata/corpus_time_coverage.json')
    bound[cutoff.relative_to(paths.root).as_posix()]=file_sha256(cutoff)
    sources=_source_hashes(paths)
    rid=datetime.now(timezone.utc).strftime('regime_input_%Y%m%dT%H%M%S_%fZ')
    run=paths.create_run(rid,dict(stage='fixed_regime_input',parent=PARENT,
        pooled_input=POOLED_INPUT,pooled_reference=POOLED_RUN,dataset_release=dataset['version'],
        contract_sha256=CONTRACT_SHA,input_sha256=bound,source_sha256=sources,
        scenarios=list(SCENARIOS),target='endpoint',qualification='Existing official-source-aware full-interval predicates',
        denominator='Previously pooled-eligible exact 7/30-day pairs; no change to pooled eligibility',
        final_test_access=False))
    print('REGIME_INPUT_RUN='+rid,flush=True)
    guard=ReadOnlyInputs(paths.root,run,data_root=paths.data_root);sys.addaudithook(guard)
    try:
        base=pd.read_parquet(paths.root/'results/runs'/POOLED_INPUT/'eligible_pairs.parquet')
        if base.duplicated(['id','horizon_days','origin_source_obs']).any():
            raise ValueError('Duplicate pooled sources.')
        source=PreparedSource(allow_test=False)
        parts=[];audits=[];track_hashes={}
        ids=sorted(map(int,base.id.unique()))
        for number,sid in enumerate(ids,1):
            if dataset['records'][str(sid)]['pool']!='train':
                raise PermissionError('Final-test ID in pooled preparation.')
            track,a,events=load_track(source,sid)
            source_index=pd.Index(track.source_obs)
            if not source_index.is_unique:
                raise ValueError('Duplicate canonical source key.')
            ledgers=[]
            for h,g in base.loc[base.id.eq(sid)].groupby('horizon_days',sort=True):
                origins=source_index.get_indexer(g.origin_source_obs)
                if (origins<0).any():raise ValueError('Absent canonical origin.')
                pooled,_=generate(track,a,events,sid,origins,int(h),'pooled',0)
                if not pooled.reason_code.eq(0).all():raise ValueError('Pooled qualification changed.')
                fresh=join_coordinates(pooled,track)
                pd.testing.assert_frame_equal(fresh,g[fresh.columns].reset_index(drop=True),check_dtype=False,check_exact=True)
                masks=qualify_intervals(a,origins,g.endpoint_epoch.to_numpy())
                for scenario,mask in zip(SCENARIOS,masks):
                    ledger,_=generate(track,a,events,sid,origins,int(h),scenario,0)
                    if not np.array_equal(ledger.reason_code.eq(0).to_numpy(),mask):
                        raise ValueError('Fixed qualification differs from interval predicates.')
                    # Only state predicates can additionally reject these pooled-eligible pairs.
                    if not ledger.reason_code.isin([0,4,5]).all():
                        raise ValueError('A non-regime predicate changed.')
                    if not np.array_equal(ledger.endpoint_source_obs,g.endpoint_source_obs):
                        raise ValueError('Scenario changed the matched endpoint.')
                    chosen=g.loc[mask].copy();chosen['scenario']=scenario;parts.append(chosen)
                    ledgers.append(ledger)
                    for reason,rg in ledger.groupby('reason_code'):
                        audits.append(dict(id=sid,scenario=scenario,horizon_days=int(h),
                            reason_code=int(reason),reason=REASONS[int(reason)],pairs=len(rg)))
            save_frame(paths,run['results']/'endpoint_ledgers'/f'{sid}.parquet',pd.concat(ledgers,ignore_index=True))
            track_hashes[str(sid)]=dataset['records'][str(sid)]['sha256']
            if number%50==0 or number==len(ids):print(f'Official interval audit: {number}/{len(ids)} development IDs',flush=True)
        pairs=pd.concat(parts,ignore_index=True)
        if pairs.duplicated(['id','horizon_days','origin_source_obs']).any():
            raise ValueError('Fixed-regime source subsets overlap.')
        save_frame(paths,run['results']/'eligible_pairs.parquet',pairs)
        reason=pd.DataFrame(audits);save_frame(paths,run['results']/'qualification_counts.csv',reason)
        support=[]
        for (scenario,h),g in pairs.groupby(['scenario','horizon_days']):
            support.append(dict(scenario=scenario,horizon_days=int(h),eligible_pairs=len(g),
                independent_ids=g.id.nunique(),origin_cells=g.origin_cell_1.nunique(),
                pooled_pairs=int(base.horizon_days.eq(h).sum()),
                retained_pct=100*len(g)/base.horizon_days.eq(h).sum()))
        save_frame(paths,run['results']/'support_summary.csv',pd.DataFrame(support))
        dev=sorted(int(sid) for sid,r in dataset['records'].items() if r['pool']=='train')
        outer,inner=make_nested_folds(dev)
        for scenario in SCENARIOS:
            save_frame(paths,run['results']/f'{scenario}_preflight.csv',preflight(pairs.loc[pairs.scenario.eq(scenario)],outer,inner))
        if guard.read_ids!=set(ids):raise ValueError('Canonical read inventory changed.')
        for sid in ids:track_path(sid,allow_test=False)
        check_frozen(paths,{**bound,**sources})
        _seal(paths,run,dict(pooled_source_keys_and_coordinates_exact=True,fixed_subsets_disjoint=True,
            source_keyed_pooled_pairs=len(base),fixed_pairs=len(pairs),canonical_tracks_read=len(ids),
            canonical_read_sha256=track_hashes,final_test_trajectories_read=0,denied_operations=guard.denied,
            canonical_data_modified=False,fold_assignment_sha256=fold_digest(outer,inner)))
        print(pd.DataFrame(support).to_string(index=False),flush=True)
        print('PREPARED_INPUT_RUN='+rid,flush=True)
        return rid
    finally:guard.active=False


def combined_report(paths,input_run,completed):
    if len(completed)!=2:raise ValueError('Exactly two fixed-regime runs required.')
    dataset,bound=_identity(paths)
    for rid in [input_run,POOLED_RUN,*completed]:
        receipt=verified_run(paths,rid);bound[receipt.relative_to(paths.root).as_posix()]=file_sha256(receipt)
    sources=_source_hashes(paths)
    run_id=datetime.now(timezone.utc).strftime('baseline_regime_comparison_%Y%m%dT%H%M%S_%fZ')
    run=paths.create_run(run_id,dict(stage='fixed_regime_combined_audit',input_run=input_run,
        model_runs=completed,pooled_reference=POOLED_RUN,input_sha256=bound,source_sha256=sources,
        dataset_release=dataset['version'],contract_sha256=CONTRACT_SHA,final_test_access=False))
    summaries=[];matched_summaries=[];intervals=[];weights=[];numeric=[];within=[]
    for scenario,rid in zip(SCENARIOS,completed):
        cfg=json.loads((paths.root/'provenance/runs'/rid/'run.json').read_text())['config']
        if cfg['scenario']!=scenario or cfg['input_run']!=input_run or cfg['pooled_reference']!=POOLED_RUN:
            raise ValueError('Run/scenario/reference mismatch.')
        check_frozen(paths,cfg['input_sha256'])
        root=paths.root/'results/runs'/rid
        for dest,name in [(summaries,'outer_summary.csv'),(matched_summaries,'matched_pooled_summary.csv'),
                          (intervals,'fixed_vs_matched_pooled.csv'),(weights,'final_alpha_selection.csv'),
                          (within,'paired_ID_intervals.csv')]:
            dest.append(pd.read_csv(root/name).assign(scenario=scenario))
        n=pd.concat([pd.read_csv(root/'numerical_audit.csv'),pd.read_csv(root/'final_numerical_audit.csv')])
        numeric.append(dict(scenario=scenario,fit_rows=len(n),unsettled_fit_rows=int((~n.converged).sum()),
                            final_unsettled=int((~pd.read_csv(root/'final_numerical_audit.csv').converged).sum())))
    summary,matched,delta,weight,inside=map(lambda xs:pd.concat(xs,ignore_index=True),[summaries,matched_summaries,intervals,weights,within])
    support=pd.read_csv(paths.root/'results/runs'/input_run/'support_summary.csv')
    for name,frame in [('support_summary.csv',support),('fixed_summary.csv',summary),('matched_pooled_summary.csv',matched),
                       ('fixed_vs_matched_pooled.csv',delta),('final_weights.csv',weight),('numerical_summary.csv',pd.DataFrame(numeric))]:
        save_frame(paths,run['results']/name,frame)
    fields=['scenario','horizon_days','model','brier_failure_penalized','zero_probability_pairs','region90_hit_pct','mean_region90_cells']
    lines=['# Fixed drogue-regime baseline comparison','',
        'This development experiment asks whether conditioning on a known, sustained drogue state improves 7/30-day endpoint probabilities. All nine pre-agreed models were fitted independently in both regimes, including both unaligned U and displacement-aligned A. No final-test trajectories were accessed, canonical data changed, visualisations generated, or Git publication performed.','',
        '## Population and qualification','',
        'Drogued means the approved official evidence supports attachment throughout the requested interval; undrogued means a known detached state throughout. Unknown or switching intervals enter neither fixed scenario and remain in the pooled data. Qualification uses the unchanged source-aware contract rules, including official attached-fill restoration, audited boundary dates and precision guards. The denominator below is the previously pooled-eligible endpoint population, not every raw R origin. One ID may contribute to both scenarios at different times; its entire history retains the same fold.','',
        _table(support,['scenario','horizon_days','eligible_pairs','independent_ids','origin_cells','pooled_pairs','retained_pct']),'',
        'This is a retrospective sustained-state estimand conditional on endpoint observability. It is not an operational guarantee that a currently attached drogue will stay attached. DEPTH-01 remains unresolved: attached-state qualification does not prove homogeneous 15 m drogue depth. These subsets cannot directly validate predictions for oil, containers or people.','',
        '## Held-out development results','',
        'Lower failure-penalised Brier is better; it is not percentage accuracy. Complete distributions use ordinary multiclass Brier. Unresolved probability remains in the failure penalty, never renormalised away. Region coverage must be read with region size and availability; zero-probability failures and raw infinite log losses remain visible. Raw scores across different regime populations do not establish which physical regime is easier.','',
        _table(summary,fields),'',
        '## Does regime-specific fitting improve over pooled fitting?','',
        'The pooled forecasts and selected weights are frozen from the completed pooled experiment. They are scored again on exactly the same fixed-regime source groups and multiplicities, with the same held-out ID folds; no pooled forecast is retrained or selected on these truths. The following differences compare each fixed model with its corresponding pooled model on those matched cases. Negative differences favour fixed-regime fitting.','',
        _table(delta,['scenario','horizon_days','model','delta_brier','lower','upper']),'',
        'Intervals use 200 paired whole-ID resamples within fixed outer folds, conditional on saved fits. They omit training-refit, model-selection, shared-environment and numerical-integration uncertainty. Comparisons are exploratory without multiplicity correction. Crossing zero means the evidence does not resolve the sign of the difference. Sustained-state selection and incomplete follow-up can bias the observed population; these results do not identify a causal drogue effect.','',
        '## U versus A and existing controls','',
        'U borrows the neighbours\' original endpoint distributions. A transfers neighbour net displacements onto the target cell\'s empirical training origins. Neither is selected as correct on intuition. The tables below compare the fitted selection procedures within each regime on identical cases.','',
        _table(inside.loc[inside.comparison.isin(['Local-U-Analytic - Global-Analytic','Local-A-Analytic - Global-Analytic','Local-A-Analytic - Local-U-Analytic'])],['scenario','horizon_days','comparison','delta_brier','lower','upper']),'',
        '## Candidate refit weights','',_table(weight,['scenario','family','horizon_days','method','alpha_value','tuning_brier']),'',
        'Each family/horizon has its own globally shared borrowing weight. Grid searches 0, 0.1, ..., 1; Analytic minimises the same quadratic score. All selection uses inner OOF predictions; outer scores assess the complete selection procedure. Full-development weights below are deployment candidates, not independent evidence of their own final-refit accuracy.','',
        '## Engineering and numerical audit','',_table(pd.DataFrame(numeric),['scenario','fit_rows','unsettled_fit_rows','final_unsettled']),'',
        'Each model run independently reproduces all five original controls from regime-specific counts, every saved outer score and weight choice, all U bases, and representative A bases from raw fitting pairs. The same outer-five/inner-four ID assignment, frozen R/D/grid, exact timestamps, equal pair weights, target and integration rule are retained. All subsets passed a fit/tuning support preflight; this guarantees computability, not sufficient statistical support in every cell. See per-run support, cell/ID scores, numerical audits and verification receipts.','',
        'For A, exact small products and balanced large-product approximations retain original donor and anchor marginals. The stability threshold is a successive-approximation diagnostic, not a certified error bound. Any unsettled inner fit can influence selected weights; unsettled outer fits affect the corresponding predictions. Matched pooled A predictions inherit the pooled run\'s numerical caveats. Synthetic land positions stay unresolved, not inferred grounding. No observed outside-D endpoint support implies no established outside calibration.','',
        '## Scope and next decision','',
        'This completes the requested fixed-state baseline comparison only. Review matched differences, interval support, coverage/size and numerical stability before choosing controls for the short-lag Markov stage. One-year, seasonal, arbitrary-object and grounding performance remain unvalidated. Negative or inconclusive effects are valid findings.','',
        '## Reproduction and evidence','',f'- Input: `{input_run}`',f'- Pooled reference: `{POOLED_RUN}`',
        *[f'- {scenario}: `{rid}`' for scenario,rid in zip(SCENARIOS,completed)],'',
        'Run `.venv/bin/python -B -m data3001.modelling.baselines.run_regimes --input-run <input>` for new fixed fits and a new combined report. Existing sealed fits may be combined using --completed-runs. Run manifests bind data/contract/code hashes, input receipts and fold digests; outputs.json seals every delivered artifact.','']
    paths.publish(run['results']/'REPORT.md',lambda stream:stream.write('\n'.join(lines).encode()))
    check_frozen(paths,{**bound,**sources})
    _seal(paths,run,dict(sealed_model_runs_verified=True,identical_case_comparisons=True,final_test_trajectories_read=0,
                        canonical_data_modified=False,no_visualisation_created=True))
    print('COMBINED_REPORT='+str(run['results']/'REPORT.md'),flush=True)
    return run_id


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--input-run')
    parser.add_argument('--completed-runs',nargs=2)
    args=parser.parse_args();paths=project_paths()
    if args.prepare_only:prepare_inputs(paths);return
    inp=args.input_run or prepare_inputs(paths)
    completed=args.completed_runs or [run_models(paths,inp,scenario=s,pooled_run=POOLED_RUN) for s in SCENARIOS]
    combined_report(paths,inp,completed)


if __name__=='__main__':main()
