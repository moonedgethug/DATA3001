"""Readable same-case results; fixed-fit ID uncertainty is separate from MC."""
import numpy as np
import pandas as pd
from data3001.modelling.markov_position_scores import summarize_scores
from data3001.modelling.run_blend_cv import save_json,save_frame

COMPARISONS=[('neighbour-CV','self-CV'),('neighbour-CV','self-at-neighbour')]


def heterogeneity(frame):
    keys=['horizon_days','outer_fold','id','origin_source_obs','origin_cell_1']
    mean=frame.groupby(keys+['model'],as_index=False).S_integration.mean()
    p=mean.pivot(index=keys,columns='model',values='S_integration')
    if p[['self-CV','neighbour-CV']].isna().any().any():raise ValueError('Heterogeneity cases differ')
    p['difference']=p['neighbour-CV']-p['self-CV'];p=p.reset_index()
    out=[]
    for group in [['horizon_days','origin_cell_1'],['horizon_days','outer_fold','id']]:
        t=p.groupby(group,as_index=False).agg(pairs=('difference','size'),difference_sum=('difference','sum'),independent_IDs=('id','nunique'))
        t['delta_S']=t.difference_sum/t.pairs;out.append(t)
    return tuple(out)


def intervals(frame,replicates=200):
    rows=[]
    for h,part in frame.groupby('horizon_days'):
        mean=part.groupby(['outer_fold','id','model'],as_index=False)[['pairs','S_integration_sum']].mean()
        loss=mean.pivot(index=['outer_fold','id'],columns='model',values='S_integration_sum')
        n=mean.pivot(index=['outer_fold','id'],columns='model',values='pairs')
        if loss.isna().any().any() or not n.eq(n.iloc[:,0],axis=0).all().all():raise ValueError('Comparison case counts differ')
        group=[np.flatnonzero(loss.index.get_level_values(0)==f) for f in sorted(set(loss.index.get_level_values(0)))]
        rng=np.random.default_rng(20261028+int(h));draws=[np.concatenate([rng.choice(g,len(g),replace=True) for g in group]) for _ in range(replicates)]
        for a,b in COMPARISONS:
            d=(loss[a]-loss[b]).to_numpy();nn=n[a].to_numpy();samples=[d[ix].sum()/nn[ix].sum() for ix in draws]
            lo,hi=np.quantile(samples,[.025,.975]);rows.append({'horizon_days':int(h),'comparison':a+' minus '+b,
                'delta_S':float(d.sum()/nn.sum()),'lower_95':float(lo),'upper_95':float(hi),
                'scope':'paired whole-ID resampling within fixed outer folds; fixed fitted procedures; adaptive development; MC separate'})
    return pd.DataFrame(rows)


def mdtable(frame):
    cols=list(frame.columns);lines=['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']
    for row in frame.itertuples(index=False,name=None):
        lines.append('| '+' | '.join(f'{v:.8g}' if isinstance(v,(float,np.floating)) else str(v) for v in row)+' |')
    return '\n'.join(lines)


def report(paths,run,c,idframe,choices,mc):
    raw=summarize_scores(idframe);summary=raw.groupby(['horizon_days','model'],as_index=False).mean(numeric_only=True).drop(columns='repeat')
    ci=intervals(idframe,c['bootstrap_replicates'])
    save_frame(paths,run['results']/'summary.csv',summary);save_frame(paths,run['results']/'paired_ID_intervals.csv',ci)
    save_frame(paths,run['results']/'outer_MC_summary.csv',mc);save_json(paths,run['results']/'selected_parameters.json',choices)
    selection=pd.DataFrame(choices)[['outer_fold','horizon_days','family','path','alpha','lambda_value','S','MC_SE','numerically_unresolved']]
    cells=[];IDs=[];causes=[];support=[]
    for fold in range(5):
        root=run['results']/'checkpoints'/f'outer_{fold}'
        small=pd.read_parquet(root/'scores.parquet',columns=['horizon_days','outer_fold','id','origin_source_obs','origin_cell_1','model','repeat','S_integration'])
        a,b=heterogeneity(small);cells.append(a);IDs.append(b)
        for h in [7,30]:
            causes.append(pd.read_csv(root/f'H{h}_step_causes.csv').assign(outer_fold=fold))
            support.append(pd.read_csv(root/f'H{h}_fitting_support.csv'))
    cells=pd.concat(cells).groupby(['horizon_days','origin_cell_1'],as_index=False)[['pairs','difference_sum','independent_IDs']].sum()
    cells['delta_S']=cells.difference_sum/cells.pairs;IDs=pd.concat(IDs,ignore_index=True)
    save_frame(paths,run['results']/'cell_differences.csv',cells);save_frame(paths,run['results']/'ID_differences.csv',IDs)
    save_frame(paths,run['results']/'fitting_donor_support.csv',pd.concat(support,ignore_index=True))
    cause_rows=[]
    for (h,model,rep),g in pd.concat(causes).groupby(['horizon_days','model','repeat']):
        denominator=g.groupby('outer_fold').particles.max().sum()
        last=g.sort_values('day').groupby('outer_fold').tail(1)
        counts={k:int(g[k].sum()) for k in ['unsupported_cell','endpoint_geometry_U','source_exit','translated_exit']}
        if int(last.U_particles.sum())!=counts['unsupported_cell']+counts['endpoint_geometry_U']:raise ValueError('U causes do not reconcile')
        if int(last.E_particles.sum())!=counts['source_exit']+counts['translated_exit']:raise ValueError('E causes do not reconcile')
        cause_rows.append({'horizon_days':int(h),'model':model,'repeat':int(rep),'origin_particles':int(denominator),
                           **{k+'_pct':100*v/denominator for k,v in counts.items()}})
    causes=pd.DataFrame(cause_rows);save_frame(paths,run['results']/'failure_causes.csv',causes)
    hrows=[]
    for h,g in cells.groupby('horizon_days'):
        q=IDs.loc[IDs.horizon_days.eq(h)]
        hrows.append({'horizon_days':int(h),'improved_cells':int(g.delta_S.lt(0).sum()),'evaluated_cells':len(g),
                      'improved_IDs':int(q.delta_S.lt(0).sum()),'evaluated_IDs':len(q)})
    hetero=pd.DataFrame(hrows)
    primary=summary[['horizon_days','model','eligible_pairs','independent_ids','S_integration','U_mass','E_mass','region90_hit','region90_cells','region90_available']]
    text='''# Displacement-neighbour Markov comparison — 7 and 30 days

## Question and bottom-line interpretation

Does borrowing equal-weight short-transition donor pairs from the eight adjacent cells improve predictions beyond a freshly tuned current-cell model? Seven and30days are optimised and assessed separately. A lower S is better; S is not percentage accuracy. Read the paired-ID intervals before describing a dependable improvement. This is adaptive development evidence: previous outer results informed the research direction. Final-test trajectories remain locked.

## What changed and what stayed fixed

The inputs remain exact longitude/latitude and the existing velocity category derived from ve/vn. No wind, temperature, season or additional feature is introduced. Each donor provides a WGS84 displacement and endpoint velocity; its displacement is applied at the particle's current exact location. We do not copy the donor's absolute endpoint. Donors are uniform eligible pairs within the local or eight-cell union, not equal-weight cells or IDs.

K(d,a,l)=(1-a)[(1-l)L_self+l B_self]+a[(1-l)L_neighbour+l B_neighbour]. Here a chooses spatial borrowing and l pools velocity categories. Conditional-neighbour fallback is decided after forming the full eight-cell union. A selected empty local/neighbor pool yields U without reallocating that mass. Source-E and translated observed-hour first-exit checks remain unchanged; E/U absorb. Synthetic invalid/land endpoints are U, not a validated grounding prediction.

## Fair tuning and evaluation

Each outer fold uses four inner whole-ID folds to select the path, a and l. The no-neighbour procedure independently selects from a=0. Both grids contain0,0.1,...,1. All968 seven-day and1089 thirty-day candidates enter initial inner CV on all eligible cases. Paths are a predeclared bounded family, not every ordered composition. Historical selected settings are not tuning inputs. Fit-role velocity thresholds and donor pools exclude the entire held ID throughout D.

The primary comparison is neighbour-CV versus self-CV, each tuned independently. The self-at-neighbour control removes borrowing while retaining the neighbour procedure's selected path/lambda, showing the effect of borrowing at matched settings. No model is selected using outer scores.

## Primary held-ID results

'''+mdtable(primary)+'''

U/E columns are probability fractions. region90_hit is an empirical fraction, not universal forecast accuracy; region90_cells is geographic cell count. A larger region can raise hits without sharper predictions. Finite-particle regions and sampled zeroes do not establish limiting-law calibration or structural zero probabilities.

## Paired whole-ID uncertainty

'''+mdtable(ci)+'''

Negative differences favour the first model. Intervals use200 paired whole-ID resamples within outer folds and condition on saved fits/selection. They do not include training-refit, research-adaptation or complete selection uncertainty. A crossing-zero interval does not establish equivalence or reliable improvement. Separate numerical Monte Carlo uncertainty follows.

'''+mdtable(mc)+'''

## Selected settings in each outer training pool

'''+mdtable(selection)+'''

These are fold-specific choices, not one universal lambda/alpha or an independently evaluated all-development deployment refit. An unresolved numerical ranking must not be called a unique optimum.

## Where differences occur and why forecasts fail

'''+mdtable(hetero)+'''

These counts describe directional score changes, not accuracy percentages. Per-cell and per-ID signed differences retain both improvements and worsenings; they are not filtered to show favourable examples. See cell_differences.csv, ID_differences.csv and fitting_donor_support.csv for eligible-pair and independent-donor support.

'''+mdtable(causes)+'''

Unsupported-cell and synthetic-endpoint geometry contributions reconcile exactly to terminal U. Source exits and translated-path exits reconcile to E. These are first absorbing-event causes across the complete path; repeated velocity backoff events are a different diagnostic. Geometry failures are not evidence of observed grounding. Donor support is fitting-only and does not create new independent drifters when one ID supplies many hourly pairs.

## Numerical computation and its limitations

Inner CV uses deterministic-mixture importance integration with at least two independent trajectories per proposal component. The initial numerical proposal lattice has7x7 components at0,.1,.3,.5,.7,.9,1 while ALL11x11 target parameters are scored. The smaller proposal lattice changes computation, not candidate coverage or the model. Every target label law has positive proposal support; exhaustive count-table checks over1..30substeps bound its ratio by92.173873823. This bound alone does not prove a variance improvement. Intended spatial/velocity labels, including dummy labels after E/U or fallback, determine the exact joint likelihood ratio. Irregular refinement grids use the joint mixture denominator. Fresh independent draws are used whenever proposal sets change. A within-component variance correction gives an unbiased estimate of the same S; negative estimates can occur and are not clipped. These integration terms are not issued probability distributions and are never normalised into maps.

A fitting-only dummy-outcome pilot selects centred versus uncentred numerical algebra by repeated integration variance, never favourable model scores. Local compiled arithmetic is independently checked against the NumPy reference; C++ source and compiled-library hashes are bound. Conservative SE sums are estimated contrast uncertainties, not certified error bounds. The full original grid is rescreened after refinement. At the declared maximum precision unresolved choices use fewer steps, smaller a, larger l, then path ID, and remain flagged.

Outer predictions use ordinary target-law iid particles (128 per repeat, two independent repeats), preserving normalized issued mass. Numerical MC intervals condition on fixed queries/fits and do not replace ID uncertainty. Two repeats can miss rare numerical events; ties and empirical zero variance must not prove a resolved winner.

## Audit and reproducibility

All eligible origins retain original equal weight. No difficult ID, unseen outcome, E/U or incomplete forecast is deleted to improve scores. Saved inner tables/ID totals, source-key case digests, fit/held rosters, selected recipes, outer predictions/step causes, hashes and environment support reproduction. Canonical features and trajectories are unchanged. No final-test file is opened. See verification.json and the separate independent saved-artifact audit.

The result concerns annual-pooled7/30-day stopped distributions for drifter-like transport. It does not validate seasonal/year forecasts, arbitrary objects, continuous-feature response functions or grounding. Neighbourhood geometry alone does not prove physical connectivity across current fronts/coasts. Wider support is not automatically a better forecast.
'''
    paths.publish(run['results']/'REPORT.md',lambda stream:stream.write(text.encode()))
    return summary,ci
