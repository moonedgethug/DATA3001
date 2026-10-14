"""Catch wrong asset selection, leaked test access and frozen-output mutation."""
import hashlib
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

class Architecture(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);(self.root/'configs').mkdir();(self.root/'data').mkdir()
  (self.root/'data/a.bin').write_bytes(b'original')
  (self.root/'data/test.bin').write_bytes(b'held-out')
  self.config={'schema_version':1,'assets':{'native':{'path':'data/a.bin','kind':'file','sha256':hashlib.sha256(b'original').hexdigest(),'split':'all'},'test_labels':{'path':'data/test.bin','kind':'file','split':'test'}}}
  (self.root/'configs/assets.json').write_text(json.dumps(self.config))
 def api(self):
  # Missing behaviour fails as an assertion during RED, rather than an import error.
  self.assertIsNotNone(importlib.util.find_spec('data3001.paths'),'Portable asset boundary is missing')
  return importlib.import_module('data3001.paths')
 def test_resolves_asset_independently_of_current_directory(self):
  p=self.api().ProjectPaths(self.root);self.assertEqual(p.asset('native').read_bytes(),b'original')
 def test_missing_registered_directory_does_not_prevent_imports(self):
  self.config['assets']['prepared']={'path':'data/absent','kind':'directory','split':'development'}
  (self.root/'configs/assets.json').write_text(json.dumps(self.config))
  p=self.api().ProjectPaths(self.root)
  self.assertEqual(p.asset('prepared',must_exist=False),(self.root/'data/absent').resolve())
  with self.assertRaises(FileNotFoundError):p.asset('prepared')
 def test_modified_source_fails_checksum(self):
  p=self.api().ProjectPaths(self.root);(self.root/'data/a.bin').write_bytes(b'changed')
  with self.assertRaises(ValueError):p.asset('native',verify=True)
 def test_test_labels_are_denied_by_default(self):
  p=self.api().ProjectPaths(self.root)
  with self.assertRaises(PermissionError):p.asset('test_labels')
  self.assertEqual(p.asset('test_labels',allow_test=True).read_bytes(),b'held-out')
 def test_catalog_path_cannot_escape_project(self):
  self.config['assets']['native']['path']='../escape';(self.root/'configs/assets.json').write_text(json.dumps(self.config))
  with self.assertRaises(ValueError):self.api().ProjectPaths(self.root).asset('native')
 def test_legacy_mapping_restricts_test_partitions(self):
  (self.root/'configs/legacy_paths.json').write_text(json.dumps({'file_map':{'preparation/restricted_test/a.parquet':'data/test.bin'},'directory_map':{}}))
  p=self.api().ProjectPaths(self.root)
  with self.assertRaises(PermissionError):p.legacy('preparation/restricted_test/a.parquet')
 def test_historical_alias_cannot_bypass_test_partition_lock(self):
  (self.root/'configs/legacy_paths.json').write_text(json.dumps({'file_map':{'preparation/audit/old_test_support.parquet':'data/restricted_test/history/test.parquet'},'directory_map':{}}))
  p=self.api().ProjectPaths(self.root)
  with self.assertRaises(PermissionError):p.legacy('preparation/audit/old_test_support.parquet')
 def test_frozen_write_is_rejected_before_existing_bytes_change(self):
  p=self.api().ProjectPaths(self.root)
  with self.assertRaises(PermissionError):p.output('data/a.bin')
  self.assertEqual((self.root/'data/a.bin').read_bytes(),b'original')
 def test_run_collision_preserves_existing_results(self):
  p=self.api().ProjectPaths(self.root);run=p.create_run('trial',{'lag_days':7});(run['results']/'score.txt').write_text('first')
  with self.assertRaises(FileExistsError):p.create_run('trial',{'lag_days':3})
  self.assertEqual((run['results']/'score.txt').read_text(),'first')
 def test_run_id_cannot_escape_run_namespace(self):
  with self.assertRaises(ValueError):self.api().ProjectPaths(self.root).create_run('../bad',{})

if __name__=='__main__':unittest.main()
