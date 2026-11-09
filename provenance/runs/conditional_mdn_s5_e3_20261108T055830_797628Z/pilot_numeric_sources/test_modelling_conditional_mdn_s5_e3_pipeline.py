"""MDN execution gates; no historical target values are used by these tests."""
import importlib
import unittest
import numpy as np
import pandas as pd
import tempfile
from pathlib import Path
import json
from unittest.mock import patch


def module():
    try:return importlib.import_module('data3001.modelling.continuous_models.conditional_mdn_s5_e3_pipeline')
    except ModuleNotFoundError:raise AssertionError('MDN phase gates are not implemented')


class PipelineTests(unittest.TestCase):
    def test_fully_cached_level_reuses_recorded_duration_without_workers(self):
        from data3001.modelling.continuous_models import conditional_mdn_s5_e3_pilot as p
        with tempfile.TemporaryDirectory() as d:
            run={'results':Path(d)/'results','provenance':Path(d)/'provenance'}
            for folder in run.values():folder.mkdir()
            (run['provenance']/'worker_parity.json').write_text('{}')
            folder=run['results']/'pilot_numerics/N65536_M65536';folder.mkdir(parents=True)
            (folder/'C_T0_0.json').write_text('[{"K":1}]')
            expected={'level_wall_seconds':3.,'cold_to_first_result_seconds':1.25}
            (folder/'timing.json').write_text(json.dumps(expected))
            with patch.object(p.cf,'ProcessPoolExecutor',side_effect=AssertionError('cached level started workers')):
                rows,timing=p.measure_level('test',run,[{'role':'C_T0','position':0}],65536,65536)
            self.assertEqual(timing,expected)
    def test_endpoint_access_requires_preexisting_exact_roster_freeze(self):
        from data3001.modelling.continuous_models import conditional_mdn_s5_e3_inputs as inp
        self.assertTrue(hasattr(inp,'authorize_endpoint_keys'),'Explicit endpoint-key gate is missing')
        keys=pd.DataFrame({'id':[1],'origin_source_obs':[10],'horizon_days':[7]})
        with tempfile.TemporaryDirectory() as d:
            run={'provenance':Path(d)}
            with self.assertRaises(PermissionError):inp.authorize_endpoint_keys(run,'C_T0',keys,'pilot')
    def test_pilot_roster_is_fixed_complete_and_sorted(self):
        m=module()
        ix=m.pilot_indices(41761)
        np.testing.assert_array_equal(ix,np.floor(np.arange(64)*(41761-1)/63).astype(int))
        self.assertEqual(len(set(ix)),64)

    def test_id_weights_do_not_reward_repeated_observations(self):
        m=module();w=m.id_weights(np.array([1,1,1,2]))
        np.testing.assert_allclose(w,[1/6,1/6,1/6,1/2])

    def test_packet_preserves_global_network_parameters_and_floor(self):
        m=module()
        params={'pi':np.array([[.4,.6]]),'mu':np.array([[[1,2],[3,4]]],float),
                'cov':np.array([[[[2.,.5],[.5,3]],[[4.,1.],[1.,5.]]]])}
        p=m.packet_at(params,0,np.array([-75.,35.]),target_scale=np.array([10.,10.]))
        np.testing.assert_allclose(np.asarray(p['cholesky'])@np.asarray(p['cholesky']).transpose(0,2,1),params['cov'][0])
        np.testing.assert_array_equal(p['weights'],params['pi'][0])
        bad={**params,'cov':np.array([np.eye(2)*1e-8]*2)[None]}
        with self.assertRaises(ValueError):m.packet_at(bad,0,[-75,35],target_scale=np.array([10,10]))

    def test_paired_replicates_not_independent_component_variances(self):
        m=module();baseline=np.array([[1.,2,3,4,5,6,7,8],[3.,4,5,6,7,8,9,10]])
        candidate=baseline+5
        self.assertAlmostEqual(m.aggregate_difference(candidate,baseline,np.array([.5,.5]))['three_se_km'],0)

    def test_failed_numeric_or_cost_gate_never_promotes_full_run(self):
        m=module()
        self.assertFalse(m.preflight_pass({'basic_numerical_pass':False,'resource_pass':True}))
        self.assertFalse(m.preflight_pass({'basic_numerical_pass':True,'resource_pass':False}))
        self.assertTrue(m.preflight_pass({'basic_numerical_pass':True,'resource_pass':True}))

