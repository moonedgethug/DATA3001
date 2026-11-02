"""English E2 report and matched figures; no parameter selection."""
from html import escape
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle, Polygon
from matplotlib.colors import Normalize
import shapely
from shapely.geometry import shape,box

from data3001.modelling.baselines.adaptive_b2_b1_report import save_plot
from data3001.modelling.common.plotting import _rings,markdown_table
from data3001.modelling.common.prediction_regions import probability_region

COLORS={'B2':'#697c85','Fixed':'#d18435','E1Adaptive':'#a27ca9','Info':'#197d8d','Weight':'#534dae'}


def make_maps(paths,run,base,vectors,weights):
    support=base.b2.support.pivot(index='origin_cell_1',columns='horizon_days',values='training_id_count')
    ranks=support.min(axis=1).sort_index().sort_values(ascending=False,kind='stable')
    if ranks.empty or ranks.iloc[0]<=0:return None,[]
    origin=int(ranks.index[0]);names=[]
    release=shape(json.loads(paths.asset('release_R').read_text())['features'][0]['geometry'])
    domain=shape(json.loads(paths.asset('transport_D').read_text())['features'][0]['geometry'])
    land=shapely.from_wkb(paths.asset('land_mask_intermediate').read_bytes()).intersection(box(-83,19,-6,56)).simplify(.025)
    polygons=[p for p in getattr(land,'geoms',[land]) if p.geom_type=='Polygon']
    for h in (7,30):
        maximum=max(vectors[m][(h,origin)].max() for m in COLORS);norm=Normalize(0,maximum)
        fig,axes=plt.subplots(5,1,figsize=(13,18),layout='constrained')
        for ax,model in zip(axes,COLORS):
            p=vectors[model][(h,origin)];region,meta=probability_region(p,base.states)
            patches=[];values=[];outlines=[]
            for j,cell in enumerate(base.states):
                if cell<0:continue
                x,y=cell%360-180,cell//360-90
                if p[j]>0:patches.append(Rectangle((x,y),1,1));values.append(p[j])
                if region[j]:outlines.append(Rectangle((x,y),1,1))
            pc=PatchCollection(patches,cmap='Blues',norm=norm,edgecolor='none');pc.set_array(np.asarray(values));ax.add_collection(pc)
            ax.add_collection(PatchCollection([Polygon(np.asarray(g.exterior.coords)) for g in polygons],facecolor='#e2e5e5',edgecolor='#9aa6aa',linewidth=.3))
            ax.add_collection(PatchCollection(outlines,facecolor='none',edgecolor='#8d3c87',linewidth=.5))
            for geom,color,style in [(release,'#25865a','-'),(domain,'#778b97','--')]:
                for ring in _rings(geom):
                    a=np.asarray(ring);ax.plot(a[:,0],a[:,1],color=color,ls=style,lw=.7)
            ax.add_patch(Rectangle((origin%360-180,origin//360-90),1,1,fill=False,edgecolor='#e2542f',lw=1.4))
            row=weights[weights.model.eq(model)&weights.horizon_days.eq(h)&weights.origin_cell_1.eq(origin)].iloc[0]
            ax.set(xlim=(-83,-6),ylim=(19,56),xlabel='Longitude',ylabel='Latitude')
            ax.set_title(f'{model} | B1 weight {row.borrowing_weight:.3f} | 90%: {meta["region90_cells"]} cells | E {p[base.index[-2]]:.2%}, U 0%',loc='left',fontsize=10)
            ax.grid(alpha=.12);ax.set_facecolor('#f5f9fc')
        row=weights[weights.model.eq('B2')&weights.horizon_days.eq(h)&weights.origin_cell_1.eq(origin)].iloc[0]
        fig.colorbar(pc,ax=axes,label='Probability per cell; shared scale across models',shrink=.65)
        fig.suptitle(f'E2 {h}-day fitted candidates | origin {origin} | {int(row.training_pair_count):,} pairs, {int(row.training_id_count)} IDs\n'
                     'Purple: 90% region. Orange: origin. Candidate maps are not held-out performance.',fontsize=12)
        name=f'candidate_comparison_{h}d.png';save_plot(paths,run,name,fig);names.append(name)
    return origin,names


def diagnostic_plots(paths,run,summary,differences,diagnostics,weights):
    names=[];fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
    for row,h in enumerate((7,30)):
        for col,metric in enumerate(('brier','region90_cells','region90_hit')):
            ax=axes[row,col];scale=100 if metric=='region90_hit' else 1
            for j,model in enumerate(('Info','Weight')):
                r=differences[differences.horizon_days.eq(h)&differences.model.eq(model)&differences.metric.eq(metric)].iloc[0]
                ax.plot([j,j],scale*np.array([r.adjusted_lower,r.adjusted_upper]),color=COLORS[model],lw=2,alpha=.4)
                ax.plot([j,j],scale*np.array([r.lower_95,r.upper_95]),color=COLORS[model],lw=5)
                ax.scatter(j,scale*r.difference,color=COLORS[model],s=45,zorder=3)
            ax.axhline(0,color='#647780',lw=.7);ax.set_xticks([0,1],['Info','Weight'])
            ax.set_title(f'{h} days: '+{'brier':'Brier difference','region90_cells':'Cell-count difference','region90_hit':'Hit difference (pp)'}[metric]);ax.grid(axis='y',alpha=.2)
    fig.suptitle('Differences from Fixed | points, 95% intervals and adjusted directional bounds\nNegative favors Brier/cells; positive favors hits. Fixed-fit whole-ID uncertainty.',fontsize=12)
    save_plot(paths,run,'quality_and_region_differences.png',fig);names.append('quality_and_region_differences.png')
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    columns=sorted([c for c in summary if c.startswith('hit_k_')],key=lambda c:int(c[6:]));ks=[int(c[6:]) for c in columns]
    for ax,h in zip(axes,(7,30)):
        for model,color in COLORS.items():
            r=summary[summary.horizon_days.eq(h)&summary.model.eq(model)].iloc[0]
            ax.plot(ks,100*r[columns].to_numpy(float),'.-',label=model,color=color,lw=1)
        ax.set(xscale='log',ylim=(0,101),xlabel='Exact D-cell budget K',ylabel='Held-out hit rate (%)',title=f'{h} days');ax.legend();ax.grid(alpha=.2)
    fig.suptitle('Matched-budget diagnostic only | uniform boundary ties, including zero ties')
    save_plot(paths,run,'budget_hit_curves.png',fig);names.append('budget_hit_curves.png')
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for ax,h in zip(axes,(7,30)):
        g=diagnostics[diagnostics.scope.eq('overall')&diagnostics.horizon_days.eq(h)].set_index('model')
        for j,(model,color) in enumerate(COLORS.items()):
            ax.bar(j,100*g.loc[model,'unseen_D_probability'],color=color,label=model)
        ax.axhline(100*g.loc['Fixed','true_unseen_D'],color='#233b4e',ls='--',label='Observed frequency')
        ax.set_xticks(range(5),COLORS,rotation=20);ax.set(ylabel='Probability / frequency (%)',title=f'{h} days');ax.legend(fontsize=8)
    fig.suptitle('Locally unseen D destinations | fitted support, complete held-out cases')
    save_plot(paths,run,'unseen_destination_mass.png',fig);names.append('unseen_destination_mass.png')
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for ax,h in zip(axes,(7,30)):
        for model,color in COLORS.items():
            g=weights[weights.model.eq(model)&weights.horizon_days.eq(h)&weights.supported].sort_values('training_pair_count')
            ax.plot(g.training_pair_count,g.borrowing_weight,'.-',color=color,label=model,lw=1)
        ax.set(xscale='log',ylim=(-.03,1.03),xlabel='Fitting hourly-pair count',ylabel='B1 weight',title=f'{h} days');ax.legend();ax.grid(alpha=.2)
    fig.suptitle('All-development candidate weights | pair counts are not independent sample sizes')
    save_plot(paths,run,'weights_by_support.png',fig);names.append('weights_by_support.png')
    return names


def write_report(paths,run,summary,differences,decisions,selected,diagnostics,base,vectors,weights,verification):
    origin,maps=make_maps(paths,run,base,vectors,weights)
    figures=diagnostic_plots(paths,run,summary,differences,diagnostics,weights)+maps
    view=summary[['horizon_days','model','evaluable_pairs','evaluable_ids','brier','region90_cells','region90_hit','unsupported_pairs']].copy()
    view['region90_hit_percent']=100*view.pop('region90_hit')
    params=selected[['role','horizon_days','model','parameter_a','parameter_c','parameter_beta','selection_status']]
    limits=[
        'This is development evidence on previously examined IDs, not final-test validation. No final-test trajectories were read.',
        'Selection uses inner Brier/hit constraints and strictly smaller 90% regions versus a Brier-selected Fixed anchor. It does not guarantee the constraints on outer cases.',
        'Info adjusts only B1 D allocation, preserving B1 E mass and positive support. Weight changes only the pair-count slope. The two changes were not combined.',
        'The 90% level is fixed; the full distribution and all eligible observed outcomes are retained. Nominal probability is not actual coverage, and cell count is not area.',
        '5,000 paired whole-ID bootstrap draws hold fits and selections fixed. They omit refitting, training-overlap and research-adaptation uncertainty. Adjusted bounds are a conservative conditional development screen, not a formal population non-inferiority proof.',
        'A point-estimate pass with bounds allowing quality deterioration remains inconclusive. The practical Brier and hit margins are zero.',
        'All-development maps use a support-only selected origin and are illustrative refits. Their parameters can differ from the outer-fold procedure.',
        'Unsupported rows have no forecast or Brier for every model. Empirical zeros are scored normally; no B1 fallback or tail deletion is used.',
        'No observed exits means exit calibration remains unestablished. Later combined models and S2 closure require user review.',
    ]
    narrative=[]
    for r in decisions.itertuples(index=False):
        narrative.append(f'{r.horizon_days} days, {r.model} versus Fixed: {r.outcome}; Brier {r.delta_brier:+.8f}, '
                         f'90% cells {r.delta_region90_cells:+.3f}, actual hits {100*r.delta_region90_hit:+.3f} percentage points.')
    md=['# Step 2 — E2 B1 Allocation and Weight Control','',f'Run: `{run["results"].name}`. Executed and audited; scientific closure pending user review.','',
        '## Main findings','',*narrative,'','## Matched outer development results','',markdown_table(view,list(view.columns)),'',
        'Rows use the same supported cases within each horizon and retain original pair multiplicities. The two horizons have different eligible populations.','',
        '## Differences and uncertainty','',markdown_table(differences,list(differences.columns)),'',
        'Hit differences in the CSV/table are fractions; multiply by 100 for percentage points. Adjusted bounds use one-sided tail 0.05/12.','',
        '## Methods','',
        'Fixed is original B1/B2 with a Brier-selected constant weight. Info scales B1 probabilities of locally unseen D destinations by c, renormalises within the original D mass and preserves E. Weight uses lambda=a/[a+(1-a)(N/m)^beta]. B2 and E1Adaptive are fresh controls.','',
        'A={0,0.05,...,1}; C={0.5,0.75,1,1.5,2}; Beta={0,0.25,0.5,0.75,1}. Each new arm has 105 candidates. Five outer/four inner whole-ID groups isolate parameter selection. Exact Fixed fallback occurs when no candidate passes quality constraints with a strict size gain.','',
        '## Selected parameters','',markdown_table(params,list(params.columns)),'',
        'Outer selections assess the complete nested procedure. All-development selections happen only after outer predictions have been frozen, and have no independent performance score.','',
        '## Figures','',f'Illustration origin: {origin}; selected only from fitting support.','']
    for f in figures:md.extend([f'![{f}]({f})',''])
    md.extend(['## Audit','',json.dumps(verification,sort_keys=True),'','## Limits','',*[f'- {s}' for s in limits],
               '','## Artifacts','',
               '[Summary](summary.csv) · [Differences](paired_differences.csv) · [Decisions](decisions.csv) · [Selected parameters](selected_parameters.csv) · [Candidate search](parameter_search.csv) · [Diagnostics](diagnostics.csv) · [Region changes](region_changes.csv) · [Held-out scores](heldout_scores.parquet)',''])
    paths.publish(run['results']/'REPORT.md',lambda out:out.write('\n'.join(md).encode()))
    html=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E2 allocation and weights</title>',
          '<style>body{max-width:1250px;margin:36px auto;padding:0 24px;font:16px/1.55 system-ui;color:#17334a}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:8px;border-bottom:1px solid #dce4e9;text-align:right}th{background:#eef4f7}img{width:100%;height:auto}.scroll{overflow:auto}h2{margin-top:32px}</style>',
          '<h1>E2 · B1 allocation and weight control</h1>',f'<p>{escape(run["results"].name)} · Development results · Review pending</p>',
          *[f'<p>{escape(s)}</p>' for s in narrative],'<h2>Matched held-out results</h2><div class="scroll">'+view.to_html(index=False,border=0,float_format=lambda v:f'{v:.6f}')+'</div>',
          '<h2>Differences and uncertainty</h2><div class="scroll">'+differences.to_html(index=False,border=0,float_format=lambda v:f'{v:.6f}')+'</div>',
          '<p>Hit differences above are fractions, not percentage points.</p>',*[f'<img src="{f}" alt="{f}">' for f in figures],
          '<h2>Limits</h2><ul>'+''.join(f'<li>{escape(s)}</li>' for s in limits)+'</ul><p><a href="REPORT.md">Full report</a> · <a href="summary.csv">Summary</a> · <a href="selected_parameters.csv">Parameters</a></p></html>']
    paths.publish(run['results']/'review.html',lambda out:out.write(''.join(html).encode()))
