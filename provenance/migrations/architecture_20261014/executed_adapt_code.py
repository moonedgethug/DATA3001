from pathlib import Path
import ast,json,re,hashlib,shutil
root=Path('/Users/moonedgethug/Documents/UNSW/DATA3001/work_place');back=root.parent/'.migration_backups/architecture_20261014/work_place/data_preprocessing'
modules={p.stem:('acquisition' if not p.stem.startswith('prep_') and p.stem!='verify_handover' else 'preprocessing') for p in (back/'scripts').glob('*.py')}
modules['verify_acquisition']='acquisition';modules['rules']='acquisition'
mutators={
 'acquire_hourly':{'json_save','get','freeze_geometry','metadata','discover','retrieve','main','__init__'},
 'downstream_acquisition':{'main'},'export_subset':{'main'},'pilot_audit':{'main'},'verify_acquisition':{'main'},
 'prep_run':{'clean','prototype'},'prep_pairs':{'compact','main'},'prep_geometry':{'audit_domains','state_index'},
 'prep_handover':{'areas','lags','depths','coverage','source_reason','main'},'prep_peers':{'diagnose'},
 'prep_support':{'process','aggregate'},'prep_boundary_diagnostics':{'run'},'prep_report':{'figures','report'},
 'prep_verify':{'verify'},'verify_handover':{'verify'},
}
for stage in ['acquisition','preprocessing']:
 d=root/'src/data3001'/stage;d.mkdir(exist_ok=True);(d/'__init__.py').write_text('"""Preserved scientific logic with explicit migrated asset boundaries."""\n')
summary=[]
for name,stage in modules.items():
 source=back/'scripts'/f'{name}.py';text=source.read_text();tree=ast.parse(text);lines=text.splitlines(keepends=True);offsets=[0]
 for line in lines:offsets.append(offsets[-1]+len(line))
 def span(n):return offsets[n.lineno-1]+n.col_offset,offsets[n.end_lineno-1]+n.end_col_offset
 def raw(n):a,b=span(n);return text[a:b]
 patches=[]
 def change(n,replacement):a,b=span(n);patches.append((a,b,replacement))
 # Import changes preserve all function bodies and computation expressions.
 for n in ast.walk(tree):
  if isinstance(n,ast.ImportFrom) and n.module in modules:
   names=', '.join(x.name+(f' as {x.asname}' if x.asname else '') for x in n.names)
   change(n,f'from data3001.{modules[n.module]}.{n.module} import {names}')
  elif isinstance(n,ast.Import) and any(x.name in modules for x in n.names):
   replacement=[]
   for x in n.names:
    if x.name in modules:replacement.append(f'from data3001.{modules[x.name]} import {x.name} as {x.asname or x.name}')
    else:replacement.append(f'import {x.name}'+(f' as {x.asname}' if x.asname else ''))
   change(n,'; '.join(replacement))
 root_scopes={'BASE':[], 'OUT':['preparation'], 'ROOT':(['preparation','remediation_20261013'] if name in ['prep_handover','verify_handover'] else [])}
 def division_parts(n):
  if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
   left=division_parts(n.left)
   if left is not None:return left+[n.right]
  if isinstance(n,ast.Name) and n.id in root_scopes:return [n.id]
  return None
 def visit(n):
  if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Div):
   parts=division_parts(n)
   if parts is not None:
    args=[repr(x) for x in root_scopes[parts[0]]]+[raw(x) for x in parts[1:]]
    change(n,'legacy_path('+', '.join(args)+')');return
  for c in ast.iter_child_nodes(n):visit(c)
 visit(tree)
 for n in ast.walk(tree):
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in mutators.get(name,set()):
   pos=offsets[n.lineno-1];patches.append((pos,pos,' '*n.col_offset+'@frozen_action\n'))
 for a,b,replacement in sorted(patches,reverse=True):text=text[:a]+replacement+text[b:]
 # Central root aliases are readable paths, not custom Path proxy objects.
 if name=='acquire_hourly':text=text.replace('ROOT = Path(__file__).resolve().parents[1]','ROOT = project_paths().root')
 if name=='prep_io':
  text=text.replace('BASE=Path(__file__).resolve().parents[1]','BASE=project_paths().root').replace("OUT=legacy_path('preparation')","OUT=asset_path('prepared_development')")
  text=text.replace("'authoritative_contract'])","'authoritative_contract'])")
  text=text.replace("sha(authority['authoritative_contract'])","sha(asset_path('english_contract'))")
  text=text.replace("def __init__(self):\n        self.g=", "def __init__(self, *, allow_test=False):\n        self.allow_test=allow_test\n        self.g=")
  text=text.replace("i=self.index[int(id)];start,end=self.offset[i:i+2]", "if self.cohort.loc[int(id),'split']=='test' and not self.allow_test:raise PermissionError('Final-test trajectory access requires explicit permission')\n        i=self.index[int(id)];start,end=self.offset[i:i+2]")
  text=text.replace("p=Path(p);p.parent.mkdir", "p=ensure_output_path(p);p.parent.mkdir")
  text=text.replace("path=Path(path);path.parent.mkdir", "path=ensure_output_path(path);path.parent.mkdir")
  start=text.index('def code_hash():');end=text.index('\n\n',start)
  text=text[:start]+"def code_hash():\n    files=sorted((project_paths().root/'src/data3001').rglob('*.py'))\n    return hashlib.sha256(''.join(sha(p) for p in files).encode()).hexdigest()"+text[end:]
 if name=='prep_geometry':
  text=text.replace("else:\n        files=list", "else:\n        raise PermissionError('Frozen mask is missing; restore its verified asset rather than rebuilding in place')\n        files=list")
 if name=='prep_run':
  # Keep the test directory explicitly locked at this I/O boundary.
  old="def directory(split):return legacy_path('preparation', 'restricted_test/cleaned') if split=='test' else legacy_path('preparation', 'cleaned')"
  new="def directory(split, *, allow_test=False):return legacy_path('preparation', 'restricted_test/cleaned', allow_test=allow_test) if split=='test' else legacy_path('preparation', 'cleaned')"
  assert old in text;text=text.replace(old,new)
 if name=='prep_pairs':text=text.replace("directory(split)/f'{id}.parquet'", "directory(split,allow_test=s.allow_test)/f'{id}.parquet'")
 text='from data3001.paths import legacy_path, asset_path, project_paths, ensure_output_path, frozen_action\n'+text
 ast.parse(text)
 (root/'src/data3001'/stage/f'{name}.py').write_text(text)
 summary.append({'module':name,'stage':stage,'archived_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'frozen_actions':sorted(mutators.get(name,set()))})
# Existing test assertions are unchanged; only namespaced imports are adapted.
for source in (back/'tests').glob('test_*.py'):
 text=source.read_text();text=re.sub(r"sys.path.insert\([^\n]+\)\n",'',text)
 text=text.replace('import rules\n','from data3001.acquisition import rules\n').replace('import prep_core as c','from data3001.preprocessing import prep_core as c')
 text=text.replace("find_spec('prep_handover')","find_spec('data3001.preprocessing.prep_handover')").replace("import_module('prep_handover')","import_module('data3001.preprocessing.prep_handover')")
 # Local imports in regression cases also use package names.
 text=text.replace('from prep_geometry import','from data3001.preprocessing.prep_geometry import')
 (root/'tests'/source.name).write_text(text)
(root/'provenance/migrations/architecture_20261014/code_adaptation.json').write_text(json.dumps(summary,indent=2)+'\n')
print('Adapted',len(summary),'modules; existing assertions retained.',flush=True)
