from pathlib import Path
import hashlib,json,os,sys,time,resource
from datetime import datetime,timezone
import pandas as pd

OUT=Path(__file__).resolve().parents[1]
OLD=OUT.parent/'endpoint_state_20261110T054332Z'
BASE=OUT.parent/'coastal_grounding_20261110T043836Z'
ROOT=OUT.parent.parent/'work_place'
KEY=['id','origin_source_obs','horizon_days']
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while b:=f.read(8*1024**2):h.update(b)
    return h.hexdigest()
def write_json(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
class Session:
    def __init__(self):
        self.started=time.monotonic();self.records={}
        self.expected=json.loads((BASE/'logs/input_manifest.json').read_text())
        self.prior={str(OLD/r['path']):r['sha256'] for r in json.loads((OLD/'logs/output_manifest.json').read_text())['files']}
        self.events=pd.read_csv(self.read(BASE/'results/id_evidence.csv'))
        self.ids=set(self.events.id);assert len(self.ids)==383
        sys.addaudithook(self.guard)
    def guard(self,event,args):
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(args[0])).resolve();mode,flags=args[1:3]
            writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT))
            if writing and not p.is_relative_to(OUT):raise PermissionError('Supplement-only writes')
            if not writing and p.is_relative_to(ROOT):
                if 'restricted_test' in p.parts or ('data' in p.parts and 'test' in p.parts):raise PermissionError('Final test')
                if p.suffix=='.parquet' and p.parent.name in ['train','development'] and p.stem.isdigit() and int(p.stem) not in self.ids:raise PermissionError('Unapproved ID')
        if event in ['os.remove','os.rmdir','os.mkdir','os.chmod'] and isinstance(args[0],(str,bytes,os.PathLike)) and not Path(os.fsdecode(args[0])).resolve().is_relative_to(OUT):raise PermissionError('Original mutation')
    def read(self,path,expected=None):
        p=Path(path).resolve();digest=sha(p)
        key=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
        fixed=self.expected.get(key,{}).get('sha256') if p.is_relative_to(ROOT) else self.prior.get(str(p))
        if expected:assert digest==expected,('source hash',p)
        if fixed:assert digest==fixed,('prior hash',p)
        if str(p) in self.records:assert digest==self.records[str(p)]['sha256']
        self.records[str(p)]={'sha256':digest,'bytes':p.stat().st_size};return p
    def check(self):
        assert time.monotonic()-self.started<1800,'Stage 30 minute budget'
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<6*1024**3,'Memory budget'
        assert sum(f.stat().st_size for f in OUT.rglob('*') if f.is_file())<250*1024**2,'Storage budget'
        assert (datetime.now(timezone.utc)-datetime.fromisoformat('2026-11-10T04:38:36+00:00')).total_seconds()<21600,'Original active-work ceiling'
    def close(self,stage,passed):
        for name,r in self.records.items():assert sha(name)==r['sha256'],('source changed',name)
        write_json(OUT/'logs'/f'{stage}_sources.json',self.records)
        write_json(OUT/'logs'/f'{stage}_verification.json',{'passed':passed,'seconds':time.monotonic()-self.started,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'unchanged_inputs':len(self.records),'model_calls':0,'new_scores':0,'final_test_access':False})
