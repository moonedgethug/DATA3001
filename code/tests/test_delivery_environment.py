"""Environment entry tests: all writes and external commands stay in temporary roots."""

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
import venv
from unittest import mock


ENVIRONMENT = Path(__file__).resolve().parents[1] / "environment"


class EnvironmentCheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.assertTrue((ENVIRONMENT / "check.py").is_file(), "Shared checker is missing")
        spec = importlib.util.spec_from_file_location("delivery_check", ENVIRONMENT / "check.py")
        self.check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.check)

    def write_manifests(self):
        (self.root / ".python-version").write_text("3.12.14\n")
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "example"\nversion = "0.1.0"\n'
            'requires-python = ">=3.12,<3.13"\ndependencies = ["example-dependency"]\n'
        )
        (self.root / "uv.lock").write_text(
            'version = 1\n[[package]]\nname = "example-dependency"\nversion = "1.2.3"\n'
        )

    def test_missing_project_has_actionable_diagnosis_without_writes(self):
        report = self.check.check_environment(self.root, verbose=False)
        self.assertFalse(report["ok"])
        self.assertEqual(report["current"]["executable"], sys.executable)
        self.assertEqual(report["setup_path"], str(self.root / "code/environment/setup.sh"))
        self.assertTrue(any(".python-version" in error for error in report["errors"]))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_wrong_kernel_is_not_mistaken_for_ready_project(self):
        self.write_manifests()
        report = self.check.check_environment(self.root, verbose=False)
        self.assertFalse(report["current"]["is_project_venv"])
        self.assertTrue(any("kernel" in error.lower() for error in report["errors"]))
        self.assertFalse(report["project"]["exists"])

    def test_old_python_returns_basic_report_instead_of_import_failure(self):
        self.write_manifests()
        with mock.patch.object(self.check.sys, "version_info", (3, 8, 10)):
            report = self.check.check_environment(self.root, verbose=False)
        self.assertEqual(report["current"]["version"], "3.8.10")
        self.assertTrue(any("3.12.14" in error for error in report["errors"]))
        self.assertTrue(any("TOML" in warning for warning in report["warnings"]))

    def test_syntax_parses_on_python_38(self):
        ast.parse((ENVIRONMENT / "check.py").read_text(), feature_version=(3, 8))

    def test_platform_check_rejects_intel_and_macos_before_14(self):
        for machine, release in (("x86_64", "26.0"), ("arm64", "13.7")):
            with self.subTest(machine=machine, release=release), \
                 mock.patch.object(self.check.platform, "system", return_value="Darwin"), \
                 mock.patch.object(self.check.platform, "machine", return_value=machine), \
                 mock.patch.object(self.check.platform, "mac_ver", return_value=(release, (), machine)):
                report = self.check.check_environment(self.root, verbose=False)
            self.assertTrue(any("Apple Silicon" in error or "macOS 14" in error for error in report["errors"]))

    def test_same_version_from_wrong_import_location_is_rejected(self):
        self.assertTrue(hasattr(self.check, "_check_module_origins"))
        fake_numpy = types.SimpleNamespace(__file__=str(self.root / "external/numpy/__init__.py"), __version__="2.5.4")
        errors = []
        with mock.patch.dict(sys.modules, {"numpy": fake_numpy}):
            origins = self.check._check_module_origins(self.root, errors)
        self.assertIn("external/numpy", origins["numpy"])
        self.assertTrue(any("numpy" in error and "outside" in error for error in errors))

    def test_native_smoke_uses_isolated_project_python_and_bounded_timeout(self):
        self.assertTrue(hasattr(self.check, "_native_library_probe"))
        python = self.root / ".venv/bin/python"
        success = subprocess.CompletedProcess([], 0, json.dumps({"ok": True, "libraries": {}}), "")
        with mock.patch.object(self.check.subprocess, "run", return_value=success) as run:
            result = self.check._native_library_probe(python, self.root)
        self.assertTrue(result["ok"])
        args, kwargs = run.call_args
        self.assertEqual(args[0][:3], [str(python), "-I", "-B"])
        self.assertLessEqual(kwargs["timeout"], 120)
        self.assertNotIn("PYTHONPATH", kwargs["env"])
        self.assertNotIn("PYTHONHOME", kwargs["env"])

    def test_native_timeout_is_reported_without_crashing_diagnosis(self):
        self.assertTrue(hasattr(self.check, "_native_library_probe"))
        with mock.patch.object(self.check.subprocess, "run", side_effect=subprocess.TimeoutExpired("probe", 25)):
            result = self.check._native_library_probe(self.root / ".venv/bin/python", self.root)
        self.assertFalse(result["ok"])
        self.assertIn("timed out", result["error"])

    def test_missing_compiler_is_an_actionable_failure(self):
        self.assertTrue(hasattr(self.check, "_compiler_probe"))
        with mock.patch.object(self.check.subprocess, "run", side_effect=FileNotFoundError("xcrun missing")):
            result = self.check._compiler_probe()
        self.assertFalse(result["ok"])
        self.assertIn("Command Line Tools", result["error"])

    def test_missing_dependency_is_identified_from_manifest(self):
        self.write_manifests()
        report = self.check.check_environment(self.root, verbose=False)
        self.assertTrue(any("example-dependency" in error for error in report["errors"]))

    def test_changed_lock_is_detected_from_preparation_record(self):
        self.write_manifests()
        (self.root / ".venv").mkdir()
        record = {"schema": 1, "python_pin": "3.12.14", "uv_version": "0.13.9",
                  "manifests": {"uv.lock": "outdated"}, "packages": {}}
        (self.root / ".venv/.data3001-environment.json").write_text(json.dumps(record))
        report = self.check.check_environment(self.root, verbose=False)
        self.assertTrue(any("uv.lock" in error and "changed" in error for error in report["errors"]))

    def test_dependency_drift_is_detected(self):
        self.write_manifests()
        (self.root / ".venv").mkdir()
        record = {"schema": 1, "python_pin": "3.12.14", "uv_version": "0.13.9",
                  "manifests": {}, "packages": {"vanished-package": "1.0"}}
        (self.root / ".venv/.data3001-environment.json").write_text(json.dumps(record))
        with mock.patch.object(self.check.sys, "prefix", str(self.root / ".venv")):
            report = self.check.check_environment(self.root, verbose=False)
        self.assertTrue(any("vanished-package" in error for error in report["errors"]))

    def test_packages_added_after_preparation_are_detected(self):
        self.write_manifests()
        (self.root / ".venv").mkdir()
        record = {"schema": 1, "python_pin": "3.12.14", "uv_version": "0.13.9",
                  "manifests": {}, "packages": {"example-dependency": "1.2.3"}}
        (self.root / ".venv/.data3001-environment.json").write_text(json.dumps(record))
        with mock.patch.object(self.check.sys, "prefix", str(self.root / ".venv")), \
             mock.patch.object(self.check, "_installed_packages", return_value={
                 "example-dependency": "1.2.3", "unexpected-package": "2.0"}):
            report = self.check.check_environment(self.root, verbose=False)
        self.assertTrue(any("unexpected-package" in error for error in report["errors"]))

    def test_cli_is_read_only_and_returns_json(self):
        self.write_manifests()
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        result = subprocess.run([sys.executable, "-B", str(ENVIRONMENT / "check.py"),
                                 "--root", str(self.root), "--json"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["ok"])
        self.assertEqual(before, sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*")))

    @unittest.skipUnless(sys.version_info[:2] == (3, 12) and sys.platform == "darwin", "macOS Python 3.12 fixture")
    def test_project_interpreter_is_checked_separately_from_wrong_current_kernel(self):
        self.write_manifests()
        (self.root / "pyproject.toml").write_text('[project]\nname = "example"\nversion = "0.1.0"\ndependencies = []\n')
        (self.root / ".python-version").write_text(".".join(map(str, sys.version_info[:3])) + "\n")
        venv.EnvBuilder(with_pip=False, symlinks=True).create(self.root / ".venv")
        record = {"schema": 1, "python_pin": (self.root / ".python-version").read_text().strip(),
                  "uv_version": "0.13.9", "packages": {}, "manifests": {
                      name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
                      for name in ("pyproject.toml", "uv.lock", ".python-version")}}
        (self.root / ".venv/.data3001-environment.json").write_text(json.dumps(record))
        report = self.check.check_environment(self.root, verbose=False)
        self.assertFalse(report["ok"])
        diagnosis = report["project"]["diagnosis"]
        self.assertTrue(diagnosis["current"]["is_project_venv"])
        self.assertFalse(diagnosis["ok"], "The intentionally empty fixture lacks scientific libraries")
        self.assertIn("native", diagnosis)


class SetupEntryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="data3001 setup ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.assertTrue((ENVIRONMENT / "setup.sh").is_file(), "Shared setup entry is missing")
        (self.root / "code/environment").mkdir(parents=True)
        shutil.copy2(ENVIRONMENT / "setup.sh", self.root / "code/environment/setup.sh")
        (self.root / "code/run_experiments.ipynb").write_text("{}")
        (self.root / "pyproject.toml").write_text("[project]\n")
        (self.root / "uv.lock").write_text("version = 1\n")
        (self.root / ".python-version").write_text("3.12.14\n")
        self.bin = self.root / "fake-bin"
        self.bin.mkdir()
        self.log = self.root / "commands.log"
        self.env = dict(os.environ, PATH=str(self.bin) + ":/usr/bin:/bin",
                        TEST_LOG=str(self.log), TEST_ROOT=str(self.root),
                        UV_PROJECT_ENVIRONMENT="/must-not-use", VIRTUAL_ENV="/must-not-use")
        self.executable("uname", '#!/bin/sh\ncase "$1" in -s) echo Darwin;; -m) echo arm64;; esac\n')
        self.executable("sw_vers", '#!/bin/sh\necho 14.0\n')
        self.executable("xcrun", '#!/bin/sh\necho /fake/apple/toolchain\n')
        self.executable("xcode-select", '#!/bin/sh\necho requested-apple-tools >> "$TEST_LOG"\n')
        self.executable("uv", '#!/bin/sh\nif [ "$1" = "--version" ]; then echo "uv 0.13.9"; exit 0; fi\n'
                        'printf "uv env=%s active=%s args=" "$UV_PROJECT_ENVIRONMENT" "${VIRTUAL_ENV-}" >> "$TEST_LOG"\n'
                        'printf "<%s>" "$@" >> "$TEST_LOG"\nprintf "\\n" >> "$TEST_LOG"\n'
                        'if [ "$1" = "sync" ]; then mkdir -p "$TEST_ROOT/.venv/bin"; '
                        'cp "$TEST_ROOT/fake-python" "$TEST_ROOT/.venv/bin/python"; fi\n')
        fake_python = self.root / "fake-python"
        fake_python.write_text('#!/bin/sh\nprintf "python-env:path=%s home=%s\\n" "${PYTHONPATH-}" "${PYTHONHOME-}" >> "$TEST_LOG"\n'
                               'printf "python:" >> "$TEST_LOG"\n'
                               'printf "<%s>" "$@" >> "$TEST_LOG"\nprintf "\\n" >> "$TEST_LOG"\n'
                               'if [ "$1" = "-" ]; then cat >/dev/null; fi\n')
        fake_python.chmod(0o755)

    def executable(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def run_setup(self, *args):
        return subprocess.run(["/bin/bash", str(self.root / "code/environment/setup.sh")] + list(args),
                              cwd="/", env=self.env, capture_output=True, text=True)

    def test_prepare_finds_root_and_does_not_launch(self):
        result = self.run_setup("--prepare")
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.log.read_text()
        self.assertIn("<sync>", commands)
        for flag in ("--locked", "--all-extras", "--all-groups", "--managed-python"):
            self.assertIn("<" + flag + ">", commands)
        self.assertIn("env=" + str(self.root / ".venv") + " active= args=", commands)
        self.assertIn("<data3001-py312>", commands)
        self.assertIn("<DATA3001 (Python 3.12)>", commands)
        self.assertNotIn("<jupyterlab>", commands)

    def test_launch_uses_project_python_and_absolute_notebook(self):
        result = self.run_setup("--launch")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<" + str(self.root / "code/environment/launch.py") + ">", self.log.read_text())

    def test_missing_apple_tools_opens_system_installer_before_python_setup(self):
        self.executable("xcrun", '#!/bin/sh\nexit 1\n')
        result = self.run_setup("--prepare")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requested-apple-tools', self.log.read_text())
        self.assertNotIn('<sync>', self.log.read_text())
        self.assertIn('START_HERE.command', result.stderr)

    def test_missing_lock_stops_before_installation(self):
        (self.root / "uv.lock").unlink()
        result = self.run_setup("--prepare")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("uv.lock", result.stderr)
        self.assertFalse(self.log.exists())

    def test_non_pinned_python_stops_before_installation(self):
        (self.root / ".python-version").write_text("3.12\n")
        result = self.run_setup("--prepare")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_unsupported_platform_stops_before_installation(self):
        self.executable("uname", "#!/bin/sh\necho Linux\n")
        result = self.run_setup("--prepare")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("macOS", result.stderr)
        self.assertFalse(self.log.exists())

    def test_intel_macos_stops_before_downloads(self):
        self.executable("uname", '#!/bin/sh\ncase "$1" in -s) echo Darwin;; -m) echo x86_64;; esac\n')
        result = self.run_setup("--prepare")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Apple Silicon", result.stderr)
        self.assertFalse(self.log.exists())

    def test_macos_13_stops_before_downloads(self):
        self.executable("sw_vers", '#!/bin/sh\necho 13.7\n')
        result = self.run_setup("--prepare")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("macOS 14", result.stderr)
        self.assertFalse(self.log.exists())

    def test_python_environment_overrides_are_cleared_for_prepare_and_launch(self):
        self.env.update(PYTHONPATH="/outside/project", PYTHONHOME="/outside/python")
        result = self.run_setup("--launch")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("/outside/", self.log.read_text())

    def test_sync_failure_prevents_kernel_registration_and_launch(self):
        self.executable("uv", '#!/bin/sh\nif [ "$1" = "--version" ]; then echo "uv 0.13.9"; exit 0; fi\nexit 42\n')
        result = self.run_setup("--launch")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / ".venv").exists())

    def test_help_and_invalid_arguments_do_not_install(self):
        self.assertEqual(self.run_setup("--help").returncode, 0)
        self.assertNotEqual(self.run_setup("--unknown").returncode, 0)
        self.assertFalse(self.log.exists())

    def test_absent_uv_bootstraps_official_pinned_version_without_python(self):
        shutil.copy2(self.bin / "uv", self.root / "downloaded-uv")
        (self.bin / "uv").unlink()
        self.executable("curl", '#!/bin/sh\nprintf "download:" >> "$TEST_LOG"\n'
                        'printf "<%s>" "$@" >> "$TEST_LOG"\nprintf "\\n" >> "$TEST_LOG"\n'
                        'while [ "$1" != "--output" ]; do shift; done\nshift\n'
                        'cat > "$1" <<\'INSTALLER\'\n#!/bin/sh\n'
                        'mkdir -p "$UV_UNMANAGED_INSTALL"\ncp "$TEST_ROOT/downloaded-uv" "$UV_UNMANAGED_INSTALL/uv"\n'
                        'INSTALLER\n')
        result = self.run_setup("--prepare")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("<https://astral.sh/uv/0.13.9/install.sh>", self.log.read_text())
        self.assertTrue((self.root / ".tools/uv/0.13.9/uv").is_file())

    def test_wrong_uv_patch_version_is_not_reused(self):
        self.executable("uv", '#!/bin/sh\necho "uv 0.13.90"\n')
        self.executable("curl", '#!/bin/sh\necho "bootstrap attempted" >&2\nexit 41\n')
        result = self.run_setup("--prepare")
        self.assertIn("bootstrap attempted", result.stderr)

    def test_preparation_record_must_describe_an_installed_environment(self):
        self.executable("uv", '#!/bin/sh\nif [ "$1" = "--version" ]; then echo "uv 0.13.9"; exit 0; fi\n'
                        'if [ "$1" = "sync" ]; then exit 45; fi\n')
        result = self.run_setup("--prepare")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / ".venv/.data3001-environment.json").exists())


if __name__ == "__main__":
    unittest.main()
