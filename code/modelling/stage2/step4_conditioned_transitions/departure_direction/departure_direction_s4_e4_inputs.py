"""Build a source-keyed historical heading from only the preceding retained position."""
import json
import numpy as np
import pandas as pd
from data3001.feature_pruning import qualification_arrays
from data3001.paths import file_sha256
from data3001.preprocessing.prep_core import GEOD

ORIGIN = ['id','origin_source_obs']
TRACK_COLUMNS = ['id','source_obs','time','cell_1','lon_normalized','lat',
                 'interval_net_ve','interval_net_vn','elapsed_seconds_from_previous']
FLAGS = ['analytical_row','position_ok','mapping_ok']


def extract_track(track, keys):
    track = track.sort_values('time',kind='stable').reset_index(drop=True)
    assert track.id.nunique()==1 and not track.source_obs.duplicated().any()
    times = track.time.to_numpy()
    assert np.isfinite(times).all() and np.all(np.diff(times)>0)
    idx = pd.Index(track.source_obs).get_indexer(keys.origin_source_obs)
    assert (idx>=0).all() and np.array_equal(track.id.to_numpy()[idx],keys.id)
    epoch=(keys.origin_time_UTC-pd.Timestamp('1970-01-01',tz='UTC')).dt.total_seconds().to_numpy()
    assert np.array_equal(times[idx],epoch) and np.array_equal(track.cell_1.to_numpy()[idx],keys.origin_cell_1)
    prev=np.maximum(idx-1,0)
    dt=np.where(idx>0,times[idx]-times[prev],np.nan)
    assert np.array_equal(dt,track.elapsed_seconds_from_previous.to_numpy()[idx],equal_nan=True)
    lon=track.lon_normalized.to_numpy();lat=track.lat.to_numpy()
    good=track[FLAGS].to_numpy(bool).all(axis=1)&np.isfinite(lon)&np.isfinite(lat)&(abs(lon)<=180)&(abs(lat)<=90)
    reasons=np.select([idx==0,dt!=3600,~(good[idx]&good[prev])],['first_row','time_gap','position_quality'],default='valid')
    valid=reasons=='valid'
    east=np.full(len(keys),np.nan);north=east.copy()
    if valid.any():
        a,b=prev[valid],idx[valid]
        az,_,distance=GEOD.inv(lon[a],lat[a],lon[b],lat[b])
        # Identical coordinate pairs have zero geometric separation, even if
        # the inverse solver returns a sub-picometre numerical residual.
        distance=np.where((lon[a]==lon[b]) & (lat[a]==lat[b]),0.,distance)
        east[valid]=distance/3600*np.sin(np.radians(az))
        north[valid]=distance/3600*np.cos(np.radians(az))
        for value,column in [(east,'interval_net_ve'),(north,'interval_net_vn')]:
            assert np.allclose(value[valid],track[column].to_numpy()[b],atol=1e-9,rtol=1e-10)
    result=keys.copy()
    result['predecessor_obs']=np.where(idx>0,track.source_obs.to_numpy()[prev],-1)
    result['predecessor_epoch']=np.where(idx>0,times[prev],np.nan)
    result['elapsed_seconds']=dt
    result['east']=east;result['north']=north
    result['speed']=np.hypot(east,north)
    result['interval_reason']=reasons
    return result


def load_features(paths,guard,keys):
    manifest_path=paths.asset('current_dataset_manifest',verify=True)
    side_path=paths.asset('current_qualification_manifest',verify=True)
    manifest=json.loads(manifest_path.read_text())
    qual=json.loads(side_path.read_text())
    inventory={p.relative_to(paths.root).as_posix():file_sha256(p) for p in [manifest_path,side_path]}
    features=[]
    for ident,group in keys.groupby('id',sort=True):
        sid=str(int(ident));record=manifest['records'][sid];side=qual['records'][sid]
        assert record['pool']==side['pool']=='train'
        assert record['path']==f'data/train/{sid}.parquet' and side['path']==f'provenance/qualification/v7/development/{sid}.parquet'
        canonical=paths._resolve(record['path']);quality=paths._resolve(side['path'])
        guard.input_files.update([canonical,quality])
        assert file_sha256(canonical)==record['sha256']
        with canonical.open('rb') as stream:
            frame=pd.read_parquet(stream,columns=TRACK_COLUMNS)
        assert len(frame)==record['rows'] and frame.id.eq(ident).all()
        frame.attrs['data3001']={'pool':'train'}
        flags=qualification_arrays(ident,frame,FLAGS,allow_test=False)
        features.append(extract_track(frame.assign(**flags),group))
        inventory[record['path']]=record['sha256'];inventory[side['path']]=side['sha256']
    result=pd.concat(features,ignore_index=True)
    assert not result.duplicated(ORIGIN).any() and len(result)==len(keys)
    assert set(keys.id)==guard.read_ids
    return result,inventory
