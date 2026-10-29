from data3001.modelling.common.probability import score_distribution, check_scoring
import numpy as np
import json
from datetime import datetime, timezone
from functools import lru_cache

import pandas as pd

from data3001.dataset import PreparedSource, manifest
from data3001.paths import file_sha256, project_paths
from data3001.preprocessing.prep_core import REASONS
from data3001.preprocessing.prep_io import code_hash
from data3001.preprocessing.prep_pairs import (
    generate,
    load_track,
    origin_indices,
)



def load_probability_table(path, conditions):
    table = pd.read_csv(path)
    keys = conditions + ["destination_cell_1"]

    if table.empty or table.duplicated(keys).any():
        raise RuntimeError("Empty or duplicated probability table.")

    if not table["pair_count"].gt(0).all():
        raise RuntimeError("Invalid training counts.")

    forecasts = {}

    for key, group in table.groupby(conditions):
        if not isinstance(key, tuple):
            key = (key,)

        probabilities = dict(zip(
            group["destination_cell_1"].astype(int),
            group["probability"].astype(float),
        ))

        # Check the saved distribution without renormalizing it.
        score_distribution(probabilities, next(iter(probabilities)))
        forecasts[tuple(int(value) for value in key)] = probabilities

    return forecasts

def summarize_validation(scores):
    rows = []

    for (days, model), group in scores.groupby(
        ["horizon_days", "model"]
    ):
        weights = group["pair_count"].to_numpy(dtype=float)
        complete = group["complete"].to_numpy(dtype=bool)
        zero_probability = group["true_probability"].eq(0).to_numpy()

        def average(column):
            values = group[column].to_numpy(dtype=float)
            return float(np.average(values, weights=weights))

        row = {
            "horizon_days": int(days),
            "model": model,
            "eligible_pairs": int(weights.sum()),
            "independent_ids": int(group["id"].nunique()),
            "forecast_coverage": float(
                weights[complete].sum() / weights.sum()
            ),
            "unresolved_pairs": int(weights[~complete].sum()),
            "complete_zero_probability_pairs": int(
                weights[complete & zero_probability].sum()
            ),
        }

        # Ordinary scores require complete forecasts on every case.
        for column in ("log_loss", "brier"):
            row[column] = average(column) if complete.all() else np.nan

        # These quantities retain every eligible validation case.
        for column in (
            "log_loss_lower",
            "log_loss_upper",
            "brier_failure_penalized",
        ):
            row[column] = average(column)

        rows.append(row)

    return pd.DataFrame(rows)

def evaluate_baselines():
    paths = project_paths()
    dataset = manifest()
    records = dataset["records"]

    fit_run = "baseline_pooled_20261018T150758_752931Z"
    parent_results = paths.root / "results" / "runs" / fit_run
    receipt_path = (
        paths.root / "provenance" / "runs" / fit_run / "run.json"
    )
    receipt = json.loads(receipt_path.read_text())
    fitted = receipt["config"]

    expected = {
        "dataset_release": "per-drifter-cleaned-20261017-v7",
        "scenario": "pooled",
        "target": "endpoint",
        "origin_population": "R",
        "grid_degrees": 1,
        "horizons_days": [7, 30],
        "tolerance_hours": 0,
        "B2_predictors": ["origin_cell_1"],
        "weighting": "equal_eligible_pairs",
        "contract_sha256": file_sha256(
            paths.root / "docs" / "contract" / "data_contract_v1.0.xlsx"
        ),
        "dataset_manifest_sha256": file_sha256(
            paths.asset("current_dataset_manifest", verify=True)
        ),
    }

    if dataset["version"] != expected["dataset_release"]:
        raise RuntimeError("Unexpected dataset release.")

    for key, value in expected.items():
        if fitted.get(key) != value:
            raise RuntimeError(f"Parent experiment mismatch: {key}")

    if (
        fitted.get("validation_used") is not False
        or fitted.get("final_test_access") is not False
    ):
        raise RuntimeError("Parent fit used a protected partition.")

    if receipt["catalog_sha256"] != file_sha256(
        paths.root / "configs" / "assets.json"
    ):
        raise RuntimeError("Asset catalog changed after fitting.")

    model_hashes = {
        "B1_probabilities.csv":
        "3d2b34a5ed3b13b218ff0e9a3cdeb4a75a69bc7c57938de85777871286a90be8",
        "B2_probabilities.csv":
        "92527ea53008f58402b19b3fa6e4b1a5d82b3dc2178d9b6841de280b2bdf7305",
    }

    for filename, checksum in model_hashes.items():
        if file_sha256(parent_results / filename) != checksum:
            raise RuntimeError(f"Saved model changed: {filename}")

    b1 = load_probability_table(
        parent_results / "B1_probabilities.csv",
        ["horizon_days"],
    )
    b2 = load_probability_table(
        parent_results / "B2_probabilities.csv",
        ["horizon_days", "origin_cell_1"],
    )

    if set(b1) != {(7,), (30,)}:
        raise RuntimeError("Missing B1 horizon.")

    train_ids = {
        int(sid)
        for sid, record in records.items()
        if record["historical_split"] == "train"
    }
    validation_ids = {
        int(sid)
        for sid, record in records.items()
        if record["historical_split"] == "validation"
    }

    if train_ids != set(fitted["historical_training_ids"]):
        raise RuntimeError("Historical training membership changed.")

    if train_ids & validation_ids:
        raise RuntimeError("Training and validation IDs overlap.")

    if any(
        records[str(sid)]["pool"] != "train"
        for sid in validation_ids
    ):
        raise RuntimeError("Validation contains a protected ID.")

    index = pd.read_csv(
        paths.asset("current_dataset_index", verify=True)
    )
    r_ids = set(
        index.loc[index["in_R"].eq(True), "id"].astype(int)
    )
    reading_ids = sorted(validation_ids & r_ids)

    print("Frozen model checks passed.")
    print("Historical validation IDs:", len(validation_ids))
    print("Validation IDs visiting R:", len(reading_ids))
    print("Final-test access: disabled")

    config = {
        **expected,
        "stage": "baseline_validation",
        "parent_fit_run": fit_run,
        "parent_receipt_sha256": file_sha256(receipt_path),
        "model_table_sha256": model_hashes,
        "historical_validation_ids": sorted(validation_ids),
        "read_validation_ids": reading_ids,
        "models": ["B0", "B1", "B2"],
        "refitted": False,
        "validation_used": True,
        "final_test_access": False,
        "source_code_sha256": code_hash(),
        "scoring": {
            "log_loss": "natural_log_without_clipping",
            "brier": "unhalved_multiclass",
            "unresolved_penalty": "extra_unobserved_failure_outcome",
        },
    }
    run_id = datetime.now(timezone.utc).strftime(
        "baseline_validation_%Y%m%dT%H%M%S_%fZ"
    )
    run = paths.create_run(run_id, config)

    @lru_cache(maxsize=65536)
    def cached_score(model, days, origin, destination):
        if model == "B0":
            probabilities = {origin: 1.0}
        elif model == "B1":
            probabilities = b1[(days,)]
        else:
            probabilities = b2.get((days, origin))

        if probabilities is None:
            return score_distribution({}, destination, unresolved=1.0)

        return score_distribution(probabilities, destination)

    source = PreparedSource()
    ledgers = []
    score_rows = []

    for completed, drifter_id in enumerate(reading_ids, start=1):
        if source.cohort.loc[drifter_id, "split"] != "validation":
            raise RuntimeError("Unexpected validation membership.")

        track, arrays, events = load_track(source, drifter_id)
        origins = origin_indices(track, arrays, population="R")

        for days in (7, 30):
            if len(origins) == 0:
                continue

            endpoint, _ = generate(
                track,
                arrays,
                events,
                drifter_id,
                origins,
                days=days,
                scenario="pooled",
                tolerance=0,
            )
            ledgers.append(endpoint)

            eligible = endpoint.loc[endpoint["reason_code"].eq(0)]

            if (
                not eligible["time_error_seconds"].eq(0).all()
                or not eligible["realized_duration_seconds"].eq(
                    days * 86400
                ).all()
            ):
                raise RuntimeError("Exact endpoint matching failed.")

            if (
                eligible["destination_cell_1"].eq(-1).any()
                or not eligible["outside"].eq(
                    eligible["destination_cell_1"].eq(-2)
                ).all()
            ):
                raise RuntimeError("Invalid eligible destination.")

            groups = (
                eligible.groupby(
                    ["origin_cell_1", "destination_cell_1"]
                )
                .size()
                .reset_index(name="pair_count")
            )

            for row in groups.itertuples(index=False):
                origin = int(row.origin_cell_1)
                destination = int(row.destination_cell_1)

                for model in ("B0", "B1", "B2"):
                    score_rows.append({
                        "id": drifter_id,
                        "horizon_days": days,
                        "origin_cell_1": origin,
                        "destination_cell_1": destination,
                        "pair_count": int(row.pair_count),
                        "model": model,
                        **cached_score(model, days, origin, destination),
                    })
        if completed % 10 == 0 or completed == len(reading_ids):
            print(
                f"Scored {completed}/{len(reading_ids)} IDs",
                flush=True,
            )
    if not score_rows:
        raise RuntimeError("No eligible validation pairs.")

    ledger = pd.concat(ledgers, ignore_index=True)
    scores = pd.DataFrame(score_rows)
    summary = summarize_validation(scores)

    qualification = (
        ledger.groupby(["id", "horizon_days", "reason_code"])
        .size()
        .reset_index(name="pair_count")
    )
    qualification["reason"] = qualification["reason_code"].map(
        REASONS
    )

    eligible_totals = (
        ledger.loc[ledger["reason_code"].eq(0)]
        .groupby("horizon_days")
        .size()
        .to_dict()
    )

    for model in ("B0", "B1", "B2"):
        scored_totals = (
            scores.loc[scores["model"].eq(model)]
            .groupby("horizon_days")["pair_count"]
            .sum()
            .to_dict()
        )
        if scored_totals != eligible_totals:
            raise RuntimeError(f"Validation case mismatch: {model}")

    tables = {
        "validation_pairs.csv": ledger,
        "validation_score_groups.csv": scores,
        "validation_qualification.csv": qualification,
        "validation_summary.csv": summary,
    }
    output_hashes = {}

    for filename, table in tables.items():
        payload = table.to_csv(
            index=False, na_rep="NA"
        ).encode("utf-8")
        destination = paths.publish(
            run["results"] / filename,
            lambda stream, data=payload: stream.write(data),
        )
        output_hashes[filename] = file_sha256(destination)

    payload = json.dumps(
        {"completed": True, "output_sha256": output_hashes},
        indent=2,
    ).encode("utf-8")
    paths.publish(
        run["provenance"] / "outputs.json",
        lambda stream: stream.write(payload),
    )

    print("\nValidation summary:")
    print(summary.to_string(index=False))
    print("\nValidation scoring completed.")
    print("Results:", run["results"])
    print("Provenance:", run["provenance"])

if __name__ == "__main__":
    check_scoring()  
    evaluate_baselines()
