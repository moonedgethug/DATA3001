"""Outcome-independent 90% CDF arithmetic repair; distributions/ES unchanged."""
import argparse
import copy
import json
import os
import time
import numpy as np
import pandas as pd
from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_frame,save_json
from data3001.modelling.baselines import position_error_s4_e8 as model
from data3001.modelling.baselines import position_error_s4_e8_inputs as inputs
from data3001.modelling.baselines import position_error_s4_e8_pipeline as pipe
from data3001.modelling.baselines.position_error_s4_e8_formal import aggregate
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography


def link(source,dest):
    dest.symlink_to(os.path.relpath(source,dest.parent),target_is_directory=source.is_dir())


def corrected_region(xy,w,old):
    r=copy.deepcopy(old);delta=xy-np.asarray(r['centre'])
    distances=np.einsum('ij,jk,ik->i',delta,np.asarray(r['inverse']),delta)
    cutoff=model.weighted_quantile(distances,w)
    r['cutoff']=cutoff
    r['attained_mass']=float(w[distances<=cutoff+1e-12].sum())
    r['area_km2']=float(np.pi*cutoff*np.sqrt(np.prod(r['eigenvalues']))) if r['rank']==2 else 0.
    return r


def revise(paths,parent,cfg,approval,guard):
    run={key:value/'numerical_revision_v1' for key,value in parent.items()}
    for p in run.values():p.mkdir()
    folder=run['results']/'formal';folder.mkdir();start=time.monotonic();completed=False
    original_formal=json.loads((parent['provenance']/'formal_resources.json').read_text())
    original_audit=json.loads((parent['provenance']/'audit_resources.json').read_text())
    prior=original_formal['elapsed_seconds']
    save_json(paths,run['provenance']/'prior_resources.json',dict(formal_seconds=prior,audit_seconds=original_audit['elapsed_seconds']))
    hashes=pipe.source_snapshot(paths,run,'revision_sources')
    for p in parent['provenance'].glob('pilot_*_resources.json'):link(p,run['provenance']/p.name)
    for p in parent['provenance'].glob('pilot_attempt_*_gate.json'):link(p,run['provenance']/p.name)
    for p in parent['results'].glob('pilot_attempt_*'):link(p,run['results']/p.name)
    link(parent['results']/'rho_sensitivity_corrected.parquet',run['results']/'rho_sensitivity_corrected.parquet')
    link(parent['provenance']/'quantile_regression_tests.txt',run['provenance']/'tests.txt')
    save_json(paths,run['provenance']/'correction_definition.json',dict(
        trigger='Exact synthetic CDF check: summing 16000 weights of 1/16000 makes the floating cumulative probability at atom 14400 slightly below .9 and incorrectly selects atom 14401.',
        correction='Use exact integer probability units for equal and stratified component weights; compensated normalized sums for general descriptive quantiles.',
        mathematical_probability=.9,model_distributions_changed=False,training_data_changed=False,
        seeds_changed=False,Energy_Scores_changed=False,prior_outputs_retained=True,
        outer_outcomes_previously_seen=True,correction_selected_from_outcomes=False,
        original_audit_limitation='The first independent region path also used ordinary floating cumulative sums. Exact CDF fixtures expose a shared arithmetic issue that seed replication alone cannot reveal.'))
    try:
        fit,ledger=inputs.load_training(cfg);fit,query,_=inputs.load_role(cfg,'C_outer',fit,ledger)
        points,sd,ok=pipe.arrays(fit);_,base_xy=model.coordinates(points)
        cells={int(c):g.index.to_numpy() for c,g in fit.groupby('origin_cell_1')}
        d=inputs.read_frame(parent['results']/'formal/donor_diagnostics.parquet')
        examples=json.loads((parent['results']/'formal/example_selection.json').read_text())['query_positions']
        for p in (parent['results']/'formal').iterdir():
            if p.name=='forecasts.jsonl' or (p.name.startswith('example_') and p.suffix=='.json' and p.name!='example_selection.json'):continue
            link(p,folder/p.name)
        geo=Geography(paths);baseline_cache={};changed={name:0 for name in model.MODELS}
        with (parent['results']/'formal/forecasts.jsonl').open() as source,(folder/'forecasts.jsonl').open('x') as out,(folder/'donors.i32').open('rb') as raw:
            for j,line in enumerate(source):
                if j%128==0:pipe.check_budget(parent,cfg,start,'formal',prior)
                packet=json.loads(line);selected=np.frombuffer(raw.read(int(d.iloc[j].donors)*4),dtype='<i4')
                assert pipe.digest_indices(selected)==d.iloc[j].lineage_digest
                q=query.iloc[j];f=packet['forecast'];n=len(selected)
                regions={'ExactPoint':corrected_region(base_xy[selected],np.full(n,1/n),f['ExactPoint']['region'])}
                for name,widths in [('EndpointCI',sd[selected]),('MatchedSpread',model.covariance_matched(sd[selected],ok[selected]))]:
                    cloud,w,_=model.component_cloud(points[selected],widths,ok[selected],f[name]['region_count'],tuple(packet['key']))
                    _,xy=model.coordinates(cloud)
                    regions[name]=corrected_region(xy,w,f[name]['region'])
                    if j in examples:
                        saved=np.load(folder/f'example_{j}_{name}.npz')
                        np.testing.assert_array_equal(cloud,saved['lonlat']);np.testing.assert_array_equal(w,saved['weight'])
                cell=int(q.origin_cell_1)
                if cell not in baseline_cache:
                    idx=cells[cell];r=corrected_region(base_xy[idx],np.full(len(idx),1/len(idx)),f['B2Point']['region'])
                    baseline_cache[cell]=(r,geo.areas(r))
                regions['B2Point']=baseline_cache[cell][0]
                for name,r in regions.items():
                    different=r['cutoff']!=f[name]['region']['cutoff'];changed[name]+=int(different)
                    f[name]['region']=r
                    if different:f[name].update(baseline_cache[cell][1] if name=='B2Point' else geo.areas(r))
                out.write(json.dumps(packet,allow_nan=False,separators=(',',':'))+'\n')
                if j in examples:
                    save_json(paths,folder/f'example_{j}.json',dict(query_position=j,origin=[float(q.lon),float(q.lat)],forecast=f))
                if (j+1)%2048==0:print('exact-CDF region correction',j+1,'/33971',round(time.monotonic()-start,1),'s',flush=True)
        freeze_files=[p for p in folder.iterdir() if p.is_file()]
        save_json(paths,run['provenance']/'forecast_freeze.json',dict(cases=33971,IDs=45,source_sha256=hashes,
            output_sha256={str(p.relative_to(inputs.ROOT)):file_sha256(p) for p in freeze_files},
            distributions_identical_to_original=True,original_distribution_freeze=str(parent['provenance']/'forecast_freeze.json'),
            outer_outcomes_previously_seen=True,outer_outcomes_read_during_this_refinement=False,
            outcome_independent_numerical_correction=True,cutoffs_changed=changed,forecast_seconds=time.monotonic()-start))
        target=inputs.release_outer_targets(run,cfg,approval).sort_values(inputs.KEY).reset_index(drop=True)
        old=inputs.read_frame(parent['results']/'case_scores.parquet')
        updates=[]
        with (folder/'forecasts.jsonl').open() as source:
            for j,line in enumerate(source):
                if j%256==0:pipe.check_budget(parent,cfg,start,'formal',prior)
                packet=json.loads(line);truth=target.iloc[j][['endpoint_lon','endpoint_lat']].to_numpy(float)
                _,xy=model.coordinates(truth[None,:])
                for name,f in packet['forecast'].items():
                    r=f['region'];updates.append(dict(query_position=j,model=name,h90=float(model.inside_region(xy,r)[0]),
                        area90_km2=r['area_km2'],mass90=r['attained_mass'],rank=r['rank'],
                        **{col:f[col] for col in ['land_area_km2','wet_area_km2','outside_D_area_km2']}))
        updates=pd.DataFrame(updates);cols=[c for c in updates if c not in ['query_position','model']]
        cases=old.drop(columns=cols).merge(updates,on=['query_position','model'],validate='one_to_one',sort=False)
        np.testing.assert_array_equal(cases.energy_km,old.energy_km)
        np.testing.assert_array_equal(cases.auxiliary,old.auxiliary)
        save_frame(paths,run['results']/'case_scores.parquet',cases)
        aggregate(paths,run,cfg,cases)
        for j in examples:
            truth=target.iloc[j][['endpoint_lon','endpoint_lat']].to_numpy(float)
            scores=cases[cases.query_position.eq(j)].set_index('model').to_dict('index')
            save_json(paths,folder/f'example_{j}_observation.json',dict(truth=truth.tolist(),scores=scores))
        save_json(paths,run['provenance']/'correction_invariance.json',dict(cases=33971,models=4,
            ES_bit_identical=True,auxiliary_bit_identical=True,donor_arrays_identical=True,
            fixed_example_quadrature_clouds_bit_identical=True,cutoffs_changed=changed))
        pipe.check_budget(parent,cfg,start,'formal',prior);completed=True
        save_json(paths,parent['provenance']/'authoritative_revision.json',dict(
            results=str(run['results'].relative_to(inputs.ROOT)),provenance=str(run['provenance'].relative_to(inputs.ROOT)),
            reason='Exact 90% CDF arithmetic correction; original region results superseded; all ES values unchanged',
            independent_audit_pending=True))
    finally:
        r=pipe.resources(parent,start);r.update(completed=completed,this_revision_seconds=r['elapsed_seconds'],prior_formal_seconds=prior,
            elapsed_seconds=prior+r['elapsed_seconds'],outer_targets_read=completed,outer_endpoint_errors_read=False,final_test_access=False,denied_access=guard.denied)
        save_json(paths,run['provenance']/'formal_resources.json',r)
        print(json.dumps(r,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    revise(*inputs.context(a.run))
