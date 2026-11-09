"""Isolated S5 input access, immutable sources and cumulative execution caps."""
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

import numpy as np
import pandas as pd
import psutil

from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import ReadOnlyInputs, save_json
from data3001.modelling.baselines import position_error_s4_e8_inputs as old

ROOT = Path(__file__).resolve().parents[4]
KEY = old.KEY
HASHES = {
    'training_coordinates.parquet': '8638434fb651d10737a2827350d5ff98a3a76a5f3427778748c17a3ddb68715d',
    'query_coordinates.parquet': '0b480d728e008444c493a228ebecb2505da21185aa70d0f07e8513fd6107fea5',
    'roles.parquet': '78da3c85f77e29b303d7137320c33a94580f4822712faace9a7f0a03ffc7fdac'}


class Guard(ReadOnlyInputs):
    def __init__(self, root, run):
        super().__init__(root, run)
        self.outcomes_allowed = False
        self.outcomes_read = False

    def __call__(self, event, args):
        super().__call__(event, args)
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.name == 'outer_targets.parquet':
                if not self.outcomes_allowed:
                    self.denied.append({'path': str(path), 'reason': 'Full forecast freeze required'})
                    raise PermissionError('Outer outcomes remain sealed')
                self.outcomes_read = True


def context(name):
    if Path(name).name != name or not name.startswith('conditional_gaussian_s5_e1_'):
        raise ValueError('Invalid S5 run identity')
    paths = project_paths()
    run = {part: ROOT/(part+'/runs')/name for part in ('results', 'provenance')}
    cfg = json.loads((run['provenance']/'run.json').read_text())['config']
    approval = json.loads((run['provenance']/'approval.json').read_text())
    guard = Guard(ROOT, run)
    sys.addaudithook(guard)
    verify(approval)
    return paths, run, cfg, approval, guard


def verify(approval):
    for relative, digest in approval['protected_files'].items():
        if file_sha256(ROOT/relative) != digest: raise ValueError('Protected file changed: '+relative)


def freeze_sources(paths, run, label):
    files = list((ROOT/'src/data3001/modelling/continuous_models').glob('conditional_gaussian_s5_e1*.py'))
    files += list((ROOT/'tests').glob('test_modelling_conditional_gaussian_s5_e1*.py'))
    files += [ROOT/'configs/conditional_gaussian_s5_e1.json']
    hashes = {}
    for path in files:
        hashes[str(path.relative_to(ROOT))] = file_sha256(path)
        paths.publish(run['provenance']/(label+'_sources')/path.name, lambda f, path=path: f.write(path.read_bytes()))
    save_json(paths, run['provenance']/(label+'_sources')/'hashes.json', hashes)
    return hashes


def load(cfg):
    base = ROOT/'results/runs'/cfg['e7_run']
    for name, digest in HASHES.items():
        if file_sha256(base/name) != digest: raise ValueError('Input identity mismatch: '+name)
    repair = ROOT/'provenance/migrations'/cfg['repair_run']
    assert file_sha256(repair/'manifest.json') == cfg['repair_manifest_sha256']
    assert file_sha256(repair/'full/error_overlay.parquet') == cfg['overlay_sha256']
    train, roles = old.load_training(cfg)
    query = old.read_frame(base/'query_coordinates.parquet', columns=KEY+['origin_cell_1','origin_time_UTC','lon','lat'])
    query = query.sort_values(KEY).reset_index(drop=True)
    assert len(query) == 33971 and query.id.nunique() == 45
    assert not set(query.id)&set(train.id)
    assert pd.to_datetime(query.origin_time_UTC, utc=True).dt.year.between(2020, 2022).all()
    assert pd.to_datetime(train.origin_time_UTC, utc=True).dt.year.between(2001, 2019).all()
    assert (train.required_interval_end_epoch < pd.Timestamp('2020-01-01', tz='UTC').timestamp()).all()
    expected = {'C_T0': (170978, 234, 41761, 50, '2014-01-01'),
                'C_T1': (209934, 280, 44612, 58, '2017-01-01')}
    out = {}
    for role, (nf, ni, nq, qi, end) in expected.items():
        fit, queries, targets = old.load_role(cfg, role, train, roles)
        assert (len(fit), fit.id.nunique(), len(queries), queries.id.nunique()) == (nf, ni, nq, qi)
        assert (fit.required_interval_end_epoch < pd.Timestamp(end, tz='UTC').timestamp()).all()
        assert (fit.target_epoch - pd.to_datetime(fit.origin_time_UTC, utc=True).dt.as_unit('s').astype(np.int64)).eq(604800).all()
        out[role] = dict(fit=fit, query=queries, target=targets)
    return out, train, query


class Budget:
    def __init__(self, run, cfg, phase, started=None):
        self.run, self.cfg, self.phase = run, cfg, phase
        self.started = time.monotonic() if started is None else started
        receipts = [json.loads(p.read_text()) for p in run['provenance'].glob('*_resources.json')]
        self.prior_phase = sum(r['elapsed_seconds'] for r in receipts if r['phase'] == phase)
        self.prior_total = sum(r['elapsed_seconds'] for r in receipts)
        remaining = min(cfg['seconds'][phase]-self.prior_phase, cfg['seconds']['total']-self.prior_total)
        self.deadline = self.started+remaining
        self.peak_rss = 0
        self.peak_storage = 0
        self.process = psutil.Process()
        signal.signal(signal.SIGALRM, self.timeout)
        signal.setitimer(signal.ITIMER_REAL, max(.01, self.deadline-time.monotonic()-.5))

    def timeout(self, *_): raise TimeoutError('Approved cumulative execution cap reached')

    def stats(self):
        rss = self.process.memory_info().rss + sum(p.memory_info().rss for p in self.process.children(recursive=True) if p.is_running())
        self.peak_rss = max(self.peak_rss, rss, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        size = sum(p.stat().st_size for folder in self.run.values() for p in folder.rglob('*') if p.is_file() and not p.is_symlink())
        self.peak_storage = max(size, self.peak_storage)
        return dict(phase=self.phase, elapsed_seconds=time.monotonic()-self.started,
                    prior_phase_seconds=self.prior_phase, prior_total_seconds=self.prior_total,
                    peak_process_tree_rss_bytes=self.peak_rss, retained_bytes=size, peak_storage_bytes=self.peak_storage)

    def check(self):
        result = self.stats()
        if time.monotonic() >= self.deadline-.5: self.timeout()
        if self.peak_rss > self.cfg['rss_gib']*2**30: raise MemoryError('Aggregate memory cap reached')
        if self.peak_storage > self.cfg['storage_gib']*2**30: raise OSError('Incremental storage cap reached')
        return result

    def finish(self, paths, label, completed, guard):
        signal.setitimer(signal.ITIMER_REAL, 0)
        receipt = self.stats()
        receipt.update(completed=completed, outer_targets_read=guard.outcomes_read,
                       denied_access=guard.denied, final_test_access=False)
        save_json(paths, self.run['provenance']/(label+'_resources.json'), receipt)
        return receipt
