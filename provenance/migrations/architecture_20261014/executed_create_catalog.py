from pathlib import Path
import json,hashlib,shutil
root=Path('/Users/moonedgethug/Documents/UNSW/DATA3001/work_place');back=root.parent/'.migration_backups/architecture_20261014'
mapdata=json.loads((root/'provenance/migrations/architecture_20261014/path_map.json').read_text());index={e['path']:e for e in mapdata['entries']}
assets={}
def original(asset_id,path,*,split='development',role='scientific input',schema=None):
 e=index['data_preprocessing/'+path];assets[asset_id]={'path':e['destination'],'kind':'file','sha256':e['sha256'],'split':split,'role':role,'snapshot':'gdp-hourly-v2.01.1 / preparation-1.0 / handover-addendum-1.1','historical_path':path}
 if schema:assets[asset_id]['schema']=schema
 return assets[asset_id]
def directory(asset_id,path,split='development',role='frozen scientific directory'):
 assets[asset_id]={'path':path,'kind':'directory','split':split,'role':role,'verification_inventory':'provenance/migrations/architecture_20261014/path_map.json'}
for e in json.loads((back/'baseline.json').read_text())['external']:
 if e['source'].endswith('.xlsx'):
  target=root/'docs/contract'/Path(e['source']).name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(back/e['backup'],target)
  assets['chinese_contract' if target.name.endswith('_zh.xlsx') else 'english_contract']={'path':str(target.relative_to(root)),'kind':'file','sha256':e['sha256'],'split':'all','role':'translation for discussion' if target.name.endswith('_zh.xlsx') else 'authoritative controlled copy; original authority unchanged','version':'1.0'}
 else:
  target=root/'results/deliverables/proposal'/Path(e['source']).name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(back/e['backup'],target)
  assets['submission_proposal']={'path':str(target.relative_to(root)),'kind':'file','sha256':e['sha256'],'split':'all','role':'byte-identical copy of submission_proposal/proposal_final.docx; no text revision'}
directory('hourly_subset','data/raw/gdp_hourly_v2.01.1/hourly_subset_v2.01.1.zarr','all','native full-cohort snapshot; forecast APIs restrict held-out IDs')
directory('source_objects','data/raw/gdp_hourly_v2.01.1/source_objects','all','partial global source-object cache; not a complete global corpus')
directory('prepared_development','data/processed/preparation_v1')
directory('prepared_test','data/restricted_test/preparation_v1','test')
for name in ['cleaned','origins','events','ledgers','support']:
 directory('development_'+name,'data/processed/preparation_v1/'+name)
 directory('test_'+name,'data/restricted_test/preparation_v1/'+name,'test')
for asset_id,path in {
 'source_snapshot':'manifests/source_snapshot.json','source_authority':'manifests/authority.json',
 'source_dictionary':'metadata/variable_dictionary.json','corpus_time_coverage':'metadata/corpus_time_coverage.json',
 'cohort_ids':'manifests/acquired_ids.csv','global_id_split':'manifests/global_id_split.csv','R_ids':'manifests/R_ids.csv','downstream_ids':'manifests/downstream_ids.csv',
 'release_R':'geometry/release_R.geojson','acquisition_envelope':'geometry/acquisition_envelope.geojson',
 'transport_D':'preparation/geometry/transport_D.geojson','preparation_config':'preparation/config/preparation.json',
 'grouped_validation_config':'preparation/config/grouped_validation.json','development_folds':'preparation/manifests_development_folds.csv',
 'source_reason_codes':'preparation/metadata/eligibility_codes.json','preprocessing_dictionary':'preparation/metadata/preprocessing_dictionary.json',
 'trajectory_context':'preparation/metadata/trajectory_context.parquet','baseline_state_index':'preparation/geometry/state_index.parquet',
 'state_index':'preparation/remediation_20261013/geometry/state_index.parquet','baseline_lag_support':'preparation/support/lag_support.parquet',
 'lag_support':'preparation/remediation_20261013/support/lag_support.parquet','lag_annual_support':'preparation/remediation_20261013/support/lag_annual_support.parquet',
 'anchor_support':'preparation/support/cell_support.parquet','depth_support':'preparation/remediation_20261013/support/depth_anchor_support.parquet',
 'grouped_fold_coverage':'preparation/remediation_20261013/support/R_grouped_fold_coverage.csv',
 'year_support':'preparation/remediation_20261013/support/R_365_cell_season_support.parquet',
 'drogue_census':'preparation/architecture_audit_20261014_drogue_census/per_ID_census.csv',
 'drogue_census_receipt':'preparation/architecture_audit_20261014_drogue_census/result.json',
 'handover_verification':'preparation/remediation_20261013/audit/verification.json',
 'depth_pending':'preparation/remediation_20261013/audit/depth_findings.json',
 'annual_limits':'preparation/remediation_20261013/audit/annual_support_limits.json',
 'source_fields_verification':'preparation/audit/source_values_reverified.json',
 'land_mask_high':'preparation/geometry/gshhg_h_land.wkb','land_mask_intermediate':'preparation/geometry/gshhg_i_land.wkb',
 }.items():original(asset_id,path,split='all' if asset_id in ['source_snapshot','source_authority','source_dictionary','corpus_time_coverage','cohort_ids','global_id_split','R_ids','downstream_ids','release_R','acquisition_envelope','trajectory_context','preprocessing_dictionary','source_reason_codes','drogue_census','drogue_census_receipt','source_fields_verification'] else 'development')
assets['state_index']['role']='current augmented regional water areas; original columns/cell IDs preserved'
assets['lag_support']['schema']='long format with explicit target column'
assets['baseline_lag_support']['schema']='historical wide format; not the active target-specific summary'
assets['trajectory_context']['role']='retrospective/source metadata; future drogue dates are not forecast features'
config={'schema_version':1,'layout_version':'architecture-1.0','research_contract_version':'1.0','contract_sha256':assets['english_contract']['sha256'],'current_data_status':'prepared core R-to-D foundation; DEPTH-01 pending; 365-day seasonal support limited; forecast accuracy untested','assets':assets}
(root/'configs/assets.json').write_text(json.dumps(config,indent=2)+'\n')
print('Catalog:',len(assets),'explicit assets; authority and schema roles recorded',flush=True)
