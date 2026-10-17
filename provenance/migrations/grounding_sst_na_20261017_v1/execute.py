"""Apply the user-approved SST-only cutoff; preserve all observations/features."""
from pathlib import Path
import copy,json,os,shutil

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from data3001.paths import project_paths,file_sha256
from data3001.grounding_sst import clear_post_grounding_sst,VERSION,POLICY
from data3001.sst_total_status import post_last_good_grounding_mask
from data3001.recovery_storage import tables_equal

root=project_paths().root
audit=root/'provenance/migrations/grounding_sst_na_20261017_v1'
archive=root/'archive/grounding_sst_na_20261017_v1';archive.mkdir(parents=True,exist_ok=True)


def write_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n');os.replace(temporary,path)


for name in ['configs/dataset_manifest.json','configs/dataset_index.csv','configs/dataset_schema.json',
             'configs/assets.json','configs/feature_review.csv','README.md','docs/data_layout.md','docs/data_dictionary.md']:
    target=archive/name;target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():shutil.copy2(root/name,target)
parent_path=archive/'configs/dataset_manifest.json'
parent=json.loads(parent_path.read_text());assert parent['version']=='per-drifter-cleaned-20261017-v3'
assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx')==parent['contract_sha256']
changed={};ledgers=[];post_rows=post_IDs=post_R=old_NA=0
for n,(sid,record) in enumerate(parent['records'].items(),1):
    current=root/record['path'];backup=archive/record['path']
    source=backup if backup.exists() else current
    assert file_sha256(source)==record['sha256'],sid
    context=pq.read_table(source,columns=['id','source_obs','time','end_date','typedeath','sst','in_R']).to_pandas()
    mask=post_last_good_grounding_mask(context)
    assert not np.isinf(context.sst.to_numpy()).any()
    post_rows+=int(mask.sum());post_IDs+=int(mask.any());post_R+=int((mask&context.in_R.to_numpy()).sum())
    old_NA+=int(context.sst.isna().sum())
    delta=mask&context.sst.notna().to_numpy()
    if delta.any():
        backup.parent.mkdir(parents=True,exist_ok=True)
        if not backup.exists():os.link(current,backup)
        before=pq.read_table(backup);after=clear_post_grounding_sst(before)
        assert before.schema.equals(after.schema,check_metadata=True)
        assert tables_equal(before.drop(['sst']),after.drop(['sst']))
        target=audit/'staged'/record['path'];target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_suffix('.tmp');pq.write_table(after,temporary,compression='zstd',compression_level=3)
        assert tables_equal(after,pq.read_table(temporary));os.replace(temporary,target)
        item={'backup_path':str(backup.relative_to(root)),'path':record['path'],
              'new_NA':int(delta.sum()),'new_NA_in_R':int((delta&context.in_R.to_numpy()).sum()),
              'sha256':file_sha256(target)}
        changed[sid]=item
        ledger=context.loc[delta,['id','source_obs','time','end_date','in_R','sst']].copy()
        ledger=ledger.rename(columns={'sst':'before_sst_K'})
        ledger['after_sst_K']=np.nan;ledger['reason']=POLICY;ledgers.append(ledger)
    if n%500==0:print(f'Checked/staged {n}/{parent["IDs"]} files',flush=True)

changes=pd.concat(ledgers,ignore_index=True);changes.to_parquet(audit/'changes.parquet',index=False)
summary={'IDs':parent['IDs'],'rows':parent['rows'],'fields_per_ID':parent['fields'],
    'changed_ID_files':len(changed),'new_SST_NA':len(changes),
    'new_SST_NA_in_R':int(changes.in_R.sum()),'previous_SST_NA':old_NA,
    'total_SST_NA':old_NA+len(changes),'post_last_good_grounding_rows':post_rows,
    'post_last_good_grounding_IDs':post_IDs,'post_last_good_grounding_rows_in_R':post_R}
assert (summary['new_SST_NA'],old_NA,post_rows)==(10512,5547,16059)
assert summary['new_SST_NA_in_R']==post_R==47
receipt={'policy':POLICY,'parent_manifest_path':str(parent_path.relative_to(root)),
    'parent_manifest_sha256':file_sha256(parent_path),'changed_files':changed,
    'change_ledger_path':str((audit/'changes.parquet').relative_to(root)),
    'change_ledger_sha256':file_sha256(audit/'changes.parquet'),'summary':summary}
write_json(audit/'receipt.json',receipt)

manifest=copy.deepcopy(parent);manifest['version']=VERSION
manifest['cleaning']['temperature']['grounding_NA']={'policy':POLICY,'column':'sst',
    'cutoff_semantics':'official last-good time, not observed first-grounding time',
    'audit_directory':str(audit.relative_to(root)),'new_NA':len(changes),'total_SST_NA':old_NA+len(changes)}
for sid,item in changed.items():manifest['records'][sid]['sha256']=item['sha256']
schema=json.loads((archive/'configs/dataset_schema.json').read_text());schema['version']=VERSION
next(f for f in schema['fields'] if f['name']=='sst')['cleaning']=(
    'Approved cleaned total SST in Kelvin. For typedeath=1, times after a finite positive official end_date are numeric NA and are not refilled. The boundary is last-good time, not exact grounding time. Original values and reasons are archived externally.')
index=pd.read_csv(archive/'configs/dataset_index.csv')
index['sha256']=index.id.astype(str).map(lambda sid:manifest['records'][sid]['sha256'])
index.to_csv(audit/'next_dataset_index.csv',index=False)
write_json(audit/'next_dataset_manifest.json',manifest);write_json(audit/'next_dataset_schema.json',schema)
assets=json.loads((archive/'configs/assets.json').read_text());assets['layout_version']='per-drifter-cleaned-1.2'
assets['current_data_status']='Cleaned total SST in sst; post-last-good SST on eventual-grounding IDs is numeric NA; recovery tails removed; other fields and ID pools unchanged'
for key in ['current_train_tracks','current_test_tracks']:
    assets['assets'][key]['version']=VERSION
    assets['assets'][key]['role']='Current records: cleaned sst with approved grounding-related NA cutoff; no new columns; same ID pool; vessel-recovery tails removed'
for key,name in [('current_dataset_manifest','dataset_manifest.json'),
                 ('current_dataset_schema','dataset_schema.json'),('current_dataset_index','dataset_index.csv')]:
    assets['assets'][key]['sha256']=file_sha256(audit/('next_'+name))
write_json(audit/'next_assets.json',assets)
for n,(sid,item) in enumerate(changed.items(),1):
    target=audit/'staged'/item['path'];destination=root/item['path']
    assert file_sha256(target)==item['sha256']
    assert file_sha256(destination) in [parent['records'][sid]['sha256'],item['sha256']]
    os.replace(target,destination)
    with (audit/'activation.jsonl').open('a') as stream:
        stream.write(json.dumps({'id':sid,'sha256':item['sha256']})+'\n');stream.flush();os.fsync(stream.fileno())
    if n%250==0:print(f'Activated {n}/{len(changed)} changed files',flush=True)
for name in ['dataset_manifest.json','dataset_index.csv','dataset_schema.json','assets.json']:
    temporary=root/'configs'/('.'+name+'.tmp');shutil.copy2(audit/('next_'+name),temporary)
    os.replace(temporary,root/'configs'/name)
write_json(audit/'publication.json',summary)
print(json.dumps(summary,indent=2),flush=True)
