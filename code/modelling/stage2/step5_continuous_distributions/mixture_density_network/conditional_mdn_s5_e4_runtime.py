"""Cumulative, externally supervised execution for the approved MDN run."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import time
from datetime import datetime, timezone

import psutil

ROOT = Path(__file__).resolve().parents[4]


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    os.replace(temporary, path)


def remaining(cfg, ledger, phase):
    entries = ledger['entries']
    phase_spent = sum(e['elapsed_seconds'] for e in entries if e['phase'] == phase)
    total_spent = sum(e['elapsed_seconds'] for e in entries)
    return min(cfg['seconds'][phase] - phase_spent, cfg['seconds']['total'] - total_spent)


def storage_bytes(run):
    total=0
    for folder in run.values():
        for path in folder.rglob('*'):
            try: metadata=path.stat(follow_symlinks=False)
            except FileNotFoundError: continue  # atomic replace completed between enumeration and stat
            if stat.S_ISREG(metadata.st_mode):total+=metadata.st_size
    return total


def stop_group(pid):
    def live_members():
        found = []
        for process in psutil.process_iter(['pid', 'status']):
            try:
                if process.info['status'] != psutil.STATUS_ZOMBIE and os.getpgid(process.pid) == pid:
                    found.append(process)
            except (ProcessLookupError, PermissionError, psutil.NoSuchProcess):
                continue
        return found
    if not live_members():
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    time.sleep(.15)
    # macOS can return EPERM for a dead group whose unreaped leader is a zombie.
    if not live_members():
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 1
    while live_members():
        if time.monotonic() >= deadline:
            raise RuntimeError('Owned process group survived termination')
        time.sleep(.02)


def supervise(run, cfg, phase, label, command, command_seconds=None):
    if Path(label).name != label:
        raise ValueError('Unsafe command label')
    ledger_path = run['provenance'] / 'resource_ledger.json'
    lock = (run['provenance'] / 'resource.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise RuntimeError('An active resource supervisor already owns this run')
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {'version': 1, 'entries': [], 'active': None}
    if ledger.get('active'):
        lock.close()
        raise RuntimeError('Unclosed active receipt: reconcile previous execution before resuming')
    allowance = remaining(cfg, ledger, phase)
    if command_seconds is not None:
        allowance = min(allowance, command_seconds)
    if allowance <= 0:
        lock.close()
        raise TimeoutError('Approved cumulative budget exhausted')
    started = time.monotonic()
    receipt = {'phase': phase, 'label': label, 'command': command,
               'started_utc': datetime.now(timezone.utc).isoformat(), 'allowance_seconds': allowance,
               'elapsed_seconds': 0., 'peak_process_tree_rss_bytes': 0, 'peak_storage_bytes': storage_bytes(run),
               'returncode': None, 'stop_reason': None}
    ledger['active'] = receipt.copy()
    atomic_json(ledger_path, ledger)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1',
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
               MDN_RUN_NAME=run['results'].name, MDN_PHASE=phase)
    child = None
    previous_sigterm=signal.getsignal(signal.SIGTERM)
    def terminate_supervisor(signum,frame):
        raise KeyboardInterrupt('Resource supervisor received SIGTERM')
    signal.signal(signal.SIGTERM,terminate_supervisor)
    try:
        with (run['provenance'] / (label + '.log')).open('a') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                     cwd=ROOT, env=env, start_new_session=True)
            process = psutil.Process(child.pid)
            next_receipt, next_storage = 0., 0.
            while child.poll() is None:
                elapsed = time.monotonic() - started
                try:
                    members = [process] + process.children(recursive=True)
                    rss = 0
                    for p in members:
                        try: rss += p.memory_info().rss
                        except psutil.NoSuchProcess: pass
                    receipt['peak_process_tree_rss_bytes'] = max(receipt['peak_process_tree_rss_bytes'], rss)
                except psutil.NoSuchProcess:
                    pass
                if elapsed >= next_storage:
                    receipt['peak_storage_bytes'] = max(receipt['peak_storage_bytes'], storage_bytes(run))
                    next_storage = elapsed + 5
                if elapsed >= allowance:
                    receipt['stop_reason'] = 'time_budget'
                elif receipt['peak_process_tree_rss_bytes'] > cfg['rss_hard_gib'] * 2**30:
                    receipt['stop_reason'] = 'memory_budget'
                elif receipt['peak_storage_bytes'] > cfg['storage_hard_gib'] * 2**30:
                    receipt['stop_reason'] = 'storage_budget'
                if receipt['stop_reason']:
                    stop_group(child.pid)
                    break
                if elapsed >= next_receipt:
                    receipt['elapsed_seconds'] = elapsed
                    ledger['active'] = receipt.copy()
                    atomic_json(ledger_path, ledger)
                    next_receipt = elapsed + 30
                time.sleep(min(.2, max(.01, allowance-elapsed)))
            child.wait()
            # The leader may finish while a scoring descendant still owns the group.
            stop_group(child.pid)
            receipt['returncode'] = child.returncode
    except BaseException as error:
        receipt['stop_reason'] = type(error).__name__ + ': ' + str(error)
        if child is not None:
            stop_group(child.pid)
            child.wait()
        receipt['returncode'] = -1
        raise
    finally:
        receipt['elapsed_seconds'] = time.monotonic() - started
        receipt['peak_storage_bytes'] = max(receipt['peak_storage_bytes'], storage_bytes(run))
        ledger['entries'].append(receipt)
        ledger['active'] = None
        atomic_json(ledger_path, ledger)
        lock.close()
        signal.signal(signal.SIGTERM,previous_sigterm)
    return receipt['returncode'] if not receipt['stop_reason'] else (receipt['returncode'] or 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run')
    parser.add_argument('phase')
    parser.add_argument('label')
    parser.add_argument('--limit-seconds', type=float)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if Path(args.run).name != args.run or not args.run.startswith('conditional_mdn_s5_e4_'):
        raise ValueError('Invalid MDN run name')
    run = {part: ROOT / (part+'/runs') / args.run for part in ('results','provenance')}
    cfg = json.loads((run['provenance']/'run.json').read_text())['config']
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        raise ValueError('A command is required')
    raise SystemExit(supervise(run, cfg, args.phase, args.label, command, args.limit_seconds))


if __name__ == '__main__':
    main()
