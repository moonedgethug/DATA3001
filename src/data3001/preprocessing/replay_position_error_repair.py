"""Check cache-only single-process versus two-process overlay reproducibility."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
from pathlib import Path
import resource
import time

import pandas as pd

from data3001.preprocessing import position_error_repair as repair
from data3001.preprocessing.run_position_error_repair import frame_hash


def rebuild(job):
    run,ident,group,entries=job
    references=[]
    for item in entries:
        if item['status']!='available':continue
        assert repair.sha256(run/item['path'])==item['sha256']
        try:frame,meta=repair.read_reference(run/item['path'],ident,group)
        except (ValueError,KeyError,IndexError) as exc:
            frame=group[['source_obs']].copy();frame['match_status']='source_metadata_unresolved'
            meta={'id':ident,'sha256':item['sha256'],'eligible':False,'reason':str(exc)}
        references.append((frame,meta))
    output=repair.build_overlay(group,references,run.name)
    if not references:
        state='not_fetched_budget' if any(x['status']=='not_fetched_budget' for x in entries) else 'source_missing'
        for k in ['status_lon','status_lat','match_status']:output[k]=state
    return ident,frame_hash(output)


def replay(run,phase):
    start=time.monotonic();folder=run/phase
    output=pd.read_parquet(folder/'error_overlay.parquet')
    target=pd.read_parquet(run/'target_keys.parquet')
    registry=json.loads((folder/'source_registry.json').read_text())
    ids=set(output.id)
    jobs=[(run,int(i),g.reset_index(drop=True),[x for x in registry if x['id']==i])
          for i,g in target[target.id.isin(ids)].groupby('id',sort=True)]
    baseline={int(i):frame_hash(g) for i,g in output.groupby('id',sort=True)}
    # Production phase was sequential. Replay in separate spawned processes:
    # HDF5/NetCDF handles are never shared between threads or inherited by fork.
    with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as pool:
        reproduced=dict(pool.map(rebuild,jobs,chunksize=1))
    assert reproduced==baseline
    parent_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    child_rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    # On this macOS execution host ru_maxrss is bytes. This deliberately loose
    # bound includes the parent plus two simultaneous copies of the largest child.
    rss_bound=parent_rss+2*child_rss
    assert rss_bound<=4*2**30,'Replay exceeds the approved memory bound'
    record={'passed':True,'phase':phase,'IDs':len(jobs),'rows':len(output),
            'production_workers':1,'replay_workers':2,'network_access':False,
            'parent_peak_rss_bytes':parent_rss,'largest_child_peak_rss_bytes':child_rss,
            'conservative_combined_rss_bound_bytes':rss_bound,
            'per_id_logical_hashes':baseline,'elapsed_seconds':time.monotonic()-start}
    with (folder/'reproducibility.json').open('x') as f:json.dump(record,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in record.items() if k!='per_id_logical_hashes'},indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--phase',choices=['pilot','full'],required=True)
    a=p.parse_args();replay(a.run.resolve(),a.phase)
