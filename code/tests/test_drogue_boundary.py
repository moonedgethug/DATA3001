"""Official nominal times and end markers are different scientific cases."""
import unittest
import numpy as np
import pandas as pd
from data3001.preprocessing import prep_core as core


class BoundaryEvidence(unittest.TestCase):
    def test_minute_refinement_corrects_the_whole_affected_day_only(self):
        from data3001.preprocessing.drogue_boundary import official_regimes
        t=np.array([0,3600,7200,10800.])
        r=official_regimes(t,{'decision':'nominal_loss','official_loss_epoch':5400.})
        self.assertEqual(r.tolist(),[1,1,0,0])

    def test_end_marker_does_not_create_a_loss_or_extrapolate_attachment(self):
        from data3001.preprocessing.drogue_boundary import official_regimes
        r=official_regimes(np.array([0,3600,7200.]),
                           {'decision':'attached_at_end','attached_through_epoch':5400.})
        self.assertEqual(r.tolist(),[1,1,-1])

    def test_unresolved_metadata_cannot_supply_confirmed_labels(self):
        from data3001.preprocessing.drogue_boundary import official_regimes
        with self.assertRaises(ValueError):
            official_regimes(np.array([0.]),{'decision':'hold_unknown'})

    def track(self,decision,loss=3600.):
        t=np.arange(49,dtype=float)*3600
        return dict(time=t,position_ok=np.ones(49,bool),mapping_ok=np.ones(49,bool),
                    inside_D=np.ones(49,bool),regime=np.ones(49,np.int8),loss=loss,
                    loss_status_source='official_boundary_refinement',
                    official_regime_decision=decision,official_loss_epoch=36*3600.,
                    official_attached_through_epoch=48*3600.)

    def test_interval_uses_verified_minute_time_instead_of_coarse_midnight(self):
        a=self.track('nominal_loss');a['regime'][36:]=0
        # Native midnight would exclude this valid 24-hour drogued interval.
        self.assertEqual(core.labels(a,np.array([0]),1,0,'drogued')[0]['reason'][0],0)
        self.assertEqual(core.labels(a,np.array([24]),1,0,'drogued')[0]['reason'][0],5)
        self.assertEqual(core.labels(a,np.array([0]),1,0,'undrogued')[0]['reason'][0],5)

    def test_end_marker_interval_is_bounded_and_not_a_recorded_loss(self):
        a=self.track('attached_at_end')
        self.assertEqual(core.labels(a,np.array([24]),1,0,'drogued')[0]['reason'][0],0)
        a['official_attached_through_epoch']=47*3600.
        self.assertEqual(core.labels(a,np.array([24]),1,0,'drogued')[0]['reason'][0],4)

    def test_boundary_test_access_stays_explicit(self):
        from data3001.preprocessing.drogue_boundary import boundary_evidence
        with self.assertRaises(PermissionError):boundary_evidence(1,'test')

    def test_overlay_changes_only_regime_and_checks_source_keys(self):
        from data3001.preprocessing.drogue_boundary import apply_overlay
        f=pd.DataFrame({'source_obs':[10,11],'regime':np.array([-1,0],np.int8),'lat':[30.,31.]})
        o=pd.DataFrame({'source_obs':[10,11],'old_regime':[-1,0],'regime':[1,1]})
        n=apply_overlay(f,o)
        pd.testing.assert_frame_equal(n.drop(columns='regime'),f.drop(columns='regime'))
        self.assertEqual(n.regime.tolist(),[1,1])
        self.assertEqual(f.regime.tolist(),[-1,0])
        with self.assertRaises(ValueError):apply_overlay(f,o.assign(source_obs=[10,12]))
        with self.assertRaises(ValueError):apply_overlay(f,o.assign(old_regime=[1,0]))


if __name__=='__main__':unittest.main()
