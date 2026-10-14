from data3001.paths import legacy_path, asset_path, project_paths, ensure_output_path, frozen_action
import hashlib
import math
import numbers


def canonical_id(value):
    if isinstance(value, numbers.Integral) and not isinstance(value, bool):
        text = str(int(value))
    elif isinstance(value, str) and value.strip().isdigit():
        text = str(int(value.strip()))
    else:
        raise ValueError('GDP ID must be a positive integer, represented without floating-point conversion')
    if int(text) <= 0:
        raise ValueError('GDP ID must be positive')
    return text

def split_id(value):
    digest = hashlib.sha256(('20261004:' + canonical_id(value)).encode('ascii')).digest()
    score = int.from_bytes(digest, 'big')
    scale = 1 << 256
    return 'train' if score*100 < 70*scale else ('validation' if score*100 < 85*scale else 'test')

def grid_cell(lon, lat, resolution=1):
    if not (math.isfinite(lon) and math.isfinite(lat) and -90 <= lat < 90):
        raise ValueError('Invalid half-open latitude–longitude grid coordinate')
    lon = (lon + 180) % 360 - 180
    return (int(math.floor((lon+180)/resolution)), int(math.floor((lat+90)/resolution)))

def closest_endpoint(times, valid, target, tolerance):
    options = [(abs(t-target), t, i) for i,t in enumerate(times) if valid[i] and abs(t-target) <= tolerance]
    if not options:
        return None, None
    _, t, i = min(options)
    return i, t-target

def classify(times, inside, valid, regime, horizon, desired_regime, target):
    # This small-pilot reference uses integer elapsed hours and exact endpoints.
    # It is deliberately separate from a future full label pipeline.
    if target not in ('endpoint', 'stopped'):
        raise ValueError(target)
    if desired_regime not in (0, 1):
        return 'regime_ineligible'
    if not times or times[0] != 0 or not valid[0]:
        return 'invalid_origin'
    if target == 'endpoint':
        try:
            endpoint = times.index(horizon)
        except ValueError:
            return 'missing_endpoint'
        if not valid[endpoint]:
            return 'invalid_endpoint'
        if any(r != desired_regime for r in regime[:endpoint+1]):
            return 'regime_ineligible'
        return 'inside' if inside[endpoint] else 'outside'
    for i,t in enumerate(times):
        if t > horizon:
            break
        if (i and t-times[i-1] != 1) or not valid[i]:
            return 'unresolved_path'
        if regime[i] != desired_regime:
            return 'regime_ineligible'
        if not inside[i]:
            return 'outside'
        if t == horizon:
            return 'inside'
    return 'unresolved_path'


def copy_spans(ranges, chunk_start, chunk_length):
    spans = []
    for begin, end, destination in ranges:
        left = max(begin, chunk_start)
        right = min(end, chunk_start + chunk_length)
        if left < right:
            spans.append((left-chunk_start, right-chunk_start,
                          destination+left-begin, destination+right-begin))
    return spans
