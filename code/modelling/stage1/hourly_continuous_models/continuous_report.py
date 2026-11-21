"""Matched development comparison and source-backed continuous-model figures."""
import argparse
import json
import platform
import sys
import zipfile
import subprocess
from importlib.metadata import version
from datetime import datetime,timezone
from html import escape
import numpy as np
import pandas as pd
import shapely as sh
from shapely.geometry import box,shape
from data3001.paths import project_paths,file_sha256
from data3001.modelling.continuous_models.continuous import particle_brier
from data3001.modelling.continuous_models.continuous_inputs import PARENT
from data3001.modelling.common.markov_position_scores import ensemble_scores
from data3001.modelling.common.plotting import map_svg, _rings, markdown_table
from data3001.modelling.common.runtime import verified_run, _seal
from data3001.modelling.common.runtime import save_frame, save_json


def region_info(law,truth,areas):
    u=law.get(-3,0.);p={k:v for k,v in law.items() if k!=-3}
    if 1-u<.9-1e-12:return False,False,np.nan,np.nan,np.nan
    ranked=sorted(p.values(),reverse=True);i=min(np.searchsorted(np.cumsum(ranked),.9-1e-12),len(ranked)-1)
    chosen={k:v for k,v in p.items() if v>=ranked[i]-1e-15}
    return True,truth in chosen,sum(k>=0 for k in chosen),sum(areas.get(k,0) for k in chosen if k>=0),sum(chosen.values())


def diagnostics(draws,table,areas):
    scored=ensemble_scores(draws,table.destination_cell_1.to_numpy())
    if not np.allclose(scored.S_integration,table.S):raise ValueError('Stored scores/draws differ')
    area=[]
    for row,y in zip(draws,table.destination_cell_1):
        k,n=np.unique(row,return_counts=True)
        area.append(region_info(dict(zip(map(int,k),n/len(row))),int(y),areas)[3])
    scored['area90_km2']=area
    scored['id']=table.id.to_numpy();scored['origin']=table.origin.to_numpy()
    return scored


def baseline(train,query,areas):
    laws={int(c):g.destination_cell_1.value_counts(normalize=True).to_dict() for c,g in train.groupby('origin_cell_1')}
    rows=[]
    for r in query.itertuples():
        p=laws.get(int(r.origin_cell_1),{-3:1.});u=p.get(-3,0.)
        available,hit,size,area,mass=region_info(p,int(r.destination_cell_1),areas)
        rows.append({'id':int(r.id),'origin':int(r.origin),'S_integration':1-2*p.get(int(r.destination_cell_1),0)+sum(v*v for v in p.values()),
            'S_issued':1-2*p.get(int(r.destination_cell_1),0)+sum(v*v for v in p.values()),
            'U_mass':u,'E_mass':p.get(-2,0),'sampled_zero':p.get(int(r.destination_cell_1),0)==0,
            'region90_available':available,'region90_hit':hit,'region90_cells':size,
            'region90_mass':mass,'area90_km2':area})
    return laws,pd.DataFrame(rows)


def bootstrap(a,b,replicates=1000):
    if not np.array_equal(a[['id','origin']],b[['id','origin']]):raise ValueError('Unmatched held queries')
    d=pd.DataFrame({'id':a.id,'delta':a.S_integration-b.S_integration}).groupby('id').agg(total=('delta','sum'),n=('delta','size'))
    rng=np.random.default_rng(20261029);ix=rng.integers(0,len(d),(replicates,len(d)))
    v=d.total.to_numpy()[ix].sum(1)/d.n.to_numpy()[ix].sum(1)
    lo,hi=np.quantile(v,[.025,.975])
    return {'delta_S':float(d.total.sum()/d.n.sum()),'lower95':float(lo),'upper95':float(hi),'independent_IDs':len(d)}


def plot_maps(path,panels,land,release,cell,h):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib.patches import Polygon,Rectangle
    from matplotlib.colors import Normalize
    from matplotlib.ticker import PercentFormatter
    maximum=max([v for _,p in panels for k,v in p.items() if k>=0] or [1.])
    norm=Normalize(0,maximum);fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    for ax,(label,p) in zip(axes.flat,panels):
        polys=[];colors=[]
        for k,v in p.items():
            if k<0:continue
            x=k%360-180;y=k//360-90
            polys.append([(x,y),(x+1,y),(x+1,y+1),(x,y+1)])
            colors.append(v)
        m=PolyCollection(polys,array=np.asarray(colors),norm=norm,cmap='magma_r',edgecolors='none')
        ax.add_collection(m)
        for ring in _rings(land):ax.add_patch(Polygon(ring,facecolor='#d9dedf',edgecolor='#647178',linewidth=.3))
        for ring in _rings(release):ax.plot(*np.asarray(ring).T,color='#11875d',lw=1)
        ax.add_patch(Rectangle((-81,20),73,35,fill=False,ec='#416e9a',lw=.8,ls='--'))
        x=cell%360-180;y=cell//360-90;ax.add_patch(Rectangle((x,y),1,1,fill=False,ec='#00a86b',lw=1.6))
        ax.set(xlim=(-83,-6),ylim=(19,56),xlabel='Longitude (degrees)',ylabel='Latitude (degrees)')
        ax.set_title(label,fontsize=12,loc='left');ax.set_aspect(1/np.cos(np.deg2rad(37.5)))
        ax.text(.01,.02,f"Outside D: {100*p.get(-2,0):.1f}% | unresolved: {100*p.get(-3,0):.1f}%",transform=ax.transAxes,fontsize=8,bbox={'facecolor':'white','alpha':.85,'edgecolor':'none'})
    fig.colorbar(m,ax=axes,label='Probability per 1-degree cell (same scale in all panels)',shrink=.8,format=PercentFormatter(1))
    fig.suptitle(f'{h}-day outcomes | release cell {cell} | matched historical validation cohort',fontsize=15)
    fig.savefig(path,dpi=160);plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    paths=project_paths();receipt=verified_run(paths,args.run);root=paths.root/'results/runs'/args.run
    cfg=json.loads((receipt.parent/'run.json').read_text())['config']
    if cfg['benchmark']:raise ValueError('Cannot publish resource pilot as model result')
    for relative,checksum in cfg['input_sha256'].items():
        if file_sha256(paths.root/relative)!=checksum:
            raise ValueError('Current report input differs from frozen run: '+relative)
    name=datetime.now(timezone.utc).strftime('continuous_report_%Y%m%dT%H%M%S_%fZ')
    run=paths.create_run(name,{'model_run':args.run,'receipt_sha256':file_sha256(receipt),'final_test_access':False})
    # Capture source, not just hashes, so this uncommitted research run can be
    # reconstructed after subsequent repository edits. No trajectory is copied.
    def snapshot(stream):
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
            files=list((paths.root/'src/data3001').rglob('*.py'))+[
                paths.root/'configs/continuous_hourly.json',paths.root/'pyproject.toml',
                paths.root/'tests/test_modelling_continuous.py']
            for f in sorted(files):z.writestr(str(f.relative_to(paths.root)),f.read_bytes())
    paths.publish(run['provenance']/'source_snapshot.zip',snapshot)
    save_json(paths,run['provenance']/'environment.json',{'python':sys.version,'platform':platform.platform(),
        'packages':{name:version(name) for name in ['torch','numpy','pandas','scipy','pyarrow','pyproj','shapely','matplotlib']},
        'device':'CPU','threads':cfg['cpu_threads'],'precision':'float32; source chart target construction float64',
        'cross_platform_bitwise_identity_guaranteed':False})
    choices=pd.read_csv(root/'selected_parameters.csv');roles=pd.read_csv(root/'roles.csv')
    choices['gamma']=choices.candidate.map({x['name']:x['l2'] for x in cfg['candidates']})
    choices['components']=choices.candidate.map({x['name']:x['components'] for x in cfg['candidates']})
    hour_support=pd.read_csv(paths.root/'results/runs'/cfg['input_run']/'ID_support.csv')
    contributing=hour_support.groupby('historical_split').agg(assigned_IDs=('id','size'),
        contributing_hourly_IDs=('pairs',lambda s:int(s.gt(0).sum())),hourly_pairs=('pairs','sum')).reset_index()
    save_frame(paths,run['results']/'hourly_training_support.csv',contributing)
    likelihood=[]
    for fold in range(cfg['cv_folds']):
        for c in cfg['candidates']:
            record=json.loads((root/f"cv{fold}_{c['name']}.json").read_text())
            epoch=record['logs'][record['best_epoch']-1]
            likelihood.append({'fold':fold,'candidate':c['name'],'pairs':record['held_pairs'],
                'selected_epoch':record['best_epoch'],'joint_NLL':epoch['held_joint_NLL'],
                'position_NLL':epoch['held_position_NLL']})
    save_frame(paths,run['results']/'one_hour_CV_likelihood.csv',pd.DataFrame(likelihood))
    train_ids=set(roles.loc[roles.role.eq('train_CV'),'id']);held_ids=set(roles.loc[roles.role.eq('historical_validation'),'id'])
    rel=pd.read_parquet(paths.root/'results/runs'/PARENT/'releases.parquet');rel=rel.loc[rel.reason_code.eq(0)]
    train=rel.loc[rel.id.isin(train_ids)];held=rel.loc[rel.id.isin(held_ids)]
    idx=pd.read_parquet(paths.asset('state_index',verify=True));idx=idx.loc[idx.resolution.eq(1)]
    areas=idx.set_index('cell').wet_area_in_D.to_dict()
    rank=train.loc[train.horizon_days.eq(7)].groupby('origin_cell_1').agg(ids=('id','nunique'),pairs=('id','size')).reset_index().sort_values(['ids','pairs','origin_cell_1'],ascending=[False,False,True])
    example=int(rank.iloc[0].origin_cell_1)
    save_json(paths,run['results']/'example_definition.json',{'cell':example,'selection':'most independent historical training IDs at 7d, ties by pair count then cell','no_validation_outcome_selection':True})
    land=sh.from_wkb(paths.asset('land_mask_intermediate',verify=True).read_bytes()).intersection(box(-83,19,-6,56)).simplify(.05,preserve_topology=True)
    region=shape(json.loads(paths.asset('release_R',verify=True).read_text())['features'][0]['geometry'])
    summaries=[];intervals=[];mc=[];svgs={};model_scores=[];cohort_rows=[]
    for h in (7,30):
        query=held.loc[held.horizon_days.eq(h)].sort_values('origin').reset_index(drop=True)
        laws,b2=baseline(train.loc[train.horizon_days.eq(h)],query,areas)
        save_json(paths,run['results']/f'B2_stopped_laws_{h}d.json',
                  {str(c):{str(k):float(v) for k,v in law.items()} for c,law in laws.items()})
        diagnostics_by_model={'B2 matched stopped control':b2};arrays={};panels={}
        for family in ('G','MDN3'):
            choice=choices.loc[choices.family.eq(family)&choices.horizon_days.eq(h)].iloc[0]
            prefix=root/('refit_'+choice.candidate+'_validation')
            t=pd.read_parquet(prefix.with_suffix('.parquet'));t=t.loc[t.horizon_days.eq(h)].reset_index(drop=True)
            if not np.array_equal(t[['id','origin','destination_cell_1']],query[['id','origin','destination_cell_1']]):
                raise ValueError('Forecast/observed case mismatch')
            a=np.load(str(prefix)+f'_{h}d.npy');arrays[family]=a
            scored=diagnostics(a,t,areas);diagnostics_by_model[family]=scored
            half=a.shape[1]//2
            mc.append({'model':family,'horizon_days':h,'first_half_S':float(particle_brier(a[:,:half],query.destination_cell_1).mean()),
                       'second_half_S':float(particle_brier(a[:,half:],query.destination_cell_1).mean()),'half_particles':half})
        for model,d in diagnostics_by_model.items():
            row={'horizon_days':h,'model':model,'pairs':len(d),'IDs':d.id.nunique(),'S':float(d.S_integration.mean()),
                'issued_S':float(d.S_issued.mean()),'region90_hit_pct':100*float(d.region90_hit.mean()),
                'region90_available_pct':100*float(d.region90_available.mean()),'region90_mean_mass_pct':100*float(d.region90_mass.mean()),
                'region90_mean_cells':float(d.region90_cells.mean()),'region90_mean_wet_km2':float(d.area90_km2.mean()),
                'U_mass_pct':100*float(d.U_mass.mean()),'E_mass_pct':100*float(d.E_mass.mean()),
                'sampled_zero_pct':100*float(d.sampled_zero.mean()),
                'observed_E_pct':100*float(query.destination_cell_1.eq(-2).mean())}
            summaries.append(row);model_scores.append(d.assign(model=model,horizon_days=h))
        common_region=np.logical_and.reduce([d.region90_available.to_numpy() for d in diagnostics_by_model.values()])
        for model,d in diagnostics_by_model.items():
            row=next(x for x in summaries if x['horizon_days']==h and x['model']==model)
            row.update(region90_common_pairs=int(common_region.sum()),
                       region90_common_wet_km2=float(d.loc[common_region,'area90_km2'].mean()),
                       region90_common_hit_pct=100*float(d.loc[common_region,'region90_hit'].mean()))
        for other in ('G','B2 matched stopped control'):
            intervals.append({'horizon_days':h,'comparison':'MDN3 minus '+other,**bootstrap(diagnostics_by_model['MDN3'],diagnostics_by_model[other])})
        common=(diagnostics_by_model['G'].U_mass.eq(0)&diagnostics_by_model['MDN3'].U_mass.eq(0)&query.destination_cell_1.ge(0))
        for family in ('G','MDN3'):
            d=diagnostics_by_model[family];ok=common & d.energy_km_issued.notna()
            row=next(x for x in summaries if x['horizon_days']==h and x['model']==family)
            row.update(common_spatial_pairs=int(ok.sum()),energy_km_common=float(d.loc[ok,'energy_km_issued'].mean()),
                       squared_mean_km2_common=float(d.loc[ok,'mean_squared_km2_issued'].mean()))
        for cell in sorted(set(query.origin_cell_1)):
            mask=query.origin_cell_1.eq(cell).to_numpy();q=query.loc[mask]
            display=[('B2 matched stopped control',laws.get(int(cell),{-3:1.}))]
            for family,label in [('G','Conditional Gaussian'),('MDN3','Three-component MDN')]:
                k,n=np.unique(arrays[family][mask],return_counts=True);display.append((label,dict(zip(map(int,k),n/n.sum()))))
            display.append((f'Observed: {len(q):,} pairs / {q.id.nunique()} IDs',q.destination_cell_1.value_counts(normalize=True).to_dict()))
            for label,law in display[:3]:
                available,_,size,area,mass=region_info(law,int(q.destination_cell_1.iloc[0]),areas)
                keys={k:v for k,v in law.items() if k!=-3}
                covered=set()
                if available:
                    v=sorted(keys.values(),reverse=True);cut=v[min(np.searchsorted(np.cumsum(v),.9-1e-12),len(v)-1)]
                    covered={k for k,value in keys.items() if value>=cut-1e-15}
                name={'Conditional Gaussian':'G','Three-component MDN':'MDN3'}.get(label,label)
                cohort_rows.append({'horizon_days':h,'model':name,'origin_cell_1':int(cell),
                    'pairs':len(q),'IDs':q.id.nunique(),'region_available':available,
                    'hit_pairs':int(q.destination_cell_1.isin(covered).sum()),
                    'region_mass':mass,'region_wet_km2':area,'particles_per_cohort':len(q)*cfg['validation_particles'] if name!='B2 matched stopped control' else 0})
            svg=map_svg([(name,{k:v for k,v in law.items() if k!=-3},law.get(-3,0)) for name,law in display],_rings(land),_rings(region),int(cell),h,0)
            svg=svg.replace('outer held-out fold 0','historical validation').replace('pooled stopped target','hourly continuous comparison')
            borders=[]
            for panel in range(4):
                left=45+(panel%2)*590;top=100+(panel//2)*340
                borders.append(f'<rect x="{left+2/77*540:.3f}" y="{top+1/37*260:.3f}" width="{73/77*540:.3f}" height="{35/37*260:.3f}" fill="none" stroke="#416e9a" stroke-dasharray="4,4"/>')
            svg=svg.replace('</g></svg>',''.join(borders)+'</g></svg>').replace('Equirectangular display;','Dashed blue: transport domain D. Equirectangular display;')
            # Keep the HTML small and load only the selected view. Embedding all
            # repeated coastline SVGs made the previous page about 75 MB.
            chart_dir=run['results']/'charts'
            chart_dir.mkdir(exist_ok=True)
            chart_name=f'{h}_{int(cell)}.svg'
            paths.publish(chart_dir/chart_name,lambda f,svg=svg:f.write(svg.encode()))
            svgs[f'{h}_{int(cell)}']='charts/'+chart_name
            if cell==example:plot_maps(run['results']/f'probability_{h}d.png',display,land,region,int(cell),h)
    table=pd.DataFrame(summaries);interval=pd.DataFrame(intervals)
    cohorts=pd.DataFrame(cohort_rows);save_frame(paths,run['results']/'cohort_region_diagnostics.csv',cohorts)
    for row in summaries:
        q=cohorts.loc[cohorts.model.eq(row['model'])&cohorts.horizon_days.eq(row['horizon_days'])]
        row['cohort90_hit_pct']=100*float(q.hit_pairs.sum()/q.pairs.sum())
        row['cohort90_available_pct']=100*float(q.loc[q.region_available,'pairs'].sum()/q.pairs.sum())
    table=pd.DataFrame(summaries)
    findings=[]
    for h in (7,30):
        a=table.loc[table.horizon_days.eq(h)].set_index('model')
        findings.append(f"At {h} days, S is {a.loc['G','S']:.6f} for Gaussian, "
            f"{a.loc['MDN3','S']:.6f} for MDN and {a.loc['B2 matched stopped control','S']:.6f} "
            f"for matched B2. The lowest point estimate on this cohort is {a.S.idxmin()}. "
            "Read the whole-ID intervals before asserting a stable difference.")
    save_frame(paths,run['results']/'summary.csv',table);save_frame(paths,run['results']/'paired_ID_intervals.csv',interval)
    save_frame(paths,run['results']/'MC_half_diagnostics.csv',pd.DataFrame(mc))
    save_frame(paths,run['results']/'per_origin_diagnostics.parquet',pd.concat(model_scores,ignore_index=True))
    # These split-ensemble ranks diagnose numerical instability; they do not
    # change the frozen full-ensemble selection or use validation to retune it.
    cvmc=[]
    for k in range(cfg['cv_folds']):
        for candidate in cfg['candidates']:
            prefix=root/f"cv{k}_{candidate['name']}_scores";t=pd.read_parquet(prefix.with_suffix('.parquet'))
            for h in (7,30):
                q=t.loc[t.horizon_days.eq(h)];a=np.load(str(prefix)+f'_{h}d.npy');m=a.shape[1]//2
                for half,d in enumerate((a[:,:m],a[:,m:])):
                    cvmc.append({'fold':k,'candidate':candidate['name'],'horizon_days':h,'half':half,'pairs':len(q),
                                 'S_sum':float(particle_brier(d,q.destination_cell_1).sum())})
    cc=pd.DataFrame(cvmc).groupby(['candidate','horizon_days','half'],as_index=False)[['pairs','S_sum']].sum();cc['S']=cc.S_sum/cc.pairs
    save_frame(paths,run['results']/'CV_MC_half_diagnostics.csv',cc)
    stability=[]
    for row in choices.itertuples():
        picked=[]
        for half in (0,1):
            a=cc.loc[cc.candidate.str.startswith(row.family+'_')&cc.horizon_days.eq(row.horizon_days)&cc.half.eq(half)]
            picked.append(str(a.sort_values(['S','candidate']).iloc[0].candidate))
        stability.append({'family':row.family,'horizon_days':row.horizon_days,'full_pick':row.candidate,
                          'half0_pick':picked[0],'half1_pick':picked[1],
                          'rank_stable':picked[0]==picked[1]==row.candidate})
    stability=pd.DataFrame(stability)
    save_frame(paths,run['results']/'parameter_rank_stability.csv',stability)
    budget=pd.read_csv(root/'fit_budget.csv')
    text=f'''# Continuous hourly transport: first development comparison

Source run: `{args.run}`. Fixed 1-hour transition, 168/720 free-running steps;
annual pooled, inputs lon/lat/ve/vn only. No final-test access, no source edits,
no grounding/seasonal/365-day or arbitrary-object claim. This is a bounded first
experiment, not evidence of globally optimal parameters or step length.

## Model and selection

In a fixed invertible chart, learn the joint four-dimensional residual
`r = (x_next - x - 3600 J(x)v, v_next - v)` given current position and velocity.
`q(r|s) = sum_k pi_k(s) Normal_4(mu_k(s), L_k L_k^T + 0.03^2 I)` in fit-standardized units.
K=1 is the Gaussian control; K=3 is MDN. Two tanh layers of width 32 predict
continuous conditional parameters. No future observed velocity is fed into a
rollout. The velocity distribution is carried jointly with displacement.

Unlike the earlier cell tables, this network learns a function of exact location
and continuous velocity. Two releases in the same cell can receive different
next-hour distributions. Repeated samples give a distribution of trajectories;
only their displayed outcomes are binned to the 1-degree grid. At inference the
starting velocity must be supplied; location-only initialization is not part of
this implementation. Mixture components are statistical components, not named
ocean currents or persistent physical regimes.

Minimize equal-pair negative log likelihood plus gamma times squared weights.
Gamma candidates 0 and 0.0001 are evaluated in both families. Three whole-ID folds
inside 2,674 historical training IDs select checkpoints by held joint NLL and
gamma by free-rollout S separately for 7/30d. Scaling is fit-only. Final candidates
are refitted on all 2,674 training IDs for the median chosen CV epoch count.
Of those assigned training IDs, 2,100 contribute eligible one-hour D transitions
(20,609,216 pairs); the others have no qualified D pair and do not enter the loss.
The comparison uses the separate 550 historical validation IDs, of which only
eligible R visitors contribute outcomes. These validation IDs were used earlier
in project development: this is not pristine confirmatory or final-test evidence.
CV scores also include epoch/parameter selection and are tuning evidence.

{markdown_table(choices,list(choices.columns))}

{int(budget.epoch_cap_reached.sum())}/{len(budget)} CV fits reached the eight-epoch
ceiling. Inspect per-epoch histories before claiming convergence; computational
budget and fixed small capacity limit the conclusion.

## Matched outcomes

{' '.join(findings)}

{markdown_table(table,['horizon_days','model','pairs','IDs','S','cohort90_hit_pct','cohort90_available_pct','U_mass_pct','E_mass_pct'])}

The main percentage above is a **release-cell cohort** diagnostic: average the
conditional forecasts over the matching initial coordinates/velocities in each
release cell, form its 90% set without seeing outcomes, then count that cohort's
observed hits. This uses many more than 32 particles per cohort, matching the maps.
It does not measure calibration of individual velocity-conditioned forecasts.
Unavailable cohort regions count as no hit. Small cohorts remain less reliable.
Individual 32-particle region diagnostics are retained separately in summary.csv;
their sparse numerical support must not be mistaken for the full model's support.

Lower S is better. It is a quadratic probability score, not percentage accuracy.
Unresolved U and first-exit E retain their mass. Land/nonfinite simulations become
U, not diagnosed grounding. Missing observed follow-up is not treated as exit.
B2 is re-fitted on the SAME stopped targets and training IDs; old endpoint-only
baseline scores are not copied into this table. Continuous models additionally
use D-origin transitions, whereas B2 uses direct R-origin 7/30-day pairs.
Neither held-out horizon contains an observed exit. Predicted exit mass remains
in the score, but sensitivity to true exits is not established by this cohort.

The 90% region hit rate means the fraction of eligible observed outcomes in the
issued nominal-90% set. Ties increase actual issued mass; read the mass/area columns
in summary.csv. Unavailable regions count as no hit in the all-case hit rate.
The common-available-region columns in the CSV compare area on identical cases;
the ordinary mean area uses each model's available sets and may use different cases.
32-particle regions are coarse numerical approximations, not precise limiting-law
calibration. Sampled zero is not a structural zero of an MDN density. Geographic
energy/squared-mean diagnostics use the common available in-D subset only; no
coordinate is invented for E or U. These are auxiliary, not the NLL training loss.

## Uncertainty and numerical audit

{markdown_table(interval,list(interval.columns))}

Intervals resample whole validation IDs 1,000 times with frozen fits, retaining
equal-pair weighting. They exclude refitting and researcher adaptation. Nearby
hourly releases overlap; they are not independent instruments. Whole-ID isolation
does not establish spatial or temporal independence, or future-year skill. The S integration
uses collision counts to remove the finite-particle bias of squared probabilities.
`MC_half_diagnostics.csv` and `CV_MC_half_diagnostics.csv` compare independent
particle halves. Two halves are a sensitivity check, not a precise MC confidence
interval. No tuning decision is revised using historical validation scores.

{markdown_table(stability,list(stability.columns))}

A ranking that changes between particle halves is not a numerically resolved
optimum. The full-ensemble choice is retained as specified, with this uncertainty
visible. In particular, a tiny gamma difference must not be described as a robust
improvement or confused with evidence that the entire model family is superior.

## Reading the maps

The default release cell {example} was chosen by the largest independent-ID
support in historical TRAINING data (ties: pair count, then cell). Each forecast
uses the corresponding validation release's exact coordinates and velocity; the
panels average these conditional forecasts over the SAME cohort as observed.
This is not a single arbitrary release-point forecast. Every panel in each view
uses the same displayed probability scale; changing cell may change that scale.
Probability per cell is not probability density. E/U are displayed separately;
surviving geographic probabilities are never renormalized to 100%.
The network can issue a density in an unobserved or sparsely observed state;
numerical forecast availability is not evidence that such extrapolation is
accurate. Unlike the empirical table, a missing fitting cell does not itself
create U. U here records geometric/nonfinite simulation failure.

![7-day matched probabilities](probability_7d.png)

![30-day matched probabilities](probability_30d.png)

## Scope and reproducibility

Canonical data and the locked test are unchanged. The hourly cache retains source
indices and exact timestamps. One unmapped outside endpoint found in the resource
pilot was excluded before formal training to match the existing geometry rules;
the final cache has 25,208,045 eligible pairs, including 2,001 observed exits.
Hourly data are processed historical GDP estimates; interpolation-derived velocity
may reflect observations on both sides of a time stamp; see
[Elipot et al. (2016)](https://repository.library.noaa.gov/view/noaa/20401/noaa_20401_DS1.pdf).
No real-time readiness is
claimed. One-hour observed/generated exits do not resolve unobserved subhour exits.

Use the saved `.pt` checkpoints with `load_model` and `rollout` in
`data3001.modelling.continuous_models.run_continuous`; the run config records seeds, optimizer,
scalers, complete ID roles and input/source hashes. No test labels are needed.

Literature precedent: [Brolly (2023)](https://doi.org/10.1029/2023MS003718) uses an
MDN for oceanic transition densities. This experiment extends the target to joint
position/velocity increments; the paper does not validate this extension or our
dataset-specific results. [Gneiting and Raftery (2007)](https://doi.org/10.1198/016214506000001437)
provides the proper-score context. No claim that a neural model must outperform
the empirical baseline follows from either source.
'''
    paths.publish(run['results']/'REPORT.md',lambda f:f.write(text.encode()))
    cells=sorted({int(k.split('_')[1]) for k in svgs})
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Hourly continuous transport</title>
<style>body{font:16px system-ui;color:#193047;background:#f5f7fa;max-width:1250px;margin:30px auto;padding:20px}h1{font-size:30px}p{line-height:1.6}section{background:white;border:1px solid #d8e1ea;border-radius:12px;padding:20px;margin:20px 0}select{padding:8px;margin:8px}table{border-collapse:collapse;font-size:13px;width:100%}td,th{padding:9px;border-bottom:1px solid #ddd;text-align:right}th{background:#eaf1f6}svg{max-width:100%;height:auto}.scroll{overflow:auto}.tag{color:#975100;font-weight:600}</style>
<h1>Continuous hourly transport</h1><p class="tag">Historical development validation · fixed 1-hour model · final test locked</p>
<p>Compare the conditional Gaussian, MDN and a matched B2 control. The forecast starts with exact longitude, latitude and velocity, then generates its own hourly positions and velocities. Exit is absorbing; unresolved mass is visible.</p>
<section><h2>Matched outcome distributions</h2><label>Horizon <select id="h"><option value="7">7 days / 168 steps</option><option value="30">30 days / 720 steps</option></select></label><label>Release cell <select id="c">'''
    html+=''.join(f'<option value="{cell}"'+(' selected' if cell==example else '')+f'>{cell}: {cell%360-180} to {cell%360-179}° lon, {cell//360-90} to {cell//360-89}° lat</option>' for cell in cells)
    html+='''</select></label><div id="map"></div><p>Same scale within a view. Forecasts and observations use matching validation releases. Forecasts are cohort averages, not a single point. E and U remain in the denominator.</p></section><section><h2>All eligible validation releases</h2><p>Lower S is better; it is not a percentage. Cohort coverage averages forecasts within each release cell, forms its 90% set, then checks matching observed endpoints. This measures the displayed cohort distribution, not individual-forecast calibration. Individual 32-particle footprints are too coarse for precise coverage conclusions; they remain labelled numerical diagnostics in the CSV.</p><div class="scroll">'''
    visible=table[['horizon_days','model','S','cohort90_hit_pct','cohort90_available_pct','U_mass_pct','pairs','IDs']].rename(columns={
        'horizon_days':'Days','model':'Model','cohort90_hit_pct':'Cohort 90% hit %','cohort90_available_pct':'Cohort 90% set available %',
        'U_mass_pct':'Unresolved mass %','pairs':'Pairs'})
    html+=visible.to_html(index=False,float_format=lambda x:f'{x:.4g}')+'</div></section>'
    html+='<p><a href="REPORT.md">Full audit and method</a> · <a href="summary.csv">Summary CSV</a> · <a href="paired_ID_intervals.csv">Whole-ID intervals</a></p>'
    html+='<script>const charts='+json.dumps(svgs)+';function render(){const h=document.getElementById("h").value,c=document.getElementById("c").value,src=charts[h+"_"+c],host=document.getElementById("map");host.replaceChildren();if(!src){host.textContent="No eligible cohort for this selection.";return;}const img=document.createElement("img");img.src=src;img.alt=h+"-day matched outcome distributions for release cell "+c;img.style.width="100%";host.appendChild(img);}document.getElementById("h").onchange=render;document.getElementById("c").onchange=render;render();</script></html>'
    paths.publish(run['results']/'review.html',lambda f:f.write(html.encode()))
    checked=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests',
                            '-p','test_modelling_continuous.py','-v'],cwd=paths.root,
                           capture_output=True,text=True,check=True)
    paths.publish(run['provenance']/'mathematical_tests.txt',lambda f:f.write((checked.stdout+checked.stderr).encode()))
    _seal(paths,run,{'model_run':args.run,'final_test_access':False,'matched_queries':True,
                   'mathematical_tests_passed':True,'source_receipt_sha256':file_sha256(receipt)})
    print(table.to_string(index=False));print('REPORT_RUN='+run['results'].name,flush=True)


if __name__=='__main__':main()
