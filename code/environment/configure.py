"""Install locked packages into the Python already running this notebook.

Python installation and editor/kernel selection are outside this entry. Only
dependency preparation and small synthetic environment checks run here.
"""
import hashlib
import importlib
import importlib.metadata
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
import zipfile


UV_VERSION = '0.13.9'
# Published Apple Silicon wheel, verified against PyPI's version metadata.
UV_WHEEL_URL = ('https://files.pythonhosted.org/packages/f3/a7/'
                'a8d7b074798c7fb3b26b37584b8fe2e29df2ccdc24ce7902caab2a53edbf/'
                'uv-0.13.9-py3-none-macosx_11_0_arm64.whl')
UV_WHEEL_SHA256 = '66c512266d633bef48384a1f53003f41f2a8e7b36fe6e7fbfd3e0fd52d96fa63'


def _run(arguments, *, cwd, env=None):
    subprocess.run(list(map(str, arguments)), cwd=cwd, env=env, check=True)


def ensure_uv(root):
    """Keep the package installer in .tools; do not install another Python."""
    directory = root / '.tools' / 'uv' / UV_VERSION
    executable = directory / 'uv'
    if not executable.is_file():
        print('Preparing the package installer...', flush=True)
        with urllib.request.urlopen(UV_WHEEL_URL, timeout=60) as response:
            package = response.read()
        if hashlib.sha256(package).hexdigest() != UV_WHEEL_SHA256:
            raise RuntimeError('The package installer download failed its checksum check.')
        with zipfile.ZipFile(io.BytesIO(package)) as wheel:
            binary = wheel.read('uv-' + UV_VERSION + '.data/scripts/uv')
        directory.mkdir(parents=True, exist_ok=True)
        executable.write_bytes(binary)
        executable.chmod(0o755)
    version = subprocess.check_output([str(executable), '--version'], text=True).split()
    if version[:2] != ['uv', UV_VERSION]:
        raise RuntimeError('The package installer must be uv ' + UV_VERSION)
    return executable


def install_packages(root, uv):
    """Respect the lock and target this executable, regardless of its location."""
    python = ['--python', sys.executable, '--no-python-downloads']
    with tempfile.TemporaryDirectory(prefix='data3001-requirements-') as temporary:
        requirements = Path(temporary) / 'requirements.txt'
        _run([uv, 'export', '--project', root, '--locked', '--all-extras', '--all-groups',
              '--no-emit-project', '--format', 'requirements.txt', '--output-file', requirements,
              '--quiet', *python], cwd=root)
        # install, rather than sync, preserves unrelated packages in this Python.
        _run([uv, 'pip', 'install', '--require-hashes', '--requirements', requirements,
              *python], cwd=root)
        _run([uv, 'pip', 'install', '--no-deps', '--editable', root, *python], cwd=root)


def check_loaded_versions(before, after):
    changed = sorted(name for name, version in before.items() if after.get(name) != version)
    if changed:
        raise RuntimeError(
            'Packages were installed successfully. Restart the current notebook kernel, '
            'then run this configuration cell again. Updated packages already in memory: '
            + ', '.join(changed)
        )


def configure(project_root=None):
    """Prepare the current Python and return its verification record."""
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError('This project requires an existing Python 3.12 notebook environment. '
                           'This cell installs packages only.')
    root = Path(project_root).resolve() if project_root else Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('data3001_package_checks', root / 'code/environment/check.py')
    checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks)
    if not checks._platform_status()['supported']:
        raise RuntimeError('The original scientific code supports Apple Silicon, macOS 14 or later.')
    for name in ('pyproject.toml', 'uv.lock'):
        if not (root / name).is_file():
            raise FileNotFoundError('Missing dependency configuration: ' + name)

    installed_before = checks._installed_packages()
    loaded = {checks._name(distribution): installed_before.get(checks._name(distribution))
              for module, distributions in importlib.metadata.packages_distributions().items()
              if module in sys.modules for distribution in distributions}
    print('Python:', sys.executable, '(' + '.'.join(map(str, sys.version_info[:3])) + ')', flush=True)
    print('Installing/checking the versions in uv.lock...', flush=True)
    install_packages(root, ensure_uv(root))
    importlib.invalidate_caches()
    installed = checks._installed_packages()
    check_loaded_versions(loaded, installed)

    errors = []
    dependencies = checks._check_dependencies(root, installed, errors)
    libraries = checks._native_library_probe(sys.executable, root, environment_prefix=sys.prefix)
    compiler = checks._compiler_probe()
    for result in (libraries, compiler):
        if not result['ok']:
            errors.append(result['error'])
    if errors:
        raise RuntimeError('Environment check failed:\n' + '\n'.join(errors))

    # A newly installed editable package's .pth takes effect in child processes
    # immediately; expose the same source to this already-running kernel too.
    for directory in (root / 'code/shared/_compat', root / 'code'):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    report = {'ok': True, 'python': sys.executable,
              'python_version': '.'.join(map(str, sys.version_info[:3])),
              'packages': dependencies['installed'], 'libraries': libraries,
              'compiler': compiler,
              'manifests': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                            for name in ('pyproject.toml', 'uv.lock')}}
    record = root / '.tools/notebook_environment.json'
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('Dependencies ready. Numerical-library and compiler checks passed.', flush=True)
    return report


if __name__ == '__main__':
    configure()
