"""Optional exact-formula EM arithmetic kernel, compiled and pinned per run."""
import ctypes
from functools import lru_cache
from pathlib import Path
import subprocess
import numpy as np


def compile_kernel(destination):
    source=Path(__file__).with_name('local_gmm_s5_e2_kernel.cpp')
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['clang++','-O3','-std=c++17','-ffp-contract=off','-dynamiclib',str(source),'-framework','Accelerate','-o',str(destination)],check=True,capture_output=True)
    return destination


@lru_cache(maxsize=1)
def library(path):
    lib=ctypes.CDLL(str(path));ptr=ctypes.POINTER(ctypes.c_double)
    lib.e2_em.argtypes=[ptr,ctypes.c_int,ctypes.c_int,ctypes.c_int,ptr,ptr,ptr,ptr,ctypes.POINTER(ctypes.c_int),ptr]
    lib.e2_em.restype=ctypes.c_int
    return lib


def run(z,parameters,path):
    z=np.ascontiguousarray(z,dtype=np.float64);w,a,b=[np.array(x,dtype=np.float64,order='C',copy=True) for x in parameters]
    trace=np.zeros(201);iterations=ctypes.c_int(0);fixed=ctypes.c_double(float('inf'));ptr=ctypes.POINTER(ctypes.c_double)
    arr=lambda x:x.ctypes.data_as(ptr)
    code=library(str(path)).e2_em(arr(z),len(z),len(w),200,arr(w),arr(a),arr(b),arr(trace),ctypes.byref(iterations),ctypes.byref(fixed))
    return dict(code=code,parameters=(w,a,b),trace=trace[:iterations.value+1].tolist(),iterations=iterations.value,fixed=fixed.value)
