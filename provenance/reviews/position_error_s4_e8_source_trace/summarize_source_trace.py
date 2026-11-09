"""Verify source-trace evidence against frozen training endpoints only."""
import hashlib
import json
from pathlib import Path
import netCDF4 as nc
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def main():
    pairs = pd.read_parquet(ROOT / 'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/training_coordinates.parquet')
    reports = []
    for ident in [7647, 99004, 300234066710170]:
        group = pairs[pairs.id == ident]
        local = pd.read_parquet(ROOT / f'data/train/{ident}.parquet',
            columns=['source_obs', 'time', 'lon', 'lat', 'err_lon', 'err_lat'],
            filters=[('source_obs', 'in', group.endpoint_source_obs.tolist())])
        report = {'id': ident, 'frozen_training_endpoints': len(local), 'axes': {}}
        with nc.Dataset(OUT / f'sources/legacy_v2_00_{ident}.nc') as old, nc.Dataset(OUT / f'sources/erddap_native_{ident}.nc') as new:
            old.set_auto_maskandscale(False); new.set_auto_maskandscale(False)
            oldtime = pd.Index(old['time'][:].ravel()); newtime = pd.Index(new['time'][:].ravel())
            assert oldtime.is_unique and newtime.is_unique
            oi = oldtime.get_indexer(local.time); ni = newtime.get_indexer(local.time)
            assert np.all(oi >= 0) and np.all(ni >= 0)
            report['location_type'] = new.getncattr('location_type')
            report['timestamps_all_match'] = True
            report['coordinates_match_at_canonical_float32_precision'] = {}
            for field, alias in [('lon', 'longitude'), ('lat', 'latitude')]:
                oname = field if field in old.variables else alias
                nname = field if field in new.variables else alias
                a = old[oname][:].ravel()[oi].astype('float32')
                b = new[nname][:].ravel()[ni].astype('float32')
                c = local[field].to_numpy('float32')
                assert np.array_equal(a, c) and np.array_equal(b, c)
                report['coordinates_match_at_canonical_float32_precision'][field] = True
            for field in ['err_lon', 'err_lat']:
                a = old[field][:].ravel()[oi].astype(float)
                b = new[field][:].ravel()[ni].astype(float)
                c = local[field].to_numpy(float)
                assert np.array_equal(b.astype('float32'), c.astype('float32'), equal_nan=True)
                regular = np.isfinite(c) & (c > 0) & (a > 0)
                ratios = a[regular] / c[regular]
                near = np.isclose(ratios, 100000, rtol=1e-6, atol=0)
                report['axes'][field] = {
                    'native_current_matches_canonical_float32': True,
                    'positive_comparable_count': int(regular.sum()),
                    'factor_100000_count': int(near.sum()),
                    'other_positive_count': int((~near).sum()),
                    'ratio_min': float(ratios.min()), 'ratio_max': float(ratios.max()),
                    'old_name': old[field].getncattr('long_name'),
                    'new_name': new[field].getncattr('long_name'),
                    'old_units': old[field].getncattr('units'),
                    'new_units': new[field].getncattr('units'),
                    'packing_attributes_old': [x for x in old[field].ncattrs() if x in ['scale_factor', 'add_offset']],
                    'packing_attributes_new': [x for x in new[field].ncattrs() if x in ['scale_factor', 'add_offset']],
                }
        reports.append(report)
    old = json.loads((OUT / 'ncei_1_1_exceptions.json').read_text())
    latest = json.loads((OUT / 'ncei_3_3_exceptions.json').read_text())
    assert not old['unmatched'] and not latest['unmatched']
    counts = {'scaled_positive': 0, 'unchanged_positive': 0, 'negative_lat_from_old_zero': 0,
              'missing_lon_from_old_zero': 0, 'missing_from_old_fill': 0}
    for row in old['samples']:
        for key in ['err_lon', 'err_lat']:
            a = row[key]['archive_raw']; c = row[key]['canonical']
            if c > 0 and a > 0:
                if np.isclose(a/c, 1e5, rtol=1e-6): counts['scaled_positive'] += 1
                else:
                    assert a == c
                    counts['unchanged_positive'] += 1
            elif c < 0:
                assert key == 'err_lat' and a == 0 and np.isclose(c, -999999e-5)
                counts['negative_lat_from_old_zero'] += 1
            elif np.isnan(c):
                if a == 0:
                    assert key == 'err_lon'; counts['missing_lon_from_old_zero'] += 1
                else:
                    assert a < -1e30; counts['missing_from_old_fill'] += 1
            else:
                raise AssertionError('Unclassified case')
    assert sum(counts.values()) == 2 * len(old['samples'])
    for row in latest['samples']:
        for key in ['lon', 'lat', 'err_lon', 'err_lat']:
            a = row[key]['archive_raw']; c = row[key]['canonical']
            assert a == c or (np.isnan(c) and (np.isnan(a) or a == -999999))
    result = {'date': '2026-11-06', 'scope': 'read-only source audit, frozen training endpoints only',
              'model_runs': 0, 'canonical_modified': False, 'outer_validation_labels_read': False,
              'locked_final_test_read': False, 'native_comparisons': reports,
              'exception_probe': {'IDs': len(set(x['id'] for x in old['samples'])),
                  'observations': len(old['samples']), 'axis_value_classification': counts,
                  'latest_archive_values_and_coordinates_match_canonical': True},
              'current_delivery_route_probe': json.loads((OUT / 'current_delivery_route_comparison.json').read_text()),
              'interpretation': {
                  'confirmed': 'Upstream version and delivery-route scale discrepancy, mixed with missing-value anomalies. Not a local cleaning or CF decoding change.',
                  'strong_hypothesis': 'An extra 1e-5 legacy-unit conversion, with conditional missing-value handling.',
                  'not_confirmed': 'Exact v2.01 production code line, universal correction rule, and empirical CI calibration.'}}
    (OUT / 'source_trace_summary.json').write_text(json.dumps(result, indent=2) + '\n')
    receipts = {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'sha256_manifest.json'}
    (OUT / 'sha256_manifest.json').write_text(json.dumps(receipts, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
