"""Actual model-view regression cases, skipped without the local data bundle."""
from pathlib import Path
import unittest
import numpy as np


class CurrentModelSSTView(unittest.TestCase):
    def setUp(self):
        if not (Path(__file__).resolve().parents[1]/'data/train/43869.parquet').exists():
            self.skipTest('Complete local data required')

    def test_native_high_value_has_approved_replacement_in_the_existing_column(self):
        from data3001.sst_sparse_current import read_sst_track
        frame=read_sst_track(43869)
        row=frame.loc[frame.time_UTC.eq('2014-10-13T00:00:00Z')].iloc[0]
        self.assertTrue(np.isfinite(row.sst))
        self.assertAlmostEqual(float(row.sst)-273.15,28.130305,places=4)
        self.assertNotIn('sst_use_K',frame.columns)
        self.assertNotIn('sst_reason',frame.columns)

    def test_final_test_guard_still_denies_normal_model_reading(self):
        from data3001.dataset import manifest
        from data3001.sst_sparse_current import read_sst_track
        sid=next(int(sid) for sid,r in manifest()['records'].items() if r['pool']=='test')
        with self.assertRaises(PermissionError):read_sst_track(sid)


if __name__=='__main__':unittest.main()
