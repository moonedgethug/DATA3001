"""Configuration uses the running Python; tests never execute research tasks."""
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ENTRY = Path(__file__).resolve().parents[1] / 'environment/configure.py'


class NotebookConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ENTRY.is_file(), 'The configuration cell needs a current-Python installer.')
        spec = importlib.util.spec_from_file_location('notebook_configuration_test', ENTRY)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_install_targets_current_python_and_keeps_lock_authoritative(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(self.module, '_run', side_effect=lambda args, **kw: calls.append(args)):
                self.module.install_packages(root, Path('/unused/uv'))
        export, dependencies, project = calls
        self.assertIn('--locked', export)
        self.assertIn('--no-emit-project', export)
        self.assertIn('--require-hashes', dependencies)
        self.assertIn('--no-deps', project)
        for call in calls:
            self.assertEqual(call[call.index('--python') + 1], sys.executable)
            self.assertIn('--no-python-downloads', call)
            self.assertNotIn('sync', call)
        self.assertIn('--editable', project)

    def test_failed_lock_validation_does_not_install(self):
        with patch.object(self.module, '_run', side_effect=subprocess.CalledProcessError(1, 'export')) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                self.module.install_packages(Path('/unused'), Path('/unused/uv'))
        self.assertEqual(run.call_count, 1)

    def test_updating_a_loaded_library_requires_restart(self):
        with self.assertRaisesRegex(RuntimeError, 'Restart.*numpy'):
            self.module.check_loaded_versions({'numpy': '1.0'}, {'numpy': '2.0'})

    def test_unchanged_loaded_libraries_do_not_require_restart(self):
        self.module.check_loaded_versions({'numpy': '2.0'}, {'numpy': '2.0', 'pandas': '3.0'})

    def test_wrong_python_stops_before_downloading_or_installing(self):
        with patch.object(self.module.sys, 'version_info', (3, 9, 6)):
            with patch.object(self.module, 'ensure_uv') as prepare:
                with self.assertRaisesRegex(RuntimeError, 'Python 3.12'):
                    self.module.configure(Path('/unused'))
            prepare.assert_not_called()

    def test_installer_download_requires_verified_package_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(self.module.urllib.request, 'urlopen', return_value=io.BytesIO(b'unverified')):
                with self.assertRaisesRegex(RuntimeError, 'checksum'):
                    self.module.ensure_uv(Path(directory))
            self.assertFalse((Path(directory) / '.tools/uv/0.13.9/uv').exists())


if __name__ == '__main__':
    unittest.main()
