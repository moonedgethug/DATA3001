"""Read-only census of canonical feature availability; never modifies data.

Run from the project root with .venv/bin/python. A new audit run is required
for changed inputs; re-running refuses to overwrite these audit outputs.
"""
from pathlib import Path
from collections import Counter, defaultdict
import datetime, json, time
import numpy as np
import pandas as pd
from data3001.dataset import manifest, read_track
from data3001.paths import project_paths, file_sha256

RUN = 'feature_audit_20261016_v1'
paths = project_paths()
out = paths.root / 'results/runs' / RUN
assert not (out/'summary.json').exists(), 'Use a new run rather than overwrite evidence'
m = manifest()
schema = json.loads(paths.asset('current_dataset_schema', verify=True).read_text())['fields']
dictionary = json.loads(paths.asset('preprocessing_dictionary', verify=True).read_text())
fields = {f['name']:f for f in schema}
constant = {f['name'] for f in schema if f['role'] in ['native_trajectory','decoded_metadata_companion']}
constant |= {'historical_split','pool','regime_annotation_version','regime_annotation_source',
             'official_regime_decision','official_loss_epoch','official_attached_through_epoch'}
profiles = defaultdict(dict)
totals = defaultdict(Counter)
metadata = []
id_checks = []
context = defaultdict(Counter)
examples = defaultdict(list)


def profile(segment, name, series, mask):
    n = int(mask.sum())
    if not n: return
    acc = profiles[segment].setdefault(name, Counter())
    acc['rows'] += n
    acc['IDs'] += 1
    if name in constant:
        x = series.iloc[:1]
        multiplier = n
    else:
        x = series.loc[mask]
        multiplier = 1
    missing = x.isna().to_numpy()
    nmissing = int(missing.sum()) * multiplier
    acc['null_rows'] += nmissing
    acc['IDs_with_null'] += int(nmissing > 0)
    acc['IDs_all_null'] += int(nmissing == n)
    if pd.api.types.is_numeric_dtype(x.dtype):
        a = x.to_numpy(dtype=float, na_value=np.nan)
        finite = np.isfinite(a)
        acc['infinite_rows'] += int(np.isinf(a).sum()) * multiplier
        for value, label in [(0,'zero_rows'),(-1,'minus_one_rows'),(-999,'minus_999_rows'),(-9999,'minus_9999_rows'),(-999999,'minus_999999_rows')]:
            acc[label] += int((a == value).sum()) * multiplier
        acc['negative_finite_rows'] += int((finite & (a < 0)).sum()) * multiplier
        if finite.any():
            lo, hi = float(a[finite].min()), float(a[finite].max())
            acc['minimum'] = min(acc.get('minimum',lo),lo)
            acc['maximum'] = max(acc.get('maximum',hi),hi)
    elif pd.api.types.is_bool_dtype(x.dtype):
        acc['true_rows'] += int(x.sum()) * multiplier
    elif fields[name]['arrow_type'] in ['string','binary']:
        clean = x[~x.isna()]
        acc['empty_rows'] += int(clean.isin(['',b'']).sum()) * multiplier
        tokens = ['', '-', 'unknown', 'unk', 'n/a', 'na', 'nan', 'none', 'null', '?', 'missing', '-1']
        normalized = clean.map(lambda v: v.decode('utf-8',errors='replace').strip().lower() if isinstance(v,bytes) else str(v).strip().lower())
        acc['placeholder_token_rows'] += int(normalized.isin(tokens).sum()) * multiplier
    fill = dictionary.get(name,{}).get('fill')
    if fill is not None and fill != 'NaN' and isinstance(fill,(float,int)):
        acc['declared_fill_rows'] += int(x.eq(fill).sum()) * multiplier


def add_example(key, id, frame, mask):
    if len(examples[key]) >= 4 or not mask.any(): return
    rows = frame.loc[mask,['source_obs','time_UTC','lat','lon','sst','flg_sst','ve','vn','gap']].head(1)
    for row in rows.to_dict('records'):
        examples[key].append({'id':id,**{k:str(v) if k=='time_UTC' else v for k,v in row.items()}})


started=time.monotonic()
for index,(sid,record) in enumerate(m['records'].items()):
    id=int(sid)
    frame=read_track(id,allow_test=True)
    assert frame.columns.tolist()==[f['name'] for f in schema]
    pool=record['pool']
    position=frame.position_ok.to_numpy()
    R=frame.in_R.to_numpy() & position & frame.analytical_row.to_numpy()
    D=position & frame.mapping_ok.to_numpy() & frame.lon_normalized.between(-81,-8).to_numpy() & frame.lat.between(20,55).to_numpy()
    segments={'development_all' if pool=='train' else 'test_technical':np.ones(len(frame),bool)}
    if pool=='train':
        segments['development_R_origins']=R
        segments['development_D_mapped_positions']=D
    for segment,mask in segments.items():
        n=int(mask.sum())
        if not n:continue
        t=totals[segment];t['rows']+=n;t['IDs']+=1
        for name in frame.columns:profile(segment,name,frame[name],mask)
        flags=['analytical_row','position_ok','mapping_ok','velocity_ok','sst_ok','sst1_ok','sst2_ok',
               'geometry_uncertain','coast_resolution_disagreement']
        for name in flags:t[name+'_true']+=int(frame[name].to_numpy()[mask].sum())
        for name in ['err_lon','err_lat','err_ve','err_vn','err_sst','err_sst1','err_sst2']:
            t[name+'_negative']+=int((frame[name].to_numpy()[mask]<0).sum())
        for code in [0,1,2]:t['duplicate_'+str(code)]+=int((frame.duplicate_status.to_numpy()[mask]==code).sum())
        speed=np.hypot(frame.ve.to_numpy()[mask],frame.vn.to_numpy()[mask])
        for threshold in [2,3,5]:t['speed_above_'+str(threshold)+'_m_s']+=int((speed>threshold).sum())
        t['finite_sst_but_not_usable']+=int((np.isfinite(frame.sst.to_numpy()[mask]) & ~frame.sst_ok.to_numpy()[mask]).sum())
        t['usable_position_without_SST']+=int((position[mask] & ~frame.sst_ok.to_numpy()[mask]).sum())
        t['usable_position_without_velocity']+=int((position[mask] & ~frame.velocity_ok.to_numpy()[mask]).sum())
        dt=frame.elapsed_seconds_from_previous.to_numpy()[mask]
        absent=frame.absent_hours_before.to_numpy()[mask]
        t['gap_intervals']+=int((absent>0).sum())
        t['absent_grid_hours']+=int(np.maximum(absent,0).sum())
        t['nonpositive_intervals']+=int((np.isfinite(dt)&(dt<=0)).sum())
        t['non_hourly_positive_intervals']+=int((np.isfinite(dt)&(dt>0)&(dt%3600!=0)).sum())
        for season in range(4):
            sel=mask & frame.season.eq(season).to_numpy()
            if not sel.any():continue
            c=context[(segment,str(season))]
            c['rows']+=int(sel.sum());c['IDs']+=1
            for flag in ['sst_ok','sst1_ok','sst2_ok','velocity_ok','mapping_ok']:
                c[flag+'_true']+=int(frame[flag].to_numpy()[sel].sum())
        for name in ['flg_sst','flg_sst1','flg_sst2','regime','location_type','duplicate_status']:
            for value,count in frame.loc[mask,name].value_counts(dropna=False).items():
                context[(segment,name)]['value_'+str(value)]+=int(count)
    # ID-grain metadata are recorded once, not thousands of times as independent samples.
    keep=[f['name'] for f in schema if f['role'] in ['native_trajectory','decoded_metadata_companion']]
    row={k:frame[k].iloc[0] for k in keep}
    for k,v in list(row.items()):
        if isinstance(v,bytes):row[k]=v.hex()
    metadata.append({'pool':pool,'R_visiting_ID':bool(R.any()),**row})
    # Deterministic per-ID key/gap checks; no thresholds are fitted to test outcomes.
    id_checks.append({'id':id,'pool':pool,'rows':len(frame),'R_origins':int(R.sum()),
        'time_null':int(frame.time.isna().sum()),'position_invalid':int((~position).sum()),
        'velocity_unusable':int((~frame.velocity_ok).sum()),'SST_unusable':int((~frame.sst_ok).sum()),
        'gap_intervals':int((frame.absent_hours_before>0).sum()),
        'absent_hours':int(frame.absent_hours_before.clip(lower=0).sum()),
        'max_absent_hours':int(frame.absent_hours_before.max()),
        'duplicate_time_keys':int(frame.time.duplicated(keep=False).sum()),
        'source_obs_duplicates':int(frame.source_obs.duplicated().sum()),
        'unexplained_nonfirst_displacement_missing':int((frame.interval_net_ve.isna() & frame.index.to_series().gt(0)).sum())})
    if pool=='train':
        add_example('missing_SST_with_position',id,frame,position & frame.sst.isna().to_numpy())
        add_example('finite_SST_rejected',id,frame,position & np.isfinite(frame.sst.to_numpy()) & ~frame.sst_ok.to_numpy())
        add_example('negative_position_uncertainty',id,frame,position & ((frame.err_lon<0)|(frame.err_lat<0)).to_numpy())
        add_example('missing_velocity',id,frame,position & ~frame.velocity_ok.to_numpy())
        add_example('timestamp_gap',id,frame,frame.absent_hours_before.gt(0).to_numpy())
    if (index+1)%200==0:print(f'Profiled {index+1}/3741 IDs in {time.monotonic()-started:.1f}s',flush=True)

records=[]
for segment,cols in profiles.items():
    for name,a in cols.items():
        records.append({'segment':segment,'feature':name,'role':fields[name]['role'],'type':fields[name]['arrow_type'],
                        **a,'null_pct':100*a['null_rows']/a['rows'],
                        'declared_fill':dictionary.get(name,{}).get('fill')})
pd.DataFrame(records).to_csv(out/'feature_profile.csv',index=False)
pd.DataFrame(metadata).to_csv(out/'metadata_by_ID.csv',index=False)
pd.DataFrame(id_checks).to_csv(out/'per_ID_checks.csv',index=False)
pd.DataFrame([{'segment':key[0],'stratum':key[1],**v} for key,v in context.items()]).to_csv(out/'context_counts.csv',index=False)
summary={'release':m['version'],'dataset_manifest_sha256':file_sha256(paths.asset('current_dataset_manifest')),
         'contract_sha256':file_sha256(paths.asset('english_contract')),'fields_audited':len(schema),
         'IDs_audited':len(id_checks),'rows_audited':sum(v['rows'] for v in id_checks),
         'segments':{k:dict(v) for k,v in totals.items()},'examples':dict(examples),
         'all_input_file_hashes_verified_on_read':True,'data_modified':False,'imputation_performed':False,
         'test_scope':'fixed technical counts only; recommendations use development data',
         'elapsed_seconds':time.monotonic()-started}
with (out/'summary.json').open('x') as f:json.dump(summary,f,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))
print(json.dumps({k:v for k,v in summary.items() if k!='examples'},indent=2),flush=True)
