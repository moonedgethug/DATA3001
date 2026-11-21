import numpy as np
def clipped_real_boundary(land,clip): return land.boundary.intersection(clip)
def distance_class(lower_m,upper_m):
    if not np.isfinite([lower_m,upper_m]).all(): return 'uncertain'
    if upper_m<=10000:return '<=10km'
    if lower_m>10000 and upper_m<=50000:return '10_50km'
    if lower_m>50000:return '>50km'
    return 'uncertain'
