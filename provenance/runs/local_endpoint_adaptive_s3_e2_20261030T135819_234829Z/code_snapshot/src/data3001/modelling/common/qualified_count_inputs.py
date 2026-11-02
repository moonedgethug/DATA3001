"""Verified development-only qualified counts, indexes and immutable input guards."""
import json
import os
from pathlib import Path

import pandas as pd

from data3001.paths import file_sha256
from data3001.preprocessing.prep_core import REASONS
from data3001.modelling.common.runtime import ReadOnlyInputs

KEYS = ["id", "horizon_days", "origin_cell_1", "destination_cell_1"]
ROW = ["horizon_days", "origin_cell_1"]
DEST = "destination_cell_1"
HORIZONS = (7, 30)
EXIT = -2
TOLERANCE = 1e-12


def validate_counts(counts, origins, destinations):
    if set(counts.columns) != set(KEYS + ["pair_count"]):
        raise ValueError("Unexpected count schema")
    if any(not pd.api.types.is_integer_dtype(counts[c]) or counts[c].isna().any()
           for c in counts.columns):
        raise ValueError("Counts and identifiers must be nonmissing integers")
    if (counts.duplicated(KEYS).any() or not counts.pair_count.gt(0).all()
            or not counts.id.gt(0).all() or not counts.horizon_days.isin(HORIZONS).all()
            or not counts.origin_cell_1.isin(origins).all()
            or not counts[DEST].isin(destinations).all()):
        raise ValueError("Invalid count key, multiplicity, horizon or frozen state")


def run_input_paths(paths, config):
    counts = paths._resolve(config["counts_path"])
    folds = paths._resolve(config["folds_path"])
    for path, filename in [(counts, "release_counts_by_id.parquet"), (folds, "folds.csv")]:
        if path.name != filename or path.parent.parent != paths.root / "results/runs":
            raise ValueError("Expected an explicit sealed data-only run input")
    return counts, folds


class ExperimentGuard(ReadOnlyInputs):
    """Deny raw trajectory reads and non-allowlisted historical run artifacts."""
    def __init__(self, paths, run, allowed_reads):
        super().__init__(paths.root, run, data_root=paths.data_root)
        self.input_files = {p.resolve() for p in allowed_reads}
        self.opened_inputs = set()

    def __call__(self, event, args):
        super().__call__(event, args)
        if not self.active or event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        p = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        writing = ((isinstance(mode, str) and any(c in mode for c in "wax+"))
                   or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)))
        if writing or any(p.is_relative_to(base) for base in self.allowed):
            return
        sensitive = (p.is_relative_to(self.data_root)
                     or p.is_relative_to(self.root / "results/runs")
                     or p.is_relative_to(self.root / "provenance/runs")
                     or (p.is_relative_to(self.root) and p.suffix == ".parquet"))
        if sensitive and p not in self.input_files:
            self.denied.append({"path": str(p), "writing": False})
            raise PermissionError("Non-allowlisted data or historical experiment artifact")
        if p in self.input_files:
            self.opened_inputs.add(p)


def read_frame(path):
    # A Python file handle ensures the read guard observes even Arrow reads.
    with path.open("rb") as stream:
        return pd.read_parquet(stream) if path.suffix == ".parquet" else pd.read_csv(stream)


def sealed_receipt(paths, input_path):
    receipt_path = paths.root / "provenance/runs" / input_path.parent.name / "outputs.json"
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("completed") is not True or receipt.get("final_test_access") is not False:
        raise ValueError("Input run is incomplete or permits final-test access")
    return receipt_path, receipt["output_sha256"]


def verify_file(paths, path, checksums, inventory):
    relative = path.relative_to(paths.root).as_posix()
    digest = file_sha256(path)
    if checksums.get(relative) != digest:
        raise ValueError("Input checksum mismatch: " + relative)
    inventory[relative] = digest


def counts_from_labels(labels):
    required = set(KEYS + ["origin_source_obs", "reason_code", "target", "scenario",
                           "tolerance_hours", "outside", "first_exit_source_obs"])
    if not required.issubset(labels.columns):
        raise ValueError("Incomplete qualified release label schema")
    if (not labels.target.eq("stopped").all() or not labels.scenario.eq("pooled").all()
            or not labels.tolerance_hours.eq(0).all()
            or not labels.reason_code.isin(REASONS).all()
            or labels.duplicated(["id", "origin_source_obs", "horizon_days"]).any()):
        raise ValueError("Label target, scenario, tolerance or source key mismatch")
    eligible = labels.loc[labels.reason_code.eq(0) & labels.horizon_days.isin(HORIZONS)]
    if (not eligible.outside.eq(eligible.destination_cell_1.eq(EXIT)).all()
            or not eligible.first_exit_source_obs.ge(0).eq(eligible.outside).all()):
        raise ValueError("Exit label does not agree with first observed exit")
    return eligible.groupby(KEYS, as_index=False).size().rename(columns={"size": "pair_count"}).astype("int64")


def load_inputs(paths, config, progress=print):
    counts_path, folds_path = run_input_paths(paths, config)
    inventory = {}
    manifest_path = paths.root / "configs/dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if (manifest["version"] != config["dataset_release"]
            or manifest["contract_sha256"] != config["contract_sha256"]):
        raise ValueError("Dataset release or contract identity changed")
    ids = sorted(int(k) for k, record in manifest["records"].items() if record["pool"] == "train")
    for path in [manifest_path, paths.root / "configs/assets.json", paths._resolve(config["approved_plan"])]:
        inventory[path.relative_to(paths.root).as_posix()] = file_sha256(path)
    for asset in config["source_assets"]:
        path = paths.asset(asset, verify=True)
        inventory[path.relative_to(paths.root).as_posix()] = file_sha256(path)
    if file_sha256(paths.asset("english_contract")) != config["contract_sha256"]:
        raise ValueError("Contract differs from approved identity")
    state = read_frame(paths.asset("state_index"))
    state = state.loc[state.resolution.eq(1)].sort_values("cell").reset_index(drop=True)
    origins = state.loc[state.R_intersection].copy()
    destinations = state.copy()
    for path in [counts_path, folds_path]:
        receipt_path, checksums = sealed_receipt(paths, path)
        inventory[receipt_path.relative_to(paths.root).as_posix()] = file_sha256(receipt_path)
        verify_file(paths, path, checksums, inventory)
    _, checksums = sealed_receipt(paths, counts_path)
    parent = paths.root / "provenance/runs" / counts_path.parent.name / "run.json"
    verify_file(paths, parent, checksums, inventory)
    parent_config = json.loads(parent.read_text())["config"]
    for key in ["dataset_release", "contract_sha256", "target", "scenario", "grid_degrees", "weighting", "tolerance_hours"]:
        if parent_config[key] != config[key]:
            raise ValueError("Qualified-cache provenance mismatch: " + key)
    if parent_config.get("final_test_access") is not False:
        raise ValueError("Cache was not development-only")
    source_path = counts_path.parent / "source_ID_summary.csv"
    verify_file(paths, source_path, checksums, inventory)
    source = read_frame(source_path)
    if source.id.duplicated().any() or sorted(source.id) != ids:
        raise ValueError("Source inventory does not match the development population")
    for row in source.itertuples(index=False):
        record = manifest["records"][str(row.id)]
        if row.source_sha256 != record["sha256"] or row.retained_rows != record["rows"]:
            raise ValueError("Qualified cache is not derived from current v7 source metadata")
    counts = read_frame(counts_path)
    counts = counts.loc[counts.horizon_days.isin(HORIZONS)].sort_values(KEYS).reset_index(drop=True)
    validate_counts(counts, origins.cell, [*destinations.cell, EXIT])
    if not counts.id.isin(ids).all():
        raise ValueError("Non-development IDs in counts")
    folds = read_frame(folds_path).sort_values("id").reset_index(drop=True)
    if (set(folds.columns) != {"id", "outer_fold"} or folds.id.duplicated().any()
            or sorted(folds.id) != ids or set(folds.outer_fold) != set(range(5))
            or not pd.api.types.is_integer_dtype(folds.id)
            or not pd.api.types.is_integer_dtype(folds.outer_fold)):
        raise ValueError("Invalid whole-ID fold assignments")
    label_paths = sorted((counts_path.parent / "release_labels").glob("*.parquet"))
    expected_ids = set(source.loc[source.R_origins.gt(0), "id"])
    if {int(p.stem) for p in label_paths} != expected_ids:
        raise ValueError("Release label files do not cover all R-origin IDs")
    rebuilt, reasons = [], []
    for n, path in enumerate(label_paths, 1):
        verify_file(paths, path, checksums, inventory)
        labels = read_frame(path)
        if not labels.id.eq(int(path.stem)).all():
            raise ValueError("Release label file contains the wrong ID")
        rebuilt.append(counts_from_labels(labels))
        r = labels.loc[labels.horizon_days.isin(HORIZONS)].groupby(["horizon_days", "reason_code"]).size().reset_index(name="candidate_count")
        r["id"] = int(path.stem); reasons.append(r)
        if n % 100 == 0:
            progress(f"Verified qualified labels: {n}/{len(label_paths)} IDs", flush=True)
    rebuilt = pd.concat(rebuilt, ignore_index=True).sort_values(KEYS).reset_index(drop=True)
    pd.testing.assert_frame_equal(counts, rebuilt, check_dtype=False, check_exact=True)
    progress(f"Inputs verified: {len(ids)} development IDs; {len(counts)} grouped eligible cases", flush=True)
    return counts, folds, origins, destinations, pd.concat(reasons, ignore_index=True), inventory

