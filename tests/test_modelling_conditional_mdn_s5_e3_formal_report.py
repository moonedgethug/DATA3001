"""Synthetic-only checks for publication and saved-model prediction."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd
import torch

from data3001.modelling.continuous_models import conditional_mdn_s5_e3 as model
from data3001.modelling.continuous_models import conditional_mdn_s5_e3_training as training
from data3001.modelling.continuous_models import conditional_mdn_s5_e3_inference as inference
from data3001.modelling.continuous_models import conditional_mdn_s5_e3_formal_report as report


def synthetic_checkpoint(path, purpose="full_refit"):
    network = model.MDN(2, 20261121)
    standardizer = model.Standardizer(np.array([-75., 35.]), np.array([5., 4.]),
                                     np.array([1., 2.]), np.array([10., 12.]))
    identity = dict(checkpoint_version=training.CHECKPOINT_VERSION,
                    contract_sha256=model.CONTRACT_SHA256, k=2, role="C_outer",
                    base_seed=20261121, purpose=purpose)
    torch.save(dict(identity=identity, model_state=network.state_dict(), best_model_state=None,
                    standardizer=standardizer.state_dict(),
                    progress=dict(epoch=3, status="complete", history=[]),
                    tracker=dict(best_epoch=3, best_nll=2.)), path)


class FormalReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_checkpoint_prediction_and_sampling_need_only_lonlat(self):
        checkpoint = self.root / "checkpoint.pt"
        synthetic_checkpoint(checkpoint)
        predictor = inference.from_checkpoint(checkpoint)
        parameters = predictor.mixture([[-75., 35.], [-70., 30.]])
        self.assertEqual(parameters["weights"].shape, (2, 2))
        self.assertEqual(parameters["means_km"].shape, (2, 2, 2))
        np.testing.assert_allclose(parameters["weights"].sum(axis=1), 1.)
        self.assertTrue(np.all(np.linalg.eigvalsh(parameters["covariances_km2"]) > 0))
        first = predictor.sample([-75., 35.], count=200, seed=59)
        second = predictor.sample([-75., 35.], count=200, seed=59)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(first.shape, (1, 200, 2))
        self.assertTrue(np.isfinite(first).all())
        self.assertFalse(np.array_equal(first, predictor.sample([-75., 35.], count=200, seed=60)))

    def test_inference_rejects_early_stop_checkpoint(self):
        checkpoint = self.root / "checkpoint.pt"
        synthetic_checkpoint(checkpoint, purpose="early_stop")
        with self.assertRaisesRegex(ValueError, "full.refit"):
            inference.from_checkpoint(checkpoint)

    def test_inference_rejects_invalid_coordinates(self):
        for origins in ([181, 35], [-75, 91], [np.nan, 35], []):
            with self.subTest(origins=origins), self.assertRaises(ValueError):
                inference.validate_origins(origins)

    def test_selected_model_loads_without_any_target_or_training_data(self):
        from data3001.paths import file_sha256
        name = "conditional_mdn_s5_e3_synthetic"
        base = self.root / "results/runs" / name / "formal_v1"
        model_folder = base / "C_outer/K2"
        model_folder.mkdir(parents=True)
        checkpoint = model_folder / "checkpoint.pt"
        synthetic_checkpoint(checkpoint)
        choice_path = base / "selection.json"
        choice_path.write_text('{"status":"complete","selected_k":2}')
        manifest_path = model_folder / "manifest.json"
        manifest_path.write_text(json.dumps(dict(status="complete", role="C_outer", k=2,
            final_test_access=False, selected_epoch=3, selected_seed=20261121,
            full_refit={"checkpoint": {"path": "C_outer/K2/checkpoint.pt", "sha256": file_sha256(checkpoint)}})))
        audit = self.root / "provenance/runs" / name / "formal_v1/final_audit.json"
        audit.parent.mkdir(parents=True)
        audit.write_text(json.dumps(dict(status="complete", passed=True, final_test_access=False,
            evidence_sha256={str(p.relative_to(self.root)): file_sha256(p) for p in (choice_path, manifest_path)})))
        predictor = inference.load_selected_model(name, root=self.root)
        self.assertEqual(predictor.sample([-75, 35], 10, 23).shape, (1, 10, 2))
        self.assertFalse((self.root / "data").exists())

    def test_fixed_map_positions_use_only_prespecified_source_order(self):
        expected = np.floor(np.arange(12) * (33971 - 1) / 11).astype(int)
        np.testing.assert_array_equal(report.fixed_case_positions(), expected)
        self.assertEqual(len(set(expected)), 12)
        self.assertEqual((expected[0], expected[-1]), (0, 33970))

    def test_report_refuses_unpassed_audit_before_reading_results(self):
        run = dict(results=self.root / "results", provenance=self.root / "provenance")
        folder = run["provenance"] / "formal_v1"
        folder.mkdir(parents=True)
        (folder / "final_audit.json").write_text(json.dumps(dict(
            status="failed", passed=False, final_test_access=False)))
        with self.assertRaisesRegex(PermissionError, "audit"):
            report.require_completed_audit(run, self.root)

    def test_report_checks_audited_hashes(self):
        from data3001.paths import file_sha256
        run = dict(results=self.root / "results", provenance=self.root / "provenance")
        folder = run["provenance"] / "formal_v1"
        folder.mkdir(parents=True)
        evidence = self.root / "evidence.csv"
        evidence.write_text("original")
        (folder / "calculation_complete.json").write_text('{"status":"complete"}')
        (folder / "final_audit.json").write_text(json.dumps(dict(
            status="complete", passed=True, final_test_access=False,
            evidence_sha256={"evidence.csv": file_sha256(evidence)})))
        self.assertTrue(report.require_completed_audit(run, self.root)["passed"])
        evidence.write_text("changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            report.require_completed_audit(run, self.root)

    def test_report_refuses_uncovered_or_changed_display_input(self):
        from data3001.paths import file_sha256
        bundle = self.root / "saved_regions.json.gz"
        bundle.write_bytes(b"scored ellipse")
        audit = dict(evidence_sha256={})
        with self.assertRaisesRegex(ValueError, "not covered"):
            report.require_audited_file(bundle, audit, self.root)
        audit["evidence_sha256"][bundle.name] = file_sha256(bundle)
        self.assertEqual(report.require_audited_file(bundle, audit, self.root), bundle.resolve())
        bundle.write_bytes(b"changed ellipse")
        with self.assertRaisesRegex(ValueError, "changed"):
            report.require_audited_file(bundle, audit, self.root)

    def test_summary_validation_never_duplicates_selected_model_alias(self):
        frame = pd.DataFrame(1., index=report.MODELS, columns=report.METRICS)
        report.validate_summary(frame, selected_k=1)
        extra = pd.concat([frame, frame.loc[["MDN1"]].rename(index={"MDN1": "MDN-K*"})])
        with self.assertRaisesRegex(ValueError, "nine"):
            report.validate_summary(extra, selected_k=1)

    def test_display_histograms_retain_mass_on_a_common_grid(self):
        clouds = {"first": (np.array([[-76., 34.], [-74., 35.]]), np.array([.2, .8])),
                  "second": (np.array([[-77., 33.], [-73., 36.]]), np.array([.5, .5]))}
        edges, histograms = report.display_histograms(clouds, (-78, 32, -72, 37))
        self.assertEqual(len(edges), 2)
        for histogram in histograms.values():
            self.assertEqual(histogram.shape, (10, 12))
            self.assertAlmostEqual(histogram.sum(), 1.)

    def test_support_diagnostics_count_all_ids_beyond_8000_nearest_pairs(self):
        origins = np.vstack([np.tile([-75., 35.], (8001, 1)),
                             [-75.1, 35.1], [-74.9, 35.1], [-75., 34.9]])
        fit = pd.DataFrame(origins, columns=["lon", "lat"])
        fit["id"] = [1] * 8001 + [2, 3, 4]
        query = pd.DataFrame(dict(id=[101, 102], origin_source_obs=[1, 2], horizon_days=[7, 7],
                                  lon=[-75., -65.], lat=[35., 35.]))
        diagnostics, summary = report._support_diagnostics(fit, query)
        self.assertEqual(diagnostics.distinct_training_ids_within_100km.tolist(), [4, 0])
        self.assertEqual(diagnostics.nearest_training_start_km.iloc[0], 0.)
        self.assertEqual(diagnostics.outside_training_lonlat_convex_hull.tolist(), [False, True])
        self.assertFalse(summary["exclusion_or_fallback"])

    def test_display_histograms_reject_probability_lost_outside_view(self):
        cloud = {"model": (np.array([[-76., 34.], [-50., 35.]]), np.array([.2, .8]))}
        with self.assertRaisesRegex(ValueError, "dropped"):
            report.display_histograms(cloud, (-78, 32, -72, 37))


if __name__ == "__main__":
    unittest.main()
