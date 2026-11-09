# Position-error repair: verified training-only overlay

Status: **VERIFIED_PARTIAL**. Generated 2026-11-06T08:35:24.588712+00:00.

All 355,247 authorized observations from 338 training drifters were accounted for. 332,770 (93.673%) have verified usable error values on both axes. Unresolved records remain in the overlay and in the unchanged training population.

| Measure | Observations | Share of frozen targets |
| --- | --- | --- |
| Target observations audited | 355247 | 100.000% |
| Reference observations matched | 334186 | 94.071% |
| Two-axis error usable | 332770 | 93.673% |
| Two-axis error unavailable | 22477 | 6.327% |
| Longitude accepted | 332782 | 93.676% |
| Latitude accepted | 332776 | 93.675% |

## What was repaired

Values were copied from identity-, time-, coordinate- and version-matched official native files. There was no global multiplication by 100,000. Missing markers were identified before any declared packing transform. A native zero remains unresolved rather than implying perfect certainty. A valid single axis is preserved without enabling a two-axis CI.

| axis | status | observations | percent |
| --- | --- | --- | --- |
| lon | restored_scale | 332782 | 93.67623 |
| lon | estimation_version_unresolved | 15295 | 4.30546 |
| lon | coordinate_changed | 5512 | 1.5516 |
| lon | unexplained_difference | 1398 | 0.39353 |
| lon | source_missing | 254 | 0.0715 |
| lon | zero_unresolved | 6 | 0.00169 |
| lat | restored_scale | 332770 | 93.67285 |
| lat | estimation_version_unresolved | 15295 | 4.30546 |
| lat | coordinate_changed | 5512 | 1.5516 |
| lat | unexplained_difference | 1398 | 0.39353 |
| lat | source_missing | 254 | 0.0715 |
| lat | zero_unresolved | 12 | 0.00338 |
| lat | verified_unchanged | 6 | 0.00169 |

Before/after error amplitudes are reported globally and separately by period, location system and native source history. The largest reference values, including withheld candidates, remain in the review tables. These are marginal positional-error amplitudes, not transport forecast spreads.

## Unresolved records

| status_lon | status_lat | observations |
| --- | --- | --- |
| coordinate_changed | coordinate_changed | 5512 |
| estimation_version_unresolved | estimation_version_unresolved | 15295 |
| restored_scale | zero_unresolved | 12 |
| source_missing | source_missing | 254 |
| unexplained_difference | unexplained_difference | 1398 |
| zero_unresolved | verified_unchanged | 6 |

Estimation-version failures include active/unfinished old trajectories or a version family outside the audited native profile. Coordinate, identity, source and semantic failures were not bypassed. Large error values were not trimmed to improve apparent quality. A zero may reflect encoding/estimation limitations; its meaning has not been established. No missing error was filled using a typical instrument accuracy, neighbouring drifter, model result or validation endpoint.

The 5,512 coordinate changes and 1,398 unexplained error differences belong to the same eight GPS IDs; all 6,910 of their target observations were withheld. Coordinate differences range from 0.110 to 23.307 metres (median 0.501 m). These are not necessarily large position errors, but exceed the registered storage-precision match. For the 1,398 coordinate-matched observations, reference/current error ratios range approximately from 98,386 to 101,738 across the two axes; they do not meet the predeclared 100,000-factor tolerance. This supports withholding them, not silently widening the matching or scale tolerance.

The missing-source ID is 300234061390930 (254 target observations); both approved official routes returned file-not-found. No matched observation was classified as a native fill/NaN/Inf reference. Eighteen observations have an unresolved native zero on one axis. The original base contains 498 null longitude errors, 492 null latitude errors and 12 negative latitude errors; these counts are distinct from unavailable repaired fields. See the [exception review](full/exception_review.json) for the descriptive checks and original-value availability.

## Pair-use coverage (not independent sample sizes)

| all_pairs | usable_origin_error | usable_endpoint_error | both_origin_and_endpoint_usable |
| --- | --- | --- | --- |
| 265393 | 249576 | 249577 | 249562 |

The observation denominator counts unique (ID, source_obs) keys. Pair-use denominators count each frozen forecast pair once. These counts are data availability, not prediction hit rates. Every original pair is retained.

## Source acquisition and identity

674/676 requested source files were available, covering 337 IDs. Availability does not imply eligibility. Native ID equality or an exact IMEI crosswalk explicitly stored in the same official file was required; WMO, filename and numeric suffix guesses were not accepted. Directory versions alone were not trusted. Files internally identified as v2.00 were required to describe trajectories ended before the v2.00 cutoff.

The current-directory file for some GPS IDs lacks a sufficient full-ID identity mapping; a valid legacy reference may still be used independently. The complete route-specific reasons are in [source_status.csv](full/source_status.csv) and [source_registry.json](full/source_registry.json).

## Validation and reproducibility

- Independent raw-HDF5 re-reading and separate matching/decoding/classification verified every accepted value and every status across 355,247 rows.
- A cache-only replay using two spawned processes exactly reproduced the per-ID logical outputs of the sequential production run. No HDF5/NetCDF handle was shared between threads.
- Every referenced native coordinate and error variable was independently checked for the audited float32 storage and degree-unit profile; a different profile would fail publication.
- All 345 protected file hashes were unchanged, including the 338 base track files, input pair cache, data contract, manifests and research-stage record.
- All 22 rule and boundary tests passed; [test output](unit_tests_final.txt) is retained.
- The 1,604-endpoint / 3,208-value anchor cases passed. The four already-unscaled latitude errors were preserved. The ten diagnosed negative endpoint errors were withheld as unresolved zeros.
- The first pilot audit found a reason-code ordering discrepancy for an active GPS trajectory. Both implementations withheld its errors. The first attempt was preserved; ordering was clarified and the pilot rebuilt from the same cached files before proceeding.
- A full-phase receipt initially displayed a pilot-only budget flag; this reporting field was scoped correctly and the full independent audit repeated. Both receipts are retained; data and repair decisions did not change.

## Resource use

Full phase: 3028.3 seconds; cumulative source download 1022.6 MiB; production peak RSS 618.4 MiB. Independent validation: 14.5 seconds; two-process replay: 103.2 seconds. Pilot attempt costs are separately retained in the run receipts.

Independent verifier peak RSS was 1143.2 MiB. The conservative combined RSS bound for replay was 997.1 MiB; both were below 4 GiB.

## Files and use boundary

- [Verified overlay](full/error_overlay.parquet)
- [All exceptions](full/exceptions.parquet) and [representative examples](full/exception_examples.csv)
- [Coverage by ID](full/coverage_by_id.csv), [ID and reason](full/coverage_by_id_and_reason.csv), and [error scale summary](full/error_scale_summary.csv)
- [Scale by period, location system and source](full/error_scale_by_stratum.csv) and [largest reference examples](full/extreme_reference_examples.csv)
- [Independent verification](full/verification.json), [reproducibility](full/reproducibility.json), [approval](approval.json)

Each overlay row is keyed by `(base_version, id, source_obs)`. `original_err_lon/lat` preserve the base values; `raw_ref_err_lon/lat` and `ref_err_lon/lat` preserve the raw and decoded native evidence. `repaired_err_lon/lat` contain only accepted degree-valued amplitudes, otherwise null. `status_lon/lat` explain each decision. `source_sha256` and `source_indices` point to the cached official file and native rows. `ci_2d_usable` requires both accepted axes and does not establish a calibrated joint region.

The overlay must be explicitly paired with its base version and release manifest hash. It has not been enabled in any model or default reader. Unavailable overlay values must not silently fall back to the unverified original errors. This is a repair of the frozen E7 training observations, not the whole development database. Neither outer-validation endpoint errors nor locked final-test observations were accessed. No model fitting, forecasting or scoring was performed. Verified marginal error fields do not establish joint CI calibration or improved transport prediction.
