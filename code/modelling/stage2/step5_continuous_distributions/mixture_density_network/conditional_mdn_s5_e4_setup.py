"""Initialize the explicitly authorized full K-refinement, without fitting."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from data3001.paths import file_sha256
from .conditional_mdn_s5_e4_runtime import ROOT, atomic_json
from .conditional_mdn_s5_e4_reuse import PARENT_RUN, NEW_KS, PARENT_KS, parent_audit


def prepare(name):
    if Path(name).name != name or not name.startswith('conditional_mdn_s5_e4_'):
        raise ValueError('Invalid refinement run name')
    cfg = json.loads((ROOT/'configs/conditional_mdn_s5_e4.json').read_text())
    parent_prov = ROOT/'provenance/runs'/PARENT_RUN
    old_cfg = json.loads((parent_prov/'run.json').read_text())['config']
    changed = {'experiment', 'contract', 'contract_sha256', 'candidates', 'new_candidates',
               'parent_run', 'defer_visualization'}
    if {k:v for k,v in cfg.items() if k not in changed} != {k:v for k,v in old_cfg.items() if k not in changed}:
        raise ValueError('Refinement changed a non-candidate setting')
    if (cfg['candidates'] != sorted((*PARENT_KS,*NEW_KS)) or cfg['new_candidates'] != list(NEW_KS)
            or cfg['parent_run'] != PARENT_RUN or cfg['defer_visualization'] is not True):
        raise ValueError('Unapproved candidate roster or delivery scope')
    if file_sha256(ROOT/cfg['contract']) != cfg['contract_sha256']:
        raise ValueError('Refinement contract hash differs')
    _, audit_hash = parent_audit()
    protected = json.loads((parent_prov/'approval.json').read_text())['protected_files']
    for relative, digest in protected.items():
        if file_sha256(ROOT/relative) != digest:
            raise ValueError('Parent protected input changed: '+relative)
    protected = dict(protected)
    protected[cfg['contract']] = cfg['contract_sha256']
    protected['configs/conditional_mdn_s5_e4.json'] = file_sha256(ROOT/'configs/conditional_mdn_s5_e4.json')
    protected[str((parent_prov/'formal_v1/final_audit.json').relative_to(ROOT))] = audit_hash
    roots = {part:ROOT/part/'runs'/name for part in ('results','provenance')}
    if any(path.exists() for path in roots.values()):
        raise FileExistsError('Run already exists; use formal pipeline to resume it')
    for path in roots.values(): path.mkdir(parents=True)
    provenance = roots['provenance']
    now = datetime.now(timezone.utc).isoformat()
    atomic_json(provenance/'run.json', dict(name=name, created_utc=now, config=cfg))
    instruction = '补充 K=3、6、12、18、20、22，依然全量训练；可视化与展示留到建模结束。'
    atomic_json(provenance/'approval.json', dict(user_authorization=instruction,
        contract_sha256=cfg['contract_sha256'], protected_files=protected, final_test_access=False))
    parent_auth = json.loads((parent_prov/'formal_v1/authorization.json').read_text())
    atomic_json(provenance/'formal_v1/authorization.json', dict(status='approved', approved_utc=now,
        full_experiment_authorized=True, resource_time_limit_seconds=None, compute_ceiling_waived=True,
        scientific_definition_unchanged=True, contract_sha256=cfg['contract_sha256'], final_test_access=False,
        user_instruction=instruction, resource_authorization='Existing explicit full-MDN time/compute waiver',
        parent_run=PARENT_RUN, new_candidates=list(NEW_KS), reused_candidates=list(PARENT_KS),
        deferred_target_path=parent_auth['deferred_target_path'],
        deferred_target_sha256=parent_auth['deferred_target_sha256']))
    atomic_json(provenance/'resource_ledger.json', dict(version=1, entries=[], active=None))
    from . import conditional_mdn_s5_e4_inputs as inp
    inp.freeze_sources(roots, 'preflight')
    inp.freeze_access(roots, inp.cohorts(cfg))
    return name


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_name')
    print(prepare(parser.parse_args().run_name))
