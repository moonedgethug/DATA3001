import importlib
import unittest
import numpy as np
import pandas as pd

try:
    m=importlib.import_module('data3001.sst_anomaly_review')
except ModuleNotFoundError:
    m=None


class SSTAnomalyReview(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(m,'Corroborated SST review is not implemented')

    def test_multiple_evidence_rules_preserve_ordinary_front_and_diurnal_differences(self):
        f=pd.DataFrame({'native_C':[44.,36.,36.,20.,27.,49.],
                        'background_C':[25.,24.,24.,26.,23.,28.],
                        'sst2':[1.,15.,15.,1.,1.,1.],
                        'flg_sst1':[5,5,5,5,5,5],
                        'flg_sst2':[5,5,3,5,5,5],
                        'recovery_tail':[False]*6,
                        'typedeath':[3]*6,'time':[0.]*6,'end_date':[100.]*6})
        self.assertEqual(m.review_reasons(f).tolist(),['corroborated_extreme_heat',
             'retain_for_review','corroborated_fit_inconsistency','retain_for_review',
             'retain_for_review','corroborated_native_above_45C'])

    def test_no_invention_for_missing_source_or_post_terminal_rows(self):
        f=pd.DataFrame({'native_C':[49.]*3,'background_C':[np.nan,28.,28.],
                        'sst2':[20.]*3,'flg_sst1':[5]*3,'flg_sst2':[3]*3,
                        'recovery_tail':[False,True,False],
                        'typedeath':[3,2,1],'time':[200.]*3,'end_date':[100.]*3})
        self.assertEqual(m.review_reasons(f).tolist(),['retain_for_review',
                          'excluded_recovery_tail','post_last_good_grounding_hold'])

    def test_patch_changes_only_approved_temperature_keys_and_preserves_known_others(self):
        base=pd.DataFrame({'id':[1,1,1],'source_obs':[10,11,12],
                           'sst_use_K':[300.,np.nan,290.],'sst_method':[0,3,0],
                           'sst_reason':['native','unknown','native'],'unrelated':[7,8,9]})
        patch=pd.DataFrame({'id':[1,1],'source_obs':[10,11],
                            'sst_use_K':[298.,299.],'sst_method':[11,14],
                            'sst_reason':['reviewed','reviewed']})
        out=m.apply_reviewed_temperature_patch(base,patch,{(1,10),(1,11)})
        self.assertEqual(out.sst_use_K.tolist(),[298.,299.,290.])
        self.assertEqual(out.unrelated.tolist(),[7,8,9])
        self.assertEqual(base.sst_use_K.iloc[0],300.)
        for bad,approved in [(patch,{(1,11)}),(patch.assign(unrelated=0),{(1,10),(1,11)}),
                              (pd.concat([patch,patch]),{(1,10),(1,11)})]:
            with self.assertRaises(ValueError):m.apply_reviewed_temperature_patch(base,bad,approved)


if __name__=='__main__':unittest.main()
