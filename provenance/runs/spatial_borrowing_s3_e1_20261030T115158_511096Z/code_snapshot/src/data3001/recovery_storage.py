"""Physical recovery-tail exclusion, preserving retained values and metadata."""
import json
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from data3001.model_input_cleaning import recovery_tail_mask
from data3001.paths import project_paths,file_sha256


def clean_table(table):
    context=table.select(['time','end_date','typedeath']).to_pandas()
    tail=recovery_tail_mask(context)
    return table.filter(pa.array(~tail)),table.filter(pa.array(tail))


def tables_equal(left,right):
    """Exact field/type/null/metadata equality, with preserved NaNs equal."""
    if len(left)!=len(right) or not left.schema.equals(right.schema,check_metadata=True):
        return False
    for name in left.column_names:
        a,b=left[name],right[name]
        if not a.is_null().equals(b.is_null()):return False
        if pa.types.is_floating(a.type):
            if not np.array_equal(a.to_numpy(),b.to_numpy(),equal_nan=True):return False
        elif not a.equals(b):return False
    return True


def verify_cleaned_release(progress=None):
    from data3001.dataset import manifest
    paths=project_paths();root=paths.root;m=manifest()
    directory=root/m['cleaning']['audit_directory']
    receipt=json.loads((directory/'receipt.json').read_text())
    oldpath=root/receipt['parent_manifest_path']
    assert file_sha256(oldpath)==receipt['parent_manifest_sha256']
    old=json.loads(oldpath.read_text());rows=0;removed=0;changed=0
    assert set(m['records'])==set(old['records'])
    for sid,r in m['records'].items():
        prior=old['records'][sid]
        assert (r['pool'],r['historical_split'],r['path'])==(prior['pool'],prior['historical_split'],prior['path'])
        path=root/r['path'];assert file_sha256(path)==r['sha256']
        table=pq.read_table(path)
        assert len(table)==r['rows'] and len(table.schema.names)==m['fields']==130
        assert not recovery_tail_mask(table.select(['time','end_date','typedeath']).to_pandas()).any()
        if sid in receipt['changed_files']:
            item=receipt['changed_files'][sid];backup=root/item['backup_path']
            assert file_sha256(backup)==prior['sha256']
            expected,excluded=clean_table(pq.read_table(backup))
            assert tables_equal(table,expected),sid
            removed+=len(excluded);changed+=1
        else:assert r['sha256']==prior['sha256'] and r['rows']==prior['rows']
        rows+=len(table)
    assert rows==m['rows']==39099193
    assert removed==old['rows']-rows==7868 and changed==159
    import pandas as pd
    idx=pd.read_csv(paths.asset('current_dataset_index',verify=True))
    assert len(idx)==m['IDs'] and int(idx.rows.sum())==rows
    assert idx.groupby('pool').size().to_dict()==m['pools']
    for row in idx.itertuples(index=False):
        r=m['records'][str(row.id)]
        assert row.rows==r['rows'] and row.sha256==r['sha256'] and row.path==r['path']
    assert file_sha256(root/'docs/contract/data_contract_v1.0.xlsx')==m['contract_sha256']
    if progress:progress('Retained values and backups verified; no recovery tails remain in current files')
    return {'passed':True,'release':m['version'],'IDs':m['IDs'],'rows':rows,'fields_per_ID':130,
            'changed_ID_files':changed,'removed_recovery_rows':removed,
            'retained_values_types_and_metadata_equal':True,'unchanged_file_hashes_preserved':True,
            'original_changed_files_archived':True,'whole_ID_pool_assignments_unchanged':True,
            'forecast_accuracy_evaluated':False}
