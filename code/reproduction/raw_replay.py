"""Development-only raw cleaning replay using the preserved scientific functions.

Raw observations are rebuilt; historical SST decisions are replayed from their
approved evidence chain. Frozen v7 tables are read only after reconstruction,
as comparison targets. No frozen_action wrapper is bypassed or changed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


APPROVED_TEMPERATURE_RUN = "total_sst_reference_audit_20261017_v1"
ATTACHED_EVIDENCE = "provenance/runs/drogue_status_20261016/group1_official_evidence.json"


def _select_development_ids(records, ids):
    development = {sid: item for sid, item in records.items() if item["pool"] == "train"}
    if ids is None:
        return sorted(development, key=lambda sid: development[sid]["source_index"])
    selected = [str(int(value)) for value in ids]
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("Choose at least one unique development ID")
    for sid in selected:
        if sid not in records:
            raise ValueError("Unknown trajectory ID: " + sid)
        if sid not in development:
            raise PermissionError("Final-test trajectory replay is not authorized: " + sid)
    return sorted(selected, key=lambda sid: development[sid]["source_index"])


def _legacy_target(mapping, relative):
    if relative in mapping["file_map"]:
        return mapping["file_map"][relative]
    for prefix in sorted(mapping["directory_map"], key=len, reverse=True):
        if relative == prefix or relative.startswith(prefix + "/"):
            return mapping["directory_map"][prefix] + relative[len(prefix):]
    raise KeyError("Unregistered historical input: " + relative)


def _bind_raw_chunks(view, relative, selected):
    """Bind only chunks needed by the selected tracks plus cohort metadata.

    The source is a shared ragged-array store. A selected observation chunk may
    contain neighbouring IDs; these storage bytes are never selected as tracks.
    """
    import numpy as np
    import zarr

    source = view.mapping.resolve(relative)
    group = zarr.open_consolidated(str(source), mode="r")
    ids, sizes = group["id"][:], group["rowsize"][:]
    lookup = {str(int(value)): index for index, value in enumerate(ids)}
    positions = [lookup[sid] for sid in selected]
    offsets = np.r_[0, np.cumsum(sizes, dtype=np.int64)]
    bound = set()
    for path in sorted(source.rglob(".z*")):
        if path.is_file():
            item = relative + "/" + path.relative_to(source).as_posix()
            view.bind(item); bound.add(item)
    for name in group.array_keys():
        array = group[name]
        if len(array.shape) != 1:
            raise ValueError("Raw replay expects the frozen one-dimensional ragged arrays")
        width = array.chunks[0]
        dimension = array.attrs.get("_ARRAY_DIMENSIONS")
        if name in ("id", "rowsize"):
            chunks = range((len(array) + width - 1) // width)
        elif dimension == ["traj"]:
            chunks = {index // width for index in positions}
        elif dimension == ["obs"]:
            chunks = {chunk for index in positions
                      for chunk in range(int(offsets[index]) // width, (int(offsets[index + 1]) - 1) // width + 1)}
        else:
            raise ValueError("Unexpected raw array dimension: " + name)
        for chunk in sorted(chunks):
            item = relative + "/" + name + "/" + str(chunk)
            # Zarr may legitimately omit all-fill chunks.
            if (source / name / str(chunk)).is_file():
                view.bind(item); bound.add(item)
    return {"selected_ids": list(selected), "raw_store": relative,
            "source_trajectory_metadata_ids": len(ids), "bound_raw_files": len(bound),
            "raw_rows_requested": sum(int(sizes[index]) for index in positions),
            "shared_raw_chunks_may_contain_other_ids": True,
            "final_test_trajectories_requested": False}


def _bind_temperature_chain(view, selected):
    remaining = set(selected)
    run = APPROVED_TEMPERATURE_RUN
    seen, evidence = set(), {}
    while run:
        if run in seen:
            raise ValueError("Cyclic approved temperature evidence")
        seen.add(run)
        directory = "results/runs/" + run
        for name in ("verification.json", "config.json", "output_manifest.json"):
            view.bind(directory + "/" + name)
        configuration = json.loads(view.mapping.resolve(directory + "/config.json").read_text())
        records = json.loads(view.mapping.resolve(directory + "/output_manifest.json").read_text())
        for item in records:
            sid = str(int(item["id"]))
            if sid not in remaining:
                continue
            if item.get("pool") == "test":
                raise PermissionError("Approved SST evidence assigns a development ID to final test")
            path = item["path"] if item["path"].startswith("results/") else directory + "/" + item["path"]
            view.bind(path, expected_sha256=item["sha256"])
            evidence[sid] = {"path": path, "sha256": item["sha256"], "run": run}
            remaining.remove(sid)
        run = configuration.get("parent_run")
        if not run and configuration.get("baseline"):
            baseline = Path(configuration["baseline"])
            if baseline.parent.as_posix() != "results/runs":
                raise ValueError("Unexpected approved temperature baseline")
            run = baseline.name
    if remaining:
        raise ValueError("Missing approved SST decisions for: " + ", ".join(sorted(remaining)))
    return evidence


def _compare_tables(actual, expected):
    """Separate exact values/types/nulls from writer and schema metadata."""
    import numpy as np
    import pyarrow as pa

    differing = []
    same_layout = len(actual) == len(expected) and actual.column_names == expected.column_names
    same_types = same_layout and all(actual[name].type == expected[name].type for name in actual.column_names)
    if same_types:
        for name in actual.column_names:
            left, right = actual[name], expected[name]
            equal = left.is_null().equals(right.is_null())
            if pa.types.is_floating(left.type):
                equal = equal and np.array_equal(left.to_numpy(), right.to_numpy(), equal_nan=True)
            else:
                equal = equal and left.equals(right)
            if not equal:
                differing.append(name)
    return {"content_equal": same_types and not differing,
            "rows_equal": len(actual) == len(expected), "column_order_equal": actual.column_names == expected.column_names,
            "types_equal": same_types, "different_columns": differing,
            "field_metadata_equal": same_layout and all(actual.schema.field(name).metadata == expected.schema.field(name).metadata
                                                         for name in actual.column_names),
            "schema_metadata_equal": actual.schema.metadata == expected.schema.metadata}


def _prepared_storage_roundtrip(frame):
    """Repeat the original preparation write/read boundary, entirely in memory."""
    import io
    import pandas as pd
    stream = io.BytesIO()
    frame.to_parquet(stream, index=False, compression="zstd")
    stream.seek(0)
    return pd.read_parquet(stream)


def _rebuild_track(source, sid, land, coarse, native_fields, native_attributes, boundary, attached_proofs, approved):
    import numpy as np
    import pyarrow as pa
    from data3001.data_release import assemble_track, unknown_reasons
    from data3001.preprocessing.prep_run import clean_track
    from data3001.preprocessing.drogue_correction import official_attached_evidence, restore_attached
    from data3001.preprocessing.drogue_boundary import boundary_evidence, official_regimes
    from data3001.recovery_storage import clean_table
    from data3001.sst_storage import replace_sst
    from data3001.grounding_sst import clear_post_grounding_sst
    from data3001.drogue_storage import materialize_drogue_status
    from data3001.hardware_missing import normalize_hardware_missing
    from data3001.paths import project_paths

    ident = int(sid)
    split = str(source.cohort.loc[ident, "split"])
    if split == "test":
        raise PermissionError("Final-test trajectory request rejected")
    raw, metadata = source.track(ident)
    frame, duplicate_groups = clean_track(raw, metadata, land, coarse)
    frame = _prepared_storage_roundtrip(frame)
    baseline_regime = frame.regime.to_numpy(copy=True)
    attached = official_attached_evidence(ident, split)
    if attached:
        evidence = attached_proofs[sid]
        if evidence["sha256"] != attached["official_file_sha256"]:
            raise ValueError("Official attachment evidence identity changed")
        frame = restore_attached(frame, evidence, ident)
    proof = boundary_evidence(ident, split)
    if proof:
        labels = official_regimes(frame.time.to_numpy(), proof)
        if int((labels != frame.regime.to_numpy()).sum()) != proof["changed_rows"]:
            raise ValueError("Boundary replay changed a different number of rows")
        frame["regime"] = labels
    context = {}
    if proof:
        context = {"loss_status_source": "official_boundary_refinement", "official_regime_decision": proof["decision"],
                   "official_loss_epoch": proof.get("official_loss_epoch"),
                   # Preserve the original release assembly's annotation key;
                   # the complete official boundary record remains attached.
                   "official_attached_through_epoch": proof.get("official_attached_through_epoch"),
                   "preparation_correction_version": "official-drogue-boundary-v1",
                   "preparation_correction_asset": "official_drogue_boundary"}
    elif attached:
        context = {"loss_status_source": "official_fill_attached", "official_attached_through_epoch": attached["attached_through_epoch"],
                   "preparation_correction_version": "official-drogue-attached-44-v1",
                   "preparation_correction_asset": "official_drogue_correction"}
    reason = unknown_reasons(frame.regime.to_numpy(), float(metadata["drogue_lost_date"]), boundary.get(sid))
    annotations = {
        "historical_split": pa.array([split] * len(frame), type=pa.string()),
        "pool": pa.array(["train"] * len(frame), type=pa.string()),
        "regime_pre_official_correction": pa.array(baseline_regime, type=pa.int8()),
        "regime_unknown_reason": pa.array(reason, type=pa.string()),
    }
    for name, value in (("regime_annotation_version", context.get("preparation_correction_version", "preparation-1.0")),
                        ("regime_annotation_source", context.get("loss_status_source", "frozen_hourly_rule")),
                        ("official_regime_decision", context.get("official_regime_decision"))):
        annotations[name] = pa.array([value] * len(frame), type=pa.string())
    for name in ("official_loss_epoch", "official_attached_through_epoch"):
        annotations[name] = pa.array([context.get(name)] * len(frame), type=pa.float64())
    # Preserve native numpy scalar widths; Source.track's Python scalar metadata
    # is suitable for cleaning but would widen several assembly field types.
    typed_metadata = {name: source.g[name][source.index[ident]] for name in native_fields
                      if source.g[name].attrs.get("_ARRAY_DIMENSIONS") == ["traj"]}
    release_context = {"release": "per-drifter-20261016-v1", "id": sid, "pool": "train", "historical_split": split,
                       "regime_context": context, "boundary_record": proof, "attached_record": attached,
                       "contract_sha256": source.snapshot.get("contract_sha256") or project_paths().catalog["contract_sha256"],
                       "native_field_names": native_fields, "prepared_field_names": frame.columns.tolist()}
    table = assemble_track(frame, typed_metadata, annotations=annotations,
                           field_attributes=native_attributes, context=release_context)
    table, removed = clean_table(table)
    table = replace_sst(table, approved)
    table = clear_post_grounding_sst(table)
    table = materialize_drogue_status(table)
    table = normalize_hardware_missing(table)
    return table, {"raw_rows": len(frame), "recovery_rows_removed": len(removed),
                   "duplicate_groups": len(duplicate_groups), "official_boundary_replayed": proof is not None,
                   "official_attached_replayed": attached is not None}


def _worker(request_path):
    import pyarrow.parquet as pq
    from data3001.preprocessing.prep_io import Source
    from data3001.preprocessing.prep_geometry import mask
    from data3001.feature_pruning import prune_table
    from data3001.sst_storage import approved_temperature_index, read_approved
    from data3001.paths import asset_path, file_sha256, project_paths

    request = json.loads(Path(request_path).read_text())
    root = project_paths().root
    manifest = json.loads((root / "configs/dataset_manifest.json").read_text())
    qualification = json.loads((root / "configs/qualification_manifest.json").read_text())
    selected = _select_development_ids(manifest["records"], request["ids"])
    source = Source(allow_test=False)
    for sid in selected:
        if str(source.cohort.loc[int(sid), "split"]) == "test":
            raise PermissionError("Raw cohort assigns a requested ID to final test")
    land, coarse = mask("h"), mask("i")
    native_fields = list(source.g.array_keys())
    attributes = {name: {**source.g[name].attrs.asdict(), "native_numpy_dtype": str(source.g[name].dtype)}
                  for name in native_fields}
    boundary = json.loads(asset_path("official_drogue_boundary", verify=True).read_text())["records"]
    evidence = json.loads((root / ATTACHED_EVIDENCE).read_text())["records"]
    attached_proofs = {str(int(item["id"])): item for item in evidence}
    approved_index, dependencies = approved_temperature_index(root)
    output = Path(request["output"])
    (output / "data/train").mkdir(parents=True, exist_ok=False)
    (output / "qualification/development").mkdir(parents=True, exist_ok=False)
    records = []
    for number, sid in enumerate(selected, 1):
        started = time.monotonic()
        table, stages = _rebuild_track(source, sid, land, coarse, native_fields, attributes,
                                       boundary, attached_proofs, read_approved(root, approved_index[sid]))
        projected_qualification = table.select(qualification["fields"]).replace_schema_metadata({
            b"raw_replay_qualification": json.dumps({"id": sid, "pool": "train",
                "method": "Recomputed original qualification from raw observations using preserved scientific functions",
                "comparison_manifest": "configs/qualification_manifest.json"}, sort_keys=True).encode()
        })
        rebuilt = prune_table(table, manifest["cleaning"]["feature_pruning"]["removed_columns"])
        data_path = output / "data/train" / (sid + ".parquet")
        qualification_path = output / "qualification/development" / (sid + ".parquet")
        # Match the approved v7 projection writer's storage settings.
        pq.write_table(rebuilt, data_path, compression="zstd", compression_level=3)
        pq.write_table(projected_qualification, qualification_path, compression="zstd", compression_level=3)
        # Comparison targets are deliberately first opened after reconstruction.
        expected_record = manifest["records"][sid]
        expected_qualification = qualification["records"][sid]
        expected_path, expected_qpath = root / expected_record["path"], root / expected_qualification["path"]
        if file_sha256(expected_path) != expected_record["sha256"] or file_sha256(expected_qpath) != expected_qualification["sha256"]:
            raise ValueError("Frozen comparison target identity changed")
        comparison = _compare_tables(pq.read_table(data_path), pq.read_table(expected_path))
        comparison["byte_equal"] = file_sha256(data_path) == expected_record["sha256"]
        qcomparison = _compare_tables(pq.read_table(qualification_path), pq.read_table(expected_qpath))
        qcomparison["byte_equal"] = file_sha256(qualification_path) == expected_qualification["sha256"]
        record = {"id": sid, "rows": len(rebuilt), "fields": len(rebuilt.column_names), **stages,
                  "data_comparison": comparison, "qualification_comparison": qcomparison,
                  "output_sha256": file_sha256(data_path), "qualification_sha256": file_sha256(qualification_path),
                  "sst_decision_source": approved_index[sid], "elapsed_seconds": time.monotonic() - started}
        records.append(record)
        print(json.dumps({"completed_ids": number, "selected_ids": len(selected), **record}), flush=True)
    report = {"task": "data.raw_cleaning", "mode": "raw_replay", "records": records,
              "ids_rebuilt": len(records), "rows_rebuilt": sum(item["rows"] for item in records),
              "all_content_equal": all(item["data_comparison"]["content_equal"] and item["qualification_comparison"]["content_equal"] for item in records),
              "all_byte_equal": all(item["data_comparison"]["byte_equal"] and item["qualification_comparison"]["byte_equal"] for item in records),
              "sst_scope": "Replay of approved SST decisions; original SST imputation is not recomputed.",
              "qualification_metadata_scope": "New raw-replay provenance is recorded; frozen qualification provenance is not copied.",
              "sst_evidence_dependencies": dependencies, "training_performed": False,
              "final_test_trajectories_requested": False, "shared_raw_chunks_may_contain_other_ids": True}
    Path(request["report"]).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return 0 if report["all_content_equal"] else 1


def run(root, run_id=None, ids=None, timeout=None):
    from .runner import run_command
    from .workspace import DeliveryMap, ExecutionWorkspace, write_json

    mapping = DeliveryMap(root)
    manifest = json.loads(mapping.resolve("configs/dataset_manifest.json").read_text())
    selected = _select_development_ids(manifest["records"], ids)
    total_development = sum(item["pool"] == "train" for item in manifest["records"].values())
    view = ExecutionWorkspace(root, run_id)
    started = time.monotonic()
    view.status.update(task="data.raw_cleaning", mode="raw_replay", shared_raw_chunks_may_contain_other_ids=True,
                       final_test_trajectories_requested=False, selected_ids=selected,
                       development_ids_available=total_development, partial_development_replay=len(selected) != total_development)
    try:
        view.materialize_sources()
        legacy = json.loads(view.mapping.resolve("configs/legacy_paths.json").read_text())
        for name in ("manifests/acquired_ids.csv", "manifests/R_ids.csv", "manifests/source_snapshot.json"):
            view.bind(_legacy_target(legacy, name))
        view.bind_assets(["release_R", "land_mask_high", "land_mask_intermediate",
                          "official_drogue_correction", "official_drogue_boundary"])
        view.bind(ATTACHED_EVIDENCE)
        raw = _bind_raw_chunks(view, _legacy_target(legacy, "raw/hourly_subset_v2.01.1.zarr"), selected)
        approved = _bind_temperature_chain(view, selected)
        qualification = json.loads(view.mapping.resolve("configs/qualification_manifest.json").read_text())
        for sid in selected:
            record, qrecord = manifest["records"][sid], qualification["records"][sid]
            if qrecord["pool"] != "train":
                raise PermissionError("Qualification assigns a requested ID to final test")
            view.bind(record["path"], expected_sha256=record["sha256"])
            view.bind(qrecord["path"], expected_sha256=qrecord["sha256"])
        view.save_inventory()
        request_path = view.directory / "raw_replay_request.json"
        report_path = view.directory / "raw_replay_report.json"
        write_json(request_path, {"ids": selected, "output": str(view.directory / "raw_replay"), "report": str(report_path)})
        run_command(view, ["-B", str(Path(__file__).resolve()), "--worker", str(request_path)],
                    label="raw_development_cleaning_replay", timeout=timeout)
        report = json.loads(report_path.read_text())
        return view.finish("complete", **report, raw_input_scope=raw, approved_sst_inputs=approved,
                           elapsed_seconds=time.monotonic() - started)
    except BaseException as error:
        view.finish("interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                    error=type(error).__name__ + ": " + str(error), elapsed_seconds=time.monotonic() - started)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", required=True)
    arguments = parser.parse_args()
    sys.exit(_worker(arguments.worker))
