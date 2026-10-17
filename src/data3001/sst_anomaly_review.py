"""Explicit project review rules; daily background is not hourly sensor truth."""
import numpy as np
import pandas as pd
from data3001.model_input_cleaning import confirmed_high_replacement


def review_reasons(frame):
    native=frame.native_C.to_numpy(dtype=float)
    background=frame.background_C.to_numpy(dtype=float)
    difference=native-background
    available=np.isfinite(background)&(background>=-3)&(background<=40)
    reason=np.full(len(frame),'retain_for_review',object)
    suspect_fit=(frame.flg_sst1.isin([2,3]).to_numpy() |
                 (frame.flg_sst2.isin([2,3]).to_numpy() &
                  (frame.sst2.abs().to_numpy()>=10)))
    reason[available&(abs(difference)>=10)&suspect_fit]='corroborated_fit_inconsistency'
    reason[available&(native>40)&(difference>=8)]='corroborated_extreme_heat'
    reason[confirmed_high_replacement(native,background)]='corroborated_native_above_45C'
    post_ground=(frame.typedeath.eq(1).to_numpy()&
                 (frame.time.to_numpy()>frame.end_date.to_numpy(dtype=float)))
    reason[post_ground]='post_last_good_grounding_hold'
    reason[frame.recovery_tail.to_numpy(dtype=bool)]='excluded_recovery_tail'
    return pd.Series(reason,index=frame.index)


def apply_reviewed_temperature_patch(base,patch,approved_keys):
    keys=['id','source_obs']
    allowed={'sst_use_K','sst_method','sst_reason','availability_scope',
             'sst_source_sd_bound_K','sst_total_se_K','sst_error_kind',
             'linear_anchor_left_source_obs','linear_anchor_right_source_obs'}
    if (not set(keys).issubset(patch) or not set(patch).issubset(base)
            or not set(patch).difference(keys).issubset(allowed)):
        raise ValueError('Only existing temperature fields may change')
    if base.duplicated(keys).any() or patch.duplicated(keys).any():
        raise ValueError('Duplicate temperature key')
    targets=set(patch[keys].itertuples(index=False,name=None))
    if not targets.issubset(approved_keys):raise ValueError('Unreviewed temperature change')
    loc=pd.MultiIndex.from_frame(base[keys]).get_indexer(pd.MultiIndex.from_frame(patch[keys]))
    if (loc<0).any():raise ValueError('Temperature key absent from parent')
    if (not np.isfinite(patch.sst_use_K).all()
            or not patch.sst_method.isin([11,12,13,14,15,16]).all()):
        raise ValueError('Invalid background replacement')
    out=base.copy(deep=True)
    for name in patch.columns.difference(keys):
        out.iloc[loc,out.columns.get_loc(name)]=patch[name].to_numpy()
    return out
