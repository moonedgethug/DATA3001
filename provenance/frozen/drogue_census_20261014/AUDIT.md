# Frozen hourly drogue-state census — 14 October 2026

## Scope and definitions

All 3,741 acquired IDs and 39,107,061 retained hourly records were counted, including every split and full available trajectories outside R/D. The census concerns observed-hour state; it does not establish constant-regime eligibility for a forecast interval.

Confirmed states follow the current contract implementation: the original source flag must agree with a finite positive loss date, outside its float32 timestamp precision guard. NaN and zero loss dates remain unresolved under that implementation. This census does not independently establish the physical drogue state of unresolved records.

## Observation states

| State | Hourly records | Share of all records | IDs with at least one record |
|---|---:|---:|---:|
| drogued | 18,892,169 | 48.3088% | 3,410 |
| undrogued | 19,376,937 | 49.5484% | 3,375 |
| unknown | 837,955 | 2.1427% | 3,249 |

ID counts in the table overlap. They are not mutually exclusive ID classes.

## Mutually exclusive ID classes

| Observed state pattern | IDs |
|---|---:|
| drogued_only | 200 |
| undrogued_only | 210 |
| drogued_and_undrogued_without_unknown | 82 |
| unknown_only | 112 |
| drogued_and_unknown | 54 |
| undrogued_and_unknown | 9 |
| drogued_and_undrogued_and_unknown | 3,074 |

## Why records are unresolved

| Reason | Records | IDs |
|---|---:|---:|
| float32_loss_time_guard | 3,137 | 3,137 |
| nonfinite_loss_date | 339,263 | 44 |
| zero_loss_date | 495,555 | 68 |

The 112 wholly unresolved IDs account for 834,818 hours (44 NaN-loss-date IDs and 68 zero-loss-date IDs). They comprise 85 train, 19 validation and 8 locked-test IDs. Another 3,137 IDs each have exactly one precision-guard hour; these are not missing whole-trajectory status metadata.

The preserved source flag itself has no missing values: 19,231,486 values are 1 and 19,875,575 are 0. For the 44 NaN-loss-date IDs all source flags are 1; for the 68 zero-loss-date IDs all source flags are 0. A source flag alone does not resolve the contract-defined uncertainty. Metadata recovery should be distinguished from motion-based state inference.

## Reconciliation

Native ID inventories, every per-ID record count and the native source-flag totals match. All 39,107,061 prepared regime values reconcile independently to the documented rule. The 837,955 unknown hours match the original preparation verification receipt; reason counts sum exactly. The 7 exclusive ID patterns sum to 3,741. Contract SHA-256 remains unchanged. No imputation or transport modelling was performed.

## Evidence files

- `audit.py`: exact full-record census and rule-reconciliation procedure.
- `audit.ipynb`: inspectable rerun companion.
- `result.json`: aggregate results and checks.
- `per_ID_census.csv`: one row per acquired drifter.
- `priority_unknown_IDs.csv`: the 112 wholly unresolved drifters.
- `input_inventory.json`: files consumed and observed file metadata.

The original data, split manifests and contract were not modified. The historical source-preservation audit remains prior evidence; this census did not repeat a raw comparison of every original field.
