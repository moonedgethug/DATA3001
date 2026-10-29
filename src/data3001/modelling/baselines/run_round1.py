import sys

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from data3001.paths import file_sha256
from data3001.preprocessing.prep_io import code_hash
from data3001.dataset import manifest, development_ids
from data3001.paths import project_paths
from data3001.dataset import PreparedSource
from data3001.preprocessing.prep_core import REASONS
from data3001.preprocessing.prep_pairs import (
  load_track,
  origin_indices,
  generate,
)

def preview_pairs():
  drifter_id = 22165
  source = PreparedSource()

  if source.cohort.loc[drifter_id, "split"] != "train":
    raise RuntimeError("Preview requires a historical training ID.")

  track, arrays, events = load_track(source, drifter_id)
  origins = origin_indices(track, arrays, population="R")

  print("\nPreview drifter ID:", drifter_id)
  print("Candidate hourly origins in R:", len(origins))

  if len(origins) == 0:
    print("NO qualified R origins for this demonstration ID.")
    return

  columns = [
    "origin_time_UTC",
    "origin_cell_1",
    "horizon_days",
    "destination_cell_1",
    "outside",
    "time_error_seconds",
  ]

  for days in (7, 30):
    endpoint, _= generate(
      track,
      arrays,
      events,
      drifter_id,
      origins,
      days=days,
      scenario="pooled",
      tolerance=0,
    )

    eligible = endpoint.loc[
      endpoint["reason_code"].eq(0)
    ].copy()

    if not eligible["time_error_seconds"].eq(0).all():
      raise RuntimeError("Esact endpoint matching failed.")

    print(f"\nHorizon: {days} days")
    print("Eligible endpoint pairs:", len(eligible))
    print("Pair qualification summary:")
    print(
      endpoint["reason_code"]
      .map(REASONS)
      .value_counts()
      .to_string()
    )

    print("Example eligible pairs:")
    print(eligible.loc[:, columns].head(3).to_string(index=False))

def estimate_probabilities(counts, conditions):
  keys = conditions + ["destination_cell_1"]
  table = counts.groupby(keys, as_index=False)["pair_count"].sum()

  totals = table.groupby(conditions)["pair_count"].transform("sum")
  table["probability"] = table["pair_count"] / totals

  mass = table.groupby(conditions)["probability"].sum()
  if not np.allclose(mass.to_numpy(), 1.0):
    raise RuntimeError("Probability mass check failed.")

  return table

def fit_baselines():
  paths = project_paths()
  dataset = manifest()

  train_ids = {
    int(sid)
    for sid, record in dataset["records"].items()
    if record["historical_split"] == "train"
  }

  index = pd.read_csv(
    paths.asset("current_dataset_index", verify=True)
  )
  r_ids = {
    int(sid)
    for sid in index.loc[index["in_R"].eq(True), "id"]
  }
  fitting_ids = sorted(train_ids & r_ids)

  print("\nHistorical training iDs:", len(train_ids))
  print("Training IDs visiting R:", len(fitting_ids))

  # Check conditional normalization with known counts.
  toy = pd.DataFrame(
    [
      [7, 10, 10, 1],
      [7, 10, 20, 3],
      [7, 20, 20, 2],
    ],
    columns=[
      "horizon_days",
      "origin_cell_1",
      "destination_cell_1",
      "pair_count",
    ],
  )
  reference = estimate_probabilities(
    toy, ["horizon_days", "origin_cell_1"]
  )
  reference = reference.loc[
    reference["origin_cell_1"].eq(10)
  ].sort_values("destination_cell_1")

  np.testing.assert_allclose(
    reference["probability"].to_numpy(), [0.25, 0.75]
  )
  print("Estimator fixture passed.")

  source = PreparedSource()
  parts = []
  audit = []

  for completed, drifter_id in enumerate(fitting_ids, start=1):
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

      for reason, number in (
        endpoint["reason_code"].value_counts().items()
      ):
        audit.append({
          "id": drifter_id,
          "horizon_days": days,
          "reason_code": int(reason),
          "reason": REASONS[int(reason)],
          "pair_count": int(number),
        })
      eligible = endpoint.loc[
        endpoint["reason_code"].eq(0)
      ].copy()

      if eligible.empty:
        continue

      if not eligible["realized_duration_seconds"].eq(
        days * 86400
      ).all():
        raise RuntimeError("Unexpected endpoint duration.")

      part = (
        eligible.groupby(
          ["origin_cell_1", "destination_cell_1"]
        )
        .size()
        .reset_index(name="pair_count")
      )
      part.insert(0, "horizon_days", days)
      part.insert(0, "id", drifter_id)
      parts.append(part)

    if completed % 25 == 0 or completed == len(fitting_ids):
      print(
        f"Processed {completed}/{len(fitting_ids)} IDs",
        flush=True,
      )
  if not parts:
    raise RuntimeError("No eligible training paris.")

  counts = pd.concat(parts, ignore_index=True)

  b1 = estimate_probabilities(counts, ["horizon_days"])
  b2 = estimate_probabilities(
    counts, ["horizon_days", "origin_cell_1"]
  )

  support = counts.groupby(
    ["horizon_days", "origin_cell_1"], as_index=False
  ).agg(
    pair_count=("pair_count", "sum"),
    independent_ids=("id", "nunique"),
  )

  run_id = datetime.now(timezone.utc).strftime(
    "baseline_pooled_%Y%m%dT%H%M%S_%fZ"
  )
  config = {
    "dataset_release": dataset["version"],
    "scenario": "pooled",
    "target": "endpoint",
    "origin_population": "R",
    "grid_degrees": 1,
    "horizons_days": [7, 30],
    "tolerance_hours": 0,
    "B2_predictors": ["origin_cell_1"],
    "weighting": "equal_eligible_pairs",
    "historical_training_ids": sorted(train_ids),
    "read_training_ids": fitting_ids,
    "validation_used": False,
    "final_test_access": False,
    "contract_sha256": dataset["contract_sha256"],
    "dataset_manifest_sha256": file_sha256(
      paths.asset("current_dataset_manifest")
    ),
    "source_code_sha256": code_hash(),
  }
  run = paths.create_run(run_id, config)

  tables = {
    "training_counts_by_id.csv": counts,
    "training_qualification.csv": pd.DataFrame(audit),
    "B1_probabilities.csv": b1,
    "B2_probabilities.csv": b2,
    "training_support.csv": support,
  }

  for filename, table in tables.items():
    payload = table.to_csv(index=False).encode("utf-8")
    paths.publish(
      run["results"] / filename,
      lambda stream, data=payload: stream.write(data),
    )

  print("\nTraining support by horizon:")
  print(
    counts.groupby("horizon_days").agg(
      eligible_pairs=("pair_count", "sum"),
      independent_ids=("id", "nunique"),
    ).to_string()
  )
  print("\nBaseline probability tables fitted.")
  print("Validation scoring: pending")
  print("Results:", run["results"])
  print("Provenance:", run["provenance"])

def main():
  dataset = manifest()
  dev_ids = development_ids()

  expected_release = "per-drifter-cleaned-20261017-v7"

  if dataset["version"] != expected_release:
    raise RuntimeError("Unexpected dataset release.")

  if len(dev_ids) != dataset["pools"]["train"]:
    raise RuntimeError("Development ID count mismatch.")

  print("Python executable:", sys.executable)
  print("Project root:", project_paths().root)
  print("Dataset release:", dataset["version"])
  print("Stored columns:", dataset["fields"])
  print("Development IDs:", len(dev_ids))
  print("Final-test access: disabled")
  print("Setup checks passed.")
  fit_baselines()

if __name__ == "__main__":
    main()
