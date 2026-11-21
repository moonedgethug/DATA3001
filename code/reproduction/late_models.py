"""Fresh late-stage initialization using unchanged science and historical approvals.

Approval metadata are reusable contracts. Model parameters, scores, completion
receipts and resource ledgers are never copied into a fresh output directory.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import copy
from pathlib import Path
import subprocess

from .registry import E3, E4, PREFIX
from .runner import run_command, run_module
from .workspace import independent_copy, safe_relative, sha256, write_json

CONTINUOUS = PREFIX + "continuous_models."
BASELINE = PREFIX + "baselines."


def finder_metadata_exception(original):
    """The two unavailable Finder metadata blobs are not scientific inputs.

    This narrow migration exception was authorized explicitly. All original
    approvals remain untouched and every excluded historical digest is retained.
    """
    allowed = {"src/.DS_Store": "a26e05c9e33f37ca8806b276b25a824c9418626289bb56b403999dea090d63ad",
               "src/data3001/.DS_Store": "568379138cdf3225304be3dcf8569f1f8d653ecf43073710ecad50e222bfe9a6"}
    approval = copy.deepcopy(original)
    excluded = []
    for path, expected in allowed.items():
        digest = approval.get("protected_files", {}).get(path)
        if digest is None:
            continue
        if digest != expected:
            raise ValueError("Finder metadata exception does not cover this historical identity")
        del approval["protected_files"][path]
        excluded.append({"path": path, "original_sha256": digest,
                         "reason": "Unavailable Finder display metadata; no source, scientific configuration or data removed."})
    return approval, excluded


def bind_identity(view, relative, digest):
    """Resolve exact historical bytes, recording any replacement inside the view."""
    relative = safe_relative(relative)
    current = view.path / relative
    if current.is_file() and sha256(current) == digest:
        return current
    candidates = []
    try:
        candidates.append(view.mapping.resolve(relative))
    except FileNotFoundError:
        pass
    bundle = view.root / "code/reproduction/historical_inputs" / digest
    if bundle.is_file():
        candidates.append(bundle)
    frozen = view.root / "provenance/frozen"
    if frozen.exists():
        candidates.extend(frozen.glob("*/records_before/" + relative))
        candidates.extend(frozen.glob("*/records_after/" + relative))
    source = next((path for path in candidates if path.is_file() and sha256(path) == digest), None)
    if source is None:
        raise FileNotFoundError(f"Missing approved historical bytes: {relative} (sha256 {digest})")
    previous = None
    if current.exists():
        if relative not in view.records:
            raise FileExistsError("Cannot replace an unrecorded execution file: " + relative)
        previous = view.records[relative]
        current.unlink()
    method = independent_copy(source, current)
    if sha256(current) != digest:
        raise ValueError("Historical copy identity mismatch: " + relative)
    view.records[relative] = {"source": source.relative_to(view.root).as_posix(),
        "execution_path": relative, "sha256": digest, "bytes": source.stat().st_size,
        "method": method, "role": "historical_contract_input"}
    if previous:
        view.records[relative]["replaced_execution_input_sha256"] = previous["sha256"]
    return current


def read_template(view, run, filename):
    relative = f"provenance/runs/{run}/{filename}"
    path = view.mapping.resolve(relative)
    value = json.loads(path.read_text())
    view.status.setdefault("reused_approval_templates", []).append({"source": relative,
                                                                  "sha256": sha256(path)})
    return value


def initialize_run(view, name, config, approval):
    safe_relative(name)
    if "/" in name:
        raise ValueError("Scientific run must be one path component")
    paths = {part: view.path / part / "runs" / name for part in ("results", "provenance")}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError("Fresh run would overwrite or reuse existing model output: " + name)
    for path in paths.values():
        path.mkdir(parents=True)
    write_json(paths["provenance"] / "run.json", {"name": name, "run_id": name,
        "created_utc": datetime.now(timezone.utc).isoformat(), "config": config})
    write_json(paths["provenance"] / "approval.json", approval)
    write_json(paths["provenance"] / "delivery_initialization.json", {
        "schema_version": 1, "fresh_output_directory": True, "saved_model_outputs_copied": False,
        "enclosing_delivery_run": view.directory.name, "logical_scientific_run": name,
        "approval_reuse_is_not_model_reuse": True})
    return paths


def _bind_approval(view, approval):
    for relative, digest in approval.get("protected_files", {}).items():
        bind_identity(view, relative, digest)
    for relative, digest in approval.get("new_source_sha256", {}).items():
        bind_identity(view, relative, digest)
    if approval.get("deferred_target_path"):
        # This is development outer validation, not the locked final-test set.
        bind_identity(view, approval["deferred_target_path"], approval["deferred_target_sha256"])


def prepare(view, task, *, timeout=None):
    from .operations import _prepare_model, _bind_config_references
    original = task.recorded_run
    if task.id.endswith("mdn12"):
        original = E3
    config = read_template(view, original, "run.json")["config"]
    approval = read_template(view, original, "approval.json")
    if task.id.endswith("seasonal_exact"):
        approval, excluded = finder_metadata_exception(approval)
        if excluded:
            write_json(view.directory / "finder_metadata_migration_exception.json", {
                "original_approval_sha256": sha256(view.mapping.resolve(f"provenance/runs/{original}/approval.json")),
                "explicit_engineering_migration_exception": True, "excluded": excluded,
                "scientific_sources_configuration_and_inputs_unchanged": True})
    bound = _prepare_model(view, replace(task, config="", runs=(), extra_inputs=(), needs_tracks=False))
    # Parent attempts are historical execution history, not required fresh fit inputs.
    dependencies = {key: value for key, value in config.items()
                    if key in {"e7_run", "e8_run", "repair_run", "baseline_run", "contract", "parent_pilot_run"}}
    _bind_config_references(view, dependencies, bound)
    _bind_approval(view, approval)
    if task.id.endswith("position_error"):
        name = "position_error_s4_e8_" + view.directory.name
        paths = initialize_run(view, name, config, approval)
        parity = read_template(view, original, "geometry_optimization_parity.json")
        write_json(paths["provenance"] / "geometry_optimization_parity.json", parity)
        commands = [(BASELINE + "run_position_error_s4_e8", ["pilot", "--run", name]),
                    (BASELINE + "position_error_s4_e8_sensitivity", ["--run", name]),
                    (BASELINE + "run_position_error_s4_e8", ["formal", "--run", name]),
                    (BASELINE + "position_error_s4_e8_audit", ["--run", name]),
                    (BASELINE + "position_error_s4_e8_report", ["--run", name])]
        run_command(view, ["-B", "-c", "from data3001.modelling.baselines import position_error_s4_e8_inputs as i; "
                          f"i.context({name!r}); print('E8 protected inputs verified; current exact-CDF implementation retained')"],
                    label="verify_position_error_initialization", timeout=timeout)
        fresh_names = [name]
    elif task.id.endswith("seasonal_exact"):
        name = "e9_formal_" + view.directory.name
        paths = initialize_run(view, name, config, approval)
        # Source snapshots are evidence of the current unchanged implementation.
        for relative, digest in approval.get("new_source_sha256", {}).items():
            source = view.path / relative
            independent_copy(source, paths["provenance"] / "sources" / source.name)
        run_command(view, ["-B", "-c", "from data3001.modelling.baselines import seasonal_exact_position_s4_e9_formal_io as i; "
                          f"a=i.context({name!r},'pilot'); a[-1].finish('delivery_initialization',True); print('E9 protected scientific inputs verified')"],
                    label="verify_seasonal_exact_initialization", timeout=timeout)
        commands = [(BASELINE + "seasonal_exact_position_s4_e9_formal", [stage, name])
                    for stage in ("tests", "inventory", "forecast", "score")]
        commands.extend([(BASELINE + "seasonal_exact_position_s4_e9_formal", ["audit", name]),
                         (BASELINE + "seasonal_exact_position_s4_e9_formal_report_v2", [name])])
        fresh_names = [name]
    elif task.id.endswith(("mdn6", "mdn12")):
        name = E3  # E4's unchanged hardcoded parent identity is local to this new view.
        paths = initialize_run(view, name, config, approval)
        authorization = read_template(view, E3, "formal_v1/authorization.json")
        bind_identity(view, authorization["deferred_target_path"], authorization["deferred_target_sha256"])
        write_json(paths["provenance"] / "formal_v1/authorization.json", authorization)
        write_json(paths["provenance"] / "resource_ledger.json", {"version": 1, "entries": [], "active": None})
        code = ("from data3001.modelling.continuous_models import conditional_mdn_s5_e3_inputs as i; "
                f"p,r,c,a,g=i.context({name!r},guarded=False); "
                "i.freeze_sources(r,'preflight'); i.freeze_access(r,i.cohorts(c)); "
                "print('Fresh MDN initialization verified; no fit performed')")
        run_command(view, ["-B", "-c", code], label="initialize_fresh_mdn", timeout=timeout)
        commands = [(CONTINUOUS + "conditional_mdn_s5_e3_formal_pipeline", [name]),
                    (CONTINUOUS + "conditional_mdn_s5_e3_formal_audit", [name])]
        fresh_names = [name]
        if task.id.endswith("mdn12"):
            commands.extend([(CONTINUOUS + "conditional_mdn_s5_e4_setup", [E4]),
                             (CONTINUOUS + "conditional_mdn_s5_e4_formal_pipeline", [E4]),
                             (CONTINUOUS + "conditional_mdn_s5_e4_formal_audit", [E4])])
            fresh_names.append(E4)
        else:
            commands.append((CONTINUOUS + "conditional_mdn_s5_e3_formal_report", [name]))
    elif task.id.endswith("gaussian"):
        name = "conditional_gaussian_s5_e1_full_" + view.directory.name
        paths = initialize_run(view, name, config, approval)
        # These are predeclared display cases; they contain no fitted parameters.
        examples = read_template(view, original, "example_selection.json")
        write_json(paths["provenance"] / "example_selection.json", examples)
        commands = [(CONTINUOUS + "conditional_gaussian_s5_e1_full", [name, mode])
                    for mode in ("preflight", "parameters", "regions", "score")]
        request = view.directory / "gaussian_support_request.json"
        write_json(request, {"run_name": name})
        commands.insert(2, ("__delivery_worker__", ["gaussian_support", str(request)]))
        commands.extend([(CONTINUOUS + "conditional_gaussian_s5_e1_verify", [name, "primary"]),
                         (CONTINUOUS + "conditional_gaussian_s5_e1_full", [name, "audit"]),
                         (CONTINUOUS + "conditional_gaussian_s5_e1_verify", [name, "audit"]),
                         (CONTINUOUS + "conditional_gaussian_s5_e1_full_report", [name])])
        run_command(view, ["-B", "-c", "from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_inputs as i; "
                          f"i.context({name!r}); print('Gaussian protected inputs verified')"],
                    label="verify_gaussian_initialization", timeout=timeout)
        fresh_names = [name]
    elif task.id.endswith("gmm"):
        name = "local_gmm_s5_e2_" + view.directory.name
        paths = initialize_run(view, name, config, approval)
        examples = read_template(view, original, "example_selection.json")
        write_json(paths["provenance"] / "example_selection.json", examples)
        changes = {}
        for key, library in (("native_path", "libe2_em.dylib"), ("score_native_path", "libe2_score.dylib")):
            changes[key] = {"original": config[key], "execution": str(paths["provenance"] / "native" / library)}
            config[key] = changes[key]["execution"]
        write_json(view.directory / "engineering_path_overrides.json", changes)
        write_json(paths["provenance"] / "run.json", {"run_id": name, "config": config})
        canonical = view.path / "configs/local_gmm_s5_e2.json"
        write_json(canonical, config)
        view.records["configs/local_gmm_s5_e2.json"].update(role="engineering_path_override", sha256=sha256(canonical), bytes=canonical.stat().st_size)
        independent_copy(canonical, paths["provenance"] / "frozen_config.json")
        code = ("from data3001.modelling.continuous_models import local_gmm_s5_e2_native as e, local_gmm_s5_e2_scoreopt as s; "
                f"e.compile_kernel({config['native_path']!r}); s.compile_kernel({config['score_native_path']!r})")
        run_command(view, ["-B", "-c", code], label="compile_unchanged_gmm_kernels", timeout=timeout)
        files = [*view.path.glob("src/data3001/modelling/continuous_models/local_gmm_s5_e2*"),
                 *view.path.glob("tests/test_modelling_local_gmm_s5_e2*.py"), canonical,
                 *paths["provenance"].glob("native/*.dylib")]
        write_json(paths["provenance"] / "source_hashes.json", {str(path.relative_to(view.path)): sha256(path) for path in files if path.is_file()})
        run_command(view, ["-B", "-c", "from data3001.modelling.continuous_models import local_gmm_s5_e2_pipeline as p; "
                          f"p.context({name!r}); print('GMM protected inputs and rebuilt kernels verified')"],
                    label="verify_gmm_initialization", timeout=timeout)
        commands = [(CONTINUOUS + "local_gmm_s5_e2_pipeline", [name, "all"])]
        fresh_names = [name]
    else:
        raise NotImplementedError("Unknown late-model initializer: " + task.id)
    plan = {"task": task.id, "fresh_scientific_runs": fresh_names, "reused_input_runs": sorted(bound),
            "commands": [{"module": module, "arguments": arguments} for module, arguments in commands],
            "model_outputs_copied_into_fresh_runs": False, "fitting_performed": False,
            "dependency_mode": "frozen_published_inputs", "upstream_refresh": False}
    write_json(view.directory / "execution_plan.json", plan)
    view.save_inventory()
    return plan


def run(view, task, *, prepare_only=False, timeout=None):
    plan = prepare(view, task, timeout=timeout)
    if prepare_only:
        return {"mode": "prepare", "prepared_only": True, "fitting_performed": False,
                "new_fits": [], "execution_plan": "execution_plan.json", "reused_input_runs": plan["reused_input_runs"]}
    for command in plan["commands"]:
        if command["module"] == "__delivery_worker__":
            run_command(view, ["-B", str(Path(__file__).with_name("worker.py")), *command["arguments"]],
                        label=command["arguments"][0], timeout=timeout)
        elif task.id.endswith("seasonal_exact") and command["arguments"][0] in {"inventory", "score"}:
            _seasonal_command(view, command, timeout=timeout)
        else:
            run_module(view, command["module"], command["arguments"], timeout=timeout)
    return {"mode": "refit", "fitting_performed": True, "new_fits": plan["fresh_scientific_runs"],
            "reused_input_runs": plan["reused_input_runs"], "execution_plan": "execution_plan.json",
            "dependency_mode": "frozen_published_inputs", "upstream_refresh": False,
            "outputs": [{"run": name, "results": f"workspace/results/runs/{name}",
                         "provenance": f"workspace/provenance/runs/{name}"} for name in plan["fresh_scientific_runs"]]}


def _seasonal_command(view, command, *, timeout):
    """Use only the previously approved recovery for its exact original trigger."""
    stage, name = command["arguments"]
    try:
        return run_module(view, command["module"], command["arguments"], timeout=timeout)
    except subprocess.CalledProcessError:
        provenance = view.path / "provenance/runs" / name
        failure_path = provenance / (stage + "_failure.json")
        if not failure_path.exists():
            raise
        failure = json.loads(failure_path.read_text())
        if stage == "inventory" and failure.get("type") == "AssertionError" and failure.get("message") == "Projected storage exceeds the approved precheck":
            inventory = json.loads((provenance / "support_inventory.json").read_text())
            if (inventory.get("cases") != 33971 or inventory.get("outer_targets_read") is not False
                    or inventory["projected_storage_bytes"] > 5 * 2**30):
                raise
            write_json(provenance / "storage_gate_review.json", {"complete_support_inventory": True,
                "outer_targets_read": False, "fresh_inventory_sha256": sha256(provenance / "support_inventory.json"),
                "prior_approved_storage_exception_replayed": True})
            module = BASELINE + "seasonal_exact_position_s4_e9_formal_resume_v2"
            run_module(view, module, ["approve", name], timeout=timeout)
            return run_module(view, module, ["resume", name], timeout=timeout)
        if stage == "score" and failure.get("type") == "KeyError" and "weighted_quantile" in failure.get("traceback", ""):
            return run_module(view, BASELINE + "seasonal_exact_position_s4_e9_formal_aggregate_resume", [name], timeout=timeout)
        raise
