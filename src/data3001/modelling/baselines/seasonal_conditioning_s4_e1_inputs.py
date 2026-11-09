"""Verified chronological inputs for S4 E1 v2; no model fitting."""
import json
import numpy as np
import pandas as pd

from data3001.paths import file_sha256
from data3001.modelling.common.qualified_count_inputs import counts_from_labels, read_frame

KEY = ['id', 'origin_source_obs', 'horizon_days']
COUNT = ['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1']
SEASON_COUNT = ['id', 'horizon_days', 'origin_cell_1', 'departure_season', 'destination_cell_1']
FEATURES = KEY + ['origin_time_UTC', 'origin_cell_1', 'departure_season']


def season_code(times):
    if str(times.dt.tz) != 'UTC' or times.isna().any():
        raise ValueError('Valid UTC departure times required')
    return ((times.dt.month % 12) // 3).astype('int8')


def assign_roles(q, config):
    """Validation-ID union is fixed before any training-support mask."""
    t0 = q.origin_time_UTC
    cut = pd.Timestamp(config['cutoff'], tz='UTC')
    validation = t0.ge(cut) & t0.lt(pd.Timestamp(config['validation_end'], tz='UTC'))
    ids = sorted(q.loc[validation, 'id'].unique().tolist())
    candidate = t0.ge(pd.Timestamp(config['train_start'], tz='UTC')) & t0.lt(cut)
    crossing = candidate & q.required_interval_end_epoch.ge(cut.timestamp())
    held_id = candidate & q.id.isin(ids)
    train = candidate & ~crossing & ~held_id
    role = np.select([validation, crossing, candidate & ~crossing & held_id, train],
                     ['validation', 'excluded_label_cutoff', 'excluded_validation_id', 'train'],
                     default='outside_training_window')
    roles = q[KEY].copy()
    roles['role'] = role
    roles['training_candidate'] = candidate.to_numpy()
    roles['crosses_label_cutoff'] = crossing.to_numpy()
    roles['validation_id_in_training_window'] = held_id.to_numpy()
    if set(q.loc[train, 'id']) & set(ids):
        raise AssertionError('Whole-ID leakage')
    return roles, ids


def annual_counts(q):
    return q.groupby(COUNT, as_index=False).size().rename(columns={'size': 'pair_count'})


def conditional_counts(q):
    return q.groupby(SEASON_COUNT, as_index=False).size().rename(columns={'size': 'pair_count'})


def validation_weights(v):
    v = v.copy()
    v['times_per_id_origin'] = v.groupby(['horizon_days', 'origin_cell_1', 'id']).id.transform('size')
    v['ids_per_origin'] = v.groupby(['horizon_days', 'origin_cell_1']).id.transform('nunique')
    v['origins_per_horizon'] = v.groupby('horizon_days').origin_cell_1.transform('nunique')
    v['weight'] = 1. / (v.times_per_id_origin * v.ids_per_origin * v.origins_per_horizon)
    if not np.allclose(v.groupby('horizon_days').weight.sum(), 1., atol=1e-12, rtol=0):
        raise AssertionError('Invalid evaluation weights')
    return v


def allowed_inputs(paths, config):
    base = paths.root / 'results/runs' / config['source_run']
    prov = paths.root / 'provenance/runs' / config['source_run']
    audit = paths.root / config['support_audit']
    return [base/'release_counts_by_id.parquet', base/'source_ID_summary.csv',
            *sorted((base/'release_labels').glob('*.parquet')), prov/'outputs.json', prov/'run.json',
            audit, audit.parent/'artifact_sha256.json',
            *[paths.asset(a) for a in config['source_assets']]]


def load_inputs(paths, config):
    base = paths.root / 'results/runs' / config['source_run']
    prov = paths.root / 'provenance/runs' / config['source_run']
    receipt = json.loads((prov/'outputs.json').read_text())
    assert receipt['completed'] is True and receipt['final_test_access'] is False
    inventory = {}
    def verify(p, expected=None):
        rel = p.relative_to(paths.root).as_posix()
        digest = file_sha256(p)
        if expected is not None and digest != expected:
            raise ValueError('Checksum mismatch: ' + rel)
        inventory[rel] = digest
    def sealed(p):
        verify(p, receipt['output_sha256'][p.relative_to(paths.root).as_posix()])
        return read_frame(p)
    verify(prov/'outputs.json')
    verify(prov/'run.json', receipt['output_sha256'][(prov/'run.json').relative_to(paths.root).as_posix()])
    parent = json.loads((prov/'run.json').read_text())['config']
    for k in ['dataset_release', 'contract_sha256', 'target', 'scenario', 'tolerance_hours']:
        assert parent[k] == config[k], k
    assert parent['final_test_access'] is False
    manifest_path = paths.root/'configs/dataset_manifest.json'
    verify(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    assert manifest['version'] == config['dataset_release']
    assert manifest['contract_sha256'] == config['contract_sha256']
    dev = {int(k) for k,v in manifest['records'].items() if v['pool'] == 'train'}
    source = sealed(base/'source_ID_summary.csv')
    assert len(dev) == 3224 and set(source.id) == dev and not source.id.duplicated().any()
    for r in source.itertuples(index=False):
        record = manifest['records'][str(r.id)]
        assert r.source_sha256 == record['sha256'] and r.retained_rows == record['rows']
    for asset in config['source_assets']:
        p = paths.asset(asset, verify=True); verify(p)
    assert file_sha256(paths.asset('english_contract')) == config['contract_sha256']
    state = read_frame(paths.asset('state_index'))
    state = state.loc[state.resolution.eq(1)].sort_values('cell').reset_index(drop=True)
    origins = state.loc[state.R_intersection].cell.to_numpy(dtype='int64')
    states = np.r_[state.cell.to_numpy(dtype='int64'), -2]
    frames, rebuilt = [], []
    label_paths = sorted((base/'release_labels').glob('*.parquet'))
    assert {int(p.stem) for p in label_paths} == set(source.loc[source.R_origins.gt(0), 'id'])
    for p in label_paths:
        z = sealed(p)
        assert z.id.eq(int(p.stem)).all() and int(p.stem) in dev
        rebuilt.append(counts_from_labels(z))
        z = z.loc[z.reason_code.eq(0) & z.horizon_days.isin(config['horizons'])].copy()
        assert season_code(z.origin_time_UTC).eq(z.departure_season).all()
        epoch = (z.origin_time_UTC-pd.Timestamp('1970-01-01', tz='UTC')).dt.total_seconds()
        assert (epoch+z.horizon_days*86400).eq(z.target_epoch).all()
        assert np.isfinite(z.required_interval_end_epoch).all()
        need = np.where(z.outside, z.required_interval_end_epoch, z.target_epoch)
        assert np.array_equal(need, z.required_interval_end_epoch)
        assert z.required_interval_end_epoch.ge(epoch).all() and z.required_interval_end_epoch.le(z.target_epoch).all()
        frames.append(z)
    q = pd.concat(frames, ignore_index=True).sort_values(KEY).reset_index(drop=True)
    assert not q.duplicated(KEY).any() and q.origin_cell_1.isin(origins).all()
    assert q.destination_cell_1.isin(states).all()
    stored = sealed(base/'release_counts_by_id.parquet')
    stored = stored.loc[stored.horizon_days.isin(config['horizons'])].sort_values(COUNT).reset_index(drop=True)
    pd.testing.assert_frame_equal(stored, pd.concat(rebuilt).sort_values(COUNT).reset_index(drop=True), check_dtype=False, check_exact=True)
    assert q.groupby('horizon_days').size().to_dict() == {7:303288, 30:268998}
    assert q.groupby('horizon_days').id.nunique().to_dict() == {7:385, 30:337}
    assert q.groupby('horizon_days').origin_cell_1.nunique().to_dict() == {7:37, 30:37}
    assert q.drop_duplicates(['id','horizon_days','origin_cell_1']).groupby('horizon_days').size().to_dict() == {7:4451,30:3974}
    auditpath = paths.root/config['support_audit']
    verify(auditpath, config['support_audit_sha256'])
    manifest_audit = json.loads((auditpath.parent/'artifact_sha256.json').read_text())
    assert manifest_audit['audit.json'] == config['support_audit_sha256']
    verify(auditpath.parent/'artifact_sha256.json')
    roles, validation_ids = assign_roles(q, config)
    train = q.loc[roles.role.eq('train')].copy()
    validation = validation_weights(q.loc[roles.role.eq('validation')])
    audit = json.loads(auditpath.read_text())
    roster = []
    for h in config['horizons']:
        expected = audit['chronological'][f'recent_2012_train_{h}d']
        for name, data, label in [('train',train,'train_final'), ('validation',validation,'validation')]:
            g = data.loc[data.horizon_days.eq(h)]
            for value, field in [(len(g),'pairs'),(g.id.nunique(),'ids'),(g.origin_cell_1.nunique(),'origins'),(len(g[['id','origin_cell_1']].drop_duplicates()),'id_origin_units')]:
                assert value == expected[label][field], (h,name,field)
            roster.append({'horizon_days':h,'role':name,'pairs':len(g),'ids':g.id.nunique(),'origins':g.origin_cell_1.nunique()})
        rr = roles.loc[roles.horizon_days.eq(h)]
        assert rr.role.eq('excluded_label_cutoff').sum() == expected['label_boundary_purged_pairs']
        assert rr.role.eq('excluded_validation_id').sum() == expected['whole_id_purged_pairs']
    assert len(validation_ids) == 45
    seasonal = conditional_counts(train)
    annual = annual_counts(train)
    collapsed = seasonal.groupby(COUNT, as_index=False).pair_count.sum().sort_values(COUNT).reset_index(drop=True)
    pd.testing.assert_frame_equal(annual.sort_values(COUNT).reset_index(drop=True), collapsed, check_exact=True)
    return {'qualified':q,'roles':roles,'train':train,'validation':validation,
            'validation_ids':validation_ids,'annual_counts':annual,'seasonal_counts':seasonal,
            'states':states,'state_index':state,'origins':origins,'inventory':inventory,
            'roster':pd.DataFrame(roster)}
