"""Deterministic whole-ID folds; metadata-only experiment preview."""

import hashlib
import json
from numbers import Integral

import pandas as pd

from data3001.dataset import manifest
from data3001.paths import file_sha256, project_paths

SETTINGS = {
    "stage": "baseline_blend_nested_cv",
    "dataset_release": "per-drifter-cleaned-20261017-v7",
    "scenario": "pooled",
    "target": "endpoint",
    "origin_population": "R",
    "grid_degrees": 1,
    "horizons_days": [7, 30],
    "tolerance_hours": 0,
    "B2_predictors": ["origin_cell_1"],
    "weighting": "equal_eligible_pairs",
    "cv_population": "development",
    "outer_folds": 5,
    "inner_folds": 4,
    "seed": 20261004,
    "lambda_grid": [k / 10.0 for k in range(11)],
    "selection_metric": "brier_failure_penalized",
    "final_test_access": False,
}

def make_folds(ids, *, n_splits=5, tag="round1-cv", seed=20261004):
    """Assign unique instrument IDs without using observations or outcomes."""
    ids = list(ids)

    if any(
        isinstance(sid, bool) or not isinstance(sid, Integral) or sid <= 0
        for sid in ids
    ):
        raise ValueError("IDs must be positive integers.")

    ids = sorted(int(sid) for sid in ids)

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate IDs are not allowed.")

    if (
        isinstance(n_splits, bool)
        or not isinstance(n_splits, Integral)
        or n_splits < 2
        or len(ids) < n_splits
    ):
        raise ValueError("Insufficient IDs or invalid fold count.")

    assignments = {}

    for sid in ids:
        payload = f"{seed}:{tag}:{sid}".encode("ascii")
        number = int.from_bytes(
            hashlib.sha256(payload).digest()[:8], "big"
        )
        assignments[sid] = number % int(n_splits)

    if set(assignments.values()) != set(range(n_splits)):
        raise ValueError(
            "An empty fold requires review; do not silently reseed."
        )

    return assignments


def make_nested_folds(ids):
    """Keep each outer holdout entirely outside all its inner folds."""
    outer = make_folds(
        ids,
        n_splits=SETTINGS["outer_folds"],
        seed=SETTINGS["seed"],
    )

    inner = {}

    for outer_fold in range(SETTINGS["outer_folds"]):
        training_ids = [
            sid for sid, fold in outer.items() if fold != outer_fold
        ]

        inner[outer_fold] = make_folds(
            training_ids,
            n_splits=SETTINGS["inner_folds"],
            tag=f"round1-inner:{outer_fold}",
            seed=SETTINGS["seed"],
        )

    return outer, inner


def fold_digest(outer, inner):
    """Hash the complete assignments, not just their summary counts."""
    payload = {
        "outer": sorted(outer.items()),
        "inner": [
            [fold, sorted(inner[fold].items())]
            for fold in sorted(inner)
        ],
    }

    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("ascii")

    return hashlib.sha256(encoded).hexdigest()


def main():
    paths = project_paths()
    dataset = manifest()

    if dataset["version"] != SETTINGS["dataset_release"]:
        raise RuntimeError("Unexpected dataset release.")

    if SETTINGS["final_test_access"] is not False:
        raise RuntimeError("Final-test access must remain disabled.")

    if (
        file_sha256(paths.asset("english_contract", verify=True))
        != dataset["contract_sha256"]
    ):
        raise RuntimeError("Contract identity mismatch.")

    records = dataset["records"]

    development = {
        int(sid)
        for sid, record in records.items()
        if record["pool"] == "train"
    }
    locked = {
        int(sid)
        for sid, record in records.items()
        if record["pool"] == "test"
    }

    if development & locked or len(development) != dataset["pools"]["train"]:
        raise RuntimeError("Invalid development/test membership.")

    index = pd.read_csv(
        paths.asset("current_dataset_index", verify=True)
    )

    if index["id"].duplicated().any():
        raise RuntimeError("Duplicate dataset-index IDs.")

    if set(index["id"].astype(int)) != {int(sid) for sid in records}:
        raise RuntimeError("Dataset-index membership mismatch.")

    r_ids = set(index.loc[index["in_R"].eq(True), "id"].astype(int))
    outer, inner = make_nested_folds(sorted(development))

    rows = []

    for fold in range(SETTINGS["outer_folds"]):
        heldout = {
            sid for sid, group in outer.items() if group == fold
        }
        training = development - heldout

        if set(inner[fold]) != training or heldout & set(inner[fold]):
            raise RuntimeError("Outer/inner ID separation failed.")

        inner_fit_r = []
        inner_validation_r = []

        for inner_fold in range(SETTINGS["inner_folds"]):
            validation = {
                sid for sid, group in inner[fold].items()
                if group == inner_fold
            }
            fitting = training - validation

            inner_fit_r.append(len(fitting & r_ids))
            inner_validation_r.append(len(validation & r_ids))

        rows.append({
            "outer_fold": fold,
            "fit_IDs": len(training),
            "heldout_IDs": len(heldout),
            "fit_R_IDs": len(training & r_ids),
            "heldout_R_IDs": len(heldout & r_ids),
            "min_inner_fit_R_IDs": min(inner_fit_r),
            "min_inner_validation_R_IDs": min(inner_validation_r)
        })

    print("Dataset release:", dataset["version"])
    print("Development IDs:", len(development))
    print("Development IDs visiting R:", len(development & r_ids))
    print("Final-test access: disabled")
    print("\nWhole-ID nested-fold preview:")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nFold assignment SHA256:", fold_digest(outer, inner))
    print("FOLD_SETUP_CHECKS_PASSED")
    print("R counts describe visitors, not eligible horizon-pair support.")
    print("No trajectories read, models trained, or output files written.")


if __name__ == "__main__":
    main()
