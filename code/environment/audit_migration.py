"""Verify migrated source identities and retained archive metadata without edits."""
from pathlib import Path
import argparse
import hashlib
import json
import os


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def audit(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'docs/migration_manifest.json').read_text())
    bad, file_count, directory_count = [], 0, 0
    for item in manifest['files']:
        original, target = root / item['source'], root / item['target']
        if item['kind'] == 'file':
            file_count += 1
            if not target.is_file() or digest(target) != item['sha256']:
                bad.append({'path': item['target'], 'reason': 'missing or changed target'})
            if not original.is_file() or digest(original) != item['sha256']:
                bad.append({'path': item['source'], 'reason': 'missing or changed original/alias'})
        else:
            directory_count += 1
            if not target.is_dir() or not original.is_dir() or original.resolve() != target.resolve():
                bad.append({'path': item['source'], 'reason': 'directory alias mismatch'})
    before_path = root / 'provenance/migrations/code_delivery_20261122/archive_before.json'
    before = json.loads(before_path.read_text())
    baseline = {row[0]: row[1:] for row in before}
    current = {}
    for base, directories, files in os.walk(root / 'archive', followlinks=False):
        for name in files:
            path = Path(base) / name
            state = path.lstat()
            current[path.relative_to(root).as_posix()] = [state.st_size, state.st_mtime_ns,
                os.readlink(path) if path.is_symlink() else None]
    changed = [path for path in sorted(set(baseline) | set(current)) if baseline.get(path) != current.get(path)]
    return {'passed': not bad and not changed, 'migrated_files': file_count,
            'migrated_directories': directory_count, 'source_mismatches': bad,
            'archive_entries_checked': len(baseline), 'archive_current_entries': len(current),
            'archive_changed_entries': changed,
            'archive_check_scope': 'file inventory, size, modification time and file-symlink target, matching the pre-migration inventory; no archived data content read'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(Path(__file__).resolve().parents[2])
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text)
    raise SystemExit(0 if result['passed'] else 1)
