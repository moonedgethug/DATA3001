"""Source verification and explicit role boundaries for existing-model validation."""
import json
import numpy as np
import pandas as pd
from data3001.paths import file_sha256
from data3001.modelling.common.qualified_count_inputs import read_frame
from data3001.modelling.baselines import seasonal_conditioning_s4_e1_inputs as original

KEY = original.KEY
FEATURES = original.FEATURES
counts = original.annual_counts


def allowed_inputs(paths, config):
    source = json.loads((paths.root / config['integrity_config']).read_text())
    fold = paths.root / config['folds_path']
    return original.allowed_inputs(paths, source) + [fold, paths.root/'provenance/runs'/fold.parent.name/'outputs.json']


def load_inputs(paths, config):
    # Reuse verified original-label reconstruction, not any prior fitted model.
    source = json.loads((paths.root / config['integrity_config']).read_text())
    raw = original.load_inputs(paths, source)
    q = raw['qualified']
    keep = q.origin_time_UTC.ge(pd.Timestamp(config['start'], tz='UTC')) & q.origin_time_UTC.lt(pd.Timestamp(config['end'], tz='UTC'))
    excluded = q.loc[~keep, FEATURES].copy()
    q = q.loc[keep].copy().reset_index(drop=True)
    assert q.groupby('horizon_days').size().to_dict() == {7:302941,30:268882}
    assert q.groupby('horizon_days').id.nunique().to_dict() == {7:383,30:336}
    fold = paths.root / config['folds_path']
    receipt_path = paths.root/'provenance/runs'/fold.parent.name/'outputs.json'
    receipt = json.loads(receipt_path.read_text())
    assert receipt['completed'] and not receipt['final_test_access']
    rel = fold.relative_to(paths.root).as_posix()
    assert file_sha256(fold) == receipt['output_sha256'][rel]
    folds = read_frame(fold)
    assert not folds.id.duplicated().any() and set(folds.outer_fold) == set(range(5))
    assert q.id.isin(folds.id).all()
    inventory = dict(raw['inventory'])
    for p in [fold, receipt_path, paths.root/config['integrity_config']]:
        inventory[p.relative_to(paths.root).as_posix()] = file_sha256(p)
    return dict(q=q, excluded=excluded, folds=folds, origins=raw['origins'],
                states=np.sort(raw['states']), state_index=raw['state_index'], inventory=inventory)


def temporal_role(q, cutoff, end, name):
    cut = pd.Timestamp(cutoff, tz='UTC'); end = pd.Timestamp(end, tz='UTC')
    valid = q.origin_time_UTC.ge(cut) & q.origin_time_UTC.lt(end)
    held = set(q.loc[valid, 'id'])
    candidate = q.origin_time_UTC.lt(cut)
    crossing = candidate & q.required_interval_end_epoch.ge(cut.timestamp())
    overlap = candidate & q.id.isin(held)
    train = candidate & ~crossing & ~overlap
    role = np.select([valid, crossing, candidate & ~crossing & overlap, train],
                     ['validation','excluded_label_cutoff','excluded_validation_id','train'],default='outside')
    ledger = q[KEY].copy()
    ledger['role_name'] = name; ledger['role'] = role
    ledger['crosses_label_cutoff'] = crossing.to_numpy()
    ledger['held_ID_in_training_window'] = overlap.to_numpy()
    t = q.loc[train].copy(); v = q.loc[valid].copy()
    assert len(t) and len(v) and not set(t.id) & set(v.id)
    assert t.required_interval_end_epoch.lt(cut.timestamp()).all()
    return dict(name=name, train=t, validation=v, ledger=ledger, cutoff=cutoff)


def build_roles(bundle, config):
    q = bundle['q']; outer = {}; inner = {}; ledgers = []; rows = []
    fold_map = bundle['folds'].set_index('id').outer_fold
    for block in config['blocks']:
        b = block['name']; out = temporal_role(q, block['cutoff'], block['end'], b+'_outer')
        outer[b] = out; ledgers.append(out['ledger']); inner[b] = {'G':[], 'T':[]}
        fit = out['train']
        for k in range(5):
            held = fit.id.map(fold_map).eq(k)
            name = f'{b}_G{k}'
            ledger = fit[KEY].copy(); ledger['role_name'] = name
            ledger['role'] = np.where(held,'validation','train')
            ledger['crosses_label_cutoff'] = False; ledger['held_ID_in_training_window'] = False
            role = dict(name=name,train=fit.loc[~held].copy(),validation=fit.loc[held].copy(),ledger=ledger,cutoff=None)
            assert len(role['validation']) and not set(role['train'].id) & set(role['validation'].id)
            inner[b]['G'].append(role); ledgers.append(ledger)
        for k, (cut, end) in enumerate(block['inner_time']):
            role = temporal_role(fit, cut, end, f'{b}_T{k}')
            inner[b]['T'].append(role); ledgers.append(role['ledger'])
        for policy, roles in [('outer',[out]), *inner[b].items()]:
            for role in roles:
                assert not set(role['train'].id) & set(out['validation'].id)
                for kind in ['train','validation']:
                    for h, g in role[kind].groupby('horizon_days'):
                        rows.append(dict(block=b,policy=policy,role_name=role['name'],kind=kind,horizon_days=h,
                                         pairs=len(g),ids=g.id.nunique(),origins=g.origin_cell_1.nunique(),
                                         first_origin=str(g.origin_time_UTC.min()),last_origin=str(g.origin_time_UTC.max())))
        expected = block['expected_validation_pairs']
        assert out['validation'].groupby('horizon_days').size().to_dict() == {7:expected[0],30:expected[1]}
    # Illustration fixed from fitting-ID support, before scoring any outcomes.
    support = []
    for b, role in outer.items():
        support.append(role['train'].groupby(['horizon_days','origin_cell_1']).id.nunique().rename(b))
    index=pd.MultiIndex.from_product([[7,30],bundle['origins']],names=['horizon_days','origin_cell_1'])
    support = pd.concat(support,axis=1).reindex(index).fillna(0)
    minimum = support.min(axis=1).groupby('origin_cell_1').min()
    origin = int(minimum[minimum.eq(minimum.max())].index.min())
    return outer, inner, pd.concat(ledgers,ignore_index=True), pd.DataFrame(rows), origin
