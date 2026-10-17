"""Read-only verification of original assets after an architecture migration."""
from pathlib import Path
import ast
import json
import os
import time
from data3001.paths import file_sha256, project_paths


def verify_inventory(root, entries):
    root = Path(root).resolve()
    mismatches = []
    checked = 0
    total_bytes = 0
    for entry in entries:
        rel = Path(entry['destination'])
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Invalid inventory destination')
        path = root / rel
        problem = None
        if entry['kind'] == 'symlink':
            if not path.is_symlink() or os.readlink(path) != entry['target']:
                problem = 'missing or changed symlink'
        elif not path.is_file() or path.is_symlink():
            problem = 'missing file or changed object type'
        elif path.stat().st_size != entry['bytes'] or file_sha256(path) != entry['sha256']:
            problem = 'size or SHA256 mismatch'
        else:
            total_bytes += entry['bytes']
        if problem:
            mismatches.append({'original': entry['path'], 'destination': entry['destination'],
                               'problem': problem})
        checked += 1
    return {'passed': not mismatches, 'checked_entries': checked,
            'verified_file_bytes': total_bytes, 'mismatches': mismatches}


def scientific_equivalence(root):
    """Compare scientific function ASTs against the exact pre-migration code."""
    root = Path(root)
    functions = {
        'prep_core': None,
        'rules': None,
        'prep_run': ['clean_track'],
        'prep_pairs': ['origin_indices', 'generate'],
        'prep_geometry': ['water_ok', 'domain_cell_ranges'],
        'prep_handover': ['polygon_area_km2', 'region_area_fields', 'release_weights',
                          'depth_stratum', 'support_summary', 'batched_summary', 'position_census'],
        'prep_peers': ['screen_score'],
        'prep_support': ['part'],
    }
    comparisons = []
    mismatches = []
    for module, names in functions.items():
        original = root / 'provenance/frozen/acquisition/scripts' / (module + '.py')
        stage = 'acquisition' if module == 'rules' else 'preprocessing'
        current = root / 'src/data3001' / stage / (module + '.py')
        old = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(original.read_text()).body
               if isinstance(n, ast.FunctionDef)}
        new = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(current.read_text()).body
               if isinstance(n, ast.FunctionDef)}
        for name in names if names is not None else old:
            equal = old[name] == new.get(name)
            comparisons.append({'module': module, 'function': name, 'equal': equal})
            if not equal:
                mismatches.append(module + '.' + name)
    # Pure scientific modules also retain their original constants, not merely
    # their function bodies. This catches changed thresholds/reason codes.
    for module in ['prep_core', 'rules']:
        stage = 'acquisition' if module == 'rules' else 'preprocessing'
        old_tree = ast.parse((root / 'provenance/frozen/acquisition/scripts' / (module+'.py')).read_text())
        new_tree = ast.parse((root / 'src/data3001' / stage / (module+'.py')).read_text())
        assignments = lambda tree: [ast.dump(n, include_attributes=False) for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
        if assignments(old_tree) != assignments(new_tree):
            mismatches.append(module + '.constants')
    return {'passed': not mismatches, 'functions_checked': len(comparisons),
            'comparisons': comparisons, 'mismatches': mismatches}


def verify_current_assets():
    """Technical identity checks only; no held-out scoring or policy selection."""
    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq
    from data3001.preprocessing.prep_io import Source
    paths = project_paths()
    checked = 0
    for asset_id, item in paths.catalog['assets'].items():
        paths.asset(asset_id, allow_test=True, verify=item['kind'] == 'file')
        checked += 1
    source = Source()
    source_receipt = source.verify()
    assert source_receipt['IDs'] == 3741 and source_receipt['rows'] == 39107061
    assert source_receipt['R_IDs'] == 463
    assert source_receipt['split_counts'] == {'train':2674,'validation':550,'test':517}
    old = pd.read_parquet(paths.asset('baseline_state_index'))
    current = pd.read_parquet(paths.asset('state_index'))
    pd.testing.assert_frame_equal(current[old.columns], old)
    for _, part in current.groupby('resolution'):
        assert np.isclose(part.whole_R_release_weight.sum(), 1, rtol=0, atol=1e-12)
        assert (part.loc[part.wet_area_in_R == 0, 'whole_R_release_weight'] == 0).all()
    assert 'target' in pq.read_schema(paths.asset('lag_support')).names
    assert 'target' not in pq.read_schema(paths.asset('baseline_lag_support')).names
    assert paths.asset('lag_support') != paths.asset('baseline_lag_support')
    return {'passed':True, 'catalog_assets_checked':checked, 'source':source_receipt,
            'augmented_index_preserves_baseline_columns':True,
            'baseline_and_current_lag_schemas_distinct':True,
            'forecast_accuracy_evaluated':False,
            'depth_policy':'DEPTH-01 remains pending',
            'annual_seasonal_limits':'retained; migration does not add evidence'}


def verify_all():
    paths = project_paths()
    if paths.catalog.get('layout_version') == 'per-drifter-cleaned-1.3':
        from data3001.drogue_storage import verify_drogue_release
        return verify_drogue_release(progress=lambda message:print(message,flush=True))
    if paths.catalog.get('layout_version') == 'per-drifter-cleaned-1.2':
        from data3001.grounding_sst import verify_grounding_sst_release
        return verify_grounding_sst_release(progress=lambda message:print(message,flush=True))
    if paths.catalog.get('layout_version') == 'per-drifter-cleaned-1.1':
        from data3001.sst_storage import verify_sst_release
        return verify_sst_release(progress=lambda message:print(message,flush=True))
    if paths.catalog.get('layout_version') == 'per-drifter-cleaned-1.0':
        from data3001.recovery_storage import verify_cleaned_release
        return verify_cleaned_release()
    if paths.catalog.get('layout_version') == 'per-drifter-1.0':
        from data3001.release_verification import verify_release
        return verify_release()
    started = time.monotonic()
    inventory_path = paths.root / 'provenance/migrations/architecture_20261014/path_map.json'
    inventory = json.loads(inventory_path.read_text())
    inventory_result = verify_inventory(paths.root, inventory['entries'])
    if not inventory_result['passed']:
        return {'passed':False, 'inventory':inventory_result}
    science = scientific_equivalence(paths.root)
    assets = verify_current_assets()
    return {'passed':science['passed'] and assets['passed'], 'inventory':inventory_result,
            'scientific_equivalence':science, 'assets':assets,
            'inventory_sha256':file_sha256(inventory_path),
            'elapsed_seconds':time.monotonic()-started,
            'scope':'architecture and asset identity; no preprocessing rerun or prediction evaluation'}
