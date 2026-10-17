"""Versioned pilot temperature views; no mutation of canonical observations."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from data3001.sst_reconstruction import bilinear
from data3001.sst_coastal import three_corner_temperature

DEFAULT_RUN='sst_pilot_completion_20261017_v1'


def patch_temperature(base,patch):
    keys=['id','source_obs']
    fields={'sst_use_K','sst_method','sst_reason','availability_scope',
            'linear_anchor_left_source_obs','linear_anchor_right_source_obs',
            'sst_source_sd_bound_K','sst_total_se_K','sst_error_kind'}
    if not set(patch).issubset(base) or not set(patch).difference(keys).issubset(fields):
        raise ValueError('Only existing temperature sidecar fields may change')
    if base.duplicated(keys).any() or patch.duplicated(keys).any():
        raise ValueError('Duplicate temperature keys')
    loc=pd.MultiIndex.from_frame(base[keys]).get_indexer(pd.MultiIndex.from_frame(patch[keys]))
    if (loc<0).any():raise ValueError('Patch key absent from parent')
    if not base.iloc[loc].sst_method.eq(3).all() or not base.iloc[loc].sst_use_K.isna().all():
        raise ValueError('Existing accepted values must remain unchanged')
    if not patch.sst_method.isin([6,7,8,9,10]).all() or not np.isfinite(patch.sst_use_K).all():
        raise ValueError('Unapproved reconstruction method or nonfinite estimate')
    out=base.copy(deep=True)
    for c in patch.columns.difference(keys):out.iloc[loc,out.columns.get_loc(c)]=patch[c].to_numpy()
    return out


def grid_temperature(lon,lat,longitudes,latitudes,temperature):
    """Sample actual source axes; do not create temperatures for missing nodes."""
    x=np.asarray(longitudes,float);y=np.asarray(latitudes,float);t=np.asarray(temperature,float)
    if t.shape!=(len(y),len(x)) or len(x)<2 or len(y)<2:raise ValueError('Unexpected source grid')
    if x[0]>x[-1]:x=x[::-1];t=t[:,::-1]
    if y[0]>y[-1]:y=y[::-1];t=t[::-1]
    if not (np.diff(x)>0).all() or not (np.diff(y)>0).all():raise ValueError('Nonmonotone source axes')
    empty={'method':3,'temperature_C':np.nan,'weights':np.array([]),
           'source_points':np.empty((0,2)),'corners_C':np.array([]),'reason':'not_bracketed'}
    if not (x[0]<=lon<=x[-1] and y[0]<=lat<=y[-1]):return empty
    ix=np.flatnonzero(np.abs(x-lon)<=1e-12);iy=np.flatnonzero(np.abs(y-lat)<=1e-12)
    if len(ix) and len(iy) and np.isfinite(t[iy[0],ix[0]]):
        return {'method':7,'temperature_C':float(t[iy[0],ix[0]]),'weights':np.array([1.]),
                'source_points':np.array([[x[ix[0]],y[iy[0]]]]),
                'corners_C':np.array([t[iy[0],ix[0]]]),'reason':'fine_exact_point'}
    i=min(max(np.searchsorted(x,lon,side='right')-1,0),len(x)-2)
    j=min(max(np.searchsorted(y,lat,side='right')-1,0),len(y)-2)
    u=(lon-x[i])/(x[i+1]-x[i]);v=(lat-y[j])/(y[j+1]-y[j])
    values=np.array([t[j,i],t[j,i+1],t[j+1,i],t[j+1,i+1]])
    points=np.array([[x[i],y[j]],[x[i+1],y[j]],[x[i],y[j+1]],[x[i+1],y[j+1]]])
    n=np.isfinite(values).sum()
    if n==4:
        value,w=bilinear(u,v,values);method=8;reason='fine_bilinear'
    elif n==3:
        r=three_corner_temperature([u],[v],[values]);value=r['temperature_C'][0]
        w=r['weights'][0];method={4:9,5:10,3:3}[int(r['method'][0])]
        reason={9:'fine_triangle',10:'fine_outside_normalized',3:'zero_numeric_support'}[method]
    else:
        value=np.nan;w=np.zeros(4);method=3;reason='fewer_than_three_source_corners'
    return {'method':method,'temperature_C':float(value),'weights':w,
            'source_points':points,'corners_C':values,'u':float(u),'v':float(v),'reason':reason}


def temperature_sidecar(id, *, run=DEFAULT_RUN):
    """Resolve a hash-checked parent chain; canonical access is guarded by the reader."""
    from data3001.paths import project_paths,file_sha256
    root=project_paths().root;seen=set()
    while True:
        directory=(root/'results/runs'/run).resolve()
        if (not directory.is_relative_to((root/'results/runs').resolve())
                or directory in seen):raise ValueError('Invalid temperature parent chain')
        seen.add(directory)
        receipt=json.loads((directory/'verification.json').read_text())
        if receipt['status']!='passed':raise ValueError('Unverified temperature run')
        if 'config_sha256' in receipt:
            # The baseline v1 receipt pins its initial configuration; incremental
            # receipts pin their own complete configuration.
            if file_sha256(directory/'config.json')!=receipt['config_sha256']:
                raise ValueError('Temperature configuration checksum changed')
        entries=json.loads((directory/'output_manifest.json').read_text())
        record=next((r for r in entries if int(r['id'])==int(id)),None)
        if record is not None:
            path=Path(record['path'])
            path=root/path if path.parts[0]=='results' else directory/path
            if (path.is_symlink() or not path.resolve().is_relative_to((root/'results/runs').resolve())
                    or file_sha256(path)!=record['sha256']):raise ValueError('Temperature sidecar changed')
            return pd.read_parquet(path),path
        config=json.loads((directory/'config.json').read_text())
        run=config.get('parent_run')
        if run is None:
            parent=Path(config['baseline'])
            if parent.parent.as_posix()!='results/runs':raise ValueError('Invalid baseline path')
            run=parent.name


def read_sst_track(id, *, run=DEFAULT_RUN, allow_test=False):
    """Return all canonical fields plus the explicitly versioned temperature view."""
    from data3001.dataset import read_track
    original=read_track(id,allow_test=allow_test)
    extra,path=temperature_sidecar(id,run=run)
    out=original.merge(extra,on=['id','source_obs'],how='left',validate='one_to_one',indicator=True)
    if len(out)!=len(original) or not out['_merge'].eq('both').all():raise ValueError('Incomplete temperature keys')
    out=out.drop(columns='_merge');out.attrs.update(original.attrs)
    out.attrs['temperature_run']=run;out.attrs['temperature_sidecar']=str(path)
    return out
