"""Read-only independent audit of a stopped E5 resource pilot and its frozen inputs."""
import hashlib
import json
from pathlib import Path
import pandas as pd


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(root,pilot_name):
    root=Path(root);pilot=root/'results/runs'/pilot_name;prov=root/'provenance/runs'/pilot_name
    receipt=json.loads((prov/'outputs.json').read_text())
    if receipt['completed'] is not True or receipt['final_test_access'] is not False:
        raise AssertionError('Pilot capacity assessment is not sealed')
    checked=0
    for relative,digest in receipt['output_sha256'].items():
        p=root/relative
        if not p.resolve().is_relative_to(root) or sha(p)!=digest:
            raise AssertionError('Pilot output hash mismatch: '+relative)
        checked+=1
    inputs=json.loads((prov/'input_inventory.json').read_text())
    for relative,digest in inputs.items():
        if sha(root/relative)!=digest:raise AssertionError('Frozen input changed: '+relative)
    sources=json.loads((prov/'source_sha256.json').read_text())
    for relative,digest in sources.items():
        if sha(root/relative)!=digest:raise AssertionError('Pilot source changed: '+relative)
    result=json.loads((pilot/'capacity.json').read_text())
    if result['status']!='CAPACITY_FAILED' or result['capacity_passed'] or result['full_experiment_started']:
        raise AssertionError('Unexpected gate status')
    if result['scientific_accuracy_results_available'] or result['canonical_train_reads'] or result['denied_accesses']:
        raise AssertionError('Scope or isolation claim mismatch')
    timings=pd.read_csv(pilot/'completed_query_timings.csv');roster=pd.read_csv(pilot/'pilot_roster.csv')
    samples=pd.read_csv(pilot/'independent_transfer_checks.csv');work=pd.read_csv(pilot/'workload.csv')
    frozen=json.loads((prov/'roster_freeze.json').read_text())
    if frozen['selection_used_outcomes'] or frozen['roster_sha256']!=sha(pilot/'pilot_roster.csv'):
        raise AssertionError('Roster freeze mismatch')
    if len(timings)!=result['completed_queries'] or len(roster)!=result['frozen_queries']:
        raise AssertionError('Completion denominators mismatch')
    if len(samples)!=result['independent_transfer_checks']:raise AssertionError('Sample count mismatch')
    folds_path=root/'results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv'
    folds=pd.read_csv(folds_path).set_index('id').outer_fold.to_dict()
    for index,r in timings.iterrows():
        q=roster.iloc[index]
        if (q.id,q.origin_source_obs,q.horizon_days)!=(r.id,r.origin_source_obs,r.horizon_days):
            raise AssertionError('Completed timing not in frozen order')
        if int(q.fold)!=1 or folds[int(q.id)]!=1:raise AssertionError('Wrong held-out pilot fold')
        outcomes=pd.read_csv(pilot/f'query_{index:03d}_outcomes.csv')
        if set(outcomes.donor_fold)-{0,2,3,4}:raise AssertionError('Forbidden donor fold')
        if int(outcomes.pair_count.sum())!=int(r.donors) or int(r.certified+r.literal_pairs)!=int(r.donors):
            raise AssertionError('Donor mass/count mismatch')
        if not ((outcomes.destination==-3)==(outcomes.reason>0)).all():raise AssertionError('Failure semantics mismatch')
        for s in samples[samples.query_index.eq(index)].itertuples(index=False):
            if s.donor_id==int(q.id) or folds[s.donor_id]==1:raise AssertionError('Sampled whole-ID leakage')
            if not ((outcomes.destination==s.destination)&(outcomes.reason==s.reason)).any():
                raise AssertionError('Sample event absent from completed aggregate')
    if work.groupby('horizon_days').outer_query_donor_combinations.sum().to_dict()!={7:15179967338,30:12193653838}:
        raise AssertionError('Workload reconciliation mismatch')
    return dict(passed=True,audit_scope='Stopped resource gate; no scientific quality acceptance',
        pilot_outputs_verified=checked,input_hashes_verified=len(inputs),source_hashes_verified=len(sources),
        completed_query_mass_checks=len(timings),independent_scalar_checks_recorded=len(samples),
        full_5000_sample_geometry_audit_completed=False,full_cv_completed=False,full_replay_completed=False,
        four_solver_real_data_capacity_test_completed=bool(result['solver_profiles']),
        final_test_access=False,canonical_training_trajectory_reads=0,
        all_original_inputs_and_sources_unchanged=True)
