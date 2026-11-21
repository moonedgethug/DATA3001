"""Independent read-only post-modelling diagnosis. No model imports."""
import os
from pathlib import Path
import numpy as np
import pandas as pd

KEY=['id','origin_source_obs','horizon_days']

def availability_flags(frame):
    f=frame.copy()
    sec=f.secondary_predicates.to_numpy(dtype=np.int64)
    f['administrative_excluded']=((sec & 2)!=0)|f.role_excluded.to_numpy(bool)
    f['origin_invalid']=((sec & 1)!=0)|f.reason_code.eq(1)
    f['known_exit']=f.outside.to_numpy(bool)&f.reason_code.eq(0)
    f['risk_set']=~(f.administrative_excluded|f.origin_invalid|f.known_exit)
    f['missing_endpoint']=f.risk_set&~f.endpoint_available.to_numpy(bool)
    return f

def id_equal_mean(frame,metric):
    return float(frame.groupby('id')[metric].mean().mean())

def availability_by_id(frame):
    z=frame.groupby('id').agg(candidates=('id','size'),risk_count=('risk_set','sum'),missing_count=('missing_endpoint','sum')).reset_index()
    z['missing_rate']=z.missing_count/z.risk_count.replace(0,np.nan)
    return z

def official_status(code):
    if code is None or pd.isna(code):return 'unresolved'
    return {0:'alive_at_source_snapshot',1:'official_grounding',2:'vessel_recovery',
        3:'transmission_stopped_unknown_cause',4:'sporadic_transmission_unknown_cause',
        5:'battery_problem',6:'inactive'}.get(int(code),'unresolved')

def window_relation(start,end,lower,upper):
    if lower is None or upper is None or not np.isfinite([lower,upper]).all():return 'event_time_unknown'
    if not lower<upper:raise ValueError('Invalid event interval')
    if upper<=start or lower>=end:return 'no_overlap'
    if lower>=start and upper<=end:return 'within_window'
    return 'possible_overlap'

def exact_join(left,right,keys):
    if left.duplicated(keys).any() or right.duplicated(keys).any():raise ValueError('Duplicate source keys')
    out=left.merge(right,on=keys,how='left',validate='one_to_one',indicator=True)
    if not out._merge.eq('both').all():raise ValueError('Missing source keys')
    return out.drop(columns='_merge')

def check_write_path(path,output):
    if not Path(path).resolve().is_relative_to(Path(output).resolve()):raise PermissionError('Original inputs are read-only')
    return True

def check_read_path(path,ids):
    p=Path(path).resolve()
    if 'restricted_test' in p.parts or ('data' in p.parts and 'test' in p.parts):raise PermissionError('Locked final test')
    if p.suffix=='.parquet' and p.parent.name in ['train','development'] and p.stem.isdigit():
        if int(p.stem) not in ids:raise PermissionError('ID outside approved 383')
    return True

def clipped_real_boundary(land,clip):return land.boundary.intersection(clip)
def bootstrap_draws(n,count,seed):return np.random.default_rng(seed).integers(0,n,size=(count,n))
def supports_interval(n):return bool(n>=10)

def metadata_conflict(native,official,assessment):
    return bool(assessment=='cross_source_conflict' or
        (pd.notna(native) and pd.notna(official) and int(native)!=0 and int(native)!=int(official)))

def distance_class(lower_m,upper_m):
    if not np.isfinite([lower_m,upper_m]).all():return 'uncertain'
    if upper_m<=10000:return '<=10km'
    if lower_m>10000 and upper_m<=50000:return '10_50km'
    if lower_m>50000:return '>50km'
    return 'uncertain'
