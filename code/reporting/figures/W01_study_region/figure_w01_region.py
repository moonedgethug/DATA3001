"""Render the introduction locator map from the registered geographic assets.

Run from the DATA3001 workspace:
    work_place/.venv/bin/python 'Final Report/figures/W01_study_region/figure_w01_region.py'
"""

from pathlib import Path
import hashlib
import json
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import FuncFormatter
import shapely
from shapely.geometry import box, shape
from shapely.plotting import patch_from_polygon


OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[2]
PROJECT = ROOT / "work_place"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registered_asset(name, registry):
    spec = registry[name]
    path = PROJECT / spec["path"]
    actual = digest(path)
    if actual != spec["sha256"]:
        raise ValueError(f"Registered asset checksum mismatch: {name}")
    return path, {"path": str(path.relative_to(ROOT)), "sha256": actual}


def polygons(geometry):
    if geometry.geom_type == "Polygon":
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from polygons(part)


def main():
    registry = json.loads((PROJECT / "configs/assets.json").read_text())["assets"]
    r_path, r_receipt = registered_asset("release_R", registry)
    land_path, land_receipt = registered_asset("land_mask_intermediate", registry)
    feature = json.loads(r_path.read_text())["features"][0]
    region = shape(feature["geometry"])
    if not region.is_valid:
        raise ValueError("Release polygon is invalid")
    land = shapely.from_wkb(land_path.read_bytes())
    west, south, east, north = region.bounds
    assert (west, south, east, north) == (-81.0, 30.0, -73.0, 35.5)

    available = {f.name for f in font_manager.fontManager.ttflist}
    font = next((n for n in ["Arial Unicode MS", "Noto Sans CJK SC", "PingFang HK"]
                 if n in available), None)
    if font is None:
        raise RuntimeError("Install a Chinese font: Arial Unicode MS or Noto Sans CJK SC")
    plt.rcParams.update({"font.family": font, "font.size": 10.5,
                         "axes.unicode_minus": False, "svg.fonttype": "path",
                         "pdf.fonttype": 42})
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 5.1),
                             gridspec_kw={"width_ratios": [1.3, 1]})
    fig.subplots_adjust(left=0.065, right=0.98, top=0.83, bottom=0.19, wspace=0.18)
    colour = "#176481"
    extents = [(-99, 19, -65, 40), (-82.5, 28.8, -71.8, 37)]
    for ax, extent in zip(axes, extents):
        x0, y0, x1, y1 = extent
        ax.set_facecolor("#eef5f8")
        for polygon in polygons(land.intersection(box(*extent))):
            ax.add_patch(patch_from_polygon(polygon, facecolor="#e1e0d8",
                                            edgecolor="#85867f", linewidth=0.45, zorder=1))
        ax.add_patch(patch_from_polygon(region, facecolor=colour, alpha=0.19,
                                        edgecolor="none", zorder=3))
        x, y = region.exterior.xy
        ax.plot(x, y, color=colour, linewidth=1.8, zorder=4)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect(1 / math.cos(math.radians((y0 + y1) / 2)))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{abs(v):g}°W"))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:g}°N"))
        ax.grid(color="#b1c0c8", linewidth=0.45, alpha=0.65, zorder=0)
        ax.tick_params(labelsize=9, length=3)
        for spine in ax.spines.values():
            spine.set_color("#87959e")

    ax = axes[0]
    ax.set_title("(a) 地理位置", loc="left", fontsize=12, pad=12)
    ax.set_xticks([-95, -85, -75, -65])
    ax.set_yticks([20, 25, 30, 35, 40])
    for x, y, label, size in [(-90, 35.2, "美国", 12), (-96, 23.4, "墨西哥", 10),
                               (-89.6, 26.5, "墨西哥湾", 12), (-81, 21.7, "古巴", 10),
                               (-70, 28, "西北大西洋", 11)]:
        ax.text(x, y, label, fontsize=size, ha="center", va="center", color="#334650")
    ax.annotate("墨西哥湾北部", xy=(-90, 29), xytext=(-95.5, 31), fontsize=9.5,
                arrowprops={"arrowstyle": "-", "color": "#626d74", "lw": 0.8})
    ax.text(-84.1, 28.1, "Florida", fontsize=9, rotation=-62, color="#52616b")
    ax.text(-76.4, 24.2, "Bahamas", fontsize=9, color="#52616b")
    ax.annotate("释放区域 R", xy=(-76, 33), xytext=(-70.4, 36.9), ha="center",
                fontsize=10, color=colour,
                arrowprops={"arrowstyle": "-", "color": colour, "lw": 0.9})

    ax = axes[1]
    ax.set_title("(b) 正式释放区域 R", loc="left", fontsize=12, pad=12)
    ax.set_xticks([-81, -79, -77, -75, -73])
    ax.set_yticks([30, 32, 34, 35.5])
    ax.add_patch(Rectangle((west, south), east-west, north-south, fill=False,
                           edgecolor="#a36f27", linewidth=1.0, linestyle=(0, (4, 3)), zorder=2))
    ax.text(-76.2, 32.7, "R", color=colour, fontsize=21, ha="center")
    ax.text(-81.15, 34.9, "美国东南岸", color="#52616b", fontsize=10, rotation=42)
    ax.text(0.5, -0.135, "外包范围：30°–35.5°N，81°–73°W", transform=ax.transAxes,
            ha="center", fontsize=10.5)

    fig.suptitle("研究区域：美国东岸 Gulf Stream 南段", fontsize=15, y=0.97)
    fig.legend(handles=[Patch(facecolor="#c3dce5", edgecolor=colour, label="正式释放区 R"),
                        Line2D([0], [0], color="#a36f27", linestyle="--", label="经纬度外包框")],
               loc="lower center", bbox_to_anchor=(0.5, 0.055), ncol=2, frameon=False, fontsize=10)
    fig.text(0.065, 0.022, "区域边界：项目冻结 GeoJSON  ·  海岸线：GSHHG 2.3.7  ·  坐标：WGS84",
             fontsize=8.5, color="#52616b")
    paths = []
    for extension in ["png", "svg", "pdf"]:
        path = OUTPUT / f"figure_w01_region_zh.{extension}"
        fig.savefig(path, dpi=300, facecolor="white")
        paths.append(path)
    plt.close(fig)
    receipt = {
        "figure": "W01-F1", "purpose": "Geographic locator and release-region definition",
        "date_sydney": "2026-11-19", "sources": {"release_R": r_receipt, "land": land_receipt},
        "region_bounds_lonlat": list(region.bounds),
        "region_vertices_lonlat": [list(c) for c in region.exterior.coords],
        "region_definition": feature["properties"]["definition"],
        "coordinate_system": "WGS84 lon/lat; aspect corrected at each panel's mid-latitude",
        "coastline": "GSHHG 2.3.7, intermediate-resolution level-1 land",
        "font": font, "data_use": "Registered geometry only; no drifter records or predictions read",
        "versions": {"matplotlib": matplotlib.__version__, "shapely": shapely.__version__},
        "script_sha256": digest(Path(__file__)),
        "outputs": {p.name: {"sha256": digest(p), "bytes": p.stat().st_size} for p in paths},
    }
    (OUTPUT / "figure_w01_region_provenance.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"bounds": receipt["region_bounds_lonlat"],
                      "outputs": [str(p) for p in paths]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
