"""Immutable source-keyed donor cache for exact-position M1vcat.

The single structured NPY file is memory-mapped at inference; per-lag Parquet
rows store only actual origin/end indices. No full donor-path expansion.
"""
import hashlib
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from data3001.dataset import PreparedSource,manifest
from data3001.modelling.markov_inputs import count_pairs,audit_pairs
from data3001.modelling.markov_position import OBS_DTYPE,GEOD,E
from data3001.modelling.markov_velocity import velocity_atoms
from data3001.modelling.run_blend_cv import save_frame
from data3001.preprocessing.prep_pairs import load_track,origin_indices,generate

KERNELS=(1,2,3,5,7)
KEYS=['id','horizon_days','origin_cell_1','destination_cell_1']


def native_observations(frame,cuts):
    required={'id','source_obs','time','lon_normalized','lat','ve','vn','cell_1'}
    if not required<=set(frame) or frame.source_obs.duplicated().any():raise ValueError('Missing/ambiguous source fields')
    out=np.zeros(len(frame),dtype=OBS_DTYPE)
    for key in ['id','source_obs','time','lat','ve','vn']:
        values=frame[key].to_numpy()
        if key in ['id','source_obs','time'] and (not np.isfinite(values).all() or not np.equal(values,np.floor(values)).all()):
            raise ValueError('Noninteger source identity or hourly time')
        out[key]=values
    out['lon']=frame.lon_normalized;out['cell']=frame.cell_1
    out['atom']=velocity_atoms(frame.ve,frame.vn,cuts)
    if len(frame)>1:
        _,_,distance=GEOD.inv(out['lon'][:-1],out['lat'][:-1],out['lon'][1:],out['lat'][1:])
        # Invalid segments outside all qualified donor intervals must not poison
        # later prefixes. Qualified complete intervals are independently checked.
        length=np.where(np.isfinite(distance),distance,0.)
        out['length']=np.r_[0,np.cumsum(length,dtype='float64')]
    return out


def donor_rows(ledger,frame,offset):
    if not ledger.target.eq('stopped').all() or ledger.duplicated(['id','horizon_days','origin_source_obs']).any():
        raise ValueError('Ambiguous or nonstopped donor labels')
    part=ledger.loc[ledger.reason_code.eq(0)]
    lookup=pd.Index(frame.source_obs);o=lookup.get_indexer(part.origin_source_obs)
    if (o<0).any():raise ValueError('Origin key absent from native track')
    if not np.array_equal(frame.id.to_numpy()[o],part.id) or not np.array_equal(frame.cell_1.to_numpy()[o],part.origin_cell_1):
        raise ValueError('Origin identity/cell differs')
    exit_=part.destination_cell_1.eq(E).to_numpy();end=np.full(len(part),E,dtype='int64')
    ix=np.flatnonzero(~exit_);ep=lookup.get_indexer(part.endpoint_source_obs.iloc[ix])
    if ((ep<0).any() or not np.array_equal(frame.cell_1.to_numpy()[ep],part.destination_cell_1.iloc[ix])
            or not np.array_equal(frame.time.to_numpy()[ep]-frame.time.to_numpy()[o[ix]],part.horizon_days.to_numpy()[ix]*86400)
            or not np.array_equal(ep-o[ix],part.horizon_days.to_numpy()[ix]*24)):
        raise ValueError('Endpoint key/cell/exact hourly interval differs')
    end[ix]=ep+offset
    if offset+len(frame)>=np.iinfo(np.int32).max:raise ValueError('Flat source index exceeds declared storage')
    return pd.DataFrame({'origin':(o+offset).astype('int32'),'endpoint':end.astype('int32'),
                         'lag':part.horizon_days.to_numpy(dtype='int16')})


def collect_position_inputs(paths,run,ids,parent,cuts,progress=print):
    data=manifest();ids=sorted(int(i) for i in ids)
    if len(set(ids))!=len(ids) or any(data['records'][str(i)]['pool']!='train' for i in ids):
        raise PermissionError('Unique development IDs only')
    total=sum(data['records'][str(i)]['rows'] for i in ids)
    if total>=np.iinfo(np.int32).max:raise ValueError('Cache requires larger source-index storage')
    old=pd.read_parquet(parent/'transition_counts_by_id.parquet')
    reference={int(i):g.reset_index(drop=True) for i,g in old.groupby('id') if int(i) in ids}
    old_R=pd.read_parquet(parent/'release_counts_by_id.parquet')
    reference_R={int(i):g.loc[g.horizon_days.isin([7,30])].reset_index(drop=True) for i,g in old_R.groupby('id') if int(i) in ids}
    parent_summary=pd.read_csv(parent/'source_ID_summary.csv').set_index('id')
    source=PreparedSource(allow_test=False);summaries=[];releases=[];audits=[];traces=[]
    begun=time.monotonic();offset=0;donors_total=0
    schema=pa.schema([('origin',pa.int32()),('endpoint',pa.int32()),('lag',pa.int16())])

    def write_observations(stream):
        nonlocal offset,donors_total
        np.lib.format.write_array_header_2_0(stream,{'descr':OBS_DTYPE.descr,'fortran_order':False,'shape':(total,)})
        def write_donors(pair_stream):
            nonlocal offset,donors_total
            with pq.ParquetWriter(pair_stream,schema,compression='zstd') as writer:
                for number,sid in enumerate(ids,1):
                    frame,a,events=load_track(source,sid)
                    if len(frame)!=data['records'][str(sid)]['rows']:raise ValueError('Native row population changed')
                    native=native_observations(frame,cuts);stream.write(native.tobytes())
                    origins=origin_indices(frame,a,'D');digest=hashlib.sha256();plain=[];count=0
                    for h in KERNELS:
                        if not len(origins):break
                        _,labels=generate(frame,a,events,sid,origins,h,'pooled',tolerance=0)
                        digest.update(labels[['origin_source_obs','horizon_days','destination_cell_1','reason_code']].to_numpy(dtype='<i8').tobytes())
                        pairs=donor_rows(labels,frame,offset)
                        writer.write_table(pa.Table.from_pandas(pairs,schema=schema,preserve_index=False))
                        count+=len(pairs);plain.append(count_pairs(labels));audits.append(audit_pairs(labels,'D'))
                        if number<=10 and len(pairs):traces.append(pairs.head(2).assign(id=sid))
                    empty=pd.DataFrame(columns=KEYS+['pair_count']).astype('int64')
                    observed=pd.concat(plain,ignore_index=True) if plain else empty
                    expected=reference.get(sid,empty)
                    pd.testing.assert_frame_equal(observed.sort_values(KEYS).reset_index(drop=True),expected.sort_values(KEYS).reset_index(drop=True))
                    rfile=parent/'release_labels'/f'{sid}.parquet'
                    if rfile.exists():
                        labels=pd.read_parquet(rfile)
                        for _,g in labels.groupby('horizon_days',sort=True):
                            digest.update(g[['origin_source_obs','horizon_days','destination_cell_1','reason_code']].to_numpy(dtype='<i8').tobytes())
                        chosen=labels.loc[labels.horizon_days.isin([7,30])].copy()
                        lookup=pd.Index(frame.source_obs).get_indexer(chosen.origin_source_obs)
                        if (lookup<0).any():raise ValueError('R source key disappeared')
                        chosen['origin']=(lookup+offset).astype('int32')
                        expected_R=reference_R.get(sid,empty)
                        pd.testing.assert_frame_equal(count_pairs(chosen).sort_values(KEYS).reset_index(drop=True),expected_R.sort_values(KEYS).reset_index(drop=True))
                        releases.append(chosen[['id','origin_source_obs','horizon_days','origin_cell_1','destination_cell_1','reason_code','origin']])
                        audits.append(audit_pairs(chosen,'R'))
                    if digest.hexdigest()!=parent_summary.loc[sid,'target_reason_digest']:raise ValueError('Source target/reason keys changed')
                    summaries.append({'id':sid,'start':offset,'end':offset+len(frame),'rows':len(frame),
                        'source_sha256':data['records'][str(sid)]['sha256'],'donor_pairs':count,
                        'source_target_digest':digest.hexdigest(),'exact_parent_counts_and_source_keys':True})
                    offset+=len(frame);donors_total+=count
                    if number%200==0 or number==len(ids):progress(f'Position cache {number}/{len(ids)}; {time.monotonic()-begun:.1f}s',flush=True)
        paths.publish(run['results']/'donors.parquet',write_donors)
        if offset!=total:raise ValueError('Native cache count mismatch')
    paths.publish(run['results']/'observations.npy',write_observations)
    if not releases:raise ValueError('No R release labels')
    release=pd.concat(releases,ignore_index=True)
    save_frame(paths,run['results']/'releases.parquet',release)
    save_frame(paths,run['results']/'source_ID_summary.csv',pd.DataFrame(summaries))
    save_frame(paths,run['results']/'candidate_reasons.csv',pd.concat(audits,ignore_index=True))
    save_frame(paths,run['results']/'trace_examples.parquet',pd.concat(traces,ignore_index=True))
    return {'IDs_read':len(ids),'retained_rows':total,'D_eligible_pairs_all_kernel_days':donors_total,
            'R_eligible_pairs':{str(int(h)):int(g.reason_code.eq(0).sum()) for h,g in release.groupby('horizon_days')},
            'all_source_keys_and_parent_counts_identical':True,'elapsed_seconds':time.monotonic()-begun}
