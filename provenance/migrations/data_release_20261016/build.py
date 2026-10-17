"""Build and verify the new release before changing any source path."""
from pathlib import Path
import json,hashlib,time
import numpy as np,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
from data3001.paths import asset_path,file_sha256
from data3001.preprocessing.prep_io import Source
from data3001.preprocessing.drogue_boundary import read_prepared_track
from data3001.preprocessing.drogue_correction import official_attached_evidence
from data3001.preprocessing.prep_pairs import load_track,origin_indices,generate
from data3001.data_release import assemble_track,unknown_reasons
B=Path.cwd();R=B/'provenance/migrations/data_release_20261016';stage=R/'staged_data';stage.mkdir(exist_ok=False)
for pool in ['train','test']:(stage/pool).mkdir()
s=Source(allow_test=True);assert s.verify()['rows']==39107061
native_fields=list(s.g.array_keys());native_attrs={k:{**s.g[k].attrs.asdict(),'native_numpy_dtype':str(s.g[k].dtype)} for k in native_fields}
meta_keys=[k for k in native_fields if s.g[k].attrs.get('_ARRAY_DIMENSIONS')==['traj']]
obs_keys=[k for k in native_fields if s.g[k].attrs.get('_ARRAY_DIMENSIONS')==['obs']]
meta_arrays={k:s.g[k][:] for k in meta_keys}
boundary=json.loads(asset_path('official_drogue_boundary').read_text())['records']
records={};index=[];first_schema=None;first_prepared=None;counter={-1:0,0:0,1:0};start=time.monotonic()
with (R/'build_log.jsonl').open('x') as journal:
 for k,v in enumerate(s.ids):
  id=int(v);i=s.index[id];split=str(s.cohort.loc[id,'split']);pool='test' if split=='test' else 'train'
  f,proof=read_prepared_track(id,split,allow_test=True)
  base=asset_path('test_cleaned' if split=='test' else 'development_cleaned',allow_test=True)/f'{id}.parquet'
  baseline=pd.read_parquet(base,columns=['regime'])
  assert len(f)==int(s.sizes[i])
  original_order=f.original_within_traj_obs.to_numpy();assert np.array_equal(np.sort(original_order),np.arange(len(f)))
  a0,a1=map(int,s.offset[i:i+2])
  for name in obs_keys:
   raw=s.read(name,a0,a1)[original_order]
   assert raw.dtype==f[name].to_numpy().dtype,(id,name,'dtype')
   assert np.array_equal(raw,f[name].to_numpy(),equal_nan=True),(id,name,'source values')
  meta={name:meta_arrays[name][i] for name in meta_keys}
  native_loss=float(meta['drogue_lost_date']);evidence=boundary.get(str(id));attached=official_attached_evidence(id,split,allow_test=True)
  context={}
  if proof:
   context={'loss_status_source':'official_boundary_refinement','official_regime_decision':proof['decision'],
            'official_loss_epoch':proof.get('official_loss_epoch'),'official_attached_through_epoch':proof.get('attached_through_epoch'),
            'preparation_correction_version':'official-drogue-boundary-v1','preparation_correction_asset':'official_drogue_boundary'}
  elif attached:
   context={'loss_status_source':'official_fill_attached','official_attached_through_epoch':attached['attached_through_epoch'],
            'preparation_correction_version':'official-drogue-attached-44-v1','preparation_correction_asset':'official_drogue_correction'}
  reason=unknown_reasons(f.regime.to_numpy(),native_loss,evidence)
  annotations={
   'historical_split':pa.array([split]*len(f),type=pa.string()),'pool':pa.array([pool]*len(f),type=pa.string()),
   'regime_pre_official_correction':pa.array(baseline.regime.to_numpy(),type=pa.int8()),
   'regime_unknown_reason':pa.array(reason,type=pa.string()),
   'regime_annotation_version':pa.array([context.get('preparation_correction_version','preparation-1.0')]*len(f),type=pa.string()),
   'regime_annotation_source':pa.array([context.get('loss_status_source','frozen_hourly_rule')]*len(f),type=pa.string()),
   'official_regime_decision':pa.array([context.get('official_regime_decision')]*len(f),type=pa.string()),
   'official_loss_epoch':pa.array([context.get('official_loss_epoch')]*len(f),type=pa.float64()),
   'official_attached_through_epoch':pa.array([context.get('official_attached_through_epoch')]*len(f),type=pa.float64())}
  metadata={'release':'per-drifter-20261016-v1','id':str(id),'pool':pool,'historical_split':split,
            'regime_context':context,'boundary_record':proof,'attached_record':attached,
            'contract_sha256':s.snapshot.get('contract_sha256') or json.loads((B/'configs/assets.json').read_text())['contract_sha256'],
            'native_field_names':native_fields,'prepared_field_names':f.columns.tolist()}
  table=assemble_track(f,meta,annotations=annotations,field_attributes=native_attrs,context=metadata)
  assert set(native_fields)|set(f.columns)<=set(table.column_names)
  if first_schema is None:first_schema=table.schema;first_prepared=f.columns.tolist()
  assert table.schema.equals(first_schema,check_metadata=False),(id,'schema')
  path=stage/pool/f'{id}.parquet';pq.write_table(table,path,compression='zstd',row_group_size=65536)
  back=pq.read_table(path)
  pd.testing.assert_frame_equal(back.select(f.columns).to_pandas(),f)
  assert back.schema.equals(table.schema,check_metadata=True)
  for name,value in meta.items():
   result=back[name].to_numpy(zero_copy_only=False)
   if np.asarray(value).dtype.kind=='S':assert all(x==bytes(value) for x in result),(id,name)
   else:assert result.dtype==np.asarray(value).dtype and np.array_equal(result,np.repeat(value,len(f)),equal_nan=True),(id,name)
  for label in [-1,0,1]:counter[label]+=int((f.regime==label).sum())
  record={'id':str(id),'path':f'data/{pool}/{id}.parquet','pool':pool,'historical_split':split,'rows':len(f),
          'sha256':file_sha256(path),'source_index':i,'regime_context':context}
  records[str(id)]=record
  index.append({'id':id,'pool':pool,'historical_split':split,'rows':len(f),'first_epoch':float(f.time.min()),
                'last_epoch':float(f.time.max()),'in_R':id in s.R,'unknown_rows':int((f.regime<0).sum()),
                'path':record['path'],'sha256':record['sha256'],'source_index':i})
  journal.write(json.dumps({'id':str(id),'rows':len(f),'file_sha256':record['sha256'],'all_native_hourly_values_equal':True,'all_prepared_columns_equal':True,'all_metadata_values_equal':True})+'\n');journal.flush()
  if (k+1)%100==0:print('Built and verified IDs',k+1,'/',len(s.ids),'elapsed_s',round(time.monotonic()-start),flush=True)
assert len(records)==3741 and sum(r['rows'] for r in records.values())==39107061
assert counter=={-1:496247,0:19342607,1:19268207},counter
schema=[]
for field in first_schema:
 role='native_hourly' if field.name in obs_keys else 'native_trajectory' if field.name in meta_keys else 'existing_prepared' if field.name in first_prepared else 'decoded_metadata_companion' if field.name.endswith('_text') else 'release_annotation'
 schema.append({'name':field.name,'arrow_type':str(field.type),'role':role,'native_attributes':native_attrs.get(field.name)})
manifest={'version':'per-drifter-20261016-v1','contract_sha256':json.loads((B/'configs/assets.json').read_text())['contract_sha256'],
          'IDs':len(records),'rows':sum(r['rows'] for r in records.values()),'fields':len(schema),
          'source_fields':native_fields,'prepared_fields':first_prepared,'regime_counts':counter,
          'pools':{'train':3224,'test':517},'source_field_attributes':native_attrs,'records':records,
          'scientific_status':'storage consolidation only; no new cleaning, imputation, split, fitted model or accuracy claim'}
(R/'dataset_manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False));pd.DataFrame(index).to_csv(R/'dataset_index.csv',index=False)
(R/'dataset_schema.json').write_text(json.dumps({'version':manifest['version'],'fields':schema},indent=2,allow_nan=False))
# Freeze paired-target semantics from real cases before the reader or paths change.
Rids=[int(v) for v in s.ids if int(v) in s.R]
examples=[]
for predicate in [lambda id:str(id) in records and str(id) in boundary and boundary[str(id)]['decision']=='nominal_loss',
                  lambda id:str(id) in boundary and boundary[str(id)]['decision']=='attached_at_end',
                  lambda id:str(id) in boundary and boundary[str(id)]['decision']=='hold_unknown',
                  lambda id:official_attached_evidence(id,str(s.cohort.loc[id,'split']),allow_test=True) is not None,
                  lambda id:float(meta_arrays['drogue_lost_date'][s.index[id]])==0]:
 for split in ['train','validation','test']:
  matches=[id for id in Rids if s.cohort.loc[id,'split']==split and predicate(id)]
  if matches:examples.append(matches[0])
fingerprints={}
for id in sorted(set(examples)):
 df,a,e=load_track(s,id);o=origin_indices(df,a,'R')
 for day in [7,30,90,180,365]:
  for scenario in ['drogued','undrogued','pooled']:
   pair=generate(df,a,e,id,o,day,scenario)
   for target,frame in zip(['endpoint','stopped'],pair):
    fingerprints[f'{id}:{day}:{scenario}:{target}']=hashlib.sha256(pd.util.hash_pandas_object(frame,index=False).values.tobytes()+str(frame.dtypes).encode()).hexdigest()
(R/'pair_fingerprints_before.json').write_text(json.dumps(fingerprints,indent=2))
(R/'build_summary.json').write_text(json.dumps({'IDs':len(records),'rows':manifest['rows'],'fields':len(schema),'source_fields_retained':len(native_fields),'prepared_fields_retained':len(first_prepared),'regime_counts':counter,'paired_label_fingerprints':len(fingerprints),'paired_example_IDs':sorted(set(examples)),'elapsed_seconds':time.monotonic()-start},indent=2))
print((R/'build_summary.json').read_text(),flush=True)
