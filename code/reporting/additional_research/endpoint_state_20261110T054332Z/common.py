import hashlib,json,os,resource,sys,time
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
import numpy as np
from pyproj import Geod

OUT=Path(__file__).resolve().parents[1]
PRIOR=OUT.parent/'coastal_grounding_20261110T043836Z'
ROOT=OUT.parent.parent/'work_place'
KEY=['id','origin_source_obs','horizon_days']
G=Geod(ellps='WGS84')
STATES=['grounding_evidence','drifting_evidence','uncertain','endpoint_missing']
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        while b:=f.read(8*1024**2):h.update(b)
    return h.hexdigest()
def write_json(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
class Session:
    def __init__(self):
        self.started=time.monotonic();self.records={}
        self.expected=json.loads((PRIOR/'logs/input_manifest.json').read_text())
        previous=json.loads((PRIOR/'logs/output_manifest.json').read_text())
        self.prior_expected={str(PRIOR/r['path']):r['sha256'] for r in previous['files']}
        self.events=pd.read_csv(self.read(PRIOR/'results/id_evidence.csv'))
        assert self.events.groupby('cohort').id.size().to_dict()=={'train':338,'validation':45}
        self.ids=set(self.events.id)
        sys.addaudithook(self.guard)
    def guard(self,event,args):
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(args[0])).resolve();mode,flags=args[1:3]
            writing=(isinstance(mode,str) and any(v in mode for v in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT))
            if writing and not p.is_relative_to(OUT):raise PermissionError('Write outside independent supplement')
            if not writing and p.is_relative_to(ROOT):
                if 'restricted_test' in p.parts or ('data' in p.parts and 'test' in p.parts):raise PermissionError('Final test access')
                if p.suffix=='.parquet' and p.parent.name in ['train','development'] and p.stem.isdigit() and int(p.stem) not in self.ids:raise PermissionError('Unapproved ID')
        if event in ['os.remove','os.rmdir','os.mkdir','os.chmod'] and isinstance(args[0],(str,bytes,os.PathLike)):
            if not Path(os.fsdecode(args[0])).resolve().is_relative_to(OUT):raise PermissionError('Mutation outside supplement')
    def read(self,p,expected=None):
        p=Path(p).resolve();key=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
        prior=self.expected.get(key,{}).get('sha256') if p.is_relative_to(ROOT) else self.prior_expected.get(str(p))
        digest=sha(p)
        if expected:assert digest==expected,('manifest mismatch',p)
        if prior:assert digest==prior,('prior mismatch',p)
        if str(p) in self.records:assert digest==self.records[str(p)]['sha256']
        self.records[str(p)]={'sha256':digest,'bytes':p.stat().st_size}
        return p
    def check(self):
        if time.monotonic()-self.started>1800:raise RuntimeError('30 minute stage budget')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>6*1024**3:raise RuntimeError('RSS budget')
        if sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())>250*1024**2:raise RuntimeError('Artifact budget')
        if (datetime.now(timezone.utc)-datetime.fromisoformat('2026-11-10T04:38:36+00:00')).total_seconds()>21600:raise RuntimeError('Original 6 hour work budget')
    def close(self,stage,passed):
        for name,r in self.records.items():assert sha(name)==r['sha256'],('source changed',name)
        write_json(OUT/'logs'/f'{stage}_sources.json',self.records)
        write_json(OUT/'logs'/f'{stage}_verification.json',{'passed':passed,'seconds':time.monotonic()-self.started,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'unchanged_inputs':len(self.records),'model_calls':0,'new_scores':0,'final_test_access':False})

def quality(valid,offsets):
    offsets=np.asarray(offsets)
    count=valid.sum(axis=1);gap=np.zeros(len(valid),dtype=int);last=np.full(len(valid),offsets[0],dtype=int)
    for j,o in enumerate(offsets):
        present=valid[:,j];gap=np.maximum(gap,np.where(present,o-last,0));last=np.where(present,o,last)
    minimum=20 if len(offsets)==25 else 136
    okay=valid[:,0]&valid[:,-1]&(count>=minimum)&(gap<=6)
    return okay,count,gap

def motion_metrics(track,flags,targets,official_end,land):
    import shapely as sh
    t=track.loc[flags.analytical_row.to_numpy()].copy();f=flags.loc[flags.analytical_row.to_numpy()]
    assert not t.time.duplicated().any()
    offsets=np.arange(-24,25)
    ix=pd.Index(t.time).get_indexer((targets[:,None]+offsets[None,:]*3600).ravel()).reshape(len(targets),49)
    safe=np.maximum(ix,0)
    good=(f.position_ok&f.mapping_ok).to_numpy()&t.time.le(official_end).to_numpy()
    valid=(ix>=0)&good[safe]
    lon=t.lon_normalized.to_numpy()[safe];lat=t.lat.to_numpy()[safe]
    on_land=sh.intersects_xy(land,lon,lat)&valid
    before,n_before,gap_before=quality(valid[:,:25],offsets[:25])
    after,n_after,gap_after=quality(valid[:,24:],offsets[24:])
    def dist(i,j):
        d=G.inv(lon[:,i],lat[:,i],lon[:,j],lat[:,j])[2]/1000
        return np.where(valid[:,i]&valid[:,j],d,np.nan)
    return pd.DataFrame({'before_complete':before,'after_complete':after,'before_hours':n_before,'after_hours':n_after,
        'before_max_gap_h':gap_before,'after_max_gap_h':gap_after,'before_24h_km':dist(0,24),'after_24h_km':dist(24,48),
        'before_6h_km':dist(18,24),'after_6h_km':dist(24,30),'motion_land_points':on_land.sum(axis=1)})

def stay_metrics(track,flags,targets,official_end):
    t=track.loc[flags.analytical_row.to_numpy()].copy();f=flags.loc[flags.analytical_row.to_numpy()]
    offsets=np.arange(169);ix=pd.Index(t.time).get_indexer((targets[:,None]+offsets[None,:]*3600).ravel()).reshape(len(targets),169)
    safe=np.maximum(ix,0);good=(f.position_ok&f.mapping_ok).to_numpy()&t.time.le(official_end).to_numpy()
    valid=(ix>=0)&good[safe];lon=t.lon_normalized.to_numpy()[safe];lat=t.lat.to_numpy()[safe]
    okay,count,gap=quality(valid,offsets)
    d=G.inv(np.broadcast_to(lon[:,:1],lon.shape).ravel(),np.broadcast_to(lat[:,:1],lat.shape).ravel(),lon.ravel(),lat.ravel())[2].reshape(lon.shape)/1000
    radius=np.max(np.where(valid,d,-np.inf),axis=1);radius[~valid[:,0]]=np.nan
    return pd.DataFrame({'stay_complete':okay,'stay_hours':count,'stay_max_gap_h':gap,'stay_radius_km':radius})

def classify(f,threshold=5):
    states=np.full(len(f),'uncertain',dtype=object)
    moving=(f.endpoint_available & ~f.endpoint_on_land & ~f.metadata_conflict & f.before_complete & f.after_complete &
        f.before_24h_km.ge(threshold)&f.after_24h_km.ge(threshold)&f.before_6h_km.ge(1)&f.after_6h_km.ge(1)&f.motion_land_points.eq(0))
    states[moving]='drifting_evidence'
    # Grounding evidence is never promoted without the individual review step.
    if 'ground_review_passed' in f:states[f.ground_candidate&f.ground_review_passed]='grounding_evidence'
    states[~f.endpoint_available]='endpoint_missing'
    return states
