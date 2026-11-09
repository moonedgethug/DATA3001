"""Isolated, capped E9 ES optimization pilot. No formal-run entry point."""
import time
BOOT = time.monotonic()
import io
import json
from pathlib import Path
import resource
import signal
import sys
import traceback
import unittest
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import save_json, save_frame
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_inputs as inputs
from data3001.modelling.baselines import seasonal_exact_position_s4_e9 as original
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
from data3001.modelling.baselines.seasonal_exact_position_s4_e9_pipeline import digest
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
from data3001.modelling.baselines.position_error_s4_e8_audit import mass_in_frozen

ROOT = inputs.ROOT
PARENT = 'seasonal_exact_position_s4_e9_20261106T124835_392309Z'
PLAN = 'docs/seasonal_exact_position_s4_e9_es_optimization_plan.md'
PLAN_SHA = '8454b9c28cf62ae98ef12265846cc8340c259621ef3561031eeb7117d6613e7d'
CAPS = dict(preflight=60., pilot=240., review=120.)
REGION_COUNT = 16384


class Budget:
    def __init__(self, paths, run, cfg, stage, guard=None):
        self.paths, self.run, self.cfg, self.stage, self.guard = paths, run, cfg, stage, guard
        self.start = BOOT
        receipts = [json.loads(p.read_text()) for p in run['provenance'].glob('*_resources.json')]
        self.prior = sum(r['elapsed_seconds'] for r in receipts)
        stage_used = sum(r['elapsed_seconds'] for r in receipts if r['stage']==stage)
        remaining = min(CAPS[stage]-stage_used, 420-self.prior, 600-cfg['previous_pilot_seconds']-self.prior)
        self.deadline = self.start+remaining
        signal.signal(signal.SIGALRM, self.timeout)
        signal.setitimer(signal.ITIMER_REAL, max(.01,self.deadline-time.monotonic()-.5))

    def timeout(self, *_): raise TimeoutError('Approved phase/cumulative time cap reached; no retry')

    def check(self):
        if time.monotonic() >= self.deadline-.5: self.timeout()
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 8*2**30: raise MemoryError('8 GiB hard cap')

    def finish(self, label, completed):
        signal.setitimer(signal.ITIMER_REAL,0)
        elapsed = time.monotonic()-self.start
        size = sum(p.stat().st_size for f in self.run.values() for p in f.rglob('*') if p.is_file())
        save_json(self.paths,self.run['provenance']/f'{label}_resources.json',dict(stage=self.stage,
            elapsed_seconds=elapsed,new_cumulative_seconds=self.prior+elapsed,
            total_pilot_seconds=self.cfg['previous_pilot_seconds']+self.prior+elapsed,
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,retained_bytes=size,
            completed=completed,formal_started=False,outer_targets_read=bool(self.guard and self.guard.outcomes_read),
            denied_access=self.guard.denied if self.guard else [],final_test_access=False))


def prepare():
    paths=project_paths()
    parent=ROOT/'provenance/runs'/PARENT
    approval=json.loads((parent/'approval.json').read_text())
    stopped=json.loads((parent/'stopped_delivery.json').read_text())
    protected={**approval['protected_files'],**stopped['source_sha256']}
    assert file_sha256(ROOT/PLAN)==PLAN_SHA
    protected[PLAN]=PLAN_SHA
    for rel,sha in protected.items(): assert file_sha256(ROOT/rel)==sha,rel
    cfg=json.loads((parent/'run.json').read_text())['config']
    receipts=[json.loads(p.read_text()) for p in parent.glob('*_resources.json')]
    cfg=dict(cfg,parent_run=PARENT,previous_pilot_seconds=sum(r['elapsed_seconds'] for r in receipts if r['phase']=='pilot'),
             optimization_plan_sha256=PLAN_SHA,new_cap_seconds=420,phase_caps=CAPS,calibration_pairs=1024)
    assert abs(cfg['previous_pilot_seconds']-167.24954079207964)<1e-8
    name='e9_esopt_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run=paths.create_run(name,cfg)
    budget=Budget(paths,run,cfg,'preflight')
    files=list((ROOT/'src/data3001/modelling/baselines').glob('seasonal_exact_position_s4_e9_esopt*.py'))
    files+=list((ROOT/'tests').glob('test_modelling_seasonal_exact_position_s4_e9_esopt.py'))
    new_hashes={str(p.relative_to(ROOT)):file_sha256(p) for p in files}
    save_json(paths,run['provenance']/'approval.json',dict(
        authorization='User approved isolated ES computation reuse and one control variate, additional 420 seconds and total 600 seconds, independent review, no formal run; report problems before proceeding.',
        protected_files=protected,new_source_sha256=new_hashes,parent_run=PARENT,plan_sha256=PLAN_SHA))
    for p in files: paths.publish(run['provenance']/'sources'/p.name,lambda f,p=p:f.write(p.read_bytes()))
    paths.publish(run['provenance']/'approved_optimization_plan.md',lambda f:f.write((ROOT/PLAN).read_bytes()))
    budget.finish('prepare',True)
    print(name,flush=True)


def context(name,stage):
    if Path(name).name!=name or not name.startswith('e9_esopt_'): raise ValueError('Invalid run')
    paths=project_paths();run=dict(results=ROOT/'results/runs'/name,provenance=ROOT/'provenance/runs'/name)
    cfg=json.loads((run['provenance']/'run.json').read_text())['config']
    approval=json.loads((run['provenance']/'approval.json').read_text())
    guard=inputs.Guard(ROOT,run);sys.addaudithook(guard)
    budget=Budget(paths,run,cfg,stage,guard)
    for rel,sha in {**approval['protected_files'],**approval['new_source_sha256']}.items():
        assert file_sha256(ROOT/rel)==sha,rel
    repair=ROOT/'provenance/migrations'/cfg['repair_run']
    assert file_sha256(repair/'manifest.json')==cfg['repair_manifest_sha256']
    assert file_sha256(repair/'full/error_overlay.parquet')==cfg['overlay_sha256']
    return paths,run,cfg,approval,guard,budget


def key(row,pool,replicate=None):
    k=('s4_e9',row.role,int(row.id),int(row.origin_source_obs),7,pool)
    return k if replicate is None else (*k,replicate)


def contexts(cfg,geo,index=False):
    train,ledger=inputs.load(cfg);out={}
    for role in ['C_T0','C_T1']:
        fit,query,target=inputs.role(cfg,role,train,ledger)
        out[role]=dict(fit=fit,query=query,target=target,cache=opt.cache(fit,geo),
            index=original.SeasonalNeighbours(fit) if index else None)
    return out,train,ledger


def pools(context,selection):
    annual=context['cache'].take(selection['annual_ix'])
    seasonal=annual if selection['fallback'] else context['cache'].take(selection['seasonal_ix'])
    return {'Annual':annual,'Seasonal':seasonal}


def read_selection(run,i):
    with np.load(run['results']/f'lineage/{i:03d}.npz',allow_pickle=False) as f:
        return {k:f[k] for k in f.files}


def save_packets(paths,path,records):
    payload=''.join(json.dumps(r,allow_nan=False)+'\n' for r in records).encode()
    paths.publish(path,lambda f:f.write(payload))


def preflight(paths,run,cfg,approval,guard,budget):
    log=io.StringIO();suite=unittest.TestSuite()
    for name in ['test_modelling_position_error_s4_e8.py','test_modelling_seasonal_exact_position_s4_e9.py',
                 'test_modelling_seasonal_exact_position_s4_e9_esopt.py']:
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern=name))
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    paths.publish(run['provenance']/'semantic_tests.txt',lambda f:f.write(log.getvalue().encode()))
    if not result.wasSuccessful(): raise AssertionError('Semantic tests failed; stop')
    budget.check();cold=time.monotonic();geo=Geography(paths)
    ctx,train,ledger=contexts(cfg,geo,index=True)
    cold_seconds=time.monotonic()-cold
    roster=inputs.read(ROOT/'results/runs'/PARENT/'pilot/roster.parquet')
    old_support=pd.read_csv(ROOT/'results/runs'/PARENT/'pilot_audit/support.csv').set_index(['pilot_position','pool'])
    old_scores=inputs.read(ROOT/'results/runs'/PARENT/'pilot/scores_4096_16384.parquet').set_index(['pilot_position','model'])
    assert len(roster)==128 and (roster.groupby('role').size()==64).all()
    records=[];timings=[];lineages=[];parity=[]
    for role,c in ctx.items():save_frame(paths,run['results']/f'{role}_fit_keys.parquet',c['fit'][inputs.KEY])
    for r in roster.itertuples(index=False):
        budget.check();c=ctx[r.role];q=c['query'].iloc[r.query_position]
        assert (int(q.id),int(q.origin_source_obs))==(r.id,r.origin_source_obs)
        t=time.monotonic();a,s,fallback=c['index'].query(q.lon,q.lat,r.majority_season);search=time.monotonic()-t
        selection=dict(annual_ix=a[0],annual_distance=a[1],seasonal_ix=s[0],seasonal_distance=s[1],fallback=np.array(fallback))
        t=time.monotonic()
        paths.publish(run['results']/f'lineage/{r.pilot_position:03d}.npz',lambda f:np.savez_compressed(f,**selection))
        lineage_io=time.monotonic()-t
        pp=pools(c,selection);truth=c['target'].iloc[r.query_position][['endpoint_lon','endpoint_lat']].to_numpy(float)
        old_f={};old_s={};t=time.monotonic()
        for pool,p in pp.items():
            if pool=='Seasonal' and fallback:old_f[pool]=old_f['Annual'];old_s[pool]=old_s['Annual'];continue
            f,_=original.predict_pool(p.points,p.sd,p.usable,key=key(r,pool,0),energy_count=4096,region_count=REGION_COUNT,geography=geo)
            old_f[pool]=f;old_s[pool]=original.score_pool(p.points,p.sd,p.usable,f,truth,key(r,pool,0))
        old_seconds=time.monotonic()-t
        profile={};new_f={};new_s={};t=time.monotonic()
        for pool,p in pp.items():
            if pool=='Seasonal' and fallback:new_f[pool]=new_f['Annual'];new_s[pool]=new_s['Annual'];continue
            f,_=opt.regions(p,key(r,pool,0),REGION_COUNT,geo,profile)
            new_f[pool]=f
            new_s[pool]=opt.score(p,f,truth,key(r,pool,0),4096,dict(coefficient=0.,mean_squared=0.),profile=profile)
        new_seconds=time.monotonic()-t
        record=dict(pilot_position=r.pilot_position,packets={pool:{str(ci):v for ci,v in fs.items()} for pool,fs in new_f.items()})
        t=time.monotonic();payload=json.dumps(record,allow_nan=False).encode()
        paths.publish(run['results']/f'packets/{r.pilot_position:03d}.json',lambda f:f.write(payload))
        packet_io=time.monotonic()-t
        for pool,p in pp.items():
            ix=a[0] if pool=='Annual' else s[0]
            assert digest(ix)==old_support.loc[(r.pilot_position,pool),'lineage_digest']
            lineages.append(dict(pilot_position=r.pilot_position,pool=pool,donors=len(ix),
                                 lineage_digest=digest(ix),fallback=bool(fallback)))
            for ci,kind in [(False,'ExactPoint'),(True,'EndpointCI')]:
                assert new_f[pool][ci]['region']==old_f[pool][ci]['region']
                for metric in ['energy_km','h90','area90_km2','energy_mc_se','land_mass','outside_D_mass','land_area_km2','wet_area_km2','outside_D_area_km2']:
                    np.testing.assert_allclose(new_s[pool][ci][metric],old_s[pool][ci][metric],atol=1e-10,rtol=0)
                    np.testing.assert_allclose(new_s[pool][ci][metric],old_scores.loc[(r.pilot_position,pool+kind),metric],atol=1e-10,rtol=0)
                parity.append(dict(pilot_position=r.pilot_position,model=pool+kind,
                    energy_abs_difference=abs(new_s[pool][ci]['energy_km']-old_s[pool][ci]['energy_km']),region_equal=True))
        profile.update(pilot_position=r.pilot_position,search_seconds=search,lineage_io_seconds=lineage_io,
            packet_io_seconds=packet_io,old_total_seconds=old_seconds+search+lineage_io+packet_io,
            reuse_total_seconds=new_seconds+search+lineage_io+packet_io)
        timings.append(profile)
        if (r.pilot_position+1)%32==0:print('preflight parity',r.pilot_position+1,'/128',round(time.monotonic()-BOOT,2),'s',flush=True)
    save_frame(paths,run['results']/'roster.parquet',roster)
    save_frame(paths,run['results']/'preflight_timings.csv',pd.DataFrame(timings))
    save_frame(paths,run['results']/'preflight_parity.csv',pd.DataFrame(parity))
    save_frame(paths,run['results']/'lineage.csv',pd.DataFrame(lineages))
    save_json(paths,run['provenance']/'preflight.json',dict(passed=True,tests=result.testsRun,queries=128,
        arms=4,cold_seconds=cold_seconds,formal_started=False,outer_targets_read=guard.outcomes_read,
        packet_sha256={str(p.relative_to(ROOT)):file_sha256(p) for p in (run['results']/'packets').glob('*.json')},
        source_cache_bytes=sum(c['cache'].bytes for c in ctx.values())))


def projections(scores,outer,cfg):
    weights=original.case_weights(outer);seasons=original.season_labels(outer.origin_time_UTC).majority_season.to_numpy()
    W={s:float(np.sum(weights[seasons==s]**2)) for s in range(4)}
    out={}
    for candidate,control in [('SeasonalExactPoint','AnnualExactPoint'),('SeasonalEndpointCI','AnnualEndpointCI')]:
        rep=[];delta=[];pilot_var=[]
        for k in [0,1]:
            a=scores[scores.model.eq(candidate)&scores.replicate.eq(k)].sort_values('pilot_position')
            b=scores[scores.model.eq(control)&scores.replicate.eq(k)].sort_values('pilot_position')
            variance=a.energy_mc_se.to_numpy()**2+b.energy_mc_se.to_numpy()**2
            variance[a.seasonal_fallback.to_numpy()]=0.
            maxima={s:float(variance[a.majority_season.to_numpy()==s].max()) for s in range(4)}
            reference=float(original.case_weights(b)@b.energy_km)
            rep.append(dict(three_se_km=float(3*np.sqrt(sum(W[s]*maxima[s] for s in range(4)))),threshold_km=.0001*reference))
            w=original.case_weights(a)
            delta.append(float(w@(a.energy_km.to_numpy()-b.energy_km.to_numpy())))
            pilot_var.append(float(np.sum(w*w*variance)))
        seed_difference=abs(delta[0]-delta[1]);seed_limit=3*np.sqrt(sum(pilot_var))
        out[candidate]=dict(replicates=rep,three_se_km=max(r['three_se_km'] for r in rep),
            threshold_km=min(r['threshold_km'] for r in rep),seed_difference_km=seed_difference,
            seed_limit_km=float(seed_limit),seed_passed=bool(seed_difference<=seed_limit),
            precision_passed=all(r['three_se_km']<=r['threshold_km'] for r in rep))
    return out


def pilot(paths,run,cfg,approval,guard,budget):
    pre=json.loads((run['provenance']/'preflight.json').read_text());assert pre['passed']
    for rel,h in pre['packet_sha256'].items():assert file_sha256(ROOT/rel)==h
    geo=Geography(paths);ctx,train,ledger=contexts(cfg,geo)
    _,outer,_=inputs.role(cfg,'C_outer',train,ledger)
    roster=inputs.read(run['results']/'roster.parquet');timing0=pd.read_csv(run['results']/'preflight_timings.csv').set_index('pilot_position')
    states=[];calibrations=[];region_checks=[]
    cache_bytes=sum(c['cache'].bytes for c in ctx.values())
    for r in roster.itertuples(index=False):
        budget.check();sel=read_selection(run,r.pilot_position);pp=pools(ctx[r.role],sel)
        cache_bytes+=sum(p.bytes for p in pp.values())
        if cache_bytes>512*2**20:raise MemoryError('Explicit cache exceeds 512 MiB')
        raw=json.loads((run['results']/f'packets/{r.pilot_position:03d}.json').read_text())['packets']
        f0={pool:{ci=='True':v for ci,v in fs.items()} for pool,fs in raw.items()}
        f1={};controls={};cal_seconds=0.
        for pool,p in pp.items():
            if pool=='Seasonal' and bool(sel['fallback']):f1[pool]=f1['Annual'];controls[pool]=controls['Annual'];continue
            t=time.monotonic();controls[pool]=opt.calibration(p,key(r,pool));cal_seconds+=time.monotonic()-t
            f1[pool],cloud=opt.regions(p,key(r,pool,1),REGION_COUNT)
            for ci,kind in [(False,'ExactPoint'),(True,'EndpointCI')]:
                mass=mass_in_frozen(*cloud[ci],f0[pool][ci]['region'])
                region_checks.append(dict(pilot_position=r.pilot_position,id=r.id,model=pool+kind,
                    mass_error=abs(mass-f0[pool][ci]['region']['attained_mass'])))
        for pool in pp:calibrations.append(dict(pilot_position=r.pilot_position,pool=pool,**controls[pool]))
        states.append((r,pp,f0,f1,controls,cal_seconds,bool(sel['fallback'])))
    save_json(paths,run['provenance']/'calibration_freeze.json',dict(calibrations=calibrations,
        scoring_key='Original E9 keys unchanged; independent calibration tag e9_es_control_calibration_v1',
        outer_targets_read=False,cache_bytes=cache_bytes))
    levels=[];selected=None
    for count in cfg['energy_ladder']:
        rows=[];timings=[]
        reference=inputs.read(ROOT/'results/runs'/PARENT/f'pilot/scores_{count}_{REGION_COUNT}.parquet').set_index(['pilot_position','model'])
        for r,pp,f0,f1,controls,cal_seconds,fallback in states:
            budget.check();truth=ctx[r.role]['target'].iloc[r.query_position][['endpoint_lon','endpoint_lat']].to_numpy(float)
            primary_profile={};primary_elapsed=0.
            for rep,packets in [(0,f0),(1,f1)]:
                profile={};scored={};t=time.monotonic()
                for pool,p in pp.items():
                    if pool=='Seasonal' and fallback:scored[pool]=scored['Annual'];continue
                    scored[pool]=opt.score(p,packets[pool],truth,key(r,pool,rep),count,controls[pool],profile=profile)
                seconds=time.monotonic()-t
                case_rows=[]
                for pool,values in scored.items():
                    for ci,kind in [(False,'ExactPoint'),(True,'EndpointCI')]:
                        v=values[ci];name=pool+kind
                        if rep==0:
                            np.testing.assert_allclose(v['raw_energy_km'],reference.loc[(r.pilot_position,name),'energy_km'],atol=1e-10,rtol=0)
                            for metric in ['h90','area90_km2','mass90']:
                                np.testing.assert_allclose(v[metric],reference.loc[(r.pilot_position,name),metric],atol=1e-10,rtol=0)
                        case_rows.append(dict(pilot_position=r.pilot_position,id=r.id,role=r.role,model=name,replicate=rep,
                            majority_season=r.majority_season,seasonal_fallback=fallback,**v))
                rows.extend(case_rows)
                if rep==0:
                    t=time.monotonic()
                    paths.publish(run['results']/f'score_io/{count}/{r.pilot_position:03d}.json',lambda f:f.write(json.dumps(case_rows,allow_nan=False).encode()))
                    profile['score_io_seconds']=time.monotonic()-t
                    primary_profile=profile;primary_elapsed=seconds+profile['score_io_seconds']
            common=timing0.loc[r.pilot_position]
            charged={n:float(common[n]) for n in ['search_seconds','lineage_io_seconds','packet_io_seconds','region_cloud_seconds','region_fit_seconds','geography_seconds']}
            charged.update(primary_profile);charged['calibration_seconds']=cal_seconds
            charged.update(pilot_position=r.pilot_position,total_seconds=primary_elapsed+cal_seconds+sum(float(common[n]) for n in
                ['search_seconds','lineage_io_seconds','packet_io_seconds','region_cloud_seconds','region_fit_seconds','geography_seconds']))
            timings.append(charged)
            if (r.pilot_position+1)%32==0:print('optimized ladder',count,r.pilot_position+1,'/128',round(time.monotonic()-BOOT,2),'s',flush=True)
        scores=pd.DataFrame(rows);timing=pd.DataFrame(timings);projection=projections(scores,outer,cfg)
        rc=[]
        checks=pd.DataFrame(region_checks)
        for name,g in scores.groupby('model'):
            a=g[g.replicate.eq(0)].sort_values('pilot_position');b=g[g.replicate.eq(1)].sort_values('pilot_position');w=original.case_weights(a)
            rc.append(dict(model=name,max_mass_error=float(checks[checks.model.eq(name)].mass_error.max()),
                weighted_hit_change=float(w@abs(a.h90.to_numpy()-b.h90.to_numpy())),
                weighted_area_change=float(w@abs(a.area90_km2.to_numpy()-b.area90_km2.to_numpy())/(w@a.area90_km2))))
        tail=float(timing.total_seconds.quantile(.95));component_names=[n for n in timing if n.endswith('_seconds') and n!='total_seconds']
        component_tail=float(sum(timing[n].quantile(.95) for n in component_names))
        cold=max(60.,pre['cold_seconds'])
        estimate=max((33971*tail+cold)*1.1,(33971*component_tail+cold)*1.1)
        numerical=all(z['precision_passed'] and z['seed_passed'] for z in projection.values())
        region_ok=all(z['max_mass_error']<=.005 and z['weighted_hit_change']<=.001 and z['weighted_area_change']<=.005 for z in rc)
        resource_ok=2*estimate<=7200 and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<=4*2**30
        level=dict(energy_count=count,region_count=REGION_COUNT,projection=projection,region_checks=rc,
            numerical_passed=numerical,region_passed=region_ok,resource_precheck_passed=resource_ok,
            p95_case_seconds=tail,component_p95_sum_seconds=component_tail,max_case_seconds=float(timing.total_seconds.max()),
            formal_projected_seconds=estimate,formal_projection_2x_seconds=2*estimate)
        save_frame(paths,run['results']/f'scores_{count}.parquet',scores)
        save_frame(paths,run['results']/f'timings_{count}.csv',timing)
        save_frame(paths,run['results']/f'region_precision_{count}.csv',checks)
        save_json(paths,run['results']/f'level_{count}.json',level)
        levels.append(level);print(json.dumps(level),flush=True)
        if not region_ok or any(not z['seed_passed'] for z in projection.values()):break
        if numerical:
            selected=count;break
    gate=dict(levels=levels,selected_count=selected,numerical_passed=levels[-1]['numerical_passed'],
        pilot_precheck_passed=levels[-1]['numerical_passed'] and levels[-1]['region_passed'] and levels[-1]['resource_precheck_passed'],
        formal_authorized=False,formal_started=False,outer_targets_read=False,full_roster_preflight_completed=False,
        reason='Await independent review and user decision; full-roster support/storage/audit gate still required',cache_bytes=cache_bytes)
    save_json(paths,run['provenance']/'pilot_gate.json',gate)
    print(json.dumps(gate,indent=2),flush=True)


def main():
    if sys.argv[1]=='prepare':prepare();return
    stage,name=sys.argv[1:];paths,run,cfg,approval,guard,budget=context(name,stage)
    completed=False
    try:
        if stage=='preflight':preflight(paths,run,cfg,approval,guard,budget)
        elif stage=='pilot':pilot(paths,run,cfg,approval,guard,budget)
        elif stage=='review':
            from data3001.modelling.baselines.seasonal_exact_position_s4_e9_esopt_review import review
            review(paths,run,cfg,approval,guard,budget)
        else:raise ValueError('Only preflight, pilot and review are authorized')
        for rel,h in approval['protected_files'].items():assert file_sha256(ROOT/rel)==h,rel
        budget.check();completed=True
    except Exception as exc:
        save_json(paths,run['provenance']/f'{stage}_stopped.json',dict(error=repr(exc),traceback=traceback.format_exc(),formal_started=False))
        raise
    finally:budget.finish(stage,completed)


if __name__=='__main__':main()
