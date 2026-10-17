"""Official fill restoration must not weaken any other regime or path rule."""
import unittest
import numpy as np
import pandas as pd
from data3001.preprocessing import prep_core as core


class OfficialDrogueCorrection(unittest.TestCase):
    def track(self, hours=(0, 24), inside=(True, True)):
        t=np.asarray(hours,dtype=float)*3600
        return dict(time=t,position_ok=np.ones(len(t),bool),
                    mapping_ok=np.ones(len(t),bool),inside_D=np.asarray(inside),
                    regime=np.ones(len(t),np.int8),loss=np.nan,
                    loss_status_source='official_fill_attached',
                    official_attached_through_epoch=float(t[-1]))

    def test_proven_attached_nan_endpoint_is_eligible_but_gap_is_not_repaired(self):
        endpoint,stopped=core.labels(self.track(),np.array([0]),1,0,'drogued')
        self.assertEqual(endpoint['reason'][0],0)
        self.assertEqual(stopped['reason'][0],6)

    def test_undrogued_is_a_known_scenario_mismatch(self):
        endpoint,_=core.labels(self.track(),np.array([0]),1,0,'undrogued')
        self.assertEqual(endpoint['reason'][0],5)

    def test_proof_does_not_extend_beyond_its_observed_time(self):
        a=self.track();a['official_attached_through_epoch']=23*3600
        endpoint,_=core.labels(a,np.array([0]),1,0,'drogued')
        self.assertEqual(endpoint['reason'][0],4)

    def test_unproven_nan_and_zero_remain_unknown(self):
        for loss in [np.nan,0]:
            a=self.track();a.pop('loss_status_source');a['loss']=loss
            self.assertEqual(core.labels(a,np.array([0]),1,0,'drogued')[0]['reason'][0],4)

    def test_official_fill_proof_cannot_override_zero_or_positive_loss(self):
        for loss in [0,12*3600]:
            a=self.track();a['loss']=loss;a['regime']=np.array([1,0],np.int8)
            self.assertNotEqual(core.labels(a,np.array([0]),1,0,'drogued')[0]['reason'][0],0)

    def test_absorbing_exit_requires_only_proven_interval(self):
        a=self.track(tuple(range(7)),(True,)*6+(False,))
        stopped=core.labels(a,np.array([0]),30,0,'drogued')[1]
        self.assertEqual(stopped['reason'][0],0)
        self.assertTrue(stopped['outside'][0])

    def test_source_restoration_changes_only_regime_and_requires_matching_ID(self):
        from data3001.preprocessing.drogue_correction import restore_attached
        frame=pd.DataFrame({'regime':np.array([-1,-1],np.int8),
                            'drogue_status':np.array([1,1],np.int8),
                            'source_obs':[100,101],'lon':[-75.,np.nan]})
        evidence={'original_id':'10','original_rows':2,'raw_loss_date':[-999999.],
                  'loss_attrs':{'_FillValue':'-999999.0',
                                'long_name':'Date of drogue loss (FillValue=drogue still attached)'}}
        result=restore_attached(frame,evidence,10)
        pd.testing.assert_frame_equal(frame.drop(columns='regime'),result.drop(columns='regime'))
        self.assertEqual(frame.regime.tolist(),[-1,-1])
        self.assertEqual(result.regime.tolist(),[1,1])
        with self.assertRaises(ValueError):restore_attached(frame,evidence,11)

    def test_test_correction_access_stays_locked(self):
        from data3001.preprocessing.drogue_correction import official_attached_evidence
        with self.assertRaises(PermissionError):
            official_attached_evidence(10,'test')


if __name__=='__main__':
    unittest.main()
