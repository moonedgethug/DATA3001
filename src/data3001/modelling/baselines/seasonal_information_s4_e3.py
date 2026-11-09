"""Training-only choice of a seasonal mixture and source-keyed forecast scoring."""
import numpy as np
import pandas as pd
from data3001.modelling.baselines.seasonal_conditioning_s4_e1 import fit
from data3001.modelling.baselines.seasonal_conditioning_s4_e1_inputs import KEY, FEATURES, validation_weights
from data3001.modelling.common.prediction_regions import probability_region

ROW = ['horizon_days','origin_cell_1','departure_season']
MODELS = ('Annual','HardSeason','Adjusted')


def fit_role(role, bundle):
    cfg = dict(horizons=[7,30],train_start='2001-01-01',cutoff=role['cutoff'])
    matrix,support = fit(role['train'],bundle['origins'],bundle['states'],cfg,role['validation'].id.unique())
    # Independent aggregation by destination before comparing every fitted row.
    pieces = [role['train'][ROW+['destination_cell_1']],role['train'][ROW+['destination_cell_1']].assign(departure_season=-1)]
    counts = pd.concat(pieces).groupby(ROW+['destination_cell_1']).size()
    states = bundle['states']
    observed_rows = set(counts.index.droplevel(-1))
    for (h,i,s),p in matrix.items():
        row = (h,i,s)
        if row not in observed_rows:
            row = (h,i,-1)
        if row not in observed_rows:
            assert p is None
            continue
        raw = counts.loc[row].reindex(states,fill_value=0).to_numpy()
        assert np.array_equal(raw/raw.sum(),p)
    return matrix,support


def mix(annual, seasonal, c):
    if c == 0: return annual.copy()
    if c == 1: return seasonal.copy()
    return (1-c)*annual + c*seasonal


def choose_weight(U,V):
    if U <= 0: return 0.
    c = float(np.clip(V/U,0,1))
    return c if 2*c*V-c*c*U > 1e-12 else 0.


def select_weights(folds, states):
    ix = {j:k for k,j in enumerate(states)}
    parts = []
    for name,matrix,v in folds:
        for key,g in v.groupby(ROW):
            h,i,s = key
            a = matrix[h,i,-1]
            z = g[FEATURES+['destination_cell_1']].copy()
            z['fold'] = name
            z['supported'] = a is not None
            z[['u','v','annual_loss']] = np.nan
            if a is not None:
                q = matrix[key] - a
                y = g.destination_cell_1.map(ix).to_numpy()
                z['u'] = q@q
                z['v'] = q[y] - a@q
                z['annual_loss'] = 1+a@a-2*a[y]
            parts.append(z)
    allcases = pd.concat(parts,ignore_index=True)
    assert not allcases.duplicated(KEY).any()
    z = validation_weights(allcases[allcases.supported])
    allcases['weight'] = z.weight.reindex(allcases.index).fillna(0)
    selections = []
    curves = []
    for h,g in z.groupby('horizon_days'):
        U,V,L0 = g.weight.to_numpy()@g[['u','v','annual_loss']].to_numpy()
        c = choose_weight(U,V)
        selections.append(dict(horizon_days=h,c=c,U=U,V=V,annual_loss=L0,hard_loss=L0-2*V+U,
                               minimum_loss=L0-2*c*V+c*c*U))
        grid = np.unique(np.r_[np.linspace(0,1,101),c])
        pooled = np.zeros(len(grid))
        for name,matrix,_ in folds:
            fold = g[g.fold==name]
            totals = np.zeros(len(grid))
            for key,group in fold.groupby(ROW):
                _,i,_ = key
                a = matrix[h,i,-1]
                s = matrix[key]
                positions = group.destination_cell_1.map(ix).to_numpy()
                frequencies = np.bincount(positions,weights=group.weight,minlength=len(a))
                predictions = (1-grid[:,None])*a + grid[:,None]*s
                totals += group.weight.sum()*(1+np.square(predictions).sum(axis=1))-2*(predictions@frequencies)
            pooled += totals
            curves.extend((h,name,w,loss/fold.weight.sum()) for w,loss in zip(grid,totals))
        analytic = L0-2*grid*V+grid*grid*U
        assert np.allclose(pooled,analytic,atol=1e-12,rtol=0)
        assert pooled[grid==c][0] <= pooled.min()+1e-12
        curves.extend((h,'pooled',w,loss) for w,loss in zip(grid,pooled))
    return pd.DataFrame(selections),pd.DataFrame(curves,columns=['horizon_days','fold','c','brier']),allcases


def make_forecasts(matrix, support, weights, states):
    c = weights.set_index('horizon_days').c.to_dict()
    rows = []
    cache = {}
    for row in support[support.departure_season.ge(0)].itertuples(index=False):
        key = (row.horizon_days,row.origin_cell_1,row.departure_season)
        annual = matrix[key[0],key[1],-1]
        if annual is None: continue
        seasonal = matrix[key]
        for model,p in zip(MODELS,(annual,seasonal,mix(annual,seasonal,c[key[0]]))):
            mask,region = probability_region(p,states)
            cache[model,*key] = (p,mask,region)
            rows.append((model,*key,region['region90_cells'],region['region90_mass'],row.annual_fallback))
    return cache,pd.DataFrame(rows,columns=['model',*ROW,'k90','region_mass','fallback'])


def score_cases(roster, targets, cache, matched, states):
    ix = {j:k for k,j in enumerate(states)}
    cases = roster.merge(targets[KEY+['destination_cell_1']],on=KEY,validate='one_to_one')
    assert len(cases)==len(roster)
    parts = []
    rep_scores = {}
    for key,group in cases.groupby(ROW):
        g = group.copy()
        if not g.supported.all():
            assert not g.supported.any()
            continue
        y = g.destination_cell_1.map(ix).to_numpy()
        h,i,s = key
        for model in MODELS:
            p,mask,region = cache[model,*key]
            bs = 1+p@p-2*p[y]
            # Explicit squared errors and independent tie-inclusive region.
            js,inv = np.unique(y,return_inverse=True)
            residual = np.tile(p,(len(js),1))
            residual[np.arange(len(js)),js] -= 1
            assert np.allclose(bs,np.square(residual).sum(axis=1)[inv],atol=1e-12,rtol=0)
            desc = sorted(p[p>0],reverse=True)
            threshold = desc[np.searchsorted(np.cumsum(desc),.9-1e-12)]
            manual = (p>0)&(p>=threshold-1e-12)
            assert np.array_equal(manual,mask) and np.count_nonzero(manual&(states>=0))==region['region90_cells']
            for metric,value in dict(brier=bs,h90=mask[y].astype(float),k90=region['region90_cells'],
                                     region_mass=region['region90_mass'],zero=(p[y]==0).astype(float),
                                     destinations=np.count_nonzero(p[states>=0]),exit=p[ix[-2]]).items():
                g[model+'_'+metric]=value
        g['lost_truth']=(g.HardSeason_zero>g.Annual_zero).astype(float)
        g['observed_exit']=(g.destination_cell_1==-2).astype(float)
        active,counts,other_share = matched[key]
        probability = counts/counts.sum(axis=1)[:,None]
        pos = pd.Index(active).get_indexer(g.destination_cell_1)
        # The zero column represents any truth absent from the annual donor support.
        issued = np.column_stack((probability,np.zeros(len(counts))))
        hitprob = issued[:,pos]
        losses = 1+np.square(probability).sum(axis=1)[:,None]-2*hitprob
        # Recompute draw losses with one-hot errors for every distinct observed outcome.
        for j in np.unique(pos):
            checks = probability.copy()
            if j>=0: checks[:,j]-=1
            direct = np.square(checks).sum(axis=1)+(j<0)
            assert np.allclose(losses[:,np.flatnonzero(pos==j)[0]],direct,atol=1e-12,rtol=0)
        g['Matched_brier'] = losses.mean(axis=0)
        g['Matched_zero'] = (hitprob==0).mean(axis=0)
        g['Matched_destinations'] = np.count_nonzero(counts[:,active>=0],axis=1).mean()
        g['other_share'] = other_share
        g['informative'] = other_share>=.25
        rep_scores[key] = losses@g.weight.to_numpy()
        parts.append(g)
    return pd.concat(parts,ignore_index=True),rep_scores
