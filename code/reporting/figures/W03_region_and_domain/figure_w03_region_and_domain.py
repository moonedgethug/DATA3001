"""Draw saved screening windows and frozen R/D geometry; no trajectory analysis.

Run from DATA3001:
    work_place/.venv/bin/python 'Final Report/figures/W03_region_and_domain/figure_w03_region_and_domain.py'
"""

from pathlib import Path
import ast
import hashlib
import json
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import shapely
from shapely.geometry import Polygon, box, shape
from shapely.plotting import patch_from_polygon

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PROJECT = ROOT / "work_place"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assignment(path, name):
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    raise ValueError(f"Missing {name} in {path}")


def parts(geom):
    if geom.geom_type == "Polygon":
        yield geom
    elif hasattr(geom, "geoms"):
        for item in geom.geoms:
            yield from parts(item)


def main():
    registry = json.loads((PROJECT / "configs/assets.json").read_text())["assets"]
    sources = {}

    def asset(name):
        p = PROJECT / registry[name]["path"]
        actual = sha(p)
        if actual != registry[name]["sha256"]:
            raise ValueError(f"Checksum mismatch: {name}")
        sources[name] = {"path": str(p.relative_to(ROOT)), "sha256": actual}
        return p

    def geo(name):
        data = json.loads(asset(name).read_text())
        return shape(data["features"][0]["geometry"])

    region = geo("release_R")
    domain = geo("transport_D")
    envelope = geo("acquisition_envelope")
    land = shapely.from_wkb(asset("land_mask_intermediate").read_bytes())
    screening = PROJECT / "archive/region_screening_6h"
    region_source = screening / "region_data_audit.py"
    segment_source = screening / "gulf_stream_segment_audit.py"
    # Read literal geometry definitions without importing or running the audits.
    definitions = assignment(region_source, "REGIONS")
    corridor = None
    for key, value in zip(definitions.keys, definitions.values):
        if ast.literal_eval(key) == "Gulf Stream Corridor":
            corridor = Polygon(ast.literal_eval(value.args[0]))
    if corridor is None:
        raise ValueError("Gulf Stream corridor not found")
    definitions = assignment(segment_source, "SEGMENTS")
    windows = {}
    for key, value in zip(definitions.keys, definitions.values):
        bounds = [ast.literal_eval(a) for a in value.args[0].args]
        windows[ast.literal_eval(key)] = corridor.intersection(box(*bounds))
    assert windows["Southern Coastal Segment"].equals_exact(region, 1e-9)
    assert region.is_valid and domain.is_valid and domain.covers(region)
    assert tuple(domain.bounds) == (-81, 20, -8, 55)
    for p in [region_source, segment_source]:
        sources[p.name] = {"path": str(p.relative_to(ROOT)), "sha256": sha(p)}

    available = {f.name for f in font_manager.fontManager.ttflist}
    font = next(f for f in ["Arial Unicode MS", "Noto Sans CJK SC", "PingFang HK"] if f in available)
    plt.rcParams.update({"font.family": font, "axes.unicode_minus": False,
                         "svg.fonttype": "none", "pdf.fonttype": 42})
    colours = ["#187f67", "#bf622a", "#7558a6"]
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 4.4), gridspec_kw={"width_ratios": [1, 1.45]})
    fig.subplots_adjust(left=.055, right=.98, top=.85, bottom=.22, wspace=.18)
    extents = [(-87, 22, -57, 45), (-91, 11, 1, 63)]
    for ax, (west, south, east, north) in zip(axes, extents):
        ax.set_facecolor("#edf4f7")
        for poly in parts(land.intersection(box(west, south, east, north))):
            ax.add_patch(patch_from_polygon(poly, facecolor="#e3dfd6", edgecolor="#8c938e", linewidth=.35, zorder=2))
        ax.set(xlim=(west, east), ylim=(south, north))
        ax.set_aspect(1 / math.cos(math.radians((south+north)/2)))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{abs(v):g}°W" if v else "0°"))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}°N"))
        ax.grid(color="#afbdc5", linewidth=.45, alpha=.65)
        ax.tick_params(labelsize=9)
        for spine in ax.spines.values():
            spine.set_color("#89969d")

    ax = axes[0]
    ax.set_title("(a) Gulf Stream 三个候选区", loc="left", fontsize=10.5, pad=10)
    for geom, colour in zip(windows.values(), colours):
        ax.add_patch(patch_from_polygon(geom, facecolor=colour, edgecolor=colour, alpha=.26, linewidth=1.4, zorder=3))
    for label, xy, target, colour in [
        ("南段（R）", (-76.5, 32.7), (-83.5, 31), colours[0]),
        ("中段\nCape Hatteras", (-72, 37), (-82.5, 38.9), colours[1]),
        ("北段", (-65.5, 40.8), (-63.5, 44), colours[2]),
    ]:
        ax.annotate(label, xy=xy, xytext=target, ha="center", fontsize=8.5, color=colour,
                    arrowprops={"arrowstyle": "-", "color": colour, "lw": .9}, zorder=5)
    ax.text(-83.6, 26.3, "Florida", rotation=65, color="#56616a", fontsize=9)
    ax.text(-76.5, 24.2, "Bahamas", color="#56616a", fontsize=9)
    ax.set_xticks([-85, -75, -65, -60])
    ax.set_yticks([25, 30, 35, 40, 45])

    ax = axes[1]
    ax.set_title("(b) 起点区域 R 与运动范围 D", loc="left", fontsize=10.5, pad=10)
    ax.add_patch(patch_from_polygon(domain, facecolor="#437da4", edgecolor="#2d668d", alpha=.13, linewidth=0, zorder=1))
    for geom, colour, style, width in [(domain, "#2d668d", "-", 1.7), (envelope, "#7b7f83", "--", 1.2)]:
        x, y = geom.exterior.xy
        ax.plot(x, y, color=colour, linestyle=style, linewidth=width, zorder=4)
    ax.add_patch(patch_from_polygon(region, facecolor=colours[0], edgecolor=colours[0], alpha=.8, linewidth=1.0, zorder=5))
    ax.annotate("R", xy=(-77, 33), xytext=(-84, 43), color=colours[0], fontsize=14,
                arrowprops={"arrowstyle": "-", "color": colours[0]}, zorder=5)
    ax.text(-44.5, 39, "D", fontsize=23, color="#2d668d", ha="center")
    ax.text(-44.5, 34, "20°–55°N\n81°–8°W", fontsize=10, ha="center", color="#2d668d")
    ax.set_xticks([-90, -75, -60, -45, -30, -15, 0])
    ax.set_yticks([15, 25, 35, 45, 55, 60])

    fig.suptitle("区域选择与研究边界", fontsize=13, y=.97)
    handles = [Patch(facecolor=c, alpha=.5, label=n) for c, n in zip(colours, ["南段试验区 R", "中段候选区", "北段候选区"])]
    handles += [Line2D([0], [0], color="#2d668d", lw=1.7, label="运动范围 D"),
                Line2D([0], [0], color="#7b7f83", ls="--", lw=1.2, label="数据获取范围")]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5,.07), ncol=3, frameon=False, fontsize=8.5)
    fig.text(.055, .025, "边界：区域筛选代码与冻结 GeoJSON  ·  海岸线：GSHHG 2.3.7  ·  坐标：WGS84", fontsize=7, color="#56616a")
    outputs = []
    for suffix in ["png", "pdf"]:
        p = OUT / f"figure_w03_region_and_domain_zh.{suffix}"
        fig.savefig(p, dpi=300, facecolor="white")
        outputs.append(p)
    plt.close(fig)
    receipt = {"figure": "W03-F2", "date": "2026-11-19", "sources": sources,
               "R_bounds": list(region.bounds), "D_bounds": list(domain.bounds),
               "acquisition_bounds": list(envelope.bounds),
               "candidate_windows": {k: list(v.bounds) for k,v in windows.items()},
               "data_use": "Saved geometry definitions only; no drifter trajectories or model predictions read",
               "font": font, "crs": "WGS84 lon/lat; aspect adjusted to each panel's middle latitude",
               "script_sha256": sha(Path(__file__)),
               "outputs": {p.name: {"sha256": sha(p), "bytes": p.stat().st_size} for p in outputs}}
    (OUT / "figure_w03_region_and_domain_provenance.json").write_text(json.dumps(receipt, indent=2)+"\n")
    print(json.dumps({"outputs": [str(p) for p in outputs], "R_equals_southern_window": True}))


if __name__ == "__main__":
    main()
