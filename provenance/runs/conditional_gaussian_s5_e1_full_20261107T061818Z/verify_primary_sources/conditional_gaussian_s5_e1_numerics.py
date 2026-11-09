"""Matched empirical/Gaussian scoring and independent region-mass checks."""
import time
import numpy as np

from data3001.modelling.baselines import position_error_s4_e8 as old
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1 as gaussian

MODELS = ('ExactPoint', 'EndpointCI', 'LocalGaussian')


def id_weights(ids):
    _, inverse, counts = np.unique(ids, return_inverse=True, return_counts=True)
    return 1/(len(counts)*counts[inverse])


def boundary_atom(xy, atomic, region):
    delta = xy-np.asarray(region['centre'])
    distance = np.einsum('ij,jk,ik->i', delta, np.asarray(region['inverse']), delta)
    included = old.inside_region(xy, region)
    return float(np.mean(atomic & included & (np.abs(distance-region['cutoff']) <= 1e-12)))


def _region(points, weights=None):
    return old.fit_region(opt.xy(points), weights)


def _point_mass(region, pool):
    probability = float(np.mean(old.inside_region(pool.xy, region)))
    atom = boundary_atom(pool.xy, np.ones(len(pool.points), bool), region)
    return dict(probability=probability, lower=probability, upper=probability, radius=0.,
                boundary_atom=atom, discrepancy=max(.9-probability, probability-.9-atom, 0.), diagnostic=0.)


def build_regions(pool, packet, count, key, geography=None, point=None, profile=None):
    profile = {} if profile is None else profile
    point_start = time.monotonic()
    if count not in (16384, 32768, 65536): raise ValueError('Unregistered region level')
    if point is None:
        region = old.fit_region(pool.xy)
        point = dict(region=region, replica_region=region, mass_check=_point_mass(region, pool),
                     land_mass=float(pool.land.mean()), outside_D_mass=float(pool.outside.mean()),
                     land_variance=0., outside_variance=0., region_count=0)
        if geography is not None: point.update(geography.areas(region))
        profile['point_region_seconds'] = time.monotonic()-point_start
    out = {'ExactPoint': point}
    for name in ('EndpointCI', 'LocalGaussian'):
        if name == 'EndpointCI' and not pool.usable.any():
            out[name] = point
            continue
        regions = []
        for replicate in (0, 1):
            started = time.monotonic()
            stream = ('s5_e1_v1', *key, name, 'region', replicate)
            if name == 'EndpointCI':
                cloud, weights, labels = old.component_cloud(pool.points, pool.sd, pool.usable, count, stream)
                np.testing.assert_allclose(np.bincount(labels, weights=weights, minlength=len(pool.points)),
                                           1/len(pool.points), rtol=0, atol=1e-12)
            else:
                cloud = gaussian.draw(packet, gaussian.sobol_normals(count, 2, (*key, name, 'region', replicate)))
                weights = None
            regions.append(_region(cloud, weights))
            field = 'primary_region_seconds' if replicate == 0 else 'replica_region_seconds'
            profile[field] = profile.get(field, 0.) + time.monotonic()-started
        check_started = time.monotonic()
        check_rng = gaussian.generator((*key, name, 'region_check', 0))
        if name == 'EndpointCI':
            indices = check_rng.integers(len(pool.points), size=count)
            check = old.perturbed(pool.points[indices], pool.sd[indices], check_rng.standard_normal((count, 2)))
            atom = boundary_atom(pool.xy, ~pool.usable, regions[0])
        else:
            check = gaussian.draw(packet, check_rng.standard_normal((count, 2)))
            atom = 0.
        hits = old.inside_region(opt.xy(check), regions[0])
        result = dict(region=regions[0], replica_region=regions[1], region_count=count,
                      mass_check=gaussian.mass_diagnostic(int(hits.sum()), count, atom))
        if geography is not None:
            result.update(geography.masses(check, np.full(count, 1/count)))
            profile['region_check_seconds'] = profile.get('region_check_seconds', 0.) + time.monotonic()-check_started
            area_started = time.monotonic()
            result.update(geography.areas(regions[0]))
            profile['area_seconds'] = profile.get('area_seconds', 0.) + time.monotonic()-area_started
            result['land_variance'] = result['land_mass']*(1-result['land_mass'])/count
            result['outside_variance'] = result['outside_D_mass']*(1-result['outside_D_mass'])/count
        out[name] = result
    return out


def region_metrics(regions, truth):
    target = opt.xy(np.asarray(truth)[None, :])
    rows = {}
    for name, packet in regions.items():
        region, replica = packet['region'], packet['replica_region']
        hit = bool(old.inside_region(target, region)[0])
        hit_replica = bool(old.inside_region(target, replica)[0])
        rows[name] = dict(h90=float(hit), h90_replica=float(hit_replica),
            hit_disagreement=float(hit != hit_replica), area90_km2=region['area_km2'],
            area_replica_km2=replica['area_km2'], rank=region['rank'],
            model_mass90=packet['mass_check']['probability'],
            mass_radius=packet['mass_check']['radius'], mass_diagnostic=packet['mass_check']['diagnostic'],
            boundary_atom=packet['mass_check']['boundary_atom'],
            region_count=packet['region_count'])
        for field in ('land_mass', 'outside_D_mass', 'land_variance', 'outside_variance',
                      'land_area_km2', 'outside_D_area_km2', 'wet_area_km2'):
            if field in packet: rows[name][field] = packet[field]
    return rows


def scores(pool, packet, regions, truth, count, key, calibration=None):
    empirical_key = ('s5_e1_v1', *key, 'empirical_energy', 0)
    if calibration is None: calibration = opt.calibration(pool, empirical_key)
    empirical = opt.score(pool, {False: regions['ExactPoint'], True: regions['EndpointCI']},
                          truth, empirical_key, count, calibration)
    result = {}
    for ci, name in [(False, 'ExactPoint'), (True, 'EndpointCI')]:
        row = empirical[ci]
        result[name] = {field: row[field] for field in
                       ('energy_km', 'energy_mc_se', 'sample_count', 'residual_variance_ratio')}
        result[name]['variance'] = row['energy_mc_se']**2
    result['LocalGaussian'] = gaussian.energy(packet, truth, count, key)
    return result, calibration


def es_projection(contrast_variances, outer_squared_weight_sum, baseline_mean):
    three_se = 3*np.sqrt(np.max(contrast_variances)*outer_squared_weight_sum)
    threshold = .0001*baseline_mean
    return dict(projected_three_se_km=float(three_se), threshold_km=float(threshold),
                passed=bool(three_se <= threshold))


def region_gate(rows, weights):
    weights = np.asarray(weights)
    mean = lambda field: float(weights @ np.asarray(rows[field]))
    area = mean('area90_km2')
    change = abs(mean('area_replica_km2')-area)/area if area else 0.
    result = dict(mass_diagnostic=mean('mass_diagnostic'),
                  max_mass_radius=float(np.max(rows['mass_radius'])),
                  hit_disagreement=mean('hit_disagreement'), area_relative_change=change,
                  land_three_se=float(3*np.sqrt(weights**2 @ np.asarray(rows['land_variance']))),
                  outside_three_se=float(3*np.sqrt(weights**2 @ np.asarray(rows['outside_variance']))))
    result['passed'] = bool(result['mass_diagnostic'] <= .005 and result['max_mass_radius'] <= .005
        and result['hit_disagreement'] <= .001 and change <= .005
        and result['land_three_se'] <= .001 and result['outside_three_se'] <= .001)
    return result
