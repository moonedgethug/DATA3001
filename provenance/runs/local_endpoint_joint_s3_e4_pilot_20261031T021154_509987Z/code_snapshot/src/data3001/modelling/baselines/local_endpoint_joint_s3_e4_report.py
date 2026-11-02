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

from data3001.modelling.baselines.local_endpoint_quality_s3_e3_report import geometry,backdrop,freeze_roster,markdown_table
from data3001.modelling.baselines.local_endpoint_joint_s3_e4 import MODELS,PRIMARY,JOINT,CATEGORIES
COLORS={'B2':'#647986','Fixed':'#c57b32','Adaptive':'#8a62b0','LocalEndpoint':'#239d8f','LocalEndpointAdaptive':'#2568b5','LocalEndpointQuality':'#ce465e',JOINT:'#82459c',PRIMARY:'#132f43'}
SHORT=['B2','Fixed','Adaptive','Local\nEndpoint','Local\nAdaptive','Local\nQuality','Joint','Joint\nConstrained']
FIELDS=[('brier','Brier (lower is better)'),('region90_cells','Mean 90% region cells'),('region90_hit','Actual hits (%)')]

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
    names=[];comparison=('LocalEndpointAdaptive','Fixed',JOINT,PRIMARY)
    for label,origin in roster:
        for h in (7,30):
            fig,axes=plt.subplots(4,1,figsize=(12,15),layout='constrained')
            norm=Normalize(0,max(vectors[m][(h,origin)].max() for m in comparison))
            for ax,model in zip(axes,comparison):
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
            fig.suptitle(f'S3 E4 | {h} days | {label}: origin {origin}\nAll-development fitted illustrations, not held-out skill. Pink: 90% region. Orange: origin.',fontsize=12)
            name=f'candidate_{label}_{h}d.png';save_plot(paths,run,name,fig);names.append(name)
    return roster,names


def diagnostic_figures(paths,run,summary,differences,support,selected,base,geoms):
    names=[]
    def save(name,fig):save_plot(paths,run,name,fig);names.append(name)
    fig,axes=plt.subplots(2,3,figsize=(17,9),layout='constrained')
    for row,h in enumerate((7,30)):
        t=summary[summary.horizon_days.eq(h)].set_index('model').loc[list(MODELS)]
        for col,(metric,title) in enumerate(FIELDS):
            ax=axes[row,col];v=t[metric].to_numpy()*(100 if metric=='region90_hit' else 1)
            ax.scatter(range(8),v,c=[COLORS[m] for m in MODELS],s=50);ax.set_xticks(range(8),SHORT,fontsize=7)
            pad=max(.002 if metric=='brier' else 2,np.ptp(v)*.3);ax.set_ylim(v.min()-pad,v.max()+pad)
            for x,value in enumerate(v):ax.annotate(f'{value:.6f}' if metric=='brier' else f'{value:.2f}',(x,value),xytext=(0,8),textcoords='offset points',ha='center',fontsize=7)
            ax.set_title(f'{h} days: {title}',fontsize=10);ax.grid(axis='y',alpha=.2)
    fig.suptitle('S3 E4 | Held-out results: eight unchanged-population forecasts\nEqual drifters within origin, equal origins. Fixed nominal 90% regions.')
    save('model_comparison.png',fig)
    fig,axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
    for row,h in enumerate((7,30)):
        for col,(metric,title) in enumerate(FIELDS):
            ax=axes[row,col];scale=100 if metric=='region90_hit' else 1
            for k,(model,ref) in enumerate([(m,r) for r in ('LocalEndpointAdaptive','Fixed') for m in (JOINT,PRIMARY)]):
                r=differences[(differences.horizon_days==h)&(differences.model==model)&(differences.reference==ref)&(differences.metric==metric)].iloc[0]
                ax.plot([k,k],scale*np.array([r.lower_95,r.upper_95]),color=COLORS[model],lw=3);ax.scatter(k,r.difference*scale,color=COLORS[model])
                if r.primary_comparison:ax.scatter(k,r.adjusted_directional_bound*scale,color='#cf395a',marker='_',s=160)
            ax.axhline(0,color='#aaa');ax.set_xticks(range(4),['Joint minus\nlocal adaptive','Constrained minus\nlocal adaptive','Joint minus\nFixed','Constrained minus\nFixed'],fontsize=8)
            ax.set_title(f'{h} days: {title} difference',fontsize=10);ax.grid(alpha=.15)
    fig.suptitle('Paired differences | ordinary 95% conditional intervals\nRed marks: 12 primary directional screens. Hit differences: percentage points.')
    save('quality_and_region_differences.png',fig)
    search=read_frame(run['results']/'parameter_search.csv');constraints=read_frame(run['results']/'constraint_summary.csv')
    for h in (7,30):
        fig,axes=plt.subplots(2,5,figsize=(20,8),layout='constrained')
        for k in range(5):
            g=search[(search.role==f'outer_{k}')&(search.horizon_days==h)&(search.model==JOINT)]
            for row,metric in enumerate(('region90_hit','region90_cells')):
                ax=axes[row,k];scale=100 if row==0 else 1;feasible=g.feasible.eq(True)
                ax.scatter(g.brier,g[metric]*scale,c=np.where(feasible,'#21866c','#b7c0c7'),s=13,alpha=.6)
                for label,color in [('anchor','#2568b5'),('fixed','#c57b32')]:ax.axhline(g[f'{label}_{metric}'].iloc[0]*scale,color=color,lw=1,ls='--')
                for flag,marker,color in [('selected_joint','x','#82459c'),('issued_constrained','*','#132f43')]:
                    z=g[g[flag].eq(True)];ax.scatter(z.brier,z[metric]*scale,marker=marker,color=color,s=100,zorder=4)
                ax.set(xlabel='Inner Brier',ylabel='Inner actual hits (%)' if row==0 else 'Inner K90',title=f'Outer partition {k}',);ax.grid(alpha=.1)
        fig.suptitle(f'{h} days | Inner selection data, not outer performance\nGreen: satisfies both H/K references. Purple x: Joint. Dark star: issued constrained/fallback. Blue/orange: local/Fixed thresholds.')
        save(f'inner_feasible_candidates_{h}d.png',fig)
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for ax,h in zip(axes,(7,30)):
        t=constraints[(constraints.horizon_days==h)&constraints.role.str.match(r'outer_\d$')].sort_values('role');x=np.arange(len(t))
        for offset,key,color in [(-.25,'feasible_anchor','#2568b5'),(0,'feasible_fixed','#c57b32'),(.25,'feasible_both','#21866c')]:ax.bar(x+offset,t[key],width=.25,color=color,label=key.replace('feasible_',''))
        ax.set_xticks(x,[f'{r.role}\n'+('FALLBACK' if r.fallback else 'ADOPT') for r in t.itertuples(index=False)],fontsize=8)
        ax.set(title=f'{h} days',ylabel='Feasible triples (of 252)');ax.legend(fontsize=8)
    fig.suptitle('Both-reference constraints and issued fallback | no relaxation after failure')
    save('constraints_and_fallback.png',fig)
    fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
    for row,h in enumerate((7,30)):
        for col,param in enumerate(('parameter_a','parameter_gamma','parameter_eta')):
            ax=axes[row,col]
            for m in ('LocalEndpointAdaptive','LocalEndpointQuality',JOINT,PRIMARY):
                t=selected[(selected.horizon_days==h)&selected.role.str.match(r'outer_\d$')&selected.model.eq(m)].sort_values('role')
                ax.plot(range(5),t[param],'o-',label=m,color=COLORS[m],alpha=.8)
            ax.set(title=f'{h} days: {param}',xticks=range(5),xlabel='Outer partition');ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=7);fig.suptitle('Parameters selected without their outer evaluation IDs')
    save('parameter_stability.png',fig)
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for ax,h in zip(axes,(7,30)):
        for m in ('LocalEndpointAdaptive',JOINT,PRIMARY):
            t=support[(support.role=='all_development_candidate')&(support.horizon_days==h)&support.model.eq(m)&support.supported].sort_values('local_ids')
            ax.scatter(t.local_ids,t.borrowing_weight,label=m,color=COLORS[m],s=30,alpha=.8)
        ax.set(xscale='log',xlabel='Local fitting IDs',ylabel='Actual neighbour weight',title=f'{h} days');ax.legend(fontsize=7);ax.grid(alpha=.2)
    fig.suptitle('All-development borrowing weights | descriptive fitted rows')
    save('actual_borrowing_weights.png',fig)
    fig,axes=plt.subplots(2,2,figsize=(14,8),layout='constrained')
    for row,h in enumerate((7,30)):
        t=summary[summary.horizon_days.eq(h)].set_index('model');x=np.arange(6)
        for col,suffix in enumerate(('probability','hit')):
            ax=axes[row,col]
            for offset,m in [(-.25,'LocalEndpointAdaptive'),(0,JOINT),(.25,PRIMARY)]:
                ax.bar(x+offset,[t.loc[m,f'category_{c}_{suffix}'] for c in CATEGORIES[:6]],width=.25,color=COLORS[m],label=m)
            ax.set_xticks(x,[c.replace('_','\n') for c in CATEGORIES[:6]],fontsize=8);ax.set_title(f'{h} days: {suffix}');ax.grid(axis='y',alpha=.2)
    axes[0,0].legend(fontsize=7);fig.suptitle('Fitting-defined endpoint groups | probability and actual hit contributions')
    save('endpoint_category_diagnostics.png',fig)
    cells=read_frame(run['results']/'cell_summary.csv');release,domain,high,land=geoms
    for metric,title in FIELDS:
        fig,axes=plt.subplots(2,2,figsize=(11,9),layout='constrained');scale=100 if metric=='region90_hit' else 1;values={}
        for h in (7,30):
            w=cells[cells.horizon_days.eq(h)].pivot(index='origin_cell_1',columns='model',values=metric)
            for ref in ('LocalEndpointAdaptive','Fixed'):values[(h,ref)]=(w[PRIMARY]-w[ref])*scale
        limit=max(max(abs(v)) for v in values.values()) or 1e-12
        for row,h in enumerate((7,30)):
            for col,ref in enumerate(('LocalEndpointAdaptive','Fixed')):
                ax=axes[row,col];d=values[(h,ref)]
                pc=PatchCollection([Rectangle((i%360-180,i//360-90),1,1) for i in d.index],cmap='RdBu_r',norm=Normalize(-limit,limit),edgecolor='#627b89',linewidth=.3);pc.set_array(d.to_numpy());ax.add_collection(pc);backdrop(ax,release,domain,land)
                ax.set(xlim=(-83,-71),ylim=(28,37),aspect='equal',title=f'{h}d: constrained minus {ref}',xlabel='Longitude',ylabel='Latitude')
        fig.colorbar(pc,ax=axes,label=title+' difference'+(' (pp)' if metric=='region90_hit' else ''),shrink=.7)
        fig.suptitle('All evaluated origins | blue negative, red positive; preferred signs differ by metric')
        save(f'per_cell_{metric}.png',fig)
    return names


def write_report(paths,run,summary,secondary,differences,decisions,selected,base,vectors,support,verification):
    geoms=geometry(paths);expected=json.loads((run['provenance']/'illustration_roster_freeze.json').read_text())['roster']
    roster,maps=candidate_maps(paths,run,base,vectors,geoms,expected)
    strata=strata_tables(paths,run,support,geoms[2])
    figures=diagnostic_figures(paths,run,summary,differences,support,selected,base,geoms)+maps
    constraints=read_frame(run['results']/'constraint_summary.csv');outcomes=[]
    for h in (7,30):
        c=constraints[(constraints.horizon_days==h)&constraints.role.str.match(r'outer_\d$')]
        changed=bool(support[(support.model==PRIMARY)&(support.horizon_days==h)&support.role.str.match(r'outer_\d$')].anchor_total_variation.gt(1e-12).any())
        decision=decisions[decisions.horizon_days.eq(h)]
        outcomes.append(dict(horizon_days=h,outer_fallbacks=int(c.fallback.sum()),outer_selections=len(c),meaningful_outer_forecast_change=changed,
            preferred_overall_candidate=bool(changed and decision.conditional_quality_preserving.all()),
            all_development_fallback=bool(constraints[(constraints.horizon_days==h)&constraints.role.eq('all_development_candidate')].iloc[0].fallback)))
    outcomes=pd.DataFrame(outcomes)
    categories=summary[['horizon_days','model',*[k for k in summary if k.startswith('category_') and not k.endswith('__denominator')]]]
    for name,table in [('outcome_summary.csv',outcomes),('category_summary.csv',categories)]:paths.publish(run['results']/name,lambda out,table=table:out.write(table.to_csv(index=False).encode()))
    fields=['horizon_days','model','brier','region90_cells','region90_hit','region90_mass','zero_true_probability','outside_local_union','evaluable_ids','evaluable_pairs']
    main=summary[fields];pars=selected[['role','horizon_days','model','parameter_a','parameter_gamma','parameter_eta','parameter_rho','selection_status','fallback']]
    report=['# Step 3 E4 — Joint endpoint allocation with dual-reference constraints','',
        '**Status: independently executed and audited; scientific retention awaits user review.**','',
        'Where Things End Up: separate direct stopped 7/30-day distributions from an arbitrary qualified origin time. Annual pooled v7, 1-degree grid, eight R-origin neighbours. Raw-pair fitting, equal drifters within origin and equal origins for evaluation. Final test remains locked.','',
        '## Held-out comparison','',markdown_table(main),'',
        'Brier is not percentage accuracy. K90 counts geographic cells, not area. All models use complete nominal-90% regions with ties; actual hits are measured independently. E contributes probability/hits but no geographic cell.','',
        '## Primary acceptance and fallback','',markdown_table(outcomes),'',markdown_table(decisions),'',
        'The primary candidate must improve Brier while preserving hits and size against BOTH LocalEndpointAdaptive and Fixed. Twelve directional screens across two references, three metrics and two horizons use 20,000 paired whole-ID multipliers. A zero-crossing interval is not evidence of non-deterioration.','',markdown_table(differences),'',
        '## Selection method','',
        'All 252 combinations of a=0:0.05:1, gamma={0,0.5,1,2}, eta={0,0.5,0.9} are evaluated; rho=1 in both new arms. Joint minimises inner Brier. JointConstrained requires inner H90>=each reference and K90<=each reference, then adopts the best feasible candidate only if its Brier is below both references. Otherwise it issues the freshly fitted LocalEndpointAdaptive anchor with an explicit failure status. Such fallback does not establish that Fixed quality was preserved.','',
        'Each reference threshold is recomputed inside the outer training partition. Inner values are selection data, not independent proof. No selected triple, feasibility condition or denominator changes after observing outer outcomes.','',markdown_table(constraints),'',markdown_table(pars),'',
        '## Attribution and limitations','',
        'The unconstrained Joint arm is diagnostic and cannot be promoted post hoc. Comparing it with E3 tests joint retuning; comparing the constrained procedure with Joint tests the added feasibility/adoption policy on the same candidates. Report constraint-induced failure honestly. No new movement information, rare-endpoint deletion or wider search is introduced.','',
        'Intervals keep fits fixed and omit refitting uncertainty, shared training, ocean forcing and prior development-set research adaptation. Nested ID exclusion does not make these data an untouched final test. All-development maps are fitted illustrations; outer scores establish comparative evidence.','',
        '## Support and geographic strata','',markdown_table(strata),'',
        'These descriptive strata do not select models. Endpoint category probability, event, hit and Brier contributions reconcile with complete outcomes. Rho=1 does not guarantee rare endpoints remain inside the region. All zero-probability truths are scored.','',
        '## Pair-weighted sensitivity','',markdown_table(secondary[fields]),'',
        'Secondary weights did not influence selection.','',
        '## Engineering verification','',
        f'- Independent audit: {verification["fitting_roles_checked"]} fitting roles; {verification["candidate_identities_checked"]} candidate identities; {verification["candidate_id_cells_checked"]} candidate ID-origin records.',
        f'- Reconstruction errors: {verification["maximum_absolute_errors"]}.',
        '- Six legacy controls reproduce S3 E3 selected matrices, parameters, common cases, weights and point metrics.',
        '- All candidate results are persisted in per-role partitions; constraints, rejection reasons and both fallback branches are explicit.',
        '- Plan/config, input/source including entrypoint and outer predictions are fingerprinted. Final-test/canonical trajectory reads are zero.',
        '- Fresh replay receipt records numerical and image identity separately from predictive acceptance.','',
        '## Visual comparison','',f'Fixed support/geometry illustration roster: {roster}.','']
    for name in figures:report.extend([f'![{name}]({name})',''])
    paths.publish(run['results']/'REPORT.md',lambda out:out.write('\n'.join(report).encode()))
    paths.publish(run['results']/'illustration_roster.json',lambda out:out.write(json.dumps(dict(roster=roster),indent=2).encode()))
    html=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>S3 E4 joint endpoint borrowing</title>',
        '<style>body{max-width:1360px;margin:40px auto;padding:0 20px;background:#f5f7fa;color:#243846;font:16px/1.6 system-ui}table{border-collapse:collapse;background:white;font-size:13px;display:block;overflow:auto}th,td{padding:8px;border-bottom:1px solid #ddd;text-align:right}img{width:100%;background:white;margin:18px 0}.note{padding:18px;background:#e8edf5;border-left:4px solid #ce465e}</style>',
        '<h1>Step 3 E4 — Joint Endpoint Borrowing</h1><p class="note">Eight-model comparison · Equal drifters within origin, equal origins · Fixed nominal 90% regions<br>Fallback means no eligible improvement was adopted; it is not proof that Fixed quality was preserved. Final test remains locked.</p>',
        '<p><a href="REPORT.md">Full report</a> · <a href="summary.csv">Scores</a> · <a href="constraint_summary.csv">Constraints and fallback</a> · <a href="paired_differences.csv">Difference intervals</a></p>',
        '<h2>Held-out comparison</h2>',main.to_html(index=False,float_format=lambda x:f'{x:.6f}'),'<h2>Acceptance and fallback</h2>',outcomes.to_html(index=False),decisions.to_html(index=False),
        '<h2>Inner selection decisions</h2>',constraints.to_html(index=False,float_format=lambda x:f'{x:.6f}'),'<p>Inner constraints are point-estimate selection rules, not outer guarantees. Conditional intervals do not include refitting or prior research adaptation.</p>']
    for name in figures:html.append('<h2>'+escape(name.replace('_',' ').replace('.png',''))+'</h2><img loading="lazy" src="'+name+'" alt="'+escape(name)+'">')
    html.append('</html>');paths.publish(run['results']/'review.html',lambda out:out.write(''.join(html).encode()))
