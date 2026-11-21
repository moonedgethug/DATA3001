from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
import shapefile
from shapely import contains_xy
from shapely.geometry import Polygon, box


STEPS_7D = 7 * 4
STEPS_30D = 30 * 4
SECONDS_7D = 7 * 24 * 60 * 60
SECONDS_30D = 30 * 24 * 60 * 60
GRID_RESOLUTIONS = (0.25, 0.5, 1.0, 2.0)


REGIONS = {
    "North-Central Gulf": box(-92.5, 25.0, -85.0, 30.0),
    "Florida-Bahamas": box(-85.0, 22.5, -75.0, 30.0),
    "Gulf Stream Corridor": Polygon(
        [
            (-81.0, 30.0),
            (-80.0, 32.0),
            (-77.0, 36.0),
            (-72.0, 40.0),
            (-68.0, 42.5),
            (-60.0, 42.5),
            (-64.0, 38.0),
            (-69.0, 34.0),
            (-75.0, 30.0),
        ]
    ),
}

REGION_COLORS = {
    "North-Central Gulf": "#E69F00",
    "Florida-Bahamas": "#009E73",
    "Gulf Stream Corridor": "#0072B2",
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Audit GDP trajectory support in three proposed project zones.")
    result.add_argument("--cache-dir", type=Path, required=True)
    result.add_argument("--source-manifest", type=Path, required=True)
    result.add_argument("--land-shapefile", type=Path, required=True)
    result.add_argument("--boem-platforms", type=Path)
    result.add_argument("--output-dir", type=Path, default=Path("analysis/outputs"))
    return result


def load_array(cache_dir: Path, name: str) -> np.ndarray:
    return np.load(cache_dir / f"{name}.npy", mmap_mode="r")


def region_state(n_trajectories: int) -> dict[str, object]:
    return {
        "enter": np.zeros(n_trajectories, dtype=bool),
        "valid_7d": np.zeros(n_trajectories, dtype=bool),
        "valid_30d": np.zeros(n_trajectories, dtype=bool),
        "drogued_valid_7d": np.zeros(n_trajectories, dtype=bool),
        "drogued_valid_30d": np.zeros(n_trajectories, dtype=bool),
        "first_valid_30d_year": np.full(n_trajectories, -1, dtype=np.int16),
        "cell_all": np.zeros((180, 360), dtype=np.int32),
        "cell_valid_7d": np.zeros((180, 360), dtype=np.int32),
        "cell_valid_30d": np.zeros((180, 360), dtype=np.int32),
        "cell_drogued_valid_30d": np.zeros((180, 360), dtype=np.int32),
        "destination_30d": defaultdict(Counter),
        "direction_30d": defaultdict(list),
        "outside_30d": defaultdict(list),
        "year_30d": defaultdict(Counter),
        "season_30d": defaultdict(Counter),
        "experiment_30d": defaultdict(Counter),
        "grid_all": {
            resolution: np.zeros(
                (round(180 / resolution), round(360 / resolution)), dtype=np.int32
            )
            for resolution in GRID_RESOLUTIONS
        },
        "grid_valid_7d": {
            resolution: np.zeros(
                (round(180 / resolution), round(360 / resolution)), dtype=np.int32
            )
            for resolution in GRID_RESOLUTIONS
        },
        "grid_valid_30d": {
            resolution: np.zeros(
                (round(180 / resolution), round(360 / resolution)), dtype=np.int32
            )
            for resolution in GRID_RESOLUTIONS
        },
        "grid_drogued_valid_30d": {
            resolution: np.zeros(
                (round(180 / resolution), round(360 / resolution)), dtype=np.int32
            )
            for resolution in GRID_RESOLUTIONS
        },
    }


def cell_codes(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    x = np.clip(np.floor(lon + 180).astype(np.int32), 0, 359)
    y = np.clip(np.floor(lat + 90).astype(np.int32), 0, 179)
    return y * 360 + x


def add_unique_trajectory_to_cells(target: np.ndarray, lon: np.ndarray, lat: np.ndarray) -> None:
    if lon.size == 0:
        return
    target.flat[np.unique(cell_codes(lon, lat))] += 1


def cell_codes_at_resolution(lon: np.ndarray, lat: np.ndarray, resolution: float) -> np.ndarray:
    n_lon = round(360 / resolution)
    n_lat = round(180 / resolution)
    x = np.clip(np.floor((lon + 180) / resolution).astype(np.int32), 0, n_lon - 1)
    y = np.clip(np.floor((lat + 90) / resolution).astype(np.int32), 0, n_lat - 1)
    return y * n_lon + x


def add_unique_at_resolution(
    target: np.ndarray,
    lon: np.ndarray,
    lat: np.ndarray,
    resolution: float,
) -> None:
    if lon.size == 0:
        return
    target.flat[np.unique(cell_codes_at_resolution(lon, lat, resolution))] += 1


def first_index_per_cell(mask: np.ndarray, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    indices = np.flatnonzero(mask)
    if indices.size == 0:
        return indices
    codes = cell_codes(lon[indices], lat[indices])
    _, first = np.unique(codes, return_index=True)
    return indices[np.sort(first)]


def analyse(
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    rowsize = load_array(args.cache_dir, "rowsize")
    trajectory_ids = load_array(args.cache_dir, "id")
    experiment_ids = load_array(args.cache_dir, "expno")
    lon = load_array(args.cache_dir, "lon")
    lat = load_array(args.cache_dir, "lat")
    time_seconds = load_array(args.cache_dir, "time")
    drogue_status = load_array(args.cache_dir, "drogue_status")

    offsets = np.concatenate(([0], np.cumsum(rowsize, dtype=np.int64)))
    n_trajectories = len(rowsize)
    states = {name: region_state(n_trajectories) for name in REGIONS}

    for trajectory_index in range(n_trajectories):
        lo = int(offsets[trajectory_index])
        hi = int(offsets[trajectory_index + 1])
        x = np.asarray(lon[lo:hi])
        y = np.asarray(lat[lo:hi])
        t = np.asarray(time_seconds[lo:hi])
        drogued = np.asarray(drogue_status[lo:hi]) == 1
        finite = np.isfinite(x) & np.isfinite(y) & np.isfinite(t)
        finite &= (x >= -180) & (x <= 180) & (y >= -90) & (y <= 90)

        trajectory_length = hi - lo
        valid_7d = np.zeros(trajectory_length, dtype=bool)
        if trajectory_length > STEPS_7D:
            valid_7d[:-STEPS_7D] = (
                finite[:-STEPS_7D]
                & finite[STEPS_7D:]
                & (np.abs(t[STEPS_7D:] - t[:-STEPS_7D] - SECONDS_7D) < 1)
            )
        valid_30d = np.zeros(trajectory_length, dtype=bool)
        if trajectory_length > STEPS_30D:
            valid_30d[:-STEPS_30D] = (
                finite[:-STEPS_30D]
                & finite[STEPS_30D:]
                & (np.abs(t[STEPS_30D:] - t[:-STEPS_30D] - SECONDS_30D) < 1)
            )
        drogued_valid_7d = np.zeros(trajectory_length, dtype=bool)
        if trajectory_length > STEPS_7D:
            drogued_valid_7d[:-STEPS_7D] = (
                valid_7d[:-STEPS_7D] & drogued[:-STEPS_7D] & drogued[STEPS_7D:]
            )
        drogued_valid_30d = np.zeros(trajectory_length, dtype=bool)
        if trajectory_length > STEPS_30D:
            drogued_valid_30d[:-STEPS_30D] = (
                valid_30d[:-STEPS_30D] & drogued[:-STEPS_30D] & drogued[STEPS_30D:]
            )

        for region_name, geometry in REGIONS.items():
            state = states[region_name]
            inside = finite & contains_xy(geometry, x, y)
            state["enter"][trajectory_index] = inside.any()
            if not inside.any():
                continue

            state["valid_7d"][trajectory_index] = (inside & valid_7d).any()
            state["valid_30d"][trajectory_index] = (inside & valid_30d).any()
            state["drogued_valid_7d"][trajectory_index] = (inside & drogued_valid_7d).any()
            state["drogued_valid_30d"][trajectory_index] = (inside & drogued_valid_30d).any()

            add_unique_trajectory_to_cells(state["cell_all"], x[inside], y[inside])
            add_unique_trajectory_to_cells(
                state["cell_valid_7d"], x[inside & valid_7d], y[inside & valid_7d]
            )
            add_unique_trajectory_to_cells(
                state["cell_valid_30d"], x[inside & valid_30d], y[inside & valid_30d]
            )
            add_unique_trajectory_to_cells(
                state["cell_drogued_valid_30d"],
                x[inside & drogued_valid_30d],
                y[inside & drogued_valid_30d],
            )
            for resolution in GRID_RESOLUTIONS:
                add_unique_at_resolution(
                    state["grid_all"][resolution], x[inside], y[inside], resolution
                )
                add_unique_at_resolution(
                    state["grid_valid_7d"][resolution],
                    x[inside & valid_7d],
                    y[inside & valid_7d],
                    resolution,
                )
                add_unique_at_resolution(
                    state["grid_valid_30d"][resolution],
                    x[inside & valid_30d],
                    y[inside & valid_30d],
                    resolution,
                )
                add_unique_at_resolution(
                    state["grid_drogued_valid_30d"][resolution],
                    x[inside & drogued_valid_30d],
                    y[inside & drogued_valid_30d],
                    resolution,
                )

            valid_indices = first_index_per_cell(inside & valid_30d, x, y)
            if valid_indices.size:
                state["first_valid_30d_year"][trajectory_index] = int(
                    str(np.datetime64(int(t[valid_indices[0]]), "s"))[:4]
                )
            for origin_index in valid_indices:
                destination_index = origin_index + STEPS_30D
                origin_code = int(cell_codes(x[origin_index : origin_index + 1], y[origin_index : origin_index + 1])[0])
                destination_code = int(
                    cell_codes(
                        x[destination_index : destination_index + 1],
                        y[destination_index : destination_index + 1],
                    )[0]
                )
                state["destination_30d"][origin_code][destination_code] += 1
                dx = (x[destination_index] - x[origin_index]) * math.cos(
                    math.radians((y[destination_index] + y[origin_index]) / 2)
                )
                dy = y[destination_index] - y[origin_index]
                state["direction_30d"][origin_code].append(math.atan2(dy, dx))
                state["outside_30d"][origin_code].append(
                    not bool(contains_xy(geometry, [x[destination_index]], [y[destination_index]])[0])
                )
                timestamp = str(np.datetime64(int(t[origin_index]), "s"))
                year = int(timestamp[:4])
                month = int(timestamp[5:7])
                season = (
                    "DJF" if month in (12, 1, 2) else
                    "MAM" if month in (3, 4, 5) else
                    "JJA" if month in (6, 7, 8) else
                    "SON"
                )
                state["year_30d"][origin_code][year] += 1
                state["season_30d"][origin_code][season] += 1
                state["experiment_30d"][origin_code][int(experiment_ids[trajectory_index])] += 1

    summary_rows: list[dict[str, object]] = []
    cell_rows: list[dict[str, object]] = []
    sensitivity_rows: list[dict[str, object]] = []
    grid_cell_rows: list[dict[str, object]] = []

    for region_name, geometry in REGIONS.items():
        state = states[region_name]
        entering = state["enter"]
        valid_7d = state["valid_7d"]
        valid_30d = state["valid_30d"]
        valid_both = valid_7d & valid_30d
        drogued_valid_30d = state["drogued_valid_30d"]
        touched = state["cell_all"] > 0

        for resolution in GRID_RESOLUTIONS:
            grid_all = state["grid_all"][resolution]
            grid_valid_7d = state["grid_valid_7d"][resolution]
            grid_valid_30d = state["grid_valid_30d"][resolution]
            grid_drogued_valid_30d = state["grid_drogued_valid_30d"][resolution]
            grid_touched = grid_all > 0
            sensitivity_rows.append(
                {
                    "region": region_name,
                    "grid_resolution_degrees": resolution,
                    "cells_touched": int(grid_touched.sum()),
                    "cells_valid7_ge_10": int((grid_touched & (grid_valid_7d >= 10)).sum()),
                    "cells_valid30_ge_10": int((grid_touched & (grid_valid_30d >= 10)).sum()),
                    "cells_valid30_ge_25": int((grid_touched & (grid_valid_30d >= 25)).sum()),
                    "cells_valid30_ge_50": int((grid_touched & (grid_valid_30d >= 50)).sum()),
                    "cells_drogued_valid30_ge_25": int(
                        (grid_touched & (grid_drogued_valid_30d >= 25)).sum()
                    ),
                    "median_valid30_per_touched_cell": float(
                        np.median(grid_valid_30d[grid_touched])
                    ),
                    "median_drogued_valid30_per_touched_cell": float(
                        np.median(grid_drogued_valid_30d[grid_touched])
                    ),
                }
            )
            n_lon = round(360 / resolution)
            for grid_y, grid_x in np.argwhere(grid_touched):
                lon_min = -180 + grid_x * resolution
                lat_min = -90 + grid_y * resolution
                grid_cell_rows.append(
                    {
                        "region": region_name,
                        "grid_resolution_degrees": resolution,
                        "lon_min": lon_min,
                        "lon_max": lon_min + resolution,
                        "lat_min": lat_min,
                        "lat_max": lat_min + resolution,
                        "cell_code": int(grid_y * n_lon + grid_x),
                        "entering_trajectories": int(grid_all[grid_y, grid_x]),
                        "valid_7d_trajectories": int(grid_valid_7d[grid_y, grid_x]),
                        "valid_30d_trajectories": int(grid_valid_30d[grid_y, grid_x]),
                        "drogued_valid_30d_trajectories": int(
                            grid_drogued_valid_30d[grid_y, grid_x]
                        ),
                    }
                )

        years = state["first_valid_30d_year"][valid_30d]
        top_year_share = float(pd.Series(years).value_counts(normalize=True).iloc[0]) if len(years) else np.nan
        valid_experiments = np.asarray(experiment_ids)[valid_30d]
        top_experiment_share = (
            float(pd.Series(valid_experiments).value_counts(normalize=True).iloc[0])
            if len(valid_experiments)
            else np.nan
        )

        for cell_y, cell_x in np.argwhere(touched):
            origin_code = int(cell_y * 360 + cell_x)
            destinations = state["destination_30d"].get(origin_code, Counter())
            destination_counts = np.asarray(list(destinations.values()), dtype=float)
            if destination_counts.size:
                probabilities = destination_counts / destination_counts.sum()
                entropy = float(-(probabilities * np.log(probabilities)).sum())
                effective_destinations = float(np.exp(entropy))
            else:
                entropy = np.nan
                effective_destinations = np.nan
            directions = np.asarray(state["direction_30d"].get(origin_code, []), dtype=float)
            direction_concentration = (
                float(abs(np.exp(1j * directions).mean())) if directions.size else np.nan
            )
            outside_values = np.asarray(state["outside_30d"].get(origin_code, []), dtype=float)
            outside_share = float(outside_values.mean()) if outside_values.size else np.nan
            year_counts = state["year_30d"].get(origin_code, Counter())
            season_counts = state["season_30d"].get(origin_code, Counter())
            experiment_counts = state["experiment_30d"].get(origin_code, Counter())
            n_cell_records = int(destination_counts.sum())
            cell_rows.append(
                {
                    "region": region_name,
                    "lon_min": int(cell_x - 180),
                    "lon_max": int(cell_x - 179),
                    "lat_min": int(cell_y - 90),
                    "lat_max": int(cell_y - 89),
                    "entering_trajectories": int(state["cell_all"][cell_y, cell_x]),
                    "valid_7d_trajectories": int(state["cell_valid_7d"][cell_y, cell_x]),
                    "valid_30d_trajectories": int(state["cell_valid_30d"][cell_y, cell_x]),
                    "drogued_valid_30d_trajectories": int(
                        state["cell_drogued_valid_30d"][cell_y, cell_x]
                    ),
                    "observed_30d_destination_cells": int(destination_counts.size),
                    "destination_entropy_nats": entropy,
                    "effective_30d_destination_cells": effective_destinations,
                    "direction_concentration_30d": direction_concentration,
                    "outside_region_share_30d": outside_share,
                    "first_valid_30d_year": min(year_counts) if year_counts else np.nan,
                    "last_valid_30d_year": max(year_counts) if year_counts else np.nan,
                    "active_valid_30d_years": len(year_counts),
                    "top_year_share_valid_30d": (
                        max(year_counts.values()) / n_cell_records if n_cell_records else np.nan
                    ),
                    "top_season_share_valid_30d": (
                        max(season_counts.values()) / n_cell_records if n_cell_records else np.nan
                    ),
                    "top_experiment_share_valid_30d": (
                        max(experiment_counts.values()) / n_cell_records if n_cell_records else np.nan
                    ),
                }
            )

        region_cells = [row for row in cell_rows if row["region"] == region_name]
        eligible_complexity = [
            row for row in region_cells if row["valid_30d_trajectories"] >= 25
        ]
        summary_rows.append(
            {
                "region": region_name,
                "entering_trajectories": int(entering.sum()),
                "valid_7d_trajectories": int(valid_7d.sum()),
                "valid_7d_pct": float(valid_7d.sum() / entering.sum()),
                "valid_30d_trajectories": int(valid_30d.sum()),
                "valid_30d_pct": float(valid_30d.sum() / entering.sum()),
                "valid_both_trajectories": int(valid_both.sum()),
                "valid_both_pct": float(valid_both.sum() / entering.sum()),
                "drogued_valid_30d_trajectories": int(drogued_valid_30d.sum()),
                "drogued_share_of_valid30_pct": float(
                    drogued_valid_30d.sum() / valid_30d.sum()
                ),
                "one_degree_cells_touched": int(touched.sum()),
                "cells_valid30_ge_10": int(
                    (touched & (state["cell_valid_30d"] >= 10)).sum()
                ),
                "cells_valid30_ge_25": int(
                    (touched & (state["cell_valid_30d"] >= 25)).sum()
                ),
                "cells_valid30_ge_50": int(
                    (touched & (state["cell_valid_30d"] >= 50)).sum()
                ),
                "median_valid30_per_touched_cell": float(
                    np.median(state["cell_valid_30d"][touched])
                ),
                "top_experiment_share_valid30": top_experiment_share,
                "top_year_share_valid30": top_year_share,
                "complexity_cells_ge25": len(eligible_complexity),
                "median_effective_30d_destination_cells_ge25": float(
                    np.nanmedian(
                        [row["effective_30d_destination_cells"] for row in eligible_complexity]
                    )
                ),
                "median_direction_concentration_30d_ge25": float(
                    np.nanmedian(
                        [row["direction_concentration_30d"] for row in eligible_complexity]
                    )
                ),
                "median_outside_region_share_30d_ge25": float(
                    np.nanmedian([row["outside_region_share_30d"] for row in eligible_complexity])
                ),
            }
        )

    checks = {
        "source_trajectory_rows": int(n_trajectories),
        "source_distinct_ids": int(np.unique(trajectory_ids).size),
        "source_observation_rows": int(len(lon)),
        "ragged_lengths_match": bool(
            int(rowsize.sum()) == len(lon) == len(lat) == len(time_seconds) == len(drogue_status)
        ),
        "region_counts_nested": all(
            int(state["valid_30d"].sum()) <= int(state["valid_7d"].sum()) <= int(state["enter"].sum())
            for state in states.values()
        ),
        "drogued_counts_bounded": all(
            int(state["drogued_valid_30d"].sum()) <= int(state["valid_30d"].sum())
            for state in states.values()
        ),
        "grid_counts_nested": all(
            np.all(state["grid_valid_30d"][resolution] <= state["grid_valid_7d"][resolution])
            and np.all(state["grid_valid_7d"][resolution] <= state["grid_all"][resolution])
            for state in states.values()
            for resolution in GRID_RESOLUTIONS
        ),
        "grid_drogued_counts_bounded": all(
            np.all(
                state["grid_drogued_valid_30d"][resolution]
                <= state["grid_valid_30d"][resolution]
            )
            for state in states.values()
            for resolution in GRID_RESOLUTIONS
        ),
    }
    return (
        pd.DataFrame(summary_rows),
        pd.DataFrame(cell_rows),
        pd.DataFrame(sensitivity_rows),
        pd.DataFrame(grid_cell_rows),
        checks,
    )


def plot_coastline(ax: plt.Axes, shapefile_path: Path) -> None:
    reader = shapefile.Reader(shapefile_path.as_posix())
    for item in reader.shapes():
        points = np.asarray(item.points)
        if points.size == 0:
            continue
        parts = list(item.parts) + [len(points)]
        for start, end in zip(parts[:-1], parts[1:]):
            segment = points[start:end]
            ax.fill(segment[:, 0], segment[:, 1], color="#F3F1EB", edgecolor="#8E949C", linewidth=0.45)


def load_boem_platforms(path: Path | None) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    if path is None:
        return None, None
    geojson = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for feature in geojson.get("features", []):
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        if len(coordinates) < 2:
            continue
        longitude, latitude = map(float, coordinates[:2])
        records.append({"longitude": longitude, "latitude": latitude})
    points = pd.DataFrame(records)
    if points.empty:
        return points, pd.DataFrame(columns=["lon_min", "lat_min", "current_platforms"])
    points["lon_min"] = np.floor(points["longitude"]).astype(int)
    points["lat_min"] = np.floor(points["latitude"]).astype(int)
    by_cell = (
        points.groupby(["lon_min", "lat_min"])
        .size()
        .rename("current_platforms")
        .reset_index()
    )
    return points, by_cell


def platform_cells_at_resolution(points: pd.DataFrame, resolution: float) -> pd.DataFrame:
    if points.empty:
        return pd.DataFrame(columns=["lon_min", "lat_min", "current_platforms"])
    cells = points.copy()
    cells["lon_min"] = (
        -180
        + np.floor((cells["longitude"] + 180) / resolution) * resolution
    ).round(6)
    cells["lat_min"] = (
        -90
        + np.floor((cells["latitude"] + 90) / resolution) * resolution
    ).round(6)
    return (
        cells.groupby(["lon_min", "lat_min"])
        .size()
        .rename("current_platforms")
        .reset_index()
    )


def draw_support_map(
    ax: plt.Axes,
    grid_cells: pd.DataFrame,
    resolution: float,
    land_shapefile: Path,
    platforms: pd.DataFrame | None,
    norm: LogNorm,
    title: str,
    show_legend: bool = True,
) -> None:
    plot_coastline(ax, land_shapefile)
    support = grid_cells[
        (grid_cells["grid_resolution_degrees"] == resolution)
        & (grid_cells["valid_30d_trajectories"] > 0)
    ]
    colormap = plt.get_cmap("viridis")
    gap = resolution * 0.12
    for row in support.itertuples(index=False):
        ax.add_patch(
            Rectangle(
                (row.lon_min + gap / 2, row.lat_min + gap / 2),
                resolution - gap,
                resolution - gap,
                facecolor=colormap(norm(row.valid_30d_trajectories)),
                edgecolor="none",
                alpha=0.86,
                zorder=3,
            )
        )
    for name, geometry in REGIONS.items():
        x, y = geometry.exterior.xy
        ax.plot(x, y, color=REGION_COLORS[name], linewidth=2.3, label=name, zorder=4)
    if platforms is not None and not platforms.empty:
        ax.scatter(
            platforms["longitude"],
            platforms["latitude"],
            s=4,
            color="#D55E00",
            alpha=0.32,
            linewidths=0,
            label="BOEM/BSEE federal OCS platforms without a removal date",
            zorder=5,
        )
    ax.set_xlim(-96, -58)
    ax.set_ylim(20, 44.5)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(title)
    ax.grid(color="#D5D9DE", linewidth=0.5, alpha=0.6)
    if show_legend:
        ax.legend(loc="lower right", frameon=True, fontsize=8)


def make_figures(
    summary: pd.DataFrame,
    cells: pd.DataFrame,
    grid_cells: pd.DataFrame,
    land_shapefile: Path,
    output_dir: Path,
    platforms: pd.DataFrame | None = None,
) -> None:
    comparison_support = grid_cells[
        grid_cells["grid_resolution_degrees"].isin([0.5, 1.0])
        & (grid_cells["valid_30d_trajectories"] > 0)
    ]
    shared_norm = LogNorm(
        vmin=1,
        vmax=max(1, int(comparison_support["valid_30d_trajectories"].max())),
    )
    mappable = plt.cm.ScalarMappable(norm=shared_norm, cmap="viridis")
    mappable.set_array([])

    for resolution, filename in [
        (1.0, "region-audit-map.png"),
        (0.5, "region-audit-map-0p5.png"),
    ]:
        fig, ax = plt.subplots(figsize=(13, 7.2))
        draw_support_map(
            ax,
            grid_cells,
            resolution,
            land_shapefile,
            platforms,
            shared_norm,
            f"Distinct trajectories with an exact 30-day endpoint by {resolution:g}° origin cell",
        )
        colorbar = fig.colorbar(mappable, ax=ax, pad=0.015)
        colorbar.set_label("Unique 30-day-valid trajectories (shared log scale)")
        fig.tight_layout()
        fig.savefig(output_dir / filename, dpi=180)
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(18, 6.8), constrained_layout=True)
    for ax, resolution in zip(axes, [0.5, 1.0]):
        draw_support_map(
            ax,
            grid_cells,
            resolution,
            land_shapefile,
            platforms,
            shared_norm,
            f"{resolution:g}° origin cells",
            show_legend=resolution == 1.0,
        )
    colorbar = fig.colorbar(mappable, ax=axes, pad=0.015, shrink=0.92)
    colorbar.set_label("Unique 30-day-valid trajectories (shared log scale)")
    fig.suptitle("0.5° versus 1° data support under the same 30-day rule", fontsize=15)
    fig.savefig(output_dir / "region-audit-map-0p5-vs-1deg.png", dpi=180)
    plt.close(fig)

    names = summary["region"].tolist()
    colors = [REGION_COLORS[name] for name in names]
    x = np.arange(len(names))
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))

    width = 0.24
    axes[0, 0].bar(x - width, summary["entering_trajectories"], width, label="Entering", color="#9AA0A6")
    axes[0, 0].bar(x, summary["valid_7d_trajectories"], width, label="Valid 7d", color="#56B4E9")
    axes[0, 0].bar(x + width, summary["valid_30d_trajectories"], width, label="Valid 30d", color="#0072B2")
    axes[0, 0].set_title("Distinct trajectory support")
    axes[0, 0].set_ylabel("Trajectories")
    axes[0, 0].legend()

    axes[0, 1].bar(x - width / 2, summary["valid_7d_pct"] * 100, width, label="7d", color="#56B4E9")
    axes[0, 1].bar(x + width / 2, summary["valid_30d_pct"] * 100, width, label="30d", color="#0072B2")
    axes[0, 1].set_title("Tracking availability after origin in zone")
    axes[0, 1].set_ylabel("Share of entering trajectories (%)")
    axes[0, 1].set_ylim(0, 100)
    axes[0, 1].legend()

    for i, threshold in enumerate([10, 25, 50]):
        axes[1, 0].bar(
            x + (i - 1) * width,
            summary[f"cells_valid30_ge_{threshold}"] / summary["one_degree_cells_touched"] * 100,
            width,
            label=f">={threshold}",
        )
    axes[1, 0].set_title("1° origin-cell support")
    axes[1, 0].set_ylabel("Touched cells meeting threshold (%)")
    axes[1, 0].set_ylim(0, 105)
    axes[1, 0].legend(title="Valid 30d trajectories")

    axes[1, 1].bar(x - width / 2, summary["median_effective_30d_destination_cells_ge25"], width, label="Effective destinations", color=colors)
    ax2 = axes[1, 1].twinx()
    ax2.plot(x + width / 2, summary["median_direction_concentration_30d_ge25"], "o-", color="#CC79A7", label="Direction concentration")
    axes[1, 1].set_title("30-day dispersion proxies (cells with >=25 tracks)")
    axes[1, 1].set_ylabel("Median effective destination cells")
    ax2.set_ylabel("Median direction concentration (0–1)")
    ax2.set_ylim(0, 1)

    for ax in axes.flat:
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=15, ha="right")
        ax.grid(axis="y", color="#D5D9DE", linewidth=0.5, alpha=0.6)
    fig.suptitle("Regional data-audit comparison", fontsize=15, y=1.01)
    fig.tight_layout()
    fig.savefig(output_dir / "region-audit-comparison.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_report(
    summary: pd.DataFrame,
    grid_sensitivity: pd.DataFrame,
    checks: dict[str, object],
    manifest: dict[str, object],
    output_dir: Path,
    platform_overlap: pd.DataFrame | None = None,
    platform_overlap_half_degree: pd.DataFrame | None = None,
    platform_count: int | None = None,
) -> None:
    display = summary[
        [
            "region",
            "entering_trajectories",
            "valid_7d_trajectories",
            "valid_7d_pct",
            "valid_30d_trajectories",
            "valid_30d_pct",
            "drogued_valid_30d_trajectories",
            "cells_valid30_ge_25",
            "one_degree_cells_touched",
            "median_valid30_per_touched_cell",
        ]
    ].copy()
    display["valid_7d_pct"] = (display["valid_7d_pct"] * 100).round(1)
    display["valid_30d_pct"] = (display["valid_30d_pct"] * 100).round(1)
    display.columns = [
        "Region",
        "Entering",
        "Valid 7d",
        "Valid 7d (%)",
        "Valid 30d",
        "Valid 30d (%)",
        "Drogued valid 30d",
        "1° cells >=25 valid 30d",
        "1° cells touched",
        "Median valid 30d per touched cell",
    ]
    headers = display.columns.tolist()
    table_rows = []
    for row in display.itertuples(index=False, name=None):
        formatted = []
        for value in row:
            if isinstance(value, float):
                formatted.append(f"{value:.1f}")
            else:
                formatted.append(str(value))
        table_rows.append(formatted)
    markdown_table = "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
            *("| " + " | ".join(row) + " |" for row in table_rows),
        ]
    )
    sensitivity_display = grid_sensitivity.copy()
    sensitivity_display["grid_resolution_degrees"] = sensitivity_display[
        "grid_resolution_degrees"
    ].map(lambda value: f"{value:g}°")
    sensitivity_display = sensitivity_display[
        [
            "region",
            "grid_resolution_degrees",
            "cells_touched",
            "cells_valid30_ge_10",
            "cells_valid30_ge_25",
            "cells_valid30_ge_50",
            "cells_drogued_valid30_ge_25",
            "median_valid30_per_touched_cell",
            "median_drogued_valid30_per_touched_cell",
        ]
    ]
    sensitivity_display.columns = [
        "Region",
        "Grid",
        "Cells touched",
        "Cells >=10 valid 30d",
        "Cells >=25 valid 30d",
        "Cells >=50 valid 30d",
        "Cells >=25 drogued valid 30d",
        "Median valid 30d per touched cell",
        "Median drogued valid 30d per touched cell",
    ]
    sensitivity_headers = sensitivity_display.columns.tolist()
    sensitivity_rows = []
    for row in sensitivity_display.itertuples(index=False, name=None):
        sensitivity_rows.append(
            [f"{value:.1f}" if isinstance(value, float) else str(value) for value in row]
        )
    sensitivity_table = "\n".join(
        [
            "| " + " | ".join(sensitivity_headers) + " |",
            "| " + " | ".join(["---"] * len(sensitivity_headers)) + " |",
            *("| " + " | ".join(row) + " |" for row in sensitivity_rows),
        ]
    )
    platform_section = ""
    if platform_overlap is not None and platform_count is not None:
        current_platforms_in_touched_cells = int(
            platform_overlap.loc[
                platform_overlap["entering_trajectories"] > 0, "current_platforms"
            ].sum()
        )
        joint_cells = platform_overlap[
            (platform_overlap["current_platforms"] > 0)
            & (platform_overlap["valid_30d_trajectories"] >= 25)
        ]
        platform_section = f"""
## BOEM platform overlap

The BOEM/BSEE federal OCS layer contains **{platform_count:,} platform points without a removal date** inside the North-Central Gulf screening box. Of these, **{current_platforms_in_touched_cells:,}** fall in a 1° cell touched by at least one audited drifter trajectory. These points are application-context evidence, not drifter observations. **{len(joint_cells)}** 1° cells contain at least one such platform and at least 25 unique 30-day-valid drifter trajectories. State-water facilities are outside the layer's stated scope.

The overlap table is saved as `north-central-gulf-platform-cell-overlap.csv`. Candidate source cells should be selected from this table only after checking temporal and experiment concentration.
"""
        if platform_overlap_half_degree is not None:
            comparison_rows = []
            for label, overlap in [
                ("0.5°", platform_overlap_half_degree),
                ("1°", platform_overlap),
            ]:
                platform_cells_only = overlap[overlap["current_platforms"] > 0]
                total_platforms = int(platform_cells_only["current_platforms"].sum())
                for threshold in (10, 25, 50):
                    eligible = platform_cells_only[
                        platform_cells_only["valid_30d_trajectories"] >= threshold
                    ]
                    represented = int(eligible["current_platforms"].sum())
                    comparison_rows.append(
                        {
                            "grid": label,
                            "minimum_valid_30d": threshold,
                            "qualifying_platform_cells": len(eligible),
                            "platforms_in_qualifying_cells": represented,
                            "share_of_platforms_pct": 100 * represented / total_platforms,
                        }
                    )
            comparison = pd.DataFrame(comparison_rows)
            comparison.to_csv(
                output_dir / "north-central-gulf-platform-resolution-comparison.csv",
                index=False,
            )
            comparison_lines = [
                "| Grid | Minimum valid 30d | Qualifying platform cells | Platforms in qualifying cells | Share of 1,108 platforms |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
            for row in comparison.itertuples(index=False):
                comparison_lines.append(
                    f"| {row.grid} | {row.minimum_valid_30d} | "
                    f"{row.qualifying_platform_cells} | {row.platforms_in_qualifying_cells} | "
                    f"{row.share_of_platforms_pct:.1f}% |"
                )
            platform_section += """

### Platform-cell resolution comparison

""" + "\n".join(comparison_lines) + """

`Platforms in qualifying cells` means platform points located inside a cell that meets the stated trajectory threshold. It is not a spill count or an additional trajectory count.
"""
    report = f"""# DATA3001 Phase 1 Region and Data Audit

## Status

This is a screening audit, not the final model dataset. It tests whether the three proposed functional zones have enough independent drifter trajectories to justify further work.

## Source and grain

- Source: NOAA Global Drifter Program six-hour ragged trajectory collection
- DOI: `{manifest.get('source_doi')}`
- Source version: `{manifest.get('source_version')}`
- Coverage: `{manifest.get('time_coverage_start')}` to `{manifest.get('time_coverage_end')}`
- Source trajectories: `{manifest.get('trajectory_rows'):,}`
- Source observations: `{manifest.get('observation_rows'):,}`
- Audit grain: unique trajectory within a proposed zone, plus unique trajectory per 1° origin cell

An entering trajectory has at least one finite position inside a zone. A 7-day or 30-day-valid trajectory has at least one origin inside the zone and a finite position at the exact horizon on the same six-hour trajectory. The future endpoint may be outside the zone. Leaving a zone is therefore not misclassified as data loss.

## Preliminary screening boundaries

- **North-Central Gulf:** 25.0–30.0°N, 92.5–85.0°W
- **Florida-Bahamas:** 22.5–30.0°N, 85.0–75.0°W
- **Gulf Stream Corridor:** a non-rectangular corridor from offshore Florida to approximately 42.5°N in the western North Atlantic; exact vertices are recorded in `region_data_audit.py`

These are non-overlapping analytical screening zones, not claims that ocean-current systems have hard boundaries.

## Core results

{markdown_table}

{platform_section}

## Grid-resolution sensitivity

Transition-block support changes materially with grid size. The 1° cell results above are therefore a screening view rather than a frozen model resolution.

{sensitivity_table}

## Integrity checks

```json
{json.dumps(checks, indent=2)}
```

## Interpretation rules

- Counts are unique trajectories, not six-hour observations.
- A trajectory can enter more than one functional zone, so regional totals overlap and must not be summed.
- Within the cell table, a trajectory is counted once per origin cell and may appear in more than one cell if it traverses the study area.
- A 1° cell threshold of 25 valid 30-day trajectories is a transparent screening threshold, not a universal statistical guarantee.
- Destination entropy and direction concentration are exploratory dispersion proxies. They do not by themselves measure full oceanographic complexity.
- Region totals are not directly comparable without considering zone area and origin-cell support.
- Drogued-valid counts require drogue status at both the origin and horizon endpoint; they do not prove uninterrupted drogue attachment between those times.

## Evidence-based findings

1. **The statement that the North-Central Gulf has no drifter data is false for the audited NOAA dataset.** The zone contains hundreds of entering trajectories and substantial exact 7-day and 30-day support.
2. **North-Central Gulf is not automatically a high-quality release zone at every location.** Support must still be checked cell by cell, particularly near the coast and at the edges of the zone.
3. **Florida-Bahamas has more trajectories than North-Central Gulf, but raw volume alone does not make it the best first pilot.** Pilot-cell selection should require high support, acceptable trajectory concentration, and a clear application scenario.
4. **Gulf Stream Corridor has the strongest regional support in this screening geometry.** Its larger area and corridor definition contribute to the raw total, so cell-level support is the more relevant comparison.
5. **Starting with the most statistically dispersed zone is not inherently easier.** A high-support but relatively stable cell is preferable for validating the pipeline before testing more dispersed or multimodal locations.
6. **Transition-cell resolution changes the feasibility conclusion.** At 0.25°, North-Central Gulf has no cell with 50 or more unique 30-day-valid trajectories, while it has 21 such cells at 1°. The project must select cell size together with its minimum-support rule rather than after modeling begins.
7. **The 0.5° grid preserves more spatial structure but fragments the platform-source evidence.** In North-Central Gulf, no platform-containing 0.5° cell has 50 valid 30-day trajectories, and only 41 of 1,108 platform points fall in a 0.5° cell with at least 25. For a single-cell empirical pilot, 1° is the safer primary resolution; 0.5° should remain a sensitivity analysis or be used with explicit spatial pooling.

## Next decisions

- Retain the three-zone functional classification for screening, but describe it as source, transition and downstream zones rather than separate oceans.
- Carry forward two or three North-Central Gulf source-cell candidates from `north-central-gulf-platform-cell-overlap.csv`; do not select from regional totals alone.
- Review the candidate cells' season, year, experiment and drogue-status concentration before freezing one pilot cell.
- Choose the transition-cell resolution and minimum support together; retain a coarser fallback if a fine grid fragments the data.
- Use 1° for the first single-cell empirical baseline and compare it with 0.5° before any final-resolution claim.
- Confirm whether 7 and 30 days are sufficient for the intended downstream question.
- Only then freeze the first pilot cell and begin model construction.
"""
    (output_dir / "region-audit-report.md").write_text(report, encoding="utf-8")


def main() -> None:
    args = parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    summary, cells, grid_sensitivity, grid_cells, checks = analyse(args)
    platforms, platform_cells = load_boem_platforms(args.boem_platforms)
    platform_overlap = None
    if platform_cells is not None:
        platform_overlap = (
            cells[cells["region"] == "North-Central Gulf"]
            .merge(platform_cells, on=["lon_min", "lat_min"], how="outer")
        )
        platform_overlap["region"] = platform_overlap["region"].fillna("North-Central Gulf")
        platform_overlap["lon_max"] = platform_overlap["lon_max"].fillna(
            platform_overlap["lon_min"] + 1
        )
        platform_overlap["lat_max"] = platform_overlap["lat_max"].fillna(
            platform_overlap["lat_min"] + 1
        )
        count_columns = [
            "entering_trajectories",
            "valid_7d_trajectories",
            "valid_30d_trajectories",
            "drogued_valid_30d_trajectories",
            "observed_30d_destination_cells",
            "active_valid_30d_years",
            "current_platforms",
        ]
        platform_overlap[count_columns] = platform_overlap[count_columns].fillna(0)
        platform_overlap[count_columns] = platform_overlap[count_columns].astype(int)
        platform_overlap = platform_overlap.sort_values(
            ["current_platforms", "valid_30d_trajectories"], ascending=False
        )
        platform_overlap.to_csv(
            args.output_dir / "north-central-gulf-platform-cell-overlap.csv", index=False
        )
        half_degree_platform_cells = platform_cells_at_resolution(platforms, 0.5)
        half_degree_overlap = (
            grid_cells[
                (grid_cells["region"] == "North-Central Gulf")
                & (grid_cells["grid_resolution_degrees"] == 0.5)
            ]
            .merge(
                half_degree_platform_cells,
                on=["lon_min", "lat_min"],
                how="outer",
            )
        )
        half_degree_overlap["region"] = half_degree_overlap["region"].fillna(
            "North-Central Gulf"
        )
        half_degree_overlap["grid_resolution_degrees"] = half_degree_overlap[
            "grid_resolution_degrees"
        ].fillna(0.5)
        half_degree_overlap["lon_max"] = half_degree_overlap["lon_max"].fillna(
            half_degree_overlap["lon_min"] + 0.5
        )
        half_degree_overlap["lat_max"] = half_degree_overlap["lat_max"].fillna(
            half_degree_overlap["lat_min"] + 0.5
        )
        half_degree_count_columns = [
            "entering_trajectories",
            "valid_7d_trajectories",
            "valid_30d_trajectories",
            "drogued_valid_30d_trajectories",
            "current_platforms",
        ]
        half_degree_overlap[half_degree_count_columns] = half_degree_overlap[
            half_degree_count_columns
        ].fillna(0).astype(int)
        half_degree_overlap = half_degree_overlap.sort_values(
            ["current_platforms", "valid_30d_trajectories"], ascending=False
        )
        half_degree_overlap.to_csv(
            args.output_dir / "north-central-gulf-platform-cell-overlap-0p5.csv",
            index=False,
        )
    summary.to_csv(args.output_dir / "region-audit-summary.csv", index=False)
    cells.to_csv(args.output_dir / "region-audit-cell-support.csv", index=False)
    grid_sensitivity.to_csv(
        args.output_dir / "region-audit-grid-sensitivity.csv", index=False
    )
    grid_cells.to_csv(args.output_dir / "region-audit-grid-cell-support.csv", index=False)
    (args.output_dir / "region-audit-checks.json").write_text(
        json.dumps(checks, indent=2) + "\n", encoding="utf-8"
    )
    make_figures(
        summary,
        cells,
        grid_cells,
        args.land_shapefile,
        args.output_dir,
        platforms,
    )
    write_report(
        summary,
        grid_sensitivity,
        checks,
        manifest,
        args.output_dir,
        platform_overlap,
        half_degree_overlap if platform_cells is not None else None,
        len(platforms) if platforms is not None else None,
    )
    print(summary.to_string(index=False))
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
