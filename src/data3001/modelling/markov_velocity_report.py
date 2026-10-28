"""One English report and velocity-matched probability-map illustrations."""
from html import escape
import json

import numpy as np
import pandas as pd
from shapely import from_wkb
from shapely.geometry import box, shape

from data3001.modelling.markov_report import markdown_table, map_svg, _rings


def report_text(summary, intervals, choices, final, threshold):
    table = markdown_table(summary, ['horizon_days', 'model', 'brier_failure_penalized',
               'region90_hit_pct_available', 'mean_region90_cells', 'zero_probability_pct',
               'mean_unresolved_mass', 'spatial_common_pairs', 'linear_quadratic_reference_common']) if len(summary) else 'No score rows.'
    ci = markdown_table(intervals, ['horizon_days', 'comparison', 'delta_S', 'lower_95', 'upper_95']) if len(intervals) else 'No interval rows.'
    selected = markdown_table(choices, ['outer_fold', 'model', 'horizon_days', 'lag_days', 'lambda_value']) if len(choices) else 'No outer choices.'
    return f'''# M1vcat: annual-pooled categorical velocity transport

## Question and scope

Does retaining a compact categorical initial velocity state improve 7/30-day location distributions over the frozen cell-only M1? Inputs are the observed origin cell and velocity at release. Future held-out velocities or positions are never fed into propagation. This is a historical known-initial-velocity query; no claim is made for a release with unspecified velocity, operational rescue/oil forecasting, seasonal differences, confirmed grounding, or 365-day accuracy. No final test trajectory was accessed.

## Mathematical model

State S=(1-degree cell, velocity label). Label 0 is exact zero velocity and is not absorbing; labels 1..8 distinguish SW/SE/NW/NE and speed <= / > the fitting median. Axis ties use ve>=0, vn>=0. The median uses only positive speeds at qualified D hourly observations from fitting IDs; it is shared across every lag/remainder in that fit. The development-candidate threshold is {threshold:.12g} m/s.

Local joint rows are multinomial frequency estimates. The cell-pooled joint law ignores source velocity while retaining destination velocity. Supported rows blend (1-lambda)*local + lambda*pooled. An unseen conditional row falls back to its fitting cell law; a wholly unsupported cell goes to U. Observed first exit E and unsupported U remain separate absorbing states. Exit and re-entry still produces stopped E. Missing follow-up is not an observed U outcome.

Propagation retains velocity between steps; the final map sums destination velocity probabilities within each cell. Exact remainder kernels are fitted separately with the same labels/IDs. At lambda=1 this construction degenerates to the corresponding old M1 location forecast. Raw classification is lambda=0 with the same explicit missing-row backoff.

## Estimation, selection and evidence

The empirical joint matrix maximises the row-multinomial likelihood; the CV-selected smoothed matrix is not claimed to maximise that unpenalised likelihood. The original outer-five/inner-four whole-ID folds are retained. Each horizon independently selects lag in {{1,3,5,7}} and lambda in {{0,.1,...,1}} by pooled inner-OOF, equal-hourly-pair-weighted S. Ties within 1e-12 prefer shorter lag, then larger lambda. Raw and cell-only controls select their own lag in the same inner folds. All candidate comparisons retain identical eligible physical cases.

The primary all-case score remains Brier/S, including unsupported forecast mass. The auxiliary linear + quadratic reference remains Energy/100 km + squared mean error/(100 km)^2, using the old ECEF cell-centre chord coordinates. It is available only under the unchanged complete in-domain forecast/outcome conditions. NA is not filled or silently dropped from primary scoring. Raw infinite log losses and zero-probability failures remain visible.

The cache partitions speed at the union of predeclared fit medians only to store lossless sufficient counts. A model merges those intervals using its own fitting median. Extra cache boundaries have no predictive effect. Summing velocity exactly restores the parent source counts; no canonical data column or value was changed or clipped.

## Outer held-ID results

Lower S is better. Coverage is an observed hit percentage for an issued nominal-90% probability region; S is not percentage accuracy. Regions include cutoff ties and do not renormalise U.

{table}

## Paired uncertainty

{ci}

Intervals use 200 paired held-out-ID resamples within outer folds, conditional on saved fits and choices. They do not include refitting, model-selection or repeated-research uncertainty. These are development comparisons, not final-test results.

## Choices by outer fold

{selected}

## Reusable development candidates

Selected lag/lambda by horizon: {final}. These candidates use fixed-candidate outer-OOF scores for final selection and are refitted on the development pool. The refits are not independently scored. All operator components, thresholds, ID roles and selected settings are saved.

## Interpretation and remaining limits

Compare M1vcat-selected with M1-selected and with the raw categorical model. Improvement after shrinkage does not prove every velocity category is well supported. Use row pair counts, independent IDs, dominant-ID fractions, backoff rates and U together. Continuous speed/direction information is still discretised; annual and drogue pooling remain deliberate benchmark assumptions. The observed held-out subset cannot establish calibrated exits if no positive exit outcomes are present.

Probability maps below are fitting-support-selected illustrations of the same origin cell/velocity class. Observed panels use only matching held-out release cases; a map is not the overall performance criterion. Sparse or unavailable observed panels are labelled honestly.
'''


def write_velocity_report(paths, run, summary, intervals, choices, final, threshold, example):
    text = report_text(summary, intervals, choices, final, threshold)
    images = []
    if example:
        land = from_wkb(paths.asset('land_mask_intermediate', verify=True).read_bytes()).intersection(
            box(-83, 19, -6, 56)).simplify(.05, preserve_topology=True)
        region = shape(json.loads(paths.asset('release_R', verify=True).read_text())['features'][0]['geometry'])
        origin, b, cut = example['origin'], example['velocity_bin'], example['threshold']
        for h, panels in example['panels'].items():
            svg = map_svg(panels, _rings(land), _rings(region), origin, int(h), 0)
            annotation = f'Observed initial velocity class {b}; fitting speed threshold {cut:.4f} m/s. Example selected using fitting support only.'
            svg = svg.replace('<g font-family=', '<g font-family=', 1).replace(
                '<text x="25" y="51"', f'<text x="25" y="73" font-size="11">{escape(annotation)}</text><text x="25" y="51"', 1)
            name = f'probability_{h}d.svg'
            paths.publish(run['results']/name, lambda stream, svg=svg: stream.write(svg.encode()))
            images.append(name); text += f'\n![{h}-day matched illustration]({name})\n'
    paths.publish(run['results']/'REPORT.md', lambda stream: stream.write(text.encode()))
    # A lightweight reusable local review page; no external publishing or scripts.
    display = summary[['horizon_days', 'model', 'brier_failure_penalized',
                       'region90_hit_pct_available', 'mean_region90_cells', 'zero_probability_pct']].to_html(
                           index=False, float_format=lambda x: f'{x:.6g}')
    html = '<!doctype html><meta charset="utf-8"><title>M1vcat results</title><style>body{font:16px system-ui;margin:32px;color:#182a3a}table{border-collapse:collapse}td,th{padding:8px;border:1px solid #ccd5dc}img{max-width:100%}</style>'
    html += '<h1>M1vcat: categorical velocity comparison</h1><p>Development outer-held-ID results. Known initial velocity; annual pooled. Lower S is better. No final-test claim.</p>'+display
    html += '<p><a href="REPORT.md">Full mathematical method, choices and limitations</a></p>'
    html += ''.join(f'<img src="{name}" alt="Velocity-matched probability maps">' for name in images)
    paths.publish(run['results']/'review.html', lambda stream: stream.write(html.encode()))
