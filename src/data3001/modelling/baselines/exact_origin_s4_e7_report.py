"""Matched E7 inference and local reports from already-frozen predictions."""
import html
import io

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle

from data3001.modelling.baselines.seasonal_information_s4_e3_inference import multiplier_summary


RESOLUTIONS = (1.0, 0.5)
MODELS = ('Annual', 'Exact')
METRICS = ('brier', 'h90', 'k90', 'area90', 'mass', 'zero', 'exit',
           'geographic_mass', 'exit_in_region')
KEY = ['id', 'origin_source_obs', 'horizon_days']
COLORS = ('#37677e', '#278464')
NAMES = {'Annual': 'Annual B2', 'Exact': 'Exact-position empirical'}


def evaluate(cases, cfg):
    """Return tables and paired ID-multiplier draws in RESOLUTIONS/METRICS order.

    The caller supplies complete, matched case rows after the prediction freeze.
    No source tracks, fitted models, neighbour index or outcomes are loaded here.
    """
    assert set(cases.resolution.unique()) == set(RESOLUTIONS)
    assert not cases.duplicated(['resolution', *KEY]).any()
    assert set(cases.horizon_days.unique()) == {7}
    ids = sorted(int(i) for i in cases.id.unique())
    id_index = {ident: index for index, ident in enumerate(ids)}
    multipliers = np.random.Generator(np.random.PCG64(cfg['bootstrap_seed'])).exponential(
        size=(cfg['bootstrap_draws'], len(ids)))
    summary, paired, by_origin, units, simulations = [], [], [], [], []
    reference = None
    columns = ['delta_' + metric for metric in METRICS]
    # Keep the shared helper's 1e-12 arithmetic checks dimensionless. Area is
    # rescaled back to km2 immediately after the multiplier calculation.
    scale = np.ones(len(METRICS))
    scale[METRICS.index('area90')] = 1e6
    tolerances = np.full(len(METRICS), 1e-12)
    tolerances[METRICS.index('area90')] = 1e-9
    for resolution in RESOLUTIONS:
        frame = cases.loc[cases.resolution.eq(resolution)].sort_values(KEY).reset_index(drop=True).copy()
        assert np.isfinite(frame.weight).all() and frame.weight.gt(0).all()
        assert abs(frame.weight.sum() - 1) <= 1e-12
        matched = frame[KEY + ['origin_cell_1', 'weight']]
        if reference is None:
            reference = matched
        else:
            pd.testing.assert_frame_equal(reference, matched, check_exact=True)
        for model in MODELS:
            values = frame[[model + '_' + metric for metric in METRICS]].to_numpy(float)
            assert np.isfinite(values).all()
            means = frame.weight.to_numpy() @ values
            row = dict(resolution=resolution, horizon_days=7, model=model,
                       pairs=len(frame), ids=frame.id.nunique(), origins=frame.origin_cell_1.nunique(),
                       observed_exit=float(frame.weight @ frame.observed_exit))
            row.update(zip(METRICS, means))
            summary.append(row)
        for metric in METRICS:
            # The stored exit-region flag is boolean. Paired indicator changes
            # are numeric -1/0/+1, so convert before subtraction.
            frame['delta_' + metric] = (frame['Exact_' + metric].to_numpy(dtype=float)
                                        - frame['Annual_' + metric].to_numpy(dtype=float))
        normalized = frame.copy()
        normalized[columns] = frame[columns].to_numpy() / scale
        point, sim = multiplier_summary(normalized, multipliers, id_index, columns,
                                        np.ones(len(frame), dtype=bool))
        point, sim = point * scale, sim * scale
        means = frame.groupby(['origin_cell_1', 'id'])[columns].mean().reset_index()
        units.append(means.assign(resolution=resolution))
        # Independent construction from the per-ID/per-origin empirical means.
        check = np.zeros_like(sim)
        independent_point = np.zeros(len(METRICS))
        for _, unit in means.groupby('origin_cell_1', sort=True):
            weights = multipliers[:, [id_index[int(i)] for i in unit.id]]
            weights = weights / weights.sum(axis=1, keepdims=True)
            check += np.einsum('rd,dm->rm', weights, unit[columns].to_numpy()) / frame.origin_cell_1.nunique()
            independent_point += unit[columns].mean().to_numpy() / frame.origin_cell_1.nunique()
        assert np.all(np.abs(check - sim) <= tolerances)
        assert np.all(np.abs(independent_point - point) <= tolerances)
        simulations.append(sim)
        low, high = np.quantile(sim, [.025, .975], axis=0, method='linear')
        upper = float(point[0] - np.quantile(sim[:, 0] - point[0], .05, method='linear'))
        assert abs(upper - (2 * point[0] - np.quantile(check[:, 0], .05, method='linear'))) <= 1e-12
        row = dict(resolution=resolution, horizon_days=7, is_primary=resolution == 1.0,
                   centered_brier_upper95=upper)
        for index, metric in enumerate(METRICS):
            row.update({f'delta_{metric}': point[index], f'{metric}_lower95': low[index],
                        f'{metric}_upper95': high[index]})
        row['brier_supported'] = bool(resolution == 1.0 and point[0] < -1e-12 and upper < 0)
        paired.append(row)
        for origin, group in frame.groupby('origin_cell_1', sort=True):
            weights = group.weight / group.weight.sum()
            row = dict(resolution=resolution, origin_cell_1=int(origin), pairs=len(group),
                       ids=group.id.nunique(), original_weight=float(group.weight.sum()))
            for model in MODELS:
                row.update({model + '_' + metric: float(weights @ group[model + '_' + metric])
                            for metric in METRICS})
            row.update({column: float(weights @ group[column]) for column in columns})
            by_origin.append(row)
    summary = pd.DataFrame(summary)
    paired = pd.DataFrame(paired)
    coarse = paired.loc[paired.resolution.eq(1.0)].iloc[0]
    fine = paired.loc[paired.resolution.eq(.5)].iloc[0]
    supported = bool(coarse.brier_supported)
    legacy = bool(coarse.delta_brier < -1e-12 and coarse.delta_h90 >= -1e-12 and coarse.delta_k90 <= 1e-12)
    fine_preserved = bool(fine.delta_brier <= 1e-12 and fine.delta_h90 >= -1e-12
                          and fine.delta_k90 <= 1e-12 and fine.delta_area90 <= 1e-9)
    recommend = supported and legacy and fine_preserved
    if recommend:
        result = 'Supported Brier gain with point-estimate quality preservation'
    elif coarse.delta_brier < -1e-12 and (not legacy or not fine_preserved):
        result = 'Brier improvement with an operational trade-off'
    else:
        result = 'Primary benefit unestablished'
    base = summary.loc[summary.resolution.eq(1.0) & summary.model.eq('Annual'), 'brier'].iloc[0]
    decision = pd.DataFrame([dict(
        primary_brier_supported=supported, legacy_quality_preserved=legacy,
        fine_quality_preserved=fine_preserved, recommend_replacement=recommend,
        delta_brier=float(coarse.delta_brier), relative_brier_change=float(coarse.delta_brier / base) if base else np.nan,
        conclusion=result, evidence='Previously inspected chronological development validation; fixed-fit conditional inference')])
    support = []
    one = cases.loc[cases.resolution.eq(1.0)]
    for metric in ['n', 'donor_ids', 'largest_id_share', 'farthest_m', 'cap_limited', 'tie_extra']:
        if metric in one:
            values = one[metric].to_numpy(float)
            assert np.isfinite(values).all()
            q = np.quantile(values, [0, .25, .5, .75, 1], method='linear')
            support.append(dict(diagnostic=metric, weighted_mean=float(one.weight @ values),
                                pair_mean=float(values.mean()), minimum=q[0], q25=q[1], median=q[2], q75=q[3], maximum=q[4]))
    tables = {'summary': summary, 'paired': paired, 'decision': decision,
              'per_origin': pd.DataFrame(by_origin), 'support': pd.DataFrame(support),
              'id_origin_differences': pd.concat(units, ignore_index=True),
              'draw_keys': pd.DataFrame([dict(resolution=r, metric=m, resolution_index=i, metric_index=j)
                                         for i, r in enumerate(RESOLUTIONS) for j, m in enumerate(METRICS)])}
    return tables, multipliers, np.stack(simulations), ids


def _as_frame(value):
    if isinstance(value, pd.DataFrame):
        return value
    if value is None:
        return pd.DataFrame()
    return pd.DataFrame([value] if isinstance(value, dict) else value)


def _coastlines(ax, land, bounds):
    if land is None:
        return
    from shapely.geometry import box
    clipped = land.intersection(box(*bounds))
    parts = list(clipped.geoms) if hasattr(clipped, 'geoms') else [clipped]
    for polygon in parts:
        if polygon.geom_type == 'Polygon':
            for ring in [polygon.exterior, *polygon.interiors]:
                x, y = ring.xy
                ax.plot(x, y, color='#777777', linewidth=.65, zorder=4)


def _example_figure(example, metadata):
    grid = example['grid'].set_index('cell', drop=False)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), layout='constrained')
    all_cells, maxima = [], []
    for model in MODELS:
        states, probabilities, mask = example[model]
        states, probabilities = np.asarray(states), np.asarray(probabilities)
        geographic = (states >= 0) & (probabilities > 0)
        all_cells.extend(states[geographic].tolist())
        maxima.extend(probabilities[geographic].tolist())
    if all_cells:
        shown = grid.loc[sorted(set(all_cells))]
        x = np.r_[shown.lon_min, shown.lon_min + .5, example['lon']]
        y = np.r_[shown.lat_min, shown.lat_min + .5, example['lat']]
    else:
        x, y = np.array([example['lon']]), np.array([example['lat']])
    tx, ty = example.get('truth_lon', np.nan), example.get('truth_lat', np.nan)
    if np.isfinite(tx) and np.isfinite(ty):
        x, y = np.r_[x, tx], np.r_[y, ty]
    padding = max(.25, .04 * max(float(np.ptp(x)), float(np.ptp(y))))
    bounds = (float(x.min() - padding), float(y.min() - padding),
              float(x.max() + padding), float(y.max() + padding))
    norm = Normalize(vmin=0, vmax=max(maxima, default=1.0))
    for ax, model in zip(axes, MODELS):
        states, probabilities, mask = (np.asarray(v) for v in example[model])
        geographic = (states >= 0) & (probabilities > 0)
        rows = grid.loc[states[geographic]]
        patches = [Rectangle((row.lon_min, row.lat_min), .5, .5) for row in rows.itertuples()]
        coll = PatchCollection(patches, cmap='YlGnBu', norm=norm, edgecolor='#ffffff', linewidth=.25)
        coll.set_array(probabilities[geographic])
        ax.add_collection(coll)
        for row in grid.loc[states[(states >= 0) & mask.astype(bool)]].itertuples():
            ax.add_patch(Rectangle((row.lon_min, row.lat_min), .5, .5, fill=False,
                                   edgecolor='#d1642b', linewidth=1.1, zorder=3))
        _coastlines(ax, metadata.get('land'), bounds)
        ax.scatter(example['lon'], example['lat'], marker='*', s=110, color='#ad2f87',
                   edgecolors='white', linewidths=.5, label='Exact departure', zorder=6)
        if np.isfinite(tx) and np.isfinite(ty):
            ax.scatter(tx, ty, marker='x', s=65, color='#b41323', linewidths=2,
                       label='Observed day-7 endpoint', zorder=7)
        exit_mass = float(probabilities[states == -2].sum())
        geographic_mass = float(probabilities[(states >= 0) & mask.astype(bool)].sum())
        ax.set(xlim=(bounds[0], bounds[2]), ylim=(bounds[1], bounds[3]), xlabel='Longitude (degrees)',
               ylabel='Latitude (degrees)', title=f'{NAMES[model]}\nExit {exit_mass:.1%} | geographic region mass {geographic_mass:.1%}')
        ax.set_aspect(1 / max(.1, np.cos(np.deg2rad(np.mean(y)))))
        ax.grid(alpha=.15)
        ax.legend(fontsize=7, loc='best')
    fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap='YlGnBu'), ax=axes, label='Probability per 0.5-degree cell', shrink=.85)
    fig.suptitle(f"Same query | ID {int(example['id'])}, source {int(example['origin_source_obs'])}, "
                 f"original cell {int(example['origin_cell_1'])}\nOrange outlines: nominal 90% region; exit is shown separately")
    return fig


def report(paths, directory, tables, choices, inner_curves, examples, metadata):
    """Publish deterministic PNG/HTML/Markdown artifacts under the supplied run."""
    metadata = metadata or {}
    choices, curves = _as_frame(choices), _as_frame(inner_curves)
    images = []

    def save(name, figure):
        data = io.BytesIO()
        figure.savefig(data, format='png', dpi=145, facecolor='white', metadata={'Software': 'DATA3001 E7'})
        plt.close(figure)
        paths.publish(directory / name, lambda stream: stream.write(data.getvalue()))
        images.append(name)

    if not curves.empty and {'k', 'brier'}.issubset(curves):
        fig, ax = plt.subplots(figsize=(9, 4), layout='constrained')
        fold_column = next((name for name in ['fold', 'role', 'window'] if name in curves), None)
        groups = curves.groupby(fold_column, sort=True) if fold_column else [('pooled', curves)]
        for label, frame in groups:
            frame = frame.sort_values('k')
            ax.plot(frame.k, frame.brier, marker='o', label=str(label), linewidth=2.5 if label == 'pooled' else 1.2)
        choice_column = next((name for name in ['selected_k', 'k', 'k7'] if name in choices), None)
        if choice_column and len(choices):
            selected = int(choices[choice_column].iloc[0])
            ax.axvline(selected, color='#333', linestyle='--', label=f'Selected k = {selected:,}')
        ticks = sorted(curves.k.unique())
        ax.set_xscale('log')
        ax.set_xticks(ticks, [f'{int(k):,}' for k in ticks])
        ax.set(xlabel='Neighbour-pair count k', ylabel='Inner 1-degree Brier',
               title='Training-period selection | 100-km cap, equal pair votes')
        ax.legend(fontsize=9)
        save('inner_selection.png', fig)

    fields = [('brier', 'Brier', 1), ('h90', 'Actual hits (%)', 100),
              ('k90', '90% region cells', 1), ('area90', '90% wet area (km²)', 1)]
    fig, axes = plt.subplots(2, 4, figsize=(15, 7), layout='constrained')
    for i, resolution in enumerate(RESOLUTIONS):
        frame = tables['summary'].loc[tables['summary'].resolution.eq(resolution)].set_index('model').loc[list(MODELS)]
        for ax, (metric, title, factor) in zip(axes[i], fields):
            values = frame[metric].to_numpy() * factor
            bars = ax.bar(['B2', 'Exact position'], values, color=COLORS)
            ax.bar_label(bars, fmt='%.5f' if metric == 'brier' else '%.2f', fontsize=8)
            ax.set(title=f'{resolution:g}° | {title}', ylim=(0, max(float(values.max()) * 1.22, .01)))
            ax.tick_params(axis='x', labelsize=9)
    fig.suptitle('Matched seven-day forecasts | same cases and equal-ID/equal-origin evaluation')
    save('matched_metrics.png', fig)

    fig, axes = plt.subplots(1, 4, figsize=(15, 4.2), layout='constrained')
    for ax, (metric, title, factor) in zip(axes, fields):
        for i, resolution in enumerate(RESOLUTIONS):
            row = tables['paired'].loc[tables['paired'].resolution.eq(resolution)].iloc[0]
            ax.plot([row[metric + '_lower95'] * factor, row[metric + '_upper95'] * factor], [i, i], color=COLORS[0], linewidth=3)
            ax.scatter(row['delta_' + metric] * factor, i, color=COLORS[1], zorder=3)
            if metric == 'brier' and resolution == 1.0:
                ax.scatter(row.centered_brier_upper95, i + .13, marker='|', s=140, color='#a85034', label='Primary one-sided upper')
        ax.axvline(0, linestyle='--', color='gray')
        ax.set(yticks=[0, 1], yticklabels=['1° primary', '0.5° secondary'], ylim=(-.4, 1.4),
               title=title.replace('Actual hits (%)', 'Hit difference (pp)'))
        if metric == 'brier':
            ax.legend(fontsize=7)
    fig.suptitle('Exact-position minus B2 | paired estimates and conditional 95% intervals')
    save('paired_differences.png', fig)

    if not tables.get('per_origin', pd.DataFrame()).empty:
        coarse = tables['per_origin'].loc[tables['per_origin'].resolution.eq(1.0)].sort_values('origin_cell_1')
        fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout='constrained')
        for ax, metric, title, factor in [(axes[0], 'brier', 'Brier difference', 1), (axes[1], 'h90', 'Hit difference (pp)', 100)]:
            values = coarse['delta_' + metric].to_numpy() * factor
            ax.bar(np.arange(len(coarse)), values, color=COLORS[1])
            ax.axhline(0, color='gray', linewidth=1)
            ax.set_xticks(np.arange(len(coarse)), coarse.origin_cell_1.astype(str), rotation=90, fontsize=7)
            ax.set(xlabel='Original 1-degree origin cell', ylabel=title)
        fig.suptitle('All original origin cells | descriptive matched changes')
        save('origin_changes.png', fig)

    for index, example in enumerate(examples or []):
        save(f'forecast_example_{index + 1:02d}.png', _example_figure(example, metadata))

    title = 'Exact-position empirical Markov transitions'
    decision = tables['decision'].iloc[0]
    paragraph = ('Seven-day forecasts use exact departure coordinates and equal votes from nearby historical starts, '
                 'with a fixed 100-km limit. Historical endpoints are not moved. The selected neighbour count uses only '
                 'internal training-period validation. Both methods face the same 2020–2022 cases. '
                 'The 1-degree comparison is primary; 0.5-degree output is a matched secondary view. '
                 'B2 at 0.5 degrees is re-tabulated from original endpoints, not a four-way split of coarse probability.')
    limits = ('The outer period has been inspected in earlier development. Intervals condition on the fitted models and '
              'observed origins; they do not include all refitting or common ocean-forcing uncertainty. '
              'Point-estimate quality preservation is not proof of statistical noninferiority. '
              'Maps show empirical probability aggregated into cells, not a smooth probability density. '
              'Orange boundaries include all cutoff ties; exit, when admitted, contributes to the nominal 90% set '
              'but has no geographic polygon. Wet area follows the frozen full-cell water-area convention.')
    sections = [('Selected neighbour count', choices), ('Matched metrics', tables['summary']),
                ('Paired differences and intervals', tables['paired']), ('Contract decisions', tables['decision']),
                ('Neighbour support', tables.get('support', pd.DataFrame())),
                ('Changes by original origin', tables.get('per_origin', pd.DataFrame()))]
    content = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
               f'<title>{title}</title><style>',
               'body{font:16px system-ui;max-width:1280px;margin:30px auto;padding:0 20px;color:#253944;line-height:1.55}',
               'img{width:100%;height:auto}section{overflow:auto;margin:24px 0}table{border-collapse:collapse;font-size:12px}',
               'td,th{padding:7px;border-bottom:1px solid #ddd;white-space:nowrap}th{background:#edf3f5}',
               '.decision{background:#eef5f1;padding:16px;border-left:4px solid #278464}.limits{color:#53636a}',
               '</style></head><body>', f'<h1>{title}</h1><p>{paragraph}</p>',
               '<div class="decision"><strong>' + html.escape(str(decision.conclusion)) + '</strong><br>',
               f'Primary Brier evidence: {bool(decision.primary_brier_supported)}; ',
               f'1° quality preserved: {bool(decision.legacy_quality_preserved)}; ',
               f'0.5° quality preserved: {bool(decision.fine_quality_preserved)}; ',
               f'default replacement criterion: {bool(decision.recommend_replacement)}.</div>']
    for name in images:
        content.append(f'<figure><img src="{name}" alt="{html.escape(name.replace("_", " "))}"></figure>')
    markdown = '# ' + title + '\n\n' + paragraph + '\n\n' + str(decision.conclusion) + '\n\n'
    for heading, table in sections:
        if table.empty:
            continue
        content.append('<section><h2>' + html.escape(heading) + '</h2>' + table.to_html(index=False, float_format=lambda value: f'{value:.8g}') + '</section>')
        markdown += '## ' + heading + '\n\n```csv\n' + table.to_csv(index=False) + '```\n\n'
    content.append('<p class="limits">' + limits + '</p></body></html>')
    markdown += '\n' + limits + '\n'
    paths.publish(directory / 'review.html', lambda stream: stream.write(''.join(content).encode('utf-8')))
    paths.publish(directory / 'REPORT.md', lambda stream: stream.write(markdown.encode('utf-8')))
