# SST reconstruction: completed run

Both pools have been processed with the same frozen rules. This is retrospective
temperature-covariate reconstruction, not destination modelling or a forecast
accuracy result. Data Contract v1.0 remains the authority.

## Results

| Pool | Temperature route | All retained hours | Hours in R |
|---|---|---:|---:|
| test | Accepted native | 4,989,395 | 62,115 |
| test | OISST bilinear background | 166,135 | 1,001 |
| test | Unknown / unresolved | 8,239 | 7 |
| train | Accepted native | 32,737,516 | 302,617 |
| train | OISST bilinear background | 1,176,026 | 14,486 |
| train | Native short-gap interpolation | 3 | 0 |
| train | Unknown / unresolved | 29,747 | 1,005 |

All 3,741 IDs, 39,107,061 hourly records and 130 original columns are preserved
in the canonical release, with every original per-ID file checksum unchanged.
The native fields are not silently overwritten. New sidecars in `train/` and
`test/` contain one row for every original `(id, source_obs)` key.

Use **`sst_use_K`** as the reconstructed total-temperature covariate. Method
codes are `0` native, `1` external background, `2` native short gap, `3` unknown.
`sst_reason` explains the route. It is deliberately possible to remain unknown.
Other new route/source/uncertainty fields are audit information; this run does
not select them as prediction features. Otherwise qualified core position
pairs must not be discarded merely because SST is unknown. A temperature-based
extension must declare its missingness handling and compare with the core model
on the same held-out release population.
`unknown_reasons.csv` separates unresolved finite native temperatures, position/
mapping exclusions, coastal-stencil refusals and other unavailable source
stencils; the ID-level ledger permits case review without deleting records.
Unknown-reason counts are exclusive primary reasons. One of the 262 high-temperature
quarantines also fails mapping and is counted under that primary reason.
The dataset's source `sst_ok` flags are unchanged; the new view quarantines 262
otherwise source-accepted observations above 45 C, without calling disagreement
with OISST proof that a native measurement is wrong.

The external branch uses the same UTC calendar day and four surrounding actual
0.25-degree OISST grid centres. Both frozen GSHHG masks must classify the entire
stencil rectangle as water. No three-corner renormalisation or distant nearest
ocean substitution occurs. The fallback uses only accepted native brackets,
at most three missing hours, complete intervening hourly positions/mapping and
no unresolved historical motion-review flags. No trajectory rows are invented.

## Temperature-related errors

| Pool | Source-only SD bound available | Total SE available (native only) |
|---|---:|---:|
| test | 5,155,530 | 4,989,395 |
| train | 33,913,545 | 32,737,516 |

`sst_source_sd_bound_K` is a **source-only propagated SD upper bound**, using
the sum of the nonnegative interpolation weights times the source SDs. It does
not assume independent errors. `sst_error_kind` identifies the estimator.
This bound excludes spatial/temporal interpolation and representation error;
it is not the total SE of the reconstructed hourly temperature.

`sst_total_se_K` retains native GDP SE when a native temperature is selected;
it remains unknown for reconstructed temperatures. GDP `err_sst`, `err_sst1`
and `err_sst2` describe the original GDP estimator and remain unchanged. Daily
OISST also cannot identify GDP's non-diurnal `sst1` and diurnal `sst2`; these
are preserved, including genuine missingness. OISST climatological anomaly is
not substituted for `sst2`.

## Validation and its limits

The frozen development-only experiment masks 2,748 known hourly temperatures
in contiguous three-hour blocks, with seasons and ID identities recorded.
The table below compares the two methods on the **same eligible masked cases**.
Full season × regime × location paired results and individual-method coverage
are in `validation_paired_metrics.json` and `validation_metrics.json`.

| Location | Method | Common masked hours | IDs | MAE (K) | RMSE (K) | Bias (K) |
|---|---|---:|---:|---:|---:|---:|
| All masked development | oisst_K | 2,715 | 477 | 0.3114 | 0.5039 | -0.0266 |
| All masked development | linear_K | 2,715 | 477 | 0.0237 | 0.0871 | 0.0009 |
| Pilot R | oisst_K | 1,776 | 380 | 0.3328 | 0.5273 | -0.0291 |
| Pilot R | linear_K | 1,776 | 380 | 0.0239 | 0.0568 | -0.0023 |

Smooth short masked gaps favour linear interpolation; they do not represent
long sensor outages or IDs without any native SST. This experiment does not
justify changing the approved external-first routing, infer missing-at-random
behaviour, or prove better destination forecasts. OISST assimilates buoy data,
so agreement is not necessarily independent measurement validation. The final
test was processed under the frozen rule and was not used for method tuning.

Masking is applied after NOAA's hourly SST estimation. Neighbouring native
estimates come from overlapping original fitting windows and may share the
underlying measurements that informed a hidden hour. This measures
post-processing reconstruction agreement, not the recovery of temperatures
after deleting raw sensor measurements. A very small linear-interpolation
error is therefore not independent evidence of physical accuracy.

Final daily OISST and two-sided native anchors are retrospective inputs. They
cannot be presented as available when a live forecast is issued. Seasonal and
365-day destination support have not increased merely by adding temperature.

## Source and reproducibility

The active source is **NOAA NCEI OISST v2.1 Final AVHRR-only**, through the NOAA
CDR page's official AWS Zarr bucket. Only required spatial chunks/dates were
acquired. Every daily asset's product, finality, date, packing and actual noon
UTC time are checked; actual fixed-grid coordinates were checked annually.
Eight variable/date comparisons with four original NCEI NetCDF files passed.

The byte-preserving SQLite cache holds 74,068 source objects
(1331.3 MB stored payload). It includes actual source metadata,
compressed source chunks, exact URLs, retrieval times, ETags and SHA256 hashes.
`source_comparison.json` records independent original-file comparisons.
`source_plan.json`, `effective_config.json`, stage receipts and object inventories freeze
the scientific and source dependencies. The abandoned PSL planning route is
not used by these results. `config.json` retains the initial preparation freeze;
the effective configuration explicitly replaces its provisional motion gate.
Missing cloud objects are checked against same-date original NCEI v2.1 final
files; `node_sst_sources.csv` and `node_err_sources.csv` record the actual backend
for every date. Download failures never become fabricated measurements.
Runtime versions and exact package pins are in `environment_versions.json` and
`requirements-reconstruction.txt` (including the NetCDF4 fallback dependency).

`targets.parquet`, `nodes.parquet`, `matched_temperature.parquet` and
`matched_errors.parquet` identify every external stencil/date/weight. For
local interpolation, the per-ID sidecar records both native anchor keys.
`input_inventory.csv` and `output_manifest.json` retain per-ID source/output
hashes. `verification.json` establishes preservation and reconciliation;
`independent_checks.json` and `worked_examples.json` check actual values.

## Read a complete track with its new temperature fields

Run from the project root after installing the existing project environment:

```python
from pathlib import Path
import pandas as pd
from data3001.dataset import read_track

run = Path("results/runs/sst_reconstruction_20261016_v1")
native = read_track(22165)  # use allow_test=True only for authorised test access
extra = pd.read_parquet(run / "train" / "22165.parquet")
track = native.merge(extra, on=["id", "source_obs"], validate="one_to_one")
assert len(track) == len(native)
```

All original fields remain accessible. Do not replace an original GDP field
with a derived field under the original field name. Do not modify this frozen
run after verification; changed methods require a new run ID.

## Execute or verify

`cloud.py preflight` validates source equivalence; `cloud.py sst` acquires
temperature; `run.py temperature` constructs it. Only then does `cloud.py err`
acquire corresponding errors and `run.py errors` create uncertainty annotations.
`run.py verify` and `independent_audit.py` validate the final outputs. All calls
use the existing `.venv/bin/python` and are made from the project root. Exact
code and evidence hashes are pinned; do not edit and silently resume.

The formula/guard tests and complete existing suite passed (107 tests) before
acquisition. Final verification receipts, not a count of tests alone, support
the completion claim. No Git commit or push was performed.

Sources: [NOAA OISST product](https://www.ncei.noaa.gov/products/optimum-interpolation-sst),
[NOAA official cloud access](https://www.ncei.noaa.gov/products/climate-data-records/sea-surface-temperature-optimum-interpolation),
and the frozen GDP SST paper, DOI 10.1038/s41597-022-01670-2.
