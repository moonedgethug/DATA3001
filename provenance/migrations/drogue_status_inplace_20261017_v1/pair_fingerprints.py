"""Representative real-label equivalence before/after a field consolidation."""
import hashlib,json
from pathlib import Path

import pandas as pd

from data3001.dataset import manifest
from data3001.paths import asset_path
from data3001.preprocessing.prep_io import Source
from data3001.preprocessing.prep_pairs import load_track,origin_indices,generate


def collect(selected=None):
    m=manifest();index=pd.read_csv('configs/dataset_index.csv').set_index('id')
    if selected is None:
        boundary=json.loads(asset_path('official_drogue_boundary',verify=True).read_text())['records']
        attached=json.loads(asset_path('official_drogue_correction',verify=True).read_text())['records']
        development=[sid for sid,r in m['records'].items() if r['pool']=='train']
        selected=[]
        for decision in ['nominal_loss','attached_at_end']:
            selected.append(next(int(sid) for sid in development if sid in boundary and
                                 boundary[sid]['decision']==decision and index.loc[int(sid),'in_R']))
        selected.append(next(int(sid) for sid in development if sid in attached))
        selected.append(next(int(sid) for sid in development if index.loc[int(sid),'unknown_rows']==index.loc[int(sid),'rows']))
        selected.append(132499)
        selected=list(dict.fromkeys(selected))
    s=Source();records=[]
    for sid in selected:
        frame,track,events=load_track(s,sid)
        for population in ['R','D']:
            origins=origin_indices(frame,track,population)
            for days in [7,30,365]:
                for scenario in ['drogued','undrogued','pooled']:
                    for target,labels in zip(['endpoint','stopped'],generate(frame,track,events,sid,origins,days,scenario)):
                        definition=json.dumps([(c,str(labels[c].dtype)) for c in labels],separators=(',',':')).encode()
                        digest=hashlib.sha256(definition+pd.util.hash_pandas_object(labels,index=True).to_numpy().tobytes()).hexdigest()
                        records.append({'id':sid,'population':population,'days':days,'scenario':scenario,
                                        'target':target,'rows':len(labels),'sha256':digest})
        print(f'Paired-label fingerprints collected for {sid}',flush=True)
    return {'IDs':selected,'records':records}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--after',action='store_true');args=p.parse_args()
    directory=Path(__file__).resolve().parent
    before=directory/'pairs_before.json'
    baseline=json.loads(before.read_text()) if args.after else None
    result=collect(baseline['IDs'] if baseline else None)
    if args.after:
        assert result==baseline,'Paired label values changed'
        (directory/'pairs_after.json').write_text(json.dumps(result,indent=2)+'\n')
        print(f'All {len(result["records"])} paired outputs unchanged',flush=True)
    else:
        assert not before.exists();before.write_text(json.dumps(result,indent=2)+'\n')
