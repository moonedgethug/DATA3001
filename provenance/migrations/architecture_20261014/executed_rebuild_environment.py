from pathlib import Path
import sys,sysconfig,subprocess,shutil,importlib.metadata as md,json,hashlib
root=Path('/Users/moonedgethug/Documents/UNSW/DATA3001/work_place')
old=root/'data_preprocessing/.venv/lib/python3.12/site-packages';new=root/'.venv'
assert not new.exists()
subprocess.run([sys.executable,'-m','venv','--without-pip',str(new)],check=True)
site=new/'lib/python3.12/site-packages'
for p in old.iterdir():
 q=site/p.name
 if p.is_dir():shutil.copytree(p,q,symlinks=True)
 else:shutil.copy2(p,q)
# Build tooling is copied from the bundled runtime. Scientific packages are not upgraded.
added={}
for name in ['setuptools','wheel']:
 d=md.distribution(name);added[name]=d.version
 for entry in d.files:
  rel=Path(str(entry))
  if '..' in rel.parts:continue
  source=Path(d.locate_file(entry));target=site/rel
  if source.is_file():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
# Recreate entry points with the new interpreter; never move old shebangs.
for dist in md.distributions(path=[str(site)]):
 for ep in dist.entry_points:
  if ep.group!='console_scripts':continue
  target=new/'bin'/ep.name
  if not target.name==ep.name:raise ValueError(ep.name)
  body=f'#!{new}/bin/python\nimport importlib,sys\ndef _entry():\n    value=importlib.import_module({ep.module!r})\n'
  for item in ep.attr.split('.'):body+=f'    value=getattr(value,{item!r})\n'
  body+='    return value()\nif __name__=="__main__":\n    sys.exit(_entry())\n'
  target.write_text(body);target.chmod(0o755)
new_versions={d.metadata['Name'].lower():d.version for d in md.distributions(path=[str(site)])}
old_versions={d.metadata['Name'].lower():d.version for d in md.distributions(path=[str(old)])}
assert all(new_versions[n]==v for n,v in old_versions.items())
receipt={'python_version':sys.version.split()[0],'strategy':'new venv; verified version-preserving copy of installed site-packages; regenerated console entry points; no scientific dependency upgrades','preserved_distributions':old_versions,'build_tooling_added':added}
(root/'provenance/migrations/architecture_20261014/environment_rebuild.json').write_text(json.dumps(receipt,indent=2)+'\n')
(root/'configs/python-version.txt').write_text(sys.version.split()[0]+'\n')
print('Rebuilt environment; all',len(old_versions),'existing distribution versions retained; added build tools:',added,flush=True)
