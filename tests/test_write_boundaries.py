"""Real filesystem regressions for the independent review's three defects."""
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,os,tempfile,threading,unittest
from pathlib import Path
import pandas as pd
from data3001.paths import ProjectPaths,project_paths
from data3001.preprocessing.prep_io import save_json,parquet

class WriteBoundaries(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve()
  (self.root/'configs').mkdir();(self.root/'data').mkdir();(self.root/'data/frozen.bin').write_bytes(b'untouched')
  config={'schema_version':1,'assets':{'prepared_development':{'path':'data/absent','kind':'directory','split':'development'},'alias':{'path':'data/development_alias','kind':'file','split':'development'}}}
  (self.root/'configs/assets.json').write_text(json.dumps(config));self.paths=ProjectPaths(self.root)
  self.previous=os.environ.get('DATA3001_PROJECT_ROOT');os.environ['DATA3001_PROJECT_ROOT']=str(self.root);project_paths.cache_clear();self.addCleanup(self.restore_root)
 def restore_root(self):
  if self.previous is None:os.environ.pop('DATA3001_PROJECT_ROOT',None)
  else:os.environ['DATA3001_PROJECT_ROOT']=self.previous
  project_paths.cache_clear()
 def test_provenance_parent_symlink_cannot_create_run_in_frozen_data(self):
  (self.root/'provenance').mkdir();(self.root/'provenance/runs').symlink_to(self.root/'data',target_is_directory=True)
  with self.assertRaises(PermissionError):self.paths.create_run('escape',{})
  self.assertFalse((self.root/'data/escape').exists())
 def test_results_parent_symlink_is_rejected_before_any_run_creation(self):
  (self.root/'results').mkdir();(self.root/'results/runs').symlink_to(self.root/'data',target_is_directory=True)
  with self.assertRaises(PermissionError):self.paths.create_run('escape',{})
  self.assertFalse((self.root/'data/escape').exists());self.assertFalse((self.root/'provenance/runs/escape').exists())
 def test_catalog_development_alias_cannot_expose_resolved_test_file(self):
  target=self.root/'data/restricted_test/labels';target.parent.mkdir();target.write_bytes(b'test')
  (self.root/'data/development_alias').symlink_to(target)
  with self.assertRaises(PermissionError):self.paths.asset('alias')
  self.assertEqual(self.paths.asset('alias',allow_test=True).read_bytes(),b'test')
 def output(self,name):return self.paths.create_run(name,{})['results']
 def test_json_temporary_symlink_cannot_overwrite_frozen_input(self):
  directory=self.output('json');(directory/'output.json.tmp').symlink_to(self.root/'data/frozen.bin')
  save_json(directory/'output.json',{'x':1})
  self.assertEqual((self.root/'data/frozen.bin').read_bytes(),b'untouched')
 def test_parquet_temporary_symlink_cannot_overwrite_frozen_input(self):
  directory=self.output('parquet');(directory/'output.tmp.parquet').symlink_to(self.root/'data/frozen.bin')
  parquet(pd.DataFrame({'x':[1]}),directory/'output.parquet')
  self.assertEqual((self.root/'data/frozen.bin').read_bytes(),b'untouched')
 def test_old_temporary_regular_file_is_not_truncated_or_consumed(self):
  directory=self.output('leftover');old=directory/'output.json.tmp';old.write_bytes(b'other-writer')
  save_json(directory/'output.json',{'x':1})
  self.assertTrue(old.exists());self.assertEqual(old.read_bytes(),b'other-writer')
 def test_competing_writers_publish_exactly_one_complete_artifact(self):
  target=self.output('competing')/'result.bin';barrier=threading.Barrier(2)
  self.assertTrue(hasattr(self.paths,'publish'),'Exclusive artifact publication is missing')
  def work(value):
   def writer(stream):barrier.wait(timeout=3);stream.write(value)
   try:self.paths.publish(target,writer);return 'published'
   except FileExistsError:return 'collision'
  with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(work,[b'one',b'two']))
  self.assertEqual(sorted(outcomes),['collision','published']);self.assertIn(target.read_bytes(),[b'one',b'two'])

if __name__=='__main__':unittest.main()
