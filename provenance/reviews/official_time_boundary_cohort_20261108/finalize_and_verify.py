"""Independent arithmetic checks and evidence-based classification refinement."""
from pathlib import Path
import hashlib
import json
import re
import h5py
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
E7=ROOT/'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z'
ledger=pd.read_csv(OUT/'boundary_ledger.csv')
assert len(ledger)==383 and ledger.id.nunique()==383
assert ledger.identity_verified.all()
assert (ledger.official_rows_found==1).all()
assert all(x['matches_20261016_source'] for x in json.loads((OUT/'source_receipts.json').read_text()))
assert json.loads((OUT/'malformed_target_directory_rows.json').read_text())==[]

# Separate parsing of the original directory date strings.
for r in ledger.itertuples(index=False):
    times=re.findall(r'\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}',r.official_row)
    assert len(times)==3
    assert pd.Timestamp(times[0],tz='UTC').timestamp()==r.official_start_epoch
    assert pd.Timestamp(times[1],tz='UTC').timestamp()==r.official_end_epoch

train=pd.read_parquet(E7/'training_coordinates.parquet')
validation=pd.read_parquet(E7/'outer_targets.parquet')
active=pd.concat([train.assign(cohort='train'),validation.assign(cohort='validation')],ignore_index=True)
active=active.merge(ledger[['id','official_start_epoch','official_end_epoch']],on='id',validate='many_to_one')
# Numeric nominal target is independent of timestamp serialization unit.
origins=active.target_epoch.to_numpy()-active.horizon_days.to_numpy()*86400
assert (origins<active.official_start_epoch).sum()==1
assert (active.matched_endpoint_epoch>active.official_end_epoch).sum()==0
assert active.loc[origins<active.official_start_epoch,'id'].tolist()==[75447]
assert (active.loc[origins<active.official_start_epoch,'official_start_epoch'].to_numpy()-origins[origins<active.official_start_epoch]).tolist()==[60.0]
historical=pd.read_csv(OUT/'historical_boundary_pairs.csv')
assert len(historical)==2 and set(historical.horizon_days)=={7,30}
assert historical.id.unique().tolist()==[75447]
assert not historical.required_end_after_official.any()

def classification(r):
    if np.isnan(r.native_end_epoch):
        assert r.native_typedeath==0 and r.canonical_last_epoch<r.official_end_epoch
        return 'native_end_missing_official_available'
    if r.boundary_status=='unresolved':
        return 'cross_source_conflict'
    outside=(r.canonical_rows_before_official>0 or r.canonical_rows_after_official>0)
    if outside:
        discrepancy=max(r.official_start_epoch-r.canonical_first_epoch,r.canonical_last_epoch-r.official_end_epoch)
        # This threshold describes the observed discrepancy, not an eligibility tolerance.
        return 'multi_hour_record_overrun_unused' if discrepancy>3600 else 'minute_scale_hourly_boundary_unresolved'
    return 'time_precision_only'

ledger['assessment']=ledger.apply(classification,axis=1)
for name,expected in [('time_precision_only',363),('native_end_missing_official_available',11),
                      ('cross_source_conflict',5),('multi_hour_record_overrun_unused',1),
                      ('minute_scale_hourly_boundary_unresolved',3)]:
    assert int(ledger.assessment.eq(name).sum())==expected
ledger.to_csv(OUT/'boundary_assessment.csv',index=False)

# Retrieve metadata already cached from verified official native files.
repair=ROOT/'provenance/migrations/position_error_repair_20261106T073218_242005Z'
registry=json.loads((repair/'full/source_registry.json').read_text())
special=ledger[ledger.assessment.isin(['cross_source_conflict','multi_hour_record_overrun_unused','minute_scale_hourly_boundary_unresolved'])].id.tolist()
receipts=[]
for identifier in special:
    for source in registry:
        if source['id']!=identifier or not source.get('inspection',{}).get('eligible'):
            continue
        path=repair/source['path'];digest=hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest==source['sha256']
        canonical=pd.read_parquet(ROOT/'data/train'/f'{identifier}.parquet',columns=['source_obs','time','lon','lat'])
        with h5py.File(path,'r') as native:
            native_time=np.asarray(native['time']).ravel()
            native_lon=np.asarray(native['longitude']).ravel()
            native_lat=np.asarray(native['latitude']).ravel()
            lookup=pd.Index(native_time).get_indexer(canonical.time)
            matched=lookup>=0
            record=dict(id=int(identifier),route=source['route'],source_url=source['url'],sha256=digest,
                        native_first_hour=float(native_time[0]),native_last_hour=float(native_time[-1]),
                        coverage_start=str(native.attrs.get('time_coverage_start')),
                        coverage_end=str(native.attrs.get('time_coverage_end')),
                        canonical_rows=len(canonical),canonical_times_found=int(matched.sum()),
                        max_lon_difference_deg=float(np.max(np.abs((native_lon[lookup[matched]]-canonical.lon.to_numpy()[matched]+180)%360-180))),
                        max_lat_difference_deg=float(np.max(np.abs(native_lat[lookup[matched]]-canonical.lat.to_numpy()[matched]))))
            receipts.append(record)
(OUT/'native_edge_evidence.json').write_text(json.dumps(receipts,indent=2)+'\n')

before=json.loads((OUT/'input_hashes_before.json').read_text())
for relative,digest in before.items():
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest

summary=dict(cohort_ids=383,training_ids=338,validation_ids=45,canonical_hourly_rows=int(ledger.canonical_rows.sum()),
             training_pairs=len(train),validation_pairs=len(validation),
             assessments=ledger.groupby(['assessment','cohort']).size().reset_index(name='ids').to_dict('records'),
             verified_official_identity_ids=383,missing_or_duplicate_official_ids=0,
             active_endpoint_overruns=0,active_origin_boundary_cases=1,
             historical_qualified_pairs=int(pd.read_csv(OUT/'historical_pair_boundary_counts.csv').qualified_pairs.sum()),
             historical_endpoint_or_required_end_overruns=0,historical_origin_boundary_cases=2,
             unchanged_input_files=len(before),independent_checks_passed=True,
             original_twelve_retained=True,model_execution=False)
(OUT/'final_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2),flush=True)
