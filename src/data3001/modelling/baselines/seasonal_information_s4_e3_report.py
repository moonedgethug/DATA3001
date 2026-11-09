"""Local review of both hypotheses, support diagnostics and operational trade-offs."""
import io
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

COLORS=['#25677e','#ab5744','#268060']


def write_report(paths, directory, tables, choices, curves, info, timing_only):
    plots=[]
    def save(name,fig):
        if timing_only:
            fig.suptitle('Resource pilot with synthetic outer outcomes')
        data=io.BytesIO()
        fig.savefig(data,format='png',dpi=140,facecolor='white',metadata={'Software':'DATA3001 seasonal information E3'})
        plt.close(fig);paths.publish(directory/name,lambda f:f.write(data.getvalue()));plots.append(name)
    summary=tables['summary'];test=tables['primary_test'];diag=tables['matched_diagnostic']
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for ax,h in zip(axes,[7,30]):
        for fold,g in curves[curves.horizon_days.eq(h)].groupby('fold'):
            ax.plot(g.c,g.brier,label=fold,linewidth=2 if fold=='pooled' else 1)
        ax.axvline(choices.loc[choices.horizon_days.eq(h),'c'].iloc[0],ls='--',color='#383838')
        ax.set(title=f'{h} days | training-period selection',xlabel='Seasonal weight c',ylabel='Inner Brier')
        ax.legend()
    save('training_weights.png',fig)
    fig,axes=plt.subplots(2,3,figsize=(12,7),layout='constrained')
    for row,h in enumerate([7,30]):
        data=summary[summary.horizon_days.eq(h)]
        for col,(m,title) in enumerate([('brier','Brier'),('h90','Actual hits (%)'),('k90','Geographic cells')]):
            ax=axes[row,col];v=data[m]*(100 if m=='h90' else 1)
            ax.bar(['Annual','Hard season','Adjusted'],v,color=COLORS)
            ax.bar_label(ax.containers[0],fmt='%.4f' if m=='brier' else '%.2f',fontsize=9)
            ax.set(title=f'{h} days | {title}',ylim=(0,max(v)*1.18))
    save('outer_metrics.png',fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,r in zip(axes,test.itertuples(index=False)):
        ax.plot([r.lower95,r.upper95],[1,1],lw=3,color=COLORS[0])
        ax.scatter(r.delta_brier,1,color=COLORS[2],label='Observed difference')
        ax.scatter(r.centered_upper,1.12,marker='|',s=150,color=COLORS[1],label='Adjusted one-sided upper bound')
        ax.axvline(0,ls='--',color='gray');ax.set(yticks=[],ylim=(.85,1.55),xlabel='Adjusted minus annual Brier',title=f'{r.horizon_days} days | paired drifter contrast')
        ax.legend(loc='upper right',fontsize=8)
    save('paired_test.png',fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,h in zip(axes,[7,30]):
        sub=diag[(diag.horizon_days==h)&(diag.estimable==True)]
        for k,r in enumerate(sub.itertuples(index=False)):
            for offset,name,color in [(-.1,'sample_cost',COLORS[0]),(.1,'season_recovery',COLORS[2])]:
                y=k+offset;ax.plot([getattr(r,name+'_lower95'),getattr(r,name+'_upper95')],[y,y],color=color,lw=2)
                ax.scatter(getattr(r,name),y,color=color,label=name.replace('_',' ') if k==0 else None)
        ax.set(yticks=range(len(sub)),yticklabels=sub.subset,title=f'{h} days | matched samples',xlabel='Brier contrast (positive = cost / recovery)')
        ax.axvline(0,ls='--',color='gray');ax.legend(fontsize=8)
    save('matched_cost_and_recovery.png',fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for ax,h in zip(axes,[7,30]):
        z=info[(info.horizon_days==h)&(info.pairs>0)]
        ax.scatter(z.ids,z.other_share_mean,alpha=.6,color=COLORS[0],s=17)
        ax.axhline(.25,color=COLORS[1],ls='--')
        ax.set(title=f'{h} days | nonempty training tables',xlabel='Seasonal drifter IDs',ylabel='Mean other-season pair share',ylim=(-.02,1.02))
    save('donor_mixing.png',fig)
    title='Departure season and future drifter destinations'
    flag='Synthetic-target capacity fixture. ' if timing_only else ''
    intro=(flag+'Training 2001–2019, validation on available 2020–2022 departures. A seasonal weight per horizon was chosen using two internal forward windows. '
           'Negative adjusted-minus-annual Brier favors the seasonal correction. The centered upper bound must be below zero to support a gain. '
           'Intervals condition on fitted forecasts and historical development data.')
    sections=[('Training-only weights',choices),('Outer forecasts',summary),('Paired primary test',test),('Equal-sample diagnostic',diag)]
    body='<!doctype html><html lang="en"><meta charset="utf-8"><title>'+title+'</title><style>body{font:16px system-ui;max-width:1220px;margin:32px auto;padding:0 18px;color:#21333a}img{width:100%}section{overflow:auto}table{border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid #ddd;padding:6px;text-align:right}p{line-height:1.55}</style><h1>'+title+'</h1><p>'+intro+'</p>'
    for h in [7,30]:
        r=test[test.horizon_days==h].iloc[0];d=diag[(diag.horizon_days==h)&(diag.subset=='all')].iloc[0]
        body+=f'<p><b>{h} days.</b> Seasonal Brier evidence: {bool(r.brier_supported)}. Point-level quality-preserving gain: {bool(r.point_quality)}. Informative matching covers {d.informative_weight:.1%} of validation weight (population threshold 80%).</p>'
    for name,z in sections:body+='<section><h2>'+name+'</h2>'+z.to_html(index=False,float_format=lambda v:f'{v:.6f}')+'</section>'
    body+=''.join('<img alt="'+n+'" src="'+n+'">' for n in plots)+'</html>'
    paths.publish(directory/'review.html',lambda f:f.write(body.encode()))
    report='# '+title+'\n\n'+intro+'\n\n'
    for name,z in sections:report+='## '+name+'\n\n```csv\n'+z.to_csv(index=False)+'```\n\n'
    paths.publish(directory/'REPORT.md',lambda f:f.write(report.encode()))
