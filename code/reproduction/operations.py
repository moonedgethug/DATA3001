"""Task orchestration with explicit saved-input reuse and newly computed outputs."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

from .registry import REGISTRY, get_task
from .runner import run_command, run_module
from .workspace import DeliveryMap, ExecutionWorkspace, independent_copy, sha256, write_json

FINAL22_SHA256 = "216f92b678e25b1c804a7f0a1928779b9233ff22f7140536e825969df6d176b0"


def inspect_task(root, identifier):
    task = get_task(identifier)
    result = task.describe()
    mapping = DeliveryMap(root)
    result["migration_manifest_sha256"] = sha256(mapping.path)
    result["inputs"] = list(task.runs)
    result["output"] = "results/reproduced/<new-run-id>/"
    result["final_test_access"] = False
    if task.config:
        path = mapping.resolve(task.config)
        result["configuration"] = {"path": str(path), "sha256": sha256(path),
                                   "settings": json.loads(path.read_text())}
    elif task.recorded_run and identifier.startswith("stage2.step5."):
        path = mapping.resolve("provenance/runs/" + task.recorded_run + "/run.json")
        settings = json.loads(path.read_text())["config"]
        result["configuration"] = {"path": str(path), "metadata_sha256": sha256(path), "settings": settings,
                                   "source": "original_approved_run_configuration"}
        result["inputs"] = {key: settings[key] for key in
                            ("e7_run", "e8_run", "repair_run", "baseline_run", "parent_run", "parent_pilot_run") if key in settings}
        result["prepare_only_supported"] = True
    if identifier in {"full.refit", "stage1.all", "stage2.all"}:
        from .full import task_plan
        selected = None
        if identifier != "full.refit":
            prefix = identifier.split(".")[0] + "."
            selected = [item.id for item in REGISTRY.values() if item.id.startswith(prefix)
                        and item.mode in {"refit", "prepare", "score"} and item.id != "stage2.step5.mdn6"]
        result["execution_plan"] = task_plan(selected)
    if task.recorded_run:
        result["recorded_result"] = str(mapping.resolve("results/runs/" + task.recorded_run))
    return result


def _bind_config_references(view, value, bound_runs):
    if isinstance(value, dict):
        for nested in value.values():
            _bind_config_references(view, nested, bound_runs)
    elif isinstance(value, list):
        for nested in value:
            _bind_config_references(view, nested, bound_runs)
    elif isinstance(value, str):
        if value.startswith(("results/runs/", "provenance/runs/")):
            components = value.split("/")
            if len(components) >= 3:
                _bind_run(view, components[2], bound_runs)
        elif re.fullmatch(r"[A-Za-z0-9_.-]+", value) and re.search(r"20\d{6}T\d{6}", value):
            try:
                view.mapping.resolve("results/runs/" + value)
            except FileNotFoundError:
                try:
                    view.mapping.resolve("provenance/migrations/" + value)
                except FileNotFoundError:
                    return
                view.bind("provenance/migrations/" + value)
                return
            _bind_run(view, value, bound_runs)
        elif value.startswith(("docs/", "provenance/reviews/", "provenance/migrations/")):
            source = view.mapping.resolve(value)
            # Support reviews carry companion hashes and tables beside their
            # nominated JSON file; the scientific readers verify those too.
            relative = str(Path(value).parent) if source.is_file() and value.startswith("provenance/reviews/") and len(Path(value).parts) > 3 else value
            view.bind(relative)


def _bind_run(view, name, bound_runs):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise ValueError("Invalid source run")
    if name in bound_runs:
        return
    bound_runs.add(name)
    for folder in ("results/runs/", "provenance/runs/"):
        view.bind(folder + name)
    metadata = view.path / "provenance/runs" / name / "run.json"
    if metadata.exists():
        _bind_config_references(view, json.loads(metadata.read_text()).get("config", {}), bound_runs)


def _bind_development(view):
    manifest = json.loads(view.mapping.resolve("configs/dataset_manifest.json").read_text())
    qualification = json.loads(view.mapping.resolve("configs/qualification_manifest.json").read_text())
    for sid, item in manifest["records"].items():
        if item["pool"] == "train":
            view.bind(item["path"], expected_sha256=item["sha256"])
            extra = qualification["records"][sid]
            if extra["pool"] != "train":
                raise ValueError("Qualification and trajectory pools differ")
            view.bind(extra["path"], expected_sha256=extra["sha256"])


def _prepare_model(view, task):
    view.materialize_sources()
    view.bind("docs")
    # Shared data readers require these metadata/geometry assets. Large raw
    # archives and final-test files are deliberately not materialized here.
    catalog = json.loads(view.mapping.resolve("configs/assets.json").read_text())
    essentials = [name for name in ("english_contract", "state_index", "release_R", "transport_D",
                  "land_mask_high", "land_mask_intermediate", "preparation_config",
                  "current_dataset_manifest", "current_dataset_index", "current_qualification_manifest",
                  "official_drogue_correction", "official_drogue_boundary", "corpus_time_coverage") if name in catalog["assets"]]
    view.bind_assets(essentials)
    bound_runs = set()
    for name in task.runs:
        _bind_run(view, name, bound_runs)
    if task.config:
        configuration = json.loads(view.mapping.resolve(task.config).read_text())
        view.bind_assets(configuration.get("source_assets", []))
        _bind_config_references(view, configuration, bound_runs)
    for relative in task.extra_inputs:
        view.bind(relative)
    if task.needs_tracks:
        _bind_development(view)
    view.save_inventory()
    return bound_runs


def _prediction(view, origins, samples, seed, timeout=None):
    if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
        raise ValueError("samples must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    registry_path = view.root / "saved_models/registry.json"
    registry = json.loads(registry_path.read_text())
    record = registry["final_mdn22"]
    if record["sha256"] != FINAL22_SHA256:
        raise ValueError("The registry does not identify the frozen final K22 checkpoint")
    view.materialize_sources()
    files = view.bind(record["path"], expected_sha256=FINAL22_SHA256)
    worker = Path(__file__).with_name("worker.py")
    request = view.directory / "prediction_request.json"
    output = view.directory / "prediction"
    write_json(request, {"checkpoint": str(files[0]), "sha256": FINAL22_SHA256,
                         "origins": origins, "samples": samples, "seed": seed, "output": str(output)})
    # This small delivery worker is separate from the unmodified scientific package.
    run_command(view, ["-B", str(worker), "predict", str(request)], label="frozen_mdn22_inference", timeout=timeout)
    prediction = json.loads((output / "prediction.json").read_text())
    if prediction["metadata"]["K"] != 22:
        raise ValueError("Inference returned the wrong model")
    return {"mode": "inference", "model_sha256": FINAL22_SHA256,
            "training_performed": False, "new_fits": [],
            "outputs": [str(p.relative_to(view.directory)) for p in sorted(output.iterdir())],
            "prediction_metadata": prediction["metadata"],
            "origins": prediction["origins_lonlat"], "samples_per_origin": samples}


def _data_inspection(view):
    path = view.mapping.resolve("configs/dataset_manifest.json")
    data = json.loads(path.read_text())
    development = [record for record in data["records"].values() if record["pool"] == "train"]
    value = {"mode": "inspection", "dataset_version": data["version"], "manifest_sha256": sha256(path),
             "development_ids": len(development), "development_rows": sum(r["rows"] for r in development),
             "declared_final_test_ids": data["pools"]["test"], "trajectory_content_read": False,
             "final_test_access": False, "contract_sha256": data["contract_sha256"]}
    write_json(view.directory / "data_identity.json", value)
    return value


def _recover(view, task_filter=None):
    records = []
    candidates = [task for task in REGISTRY.values() if task.recorded_run]
    if task_filter:
        candidates = [get_task(task_filter)]
    for task in candidates:
        if not task.recorded_run:
            raise ValueError("The selected task has no recorded experiment")
        base = view.mapping.resolve("results/runs/" + task.recorded_run)
        outputs = []
        # Recover presentation-scale summaries, not large per-node caches.
        for source in sorted(base.rglob("*")):
            if not source.is_file() or source.is_symlink() or source.stat().st_size > (20 << 20):
                continue
            name = source.name.lower()
            if not (source.suffix.lower() in {".md", ".html", ".png", ".pdf", ".svg"}
                    or (source.suffix == ".csv" and any(word in name for word in
                        ("summary", "comparison", "selection", "support", "interval", "acceptance")))
                    or name in {"selection.json", "acceptance.json", "completion.json", "summary.json"}):
                continue
            relative = source.relative_to(base)
            destination = view.directory / "recovered" / task.id / relative
            method = independent_copy(source, destination)
            digest = sha256(source)
            if sha256(destination) != digest:
                raise ValueError("Recovered result identity mismatch")
            outputs.append({"source": str(source.relative_to(view.root)),
                            "output": destination.relative_to(view.directory).as_posix(),
                            "sha256": digest, "method": method})
        records.append({"task": task.id, "original_run": task.recorded_run,
                        "source_directory": str(base), "recovered": outputs})
    value = {"mode": "reuse", "fitting_performed": False, "scores_recomputed": False,
             "scope": "Recorded reports and presentation-scale summaries; original full runs remain available at source_directory.",
             "experiments": records}
    write_json(view.directory / "recorded_results.json", value)
    return value


def execute_model_commands(view, task, *, timeout=None):
    arguments = list(task.arguments)
    if task.preflight_argument:
        folder = view.path / "results/runs"
        before = {p.name for p in folder.glob(task.preflight_prefix + "*") if p.is_dir()}
        pilot_arguments = ["--stage", "pilot"] if task.staged else ["--preflight"]
        run_module(view, task.module, pilot_arguments, timeout=timeout)
        fresh = sorted(p.name for p in folder.glob(task.preflight_prefix + "*")
                       if p.is_dir() and p.name not in before)
        if len(fresh) != 1:
            raise RuntimeError("Preflight did not create exactly one new gate run")
        arguments.extend([task.preflight_argument, fresh[0]])
        if task.staged:
            arguments.extend(["--stage", "primary"])
    view.status["status"] = "running"
    write_json(view.directory / "run.json", view.status)
    return run_module(view, task.module, arguments, timeout=timeout)


def execute(root, identifier, *, run_id=None, origins=None, samples=1000, seed=20261126,
            recover_task=None, timeout=None, prepare_only=False):
    task = get_task(identifier)
    if not task.implemented:
        raise NotImplementedError(task.gap)
    late_task = identifier.startswith("stage2.step5.") or identifier in {"stage2.step4.position_error", "stage2.step4.seasonal_exact"}
    if prepare_only and not late_task:
        raise ValueError("prepare_only applies only to late-stage model initialization")
    view = ExecutionWorkspace(root, run_id)
    started = time.monotonic()
    view.status.update(task=identifier, mode=task.mode, scope=task.scope)
    write_json(view.directory / "run.json", view.status)
    try:
        if identifier == "predict.final_mdn22":
            details = _prediction(view, origins or [[-78.0, 33.0]], samples, seed, timeout)
        elif identifier == "data.inspect":
            details = _data_inspection(view)
        elif identifier == "results.recover":
            details = _recover(view, recover_task)
        elif late_task:
            from .late_models import run
            details = run(view, task, prepare_only=prepare_only, timeout=timeout)
        else:
            bound_runs = _prepare_model(view, task)
            before = {p.name for p in (view.path / "results/runs").glob("*") if p.is_dir()}
            execute_model_commands(view, task, timeout=timeout)
            new_runs = sorted(p.name for p in (view.path / "results/runs").glob("*")
                              if p.is_dir() and p.name not in before)
            if not new_runs:
                raise RuntimeError("The scientific command exited without producing a new run")
            outputs = []
            for name in new_runs:
                directory = view.path / "results/runs" / name
                outputs.append({"run": name, "results": str(directory.relative_to(view.directory)),
                                "provenance": str((view.path / "provenance/runs" / name).relative_to(view.directory))})
            details = {"mode": task.mode, "scientific_command_completed": True,
                       "new_fits": [name for name in new_runs if not task.preflight_prefix
                                     or not name.startswith(task.preflight_prefix)] if task.mode == "refit" else [],
                       "preflight_runs": [name for name in new_runs if task.preflight_prefix
                                          and name.startswith(task.preflight_prefix)],
                       "new_data_runs": new_runs if task.mode == "prepare" else [],
                       "new_score_runs": new_runs if task.mode == "score" else [],
                       "reused_input_runs": sorted(bound_runs), "outputs": outputs,
                       "scope": task.scope or "Refit from the bound published input snapshots; upstream stages were not rerun."}
        return view.finish("prepared" if details.get("prepared_only") else "complete", **details, elapsed_seconds=time.monotonic() - started)
    except BaseException as error:
        failures = []
        for gate_path in view.path.glob("provenance/runs/conditional_gaussian_s5_e1_*/full_preflight.json"):
            relative = gate_path.relative_to(view.path).as_posix()
            if relative in view.records:
                continue
            gate = json.loads(gate_path.read_text())
            if gate.get("passed") is False:
                failures.append({"path": relative, "gate": gate})
        view.finish("interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                    error=f"{type(error).__name__}: {error}",
                    failure_category="resource_gate_failed" if failures else "execution_failure",
                    resource_gate_failures=failures, elapsed_seconds=time.monotonic() - started)
        raise
