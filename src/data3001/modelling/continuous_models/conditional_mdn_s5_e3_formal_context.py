"""Release validation labels only after complete forecasts and streams freeze."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from data3001.paths import file_sha256
from . import conditional_mdn_s5_e3_inputs as inp
from .conditional_mdn_s5_e3_runtime import ROOT, atomic_json

_CONTEXT = {}
_TARGETS = {}
CANDIDATES = (1, 2, 4, 8, 16, 32)


def authorization(run, cfg):
    path = run['provenance']/'formal_v1/authorization.json'
    if not path.exists():
        raise PermissionError('Full experiment authorization required')
    value = json.loads(path.read_text())
    if value.get('status') != 'approved' or not value.get('full_experiment_authorized'):
        raise PermissionError('Full experiment not approved')
    if (value.get('contract_sha256') != cfg['contract_sha256'] or
        value.get('scientific_definition_unchanged') is not True or
        value.get('final_test_access') is not False):
        raise ValueError('Scientific authorization identity mismatch')
    return value


def completed_selection(path):
    path = Path(path)
    if not path.exists():
        raise PermissionError('Outer phase requires completed inner selection')
    value = json.loads(path.read_text())
    if value.get('status') != 'complete':
        raise PermissionError('Inner selection is not complete')
    if value.get('selected_k') not in CANDIDATES:
        raise ValueError('Unregistered selected K')
    return value


def context(name):
    # Audit hooks cannot be removed: one shared guard per process avoids stale
    # closed guards blocking a correctly authorized later scoring stage.
    if name not in _CONTEXT:
        value = inp.context(name, guarded=False)
        authorization(value[1], value[2])
        sys.addaudithook(value[4])
        _CONTEXT[name] = value
    return _CONTEXT[name]


def checked_file(base, relative, digest):
    path = (base/relative).resolve()
    if not path.is_relative_to(base.resolve()) or file_sha256(path) != digest:
        raise ValueError('Frozen file identity mismatch: '+str(relative))
    return path


def validate_stream_integrity(stream, forecast_path, query, role, mode, k_values, count, region_count):
    """Verify the receipt and reconstruct its target-free stream declaration."""
    from .conditional_mdn_s5_e3_formal_scoring import stream_manifest, validate_request
    validate_request(role, mode, k_values, count, region_count)
    content = {key: value for key, value in stream.items() if key != 'identity_sha256'}
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':'),
                                      allow_nan=False).encode()).hexdigest()
    if stream.get('identity_sha256') != digest:
        raise ValueError('Scoring freeze canonical identity mismatch')
    if stream.get('forecast_freeze_sha256') != file_sha256(forecast_path):
        raise ValueError('Scoring stream freeze belongs to different forecasts')
    sources = stream.get('source_hashes')
    schedule = stream.get('streams')
    if (not isinstance(sources, dict) or not sources or not isinstance(schedule, dict)
            or not schedule.get('streams') or not schedule.get('all_streams')):
        raise ValueError('Scoring freeze lacks sources or complete primary/audit streams')
    expected = stream_manifest(query, role, mode, count, region_count)
    if schedule != expected or stream.get('node_key_sha256') != expected['node_key_sha256']:
        raise ValueError('Frozen numerical streams differ from registered seed identities')
    for relative, checksum in sources.items():
        checked_file(ROOT, relative, checksum)


def release_targets(name, role, mode, k_values, count, region_count):
    _, run, cfg, approval, guard = context(name)
    auth = authorization(run, cfg)
    # The audit hook is cached, but protected inputs must still be current at
    # every release; unchanged source keys alone cannot detect changed labels.
    for relative, checksum in approval['protected_files'].items():
        checked_file(ROOT, relative, checksum)
    query = inp.cohorts(cfg)[role]['query']
    base = run['results']/'formal_v1'
    prov = run['provenance']/'formal_v1'
    path = prov/role/'forecast_freeze.json'
    if not path.exists():
        raise PermissionError('Complete six-model forecast freeze required')
    forecast = json.loads(path.read_text())
    if (forecast.get('status') != 'complete' or forecast.get('role') != role or
        forecast.get('query_count') != len(query) or
        forecast.get('query_key_sha256') != inp.key_digest(query) or
        set(forecast.get('models', {})) != set(map(str, CANDIDATES)) or
        forecast.get('outer_targets_read') is not False):
        raise ValueError('Incomplete or changed forecast roster')
    hashes = {}
    for k, record in forecast['models'].items():
        checked_file(base, record['manifest'], record['manifest_sha256'])
        checked_file(base, record['parameters'], record['parameters_sha256'])
        hashes[k] = record['parameters_sha256']
    stream_path = prov/role/mode/f'inputs_N{count}_M{region_count}.json'
    if not stream_path.exists():
        raise PermissionError('Frozen scoring streams required before targets')
    stream = json.loads(stream_path.read_text())
    if (stream.get('status') != 'complete' or stream.get('role') != role or
        stream.get('mode') != mode or stream.get('query_count') != len(query) or
        stream.get('query_key_sha256') != inp.key_digest(query) or
        tuple(stream.get('k_values', [])) != tuple(sorted(k_values)) or
        stream.get('count') != count or stream.get('region_count') != region_count or
        stream.get('parameter_hashes') != {str(k): hashes[str(k)] for k in sorted(k_values)}):
        raise ValueError('Scoring freeze identity mismatch')
    validate_stream_integrity(stream, path, query, role, mode, k_values, count, region_count)
    if role == 'C_outer':
        from .conditional_mdn_s5_e3_formal_pipeline import validate_selection
        selection_path = base/'selection.json'
        validate_selection(run)
        selected = completed_selection(selection_path)
        if (forecast.get('selection_sha256') != file_sha256(selection_path) or
            forecast.get('selected_k') != selected['selected_k']):
            raise ValueError('Outer forecasts do not match frozen selection')
    cache_key = (name, role)
    if cache_key not in _TARGETS:
        if role == 'C_outer':
            source = ROOT/auth['deferred_target_path']
            previous_permission = guard.outer_allowed
            try:
                guard.outer_allowed = True
                if file_sha256(source) != auth['deferred_target_sha256']:
                    raise ValueError('Outer target source changed')
                table = inp.read_frame(source, columns=inp.KEY+['endpoint_lon','endpoint_lat','outside'])
            finally:
                guard.outer_allowed = previous_permission
            if table.outside.any():
                raise ValueError('Observed exit cannot be assigned an artificial coordinate')
            table = table.drop(columns='outside')
        else:
            source = ROOT/'results/runs'/cfg['e7_run']/'training_coordinates.parquet'
            table = inp.read_frame(source, columns=inp.KEY+['endpoint_lon','endpoint_lat'],
                                   filters=[('origin_source_obs','in',query.origin_source_obs.astype(int).tolist()),
                                            ('horizon_days','==',7)])
        target = query[inp.KEY].merge(table, on=inp.KEY, how='left', validate='one_to_one', indicator=True)
        if not target._merge.eq('both').all() or not np.isfinite(target[['endpoint_lon','endpoint_lat']]).all().all():
            raise ValueError('Target roster incomplete or nonfinite')
        _TARGETS[cache_key] = target.drop(columns='_merge')
    atomic_json(prov/role/mode/f'target_release_N{count}_M{region_count}.json', dict(
        status='complete', query_count=len(query), query_key_sha256=inp.key_digest(query),
        forecast_sha256=file_sha256(path), scoring_freeze_sha256=file_sha256(stream_path),
        outer_targets_read=guard.outer_read, final_test_access=False, denied=guard.denied))
    return _TARGETS[cache_key].copy()
