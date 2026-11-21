"""First launch without Python on PATH; no experiments or servers are started."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


class FirstLaunchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='DATA3001 first launch ')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        (self.root / 'code/environment').mkdir(parents=True)

    def test_double_click_entry_finds_project_without_python_on_path(self):
        entry = ROOT / 'START_HERE.command'
        self.assertTrue(entry.is_file(), 'A first-run entry outside the notebook is required')
        shutil.copy2(entry, self.root / entry.name)
        log = self.root / 'entry.log'
        shell_tools = self.root / 'shell-tools'
        shell_tools.mkdir()
        (shell_tools / 'dirname').symlink_to('/usr/bin/dirname')
        self.assertIsNone(shutil.which('python', path=str(shell_tools)))
        self.assertIsNone(shutil.which('python3', path=str(shell_tools)))
        (self.root / 'code/environment/setup.sh').write_text(
            '#!/bin/bash\nprintf "%s\\n" "$1" > "$STARTUP_TEST_LOG"\n')
        result = subprocess.run(['/bin/bash', str(self.root / entry.name)], cwd='/',
                                env={'PATH': str(shell_tools), 'STARTUP_TEST_LOG': str(log)},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(log.read_text().strip(), '--launch')

    def test_first_run_failure_preserves_the_installers_exit_status(self):
        entry = ROOT / 'START_HERE.command'
        self.assertTrue(entry.is_file())
        shutil.copy2(entry, self.root / entry.name)
        (self.root / 'code/environment/setup.sh').write_text('#!/bin/bash\nexit 42\n')
        result = subprocess.run(['/bin/bash', str(self.root / entry.name)], cwd='/',
                                stdin=subprocess.DEVNULL, capture_output=True, text=True)
        self.assertEqual(result.returncode, 42)

    def launch_module(self):
        path = ROOT / 'code/environment/launch.py'
        self.assertTrue(path.is_file(), 'Launch must select the prepared local kernel')
        spec = importlib.util.spec_from_file_location('delivery_launch', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_remote_kernel_metadata_is_replaced_without_erasing_cells_or_outputs(self):
        launch = self.launch_module()
        notebook = {'metadata': {'kernelspec': {'name': 'python3'}, 'keep': 'yes'},
                    'cells': [{'cell_type': 'code', 'source': ['print(1)'],
                               'execution_count': 1, 'outputs': [{'text': 'saved output'}]}]}
        path = self.root / 'code/run_experiments.ipynb'
        path.write_text(json.dumps(notebook))
        self.assertEqual(launch.prepare_notebook(self.root), path)
        prepared = json.loads(path.read_text())
        self.assertEqual(prepared['metadata']['kernelspec']['name'], 'data3001-py312')
        self.assertEqual(prepared['cells'], notebook['cells'])
        self.assertEqual(prepared['metadata']['keep'], 'yes')

    def test_server_uses_project_directory_and_only_the_prepared_kernel(self):
        launch = self.launch_module()
        (self.root / 'code/run_experiments.ipynb').write_text('{"metadata": {}, "cells": []}')
        with patch.object(launch.os, 'chdir') as change_directory, patch.object(launch.os, 'execv') as execute:
            launch.main(self.root)
        change_directory.assert_called_once_with(self.root)
        executable, args = execute.call_args.args
        self.assertEqual(executable, launch.sys.executable)
        self.assertIn('--ServerApp.root_dir=' + str(self.root), args)
        self.assertIn('--ServerApp.ip=127.0.0.1', args)
        self.assertIn('--MappingKernelManager.default_kernel_name=data3001-py312', args)
        self.assertIn('--KernelSpecManager.allowed_kernelspecs=["data3001-py312"]', args)


if __name__ == '__main__':
    unittest.main()
