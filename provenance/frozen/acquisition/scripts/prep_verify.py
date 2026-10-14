"""Independent source linkage, frozen-rule and candidate reconciliation audit."""
import json,time,hashlib
import numpy as np
import pandas as pd
import duckdb
from prep_io import BASE,OUT,Source,sha,save_json,now
from prep_run import directory

def verify():
    s=Source();start=time.monotonic();source_rows=0;files=0;counts={};source_names=None
    freeze=json.loads((OUT/'config/frozen_before_test.json').read_text())
    assert all(sha(BASE/p)==h for p,h in freeze['files_sha256'].items()),'Frozen file changed'
    source_stats=json.loads((OUT/'audit/source_values_reverified.json').read_text());assert source_stats['all_passed']
    clean_signatures=[]
    for i,id in enumerate(s.ids):
        id=int(id);split=s.cohort.loc[id,'split'];f=directory(split)/f'{id}.parquet'
        cp=json.loads((OUT/'checkpoints'/f'clean_{id}.json').read_text());assert sha(f)==cp['output_sha256'];files+=1
        signature=json.loads(cp['signature']);clean_signatures.append(signature)
        raw,meta=s.track(id);d=pd.read_parquet(f);order=d.original_within_traj_obs.to_numpy()
        assert len(order)==len(raw['time']) and np.array_equal(np.sort(order),np.arange(len(order)))
        assert np.array_equal(d.source_obs.to_numpy(),int(meta['source_obs_start_global'])+order)
        for k,v in raw.items():assert np.array_equal(d[k].to_numpy(),v[order],equal_nan=True),(id,k)
        if source_names is None:source_names=sorted(raw)
        assert (np.diff(d.time.to_numpy())>0).all() # verified acquired cohort has no duplicate/missing times
        expected=np.isfinite(d.lon)&np.isfinite(d.lat)&d.lon.between(-180,180)&d.lat.between(-90,90)&d.analytical_row
        assert (d.position_ok==expected).all()
        assert not ((~np.isfinite(d.sst))&~d.position_ok).any(),'missing SST unexpectedly removed position'
        assert (d.velocity_ok==(np.isfinite(d.ve)&np.isfinite(d.vn))).all()
        for k in ['err_lon','err_lat','err_ve','err_vn','err_sst','err_sst1','err_sst2']:
            assert (d[k+'_ok']==(np.isfinite(d[k])&(d[k]>=0))).all()
        for k in ['sst','sst1']:
            x=d[k].astype(float)-273.15;correct=np.isfinite(d[k])&d['flg_'+k].isin([4,5])&x.between(-2,50)
            assert (d[k+'_ok']==correct).all()
        assert (d.sst2_ok==(np.isfinite(d.sst2)&(d.flg_sst2==5))).all()
        source_rows+=len(d)
        for k,z in {'missing_SST_position_retained':int((~np.isfinite(d.sst)&d.position_ok).sum()),'temperature_rejected_position_retained':int((~d.sst_ok&d.position_ok).sum()),
           'negative_position_uncertainty':int(((d.err_lat<0)|(d.err_lon<0)).sum()),'unknown_regime_rows':int((d.regime<0).sum()),'geometry_uncertain_rows':int(d.geometry_uncertain.sum())}.items():counts[k]=counts.get(k,0)+z
        root=OUT/'restricted_test' if split=='test' else OUT
        paircp=json.loads((root/'checkpoints'/f'pairs_{id}.json').read_text())
        for relative,h in paircp['files'].items():assert sha(root/relative)==h,(id,relative);files+=1
        # Origin ledger must include every eligible-time position in actual D,
        # and R subset must agree with original per-ID source-linked flags.
        o=pd.read_parquet(root/'origins'/f'{id}.parquet')
        domain=json.loads((OUT/'audit/domain_selection.json').read_text())['selected_bounds'];x0,y0,x1,y1=domain
        take=d.position_ok&d.lon_normalized.between(x0,x1)&d.lat.between(y0,y1)
        assert set(o.source_obs)==set(d.loc[take,'source_obs'])
        assert len(o[o.in_R])==int(d.in_R.sum())
        states=pd.read_parquet(OUT/'geometry/state_index.parquet',columns=['resolution','cell'])
        for res,col in [(1,'cell_1'),(.5,'cell_05')]:assert set(o[col])<=set(states.loc[states.resolution==res,'cell'])
        if i%500==0:print('verified source/partitions',i+1,len(s.ids),flush=True)
    assert source_rows==39107061 and len(s.ids)==3741
    assert counts['missing_SST_position_retained']==1366330
    # Recorded code dependencies must be recoverable as exact source files.
    archive=list((OUT/'metadata/code_revisions').glob('*.py'))+list((BASE/'scripts').glob('*.py'))
    hashes={sha(p) for p in archive}
    for sig in clean_signatures:
        for k in ['clean_code','core_code','geometry_code']:assert sig[k] in hashes,(k,sig[k])
    for root in [OUT,OUT/'restricted_test']:
        support=pd.read_parquet(root/'support/cell_support.parquet')
        assert (support.candidates==support.eligible+support[['reason_'+str(i) for i in range(1,10)]].sum(axis=1)).all()
        # Every population/scenario/horizon/target/grid uses the same complete
        # set of origins. Only eligibility, not candidate definition, varies.
        g=support.groupby(['split','population','resolution','scenario','horizon_days','target']).candidates.sum().reset_index()
        for (_,pop),z in g.groupby(['split','population']):assert z.candidates.nunique()==1
    peers=pd.read_parquet(OUT/'audit/selected_peer_observations.parquet')
    if len(peers):
        targets={e['event']:e['id'] for e in json.loads((OUT/'audit/speed_event_diagnostics.json').read_text())['events']}
        assert all(s.cohort.loc[int(r.reference_id),'split']=='train' and int(r.reference_id)!=targets[int(r.event)] for r in peers.itertuples())
        assert not peers.duplicated(['event','reference_id']).any()
    report={'status':'PASS_WITH_REPORTED_SUPPORT_LIMITATIONS','utc':now(),'acquired_IDs':len(s.ids),'source_rows':source_rows,
        'all_original_obs_fields_equal':source_names,'source_objects_reverified':source_stats['source_objects_verified'],
        'source_subset_fields_reverified':len(source_stats['subset_field_value_hashes']),
        'output_hashes_verified':files,'frozen_files_verified':len(freeze['files_sha256']),'all_candidate_counts_reconciled':True,
        'origin_state_indices_admissible':True,'held_out_peer_references':0,'same_ID_peer_references':0,
        'source_field_rules_independently_rechecked':True,'counts':counts,'elapsed_seconds':time.monotonic()-start,
        'support_limit':'365-day fixed-drogued validation DJF zero endpoint/stopped and MAM zero stopped; no predictive acceptance claimed',
        'unresolved_semantics':'affected uncertainty/NaN-loss/gap uses explicitly isolated, see unresolved_questions.json',
        'predictive_model_fitting_or_scoring':False,'test_support_policy':'kept under restricted_test; not used in settings or examples'}
    save_json(OUT/'audit/preparation_verification.json',report);print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':verify()
