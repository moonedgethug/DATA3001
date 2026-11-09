"""Isolated exact-origin fitting, forecast freeze and matched-grid scoring."""
import hashlib
import json
import time
import numpy as np
import pandas as pd
from scipy import sparse

from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_frame, save_json
from data3001.modelling.baselines.seasonal_information_s4_e3_pipeline import load_roles
from data3001.modelling.baselines.seasonal_conditioning_s4_e1_inputs import KEY, validation_weights
from data3001.modelling.baselines.run_seasonal_conditioning_s4_e1 import array_file
from data3001.modelling.baselines import exact_origin_s4_e7_inputs as inputs
from data3001.modelling.baselines.exact_origin_s4_e7 import NeighbourIndex, sparse_forecast, probability_summary

METRICS = ['brier', 'h90', 'k90', 'area90', 'mass', 'zero', 'exit', 'geographic_mass', 'exit_in_region']
RESOLUTIONS = (1., .5)
DEST = {1.: 'destination_cell_1', .5: 'destination_cell_05'}


def grids(paths):
    frame = pd.read_parquet(paths.asset('state_index', verify=True))
    result = {}
    for resolution in RESOLUTIONS:
        grid = frame[frame.resolution.eq(resolution)].sort_values('cell').reset_index(drop=True)
        states = np.sort(np.r_[-2, grid.cell.to_numpy(dtype='int64')])
        area = grid.set_index('cell').wet_area_km2.to_dict()
        area[-2] = 0.
        result[resolution] = (grid, states, area)
    return result


def build_roles(paths, run, cfg, guard):
    start = time.monotonic()
    bundle, outer, inner, ref = load_roles(paths, cfg)
    old, reference_inventory = inputs.verify_reference(paths, cfg)
    inventory = dict(bundle['inventory']); inventory.update(reference_inventory)
    train, queries = inputs.prepare_positions(paths, guard, outer, inventory)
    roles = []
    columns = KEY + ['origin_cell_1', 'origin_time_UTC', 'lon', 'lat']
    for role in inner:
        fitkeys = role['train'].query('horizon_days == 7')[KEY]
        qkeys = role['validation'].query('horizon_days == 7')[KEY]
        fitting = fitkeys.merge(train, on=KEY, validate='one_to_one').sort_values(KEY).reset_index(drop=True)
        labelled = qkeys.merge(train, on=KEY, validate='one_to_one').sort_values(KEY).reset_index(drop=True)
        assert len(fitting) == len(fitkeys) and len(labelled) == len(qkeys)
        roles.append(dict(name=role['name'], train=fitting, queries=labelled[columns].copy(), targets=labelled))
    roles.append(dict(name='C_outer', train=train, queries=queries[columns].copy(), targets=None))
    assert [(len(r['train']),len(r['queries'])) for r in roles] == [(170978,41761),(209934,44612),(265393,33971)]
    save_frame(paths, run['results'] / 'roles.parquet', pd.concat([r['ledger'] for r in [outer,*inner]], ignore_index=True))
    save_frame(paths, run['results'] / 'training_coordinates.parquet', train)
    save_frame(paths, run['results'] / 'query_coordinates.parquet', queries[columns])
    return roles, outer, grids(paths), inventory, old, time.monotonic()-start


def baseline(train, geography):
    forecasts = {}
    for cell, group in train.groupby('origin_cell_1', sort=True):
        for resolution, (_, states, area) in geography.items():
            codes, probabilities = sparse_forecast(group[DEST[resolution]].to_numpy(), np.arange(len(group)))
            assert np.isin(codes, states).all()
            summary = probability_summary(codes, probabilities, -2, area)
            forecasts[int(cell), resolution] = (codes, probabilities, summary['mask'])
    return forecasts


def index_for(train, cfg):
    return NeighbourIndex(train.lon.to_numpy(), train.lat.to_numpy(), cfg['radius_m'], cfg['distance_tolerance_m'])


def support_mask(role, index):
    query = role['queries']
    supported = query.origin_cell_1.isin(role['train'].origin_cell_1).to_numpy()
    exact = index.support(query.lon.to_numpy(), query.lat.to_numpy())
    if np.any(supported & ~exact):
        raise ValueError(f"{role['name']}: {int((supported & ~exact).sum())} baseline-supported starts lack a donor within the approved cap")
    return supported, exact


def diagnostic(train_ids, selected, distances, k):
    ids, counts = np.unique(train_ids[selected], return_counts=True)
    return dict(n=len(selected), donor_ids=len(ids), largest_id_share=float(counts.max()/len(selected)),
                farthest_m=float(distances[len(selected)-1]), cap_limited=bool(len(selected)<k), tie_extra=max(0,len(selected)-k),
                lineage_digest=hashlib.sha256(np.asarray(selected,dtype='<i8').tobytes()).hexdigest())


def deterministic_pilot_keys(query, maximum, index):
    from pyproj import Transformer
    transform=Transformer.from_crs('EPSG:4979','EPSG:4978',always_xy=True)
    xyz=np.column_stack(transform.transform(query.lon.to_numpy(),query.lat.to_numpy(),np.zeros(len(query))))
    density=index.tree.query_ball_point(xyz,index.radius_m+1e-6,return_length=True,workers=1)
    chosen = set()
    for _, positions in query.groupby('origin_cell_1', sort=True).indices.items():
        chosen.update(int(positions[i]) for i in {0,len(positions)//2,len(positions)-1})
        chosen.add(int(positions[np.argmin(density[positions])]))
        chosen.add(int(positions[np.argmax(density[positions])]))
    chosen.update(np.linspace(0,len(query)-1,max(1,maximum-len(chosen)),dtype=int).tolist())
    return np.array(sorted(chosen)[:maximum], dtype=int)


def exact_search_audit(role, index, cfg):
    """One predeclared query per original origin in every role, all fitting donors."""
    checks = 0
    for _, group in role['queries'].groupby('origin_cell_1',sort=True):
        row = group.iloc[0]
        found, d = index.query(row.lon,row.lat,max(cfg['ks']))
        reference, rd = index.exhaustive(row.lon,row.lat,max(cfg['ks']))
        assert np.array_equal(found,reference), (role['name'],row.origin_cell_1)
        assert np.allclose(d,rd,atol=1e-6,rtol=0)
        for k in cfg['ks']:
            assert np.array_equal(index.select(found,d,k),index.select(reference,rd,k))
        checks += 1
    return checks


def pilot(paths,run,cfg,guard):
    roles, outer, geography, inventory, old, io_seconds = build_roles(paths,run,cfg,guard)
    measurements = []; total_prediction = 0.; audit_time = 0.; forecast_bytes = 0.
    for role in roles:
        started = time.monotonic(); idx = index_for(role['train'],cfg)
        supported, exact = support_mask(role,idx)
        index_seconds = time.monotonic()-started
        started = time.monotonic(); checks = exact_search_audit(role,idx,cfg)
        checked_seconds = time.monotonic()-started; audit_time += checked_seconds
        positions = deterministic_pilot_keys(role['queries'],min(1365,len(role['queries'])),idx)
        costs = []; train = role['train']; ids = train.id.to_numpy()
        baselines = baseline(train, geography)
        donor_codes = {res:train[DEST[res]].to_numpy() for res in RESOLUTIONS}
        for n,position in enumerate(positions):
            q = role['queries'].iloc[position]
            if not supported[position]:continue
            started = time.monotonic(); neighbours,distance = idx.query(q.lon,q.lat,max(cfg['ks']))
            candidate_count = idx.last_stats['candidate_count']
            largest_nnz = 0
            for k in cfg['ks']:
                selected = idx.select(neighbours,distance,k)
                diagnostic(ids,selected,distance,k)
                for resolution in RESOLUTIONS:
                    codes,p = sparse_forecast(donor_codes[resolution],selected)
                    probability_summary(codes,p,-2,geography[resolution][2])
                    if k==max(cfg['ks']):largest_nnz += int((p>0).sum())
            annual_nnz = sum(int((baselines[int(q.origin_cell_1),res][1]>0).sum()) for res in RESOLUTIONS)
            costs.append((int(q.origin_cell_1),time.monotonic()-started,candidate_count,largest_nnz+annual_nnz))
            if n and n%256==0:print('Pilot',role['name'],n,'/',len(positions),flush=True)
        sampled = pd.DataFrame(costs,columns=['origin_cell_1','seconds','candidate_count','forecast_nnz'])
        rates = sampled.groupby('origin_cell_1').seconds.agg(['mean','max'])
        workloads = role['queries'][supported].groupby('origin_cell_1').size()
        # Use per-origin 90th percentile or mean, whichever is larger.
        conservative = sampled.groupby('origin_cell_1').seconds.quantile(.9).combine(rates['mean'],max)
        estimate = float(workloads@conservative.reindex(workloads.index))
        total_prediction += estimate
        if role['name']=='C_outer':
            per_origin=sampled.groupby('origin_cell_1').forecast_nnz.max()
            forecast_bytes=float(workloads@per_origin.reindex(workloads.index))*17+len(role['queries'])*64
        measurements.append(dict(role=role['name'],queries=len(role['queries']),pilot_queries=len(costs),
             supported=int(supported.sum()),exact_supported=int(exact.sum()),new_unsupported=0,
             exhaustive_checks=checks,index_support_seconds=index_seconds,exhaustive_seconds=checked_seconds,
             projected_prediction_seconds=estimate,max_candidate_count=int(sampled.candidate_count.max())))
        save_frame(paths,run['results']/(role['name']+'_pilot_timing.csv'),sampled)
    save_json(paths,run['provenance']/'input_inventory.json',inventory)
    save_frame(paths,run['results']/'pilot_roles.csv',pd.DataFrame(measurements))
    # Full prediction projection includes all 3 candidates on both grids even though
    # the formal outer role uses only one k. Reserve independent scoring/report time.
    projected = io_seconds + total_prediction + audit_time + sum(x['index_support_seconds'] for x in measurements) + 120.
    save_json(paths,run['results']/'pilot_projection.json',{'io_seconds':io_seconds,'predicted_seconds_per_phase':projected,
              'prediction_seconds':total_prediction,'audit_seconds':audit_time,'fixed_scoring_report_allowance_seconds':120.,
              'outer_skill_inspected':False,'k_selected':False,'sampled_queries':sum(x['pilot_queries'] for x in measurements)})
    input_bytes=sum(f.stat().st_size for f in run['results'].rglob('*') if f.is_file())
    per_phase_bytes=input_bytes+forecast_bytes+120_000_000
    projected_total_bytes=input_bytes+2*per_phase_bytes
    save_json(paths,run['results']/'storage_projection.json',{'forecast_uncompressed_bytes':forecast_bytes,
              'input_bytes':input_bytes,'projected_all_run_bytes':projected_total_bytes,
              'additional_working_bytes':2*forecast_bytes})
    return dict(projected_seconds=projected,projected_artifact_bytes=projected_total_bytes,
                projected_working_bytes=2*forecast_bytes,all_roles_checked=True,outer_skill_inspected=False,k_selected=False)


def inner_candidates(paths,run,cfg,roles,geography):
    parts = []
    for role in roles[:-1]:
        train,query,target = role['train'],role['queries'],role['targets']
        idx = index_for(train,cfg); supported,_ = support_mask(role,idx)
        eligible=validation_weights(query.copy());eligible['supported']=supported
        save_frame(paths,run['results']/(role['name']+'_eligibility.parquet'),eligible)
        save_json(paths,run['results']/(role['name']+'_support.json'),{'eligible_pairs':len(query),
                  'unsupported_pairs':int((~supported).sum()),'unsupported_weight':float(eligible.loc[~supported,'weight'].sum())})
        baselines = baseline(train,geography)
        ids = train.id.to_numpy(); dest = train.destination_cell_1.to_numpy()
        records = []; clock = time.monotonic()
        for i,q in enumerate(query.itertuples(index=False)):
            if not supported[i]:continue
            found,d = idx.query(q.lon,q.lat,max(cfg['ks']))
            truth = int(target.iloc[i].destination_cell_1)
            codes,ap,_ = baselines[int(q.origin_cell_1),1.]
            annual = probability_summary(codes,ap,truth,geography[1.][2])
            for k in cfg['ks']:
                selected = idx.select(found,d,k)
                codes,p = sparse_forecast(dest,selected)
                stats = probability_summary(codes,p,truth,geography[1.][2])
                row = {name:getattr(q,name) for name in KEY+['origin_cell_1']}
                row.update(role=role['name'],k=k,Annual_brier=annual['brier'],**diagnostic(ids,selected,d,k))
                row.update({name:stats[name] for name in METRICS})
                records.append(row)
            if time.monotonic()-clock>=20:
                print('Inner',role['name'],i+1,'/',len(query),flush=True);clock=time.monotonic()
        parts.append(pd.DataFrame(records))
    cases = pd.concat(parts,ignore_index=True)
    unique = cases[KEY+['origin_cell_1']].drop_duplicates().reset_index(drop=True)
    assert not unique.duplicated(KEY).any()
    weights = validation_weights(unique)[KEY+['weight']]
    cases = cases.merge(weights,on=KEY,validate='many_to_one',sort=False)
    curves = []
    for label,part in [('pooled',cases),*list(cases.groupby('role'))]:
        for k,g in part.groupby('k'):
            w = g.weight.to_numpy()/g.weight.sum()
            curves.append(dict(fold=label,k=int(k),**{m:float(w@g[m]) for m in METRICS},Annual_brier=float(w@g.Annual_brier)))
    curves = pd.DataFrame(curves)
    pooled = curves[curves.fold.eq('pooled')]
    best = pooled.brier.min()
    chosen = int(pooled.loc[pooled.brier.le(best+1e-12),'k'].max())
    choices = pd.DataFrame([dict(horizon_days=7,k=chosen,radius_m=cfg['radius_m'],inner_brier=float(pooled.set_index('k').loc[chosen,'brier']))])
    save_frame(paths,run['results']/'choices.csv',choices)
    save_frame(paths,run['results']/'inner_curves.csv',curves)
    save_frame(paths,run['results']/'inner_cases.parquet',cases)
    return chosen,choices,curves


class ForecastStore:
    def __init__(self,states):
        self.states=states; self.pointer=[0]; self.index=[]; self.data=[]; self.region=[]

    def append(self,states,p,mask):
        use=p>0; states,p,mask=states[use],p[use],mask[use]
        index=np.searchsorted(self.states,states)
        assert np.array_equal(self.states[index],states)
        self.index.append(index.astype('int32'));self.data.append(p);self.region.append(mask)
        self.pointer.append(self.pointer[-1]+len(p))

    def save(self,paths,prefix):
        args=(np.concatenate(self.index),np.array(self.pointer,dtype='int64'))
        shape=(len(self.pointer)-1,len(self.states))
        matrix=sparse.csr_matrix((np.concatenate(self.data),*args),shape=shape)
        masks=sparse.csr_matrix((np.concatenate(self.region),*args),shape=shape,dtype=bool)
        for suffix,value in [('probabilities',matrix),('regions',masks)]:
            paths.publish(prefix.with_name(prefix.name+'_'+suffix+'.npz'),lambda f,v=value:sparse.save_npz(f,v))
        array_file(paths,prefix.with_name(prefix.name+'_states.npy'),self.states)
        return matrix,masks


def example_positions(train,query):
    supports=train.groupby('origin_cell_1').id.nunique().sort_index()
    chosen=[]
    for quantile in [.25,.5,.75]:
        target=float(supports.quantile(quantile))
        candidates=sorted(supports.index,key=lambda i:(abs(supports[i]-target),i))
        cell=next((i for i in candidates if i in set(query.origin_cell_1) and i not in chosen),None)
        if cell is not None:chosen.append(cell)
    positions=[]
    for cell in chosen:
        g=query[query.origin_cell_1.eq(cell)]
        for quantile in [.25,.75]:
            centre=g.lon.quantile(quantile)
            selected=g.assign(distance=(g.lon-centre).abs()).sort_values(['distance','id','origin_source_obs']).index[0]
            if selected not in positions:positions.append(int(selected))
    return positions


def outer_forecasts(paths,run,cfg,role,geography,chosen,old):
    train,query=role['train'],role['queries']
    idx=index_for(train,cfg);supported,_=support_mask(role,idx)
    assert supported.all(), 'Current outer reference has complete B2 support'
    roster=validation_weights(query.copy())
    previous=pd.read_parquet(old/'outer_roster.parquet').query('horizon_days == 7')
    match=roster.merge(previous[KEY+['weight','supported']],on=KEY,suffixes=('','_old'),validate='one_to_one')
    assert len(match)==len(roster) and match.supported.all() and np.allclose(match.weight,match.weight_old,rtol=0,atol=1e-12)
    baselines=baseline(train,geography)
    reference=pd.read_parquet(old/'C_outer_donors.parquet').query('horizon_days == 7')
    for cell,g in reference.groupby('origin_cell_1'):
        codes,p,_=baselines[int(cell),1.]
        expected=g.groupby('destination').pairs.sum().reindex(codes,fill_value=0).to_numpy()
        assert set(codes[p>0])==set(g.loc[g.pairs.gt(0),'destination'])
        assert expected.sum()==g.pairs.sum()==int(train.origin_cell_1.eq(cell).sum())
        assert np.allclose(p,expected/expected.sum(),rtol=0,atol=1e-12)
    examples_at=example_positions(train,query)
    save_json(paths,run['results']/'example_selection.json',{'query_positions':examples_at,'outcomes_used':False})
    stores={(name,res):ForecastStore(geography[res][1]) for name in ['Annual','Exact'] for res in RESOLUTIONS}
    ids=train.id.to_numpy();diagnostics=[];examples=[];clock=time.monotonic()
    donor_codes={res:train[DEST[res]].to_numpy() for res in RESOLUTIONS}
    for i,q in enumerate(query.itertuples(index=False)):
        found,d=idx.query(q.lon,q.lat,chosen)
        selected=idx.select(found,d,chosen)
        diagnostic_row=diagnostic(ids,selected,d,chosen);diagnostics.append(diagnostic_row)
        example={'lon':q.lon,'lat':q.lat,'id':q.id,'origin_source_obs':q.origin_source_obs,'origin_cell_1':q.origin_cell_1,'grid':geography[.5][0]}
        for res in RESOLUTIONS:
            codes,p=sparse_forecast(donor_codes[res],selected)
            stats=probability_summary(codes,p,-2,geography[res][2])
            stores['Exact',res].append(codes,p,stats['mask'])
            ac,ap,am=baselines[int(q.origin_cell_1),res]
            stores['Annual',res].append(ac,ap,am)
            if res==.5 and i in examples_at:
                example['Exact']=(codes,p,stats['mask']);example['Annual']=(ac,ap,am)
        if i in examples_at:
            examples.append(example)
            save_frame(paths,run['results']/f'examples/donors_{i}.parquet',train.iloc[selected][KEY+['lon','lat','endpoint_lon','endpoint_lat',*DEST.values()]])
        if time.monotonic()-clock>=20:
            print('Outer forecasts',i+1,'/',len(query),flush=True);clock=time.monotonic()
    roster=pd.concat([roster.reset_index(drop=True),pd.DataFrame(diagnostics)],axis=1)
    roster['supported']=True
    save_frame(paths,run['results']/'outer_roster.parquet',roster)
    forecasts={key:value.save(paths,run['results']/f"forecasts/{key[0]}_{str(key[1]).replace('.','p')}") for key,value in stores.items()}
    for name in ['Annual','Exact']:
        fine=forecasts[name,.5][0];coarse=forecasts[name,1.][0]
        fc=geography[.5][1]
        pc=np.where(fc==-2,-2,((fc//720)//2)*360+((fc%720)//2))
        assert np.isin(pc,geography[1.][1]).all(), 'Fine state has no frozen coarse parent'
        mapping=sparse.csr_matrix((np.ones(len(fc)),(np.arange(len(fc)),np.searchsorted(geography[1.][1],pc))),shape=(len(fc),len(geography[1.][1])))
        diff=fine@mapping-coarse
        assert not diff.nnz or abs(diff.data).max()<1e-12
    files={f.relative_to(run['results']).as_posix():file_sha256(f) for f in run['results'].rglob('*') if f.is_file()}
    save_json(paths,run['provenance']/'forecast_freeze.json',{'status':'FROZEN_BEFORE_OUTER_SCORING','files':files,'selected_k':chosen})
    return roster,forecasts,examples


def score_forecasts(roster,forecasts,targets,geography):
    labels=roster[KEY].merge(targets,on=KEY,validate='one_to_one',sort=False)
    parts=[]
    for res in RESOLUTIONS:
        states=geography[res][1];area=geography[res][2]
        result=roster.copy();result['resolution']=res
        truth=labels[DEST[res]].to_numpy()
        result['observed_exit']=(truth==-2).astype(float)
        for name in ['Annual','Exact']:
            p,masks=forecasts[name,res];records=[]
            for i in range(len(result)):
                a,b=p.indptr[i:i+2];codes=states[p.indices[a:b]];v=p.data[a:b]
                if -2 not in codes:codes=np.r_[-2,codes];v=np.r_[0.,v]
                stats=probability_summary(codes,v,int(truth[i]),area)
                selected=codes[stats['mask']]
                a,b=masks.indptr[i:i+2]
                expected=states[masks.indices[a:b][masks.data[a:b]]]
                assert np.array_equal(selected,expected)
                records.append({name+'_'+metric:stats[metric] for metric in METRICS})
            result=pd.concat([result,pd.DataFrame(records)],axis=1)
        parts.append(result)
    return pd.concat(parts,ignore_index=True)


def primary(paths,run,cfg,guard):
    roles,outer,geography,inventory,old,io_seconds=build_roles(paths,run,cfg,guard)
    # Exact real-query audits run afresh, independent of pilot artifacts.
    checks={r['name']:exact_search_audit(r,index_for(r['train'],cfg),cfg) for r in roles}
    chosen,choices,curves=inner_candidates(paths,run,cfg,roles,geography)
    print('Selected k frozen:',chosen,flush=True)
    roster,forecasts,examples=outer_forecasts(paths,run,cfg,roles[-1],geography,chosen,old)
    print('All forecasts frozen; releasing held-out endpoints for scoring.',flush=True)
    targets=inputs.outer_targets(paths,guard,outer['validation'],inventory)
    save_frame(paths,run['results']/'outer_targets.parquet',targets)
    cases=score_forecasts(roster,forecasts,targets,geography)
    legacy=pd.read_csv(old/'summary.csv').query("horizon_days == 7 and model == 'Annual'").iloc[0]
    coarse=cases[cases.resolution.eq(1.)]
    for metric in ['brier','h90','k90','zero']:
        assert abs(float(coarse.weight@coarse['Annual_'+metric])-legacy[metric])<=1e-12
    for e in examples:
        row=targets[(targets.id==e['id']) & (targets.origin_source_obs==e['origin_source_obs'])].iloc[0]
        e.update(truth_lon=row.endpoint_lon,truth_lat=row.endpoint_lat,truth_exit=bool(row.outside))
    save_json(paths,run['provenance']/'input_inventory.json',inventory)
    save_json(paths,run['provenance']/'numerical_checks.json',{'exhaustive_origin_queries_per_role':checks,'baseline_reconciled':True,'nested_grids_reconciled':True,'io_seconds':io_seconds})
    return cases,choices,curves,examples,geography
