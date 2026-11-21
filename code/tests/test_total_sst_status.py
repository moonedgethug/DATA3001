"""Total SST availability labels preserve numeric missingness and source data."""
import importlib
import unittest
import numpy as np
import pandas as pd

try:
    m=importlib.import_module('data3001.sst_total_status')
except ModuleNotFoundError:
    m=None


class TotalSSTStatus(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(m,'Total SST missing-reason handling is absent')

    def test_post_last_good_on_grounding_ID_is_not_labelled_as_exact_beaching_time(self):
        f=pd.DataFrame({'time':[100.,200.,300.,300.], 'end_date':[200.]*4,
                        'typedeath':[1,1,1,3],'sst_use_K':[np.nan]*4,
                        'sst_reason':['original_unknown']*4,'unrelated':[1,2,3,4]})
        original=f.copy(deep=True);out=m.annotate_total_sst_missingness(f)
        self.assertEqual(out.sst_reason.tolist(),['original_unknown','original_unknown',
            'unavailable_after_last_good_on_grounding_ID','original_unknown'])
        self.assertTrue(out.sst_use_K.isna().all())
        self.assertTrue(pd.api.types.is_numeric_dtype(out.sst_use_K))
        pd.testing.assert_frame_equal(f,original)
        pd.testing.assert_frame_equal(out.drop(columns='sst_reason'),f.drop(columns='sst_reason'))

    def test_known_temperature_and_unknown_terminal_time_are_not_reclassified(self):
        f=pd.DataFrame({'time':[300.,300.],'end_date':[200.,np.nan],
                        'typedeath':[1,1],'sst_use_K':[300.,np.nan],
                        'sst_reason':['native_accepted','unresolved']})
        pd.testing.assert_frame_equal(m.annotate_total_sst_missingness(f),f)

    def test_independent_grounding_context_does_not_require_missing_temperature(self):
        f=pd.DataFrame({'time':[199.,200.,201.],'end_date':[200.]*3,'typedeath':[1]*3})
        self.assertEqual(m.post_last_good_grounding_mask(f).tolist(),[False,False,True])


if __name__=='__main__':unittest.main()
