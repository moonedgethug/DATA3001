"""Additional approved 20-minute cap, inside the original pilot supervisor."""
import json
import sys
from pathlib import Path

from data3001.modelling.continuous_models.conditional_mdn_s5_e3_runtime import supervise

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAPS = {'A': 180., 'B': 300., 'C': 480., 'D': 240.}


def available(entries, stage):
    selected = [e for e in entries if e['label'].startswith('optv1_')]
    total = sum(e['elapsed_seconds'] for e in selected)
    own = sum(e['elapsed_seconds'] for e in selected if e['label'].startswith('optv1_'+stage+'_'))
    return min(1200.-total, CAPS[stage]-own)


def main():
    stage, label, *command = sys.argv[1:]
    if command[:1] == ['--']:
        command = command[1:]
    if stage not in CAPS or not command:
        raise ValueError('Expected stage A/B/C/D, label and command')
    prov = HERE.parent
    ledger = json.loads((prov/'resource_ledger.json').read_text())
    cfg = json.loads((prov/'run.json').read_text())['config']
    allowance = available(ledger['entries'], stage)
    if allowance <= 1:
        raise TimeoutError('Additional validation budget exhausted')
    approval = json.loads((HERE/'approval.json').read_text())
    # The old run remains intact. Enforce the smaller new incremental storage cap.
    cfg = dict(cfg, storage_hard_gib=min(cfg['storage_hard_gib'],
                    (approval['initial_run_storage_bytes']+512*2**20)/2**30))
    run = {'provenance': prov, 'results': ROOT/'results/runs'/prov.name}
    raise SystemExit(supervise(run,cfg,'pilot','optv1_'+stage+'_'+label,command,allowance-1.))


if __name__ == '__main__':
    main()
