"""Sequential complete-run coordinator; no model or sample redefinition."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import traceback
import numpy as np
import pandas as pd
from data3001.paths import file_sha256
from . import conditional_mdn_s5_e3_inputs as inp
from . import conditional_mdn_s5_e3_selection as selection
from .conditional_mdn_s5_e3_runtime import ROOT, atomic_json

PREFIX = 'data3001.modelling.continuous_models.conditional_mdn_s5_e3_'
LEVELS = (65536,131072,262144)
KS = (1,2,4,8,16,32)


def next_level(value):
    if value not in LEVELS: raise ValueError('Unregistered integration level')
    if value == LEVELS[-1]: raise ArithmeticError('Maximum registered precision still insufficient')
    return LEVELS[LEVELS.index(value)+1]


def join_audit(main, audit):
    keys = ['role','position',*inp.KEY,'K']
    if main.duplicated(keys).any() or audit.duplicated(keys).any():
        raise ValueError('Duplicated score/audit keys')
    columns = [c for c in audit if c.startswith(('audit_', 'es_audit_', 'iid_'))]
    out = main.merge(audit[keys+columns], on=keys, how='outer', validate='one_to_one', indicator=True)
    if not out._merge.eq('both').all(): raise ValueError('Incomplete main/audit roster')
    return out.drop(columns='_merge')


def immutable_json(path, value):
    if path.exists():
        if json.loads(path.read_text()) != value: raise ValueError('Frozen stage changed: '+str(path))
    else: atomic_json(path,value)


def stage(name, suffix, *arguments):
    command = [sys.executable,'-m',PREFIX+suffix,name,*map(str,arguments)]
    print(json.dumps(dict(stage=suffix, arguments=arguments)),flush=True)
    subprocess.run(command,cwd=ROOT,check=True)


def paths(name):
    _,run,cfg,approval,_ = inp.context(name,guarded=False)
    from .conditional_mdn_s5_e3_formal_context import authorization
    authorization(run,cfg)
    return run,cfg,approval


def score_folder(run,role,mode,n,m):
    return run['results']/f'formal_v1/{role}/{mode}/N{n}_M{m}'


def read_complete(run,role,mode,n,m):
    folder = score_folder(run,role,mode,n,m)
    receipt = json.loads((folder/'complete.json').read_text())
    freeze_path=run['provenance']/f'formal_v1/{role}/{mode}/inputs_N{n}_M{m}.json'
    freeze=json.loads(freeze_path.read_text())
    expected=inp.EXPECTED[role]
    if (receipt.get('status') != 'complete' or receipt.get('role')!=role or receipt.get('mode')!=mode or
        receipt.get('count')!=n or receipt.get('region_count')!=m or
        receipt.get('query_count')!=expected[2] or receipt.get('query_id_count')!=expected[3] or
        receipt.get('identity_sha256')!=freeze.get('identity_sha256') or
        receipt.get('query_key_sha256')!=freeze.get('query_key_sha256') or
        receipt.get('k_values')!=freeze.get('k_values') or
        receipt['scores_sha256'] != file_sha256(folder/'scores.parquet')):
        raise ValueError('Unverified complete score table')
    return pd.read_parquet(folder/'scores.parquet')


def freeze_analysis(run):
    names = ['conditional_mdn_s5_e3_selection.py','conditional_mdn_s5_e3_formal_pipeline.py']
    files = [Path(__file__).parent/name for name in names]
    identity = {str(p.relative_to(ROOT)):file_sha256(p) for p in files}
    immutable_json(run['provenance']/'formal_v1/analysis_sources.json',identity)
    return identity


def freeze_controls(run,cfg):
    base = ROOT/'results/runs'/cfg['baseline_run']
    prov = ROOT/'provenance/runs'/cfg['baseline_run']
    primary=sorted((base/'C_outer/score').glob('*.parquet'))
    audit=sorted((base/'C_outer/audit').glob('*.parquet'))
    if not primary or not audit:raise ValueError('Missing historical score or audit shards')
    files = primary+audit
    files += [base/'model_manifest.json', prov/'full_audit.json',prov/'run.json',prov/'forecast_freeze.json']
    if not files or not all(p.is_file() for p in files):raise ValueError('Missing historical controls')
    forecast=json.loads((prov/'forecast_freeze.json').read_text())
    if forecast.get('cases')!=33971 or forecast.get('outer_targets_read') is not False:
        raise ValueError('Historical forecast freeze is not complete and outcome-blind')
    for relative,digest in forecast['output_sha256'].items():
        p=(ROOT/relative).resolve()
        if not p.is_relative_to(base.resolve()) or file_sha256(p)!=digest:
            raise ValueError('Historical control forecast artifact changed')
        files.append(p)
    receipt = dict(baseline_run=cfg['baseline_run'],
                   files={str(p.relative_to(ROOT)):file_sha256(p) for p in files})
    immutable_json(run['provenance']/'formal_v1/control_sources.json',receipt)


def precision_upgrade(run,n,m,old_n,old_m,reason):
    immutable_json(run['provenance']/f'formal_v1/precision_upgrade_N{n}_M{m}.json',dict(
        status='approved', authorization='contract registered levels; user resource waiver',
        global_checks_complete=True, previous_count=old_n, previous_region_count=old_m,
        count=n,region_count=m,reason=reason))


def inner_precision(table):
    failures = {}
    for role in ('C_T0','C_T1','pooled'):
        frame = table if role=='pooled' else table[table.role.eq(role)]
        baseline = float(selection.pooled_id_means(frame,'energy_km')[1].mean())
        for k in KS[1:]:
            result=selection.paired_numerics(frame,k,1)
            try:selection._check_es_precision(result,baseline,f'{role}:{k}-1')
            except ArithmeticError:failures[f'{role}:{k}-1']=result
    return failures


def choose_inner(name,run):
    base = run['results']/'formal_v1'
    if (base/'selection.json').exists():
        validate_selection(run)
        return json.loads((base/'selection.json').read_text())
    n,m=65536,65536
    while True:
        pieces=[]
        for role in ('C_T0','C_T1'):
            stage(name,'formal_scoring',role,'inner_energy','--count',n,'--region-count',m)
            pieces.append(read_complete(run,role,'inner_energy',n,m))
        table=pd.concat(pieces,ignore_index=True)
        failures=inner_precision(table)
        atomic_json(run['provenance']/f'formal_v1/inner_precision_N{n}_M{m}.json',dict(passed=not failures,failures=failures))
        if not failures:break
        old=n;n=next_level(n)
        precision_upgrade(run,n,m,old,m,'Complete inner ES tables fail basic numerical precision')
    choice=selection.select_k(table)
    choice.update(status='complete',energy_count=n,region_count=m)
    immutable_json(base/'provisional_selection.json',choice)
    regions=None
    if choice['provisional_k']>1:
        while True:
            pieces=[]
            for role in ('C_T0','C_T1'):
                stage(name,'formal_scoring',role,'inner_regions','--k-values',1,choice['provisional_k'],
                      '--count',n,'--region-count',m)
                pieces.append(read_complete(run,role,'inner_regions',n,m))
            regions=pd.concat(pieces,ignore_index=True)
            try:
                result=selection.apply_quality(choice,regions)
                break
            except ArithmeticError as error:
                atomic_json(run['provenance']/f'formal_v1/inner_region_failure_N{n}_M{m}.json',dict(reason=str(error)))
                old=m;m=next_level(m)
                precision_upgrade(run,n,m,n,old,'Complete inner region tables fail basic numerical precision')
    else:result=selection.apply_quality(choice,None)
    result.update(energy_count=n,region_count=m,source_run_name=run['results'].name,
                  contract_sha256=json.loads((run['provenance']/'run.json').read_text())['config']['contract_sha256'])
    evidence={}
    for role in ('C_T0','C_T1'):
        files=[run['provenance']/f'formal_v1/{role}/forecast_freeze.json',
               score_folder(run,role,'inner_energy',n,65536)/'complete.json']
        if choice['provisional_k']>1:files.append(score_folder(run,role,'inner_regions',n,m)/'complete.json')
        for p in files:evidence[str(p.relative_to(ROOT))]=file_sha256(p)
    evidence[str((base/'provisional_selection.json').relative_to(ROOT))]=file_sha256(base/'provisional_selection.json')
    result['selection_inputs_sha256']=evidence
    table.to_parquet(base/'inner_energy.parquet',index=False)
    if regions is not None:regions.to_parquet(base/'inner_regions.parquet',index=False)
    immutable_json(base/'selection.json',result)
    validate_selection(run)
    return result


def validate_selection(run):
    base=run['results']/'formal_v1'
    value=json.loads((base/'selection.json').read_text())
    from .conditional_mdn_s5_e3_formal_training import _selection
    _selection(base,'C_outer',run)
    if value['selected_k'] not in {1,value['provisional_k']}:
        raise ValueError('Selected K is not the provisional K or prescribed K1 fallback')
    for relative,digest in value['selection_inputs_sha256'].items():
        p=ROOT/relative
        if file_sha256(p)!=digest:raise ValueError('Selection evidence changed')
        receipt=json.loads(p.read_text())
        if receipt.get('status')!='complete':raise ValueError('Selection evidence incomplete')
        if p.name=='forecast_freeze.json':
            expected=inp.EXPECTED[receipt['role']]
            if (receipt.get('query_count')!=expected[2] or receipt.get('query_id_count')!=expected[3] or
                set(receipt.get('models',{}))!=set(map(str,KS)) or receipt.get('outer_targets_read') is not False):
                raise ValueError('Selection forecast evidence roster incomplete')
            for item in receipt['models'].values():
                for kind in ('manifest','parameters'):
                    target=(base/item[kind]).resolve()
                    if not target.is_relative_to(base.resolve()) or file_sha256(target)!=item[kind+'_sha256']:
                        raise ValueError('Selection forecast bytes changed')
        if p.name=='complete.json':
            if file_sha256(p.parent/'scores.parquet')!=receipt['scores_sha256']:
                raise ValueError('Selection score contents changed')
            expected=inp.EXPECTED[receipt['role']]
            if receipt['query_count']!=expected[2] or receipt['query_id_count']!=expected[3]:
                raise ValueError('Selection evidence roster changed')
            expected_k=list(KS) if receipt['mode']=='inner_energy' else sorted({1,value['provisional_k']})
            if receipt['k_values']!=expected_k:raise ValueError('Selection candidates changed')
            if receipt.get('row_count')!=expected[2]*len(expected_k) or receipt.get('excluded_queries')!=0:
                raise ValueError('Selection score receipt omits queries')
    return value


def controls(run,cfg):
    manifest=json.loads((run['provenance']/'formal_v1/control_sources.json').read_text())
    for relative,digest in manifest['files'].items():
        if file_sha256(ROOT/relative)!=digest:raise ValueError('Historical control changed')
    base=ROOT/'results/runs'/cfg['baseline_run']/'C_outer'
    audit_receipt=json.loads((ROOT/'provenance/runs'/cfg['baseline_run']/'full_audit.json').read_text())
    if not audit_receipt['passed'] or audit_receipt['final_test_access']:
        raise ValueError('Historical control audit is not usable')
    main=pd.concat([pd.read_parquet(p) for p in sorted((base/'score').glob('*.parquet'))],ignore_index=True)
    audit=pd.concat([pd.read_parquet(p) for p in sorted((base/'audit').glob('*.parquet'))],ignore_index=True)
    main=main[main.model.isin(selection.CONTROLS)].rename(columns={'query_position':'position','area_replica_km2':'replica_area90_km2'})
    audit=audit[audit.model.isin(selection.CONTROLS)].rename(columns={'query_position':'position'})
    keys=['role','position','id','model']
    fields=['energy_km','variance','h90','area90_km2','hit_disagreement']
    audit=audit[keys+fields].rename(columns={c:'audit_'+c for c in fields})
    joined=main.merge(audit,on=keys,how='outer',validate='one_to_one',indicator=True)
    if not joined._merge.eq('both').all():raise ValueError('Historical score/audit mismatch')
    return joined.drop(columns=['_merge','replicate_means'])


def outer_table(run,cfg,n,m):
    main=read_complete(run,'C_outer','outer_score',n,m)
    audit=read_complete(run,'C_outer','outer_audit',n,m)
    mdn=join_audit(main,audit)
    table=pd.concat([mdn,controls(run,cfg)],ignore_index=True)
    query=inp.cohorts(cfg)['C_outer']['query']
    for model,part in table.groupby('model'):
        part=part.sort_values('position')
        if not np.array_equal(part[inp.KEY].to_numpy(np.int64),query[inp.KEY].to_numpy(np.int64)):
            raise ValueError('Control/MDN source-key mismatch: '+model)
    return table


def evaluate_outer(name,run,cfg,choice):
    n,m=choice['energy_count'],choice['region_count']
    while True:
        for mode in ('outer_score','outer_audit'):
            stage(name,'formal_scoring','C_outer',mode,'--count',n,'--region-count',m)
        table=outer_table(run,cfg,n,m)
        try:
            result=selection.summarize_outer(table,choice['selected_k'])
            break
        except ArithmeticError as error:
            atomic_json(run['provenance']/f'formal_v1/outer_precision_failure_N{n}_M{m}.json',dict(reason=str(error)))
            old_n,old_m=n,m
            if 'ES precision' in str(error):n=next_level(n)
            elif 'region precision' in str(error):m=next_level(m)
            else:raise
            precision_upgrade(run,n,m,old_n,old_m,'Complete outer tables fail: '+str(error))
    base=run['results']/'formal_v1'
    summary,per_id,comparisons,acceptance=result
    summary.to_csv(base/'summary.csv',index=True)
    per_id.to_csv(base/'per_id.csv',index=False)
    comparisons.to_csv(base/'comparisons.csv',index=False)
    table.drop(columns=[c for c in table if c.endswith('region_json')]).to_parquet(base/'outer_complete.parquet',index=False)
    acceptance.update(energy_count=n,region_count=m)
    atomic_json(base/'acceptance.json',acceptance)
    return acceptance


def run_full(name):
    run,cfg,_=paths(name)
    freeze_analysis(run);freeze_controls(run,cfg)
    prov=run['provenance']/'formal_v1'
    try:
        for role in ('C_T0','C_T1'):stage(name,'formal_training',role)
        choice=choose_inner(name,run)
        validate_selection(run)
        stage(name,'formal_training','C_outer')
        acceptance=evaluate_outer(name,run,cfg,choice)
        atomic_json(prov/'calculation_complete.json',dict(status='complete',acceptance=acceptance,
                    final_test_access=False,independent_final_audit_pending=True))
        print('Full calculations finished; independent final audit and report are required.',flush=True)
    except BaseException as error:
        atomic_json(prov/'formal_failure.json',dict(status='stopped',reason=repr(error),traceback=traceback.format_exc(),
                    model_definition_changed=False,final_test_access=False))
        raise


def main():
    parser=argparse.ArgumentParser();parser.add_argument('run_name')
    args=parser.parse_args();run_full(args.run_name)


if __name__=='__main__':main()
