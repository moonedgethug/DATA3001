"""Scientific fixtures for the approved S5 E1, without project observations."""
import importlib
import importlib.util
import unittest

import numpy as np

MODULE = 'data3001.modelling.continuous_models.conditional_gaussian_s5_e1'


class GaussianDefinitionTests(unittest.TestCase):
    def model(self):
        self.assertIsNotNone(importlib.util.find_spec(MODULE), 'S5 E1 module not implemented')
        return importlib.import_module(MODULE)

    def test_chart_roundtrip_preserves_original_endpoints(self):
        m = self.model()
        origin = np.array([-77., 33.])
        points = np.array([origin, [-72., 37.], [-80., 29.], [179., -10.]])
        np.testing.assert_allclose(m.to_geographic(origin, m.to_vectors(origin, points)), points, atol=1e-10)

    def test_chart_east_north_axis_and_zero(self):
        m = self.model()
        v = np.array([[0., 0.], [10., 0.], [0., 10.]])
        p = m.to_geographic([-75., 35.], v)
        np.testing.assert_array_equal(p[0], [-75., 35.])
        self.assertGreater(p[1, 0], -75.)
        self.assertGreater(p[2, 1], 35.)
        np.testing.assert_allclose(m.to_vectors([-75., 35.], p), v, atol=1e-9)

    def test_mle_n_divisor_and_off_diagonal(self):
        m = self.model()
        x = np.array([[0., 0.], [3., 1.], [2., 5.], [8., 6.]])
        fit = m.fit_vectors(x)
        np.testing.assert_allclose(fit['mean'], x.mean(axis=0))
        np.testing.assert_allclose(fit['covariance'], np.cov(x, rowvar=False, ddof=0))
        self.assertNotEqual(fit['covariance'][0][1], 0.)
        l = np.asarray(fit['cholesky'])
        np.testing.assert_allclose(l @ l.T, fit['covariance'])

    def test_rotation_equivariance(self):
        m = self.model()
        x = np.array([[0., 0.], [3., 1.], [2., 5.], [8., 6.]])
        r = np.array([[0., -1.], [1., 0.]])
        a, b = m.fit_vectors(x), m.fit_vectors(x @ r.T)
        np.testing.assert_allclose(b['covariance'], r @ np.array(a['covariance']) @ r.T)

    def test_no_support_and_too_few_stop(self):
        m = self.model()
        for n in [0, 1, 2]:
            with self.assertRaises(m.SupportError): m.fit_vectors(np.zeros((n, 2)))

    def test_support_failure_preserves_diagnostic_values(self):
        m = self.model()
        for values in (np.zeros((2, 2)), np.array([[0., 0.], [1., 2.], [2., 4.]])):
            try:
                m.fit_vectors(values)
            except m.SupportError as error:
                self.assertTrue(hasattr(error, 'diagnostics'))
                self.assertEqual(error.diagnostics['pairs'], len(values))
                if len(values) >= 3:
                    self.assertIn('eigenvalues', error.diagnostics)
                    self.assertIn('covariance', error.diagnostics)
            else:
                self.fail('Invalid covariance did not stop')

    def test_resource_projection_requires_component_and_io_measurements(self):
        m = importlib.import_module(MODULE+'_pilot')
        self.assertTrue(hasattr(m, 'resource_projection'))
        components = np.array([[1., 0.], [0., 1.]])
        result = m.resource_projection(components, cold_seconds=3., cases=10)
        self.assertAlmostEqual(result['case_p95_seconds'], 1.)
        self.assertAlmostEqual(result['component_p95_sum_seconds'], 1.9)
        self.assertAlmostEqual(result['formal_seconds'], (3+10*1.9)*1.1)

    def test_identical_collinear_ill_conditioned_stop(self):
        m = self.model()
        for x in [np.zeros((8, 2)), np.array([[0., 0.], [1., 2.], [2., 4.]]),
                  np.array([[0., 0.], [1., 1e-8], [2., -1e-8], [3., 0.]])]:
            with self.assertRaises(m.SupportError): m.fit_vectors(x)

    def test_nonfinite_inputs_stop(self):
        m = self.model()
        with self.assertRaises(ValueError): m.fit_vectors(np.array([[0., 0.], [1., 2.], [np.nan, 4.]]))

    def test_normal_draw_streams_are_reproducible_distinct(self):
        m = self.model()
        a = m.sobol_normals(1024, 4, ('fixture', 0))
        np.testing.assert_array_equal(a, m.sobol_normals(1024, 4, ('fixture', 0)))
        self.assertFalse(np.array_equal(a, m.sobol_normals(1024, 4, ('fixture', 1))))
        self.assertLess(abs(a.mean()), .01)
        self.assertLess(abs(a.var()-1), .03)

    def test_gaussian_energy_isotropic_planar_fixture(self):
        m = self.model()
        values = []
        for i in range(8):
            z = 3*m.sobol_normals(8192, 4, ('planar', i))
            values.append(m.energy_integrands(z[:, :2], z[:, 2:], np.zeros(2)).mean())
        expected = 3*np.sqrt(np.pi)*(1/np.sqrt(2)-.5)
        self.assertAlmostEqual(np.mean(values), expected, delta=.0015)

    def test_discrete_energy_includes_equal_index_pairs(self):
        m = self.model()
        x = np.array([[0., 0.], [2., 0.]])
        a, b = np.repeat(x, 2, axis=0), np.tile(x, (2, 1))
        self.assertAlmostEqual(m.energy_integrands(a, b, np.array([1., 0.])).mean(), .5)

    def test_geographic_tail_not_clipped_or_reassigned(self):
        m = self.model()
        points = m.to_geographic([-75., 35.], np.array([[3000., 0.], [0., 30000.], [-5000., 100.]]))
        self.assertEqual(points.shape, (3, 2))
        self.assertTrue(np.isfinite(points).all())
        self.assertTrue((points[:, 0] < -81.).any())

    def test_mass_diagnostic_uses_real_atom_allowance(self):
        m = self.model()
        a = m.mass_diagnostic(9500, 10000, boundary_atom=.1)
        b = m.mass_diagnostic(9500, 10000, boundary_atom=0.)
        self.assertEqual(a['discrepancy'], 0.)
        self.assertAlmostEqual(b['discrepancy'], .05)
        self.assertGreater(a['radius'], 0.)

    def test_es_requires_eight_independent_replicate_means(self):
        m = self.model()
        means = np.arange(8, dtype=float)
        result = m.replicate_summary(means)
        self.assertAlmostEqual(result['variance'], means.var(ddof=1)/8)
        with self.assertRaises(ValueError): m.replicate_summary(means[:2])

    def test_covariance_fit_does_not_modify_donors(self):
        m = self.model()
        origin = np.array([-75., 35.])
        points = np.array([[-74., 36.], [-73., 36.], [-74., 37.], [-72., 38.]])
        before = points.copy()
        packet = m.fit(origin, points)
        np.testing.assert_array_equal(points, before)
        self.assertLess(packet['roundtrip_max_km'], 1e-6)


class IntegrationTests(unittest.TestCase):
    def numerical(self):
        name = MODULE + '_numerics'
        self.assertIsNotNone(importlib.util.find_spec(name), 'Numerical adapter not implemented')
        return importlib.import_module(name)

    def test_equal_id_weights_do_not_depend_on_pair_counts(self):
        m = self.numerical()
        np.testing.assert_allclose(m.id_weights(np.array([1, 1, 1, 2])), [1/6, 1/6, 1/6, 1/2])

    def test_no_usable_ci_equals_exact_point_regions(self):
        m = self.numerical()
        from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
        core = importlib.import_module(MODULE)
        p = np.array([[-74., 36.], [-73., 36.], [-74., 37.], [-72., 38.]])
        pool = opt.Pool(p, np.zeros_like(p), np.zeros(4, bool), opt.xyz(p), opt.xy(p), np.zeros(4, bool), np.zeros(4, bool))
        g = core.fit([-75., 35.], p)
        regions = m.build_regions(pool, g, 16384, ('synthetic',), None)
        self.assertEqual(regions['ExactPoint']['region'], regions['EndpointCI']['region'])
        self.assertEqual(regions['EndpointCI']['mass_check']['radius'], 0.)
        self.assertEqual(regions['LocalGaussian']['mass_check']['boundary_atom'], 0.)

    def test_real_fallback_atom_only_at_boundary(self):
        m = self.numerical()
        from data3001.modelling.baselines import position_error_s4_e8 as old
        xy = np.array([[0., 0.], [1., 0.], [0., 1.], [2., 2.]])
        region = old.fit_region(xy)
        b = m.boundary_atom(xy, np.ones(4, bool), region)
        self.assertAlmostEqual(b, .25)
        self.assertEqual(m.boundary_atom(xy, np.zeros(4, bool), region), 0.)

    def test_numerical_projection_uses_outer_squared_weights(self):
        m = self.numerical()
        self.assertTrue(hasattr(m, 'es_projection'), 'ES gate not implemented')
        r = m.es_projection(np.array([1., 4.]), .002, 100.)
        self.assertAlmostEqual(r['projected_three_se_km'], 3*np.sqrt(4*.002))
        self.assertFalse(r['passed'])

    def test_region_disagreement_cannot_cancel(self):
        m = self.numerical()
        self.assertTrue(hasattr(m, 'region_gate'), 'Region gate not implemented')
        rows = dict(mass_diagnostic=np.array([.001, .001]), mass_radius=np.array([.001, .001]),
                    hit_disagreement=np.array([1., 1.]), area90_km2=np.ones(2),
                    area_replica_km2=np.ones(2), land_variance=np.zeros(2), outside_variance=np.zeros(2))
        r = m.region_gate(rows, np.array([.5, .5]))
        self.assertFalse(r['passed'])
        self.assertEqual(r['hit_disagreement'], 1.)


if __name__ == '__main__': unittest.main()
