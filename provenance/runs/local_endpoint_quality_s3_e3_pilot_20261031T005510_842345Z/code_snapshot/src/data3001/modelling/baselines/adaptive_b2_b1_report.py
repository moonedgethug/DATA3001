"""English S2 report and matched candidate/held-out diagnostic figures."""
from html import escape
from io import BytesIO
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle, Polygon
from matplotlib.colors import Normalize
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import shape, box

from data3001.modelling.common.prediction_regions import probability_region
from data3001.modelling.common.plotting import _rings, markdown_table

COLORS = {'B2':'#197b84', 'Fixed':'#bb692d', 'Adaptive':'#7152a3'}


def save_plot(paths, run, name, fig):
    stream = BytesIO()
    fig.savefig(stream, format='png', dpi=130, facecolor='white', bbox_inches='tight')
    paths.publish(run['results']/name, lambda out: out.write(stream.getvalue()))
    plt.close(fig)


def candidate_maps(paths, run, base, vectors, weights):
    pivot = base.b2.support.pivot(index='origin_cell_1', columns='horizon_days', values='training_id_count')
    ranks = pivot.min(axis=1).sort_index().sort_values(ascending=False, kind='stable')
    if ranks.empty or ranks.iloc[0] <= 0:
        return None, []
    origin = int(ranks.index[0])
    release = shape(json.loads(paths.asset('release_R').read_text())['features'][0]['geometry'])
    domain = shape(json.loads(paths.asset('transport_D').read_text())['features'][0]['geometry'])
    land = shapely.from_wkb(paths.asset('land_mask_intermediate').read_bytes()).intersection(box(-83,19,-6,56)).simplify(.025)
    polygons = [g for g in getattr(land, 'geoms', [land]) if g.geom_type == 'Polygon']
    names = []
    for h in (7,30):
        maximum = max(float(vectors[model][(h,origin)].max()) for model in COLORS)
        norm = Normalize(0, maximum)
        fig, axes = plt.subplots(3,1,figsize=(13,12),layout='constrained')
        for ax, model in zip(axes, COLORS):
            p = vectors[model][(h,origin)]
            region, meta = probability_region(p, base.states)
            patches, values, outlines = [], [], []
            for j,cell in enumerate(base.states):
                if cell < 0:
                    continue
                x,y = cell%360-180,cell//360-90
                if p[j]>0:
                    patches.append(Rectangle((x,y),1,1)); values.append(p[j])
                if region[j]:
                    outlines.append(Rectangle((x,y),1,1))
            pc = PatchCollection(patches,cmap='Blues',norm=norm,edgecolor='none')
            pc.set_array(np.array(values)); ax.add_collection(pc)
            ax.add_collection(PatchCollection([Polygon(np.asarray(g.exterior.coords)) for g in polygons],
                                             facecolor='#e0e3e3',edgecolor='#9da8ad',linewidth=.3))
            ax.add_collection(PatchCollection(outlines,facecolor='none',edgecolor='#8d3c87',linewidth=.5))
            for ring in _rings(release):
                a=np.asarray(ring); ax.plot(a[:,0],a[:,1],color='#25865a',lw=1)
            for ring in _rings(domain):
                a=np.asarray(ring); ax.plot(a[:,0],a[:,1],color='#758696',ls='--',lw=.6)
            ax.add_patch(Rectangle((origin%360-180,origin//360-90),1,1,fill=False,edgecolor='#e2542f',lw=1.6))
            row=weights.loc[weights.model.eq(model)&weights.horizon_days.eq(h)&weights.origin_cell_1.eq(origin)].iloc[0]
            ax.set(xlim=(-83,-6),ylim=(19,56),ylabel='Latitude',xlabel='Longitude')
            ax.set_title(f"{model} | borrowing {row.borrowing_weight:.3f} | 90% region: {meta['region90_cells']} cells | "
                         f"E {p[base.index[-2]]:.3%}, unresolved 0%",loc='left',fontsize=11)
            ax.set_facecolor('#f5f9fc'); ax.grid(alpha=.12)
        fig.colorbar(pc,ax=axes,label='Probability per cell (same scale across models)',shrink=.65)
        fig.suptitle(f'{h}-day fitted candidates | origin {origin} | annual pooled, stopped target\n'
                     'Purple outlines: 90% region. Orange: origin. These maps are not held-out validation.',fontsize=13)
        name=f'candidate_comparison_{h}d.png'; save_plot(paths,run,name,fig); names.append(name)
    return origin,names


def diagnostic_plots(paths,run,weights,summary):
    names=[]
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for ax,h in zip(axes,(7,30)):
        for model in COLORS:
            rows=weights.loc[weights.model.eq(model)&weights.horizon_days.eq(h)&weights.supported].sort_values('training_pair_count')
            ax.plot(rows.training_pair_count,rows.borrowing_weight,'.-',color=COLORS[model],label=model,lw=1)
        ax.set(xscale='log',ylim=(-.03,1.03),xlabel='Fitting hourly-pair count (log)',ylabel='B1 borrowing weight',title=f'{h} days')
        ax.grid(alpha=.2); ax.legend()
    fig.suptitle('All-development candidate weights | counts are not independent sample sizes')
    save_plot(paths,run,'weights_by_support.png',fig); names.append('weights_by_support.png')
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    columns=sorted((c for c in summary if c.startswith('hit_k_')),key=lambda c:int(c[6:]))
    ks=[int(c[6:]) for c in columns]
    for ax,h in zip(axes,(7,30)):
        for model in COLORS:
            row=summary.loc[summary.horizon_days.eq(h)&summary.model.eq(model)].iloc[0]
            ax.plot(ks,[100*row[c] for c in columns],'.-',label=model,color=COLORS[model])
        ax.set(xscale='log',ylim=(0,101),xlabel='Exact D-cell budget K (log)',ylabel='Held-out expected hit rate (%)',title=f'{h} days')
        ax.grid(alpha=.2); ax.legend()
    fig.suptitle('Matched-budget development hits | uniform boundary ties, including zero ties')
    save_plot(paths,run,'budget_hit_curves.png',fig); names.append('budget_hit_curves.png')
    return names


def write_report(paths,run,config,summary,intervals,differences,selected,base,vectors,weights,verification):
    chosen,maps=candidate_maps(paths,run,base,vectors,weights)
    plots=diagnostic_plots(paths,run,weights,summary)
    view=summary[['horizon_days','model','eligible_pairs','eligible_ids','brier','region90_cells','region90_hit','unsupported_pairs']].copy()
    view['region90_hit_pct']=100*view.pop('region90_hit')
    ci=intervals.loc[intervals.metric.eq('brier')].set_index(['horizon_days','model'])
    view['Brier_95_interval']=[f"[{ci.loc[(h,m),'lower_95']:.6f}, {ci.loc[(h,m),'upper_95']:.6f}]" for h,m in zip(view.horizon_days,view.model)]
    contrast=differences.loc[differences.metric.isin(['brier','region90_cells','region90_hit'])].copy()
    parameter_view=selected[['role','horizon_days','model','parameter_a','selection_brier']]
    outcomes=[]
    for h in (7,30):
        tab=summary.loc[summary.horizon_days.eq(h)].set_index('model')
        da=tab.loc['Adaptive']-tab.loc['Fixed']
        met=da.brier<0 and da.region90_cells<0 and da.region90_hit>=0
        outcomes.append(f"{h} days: the prespecified joint point-estimate screen is {'met' if met else 'not met'}. "
                        f"Adaptive minus Fixed: Brier {da.brier:+.6f}; region cells {da.region90_cells:+.3f}; "
                        f"actual hits {100*da.region90_hit:+.3f} percentage points. Read paired intervals before interpreting strength of evidence.")
    limitations=[
        'Five outer / four inner whole-ID development validation on previously examined development data; not independent final-test evidence. The final test remains locked.',
        'Selection uses only inner pair-weighted standard Brier on a common support mask. Region size and hits do not select parameters. The two horizons have different eligible populations.',
        'A is selected on 21 values per family/horizon. Adaptive uses the fitting median pair count as its reference scale; no independent per-cell weights are optimized.',
        'Hourly and overlapping pairs are correlated. 200 paired whole-ID intervals condition on saved fits and omit refitting, parameter-selection and research-selection uncertainty; no multiplicity adjustment.',
        'A smaller nominal 90% region is not a gain if achieved by losing actual coverage. Brier is not an accuracy percentage or a geographic-distance measure.',
        '90% regions retain cutoff ties. E is an outcome, never a geographic cell. Region counts are not square kilometres.',
        'Exact-budget curves average uniformly over boundary ties; zero-probability ties are uninformed allocations, not newly supported predictions. Exit truths are excluded only from these D-cell budget curves and reported in primary score denominators.',
        'Unsupported origin rows remain unsupported for all models, even if B1 exists. Supported rows retain all blended probability; no threshold clipping or tail renormalization.',
        'No observed exits establishes no exit calibration. B1 and B2 share fitting data, so this is a regularized point estimator, not a validated full Bayesian uncertainty model.',
        'All-development maps and selected full-development parameters are illustrative refits; their tuning scores are not independent validation. No S2 closure or next-stage work is automatic.',
    ]
    links=['summary.csv','paired_differences.csv','bootstrap_intervals.csv','selected_parameters.csv','parameter_search.csv',
           'row_support.csv','cell_summary.csv','budget_boundaries.parquet','heldout_scores.parquet','fit_roles.json','config.json']
    md=['# Stage 2 — Fixed and Adaptive B2/B1 Shrinkage','',f"Run: `{run['results'].name}`. E1 implementation and audit complete; scientific closure pending user review.",'',
        '## Definitions','',
        'B2 uses fitting-origin frequencies. B1 pools eligible fitting-origin outcomes across R. Fixed uses one selected weight per horizon. Adaptive uses lambda_i=m*a/((1-a)*N_i+m*a), with m the fitting median positive row count. Both endpoints a=0/1 are explicit. All targets are stopped first-exit outcomes; E and missing follow-up remain distinct.','',
        '## Matched outer held-out results','',markdown_table(view,list(view.columns)),'',
        '90% region size and hits use the same evaluable, pair-weighted cases. Hits are percentages in this table; saved numeric CSV fields use fractions.','',
        '## Paired differences','',markdown_table(contrast,list(contrast.columns)),'',
        'Region-hit differences in the table above are fractions; multiply by 100 for percentage points. Negative Brier/cell differences favor Adaptive; positive hit differences favor Adaptive.','',
        *outcomes,'','## Selected parameters','',markdown_table(parameter_view,list(parameter_view.columns)),'',
        'Outer parameters come from four inner groups. All-development candidate parameters use five-fold base out-of-fold tuning; their selection scores are not final-refit validation.','',
        '## Figures','',f'Illustration origin {chosen} was selected only by fitting-ID support, using the frozen S1 rule.','']
    for name in plots+maps:
        md += [f'![{name}]({name})','']
    md += ['## Numerical audit','',json.dumps(verification,sort_keys=True),'','## Limits','',*[f'- {s}' for s in limitations],
           '','## Artifacts and reproduction','',', '.join(f'[{n}]({n})' for n in links),'',
           '```sh','.venv/bin/python -B -m data3001.modelling.baselines.run_adaptive_b2_b1',
           f'.venv/bin/python -B -m data3001.modelling.baselines.run_adaptive_b2_b1 --replay-of {run["results"].name}','```','']
    paths.publish(run['results']/'REPORT.md',lambda out:out.write('\n'.join(md).encode()))
    html=["<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
          '<title>Stage 2: Adaptive B2/B1</title>',
          '<style>body{max-width:1250px;margin:35px auto;padding:0 24px;font:16px/1.55 system-ui;color:#17334a}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:9px;border-bottom:1px solid #dce4e9;text-align:right}th{background:#eef4f7}img{width:100%;height:auto}li{margin:10px 0}.scroll{overflow:auto}h2{margin-top:36px}a{color:#146d99}</style>',
          '<h1>Stage 2 · Fixed and adaptive B2/B1</h1>',f'<p>{escape(run["results"].name)} · Development results · Scientific review pending</p>',
          '<h2>Matched held-out results</h2><div class="scroll">'+view.to_html(index=False,border=0,float_format=lambda v:f'{v:.6f}')+'</div>',
          '<p>Region-hit percentage and cell count must be read together. Lower Brier is better.</p>',
          *[f'<p>{escape(s)}</p>' for s in outcomes],'<h2>Paired differences</h2><div class="scroll">'+contrast.to_html(index=False,border=0,float_format=lambda v:f'{v:.6f}')+'</div>',
          '<p>Hit differences above are fractions, not percentage points. Fixed-fit paired whole-ID intervals.</p>']
    html += [f'<img src="{name}" alt="{name}">' for name in plots+maps]
    html += ['<h2>Limits</h2><ul>'+''.join(f'<li>{escape(s)}</li>' for s in limitations)+'</ul>',
             '<p><a href="REPORT.md">Full report</a> · <a href="summary.csv">Summary CSV</a> · <a href="selected_parameters.csv">Selected parameters</a></p></html>']
    paths.publish(run['results']/'review.html',lambda out:out.write(''.join(html).encode()))
