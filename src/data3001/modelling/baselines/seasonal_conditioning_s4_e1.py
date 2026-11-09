"""Two untuned empirical estimators and unchanged hierarchical scoring."""
import numpy as np
import pandas as pd
from data3001.modelling.common.prediction_regions import probability_region

MODELS = ('B2Annual', 'B2SeasonalC1')
METRICS = ('brier', 'h90', 'k90')
FORECAST_KEY = ['model','horizon_days','origin_cell_1','departure_season']


def fit(train, origins, states, config, held_ids):
    cut = pd.Timestamp(config['cutoff'], tz='UTC')
    assert train.origin_time_UTC.ge(pd.Timestamp(config['train_start'],tz='UTC')).all()
    assert train.origin_time_UTC.lt(cut).all() and train.required_interval_end_epoch.lt(cut.timestamp()).all()
    assert not train.id.isin(held_ids).any()
    assert train.destination_cell_1.isin(states).all()
    ix = {int(j):k for k,j in enumerate(states)}
    groups = {key:g for key,g in train.groupby(['horizon_days','origin_cell_1','departure_season'])}
    annual = {key:g for key,g in train.groupby(['horizon_days','origin_cell_1'])}
    matrices, rows = {}, []
    for h in config['horizons']:
        for i in origins:
            for s in [-1,0,1,2,3]:
                g = annual.get((h,i)) if s == -1 else groups.get((h,i,s))
                a = annual.get((h,i))
                fallback = g is None and a is not None and s >= 0
                use = a if fallback else g
                if use is None:
                    p = None
                else:
                    counts = np.bincount(use.destination_cell_1.map(ix).to_numpy(), minlength=len(states))
                    p = counts / counts.sum()
                    assert np.isclose(p.sum(),1,atol=1e-12,rtol=0)
                matrices[(h,int(i),s)] = p
                rows.append({'horizon_days':h,'origin_cell_1':int(i),'departure_season':s,
                    'pairs':0 if g is None else len(g),'ids':0 if g is None else g.id.nunique(),
                    'years':0 if g is None else g.origin_time_UTC.dt.year.nunique(),
                    'destinations':0 if g is None else g.destination_cell_1.nunique(),
                    'dominant_id_share':0. if g is None else float(g.id.value_counts().iloc[0]/len(g)),
                    'annual_pairs':0 if a is None else len(a),
                    'effective_pairs':0 if use is None else len(use),
                    'annual_fallback':fallback,'supported':p is not None})
    return matrices, pd.DataFrame(rows)


def predict(matrices, features, states):
    cache, rows, entries = {}, [], []
    queries = features[['horizon_days','origin_cell_1','departure_season']].drop_duplicates().sort_values(['horizon_days','origin_cell_1','departure_season'])
    for h,i,s in queries.itertuples(index=False,name=None):
        a = matrices[(h,i,-1)]
        p_s = matrices[(h,i,s)]
        for model in MODELS:
            p = a if model == MODELS[0] else p_s
            key = (model,int(h),int(i),int(s))
            if p is None:
                raise ValueError('Unexpected annually unsupported validation origin')
            mask, region = probability_region(p, states)
            entry = {'p':p,'mask':mask,'sum_squares':float(p@p),
                     'k90':region['region90_cells'],'region_mass':region['region90_mass'],
                     'exit_probability':float(p[states == -2][0])}
            cache[key] = entry
            changed = bool(np.max(np.abs(p-a)) > 1e-12)
            rows.append(dict(zip(FORECAST_KEY,key), k90=entry['k90'],region_mass=entry['region_mass'],
                             sum_squares=entry['sum_squares'],exit_probability=entry['exit_probability'],season_changed=changed))
            for k in np.flatnonzero(p):
                entries.append(dict(zip(FORECAST_KEY,key),destination_cell_1=int(states[k]),probability=float(p[k]),in_region=bool(mask[k])))
    return cache, pd.DataFrame(rows), pd.DataFrame(entries)


def score(cache, validation, support, states):
    ix = {int(j):k for k,j in enumerate(states)}
    lookup = support.set_index(['horizon_days','origin_cell_1','departure_season'])
    pieces = []
    for (h,i,s),g in validation.groupby(['horizon_days','origin_cell_1','departure_season']):
        truth = g.destination_cell_1.map(ix).to_numpy()
        a = cache[(MODELS[0],h,i,s)]['p']
        for model in MODELS:
            item = cache[(model,h,i,s)]
            z = g[['id','origin_source_obs','horizon_days','origin_time_UTC','origin_cell_1','departure_season','destination_cell_1','weight']].copy()
            z['model'] = model
            z['brier'] = 1 + item['sum_squares'] - 2*item['p'][truth]
            z['h90'] = item['mask'][truth].astype(float)
            z['k90'] = float(item['k90'])
            z['region_mass'] = item['region_mass']
            z['zero_truth'] = item['p'][truth] == 0
            z['predicted_exit'] = item['exit_probability']
            z['annual_fallback'] = model == MODELS[1] and bool(lookup.loc[(h,i,s),'annual_fallback'])
            z['season_changed'] = model == MODELS[1] and bool(np.max(np.abs(item['p']-a))>1e-12)
            z['training_season_ids'] = int(lookup.loc[(h,i,s),'ids'])
            pieces.append(z)
    cases = pd.concat(pieces,ignore_index=True).sort_values(['model','horizon_days','id','origin_source_obs']).reset_index(drop=True)
    mean = cases.groupby(['model','horizon_days','origin_cell_1','id'],as_index=False)[list(METRICS)].mean()
    summaries=[]
    for (model,h),g in cases.groupby(['model','horizon_days'],sort=True):
        assert np.isclose(g.weight.sum(),1,atol=1e-12,rtol=0)
        out={'model':model,'horizon_days':h,'pairs':len(g),'ids':g.id.nunique(),'origins':g.origin_cell_1.nunique()}
        for m in [*METRICS,'region_mass','zero_truth','predicted_exit','annual_fallback','season_changed']:
            out[m]=float(np.dot(g.weight,g[m]))
        out.update(fallback_pairs=int(g.annual_fallback.sum()),fallback_ids=g.loc[g.annual_fallback,'id'].nunique(),
                   fallback_origins=g.loc[g.annual_fallback,'origin_cell_1'].nunique(),observed_exit_pairs=int(g.destination_cell_1.eq(-2).sum()))
        summaries.append(out)
    slices=[]
    for dimension in ['departure_season','year','annual_fallback','training_support']:
        tmp=cases.copy()
        tmp['year']=tmp.origin_time_UTC.dt.year
        tmp['training_support']=pd.cut(tmp.training_season_ids,[-1,0,4,9,np.inf],labels=['empty','1-4 IDs','5-9 IDs','10+ IDs']).astype(str)
        for (model,h,value),g in tmp.groupby(['model','horizon_days',dimension],observed=True):
            mass=float(g.weight.sum())
            row={'model':model,'horizon_days':h,'dimension':dimension,'value':str(value),'weight':mass,'pairs':len(g),'ids':g.id.nunique()}
            row.update({m:float(np.dot(g.weight,g[m])/mass) for m in METRICS})
            slices.append(row)
    return cases, mean, pd.DataFrame(summaries), pd.DataFrame(slices)


def paired_uncertainty(id_means, validation_ids, config):
    ids = sorted(int(d) for d in validation_ids)
    pos={d:k for k,d in enumerate(ids)}
    rng=np.random.Generator(np.random.PCG64(config['seed']))
    multipliers=rng.exponential(1.,size=(config['uncertainty_replicates'],len(ids)))
    draws=np.zeros((config['uncertainty_replicates'],len(config['horizons']),len(METRICS)))
    for hi,h in enumerate(config['horizons']):
        v=id_means.loc[id_means.horizon_days.eq(h)]
        origins=sorted(v.origin_cell_1.unique())
        for i in origins:
            x=v.loc[v.origin_cell_1.eq(i)].pivot(index='id',columns='model',values=list(METRICS)).sort_index()
            delta=np.column_stack([(x[(m,MODELS[1])]-x[(m,MODELS[0])]).to_numpy() for m in METRICS])
            w=multipliers[:,[pos[int(d)] for d in x.index]]
            draws[:,hi,:]+=(w@delta)/w.sum(axis=1)[:,None]/len(origins)
    intervals=[]
    for hi,h in enumerate(config['horizons']):
        for mi,m in enumerate(METRICS):
            lo,up,adjlo,adjup=np.quantile(draws[:,hi,mi],[.025,.975,.05/config['screens'],1-.05/config['screens']],method='linear')
            intervals.append({'horizon_days':h,'metric':m,'lower95':lo,'upper95':up,'adjusted_lower':adjlo,'adjusted_upper':adjup})
    return multipliers, draws, pd.DataFrame(intervals)


def decisions(summary, intervals):
    rows=[]
    for h in sorted(summary.horizon_days.unique()):
        s=summary.loc[summary.horizon_days.eq(h)].set_index('model')
        delta={m:float(s.loc[MODELS[1],m]-s.loc[MODELS[0],m]) for m in METRICS}
        b=delta['brier'] < -1e-12 and s.loc[MODELS[1],'season_changed']>0
        q=bool(b and delta['h90']>=-1e-12 and delta['k90']<=1e-12)
        ci=intervals.loc[intervals.horizon_days.eq(h)].set_index('metric')
        bs=bool(b and ci.loc['brier','adjusted_upper'] < -1e-12)
        qs=bool(q and bs and ci.loc['h90','adjusted_lower']>=-1e-12 and ci.loc['k90','adjusted_upper']<=1e-12)
        status=('QUALITY_GAIN_SUPPORTED_CONDITIONALLY' if qs else 'QUALITY_NOT_ESTABLISHED' if q else
                'BRIER_GAIN_WITH_QUALITY_TRADEOFF' if b else 'NO_BRIER_POINT_GAIN')
        row={'horizon_days':int(h),**{'delta_'+k:v for k,v in delta.items()},
             'BRIER_POINT_GAIN':bool(b),'QUALITY_POINT_GAIN':q,'BRIER_GAIN_SUPPORTED_CONDITIONALLY':bs,
             'QUALITY_GAIN_SUPPORTED_CONDITIONALLY':qs,'status':status}
        for m in METRICS:
            ref=float(s.loc[MODELS[0],m]);row['relative_'+m]=delta[m]/ref if ref else None
        rows.append(row)
    return pd.DataFrame(rows)
