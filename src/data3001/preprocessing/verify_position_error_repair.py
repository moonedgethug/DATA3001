"""Independent HDF5-level audit of native-reference error overlays.

Does not import the production matching/decoding/classification implementation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import resource
import time

import h5py
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
GOOD={'restored_scale','verified_unchanged','recovered_from_reference'}
CUTOFF=pd.Timestamp('2020-06-30T23:00:00Z').timestamp()


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''): h.update(block)
    return h.hexdigest()


def attr(obj,key,default=None):
    val=obj.attrs.get(key,default)
    if isinstance(val,np.ndarray) and val.size==1:val=val.reshape(-1)[0]
    if isinstance(val,(bytes,np.bytes_)):return val.decode().strip('\x00')
    return val


def number(value):
    if isinstance(value,(bytes,np.bytes_)):value=value.decode()
    if isinstance(value,str):
        s=value.strip()
        if not re.fullmatch(r'[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?[fFdD]?',s):
            raise ValueError('Non-numeric metadata')
        return float(s[:-1] if s[-1:] in 'fFdD' else s)
    return float(value)


def unpack(dataset, indices=None):
    if indices is None:raw=np.asarray(dataset[:]).reshape(-1)
    else:
        unique=np.unique(indices)
        raw=np.asarray(dataset[0,unique] if dataset.ndim==2 else dataset[unique]).reshape(-1)
    missing=~np.isfinite(raw)
    for name in ['_FillValue','missing_value']:
        marker=attr(dataset,name)
        if marker is not None:
            for x in np.atleast_1d(marker):
                missing |= raw == np.asarray(number(x),dtype=dataset.dtype)
    invalid=np.zeros(len(raw),bool)
    if 'valid_range' in dataset.attrs:
        lo,hi=[number(x) for x in dataset.attrs['valid_range']];invalid |= (raw<lo)|(raw>hi)
    if 'valid_min' in dataset.attrs:invalid |= raw<number(attr(dataset,'valid_min'))
    if 'valid_max' in dataset.attrs:invalid |= raw>number(attr(dataset,'valid_max'))
    result=raw.astype(float)
    scale=number(attr(dataset,'scale_factor',1));offset=number(attr(dataset,'add_offset',0))
    if not np.isfinite(scale) or not np.isfinite(offset) or scale<=0:raise ValueError('Bad scale')
    result[missing]=np.nan
    result[~missing]=result[~missing]*scale+offset
    return raw,result,missing,invalid


def seconds(dataset):
    if attr(dataset,'calendar','standard') not in ['standard','gregorian','proleptic_gregorian']:
        raise ValueError('Unsupported time calendar')
    units=attr(dataset,'units')
    match=re.fullmatch(r'(seconds|hours|days) since (.+)',units)
    if not match:raise ValueError('Unsupported time encoding')
    epoch=pd.Timestamp(match[2].replace(' UTC','+00:00'))
    if epoch.tzinfo is None:epoch=epoch.tz_localize('UTC')
    _,v,missing,_=unpack(dataset)
    if missing.any():raise ValueError('Missing time')
    return v*{'seconds':1,'hours':3600,'days':86400}[match[1]]+epoch.timestamp()


def equivalent_position(a,b):
    alon=np.float32((a[0]+180)%360-180);blon=np.float32((b[0]+180)%360-180)
    return alon==blon and np.float32(a[1])==np.float32(b[1])


def reference_rows(path,ident,targets):
    """Reconstruct source eligibility and matching without production helpers."""
    result={}
    with h5py.File(path,'r') as h:
        raw=h['ID'][:]
        native=int(raw.tobytes().decode().strip('\x00 ')) if raw.dtype.kind=='S' else int(raw.reshape(-1)[0])
        if native!=ident and str(attr(h,'imei','')).strip()!=str(ident):
            return {int(x.source_obs):{'status':'source_metadata_unresolved'} for x in targets.itertuples()}
        history=attr(h,'history','').lower()
        reason=None
        if not re.search(r'version\s+v?2\.00\b',history):reason='version_unresolved'
        elif (int(h['typedeath'][:].reshape(-1)[0]) not in [1,2,3,4,5,6]
              or pd.Timestamp(attr(h,'time_coverage_end')).timestamp()>CUTOFF):
            reason='estimation_version_unresolved'
        elif not 0<seconds(h['end_date'])[0]<=CUTOFF:
            reason='estimation_version_unresolved'
        for axis,unit in [('lon','degrees_east'),('lat','degrees_north')]:
            v=h['err_'+axis]
            if attr(v,'units')!=unit or '95% confidence interval' not in attr(v,'long_name','').lower():reason='semantics_unresolved'
        if reason:return {int(x.source_obs):{'status':reason} for x in targets.itertuples()}
        times=seconds(h['time']);time_map={}
        for ix,epoch in enumerate(times):time_map.setdefault(float(epoch),[]).append(ix)
        selected=sorted({j for t in targets.time for j in time_map.get(float(t),[])})
        cols={}
        if selected:
            for key in ['lon','lat','err_lon','err_lat']:
                alias=key if key in h else {'lon':'longitude','lat':'latitude'}[key]
                raw,val,missing,invalid=unpack(h[alias],selected)
                cols[key]={j:(float(a),float(b),bool(c),bool(d)) for j,a,b,c,d in zip(selected,raw,val,missing,invalid)}
        for x in targets.itertuples():
            idx=time_map.get(float(x.time),[])
            if not idx:result[int(x.source_obs)]={'status':'time_unmatched'};continue
            if len(idx)>1:
                a=[cols[k][idx[0]][0] for k in cols]
                if any(not np.array_equal(a,[cols[k][j][0] for k in cols],equal_nan=True) for j in idx[1:]):
                    result[int(x.source_obs)]={'status':'duplicate_conflict'};continue
            j=idx[0];r={'status':'matched','indices':idx,'longitude':cols['lon'][j][1],
                       'latitude':cols['lat'][j][1]}
            if not equivalent_position((x.lon,x.lat),(r['longitude'],r['latitude'])):r['status']='coordinate_changed'
            r['lon']=cols['err_lon'][j];r['lat']=cols['err_lat'][j]
            result[int(x.source_obs)]=r
    return result


def axis_result(old,ref,axis,latitude):
    raw,val,missing,invalid=ref
    if invalid and not missing:return np.nan,'reference_invalid'
    if missing or not math.isfinite(val):return np.nan,'reference_missing'
    if val<0:return np.nan,'reference_invalid'
    if val==0:return np.nan,'zero_unresolved'
    if (axis=='lon' and val>=180) or (axis=='lat' and (latitude-val < -90 or latitude+val>90)):
        return np.nan,'geometry_review_required'
    if not math.isfinite(old) or old<0:return val,'recovered_from_reference'
    if old>0:
        ratio=val/old
        if abs(ratio-1)<=1e-6:return val,'verified_unchanged'
        if abs(ratio-100000)<=.1:return val,'restored_scale'
    return np.nan,'unexplained_difference'


def independent_expected(targets,registry,run):
    rows=[]
    for ident,group in targets.groupby('id',sort=True):
        refs=[]
        for entry in registry:
            if entry['id']!=ident or entry['status']!='available':continue
            path=run/entry['path'];assert digest(path)==entry['sha256']
            try:r=reference_rows(path,int(ident),group)
            except (ValueError,KeyError,IndexError):
                r={int(t.source_obs):{'status':'source_metadata_unresolved'} for t in group.itertuples()}
            refs.append((r,entry['sha256']))
        for t in group.itertuples():
            candidates=[(r[int(t.source_obs)],sha) for r,sha in refs]
            good=[(r,sha) for r,sha in candidates if r['status']=='matched']
            e={'id':int(ident),'source_obs':int(t.source_obs)}
            if not good:
                if candidates:
                    preferred=next(((r,s) for r,s in candidates if r['status']=='coordinate_changed'),candidates[0])
                    status=preferred[0]['status']
                else:
                    status='not_fetched_budget' if any(r['id']==ident and r['status']=='not_fetched_budget' for r in registry) else 'source_missing'
                e.update(match_status=status,status_lon=status,status_lat=status,
                         repaired_err_lon=np.nan,repaired_err_lat=np.nan,ci_2d_usable=False)
            else:
                r,sha=good[0]
                conflict=False
                for other,_ in good[1:]:
                    for axis in ['lon','lat']:
                        a=r[axis][1];b=other[axis][1]
                        if not ((np.isnan(a) and np.isnan(b)) or np.float32(a)==np.float32(b)):conflict=True
                e.update(match_status='reference_conflict' if conflict else 'matched',source_sha256=sha,
                         source_indices=json.dumps(r['indices']),ref_lon=r['longitude'],ref_lat=r['latitude'])
                for axis in ['lon','lat']:
                    val,status=(np.nan,'reference_conflict') if conflict else axis_result(getattr(t,'original_err_'+axis),r[axis],axis,t.lat)
                    e['repaired_err_'+axis]=val;e['status_'+axis]=status
                    e['ref_err_'+axis]=r[axis][1];e['raw_ref_err_'+axis]=r[axis][0]
                e['ci_2d_usable']=all(e['status_'+axis] in GOOD for axis in ['lon','lat'])
            rows.append(e)
    return pd.DataFrame(rows).sort_values(['id','source_obs']).reset_index(drop=True)


def verify(run,phase):
    start=time.monotonic();folder=run/phase
    approval=json.loads((run/'approval.json').read_text())
    assert digest(run/'approved_plan.md')==approval['plan_sha256']
    targets=pd.read_parquet(run/'target_keys.parquet')
    assert digest(run/'target_keys.parquet')==approval['target_sha256']
    ids=approval['diagnostic_ids'] if phase=='pilot' else approval['all_ids']
    targets=targets[targets.id.isin(ids)].sort_values(['id','source_obs']).reset_index(drop=True)
    overlay=pd.read_parquet(folder/'error_overlay.parquet').sort_values(['id','source_obs']).reset_index(drop=True)
    assert len(overlay)==len(targets) and not overlay.duplicated(['id','source_obs']).any()
    pd.testing.assert_frame_equal(overlay[targets.columns],targets,check_exact=True)
    # Verify all target values against canonical files independently of the target builder.
    ds=json.loads((ROOT/'configs/dataset_manifest.json').read_text())
    for ident,g in targets.groupby('id'):
        spec=ds['records'][str(ident)];assert spec['pool']=='train'
        actual=pd.read_parquet(ROOT/spec['path'],columns=['source_obs','time','lon','lat','err_lon','err_lat'],
                              filters=[('source_obs','in',g.source_obs.tolist())]).sort_values('source_obs').reset_index(drop=True)
        b=g.sort_values('source_obs').reset_index(drop=True)
        for col in ['source_obs','time','lon','lat','err_lon','err_lat']:
            key='original_'+col if col.startswith('err_') else col
            np.testing.assert_array_equal(actual[col],b[key])
    registry=json.loads((folder/'source_registry.json').read_text())
    expected=independent_expected(targets,registry,run)
    for col in ['id','source_obs','match_status','status_lon','status_lat','repaired_err_lon','repaired_err_lat','ci_2d_usable']:
        pd.testing.assert_series_equal(overlay[col],expected[col],check_names=False,check_dtype=False,check_exact=True)
    matched=expected.match_status.isin(['matched','reference_conflict'])
    for col in ['source_sha256','source_indices','ref_lon','ref_lat','ref_err_lon','ref_err_lat','raw_ref_err_lon','raw_ref_err_lat']:
        pd.testing.assert_series_equal(overlay.loc[matched,col],expected.loc[matched,col],check_names=False,check_dtype=False,check_exact=True)
    np.testing.assert_array_equal(overlay.loc[matched,'source_epoch'],overlay.loc[matched,'time'])
    # The matching policy audited for this release uses native float32 precision.
    # Fail the audit if an accepted reference has another storage/units profile.
    referenced={s for values in overlay.loc[matched,'reference_sources'] for s in json.loads(values)}
    native_profiles=Counter()
    for entry in registry:
        if entry.get('sha256') not in referenced:continue
        with h5py.File(run/entry['path'],'r') as h:
            for axis,unit in [('lon','degrees_east'),('lat','degrees_north')]:
                name=axis if axis in h else {'lon':'longitude','lat':'latitude'}[axis]
                for key in [name,'err_'+axis]:
                    d=h[key]
                    assert d.dtype==np.dtype('float32'),(entry['id'],key,str(d.dtype))
                    assert attr(d,'units')==unit,(entry['id'],key,attr(d,'units'))
                    native_profiles[(key,str(d.dtype),unit)]+=1
    exceptions=pd.read_parquet(folder/'exceptions.parquet')
    pd.testing.assert_frame_equal(exceptions.reset_index(drop=True),overlay.loc[~overlay.ci_2d_usable].reset_index(drop=True))
    for relative,sha in approval['protected_files'].items(): assert digest(ROOT/relative)==sha,relative
    # Existing diagnosed cases must not be silently erased or converted to positive certainty.
    trace=ROOT/'provenance/reviews/position_error_s4_e8_source_trace'
    old=json.loads((trace/'ncei_1_1_exceptions.json').read_text())['samples']
    lookup=overlay.set_index(['id','source_obs']);regression=Counter()
    for case in old:
        key=(case['id'],case['source_obs'])
        if key not in lookup.index:continue
        row=lookup.loc[key];value=case['err_lat']['canonical']
        if value>1e-5:
            assert row.status_lat=='verified_unchanged' and row.repaired_err_lat==case['err_lat']['archive_raw'];regression['unscaled_latitude_preserved']+=1
        if value<0:
            assert row.status_lat=='zero_unresolved' and np.isnan(row.repaired_err_lat);regression['negative_to_zero_unresolved']+=1
    anchor_ids=[7647,99004,300234066710170]
    pairs=pd.read_parquet(ROOT/'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/training_coordinates.parquet')
    anchor=pairs[pairs.id.isin(anchor_ids)][['id','endpoint_source_obs']].rename(columns={'endpoint_source_obs':'source_obs'}).drop_duplicates()
    z=anchor.merge(overlay,on=['id','source_obs'],validate='one_to_one')
    assert len(z)==1604 and z.status_lon.eq('restored_scale').all() and z.status_lat.eq('restored_scale').all()
    regression['anchor_endpoint_values']=3208
    resources=json.loads((folder/'resources.json').read_text())
    clock=json.loads((run/'resource_clock.json').read_text())
    # Conservative twofold projection for remaining network/reconciliation work.
    projected=resources.get('projection_base_seconds',resources['elapsed_seconds'])*338/19*2 if phase=='pilot' else resources['elapsed_seconds']
    peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    assert peak_rss<=4*2**30,'Independent verifier exceeds the approved memory bound'
    result={'passed':True,'phase':phase,'independent_engine':'h5py raw HDF5, separate time/metadata/matching/classification implementation',
            'IDs':len(ids),'target_rows':len(targets),'accepted_lon':int(overlay.status_lon.isin(GOOD).sum()),
            'accepted_lat':int(overlay.status_lat.isin(GOOD).sum()),'ci_2d_usable':int(overlay.ci_2d_usable.sum()),
            'matched_rows':int(overlay.match_status.eq('matched').sum()),
            'status_lon':overlay.status_lon.value_counts().to_dict(),'status_lat':overlay.status_lat.value_counts().to_dict(),
            'match_status':overlay.match_status.value_counts().to_dict(),'regression_cases':dict(regression),
            'protected_files_unchanged':len(approval['protected_files']),'validation_seconds':time.monotonic()-start,
            'peak_rss_bytes':peak_rss,
            'referenced_source_hashes':len(referenced),
            'native_storage_profiles':[{'variable':k[0],'dtype':k[1],'units':k[2],'source_entries':v} for k,v in native_profiles.items()],
            'projected_full_seconds_with_2x_margin':projected,
            'pilot_budget_projection_passed':(projected<7200 and resources['elapsed_seconds']<1200 and time.time()<clock['deadline_epoch']) if phase=='pilot' else None,
            'resource_deadline_passed':time.time()<clock['deadline_epoch'],
            'models_run':False,'final_test_accessed':False,'outer_endpoint_errors_accessed':False}
    with (folder/'verification.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--phase',choices=['pilot','full'],required=True)
    a=p.parse_args();verify(a.run.resolve(),a.phase)
