"""Pilot gates and outcome-sealed forecasting for the approved E8 design."""
import hashlib
import json
import os
from pathlib import Path
import resource
import time

import numpy as np
import pandas as pd

from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_frame,save_json
from data3001.modelling.baselines import position_error_s4_e8 as model
from data3001.modelling.baselines import position_error_s4_e8_inputs as inputs
from data3001.modelling.baselines.exact_origin_s4_e7 import NeighbourIndex
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography


def index_for(fit,cfg):
    return NeighbourIndex(fit.lon.to_numpy(),fit.lat.to_numpy(),cfg['radius_m'],cfg['distance_tolerance_m'])


def arrays(fit):
    return (fit[['endpoint_lon','endpoint_lat']].to_numpy(),fit[['sd_e_km','sd_n_km']].to_numpy(),
            fit.ci_2d_usable.to_numpy(bool))


def digest_indices(indices):
    return hashlib.sha256(np.asarray(indices,dtype='<i8').tobytes()).hexdigest()


def weights(frame):
    ids=frame.id.nunique()
    return 1/(ids*frame.groupby('id').id.transform('size').to_numpy())


def diagnostic(fit,selected,distance):
    part=fit.iloc[selected];counts=part.id.value_counts()
    reasons=part.loc[~part.ci_2d_usable].groupby(['error_status_lon','error_status_lat']).size()
    return dict(donors=len(selected),donor_IDs=len(counts),largest_ID_share=float(counts.max()/len(selected)),
                error_available_fraction=float(part.ci_2d_usable.mean()),fallback_mass=float((~part.ci_2d_usable).mean()),
                fallback_reasons=json.dumps({str(k):int(v) for k,v in reasons.items()},sort_keys=True),
                farthest_m=float(distance[-1]),lineage_digest=digest_indices(selected))


def source_snapshot(paths,run,label):
    folder=run['provenance']/label;folder.mkdir()
    files=list((inputs.ROOT/'src/data3001/modelling/baselines').glob('*position_error_s4_e8*.py'))
    files += [inputs.ROOT/'tests/test_modelling_position_error_s4_e8.py',inputs.ROOT/'configs/position_error_s4_e8.json']
    hashes={}
    for p in files:
        paths.publish(folder/p.name,lambda f,p=p:f.write(p.read_bytes()))
        hashes[str(p.relative_to(inputs.ROOT))]=file_sha256(p)
    save_json(paths,folder/'hashes.json',hashes)
    return hashes


def resources(run,start):
    return dict(elapsed_seconds=time.monotonic()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                retained_bytes=sum(p.stat().st_size for d in run.values() for p in d.rglob('*') if p.is_file()))


def check_budget(run,cfg,start,phase,prior_seconds=0):
    r=resources(run,start)
    if r['elapsed_seconds']+prior_seconds>cfg['seconds'][phase]:raise TimeoutError(phase+' cumulative time budget')
    if r['peak_rss_bytes']>cfg['rss_gib']*2**30:raise MemoryError('RSS budget')
    if r['retained_bytes']>cfg['storage_gib']*2**30:raise OSError('Storage budget')
    return r


def choose_pilot(fit,query,index,role,cfg):
    """Fixed sorted-key pool, then balanced support and error-availability strata."""
    pool=set(np.linspace(0,len(query)-1,256,dtype=int).tolist())
    for _,g in query.groupby('id',sort=True):pool.update([int(g.index[0]),int(g.index[-1])])
    details=[]
    for j in sorted(pool):
        q=query.iloc[j];selected,d=index.query(q.lon,q.lat,cfg['k'])
        if not len(selected):raise ValueError('Unexpected unsupported pilot candidate')
        a=float(fit.iloc[selected].ci_2d_usable.mean())
        availability=0 if a==0 else 1 if a<.5 else 2 if a<.9 else 3 if a<1 else 4
        details.append(dict(role=role,query_position=j,availability_stratum=availability,
                            support_stratum=int(len(selected)>=cfg['k']),**diagnostic(fit,selected,d)))
    frame=pd.DataFrame(details)
    groups=[]
    for _,g in frame.groupby(['availability_stratum','support_stratum'],sort=True):
        positions=g.index.to_numpy();order=np.linspace(0,len(positions)-1,len(positions),dtype=int)
        # Spread early picks across the complete sorted pool, then fill deterministically.
        first=np.unique(np.linspace(0,len(positions)-1,min(64,len(positions)),dtype=int))
        groups.append(list(positions[np.r_[first,np.setdiff1d(order,first)]]))
    chosen=[]
    while len(chosen)<cfg['pilot_queries_per_role']:
        for g in groups:
            if g and len(chosen)<cfg['pilot_queries_per_role']:chosen.append(g.pop(0))
    return frame.loc[chosen].sort_values('query_position').reset_index(drop=True)


def predict_case(fit,packed,selected,baseline_indices,key,energy_count,region_count,geo=None,rho=0.,retain=False):
    points,sd,usable=packed
    f,clouds=model.predict(points[selected],sd[selected],usable[selected],energy_count=energy_count,
                          region_count=region_count,key=key,rho=rho,retain_cloud=True)
    baseline=model.point_forecast(points[baseline_indices],energy_count,key)
    f['B2Point']=baseline
    clouds['B2Point']=(points[baseline_indices],np.full(len(baseline_indices),1/len(baseline_indices)))
    if geo is not None:
        for name,packet in f.items():
            packet.update(geo.masses(*clouds[name]));packet.update(geo.areas(packet['region']))
    return f,clouds if retain else None


def score_case(packed,selected,baseline_indices,forecast,truth,key,rho=0.):
    points,sd,usable=packed
    other={k:v for k,v in forecast.items() if k!='B2Point'}
    rows=model.evaluate(points[selected],sd[selected],usable[selected],other,truth,key=key,rho=rho)
    rows['B2Point']=model.evaluate_point(points[baseline_indices],forecast['B2Point'],truth)
    for name in rows:
        for col in ['land_mass','outside_D_mass','land_area_km2','wet_area_km2','outside_D_area_km2']:
            if col in forecast[name]:rows[name][col]=forecast[name][col]
    return rows


def pilot(paths,run,cfg,approval):
    attempts=list(run['provenance'].glob('pilot_attempt_*_resources.json'))
    prior=sum(json.loads(p.read_text())['elapsed_seconds'] for p in attempts)
    attempt=len(attempts)+1;label=f'pilot_attempt_{attempt}'
    folder=run['results']/label;folder.mkdir();start=time.monotonic()
    source_snapshot(paths,run,label+'_sources')
    success=False
    try:
        train,ledger=inputs.load_training(cfg)
        geo=Geography(paths);roles={};rosters=[]
        for name in ['C_T0','C_T1']:
            fit,query,target=inputs.load_role(cfg,name,train,ledger);index=index_for(fit,cfg)
            roles[name]=(fit,query,target,index,arrays(fit),{int(c):g.index.to_numpy() for c,g in fit.groupby('origin_cell_1')})
            roster=choose_pilot(fit,query,index,name,cfg);rosters.append(roster)
        roster=pd.concat(rosters,ignore_index=True);save_frame(paths,folder/'roster.parquet',roster)
        assert len(roster)==128
        # Verify current local indices reproduce the previously frozen E7 donors.
        old=inputs.read_frame(inputs.ROOT/'results/runs'/cfg['e7_run']/'inner_cases.parquet',
            columns=inputs.KEY+['role','k','lineage_digest'])
        old=old[old.k.eq(8000)].set_index(['role','id','origin_source_obs'])
        all_scores=[];checks=[];bench=[];rho_rows=[]
        energy_count=cfg['energy_ladder'][0];region_count=cfg['region_ladder'][0]
        for number,row in enumerate(roster.itertuples(index=False)):
            check_budget(run,cfg,start,'pilot',prior)
            fit,query,target,index,packed,cells=roles[row.role];q=query.iloc[row.query_position]
            selected,distance=index.query(q.lon,q.lat,cfg['k']);baseline=cells[int(q.origin_cell_1)]
            assert digest_indices(selected)==old.loc[(row.role,int(q.id),int(q.origin_source_obs)),'lineage_digest']
            if number%16==0:
                exact,ed=index.exhaustive(q.lon,q.lat,cfg['k'])
                np.testing.assert_array_equal(selected,exact);np.testing.assert_allclose(distance,ed,atol=1e-6,rtol=0)
            truth=target.iloc[row.query_position][['endpoint_lon','endpoint_lat']].to_numpy(float)
            key=(row.role,int(q.id),int(q.origin_source_obs),0)
            base_start=time.monotonic()
            f,clouds=predict_case(fit,packed,selected,baseline,key,energy_count,region_count,geo,retain=True)
            scores=score_case(packed,selected,baseline,f,truth,key)
            bench.append(time.monotonic()-base_start)
            rep_key=(row.role,int(q.id),int(q.origin_source_obs),1)
            repeat,rep_clouds=predict_case(fit,packed,selected,baseline,rep_key,energy_count,region_count,None,retain=True)
            repeat_scores=score_case(packed,selected,baseline,repeat,truth,rep_key)
            for name,score in scores.items():
                all_scores.append(dict(role=row.role,id=int(q.id),origin_source_obs=int(q.origin_source_obs),
                    query_position=int(row.query_position),model=name,replicate=0,**score,
                    error_available_fraction=row.error_available_fraction))
                all_scores.append(dict(role=row.role,id=int(q.id),origin_source_obs=int(q.origin_source_obs),
                    query_position=int(row.query_position),model=name,replicate=1,**repeat_scores[name],
                    error_available_fraction=row.error_available_fraction))
                p,w=rep_clouds[name];_,xy=model.coordinates(p)
                verified_mass=float(w @ model.inside_region(xy,f[name]['region']))
                checks.append(dict(role=row.role,id=int(q.id),origin_source_obs=int(q.origin_source_obs),model=name,
                    mass_replication_error=abs(verified_mass-f[name]['region']['attained_mass']),
                    area_relative_change=abs(f[name]['region']['area_km2']-repeat[name]['region']['area_km2'])/max(f[name]['region']['area_km2'],1e-20),
                    hit_changed=abs(score['h90']-repeat_scores[name]['h90'])))
            for rho in [-.5,.5]:
                sensitivity,_=model.predict(packed[0][selected],packed[1][selected],packed[2][selected],
                    energy_count=energy_count,region_count=region_count,key=key,rho=rho)
                result=model.evaluate(packed[0][selected],packed[1][selected],packed[2][selected],sensitivity,truth,key=key,rho=rho)
                for name in ['EndpointCI','MatchedSpread']:
                    rho_rows.append(dict(role=row.role,id=int(q.id),origin_source_obs=int(q.origin_source_obs),rho=rho,model=name,**result[name]))
            if number in [0,32,64,96]:
                save_json(paths,folder/f'example_{number}.json',{'role':row.role,'id':int(q.id),'origin_source_obs':int(q.origin_source_obs),
                    'origin':[float(q.lon),float(q.lat)],'truth':truth.tolist(),'forecast':f})
                for name,(p,w) in clouds.items():
                    np.savez_compressed(folder/f'example_{number}_{name}.npz',lonlat=p,weight=w)
            if (number+1)%16==0:print(label,number+1,'/128',round(time.monotonic()-start,1),'s',flush=True)
        scores=pd.DataFrame(all_scores);diagnostics=pd.DataFrame(checks)
        save_frame(paths,folder/'case_scores.parquet',scores);save_frame(paths,folder/'precision.csv',diagnostics)
        save_frame(paths,folder/'rho_sensitivity.parquet',pd.DataFrame(rho_rows))
        primary=scores[scores.replicate.eq(0)].copy();rep=scores[scores.replicate.eq(1)].copy()
        grouped=[]
        for name,g in primary.groupby('model',sort=False):
            w=weights(g);other=rep[rep.model.eq(name)].sort_values(['role','id','origin_source_obs'])
            g=g.sort_values(['role','id','origin_source_obs']);w=weights(g)
            delta=(g.energy_km.to_numpy()-other.energy_km.to_numpy())
            grouped.append(dict(model=name,energy_km=float(w@g.energy_km),h90=float(w@g.h90),area90_km2=float(w@g.area90_km2),
                repeat_energy_change=float(w@delta),repeat_hit_change=float(w@(g.h90.to_numpy()-other.h90.to_numpy())),
                repeat_area_relative=float(abs(w@(g.area90_km2.to_numpy()-other.area90_km2.to_numpy()))/(w@g.area90_km2)),
                repeat_delta_energy=float(w@(g.delta_energy_vs_exact_km.fillna(0).to_numpy()-other.delta_energy_vs_exact_km.fillna(0).to_numpy())),
                numerical_se_delta=float(np.sqrt(np.sum((w*g.energy_mc_se.to_numpy())**2)))))
        summary=pd.DataFrame(grouped).set_index('model')
        threshold=.0001*summary.loc['ExactPoint','energy_km']
        numeric=(diagnostics.mass_replication_error.max()<=.005 and
                 summary.repeat_hit_change.abs().max()<=.001 and summary.repeat_area_relative.max()<=.005 and
                 abs(summary.loc['EndpointCI','repeat_delta_energy'])<=threshold and
                 3*summary.loc['EndpointCI','numerical_se_delta']<=threshold)
        projected=33971*float(np.mean(bench))+180
        r=check_budget(run,cfg,start,'pilot',prior)
        resource_ok=2*projected<=cfg['seconds']['formal'] and 2*r['peak_rss_bytes']<cfg['rss_gib']*2**30
        gate={'passed':bool(numeric and resource_ok),'numerical_passed':bool(numeric),'resource_passed':bool(resource_ok),
              'attempt':attempt,'energy_count':energy_count,'region_count':region_count,'queries':128,
              'formal_projected_seconds':projected,'formal_projection_2x_seconds':2*projected,
              'mean_case_seconds':float(np.mean(bench)),'max_mass_replication_error':float(diagnostics.mass_replication_error.max()),
              'max_weighted_area_repeat_change':float(summary.repeat_area_relative.max()),
              'max_weighted_hit_repeat_change':float(summary.repeat_hit_change.abs().max()),
              'delta_ES_precision_threshold_km':threshold,'models_run_on_outer':False,'outer_targets_read':False}
        save_frame(paths,folder/'summary.csv',summary.reset_index());save_json(paths,folder/'gate.json',gate)
        save_json(paths,run['provenance']/(label+'_gate.json'),gate)
        success=True
        print(json.dumps(gate,indent=2),flush=True)
        return gate
    finally:
        r=resources(run,start);r.update(attempt=attempt,completed=success)
        save_json(paths,run['provenance']/(label+'_resources.json'),r)
