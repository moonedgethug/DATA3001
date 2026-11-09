"""Complete outcome-sealed E8 comparison; no fitting or parameter selection."""
import json
import time
import numpy as np
import pandas as pd

from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_frame,save_json
from data3001.modelling.baselines import position_error_s4_e8 as model
from data3001.modelling.baselines import position_error_s4_e8_inputs as inputs
from data3001.modelling.baselines import position_error_s4_e8_pipeline as pipe
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography


def aggregate(paths,run,cfg,cases):
    metrics=['energy_km','h90','area90_km2','auxiliary','mean_squared_km2','land_mass',
             'outside_D_mass','land_area_km2','wet_area_km2','outside_D_area_km2','mass90']
    ids=cases.groupby(['id','model'])[metrics].mean().reset_index()
    save_frame(paths,run['results']/'per_ID.csv',ids)
    summary=ids.groupby('model',sort=False)[metrics].mean().reset_index()
    for name in model.MODELS:
        g=cases[cases.model.eq(name)];w=pipe.weights(g)
        for p,label in [(.1,'area_p10'),(.5,'area_median'),(.9,'area_p90')]:
            summary.loc[summary.model.eq(name),label]=model.weighted_quantile(g.area90_km2.to_numpy(),w,p)
        summary.loc[summary.model.eq(name),'degenerate_fraction']=float(w@(g['rank'].to_numpy()<2))
        summary.loc[summary.model.eq(name),'coverage_gap']=float(w@g.h90)-.9
    save_frame(paths,run['results']/'summary.csv',summary)
    names=list(model.MODELS);identity=sorted(ids.id.unique());n=len(identity)
    values=np.stack([ids[ids.model.eq(m)].set_index('id').loc[identity,metrics].to_numpy() for m in names],axis=1)
    draws=np.random.Generator(np.random.PCG64(cfg['seed'])).integers(n,size=(cfg['bootstrap_draws'],n))
    boot=values[draws].mean(axis=1)
    np.savez_compressed(run['results']/'bootstrap.npz',values=boot,models=np.array(names),metrics=np.array(metrics),ids=np.array(identity),draws=draws)
    contrasts=[]
    for candidate,control in [('EndpointCI','ExactPoint'),('EndpointCI','MatchedSpread'),('EndpointCI','B2Point'),('ExactPoint','B2Point'),('MatchedSpread','ExactPoint')]:
        a=names.index(candidate);b=names.index(control)
        row=dict(candidate=candidate,control=control)
        for metric in metrics:
            j=metrics.index(metric);sample=boot[:,a,j]-boot[:,b,j]
            row[metric+'_difference']=float(values[:,a,j].mean()-values[:,b,j].mean())
            row[metric+'_lo'],row[metric+'_hi']=map(float,np.quantile(sample,[.025,.975]))
        j=metrics.index('area90_km2');ratio=boot[:,a,j]/boot[:,b,j]
        row['area_ratio']=float(values[:,a,j].mean()/values[:,b,j].mean())
        row['area_ratio_lo'],row['area_ratio_hi']=map(float,np.quantile(ratio,[.025,.975]))
        j=metrics.index('energy_km');row['relative_ES_reduction']=-row['energy_km_difference']/values[:,b,j].mean()
        row['supported_ES_benefit']=row['energy_km_hi']<0
        row['practical_ES_benefit']=row['relative_ES_reduction']>=.001
        row['point_quality_direction']=row['h90_difference']>=0 and row['area_ratio']<=1
        row['interval_quality_guardrails']=row['h90_lo']>=-.01 and row['area_ratio_hi']<=1.02
        row['geographic_guardrails']=row['land_mass_difference']<=.01 and row['outside_D_mass_difference']<=.01
        contrasts.append(row)
    save_frame(paths,run['results']/'contrasts.csv',pd.DataFrame(contrasts))
    loo=[]
    a=names.index('EndpointCI');b=names.index('ExactPoint')
    for i,ident in enumerate(identity):
        v=np.delete(values,i,axis=0).mean(axis=0)
        loo.append(dict(omitted_ID=int(ident),delta_ES=float(v[a,0]-v[b,0]),delta_H90=float(v[a,1]-v[b,1]),area_ratio=float(v[a,2]/v[b,2])))
    save_frame(paths,run['results']/'leave_one_ID_out.csv',pd.DataFrame(loo))
    year_ids=cases.groupby(['year','id','model'])[metrics].mean().reset_index()
    save_frame(paths,run['results']/'year_strata.csv',year_ids.groupby(['year','model'])[metrics].mean().reset_index())
    available_ids=cases.groupby(['availability_stratum','id','model'])[metrics].mean().reset_index()
    save_frame(paths,run['results']/'availability_strata.csv',available_ids.groupby(['availability_stratum','model'])[metrics].mean().reset_index())
    g=cases[cases.model.eq('EndpointCI')];w=pipe.weights(g)
    uncertainty=float(np.sqrt(np.sum((w*g.energy_mc_se.to_numpy())**2)))
    save_json(paths,run['results']/'numerical_summary.json',dict(primary_delta_ES_mc_se_km=uncertainty,
              three_se_km=3*uncertainty,threshold_km=.0001*summary.set_index('model').loc['ExactPoint','energy_km'],
              absolute_point_ES_is_MC_estimate=True,CI_models_SE_measures_paired_difference_to_ExactPoint=True))
    return contrasts


def formal(paths,run,cfg,approval,guard):
    if (run['results']/'formal').exists():raise FileExistsError('Never overwrite an E8 formal attempt')
    gates=sorted(run['provenance'].glob('pilot_attempt_*_gate.json'))
    gate=json.loads(gates[-1].read_text())
    if not gate['passed']:raise PermissionError('Latest pilot gate did not pass')
    parity=json.loads((run['provenance']/'geometry_optimization_parity.json').read_text())
    assert parity['passed']
    start=time.monotonic();complete=False;released=False
    folder=run['results']/'formal';folder.mkdir()
    hashes=pipe.source_snapshot(paths,run,'formal_sources')
    try:
        train,ledger=inputs.load_training(cfg);fit,query,_=inputs.load_role(cfg,'C_outer',train,ledger)
        assert len(query)==33971 and query.id.nunique()==45
        packed=pipe.arrays(fit);index=pipe.index_for(fit,cfg);geo=Geography(paths)
        cells={int(c):g.index.to_numpy() for c,g in fit.groupby('origin_cell_1')}
        examples=json.loads((inputs.ROOT/'results/runs'/cfg['e7_run']/'example_selection.json').read_text())
        save_json(paths,folder/'example_selection.json',examples)
        save_frame(paths,folder/'query_roster.parquet',query)
        support=fit.assign(year=pd.to_datetime(fit.origin_time_UTC,utc=True).dt.year)
        support=support.groupby(['year','location_type','ci_2d_usable'],dropna=False).agg(pairs=('id','size'),IDs=('id','nunique')).reset_index()
        save_frame(paths,folder/'training_error_availability.csv',support)
        forecasts=folder/'forecasts.jsonl';donors=folder/'donors.i32'
        offset=0;diagnostics=[]
        with forecasts.open('x') as out,donors.open('xb') as indices:
            for j,q in enumerate(query.itertuples(index=False)):
                if j%128==0:pipe.check_budget(run,cfg,start,'formal')
                selected,distance=index.query(q.lon,q.lat,cfg['k'])
                if len(selected)==0:raise ValueError('Unexpected unsupported outer query')
                baseline=cells[int(q.origin_cell_1)];key=('C_outer',int(q.id),int(q.origin_source_obs),0)
                is_example=j in examples['query_positions']
                f,clouds=pipe.predict_case(fit,packed,selected,baseline,key,gate['energy_count'],gate['region_count'],geo,retain=is_example)
                d=pipe.diagnostic(fit,selected,distance)
                d.update(query_position=j,id=int(q.id),origin_source_obs=int(q.origin_source_obs),origin_cell_1=int(q.origin_cell_1),donor_offset=offset)
                diagnostics.append(d)
                indices.write(np.asarray(selected,dtype='<i4').tobytes());offset+=len(selected)
                out.write(json.dumps(dict(query_position=j,key=key,forecast=f),allow_nan=False,separators=(',',':'))+'\n')
                if is_example:
                    save_json(paths,folder/f'example_{j}.json',dict(query_position=j,origin=[float(q.lon),float(q.lat)],forecast=f))
                    for name,(points,w) in clouds.items():np.savez_compressed(folder/f'example_{j}_{name}.npz',lonlat=points,weight=w)
                if (j+1)%512==0:print('forecast',j+1,'/33971',round(time.monotonic()-start,1),'s',flush=True)
        frame=pd.DataFrame(diagnostics);save_frame(paths,folder/'donor_diagnostics.parquet',frame)
        # Every distribution and region is sealed before any outer outcome read.
        files=[p for p in folder.iterdir() if p.is_file()]
        save_json(paths,run['provenance']/'forecast_freeze.json',dict(cases=len(query),IDs=query.id.nunique(),
                  energy_count=gate['energy_count'],region_count=gate['region_count'],source_sha256=hashes,
                  output_sha256={str(p.relative_to(inputs.ROOT)):file_sha256(p) for p in files},
                  outer_targets_read=False,outer_endpoint_errors_read=False,final_test_access=False,
                  forecast_seconds=time.monotonic()-start))
        target=inputs.release_outer_targets(run,cfg,approval).sort_values(inputs.KEY).reset_index(drop=True)
        released=True
        pd.testing.assert_frame_equal(query[inputs.KEY],target[inputs.KEY])
        assert not target.outside.any()
        scores=[]
        with forecasts.open() as stream,donors.open('rb') as indices:
            for j,line in enumerate(stream):
                if j%128==0:pipe.check_budget(run,cfg,start,'formal')
                packet=json.loads(line);q=query.iloc[j];d=frame.iloc[j]
                selected=np.frombuffer(indices.read(int(d.donors)*4),dtype='<i4')
                assert pipe.digest_indices(selected)==d.lineage_digest
                baseline=cells[int(q.origin_cell_1)];truth=target.iloc[j][['endpoint_lon','endpoint_lat']].to_numpy(float)
                result=pipe.score_case(packed,selected,baseline,packet['forecast'],truth,tuple(packet['key']))
                a=d.error_available_fraction
                stratum='zero' if a==0 else '(0,.5)' if a<.5 else '[.5,.9)' if a<.9 else '[.9,1)' if a<1 else 'one'
                for name,row in result.items():scores.append(dict(query_position=j,id=int(q.id),origin_source_obs=int(q.origin_source_obs),
                    year=int(pd.Timestamp(q.origin_time_UTC).year),model=name,error_available_fraction=float(a),availability_stratum=stratum,**row))
                if j in examples['query_positions']:
                    save_json(paths,folder/f'example_{j}_observation.json',dict(truth=truth.tolist(),scores=result))
                if (j+1)%2048==0:print('score',j+1,'/33971',round(time.monotonic()-start,1),'s',flush=True)
        cases=pd.DataFrame(scores);assert len(cases)==33971*4
        assert np.isfinite(cases[['energy_km','auxiliary','h90','area90_km2']].to_numpy()).all()
        save_frame(paths,run['results']/'case_scores.parquet',cases)
        aggregate(paths,run,cfg,cases)
        for name,digest in approval['protected_files'].items():assert file_sha256(inputs.ROOT/name)==digest,name
        assert not guard.denied
        pipe.check_budget(run,cfg,start,'formal');complete=True
        print('Formal comparison complete',round(time.monotonic()-start,1),'s',flush=True)
    finally:
        receipt=pipe.resources(run,start)
        receipt.update(completed=complete,outer_targets_read=released,outer_endpoint_errors_read=False,
                       final_test_access=False,denied_access=guard.denied)
        save_json(paths,run['provenance']/'formal_resources.json',receipt)
