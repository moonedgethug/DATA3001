"""Source-preserving model-input rules authorized on 2026-10-17.

Each input frame is one complete instrument trajectory. Official last-good
time is an exclusion bound, not a claim to observe the exact recovery event.
"""
import numpy as np


def recovery_tail_mask(frame):
    death = frame['typedeath'].to_numpy()
    if not (death == 2).any():
        return np.zeros(len(frame), dtype=bool)
    end = frame['end_date'].to_numpy(dtype=float)
    time = frame['time'].to_numpy(dtype=float)
    if (not (death == 2).all() or not np.isfinite(end).all()
            or len(np.unique(end)) != 1 or not np.isfinite(time).all()):
        raise ValueError('Missing or contradictory recovery metadata')
    return time > end


def exclude_recovery_tail(frame):
    out = frame.loc[~recovery_tail_mask(frame)].copy()
    out.attrs.update(frame.attrs)
    out.attrs['recovery_policy'] = 'typedeath=2: time <= official numeric end_date'
    return out


def sst_review_mask(frame):
    temperature = frame['sst'].to_numpy(dtype=float) - 273.15
    accepted = frame['flg_sst'].isin([4, 5]).to_numpy() & np.isfinite(temperature)
    time = frame['time'].to_numpy(dtype=float)
    review = accepted & ((temperature > 40.) | (temperature < -2.05))
    if len(frame) > 1:
        delta = np.diff(time)
        jump = (accepted[1:] & accepted[:-1] & (delta > 0) & (delta <= 3600)
                & (np.abs(np.diff(temperature)) > 5.))
        review[1:] |= jump
        review[:-1] |= jump
    return review


def confirmed_high_replacement(native_C, background_C):
    native = np.asarray(native_C, dtype=float)
    background = np.asarray(background_C, dtype=float)
    return (np.isfinite(native) & (native > 45.) & np.isfinite(background)
            & (background >= -3.) & (background <= 40.)
            & (native - background >= 5.))
