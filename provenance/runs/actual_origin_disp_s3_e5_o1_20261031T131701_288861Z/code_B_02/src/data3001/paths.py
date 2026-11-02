"""Explicit asset locations and safe run boundaries; no acquisition side effects."""
from __future__ import annotations

from functools import lru_cache, wraps
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


class ProjectPaths:
    def __init__(self, root: Path, data_root: Path | None = None):
        self.root = Path(root).resolve()
        self.data_root = Path(data_root).resolve() if data_root else self.root / 'data'
        self.catalog = json.loads((self.root / 'configs/assets.json').read_text())
        if self.catalog['schema_version'] != 1:
            raise ValueError('Unsupported asset catalog schema')
        self._legacy = None

    def _test_partition(self,path:Path)->bool:
        if (path.is_relative_to(self.data_root/'test') or
            path.is_relative_to(self.data_root/'restricted_test')):
            return True
        return path.is_relative_to(self.root) and 'restricted_test' in path.relative_to(self.root).parts

    def _resolve(self, relative: str) -> Path:
        rel = Path(relative)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Asset path must be project-relative without traversal')
        base = self.data_root if rel.parts and rel.parts[0] == 'data' else self.root
        suffix = Path(*rel.parts[1:]) if base == self.data_root else rel
        destination = (base / suffix).resolve()
        if not destination.is_relative_to(base):
            raise ValueError('Asset symlink escapes its configured root')
        return destination

    def asset(self, asset_id: str, *, allow_test: bool = False, verify: bool = False,
              must_exist: bool = True) -> Path:
        item = self.catalog['assets'][asset_id]
        if item.get('split') == 'test' and not allow_test:
            raise PermissionError('Final-test labels remain locked for model selection')
        path = self._resolve(item['path'])
        if self._test_partition(path) and not allow_test:
            raise PermissionError('Asset alias resolves to a locked final-test partition')
        if must_exist and not path.exists():
            raise FileNotFoundError(f'Asset {asset_id!r} is absent: {path}')
        if verify:
            if item.get('kind') != 'file' or not item.get('sha256'):
                raise ValueError('Use the frozen inventory for directory verification')
            if file_sha256(path) != item['sha256']:
                raise ValueError(f'Asset checksum mismatch: {asset_id}')
        return path

    def legacy(self, *parts: str, allow_test: bool = False) -> Path:
        """Resolve preserved historical relative paths without rewriting receipts."""
        relative = Path(*parts).as_posix()
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Historical path must be relative')
        if 'restricted_test' in Path(relative).parts and not allow_test:
            raise PermissionError('Final-test partitions require explicit access')
        if self._legacy is None:
            self._legacy = json.loads((self.root / 'configs/legacy_paths.json').read_text())
        mapping = self._legacy['file_map']
        def destination(value):
            path = self._resolve(value)
            if self._test_partition(path) and not allow_test:
                raise PermissionError('Historical alias resolves to a locked final-test partition')
            return path
        if relative in mapping:
            return destination(mapping[relative])
        directories = self._legacy['directory_map']
        if relative in directories:
            return destination(directories[relative])
        # An existing mapped directory can contain a requested child. This does
        # not authorise writes or silently select between different snapshots.
        parents = sorted(directories, key=len, reverse=True)
        for parent in parents:
            if relative.startswith(parent + '/'):
                return destination(directories[parent] + relative[len(parent):])
        raise KeyError(f'Unregistered historical path: {relative}')

    def output(self, path: str | Path) -> Path:
        destination = Path(path)
        if not destination.is_absolute():
            destination = self.root / destination
        if destination.is_symlink():
            raise FileExistsError('An output symlink already occupies the destination')
        destination = destination.resolve()
        allowed = [self.root / 'results/runs', self.root / 'provenance/runs',
                   self.root / 'provenance/migrations']
        if not any(destination.is_relative_to(base) and destination != base for base in allowed):
            raise PermissionError('Frozen inputs/history cannot be overwritten; use a new run')
        if destination.exists():
            raise FileExistsError(f'Refusing to overwrite an existing run artifact: {destination}')
        return destination

    def publish(self, path: str | Path, writer) -> Path:
        """Publish one complete new artifact without truncating or replacing another."""
        destination = self.output(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.' + destination.name + '.',
                                                 suffix='.tmp', dir=destination.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                writer(stream)
                stream.flush()
                os.fsync(stream.fileno())
            self.output(destination)
            # Same-directory hard-link publication is atomic and fails if the
            # final name already exists. Never use replace() for a run artifact.
            os.link(temporary, destination)
            return destination
        finally:
            Path(temporary).unlink(missing_ok=True)

    def create_run(self, run_id: str, config: dict) -> dict[str, Path]:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', run_id):
            raise ValueError('Run ID must be a safe single path component')
        # Validate both namespaces before creating either directory. Resolving
        # a symlink must never route the initial run receipt into frozen data.
        results = self.output(self.root / 'results/runs' / run_id)
        provenance = self.output(self.root / 'provenance/runs' / run_id)
        provenance.mkdir(parents=True, exist_ok=False)
        try:
            results.mkdir(parents=True, exist_ok=False)
        except Exception:
            provenance.rmdir()
            raise
        with (provenance / 'run.json').open('x') as stream:
            json.dump({'run_id': run_id, 'created_UTC': datetime.now(timezone.utc).isoformat(),
                       'config': config, 'catalog_sha256': file_sha256(self.root / 'configs/assets.json')},
                      stream, indent=2)
            stream.write('\n')
        return {'results': results, 'provenance': provenance}


@lru_cache(maxsize=1)
def project_paths() -> ProjectPaths:
    root = Path(os.environ.get('DATA3001_PROJECT_ROOT', Path(__file__).resolve().parents[2]))
    data_root = os.environ.get('DATA3001_DATA_ROOT')
    return ProjectPaths(root, Path(data_root) if data_root else None)


def legacy_path(*parts: str, allow_test: bool = False) -> Path:
    return project_paths().legacy(*parts, allow_test=allow_test)


def asset_path(asset_id: str, **kwargs) -> Path:
    return project_paths().asset(asset_id, **kwargs)


def ensure_output_path(path: str | Path) -> Path:
    return project_paths().output(path)


def frozen_action(function):
    """Retain historical algorithms but reject mutation of their frozen run."""
    @wraps(function)
    def protected(*args, **kwargs):
        raise PermissionError(
            f'{function.__name__} targets a frozen historical run. '
            'Create and validate a separate data/run version before rebuilding; '
            'the archived source and checkpoints retain the original execution identity.'
        )
    return protected
