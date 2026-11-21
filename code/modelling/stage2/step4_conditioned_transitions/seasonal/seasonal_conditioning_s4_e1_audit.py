"""Independent Counter/set and squared-error checks; no production estimator calls."""
from collections import Counter, defaultdict
from math import fsum
import numpy as np
import pandas as pd


def audit_prepared(bundle, matrices, support, cache, config):
    q,roles=bundle['qualified'],bundle['roles']
    cutoff=pd.Timestamp('2020-01-01',tz='UTC')
    start=pd.Timestamp('2012-01-01',tz='UTC');end=pd.Timestamp('2023-01-01',tz='UTC')
    val_ids={int(d) for d,t in q[['id','origin_time_UTC']].itertuples(index=False,name=None) if cutoff<=t<end}
    actual=dict(zip(roles[['id','origin_source_obs','horizon_days']].itertuples(index=False,name=None),roles.role))
    trained,held=[],[]
    for r in q.itertuples(index=False):
        if cutoff<=r.origin_time_UTC<end:
            expected='validation';held.append((r.id,r.origin_source_obs,r.horizon_days))
        elif not start<=r.origin_time_UTC<cutoff: expected='outside_training_window'
        elif r.required_interval_end_epoch>=cutoff.timestamp(): expected='excluded_label_cutoff'
        elif r.id in val_ids: expected='excluded_validation_id'
        else:
            expected='train';trained.append((r.id,r.origin_source_obs,r.horizon_days))
        assert actual[(r.id,r.origin_source_obs,r.horizon_days)]==expected
    assert sorted(val_ids)==bundle['validation_ids']
    assert set(trained)==set(bundle['train'][['id','origin_source_obs','horizon_days']].itertuples(index=False,name=None))
    assert set(held)==set(bundle['validation'][['id','origin_source_obs','horizon_days']].itertuples(index=False,name=None))
    count=Counter();ids=defaultdict(set)
    for r in bundle['train'].itertuples(index=False):
        for s in [-1,int(r.departure_season)]:
            count[(r.horizon_days,r.origin_cell_1,s,r.destination_cell_1)]+=1
            ids[(r.horizon_days,r.origin_cell_1,s)].add(r.id)
    rows=defaultdict(dict)
    for (h,i,s,j),n in count.items(): rows[(h,i,s)][j]=n
    statepos={int(j):k for k,j in enumerate(bundle['states'])}
    expected_matrices={};worst=0.
    for key,p in matrices.items():
        raw=rows.get(key,{})
        fallback=not raw and key[2]>=0 and bool(rows.get((*key[:2],-1)))
        use=rows.get((*key[:2],-1),{}) if fallback else raw
        sup=support.loc[(support.horizon_days==key[0])&(support.origin_cell_1==key[1])&(support.departure_season==key[2])].iloc[0]
        assert sup.pairs==sum(raw.values()) and sup.ids==len(ids.get(key,set()))
        assert bool(sup.annual_fallback)==fallback and bool(sup.supported)==bool(use)
        if not use:
            assert p is None;expected_matrices[key]=None;continue
        vector=np.zeros(len(statepos));total=sum(use.values())
        for j,n in use.items(): vector[statepos[j]]=n/total
        worst=max(worst,float(np.max(np.abs(vector-p))))
        assert worst<=1e-12
        expected_matrices[key]=vector
    reference={}
    queries=set(bundle['validation'][['horizon_days','origin_cell_1','departure_season']].itertuples(index=False,name=None))
    assert set(cache)=={(m,*key) for m in ['B2Annual','B2SeasonalC1'] for key in queries}
    for key,item in cache.items():
        model,h,i,s=key;p=expected_matrices[(h,i,-1 if model=='B2Annual' else s)]
        assert p is not None and np.max(np.abs(p-item['p']))<=1e-12
        sorted_positive=sorted((float(v) for v in p if v>0),reverse=True)
        cumulative=0.
        for cutoff_p in sorted_positive:
            cumulative+=cutoff_p
            if cumulative>=.9-1e-12:break
        region={int(j) for j,pj in zip(bundle['states'],p) if pj>0 and pj>=cutoff_p-1e-12}
        assert region==set(bundle['states'][item['mask']])
        assert item['k90']==len(region-{-2})
        assert abs(item['region_mass']-sum(p[statepos[j]] for j in region))<=1e-12
        reference[key]=(p,region)
    return reference,{'source_roles_independent':True,'counts_probabilities_regions_independent':True,
                      'max_probability_error':worst,'forecast_keys_checked':len(cache)}


def audit_scored(bundle, reference, cases, idmeans, summary, multipliers, draws, intervals, flags, config):
    v=bundle['validation'];states=bundle['states'];pos={int(j):k for k,j in enumerate(states)}
    keys=['id','origin_source_obs','horizon_days']
    columns=keys+['origin_cell_1','departure_season','destination_cell_1']
    expected=v[columns].sort_values(keys).reset_index(drop=True)
    assert set(cases.model)=={'B2Annual','B2SeasonalC1'}
    for name,g in cases.groupby('model'):
        pd.testing.assert_frame_equal(expected,g[columns].sort_values(keys).reset_index(drop=True),check_exact=True)
    n=Counter((int(h),int(i),int(d)) for h,i,d in v[['horizon_days','origin_cell_1','id']].itertuples(index=False,name=None))
    ids=defaultdict(set);cells=defaultdict(set)
    for h,i,d in n:ids[(h,i)].add(d);cells[h].add(i)
    max_error=0.;direct_terms=defaultdict(list);id_terms=defaultdict(list)
    for key,g in cases.groupby(['model','horizon_days','origin_cell_1','departure_season']):
        p,region=reference[key];model,h,i,s=key
        for j,part in g.groupby('destination_cell_1'):
            difference=p.copy();difference[pos[j]]-=1
            bs=float(np.dot(difference,difference));hit=float(j in region);size=float(len(region-{-2}))
            for m,value in [('brier',bs),('h90',hit),('k90',size)]:
                max_error=max(max_error,float(np.abs(part[m]-value).max()))
            for r in part.itertuples(index=False):
                w=1/(len(cells[h])*len(ids[(h,i)])*n[(h,i,r.id)])
                assert abs(w-r.weight)<=1e-12
                sk=(model,h);dk=(model,h,i,r.id)
                direct_terms[sk].append((w*bs,w*hit,w*size))
                id_terms[dk].append((bs/n[(h,i,r.id)],hit/n[(h,i,r.id)],size/n[(h,i,r.id)]))
    assert max_error<=1e-12
    direct={k:np.array([fsum(column) for column in zip(*terms)]) for k,terms in direct_terms.items()}
    direct_idmeans={k:np.array([fsum(column) for column in zip(*terms)]) for k,terms in id_terms.items()}
    for r in summary.itertuples(index=False):
        assert np.max(np.abs(direct[(r.model,r.horizon_days)]-[r.brier,r.h90,r.k90]))<=1e-12
    for r in idmeans.itertuples(index=False):
        assert np.max(np.abs(direct_idmeans[(r.model,r.horizon_days,r.origin_cell_1,r.id)]-[r.brier,r.h90,r.k90]))<=1e-12
    for h in [7,30]:
        g=cases.loc[(cases.horizon_days==h)&(cases.model=='B2SeasonalC1')]
        fallback=g.loc[g.annual_fallback]
        assert len(fallback)==(41 if h==7 else 0)
        assert abs(fallback.weight.sum()-(1/36 if h==7 else 0))<=1e-12
        if len(fallback):
            annual=cases.loc[cases.model=='B2Annual'].set_index(['id','origin_source_obs','horizon_days'])
            for r in fallback.itertuples(index=False):
                a=annual.loc[(r.id,r.origin_source_obs,r.horizon_days)]
                assert abs(r.brier-a.brier)<=1e-12 and r.h90==a.h90 and r.k90==a.k90
    ids_union=sorted(bundle['validation_ids']);di={d:k for k,d in enumerate(ids_union)}
    rng=np.random.Generator(np.random.PCG64(20261102))
    assert np.array_equal(multipliers,rng.exponential(1.,(10000,len(ids_union))))
    independently=np.zeros_like(draws)
    for hi,h in enumerate([7,30]):
        for i in sorted(cells[h]):
            group=sorted(ids[(h,i)])
            delta=np.array([direct_idmeans[('B2SeasonalC1',h,i,d)]-direct_idmeans[('B2Annual',h,i,d)] for d in group])
            weights=multipliers[:,[di[d] for d in group]]
            weights=weights/np.sum(weights,axis=1,keepdims=True)
            independently[:,hi]+=np.einsum('rd,dm->rm',weights,delta,optimize=False)/len(cells[h])
    # Direct scalar accumulation above has a documented roundoff accumulation bound.
    uncertainty_error=float(np.max(np.abs(independently-draws)))
    assert uncertainty_error<=1e-12,uncertainty_error
    for hi,h in enumerate([7,30]):
        for mi,m in enumerate(['brier','h90','k90']):
            r=intervals.loc[(intervals.horizon_days==h)&(intervals.metric==m)].iloc[0]
            bounds=np.quantile(independently[:,hi,mi],[.025,.975,.05/6,1-.05/6],method='linear')
            assert np.max(np.abs(bounds-r[['lower95','upper95','adjusted_lower','adjusted_upper']].to_numpy(dtype=float)))<=1e-12
        r=flags.loc[flags.horizon_days==h].iloc[0]
        d=direct[('B2SeasonalC1',h)]-direct[('B2Annual',h)]
        assert np.max(np.abs(d-r[['delta_brier','delta_h90','delta_k90']].to_numpy(dtype=float)))<=1e-12
        changed=summary.loc[(summary.horizon_days==h)&(summary.model=='B2SeasonalC1'),'season_changed'].iloc[0]>0
        b=bool(d[0]<-1e-12 and changed);q=bool(b and d[1]>=-1e-12 and d[2]<=1e-12)
        ci=intervals.loc[intervals.horizon_days==h].set_index('metric')
        bs=bool(b and ci.loc['brier','adjusted_upper']<-1e-12)
        qs=bool(q and bs and ci.loc['h90','adjusted_lower']>=-1e-12 and ci.loc['k90','adjusted_upper']<=1e-12)
        assert [r.BRIER_POINT_GAIN,r.QUALITY_POINT_GAIN,r.BRIER_GAIN_SUPPORTED_CONDITIONALLY,r.QUALITY_GAIN_SUPPORTED_CONDITIONALLY]==[b,q,bs,qs]
        expected_status=('QUALITY_GAIN_SUPPORTED_CONDITIONALLY' if qs else 'QUALITY_NOT_ESTABLISHED' if q else 'BRIER_GAIN_WITH_QUALITY_TRADEOFF' if b else 'NO_BRIER_POINT_GAIN')
        assert r.status==expected_status
    return {'independent_scores_weights_fallback':True,'paired_uncertainty_and_flags':True,
            'maximum_case_score_error':max_error,'maximum_draw_error':uncertainty_error,
            'final_test_access':False}
