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
from data3001.modelling.baselines.spatial_borrowing_s3_e1_inputs import REASONS

COLORS={'B2':'#647986','Fixed':'#c57b32','Adaptive':'#8a62b0','LocalEndpoint':'#239d8f','LocalDisplacement':'#2568b5'}
SHORT={'B2':'B2','Fixed':'Fixed','Adaptive':'Adaptive','LocalEndpoint':'Local\nEndpoint','LocalDisplacement':'Local\nDisplacement'}


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


def candidate_maps(paths,run,base,vectors,geoms):
    release,domain,high,land=geoms
    support=base.b2.support.pivot(index='origin_cell_1',columns='horizon_days',values='training_id_count').min(axis=1)
    positive=support[support>0];ordered=sorted(positive.index,key=lambda i:(-positive[i],i))
    roster=[('high_support',int(ordered[0]))]
    others=[i for i in positive.index if i!=roster[0][1]]
    if others:roster.append(('low_support',int(min(others,key=lambda i:(positive[i],i)))))
    coastal=[i for i in ordered if i not in [c for _,c in roster] and high.intersects(box(i%360-180,i//360-90,i%360-179,i//360-89))]
    if coastal:roster.append(('coastal',int(coastal[0])))
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
            fig.suptitle(f'S3 E1 | {h} days | {label}: origin {origin}\nAll-development fitted illustrations, not held-out skill. Pink: 90% region. Orange: origin.',fontsize=12)
            name=f'candidate_{label}_{h}d.png';save_plot(paths,run,name,fig);names.append(name)
    return roster,names


def diagnostic_figures(paths,run,summary,differences,support,geoms):
    names=[];models=list(COLORS);fields=[('brier','Brier (lower is better)'),('region90_cells','Mean 90% region cells'),('region90_hit','Actual hits (%)')]
    fig,axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
    for row,h in enumerate((7,30)):
        table=summary[summary.horizon_days.eq(h)].set_index('model').loc[models]
        for col,(metric,title) in enumerate(fields):
            ax=axes[row,col];values=table[metric].to_numpy(float)*(100 if metric=='region90_hit' else 1)
            if metric=='brier':
                ax.scatter(range(5),values,c=list(COLORS.values()),s=55,zorder=3);pad=max(.003,(values.max()-values.min())*.25);ax.set_ylim(values.min()-pad,values.max()+2*pad)
            else:ax.bar(range(5),values,color=list(COLORS.values()));ax.set_ylim(0,105 if metric=='region90_hit' else values.max()*1.2)
            for x,v in enumerate(values):ax.annotate(f'{v:.6f}' if metric=='brier' else f'{v:.2f}',(x,v),xytext=(0,6),textcoords='offset points',ha='center',fontsize=8)
            ax.set_xticks(range(5),[SHORT[m] for m in models],fontsize=8);ax.set_title(f'{h} days: {title}',fontsize=10);ax.grid(axis='y',alpha=.15)
    fig.suptitle('Held-out five-model comparison | equal cells, equal IDs within cell\nFull distributions retained; nominal 90% probability does not guarantee 90% actual coverage.',fontsize=12)
    name='model_comparison.png';save_plot(paths,run,name,fig);names.append(name)
    fig,axes=plt.subplots(2,3,figsize=(14,7),layout='constrained')
    for row,h in enumerate((7,30)):
        for col,(metric,title) in enumerate(fields):
            ax=axes[row,col];scale=100 if metric=='region90_hit' else 1
            for x,m in enumerate(('LocalEndpoint','LocalDisplacement')):
                r=differences[(differences.horizon_days==h)&(differences.model==m)&(differences.reference=='Fixed')&(differences.metric==metric)].iloc[0]
                ax.plot([x,x],scale*np.array([r.lower_95,r.upper_95]),lw=3,color=COLORS[m]);ax.scatter(x,scale*r.difference,color=COLORS[m],zorder=3)
                if m=='LocalDisplacement':ax.scatter(x,scale*r.adjusted_directional_bound,marker='_',s=150,color='#b7354d',zorder=4)
            ax.axhline(0,color='#657d8b',lw=.8);ax.set_xticks([0,1],['LocalEndpoint','LocalDisplacement']);ax.set_title(f'{h} days: {title} difference');ax.grid(axis='y',alpha=.15)
    fig.suptitle('Spatial candidate minus Fixed | ordinary 95% conditional ID intervals\nRed mark: adjusted directional bound for the primary LocalDisplacement comparison.',fontsize=12)
    name='quality_and_region_differences.png';save_plot(paths,run,name,fig);names.append(name)
    fig,axes=plt.subplots(1,2,figsize=(13,4.8),layout='constrained')
    for ax,h in zip(axes,(7,30)):
        s=support[(support.role=='all_development_candidate')&(support.model=='LocalDisplacement')&(support.horizon_days==h)&support.supported].sort_values('training_pair_count')
        ax.plot(s.training_pair_count,s.borrowing_weight,'--',color='#8a62b0',label='Nominal neighbour weight')
        points=ax.scatter(s.training_pair_count,s.effective_borrowing_weight,c=s.fallback_fraction,cmap='magma_r',vmin=0,vmax=1,s=35,label='Successful spatial weight')
        ax.set(xscale='log',ylim=(-.03,1.03),xlabel='Local training pair count (not independent samples)',ylabel='Weight',title=f'{h} days');ax.legend(fontsize=8);ax.grid(alpha=.15)
    fig.suptitle('Geometry fallback returns failed weight to B2 | all-development fits\nNominal spatial weight is constant; effective weight changes because transfer validity varies.',fontsize=11)
    fig.colorbar(points,ax=axes,label='Failed-transfer fraction',shrink=.8)
    name='effective_borrowing.png';save_plot(paths,run,name,fig);names.append(name)
    cells=read_frame(run['results']/'cell_summary.csv');release,domain,high,land=geoms
    fig,axes=plt.subplots(2,2,figsize=(12,9),layout='constrained')
    changes=[]
    for h in (7,30):
        w=cells[cells.horizon_days.eq(h)].pivot(index='origin_cell_1',columns='model',values='brier')
        changes.extend((w[m]-w.Fixed).to_list() for m in ('LocalEndpoint','LocalDisplacement'))
    limit=max(abs(v) for vals in changes for v in vals)
    for row,h in enumerate((7,30)):
        w=cells[cells.horizon_days.eq(h)].pivot(index='origin_cell_1',columns='model',values='brier')
        for col,m in enumerate(('LocalEndpoint','LocalDisplacement')):
            ax=axes[row,col];delta=w[m]-w.Fixed
            patch=PatchCollection([Rectangle((i%360-180,i//360-90),1,1) for i in delta.index],cmap='RdBu_r',norm=Normalize(-limit,limit),edgecolor='#627b89',linewidth=.25)
            patch.set_array(delta.to_numpy());ax.add_collection(patch);backdrop(ax,release,domain,land)
            ax.set(xlim=(-83,-71),ylim=(28,37),xlabel='Longitude',ylabel='Latitude',title=f'{h} days: {m} minus Fixed')
    fig.colorbar(patch,ax=axes,label='Brier difference; blue favours spatial model',shrink=.8)
    fig.suptitle('All evaluable origin cells | per-cell ID-balanced diagnostic; no performance-selected cells')
    name='per_cell_brier.png';save_plot(paths,run,name,fig);names.append(name)
    return names


def path_figure(paths,run,input_root,geoms):
    sample=read_frame(input_root/'audit_sample.csv').sort_values(['horizon_days','id','origin_source_obs','origin_cell_1'])
    groups=[('resolved',sample[sample.destination_cell_1.ge(0)]),('fallback',sample[sample.reason_code.gt(0)])]
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained');release,domain,high,land=geoms;chosen=[]
    for ax,(name,g) in zip(axes,groups):
        if g.empty:ax.text(.5,.5,'No example available',transform=ax.transAxes);continue
        r=g.iloc[0];ident=int(r.id);f=read_frame(input_root/'paths'/f'{ident}.parquet');start=f.loc[f.source_obs.eq(r.origin_source_obs),'time'].iloc[0]
        path=f[(f.time>=start)&(f.time<=start+r.horizon_days*86400)].copy();x=path.lon.to_numpy();y=path.lat.to_numpy();xx=x+r.dx;yy=y+r.dy
        backdrop(ax,release,domain,land)
        tx,ty=int(r.origin_cell_1)%360-180,int(r.origin_cell_1)//360-90
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                ax.add_patch(Rectangle((tx+dx,ty+dy),1,1,fill=False,edgecolor='#f26a2c' if dx==dy==0 else '#a1b2ba',lw=1.4 if dx==dy==0 else .5,zorder=5))
        ax.plot(x,y,color='#6b7e8c',lw=1,label='Observed neighbour path',zorder=6);ax.plot(xx,yy,color='#2671b9',lw=1,label='Transferred path',zorder=6)
        ax.scatter([x[0],xx[0]],[y[0],yy[0]],c=['#6b7e8c','#2671b9'],s=28,zorder=7)
        ax.set(xlim=(min(x.min(),xx.min())-.5,max(x.max(),xx.max())+.5),ylim=(min(y.min(),yy.min())-.5,max(y.max(),yy.max())+.5),xlabel='Longitude',ylabel='Latitude',title=f'{name}: {REASONS[int(r.reason_code)]}\nID {ident}; {int(r.horizon_days)} days; offset ({int(r.dx)}, {int(r.dy)})')
        ax.legend(fontsize=8);chosen.append(dict(id=ident,origin_source_obs=int(r.origin_source_obs),target=int(r.origin_cell_1),reason=REASONS[int(r.reason_code)]))
    fig.suptitle('Deterministic path examples chosen by source keys | full path shown, not a physical simulation\nA failed transfer contributes its original weight to target B2; it is not deleted.',fontsize=11)
    name='path_transfer_examples.png';save_plot(paths,run,name,fig);return name,chosen


def strata_tables(paths,run,support,high):
    """Descriptive subsets preserve the original case weights, then renormalise."""
    scores=read_frame(run['results']/'heldout_scores.parquet')
    meta=support[['role','horizon_days','origin_cell_1','model','training_id_count']]
    data=scores.merge(meta,on=['role','horizon_days','origin_cell_1','model'],validate='many_to_one')
    data['support_stratum']=pd.cut(data.training_id_count,[0,9,49,np.inf],labels=['1-9 fitting IDs','10-49 fitting IDs','50+ fitting IDs']).astype(str)
    coast={int(i):high.intersects(box(i%360-180,i//360-90,i%360-179,i//360-89)) for i in data.origin_cell_1.unique()}
    data['boundary_stratum']=data.origin_cell_1.map(lambda i:'coastal grid polygon' if coast[i] else 'offshore grid polygon')
    all_tables=[]
    for field in ['support_stratum','boundary_stratum']:
        rows=[]
        for (h,m,s),g in data[data.status.eq('evaluable')].groupby(['horizon_days','model',field]):
            w=g.primary_group_weight.to_numpy();mass=w.sum()
            rows.append(dict(horizon_days=h,model=m,stratum=s,primary_weight_mass=mass,ids=g.id.nunique(),cells=g.origin_cell_1.nunique(),
                **{k:float(np.dot(w,g[k])/mass) for k in ['brier','region90_cells','region90_hit']}))
        table=pd.DataFrame(rows)
        for (h,m),g in table.groupby(['horizon_days','model']):
            assert abs(g.primary_weight_mass.sum()-1)<1e-12
            raw=data[(data.horizon_days==h)&(data.model==m)]
            for k in ['brier','region90_cells','region90_hit']:
                assert abs(np.dot(g.primary_weight_mass,g[k])-np.dot(raw.primary_group_weight,raw[k].fillna(0)))<1e-12
        paths.publish(run['results']/f'{field}.csv',lambda out,table=table:out.write(table.to_csv(index=False).encode()))
        all_tables.append(table.assign(stratum_type=field))
    return pd.concat(all_tables,ignore_index=True)


def write_report(paths,run,input_root,summary,secondary,differences,decisions,selected,base,vectors,support,verification):
    geoms=geometry(paths);roster,maps=candidate_maps(paths,run,base,vectors,geoms)
    strata=strata_tables(paths,run,support,geoms[2])
    figures=diagnostic_figures(paths,run,summary,differences,support,geoms)
    pathplot,pathcases=path_figure(paths,run,input_root,geoms);figures+=[pathplot]+maps
    fields=['horizon_days','model','brier','region90_cells','region90_hit','zero_true_probability','predicted_exit_probability','evaluable_ids','evaluable_pairs']
    view=summary[fields].copy();old=secondary[fields].copy()
    finalsupport=support[(support.role=='all_development_candidate')&(support.model=='LocalDisplacement')&support.supported]
    fallback=finalsupport.groupby('horizon_days').agg(cells=('origin_cell_1','size'),mean_row_fallback=('fallback_fraction','mean'),maximum_row_fallback=('fallback_fraction','max'),mean_row_effective_borrowing=('effective_borrowing_weight','mean')).reset_index()
    diagnosis=read_frame(input_root/'transfer_diagnostics.csv')
    distort=[]
    for h,g in diagnosis.groupby('horizon_days'):
        distort.append(dict(horizon_days=int(h),resolved_transfers=int(g.resolved_in_D.sum()),mean_absolute_distance_change_m=float(g.distance_change_abs_sum_m.sum()/max(g.resolved_in_D.sum(),1)),maximum_absolute_distance_change_m=float(g.distance_change_abs_max_m.max()),mean_absolute_azimuth_change_deg=float(g.azimuth_change_abs_sum_deg.sum()/max(g.azimuth_defined.sum(),1))))
    report=['# Step 3 E1 — Local spatial borrowing','',
        '**Status: independently executed and audited; submitted for user review. Stage closure is pending.**','',
        'This is the first benchmark under the approved S3 grid-path transfer definition. Historical favourable neighbourhood results do not establish success here. All skill values below are nested whole-ID development results, not locked-final-test performance.','',
        '## Model definitions','',
        'B2 uses local raw pair frequencies. Fixed borrows the global B1 reference with a constant per-horizon weight. Adaptive uses the original support-count schedule, retuned under the current target. LocalEndpoint borrows neighbours\' observed stopped destinations. LocalDisplacement translates complete hourly paths in the 1-degree longitude-latitude grid; failed transfer weights return to target B2. The eight-cell neighbourhood excludes self and only contains qualified fitting R-origin records.','',
        'The shift preserves grid-relative increments, not exact geodesic distances. Land and intermediate-hour paths are checked; first observed exits are absorbing E. Endpoint-versus-displacement differences include the geometry/fallback safeguard. No state, probability or failed proposal is deleted to improve the map.','',
        '## Primary held-out comparison','',markdown_table(view),'',
        'Primary aggregation: eligible times within each ID/cell, equal IDs within cell, equal cells. Brier is unnormalised multiclass Brier and is not accuracy. K90 counts geographic cells, not area. H90 includes the stopped outcome E; nominal probability 0.90 need not equal observed coverage. The complete distribution remains stored.','',
        '## Differences and uncertainty','',markdown_table(differences),'',markdown_table(decisions),'',
        'Ordinary 95% paired ID intervals condition on saved fits. The six primary metric/horizon screens use directional 0.05/6 tails. These omit model refitting, shared-training dependence, earlier research adaptation and common ocean forcing. Non-significance is not proof of non-deterioration. Improvement at one horizon does not imply improvement at the other.','',
        '## Selected parameters','',markdown_table(selected[['role','horizon_days','model','parameter_a']]),'',
        '## Transfer safeguards','',markdown_table(fallback),'',
        'The table above is an unweighted mean over supported all-development fitted rows, not held-out case weighting. Effective borrowing is a*(1-fallback fraction). These weights describe the guarded estimator and must not be mistaken for additional independent observations.','',markdown_table(pd.DataFrame(distort)),'',
        'Geodesic distortion is descriptive across resolved transfers, which can reuse the same donor for several target cells. It neither selects donors nor provides extra statistical sample size.','',
        '## Support and boundary diagnostics','',markdown_table(strata),'',
        'Support uses distinct fitting IDs in the actual outer role: 1-9, 10-49, or 50+. Boundary classes use intersection of the origin grid polygon with the pinned high-resolution land mask. These descriptive subsets retain and renormalise the original primary case weights; their weight-mass mixture reproduces the overall score. No strata select models or parameters.','',
        '## Pair-weighted sensitivity','',markdown_table(old),'',
        'These secondary scores use the same newly selected forecasts. They do not choose parameters, replace the primary target, or reproduce the old E1 procedure.','',
        '## Audit and scope','',
        f'- Fitting roles: {verification["fitting_roles_checked"]}; candidate identities: {verification["candidate_identities_checked"]}; candidate ID-cell rows: {verification["candidate_id_cells_checked"]}.',
        f'- Maximum independently reconstructed probability/score errors: {verification["maximum_absolute_errors"]}.',
        f'- Path/ledger check: {verification["path_and_ledger_audit"]}.',
        '- B2 and Fixed matrices, held-out metrics and weights reproduce E4 under the same target. Adaptive is newly tuned. Outer forecasts were frozen before all-development tuning.',
        '- Final-test trajectories were not read. The model does not validate beaching, oil spreading/weathering, seasons, other object types or intermediate horizons.',
        '- Retain all outcomes, including negative or inconclusive results. This run does not automatically select a production model or close Step 3.','',
        '## Visual review','',f'Illustration roster (training support only): {roster}. Path examples are selected by source keys, not forecast success.','']
    for name in figures:report += [f'![{name}]({name})','']
    text='\n'.join(report)
    paths.publish(run['results']/'REPORT.md',lambda out:out.write(text.encode()))
    paths.publish(run['results']/'illustration_roster.json',lambda out:out.write(json.dumps(dict(roster=roster,path_examples=pathcases),indent=2).encode()))
    paths.publish(run['results']/'fallback_summary.csv',lambda out:out.write(fallback.to_csv(index=False).encode()))
    paths.publish(run['results']/'alignment_distortion.csv',lambda out:out.write(pd.DataFrame(distort).to_csv(index=False).encode()))
    html=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>S3 E1 spatial borrowing</title><style>body{max-width:1280px;margin:40px auto;padding:0 20px;background:#f5f7fa;color:#243846;font:16px/1.6 system-ui}h1,h2{line-height:1.2}table{border-collapse:collapse;background:white;font-size:13px;display:block;overflow:auto}th,td{padding:8px;border-bottom:1px solid #ddd;text-align:right}img{width:100%;background:white;border-radius:10px;margin:18px 0}section{margin:35px 0}.note{padding:18px;background:#e8edf5;border-left:4px solid #286cb2}</style>',
        '<h1>Step 3 E1 — Local spatial borrowing</h1><p class="note">Five-model benchmark · Pooled 1° · 7 / 30 days · Whole-ID nested development validation<br>Primary target: equal cells, equal IDs within cell. Fixed 90% regions. Final test remains locked.</p>',
        '<p><a href="REPORT.md">Full scientific report</a> · <a href="summary.csv">Primary data</a> · <a href="paired_differences.csv">Differences and intervals</a> · <a href="row_support.csv">Support and fallback</a></p>',
        '<h2>Held-out results</h2>',view.to_html(index=False,float_format=lambda x:f'{x:.6f}'),'<h2>Primary decision screens</h2>',decisions.to_html(index=False),
        '<p>Smaller regions alone do not establish better prediction. Red interval marks use the prespecified conditional quality screen; they are not independent final-test guarantees.</p>']
    for name in figures:html += ['<section><h2>'+escape(name.replace('_',' ').replace('.png',''))+'</h2><img loading="lazy" src="'+name+'" alt="'+escape(name)+'"></section>']
    html+=['<p>Candidate maps show full-development fits and training-support-selected examples; held-out statistics provide the skill evidence. Full probability tails remain stored.</p></html>']
    paths.publish(run['results']/'review.html',lambda out:out.write(''.join(html).encode()))
