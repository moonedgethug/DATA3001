"""Approved numeric SST exclusion after an eventual-grounding last-good bound."""
import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from data3001.paths import project_paths,file_sha256
from data3001.sst_total_status import post_last_good_grounding_mask

VERSION='per-drifter-cleaned-20261017-v4'
POLICY='typedeath_1_time_gt_valid_official_end_date_sst_NA'


def clear_post_grounding_sst(table):
    """Only replace SST values; preserve rows, columns, types and metadata.

    The cutoff is a conservative validity bound, not an observed beaching hour.
    """
    mask=post_last_good_grounding_mask(table.select(['time','end_date','typedeath']).to_pandas())
    if not mask.any():return table
    index=table.schema.get_field_index('sst');field=table.schema.field('sst')
    values=pc.if_else(pa.array(mask),pa.scalar(None,type=field.type),table['sst'])
    return table.set_column(index,field,values)


def verify_grounding_sst_release(progress=None):
    """Read-only full-cohort checks against the immediately preceding release."""
    from data3001.dataset import manifest
    from data3001.recovery_storage import tables_equal
    from data3001.model_input_cleaning import recovery_tail_mask
    paths=project_paths();root=paths.root;current=manifest()
    policy=current['cleaning']['temperature']['grounding_NA']
    assert policy['policy']==POLICY
    directory=root/policy['audit_directory']
    receipt=json.loads((directory/'receipt.json').read_text())
    parent_path=root/receipt['parent_manifest_path']
    assert file_sha256(parent_path)==receipt['parent_manifest_sha256']
    parent=json.loads(parent_path.read_text())
    ledger_path=root/receipt['change_ledger_path']
    assert file_sha256(ledger_path)==receipt['change_ledger_sha256']
    ledger=pq.read_table(ledger_path).to_pandas()
    assert not ledger.duplicated(['id','source_obs']).any()
    ledger_counts=ledger.groupby('id').size().to_dict()
    assert current['version']==VERSION and set(current['records'])==set(parent['records'])
    rows=post_rows=missing=missing_R=post_R=new_NA=new_NA_R=0
    for n,(sid,record) in enumerate(current['records'].items(),1):
        before=parent['records'][sid]
        for name in ['path','pool','historical_split','rows']:
            assert record[name]==before[name],(sid,name)
        path=root/record['path'];assert file_sha256(path)==record['sha256'],sid
        frame=pq.read_table(path,columns=['time','end_date','typedeath','sst','in_R']).to_pandas()
        # Independent expression checks the physical stored values, rather than
        # trusting the mutation function or the candidate list.
        mask=(frame.typedeath.to_numpy()==1)&np.isfinite(frame.time.to_numpy())&np.isfinite(frame.end_date.to_numpy())
        mask&=(frame.end_date.to_numpy()>0)&(frame.time.to_numpy()>frame.end_date.to_numpy(dtype=float))
        assert frame.loc[mask,'sst'].isna().all(),sid
        assert not recovery_tail_mask(frame).any(),sid
        schema=pq.read_schema(path)
        assert len(schema)==130 and 'sst_use_K' not in schema.names
        assert len(frame)==record['rows']
        post_rows+=int(mask.sum());post_R+=int((mask&frame.in_R.to_numpy()).sum())
        missing+=int(frame.sst.isna().sum());missing_R+=int((frame.sst.isna()&frame.in_R).sum())
        if sid in receipt['changed_files']:
            item=receipt['changed_files'][sid];backup=root/item['backup_path']
            assert file_sha256(backup)==before['sha256']
            old=pq.read_table(backup);actual=pq.read_table(path)
            assert actual.schema.equals(old.schema,check_metadata=True),sid
            assert actual.column_names==old.column_names
            assert tables_equal(actual.drop(['sst']),old.drop(['sst'])),sid
            selected=pa.array(~mask)
            assert tables_equal(actual.select(['sst']).filter(selected),old.select(['sst']).filter(selected)),sid
            assert actual['sst'].filter(pa.array(mask)).null_count==int(mask.sum()),sid
            delta=mask&np.isfinite(old['sst'].to_numpy())
            assert int(delta.sum())==item['new_NA']
            assert ledger_counts[int(sid)]==int(delta.sum())
            evidence=ledger.loc[ledger.id.eq(int(sid))]
            assert set(evidence.source_obs)==set(actual['source_obs'].to_numpy()[delta])
            new_NA+=int(delta.sum());new_NA_R+=int((delta&frame.in_R.to_numpy()).sum())
        else:
            assert record['sha256']==before['sha256'],sid
        rows+=len(frame)
        if progress and n%500==0:progress(f'Verified {n}/{current["IDs"]} files')
    assert rows==current['rows']==parent['rows'] and current['pools']==parent['pools']
    assert len(ledger)==new_NA
    index=pd.read_csv(paths.asset('current_dataset_index',verify=True))
    assert len(index)==current['IDs'] and int(index.rows.sum())==rows
    assert index.groupby('pool').size().to_dict()==current['pools']
    for item in index.itertuples(index=False):
        record=current['records'][str(item.id)]
        assert (item.rows,item.path,item.sha256)==(record['rows'],record['path'],record['sha256'])
    assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx')==current['contract_sha256']
    return {'passed':True,'release':current['version'],'IDs':current['IDs'],'rows':rows,
        'fields_per_ID':130,'changed_ID_files':len(receipt['changed_files']),
        'new_SST_NA':new_NA,'new_SST_NA_in_R':new_NA_R,'post_last_good_grounding_rows':post_rows,
        'post_last_good_grounding_rows_in_R':post_R,'total_SST_NA':missing,'total_SST_NA_in_R':missing_R,
        'all_selected_SST_are_numeric_NA':True,'SST_elsewhere_unchanged':True,
        'other_129_fields_and_all_schema_metadata_unchanged':True,
        'whole_ID_pool_assignments_unchanged':True,'added_feature_columns':[],
        'recovery_tails_still_absent':True,'contract_unchanged':True,
        'exact_grounding_hour_inferred':False,'forecast_accuracy_evaluated':False}
