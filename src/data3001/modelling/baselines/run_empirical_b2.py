"""Independent, development-only standard B2 experiment with sealed outputs."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time

import numpy as np
import pandas as pd

from data3001.paths import file_sha256, project_paths
from data3001.modelling.common.runtime import ReadOnlyInputs, save_frame, save_json, _seal
from data3001.modelling.baselines.empirical_b2 import (
    EXIT, HORIZONS, KEYS, ROW, TOLERANCE, bootstrap_scores, evaluate_b2,
    fit_b2, summarise, validate_counts,
)
from data3001.modelling.baselines.empirical_b2_report import write_report
from data3001.modelling.common.qualified_count_inputs import (
    ExperimentGuard, run_input_paths, read_frame, sealed_receipt, verify_file,
    counts_from_labels, load_inputs,
)


def validate_config(config):
    fixed = {"experiment": "empirical_b2", "model": "B2", "plan_version": "E2",
             "dataset_release": "per-drifter-cleaned-20261017-v7",
             "grid_degrees": 1, "target": "stopped", "scenario": "pooled",
             "departure_seasons": "annual_pooled", "origin_population": "R",
             "horizons_days": [7, 30], "tolerance_hours": 0,
             "predictors": ["origin_cell_1"], "weighting": "equal_eligible_pairs",
             "primary_metric": "standard_multiclass_brier",
             "unsupported_score": "missing_report_availability", "smoothing": False,
             "outer_folds": 5, "inner_search": False, "bootstrap_replicates": 200,
             "bootstrap_seed": 20261029, "mass_tolerance": TOLERANCE,
             "compute_cap_seconds": 1800, "final_test_access": False}
    if any(config.get(k) != value for k, value in fixed.items()):
        raise ValueError("Configuration differs from approved E2 scientific settings")
    if config.get("source_assets") != ["english_contract", "state_index", "release_R",
                                      "transport_D", "land_mask_intermediate"]:
        raise ValueError("Unapproved source assets")



def audit_numeric_results(counts, folds, origins, destinations, models, scores):
    """Recompute counts with Python counters and Brier via squared vector errors."""
    max_probability_error = 0.
    for role, model in models.items():
        expected = Counter()
        training_ids = set(model.training_ids)
        for row in counts.itertuples(index=False):
            if row.id in training_ids:
                expected[(row.horizon_days, row.origin_cell_1, row.destination_cell_1)] += row.pair_count
        actual = {(r.horizon_days, r.origin_cell_1, r.destination_cell_1): r
                  for r in model.transitions.itertuples(index=False)}
        if set(expected) != set(actual):
            raise AssertionError("Matrix support differs from direct counter: " + role)
        totals = Counter()
        for (h, origin, dest), count in expected.items():
            totals[(h, origin)] += count
        for key, count in expected.items():
            if actual[key].pair_count != count:
                raise AssertionError("Matrix count mismatch")
            error = abs(actual[key].probability - count / totals[key[:2]])
            max_probability_error = max(max_probability_error, error)
        for r in model.support.itertuples(index=False):
            if r.training_pair_count != totals[(r.horizon_days, r.origin_cell_1)]:
                raise AssertionError("Row support does not match count totals")
    pd.testing.assert_frame_equal(scores[KEYS + ["pair_count"]].sort_values(KEYS).reset_index(drop=True),
                                  counts.sort_values(KEYS).reset_index(drop=True), check_exact=True)
    expected_fold = folds.set_index("id").outer_fold
    if not scores.outer_fold.eq(scores.id.map(expected_fold)).all():
        raise AssertionError("Held-out case assigned to wrong fold")
    index = {int(c): n for n, c in enumerate([*destinations.cell, EXIT])}
    maximum_score_error = 0.
    for (fold, h, origin), group in scores.groupby(["outer_fold", *ROW]):
        model = models[f"outer_{fold}"]
        if set(group.id) & set(model.training_ids):
            raise AssertionError("Held-out ID contributes to fitted model")
        p = model.transitions.loc[model.transitions.horizon_days.eq(h) & model.transitions.origin_cell_1.eq(origin)]
        if p.empty:
            if not group.brier.isna().all() or not group.status.eq("unsupported_origin").all():
                raise AssertionError("Unsupported cases have numerical scores")
            continue
        vector = np.zeros(len(index))
        for r in p.itertuples(index=False):
            vector[index[r.destination_cell_1]] = r.probability
        for truth, cases in group.groupby("destination_cell_1"):
            one_hot = np.zeros(len(index)); one_hot[index[truth]] = 1.
            reference = float(np.square(vector - one_hot).sum())
            maximum_score_error = max(maximum_score_error, float((cases.brier - reference).abs().max()))
    if max_probability_error > TOLERANCE or maximum_score_error > TOLERANCE:
        raise AssertionError("Independent numerical audit exceeds tolerance")
    return {"matrix_count_reconciliation": True, "heldout_cases_reconciled": True,
            "max_probability_error": max_probability_error, "max_brier_error": maximum_score_error,
            "whole_ID_leakage": False, "matrix_count": len(models) * len(HORIZONS)}


def experiment_source_hashes(paths):
    files = {Path(module.__file__).resolve() for name, module in list(sys.modules.items())
             if name.startswith("data3001") and getattr(module, "__file__", None)
             and str(module.__file__).endswith(".py")}
    # A `python -m` entry point is registered as __main__, not its package name.
    files.add(Path(__file__).resolve())
    return {p.relative_to(paths.root).as_posix(): file_sha256(p) for p in sorted(files)}


def execute(paths, config, config_path, run_id, replay_of=None):
    start = time.monotonic()
    validate_config(config)
    if not run_id.startswith("empirical_b2_"):
        raise ValueError("Independent B2 runs require their own run-ID namespace")
    counts_path, folds_path = run_input_paths(paths, config)
    allowed = [counts_path, folds_path, counts_path.parent / "source_ID_summary.csv"]
    allowed += list((counts_path.parent / "release_labels").glob("*.parquet"))
    for p in [counts_path, folds_path]:
        allowed += [paths.root / "provenance/runs" / p.parent.name / "outputs.json",
                    paths.root / "provenance/runs" / p.parent.name / "run.json"]
    allowed += [paths.asset(a) for a in config["source_assets"]]
    if replay_of:
        if not replay_of.startswith("empirical_b2_") or Path(replay_of).name != replay_of:
            raise ValueError("Replay comparison must name a prior independent B2 run")
        replay_root = paths.root / "results/runs" / replay_of
        allowed += list(replay_root.rglob("*.parquet")) + list(replay_root.rglob("*.csv"))
        allowed += [paths.root / "provenance/runs" / replay_of / "outputs.json"]
    run = paths.create_run(run_id, config)
    guard = ExperimentGuard(paths, run, allowed)
    sys.addaudithook(guard)
    try:
        counts, folds, origins, destinations, reasons, inventory = load_inputs(paths, config)
        inventory[config_path.relative_to(paths.root).as_posix()] = file_sha256(config_path)
        code_hashes = experiment_source_hashes(paths)
        save_json(paths, run["results"] / "config.json", config)
        save_json(paths, run["provenance"] / "input_inventory.json", inventory)
        save_json(paths, run["provenance"] / "source_sha256.json", code_hashes)
        git_state = subprocess.run(["git", "status", "--porcelain"], cwd=paths.root, text=True, capture_output=True, check=True).stdout
        git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=paths.root, text=True, capture_output=True, check=True).stdout.strip()
        save_json(paths, run["provenance"] / "environment.json", {
            "python": sys.version, "platform": platform.platform(), "git_head": git_head,
            "git_worktree_status": git_state, "packages": {n: importlib.metadata.version(n) for n in ["numpy", "pandas", "pyarrow", "shapely"]}})
        for name, table in [("counts_by_id.parquet", counts), ("folds.csv", folds),
                            ("source_index.csv", origins), ("destination_cells.csv", destinations),
                            ("qualification_reasons_by_id.csv", reasons)]:
            save_frame(paths, run["results"] / name, table)
        save_frame(paths, run["results"] / "destination_index.csv",
                   pd.DataFrame({"destination_cell_1": [*destinations.cell, EXIT],
                                 "state_kind": ["D_cell"] * len(destinations) + ["first_exit_E"]}))
        models, all_scores, supports, forecasts = {}, [], [], []
        fitting_ids = {}
        for fold in range(5):
            role = f"outer_{fold}"
            train_ids = folds.loc[folds.outer_fold.ne(fold), "id"].tolist()
            heldout_ids = folds.loc[folds.outer_fold.eq(fold), "id"].tolist()
            model = fit_b2(counts, train_ids, origins.cell, [*destinations.cell, EXIT])
            models[role] = model; fitting_ids[role] = train_ids
            for h in HORIZONS:
                save_frame(paths, run["results"] / "matrices" / f"{role}_{h}d.parquet",
                           model.transitions.loc[model.transitions.horizon_days.eq(h)])
            forecasts.append(model.transitions.assign(outer_fold=fold, role=role))
            supports.append(model.support.assign(outer_fold=fold, role=role))
            all_scores.append(evaluate_b2(model, counts, heldout_ids).assign(outer_fold=fold, role=role))
            print(f"Finished fold {fold}: {len(train_ids)} fitting IDs, {len(heldout_ids)} held-out IDs", flush=True)
        scores = pd.concat(all_scores, ignore_index=True).sort_values(["outer_fold", *KEYS]).reset_index(drop=True)
        candidate = fit_b2(counts, folds.id.tolist(), origins.cell, [*destinations.cell, EXIT])
        role = "all_development_candidate"
        models[role] = candidate; fitting_ids[role] = folds.id.tolist()
        supports.append(candidate.support.assign(outer_fold=-1, role=role))
        for h in HORIZONS:
            save_frame(paths, run["results"] / "matrices" / f"{role}_{h}d.parquet",
                       candidate.transitions.loc[candidate.transitions.horizon_days.eq(h)])
        summary = summarise(scores)
        draws, intervals = bootstrap_scores(scores, folds.id.tolist(), config["bootstrap_replicates"], config["bootstrap_seed"])
        support = pd.concat(supports, ignore_index=True)
        for name, table in [("heldout_predictions.parquet", pd.concat(forecasts, ignore_index=True)),
                            ("heldout_scores.parquet", scores), ("row_support.csv", support),
                            ("summary.csv", summary), ("cell_summary.csv", summarise(scores, ROW)),
                            ("fold_summary.csv", summarise(scores, ["outer_fold", "horizon_days"])),
                            ("bootstrap_draws.csv", draws), ("bootstrap_intervals.csv", intervals)]:
            save_frame(paths, run["results"] / name, table)
        save_json(paths, run["results"] / "fitting_ids.json", fitting_ids)
        verification = audit_numeric_results(counts, folds, origins, destinations, models, scores)
        write_report(paths, run, config, summary, intervals, candidate, origins, destinations, verification)
        if replay_of:
            receipt = json.loads((paths.root / "provenance/runs" / replay_of / "outputs.json").read_text())
            if receipt.get("completed") is not True or receipt.get("final_test_access") is not False:
                raise ValueError("Replay source is not a completed development run")
            compared = []
            for p in sorted(run["results"].rglob("*")):
                if p.suffix not in (".parquet", ".csv"):
                    continue
                previous = replay_root / p.relative_to(run["results"])
                verify_file(paths, previous, receipt["output_sha256"], {})
                pd.testing.assert_frame_equal(read_frame(p), read_frame(previous), check_exact=False, rtol=0, atol=TOLERANCE)
                compared.append(p.relative_to(run["results"]).as_posix())
            verification["replay"] = {"reference_run": replay_of, "tolerance": TOLERANCE, "tables_compared": compared, "passed": True}
        for relative, digest in inventory.items():
            if file_sha256(paths.root / relative) != digest:
                raise AssertionError("Input changed during experiment: " + relative)
        for relative, digest in code_hashes.items():
            if file_sha256(paths.root / relative) != digest:
                raise AssertionError("Code changed during experiment: " + relative)
        verification.update({"elapsed_seconds": time.monotonic() - start,
                             "max_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                             "development_IDs": len(folds), "qualified_label_counts_reconciled": True,
                             "canonical_trajectory_files_read": len(guard.read_ids),
                             "final_test_trajectories_read": 0, "denied_operations": guard.denied,
                             "input_hashes_unchanged": True, "code_hashes_unchanged": True,
                             "historical_model_outputs_used": False,
                             "input_files_opened": sorted(p.relative_to(paths.root).as_posix() for p in guard.opened_inputs)})
        _seal(paths, run, verification)
        print(json.dumps({"run_id": run_id, "elapsed_seconds": verification["elapsed_seconds"],
                          "report": str(run["results"] / "REPORT.md"), "summary": summary.to_dict("records")}))
        return run
    except Exception as error:
        save_json(paths, run["provenance"] / "FAILED.json", {"type": type(error).__name__, "message": str(error), "denied_operations": guard.denied})
        raise
    finally:
        guard.active = False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/empirical_b2.json")
    parser.add_argument("--run-id")
    parser.add_argument("--replay-of", help="Verify numerical replay against a new empirical_b2 run")
    args = parser.parse_args()
    paths = project_paths()
    config_path = paths._resolve(args.config)
    config = json.loads(config_path.read_text())
    validate_config(config)
    run_id = args.run_id or "empirical_b2_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    def timeout(signum, frame):
        raise TimeoutError("Approved 30-minute complete-run cap reached")
    previous = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(config["compute_cap_seconds"])
    try:
        execute(paths, config, config_path, run_id, args.replay_of)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


if __name__ == "__main__":
    main()
