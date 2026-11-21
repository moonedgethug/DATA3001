"""Reproduction outputs and subprocesses stay inside their owned boundaries."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import psutil

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))

from reproduction.runner import run_command
from reproduction.workspace import ExecutionWorkspace


class DeliverySafetyTests(unittest.TestCase):
    def test_output_aliases_are_rejected_before_any_archive_write(self):
        for aliased_component in ("results", "results/reproduced"):
            with self.subTest(component=aliased_component), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                (root / "docs").mkdir()
                (root / "docs/migration_manifest.json").write_text(json.dumps({
                    "schema_version": 1, "files": []}))
                archive = root / "archive"
                archive.mkdir()
                (archive / "sentinel.txt").write_text("original")
                alias = root / aliased_component
                alias.parent.mkdir(parents=True, exist_ok=True)
                alias.symlink_to(archive, target_is_directory=True)
                with self.assertRaises(PermissionError):
                    ExecutionWorkspace(root, "must-not-exist")
                self.assertEqual(list(archive.iterdir()), [archive / "sentinel.txt"])
                self.assertEqual((archive / "sentinel.txt").read_text(), "original")

    def exercise_descendant(self, *, parent_waits, interrupted=False):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            workspace = directory / "workspace"
            workspace.mkdir()
            view = SimpleNamespace(directory=directory, path=workspace)
            marker = workspace / "descendant.pid"
            descendant = (
                "import os,signal,time\n"
                "from pathlib import Path\n"
                "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
                "Path('descendant.pid').write_text(str(os.getpid()))\n"
                "time.sleep(30)\n"
            )
            parent = (
                "import subprocess,sys,time\n"
                "from pathlib import Path\n"
                f"subprocess.Popen([sys.executable,'-c',{descendant!r}])\n"
                "while not Path('descendant.pid').exists(): time.sleep(0.01)\n"
                + ("time.sleep(30)\n" if parent_waits else "")
            )
            try:
                if interrupted:
                    def interrupt_after_start(**kwargs):
                        deadline = time.monotonic() + 5
                        while not marker.exists() and time.monotonic() < deadline:
                            time.sleep(0.01)
                        self.assertTrue(marker.exists())
                        raise KeyboardInterrupt

                    with patch.object(subprocess.Popen, "wait", side_effect=interrupt_after_start):
                        with self.assertRaises(KeyboardInterrupt):
                            run_command(view, ["-B", "-c", parent])
                elif parent_waits:
                    with self.assertRaises(subprocess.TimeoutExpired):
                        run_command(view, ["-B", "-c", parent], timeout=1)
                else:
                    run_command(view, ["-B", "-c", parent], timeout=5)
                self.assertTrue(marker.is_file(), "The descendant must start before cancellation")
                pid = int(marker.read_text())
                try:
                    active = psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
                except psutil.NoSuchProcess:
                    active = False
                self.assertFalse(active, "The runner returned while its descendant was still alive")
                receipt = json.loads((directory / "commands.json").read_text())[-1]
                expected_status = "interrupted" if interrupted else "failed" if parent_waits else "complete"
                self.assertEqual(receipt["status"], expected_status)
                self.assertTrue(receipt["process_group_cleanup"]["forced_kill"])
                if interrupted:
                    self.assertIn("KeyboardInterrupt", receipt["error"])
                elif parent_waits:
                    self.assertIn("TimeoutExpired", receipt["error"])
            finally:
                # A red regression must not leave its deliberately stubborn process running.
                receipts = directory / "commands.json"
                if receipts.exists():
                    pid = json.loads(receipts.read_text())[-1].get("pid")
                    if pid:
                        try:
                            os.killpg(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass

    def test_timeout_stops_descendant_after_parent_exits_on_term(self):
        self.exercise_descendant(parent_waits=True)

    def test_normal_parent_exit_also_cleans_up_remaining_descendants(self):
        self.exercise_descendant(parent_waits=False)

    def test_keyboard_interrupt_stops_workers_and_records_interruption(self):
        self.exercise_descendant(parent_waits=True, interrupted=True)


if __name__ == "__main__":
    unittest.main()
