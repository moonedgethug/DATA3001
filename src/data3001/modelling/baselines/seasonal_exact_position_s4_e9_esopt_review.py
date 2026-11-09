"""Independent reconstruction and bounded report for the E9 numerical pilot."""
import base64
import hashlib
import json
import time
import numpy as np
import pandas as pd
from pyproj import Geod, Transformer
from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_json, save_frame
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_inputs as inputs
from data3001.modelling.baselines import position_error_s4_e8 as geometry
from data3001.modelling.baselines.seasonal_exact_position_s4_e9_audit import reference_calendar, reference_selection
from data3001.modelling.baselines.position_error_s4_e8_audit import reference_region

GEOD=Geod(ellps='WGS84')
TRANSFORM=Transformer.from_crs('EPSG:4979','EPSG:4978',always_xy=True)


def rng(k):
    seed=int.from_bytes(hashlib.sha256(json.dumps(k,separators=(',',':')).encode()).digest()[:16],'little')
    return np.random.Generator(np.random.PCG64(seed))


def cartesian(p):
    return np.array(TRANSFORM.transform(p[:,0],p[:,1],np.zeros(len(p)))).T/1000


def shift(p,sd,z):
    offset=sd*z
    distance=np.linalg.norm(offset,axis=1)
    lon,lat,_=GEOD.fwd(p[:,0],p[:,1],np.degrees(np.arctan2(offset[:,0],offset[:,1])),distance*1000)
    out=np.column_stack([lon,lat]);out[distance==0]=p[distance==0]
    return out


def reference_score(p,sd,truth,base_key,count,coefficient,mu,rep):
    g=rng((*base_key,rep,'energy'));n=len(p)
    i,j=g.integers(n,size=count),g.integers(n,size=count)
    z,w=g.standard_normal((count,2)),g.standard_normal((count,2))
    x=cartesian(p);y=cartesian(np.asarray(truth)[None,:])[0]
    u,v=cartesian(shift(p[i],sd[i],z)),cartesian(shift(p[j],sd[j],w))
    d=np.sqrt(np.sum((x[i]-x[j])**2,axis=1))
    correction=-.5*d+.5*coefficient*(d*d-mu)
    increment=np.sqrt(np.sum((u-y)**2,axis=1))-np.sqrt(np.sum((x[i]-y)**2,axis=1))-.5*(np.sqrt(np.sum((u-v)**2,axis=1))-d)
    first=np.sqrt(np.sum((x-y)**2,axis=1)).mean()
    return [(float(first+q.mean()),float(np.sqrt(np.var(q,ddof=1)/count))) for q in (correction,correction+increment)]


def review(paths,run,cfg,approval,guard,budget):
    gate=json.loads((run['provenance']/'pilot_gate.json').read_text())
    pre=json.loads((run['provenance']/'preflight.json').read_text())
    frozen=json.loads((run['provenance']/'calibration_freeze.json').read_text())
    coefficients={(r['pilot_position'],r['pool']):r for r in frozen['calibrations']}
    count=gate['levels'][-1]['energy_count']
    scores=inputs.read(run['results']/f'scores_{count}.parquet')
    indexed=scores.set_index(['pilot_position','model','replicate'])
    roster=inputs.read(run['results']/'roster.parquet');train,ledger=inputs.load(cfg)
    _,outer,_=inputs.role(cfg,'C_outer',train,ledger)
    checks=[]
    for role,subset in roster.groupby('role',sort=False):
        fit,query,target=inputs.role(cfg,role,train,ledger)
        fit_season,*_=reference_calendar(fit.origin_time_UTC)
        query_season,*_=reference_calendar(query.origin_time_UTC)
        for r in subset.itertuples(index=False):
            budget.check();q=query.iloc[r.query_position]
            assert query_season[r.query_position]==r.majority_season
            _,_,dist=GEOD.inv(np.full(len(fit),q.lon),np.full(len(fit),q.lat),fit.lon.to_numpy(),fit.lat.to_numpy())
            dist[(fit.lon.to_numpy()==q.lon)&(fit.lat.to_numpy()==q.lat)]=0.
            selections={pool:reference_selection(fit,dist,fit_season,s) for pool,s in [('Annual',None),('Seasonal',r.majority_season)]}
            fallback=len(selections['Seasonal'])==0
            if fallback:selections['Seasonal']=selections['Annual']
            with np.load(run['results']/f'lineage/{r.pilot_position:03d}.npz') as f:
                assert bool(f['fallback'])==fallback
                for pool,ix in selections.items():
                    np.testing.assert_array_equal(ix,f[pool.lower()+'_ix'])
                    np.testing.assert_allclose(dist[ix],f[pool.lower()+'_distance'],atol=1e-6,rtol=0)
            truth=target.iloc[r.query_position][['endpoint_lon','endpoint_lat']].to_numpy(float)
            for pool,ix in selections.items():
                used_pool='Annual' if pool=='Seasonal' and fallback else pool
                part=fit.iloc[ix];p=part[['endpoint_lon','endpoint_lat']].to_numpy();sd=part[['sd_e_km','sd_n_km']].to_numpy()
                base=('s4_e9',role,int(r.id),int(r.origin_source_obs),7,used_pool)
                cal=coefficients[(r.pilot_position,used_pool)]
                x=cartesian(p);g=rng((*base,'e9_es_control_calibration_v1'))
                i,j=g.integers(len(p),size=1024),g.integers(len(p),size=1024)
                d=np.sqrt(np.sum((x[i]-x[j])**2,axis=1));c=d*d
                b=float(np.cov(d,c,ddof=1)[0,1]/np.var(c,ddof=1)) if np.var(c,ddof=1)>0 else 0.
                mu=float(2*np.sum(np.var(x,axis=0)))
                np.testing.assert_allclose([b,mu],[cal['coefficient'],cal['mean_squared']],rtol=1e-12,atol=1e-9)
                for rep in [0,1]:
                    expected=reference_score(p,sd,truth,base,count,cal['coefficient'],cal['mean_squared'],rep)
                    for ci,kind in [(False,'ExactPoint'),(True,'EndpointCI')]:
                        row=indexed.loc[(r.pilot_position,pool+kind,rep)]
                        es,se=expected[int(ci)]
                        np.testing.assert_allclose([es,se],[row.energy_km,row.energy_mc_se],rtol=0,atol=1e-9)
                        if ci and part.ci_2d_usable.any():
                            cloud,weight,_=geometry.component_cloud(p,sd,part.ci_2d_usable.to_numpy(bool),16384,(*base,rep))
                        else:cloud,weight=p,np.full(len(p),1/len(p))
                        region=reference_region(cloud,weight,truth)
                        assert region['hit']==row.h90
                        np.testing.assert_allclose(region['area'],row.area90_km2,rtol=2e-10,atol=1e-8)
                        checks.append(dict(pilot_position=r.pilot_position,model=pool+kind,replicate=rep,
                            energy_abs_difference=abs(es-row.energy_km),se_abs_difference=abs(se-row.energy_mc_se),
                            area_abs_difference=abs(region['area']-row.area90_km2),hit_equal=True))
            if (r.pilot_position+1)%32==0:print('independent audit',r.pilot_position+1,'/128',flush=True)
    save_frame(paths,run['results']/'independent_checks.csv',pd.DataFrame(checks))
    outer_season,*_=reference_calendar(outer.origin_time_UTC)
    counts=outer.id.value_counts();weight=np.array([1/(outer.id.nunique()*counts[i]) for i in outer.id])
    verified=[]
    for level in gate['levels']:
        ec=level['energy_count'];frame=inputs.read(run['results']/f'scores_{ec}.parquet')
        for candidate,control in [('SeasonalExactPoint','AnnualExactPoint'),('SeasonalEndpointCI','AnnualEndpointCI')]:
            deltas=[];variances=[]
            for rep in [0,1]:
                a=frame[frame.model.eq(candidate)&frame.replicate.eq(rep)].sort_values('pilot_position')
                b=frame[frame.model.eq(control)&frame.replicate.eq(rep)].sort_values('pilot_position')
                v=a.energy_mc_se.to_numpy()**2+b.energy_mc_se.to_numpy()**2;v[a.seasonal_fallback.to_numpy()]=0.
                maximum={s:float(v[a.majority_season.to_numpy()==s].max()) for s in range(4)}
                projected=3*np.sqrt(sum(maximum[s]*np.square(weight[outer_season==s]).sum() for s in range(4)))
                threshold=float(b.groupby('id').energy_km.mean().mean())*.0001
                expected=level['projection'][candidate]['replicates'][rep]
                np.testing.assert_allclose([projected,threshold],[expected['three_se_km'],expected['threshold_km']],rtol=1e-12)
                diff=pd.DataFrame(dict(id=a.id,delta=a.energy_km.to_numpy()-b.energy_km.to_numpy()))
                deltas.append(float(diff.groupby('id').delta.mean().mean()))
                n=a.id.value_counts();w=np.array([1/(a.id.nunique()*n[i]) for i in a.id]);variances.append(float(np.sum(w*w*v)))
            z=level['projection'][candidate]
            np.testing.assert_allclose([abs(deltas[0]-deltas[1]),3*np.sqrt(sum(variances))],
                                      [z['seed_difference_km'],z['seed_limit_km']],rtol=1e-10,atol=1e-12)
        timing=pd.read_csv(run['results']/f'timings_{ec}.csv')
        tail=float(np.percentile(timing.total_seconds,95))
        components=[n for n in timing if n.endswith('_seconds') and n!='total_seconds']
        component_sum=sum(float(np.percentile(timing[n],95)) for n in components)
        estimate=(33971*max(tail,component_sum)+max(60.,pre['cold_seconds']))*1.1
        np.testing.assert_allclose(estimate,level['formal_projected_seconds'],rtol=1e-12)
        n=frame.sample_count.to_numpy();reconstructed=np.maximum(0,(frame.sample_sumsq-frame.sample_sum**2/n)/(n-1)/n)
        np.testing.assert_allclose(np.sqrt(reconstructed),frame.energy_mc_se,rtol=1e-9,atol=1e-10)
        verified.append(ec)
    assert not guard.outcomes_read and not guard.denied
    receipt=dict(independent_review_passed=True,queries=128,score_region_checks=len(checks),levels=verified,
        max_energy_abs_difference=max(r['energy_abs_difference'] for r in checks),
        max_area_abs_difference=max(r['area_abs_difference'] for r in checks),
        outer_targets_read=False,final_test_access=False,formal_started=False,
        full_roster_preflight_completed=False)
    save_json(paths,run['provenance']/'independent_review.json',receipt)
    make_report(paths,run,cfg,gate,pre,receipt,budget)


def make_report(paths,run,cfg,gate,pre,review,budget):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    last=gate['levels'][-1];count=last['energy_count']
    old=json.loads((inputs.ROOT/'provenance/runs'/cfg['parent_run']/'pilot_gate.json').read_text())
    old_by_count={r['energy_count']:r for r in old['levels']}
    baseline=pd.read_csv(run['results']/'preflight_timings.csv')
    old_tail=float(baseline.old_total_seconds.quantile(.95));reuse_tail=float(baseline.reuse_total_seconds.quantile(.95))
    speedup=old_tail/reuse_tail
    scores=inputs.read(run['results']/f'scores_{count}.parquet')
    rows=[]
    for name,g in scores[scores.replicate.eq(0)].groupby('model',sort=False):
        rows.append(dict(model=name,energy_km=float(g.groupby('id').energy_km.mean().mean()),
            h90=float(g.groupby('id').h90.mean().mean()),area90_km2=float(g.groupby('id').area90_km2.mean().mean()),
            median_variance_ratio=float(g.residual_variance_ratio.median())))
    save_frame(paths,run['results']/'pilot_summary.csv',pd.DataFrame(rows))
    timing=pd.read_csv(run['results']/f'timings_{count}.csv')
    components=[n for n in timing if n.endswith('_seconds') and n!='total_seconds']
    component_table=pd.DataFrame([dict(component=n,mean_seconds=float(timing[n].mean()),p95_seconds=float(timing[n].quantile(.95))) for n in components])
    save_frame(paths,run['results']/'component_profile.csv',component_table)
    folder=run['results']/'report';folder.mkdir()
    counts=[z['energy_count'] for z in gate['levels']]
    before=[1000*old_by_count[n]['energy_projection']['SeasonalEndpointCI']['three_se_km'] for n in counts]
    after=[1000*z['projection']['SeasonalEndpointCI']['three_se_km'] for z in gate['levels']]
    limits=[1000*z['projection']['SeasonalEndpointCI']['threshold_km'] for z in gate['levels']]
    times=[z['formal_projected_seconds']/60 for z in gate['levels']]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,ax=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    ax[0].plot(counts,before,'o--',color='#9a685a',label='Original numerical method (prior pilot)')
    ax[0].plot(counts,after,'o-',color='#237c80',label='Optimized: maximum of two replicates')
    ax[0].plot(counts,limits,':',color='#333333',label='Unchanged precision gate')
    ax[0].set(title='Seasonal CI minus annual CI: ES precision',ylabel='Projected aggregate 3 SE (metres)',ylim=(0,max(before)*1.12))
    ax[1].plot(counts,times,'o-',color='#237c80',label='Optimized formal projection')
    ax[1].plot(counts,[old_by_count[n]['formal_projected_seconds']/60 for n in counts],'o--',color='#9a685a',label='Prior method at same draw count')
    ax[1].axhline(60,color='#333333',linestyle=':',label='60 min: leaves required 2x reserve')
    ax[1].set(title='Projected formal cost: still provisional',ylabel='Minutes',ylim=(0,max(70,max(times)*1.15,max(old_by_count[n]['formal_projected_seconds']/60 for n in counts)*1.15)))
    for a in ax:
        a.set_xscale('log',base=2);a.set_xticks(counts,[f'{n:,}' for n in counts]);a.set_xlabel('ES pairs per query');a.grid(axis='y',alpha=.18);a.legend(fontsize=8,frameon=False)
    fig.suptitle('Step 4 E9 | Approved numerical optimization pilot',fontsize=15,fontweight='bold')
    fig.savefig(folder/'precision_runtime.png',dpi=160);fig.savefig(folder/'precision_runtime.svg');plt.close(fig)
    status='PILOT PRECHECK PASSED — FORMAL RUN NOT AUTHORIZED' if gate['pilot_precheck_passed'] else 'PILOT PRECHECK NOT PASSED — FORMAL RUN NOT STARTED'
    table='\n'.join(f"| {z['energy_count']:,} | {1000*z['projection']['SeasonalExactPoint']['three_se_km']:.3f} | {1000*z['projection']['SeasonalEndpointCI']['three_se_km']:.3f} | {z['formal_projected_seconds']/60:.2f} | {z['formal_projection_2x_seconds']/60:.2f} |" for z in gate['levels'])
    consumed=budget.prior+time.monotonic()-budget.start
    text=f'''# Step 4 E9 — ES optimization pilot

Status: **{status}**. Independent review passed on all 128 internal cases. No outer validation endpoint or final-test data was accessed.

## Numerical precision and runtime

| ES pairs/query | Point contrast 3 SE (m) | CI contrast 3 SE (m) | Formal projection (min) | Required 2x reserve (min) |
|---:|---:|---:|---:|---:|
{table}

The numerical precision gate remains 0.0001 times the reference annual mean, about {limits[-1]:.3f} m here. Values are conservative full-roster projections from the fixed internal pilot, not measured full-validation uncertainty or drifter position errors. Both independent seed checks are recorded in the gate receipt. The smallest passing precision level was {gate['selected_count']}; no draw beyond the registered ladder was used.

At 4,096 draws, the same-session p95 case time was {old_tail:.6f} s for the original computation and {reuse_tail:.6f} s for exact reuse: **{speedup:.2f}x**. These timings include the same measured search, lineage and packet I/O costs. Controlled integration changes numerical realizations, so the speedup compares the zero-control exact-reuse stage only. Historical higher-count runtimes are shown as context, not a same-session benchmark.

At the final level the total-case p95 is {last['p95_case_seconds']:.6f} s and the sum of component p95 costs is {last['component_p95_sum_seconds']:.6f} s. Projection uses the larger, charges cold work and actual output costs, and retains the original 10% allowance and 2x reserve. Independent full-roster support, storage and audit feasibility remain unmeasured; this is a provisional projection, not a formal go decision.

![Numerical precision and runtime](precision_runtime.png)

## Definition and audit

All four models, donors, votes, CI construction, seasonal rule, fallback rules, evaluation weights and region definitions remain unchanged. Every original ES draw stream is preserved; the 1,024-pair coefficient calibration uses a distinct outcome-free stream. All stored raw ES scores reconcile to the original pilot. Region/hit/area checks agree with the original forecast and independent replay.

{pre['tests']} semantic/regression tests passed. Independent review reconstructed all 128 neighbour sets by full WGS84 scans, checked UTC season labels, recomputed coefficients and both scoring replicates, replayed the four-arm regions, and reconstructed every aggregate uncertainty/time gate. Maximum independently reconstructed ES discrepancy: {review['max_energy_abs_difference']:.3g} km. The control-variate coefficient affects integration only; it is not a prediction weight.

## Budget and next gate

New execution through report generation: approximately {consumed:.2f} s; prior pilot: {cfg['previous_pilot_seconds']:.2f} s. Final exact totals are in review_resources.json. Caps remain 420 new seconds and 600 cumulative pilot seconds. No formal experiment was started or scheduled.

Return this pilot to the user. A later formal decision requires full-roster outcome-blind support/storage/audit preflight and a frozen forecast definition before endpoint access. No extra optimization search, resampling level, model change or automatic continuation is authorized.

Files: ../pilot_summary.csv (internal pilot values only), ../component_profile.csv, ../independent_checks.csv, all per-level scores/timings and the provenance gate/resource/approval receipts. Run: {run['results'].name}.
'''
    paths.publish(folder/'REPORT.md',lambda f:f.write(text.encode()))
    image64=base64.b64encode((folder/'precision_runtime.png').read_bytes()).decode()
    summary_table=pd.DataFrame(rows).to_html(index=False,float_format=lambda x:f'{x:,.6f}',border=0)
    levels_table=pd.DataFrame([dict(pairs=z['energy_count'],point_3SE_m=1000*z['projection']['SeasonalExactPoint']['three_se_km'],
        CI_3SE_m=1000*z['projection']['SeasonalEndpointCI']['three_se_km'],formal_minutes=z['formal_projected_seconds']/60,
        reserved_minutes=z['formal_projection_2x_seconds']/60) for z in gate['levels']]).to_html(index=False,float_format=lambda x:f'{x:,.3f}',border=0)
    page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E9 ES optimization pilot</title>
<style>body{{font:16px/1.6 system-ui;color:#243642;background:#f4f6f7;margin:0}}main{{max-width:1100px;padding:32px 18px;margin:auto}}h1{{line-height:1.25}}.card{{background:white;border:1px solid #d8e0e5;padding:20px;margin:20px 0;border-radius:8px}}.status{{font-size:13px;font-weight:bold;color:#70532e}}img{{max-width:100%;height:auto}}table{{border-collapse:collapse;font-size:13px;width:100%}}td,th{{padding:10px;text-align:right;white-space:nowrap;border-bottom:1px solid #e0e5e8}}td:first-child,th:first-child{{text-align:left}}.scroll{{overflow:auto}}a{{color:#216c86}}</style>
<main><p class="status">{status}</p><h1>ES precision and computation reuse</h1><p>The four probability models are unchanged. This page reports a bounded engineering pilot, not full validation performance.</p>
<div class="card"><strong>Same-session exact-reuse speedup: {speedup:.2f}x at 4,096 draws.</strong><p>Final level: {count:,} draws. Projected formal processing: {last['formal_projected_seconds']/60:.1f} minutes; {last['formal_projection_2x_seconds']/60:.1f} minutes with the required reserve. Full-roster preflight remains outstanding.</p></div>
<div class="card"><img alt="Original and optimized numerical uncertainty and projected runtime at every completed draw count" src="data:image/png;base64,{image64}"><div class="scroll">{levels_table}</div></div>
<p>The 3-SE numbers extrapolate internal numerical variance using season maxima and full-query weights. They are not geographic forecast errors. The precision threshold is about {limits[-1]:.3f} m. Both independent replicates must pass; no favorable seed is selected.</p>
<h2>Independent review</h2><p>{pre['tests']} tests passed. All 128 support selections and both numerical replicates were reconstructed independently. Raw score parity, unchanged regions, hits, areas and fallbacks were checked. No outer outcomes or locked final-test data were read.</p>
<h2>Internal pilot values only</h2><p>128 fixed internal cases, equal evaluation weight per ID. This table cannot decide seasonal benefit.</p><div class="card scroll">{summary_table}</div>
<h2>Next step</h2><p>Stop here for the user's review. The complete experiment has not started. Full-roster support, storage and audit feasibility must be confirmed before a later execution decision.</p>
<p><a href="REPORT.md">Detailed report</a> · <a href="../component_profile.csv">Component timings</a> · <a href="../independent_checks.csv">Independent checks</a> · <a href="../pilot_summary.csv">Pilot values</a> · <a href="precision_runtime.svg">Vector figure</a></p><small>Run: {run['results'].name}</small></main></html>'''
    paths.publish(folder/'review.html',lambda f:f.write(page.encode()))
    save_json(paths,run['provenance']/'report_receipt.json',dict(formal_started=False,review_passed=True,
        report_sha256={str(p.relative_to(inputs.ROOT)):file_sha256(p) for p in folder.iterdir()}))
