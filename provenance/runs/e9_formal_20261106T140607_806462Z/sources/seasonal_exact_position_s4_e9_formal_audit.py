"""Separate reconstruction plus complete independent-seed numerical verification."""
import json
import time
import numpy as np
import pandas as pd
from data3001.modelling.common.runtime import save_json, save_frame
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_formal_io as fio
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_inputs as inputs
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
from data3001.modelling.baselines import position_error_s4_e8 as geometry
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
from data3001.modelling.baselines.position_error_s4_e8_audit import mass_in_frozen, MAP, reference_sd
from data3001.modelling.baselines.seasonal_exact_position_s4_e9_audit import reference_calendar, reference_selection
from data3001.modelling.baselines.seasonal_exact_position_s4_e9_esopt_review import reference_score, cartesian, rng, GEOD
from data3001.modelling.baselines.seasonal_exact_position_s4_e9_formal_analysis import CONTRASTS, METRICS


def frozen_region(region,truth):
    """Replay sealed region by direct matrix algebra, without production scorer."""
    xy=np.array(MAP.transform(float(truth[0]),float(truth[1])))/1000
    r=xy-np.array(region['centre']);inv=np.array(region['inverse']);cov=np.array(region['covariance'])
    hit=bool(r@inv@r<=region['cutoff']+1e-12)
    if region['rank']<2:hit=hit and np.linalg.norm(r-r@cov@inv)<=region['null_tolerance_km']
    area=np.pi*region['cutoff']*np.sqrt(max(0.,np.linalg.det(cov))) if region['rank']==2 else 0.
    return float(hit),float(area)


def independent_statistics(cases,run):
    ids=sorted(cases.id.unique());cube=np.empty((len(ids),4,3))
    for i,id_value in enumerate(ids):
        for j,name in enumerate(fio.MODELS):
            part=cases[(cases.id==id_value)&(cases.model==name)]
            np.testing.assert_allclose(part.weight,1/(len(ids)*len(part)),rtol=0,atol=1e-15)
            cube[i,j]=[sum(part[m])/len(part) for m in METRICS]
    summary=pd.read_csv(run['results']/'summary.csv').set_index('model')
    for j,name in enumerate(fio.MODELS):
        np.testing.assert_allclose(cube[:,j].mean(axis=0),summary.loc[name,METRICS].to_numpy(float),atol=1e-9,rtol=1e-12)
    g=np.random.Generator(np.random.PCG64(20261106));draws=g.integers(len(ids),size=(10000,len(ids)))
    counts=np.array([np.bincount(ix,minlength=len(ids)) for ix in draws])/len(ids)
    bootstrap=np.einsum('bi,imk->bmk',counts,cube)
    contrasts=pd.read_csv(run['results']/'contrasts.csv').set_index(['candidate','reference'])
    largest=0.
    for a,b in CONTRASTS:
        x,y=fio.MODELS.index(a),fio.MODELS.index(b);r=contrasts.loc[(a,b)]
        independent=np.r_[np.quantile(bootstrap[:,x,0]-bootstrap[:,y,0],[.025,.975]),
                           np.quantile(bootstrap[:,x,1]-bootstrap[:,y,1],[.025,.975]),
                           np.quantile(bootstrap[:,x,2]/bootstrap[:,y,2],[.025,.975])]
        expected=r[['es_low','es_high','h90_low','h90_high','area_ratio_low','area_ratio_high']].to_numpy(float)
        np.testing.assert_allclose(independent,expected,rtol=0,atol=1e-9)
        largest=max(largest,float(np.max(abs(independent-expected))))
    return dict(IDs=len(ids),models=4,bootstrap_draws=10000,max_interval_abs_difference=largest)


def audit(paths,run,cfg,approval,guard,budget):
    target=fio.release_targets(paths,run,cfg,approval,guard)
    roster=inputs.read(run['results']/'roster.parquet');cases=inputs.read(run['results']/'case_scores.parquet')
    assert len(cases)==33971*4 and cases.id.nunique()==45 and not cases.duplicated(['query_position','model']).any()
    pd.testing.assert_frame_equal(roster[fio.KEY],target[fio.KEY]);assert not target.outside.any()
    train,ledger=inputs.load(cfg);fit,_,_=inputs.role(cfg,'C_outer',train,ledger)
    fseason,fdeparture,fduration,ftie=reference_calendar(fit.origin_time_UTC)
    qseason,qdeparture,qduration,qtie=reference_calendar(roster.origin_time_UTC)
    frozen_fit=inputs.read(run['results']/'fit_keys_seasons.parquet')
    for expected,actual in [(fseason,frozen_fit.majority_season),(qseason,roster.majority_season),
                            (fdeparture,frozen_fit.departure_season),(qdeparture,roster.departure_season),
                            (ftie,frozen_fit.season_tie),(qtie,roster.season_tie)]:
        np.testing.assert_array_equal(expected,actual)
    for labels,durations in [(frozen_fit,fduration),(roster,qduration)]:
        np.testing.assert_array_equal(durations,labels[['DJF_seconds','MAM_seconds','JJA_seconds','SON_seconds']])
    geo=Geography(paths);cache=opt.cache(fit,geo)
    repaired=reference_sd(cache.points,fit[['repaired_err_lon','repaired_err_lat']].to_numpy(),cache.usable)
    np.testing.assert_allclose(repaired,cache.sd,rtol=2e-14,atol=1e-14)
    lookup=cases.set_index(['query_position','model']);reference_positions=set(fio.AUDIT)
    pre=json.loads((run['provenance']/'preflight.json').read_text());region_count=pre['chosen_region_count']
    secondary=[];mass_rows=[];es_checks=[];neighbour_checks=[];region_max_error=0.;selected_count=0;started=time.monotonic()
    with (run['results']/'forecasts.jsonl').open() as stream:
        for i,(q,selection,line) in enumerate(zip(roster.itertuples(index=False),fio.selections(run),stream)):
            budget.check();record=json.loads(line);a,s,fallback=selection
            assert record['query_position']==i and record['id']==q.id and record['origin_source_obs']==q.origin_source_obs
            assert record['seasonal_fallback']==fallback
            truth=target.iloc[i][['endpoint_lon','endpoint_lat']].to_numpy(float)
            if i in reference_positions:
                _,_,distance=GEOD.inv(np.full(len(fit),q.lon),np.full(len(fit),q.lat),fit.lon.to_numpy(),fit.lat.to_numpy())
                distance[(fit.lon.to_numpy()==q.lon)&(fit.lat.to_numpy()==q.lat)]=0.
                expected={pool:reference_selection(fit,distance,fseason,season) for pool,season in [('Annual',None),('Seasonal',q.majority_season)]}
                assert fallback==(len(expected['Seasonal'])==0)
                if fallback:expected['Seasonal']=expected['Annual']
                for pool,choice in [('Annual',a),('Seasonal',s)]:
                    np.testing.assert_array_equal(expected[pool],choice[0])
                    np.testing.assert_allclose(distance[choice[0]],choice[1],atol=1e-6,rtol=0)
                neighbour_checks.append(dict(query_position=i,annual_donors=len(a[0]),seasonal_donors=len(s[0]),exact_match=True))
            scored={};reintegrated={}
            for pool,choice in [('Annual',a),('Seasonal',s)]:
                ix,distance=choice;selected_count+=len(ix)
                assert np.all(distance>=0) and np.all(distance<=100000.+1e-6)
                assert np.array_equal(np.lexsort((ix,distance)),np.arange(len(ix)))
                if pool=='Seasonal' and not fallback:assert np.all(fseason[ix]==q.majority_season)
                assert abs(np.full(len(ix),1/len(ix)).sum()-1)<=1e-10
                if pool=='Seasonal' and fallback:
                    np.testing.assert_array_equal(a[0],s[0]);assert record['packets'][pool]==record['packets']['Annual']
                    assert record['controls'][pool]==record['controls']['Annual'] and record['keys'][pool]==record['keys']['Annual']
                    scored[pool]=scored['Annual'];reintegrated[pool]=reintegrated['Annual']
                else:
                    p=cache.take(ix);base=fio.key(q,pool);control=record['controls'][pool]
                    f1,c1=opt.regions(p,(*base,1),region_count)
                    scored[pool]=opt.score(p,f1,truth,(*base,1),16384,control)
                    reintegrated[pool]={ci:mass_in_frozen(*c1[ci],record['packets'][pool][str(ci)]['region']) for ci in [False,True]}
                    if i in reference_positions:
                        x=cartesian(p.points);g=rng((*base,'e9_es_control_calibration_v1'))
                        ca,cb=g.integers(len(p.points),size=1024),g.integers(len(p.points),size=1024)
                        d=np.linalg.norm(x[ca]-x[cb],axis=1);c=d*d;var=float(np.var(c,ddof=1))
                        b=float(np.cov(d,c,ddof=1)[0,1]/var) if var else 0.;mu=float(2*np.sum(np.var(x,axis=0)))
                        np.testing.assert_allclose([b,mu],[control['coefficient'],control['mean_squared']],rtol=1e-12,atol=1e-9)
                        same=reference_score(p.points,p.sd,truth,base,16384,control['coefficient'],control['mean_squared'],0)
                        independent=reference_score(p.points,p.sd,truth,base,65536,control['coefficient'],control['mean_squared'],2)
                        for ci,kind in [(False,'ExactPoint'),(True,'EndpointCI')]:
                            original=lookup.loc[(i,pool+kind)];es,se=same[int(ci)];other,ose=independent[int(ci)]
                            np.testing.assert_allclose([es,se],[original.energy_km,original.energy_mc_se],rtol=0,atol=1e-9)
                            denominator=np.hypot(ose,se)
                            es_checks.append(dict(query_position=i,model=pool+kind,same_seed_abs_difference=abs(es-original.energy_km),
                                independent_energy_km=other,independent_se_km=ose,original_energy_km=original.energy_km,
                                independent_difference_km=other-original.energy_km,standardized_difference=(other-original.energy_km)/denominator if denominator else 0.))
                for ci,kind in [(False,'ExactPoint'),(True,'EndpointCI')]:
                    name=pool+kind;primary=lookup.loc[(i,name)];r=record['packets'][pool][str(ci)]['region']
                    hit,area=frozen_region(r,truth)
                    assert hit==primary.h90
                    np.testing.assert_allclose(area,primary.area90_km2,rtol=1e-9,atol=1e-7)
                    region_max_error=max(region_max_error,abs(area-primary.area90_km2))
                    mass_rows.append(dict(query_position=i,model=name,weight=q.weight,integrated_mass=reintegrated[pool][ci],
                        attained_mass=r['attained_mass'],discrepancy=abs(reintegrated[pool][ci]-r['attained_mass'])))
                    secondary.append(dict(query_position=i,id=int(q.id),model=name,weight=q.weight,seasonal_fallback=fallback,**scored[pool][ci]))
            if (i+1)%512==0:
                budget.check(storage=True);fio.progress('independent full audit',i+1,len(roster),started)
    assert i+1==33971 and len(neighbour_checks)==128
    second=pd.DataFrame(secondary);mass=pd.DataFrame(mass_rows)
    save_frame(paths,run['results']/'independent_seed_scores.parquet',second)
    save_frame(paths,run['results']/'region_integration_checks.parquet',mass)
    save_frame(paths,run['results']/'independent_es_65536.csv',pd.DataFrame(es_checks))
    save_frame(paths,run['results']/'independent_neighbours.csv',pd.DataFrame(neighbour_checks))
    stats=independent_statistics(cases,run)
    from data3001.modelling.baselines.seasonal_exact_position_s4_e9_formal_analysis import precision
    ep=precision(cases);save_frame(paths,run['results']/'independent_seed_energy_precision.csv',precision(second))
    primary_means=cases.groupby('model').apply(lambda g:pd.Series({c:float(g.weight@g[c]) for c in METRICS}),include_groups=False)
    secondary_means=second.groupby('model').apply(lambda g:pd.Series({c:float(g.weight@g[c]) for c in METRICS}),include_groups=False)
    numerical=[]
    for name in fio.MODELS:
        m=mass[mass.model==name];p=primary_means.loc[name];s2=secondary_means.loc[name]
        g=cases[cases.model==name].sort_values('query_position');g2=second[second.model==name].sort_values('query_position')
        numerical.append(dict(model=name,es_seed_change_km=float(s2.energy_km-p.energy_km),h90_seed_change=float(s2.h90-p.h90),
            hit_membership_disagreement_weight=float(g.weight.to_numpy()@abs(g2.h90.to_numpy()-g.h90.to_numpy())),
            area_relative_seed_change=float(s2.area90_km2/p.area90_km2-1),max_mass_discrepancy=float(m.discrepancy.max()),
            weighted_mass_discrepancy=float(m.weight@m.discrepancy),mass_pass=bool(m.discrepancy.max()<=.005),
            h90_pass=bool(abs(s2.h90-p.h90)<=.001),area_pass=bool(abs(s2.area90_km2/p.area90_km2-1)<=.005)))
    numerical=pd.DataFrame(numerical);save_frame(paths,run['results']/'numerical_stability.csv',numerical)
    contrasts=pd.read_csv(run['results']/'contrasts.csv');decisions=[]
    global_numeric=bool(numerical[['mass_pass','h90_pass','area_pass']].to_numpy().all() and ep.passed.all())
    degeneracy=pd.read_csv(run['results']/'summary.csv').degenerate_weight.max()<=.01
    for r in contrasts.itertuples(index=False):
        if (r.candidate,r.reference) not in CONTRASTS[:2]:continue
        a,b=secondary_means.loc[r.candidate],secondary_means.loc[r.reference]
        change=float(abs((a.energy_km-b.energy_km)-r.es_difference_km))
        seed_resolved=change<=.1*abs(r.es_difference_km)
        hit_second=float(a.h90-b.h90);area_second=float(a.area90_km2-b.area90_km2)
        direction_resolved=bool((r.h90_difference==0 and hit_second==0 or r.h90_difference>abs(hit_second-r.h90_difference)) and
                               (r.area_difference_km2==0 and area_second==0 or -r.area_difference_km2>abs(area_second-r.area_difference_km2)))
        accepted=bool(r.statistical_quality_criteria and global_numeric and seed_resolved and direction_resolved and degeneracy)
        status='QUALITY_PRESERVING_IMPROVEMENT' if accepted else ('NUMERICALLY_INCONCLUSIVE' if not global_numeric or not seed_resolved else 'DOES_NOT_MEET_REGISTERED_CRITERIA')
        decisions.append(dict(candidate=r.candidate,reference=r.reference,status=status,accepted=accepted,
            es_independent_seed_change_km=change,es_effect_seed_resolved=seed_resolved,quality_direction_resolved=direction_resolved,
            region_degeneracy_under_one_percent=bool(degeneracy),statistical_quality_criteria=bool(r.statistical_quality_criteria)))
    save_json(paths,run['provenance']/'decision.json',dict(decisions=decisions,global_numerical_gates_passed=global_numeric,
        no_model_replacement=True,no_further_tuning=True,interpretation_scope='Repeatedly inspected development data, not an independent final test'))
    fio.verify({**approval['protected_files'],**approval['new_source_sha256']})
    assert not guard.denied
    save_json(paths,run['provenance']/'independent_audit.json',dict(structural_checks_passed=True,selected_donor_occurrences=selected_count,
        all_donor_seasons_radius_votes_checked=True,outer_full_distance_queries=128,pilot_full_distance_queries=128,
        pilot_audit_reference=f'provenance/runs/{fio.PILOT}/independent_review.json',region_replays=33971*4,
        max_region_area_replay_difference_km2=region_max_error,independent_energy_records=len(es_checks),
        max_same_seed_energy_difference_km=max(r['same_seed_abs_difference'] for r in es_checks),
        max_independent_seed_standardized_difference=max(abs(r['standardized_difference']) for r in es_checks),
        independent_statistics=stats,full_second_seed_queries=33971,numerical_gates_passed=global_numeric,
        protected_files_unchanged=True,final_test_access=False,outer_endpoint_errors_read=False))
