"""Compatibility reader for the stored cleaned SST; never adds feature columns."""
import numpy as np
import pandas as pd


def official_end_seconds(values):
    stamps=pd.to_datetime(values,utc=True)
    # Timestamp.timestamp() is in seconds regardless of pandas' backing storage
    # resolution (seconds, milliseconds, microseconds or nanoseconds).
    # Still-active instruments normally have no terminal date; retain NaN.
    return np.array([np.nan if pd.isna(stamp) else pd.Timestamp(stamp).timestamp() for stamp in stamps],float)


def read_sst_track(id, *, run=None, allow_test=False):
    from data3001.dataset import read_track
    if run is not None:
        raise ValueError('Current SST is stored in sst. Historical reconstruction runs are audit evidence only.')
    return read_track(id,allow_test=allow_test)
