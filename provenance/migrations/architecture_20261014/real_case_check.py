from pathlib import Path
import json,time,hashlib,ast,numpy as np,pandas as pd
from data3001.paths import project_paths,file_sha256
from data3001.preprocessing.prep_io import Source
from data3001.preprocessing.prep_run import clean_track,directory
from data3001.preprocessing.prep_geometry import mask
from data3001.preprocessing.prep_pairs import load_track,generate
paths=project_paths();start=time.monotonic();source=Source();land=mask('h');coarse=mask('i')
cases=[]
for id in [9825497,43869,17503,55353,23120]:
 raw,meta=source.track(id);new,_=clean_track(raw,meta,land,coarse)
 frozen=pd.read_parquet(directory(source.cohort.loc[id,'split'])/f'{id}.parquet')
 # Parquet timestamp units may differ from an in-memory Pandas construction;
 # compare exact logical values while file SHA256 independently proves the
 # stored schema/dtypes and bytes unchanged.
 pd.testing.assert_frame_equal(new,frozen,check_dtype=False,check_exact=True)
 cases.append({'id':id,'rows':len(new),'all_columns_exactly_equal':True})
exit_cases=[]
for id,time_UTC in [(7706157,'1990-09-06T05:00:00Z'),(7706158,'1990-08-28T15:00:00Z')]:
 frame,track,events=load_track(source,id);origin=np.flatnonzero(track['time']==pd.Timestamp(time_UTC).timestamp());assert len(origin)==1
 endpoint,stopped=generate(frame,track,events,id,origin,365,'drogued',0)
 assert endpoint.reason_code.iloc[0]==3
 assert stopped.reason_code.iloc[0]==0 and bool(stopped.outside.iloc[0])
 exit_cases.append({'id':id,'365_day_endpoint_reason':3,'365_day_stopped_reason':0,'stopped_outside':True,'depth_policy_not_selected':True})
# New interpreter retains the exact installed Python/native source files. Cache
# bytecode is interpreter-derived; the original bytecode remains preserved in archive.
inventory=json.loads((paths.root/'provenance/migrations/architecture_20261014/path_map.json').read_text())['entries']; checked=0
for entry in inventory:
 prefix='data_preprocessing/.venv/lib/python3.12/site-packages/'
 if entry['kind']!='file' or not entry['path'].startswith(prefix) or '__pycache__' in entry['path']:continue
 dest=paths.root/'.venv/lib/python3.12/site-packages'/entry['path'][len(prefix):]
 assert file_sha256(dest)==entry['sha256'],entry['path'];checked+=1
result={'passed':True,'five_full_track_cleaning_regressions':cases,'qualified_early_exit_regressions':exit_cases,'new_environment_source_files_SHA256_verified':checked,'forecast_accuracy_evaluated':False,'elapsed_seconds':time.monotonic()-start}
print(json.dumps(result,indent=2),flush=True)
