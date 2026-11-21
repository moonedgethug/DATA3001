"""Delivery boundaries: immutable inputs, locked partitions and honest run status."""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))


class DeliveryWorkflowTests(unittest.TestCase):
    def api(self, name):
        self.assertTrue((CODE / "reproduction" / (name + ".py")).is_file(),
                        "The isolated reproduction adapter must be implemented")
        return importlib.import_module("reproduction." + name)

    def fixture(self, root, content=b"VALUE = 7\n"):
        source = root / "code/shared/scientific.py"
        source.parent.mkdir(parents=True)
        source.write_bytes(content)
        initializer = source.with_name("package_init.py")
        initializer.write_bytes(b"")
        (root / "docs").mkdir()
        (root / "docs/migration_manifest.json").write_text(json.dumps({
            "schema_version": 1, "files": [{"source": "src/data3001/scientific.py",
            "target": "code/shared/scientific.py", "sha256": hashlib.sha256(content).hexdigest(),
            "kind": "source"}, {"source": "src/data3001/__init__.py",
            "target": "code/shared/package_init.py", "sha256": hashlib.sha256(b"").hexdigest(),
            "kind": "source"}]}))
        return source

    def test_cli_lists_modes_without_requiring_data_or_importing_torch(self):
        result = subprocess.run([sys.executable, str(CODE / "workflow.py"), "list", "--json"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        tasks = json.loads(result.stdout)
        self.assertTrue(any(t["id"] == "predict.final_mdn22" for t in tasks))
        self.assertTrue(any(t["mode"] == "reuse" for t in tasks))
        self.assertTrue(any(t["mode"] == "refit" for t in tasks))

    def test_materialized_source_is_real_independent_copy_with_original_depth(self):
        api = self.api("workspace")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); original = self.fixture(root)
            view = api.ExecutionWorkspace(root, "copy-check")
            view.materialize_sources()
            copied = view.path / "src/data3001/scientific.py"
            self.assertTrue(copied.is_file())
            self.assertFalse(copied.is_symlink())
            self.assertEqual(copied.resolve().parents[2], view.path)
            copied.write_text("VALUE = 9\n")
            self.assertEqual(original.read_text(), "VALUE = 7\n")

    def test_corrupted_migrated_source_fails_before_execution(self):
        api = self.api("workspace")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); original = self.fixture(root); original.write_text("changed")
            view = api.ExecutionWorkspace(root, "identity-check")
            with self.assertRaisesRegex(ValueError, "[Ii]dentity|[Cc]hecksum"):
                view.materialize_sources()

    def test_locked_partition_and_parent_traversal_are_rejected(self):
        api = self.api("workspace")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.fixture(root)
            view = api.ExecutionWorkspace(root, "locked-check")
            for path in ["data/test/12.parquet", "archive/restricted_test/a", "../outside"]:
                with self.subTest(path=path), self.assertRaises((ValueError, PermissionError)):
                    view.bind(path)

    def test_same_run_id_never_overwrites_previous_run(self):
        api = self.api("workspace")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.fixture(root)
            api.ExecutionWorkspace(root, "once")
            with self.assertRaises(FileExistsError):
                api.ExecutionWorkspace(root, "once")

    def test_subprocess_uses_materialized_source_and_records_failure_honestly(self):
        api = self.api("workspace"); runner = self.api("runner")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            self.fixture(root, b"from pathlib import Path\np=Path(__file__).resolve().parents[2]\n(p/'made.txt').write_text('new calculation')\n")
            view = api.ExecutionWorkspace(root, "run-check"); view.materialize_sources()
            receipt = runner.run_module(view, "data3001.scientific", [])
            self.assertEqual(receipt["returncode"], 0)
            self.assertEqual((view.path / "made.txt").read_text(), "new calculation")
            self.assertFalse((root / "made.txt").exists())
            with self.assertRaises(subprocess.CalledProcessError):
                runner.run_module(view, "data3001.absent", [])
            receipts = json.loads((view.directory / "commands.json").read_text())
            self.assertNotEqual(receipts[-1]["returncode"], 0)

    def test_expected_input_hash_does_not_accept_current_changed_bytes(self):
        api = self.api("workspace")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.fixture(root)
            source = root / "docs/input.txt"; source.write_text("new value")
            view = api.ExecutionWorkspace(root, "input-check")
            with self.assertRaisesRegex(ValueError, "[Ii]dentity|[Cc]hecksum"):
                view.bind("docs/input.txt", expected_sha256="0" * 64)

    def test_directory_binding_excludes_locked_children_and_copies_safe_files(self):
        api = self.api("workspace")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.fixture(root)
            (root / "inputs/development").mkdir(parents=True)
            (root / "inputs/restricted_test").mkdir()
            (root / "inputs/development/a.txt").write_text("allowed")
            (root / "inputs/restricted_test/b.txt").write_text("locked")
            view = api.ExecutionWorkspace(root, "tree-check"); view.bind("inputs")
            self.assertEqual((view.path / "inputs/development/a.txt").read_text(), "allowed")
            self.assertFalse((view.path / "inputs/restricted_test").exists())

    def test_preflight_chain_selects_the_new_preflight_for_the_full_fit(self):
        operations = self.api("operations")
        self.assertTrue(hasattr(operations, "execute_model_commands"),
                        "Gated models need a fresh preflight chain, not a missing gate argument")
        api = self.api("workspace")
        from reproduction.registry import Task
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            program = b"import pathlib,sys\np=pathlib.Path.cwd()/'results/runs'\np.mkdir(parents=True,exist_ok=True)\nif '--preflight' in sys.argv:\n (p/'synthetic_preflight_new').mkdir()\nelse:\n assert sys.argv[sys.argv.index('--preflight-run')+1]=='synthetic_preflight_new'\n (p/'synthetic_fit_new').mkdir()\n"
            self.fixture(root, program)
            view = api.ExecutionWorkspace(root, "gated-check"); view.materialize_sources()
            task = Task("fixture", "fixture", "refit", "data3001.scientific",
                        preflight_argument="--preflight-run", preflight_prefix="synthetic_preflight_")
            operations.execute_model_commands(view, task)
            self.assertTrue((view.path / "results/runs/synthetic_fit_new").is_dir())

    def test_task_listing_distinguishes_a_recorded_success_from_an_unrun_task(self):
        self.assertTrue((CODE / "workflow.py").is_file())
        import workflow
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            folder = root / "results/reproduced/check"
            folder.mkdir(parents=True)
            (folder / "run.json").write_text(json.dumps({"task": "stage2.step1", "status": "complete",
                "mode": "refit", "created_utc": "2026-11-22T00:00:00Z", "new_fits": ["new_fit"]}))
            try:
                tasks = {task["id"]: task for task in workflow.list_tasks(root=root)}
            except TypeError:
                self.fail("Task listing must inspect successful delivery receipts separately from available code")
            self.assertEqual(tasks["stage2.step1"]["execution_validation"], "recorded_success")
            self.assertEqual(tasks["stage2.step5.mdn12"]["execution_validation"], "not_yet_run_in_this_delivery")

    def test_staged_model_receives_new_pilot_before_primary(self):
        operations = self.api("operations"); api = self.api("workspace")
        from reproduction.registry import Task
        self.assertIn("staged", Task.__dataclass_fields__, "Stage4 needs its actual pilot/primary interface")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            program = b"import pathlib,sys\np=pathlib.Path.cwd()/'results/runs'\np.mkdir(parents=True,exist_ok=True)\ns=sys.argv[sys.argv.index('--stage')+1]\nif s=='pilot':\n (p/'test_pilot_new').mkdir()\nelse:\n assert s=='primary' and sys.argv[sys.argv.index('--pilot')+1]=='test_pilot_new'\n (p/'test_primary_new').mkdir()\n"
            self.fixture(root, program)
            view = api.ExecutionWorkspace(root, "stages-check"); view.materialize_sources()
            task = Task("fixture", "fixture", "refit", "data3001.scientific", staged=True,
                        preflight_argument="--pilot", preflight_prefix="test_pilot_")
            operations.execute_model_commands(view, task)
            self.assertTrue((view.path / "results/runs/test_primary_new").is_dir())

    def test_cli_passes_only_selected_adapter_options(self):
        import workflow
        for argv, expected in [
            (["run", "report.rebuild", "--figures", "study_region", "--recompute-region"],
             {"figures": ["study_region"], "recompute_region": True}),
            (["run", "data.raw_cleaning", "--ids", "7706157"], {"ids": ["7706157"]}),
        ]:
            with self.subTest(argv=argv), patch.object(workflow, "run_task", return_value={}) as run:
                self.assertEqual(workflow.main(argv), 0)
                kwargs = run.call_args.kwargs
                self.assertNotIn("origins", kwargs)
                self.assertNotIn("recover_task", kwargs)
                for key, value in expected.items():
                    self.assertEqual(kwargs[key], value)

    def test_child_drops_inherited_data_root_and_pythonhome(self):
        api = self.api("workspace"); runner = self.api("runner")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            program = b"import os\nassert 'DATA3001_DATA_ROOT' not in os.environ\nassert 'PYTHONHOME' not in os.environ\nassert os.environ['OMP_NUM_THREADS']=='1'\n"
            self.fixture(root, program)
            view = api.ExecutionWorkspace(root, "env-check"); view.materialize_sources()
            with patch.dict("os.environ", {"DATA3001_DATA_ROOT": "/inherited/data", "PYTHONHOME": "/wrong/python"}):
                runner.run_module(view, "data3001.scientific", [])

    def test_historical_identity_binding_replaces_only_the_execution_copy(self):
        api = self.api("workspace"); late = self.api("late_models")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.fixture(root)
            (root / "docs/input.md").write_text("current")
            old = root / "provenance/frozen/check/records_before/docs/input.md"
            old.parent.mkdir(parents=True); old.write_text("approved")
            view = api.ExecutionWorkspace(root, "historical-check"); view.bind("docs/input.md")
            late.bind_identity(view, "docs/input.md", api.sha256(old))
            self.assertEqual((view.path / "docs/input.md").read_text(), "approved")
            self.assertEqual((root / "docs/input.md").read_text(), "current")
            self.assertEqual(view.records["docs/input.md"]["role"], "historical_contract_input")

    def test_late_model_bootstrap_has_no_saved_outputs(self):
        api = self.api("workspace"); late = self.api("late_models")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.fixture(root)
            view = api.ExecutionWorkspace(root, "bootstrap-check")
            paths = late.initialize_run(view, "conditional_mdn_s5_e3_fresh", {"candidates": [1, 2]},
                                        {"protected_files": {}, "final_test_access": False})
            self.assertEqual(list(paths["results"].iterdir()), [])
            self.assertFalse((paths["provenance"] / "formal_v1/final_audit.json").exists())
            with self.assertRaises(FileExistsError):
                late.initialize_run(view, "conditional_mdn_s5_e3_fresh", {}, {})

    def test_only_exact_historical_finder_metadata_can_be_excluded(self):
        late = self.api("late_models")
        original = {"protected_files": {"src/.DS_Store": "a26e05c9e33f37ca8806b276b25a824c9418626289bb56b403999dea090d63ad",
                     "src/data3001/science.py": "protected", "configs/science.json": "also-protected"}}
        fixed, excluded = late.finder_metadata_exception(original)
        self.assertEqual(set(fixed["protected_files"]), {"src/data3001/science.py", "configs/science.json"})
        self.assertEqual(excluded[0]["path"], "src/.DS_Store")
        self.assertIn("src/.DS_Store", original["protected_files"])
        with self.assertRaises(ValueError):
            late.finder_metadata_exception({"protected_files": {"src/.DS_Store": "unknown-historical-hash"}})

    def test_full_refit_stops_and_preserves_completed_child_on_failure(self):
        api = self.api("workspace"); full = self.api("full")
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.fixture(root)
            with patch.object(full, "run_stage", side_effect=[
                {"status": "complete", "new_fits": ["fresh_one"], "output_directory": "child1"},
                RuntimeError("second scientific gate failed")]) as run:
                with self.assertRaisesRegex(RuntimeError, "scientific gate"):
                    full.run(root, run_id="full-failed", tasks=["stage2.step1", "stage2.step4.seasonal"])
            self.assertEqual(run.call_count, 2)
            receipt = json.loads((root / "results/reproduced/full-failed/run.json").read_text())
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(len(receipt["completed_tasks"]), 1)
            self.assertFalse(receipt["upstream_refresh"])
            self.assertEqual(receipt["dependency_mode"], "frozen_published_inputs")

    def test_gaussian_support_receipt_is_recomputed_from_new_parameters(self):
        worker = self.api("worker")
        records = [{"query_position": i, "id": 7, "pairs": 4, "independent_ids": 2,
                    "gaussian": {"eigenvalues": [2., 6.], "condition_number": 3.}} for i in range(2)]
        result = worker.summarize_gaussian_support(records, expected_cases=2, expected_ids=1)
        self.assertEqual(result["min_eigenvalue"], 2.)
        self.assertTrue(result["passed"])
        records[1]["gaussian"]["eigenvalues"][0] = -1
        with self.assertRaises(ValueError):
            worker.summarize_gaussian_support(records, expected_cases=2, expected_ids=1)

    def test_prepare_only_rejects_unsupported_tasks_before_creating_output(self):
        import workflow
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for identifier in ("stage1.baselines", "data.inspect", "predict.final_mdn22", "full.refit", "report.rebuild"):
                with self.subTest(task=identifier), self.assertRaisesRegex(ValueError, "prepare_only"):
                    workflow.run_task(identifier, root=root, prepare_only=True)
            self.assertFalse((root / "results").exists())

    def test_default_full_plan_includes_reports_and_phase_aliases_exclude_recursion(self):
        full = self.api("full")
        import workflow
        plan = full.task_plan()
        self.assertEqual(plan["followup_tasks"], ["report.rebuild", "presentation.export"])
        self.assertFalse(full.task_plan(["stage2.step1"])["followup_tasks"])
        with patch.object(full, "run", return_value={}) as run:
            workflow.run_task("stage2.all")
            kwargs = run.call_args.kwargs
            self.assertEqual(kwargs["task_id"], "stage2.all")
            self.assertIn("stage2.step5.mdn12", kwargs["tasks"])
            self.assertNotIn("stage2.step5.mdn6", kwargs["tasks"])
            self.assertNotIn("stage2.all", kwargs["tasks"])

    def test_latest_resource_gate_failure_remains_visible_after_initialization(self):
        import workflow
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for index, status in enumerate(["prepared", "failed"]):
                folder = root / "results/reproduced" / str(index); folder.mkdir(parents=True)
                (folder / "run.json").write_text(json.dumps({"task": "stage2.step5.gaussian", "status": status,
                    "created_utc": str(index), "failure_category": "resource_gate_failed" if index else None}))
            task = next(item for item in workflow.list_tasks(root=root) if item["id"] == "stage2.step5.gaussian")
            self.assertEqual(task["execution_validation"], "not_yet_run_in_this_delivery")
            self.assertEqual(task["initialization_validation"], "recorded_success_without_fitting")
            self.assertEqual(task["current_blocker"], "resource_gate_failed")


if __name__ == "__main__":
    unittest.main()
