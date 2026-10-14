from pathlib import Path
import ast,hashlib,json,shutil,os,subprocess,sys,time
BASE=Path('/Users/moonedgethug/Documents/UNSW/DATA3001/work_place')
BACK=BASE.parent/'.migration_backups/architecture_20261014'
MIG=BASE/'provenance/migrations/architecture_20261014'
old=json.loads((BACK/'baseline.json').read_text())
ROUTES={
 'README.md':'archive/planning/README_pre_migration.md',
 'docs/DATA_CONTRACT_V1.0.md':'archive/planning/DATA_CONTRACT_V1.0.md',
 'analysis':'archive/region_screening_6h',
 'proposal':'archive/proposal_history',
 'poster':'results/deliverables/poster_history',
 'poster/.build_v0.1':'archive/poster_build_v0.1',
 'data_preprocessing_audit.xlsx':'archive/planning/data_preprocessing_audit.xlsx',
 'data_preprocessing':'archive/planning/acquisition_misc',
 'data_preprocessing/.venv':'archive/environment/pre_migration_venv',
 'data_preprocessing/scripts':'provenance/frozen/acquisition/scripts',
 'data_preprocessing/tests':'provenance/frozen/acquisition/tests',
 'data_preprocessing/raw':'data/raw/gdp_hourly_v2.01.1',
 'data_preprocessing/geometry':'data/reference/acquisition/geometry',
 'data_preprocessing/manifests':'provenance/frozen/acquisition/manifests',
 'data_preprocessing/metadata':'provenance/frozen/acquisition/metadata',
 'data_preprocessing/audit':'provenance/frozen/acquisition/audit',
 'data_preprocessing/reports':'archive/report_sources',
 'data_preprocessing/preparation':'provenance/frozen/preparation_v1/misc',
 'data_preprocessing/preparation/cleaned':'data/processed/preparation_v1/cleaned',
 'data_preprocessing/preparation/origins':'data/processed/preparation_v1/origins',
 'data_preprocessing/preparation/events':'data/processed/preparation_v1/events',
 'data_preprocessing/preparation/ledgers':'data/processed/preparation_v1/ledgers',
 'data_preprocessing/preparation/support':'data/processed/preparation_v1/support',
 'data_preprocessing/preparation/support/spill':'archive/runtime_cache/preparation_support_spill',
 'data_preprocessing/preparation/geometry':'data/reference/preparation_v1/geometry',
 'data_preprocessing/preparation/config':'provenance/frozen/preparation_v1/config',
 'data_preprocessing/preparation/docs':'archive/planning/preparation',
 'data_preprocessing/preparation/audit':'provenance/frozen/preparation_v1/audit',
 'data_preprocessing/preparation/metadata':'data/reference/preparation_v1/metadata',
 'data_preprocessing/preparation/metadata/code_revisions':'provenance/frozen/preparation_v1/metadata/code_revisions',
 'data_preprocessing/preparation/metadata/checkpoint_revisions':'provenance/frozen/preparation_v1/metadata/checkpoint_revisions',
 'data_preprocessing/preparation/metadata/sources':'provenance/frozen/preparation_v1/metadata/sources',
 'data_preprocessing/preparation/metadata/sources/gshhg':'data/raw/reference_sources/gshhg',
 'data_preprocessing/preparation/metadata/sources/gshhg-shp-2.3.7.zip':'data/raw/reference_sources/gshhg-shp-2.3.7.zip',
 'data_preprocessing/preparation/checkpoints':'provenance/frozen/preparation_v1/checkpoints',
 'data_preprocessing/preparation/restricted_test':'provenance/frozen/preparation_v1/restricted_test',
 'data_preprocessing/preparation/restricted_test/cleaned':'data/restricted_test/preparation_v1/cleaned',
 'data_preprocessing/preparation/restricted_test/origins':'data/restricted_test/preparation_v1/origins',
 'data_preprocessing/preparation/restricted_test/events':'data/restricted_test/preparation_v1/events',
 'data_preprocessing/preparation/restricted_test/ledgers':'data/restricted_test/preparation_v1/ledgers',
 'data_preprocessing/preparation/restricted_test/support':'data/restricted_test/preparation_v1/support',
 'data_preprocessing/preparation/remediation_20261013':'provenance/frozen/handover_20261013',
 'data_preprocessing/preparation/remediation_20261013/geometry':'data/reference/handover_20261013/geometry',
 'data_preprocessing/preparation/remediation_20261013/support':'data/processed/handover_20261013/support',
 'data_preprocessing/preparation/architecture_audit_20261014_drogue_census':'provenance/frozen/drogue_census_20261014',
}
for name in ['acquired_ids.csv','R_ids.csv','downstream_ids.csv','global_id_split.csv']:
 ROUTES['data_preprocessing/manifests/'+name]='data/splits/acquisition/'+name
for name in ['trajectory_metadata.npz','variable_dictionary.json','corpus_time_coverage.json']:
 ROUTES['data_preprocessing/metadata/'+name]='data/reference/acquisition/metadata/'+name
for name in ['environment_lock.txt','stage_authority.json','package_artifact_manifest.json','readiness_status.json','unresolved_questions.json']:
 ROUTES['data_preprocessing/preparation/metadata/'+name]='provenance/frozen/preparation_v1/metadata/'+name
ROUTES['data_preprocessing/preparation/docs/AUTHORIZED_STAGE_PROMPT.txt']='provenance/frozen/preparation_v1/docs/AUTHORIZED_STAGE_PROMPT.txt'
ROUTES['data_preprocessing/preparation/manifests_development_folds.csv']='data/splits/preparation_v1/manifests_development_folds.csv'
for name in ['per_ID_census.csv','priority_unknown_IDs.csv']:
 ROUTES['data_preprocessing/preparation/architecture_audit_20261014_drogue_census/'+name]='data/reference/drogue_census_20261014/'+name
for name in ['profile.parquet','speed_review_flags.parquet']:
 ROUTES['data_preprocessing/preparation/restricted_test/'+name]='data/restricted_test/preparation_v1/'+name
# Preserve diagnostic observations as data; leave receipt prose and run logs in provenance.
for e in old['entries']:
 p=e['path']
 if p.endswith('.DS_Store'):
  ROUTES[p]='archive/filesystem_metadata/'+p.replace('/','__')
 elif '/audit/' in p and p.endswith('.parquet'):
  if '/preparation/restricted_test/audit/' in p:
   ROUTES[p]='data/restricted_test/preparation_v1/diagnostics/'+p.split('/audit/',1)[1]
  elif '/preparation/audit/' in p:
   ROUTES[p]='data/reference/preparation_v1/diagnostics/'+p.split('/preparation/audit/',1)[1]
  elif p.startswith('data_preprocessing/audit/'):
   ROUTES[p]='data/reference/acquisition/diagnostics/'+p.split('/audit/',1)[1]

def mapped(p):
 for prefix in sorted(ROUTES,key=len,reverse=True):
  if p==prefix or p.startswith(prefix+'/'):return ROUTES[prefix]+p[len(prefix):]
 if p.startswith('docs/images/'):return p
 raise RuntimeError(('Unclassified original asset',p))

def create_maps():
 entries=[{**e,'destination':mapped(e['path'])} for e in old['entries']]
 assert len(set(e['destination'] for e in entries))==len(entries),'Destination collision'
 (MIG/'path_map.json').write_text(json.dumps({'schema_version':1,'migration_id':'architecture_20261014','entries':entries},indent=2)+'\n')
 pref='data_preprocessing/'
 files={k[len(pref):]:v for k,v in ROUTES.items() if k.startswith(pref) and (BACK/'work_place'/k).is_file()}
 dirs={k[len(pref):]:v for k,v in ROUTES.items() if k.startswith(pref) and (BACK/'work_place'/k).is_dir()}
 dirs['preparation']='data/processed/preparation_v1'
 dirs['preparation/restricted_test']='data/restricted_test/preparation_v1'
 # Scientific functions can request the original prepared tree's root.
 (BASE/'configs/legacy_paths.json').write_text(json.dumps({'schema_version':1,'scope':'original acquisition-relative paths; historical only','file_map':files,'directory_map':dirs},indent=2)+'\n')
 print('Destination map checked:',len(entries),'unique entries;',len(files),'file overrides;',len(dirs),'directory routes',flush=True)
 return entries

def move():
 entries=create_maps()
 for group in sorted(ROUTES,key=lambda p:(p.count('/'),len(p)),reverse=True):
  source=BASE/group;target=BASE/ROUTES[group]
  if not source.exists() and not source.is_symlink():continue
  target.parent.mkdir(parents=True,exist_ok=True)
  # Nested routes may have created the target parent; merge only directories,
  # never overwrite a destination file.
  with (MIG/'move_journal.jsonl').open('a') as stream:
   stream.write(json.dumps({'event':'before','source':group,'destination':ROUTES[group]})+'\n');stream.flush();os.fsync(stream.fileno())
   if target.exists():
    assert source.is_dir() and target.is_dir(),('Collision',group,str(target))
    for child in list(source.iterdir()):
     dest=target/child.name;assert not dest.exists() and not dest.is_symlink(),('Collision',str(dest));child.rename(dest)
    source.rmdir()
   else:source.rename(target)
   stream.write(json.dumps({'event':'after','source':group,'destination':ROUTES[group]})+'\n');stream.flush();os.fsync(stream.fileno())
 print('All classified original groups moved; no file content edited.',flush=True)

if __name__=='__main__':
 if sys.argv[1]=='maps':create_maps()
 elif sys.argv[1]=='move':move()
