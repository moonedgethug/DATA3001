"""Independent release-area, aggregation, and saved-model sampling checks."""
from pathlib import Path
import hashlib
import json
import sys
from importlib.metadata import version

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import box, shape
from pyproj import Geod

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
WORK = ROOT / 'work_place'
sys.path.insert(0, str(WORK / 'src'))
from data3001.modelling.continuous_models.conditional_mdn_s5_e4_inference import from_checkpoint


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def area(g, geod):
    if g.is_empty:
        return 0.
    if g.geom_type == 'Polygon':
        return abs(geod.geometry_area_perimeter(shapely.orient_polygons(g))[0]) / 1e6
    return sum(area(p, geod) for p in getattr(g, 'geoms', []))


def main():
    s = json.loads((OUT / 'summary.json').read_text())
    provenance = json.loads((OUT / 'provenance.json').read_text())
    assert s['status'] == 'complete'
    for path, checksum in provenance['source_sha256'].items():
        assert sha(ROOT / path) == checksum, path
    for path, checksum in provenance['protected_drafts_and_figure_sha256'].items():
        assert sha(ROOT / path) == checksum, path
    assert sha(OUT / 'run_analysis.py') == provenance['script_sha256']
    assets = json.loads((WORK / 'configs/assets.json').read_text())['assets']
    def asset(name):
        return WORK / assets[name]['path']
    r = shape(json.loads(asset('release_R').read_text())['features'][0]['geometry'])
    d = shape(json.loads(asset('transport_D').read_text())['features'][0]['geometry'])
    land = shapely.from_wkb(asset('land_mask_high').read_bytes())
    for g in [r, d, land]:
        shapely.prepare(g)
    cells = pd.read_csv(OUT / 'release_cells.csv')
    origins = pd.read_parquet(OUT / 'release_origins.parquet')
    recomputed = []
    geod = Geod(ellps='WGS84')
    for row in cells.itertuples():
        wet = box(row.lon_min, row.lat_min, row.lon_min + 1, row.lat_min + 1).difference(land).intersection(r)
        recomputed.append(area(wet, geod))
    area_error = float(np.abs(np.asarray(recomputed) - cells.wet_area_in_R).max())
    assert area_error < 1e-5
    weight_error = float(np.abs(np.asarray(recomputed) / np.sum(recomputed) - cells.whole_R_release_weight).max())
    assert weight_error < 1e-10
    assert cells.origin_count.sum() == len(origins) == 265393
    assert origins.id.nunique() == 338
    assert np.isclose(origins.area_release_weight.sum() + s['release']['unresolved_weight'], 1., atol=1e-12, rtol=0)
    numerical = np.load(OUT / 'integration_by_cell.npz')
    scenarios = ['area_release', 'historical_origins', 'area_supported_only']
    categories = ['R_water','D_water_outside_R','D_land','outside_D']
    summary = pd.read_csv(OUT / 'region_probabilities.csv')
    grid = pd.read_parquet(OUT / 'display_grid.parquet')
    max_reconstruction_error = 0.
    for j, scenario in enumerate(scenarios):
        predicted = np.average(numerical['regions'][:, -1].mean(axis=1), weights=numerical['cell_weights'][j], axis=0)
        predicted *= numerical['cell_weights'][j].sum()
        expected = summary[summary.scenario.eq(scenario)].set_index('category').loc[categories,'probability'].to_numpy()
        max_reconstruction_error = max(max_reconstruction_error, float(np.abs(predicted - expected).max()))
        assert np.allclose(predicted, expected, atol=1e-13, rtol=0)
        unresolved = float(summary[(summary.scenario == scenario) & (summary.category == 'unresolved')].probability.iloc[0])
        assert abs(expected.sum() + unresolved - 1.) < 1e-12
        assert abs(grid[scenario + '_day7'].sum() + s['outside_display_grid'][scenario] + unresolved - 1.) < 1e-12
        assert abs(grid[scenario + '_initial'].sum() + unresolved - 1.) < 1e-12
        assert np.allclose(grid[scenario + '_change'], grid[scenario + '_day7'] - grid[scenario + '_initial'], atol=1e-14, rtol=0)
    # Different random generator, normal generator, public sampling API, and
    # geometry predicate from the integration code; never refit a model.
    checkpoint = WORK / 'results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1/C_outer/K22/full_refit/checkpoint.pt'
    predictor = from_checkpoint(checkpoint, sha256=provenance['checkpoint_sha256'])
    independent = np.zeros(4)
    variance = np.zeros(4)
    samples_per_cell = 8192
    for row in cells[cells.supported].itertuples():
        source = origins[origins.origin_cell_1.eq(row.cell)][['lon','lat']].to_numpy()
        rng = np.random.default_rng(np.random.SeedSequence([20261122, int(row.cell)]))
        selected = source[rng.integers(0, len(source), samples_per_cell)]
        endpoints = predictor.sample(selected, count=1, seed=int(row.cell) + 20261122)[:, 0]
        points = shapely.points(endpoints)
        in_d = shapely.covers(d, points)
        in_r = shapely.covers(r, points)
        on_land = shapely.covers(land, points)
        masks = [in_d & ~on_land & in_r, in_d & ~on_land & ~in_r, in_d & on_land, ~in_d]
        assert np.all(np.asarray(masks).sum(axis=0) == 1)
        proportions = np.array([mask.mean() for mask in masks])
        independent += row.whole_R_release_weight * proportions
        variance += row.whole_R_release_weight ** 2 * proportions * (1 - proportions) / (samples_per_cell - 1)
    primary = summary[summary.scenario.eq('area_release')].set_index('category').loc[categories]
    difference = independent - primary.probability.to_numpy()
    numerical_se = np.sqrt(variance)
    tolerance = 6 * np.hypot(numerical_se, primary.numerical_standard_error.to_numpy()) + 1e-5
    assert (np.abs(difference) <= tolerance).all()
    result = {'status': 'passed', 'recomputed_max_wet_area_error_km2': area_error,
        'recomputed_max_release_weight_error': weight_error, 'max_aggregation_reconstruction_error': max_reconstruction_error,
        'independent_sampler': {'method': 'Existing Predictor.sample, independent random origin selection, existing geographic transform; covers predicates',
            'samples_per_supported_cell': samples_per_cell, 'total_samples': samples_per_cell * int(cells.supported.sum()),
            'probabilities': dict(zip(categories, independent.tolist())), 'difference_from_primary': dict(zip(categories, difference.tolist())),
            'numerical_standard_error': dict(zip(categories, numerical_se.tolist())),
            'check_tolerance': dict(zip(categories, tolerance.tolist()))},
        'source_and_draft_hashes_unchanged': True, 'no_training': True, 'final_test_access': False,
        'scripts_sha256': {p.name: sha(p) for p in OUT.glob('*.py')},
        'software_versions': {'python': sys.version, **{name:version(name) for name in ['numpy','pandas','scipy','shapely','pyproj','torch','matplotlib','pyarrow']}}}
    for path, checksum in provenance['source_sha256'].items():
        assert sha(ROOT / path) == checksum, path
    for path, checksum in provenance['protected_drafts_and_figure_sha256'].items():
        assert sha(ROOT / path) == checksum, path
    (OUT / 'verification.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
