from pathlib import Path
import json,hashlib,shutil,datetime,os
B=Path.cwd();R=B/'provenance/migrations/data_release_20261016';backup=R/'before';backup.mkdir(exist_ok=False)
for name in ['src','tests','configs','docs']:
 shutil.copytree(B/name,backup/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for name in ['README.md','.gitignore','pyproject.toml']:shutil.copy2(B/name,backup/name)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8<<20),b''):h.update(chunk)
 return h.hexdigest()
rows=[]
with (R/'original_data_inventory.jsonl').open('x') as f:
 for k,p in enumerate(sorted((B/'data').rglob('*'))):
  if p.is_symlink():r={'path':str(p.relative_to(B/'data')),'kind':'symlink','target':os.readlink(p)}
  elif p.is_file():r={'path':str(p.relative_to(B/'data')),'kind':'file','bytes':p.stat().st_size,'sha256':sha(p)}
  elif p.is_dir():r={'path':str(p.relative_to(B/'data')),'kind':'directory'}
  else:raise RuntimeError(str(p))
  f.write(json.dumps(r)+'\n');rows.append(r)
  if k%10000==0:print('frozen entries',k,flush=True)
summary={'created_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_data_entries':len(rows),'original_data_files':sum(r['kind']=='file' for r in rows),'original_file_bytes':sum(r.get('bytes',0) for r in rows),'inventory_sha256':sha(R/'original_data_inventory.jsonl'),'baseline_tests':77,'archive':'archive/data_before_release_20261016','stage':'provenance/migrations/data_release_20261016/staged_data','no_git_publication':True}
(R/'baseline.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
