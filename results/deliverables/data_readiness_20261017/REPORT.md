# Modelling entry readiness — 17 October 2026

**Decision: sufficient evidence to begin development-stage model selection and
baseline experiments for supported cells in the Southern Gulf Stream Corridor.**
This is not approval of a final primary-model protocol and is not evidence of
accurate 365-day seasonal forecasts. No model has been fitted or scored.

## Current data and verification

The frozen current release is `per-drifter-cleaned-20261017-v7`: 3,741 IDs,
39,099,193 retained hourly records and 62 existing columns per ID. Development
contains 3,224 IDs; the final test contains 517 different IDs. All approved
cleaning applies to both pools, and uncertainty without source evidence remains
explicit. SST and three-state drogue labels are stored in their original
columns; the four native position/velocity uncertainty values are retained.

The latest full preservation check compared all 3,741 files with the exact
pre-projection parents. Every retained value, null, type, field attribute, key
and record order matched. The 175-test suite passed; 156,024 representative
endpoint/stopped label rows remained identical before and after projection.
These checks establish implementation consistency, not predictive skill.

## Current development support

This new audit reads only the 396 development IDs that visited R. It applies
the existing exact-time (`0 h`) label generator to all qualified hourly origins
in R, on the 1-degree grid, at 7, 30 and 365 days. Endpoint occupancy and the
stopped process remain separate; pooled, fixed-drogued and fixed-undrogued
scenarios retain their existing meanings. No test trajectory or model score
was used to decide readiness.

There are **318,061 qualified-position hourly origins**.
Multiple origins from the same drifter are dependent. Counts below report the
union of contributing IDs, not a sum across cells or seasons. A fixed-state
scenario requires the contracted state over the applicable target interval.

| Horizon | Scenario | Endpoint pairs | Endpoint IDs | Stopped pairs | Stopped IDs |
|---|---|---:|---:|---:|---:|
| 7 days | pooled | 308,312 | 387 | 303,288 | 385 |
| 7 days | drogued | 178,082 | 253 | 175,652 | 251 |
| 7 days | undrogued | 122,123 | 157 | 119,671 | 157 |
| 30 days | pooled | 287,004 | 358 | 268,998 | 337 |
| 30 days | drogued | 155,188 | 226 | 145,821 | 213 |
| 30 days | undrogued | 116,505 | 142 | 109,148 | 133 |
| 365 days | pooled | 116,068 | 154 | 91,265 | 106 |
| 365 days | drogued | 12,372 | 23 | 9,827 | 15 |
| 365 days | undrogued | 55,521 | 73 | 42,913 | 53 |

The 7/30-day totals support an initial model experiment; they do not establish
adequacy of every cell-season or validation fold. At 365 days, the fixed-drogued
endpoint and stopped targets have only 23 and 15 contributing IDs, respectively,
before subdivision. Seasonal/cell/fold sparsity therefore remains material.
The accompanying tables expose those subdivisions rather than hiding them
behind the global record count.

## Next stage and boundaries

1. Settle the recorded-depth policy DEPTH-01 and identify the exact scenario
   and supported release cells before calling a result the primary model.
   Status alone does not establish a common drogue depth.
2. Freeze the model-stage feature list, outcome definition and a whole-ID
   development validation protocol before fitting. Retained lifecycle dates
   and future outcomes are evidence, not automatically forecast-time inputs.
   Keep the final 517 test IDs outside model or parameter selection.
3. Specify an explicit mathematical baseline and evaluation protocol, then
   generate a 7/30-day destination-probability map and compare distributions
   on common eligible cases. Candidate models, lags and hyperparameters have
   not been selected by this audit.
4. Extend to 365 integer-day outputs and seasonal differences only with
   declared assumptions and validation. Unsupported states remain explicit;
   additional hourly samples, bootstrap replicates or imputation cannot
   manufacture independent drifters.

The final Excel Data Contract remains the research authority. Grid refinement,
regional expansion and object-specific forecasts are subsequent audited stages.
The current unresolved temperature-quality comparisons, missing hardware,
unknown drogue intervals and depth-policy uncertainty are not declared solved.

## Evidence and distribution

- `summary.json` binds the audit to the dataset-manifest and contract hashes.
- `support_summary.csv` reports whole-R and seasonal eligible pairs/ID unions.
- `cell_season_support.csv` reports supported cell-season groups; absent groups
  are not evidence of valid zero transport.
- `recorded_audit.py` preserves the executed read-only calculation. Its run ID
  is historical; use a new run identity for a future recomputation.
- Full local verification remains in
  `provenance/migrations/feature_pruning_20261017_v1/verification.json`.

Git distributes code, source definitions, manifests, reference geometry and
reviewed evidence. It does not distribute the large active Parquet files,
raw source caches or full archived parents. A new clone must receive the
verified data/provenance bundle separately before data-dependent operations;
the `pair` adapter requires the archived qualification evidence as well as
the active 62-column trajectories.
