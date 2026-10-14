"""Catch mutation and missing/symlink assets without altering source receipts."""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

class Migration(unittest.TestCase):
 def api(self):
  self.assertIsNotNone(importlib.util.find_spec('data3001.migration'),'Read-only migration verifier is missing')
  from data3001.migration import verify_inventory
  return verify_inventory
 def test_changed_bytes_are_reported_without_rewriting_receipt(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);(r/'a').write_bytes(b'changed');(r/'receipt').write_bytes(b'frozen')
   entries=[{'path':'old/a','destination':'a','kind':'file','bytes':8,'sha256':hashlib.sha256(b'original').hexdigest()},{'path':'old/receipt','destination':'receipt','kind':'file','bytes':6,'sha256':hashlib.sha256(b'frozen').hexdigest()}]
   result=self.api()(r,entries)
   self.assertFalse(result['passed']);self.assertEqual(result['mismatches'][0]['original'],'old/a');self.assertEqual((r/'receipt').read_bytes(),b'frozen')
 def test_missing_file_and_changed_symlink_fail_verification(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);(r/'link').symlink_to('wrong')
   entries=[{'path':'old/link','destination':'link','kind':'symlink','target':'right'},{'path':'old/missing','destination':'missing','kind':'file','bytes':1,'sha256':'unused'}]
   result=self.api()(r,entries)
   self.assertFalse(result['passed']);self.assertEqual(len(result['mismatches']),2)

if __name__=='__main__':unittest.main()
