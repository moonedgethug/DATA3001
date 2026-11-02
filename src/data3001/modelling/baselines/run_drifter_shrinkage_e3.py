"""Locked E3 v2 experiment with guarded inputs, bounded preflight and replay."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import platform
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import save_frame, save_json, _seal
from data3001.modelling.common.qualified_count_inputs import ExperimentGuard, load_inputs, read_frame, run_input_paths, KEYS, EXIT
from data3001.modelling.baselines.drifter_shrinkage_e3 import (
    MODELS, METRICS, IDENTITY, fit_bases, candidate_units, select_parameters, forecasts,
    diagnostic_scores, score_units, summarize_units, attach_primary_weights, metric_columns,
    uncertainty, region_changes,
)
from data3001.modelling.baselines.drifter_shrinkage_e3_audit import (
    rebuild, audit_candidates, independent_audit, audit_uncertainty, verify_sealed_run, frozen_regressions,
)
from data3001.modelling.baselines.drifter_shrinkage_e3_report import write_report

_CONFIG_LITERAL = r'''{
  "experiment": "drifter_shrinkage_e3",
  "plan_version": "E3_v2",
  "approved_plan": "docs/drifter_shrinkage_e3_plan.md",
  "approved_plan_sha256": "f7684a0fde10d252ad24057f8d380f55231b7889101784d657ac12584aa223df",
  "dataset_release": "per-drifter-cleaned-20261017-v7",
  "contract_sha256": "6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446",
  "grid_degrees": 1,
  "target": "stopped",
  "scenario": "pooled",
  "departure_seasons": "annual_pooled",
  "origin_population": "R",
  "horizons_days": [
    7,
    30
  ],
  "tolerance_hours": 0,
  "predictors": [
    "origin_cell_1"
  ],
  "weighting": "equal_eligible_pairs",
  "weighting_field_role": "qualified_raw_cache_provenance_only",
  "training_weighting": {
    "B2": "equal_pairs",
    "EqualID": "equal_ID_within_origin_horizon",
    "Fixed": "raw_B2_and_raw_B1"
  },
  "primary_weighting": "equal_cell_then_equal_ID_then_equal_eligible_time",
  "secondary_weighting": "equal_eligible_pairs",
  "models": [
    "B2",
    "EqualID",
    "Fixed"
  ],
  "gamma": 1,
  "parameter_grid": [
    0,
    0.05,
    0.1,
    0.15,
    0.2,
    0.25,
    0.3,
    0.35,
    0.4,
    0.45,
    0.5,
    0.55,
    0.6,
    0.65,
    0.7,
    0.75,
    0.8,
    0.85,
    0.9,
    0.95,
    1
  ],
  "primary_metric": "standard_multiclass_brier",
  "selector": "new_target_Brier_only_then_smaller_a",
  "unsupported_score": "common_B2_mask_missing",
  "outer_folds": 5,
  "inner_folds": 4,
  "bootstrap_replicates": 5000,
  "bootstrap_seed": 20261030,
  "bootstrap_distribution": "Exp(1)_whole_ID",
  "bootstrap_generator": "PCG64",
  "brier_adjusted_upper_quantile": 0.9875,
  "region_level": 0.9,
  "mass_tolerance": 1e-12,
  "tie_tolerance": 1e-12,
  "compute_cap_seconds": 1800,
  "preflight_cap_seconds": 300,
  "final_test_access": false,
  "counts_path": "results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet",
  "folds_path": "results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv",
  "frozen_s1_run": "empirical_b2_20261029T121555_976173Z",
  "frozen_e1_run": "adaptive_b2_b1_20261030T044950_931787Z",
  "frozen_e2_run": "b2_b1_e2_20261030T060621_291294Z",
  "source_assets": [
    "english_contract",
    "state_index",
    "release_R",
    "transport_D",
    "land_mask_intermediate"
  ]
}'''


def expected_config():
    return json.loads(_CONFIG_LITERAL)


def validate_config(config):
    if config != expected_config():
        raise ValueError("Configuration differs from approved E3 v2")


def source_hashes(paths):
    files = {Path(m.__file__).resolve() for name, m in list(sys.modules.items())
             if name.startswith("data3001") and getattr(m, "__file__", None) and str(m.__file__).endswith(".py")}
    files.add(Path(__file__).resolve())
    return {p.relative_to(paths.root).as_posix(): file_sha256(p) for p in sorted(files)}


def matrix_frame(base, vectors):
    return pd.concat([pd.DataFrame(dict(horizon_days=h, origin_cell_1=o,
                                        destination_cell_1=base.states[p > 0], probability=p[p > 0]))
                      for (h, o), p in sorted(vectors.items())], ignore_index=True)


def execute(paths, config, config_path, run_id, preflight=False, preflight_run=None, replay_of=None):
    start = time.monotonic()
    validate_config(config)
    prefix = "drifter_shrinkage_e3_preflight_" if preflight else "drifter_shrinkage_e3_"
    if not run_id.startswith(prefix) or (not preflight and "preflight" in run_id):
        raise ValueError("Invalid E3 run namespace")
    if not preflight and not preflight_run:
        raise ValueError("Successful unchanged-source preflight required")
    if file_sha256(paths._resolve(config["approved_plan"])) != config["approved_plan_sha256"]:
        raise ValueError("Approved plan changed")
    counts_path, folds_path = run_input_paths(paths, config)
    allowed = [counts_path, folds_path, counts_path.parent/"source_ID_summary.csv",
               *list((counts_path.parent/"release_labels").glob("*.parquet"))]
    for p in (counts_path, folds_path):
        allowed.extend(paths.root/"provenance/runs"/p.parent.name/name for name in ("outputs.json", "run.json"))
    allowed.extend(paths.asset(a) for a in config["source_assets"])
    run = paths.create_run(run_id, {**config, "execution_mode": "preflight" if preflight else "full"})
    guard = ExperimentGuard(paths, run, allowed)
    sys.addaudithook(guard)
    try:
        counts, folds, origins, destinations, reasons, inventory = load_inputs(paths, config)
        inventory[config_path.relative_to(paths.root).as_posix()] = file_sha256(config_path)
        code = source_hashes(paths)
        if not preflight:
            if not preflight_run.startswith("drifter_shrinkage_e3_preflight_"):
                raise ValueError("Invalid preflight namespace")
            verify_sealed_run(paths, preflight_run, guard)
            previous = paths.root/"provenance/runs"/preflight_run
            receipt = json.loads((previous/"verification.json").read_text())
            assert receipt["preflight_only"] and receipt["projected_complete_seconds"] < config["compute_cap_seconds"]
            assert json.loads((previous/"source_sha256.json").read_text()) == code
            assert json.loads((previous/"input_inventory.json").read_text()) == inventory
        save_json(paths, run["results"]/"config.json", config)
        for name, value in [("input_inventory.json", inventory), ("source_sha256.json", code)]:
            save_json(paths, run["provenance"]/name, value)
        paths.publish(run["provenance"]/"approved_plan.md", lambda out: out.write(paths._resolve(config["approved_plan"]).read_bytes()))
        save_json(paths, run["provenance"]/"environment.json", dict(
            python=sys.version, platform=platform.platform(),
            git_head=subprocess.run(["git", "rev-parse", "HEAD"], cwd=paths.root, text=True, capture_output=True, check=True).stdout.strip(),
            git_status=subprocess.run(["git", "status", "--porcelain"], cwd=paths.root, text=True, capture_output=True, check=True).stdout,
            packages={n: importlib.metadata.version(n) for n in ("numpy", "pandas", "pyarrow", "shapely", "matplotlib")}))
        for name, frame in [("counts_by_id.parquet", counts), ("folds.csv", folds),
                            ("source_index.csv", origins), ("destination_cells.csv", destinations),
                            ("qualification_reasons_by_id.csv", reasons)]:
            save_frame(paths, run["results"]/name, frame)
        states = [*destinations.cell, EXIT]
        save_frame(paths, run["results"]/"destination_index.csv",
                   pd.DataFrame(dict(destination_cell_1=states, state_kind=["D_cell"]*len(destinations)+["first_exit_E"])))
        bases, roles, predictions = {}, {}, {}
        candidates, selections, searches, score_parts, supports, boundaries, changes = [], [], [], [], [], [], []

        def fit(role, train, heldout, outer=-1, inner=-1):
            base = fit_bases(counts, train, origins.cell, states)
            bases[role] = base
            roles[role] = dict(training_ids=list(map(int, train)), evaluation_ids=list(map(int, heldout)),
                               outer_fold=outer, inner_fold=inner)
            references = []
            for h in (7, 30):
                active = base.references[h] > 0
                references.append(pd.DataFrame(dict(horizon_days=h, destination_cell_1=base.states[active],
                                                     probability=base.references[h][active])))
            for name, frame in [("b2.parquet", base.b2.transitions), ("b1.parquet", pd.concat(references, ignore_index=True)),
                                ("support.csv", base.b2.support), ("equal.parquet", matrix_frame(base, base.equal_rows)),
                                ("contributions.parquet", base.contributions), ("local_distributions.parquet", base.local_distributions)]:
                save_frame(paths, run["results"]/"bases"/f"{role}_{name}", frame)
            return base

        def tune(base, role, target, ids):
            table = candidate_units(base, counts, ids).assign(fit_role=role, selection_role=target)
            candidates.append(table)
            return table

        def select(parts, role):
            chosen, pool = select_parameters(pd.concat(parts, ignore_index=True))
            chosen["role"], pool["role"] = role, role
            selections.append(chosen); searches.append(pool)
            return chosen

        def export(base, role, chosen, ids=None, outer=-1):
            predictions[role] = {}
            for model in MODELS:
                vectors, support = forecasts(base, model, chosen)
                predictions[role][model] = vectors
                supports.append(support.assign(role=role, outer_fold=outer))
                save_frame(paths, run["results"]/"matrices"/f"{role}_{model}.parquet", matrix_frame(base, vectors))
                if ids is not None:
                    scores, bounds = diagnostic_scores(base, vectors, counts, ids, model)
                    score_parts.append(scores.assign(role=role, outer_fold=outer))
                    boundaries.append(bounds.assign(role=role, outer_fold=outer))
            if ids is not None:
                changes.append(region_changes(base, predictions[role], counts, ids).assign(role=role, outer_fold=outer))

        if preflight:
            role = "outer_0_inner_1"
            train = folds.loc[~folds.outer_fold.isin([0, 1]), "id"].tolist()
            ids = folds.loc[folds.outer_fold.eq(1), "id"].tolist()
            measured = time.monotonic()
            base = fit(role, train, ids, 0, 1)
            units = tune(base, role, "outer_0", ids)
            summaries = summarize_units(units, ("fit_role", *IDENTITY))
            reconstructed = rebuild(counts, folds, roles, base.states)
            audit = audit_candidates(counts, roles, base.states, reconstructed, units, summaries)
            role_seconds = time.monotonic()-measured
            projected = 25*role_seconds + 480 + (time.monotonic()-start-role_seconds)
            if projected >= config["compute_cap_seconds"]:
                raise TimeoutError("Projected execution exceeds approved cap")
            for name, table in [("candidate_id_cells.parquet", units), ("candidate_scores.csv", summaries)]:
                save_frame(paths, run["results"]/name, table)
            save_json(paths, run["results"]/"fit_roles.json", roles)
            verification = dict(preflight_only=True, role_seconds=role_seconds, projected_complete_seconds=projected,
                                candidate_audit=audit, elapsed_seconds=time.monotonic()-start,
                                canonical_trajectory_files_read=len(guard.read_ids), final_test_trajectories_read=0,
                                denied_operations=guard.denied)
            for relative, digest in {**inventory, **code}.items():
                assert file_sha256(paths.root/relative) == digest
            _seal(paths, run, verification)
            print(json.dumps({"run_id": run_id, **verification}), flush=True)
            return run

        for outer in range(5):
            role, parts = f"outer_{outer}", []
            for inner in range(5):
                if inner == outer:
                    continue
                train = folds.loc[~folds.outer_fold.isin([outer, inner]), "id"].tolist()
                ids = folds.loc[folds.outer_fold.eq(inner), "id"].tolist()
                fit_role = f"outer_{outer}_inner_{inner}"
                base = fit(fit_role, train, ids, outer, inner)
                parts.append(tune(base, fit_role, role, ids))
            chosen = select(parts, role)
            train = folds.loc[folds.outer_fold.ne(outer), "id"].tolist()
            ids = folds.loc[folds.outer_fold.eq(outer), "id"].tolist()
            base = fit(role, train, ids, outer)
            export(base, role, chosen, ids, outer)
            print(f"Completed outer {outer}: "+chosen[["horizon_days", "parameter_a"]].to_json(orient="records"), flush=True)
        scores = attach_primary_weights(pd.concat(score_parts, ignore_index=True).sort_values(["outer_fold", "model", *KEYS]).reset_index(drop=True))
        units = score_units(scores)
        for name, table in [("heldout_scores.parquet", scores), ("heldout_id_cells.parquet", units),
                            ("selected_outer_parameters.csv", pd.concat(selections, ignore_index=True))]:
            save_frame(paths, run["results"]/name, table)
        frozen_files = [run["results"]/n for n in ("heldout_scores.parquet", "heldout_id_cells.parquet", "selected_outer_parameters.csv")]
        frozen_files += sorted((run["results"]/"matrices").glob("*.parquet"))
        frozen = {p.relative_to(paths.root).as_posix(): file_sha256(p) for p in frozen_files}
        save_json(paths, run["provenance"]/"outer_freeze.json", dict(phase="before_all_development_tuning", sha256=frozen))
        full_parts = [tune(bases[f"outer_{k}"], f"outer_{k}", "all_development_candidate", roles[f"outer_{k}"]["evaluation_ids"]) for k in range(5)]
        final = "all_development_candidate"
        chosen = select(full_parts, final)
        base = fit(final, folds.id.tolist(), [])
        export(base, final, chosen)
        for relative, digest in frozen.items():
            assert file_sha256(paths.root/relative) == digest
        metrics = metric_columns(scores)
        summary = summarize_units(units, metrics=metrics)
        secondary = summarize_units(units, metrics=metrics, pair_weighted=True)
        print("Computing 5,000 paired whole-ID positive multiplier resamples", flush=True)
        draws, intervals, differences, decisions, draw_identity = uncertainty(units, folds.id.tolist(), config["bootstrap_replicates"], config["bootstrap_seed"])
        all_candidates = pd.concat(candidates, ignore_index=True)
        all_selected = pd.concat(selections, ignore_index=True)
        all_support = pd.concat(supports, ignore_index=True)
        change_units = pd.concat(changes, ignore_index=True)
        change_summary = summarize_units(change_units, ("horizon_days", "reference", "part"), ("cells", "hit", "probability_mass", "exit_included"))
        tables = {
            "row_support.csv": all_support, "summary.csv": summary, "pair_weighted_summary.csv": secondary,
            "cell_summary.csv": summarize_units(units, ("horizon_days", "model", "origin_cell_1"), metrics),
            "fold_summary.csv": summarize_units(units, ("outer_fold", "horizon_days", "model"), metrics),
            "candidate_id_cells.parquet": all_candidates,
            "candidate_scores.csv": summarize_units(all_candidates, ("fit_role", *IDENTITY)),
            "selected_parameters.csv": all_selected, "parameter_search.csv": pd.concat(searches, ignore_index=True),
            "region_changes.csv": change_units, "region_change_summary.csv": change_summary,
            "budget_boundaries.parquet": pd.concat(boundaries, ignore_index=True),
            "bootstrap_draws.csv": draws, "bootstrap_intervals.csv": intervals,
            "paired_differences.csv": differences, "decisions.csv": decisions,
        }
        for name, table in tables.items():
            save_frame(paths, run["results"]/name, table)
        save_json(paths, run["results"]/"fit_roles.json", roles)
        save_json(paths, run["results"]/"multiplier_identity.json", draw_identity)
        save_json(paths, run["results"]/"weighting_definitions.json", dict(
            primary="within-ID time mean, then equal ID mean per cell, then equal cell mean",
            primary_group_weight="compressed destination multiplicity divided by local evaluation count, ID count and cell count",
            unit_metric="within-ID unconditional metric numerator; __mass is the corresponding eligible metric mass",
            conditional_diagnostics="same primary weights, conditioned on nonmissing metric outcomes",
            source_weighting_field="raw count-cache provenance, not E3 evaluation weights",
            historical_pair_scores="secondary only; cannot select parameters or decide E3 acceptance"))
        print("Auditing every fitting role, candidate, outer score, summary and resample", flush=True)
        verification = independent_audit(paths, run, counts, folds, roles, base.states)
        verification["uncertainty"] = audit_uncertainty(run["results"], folds, config["bootstrap_replicates"], config["bootstrap_seed"])
        verification["frozen_regressions"] = frozen_regressions(paths, run, guard, config, bases)
        if replay_of:
            if not replay_of.startswith("drifter_shrinkage_e3_") or "preflight" in replay_of:
                raise ValueError("Invalid replay reference")
            verify_sealed_run(paths, replay_of, guard)
            previous = paths.root/"results/runs"/replay_of
            compared = []
            for p in sorted(run["results"].rglob("*")):
                if p.suffix in (".csv", ".parquet"):
                    pd.testing.assert_frame_equal(read_frame(p), read_frame(previous/p.relative_to(run["results"])),
                                                  check_exact=False, rtol=0, atol=1e-12)
                    compared.append(p.relative_to(run["results"]).as_posix())
            assert json.loads((previous/"multiplier_identity.json").read_text()) == draw_identity
            verification["replay"] = dict(passed=True, reference_run=replay_of, numerical_tables_compared=compared)
        write_report(paths, run, summary, secondary, differences, decisions, all_selected, base, predictions[final], all_support, verification)
        for relative, digest in {**inventory, **code, **frozen}.items():
            assert file_sha256(paths.root/relative) == digest, relative
        verification.update(preflight_only=False, preflight_run=preflight_run, elapsed_seconds=time.monotonic()-start,
                            max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                            development_IDs=len(folds), canonical_trajectory_files_read=len(guard.read_ids),
                            final_test_trajectories_read=0, denied_operations=guard.denied,
                            input_hashes_unchanged=True, code_hashes_unchanged=True,
                            outer_predictions_unchanged_after_all_development_tuning=True,
                            historical_outputs_used_for_fitting=False,
                            input_files_opened=sorted(p.relative_to(paths.root).as_posix() for p in guard.opened_inputs))
        _seal(paths, run, verification)
        print(json.dumps(dict(run_id=run_id, elapsed_seconds=verification["elapsed_seconds"],
                              decisions=decisions.to_dict("records"))), flush=True)
        return run
    except Exception as error:
        save_json(paths, run["provenance"]/"FAILED.json",
                  dict(type=type(error).__name__, message=str(error), denied_operations=guard.denied))
        raise
    finally:
        guard.active = False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/drifter_shrinkage_e3.json")
    parser.add_argument("--run-id")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--preflight-run")
    parser.add_argument("--replay-of")
    args = parser.parse_args()
    paths = project_paths(); config_path = paths._resolve(args.config)
    config = json.loads(config_path.read_text()); validate_config(config)
    if args.preflight and (args.preflight_run or args.replay_of):
        raise ValueError("Preflight cannot replay or use a prior preflight")
    run_id = args.run_id or ("drifter_shrinkage_e3_preflight_" if args.preflight else "drifter_shrinkage_e3_")+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    def timeout(signum, frame):
        raise TimeoutError("Approved E3 execution cap reached")
    previous = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(config["preflight_cap_seconds"] if args.preflight else config["compute_cap_seconds"])
    try:
        execute(paths, config, config_path, run_id, args.preflight, args.preflight_run, args.replay_of)
    finally:
        signal.alarm(0); signal.signal(signal.SIGALRM, previous)


if __name__ == "__main__":
    main()

