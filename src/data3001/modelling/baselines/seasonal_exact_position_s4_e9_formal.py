"""Full E9 execution, with immutable forecast freeze before outer scoring."""
import io
import json
import time
import traceback
import unittest
import resource
import sys
import numpy as np
import pandas as pd
from data3001.modelling.common.runtime import save_json, save_frame
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_formal_io as fio
from data3001.modelling.baselines import seasonal_exact_position_s4_e9 as model
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_inputs as inputs
from data3001.modelling.baselines import position_error_s4_e8 as geometry
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
from data3001.modelling.baselines.position_error_s4_e8_audit import mass_in_frozen
from data3001.modelling.baselines.seasonal_exact_position_s4_e9_pipeline import diagnostic, digest


def tests(paths,run,cfg,approval,guard,budget):
    log=io.StringIO();suite=unittest.TestSuite()
    for pattern in ['test_modelling_position_error_s4_e8.py','test_modelling_seasonal_exact_position_s4_e9.py',
                    'test_modelling_seasonal_exact_position_s4_e9_esopt.py','test_modelling_seasonal_exact_position_s4_e9_formal.py']:
        suite.addTests(unittest.defaultTestLoader.discover(str(fio.ROOT/'tests'),pattern=pattern))
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    paths.publish(run['provenance']/'semantic_tests.txt',lambda f:f.write(log.getvalue().encode()))
    assert result.wasSuccessful(),log.getvalue()
    save_json(paths,run['provenance']/'semantic_tests.json',dict(passed=True,tests=result.testsRun))
    print('Semantic tests passed:',result.testsRun,flush=True)


def inventory(paths,run,cfg,approval,guard,budget):
    assert json.loads((run['provenance']/'semantic_tests.json').read_text())['passed']
    train,ledger=inputs.load(cfg);fit,query,_=inputs.role(cfg,'C_outer',train,ledger)
    query=query.sort_values(fio.KEY).reset_index(drop=True)
    qlabels=model.season_labels(query.origin_time_UTC);flabels=model.season_labels(fit.origin_time_UTC)
    roster=pd.concat([query,qlabels],axis=1);roster['query_position']=np.arange(len(query));roster['weight']=model.case_weights(query)
    save_frame(paths,run['results']/'roster.parquet',roster)
    save_frame(paths,run['results']/'fit_keys_seasons.parquet',pd.concat([fit[fio.KEY+['origin_time_UTC']],flabels],axis=1))
    save_frame(paths,run['results']/'audit_roster.parquet',roster.iloc[fio.AUDIT])
    save_frame(paths,run['results']/'example_roster.parquet',roster.iloc[fio.EXAMPLES])
    e7=fio.ROOT/'results/runs'/cfg['e7_run']
    assert json.loads((e7/'example_selection.json').read_text())['query_positions']==fio.EXAMPLES
    historical=inputs.read(e7/'outer_roster.parquet',columns=fio.KEY+['n','lineage_digest']).sort_values(fio.KEY).reset_index(drop=True)
    pd.testing.assert_frame_equal(query[fio.KEY],historical[fio.KEY])
    for j in fio.EXAMPLES:
        old=inputs.read(e7/f'examples/donors_{j}.parquet')
        assert len(old)>0
    index=model.SeasonalNeighbours(fit);rows=[];offsets=[];timings=[];minimum=0
    started=time.monotonic()
    with (run['results']/'donor_lineage.zst').open('xb') as stream:
        for i,q in enumerate(roster.itertuples(index=False)):
            budget.check();t=time.monotonic();a,s,fallback=index.query(q.lon,q.lat,q.majority_season)
            assert len(a[0])==historical.iloc[i]['n'] and digest(a[0])==historical.iloc[i].lineage_digest
            blob=fio.encode_selection(a,s,fallback);decoded=fio.decode_selection(blob)
            assert decoded[2]==fallback
            for before,after in zip([a,s],decoded[:2]):
                np.testing.assert_array_equal(before[0],after[0])
                assert before[1].astype('<f8').tobytes()==after[1].tobytes()
            offsets.append(dict(query_position=i,offset=stream.tell(),length=len(blob)))
            stream.write(blob)
            for pool,selection in [('Annual',a),('Seasonal',s)]:
                r=diagnostic(fit,*selection)
                minimum=max(minimum,2*(r['donors']-r['error_fallback_pairs'])+r['error_fallback_pairs'])
                rows.append(dict(query_position=i,pool=pool,seasonal_fallback=fallback,**r))
            timings.append(time.monotonic()-t)
            if (i+1)%512==0:
                stream.flush();budget.check(storage=True);fio.progress('full support inventory',i+1,len(roster),started)
    save_frame(paths,run['results']/'lineage_offsets.parquet',pd.DataFrame(offsets))
    support=pd.DataFrame(rows);save_frame(paths,run['results']/'support.parquet',support)
    save_frame(paths,run['results']/'inventory_timings.csv',pd.DataFrame(dict(seconds=timings)))
    counts=[]
    for role,frame,labels in [('training',fit,flabels),('query',query,qlabels)]:
        for season in range(4):
            mask=labels.majority_season.eq(season)
            counts.append(dict(role=role,season=model.SEASONS[season],pairs=int(mask.sum()),IDs=int(frame.loc[mask,'id'].nunique()),
                cross_season=int(labels.loc[mask,'cross_season'].sum()),ties=int(labels.loc[mask,'season_tie'].sum()),
                evaluation_weight=float(roster.loc[mask,'weight'].sum()) if role=='query' else 0.))
    save_frame(paths,run['results']/'season_support.csv',pd.DataFrame(counts))
    region_count=next((n for n in cfg['region_ladder'] if n>=minimum),None)
    if region_count is None: raise ValueError('Registered quadrature cannot represent every donor')
    retained=budget.size();projected=retained+len(roster)*8500+150*2**20
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    preliminary=dict(cases=len(roster),IDs=query.id.nunique(),training_pairs=len(fit),training_IDs=fit.id.nunique(),
        required_region_points=minimum,region_count=region_count,retained_bytes=retained,
        projected_storage_bytes=projected,projected_peak_rss_bytes=peak+512*2**20,
        annual_lineage_matches_E7=True,lossless_roundtrips=len(roster),outer_targets_read=False)
    save_json(paths,run['provenance']/'support_inventory.json',preliminary)
    assert projected<=2.5*2**30,'Projected storage exceeds the approved precheck'
    assert peak+512*2**20<=4*2**30,'Projected memory exceeds the approved precheck'
    # Outcome-blind outer geometry checks. Query positions are timing placeholders, not outcomes.
    geo=Geography(paths);cache=opt.cache(fit,geo);selected={}
    for i,item in enumerate(fio.selections(run)):
        if i in set(fio.AUDIT):selected[i]=item
    audit_timings=[];mass_checks=[];levels=[]
    while True:
        level_checks=[]
        for i in fio.AUDIT:
            budget.check();q=roster.iloc[i];a,s,fallback=selected[i];audit_seconds=0.
            for pool,choice in [('Annual',a),('Seasonal',s)]:
                if pool=='Seasonal' and fallback:continue
                p=cache.take(choice[0]);f,c=opt.regions(p,fio.key(q,pool,0),region_count)
                cal=opt.calibration(p,fio.key(q,pool))
                timer=time.monotonic()
                f1,c1=opt.regions(p,fio.key(q,pool,1),region_count)
                # Only timing is retained. No synthetic scores enter scientific results.
                opt.score(p,f1,[q.lon,q.lat],fio.key(q,pool,1),16384,cal)
                for ci in [False,True]:
                    integrated=mass_in_frozen(*c1[ci],f[ci]['region'])
                    area=f[ci]['region']['area_km2'];area1=f1[ci]['region']['area_km2']
                    level_checks.append(dict(query_position=int(i),pool=pool,ci=ci,region_count=region_count,
                        mass_discrepancy=abs(integrated-f[ci]['region']['attained_mass']),
                        relative_area_difference=abs(area1-area)/area if area else 0.))
                audit_seconds+=time.monotonic()-timer
            audit_timings.append(audit_seconds)
        maximum=max(r['mass_discrepancy'] for r in level_checks)
        levels.append(dict(region_count=region_count,max_mass_discrepancy=maximum))
        mass_checks.extend(level_checks)
        if maximum<=.005:break
        next_level=[n for n in cfg['region_ladder'] if n>region_count]
        if not next_level:raise ValueError('Outcome-blind region precision unresolved at registered maximum')
        region_count=next_level[0]
    # Includes new region integration, second ES stream and independent mass check.
    audit_projection=float(np.percentile(audit_timings,95))*len(roster)*1.10+120
    save_frame(paths,run['results']/'outer_geometry_checks.csv',pd.DataFrame(mass_checks))
    save_json(paths,run['provenance']/'preflight.json',dict(**preliminary,chosen_region_count=region_count,
        energy_count=16384,region_precision_levels=levels,audit_projected_seconds=audit_projection,
        actual_inventory_seconds=time.monotonic()-started,time_margin_waived=True,outer_targets_read=guard.outcomes_read,
        storage_precheck_passed=True,memory_precheck_passed=True))
    assert audit_projection+cfg['prior_audit_seconds']<=1800,'Audit projection exceeds its actual budget'
    assert not guard.outcomes_read and not guard.denied
    print('Full preflight passed',region_count,'region points; audit estimate',audit_projection,flush=True)


def forecast(paths,run,cfg,approval,guard,budget):
    pre=json.loads((run['provenance']/'preflight.json').read_text())
    assert pre['audit_projected_seconds']+cfg['prior_audit_seconds']<=1800
    train,ledger=inputs.load(cfg);fit,query,_=inputs.role(cfg,'C_outer',train,ledger)
    roster=inputs.read(run['results']/'roster.parquet');geo=Geography(paths);cache=opt.cache(fit,geo)
    timings=[];started=time.monotonic();examples=set(fio.EXAMPLES)
    with (run['results']/'forecasts.jsonl').open('x') as stream:
        for i,(q,selection) in enumerate(zip(roster.itertuples(index=False),fio.selections(run))):
            budget.check();timer=time.monotonic();a,s,fallback=selection;packets={};controls={};profile={};clouds={}
            for pool,choice in [('Annual',a),('Seasonal',s)]:
                if pool=='Seasonal' and fallback:
                    controls[pool]=controls['Annual'];packets[pool]=packets['Annual'];clouds[pool]=clouds['Annual'];continue
                p=cache.take(choice[0]);f,c=opt.regions(p,fio.key(q,pool,0),pre['chosen_region_count'],geo,profile)
                packets[pool]={str(ci):v for ci,v in f.items()};clouds[pool]=c
                controls[pool]=opt.calibration(p,fio.key(q,pool))
            record=dict(query_position=i,id=int(q.id),origin_source_obs=int(q.origin_source_obs),
                seasonal_fallback=fallback,packets=packets,controls=controls,
                keys={pool:fio.key(q,'Annual' if pool=='Seasonal' and fallback else pool,0) for pool in ['Annual','Seasonal']})
            stream.write(json.dumps(record,separators=(',',':'),allow_nan=False)+'\n')
            if i in examples:
                saved=dict(query_position=i,origin=[q.lon,q.lat],majority_season=int(q.majority_season),forecast={})
                for pool in ['Annual','Seasonal']:
                    for ci,kind in [(False,'ExactPoint'),(True,'EndpointCI')]:
                        name=pool+kind;saved['forecast'][name]=packets[pool][str(ci)]
                        p,w=clouds[pool][ci]
                        paths.publish(run['results']/f'examples/example_{i}_{name}.npz',lambda f,p=p,w=w:np.savez_compressed(f,lonlat=p,weight=w))
                save_json(paths,run['results']/f'examples/example_{i}.json',saved)
            timings.append(dict(query_position=i,total_seconds=time.monotonic()-timer,**profile))
            if (i+1)%256==0:
                stream.flush();budget.check(storage=True);fio.progress('freezing forecasts',i+1,len(roster),started)
    assert i+1==33971
    save_frame(paths,run['results']/'forecast_timings.csv',pd.DataFrame(timings))
    files=[p for p in run['results'].rglob('*') if p.is_file()]
    save_json(paths,run['provenance']/'forecast_freeze.json',dict(cases=33971,models=fio.MODELS,
        energy_count=16384,region_count=pre['chosen_region_count'],outer_targets_read=guard.outcomes_read,
        output_sha256=fio.hashes(files),source_sha256=approval['new_source_sha256'],
        controls_calibrated_without_outcomes=True,all_predictions_frozen=True))
    assert not guard.outcomes_read and not guard.denied


def score(paths,run,cfg,approval,guard,budget):
    target=fio.release_targets(paths,run,cfg,approval,guard)
    roster=inputs.read(run['results']/'roster.parquet')
    pd.testing.assert_frame_equal(roster[fio.KEY],target[fio.KEY]);assert not target.outside.any()
    train,ledger=inputs.load(cfg);fit,_,_=inputs.role(cfg,'C_outer',train,ledger)
    geo=Geography(paths);cache=opt.cache(fit,geo);rows=[];timings=[];started=time.monotonic()
    support=inputs.read(run['results']/'support.parquet').set_index(['query_position','pool'])
    with (run['results']/'forecasts.jsonl').open() as stream:
        for i,(q,selection,line) in enumerate(zip(roster.itertuples(index=False),fio.selections(run),stream)):
            budget.check();timer=time.monotonic();record=json.loads(line);assert record['query_position']==i
            a,s,fallback=selection;truth=target.iloc[i][['endpoint_lon','endpoint_lat']].to_numpy(float);scored={};profile={}
            for pool,choice in [('Annual',a),('Seasonal',s)]:
                if pool=='Seasonal' and fallback:scored[pool]=scored['Annual'];continue
                p=cache.take(choice[0]);packets={ci:record['packets'][pool][str(ci)] for ci in [False,True]}
                scored[pool]=opt.score(p,packets,truth,tuple(record['keys'][pool]),cfg['energy_count'],record['controls'][pool],profile=profile)
            for pool in ['Annual','Seasonal']:
                diagnostic_row=support.loc[(i,pool)]
                for ci,kind in [(False,'ExactPoint'),(True,'EndpointCI')]:
                    rows.append(dict(query_position=i,id=int(q.id),origin_source_obs=int(q.origin_source_obs),horizon_days=7,
                        model=pool+kind,weight=q.weight,majority_season=q.majority_season,cross_season=q.cross_season,
                        year=q.origin_time_UTC.year,seasonal_fallback=fallback,donors=int(diagnostic_row.donors),
                        donor_IDs=int(diagnostic_row.donor_IDs),error_fallback_mass=diagnostic_row.error_fallback_mass,
                        **scored[pool][ci]))
            if i in fio.EXAMPLES:
                save_json(paths,run['results']/f'examples/example_{i}_observation.json',dict(truth=truth.tolist(),scores={pool+kind:scored[pool][ci] for pool in ['Annual','Seasonal'] for ci,kind in [(False,'ExactPoint'),(True,'EndpointCI')]}))
            timings.append(dict(query_position=i,total_seconds=time.monotonic()-timer,**profile))
            if (i+1)%512==0:
                budget.check(storage=True);fio.progress('scoring all four models',i+1,len(roster),started)
    assert i+1==33971 and len(rows)==33971*4
    scores=pd.DataFrame(rows);save_frame(paths,run['results']/'case_scores.parquet',scores)
    save_frame(paths,run['results']/'score_timings.csv',pd.DataFrame(timings))
    from data3001.modelling.baselines.seasonal_exact_position_s4_e9_formal_analysis import analyze
    analyze(paths,run,scores)


def main():
    if sys.argv[1]=='prepare':fio.prepare();return
    stage,name=sys.argv[1:3]
    phase='pilot' if stage=='tests' else ('audit' if stage in ['audit','report'] else 'formal')
    args=fio.context(name,phase);paths,run,cfg,approval,guard,budget=args
    completed=False
    try:
        if stage=='audit':
            from data3001.modelling.baselines.seasonal_exact_position_s4_e9_formal_audit import audit
            audit(*args)
        elif stage=='report':
            from data3001.modelling.baselines.seasonal_exact_position_s4_e9_formal_report import report
            report(*args)
        else:globals()[stage](*args)
        budget.check(storage=True);completed=True
    except BaseException as error:
        save_json(paths,run['provenance']/f'{stage}_failure.json',dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc(),no_automatic_retry=True))
        raise
    finally:budget.finish(stage,completed)


if __name__=='__main__':main()
