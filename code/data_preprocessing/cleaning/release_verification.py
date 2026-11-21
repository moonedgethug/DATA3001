"""Read-only, full-value acceptance for the per-drifter release."""
import hashlib,json,os,time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from data3001.paths import project_paths,asset_path,file_sha256


def verify_release(progress=None):
    from data3001.dataset import manifest
    from data3001.preprocessing.prep_io import Source
    from data3001.preprocessing.prep_pairs import load_track,origin_indices,generate
    paths=project_paths();root=paths.root;started=time.monotonic();m=manifest()
    inventory_path=paths.asset('retained_data_inventory',verify=True)
    archive=paths.asset('retained_data_root')
    entries=[json.loads(line) for line in inventory_path.read_text().splitlines()]
    actual={str(p.relative_to(archive)) for p in archive.rglob('*')}
    if actual!={r['path'] for r in entries}:raise AssertionError('Archived object set changed')
    file_bytes=0;file_count=0
    for r in entries:
        p=archive/r['path']
        if r['kind']=='directory':assert p.is_dir() and not p.is_symlink()
        elif r['kind']=='symlink':assert p.is_symlink() and os.readlink(p)==r['target']
        else:
            assert p.is_file() and not p.is_symlink() and p.stat().st_size==r['bytes'],r['path']
            assert file_sha256(p)==r['sha256'],r['path'];file_count+=1;file_bytes+=r['bytes']
    if progress:progress(f'All {file_count} archived file hashes preserved')
    source=Source(allow_test=True);source_receipt=source.verify()
    assert set(map(int,m['records']))==set(map(int,source.ids))
    assert {p.name for p in paths.data_root.iterdir()}=={'train','test'}
    for pool,key in [('train','current_train_tracks'),('test','current_test_tracks')]:
        expected={id+'.parquet' for id,r in m['records'].items() if r['pool']==pool}
        assert {p.name for p in paths.asset(key,allow_test=True).iterdir()}==expected
    attrs=m['source_field_attributes'];meta_keys=[k for k in source.g.array_keys() if source.g[k].attrs.get('_ARRAY_DIMENSIONS')==['traj']]
    obs_keys=[k for k in source.g.array_keys() if source.g[k].attrs.get('_ARRAY_DIMENSIONS')==['obs']]
    metadata={k:source.g[k][:] for k in meta_keys}
    fill=json.loads(asset_path('official_drogue_correction').read_text())['records']
    boundary=json.loads(asset_path('official_drogue_boundary').read_text())['records']
    overlay=pd.concat([pd.read_parquet(asset_path('drogue_boundary_development')),
                       pd.read_parquet(asset_path('drogue_boundary_test',allow_test=True))],ignore_index=True)
    overlay_groups={int(id):x for id,x in overlay.groupby('id')}
    counts={-1:0,0:0,1:0};reasons={};pools={'train':0,'test':0};rows=0
    for n,v in enumerate(source.ids):
        id=int(v);i=source.index[id];record=m['records'][str(id)];split=str(source.cohort.loc[id,'split'])
        pool='test' if split=='test' else 'train';assert record['pool']==pool and record['historical_split']==split
        key='current_test_tracks' if pool=='test' else 'current_train_tracks';p=asset_path(key,allow_test=True)/f'{id}.parquet'
        assert not p.is_symlink() and file_sha256(p)==record['sha256']
        table=pq.read_table(p);frame=table.to_pandas();assert len(frame)==record['rows']==source.sizes[i]
        assert frame.id.dtype==np.dtype('int64') and frame.id.eq(id).all()
        baseline_path=asset_path('test_cleaned' if split=='test' else 'development_cleaned',allow_test=True)/f'{id}.parquet'
        baseline=pd.read_parquet(baseline_path)
        expected=baseline.copy()
        if str(id) in fill:
            old_key='drogue_correction_test' if split=='test' else 'drogue_correction_development'
            expected=pd.read_parquet(asset_path(old_key,allow_test=True)/'cleaned'/f'{id}.parquet')
        elif id in overlay_groups:
            o=overlay_groups[id];ix=pd.Index(expected.source_obs).get_indexer(o.source_obs);assert (ix>=0).all()
            values=expected.regime.to_numpy(copy=True);assert np.array_equal(values[ix],o.old_regime)
            values[ix]=o.regime.to_numpy();expected['regime']=values
        pd.testing.assert_frame_equal(frame[expected.columns],expected,check_exact=True)
        assert np.array_equal(frame.regime_pre_official_correction,baseline.regime)
        assert frame.pool.eq(pool).all() and frame.historical_split.eq(split).all()
        assert set(source.g.array_keys())|set(expected.columns)<=set(frame.columns)
        assert len(frame.columns)==m['fields']
        original=frame.original_within_traj_obs.to_numpy();assert np.array_equal(np.sort(original),np.arange(len(frame)))
        start,end=map(int,source.offset[i:i+2])
        for name in obs_keys:
            value=source.read(name,start,end)[original];actual_value=frame[name].to_numpy()
            assert value.dtype==actual_value.dtype and np.array_equal(value,actual_value,equal_nan=True),(id,name)
        for name in meta_keys:
            value=metadata[name][i];actual_value=frame[name].to_numpy()
            if np.asarray(value).dtype.kind=='S':
                assert all(x==bytes(value) for x in actual_value),(id,name)
                try:text=bytes(value).decode('utf-8')
                except UnicodeDecodeError:text=None
                assert all(x==text for x in frame[name+'_text']),(id,name,'decoded companion')
            else:
                assert actual_value.dtype==np.asarray(value).dtype
                assert np.array_equal(actual_value,np.repeat(value,len(frame)),equal_nan=True),(id,name)
        for name in source.g.array_keys():
            recorded=json.loads(table.schema.field(name).metadata[b'source_attributes'])
            assert recorded==attrs[name],(id,name,'attributes')
        assert frame.source_obs.is_unique
        known=frame.regime.ge(0);assert frame.loc[known,'regime_unknown_reason'].isna().all()
        unknown=frame.loc[~known,'regime_unknown_reason'];assert unknown.notna().all()
        for name,total in unknown.value_counts().items():reasons[name]=reasons.get(name,0)+int(total)
        for label in counts:counts[label]+=int(frame.regime.eq(label).sum())
        rows+=len(frame);pools[pool]+=1
        if progress and (n+1)%100==0:progress(f'Independently verified full fields for {n+1}/3741 IDs')
    assert counts=={-1:496247,0:19342607,1:19268207}
    assert reasons=={'uncertain_from_start':495555,'unresolved_boundary':9,'beyond_attached_evidence':683}
    assert rows==39107061 and pools=={'train':3224,'test':517}
    before=root/'provenance/migrations/data_release_20261016/pair_fingerprints_before.json'
    fingerprints=json.loads(before.read_text());checked=0
    for key,expected in fingerprints.items():
        id,day,scenario,target=key.split(':');id=int(id)
        df,a,e=load_track(source,id);o=origin_indices(df,a,'R');pair=generate(df,a,e,id,o,int(day),scenario)
        f=pair[0 if target=='endpoint' else 1]
        actual=hashlib.sha256(pd.util.hash_pandas_object(f,index=False).values.tobytes()+str(f.dtypes).encode()).hexdigest()
        assert actual==expected,key;checked+=1
    for rel in ['src/data3001/preprocessing/prep_core.py','src/data3001/acquisition/rules.py']:
        old=root/'provenance/migrations/data_release_20261016/before'/rel
        assert file_sha256(old)==file_sha256(root/rel),'Scientific rule changed: '+rel
    return {'passed':True,'release':m['version'],'archived_files_preserved':file_count,'archived_bytes_preserved':file_bytes,
            'IDs':3741,'rows':rows,'fields_per_ID':m['fields'],'native_source_fields_preserved':len(meta_keys)+len(obs_keys),
            'current_prepared_fields_preserved':len(m['prepared_fields']),'pools':pools,'regime_counts':counts,'unknown_reasons':reasons,
            'all_hourly_values_and_metadata_independently_equal':True,'all_original_missingness_preserved':True,
            'paired_label_fingerprints_equal':checked,'scientific_rules_unchanged':True,
            'source_contract_sha256':paths.catalog['contract_sha256'],'forecast_accuracy_evaluated':False,
            'old_support_tables':'retained as historical; not silently promoted to current',
            'elapsed_seconds':time.monotonic()-started}
