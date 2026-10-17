# Current data: one file per drifter

**Current stage: feature cleaning and review.** All approved total-SST fills and
corrections are stored directly in the existing **`sst`** column of each
`data/train/<id>.parquet` and `data/test/<id>.parquet` file. No extra temperature
feature or merge is needed. Read the files directly or use
`data3001.dataset.read_track`.

The active release is **per-drifter-cleaned-20261017-v5**. SST is in **Kelvin**,
stored as float64 to preserve the approved interpolation precision. The release has 129 columns. The approved drogue labels are stored in the existing
`drogue_status` column, with no `regime` column. This consolidation changes no
state values, other fields, retained rows, row order or whole-ID train/test assignments. Vessel-recovery tails remain physically removed.

For an official eventual-grounding ID (`typedeath == 1`), **`sst` is numeric NA
when `time > end_date` and `end_date` is finite and positive**. Do not refill these
values. The boundary is the official last-good observation time, not an observed
first-grounding hour. Records at/before that boundary keep their cleaned SST.
The rule does not infer grounding from low speed and does not affect other IDs.

There are **16,059 intentionally unavailable SST values** under this rule,
including **47 in R**. The latest step added 10,512 NA values to the previous
5,547. Positions, times, all other columns and all records remain available for
event audits; these tail records are not thereby approved as freely drifting
training examples. No SST values are missing outside the excluded context.
Another **2,582 temperature-quality comparisons remain unresolved (213 in R)**.
The historical reference audit counted 2,584 before this rule; two of those points
are now excluded SST rather than active temperature observations. Numerical
completeness does not imply quality approval.

See the [current grounding-SST report](../provenance/migrations/grounding_sst_na_20261017_v1/REPORT.md)
for the exact keys, counts, preservation checks and prior-value backups.

The [in-column SST migration report](../provenance/migrations/sst_inplace_20261017_v1/REPORT.md)
records preservation checks and counts. Original values and all earlier
reconstruction evidence are retained outside active data. Native `flg_sst`,
`err_sst` and older derived audit fields still describe the original GDP data;
they were not recalculated and must not be presented as quality/uncertainty of
replacement temperatures. The [Data Contract v1.0](contract/data_contract_v1.0.xlsx)
remains the scientific authority.

## What to open

```text
data/
  train/   3,224 files: original train + validation IDs
  test/      517 files: unchanged final-test IDs
```

Each `<integer-ID>.parquet` contains **all retained hourly records for that ID after recovery-tail removal**, including positions outside R and D. Nothing is cropped to the release region. Across both pools there are **3,741 IDs and 39,099,193 rows**, with 129 fields after the authorized removal of the redundant `regime` column. Other quality flags and unresolved cases remain explicit. Availability is not the same as analytical eligibility.

| Question | Open |
|---|---|
| Which IDs, row counts, time bounds and historical splits? | [Dataset index](../configs/dataset_index.csv), one row per ID |
| What does each column mean? | [Complete column dictionary](data_dictionary.md) |
| What are the exact schema and source attributes? | [Schema](../configs/dataset_schema.json) |
| Which release and per-file checksums? | [Manifest](../configs/dataset_manifest.json) |
| How are pairs, paths, seasons and geometry defined? | [Preprocessing guide](preprocessing.md) and the contract |
| Where is preservation demonstrated? | [Acceptance report](../provenance/migrations/data_release_20261016/acceptance.md) |

Parquet preserves types and supports reading one ID or selected columns without loading a global spreadsheet. IDs are stored as **int64**, including long IDs that spreadsheet software can round. Do not overwrite canonical data by exporting an edited spreadsheet.

## Read a development ID

After installing the existing package/environment described in [architecture](architecture.md#environment):

```python
from data3001.dataset import read_track, development_ids

ids = development_ids()
frame = read_track(22165)
print(frame.shape)                    # (2317, 129)
print(frame[["id", "time_UTC", "lat", "lon", "drogue_status"]].head())
context = frame.attrs["data3001"]      # embedded per-ID provenance
```

`read_track` checks the file against the manifest and returns every column and row. It does not filter on QC, R membership, drogue status or split. Iterate over IDs to limit memory use. Build derived tables in a new `results/runs/<run_id>/` rather than modifying input files.

For authorised technical review of final-test data, `read_track(id, allow_test=True)` is an explicit opt-in. Routine development should not opt in. A direct pandas/filesystem read bypasses that workflow guard; filesystem separation is not an operating-system security boundary.

## Current fields and provenance

There are **129 columns per file**:

- The union of all **62 acquired arrays** and **66 retained prepared columns** has 108 distinct names. Twenty source hourly columns overlap the prepared columns. The 62 arrays comprise 20 native hourly variables, 40 native trajectory metadata variables and two acquisition provenance arrays.
- **12 text companions** decode fixed-byte metadata for inspection. Original binary values remain in their original columns. Invalid UTF-8 has a null companion; its original bytes remain available.
- **Nine release annotations** retain pool membership, historical split, pre-correction labels, unknown reasons and official correction evidence.

Trajectory metadata are repeated as typed constants across an ID's rows. Native source attributes and NumPy dtypes are also retained in Arrow field metadata; per-ID correction records are embedded in `schema.metadata[b'data3001']`. The exact frozen source objects, original schemas and old outputs remain in the archive.

**`drogue_status` is the cleaned research state: `1` drogued, `0` undrogued, `-1` unknown.** It exactly contains the previously approved `regime` values; `regime` has been physically removed and is not recreated by the reader. This is an int8 categorical state, not a Boolean. Native source attributes describe the original product; cleaned attributes describe the current three-state field. Original binary flags remain in the archive. `drogue_lost_date == 0` denotes uncertain source metadata and differs from `drogue_status == 0` (undrogued). Loss dates are unchanged. A NaN loss date is not generically proof of attachment: the 44-ID correction has specific source evidence. See the [consolidation report](../provenance/migrations/drogue_status_inplace_20261017_v1/REPORT.md).

| Unknown reason | Hours | Meaning |
|---|---:|---|
| `uncertain_from_start` | 495,504 | 68 IDs with the audited zero-loss uncertainty code |
| `unresolved_boundary` | 9 | Nine boundary hours lacking resolved official evidence |
| `beyond_attached_evidence` | 637 | Tail hours beyond the documented attached-through bound |

These current retained counts total 496,150 unknown hours. Earlier pre-recovery-removal counts included 51 additional uncertain-from-start and 46 additional beyond-evidence hours.

Unknown hours remain `drogue_status = -1`. Known hours have a null unknown-reason field. This migration performs no correlation, wind-assisted or model-based imputation.

Preservation of every field does **not** authorise every field as a prediction input. End dates, loss dates, future states, subsequent gaps/exits and matched outcomes are retrospective evidence. Model-stage features must be available at forecast time. Feature contribution and missing-value strategies remain later decisions.

## Development validation and final test

The `train` directory is the **development pool**, not a new random assignment. It combines 2,674 original train IDs and 550 original validation IDs. `historical_split` preserves the old assignment; `pool` describes the current directory. Original manifests and fold files are unchanged in the archive. R has 396 development visitors and 67 final-test visitors.

No new validation split has been generated. The user's approved workflow allows validation experiments within the development pool at modelling time. Each experiment must group by **complete drifter ID**, save its ID allocation, seed and purpose before fitting, and declare the chosen protocol against Data Contract clause 10. Row-wise random splits are not acceptable. Any fitted transformations or imputation use only the corresponding training portion. The final 517 test IDs remain outside model and protocol selection.

## Historical evidence and verification

The complete previous `data` tree was renamed intact to `archive/data_before_release_20261016/`. It contains raw source data, original preparation, official correction contributions, geometry, split manifests and earlier support tables. Asset names in [the catalog](../configs/assets.json) and [historical path map](../configs/legacy_paths.json) resolve those locations. Historical receipt contents and hashes were not rewritten.

Earlier global support tables predate official label corrections. They remain useful historical evidence; they are **not current full-cohort support estimates**. Recompute support using canonical tracks and the selected development protocol before modelling. DEPTH-01 and long-horizon seasonal support limitations remain unresolved; data preservation does not establish predictive accuracy.

The complete retained checkout can run:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m data3001 verify-migration
.venv/bin/python -m data3001 pair --id 22165 --days 7 --population R
```

The full current audit compares every file with its archived predecessor and the frozen approved temperature evidence; it verifies all non-temperature fields, row keys, pool assignments, NA values and recovery exclusions. It can take several minutes and requires the retained source/archive bundle. The pair command is a qualification check, not a fitted probability forecast. Add a unique `--run-id` to save new labels and a receipt identifying the source, release, code and environment.

## Temperature evidence

Current files already contain the cleaned `sst`; the compatibility reader
`data3001.sst_sparse_current.read_sst_track` returns those same stored columns.
Historical temperature runs under `results/runs/` are audit evidence only. They
are not additional active datasets or extra prediction features. The
[reference audit](../results/runs/total_sst_reference_audit_20261017_v1/REPORT.md)
explains the last 49 corroborated repairs and the remaining quality cases.
