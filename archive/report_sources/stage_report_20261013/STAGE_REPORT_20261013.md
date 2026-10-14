# DATA3001 data preparation stage report

As of 13 October 2026 (Australia/Sydney). Underlying hourly source ends on 31 October 2022.

## Executive summary

The audited package retains **3,741 complete available drifter trajectories and 39.1M hourly estimates**. Source preservation, field-specific cleaning, target definitions and handover reconciliation have passed their documented checks. These records support starting the 1° short-lag modelling and evaluation programme.

**Predictive accuracy has not been measured.** The primary depth/hardware policy must be decided before modelling the near-15 m scenario. One-year seasonal evidence remains sparse, with some groups and folds impossible to evaluate.

## 1. Work completed

The data stage now covers acquisition, source-preserving cleaning, origin and target preparation, geometry, observational support and reproducible handover. The architecture audit's additions have been implemented without replacing the research contract.

| Task | Completed result |
| --- | --- |
| Acquisition and provenance | Pinned NOAA hourly v2.01.1; full available trajectories and all original metadata retained. |
| Cleaning and annotations | Field-specific QC; SST, uncertainty, speed, timestamp gaps, mapping and regime annotations remain separate. |
| Origins and target labels | All QC-valid hourly candidate origins; separate endpoint and stopped-first-exit ledgers; exact UTC durations and tolerance sensitivities. |
| Geometry and release weights | Frozen R/D, primary 1° and aligned 0.5° diagnostics; water inside R/D and whole-R unit-mass weights. |
| Support and dependence evidence | ID unions, concentration, season/fold coverage; short lag/remainders and anchor support. |
| Architecture audit correction | Source-position and pure geometry failures separated; no current snapshot eligibility change. |

## 2. Current data overview

The source is the frozen official **NOAA GDP hourly v2.01.1** product. The downloaded trajectories span **6 July 1990 to 31 October 2022 UTC**. Hourly records are processed estimates and overlapping windows, not independent hourly measurements.

There are **463 R-visiting IDs** and **3,278 additional IDs** retained for downstream support. Entire available trajectories are preserved, including positions outside R. The R cohort is a subset of the full cohort; the table's rows must not be added together. Splits are global whole-ID assignments, with the final test kept out of setting selection.

| Cohort | IDs | Source hourly records | Train IDs | Validation IDs | Locked test IDs |
| --- | --- | --- | --- | --- | --- |
| All acquired trajectories | 3,741 | 39,107,061 | 2,674 | 550 | 517 |
| R-visiting trajectories (subset of all) | 463 | 6,243,277 | 323 | 73 | 67 |

### Release region and transport domain

**R** is the Southern Gulf Stream corridor polygon intersected with 30–35.5°N and 82–73°W. The bounding rectangle alone is not R. Its 1° partition contains approximately **334,502 km² of water**. Whole-R unit mass is allocated by water inside R, including zero weight for 13 boundary-contact-only cells.

**D** is the frozen downstream domain, 81–8°W and 20–55°N. Non-R drifters contribute local downstream evidence. The primary grid is **1°**, anchored at −180° longitude and −90° latitude; aligned 0.5° geometry/support are prepared for later comparison. The finite-domain stopped target remains distinct from unrestricted endpoint occupancy.

### Quality means preserved values and explicit eligibility

Cleaning keeps original values and separates position, temperature, uncertainty, geometry, timestamp and regime flags. Missing SST does not remove a usable position. Gaps, disappearance and immature follow-up do not become observed physical exits.

The full source-field comparison belongs to the accepted baseline audit. Label semantics additionally have regression and sampled independent evidence; this is not a claim that every semantic predicate on every label was independently recomputed. The later source-position reason correction has no eligibility effect in this snapshot.

| Aspect | Evidence | Status |
| --- | --- | --- |
| Raw observation preservation | All 20 fields match the frozen snapshot across 39,107,061 rows | Verified baseline |
| Missing SST | 1,366,330 rows retain usable positions | Separate field flag |
| Negative position uncertainty | 1,521 rows retained; uncertainty use isolated | Source interpretation unresolved |
| Absent expected timestamps | 730,371 hours across 13,276 intervals; not physical exits | Explicit path incompleteness |
| Geometry mapping | 24,966 rows flagged; no water snapping or inferred beaching | Affected use isolated |
| Regression and handover checks | 41 tests; 9,676 consumed input-file hashes and count reconciliation | Passed |
| Prediction accuracy | No model fit, predictive score or bootstrap result | Not evaluated |

### What research is supported now

The package provides reproducible inputs to **attempt 1° annual and seasonal short-lag transport models**, and to evaluate 7/30-day probability distributions on held-out whole IDs. It also supports separate fixed-undrogued and pooled reference scenarios, first-exit/retention descriptions and whole-R release preparation.

The table reports **eligible hourly-origin labels and distinct IDs**, for actual R origins under the existing fixed-drogued rules. It is observational support, not model accuracy or a universal local sufficiency test. Endpoint labels require the actual matched end location; stopped labels need a complete qualified path only until the horizon or established first exit. These targets must not share a generic valid label.

| Days | Target | Train labels | Train IDs | Validation labels | Validation IDs |
| --- | --- | --- | --- | --- | --- |
| 7 | endpoint | 140,548 | 202 | 36,071 | 48 |
| 7 | stopped | 138,603 | 200 | 35,614 | 48 |
| 30 | endpoint | 123,533 | 180 | 30,281 | 44 |
| 30 | stopped | 116,532 | 170 | 28,025 | 41 |
| 365 | endpoint | 10,722 | 18 | 1,513 | 4 |
| 365 | stopped | 8,668 | 12 | 1,145 | 3 |

### What remains limited

**One year:** the mandatory 365-day analysis stays in scope, but sparse independent support prevents a claim of accurate seasonal one-year forecasting. In train stopped support, 55 of 145 candidate cell–season combinations have zero eligible IDs and 45 have one. A supported combination's median dominant-ID share is 97.73%. Empty validation folds are explicitly not evaluable.

**Depth:** 17 development IDs contribute 41,879 usable drogued D origins from recorded 10 m or missing depth. Another two IDs record depth zero and contribute 3,022 origins. All are retained and separately audited; none of these usable drogued origins lie in R. Drogue attachment does not establish a uniform 15 m operating depth.

The current data do not establish unrestricted one-year domain coverage, accuracy in new regions, or object-specific forecasts for oil, vessels, containers or people.

## 3. Next-stage plan

1. **Architecture decision:** record the primary allowed depth/hardware mixture and sensitivity cohorts. Do not silently delete or relabel non-15 m/unknown equipment.
2. **1° core modelling:** estimate annual and departure-season empirical operators; compare 1/3/5/7-day lags and estimated remainders. Advance the UTC date and operator season at every propagation step. Retain direct anchor references and persistence/destination-climatology baselines.
3. **7/30-day development validation:** compare the same targets and cases using log loss, Brier score and calibration, preserving outside and unresolved-support mass. Select lag, pooling and regularization from development evidence; use whole-ID uncertainty and lock settings before final test.
4. **365-day assessment:** attempt annual and seasonally pooled/shrunk predictions; publish sparse and non-evaluable groups. Do not use long-lived survivors as the entire short-lag cohort or rebalance IDs to fill seasons.
5. **Refinement after evidence:** consider 0.5° and broader regional transfer only when the core runs and development results justify them. Optional challengers remain subsequent experiments, not immediate dependencies.

The next completed milestone is a reproducible core-model evaluation package. Improving prediction accuracy is the objective; its success must be demonstrated by held-out probability scores and calibration.

## Evidence and authority

The Data Contract v1.0 Excel remains the research specification. This report is a status summary, not a replacement contract. Counts are taken from the reviewed local audit and support outputs, not newly fitted models. Full source-preservation checks belong to the accepted baseline; regression and sampled label checks have their documented scope.

- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/geometry/release_R.geojson
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/READINESS_REPORT.md
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/audit/preparation_verification.json
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/geometry/transport_D.geojson
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/metadata/contract_aspects.json
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/remediation_20261013/audit/annual_support_limits.json
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/remediation_20261013/audit/depth_findings.json
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/remediation_20261013/audit/verification.json
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/remediation_20261013/configuration.json
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/remediation_20261013/geometry/area_policy.json
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/remediation_20261013/readiness_gate.json
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/remediation_20261013/semantic_green.log
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/remediation_20261013/support/R_anchor_support.parquet
- /Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/remediation_20261013/unresolved_questions_addendum.json
