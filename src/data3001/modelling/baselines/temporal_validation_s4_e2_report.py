"""Local English review of existing-model validation with deterministic figures."""
from html import escape
import io
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import Normalize
from matplotlib.ticker import PercentFormatter
import shapely
from shapely.geometry import box
from data3001.modelling.baselines.seasonal_conditioning_s4_e1_report import land_polygons
from data3001.modelling.baselines.temporal_validation_s4_e2 import MODELS

COLORS={'G':'#2369a5','T':'#d77826'}


def write_report(paths,run,bundle,outer,cache,meta,summary,intervals,flags,selections,roster,config,origin,timing_only=False):
    names=[]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    def save(name,fig):
        if timing_only:fig.text(.5,.004,'SYNTHETIC OUTER TARGETS — RESOURCE PILOT ONLY',ha='center',color='#b03a2e')
        buffer=io.BytesIO();fig.savefig(buffer,format='png',dpi=140,facecolor='white',metadata={'Software':'DATA3001 temporal validation S4 E2'})
        plt.close(fig);paths.publish(run['results']/name,lambda f:f.write(buffer.getvalue()));names.append(name)
    fig,ax=plt.subplots(figsize=(12,4),layout='constrained')
    for k,b in enumerate(config['blocks']):
        cut=int(b['cutoff'][:4]);end=int(b['end'][:4])
        ax.barh(k,cut-2001,left=2001,height=.45,color='#547d99',label='Shared final fitting period' if k==0 else None)
        ax.barh(k,end-cut,left=cut,height=.45,color='#cf8a48',label='Shared later validation period' if k==0 else None)
        ax.text(2001.3,k,'G: whole-ID CV   |   T: forward ID-isolated CV',va='center',color='white',fontsize=9)
    ax.set_yticks(range(3),['A','B','C']);ax.set_xticks(range(2001,2024,2));ax.set_xlim(2000.7,2023.2)
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.12),ncol=2);ax.set_title('Existing models; two selection policies; identical final training and evaluation within each block')
    save('validation_design.png',fig)
    labels=['B2','Fixed','Adaptive','Local EP','Local EP adaptive','Selected']
    for h in [7,30]:
        fig,axes=plt.subplots(3,3,figsize=(15,10),layout='constrained')
        for bi,b in enumerate(['A','B','C']):
            for mi,(m,title) in enumerate([('brier','Brier (lower is better)'),('k90','90% region cells'),('h90','Actual 90% region hits')]):
                ax=axes[bi,mi]
                for policy in ['G','T']:
                    z=summary[(summary.horizon_days==h)&(summary.block==b)&(summary.policy==policy)].set_index('model').reindex([*MODELS,'Selected'])
                    ax.plot(range(6),z[m],marker='o' if policy=='G' else 's',color=COLORS[policy],label=policy,ms=5)
                ax.set_xticks(range(6),labels,rotation=35,ha='right',fontsize=8);ax.set_title(f'Block {b} | {title}')
                if m=='h90':ax.yaxis.set_major_formatter(PercentFormatter(1));ax.set_ylim(0,1)
                if bi==0 and mi==0:ax.legend(title='Selection policy')
        fig.suptitle(f'{h}-day forward validation | equal drifter/origin weights | all selected family variants')
        save(f'metrics_{h}d.png',fig)
    fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
    for hi,h in enumerate([7,30]):
        for mi,m in enumerate(['brier','h90','relative_k90']):
            ax=axes[hi,mi];scale=100 if m in ['h90','relative_k90'] else 1.
            for bi,b in enumerate(['A','B','C']):
                c=intervals[(intervals.block==b)&(intervals.horizon_days==h)&(intervals.metric==m)].iloc[0]
                f=flags[(flags.block==b)&(flags.horizon_days==h)].iloc[0]
                point=f[m if m=='relative_k90' else 'delta_'+m]
                ax.plot([c.adjusted_lower*scale,c.adjusted_upper*scale],[bi,bi],lw=1,color='#9ca4ad')
                ax.plot([c.lower95*scale,c.upper95*scale],[bi,bi],lw=4,color=COLORS['G'])
                ax.scatter(point*scale,bi,color=COLORS['T'],zorder=3)
            margin=config['equivalence'][m]*scale
            ax.axvspan(-margin,margin,color='#d5eadb',alpha=.7);ax.axvline(0,color='gray',ls='--')
            ax.set_yticks(range(3),['A','B','C']);ax.set_title(f'{h} days | '+{'brier':'Brier difference','h90':'Hit difference (pp)','relative_k90':'Region-size difference (%)'}[m])
    fig.suptitle('T-selected minus G-selected | thick: 95% | thin: adjusted | green: approved equivalence range')
    save('selected_differences.png',fig)
    land=shapely.from_wkb(paths.asset('land_mask_intermediate').read_bytes());states=bundle['states']
    for b in ['A','B','C']:
        for h in [7,30]:
            items=[cache[(b,'G','B2',h,origin)],cache[(b,'G','Selected',h,origin)],cache[(b,'T','Selected',h,origin)]]
            cells=set(int(j) for item in items if item is not None for j in states[item['p']>0] if j>=0)
            if not cells:continue
            xs=[j%360-180 for j in cells];ys=[j//360-90 for j in cells]
            bounds=(max(-82,min(xs)-1),max(19,min(ys)-1),min(-7,max(xs)+2),min(56,max(ys)+2))
            vmax=max(float(item['p'].max()) for item in items if item is not None);norm=Normalize(0,vmax)
            fig,axes=plt.subplots(1,3,figsize=(15,5),layout='constrained')
            for ax,item,title in zip(axes,items,['B2','G-selected','T-selected']):
                if item is None:ax.set_title(title+' | unsupported');continue
                geo=np.flatnonzero((states>=0)&(item['p']>0));polygons=[]
                for idx in geo:
                    j=int(states[idx]);x=j%360-180;y=j//360-90
                    polygons.append([(x,y),(x+1,y),(x+1,y+1),(x,y+1)])
                pc=PolyCollection(polygons,array=item['p'][geo],cmap='Blues',norm=norm,edgecolor='none');ax.add_collection(pc)
                selected=[poly for poly,idx in zip(polygons,geo) if item['mask'][idx]]
                ax.add_collection(PolyCollection(selected,facecolor='none',edgecolor='#27936a',linewidth=.45))
                clip=land.intersection(box(*bounds));ax.add_collection(PolyCollection(land_polygons(clip),facecolor='#d4d6d8',edgecolor='#888',linewidth=.3))
                x=origin%360-180;y=origin//360-90;ax.plot([x+.5],[y+.5],marker='*',color='#d35400',ms=10)
                ax.set_xlim(bounds[0],bounds[2]);ax.set_ylim(bounds[1],bounds[3]);ax.set_aspect(1/np.cos(np.deg2rad(np.mean(bounds[1::2]))))
                ax.set_xlabel('Longitude');ax.set_ylabel('Latitude')
                ax.set_title(f'{title} | K90={item["k90"]} | mass={item["region_mass"]:.1%}\nExit probability={item["predicted_exit"]:.3f}')
            fig.colorbar(pc,ax=axes,shrink=.6,label='Probability per 1-degree cell')
            fig.suptitle(f'Block {b}, {h} days | origin {origin} selected using fitting support only | green: 90% region')
            save(f'map_{b}_{h}d.png',fig)
    chosen=selections[selections.winner][['block','policy','horizon_days','model','parameter_a','parameter_gamma','brier']].rename(columns={'brier':'inner_selection_brier'})
    primary=summary[summary.model=='Selected'][['block','policy','horizon_days','brier','k90','h90','zero_truth','unsupported_pairs']]
    title='Existing Step 1–3 models: validation-policy comparison'
    note='SYNTHETIC OUTER TARGETS — CAPACITY ONLY. ' if timing_only else ''
    explanation=(note+'G uses whole-ID, calendar-mixed internal CV. T uses forward, ID-isolated internal CV. '
        'Each block uses identical final fitting data and later validation cases. This is a model-selection-policy comparison, '
        'not a new model, a physical ocean change-point test, or an untouched final test. All models retain annual pooling. '
        'Outer metrics use equal times within drifter/origin, equal drifters within origin, and equal origins. '
        'Intervals condition on fitted forecasts; training and selection uncertainty and common forcing are not fully represented. '
        'B2 equality across policies is a required control. Similarity margins do not relax the quality-preserving improvement criterion.')
    support=selections[selections.winner][['block','policy','horizon_days','eligible_pairs','scored_pairs','eligible_ids','scored_ids','scored_origins','unsupported_pairs']].copy()
    support['scored_pair_fraction']=support.scored_pairs/support.eligible_pairs
    tables=[('Policy-selected future predictions',primary),('Inner-selected models and parameters',chosen),('Primary decisions',flags),
            ('Inner evaluation support',support),
            ('All family comparisons',summary),('Role support',roster)]
    html='<!doctype html><html lang="en"><meta charset="utf-8"><title>'+title+'</title><style>body{font:16px system-ui;max-width:1400px;margin:35px auto;padding:0 20px;color:#203040}img{width:100%;height:auto}table{border-collapse:collapse;font-size:13px}td,th{padding:7px;border-bottom:1px solid #dde3e8;text-align:right}section{overflow:auto;margin:28px 0}p{line-height:1.6}</style><h1>'+title+'</h1><p>'+escape(explanation)+'</p>'
    for title,table in tables:html+='<section><h2>'+title+'</h2>'+table.to_html(index=False,float_format=lambda x:f'{x:.6f}')+'</section>'
    calendar=run['results']/('..' if timing_only else '.')/'validation_calendar_composition.csv'
    if calendar.exists():html+='<p>Role-specific year and season composition: <a href="'+('../' if timing_only else '')+'validation_calendar_composition.csv">download counts and supported fractions</a>.</p>'
    html+=''.join('<img alt="'+escape(n)+'" src="'+n+'">' for n in names)+'</html>'
    paths.publish(run['results']/'review.html',lambda f:f.write(html.encode()))
    report='# Existing Step 1–3 models: validation-policy comparison\n\n'+explanation+'\n\n'
    for title,table in tables[:3]:report+='## '+title+'\n\n```csv\n'+table.to_csv(index=False)+'```\n\n'
    report+='See summary.csv, uncertainty.csv, decisions.csv, selections.csv, role_roster.csv and review.html for complete evidence.\n'
    paths.publish(run['results']/'REPORT.md',lambda f:f.write(report.encode()))
    return names
