import unittest
import numpy as np
import torch
from unittest.mock import patch
from shapely.geometry import box
from scipy.special import logsumexp
from scipy.stats import multivariate_normal
from data3001.modelling.continuous import (
    to_state, to_lonlat, drift, residual, advance, hour_pairs,
    TransitionMixture, mixture_nll, mixture_draw, particle_brier,
)
from data3001.modelling.markov_position_scores import ensemble_scores
from data3001.modelling.neighbourhood import EndpointMapper
from data3001.modelling.run_continuous import rollout, fit_scaler, index_for


class ContinuousTests(unittest.TestCase):
    def test_chart_and_euler_residual_roundtrip(self):
        x = to_state(np.array([-80., -20.]), np.array([25., 52.]), [.4, 1.], [.2, -.1])
        np.testing.assert_allclose(to_lonlat(x), [[-80, 25], [-20, 52]])
        y = advance(x, np.array([[20., -30., .01, -.02], [-10., 60., -.03, .04]]))
        np.testing.assert_allclose(advance(x, residual(x, y)), y)
        np.testing.assert_allclose(drift(torch.tensor(x)).numpy(), drift(x))
        self.assertGreater(drift(x)[1, 0], x[1, 2])

    def test_hour_pairs_retains_exit_rejects_gap_and_invalid_geometry(self):
        t = np.array([0, 3600, 7200, 14400, 18000])
        p = np.ones(5, bool); inside = np.array([1, 1, 0, 1, 1], bool)
        mapping = np.array([1, 1, 1, 1, 0], bool)
        np.testing.assert_array_equal(hour_pairs(t, p, mapping, inside, p), [0, 1])
        mapping[2]=False
        np.testing.assert_array_equal(hour_pairs(t, p, mapping, inside, p), [0])

    def test_full_covariance_nll_matches_scipy_and_gradients(self):
        torch.manual_seed(5)
        model = TransitionMixture(3).double()
        x, y = torch.randn(7, 4, dtype=torch.float64), torch.randn(7, 4, dtype=torch.float64)
        lp, mu, ch = model(x)
        for dimensions in (2, 4):
            expected = []
            for i in range(7):
                values = []
                for j in range(3):
                    l = ch[i, j].detach().numpy(); cov = l @ l.T
                    values.append(lp[i, j].item() + multivariate_normal.logpdf(
                        y[i, :dimensions], mu[i, j, :dimensions].detach(), cov[:dimensions, :dimensions]))
                expected.append(-logsumexp(values))
            np.testing.assert_allclose(mixture_nll((lp, mu, ch), y, dimensions).detach(), expected, atol=1e-9)
        mixture_nll((lp, mu, ch), y).mean().backward()
        self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters()))
        covariance = ch @ ch.transpose(-1, -2)
        self.assertTrue((torch.linalg.eigvalsh(covariance) >= model.floor**2 - 1e-10).all())

    def test_draw_and_brier_semantics(self):
        torch.manual_seed(8)
        model = TransitionMixture(2)
        out = model(torch.zeros(100, 4))
        self.assertEqual(tuple(mixture_draw(out).shape), (100, 4))
        a = np.array([[1, 1, 2, -3], [-2, -2, -2, -2], [4, 5, 6, 7]])
        y = np.array([1, -2, 8])
        np.testing.assert_allclose(particle_brier(a, y), ensemble_scores(a, y).S_integration)
        self.assertEqual(particle_brier(a, y)[1], 0)
        self.assertEqual(particle_brier(a, y)[2], 1)

    def test_exit_absorbs_and_later_observations_are_not_inputs(self):
        model=TransitionMixture(1)
        state=to_state(np.array([-.01]),np.array([30.]),np.array([2.]),np.array([0.]))
        mapper=EndpointMapper(box(-1,29,0,31))
        with patch('data3001.modelling.run_continuous.mixture_draw',side_effect=lambda o:torch.zeros(len(o[0]),4)):
            result=rollout(model,np.zeros(8,'f4'),np.ones(8,'f4'),state,mapper,4,1,(1,3))
        np.testing.assert_array_equal(result[1],np.full((1,4),-2))
        np.testing.assert_array_equal(result[3],result[1])

    def test_land_is_unresolved_not_exit_or_grounding(self):
        model=TransitionMixture(1)
        state=to_state(np.array([-.01]),np.array([30.]),np.array([2.]),np.array([0.]))
        mapper=EndpointMapper(box(-1,29,1,31),box(0,29,1,31))
        with patch('data3001.modelling.run_continuous.mixture_draw',side_effect=lambda o:torch.zeros(len(o[0]),4)):
            result=rollout(model,np.zeros(8,'f4'),np.ones(8,'f4'),state,mapper,4,1,(1,3))
        np.testing.assert_array_equal(result[3],np.full((1,4),-3))

    def test_scaling_is_fitting_only(self):
        values=np.arange(32,dtype='float32').reshape(4,8)
        mean,sd=fit_scaler(values,np.array([0,1]))
        np.testing.assert_allclose(mean,values[:2].mean(0))
        np.testing.assert_allclose(sd,values[:2].std(0))


if __name__ == '__main__':
    unittest.main()
