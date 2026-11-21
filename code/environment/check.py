"""Read-only environment diagnosis, callable from an old notebook kernel or CLI.

The initial diagnosis uses only the standard library, including on old Python.
Native libraries are tested in a bounded project-Python subprocess with tiny
synthetic inputs. The compiler probe builds only in a temporary directory.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys
import tempfile


NATIVE_LIBRARIES = ("numpy", "pandas", "pyarrow", "scipy", "torch", "shapely", "pyproj", "netCDF4", "h5py")


def _platform_status():
    release = platform.mac_ver()[0]
    major = release.split(".")[0]
    supported = (platform.system() == "Darwin" and platform.machine() == "arm64"
                 and major.isdigit() and int(major) >= 14)
    return {"system": platform.system(), "machine": platform.machine(),
            "macos_version": release, "supported": supported}


def _within(path, directory):
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
        return True
    except (ValueError, TypeError):
        return False


def _check_module_origins(root, errors):
    """Inspect the current kernel's import resolution without loading native code."""
    origins = {}
    for name in NATIVE_LIBRARIES + ("data3001",):
        try:
            loaded = sys.modules.get(name)
            if loaded is not None:
                origin = getattr(loaded, "__file__", None)
            else:
                spec = importlib.util.find_spec(name)
                origin = spec.origin if spec is not None else None
            origins[name] = origin
            if not origin:
                errors.append("Cannot locate required module: " + name)
            elif name == "data3001":
                expected = (root / "code/shared/_compat/data3001/__init__.py").resolve()
                if Path(origin).resolve() != expected:
                    errors.append("data3001 resolves outside the canonical project source: " + origin)
            elif not _within(origin, root / ".venv"):
                errors.append(name + " resolves outside the project .venv: " + origin)
        except (ImportError, ValueError, AttributeError) as error:
            errors.append("Cannot inspect module {0}: {1}".format(name, error))
    return origins


def _probe_environment(directory):
    environment = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(name, None)
    environment.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(directory),
                       XDG_CACHE_HOME=str(Path(directory) / "cache"), PROJ_NETWORK="OFF",
                       OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1")
    return environment


def _native_library_probe(project_python, root, environment_prefix=None):
    # All inputs are literal in-memory values. No project datasets or model code
    # are imported; no optimizers, fitting, GPU device selection or downloads run.
    source = r'''
import importlib
import io
import json
from pathlib import Path
import sys
import time

venv = Path(sys.argv[1]).resolve()
checks = {
    "numpy": "assert float(module.dot([1., 2.], [3., 4.])) == 11.0",
    "pandas": "assert int(module.Series([1, 2, 3]).sum()) == 6",
    "pyarrow": "from pyarrow import compute; assert compute.sum(module.array([1, 2, 3])).as_py() == 6",
    "scipy": "from scipy.linalg import solve; import numpy as np; assert np.allclose(solve([[2., 0.], [0., 4.]], [2., 8.]), [1., 2.])",
    "torch": "module.set_num_threads(1); assert module.dot(module.tensor([1., 2.], device='cpu'), module.tensor([3., 4.], device='cpu')).item() == 11.0",
    "shapely": "from shapely.geometry import box; assert box(0, 0, 2, 2).intersection(box(1, 1, 3, 3)).area == 1.0",
    "pyproj": "point = module.Transformer.from_crs(4326, 3857, always_xy=True).transform(0., 0.); assert max(abs(value) for value in point) < 1e-8",
    "netCDF4": "with module.Dataset('native-smoke', 'w', diskless=True, persist=False) as data:\n data.createDimension('n', 2)\n value = data.createVariable('value', 'f8', ('n',))\n value[:] = [1., 2.]\n assert float(value[:].sum()) == 3.0",
    "h5py": "with module.File(io.BytesIO(), 'w') as data:\n value = data.create_dataset('value', data=[1., 2.])\n assert float(value[:].sum()) == 3.0",
}
results = {}
for name, check in checks.items():
    started = time.monotonic()
    print("Checking " + name, file=sys.stderr, flush=True)
    try:
        module = importlib.import_module(name)
        origin = Path(module.__file__).resolve()
        origin.relative_to(venv)
        exec(check, {"module": module, "io": io})
        results[name] = {"ok": True, "version": getattr(module, "__version__", None), "path": str(origin)}
    except Exception as error:
        results[name] = {"ok": False, "error": type(error).__name__ + ": " + str(error)}
    results[name]["elapsed_seconds"] = round(time.monotonic() - started, 4)
    print(name + ": " + str(results[name]), file=sys.stderr, flush=True)
print(json.dumps({"ok": all(item["ok"] for item in results.values()), "libraries": results}))
'''
    try:
        with tempfile.TemporaryDirectory(prefix="data3001-native-") as directory:
            completed = subprocess.run(
                [str(project_python), "-I", "-B", "-c", source,
                 str(environment_prefix or root / ".venv")],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                timeout=120, cwd=directory, env=_probe_environment(directory),
            )
        if completed.returncode != 0:
            return {"ok": False, "error": "Native subprocess failed: " + completed.stderr[-2000:]}
        result = json.loads(completed.stdout)
        if not result["ok"]:
            result["error"] = "; ".join(name + ": " + item["error"]
                                         for name, item in result["libraries"].items() if not item["ok"])
        return result
    except subprocess.TimeoutExpired as error:
        progress = error.stderr or ""
        if isinstance(progress, bytes):
            progress = progress.decode("utf-8", errors="replace")
        return {"ok": False, "error": "Native library smoke check timed out after 120 seconds. " + progress[-2000:]}
    except (OSError, ValueError, KeyError) as error:
        return {"ok": False, "error": "Native library smoke check failed: " + str(error)}


def _compiler_probe():
    """Check the selected macOS SDK and compile/link/run a two-element BLAS call."""
    try:
        with tempfile.TemporaryDirectory(prefix="data3001-compiler-") as directory:
            environment = _probe_environment(directory)
            environment["CLANG_MODULE_CACHE_PATH"] = str(Path(directory) / "clang-cache")

            def run(command, timeout=5):
                completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           universal_newlines=True, timeout=timeout, cwd=directory, env=environment)
                if completed.returncode != 0:
                    raise RuntimeError(completed.stderr[-2000:] or "Command failed: " + command[0])
                return completed.stdout.strip()

            compiler = run(["xcrun", "--find", "clang++"])
            sdk = run(["xcrun", "--sdk", "macosx", "--show-sdk-path"])
            source = Path(directory) / "accelerate_smoke.cpp"
            executable = Path(directory) / "accelerate_smoke"
            source.write_text(
                '#include <Accelerate/Accelerate.h>\n#include <cmath>\n'
                'int main() { double x[2]={1.,2.}, y[2]={3.,4.}; '
                'return std::abs(cblas_ddot(2,x,1,y,1)-11.) < 1e-12 ? 0 : 1; }\n',
                encoding="utf-8",
            )
            run([compiler, "-std=c++17", "-ffp-contract=off", "-isysroot", sdk,
                 str(source), "-framework", "Accelerate", "-o", str(executable)], timeout=10)
            run([str(executable)])
        return {"ok": True, "compiler": compiler, "sdk": sdk, "accelerate": "compile/link/run passed"}
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "error": "C++17 / Apple Accelerate check failed. Install or select Apple's Command Line Tools and macOS SDK: " + str(error)}


def _name(value):
    return re.sub(r"[-_.]+", "-", value).lower()


def _installed_packages():
    try:
        from importlib import metadata
    except ImportError:
        return None
    return {_name(item.metadata["Name"]): item.version
            for item in metadata.distributions() if item.metadata["Name"]}


def _read_toml(path, errors):
    try:
        import tomllib
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, ValueError) as error:
        errors.append("Cannot read {0}: {1}".format(path.name, error))
        return {}


def _check_dependencies(root, installed, errors):
    project = _read_toml(root / "pyproject.toml", errors)
    lock = _read_toml(root / "uv.lock", errors)
    declared = list(project.get("project", {}).get("dependencies", []))
    for dependencies in project.get("project", {}).get("optional-dependencies", {}).values():
        declared.extend(dependencies)
    for dependencies in project.get("dependency-groups", {}).values():
        declared.extend(value for value in dependencies if isinstance(value, str))
    locked = {}
    for package in lock.get("package", []):
        if "name" in package and "version" in package:
            locked.setdefault(_name(package["name"]), set()).add(package["version"])
    required = set()
    for requirement in declared:
        match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement)
        if match:
            required.add(_name(match.group()))
    for package in sorted(required):
        if package not in installed:
            errors.append("Missing declared dependency: " + package)
        elif package not in locked:
            errors.append("Declared dependency missing from uv.lock: " + package)
    for package, version in sorted(installed.items()):
        if package in locked and version not in locked[package]:
            errors.append("Dependency differs from uv.lock: {0} is {1}; locked: {2}".format(
                package, version, ", ".join(sorted(locked[package]))))
    return {"declared": sorted(required), "installed": installed,
            "locked_package_count": len(locked)}


def check_environment(project_root=None, verbose=True, inspect_project=True):
    """Return diagnosis for this process and the project's .venv, without changes.

    ``ok`` is true only when this process is the prepared project interpreter.
    A ready project environment therefore does not hide a wrong notebook kernel.
    """
    root = Path(project_root).resolve() if project_root is not None else Path(__file__).resolve().parents[2]
    venv = root / ".venv"
    project_python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    version = ".".join(str(part) for part in sys.version_info[:3])
    is_project = Path(sys.prefix).resolve() == venv.resolve()
    report = {
        "ok": False, "root": str(root), "setup_path": str(root / "code/environment/setup.sh"),
        "current": {"executable": sys.executable, "version": version,
                    "prefix": sys.prefix, "is_project_venv": is_project},
        "project": {"path": str(venv), "python": str(project_python), "exists": project_python.is_file()},
        "metadata": {}, "dependencies": {}, "module_origins": {},
        "platform": _platform_status(), "native": {}, "errors": [], "warnings": [],
    }
    errors, warnings = report["errors"], report["warnings"]
    try:
        pin = (root / ".python-version").read_text(encoding="utf-8").strip()
    except OSError:
        pin = ""
    report["metadata"]["python_pin"] = pin
    if not re.fullmatch(r"3\.12\.[0-9]+", pin):
        errors.append("Missing or invalid .python-version; pin a Python 3.12 patch release.")
    elif version != pin:
        errors.append("Current Python is {0}; required Python is {1}.".format(version, pin))
    if not is_project:
        errors.append("Current notebook kernel/interpreter is not the project .venv. Select DATA3001 (Python 3.12).")
    if not report["platform"]["supported"]:
        errors.append("The locked environment requires native Apple Silicon (arm64) and macOS 14 or later; Intel, Rosetta and other platforms are unsupported.")
    for name in ("pyproject.toml", "uv.lock"):
        if not (root / name).is_file():
            errors.append("Missing environment authority: " + name)

    installed = _installed_packages()
    if sys.version_info[:2] >= (3, 11) and installed is not None:
        report["dependencies"] = _check_dependencies(root, installed, errors)
    else:
        warnings.append("Full TOML/dependency checks require the prepared Python 3.12 environment.")

    record_path = venv / ".data3001-environment.json"
    record = {}
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("schema") != 1:
            raise ValueError("unsupported preparation record")
    except (OSError, ValueError) as error:
        errors.append("Environment preparation metadata is missing or invalid: {0}".format(error))
        record = {}
    report["metadata"]["prepared"] = bool(record)
    report["metadata"]["uv_version"] = record.get("uv_version")
    if record:
        if record.get("python_pin") != pin:
            errors.append("Prepared Python pin differs from .python-version.")
        for name in ("pyproject.toml", "uv.lock", ".python-version"):
            try:
                digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
            except OSError:
                continue
            if record.get("manifests", {}).get(name) != digest:
                errors.append(name + " changed since environment preparation; rerun --prepare.")
        if is_project and installed is not None:
            prepared_packages = record.get("packages", {})
            for name, expected in sorted(prepared_packages.items()):
                if installed.get(name) != expected:
                    errors.append("Prepared dependency changed: {0}; expected {1}, found {2}.".format(
                        name, expected, installed.get(name, "missing")))
            for name in sorted(set(installed) - set(prepared_packages)):
                errors.append("Dependency added after environment preparation: " + name)
    if not project_python.is_file():
        errors.append("Project .venv Python is missing; run the shared setup entry.")
    elif is_project and report["platform"]["supported"]:
        report["module_origins"] = _check_module_origins(root, errors)
        report["native"]["libraries"] = _native_library_probe(project_python, root)
        report["native"]["compiler"] = _compiler_probe()
        for result in report["native"].values():
            if not result["ok"]:
                errors.append(result["error"])
    elif inspect_project and not is_project:
        try:
            completed = subprocess.run(
                [str(project_python), "-I", "-B", str(Path(__file__).resolve()), "--root", str(root), "--json", "--local-only"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=150,
                env={name: value for name, value in dict(os.environ, PYTHONDONTWRITEBYTECODE="1").items()
                     if name not in ("PYTHONPATH", "PYTHONHOME")},
            )
            report["project"]["diagnosis"] = json.loads(completed.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            errors.append("Cannot inspect the project interpreter: {0}".format(error))
    warnings.append("Native checks use tiny synthetic CPU operations and temporary compiler outputs; they do not run experiments or validate scientific results.")
    report["ok"] = not errors
    if verbose:
        print("Current Python: {0} ({1})".format(sys.executable, version))
        print("Project Python: " + str(project_python))
        print("Required Python: " + (pin or "not pinned"))
        print("Platform: {0} {1}, macOS {2}".format(report["platform"]["system"], report["platform"]["machine"], report["platform"]["macos_version"]))
        print("Environment: " + ("ready" if report["ok"] else "needs preparation or the correct kernel"))
        for name, result in report["native"].items():
            print("Native {0}: {1}".format(name, "passed" if result["ok"] else "failed"))
        for error in errors:
            print("ERROR: " + error)
        for warning in warnings:
            print("NOTE: " + warning)
        if "diagnosis" in report["project"]:
            print("Project environment checked separately: " + ("ready" if report["project"]["diagnosis"]["ok"] else "not ready"))
        if errors:
            print("Prepare in Terminal: bash {0} --prepare".format(shlex.quote(report["setup_path"])))
            print("Then select DATA3001 (Python 3.12) and restart the notebook kernel.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="Project root (defaults to the location of this script).")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable diagnosis.")
    parser.add_argument("--local-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    report = check_environment(args.root, verbose=not args.json, inspect_project=not args.local_only)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
