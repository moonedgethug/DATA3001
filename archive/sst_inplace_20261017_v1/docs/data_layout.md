# Current data: one file per drifter

**Current stage: temperature feature-group cleaning.** Use
`data3001.sst_sparse_current.read_sst_track` to include the working total temperature
`sst_use_K`. Vessel-recovery tails have now been physically removed from current files;
this is no longer only a reader-level exclusion. See the
[full temperature-group audit](../results/runs/temperature_group_audit_20261017_v1/REPORT.md).
Total SST has no missing values in R, but the temperature group is not yet closed.

The [current total-SST-only comparison](../results/runs/total_sst_reference_audit_20261017_v1/REPORT.md)
adds 49 reference-corroborated working corrections and labels all 5,547 remaining
missing totals as numeric NA with the existing `sst_reason` code
`unavailable_after_last_good_on_grounding_ID`. The current default view is
`total_sst_reference_audit_20261017_v1`. Another 2,584 compared temperature points
remain unresolved (213 in R). Component reconstruction is outside this step.

The active release is **per-drifter-cleaned-20261017-v2**. The [Data Contract v1.0](contract/data_contract_v1.0.xlsx) remains the scientific authority. Original affected files and configurations are archived under `archive/recovery_tail_removal_20261017_v1/`. The prior release and earlier receipts describe pre-removal source evidence.

## What to open

```text
data/
  train/   3,224 files: original train + validation IDs
  test/      517 files: unchanged final-test IDs
```

Each `<integer-ID>.parquet` contains **all retained hourly records for that ID after recovery-tail removal**, including positions outside R and D. Nothing is cropped to the release region. Across both pools there are **3,741 IDs and 39,099,193 rows**, with all 130 fields retained. Other quality flags and unresolved cases remain explicit. Availability is not the same as analytical eligibility.

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
print(frame.shape)                    # (2317, 130)
print(frame[["id", "time_UTC", "lat", "lon", "regime"]].head())
context = frame.attrs["data3001"]      # embedded per-ID provenance
```

`read_track` checks the file against the manifest and returns every column and row. It does not filter on QC, R membership, drogue status or split. Iterate over IDs to limit memory use. Build derived tables in a new `results/runs/<run_id>/` rather than modifying input files.

For authorised technical review of final-test data, `read_track(id, allow_test=True)` is an explicit opt-in. Routine development should not opt in. A direct pandas/filesystem read bypasses that workflow guard; filesystem separation is not an operating-system security boundary.

## All features are retained

There are **130 columns per file**:

- The union of all **62 acquired arrays** and **67 existing prepared columns** has 109 distinct names. Twenty source hourly columns overlap the prepared columns. The 62 arrays comprise 20 native hourly variables, 40 native trajectory metadata variables and two acquisition provenance arrays.
- **12 text companions** decode fixed-byte metadata for inspection. Original binary values remain in their original columns. Invalid UTF-8 has a null companion; its original bytes remain available.
- **Nine release annotations** retain pool membership, historical split, pre-correction labels, unknown reasons and official correction evidence.

Trajectory metadata are repeated as typed constants across an ID's rows. Native source attributes and NumPy dtypes are also retained in Arrow field metadata; per-ID correction records are embedded in `schema.metadata[b'data3001']`. The exact frozen source objects, original schemas and old outputs remain in the archive.

`drogue_status` is the native hourly product flag. **`regime` is the approved research label: `1` drogued, `0` undrogued, `-1` unknown.** The two fields can differ after official evidence corrections; neither has been deleted. `drogue_lost_date == 0` denotes uncertain source metadata and must not be confused with `regime == 0`. A NaN loss date is not generically proof of attachment: the 44-ID correction has specific source evidence.

| Unknown reason | Hours | Meaning |
|---|---:|---|
| `uncertain_from_start` | 495,555 | 68 IDs with the audited zero-loss uncertainty code |
| `unresolved_boundary` | 9 | Nine boundary hours lacking resolved official evidence |
| `beyond_attached_evidence` | 683 | Tail hours beyond the documented attached-through bound |

Unknown hours remain `regime = -1`. Known hours have a null unknown-reason field. This migration performs no correlation, wind-assisted or model-based imputation.

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

The full audit reads every archived file and every current field, then compares 300 representative endpoint/stopped label fingerprints. It can take several minutes and requires the retained source/archive bundle. The pair command is a qualification check, not a fitted probability forecast. Add a unique `--run-id` to save new labels and a receipt identifying the source, release, code and environment.

## Sourced temperature reconstruction

The verified [baseline SST reconstruction report](../results/runs/sst_reconstruction_20261016_v1/REPORT.md)
provides the original reconstructed temperature view for both pools. Canonical files above remain
byte-identical. Corresponding per-ID sidecars in that run's `train/` and `test/`
join on `(id, source_obs)` without losing any source field or record. Use the
new `sst_use_K` field for the reconstructed total SST; the report supplies the
reading example, method codes and provenance. Route/error annotations are not
automatically selected model predictors.

Daily OISST does not identify GDP `sst1`/`sst2` components or the original GDP
standard errors. Those native fields are retained, and new source-only error
bounds are explicitly distinguished from total reconstruction uncertainty.
Residual unknowns remain available to the core position-based model. This run
does not establish improved destination prediction or new seasonal/year support.

### Completed three-corner extension

The [coastal extension report](../results/runs/sst_coastal_extension_20261017_v1/REPORT.md)
and [approved method](sst_coastal_extension_plan.md) describe the incremental
17 October update. Method `4` uses linear triangular interpolation inside the
three available source corners; method `5` uses normalized available bilinear
weights outside their triangle. Both retain the no-cross-land geometry check.
The outside route is explicitly an estimate with weaker spatial support, not
an equivalent-accuracy observation. This update adds 1,126 temperatures (121
in R); 36,860 remain unknown (891 in R). It changes no research eligibility.

The extension remains a frozen parent of the current pilot view below.

### Completed pilot temperature view

The [pilot completion report](../results/runs/sst_pilot_completion_20261017_v2/REPORT.md)
records 795 additional four-corner OISST estimates in R and 81 additional
four-corner estimates from the official 0.05-degree NOAA OceanWatch CoralTemp
v1.0 archive. The 795 retain explicit diagnostics for coarse-grid/coastline
conflicts; accepting their finite source values does not certify coastline
geometry. The 81 use the delivered archive's actual coordinates, daily dates,
units and missing-value rules. All 81 have four finite corners, so the approved
three-corner fallback was not needed for this set.

That frozen pilot view had **35,984 unresolved hours globally and 15 in R**. Of the
15, 13 remain under native high-temperature review and two have unqualified
position/mapping. No suspect values or coordinates were silently repaired.
Fine SST is daily nighttime background, not recovered hourly sensor data;
its uncertainty field is unavailable and remains unknown. In 16 preselected
development comparisons, fine-source MAE was 0.525 K versus 0.304 K for OISST.
This small diagnostic does not establish accuracy for the 81 coastal cases or
justify claiming that finer spatial resolution improves forecasts.

Use the following explicit run to reproduce that frozen pilot view:

```python
from data3001.sst_completion import read_sst_track
frame = read_sst_track(22165, run="sst_pilot_completion_20261017_v2")
```

It retains all original columns and rows, verifies the canonical and selected
temperature files, uses complete updated sidecars for three newly changed IDs,
and inherits the coastal-extension/baseline sidecars for other IDs. Raw `sst` remains unchanged;
`sst_use_K` is the reconstructed working covariate. Source-only SD bounds remain
distinct from total reconstruction uncertainty. Final-test access still requires
an explicit `allow_test=True` for an authorized purpose. Development-only
simulated corner removal does not establish real coastal or forecast accuracy.

The earlier pilot v1 is retained for provenance, but is superseded for reading:
its fine-source stage encountered a local read-only-array error. The corrected
v2 decodes an owned array, has no source-download failures, and retains the
same interpolation rules. V1's errors must not be interpreted as missing
official observations. No grounding-based record deletion or new model state
has been implemented; trajectory-level `typedeath` is not an hourly state.

### Current sparse-source temperature view

The user's subsequent decision removed temperature-specific land-path and
water-support-hull vetoes. The [current completion report](../results/runs/sst_sparse_completion_20261017_v2/REPORT.md)
and [execution method](sst_sparse_completion_plan.md) supersede those old
reconstruction gates. Four valid corners use bilinear interpolation; three
use triangle/normalized weights; two use WGS84 inverse-distance weights with
exponent 1; one uses the actual available source value. Methods and source
distances remain explicit. A single-source value is a coarse approximation.

This update adds **24,810** temperatures across both pools, including the final
two mapping-disagreement cases in R. It resolves all 36 original zero-corner
cases through actual finer NOAA sources. **11,174** working total-SST values
remain unknown: 5,547 on later dates than an eventually grounded ID's official
last-good date, 5,365 after vessel recovery's last-good date, and 262 native
high-temperature review cases. Only **13** remain in R, all under that review.

The new estimates include 9,785 rows with old unqualified mapping flags. Those
flags were not used to veto SST, and remain unchanged for research provenance.
Temperature admission does not rewrite frozen transition/endpoint eligibility.
For 2,600 terminal-day estimates the event hour is unknown: the ledger records
that uncertainty rather than promoting them to confirmed floating samples.
The official last-good date is not asserted to be a first-grounding timestamp.

```python
from data3001.sst_sparse_current import read_sst_track
frame = read_sst_track(139080)
# Raw sst remains unchanged; the reconstructed covariate is sst_use_K.
```

This historical entry is superseded by the current cleaning report linked above. It inherited previous temperature sidecars
where unchanged, retains every canonical row/field, and preserves the test
access guard. The first sparse run `sst_sparse_completion_20261017_v1` is
superseded: a datetime storage-unit error incorrectly held eligible records.
Use v2, which independently matches parsed epochs to the original numeric
metadata. Its report and receipts describe actual source acquisitions. No
original observations, components, native errors, labels or pools were edited.
