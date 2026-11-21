"""English local report and ten deterministic scientific figures."""
from html import escape
import io
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import Normalize
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import box

from data3001.modelling.common.prediction_regions import probability_region

COLORS=['#2563a6','#dc7633']
NAMES=['Annual B2','Seasonal B2 (c=1)']
SEASONS=['DJF','MAM','JJA','SON']
_TIMING_ONLY=False


def put_text(paths,p,text):
    paths.publish(p,lambda f:f.write(text.encode('utf-8')))


def save_figure(paths,run,name,fig):
    if _TIMING_ONLY:
        fig.text(.5,.005,'TIMING FIXTURE — SYNTHETIC TARGETS — NOT VALIDATION RESULTS',ha='center',fontsize=9,color='#a93226')
    buffer=io.BytesIO();fig.savefig(buffer,format='png',dpi=140,facecolor='white',metadata={'Software':'DATA3001 S4 E1 v2'})
    plt.close(fig);paths.publish(run['results']/name,lambda f:f.write(buffer.getvalue()))


def land_polygons(geom):
    if geom.geom_type=='Polygon':return [np.asarray(geom.exterior.coords)]
    result=[]
    for g in getattr(geom,'geoms',[]):result.extend(land_polygons(g))
    return result


def write_report(paths,run,bundle,matrices,support,summary,intervals,flags,slices,audit,timing_only=False):
    global _TIMING_ONLY
    _TIMING_ONLY=timing_only
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    names=[]
    fig,axes=plt.subplots(1,3,figsize=(12,4),layout='constrained')
    for ax,m,title in zip(axes,['brier','k90','h90'],['Brier (lower is better)','Mean cells in 90% region','Actual hits in 90% region']):
        for j,model in enumerate(['B2Annual','B2SeasonalC1']):
            z=summary.loc[summary.model==model].sort_values('horizon_days')
            values=z[m].to_numpy();bars=ax.bar(np.arange(2)+(.36*j-.18),values,width=.34,color=COLORS[j],label=NAMES[j])
            for rect,v in zip(bars,values):ax.annotate(f'{v:.2%}' if m=='h90' else f'{v:.4f}' if m=='brier' else f'{v:.2f}',(rect.get_x()+rect.get_width()/2,v),xytext=(0,4),textcoords='offset points',ha='center',fontsize=8)
        ax.set_xticks([0,1],['7 days','30 days']);ax.set_title(title);ax.margins(y=.2)
        if m=='h90':ax.yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].legend(fontsize=8);fig.suptitle('2020–2022 validation | matched cases and drifter/origin weights')
    name='metrics.png';save_figure(paths,run,name,fig);names.append(name)
    fig,axes=plt.subplots(1,3,figsize=(12,4),layout='constrained')
    for ax,m,title in zip(axes,['brier','k90','h90'],['Brier difference','Region-size difference (cells)','Hit-rate difference (percentage points)']):
        for y,h in enumerate([7,30]):
            x=float(flags.loc[flags.horizon_days==h,'delta_'+m].iloc[0]);ci=intervals.loc[(intervals.horizon_days==h)&(intervals.metric==m)].iloc[0]
            scale=100 if m=='h90' else 1
            ax.plot([ci.lower95*scale,ci.upper95*scale],[y,y],color=COLORS[y],lw=3)
            ax.scatter([x*scale],[y],color=COLORS[y],s=45,zorder=3)
        ax.axvline(0,color='#5d6d7e',ls='--',lw=1);ax.set_yticks([0,1],['7 days','30 days']);ax.set_ylim(-.5,1.5);ax.set_title(title)
    fig.suptitle('Seasonal minus annual | paired conditional 95% intervals (10,000 ID draws)')
    name='paired_differences.png';save_figure(paths,run,name,fig);names.append(name)
    fig,axes=plt.subplots(1,2,figsize=(12,9),layout='constrained')
    v=bundle['validation']
    for ax,h in zip(axes,[7,30]):
        observed=sorted(bundle['train'].loc[bundle['train'].horizon_days==h,'origin_cell_1'].unique())
        piv=support.loc[(support.horizon_days==h)&support.departure_season.ge(0)&support.origin_cell_1.isin(observed)].pivot(index='origin_cell_1',columns='departure_season',values='ids').reindex(observed)
        image=ax.imshow(piv.to_numpy(),aspect='auto',cmap='Blues',vmin=0,vmax=float(support.ids.max()))
        for y,i in enumerate(observed):
            for s in range(4):
                n=int(piv.loc[i,s]);ax.text(s,y,str(n),ha='center',va='center',fontsize=7,color='black')
                if n==0 and ((v.horizon_days==h)&(v.origin_cell_1==i)&(v.departure_season==s)).any():ax.plot(s,y,marker='s',ms=17,mfc='none',mec='#d35400',mew=2)
        ax.set_xticks(range(4),SEASONS);ax.set_yticks(range(len(observed)),observed,fontsize=7);ax.set_title(f'{h} days | distinct training IDs')
    fig.colorbar(image,ax=axes,shrink=.5,label='Distinct IDs (diagnostic, not a threshold)')
    fig.suptitle('Training seasonal support | orange outline: evaluated annual-fallback row')
    name='seasonal_support.png';save_figure(paths,run,name,fig);names.append(name)
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for hi,h in enumerate([7,30]):
        ax=axes[0,hi]
        for data,color,label in [(bundle['train'],COLORS[0],'Training'),(v,COLORS[1],'Validation')]:
            z=data.loc[data.horizon_days==h].assign(year=lambda d:d.origin_time_UTC.dt.year).groupby('year').id.nunique()
            ax.bar(z.index,z.values,color=color,label=label)
        ax.axvline(2019.5,color='gray',ls='--');ax.set_title(f'{h} days: distinct IDs by departure year');ax.legend(fontsize=8);ax.set_xticks(range(2012,2023,2))
        ax=axes[1,hi]
        for mi,model in enumerate(['B2Annual','B2SeasonalC1']):
            z=slices.loc[(slices.horizon_days==h)&(slices.model==model)&(slices.dimension=='departure_season')].sort_values('value')
            ax.plot(z.value.astype(int),z.brier,marker='o',color=COLORS[mi],label=NAMES[mi])
        ax.set_xticks(range(4),SEASONS);ax.set_title(f'{h} days: descriptive seasonal Brier');ax.set_ylabel('Original weights conditioned on season');ax.legend(fontsize=8)
    fig.suptitle('Composition and descriptive slices | repeated IDs across years are not independent')
    name='composition_and_seasons.png';save_figure(paths,run,name,fig);names.append(name)
    # Pinned land is presentation only. No trajectory geometry is recomputed.
    land=shapely.from_wkb(paths.asset('land_mask_intermediate').read_bytes())
    states=bundle['states']
    for origin in [44744,44742,44382]:
        positive=set()
        maximum=0.
        for h in [7,30]:
            for s in [-1,0,1,2,3]:
                p=matrices[(h,origin,s)]
                if p is not None:
                    positive.update(int(j) for j in states[p>0] if j>=0);maximum=max(maximum,float(p.max()))
        positive.add(origin)
        lons=[j%360-180 for j in positive];lats=[j//360-90 for j in positive]
        extent=(max(-83,min(lons)-2),min(-6,max(lons)+3),max(19,min(lats)-2),min(56,max(lats)+3))
        rings=land_polygons(land.intersection(box(extent[0],extent[2],extent[1],extent[3])).simplify(.035,preserve_topology=True))
        norm=Normalize(0,max(maximum,1e-6))
        for h in [7,30]:
            fig,axes=plt.subplots(1,5,figsize=(18,4.7),layout='constrained',sharex=True,sharey=True)
            for ax,s,title in zip(axes,[-1,0,1,2,3],['Annual B2',*SEASONS]):
                p=matrices[(h,origin,s)]
                row=support.loc[(support.horizon_days==h)&(support.origin_cell_1==origin)&(support.departure_season==s)].iloc[0]
                ax.set_xlim(extent[:2]);ax.set_ylim(extent[2:]);ax.set_aspect(1/np.cos(np.deg2rad(np.mean(extent[2:]))))
                ax.set_xlabel('Longitude');ax.tick_params(labelsize=8)
                if p is None:ax.text(.5,.5,'Unsupported',transform=ax.transAxes,ha='center')
                else:
                    mask,reg=probability_region(p,states)
                    cells=[(int(j),float(pj),bool(m)) for j,pj,m in zip(states,p,mask) if j>=0 and pj>0]
                    verts=[];values=[];outlines=[]
                    for j,pj,m in cells:
                        x,y=j%360-180,j//360-90;poly=[(x,y),(x+1,y),(x+1,y+1),(x,y+1)]
                        verts.append(poly);values.append(pj)
                        if m:outlines.append(poly)
                    pc=PolyCollection(verts,array=np.asarray(values),cmap='YlOrRd',norm=norm,edgecolors='none');ax.add_collection(pc)
                    ax.add_collection(PolyCollection(rings,facecolors='#d6dbdf',edgecolors='#87949c',linewidths=.3))
                    ax.add_collection(PolyCollection(outlines,facecolors='none',edgecolors='#263238',linewidths=.45))
                    x,y=origin%360-180,origin//360-90
                    ax.plot(x+.5,y+.5,marker='*',color='#006b65',mec='white',ms=10)
                    title+=f'\nK90={reg["region90_cells"]}, mass={reg["region90_mass"]:.1%}'
                subtitle='ANNUAL FALLBACK' if row.annual_fallback else f'{int(row.ids)} IDs; {int(row.pairs):,} pairs'
                ax.set_title(title+'\n'+subtitle,fontsize=9)
            axes[0].set_ylabel('Latitude')
            sm=plt.cm.ScalarMappable(norm=norm,cmap='YlOrRd');fig.colorbar(sm,ax=axes,shrink=.7,label='Probability per cell',format=PercentFormatter(1))
            fig.suptitle(f'Origin {origin} | {h} days | training-only illustrations, 2012–2019\nBlack outlines: nominal 90% set; green star: origin; identical scale across seasons and horizons',fontsize=11)
            name=f'map_{origin}_{h}d.png';save_figure(paths,run,name,fig);names.append(name)
    assert len(names)==10
    view=summary[['horizon_days','model','brier','k90','h90','fallback_pairs','annual_fallback']].sort_values(['horizon_days','model']).copy()
    view['h90']=view.h90*100;view['annual_fallback']=view.annual_fallback*100
    view=view.rename(columns={'h90':'H90 (%)','k90':'K90 (cells)','annual_fallback':'Fallback weight (%)'})
    limitations=['Chronological development backtest, not a new untouched final test. Earlier project use of development data remains a limitation.',
        'Both fits use permitted 2012–2019 pairs only. Validation is available 2020–2022 data, with 45 / 42 IDs at 7 / 30 days; 2022 is incomplete.',
        'Training uses raw pairs. Evaluation averages times within ID/origin, then IDs within origin, then origins equally. Seasons are not given extra full votes.',
        'The nominal region contains at least 90% fitted probability with cutoff ties; this is not a guarantee of 90% observed coverage. K90 counts cells, not physical area.',
        'Conditional paired intervals hold fitted models fixed and omit training uncertainty and shared ocean forcing. Six directional screens are approximate resampling evidence.',
        'Sparse seasonal empirical rows may be noisy. Failure of c=1 does not establish that season, SST or other features cannot help.',
        'Annual fallback preserves unsupported-season cases. It is not model-level fallback after observing validation quality. No future window or weight was searched.']
    conclusion='; '.join(f'{int(r.horizon_days)} days: {r.status}' for r in flags.itertuples(index=False))
    body=['# Step 4 E1 v2 — Chronological Seasonal B2 Comparison','',f'Run: `{run["results"].name}`. Results submitted for user review; model retention remains undecided.','',
          '## Design','', 'Training: 2012–2019, with labels requiring observations at/after 2020 removed, then all validation IDs removed at both horizons. Validation: available 2020–2022 departures. Standard Brier and fixed 90% regions. Two untuned models only.','',
          '## Results','',view.to_csv(index=False),'',conclusion,'','Complete exact values: [summary.csv](summary.csv), [contrasts.csv](contrasts.csv), [uncertainty.csv](uncertainty.csv), [descriptive_slices.csv](descriptive_slices.csv).','',
          '## Visual comparison','']
    for name in names:body.extend([f'![{name}]({name})',''])
    body+=['## Limitations','',*[f'- {s}' for s in limitations],'','## Verification','',json.dumps(audit,sort_keys=True),'',
           'Scientific input roles, forecasts and original weights were frozen before validation scoring. Independent arithmetic checks and fresh-replay status are in the matching provenance directory. The successful deliverable alias is created only after replay verification.']
    if timing_only:body.insert(0,'# TIMING FIXTURE — SYNTHETIC TARGETS — NOT VALIDATION RESULTS\n')
    put_text(paths,run['results']/'REPORT.md','\n'.join(body)+'\n')
    html=['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>S4 E1 — Seasonal B2</title>',
          '<style>body{font:16px/1.6 system-ui;color:#193549;background:#f7f9fb;max-width:1400px;margin:36px auto;padding:0 24px}h1{font-size:34px}h2{margin-top:36px}table{border-collapse:collapse;background:white;width:100%;font-size:14px}td,th{padding:10px;border-bottom:1px solid #dfe6ec;text-align:right}img{width:100%;background:white;margin:12px 0;border-radius:8px}.notice{padding:16px;background:#eaf1f6;border-left:4px solid #2563a6}code{overflow-wrap:anywhere}a{color:#17619b}.scroll{overflow:auto}</style></head><body>',
          '<h1>Does departure season improve destination forecasts?</h1><p>Step 4 E1 v2 · 2012–2019 training → 2020–2022 validation · Development evidence</p>',
          f'<p class="notice">{escape(conclusion)}</p>',
          '<h2>Matched comparison</h2><p>Brier: lower is better. H90: actual hit rate. K90: mean geographic cells in the nominal 90% region.</p><div class="scroll">'+view.to_html(index=False,border=0,float_format=lambda x:f'{x:.6f}')+'</div>',
          '<h2>Seasonal fallback</h2><p>7 days: 41 cases, 0.121% of pairs but 2.778% of evaluation weight. 30 days: no cases. Both models have annual support for every validation case. Fallback cases remain in every primary score.</p>',
          '<h2>Figures</h2>']
    html += [f'<a href="{name}"><img loading="lazy" src="{name}" alt="{escape(name)}"></a>' for name in names]
    html += ['<h2>Interpretation limits</h2><ul>'+''.join('<li>'+escape(s)+'</li>' for s in limitations)+'</ul>',
             '<p><a href="REPORT.md">Full report</a> · <a href="summary.csv">Metrics</a> · <a href="contrasts.csv">Differences and decisions</a> · <a href="uncertainty.csv">Intervals</a> · <a href="descriptive_slices.csv">Season/year breakdowns</a></p>',
             '<p><code>'+escape(run['results'].name)+'</code></p></body></html>']
    if timing_only:html.insert(2,'<p class="notice">TIMING FIXTURE — SYNTHETIC TARGETS — NOT VALIDATION RESULTS</p>')
    put_text(paths,run['results']/'review.html',''.join(html))
    return names
