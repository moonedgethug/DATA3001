"""Same-node identities for the opt-in MDN numerical implementation.

Only synthetic distributions are used. The frozen numerical implementation is
the independent oracle for streams, reductions, and region tie behaviour.
"""
import importlib
import unittest

import numpy as np

from data3001.modelling.baselines import position_error_s4_e8 as region_math
from data3001.modelling.continuous_models import conditional_mdn_s5_e3_numerics as legacy


def optimized():
    try:
        return importlib.import_module(
            'data3001.modelling.continuous_models.conditional_mdn_s5_e3_optimized'
        )
    except ModuleNotFoundError as exc:
        if exc.name.endswith('conditional_mdn_s5_e3_optimized'):
            raise AssertionError('Opt-in equivalent MDN numerics are not implemented') from exc
        raise


def packets():
    return [
        dict(origin=[-75., 35.], weights=np.array([1.]),
             means=np.array([[0., 0.]]), cholesky=np.array([[[10., 0.], [2., 6.]]])),
        dict(origin=[179.9, 79.8], weights=np.array([1e-12, .4, .6-1e-12]),
             means=np.array([[8000., 1000.], [-50., -20.], [50., 30.]]),
             cholesky=np.array([[[.04, 0.], [.01, .05]],
                                [[10., 0.], [3., 7.]], [[4., 0.], [-2., 12.]]])),
    ]


class SyntheticGeography:
    """An observable deterministic classification independent of region fitting."""
    def __init__(self):
        self.masks = []

    def masses(self, points, weights):
        land = points[:, 0] < 0
        outside = points[:, 1] > 79.8
        self.masks.append((land.copy(), outside.copy()))
        return dict(land_mass=float(weights[land].sum()),
                    outside_D_mass=float(weights[outside].sum()))


class EquivalentNumericsTests(unittest.TestCase):
    def test_cache_reuses_exact_nodes_and_normals_without_legacy_global_cache(self):
        m = optimized()
        key = (10, 4, 7)
        expected = legacy.uniforms(128, 6, 'ES', 2, key, 'C_T0')
        expected_z = legacy.normals(expected[:, 1:3])
        before = legacy.uniforms.cache_info()
        with m.QueryCache(key, 'ES') as cache:
            actual = cache.uniforms(128, 6, 'ES', 2, key, 'C_T0')
            normal = cache.normals(128, 6, 'ES', 2, key, 'C_T0', offset=1)
            np.testing.assert_array_equal(actual, expected)
            np.testing.assert_array_equal(normal, expected_z)
            self.assertIs(actual, cache.uniforms(128, 6, 'ES', 2, key, 'C_T0'))
            self.assertIs(normal, cache.normals(128, 6, 'ES', 2, key, 'C_T0', offset=1))
            self.assertFalse(actual.flags.writeable)
            self.assertFalse(normal.flags.writeable)
            self.assertGreater(cache.cache_bytes, 0)
            self.assertEqual(legacy.uniforms.cache_info(), before)
        self.assertEqual(cache.cache_bytes, 0)
        with self.assertRaises(RuntimeError):
            cache.uniforms(128, 6, 'ES', 2, key, 'C_T0')

    def test_cache_keys_separate_role_count_dimension_replicate_and_normal_offset(self):
        m = optimized()
        key = (1, 2, 7)
        with m.QueryCache(key, 'ES') as cache:
            args = [(128, 6, 'ES', 0, key, 'C_T0'),
                    (128, 6, 'ES', 0, key, 'C_T1'),
                    (256, 6, 'ES', 0, key, 'C_T0'),
                    (128, 3, 'ES', 0, key, 'C_T0'),
                    (128, 6, 'ES', 1, key, 'C_T0')]
            for item in args:
                np.testing.assert_array_equal(cache.uniforms(*item), legacy.uniforms(*item))
            first = cache.normals(*args[0], offset=1)
            second = cache.normals(*args[0], offset=4)
            np.testing.assert_array_equal(second, legacy.normals(legacy.uniforms(*args[0])[:, 4:6]))
            self.assertFalse(np.array_equal(first, second))
            with self.assertRaises(ValueError):
                cache.uniforms(128, 6, 'ES', 0, ('different',), 'C_T0')
            with self.assertRaises(ValueError):
                cache.uniforms(128, 6, 'audit', 0, key, 'C_T0')

    def test_cache_scope_separates_main_audit_and_query_and_enforces_memory_limit(self):
        m = optimized()
        key = (1, 2, 7)
        with m.QueryCache(key, 'ES', max_bytes=4096) as main:
            u = main.uniforms(128, 3, 'ES', 0, key, 'C_T0')
            for rep in range(4):
                large = main.uniforms(256, 6, 'ES', rep, key, 'C_T0')
                self.assertFalse(large.flags.writeable)
                self.assertLessEqual(main.cache_bytes, 4096)
            self.assertLessEqual(main.peak_cache_bytes, 4096)
        with m.QueryCache(key, 'audit_ES') as audit:
            other = audit.uniforms(128, 3, 'audit', 0, key, 'C_T0')
            self.assertFalse(np.array_equal(u, other))
            np.testing.assert_array_equal(other, legacy.uniforms(128, 3, 'audit', 0, key, 'C_T0'))
        with m.QueryCache(key, 'ES') as fresh:
            regenerated = fresh.uniforms(128, 3, 'ES', 0, key, 'C_T0')
            self.assertIsNot(u, regenerated)
            np.testing.assert_array_equal(u, regenerated)
        with self.assertRaises(ValueError):
            m.QueryCache(key, 'ES', max_bytes=128*1024**2+1)

    def test_prepared_packet_copies_validates_and_preserves_tiny_component(self):
        m = optimized()
        packet = packets()[1]
        original = {name: np.array(value, copy=True) for name, value in packet.items()}
        prepared = m.prepare_packet(packet)
        nodes = np.array([[5e-13, 0., 0.], [.2, 0., 0.], [.8, 0., 0.]])
        expected = legacy.draw_vectors(packet, nodes)
        packet['weights'][:] = 0
        packet['means'][:] = 999
        packet['cholesky'][:] = 0
        packet['origin'][:] = [0., 0.]
        np.testing.assert_array_equal(m.draw_vectors(prepared, nodes), expected)
        for name in ('weights', 'means', 'cholesky', 'cdf', 'origin'):
            value = getattr(prepared, name)
            self.assertFalse(value.flags.writeable)
            with self.assertRaises(ValueError):
                value.setflags(write=True)
        self.assertIs(prepared, m.prepare_packet(prepared))
        invalid = dict(original, weights=[.2, .3, .1])
        with self.assertRaises(ValueError):
            m.prepare_packet(invalid)
        invalid = dict(original, cholesky=np.zeros((3, 2, 2)))
        with self.assertRaises(ValueError):
            m.prepare_packet(invalid)

    def test_same_node_energy_is_bitwise_equal_for_k1_multimodal_and_audit(self):
        m = optimized()
        key = (11, 4, 7)
        for audit in (False, True):
            scope = 'audit_ES' if audit else 'ES'
            with m.QueryCache(key, scope) as cache:
                for packet in packets():
                    target = [packet['origin'][0]-.1, packet['origin'][1]-.1]
                    expected = legacy.score_es(packet, target, 65536, key, 'C_T0', audit=audit)
                    actual = m.score_es(m.prepare_packet(packet), target, 65536, key, 'C_T0',
                                        audit=audit, cache=cache)
                    self.assertEqual(actual, expected)
        self.assertEqual(m.score_es(packets()[0], [-75., 35.], 65536, key, 'C_T0'),
                         legacy.score_es(packets()[0], [-75., 35.], 65536, key, 'C_T0'))

    def test_uniform_region_kth_preserves_ties_rank_and_attained_mass(self):
        m = optimized()
        fixtures = [
            np.array([[0., 0.]]*10),
            np.array([[-1., 0.], [1., 0.]]*5),
            np.array([[-1., -1.], [-1., 1.], [1., -1.], [1., 1.]]*3+[[0., 0.]]),
            np.array([[x, x*x % 7] for x in range(23)], dtype=float),
        ]
        for points in fixtures:
            expected = region_math.fit_region(points)
            actual = m.fit_region_uniform(points)
            self.assertEqual(actual, expected)
            targets = np.vstack([points, [[0., 0.], [100., 100.]]])
            np.testing.assert_array_equal(region_math.inside_region(targets, actual),
                                          region_math.inside_region(targets, expected))
        self.assertAlmostEqual(m.fit_region_uniform(fixtures[2])['attained_mass'], 1.)

    def test_same_node_regions_hits_and_geography_masks_are_bitwise_equal(self):
        m = optimized()
        key = (12, 4, 7)
        for audit in (False, True):
            scope = 'audit_region' if audit else 'region'
            with m.QueryCache(key, scope) as cache:
                for packet in packets():
                    old_geo, new_geo = SyntheticGeography(), SyntheticGeography()
                    expected = legacy.build_region(packet, 65536, key, 'C_T0', old_geo, audit)
                    actual = m.build_region(m.prepare_packet(packet), 65536, key, 'C_T0',
                                            new_geo, audit, cache=cache)
                    self.assertEqual(actual, expected)
                    for old_mask, new_mask in zip(old_geo.masks[0], new_geo.masks[0]):
                        np.testing.assert_array_equal(new_mask, old_mask)
                    target = packet['origin']
                    self.assertEqual(legacy.region_metrics(actual, target),
                                     legacy.region_metrics(expected, target))

    def test_wrong_scope_and_unregistered_levels_are_rejected(self):
        m = optimized()
        key = (1, 2, 7)
        with m.QueryCache(key, 'region') as cache:
            with self.assertRaises(ValueError):
                m.score_es(packets()[0], [-75., 35.], 65536, key, 'C_T0', cache=cache)
        with m.QueryCache(key, 'audit_region') as cache:
            with self.assertRaises(ValueError):
                m.build_region(packets()[0], 65536, key, 'C_T0', cache=cache)
        with self.assertRaises(ValueError):
            m.score_es(packets()[0], [-75., 35.], 1024, key, 'C_T0')
        with self.assertRaises(ValueError):
            m.build_region(packets()[0], 1024, key, 'C_T0')
