"""Independent saved-artifact audit; does not re-open trajectories or fit models."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def audit(root,run_id):
    run=root/'results/runs'/run_id;prov=root/'provenance/runs'/run_id
    receipt=json.loads((prov/'outputs.json').read_text())
    for rel,expected in receipt['output_sha256'].items():
        assert digest(root/rel)==expected,rel
    trial=json.loads((run/'trial.json').read_text())
    assert trial['full_experiment_started'] is False and trial['final_test_access'] is False
    if trial.get('final_access_counters_flushed',True):
        assert trial['denied_accesses']==[] and trial['canonical_reads']==0
    else:
        assert trial['metadata_recovered_after_native_crash'] and trial['read_guard_active']
    assert sum(trial['used_seconds'].values())<=7201
    for stage,limit in dict(A=1200,B=3000,C=2100,D=900).items():
        assert trial['used_seconds'][stage]<=limit+1
    checked=0;queries=0
    for p in sorted(run.glob('selected_*.npz')):
        index=int(p.stem.split('_')[1]);a=np.load(p);b=np.load(run/f'reference_{index:03d}.npz')
        np.testing.assert_array_equal(a['destination'],b['destination']);np.testing.assert_array_equal(a['reason'],b['reason'])
        table=pd.read_csv(run/f'checkpoint_{index:03d}.csv')
        actual=pd.DataFrame(dict(destination=a['destination'],reason=a['reason'])).value_counts().sort_index()
        saved=table.groupby(['destination','reason']).pair_count.sum().sort_index()
        np.testing.assert_array_equal(actual.index.to_numpy(),saved.index.to_numpy());np.testing.assert_array_equal(actual.values,saved.values)
        checked+=len(a['destination']);queries+=1
    valpath=run/'validation.json'
    if valpath.exists() and json.loads(valpath.read_text()).get('status')!='INCOMPLETE':
        val=json.loads(valpath.read_text());assert checked==val['complete_pair_parity'];assert queries==12
        scalar=pd.read_csv(run/'scalar_checks.csv');assert len(scalar)>=5000 and len(scalar)==val['scalar_checks']
        assert set(scalar.horizon)=={7,30} and set(scalar.query_fold)==set(range(5)) and set(scalar.coastal)=={False,True}
        roster=pd.read_csv(run/'roster.csv');assert len(roster)==58 and roster.calibration.sum()==8
        for r in roster.itertuples(index=False):
            table=pd.read_csv(run/f'checkpoint_{r.query_index:03d}.csv');proof=json.loads((run/f'checkpoint_{r.query_index:03d}_receipt.json').read_text())
            assert table.pair_count.sum()==proof['donors'] and not table.donor_fold.eq(r.fold).any()
            assert proof['sha256']==digest(run/f'checkpoint_{r.query_index:03d}.csv')
    else:
        times=pd.read_csv(run/'timings.csv');chosen=json.loads((run/'configuration_freeze.json').read_text())['selected']
        completed=times[times.variant.eq(chosen['variant'])&times.batch.eq(chosen['batch'])]
        val=json.loads(valpath.read_text());assert len(completed)==8
        assert completed.donors.sum()==val['in_process_full_pair_comparisons_per_variant_batch']
    original=json.loads(Path('/tmp/s3e5_o1_development_before.json').read_text())
    changed=[rel for rel,sha in original.items() if digest(root/rel)!=sha]
    assert not changed,changed
    return dict(sealed_artifacts_verified=len(receipt['output_sha256']),independent_saved_pair_comparisons=checked,pair_comparison_queries=queries,preexisting_files_verified=len(original),preexisting_files_changed=changed,full_experiment_started=False,status='ARTIFACT_AUDIT_PASS_SCIENTIFIC_AND_EXTENDED_VALIDATION_INCOMPLETE',final_access_counter_log_complete=trial.get('final_access_counters_flushed',True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_id');a=p.parse_args()
    print(json.dumps(audit(Path(__file__).resolve().parents[2],a.run_id),indent=2))
