"""Seven-day regional release using the frozen 22-component network.

No fitting, selection, scoring, or final-test data access. Each source cell is
integrated separately over its empirical training-origin prior and complete
conditional mixture. Scrambled Sobol replicates quantify numerical error only.
Run from DATA3001 with work_place/.venv/bin/python and PYTHONDONTWRITEBYTECODE=1.
"""
from pathlib import Path
import hashlib
import json
import math
import sys
import time

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import shape
from scipy.stats import qmc
from pyproj import Geod

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
WORK = ROOT / 'work_place'
sys.path.insert(0, str(WORK / 'src'))
from data3001.modelling.continuous_models.conditional_mdn_s5_e4_inference import from_checkpoint

RUN = WORK / 'results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1'
TRAIN = WORK / 'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/training_coordinates.parquet'
CHECKPOINT_SHA = '216f92b678e25b1c804a7f0a1928779b9233ff22f7140536e825969df6d176b0'
LEVELS = (16, 18)
REPLICATES = 8
BASE_SEED = 20261121
LON_EDGES = np.arange(-85., -55. + .25, .5)
LAT_EDGES = np.arange(20., 45. + .25, .5)
VIEW = (-82., 27., -63., 43.)
NX, NY = len(LON_EDGES) - 1, len(LAT_EDGES) - 1
GRID_SIZE = NX * NY + 1  # Last entry retains all endpoints outside the map grid.
CATEGORIES = ['R_water', 'D_water_outside_R', 'D_land', 'outside_D']
DIRECTIONS = ['north_of_R', 'east_of_R_below_north_edge', 'south_of_R_west_of_east_edge', 'other_R_edge_water']
SCENARIOS = ['area_release', 'historical_origins', 'area_supported_only']
GEOD = Geod(ellps='WGS84')
SOURCES = {}
OPENED = set()


def audit_open(event, args):
    if event != 'open' or not isinstance(args[0], (str, bytes)):
        return
    path = Path(args[0]).resolve()
    if not path.is_relative_to(ROOT):
        return
    name = str(path.relative_to(ROOT))
    if '/restricted_test/' in '/' + name or name.startswith('work_place/data/test/'):
        raise PermissionError('Final-test access is prohibited for this analysis')
    OPENED.add(name)


sys.addaudithook(audit_open)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def source(path, expected=None):
    actual = sha(path)
    if expected is not None:
        assert actual == expected, str(path)
    SOURCES[str(path.relative_to(ROOT))] = actual
    return path


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def grid_indices(lon, lat):
    x = np.floor((lon - LON_EDGES[0]) / .5).astype(int)
    y = np.floor((lat - LAT_EDGES[0]) / .5).astype(int)
    inside = (x >= 0) & (x < NX) & (y >= 0) & (y < NY)
    return np.where(inside, y * NX + x, GRID_SIZE - 1)


def geographic(origin, vectors):
    radius = np.hypot(vectors[:, 0], vectors[:, 1])
    bearing = np.degrees(np.arctan2(vectors[:, 0], vectors[:, 1]))
    lon, lat, _ = GEOD.fwd(origin[:, 0], origin[:, 1], bearing, radius * 1000.)
    assert np.isfinite(lon).all() and np.isfinite(lat).all()
    return lon, lat


def integrate_cell(cell, origins, parameters, release, domain, land):
    """Return nested numerical levels, sharing draws for both release scenarios."""
    n = len(origins)
    cumulative = np.cumsum(parameters['weights'], axis=1)
    cumulative[:, -1] = 1.
    lower = np.linalg.cholesky(parameters['covariances_km2'])
    means = parameters['means_km']
    region = np.zeros((len(LEVELS), REPLICATES, 4))
    grids = np.zeros((len(LEVELS), REPLICATES, GRID_SIZE))
    outside_view = np.zeros((len(LEVELS), REPLICATES))
    directions = np.zeros((len(LEVELS), REPLICATES, 4))
    for replicate in range(REPLICATES):
        seed = int(np.random.SeedSequence([BASE_SEED, int(cell), replicate]).generate_state(1)[0])
        u = qmc.Sobol(4, scramble=True, rng=np.random.default_rng(seed)).random_base2(LEVELS[-1])
        origin_index = np.minimum((u[:, 0] * n).astype(int), n - 1)
        component = np.sum(u[:, 1, None] >= cumulative[origin_index], axis=1)
        radius = np.sqrt(-2 * np.log1p(-u[:, 2]))
        angle = 2 * np.pi * u[:, 3]
        normal = np.column_stack([radius * np.cos(angle), radius * np.sin(angle)])
        vectors = means[origin_index, component] + np.einsum('nij,nj->ni', lower[origin_index, component], normal)
        lon, lat = geographic(origins[origin_index], vectors)
        in_d = shapely.intersects_xy(domain, lon, lat)
        on_land = shapely.intersects_xy(land, lon, lat)
        in_r = shapely.intersects_xy(release, lon, lat)
        # Outside D has priority; all categories are mutually exclusive.
        category = np.full(len(lon), 3)
        category[in_d & on_land] = 2
        category[in_d & ~on_land & ~in_r] = 1
        category[in_d & ~on_land & in_r] = 0
        # Descriptive endpoint subregions, not crossing locations or trajectories.
        direction = np.full(len(lon), -1)
        outside_r_water = category == 1
        direction[outside_r_water] = 3
        direction[outside_r_water & (lat >= 35.5)] = 0
        direction[outside_r_water & (lat < 35.5) & (lon >= -73.)] = 1
        direction[outside_r_water & (lat < 30.) & (lon < -73.)] = 2
        grid = grid_indices(lon, lat)
        off_view = ~((lon >= VIEW[0]) & (lon < VIEW[2]) & (lat >= VIEW[1]) & (lat < VIEW[3]))
        for level, power in enumerate(LEVELS):
            count = 2 ** power
            region[level, replicate] = np.bincount(category[:count], minlength=4) / count
            grids[level, replicate] = np.bincount(grid[:count], minlength=GRID_SIZE) / count
            outside_view[level, replicate] = np.mean(off_view[:count])
            d = direction[:count]
            directions[level, replicate] = np.bincount(d[d >= 0], minlength=4) / count
    assert np.allclose(region.sum(axis=-1), 1., atol=1e-14, rtol=0)
    assert np.allclose(grids.sum(axis=-1), 1., atol=1e-14, rtol=0)
    assert np.allclose(directions.sum(axis=-1), region[:, :, 1], atol=1e-14, rtol=0)
    return region, grids, outside_view, directions


def main():
    started = time.monotonic()
    OUT.mkdir(exist_ok=True, parents=True)
    protected = list((ROOT / 'Final Report/drafts').glob('*.md'))
    protected += [ROOT / 'Final Report/figures/W12_prediction_cases/figure_w12_four_cases_zh.png']
    before_drafts = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    registry = json.loads(source(WORK / 'configs/assets.json').read_text())['assets']

    def asset(name):
        row = registry[name]
        return source(WORK / row['path'], row['sha256'])

    source(asset('english_contract'))
    release = shape(json.loads(asset('release_R').read_text())['features'][0]['geometry'])
    domain = shape(json.loads(asset('transport_D').read_text())['features'][0]['geometry'])
    land = shapely.from_wkb(asset('land_mask_high').read_bytes())
    for geometry in [release, domain, land]:
        shapely.prepare(geometry)
    states = pd.read_parquet(asset('state_index'))
    cells = states.loc[(states.resolution == 1.) & (states.wet_area_in_R > 0)].copy().sort_values('cell')
    assert np.allclose(cells.whole_R_release_weight, cells.wet_area_in_R / cells.wet_area_in_R.sum(), atol=1e-14, rtol=0)
    assert abs(cells.whole_R_release_weight.sum() - 1) < 1e-14
    train = pd.read_parquet(source(TRAIN), columns=['id', 'origin_source_obs', 'origin_time_UTC', 'horizon_days', 'origin_cell_1', 'lon', 'lat'])
    assert len(train) == 265393 and train.id.nunique() == 338
    assert train.horizon_days.eq(7).all() and train.origin_time_UTC.dt.year.between(2001, 2019).all()
    assert not train.duplicated(['id', 'origin_source_obs', 'horizon_days']).any()
    assert shapely.intersects_xy(release, train.lon.to_numpy(), train.lat.to_numpy()).all()
    assert not shapely.intersects_xy(land, train.lon.to_numpy(), train.lat.to_numpy()).any()
    calculated_cells = np.floor(train.lon.to_numpy() + 180).astype(int) + 360 * np.floor(train.lat.to_numpy() + 90).astype(int)
    assert np.array_equal(calculated_cells, train.origin_cell_1.to_numpy())
    assert set(train.origin_cell_1) <= set(cells.cell)
    train = train.sort_values(['origin_cell_1', 'id', 'origin_source_obs'], kind='stable').reset_index(drop=True)
    counts = train.groupby('origin_cell_1').agg(origin_count=('id', 'size'), independent_drifters=('id', 'nunique'))
    dominance = train.groupby(['origin_cell_1', 'id']).size().groupby(level=0).max() / counts.origin_count
    cells = cells.merge(counts, how='left', left_on='cell', right_index=True)
    cells[['origin_count', 'independent_drifters']] = cells[['origin_count', 'independent_drifters']].fillna(0).astype(int)
    cells['largest_drifter_fraction'] = cells.cell.map(dominance)
    cells['supported'] = cells.origin_count > 0
    unresolved = float(cells.loc[~cells.supported, 'whole_R_release_weight'].sum())
    cells['historical_origin_weight'] = cells.origin_count / len(train)
    cells['area_supported_only_weight'] = np.where(cells.supported, cells.whole_R_release_weight / (1 - unresolved), 0.)
    cells.to_csv(OUT / 'release_cells.csv', index=False)
    weight_by_cell = cells.set_index('cell').whole_R_release_weight
    count_by_cell = counts.origin_count
    train['area_release_weight'] = train.origin_cell_1.map(weight_by_cell) / train.origin_cell_1.map(count_by_cell)
    train['historical_origin_weight'] = 1. / len(train)
    train['area_supported_only_weight'] = train.area_release_weight / (1 - unresolved)
    assert abs(train.area_release_weight.sum() + unresolved - 1.) < 1e-13
    assert abs(train.historical_origin_weight.sum() - 1.) < 1e-13
    reconstructed = train.groupby('origin_cell_1').area_release_weight.sum()
    assert np.allclose(reconstructed, weight_by_cell.loc[reconstructed.index], atol=1e-14, rtol=0)
    train.to_parquet(OUT / 'release_origins.parquet', index=False)

    manifest_path = source(RUN / 'C_outer/K22/manifest.json')
    manifest = json.loads(manifest_path.read_text())
    checkpoint = source(RUN / manifest['full_refit']['checkpoint']['path'], CHECKPOINT_SHA)
    assert set(manifest['full_refit']['identity']['optimization_ids']) == set(train.id)
    predictor = from_checkpoint(checkpoint, sha256=CHECKPOINT_SHA)
    assert predictor.metadata['K'] == 22 and predictor.metadata['horizon_days'] == 7
    assert predictor.metadata['role'] == 'C_outer'
    # Reproduce saved case parameters before creating any regional predictions.
    saved = np.load(source(RUN / 'C_outer/K22/parameters.npz', manifest['parameters']['sha256']))
    positions = np.array([0, 3088, 24705, 12820])
    verification = predictor.mixture(saved['origins'][positions])
    parameter_differences = {}
    for current, old in [('weights', 'pi'), ('means_km', 'mu'), ('covariances_km2', 'cov')]:
        parameter_differences[current] = float(np.max(np.abs(verification[current] - saved[old][positions])))
        assert np.allclose(verification[current], saved[old][positions], rtol=1e-10, atol=1e-10)
    saved.close()
    supported = cells[cells.supported].copy()
    cell_weights = supported[['whole_R_release_weight', 'historical_origin_weight', 'area_supported_only_weight']].to_numpy().T
    initial = np.zeros((3, GRID_SIZE))
    idx = grid_indices(train.lon.to_numpy(), train.lat.to_numpy())
    for s, column in enumerate(['area_release_weight', 'historical_origin_weight', 'area_supported_only_weight']):
        initial[s] = np.bincount(idx, weights=train[column], minlength=GRID_SIZE)
    regions, grids, views, directions = [], [], [], []
    parameter_checks = []
    for number, cell in enumerate(supported.cell):
        rows = train[train.origin_cell_1.eq(cell)]
        origins = rows[['lon', 'lat']].to_numpy()
        packet = predictor.mixture(origins)
        weight_error = float(np.abs(packet['weights'].sum(axis=1) - 1.).max())
        minimum_eigenvalue = float(np.linalg.eigvalsh(packet['covariances_km2']).min())
        assert weight_error < 1e-12 and minimum_eigenvalue > 0
        assert all(np.isfinite(v).all() for v in packet.values())
        region, grid, view, direction = integrate_cell(cell, origins, packet, release, domain, land)
        regions.append(region); grids.append(grid); views.append(view)
        directions.append(direction)
        parameter_checks.append({'cell': int(cell), 'max_weight_sum_error': weight_error, 'min_covariance_eigenvalue': minimum_eigenvalue})
        print(f'{number + 1}/{len(supported)} cells integrated; elapsed {time.monotonic() - started:.1f}s', flush=True)
    regions = np.stack(regions); grids = np.stack(grids); views = np.stack(views)
    directions = np.stack(directions)
    aggregate_region = np.einsum('sc,clrk->slrk', cell_weights, regions)
    aggregate_grid = np.einsum('sc,clrg->slrg', cell_weights, grids)
    aggregate_view = np.einsum('sc,clr->slr', cell_weights, views)
    aggregate_direction = np.einsum('sc,clrk->slrk', cell_weights, directions)
    assert np.allclose(aggregate_direction.sum(axis=-1), aggregate_region[:, :, :, 1], atol=1e-12, rtol=0)
    unresolved_by_scenario = np.array([unresolved, 0., 0.])
    mass_errors = np.abs(aggregate_region.sum(axis=-1) + unresolved_by_scenario[:, None, None] - 1.)
    assert mass_errors.max() < 1e-12
    assert np.allclose(aggregate_grid.sum(axis=-1) + unresolved_by_scenario[:, None, None], 1., atol=1e-12, rtol=0)
    np.savez_compressed(OUT / 'integration_by_cell.npz', cells=supported.cell.to_numpy(), cell_weights=cell_weights,
        levels=LEVELS, regions=regions, grids=grids, outside_view=views, directions=directions, initial_grid=initial,
        lon_edges=LON_EDGES, lat_edges=LAT_EDGES)
    numerical_rows = []
    for s, scenario in enumerate(SCENARIOS):
        for l, power in enumerate(LEVELS):
            for rep in range(REPLICATES):
                numerical_rows.append({'scenario': scenario, 'points_per_cell': 2 ** power, 'replicate': rep,
                    **dict(zip(CATEGORIES, aggregate_region[s, l, rep])), 'unresolved': unresolved_by_scenario[s],
                    'outside_display_grid': aggregate_grid[s, l, rep, -1], 'outside_main_view': aggregate_view[s, l, rep]})
    pd.DataFrame(numerical_rows).to_csv(OUT / 'numerical_replicates.csv', index=False)
    result_rows = []
    for s, scenario in enumerate(SCENARIOS):
        fine = aggregate_region[s, -1]
        mean = fine.mean(axis=0)
        se = fine.std(axis=0, ddof=1) / np.sqrt(REPLICATES)
        difference = mean - aggregate_region[s, 0].mean(axis=0)
        for k, category in enumerate(CATEGORIES):
            result_rows.append({'scenario': scenario, 'category': category, 'probability': mean[k],
                'numerical_standard_error': se[k], 'fine_minus_coarse': difference[k]})
        result_rows.append({'scenario': scenario, 'category': 'unresolved', 'probability': unresolved_by_scenario[s],
            'numerical_standard_error': 0., 'fine_minus_coarse': 0.})
    probabilities = pd.DataFrame(result_rows)
    probabilities.to_csv(OUT / 'region_probabilities.csv', index=False)
    direction_rows = []
    for s, scenario in enumerate(SCENARIOS):
        for k, name in enumerate(DIRECTIONS):
            fine = aggregate_direction[s, -1, :, k]
            direction_rows.append({'scenario': scenario, 'subregion': name, 'probability': float(fine.mean()),
                'numerical_standard_error': float(fine.std(ddof=1) / np.sqrt(REPLICATES)),
                'fine_minus_coarse': float(fine.mean() - aggregate_direction[s, 0, :, k].mean())})
    pd.DataFrame(direction_rows).to_csv(OUT / 'outside_R_water_subregions.csv', index=False)
    yy, xx = np.meshgrid(LAT_EDGES[:-1], LON_EDGES[:-1], indexing='ij')
    grid_table = pd.DataFrame({'lon_min': xx.ravel(), 'lat_min': yy.ravel()})
    for s, scenario in enumerate(SCENARIOS):
        grid_table[scenario + '_initial'] = initial[s, :-1]
        grid_table[scenario + '_day7'] = aggregate_grid[s, -1, :, :-1].mean(axis=0)
        grid_table[scenario + '_change'] = grid_table[scenario + '_day7'] - grid_table[scenario + '_initial']
        grid_table[scenario + '_numerical_se'] = aggregate_grid[s, -1, :, :-1].std(axis=0, ddof=1) / np.sqrt(REPLICATES)
    grid_table.to_parquet(OUT / 'display_grid.parquet', index=False)
    for variable in ['area_release_day7', 'area_release_change']:
        grid_table.sort_values(variable, ascending=False).head(20).to_csv(OUT / ('top_' + variable + '.csv'), index=False)
    grid_table.sort_values('area_release_change').head(20).to_csv(OUT / 'largest_probability_decreases.csv', index=False)
    numerical = {
        'method': '8 independently scrambled Sobol sequences per supported source cell; 4 dimensions: empirical origin, component, Box-Muller pair',
        'base_seed': BASE_SEED, 'points_per_cell_coarse': 2 ** LEVELS[0], 'points_per_cell_fine': 2 ** LEVELS[-1],
        'replicates': REPLICATES, 'total_fine_endpoints': len(supported) * REPLICATES * 2 ** LEVELS[-1],
        'max_category_fine_minus_coarse': float(probabilities.fine_minus_coarse.abs().max()),
        'max_category_numerical_standard_error': float(probabilities.numerical_standard_error.max()),
        'max_grid_fine_minus_coarse': float(np.abs(aggregate_grid[:, -1].mean(axis=1) - aggregate_grid[:, 0].mean(axis=1)).max()),
        'max_grid_numerical_standard_error': float((aggregate_grid[:, -1].std(axis=1, ddof=1) / np.sqrt(REPLICATES)).max()),
        'max_probability_total_error': float(mass_errors.max()),
        'interpretation': 'numerical integration uncertainty conditional on frozen model and fixed empirical release prior; not model-estimation uncertainty',
    }
    # Predeclared tolerances support reporting region percentages to 0.1 pp.
    assert numerical['max_category_fine_minus_coarse'] < 0.0005
    assert numerical['max_category_numerical_standard_error'] < 0.00025
    assert numerical['max_grid_fine_minus_coarse'] < 0.001
    summary = {
        'status': 'complete', 'model': 'frozen 22-component mixture density network', 'horizon_days': 7,
        'training': {'origins': len(train), 'independent_drifters': int(train.id.nunique()),
            'start': str(train.origin_time_UTC.min()), 'end': str(train.origin_time_UTC.max())},
        'release': {'wet_cells': len(cells), 'supported_cells': len(supported), 'wet_area_km2': float(cells.wet_area_in_R.sum()),
            'unresolved_weight': unresolved, 'resolved_weight': 1. - unresolved,
            'all_origins_in_R_water': True, 'cell_membership_verified': True,
            'weights': 'whole_R_release_weight / eligible training origin count in each 1-degree cell',
            'unsupported_cells': cells.loc[~cells.supported, ['cell','lon_min','lat_min','wet_area_in_R','whole_R_release_weight']].to_dict('records'),
            'independent_drifters_min': int(supported.independent_drifters.min()),
            'independent_drifters_max': int(supported.independent_drifters.max()),
            'independent_drifters_median': float(supported.independent_drifters.median()),
            'under_20_drifters_area_weight': float(cells.loc[cells.independent_drifters.between(1,19), 'whole_R_release_weight'].sum())},
        'probabilities': result_rows, 'numerical': numerical,
        'outside_R_water_subregions': direction_rows,
        'subregion_definitions': {'north_of_R': 'D water outside R with latitude >= 35.5N, including northeast',
            'east_of_R_below_north_edge': 'D water outside R with longitude >= 73W and latitude < 35.5N',
            'south_of_R_west_of_east_edge': 'D water outside R with latitude < 30N and longitude < 73W',
            'other_R_edge_water': 'remaining D water outside the actual R polygon'},
        'saved_case_parameter_max_absolute_differences': parameter_differences,
        'parameter_checks': parameter_checks,
        'main_view': VIEW, 'display_grid_bounds': [LON_EDGES[0],LAT_EDGES[0],LON_EDGES[-1],LAT_EDGES[-1]],
        'outside_main_view': dict(zip(SCENARIOS, aggregate_view[:, -1].mean(axis=1).tolist())),
        'outside_display_grid': dict(zip(SCENARIOS, aggregate_grid[:, -1, :, -1].mean(axis=1).tolist())),
        'map_units': 'probability per 0.5-degree display cell; land probability retained',
        'land_policy': 'registered high-resolution coastline, matching regional wet-area release policy; outside D classified first',
        'new_training': False, 'model_selection': False, 'final_test_access': False,
        'w12_body_modified': False, 'elapsed_seconds': time.monotonic() - started,
    }
    for path, checksum in SOURCES.items():
        assert sha(ROOT / path) == checksum, path
    assert before_drafts == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    write_json('summary.json', summary)
    write_json('provenance.json', {'source_sha256': SOURCES, 'protected_drafts_and_figure_sha256': before_drafts,
        'checkpoint_sha256': CHECKPOINT_SHA, 'script_sha256': sha(Path(__file__)),
        'project_files_opened': sorted(OPENED), 'source_and_draft_hashes_unchanged': True,
        'authorization': '2026-11-21 user approved regional analysis and figures using frozen model; no training; prose pending review'})
    print(json.dumps({'summary': str(OUT / 'summary.json'), 'probabilities': result_rows, 'numerical': numerical}, indent=2), flush=True)


if __name__ == '__main__':
    main()
