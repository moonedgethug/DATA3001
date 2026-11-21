"""Scientific fixtures independent of the neighbourhood implementation."""
import unittest

import numpy as np
import pandas as pd
import shapely as sh
from pyproj import Geod
from shapely.geometry import box

from data3001.modelling.neighbourhood import (
    EndpointMapper, aligned_distribution, balanced_coupling,
    blend_score_envelope, neighbour_cells, net_displacements,
    unaligned_distribution,
)
from data3001.modelling.blend import mix_forecasts
from data3001.modelling.evaluate import score_distribution


def cell(lon, lat):
    return int(np.floor(lat + 90) * 360 + np.floor((lon + 180) % 360))


class NeighbourhoodTests(unittest.TestCase):
    def donors(self):
        return pd.DataFrame({
            "origin_lon": [1.2, 1.2], "origin_lat": [0.2, 0.2],
            "endpoint_lon": [1.2, 3.2], "endpoint_lat": [0.2, 0.2],
            "destination_cell_1": [cell(1.2, 0.2), cell(3.2, 0.2)],
        })

    def test_eight_neighbours_exclude_self_and_wrap_longitude(self):
        c = cell(-75.5, 34.5)
        self.assertEqual(set(neighbour_cells(c)),
                         {c + dy * 360 + dx for dy in (-1, 0, 1)
                          for dx in (-1, 0, 1) if (dx, dy) != (0, 0)})
        self.assertIn(cell(179.5, 0.5), neighbour_cells(cell(-179.5, 0.5)))
        self.assertEqual(len(neighbour_cells(cell(0.5, 89.5))), 5)
        with self.assertRaises(ValueError):
            neighbour_cells(-1)

    def test_numeric_workers_own_distinct_native_geometries(self):
        mapper = EndpointMapper(box(-5, -5, 5, 5), box(1, 1, 2, 2))
        a, b = mapper.worker_copy(), mapper.worker_copy()
        self.assertIsNot(a.domain, b.domain)
        self.assertIsNot(a.land, b.land)
        self.assertIsNot(a.domain, mapper.domain)
        self.assertEqual(a.domain.wkb, mapper.domain.wkb)
        self.assertEqual(a.land.wkb, mapper.land.wkb)
        np.testing.assert_array_equal(a([0., 1.5, 8.], [0., 1.5, 0.]),
                                      b([0., 1.5, 8.], [0., 1.5, 0.]))

    def test_exact_land_cell_index_matches_direct_predicates_at_boundaries(self):
        land = sh.union_all([box(-2, -2, -.1, 3), box(1.2, -.3, 1.8, .3)])
        mapper = EndpointMapper(box(-3, -3, 3, 3), land)
        self.assertIsNotNone(mapper._land_cell_class)
        rng = np.random.default_rng(42)
        x = np.r_[rng.uniform(-4, 4, 10000), -3., 3., -.1, 1.2, 1.8, 2.]
        y = np.r_[rng.uniform(-4, 4, 10000), 0., 0., 0., -.3, .3, 0.]
        x = (x+180) % 360-180  # frozen longitude convention, including roundoff
        expected = np.full(len(x), -2)
        inside = sh.intersects_xy(mapper.domain, x, y)
        landward = inside & sh.intersects_xy(land, x, y)
        water = inside & ~landward
        expected[landward] = -1
        expected[water] = [cell(a, b) for a, b in zip(x[water], y[water])]
        np.testing.assert_array_equal(mapper(x, y), expected)

    def test_land_accelerator_uses_actual_closed_box_at_nextafter_boundaries(self):
        land = box(-76, 35, -74, 36)
        mapper = EndpointMapper(box(-81, 20, -8, 55), land)
        x = np.array([-75.5]*6 + [np.nextafter(-76., -np.inf), -76., np.nextafter(-76., np.inf)])
        y = np.array([np.nextafter(35., -np.inf), 35., np.nextafter(35., np.inf),
                      np.nextafter(36., -np.inf), 36., np.nextafter(36., np.inf)] + [35.5]*3)
        x = (x+180) % 360-180
        result = mapper(x, y)
        np.testing.assert_array_equal(result == -1, sh.intersects_xy(land, x, y))
        self.assertNotEqual(result[0], -1)

    def test_unaligned_uses_pair_counts_not_equal_cell_weights(self):
        d = self.donors().iloc[[0, 0, 0, 1]].reset_index(drop=True)
        p, u = unaligned_distribution(d)
        self.assertEqual(p, {cell(1.2, 0.2): .75, cell(3.2, 0.2): .25})
        self.assertEqual(u, 0.)
        self.assertEqual(unaligned_distribution(d.iloc[:0]), ({}, 1.))

    def test_balanced_coupling_preserves_every_equal_marginal(self):
        for n, m in ((2, 3), (5, 2), (7, 11), (1, 4), (4, 4)):
            di, ai, w = balanced_coupling(n, m, np.random.default_rng(12))
            np.testing.assert_allclose(np.bincount(di, weights=w, minlength=n), 1/n)
            np.testing.assert_allclose(np.bincount(ai, weights=w, minlength=m), 1/m)
            self.assertTrue((w > 0).all())
            self.assertLessEqual(len(w), n + m - 1)
        with self.assertRaises(ValueError):
            balanced_coupling(0, 3, np.random.default_rng(12))

    def test_geodesic_inverse_forward_round_trip(self):
        d = self.donors()
        az, distance = net_displacements(d)
        g = Geod(ellps="WGS84")
        lon, lat, _ = g.fwd(d.origin_lon.to_numpy(), d.origin_lat.to_numpy(), az, distance)
        np.testing.assert_allclose(lon, d.endpoint_lon, atol=1e-12)
        np.testing.assert_allclose(lat, d.endpoint_lat, atol=1e-12)

    def test_alignment_preserves_empirical_anchor_prior_not_cell_centre(self):
        d = self.donors().iloc[[0]]  # exactly zero displacement
        anchors = np.array([[.1, .1], [.1, .1], [.9, .9]])
        p, u, audit = aligned_distribution(d, anchors, EndpointMapper(box(-10, -10, 10, 10)),
                                           exact_limit=100)
        self.assertEqual(p, {cell(.1, .1): 1.})
        self.assertEqual(u, 0.)
        self.assertEqual(audit["method"], "exact")
        # A finer synthetic mapper distinguishes actual anchor positions.
        def fine(lon, lat):
            return np.where(np.asarray(lon) < .5, 10, 20)
        p, u, _ = aligned_distribution(d, anchors, fine, exact_limit=100)
        self.assertAlmostEqual(p[10], 2/3)
        self.assertAlmostEqual(p[20], 1/3)

    def test_alignment_does_not_require_donor_inside_D(self):
        d = self.donors().iloc[[1]].copy()
        d["destination_cell_1"] = -2
        mapper = EndpointMapper(box(-1, -1, 2.9, 1))
        p, u, _ = aligned_distribution(d, np.array([[.2, .2]]), mapper, exact_limit=100)
        self.assertNotIn(-2, p)
        self.assertEqual(u, 0.)
        self.assertAlmostEqual(sum(p.values()), 1.)

    def test_synthetic_land_and_outside_mass_are_never_renormalized(self):
        d = self.donors()
        mapper = EndpointMapper(box(-1, -1, 2, 1), land=box(.0, .0, .4, .4))
        p, u, _ = aligned_distribution(d, np.array([[.2, .2]]), mapper, exact_limit=100)
        self.assertEqual(p, {-2: .5})
        self.assertEqual(u, .5)
        self.assertEqual(sum(p.values()) + u, 1.)

    def test_empty_donors_or_anchors_remain_unresolved(self):
        mapper = EndpointMapper(box(-10, -10, 10, 10))
        for d, a in ((self.donors().iloc[:0], np.array([[.2, .2]])),
                     (self.donors(), np.empty((0, 2)))):
            p, u, audit = aligned_distribution(d, a, mapper)
            self.assertEqual((p, u), ({}, 1.))
            self.assertEqual(audit["method"], "unsupported")

    def test_balanced_integrator_is_deterministic_and_matches_exact_fixture(self):
        d = self.donors().iloc[[0, 0, 1, 1, 1]].reset_index(drop=True)
        anchors = np.array([[.1, .1], [.9, .9], [.2, .2]])
        mapper = EndpointMapper(box(-10, -10, 10, 10))
        exact = aligned_distribution(d, anchors, mapper, exact_limit=100)[0]
        kw = dict(exact_limit=0, levels=(16, 64), seed=99, tolerance=0.)
        one = aligned_distribution(d, anchors, mapper, **kw)
        two = aligned_distribution(d, anchors, mapper, **kw)
        self.assertEqual(one, two)
        for key in set(exact) | set(one[0]):
            self.assertAlmostEqual(exact.get(key, 0.), one[0].get(key, 0.), delta=.05)
        self.assertAlmostEqual(sum(one[0].values()) + one[1], 1.)

    def test_score_envelope_covers_all_truths_and_all_alpha_values(self):
        base, p, q = {1: .7, 2: .3}, {1: .3, 3: .5}, {1: .4, 2: .3}
        bound = blend_score_envelope(base, 0., p, .2, q, .3)
        for alpha in np.linspace(0, 1, 201):
            pa, ua = mix_forecasts(base, p, alpha, u1=.2)
            pb, ub = mix_forecasts(base, q, alpha, u1=.3)
            for truth in (1, 2, 3, 999):
                delta = abs(score_distribution(pa, truth, ua)["brier_failure_penalized"]
                            - score_distribution(pb, truth, ub)["brier_failure_penalized"])
                self.assertLessEqual(delta, bound + 1e-12)
        self.assertEqual(blend_score_envelope(base, 0., p, .2, p, .2), 0.)

    def test_mapper_uses_actual_point_and_handles_invalid_coordinates(self):
        mapper = EndpointMapper(box(0, 0, 1, 1), land=box(.2, .2, .3, .3))
        actual = mapper(np.array([1., 1.01, .25, np.nan]), np.array([.5, .5, .25, .5]))
        np.testing.assert_array_equal(actual, [cell(1., .5), -2, -1, -1])


if __name__ == "__main__":
    unittest.main()
