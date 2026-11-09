"""Replay lifecycle source recovery and preservation checks; never write data."""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json
import math

import netCDF4
import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
FIELDS = ('deploy_date', 'deploy_lat', 'deploy_lon', 'start_date', 'start_lat',
          'start_lon', 'end_date', 'end_lat', 'end_lon', 'typedeath')
FROZEN = ROOT/'archive/data_before_release_20261016/reference/acquisition/metadata/trajectory_metadata.npz'


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b''):
            value.update(chunk)
    return value.hexdigest()


def missing(value):
    return value is None or (isinstance(value, (float, np.floating)) and not math.isfinite(value))


def raw_scalar(dataset, name):
    var = dataset[name]
    value = np.asarray(var[:]).ravel()[0].item()
    attrs = {k: var.getncattr(k) for k in ('_FillValue', 'missing_value', 'units', 'history') if k in var.ncattrs()}
    invalid = missing(value)
    for name in ('_FillValue', 'missing_value'):
        if name in attrs:
            invalid = invalid or any(value == code for code in np.asarray(attrs[name]).ravel())
    attrs = {k: (v.item() if isinstance(v, np.generic) else v) for k,v in attrs.items()}
    return {'raw_value': value, 'declared_missing': bool(invalid), 'attributes': attrs}


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main():
    scope = json.loads((RUN/'scope.json').read_text())
    manifest_path = ROOT/'configs/dataset_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert sha(manifest_path) == scope['manifest_sha256']
    assert sha(ROOT/'configs/dataset_schema.json') == scope['schema_sha256']
    assert sha(ROOT/'docs/contract/data_contract_v1.0.xlsx') == scope['contract_sha256']
    frozen = np.load(FROZEN)
    indices = {str(int(sid)): number for number,sid in enumerate(frozen['id'])}
    target_ids = sorted(set().union(*map(set, scope['missing_IDs_by_field'].values())))
    current = {}
    for sid in target_ids:
        path = ROOT/manifest['records'][sid]['path']
        current[sid] = next(pq.ParquetFile(path).iter_batches(batch_size=1,
            columns=list(FIELDS)+['WMO','expno'])).to_pylist()[0]
        for field in FIELDS:
            old = frozen[field][indices[sid]].item()
            now = current[sid][field]
            assert (missing(old) and missing(now)) or old == now, (sid,field,'frozen source changed')
    log_path = ROOT/'results/runs/feature_review_batch11_20261017_v1/deployment_source_candidates.json'
    log = json.loads(log_path.read_text())
    log_content = ROOT/'results/runs/feature_review_batch11_20261017_v1/sources/deployment_log.html'
    assert sha(log_content) == log['source_receipt']['sha256']
    nc_evidence = {}
    failures = []
    for sid in scope['missing_IDs_by_field']['deploy_date']:
        path = RUN/'sources'/f'drifter_hourly_{sid}.nc'
        if not path.exists():
            failures.append(sid)
            continue
        receipt = json.loads((RUN/'sources'/f'drifter_hourly_{sid}.receipt.json').read_text())
        assert sha(path) == receipt['sha256'] and path.stat().st_size == receipt['bytes']
        with netCDF4.Dataset(path) as dataset:
            dataset.set_auto_mask(False)
            identifier = np.asarray(dataset['ID'][:]).tobytes().decode().strip('\x00 ')
            assert identifier == sid and dataset.getncattr('id').strip().endswith(' '+sid), sid
            evidence = {
                'source_URL': receipt['url'], 'source_sha256': receipt['sha256'],
                'source_ID': identifier, 'history': dataset.getncattr('history'),
                'date_created': dataset.getncattr('date_created'),
                'fields': {field:raw_scalar(dataset,field) for field in FIELDS},
                'WMO': int(dataset['WMO'][:].ravel()[0]),
                'expno': int(dataset['expno'][:].ravel()[0]),
            }
            assert evidence['WMO'] == current[sid]['WMO'] and evidence['expno'] == current[sid]['expno'], sid
            for field in FIELDS:
                source = evidence['fields'][field]
                value = current[sid][field]
                if missing(value):
                    assert source['declared_missing'], (sid,field,'potential restoration requires adjudication')
                else:
                    assert not source['declared_missing']
                    # The downloaded cloud product stores these native metadata as float32.
                    expected = (np.float32(source['raw_value']).item() if field != 'typedeath'
                                else source['raw_value'])
                    assert value == expected, (sid,field,'nonmissing source mismatch')
        nc_evidence[sid] = evidence
    field_rows = []
    for field, ids in scope['missing_IDs_by_field'].items():
        for sid in ids:
            assert missing(current[sid][field]) and missing(frozen[field][indices[sid]].item())
            source = nc_evidence.get(sid, {}).get('fields', {}).get(field)
            if field.startswith('end_'):
                assert current[sid]['typedeath'] == int(frozen['typedeath'][indices[sid]]) == 0
                reason = 'frozen_alive_snapshot_no_termination_record'
            elif field == 'deploy_date' and log['raw_matches'][sid]:
                assert len(log['raw_matches'][sid]) == 1
                reason = 'official_product_missing_log_date_discrepancy_unresolved'
            else:
                reason = 'official_product_missing_no_exact_deployment_log_match'
            field_rows.append({'id':sid, 'pool':manifest['records'][sid]['pool'],
                'field':field, 'current_value':'NA', 'frozen_acquisition_value':'NA',
                'official_NetCDF_raw_value':source['raw_value'] if source else '',
                'official_NetCDF_declares_missing':source['declared_missing'] if source else '',
                'decision':'retain_numeric_missing', 'reason':reason})
    assert len(target_ids) == 227 and len(field_rows) == 616
    write_csv(RUN/'per_field_audit.csv', field_rows)
    grouped = []
    for sid in target_ids:
        cases = [r for r in field_rows if r['id'] == sid]
        grouped.append({'id':sid, 'pool':manifest['records'][sid]['pool'],
            'missing_fields':';'.join(r['field'] for r in cases),
            'original_hourly_NetCDF_checked':sid in nc_evidence,
            'exact_deployment_log_match':bool(log['raw_matches'].get(sid)),
            'typedeath':current[sid]['typedeath'], 'accepted_restorations':0,
            'reasons':';'.join(sorted({r['reason'] for r in cases}))})
    write_csv(RUN/'per_ID_audit.csv', grouped)
    (RUN/'original_NetCDF_evidence.json').write_text(json.dumps(nc_evidence, indent=2)+'\n')
    rows = 0
    for number, (sid,entry) in enumerate(manifest['records'].items(),1):
        path = ROOT/entry['path']
        assert sha(path) == entry['sha256'], sid
        metadata = pq.read_metadata(path)
        assert metadata.num_rows == entry['rows'] and metadata.num_columns == scope['columns']
        rows += metadata.num_rows
        if number % 500 == 0:
            print('Preserved data file hashes',number,'/',manifest['IDs'],flush=True)
    assert rows == scope['rows']
    totals = Counter(r['reason'] for r in field_rows)
    summary = {'complete':True,'release_unchanged':scope['release'],
        'scoped_IDs':len(target_ids),'missing_ID_field_cases':len(field_rows),
        'all_missing_cases_match_frozen_official_acquisition':True,
        'original_NetCDF_deployment_IDs_checked':len(nc_evidence),
        'original_NetCDF_deployment_IDs_not_retrieved':failures,
        'original_NetCDF_candidate_values_accepted':0,
        'all_190_missing_end_triplets_have_frozen_alive_code':True,
        'retained_missing_IDs_by_field':{k:len(v) for k,v in scope['missing_IDs_by_field'].items()},
        'field_dispositions':dict(totals),'accepted_IDs':0,'accepted_fields':0,
        'new_active_feature_columns':[], 'data_files_modified':0,
        'all_3741_data_file_hashes_unchanged':True,'rows':rows,'columns':scope['columns'],
        'frozen_metadata_path':str(FROZEN.relative_to(ROOT)),'frozen_metadata_sha256':sha(FROZEN),
        'manifest_sha256':scope['manifest_sha256'],'contract_sha256':scope['contract_sha256'],
        'NA_representation':'Existing numeric NaN/Arrow null retained; no string NA or physical zero substituted.',
        'forecast_accuracy_evaluated':False,
        'coverage_limit':'No accepted recovery in inspected sources; unpublished corrections or future official releases may provide other evidence.'}
    (RUN/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
