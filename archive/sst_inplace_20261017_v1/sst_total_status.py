"""Total-SST missingness semantics, separate from observed grounding time."""
import numpy as np


def post_last_good_grounding_mask(frame):
    time=frame.time.to_numpy(dtype=float)
    end=frame.end_date.to_numpy(dtype=float)
    return (frame.typedeath.eq(1).to_numpy() & np.isfinite(time) &
            np.isfinite(end) & (end>0) & (time>end))


def annotate_total_sst_missingness(frame):
    out=frame.copy()
    selected=post_last_good_grounding_mask(out)&out.sst_use_K.isna().to_numpy()
    out.loc[selected,'sst_reason']='unavailable_after_last_good_on_grounding_ID'
    out.attrs.update(frame.attrs)
    out.attrs['total_SST_missing_policy']='numeric NA plus existing sst_reason; no inferred grounding hour'
    return out
