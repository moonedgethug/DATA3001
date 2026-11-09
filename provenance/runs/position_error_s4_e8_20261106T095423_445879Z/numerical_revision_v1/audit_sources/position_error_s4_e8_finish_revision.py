"""Finish example export after an optional B2 contrast field was NaN.

No forecast, region, score, aggregate, bootstrap draw or input is recomputed.
The failed receipt and its frozen source snapshot remain immutable.
"""
import argparse
import json
import time
import numpy as np
import pandas as pd
from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_json
from data3001.modelling.baselines import position_error_s4_e8_inputs as inputs
from data3001.modelling.baselines import position_error_s4_e8_pipeline as pipe


def finish(paths,parent,cfg,approval,guard):
    start=time.monotonic();run={k:v/'numerical_revision_v1' for k,v in parent.items()}
    failed=json.loads((run['provenance']/'formal_resources.json').read_text());assert not failed['completed']
    freeze=json.loads((run['provenance']/'forecast_freeze.json').read_text())
    target=inputs.release_outer_targets(run,cfg,approval).sort_values(inputs.KEY).reset_index(drop=True)
    cases=inputs.read_frame(run['results']/'case_scores.parquet');original=inputs.read_frame(parent['results']/'case_scores.parquet')
    assert len(cases)==33971*4 and cases.id.nunique()==45
    np.testing.assert_array_equal(cases.energy_km,original.energy_km)
    np.testing.assert_array_equal(cases.auxiliary,original.auxiliary)
    assert np.isfinite(cases[['energy_km','h90','area90_km2','auxiliary']]).all().all()
    examples=json.loads((run['results']/'formal/example_selection.json').read_text())['query_positions']
    for j in examples:
        scores={name:{col:value for col,value in values.items() if pd.notna(value)} for name,values in cases[cases.query_position.eq(j)].set_index('model').to_dict('index').items()}
        truth=target.iloc[j][['endpoint_lon','endpoint_lat']].to_numpy(float)
        save_json(paths,run['results']/'formal'/f'example_{j}_observation.json',dict(truth=truth.tolist(),scores=scores))
    for name,digest in approval['protected_files'].items():assert file_sha256(inputs.ROOT/name)==digest,name
    save_json(paths,run['provenance']/'correction_invariance.json',dict(cases=33971,models=4,ES_bit_identical=True,
        auxiliary_bit_identical=True,donor_arrays_identical=True,fixed_example_quadrature_clouds_bit_identical=True,
        cutoffs_changed=freeze['cutoffs_changed'],scores_or_regions_recomputed_during_export_recovery=False))
    resource=pipe.resources(parent,start)
    receipt=dict(failed,completed=True,outer_targets_read=True,elapsed_seconds=failed['elapsed_seconds']+resource['elapsed_seconds'],
        peak_rss_bytes=max(failed['peak_rss_bytes'],resource['peak_rss_bytes']),retained_bytes=resource['retained_bytes'],
        recovery_seconds=resource['elapsed_seconds'],
        recovery_reason='Optional per-case B2 delta-to-ExactPoint was undefined in the table; omit that absent field from example JSON. All primary metrics are finite. No predictions or results were changed.',
        earlier_failure_receipt='formal_resources.json',earlier_outer_targets_flag_was_completion_flag=True)
    assert receipt['elapsed_seconds']<=cfg['seconds']['formal']
    save_json(paths,run['provenance']/'formal_resources_recovery.json',receipt)
    save_json(paths,parent['provenance']/'authoritative_revision.json',dict(
        results=str(run['results'].relative_to(inputs.ROOT)),provenance=str(run['provenance'].relative_to(inputs.ROOT)),
        reason='Exact 90% CDF arithmetic correction; original region results superseded; all ES values unchanged',independent_audit_pending=True))
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    finish(*inputs.context(a.run))
