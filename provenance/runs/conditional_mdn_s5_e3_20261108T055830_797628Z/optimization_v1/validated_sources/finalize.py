"""Close an additive validation record; never advances experiment permissions."""
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
PROV=HERE.parent
ROOT=HERE.parents[3]
RESULTS=ROOT/'results/runs'/PROV.name
OUT=ROOT/'results/deliverables/conditional_mdn_s5_e3_optimization'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


approval=json.loads((HERE/'approval.json').read_text())
for path,value in approval['old_artifacts_sha256'].items():
    assert sha(ROOT/path)==value,path
review=json.loads((HERE/'independent_review.json').read_text())
assert review['status']=='PASS_FOR_BOUNDED_VALIDATION_REPORT_ONLY'
sources=list(HERE.glob('*.py'))+[
    ROOT/'src/data3001/modelling/continuous_models/conditional_mdn_s5_e3_optimized.py',
    ROOT/'tests/test_modelling_conditional_mdn_s5_e3_optimized.py']
folder=HERE/'validated_sources';folder.mkdir(exist_ok=True)
source_hashes={}
for source in sources:
    source_hashes[str(source.relative_to(ROOT))]=sha(source)
    shutil.copy2(source,folder/source.name)
(HERE/'validated_sources.json').write_text(json.dumps(source_hashes,indent=2))
ledger=json.loads((PROV/'resource_ledger.json').read_text())
entries=[e for e in ledger['entries'] if e['label'].startswith('optv1_')]
stages={s:sum(e['elapsed_seconds'] for e in entries if e['label'].startswith('optv1_'+s+'_'))
        for s in ('A','B','C','D')}
assert all(stages[s]<approval['stage_seconds'][s] for s in stages)
assert sum(stages.values())<1200
pilot=sum(e['elapsed_seconds'] for e in ledger['entries'] if e['phase']=='pilot')
assert pilot<3600
run_bytes=sum(p.stat().st_size for f in (PROV,RESULTS) for p in f.rglob('*') if p.is_file())
outside_bytes=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
new_bytes=run_bytes-approval['initial_run_storage_bytes']+outside_bytes
assert new_bytes<512*2**20
summary=json.loads((HERE/'validation_summary.json').read_text())
summary['final_resource_snapshot_before_close']={
    'stage_seconds':stages,'additional_seconds':sum(stages.values()),'pilot_total_seconds':pilot,
    'additional_peak_rss_gib':max(e.get('peak_process_tree_rss_bytes',0) for e in entries)/2**30,
    'new_output_bytes':new_bytes,'closure_overhead_in_live_ledger':True}
summary['independent_review_passed']=True
summary['formal_next_stage']=None
(HERE/'validation_summary.json').write_text(json.dumps(summary,indent=2))
(HERE/'STATUS.json').write_text(json.dumps({'status':'BOUNDED_VALIDATION_COMPLETE_FORMAL_STOPPED',
    'effective_next_stage':None,'resume_formal_authorized':False,
    'old_gate_and_contract_unchanged':True,'source_manifest':'validated_sources.json'},indent=2))
plan=(HERE/'PLAN.md').read_text().replace('- [ ] D (240 s):','- [x] D (240 s):')
(HERE/'PLAN.md').write_text(plan)
print(json.dumps(summary['final_resource_snapshot_before_close']))
