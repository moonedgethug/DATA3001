"""One English account of selection, coordinate ablation and held-ID evidence."""
from html import escape
import json
import numpy as np
import pandas as pd
from shapely import from_wkb
from shapely.geometry import box,shape
from data3001.modelling.markov_report import markdown_table,map_svg,_rings
from data3001.modelling.markov_iteration import SCHEDULES


def report_text(table,intervals,choices):
    text='''# 30-day schedule/lambda CV: does exact position help?

## Question and fair controls

Both coordinate-discarded and exact-position representations are independently optimised over the same nine schedules and eleven lambdas. Comparing only a newly tuned position model with an old frozen coarse model would confound coordinates with tuning opportunity. The primary contrast is position-CV minus coarse-CV. The matched-setting controls additionally compare representations at each procedure's selected settings. Frozen coarse/position models and direct B2 remain references. These are adaptive development comparisons, not final-test results: earlier outer outcomes influenced the research direction.

No path was eliminated by a manually fixed lambda. Within each original outer training pool, four whole-ID inner folds evaluate all99 candidates. StageA is a diagnostic at the historical training-CV reference lambda; it cannot prune paths. StageB jointly selects path/lambda by pooled inner-OOF S, refines numerically unresolved contenders, locks choices, then evaluates the untouched outer IDs. Complete fitting IDs are excluded across both R and the wider D. Existing fit-only speed medians and nine velocity labels remain fixed by role.

## Mathematical model and numerical computation

State is exact WGS84 position plus velocity category, or E/U. Each kernel is the existing affine law K[d,lambda]=(1-lambda)*L[d]+lambda*B[d], with the same missing-row fallback. Propagate the full joint state along an ordered sequence summing exactly30days, then marginalise velocity and bin positions at1degree. Future held-out observations are never inputs. Observed-hour exit/re-entry and synthetic geometry rules are unchanged; source E/U absorb and no unresolved mass is renormalised away.

Inner CV shares simulations through conditional component count stratification. For m ordered steps and k pooled labels, sample their positions uniformly among choose(m,k) orders. The exact mixing weights are choose(m,k)*lambda^k*(1-lambda)^(m-k). This identity holds even for noncommuting kernels, state-dependent rows, backoff L=B and absorbing dummy labels. It changes numerical integration, not the model, data features, origin weights or lambda search. Every lambda is scored. Different path/allocation layouts have separate keyed RNG streams; lambdas within one path share samples. Independent repeats support MC error estimation.

Each active stratum uses at least two samples and at least ceil(target*max_lambda binomial_weight). This bounds each category probability estimator's variance by its iid-target counterpart. It does not assert a corresponding universal bound for the nonlinear score. The issued distribution is a normalised weighted sum of stratum frequencies. Subtract the within-stratum squared-probability bias to obtain an unbiased estimate of the same S; ordinary issued S remains secondary. The final outer comparison uses the original independent-particle implementation at64particles x2repeats. Inner numerical targets32/64/128 and actual allocations are recorded.

Native inverse-geodesic displacements are cached without approximation. A conservative directional bound can certify transferred hourly paths inside the frozen rectangular D; any uncertified path receives the original full hourly scan. This is computational metadata, not new learned features. Cached/uncached forecasts and lambda-endpoint samplers are verified against the original implementation.

## Primary held-ID outcome

Lower S is better; S is not percentage accuracy. All268998 eligible30-day origins/337IDs remain in primary scoring. Analytic coarse scores have no particle bias; position scores use the unbiased collision estimate. Repeated particle runs do not double the statistical sample size. U/E remain visible. Smaller finite-particle regions do not establish greater sharpness or limiting-law calibration.

'''+markdown_table(table,list(table.columns))+'\n\n## Paired whole-ID uncertainty\n\n'
    text+=(markdown_table(intervals,['comparison','delta_S','lower_95','upper_95']) if len(intervals) else 'No formal intervals in this fixture.')
    text+='''

Intervals use200 paired whole-ID resamples within outer folds, conditional on fixed fits/choices. They exclude refitting, researcher adaptation and all selection uncertainty. Numerical integration error is a separate quantity. A crossing-zero interval does not establish equivalence or a reliable gain. Improved S accompanied by more U must be interpreted with failure/support diagnostics.

## Choices and reproducibility

'''+('```json\n'+json.dumps(choices,indent=2)+'\n```\n' if choices else 'No choices in this fixture.\n')
    text+='''
All initial grids, refined candidate sets, per-ID scores, role IDs/thresholds, source-case digests and immutable checkpoint receipts are saved. Completed runs are immutable. The canonical dataset and final test are untouched. The evidence concerns annual-pooled, known-initial-velocity30-day distributions, not seasonal/year/grounding or arbitrary-object performance.

Maps average individual forecasts over a fitting-support-selected cell/initial-velocity cohort in fold0. Observed endpoints are the identical held-out cohort. They are illustrative cohort distributions, not overall performance or a single-point forecast. All panels share a scale. Auxiliary Energy/100+squared ECEF-mean error/10000 values are issued-ensemble diagnostics on declared available subsets, not a new selection loss.
'''
    return text


def write_report(paths,run,c,summary,intervals,choices):
    rows=[]
    for model,g in summary.groupby('model'):
        rows.append({'model':model,'eligible_pairs':int(g.eligible_pairs.iloc[0]),'independent_ids':int(g.independent_ids.iloc[0]),
            'S':float(g.S_integration.mean()),'mean_U_pct':float(100*g.U_mass.mean()),'mean_E_pct':float(100*g.E_mass.mean())})
    table=pd.DataFrame(rows);text=report_text(table,intervals,choices)
    mc=pd.read_csv(run['results']/'outer_MC_summary.csv')
    text+='\n## Numerical uncertainty on the same outer cases\n\n'
    text+=markdown_table(mc,['comparison','delta_S','MC_SE','MC_only_lower_95','MC_only_upper_95'])
    text+='\n\nMC intervals condition on fixed queries/fits and independent query streams; they are not whole-ID generalisation intervals.\n'
    trace=pd.concat([pd.read_parquet(run['results']/f'outer_{f}_trace.parquet') for f in range(5)])
    support=[]
    for model,g in trace.groupby('model'):
        denom=float(g.loc[g.day.eq(30),'particles'].sum())
        support.append({'model':model,'origin_particles':int(denom),
            'unsupported_U_pct':100*g.step_unsupported_cell.sum()/denom,
            'geometry_U_pct':100*g.step_endpoint_geometry_U.sum()/denom,
            'translated_exit_pct':100*g.step_translated_exit.sum()/denom,
            'backoff_events_per100particles':100*g.step_row_backoff.sum()/denom})
    text+='\n## Failure causes across the complete propagated paths\n\n'
    text+=markdown_table(pd.DataFrame(support),list(support[0]))
    text+='\n\nU and E absorb, so their first-event causes are counted once. Backoff may repeat; its events-per100 measure can exceed100. Full per-substep traces retain active particles and every original step audit counter.\n'
    definition=json.loads((run['results']/'example_definition.json').read_text())
    parts=pd.read_parquet(run['results']/'example_particles.parquet');coarse=pd.read_csv(run['results']/'example_coarse.csv')
    observed=pd.read_parquet(run['results']/'example_observed.parquet');panels=[]
    for model in ['coarse-CV','position-CV','position-frozen']:
        if model.startswith('coarse'):
            g=coarse.loc[coarse.model.eq(model)];p=dict(zip(g.destination_cell_1,g.probability))
        else:
            g=parts.loc[parts.model.eq(model)].groupby('destination_cell_1').particles.sum();total=int(g.sum())
            p={int(k):float(v/total) for k,v in g.items()}
        u=p.pop(-3,0.);panels.append((model,p,u))
    freq=observed.destination_cell_1.value_counts();p={int(k):float(v/len(observed)) for k,v in freq.items()}
    panels.append((f'Observed: {len(observed)} pairs / {observed.id.nunique()} IDs',p,0.))
    land=from_wkb(paths.asset('land_mask_intermediate',verify=True).read_bytes()).intersection(box(-83,19,-6,56)).simplify(.05,preserve_topology=True)
    region=shape(json.loads(paths.asset('release_R',verify=True).read_text())['features'][0]['geometry'])
    svg=map_svg(panels,_rings(land),_rings(region),definition['cell'],30,0)
    note=f'Initial velocity category {definition["velocity_bin"]}; selected by fitting support; cohort means, common held cases.'
    svg=svg.replace('<text x="25" y="51"',f'<text x="25" y="73" font-size="11">{escape(note)}</text><text x="25" y="51"',1)
    paths.publish(run['results']/'probability_30d.svg',lambda s:s.write(svg.encode()))
    text+='\n![30-day matched cohort probability maps](probability_30d.svg)\n'
    paths.publish(run['results']/'REPORT.md',lambda s:s.write(text.encode()))
    html='<!doctype html><html lang="en"><meta charset="utf-8"><title>30-day iteration CV</title><style>body{font:16px system-ui;max-width:1300px;margin:30px auto;padding:16px;color:#182a3a}table{border-collapse:collapse}th,td{padding:8px;border:1px solid #ccd5dc}img{width:100%}p{line-height:1.6}</style>'
    html+='<h1>30-day schedule/lambda CV</h1><p>Both representations independently optimised; lower S is better. Adaptive development evidence, not final test.</p>'
    html+=table.to_html(index=False,float_format=lambda v:f'{v:.6g}')
    html+='<h2>Paired ID comparisons</h2>'+intervals.to_html(index=False,float_format=lambda v:f'{v:.6g}')
    html+='<h2>Numerical uncertainty</h2>'+mc[['comparison','delta_S','MC_SE']].to_html(index=False,float_format=lambda v:f'{v:.6g}')
    html+='<p><a href="REPORT.md">Full method, choices and limitations</a> · <a href="selected_parameters.json">Fold choices</a></p><img src="probability_30d.svg" alt="Common-cohort probability maps"></html>'
    paths.publish(run['results']/'review.html',lambda s:s.write(html.encode()))
