"""Opt-in, same-node ES optimization. No fitting, data I/O or selection."""
import ctypes
from functools import lru_cache
from pathlib import Path
import subprocess
import time
import numpy as np
from . import local_gmm_s5_e2 as gmm
from . import conditional_gaussian_s5_e1 as single
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as geometry


def compile_kernel(destination):
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    source=Path(__file__).with_name('local_gmm_s5_e2_score_kernel.cpp')
    subprocess.run(['clang++','-O3','-std=c++17','-ffp-contract=off','-dynamiclib',str(source),
        '-o',str(destination)],check=True,capture_output=True)
    return destination


@lru_cache(maxsize=2)
def library(path):
    lib=ctypes.CDLL(str(path));ptr=ctypes.POINTER(ctypes.c_double)
    lib.e2_score.argtypes=[ptr,ptr,ptr,ptr,ctypes.c_int,ctypes.c_int,ptr]
    lib.e2_score.restype=ctypes.c_int
    return lib


def integrands(first,second,truth,weights,native_path):
    a,b,t,w=[np.ascontiguousarray(x,dtype=np.float64) for x in [first,second,truth,weights]]
    if a.ndim!=3 or a.shape!=b.shape or a.shape[2]!=3 or t.shape!=(3,) or w.shape!=(len(a),):
        raise ValueError('Invalid mixture distance arrays')
    if not 1<=len(w)<=3 or not np.isfinite(t).all() or not np.isfinite(w).all():
        raise ValueError('Invalid mixture weights or target')
    out=np.empty(a.shape[1],np.float64);ptr=ctypes.POINTER(ctypes.c_double)
    arr=lambda x:x.ctypes.data_as(ptr)
    code=library(str(native_path)).e2_score(arr(a),arr(b),arr(t),arr(w),len(w),len(out),arr(out))
    if code:raise ArithmeticError('Nonfinite or invalid ES arithmetic')
    return out


def geographic_xyz(origin,vectors):
    v=np.asarray(vectors,dtype=np.float64)
    if v.ndim!=2 or v.shape[1]!=2 or not np.isfinite(v).all():raise ValueError('Invalid vectors')
    radius=np.linalg.norm(v,axis=1)
    azimuth=np.rad2deg(np.arctan2(v[:,0],v[:,1]))
    # Only private buffers are passed to the in-place geographic operation.
    lon,lat,_=single.GEOD.fwd(np.full(len(v),float(origin[0])),np.full(len(v),float(origin[1])),
        azimuth,radius*1000,inplace=True)
    points=np.column_stack([lon,lat]);points[radius==0]=origin
    if not np.isfinite(points).all():raise ArithmeticError('Nonfinite direct geodesic')
    return geometry.xyz(points)


def score_models(packets,target,count,key,native_path,profile=None):
    if count not in (8192,16384,32768,65536):raise ValueError('Unregistered ES integration level')
    if 1 not in packets:raise ValueError('G1 required for exact fallback reuse')
    profile={} if profile is None else profile
    def elapsed(name,start):profile[name]=profile.get(name,0.)+time.monotonic()-start
    start=time.monotonic();truth=geometry.xyz(np.asarray(target)[None])[0]
    prepared={};origin=packets[1]['origin']
    for k,p in sorted(packets.items()):
        if k not in (1,2,3) or p['origin']!=origin:raise ValueError('Mixed query or unregistered K')
        if k>1 and p['fallback']:
            for field in ['weights','means','cholesky']:
                if not np.array_equal(p[field],packets[1][field]):raise ValueError('Fallback is not G1')
            continue
        w,m,l=[np.asarray(p[f],dtype=np.float64) for f in ['weights','means','cholesky']]
        if len(w)!=k or m.shape!=(k,2) or l.shape!=(k,2,2):raise ValueError('Invalid frozen packet')
        prepared[k]=(w,m,l)
    elapsed('prepare',start);means={k:[] for k in prepared};n=count//8
    for rep in range(8):
        start=time.monotonic();z=gmm.normals(n,4,(*key,'energy',rep));elapsed('normal_nodes',start)
        start=time.monotonic();vectors=[];slices={};offset=0
        for k,(_,m,l) in prepared.items():
            for half in (0,1):
                slices[k,half]=(offset,offset+k*n)
                for centre,root in zip(m,l):vectors.append(centre+z[:,half*2:half*2+2]@root.T)
                offset+=k*n
        vectors=np.concatenate(vectors);elapsed('affine_and_buffers',start)
        start=time.monotonic();cloud=geographic_xyz(origin,vectors);elapsed('geography_ecef',start)
        start=time.monotonic()
        for k,(w,_,_) in prepared.items():
            a,b=[cloud[slice(*slices[k,h])].reshape(k,n,3) for h in (0,1)]
            means[k].append(float(integrands(a,b,truth,w,native_path).mean()))
        elapsed('distance_and_reduce',start)
    values={k:dict(single.replicate_summary(v),sample_count=count) for k,v in means.items()}
    return {k:values[1] if k>1 and p['fallback'] else values[k] for k,p in sorted(packets.items())}
