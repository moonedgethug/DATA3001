"""Scoped official metadata refinements; never a learned drogue imputer.

The native product and its flags remain unchanged. Sparse regime overlays are
retrospective annotations. The official recorded minute is a nominal metadata
time, not a claim of minute-accurate physical sensor detection.
"""
from functools import lru_cache
import json
import numpy as np
import pandas as pd
from data3001.paths import asset_path, project_paths, file_sha256

VERSION='official-drogue-boundary-v1'


def official_regimes(time, record):
    t=np.asarray(time,dtype=float)
    if record['decision']=='nominal_loss':
        loss=float(record['official_loss_epoch'])
        if not np.isfinite(loss) or loss<=0:raise ValueError('Invalid official loss time')
        return np.where(np.isfinite(t),np.where(t<loss,1,0),-1).astype(np.int8)
    if record['decision']=='attached_at_end':
        through=float(record['attached_through_epoch'])
        if not np.isfinite(through):raise ValueError('Unbounded attachment proof')
        return np.where(np.isfinite(t)&(t<=through),1,-1).astype(np.int8)
    raise ValueError('Unresolved evidence cannot supply confirmed regime labels')


@lru_cache(maxsize=2)
def _manifest(path, checksum):
    if file_sha256(path)!=checksum:raise ValueError('Boundary manifest checksum mismatch')
    data=json.loads(path.read_text())
    if data['version']!=VERSION or len(data['records'])!=3137:
        raise ValueError('Unexpected boundary correction scope')
    return data


def boundary_evidence(id, split, *, allow_test=False):
    if split=='test' and not allow_test:
        raise PermissionError('Final-test boundary access requires explicit permission')
    spec=project_paths().catalog['assets'].get('official_drogue_boundary')
    if spec is None:return None
    data=_manifest(asset_path('official_drogue_boundary'),spec['sha256'])
    record=data['records'].get(str(int(id)))
    if record is not None and record['split']!=split:
        raise ValueError('Boundary correction split mismatch')
    return record if record and record['decision']!='hold_unknown' else None


@lru_cache(maxsize=2)
def _overlays(path, checksum):
    if file_sha256(path)!=checksum:raise ValueError('Boundary overlay checksum mismatch')
    frame=pd.read_parquet(path)
    if frame.duplicated(['id','source_obs']).any():raise ValueError('Duplicate overlay keys')
    return {int(id):g.drop(columns='id').reset_index(drop=True) for id,g in frame.groupby('id')}


def apply_overlay(frame, overlay):
    if frame.source_obs.duplicated().any() or overlay.source_obs.duplicated().any():
        raise ValueError('Ambiguous source observation key')
    index=pd.Index(frame.source_obs).get_indexer(overlay.source_obs)
    if (index<0).any():raise ValueError('Overlay source observation missing')
    old=frame.regime.to_numpy()[index]
    if not np.array_equal(old,overlay.old_regime.to_numpy()):
        raise ValueError('Overlay baseline labels changed')
    if not np.isin(overlay.regime,[-1,0,1]).all():raise ValueError('Invalid regime')
    result=frame.copy()
    values=result.regime.to_numpy(copy=True)
    values[index]=overlay.regime.to_numpy()
    result['regime']=values
    return result


def read_prepared_track(id, split, *, allow_test=False):
    """Return the active frame, composing the 44-ID and boundary corrections."""
    if 'current_dataset_manifest' in project_paths().catalog['assets']:
        from data3001.dataset import read_track,manifest
        record=manifest()['records'][str(int(id))]
        if record['historical_split']!=split:raise ValueError('Historical split mismatch')
        frame=read_track(id,allow_test=allow_test)
        return frame,frame.attrs['data3001'].get('boundary_record')
    from data3001.preprocessing.drogue_correction import prepared_track_path
    path=prepared_track_path(id,split,allow_test=allow_test)
    record=boundary_evidence(id,split,allow_test=allow_test)
    if record and file_sha256(path)!=record['baseline_track_sha256']:
        raise ValueError('Frozen boundary input changed')
    frame=pd.read_parquet(path)
    if record is None:return frame,None
    key='drogue_boundary_test' if split=='test' else 'drogue_boundary_development'
    spec=project_paths().catalog['assets'][key]
    overlays=_overlays(asset_path(key,allow_test=allow_test),spec['sha256'])
    overlay=overlays.get(int(id))
    if overlay is None or len(overlay)!=record['changed_rows']:
        raise ValueError('Missing or incomplete boundary overlay')
    result=apply_overlay(frame,overlay)
    expected=official_regimes(result.time.to_numpy(),record)
    if not np.array_equal(result.regime.to_numpy(),expected):
        raise ValueError('Materialized labels disagree with official evidence')
    return result,record
