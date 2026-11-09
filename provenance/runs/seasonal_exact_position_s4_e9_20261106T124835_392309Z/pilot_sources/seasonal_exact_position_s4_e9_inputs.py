"""Pinned E9 inputs, authorization, access guards and resource accounting."""
import json
import os
from pathlib import Path
import resource
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import ReadOnlyInputs, save_json, save_frame
from data3001.modelling.baselines import position_error_s4_e8_inputs as old

ROOT = Path(__file__).resolve().parents[4]
KEY = old.KEY


def read(path, **kwargs):
    return old.read_frame(path, **kwargs)


class Guard(ReadOnlyInputs):
    def __init__(self, root, run):
        super().__init__(root, run)
        self.outcomes_allowed = False
        self.outcomes_read = False

    def __call__(self, event, args):
        super().__call__(event, args)
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        p = Path(os.fsdecode(args[0])).resolve()
        if p.name == 'outer_targets.parquet':
            if not self.outcomes_allowed:
                self.denied.append({'path': str(p), 'reason': 'forecast freeze required'})
                raise PermissionError('Outer endpoints sealed until forecast freeze')
            self.outcomes_read = True


def config():
    return json.loads((ROOT / 'configs/seasonal_exact_position_s4_e9.json').read_text())


def prepare():
    started = time.monotonic()
    paths = project_paths(); cfg = config()
    assert file_sha256(ROOT / cfg['contract']) == cfg['contract_sha256']
    review = json.loads((ROOT / 'provenance/reviews/seasonal_exact_position_s4_e9_contract_v1_review.json').read_text())
    protected = review['protected_existing_sha256']
    protected[cfg['contract']] = cfg['contract_sha256']
    protected['configs/seasonal_exact_position_s4_e9.json'] = file_sha256(ROOT / 'configs/seasonal_exact_position_s4_e9.json')
    for name, digest in protected.items():
        assert file_sha256(ROOT / name) == digest, name
    e7_receipt = json.loads((ROOT / 'provenance/runs' / cfg['e7_run'] / 'outputs.json').read_text())
    for name in old.E7_INPUTS:
        p = ROOT / 'results/runs' / cfg['e7_run'] / name
        rel = str(p.relative_to(ROOT))
        assert file_sha256(p) == e7_receipt['output_sha256'][rel], name
        protected[rel] = file_sha256(p)
    pilot = ROOT / 'results/runs' / cfg['e8_run'] / 'pilot_attempt_4/roster.parquet'
    protected[str(pilot.relative_to(ROOT))] = file_sha256(pilot)
    for asset in ['release_R', 'transport_D', 'land_mask_high']:
        p = paths.asset(asset, verify=True)
        protected[str(p.relative_to(ROOT))] = file_sha256(p)
    run = paths.create_run('seasonal_exact_position_s4_e9_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'), cfg)
    paths.publish(run['provenance'] / 'approved_contract.md', lambda f: f.write((ROOT / cfg['contract']).read_bytes()))
    target = str(Path('results/runs') / cfg['e7_run'] / 'outer_targets.parquet')
    save_json(paths, run['provenance'] / 'approval.json', dict(
        user_authorization='User approved E9 including majority season and departure-season tie: develop, run pilot, proceed within budget only after passing, independently verify and visualize. No unapproved model/weight/definition changes; report problems first.',
        contract_sha256=cfg['contract_sha256'], protected_files=protected,
        deferred_target_path=target, deferred_target_sha256=e7_receipt['output_sha256'][target],
        final_test_access=False, outer_endpoint_error_access=False))
    save_json(paths, run['provenance'] / 'prepare_resources.json', dict(
        phase='pilot', completed=True, elapsed_seconds=time.monotonic() - started,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    print(run['results'].name, flush=True)


def context(name):
    if Path(name).name != name or not name.startswith('seasonal_exact_position_s4_e9_'):
        raise ValueError('Invalid E9 run identity')
    paths = project_paths()
    run = dict(results=ROOT / 'results/runs' / name, provenance=ROOT / 'provenance/runs' / name)
    cfg = json.loads((run['provenance'] / 'run.json').read_text())['config']
    approval = json.loads((run['provenance'] / 'approval.json').read_text())
    guard = Guard(ROOT, run); sys.addaudithook(guard)
    verify(approval)
    return paths, run, cfg, approval, guard


def verify(approval):
    for name, digest in approval['protected_files'].items():
        assert file_sha256(ROOT / name) == digest, name


def snapshot(paths, run, stage):
    folder = run['provenance'] / (stage + '_sources'); folder.mkdir()
    files = list((ROOT / 'src/data3001/modelling/baselines').glob('*seasonal_exact_position_s4_e9*.py'))
    files += list((ROOT / 'tests').glob('*seasonal_exact_position_s4_e9*.py'))
    files += [ROOT / 'configs/seasonal_exact_position_s4_e9.json']
    hashes = {}
    for p in files:
        hashes[str(p.relative_to(ROOT))] = file_sha256(p)
        paths.publish(folder / p.name, lambda f, p=p: f.write(p.read_bytes()))
    save_json(paths, folder / 'hashes.json', hashes)
    return hashes


def load(cfg):
    train, ledger = old.load_training(cfg)
    return train, ledger


def role(cfg, name, train, ledger):
    return old.load_role(cfg, name, train, ledger)


def release_targets(paths, run, cfg, approval, guard):
    frozen = json.loads((run['provenance'] / 'forecast_freeze.json').read_text())
    assert frozen['cases'] == 33971
    for name, digest in frozen['output_sha256'].items():
        assert file_sha256(ROOT / name) == digest, name
    guard.outcomes_allowed = True
    path = ROOT / approval['deferred_target_path']
    assert file_sha256(path) == approval['deferred_target_sha256']
    return read(path, columns=KEY + ['endpoint_lon', 'endpoint_lat', 'outside', 'origin_time_UTC']).sort_values(KEY).reset_index(drop=True)


class Budget:
    def __init__(self, run, cfg, phase):
        self.run, self.cfg, self.phase = run, cfg, phase
        self.start = time.monotonic()
        old_receipts = [json.loads(p.read_text()) for p in run['provenance'].glob('*_resources.json')]
        self.prior_phase = sum(r['elapsed_seconds'] for r in old_receipts if r['phase'] == phase)
        self.prior_total = sum(r['elapsed_seconds'] for r in old_receipts)
        self.last_bytes = 0

    def stats(self, storage=False):
        if storage:
            self.last_bytes = sum(p.stat().st_size for folder in self.run.values()
                                  for p in folder.rglob('*') if p.is_file() and not p.is_symlink())
        return dict(phase=self.phase, elapsed_seconds=time.monotonic() - self.start,
                    peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    retained_bytes=self.last_bytes)

    def check(self, storage=False):
        r = self.stats(storage)
        if self.prior_phase + r['elapsed_seconds'] > self.cfg['seconds'][self.phase]:
            raise TimeoutError('Cumulative ' + self.phase + ' cap reached')
        if self.prior_total + r['elapsed_seconds'] > self.cfg['seconds']['total']:
            raise TimeoutError('Total execution cap reached')
        if r['peak_rss_bytes'] > self.cfg['rss_gib'] * 2**30:
            raise MemoryError('Memory cap reached')
        if r['retained_bytes'] > self.cfg['storage_gib'] * 2**30:
            raise OSError('Storage cap reached')
        return r

    def finish(self, paths, label, completed, guard=None):
        r = self.stats(storage=True)
        r.update(completed=completed, final_test_access=False, outer_endpoint_errors_read=False)
        if guard is not None:
            r.update(outer_targets_read=guard.outcomes_read, denied_access=guard.denied)
        save_json(paths, self.run['provenance'] / (label + '_resources.json'), r)
