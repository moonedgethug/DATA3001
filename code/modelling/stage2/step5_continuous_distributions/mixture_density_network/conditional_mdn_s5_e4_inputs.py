"""Frozen MDN cohorts and guarded input/output; no model fitting."""
import json
import os
from pathlib import Path
import sys
import hashlib
import numpy as np
import pandas as pd

from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import ReadOnlyInputs
from .conditional_mdn_s5_e4_runtime import ROOT, atomic_json

KEY=['id','origin_source_obs','horizon_days']
EXPECTED={'C_T0':(170978,234,41761,50), 'C_T1':(209934,280,44612,58),
          'C_outer':(265393,338,33971,45)}


class Guard(ReadOnlyInputs):
    def __init__(self,root,run):
        super().__init__(root,run)
        self.outer_allowed=False
        self.outer_read=False

    def __call__(self,event,args):
        super().__call__(event,args)
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            path=Path(os.fsdecode(args[0])).resolve()
            if path.name=='outer_targets.parquet':
                if not self.outer_allowed:
                    self.denied.append({'path':str(path),'reason':'MDN all-model forecast freeze required'})
                    raise PermissionError('MDN outer targets remain sealed')
                self.outer_read=True


def context(name,guarded=True):
    if Path(name).name!=name or not name.startswith('conditional_mdn_s5_e4_'):raise ValueError('Invalid MDN run')
    run={part:ROOT/(part+'/runs')/name for part in ('results','provenance')}
    cfg=json.loads((run['provenance']/'run.json').read_text())['config']
    canonical=json.loads((ROOT/'configs/conditional_mdn_s5_e4.json').read_text())
    if cfg!=canonical:raise ValueError('Run config differs from approved canonical config')
    approval=json.loads((run['provenance']/'approval.json').read_text())
    if cfg['contract_sha256']!=approval['contract_sha256']:raise ValueError('Contract identity mismatch')
    for path,digest in approval['protected_files'].items():
        if file_sha256(ROOT/path)!=digest:raise ValueError('Protected input changed: '+path)
    guard=Guard(ROOT,run)
    if guarded:sys.addaudithook(guard)
    return project_paths(),run,cfg,approval,guard


def read_frame(path,columns=None,filters=None):
    with Path(path).open('rb') as f:return pd.read_parquet(f,columns=columns,filters=filters)


def cohorts(cfg):
    base=ROOT/'results/runs'/cfg['e7_run']
    train=read_frame(base/'training_coordinates.parquet',columns=KEY+['origin_time_UTC','lon','lat','outside','required_interval_end_epoch'])
    ledger=read_frame(base/'roles.parquet')
    if (len(train),train.id.nunique())!=(265393,338):raise ValueError('Training roster changed')
    if train.outside.any() or not train.horizon_days.eq(7).all():raise ValueError('Continuous cohort semantics changed')
    if train.duplicated(KEY).any():raise ValueError('Repeated training source key')
    out={}
    for role,(nf,ni,nq,qi) in EXPECTED.items():
        roles=ledger[ledger.role_name.eq(role)&ledger.horizon_days.eq(7)]
        fit=roles[roles.role.eq('train')][KEY].merge(train,on=KEY,validate='one_to_one').sort_values(KEY).reset_index(drop=True)
        if role=='C_outer':
            query=read_frame(base/'query_coordinates.parquet').sort_values(KEY).reset_index(drop=True)
            targets=None
        else:
            # These labels are in the authorized training-period source; only the
            # pilot whitelist or a frozen formal role may be passed to a scorer.
            validation_metadata=roles[roles.role.eq('validation')][KEY].merge(train,on=KEY,validate='one_to_one').sort_values(KEY).reset_index(drop=True)
            query=validation_metadata[KEY+['origin_time_UTC','lon','lat']].copy()
            targets=None
        if (len(fit),fit.id.nunique(),len(query),query.id.nunique())!=(nf,ni,nq,qi):raise ValueError('Role roster changed: '+role)
        if set(fit.id)&set(query.id):raise ValueError('Fit/validation ID overlap')
        if query.duplicated(KEY).any():raise ValueError('Duplicate query key')
        cutoff={'C_T0':'2014-01-01','C_T1':'2017-01-01','C_outer':'2020-01-01'}[role]
        if not (fit.required_interval_end_epoch<pd.Timestamp(cutoff,tz='UTC').timestamp()).all():raise ValueError('Cross-boundary label in fit')
        out[role]={'fit':fit,'query':query,'targets':targets}
    return out


def key_digest(keys):
    values=keys[KEY].sort_values(KEY).to_numpy(dtype='<i8')
    return hashlib.sha256(values.tobytes()).hexdigest()


def freeze_access(run,roles):
    from .conditional_mdn_s5_e4_training import partition_ids
    receipt={}
    for role,value in roles.items():
        opt,stop=partition_ids(value['fit'].id.to_numpy())
        indices=np.floor(np.arange(64)*(len(value['query'])-1)/63).astype(int)
        receipt[role]={'fit_key_sha256':key_digest(value['fit']),
                       'optimization_ids':opt.tolist(),'stop_ids':stop.tolist(),
                       'pilot_keys':value['query'].iloc[indices][KEY].to_numpy(dtype=np.int64).tolist() if role!='C_outer' else []}
    path=run['provenance']/'endpoint_access_freeze.json'
    if path.exists() and json.loads(path.read_text())!=receipt:raise ValueError('Frozen endpoint permissions changed')
    if not path.exists():atomic_json(path,receipt)
    return receipt


def authorize_endpoint_keys(run,role,keys,kind):
    path=run['provenance']/'endpoint_access_freeze.json'
    if not path.exists():raise PermissionError('Freeze stop IDs and pilot keys before endpoint access')
    receipt=json.loads(path.read_text())[role]
    if kind=='fit':
        if key_digest(keys)!=receipt['fit_key_sha256']:raise PermissionError('Fit endpoint roster differs from freeze')
    elif kind=='pilot':
        actual=set(map(tuple,keys[KEY].to_numpy(dtype=np.int64)))
        allowed=set(map(tuple,receipt['pilot_keys']))
        if not actual or not actual<=allowed:raise PermissionError('Pilot endpoint outside fixed whitelist')
    else:raise PermissionError('Formal target release is not enabled by the pilot loader')


def endpoints(cfg,run,role,keys,kind):
    authorize_endpoint_keys(run,role,keys,kind)
    base=ROOT/'results/runs'/cfg['e7_run']
    values=read_frame(base/'training_coordinates.parquet',columns=KEY+['endpoint_lon','endpoint_lat'],
        filters=[('origin_source_obs','in',keys.origin_source_obs.astype(int).tolist()),('horizon_days','==',7)])
    joined=keys[KEY].merge(values,on=KEY,how='left',validate='one_to_one',indicator=True)
    if not joined._merge.eq('both').all() or len(joined)!=len(keys):raise ValueError('Endpoint-key mismatch')
    return joined[['endpoint_lon','endpoint_lat']].to_numpy()


def freeze_sources(run,label):
    files=list((ROOT/'src/data3001/modelling/continuous_models').glob('conditional_mdn_s5_e4*.py'))
    files+=list((ROOT/'tests').glob('test_modelling_conditional_mdn_s5_e4*.py'))
    files+=[ROOT/'configs/conditional_mdn_s5_e4.json']
    folder=run['provenance']/(label+'_sources');folder.mkdir(exist_ok=True)
    hashes={}
    for p in files:
        digest=file_sha256(p);hashes[str(p.relative_to(ROOT))]=digest
        target=folder/p.name
        if target.exists() and file_sha256(target)!=digest:raise ValueError('Source snapshot is immutable')
        if not target.exists():target.write_bytes(p.read_bytes())
    atomic_json(folder/'hashes.json',hashes)
    return hashes
