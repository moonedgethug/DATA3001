"""Isolated G1 input allowlists, approval receipt and bounded resource checks."""
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import psutil
import shapely
from shapely.geometry import shape

from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import ReadOnlyInputs, save_json, save_frame
from data3001.modelling.baselines.b2_grid_translation import KEY, translated_cells

ROOT = Path(__file__).resolve().parents[4]
CONTRACT_SHA = 'c4c64782ed7ad7a33dc366fe6a971defb0b68c2b7b2f79534f58fd598a941fd7'
INPUT_HASHES = {
    'training_coordinates.parquet': '8638434fb651d10737a2827350d5ff98a3a76a5f3427778748c17a3ddb68715d',
    'query_coordinates.parquet': '0b480d728e008444c493a228ebecb2505da21185aa70d0f07e8513fd6107fea5',
    'roles.parquet': '78da3c85f77e29b303d7137320c33a94580f4822712faace9a7f0a03ffc7fdac',
}
TRAIN_COLUMNS = KEY + ['origin_time_UTC', 'target_epoch', 'required_interval_end_epoch',
    'origin_cell_1', 'lon', 'lat', 'endpoint_lon', 'endpoint_lat', 'endpoint_source_obs',
    'destination_cell_1', 'outside']
QUERY_COLUMNS = KEY + ['origin_cell_1', 'origin_time_UTC', 'lon', 'lat']


class Guard(ReadOnlyInputs):
    def __call__(self, event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.name == 'outer_targets.parquet':
                self.denied.append({'path': str(path), 'reason': 'Support/pilot stage: outcomes sealed'})
                raise PermissionError('G1 outer outcomes are sealed until full forecast freeze')
        return super().__call__(event, args)


class Budget:
    def __init__(self, run, cfg, stage, prior_seconds=0., started=None):
        self.run, self.cfg, self.stage = run, cfg, stage
        self.start = time.monotonic() if started is None else started
        self.prior_seconds = prior_seconds
        self.peak_rss = 0
        self.peak_storage = 0
        self.process = psutil.Process()

    def snapshot(self):
        processes = [self.process] + self.process.children(recursive=True)
        rss = sum(p.memory_info().rss for p in processes if p.is_running())
        size = sum(p.stat().st_size for folder in self.run.values()
                   for p in folder.rglob('*') if p.is_file() and not p.is_symlink())
        self.peak_rss = max(rss, self.peak_rss)
        self.peak_storage = max(size, self.peak_storage)
        return dict(stage=self.stage, elapsed_seconds=time.monotonic()-self.start,
            prior_stage_seconds=self.prior_seconds, peak_process_tree_rss_bytes=self.peak_rss,
            peak_new_storage_bytes=self.peak_storage, current_storage_bytes=size)

    def check(self):
        info = self.snapshot()
        if info['elapsed_seconds']+self.prior_seconds > self.cfg['seconds'][self.stage]:
            raise RuntimeError('Contract phase time budget reached')
        if info['peak_process_tree_rss_bytes'] > self.cfg['rss_gib']*2**30:
            raise RuntimeError('Contract aggregate memory budget reached')
        if info['peak_new_storage_bytes'] > self.cfg['storage_gib']*2**30:
            raise RuntimeError('Contract incremental storage budget reached')
        return info


def prepare():
    paths = project_paths()
    cfg = json.loads((ROOT/'configs/b2_grid_translation.json').read_text())
    assert cfg['contract_sha256'] == CONTRACT_SHA
    assert file_sha256(ROOT/cfg['contract']) == CONTRACT_SHA
    tests = json.loads((ROOT/'provenance/reviews/b2_grid_translation_tests.json').read_text())
    assert tests['exit_code'] == 0
    run = paths.create_run('b2_grid_translation_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'), cfg)
    guard = Guard(ROOT, run); sys.addaudithook(guard)
    protected = {}
    for folder, pattern in [('docs', '*.md'), ('src', '*.py'), ('tests', '*.py'), ('configs', '*.json')]:
        for p in (ROOT/folder).rglob(pattern):
            if 'b2_grid_translation' not in p.name:
                protected[str(p.relative_to(ROOT))] = file_sha256(p)
    protected[cfg['contract']] = CONTRACT_SHA
    save_json(paths, run['provenance']/'approval.json', {
        'user_authorization': 'User confirmed G1 contract: independent development, bounded pilot, formal experiment only if gates pass, independent verification and visualization. Stop/report support or budget problems; no model/definition changes.',
        'contract_sha256': CONTRACT_SHA, 'approved_config': cfg,
        'protected_existing_sha256': protected, 'final_test_access': False,
        'outer_outcomes_sealed': True})
    paths.publish(run['provenance']/'approved_contract.md', lambda f: f.write((ROOT/cfg['contract']).read_bytes()))
    save_json(paths, run['provenance']/'synthetic_tests.json', tests)
    sources = list((ROOT/'src/data3001/modelling/baselines').glob('b2_grid_translation*.py'))
    sources += [ROOT/'tests/test_modelling_b2_grid_translation.py', ROOT/'configs/b2_grid_translation.json']
    hashes = {}
    for p in sources:
        hashes[str(p.relative_to(ROOT))] = file_sha256(p)
        paths.publish(run['provenance']/'sources'/p.name, lambda f, p=p: f.write(p.read_bytes()))
    save_json(paths, run['provenance']/'source_hashes.json', hashes)
    return paths, run, cfg, guard, tests['elapsed_seconds']


def read_frame(path, columns):
    with path.open('rb') as stream:
        return pd.read_parquet(stream, columns=columns)


def load_inputs(paths, run, cfg):
    base = ROOT/'results/runs'/cfg['source_run']
    for name, digest in INPUT_HASHES.items():
        assert file_sha256(base/name) == digest, name
    for asset in ['release_R', 'transport_D', 'land_mask_high', 'state_index']:
        paths.asset(asset, verify=True)
    assert file_sha256(ROOT/'docs/contract/data_contract_v1.0.xlsx') == '6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446'
    assert file_sha256(ROOT/'configs/dataset_manifest.json') == 'c71a7ac3d0230b7489bcfc417d4caceb26ffc1230644a11300a642d7812e041e'
    train = read_frame(base/'training_coordinates.parquet', TRAIN_COLUMNS).sort_values(KEY).reset_index(drop=True)
    query = read_frame(base/'query_coordinates.parquet', QUERY_COLUMNS).sort_values(KEY).reset_index(drop=True)
    roles = read_frame(base/'roles.parquet', KEY+['role_name', 'role'])
    assert (len(train), train.id.nunique(), len(query), query.id.nunique()) == (265393, 338, 33971, 45)
    assert not train.duplicated(KEY).any() and not query.duplicated(KEY).any()
    assert not set(train.id)&set(query.id)
    for part in [train, query]:
        assert part.horizon_days.eq(7).all()
        np.testing.assert_array_equal(translated_cells(part.lon, part.lat), part.origin_cell_1)
    ts = pd.to_datetime(train.origin_time_UTC, utc=True)
    qs = pd.to_datetime(query.origin_time_UTC, utc=True)
    assert ts.dt.year.between(2001,2019).all() and qs.dt.year.between(2020,2022).all()
    assert np.all(train.required_interval_end_epoch < pd.Timestamp('2020-01-01',tz='UTC').timestamp())
    np.testing.assert_array_equal(train.target_epoch.to_numpy()-ts.dt.as_unit('s').astype(np.int64).to_numpy(), np.full(len(train),604800))
    outer = roles[roles.role_name.eq('C_outer') & roles.horizon_days.eq(7)]
    for name, frame in [('train',train),('validation',query)]:
        keys=outer.loc[outer.role.eq(name),KEY].sort_values(KEY).reset_index(drop=True)
        pd.testing.assert_frame_equal(keys,frame[KEY],check_dtype=False)
    release = shape(json.loads(paths.asset('release_R').read_text())['features'][0]['geometry'])
    domain = shape(json.loads(paths.asset('transport_D').read_text())['features'][0]['geometry'])
    for part in [train,query]:
        assert shapely.intersects_xy(release,part.lon,part.lat).all()
        assert shapely.intersects_xy(domain,part.lon,part.lat).all()
    inside = ~train.outside.to_numpy(dtype=bool)
    assert shapely.intersects_xy(domain,train.loc[inside,'endpoint_lon'],train.loc[inside,'endpoint_lat']).all()
    np.testing.assert_array_equal(translated_cells(train.loc[inside,'endpoint_lon'],train.loc[inside,'endpoint_lat']),train.loc[inside,'destination_cell_1'])
    save_json(paths,run['provenance']/'input_checks.json', dict(
        train_pairs=len(train),train_ids=int(train.id.nunique()),query_pairs=len(query),query_ids=int(query.id.nunique()),
        training_exits=int(train.outside.sum()),source_hashes=INPUT_HASHES,
        roles_reproduced=True,id_overlap=0,cutoff_purge_verified=True,horizon_seconds=604800,
        source_coordinate_states_verified=True,outer_targets_read=False,final_test_read=False))
    return train,query,roles

