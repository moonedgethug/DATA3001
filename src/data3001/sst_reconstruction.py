"""Source-preserving, retrospective SST covariate reconstruction primitives.

These estimates are not replacement GDP sensor observations. Native standard
errors and OISST analysis errors describe different estimators.
"""
import re
import struct
import hashlib
from pathlib import Path
import numpy as np

AVAILABILITY = 'retrospective_only'


def source_fallback_allowed(status_code):
    """An absent mirror object permits original-file fallback, not fake data."""
    return status_code == 404


def interpolation_path_ok(position_ok, mapping_ok, unresolved_motion):
    return (np.asarray(position_ok, bool) & np.asarray(mapping_ok, bool)
            & ~np.asarray(unresolved_motion, bool))


def verify_frozen(root, hashes):
    for name, expected in hashes.items():
        p = Path(root)/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen dependency changed: {name}')


def verify_cached(payload, receipt, url, metadata_sha256):
    if (receipt['url'] != url or receipt['metadata_sha256'] != metadata_sha256
            or hashlib.sha256(payload).hexdigest() != receipt['response_sha256']):
        raise ValueError('Cached response/request/metadata binding mismatch')


def decode_zarr_chunk(payload, spec, attrs):
    """Decode this asset's packing, masking packed fills before conversion."""
    import numcodecs
    if spec.get('filters') or spec['order']!='C':
        raise ValueError('Unreviewed Zarr encoding')
    raw=numcodecs.get_codec(spec['compressor']).decode(payload)
    a=np.frombuffer(raw,dtype=spec['dtype']).reshape(spec['chunks'])
    valid=np.isfinite(a)
    fill=spec.get('fill_value')
    if isinstance(fill,(int,float)):valid &= a!=fill
    if 'valid_min' in attrs:valid &= a>=attrs['valid_min']
    if 'valid_max' in attrs:valid &= a<=attrs['valid_max']
    return np.where(valid,a.astype(float)*attrs.get('scale_factor',1)+attrs.get('add_offset',0),np.nan)


def paired_metrics(reference,a,b):
    ref=np.asarray(reference,float);a=np.asarray(a,float);b=np.asarray(b,float)
    common=np.isfinite(ref)&np.isfinite(a)&np.isfinite(b)
    out={'n_common':int(common.sum())}
    for name,pred in [('a',a),('b',b)]:
        err=(pred-ref)[common]
        out[name+'_MAE']=float(np.mean(abs(err))) if len(err) else None
        out[name+'_RMSE']=float(np.sqrt(np.mean(err**2))) if len(err) else None
        out[name+'_bias']=float(np.mean(err)) if len(err) else None
    return out


def stencil(lon, lat):
    """Indices and fractions on the actual verified 0.125-centred OISST grid.

    Longitudes use [0,360) with cyclic neighbours; polar extrapolation fails.
    The acquisition runner verifies these centres against every downloaded map.
    """
    x = (np.asarray(lon, float) % 360 - .125) / .25
    y = (np.asarray(lat, float) + 89.875) / .25
    if np.any(~np.isfinite(x)) or np.any(~np.isfinite(y)) or np.any((y < 0) | (y >= 719)):
        raise ValueError('Unavailable OISST latitude bracket')
    return np.floor(x).astype(int) % 1440, np.floor(y).astype(int), x % 1, y % 1


def bilinear(u, v, temperatures):
    u, v = np.asarray(u), np.asarray(v)
    if np.any((u < 0) | (u > 1) | (v < 0) | (v > 1)):
        raise ValueError('Point lies outside interpolation stencil')
    weights = np.stack([(1-u)*(1-v), u*(1-v), (1-u)*v, u*v], axis=-1)
    values = np.asarray(temperatures, float)
    value = np.sum(weights * values, axis=-1)
    value = np.where(np.isfinite(values).all(axis=-1), value, np.nan)
    return value, weights


def error_bound(weights, standard_errors):
    """Upper bound on source-only propagated SD, with arbitrary correlation.

    SD(sum w_i e_i) <= sum |w_i| SD(e_i). This omits representation and
    interpolation error and is NOT the reconstructed hourly SST's total SE.
    """
    errors = np.asarray(standard_errors, float)
    bound = np.sum(np.abs(weights) * errors, axis=-1)
    return np.where((np.isfinite(errors) & (errors >= 0)).all(axis=-1), bound, np.nan)


def short_linear(t, native, accepted, path_ok, raw_missing, max_gap=3):
    """Only closed, contiguous, all-raw-missing native gaps; never chained."""
    t = np.asarray(t, float); native = np.asarray(native, float)
    accepted = np.asarray(accepted, bool); raw_missing = np.asarray(raw_missing, bool)
    path_ok = np.asarray(path_ok, bool)
    n = len(t); out = np.full(n, np.nan)
    left = np.full(n, -1, np.int64); right = left.copy()
    anchors = np.flatnonzero(accepted)
    for a, b in zip(anchors[:-1], anchors[1:]):
        if not (1 <= b-a-1 <= max_gap):
            continue
        if not raw_missing[a+1:b].all() or not path_ok[a:b+1].all():
            continue
        if not (np.diff(t[a:b+1]) == 3600).all():
            continue
        w = (t[a+1:b]-t[a])/(t[b]-t[a])
        out[a+1:b] = (1-w)*native[a]+w*native[b]
        left[a+1:b] = a; right[a+1:b] = b
    return out, left, right


def parse_dods(payload, variable):
    """Decode a single DAP2 Float32 Grid and verify every XDR count.

    The exact response bytes are retained and hashed by the acquisition runner.
    This intentionally accepts only the inspected NOAA PSL response shape.
    """
    header, data = payload.split(b'\nData:\n', 1)
    match = re.search(rb'Float32 '+variable.encode()+rb'\[time = (\d+)\]\[lat = (\d+)\]\[lon = (\d+)\]', header)
    if match is None:
        raise ValueError('Unexpected DAP Grid schema')
    shape = tuple(map(int, match.groups())); offset = 0
    def array(n, dtype):
        nonlocal offset
        counts = struct.unpack_from('>II', data, offset); offset += 8
        if counts != (n, n):
            raise ValueError('DAP count mismatch')
        ans = np.frombuffer(data, dtype=dtype, count=n, offset=offset).astype(dtype.replace('>', '='))
        offset += n*np.dtype(dtype).itemsize
        return ans
    values = array(int(np.prod(shape)), '>f4').reshape(shape)
    times = array(shape[0], '>f8'); lat = array(shape[1], '>f4'); lon = array(shape[2], '>f4')
    if offset != len(data):
        raise ValueError('Unexpected trailing DAP bytes')
    return values, times, lat, lon
