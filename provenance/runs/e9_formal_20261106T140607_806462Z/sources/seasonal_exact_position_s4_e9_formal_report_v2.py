"""English research evidence and fixed-example visual comparison for E9."""
import html
import json
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import shapely as sh
from shapely.geometry import box
from data3001.modelling.common.runtime import save_json
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_formal_io as fio
from data3001.modelling.baselines import position_error_s4_e8 as geometry
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography

LABELS=['Annual\nExactPoint','Annual\nEndpointCI','Seasonal\nExactPoint','Seasonal\nEndpointCI']
COLORS=['#285477','#4c8494','#ad7044','#d19467']


def overview(summary,dest):
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    for ax,metric,factor,title in zip(axes,['energy_km','h90','area90_km2'],[1,100,1/1000],
                                    ['Energy Score (km) · lower is better','Actual 90% region hit rate (%)','Mean 90% region area (1,000 km²)']):
        y=summary.loc[fio.MODELS,metric].to_numpy()*factor
        lo=summary.loc[fio.MODELS,metric+'_low'].to_numpy()*factor;hi=summary.loc[fio.MODELS,metric+'_high'].to_numpy()*factor
        ax.bar(np.arange(4),y,color=COLORS,alpha=.9)
        ax.errorbar(np.arange(4),y,yerr=np.maximum(np.vstack([y-lo,hi-y]),0),fmt='none',ecolor='#253246',capsize=4)
        for i,value in enumerate(y):ax.annotate(f'{value:.3f}',(i,value),xytext=(0,6),textcoords='offset points',ha='center',fontsize=9)
        ax.set_xticks(np.arange(4),LABELS,fontsize=9);ax.set_title(title,fontsize=10);ax.spines[['top','right']].set_visible(False)
        ax.set_ylim(0,max(hi)*1.16)
    fig.suptitle('Seven-day seasonal closure · all 33,971 cases, 45 equally weighted drifters\nError bars: paired whole-ID bootstrap 95% intervals; development evidence',fontsize=13)
    fig.savefig(dest,dpi=170);plt.close(fig)


def effect_plot(contrasts,dest):
    fig,axes=plt.subplots(1,3,figsize=(13,4.6),layout='constrained')
    names=['SC − AC','SP − AP','SC − SP','AC − AP','SC − AP'];y=np.arange(5)
    for ax,col,lo,hi,factor,offset,title in [
        (axes[0],'es_difference_km','es_low','es_high',1,0,'Energy Score difference (km)'),
        (axes[1],'h90_difference','h90_low','h90_high',100,0,'Actual hit-rate difference (pp)'),
        (axes[2],'area_ratio','area_ratio_low','area_ratio_high',100,1,'Mean area change (%)')]:
        value=(contrasts[col].to_numpy()-offset)*factor;low=(contrasts[lo].to_numpy()-offset)*factor;high=(contrasts[hi].to_numpy()-offset)*factor
        ax.errorbar(value,y,xerr=np.maximum(np.vstack([value-low,high-value]),0),fmt='o',color='#285477',capsize=4)
        ax.axvline(0,color='#888',lw=.8);ax.set_yticks(y,names);ax.invert_yaxis();ax.set_title(title,fontsize=10);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Prespecified paired contrasts · 10,000 whole-drifter bootstrap draws\nA = annual; S = seasonal; P = ExactPoint; C = EndpointCI. First two rows are the season tests.',fontsize=12)
    fig.savefig(dest,dpi=170);plt.close(fig)


def support_plot(folder,dest):
    data=pd.read_csv(folder/'season_support.csv');support=pd.read_parquet(folder/'support.parquet');roster=pd.read_parquet(folder/'roster.parquet')
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained');labels=['DJF','MAM','JJA','SON'];x=np.arange(4)
    for role,shift,color in [('training',-.18,COLORS[0]),('query',.18,COLORS[2])]:
        g=data[data.role==role].set_index('season').loc[labels]
        axes[0].bar(x+shift,g.IDs,.36,label=role,color=color)
    axes[0].set_xticks(x,labels);axes[0].set_title('Independent IDs by majority season');axes[0].legend(fontsize=8)
    for pool,color in [('Annual',COLORS[0]),('Seasonal',COLORS[2])]:
        g=support[support.pool==pool].sort_values('query_position')
        axes[1].hist(g.donor_IDs,bins=25,weights=roster.weight,alpha=.55,label=pool,color=color)
        axes[2].hist(g.error_fallback_mass*100,bins=np.linspace(0,100,21),weights=roster.weight,alpha=.55,label=pool,color=color)
    axes[1].set_title('Historical drifter support per prediction');axes[1].set_xlabel('Distinct selected training IDs');axes[1].legend(fontsize=8)
    axes[2].set_title('Unavailable error: retained point-mass vote');axes[2].set_xlabel('Forecast probability (%)');axes[2].legend(fontsize=8)
    for ax in axes:ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Support and error fallback · seasonal ID counts overlap across seasons',fontsize=12)
    fig.savefig(dest,dpi=170);plt.close(fig)


def example_map(folder,j,land,dest):
    e=json.loads((folder/f'example_{j}.json').read_text());obs=json.loads((folder/f'example_{j}_observation.json').read_text())
    data={}
    for name in fio.MODELS:
        with np.load(folder/f'example_{j}_{name}.npz') as f:data[name]={k:f[k].copy() for k in f.files}
    boundaries={name:geometry.ellipse_boundary(e['forecast'][name]['region']) for name in fio.MODELS}
    geographic={name:np.column_stack(geometry.INVERSE.transform(v[:,0]*1000,v[:,1]*1000)) for name,v in boundaries.items()}
    allpoints=np.vstack([*[data[name]['lonlat'] for name in fio.MODELS],*geographic.values(),np.array([e['origin'],obs['truth']])])
    low=np.floor((allpoints.min(axis=0)-.5)*2)/2;high=np.ceil((allpoints.max(axis=0)+.5)*2)/2
    edges=[np.arange(low[k],high[k]+.25,.5) for k in range(2)]
    hist={name:np.histogram2d(data[name]['lonlat'][:,0],data[name]['lonlat'][:,1],bins=edges,weights=data[name]['weight'])[0]*100 for name in fio.MODELS}
    for value in hist.values():assert abs(value.sum()-100)<1e-8
    vmax=max(a.max() for a in hist.values());vmin=min(a[a>0].min() for a in hist.values());norm=LogNorm(vmin=max(vmin,.001),vmax=vmax)
    parts=sh.get_parts(land.intersection(box(low[0],low[1],high[0],high[1])))
    fig,axes=plt.subplots(2,2,figsize=(12,9),layout='constrained')
    for ax,name in zip(axes.flat,fio.MODELS):
        im=ax.pcolormesh(edges[0],edges[1],np.ma.masked_equal(hist[name].T,0),norm=norm,cmap='YlGnBu',rasterized=True)
        for polygon in parts:
            if polygon.geom_type=='Polygon':
                x,y=polygon.exterior.xy;ax.plot(x,y,color='#777',lw=.45)
        boundary=geographic[name];ax.plot(boundary[:,0],boundary[:,1],color='#c26736',lw=1.3,label='Continuous 90% ellipse')
        ax.scatter(*e['origin'],marker='^',color='black',s=28,zorder=6,label='Release')
        ax.scatter(*obs['truth'],marker='*',s=105,color='#d42f40',edgecolor='white',lw=.5,zorder=7,label='Observed day 7')
        score=obs['scores'][name];ax.set_title(f"{name} · ES {score['energy_km']:.4f} km\nArea {score['area90_km2']:,.0f} km² · observed hit {int(score['h90'])}",fontsize=10)
        ax.set_xlim(low[0],high[0]);ax.set_ylim(low[1],high[1]);ax.set_aspect(1/np.cos(np.deg2rad((low[1]+high[1])/2)))
        ax.set_xlabel('Longitude');ax.set_ylabel('Latitude');ax.grid(alpha=.12)
    axes[0,0].legend(fontsize=7,loc='best',framealpha=.9)
    fig.colorbar(im,ax=axes,shrink=.8,label='Probability per 0.5° display cell (%) · logarithmic colour')
    fig.suptitle(f'Frozen example {j} · identical start, extent and colour scale\nCells display mass only; continuous positions determine scores, hits and areas.',fontsize=12)
    fig.savefig(dest,dpi=150);plt.close(fig)


def markdown_table(frame):
    rows=['| '+' | '.join(frame.columns)+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    for row in frame.itertuples(index=False,name=None):rows.append('| '+' | '.join(str(v) for v in row)+' |')
    return '\n'.join(rows)


def report(paths,run,cfg,approval,guard,budget):
    folder=run['results'];figures=folder/'figures';figures.mkdir()
    summary=pd.read_csv(folder/'summary.csv').set_index('model');contrasts=pd.read_csv(folder/'contrasts.csv')
    decision=json.loads((run['provenance']/'decision.json').read_text());audit=json.loads((run['provenance']/'independent_audit.json').read_text())
    numerical=pd.read_csv(folder/'numerical_stability.csv');fallback=pd.read_csv(folder/'fallback_summary.csv')
    overview(summary,figures/'overview.png');effect_plot(contrasts,figures/'paired_effects.png');support_plot(folder,figures/'support.png')
    geo=Geography(paths)
    for j in fio.EXAMPLES:
        budget.check();example_map(folder/'examples',j,geo.land,figures/f'example_{j}.png')
    display=pd.DataFrame([dict(Model=name,**{'ES (km)':f'{summary.loc[name,"energy_km"]:.6f}',
        'Actual H90':f'{100*summary.loc[name,"h90"]:.4f}%', 'Mean area (km²)':f'{summary.loc[name,"area90_km2"]:,.2f}'}) for name in fio.MODELS])
    effects=pd.DataFrame([{'Comparison':r.candidate+' − '+r.reference,'ES difference (km)':f'{r.es_difference_km:+.6f}',
        'ES 95% interval':f'[{r.es_low:+.6f}, {r.es_high:+.6f}]','H90 change (pp)':f'{100*r.h90_difference:+.4f}',
        'Area change':f'{100*(r.area_ratio-1):+.4f}%'} for r in contrasts.itertuples(index=False)])
    conclusions=[]
    for r in decision['decisions']:
        c=contrasts[(contrasts.candidate==r['candidate'])&(contrasts.reference==r['reference'])].iloc[0]
        conclusions.append(f"{r['candidate']} versus {r['reference']}: **{r['status']}**. ES changes by {c.es_difference_km:+.6f} km ({100*c.es_relative_difference:+.3f}%), H90 by {100*c.h90_difference:+.4f} percentage points, and mean area by {100*(c.area_ratio-1):+.4f}%.")
    if not any(r['accepted'] for r in decision['decisions']):
        conclusions.append('No seasonal candidate meets all registered acceptance criteria. This closes the specified seasonal comparison; it does not establish that ocean dynamics have no seasonality. No model replacement or additional tuning is performed.')
    subgroups=pd.read_csv(folder/'subgroups.csv');loo=pd.read_csv(folder/'leave_one_id_out.csv')
    s_support=pd.read_parquet(folder/'support.parquet');q_roster=pd.read_parquet(folder/'roster.parquet')
    support_means={}
    for pool,g in s_support.groupby('pool'):
        g=g.sort_values('query_position');w=q_roster.weight.to_numpy()
        support_means[pool]=dict(IDs=float(w@g.donor_IDs),pairs=float(w@g.donors),farthest_km=float(w@g.farthest_m)/1000)
    subgroup_worse={}
    for group in ['majority_season','year']:
        a=subgroups[(subgroups.group==group)&(subgroups.model=='AnnualEndpointCI')].set_index('value')
        b=subgroups[(subgroups.group==group)&(subgroups.model=='SeasonalEndpointCI')].set_index('value')
        subgroup_worse[group]=int((b.energy_km-a.energy_km>0).sum())
    leave=loo[loo.candidate=='SeasonalEndpointCI']
    diagnostic=(f"The CI seasonal model has higher mean ES in {subgroup_worse['majority_season']} of four season subgroups and {subgroup_worse['year']} of three calendar-year subgroups. "
        f"Leaving out each validation ID in turn gives an SC-minus-AC ES difference from {leave.es_difference_km.min():.3f} to {leave.es_difference_km.max():.3f} km. "
        f"The evaluation-weighted mean number of selected training IDs changes from {support_means['Annual']['IDs']:.1f} to {support_means['Seasonal']['IDs']:.1f}; "
        f"the corresponding mean of each query's farthest selected-start distance changes from {support_means['Annual']['farthest_km']:.1f} to {support_means['Seasonal']['farthest_km']:.1f} km. "
        "These are registered descriptive diagnostics, not additional significance tests. Season filtering changes both sample support and selected-neighbour distances; this experiment does not isolate their causal contributions.")
    conclusions.append(diagnostic)
    unavailable='; '.join(f"{r.pool}: {100*r.weighted_error_fallback_mass:.4f}% mean probability retained at the original endpoint" for r in fallback.itertuples(index=False))
    sf=fallback[fallback.pool=='Seasonal'].iloc[0]
    falltext=f"Empty-season fallback: {sf.seasonal_fallback_count:,} / 33,971 queries ({100*sf.seasonal_fallback_fraction:.4f}% of queries; {100*sf.seasonal_fallback_weight:.4f}% of evaluation weight; {sf.seasonal_fallback_IDs} IDs). Error fallback is separate: {unavailable}. These percentages are not added."
    examples=pd.read_parquet(folder/'example_roster.parquet');seasons=sorted(examples.majority_season.unique().tolist())
    figure_note=f'Example positions were frozen before scoring: {fio.EXAMPLES}. Represented season indices: {seasons} (0 DJF, 1 MAM, 2 JJA, 3 SON); cross-season examples: {int(examples.cross_season.sum())}. Missing categories are not replaced by outcome-selected examples.'
    methods='Training: 265,393 pairs from 338 IDs, 2001–2019. Development validation: all 33,971 pairs from 45 non-overlapping IDs, 2020–2022. Seven days exactly; elapsed-duration majority UTC season, exact half-and-half ties assigned to departure season. Same-season filtering precedes the 100 km, nearest-8,000-with-ties search. Every selected pair retains one equal vote. No annual/seasonal blending, trajectory translation, new predictors, probability clipping or sample removal. EndpointCI uses the accepted repaired marginal location errors with the inherited E8 construction; unavailable errors retain the original point. CI denotes measurement uncertainty, not a fitted Gaussian transport law.'
    evaluation='Energy Score uses exponent-one ECEF chord distances in km. H90 and area use the corrected distribution-quantile LAEA ellipse; 0.5° cells are display only. Times are averaged within each drifter, then the 45 drifters are equally weighted. The 10,000 whole-ID paired bootstrap draws use the frozen seed 20261106. The two season claims share a nominal Bonferroni family level of 0.05. Subgroup tables retain and renormalize the original evaluation weights.'
    validity=f"Numerical gates passed: {decision['global_numerical_gates_passed']}. All {audit['region_replays']:,} primary region hit/area records were independently replayed; all 33,971 queries received a second numerical stream. Full-distance neighbours were independently reconstructed for 128 frozen outer queries, in addition to the previously verified 128 pilot queries. Separate 65,536-pair ES calculations checked 128 frozen outer queries. Maximum same-stream ES reconstruction error: {audit['max_same_seed_energy_difference_km']:.3g} km. Complete donor lineage, all region definitions, streams, per-case scores and bootstrap outputs are retained."
    limitation='This is reused development evidence. The forecasts are held fixed in the bootstrap; its intervals do not include training-set uncertainty, shared ocean forcing or all effects of repeated analysis of this validation period. The ellipse can bridge low-density gaps and is not a minimum-area region. Available 2022 observations do not cover a complete year. No final-test IDs or validation-endpoint errors were accessed.'
    text='# Step 4 E9 — Exact-position seasonal closure\n\n## Material Passport\n\n- Mode: execution and computational validation.\n- Status: complete four-arm development comparison; scientific acceptance is reported separately below.\n- Run: `'+folder.name+'`.\n- Authority: user-approved E9 contract and ES optimization; subsequent explicit authorizations waived the twofold runtime precheck and the 2.5 GiB storage precheck, while retaining actual phase caps and the 5 GiB hard storage budget.\n\n## Findings\n\n'+'\n\n'.join(conclusions)+'\n\n'+markdown_table(display)+'\n\n'+markdown_table(effects)+'\n\n## Frozen methods\n\n'+methods+'\n\n'+evaluation+'\n\n## Fallbacks\n\n'+falltext+'\n\n## Verification and limits\n\n'+validity+'\n\n'+limitation+'\n\n## Figures\n\n![Overview](figures/overview.png)\n\n![Paired effects](figures/paired_effects.png)\n\n![Support](figures/support.png)\n\n'+figure_note+'\n\n'+'\n\n'.join(f'![Frozen example {j}](figures/example_{j}.png)' for j in fio.EXAMPLES)+'\n\n## Evidence files\n\n- `summary.csv`, `contrasts.csv`, `case_scores.parquet`, `per_id_scores.csv`.\n- `subgroups.csv`, `leave_one_id_out.csv`, `season_support.csv`, `fallback_summary.csv`.\n- `energy_precision.csv`, `numerical_stability.csv`, `independent_es_65536.csv`, `independent_neighbours.csv`.\n- `forecasts.jsonl`, `donor_lineage.zst`, `lineage_offsets.parquet`, `fit_keys_seasons.parquet`.\n- Matching provenance: approval, forecast freeze, independent audit, decision and phase resource receipts.\n'
    paths.publish(folder/'REPORT.md',lambda f:f.write(text.encode()))
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E9 seasonal research evidence</title>',
           '<style>body{font-family:system-ui,sans-serif;max-width:1200px;margin:40px auto;padding:0 22px;color:#1d2d3b;line-height:1.6;background:#f6f7f8}h1{font-size:30px}section{background:white;padding:24px;margin:20px 0;border-radius:12px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px;border-bottom:1px solid #ddd;text-align:right}th:first-child,td:first-child{text-align:left}img{width:100%;height:auto}code{overflow-wrap:anywhere}.scroll{overflow:auto}</style><body>',
           '<h1>Step 4 E9 · Seasonal closure</h1><p>Exact release positions · seven-day forecasts · all 33,971 cases / 45 drifters</p><section><h2>Research decision</h2>',
           *['<p>'+html.escape(s).replace('**','')+'</p>' for s in conclusions],display.to_html(index=False,escape=True),'</section>',
           '<section><h2>Matched comparisons</h2><div class="scroll">'+effects.to_html(index=False,escape=True)+'</div><img src="figures/overview.png"><img src="figures/paired_effects.png"></section>',
           '<section><h2>Support and fallbacks</h2><p>'+html.escape(falltext)+'</p><img src="figures/support.png"></section>',
           '<section><h2>Frozen experiment and verification</h2><p>'+html.escape(methods)+'</p><p>'+html.escape(evaluation)+'</p><p>'+html.escape(validity)+'</p><p>'+html.escape(limitation)+'</p></section>',
           '<section><h2>Six prespecified comparisons</h2><p>'+html.escape(figure_note)+'</p>',
           *[f'<img loading="lazy" src="figures/example_{j}.png" alt="Four-model forecast comparison at frozen query {j}">' for j in fio.EXAMPLES],
           '</section><section><h2>Download evidence</h2><p><a href="REPORT.md">Research report</a> · <a href="summary.csv">Four-model table</a> · <a href="contrasts.csv">Paired effects</a> · <a href="numerical_stability.csv">Numerical checks</a></p><p><code>'+folder.name+'</code></p></section></body></html>']
    paths.publish(folder/'review.html',lambda f:f.write(''.join(parts).encode()))
    fio.verify({**approval['protected_files'],**approval['new_source_sha256']})
    save_json(paths,run['provenance']/'report_checks.json',dict(figures=9,prespecified_examples=fio.EXAMPLES,
        tables_match_saved_scores=True,all_four_models_displayed=True,shared_map_extent_colour_scale=True,
        HTML_links_checked=all((folder/'figures'/f'example_{j}.png').exists() for j in fio.EXAMPLES),
        English_report=True,final_test_access=False,protected_files_unchanged=True))
    print('Report complete:',folder/'review.html',flush=True)


def main(name):
    import sys, traceback
    paths,run,cfg,approval,guard,budget=fio.context(name,'audit');completed=False
    try:
        source=fio.ROOT/'src/data3001/modelling/baselines/seasonal_exact_position_s4_e9_formal_report_v2.py'
        paths.publish(run['provenance']/'sources'/source.name,lambda f:f.write(source.read_bytes()))
        save_json(paths,run['provenance']/'report_source_revision.json',dict(source_sha256=fio.hashes([source]),
            scope='Report the later explicit storage waiver and the already registered subgroup, leave-one-ID-out and support diagnostics. All scores, intervals, decisions and figures use saved unchanged scientific results.',model_or_weight_change=False))
        report(paths,run,cfg,approval,guard,budget);budget.check(storage=True);completed=True
    except BaseException as error:
        save_json(paths,run['provenance']/'report_failure.json',dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
        raise
    finally:budget.finish('report',completed)


if __name__=='__main__':
    import sys
    main(sys.argv[1])
