"""Read the narrowly scoped, source-audited 44-ID drogue correction.

Frozen source values and preparation-1.0 files are never overwritten. This is
official metadata decoding, not a learned imputer or a forecast-time feature.
"""
from functools import lru_cache
import json
import numpy as np
from data3001.paths import asset_path, project_paths, file_sha256


@lru_cache(maxsize=2)
def _manifest(path, expected_sha256):
    if file_sha256(path)!=expected_sha256:
        raise ValueError('Official drogue correction manifest checksum mismatch')
    with path.open() as stream:
        data=json.load(stream)
    if data['version']!='official-drogue-attached-44-v1' or len(data['records'])!=44:
        raise ValueError('Unexpected official drogue correction scope')
    return data


def official_attached_evidence(id, split, *, allow_test=False):
    if split=='test' and not allow_test:
        raise PermissionError('Final-test correction access requires explicit permission')
    catalog=project_paths().catalog['assets']
    if 'official_drogue_correction' not in catalog:
        return None
    spec=catalog['official_drogue_correction']
    data=_manifest(asset_path('official_drogue_correction'),spec['sha256'])
    record=data['records'].get(str(int(id)))
    if record is not None and record['split']!=split:
        raise ValueError('Correction split does not match the frozen assignment')
    return record


def prepared_track_path(id, split, *, allow_test=False):
    if 'current_dataset_manifest' in project_paths().catalog['assets']:
        from data3001.dataset import track_path,manifest
        if manifest()['records'][str(int(id))]['historical_split']!=split:
            raise ValueError('Historical split mismatch')
        return track_path(id,allow_test=allow_test)
    baseline=asset_path('test_cleaned' if split=='test' else 'development_cleaned',
                        allow_test=allow_test)/f'{int(id)}.parquet'
    record=official_attached_evidence(id,split,allow_test=allow_test)
    if record is None:
        return baseline
    key='drogue_correction_test' if split=='test' else 'drogue_correction_development'
    path=asset_path(key,allow_test=allow_test)/'cleaned'/f'{int(id)}.parquet'
    if file_sha256(baseline)!=record['baseline_track_sha256']:
        raise ValueError('Frozen correction input changed')
    if file_sha256(path)!=record['corrected_track_sha256']:
        raise ValueError('Corrected track checksum mismatch')
    return path


def restore_attached(frame, evidence, id):
    """Return a copy changing only regime after checking explicit source proof."""
    attrs=evidence['loss_attrs']
    if (str(evidence['original_id'])!=str(int(id)) or
        evidence['raw_loss_date']!=[-999999.0] or
        float(attrs['_FillValue'])!=-999999.0 or
        'FillValue=drogue still attached' not in attrs['long_name'] or
        int(evidence['original_rows'])!=len(frame)):
        raise ValueError('Official per-ID attached proof does not match this track')
    if not (frame.drogue_status.eq(1).all() and frame.regime.eq(-1).all()):
        raise ValueError('Unexpected source flags or baseline regimes')
    corrected=frame.copy()
    corrected['regime']=np.ones(len(frame),dtype=frame.regime.dtype)
    return corrected
