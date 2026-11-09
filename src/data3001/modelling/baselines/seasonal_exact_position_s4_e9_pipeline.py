"""Bounded E9 pilot and full-roster support inventory; no model selection."""
import hashlib
import json
import time
import numpy as np
import pandas as pd

from data3001.modelling.common.runtime import save_json, save_frame
from data3001.modelling.baselines import seasonal_exact_position_s4_e9 as model
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_inputs as inputs
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
from data3001.modelling.baselines.position_error_s4_e8_audit import mass_in_frozen


def digest(indices):
    return hashlib.sha256(np.asarray(indices, dtype='<i8').tobytes()).hexdigest()


def diagnostic(fit, selected, distances):
    part = fit.iloc[selected]; counts = part.id.value_counts()
    reasons = part.loc[~part.ci_2d_usable].groupby(['error_status_lon', 'error_status_lat']).size()
    return dict(donors=len(selected), donor_IDs=len(counts), largest_ID_share=float(counts.max()/len(part)),
                error_fallback_mass=float((~part.ci_2d_usable).mean()),
                error_fallback_pairs=int((~part.ci_2d_usable).sum()),
                farthest_m=float(distances[-1]), lineage_digest=digest(selected),
                fallback_reasons=json.dumps({str(k):int(v) for k,v in reasons.items()},sort_keys=True))


def selection_check(index, q, season, found):
    expected = index.query(q.lon, q.lat, season, exhaustive=True)
    for a, b in zip(found[:2], expected[:2]):
        np.testing.assert_array_equal(a[0], b[0])
        np.testing.assert_allclose(a[1], b[1], rtol=0, atol=1e-6)
    assert found[2] == expected[2]


def forecast(fit_arrays, selected, *, role, q, replicate, energy_count, region_count, geography=None):
    annual, seasonal, fallback = selected
    packets, clouds, keys = {}, {}, {}
    for pool, choice in [('Annual', annual), ('Seasonal', seasonal)]:
        if pool == 'Seasonal' and fallback:
            for kind in ['ExactPoint', 'EndpointCI']:
                packets[pool+kind] = packets['Annual'+kind]
                clouds[pool+kind] = clouds['Annual'+kind]
            keys[pool] = keys['Annual']
            continue
        ix = choice[0]
        key = ('s4_e9', role, int(q.id), int(q.origin_source_obs), 7, pool, replicate)
        f, c = model.predict_pool(*[v[ix] for v in fit_arrays], key=key,
                                  energy_count=energy_count, region_count=region_count, geography=geography)
        for ci, kind in [(False, 'ExactPoint'), (True, 'EndpointCI')]:
            packets[pool+kind], clouds[pool+kind] = f[ci], c[ci]
        keys[pool] = key
    return packets, clouds, keys


def score(fit_arrays, selected, packets, truth, keys):
    rows = {}
    for pool, choice in [('Annual', selected[0]), ('Seasonal', selected[1])]:
        if pool == 'Seasonal' and selected[2]:
            for kind in ['ExactPoint', 'EndpointCI']:
                rows[pool+kind] = rows['Annual'+kind].copy()
            continue
        f = {ci:packets[pool+kind] for ci,kind in [(False,'ExactPoint'),(True,'EndpointCI')]}
        ix = choice[0]
        scored = model.score_pool(*[v[ix] for v in fit_arrays], f, truth, tuple(keys[pool]))
        for ci,kind in [(False,'ExactPoint'),(True,'EndpointCI')]:rows[pool+kind] = scored[ci]
    return rows


def pilot(paths, run, cfg, approval, guard):
    budget = inputs.Budget(run, cfg, 'pilot'); completed = False
    folder = run['results']/'pilot';folder.mkdir()
    inputs.snapshot(paths,run,'pilot')
    try:
        train, ledger = inputs.load(cfg)
        _, outer, _ = inputs.role(cfg,'C_outer',train,ledger)
        outer_labels = model.season_labels(outer.origin_time_UTC)
        outer_w = model.case_weights(outer)
        variance_weights = {s:float(np.sum(outer_w[outer_labels.majority_season.eq(s)]**2)) for s in range(4)}
        roster = inputs.read(inputs.ROOT/'results/runs'/cfg['e8_run']/'pilot_attempt_4/roster.parquet')
        assert len(roster)==128 and (roster.groupby('role').size()==64).all()
        geo = Geography(paths); contexts = {}; selections = []; saved_roster = []
        for role in ['C_T0','C_T1']:
            fit, query, targets = inputs.role(cfg,role,train,ledger)
            index = model.SeasonalNeighbours(fit, k=cfg['k'], radius_m=cfg['radius_m'], tolerance_m=cfg['distance_tolerance_m'])
            contexts[role] = (fit,query,targets,index,model.arrays(fit),model.season_labels(query.origin_time_UTC))
        started = time.monotonic()
        old = inputs.read(inputs.ROOT/'results/runs'/cfg['e7_run']/'inner_cases.parquet',
                         columns=inputs.KEY+['role','k','lineage_digest'])
        old = old[old.k.eq(8000)].set_index(['role','id','origin_source_obs'])
        for i,row in enumerate(roster.itertuples(index=False)):
            budget.check();fit,query,target,index,packed,labels=contexts[row.role]
            q=query.iloc[row.query_position];s=int(labels.majority_season.iloc[row.query_position])
            t=time.monotonic();selected=index.query(q.lon,q.lat,s);seconds=time.monotonic()-t
            selection_check(index,q,s,selected)
            assert digest(selected[0][0]) == old.loc[(row.role,int(q.id),int(q.origin_source_obs)),'lineage_digest']
            assert digest(selected[0][0]) == row.lineage_digest
            selections.append(selected)
            saved_roster.append(dict(pilot_position=i,role=row.role,query_position=int(row.query_position),
                id=int(q.id),origin_source_obs=int(q.origin_source_obs),horizon_days=7,
                majority_season=s,seasonal_fallback=selected[2],search_seconds=seconds,
                **labels.iloc[row.query_position].drop('majority_season').to_dict()))
            if (i+1)%32==0:print('pilot support audit',i+1,'/128',round(time.monotonic()-started,1),'s',flush=True)
        roster_full=pd.DataFrame(saved_roster);save_frame(paths,folder/'roster.parquet',roster_full)
        ec=cfg['energy_ladder'][0];rc=cfg['region_ladder'][0]
        levels=[];all_scores=[];checks=[];bench=[]
        # All models are fixed. Only numerical precision follows registered ladders.
        while True:
            level=[];precision=[];timings=[]
            for i,row in enumerate(roster_full.itertuples(index=False)):
                budget.check(storage=i%32==0)
                fit,query,target,index,packed,labels=contexts[row.role];q=query.iloc[row.query_position]
                truth=target.iloc[row.query_position][['endpoint_lon','endpoint_lat']].to_numpy(float)
                selected=selections[i];t=time.monotonic()
                f,c,key=forecast(packed,selected,role=row.role,q=q,replicate=0,energy_count=ec,region_count=rc,geography=geo)
                scored=score(packed,selected,f,truth,key)
                # Include output serialization in the per-case timing estimate.
                json.dumps(f,allow_nan=False)
                timings.append(dict(majority_season=row.majority_season,seconds=time.monotonic()-t+row.search_seconds))
                f2,c2,key2=forecast(packed,selected,role=row.role,q=q,replicate=1,energy_count=ec,region_count=rc)
                scored2=score(packed,selected,f2,truth,key2)
                for name in model.MODELS:
                    z=dict(pilot_position=i,id=int(q.id),role=row.role,model=name,
                        majority_season=row.majority_season,energy_count=ec,region_count=rc,
                        seasonal_fallback=selected[2],**scored[name])
                    level.append(z)
                    p,w=c2[name]
                    mass=mass_in_frozen(p,w,f[name]['region'])
                    precision.append(dict(pilot_position=i,model=name,id=int(q.id),
                        mass_error=abs(mass-f[name]['region']['attained_mass']),
                        area_change=abs(scored[name]['area90_km2']-scored2[name]['area90_km2']),
                        area=scored[name]['area90_km2'],hit_change=abs(scored[name]['h90']-scored2[name]['h90'])))
                if (i+1)%32==0:print('pilot precision',ec,rc,i+1,'/128',round(budget.stats()['elapsed_seconds'],1),'s',flush=True)
            scores=pd.DataFrame(level);check=pd.DataFrame(precision);timing=pd.DataFrame(timings)
            projection={}
            for candidate,control in [('SeasonalExactPoint','AnnualExactPoint'),('SeasonalEndpointCI','AnnualEndpointCI')]:
                a=scores[scores.model.eq(candidate)].set_index('pilot_position')
                b=scores[scores.model.eq(control)].set_index('pilot_position')
                var=(a.energy_mc_se**2+b.energy_mc_se**2).where(~a.seasonal_fallback,0.)
                maxima=var.groupby(a.majority_season).max().to_dict()
                conservative=sum(variance_weights[s]*float(maxima.get(s,var.max())) for s in range(4))
                reference=float(model.case_weights(b)@b.energy_km)
                projection[candidate]=dict(three_se_km=3*np.sqrt(conservative),threshold_km=.0001*reference)
            region_checks={}
            for name,g in check.groupby('model'):
                w=model.case_weights(g)
                region_checks[name]=dict(max_mass_error=float(g.mass_error.max()),
                    weighted_hit_change=float(w@g.hit_change),
                    weighted_area_change=float(w@g.area_change/max(w@g.area,1e-30)))
            energy_ok=all(z['three_se_km']<=z['threshold_km'] for z in projection.values())
            region_ok=all(z['max_mass_error']<=.005 and z['weighted_hit_change']<=.001 and z['weighted_area_change']<=.005
                          for z in region_checks.values())
            # A tail-cost projection, not a promised runtime; the full-roster inventory is still required.
            tail=float(timing.seconds.quantile(.95))
            estimated=(tail*33971+60)*1.1
            record=dict(energy_count=ec,region_count=rc,energy_passed=bool(energy_ok),region_passed=bool(region_ok),
                energy_projection=projection,region_checks=region_checks,case_seconds_p95=tail,
                case_seconds_max=float(timing.seconds.max()),formal_projected_seconds=estimated,
                formal_projection_2x_seconds=2*estimated)
            levels.append(record)
            save_frame(paths,folder/f'scores_{ec}_{rc}.parquet',scores)
            save_frame(paths,folder/f'precision_{ec}_{rc}.parquet',check)
            save_frame(paths,folder/f'timing_{ec}_{rc}.csv',timing)
            save_json(paths,folder/f'level_{ec}_{rc}.json',record)
            print(json.dumps(record),flush=True)
            if energy_ok and region_ok:break
            next_ec=ec if energy_ok else next((v for v in cfg['energy_ladder'] if v>ec),None)
            next_rc=rc if region_ok else next((v for v in cfg['region_ladder'] if v>rc),None)
            if next_ec is None or next_rc is None:break
            ec,rc=next_ec,next_rc
        stats=budget.check(storage=True)
        resource_ok=2*estimated<=cfg['seconds']['formal'] and stats['peak_rss_bytes']<=4*2**30
        numeric_ok=energy_ok and region_ok
        gate=dict(pilot_passed=bool(numeric_ok and resource_ok),numerical_passed=bool(numeric_ok),
            resource_precheck_passed=bool(resource_ok),formal_authorized=False,
            remaining_gate='Full-roster support/storage/audit projection inventory required' if numeric_ok and resource_ok else 'Stop and report; no formal run',
            energy_count=ec,region_count=rc,levels=levels,queries=128,
            outer_targets_read=False,final_test_access=False)
        save_json(paths,run['provenance']/'pilot_gate.json',gate)
        inputs.verify(approval);completed=True
        print(json.dumps(gate,indent=2),flush=True)
        return gate
    finally:
        budget.finish(paths,'pilot',completed,guard)
