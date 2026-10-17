"""Publish an exact drogue-state column consolidation, with resumable staging."""
from pathlib import Path
from collections import Counter
import copy,json,os,shutil

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from data3001.paths import project_paths,file_sha256
from data3001.drogue_storage import materialize_drogue_status,VERSION,POLICY,ATTRIBUTES
from data3001.recovery_storage import tables_equal

root=project_paths().root;audit=root/'provenance/migrations/drogue_status_inplace_20261017_v1'
archive=root/'archive/drogue_status_inplace_20261017_v1'
parent_path=archive/'configs/dataset_manifest.json'
parent=json.loads(parent_path.read_text());assert parent['version']=='per-drifter-cleaned-20261017-v4'
assert (audit/'pairs_before.json').exists()
assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx')==parent['contract_sha256']


def write_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n');os.replace(temporary,path)


journal=audit/'staging.jsonl';staged={}
if journal.exists():
    for line in journal.read_text().splitlines():
        item=json.loads(line);staged[item['id']]=item
for n,(sid,record) in enumerate(parent['records'].items(),1):
    current=root/record['path'];backup=archive/record['path'];backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():
        assert file_sha256(current)==record['sha256'],sid
        os.link(current,backup)
    assert file_sha256(backup)==record['sha256'],sid
    target=audit/'staged'/record['path'];target.parent.mkdir(parents=True,exist_ok=True)
    if sid in staged:
        assert file_sha256(target if target.exists() else current)==staged[sid]['sha256'],sid
        continue
    old=pq.read_table(backup);new=materialize_drogue_status(old)
    assert new['drogue_status'].equals(old['regime'])
    assert tables_equal(new.drop(['drogue_status']).replace_schema_metadata(None),
                        old.drop(['drogue_status','regime']).replace_schema_metadata(None))
    temporary=target.with_suffix('.tmp');pq.write_table(new,temporary,compression='zstd',compression_level=3)
    assert tables_equal(new,pq.read_table(temporary));os.replace(temporary,target)
    values=new['drogue_status'].to_numpy()
    item={'id':sid,'path':record['path'],'backup_path':str(backup.relative_to(root)),
          'rows':len(new),'sha256':file_sha256(target),
          'native_values_changed':int((values!=old['drogue_status'].to_numpy()).sum()),
          'state_counts':{str(v):int((values==v).sum()) for v in [-1,0,1]}}
    with journal.open('a') as stream:
        stream.write(json.dumps(item)+'\n');stream.flush();os.fsync(stream.fileno())
    staged[sid]=item
    if n%250==0:print(f'Staged and verified {n}/{parent["IDs"]} files',flush=True)
assert len(staged)==parent['IDs']
counts=Counter()
for item in staged.values():counts.update(item['state_counts'])
assert counts==Counter(parent['regime_counts'])
ledger=[]
for sid,item in staged.items():
    if not item['native_values_changed']:continue
    frame=pq.read_table(root/item['backup_path'],columns=['id','source_obs','time','drogue_status','regime']).to_pandas()
    changed=frame.drogue_status.ne(frame.regime)
    frame=frame.loc[changed].rename(columns={'drogue_status':'previous_native_flag','regime':'new_drogue_status'})
    ledger.append(frame)
pd.concat(ledger,ignore_index=True).to_parquet(audit/'changes.parquet',index=False)
receipt={'policy':POLICY,'parent_manifest_path':str(parent_path.relative_to(root)),
    'parent_manifest_sha256':file_sha256(parent_path),'files':staged,
    'change_ledger_path':str((audit/'changes.parquet').relative_to(root)),
    'change_ledger_sha256':file_sha256(audit/'changes.parquet'),
    'pairs_before_sha256':file_sha256(audit/'pairs_before.json')}
write_json(audit/'receipt.json',receipt)

manifest=copy.deepcopy(parent);manifest['version']=VERSION;manifest['fields']=129
manifest['prepared_fields']=[c for c in manifest['prepared_fields'] if c!='regime']
manifest['drogue_status_counts']=manifest.pop('regime_counts')
manifest['cleaned_field_attributes']={**manifest.get('cleaned_field_attributes',{}),'drogue_status':ATTRIBUTES}
manifest['cleaning']['drogue_status']={'policy':POLICY,'column':'drogue_status','removed_column':'regime',
    'audit_directory':str(audit.relative_to(root)),
    'contract_mapping':'Prior implementation field regime now stored in drogue_status; state semantics and qualification unchanged'}
for sid,item in staged.items():manifest['records'][sid]['sha256']=item['sha256']
schema=json.loads((archive/'configs/dataset_schema.json').read_text());schema['version']=VERSION
schema['fields']=[f for f in schema['fields'] if f['name']!='regime']
field=next(f for f in schema['fields'] if f['name']=='drogue_status')
field.update(role='cleaned_official_hourly',cleaned_attributes=ATTRIBUTES,
    cleaning='Exact prior regime values transferred here; -1 unknown, 0 undrogued, 1 drogued. Original binary product flags archived. No further imputation or state inference.')
index=pd.read_csv(archive/'configs/dataset_index.csv')
index['sha256']=index.id.astype(str).map(lambda sid:staged[sid]['sha256'])
index.to_csv(audit/'next_dataset_index.csv',index=False)
write_json(audit/'next_dataset_manifest.json',manifest);write_json(audit/'next_dataset_schema.json',schema)
assets=json.loads((archive/'configs/assets.json').read_text());assets['layout_version']='per-drifter-cleaned-1.3'
assets['current_data_status']='Cleaned three-state drogue_status stored in original column; redundant regime physically removed; total SST and all other fields unchanged'
for key in ['current_train_tracks','current_test_tracks']:
    assets['assets'][key]['version']=VERSION
    assets['assets'][key]['role']='129 retained fields: final three-state drogue_status, no regime feature; cleaned sst; unchanged complete-ID pool and retained records'
for key,name in [('current_dataset_manifest','dataset_manifest.json'),
                 ('current_dataset_schema','dataset_schema.json'),('current_dataset_index','dataset_index.csv')]:
    assets['assets'][key]['sha256']=file_sha256(audit/('next_'+name))
write_json(audit/'next_assets.json',assets)
for n,(sid,item) in enumerate(staged.items(),1):
    source=audit/'staged'/item['path'];destination=root/item['path']
    if source.exists():
        assert file_sha256(source)==item['sha256']
        assert file_sha256(destination) in [parent['records'][sid]['sha256'],item['sha256']]
        os.replace(source,destination)
        with (audit/'activation.jsonl').open('a') as stream:
            stream.write(json.dumps({'id':sid,'sha256':item['sha256']})+'\n');stream.flush();os.fsync(stream.fileno())
    else:assert file_sha256(destination)==item['sha256']
    if n%500==0:print(f'Activated {n}/{len(staged)} files',flush=True)
for name in ['dataset_manifest.json','dataset_index.csv','dataset_schema.json','assets.json']:
    temporary=root/'configs'/('.'+name+'.tmp');shutil.copy2(audit/('next_'+name),temporary)
    os.replace(temporary,root/'configs'/name)
summary={'version':VERSION,'IDs':len(staged),'rows':sum(r['rows'] for r in staged.values()),
    'fields_per_ID':129,'removed_column':'regime','state_counts':dict(counts),
    'native_values_changed':sum(r['native_values_changed'] for r in staged.values()),'new_feature_columns':[]}
write_json(audit/'publication.json',summary);print(json.dumps(summary,indent=2),flush=True)
