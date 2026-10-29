"""Contract-preserving fixed-state qualification and matched development comparisons."""
import numpy as np
import pandas as pd
from data3001.modelling.baselines.cv import KEYS
from data3001.preprocessing import prep_core as core

SCENARIOS = ('drogued', 'undrogued')


def qualify_intervals(arrays, origins, ends):
    """Reuse source-aware interval rules, never infer state from velocity."""
    events = core.event_bounds(arrays)
    result = []
    for scenario in SCENARIOS:
        unknown, mismatch = core._regime(arrays, origins, ends, scenario, events)
        result.append(~unknown & ~mismatch)
    if (result[0] & result[1]).any():
        raise ValueError('Fixed regimes overlap.')
    return tuple(result)


def matched_pooled_scores(pooled, fixed_counts):
    """Keep frozen OOF forecasts; change only multiplicities on a subset population."""
    if fixed_counts.duplicated(KEYS).any() or (fixed_counts.pair_count <= 0).any():
        raise ValueError('Invalid fixed case multiplicities.')
    key = ['model', *KEYS]
    if pooled.duplicated(key).any() or (pooled.pair_count <= 0).any():
        raise ValueError('Ambiguous pooled score groups.')
    rows = []
    for name, g in pooled.groupby('model'):
        matched = fixed_counts.merge(g, on=KEYS, how='left', validate='one_to_one',
                                     suffixes=('_fixed', ''), indicator=True)
        if (not matched['_merge'].eq('both').all()
                or (matched.pair_count_fixed > matched.pair_count).any()):
            raise ValueError('Fixed cases are not a subset of each pooled model population.')
        matched['pair_count'] = matched.pop('pair_count_fixed')
        rows.append(matched.drop(columns='_merge')[pooled.columns])
    if not rows:
        raise ValueError('No pooled predictions.')
    return pd.concat(rows, ignore_index=True)


def paired_regime_intervals(fixed, pooled, replicates=200, seed=20261004):
    """Fixed minus pooled on identical cases; ID bootstrap conditional on frozen fits."""
    key=['outer_fold', *KEYS, 'model']
    a=fixed.sort_values(key).reset_index(drop=True)
    b=pooled.sort_values(key).reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(a[key+['pair_count']], b[key+['pair_count']], check_dtype=False)
    except AssertionError as error:
        raise ValueError('Paired comparisons require identical folds/cases/counts.') from error
    if a.duplicated(key).any():
        raise ValueError('Duplicate paired cases.')
    if a.groupby('id').outer_fold.nunique().gt(1).any():
        raise ValueError('An ID appears in more than one outer fold.')
    a['difference']=(a.brier_failure_penalized-b.brier_failure_penalized)*a.pair_count
    totals=a.groupby(['horizon_days','model','outer_fold','id'],as_index=False).agg(
        difference=('difference','sum'), pairs=('pair_count','sum'))
    rows=[]
    for (h,model),g in totals.groupby(['horizon_days','model']):
        g=g.reset_index(drop=True)
        units=[np.flatnonzero(g.outer_fold.eq(f)) for f in sorted(g.outer_fold.unique())]
        rng=np.random.default_rng(seed+int(h))
        d,w=g.difference.to_numpy(),g.pairs.to_numpy()
        values=[]
        for _ in range(replicates):
            ix=np.concatenate([rng.choice(ix,len(ix),replace=True) for ix in units])
            values.append(d[ix].sum()/w[ix].sum())
        lower,upper=np.quantile(values,[.025,.975])
        rows.append(dict(horizon_days=int(h),model=model,delta_brier=d.sum()/w.sum(),
                         lower=lower,upper=upper,replicates=replicates,independent_ids=len(g),
                         eligible_pairs=int(w.sum()),scope='Fixed minus matched pooled; paired whole-ID within outer folds; conditional on saved fits, no refitting/selection/numerical uncertainty'))
    return pd.DataFrame(rows)


def preflight(pairs,outer,inner):
    if not set(pairs.id).issubset(outer):
        raise ValueError('Unassigned ID.')
    rows=[]
    for fold in sorted(set(outer.values())):
        heldout={sid for sid,f in outer.items() if f==fold}
        fitting=set(outer)-heldout
        if set(inner[fold])!=fitting:
            raise ValueError('Inner membership differs from the frozen outer split.')
        splits=[('outer_fit',fitting),('outer_validation',heldout)]
        for k in sorted(set(inner[fold].values())):
            tuning={sid for sid,f in inner[fold].items() if f==k}
            splits += [(f'inner{k}_fit',fitting-tuning),(f'inner{k}_tuning',tuning)]
        for role,ids in splits:
            for h in (7,30):
                g=pairs.loc[pairs.id.isin(ids)&pairs.horizon_days.eq(h)]
                rows.append(dict(outer_fold=fold,role=role,horizon_days=h,
                                 eligible_pairs=len(g),independent_ids=g.id.nunique(),
                                 origin_cells=g.origin_cell_1.nunique(),evaluable=len(g)>0))
    out=pd.DataFrame(rows)
    if not out.evaluable.all():
        raise ValueError('Not evaluable: empty required fitting/tuning/validation population. '+out.loc[~out.evaluable].to_json(orient='records'))
    return out
