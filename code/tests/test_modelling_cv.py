"""Independent, synthetic checks for grouped nested transport validation."""
import hashlib
import importlib
import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import numpy as np
import pandas as pd

from data3001.modelling import experiment
from data3001.modelling.blend import mix_forecasts
from data3001.modelling.evaluate import score_distribution
from data3001.modelling.run_blend_cv import ReadOnlyInputs
from pathlib import Path


class SetupRegressionTests(unittest.TestCase):
    def test_approved_grid_is_numeric(self):
        self.assertEqual(experiment.SETTINGS["grid_degrees"], 1)
        self.assertNotIsInstance(experiment.SETTINGS["grid_degrees"], str)

    def test_outer_hash_uses_approved_protocol_tag(self):
        ids = list(range(1001, 1401))
        actual = experiment.make_folds(ids)
        expected = {
            sid: int.from_bytes(hashlib.sha256(
                f"20261004:round1-cv:{sid}".encode("ascii")
            ).digest()[:8], "big") % 5 for sid in ids
        }
        self.assertEqual(actual, expected)

    def test_metadata_preview_does_not_read_trajectories(self):
        with patch("data3001.dataset.read_track", side_effect=AssertionError("Trajectory access")):
            with redirect_stdout(io.StringIO()) as out:
                experiment.main()
        self.assertIn("FOLD_SETUP_CHECKS_PASSED", out.getvalue())

    def test_run_guard_rejects_test_and_canonical_writes(self):
        root = Path("/synthetic/data3001")
        guard = ReadOnlyInputs(root, {"results": root / "results/runs/new"})
        for path, mode in ((root / "data/test/123.parquet", "r"),
                           (root / "data/train/123.parquet", "w"),
                           (root / "provenance/qualification/v7/restricted_test/123.parquet", "r")):
            with self.subTest(path=path), self.assertRaises(PermissionError):
                guard("open", (str(path), mode, 0))
        guard("open", (str(root / "data/train/123.parquet"), "r", 0))
        self.assertEqual(guard.read_ids, {123})
        guard("open", (str(root / "results/runs/new/scores.csv"), "w", 0))

    def test_guard_respects_external_configured_data_root(self):
        root = Path("/synthetic/data3001")
        data_root = Path("/synthetic/shared/drifters")
        guard = ReadOnlyInputs(root, {"results": root / "results/runs/new"}, data_root=data_root)
        guard("open", (str(data_root / "train/123.parquet"), "r", 0))
        self.assertEqual(guard.read_ids, {123})
        for path, mode in ((data_root / "test/123.parquet", "r"),
                           (data_root / "train/123.parquet", "w")):
            with self.subTest(path=path), self.assertRaises(PermissionError):
                guard("open", (str(path), mode, 0))


class NestedCVTests(unittest.TestCase):
    def api(self):
        name = "data3001.modelling.cv"
        self.assertIsNotNone(importlib.util.find_spec(name), "CV implementation is missing")
        return importlib.import_module(name)

    def fixture(self):
        return pd.DataFrame([
            [1, 7, 100, 101, 3], [1, 7, 100, 102, 1],
            [2, 7, 200, 103, 4], [3, 7, 100, 103, 2],
            [4, 7, 999, 104, 1],
        ], columns=["id", "horizon_days", "origin_cell_1", "destination_cell_1", "pair_count"])

    def test_fit_cannot_include_heldout_outcomes(self):
        api = self.api()
        model = api.fit_baselines(self.fixture(), {1, 2})
        self.assertNotIn(104, model["B1"][7])
        self.assertNotIn(103, model["B2"][(7, 100)])
        self.assertAlmostEqual(model["B1"][7][103], 0.5)

    def test_polynomial_matches_existing_direct_score(self):
        api = self.api()
        model = api.fit_baselines(self.fixture(), {1, 2})
        cases = api.coefficient_cases(self.fixture(), model, {3, 4})
        for row in cases.itertuples():
            q = model["B2"].get((7, row.origin_cell_1), {})
            u2 = 0.0 if q else 1.0
            for lam in (0.0, 0.1, 0.37, 1.0):
                p, u = mix_forecasts(q, model["B1"][7], lam, u2=u2)
                direct = score_distribution(p, row.destination_cell_1, unresolved=u)["brier_failure_penalized"]
                self.assertAlmostEqual(row.A * lam**2 + row.B * lam + row.C, direct)

    def test_fitting_ids_cannot_be_scored_as_heldout(self):
        api = self.api()
        model = api.fit_baselines(self.fixture(), {1, 2})
        with self.assertRaises(ValueError):
            api.coefficient_cases(self.fixture(), model, {1, 3})

    def test_region_includes_cutoff_ties_and_preserves_outside(self):
        api = self.api()
        region = api.probability_region({1: 0.7, 2: 0.1, 3: 0.1, -2: 0.1})
        self.assertEqual(region["states"], {1, 2, 3, -2})
        self.assertAlmostEqual(region["mass"], 1.0)
        self.assertEqual(region["cells"], 3)
        self.assertFalse(api.probability_region({1: 0.3}, 0.7)["available"])

    def test_missing_B2_is_unresolved_not_automatic_B1(self):
        api = self.api()
        model = api.fit_baselines(self.fixture(), {1, 2})
        lambdas = {"Grid": {7: 0.0}, "Analytic": {7: 1.0}}
        scores = api.score_groups(self.fixture(), model, {4}, lambdas, outer_fold=0)
        by_model = scores.set_index("model")
        self.assertEqual(by_model.loc["B2", "unresolved_mass"], 1.0)
        self.assertEqual(by_model.loc["Grid", "brier_failure_penalized"], 2.0)
        self.assertEqual(by_model.loc["Analytic", "unresolved_mass"], 0.0)
        self.assertAlmostEqual(by_model.loc["Analytic", "brier_failure_penalized"],
                               by_model.loc["B1", "brier_failure_penalized"])

    def test_fully_unresolved_forecast_has_no_top_cell_hit(self):
        api = self.api()
        counts = self.fixture()
        counts.loc[counts["id"].eq(4), "destination_cell_1"] = 101
        model = api.fit_baselines(counts, {1, 2})
        scores = api.score_groups(counts, model, {4},
                                  {"Grid": {7: 0.0}, "Analytic": {7: 1.0}}, outer_fold=0)
        self.assertFalse(scores.set_index("model").loc["Grid", "top_cell_hit"])

    def test_nested_cases_are_all_heldout_and_share_denominators(self):
        api = self.api()
        ids = list(range(1001, 1401))
        counts = pd.DataFrame([
            [sid, h, 100, 101 + sid % 2, 1] for sid in ids for h in (7, 30)
        ], columns=["id", "horizon_days", "origin_cell_1", "destination_cell_1", "pair_count"])
        outer, inner = experiment.make_nested_folds(ids)
        result = api.evaluate_nested(counts, outer, inner, progress=lambda *args: None)
        scores = result["scores"]
        self.assertEqual(set(scores["model"]), {"B0", "B1", "B2", "Grid", "Analytic"})
        self.assertEqual(len(result["lambda_selection"]), 20)
        self.assertTrue(all(outer[int(r.id)] == r.outer_fold for r in scores.itertuples()))
        np.testing.assert_array_equal(scores.groupby(["horizon_days", "model"])["pair_count"].sum(), 400)


if __name__ == "__main__":
    unittest.main()
