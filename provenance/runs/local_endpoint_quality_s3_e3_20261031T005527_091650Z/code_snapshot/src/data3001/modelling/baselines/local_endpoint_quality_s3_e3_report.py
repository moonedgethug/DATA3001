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

COLORS={'B2':'#647986','Fixed':'#c57b32','Adaptive':'#8a62b0','LocalEndpoint':'#239d8f','LocalEndpointAdaptive':'#2568b5','LocalEndpointQuality':'#ce465e'}
SHORT={'B2':'B2','Fixed':'Fixed','Adaptive':'Adaptive','LocalEndpoint':'Local\nEndpoint','LocalEndpointAdaptive':'Local Endpoint\nAdaptive','LocalEndpointQuality':'Local Endpoint\nQuality'}


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


from data3001.modelling.baselines.local_endpoint_adaptive_s3_e2_report import freeze_roster
from data3001.modelling.baselines.local_endpoint_quality_s3_e3 import CATEGORIES,MODELS,ABLATIONS

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
            fig,axes=plt.subplots(6,1,figsize=(12,21),layout='constrained')
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
            fig.suptitle(f'S3 E3 | {h} days | {label}: origin {origin}\nAll-development fitted illustrations, not held-out skill. Pink: 90% region. Orange: origin.',fontsize=12)
            name=f'candidate_{label}_{h}d.png';save_plot(paths,run,name,fig);names.append(name)
    return roster,names


def diagnostic_figures(paths,run,summary,differences,support,selected,base,geoms):
    names=[];models=list(COLORS);refs=('LocalEndpointAdaptive','LocalEndpoint','Fixed')
    fields=[('brier','Brier (lower is better)'),('region90_cells','Mean 90% region cells'),('region90_hit','Actual hits (%)')]
    fig,axes=plt.subplots(2,3,figsize=(16,8),layout='constrained')
    for row,h in enumerate((7,30)):
        table=summary[summary.horizon_days.eq(h)].set_index('model').loc[models]
        for col,(metric,title) in enumerate(fields):
            ax=axes[row,col];v=table[metric].to_numpy(float)*(100 if metric=='region90_hit' else 1)
            ax.scatter(range(6),v,c=list(COLORS.values()),s=55,zorder=3)
            pad=max(.002 if metric=='brier' else 2,(v.max()-v.min())*.3);ax.set_ylim(v.min()-pad,v.max()+pad)
            for x,value in enumerate(v):ax.annotate(f'{value:.6f}' if metric=='brier' else f'{value:.2f}',(x,value),xytext=(0,8),textcoords='offset points',ha='center',fontsize=8)
            ax.set_xticks(range(6),[SHORT[m] for m in models],fontsize=7);ax.set_title(f'{h} days: {title}',fontsize=10);ax.grid(axis='y',alpha=.2)
    fig.suptitle('S3 E3 | Held-out comparison: equal drifters within cell, equal cells\nAll models issue fixed nominal 90% regions; actual coverage is measured separately.')
    save_plot(paths,run,'model_comparison.png',fig);names.append('model_comparison.png')
    fig,axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
    for row,h in enumerate((7,30)):
        for col,(metric,title) in enumerate(fields):
            ax=axes[row,col];scale=100 if metric=='region90_hit' else 1
            for x,ref in enumerate(refs):
                r=differences[(differences.horizon_days==h)&(differences.reference==ref)&(differences.metric==metric)].iloc[0]
                ax.plot([x,x],scale*np.array([r.lower_95,r.upper_95]),lw=3,color=COLORS[ref]);ax.scatter(x,scale*r.difference,color=COLORS[ref],zorder=3)
                ax.scatter(x,scale*r.adjusted_directional_bound,marker='_',s=140,color='#b7354d',zorder=4)
            ax.axhline(0,color='#657d8b',lw=.8);ax.set_xticks(range(3),['minus local\nadaptive','minus local\nendpoint','minus Fixed'],fontsize=9)
            ax.set_title(f'{h} days: {title} difference',fontsize=10);ax.grid(axis='y',alpha=.15)
    fig.suptitle('LocalEndpointQuality minus reference | ordinary 95% paired-ID intervals\nRed marks: 18 predeclared directional screens. Hit differences: percentage points.',fontsize=12)
    save_plot(paths,run,'quality_and_region_differences.png',fig);names.append('quality_and_region_differences.png')
    fig,axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
    compare=['LocalEndpointAdaptive','QualitySimilarityOnly','QualityGateOnly','LocalEndpointQuality']
    labels=['Anchor','Similarity\nonly','Gate\nonly','Combined']
    for row,h in enumerate((7,30)):
        t=summary[summary.horizon_days.eq(h)].set_index('model').loc[compare]
        for col,(metric,title) in enumerate(fields):
            ax=axes[row,col];v=t[metric]*(100 if metric=='region90_hit' else 1)
            ax.plot(range(4),v,'o-',color='#46758d');ax.set_xticks(range(4),labels);ax.set_title(f'{h} days: {title}',fontsize=10);ax.grid(alpha=.2)
            for x,value in enumerate(v):ax.annotate(f'{value:.6f}' if metric=='brier' else f'{value:.3f}',(x,value),xytext=(0,8),textcoords='offset points',ha='center',fontsize=8)
            ax.margins(y=.3)
    fig.suptitle('Selected-setting ablations | remove one component without retuning\nThese are diagnostic procedures, not additional selected winners.')
    save_plot(paths,run,'component_ablations.png',fig);names.append('component_ablations.png')
    fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
    for row,h in enumerate((7,30)):
        pars=selected[(selected.role=='all_development_candidate')&(selected.model=='LocalEndpointQuality')&(selected.horizon_days==h)].iloc[0]
        t=base.donor_quality[(base.donor_quality.horizon_days==h)&(base.donor_quality.parameter_eta==pars.parameter_eta)&base.donor_quality.applied_quality]
        axes[row,0].scatter(t.similarity,t.reweighted_D_weight/t.original_D_weight,c=t.donor_ids,cmap='viridis',s=20)
        axes[row,0].axhline(1,color='#aaa',ls='--');axes[row,0].set(xlabel='Historical geographic distribution overlap',ylabel='Weight / original pair-pool weight',title=f'{h} days: selected eta={pars.parameter_eta:g}')
        t=support[(support.role=='all_development_candidate')&(support.model=='LocalEndpointQuality')&(support.horizon_days==h)&support.supported]
        axes[row,1].scatter(t.local_ids,100*t.mixed_redirected_D_mass,c=t.quality_total_variation,cmap='plasma',s=28)
        axes[row,1].set(xlabel='Local fitting drifters',ylabel='Forecast mass returned to local D (%)',title=f'{h} days: selected rho={pars.parameter_rho:g}',xscale='log')
        for ax in axes[row]:ax.grid(alpha=.15)
    fig.suptitle('All-development mechanism diagnostics | descriptive fitted rows\nLeft colour: donor ID support. Right colour: forecast total-variation change.')
    save_plot(paths,run,'neighbour_weights_and_returned_mass.png',fig);names.append('neighbour_weights_and_returned_mass.png')
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    for ax,h in zip(axes,(7,30)):
        t=selected[(selected.horizon_days==h)&selected.role.str.match(r'outer_\d$')&selected.model.eq('LocalEndpointQuality')].sort_values('role')
        ax.plot(range(len(t)),t.parameter_eta,'o-',label='eta: similarity');ax.plot(range(len(t)),t.parameter_rho,'s-',label='rho: weak fraction retained')
        ax.set(xticks=range(len(t)),xticklabels=t.role,ylim=(-.05,1.15),title=f'{h} days',ylabel='Selected parameter');ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.suptitle('Quality settings selected inside each outer training partition')
    save_plot(paths,run,'parameter_stability.png',fig);names.append('parameter_stability.png')
    fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
    for row,h in enumerate((7,30)):
        t=summary[summary.horizon_days.eq(h)].set_index('model');x=np.arange(6)
        for col,suffix in enumerate(('probability','brier')):
            ax=axes[row,col]
            for offset,m in [(-.18,'LocalEndpointAdaptive'),(.18,'LocalEndpointQuality')]:
                v=[t.loc[m,f'category_{c}_{suffix}'] for c in CATEGORIES[:6]]
                ax.bar(x+offset,v,width=.36,color=COLORS[m],label='Anchor' if offset<0 else 'Quality')
            if suffix=='probability':ax.scatter(x,[t.loc['LocalEndpointQuality',f'category_{c}_observed'] for c in CATEGORIES[:6]],marker='x',color='#242e39',label='Observed event frequency',zorder=3)
            ax.set_xticks(x,[z.replace('_','\n') for z in CATEGORIES[:6]],fontsize=8);ax.set_title(f'{h} days: {suffix} by fitting-defined category',fontsize=10);ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2)
    fig.suptitle('Endpoint categories | probability allocation and Brier contributions\nAll categories and zero-probability truths remain in the evaluation.')
    save_plot(paths,run,'endpoint_category_diagnostics.png',fig);names.append('endpoint_category_diagnostics.png')
    cells=read_frame(run['results']/'cell_summary.csv');release,domain,high,land=geoms
    for metric,title in fields:
        fig,axes=plt.subplots(2,3,figsize=(15,9),layout='constrained');scale=100 if metric=='region90_hit' else 1;changes={}
        for h in (7,30):
            w=cells[cells.horizon_days.eq(h)].pivot(index='origin_cell_1',columns='model',values=metric)
            for ref in refs:changes[(h,ref)]=(w.LocalEndpointQuality-w[ref])*scale
        limit=max(max(abs(s)) for s in changes.values()) or 1e-12
        for row,h in enumerate((7,30)):
            for col,ref in enumerate(refs):
                ax=axes[row,col];delta=changes[(h,ref)]
                pc=PatchCollection([Rectangle((i%360-180,i//360-90),1,1) for i in delta.index],cmap='RdBu_r',norm=Normalize(-limit,limit),edgecolor='#627b89',linewidth=.25)
                pc.set_array(delta.to_numpy());ax.add_collection(pc);backdrop(ax,release,domain,land)
                ax.set(xlim=(-83,-71),ylim=(28,37),xlabel='Longitude',ylabel='Latitude',title=f'{h}d: quality minus\n{ref}',aspect='equal')
        fig.colorbar(pc,ax=axes,label=title+' difference'+(' (pp)' if metric=='region90_hit' else ''),shrink=.8)
        fig.suptitle('All evaluable origins | blue: negative, red: positive\nLower Brier/K90 and higher hits have different preferred signs.')
        name=f'per_cell_{metric}.png';save_plot(paths,run,name,fig);names.append(name)
    return names


def information_maps(paths,run,base,selected,geoms,roster):
    release,domain,high,land=geoms;names=[]
    palette=['#a97fc8','#1c8a78','#3e70b3','#dc6854','#dbb947','#bcbcbc']
    for label,origin in roster:
        for h in (7,30):
            par=selected[(selected.role=='all_development_candidate')&(selected.model=='LocalEndpointQuality')&(selected.horizon_days==h)].iloc[0]
            donors=base.donor_quality[(base.donor_quality.horizon_days==h)&(base.donor_quality.origin_cell_1==origin)&(base.donor_quality.parameter_eta==par.parameter_eta)]
            fig,axes=plt.subplots(1,2,figsize=(15,5),layout='constrained');ax=axes[0]
            x0,y0=origin%360-180,origin//360-90
            for r in donors.itertuples(index=False):
                x,y=r.donor_cell_1%360-180,r.donor_cell_1//360-90
                ax.add_patch(Rectangle((x,y),1,1,facecolor=plt.cm.Blues(r.reweighted_D_weight),edgecolor='#506878'))
                ax.text(x+.5,y+.5,f'{r.reweighted_D_weight:.1%}\nS={r.similarity:.2f}\nIDs={r.donor_ids}',ha='center',va='center',fontsize=8)
            ax.add_patch(Rectangle((x0,y0),1,1,facecolor='#ffe7cf',edgecolor='#f26a2c'));ax.text(x0+.5,y0+.5,'Origin',ha='center',va='center')
            ax.set(xlim=(x0-1.1,x0+2.1),ylim=(y0-1.1,y0+2.1),aspect='equal',title=f'D-only donor shares | eta={par.parameter_eta:g}',xlabel='Longitude',ylabel='Latitude')
            ax=axes[1];groups=base.quality[(h,origin)]['category']
            for k in range(5):
                cells=base.states[(groups==k)&(base.states>=0)]
                ax.add_collection(PatchCollection([Rectangle((j%360-180,j//360-90),1,1) for j in cells],facecolor=palette[k],edgecolor='none',label=CATEGORIES[k]))
            backdrop(ax,release,domain,land);ax.add_patch(Rectangle((x0,y0),1,1,fill=False,edgecolor='#f26a2c',lw=1.5,zorder=8))
            ax.set(xlim=(-83,-6),ylim=(19,56),title='Historical endpoint categories',xlabel='Longitude',ylabel='Latitude')
            handles=[Rectangle((0,0),1,1,color=palette[k],label=CATEGORIES[k].replace('_',' ')) for k in range(5)]
            ax.legend(handles=handles,fontsize=7,loc='lower right')
            fig.suptitle(f'All-development information sources | {label} {origin} | {h} days\nFitting evidence only; this map does not establish held-out skill.')
            name=f'information_{label}_{h}d.png';save_plot(paths,run,name,fig);names.append(name)
    return names


def write_report(paths,run,summary,secondary,differences,decisions,selected,base,vectors,support,verification):
    geoms=geometry(paths);expected=json.loads((run['provenance']/'illustration_roster_freeze.json').read_text())['roster']
    roster,maps=candidate_maps(paths,run,base,vectors,geoms,expected)
    strata=strata_tables(paths,run,support,geoms[2])
    figures=diagnostic_figures(paths,run,summary,differences,support,selected,base,geoms)+maps+information_maps(paths,run,base,selected,geoms,roster)
    fields=['horizon_days','model','brier','region90_cells','region90_hit','region90_mass','zero_true_probability','outside_local_union','evaluable_ids','evaluable_pairs']
    primary=summary[summary.model.isin(MODELS)][fields];ablation=summary[summary.model.isin(('LocalEndpointAdaptive','LocalEndpointQuality',*ABLATIONS))][fields]
    q=support[(support.model=='LocalEndpointQuality')&support.supported]
    mechanisms=q.groupby(['role','horizon_days']).agg(cells=('origin_cell_1','size'),changed_rows=('quality_total_variation',lambda x:int((x>1e-12).sum())),
        mean_total_variation=('quality_total_variation','mean'),maximum_total_variation=('quality_total_variation','max'),mean_returned_mass=('mixed_redirected_D_mass','mean'),maximum_returned_mass=('mixed_redirected_D_mass','max')).reset_index()
    outcomes=[]
    for h in (7,30):
        d=decisions[decisions.horizon_days.eq(h)].set_index('reference');changed=bool(q[q.horizon_days.eq(h)&q.role.str.match(r'outer_\d$')].quality_total_variation.gt(1e-12).any())
        outcomes.append(dict(horizon_days=h,meaningful_outer_forecast_change=changed,coverage_preserving_information_gain=bool(d.loc['LocalEndpointAdaptive','conditional_coverage_preserving']),preferred_overall_candidate=bool(changed and d.conditional_quality_preserving.all())))
    outcomes=pd.DataFrame(outcomes)
    for name,table in [('mechanism_summary.csv',mechanisms),('outcome_summary.csv',outcomes)]:paths.publish(run['results']/name,lambda out,table=table:out.write(table.to_csv(index=False).encode()))
    categories=summary[['horizon_days','model',*[c for c in summary if c.startswith('category_') and not c.endswith('__denominator')]]]
    paths.publish(run['results']/'category_summary.csv',lambda out:out.write(categories.to_csv(index=False).encode()))
    report=['# Step 3 E3 — Neighbour endpoint information quality','',
        '**Status: independently executed and audited; scientific retention awaits user review.**','',
        'Where Things End Up: direct stopped 7/30-day destination distributions from an arbitrary qualified origin-cell time. Pooled v7, 1-degree cells, unchanged R/D and eight R-origin neighbours. Final test remains locked.','',
        '## Held-out results','',markdown_table(primary),'',
        'Raw-pair training; equal eligible times within drifter/cell, equal drifters within cell, equal cells. Brier is not percentage accuracy. K90 counts geographic cells, not square-kilometre area. E contributes probability/hits but not a geographic cell. Full fitted distributions are retained; nominal 90% is not a promise of 90% observed hits.','',
        '## Model and selection','',
        'S=sum(min(local_D, donor_D)); donor weights are proportional to donor D pairs times (1-eta+eta*S). Original pooled E mass is preserved. Weak-unseen endpoints are absent locally, below 1% of original neighbour D mass and supported by fewer than three distinct neighbour IDs. Shared locally rare and strongly supported new endpoints are exempt. Rho retains 1, 0.5 or 0 of weak-unseen borrowed probability; removed D mass returns to local B2 conditional on D. This changes predictions, including possible zeros, without deleting observations.','',
        'Five controls are freshly tuned by primary Brier inside each outer training partition. LocalEndpointQuality inherits that partition\'s LocalEndpointAdaptive a/gamma and selects only nine eta/rho combinations. Eta=0/rho=1 exactly contains its anchor. Outer predictions are frozen before all-development illustration tuning. No held-out future endpoint enters a fitted similarity, gate or support count.','',
        '## Prespecified decisions','',markdown_table(outcomes),'',markdown_table(decisions),'',markdown_table(differences),'',
        'Differences are Quality minus reference. Ordinary 95% intervals and 18 directional screens use 20,000 paired PCG64 Exp(1) whole-ID multipliers, seed 20261031. Fits are held fixed. These conditional development screens omit refitting, shared-training dependence, ocean forcing and repeated research adaptation. Non-significance does not establish non-deterioration.','',
        'A coverage-preserving information gain requires supported Brier improvement and preserved hits against LocalEndpointAdaptive; region expansion is then reported as a trade-off. The overall candidate must additionally pass no-region-expansion quality rules against LocalEndpointAdaptive, LocalEndpoint and Fixed, and actually change forecasts. Smaller regions with lost coverage do not pass.','',
        '## Selection and component ablations','',markdown_table(selected[['role','horizon_days','model','parameter_a','parameter_gamma','parameter_eta','parameter_rho']]),'',markdown_table(ablation),'',
        'Similarity-only and gate-only ablations remove one selected component without retuning; they are not extra searched winners. A tie or neutral choice is a valid negative finding. No threshold or grid is expanded after the result.','',
        '## Mechanism and support','',markdown_table(mechanisms),'',
        'Mechanism summaries above are unweighted fitted-row descriptions. Mixed returned mass is lambda*delta; nominal lambda alone does not describe endpoint-specific shrinkage. Source similarity can reinforce sampling error; distinct IDs are support proxies, not independent sample sizes. Shared rare endpoints are protected from the gate but can still gain or lose probability after source reweighting.','',markdown_table(strata),'',
        'Support bands and coastal/offshore strata are descriptive and preserve/renormalise primary case weights. All endpoint category probability, outcome, hit and Brier contributions are exported in category_summary.csv. Zero-probability truths remain scored. E calibration is unvalidated if no E outcomes are observed.','',
        '## Pair-weighted sensitivity','',markdown_table(secondary[secondary.model.isin(MODELS)][fields]),'',
        'These are the same forecasts under secondary weights; this table did not select models.','',
        '## Engineering verification','',
        f'- Independent reconstruction: {verification["fitting_roles_checked"]} fitting roles; {verification["candidate_identities_checked"]} candidate/horizon/role identities; {verification["candidate_id_cells_checked"]} candidate ID-cell rows.',
        f'- Maximum absolute reconstruction errors: {verification["maximum_absolute_errors"]}.',
        '- Five controls reproduce S3 E2: all 30 selected matrices, parameters, cases, weights and point metrics.',
        '- Count/ID sets, L1-derived overlap, original-reference gates, E conservation, anchor-first selections, ablations, scores and decision bounds independently checked.',
        '- Approved plan/config, source including entrypoint, inputs and outer predictions are hashed; no canonical or final-test trajectory reads.',
        '- Fresh replay status and timing are recorded in the sealed provenance verification and later handoff.','',
        '## Visual comparison','',f'Predetermined support/geometry roster: {roster}. All-development maps show fitted distributions; held-out scores establish comparative performance.','']
    for name in figures:report.extend([f'![{name}]({name})',''])
    paths.publish(run['results']/'REPORT.md',lambda out:out.write('\n'.join(report).encode()))
    paths.publish(run['results']/'illustration_roster.json',lambda out:out.write(json.dumps(dict(roster=roster),indent=2).encode()))
    html=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>S3 E3 neighbour endpoint quality</title><style>body{max-width:1280px;margin:40px auto;padding:0 20px;background:#f5f7fa;color:#243846;font:16px/1.6 system-ui}table{border-collapse:collapse;background:white;font-size:13px;display:block;overflow:auto}th,td{padding:8px;border-bottom:1px solid #ddd;text-align:right}img{width:100%;background:white;margin:18px 0}.note{padding:18px;background:#e8edf5;border-left:4px solid #ce465e}</style>',
        '<h1>Step 3 E3 — Neighbour Endpoint Quality</h1><p class="note">Where Things End Up · 1 degree · 7 / 30 days · Six-model comparison<br>Equal drifters within cell, equal cells. Fixed nominal 90% regions. Final test remains locked.</p>',
        '<p><a href="REPORT.md">Full report</a> · <a href="summary.csv">Primary data</a> · <a href="paired_differences.csv">Difference intervals</a> · <a href="category_summary.csv">Endpoint diagnostics</a></p>',
        '<h2>Held-out results</h2>',primary.to_html(index=False,float_format=lambda x:f'{x:.6f}'),'<h2>Prespecified decisions</h2>',outcomes.to_html(index=False),decisions.to_html(index=False),
        '<p>Quality minus reference. A smaller region does not establish preserved quality. Conditional intervals hold fits fixed; a zero-crossing interval does not prove non-deterioration.</p>',
        '<h2>Selected-setting ablations</h2>',ablation.to_html(index=False,float_format=lambda x:f'{x:.6f}')]
    for name in figures:html.append('<h2>'+escape(name.replace('_',' ').replace('.png',''))+'</h2><img loading="lazy" src="'+name+'" alt="'+escape(name)+'">')
    html.append('</html>');paths.publish(run['results']/'review.html',lambda out:out.write(''.join(html).encode()))


