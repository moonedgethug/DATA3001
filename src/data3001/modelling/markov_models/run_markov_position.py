"""Guarded frozen-fold exact-position M1vcat experiment. Final test is locked.

python -B -m data3001.modelling.markov_models.run_markov_position --prepare-only [--pilot]
python -B -m data3001.modelling.markov_models.run_markov_position --input-run RUN [--benchmark]
"""
from data3001.modelling.common.geometry import mapper_for
import argparse
from datetime import datetime,timezone
import gc
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
import pandas as pd
import shapely as sh
from shapely.geometry import shape

from data3001.dataset import track_path
from data3001.modelling.common.experiment import make_nested_folds, fold_digest
from data3001.modelling.markov_models.markov_position import fit_pool, forecast_particles, categorical_law
from data3001.modelling.markov_models.markov_position_inputs import collect_position_inputs
from data3001.modelling.common.markov_position_scores import ensemble_scores, aggregate_scores, summarize_scores, paired_intervals, validate_comparison
from data3001.modelling.markov_models.markov_velocity import coarse_velocity
from data3001.modelling.common.geometry import EndpointMapper
from data3001.modelling.common.runtime import ReadOnlyInputs, save_frame, save_json
from data3001.modelling.markov_models.run_markov import identity, environment, verify_bound
from data3001.modelling.common.runtime import verified_run, _source_hashes, _seal
from data3001.paths import project_paths,file_sha256

CONFIG=Path('configs/markov_m1_position.json')
KEYS=['id','horizon_days','origin_cell_1','origin_velocity_bin','destination_cell_1']


def validate_settings(c):
    required={'predictors':['lon','lat','ve','vn'],'velocity_classes':9,'target':'stopped',
        'scenario':'pooled','departure_seasons':'annual_pooled','grid_degrees':1,
        'evaluation_days':[7,30],'kernel_days':[1,2,3,5,7],
        'parameters':'frozen_original_outer_folds_no_retuning',
        'displacement':'WGS84_source_inverse_then_query_forward',
        'translated_exit':'every_observed_hour_or_proven_interior',
        'source_exit':'retain_original_empirical_E_branch','geometry_failure':'U_no_renormalization',
        'weighting':'equal_eligible_pairs','tolerance_hours':0,'particles_per_repeat':32,
        'repeats':2,'batch_origins':128,'seed':20261027,'final_test_access':False}
    if any(c.get(k)!=v for k,v in required.items()):raise ValueError('Settings exceed frozen exact-position scope')
    return c


def settings(paths):return validate_settings(json.loads((paths.root/CONFIG).read_text()))


def particles_for_level(level):
    if isinstance(level,bool) or level not in [0,1,2] or int(level)!=level:
        raise ValueError('Numerical integration level must be 0, 1 or 2')
    return 32*2**int(level)


def start(paths,kind,c,extra,receipts):
    data,bound=identity(paths)
    if data['version']!=c['dataset_release'] or bound.get('docs/contract/data_contract_v1.0.xlsx')!=c['contract_sha256']:
        raise ValueError('Dataset/contract changed')
    bound[CONFIG.as_posix()]=file_sha256(paths.root/CONFIG)
    for p in receipts:bound[p.relative_to(paths.root).as_posix()]=file_sha256(p)
    sources=_source_hashes(paths);name=datetime.now(timezone.utc).strftime(kind+'_%Y%m%dT%H%M%S_%fZ')
    run=paths.create_run(name,{**c,**extra,'input_sha256':bound,'source_sha256':sources})
    guard=ReadOnlyInputs(paths.root,run,data_root=paths.data_root);sys.addaudithook(guard)
    return data,bound,sources,run,guard


def finish(paths,run,bound,sources,guard,record):
    verify_bound(paths,bound,sources)
    if guard.denied:raise ValueError('Read-only/test guard triggered')
    record.update(canonical_tracks_read=len(guard.read_ids),final_test_trajectories_read=0,
        canonical_changed=False,denied_operations=guard.denied,
        max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,environment=environment())
    _seal(paths,run,record);print('COMPLETED_RUN='+run['results'].name,flush=True)
    print(json.dumps({k:v for k,v in record.items() if k!='environment'},indent=2),flush=True)


def prepare(paths,pilot=False):
    c=settings(paths);receipts=[verified_run(paths,c[k]) for k in ['source_parent','velocity_parent','comparison_parent']]
    data,_=identity(paths);ids=sorted(int(i) for i,r in data['records'].items() if r['pool']=='train')
    outer,inner=make_nested_folds(ids)
    if pilot:
        ix=pd.read_csv(paths.asset('current_dataset_index',verify=True));visiting=set(ix.loc[ix.in_R.eq(True),'id'])
        ids=sorted([i for i in ids if i in visiting][:10]+[i for i in ids if i not in visiting][:10])
    _,bound,sources,run,guard=start(paths,'markov_position_pilot' if pilot else 'markov_position_input',c,
        {'pilot':pilot,'development_IDs':ids,'fold_digest':fold_digest(outer,inner)},receipts)
    try:
        thresholds=json.loads((paths.root/'results/runs'/c['velocity_parent']/'thresholds.json').read_text())
        save_json(paths,run['results']/'thresholds.json',thresholds)
        record=collect_position_inputs(paths,run,ids,paths.root/'results/runs'/c['source_parent'],thresholds['cutpoints'])
        if guard.read_ids!=set(ids):raise ValueError('Canonical read roster mismatch')
        for i in ids:track_path(i,allow_test=False)
        finish(paths,run,bound,sources,guard,{**record,'pilot':pilot})
    except Exception as e:save_json(paths,run['provenance']/'FAILED.json',{'error':repr(e)});raise
    finally:guard.active=False


def choices_for_fold(table,fold):
    g=table.loc[table.outer_fold.eq(fold)&table.model.eq('M1vcat-selected')]
    if len(g)!=2 or set(g.horizon_days)!={7,30}:raise ValueError('Original frozen choices missing or duplicated')
    return {int(r.horizon_days):(int(r.lag_days),float(r.lambda_value)) for r in g.itertuples()}


def match_reference(part,reference):
    if reference.duplicated(KEYS).any():raise ValueError('Ambiguous original score groups')
    actual=part.groupby(KEYS,as_index=False).size().rename(columns={'size':'pair_count'})
    expected=reference[KEYS+['pair_count']]
    try:
        pd.testing.assert_frame_equal(actual.sort_values(KEYS).reset_index(drop=True),
            expected.sort_values(KEYS).reset_index(drop=True),check_dtype=False)
    except AssertionError as e:raise ValueError('Original R case counts differ') from e
    result=part.merge(reference[KEYS+['brier_failure_penalized']],on=KEYS,how='left',validate='many_to_one')
    if len(result)!=len(part) or result.brier_failure_penalized.isna().any():raise ValueError('Unmatched original R case')
    return result.rename(columns={'brier_failure_penalized':'old_S'})


def load_inputs(paths,name,pilot=False):
    receipt=verified_run(paths,name);meta=json.loads((receipt.parent/'run.json').read_text())['config']
    data,_=identity(paths);all_ids={int(i) for i,r in data['records'].items() if r['pool']=='train'}
    ids=set(meta['development_IDs'])
    if not ids<=all_ids or (not pilot and (meta.get('pilot') is not False or ids!=all_ids)):
        raise ValueError('Full development-only source cache required')
    for rel,sha in meta['input_sha256'].items():
        if file_sha256(paths.root/rel)!=sha:raise ValueError('Cache input changed: '+rel)
    root=paths.root/'results/runs'/name;obs=np.load(root/'observations.npy',mmap_mode='r')
    releases=pd.read_parquet(root/'releases.parquet');roster=pd.read_csv(root/'source_ID_summary.csv')
    if set(roster.id)!=ids or len(obs)!=int(roster.rows.sum()) or not set(releases.id)<=ids:raise ValueError('Invalid cache roster')
    outer,inner=make_nested_folds(sorted(all_ids))
    if meta['fold_digest']!=fold_digest(outer,inner):raise ValueError('Fold map changed')
    th=json.loads((root/'thresholds.json').read_text())
    return ids,obs,releases,th,outer,receipt


def fitted_pools(root,obs,bins,fitting,schedule):
    pools={}
    for lag in sorted(set(schedule)):
        t=pd.read_parquet(root/'donors.parquet',filters=[('lag','==',lag)],columns=['origin','endpoint'])
        keep=np.isin(obs['id'][t.origin.to_numpy()],list(fitting));t=t.loc[keep]
        pools[lag]=fit_pool(obs,t.origin.to_numpy(),t.endpoint.to_numpy(),bins,fitting,lag)
        del t,keep;gc.collect()
    return pools


def verify_old_law(paths,parent,fold,pools,bins,lam):
    """All fitting row counts and selected exact joint laws must match the old operator."""
    from scipy.sparse import load_npz
    checks=[]
    for lag,pool in pools.items():
        base=paths.root/'results/runs'/parent/'operators'/f'outer_{fold}_{lag}d'
        support=pd.read_parquet(str(base)+'_support.parquet')
        keys=support.origin_cell_1.to_numpy()*9+support.origin_velocity_bin.to_numpy()
        if not np.array_equal(pool.conditional_count[keys],support.pair_count):raise ValueError('Fitting donor frequencies differ')
        meta=json.loads(Path(str(base)+'.json').read_text());cells=meta['cells'];pos={c:i for i,c in enumerate(cells)}
        local=load_npz(str(base)+'_local.npz');pooled=load_npz(str(base)+'_pooled.npz')
        nonzero=support.loc[support.pair_count.gt(0)]
        sampled=nonzero.iloc[np.linspace(0,len(nonzero)-1,min(16,len(nonzero)),dtype=int)]
        maximum=0.
        for r in sampled.itertuples():
            c,b=int(r.origin_cell_1),int(r.origin_velocity_bin);j=pos[c]*9+b
            law=categorical_law(pool,c,b,lam)
            v=((1-lam)*local.getrow(j)+lam*pooled.getrow(pos[c])).tocsr()
            expected={((cells[k//9],k%9) if k<len(cells)*9 else (-2,-2) if k==len(cells)*9 else (-3,-3)):float(w)
                for k,w in zip(v.indices,v.data)}
            error=max([abs(law.get(k,0)-expected.get(k,0)) for k in set(law)|set(expected)]+[0.])
            maximum=max(maximum,error)
        if maximum>1e-12:raise ValueError('Old joint law differs from donor law')
        checks.append({'outer_fold':fold,'lag_days':lag,'all_support_counts_identical':True,
                       'joint_rows_checked':len(sampled),'maximum_joint_probability_error':maximum})
    return checks




def evaluate(paths,name,benchmark=False,integration_level=0):
    particles=particles_for_level(integration_level)
    c=settings(paths);ids,obs,releases,th,outer,receipt=load_inputs(paths,name,benchmark)
    old_receipt=verified_run(paths,c['comparison_parent']);root=paths.root/'results/runs'/name
    _,bound,sources,run,guard=start(paths,'markov_position_benchmark' if benchmark else 'markov_position_cv',c,
        {'input_run':name,'benchmark':benchmark,'integration_level':integration_level,
         'numerical_particles_per_repeat':particles},(receipt,old_receipt))
    begun=time.monotonic();parts=[];audit=[];closures=[];fits=[];example=[];observed=[]
    try:
        original=pd.read_csv(paths.root/'results/runs'/c['comparison_parent']/'selected_parameters.csv')
        save_frame(paths,run['results']/'frozen_parameters.csv',original.loc[original.model.eq('M1vcat-selected')])
        mapper=mapper_for(paths)
        for fold in ([0] if benchmark else range(5)):
            held={i for i in ids if outer[i]==fold};fitting=ids-held
            record=th['roles'][f'outer_{fold}']
            # A preparation pilot is only for engineering; it uses a subset of
            # the original fitting roster and cannot be reported as formal CV.
            if benchmark and ids!=set(record['fitting_ids'])|held:record={**record,'fitting_ids':sorted(fitting)}
            bins=coarse_velocity(obs['atom'],th['cutpoints'],record['threshold_m_s'])
            choices=choices_for_fold(original,fold)
            trainR=releases.loc[releases.reason_code.eq(0)&releases.id.isin(fitting)&releases.horizon_days.eq(7)].copy()
            trainR['origin_velocity_bin']=bins[trainR.origin]
            support=trainR.groupby(['origin_cell_1','origin_velocity_bin']).size().sort_values(ascending=False)
            example_key=tuple(map(int,support.index[0]))
            ref=pd.read_parquet(paths.root/'results/runs'/c['comparison_parent']/f'outer_{fold}_scores.parquet')
            ref=ref.loc[ref.model.eq('M1vcat-selected')]
            for h,(lag,lam) in choices.items():
                validate_comparison(record,fitting,held,lag,lam)
                print(f'Fold {fold+1}/5, {h}d: preparing frozen {lag}d / lambda {lam}',flush=True)
                q,r=divmod(h,lag);schedule=[lag]*q+([r] if r else [])
                pools=fitted_pools(root,obs,bins,fitting,schedule)
                if not benchmark:closures.extend(verify_old_law(paths,c['comparison_parent'],fold,pools,bins,lam))
                part=releases.loc[releases.reason_code.eq(0)&releases.id.isin(held)&releases.horizon_days.eq(h)].copy()
                part['origin_velocity_bin']=bins[part.origin]
                if not benchmark:part=match_reference(part,ref.loc[ref.horizon_days.eq(h)])
                else:part=part.head(256).assign(old_S=np.nan)
                if part.empty:
                    if not benchmark:raise ValueError('Formal outer horizon has no eligible held-out cases')
                    print(f'Engineering subset has no {h}d held cases; no score fabricated',flush=True)
                    del pools;gc.collect();continue
                foldscores=[]
                for number,(sid,g) in enumerate(part.groupby('id',sort=True),1):
                    g=g.sort_values('origin_source_obs').reset_index(drop=True)
                    for start_at in range(0,len(g),c['batch_origins']):
                        batch=g.iloc[start_at:start_at+c['batch_origins']];idx=batch.origin.to_numpy()
                        for rep in range(c['repeats']):
                            seed=int((c['seed']+fold*1000003+h*10007+int(sid)*97+start_at*193+rep*1000000007)%(2**63-1))
                            for precise in [False,True]:
                                model='exact-position' if precise else 'coarse-sampler'
                                draws,stats=forecast_particles(pools,obs['lon'][idx],obs['lat'][idx],bins[idx],h,lag,lam,
                                    particles,seed,mapper,precise=precise)
                                score=ensemble_scores(draws,batch.destination_cell_1.to_numpy())
                                for key in ['id','origin_source_obs','origin_cell_1','origin_velocity_bin','destination_cell_1']:
                                    score[key]=batch[key].to_numpy()
                                score['horizon_days']=h;score['outer_fold']=fold;score['repeat']=rep;score['model']=model
                                foldscores.append(score)
                                audit.append({'outer_fold':fold,'horizon_days':h,'id':int(sid),'repeat':rep,'model':model,**stats})
                                if fold==0:
                                    ex=batch.origin_cell_1.eq(example_key[0])&batch.origin_velocity_bin.eq(example_key[1])
                                    if ex.any():
                                        keys,cnt=np.unique(draws[ex],return_counts=True)
                                        example.extend((h,model,rep,int(k),int(n)) for k,n in zip(keys,cnt))
                                        if not precise and rep==0:
                                            observed.extend((h,int(y),int(sid),int(o),float(x),float(z)) for y,o,x,z in zip(
                                                batch.loc[ex,'destination_cell_1'],batch.loc[ex,'origin_source_obs'],obs['lon'][idx[ex]],obs['lat'][idx[ex]]))
                        if not benchmark:
                            score=foldscores[-1].copy();score['model']='old-exact';score['repeat']=0
                            score['S_integration']=batch.old_S.to_numpy();score['S_issued']=batch.old_S.to_numpy()
                            # Only categorical S is imported from the exact old
                            # operator here; do not mislabel new ensemble diagnostics.
                            for key in ['true_probability_issued','U_mass','E_mass','sampled_zero','region90_available',
                                        'region90_hit','region90_cells','region90_mass','energy_km_issued',
                                        'mean_squared_km2_issued','linear_quadratic_issued']:score[key]=np.nan
                            foldscores.append(score)
                    if number%10==0 or number==part.id.nunique():
                        print(f'Fold {fold+1}, {h}d: {number}/{part.id.nunique()} IDs; elapsed {time.monotonic()-begun:.1f}s',flush=True)
                scored=pd.concat(foldscores,ignore_index=True);del foldscores
                summary=aggregate_scores(scored);parts.append(summary)
                save_frame(paths,run['results']/f'outer_{fold}_{h}d_scores.parquet',scored)
                save_frame(paths,run['results']/f'outer_{fold}_{h}d_ID_scores.csv',summary)
                fits.append({'outer_fold':fold,'horizon_days':h,'fitting_ids':sorted(fitting),'evaluation_ids':sorted(held),
                             'lag_days':lag,'lambda_value':lam,'threshold_m_s':record['threshold_m_s']})
                if fold==0:save_json(paths,run['results']/'example_definition.json',{'cell':example_key[0],'velocity_bin':example_key[1],
                    'selection':'largest fitting-only 7-day eligible R support; average individual exact queries within this cohort'}) if h==7 else None
                del pools,scored,part;gc.collect()
            del bins;gc.collect()
        allscores=pd.concat(parts,ignore_index=True);summary=summarize_scores(allscores)
        save_frame(paths,run['results']/'ID_scores.csv',allscores);save_frame(paths,run['results']/'summary.csv',summary)
        save_frame(paths,run['results']/'particle_audit.parquet',pd.DataFrame(audit))
        save_frame(paths,run['results']/'old_law_closure.csv',pd.DataFrame(closures))
        save_json(paths,run['provenance']/'fit_ID_records.json',fits)
        save_frame(paths,run['results']/'example_predictions.parquet',pd.DataFrame(example,columns=['horizon_days','model','repeat','destination_cell_1','particles']))
        save_frame(paths,run['results']/'example_observed.parquet',pd.DataFrame(observed,columns=['horizon_days','destination_cell_1','id','origin_source_obs','lon','lat']))
        if not benchmark:
            save_frame(paths,run['results']/'paired_ID_intervals.csv',paired_intervals(allscores,c['bootstrap_replicates']))
            # A reusable refit is the full-development empirical donor law;
            # immutable cache indices + this threshold/recipe reconstruct it.
            candidate=json.loads((paths.root/'results/runs'/c['comparison_parent']/'development_candidate.json').read_text())
            save_json(paths,run['results']/'development_candidate.json',{**candidate,'input_run':name,
                'position_update':c['displacement'],'source_cache_sha256':file_sha256(root/'donors.parquet'),
                'implementation':'data3001.modelling.markov_models.run_markov_position.fitted_pools',
                'evaluation_claim':'reconstructible_development_refit_not_independently_scored'})
            from data3001.modelling.markov_models.markov_position_report import write_report
            write_report(paths,run,{**c,'active_particles_per_repeat':particles},summary,allscores)
        finish(paths,run,bound,sources,guard,{'elapsed_seconds':time.monotonic()-begun,'benchmark':benchmark,
            'frozen_parameter_comparison':True,'source_input_run':name,'all_parent_R_cases_matched':not benchmark,
            'canonical_rows_recleaned':0,'outer_folds':1 if benchmark else 5,
            'particles_per_repeat':particles,'independent_repeats':c['repeats']})
    except Exception as e:save_json(paths,run['provenance']/'FAILED.json',{'error':repr(e)});raise
    finally:guard.active=False


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--pilot',action='store_true');parser.add_argument('--input-run');parser.add_argument('--benchmark',action='store_true')
    parser.add_argument('--integration-level',type=int,choices=[0,1,2],default=0,
                        help='32/64/128 particles per repeat; numerical integration only, no parameter retuning')
    a=parser.parse_args();paths=project_paths()
    if a.prepare_only:prepare(paths,a.pilot)
    elif a.input_run:evaluate(paths,a.input_run,a.benchmark,a.integration_level)
    else:parser.error('Choose --prepare-only or --input-run')


if __name__=='__main__':main()
