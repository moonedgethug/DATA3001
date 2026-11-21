"""Render the reviewed regional-release tables without model execution."""
from pathlib import Path
import json
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import Normalize, TwoSlopeNorm
from matplotlib.cm import ScalarMappable
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import shape, box
from shapely.plotting import patch_from_polygon

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
WORK = ROOT / 'work_place'
NAVY = '#123c5a'
GREY = '#d9ddd9'
TEAL = '#147a74'


def polygons(g):
    if g.geom_type == 'Polygon':
        yield g
    elif hasattr(g, 'geoms'):
        for part in g.geoms:
            yield from polygons(part)


def main():
    summary = json.loads((OUT / 'summary.json').read_text())
    cells = pd.read_csv(OUT / 'release_cells.csv')
    grid = pd.read_parquet(OUT / 'display_grid.parquet')
    data = np.load(OUT / 'integration_by_cell.npz')
    edges_x, edges_y = data['lon_edges'], data['lat_edges']
    shape_grid = (len(edges_y) - 1, len(edges_x) - 1)
    assets = json.loads((WORK / 'configs/assets.json').read_text())['assets']
    def asset(name):
        return WORK / assets[name]['path']
    release = shape(json.loads(asset('release_R').read_text())['features'][0]['geometry'])
    domain = shape(json.loads(asset('transport_D').read_text())['features'][0]['geometry'])
    land = shapely.from_wkb(asset('land_mask_high').read_bytes())
    available = {f.name for f in font_manager.fontManager.ttflist}
    font = next(n for n in ['Arial Unicode MS', 'Noto Sans CJK SC', 'PingFang HK'] if n in available)
    plt.rcParams.update({'font.family': font, 'font.size': 10, 'axes.unicode_minus': False,
        'pdf.fonttype': 42, 'axes.labelcolor': NAVY, 'text.color': NAVY})

    def basemap(ax, extent, coastal_lines=False):
        ax.set_facecolor('#fbfcfd')
        for p in polygons(land.intersection(box(*extent))):
            if not coastal_lines:
                ax.add_patch(patch_from_polygon(p, facecolor=GREY, edgecolor='none', zorder=0))
            ax.plot(*p.exterior.xy, color='#77837d', lw=.45, zorder=5)
        for p in polygons(release):
            ax.plot(*p.exterior.xy, color=TEAL, lw=1.25, ls='--', zorder=6)
        for p in polygons(domain):
            ax.plot(*p.exterior.xy, color='#737f8b', lw=.9, ls=':', zorder=5)
        ax.set_xlim(extent[0], extent[2]); ax.set_ylim(extent[1], extent[3])
        ax.set_aspect(1 / math.cos(math.radians((extent[1] + extent[3]) / 2)))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{abs(x):g}°W'))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:g}°N'))
        ax.tick_params(labelsize=9)
        for spine in ax.spines.values():
            spine.set_color('#a6afb5')

    missing_geometries = []
    for row in cells[~cells.supported].itertuples():
        wet = box(row.lon_min, row.lat_min, row.lon_min + 1, row.lat_min + 1).intersection(release).difference(land)
        missing_geometries.append(wet)

    def hatch_missing(ax):
        for g in missing_geometries:
            for p in polygons(g):
                ax.add_patch(patch_from_polygon(p, facecolor='#f1e8cf', edgecolor='#856a30', hatch='////', lw=.6, zorder=8))

    # Main release-to-destination comparison; geographic grid is display only.
    fig, axes = plt.subplots(1, 3, figsize=(13.3, 6.8))
    fig.subplots_adjust(left=.055, right=.985, bottom=.27, top=.82, wspace=.16)
    initial = grid.area_release_initial.to_numpy().reshape(shape_grid) * 100
    endpoint = grid.area_release_day7.to_numpy().reshape(shape_grid) * 100
    change = grid.area_release_change.to_numpy().reshape(shape_grid) * 100
    max_probability = math.ceil(max(initial.max(), endpoint.max()) * 2) / 2
    max_change = math.ceil(np.abs(change).max() * 2) / 2
    norm = Normalize(0, max_probability)
    delta_norm = TwoSlopeNorm(0, -max_change, max_change)
    cmap = plt.get_cmap('YlOrRd').copy(); cmap.set_bad((0, 0, 0, 0))
    change_cmap = plt.get_cmap('PuOr_r').copy(); change_cmap.set_bad((0, 0, 0, 0))
    arrays = [initial, endpoint, change]
    titles = ['(a) 初始释放分布', '(b) 七天后综合终点分布', '(c) 七天后 − 初始分布']
    for i, (ax, values, title) in enumerate(zip(axes, arrays, titles)):
        basemap(ax, summary['main_view'])
        # No positive-probability display threshold: zero cells alone are masked.
        ax.pcolormesh(edges_x, edges_y, np.ma.masked_equal(values, 0),
            cmap=cmap if i < 2 else change_cmap, norm=norm if i < 2 else delta_norm,
            shading='flat', rasterized=True, zorder=2)
        if i == 0:
            hatch_missing(ax)
        ax.set_title(title, loc='left', fontsize=12, pad=12)
        ax.set_xticks([-80, -75, -70, -65]); ax.set_yticks([28, 32, 36, 40, 43])
        ax.text(.03, .96, '美国东岸', transform=ax.transAxes, va='top', color='#576765', fontsize=9)
    bar1 = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=fig.add_axes([.09, .19, .53, .022]), orientation='horizontal')
    bar1.set_label('每个 0.5° 显示网格的概率（%）；图(a)、(b)共用色标', labelpad=6)
    bar2 = fig.colorbar(ScalarMappable(norm=delta_norm, cmap=change_cmap), cax=fig.add_axes([.72, .19, .24, .022]), orientation='horizontal')
    bar2.set_label('概率变化（百分点）', labelpad=6)
    handles = [Line2D([], [], color=TEAL, ls='--', label='释放区域 R'),
        Line2D([], [], color='#737f8b', ls=':', label='研究域 D 的西边界'),
        Patch(facecolor='#f1e8cf', edgecolor='#856a30', hatch='////', label='无合格历史起点的水面')]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.51, .94), ncol=3, frameon=False, fontsize=10)
    fig.suptitle('R 区域释放后的七天综合去向', x=.055, ha='left', y=.992, fontsize=18)
    unresolved = summary['release']['unresolved_weight'] * 100
    outside_view = summary['outside_main_view']['area_release'] * 100
    fig.text(.055, .064, f'按 R 内水面面积分配各格权重；格内采用2001–2019年合格历史起点。可解析释放量：{100-unresolved:.2f}%；未解析：{unresolved:.2f}%。', fontsize=9.5)
    fig.text(.055, .027, f'着色表示整格概率，边界格可跨越 R 或海岸；陆地概率按海岸线另行统计。未重新归一化；主视窗外概率为{outside_view:.4f}%。', fontsize=9.5)
    for ext in ['png', 'pdf']:
        fig.savefig(OUT / f'figure_w12_regional_distribution_zh.{ext}', dpi=260, facecolor='white')
    plt.close(fig)

    # Source support and the release-weight sensitivity, using actual water geometry.
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 6.8))
    fig.subplots_adjust(left=.075, right=.97, bottom=.23, top=.82, wspace=.20)
    extent = (-81.5, 29.6, -72.5, 36.)
    count_norm = Normalize(0, math.ceil(cells.independent_drifters.max() / 50) * 50)
    weight_change = 100 * (cells.historical_origin_weight - cells.whole_R_release_weight)
    weight_limit = math.ceil(weight_change.abs().max())
    weight_norm = TwoSlopeNorm(0, -weight_limit, weight_limit)
    count_cmap = plt.get_cmap('YlGnBu')
    for ax in axes:
        basemap(ax, extent)
        ax.set_xticks([-81, -79, -77, -75, -73]); ax.set_yticks([30, 32, 34, 35.5])
    for row in cells.itertuples():
        wet = box(row.lon_min, row.lat_min, row.lon_min + 1, row.lat_min + 1).intersection(release).difference(land)
        difference = 100 * (row.historical_origin_weight - row.whole_R_release_weight)
        for p in polygons(wet):
            axes[0].add_patch(patch_from_polygon(p, facecolor=count_cmap(count_norm(row.independent_drifters)), edgecolor='#bdc8cf', lw=.5, zorder=2))
            axes[1].add_patch(patch_from_polygon(p, facecolor=change_cmap(weight_norm(difference)), edgecolor='#bdc8cf', lw=.5, zorder=2))
        if not wet.is_empty:
            label = wet.representative_point()
            color = 'white' if row.independent_drifters > .55 * count_norm.vmax else NAVY
            axes[0].text(label.x, label.y, str(row.independent_drifters), ha='center', va='center', fontsize=8.3, color=color, zorder=9)
    hatch_missing(axes[0]); hatch_missing(axes[1])
    axes[0].set_title('(a) 各格提供起点的独立漂流器数量', loc='left', fontsize=12, pad=10)
    axes[1].set_title('(b) 历史起点等权 − 水面面积权重', loc='left', fontsize=12, pad=10)
    cb = fig.colorbar(ScalarMappable(norm=count_norm, cmap=count_cmap), cax=fig.add_axes([.095, .17, .36, .022]), orientation='horizontal')
    cb.set_label('独立漂流器数量；同一漂流器可出现在多个格中')
    cb = fig.colorbar(ScalarMappable(norm=weight_norm, cmap=change_cmap), cax=fig.add_axes([.61, .17, .33, .022]), orientation='horizontal')
    cb.set_label('初始释放权重差异（百分点）')
    fig.suptitle('释放位置的数据支持与权重差异', x=.075, ha='left', y=.98, fontsize=17)
    fig.text(.075, .89, '2001–2019年 · 265,393条合格起点记录 · 338条独立漂流器 · 39个具有水面面积的1°网格', fontsize=10)
    fig.text(.075, .055, f'斜线标出两个没有合格历史起点的网格内水面，占总释放权重{unresolved:.2f}%。数字统计独立漂流器，不把小时记录数当作独立样本数。', fontsize=9.5)
    for ext in ['png', 'pdf']:
        fig.savefig(OUT / f'figure_w12_release_support_zh.{ext}', dpi=260, facecolor='white')
    plt.close(fig)

    # Same supported area, normalized explicitly for the sensitivity comparison.
    fig, axes = plt.subplots(1, 3, figsize=(13.3, 6.7))
    fig.subplots_adjust(left=.055, right=.985, bottom=.26, top=.80, wspace=.16)
    area = grid.area_supported_only_day7.to_numpy().reshape(shape_grid) * 100
    empirical = grid.historical_origins_day7.to_numpy().reshape(shape_grid) * 100
    delta = empirical - area
    sensitivity_norm = Normalize(0, math.ceil(max(area.max(), empirical.max()) * 2) / 2)
    delta_limit = math.ceil(np.abs(delta).max() * 4) / 4
    sensitivity_delta_norm = TwoSlopeNorm(0, -delta_limit, delta_limit)
    for i, (ax, values, title) in enumerate(zip(axes, [area, empirical, delta],
            ['(a) 水面面积加权：有起点的37格', '(b) 历史起点记录等权', '(c) 历史等权 − 面积加权'])):
        basemap(ax, summary['main_view'])
        ax.pcolormesh(edges_x, edges_y, np.ma.masked_equal(values, 0),
            cmap=cmap if i < 2 else change_cmap, norm=sensitivity_norm if i < 2 else sensitivity_delta_norm,
            shading='flat', rasterized=True, zorder=2)
        ax.set_title(title, loc='left', fontsize=11.5, pad=12)
        ax.set_xticks([-80,-75,-70,-65]);ax.set_yticks([28,32,36,40,43])
    cb=fig.colorbar(ScalarMappable(norm=sensitivity_norm,cmap=cmap),cax=fig.add_axes([.09,.18,.53,.022]),orientation='horizontal')
    cb.set_label('每个0.5°显示网格的概率（%）；图(a)、(b)共用色标')
    cb=fig.colorbar(ScalarMappable(norm=sensitivity_delta_norm,cmap=change_cmap),cax=fig.add_axes([.72,.18,.24,.022]),orientation='horizontal')
    cb.set_label('概率差异（百分点）')
    fig.suptitle('七天综合去向对释放权重的敏感性',x=.055,ha='left',y=.98,fontsize=17)
    fig.text(.055,.89,'同一冻结模型、同一组37个有历史起点的网格；两种释放分布均归一化为100%，用于单独比较权重的影响。',fontsize=10)
    fig.text(.055,.055,'图(a)明确条件于有历史起点的区域；主分析仍保留整个 R 中0.86%的未解析释放量，不作重新归一化。',fontsize=10)
    for ext in ['png','pdf']:
        fig.savefig(OUT/f'figure_w12_weight_sensitivity_zh.{ext}',dpi=260,facecolor='white')
    plt.close(fig)
    print('Rendered three figures as PNG and PDF.')


if __name__ == '__main__':
    main()
