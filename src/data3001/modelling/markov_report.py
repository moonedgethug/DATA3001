"""English, source-backed report and shared-scale static probability maps."""
from html import escape
import json

import numpy as np
import pandas as pd
from shapely import from_wkb
from shapely.geometry import box, shape

from data3001.modelling.report import _default_origins


def markdown_table(frame, columns):
    def value(x):
        if isinstance(x, (float, np.floating)):
            return 'NA' if np.isnan(x) else 'inf' if np.isinf(x) else f'{x:.6g}'
        return str(x)
    lines = ['| '+' | '.join(columns)+' |', '| '+' | '.join(['---']*len(columns))+' |']
    lines += ['| '+' | '.join(value(x) for x in row)+' |' for row in frame[columns].itertuples(index=False, name=None)]
    return '\n'.join(lines)


def map_svg(panels, land_rings, release_rings, origin, days, fold):
    width, height = 1200, 800
    x0, x1, y0, y1 = -83., -6., 19., 56.
    maximum = max([p for _, dist, _ in panels for c, p in dist.items() if c >= 0] or [1.])
    maximum = maximum or 1.
    result = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
              '<rect width="100%" height="100%" fill="white"/>',
              '<g font-family="Arial, sans-serif" fill="#182a3a">',
              f'<text x="25" y="28" font-size="20">{days} days | pooled stopped target | outer held-out fold {fold}</text>',
              f'<text x="25" y="51" font-size="13">Release cell {origin}; Shared scale: 0 to {maximum*100:.1f}% probability per cell. No renormalisation.</text>']
    for panel, (title, distribution, u) in enumerate(panels):
        left, top = 45+(panel % 2)*590, 100+(panel//2)*340
        w, h = 540, 260
        def xy(lon, lat):
            return left+(lon-x0)/(x1-x0)*w, top+(y1-lat)/(y1-y0)*h
        result.append(f'<text x="{left}" y="{top-14}" font-size="17">{escape(title)}</text>')
        result.append(f'<rect x="{left}" y="{top}" width="{w}" height="{h}" fill="#f4f8fa" stroke="#b0bdc5"/>')
        for cell, p in distribution.items():
            if cell < 0 or p <= 0:
                continue
            lon, lat = -180+cell % 360, -90+cell//360
            x, y = xy(lon, lat+1)
            t = min(1., p/maximum)
            red, green, blue = int(255-100*t), int(250-230*t), int(252-130*t)
            result.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w/(x1-x0):.3f}" height="{h/(y1-y0):.3f}" fill="rgb({red},{green},{blue})"/>')
        def rings_path(rings):
            chunks = []
            for ring in rings:
                points = [xy(lon, lat) for lon, lat in ring]
                chunks.append('M'+' L'.join(f'{x:.2f},{y:.2f}' for x, y in points)+' Z')
            return ' '.join(chunks)
        if land_rings:
            result.append(f'<path d="{rings_path(land_rings)}" fill="#d9dedf" fill-rule="evenodd" stroke="#7c898f" stroke-width="0.5"/>')
        if release_rings:
            result.append(f'<path d="{rings_path(release_rings)}" fill="none" stroke="#1d6a48" stroke-width="1.2"/>')
        ox, oy = xy(-180+origin % 360, -90+origin//360+1)
        result.append(f'<rect x="{ox:.3f}" y="{oy:.3f}" width="{w/(x1-x0):.3f}" height="{h/(y1-y0):.3f}" fill="none" stroke="#00a55b" stroke-width="2"/>')
        for lon in [-80, -60, -40, -20]:
            x, y = xy(lon, y0)
            result.append(f'<text x="{x-13:.1f}" y="{y+16:.1f}" font-size="11">{abs(lon)} W</text>')
        for lat in [20, 30, 40, 50]:
            x, y = xy(x0, lat)
            result.append(f'<text x="{x-33:.1f}" y="{y+4:.1f}" font-size="11">{lat} N</text>')
        result.append(f'<text x="{left}" y="{top+h+37}" font-size="12">OUTSIDE {distribution.get(-2, 0.)*100:.3f}% | unresolved {u*100:.3f}% | geographic mass {sum(p for c,p in distribution.items() if c>=0)*100:.3f}%</text>')
    result += ['<text x="25" y="791" font-size="11">Equirectangular display; cell probability, not density or confirmed grounding. Grey land can obscure coastal cell fills.</text>', '</g></svg>']
    return ''.join(result)


def _rings(geometry):
    parts = list(geometry.geoms) if geometry.geom_type == 'MultiPolygon' else [geometry]
    return [list(r.coords) for p in parts if p.geom_type == 'Polygon' for r in [p.exterior, *p.interiors]]


def write_report(paths, run, summary, intervals, scores, predictions, support, releases, outer, inputs):
    default = _default_origins(support, [0])['0']
    land = from_wkb(paths.asset('land_mask_intermediate', verify=True).read_bytes())
    land = land.intersection(box(-83, 19, -6, 56)).simplify(.05, preserve_topology=True)
    release = shape(json.loads(paths.asset('release_R', verify=True).read_text())['features'][0]['geometry'])
    images = []
    for h in [7, 30]:
        panels = []
        for model in ['B1', 'B2', 'M1']:
            key = (h, default, model)
            if key in predictions[0]:
                p, u = predictions[0][key]
                panels.append((model+' prediction', p, u))
        observed = releases.loc[releases.horizon_days.eq(h) & releases.origin_cell_1.eq(default)
                                & releases.id.map(outer).eq(0)]
        if len(observed):
            n = int(observed.pair_count.sum())
            counts = observed.groupby('destination_cell_1').pair_count.sum()
            observed_p = {int(c): float(v/n) for c, v in counts.items()}
            panels.append((f'Observed held-out: {n} pairs / {observed.id.nunique()} IDs', observed_p, 0.))
        else:
            panels.append(('No eligible held-out cases', {}, 0.))
        svg = map_svg(panels, _rings(land), _rings(release), default, h, 0)
        name = f'probability_{h}d.svg'
        paths.publish(run['results']/name, lambda stream, svg=svg: stream.write(svg.encode()))
        images.append(f'![{h}-day stopped probabilities]({name})')
    audit = pd.read_csv(inputs/'candidate_reasons.csv')
    eligible = audit.loc[audit.population.eq('R') & audit.reason_code.eq(0)]
    long_support = eligible.groupby(['horizon_days', 'departure_season'], as_index=False).agg(
        eligible_pairs=('candidate_count', 'sum'), independent_ids=('id', 'nunique'))
    source = pd.read_csv(inputs/'source_ID_summary.csv')
    totals = eligible.groupby('horizon_days', as_index=False).agg(eligible_pairs=('candidate_count', 'sum'), independent_ids=('id', 'nunique'))
    sections = [
        '# M1: fixed one-day annual-pooled Markov prototype',
        '**Status:** real development-only fitting and five whole-ID outer-fold evaluation. This is a fixed configuration, not an optimised-lag or final-test result.',
        '## Question and inputs',
        f'From a selected Southern Gulf Stream release cell, predict the stopped outcome at day 7 or 30. Input cache: `{inputs.name}`. Read {len(source):,} development IDs and {int(source.retained_rows.sum()):,} retained records during preparation. Fit all eligible D-origin transitions, including D-only instruments; evaluate releases in R.',
        'R and D, exact UTC matching, 1-degree grid, equal valid-pair weights and interval eligibility follow Data Contract v1.0. D is 81-8 W, 20-55 N. Every hourly origin may contribute a one-day pair. Intermediate hourly observations validate first exit/path completeness; they are not future predictors.',
        '## Mathematical method',
        '`P[i,j] = N[i,j] / sum_j N[i,j]`; unsupported geographic rows send mass to U. First observed exit E and algorithmic support U remain separate and absorbing. `p_h = e_origin @ P^h` for this one-day kernel. No observed intermediate validation position is fed back. Predictors: current cell only. No velocity, SST, wind, seasonal or fixed-regime conditioning.',
        'Five existing outer ID folds are reused. Each fit excludes the complete held-out IDs across R and D. No inner search is performed because lag=1 and epsilon=0 are fixed. B0/B1/B2 are newly fitted stopped-target controls. Old endpoint baseline scores are not a comparable leaderboard. M1 additionally uses downstream D information, so a difference is not attributable solely to iteration.',
        '## Primary held-out scores',
        'Lower S is better. S equals Brier for complete forecasts and otherwise treats U as an extra failed category: `S = 1 - 2*p_truth + sum(p_j^2) + u^2`. It is neither zero-one loss, percentage accuracy nor a worst-case physical completion bound. Complete-case Brier and common-complete scores are in summary.csv. All eligible cases remain in S.',
        markdown_table(summary, ['horizon_days', 'model', 'eligible_pairs', 'independent_ids', 'brier_failure_penalized', 'complete_forecast_pct', 'mean_unresolved_mass', 'max_unresolved_mass', 'zero_probability_pct']),
        '## Paired uncertainty',
        '200 whole-held-out-ID resamples within folds, conditional on saved fits. These intervals exclude refitting, lag selection, structural and source-interpolation uncertainty. Exploratory comparisons are not multiplicity-adjusted confirmatory tests.',
        markdown_table(intervals, ['horizon_days', 'comparison', 'delta_S', 'lower_95', 'upper_95']),
        '## Linear and quadratic spatial evaluation',
        'Brier is a quadratic probability score, not a geographic distance score. The added linear component is Energy Score: `ES = E||X-y|| - 0.5*E||X-Xprime||`. The quadratic component is `||mean(X)-y||^2`. Report components separately, plus the auxiliary reference `ES/100 + squared_mean_error/10000`. Its 100-km scale and equal weights are declared engineering references, not optimal values or a replacement primary criterion.',
        'Coordinates are WGS84 ECEF cell-centre coordinates; distances are Euclidean chords in km, not geodesic distances. Conditioning is on a complete forecast with positive in-D mass and observed in-D outcome. The geometric score is conditional on remaining in D; exit probability is evaluated separately by the full categorical score. No invented coordinate for E/U. No redistribution of U. Fair spatial comparisons use the identical common eligible subset across all four models; NA means unavailable, not zero error. Always read the subset size and individual availability.',
        'The corrected combination retains distributional propriety under its spatial assumptions. In contrast, direct expected linear-plus-squared distance can prefer a false midpoint to two real branches. Squared mean error alone cannot detect different spreads with the same mean. A new score does not guarantee convergence or alter the raw count estimate.',
        markdown_table(summary, ['horizon_days', 'model', 'spatial_individual_available_pct', 'spatial_common_pairs', 'energy_km_common', 'mean_squared_km2_common', 'linear_quadratic_reference_common']),
        '## Probability regions and exit',
        'State regions may include the OUTSIDE category; geographic regions contain cells only. Ties can make actual selected mass exceed nominal 90%. Compare hit rates with actual issued mass, disclose unavailable regions and inspect wet area rather than equating cell count with area. Region hit rate alone is not accuracy. With zero observed exits, positive-event exit calibration is not established.',
        markdown_table(summary, ['horizon_days', 'model', 'region90_available_pct', 'region90_hit_pct_available', 'mean_region90_mass', 'mean_region90_cells', 'geo90_available_pct', 'geo90_hit_pct_available', 'mean_outside_probability', 'observed_outside_pairs']),
        '## Source-backed illustrative maps',
        f'Outer fold 0, origin {default}, chosen solely by the maximum minimum 7/30-day fitting-ID support, ties by ascending cell ID. Every panel in a figure shares a probability scale. Observed panels contain matching held-out IDs only. Display land is a simplified frozen GSHHG mask; scientific geometry is unchanged. The full D is displayed; very small probabilities can be visually faint.',
        *images,
        '## Observational support, not predictive accuracy',
        markdown_table(totals, ['horizon_days', 'eligible_pairs', 'independent_ids']),
        markdown_table(long_support, ['horizon_days', 'departure_season', 'eligible_pairs', 'independent_ids']),
        'Long-horizon labels are audited, not scored here. A zero/absent cell-season or small independent-ID count must remain an explicit limitation. Many hourly windows overlap. These counts do not certify 365-day performance.',
        '## What is delivered and what remains',
        'Delivered: per-ID qualified counts and reason accounting, five fitted operators/state indexes, matched stopped controls, frozen held-out forecasts/scores, linear/quadratic auxiliary metrics, maps and fixed-fit paired intervals. No canonical values/columns changed; final-test reads are zero.',
        'Next: inspect incomplete support and direct-versus-composed/memory diagnostics; define the cross-horizon lag-selection rule before comparing 1/3/5/7 days and exact remainders. Then assess seasonal/shrinkage and fixed-regime extensions. No best lag, annual skill, grounding identification or universal oil/raft/container performance is claimed.',
        'Sources: [Data Contract v1.0](../../../docs/contract/data_contract_v1.0.xlsx); [Gneiting and Raftery (2007)](https://doi.org/10.1198/016214506000001437).',
    ]
    text = '\n\n'.join(sections)+'\n'
    paths.publish(run['results']/'REPORT.md', lambda stream: stream.write(text.encode()))
    html = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>M1 probability review</title>'
            '<style>body{font:16px system-ui;max-width:1250px;margin:32px auto;padding:16px;color:#182a3a}img{width:100%}p{line-height:1.6}</style>'
            '<h1>M1 fixed one-day prototype</h1><p>Development-only, pooled stopped forecasts. '
            'The observed panels use matching held-out IDs. Shared scales within each figure; OUTSIDE and unresolved remain visible. '
            'Read REPORT.md and summary.csv for support and validation limits.</p>'
            '<p><a href="REPORT.md">Full method and audit report</a> · <a href="summary.csv">Summary table</a></p>'
            '<img src="probability_7d.svg" alt="7-day predictions and observed outcomes">'
            '<img src="probability_30d.svg" alt="30-day predictions and observed outcomes"></html>')
    paths.publish(run['results']/'review.html', lambda stream: stream.write(html.encode()))
