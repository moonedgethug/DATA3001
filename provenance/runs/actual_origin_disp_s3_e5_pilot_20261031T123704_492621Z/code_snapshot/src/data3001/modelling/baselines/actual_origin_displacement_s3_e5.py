"""E5 query-level scoring adapters; training counts remain raw eligible pairs."""
import numpy as np
import pandas as pd
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_selection import (
    ForecastCase,CaseEvaluator,GRID,GAMMAS,best_brier,
)
from data3001.modelling.baselines.local_endpoint_adaptive_s3_e2 import vector
from data3001.modelling.common.prediction_regions import probability_region


def primary_query_weights(queries):
    """A single horizon: equal times within ID/origin, IDs within origin, origins."""
    if len(queries)==0 or queries.horizon_days.nunique()!=1:raise ValueError('One nonempty horizon required')
    ntime=queries.groupby(['origin_cell_1','id']).id.transform('size')
    nids=queries.groupby('origin_cell_1').id.transform('nunique')
    weights=1/(queries.origin_cell_1.nunique()*nids*ntime)
    if not np.isclose(weights.sum(),1,atol=1e-12,rtol=0):raise AssertionError('Query weighting failed')
    return weights.to_numpy(float)


def make_evaluator(records,base,check=lambda:None):
    table=pd.DataFrame([r['query'] for r in records]);w=primary_query_weights(table);cases=[]
    for record,weight in zip(records,w):
        row=record['query'];key=(row['horizon_days'],row['origin_cell_1'])
        p,q=base.rows[key],record['q'];truth=record['truth'];support=base.support_lookup[key]
        mask=(p>0)|(q>0)|(base.states==truth)|(base.states==-2)
        cases.append(ForecastCase(base.states[mask],p[mask],q[mask],truth,
                                  support['normalised_support_ratio'],float(weight),('pilot_inner_0_1',key[1])))
    return CaseEvaluator(cases,check)


def pilot_references(records,base,check=lambda:None):
    """Timing-only choices on the frozen pilot roster, never outer performance."""
    table=pd.DataFrame([r['query'] for r in records]);weights=primary_query_weights(table)
    references={}
    for model,gammas in [('Fixed',(0.,)),('LocalEndpointAdaptive',GAMMAS)]:
        candidates=[]
        for gamma in gammas:
            for a in GRID:
                check();total=np.zeros(4)
                for record,w in zip(records,weights):
                    row=record['query'];p=vector(base,row['horizon_days'],row['origin_cell_1'],model,a,gamma)
                    mask,region=probability_region(p,base.states);idx=base.index[record['truth']]
                    total+=w*np.array([1+p@p-2*p[idx],region['region90_cells'],float(mask[idx]),region['region90_mass']])
                candidates.append(dict(a=a,gamma=gamma,brier=float(total[0]),region90_cells=float(total[1]),
                                       region90_hit=float(total[2]),region90_mass=float(total[3])))
        references[model]=best_brier(candidates)
    return references
