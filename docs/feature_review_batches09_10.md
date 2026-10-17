# Feature review: hardware categories and deployment context

Authority: the final Excel Data Contract v1.0, SHA-256
`6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`,
and the user's instruction to exclude group 09 from the current model input set
unless a strong learning role can be justified, then proceed to group 10.

The active data remain `per-drifter-cleaned-20261017-v6`: 3,741 IDs,
39,099,193 rows and 129 columns. This review changes only the existing feature
decision registry and writes inspection evidence outside `data/`. No source
column, row, state, missing value, ID split or scientific contract was changed.

## Group 09: agreed current-core exclusion

All 14 stored columns in `09_hardware_and_tracking_types` are now marked
`exclude_current_core` in `configs/feature_review.csv`. This is the agreed
model-input drop list, not physical deletion from the retained source files.
The registry has 57 excluded entries after this decision, previously 43.

No predictive experiment has yet established a gain from these categories.
Core exclusion is a scope decision, not proof that hardware never affects drift.
The contract's measurement-quality and hardware-composition audits still apply.

| Field family | Current evidence and decision |
|---|---|
| `BuoyTypeManufacturer` and `_text` | Manufacturer identity supports exact source/configuration lookup; it is not a direct measurement of transport. Exclude from core predictors and retain provenance. |
| `BuoyTypeSensorArray` and `_text` | Instrument category. Both representations match `ManufactureSensorType` exactly for every current ID. Exclude redundant category encoding; retain design-composition evidence. |
| `ManufactureSensorType` and `_text` | Exact duplicate of the sensor-array metadata in this release; no independent information. |
| `DrogueDetectSensor` and `_text` | Detection method, not attachment state. There are 113 development IDs with literal `unknown`. Retain for assessing state-evidence reliability; exclude as an ordinary predictor. |
| `DrogueType` and `_text` | Design code, not a measured drag or depth parameter. Development has 105 recorded categories including 839 blank IDs; 51 R-visiting development IDs have blank codes. Physical relevance is plausible, but predictive gain and adequate category-level support have not been demonstrated. Retain for design sensitivity rather than conditioning the core on all codes. |
| `typebuoy` and `_text` | Broad instrument family; it is not calibration for oil, containers or other application objects. Retain for configuration sensitivity; exclude from the current core. |
| `SubsfcFloatPresence` | Static auxiliary-float design attribute, not the cleaned `drogue_status`. Retain for physical-design sensitivity; a plausible effect is not a demonstrated improvement in predicted distributions. |
| `location_type` | Positioning method: GPS=1, Argos=0. Preserve for measurement-quality checks required by contract clause 23. Exclude from ordinary transport predictors; no physical speed meaning is assigned to its code. |

All six binary/text pairs decode exactly. Each field is constant within an ID;
millions of repeated hourly copies do not create millions of independent
hardware-design examples. An optional later hardware sensitivity comparison
would need development-only validation and controlled sample support before
promoting a category into the predictor set. No such experiment was run here.

## Group 10: audited, decisions pending discussion

There are 15 stored columns representing nine native fields. The six text fields
are exact decodes, not additional measurements. Counts below use the 3,224
development IDs, including 396 R-visiting IDs, rather than repeated hourly rows.
Final-test outcomes were not inspected for this decision.

| Native field (plus `_text` where present) | Meaning and observed values | Unknown/blank or special code: development IDs (R-visiting IDs) | Proposed treatment, not executed |
|---|---|---:|---|
| `DeployingCountry` | Deployment country; values include United States, France and unknown labels. | 867 (70) blank/literal unknown | Exclude from model inputs; retain provenance. Do not infer from the current position. |
| `DeployingShip` | Recorded deployment platform/name; 378 categories include ships, aircraft/platform descriptions and unknown labels. | 567 (33) blank/literal unknown | Exclude from model inputs; retain provenance. |
| `DeploymentStatus` | `good`: 3,219 IDs; `failed on deployment`: four; `unknown`: one. None of the five exceptions visits R. | 1 (0) literal unknown | Keep as deployment-quality evidence. Investigate the four failure labels against their retained valid tracks before proposing any row exclusion. This is not a current drogue-state flag. |
| `PurchaserFunding` | Purchaser/funding identity, commonly NOAA or country names. | 320 (44) blank | Exclude from model inputs; retain provenance. |
| `SensorUpgrade` | Nonblank values are mainly country/organisation labels, not a measured upgrade or upgrade date. Exact interpretation needs upstream documentation. | 2,019 (328) blank | Exclude as an ordinary predictor; do not equate blank with no upgrade or fabricate an upgrade measurement. |
| `Transmissions` | Nonblank values are country/organisation labels, not transmission counts, rates or GPS/Argos method. Exact interpretation needs upstream documentation. | 320 (44) blank | Exclude as an ordinary predictor; no numeric conversion or imputation. |
| `DeploymentComments` | Recorded integers are -1 or year-like values 2004–2022. This conflicts with a free-text-comment interpretation. | 1,249 (176) code -1 | Hold semantic interpretation; do not silently rename, impute or use as a calendar covariate. |
| `ManufactureMonth` | Recorded values are -1 or integers 1–12. Manufacture month is distinct from observation/release season. | 1,249 (176) code -1 | Exclude from model inputs; retain provenance. Do not infer from deployment month. |
| `ManufactureVoltage` | Every development ID records -1. No measured voltage is represented. | 3,224 (396) code -1 | Exclude from model inputs; do not average-fill or treat -1 as physical voltage. |

No storage nulls occur in these 15 fields, but this does not imply full semantic
availability. Blank strings, literal unknown labels and negative codes must be
distinguished from a measured physical value. Blank funding/upgrade entries can
also reflect undocumented applicability; no blanket imputation policy is applied.

### Semantic mismatch requiring caution

Among 700 development IDs with a unique exact-ID match and a populated
`Manufacture Year` in the frozen NOAA drifter specification CSV,
`DeploymentComments` equals that official manufacture year for all 700.
This supports investigating an upstream naming/mapping problem; it does not
authorize changing the current source column or declaring the meaning settled
for every ID. No values or names were changed. Country/organisation values under
`SensorUpgrade` and `Transmissions` likewise must not be interpreted literally as
technical upgrade states or communications performance.

## Verification and evidence

- [Existing decision registry](../configs/feature_review.csv): all 14 group-09
  entries agreed/excluded; all 15 group-10 entries audited/pending decision.
- [Profile](../results/runs/feature_review_batch09_10_20261017_v1/profile.json):
  every field, values, populations, source hashes and source-year comparison.
- [Per-ID metadata](../results/runs/feature_review_batch09_10_20261017_v1/per_ID_metadata.csv)
  and [read-only replay](../results/runs/feature_review_batch09_10_20261017_v1/audit.py).
- [Registry change verification](../results/runs/feature_review_batch09_10_20261017_v1/registry_update.json)
  and the exact pre-edit registry snapshot in the same evidence directory.

All 3,741 Parquet metadata inventories agree with manifest rows/column counts.
All selected fields are constant within each ID, binary/text companions decode
exactly, and data-file sizes/modification times were preserved during inspection.
The manifest, schema and contract hashes remain unchanged. This metadata audit
does not establish predictive accuracy and does not replace sample eligibility
rules, physical specification checks or final model validation.

Official interpretation sources:
[NOAA hourly-product documentation](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php),
[NOAA drifter FAQ](https://www.aoml.noaa.gov/phod/gdp/faq.php) and the frozen
[NOAA drifter specification CSV](https://www.aoml.noaa.gov/ftp/pub/phod/pazos/deplog/Drifter_Specifications.csv).
