"""Run every scientific stage in its own process and preserve its exit status."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import psutil

from .workspace import write_json


def _live_group_members(group_id):
    members = []
    for process in psutil.process_iter(["pid", "status"]):
        try:
            if process.info["status"] != psutil.STATUS_ZOMBIE and os.getpgid(process.pid) == group_id:
                members.append(process.pid)
        except (ProcessLookupError, PermissionError, psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return members


def _signal_group(group_id, requested_signal):
    try:
        os.killpg(group_id, requested_signal)
    except ProcessLookupError:
        pass
    except PermissionError:
        # macOS can keep an unowned zombie after reparenting; it has already
        # stopped and must not turn a successful cleanup into a false failure.
        if _live_group_members(group_id):
            raise


def _stop_process_group(child, *, grace_seconds=5):
    """Reap the leader and stop its remaining workers, including orphaned ones."""
    child.poll()
    members = _live_group_members(child.pid)
    result = {"terminated_pids": members, "forced_kill": False}
    if not members:
        return result
    _signal_group(child.pid, signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        child.poll()
        if not _live_group_members(child.pid):
            child.poll()
            return result
        time.sleep(0.05)
    # Waiting only for the leader misses workers that ignore TERM after the
    # leader exits. Escalate for the owned group, regardless of leader status.
    _signal_group(child.pid, signal.SIGKILL)
    result["forced_kill"] = True
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        child.poll()
        if not _live_group_members(child.pid):
            child.poll()
            return result
        time.sleep(0.05)
    raise RuntimeError(f"Command process group {child.pid} did not stop")


def run_command(view, arguments, *, label=None, timeout=None):
    receipts_path = view.directory / "commands.json"
    receipts = json.loads(receipts_path.read_text()) if receipts_path.exists() else []
    number = len(receipts) + 1
    logfile = view.directory / f"command_{number:03d}.log"
    environment = dict(os.environ, DATA3001_PROJECT_ROOT=str(view.path),
                       PYTHONPATH=str(view.path / "src"), PYTHONDONTWRITEBYTECODE="1",
                       PYTHONUNBUFFERED="1", MPLCONFIGDIR=str(view.directory / "matplotlib"))
    # ProjectPaths derives data from PROJECT_ROOT. A fixed DATA_ROOT would
    # override temporary project roots used by the original scientific tests.
    environment.pop("DATA3001_DATA_ROOT", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONOPTIMIZE"] = "0"
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                     "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS"):
        environment[variable] = "1"
    receipt = {"label": label or arguments[0], "command": list(map(str, arguments)),
               "started_utc": datetime.now(timezone.utc).isoformat(), "status": "running",
               "cwd": str(view.path), "log": str(logfile), "returncode": None}
    receipts.append(receipt); write_json(receipts_path, receipts)
    started = time.monotonic()
    child = None
    try:
        with logfile.open("w") as log:
            child = subprocess.Popen([sys.executable, *map(str, arguments)], cwd=view.path,
                                     env=environment, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            receipt["pid"] = child.pid; write_json(receipts_path, receipts)
            result = child.wait(timeout=timeout)
        receipt["process_group_cleanup"] = _stop_process_group(child)
        receipt.update(returncode=result, status="complete" if result == 0 else "failed")
        if result:
            raise subprocess.CalledProcessError(result, receipt["command"])
        return receipt
    except BaseException as error:
        if child is not None and "process_group_cleanup" not in receipt:
            try:
                receipt["process_group_cleanup"] = _stop_process_group(child)
            except Exception as cleanup_error:
                receipt["cleanup_error"] = f"{type(cleanup_error).__name__}: {cleanup_error}"
        receipt.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                       error=f"{type(error).__name__}: {error}",
                       returncode=child.returncode if child is not None else None)
        raise
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - started
        write_json(receipts_path, receipts)


def run_module(view, module, arguments, **kwargs):
    return run_command(view, ["-B", "-m", module, *arguments], label=module, **kwargs)
