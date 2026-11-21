"""Read-only sources, supplemental-only outputs, cumulative resource accounting."""
import hashlib,json,os,resource,shutil,sys,time
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
from diagnostic import check_read_path,check_write_path

ROOT=Path('/Users/moonedgethug/Documents/UNSW/DATA3001/work_place')
OUT=Path(__file__).resolve().parents[1]
RES=OUT/'results'; LOG=OUT/'logs'
AUDIT=ROOT/'provenance/reviews/official_time_boundary_cohort_20261108'
E7=ROOT/'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z'
MDN=ROOT/'results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1'
FREEZE=ROOT/'provenance/frozen/mdn_final_20261110_v1'
LABELS=ROOT/'results/runs/markov_input_20261025T095949_830292Z/release_labels'
STAGE_LIMITS={'preflight':900,'events':1200,'availability':1800,'coastal':2100,'audit':1200}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while b:=f.read(8*1024*1024):h.update(b)
    return h.hexdigest()

def json_write(path,value):
    check_write_path(path,OUT)
    tmp=Path(str(path)+'.tmp');tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False,default=str)+'\n')
    tmp.replace(path)

class Sources:
    def __init__(self):
        self.records=json.loads((LOG/'input_manifest.json').read_text()) if (LOG/'input_manifest.json').exists() else {}
        self.access=[];self.ids=set();self.active=False
    def guard(self,event,args):
        if not self.active:return
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(args[0])).resolve();mode,flags=args[1:3]
            writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT))
            if writing:check_write_path(p,OUT)
            elif p.is_relative_to(ROOT):
                check_read_path(p,self.ids)
                self.access.append(str(p.relative_to(ROOT)))
        if event in ['os.remove','os.rmdir','os.mkdir','os.chmod'] and isinstance(args[0],(str,bytes,os.PathLike)):
            check_write_path(Path(os.fsdecode(args[0])),OUT)
        if event in ['os.rename','os.link','os.symlink']:
            for p in args[:2]:
                if isinstance(p,(str,bytes,os.PathLike)):check_write_path(Path(os.fsdecode(p)),OUT)
    def install(self,ids):self.ids=set(map(int,ids));sys.addaudithook(self.guard);self.active=True
    def verified(self,path,expected=None):
        p=Path(path).resolve();check_read_path(p,self.ids)
        digest=sha(p);key=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
        if expected and digest!=expected:raise ValueError('Source digest mismatch: '+key)
        if key in self.records and self.records[key]['sha256']!=digest:raise ValueError('Source drift: '+key)
        self.records[key]={'sha256':digest,'bytes':p.stat().st_size}
        return p
    def frame(self,path,expected=None,columns=None,filters=None):
        p=self.verified(path,expected)
        with p.open('rb') as f:
            return pq.read_table(f,columns=columns,filters=filters).to_pandas() if p.suffix=='.parquet' else pd.read_csv(f)
    def json(self,path,expected=None):return json.loads(self.verified(path,expected).read_text())
    def save(self):
        json_write(LOG/'input_manifest.json',self.records)
        p=LOG/'access_log.json'; prior=json.loads(p.read_text()) if p.exists() else []
        json_write(p,sorted(set(prior+self.access)))

@contextmanager
def stage(name):
    started=time.monotonic();p=LOG/'resource_log.json'
    records=json.loads(p.read_text()) if p.exists() else []
    prior=sum(r['seconds'] for r in records)
    if prior>=7200:raise RuntimeError('Computation budget exhausted')
    if time.time()-datetime.fromisoformat('2026-11-10T04:38:36+00:00').timestamp()>21600:raise RuntimeError('Active work budget exceeded')
    used=sum(r['seconds'] for r in records if r['stage']==name)
    def check():
        elapsed=time.monotonic()-started
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if elapsed+prior>7200 or elapsed+used>STAGE_LIMITS[name]:raise RuntimeError('Stage/computation budget exceeded')
        if rss>6*1024**3:raise RuntimeError('RSS limit')
        if shutil.disk_usage(OUT).free<2*1024**3:raise RuntimeError('Disk floor')
        if sum(x.stat().st_size for x in OUT.rglob('*') if x.is_file())>1024**3:raise RuntimeError('Output storage cap')
    status='failed'
    try:
        check();yield check;check();status='complete'
    finally:
        records.append({'stage':name,'seconds':time.monotonic()-started,'status':status,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
        json_write(p,records)

def save_frame(name,frame):
    path=RES/name;check_write_path(path,OUT)
    if path.suffix=='.parquet':frame.to_parquet(path,index=False)
    else:frame.to_csv(path,index=False)

def start():
    s=Sources()
    roster=s.frame(AUDIT/'cohort_roster.csv')
    assert roster.id.dtype.kind in 'iu' and not roster.id.duplicated().any()
    assert roster.groupby('cohort').id.size().to_dict()=={'train':338,'validation':45}
    s.install(roster.id)
    return s,roster
