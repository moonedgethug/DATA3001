"""Independent readback and reconciliation of the completed downloaded subset."""
from data3001.paths import legacy_path, asset_path, project_paths, ensure_output_path, frozen_action
import hashlib
import json
import math
import time
from pathlib import Path
import numpy as np
import pandas as pd
import zarr
from data3001.acquisition.acquire_hourly import ROOT, Snapshot, metadata, sha, json_save, utcnow
from data3001.acquisition.rules import split_id


@frozen_action
def main():
    started=time.monotonic()
    snap=Snapshot();meta,offsets,global_frame=metadata(snap)
    selected=pd.read_csv(legacy_path('manifests/acquired_ids.csv'),dtype={'id':str})
    export=json.loads((legacy_path('manifests/subset_export.json')).read_text())
    if export['status']!='PASS' or sha(legacy_path('manifests/acquired_ids.csv'))!=export['selected_ids_sha256']:
        raise RuntimeError('Export selection identity mismatch')
    subset=zarr.open_consolidated(legacy_path('raw/hourly_subset_v2.01.1.zarr'),mode='r')
    original=global_frame.set_index('id').loc[selected.id]
    for col in ['split','source_traj_index','source_obs_start','source_obs_end_exclusive','source_rowsize']:
        if original[col].tolist()!=selected[col].tolist():
            raise RuntimeError('Acquired/global manifest mismatch: '+col)
    if subset['id'][:].astype(str).tolist()!=selected.id.tolist():
        raise RuntimeError('Exported IDs do not match selected source trajectories')
    if not np.array_equal(subset['rowsize'][:],selected.source_rowsize):
        raise RuntimeError('Ragged sizes changed')
    if any(split_id(row.id)!=row.split for row in global_frame.itertuples()):
        raise RuntimeError('Global split changed')
    # Verify output afresh, not merely trust the export's stored PASS.
    for item in export['source_selected_and_exported_fields']:
        array=subset[item['variable']];h=hashlib.sha256()
        for a in range(0,len(array),250000):
            h.update(array[a:min(a+250000,len(array))].tobytes())
        if h.hexdigest()!=item['source_selected_value_sha256']:
            raise RuntimeError('Independent output hash mismatch: '+item['variable'])
    # Determine the actual corpus cutoff rather than parse malformed coverage attrs.
    spec=snap.spec('time');first=np.inf;last=-np.inf;finite_count=0
    for k in range(math.ceil(spec['shape'][0]/spec['chunks'][0])):
        t=snap.chunk('time',k);finite=t[np.isfinite(t)]
        if len(finite):
            first=min(first,float(finite.min()));last=max(last,float(finite.max()));finite_count+=len(finite)
    corpus_time={'start_epoch_seconds':first,'end_epoch_seconds':last,'finite_timestamps':finite_count,
        'start_UTC':pd.to_datetime(first,unit='s',utc=True).isoformat(),
        'end_UTC':pd.to_datetime(last,unit='s',utc=True).isoformat(),
        'source_attributes_preserved_verbatim':snap.meta['.zattrs'],
        'rule':'Actual min/max of every time chunk in the pinned source asset; no trajectory outcomes used for model/domain tuning'}
    json_save(legacy_path('metadata/corpus_time_coverage.json'),corpus_time)
    # Completeness/profile every acquired ID, without producing predictive scores.
    counts=selected.source_rowsize.to_numpy(dtype=np.int64)
    out_offsets=np.concatenate([[0],np.cumsum(counts)])
    profiles=[]
    for row,a,b in zip(selected.itertuples(),out_offsets[:-1],out_offsets[1:]):
        t=subset['time'][a:b];lon=subset['lon'][a:b];lat=subset['lat'][a:b];status=subset['drogue_status'][a:b]
        valid=np.isfinite(t)&np.isfinite(lon)&np.isfinite(lat)&(lat>=-90)&(lat<90)
        finite=t[np.isfinite(t)];changes=np.diff(t)
        profiles.append({'id':row.id,'split':row.split,'also_visits_R':bool(row.also_visits_R),
            'source_records':int(b-a),'local_records':len(t),'position_time_valid':int(valid.sum()),
            'duplicate_timestamps':int(len(finite)-len(np.unique(finite))),
            'nonincreasing_time_steps':int(np.count_nonzero(changes<=0)),
            'nonhourly_time_steps':int(np.count_nonzero(changes!=3600)),
            'start_UTC':pd.to_datetime(finite.min(),unit='s',utc=True).isoformat(),
            'end_UTC':pd.to_datetime(finite.max(),unit='s',utc=True).isoformat(),
            'unknown_source_drogue_flags':int(np.count_nonzero(~np.isin(status,[0,1]))),
            'source_drogue_state_changes':int(np.count_nonzero(np.diff(status)!=0)),
            'usable_rows_with_missing_SST':int(np.count_nonzero(valid&~np.isfinite(subset['sst'][a:b])))})
    profile=pd.DataFrame(profiles)
    profile.to_csv(legacy_path('audit/acquired_trajectory_profile.csv'),index=False)
    if (profile.source_records!=profile.local_records).any():
        raise RuntimeError('Source/local per-ID row-count mismatch')
    # Raw bad records are retained. Record QC risks rather than silently delete them.
    nobjects=snap.verify()
    authority=json.loads((legacy_path('manifests/authority.json')).read_text())
    if sha(authority['authoritative_contract'])!=authority['contract_sha256']:
        raise RuntimeError('Authoritative contract changed during acquisition')
    code_hashes={p.name:sha(p) for p in sorted((legacy_path('scripts')).glob('*.py'))}
    bound_files=['manifests/authority.json','manifests/source_snapshot.json','manifests/global_id_split.csv',
        'manifests/acquired_ids.csv','geometry/release_R.geojson','geometry/acquisition_envelope.geojson',
        'metadata/object_inventory.json','metadata/variable_dictionary.json','metadata/environment_lock.txt',
        'metadata/trajectory_metadata.npz','tests/test_rules.py','audit/standard_reader_check.json']
    result={'acquisition_status':'PASS','verified_UTC':utcnow(),'source_version':'2.01.1','source_IDs':len(global_frame),
        'source_observations':int(offsets[-1]),'acquired_IDs':len(selected),'acquired_observations':int(counts.sum()),
        'R_IDs':int(selected.also_visits_R.sum()),'downstream_only_IDs':int((~selected.also_visits_R).sum()),
        'split_counts':selected.split.value_counts().to_dict(),
        'R_split_counts':selected[selected.also_visits_R].split.value_counts().to_dict(),
        'corpus_start_UTC':corpus_time['start_UTC'],'corpus_cutoff_UTC':corpus_time['end_UTC'],
        'source_fields_retained':export['source_fields'],'source_objects_SHA256_verified':nobjects,
        'raw_source_bytes':sum(v['size'] for v in snap.receipts.values()),
        'local_subset_bytes':sum(p.stat().st_size for p in (legacy_path('raw/hourly_subset_v2.01.1.zarr')).rglob('*') if p.is_file()),
        'completeness_counts_reconciled':True,'subset_value_hashes_rechecked':True,
        'duplicate_timestamps':int(profile.duplicate_timestamps.sum()),
        'nonincreasing_time_steps':int(profile.nonincreasing_time_steps.sum()),
        'nonhourly_time_steps':int(profile.nonhourly_time_steps.sum()),
        'position_time_invalid_rows_retained':int((profile.source_records-profile.position_time_valid).sum()),
        'missing_SST_position_valid_rows_retained':int(profile.usable_rows_with_missing_SST.sum()),
        'unknown_source_drogue_flags':int(profile.unknown_source_drogue_flags.sum()),
        'geometry_selection_test_IDs_used':0,'final_D_frozen':False,'formal_cleaning_complete':False,
        'formal_support_audit_complete':False,'model_fitting_or_final_test_evaluation_performed':False,
        'processing_code_SHA256':code_hashes,'bound_file_SHA256':{p:sha(legacy_path(p)) for p in bound_files},
        'elapsed_seconds':round(time.monotonic()-started,2)}
    json_save(legacy_path('audit/acquisition_verification.json'),result)
    snapshot=json.loads((legacy_path('manifests/source_snapshot.json')).read_text())
    snapshot.update({'actual_corpus_start_UTC':corpus_time['start_UTC'],'actual_corpus_cutoff_UTC':corpus_time['end_UTC'],
        'acquired_IDs':len(selected),'acquired_observations':int(counts.sum()),'full_available_trajectories':True,
        'acquisition_complete':True,'final_D_frozen':False,'final_receipt':'audit/acquisition_verification.json'})
    json_save(legacy_path('manifests/source_snapshot.json'),snapshot)
    # Update the bound hash after the intentional snapshot status update.
    result['bound_file_SHA256']['manifests/source_snapshot.json']=sha(legacy_path('manifests/source_snapshot.json'))
    json_save(legacy_path('audit/acquisition_verification.json'),result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
