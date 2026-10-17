"""Materialize existing approved SST decisions. Run from the project root."""
from pathlib import Path
import copy
import json
import os
import shutil
from datetime import datetime,timezone

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from data3001.paths import project_paths,file_sha256
from data3001.sst_storage import VERSION,APPROVED_RUN,replace_sst,approved_temperature_index,read_approved
from data3001.recovery_storage import tables_equal

root=project_paths().root
audit=root/'provenance/migrations/sst_inplace_20261017_v1'
archive=root/'archive/sst_inplace_20261017_v1'
archive.mkdir(parents=True,exist_ok=True)


def write_json(path,body):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(body,indent=2)+'\n')
    os.replace(temporary,path)


for name in ['dataset_manifest.json','dataset_index.csv','dataset_schema.json','assets.json','feature_review.csv']:
    source=root/'configs'/name;target=archive/name
    if not target.exists():shutil.copy2(source,target)

parent=json.loads((archive/'dataset_manifest.json').read_text())
assert parent['version']=='per-drifter-cleaned-20261017-v2'
assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx')==parent['contract_sha256']
sources_path=audit/'approved_sources.json'
if sources_path.exists():evidence=json.loads(sources_path.read_text())
else:
    records,dependencies=approved_temperature_index(root)
    evidence={'approved_run':APPROVED_RUN,'records':records,'dependencies':dependencies}
    write_json(sources_path,evidence)
assert set(evidence['records'])==set(parent['records'])
for path,checksum in evidence['dependencies'].items():assert file_sha256(root/path)==checksum
for name in ['sst_completion.py','sst_sparse_current.py','sst_total_status.py']:
    source=root/'src/data3001'/name;target=archive/name
    if not target.exists():shutil.copy2(source,target)

journal=audit/'staging.jsonl'
staged={}
if journal.exists():
    for line in journal.read_text().splitlines():
        record=json.loads(line);staged[record['id']]=record

for n,(sid,record) in enumerate(parent['records'].items(),1):
    backup=archive/record['path'];backup.parent.mkdir(parents=True,exist_ok=True)
    source=root/record['path']
    if not backup.exists():
        assert file_sha256(source)==record['sha256'],sid
        os.link(source,backup)
    assert file_sha256(backup)==record['sha256'],sid
    target=audit/'staged'/record['path'];target.parent.mkdir(parents=True,exist_ok=True)
    if sid in staged:
        current_hash=file_sha256(target if target.exists() else source)
        assert current_hash==staged[sid]['sha256'],sid
        continue
    old=pq.read_table(backup);approved=read_approved(root,evidence['records'][sid])
    new=replace_sst(old,approved)
    assert new.column_names==old.column_names and len(new)==len(old)
    assert tables_equal(new.drop(['sst']).replace_schema_metadata(None),
                        old.drop(['sst']).replace_schema_metadata(None)),sid
    temporary=target.with_suffix('.tmp')
    pq.write_table(new,temporary,compression='zstd',compression_level=3)
    assert tables_equal(new,pq.read_table(temporary)),sid
    os.replace(temporary,target)
    a=old['sst'].to_numpy();b=new['sst'].to_numpy()
    delta=~((a==b)|(np.isnan(a)&np.isnan(b)))
    item={'id':sid,'path':record['path'],'backup_path':str(backup.relative_to(root)),
        'sha256':file_sha256(target),'rows':len(new),'changed_SST_values':int(delta.sum()),
        'filled_missing_SST':int((~np.isfinite(a)&np.isfinite(b)).sum()),
        'corrected_finite_SST':int((np.isfinite(a)&np.isfinite(b)&delta).sum()),
        'set_unaccepted_SST_to_NA':int((np.isfinite(a)&~np.isfinite(b)).sum()),
        'remaining_NA':int(np.isnan(b).sum())}
    if delta.any():
        key=old.select(['id','source_obs','time']).to_pandas()
        loc=pd.MultiIndex.from_frame(approved[['id','source_obs']]).get_indexer(
            pd.MultiIndex.from_frame(key[['id','source_obs']]))
        ledger=key.loc[delta].copy()
        ledger['before_sst_K']=a[delta];ledger['after_sst_K']=b[delta]
        selected=approved.iloc[loc[delta]]
        for name in ['sst_method','sst_reason','availability_scope']:
            ledger[name]=selected[name].to_numpy()
        ledger_path=audit/'changes'/record['pool']/f'{sid}.parquet'
        ledger_path.parent.mkdir(parents=True,exist_ok=True)
        ledger.to_parquet(ledger_path,index=False)
        item['change_ledger_path']=str(ledger_path.relative_to(root))
        item['change_ledger_sha256']=file_sha256(ledger_path)
    with journal.open('a') as stream:
        stream.write(json.dumps(item)+'\n');stream.flush();os.fsync(stream.fileno())
    staged[sid]=item
    if n%200==0:print(f'Staged and checked {n}/{parent["IDs"]} files',flush=True)

assert len(staged)==parent['IDs']
receipt={'authorized_UTC':datetime.now(timezone.utc).isoformat(),
    'scope':'Store existing approved temperature results in sst; no new feature columns or imputation rules',
    'parent_manifest_path':str((archive/'dataset_manifest.json').relative_to(root)),
    'parent_manifest_sha256':file_sha256(archive/'dataset_manifest.json'),
    'approved_sources_sha256':file_sha256(sources_path),
    'files':staged,'contract_sha256':parent['contract_sha256']}
write_json(audit/'receipt.json',receipt)

newmanifest=copy.deepcopy(parent);newmanifest['version']=VERSION
newmanifest['cleaning']['temperature']={'column':'sst','unit':'Kelvin','storage_type':'float64',
    'approved_run':APPROVED_RUN,'audit_directory':str(audit.relative_to(root)),
    'parent_manifest_path':receipt['parent_manifest_path']}
for sid,record in newmanifest['records'].items():record['sha256']=staged[sid]['sha256']
schema=json.loads((archive/'dataset_schema.json').read_text());schema['version']=VERSION
entry=next(f for f in schema['fields'] if f['name']=='sst')
entry.update(arrow_type='double',role='cleaned_official_hourly',
    cleaning='Existing SST, Kelvin. Approved source-backed fills and anomaly repairs stored in this column; original values archived. Native flags/errors retain original-estimate semantics.')
index=pd.read_csv(archive/'dataset_index.csv')
index['sha256']=index.id.astype(str).map(lambda sid:staged[sid]['sha256'])
index.to_csv(audit/'next_dataset_index.csv',index=False)
write_json(audit/'next_dataset_manifest.json',newmanifest)
write_json(audit/'next_dataset_schema.json',schema)
assets=json.loads((archive/'assets.json').read_text());assets['layout_version']='per-drifter-cleaned-1.1'
assets['current_data_status']='Total SST cleaning stored directly in sst; no extra temperature features; recovery tails physically removed; unresolved temperature quality cases retained for review'
for name in ['current_train_tracks','current_test_tracks']:
    assets['assets'][name]['version']=VERSION
    assets['assets'][name]['role']='Current cleaned observations: total SST corrections in sst; other fields and whole-ID pool unchanged; vessel-recovery tails removed'
for key,name in [('current_dataset_manifest','dataset_manifest.json'),
                 ('current_dataset_schema','dataset_schema.json'),('current_dataset_index','dataset_index.csv')]:
    assets['assets'][key]['sha256']=file_sha256(audit/('next_'+name))
write_json(audit/'next_assets.json',assets)

activation=audit/'activation.jsonl'
for n,(sid,record) in enumerate(parent['records'].items(),1):
    current=root/record['path'];candidate=audit/'staged'/record['path']
    if candidate.exists():
        assert file_sha256(candidate)==staged[sid]['sha256']
        assert file_sha256(current) in [record['sha256'],staged[sid]['sha256']]
        os.replace(candidate,current)
        with activation.open('a') as stream:
            stream.write(json.dumps({'id':sid,'sha256':staged[sid]['sha256']})+'\n')
            stream.flush();os.fsync(stream.fileno())
    else:assert file_sha256(current)==staged[sid]['sha256']
    if n%500==0:print(f'Activated {n}/{parent["IDs"]} files',flush=True)

for name in ['dataset_manifest.json','dataset_index.csv','dataset_schema.json','assets.json']:
    shutil.copy2(audit/('next_'+name),root/'configs'/('.'+name+'.tmp'))
    os.replace(root/'configs'/('.'+name+'.tmp'),root/'configs'/name)
project_paths.cache_clear()
from data3001.dataset import _manifest
_manifest.cache_clear()
summary={name:sum(item[name] for item in staged.values()) for name in
    ['rows','changed_SST_values','filled_missing_SST','corrected_finite_SST',
     'set_unaccepted_SST_to_NA','remaining_NA']}
summary.update(release=VERSION,IDs=len(staged),fields_per_ID=130)
write_json(audit/'publication.json',summary)
print(json.dumps(summary,indent=2),flush=True)
