"""Formal fit orchestration tests; fixtures contain no historical endpoints."""

from contextlib import ExitStack
import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd


MODULE = "data3001.modelling.continuous_models.conditional_mdn_s5_e3_formal_training"


def module():
    assert importlib.util.find_spec(MODULE), "Formal MDN fit orchestration is not implemented"
    return importlib.import_module(MODULE)


class Fixture:
    """Replace expensive training and historical loaders, retaining real gates/I/O."""

    def __init__(self, m, root):
        self.m = m
        self.run = {kind: Path(root) / kind for kind in ("results", "provenance")}
        for folder in self.run.values():
            folder.mkdir()
        self.cfg = {"contract_sha256": m.training.CONTRACT_SHA256,
                    "candidates": [1, 2, 4, 8, 16, 32], "training_threads": 1,
                    "initialization_seeds": list(m.training.BASE_SEEDS)}
        self.guard = SimpleNamespace(outer_read=False, denied=[])
        fit = pd.DataFrame({"id": np.repeat(np.arange(1, 11), 2),
                            "origin_source_obs": np.arange(20), "horizon_days": 7,
                            "lon": np.linspace(-76, -74, 20),
                            "lat": np.linspace(32, 37, 20)})
        query = pd.DataFrame({"id": [21, 22, 22], "origin_source_obs": [50, 51, 52],
                              "horizon_days": 7, "lon": [-75.1, -74.9, -74.8],
                              "lat": [34.1, 34.2, 34.3]})
        self.roles = {role: {"fit": fit.copy(), "query": query.copy(), "targets": None}
                      for role in ("C_T0", "C_T1", "C_outer")}
        self.calls = []
        self.endpoint_calls = []
        self.pause_k = None
        self.interrupt_k = None
        self.bad_parameters = False

    def endpoints(self, cfg, run, role, keys, kind):
        self.m.inp.authorize_endpoint_keys(run, role, keys, kind)
        self.endpoint_calls.append((role, kind))
        return keys[["lon", "lat"]].to_numpy() + [0.3, 0.2]

    def fit(self, x, v, ids, k, role, outdir, *, identity, resume):
        self.calls.append((role, k, identity, resume, len(x)))
        if k == self.interrupt_k:
            raise InterruptedError("Synthetic interruption between candidates")
        outdir = Path(outdir)
        scaler = self.m.training.Standardizer.fit(x, v)
        def result(seed, purpose):
            folder = outdir / (f"seed_{seed}" if purpose == "early_stop" else "full_refit")
            folder.mkdir(parents=True, exist_ok=True)
            checkpoint = folder / "checkpoint.pt"
            checkpoint.write_bytes(f"{role}|{k}|{seed}|{purpose}".encode())
            history = [dict(epoch=i, training_nll=2 / i,
                            stop_nll=1.2 / i if purpose == "early_stop" else None,
                            pairs_seen=len(x), batch_sizes=[len(x)], clipped_steps=i - 1,
                            gradient_clip_rate=float(i - 1), seconds=0.1) for i in (1, 2)]
            def parameters(origins):
                pi = np.full((len(origins), k), 1 / k)
                if self.bad_parameters:
                    pi[0, 0] = np.nan
                return {"pi": pi, "mu": np.zeros((len(origins), k, 2)),
                        "cov": np.broadcast_to(np.diag(scaler.y_std ** 2),
                                               (len(origins), k, 2, 2)).copy()}
            return SimpleNamespace(base_seed=seed, best_epoch=2,
                                   best_nll=.6 if purpose == "early_stop" else None,
                                   epochs_completed=2,
                                   status="early_stopped" if purpose == "early_stop" else "complete",
                                   history=history, checkpoint_path=checkpoint, purpose=purpose,
                                   identity={"external": identity}, standardizer=scaler,
                                   parameters=parameters)
        seeds = [result(seed, "early_stop") for seed in self.m.training.BASE_SEEDS]
        if k == self.pause_k:
            seeds[0].status = "epoch_cap_reached"
            seeds[0].best_epoch = 490
            seeds[0].epochs_completed = 500
            return SimpleNamespace(fit=None, seed_results=seeds,
                                   selected_seed=seeds[0].base_seed, requires_pause=True)
        return SimpleNamespace(fit=result(seeds[0].base_seed, "full_refit"),
                               seed_results=seeds, selected_seed=seeds[0].base_seed,
                               requires_pause=False)

    def patch(self):
        stack = ExitStack()
        stack.enter_context(patch.object(self.m.inp, "context", return_value=(
            None, self.run, self.cfg, {"protected_files": {}}, self.guard)))
        stack.enter_context(patch.object(self.m.inp, "cohorts", return_value=self.roles))
        stack.enter_context(patch.object(self.m.inp, "endpoints", side_effect=self.endpoints))
        stack.enter_context(patch.object(self.m.training, "fit_role", side_effect=self.fit))
        return stack


class FormalTrainingTests(unittest.TestCase):
    def test_sequential_full_pool_fits_export_all_query_parameters(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            fixture = Fixture(m, d)
            with fixture.patch():
                receipt = m.train_role("conditional_mdn_s5_e3_fixture", "C_T0")
            self.assertEqual(receipt["status"], "complete")
            self.assertEqual([call[1] for call in fixture.calls], [1, 2, 4, 8, 16, 32])
            self.assertTrue(all(call[3] and call[4] == 20 for call in fixture.calls))
            self.assertEqual(fixture.endpoint_calls, [("C_T0", "fit")])
            self.assertFalse(receipt["outer_targets_read"])
            self.assertEqual(set(receipt["models"]), {"1", "2", "4", "8", "16", "32"})
            folder = fixture.run["results"] / "formal_v1/C_T0/K4"
            with np.load(folder / "parameters.npz", allow_pickle=False) as archive:
                self.assertEqual(archive["pi"].shape, (3, 4))
                self.assertEqual(archive["query_keys"].dtype, np.dtype("int64"))
                np.testing.assert_array_equal(archive["query_keys"],
                                              fixture.roles["C_T0"]["query"][m.inp.KEY])
                self.assertEqual(archive["cov"].shape, (3, 4, 2, 2))
                self.assertEqual(archive["target_scale"].shape, (2,))
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(len(manifest["seeds"]), 3)
            self.assertEqual(len(manifest["seeds"][0]["history"]), 2)
            self.assertEqual(manifest["diagnostics"]["prediction_count"], 3)
            self.assertAlmostEqual(manifest["diagnostics"]["mixture_entropy_mean_nats"], np.log(4))
            self.assertEqual(manifest["diagnostics"]["full_refit_gradient_clip_rate"], .5)

    def test_completed_role_reuses_frozen_files_without_endpoint_reads_or_fits(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            fixture = Fixture(m, d)
            with fixture.patch():
                original = m.train_role("conditional_mdn_s5_e3_fixture", "C_T1")
                fixture.calls.clear()
                fixture.endpoint_calls.clear()
                resumed = m.train_role("conditional_mdn_s5_e3_fixture", "C_T1")
            self.assertEqual(resumed, original)
            self.assertEqual(fixture.calls, [])
            self.assertEqual(fixture.endpoint_calls, [])

    def test_outer_requires_completed_selection_before_any_fit_endpoint_access(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            fixture = Fixture(m, d)
            with fixture.patch(), self.assertRaisesRegex(PermissionError, "selection"):
                m.train_role("conditional_mdn_s5_e3_fixture", "C_outer")
            self.assertEqual(fixture.calls, [])
            self.assertEqual(fixture.endpoint_calls, [])
            selection = fixture.run["results"] / "formal_v1/selection.json"
            selection.parent.mkdir(parents=True, exist_ok=True)
            selection.write_text(json.dumps({"status": "complete", "selected_k": 4}))
            with fixture.patch(), self.assertRaisesRegex(PermissionError, 'selection'):
                m.train_role("conditional_mdn_s5_e3_fixture", "C_outer")
            evidence = {}
            for role in ('C_T0', 'C_T1'):
                for kind in ('forecast', 'inner_energy', 'inner_regions'):
                    suffix = 'forecast_freeze.json' if kind == 'forecast' else f'{kind}/N65536_M65536/complete.json'
                    path = fixture.run['provenance']/f'formal_v1/{role}/{suffix}'
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(dict(status='complete', role=role, kind=kind)))
                    evidence[str(path)] = m.file_sha256(path)
            choice = dict(status='complete', selected_k=4, provisional_k=4,
                          contract_sha256=m.training.CONTRACT_SHA256,
                          source_run_name=fixture.run['results'].name,
                          selection_inputs_sha256=evidence)
            selection.write_text(json.dumps(choice))
            with fixture.patch():
                receipt = m.train_role("conditional_mdn_s5_e3_fixture", "C_outer")
            self.assertEqual(receipt["selected_k"], 4)
            self.assertEqual(fixture.endpoint_calls, [("C_outer", "fit")])
            self.assertFalse(fixture.guard.outer_read)

    def test_partial_role_reuses_completed_candidate_before_resuming_remaining_candidates(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            fixture = Fixture(m, d)
            fixture.interrupt_k = 2
            with fixture.patch():
                with self.assertRaises(InterruptedError):
                    m.train_role("conditional_mdn_s5_e3_fixture", "C_T0")
                fixture.interrupt_k = None
                receipt = m.train_role("conditional_mdn_s5_e3_fixture", "C_T0")
            self.assertEqual(receipt["status"], "complete")
            self.assertEqual([call[1] for call in fixture.calls], [1, 2, 2, 4, 8, 16, 32])

    def test_selected_late_epoch_cap_preserves_curves_and_stops_before_export(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            fixture = Fixture(m, d)
            fixture.pause_k = 1
            with fixture.patch(), self.assertRaisesRegex(m.EpochCapPause, "last 30"):
                m.train_role("conditional_mdn_s5_e3_fixture", "C_T0")
            self.assertEqual(len(fixture.calls), 1)
            folder = fixture.run["results"] / "formal_v1/C_T0/K1"
            self.assertTrue((folder / "training_receipt.json").exists())
            self.assertFalse((folder / "parameters.npz").exists())
            self.assertFalse((fixture.run["provenance"] / "formal_v1/C_T0/forecast_freeze.json").exists())

    def test_tampered_parameter_archive_is_rejected_without_refitting(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            fixture = Fixture(m, d)
            with fixture.patch():
                m.train_role("conditional_mdn_s5_e3_fixture", "C_T0")
                archive = fixture.run["results"] / "formal_v1/C_T0/K1/parameters.npz"
                archive.write_bytes(b"tampered")
                fixture.calls.clear()
                with self.assertRaisesRegex(ValueError, "changed|checksum"):
                    m.train_role("conditional_mdn_s5_e3_fixture", "C_T0")
            self.assertEqual(fixture.calls, [])

    def test_nonfinite_predictions_fail_without_freezing_or_fallback(self):
        m = module()
        with tempfile.TemporaryDirectory() as d:
            fixture = Fixture(m, d)
            fixture.bad_parameters = True
            with fixture.patch(), self.assertRaisesRegex(FloatingPointError, "finite"):
                m.train_role("conditional_mdn_s5_e3_fixture", "C_T0")
            self.assertEqual(len(fixture.calls), 1)
            self.assertFalse((fixture.run["provenance"] / "formal_v1/C_T0/forecast_freeze.json").exists())

    def test_core_source_identity_excludes_evolving_scoring_and_report_files(self):
        m = module()
        sources = m.core_source_hashes()
        self.assertTrue(any(path.endswith("conditional_mdn_s5_e3_training.py") for path in sources))
        self.assertTrue(any(path.endswith("conditional_mdn_s5_e3_formal_training.py") for path in sources))
        self.assertFalse(any("test_" in path or "report" in path or "formal_scoring" in path
                             or "formal_context" in path for path in sources))


if __name__ == "__main__":
    unittest.main()
