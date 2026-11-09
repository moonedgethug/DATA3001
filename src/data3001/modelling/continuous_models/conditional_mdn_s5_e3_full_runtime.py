"""Metered formal execution after explicit resource-ceiling waiver.

Resource use remains visible and interruption closes the owned process tree.
There is intentionally no time, CPU or experimental storage budget cutoff.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import psutil
from .conditional_mdn_s5_e3_runtime import ROOT, atomic_json, storage_bytes, stop_group


def supervise(name, label, command):
    if Path(name).name != name or not name.startswith('conditional_mdn_s5_e3_'):
        raise ValueError('Invalid run')
    if Path(label).name != label or not command:
        raise ValueError('Invalid stage')
    run = {k: ROOT/k/'runs'/name for k in ('results', 'provenance')}
    folder = run['provenance']/'formal_v1'
    auth = json.loads((folder/'authorization.json').read_text())
    if not auth['full_experiment_authorized'] or auth['resource_time_limit_seconds'] is not None:
        raise PermissionError('Explicit full-run resource waiver required')
    lock = (run['provenance']/'resource.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    ledger_path = folder/'resource_ledger.json'
    old = json.loads((run['provenance']/'resource_ledger.json').read_text())
    if old.get('active'):
        raise RuntimeError('Old supervisor remains active')
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else dict(
        version=1, prior_compute_seconds=sum(e['elapsed_seconds'] for e in old['entries']),
        entries=[], active=None, resource_limit_seconds=None)
    if ledger['active']:
        raise RuntimeError('Reconcile interrupted receipt before resuming')
    receipt = dict(label=label, command=command, started_utc=datetime.now(timezone.utc).isoformat(),
                   elapsed_seconds=0., peak_process_tree_rss_bytes=0,
                   peak_storage_bytes=storage_bytes(run), returncode=None, stop_reason=None)
    started = time.monotonic()
    ledger['active'] = receipt.copy(); atomic_json(ledger_path, ledger)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1',
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
               VECLIB_MAXIMUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    child = None
    previous = signal.getsignal(signal.SIGTERM)
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Formal supervisor interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with (folder/(label+'.log')).open('a') as log:
            child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
                                     stderr=subprocess.STDOUT, start_new_session=True)
            receipt['pid'] = child.pid
            process = psutil.Process(child.pid)
            next_update = 0.
            while child.poll() is None:
                elapsed = time.monotonic()-started
                if elapsed >= next_update:
                    rss = 0
                    try:
                        for p in [process]+process.children(recursive=True):
                            try: rss += p.memory_info().rss
                            except psutil.NoSuchProcess: pass
                    except psutil.NoSuchProcess: pass
                    receipt['peak_process_tree_rss_bytes'] = max(receipt['peak_process_tree_rss_bytes'], rss)
                    receipt['peak_storage_bytes'] = max(receipt['peak_storage_bytes'], storage_bytes(run))
                    receipt['elapsed_seconds'] = elapsed
                    receipt['free_disk_bytes'] = shutil.disk_usage(ROOT).free
                    ledger['active'] = receipt.copy(); atomic_json(ledger_path, ledger)
                    # Physical availability safeguard, not an experimental budget.
                    if receipt['free_disk_bytes'] < 2*2**30:
                        receipt['stop_reason'] = 'physical_disk_below_2GiB'
                        stop_group(child.pid); break
                    next_update = elapsed+30
                time.sleep(.5)
            child.wait(); stop_group(child.pid)
            receipt['returncode'] = child.returncode
    except BaseException as error:
        receipt['stop_reason'] = repr(error)
        if child is not None:
            stop_group(child.pid); child.wait()
        receipt['returncode'] = -1
        raise
    finally:
        receipt['elapsed_seconds'] = time.monotonic()-started
        receipt['peak_storage_bytes'] = max(receipt['peak_storage_bytes'], storage_bytes(run))
        ledger['entries'].append(receipt); ledger['active'] = None
        atomic_json(ledger_path, ledger)
        signal.signal(signal.SIGTERM, previous); lock.close()
    return receipt['returncode'] or (1 if receipt['stop_reason'] else 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run'); parser.add_argument('label')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    raise SystemExit(supervise(args.run, args.label, command))


if __name__ == '__main__':
    main()
