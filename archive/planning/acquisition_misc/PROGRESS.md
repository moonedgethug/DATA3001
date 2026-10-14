# Hourly acquisition execution record

Authority: final Data Contract v1.0 Excel, identified by SHA-256 in `manifests/authority.json`, plus the user's 2026-10-12 execution instructions. This file records execution; it introduces no replacement research contract.

1. Source verified: NOAA public AWS `latest/gdp-v2.01.1.zarr/`, asset history explicitly identifies v2.01.1. Frozen consolidated metadata and complete object inventory saved.
2. All 19,396 official integer GDP IDs assigned using stable SHA-256 with seed 20261004; manifest saved before any domain selection. No ratio balancing or reassignment.
3. R serialized from the existing corridor vertices and contractual intersection window. Boundary included, longitude-first CRS84.
4. Complete scan of 197,214,787 hourly longitude/latitude records discovered 463 R IDs. Six-hour data supplied no ID whitelist.
5. Nine contractual boundary tests pass, including known first exit before signal loss, return and later drogue loss, unknown-state exclusion, and chunk-boundary preservation.
6. Small training-only audit passed: 8 IDs, 41,619 rows. Recorded peak RSS 175,915,008 bytes. Real endpoint/stopped examples retain different results where appropriate.
7. All 463 R IDs downloaded completely: 323 train, 73 validation, 67 test; 6,243,277 source records.
8. Development-only path diagnostic used exactly 396 train/validation IDs, zero test IDs. Observed extents [-80.93445,20.78577,-8.11419,54.71530]; provisional conservative acquisition envelope [-86,15,-3,60]. Final D remains unfrozen. Retrieved 3,741 IDs and 39,107,061 complete source rows, including 3,278 downstream-only IDs. Global assignments are unchanged.
9. COMPLETE: raw-byte SHA-256 verification passed for all 8,075 fetched source objects, including additional time chunks used to measure the actual corpus cutoff. All 60 source fields exported and independently re-read with matching value-byte hashes. Standard xarray reader opens 3,741 trajectories / 39,107,061 observations / 62 variables (60 source + 2 provenance). Source/local per-ID counts and current source/configuration/code/environment bindings reconcile. Nine rule tests pass.
10. Acquisition-only findings: zero duplicate/nonincreasing timestamps; 13,276 missing-hour intervals, all positive integer-hour intervals; 1,366,330 usable position/time rows with missing SST retained. No scientific cleaning, model fitting, support sufficiency claim or final test evaluation. Final D remains unfrozen.

Implementation rulings:
- Official GDP ID is the source int64 buoy ID, not WMO or trajectory row number. Canonical hash input is ASCII `20261004:<positive-decimal-ID>`.
- Raw data are byte-identical source objects, with If-Match ETags and local SHA-256. The local source-object cache is a partial global asset and must only be read through selected, checked trajectory intervals.
- Complete means the full available source trajectory for each selected ID, including pre-R history and all later visits. It does not promise an observed endpoint for every horizon.
- `gap` describes the original sampling interval, not a missing-hour flag. Both are retained separately.
- Global metadata time-coverage attributes are preserved verbatim; reported subset ranges will be computed from actual timestamps.
- Source drogue flags and loss-date metadata are retained without rewriting. Missing/zero metadata conventions and fixed-regime eligibility remain explicit formal-QC questions; acquisition does not create physical measurements.

Resolved execution issues:
- Use `shapely.geometry` for geometry serialization helpers in the installed Shapely version.
- CSV normalizes source rowsize int32 to int64. Normalize the in-memory manifest column to int64 for an exact repeat-read comparison; saved split assignments are unchanged.
- Completed download futures now return no byte buffer, preventing total-download-sized memory retention. Source bytes remain in the checked cache.
- Independent review found an unknown desired regime could equal unknown observed flags in the small reference classifier. Regression reproduced the error; explicit 0/1 fixed-regime guard corrected it. Nine tests pass; no raw data or current 0/1 pilot labels changed.
- xarray 2026.9.0 requires Zarr-Python 3 and could not read with the acquisition library Zarr-Python 2.18.7. Pinned xarray 2025.3.1; a standard reader now opens all 62 variables and exact dimensions. Environment lock updated and full final verification repeated to bind the tested environment.

Independent read-only review completed:
- No critical acquisition defect; global hash assignments, ID offsets, full interval selection and development-only geometry provenance confirmed.
- Export still needs executed source/readback checks and independent full source hash verification before delivery.
- Deferred minor: cached geometry/discovery identity guards assume this frozen run. Reuse with changed geometry requires a fresh query namespace/manifest; the frozen run does not change these inputs.
- Unknown drogue-date interpretation, formal QC, stratified support and model performance are subsequent scientific work, not download completion claims.


## 2026-10-12 formal preparation completed with support limitations

- 3,741 IDs and 39,107,061 original hourly records retained; original observation fields independently compared for every row.
- Frozen source/ID splits verified; 8,075 cached objects and all60 selected source-field value hashes rechecked.
- Source dictionary,31-aspect crosswalk, field-specific rule register, isolated-convention log, GSHHG states, origin/event and separate endpoint/stopped ledgers delivered.
- All candidate counts reconcile;17 consequential semantic tests plus5 real source regressions and on-demand integer days1–365 checks passed.
- 40,540 owned output hashes passed; historical code/checkpoint versions and implementation corrections preserved.
- Fixed-drogued365-day validation DJF has no eligible endpoint/stopped observations; MAM has no stopped observations. Predictive acceptance remains unperformed.
- Readiness/report/handover: `preparation/READINESS_REPORT.md`, `preparation/docs/MODELLING_HANDOVER.md`, `preparation/audit/preparation_verification.json`.

## Architecture audit additions — 2026-10-13

Completed versioned regional wet areas and whole-R release weights, short-lag/remainder ID support, depth/hardware stratification, explicit annual/grouped-fold coverage, and corrected source-position failure attribution. 41 tests pass; 9,676 source-linked aggregate/origin input hashes and counts reconcile. Original source data, global split, geometry and historical freeze are preserved. Additional zero-depth IDs 7706157/7706158 retain 3,022 drogued D origins. DEPTH-01 remains pending architecture policy. See `preparation/remediation_20261013/README.md` and `audit/verification.json`. No prediction model fitted or accuracy claim made.
