"""Human-readable exact-position comparison, with shared-scale cohort maps."""
import json
from html import escape
import numpy as np
import pandas as pd
from shapely import from_wkb
from shapely.geometry import box,shape
from data3001.modelling.markov_report import markdown_table,map_svg,_rings


def comparison_table(summary):
    rows=[]
    for (h,model),g in summary.groupby(['horizon_days','model']):
        rows.append({'horizon_days':int(h),'model':model,'eligible_pairs':int(g.eligible_pairs.iloc[0]),
            'independent_ids':int(g.independent_ids.iloc[0]),'S_estimate':g.S_integration.mean(),
            'S_issued':g.S_issued.mean(),'repeat_range':g.S_integration.max()-g.S_integration.min(),
            'U_mass_pct':100*g.U_mass.mean(),'E_mass_pct':100*g.E_mass.mean(),
            'issued90_hit_pct':100*g.region90_hit.mean(),'issued90_available_pct':100*g.region90_available.mean(),
            'issued90_cells':g.region90_cells.mean()})
    return pd.DataFrame(rows)


def report_text(table,intervals,particles=32):
    text='''# M1vcat exact-position displacement refinement

## Research question and fixed comparison

Does retaining within-cell longitude/latitude during propagation improve 7/30-day destination-cell distributions? This round changes only the position propagation of the previous annual-pooled, drogue-pooled M1vcat. The same outer whole-ID fitting/held-out roles, fitting-only speed thresholds, nine velocity categories, lag/lambda choices, equal qualified-hourly-pair weights, stopped labels and 1-degree output grid are frozen. There is no hyperparameter retuning. No final-test trajectory was accessed. These repeatedly inspected development folds are not a new confirmatory evaluation.

## Exact mathematical change

For a source survivor donor (x_d,v_d)->(y_d,v'_d), compute WGS84 inverse-geodesic azimuth a_d and distance r_d from its actual origin x_d to endpoint y_d. At the current query/particle position x, set y=ForwardWGS84(x,a_d,r_d). Preserve y between iterations; map it to its 1-degree cell before the next step and carry the donor endpoint velocity class jointly. At the original source anchor, recover the exact observed endpoint. This is an empirical displacement model, not a continuous-velocity regression, MDN, kernel estimator or newly weighted neighbour model.

Sample each eligible fitting donor equally within its cell/class row. The source law is the unchanged (1-lambda)*local + lambda*cell-pooled mixture; an absent class uses the cell law, an absent cell uses U. E and U absorb. The coordinate-discarded sampler copies the native donor endpoint cell, so its law equals the old M1vcat analytically. Exact joint-law and all-row frequency checks are saved separately. At lambda=1 the position-refined model becomes its pooled displacement counterpart, not the old cell-only M1.

Source first-exit donors remain E. For source survivors, transfer each observed hourly displacement relative to the source origin to the particle anchor; any observed-hour exit from D becomes E even if the path later returns. A conservative WGS84 geodesic-ball proof accelerates paths strictly inside D without changing exit results. Synthetic land/nonfinite endpoints become U, not inferred grounding or dropped/renormalised mass. Intermediate path transfer is used for D exit only; no new coastal-fate model is introduced.

This tests the additional assumption that within-cell/class donor displacements transfer to a different exact anchor. It preserves coordinate offsets but does not learn a spatially varying velocity function within the cell. Source E risk remains coarse rather than being counterfactually reclassified. A positive or negative result should be interpreted under these limitations.

## Scores and numerical integration

The primary criterion is unchanged S=1-2*p(truth)+sum_k p_k^2, including U as an extra failed category. S is not percentage accuracy. For M independent particles, the collision estimator 1-2*n_truth/M+sum_k n_k*(n_k-1)/(M*(M-1)) is an unbiased integration estimate of the same limiting-law S. The ordinary S of the actually issued finite ensemble is reported alongside it. Its upward finite-M bias must not be mistaken for a model effect. Two independent 32-particle repeats are run, coupled between coarse/precise models with common random inputs. The repeat range reports Monte Carlo variation; two repeats alone do not provide a precise Monte Carlo confidence interval.

Lower S is better. Old-exact is the previous analytic operator. The coordinate-discarded coarse sampler is its numerical control. Old-exact footprint and mass diagnostics remain in the parent report; NA below does not mean zero.

'''+markdown_table(table,['horizon_days','model','eligible_pairs','independent_ids','S_estimate','S_issued',
        'repeat_range','U_mass_pct','E_mass_pct','issued90_hit_pct','issued90_available_pct','issued90_cells'])+'''

## Fixed-fit paired-ID uncertainty

'''+(markdown_table(intervals,['horizon_days','comparison','delta_S','lower_95','upper_95']) if len(intervals) else 'No formal intervals in this engineering profile.')+'''

Intervals resample complete held-out IDs within old outer folds, conditional on fixed fits and settings. Particle repeats are averaged before resampling. Intervals do not account for refitting, researcher adaptation or all Monte Carlo uncertainty. Interpret any small improvement together with coarse-control error and repeat spread.

## Probability-region and spatial interpretation

Issued nominal-90% regions include cutoff ties and never renormalise U; if resolved mass is below 90%, the region is unavailable and the case remains in S. More or fewer sampled cells does not by itself establish a sharper limiting-law forecast. Zero sampled probability is not proven structural zero. No U sample is not proof that the limiting law has zero U. Formal limiting-law spatial completeness is unverified for particle forecasts, so no formal common-complete spatial superiority is claimed. Separately labelled issued-ensemble diagnostics retain the original Energy/100 km + squared ECEF cell-centre mean error/10000 reference. E/U receive no invented coordinates. These diagnostics use their own availability counts and are not a replacement selection loss.

## Traceability and reusable candidate

The compact cache retains native source keys, timestamps, exact positions/velocity atoms, per-ID ranges and qualified donor indices. Every ID's source target/reason digest and cell-pair frequencies reconcile with the sealed parent. All canonical data remain unchanged. The reusable candidate records the original full-development threshold, lag/lambda, cache digest and reconstruction function; it is not independently scored. Saved per-origin scores, ID summaries, sampling/backoff/exit audit, frozen choices and law closure permit inspection and reruns.

## Illustrative maps

The example cell/initial-velocity category is chosen by fitting-only 7-day pair support in fold 0. Each refined forecast starts from its own held-out exact origin; the map averages those forecasts across the matching release cohort. The observed panel uses exactly the same cohort. This is a cohort-average illustration, not a forecast from one arbitrarily chosen point. All panels share one probability scale. Full-D display can make small probabilities faint; cell probability is not continuous density. Seasonal, 365-day and grounding performance remain outside this experiment.
'''
    return text.replace('32-particle repeats',f'{particles}-particle repeats')


def write_report(paths,run,c,summary,idscores):
    table=comparison_table(summary);save=lambda p,t:paths.publish(p,lambda stream:stream.write(t.encode()))
    intervals=pd.read_csv(run['results']/'paired_ID_intervals.csv')
    text=report_text(table,intervals,c.get('active_particles_per_repeat',32));images=[]
    preds=pd.read_parquet(run['results']/'example_predictions.parquet')
    observed=pd.read_parquet(run['results']/'example_observed.parquet')
    definition=json.loads((run['results']/'example_definition.json').read_text())
    old=pd.read_parquet(paths.root/'results/runs'/c['comparison_parent']/'outer_0_forecasts.parquet')
    old=old.loc[old.model.eq('M1vcat-selected')&old.origin_cell_1.eq(definition['cell'])
                &old.origin_velocity_bin.eq(definition['velocity_bin'])]
    land=from_wkb(paths.asset('land_mask_intermediate',verify=True).read_bytes()).intersection(box(-83,19,-6,56)).simplify(.05,preserve_topology=True)
    region=shape(json.loads(paths.asset('release_R',verify=True).read_text())['features'][0]['geometry'])
    for h in [7,30]:
        g=old.loc[old.horizon_days.eq(h)];p=dict(zip(g.destination_cell_1,g.probability));u=p.pop(-3,0.)
        panels=[('Original M1vcat (analytic)',p,u)]
        for model in ['coarse-sampler','exact-position']:
            g=preds.loc[preds.horizon_days.eq(h)&preds.model.eq(model)].groupby('destination_cell_1').particles.sum()
            total=int(g.sum());p={int(k):float(v/total) for k,v in g.items()} if total else {};u=p.pop(-3,0.)
            panels.append((model+' (cohort mean)',p,u))
        g=observed.loc[observed.horizon_days.eq(h)];freq=g.destination_cell_1.value_counts()
        p={int(k):float(v/len(g)) for k,v in freq.items()} if len(g) else {}
        panels.append((f'Observed: {len(g)} pairs / {g.id.nunique()} IDs',p,0.))
        svg=map_svg(panels,_rings(land),_rings(region),definition['cell'],h,0)
        note=f'Initial velocity class {definition["velocity_bin"]}; forecasts averaged over matching exact release coordinates.'
        svg=svg.replace('<text x="25" y="51"',f'<text x="25" y="73" font-size="11">{escape(note)}</text><text x="25" y="51"',1)
        name=f'probability_{h}d.svg';save(run['results']/name,svg);images.append(name)
        text+=f'\n![{h}-day matched cohort probability maps]({name})\n'
    save(run['results']/'REPORT.md',text)
    html='<!doctype html><html lang="en"><meta charset="utf-8"><title>M1vcat exact position</title><style>body{font:16px system-ui;max-width:1300px;margin:32px auto;padding:16px;color:#182a3a}table{border-collapse:collapse}th,td{padding:8px;border:1px solid #ccd5dc}img{width:100%}p{line-height:1.6}</style>'
    html+='<h1>M1vcat: exact-position comparison</h1><p>Frozen development folds and parameters. Lower S is better. Finite-ensemble footprint diagnostics are approximate. No final-test claim.</p>'
    html+=table.to_html(index=False,float_format=lambda x:f'{x:.6g}')
    html+='<p><a href="REPORT.md">Full method and limitations</a> · <a href="summary.csv">Repeat scores</a> · <a href="paired_ID_intervals.csv">Paired ID intervals</a></p>'
    html+=''.join(f'<img src="{name}" alt="Matched cohort probability maps">' for name in images)+'</html>'
    save(run['results']/'review.html',html)
