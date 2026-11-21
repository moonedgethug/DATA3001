"""Independent technical acceptance of the versioned handover additions.

This does not re-audit every raw field or fit/evaluate a prediction model.
The accepted baseline and supplied architecture audit retain those scopes.
"""
from data3001.paths import legacy_path, asset_path, project_paths, ensure_output_path, frozen_action
import json
import time
import numpy as np
import pandas as pd
import pyarrow as pa
import duckdb
from data3001.preprocessing.prep_io import BASE, OUT, sha, save_json, now, Source
from data3001.preprocessing.prep_handover import ROOT

@frozen_action
def verify():
    begin=time.monotonic();source=Source();authority=source.verify()
    receipt=json.loads((legacy_path('preparation', 'remediation_20261013', 'baseline_authority.json')).read_text())
    assert sha(legacy_path('preparation', 'config/frozen_before_test.json'))==receipt['parent_freeze_sha256']
    corrections={'scripts/prep_core.py','scripts/prep_pairs.py','tests/test_preparation.py'}
    for path,digest in receipt['parent_frozen_files'].items():
        historical=legacy_path('preparation', 'remediation_20261013', 'baseline', path.split('/')[-1]) if path in corrections else legacy_path(path)
        assert sha(historical)==digest,path
    package=json.loads((legacy_path('preparation', 'metadata/package_artifact_manifest.json')).read_text())['artifact_sha256']
    for path,digest in package.items():
        historical=legacy_path('preparation', 'remediation_20261013', 'baseline', path.split('/')[-1]) if path in corrections else legacy_path(path)
        assert sha(historical)==digest,path
    states=pd.read_parquet(legacy_path('preparation', 'remediation_20261013', 'geometry/state_index.parquet'))
    original=pd.read_parquet(legacy_path('preparation', 'geometry/state_index.parquet'))
    pd.testing.assert_frame_equal(states[original.columns],original)
    assert states[['wet_area_in_R','wet_area_in_D']].ge(0).all().all()
    assert np.isfinite(states[['wet_area_in_R','wet_area_in_D']]).all().all()
    assert (states.loc[states.R_boundary_only,'wet_area_in_R']==0).all()
    assert (states.loc[states.D_boundary_only,'wet_area_in_D']==0).all()
    assert (states.loc[states.wet_area_in_R==0,'whole_R_release_weight']==0).all()
    for _,x in states.groupby('resolution'):
        assert abs(x.whole_R_release_weight.sum()-1)<1e-12
        assert np.allclose(x.whole_R_release_weight,x.wet_area_in_R/x.wet_area_in_R.sum(),rtol=1e-12,atol=1e-15)
        assert x.wet_area_in_R.sum()>334000 and x.wet_area_in_R.sum()<335000
    con=duckdb.connect();con.execute("SET memory_limit='1500MB'");con.execute('SET threads=2')
    con.execute('SET preserve_insertion_order=false')
    folders=['support/lags','support/partials','origins']
    # Per-file grain validation bounds memory; every supplied ID and split is checked.
    input_hashes={};native_lag_rows=0
    for folder in folders:
        for p in sorted((legacy_path('preparation', folder)).glob('*.parquet')):
            id=int(p.stem);assert source.cohort.loc[id,'split']!='test'
            cp=json.loads((legacy_path('preparation', 'checkpoints', f'pairs_{id}.json')).read_text())
            digest=sha(p);assert cp['files'][str(p.relative_to(OUT))]==digest,(id,folder)
            if folder=='support/lags':
                x=pd.read_parquet(p);native_lag_rows+=len(x)
                assert (x.id==id).all() and (x.split==source.cohort.loc[id,'split']).all()
                assert not x.duplicated(['id','split','cell','season','days','scenario']).any()
                assert x[['endpoint_eligible','stopped_eligible']].ge(0).all().all()
                assert x.endpoint_eligible.le(x.candidates).all() and x.stopped_eligible.le(x.candidates).all()
            input_hashes[str(p.relative_to(BASE))]=digest
    input_hashes['preparation/metadata/trajectory_context.parquet']=sha(legacy_path('preparation', 'metadata/trajectory_context.parquet'))
    input_hashes['preparation/manifests_development_folds.csv']=sha(legacy_path('preparation', 'manifests_development_folds.csv'))
    for name in ['cell_support','lag_support']:
        p=legacy_path('preparation', 'support', f'{name}.parquet');input_hashes[str(p.relative_to(BASE))]=sha(p)
    save_json(legacy_path('preparation', 'remediation_20261013', 'input_partition_hashes.json'),{'utc':now(),'files_sha256':input_hashes})
    lag=legacy_path('preparation', 'remediation_20261013', 'support/lag_support.parquet');annual=legacy_path('preparation', 'remediation_20261013', 'support/lag_annual_support.parquet')
    con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{lag}')")
    con.execute(f"CREATE VIEW a AS SELECT * FROM read_parquet('{annual}')")
    bad=con.execute('SELECT count(*) FROM s WHERE eligible>candidates OR eligible_IDs>candidate_IDs OR (eligible=0 AND dominant_ID_share IS NOT NULL)').fetchone()[0]
    assert bad==0
    totals=con.execute('''SELECT count(*) FROM (
      SELECT split,cell,days,scenario,target,sum(candidates) c,sum(eligible) e FROM s GROUP BY ALL
      ) q JOIN a USING(split,cell,days,scenario,target) WHERE q.c<>a.candidates OR q.e<>a.eligible''').fetchone()[0]
    assert totals==0
    assert con.execute('SELECT count(*) FROM (SELECT split,cell,days,scenario,target,count(DISTINCT season) n FROM s GROUP BY ALL) WHERE n<>4').fetchone()[0]==0
    assert con.execute('SELECT count(*) FROM s WHERE split NOT IN (\'train\',\'validation\')').fetchone()[0]==0
    # Independent annual ID/concentration queries over original per-ID short-lag
    # partitions, one day/target at a time, avoid summing seasonal ID counts.
    comparisons=0
    for day in [1,2,3,4,5,6,7,9,10,14,15,21]:
        for target in ['endpoint','stopped']:
            con.execute(f'''CREATE OR REPLACE TEMP TABLE per_id AS
              SELECT split,cell,days,scenario,id,sum({target}_eligible) n FROM read_parquet('{OUT}/support/lags/*.parquet',union_by_name=true)
              WHERE days={day} GROUP BY ALL''')
            fail=con.execute(f'''WITH u AS (
              SELECT split,cell,days,scenario,sum(n) e,sum(CASE WHEN n>0 THEN 1 ELSE 0 END) ni,max(n) dominant FROM per_id GROUP BY ALL)
              SELECT count(*) FROM u JOIN a USING(split,cell,days,scenario)
              WHERE a.target='{target}' AND (u.e<>a.eligible OR u.ni<>a.eligible_IDs OR u.dominant<>a.dominant_ID_pairs)''').fetchone()[0]
            assert fail==0;comparisons+=1
    depth=pd.read_parquet(legacy_path('preparation', 'remediation_20261013', 'support/depth_hardware_metadata.parquet'))
    assert len(depth)==3224 and not depth.id.duplicated().any()
    native=pd.read_parquet(legacy_path('preparation', 'metadata/trajectory_context.parquet'));native=native[native.split!='test']
    pd.testing.assert_frame_equal(depth[['id','split','DrogueCenterDepth','typebuoy','location_type']].reset_index(drop=True),
                                   native[['id','split','DrogueCenterDepth','typebuoy','location_type']].reset_index(drop=True))
    # Stratification partitions must reconcile all original support counts.
    for name,horizon in [('depth_anchor_support','horizon_days'),('depth_lag_support','days')]:
        p=legacy_path('preparation', 'remediation_20261013', 'support', f'{name}.parquet')
        keys=['split','cell','season','scenario',horizon,'target']
        if name=='depth_anchor_support':keys.insert(1,'population')
        k=','.join(keys)
        con.execute(f"CREATE OR REPLACE VIEW depth_counts AS SELECT {k},sum(candidates) c,sum(eligible) e FROM read_parquet('{p}') GROUP BY {k}")
        if name=='depth_anchor_support':
            expected=f"SELECT {k},sum(candidates) c,sum(eligible) e FROM read_parquet('{OUT}/support/partials/*.parquet',union_by_name=true) WHERE resolution=1 GROUP BY {k}"
        else:
            expected=f"SELECT split,cell,season,scenario,days,target,candidates c,eligible e FROM s WHERE candidates>0"
        fail=con.execute(f'''SELECT count(*) FROM depth_counts d FULL OUTER JOIN ({expected}) e USING({k})
                          WHERE d.c IS DISTINCT FROM e.c OR d.e IS DISTINCT FROM e.e''').fetchone()[0]
        assert fail==0,name
    folds=pd.read_csv(legacy_path('preparation', 'remediation_20261013', 'support/R_grouped_fold_coverage.csv'))
    assert len(folds)==750 and not folds.duplicated(['development_fold','season','scenario','horizon_days','target']).any()
    assert (folds.loc[folds.eligible==0,'evaluation_status']=='not_evaluable').all()
    req=pd.read_csv(legacy_path('preparation', 'remediation_20261013', 'support/exact_duration_kernel_requirements.csv'))
    assert len(req)==1460
    assert (req.horizon_days==req.full_steps*req.lag_days+req.remainder_days).all()
    assert req.remainder_days.ge(0).all() and req.remainder_days.lt(req.lag_days).all()
    reason=json.loads((legacy_path('preparation', 'remediation_20261013', 'audit/source_reason_correction.json')).read_text())
    assert reason['source_position_technical_census']=={'rows':39107061,'bad_positions':0,'native_invalid':0}
    assert reason['all_preexisting_label_fields_equal']
    con.close()
    result={'status':'PASS_DATA_ADDITIONS_WITH_PENDING_DEPTH_POLICY_AND_365_EVIDENCE_LIMITS','utc':now(),
        'authority':authority,'baseline_frozen_files_unchanged_or_exact_archived_code':len(receipt['parent_frozen_files']),
        'baseline_key_artifacts_unchanged_or_exact_archived_code':len(package),
        'baseline_paths_changed':sorted(corrections),'input_partition_hashes':len(input_hashes),'native_lag_rows':native_lag_rows,
        'regional_area_and_unit_mass_checks':True,'annual_lag_independent_count_queries':comparisons,
        'depth_counts_reconcile_to_original_anchors_and_lags':True,'all_four_seasons_and_empty_folds_preserved':True,
        'depth_policy':'DEPTH-01 awaiting architecture decision; no primary eligibility changed',
        'baseline_full_source_field_audit':'Accepted existing audit and supplied architecture audit; not repeated here',
        'new_source_position_census':'All 39,107,061 rows; this technical invariant does not tune held-out outcomes',
        'prediction_models_fitted_or_scored':False,'elapsed_seconds':time.monotonic()-begin}
    save_json(legacy_path('preparation', 'remediation_20261013', 'audit/verification.json'),result);print(json.dumps(result,indent=2))

if __name__=='__main__':verify()
