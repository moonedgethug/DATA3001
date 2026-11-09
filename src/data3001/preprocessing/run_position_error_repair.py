"""Approved two-stage repair runner. No model or canonical writes."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from ftplib import FTP, error_perm
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import threading
import time

import numpy as np
import pandas as pd

from data3001.preprocessing import position_error_repair as repair

ROOT = Path(__file__).resolve().parents[3]
TRACE = ROOT / 'provenance/reviews/position_error_s4_e8_source_trace'
PAIRS = ROOT / 'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/training_coordinates.parquet'
PLAN = ROOT / 'docs/position_error_s4_e8_repair_plan.md'
EXPECTED = {
    'docs/contract/data_contract_v1.0.xlsx': '6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446',
    'configs/dataset_manifest.json': 'c71a7ac3d0230b7489bcfc417d4caceb26ffc1230644a11300a642d7812e041e',
    str(PAIRS.relative_to(ROOT)): '8638434fb651d10737a2827350d5ff98a3a76a5f3427778748c17a3ddb68715d',
    'docs/position_error_s4_e8_repair_plan.md': '7507b533679849f411cdab88b37e3ad72ed8a6b7c5d2492cac74139f6bf7230a',
}
ROUTES = {
    'legacy': '/phod/pub/lumpkin/hourly/v2.00/netcdf/drifter_{id}.nc',
    'current': '/phod/pub/buoydata/hourly_product/v2.01.1/drifter_hourly_{id}.nc',
}


def write_json(path, data):
    path = Path(path)
    text = json.dumps(data, indent=2, default=repair.jsonable, allow_nan=True) + '\n'
    with path.open('x') as stream:
        stream.write(text)


def frame_hash(frame):
    ordered = frame.sort_values(['id', 'source_obs']).reset_index(drop=True)
    return hashlib.sha256(pd.util.hash_pandas_object(ordered, index=False).values.tobytes()).hexdigest()


def prepare():
    for name, expected in EXPECTED.items():
        assert repair.sha256(ROOT / name) == expected, name
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run = ROOT / 'provenance/migrations' / ('position_error_repair_' + stamp)
    run.mkdir()
    for name in ['sources', 'pilot', 'full']:
        (run / name).mkdir()
    ds = json.loads((ROOT / 'configs/dataset_manifest.json').read_text())
    pairs = pd.read_parquet(PAIRS)
    assert len(pairs) == 265393 and pairs.id.nunique() == 338
    assert pairs.horizon_days.eq(7).all() and not pairs.outside.any()
    pieces = []
    protected = dict(EXPECTED)
    for name in ['configs/assets.json', 'docs/research_stage_ledger.md',
                 'docs/position_error_s4_e8_contract.md']:
        protected[name] = repair.sha256(ROOT / name)
    for ident, group in pairs.groupby('id', sort=True):
        entry = ds['records'][str(ident)]
        assert entry['pool'] == 'train' and entry['path'] == f'data/train/{ident}.parquet'
        assert repair.sha256(ROOT / entry['path']) == entry['sha256']
        protected[entry['path']] = entry['sha256']
        origin = group.origin_source_obs.value_counts()
        endpoint = group.endpoint_source_obs.value_counts()
        keys = np.unique(np.r_[origin.index, endpoint.index]).astype('int64')
        obs = pd.read_parquet(ROOT / entry['path'],
            columns=['source_obs', 'time', 'lon', 'lat', 'err_lon', 'err_lat'],
            filters=[('source_obs', 'in', keys.tolist())])
        assert len(obs) == len(keys) and not obs.source_obs.duplicated().any()
        assert obs.time.lt(pd.Timestamp('2020-01-01', tz='UTC').timestamp()).all()
        obs['id'] = np.int64(ident)
        obs['origin_pair_count'] = obs.source_obs.map(origin).fillna(0).astype('int64')
        obs['endpoint_pair_count'] = obs.source_obs.map(endpoint).fillna(0).astype('int64')
        obs['base_version'] = ds['version']
        obs = obs.rename(columns={'err_lon':'original_err_lon', 'err_lat':'original_err_lat'})
        pieces.append(obs)
    targets = pd.concat(pieces, ignore_index=True).sort_values(['id','source_obs']).reset_index(drop=True)
    assert len(targets) == 355247
    assert targets.origin_pair_count.sum() == targets.endpoint_pair_count.sum() == len(pairs)
    targets['time_UTC'] = pd.to_datetime(targets.time, unit='s', utc=True)
    targets.to_parquet(run / 'target_keys.parquet', index=False)
    diagnostic = sorted({int(x['id']) for x in json.loads((TRACE / 'selected_training_keys.json').read_text())})
    assert len(diagnostic) == 19 and set(diagnostic) <= set(targets.id)
    write_json(run / 'approval.json', {
        'approved_user_instruction': 'Develop and run the 19-ID pilot; if verified, process all 338 training IDs within budget; independently verify and deliver an overlay; preserve base data; no model experiments.',
        'plan_sha256': repair.sha256(PLAN), 'approval_date':'2026-11-06',
        'scope': 'frozen E7 training origin and endpoint keys only',
        'diagnostic_ids': diagnostic, 'all_ids': sorted(map(int, targets.id.unique())),
        'target_count': len(targets), 'target_logical_hash': frame_hash(targets),
        'target_sha256': repair.sha256(run / 'target_keys.parquet'),
        'protected_files': protected, 'policy': repair.POLICY,
        'format_note': 'Legacy GPS ID may differ; an exact official imei field is accepted as an explicit within-file identity crosswalk. WMO, suffixes and filename alone are not accepted.',
        'budgets': {'workers':2,'request_timeout_s':45,'attempts':3,'pilot_s':1200,
                    'total_runtime_s':7200,'network_bytes':8*2**30,'disk_bytes':10*2**30,'peak_rss_bytes':4*2**30}})
    shutil.copyfile(PLAN, run / 'approved_plan.md')
    print(str(run), flush=True)


class Fetcher:
    def __init__(self, run, deadline, previous_bytes=0):
        self.run = run; self.deadline = deadline
        self.lock = threading.Lock(); self.local = threading.local()
        self.bytes = previous_bytes

    def ftp(self):
        if not getattr(self.local, 'ftp', None):
            f = FTP(); f.connect('ftp.aoml.noaa.gov', 21, timeout=45); f.login()
            self.local.ftp = f
        return self.local.ftp

    def disconnect(self):
        if getattr(self.local, 'ftp', None):
            self.local.ftp.close(); self.local.ftp = None

    def fetch(self, ident, route):
        remote = ROUTES[route].format(id=ident)
        record = {'id': int(ident), 'route':route, 'url':'ftp://ftp.aoml.noaa.gov'+remote,
                  'fetched_utc':datetime.now(timezone.utc).isoformat(), 'attempts':[]}
        cached = TRACE / f'sources/{"legacy_v2_00" if route == "legacy" else "current_v2_01_1"}_{ident}.nc'
        original_receipt = TRACE / ('legacy_v2_00_native_inspection.json' if route == 'legacy' else 'current_v2_01_1_native_inspection.json')
        if cached.exists():
            expected = {int(x['id']):x['sha256'] for x in json.loads(original_receipt.read_text())}
            digest = repair.sha256(cached)
            assert digest == expected[ident]
            final = self.run / 'sources' / (digest + '.nc')
            with self.lock:
                if not final.exists(): shutil.copyfile(cached, final)
            return dict(record, status='available', sha256=digest, path=str(final.relative_to(self.run)),
                        bytes=final.stat().st_size, reused_audited_cache=True)
        for attempt in range(1, 4):
            if time.time() >= self.deadline or self.bytes >= 8*2**30:
                return dict(record, status='not_fetched_budget')
            temporary = self.run / 'sources' / f'.{ident}_{route}.partial'
            try:
                f = self.ftp(); f.voidcmd('TYPE I')
                size = f.size(remote)
                with self.lock:
                    if self.bytes + size > 8*2**30: return dict(record, status='not_fetched_budget')
                with temporary.open('wb') as stream:
                    def save(block):
                        if time.time() > self.deadline: raise TimeoutError('Resource deadline reached')
                        with self.lock:
                            self.bytes += len(block)
                            if self.bytes > 8*2**30: raise TimeoutError('Network budget reached')
                        stream.write(block)
                    f.retrbinary('RETR ' + remote, save, blocksize=1024*1024)
                assert temporary.stat().st_size == size
                digest = repair.sha256(temporary)
                final = self.run / 'sources' / (digest + '.nc')
                with self.lock:
                    if final.exists(): temporary.unlink()
                    else: temporary.rename(final)
                record['attempts'].append({'attempt':attempt,'status':'complete'})
                return dict(record,status='available',sha256=digest,path=str(final.relative_to(self.run)),
                            bytes=size,reused_audited_cache=False)
            except error_perm as exc:
                record['attempts'].append({'attempt':attempt,'error':str(exc)})
                if str(exc).startswith('550'):
                    return dict(record,status='source_not_found')
                self.disconnect()
            except Exception as exc:
                record['attempts'].append({'attempt':attempt,'error':str(exc)})
                self.disconnect()
            finally:
                if temporary.exists(): temporary.unlink()
            time.sleep(min(attempt, 3))
        return dict(record,status='fetch_failed')


def run_phase(run, phase, reuse_registry=None):
    approval = json.loads((run / 'approval.json').read_text())
    assert repair.sha256(run / 'target_keys.parquet') == approval['target_sha256']
    for rel, expected in EXPECTED.items(): assert repair.sha256(ROOT / rel) == expected
    folder = run / phase
    if (folder / 'error_overlay.parquet').exists(): raise FileExistsError('Phase output already exists')
    if phase == 'full':
        pv = json.loads((run / 'pilot/verification.json').read_text())
        assert pv['passed'] and pv['pilot_budget_projection_passed']
    targets = pd.read_parquet(run / 'target_keys.parquet')
    ids = approval['diagnostic_ids'] if phase == 'pilot' else approval['all_ids']
    targets = targets[targets.id.isin(ids)]
    existing = []
    previous_bytes = 0
    if phase == 'full':
        existing = json.loads((run / 'pilot/source_registry.json').read_text())
        previous_bytes = json.loads((run / 'pilot/resources.json').read_text())['network_bytes']
    prior_elapsed = 0
    if reuse_registry is not None:
        assert reuse_registry.resolve().is_relative_to(run)
        existing = json.loads(reuse_registry.read_text())
        prior_resources = json.loads((reuse_registry.parent / 'resources.json').read_text())
        previous_bytes = prior_resources['network_bytes']
        prior_elapsed = prior_resources['elapsed_seconds']
    start = time.time()
    if not (run / 'resource_clock.json').exists():
        write_json(run / 'resource_clock.json', {'start_epoch':start, 'deadline_epoch':start+7200})
    deadline = json.loads((run / 'resource_clock.json').read_text())['deadline_epoch']
    phase_deadline = min(deadline, start+1200) if phase == 'pilot' else deadline
    known = {(x['id'], x['route']) for x in existing}
    jobs = [(i,r) for i in ids for r in ROUTES if (i,r) not in known]
    fetcher = Fetcher(run, phase_deadline, previous_bytes)
    records = list(existing)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(fetcher.fetch, i, r):(i,r) for i,r in jobs}
        for n, future in enumerate(as_completed(futures),1):
            item = future.result(); records.append(item)
            with (folder / 'download_log.jsonl').open('a') as out: out.write(json.dumps(item)+'\n')
            if n % 10 == 0 or n == len(jobs):
                print(f'{phase}: downloaded {n}/{len(jobs)} source requests; {fetcher.bytes/2**20:.1f} MiB; elapsed {time.time()-start:.1f}s',flush=True)
    records.sort(key=lambda r:(r['id'],list(ROUTES).index(r['route'])))
    outputs = []
    for n,(ident, group) in enumerate(targets.groupby('id', sort=True),1):
        refs = []
        for item in records:
            if item['id'] != ident or item['status'] != 'available': continue
            assert repair.sha256(run / item['path']) == item['sha256']
            try:
                frame, meta = repair.read_reference(run / item['path'], ident, group)
            except (ValueError, KeyError, IndexError) as exc:
                frame = group[['source_obs']].copy(); frame['match_status'] = 'source_metadata_unresolved'
                meta = {'id':int(ident),'sha256':item['sha256'],'eligible':False,'reason':str(exc)}
            item['inspection'] = meta
            refs.append((frame,meta))
        overlay = repair.build_overlay(group, refs, run.name)
        if not refs:
            status = 'not_fetched_budget' if any(r['id']==ident and r['status']=='not_fetched_budget' for r in records) else 'source_missing'
            overlay['status_lon'] = status; overlay['status_lat'] = status; overlay['match_status'] = status
        outputs.append(overlay)
        if n % 10 == 0 or n == len(ids):
            print(f'{phase}: reconciled {n}/{len(ids)} IDs; elapsed {time.time()-start:.1f}s',flush=True)
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 4*2**30: raise MemoryError('RSS budget exceeded')
        if sum(p.stat().st_size for p in run.rglob('*') if p.is_file()) > 10*2**30: raise RuntimeError('Disk budget exceeded')
        if time.time() > phase_deadline: raise TimeoutError('Phase budget reached; sources/checkpoints retained')
    all_rows = pd.concat(outputs,ignore_index=True).sort_values(['id','source_obs']).reset_index(drop=True)
    assert len(all_rows)==len(targets) and not all_rows.duplicated(['id','source_obs']).any()
    all_rows.to_parquet(folder / 'error_overlay.parquet',index=False)
    all_rows.loc[~all_rows.ci_2d_usable].to_parquet(folder / 'exceptions.parquet',index=False)
    write_json(folder / 'source_registry.json', records)
    write_json(folder / 'resources.json', {'phase':phase,'elapsed_seconds':time.time()-start,
        'prior_attempt_seconds':prior_elapsed,'projection_base_seconds':time.time()-start+prior_elapsed,
        'network_bytes':fetcher.bytes,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'new_disk_bytes':sum(p.stat().st_size for p in run.rglob('*') if p.is_file()),
        'IDs':len(ids),'target_rows':len(targets),'logical_output_hash':frame_hash(all_rows)})
    print(f'{phase}: complete, {len(all_rows)} rows, usable {all_rows.ci_2d_usable.sum()}',flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','pilot','full'])
    parser.add_argument('--run',type=Path)
    parser.add_argument('--reuse-registry',type=Path)
    args=parser.parse_args()
    if args.action=='prepare': prepare()
    else:
        run=args.run.resolve()
        assert run.is_relative_to(ROOT / 'provenance/migrations') and run.name.startswith('position_error_repair_')
        run_phase(run,args.action,args.reuse_registry)


if __name__=='__main__': main()
