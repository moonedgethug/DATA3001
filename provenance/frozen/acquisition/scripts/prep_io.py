"""Read-only input access; no acquisition constructors or network calls."""
from pathlib import Path
from collections import OrderedDict
import hashlib,json,datetime
import numpy as np
import pandas as pd
import zarr

BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'preparation'
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save_json(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)));tmp.replace(p)
def parquet(df,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp.parquet')
    df.to_parquet(tmp,index=False,compression='zstd');tmp.replace(path)
def code_hash():
    return hashlib.sha256(''.join(sha(p) for p in sorted((BASE/'scripts').glob('prep_*.py'))).encode()).hexdigest()

class Source:
    def __init__(self):
        self.g=zarr.open_consolidated(str(BASE/'raw/hourly_subset_v2.01.1.zarr'),mode='r')
        self.ids=self.g['id'][:];self.sizes=self.g['rowsize'][:]
        self.offset=np.r_[0,np.cumsum(self.sizes,dtype=np.int64)]
        self.index={int(v):i for i,v in enumerate(self.ids)}
        self.cohort=pd.read_csv(BASE/'manifests/acquired_ids.csv',dtype={'id':'int64'}).set_index('id')
        self.R=set(pd.read_csv(BASE/'manifests/R_ids.csv')['id'])
        self.snapshot=json.loads((BASE/'manifests/source_snapshot.json').read_text())
        self.cache={}
    def read(self,k,start,end):
        a=self.g[k];width=a.chunks[0];cache=self.cache.setdefault(k,OrderedDict());parts=[]
        for ci in range(start//width,(end-1)//width+1):
            if ci not in cache:cache[ci]=a[ci*width:min((ci+1)*width,a.shape[0])]
            cache.move_to_end(ci);parts.append(cache[ci][max(start-ci*width,0):min(end-ci*width,width)])
            while len(cache)>2:cache.popitem(last=False)
        return np.concatenate(parts) if len(parts)>1 else parts[0].copy()
    def track(self,id):
        i=self.index[int(id)];start,end=self.offset[i:i+2]
        d={k:self.read(k,int(start),int(end)) for k in self.g.array_keys() if self.g[k].attrs.get('_ARRAY_DIMENSIONS')==['obs']}
        meta={k:self.g[k][i].item() for k in self.g.array_keys() if self.g[k].attrs.get('_ARRAY_DIMENSIONS')==['traj']}
        return d,meta
    def verify(self):
        authority=json.loads((BASE/'manifests/authority.json').read_text());assert sha(authority['authoritative_contract'])==authority['contract_sha256']
        receipt=json.loads((BASE/'audit/acquisition_verification.json').read_text())
        failures={k:sha(BASE/k) for k,h in receipt['bound_file_SHA256'].items() if sha(BASE/k)!=h}
        assert not failures,failures
        assert len(self.ids)==3741 and int(self.sizes.sum())==39107061
        assert set(self.ids)==set(self.cohort.index)
        global_ids=pd.read_csv(BASE/'manifests/global_id_split.csv',dtype={'id':'int64'}).set_index('id')
        def split(id):
            n=int.from_bytes(hashlib.sha256(f'20261004:{int(id)}'.encode('ascii')).digest(),'big')
            return 'train' if n*100<70*2**256 else 'validation' if n*100<85*2**256 else 'test'
        assert all(row['split']==split(id) for id,row in global_ids.iterrows())
        assert all(row['split']==global_ids.loc[id,'split'] for id,row in self.cohort.iterrows())
        return {'utc':now(),'IDs':len(self.ids),'rows':int(self.sizes.sum()),'R_IDs':len(self.R),
                'R_rows':int(sum(self.sizes[self.index[int(v)]] for v in self.R)),
                'split_counts':self.cohort['split'].value_counts().to_dict(),
                'R_split_counts':self.cohort.loc[list(self.R),'split'].value_counts().to_dict(),
                'bound_files_verified':len(receipt['bound_file_SHA256']),
                'whole_global_ID_split_verified':len(global_ids),'source_snapshot_sha':sha(BASE/'manifests/source_snapshot.json')}
