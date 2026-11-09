"""Read-only time-boundary audit of the fixed 338/45 development cohorts.

Writes only new audit artifacts beside this script. Does not import model code.
"""
from pathlib import Path
import hashlib
import json
import time

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
E7 = ROOT / 'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z'
KEYS = ['id', 'origin_source_obs', 'horizon_days']
META = ['id', 'WMO', 'start_date', 'end_date', 'start_lat', 'start_lon',
        'end_lat', 'end_lon', 'typedeath']


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=str, ensure_ascii=False)+'\n')


def epoch(date, clock):
    return pd.Timestamp(f'{date} {clock}', tz='UTC').timestamp()


def lon_difference(a, b):
    return abs((a-b+180)%360-180)


start = time.monotonic()
train = pd.read_parquet(E7/'training_coordinates.parquet')
query = pd.read_parquet(E7/'query_coordinates.parquet')
targets = pd.read_parquet(E7/'outer_targets.parquet')
assert len(train)==265393 and train.id.nunique()==338
assert len(query)==33971 and query.id.nunique()==45
assert not (set(train.id) & set(query.id))
assert query[KEYS].equals(targets[KEYS])
train = train.assign(cohort='train')
validation = targets.assign(cohort='validation')
active = pd.concat([train, validation], ignore_index=True)
ids = sorted(active.id.unique().tolist())
assert len(ids)==383
roster = active.groupby(['id','cohort'],as_index=False).agg(active_pairs=('id','size'))
roster.to_csv(OUT/'cohort_roster.csv',index=False)
paths = [ROOT/'data/train'/f'{i}.parquet' for i in ids]
paths += [E7/'training_coordinates.parquet', E7/'query_coordinates.parquet', E7/'outer_targets.parquet']
before = {str(p.relative_to(ROOT)):sha(p) for p in paths}
write_json('input_hashes_before.json',before)

with np.load(ROOT/'archive/data_before_release_20261016/reference/acquisition/metadata/trajectory_metadata.npz',allow_pickle=False) as saved:
    mask = np.isin(saved['id'],ids)
    metadata = pd.DataFrame({key:saved[key][mask] for key in META}).set_index('id')
assert len(metadata)==383 and metadata.index.is_unique

official = {}
malformed = []
for path in sorted((OUT/'sources').glob('dirfl*.dat')):
    for line_number, line in enumerate(path.read_text().splitlines(),1):
        fields = line.split()
        try:
            identifier = int(fields[0])
        except (ValueError,IndexError):
            continue
        if identifier not in ids:
            continue
        if len(fields)!=15:
            malformed.append(dict(id=identifier,file=path.name,line_number=line_number,row=line))
            continue
        item = dict(id=identifier, official_wmo=int(fields[1]),
                    official_start_epoch=epoch(fields[4],fields[5]),
                    official_start_lat=float(fields[6]),official_start_lon=float(fields[7]),
                    official_end_epoch=epoch(fields[8],fields[9]),
                    official_end_lat=float(fields[10]),official_end_lon=float(fields[11]),
                    official_typedeath=int(fields[14]),source_file=path.name,
                    source_line=line_number,official_row=line)
        official.setdefault(identifier,[]).append(item)
write_json('malformed_target_directory_rows.json',malformed)
records=[]; anomalies=[]; pair_checks=[]
canonical_columns=['id','source_obs','time','start_date','end_date','start_lat','start_lon','end_lat','end_lon','typedeath']
for count, identifier in enumerate(ids):
    canonical = pd.read_parquet(ROOT/'data/train'/f'{identifier}.parquet', columns=canonical_columns)
    assert canonical.id.nunique()==1 and int(canonical.id.iloc[0])==identifier
    native = metadata.loc[identifier]
    pairs = active[active.id==identifier].copy()
    r = dict(id=identifier,cohort=pairs.cohort.iloc[0],active_pairs=len(pairs),
             canonical_rows=len(canonical),canonical_first_epoch=float(canonical.time.min()),
             canonical_last_epoch=float(canonical.time.max()),native_wmo=int(native.WMO),
             native_start_epoch=float(native.start_date),native_end_epoch=float(native.end_date),
             native_typedeath=int(native.typedeath))
    metadata_agrees=True
    for field in ['start_date','end_date','start_lat','start_lon','end_lat','end_lon','typedeath']:
        metadata_agrees &= canonical[field].nunique(dropna=False)==1
        metadata_agrees &= bool(np.isclose(float(canonical[field].iloc[0]),float(native[field]),rtol=0,atol=1e-5,equal_nan=True))
    r['canonical_metadata_matches_acquisition']=bool(metadata_agrees)
    candidates=official.get(identifier,[])
    r['official_rows_found']=len(candidates)
    r['identity_verified']=False
    if len(candidates)!=1:
        r['boundary_status']='unresolved';r['unresolved_reason']='missing_or_duplicate_official_id'
        records.append(r);continue
    r.update(candidates[0])
    wmo_match = int(native.WMO)==r['official_wmo']
    start_day_match = bool(np.isfinite(native.start_date) and int(native.start_date//86400)==int(r['official_start_epoch']//86400))
    end_day_match = bool(np.isfinite(native.end_date) and int(native.end_date//86400)==int(r['official_end_epoch']//86400))
    r['start_lat_difference_deg']=abs(float(native.start_lat)-r['official_start_lat'])
    r['start_lon_difference_deg']=lon_difference(float(native.start_lon),r['official_start_lon'])
    r['end_lat_difference_deg']=abs(float(native.end_lat)-r['official_end_lat'])
    r['end_lon_difference_deg']=lon_difference(float(native.end_lon),r['official_end_lon'])
    start_coordinate_match=max(r['start_lat_difference_deg'],r['start_lon_difference_deg'])<=0.0051
    end_coordinate_match=max(r['end_lat_difference_deg'],r['end_lon_difference_deg'])<=0.0051
    r.update(wmo_match=bool(wmo_match),start_day_match=bool(start_day_match),end_day_match=bool(end_day_match),
             start_coordinate_match=bool(start_coordinate_match),end_coordinate_match=bool(end_coordinate_match),
             start_delta_seconds=r['official_start_epoch']-float(native.start_date),
             end_delta_seconds=r['official_end_epoch']-float(native.end_date))
    r['identity_verified']=bool(wmo_match and start_day_match and start_coordinate_match and metadata_agrees)
    reconciled=bool(r['identity_verified'] and end_day_match and end_coordinate_match)
    r['official_boundary_reconciled']=reconciled
    r['boundary_status']=('time_precision_difference' if r['start_delta_seconds'] or r['end_delta_seconds'] else 'consistent') if reconciled else 'unresolved'
    r['unresolved_reason']=';'.join(key for key,passed in [('canonical_metadata',metadata_agrees),('wmo',wmo_match),('start_day',start_day_match),('start_coordinates',start_coordinate_match),('end_day',end_day_match),('end_coordinates',end_coordinate_match)] if not passed)
    # Arrow-backed timestamps may be microseconds; do not assume int64 means ns.
    origin_epoch=pd.to_datetime(pairs.origin_time_UTC,utc=True).map(lambda value:value.timestamp()).to_numpy(float)
    assert np.allclose(origin_epoch+7*86400,pairs.target_epoch.to_numpy(float),rtol=0,atol=1e-6)
    endpoint_epoch=pairs.matched_endpoint_epoch.to_numpy(float)
    pair_before=origin_epoch<r['official_start_epoch']
    pair_after=endpoint_epoch>r['official_end_epoch']
    native_before=origin_epoch<float(native.start_date)
    native_after=endpoint_epoch>float(native.end_date)
    r.update(active_origins_before_official=int(pair_before.sum()),active_endpoints_after_official=int(pair_after.sum()),
             active_pairs_outside_official=int((pair_before|pair_after).sum()),
             active_origins_before_native=int(native_before.sum()),active_endpoints_after_native=int(native_after.sum()),
             canonical_rows_before_official=int((canonical.time<r['official_start_epoch']).sum()),
             canonical_rows_after_official=int((canonical.time>r['official_end_epoch']).sum()),
             canonical_rows_before_native=int((canonical.time<float(native.start_date)).sum()),
             canonical_rows_after_native=int((canonical.time>float(native.end_date)).sum()))
    if reconciled and (pair_before|pair_after).any():
        r['boundary_status']='used_pairs_outside_official'
    flagged=(pair_before|pair_after|native_before|native_after) | (not reconciled)
    if flagged.any():
        p=pairs.loc[flagged,KEYS+['cohort','origin_time_UTC','matched_endpoint_epoch','endpoint_source_obs','origin_cell_1','destination_cell_1']].copy()
        p['origin_before_official']=pair_before[flagged];p['endpoint_after_official']=pair_after[flagged]
        p['origin_before_native']=native_before[flagged];p['endpoint_after_native']=native_after[flagged]
        p['boundary_reconciled']=reconciled;p['boundary_status']=r['boundary_status'];pair_checks.append(p)
    for kind,mask in [('before_official',canonical.time<r['official_start_epoch']),('after_official',canonical.time>r['official_end_epoch'])]:
        if mask.any():
            a=canonical.loc[mask,['id','source_obs','time']].copy();a['relation']=kind;a['boundary_reconciled']=reconciled;anomalies.append(a)
    records.append(r)
    if (count+1)%100==0:print('checked',count+1,'/383',flush=True)

ledger=pd.DataFrame(records)
ledger.to_csv(OUT/'boundary_ledger.csv',index=False)
pd.concat(pair_checks,ignore_index=True).to_csv(OUT/'active_pair_flags.csv',index=False) if pair_checks else pd.DataFrame(columns=KEYS).to_csv(OUT/'active_pair_flags.csv',index=False)
pd.concat(anomalies,ignore_index=True).to_csv(OUT/'canonical_boundary_rows.csv',index=False) if anomalies else pd.DataFrame(columns=['id','source_obs','time','relation']).to_csv(OUT/'canonical_boundary_rows.csv',index=False)
after={str(p.relative_to(ROOT)):sha(p) for p in paths}
assert before==after
write_json('source_integrity.json',dict(files_checked=len(before),all_unchanged=True,after=after))
summary=dict(cohort_ids=len(ledger),train_ids=int((ledger.cohort=='train').sum()),validation_ids=int((ledger.cohort=='validation').sum()),
             training_pairs=len(train),validation_pairs=len(validation),canonical_rows=int(ledger.canonical_rows.sum()),
             status_counts=ledger.groupby(['cohort','boundary_status']).size().to_dict().__str__(),
             active_pairs_outside_official=int(ledger.active_pairs_outside_official.sum()),
             active_pairs_on_unresolved_ids=int(ledger.loc[ledger.boundary_status=='unresolved','active_pairs'].sum()),
             canonical_rows_before_official=int(ledger.canonical_rows_before_official.sum()),canonical_rows_after_official=int(ledger.canonical_rows_after_official.sum()),
             elapsed_seconds=time.monotonic()-start)
write_json('summary.json',summary)
print(json.dumps(summary,indent=2),flush=True)
print('UNRESOLVED',ledger.loc[ledger.boundary_status=='unresolved',['id','cohort','unresolved_reason','start_delta_seconds','end_delta_seconds','active_pairs_outside_official']].to_json(orient='records'),flush=True)
