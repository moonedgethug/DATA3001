"""Reproducible development-only nested CV and final candidate refitting.

Run with: .venv/bin/python -B -m data3001.modelling.baselines.run_blend_cv
This entry point never opens final-test trajectories and never changes data.
"""
from data3001.modelling.common.runtime import ReadOnlyInputs, save_frame, save_json
import json
import os
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from data3001.dataset import PreparedSource, manifest, track_path
from data3001.modelling.baselines.blend import select_lambdas
from data3001.modelling.baselines.cv import KEYS, bootstrap_differences, evaluate_nested, fit_baselines, serializable_model, summarize_scores
from data3001.modelling.common.experiment import SETTINGS, fold_digest, make_nested_folds
from data3001.paths import file_sha256, project_paths
from data3001.preprocessing.prep_core import REASONS
from data3001.preprocessing.prep_pairs import generate, load_track, origin_indices

OLD_FIT = "baseline_pooled_20261018T150758_752931Z"
OLD_VALIDATION = "baseline_validation_20261019T052149_527052Z"








def _sorted_counts(frame):
    return frame[KEYS + ["pair_count"]].sort_values(KEYS).reset_index(drop=True).astype("int64")


def reconcile_old_counts(paths, dataset, counts):
    """Require exact equality to both original development case populations."""
    checks = {}
    for historical, run_id, name in (("train", OLD_FIT, "training_counts_by_id.csv"),
                                      ("validation", OLD_VALIDATION, "validation_score_groups.csv")):
        old = pd.read_csv(paths.root / "results/runs" / run_id / name)
        if historical == "validation":
            old = old.loc[old["model"].eq("B1")]
        ids = {int(sid) for sid, r in dataset["records"].items() if r["historical_split"] == historical}
        fresh = counts.loc[counts["id"].isin(ids)]
        pd.testing.assert_frame_equal(_sorted_counts(fresh), _sorted_counts(old))
        checks[historical] = {"exact_grouped_counts_equal": True,
                              "eligible_pairs": {str(int(h)): int(g["pair_count"].sum())
                                                 for h, g in fresh.groupby("horizon_days")}}
    return checks


def collect_counts(paths, run, dataset, r_ids):
    source = PreparedSource(allow_test=False)
    parts, audits = [], []
    stored_rows = 0
    for number, sid in enumerate(sorted(r_ids), 1):
        if dataset["records"][str(sid)]["pool"] != "train":
            raise PermissionError("Non-development instrument in requested R population.")
        track, arrays, events = load_track(source, sid)
        stored_rows += dataset["records"][str(sid)]["rows"]
        origins = origin_indices(track, arrays, population="R")
        ledgers = []
        for h in SETTINGS["horizons_days"]:
            if not len(origins):
                continue
            endpoint, _ = generate(track, arrays, events, sid, origins,
                                   days=h, scenario="pooled", tolerance=0)
            if endpoint.duplicated(["id", "origin_source_obs", "horizon_days"]).any():
                raise RuntimeError("Duplicated source-keyed endpoint candidates.")
            ledgers.append(endpoint)
            for reason, n in endpoint["reason_code"].value_counts().items():
                audits.append({"id": sid, "horizon_days": h, "reason_code": int(reason),
                               "reason": REASONS[int(reason)], "pair_count": int(n)})
            eligible = endpoint.loc[endpoint["reason_code"].eq(0)]
            if not eligible["time_error_seconds"].eq(0).all() or not eligible["realized_duration_seconds"].eq(h * 86400).all():
                raise RuntimeError("Exact fixed-horizon matching changed.")
            if eligible["destination_cell_1"].eq(-1).any():
                raise RuntimeError("Invalid destination sentinel entered eligible labels.")
            if len(eligible):
                part = eligible.groupby(KEYS, as_index=False).size().rename(columns={"size": "pair_count"})
                parts.append(part)
        if ledgers:
            save_frame(paths, run["results"] / "endpoint_ledgers" / f"{sid}.parquet",
                       pd.concat(ledgers, ignore_index=True))
        if number % 25 == 0 or number == len(r_ids):
            print(f"Paired {number}/{len(r_ids)} development R-visitor IDs.", flush=True)
    counts = _sorted_counts(pd.concat(parts, ignore_index=True))
    audit = pd.DataFrame(audits)
    if counts.duplicated(KEYS).any():
        raise RuntimeError("Duplicate grouped count key.")
    for h in SETTINGS["horizons_days"]:
        if counts.loc[counts["horizon_days"].eq(h), "pair_count"].sum() != audit.loc[
            audit["horizon_days"].eq(h) & audit["reason_code"].eq(0), "pair_count"].sum():
            raise RuntimeError("Qualification/count denominator mismatch.")
    save_frame(paths, run["results"] / "development_counts.parquet", counts)
    save_frame(paths, run["results"] / "pair_qualification.csv", audit)
    return counts, stored_rows


def final_choices(terms):
    selections, grids = [], []
    for h, group in terms.groupby("horizon_days"):
        choice = select_lambdas(group[["A", "B", "C"]], group["pair_count"])
        for name, key in (("Grid", "grid"), ("Analytic", "analytic")):
            selections.append({"horizon_days": int(h), "method": name,
                               "lambda_value": choice[f"{key}_lambda"],
                               "tuning_brier": choice[f"{key}_brier"],
                               "A": choice["mean_coefficients"]["A"],
                               "B": choice["mean_coefficients"]["B"],
                               "C": choice["mean_coefficients"]["C"],
                               "scope": "All-development base OOF tuning; not an independent evaluation of this final weight"})
        grids.extend({"horizon_days": int(h), "lambda_value": r["lambda"],
                      "selection_brier": r["selection_brier"]} for r in choice["grid_scores"])
    return pd.DataFrame(selections), pd.DataFrame(grids)


def main():
    paths = project_paths()
    dataset = manifest()
    if dataset["version"] != SETTINGS["dataset_release"] or SETTINGS["final_test_access"]:
        raise RuntimeError("Dataset or final-test policy mismatch.")
    contract = paths.asset("english_contract", verify=True)
    if file_sha256(contract) != dataset["contract_sha256"]:
        raise RuntimeError("Contract identity mismatch.")
    development = {int(sid) for sid, r in dataset["records"].items() if r["pool"] == "train"}
    index = pd.read_csv(paths.asset("current_dataset_index", verify=True))
    r_ids = set(index.loc[index["in_R"].eq(True), "id"].astype(int)) & development
    outer, inner = make_nested_folds(sorted(development))
    bound_paths = [contract, paths.asset("current_dataset_manifest", verify=True),
                   paths.asset("current_dataset_index", verify=True),
                   paths.asset("current_qualification_manifest", verify=True),
                   paths.asset("release_R", verify=True), paths.asset("transport_D", verify=True)]
    # Old fitted/scored outputs are inputs to the reproducibility reconciliation.
    for run_id in (OLD_FIT, OLD_VALIDATION):
        bound_paths.extend(p for p in (paths.root / "results/runs" / run_id).rglob("*") if p.is_file())
        bound_paths.extend(p for p in (paths.root / "provenance/runs" / run_id).rglob("*") if p.is_file())
    input_hashes = {p.relative_to(paths.root).as_posix(): file_sha256(p) for p in bound_paths}
    source_paths = [p for p in (paths.root / "src/data3001").rglob("*.py")
                    if p.name != "report.py"]
    source_hashes = {p.relative_to(paths.root).as_posix(): file_sha256(p) for p in source_paths}
    run_id = datetime.now(timezone.utc).strftime("baseline_blend_cv_%Y%m%dT%H%M%S_%fZ")
    config = {**SETTINGS, "fold_assignment_sha256": fold_digest(outer, inner),
              "development_IDs": len(development), "R_visitor_IDs": len(r_ids),
              "contract_sha256": dataset["contract_sha256"],
              "input_sha256": input_hashes, "source_sha256": source_hashes,
              "outer_tag": "round1-cv", "inner_tag": "round1-inner:{outer_fold}",
              "formula": "p=(1-lambda)*B2+lambda*B1; u=(1-lambda)*u2+lambda*u1",
              "final_lambda_rule": "Separate per horizon; selected on all-development base OOF quadratic Brier, then refit bases on all development",
              "bootstrap": "200 paired ID resamples within fixed outer folds; conditional on fitted OOF predictions"}
    run = paths.create_run(run_id, config)
    print("Run:", run_id, flush=True)
    print(f"Development: {len(development)} IDs; {len(r_ids)} R visitors. Final-test access: blocked.", flush=True)
    guard = ReadOnlyInputs(paths.root, run, data_root=paths.data_root)
    sys.addaudithook(guard)
    try:
        save_frame(paths, run["provenance"] / "outer_folds.csv",
                   pd.DataFrame(sorted(outer.items()), columns=["id", "outer_fold"]))
        save_frame(paths, run["provenance"] / "inner_folds.csv", pd.DataFrame([
            {"id": sid, "outer_fold": f, "inner_fold": k}
            for f in sorted(inner) for sid, k in sorted(inner[f].items())]))
        counts, stored_rows = collect_counts(paths, run, dataset, r_ids)
        reconciliation = reconcile_old_counts(paths, dataset, counts)
        print("Exact reconciliation with original training AND validation case counts passed.", flush=True)
        result = evaluate_nested(counts, outer, inner, progress=lambda msg: print(msg, flush=True))
        summary = summarize_scores(result["scores"])
        final_selection, final_grid = final_choices(result["base_terms"])
        final_model = fit_baselines(counts, development)
        tables = {"outer_scores.csv": result["scores"], "outer_summary.csv": summary,
                  "outer_fold_summary.csv": summarize_scores(result["scores"], by_fold=True),
                  "lambda_selection.csv": result["lambda_selection"],
                  "lambda_grid_scores.csv": result["lambda_grid_scores"],
                  "training_support.csv": result["training_support"],
                  "outer_base_terms.parquet": result["base_terms"],
                  "final_lambda_selection.csv": final_selection,
                  "final_lambda_grid_scores.csv": final_grid,
                  "bootstrap_differences.csv": bootstrap_differences(result["scores"])}
        for name, table in tables.items():
            save_frame(paths, run["results"] / name, table)
        save_json(paths, run["results"] / "outer_models.json", result["outer_models"])
        save_json(paths, run["results"] / "final_models.json", serializable_model(final_model))
        # Recheck every actually accessed canonical track, with no final-test read.
        if guard.read_ids != r_ids:
            raise RuntimeError("Actual canonical reads differ from authorized development R visitors.")
        for sid in sorted(guard.read_ids):
            # The reader validates each declared checksum and configured data
            # root, including a legitimate DATA3001_DATA_ROOT override.
            track_path(sid, allow_test=False)
        for name, checksum in {**input_hashes, **source_hashes}.items():
            if file_sha256(paths.root / name) != checksum:
                raise RuntimeError(f"Frozen input or scientific code changed during run: {name}")
        save_json(paths, run["provenance"] / "verification.json", {
            "exact_old_case_reconciliation": reconciliation,
            "canonical_tracks_read": sorted(guard.read_ids), "canonical_track_count": len(guard.read_ids),
            "stored_rows_in_read_tracks": stored_rows,
            "canonical_read_hashes_verified_before_and_after": True,
            "frozen_inputs_unchanged": True, "scientific_source_unchanged_during_run": True,
            "final_test_trajectories_read": 0, "denied_operations": guard.denied,
            "features_or_canonical_rows_modified": False,
            "python": sys.version, "platform": platform.platform(),
            "numpy": np.__version__, "pandas": pd.__version__})
        from data3001.modelling.baselines.report import build_report
        build_report(run["results"], run["provenance"])
        all_outputs = [p for folder in run.values() for p in folder.rglob("*") if p.is_file()]
        save_json(paths, run["provenance"] / "outputs.json", {
            "completed": True, "final_test_access": False,
            "output_sha256": {p.relative_to(paths.root).as_posix(): file_sha256(p) for p in all_outputs},
            "report_source_sha256": file_sha256(Path(__file__).with_name("report.py"))})
        print("\nNested out-of-fold results (lower Brier is better):", flush=True)
        print(summary.to_string(index=False), flush=True)
        print("\nFinal candidate weights (OOF-tuned, bases refitted on all development):", flush=True)
        print(final_selection.to_string(index=False), flush=True)
        print("\nResults:", run["results"], flush=True)
        print("Provenance:", run["provenance"], flush=True)
    finally:
        guard.active = False


if __name__ == "__main__":
    main()
