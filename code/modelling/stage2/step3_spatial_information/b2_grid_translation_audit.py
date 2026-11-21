"""Independent count/support audit of a stopped G1 gate; never reads outcomes."""
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import save_json
from data3001.modelling.baselines.b2_grid_translation_inputs import ROOT, Guard, Budget, INPUT_HASHES


def reference_cells(lon,lat,offset):
    # Independent bin-search implementation of the specified transformed axes.
    dx,dy=offset
    u=(np.asarray(lon,dtype=float)+180-dx)%360
    v=np.asarray(lat,dtype=float)+90-dy
    x=np.searchsorted(np.arange(361,dtype=float),u,side='right')-1
    y=np.searchsorted(np.arange(-1,182,dtype=float),v,side='right')-2
    return (y*360+x).astype(np.int64)


def read(path,columns=None):
    with path.open('rb') as f:
        return pd.read_parquet(f,columns=columns)


def independent_id_support(origin,ids):
    unique_ids,dense_ids=np.unique(np.asarray(ids),return_inverse=True)
    packed=np.asarray(origin,dtype=np.int64)*len(unique_ids)+dense_ids
    keys,counts=np.unique(packed,return_counts=True)
    rows=keys//len(unique_ids)
    n_ids=np.bincount(rows,minlength=65536)
    largest=np.zeros(65536,dtype=np.int64)
    np.maximum.at(largest,rows,counts)
    return n_ids,largest


def audit(name):
    started=time.monotonic()
    if Path(name).name!=name or not name.startswith('b2_grid_translation_'):
        raise ValueError('Invalid run identity')
    paths=project_paths()
    run={'results':ROOT/'results/runs'/name,'provenance':ROOT/'provenance/runs'/name}
    cfg=json.loads((run['provenance']/'run.json').read_text())['config']
    guard=Guard(ROOT,run);sys.addaudithook(guard)
    prior=sum(json.loads(p.read_text())['elapsed_seconds'] for p in run['provenance'].glob('audit_attempt_*/failure.json'))
    prior+=json.loads((run['provenance']/'audit_regression_tests.json').read_text())['elapsed_seconds']
    budget=Budget(run,cfg,'audit',started=started,prior_seconds=prior)
    approval=json.loads((run['provenance']/'approval.json').read_text())
    for p,h in approval['protected_existing_sha256'].items():
        assert file_sha256(ROOT/p)==h,p
    base=ROOT/'results/runs'/cfg['source_run']
    for p,h in INPUT_HASHES.items():assert file_sha256(base/p)==h,p
    train=read(base/'training_coordinates.parquet',columns=['id','lon','lat','endpoint_lon','endpoint_lat','outside'])
    # Input train is sorted in the primary path; count audit is order-invariant.
    query=read(run['results']/'query_starts.parquet')
    shifts=read(run['results']/'translations.parquet')
    freeze=json.loads((run['provenance']/'translation_freeze.json').read_text())
    assert file_sha256(run['results']/'translations.parquet')==freeze['sha256']
    expected=np.random.Generator(np.random.PCG64(20261107)).random((100,2))
    np.testing.assert_array_equal(shifts[['delta_lon','delta_lat']].to_numpy(),expected)
    arrays=np.load(run['results']/'query_support_arrays.npz')
    saved_cells,saved_pairs=arrays['cells'],arrays['pairs']
    summaries=pd.read_csv(run['results']/'support_summary.csv')
    ids,n_per_id=np.unique(query.id.to_numpy(),return_counts=True)
    w=1./(len(ids)*n_per_id[np.searchsorted(ids,query.id.to_numpy())])
    np.testing.assert_array_equal(w,query.evaluation_weight.to_numpy())
    all_offsets=[(0.,0.)]+list(map(tuple,expected))
    all_missing=np.zeros((101,len(query)),dtype=bool)
    for grid,offset in enumerate(all_offsets):
        budget.check()
        origin=reference_cells(train.lon,train.lat,offset)
        destination=np.full(len(train),-2,dtype=np.int64)
        inside=~train.outside.to_numpy(dtype=bool)
        destination[inside]=reference_cells(train.loc[inside,'endpoint_lon'],train.loc[inside,'endpoint_lat'],offset)
        packed=origin*65536+destination+2
        keys,frequencies=np.unique(packed,return_counts=True)
        reference=np.column_stack([keys//65536,keys%65536-2,frequencies])
        recorded=read(run['results']/'counts'/f'{grid:03}.parquet')
        np.testing.assert_array_equal(reference,recorded[['origin','destination','count']].to_numpy())
        totals=np.bincount(origin,minlength=65536)
        np.testing.assert_array_equal(recorded.probability.to_numpy(),frequencies/totals[reference[:,0]])
        n_ids,largest=independent_id_support(origin,train.id.to_numpy())
        rows=read(run['results']/'row_support'/f'{grid:03}.parquet')
        np.testing.assert_array_equal(rows.pairs,totals[rows.origin])
        np.testing.assert_array_equal(rows.ids,n_ids[rows.origin])
        np.testing.assert_array_equal(rows.largest_id_pairs,largest[rows.origin])
        query_cells=reference_cells(query.lon,query.lat,offset)
        np.testing.assert_array_equal(query_cells,saved_cells[grid])
        np.testing.assert_array_equal(totals[query_cells],saved_pairs[grid])
        missing=totals[query_cells]==0;all_missing[grid]=missing
        row=summaries.loc[summaries.grid.eq(grid)].iloc[0]
        assert int(row.unsupported_queries)==int(missing.sum())
        assert abs(float(row.unsupported_weight)-float(w[missing].sum()))<1e-12
        assert int(row.unsupported_ids)==len(np.unique(query.id.to_numpy()[missing]))
        if grid%20==0:print('AUDIT',grid,'of 100',flush=True)
    gate=json.loads((run['results']/'support_gate.json').read_text())
    union=all_missing.any(axis=0)
    assert gate['affected_queries']==int(union.sum())
    assert abs(gate['affected_evaluation_weight']-w[union].sum())<1e-12
    assert gate['missing_grid_query_combinations']==int(all_missing[1:].sum())
    affected=read(run['results']/'affected_queries.parquet')
    np.testing.assert_array_equal(affected[['id','origin_source_obs','horizon_days']],
        query.loc[union,['id','origin_source_obs','horizon_days']])
    np.testing.assert_array_equal(affected.missing_shift_count,all_missing[1:,union].sum(axis=0))
    source=Path(__file__)
    paths.publish(run['provenance']/'audit_sources'/source.name,lambda f:f.write(source.read_bytes()))
    result=dict(status='VERIFIED_SUPPORT_FAILURE' if union.any() else 'VERIFIED_SUPPORT',
        independent_algorithm='Integer-axis bin searches, packed numpy.unique transition counts, bincount support; no fitting_counts/query_support reuse',
        full_count_tables_checked=101,full_query_support_entries_checked=int(all_missing.size),
        max_count_difference=0,max_support_difference=0,
        evaluation_weights_verified=True,translation_seed_verified=True,
        input_and_protected_hashes_verified=True,outer_targets_read=False,final_test_read=False,
        guard_denials=guard.denied,formal_started=False,score_comparison_available=False,
        source_sha256=file_sha256(source),affected_queries=int(union.sum()))
    save_json(paths,run['provenance']/'support_independent_audit.json',result)
    save_json(paths,run['provenance']/'support_audit_resources.json',budget.check())
    print(json.dumps(result),flush=True)


if __name__=='__main__':audit(sys.argv[1])
