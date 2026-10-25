"""Tiny end-to-end local-model CV with independent score reconstruction."""
import unittest

import numpy as np
import pandas as pd
from shapely.geometry import box

from data3001.modelling.experiment import make_nested_folds
from data3001.modelling.neighbourhood import EndpointMapper
from data3001.modelling.neighbourhood_cv import (
    MODEL_NAMES, coefficient_cases, evaluate_local_nested, fit_local_bases,
    forecast, pair_counts,
)
from data3001.modelling.evaluate import score_distribution


def cell(lon, lat):
    return int(np.floor(lat + 90) * 360 + np.floor(lon + 180))


class LocalCVTests(unittest.TestCase):
    def fixture(self, ids=range(1, 41)):
        rows = []
        for sid in ids:
            for h in (7, 30):
                x = .2 + sid % 2
                y = .2 + (sid % 3) * .1
                endx = x + (2. if sid % 4 else 0.)
                rows.append([sid, h, cell(x, y), cell(endx, y), x, y, endx, y])
        return pd.DataFrame(rows, columns=["id", "horizon_days", "origin_cell_1",
                                          "destination_cell_1", "origin_lon", "origin_lat",
                                          "endpoint_lon", "endpoint_lat"])

    def fit(self, pairs, ids):
        return fit_local_bases(pairs, ids, {cell(.2, .2), cell(1.2, .2)},
                               EndpointMapper(box(-10, -10, 10, 10)),
                               fit_tag="test", integration={"exact_limit": 10000})

    def test_heldout_coordinates_and_outcomes_cannot_enter_fit(self):
        pairs = self.fixture(range(1, 11))
        a = self.fit(pairs, set(range(1, 10)))
        pairs.loc[pairs.id.eq(10), ["origin_lon", "origin_lat", "endpoint_lon", "endpoint_lat"]] = 99.
        pairs.loc[pairs.id.eq(10), "destination_cell_1"] = 999
        b = self.fit(pairs, set(range(1, 10)))
        for kind in ("B1", "B2", "Local-U", "Local-A"):
            self.assertEqual(a[kind], b[kind])
        self.assertNotIn(999, a["B1"][7])

    def test_alpha_zero_is_exact_B2_and_alpha_one_uses_local_base(self):
        model = self.fit(self.fixture(), set(range(1, 30)))
        origin = cell(.2, .2)
        for name in ("Local-U-Grid", "Local-A-Analytic"):
            p, u = forecast(model, name, 7, origin, 0.)
            self.assertEqual((p, u), (model["B2"][(7, origin)], 0.))
            p, u = forecast(model, name, 7, origin, 1.)
            self.assertEqual((p, u), model[name.rsplit("-", 1)[0]][(7, origin)])

    def test_polynomial_matches_direct_scores_for_each_family(self):
        pairs = self.fixture()
        model = self.fit(pairs, set(range(1, 30)))
        counts = pair_counts(pairs)
        for family in ("Global", "Local-U", "Local-A"):
            cases = coefficient_cases(counts, model, set(range(30, 41)), family)
            for r in cases.itertuples():
                for alpha in (0., .3, .73, 1.):
                    p, u = forecast(model, family+"-Grid", r.horizon_days, r.origin_cell_1, alpha)
                    direct = score_distribution(p, r.destination_cell_1, u)["brier_failure_penalized"]
                    self.assertAlmostEqual(r.A*alpha**2+r.B*alpha+r.C, direct)
        with self.assertRaises(ValueError):
            coefficient_cases(counts, model, {1}, "Local-U")

    def test_nested_comparison_preserves_cases_and_group_isolation(self):
        pairs = self.fixture()
        ids = sorted(pairs.id.unique().tolist())
        outer, inner = make_nested_folds(ids)
        result = evaluate_local_nested(pairs, outer, inner, {cell(.2, .2), cell(1.2, .2)},
                                        EndpointMapper(box(-10, -10, 10, 10)),
                                        integration={"exact_limit": 10000}, progress=lambda s: None)
        scores = result["scores"]
        self.assertEqual(set(scores.model), set(MODEL_NAMES))
        self.assertTrue(all(outer[r.id] == r.outer_fold for r in scores.itertuples()))
        self.assertEqual(len(result["selection"]), 5*2*3*2)
        self.assertTrue(result["numerical_audit"].converged.all())
        np.testing.assert_array_equal(scores.groupby(["horizon_days", "model"]).pair_count.sum(), 40)
        for r in scores.itertuples():
            model = result["models"][r.outer_fold]
            if r.model == "B0":
                p, u = {r.origin_cell_1: 1.}, 0.
            else:
                p, u = forecast(model, r.model, r.horizon_days, r.origin_cell_1, r.alpha_value)
            self.assertAlmostEqual(r.brier_failure_penalized,
                                   score_distribution(p, r.destination_cell_1, u)["brier_failure_penalized"])
        # Fixed-alpha curves are diagnostics, not the chosen outer-test optimum.
        self.assertEqual(set(result["fixed_alpha_scores"].alpha_value), {k/10 for k in range(11)})

    def test_missing_neighbours_preserve_unresolved_weight(self):
        pairs = self.fixture(range(1, 11))
        pairs = pairs.loc[pairs.origin_cell_1.eq(cell(.2, .2))]
        model = self.fit(pairs, set(range(1, 11)))
        p, u = forecast(model, "Local-U-Grid", 7, cell(.2, .2), .4)
        self.assertAlmostEqual(u, .4)
        self.assertAlmostEqual(sum(p.values()), .6)

    def test_serial_and_parallel_fits_are_identical(self):
        pairs = self.fixture()
        kwargs = {"fit_tag": "determinism", "integration": {"exact_limit": 0, "levels": (4, 16),
                                                          "tolerance": .0005}}
        args = (pairs, set(range(1, 30)), {cell(.2, .2), cell(1.2, .2)})
        a = fit_local_bases(*args, EndpointMapper(box(-10, -10, 10, 10)), workers=1, **kwargs)
        b = fit_local_bases(*args, EndpointMapper(box(-10, -10, 10, 10)), workers=4, **kwargs)
        for kind in ("B1", "B2", "Local-U", "Local-A", "support", "numerical_audit"):
            self.assertEqual(a[kind], b[kind])


if __name__ == "__main__":
    unittest.main()
