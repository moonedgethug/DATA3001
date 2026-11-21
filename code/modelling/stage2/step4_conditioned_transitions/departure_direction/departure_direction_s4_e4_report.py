"""Paired inference, fallback exposure, and local presentation of E4 forecasts."""
import io
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from data3001.modelling.baselines.seasonal_information_s4_e3_inference import multiplier_summary

METRICS=['brier','h90','k90']
LABELS=['Annual','Adjusted']
COLORS=['#37677e','#278464']


def evaluate(cases,roster,cfg):
    rows=[];tests=[];coverage=[];by_group=[];units=[];simulated=[]
    ids=sorted(cases.id.unique());id_ix={d:k for k,d in enumerate(ids)}
    draws=np.random.Generator(np.random.PCG64(cfg['bootstrap_seed'])).exponential(size=(cfg['bootstrap_draws'],len(ids)))
    for h,g0 in cases.groupby('horizon_days'):
        g=g0.copy();base=roster[roster.horizon_days==h]
        for name in LABELS:
            cols=METRICS+['zero','exit','mass']
            s={m:g.weight@g[name+'_'+m] for m in cols}
            rows.append(dict(horizon_days=h,model=name,**s,pairs=len(g),ids=g.id.nunique(),origins=g.origin_cell_1.nunique(),
                             eligible_pairs=len(base),unsupported_pairs=int((~base.supported).sum()),unsupported_weight=base.loc[~base.supported,'eligible_weight'].sum(),
                             observed_exit=g.weight@g.observed_exit,missing_donor_share=g.weight@g.missing_donor_share))
        for m in METRICS:g['delta_'+m]=g['Adjusted_'+m]-g['Annual_'+m]
        columns=['delta_'+m for m in METRICS]
        observed,sim=multiplier_summary(g,draws,id_ix,columns,np.ones(len(g),dtype=bool))
        means=g.groupby(['origin_cell_1','id'])[columns].mean()
        units.append(means.reset_index().assign(horizon_days=h))
        assert np.allclose(means.groupby(level=0).mean().mean(),observed,rtol=0,atol=1e-12)
        independent=np.zeros_like(sim)
        for _,v in means.reset_index().groupby('origin_cell_1'):
            w=draws[:,[id_ix[d] for d in v.id]]
            independent+=np.einsum('rd,dk->rk',w/w.sum(axis=1)[:,None],v[columns])/g.origin_cell_1.nunique()
        assert np.allclose(independent,sim,rtol=0,atol=1e-12)
        simulated.append(sim)
        lo,hi=np.quantile(sim,[.025,.975],axis=0)
        upper=observed[0]-np.quantile(sim[:,0]-observed[0],.025)
        assert abs(upper-(2*observed[0]-np.quantile(independent[:,0],.025)))<1e-12
        t=dict(horizon_days=h,centered_upper=upper,brier_supported=bool(upper<0),
               point_quality=bool(observed[0]<-1e-12 and observed[1]>=-1e-12 and observed[2]<=1e-12))
        for k,m in enumerate(METRICS):
            t.update({f'delta_{m}':observed[k],m+'_lower95':lo[k],m+'_upper95':hi[k]})
        tests.append(t)
        fallback=g.fallback_reason.ne('valid')
        for label,mask in [('any_fallback',fallback),('query_unavailable',fallback & g.fallback_reason.ne('empty_usable_donor_row')),
                           ('no_usable_donors_independent',g.no_usable_donors),('direction_used',~fallback),
                           *[(n,g.fallback_reason.eq(n)) for n in ['first_row','time_gap','position_quality','zero_speed','low_speed','empty_usable_donor_row','no_positive_fit_speed']]]:
            z=g[mask];w=z.weight.sum()
            coverage.append(dict(horizon_days=h,reason=label,cases=len(z),case_fraction=len(z)/len(base),weight=w,
                                 ids=z.id.nunique(),origins=z.origin_cell_1.nunique()))
            if w:
                for name in LABELS:
                    by_group.append(dict(horizon_days=h,group=label,model=name,original_weight=w,
                                         **{m:(z.weight/w)@z[name+'_'+m] for m in METRICS}))
        assert np.all(g.loc[fallback,columns].to_numpy()==0)
    tables={'summary':pd.DataFrame(rows),'primary_test':pd.DataFrame(tests),'fallback':pd.DataFrame(coverage),
            'strata':pd.DataFrame(by_group),'id_origin_differences':pd.concat(units,ignore_index=True)}
    return tables,draws,np.stack(simulated),ids


def report(paths,directory,tables,choices,curves,thresholds,pilot):
    images=[]
    def save(name,fig):
        if pilot:fig.suptitle('Capacity fixture | synthetic validation targets')
        data=io.BytesIO();fig.savefig(data,format='png',dpi=145,facecolor='white',metadata={'Software':'DATA3001 E4'})
        plt.close(fig);paths.publish(directory/name,lambda f:f.write(data.getvalue()));images.append(name)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,h in zip(axes,[7,30]):
        for label,g in curves[curves.horizon_days==h].groupby('fold'):
            ax.plot(g.lambda_h,g.brier,label=label,lw=2.8 if label=='pooled' else 1.2)
        lam=choices.loc[choices.horizon_days==h,'lambda_h'].iloc[0]
        ax.axvline(lam,ls='--',color='#333');ax.set(xlabel='Heading adjustment strength',ylabel='Inner Brier',
                                                     title=f'{h} days | selected λ = {lam:.3f}');ax.legend()
    save('inner_curves.png',fig)
    fig,axes=plt.subplots(2,3,figsize=(12,7),layout='constrained')
    for row,h in enumerate([7,30]):
        z=tables['summary'][tables['summary'].horizon_days==h].set_index('model').loc[LABELS]
        for col,(m,title) in enumerate(zip(METRICS,['Brier','Actual hits (%)','90% region cells'])):
            ax=axes[row,col];v=z[m]*(100 if m=='h90' else 1)
            bars=ax.bar(['Annual B2','Heading B2'],v,color=COLORS)
            ax.bar_label(bars,fmt='%.5f' if m=='brier' else '%.2f')
            ax.set(title=f'{h} days | {title}',ylim=(0,max(v)*1.20))
    save('outer_metrics.png',fig)
    fig,axes=plt.subplots(1,3,figsize=(13,3.8),layout='constrained')
    for ax,m,title in zip(axes,METRICS,['Brier difference','Hit-rate difference (pp)','Region-size difference (cells)']):
        scale=100 if m=='h90' else 1
        for k,(_,r) in enumerate(tables['primary_test'].iterrows()):
            ax.plot([r[m+'_lower95']*scale,r[m+'_upper95']*scale],[k,k],color=COLORS[0],lw=3)
            ax.scatter(r['delta_'+m]*scale,k,color=COLORS[1],zorder=3)
            if m=='brier':ax.scatter(r.centered_upper,k+.12,marker='|',s=150,color='#a85034',label='One-sided upper' if k==0 else None)
        ax.axvline(0,ls='--',color='gray');ax.set(yticks=[0,1],yticklabels=['7 days','30 days'],ylim=(-.4,1.5),title=title)
        if m=='brier':ax.legend(fontsize=8)
    fig.suptitle('Heading B2 minus annual B2 | paired estimates and 95% intervals')
    save('paired_differences.png',fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    reasons=['time_gap','first_row','position_quality','zero_speed','low_speed','empty_usable_donor_row','no_positive_fit_speed']
    for ax,h in zip(axes,[7,30]):
        z=tables['fallback'][tables['fallback'].horizon_days==h].set_index('reason')
        groups=[s for s in reasons if z.loc[s,'cases']>0]
        x=np.arange(len(groups));ax.bar(x-.18,100*z.loc[groups,'case_fraction'],.36,label='Pairs',color=COLORS[0])
        ax.bar(x+.18,100*z.loc[groups,'weight'],.36,label='Evaluation weight',color=COLORS[1])
        ax.set_xticks(x,[s.replace('_',' ') for s in groups],rotation=18,ha='right')
        ax.set(title=f'{h} days | fallback to annual B2',ylabel='Share (%)');ax.legend()
    save('fallback.png',fig)
    title='Departure heading and future drifter destinations'
    para=('Synthetic outer outcomes for resource timing. ' if pilot else '')+('Use the hour ending at departure, with a fitting-only low-speed threshold. '
          'Both methods face identical 2020–2022 cases. The primary comparison is heading-adjusted minus annual Brier. '
          'Its corrected one-sided upper bound must be negative to support an improvement. Hits and region size qualify the operational trade-off.')
    sections=[('Training selections',choices),('Matched outer metrics',tables['summary']),('Paired decisions',tables['primary_test']),
              ('Fallback exposure',tables['fallback']),('Fitting thresholds',thresholds)]
    html='<!doctype html><html lang="en"><meta charset="utf-8"><title>'+title+'</title><style>body{font:16px system-ui;max-width:1200px;margin:30px auto;padding:0 18px;color:#253944}img{width:100%}section{overflow:auto}table{border-collapse:collapse;font-size:13px}td,th{padding:6px;border-bottom:1px solid #ddd}</style><h1>'+title+'</h1><p>'+para+'</p>'
    for r in tables['primary_test'].itertuples():
        result='passes' if r.brier_supported else 'does not pass'
        html+=f'<p><b>{r.horizon_days} days.</b> The paired Brier test {result}. Point-level quality preservation: {r.point_quality}.</p>'
    html+=''.join('<img alt="'+n+'" src="'+n+'">' for n in images)
    md='# '+title+'\n\n'+para+'\n\n'
    for name,z in sections:
        html+='<section><h2>'+name+'</h2>'+z.to_html(index=False,float_format=lambda x:f'{x:.6f}')+'</section>'
        md+='## '+name+'\n\n```csv\n'+z.to_csv(index=False)+'```\n\n'
    paths.publish(directory/'review.html',lambda f:f.write((html+'</html>').encode()))
    paths.publish(directory/'REPORT.md',lambda f:f.write(md.encode()))
