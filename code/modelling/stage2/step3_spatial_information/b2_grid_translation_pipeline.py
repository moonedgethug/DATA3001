"""Run the mandatory support gate before developing/running costly geometry."""
import time
STARTED = time.monotonic()
import json
import numpy as np
import pandas as pd

from data3001.modelling.baselines.b2_grid_translation import (
    KEY, translation_table, fitting_counts, query_support, evaluation_weights)
from data3001.modelling.baselines.b2_grid_translation_inputs import (
    ROOT, prepare, load_inputs, Budget)
from data3001.modelling.common.runtime import save_frame, save_json
from data3001.paths import file_sha256


def support_gate():
    paths, run, cfg, guard, prior = prepare()
    budget = Budget(run,cfg,'pilot',prior_seconds=prior,started=STARTED)
    print('RUN',run['results'].name,flush=True)
    try:
        train,query,roles = load_inputs(paths,run,cfg)
        offsets=translation_table()
        save_frame(paths,run['results']/'translations.parquet',offsets)
        save_json(paths,run['provenance']/'translation_freeze.json',dict(
            seed=20261107,generator='PCG64',numpy_version=np.__version__,count=100,
            sha256=file_sha256(run['results']/'translations.parquet'),frozen_before_counts=True))
        weights=evaluation_weights(query)
        save_frame(paths,run['results']/'query_starts.parquet',query.assign(evaluation_weight=weights))
        query_pairs=np.empty((101,len(query)),dtype=np.int32)
        query_cells=np.empty_like(query_pairs)
        summaries=[]
        all_offsets=[(0.,0.)]+list(offsets[['delta_lon','delta_lat']].itertuples(index=False,name=None))
        first_problem=True
        for grid,offset in enumerate(all_offsets):
            budget.check()
            counts,support=fitting_counts(train,offset)
            q=query_support(query,support,offset)
            save_frame(paths,run['results']/'counts'/f'{grid:03}.parquet',counts)
            save_frame(paths,run['results']/'row_support'/f'{grid:03}.parquet',support)
            query_pairs[grid]=q.pairs.to_numpy()
            query_cells[grid]=q.origin.to_numpy()
            missing=~q.supported.to_numpy()
            summaries.append(dict(grid=grid,delta_lon=offset[0],delta_lat=offset[1],
                unsupported_queries=int(missing.sum()),unsupported_query_fraction=float(missing.mean()),
                unsupported_weight=float(weights[missing].sum()),unsupported_ids=int(query.loc[missing,'id'].nunique()),
                fitted_rows=len(support),transition_entries=len(counts),training_pairs=int(counts['count'].sum()),
                min_query_pair_support=int(q.pairs.min()),min_query_id_support=int(q.ids.min())))
            if missing.any() and first_problem:
                print('SUPPORT_GAP_DETECTED',grid,int(missing.sum()),'finishing required full support table only',flush=True)
                first_problem=False
            if grid%10==0 or grid==100:
                info=budget.check()
                print('SUPPORT_PROGRESS',grid,'of 100',round(info['elapsed_seconds'],2),'seconds',flush=True)
        paths.publish(run['results']/'query_support_arrays.npz',lambda f:np.savez_compressed(f,pairs=query_pairs,cells=query_cells))
        summary=pd.DataFrame(summaries)
        save_frame(paths,run['results']/'support_summary.csv',summary)
        missing_any=(query_pairs<=0).any(axis=0)
        affected=query.loc[missing_any].copy()
        affected['evaluation_weight']=weights[missing_any]
        affected['missing_shift_count']=(query_pairs[1:,missing_any]<=0).sum(axis=0)
        save_frame(paths,run['results']/'affected_queries.parquet',affected)
        passed=not missing_any.any()
        status='SUPPORT_PASSED_PILOT_INCOMPLETE' if passed else 'STOPPED_UNSUPPORTED_ORIGIN'
        result=dict(status=status,complete_all_shift_support_scan=True,
            original_unsupported=int(summary.iloc[0].unsupported_queries),
            affected_shift_count=int((summary.iloc[1:].unsupported_queries>0).sum()),
            affected_queries=int(missing_any.sum()),affected_query_fraction=float(missing_any.mean()),
            affected_evaluation_weight=float(weights[missing_any].sum()),affected_ids=int(affected.id.nunique()),
            missing_grid_query_combinations=int((query_pairs[1:]<=0).sum()),
            query_count=len(query),query_ids=int(query.id.nunique()),
            formal_started=False,scores_computed=False,geometry_pilot_started=False,
            outer_targets_read=False,final_test_read=False,guard_denials=guard.denied)
        save_json(paths,run['results']/'support_gate.json',result)
        save_json(paths,run['provenance']/'pilot_support_resources.json',budget.check())
        print(json.dumps(result),flush=True)
        return 0 if passed else 2
    except Exception as error:
        save_json(paths,run['provenance']/'stopped_error.json',dict(
            error=repr(error),stage='pilot_support',resources=budget.snapshot(),guard_denials=guard.denied,
            formal_started=False,outer_targets_read=False))
        raise


if __name__=='__main__':
    raise SystemExit(support_gate())
