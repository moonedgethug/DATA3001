"""One human-facing diagnosis/optimisation report, source-backed static maps."""
from html import escape
import json

import numpy as np
import pandas as pd
from shapely import from_wkb
from shapely.geometry import box, shape

from data3001.modelling.markov_report import markdown_table, map_svg, _rings
from data3001.modelling.report import _default_origins
from data3001.modelling.cv import fit_baselines
from data3001.modelling.markov_diagnostics import forecast_lag


def bias_svg(table):
    width, height = 1200, 430
    output = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
              '<rect width="100%" height="100%" fill="white"/>', '<g font-family="Arial, sans-serif" fill="#182a3a">',
              '<text x="25" y="26" font-size="19">Descriptive propagation diagnosis: identical matched 30-day-qualified starts</text>',
              '<text x="25" y="48" font-size="12">Known in-domain mass conditioning; E/U reported separately. These are not proper scores or individual-position RMSE.</text>']
    days = [1, 2, 3, 5, 7, 30]
    metrics = [('centre_bias_km', 'Prediction-centre to observed-centre (km)'),
               ('predicted_RMS_km', 'Spread around prediction centre (km)'),
               ('observed_RMS_km', 'Spread around observed centre (km)')]
    for index, (column, title) in enumerate(metrics):
        left, top, w, h = 55+index*395, 95, 330, 240
        part = table.loc[table.model.isin(['B2', 'M1-1d'])]
        finite = part.loc[np.isfinite(part[column]), column]
        maximum = max(float(finite.max()) if len(finite) else 0., 1.)*1.1
        output.append(f'<text x="{left-25}" y="{top-15}" font-size="13">{escape(title)}</text>')
        for y in range(5):
            value = maximum*y/4; yy = top+h-h*y/4
            output.append(f'<path d="M{left},{yy} H{left+w}" stroke="#dce3e8"/>')
            output.append(f'<text x="{left-8}" y="{yy+4}" text-anchor="end" font-size="11">{value:.0f}</text>')
        for model, colour in [('B2', '#336fba'), ('M1-1d', '#bd3c69')]:
            group = part.loc[part.model.eq(model)].set_index('horizon_days')
            points, segments, available = [], [], 0
            for j, day in enumerate(days):
                value = float(group.loc[day, column]) if day in group.index else np.nan
                if not np.isfinite(value):
                    if points:
                        segments.append(points); points = []
                    continue
                available += 1
                x = left+j*w/5; yy = top+h-h*value/maximum
                points.append(f'{x:.2f},{yy:.2f}')
                output.append(f'<circle cx="{x}" cy="{yy}" r="3" fill="{colour}"/>')
            if points:
                segments.append(points)
            for points in segments:
                output.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{colour}" stroke-width="2"/>')
            if not available:
                yy = top+18+(18 if model == 'M1-1d' else 0)
                output.append(f'<text x="{left+12}" y="{yy}" font-size="12" fill="{colour}">Unavailable: {model}</text>')
        for j, day in enumerate(days):
            output.append(f'<text x="{left+j*w/5}" y="{top+h+20}" text-anchor="middle" font-size="12">{day}</text>')
    output += ['<text x="25" y="390" font-size="13">Blue: direct B2 | Magenta: daily M1 | Days use categorical spacing. Means are weighted by matched hourly pairs.</text>',
               '<text x="25" y="414" font-size="11">Centres and widths use fixed WGS84 ECEF cell-centre coordinates. A close mean alone does not establish distributional accuracy.</text>', '</g></svg>']
    return ''.join(output)


def illustrative_panels(result, releases, outer, origin, h, fold=0):
    held = {i for i, f in outer.items() if f == fold}
    choices = result['choices']
    lag = int(choices.loc[choices.outer_fold.eq(fold) & choices.horizon_days.eq(h), 'lag_days'].iloc[0])
    mapping = result['predictions'][fold]
    models = ('B2', 'M1-1d', 'M1-selected')
    if not all((h, origin, model) in mapping for model in models):
        controls = fit_baselines(releases, set(outer)-held)
        p = controls['B2'].get((h, origin))
        fallback = {'B2': (p or {}, 0. if p else 1.),
                    'M1-1d': forecast_lag(result['operators'][fold], origin, h, 1),
                    'M1-selected': forecast_lag(result['operators'][fold], origin, h, lag)}
    else:
        fallback = {}
    panels = []
    for model in models:
        p, u = mapping[(h, origin, model)] if (h, origin, model) in mapping else fallback[model]
        label = model + (f' ({lag}-day lag)' if model == 'M1-selected' else '')
        panels.append((label, p, u))
    observed = releases.loc[releases.id.isin(held) & releases.origin_cell_1.eq(origin) & releases.horizon_days.eq(h)]
    counts = observed.groupby('destination_cell_1').pair_count.sum()
    n = int(counts.sum())
    panels.append((f'Observed: {n} pairs / {observed.id.nunique()} IDs' if n else 'No eligible held-out starts',
                   {int(c): float(v/n) for c, v in counts.items()} if n else {}, 0.))
    return panels


def write_optimisation_report(paths, run, summary, intervals, result, releases, outer, diagnosis, final_selection):
    diag = pd.read_csv(diagnosis/'summary.csv')
    bias = pd.read_csv(diagnosis/'bias_summary.csv')
    ck = pd.read_csv(diagnosis/'controlled_summary.csv')
    support = releases.loc[releases.id.map(outer).ne(0)].groupby(
        ['horizon_days', 'origin_cell_1'], as_index=False).agg(pair_count=('pair_count', 'sum'), independent_ids=('id', 'nunique'))
    support['outer_fold'] = 0
    origin = _default_origins(support, [0])['0']
    land = from_wkb(paths.asset('land_mask_intermediate', verify=True).read_bytes()).intersection(
        box(-83, 19, -6, 56)).simplify(.05, preserve_topology=True)
    region = shape(json.loads(paths.asset('release_R', verify=True).read_text())['features'][0]['geometry'])
    for h in (7, 30):
        panels = illustrative_panels(result, releases, outer, origin, h)
        svg = map_svg(panels, _rings(land), _rings(region), origin, h, 0)
        paths.publish(run['results']/f'probability_{h}d.svg', lambda s, svg=svg: s.write(svg.encode()))
    selected = summary.loc[summary.model.isin(['B1', 'B2', 'M1-1d', 'M1-selected'])]
    diagnostics = diag.loc[diag.model.isin(['B2', 'M1-1d'])]
    bias = bias.loc[bias.model.isin(['B2', 'M1-1d'])]
    sections = [
        '# M1 diagnosis and one bounded lag optimisation',
        '**Status:** development-only benchmark analysis; no new predictor, canonical change, final-test access or annual/seasonal/grounding skill claim.',
        '## What was tested',
        'First locate deviations at days 1/2/3/5/7/30 using an identical retrospective 30-day-qualified set of source-keyed releases. Then compare one predeclared lag grid, 1/3/5/7 days, with exact independently fitted remainder kernels. All geographic definitions, pooled scenario and equal eligible-pair weights remain fixed. A daily self-transition is endpoint occupancy, not continuous within-cell residence.',
        'The operator remains empirical: `P_tau[i,j] = N_tau[i,j] / sum_j N_tau[i,j]`; `p_h = e_i P_tau^(h//tau) P_r` when r=h%tau is nonzero. E (first observed exit) and U (unsupported model state) remain separate absorbers. No missing probability is renormalised into physical destinations. Linear/quadratic spatial scores evaluate forecasts; they do not train the frequency estimator.',
        '## 1. Where daily forecasts deviate',
        'The table below uses the same eligible source starts at every diagnostic horizon. B2 is fitted directly at each horizon using fitting IDs from that same retrospective cohort; M1 uses daily D-origin production counts. Cohort and information differences remain, so this diagnoses the deployed approximation rather than isolating a single physical cause.',
        markdown_table(diagnostics, ['horizon_days', 'model', 'eligible_pairs', 'independent_ids', 'brier_failure_penalized', 'region90_hit_pct_available', 'mean_region90_cells']),
        markdown_table(bias, ['horizon_days', 'model', 'descriptive_available_pct', 'centre_bias_km', 'predicted_RMS_km', 'observed_RMS_km', 'unresolved_mass']),
        f'![Bias over horizon](../{diagnosis.name}/bias_by_horizon.svg)',
        'Centres and RMS spreads condition on the known geographic mass and use fixed WGS84 ECEF cell centres. They are descriptive group-distribution comparisons, not individual endpoint RMSE or replacement scoring criteria. They can be available when exact-U=0 formal spatial scores are NA. A close mean can conceal errors that cancel. A large number of positive-probability cells can consist mostly of negligible tail mass.',
        '## 2. Controlled short-lag consistency screen',
        'All phase/direct estimates below use matched three-day-qualified D-start windows from fitting IDs, evaluated on held-out R starts from that cohort. Direct fits 0->2/3. Phase-composed separately fits 0->1, 1->2, 2->3; Pooled-composed pools those phase counts into one daily row. Already absorbed E stays E in later phases even after geographical re-entry. This is a retrospective diagnostic with explicit phase/window weights, not a new production weighting policy.',
        markdown_table(ck, ['horizon_days', 'model', 'pairs', 'independent_ids', 'S']),
        'Differences can reflect coarse-state memory, phase-dependent sampling, qualification selection and estimation noise. They do not prove that physical ocean motion is non-Markovian. Per-cell total-variation differences and unresolved mass are retained in the source diagnosis run.',
        '## 3. One optimisation: lag selection',
        'Each original outer whole-ID fold has four inner whole-ID folds. Select a lag independently for day 7 and day 30 using inner-OOF pair-weighted S. Ties within 1e-12 choose the shortest lag. No cross-horizon weighting or spatial loss is introduced. All fitting counts and choices exclude the complete outer-held-out IDs. Fixed candidates and the selected procedure are scored on identical original eligible 7/30-day cases, not the retrospective diagnostic subset.',
        markdown_table(result['choices'], ['outer_fold', 'horizon_days', 'lag_days']),
        markdown_table(summary, ['horizon_days', 'model', 'eligible_pairs', 'independent_ids', 'brier_failure_penalized', 'zero_probability_pct', 'region90_hit_pct_available', 'mean_region90_cells', 'mean_unresolved_mass']),
        '## 4. Paired held-out comparison',
        'Lower S is better, not percentage accuracy. The intervals use 200 whole-held-out-ID resamples within fixed outer folds; they condition on fitted kernels and choices, excluding refitting/selection/source uncertainty. Comparisons are exploratory, not multiplicity-adjusted confirmation.',
        markdown_table(intervals, ['horizon_days', 'comparison', 'delta_S', 'lower_95', 'upper_95']),
        '## 5. Illustrative before/after maps',
        f'Outer fold 0, release cell {origin}; selected solely from fitting-ID support across the two horizons. Each figure shares one scale and matching held-out observations. Display land can cover parts of coastal cells. The figures show per-cell probability, not area density or confirmed grounding.',
        '![7-day comparison](probability_7d.svg)', '![30-day comparison](probability_30d.svg)',
        '## 6. Handover and limitations',
        f'Full-development candidate lags: {final_selection}. These are chosen from fixed-candidate outer-OOF terms and then refitted on development IDs. Their final refits have no independent final-test score. Exact-remainder kernels and stable state indexes are saved under operators/; development_candidate.json records release semantics and selected lags.',
        'Existing complete-forecast spatial rules are unchanged: a strictly positive U, even if tiny, makes that formal spatial score unavailable. Conditional centre/spread diagnostics must not be presented as a silently relaxed Energy Score. Failed and unsupported cases remain in S. Old daily scores are independently required to match the frozen prototype before this report can complete.',
        'One lag comparison cannot fix all coarse-state effects. Review direction/subcell/phase evidence before choosing a small additional state or environmental predictor. Do not automatically add features or assume narrower maps are better. Final-test, year-scale, seasonal, object-specific and grounding performance remain unvalidated.',
        'Sources: [Data Contract v1.0](../../../docs/contract/data_contract_v1.0.xlsx); [McAdam and van Sebille (2018)](https://doi.org/10.1002/2017JC013363); [O\u2019Malley et al. (2021)](https://doi.org/10.1175/JTECH-D-20-0134.1).',
    ]
    text = '\n\n'.join(sections)+'\n'
    paths.publish(run['results']/'REPORT.md', lambda s: s.write(text.encode()))
    html = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>M1 lag optimisation</title>'
            '<style>body{font:16px system-ui;max-width:1250px;margin:25px auto;padding:15px;color:#182a3a}img{width:100%}table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #ccd;padding:7px}p{line-height:1.6}</style>'
            '<h1>M1: diagnosis and one lag optimisation</h1><p>Development outer-held-out results; no final-test score. '
            'Lower S is better, not percentage accuracy. Read the report for matched-cohort and uncertainty limits.</p>'
            '<p><a href="REPORT.md">Full report</a> | <a href="summary.csv">Complete score table</a></p>'
            +selected[['horizon_days', 'model', 'brier_failure_penalized', 'region90_hit_pct_available', 'mean_region90_cells']].to_html(index=False)
            +f'<img src="../{diagnosis.name}/bias_by_horizon.svg" alt="Bias over horizons">'
            +'<img src="probability_7d.svg" alt="7-day before and after">'
            +'<img src="probability_30d.svg" alt="30-day before and after"></html>')
    paths.publish(run['results']/'review.html', lambda s: s.write(html.encode()))
