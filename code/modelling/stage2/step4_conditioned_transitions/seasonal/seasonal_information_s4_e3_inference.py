"""Paired Brier decision and predictive-cost decomposition with whole-ID weights."""
import numpy as np
import pandas as pd
from data3001.modelling.baselines.seasonal_information_s4_e3 import MODELS


def multiplier_summary(cases, multipliers, id_index, columns, mask):
    data=cases[['origin_cell_1','id']].copy()
    data['mass']=mask.astype(float)
    data[columns]=cases[columns].to_numpy()*data.mass.to_numpy()[:,None]
    units=data.groupby(['origin_cell_1','id']).mean().reset_index()
    names=['mass',*columns]
    totals=np.zeros((len(multipliers),len(names)))
    point=np.zeros(len(names))
    origins=units.origin_cell_1.nunique()
    for _,g in units.groupby('origin_cell_1'):
        v=g[names].to_numpy()
        w=multipliers[:,[id_index[d] for d in g.id]]
        totals+=(w@v)/w.sum(axis=1)[:,None]/origins
        point+=v.mean(axis=0)/origins
    mass=cases.loc[mask,'weight'].sum()
    assert abs(point[0]-mass)<1e-12
    obs=point[1:]/point[0]
    expected=(cases.loc[mask,'weight'].to_numpy()@cases.loc[mask,columns].to_numpy())/mass
    assert np.allclose(expected,obs,atol=1e-12,rtol=0)
    return obs,totals[:,1:]/totals[:,:1]


def inference(cases, rep_scores, config):
    ids=sorted(cases.id.unique())
    weights=np.random.Generator(np.random.PCG64(config['bootstrap_seed'])).exponential(size=(config['bootstrap_draws'],len(ids)))
    id_index={d:k for k,d in enumerate(ids)}
    summary=[]; primary=[]; diag=[]; draws=[]; draw_keys=[]; rep_table=[]; slices=[]
    cols=['delta_brier','delta_h90','delta_k90','sample_cost','season_recovery','net_cost']
    for h,raw in cases.groupby('horizon_days'):
        g=raw.copy()
        for metric in ['brier','h90','k90']:
            g['delta_'+metric]=g['Adjusted_'+metric]-g['Annual_'+metric]
        g['sample_cost']=g.Matched_brier-g.Annual_brier
        g['season_recovery']=g.Matched_brier-g.HardSeason_brier
        g['net_cost']=g.HardSeason_brier-g.Annual_brier
        assert np.allclose(g.sample_cost-g.season_recovery,g.net_cost,atol=1e-12,rtol=0)
        for model in MODELS:
            row=dict(horizon_days=h,model=model,pairs=len(g),ids=g.id.nunique(),origins=g.origin_cell_1.nunique())
            for metric in ['brier','h90','k90','region_mass','zero','destinations','exit']:
                row[metric]=g.weight@g[model+'_'+metric]
            row.update(fallback_pairs=int(g.fallback.sum()),fallback_weight=g.weight@g.fallback.astype(float),
                       lost_truth=g.weight@g.lost_truth,observed_exit=g.weight@g.observed_exit)
            summary.append(row)
        for dim,values in [('year',g.origin_time_UTC.dt.year),('departure_season',g.departure_season),
                           ('training_season_IDs',pd.cut(g.season_ids,[-1,0,4,9,np.inf],labels=['empty','1–4','5–9','10+']))]:
            for category,part in g.groupby(values,observed=True):
                for model in MODELS:
                    w=part.weight/part.weight.sum()
                    slices.append((h,dim,str(category),model,part.weight.sum(),len(part),part.id.nunique(),
                                   *(w@part[model+'_'+m] for m in ['brier','h90','k90'])))
        informative_weight=float(g.loc[g.informative,'weight'].sum())
        subsets={'all':np.ones(len(g),dtype=bool),'nonempty':~g.fallback.to_numpy(),'informative':g.informative.to_numpy()}
        for label,mask in subsets.items():
            sel=g.loc[mask];mass=float(sel.weight.sum())
            if not mass:
                diag.append(dict(horizon_days=h,subset=label,estimable=False,original_weight=0.,pairs=0))
                continue
            obs,sim=multiplier_summary(g,weights,id_index,cols,mask)
            draws.append(sim);draw_keys.append((h,label))
            lower,upper=np.quantile(sim,[.025,.975],axis=0)
            if label=='all':
                bound=obs[0]-np.quantile(sim[:,0]-obs[0],.025)
                primary.append(dict(horizon_days=h,delta_brier=obs[0],lower95=lower[0],upper95=upper[0],
                                    centered_upper=bound,brier_supported=bool(bound<0),delta_h90=obs[1],h90_lower95=lower[1],
                                    h90_upper95=upper[1],delta_k90=obs[2],k90_lower95=lower[2],k90_upper95=upper[2],
                                    point_quality=bool(obs[0]<-1e-12 and obs[1]>=-1e-12 and obs[2]<=1e-12)))
                # Independently rebuild the paired primary distribution with normalized weights.
                check=np.zeros(len(weights))
                for _,unit in g.groupby('origin_cell_1'):
                    v=unit.groupby('id').delta_brier.mean()
                    w=weights[:,[id_index[d] for d in v.index]];w=w/w.sum(axis=1)[:,None]
                    check+=np.einsum('rd,d->r',w,v)/g.origin_cell_1.nunique()
                assert np.allclose(sim[:,0],check,rtol=0,atol=1e-12)
                assert abs(bound-(obs[0]-np.quantile(check-obs[0],.025)))<1e-12
            w=sel.weight.to_numpy()/mass
            group_keys=sel.groupby(['horizon_days','origin_cell_1','departure_season']).groups
            replicas=sum(rep_scores[key] for key in group_keys)/mass
            row=dict(horizon_days=h,subset=label,estimable=True,pairs=len(sel),ids=sel.id.nunique(),
                     original_weight=mass,informative_weight=informative_weight,population_mixing_gate=informative_weight>=.8,
                     other_season_pair_share=w@sel.other_share)
            for model in ['Annual','HardSeason','Matched']:
                for metric in ['brier','zero','destinations']:
                    row[model+'_'+metric]=w@sel[model+'_'+metric]
            assert abs(replicas.mean()-row['Matched_brier'])<1e-12
            for idx,name,ref in [(3,'sample_cost','Annual'),(4,'season_recovery','HardSeason')]:
                replicate_delta=replicas-row[ref+'_brier']
                se=replicate_delta.std(ddof=1)/np.sqrt(len(replicas))
                assert abs(obs[idx]-replicate_delta.mean())<1e-12
                row.update({name:obs[idx],name+'_lower95':lower[idx],name+'_upper95':upper[idx],name+'_mcse':se,
                            name+'_sign_resolved':bool((lower[idx]>0 and obs[idx]-1.96*se>0) or (upper[idx]<0 and obs[idx]+1.96*se<0))})
            row['net_cost']=obs[5]
            assert abs(obs[3]-obs[4]-obs[5])<1e-12
            diag.append(row)
            rep_table.extend((h,label,k,value) for k,value in enumerate(replicas))
    tables={'summary':pd.DataFrame(summary),'primary_test':pd.DataFrame(primary),'matched_diagnostic':pd.DataFrame(diag),
            'replicate_scores':pd.DataFrame(rep_table,columns=['horizon_days','subset','replicate','brier']),
            'slices':pd.DataFrame(slices,columns=['horizon_days','dimension','value','model','weight','pairs','ids','brier','h90','k90']),
            'draw_keys':pd.DataFrame(draw_keys,columns=['horizon_days','subset'])}
    return tables,weights,np.stack(draws),ids,cols
