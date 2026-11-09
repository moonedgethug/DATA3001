"""Freeze all earlier artifacts before additive diagnosis. No model evaluation."""
import hashlib
import json
import shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
PROV=HERE.parent
ROOT=HERE.parents[3]
RESULTS=ROOT/'results/runs'/PROV.name


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


if (HERE/'approval.json').exists():
    raise RuntimeError('Do not reset an existing validation allowance')
old=json.loads((PROV/'approval.json').read_text())
protected=dict(old['protected_files'])
for name in ('pilot_result.json','pilot_frozen_tasks.json','pilot_stream_manifest.json',
             'pilot_query_whitelist.json','pilot_training_receipt.json','run.json'):
    path=PROV/name
    protected[str(path.relative_to(ROOT))]=digest(path)
for path in RESULTS.rglob('*'):
    if path.is_file(): protected[str(path.relative_to(ROOT))]=digest(path)
for path in (ROOT/'src/data3001/modelling/continuous_models').glob('conditional_mdn_s5_e3*.py'):
    if path.name.endswith(('_optimized.py','_validation.py')): continue
    protected[str(path.relative_to(ROOT))]=digest(path)
    snap=HERE/'original_sources'/path.name
    snap.parent.mkdir(exist_ok=True)
    shutil.copy2(path,snap)
for path,expected in protected.items():
    assert digest(ROOT/path)==expected,path
ledger=json.loads((PROV/'resource_ledger.json').read_text())
storage=sum(p.stat().st_size for folder in (PROV,RESULTS) for p in folder.rglob('*') if p.is_file())
approval={
    'authorization':'User approved additive bounded diagnosis and equivalence optimization; max20min inside original1h pilot; no formal run.',
    'additional_seconds':1200,'stage_seconds':{'A':180,'B':300,'C':480,'D':240},
    'prior_compute_seconds':sum(e['elapsed_seconds'] for e in ledger['entries']),
    'initial_run_storage_bytes':storage,'new_storage_cap_bytes':512*2**20,
    'formal_training_allowed':False,'old_artifacts_sha256':protected,
    'main_N_M':65536,'reference_diagnostic_totals':[65536,262144],
    'reference_replicates':8,'reference_keys':'all original8keys x6distributions; no selective seed retries',
    'equivalence':'same nodes: ES<=1e-9km, area relative<=1e-10; identical hits, masks, weights',
    'preserve':['model','K','weights','full samples','score definition','precision gates','raw historical failures']}
(HERE/'approval.json').write_text(json.dumps(approval,indent=2))
print(json.dumps({'protected_files':len(protected),'prior_compute_seconds':approval['prior_compute_seconds']}))
