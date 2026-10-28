"""Optional local compiled arithmetic; independent NumPy reference remains tested."""
import ctypes
from functools import lru_cache
from pathlib import Path
import numpy as np
from data3001.modelling.markov_neighbour_integration import weight_table

SOURCE=Path(__file__).with_name('_neighbour_scoring.cpp')
LIBRARY=Path(__file__).resolve().parents[3]/'.superpowers/native/neighbour_scoring.dylib'
KEYS=['S_integration','S_uncentred','mass_estimate','true_probability_estimate','U_mass_estimate','E_mass_estimate']


@lru_cache(maxsize=1)
def library():
    lib=ctypes.CDLL(str(LIBRARY));function=lib.neighbour_scores
    ptr=lambda dtype:np.ctypeslib.ndpointer(dtype=dtype,flags='C_CONTIGUOUS')
    function.argtypes=[ctypes.c_int]*5+[ptr(np.int32),ptr(np.int32),ptr(np.uint8),ptr(np.uint8),ptr(np.float64),ptr(np.float64)]
    function.restype=ctypes.c_int;return function


def score_counts(draws,truth,k,l,steps,proposal,r,targets=None):
    d=np.ascontiguousarray(draws,dtype='int32');y=np.ascontiguousarray(truth,dtype='int32')
    k=np.ascontiguousarray(k,dtype='uint8');l=np.ascontiguousarray(l,dtype='uint8')
    if (d.ndim!=2 or y.shape!=(len(d),) or k.shape!=d.shape or l.shape!=d.shape
            or r<2 or d.shape[1]!=len(proposal)*r or (k>steps).any() or (l>steps).any()
            or not (((d>=0)&(d<64800))|(d==-2)|(d==-3)).all()):raise ValueError('Invalid compiled score arrays')
    targets=proposal if targets is None else targets
    table=weight_table(steps,tuple(map(tuple,proposal)),tuple(map(tuple,targets)))
    out=np.empty((len(d),6,len(targets)),dtype='float64')
    if library()(len(d),d.shape[1],len(targets),r,steps+1,d,y,k,l,table,out):raise RuntimeError('Compiled scorer rejected input')
    if not np.isfinite(out).all():raise ValueError('Nonfinite compiled score')
    return {name:out[:,i,:] for i,name in enumerate(KEYS)}
