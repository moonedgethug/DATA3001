"""Reproducible recovery-tail audit and official-background SST comparison.

Run prepare, compare, then finalize. Canonical files are always read-only.
"""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import sqlite3
import threading
import sys
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import requests
import netCDF4
from data3001.dataset import manifest
from data3001.paths import project_paths, file_sha256, ensure_output_path
from data3001.model_input_cleaning import recovery_tail_mask, sst_review_mask, confirmed_high_replacement
from data3001.sst_completion import temperature_sidecar
from data3001.sst_reconstruction import stencil, decode_zarr_chunk
from data3001.sst_sparse import sparse_temperature, apply_sparse_patch

RUN = 'sst_anomaly_recovery_20261017_v1'
PARENT = 'sst_sparse_completion_20261017_v2'
CONTRACT = '6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446'
BUCKET = 'https://noaa-cdr-sea-surface-temp-optimum-interpolation-pds.s3.amazonaws.com/'
ROOT = project_paths().root
DEST = ROOT / 'results/runs' / RUN
BASE = ROOT / 'results/runs/sst_reconstruction_20261016_v1'
KEYS = ['id', 'source_obs']


def save_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False, default=str)+'\n')


def prepare():
    ensure_output_path('results/runs/' + RUN)
    if DEST.exists():
        raise FileExistsError(DEST)
    assert file_sha256(ROOT/'docs/contract/data_contract_v1.0.xlsx') == CONTRACT
    DEST.mkdir()
    records = manifest()['records']
    cols = ['id','source_obs','time','time_UTC','lat','lon','sst','sst1','sst2',
            'flg_sst','flg_sst1','flg_sst2','err_sst','in_R','end_date','typedeath']
    def scan(item):
        sid, record = item
        path = ROOT/record['path']
        assert file_sha256(path) == record['sha256']
        assert len(pq.read_schema(path).names) == 130
        f = pq.read_table(path, columns=cols).to_pandas()
        assert len(f) == record['rows']
        tail = recovery_tail_mask(f)
        excluded = f.loc[tail, KEYS+['time','time_UTC','end_date','typedeath','in_R']].copy()
        excluded['pool'] = record['pool']
        selected = sst_review_mask(f)
        q = f.loc[selected].copy()
        q['pool'] = record['pool']
        q['native_C'] = q.sst.astype(float)-273.15
        q['recovery_tail'] = tail[selected]
        s = f.sst.to_numpy(dtype=float)-273.15
        t = f.time.to_numpy()
        q['previous_native_C'] = np.r_[np.nan, s[:-1]][selected]
        q['next_native_C'] = np.r_[s[1:], np.nan][selected]
        q['previous_gap_seconds'] = np.r_[np.nan, np.diff(t)][selected]
        q['next_gap_seconds'] = np.r_[np.diff(t), np.nan][selected]
        return q, excluded, {'id':int(sid),'pool':record['pool'],'source_rows':len(f),
                              'excluded_rows':int(tail.sum()),'source_sha256':record['sha256'],
                              'recovered':int(f.typedeath.iloc[0]) == 2}
    with ThreadPoolExecutor(max_workers=4) as ex:
        scanned = list(ex.map(scan, records.items()))
    q = pd.concat([r[0] for r in scanned], ignore_index=True).sort_values(KEYS).reset_index(drop=True)
    exclusions = pd.concat([r[1] for r in scanned], ignore_index=True)
    q.to_parquet(DEST/'candidates.parquet', index=False)
    exclusions.to_parquet(DEST/'recovery_exclusions.parquet', index=False)
    pd.DataFrame([r[2] for r in scanned]).to_csv(DEST/'input_inventory.csv', index=False)
    assert sum(r[2]['source_rows'] for r in scanned) == 39107061
    deps = ['configs/dataset_manifest.json','configs/assets.json',
            'docs/contract/data_contract_v1.0.xlsx','docs/sst_anomaly_recovery_plan.md',
            'src/data3001/model_input_cleaning.py','src/data3001/sst_anomaly_run.py',
            'src/data3001/sst_sparse.py','src/data3001/sst_reconstruction.py',
            'tests/test_model_input_cleaning.py',
            f'results/runs/{PARENT}/config.json', f'results/runs/{PARENT}/verification.json',
            f'results/runs/{PARENT}/output_manifest.json',
            str((BASE/'nodes.parquet').relative_to(ROOT)),
            str((BASE/'node_sst.npy').relative_to(ROOT)),str((BASE/'node_err.npy').relative_to(ROOT))]
    save_json(DEST/'config.json', {'run_id':RUN, 'parent_run':PARENT,
        'created_UTC':datetime.now(timezone.utc).isoformat(),'contract_sha256':CONTRACT,
        'authorization':'User: exclude vessel recovery tails; compare suspect SST to official source and replace confirmed high temperatures',
        'screen':'QC4/5 total SST >40 C, < -2.05 C, or either endpoint of >5 K change within <=1 h with both endpoints QC4/5',
        'replacement':'Native >45 C; finite official daily background in [-3,40] C and >=5 K cooler; lower-temperature discrepancies review-only',
        'recovery_cutoff':'typedeath==2 and numeric time > numeric end_date; conservative last-good cutoff, not pickup timestamp',
        'source_match':'Actual location, same UTC date of OISST v2.1 final; daily background, not hourly truth',
        'dependencies':{name:file_sha256(ROOT/name) for name in deps}})
    print(json.dumps({'candidates':len(q),'candidate_IDs':q.id.nunique(),
                      'recovery_excluded':len(exclusions),'excluded_IDs':exclusions.id.nunique()}), flush=True)


def check_dependencies():
    config = json.loads((DEST/'config.json').read_text())
    for name, digest in config['dependencies'].items():
        assert file_sha256(ROOT/name) == digest, name
    return config


def compare():
    check_dependencies()
    q = pd.read_parquet(DEST/'candidates.parquet')
    i,j,u,v = stencil(q.lon, q.lat)
    day = np.floor(q.time/86400).astype(np.int64).to_numpy()
    nodekeys = np.column_stack([((day*720+j)*1440+i),((day*720+j)*1440+(i+1)%1440),
                               ((day*720+j+1)*1440+i),((day*720+j+1)*1440+(i+1)%1440)])
    unique, inverse = np.unique(nodekeys, return_inverse=True)
    nodes = pd.DataFrame({'key':unique})
    nodes['i'] = nodes.key%1440
    nodes['j'] = (nodes.key//1440)%720
    nodes['day'] = nodes.key//(1440*720)
    old = pd.read_parquet(BASE/'nodes.parquet')
    loc = pd.Index(old.key).get_indexer(nodes.key)
    available = loc >= 0
    values = np.full(len(nodes), np.nan)
    errors = np.full(len(nodes), np.nan)
    values[available] = np.load(BASE/'node_sst.npy')[loc[available]]
    errors[available] = np.load(BASE/'node_err.npy')[loc[available]]
    used_objects=[]
    object_lock=threading.Lock()
    nc_lock=threading.Lock()
    (DEST/'sources').mkdir(exist_ok=True)
    cache_path=BASE/'external_noaa.sqlite'
    def object_bytes(key, conn):
        url=BUCKET+key
        row=conn.execute('select url,encoding,payload,sha256 from objects where key=?',(key,)).fetchone()
        if row:
            raw=gzip.decompress(row[2]) if row[1]=='gzip' else row[2]
            assert row[0]==url and hashlib.sha256(raw).hexdigest()==row[3]
            receipt={'key':key,'url':url,'sha256':row[3],'storage':'verified_parent_cache'}
        else:
            token=hashlib.sha256(key.encode()).hexdigest()
            p=DEST/'sources'/token
            rp=p.with_suffix('.json')
            if p.exists() and rp.exists():
                receipt=json.loads(rp.read_text());raw=p.read_bytes()
                assert receipt['url']==url and hashlib.sha256(raw).hexdigest()==receipt['sha256']
            else:
                r=requests.get(url,timeout=(10,40));r.raise_for_status();raw=r.content
                receipt={'key':key,'url':url,'sha256':hashlib.sha256(raw).hexdigest(),
                         'storage':'sources/'+token,'retrieved_UTC':datetime.now(timezone.utc).isoformat()}
                p.write_bytes(raw);save_json(rp,receipt)
        with object_lock:used_objects.append(receipt)
        return raw
    def daily(pair):
        day,g=pair;day=int(day)
        date=pd.to_datetime(day,unit='D',utc=True)
        pre=f'data/v2.1/avhrr-zarr/{date:%Y/%m}/oisst-avhrr-v02r01.{date:%Y%m%d}.zarr/'
        conn=sqlite3.connect(f'file:{cache_path}?mode=ro',uri=True)
        try:
            meta=json.loads(object_bytes(pre+'.zmetadata',conn))['metadata']
            glob=meta['.zattrs']
            assert 'Version 2.1 - Final' in glob['title'] and 'AVHRR-ONLY' in glob['summary']
            assert glob['id']==f'oisst-avhrr-v02r01.{date:%Y%m%d}.nc'
            assert glob['time_coverage_start'].startswith(f'{date:%Y-%m-%d}')
            actual={}
            for coord in ['lat','lon','time']:
                actual[coord]=decode_zarr_chunk(object_bytes(pre+coord+'/0',conn),
                                    meta[coord+'/.zarray'],meta[coord+'/.zattrs'])
            np.testing.assert_array_equal(actual['lat'],np.arange(720)*.25-89.875)
            np.testing.assert_array_equal(actual['lon'],np.arange(1440)*.25+.125)
            units=meta['time/.zattrs']['units'];assert units.startswith('days since ')
            assert (pd.Timestamp(units[len('days since '):],tz='UTC')+
                    pd.Timedelta(days=float(actual['time'][0])))==date+pd.Timedelta(hours=12)
            found=np.full(len(g),np.nan);sd=found.copy()
            for var,out,limits in [('sst',found,(-300,4500)),('err',sd,(0,1000))]:
                spec=meta[var+'/.zarray'];attrs=meta[var+'/.zattrs']
                assert spec['shape']==[1,1,720,1440] and spec['chunks']==[1,1,180,180]
                assert spec['dtype']=='<i2' and spec['fill_value']==-999
                assert attrs['units']=='Celsius' and attrs['scale_factor']==.01
                assert attrs.get('add_offset',0)==0 and (attrs['valid_min'],attrs['valid_max'])==limits
                codes=(g.j//180)*8+g.i//180
                for code in np.unique(codes):
                    take=(codes==code).to_numpy();rows=g.iloc[np.flatnonzero(take)]
                    key=pre+f'{var}/0.0.{int(code)//8}.{int(code)%8}'
                    chunk=decode_zarr_chunk(object_bytes(key,conn),spec,attrs)
                    out[take]=chunk[0,0,(rows.j%180).to_numpy(),(rows.i%180).to_numpy()]
            return g.index.to_numpy(),found,sd
        finally:conn.close()
    failures=[]
    groups=list(nodes.loc[~available].groupby('day'))
    print('Comparison nodes',len(nodes),'new nodes',int((~available).sum()),'source days',len(groups),flush=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        from concurrent.futures import as_completed
        futures={ex.submit(daily,g):int(g[0]) for g in groups}
        for n,future in enumerate(as_completed(futures),1):
            try:ids,vals,err=future.result();values[ids]=vals;errors[ids]=err
            except Exception as exc:failures.append({'day':futures[future],'error':repr(exc)})
            if n%100==0:print('Official source days',n,'/',len(groups),flush=True)
    save_json(DEST/'source_receipts.json',list({r['key']:r for r in used_objects}.values()))
    save_json(DEST/'source_failures.json',failures)
    # Missing responses remain NaN and cannot authorize a temperature change.
    corners=values[inverse.reshape(-1,4)]
    sd=errors[inverse.reshape(-1,4)]
    left=i*.25+.125;left=(left+180)%360-180
    bottom=j*.25-89.875
    points=np.stack([left[:,None]+[0.,.25,0.,.25],bottom[:,None]+[0.,0.,.25,.25]],axis=2)
    est=sparse_temperature(q.lon,q.lat,points,corners,u,v)
    q['background_C']=est['temperature_C']
    q['native_minus_background_K']=q.native_C-q.background_C
    q['background_method']=est['method']
    q['finite_source_count']=est['finite_source_count']
    q['day']=day;q['u']=u;q['v']=v
    for k in range(4):
        q[f'corner{k}_C']=corners[:,k];q[f'corner{k}_SD_K']=sd[:,k]
        q[f'weight{k}']=est['weights'][:,k];q[f'point{k}_lon']=points[:,k,0];q[f'point{k}_lat']=points[:,k,1]
        q[f'nodekey{k}']=nodekeys[:,k]
    needed=est['weights']>0
    bound=np.sum(est['weights']*np.where(np.isfinite(sd),sd,0.),axis=1)
    bound[~np.all(~needed|np.isfinite(sd),axis=1)]=np.nan
    q['source_sd_bound_K']=bound
    q['replace']=confirmed_high_replacement(q.native_C,q.background_C)&~q.recovery_tail
    q['disposition']=np.where(q['replace'],'replace_confirmed_native_above_45C',
        np.where(q.recovery_tail,'excluded_recovery_tail',
        np.where(~np.isfinite(q.background_C),'official_background_unavailable',
        np.where(abs(q.native_minus_background_K)>5.,'large_discrepancy_review_only','background_comparison_retained'))))
    q.to_parquet(DEST/'comparisons.parquet',index=False)
    nodes['temperature_C']=values;nodes['source_sd_K']=errors
    nodes['inherited_verified_node']=available
    nodes.to_parquet(DEST/'source_nodes.parquet',index=False)
    print(q.groupby('disposition').size().to_string(),flush=True)


def finalize():
    check_dependencies()
    q=pd.read_parquet(DEST/'comparisons.parquet')
    entries=[]
    patch_fields=['sst_use_K','sst_method','sst_reason','availability_scope',
                  'sst_source_sd_bound_K','sst_total_se_K','sst_error_kind']
    for sid,g in q[q['replace']].groupby('id'):
        old,_=temperature_sidecar(int(sid),run=PARENT)
        patch=g[KEYS].copy();patch['sst_use_K']=g.background_C.to_numpy()+273.15
        patch['sst_method']=g.background_method.to_numpy(dtype=np.int8)
        patch['sst_reason']='confirmed_native_high_replaced_by_daily_oisst'
        patch['availability_scope']='retrospective_only'
        patch['sst_source_sd_bound_K']=g.source_sd_bound_K.to_numpy()
        patch['sst_total_se_K']=np.nan
        patch['sst_error_kind']='official_background_source_only_bound; total_reconstruction_error_unknown'
        out=apply_sparse_patch(old,patch)
        selected=old.source_obs.isin(patch.source_obs)
        pd.testing.assert_frame_equal(old.loc[~selected].reset_index(drop=True),out.loc[~selected].reset_index(drop=True))
        pd.testing.assert_frame_equal(old.drop(columns=patch_fields),out.drop(columns=patch_fields))
        pool=manifest()['records'][str(sid)]['pool']
        folder=DEST/pool;folder.mkdir(exist_ok=True)
        path=folder/f'{sid}.parquet';out.to_parquet(path,index=False)
        entries.append({'id':int(sid),'path':str(path.relative_to(ROOT)),
                        'sha256':file_sha256(path),'pool':pool,'rows':len(out)})
    save_json(DEST/'output_manifest.json',entries)
    # Recompute every replacement separately from stored corner values/weights.
    for row in q[q['replace']].itertuples(index=False):
        actual=sum(getattr(row,f'weight{k}')*getattr(row,f'corner{k}_C')
                   for k in range(4) if getattr(row,f'weight{k}')>0)
        assert abs(actual-row.background_C)<1e-10
    inventory=pd.read_csv(DEST/'input_inventory.csv')
    for sid,record in manifest()['records'].items():
        assert file_sha256(ROOT/record['path'])==record['sha256']
    config=json.loads((DEST/'config.json').read_text())
    exclusions=pd.read_parquet(DEST/'recovery_exclusions.parquet')
    summary={'status':'passed','config_sha256':file_sha256(DEST/'config.json'),
        'canonical_rows':int(inventory.source_rows.sum()),'canonical_fields':130,
        'native_files_preserved':len(inventory),'whole_ID_pools_unchanged':True,
        'recovered_IDs':int(inventory.recovered.sum()),'excluded_recovery_rows':len(exclusions),
        'excluded_recovery_IDs':exclusions.id.nunique(),'excluded_recovery_in_R':int(exclusions.in_R.sum()),
        'model_view_rows_after_recovery_exclusion':int(inventory.source_rows.sum())-len(exclusions),
        'SST_review_candidates':len(q),'candidate_IDs':q.id.nunique(),
        'official_background_matched':int(np.isfinite(q.background_C).sum()),
        'high_replaced':int(q['replace'].sum()),'high_replaced_in_R':int((q['replace']&q.in_R).sum()),
        'high_replaced_IDs':q.loc[q['replace'],'id'].nunique(),
        'lower_temperature_large_discrepancy_review_only':int(q.disposition.eq('large_discrepancy_review_only').sum()),
        'source_failures':len(json.loads((DEST/'source_failures.json').read_text()))}
    save_json(DEST/'verification.json',summary)
    files=['config.json','candidates.parquet','comparisons.parquet','recovery_exclusions.parquet',
           'input_inventory.csv','source_nodes.parquet','source_receipts.json','source_failures.json','output_manifest.json']
    save_json(DEST/'artifact_manifest.json',{name:file_sha256(DEST/name) for name in files})
    pd.DataFrame([summary]).to_csv(DEST/'summary.csv',index=False)
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    {'prepare':prepare,'compare':compare,'finalize':finalize}[sys.argv[1]]()
