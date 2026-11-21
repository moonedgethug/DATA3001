"""Immutable E7 coordinates and opt-in verified errors for E8 only."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import ReadOnlyInputs, save_json
from data3001.modelling.baselines.position_error_s4_e8 import equivalent_sd

ROOT = Path(__file__).resolve().parents[4]
KEY = ['id', 'origin_source_obs', 'horizon_days']
E7_INPUTS = ['training_coordinates.parquet', 'query_coordinates.parquet', 'roles.parquet',
             'C_T0_eligibility.parquet', 'C_T1_eligibility.parquet', 'choices.csv',
             'inner_cases.parquet', 'outer_roster.parquet', 'example_selection.json']


def read_frame(path, **kwargs):
    with Path(path).open('rb') as stream:
        return pd.read_parquet(stream, **kwargs)


def config():
    return json.loads((ROOT/'configs/position_error_s4_e8.json').read_text())


def prepare():
    paths = project_paths(); cfg = config()
    assert paths.root == ROOT
    assert file_sha256(ROOT/cfg['contract']) == cfg['contract_sha256']
    repair = ROOT/'provenance/migrations'/cfg['repair_run']
    assert file_sha256(repair/'manifest.json') == cfg['repair_manifest_sha256']
    assert file_sha256(repair/'full/error_overlay.parquet') == cfg['overlay_sha256']
    old = json.loads((repair/'approval.json').read_text())
    protected = dict(old['protected_files'])
    # The user explicitly approved replacing E8 v1 by v2 after data repair.
    protected[cfg['contract']] = cfg['contract_sha256']
    for name, digest in protected.items(): assert file_sha256(ROOT/name) == digest, name
    e7 = ROOT/'results/runs'/cfg['e7_run']
    receipt = json.loads((ROOT/'provenance/runs'/cfg['e7_run']/'outputs.json').read_text())
    assert receipt['completed'] and receipt['final_test_access'] is False
    for name in E7_INPUTS:
        path = e7/name; rel = str(path.relative_to(ROOT))
        assert file_sha256(path) == receipt['output_sha256'][rel], name
        protected[rel] = file_sha256(path)
    for asset in ['release_R', 'transport_D', 'land_mask_high']:
        path = paths.asset(asset, verify=True); protected[str(path.relative_to(ROOT))] = file_sha256(path)
    protected[str((repair/'manifest.json').relative_to(ROOT))] = cfg['repair_manifest_sha256']
    protected[str((repair/'full/error_overlay.parquet').relative_to(ROOT))] = cfg['overlay_sha256']
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run = paths.create_run('position_error_s4_e8_'+stamp, cfg)
    paths.publish(run['provenance']/'approved_contract.md', lambda f:f.write((ROOT/cfg['contract']).read_bytes()))
    target = str((e7/'outer_targets.parquet').relative_to(ROOT))
    save_json(paths, run['provenance']/'approval.json', {
        'user_authorization':'Develop E8 v2 independently; run the pilot; proceed only after resource and precision gates; complete full comparison and independent audit within budget; provide visual comparisons.',
        'contract_sha256':cfg['contract_sha256'], 'protected_files':protected,
        'deferred_target_path':target, 'deferred_target_sha256':receipt['output_sha256'][target],
        'no_final_test':True, 'no_outer_endpoint_errors':True})
    print(run['results'].name, flush=True)


def context(run_id, guarded=True):
    if Path(run_id).name != run_id or not run_id.startswith('position_error_s4_e8_'):
        raise ValueError('Invalid E8 run')
    paths = project_paths(); run = {'results':ROOT/'results/runs'/run_id, 'provenance':ROOT/'provenance/runs'/run_id}
    cfg = json.loads((run['provenance']/'run.json').read_text())['config']
    approval = json.loads((run['provenance']/'approval.json').read_text())
    if guarded:
        guard = ReadOnlyInputs(ROOT, run)
        sys.addaudithook(guard)
    else: guard = None
    for name,digest in approval['protected_files'].items(): assert file_sha256(ROOT/name)==digest,name
    return paths,run,cfg,approval,guard


def load_training(cfg):
    e7 = ROOT/'results/runs'/cfg['e7_run']; repair = ROOT/'provenance/migrations'/cfg['repair_run']
    train = read_frame(e7/'training_coordinates.parquet')
    overlay = read_frame(repair/'full/error_overlay.parquet', columns=['id','source_obs','time','lon','lat',
              'repaired_err_lon','repaired_err_lat','ci_2d_usable','status_lon','status_lat','location_type','base_version'])
    overlay = overlay.rename(columns={'source_obs':'endpoint_source_obs','lon':'verified_lon','lat':'verified_lat',
                                      'time':'verified_epoch','status_lon':'error_status_lon','status_lat':'error_status_lat'})
    train = train.merge(overlay, on=['id','endpoint_source_obs'], how='left', validate='many_to_one', indicator=True)
    assert train._merge.eq('both').all() and len(train)==265393 and train.id.nunique()==338
    assert train.base_version.eq('per-drifter-cleaned-20261017-v7').all()
    assert np.array_equal(train.target_epoch,train.verified_epoch)
    assert np.array_equal(train.endpoint_lon,train.verified_lon) and np.array_equal(train.endpoint_lat,train.verified_lat)
    assert not train.outside.any() and train.horizon_days.eq(7).all()
    train = train.drop(columns='_merge').sort_values(KEY).reset_index(drop=True)
    sd = equivalent_sd(train[['endpoint_lon','endpoint_lat']].to_numpy(),
                       train[['repaired_err_lon','repaired_err_lat']].to_numpy(),train.ci_2d_usable.to_numpy())
    train['sd_e_km'],train['sd_n_km'] = sd.T
    assert train.ci_2d_usable.sum()==249577
    return train,read_frame(e7/'roles.parquet')


def load_role(cfg, name, train=None, ledger=None):
    if train is None:train,ledger=load_training(cfg)
    if name=='C_outer':
        fit=train
        query=read_frame(ROOT/'results/runs'/cfg['e7_run']/'query_coordinates.parquet')
        target=None
    else:
        role=ledger[ledger.role_name.eq(name)&ledger.horizon_days.eq(7)]
        fit=role[role.role.eq('train')][KEY].merge(train,on=KEY,validate='one_to_one').sort_values(KEY).reset_index(drop=True)
        target=role[role.role.eq('validation')][KEY].merge(train,on=KEY,validate='one_to_one').sort_values(KEY).reset_index(drop=True)
        query=target[KEY+['origin_cell_1','origin_time_UTC','lon','lat']].copy()
    expected={'C_T0':(170978,41761),'C_T1':(209934,44612),'C_outer':(265393,33971)}
    assert (len(fit),len(query))==expected[name]
    assert not set(fit.id)&set(query.id)
    assert not fit.duplicated(KEY).any() and not query.duplicated(KEY).any()
    return fit,query,target


def release_outer_targets(run,cfg,approval):
    freeze=run['provenance']/'forecast_freeze.json'
    if not freeze.exists():raise PermissionError('Outer outcomes remain sealed until all forecasts freeze')
    receipt=json.loads(freeze.read_text());assert receipt['cases']==33971
    for name,digest in receipt['output_sha256'].items():assert file_sha256(ROOT/name)==digest
    path=ROOT/approval['deferred_target_path']
    assert file_sha256(path)==approval['deferred_target_sha256']
    # Explicit column allowlist excludes error fields even if an upstream schema changes.
    return read_frame(path,columns=KEY+['endpoint_lon','endpoint_lat','outside','origin_time_UTC'])
