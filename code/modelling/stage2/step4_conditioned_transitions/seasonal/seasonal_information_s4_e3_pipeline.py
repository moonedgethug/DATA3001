"""Sealed source roles, matched forecast generation and legacy reconciliation."""
import json
import numpy as np
import pandas as pd
from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_frame,save_json
from data3001.modelling.baselines import seasonal_conditioning_s4_e1_inputs as inputs
from data3001.modelling.baselines.temporal_validation_s4_e2_inputs import temporal_role
from data3001.modelling.baselines.run_seasonal_conditioning_s4_e1 import array_file
from data3001.modelling.baselines import seasonal_information_s4_e3 as model
from data3001.modelling.baselines.seasonal_information_s4_e3_matching import draw_table,audit_draws


REFERENCE_FILES=['role_roster.csv','role_membership.parquet','outer_case_roster.parquet','forecast_keys.csv',
                 'forecast_vectors.npy','destination_states.npy','summary.csv']


def permitted(paths,cfg):
    source=json.loads((paths.root/cfg['integrity_config']).read_text())
    ref=paths.root/'results/runs'/cfg['reference']
    return inputs.allowed_inputs(paths,source)+[ref/n for n in REFERENCE_FILES]+[paths.root/'provenance/runs'/cfg['reference']/'outputs.json']


def parquet(path, **kwargs):
    with path.open('rb') as f: return pd.read_parquet(f,**kwargs)


def load_roles(paths,cfg):
    source=json.loads((paths.root/cfg['integrity_config']).read_text())
    bundle=inputs.load_inputs(paths,source)
    q=bundle.pop('qualified')
    q=q[q.origin_time_UTC.between(pd.Timestamp('2001-01-01',tz='UTC'),pd.Timestamp('2023-01-01',tz='UTC'),inclusive='left')]
    ref=paths.root/'results/runs'/cfg['reference']
    receipt=json.loads((paths.root/'provenance/runs'/cfg['reference']/'outputs.json').read_text())
    assert receipt['completed'] and not receipt['final_test_access']
    for name in REFERENCE_FILES:
        path=ref/name;rel=path.relative_to(paths.root).as_posix();digest=file_sha256(path)
        assert receipt['output_sha256'][rel]==digest
        bundle['inventory'][rel]=digest
    outer=temporal_role(q,'2020-01-01','2023-01-01','C_outer')
    inner=[temporal_role(outer['train'],cut,end,name) for cut,end,name in
           [('2014-01-01','2017-01-01','C_T0'),('2017-01-01','2020-01-01','C_T1')]]
    for role in [outer,*inner]:
        saved=parquet(ref/'role_membership.parquet',filters=[('role_name','=',role['name'])])
        current=role['ledger']
        pd.testing.assert_frame_equal(current.sort_values(inputs.KEY).reset_index(drop=True),
                                      saved[current.columns].sort_values(inputs.KEY).reset_index(drop=True),check_exact=True)
        assert set(role['train'].id).isdisjoint(outer['validation'].id)
    for r,counts in zip([outer,*inner],[(33971,30128),(41761,35035),(44612,41123)]):
        assert tuple(r['validation'].groupby('horizon_days').size())==counts
    assert tuple(outer['train'].groupby('horizon_days').size())==(265393,235177)
    assert tuple(outer['train'].groupby('horizon_days').id.nunique())==(338,294)
    return bundle,outer,inner,ref


def matched_forecasts(paths,run,cfg,train,matrices,states):
    t=train.reset_index(drop=True)
    features=t[inputs.FEATURES].copy()
    features['source_index']=features.index
    save_frame(paths,run['results']/'matched_training_keys.parquet',features)
    results={}; manifests=[]; rows=[]
    for (h,i),cell in features.groupby(['horizon_days','origin_cell_1']):
        targets=t.loc[cell.index,'destination_cell_1']
        active,encoded=np.unique(targets.to_numpy(),return_inverse=True)
        # Global training index is independent of future data; the sampler sees only features.
        code=np.zeros(len(t),dtype='int32');code[cell.index]=encoded
        for s in range(4):
            key=(int(h),int(i),s)
            n=int(cell.departure_season.eq(s).sum())
            if n:
                selected,m,edges=draw_table(cell,s,key,cfg['replicates'],cfg['sampling_seed'])
                other,identical=audit_draws(cell,s,selected,m)
                manifests.append(m.assign(horizon_days=h,origin_cell_1=i,departure_season=s))
                codes=code[selected]
                counts=np.stack([np.bincount(v,minlength=len(active)) for v in codes]).astype('int32')
                # Independent count from sampled source indices, using original endpoint labels.
                # Cross-tabulate original labels and replicate IDs in one joint histogram.
                raw=t.destination_cell_1.to_numpy()[selected]
                actual=pd.Index(active).get_indexer(raw.ravel()).reshape(raw.shape)
                joint=actual+len(active)*np.arange(len(counts))[:,None]
                direct=np.bincount(joint.ravel(),minlength=counts.size).reshape(counts.shape)
                assert np.array_equal(direct,counts)
                assert np.all(counts.sum(axis=1)==n)
                donor_ids=m.donor_id.nunique()
            else:
                edges=0;donor_ids=0;other=np.zeros(cfg['replicates']);identical=np.ones(cfg['replicates'],dtype=bool)
                counts=np.tile(np.bincount(encoded,minlength=len(active)),(cfg['replicates'],1)).astype('int32')
            if not n:
                assert np.array_equal(counts[0]/counts[0].sum(),matrices[h,i,-1][np.searchsorted(states,active)])
            prefix=f'matched/{h}_{i}_{s}'
            array_file(paths,run['results']/(prefix+'_counts.npy'),counts)
            array_file(paths,run['results']/(prefix+'_states.npy'),active)
            results[key]=(active,counts,float(other.mean()))
            rows.append(dict(horizon_days=h,origin_cell_1=i,departure_season=s,pairs=n,
                             ids=cell.loc[cell.departure_season==s,'id'].nunique(),annual_pairs=len(cell),annual_ids=cell.id.nunique(),
                             feasible_edges=edges,unique_donor_ids=donor_ids,identical_draws=int(identical.sum()),
                             other_share_mean=float(other.mean()),other_share_min=float(other.min()),other_share_max=float(other.max()),
                             matched_destinations_min=int((counts[:,active>=0]>0).sum(axis=1).min()),
                             matched_destinations_max=int((counts[:,active>=0]>0).sum(axis=1).max())))
    save_frame(paths,run['results']/'sampled_placements.parquet',pd.concat(manifests,ignore_index=True))
    info=pd.DataFrame(rows)
    save_frame(paths,run['results']/'matching_support.csv',info)
    return results,info


def reconcile_reference(ref,states,cache,roster,summary=None):
    # E2 G/T B2 is annual and therefore independent of query season.
    keys=pd.read_csv(ref/'forecast_keys.csv')
    with (ref/'destination_states.npy').open('rb') as f: previous_states=np.load(f)
    with (ref/'forecast_vectors.npy').open('rb') as f: previous=np.load(f)
    order=pd.Index(previous_states).get_indexer(states)
    assert np.all(order>=0)
    for idx,row in keys[(keys.block=='C')&(keys.policy=='G')&(keys.model=='B2')].iterrows():
        key=('Annual',row.horizon_days,row.origin_cell_1,0)
        if key not in cache:
            assert not previous[idx].any()
        else:
            assert np.max(np.abs(previous[idx,order]-cache[key][0]))<=1e-12
    prior=parquet(ref/'outer_case_roster.parquet',filters=[('block','=','C')],
                  columns=inputs.KEY+['score_weight','supported'])
    merged=roster.merge(prior,on=inputs.KEY,suffixes=('','_ref'),validate='one_to_one')
    assert len(merged)==len(roster)==len(prior)
    assert np.array_equal(merged.supported,merged.supported_ref)
    assert np.allclose(merged.weight,merged.score_weight,rtol=0,atol=1e-12)
    if summary is not None:
        old=pd.read_csv(ref/'summary.csv')
        old=old[(old.block=='C')&(old.policy=='G')&(old.model=='B2')].sort_values('horizon_days')
        new=summary[summary.model=='Annual'].sort_values('horizon_days')
        cols=['brier','h90','k90']
        assert np.allclose(old[cols],new[cols],rtol=0,atol=1e-12)


def prepare(paths,run,cfg):
    bundle,outer,inner,ref=load_roles(paths,cfg)
    states=np.sort(bundle['states']);bundle['states']=states
    save_json(paths,run['provenance']/'input_inventory.json',bundle['inventory'])
    array_file(paths,run['results']/'states.npy',states)
    save_frame(paths,run['results']/'source_roles.parquet',pd.concat([r['ledger'] for r in [outer,*inner]],ignore_index=True))
    folds=[]
    for role in inner:
        matrix,support=model.fit_role(role,bundle)
        folds.append((role['name'],matrix,role['validation']))
        save_frame(paths,run['results']/f"inner/{role['name']}_support.csv",support)
        save_frame(paths,run['results']/f"inner/{role['name']}_counts.parquet",inputs.conditional_counts(role['train']))
    choices,curves,held=model.select_weights(folds,states)
    save_frame(paths,run['results']/'choices.csv',choices)
    save_frame(paths,run['results']/'inner_curves.csv',curves)
    save_frame(paths,run['results']/'inner_cases.parquet',held)
    matrices,support=model.fit_role(outer,bundle)
    cache,metadata=model.make_forecasts(matrices,support,choices,states)
    save_frame(paths,run['results']/'training_support.csv',support)
    save_frame(paths,run['results']/'outer_counts.parquet',inputs.conditional_counts(outer['train']))
    save_frame(paths,run['results']/'forecast_keys.csv',metadata)
    array_file(paths,run['results']/'forecast_vectors.npy',np.stack([item[0] for item in cache.values()]))
    array_file(paths,run['results']/'region_masks.npy',np.stack([item[1] for item in cache.values()]))
    roster=inputs.validation_weights(outer['validation'][inputs.FEATURES]).rename(columns={'weight':'eligible_weight'})
    roster=roster.merge(support[support.departure_season.ge(0)][model.ROW+['supported','annual_fallback','ids']],
                        on=model.ROW,validate='many_to_one').rename(columns={'annual_fallback':'fallback','ids':'season_ids'})
    wt=inputs.validation_weights(roster[roster.supported])
    roster['weight']=wt.weight.reindex(roster.index).fillna(0.)
    reconcile_reference(ref,states,cache,roster)
    save_frame(paths,run['results']/'outer_roster.parquet',roster)
    print('Training-only weights locked; building full matched-control roster.',flush=True)
    matched,info=matched_forecasts(paths,run,cfg,outer['train'],matrices,states)
    files={p.relative_to(run['results']).as_posix():file_sha256(p) for p in run['results'].rglob('*') if p.is_file()}
    save_json(paths,run['provenance']/'forecast_freeze.json',{'status':'FORECASTS_AND_SAMPLES_FROZEN_BEFORE_SCORING','files':files})
    return states,outer,ref,choices,curves,roster,cache,matched,info
