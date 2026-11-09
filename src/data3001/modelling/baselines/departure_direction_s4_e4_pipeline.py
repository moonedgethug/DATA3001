"""Fit, freeze and score the common E4 chronological roster."""
import json
import time
import numpy as np
import pandas as pd

from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_json,save_frame
from data3001.modelling.common.prediction_regions import probability_region
from data3001.modelling.baselines.seasonal_conditioning_s4_e1_inputs import validation_weights,KEY
from data3001.modelling.baselines.run_seasonal_conditioning_s4_e1 import array_file
from data3001.modelling.baselines.seasonal_information_s4_e3_pipeline import load_roles,permitted as e2_inputs,parquet
from data3001.modelling.baselines.departure_direction_s4_e4_inputs import ORIGIN,load_features
from data3001.modelling.baselines import departure_direction_s4_e4 as model

E3_FILES=['outer_roster.parquet','forecast_keys.csv','forecast_vectors.npy','states.npy','region_masks.npy','summary.csv']
QUERY=KEY+['origin_cell_1','origin_time_UTC']


def permitted(paths,cfg):
    base=paths.root/'results/runs'/cfg['reference_e3']
    return e2_inputs(paths,cfg)+[base/f for f in E3_FILES]+[paths.root/'provenance/runs'/cfg['reference_e3']/'outputs.json']


def check_reference(paths,cfg,ref,support,roster,states,inventory):
    old=paths.root/'results/runs'/cfg['reference_e3']
    receipt=json.loads((paths.root/'provenance/runs'/old.name/'outputs.json').read_text())
    assert receipt['completed'] and not receipt['final_test_access']
    for name in E3_FILES:
        rel=(old/name).relative_to(paths.root).as_posix();digest=file_sha256(old/name)
        assert receipt['output_sha256'][rel]==digest
        inventory[rel]=digest
    for directory,tag in [(ref,'e2'),(old,'e3')]:
        if tag=='e2':
            previous=parquet(ref/'outer_case_roster.parquet',filters=[('block','=','C')],columns=KEY+['supported','score_weight'])
            previous=previous.rename(columns={'score_weight':'weight'})
        else:
            previous=parquet(old/'outer_roster.parquet',columns=KEY+['supported','weight','eligible_weight'])
        joined=roster.merge(previous,on=KEY,suffixes=('','_ref'),validate='one_to_one')
        assert len(joined)==len(roster)==len(previous)
        for name in previous.columns.difference(KEY):
            assert np.allclose(joined[name],joined[name+'_ref'],rtol=0,atol=1e-12)
        ids=pd.read_csv(directory/'forecast_keys.csv')
        vectors=np.load(directory/'forecast_vectors.npy')
        domain=np.load(directory/('states.npy' if tag=='e3' else 'destination_states.npy'))
        assert set(domain)==set(states)
        if tag=='e3':
            selected=ids[ids.model=='Annual'];masks=np.load(old/'region_masks.npy')
        else:selected=ids[(ids.block=='C')&(ids.policy=='G')&(ids.model=='B2')]
        for index,row in selected.iterrows():
            z=support[(support.horizon_days==row.horizon_days)&(support.origin_cell_1==row.origin_cell_1)]
            expected=np.zeros(len(domain))
            if not z.empty:expected[pd.Index(domain).get_indexer(z.destination)]=z.pairs/z.pairs.sum()
            assert np.allclose(expected,vectors[index],atol=1e-12,rtol=0)
            if tag=='e3':
                mask,_=probability_region(expected,domain)
                assert np.array_equal(mask,masks[index])
    return old


def attach(frame,features):
    result=frame.merge(features[ORIGIN+model.FEATURES],on=ORIGIN,how='left',validate='many_to_one',sort=False)
    assert len(result)==len(frame) and result.interval_reason.notna().all()
    return result


def prepare(paths,run,cfg,guard):
    bundle,outer,inner,ref=load_roles(paths,cfg)
    directory=run['results']
    states=np.sort(bundle['states'])
    save_frame(paths,directory/'roles.parquet',pd.concat([r['ledger'] for r in [outer,*inner]],ignore_index=True))
    keys=pd.concat([r[QUERY] for r in [outer['train'],outer['validation']]],ignore_index=True)
    keys=keys[ORIGIN+['origin_time_UTC','origin_cell_1']].drop_duplicates().sort_values(ORIGIN)
    assert not keys.duplicated(ORIGIN).any()
    start=time.monotonic()
    print('Reading verified per-ID past-hour features for',keys.id.nunique(),'development drifters.',flush=True)
    features,inventory=load_features(paths,guard,keys)
    io_seconds=time.monotonic()-start
    save_frame(paths,directory/'past_hour_features.parquet',features)
    save_json(paths,run['provenance']/'feature_io.json',{'elapsed_seconds':io_seconds,'tracks':len(guard.read_ids),
              'source_rows':len(features),'input_bytes_hashed':sum(paths._resolve(k).stat().st_size for k in inventory)})
    inventory.update(bundle['inventory'])
    folds=[];statistics=[]
    def fit_and_predict(role,with_targets):
        train=attach(role['train'][QUERY+['destination_cell_1']],features)
        valid=attach(role['validation'][QUERY+(['destination_cell_1'] if with_targets else [])],features)
        tau,support,blocks=model.make_blocks(train,valid)
        uniq=train.drop_duplicates(ORIGIN)
        reason,_=model.classify(uniq,tau)
        statistics.append(dict(role=role['name'],tau_m_s=tau,unique_origins=len(uniq),positive_valid_speeds=int((uniq.speed>0).sum()),
                               usable_training_keys=int((reason=='valid').sum()),low_speed_keys=int((reason=='low_speed').sum())))
        save_frame(paths,directory/(role['name']+'_donors.parquet'),support)
        return blocks,support
    for role in inner:
        folds.append((role['name'],fit_and_predict(role,True)[0]))
    choices,curves,inner_cases=model.selection(folds)
    del folds
    save_frame(paths,directory/'choices.csv',choices)
    save_frame(paths,directory/'inner_curves.csv',curves)
    save_frame(paths,directory/'inner_cases.parquet',inner_cases)
    print('Inner choices locked. Building source-keyed outer probabilities and regions.',flush=True)
    blocks,support=fit_and_predict(outer,False)
    thresholds=pd.DataFrame(statistics);save_frame(paths,directory/'thresholds.csv',thresholds)
    roster=validation_weights(pd.concat([g for _,g,_,_ in blocks],ignore_index=True)).rename(columns={'weight':'eligible_weight'})
    wt=validation_weights(roster[roster.supported])
    roster['weight']=wt.weight.reindex(roster.index).fillna(0)
    old=check_reference(paths,cfg,ref,support,roster,states,inventory)
    save_json(paths,run['provenance']/'input_inventory.json',inventory)
    save_frame(paths,directory/'outer_roster.parquet',roster)
    array_file(paths,directory/'domain_states.npy',states)
    forecasts={}
    lambdas=choices.set_index('horizon_days').lambda_h
    for (h,i),g,b,D in blocks:
        if b is None:continue
        lam=lambdas[h]
        P=b.annual+lam*(D-b.annual)
        fallback=g.fallback_reason.ne('valid').to_numpy()
        assert np.array_equal(P[fallback],np.broadcast_to(b.annual,P[fallback].shape))
        assert np.allclose(P.sum(axis=1),1,atol=1e-12,rtol=0) and np.all((P>0)==(b.annual>0))
        if lam==0:assert np.all(P==b.annual)
        amask,_=probability_region(b.annual,b.states)
        masks=model.regions(P,b.states)
        prefix=directory/f'forecasts/{h}_{i}'
        for label,value in [('states',b.states),('annual',b.annual),('adjusted',P),('annual_mask',amask),('adjusted_mask',masks)]:
            array_file(paths,prefix.with_name(prefix.name+'_'+label+'.npy'),value)
        save_frame(paths,prefix.with_name(prefix.name+'_keys.parquet'),g[KEY])
        forecasts[h,i]=(g,b,P,amask,masks)
    files={f.relative_to(directory).as_posix():file_sha256(f) for f in directory.rglob('*') if f.is_file()}
    save_json(paths,run['provenance']/'forecast_freeze.json',{'status':'FROZEN_BEFORE_OUTER_SCORING','files':files})
    return outer,states,ref,old,choices,curves,thresholds,roster,forecasts


def score(roster,targets,forecasts):
    parts=[]
    for key,(keys,b,P,amask,masks) in forecasts.items():
        g=keys[KEY].merge(roster,on=KEY,validate='one_to_one').merge(targets,on=KEY,validate='one_to_one')
        assert len(g)==len(keys) and np.array_equal(keys.origin_source_obs,g.origin_source_obs)
        pos=pd.Index(b.states).get_indexer(g.destination_cell_1)
        g['observed_exit']=g.destination_cell_1.eq(-2).astype(float)
        g['missing_donor_share']=b.unheaded.sum()/(b.unheaded.sum()+b.headed.sum())
        g['no_usable_donors']=b.headed.sum()==0
        for label,vector,mask in [('Annual',np.broadcast_to(b.annual,P.shape),np.broadcast_to(amask,P.shape)),('Adjusted',P,masks)]:
            truth=model.at_truth(vector,pos)
            bs=1+np.einsum('ij,ij->i',vector,vector)-2*truth
            error=vector.copy();good=np.flatnonzero(pos>=0);error[good,pos[good]]-=1
            assert np.allclose(bs,np.square(error).sum(axis=1)+(pos<0),rtol=0,atol=1e-12)
            g[label+'_brier']=bs;g[label+'_h90']=model.at_truth(mask,pos)
            g[label+'_k90']=mask[:,b.states>=0].sum(axis=1)
            g[label+'_mass']=(vector*mask).sum(axis=1)
            g[label+'_zero']=(truth==0).astype(float);g[label+'_exit']=vector[:,np.flatnonzero(b.states==-2)[0]]
        parts.append(g)
    result=pd.concat(parts,ignore_index=True)
    assert len(result)==int(roster.supported.sum())
    return result
