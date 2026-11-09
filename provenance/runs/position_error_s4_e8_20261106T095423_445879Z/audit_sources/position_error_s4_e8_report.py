"""Source-backed English figures and local review for the approved E8 run."""
import argparse
import html
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import shapely as sh
from shapely.geometry import box

from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_frame,save_json
from data3001.modelling.baselines import position_error_s4_e8 as model
from data3001.modelling.baselines import position_error_s4_e8_inputs as inputs
from data3001.modelling.baselines import position_error_s4_e8_pipeline as pipe

COLORS={'EndpointCI':'#137d83','ExactPoint':'#263b5c','MatchedSpread':'#b77935','B2Point':'#8c94a4'}
ORDER=['EndpointCI','ExactPoint','MatchedSpread','B2Point']


def table(frame,formats=None):
    display=frame.copy()
    for name,fmt in (formats or {}).items():display[name]=display[name].map(fmt.format)
    return display.to_html(index=False,escape=True,border=0,classes='data')


def overview(summary,dest):
    f,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    s=summary.loc[ORDER]
    for ax,col,title,scale in zip(axes,['energy_km','h90','area90_km2'],['Energy Score (km) — lower is better','Actual hit rate (%)','Mean 90% region area (1,000 km²)'],[1,100,.001]):
        v=s[col].to_numpy()*scale
        ax.bar(range(4),v,color=[COLORS[n] for n in ORDER],width=.65)
        ax.set_xticks(range(4),['Endpoint\nCI','Exact\nPoint','Matched\nSpread','B2\nPoint'])
        ax.set_title(title,fontsize=11,pad=16)
        for j,value in enumerate(v):ax.text(j,value,f'{value:.3f}' if col=='energy_km' else f'{value:.2f}',ha='center',va='bottom',fontsize=9)
        ax.set_ylim(0,max(v)*1.2)
        if col=='h90':ax.axhline(90,color='#b54f4b',ls='--',lw=1,label='Nominal 90%');ax.legend(frameon=False,fontsize=8)
        ax.spines[['top','right']].set_visible(False)
    f.suptitle('Seven-day development validation · 33,971 cases · 45 equally weighted drifters',fontsize=12)
    f.savefig(dest,dpi=180);plt.close(f)


def contrast_figure(contrasts,dest):
    keep=contrasts[(contrasts.control=='ExactPoint')|((contrasts.candidate=='EndpointCI')&(contrasts.control=='MatchedSpread'))]
    keep=keep[keep.candidate!='ExactPoint'].reset_index(drop=True)
    f,axes=plt.subplots(1,3,figsize=(13,4.1),layout='constrained')
    labels=[f'{r.candidate}\nminus {r.control}' for r in keep.itertuples()]
    for ax,metric,scale,title in zip(axes,['energy_km','h90','area_ratio'],[1000,100,100],['Paired ES difference (metres)','Paired hit difference (percentage points)','Area change (%)']):
        if metric=='area_ratio':v=(keep.area_ratio-1)*100;lo=(keep.area_ratio_lo-1)*100;hi=(keep.area_ratio_hi-1)*100
        else:v=keep[metric+'_difference']*scale;lo=keep[metric+'_lo']*scale;hi=keep[metric+'_hi']*scale
        for j in range(len(keep)):
            color=COLORS[keep.iloc[j].candidate]
            ax.errorbar(float(v.iloc[j]),j,xerr=np.array([[v.iloc[j]-lo.iloc[j]],[hi.iloc[j]-v.iloc[j]]]),fmt='o',color=color,capsize=4)
        ax.axvline(0,color='#777',lw=1,ls='--');ax.set_yticks(range(len(keep)),labels if ax==axes[0] else ['']*len(keep));ax.invert_yaxis()
        ax.set_title(title,fontsize=11);ax.spines[['top','right']].set_visible(False);ax.grid(axis='x',alpha=.15)
    f.suptitle('Whole-drifter paired bootstrap · 10,000 draws · conditional 95% intervals',fontsize=12)
    f.savefig(dest,dpi=180);plt.close(f)


def ID_figure(cases,diagnostic,dest):
    f,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    ids=cases.groupby(['id','model']).energy_km.mean().unstack()
    delta=((ids.EndpointCI-ids.ExactPoint)*1000).sort_values()
    axes[0].bar(np.arange(len(delta)),delta,color=np.where(delta<=0,'#137d83','#b77935'))
    axes[0].axhline(0,color='#777',lw=.8);axes[0].set_title('EndpointCI − ExactPoint by drifter');axes[0].set_ylabel('Mean ES difference (metres)');axes[0].set_xlabel('45 drifters, sorted by paired difference')
    w=pipe.weights(diagnostic);axes[1].hist(diagnostic.fallback_mass*100,bins=np.linspace(0,100,21),weights=w*100,color='#263b5c',edgecolor='white')
    axes[1].set_title('Unavailable-error fallback in each forecast');axes[1].set_xlabel('Probability retained as original point mass (%)');axes[1].set_ylabel('Drifter-equal validation weight (%)')
    for ax in axes:ax.spines[['top','right']].set_visible(False)
    f.savefig(dest,dpi=180);plt.close(f)


def map_figure(folder,j,land,dest):
    example=json.loads((folder/f'example_{j}.json').read_text());observed=json.loads((folder/f'example_{j}_observation.json').read_text())
    data={n:np.load(folder/f'example_{j}_{n}.npz') for n in ORDER}
    boundaries={n:model.ellipse_boundary(example['forecast'][n]['region']) for n in ORDER}
    geographic={n:np.column_stack(model.INVERSE.transform(v[:,0]*1000,v[:,1]*1000)) for n,v in boundaries.items()}
    allpoints=np.vstack([*[data[n]['lonlat'] for n in ORDER],*geographic.values(),np.array([example['origin'],observed['truth']])])
    low=np.floor((allpoints.min(axis=0)-.5)*2)/2;high=np.ceil((allpoints.max(axis=0)+.5)*2)/2
    edges=[np.arange(low[k],high[k]+.25,.5) for k in range(2)]
    hist={n:np.histogram2d(data[n]['lonlat'][:,0],data[n]['lonlat'][:,1],bins=edges,weights=data[n]['weight'])[0]*100 for n in ORDER}
    for n in ORDER:assert abs(hist[n].sum()-100)<1e-8
    vmax=max(x.max() for x in hist.values());vmin=min(x[x>0].min() for x in hist.values())
    norm=LogNorm(vmin=max(vmin,.001),vmax=vmax)
    coastline=land.intersection(box(low[0],low[1],high[0],high[1]));parts=sh.get_parts(coastline)
    f,axes=plt.subplots(2,2,figsize=(12,9),layout='constrained')
    for ax,n in zip(axes.flat,ORDER):
        im=ax.pcolormesh(edges[0],edges[1],np.ma.masked_equal(hist[n].T,0),norm=norm,cmap='YlGnBu',rasterized=True)
        for polygon in parts:
            if polygon.geom_type=='Polygon':
                x,y=polygon.exterior.xy;ax.plot(x,y,color='#777',lw=.45)
        boundary=geographic[n];ax.plot(boundary[:,0],boundary[:,1],color='#c26736',lw=1.3,label='Continuous 90% ellipse')
        ax.scatter(*example['origin'],marker='^',color='black',s=28,zorder=6,label='Release')
        ax.scatter(*observed['truth'],marker='*',s=105,color='#d42f40',edgecolor='white',lw=.5,zorder=7,label='Observed day 7')
        score=observed['scores'][n];ax.set_title(f"{n} · ES {score['energy_km']:.4f} km\nArea {score['area90_km2']:,.0f} km² · observed hit {int(score['h90'])}",fontsize=10)
        ax.set_xlim(low[0],high[0]);ax.set_ylim(low[1],high[1]);ax.set_aspect(1/np.cos(np.deg2rad((low[1]+high[1])/2)))
        ax.set_xlabel('Longitude');ax.set_ylabel('Latitude');ax.grid(alpha=.12)
    axes[0,0].legend(fontsize=7,loc='best',framealpha=.9)
    f.colorbar(im,ax=axes,shrink=.8,label='Probability per 0.5° display cell (%) · logarithmic colour')
    f.suptitle(f'Frozen example {j} · identical start, extent and colour scale\nCells are display only; continuous coordinates determine scores, hits and areas.',fontsize=12)
    f.savefig(dest,dpi=150);plt.close(f)


def report(paths,run,cfg,approval,guard):
    start=time.monotonic();folder=run['results'];figures=folder/'figures';figures.mkdir(exist_ok=False)
    summary=pd.read_csv(folder/'summary.csv').set_index('model');contrasts=pd.read_csv(folder/'contrasts.csv')
    cases=inputs.read_frame(folder/'case_scores.parquet');d=inputs.read_frame(folder/'formal/donor_diagnostics.parquet')
    audit=json.loads((run['provenance']/'audit.json').read_text());formal=json.loads((run['provenance']/'formal_resources.json').read_text())
    attempts=[json.loads(p.read_text()) for p in run['provenance'].glob('pilot_attempt_*_resources.json')]
    resources=json.loads((run['provenance']/'audit_resources.json').read_text())
    main=contrasts[(contrasts.candidate=='EndpointCI')&(contrasts.control=='ExactPoint')].iloc[0]
    latest=sorted(run['provenance'].glob('pilot_attempt_*_gate.json'))[-1]
    pilot=json.loads(latest.read_text());pilot_folder=folder/f"pilot_attempt_{pilot['attempt']}"
    sensitivity=inputs.read_frame(folder/'rho_sensitivity_corrected.parquet')
    sensitivity=sensitivity.groupby(['rho','model','id'])[['energy_km','delta_energy_vs_exact_km','h90','area90_km2']].mean().reset_index()
    sensitivity=sensitivity.groupby(['rho','model'])[['energy_km','delta_energy_vs_exact_km','h90','area90_km2']].mean().reset_index()
    save_frame(paths,folder/'rho_pilot_summary.csv',sensitivity)
    w=pipe.weights(d)
    fallback=dict(training_pairs=265393,usable_endpoint_pairs=249577,point_fallback_pairs=15816,
        training_point_fallback_fraction=15816/265393,query_weighted_point_fallback_mass=float(w@d.fallback_mass),
        queries_with_any_fallback=int((d.fallback_mass>0).sum()),queries_all_fallback=int((d.fallback_mass==1).sum()),
        donor_count_min=int(d.donors.min()),donor_count_max=int(d.donors.max()),
        donor_ID_min=int(d.donor_IDs.min()),donor_ID_max=int(d.donor_IDs.max()),
        weighted_largest_ID_share=float(w@d.largest_ID_share))
    reasons={}
    for weight,r in zip(w,d.fallback_reasons):
        row=json.loads(r)
        # Reasons are pair counts within the query, so divide by that query's
        # complete donor count before equal-drifter aggregation.
        for reason,count in row.items():reasons.setdefault(reason,[])
    for i,row in enumerate(d.itertuples()):
        for reason,count in json.loads(row.fallback_reasons).items():reasons[reason].append(w[i]*count/row.donors)
    fallback['reason_probability_mass']={k:float(sum(v)) for k,v in reasons.items()}
    assert abs(sum(fallback['reason_probability_mass'].values())-fallback['query_weighted_point_fallback_mass'])<1e-12
    save_json(paths,folder/'fallback_summary.json',fallback)
    overview(summary,figures/'overview.png');contrast_figure(contrasts,figures/'paired_contrasts.png');ID_figure(cases,d,figures/'drifters_and_fallback.png')
    land=sh.from_wkb(paths.asset('land_mask_high',verify=True).read_bytes())
    examples=json.loads((folder/'formal/example_selection.json').read_text())['query_positions']
    for j in examples:map_figure(folder/'formal',j,land,figures/f'example_{j}.png')
    headline=summary.loc[ORDER,['energy_km','h90','area90_km2','auxiliary','coverage_gap']].reset_index()
    headline.h90*=100;headline.coverage_gap*=100
    headline.columns=['Model','Energy Score (km)','Actual H90 (%)','Mean area (km²)','Auxiliary loss','H90 minus nominal (pp)']
    markdown_table='| '+' | '.join(headline.columns)+' |\n| '+' | '.join(['---']*len(headline.columns))+' |\n'
    markdown_table+='\n'.join('| '+' | '.join([str(row[0])]+[f'{v:,.6f}' for v in row[1:]])+' |' for row in headline.itertuples(index=False,name=None))
    contrast_table=contrasts[['candidate','control','energy_km_difference','energy_km_lo','energy_km_hi','h90_difference','area_ratio']].copy()
    for c in ['energy_km_difference','energy_km_lo','energy_km_hi']:contrast_table[c]*=1000
    contrast_table.h90_difference*=100;contrast_table.area_ratio=(contrast_table.area_ratio-1)*100
    contrast_table.columns=['Candidate','Control','ES difference (m)','95% lower (m)','95% upper (m)','H90 difference (pp)','Area change (%)']
    tables=table(headline,{c:'{:,.6f}' if 'Energy' in c else '{:,.3f}' for c in headline.columns[1:]})
    contrasts_html=table(contrast_table,{c:'{:,.6f}' for c in contrast_table.columns[2:]})
    pilot_seconds=sum(x['elapsed_seconds'] for x in attempts)+json.loads((run['provenance']/'pilot_correlation_correction_resources.json').read_text())['elapsed_seconds']
    narrative=(f"EndpointCI minus ExactPoint: ES {main.energy_km_difference*1000:+.6f} metres "
        f"(paired 95% interval {main.energy_km_lo*1000:+.6f} to {main.energy_km_hi*1000:+.6f}); "
        f"actual H90 {main.h90_difference*100:+.6f} percentage points; mean area {(main.area_ratio-1)*100:+.6f}%. "
        f"The predeclared minimum useful ES reduction was 0.1%; the observed relative reduction is {main.relative_ES_reduction*100:+.6f}%.")
    if not main.practical_ES_benefit:
        interpretation='The added location-error clouds did not establish a practically useful improvement. Preserve the point estimator; do not increase error widths to search for a win. A small or unresolved effect does not prove that measurement uncertainty is irrelevant.'
    elif not main.supported_ES_benefit:
        interpretation='The paired development interval does not establish an ES improvement. The point estimator remains the reference.'
    else:interpretation='Assess the ES change together with all quality and numerical guardrails below; a favourable point estimate alone does not authorize replacing the reference.'
    guardrails=pd.DataFrame([
        ['Bootstrap ES direction',bool(main.supported_ES_benefit),'Upper paired 95% ES-difference bound < 0; numerical resolution is assessed separately'],
        ['Practical ES improvement',bool(main.practical_ES_benefit),'Relative ES reduction >= 0.1%'],
        ['Observed quality direction',bool(main.point_quality_direction),'H90 does not decrease and mean area does not increase'],
        ['Interval quality margins',bool(main.interval_quality_guardrails),'H90 lower bound >= -1 pp; area ratio upper bound <= 1.02'],
        ['Geographic margins',bool(main.geographic_guardrails),'Land and outside-D mass increases each <= 1 pp'],
        ['Numerical and independent audit',bool(audit['passed']),'Full-roster region replication and independent score checks']
    ],columns=['Requirement','Met','Definition'])
    region_audit=pd.DataFrame(audit['region_replication']).T.reset_index().rename(columns={'index':'Model'})
    availability=pd.read_csv(folder/'formal/training_error_availability.csv')
    resources_text=f"Pilot: {pilot_seconds:.1f} s over {len(attempts)} preserved attempts plus a nonzero-rho diagnostic covariance correction. Formal: {formal['elapsed_seconds']:.1f} s. Independent audit: {resources['elapsed_seconds']:.1f} s. Peak observed process RSS: {max(formal['peak_rss_bytes'],resources['peak_rss_bytes'])/2**30:.2f} GiB."
    examples_html=''.join(f'<details><summary>Frozen example {j}</summary><img src="figures/example_{j}.png" alt="Four matched continuous forecasts for frozen example {j}" loading="lazy"></details>' for j in examples)
    document=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Step 4 E8 · Endpoint uncertainty</title>
<style>body{{margin:0;background:#f4f6f8;color:#203047;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1180px;margin:auto;padding:36px 24px 70px}}header{{background:#203047;color:white;padding:36px;border-radius:14px}}h1{{font-size:35px;line-height:1.2;margin:10px 0}}h2{{font-size:25px;margin-top:0}}.eyebrow{{letter-spacing:.12em;font-size:12px;text-transform:uppercase;color:#a6d9da}}section{{background:white;padding:28px;margin-top:22px;border-radius:12px}}.lead{{font-size:20px}}.note{{background:#eef5f5;border-left:4px solid #137d83;padding:16px}}.muted{{color:#647084;font-size:14px}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:10px;border-bottom:1px solid #e4e8ed;text-align:right;white-space:nowrap}}td:first-child,th:first-child{{text-align:left}}th{{background:#eef2f6}}img{{width:100%;height:auto;margin:14px 0}}details{{border-top:1px solid #dde3ea;padding:12px 0}}summary{{cursor:pointer;font-weight:600}}a{{color:#08797c}}code{{font-size:12px;overflow-wrap:anywhere}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.card{{background:#eef2f6;padding:14px;border-radius:8px}}.card b{{display:block;font-size:23px}}@media(max-width:700px){{main{{padding:14px}}header,section{{padding:19px}}h1{{font-size:27px}}.cards{{grid-template-columns:1fr}}}}</style></head><body><main>
<header><div class="eyebrow">Where things end up · Step 4 E8 v2</div><h1>Does endpoint position uncertainty help?</h1><p>Seven-day Markov destination forecasts, with repaired historical endpoint errors.</p><p class="lead">{html.escape(audit['conclusion'].capitalize())}</p></header>
<section><h2>Matched comparison</h2><div class="cards"><div class="card"><b>33,971</b>complete validation cases</div><div class="card"><b>45</b>equally weighted validation drifters</div><div class="card"><b>100 km</b>fixed historical-start cap; k = 8,000 plus ties</div></div><p>{narrative}</p><div class="note">{interpretation}</div><p class="muted">Training: 2001–2019. Development validation: 2020–2022. Every model uses the same validation cases and equal-time-within-ID, equal-ID evaluation. These are repeatedly inspected development data, not an untouched final test.</p><div class="scroll">{tables}</div><img src="figures/overview.png" alt="Four model score, hit-rate and region-area comparison"></section>
<section><h2>What changed, and what stayed fixed</h2><p><b>ExactPoint</b> uses the original historical endpoint atoms. <b>EndpointCI</b> spreads usable endpoints using their repaired 95% marginal half-widths divided by 1.9599639845, with fixed normal shape and zero axis correlation. <b>MatchedSpread</b> uses the same valid mask but a common query-level covariance. <b>B2Point</b> retains the original one-degree conditioning rule and exact endpoint coordinates.</p><p>Every historical donor keeps its original vote. Only endpoint uncertainty changes. No origin jitter, wind, velocity, bandwidth selection, Gaussian transport model or neural estimator is introduced.</p><p class="note">A location CI is not a seven-day transport interval. The final forecast is a mixture of historical destinations. The 90% region is a common distribution-quantile ellipse, not a minimum-area region. Actual hit rate need not equal its nominal model probability.</p></section>
<section><h2>Paired evidence and decision</h2><p>Intervals resample whole drifter IDs, preserving paired forecasts and all observations within each ID. Small CI-model effects are shown in metres to make their scale legible.</p><div class="scroll">{contrasts_html}</div><img src="figures/paired_contrasts.png" alt="Paired drifter bootstrap differences with confidence intervals"><div class="scroll">{table(guardrails)}</div><p class="muted">A tiny area increase remains a trade-off even when inside the 2% noninferiority margin. No default-model replacement follows automatically.</p></section>
<section><h2>Error availability and point fallback</h2><p>{fallback['usable_endpoint_pairs']:,} of {fallback['training_pairs']:,} training pairs have usable two-axis endpoint errors. The remaining {fallback['point_fallback_pairs']:,} pairs ({fallback['training_point_fallback_fraction']*100:.4f}%) retain their exact original endpoint and full vote.</p><p>The drifter-equal average point-fallback probability in the actual forecasts is <b>{fallback['query_weighted_point_fallback_mass']*100:.4f}%</b>. {fallback['queries_with_any_fallback']:,} queries include some fallback; {fallback['queries_all_fallback']:,} have no usable error donors. Fallback is not a transport failure or missing validation case.</p><img src="figures/drifters_and_fallback.png" alt="Per-drifter energy-score effects and unavailable-error fallback"><details><summary>Training availability by period and source location type</summary><div class="scroll">{table(availability)}</div></details><p><a href="fallback_summary.json">Fallback reasons and support diagnostics</a> · <a href="availability_strata.csv">Query-availability strata</a> · <a href="year_strata.csv">Validation-year strata</a></p></section>
<section><h2>Same-start visual comparisons</h2><p>The six example keys were frozen in E7 before seeing E8 outcomes. All four models share each map's extent and colour scale. Probability is aggregated into 0.5° cells for display only; exact coordinates determine the Energy Score, hit and continuous area. Small error clouds may be visually indistinguishable at this display scale.</p>{examples_html}</section>
<section><h2>Independent verification and limits</h2><p>Independent formulas and random streams rechecked continuous regions on all 33,971 cases and Energy Score contrasts on 128 fixed cases. All donor digests, complete-case weights, bootstrap aggregates and protected input hashes were checked. Outer endpoint errors and the locked final-test pool were not read.</p><div class="scroll">{table(region_audit)}</div><p>{resources_text}</p><details><summary>Inner pilot correlation sensitivity (128 fixed queries only)</summary><div class="scroll">{table(sensitivity)}</div><p class="muted">This is an engineering sensitivity check, not a full-window performance estimate or a route to select rho.</p></details><p class="muted">The normal observation-error shape and zero correlation are working assumptions. Inner rho = ±0.5 checks are diagnostic, not parameter selection or full-period robustness. This is empirical smoothing of already estimated observations, not deconvolution or proof of improved latent physical positions. The retrospective source product does not establish real-time availability.</p><p><a href="REPORT.md">English report</a> · <a href="summary.csv">All summary metrics</a> · <a href="contrasts.csv">Paired intervals</a> · <a href="per_ID.csv">Per-ID scores</a> · <a href="numerical_summary.json">Numerical precision</a> · <a href="leave_one_ID_out.csv">Leave-one-ID-out diagnostics</a></p><p class="muted">Run: <code>{folder.name}</code><br>Approved contract SHA256: <code>{cfg['contract_sha256']}</code></p></section>
</main></body></html>'''
    paths.publish(folder/'review.html',lambda f:f.write(document.encode()))
    text=f'''# Step 4 E8 v2 — Endpoint position uncertainty

Status: {audit['conclusion']}.

{narrative}

{interpretation}

## Complete matched result

All 33,971 seven-day cases from 45 validation IDs are retained. Training is 2001–2019; validation is the previously used 2020–2022 development period. Evaluation gives equal weight to each drifter after averaging its times. See [summary.csv](summary.csv), [paired intervals](contrasts.csv), and [visual review](review.html).

{markdown_table}

## Scientific interpretation

This is a fixed-lag Markov kernel over exact positions. EndpointCI adds only verified historical endpoint location uncertainty, preserving all original votes. ExactPoint is the main reference; MatchedSpread separates generic spreading from record-specific width allocation; B2Point is a historical anchor rescored in the same continuous space. No origin errors or validation endpoint errors enter prediction or scoring.

Energy Score uses Euclidean WGS84 ECEF chord distances in kilometres. The auxiliary loss is ES/100 + squared mean error/10000. The common 90% region is a distribution-quantile ellipse in WGS84 LAEA, with continuous area and exact-point hits. It is not an HDR. 0.5-degree cells are display only.

## Fallback and numerical evidence

Training endpoint-error fallback: 15,816/265,393 pairs (5.959462%). Actual forecast-weighted fallback: {fallback['query_weighted_point_fallback_mass']*100:.6f}%. All original votes are retained; no complete-case-only analysis, land rejection or renormalization was performed. See [fallback_summary.json](fallback_summary.json), [period/source coverage](formal/training_error_availability.csv), [year strata](year_strata.csv), and [availability strata](availability_strata.csv).

Independent region replay covers all 33,971 cases; independent Energy Score checks cover 128 fixed queries. The numerical audit status is {audit['passed']}. {resources_text}

The corrected error amplitudes characterize observation-location uncertainty, not transport uncertainty. The normal working kernel is not an identified posterior or deconvolution. A negligible effect is not proof that uncertainty is universally irrelevant. No model replacement or Step 5 transition is made.

## Provenance

Run: {folder.name}

Contract: {cfg['contract_sha256']}

Repair overlay: {cfg['overlay_sha256']}

Frozen forecasts precede outer endpoint scoring. Protected canonical data, approved contract, ledger, repair outputs and E7 inputs remain unchanged. The final-test pool and outer endpoint errors remain unread. Figures reuse the six E7 example keys. All earlier pilot attempts are preserved.
'''
    paths.publish(folder/'REPORT.md',lambda f:f.write(text.encode()))
    receipt=pipe.resources(run,start);receipt['figures']=len(list(figures.glob('*.png')))
    receipt['total_resource_seconds']=pilot_seconds+formal['elapsed_seconds']+resources['elapsed_seconds']+receipt['elapsed_seconds']
    assert receipt['total_resource_seconds']<=cfg['seconds']['total']
    assert receipt['retained_bytes']<=cfg['storage_gib']*2**30
    assert pilot_seconds<=cfg['seconds']['pilot'] and formal['elapsed_seconds']<=cfg['seconds']['formal'] and resources['elapsed_seconds']<=cfg['seconds']['audit']
    save_json(paths,run['provenance']/'report_resources.json',receipt)
    outputs={str(p.relative_to(inputs.ROOT)):file_sha256(p) for directory in run.values() for p in directory.rglob('*') if p.is_file()}
    save_json(paths,run['provenance']/'outputs.json',dict(completed=True,scientific_benefit_claimed=audit['conclusion']=='supported benefit with guardrails met',
        final_test_access=False,outer_endpoint_errors_read=False,independent_audit_passed=bool(audit['passed']),output_sha256=outputs))
    print(str(folder/'review.html'),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    report(*inputs.context(a.run))

if __name__=='__main__':main()
