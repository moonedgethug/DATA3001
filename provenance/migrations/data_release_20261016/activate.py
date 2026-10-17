"""Activate only the fully verified staged release; preserve every old byte."""
from pathlib import Path
import json,os,shutil,datetime
from data3001.paths import file_sha256
B=Path.cwd();R=B/'provenance/migrations/data_release_20261016';stage=R/'staged_data';archive=B/'archive/data_before_release_20261016'
summary=json.loads((R/'build_summary.json').read_text());assert summary['IDs']==3741 and summary['rows']==39107061
assert not archive.exists();assert {p.name for p in stage.iterdir()}=={'train','test'}
manifest=json.loads((R/'dataset_manifest.json').read_text())
for id,r in manifest['records'].items():
 p=stage/r['pool']/f'{id}.parquet';assert file_sha256(p)==r['sha256']
assert len(list((stage/'train').glob('*.parquet')))==3224
assert len(list((stage/'test').glob('*.parquet')))==517
for name in ['dataset_manifest.json','dataset_schema.json','dataset_index.csv']:
 p=B/'configs'/name;assert not p.exists();shutil.copy2(R/name,p)
old_catalog=json.loads((B/'configs/assets.json').read_text());new=json.loads(json.dumps(old_catalog))
prefix='archive/data_before_release_20261016/'
for k,spec in new['assets'].items():
 if spec['path'].startswith('data/'):
  spec['path']=prefix+spec['path'][5:]
  spec['storage_status']='retained original source/preparation; use canonical release for current hourly frames'
new['layout_version']='per-drifter-1.0'
new['current_data_status']='Consolidated full-field per-ID release; train is the development pool; final test unchanged; historical support tables retained; predictive accuracy untested'
new['assets'].update({
 'current_train_tracks':{'path':'data/train','kind':'directory','split':'development','version':manifest['version'],'role':'All 3224 development IDs, one complete current file per ID; original split retained as provenance'},
 'current_test_tracks':{'path':'data/test','kind':'directory','split':'test','version':manifest['version'],'role':'The unchanged 517 held-out IDs; explicit access only'},
 'current_dataset_manifest':{'path':'configs/dataset_manifest.json','kind':'file','split':'all','sha256':file_sha256(B/'configs/dataset_manifest.json'),'role':'Canonical per-ID hashes, source fields, current annotations and release identity'},
 'current_dataset_schema':{'path':'configs/dataset_schema.json','kind':'file','split':'all','sha256':file_sha256(B/'configs/dataset_schema.json'),'role':'Complete current field/type/source-role dictionary'},
 'current_dataset_index':{'path':'configs/dataset_index.csv','kind':'file','split':'all','sha256':file_sha256(B/'configs/dataset_index.csv'),'role':'Human-readable per-ID overview; no hourly observations omitted from data files'},
 'retained_data_inventory':{'path':'provenance/migrations/data_release_20261016/original_data_inventory.jsonl','kind':'file','split':'all','sha256':file_sha256(R/'original_data_inventory.jsonl'),'role':'Every original data object retained byte-identically in archive'},
 'retained_data_root':{'path':'archive/data_before_release_20261016','kind':'directory','split':'all','role':'The complete pre-release data directory; immutable source/history, not the daily data entry point'}})
legacy=json.loads((B/'configs/legacy_paths.json').read_text())
for group in ['file_map','directory_map']:
 for k,v in legacy[group].items():
  if v.startswith('data/'):legacy[group][k]=prefix+v[5:]
def atomic_json(path,data):
 temp=path.with_suffix(path.suffix+'.release-tmp')
 with temp.open('x') as f:json.dump(data,f,indent=2);f.flush();os.fsync(f.fileno())
 os.replace(temp,path)
def journal(action):
 with (R/'moves.jsonl').open('a') as f:f.write(json.dumps({'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),**action})+'\n');f.flush();os.fsync(f.fileno())
moved_old=False;moved_new=False
try:
 os.rename(B/'data',archive);moved_old=True;journal({'from':'data','to':str(archive.relative_to(B))})
 os.rename(stage,B/'data');moved_new=True;journal({'from':str(stage.relative_to(B)),'to':'data'})
 atomic_json(B/'configs/assets.json',new);atomic_json(B/'configs/legacy_paths.json',legacy)
except Exception:
 if moved_new:os.rename(B/'data',stage)
 if moved_old:os.rename(archive,B/'data')
 shutil.copy2(R/'before/configs/assets.json',B/'configs/assets.json');shutil.copy2(R/'before/configs/legacy_paths.json',B/'configs/legacy_paths.json')
 raise
(R/'activation.json').write_text(json.dumps({'activated':True,'archive':str(archive.relative_to(B)),'catalog_sha256':file_sha256(B/'configs/assets.json'),'legacy_map_sha256':file_sha256(B/'configs/legacy_paths.json'),'original_files_deleted':0,'train_IDs':3224,'test_IDs':517},indent=2))
print((R/'activation.json').read_text())
