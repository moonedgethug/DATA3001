from pathlib import Path
import unittest
import numpy as np


class TotalSSTCurrent(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]
        if not any((root/f'data/{pool}/60350.parquet').exists() for pool in ['train','test']):
            self.skipTest('Complete local data required')

    def test_corroborated_total_anomaly_is_stored_in_sst_without_extra_temperature_column(self):
        from data3001.sst_sparse_current import read_sst_track
        f=read_sst_track(60350,allow_test=True)
        row=f.loc[f.time_UTC.eq('2006-07-01T12:00:00Z')].iloc[0]
        self.assertAlmostEqual(float(row.sst)-273.15,27.785621,places=4)
        self.assertNotIn('sst_use_K',f.columns)
        from data3001.dataset import manifest
        self.assertEqual(f.shape[1],manifest()['fields'])
        if manifest()['version']=='per-drifter-cleaned-20261017-v5':
            self.assertNotIn('regime',f.columns)


if __name__=='__main__':unittest.main()
