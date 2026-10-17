"""Store approved SST cleaning in the existing field; provenance stays external."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from data3001.paths import file_sha256, project_paths

VERSION='per-drifter-cleaned-20261017-v3'
APPROVED_RUN='total_sst_reference_audit_20261017_v1'


def replace_sst(table, approved):
    """Key-align the already approved result, replacing only the SST field.

    Historical evidence may include removed vessel-recovery rows. Every retained
    row must have exactly one corresponding temperature decision. No imputation
    or new quality decision is made here.
    """
    keys=['id','source_obs']
    source=table.select(keys).to_pandas()
    if source.duplicated(keys).any() or approved.duplicated(keys).any():
        raise ValueError('Duplicate temperature evidence keys')
    loc=pd.MultiIndex.from_frame(approved[keys]).get_indexer(pd.MultiIndex.from_frame(source[keys]))
    if (loc<0).any():raise ValueError('Approved temperature evidence missing for retained rows')
    values=approved.iloc[loc]['sst_use_K'].to_numpy(dtype=float)
    if np.isinf(values).any():raise ValueError('Infinite temperature cannot be published')
    field=table.schema.field('sst')
    metadata=dict(field.metadata or {})
    metadata[b'cleaning']=json.dumps({'status':'cleaned_in_place','units':'Kelvin',
        'approved_evidence_run':APPROVED_RUN,
        'original_values':'archived outside active data; see migration receipt',
        'native_flags_and_errors':'describe original GDP estimates, not replacement uncertainty'}).encode()
    replacement=pa.array(values,type=pa.float64(),from_pandas=True)
    out=table.set_column(table.schema.get_field_index('sst'),
        pa.field('sst',pa.float64(),nullable=field.nullable,metadata=metadata),replacement)
    schema_metadata=dict(table.schema.metadata or {})
    if b'pandas' in schema_metadata:
        pandas=json.loads(schema_metadata[b'pandas'])
        for column in pandas['columns']:
            if column.get('field_name')=='sst':
                column.update(pandas_type='float64',numpy_type='float64')
        schema_metadata[b'pandas']=json.dumps(pandas).encode()
    if b'data3001' in schema_metadata:
        context=json.loads(schema_metadata[b'data3001'])
        context['release']=VERSION
        context['sst_cleaning']={'column':'sst','units':'Kelvin','evidence_run':APPROVED_RUN,
                                 'audit_directory':'provenance/migrations/sst_inplace_20261017_v1'}
        schema_metadata[b'data3001']=json.dumps(context,sort_keys=True).encode()
    return out.replace_schema_metadata(schema_metadata)


def approved_temperature_index(root, run=APPROVED_RUN):
    """Resolve the frozen evidence chain once, latest verified decision first."""
    root=Path(root);index={};dependencies={};seen=set()
    while run:
        directory=root/'results/runs'/run
        if directory in seen:raise ValueError('Cyclic temperature evidence')
        seen.add(directory)
        receipt_path=directory/'verification.json';config_path=directory/'config.json'
        output_path=directory/'output_manifest.json'
        receipt=json.loads(receipt_path.read_text());config=json.loads(config_path.read_text())
        if receipt['status']!='passed':raise ValueError('Unverified temperature evidence')
        if 'config_sha256' in receipt and file_sha256(config_path)!=receipt['config_sha256']:
            raise ValueError('Temperature evidence configuration changed')
        for path in [receipt_path,config_path,output_path]:
            dependencies[str(path.relative_to(root))]=file_sha256(path)
        for record in json.loads(output_path.read_text()):
            sid=str(int(record['id']))
            if sid in index:continue
            path=Path(record['path'])
            path=root/path if path.parts[0]=='results' else directory/path
            if path.is_symlink() or not path.resolve().is_relative_to((root/'results/runs').resolve()):
                raise ValueError('Temperature evidence escapes run directory')
            index[sid]={'path':str(path.relative_to(root)),'sha256':record['sha256'],'run':run}
        run=config.get('parent_run')
        if not run and config.get('baseline'):
            baseline=Path(config['baseline'])
            if baseline.parent.as_posix()!='results/runs':raise ValueError('Unexpected baseline')
            run=baseline.name
    return index,dependencies


def read_approved(root, record):
    path=Path(root)/record['path']
    if file_sha256(path)!=record['sha256']:raise ValueError('Approved SST evidence changed')
    return pq.read_table(path).to_pandas()


def verify_sst_release(progress=None):
    """Independently compare all stored values to old records and frozen evidence."""
    from data3001.dataset import manifest
    from data3001.recovery_storage import tables_equal
    from data3001.model_input_cleaning import recovery_tail_mask
    paths=project_paths();root=paths.root;current=manifest()
    directory=root/current['cleaning']['temperature']['audit_directory']
    receipt=json.loads((directory/'receipt.json').read_text())
    parent_path=root/receipt['parent_manifest_path']
    assert file_sha256(parent_path)==receipt['parent_manifest_sha256']
    parent=json.loads(parent_path.read_text())
    sources_path=directory/'approved_sources.json'
    assert file_sha256(sources_path)==receipt['approved_sources_sha256']
    evidence=json.loads(sources_path.read_text())
    for name,checksum in evidence['dependencies'].items():assert file_sha256(root/name)==checksum
    assert set(current['records'])==set(parent['records'])==set(evidence['records'])
    rows=missing=changed_values=filled=corrected=cleared=0
    for n,(sid,record) in enumerate(current['records'].items(),1):
        old_record=parent['records'][sid]
        for field in ['path','pool','historical_split','rows']:
            assert record[field]==old_record[field],(sid,field)
        backup=root/receipt['files'][sid]['backup_path']
        assert file_sha256(backup)==old_record['sha256'],sid
        old=pq.read_table(backup)
        expected=replace_sst(old,read_approved(root,evidence['records'][sid]))
        actual_path=root/record['path']
        assert file_sha256(actual_path)==record['sha256'],sid
        actual=pq.read_table(actual_path)
        assert tables_equal(actual,expected),sid
        assert actual.column_names==old.column_names and 'sst_use_K' not in actual.column_names,sid
        assert len(actual.schema)==current['fields']==130 and len(actual)==old_record['rows']
        assert not recovery_tail_mask(actual.select(['time','end_date','typedeath']).to_pandas()).any()
        a=old['sst'].to_numpy();b=actual['sst'].to_numpy()
        delta=~((a==b)|(np.isnan(a)&np.isnan(b)))
        changed_values+=int(delta.sum())
        filled+=int((~np.isfinite(a)&np.isfinite(b)).sum())
        corrected+=int((np.isfinite(a)&np.isfinite(b)&delta).sum())
        cleared+=int((np.isfinite(a)&~np.isfinite(b)).sum())
        rows+=len(actual);missing+=int(np.isnan(b).sum())
        if progress and n%500==0:progress(f'Verified {n}/{current["IDs"]} files')
    assert rows==current['rows']==parent['rows'] and current['pools']==parent['pools']
    index=pd.read_csv(paths.asset('current_dataset_index',verify=True))
    assert len(index)==current['IDs'] and int(index.rows.sum())==rows
    assert index.groupby('pool').size().to_dict()==current['pools']
    for item in index.itertuples(index=False):
        r=current['records'][str(item.id)]
        assert (item.rows,item.path,item.sha256)==(r['rows'],r['path'],r['sha256'])
    schema=json.loads(paths.asset('current_dataset_schema',verify=True).read_text())
    assert len(schema['fields'])==130 and next(f for f in schema['fields'] if f['name']=='sst')['arrow_type']=='double'
    assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx')==current['contract_sha256']
    return {'passed':True,'release':current['version'],'IDs':current['IDs'],'rows':rows,
        'fields_per_ID':130,'temperature_column':'sst','added_data_columns':[],
        'sst_use_K_absent_from_active_files':True,'sst_exactly_matches_approved_values':True,
        'other_129_fields_values_types_and_nulls_unchanged':True,
        'whole_ID_pool_assignments_unchanged':True,'contract_unchanged':True,
        'missing_total_SST':missing,'changed_SST_values':changed_values,
        'filled_missing_SST':filled,'corrected_finite_SST':corrected,'set_unaccepted_SST_to_NA':cleared,
        'recovery_tails_still_absent':True,'forecast_accuracy_evaluated':False}
