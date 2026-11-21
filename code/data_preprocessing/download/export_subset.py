"""Create a complete local ragged Zarr subset, preserving every source value.

Per-variable hashes compare source-selected values with re-read exported values.
The full compressed source-object receipts remain the independent provenance.
"""
from data3001.paths import legacy_path, asset_path, project_paths, ensure_output_path, frozen_action
import hashlib
import json
import math
import resource
import sys
import time
import numpy as np
import pandas as pd
import zarr
from numcodecs import Blosc
from data3001.acquisition.acquire_hourly import ROOT, Snapshot, metadata, json_save, sha, utcnow
from data3001.acquisition.rules import copy_spans


@frozen_action
def main():
    started=time.monotonic()
    snap=Snapshot();meta,offsets,frame=metadata(snap)
    selected=pd.read_csv(legacy_path('manifests/acquired_ids.csv'),dtype={'id':str}).sort_values('source_traj_index')
    counts=selected.source_rowsize.to_numpy(dtype=np.int64)
    output_offsets=np.concatenate([[0],np.cumsum(counts)])
    n=int(output_offsets[-1]);indices=selected.source_traj_index.to_numpy(dtype=np.int64)
    ranges=[(int(a),int(b),int(d)) for a,b,d in zip(selected.source_obs_start,selected.source_obs_end_exclusive,output_offsets[:-1])]
    out=legacy_path('raw/hourly_subset_v2.01.1.zarr')
    complete=legacy_path('manifests/subset_export.json')
    if complete.exists():
        raise RuntimeError('Subset already exported; use the verification script instead of overwriting')
    # An incomplete prior attempt can resume deterministically with identical selectors.
    group=zarr.open_group(out,mode='a')
    group.attrs.update(snap.meta['.zattrs'])
    group.attrs.update({'subset_status':'Full available source trajectories for acquired_ids.csv; no scientific cleaning applied',
        'subset_source_asset':'https://noaa-oar-hourly-gdp-pds.s3.amazonaws.com/latest/gdp-v2.01.1.zarr/',
        'subset_id_manifest_sha256':sha(legacy_path('manifests/acquired_ids.csv')),
        'subset_source_metadata_sha256':sha(legacy_path('raw/source_objects/.zmetadata')),
        'subset_release_R_sha256':sha(legacy_path('geometry/release_R.geojson')),
        'subset_global_ID_split_sha256':sha(legacy_path('manifests/global_id_split.csv')),
        'subset_final_D_frozen':False,'subset_created_utc':utcnow()})
    copied=[]
    fields=sorted(k[:-8] for k in snap.meta if k.endswith('/.zattrs'))
    for number,var in enumerate(fields,1):
        spec=snap.spec(var);attrs=snap.meta[var+'/.zattrs'];dims=attrs['_ARRAY_DIMENSIONS']
        if dims not in [['obs'],['traj']]:
            raise RuntimeError('Unsupported source dimensions: '+str((var,dims)))
        is_obs=dims==['obs'];length=n if is_obs else len(selected)
        fill=spec['fill_value']
        if fill=='NaN':fill=float('nan')
        array=group.create_dataset(var,shape=(length,),dtype=np.dtype(spec['dtype']),
            chunks=(min(250000,length),),compressor=Blosc(cname='lz4',clevel=5,shuffle=1),
            fill_value=fill,overwrite=True)
        array.attrs.update(attrs)
        expected=hashlib.sha256();written=0
        if not is_obs:
            values=meta[var][indices]
            array[:]=values;expected.update(values.tobytes());written=len(values)
        else:
            chunk=spec['chunks'][0]
            numbers=set()
            for a,b,_ in ranges:
                numbers.update(range(a//chunk,(b-1)//chunk+1))
            for k in sorted(numbers):
                values=snap.chunk(var,k)
                for a,b,d,e in copy_spans(ranges,k*chunk,len(values)):
                    part=values[a:b]
                    array[d:e]=part
                    expected.update(part.tobytes());written+=len(part)
        if written!=length:
            raise RuntimeError(f'Incomplete exported field {var}: {written} != {length}')
        actual=hashlib.sha256()
        for a in range(0,length,250000):
            actual.update(array[a:min(length,a+250000)].tobytes())
        if actual.hexdigest()!=expected.hexdigest():
            raise RuntimeError('Source/export value-byte mismatch: '+var)
        copied.append({'variable':var,'dimensions':dims,'values':length,'dtype':spec['dtype'],
            'source_selected_value_sha256':expected.hexdigest(),'exported_value_sha256':actual.hexdigest()})
        json_save(legacy_path('audit/subset_export_progress.json'),{'completed_fields':copied,'total_fields':len(fields),'elapsed_seconds':round(time.monotonic()-started,2)})
        print(f'Export verified {number}/{len(fields)}: {var}, {length} values',flush=True)
    for name,values in [('source_traj_index',indices),('source_obs_start_global',selected.source_obs_start.to_numpy(dtype=np.int64))]:
        array=group.create_dataset(name,data=values,chunks=(len(selected),),overwrite=True)
        array.attrs.update({'_ARRAY_DIMENSIONS':['traj'],'long_name':'Derived source provenance index; not a forecast feature'})
    zarr.consolidate_metadata(out)
    json_save(complete, {'status':'PASS','created_utc':utcnow(),'subset_path':'raw/hourly_subset_v2.01.1.zarr',
        'IDs':len(selected),'observations':n,'source_fields':len(fields),'all_source_fields_retained':True,
        'source_observation_values_transformed':False,'time_or_spatial_truncation':False,
        'selected_ids_sha256':sha(legacy_path('manifests/acquired_ids.csv')),'source_metadata_sha256':sha(legacy_path('raw/source_objects/.zmetadata')),
        'source_selected_and_exported_fields':copied,'elapsed_seconds':round(time.monotonic()-started,2),
        'peak_RSS_bytes':int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024)})
    print(f'Complete export: {len(selected)} IDs / {n} observations',flush=True)


if __name__=='__main__':
    main()
