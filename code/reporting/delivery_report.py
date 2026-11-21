"""Rebuild report figures in a new run using unchanged, frozen-source scripts.

Regional table replay is the default. ``recompute_region=True`` reruns the
registered integration and independent sampler using the frozen K=22 model;
neither route fits or selects a model or reads final-test trajectories.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
import time

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reproduction.runner import run_command
from reproduction.workspace import ExecutionWorkspace, independent_copy, safe_relative, sha256, write_json


BUNDLE = "data/prepared/report_inputs"
GROUPS = {
    "study_region": ("W01_study_region", "figure_w01_region.py", ["figure_w01_region_zh"]),
    "region_domain": ("W03_region_and_domain", "figure_w03_region_and_domain.py", ["figure_w03_region_and_domain_zh"]),
    "model_comparison": ("W05_W11_models", "render_figures.py", [
        "figure04_hourly_propagation", "figure05_spatial_information", "figure06_exact_starting_position"]),
    "prediction_cases": ("W12_prediction_cases", "render_cases.py", ["figure_w12_four_cases_zh"]),
    "regional_distribution": ("W12_regional_distribution", "render_figures.py", [
        "figure_w12_regional_distribution_zh", "figure_w12_release_support_zh", "figure_w12_weight_sensitivity_zh"]),
    "training_support": ("W13_training_support", "render_training_support.py", ["figure09_annual_training_support_zh"]),
}


def select_figures(figures):
    if figures is None or figures == "all":
        return list(GROUPS)
    if isinstance(figures, str):
        figures = [figures]
    selected = list(dict.fromkeys(figures))
    if not selected or any(name not in GROUPS for name in selected):
        raise ValueError("Choose report figures from: " + ", ".join(GROUPS))
    return selected


def validate_bundle_entry(root, entry):
    relative = safe_relative(entry["path"])
    if Path(relative).suffix not in {".csv", ".parquet", ".npz", ".json"}:
        raise ValueError("The report input bundle may contain data and metadata only")
    base = Path(root).resolve() / BUNDLE
    source = (base / relative).resolve()
    if not source.is_relative_to(base.resolve()):
        raise ValueError("Report input escapes its portable bundle")
    safe_relative(entry["execution_path"])
    if sha256(source) != entry["sha256"]:
        raise ValueError("Report input checksum mismatch: " + relative)
    return source


def check_probability_rows(rows, unresolved_weight):
    grouped = {}
    for row in rows:
        scenario, category = row["scenario"], row["category"]
        values = grouped.setdefault(scenario, {})
        value = float(row["probability"])
        if category in values or not math.isfinite(value) or value < 0 or value > 1:
            raise ValueError("Invalid or duplicated regional probability")
        values[category] = value
    required = {"R_water", "D_water_outside_R", "D_land", "outside_D", "unresolved"}
    if "area_release" not in grouped:
        raise ValueError("The whole-R release scenario is missing")
    totals = {}
    for scenario, values in grouped.items():
        if set(values) != required:
            raise ValueError("All geographic categories and unresolved release mass must remain explicit")
        expected_unresolved = unresolved_weight if scenario == "area_release" else 0.
        if abs(values["unresolved"] - expected_unresolved) > 1e-12:
            raise ValueError("Unresolved release mass was changed or renormalized")
        totals[scenario] = math.fsum(values.values())
        if abs(totals[scenario] - 1.) > 1e-12:
            raise ValueError("Regional probability total differs from one")
    return {"scenario_totals": totals, "unresolved_weight": unresolved_weight,
            "unresolved_percent": 100 * unresolved_weight,
            "unresolved_semantics": "Whole-R wet-area release weight without eligible training-origin support; not a grounding probability."}


def _regional_checks(folder, manifest, reference):
    import numpy as np
    import pandas as pd

    summary = json.loads((folder / "summary.json").read_text())
    if summary.get("status") != "complete" or summary.get("new_training") is not False:
        raise ValueError("Regional results are not a completed frozen-model analysis")
    if summary.get("final_test_access") is not False or summary.get("model_selection") is not False:
        raise ValueError("Regional analysis exceeded its frozen-model scope")
    unresolved = float(summary["release"]["unresolved_weight"])
    if abs(unresolved - manifest["regional_unresolved_weight"]) > 1e-12:
        raise ValueError("Whole-R unsupported release weight differs from the frozen analysis")
    with (folder / "region_probabilities.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    result = check_probability_rows(rows, unresolved)
    cells = pd.read_csv(folder / "release_cells.csv")
    origins = pd.read_parquet(folder / "release_origins.parquet")
    grid = pd.read_parquet(folder / "display_grid.parquet")
    if len(origins) != 265393 or origins.id.nunique() != 338:
        raise ValueError("Regional release population differs from the approved training-origin prior")
    if not math.isclose(cells.whole_R_release_weight.sum(), 1., abs_tol=1e-12):
        raise ValueError("Release cell weights do not cover whole R")
    unsupported = float(cells.loc[~cells.supported, "whole_R_release_weight"].sum())
    if abs(unsupported - unresolved) > 1e-12 or abs(origins.area_release_weight.sum() + unresolved - 1.) > 1e-12:
        raise ValueError("Unsupported cells or origin weights were omitted from whole-R accounting")
    categories = ["R_water", "D_water_outside_R", "D_land", "outside_D"]
    scenarios = ["area_release", "historical_origins", "area_supported_only"]
    table = {(row["scenario"], row["category"]): float(row["probability"]) for row in rows}
    maximum_error = 0.
    with np.load(folder / "integration_by_cell.npz", allow_pickle=False) as integration:
        for j, scenario in enumerate(scenarios):
            current = np.einsum("c,ck->k", integration["cell_weights"][j], integration["regions"][:, -1].mean(axis=1))
            expected = np.array([table[(scenario, category)] for category in categories])
            maximum_error = max(maximum_error, float(np.max(np.abs(current - expected))))
            missing = unresolved if scenario == "area_release" else 0.
            if abs(grid[scenario + "_day7"].sum() + summary["outside_display_grid"][scenario] + missing - 1.) > 1e-12:
                raise ValueError("Display-grid tail mass was lost")
    if maximum_error > 1e-12:
        raise ValueError("Regional probabilities disagree with saved cell integrations")
    expected = {(row["scenario"], row["category"]): row["probability"] for row in reference["probabilities"]}
    delta = max(abs(value - expected[key]) for key, value in table.items())
    if delta > 0.0005:
        raise ValueError("Recomputed regional probabilities exceed the original numerical tolerance")
    result.update(max_aggregation_error=maximum_error, max_probability_difference_from_reference=delta,
                  supported_cells=int(cells.supported.sum()), wet_cells=len(cells),
                  training_origins=len(origins), training_drifters=int(origins.id.nunique()))
    return result


def _copy_to_run(view, source, destination, copied, *, role):
    destination = view.directory / safe_relative(destination)
    if not destination.resolve().is_relative_to(view.directory.resolve()):
        raise PermissionError("Report execution destination escapes the run")
    independent_copy(source, destination)
    digest = sha256(source)
    if sha256(destination) != digest:
        raise ValueError("Report execution copy changed bytes")
    copied.append({"execution_path": destination.relative_to(view.directory).as_posix(),
                   "sha256": digest, "bytes": destination.stat().st_size, "role": role})
    return destination


def _check_outputs(folder, names):
    from PIL import Image

    outputs = []
    for name in names:
        for suffix in ("png", "pdf"):
            path = folder / (name + "." + suffix)
            if not path.is_file() or path.stat().st_size < 100:
                raise ValueError("A requested report figure was not generated: " + str(path))
            if suffix == "png":
                with Image.open(path) as image:
                    if min(image.size) < 200:
                        raise ValueError("Report figure has invalid dimensions")
                    image.verify()
            elif not path.read_bytes().startswith(b"%PDF-"):
                raise ValueError("Report PDF header is invalid")
            outputs.append(path)
    return outputs


def run(root, run_id=None, figures=None, recompute_region=False, **kwargs):
    """Generate chosen figure groups in a new ``results/reproduced`` directory."""
    selected = select_figures(figures)
    if not isinstance(recompute_region, bool):
        raise TypeError("recompute_region must be a boolean")
    timeout = kwargs.pop("timeout", 900)
    if kwargs:
        raise TypeError("Unknown report option(s): " + ", ".join(sorted(kwargs)))
    if recompute_region and "regional_distribution" not in selected:
        raise ValueError("recompute_region requires the regional_distribution figure group")
    requested = list(selected)
    if recompute_region and "prediction_cases" not in selected:
        selected.insert(selected.index("regional_distribution"), "prediction_cases")
    # Original analysis protects the four-case picture, so render it first.
    selected = [name for name in GROUPS if name in selected]
    root = Path(root).resolve()
    manifest_path = root / BUNDLE / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported report input manifest")
    reference = json.loads((root / BUNDLE / "regional_distribution/summary.json").read_text())
    view = ExecutionWorkspace(root, run_id)
    started = time.monotonic()
    copied, outputs = [], []
    try:
        view.status.update(task="report.rebuild", mode="report", requested_figures=requested, figures=selected,
                           regional_mode="recomputed_frozen_model" if recompute_region else "replayed_frozen_tables",
                           report_input_manifest_sha256=sha256(manifest_path),
                           report_adapter_sha256=sha256(Path(__file__)), no_training=True)
        view.materialize_sources()
        (view.directory / "work_place").symlink_to("workspace", target_is_directory=True)
        view.bind(BUNDLE + "/manifest.json", expected_sha256=sha256(manifest_path))
        for entry in manifest["repository_inputs"]:
            if set(entry["figures"]) & set(selected):
                view.bind(entry["path"], expected_sha256=entry["sha256"])
        for entry in manifest["sources"]:
            source = view.bind(entry["path"], expected_sha256=entry["sha256"])[0]
            _copy_to_run(view, source, entry["execution_path"], copied, role="unchanged_source")
        for entry in manifest["files"]:
            if not set(entry["figures"]) & set(selected):
                continue
            validate_bundle_entry(root, entry)
            source = view.bind(BUNDLE + "/" + entry["path"], expected_sha256=entry["sha256"])[0]
            if recompute_region and entry["mode"] == "replay":
                continue
            _copy_to_run(view, source, entry["execution_path"], copied, role="frozen_report_input")
        view.save_inventory()
        write_json(view.directory / "report_input_manifest.json", {"files": copied})
        view.status.update(status="running", reused_input_files=len(view.records))
        write_json(view.directory / "run.json", view.status)
        for name in selected:
            folder_name, script, names = GROUPS[name]
            folder = view.directory / "Final Report/figures" / folder_name
            if name == "regional_distribution" and recompute_region:
                run_command(view, ["-B", folder / "run_analysis.py"], label="regional_frozen22_integration", timeout=timeout)
                run_command(view, ["-B", folder / "verify_analysis.py"], label="regional_independent_verification", timeout=timeout)
            run_command(view, ["-B", folder / script], label="report_" + name, timeout=timeout)
            outputs.extend(_check_outputs(folder, names))
        probability = None
        if "regional_distribution" in selected:
            probability = _regional_checks(view.directory / "Final Report/figures/W12_regional_distribution", manifest, reference)
        for record in copied:
            if sha256(view.directory / record["execution_path"]) != record["sha256"]:
                raise ValueError("A copied report input or source was modified: " + record["execution_path"])
        for record in view.records.values():
            if sha256(view.path / record["execution_path"]) != record["sha256"]:
                raise ValueError("A frozen workspace input was modified: " + record["execution_path"])
        output_records = {path.relative_to(view.directory).as_posix(): {
            "sha256": sha256(path), "bytes": path.stat().st_size} for path in outputs}
        verification = {"status": "passed", "figures": len(outputs) // 2,
                        "png_pdf_outputs": len(outputs), "probability_accounting": probability,
                        "source_and_input_hashes_unchanged": True, "new_fits": [], "final_test_access": False,
                        "regional_mode": view.status["regional_mode"]}
        write_json(view.directory / "report_verification.json", verification)
        return view.finish("complete", outputs=output_records, report_verification=verification,
                           elapsed_seconds=time.monotonic() - started)
    except BaseException as error:
        view.finish("interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                    error=f"{type(error).__name__}: {error}", elapsed_seconds=time.monotonic() - started)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--run-id")
    parser.add_argument("--figures", nargs="+", choices=list(GROUPS))
    parser.add_argument("--recompute-region", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.run_id, args.figures, args.recompute_region), indent=2))


if __name__ == "__main__":
    main()
