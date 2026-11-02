"""Independent fixtures for the approved standard B2 experiment."""
import importlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from data3001.modelling.baselines.empirical_b2 import (
    KEYS, bootstrap_scores, evaluate_b2, fit_b2, standard_brier, summarise,
)


def fixture():
    return pd.DataFrame([
        [1, 7, 10, 10, 1], [1, 7, 10, 20, 3],
        [2, 7, 10, 20, 100], [2, 7, 30, 20, 5],
        [2, 7, 10, 30, 1], [1, 30, 10, -2, 2],
        [2, 30, 10, -2, 1],
    ], columns=KEYS + ["pair_count"])


class EmpiricalB2Tests(unittest.TestCase):
    def model(self):
        return fit_b2(fixture(), [1], [10, 20, 30], [-2, 10, 20, 30])

    def test_counts_not_heldout_outcomes_determine_probabilities(self):
        model = self.model()
        row = model.transitions.query("horizon_days == 7")
        np.testing.assert_allclose(row.probability, [.25, .75], atol=0, rtol=0)
        modified = fixture()
        modified.loc[modified.id.eq(2), "pair_count"] *= 999
        other = fit_b2(modified, [1], [10, 20, 30], [-2, 10, 20, 30])
        pd.testing.assert_frame_equal(model.transitions, other.transitions)
        support = model.support.query("horizon_days == 7 and origin_cell_1 == 10").iloc[0]
        self.assertEqual(support.training_pair_count, 4)
        self.assertEqual(support.training_id_count, 1)

    def test_exact_brier_fixtures(self):
        self.assertEqual(standard_brier({10: .25, 20: .75}, 20), .125)
        self.assertEqual(standard_brier({10: 1.}, 10), 0.)
        self.assertEqual(standard_brier({10: 1.}, 20), 2.)
        self.assertEqual(standard_brier({-2: 1.}, -2), 0.)

    def test_unseen_destination_is_scored_and_unsupported_origin_is_not(self):
        scores = evaluate_b2(self.model(), fixture(), [2])
        missing = scores.loc[scores.origin_cell_1.eq(30)].iloc[0]
        self.assertTrue(np.isnan(missing.brier))
        self.assertEqual(missing.unresolved_mass, 1.)
        unseen = scores.loc[scores.destination_cell_1.eq(30)].iloc[0]
        self.assertEqual(unseen.status, "evaluable")
        self.assertEqual(unseen.true_probability, 0.)
        self.assertEqual(unseen.brier, 1.625)
        self.assertEqual(unseen.unresolved_mass, 0.)

    def test_summary_denominators_and_pair_weights(self):
        summary = summarise(evaluate_b2(self.model(), fixture(), [2])).set_index("horizon_days")
        self.assertEqual(summary.loc[7, "eligible_pairs"], 106)
        self.assertEqual(summary.loc[7, "evaluable_pairs"], 101)
        self.assertEqual(summary.loc[7, "unsupported_pairs"], 5)
        self.assertAlmostEqual(summary.loc[7, "brier"], (100*.125 + 1.625)/101)
        self.assertAlmostEqual(summary.loc[7, "zero_true_probability_fraction"], 1/101)
        self.assertEqual(summary.loc[30, "brier"], 0.)

    def test_invalid_probability_mass_is_rejected(self):
        for p in ({10: .9}, {}, {10: np.nan}, {10: -.1, 20: 1.1}, {10: np.inf}):
            with self.subTest(p=p), self.assertRaises(ValueError):
                standard_brier(p, 10)

    def test_leaked_ids_and_bad_counts_are_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_b2(self.model(), fixture(), [1, 2])
        variants = [pd.concat([fixture(), fixture().iloc[:1]], ignore_index=True)]
        for col, value in [("pair_count", 0), ("destination_cell_1", -1),
                           ("origin_cell_1", 999), ("horizon_days", 90)]:
            bad = fixture(); bad.loc[0, col] = value; variants.append(bad)
        bad = fixture().astype({"pair_count": float}); variants.append(bad)
        for counts in variants:
            with self.assertRaises(ValueError):
                fit_b2(counts, [1], [10, 20, 30], [-2, 10, 20, 30])

    def test_zero_support_and_horizons_are_explicit(self):
        model = fit_b2(fixture(), [3], [10, 20, 30], [-2, 10, 20, 30])
        self.assertTrue(model.transitions.empty)
        self.assertEqual(len(model.support), 6)
        self.assertTrue(model.support.unresolved_mass.eq(1).all())
        scores = evaluate_b2(model, fixture(), [2])
        self.assertTrue(scores.brier.isna().all())
        self.assertTrue(summarise(scores).availability.eq(0).all())

    def test_bootstrap_keeps_id_clusters_and_is_reproducible(self):
        scores = evaluate_b2(self.model(), fixture(), [2])
        a, intervals = bootstrap_scores(scores, [2, 3], replicates=200, seed=42)
        b, _ = bootstrap_scores(scores, [2, 3], replicates=200, seed=42)
        pd.testing.assert_frame_equal(a, b)
        h = a.loc[a.horizon_days.eq(7)]
        self.assertTrue(set(h.eligible_pairs).issubset({0, 106, 212}))
        expected = (100*.125 + 1.625)/101
        np.testing.assert_allclose(h.brier.dropna(), expected)
        self.assertGreater(int(intervals.undefined_replicates.sum()), 0)

    def test_import_does_not_load_other_model_families(self):
        script = """
import sys
import data3001.modelling.baselines.run_empirical_b2
for name in sys.modules:
    assert not any(x in name for x in ('markov_models', 'continuous_models', 'baselines.cv', 'common.experiment', 'torch')), name
"""
        subprocess.run([sys.executable, "-B", "-c", script], check=True, capture_output=True)

    def test_qualified_labels_retain_exit_and_exclude_missing_followup(self):
        from data3001.modelling.baselines.run_empirical_b2 import counts_from_labels
        labels = pd.DataFrame({"id": [1, 1, 1], "horizon_days": [7, 7, 7],
                               "origin_cell_1": [10, 10, 10], "destination_cell_1": [-2, 20, -1],
                               "origin_source_obs": [0, 1, 2], "reason_code": [0, 0, 1],
                               "target": ["stopped"]*3, "scenario": ["pooled"]*3,
                               "tolerance_hours": [0]*3, "outside": [True, False, False],
                               "first_exit_source_obs": [48, -1, -1]})
        counts = counts_from_labels(labels)
        self.assertEqual(counts.destination_cell_1.tolist(), [-2, 20])
        self.assertEqual(counts.pair_count.sum(), 2)
        for changed in (labels.assign(target="endpoint"), labels.assign(reason_code=999),
                        pd.concat([labels, labels.iloc[:1]], ignore_index=True)):
            with self.assertRaises(ValueError):
                counts_from_labels(changed)

    def test_runtime_blocks_historical_scores_and_test_reads(self):
        from data3001.modelling.baselines.run_empirical_b2 import ExperimentGuard
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = SimpleNamespace(root=root, data_root=root/"data")
            run = {"results": root/"results/runs/empirical_b2_fixture",
                   "provenance": root/"provenance/runs/empirical_b2_fixture"}
            allowed = root/"results/runs/prior/folds.csv"
            guard = ExperimentGuard(paths, run, [allowed])
            guard("open", (str(allowed), "r", 0))
            for p in [root/"data/test/1.parquet", root/"data/train/2.parquet",
                      root/"results/runs/prior/scores.parquet"]:
                with self.assertRaises(PermissionError):
                    guard("open", (str(p), "r", 0))
            with self.assertRaises(PermissionError):
                guard("open", (str(allowed), "w", 0))

    def test_config_does_not_allow_old_loss_or_model_features(self):
        import json
        from data3001.modelling.baselines.run_empirical_b2 import validate_config
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root/"configs/empirical_b2.json").read_text())
        validate_config(config)
        for key,value in [("primary_metric", "brier_failure_penalized"), ("smoothing", True),
                          ("horizons_days", [1, 7, 30]), ("final_test_access", True)]:
            bad = dict(config); bad[key] = value
            with self.assertRaises(ValueError):
                validate_config(bad)

    def test_source_receipt_includes_the_entrypoint_even_as_main(self):
        from data3001.modelling.baselines import run_empirical_b2 as runner
        from data3001.paths import project_paths
        key = "data3001.modelling.baselines.run_empirical_b2"
        # Model the module-name situation created by `python -m`.
        module = sys.modules.pop(key)
        try:
            hashes = runner.experiment_source_hashes(project_paths())
        finally:
            sys.modules[key] = module
        self.assertIn("src/data3001/modelling/baselines/run_empirical_b2.py", hashes)


if __name__ == "__main__":
    unittest.main()
