"""Phase gates for the approved MDN experiment. Pilot is not model selection."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
import torch

from . import conditional_mdn_s5_e3_inputs as inp
from . import conditional_mdn_s5_e3_numerics as num
from .conditional_mdn_s5_e3_runtime import atomic_json


def pilot_indices(count):
    if count<64:raise ValueError('Pilot role must have at least64 queries')
    return np.floor(np.arange(64)*(count-1)/63).astype(int)


def id_weights(ids):
    _,inverse,counts=np.unique(ids,return_inverse=True,return_counts=True)
    return 1/(len(counts)*counts[inverse])


def packet_at(params,index,origin,target_scale):
    w,m,c=[np.asarray(params[k][index],float) for k in ('pi','mu','cov')]
    scale=np.asarray(target_scale,float)
    zcov=c/scale[None,:,None]/scale[None,None,:]
    if not np.isfinite(zcov).all() or np.linalg.eigvalsh(zcov).min()<.001-1e-10:
        raise ValueError('MDN standardized covariance floor failed')
    packet=dict(origin=np.asarray(origin,float).tolist(),weights=w.tolist(),means=m.tolist(),cholesky=np.linalg.cholesky(c).tolist())
    num.arrays(packet)
    return packet


def aggregate_difference(candidate,baseline,weights):
    delta=np.asarray(candidate)-np.asarray(baseline)
    variance=delta.var(axis=1,ddof=1)/8
    return dict(delta_km=float(weights@delta.mean(axis=1)),three_se_km=float(3*np.sqrt(weights**2@variance)))


def preflight_pass(receipt):
    return bool(receipt.get('basic_numerical_pass') and receipt.get('resource_pass'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('run');parser.add_argument('stage',choices=['pilot_train','pilot_numeric'])
    args=parser.parse_args()
    from .conditional_mdn_s5_e3_pilot import run_pilot
    run_pilot(args.run,args.stage)


if __name__=='__main__':main()
