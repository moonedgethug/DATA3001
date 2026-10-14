from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
from shapely import contains_xy
from shapely.geometry import box

from region_data_audit import (
    REGIONS,
    SECONDS_7D,
    SECONDS_30D,
    STEPS_7D,
    STEPS_30D,
    add_unique_at_resolution,
    load_array,
    plot_coastline,
)


CORRIDOR = REGIONS["Gulf Stream Corridor"]
SEGMENTS = {
    "Southern Coastal Segment": CORRIDOR.intersection(box(-82.0, 30.0, -73.0, 35.5)),
    "Cape Hatteras Separation": CORRIDOR.intersection(box(-78.0, 35.5, -66.0, 38.5)),
    "Northern Offshore Extension": CORRIDOR.intersection(box(-74.0, 38.5, -60.0, 42.5)),
}
SEGMENT_COLORS = {
    "Southern Coastal Segment": "#009E73",
    "Cape Hatteras Separation": "#D55E00",
    "Northern Offshore Extension": "#7B61A8",
}
RESOLUTIONS = (0.5, 1.0)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Audit three candidate Gulf Stream pilot segments.")
    result.add_argument("--cache-dir", type=Path, required=True)
    result.add_argument("--land-shapefile", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, default=Path("analysis/outputs"))
    return result


def state(n_trajectories: int) -> dict[str, object]:
    return {
        "enter": np.zeros(n_trajectories, dtype=bool),
        "valid_7d": np.zeros(n_trajectories, dtype=bool),
        "valid_30d": np.zeros(n_trajectories, dtype=bool),
        "drogued_valid_30d": np.zeros(n_trajectories, dtype=bool),
        "grid_all": {
            resolution: np.zeros(
                (round(180 / resolution), round(360 / resolution)), dtype=np.int32
            )
            for resolution in RESOLUTIONS
        },
        "grid_valid_30d": {
            resolution: np.zeros(
                (round(180 / resolution), round(360 / resolution)), dtype=np.int32
            )
            for resolution in RESOLUTIONS
        },
        "grid_drogued_valid_30d": {
            resolution: np.zeros(
                (round(180 / resolution), round(360 / resolution)), dtype=np.int32
            )
            for resolution in RESOLUTIONS
        },
        "destination_cells": Counter(),
        "directions": [],
        "outside": [],
        "years": Counter(),
        "experiments": Counter(),
    }


def analyse(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, bool]]:
    rowsize = load_array(args.cache_dir, "rowsize")
    experiment_ids = load_array(args.cache_dir, "expno")
    lon = load_array(args.cache_dir, "lon")
    lat = load_array(args.cache_dir, "lat")
    time_seconds = load_array(args.cache_dir, "time")
    drogue_status = load_array(args.cache_dir, "drogue_status")
    offsets = np.concatenate(([0], np.cumsum(rowsize, dtype=np.int64)))
    states = {name: state(len(rowsize)) for name in SEGMENTS}

    for trajectory_index in range(len(rowsize)):
        lo = int(offsets[trajectory_index])
        hi = int(offsets[trajectory_index + 1])
        x = np.asarray(lon[lo:hi])
        y = np.asarray(lat[lo:hi])
        t = np.asarray(time_seconds[lo:hi])
        drogued = np.asarray(drogue_status[lo:hi]) == 1
        finite = np.isfinite(x) & np.isfinite(y) & np.isfinite(t)
        finite &= (x >= -180) & (x <= 180) & (y >= -90) & (y <= 90)
        length = hi - lo

        valid_7d = np.zeros(length, dtype=bool)
        if length > STEPS_7D:
            valid_7d[:-STEPS_7D] = (
                finite[:-STEPS_7D]
                & finite[STEPS_7D:]
                & (np.abs(t[STEPS_7D:] - t[:-STEPS_7D] - SECONDS_7D) < 1)
            )
        valid_30d = np.zeros(length, dtype=bool)
        if length > STEPS_30D:
            valid_30d[:-STEPS_30D] = (
                finite[:-STEPS_30D]
                & finite[STEPS_30D:]
                & (np.abs(t[STEPS_30D:] - t[:-STEPS_30D] - SECONDS_30D) < 1)
            )
        drogued_valid_30d = np.zeros(length, dtype=bool)
        if length > STEPS_30D:
            drogued_valid_30d[:-STEPS_30D] = (
                valid_30d[:-STEPS_30D]
                & drogued[:-STEPS_30D]
                & drogued[STEPS_30D:]
            )

        for name, geometry in SEGMENTS.items():
            current = states[name]
            inside = finite & contains_xy(geometry, x, y)
            current["enter"][trajectory_index] = inside.any()
            if not inside.any():
                continue
            current["valid_7d"][trajectory_index] = (inside & valid_7d).any()
            current["valid_30d"][trajectory_index] = (inside & valid_30d).any()
            current["drogued_valid_30d"][trajectory_index] = (
                inside & drogued_valid_30d
            ).any()
            for resolution in RESOLUTIONS:
                add_unique_at_resolution(
                    current["grid_all"][resolution], x[inside], y[inside], resolution
                )
                add_unique_at_resolution(
                    current["grid_valid_30d"][resolution],
                    x[inside & valid_30d],
                    y[inside & valid_30d],
                    resolution,
                )
                add_unique_at_resolution(
                    current["grid_drogued_valid_30d"][resolution],
                    x[inside & drogued_valid_30d],
                    y[inside & drogued_valid_30d],
                    resolution,
                )

            valid_indices = np.flatnonzero(inside & valid_30d)
            if valid_indices.size:
                origin = int(valid_indices[0])
                destination = origin + STEPS_30D
                destination_lon = int(np.floor(x[destination] + 180))
                destination_lat = int(np.floor(y[destination] + 90))
                current["destination_cells"][(destination_lon, destination_lat)] += 1
                dx = (x[destination] - x[origin]) * math.cos(
                    math.radians((y[destination] + y[origin]) / 2)
                )
                dy = y[destination] - y[origin]
                current["directions"].append(math.atan2(dy, dx))
                current["outside"].append(
                    not bool(contains_xy(geometry, [x[destination]], [y[destination]])[0])
                )
                year = int(str(np.datetime64(int(t[origin]), "s"))[:4])
                current["years"][year] += 1
                current["experiments"][int(experiment_ids[trajectory_index])] += 1

    summary_rows = []
    cell_rows = []
    for name, current in states.items():
        entering = int(current["enter"].sum())
        valid_7d = int(current["valid_7d"].sum())
        valid_30d = int(current["valid_30d"].sum())
        drogued_30d = int(current["drogued_valid_30d"].sum())
        destination_counts = np.asarray(list(current["destination_cells"].values()), dtype=float)
        probabilities = destination_counts / destination_counts.sum()
        effective_destinations = float(
            np.exp(-(probabilities * np.log(probabilities)).sum())
        )
        directions = np.asarray(current["directions"], dtype=float)
        direction_concentration = float(abs(np.exp(1j * directions).mean()))
        summary_rows.append(
            {
                "segment": name,
                "entering_trajectories": entering,
                "valid_7d_trajectories": valid_7d,
                "valid_7d_pct": valid_7d / entering,
                "valid_30d_trajectories": valid_30d,
                "valid_30d_pct": valid_30d / entering,
                "drogued_valid_30d_trajectories": drogued_30d,
                "drogued_share_of_valid30_pct": drogued_30d / valid_30d,
                "effective_destination_cells_30d": effective_destinations,
                "direction_concentration_30d": direction_concentration,
                "outside_segment_share_30d": float(np.mean(current["outside"])),
                "top_year_share_valid30": max(current["years"].values()) / valid_30d,
                "top_experiment_share_valid30": max(current["experiments"].values()) / valid_30d,
            }
        )
        for resolution in RESOLUTIONS:
            grid_all = current["grid_all"][resolution]
            grid_valid_30d = current["grid_valid_30d"][resolution]
            grid_drogued = current["grid_drogued_valid_30d"][resolution]
            n_lon = round(360 / resolution)
            for grid_y, grid_x in np.argwhere(grid_all > 0):
                lon_min = -180 + grid_x * resolution
                lat_min = -90 + grid_y * resolution
                cell_rows.append(
                    {
                        "segment": name,
                        "grid_resolution_degrees": resolution,
                        "lon_min": lon_min,
                        "lon_max": lon_min + resolution,
                        "lat_min": lat_min,
                        "lat_max": lat_min + resolution,
                        "cell_code": int(grid_y * n_lon + grid_x),
                        "entering_trajectories": int(grid_all[grid_y, grid_x]),
                        "valid_30d_trajectories": int(grid_valid_30d[grid_y, grid_x]),
                        "drogued_valid_30d_trajectories": int(grid_drogued[grid_y, grid_x]),
                    }
                )

    summary = pd.DataFrame(summary_rows)
    cells = pd.DataFrame(cell_rows)
    checks = {
        "region_counts_nested": bool(
            (summary["valid_30d_trajectories"] <= summary["valid_7d_trajectories"]).all()
            and (summary["valid_7d_trajectories"] <= summary["entering_trajectories"]).all()
        ),
        "cell_counts_nested": bool(
            (cells["valid_30d_trajectories"] <= cells["entering_trajectories"]).all()
        ),
        "drogued_counts_bounded": bool(
            (
                cells["drogued_valid_30d_trajectories"]
                <= cells["valid_30d_trajectories"]
            ).all()
        ),
    }
    return summary, cells, checks


def make_figure(cells: pd.DataFrame, land_shapefile: Path, output_dir: Path) -> None:
    support = cells[cells["valid_30d_trajectories"] > 0]
    norm = LogNorm(vmin=1, vmax=int(support["valid_30d_trajectories"].max()))
    cmap = plt.get_cmap("viridis")
    mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    mappable.set_array([])
    fig, axes = plt.subplots(1, 2, figsize=(17, 6.7), constrained_layout=True)
    for ax, resolution in zip(axes, RESOLUTIONS):
        plot_coastline(ax, land_shapefile)
        selected = support[support["grid_resolution_degrees"] == resolution]
        gap = resolution * 0.12
        for row in selected.itertuples(index=False):
            ax.add_patch(
                Rectangle(
                    (row.lon_min + gap / 2, row.lat_min + gap / 2),
                    resolution - gap,
                    resolution - gap,
                    facecolor=cmap(norm(row.valid_30d_trajectories)),
                    edgecolor="none",
                    alpha=0.88,
                    zorder=3,
                )
            )
        x, y = CORRIDOR.exterior.xy
        ax.plot(x, y, color="#0072B2", linewidth=1.4, linestyle="--", zorder=4)
        for name, geometry in SEGMENTS.items():
            x, y = geometry.exterior.xy
            ax.plot(x, y, color=SEGMENT_COLORS[name], linewidth=2.5, label=name, zorder=5)
        ax.set_xlim(-83, -59)
        ax.set_ylim(29, 43.5)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title(f"{resolution:g}° origin cells")
        ax.grid(color="#D5D9DE", linewidth=0.5, alpha=0.6)
        if resolution == 1.0:
            ax.legend(loc="lower right", fontsize=8)
    colorbar = fig.colorbar(mappable, ax=axes, pad=0.015, shrink=0.92)
    colorbar.set_label("Unique 30-day-valid trajectories (shared log scale)")
    fig.suptitle("Candidate Gulf Stream pilot segments", fontsize=15)
    fig.savefig(output_dir / "gulf-stream-segment-support-0p5-vs-1deg.png", dpi=180)
    plt.close(fig)


def main() -> None:
    args = parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary, cells, checks = analyse(args)
    summary.to_csv(args.output_dir / "gulf-stream-segment-summary.csv", index=False)
    cells.to_csv(args.output_dir / "gulf-stream-segment-cell-support.csv", index=False)
    (args.output_dir / "gulf-stream-segment-checks.json").write_text(
        json.dumps(checks, indent=2) + "\n", encoding="utf-8"
    )
    make_figure(cells, args.land_shapefile, args.output_dir)
    print(summary.to_string(index=False))
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
