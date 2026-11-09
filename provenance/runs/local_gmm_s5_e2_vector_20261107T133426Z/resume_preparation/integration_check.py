"""Compare formal integrated rows against two retained batches; never publish scores."""
import time
import json
import pandas as pd
import numpy as np
from data3001.modelling.continuous_models import local_gmm_s5_e2_pipeline as p
from data3001.modelling.continuous_models.local_gmm_s5_e2_scoreopt_validation import compare_scores
name='local_gmm_s5_e2_vector_20261107T133426Z'
started=time.monotonic();p.initialise(name,'energy','C_T0',[1,2,3]);s=p.STATE
assert s['pool'] is s['geo'] is s['index'] is None
count=0
for batch in [0,67]:
    files=p.batch_paths(s['run'],'C_T0',batch);old=pd.read_parquet(files['energy']).set_index(['query_position','model'])
    for rec in p.previous_io.read_bundle(files['parameters']):
        truth=s['target'].iloc[rec['query_position']][['endpoint_lon','endpoint_lat']].to_numpy(float)
        for row in p.energy_rows(rec,truth):
            expected=old.loc[(row['query_position'],row['model'])].to_dict()
            expected['sample_count']=int(expected['sample_count']);compare_scores(expected,row)
            for field in ['id','origin_source_obs','horizon_days','pairs','independent_ids','largest_id_share','ci_unavailable_mass','fallback']:
                assert row[field]==expected[field],field
        count+=1
assert count==64 and not s['guard'].outcomes_read and not s['guard'].denied
result=dict(passed=True,queries=count,candidates=[1,2,3],complete_ES_replicates_and_variance_verified=True,
    metadata_verified=True,formal_outputs_modified=False,outer_targets_read=False,final_test_access=False,
    elapsed_seconds=time.monotonic()-started)
p.save_json(s['paths'],s['run']['provenance']/'resume_preparation/integration_check.json',result)
print(json.dumps(result),flush=True)
