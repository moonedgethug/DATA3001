"""Frozen, resumable full-cohort MDN scoring with the validated node backend.

Parameters and all stream identities are sealed before target release. The
executor owns only small query-row batches, never per-query files or point
clouds. Its numerical kernels are the unchanged optimized implementation.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import multivariate_normal

from data3001.paths import file_sha256
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
from . import conditional_mdn_s5_e3_inputs as inp
from . import conditional_mdn_s5_e3_numerics as num
from . import conditional_mdn_s5_e3_optimized as optimized
from .conditional_mdn_s5_e3 import K_CANDIDATES, stable_seed
from .conditional_mdn_s5_e3_runtime import ROOT, atomic_json


MODES = ('inner_energy', 'inner_regions', 'outer_score', 'outer_audit')
WORKER_THREAD_ENV = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
                     'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS')
STATE = {}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def validate_request(role, mode, k_values, count, region_count):
    if mode not in MODES or role not in inp.EXPECTED:
        raise ValueError('Unknown formal scoring role or mode')
    if (role == 'C_outer') != mode.startswith('outer_'):
        raise ValueError('Formal scoring mode does not match role')
    values = tuple(k_values)
    if not values or len(set(values)) != len(values) or any(k not in K_CANDIDATES for k in values):
        raise ValueError('Invalid formal candidate roster')
    values = tuple(sorted(values))
    if mode != 'inner_regions' and values != K_CANDIDATES:
        raise ValueError('Formal energy and outer scoring require all six candidates')
    if mode == 'inner_regions' and (values[0] != 1 or len(values) > 2):
        raise ValueError('Inner regions require only MDN1 and the provisional candidate')
    if count not in num.LEVELS or region_count not in num.LEVELS:
        raise ValueError('Unregistered formal integration level')
    return values


def load_parameters(path, query, k):
    """Validate an entire immutable forecast archive without accessing targets."""
    required = {'query_keys', 'origins', 'pi', 'mu', 'cov', 'target_scale'}
    with np.load(path, allow_pickle=False) as archive:
        if not required.issubset(archive.files):
            raise ValueError('Incomplete MDN parameter archive')
        values = {name: np.array(archive[name], copy=True) for name in required}
    n = len(query)
    shapes = dict(query_keys=(n, 3), origins=(n, 2), pi=(n, k),
                  mu=(n, k, 2), cov=(n, k, 2, 2), target_scale=(2,))
    for name, shape in shapes.items():
        value = values[name]
        if value.shape != shape or not np.isfinite(value).all():
            raise ValueError('Invalid forecast array: ' + name)
        if value.dtype != (np.dtype('int64') if name == 'query_keys' else np.dtype('float64')):
            raise ValueError('Forecast array has unapproved dtype: ' + name)
    if not np.array_equal(values['query_keys'], query[inp.KEY].to_numpy(np.int64)):
        raise ValueError('Forecast source-key roster or order differs')
    if not np.array_equal(values['origins'], query[['lon', 'lat']].to_numpy(np.float64)):
        raise ValueError('Forecast origins differ from frozen query coordinates')
    if (values['pi'] < 0).any() or np.max(np.abs(values['pi'].sum(axis=1)-1)) > 1e-10:
        raise ValueError('Invalid mixture probability mass')
    scale = values['target_scale']
    covariance = values['cov']
    if (scale <= 0).any() or not np.allclose(covariance, covariance.swapaxes(-1, -2),
                                           rtol=1e-12, atol=1e-10):
        raise ValueError('Invalid covariance or standardization scale')
    standardized = covariance / scale[None, None, :, None] / scale[None, None, None, :]
    if np.linalg.eigvalsh(standardized).min() < .001-1e-10:
        raise ValueError('MDN standardized covariance floor failed')
    values['cholesky'] = np.linalg.cholesky(covariance)
    for value in values.values():
        value.setflags(write=False)
    return values


def fixed_iid_positions(count):
    if not isinstance(count, (int, np.integer)) or count < 1:
        raise ValueError('IID roster must be nonempty')
    size = min(128, count)
    if size == 1:
        return np.array([0], dtype=np.int64)
    return np.floor(np.arange(size)*(count-1)/(size-1)).astype(np.int64)


def _streams(mode, count, region_count):
    streams = []
    if mode in ('inner_energy', 'outer_score'):
        streams += [('ES', rep, count//8, 6) for rep in range(8)]
    if mode in ('inner_energy', 'outer_audit'):
        streams += [('audit', rep, count//8, 6) for rep in range(8)]
    if mode in ('inner_regions', 'outer_score'):
        streams += [('region', rep, region_count, 3) for rep in range(2)]
        streams += [('IID', 0, 65536, 2)]
    if mode in ('inner_regions', 'outer_audit'):
        streams += [('audit', 100+rep, region_count, 3) for rep in range(2)]
        streams += [('IID', 1, 65536, 2)]
    return streams


def stream_manifest(query, role, mode, count, region_count):
    """Hash actual stable seeds and node shapes, without generating any nodes."""
    keys = query[inp.KEY].to_numpy(dtype=np.int64)
    streams = _streams(mode, count, region_count)
    # Freeze later numerical checks at the first release, even though this
    # invocation may only execute the main energy or region calculation.
    all_streams = (_streams('inner_energy', count, region_count)
                   + _streams('inner_regions', count, region_count)
                   + [('IID', 10, 65536, 2), ('IID', 11, 65536, 2)])
    iid_positions = fixed_iid_positions(len(query)) if mode == 'outer_audit' else np.array([], dtype=int)
    iid_set = set(iid_positions.tolist())
    all_iid_positions = fixed_iid_positions(len(query)) if role == 'C_outer' else np.array([], dtype=int)
    all_iid_set = set(all_iid_positions.tolist())
    identity = dict(seed_scheme='mdn_s5_e3_v1', base_seed=20261121, candidate_seed_field=None,
                    role=role, mode=mode, count=int(count), region_count=int(region_count),
                    streams=[dict(purpose=p, replicate=r, nodes=n, dimensions=d) for p, r, n, d in streams],
                    all_streams=[dict(purpose=p, replicate=r, nodes=n, dimensions=d)
                                 for p, r, n, d in all_streams],
                    all_iid_positions=all_iid_positions.tolist(),
                    iid_count=65536, iid_positions=iid_positions.tolist(),
                    iid_checker_replicates=[10, 11] if mode == 'outer_audit' else [],
                    iid_checker_path='eigen_root_standard_normal_independent_ecef_scipy_density',
                    common_random_numbers='same query and purpose across K only')
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode())
    all_digest = hashlib.sha256(json.dumps(dict(role=role, count=count, region_count=region_count,
                                               streams=all_streams), sort_keys=True).encode())
    for position, raw_key in enumerate(keys):
        key = tuple(int(value) for value in raw_key)
        digest.update(np.asarray(key, dtype='<i8').tobytes())
        current = streams + ([('IID', 10, 65536, 2), ('IID', 11, 65536, 2)] if position in iid_set else [])
        for purpose, replicate, nodes, dimensions in current:
            digest.update(np.asarray([stable_seed(purpose, role, None, 20261121, key, replicate),
                                      nodes, dimensions], dtype='<u8').tobytes())
        all_digest.update(np.asarray(key, dtype='<i8').tobytes())
        for purpose, replicate, nodes, dimensions in all_streams:
            if purpose == 'IID' and replicate in (10, 11) and position not in all_iid_set:
                continue
            all_digest.update(np.asarray([stable_seed(purpose, role, None, 20261121, key, replicate),
                                          nodes, dimensions], dtype='<u8').tobytes())
    identity['node_key_sha256'] = digest.hexdigest()
    identity['all_node_key_sha256'] = all_digest.hexdigest()
    return identity


def _source_hashes():
    names = ('conditional_mdn_s5_e3.py', 'conditional_mdn_s5_e3_inputs.py',
             'conditional_mdn_s5_e3_numerics.py', 'conditional_mdn_s5_e3_optimized.py',
             'conditional_mdn_s5_e3_runtime.py', 'conditional_mdn_s5_e3_formal_context.py',
             'conditional_mdn_s5_e3_formal_scoring.py', 'conditional_mdn_s5_e3_training.py',
             'conditional_mdn_s5_e3_formal_training.py', 'conditional_mdn_s5_e3_formal_pipeline.py',
             'conditional_mdn_s5_e3_selection.py')
    files = [Path(__file__).parent/name for name in names]
    files += [ROOT/'configs/conditional_mdn_s5_e3.json', ROOT/'configs/assets.json',
              ROOT/'docs/conditional_mdn_s5_e3_contract.md',
              ROOT/'src/data3001/modelling/baselines/position_error_s4_e8.py',
              ROOT/'src/data3001/modelling/baselines/position_error_s4_e8_geometry.py',
              ROOT/'src/data3001/modelling/continuous_models/conditional_gaussian_s5_e1.py',
              ROOT/'src/data3001/modelling/common/runtime.py', ROOT/'src/data3001/paths.py']
    return {str(path.relative_to(ROOT)): file_sha256(path) for path in sorted(files)}


def _verify_sources(hashes):
    for relative, expected in hashes.items():
        if file_sha256(ROOT/relative) != expected:
            raise ValueError('Formal scoring source changed: ' + relative)


def _safe_parameter_path(root, relative):
    path = (root/relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Forecast path escapes formal results')
    return path


def _freeze_path(run, role, mode, count, region_count):
    return run['provenance']/f'formal_v1/{role}/{mode}/inputs_N{count}_M{region_count}.json'


def score_directory(run, role, mode, count, region_count):
    return run['results']/f'formal_v1/{role}/{mode}/N{count}_M{region_count}'


def freeze_score_inputs(run_name, role, mode, k_values, count=65536, region_count=65536):
    """Persist a complete forecast/stream freeze before the target loader runs."""
    from . import conditional_mdn_s5_e3_formal_context as formal
    k_values = validate_request(role, mode, k_values, count, region_count)
    _, run, cfg, _, _ = formal.context(run_name)
    query = inp.cohorts(cfg)[role]['query']
    formal_root = run['results']/'formal_v1'
    forecast_path = run['provenance']/f'formal_v1/{role}/forecast_freeze.json'
    if not forecast_path.exists():
        raise PermissionError('Freeze all six forecast archives before formal scoring')
    forecast = json.loads(forecast_path.read_text())
    query_hash = inp.key_digest(query)
    if (forecast.get('status') != 'complete' or forecast.get('role') != role
            or forecast.get('query_count') != len(query) or forecast.get('query_key_sha256') != query_hash
            or set(forecast.get('models', {})) != {str(k) for k in K_CANDIDATES}):
        raise PermissionError('Incomplete or mismatched full-role forecast freeze')
    if mode == 'inner_regions':
        choice = json.loads((formal_root/'provisional_selection.json').read_text())
        expected = tuple(sorted({1, int(choice['provisional_k'])}))
        if choice.get('status') != 'complete' or k_values != expected:
            raise PermissionError('Region candidates differ from the frozen provisional selection')
    upgrade_hash = None
    if count != 65536 or region_count != 65536:
        upgrade = run['provenance']/f'formal_v1/precision_upgrade_N{count}_M{region_count}.json'
        evidence = json.loads(upgrade.read_text())
        if (evidence.get('status') != 'approved' or evidence.get('global_checks_complete') is not True
                or evidence.get('count') != count or evidence.get('region_count') != region_count
                or evidence.get('previous_count') not in num.LEVELS
                or evidence.get('previous_region_count') not in num.LEVELS
                or count < evidence['previous_count'] or region_count < evidence['previous_region_count']
                or not evidence.get('reason')):
            raise PermissionError('Precision upgrade lacks completed global checks')
        upgrade_hash = file_sha256(upgrade)
    parameter_hashes, manifest_hashes, parameter_paths = {}, {}, {}
    for k in K_CANDIDATES:
        entry = forecast['models'][str(k)]
        path = _safe_parameter_path(formal_root, entry['parameters'])
        manifest_path = _safe_parameter_path(formal_root, entry['manifest'])
        if file_sha256(path) != entry['parameters_sha256'] or file_sha256(manifest_path) != entry['manifest_sha256']:
            raise ValueError('Frozen forecast archive or manifest changed')
        manifest = json.loads(manifest_path.read_text())
        if (manifest.get('status') != 'complete' or manifest.get('k') != k
                or manifest.get('role') != role or manifest.get('query_key_sha256') != query_hash
                or manifest.get('parameters', {}).get('sha256') != entry['parameters_sha256']):
            raise ValueError('Forecast manifest does not identify a complete model')
        if k in k_values:
            load_parameters(path, query, k)
            parameter_hashes[str(k)] = entry['parameters_sha256']
            manifest_hashes[str(k)] = entry['manifest_sha256']
            parameter_paths[str(k)] = entry['parameters']
    streams = stream_manifest(query, role, mode, count, region_count)
    manifest = dict(schema_version=1, status='complete', run_name=run_name, role=role, mode=mode,
                    k_values=list(k_values), count=int(count), region_count=int(region_count),
                    query_count=len(query), query_id_count=int(query.id.nunique()),
                    query_key_sha256=query_hash, parameter_hashes=parameter_hashes,
                    parameter_manifest_hashes=manifest_hashes, parameter_paths=parameter_paths,
                    source_hashes=_source_hashes(), forecast_freeze_sha256=file_sha256(forecast_path),
                    node_key_sha256=streams['node_key_sha256'], streams=streams,
                    precision_upgrade_sha256=upgrade_hash, excluded_queries=0,
                    target_values_accessed=False, final_test_access=False)
    manifest['identity_sha256'] = _digest(manifest)
    output = _freeze_path(run, role, mode, count, region_count)
    if output.exists():
        if json.loads(output.read_text()) != manifest:
            raise ValueError('Formal scoring input freeze is immutable')
    else:
        atomic_json(output, manifest)
    return manifest


def _require_active(stop):
    if stop is not None and stop.is_set():
        raise InterruptedError('Formal scoring cancelled after interruption or worker failure')


def independent_xyz(points):
    """Zero-height WGS84 ECEF using ellipsoid equations instead of PROJ ECEF."""
    lon, lat = np.deg2rad(np.asarray(points, dtype=np.float64)).T
    eccentricity_squared = 1-(6356752.314245179/6378137.)**2
    radius = 6378137./np.sqrt(1-eccentricity_squared*np.sin(lat)**2)
    return np.column_stack((radius*np.cos(lat)*np.cos(lon), radius*np.cos(lat)*np.sin(lon),
                            radius*(1-eccentricity_squared)*np.sin(lat)))/1000


def independent_log_density(vectors, weights, means, covariances):
    """SciPy density path, including all nonzero component probabilities."""
    columns = []
    for probability, mean, covariance in zip(weights, means, covariances):
        if probability == 0:
            columns.append(np.full(len(vectors), -np.inf))
        else:
            columns.append(np.log(probability)+multivariate_normal.logpdf(
                vectors, mean=mean, cov=covariance, allow_singular=False))
    return logsumexp(np.asarray(columns), axis=0)


def independent_iid_check(packet, target, key, role, count=65536):
    """A separate eigen-root draw/density/ECEF path for the fixed outer subset."""
    if count != 65536:
        raise ValueError('The independent IID checker has a fixed 65,536 draws')
    from pyproj import Geod
    import torch
    from .conditional_mdn_s5_e3 import mixture_nll
    prepared = optimized.prepare_packet(packet)
    weights, means = prepared.weights, prepared.means
    covariance = prepared.cholesky @ prepared.cholesky.swapaxes(-1, -2)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    roots = eigenvectors*np.sqrt(eigenvalues)[:, None, :]
    geod = Geod(ellps='WGS84')
    vectors, samples = [], []
    for rep in (10, 11):
        rng = np.random.default_rng(stable_seed('IID', role, None, 20261121, key, rep))
        chosen = rng.choice(len(weights), count, p=weights)
        normal = rng.standard_normal((count, 2))
        v = means[chosen]+np.einsum('nij,nj->ni', roots[chosen], normal)
        lon, lat, _ = geod.fwd(np.full(count, prepared.origin[0]), np.full(count, prepared.origin[1]),
                               np.degrees(np.arctan2(v[:, 0], v[:, 1])), np.hypot(v[:, 0], v[:, 1])*1000)
        points = np.column_stack([lon, lat]); points[np.all(v == 0, axis=1)] = prepared.origin
        samples.append(independent_xyz(points)); vectors.append(v)
    truth = independent_xyz(np.asarray(target)[None])[0]
    integrand = np.sqrt(np.sum((samples[0]-truth)**2, axis=1))
    integrand -= .5*np.sqrt(np.sum((samples[0]-samples[1])**2, axis=1))
    check_vectors = np.vstack([vectors[0][:32], vectors[1][:32], means])
    reference_density = independent_log_density(check_vectors, weights, means, covariance)
    with np.errstate(divide='ignore'):
        log_weights = np.log(weights)
    output = tuple(torch.from_numpy(np.array(value, copy=True)) for value in
                   (log_weights[None], means[None], covariance[None]))
    with torch.no_grad():
        production_density = -mixture_nll(output, torch.from_numpy(check_vectors)).numpy()
    difference = float(np.max(np.abs(production_density-reference_density)))
    if not np.isfinite(integrand).all() or not np.isfinite(reference_density).all() or difference > 1e-7:
        raise ArithmeticError('Independent IID/density calculation failed')
    return dict(iid_energy_km=float(integrand.mean()), iid_variance=float(integrand.var(ddof=1)/count),
                iid_count=count, iid_density_max_abs=difference)


def _energy_fields(row, result, audit):
    prefix = 'audit_' if audit else ''
    row.update({prefix+'energy_km': result['energy_km'], prefix+'variance': result['variance'],
                prefix+'energy_mc_se': result['energy_mc_se']})
    for replicate, value in enumerate(result['replicates']):
        row[('es_audit_rep' if audit else 'es_rep')+str(replicate)] = value


def _region_fields(row, regions, target, audit):
    prefix = 'audit_' if audit else ''
    row.update({prefix+name: value for name, value in num.region_metrics(regions, target).items()})
    for name in ('land_mass', 'outside_D_mass', 'land_variance', 'outside_variance'):
        if name in regions:
            row[prefix+name] = regions[name]
    row[prefix+'region_json'] = json.dumps(regions, separators=(',', ':'), allow_nan=False)
    row[prefix+'model_mass90'] = regions['mass_check']['probability']
    truth = num.xyz(np.asarray(target)[None])[0]
    mean1, mean2 = np.asarray(regions['means'])
    square = float(np.dot(mean1-truth, mean2-truth))
    row[prefix+'mean_error_squared_km2'] = square
    if prefix+'energy_km' in row:
        auxiliary = row[prefix+'energy_km']/100+square/10000
        row[prefix+'auxiliary_loss'] = auxiliary
        row[prefix+'auxiliary_score'] = auxiliary


def score_query(task, geography, stop=None):
    """Score one complete query; each scope shares nodes across its K values."""
    _require_active(stop)
    key, mode, role = tuple(task['key']), task['mode'], task['role']
    packets = {int(k): optimized.prepare_packet(value) for k, value in task['packets'].items()}
    rows = {k: dict(role=role, position=int(task['position']), id=int(key[0]),
                    origin_source_obs=int(key[1]), horizon_days=int(key[2]), K=k,
                    model='MDN'+str(k), energy_count=int(task['count']),
                    region_count=int(task['region_count']), excluded=False)
            for k in sorted(packets)}
    scopes = []
    if mode in ('inner_energy', 'outer_score'):
        scopes.append(('ES', False, False))
    if mode in ('inner_energy', 'outer_audit'):
        scopes.append(('audit_ES', True, False))
    if mode in ('inner_regions', 'outer_score'):
        scopes.append(('region', False, True))
    if mode in ('inner_regions', 'outer_audit'):
        scopes.append(('audit_region', True, True))
    peak = 0
    for scope, audit, region in scopes:
        # A single 128 MiB scope is alive at a time; no primary/audit node reuse.
        with optimized.QueryCache(key, scope, max_bytes=128*1024**2) as cache:
            for k, packet in packets.items():
                _require_active(stop)
                if region:
                    result = optimized.build_region(packet, task['region_count'], key, role,
                                                     geography, audit, cache=cache)
                    _region_fields(rows[k], result, task['target'], audit)
                else:
                    result = optimized.score_es(packet, task['target'], task['count'], key, role,
                                                 audit, cache=cache)
                    _energy_fields(rows[k], result, audit)
            peak = max(peak, cache.peak_cache_bytes)
        if cache.cache_bytes:
            raise RuntimeError('Numerical node cache leaked past its scope')
    if mode == 'outer_audit' and task.get('iid'):
        for k, packet in packets.items():
            _require_active(stop)
            rows[k].update(independent_iid_check(packet, task['target'], key, role))
    for row in rows.values():
        row['peak_node_cache_bytes'] = peak
        if any(not np.isfinite(value) for value in row.values()
               if isinstance(value, (float, np.floating))):
            raise ArithmeticError('Nonfinite scoring output; no query may be omitted')
    return list(rows.values())


def _atomic_frame(path, frame):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)


def write_shard(folder, batch, rows, identity, start, end):
    folder = Path(folder)
    path = folder/f'batch_{batch:06d}.parquet'
    frame = pd.DataFrame(rows)
    _atomic_frame(path, frame)
    atomic_json(folder/f'batch_{batch:06d}.json',
                dict(status='complete', identity_sha256=identity, start=int(start), end=int(end),
                     row_count=len(frame), parquet_sha256=file_sha256(path)))


def _validate_rows(frame, keys, k_values, start, end):
    expected = [(position, *map(int, keys[position]), k)
                for position in range(start, end) for k in k_values]
    columns = ['position', *inp.KEY, 'K']
    if any(name not in frame for name in columns) or len(frame) != len(expected):
        raise ValueError('Score shard has missing or extra query/candidate rows')
    actual = list(frame[columns].itertuples(index=False, name=None))
    if actual != expected:
        raise ValueError('Score shard source keys, positions, or candidate order differ')
    if 'excluded' in frame and frame.excluded.any():
        raise ValueError('Formal scoring cannot exclude queries')


def read_valid_shard(folder, batch, identity, keys, k_values, start, end):
    folder = Path(folder)
    receipt_path = folder/f'batch_{batch:06d}.json'
    path = folder/f'batch_{batch:06d}.parquet'
    if not receipt_path.exists():
        return None  # A parquet without the atomic receipt was never committed.
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get('status') != 'complete' or receipt.get('identity_sha256') != identity
            or receipt.get('start') != start or receipt.get('end') != end
            or not path.exists() or receipt.get('parquet_sha256') != file_sha256(path)):
        raise ValueError('Score shard identity or content hash differs from freeze')
    frame = pd.read_parquet(path)
    if receipt.get('row_count') != len(frame):
        raise ValueError('Score shard receipt row count differs')
    _validate_rows(frame, keys, k_values, start, end)
    return frame


def validate_worker_environment():
    if any(os.environ.get(name) != '1' for name in WORKER_THREAD_ENV):
        raise RuntimeError('Scoring worker must inherit single-thread BLAS controls before spawn')


def initialize_worker(run_name, freeze, query, targets, stop):
    global STATE
    import torch
    from . import conditional_mdn_s5_e3_formal_context as formal
    validate_worker_environment()
    torch.set_num_threads(1)
    paths, run, _, _, _ = formal.context(run_name)
    _verify_sources(freeze['source_hashes'])
    parameters = {}
    for k in freeze['k_values']:
        path = _safe_parameter_path(run['results']/'formal_v1', freeze['parameter_paths'][str(k)])
        if file_sha256(path) != freeze['parameter_hashes'][str(k)]:
            raise ValueError('Worker forecast archive changed')
        parameters[k] = load_parameters(path, query, k)
    geometry = Geography(paths) if freeze['mode'] != 'inner_energy' else None
    STATE = dict(freeze=freeze, query=query, targets=targets, parameters=parameters,
                 stop=stop, geography=geometry,
                 iid_positions=set(freeze['streams']['iid_positions']))


def work_batch(batch):
    number, start, end = batch
    state, rows = STATE, []
    freeze = state['freeze']
    keys = state['query'][inp.KEY].to_numpy(np.int64)
    for position in range(start, end):
        _require_active(state['stop'])
        packets = {k: dict(origin=values['origins'][position], weights=values['pi'][position],
                           means=values['mu'][position], cholesky=values['cholesky'][position])
                   for k, values in state['parameters'].items()}
        task = dict(role=freeze['role'], mode=freeze['mode'], key=tuple(keys[position]),
                    position=position, target=state['targets'][position], packets=packets,
                    count=freeze['count'], region_count=freeze['region_count'],
                    iid=position in state['iid_positions'])
        rows.extend(score_query(task, state['geography'], state['stop']))
    return number, start, end, rows


def _targets_in_order(targets, query):
    if targets.duplicated(inp.KEY).any() or len(targets) != len(query):
        raise ValueError('Released targets have missing, duplicate, or extra keys')
    joined = query[inp.KEY].merge(targets[inp.KEY+['endpoint_lon', 'endpoint_lat']],
                                 on=inp.KEY, how='left', sort=False, validate='one_to_one', indicator=True)
    if not joined._merge.eq('both').all():
        raise ValueError('Released target roster differs from frozen forecasts')
    result = joined[['endpoint_lon', 'endpoint_lat']].to_numpy(np.float64)
    if not np.isfinite(result).all():
        raise ValueError('Nonfinite formal target; no query may be excluded')
    return result


def score_role(run_name, role, mode, k_values, count=65536, region_count=65536,
               *, workers=2, batch_size=32):
    """Resume only validated row shards, then publish the complete role table."""
    from . import conditional_mdn_s5_e3_formal_context as formal
    if workers not in (1, 2) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError('Use one/two spawn workers and positive query batches')
    freeze = freeze_score_inputs(run_name, role, mode, k_values, count, region_count)
    _, run, cfg, _, _ = formal.context(run_name)
    query = inp.cohorts(cfg)[role]['query']
    keys = query[inp.KEY].to_numpy(np.int64)
    folder = score_directory(run, role, mode, count, region_count)
    folder.mkdir(parents=True, exist_ok=True)
    layout = dict(identity_sha256=freeze['identity_sha256'], batch_size=batch_size, query_count=len(query))
    layout_path = folder/'batch_layout.json'
    if layout_path.exists() and json.loads(layout_path.read_text()) != layout:
        raise ValueError('Resumed score batch layout differs')
    atomic_json(layout_path, layout)
    batches = [(i, start, min(start+batch_size, len(query)))
               for i, start in enumerate(range(0, len(query), batch_size))]
    frames, remaining = {}, []
    for number, start, end in batches:
        frame = read_valid_shard(folder, number, freeze['identity_sha256'], keys,
                                 freeze['k_values'], start, end)
        if frame is None:
            remaining.append((number, start, end))
        else:
            frames[number] = frame
    started = time.monotonic()
    if remaining:
        # The only endpoint release is after both immutable freezes exist.
        targets = _targets_in_order(formal.release_targets(
            run_name, role, mode, freeze['k_values'], count, region_count), query)
        context = mp.get_context('spawn')
        stop = context.Event()
        env_names = WORKER_THREAD_ENV
        previous_env = {name: os.environ.get(name) for name in env_names}
        for name in env_names:
            os.environ[name] = '1'
        pool, pending = None, {}
        try:
            pool = cf.ProcessPoolExecutor(max_workers=workers, mp_context=context,
                                          initializer=initialize_worker,
                                          initargs=(run_name, freeze, query, targets, stop))
            jobs = iter(remaining)
            for _ in range(min(workers*2, len(remaining))):
                batch = next(jobs)
                pending[pool.submit(work_batch, batch)] = batch
            while pending:
                done, _ = cf.wait(pending, timeout=30, return_when=cf.FIRST_COMPLETED)
                for future in done:
                    pending.pop(future)
                    number, start, end, rows = future.result()
                    frame = pd.DataFrame(rows)
                    _validate_rows(frame, keys, freeze['k_values'], start, end)
                    write_shard(folder, number, rows, freeze['identity_sha256'], start, end)
                    frames[number] = frame
                    batch = next(jobs, None)
                    if batch is not None:
                        pending[pool.submit(work_batch, batch)] = batch
                progress = dict(role=role, mode=mode, completed_queries=sum(len(f)//len(freeze['k_values'])
                                                                                 for f in frames.values()),
                                total_queries=len(query), elapsed_seconds=time.monotonic()-started,
                                completed_batches=len(frames), total_batches=len(batches))
                atomic_json(folder/'progress.json', progress)
                print(json.dumps(progress), flush=True)
        except BaseException:
            stop.set()
            for future in pending:
                future.cancel()
            raise
        finally:
            if pool is not None:
                pool.shutdown(wait=True, cancel_futures=True)
            for name, value in previous_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
    result = pd.concat([frames[i] for i, _, _ in batches], ignore_index=True)
    _validate_rows(result, keys, freeze['k_values'], 0, len(query))
    _verify_sources(freeze['source_hashes'])
    _atomic_frame(folder/'scores.parquet', result)
    atomic_json(folder/'complete.json', dict(status='complete', identity_sha256=freeze['identity_sha256'],
                role=role, mode=mode, query_count=len(query), query_id_count=int(query.id.nunique()),
                row_count=len(result), k_values=freeze['k_values'], query_key_sha256=freeze['query_key_sha256'],
                scores_sha256=file_sha256(folder/'scores.parquet'), excluded_queries=0,
                count=count, region_count=region_count, final_test_access=False))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_name')
    parser.add_argument('role', choices=tuple(inp.EXPECTED))
    parser.add_argument('mode', choices=MODES)
    parser.add_argument('--k-values', nargs='+', type=int, default=list(K_CANDIDATES))
    parser.add_argument('--count', type=int, default=65536)
    parser.add_argument('--region-count', type=int, default=65536)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--batch-size', type=int, default=32)
    args = parser.parse_args()
    score_role(args.run_name, args.role, args.mode, args.k_values, args.count, args.region_count,
               workers=args.workers, batch_size=args.batch_size)


if __name__ == '__main__':
    main()
