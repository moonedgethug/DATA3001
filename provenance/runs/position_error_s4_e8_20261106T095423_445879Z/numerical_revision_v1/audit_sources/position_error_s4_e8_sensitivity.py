"""Correct full-covariance matching for the predeclared inner rho diagnostic.

Main E8 rho=0 predictions are unchanged. The original pilot's common-rho C
diagnostic matched marginal variances but not average cross-covariance.
"""
import argparse
import json
import time
import numpy as np
import pandas as pd
from data3001.modelling.common.runtime import save_frame,save_json
from data3001.modelling.baselines import position_error_s4_e8 as model
from data3001.modelling.baselines import position_error_s4_e8_inputs as inputs
from data3001.modelling.baselines import position_error_s4_e8_pipeline as pipe


def run(paths,folders,cfg,approval,guard):
    start=time.monotonic()
    attempts=[json.loads(p.read_text()) for p in folders['provenance'].glob('pilot_attempt_*_resources.json')]
    prior=sum(a['elapsed_seconds'] for a in attempts)
    gate=json.loads(sorted(folders['provenance'].glob('pilot_attempt_*_gate.json'))[-1].read_text())
    pilot=folders['results']/f"pilot_attempt_{gate['attempt']}"
    roster=inputs.read_frame(pilot/'roster.parquet');original=inputs.read_frame(pilot/'rho_sensitivity.parquet')
    train,ledger=inputs.load_training(cfg);roles={}
    for role in ['C_T0','C_T1']:
        fit,query,target=inputs.load_role(cfg,role,train,ledger)
        roles[role]=(fit,query,target,pipe.index_for(fit,cfg),pipe.arrays(fit))
    rows=[]
    for row in roster.itertuples(index=False):
        pipe.check_budget(folders,cfg,start,'pilot',prior)
        fit,query,target,index,packed=roles[row.role];q=query.iloc[row.query_position]
        selected,_=index.query(q.lon,q.lat,cfg['k']);p,sd,ok=[a[selected] for a in packed]
        common=model.covariance_matched(sd,ok)
        key=(row.role,int(q.id),int(q.origin_source_obs),0)
        truth=target.iloc[row.query_position][['endpoint_lon','endpoint_lat']].to_numpy(float)
        for rho in [-.5,.5]:
            effective_rho=0. if not ok.any() else float(rho*np.mean(sd[ok,0]*sd[ok,1])/np.prod(common[ok][0]))
            if ok.any():
                np.testing.assert_allclose(effective_rho*np.prod(common[ok][0]),rho*np.mean(sd[ok,0]*sd[ok,1]),rtol=1e-14)
            f,_=model.predict(p,common,ok,energy_count=gate['energy_count'],region_count=gate['region_count'],key=key,rho=effective_rho)
            scores=model.evaluate(p,common,ok,f,truth,key=key,rho=effective_rho)['EndpointCI']
            rows.append(dict(role=row.role,id=int(q.id),origin_source_obs=int(q.origin_source_obs),rho=rho,
                    effective_common_rho=effective_rho,model='MatchedSpread',**scores))
    corrected=pd.concat([original[original.model.eq('EndpointCI')],pd.DataFrame(rows)],ignore_index=True)
    save_frame(paths,folders['results']/'rho_sensitivity_corrected.parquet',corrected)
    receipt=pipe.resources(folders,start);receipt.update(completed=True,prior_pilot_seconds=prior,
        cumulative_pilot_seconds=prior+receipt['elapsed_seconds'],queries=128,primary_rho_zero_unchanged=True,
        correction='C at nonzero rho now matches average full donor covariance; previous common-rho C diagnostic is superseded; B rows unchanged',
        fitted_parameters=False,outer_outcomes_used=False)
    save_json(paths,folders['provenance']/'pilot_correlation_correction_resources.json',receipt)
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    run(*inputs.context(a.run))
