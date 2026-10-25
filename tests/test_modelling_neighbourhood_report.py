import unittest

import numpy as np
import pandas as pd

from data3001.modelling.neighbourhood_report import (
    audit_score_rows, independent_quadratic, paired_intervals, region_summary,
    reconstruct_aligned_basis,
)
from shapely.geometry import box


class NeighbourReportTests(unittest.TestCase):
    def scored_fixture(self):
        model = {"training_ids": [1], "B1": {}, "B2": {"7:10": {"10": .8, "20": .2}},
                 "Local-U": {"7:10": {"probabilities": {"10": .8, "20": .2}, "unresolved": 0.}},
                 "Local-A": {}}
        row = {"id": 2, "outer_fold": 0, "model": "Local-U-Grid", "horizon_days": 7,
               "origin_cell_1": 10, "destination_cell_1": 20, "pair_count": 3,
               "alpha_value": 1., "true_probability": .2, "unresolved_mass": 0.,
               "brier_failure_penalized": 1.28, "brier": 1.28, "complete": True,
               "log_loss": -np.log(.2), "log_loss_lower": -np.log(.2),
               "log_loss_upper": -np.log(.2), "outside_probability": 0., "top_cell_hit": False}
        for level in (50, 80, 90, 95):
            row.update({f"region{level}_available": True, f"region{level}_hit": level > 80,
                        f"region{level}_mass": .8 if level <= 80 else 1.,
                        f"region{level}_cells": 1 if level <= 80 else 2})
        return pd.DataFrame([row]), {0: model}

    def test_independent_polynomial_has_known_closed_form(self):
        q, r = {1: 1.}, {2: 1.}
        np.testing.assert_allclose(independent_quadratic(q, 0., r, 0., 2), [2., -4., 2.])
        np.testing.assert_allclose(independent_quadratic({}, 1., r, 0., 2), [2., -4., 2.])

    def test_independent_score_audit_catches_tampered_score(self):
        scores, models = self.scored_fixture()
        self.assertEqual(audit_score_rows(scores, models)["score_rows_verified"], 1)
        scores.loc[0, "brier_failure_penalized"] = 1.27
        with self.assertRaises(ValueError):
            audit_score_rows(scores, models)

    def test_independent_audit_rejects_tampered_local_diagnostics(self):
        scores, models = self.scored_fixture()
        for field, wrong in (("region90_mass", .9), ("region90_cells", 1),
                             ("log_loss", 0.), ("complete", False),
                             ("region50_hit", True), ("top_cell_hit", True),
                             ("outside_probability", .1)):
            with self.subTest(field=field):
                changed = scores.copy()
                changed.loc[0, field] = wrong
                with self.assertRaises(ValueError):
                    audit_score_rows(changed, models)

    def test_independent_aligned_reconstruction_includes_land_and_outside(self):
        donors = pd.DataFrame({"origin_lon": [0., 0.], "origin_lat": [0., 0.],
                               "endpoint_lon": [1., 20.], "endpoint_lat": [0., 0.]})
        anchors = np.array([[0., 0.]])
        audit = {"method": "exact", "seed": 1, "couplings": 0}
        p, u = reconstruct_aligned_basis(donors, anchors, box(-5, -5, 5, 5),
                                         box(.5, -.5, 1.5, .5), audit)
        self.assertEqual(p, {-2: .5})
        self.assertEqual(u, .5)
        audit = {"method": "balanced", "seed": 1, "couplings": 8}
        q, v = reconstruct_aligned_basis(donors, anchors, box(-5, -5, 5, 5),
                                         box(.5, -.5, 1.5, .5), audit)
        self.assertEqual((p, u), (q, v))

    def test_paired_ID_interval_preserves_constant_difference(self):
        rows = []
        for sid in range(1, 21):
            for model, loss in (("B2", 1.), ("Local-U-Grid", .9)):
                rows.append({"id": sid, "outer_fold": sid % 5, "horizon_days": 7,
                             "model": model, "pair_count": sid,
                             "brier_failure_penalized": loss})
        result = paired_intervals(pd.DataFrame(rows), comparisons=[("Local-U-Grid", "B2")], replicates=50)
        np.testing.assert_allclose(result.iloc[0][["delta_brier", "lower", "upper"]].astype(float), -.1)

    def test_region_unavailability_is_not_removed_from_hit_denominator(self):
        rows = []
        for available, hit in ((True, True), (False, False)):
            row = {"horizon_days": 7, "model": "X", "pair_count": 1}
            for level in (50, 80, 90, 95):
                row.update({f"region{level}_available": available, f"region{level}_hit": hit,
                            f"region{level}_mass": .95 if available else np.nan,
                            f"region{level}_cells": 3 if available else 0})
            rows.append(row)
        result = region_summary(pd.DataFrame(rows))
        self.assertTrue(result.hit_pct.eq(50.).all())
        self.assertTrue(result.available_pct.eq(50.).all())
        self.assertTrue(result.mean_cells_when_available.eq(3.).all())


if __name__ == "__main__":
    unittest.main()
