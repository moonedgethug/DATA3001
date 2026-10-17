"""Simple read-only access to the current per-drifter development/test release."""
from functools import lru_cache
import json
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
from data3001.paths import asset_path,project_paths,file_sha256


@lru_cache(maxsize=2)
def _manifest(path,checksum):
    if file_sha256(path)!=checksum:raise ValueError('Dataset manifest checksum mismatch')
    data=json.loads(path.read_text())
    if data['version'] not in ['per-drifter-20261016-v1','per-drifter-cleaned-20261017-v2',
                               'per-drifter-cleaned-20261017-v3','per-drifter-cleaned-20261017-v4',
                               'per-drifter-cleaned-20261017-v5','per-drifter-cleaned-20261017-v6',
                               'per-drifter-cleaned-20261017-v7'] or len(data['records'])!=data['IDs']:
        raise ValueError('Unexpected dataset manifest')
    if (data['version'] in ['per-drifter-cleaned-20261017-v2','per-drifter-cleaned-20261017-v3',
                            'per-drifter-cleaned-20261017-v4','per-drifter-cleaned-20261017-v5','per-drifter-cleaned-20261017-v6','per-drifter-cleaned-20261017-v7'] and
            data.get('cleaning',{}).get('policy')!='vessel_recovery_last_good_cutoff'):
        raise ValueError('Missing declared cleaning policy')
    if (data['version'] in ['per-drifter-cleaned-20261017-v3','per-drifter-cleaned-20261017-v4',
                            'per-drifter-cleaned-20261017-v5','per-drifter-cleaned-20261017-v6','per-drifter-cleaned-20261017-v7'] and
            data.get('cleaning',{}).get('temperature',{}).get('column')!='sst'):
        raise ValueError('Missing in-column SST cleaning policy')
    if (data['version'] in ['per-drifter-cleaned-20261017-v4','per-drifter-cleaned-20261017-v5','per-drifter-cleaned-20261017-v6','per-drifter-cleaned-20261017-v7'] and
            data.get('cleaning',{}).get('temperature',{}).get('grounding_NA',{}).get('policy')
            !='typedeath_1_time_gt_valid_official_end_date_sst_NA'):
        raise ValueError('Missing approved post-grounding SST policy')
    if (data['version'] in ['per-drifter-cleaned-20261017-v5','per-drifter-cleaned-20261017-v6','per-drifter-cleaned-20261017-v7'] and
            data.get('cleaning',{}).get('drogue_status',{}).get('policy')
            !='exact_regime_transfer_to_drogue_status_then_remove_regime'):
        raise ValueError('Missing approved drogue-status consolidation policy')
    if data['version'] in ['per-drifter-cleaned-20261017-v6','per-drifter-cleaned-20261017-v7']:
        from data3001.hardware_missing import POLICY,FIELDS
        rule=data.get('cleaning',{}).get('hardware_missing',{})
        if rule.get('policy')!=POLICY or rule.get('fields')!=list(FIELDS):
            raise ValueError('Missing approved seven-field hardware NA policy')
    if data['version']=='per-drifter-cleaned-20261017-v7':
        from data3001.feature_pruning import POLICY,PROTECTED
        rule=data.get('cleaning',{}).get('feature_pruning',{})
        if (rule.get('policy')!=POLICY or data.get('fields')!=62 or
                len(rule.get('removed_columns',[]))!=67 or
                len(rule.get('retained_columns',[]))!=62 or
                not set(PROTECTED)<=set(rule['retained_columns']) or
                set(rule['removed_columns'])&set(rule['retained_columns'])):
            raise ValueError('Missing approved feature-pruning policy')
    for id,record in data['records'].items():
        pool=record['pool']
        if (str(int(id))!=id or int(id)<=0 or pool not in ['train','test'] or
            record['path']!=f'data/{pool}/{id}.parquet' or
            (record['historical_split']=='test')!=(pool=='test')):
            raise ValueError('Invalid per-ID dataset routing')
    if sum(r['rows'] for r in data['records'].values())!=data['rows']:
        raise ValueError('Dataset manifest row total mismatch')
    return data


def manifest():
    spec=project_paths().catalog['assets']['current_dataset_manifest']
    return _manifest(asset_path('current_dataset_manifest'),spec['sha256'])


def track_path(id, *, allow_test=False):
    id=int(id);record=manifest()['records'][str(id)]
    if record['pool']=='test' and not allow_test:
        raise PermissionError('Final-test trajectories require explicit permission')
    key='current_test_tracks' if record['pool']=='test' else 'current_train_tracks'
    base=asset_path(key,allow_test=allow_test)
    path=base/f'{id}.parquet'
    if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
        raise PermissionError('Track path escapes its declared pool')
    if file_sha256(path)!=record['sha256']:
        raise ValueError(f'Current track checksum mismatch: {id}')
    return path


def read_track(id, *, allow_test=False):
    """Read the cleaned stored fields/rows for one ID; no extra feature columns.

    SST fills/corrections are already materialized in sst. This function makes
    no new cleaning or imputation decisions while reading.
    """
    id=int(id);path=track_path(id,allow_test=allow_test)
    record=manifest()['records'][str(id)];table=pq.read_table(path)
    context=json.loads(table.schema.metadata[b'data3001'])
    if str(context['id'])!=str(id) or context['pool']!=record['pool']:
        raise ValueError('Track identity metadata mismatch')
    frame=table.to_pandas()
    if len(frame)!=record['rows'] or not frame.id.eq(id).all():
        raise ValueError('Track identity or row count mismatch')
    frame.attrs['data3001']=context
    return frame


def development_ids():
    """All original train + validation IDs; final test is not returned."""
    return sorted(int(id) for id,r in manifest()['records'].items() if r['pool']=='train')


class PreparedSource:
    """Manifest-backed cohort context for labels; no raw acquisition required."""
    def __init__(self, *, allow_test=False):
        self.allow_test = allow_test
        records = manifest()['records']
        self.cohort = pd.DataFrame([
            {'id': int(sid), 'split': record['historical_split']}
            for sid, record in records.items()]).set_index('id')


def verify_current_data(progress=None):
    """Verify the distributed data and qualification files without local backups."""
    from data3001.feature_pruning import qualification_arrays
    paths = project_paths(); current = manifest()
    definition = json.loads(paths.asset('current_dataset_schema', verify=True).read_text())
    names = [f['name'] for f in definition['fields']]
    qualified = paths.catalog['assets'].get('current_qualification_manifest')
    qfields = []
    if qualified:
        qm = json.loads(paths.asset('current_qualification_manifest', verify=True).read_text())
        if set(qm['records']) != set(current['records']):
            raise ValueError('Portable qualification ID inventory mismatch')
        qfields = [n for n in qm['fields'] if n not in ['id', 'source_obs', 'time']]
    rows = 0; qfiles = 0; pools = {'train': 0, 'test': 0}
    for n, (sid, record) in enumerate(current['records'].items(), 1):
        path = track_path(int(sid), allow_test=True)
        parquet = pq.ParquetFile(path); schema = parquet.schema_arrow
        if (schema.names != names or parquet.metadata.num_rows != record['rows']
                or [str(f.type) for f in schema] != [f['arrow_type'] for f in definition['fields']]):
            raise ValueError('Distributed track schema or row count mismatch: '+sid)
        context = json.loads(schema.metadata[b'data3001'])
        if str(context['id']) != sid or context['pool'] != record['pool']:
            raise ValueError('Distributed track identity mismatch: '+sid)
        if qfields:
            frame = parquet.read(columns=['id', 'source_obs', 'time']).to_pandas()
            frame.attrs['data3001'] = context
            qualification_arrays(int(sid), frame, qfields, allow_test=True)
            qfiles += 1
        rows += record['rows']; pools[record['pool']] += 1
        if progress and n % 500 == 0: progress(f'Verified {n}/{current["IDs"]} distributed tracks')
    if rows != current['rows'] or pools != current['pools']:
        raise ValueError('Distributed totals differ from the manifest')
    return {'passed': True, 'release': current['version'], 'IDs': current['IDs'],
            'rows': rows, 'fields': current['fields'], 'pools': pools,
            'qualification_files': qfiles, 'all_published_file_checksums_verified': True,
            'local_raw_cache_or_full_parent_required': False,
            'forecast_accuracy_evaluated': False}
