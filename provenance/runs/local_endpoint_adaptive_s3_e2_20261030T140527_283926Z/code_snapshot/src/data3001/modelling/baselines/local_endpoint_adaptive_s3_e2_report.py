"""English S3 report and matched complete-probability visual comparisons."""
from html import escape
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle,Polygon
from matplotlib.colors import Normalize
import shapely as sh
from shapely.geometry import shape,box
from data3001.modelling.baselines.adaptive_b2_b1_report import save_plot
from data3001.modelling.common.plotting import _rings,markdown_table as _markdown_table
from data3001.modelling.common.prediction_regions import probability_region
from data3001.modelling.common.qualified_count_inputs import read_frame
from data3001.modelling.baselines.spatial_borrowing_s3_e1_report import strata_tables

COLORS={'B2':'#647986','Fixed':'#c57b32','Adaptive':'#8a62b0','LocalEndpoint':'#239d8f','LocalEndpointAdaptive':'#2568b5'}
SHORT={'B2':'B2','Fixed':'Fixed','Adaptive':'Adaptive','LocalEndpoint':'Local\nEndpoint','LocalEndpointAdaptive':'Local Endpoint\nAdaptive'}


def markdown_table(frame):
    return _markdown_table(frame,list(frame.columns))


def geometry(paths):
    release=shape(json.loads(paths.asset('release_R').read_text())['features'][0]['geometry'])
    domain=shape(json.loads(paths.asset('transport_D').read_text())['features'][0]['geometry'])
    high=sh.from_wkb(paths.asset('land_mask_high').read_bytes())
    land=sh.from_wkb(paths.asset('land_mask_intermediate').read_bytes()).intersection(box(-84,18,-5,57)).simplify(.025)
    return release,domain,high,land


def backdrop(ax,release,domain,land):
    pieces=[g for g in getattr(land,'geoms',[land]) if g.geom_type=='Polygon']
    ax.add_collection(PatchCollection([Polygon(np.asarray(g.exterior.coords)) for g in pieces],facecolor='#e4e7e9',edgecolor='#9aa8af',linewidth=.25,zorder=4))
    for geom,color,style in [(release,'#268661','-'),(domain,'#7d8c98','--')]:
        for ring in _rings(geom):
            a=np.asarray(ring);ax.plot(a[:,0],a[:,1],color=color,ls=style,lw=.7,zorder=5)
    ax.set_facecolor('#f6f9fc');ax.grid(alpha=.12)


def candidate_maps(paths,run,base,vectors,geoms,expected_roster):
    release,domain,high,land=geoms
    support=base.b2.support.pivot(index='origin_cell_1',columns='horizon_days',values='training_id_count').min(axis=1)
    positive=support[support>0];ordered=sorted(positive.index,key=lambda i:(-positive[i],i))
    roster=[('high_support',int(ordered[0]))]
    others=[i for i in positive.index if i!=roster[0][1]]
    if others:roster.append(('low_support',int(min(others,key=lambda i:(positive[i],i)))))
    coastal=[i for i in ordered if i not in [c for _,c in roster] and high.intersects(box(i%360-180,i//360-90,i%360-179,i//360-89))]
    if coastal:roster.append(('coastal',int(coastal[0])))
    assert [list(r) for r in roster]==expected_roster, 'Illustration roster changed after freeze'
    names=[]
    for label,origin in roster:
        for h in (7,30):
            fig,axes=plt.subplots(5,1,figsize=(12,18),layout='constrained')
            norm=Normalize(0,max(vectors[m][(h,origin)].max() for m in COLORS))
            for ax,model in zip(axes,COLORS):
                p=vectors[model][(h,origin)];reg,meta=probability_region(p,base.states)
                patches=[];values=[];outlines=[]
                for j,c in enumerate(base.states):
                    if c<0:continue
                    x,y=c%360-180,c//360-90
                    if p[j]>0:patches.append(Rectangle((x,y),1,1));values.append(p[j])
                    if reg[j]:outlines.append(Rectangle((x,y),1,1))
                pc=PatchCollection(patches,cmap='viridis',norm=norm,edgecolor='none');pc.set_array(np.asarray(values));ax.add_collection(pc)
                backdrop(ax,release,domain,land)
                ax.add_collection(PatchCollection(outlines,facecolor='none',edgecolor='#bd3f8c',linewidth=.65,zorder=6))
                ax.add_patch(Rectangle((origin%360-180,origin//360-90),1,1,fill=False,edgecolor='#f26a2c',lw=1.4,zorder=7))
                ax.set(xlim=(-83,-6),ylim=(19,56),xlabel='Longitude',ylabel='Latitude')
                ax.set_title(f'{model} | K90 {meta["region90_cells"]} | issued mass {meta["region90_mass"]:.2%} | E {p[base.index[-2]]:.2%}',loc='left',fontsize=10)
            fig.colorbar(pc,ax=axes,label='Probability per cell; common colour scale',shrink=.6)
            fig.suptitle(f'S3 E2 | {h} days | {label}: origin {origin}\nAll-development fitted illustrations, not held-out skill. Pink: 90% region. Orange: origin.',fontsize=12)
            name=f'candidate_{label}_{h}d.png';save_plot(paths,run,name,fig);names.append(name)
    return roster,names


def freeze_roster(counts,high):
    s=counts.groupby(['origin_cell_1','horizon_days']).id.nunique().unstack().reindex(columns=[7,30]).fillna(0).min(axis=1)
    s=s[s>0];ordered=sorted(s.index,key=lambda i:(-s[i],i));roster=[['high_support',int(ordered[0])]]
    other=[i for i in s.index if i!=roster[0][1]]
    if other:roster.append(['low_support',int(min(other,key=lambda i:(s[i],i)))])
    coastal=[i for i in ordered if i not in [c for _,c in roster] and high.intersects(box(i%360-180,i//360-90,i%360-179,i//360-89))]
    if coastal:roster.append(['coastal',int(coastal[0])])
    return roster


def diagnostic_figures(paths,run,summary,differences,support,selected,geoms):
    names=[];models=list(COLORS);fields=[('brier','Brier (lower is better)'),('region90_cells','Mean 90% region cells'),('region90_hit','Actual hits (%)')]
    fig,axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
    for row,h in enumerate((7,30)):
        table=summary[summary.horizon_days.eq(h)].set_index('model').loc[models]
        for col,(metric,title) in enumerate(fields):
            ax=axes[row,col];v=table[metric].to_numpy(float)*(100 if metric=='region90_hit' else 1)
            ax.scatter(range(5),v,c=list(COLORS.values()),s=60,zorder=3)
            pad=max(.002 if metric=='brier' else 2,(v.max()-v.min())*.3);ax.set_ylim(v.min()-pad,v.max()+pad)
            for x,value in enumerate(v):ax.annotate(f'{value:.6f}' if metric=='brier' else f'{value:.2f}',(x,value),xytext=(0,7),textcoords='offset points',ha='center',fontsize=8)
            ax.set_xticks(range(5),[SHORT[m] for m in models],fontsize=8);ax.set_title(f'{h} days: {title}',fontsize=10);ax.grid(axis='y',alpha=.2)
    fig.suptitle('S3 E2 | Held-out comparison: equal cells, equal drifters within cell\nNominal 90% mass is fixed; actual coverage is measured separately.')
    save_plot(paths,run,'model_comparison.png',fig);names.append('model_comparison.png')
    fig,axes=plt.subplots(2,3,figsize=(14,7),layout='constrained')
    for row,h in enumerate((7,30)):
        for col,(metric,title) in enumerate(fields):
            ax=axes[row,col];scale=100 if metric=='region90_hit' else 1
            for x,ref in enumerate(('LocalEndpoint','Fixed')):
                r=differences[(differences.horizon_days==h)&(differences.reference==ref)&(differences.metric==metric)].iloc[0]
                ax.plot([x,x],scale*np.array([r.lower_95,r.upper_95]),lw=3,color=COLORS[ref]);ax.scatter(x,scale*r.difference,color=COLORS[ref],zorder=3)
                ax.scatter(x,scale*r.adjusted_directional_bound,marker='_',s=150,color='#b7354d',zorder=4)
            ax.axhline(0,color='#657d8b',lw=.8);ax.set_xticks([0,1],['minus LocalEndpoint','minus Fixed'],fontsize=9)
            ax.set_title(f'{h} days: {title} difference',fontsize=10);ax.grid(axis='y',alpha=.15)
    fig.suptitle('LocalEndpointAdaptive minus reference | ordinary 95% paired-ID intervals\nRed mark: predeclared adjusted directional bound. Hit differences are percentage points.',fontsize=12)
    save_plot(paths,run,'quality_and_region_differences.png',fig);names.append('quality_and_region_differences.png')
    fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    for row,h in enumerate((7,30)):
        s=support[(support.role=='all_development_candidate')&(support.model=='LocalEndpointAdaptive')&(support.horizon_days==h)&support.supported]
        const=selected[(selected.role=='all_development_candidate')&(selected.model=='LocalEndpoint')&(selected.horizon_days==h)].parameter_a.iloc[0]
        for col,(x,label) in enumerate([('local_ids','Local distinct fitting drifters'),('normalised_support_ratio','Normalised neighbour/local ID ratio')]):
            ax=axes[row,col];points=ax.scatter(s[x],s.borrowing_weight,c=s.neighbour_ids,cmap='viridis',s=25+100*s.jaccard_overlap,vmin=0,vmax=support.neighbour_ids.max(),edgecolor='#45545c',linewidth=.3)
            ax.axhline(const,color=COLORS['LocalEndpoint'],ls='--',label='Selected constant LocalEndpoint')
            ax.set(xscale='log',ylim=(-.03,1.03),xlabel=label,ylabel='Neighbour weight',title=f'{h} days');ax.legend(fontsize=8);ax.grid(alpha=.15)
    fig.colorbar(points,ax=axes,label='Distinct neighbour drifters',shrink=.8)
    fig.suptitle('All-development applied borrowing | point area increases with local/donor ID overlap\nID counts affect only borrowing; original pair-frequency distributions are retained.',fontsize=11)
    save_plot(paths,run,'adaptive_weights.png',fig);names.append('adaptive_weights.png')
    cells=read_frame(run['results']/'cell_summary.csv');release,domain,high,land=geoms
    for metric,title in fields:
        fig,axes=plt.subplots(2,2,figsize=(12,9),layout='constrained');scale=100 if metric=='region90_hit' else 1
        changes={}
        for h in (7,30):
            w=cells[cells.horizon_days.eq(h)].pivot(index='origin_cell_1',columns='model',values=metric)
            for ref in ('LocalEndpoint','Fixed'):changes[(h,ref)]=(w.LocalEndpointAdaptive-w[ref])*scale
        limit=max(max(abs(s)) for s in changes.values()) or 1e-12
        for row,h in enumerate((7,30)):
            for col,ref in enumerate(('LocalEndpoint','Fixed')):
                ax=axes[row,col];delta=changes[(h,ref)]
                patch=PatchCollection([Rectangle((i%360-180,i//360-90),1,1) for i in delta.index],cmap='RdBu_r',norm=Normalize(-limit,limit),edgecolor='#627b89',linewidth=.25)
                patch.set_array(delta.to_numpy());ax.add_collection(patch);backdrop(ax,release,domain,land)
                ax.set(xlim=(-83,-71),ylim=(28,37),xlabel='Longitude',ylabel='Latitude',title=f'{h} days: adaptive local minus {ref}',aspect='equal')
        fig.colorbar(patch,ax=axes,label=f'{title} difference'+(' (percentage points)' if metric=='region90_hit' else ''),shrink=.8)
        fig.suptitle('All evaluable origins | blue: negative, red: positive\nLower Brier/K90 and higher actual hits have different preferred signs.')
        name=f'per_cell_{metric}.png';save_plot(paths,run,name,fig);names.append(name)
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    for ax,h in zip(axes,(7,30)):
        t=selected[(selected.horizon_days==h)&selected.role.str.match(r'outer_\d$')&selected.model.eq('LocalEndpointAdaptive')].sort_values('role')
        ax.plot(range(len(t)),t.parameter_a,'o-',label='a');ax.plot(range(len(t)),t.parameter_gamma,'s-',label='gamma')
        ax.set(xticks=range(len(t)),xticklabels=t.role,title=f'{h} days',ylabel='Selected parameter');ax.legend();ax.grid(alpha=.2)
    fig.suptitle('Parameters selected inside each outer training fold')
    save_plot(paths,run,'parameter_stability.png',fig);names.append('parameter_stability.png')
    return names


def write_report(paths,run,summary,secondary,differences,decisions,selected,base,vectors,support,verification):
    geoms=geometry(paths);expected=json.loads((run['provenance']/'illustration_roster_freeze.json').read_text())['roster']
    roster,maps=candidate_maps(paths,run,base,vectors,geoms,expected)
    strata=strata_tables(paths,run,support,geoms[2])
    figures=diagnostic_figures(paths,run,summary,differences,support,selected,geoms)+maps
    fields=['horizon_days','model','brier','region90_cells','region90_hit','region90_mass','outside_local_union','zero_true_probability','evaluable_ids','evaluable_pairs']
    view=summary[fields];weights=support[(support.model=='LocalEndpointAdaptive')&support.supported]
    mechanisms=weights.groupby(['role','horizon_days']).agg(cells=('origin_cell_1','size'),minimum_weight=('borrowing_weight','min'),median_weight=('borrowing_weight','median'),maximum_weight=('borrowing_weight','max'),changed_from_constant=('adaptation_total_variation',lambda x:int((x>1e-12).sum())),mean_total_variation=('adaptation_total_variation','mean')).reset_index()
    paths.publish(run['results']/'mechanism_summary.csv',lambda out:out.write(mechanisms.to_csv(index=False).encode()))
    report=['# Step 3 E2 — Adaptive LocalEndpoint borrowing','',
        '**Status: independently executed and audited; scientific retention awaits user review.**','',
        'Where Things End Up: direct 7/30-day stopped destination distributions from an arbitrary qualified origin-cell time. Pooled v7, 1-degree cells, unchanged eight-neighbour R-only raw pair references. The locked final test remains unread.','',
        '## Held-out results','',markdown_table(view),'',
        'Primary weighting: eligible times within drifter/cell, equal drifters within cell, equal cells. Brier is not percentage accuracy. K90 counts geographic cells, not square-kilometre area. E contributes mass/hits but no cell. The nominal region remains 90%; probabilities outside it remain stored.','',
        '## New weight and retained controls','',
        'LocalEndpointAdaptive uses lambda=a*z^gamma/(1-a+a*z^gamma), where z=(neighbour distinct IDs/local distinct IDs) divided by its fitting-only median. The same ID in several neighbour cells counts once in that union. Raw pair-frequency training remains unchanged. Gamma=0 exactly contains constant LocalEndpoint. Fixed and Adaptive still borrow global B1; global Adaptive retains its original pair-count schedule. No trajectories are translated.','',
        '## Prespecified comparisons','',markdown_table(differences),'',markdown_table(decisions),'',
        'All changes are adaptive local minus reference. Ordinary 95% intervals and 12 adjusted directional screens use 10,000 paired PCG64 Exp(1) whole-ID multipliers, seed 20261031. Fits are held fixed. These omit refitting, shared-training dependence, prior research adaptation and common ocean forcing; they are conditional development evidence, not final-test guarantees. Non-significance is not proof of non-deterioration.','',
        'The LocalEndpoint comparison tests adaptation. The Fixed comparison tests overall quality and region size. A preferred adaptive candidate needs an actual adaptive forecast change, lower Brier and preserved coverage against LocalEndpoint, plus lower Brier/preserved coverage/no larger region against Fixed. Smaller regions alone never pass.','',
        '## Selection and mechanism','',markdown_table(selected[['role','horizon_days','model','parameter_a','parameter_gamma']]),'',markdown_table(mechanisms),'',
        'Weight summaries are unweighted across supported fitted rows, not held-out case-weighted estimates. Support ratios are heuristics: identical IDs may occur locally and in donors, and raw pairs may still be concentrated in a few IDs. Gamma>0 is meaningful only when it changes forecasts. The outside-local-union rate is a structural limit on this two-distribution mixture, not a reason to discard those truths.','',
        '## Support and boundary diagnostics','',markdown_table(strata),'',
        'Support bands 1-9 / 10-49 / 50+ use actual outer fitting IDs. Coastal classification is grid-polygon intersection with the pinned high land mask. Subsets retain/renormalise original case weights. None selected parameters.','',
        '## Pair-weighted sensitivity','',markdown_table(secondary[fields]),'',
        'These are the same forecasts under secondary weights; they did not select the parameters.','',
        '## Audit','',
        f'- Independently reconstructed {verification["fitting_roles_checked"]} fitting roles, {verification["candidate_identities_checked"]} candidate/horizon/role identities, {verification["candidate_id_cells_checked"]} candidate ID-cell rows.',
        f'- Maximum absolute reconstruction errors: {verification["maximum_absolute_errors"]}.',
        '- All four controls reproduce S3 E1, including selected matrices, parameters, case weights and metrics.',
        '- Gamma-zero nesting, ID union counting, weight rules, uncertainty and acceptance decisions passed independent checks.',
        '- Source, approved-plan, config and input hashes are frozen. Outer predictions/support were frozen before all-development tuning.',
        '- No final-test trajectories, displacement path cache, old stopped run or unrelated model were accessed.','',
        '## Visual comparison','',f'Predetermined support/geometry illustration roster: {roster}. All-development maps are illustrations; held-out scores provide the performance evidence.','']
    for name in figures:report.extend([f'![{name}]({name})',''])
    paths.publish(run['results']/'REPORT.md',lambda out:out.write('\n'.join(report).encode()))
    paths.publish(run['results']/'illustration_roster.json',lambda out:out.write(json.dumps(dict(roster=roster),indent=2).encode()))
    html=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>S3 E2 adaptive local borrowing</title><style>body{max-width:1280px;margin:40px auto;padding:0 20px;background:#f5f7fa;color:#243846;font:16px/1.6 system-ui}table{border-collapse:collapse;background:white;font-size:13px;display:block;overflow:auto}th,td{padding:8px;border-bottom:1px solid #ddd;text-align:right}img{width:100%;background:white;margin:18px 0}.note{padding:18px;background:#e8edf5;border-left:4px solid #286cb2}</style>',
        '<h1>Step 3 E2 — Adaptive LocalEndpoint</h1><p class="note">Where Things End Up · 1 degree · 7 / 30 days · Five-model comparison<br>Equal drifters within cell, equal cells. Fixed nominal 90% regions. Final test remains locked.</p>',
        '<p><a href="REPORT.md">Full report</a> · <a href="summary.csv">Primary data</a> · <a href="paired_differences.csv">Difference intervals</a> · <a href="row_support.csv">Weights and support</a></p>',
        '<h2>Held-out results</h2>',view.to_html(index=False,float_format=lambda x:f'{x:.6f}'),'<h2>Predeclared quality screens</h2>',decisions.to_html(index=False),
        '<p>Differences are adaptive local minus reference. A smaller region does not establish preserved quality. Ordinary intervals condition on fixed fits; adjusted screens are development evidence.</p>']
    for name in figures:html.extend(['<h2>'+escape(name.replace('_',' ').replace('.png',''))+'</h2><img loading="lazy" src="'+name+'" alt="'+escape(name)+'">'])
    html.append('</html>');paths.publish(run['results']/'review.html',lambda out:out.write(''.join(html).encode()))
