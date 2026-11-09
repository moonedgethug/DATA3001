"""Read-only result verification and append-only release receipts for this run."""
import time
STARTED = time.monotonic()
import json
from html.parser import HTMLParser
from pathlib import Path
import numpy as np
import pandas as pd
from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_json
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_inputs as inp
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_full as full

NAME = 'conditional_gaussian_s5_e1_full_20261107T061818Z'
paths, run, cfg, approval, guard = inp.context(NAME)
budget = inp.Budget(run, cfg, 'audit', STARTED)
completed = False
try:
    root = run['results']
    full.verify_freeze(run, approval)
    summary = pd.read_csv(root / 'summary.csv').set_index('model')
    metrics = pd.read_parquet(root / 'metrics.parquet')
    parameters = pd.read_parquet(root / 'gaussian_parameters.parquet')
    assert len(metrics) == 33971 * 3 and metrics.id.nunique() == 45
    assert len(parameters) == 33971 and parameters.query_position.is_unique
    assert set(parameters.query_position) == set(metrics.query_position)
    rebuilt = metrics.groupby(['id', 'model'])[['energy_km', 'h90', 'area90_km2']].mean().groupby('model').mean()
    for field in rebuilt.columns:
        np.testing.assert_allclose(rebuilt[field], summary.loc[rebuilt.index, field], rtol=1e-12)
    for field in ['mu_east_km', 'mu_north_km', 'cov_ee_km2', 'cov_en_km2', 'cov_nn_km2']:
        assert np.isfinite(parameters[field]).all()
    assert (parameters.cov_ee_km2 * parameters.cov_nn_km2 - parameters.cov_en_km2 ** 2 > 0).all()
    manifest = json.loads((root / 'model_manifest.json').read_text())
    assert manifest['contract_sha256'] == approval['contract_sha256']
    assert file_sha256(Path(manifest['fitting_coordinates'])) == manifest['fitting_coordinates_sha256']
    for stage in ['parameters', 'regions', 'score', 'audit', 'verify_primary', 'verify_audit', 'full_report']:
        assert json.loads((run['provenance'] / (stage + '_resources.json')).read_text())['completed']
    for check in ['primary_numerical_checks', 'full_independent_checks']:
        assert json.loads((run['provenance'] / (check + '.json')).read_text())['passed']
    decision = json.loads((run['provenance'] / 'scientific_decision.json').read_text())
    assert decision['engineering_complete'] and not decision['model_default_changed']
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.links = []; self.examples = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            self.links.extend(attrs[k] for k in ['href', 'src'] if k in attrs)
            if tag == 'figure' and 'id' in attrs: self.examples.append(attrs['id'])
    document = (root / 'review.html').read_text()
    parser = Links(); parser.feed(document)
    assert len(parser.examples) == 6 and len(set(parser.examples)) == 6
    assert 'function showExample(n)' in document
    for link in parser.links:
        assert '://' not in link and (root / link).is_file(), link
    for model, row in summary.iterrows():
        assert f'{row.energy_km:.6f}' in document
        assert f'{row.h90 * 100:.3f}%' in document
        assert f'{row.area90_km2:,.1f}' in document
    displays = json.loads((run['provenance'] / 'example_display_checks.json').read_text())
    assert len(displays) == 6
    assert all(not r['outcome_used_for_selection'] for r in displays)
    assert all(abs(mass - 1) < 1e-12 for r in displays for mass in r['display_mass'].values())
    receipts = [json.loads(p.read_text()) for p in run['provenance'].glob('*_resources.json')]
    phases = {phase: sum(r['elapsed_seconds'] for r in receipts if r['phase'] == phase)
              for phase in ['pilot', 'formal', 'audit', 'report']}
    phases['audit'] += time.monotonic() - STARTED
    assert all(phases[p] < cfg['seconds'][p] for p in phases)
    assert sum(phases.values()) < cfg['seconds']['total']
    folders = list(run.values()) + [inp.ROOT / part / 'runs' / cfg['parent_pilot_run'] for part in ['results', 'provenance']]
    stored = sum(p.stat().st_size for folder in folders for p in folder.rglob('*') if p.is_file() and not p.is_symlink())
    assert stored < cfg['storage_gib'] * 2 ** 30
    inp.verify(approval)
    qa = dict(passed=True, protected_files_verified=len(approval['protected_files']),
        cases_per_model=33971, evaluation_ids=45, parameters_saved=len(parameters),
        summary_matches_full_per_id_aggregation=True, local_links_checked=len(parser.links),
        six_predetermined_map_masses_sum_to_one=True, source_numbers_match_report=True,
        plots_visually_inspected=['full_comparison.png', 'paired_effects.png', 'per_id_effects.png'] +
            [f'example_{i:02d}.png' for i in range(1, 7)],
        plot_visual_findings='All nine plots inspected; labels, legends and per-example shared scales readable.',
        browser_layout_verified=False,
        browser_note='Local-file browser access was unavailable; no alternate transport used. PNGs and HTML source/links were checked.',
        phases_seconds_before_final_seal=phases, old_and_new_retained_bytes=stored,
        numerical_levels=dict(energy=8192, region_packet=32768), final_test_access=False,
        scientific_decision=decision['decision'], model_definition_changed=False)
    save_json(paths, run['provenance'] / 'final_release_qa.json', qa)
    hashes = {str(p.relative_to(root)): file_sha256(p) for p in sorted(root.rglob('*')) if p.is_file()}
    save_json(paths, run['provenance'] / 'release_manifest.json', dict(run=NAME, result_sha256=hashes,
        contract_sha256=approval['contract_sha256'], resource_only_amendment=True,
        final_test_access=False, complete=True))
    budget.check(); completed = True
    print(json.dumps(qa, ensure_ascii=False))
finally:
    budget.finish(paths, 'final_release', completed, guard)
