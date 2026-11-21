"""Explicit, hash-bound reuse of completed E3 models and compatible score rows.

Imported bytes retain their original identities. This module never relabels a
parent checkpoint as a new fit and never imports scores before forecast freeze.
"""
from functools import lru_cache
import json
import os
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from data3001.paths import file_sha256
from .conditional_mdn_s5_e4_runtime import ROOT, atomic_json

PARENT_RUN = 'conditional_mdn_s5_e3_20261108T055830_797628Z'
PARENT_KS = (1,2,4,8,16,32)
NEW_KS = (3,6,12,18,20,22)
PARAMETER_FIELDS = ('query_keys','origins','pi','mu','cov','target_scale')
IDENTITY_FIELDS = ('role','fit_key_sha256','query_key_sha256','fit_origins_sha256',
                   'query_origins_sha256','fit_pairs','fit_ids','optimization_ids',
                   'stop_ids','input_source_hashes')


@lru_cache(maxsize=1)
def parent_audit():
    path=ROOT/'provenance/runs'/PARENT_RUN/'formal_v1/final_audit.json'
    value=json.loads(path.read_text())
    if (value.get('status')!='complete' or value.get('passed') is not True or
            value.get('final_test_access') is not False or value.get('run_name')!=PARENT_RUN):
        raise ValueError('Parent MDN audit is not complete, passing and development-only')
    return value,file_sha256(path)


def audited(path):
    path=Path(path).resolve()
    if not path.is_relative_to(ROOT):raise ValueError('Parent evidence escapes project')
    value,_=parent_audit();relative=path.relative_to(ROOT).as_posix()
    expected=value['evidence_sha256'].get(relative)
    if not expected or file_sha256(path)!=expected:
        raise ValueError('Unaudited or changed parent evidence: '+relative)
    return expected


def validate_compatible_forecast(current,parent):
    for name in PARAMETER_FIELDS:
        if name not in current or name not in parent:
            raise ValueError('Forecast field missing: '+name)
        a,b=current[name],parent[name]
        if a.dtype!=b.dtype or a.shape!=b.shape or not np.array_equal(a,b):
            raise ValueError('Forecast differs from parent: '+name)


def validate_reuse_streams(current,parent):
    for field in ('role','mode','count','region_count','query_key_sha256','streams'):
        if field not in current or current[field]!=parent.get(field):
            raise ValueError('Parent score stream mismatch: '+field)


def _parent_base():
    return ROOT/'results/runs'/PARENT_RUN/'formal_v1'


def _assert_identity(current,parent):
    for name in IDENTITY_FIELDS:
        if current.get(name)!=parent.get(name):
            raise ValueError('Parent fit/query definition mismatch: '+name)


def import_model(formal_root,role,k,identity,query):
    if k not in PARENT_KS:raise ValueError('Only registered parent K may be imported')
    formal_root=Path(formal_root)
    source_folder=_parent_base()/role/f'K{k}'
    source_manifest=source_folder/'manifest.json'
    audited(source_manifest)
    manifest=json.loads(source_manifest.read_text())
    _assert_identity(identity,manifest['identity'])
    files=[source_manifest,source_folder/'seed_selection.json']
    records=[manifest['parameters'],manifest['training_receipt'],
             *(r['checkpoint'] for r in [*manifest['seeds'],manifest['full_refit']])]
    for record in records:
        rel=Path(record['path'])
        source=(_parent_base()/rel).resolve()
        if not source.is_relative_to(source_folder.resolve()):raise ValueError('Parent model artifact escapes candidate')
        if audited(source)!=record['sha256']:raise ValueError('Parent manifest artifact mismatch')
        files.append(source)
    copied={}
    for source in files:
        digest=audited(source);relative=source.relative_to(_parent_base())
        target=formal_root/relative
        if target.exists():
            if target.is_symlink() or file_sha256(target)!=digest:raise ValueError('Imported artifact changed')
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_name(target.name+'.import.tmp')
            shutil.copyfile(source,temporary)
            if file_sha256(temporary)!=digest:
                raise ValueError('Parent artifact changed while copying')
            with temporary.open('rb') as handle:os.fsync(handle.fileno())
            os.replace(temporary,target)
        copied[relative.as_posix()]={'source':source.relative_to(ROOT).as_posix(),'sha256':digest}
    receipt=dict(status='complete',parent_run=PARENT_RUN,parent_audit_sha256=parent_audit()[1],
                 role=role,k=k,files=copied,new_training_performed=False,
                 parent_identity_preserved=True,final_test_access=False)
    path=formal_root/role/f'K{k}'/'reuse.json'
    if path.exists() and json.loads(path.read_text())!=receipt:raise ValueError('Import receipt changed')
    atomic_json(path,receipt)
    return verify_import(formal_root,role,k,identity,query)


def verify_import(formal_root,role,k,identity,query):
    from .conditional_mdn_s5_e3_formal_training import _verify_model
    folder=Path(formal_root)/role/f'K{k}'
    receipt=json.loads((folder/'reuse.json').read_text())
    if (k not in PARENT_KS or receipt.get('parent_run')!=PARENT_RUN or
            receipt.get('parent_audit_sha256')!=parent_audit()[1] or
            receipt.get('new_training_performed') is not False or
            receipt.get('status')!='complete' or receipt.get('role')!=role or receipt.get('k')!=k):
        raise ValueError('Invalid parent import receipt')
    for relative,record in receipt['files'].items():
        unresolved=Path(formal_root)/relative
        local=unresolved.resolve()
        if not local.is_relative_to(folder.resolve()) or unresolved.is_symlink():raise ValueError('Import path escapes candidate')
        source=ROOT/record['source']
        if audited(source)!=record['sha256'] or file_sha256(local)!=record['sha256']:
            raise ValueError('Imported bytes differ from audited parent')
    manifest_path=folder/'manifest.json'
    if file_sha256(manifest_path)!=audited(_parent_base()/role/f'K{k}'/'manifest.json'):
        raise ValueError('Imported manifest is not original parent bytes')
    manifest=json.loads(manifest_path.read_text())
    _assert_identity(identity,manifest['identity'])
    return _verify_model(formal_root,role,k,manifest['identity'],query)


def compatible_scores(run,freeze,query):
    """Return audited parent rows, or no reuse if the required level was absent."""
    from .conditional_mdn_s5_e4_formal_scoring import _validate_rows,load_parameters
    # Called only after target release. Never silently accept a corrupt receipt.
    role,mode=freeze['role'],freeze['mode']
    if mode=='inner_regions':return pd.DataFrame()
    n,m=freeze['count'],freeze['region_count']
    relative=Path(role)/mode/f'N{n}_M{m}'
    folder=_parent_base()/relative
    if not (folder/'complete.json').exists():return pd.DataFrame()
    audited(folder/'complete.json')
    receipt=json.loads((folder/'complete.json').read_text())
    parent_freeze=ROOT/'provenance/runs'/PARENT_RUN/'formal_v1'/role/mode/f'inputs_N{n}_M{m}.json'
    audited(parent_freeze);old=json.loads(parent_freeze.read_text())
    validate_reuse_streams(freeze,old)
    if (receipt.get('status')!='complete' or receipt.get('excluded_queries')!=0 or
            receipt.get('k_values')!=list(PARENT_KS) or receipt.get('identity_sha256')!=old['identity_sha256']):
        raise ValueError('Parent score completion evidence differs')
    hashes={}
    for k in PARENT_KS:
        source=_parent_base()/role/f'K{k}'/'parameters.npz'
        current=run['results']/'formal_v1'/role/f'K{k}'/'parameters.npz'
        digest=audited(source)
        if file_sha256(current)!=digest or freeze['parameter_hashes'][str(k)]!=digest:
            raise ValueError('Score reuse requires unchanged audited parameter bytes')
        if old['parameter_hashes'][str(k)]!=digest:raise ValueError('Parent scoring used different parameters')
        load_parameters(current,query,k)
        hashes[str(k)]=digest
    digest=audited(folder/'scores.parquet')
    if receipt['scores_sha256']!=digest:raise ValueError('Parent score table hash mismatch')
    frame=pd.read_parquet(folder/'scores.parquet')
    keys=query[['id','origin_source_obs','horizon_days']].to_numpy(np.int64)
    _validate_rows(frame,keys,PARENT_KS,0,len(query))
    evidence=dict(status='complete',parent_run=PARENT_RUN,source=(folder/'scores.parquet').relative_to(ROOT).as_posix(),
                  source_sha256=digest,parent_audit_sha256=parent_audit()[1],parameter_hashes=hashes,
                  role=role,mode=mode,count=n,region_count=m,k_values=list(PARENT_KS),
                  query_count=len(query),row_count=len(frame),forecast_freeze_precedes_reuse=True)
    path=run['provenance']/f'formal_v1/{role}/{mode}/reuse_N{n}_M{m}.json'
    if path.exists() and json.loads(path.read_text())!=evidence:raise ValueError('Parent score reuse evidence changed')
    atomic_json(path,evidence)
    return frame


def merge_rows(computed,reused,keys,k_values,start,end):
    from .conditional_mdn_s5_e4_formal_scoring import _validate_rows
    pieces=[x for x in (computed,reused) if len(x)]
    if not pieces:raise ValueError('No rows to combine')
    result=pd.concat(pieces,ignore_index=True).sort_values(['position','K']).reset_index(drop=True)
    _validate_rows(result,keys,k_values,start,end)
    return result
