"""Charge each audit recovery check to the original checks budget, <=300 s total."""
import time
START=time.monotonic()
import json
import os
import signal
import subprocess
import sys
import traceback
from pathlib import Path
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[key]='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
from data3001.modelling.continuous_models import local_gmm_s5_e2_pipeline as pipe
from data3001.modelling.continuous_models.local_gmm_s5_e2_scoreopt_processes import stop_group

p=Path(__file__).resolve().parent;provenance=p.parent
run={'provenance':provenance,'results':pipe.ROOT/'results/runs'/provenance.name}
cfg=json.loads((provenance/'frozen_config.json').read_text())
receipts=[json.loads(f.read_text()) for f in provenance.glob('*_resources.json')]
used=sum(json.loads(f.read_text())['elapsed_seconds'] for f in provenance.glob('auditfix_*_resources.json'))
remaining=min(300-used,
    cfg['seconds']['checks']-sum(x['elapsed_seconds'] for x in receipts if x['phase']=='checks'),
    cfg['seconds']['total']-sum(x['elapsed_seconds'] for x in receipts))-3.
if remaining<=0:raise RuntimeError('Audit recovery 300-second cumulative budget exhausted')
cfg['seconds']['checks']=min(cfg['seconds']['checks'],sum(x['elapsed_seconds'] for x in receipts if x['phase']=='checks')+remaining)
cfg['seconds']['total']=min(cfg['seconds']['total'],sum(x['elapsed_seconds'] for x in receipts)+remaining)
label='auditfix_'+sys.argv[1]
if (provenance/(label+'_resources.json')).exists():raise FileExistsError(label)
if (provenance/'active_budget.json').exists():raise RuntimeError('Another computation is active')
guard=pipe.previous_inputs.Guard(pipe.ROOT,run)
budget=pipe.Budget(run,cfg,'checks',label,START);child=None;code=1;failure=None
try:
    with (p/(sys.argv[1]+'.log')).open('x') as output:
        child=subprocess.Popen(sys.argv[2:],stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        while child.poll() is None:
            budget.check();time.sleep(.5)
        code=child.returncode;budget.check()
except BaseException as e:
    failure=repr(e)
    (p/(sys.argv[1]+'_failure_trace.txt')).write_text(traceback.format_exc())
finally:
    if child is not None:
        try:stop_group(child.pid)
        except BaseException as e:
            failure=repr(e)
            (p/(sys.argv[1]+'_cleanup_trace.txt')).write_text(traceback.format_exc())
        try:child.wait(timeout=.5)
        except subprocess.TimeoutExpired:failure='Command leader survived process-group cleanup'
    receipt=budget.finish(pipe.project_paths(),label,code==0 and failure is None,guard)
    print(json.dumps(dict(exit_code=code,failure=failure,elapsed_seconds=receipt['elapsed_seconds'],
        cumulative_recovery_check_seconds=used+receipt['elapsed_seconds'],log=str(p/(sys.argv[1]+'.log')))),flush=True)
if failure:raise RuntimeError(failure)
raise SystemExit(code)
