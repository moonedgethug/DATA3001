"""CLI remains available without large data and does not create run files."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

class CLI(unittest.TestCase):
 def test_help_is_available_from_another_working_directory(self):
  with tempfile.TemporaryDirectory() as d:
   r=subprocess.run([sys.executable,'-m','data3001','--help'],cwd=d,capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
   self.assertIn('verify-migration',r.stdout)
 def test_inspection_does_not_create_a_run_or_open_missing_large_data(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'configs').mkdir();(root/'configs/assets.json').write_text(json.dumps({'schema_version':1,'research_contract_version':'1.0','current_data_status':'prepared, unscored','assets':{'native':{'path':'data/absent','kind':'directory','split':'all'}}}))
   r=subprocess.run([sys.executable,'-m','data3001','--root',d,'inspect'],cwd=d,capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['research_contract_version'],'1.0')
   self.assertFalse((root/'results').exists());self.assertFalse((root/'provenance').exists())

if __name__=='__main__':unittest.main()
