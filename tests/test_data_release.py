"""Lossless assembly of hourly values, native metadata and audit annotations."""
import unittest
import numpy as np
import pandas as pd
import pyarrow as pa
from data3001 import data_release


class LosslessDataRelease(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({'source_obs':np.array([9,10],np.int64),
                             've':np.array([np.nan,-0.5],np.float32),
                             'regime':np.array([-1,1],np.int8),
                             'time_UTC':pd.to_datetime(['2000-01-01','2000-01-02'],utc=True)})

    def test_preserves_prepared_columns_types_and_missingness(self):
        f=self.frame();t=data_release.assemble_track(f,{'id':np.int64(300234066216690),
                                                    'DrogueCenterDepth':np.float32(np.nan)})
        pd.testing.assert_frame_equal(t.select(f.columns).to_pandas(),f)
        self.assertEqual(t.schema.field('id').type,pa.int64())
        self.assertEqual(t.schema.field('DrogueCenterDepth').type,pa.float32())
        self.assertTrue(np.isnan(t['DrogueCenterDepth'].to_numpy()).all())

    def test_byte_metadata_is_not_silently_decoded_or_lost(self):
        raw=np.bytes_(b'\xffbad')
        t=data_release.assemble_track(self.frame(),{'sensor':raw,'country':np.bytes_(b'USA')})
        self.assertEqual(t['sensor'].to_pylist(),[bytes(raw)]*2)
        self.assertEqual(t['sensor_text'].to_pylist(),[None,None])
        self.assertEqual(t['country_text'].to_pylist(),['USA','USA'])

    def test_conflicting_metadata_cannot_overwrite_existing_column(self):
        with self.assertRaises(ValueError):
            data_release.assemble_track(self.frame(),{'regime':np.int8(0)})

    def test_annotation_cannot_overwrite_source_or_prepared_feature(self):
        with self.assertRaises(ValueError):
            data_release.assemble_track(self.frame(),{},annotations={'ve':[0.,0.]})

    def test_preserves_all_three_unknown_reasons(self):
        self.assertEqual(data_release.unknown_reasons(np.array([-1,1]),0,None).tolist(),
                         ['uncertain_from_start',None])
        self.assertEqual(data_release.unknown_reasons(np.array([-1,0]),100.,
                         {'decision':'hold_unknown'}).tolist(),['unresolved_boundary',None])
        self.assertEqual(data_release.unknown_reasons(np.array([1,-1]),100.,
                         {'decision':'attached_at_end'}).tolist(),[None,'beyond_attached_evidence'])

    def test_unexplained_unknown_is_not_silently_renamed(self):
        with self.assertRaises(ValueError):
            data_release.unknown_reasons(np.array([-1]),100.,None)


if __name__=='__main__':unittest.main()
