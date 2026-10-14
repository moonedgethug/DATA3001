"""Redraw preliminary pilot support from saved audit rows, without refitting.

This figure is an endpoint-availability screen. It is not the formal hourly,
fixed-regime/path-complete support audit or a transport probability forecast.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, PathPatch, Polygon as PolygonPatch
from matplotlib.path import Path as MplPath
import numpy as np
import shapefile
import shapely
from shapely.geometry import Polygon, box


SEGMENT = "Southern Coastal Segment"
CORRIDOR = Polygon([
    (-81.0, 30.0), (-80.0, 32.0), (-77.0, 36.0),
    (-72.0, 40.0), (-68.0, 42.5), (-60.0, 42.5),
    (-64.0, 38.0), (-69.0, 34.0), (-75.0, 30.0),
])
R = CORRIDOR.intersection(box(-82.0, 30.0, -73.0, 35.5))
BASE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def draw_coastline(ax, path: Path) -> None:
    """Existing Natural Earth geometry supplies context, not a formal wet mask."""
    reader = shapefile.Reader(str(path))
    for item in reader.shapes():
        points = np.asarray(item.points)
        parts = list(item.parts) + [len(points)]
        for first, last in zip(parts[:-1], parts[1:]):
            vertices = points[first:last]
            if len(vertices) < 3:
                continue
            if vertices[:, 0].max() < -83 or vertices[:, 0].min() > -72:
                continue
            if vertices[:, 1].max() < 29 or vertices[:, 1].min() > 37:
                continue
            ax.add_patch(PolygonPatch(vertices, facecolor="#E8E3D8",
                edgecolor="#8A8984", linewidth=0.45, zorder=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coastline", type=Path, required=True)
    parser.add_argument("--cells", type=Path,
        default=BASE / "outputs/gulf-stream-segment-cell-support.csv")
    parser.add_argument("--summary", type=Path,
        default=BASE / "outputs/gulf-stream-segment-summary.csv")
    parser.add_argument("--output", type=Path,
        default=BASE / "outputs/southern-gulf-stream-pilot-support.png")
    args = parser.parse_args()
    with args.cells.open() as stream:
        rows = [row for row in csv.DictReader(stream) if row["segment"] == SEGMENT]
    with args.summary.open() as stream:
        summaries = [row for row in csv.DictReader(stream) if row["segment"] == SEGMENT]
    assert len(summaries) == 1
    regional = summaries[0]
    assert [int(regional[key]) for key in (
        "entering_trajectories", "valid_7d_trajectories", "valid_30d_trajectories"
    )] == [621, 605, 561]

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8,
        "axes.labelsize": 8, "axes.titlesize": 9,
        "xtick.labelsize": 8, "ytick.labelsize": 8,
        "hatch.linewidth": 0.4,
    })
    # Physical canvas equals the embedded width: chart type stays readable in A4.
    fig = plt.figure(figsize=(159.2 / 25.4, 2.82), facecolor="white")
    fig.text(0.5, 0.966,
        "Southern Gulf Stream pilot: preliminary endpoint availability",
        ha="center", va="top", fontsize=9.6, weight="bold")
    fig.text(0.5, 0.901,
        "Six-hour GDP, 1979–2025 | seasons and drogue states pooled",
        ha="center", va="top", fontsize=8)
    cmap = plt.get_cmap("viridis")
    maximum = max(int(row["valid_30d_trajectories"]) for row in rows)
    norm = LogNorm(vmin=1, vmax=maximum)
    no_origins = "#DDE3E8"
    no_endpoint = "#FFFFFF"
    expected = {1.0: (38, 133.5), 0.5: (137, 84.0)}
    manifest = {
        "metric": "Unique drifter IDs with at least one finite origin in cell intersect R and a finite endpoint exactly 30 days later",
        "origin_sampling": "Any qualifying six-hour origin; not first-entry-only",
        "endpoint_may_leave_R": True,
        "pooled": ["departure seasons", "drogue states"],
        "status": "Preliminary endpoint-availability screening; not formal hourly support or a forecast",
        "source_version": "May 2025",
        "source_coverage": "1979-02-15 to 2025-06-12",
        "dataset_doi": "10.25921/7ntx-z961",
        "regional_counts": {"visiting_R": 621, "7_day_endpoint": 605, "30_day_endpoint": 561},
        "cells_csv_sha256": sha256(args.cells),
        "summary_csv_sha256": sha256(args.summary),
        "coastline_shp_sha256": sha256(args.coastline),
        "coastline_role": "Natural Earth 1:110m context only; not the formal GSHHG wet mask",
        "R_coordinates": [list(p) for p in R.exterior.coords],
        "shared_positive_colour_range": [1, maximum],
        "crs": "EPSG:4326; longitude then latitude",
        "grid_anchor": [-180, -90],
        "software": {"python": platform.python_version(), "matplotlib": matplotlib.__version__,
            "numpy": np.__version__, "shapely": shapely.__version__, "pyshp": shapefile.__version__},
        "panels": [],
    }
    for index, resolution in enumerate((1.0, 0.5)):
        selected = [row for row in rows if float(row["grid_resolution_degrees"]) == resolution]
        counts = [int(row["valid_30d_trajectories"]) for row in selected]
        assert (len(selected), statistics.median(counts)) == expected[resolution]
        lookup = {(float(row["lon_min"]), float(row["lat_min"])): row for row in selected}
        assert len(lookup) == len(selected), "A displayed cell must have one R-specific value."
        assert all(0 <= int(row["valid_30d_trajectories"]) <= int(row["entering_trajectories"]) for row in selected)
        x = 0.067 if index == 0 else 0.547
        ax = fig.add_axes([x, 0.289, 0.36, 0.445])
        ax.set_facecolor("#FAFCFE")
        draw_coastline(ax, args.coastline)
        coords = np.asarray(R.exterior.coords)
        clip = PathPatch(MplPath(coords), transform=ax.transData)
        drawn = []
        panel_counts = {"positive_endpoint_cells": 0, "observed_cells_without_endpoint": 0, "no_screened_origin_cells": 0}
        for y in np.arange(math.floor(R.bounds[1] / resolution) * resolution,
                           math.ceil(R.bounds[3] / resolution) * resolution, resolution):
            for x0 in np.arange(math.floor(R.bounds[0] / resolution) * resolution,
                                math.ceil(R.bounds[2] / resolution) * resolution, resolution):
                tile = box(x0, y, x0 + resolution, y + resolution)
                if R.intersection(tile).area <= 1e-12:
                    continue
                key = (float(x0), float(y))
                row = lookup.get(key)
                value = int(row["valid_30d_trajectories"]) if row else None
                category = ("no_screened_origin_cells" if row is None else
                    "observed_cells_without_endpoint" if value == 0 else "positive_endpoint_cells")
                panel_counts[category] += 1
                patch = PolygonPatch(np.asarray(tile.exterior.coords),
                    facecolor=no_origins if row is None else no_endpoint if value == 0 else cmap(norm(value)),
                    edgecolor="#FFFFFF" if value else "#888888",
                    linewidth=0.35, alpha=1.0,
                    hatch="///" if value == 0 else None, zorder=3)
                patch.set_clip_path(clip)
                ax.add_patch(patch)
                drawn.append(key)
        assert len(drawn) == len(set(drawn))
        assert panel_counts["positive_endpoint_cells"] + panel_counts["observed_cells_without_endpoint"] == len(selected)
        assert panel_counts["observed_cells_without_endpoint"] == 1
        ax.plot(coords[:, 0], coords[:, 1], color="#171717", linewidth=1.05, zorder=5)
        ax.set_xlim(-81.7, -72.6)
        ax.set_ylim(29.7, 35.8)
        ax.set_aspect(1 / math.cos(math.radians(32.75)))
        ax.set_xticks([-80, -76, -73], ["80°W", "76°W", "73°W"])
        ax.set_yticks([30, 32, 34], ["30°N", "32°N", "34°N"])
        ax.tick_params(length=2.5, width=0.6, pad=2)
        ax.grid(color="#B9C2CA", linewidth=0.3, alpha=0.45, zorder=4)
        for spine in ax.spines.values():
            spine.set_color("#7D858C"); spine.set_linewidth(0.6)
        centre = 0.247 if index == 0 else 0.727
        label = "(a) 1° initial grid" if index == 0 else "(b) 0.5° candidate refinement"
        fig.text(centre, 0.824, label, ha="center", va="top", fontsize=9, weight="bold")
        fig.text(centre, 0.768,
            f"{len(selected)} observed cells; median {statistics.median(counts):g} IDs",
            ha="center", va="top", fontsize=7.9)
        manifest["panels"].append({"resolution_degrees": resolution,
            "observed_cells": len(selected), "median_over_observed_cells": statistics.median(counts),
            "repeated_rendered_cells": 0, **panel_counts})

    legend = [Line2D([0], [0], color="#171717", linewidth=1.05, label="R boundary"),
        Patch(facecolor=no_origins, edgecolor="#888888", label="No screened origins"),
        Patch(facecolor=no_endpoint, edgecolor="#888888", hatch="///", label="Origins, no 30-day endpoint")]
    fig.legend(handles=legend, loc="center", bbox_to_anchor=(0.5, 0.186),
        ncol=3, frameon=False, fontsize=7.1, handlelength=1.3, columnspacing=1.1)
    colour_ax = fig.add_axes([0.22, 0.081, 0.56, 0.028])
    bar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=colour_ax,
        orientation="horizontal", ticks=[1, 10, 100, maximum])
    bar.ax.set_xticklabels(["1", "10", "100", str(maximum)])
    bar.ax.xaxis.set_ticks_position("top")
    bar.ax.tick_params(length=2.4, pad=1.2, labelsize=7.7)
    bar.ax.minorticks_off()
    bar.outline.set_linewidth(0.45)
    fig.text(0.5, 0.024, "Unique IDs with a 30-day forward endpoint (log scale)",
        ha="center", va="bottom", fontsize=8)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=400, facecolor="white", metadata={
        "Title": "Southern Gulf Stream pilot preliminary endpoint availability",
        "Description": manifest["metric"], "Source": "NOAA GDP six-hour May 2025 version; saved team screening",
    })
    plt.close(fig)
    manifest["figure_sha256"] = sha256(args.output)
    args.output.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"figure": str(args.output), "panels": manifest["panels"]}, indent=2))


if __name__ == "__main__":
    main()
