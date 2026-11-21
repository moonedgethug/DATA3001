"""Fixed CI-assisted Markov measures and continuous forecast diagnostics.

No temporal-role selection or held-out outcome access occurs in prediction.
The mathematical measures retain every donor; clouds are numerical quadrature.
"""
import hashlib
import json
from fractions import Fraction

import numpy as np
from pyproj import Geod, Transformer

GEOD = Geod(ellps='WGS84')
ECEF = Transformer.from_crs('EPSG:4979', 'EPSG:4978', always_xy=True)
LAEA = Transformer.from_crs('EPSG:4326', '+proj=laea +lon_0=-75 +lat_0=35 +ellps=WGS84 +units=m', always_xy=True)
INVERSE = Transformer.from_crs('+proj=laea +lon_0=-75 +lat_0=35 +ellps=WGS84 +units=m', 'EPSG:4326', always_xy=True)
MODELS = ('ExactPoint', 'EndpointCI', 'MatchedSpread', 'B2Point')
Z95 = 1.9599639845


def rng_for(*key):
    digest = hashlib.sha256(json.dumps(key, separators=(',', ':')).encode()).digest()
    return np.random.Generator(np.random.PCG64(int.from_bytes(digest[:16], 'little')))


def coordinates(lonlat):
    p = np.asarray(lonlat, float)
    xyz = np.column_stack(ECEF.transform(p[:, 0], p[:, 1], np.zeros(len(p)))) / 1000
    xy = np.column_stack(LAEA.transform(p[:, 0], p[:, 1])) / 1000
    if not np.isfinite(xyz).all() or not np.isfinite(xy).all():
        raise ValueError('Nonfinite geographic transformation')
    return xyz, xy


def equivalent_sd(lonlat, halfwidths, usable):
    """Normal quantile-matched width, not a claim about native standard errors."""
    p = np.asarray(lonlat, float); h = np.asarray(halfwidths, float)
    ok = np.asarray(usable, bool)
    if h.shape != p.shape or ok.shape != (len(p),):
        raise ValueError('Position/error shapes differ')
    if not np.isfinite(h[ok]).all() or (h[ok] <= 0).any():
        raise ValueError('Accepted widths must be finite and positive')
    phi = np.deg2rad(p[:, 1]); e2 = 6.6943799901413165e-3
    denominator = 1 - e2 * np.sin(phi)**2
    north = 6378137 * (1-e2) / denominator**1.5
    east = 6378137 / np.sqrt(denominator) * np.cos(phi)
    out = np.zeros_like(p)
    out[ok] = np.deg2rad(h[ok]) * np.column_stack([east, north])[ok] / 1000 / Z95
    return out


def perturbed(lonlat, sd, normals, rho=0.):
    p = np.asarray(lonlat, float); z = np.asarray(normals, float)
    if abs(rho) >= 1: raise ValueError('Correlation must be strictly inside [-1,1]')
    east = sd[:, 0] * z[:, 0]
    north = sd[:, 1] * (rho*z[:, 0] + np.sqrt(1-rho*rho)*z[:, 1])
    radius = np.hypot(east, north)
    lon, lat, _ = GEOD.fwd(p[:, 0], p[:, 1], np.rad2deg(np.arctan2(east, north)), radius*1000)
    result = np.column_stack([lon, lat])
    # Preserve point fallbacks exactly, including binary coordinate identity.
    result[radius == 0] = p[radius == 0]
    if not np.isfinite(result).all(): raise ValueError('Geodesic perturbation failed')
    return result


def covariance_matched(sd, usable):
    out = np.zeros_like(sd)
    if np.any(usable): out[usable] = np.sqrt(np.mean(sd[usable]**2, axis=0))
    return out


def component_cloud(lonlat, sd, usable, budget, key, rho=0.):
    """Antithetic stratification with exactly 1/n total weight per donor."""
    n = len(lonlat); valid = np.flatnonzero(usable); invalid = np.flatnonzero(~usable)
    if not n: raise ValueError('Unsupported distribution')
    if not len(valid): return lonlat.copy(), np.full(n, 1/n), np.arange(n)
    per = 2 * ((int(budget) - len(invalid)) // (2*len(valid)))
    if per < 2: raise ValueError('Numerical budget cannot represent every component with antithetic draws')
    repeat = per // 2
    indices = np.repeat(valid, repeat)
    z = rng_for(*key, 'cloud').standard_normal((len(indices), 2))
    indices = np.r_[indices, indices]
    z = np.vstack([z, -z])
    p = perturbed(lonlat[indices], sd[indices], z, rho)
    cloud = np.vstack([p, lonlat[invalid]])
    weights = np.r_[np.full(len(p), 1/(n*per)), np.full(len(invalid), 1/n)]
    labels = np.r_[indices, invalid]
    if abs(weights.sum()-1) > 1e-10: raise ValueError('Quadrature loses probability')
    return cloud, weights, labels


def weighted_quantile(values, weights, probability=.9):
    order = np.argsort(values, kind='stable')
    w=np.asarray(weights,float)[order]
    p=Fraction(str(probability))
    # Uniform donor votes and stratified mixture clouds have exact integer
    # weight ratios. Integer arithmetic prevents a 90% boundary from moving
    # by one atom because 14,400 additions of 1/16,000 round below 0.9.
    ratios=w/w.min();units=np.rint(ratios)
    if units.max()<1e9 and np.all(abs(ratios-units)<=8*np.finfo(float).eps*np.maximum(1,ratios)):
        cumulative=np.cumsum(units.astype(np.int64))
        threshold=(p.numerator*int(cumulative[-1])+p.denominator-1)//p.denominator
        at=np.searchsorted(cumulative,threshold,side='left')
    else:
        cumulative=np.cumsum(w,dtype=np.longdouble)
        threshold=np.longdouble(p.numerator)/p.denominator*cumulative[-1]
        tolerance=8*np.finfo(float).eps*cumulative[-1]
        at=np.searchsorted(cumulative,threshold-tolerance,side='left')
    return float(values[order[min(at, len(order)-1)]])


def fit_region(xy, weights=None):
    p = np.asarray(xy, float)
    w = np.full(len(p), 1/len(p)) if weights is None else np.asarray(weights, float)
    if len(p) == 0 or abs(w.sum()-1) > 1e-10 or (w <= 0).any():
        raise ValueError('Region requires a normalized positive measure')
    centre = w @ p; delta = p-centre
    covariance = delta.T @ (delta*w[:, None])
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    largest = max(float(eigenvalues.max()), 0.)
    keep = eigenvalues > 64*np.finfo(float).eps*largest if largest else np.zeros(2, bool)
    rank = int(keep.sum())
    inverse = (eigenvectors[:, keep] / eigenvalues[keep]) @ eigenvectors[:, keep].T if rank else np.zeros((2, 2))
    distance = np.einsum('ij,jk,ik->i', delta, inverse, delta)
    cutoff = weighted_quantile(distance, w)
    included = distance <= cutoff+1e-12
    area = np.pi*cutoff*np.sqrt(np.prod(eigenvalues)) if rank == 2 else 0.
    return dict(centre=centre.tolist(), covariance=covariance.tolist(), inverse=inverse.tolist(),
                eigenvalues=eigenvalues.tolist(), eigenvectors=eigenvectors.tolist(), rank=rank,
                cutoff=cutoff, area_km2=float(area), attained_mass=float(w[included].sum()),
                null_tolerance_km=float(64*np.finfo(float).eps*max(1., np.linalg.norm(centre), np.sqrt(largest))))


def inside_region(xy, region):
    delta = np.asarray(xy, float) - np.asarray(region['centre'])
    inverse = np.asarray(region['inverse'])
    value = np.einsum('ij,jk,ik->i', delta, inverse, delta)
    inside = value <= region['cutoff'] + 1e-12
    if region['rank'] < 2:
        covariance = np.asarray(region['covariance'])
        residual = delta - delta @ (covariance @ inverse)
        inside &= np.linalg.norm(residual, axis=1) <= region['null_tolerance_km']
    return inside


def ellipse_boundary(region, vertices=512):
    centre = np.asarray(region['centre'])
    values = np.maximum(region['eigenvalues'], 0)
    vectors = np.asarray(region['eigenvectors'])
    angle = np.linspace(0, 2*np.pi, vertices+1)
    axes = np.sqrt(values*region['cutoff'])
    return centre + (np.column_stack([np.cos(angle), np.sin(angle)])*axes) @ vectors.T


def score_terms(points, sd, usable, count, key, rho=0.):
    """Outcome-free self-distance correction and unbiased mean construction."""
    n = len(points); g = rng_for(*key, 'energy')
    a = g.integers(n, size=count); b = g.integers(n, size=count)
    z1 = g.standard_normal((count, 2)); z2 = g.standard_normal((count, 2))
    xyz, _ = coordinates(points)
    base_distance = np.linalg.norm(xyz[a]-xyz[b], axis=1)
    result = {'ExactPoint': dict(correction=.5*float(base_distance.mean()),
                               correction_se=.5*float(base_distance.std(ddof=1)/np.sqrt(count)),
                               mean2=xyz.mean(axis=0).tolist())}
    samples = {'ExactPoint': xyz[a]}
    paired_distance = {}
    for name, widths in [('EndpointCI', sd), ('MatchedSpread', covariance_matched(sd, usable))]:
        first, _ = coordinates(perturbed(points[a], widths[a], z1, rho))
        second, _ = coordinates(perturbed(points[b], widths[b], z2, rho))
        negative, _ = coordinates(perturbed(points[a], widths[a], -z1, rho))
        difference = np.linalg.norm(first-second, axis=1)-base_distance
        result[name] = dict(correction=result['ExactPoint']['correction']+.5*float(difference.mean()),
                            correction_delta=.5*float(difference.mean()),
                            mean2=(xyz.mean(axis=0)+(.5*(first+negative)-xyz[a]).mean(axis=0)).tolist())
        samples[name] = first; paired_distance[name] = difference
    return result, samples, paired_distance


def predict(points, sd, usable, *, energy_count=4096, region_count=16384, key=(), rho=0., retain_cloud=False):
    xyz, xy = coordinates(points)
    terms, _, _ = score_terms(points, sd, usable, energy_count, key, rho)
    distributions = {}
    clouds = {}
    for name, widths in [('ExactPoint', None), ('EndpointCI', sd), ('MatchedSpread', covariance_matched(sd, usable))]:
        if widths is None or not usable.any():
            cloud, weights = points, np.full(len(points), 1/len(points))
            cloud_xyz, cloud_xy = xyz, xy
        else:
            cloud, weights, _ = component_cloud(points, widths, usable, region_count, key, rho)
            cloud_xyz, cloud_xy = coordinates(cloud)
        region = fit_region(cloud_xy, weights)
        distributions[name] = dict(region=region, mean1=(weights @ cloud_xyz).tolist(),
                                    **terms[name], particles=len(cloud), energy_count=energy_count,
                                    region_count=region_count, rho=float(rho))
        if retain_cloud: clouds[name] = (cloud, weights)
    return distributions, clouds


def point_forecast(points, count=4096, key=()):
    xyz, xy = coordinates(points); g = rng_for(*key, 'point_energy')
    a = g.integers(len(points), size=count); b = g.integers(len(points), size=count)
    d = np.linalg.norm(xyz[a]-xyz[b], axis=1)
    return dict(region=fit_region(xy), correction=.5*float(d.mean()),
                correction_se=.5*float(d.std(ddof=1)/np.sqrt(count)),
                mean1=xyz.mean(axis=0).tolist(), mean2=xyz.mean(axis=0).tolist(),
                energy_count=count, particles=len(points), region_count=len(points))


def evaluate(points, sd, usable, forecast, truth, *, key=(), rho=0.):
    target, target_xy = coordinates(np.asarray(truth, float).reshape(1, 2)); target = target[0]
    xyz, _ = coordinates(points); nmc = forecast['ExactPoint']['energy_count']
    _, samples, pair_difference = score_terms(points, sd, usable, nmc, key, rho)
    base_first = float(np.linalg.norm(xyz-target, axis=1).mean())
    base_sample = np.linalg.norm(samples['ExactPoint']-target, axis=1)
    rows = {}
    for name, packet in forecast.items():
        if name == 'ExactPoint':
            first = base_first; delta = 0.; se = packet['correction_se']
        else:
            change = np.linalg.norm(samples[name]-target, axis=1)-base_sample
            first = base_first+float(change.mean())
            contrast = change-.5*pair_difference[name]
            delta = float(contrast.mean()); se = float(contrast.std(ddof=1)/np.sqrt(nmc))
        energy = first-packet['correction']
        squared = float((np.asarray(packet['mean1'])-target) @ (np.asarray(packet['mean2'])-target))
        rows[name] = dict(energy_km=energy, delta_energy_vs_exact_km=delta, energy_mc_se=se,
                          mean_squared_km2=squared, auxiliary=energy/100+squared/10000,
                          h90=float(inside_region(target_xy, packet['region'])[0]),
                          area90_km2=packet['region']['area_km2'], mass90=packet['region']['attained_mass'],
                          rank=packet['region']['rank'])
    return rows


def evaluate_point(points, packet, truth):
    xyz, _ = coordinates(points); target, target_xy = coordinates(np.asarray(truth).reshape(1, 2)); target = target[0]
    energy = float(np.linalg.norm(xyz-target, axis=1).mean())-packet['correction']
    squared = float(np.sum((np.asarray(packet['mean1'])-target)**2))
    return dict(energy_km=energy, energy_mc_se=packet['correction_se'], mean_squared_km2=squared,
                auxiliary=energy/100+squared/10000, h90=float(inside_region(target_xy, packet['region'])[0]),
                area90_km2=packet['region']['area_km2'], mass90=packet['region']['attained_mass'], rank=packet['region']['rank'])
