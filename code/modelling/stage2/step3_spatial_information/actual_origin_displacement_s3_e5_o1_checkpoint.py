"""Strict lineage checks for exact integer fold-count chunks."""
import pandas as pd
from data3001.paths import file_sha256


def read_checkpoint(path,receipt,context_identity,coordinate_hex,horizon,source_key,fold,algorithm):
    expected=dict(context_identity=context_identity,query_coordinate_hex=coordinate_hex,horizon=horizon,
                  source_key=source_key,query_fold=fold,algorithm=algorithm)
    if path.name.startswith('.') or path.suffix!='.csv':raise ValueError('Incomplete checkpoint name')
    if any(receipt.get(k)!=v for k,v in expected.items()):raise ValueError('Stale checkpoint lineage')
    if file_sha256(path)!=receipt['sha256']:raise ValueError('Incomplete or changed checkpoint')
    data=pd.read_csv(path)
    if list(data.columns)!=['donor_fold','destination','reason','pair_count']:raise ValueError('Unexpected checkpoint schema')
    if (not all(pd.api.types.is_integer_dtype(data[k]) for k in data) or data.isna().any().any()
        or data.pair_count.le(0).any() or data.donor_fold.eq(fold).any()
        or data.duplicated(['donor_fold','destination','reason']).any()
        or not data.destination.eq(-3).equals(data.reason.gt(0))
        or int(data.pair_count.sum())!=receipt['donors']):raise ValueError('Invalid checkpoint count/role ledger')
    return data
