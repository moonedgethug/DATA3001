"""E2 scientific fixtures: synthetic inputs only, never a resource pilot."""
import importlib
import importlib.util
import unittest
import tempfile
from pathlib import Path
import numpy as np

PREFIX = 'data3001.modelling.continuous_models.local_gmm_s5_e2'


class FitTests(unittest.TestCase):
    def model(self):
        self.assertIsNotNone(importlib.util.find_spec(PREFIX), 'E2 fitting is not implemented')
        return importlib.import_module(PREFIX)

    @staticmethod
    def fixture():
        rng = np.random.default_rng(39)
        x = np.r_[rng.normal([-5, 0], [.5, .8], (300, 2)),
                  rng.normal([5, 2], [.6, .9], (300, 2))]
        return x, np.tile(np.arange(12), 50)

    def test_k1_is_existing_mle_not_regularized(self):
        m = self.model(); x, ids = self.fixture()
        r = m.fit_local(x, ids, 1, ('synthetic', 1))
        np.testing.assert_allclose(r['means'][0], x.mean(0), atol=1e-12)
        np.testing.assert_allclose(r['covariances'][0], np.cov(x, rowvar=False, ddof=0), atol=1e-12)
        self.assertEqual(r['weights'], [1.]); self.assertFalse(r['fallback'])

    def test_two_supported_groups_full_covariance_and_restarts(self):
        m = self.model(); x, ids = self.fixture()
        r = m.fit_local(x, ids, 2, ('synthetic', 2))
        self.assertEqual(r['K_effective'], 2)
        self.assertEqual(len(r['restarts']), 5)
        np.testing.assert_allclose(sorted(np.asarray(r['means'])[:, 0]), [-5, 5], atol=.15)
        self.assertAlmostEqual(sum(r['weights']), 1.)
        for diag in r['component_diagnostics']:
            self.assertGreaterEqual(diag['effective_ids'], 3)
        self.assertEqual(r, m.fit_local(x, ids, 2, ('synthetic', 2)))

    def test_one_drifter_is_fallback_without_dropping_endpoints(self):
        m = self.model(); x, _ = self.fixture()
        r = m.fit_local(x, np.zeros(len(x), int), 2, ('synthetic', 3))
        self.assertTrue(r['fallback']); self.assertEqual(r['K_effective'], 1)
        self.assertEqual(r['pairs'], len(x))
        np.testing.assert_allclose(r['means'][0], x.mean(0), atol=1e-12)

    def test_collinear_base_stops_instead_of_fallback(self):
        m = self.model()
        with self.assertRaises(ValueError):
            m.fit_local(np.column_stack([np.arange(10), np.arange(10)]), np.arange(10), 2, ('bad',))

    def test_constrained_m_step_and_responsibility_votes(self):
        m = self.model(); z = np.array([[-1., 0], [1., 0], [0., -1], [0., 1]])
        resp = np.array([[1., 0], [1., 0], [0., 1], [0., 1]])
        w, a, b = m.maximize(z, resp)
        np.testing.assert_array_equal(w, [.5, .5]); np.testing.assert_allclose(a, 0.)
        np.testing.assert_allclose(np.linalg.eigvalsh(b), [[.01, 1], [.01, 1]])
        ll, r = m.expectation(z, w, a, b)
        self.assertTrue(np.isfinite(ll)); np.testing.assert_allclose(r.sum(1), 1.)

    def test_component_id_effective_count_uses_soft_mass(self):
        m = self.model(); r = np.ones((120, 1)); ids = np.repeat([1, 2, 3], 40)
        d, reasons = m.component_support(r, ids, np.eye(2)[None])
        self.assertEqual(reasons, [])
        self.assertAlmostEqual(d[0]['effective_ids'], 3.)
        self.assertAlmostEqual(d[0]['largest_id_share'], 1/3)

    def test_all_records_equal_likelihood_contribution(self):
        m = self.model(); x, ids = self.fixture()
        a = m.fit_local(x, ids, 1, ('replication',))
        b = m.fit_local(np.repeat(x, 2, axis=0), np.repeat(ids, 2), 1, ('replication',))
        np.testing.assert_allclose(a['covariances'], b['covariances'], atol=1e-12)

    def test_seed_keys_are_deterministic_distinct(self):
        m = self.model()
        np.testing.assert_array_equal(m.generator(('x',)).random(5), m.generator(('x',)).random(5))
        self.assertFalse(np.array_equal(m.generator(('x',)).random(5),m.generator(('y',)).random(5)))


class NativeParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory()
        cls.lib=Path(cls.directory.name)/'em.dylib'
        native=importlib.import_module(MODULE_NATIVE)
        native.compile_kernel(cls.lib)

    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def test_fused_kernel_preserves_all_restarts_and_prediction(self):
        m=importlib.import_module(MODULE_FIT);x,ids=FitTests.fixture()
        for K in [2,3]:
            a=m.fit_local(x,ids,K,('native_parity',K))
            b=m.fit_local(x,ids,K,('native_parity',K),{'native_path':str(self.lib)})
            self.assertEqual(b.get('backend'),'native')
            self.assertEqual(a['fallback'],b['fallback']);self.assertEqual(a['K_effective'],b['K_effective'])
            for field in ['weights','means','covariances']:np.testing.assert_allclose(a[field],b[field],rtol=1e-8,atol=1e-8)
            for ra,rb in zip(a['restarts'],b['restarts']):
                self.assertEqual(ra['iterations'],rb['iterations']);self.assertEqual(ra['status'],rb['status'])
                np.testing.assert_allclose(ra['trace'],rb['trace'],rtol=0,atol=1e-10)


MODULE_FIT=PREFIX
MODULE_NATIVE=PREFIX+'_native'


if __name__ == '__main__': unittest.main()
