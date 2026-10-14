from pathlib import Path
import hashlib, json, shutil, os, time
ROOT=Path('/Users/moonedgethug/Documents/UNSW/DATA3001/work_place')
BACK=ROOT.parent/'.migration_backups/architecture_20261014'
DEST=BACK/'work_place'
assert not DEST.exists(), 'Existing backup: inspect rather than overwrite'
DEST.mkdir()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
entries=[]; began=time.monotonic()
paths=sorted(ROOT.rglob('*'))
for i,p in enumerate(paths):
 rel=p.relative_to(ROOT); q=DEST/rel
 if p.is_symlink():
  q.parent.mkdir(parents=True,exist_ok=True);q.symlink_to(os.readlink(p));entry={'path':rel.as_posix(),'kind':'symlink','target':os.readlink(p)}
 elif p.is_dir():q.mkdir(exist_ok=True);continue
 elif p.is_file():
  before=p.stat();digest=sha(p);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
  after=p.stat()
  assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),(rel,'changed during freeze')
  assert sha(q)==digest,(rel,'backup mismatch')
  entry={'path':rel.as_posix(),'kind':'file','bytes':before.st_size,'sha256':digest,'mtime_ns':before.st_mtime_ns}
 else:raise RuntimeError(('Unsupported filesystem object',str(rel)))
 if '.git' not in rel.parts:entries.append(entry)
 if i%10000==0:print('Frozen and verified',i,'/',len(paths),flush=True)
external=[]
for p in [ROOT.parent/'outputs/01a09d9c-2168-7d51-8b63-87eb559bf139/data_contract_v1.0.xlsx',ROOT.parent/'outputs/01a09d9c-2168-7d51-8b63-87eb559bf139/data_contract_v1.0_zh.xlsx',ROOT.parent/'submission_proposal/proposal_final.docx']:
 q=BACK/'external'/p.name;q.parent.mkdir(exist_ok=True);shutil.copy2(p,q);digest=sha(p);assert sha(q)==digest
 external.append({'source':str(p),'backup':str(q.relative_to(BACK)),'sha256':digest,'bytes':p.stat().st_size})
manifest={'version':1,'migration_id':'architecture_20261014','original_root':str(ROOT),'backup_root':str(DEST),'entries':entries,'external':external,'backup_verified':True,'elapsed_seconds':time.monotonic()-began}
(BACK/'baseline.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'backup_verified':True,'entries':len(entries),'bytes':sum(e.get('bytes',0) for e in entries),'external':len(external),'elapsed_seconds':manifest['elapsed_seconds']}),flush=True)
