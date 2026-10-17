# Feature availability and preparation audit — 16 October 2026

**Status: audit complete; handling proposals below are for discussion and have not been applied.** No source/canonical data, contract, eligibility rules or split assignments were changed. No imputer or predictive model was fitted.

## Authority, population and checks

The English Data Contract v1.0 remains authoritative: SHA256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`. Clauses 12–14, 20, 23 and 26 govern retention, vector interpretation, release targets, variable-specific QC and feature availability; clauses 10 and 28 govern grouped validation and dependence. This document records evidence and proposals, not a parallel contract.

All **3,741 files / 39,107,061 rows / 130 columns** in `per-drifter-20261016-v1` were profiled with per-file hash checks. Recommendations use **3,224 development IDs / 33,943,292 rows**, including **396 R-visiting IDs / 318,108 observed R origins**. D has **2,541 development IDs / 25,220,185 mapped observed positions**. Counts in R/D are observations, not valid-horizon pairs. The final 517 test IDs received fixed technical completeness checks only; no test score or fitted selection was used.

Checks cover null/NaN, infinity, declared finite fills, separate zero/-1 counts, candidate text placeholders, existing QC flags, ID-grain metadata, duplicate keys, actual timestamp gaps, structural first-row missingness and departure-season differences. No infinite numeric values, duplicate time keys or duplicate source observation keys were found in the retained corpus. Key development counts were independently reconciled using a separate DuckDB query.

## Main finding

Existing time, position, native velocity, cell and season fields contain no nulls in the development pool. The main issues are optional SST coverage/quality, uncertainty fields, hardware metadata, structural annotations and missing intervals between observed rows. Their presence does not justify dropping every incomplete row or delaying the contracted position-pair core until every auxiliary field is filled. Preparation QA is not proof of valid one-year pairs or prediction accuracy.

## Hourly fields: raw missingness and analytical usability

All percentages below use the stated observation denominator. "Unavailable after QC" includes source nulls and values rejected by the existing rules; it is not an additional population to add to nulls.

| Field / check | Development missing / unavailable | R-origin missing / unavailable | Interpretation |
|---|---:|---:|---|
| UTC source time | 0 (0.000%) | 0 (0.000%) | No missing timestamps among retained observations; omitted hours are a separate problem. |
| Latitude | 0 (0.000%) | 0 (0.000%) | No source-position nulls; geometry qualification remains separate. |
| Longitude | 0 (0.000%) | 0 (0.000%) | Negative longitude is valid, not a missing code. |
| Eastward velocity | 0 (0.000%) | 0 (0.000%) | No nulls; sign gives direction. Finite is not a guarantee against extremes. |
| Northward velocity | 0 (0.000%) | 0 (0.000%) | No nulls; sign gives direction. |
| Total SST, raw nulls | 1,194,141 (3.518%) | 15,403 (4.842%) | Temperature uses Kelvin in the native field. |
| Non-diurnal SST, raw nulls | 1,194,141 (3.518%) | 15,403 (4.842%) | Do not confuse this component with the diurnal anomaly. |
| Diurnal anomaly, raw nulls | 1,194,141 (3.518%) | 15,403 (4.842%) | Negative anomalies can be physically meaningful. |
| Eastward velocity uncertainty | 3,326,919 (9.801%) | 21,801 (6.853%) | Missing uncertainty does not mean missing velocity. |
| Northward velocity uncertainty | 3,327,495 (9.803%) | 21,805 (6.855%) | Do not replace with zero precision error. |
| Latitude uncertainty, raw nulls | 21,195 (0.062%) | 338 (0.106%) | Additional negative values are not included in null counts. |
| Longitude uncertainty, raw nulls | 21,710 (0.064%) | 344 (0.108%) | Uncertainty usability remains variable-specific. |
| Total SST unavailable after QC | 1,205,537 (3.552%) | 15,485 (4.868%) | Optional extension only; preserve position pairs. |
| Non-diurnal SST unavailable after QC | 1,203,957 (3.547%) | 15,423 (4.848%) | Use its own quality rule. |
| Diurnal anomaly unavailable after QC | 8,361,043 (24.632%) | 92,183 (28.979%) | The stricter diurnal rule rejects many finite values; not ordinary random nulls. |

R contains 15,403 raw-missing total-SST observations and another 82 finite values failing its current rule. Thus requiring total SST would remove 15,485 (4.868%) observed R origins before horizon pairing. Requiring usable diurnal anomalies would remove 92,183 (28.979%). These are origin attrition counts, not gains/losses in valid endpoint pairs.

49 development IDs have no SST anywhere in their acquired track; 13 IDs have no SST in their R observations (not necessarily their whole track). Three SST components have identical raw missing masks in the independent development check. A cause such as absent instrumentation is not established merely from these patterns.

| R departure season | Observed origins | Distinct IDs within season | Total SST unavailable | Diurnal anomaly unavailable |
|---|---:|---:|---:|---:|
| DJF | 75,855 | 153 | 4,786 (6.31%) | 27,318 (36.01%) |
| MAM | 55,124 | 128 | 2,992 (5.43%) | 16,724 (30.34%) |
| JJA | 87,891 | 162 | 4,307 (4.90%) | 20,125 (22.90%) |
| SON | 99,238 | 182 | 3,400 (3.43%) | 28,016 (28.23%) |

These are departure-observation coverage counts. IDs can occur in multiple seasons; do not sum them as independent samples. They do not establish 365-day seasonal outcome support.

## Uncertainty, extreme motion and geometry

- Latitude uncertainty has **1,342 negative values in development**, including **11 R origins**. They are preserved with unresolved-negative flags. A negative uncertainty is unusable as an uncertainty, but this audit does not establish that its position is false. Do not take its absolute value or discard the trajectory solely for this reason.
- There are **112 development observations with native speed above 3 m/s**, including **seven above 5 m/s**; R has one above 3 m/s and none above 5 m/s. These are descriptive screens, not physical rejection thresholds. Existing earlier diagnostics retained 6,007 review-flagged development rows under frozen train-derived thresholds. Their old peer-regime interpretation predates the official corrections and is historical evidence, not automatically current adjudication.
- Review suspicious motion using exact elapsed time, coordinate-derived interval vectors, position/velocity uncertainty, source gap and within-track continuity. Then seek independent, contemporaneous, same-regime/hardware/depth peers in the documented staged windows (25 km / 3 h, 50 km / 6 h, 100 km / 12 h), respecting water connectivity and fronts. No peer or disagreement does not prove error, and peer agreement does not restore an observed path.
- Development has **18,934 geometry-uncertain observations**; R has **two**, both mask-resolution disagreement. Preserve the mapping predicate and target-specific treatment. Do not move coordinates onto water or fill missing uncertainty with zero to bypass it.

## Missing time intervals and structural nulls

- Development has **11,257 intervals** containing **620,388 absent hourly timestamps** between retained observations, across 1,531 IDs. The longest missing interval contains 24,835 absent hours. The whole corpus has 13,276 such intervals / 730,371 absent hours. These are within-track grid omissions, not all possible unobserved life-history time.
- R has 91 gap-ending observed rows; the preceding intervals contain 3,892 absent hours. This attributes gaps to their ending row and does not assert that all unobserved positions were inside R.
- Native `gap` measures original sampling context in the processed source product. It is distinct from missing hourly grid records detected by timestamp differences. Neither all-finite coordinates nor a populated source gap variable proves a continuous hourly path.
- Development has exactly **3,224 nulls** in each previous-interval displacement/component/elapsed-time field: one first row per ID. The full corpus has 3,741. There are zero additional non-first-row missing interval vectors. These nulls mean "no previous observed interval", not speed zero. Preserve them.
- Keep endpoint and stopped/path targets independent. A real endpoint may be usable across an intermediate gap, while first exit/hitting remains unresolved. Do not interpolate primary targets, infer first exit from a missing segment, or label a reconstructed path as observed.

## ID-level metadata

These counts use **IDs**, not repeated hourly rows. Zero and -1 are shown separately and are not universally treated as null.

| Metadata | Development NaN/blank IDs | R-visiting NaN/blank IDs | Other code / limitation |
|---|---:|---:|---|
| `DrogueCenterDepth` | 4 | 0 | Development: 85 zero, 29 at 10 m, 3,106 at 15 m. R: 20 zero, 376 at 15 m. |
| `DrogueLength` | 7 | 0 | Development additionally has 93 zeros; R has 20. |
| `DrogueBallast` | 142 | 5 | Development additionally has 83 zeros; R has 16. Do not infer all zeros are missing. |
| `DragAreaAboveDrogue` | 82 | 13 | Hardware lookup needs exact ID/model evidence and checked units. |
| `DragAreaOfDrogue` | 85 | 13 | R additionally has 20 zero-valued IDs. |
| `DragAreaRatio` | 85 | 13 | Native units say m despite an area-ratio label: meaning/units require verification before physical use. |
| `FloatDiameter` | 6 | 0 | Do not replace unknown diameter with a global hardware average. |
| `deploy_date` | 36 | 4 | Deployment time differs from first QC position time. |
| `end_date` | 163 | 11 | All 163 development missing-end cases have typedeath=0 (alive) in this snapshot. |
| `start_date` | 0 | 0 | Recorded first QC date is not necessarily the first estimated hourly timestamp. |

- `ManufactureVoltage` is **-1 for every ID** (3,224 development, 396 R-visiting); -1 is a declared fill, so its apparent 0% null rate is misleading. Preserve the column but do not invent a voltage or assume it adds predictive information.
- `ManufactureMonth` has **1,249 development / 176 R-visiting IDs** with declared -1 fill. `DrogueType_text` is empty for **839 / 51 IDs**. `DrogueDetectSensor_text` says unknown for **113 / 20 IDs**. Keep raw values and explicit per-field unknown categories; do not mode-fill hardware identity.
- All 20 zero-depth R-visiting IDs contribute **8,784 R origins, all labelled undrogued** under the already approved rules. Zero depth does not overturn their regime labels, nor justify inventing a 15 m drogue. The physical interpretation of zero hardware entries needs source evidence. Downstream development includes other depth strata; DEPTH-01 remains pending.
- `DeploymentComments` is stored as int16 with -1 and year-like values up to 2022 despite its comments label. This is a schema/meaning question, not a licence to silently rename it to manufacturing year or impute a numeric mean.
- `location_type=0` is Argos and `SubsfcFloatPresence=0` is a valid Boolean category. These are examples where a global zero-to-missing conversion would damage data.
- End/death/loss metadata are retrospective context, not automatically release-time features. Missing live-end metadata must not be replaced by a fabricated future termination, and missing deployment time must not be silently redefined as first QC-observation time.

## Evidence annotations are not ordinary features

For example, `regime_unknown_reason` is null for known labels by design; scoped official-loss/attached-through fields can be null when that interpretation does not apply. Filling these nulls would invent evidence. Native drogue fields and the already corrected `regime` remain separate. All 496,247 current unknown regime hours remain unchanged.

## Proposed next decisions — not yet applied

1. **Retain the position-pair core.** Core states use origin cell, UTC departure season/date and declared scenario; destinations require real qualified future positions or a proven stopped exit. Missing optional SST/uncertainty/hardware does not automatically exclude the whole row. Do not treat all 130 stored columns as forecast predictors.
2. **Create QC-aware feature views, not edits to canonical observations.** Proposed temperature aliases mask with the corresponding existing `_ok` flag; native fields remain untouched. Keep separate absent/unusable indicators. Preserve first-interval missingness; speed/direction are derived only from qualified vectors, with direction undefined at zero speed. Retain signed components or sine/cosine representations rather than averaging compass degrees.
3. **Use source recovery before statistical filling.** Accept auxiliary metadata only with exact ID/model, compatible source/version, evidence and a recorded disposition. Preserve unknowns that remain unproven. Hardware, measurement uncertainty, lost timestamps and future outcome labels have different meanings and are not all candidates for interpolation.
4. **Treat optional SST imputation as an evaluated modelling extension.** Compare the no-SST core, a missing-aware SST extension, and a simple training-fold-only cell/season baseline with a declared fallback where local support is inadequate. More complex spatial/temporal interpolation or regression is a challenger, not presumed superior. Respect connected water, fronts and release-time availability; use only contemporaneous/earlier donor information in a forecast-use experiment. Retrospective reconstructions require a separate label and validation interpretation.
5. **Validate recovery realistically.** Hide known observations in contiguous blocks and, where justified, entire IDs to resemble observed missingness; random single-hour masking alone is insufficient. Evaluate reconstruction error and, separately, destination-distribution scores/calibration and origin/case attrition on shared held-out development cases. Select and fit all learned preprocessing inside complete-ID folds. Never learn from final-test data or treat inferred values as observed measurements.
6. **Resolve the small set of interpretation gates.** Start with SST aliases/usage, uncertainty policy, zero-depth/hardware semantics and the two suspicious metadata descriptions. No source feature is deleted; choosing a model input subset is a separate, reviewable modelling decision. These investigations should not be conflated with proof of annual/seasonal accuracy.

## Inspectable evidence

- [Full 130-column profiles](../results/runs/feature_audit_20261016_v1/feature_profile.csv)
- [Per-field action proposals](../results/runs/feature_audit_20261016_v1/feature_action_proposals.csv)
- [One-row-per-ID metadata](../results/runs/feature_audit_20261016_v1/metadata_by_ID.csv) — empty strings are preserved; use `keep_default_na=False` when reading this inspection export.
- [Per-ID checks](../results/runs/feature_audit_20261016_v1/per_ID_checks.csv)
- [Season/context counts](../results/runs/feature_audit_20261016_v1/context_counts.csv)
- [Summary and real cases](../results/runs/feature_audit_20261016_v1/summary.json)
- [Independent query/checks](../results/runs/feature_audit_20261016_v1/independent_checks.json)
- [Executed companion notebook](../results/runs/feature_audit_20261016_v1/feature_audit_companion.ipynb)
- [Exact audit code](../provenance/runs/feature_audit_20261016_v1/audit_features.py)
- [Validation receipt](../provenance/runs/feature_audit_20261016_v1/validation.json)

## External source checks

[NOAA hourly product and release notes](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php) identify these as processed hourly estimates and describe the variable-specific SST flags, deployment versus first-QC distinction and v2.01.1 location-type correction. Current source documentation corroborates conventions; it does not replace the frozen data version.

[Scikit-learn imputation documentation](https://scikit-learn.org/stable/modules/impute.html) provides candidate tools, including missing indicators and multivariate/neighbor methods; it does not establish which one is best for this ocean region. [Preprocessing guidance](https://scikit-learn.org/stable/common_pitfalls.html) requires fitted transformations to stay inside the training partition. Some imputers drop entirely empty columns by default, so any later implementation must explicitly preserve the required source schema and record the chosen input representation.

The linked primary SST paper was not retrievable in this web session, and the full NOAA hardware specification pages exceeded the web reader limit. No missing physical hardware meaning or area-unit conversion was guessed from those inaccessible pages.
