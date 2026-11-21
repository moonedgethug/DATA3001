"""Validation adapters for frozen Step 1–3 estimators; no new estimator family."""
import numpy as np
import pandas as pd
from data3001.modelling.baselines import local_endpoint_adaptive_s3_e2 as legacy
from data3001.modelling.baselines.temporal_validation_s4_e2_inputs import counts
from data3001.modelling.common.prediction_regions import probability_region

MODELS = legacy.MODELS
SPECS = legacy.specifications()
SCORE_COLS = [f'candidate_{k:03d}' for k in range(len(SPECS))]
UNIT = ['horizon_days','origin_cell_1','id']
METRICS = ['brier','h90','k90']
DIAGNOSTICS = ['region_mass','zero_truth','true_probability','predicted_exit','observed_exit']


def fit_role(role, bundle):
    return legacy.fit_bases(counts(role['train']), sorted(role['train'].id.unique()),
                            bundle['origins'], bundle['states'])


def candidate_brier(base, validation):
    """Compute only the selection score using unchanged legacy probability vectors."""
    if set(base.b2.training_ids) & set(validation.id):
        raise ValueError('Inner fitting/validation ID leakage')
    out=[]
    for (h,i), g in counts(validation).groupby(['horizon_days','origin_cell_1']):
        ident = sorted(g.id.unique()); di = {d:k for k,d in enumerate(ident)}
        n = g.groupby('id').pair_count.sum().reindex(ident).to_numpy()
        common = pd.DataFrame(dict(horizon_days=h, origin_cell_1=i, id=ident, eligible_pairs=n,
                                   supported=(h,i) in base.rows))
        values = np.full((len(ident),len(SPECS)),np.nan)
        if (h,i) in base.rows:
            js = sorted(g.destination_cell_1.unique()); ji = {j:k for k,j in enumerate(js)}
            observed = np.zeros((len(ident),len(js)))
            for r in g.itertuples(index=False): observed[di[r.id],ji[r.destination_cell_1]] = r.pair_count
            vectors = np.array([legacy.vector(base,h,i,m,a,gamma) for m,a,gamma in SPECS])
            values = 1 + np.square(vectors).sum(axis=1)[None,:] - 2*(observed/n[:,None])@vectors[:,[base.index[j] for j in js]].T
        out.append(pd.concat([common,pd.DataFrame(values,columns=SCORE_COLS)],axis=1))
    return pd.concat(out,ignore_index=True)


def pool_candidates(parts):
    """Combine repeated ID/cell units across time folds by their valid pair counts."""
    z = pd.concat(parts,ignore_index=True)
    z['scored_pairs'] = np.where(z.supported,z.eligible_pairs,0)
    values = z[SCORE_COLS].fillna(0).to_numpy()*z.scored_pairs.to_numpy()[:,None]
    values = pd.DataFrame(values,columns=SCORE_COLS)
    weighted = pd.concat([z[UNIT+['eligible_pairs','scored_pairs']].reset_index(drop=True),values],axis=1)
    collapsed = weighted.groupby(UNIT,as_index=False).sum(numeric_only=True)
    good = collapsed.scored_pairs.gt(0)
    collapsed.loc[good,SCORE_COLS] = collapsed.loc[good,SCORE_COLS].to_numpy()/collapsed.loc[good,'scored_pairs'].to_numpy()[:,None]
    collapsed.loc[~good,SCORE_COLS] = np.nan
    rows=[]
    for h,allg in collapsed.groupby('horizon_days'):
        g = allg[allg.scored_pairs.gt(0)]
        if g.empty: raise ValueError('No supported inner validation cases')
        w = 1/(g.origin_cell_1.nunique()*g.groupby('origin_cell_1').id.transform('size').to_numpy())
        scores = w@g[SCORE_COLS].to_numpy()
        for k,(m,a,gamma) in enumerate(SPECS):
            rows.append(dict(horizon_days=h,candidate=k,model=m,parameter_a=a,parameter_gamma=gamma,brier=float(scores[k]),
                eligible_pairs=int(allg.eligible_pairs.sum()),scored_pairs=int(g.scored_pairs.sum()),
                eligible_ids=allg.id.nunique(),scored_ids=g.id.nunique(),scored_origins=g.origin_cell_1.nunique(),
                unsupported_pairs=int(allg.eligible_pairs.sum()-g.scored_pairs.sum())))
    return collapsed,pd.DataFrame(rows)


def select(pool):
    selected=[]
    for (h,m),g in pool.groupby(['horizon_days','model']):
        tied=g[g.brier.le(g.brier.min()+1e-12)]
        selected.append(tied.sort_values(['parameter_gamma','parameter_a']).iloc[0].to_dict())
    selected=pd.DataFrame(selected)
    selected['family_rank']=selected.model.map({m:k for k,m in enumerate(MODELS)})
    selected['winner']=False
    for h,g in selected.groupby('horizon_days'):
        best=g[g.brier.le(g.brier.min()+1e-12)].sort_values('family_rank').index[0]
        selected.loc[best,'winner']=True
    return selected.sort_values(['horizon_days','family_rank']).reset_index(drop=True)


def forecast_block(base, selected, features, block):
    cache={}; meta=[]
    for policy,chosen in selected.items():
        for h,i in features[['horizon_days','origin_cell_1']].drop_duplicates().sort_values(['horizon_days','origin_cell_1']).itertuples(index=False,name=None):
            choices=chosen[chosen.horizon_days.eq(h)]
            for label in [*MODELS,'Selected']:
                row=choices.loc[choices.winner if label=='Selected' else choices.model.eq(label)].iloc[0]
                p=legacy.vector(base,h,i,row.model,row.parameter_a,row.parameter_gamma)
                key=(block,policy,label,h,i)
                record=dict(block=block,policy=policy,model=label,selected_family=row.model,horizon_days=h,origin_cell_1=i,
                    parameter_a=float(row.parameter_a),parameter_gamma=float(row.parameter_gamma),supported=p is not None)
                if p is None:
                    cache[key]=None
                else:
                    mask,region=probability_region(p,base.states)
                    item=dict(p=p.copy(),mask=mask,sum_squares=float(p@p),k90=int(region['region90_cells']),
                              region_mass=float(p[mask].sum()),predicted_exit=float(p[base.index[-2]]))
                    cache[key]=item
                    record.update(k90=item['k90'],region_mass=item['region_mass'],sum_squares=item['sum_squares'],
                                  borrowing_weight=legacy.applied_weight(base,h,i,row.model,row.parameter_a,row.parameter_gamma))
                meta.append(record)
    for key,item in cache.items():
        if key[1]=='G' and key[2]=='B2':
            other=cache[(block,'T','B2',key[3],key[4])]
            assert (item is None)==(other is None)
            if item is not None: assert np.array_equal(item['p'],other['p'])
    return cache,pd.DataFrame(meta)


def score_block(cache, validation, block, states):
    """Exact sufficient-case scores; multiplicity preserves every eligible origin."""
    ix={int(j):k for k,j in enumerate(states)}; pieces=[]
    for (h,i),g in counts(validation).groupby(['horizon_days','origin_cell_1']):
        for policy in ['G','T']:
            for m in [*MODELS,'Selected']:
                z=g.copy();item=cache[(block,policy,m,h,i)]
                z['block']=block;z['policy']=policy;z['model']=m;z['supported']=item is not None
                for field in METRICS+DIAGNOSTICS: z[field]=np.nan
                if item is not None:
                    pos=g.destination_cell_1.map(ix).to_numpy()
                    pt=item['p'][pos]
                    z['brier']=1+item['sum_squares']-2*pt
                    z['h90']=item['mask'][pos].astype(float);z['k90']=item['k90']
                    z['region_mass']=item['region_mass'];z['zero_truth']=(pt==0).astype(float)
                    z['true_probability']=pt;z['predicted_exit']=item['predicted_exit']
                    z['observed_exit']=g.destination_cell_1.eq(-2).astype(float)
                pieces.append(z)
    return pd.concat(pieces,ignore_index=True)


def summaries(cases):
    ident=['block','policy','model','horizon_days']; metrics=METRICS+DIAGNOSTICS
    weighted=cases[ident+['origin_cell_1','id','pair_count']].copy()
    weighted['scored_pairs']=np.where(cases.supported,cases.pair_count,0)
    for m in metrics: weighted[m]=cases[m].fillna(0)*weighted.scored_pairs
    units=weighted.groupby(ident+['origin_cell_1','id'],as_index=False).sum(numeric_only=True)
    good=units.scored_pairs.gt(0)
    units.loc[good,metrics]=units.loc[good,metrics].to_numpy()/units.loc[good,'scored_pairs'].to_numpy()[:,None]
    units.loc[~good,metrics]=np.nan
    rows=[]
    for key,g in units.groupby(ident):
        valid=g[g.scored_pairs.gt(0)]
        if valid.empty:raise ValueError('Empty supported outer evaluation')
        w=1/(valid.origin_cell_1.nunique()*valid.groupby('origin_cell_1').id.transform('size').to_numpy())
        membership=g.groupby('origin_cell_1').scored_pairs.agg(lambda a:float(a.gt(0).mean()))
        row=dict(zip(ident,key));row.update(pairs=int(g.pair_count.sum()),ids=g.id.nunique(),origins=g.origin_cell_1.nunique(),
            scored_pairs=int(valid.scored_pairs.sum()),scored_ids=valid.id.nunique(),scored_origins=valid.origin_cell_1.nunique(),
            unsupported_pairs=int(g.pair_count.sum()-valid.scored_pairs.sum()),
            unsupported_ids=int(g.loc[g.scored_pairs.eq(0),'id'].nunique()),target_availability=float(membership.mean()))
        for k,m in enumerate(metrics):
            row[m]=float(w@valid[m].to_numpy())
            row['pair_'+m]=float(np.average(valid[m],weights=valid.scored_pairs))
        rows.append(row)
    return units,pd.DataFrame(rows)


def uncertainty(units, config):
    z=units[(units.model=='Selected') & units.scored_pairs.gt(0)]
    ids=sorted(z.id.unique());lookup={d:k for k,d in enumerate(ids)}
    multipliers=np.random.Generator(np.random.PCG64(config['seed'])).exponential(1.,(config['replicates'],len(ids)))
    draws={}; intervals=[]
    for (b,h,policy),g in z.groupby(['block','horizon_days','policy']):
        v=np.zeros((config['replicates'],3))
        for i,c in g.groupby('origin_cell_1'):
            assert not c.id.duplicated().any()
            w=multipliers[:,[lookup[d] for d in c.id]]
            v+=(w@c[METRICS].to_numpy())/w.sum(axis=1)[:,None]/g.origin_cell_1.nunique()
        draws[(b,h,policy)]=v
    blocks=[b['name'] for b in config['blocks']]; values=[]
    for b in blocks:
        for h in [7,30]:
            g=draws[(b,h,'G')];t=draws[(b,h,'T')];delta=t-g
            relative=np.divide(delta[:,2],g[:,2],out=np.full(len(g),np.nan),where=g[:,2]!=0)
            values.append(np.column_stack([delta,relative]))
            for k,m in enumerate([*METRICS,'relative_k90']):
                x=values[-1][:,k]
                bounds=np.quantile(x,[.025,.975,config['tail'],1-config['tail']]) if np.isfinite(x).all() else [np.nan]*4
                intervals.append(dict(block=b,horizon_days=h,metric=m,lower95=bounds[0],upper95=bounds[1],
                                      adjusted_lower=bounds[2],adjusted_upper=bounds[3]))
    return ids,multipliers,np.stack(values,axis=1),pd.DataFrame(intervals)


def decisions(summary, intervals, config):
    rows=[]
    selected=summary[summary.model=='Selected'].set_index(['block','horizon_days','policy'])
    for b in [x['name'] for x in config['blocks']]:
        for h in [7,30]:
            g=selected.loc[(b,h,'G')];t=selected.loc[(b,h,'T')]
            d=t[METRICS]-g[METRICS]
            ci=intervals[(intervals.block==b)&(intervals.horizon_days==h)].set_index('metric')
            equivalent=all(ci.loc[m,'adjusted_lower']>=-v and ci.loc[m,'adjusted_upper']<=v for m,v in config['equivalence'].items())
            point=bool(d.brier < -1e-12 and d.h90>=-1e-12 and d.k90<=1e-12)
            gain=bool(point and ci.loc['brier','adjusted_upper'] < -1e-12 and ci.loc['h90','adjusted_lower']>=-1e-12 and ci.loc['k90','adjusted_upper']<=1e-12)
            rows.append(dict(block=b,horizon_days=h,delta_brier=float(d.brier),delta_h90=float(d.h90),delta_k90=float(d.k90),
                relative_k90=float(d.k90/g.k90) if g.k90 else np.nan,quality_point_gain=point,quality_supported=gain,
                equivalent_supported=bool(equivalent),status='QUALITY_GAIN_SUPPORTED' if gain else 'EQUIVALENCE_SUPPORTED' if equivalent else 'NOT_RESOLVED_OR_TRADEOFF'))
    return pd.DataFrame(rows)
