# Preprocessing and modelling handover

## Authority and current version

The [English Data Contract v1.0](contract/data_contract_v1.0.xlsx) is the research source of truth; the [Chinese copy](contract/data_contract_v1.0_zh.xlsx) is a translation. The contract content, frozen scientific settings and prior results were not changed by the architecture migration.

The current foundation combines **preparation-1.0** with **handover-addendum-1.1**, and the separate 2026-10-14 drogue census. Do not choose a table by its basename or the newest modification time. Use [the asset catalog](../configs/assets.json).

The complete earlier clause-to-implementation mapping is retained in [the original crosswalk](../archive/planning/preparation/contract_crosswalk.csv). The [handover crosswalk](../provenance/frozen/handover_20261013/contract_crosswalk_addendum.csv) records the subsequent implementation additions. Historical stage instructions, checkpoints and receipts retain their original content and execution identity.

## Source, cohort and geometry

The asset is NOAA GDP `gdp-v2.01.1.zarr`, acquired from the [official hourly cloud asset](https://noaa-oar-hourly-gdp-pds.s3.amazonaws.com/latest/gdp-v2.01.1.zarr/). Frozen source metadata and checksums identify the actual snapshot; a mutable `latest` URL by itself is insufficient for reproduction.

The acquired subset retains **3,741 IDs / 39,107,061 hourly records**, including all 20 original observation fields and 40 original trajectory-level fields. These are complete available acquired trajectories, not uninterrupted observations. Source-object caches contain selected global chunks; they are not a complete global corpus.

| Definition | Current asset | Meaning |
|---|---|---|
| Acquisition envelope | `acquisition_envelope` | Broader search/acquisition bounds, not the study or a confidence region |
| Release region R | `release_R` | Frozen southern corridor polygon intersected with `[-82,30,-73,35.5]` |
| Transport domain D | `transport_D` | Frozen finite domain `[-81,20,-8,55]`; target-specific exit treatment |
| Main grid | `preparation_config`, `state_index` | Aligned 1° cells; 0.5° geometry retained for later assessed refinement |

There are 463 R-visiting IDs and 3,278 additional downstream-support IDs. Acquisition support does not establish validated coverage of the entire Gulf or East Coast. New release regions require a new support and holdout audit.

## Cleaning and eligibility semantics

These points summarise the existing implementation, without replacing the contract:

1. Preserve original records, values, metadata and source observation indices. Keep representative/exact-duplicate/conflict status and analysis eligibility separately; no silent row deletion or fabricated observation.
2. Missing temperature or velocity does not automatically invalidate a usable position. Variable-specific flags and uncertainty checks remain separate. Absolute SST is converted from Kelvin for analysis; the diurnal anomaly retains its anomaly interpretation. Missingness and special source encodings keep explicit meanings.
3. Negative velocity components are valid directions. Extreme speeds/displacements receive review flags, peer/context evidence and recorded disposition. The primary snapshot does not replace positions, infer drogue from neighbours, or interpolate missing path hours.
4. Main origins are all qualified hourly starts. Keep visit IDs and elapsed intervals; optional thinning/reweighting is a sensitivity analysis, not a replacement for equal qualified-pair weighting.
5. Main fixed-duration matching is exact (`0 h` tolerance). Existing 1/2/3 h sensitivity and 6 h diagnostic settings are retained. A tolerant endpoint does not repair a nominal path gap or prove a continuous path.
6. Drogued, undrogued and unknown are distinct. Positive documented loss dates require source agreement and the existing half-float32-ULP transition guard. Zero/NaN loss metadata remains unresolved under the frozen rules. Fixed-regime eligibility applies to the target-specific required interval. Unknown records remain available for appropriate uses; they are not relabelled as confirmed physical states.
7. Recorded depth/hardware remains native metadata. Drogued status does not prove 15 m depth. **DEPTH-01 is still pending**: no recorded-15 m restriction or mixed-depth primary policy was adopted during migration. A correlation/wind-assisted imputed dataset is not present in the current primary assets.
8. Actual positions determine R/D membership, including the frozen boundary convention. Land-mask resolution disagreement is retained as mapping uncertainty. Do not snap coordinates to water or infer beaching from an unresolved position.

## Independent targets and time coverage

- **Endpoint occupancy:** the position at the requested horizon, with its own timestamp, position and scenario eligibility. Some intermediate gaps may leave an endpoint usable without establishing a complete path.
- **Stopped process:** first qualified exit from D is absorbing. A proven early exit can remain an outside outcome despite later record termination or state change. A gap or unusable mapping before the required stopping time prevents an unproven exit from becoming a valid outside label.
- **Unknown outcomes:** absence, administrative immaturity, termination, source failure, mapping uncertainty and insufficient support retain distinct meanings. Missing outcomes do not become transitions.

Keep both primary reason and secondary predicates. Never collapse all eligibility into one `valid` flag. Existing compact events and anchor ledgers retain their historical schema; the current generator derives independent event bounds from cleaned records and can emit the later source/geometry annotations.

The product horizon is **1–365 integer days**, not arbitrary-hour forecasts. Prepared anchor audits cover 7/30/90/180/365 days. Exact short-lag and remainder requirements are retained. Annual and seasonal propagation remains a future model-validation task; daily output enumeration does not prove daily or yearly accuracy.

## Which tables to use

| Catalog ID | Current role |
|---|---|
| `state_index` | Augmented index with water area inside R/D and whole-R release weights |
| `baseline_state_index` | Original preserved columns/cell IDs; historical reference |
| `lag_support` | Current long table with explicit `target`; candidate/eligible IDs and concentration |
| `baseline_lag_support` | Original wide table, retained without conversion |
| `anchor_support` | Baseline target-specific anchor support |
| `development_folds` | Frozen whole-ID development fold assignments |
| `grouped_fold_coverage`, `year_support` | Long-horizon fold/cell-season availability evidence |
| `depth_support`, `depth_pending` | Native hardware/depth strata and pending-policy evidence |
| `drogue_census` | Per-ID state-record census; not inferred physical state |

Whole-R release weights use water **inside R** at each resolution, not full-cell wet area. The empirical within-cell origin prior remains contracted. Do not renormalise only supported cells or hide unsupported operator mass.

Count independent IDs by union, not by summing counts across cells/seasons/horizons. Report effective support and dominant-ID concentration alongside hourly pair totals. Empty evaluation groups remain `not_evaluable`, not a score of zero.

## Splits and forecast-time information

The fixed whole-ID assignments are unchanged: **2,674 train / 550 validation / 517 test**; R visitors **323 / 73 / 67**. Development-only grouped folds also retain their existing assignments. Do not split observations or rebuild assignments as part of an experiment.

Source/label preparation can use retrospective evidence to determine eligibility. Future loss dates, next gap/exit, matched endpoints and other future track information are **not forecast features**. Features must be available at release time and follow the contract. Training, model selection and any fitted imputation remain separated from locked final-test outcomes.

The `Source.track()` interface denies test trajectories by default; explicitly authorised technical audits may opt in. The development `pair` CLI refuses test IDs. Filesystem separation is a workflow safeguard, not an access-control security system.

## Next model-stage gates

Before fitting a primary model, settle DEPTH-01 and the model-stage protocol. Retain 1° annual/seasonal analysis, development-selected lag and the contracted comparison/validation requirements. Assess probability distributions and calibration on common targets/cases; distinguish model accuracy from preparation QA.

365-day seasonal support includes empty folds and strong dominant-ID concentration. Seasonal pooling/shrinkage may be considered in the model protocol, but extra folds, bootstrap replicates or imputed rows cannot manufacture independent trajectory evidence. Broader acquisition or new regions require an explicit audited change and appropriate validation.

## Evidence and safe execution

Start with [the migration acceptance](../provenance/migrations/architecture_20261014/verification.json), [original readiness report](../provenance/frozen/preparation_v1/misc/READINESS_REPORT.md), [addendum](../provenance/frozen/handover_20261013/README.md) and [original handover](../archive/planning/preparation/MODELLING_HANDOVER.md). Their old relative paths are interpreted using [the historical path map](../configs/legacy_paths.json); old prose and hashes are retained, not rewritten.

Use `python -m data3001 pair` for read-only development label checks. Saving requires a new run ID. Do not invoke historical mutating scripts to verify this migration. They are protected in the live package because their output/checkpoint identities belong to frozen runs. Any future full recomputation must define a new version and validate its output boundaries first.
