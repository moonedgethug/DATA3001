"""Apply the reviewed delivery mapping without changing scientific source bytes.

The manifest is also the rollback and historical-path index. This tool never
removes archive and leaves relative compatibility links at original locations.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def result_stage(name):
    if name.startswith(('conditional_', 'local_gmm_', 'empirical_b2_', 'adaptive_b2_b1_',
                        'b2_b1_', 'drifter_shrinkage_', 'partial_weighting_', 'spatial_',
                        'local_endpoint_', 'actual_origin_', 'seasonal_', 'temporal_',
                        'departure_direction_', 'exact_origin_', 'position_error_', 'e9_',
                        'b2_grid_')):
        return 'stage2'
    if name.startswith(('baseline_', 'neighbour_', 'regime_', 'markov_', 'continuous_')):
        return 'stage1'
    if name.startswith(('sst_', 'feature_', 'drogue_', 'data_release_', 'boundary_',
                        'migration-', 'temperature_', 'total_sst_', 'modelling_entry_')):
        return 'data_preprocessing'
    return 'report'


def plan(root, source_map):
    mapping = dict(source_map['mapping'])
    mapping.update(source_map['external_code_mapping'])
    mapping.update(source_map['metadata_file_mapping'])
    for p in (root / 'tests').glob('*.py'):
        mapping[str(p.relative_to(root))] = 'code/tests/' + p.name
    metadata = {'assets.json', 'dataset_index.csv', 'dataset_manifest.json',
                'dataset_schema.json', 'feature_review.csv', 'legacy_paths.json',
                'qualification_manifest.json'}
    for p in (root / 'configs').iterdir():
        if not p.is_file() or p.is_symlink():
            continue
        if p.name in metadata:
            target = 'data/metadata/' + p.name
        elif p.suffix == '.json':
            stage = 'stage1' if p.stem.startswith(('markov_', 'continuous_')) else 'stage2'
            target = 'configs/' + stage + '/' + p.name
        else:
            continue
        mapping[str(p.relative_to(root))] = target
    entries = []
    for old, new in sorted(mapping.items()):
        p = root / old
        if not p.is_file():
            raise FileNotFoundError(p)
        entries.append(dict(source=old, target=new, sha256=digest(p),
                            bytes=p.stat().st_size, kind='file', action='move_with_alias'))
    for p in sorted((root / 'results/runs').iterdir()):
        if p.is_symlink():
            continue
        if p.is_dir():
            entries.append(dict(source=str(p.relative_to(root)),
                                target='results/reference/' + result_stage(p.name) + '/' + p.name,
                                kind='directory', action='move_with_alias'))
        elif p.suffix == '.ipynb':
            entries.append(dict(source=str(p.relative_to(root)),
                                target='code/data_preprocessing/cleaning/notebooks/' + p.name,
                                sha256=digest(p), bytes=p.stat().st_size,
                                kind='file', action='move_with_alias'))
    if len({r['target'] for r in entries}) != len(entries):
        raise ValueError('Duplicate migration destination')
    return dict(schema_version=1, status='planned', archive_policy='preserve_unchanged',
                scientific_source_policy='byte_identical; run in materialized historical layout',
                files=entries)


def migrate(root, manifest):
    archive = root / 'provenance/migrations/code_delivery_20261122/before/external'
    for entry in manifest['files']:
        old, new = root / entry['source'], root / entry['target']
        if entry['action'] == 'copy_preserve_archive':
            if not new.exists():
                new.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old, new)
            if digest(old) != entry['sha256'] or digest(new) != entry['sha256']:
                raise ValueError('Preserved archive source or copy changed: ' + entry['source'])
            continue
        if new.is_symlink() and new.resolve() == old.resolve() and not old.is_symlink():
            entry['action'] = 'reference_link_preserve_frozen_location'
            continue
        if old.is_symlink() and old.resolve() == new.resolve() and new.exists():
            continue
        if new.exists() or new.is_symlink():
            raise FileExistsError(new)
        if entry['kind'] == 'file' and digest(old) != entry['sha256']:
            raise ValueError('Source changed: ' + entry['source'])
        if entry['source'].startswith('../'):
            backup = archive / entry['source'][3:]
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old, backup)
        new.parent.mkdir(parents=True, exist_ok=True)
        try:
            old.rename(new)
        except PermissionError:
            if entry['kind'] != 'directory' or not entry['source'].startswith('results/runs/'):
                raise
            # Frozen payloads may deny even a directory rename. Preserve their
            # filesystem protection and index them from the new result layout.
            new.symlink_to(os.path.relpath(old, new.parent), target_is_directory=True)
            entry['action'] = 'reference_link_preserve_frozen_location'
            continue
        old.symlink_to(os.path.relpath(new, old.parent), target_is_directory=entry['kind'] == 'directory')
        if entry['source'].startswith('src/data3001/'):
            package_link = root / 'code/shared/_compat' / entry['source'][4:]
            package_link.parent.mkdir(parents=True, exist_ok=True)
            package_link.symlink_to(os.path.relpath(new, package_link.parent))
    manifest['status'] = 'migrated'
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mapping', type=Path, nargs='?', help='Initial approved map; existing manifest is sufficient on subsequent runs')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    path = root / 'docs/migration_manifest.json'
    if not path.exists() and args.mapping is None:
        parser.error('Provide the approved map for an initial migration')
    manifest = json.loads(path.read_text()) if path.exists() else plan(root, json.loads(args.mapping.read_text()))
    if args.apply:
        manifest = migrate(root, manifest)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'status': manifest['status'], 'entries': len(manifest['files']),
                      'manifest': str(path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
