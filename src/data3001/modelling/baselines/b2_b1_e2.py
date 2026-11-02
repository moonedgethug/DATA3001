"""Approved E2 allocation, independent weight control and constrained selection."""
import numpy as np
import pandas as pd

from data3001.modelling.baselines.adaptive_b2_b1 import fit_bases, evaluate, summarize_scores
from data3001.modelling.baselines.empirical_b2 import checked_ids
from data3001.modelling.common.qualified_count_inputs import HORIZONS, EXIT, KEYS
from data3001.modelling.common.prediction_regions import checked_distribution, probability_region

TOL = 1e-12
A_GRID = tuple(k/20 for k in range(21))
C_GRID = (.5, .75, 1., 1.5, 2.)
BETA_GRID = (0., .25, .5, .75, 1.)
MODELS = ('B2', 'Fixed', 'E1Adaptive', 'Info', 'Weight')
METRICS = ('brier', 'region90_cells', 'region90_hit')
PARAMS = ('model', 'parameter_a', 'parameter_c', 'parameter_beta')


def allocation_reference(p, q, states, c):
    if not np.isfinite(c) or c <= 0:
        raise ValueError('Allocation factor must be positive')
    checked_distribution(p, states); checked_distribution(q, states)
    d = np.asarray(states) >= 0
    weights = np.where(p[d] > 0, 1., c)
    mass, normalizer = float(q[d].sum()), float(np.dot(q[d], weights))
    out = q.copy()
    if mass > 0 and c != 1:
        out[d] = mass*q[d]*weights/normalizer
    checked_distribution(out, states)
    return out, normalizer


def weight(a, beta, n, median):
    if not np.isfinite([a, beta, n, median]).all() or not 0 <= a <= 1 or not 0 <= beta <= 1 or min(n, median) <= 0:
        raise ValueError('Invalid supported-row weight parameters')
    if a in (0., 1.) or beta == 0:
        return float(a)
    if beta == 1:
        return float(median*a/((1-a)*n+median*a))
    return float(a/(a+(1-a)*(n/median)**beta))


def specifications():
    rows = []
    for a in A_GRID:
        rows.extend(('Info', a, c, 0.) for c in C_GRID)
        rows.extend(('Weight', a, 1., b) for b in BETA_GRID)
    return pd.DataFrame(rows, columns=PARAMS)


def candidate_metrics(base, counts, evaluation_ids):
    """Vectorized complete-grid evaluation; support is exclusively fitting-derived."""
    ids = checked_ids(evaluation_ids)
    if set(ids) & set(base.b2.training_ids):
        raise ValueError('Evaluation IDs overlap fitting IDs')
    part = counts[counts.id.isin(ids)]
    support = base.b2.support.set_index(['horizon_days', 'origin_cell_1'])
    spec = specifications()
    result = []
    for h in HORIZONS:
        sums = np.zeros((len(spec), 3)); evaluable = 0
        section = part[part.horizon_days.eq(h)]
        active = (base.references[h] > 0) | (base.states == EXIT)
        states = base.states[active]; local = {int(c): i for i, c in enumerate(states)}
        for origin, group in section.groupby('origin_cell_1'):
            if (h, origin) not in base.rows:
                continue
            p, q = base.rows[(h, origin)][active], base.references[h][active]
            n = support.loc[(h, origin), 'training_pair_count']
            refs = {c: allocation_reference(p, q, states, c)[0] for c in C_GRID}
            vectors = []
            for s in spec.itertuples(index=False):
                lam = s.parameter_a if s.model == 'Info' else weight(s.parameter_a, s.parameter_beta, n, base.medians[h])
                ref = refs[s.parameter_c] if s.model == 'Info' else q
                vectors.append((1-lam)*p+lam*ref)
            vectors = np.asarray(vectors)
            observed = np.zeros(len(states)); total = int(group.pair_count.sum())
            for dest, amount in group.groupby('destination_cell_1').pair_count.sum().items():
                if dest in local:
                    observed[local[dest]] = amount
            # Truth outside fitting reference support still contributes its full +1 Brier term.
            ordered = np.sort(vectors, axis=1)[:, ::-1]
            reached = np.cumsum(ordered, axis=1) >= .9-TOL
            if not reached.any(axis=1).all():
                raise AssertionError('Candidate row lost mass')
            cut = ordered[np.arange(len(spec)), reached.argmax(axis=1)]
            regions = (vectors > 0) & (vectors >= cut[:, None]-TOL)
            sums[:, 0] += total*(1+np.square(vectors).sum(axis=1))-2*np.sum(vectors*observed, axis=1)
            sums[:, 1] += total*np.sum(regions & (states >= 0), axis=1)
            sums[:, 2] += np.sum(regions*observed, axis=1)
            evaluable += total
        table = spec.copy()
        table['horizon_days'] = h
        table['eligible_pairs'] = int(section.pair_count.sum())
        table['evaluable_pairs'] = evaluable
        for j, name in enumerate(('score_sum', 'cell_sum', 'hit_sum')):
            table[name] = sums[:, j]
        fixed = table[table.model.eq('Info') & table.parameter_c.eq(1)].assign(model='Fixed')
        old = table[table.model.eq('Weight') & table.parameter_beta.eq(1)].assign(model='E1Adaptive')
        result.extend([table, fixed, old])
    return pd.concat(result, ignore_index=True)


def _tie_filter(table, column, ascending=True):
    best = table[column].min() if ascending else table[column].max()
    return table[np.abs(table[column]-best) <= TOL]


def select_parameters(candidates):
    columns = ['horizon_days', *PARAMS]
    pool = candidates.groupby(columns, as_index=False)[['score_sum','cell_sum','hit_sum','eligible_pairs','evaluable_pairs']].sum()
    if not pool.evaluable_pairs.gt(0).all():
        raise ValueError('No common supported validation population')
    for h, group in pool.groupby('horizon_days'):
        if group.evaluable_pairs.nunique() != 1 or group.eligible_pairs.nunique() != 1:
            raise ValueError('Candidates have different comparison populations')
    for field, numerator in zip(METRICS, ('score_sum','cell_sum','hit_sum')):
        pool[field] = pool[numerator]/pool.evaluable_pairs
    pool['quality_feasible'] = False; pool['strict_size_gain'] = False; pool['selected'] = False
    selections = []
    for h in HORIZONS:
        section = pool[pool.horizon_days.eq(h)]
        controls = {}
        for model in ('Fixed','E1Adaptive'):
            g = section[section.model.eq(model)]
            chosen = _tie_filter(g, 'brier').sort_values('parameter_a').iloc[0]
            controls[model] = chosen
            row = chosen.to_dict(); row['selection_status'] = 'brier_control'; row['selected'] = True
            selections.append(row); pool.loc[chosen.name, 'selected'] = True
        anchor = controls['Fixed']
        for model in ('Info','Weight'):
            g = section[section.model.eq(model)].copy()
            good = (g.brier <= anchor.brier+TOL) & (g.region90_hit >= anchor.region90_hit-TOL)
            smaller = g.region90_cells < anchor.region90_cells-TOL
            pool.loc[g.index, 'quality_feasible'] = good
            pool.loc[g.index, 'strict_size_gain'] = smaller
            for metric in METRICS:
                pool.loc[g.index, 'delta_'+metric] = g[metric]-anchor[metric]
            eligible = g[good & smaller].copy()
            if eligible.empty:
                neutral = g.parameter_c.eq(1) if model == 'Info' else g.parameter_beta.eq(0)
                chosen = g[neutral & g.parameter_a.eq(anchor.parameter_a)].iloc[0]
                status = 'fallback_fixed'
            else:
                for field, asc in [('region90_cells', True), ('brier', True), ('region90_hit', False)]:
                    eligible = _tie_filter(eligible, field, asc)
                eligible['departure'] = np.abs(np.log(eligible.parameter_c)) if model == 'Info' else eligible.parameter_beta
                eligible = _tie_filter(eligible, 'departure')
                for field in ('parameter_a', 'parameter_c' if model == 'Info' else 'parameter_beta'):
                    eligible = _tie_filter(eligible, field)
                chosen = g.loc[eligible.index[0]]; status = 'constrained_gain'
            row = chosen.to_dict(); row.update(selection_status=status, selected=True,
                                               quality_feasible=True, strict_size_gain=status=='constrained_gain')
            row.update(anchor_a=float(anchor.parameter_a), anchor_brier=float(anchor.brier),
                       anchor_hit=float(anchor.region90_hit), anchor_cells=float(anchor.region90_cells))
            selections.append(row); pool.loc[chosen.name, 'selected'] = True
    return pd.DataFrame(selections), pool


def forecasts(base, model, selected):
    if model not in MODELS:
        raise ValueError('Unknown E2 model')
    vectors, details = {}, []
    indexed = selected.set_index(['horizon_days','model']) if model != 'B2' else None
    for r in base.b2.support.itertuples(index=False):
        h, origin = r.horizon_days, r.origin_cell_1
        a, c, beta, status = 0., 1., 0., 'untuned_baseline'
        if model != 'B2':
            s = indexed.loc[(h, model)]
            a, c, beta, status = s.parameter_a, s.parameter_c, s.parameter_beta, s.selection_status
        row = r._asdict()
        row.update(model=model, parameter_a=a, parameter_c=c, parameter_beta=beta,
                   selection_status=status, median_pair_count=base.medians[h], borrowing_weight=np.nan,
                   reference_D_mass=np.nan, reference_normalizer=np.nan, reference_exit=np.nan,
                   modified_reference_exit=np.nan, reference_unseen_D_mass=np.nan,
                   modified_reference_unseen_D_mass=np.nan)
        if r.supported:
            p, q = base.rows[(h, origin)], base.references[h]
            lam = weight(a, beta, r.training_pair_count, base.medians[h]) if model in ('Weight','E1Adaptive') else a
            ref, normalizer = allocation_reference(p, q, base.states, c) if model == 'Info' else (q, float(q[base.states >= 0].sum()))
            vector = (1-lam)*p+lam*ref
            checked_distribution(vector, base.states); vectors[(h, origin)] = vector
            unseen = (base.states >= 0) & (p == 0)
            row.update(borrowing_weight=lam, reference_D_mass=float(q[base.states >= 0].sum()),
                       reference_normalizer=normalizer, reference_exit=float(q[base.index[EXIT]]),
                       modified_reference_exit=float(ref[base.index[EXIT]]),
                       reference_unseen_D_mass=float(q[unseen].sum()), modified_reference_unseen_D_mass=float(ref[unseen].sum()))
        details.append(row)
    return vectors, pd.DataFrame(details)


def diagnostic_scores(base, vectors, counts, ids, model):
    scores, boundaries = evaluate(base, vectors, counts, ids, model)
    for field in ('seen_D_probability','unseen_D_probability','true_seen_D','true_unseen_D','D_region_hit'):
        scores[field] = np.nan
    for (h, origin), indices in scores.groupby(['horizon_days','origin_cell_1']).groups.items():
        if (h, origin) not in vectors:
            continue
        p, b2 = vectors[(h, origin)], base.rows[(h, origin)]
        seen = (base.states >= 0) & (b2 > 0); unseen = (base.states >= 0) & (b2 == 0)
        truth = scores.loc[indices, 'destination_cell_1']
        scores.loc[indices, 'seen_D_probability'] = p[seen].sum()
        scores.loc[indices, 'unseen_D_probability'] = p[unseen].sum()
        scores.loc[indices, 'true_seen_D'] = truth.isin(base.states[seen]).astype(float)
        scores.loc[indices, 'true_unseen_D'] = truth.isin(base.states[unseen]).astype(float)
        scores.loc[indices, 'D_region_hit'] = scores.loc[indices, 'region90_hit'].where(truth.ne(EXIT))
    return scores, boundaries


def group_diagnostics(scores, weights):
    keys = ['role','model','horizon_days','origin_cell_1']
    s = scores.merge(weights[keys+['training_pair_count','training_id_count','largest_id_share','median_pair_count','borrowing_weight']], on=keys, validate='many_to_one')
    s['support_stratum'] = np.where(s.training_pair_count < s.median_pair_count, 'below_median', 'at_or_above_median')
    rows = []
    for grouping in [('horizon_days','model'), ('horizon_days','model','support_stratum')]:
        for key, g in s.groupby(list(grouping)):
            row = dict(zip(grouping, key)); row['scope'] = 'overall' if len(grouping)==2 else 'support_stratum'
            row.update(eligible_pairs=int(g.pair_count.sum()), eligible_ids=int(g.id.nunique()),
                       evaluable_pairs=int(g.loc[g.status.eq('evaluable'),'pair_count'].sum()))
            for field in (*METRICS,'seen_D_probability','unseen_D_probability','true_seen_D','true_unseen_D',
                          'predicted_exit_probability','D_region_hit','borrowing_weight'):
                valid = g[field].notna()
                row[field] = float(np.average(g.loc[valid,field],weights=g.loc[valid,'pair_count'])) if valid.any() else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def region_changes(base, models, scores):
    out = []
    for (h, origin), cases in scores[scores.model.eq('B2')].groupby(['horizon_days','origin_cell_1']):
        if (h, origin) not in models['B2']:
            continue
        observed = np.zeros(len(base.states))
        for dest, n in cases.groupby('destination_cell_1').pair_count.sum().items():
            observed[base.index[dest]] = n
        total = int(observed.sum()); regions = {m: probability_region(v[(h,origin)],base.states)[0] for m,v in models.items()}
        for model in ('Fixed','E1Adaptive','Info','Weight'):
            for reference in ('Fixed','B2'):
                if model == reference:
                    continue
                for label, mask in [('added',regions[model]&~regions[reference]),('removed',regions[reference]&~regions[model])]:
                    p = models[model][(h,origin)]
                    out.append(dict(horizon_days=h,origin_cell_1=origin,model=model,reference=reference,part=label,
                                    pair_count=total,cells=int(np.sum(mask&(base.states>=0))),
                                    hit_count=int(observed[mask].sum()), probability_mass=float(p[mask].sum()),
                                    exit_included=bool(mask[base.index[EXIT]])))
    return pd.DataFrame(out)


def classify(point, lower, upper, defined, required):
    b,k,h = [float(point[m]) for m in METRICS]
    passed = b <= TOL and h >= -TOL and k < -TOL
    supported = passed and defined == required and upper['brier'] <= TOL and lower['region90_hit'] >= -TOL and upper['region90_cells'] < -TOL
    if all(abs(float(point[m])) <= TOL for m in METRICS):
        return 'no_change', False, False
    return ('conditional_development_support' if supported else 'point_candidate_inconclusive' if passed else 'no_improvement_or_tradeoff'), passed, supported


def paired_bootstrap(scores, development_ids, replicates=5000, seed=20261030):
    ids = checked_ids(development_ids)
    if not scores.id.isin(ids).all() or replicates < 1:
        raise ValueError('Invalid bootstrap population')
    rng = np.random.default_rng(seed)
    multiplicity = rng.multinomial(len(ids), np.full(len(ids), 1/len(ids)), size=replicates)
    draws, aggregates = [], []
    for (h, model), g in scores.groupby(['horizon_days','model']):
        values = {}
        for metric in METRICS:
            good = g[metric].notna()
            raw = pd.DataFrame({'id':g.id,'den':g.pair_count.where(good,0),'num':g[metric].fillna(0)*g.pair_count})
            grouped = raw.groupby('id')[['num','den']].sum().reindex(ids,fill_value=0)
            aggregates.append(grouped.reset_index().assign(horizon_days=h,model=model,metric=metric))
            active = grouped.den.to_numpy() > 0
            sampled = multiplicity[:,active] @ grouped.to_numpy(float)[active]
            values[metric] = np.divide(sampled[:,0],sampled[:,1],out=np.full(replicates,np.nan),where=sampled[:,1]>0)
        draws.append(pd.DataFrame({'horizon_days':h,'model':model,'replicate':np.arange(replicates),**values}))
    draws = pd.concat(draws,ignore_index=True)
    intervals = []
    for (h,model), g in draws.groupby(['horizon_days','model']):
        for metric in METRICS:
            valid = g[metric].dropna()
            intervals.append(dict(horizon_days=h,model=model,metric=metric,lower_95=valid.quantile(.025),upper_95=valid.quantile(.975),
                                  defined_replicates=len(valid),undefined_replicates=replicates-len(valid)))
    points = summarize_scores(scores).set_index(['horizon_days','model'])
    differences, decisions = [], []
    for h in HORIZONS:
        wide = draws[draws.horizon_days.eq(h)].set_index(['replicate','model'])
        for model in ('Info','Weight'):
            point, lower, upper = {}, {}, {}
            defined = replicates
            for metric in METRICS:
                d = (wide.xs(model,level='model')[metric]-wide.xs('Fixed',level='model')[metric]).dropna()
                point[metric] = points.loc[(h,model),metric]-points.loc[(h,'Fixed'),metric]
                lower[metric],upper[metric] = d.quantile(.05/12),d.quantile(1-.05/12)
                defined = min(defined,len(d))
                differences.append(dict(horizon_days=h,model=model,reference='Fixed',metric=metric,difference=point[metric],
                                        lower_95=d.quantile(.025),upper_95=d.quantile(.975),adjusted_lower=lower[metric],adjusted_upper=upper[metric],
                                        defined_replicates=len(d),undefined_replicates=replicates-len(d)))
            outcome,passed,supported = classify(point,lower,upper,defined,replicates)
            decisions.append(dict(horizon_days=h,model=model,reference='Fixed',outcome=outcome,
                                  joint_point_pass=passed,conditional_support=supported,
                                  **{'delta_'+m:point[m] for m in METRICS}))
    return draws,pd.DataFrame(intervals),pd.DataFrame(differences),pd.DataFrame(decisions),pd.concat(aggregates,ignore_index=True)
