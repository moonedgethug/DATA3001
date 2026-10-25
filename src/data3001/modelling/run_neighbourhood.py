"""Guarded, no-visualisation pooled neighbourhood baseline experiment.

Prepare source-keyed coordinates once:
  python -B -m data3001.modelling.run_neighbourhood --prepare-only
Fit/evaluate from that sealed preparation:
  python -B -m data3001.modelling.run_neighbourhood --input-run <preparation-run>
"""
import argparse
from datetime import datetime, timezone
import json
from importlib.metadata import version
from pathlib import Path
import platform
import resource
import sys
import time

import numpy as np
import pandas as pd
import pyproj
import shapely as sh
from shapely.geometry import shape

from data3001.dataset import manifest, track_path
from data3001.modelling.blend import select_lambdas
from data3001.modelling.cv import KEYS, summarize_scores
from data3001.modelling.experiment import fold_digest, make_nested_folds
from data3001.modelling.neighbourhood import EndpointMapper, net_displacements
from data3001.modelling.neighbourhood_cv import (
    FAMILIES, evaluate_local_nested, fit_local_bases, pair_counts, serialize_local_model,
)
from data3001.modelling.run_blend_cv import ReadOnlyInputs, save_frame, save_json
from data3001.paths import file_sha256, project_paths
from data3001.preprocessing.prep_core import cells

PARENT = "baseline_blend_cv_20261022T160806_056571Z"
CONTRACT_SHA = "6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446"
INTEGRATION = {"exact_limit": 2_000_000, "levels": (8, 32, 128, 512),
               "tolerance": .0005, "chunk_size": 200_000}


def scientific_environment():
    return {"packages": {name: version(name) for name in ("numpy", "pandas", "pyarrow", "shapely", "pyproj")},
            "geos": sh.geos_version_string, "proj": pyproj.proj_version_str,
            "python": sys.version, "platform": platform.platform(), "numeric_workers": 4}


def validate_parent_receipt(receipt):
    if (receipt.get("completed") is not True or receipt.get("final_test_access") is not False
            or not isinstance(receipt.get("output_sha256"), dict)):
        raise ValueError("A complete, sealed development-only input run is required.")


def verified_run(paths, run_id):
    if Path(run_id).name != run_id or not run_id or run_id in (".", ".."):
        raise ValueError("Unsafe input run name.")
    receipt_path = paths.root / "provenance/runs" / run_id / "outputs.json"
    receipt = json.loads(receipt_path.read_text())
    validate_parent_receipt(receipt)
    for relative, checksum in receipt["output_sha256"].items():
        rel = Path(relative)
        if rel.is_absolute() or ".." in rel.parts or not rel.parts[:2] in (
                ("results", "runs"), ("provenance", "runs")) or rel.parts[2] != run_id:
            raise ValueError("Input receipt contains an unexpected path.")
        if file_sha256(paths.root / rel) != checksum:
            raise ValueError("Input run artifact checksum mismatch: " + relative)
    return receipt_path


def join_coordinates(ledger, track):
    eligible = ledger.loc[ledger.reason_code.eq(0)].copy()
    if track.source_obs.duplicated().any() or eligible.duplicated(
            ["id", "origin_source_obs", "horizon_days"]).any():
        raise ValueError("Ambiguous source keys.")
    if eligible.empty:
        return pd.DataFrame()
    source = track.set_index("source_obs")  # uniqueness checked above
    try:
        origin = source.loc[eligible.origin_source_obs]
        end = source.loc[eligible.endpoint_source_obs]
    except KeyError as error:
        raise ValueError("Eligible pair has an absent canonical source record.") from error
    ot, et = origin.time.to_numpy(float), end.time.to_numpy(float)
    if (not np.array_equal(et-ot, eligible.horizon_days.to_numpy()*86400)
            or not np.array_equal(origin.id.to_numpy(), eligible.id.to_numpy())
            or not np.array_equal(end.id.to_numpy(), eligible.id.to_numpy())
            or not np.array_equal(origin.cell_1.to_numpy(), eligible.origin_cell_1.to_numpy())):
        raise ValueError("Canonical pair identity, duration, or origin-cell mismatch.")
    known = eligible.destination_cell_1.to_numpy() >= 0
    if not np.array_equal(end.cell_1.to_numpy()[known], eligible.destination_cell_1.to_numpy()[known]):
        raise ValueError("Canonical destination-cell mismatch.")
    frame = eligible[["id", "horizon_days", "origin_cell_1", "destination_cell_1",
                      "origin_source_obs", "endpoint_source_obs"]].reset_index(drop=True)
    frame["origin_epoch"], frame["endpoint_epoch"] = ot, et
    frame["origin_lon"], frame["origin_lat"] = origin.lon_normalized.to_numpy(float), origin.lat.to_numpy(float)
    frame["endpoint_lon"], frame["endpoint_lat"] = end.lon_normalized.to_numpy(float), end.lat.to_numpy(float)
    coords = frame[["origin_lon", "origin_lat", "endpoint_lon", "endpoint_lat"]].to_numpy()
    if (not np.isfinite(coords).all() or not np.array_equal(
            cells(frame.origin_lon.to_numpy(), frame.origin_lat.to_numpy()), frame.origin_cell_1)):
        raise ValueError("Invalid source coordinates or frozen grid mismatch.")
    return frame


def _identity(paths):
    data = manifest()
    contract = paths.asset("english_contract", verify=True)
    if data["version"] != "per-drifter-cleaned-20261017-v7" or file_sha256(contract) != CONTRACT_SHA:
        raise ValueError("Dataset/contract identity changed.")
    inputs = [contract] + [paths.asset(k, verify=True) for k in (
        "current_dataset_manifest", "current_dataset_index", "current_qualification_manifest",
        "release_R", "transport_D", "land_mask_high")]
    return data, {p.relative_to(paths.root).as_posix(): file_sha256(p) for p in inputs}


def _source_hashes(paths):
    return {p.relative_to(paths.root).as_posix(): file_sha256(p)
            for p in (paths.root/"src/data3001").rglob("*.py")}


def _seal(paths, run, verification):
    save_json(paths, run["provenance"]/"verification.json", verification)
    files = [p for directory in run.values() for p in directory.rglob("*") if p.is_file()]
    save_json(paths, run["provenance"]/"outputs.json", {
        "completed": True, "final_test_access": False,
        "output_sha256": {p.relative_to(paths.root).as_posix(): file_sha256(p) for p in files}})


def prepare_inputs(paths):
    data, bound = _identity(paths)
    parent_receipt = verified_run(paths, PARENT)
    bound[parent_receipt.relative_to(paths.root).as_posix()] = file_sha256(parent_receipt)
    run_id = datetime.now(timezone.utc).strftime("neighbour_input_%Y%m%dT%H%M%S_%fZ")
    run = paths.create_run(run_id, {"stage": "pooled_neighbour_coordinate_input", "parent": PARENT,
                                    "dataset_release": data["version"], "contract_sha256": CONTRACT_SHA,
                                    "input_sha256": bound, "source_sha256": _source_hashes(paths),
                                    "final_test_access": False})
    guard = ReadOnlyInputs(paths.root, run, data_root=paths.data_root)
    sys.addaudithook(guard)
    frames, read_hashes = [], {}
    try:
        index = pd.read_csv(paths.asset("current_dataset_index", verify=True))
        r_ids = {int(sid) for sid in index.loc[index.in_R.eq(True), "id"]
                 if data["records"][str(int(sid))]["pool"] == "train"}
        region = shape(json.loads(paths.asset("release_R").read_text())["features"][0]["geometry"])
        sh.prepare(region)
        for n, sid in enumerate(sorted(r_ids), 1):
            ledger_path = paths.root/"results/runs"/PARENT/"endpoint_ledgers"/f"{sid}.parquet"
            ledger = pd.read_parquet(ledger_path)
            if not ledger.id.eq(sid).all():
                raise ValueError("Parent ledger identity mismatch.")
            canonical = track_path(sid, allow_test=False)
            track = pd.read_parquet(canonical, columns=["id", "source_obs", "time", "lon_normalized", "lat", "cell_1"])
            joined = join_coordinates(ledger, track)
            read_hashes[str(sid)] = data["records"][str(sid)]["sha256"]
            if len(joined):
                if not sh.intersects_xy(region, joined.origin_lon.to_numpy(), joined.origin_lat.to_numpy()).all():
                    raise ValueError("A supposedly eligible origin is outside frozen R.")
                frames.append(joined)
            if n % 50 == 0 or n == len(r_ids):
                print(f"Source-key joins verified: {n}/{len(r_ids)} development R IDs", flush=True)
        pairs = pd.concat(frames, ignore_index=True)
        counts = pair_counts(pairs).sort_values(KEYS).reset_index(drop=True)
        original = pd.read_parquet(paths.root/"results/runs"/PARENT/"development_counts.parquet").sort_values(KEYS).reset_index(drop=True)
        pd.testing.assert_frame_equal(counts.astype("int64"), original.astype("int64"))
        az, distance = net_displacements(pairs)
        pairs["displacement_azimuth"], pairs["net_distance_m"] = az, distance
        save_frame(paths, run["results"]/"eligible_pairs.parquet", pairs)
        save_frame(paths, run["results"]/"development_counts.parquet", counts)
        if guard.read_ids != r_ids:
            raise ValueError("Canonical read population mismatch.")
        for sid in sorted(guard.read_ids):
            track_path(sid, allow_test=False)
        for relative, checksum in bound.items():
            if file_sha256(paths.root/relative) != checksum:
                raise ValueError("Input changed during preparation.")
        _seal(paths, run, {"parent_counts_exact": True, "canonical_read_hashes": read_hashes,
                           "source_keyed_pairs": len(pairs), "canonical_tracks_read": len(r_ids),
                           "final_test_trajectories_read": 0, "denied_operations": guard.denied,
                           "data_modified": False, "geometry_modified": False})
        print("PREPARED_INPUT_RUN="+run_id, flush=True)
        return run_id
    finally:
        guard.active = False


def _final_selections(terms):
    rows, grids = [], []
    for (family, h), g in terms.groupby(["family", "horizon_days"]):
        choice = select_lambdas(g[["A", "B", "C"]], g.pair_count)
        for method in ("Grid", "Analytic"):
            rows.append({"family": family, "horizon_days": int(h), "method": method,
                         "alpha_value": choice[method.lower()+"_lambda"],
                         "tuning_brier": choice[method.lower()+"_brier"],
                         "scope": "All-development base OOF tuning; NOT an independent score of the final refit"})
        grids.extend({"family": family, "horizon_days": int(h), "alpha_value": r["lambda"],
                      "tuning_brier": r["selection_brier"]} for r in choice["grid_scores"])
    return pd.DataFrame(rows), pd.DataFrame(grids)


def run_models(paths, input_run, *, scenario="pooled", pooled_run=None):
    if scenario not in ("pooled", "drogued", "undrogued"):
        raise ValueError("Unknown regime scenario.")
    data, bound = _identity(paths)
    input_receipt = verified_run(paths, input_run)
    prep_config = json.loads((paths.root/"provenance/runs"/input_run/"run.json").read_text())["config"]
    if (prep_config.get("stage") != ("pooled_neighbour_coordinate_input" if scenario == "pooled" else "fixed_regime_input") or prep_config.get("parent") != PARENT
            or prep_config.get("dataset_release") != data["version"] or prep_config.get("contract_sha256") != CONTRACT_SHA):
        raise ValueError("Unexpected coordinate input preparation.")
    for relative, checksum in prep_config["input_sha256"].items():
        if file_sha256(paths.root/relative) != checksum:
            raise ValueError("Prepared input is stale.")
    bound[input_receipt.relative_to(paths.root).as_posix()] = file_sha256(input_receipt)
    development = sorted(int(sid) for sid, r in data["records"].items() if r["pool"] == "train")
    outer, inner = make_nested_folds(development)
    if scenario != "pooled":
        if not pooled_run:
            raise ValueError("A sealed pooled OOF reference is required.")
        pooled_receipt = verified_run(paths, pooled_run)
        bound[pooled_receipt.relative_to(paths.root).as_posix()] = file_sha256(pooled_receipt)
        pooled_config = json.loads((paths.root/"provenance/runs"/pooled_run/"run.json").read_text())["config"]
        if (pooled_config.get("stage") != "pooled_neighbour_nested_cv"
                or pooled_config.get("scenario") != "pooled"
                or pooled_config.get("fold_assignment_sha256") != fold_digest(outer, inner)
                or pooled_config.get("dataset_release") != data["version"]
                or pooled_config.get("contract_sha256") != CONTRACT_SHA
                or pooled_config.get("input_run") != prep_config.get("pooled_input")):
            raise ValueError("Pooled reference uses a different scientific population or folds.")
    source_hashes = _source_hashes(paths)
    prefix = "baseline_neighbour_cv" if scenario == "pooled" else "baseline_"+scenario+"_cv"
    run_id = datetime.now(timezone.utc).strftime(prefix+"_%Y%m%dT%H%M%S_%fZ")
    run = paths.create_run(run_id, {"stage": "pooled_neighbour_nested_cv" if scenario == "pooled" else "fixed_regime_neighbour_nested_cv", "parent": PARENT, "pooled_reference": pooled_run,
                                    "input_run": input_run, "dataset_release": data["version"],
                                    "contract_sha256": CONTRACT_SHA, "input_sha256": bound,
                                    "source_sha256": source_hashes, "fold_assignment_sha256": fold_digest(outer, inner),
                                    "integration": INTEGRATION, "scenario": scenario, "target": "endpoint",
                                    "origin_population": "R", "grid_degrees": 1, "horizons_days": [7, 30],
                                    "tolerance_hours": 0, "final_test_access": False,
                                    "alpha_rule": "Separate variant/horizon global-cell alpha: grid 0:0.1:1 and analytic, inner OOF only",
                                    "numerical_note": "Balanced couplings preserve exact donor/anchor marginals; stability is not a certified integral error bound",
                                    "visualisation": False, "scientific_environment": scientific_environment()})
    print("MODEL_RUN="+run_id, flush=True)
    guard = ReadOnlyInputs(paths.root, run, data_root=paths.data_root)
    sys.addaudithook(guard)
    started = time.monotonic()
    try:
        pairs = pd.read_parquet(paths.root/"results/runs"/input_run/"eligible_pairs.parquet")
        control_reference = None
        if scenario != "pooled":
            from data3001.modelling.regimes import preflight
            pairs = pairs.loc[pairs.scenario.eq(scenario)].drop(columns="scenario").reset_index(drop=True)
            save_frame(paths, run["results"]/"fold_support_preflight.csv", preflight(pairs, outer, inner))
            from data3001.modelling.cv import evaluate_nested
            control_reference = evaluate_nested(pair_counts(pairs), outer, inner, progress=lambda s: None)["scores"]
            save_frame(paths, run["results"]/"independent_controls.parquet", control_reference)
        domain = shape(json.loads(paths.asset("transport_D").read_text())["features"][0]["geometry"])
        region = shape(json.loads(paths.asset("release_R").read_text())["features"][0]["geometry"])
        land = sh.from_wkb(paths.asset("land_mask_high").read_bytes())
        mapper = EndpointMapper(domain, land)
        # Geometry-only scope, not cells discovered from heldout outcomes.
        x0, y0, x1, y1 = region.bounds
        from shapely.geometry import box
        target_cells = {int((y+90)*360+x+180) for y in range(int(np.floor(y0)), int(np.floor(y1))+1)
                        for x in range(int(np.floor(x0)), int(np.floor(x1))+1)
                        if region.intersects(box(x, y, x+1, y+1))}
        save_frame(paths, run["provenance"]/"outer_folds.csv",
                   pd.DataFrame(sorted(outer.items()), columns=["id", "outer_fold"]))
        save_frame(paths, run["provenance"]/"inner_folds.csv", pd.DataFrame([
            {"id": sid, "outer_fold": f, "inner_fold": k}
            for f in sorted(inner) for sid, k in sorted(inner[f].items())]))

        def checkpoint(tag, model):
            save_json(paths, run["results"]/"fit_checkpoints"/(tag+".json"), serialize_local_model(model))
            save_frame(paths, run["results"]/"fit_checkpoints"/(tag+"_numerical.csv"), pd.DataFrame(model["numerical_audit"]))

        result = evaluate_local_nested(pairs, outer, inner, target_cells, mapper,
                                       integration=INTEGRATION, fit_callback=checkpoint,
                                       progress=lambda msg: print(msg, flush=True))
        summary = summarize_scores(result["scores"])
        selections, final_grid = _final_selections(result["base_terms"])
        frames = {"outer_scores.parquet": result["scores"], "outer_summary.csv": summary,
                  "outer_fold_summary.csv": summarize_scores(result["scores"], by_fold=True),
                  "alpha_selection.csv": result["selection"], "alpha_grid_scores.csv": result["grid_scores"],
                  "fixed_alpha_diagnostics.csv": result["fixed_alpha_scores"],
                  "outer_base_terms.parquet": result["base_terms"], "training_support.csv": result["support"],
                  "numerical_audit.csv": result["numerical_audit"], "final_alpha_selection.csv": selections,
                  "final_alpha_grid_scores.csv": final_grid}
        for name, frame in frames.items():
            save_frame(paths, run["results"]/name, frame)
        final = fit_local_bases(pairs, development, target_cells, mapper, fit_tag="all_development",
                                integration=INTEGRATION, progress=lambda msg: print(msg, flush=True))
        save_json(paths, run["results"]/"final_models.json", serialize_local_model(final))
        save_frame(paths, run["results"]/"final_numerical_audit.csv", pd.DataFrame(final["numerical_audit"]))
        save_frame(paths, run["results"]/"final_training_support.csv", pd.DataFrame(final["support"]))
        from data3001.modelling.neighbourhood_report import audit_and_report
        audit = audit_and_report(paths, run, result, selections, final, pairs,
                                 scenario=scenario, control_reference=control_reference)
        if scenario != "pooled":
            from data3001.modelling.regimes import matched_pooled_scores, paired_regime_intervals
            pooled_scores = pd.read_parquet(paths.root/"results/runs"/pooled_run/"outer_scores.parquet")
            matched = matched_pooled_scores(pooled_scores, pair_counts(pairs))
            paired = paired_regime_intervals(result["scores"], matched)
            save_frame(paths, run["results"]/"matched_pooled_scores.parquet", matched)
            save_frame(paths, run["results"]/"matched_pooled_summary.csv", summarize_scores(matched))
            save_frame(paths, run["results"]/"fixed_vs_matched_pooled.csv", paired)
            audit["matched_pooled_same_cases_verified"] = True
        if guard.read_ids:
            raise ValueError("Fitting should reuse the sealed coordinate input without reopening trajectories.")
        for relative, checksum in {**bound, **source_hashes}.items():
            if file_sha256(paths.root/relative) != checksum:
                raise ValueError("Input/scientific code changed during fitting: "+relative)
        _seal(paths, run, {"audit": audit, "input_coordinate_run": input_run,
                           "canonical_tracks_read_by_fitting": 0, "final_test_trajectories_read": 0,
                           "denied_operations": guard.denied, "frozen_inputs_unchanged": True,
                           "source_code_unchanged_during_fit": True, "canonical_data_modified": False,
                           "elapsed_seconds": time.monotonic()-started,
                           "peak_rss_bytes_macos": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                           "scientific_environment": scientific_environment()})
        print(summary.to_string(index=False), flush=True)
        print("FINAL_WEIGHTS\n"+selections.to_string(index=False), flush=True)
        print("REPORT="+str(run["results"]/"REPORT.md"), flush=True)
        return run_id
    finally:
        guard.active = False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--input-run")
    args = parser.parse_args()
    paths = project_paths()
    if args.prepare_only:
        prepare_inputs(paths)
    else:
        run_models(paths, args.input_run or prepare_inputs(paths))


if __name__ == "__main__":
    main()
