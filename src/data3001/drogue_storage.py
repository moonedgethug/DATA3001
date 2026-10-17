"""Consolidate existing cleaned drogue labels without creating a new feature."""
import json
from collections import Counter

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from data3001.paths import project_paths,file_sha256

VERSION='per-drifter-cleaned-20261017-v5'
POLICY='exact_regime_transfer_to_drogue_status_then_remove_regime'
ATTRIBUTES={'long_name':'Cleaned drogue status','units':'-', 'dtype':'int8',
            'flag_values':[-1,0,1],'flag_meanings':['unknown','undrogued','drogued']}


def materialize_drogue_status(table):
    """Transfer the existing int8 labels exactly and remove only regime."""
    labels=table['regime']
    if (not pa.types.is_int8(labels.type) or labels.null_count or
            not np.isin(labels.to_numpy(),[-1,0,1]).all()):
        raise ValueError('Approved labels must be complete int8 values in {-1,0,1}')
    old=table.schema.field('drogue_status');metadata=dict(old.metadata or {})
    metadata[b'cleaned_attributes']=json.dumps(ATTRIBUTES).encode()
    metadata[b'cleaning_policy']=POLICY.encode()
    out=table.set_column(table.schema.get_field_index('drogue_status'),
                         pa.field('drogue_status',labels.type,nullable=old.nullable,metadata=metadata),labels)
    out=out.drop(['regime']);metadata=dict(table.schema.metadata or {})
    if b'pandas' in metadata:
        attributes=json.loads(metadata[b'pandas'])
        attributes['columns']=[c for c in attributes['columns'] if c.get('field_name')!='regime']
        metadata[b'pandas']=json.dumps(attributes).encode()
    if b'data3001' in metadata:
        context=json.loads(metadata[b'data3001']);context['release']=VERSION
        if 'prepared_field_names' in context:
            context['prepared_field_names']=[c for c in context['prepared_field_names'] if c!='regime']
        context['drogue_status_cleaning']={'policy':POLICY,'column':'drogue_status',
            'states':{'-1':'unknown','0':'undrogued','1':'drogued'},
            'audit_directory':'provenance/migrations/drogue_status_inplace_20261017_v1'}
        metadata[b'data3001']=json.dumps(context,sort_keys=True).encode()
    return out.replace_schema_metadata(metadata)


def cleaned_drogue_values(frame):
    """Use the declared current column; historical frames keep their own schema.

    Returns an array only. It never appends a regime feature to a data frame.
    """
    current=frame.attrs.get('data3001',{}).get('drogue_status_cleaning',{}).get('policy')==POLICY
    if current:
        if 'regime' in frame:raise ValueError('Removed regime feature reappeared in a current frame')
        return frame['drogue_status'].to_numpy()
    if 'regime' in frame:return frame['regime'].to_numpy()
    raise ValueError('No declared cleaned drogue status is available')


def verify_drogue_release(progress=None):
    """Compare every active state directly with the parent's regime values."""
    from data3001.dataset import manifest
    from data3001.recovery_storage import tables_equal
    from data3001.model_input_cleaning import recovery_tail_mask
    paths=project_paths();root=paths.root;m=manifest()
    rule=m['cleaning']['drogue_status'];assert rule['policy']==POLICY and m['version']==VERSION
    directory=root/rule['audit_directory'];receipt=json.loads((directory/'receipt.json').read_text())
    parent_path=root/receipt['parent_manifest_path']
    assert file_sha256(parent_path)==receipt['parent_manifest_sha256']
    parent=json.loads(parent_path.read_text());assert set(m['records'])==set(parent['records'])
    rows=changed=sst_NA=sst_NA_R=0;counts=Counter()
    index=pd.read_csv(paths.asset('current_dataset_index',verify=True)).set_index('id')
    assert len(index)==m['IDs']
    for n,(sid,record) in enumerate(m['records'].items(),1):
        before=parent['records'][sid];item=receipt['files'][sid]
        for key in ['path','pool','historical_split','rows']:assert record[key]==before[key],(sid,key)
        backup=root/item['backup_path'];assert file_sha256(backup)==before['sha256'],sid
        path=root/record['path'];assert file_sha256(path)==record['sha256'],sid
        old=pq.read_table(backup);current=pq.read_table(path)
        assert len(current)==len(old)==record['rows']
        assert current.column_names==[c for c in old.column_names if c!='regime'],sid
        assert len(current.schema)==m['fields']==129 and 'regime' not in current.column_names
        # Independently verify label identity and every unrelated value/type/null.
        assert current['drogue_status'].equals(old['regime']),sid
        assert current['drogue_status'].null_count==0 and current['drogue_status'].type==pa.int8()
        assert tables_equal(current.drop(['drogue_status']).replace_schema_metadata(None),
                            old.drop(['drogue_status','regime']).replace_schema_metadata(None)),sid
        assert tables_equal(current,materialize_drogue_status(old)),sid
        status=current['drogue_status'].to_numpy()
        counts.update({str(v):int((status==v).sum()) for v in [-1,0,1]})
        changed+=int((old['drogue_status'].to_numpy()!=status).sum())
        assert int((status==-1).sum())==int(index.loc[int(sid),'unknown_rows'])
        t=current.select(['time','end_date','typedeath','sst','in_R']).to_pandas()
        assert not recovery_tail_mask(t).any(),sid
        post=(t.typedeath==1)&np.isfinite(t.end_date)&(t.end_date>0)&(t.time>t.end_date.astype(float))
        assert t.loc[post,'sst'].isna().all(),sid
        sst_NA+=int(t.sst.isna().sum());sst_NA_R+=int((t.sst.isna()&t.in_R).sum())
        entry=index.loc[int(sid)]
        assert (int(entry['rows']),entry['path'],entry['sha256'])==(record['rows'],record['path'],record['sha256'])
        rows+=len(current)
        if progress and n%500==0:progress(f'Verified {n}/{m["IDs"]} files')
    assert rows==m['rows']==parent['rows'] and m['pools']==parent['pools']
    assert counts==Counter(parent['regime_counts'])==Counter(m['drogue_status_counts'])
    assert int(index['rows'].sum())==rows and index.groupby('pool').size().to_dict()==m['pools']
    schema=json.loads(paths.asset('current_dataset_schema',verify=True).read_text())
    assert len(schema['fields'])==129 and not any(f['name']=='regime' for f in schema['fields'])
    assert next(f for f in schema['fields'] if f['name']=='drogue_status')['cleaned_attributes']==ATTRIBUTES
    assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx')==m['contract_sha256']
    return {'passed':True,'release':m['version'],'IDs':m['IDs'],'rows':rows,'fields_per_ID':129,
        'drogue_status_exactly_equals_parent_regime':True,'regime_absent_from_active_files':True,
        'drogue_status_counts':dict(counts),'native_binary_status_values_updated':changed,
        'other_128_columns_values_types_and_nulls_unchanged':True,'all_record_keys_and_order_unchanged':True,
        'drogue_lost_date_unchanged':True,'whole_ID_pool_assignments_unchanged':True,
        'SST_NA_unchanged':sst_NA,'SST_NA_in_R_unchanged':sst_NA_R,
        'new_feature_columns':[],'recovery_tails_still_absent':True,'contract_unchanged':True,
        'forecast_accuracy_evaluated':False}
