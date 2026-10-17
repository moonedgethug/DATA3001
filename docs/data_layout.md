# Current data: one file per drifter

**Current stage: feature cleaning and review.** All approved total-SST fills and
corrections are stored directly in the existing **`sst`** column of each
`data/train/<id>.parquet` and `data/test/<id>.parquet` file. No extra temperature
feature or merge is needed. Read the files directly or use
`data3001.dataset.read_track`.

The active release is **per-drifter-cleaned-20261017-v7**. SST is in **Kelvin**,
stored as float64 to preserve the approved interpolation precision. The release has 62 columns after the user-approved removal of 67 registered fields. The four original uncertainty fields `err_lat`, `err_lon`, `err_ve`, and `err_vn` remain unchanged. The approved drogue labels are stored in the existing
`drogue_status` column, with no `regime` column. This consolidation changes no
state values, retained field values, retained rows, row order or whole-ID train/test assignments. Vessel-recovery tails remain physically removed.

The actual current train/test files are distributed on `main`. See
[team download and setup](getting_started.md) for cloning, environment setup
and `verify-data`.

The [feature-projection report](../provenance/migrations/feature_pruning_20261017_v1/REPORT.md)
lists the 67 physical removals and the 62 retained columns. Exact pre-projection
files remain in `archive/feature_pruning_20261017_v1/` (test evidence under
`restricted_test`). Exact qualification projections are also distributed in
`provenance/qualification/v7/`, bound by `configs/qualification_manifest.json`.
The reader prefers this portable evidence and otherwise retains the archived
fallback. These annotations are not recreated in active files or in the normal
`read_track` result. No research eligibility rule changed.

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

## Hardware missing values

The seven official hardware fields (`DragAreaAboveDrogue`, `DragAreaOfDrogue`,
`DragAreaRatio`, `DrogueBallast`, `DrogueCenterDepth`, `DrogueLength`,
`FloatDiameter`) use numeric null for missing values in their original columns.
The v6 step normalized existing NaN values in 210 files; no additional numeric
anomalies were established. All recorded zeros and finite specifications remain
unchanged. Do not interpret zero hardware depth as an hourly drogue-state flag.
No specification was inferred or new feature added. Readers may display numeric
missing values as NA, NaN or blank; use a missing-value test rather than comparing
against the literal string `NA`. See the [normalization report](../provenance/migrations/hardware_NA_20261017_v1/REPORT.md).

## What to open

```text
data/
  train/   3,224 files: original train + validation IDs
  test/      517 files: unchanged final-test IDs
```

Each `<integer-ID>.parquet` contains **all retained hourly records for that ID after recovery-tail removal**, including positions outside R and D. Nothing is cropped to the release region. Across both pools there are **3,741 IDs and 39,099,193 rows**, with 62 fields after the approved feature projection. Existing uncertainty values, NA values and unresolved scientific cases remain unchanged; removed audit annotations remain in the archive. Availability is not the same as analytical eligibility.

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
print(frame.shape)                    # (2317, 62)
print(frame[["id", "time_UTC", "lat", "lon", "drogue_status"]].head())
context = frame.attrs["data3001"]      # embedded per-ID provenance
```

`read_track` checks the file against the manifest and returns every column and row. It does not filter on QC, R membership, drogue status or split. Iterate over IDs to limit memory use. Build derived tables in a new `results/runs/<run_id>/` rather than modifying input files.

For authorised technical review of final-test data, `read_track(id, allow_test=True)` is an explicit opt-in. Routine development should not opt in. A direct pandas/filesystem read bypasses that workflow guard; filesystem separation is not an operating-system security boundary.

## Current fields and provenance

There are **62 columns per file**. The machine-readable schema and column
dictionary describe exactly those active fields. The former 129-column release
and its complete source attributes remain archived. No new field was created.
The original 62 acquired arrays describe source acquisition, not the number of
active columns after the approved projection. The text companions and repeated
drogue-audit columns in the registered removal list are no longer active fields.

Retained trajectory metadata are repeated as typed constants across an ID's rows. Native source attributes and NumPy dtypes for retained fields remain in Arrow field metadata; per-ID correction records are embedded in `schema.metadata[b'data3001']`. The exact frozen source objects, original schemas and old outputs remain in the archive.

**`drogue_status` is the cleaned research state: `1` drogued, `0` undrogued, `-1` unknown.** It exactly contains the previously approved `regime` values; `regime` has been physically removed and is not recreated by the reader. This is an int8 categorical state, not a Boolean. Native source attributes describe the original product; cleaned attributes describe the current three-state field. Original binary flags remain in the archive. `drogue_lost_date == 0` denotes uncertain source metadata and differs from `drogue_status == 0` (undrogued). Loss dates are unchanged. A NaN loss date is not generically proof of attachment: the 44-ID correction has specific source evidence. See the [consolidation report](../provenance/migrations/drogue_status_inplace_20261017_v1/REPORT.md).

| Unknown reason | Hours | Meaning |
|---|---:|---|
| `uncertain_from_start` | 495,504 | 68 IDs with the audited zero-loss uncertainty code |
| `unresolved_boundary` | 9 | Nine boundary hours lacking resolved official evidence |
| `beyond_attached_evidence` | 637 | Tail hours beyond the documented attached-through bound |

These current retained counts total 496,150 unknown hours. Earlier pre-recovery-removal counts included 51 additional uncertain-from-start and 46 additional beyond-evidence hours.

Unknown hours remain `drogue_status = -1`. The detailed unknown-reason field and
its original row-level values are archived, rather than repeated in the active
62-column files. This migration performs no correlation, wind-assisted or
model-based imputation.

Retention in the active schema does **not** authorise every field as a prediction input. End dates, loss dates, future states, subsequent gaps/exits and matched outcomes are retrospective evidence. Model-stage features must be available at forecast time. Feature contribution and missing-value strategies remain later decisions.

## Development validation and final test

The `train` directory is the **development pool**, not a new random assignment. It combines 2,674 original train IDs and 550 original validation IDs. `historical_split` preserves the old assignment; `pool` describes the current directory. Original manifests and fold files are unchanged in the archive. R has 396 development visitors and 67 final-test visitors.

No new validation split has been generated. The user's approved workflow allows validation experiments within the development pool at modelling time. Each experiment must group by **complete drifter ID**, save its ID allocation, seed and purpose before fitting, and declare the chosen protocol against Data Contract clause 10. Row-wise random splits are not acceptable. Any fitted transformations or imputation use only the corresponding training portion. The final 517 test IDs remain outside model and protocol selection.

## Historical evidence and verification

The complete previous `data` tree was renamed intact to `archive/data_before_release_20261016/`. It contains raw source data, original preparation, official correction contributions, geometry, split manifests and earlier support tables. Asset names in [the catalog](../configs/assets.json) and [historical path map](../configs/legacy_paths.json) resolve those locations. Historical receipt contents and hashes were not rewritten.

Earlier global support tables predate official label corrections. They remain useful historical evidence; they are **not current full-cohort support estimates**. Recompute support using canonical tracks and the selected development protocol before modelling. DEPTH-01 and long-horizon seasonal support limitations remain unresolved; data preservation does not establish predictive accuracy.

Any downloaded checkout with the published data can run:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m data3001 verify-data
.venv/bin/python -m data3001 pair --id 22165 --days 7 --population R
```

The distributed-data audit checks current checksums, schema, row counts and
portable qualification keys without full historical parents. The deeper
`verify-migration` audit compares every surviving value, null, type, field
attribute and row key with the exact archived 129-column parent and requires
the local source/archive bundle. Earlier temperature and recovery evidence
remains linked through the parent manifest. The pair command reads the exact
qualification arrays and is not a fitted forecast. Add a unique `--run-id` to
save new labels and a receipt identifying the source, release, qualification
manifest, code and environment.

## Temperature evidence

Current files already contain the cleaned `sst`; the compatibility reader
`data3001.sst_sparse_current.read_sst_track` returns those same stored columns.
Historical temperature runs under `results/runs/` are audit evidence only. They
are not additional active datasets or extra prediction features. The
[reference audit](../results/runs/total_sst_reference_audit_20261017_v1/REPORT.md)
explains the last 49 corroborated repairs and the remaining quality cases.
