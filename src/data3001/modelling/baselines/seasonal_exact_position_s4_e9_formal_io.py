"""Isolated formal-run I/O. Scientific E9 implementations remain read-only."""
import time
BOOT = time.monotonic()
import hashlib
import json
import resource
import signal
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import save_json, save_frame
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_inputs as inputs

ROOT = inputs.ROOT
KEY = inputs.KEY
PILOT = 'e9_esopt_20261106T133844_947508Z'
ORIGINAL = 'seasonal_exact_position_s4_e9_20261106T124835_392309Z'
MODELS = ['AnnualExactPoint', 'AnnualEndpointCI', 'SeasonalExactPoint', 'SeasonalEndpointCI']
EXAMPLES = [26952, 6475, 24032, 23714, 11213, 28115]
AUDIT = np.floor(np.arange(128)*(33971-1)/127).astype(int)
CODEC = pa.Codec('zstd', compression_level=3)


def encode_selection(annual, seasonal, fallback):
    """Lossless sorted-index / integer-bit delta coding; no distance rounding."""
    chunks = []
    selections = [annual] if fallback else [annual, seasonal]
    for indices, distances in selections:
        order = np.argsort(indices)
        ix = np.asarray(indices, dtype='<i8')[order]
        if len(np.unique(ix)) != len(ix): raise ValueError('Duplicate source indices')
        delta = np.diff(ix, prepend=0).astype('<u4')
        chunks.append(delta.view('u1').reshape(-1, 4).T.copy().tobytes())
        bits = np.asarray(distances, dtype='<f8')[order].view('<i8')
        delta = np.diff(np.diff(bits, prepend=0), prepend=0)
        zigzag = ((delta << 1) ^ (delta >> 63)).astype('<u8')
        chunks.append(zigzag.view('u1').reshape(-1, 8).T.copy().tobytes())
    raw = b''.join(chunks)
    return struct.pack('<IIB', len(annual[0]), 0 if fallback else len(seasonal[0]), fallback) + bytes(CODEC.compress(raw))


def decode_selection(blob):
    n, m, fallback = struct.unpack('<IIB', blob[:9])
    raw = memoryview(CODEC.decompress(blob[9:], (n+m)*12))
    position = 0; out = []
    for count in ([n] if fallback else [n, m]):
        delta = np.frombuffer(raw[position:position+4*count], 'u1').reshape(4, count).T.copy().ravel().view('<u4')
        position += 4*count
        indices = np.cumsum(delta, dtype=np.int64)
        zigzag = np.frombuffer(raw[position:position+8*count], 'u1').reshape(8, count).T.copy().ravel().view('<u8')
        position += 8*count
        delta = (zigzag >> 1).astype('int64') ^ -(zigzag & 1).astype('int64')
        bits = np.cumsum(np.cumsum(delta, dtype=np.int64), dtype=np.int64)
        distances = bits.view('<f8')
        order = np.lexsort((indices, distances))
        out.append((indices[order], distances[order]))
    if fallback: out.append(out[0])
    return out[0], out[1], bool(fallback)


def selections(run):
    offsets = inputs.read(run['results']/'lineage_offsets.parquet')
    with (run['results']/'donor_lineage.zst').open('rb') as stream:
        for r in offsets.itertuples(index=False):
            assert stream.tell() == r.offset
            yield decode_selection(stream.read(r.length))


def key(row, pool, rep=None):
    k = ('s4_e9', 'C_outer', int(row.id), int(row.origin_source_obs), 7, pool)
    return k if rep is None else (*k, rep)


def hashes(files):
    return {str(p.relative_to(ROOT)): file_sha256(p) for p in files}


def verify(mapping):
    for relative, expected in mapping.items():
        assert file_sha256(ROOT/relative) == expected, relative


def prepare():
    paths = project_paths()
    p = ROOT/'provenance/runs'/PILOT
    old = json.loads((p/'approval.json').read_text())
    protected = {**old['protected_files'], **old['new_source_sha256']}
    verify(protected)
    first = json.loads((ROOT/'provenance/runs'/ORIGINAL/'approval.json').read_text())
    gate = json.loads((p/'pilot_gate.json').read_text())
    review = json.loads((p/'independent_review.json').read_text())
    assert review['independent_review_passed']
    assert gate['levels'][-1]['energy_count'] == 16384
    cfg = json.loads((p/'run.json').read_text())['config']
    prior = []
    for parent in [ORIGINAL, PILOT]:
        for receipt in (ROOT/'provenance/runs'/parent).glob('*_resources.json'):
            r = json.loads(receipt.read_text())
            prior.append(dict(path=str(receipt.relative_to(ROOT)), seconds=r['elapsed_seconds'],
                              phase=r.get('phase', 'pilot' if r.get('stage') in ['preflight','pilot'] else 'audit')))
    cfg = dict(cfg, formal_parent_pilot=PILOT, energy_count=16384,
               prior_execution_seconds=sum(r['seconds'] for r in prior),
               prior_audit_seconds=sum(r['seconds'] for r in prior if r['phase']=='audit'),
               prior_pilot_seconds=sum(r['seconds'] for r in prior if r['phase']=='pilot'))
    name = 'e9_formal_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run = paths.create_run(name, cfg)
    sources = list((ROOT/'src/data3001/modelling/baselines').glob('seasonal_exact_position_s4_e9_formal*.py'))
    sources += list((ROOT/'tests').glob('test_modelling_seasonal_exact_position_s4_e9_formal.py'))
    source_hashes = hashes(sources)
    save_json(paths, run['provenance']/'approval.json', dict(
        authorization='User explicitly authorized the complete four-model E9 experiment to retain research evidence, accepting the measured runtime. The 2x formal-time precheck is waived; actual phase, total, RAM and storage caps remain. No scientific changes or automatic follow-up experiments.',
        runtime_precheck_2x_waived=True, protected_files=protected, new_source_sha256=source_hashes,
        deferred_target_path=first['deferred_target_path'], deferred_target_sha256=first['deferred_target_sha256'],
        prior_receipts=prior, final_test_access=False, outer_endpoint_error_access=False))
    for source in sources:
        paths.publish(run['provenance']/'sources'/source.name, lambda f, source=source:f.write(source.read_bytes()))
    save_json(paths, run['provenance']/'parent_evidence.json', dict(
        hashes=hashes([p/'pilot_gate.json',p/'independent_review.json',p/'delivery.json']),
        selected_energy_count=16384, original_contract_sha256=cfg['contract_sha256']))
    print(name, flush=True)


class Budget:
    def __init__(self, paths, run, cfg, phase, guard):
        self.paths,self.run,self.cfg,self.phase,self.guard = paths,run,cfg,phase,guard
        self.start = BOOT
        old = [json.loads(p.read_text()) for p in run['provenance'].glob('*_resources.json')]
        self.prior_total = cfg['prior_execution_seconds'] + sum(r['elapsed_seconds'] for r in old)
        prior_phase = sum(r['elapsed_seconds'] for r in old if r['phase']==phase)
        if phase=='audit': prior_phase += cfg['prior_audit_seconds']
        if phase=='pilot': prior_phase += cfg['prior_pilot_seconds']
        remaining = min(cfg['seconds'][phase]-prior_phase, cfg['seconds']['total']-self.prior_total)
        self.deadline = self.start + remaining
        signal.signal(signal.SIGALRM, self.timeout)
        signal.setitimer(signal.ITIMER_REAL, max(.1,self.deadline-time.monotonic()-.5))

    def timeout(self, *_): raise TimeoutError('Approved actual execution cap reached')

    def size(self):
        return sum(p.stat().st_size for f in self.run.values() for p in f.rglob('*') if p.is_file())

    def check(self, storage=False):
        if time.monotonic() >= self.deadline-.5: self.timeout()
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 8*2**30: raise MemoryError('8 GiB cap')
        if storage and self.size() > 5*2**30: raise OSError('5 GiB cap')

    def finish(self, label, completed):
        signal.setitimer(signal.ITIMER_REAL, 0)
        elapsed = time.monotonic()-self.start
        save_json(self.paths,self.run['provenance']/f'{label}_resources.json',dict(
            phase=self.phase,elapsed_seconds=elapsed,total_execution_seconds=self.prior_total+elapsed,
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,retained_bytes=self.size(),
            completed=completed,outer_targets_read=self.guard.outcomes_read,denied_access=self.guard.denied,
            final_test_access=False,outer_endpoint_errors_read=False))


def context(name, phase):
    if Path(name).name!=name or not name.startswith('e9_formal_'): raise ValueError('Invalid run')
    paths=project_paths();run=dict(results=ROOT/'results/runs'/name,provenance=ROOT/'provenance/runs'/name)
    cfg=json.loads((run['provenance']/'run.json').read_text())['config']
    approval=json.loads((run['provenance']/'approval.json').read_text())
    guard=inputs.Guard(ROOT,run);sys.addaudithook(guard)
    budget=Budget(paths,run,cfg,phase,guard)
    verify({**approval['protected_files'],**approval['new_source_sha256']})
    return paths,run,cfg,approval,guard,budget


def release_targets(paths, run, cfg, approval, guard):
    return inputs.release_targets(paths,run,cfg,approval,guard)


def progress(stage, position, total, started, **extra):
    print(json.dumps(dict(stage=stage,completed=position,total=total,
        elapsed_seconds=round(time.monotonic()-started,2),**extra)),flush=True)
