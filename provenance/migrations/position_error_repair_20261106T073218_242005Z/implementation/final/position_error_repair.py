"""Conservative, source-backed position-error overlays; never changes base data."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
from pyproj import Geod

POLICY = 'position-error-native-reference-v1'
CUTOFF = pd.Timestamp('2020-06-30T23:00:00Z').timestamp()
EPOCH_UNITS = 'seconds since 1970-01-01 00:00:00 UTC'
ACCEPTED = {'verified_unchanged', 'restored_scale', 'recovered_from_reference'}
GEOD = Geod(ellps='WGS84')


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def jsonable(value):
    if isinstance(value, bytes):
        return value.decode('utf-8').strip('\x00 ')
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def attributes(obj):
    return {k: jsonable(obj.getncattr(k)) for k in obj.ncattrs()}


def numeric_attribute(value):
    """Accept documented legacy numeric strings, never evaluate source text."""
    if isinstance(value, bytes):
        value = value.decode()
    if isinstance(value, str):
        if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[fFdD]?', value.strip()):
            raise ValueError('Unrecognized numeric attribute')
        return float(value.strip().rstrip('fFdD'))
    return float(value)


def decode_values(raw, attrs):
    """Mask external missing values before the single declared packing transform."""
    raw = np.asarray(raw)
    bad = ~np.isfinite(raw)
    for key in ['_FillValue', 'missing_value']:
        if key in attrs:
            for marker in np.asarray(attrs[key]).ravel():
                v = np.asarray(numeric_attribute(marker), dtype=raw.dtype)
                bad |= raw == v
    values = raw.astype('float64')
    values[bad] = np.nan
    scale = numeric_attribute(attrs.get('scale_factor', 1))
    offset = numeric_attribute(attrs.get('add_offset', 0))
    if not np.isfinite(scale) or not np.isfinite(offset) or scale <= 0:
        raise ValueError('Invalid packing transform')
    values[~bad] = values[~bad] * scale + offset
    return values, bad


def epoch_values(raw, attrs):
    vals, _ = decode_values(raw, attrs)
    if not np.isfinite(vals).all():
        raise ValueError('Missing source time')
    calendar = attrs.get('calendar', 'standard')
    if calendar not in ['standard', 'gregorian', 'proleptic_gregorian']:
        raise ValueError('Unsupported calendar')
    dates = netCDF4.num2date(vals, attrs['units'], calendar=calendar,
                            only_use_cftime_datetimes=True)
    return np.asarray(netCDF4.date2num(dates, EPOCH_UNITS, calendar='proleptic_gregorian'), float)


def wrapped(lon):
    return (np.asarray(lon, float) + 180) % 360 - 180


def coordinate_match(lon, lat, source_lon, source_lat):
    # Canonical source coordinates were float32, before lossless float64 storage.
    return ((wrapped(lon).astype('float32') == wrapped(source_lon).astype('float32'))
            & (np.asarray(lat).astype('float32') == np.asarray(source_lat).astype('float32')))


def identity_basis(ident, native_id, attrs):
    if native_id == int(ident):
        return 'native_id_exact'
    # Explicit identity crosswalk inside the official file, not suffix matching.
    imei = str(attrs.get('imei', '')).strip()
    if imei.isdigit() and int(imei) == int(ident):
        return 'official_imei_exact'
    raise ValueError('Source ID mismatch')


def classify_axis(current, reference, missing, axis, lat):
    current = np.asarray(current, float)
    ref = np.asarray(reference, float)
    missing = np.asarray(missing, bool)
    result = np.full(len(ref), np.nan)
    state = np.full(len(ref), 'unexplained_difference', dtype=object)
    state[missing | ~np.isfinite(ref)] = 'reference_missing'
    state[np.isfinite(ref) & (ref < 0)] = 'reference_invalid'
    state[ref == 0] = 'zero_unresolved'
    positive = np.isfinite(ref) & (ref > 0) & ~missing
    if axis == 'lon':
        geometry = positive & (ref >= 180)
    else:
        geometry = positive & ((np.asarray(lat) - ref < -90) | (np.asarray(lat) + ref > 90))
    state[geometry] = 'geometry_review_required'
    good = positive & ~geometry
    recover = good & (~np.isfinite(current) | (current < 0))
    state[recover] = 'recovered_from_reference'
    old_positive = good & np.isfinite(current) & (current > 0)
    ratio = np.full(len(ref), np.nan)
    ratio[old_positive] = ref[old_positive] / current[old_positive]
    state[old_positive & np.isclose(ratio, 1, rtol=1e-6, atol=0)] = 'verified_unchanged'
    state[old_positive & np.isclose(ratio, 1e5, rtol=1e-6, atol=0)] = 'restored_scale'
    accepted = np.isin(state, list(ACCEPTED))
    result[accepted] = ref[accepted]
    return result, state


def read_reference(path, ident, targets):
    """Read metadata/time index, then only the authorized observation values."""
    meta = {'sha256': sha256(path), 'id': int(ident), 'eligible': False}
    out = targets[['source_obs']].copy()
    out['match_status'] = 'source_unusable'
    with netCDF4.Dataset(path) as ds:
        ds.set_auto_maskandscale(False)
        ds.set_auto_chartostring(False)
        attrs = attributes(ds)
        raw_id = ds['ID'][:]
        text_id = raw_id.tobytes().decode().strip('\x00 ') if raw_id.dtype.kind == 'S' else str(int(raw_id.ravel()[0]))
        basis = identity_basis(ident, int(text_id), attrs)
        meta.update(global_attributes=attrs, identity_basis=basis, native_id=int(text_id),
                    location_type=attrs.get('location_type', 'unknown'), variables={})
        history = str(attrs.get('history', '')).lower()
        death = int(ds['typedeath'][:].ravel()[0])
        coverage_end = pd.Timestamp(attrs['time_coverage_end']).timestamp()
        meta.update(coverage_end_epoch=coverage_end, typedeath=death)
        # Only the audited native v2.00 family is an approved semantic profile.
        if not re.search(r'version\s+v?2\.00\b', history):
            meta['reason'] = 'version_unresolved'
        elif death not in [1, 2, 3, 4, 5, 6] or coverage_end > CUTOFF:
            meta['reason'] = 'estimation_version_unresolved'
        else:
            end = epoch_values(ds['end_date'][:].ravel(), attributes(ds['end_date']))[0]
            meta['end_epoch'] = float(end)
            if 0 < end <= CUTOFF:
                meta.update(eligible=True, reason='audited_native_v2_00_ended_before_cutoff')
            else:
                meta['reason'] = 'estimation_version_unresolved'
        names = {k: k if k in ds.variables else {'lon':'longitude', 'lat':'latitude'}[k]
                 for k in ['lon', 'lat', 'err_lon', 'err_lat', 'time']}
        for key, name in names.items():
            v = ds[name]
            meta['variables'][key] = {'name': name, 'dtype': str(v.dtype), 'attributes': attributes(v)}
        for axis, unit in [('lon', 'degrees_east'), ('lat', 'degrees_north')]:
            va = meta['variables']['err_' + axis]['attributes']
            if va.get('units') != unit or '95% confidence interval' not in va.get('long_name', '').lower():
                meta.update(eligible=False, reason='semantics_unresolved')
        if not meta['eligible']:
            out['match_status'] = meta['reason']
            return out, meta
        times = epoch_values(ds[names['time']][:].ravel(), attributes(ds[names['time']]))
        lookup = {}
        for index, epoch in enumerate(times):
            lookup.setdefault(float(epoch), []).append(index)
        out['source_indices'] = [json.dumps(lookup.get(float(t), [])) for t in targets.time]
        needed = sorted({j for t in targets.time for j in lookup.get(float(t), [])})
        values = {}
        if needed:
            for key in ['lon', 'lat', 'err_lon', 'err_lat']:
                v = ds[names[key]]
                raw = np.asarray(v[0, needed] if v.ndim == 2 else v[needed])
                val, miss = decode_values(raw, attributes(v))
                invalid = np.zeros(len(raw), bool)
                if key.startswith('err_'):
                    va = attributes(v)
                    if 'valid_range' in va:
                        lo, hi = [numeric_attribute(x) for x in va['valid_range']]
                        invalid |= (raw < lo) | (raw > hi)
                    if 'valid_min' in va: invalid |= raw < numeric_attribute(va['valid_min'])
                    if 'valid_max' in va: invalid |= raw > numeric_attribute(va['valid_max'])
                values[key] = {j: (float(r), float(z), bool(m), bool(iv))
                               for j, r, z, m, iv in zip(needed, raw, val, miss, invalid)}
        records = []
        for row in targets.itertuples(index=False):
            indices = lookup.get(float(row.time), [])
            record = {'source_obs': row.source_obs, 'source_indices': json.dumps(indices),
                      'match_status': 'time_unmatched', 'source_epoch': float(row.time)}
            if not indices:
                records.append(record); continue
            j = indices[0]
            if len(indices) > 1:
                vectors = [[values[k][ix][0] for k in values] for ix in indices]
                if any(not np.array_equal(vectors[0], x, equal_nan=True) for x in vectors[1:]):
                    record['match_status'] = 'duplicate_conflict'; records.append(record); continue
            for key in values:
                r, z, m, iv = values[key][j]
                record['raw_' + key] = r
                record['ref_' + key] = z
                if key.startswith('err_'):
                    record['missing_' + key] = m
                    record['invalid_' + key] = iv
            same = coordinate_match(row.lon, row.lat, record['ref_lon'], record['ref_lat'])
            record['match_status'] = 'matched' if same else 'coordinate_changed'
            record['coordinate_distance_m'] = GEOD.inv(row.lon, row.lat, record['ref_lon'], record['ref_lat'])[2]
            records.append(record)
    return pd.DataFrame(records), meta


def build_overlay(targets, references, run_id):
    """Reconcile all eligible sources without silently choosing conflicts."""
    result = targets.copy().reset_index(drop=True)
    for axis in ['lon', 'lat']:
        result['repaired_err_' + axis] = np.nan
        result['status_' + axis] = 'source_missing'
        result['ref_err_' + axis] = np.nan
        result['raw_ref_err_' + axis] = np.nan
    result['source_sha256'] = ''
    result['source_indices'] = '[]'
    result['reference_sources'] = '[]'
    result['source_epoch'] = np.nan
    result['ref_lon'] = np.nan; result['ref_lat'] = np.nan
    result['coordinate_distance_m'] = np.nan
    result['match_status'] = 'source_missing'
    result['location_type'] = 'unknown'
    result['identity_basis'] = ''
    result['source_history'] = ''
    aligned = [(frame.set_index('source_obs').reindex(result.source_obs), meta)
               for frame, meta in references]
    for pos, row in result.iterrows():
        options = [(frame.iloc[pos], meta) for frame, meta in aligned]
        matches = [(r, m) for r, m in options if r.match_status == 'matched' and m['eligible']]
        if not matches:
            if options:
                # Prefer a concrete identity match failure over a generic absent source.
                chosen = next(((r,m) for r,m in options if r.match_status == 'coordinate_changed'), options[0])
                r, m = chosen
                result.at[pos, 'match_status'] = r.match_status
                result.at[pos, 'source_sha256'] = m['sha256']
                result.at[pos, 'location_type'] = m.get('location_type', 'unknown')
                result.at[pos, 'identity_basis'] = m.get('identity_basis', '')
                for axis in ['lon','lat']: result.at[pos, 'status_' + axis] = r.match_status
                for field in ['ref_lon','ref_lat','source_epoch','coordinate_distance_m','source_indices']:
                    if field in r: result.at[pos,field] = r[field]
            continue
        r, m = matches[0]
        result.at[pos, 'reference_sources'] = json.dumps([mm['sha256'] for _,mm in matches])
        result.at[pos, 'source_sha256'] = m['sha256']
        result.at[pos, 'source_indices'] = r.source_indices
        result.at[pos, 'source_epoch'] = r.source_epoch
        result.at[pos, 'identity_basis'] = m['identity_basis']
        result.at[pos, 'source_history'] = m['global_attributes'].get('history','')
        result.at[pos, 'location_type'] = m['location_type']
        for name in ['ref_lon','ref_lat','coordinate_distance_m']: result.at[pos,name] = r[name]
        conflict = False
        for other, _ in matches[1:]:
            for axis in ['lon','lat']:
                a = r['ref_err_' + axis]; b = other['ref_err_' + axis]
                if not ((np.isnan(a) and np.isnan(b)) or np.float32(a) == np.float32(b)):
                    conflict = True
        result.at[pos, 'match_status'] = 'reference_conflict' if conflict else 'matched'
        for axis in ['lon','lat']:
            result.at[pos,'ref_err_' + axis] = r['ref_err_' + axis]
            result.at[pos,'raw_ref_err_' + axis] = r['raw_err_' + axis]
            if conflict:
                result.at[pos,'status_' + axis] = 'reference_conflict'; continue
            if r['invalid_err_' + axis] and not r['missing_err_' + axis]:
                result.at[pos,'status_' + axis] = 'reference_invalid'; continue
            fixed, status = classify_axis([row['original_err_' + axis]], [r['ref_err_' + axis]],
                                         [r['missing_err_' + axis]], axis, [row.lat])
            result.at[pos,'repaired_err_' + axis] = fixed[0]
            result.at[pos,'status_' + axis] = status[0]
    result['ci_2d_usable'] = result.status_lon.isin(ACCEPTED) & result.status_lat.isin(ACCEPTED)
    result['repair_version'] = run_id
    result['policy'] = POLICY
    result['transform'] = 'copy verified native decoded degrees; missing masked before packing; no inferred scale'
    return result
