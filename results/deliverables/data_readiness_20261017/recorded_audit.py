from pathlib import Path
import json
from collections import defaultdict
import numpy as np
import pandas as pd
from data3001.paths import project_paths,file_sha256
from data3001.dataset import manifest
from data3001.preprocessing.prep_io import Source
from data3001.preprocessing.prep_pairs import load_track,origin_indices
from data3001.preprocessing import prep_core as c
from data3001.preprocessing.prep_pairs import CUTOFF
root=project_paths().root
run=root/'provenance/runs/modelling_entry_audit_20261017_v1'
out=root/'results/runs/modelling_entry_audit_20261017_v1'
m=manifest();manifest_hash=file_sha256(root/'configs/dataset_manifest.json')
idx=pd.read_csv(root/'configs/dataset_index.csv')
ids=sorted(idx.loc[(idx.pool=='train') & idx.in_R.astype(bool),'id'].astype(int))
assert len(ids)==396
source=Source();totals=defaultdict(lambda:{'pairs':0,'ids':set()});cells=defaultdict(lambda:{'pairs':0,'ids':set()});origins=0
for n,sid in enumerate(ids,1):
 df,a,events=load_track(source,sid);o=origin_indices(df,a,'R');origins+=len(o)
 cell=df.cell_1.to_numpy()[o];season=df.season.to_numpy()[o]
 for h in [7,30,365]:
  for scenario in ['pooled','drogued','undrogued']:
   e,p=c.labels(a,o,h,0,scenario,events,cutoff=CUTOFF)
   for target,label in [('endpoint',e),('stopped',p)]:
    ok=label['reason']==0;k=(h,scenario,target);totals[k]['pairs']+=int(ok.sum())
    if ok.any():totals[k]['ids'].add(sid)
    for ss in range(4):
     mask=ok & (season==ss);key=(h,scenario,target,ss);totals[key]['pairs']+=int(mask.sum())
     if mask.any():totals[key]['ids'].add(sid)
     if mask.any():
      values,counts=np.unique(cell[mask],return_counts=True)
      for cc,count in zip(values,counts):
       z=cells[(h,scenario,target,ss,int(cc))];z['pairs']+=int(count);z['ids'].add(sid)
 if n%50==0:print(f'Audited {n}/{len(ids)} development R IDs',flush=True)
assert file_sha256(root/'configs/dataset_manifest.json')==manifest_hash
records=[]
for k,v in totals.items():
 row={'horizon_days':k[0],'scenario':k[1],'target':k[2],'season':k[3] if len(k)==4 else 'all','eligible_pairs':v['pairs'],'independent_IDs':len(v['ids'])};records.append(row)
pd.DataFrame(records).to_csv(out/'support_summary.csv',index=False)
pd.DataFrame([{'horizon_days':k[0],'scenario':k[1],'target':k[2],'season':k[3],'cell_1':k[4],'eligible_pairs':v['pairs'],'independent_IDs':len(v['ids'])} for k,v in cells.items()]).to_csv(out/'cell_season_support.csv',index=False)
summary={'passed':True,'dataset_release':m['version'],'dataset_manifest_sha256':manifest_hash,'contract_sha256':m['contract_sha256'],'development_R_IDs':len(ids),'qualified_position_origins':origins,'final_test_accessed':False,'fitted_model':False,'forecast_accuracy_evaluated':False,'overall_support':[r for r in records if r['season']=='all'],'seasonal_support':[r for r in records if r['season']!='all'],'limitations':['Counts establish eligible observations, not forecast accuracy.','Overlapping hourly origins are dependent; independent ID counts are reported.','Depth policy DEPTH-01 and the model-stage validation protocol remain to be settled.']}
(run/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'passed':True,'development_R_IDs':len(ids),'overall_support':summary['overall_support']}),flush=True)
