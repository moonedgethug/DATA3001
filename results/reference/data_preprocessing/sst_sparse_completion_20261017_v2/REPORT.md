# SST sparse-source completion (corrected replay)

This run supersedes `sst_sparse_completion_20261017_v1`. V1 misread pandas
microsecond-backed UTC timestamps as nanoseconds and incorrectly held eligible
records. V1's unconditional fine-source description did not match its empty
source receipt list; do not use it for source or coverage claims. In V2, official
epoch seconds are unit-safe and were compared exactly with each corresponding
original numeric `end_date` and observation timestamp. All earlier artifacts are
preserved; no changed source fields or an inferred grounding hour repairs this bug.

The user authorized removal of temperature interpolation land-path/support-hull
gates and estimation from four, three, two or one actual official source values.
This run inherits `sst_pilot_completion_20261017_v2` and changes previously unknown derived temperatures
only. The Data Contract, all 130 canonical fields, all 39,107,061 source rows and
all whole-ID pools are preserved. Research mapping flags and model qualifications
are not rewritten by this temperature-specific policy change.

## Result

Added **24,810** temperatures across **655** IDs.
Remaining unknown working SST: **11,174**, including
**13** in R. Existing finite/native accepted
temperatures, components and native errors remain unchanged.

| Pool | Source | Method | Hours | IDs | In R |
|---|---|---:|---:|---:|---:|
| test | OISST_v2.1 | 11 | 2154 | 68 | 0 |
| test | OISST_v2.1 | 12 | 188 | 12 | 0 |
| test | OISST_v2.1 | 13 | 2025 | 10 | 0 |
| test | OISST_v2.1 | 14 | 168 | 23 | 0 |
| train | CoralTemp_archive_v1.0 | 11 | 24 | 1 | 0 |
| train | CoralTemp_v3.1 | 11 | 9 | 1 | 0 |
| train | CoralTemp_v3.1 | 12 | 2 | 2 | 0 |
| train | CoralTemp_v3.1 | 14 | 1 | 1 | 0 |
| train | OISST_v2.1 | 11 | 10903 | 396 | 2 |
| train | OISST_v2.1 | 12 | 901 | 82 | 0 |
| train | OISST_v2.1 | 13 | 3875 | 56 | 0 |
| train | OISST_v2.1 | 14 | 4258 | 109 | 0 |
| train | OISST_v2.1 | 15 | 302 | 24 | 0 |

Methods: 11 four-corner bilinear; 12 triangle; 13 normalized available three
bilinear weights; 14 two-source WGS84 inverse-distance weights with exponent 1;
15 actual single-source value; 16 three-source inverse-distance fallback for a
zero available-bilinear-weight sum. Exact valid-source matches have unit weight.
All weights are nonnegative and sum to one; all estimates remain within the
positively weighted source range. A one-source estimate is a marked rough
approximation, not recovered hourly sensor truth.

## Official termination context and remaining rows

| Remaining reason | Hours | IDs | In R |
|---|---:|---:|---:|
| finite_native_above_45C_review_retained | 262 | 34 | 13 |
| outside_official_last_good_day_grounding | 5547 | 25 | 0 |
| outside_official_last_good_day_vessel_recovery | 5365 | 5 | 0 |

`typedeath=1/2` and the official last-good date govern the two post-terminal
categories. A later UTC date is held; the last-good marker is not claimed to
timestamp the first grounding/recovery hour. On the terminal date, background
SST can be estimated but exact event-time uncertainty remains in the ledger:
**2,600** new estimates have that context.
They are not promoted to confirmed floating states or training eligibility.
Other termination causes do not prove absence of an earlier grounding event.
Native >45 C quarantines are still under a separate review, not automatically
repaired by this geometry/source-count change. See `remaining_records.csv`.

No land mask blocked an estimate: **9,785**
added values have an existing unqualified mapping flag. Those flags are retained
as research evidence and are not silently changed to valid model transitions.
No native rows were deleted and no new beaching model state was added.

## Sources and uncertainty

Actual added source counts are `{'CoralTemp_archive_v1.0': 24, 'CoralTemp_v3.1': 12, 'OISST_v2.1': 24774}`. Most estimates reuse frozen,
source-verified NOAA OISST v2.1 same-date daily fields. Only original zero-corner
cases request new fine SST. The candidates are the NOAA OceanWatch
`CRW_sst_v1_0` daily nighttime archive for 2014 and NOAA STAR CoralTemp v3.1
daily files for three needed 2022 dates. The actual fetched objects and any
failures are recorded in the source receipt/failure lists; no absent response
is described as an observed temperature. Versions are declared separately.
Actual coordinates, UTC daily timestamps, units, packed fills, source validity
ranges and returned versions were checked. Original source responses, URLs,
retrieval times and hashes are in `sources/` and `source_receipts.json`.
Fine matching uses an enclosing stencil and, if it is empty, the nearest finite
actual source in the received 0.1-degree-halo window. It never expands to an
unbounded nearest search. A true all-missing received source is not fabricated.

The propagated source-only SD upper bound is `sum(abs(w)*sigma)` where every
positively weighted source has an SD. Fine-source SD and total reconstruction
standard error are unknown. GDP `err_sst*` are not overwritten. No correction
was fitted, and no final-test temperatures were used to select algorithms or
score predictions. More complete SST does not prove improved destination maps,
new seasonal/year support, or independence from assimilated buoy observations.

## Reading and verification

```python
from data3001.sst_sparse_current import read_sst_track
frame = read_sst_track(139080)
# Native sst is retained; use sst_use_K for the reconstructed covariate.
```

The reader resolves complete per-ID sidecars and verified parent views, retains
all native columns/rows, and still guards final-test access. All added formulas
were checked individually; original file hashes, unchanged sidecar rows, parent
artifact hashes and pool assignments were verified. `decisions.parquet` retains
source values, coordinates, weights, distances, methods and official context.
Columns named original_oisst_node*/i/j/u/v retain the original coarse-stencil
provenance even for fine-source estimates; source_family/source_object and
point*/corner* identify the actual matched fine sources without reusing coarse
node IDs as fine-grid indices.
No Git commit/push was performed.
