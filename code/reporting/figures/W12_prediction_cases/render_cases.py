"""Plot existing seven-day forecast parameters; never fit, infer, sample or score.

Run from DATA3001:
  work_place/.venv/bin/python 'Final Report/figures/W12_prediction_cases/render_cases.py'
The raster evaluates the stored mixture formula solely for display. Its units
are density in the model's east/north displacement plane, not cell probability.
"""

from pathlib import Path
import hashlib
import json
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
from pyproj import Geod, Transformer
import shapely
from shapely.geometry import box, shape, Point
from shapely.plotting import patch_from_polygon

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
WORK = ROOT / 'work_place'
RUN = WORK / 'results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1'
GEOD = Geod(ellps='WGS84')
INVERSE = Transformer.from_crs(
    '+proj=laea +lon_0=-75 +lat_0=35 +ellps=WGS84 +units=m',
    'EPSG:4326', always_xy=True)
SOURCES = {}


def source(path, expected=None):
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected is not None:
        assert checksum == expected, path
    SOURCES[str(path.relative_to(ROOT))] = checksum
    return path


def polygons(geometry):
    if geometry.geom_type == 'Polygon':
        yield geometry
    elif hasattr(geometry, 'geoms'):
        for child in geometry.geoms:
            yield from polygons(child)


def ellipse(region):
    angles = np.linspace(0, 2 * np.pi, 361)
    axes = np.sqrt(np.asarray(region['eigenvalues']) * region['cutoff'])
    points = np.asarray(region['centre']) + (
        np.column_stack([np.cos(angles), np.sin(angles)]) * axes
    ) @ np.asarray(region['eigenvectors']).T
    return np.column_stack(INVERSE.transform(points[:, 0] * 1000, points[:, 1] * 1000))


def display_density(origin, weights, means, covariances, extent, count=500):
    west, south, east, north = extent
    lon, lat = np.meshgrid(np.linspace(west, east, count), np.linspace(south, north, count))
    azimuth, _, distance = GEOD.inv(
        np.full(lon.size, origin[0]), np.full(lon.size, origin[1]), lon.ravel(), lat.ravel())
    vectors = np.column_stack([np.sin(np.radians(azimuth)), np.cos(np.radians(azimuth))])
    vectors *= distance[:, None] / 1000
    density = np.zeros(lon.size)
    for weight, mean, covariance in zip(weights, means, covariances):
        delta = vectors - mean
        quadratic = np.einsum('ni,ij,nj->n', delta, np.linalg.inv(covariance), delta)
        density += weight * np.exp(-quadratic / 2) / (2 * np.pi * np.sqrt(np.linalg.det(covariance)))
    return lon, lat, density.reshape(lon.shape)


def main():
    website_path = ROOT / 'sites/ocean-drifter-prototype/dist/assets/pt3/data.json'
    website = json.loads(source(website_path).read_text())
    expected = website['sources']
    parameter_path = RUN / 'C_outer/K22/parameters.npz'
    score_path = RUN / 'C_outer/outer_score/N65536_M65536/scores.parquet'
    target_path = WORK / 'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/outer_targets.parquet'
    for path in [parameter_path, score_path, target_path]:
        source(path, expected[str(path.relative_to(WORK))])
    parameters = np.load(parameter_path)
    manifest = json.loads(source(RUN / 'C_outer/K22/manifest.json').read_text())
    assert manifest['parameters']['sha256'] == SOURCES[str(parameter_path.relative_to(ROOT))]
    assert manifest['parameter_units']['mu'] == 'displacement_km'
    roster_path = WORK / 'results/deliverables/conditional_mdn_s5_e3/fixed_examples.json'
    roster = json.loads(source(roster_path).read_text())['examples']
    western = min(roster, key=lambda e: parameters['origins'][e['position'], 0])
    northern = max(roster, key=lambda e: parameters['origins'][e['position'], 1])
    origins = parameters['origins']
    southwest_indices = np.flatnonzero((origins[:, 0] < -77) & (origins[:, 1] < 32.75))
    _, _, southwest_distances = GEOD.inv(
        np.full(len(southwest_indices), -79.), np.full(len(southwest_indices), 31.375),
        origins[southwest_indices, 0], origins[southwest_indices, 1])
    southwest_position = int(southwest_indices[np.argmin(southwest_distances)])
    southwest = {'number': None, 'position': southwest_position,
                 'key': parameters['query_keys'][southwest_position].tolist()}
    examples = [roster[0], western, northern, southwest]
    positions = [e['position'] for e in examples]
    assert positions == [0, 3088, 24705, 12820]
    scores = pd.read_parquet(score_path, filters=[('K', '=', 22), ('position', 'in', positions)])
    targets = pd.read_parquet(target_path, filters=[('origin_source_obs', 'in', [e['key'][1] for e in examples])],
        columns=['id', 'origin_source_obs', 'horizon_days', 'origin_time_UTC', 'endpoint_lon', 'endpoint_lat', 'outside'])
    registry = json.loads(source(WORK / 'configs/assets.json').read_text())['assets']

    def asset(name):
        row = registry[name]
        return source(WORK / row['path'], row['sha256'])

    release = shape(json.loads(asset('release_R').read_text())['features'][0]['geometry'])
    domain = shape(json.loads(asset('transport_D').read_text())['features'][0]['geometry'])
    land = shapely.from_wkb(asset('land_mask_intermediate').read_bytes())
    available = {font.name for font in font_manager.fontManager.ttflist}
    font = next(name for name in ['Arial Unicode MS', 'Noto Sans CJK SC', 'PingFang HK'] if name in available)
    plt.rcParams.update({'font.family': font, 'font.size': 10, 'axes.unicode_minus': False, 'pdf.fonttype': 42})
    fig, axes = plt.subplots(2, 2, figsize=(11.6, 12.8))
    axes = axes.ravel()
    fig.subplots_adjust(left=.065, right=.985, bottom=.18, top=.88, wspace=.14, hspace=.24)
    extent = (-81.5, 28, -68.5, 39)
    norm = LogNorm(vmin=1e-8, vmax=1e-3)
    cmap = plt.get_cmap('YlOrRd').copy()
    cmap.set_under('#f4f8fb')
    titles = ['(a) 东南侧外海起点', '(b) 西侧近岸起点', '(c) 东北侧外海起点', '(d) 西南侧起点']
    case_records = []

    def basemap(ax, bounds, ticks=True):
        ax.set_facecolor('#f4f8fb')
        for polygon in polygons(land.intersection(box(*bounds))):
            ax.add_patch(patch_from_polygon(polygon, facecolor='#dcddd8', edgecolor='#858c87', linewidth=.5, zorder=1))
        for geometry, color, style in [(release, '#297d87', '--'), (domain, '#7e828a', ':')]:
            for polygon in polygons(geometry):
                ax.plot(*polygon.exterior.xy, color=color, linestyle=style, linewidth=.9, zorder=4)
        ax.set_xlim(bounds[0], bounds[2]); ax.set_ylim(bounds[1], bounds[3])
        ax.set_aspect(1 / math.cos(math.radians((bounds[1] + bounds[3]) / 2)))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{abs(x):g}°W'))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:g}°N'))
        ax.tick_params(labelsize=8)
        if ticks:
            ax.set_xticks([-80, -75, -70]); ax.set_yticks([28, 32, 36, 39])
        for spine in ax.spines.values():
            spine.set_color('#a1a8ad')

    for index, (ax, entry, title) in enumerate(zip(axes, examples, titles)):
        pos = entry['position']
        key = entry['key']
        assert parameters['query_keys'][pos].tolist() == key
        row = scores[scores.position.eq(pos)].iloc[0]
        assert [int(row.id), int(row.origin_source_obs), int(row.horizon_days)] == key
        target = targets[(targets.id.eq(key[0])) & (targets.origin_source_obs.eq(key[1])) & (targets.horizon_days.eq(7))]
        assert len(target) == 1 and not bool(target.iloc[0].outside)
        target = target.iloc[0]
        origin = parameters['origins'][pos]
        truth = [float(target.endpoint_lon), float(target.endpoint_lat)]
        assert release.covers(Point(*origin))
        weights, means, covariances = parameters['pi'][pos], parameters['mu'][pos], parameters['cov'][pos]
        assert np.isclose(weights.sum(), 1, atol=1e-12) and np.all(weights >= 0)
        assert np.all(np.linalg.eigvalsh(covariances) > 0)
        region = json.loads(row.region_json)['region']
        assert np.isclose(region['area_km2'], row.area90_km2)
        boundary = ellipse(region)
        basemap(ax, extent)
        x, y, density = display_density(origin, weights, means, covariances, extent)
        # An unnormalised geographic rendering of density in each origin's displacement plane.
        # Density over land is retained; coastlines remain visible above the raster.
        raster = ax.pcolormesh(x, y, np.ma.masked_less(density, 1e-8), cmap=cmap, norm=norm, shading='auto', rasterized=True, zorder=2)
        for polygon in polygons(land.intersection(box(*extent))):
            ax.plot(*polygon.exterior.xy, color='#858c87', linewidth=.5, zorder=3)
        ax.plot(*boundary.T, color='#334b68', linewidth=1.4, zorder=5)
        ax.scatter(*origin, marker='o', facecolor='white', edgecolor='black', s=43, linewidth=1.2, zorder=7)
        ax.scatter(*truth, marker='x', color='#0354b4', s=54, linewidth=1.6, zorder=8)
        ax.set_title(title + f'\n{abs(origin[0]):.3f}°W，{origin[1]:.3f}°N', loc='left', fontsize=11, pad=10)
        ax.text(.04, .95, '美国东岸', transform=ax.transAxes, fontsize=9, color='#596469', va='top')
        ax.text(.97, .02, f'90%区域：{row.area90_km2:,.0f} km²', transform=ax.transAxes, ha='right', fontsize=9,
                bbox={'facecolor':'white', 'alpha':.9, 'edgecolor':'none', 'pad':3}, zorder=10)
        if index == 1:
            zoom_extent = (-78.45, 33.4, -77.15, 34.55)
            inset = ax.inset_axes([.55, .16, .43, .38])
            basemap(inset, zoom_extent, ticks=False)
            zx, zy, zd = display_density(origin, weights, means, covariances, zoom_extent, count=250)
            inset.pcolormesh(zx, zy, np.ma.masked_less(zd, 1e-8), cmap=cmap, norm=norm, shading='auto', rasterized=True, zorder=2)
            for polygon in polygons(land.intersection(box(*zoom_extent))):
                inset.plot(*polygon.exterior.xy, color='#858c87', linewidth=.5, zorder=3)
            inset.plot(*boundary.T, color='#334b68', linewidth=1, zorder=5)
            inset.scatter(*origin, facecolor='white', edgecolor='black', s=29, zorder=7)
            inset.scatter(*truth, marker='x', color='#0354b4', s=35, zorder=8)
            inset.set_title('近岸局部放大', fontsize=8, pad=4)
            inset.set_xticks([-78, -77.5]); inset.set_yticks([33.5, 34, 34.5]); inset.tick_params(labelsize=6)
        case_records.append({'source_case': entry['number'], 'position': pos, 'key': key,
            'origin': origin.tolist(), 'origin_time_UTC': str(target.origin_time_UTC), 'truth': truth,
            'weights_sum': float(weights.sum()), 'display_grid_peak_density': float(density.max()),
            'energy_km': float(row.energy_km), 'observed_inside_region90': bool(row.h90),
            'area90_km2': float(row.area90_km2), 'land_mass': float(row.land_mass),
            'outside_D_mass': float(row.outside_D_mass), 'model_mass90': float(row.model_mass90),
            'saved_ellipse': region})
    anchor = website['models']['mdn22']['map']
    assert anchor['sourceKey'] == case_records[0]['key']
    assert np.allclose(anchor['origin'], case_records[0]['origin'])
    assert np.allclose(anchor['truth'], case_records[0]['truth'])
    fig.suptitle('同一个七天模型，不同起点的去向分布', fontsize=16, y=.965)
    fig.text(.5, .935, '22成分混合密度网络 · 已保存的开发验证预测 · 四图使用相同坐标范围和色标', ha='center', fontsize=10, color='#52616b')
    color_ax = fig.add_axes([.26, .115, .48, .014])
    colorbar = fig.colorbar(raster, cax=color_ax, orientation='horizontal', extend='min', ticks=[1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3])
    colorbar.set_label('模型位移平面概率密度（km⁻²，对数色标）', fontsize=10)
    fig.legend(handles=[
        Line2D([0], [0], marker='o', color='none', markerfacecolor='white', markeredgecolor='black', label='真实起点'),
        Line2D([0], [0], marker='x', color='#0354b4', linestyle='none', label='七天后观测终点'),
        Line2D([0], [0], color='#334b68', label='已保存的90%预测椭圆'),
        Line2D([0], [0], color='#297d87', linestyle='--', label='起点区域 R'),
        Line2D([0], [0], color='#7e828a', linestyle=':', label='研究域 D 的西边界')],
        loc='lower center', bbox_to_anchor=(.5, .036), ncol=3, fontsize=9, frameon=False)
    fig.text(.5, .017, '密度低于10⁻⁸的部分留白；未裁剪或重新归一化预测分布。D的完整范围见图2。', ha='center', fontsize=9, color='#52616b')
    for suffix in ['png', 'pdf']:
        fig.savefig(OUT / f'figure_w12_four_cases_zh.{suffix}', dpi=240, facecolor='white')
    plt.close(fig)
    provenance = {'date':'2026-11-21', 'model':'Mixture Density Network, 22 Components',
        'selection':'Original fixed example 1, westernmost and northernmost origins among the original 12 fixed examples; plus the saved southwest development origin closest to (-79,31.375). Both rules fixed before reading corresponding scores/shapes.',
        'southwest_selection':{'anchor':[-79,31.375], 'quadrant':'longitude < -77, latitude < 32.75, inside R',
            'candidate_queries':len(southwest_indices), 'distance_m':float(southwest_distances.min()),
            'original_twelve_case':False},
        'operation':'Read saved forecast parameters and saved scores; evaluate mixture formula for visualisation only. No inference, sampling, scoring, fitting or final-test access.',
        'density_units':'km^-2 in each origin-centred east/north geodesic displacement plane; not geographic area density or per-cell probability.',
        'display_extent':extent, 'normalisation':'Original 22 weights retained, no land masking or viewport renormalisation.',
        'sources':SOURCES, 'cases':case_records}
    (OUT / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'cases':len(case_records), 'positions':positions, 'sources_checked':len(SOURCES), 'output':str(OUT)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
