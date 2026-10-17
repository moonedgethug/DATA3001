# Preprocessing and modelling handover

## Authority and current version

The [English Data Contract v1.0](contract/data_contract_v1.0.xlsx) is the research source of truth; the [Chinese copy](contract/data_contract_v1.0_zh.xlsx) is a translation. The contract content, frozen scientific settings and prior results were not changed by the architecture migration.

The active hourly release is **per-drifter-cleaned-20261017-v7**: [one complete file per ID](data_layout.md), with 62 fields after the approved 67-column projection and all retained observations consolidated. Original `err_lat`, `err_lon`, `err_ve` and `err_vn` remain unchanged. Approved drogue states are stored directly in `drogue_status` (1 drogued, 0 undrogued, -1 unknown); the former `regime` column has been removed without changing those labels. Its scientific foundation remains **preparation-1.0**, **handover-addendum-1.1** and the two approved official drogue corrections. Do not choose a table by basename or modification time. Use [the asset catalog](../configs/assets.json).

**2026-10-16 scoped corrections:** `official-drogue-attached-44-v1` restores the 44 source-audited IDs whose original NOAA loss-date fill value explicitly means "drogue still attached". The separate [boundary audit](drogue_boundary_audit.md) refines documented nominal-loss or bounded attached-end cases. Both are already incorporated in the current per-ID files, with their source evidence embedded in file metadata. Use `data3001.dataset.read_track(id)` for a complete frame and `prep_pairs.load_track()` for label generation with the corresponding interval rules. Test access still requires an explicit opt-in for authorised audits.

The previous preparation, correction directories and ledgers are retained unchanged under `archive/data_before_release_20261016/`. Correction contributions are **not complete datasets**. Frozen global support tables, depth/fold summaries and the 2026-10-14 census predate the official corrections. Regenerate current aggregates from canonical tracks, or replace the affected old per-ID contributions without double-counting. The release manifest records the current regime census: 19,267,484 drogued, 19,335,559 undrogued and 496,150 unknown hours in `drogue_status`. This is a label census, not a current support audit or prediction result.

The complete earlier clause-to-implementation mapping is retained in [the original crosswalk](../archive/planning/preparation/contract_crosswalk.csv). The [handover crosswalk](../provenance/frozen/handover_20261013/contract_crosswalk_addendum.csv) records the subsequent implementation additions. Historical stage instructions, checkpoints and receipts retain their original content and execution identity.

## Hardware missing-value normalization

The seven physical hardware fields were normalized in place to numeric null
without specification imputation. This changes missing-value representation,
not drifter trajectories or physical states. Existing zero codes, all finite
specifications, SST and drogue labels are unchanged. Source units/attributes
remain as supplied; the unresolved `DragAreaRatio` unit annotation is not
corrected by this cleaning. See the [scoped report](../provenance/migrations/hardware_NA_20261017_v1/REPORT.md).

## Source, cohort and geometry

The asset is NOAA GDP `gdp-v2.01.1.zarr`, acquired from the [official hourly cloud asset](https://noaa-oar-hourly-gdp-pds.s3.amazonaws.com/latest/gdp-v2.01.1.zarr/). Frozen source metadata and checksums identify the actual snapshot; a mutable `latest` URL by itself is insufficient for reproduction.

The acquired subset retains **3,741 IDs / 39,107,061 hourly records**, including all 20 original observation fields, 40 original trajectory-level fields and two acquisition provenance arrays. Their union with all 67 prepared fields contains 109 distinct columns; 12 decoded text companions and nine release/provenance annotations brought the original release to 130 columns. The current release has 39,099,193 rows after authorized vessel-recovery-tail deletion and 62 columns after the approved drogue consolidation and feature projection; earlier source snapshots and the complete 129-column parent remain archived. These are complete available acquired trajectories, not uninterrupted observations. Source-object caches contain selected global chunks; they are not a complete global corpus.

| Definition | Current asset | Meaning |
|---|---|---|
| Acquisition envelope | `acquisition_envelope` | Broader search/acquisition bounds, not the study or a confidence region |
| Release region R | `release_R` | Frozen southern corridor polygon intersected with `[-82,30,-73,35.5]` |
| Transport domain D | `transport_D` | Frozen finite domain `[-81,20,-8,55]`; target-specific exit treatment |
| Main grid | `preparation_config`, `state_index` | Aligned 1° cells; 0.5° geometry retained for later assessed refinement |

There are 463 R-visiting IDs and 3,278 additional downstream-support IDs. Acquisition support does not establish validated coverage of the entire Gulf or East Coast. New release regions require a new support and holdout audit.

## Cleaning and eligibility semantics

The v7 storage projection removed 67 approved columns from active train/test
files. The rules below remain unchanged. Removed qualification annotations and
visit numbers are distributed as exact portable projections under
`provenance/qualification/v7/`; complete parents remain archived. The pair-label
adapter reads their arrays by source_obs/time without requiring the raw source
cache and does not recreate them as canonical features. Detailed correction
evidence also remains in the existing per-track metadata and archives. See
[data layout](data_layout.md) and [team setup](getting_started.md).

These points summarise the existing implementation, without replacing the contract:

1. Preserve original records, values, metadata and source observation indices. Keep representative/exact-duplicate/conflict status and analysis eligibility separately; no silent row deletion or fabricated observation.
2. Missing temperature or velocity does not automatically invalidate a usable position. Variable-specific flags and uncertainty checks remain separate. Absolute SST is converted from Kelvin for analysis; the diurnal anomaly retains its anomaly interpretation. Missingness and special source encodings keep explicit meanings.
3. Negative velocity components are valid directions. Extreme speeds/displacements receive review flags, peer/context evidence and recorded disposition. The primary snapshot does not replace positions, infer drogue from neighbours, or interpolate missing path hours.
4. Main origins are all qualified hourly starts. Keep visit IDs and elapsed intervals; optional thinning/reweighting is a sensitivity analysis, not a replacement for equal qualified-pair weighting.
5. Main fixed-duration matching is exact (`0 h` tolerance). Existing 1/2/3 h sensitivity and 6 h diagnostic settings are retained. A tolerant endpoint does not repair a nominal path gap or prove a continuous path.
6. Drogued, undrogued and unknown are distinct. The [official boundary audit](drogue_boundary_audit.md) refines 3,128 approved IDs using documented nominal minutes or bounded attached-end markers; nine boundary cases remain unresolved. Other positive-date cases retain the previous source-agreement/precision rule. The separate 44-ID official-fill correction remains active; zero-loss cases remain unknown. Both refinements are materialised in `drogue_status` without re-estimation; `regime_pre_official_correction` preserves the older labels. `regime_unknown_reason` distinguishes 495,504 uncertain-from-start hours, nine unresolved boundary hours and 637 hours beyond attached evidence. Fixed-regime eligibility uses the same evidence throughout the target-specific interval. Recorded times do not prove exact physical loss times.
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
| `lag_support` | Handover long table with explicit `target`; historical support before official corrections |
| `baseline_lag_support` | Original wide table, retained without conversion |
| `anchor_support` | Baseline target-specific anchor support |
| `development_folds` | Historical whole-ID development fold assignments; retained for reproduction |
| `grouped_fold_coverage`, `year_support` | Long-horizon fold/cell-season availability evidence |
| `depth_support`, `depth_pending` | Native hardware/depth strata and pending-policy evidence |
| `drogue_census` | Frozen pre-correction census; current counts are linked in the boundary audit |

Whole-R release weights use water **inside R** at each resolution, not full-cell wet area. The empirical within-cell origin prior remains contracted. Do not renormalise only supported cells or hide unsupported operator mass.

Count independent IDs by union, not by summing counts across cells/seasons/horizons. Report effective support and dominant-ID concentration alongside hourly pair totals. Empty evaluation groups remain `not_evaluable`, not a score of zero.

## Splits and forecast-time information

Physical storage now uses **3,224 development (`train`) / 517 final-test IDs**; R visitors **396 / 67**. This combines the original train and validation directories without altering any ID's historical assignment, original manifests or old folds. No new validation allocation was made. As authorised by the user, model-stage validation may be allocated within the development pool by complete ID. Save each allocation, seed and purpose before fitting; declare changes against Data Contract clause 10. Use a fixed development validation protocol for model selection, and leave final-test membership and outcomes outside selection. Never randomly split hourly observations across training and validation.

Source/label preparation can use retrospective evidence to determine eligibility. Future loss dates, next gap/exit, matched endpoints and other future track information are **not forecast features**. Features must be available at release time and follow the contract. Training, model selection and any fitted imputation remain separated from locked final-test outcomes.

The canonical `read_track()` and historical `Source.track()` interfaces deny test trajectories by default; explicitly authorised technical audits may opt in. The development `pair` CLI refuses test IDs. Ordinary filesystem reads are still possible: directory separation is a workflow safeguard, not an access-control security system.

## Next model-stage gates

Before fitting a primary model, settle DEPTH-01 and the model-stage protocol. Retain 1° annual/seasonal analysis, development-selected lag and the contracted comparison/validation requirements. Assess probability distributions and calibration on common targets/cases; distinguish model accuracy from preparation QA.

365-day seasonal support includes empty folds and strong dominant-ID concentration. Seasonal pooling/shrinkage may be considered in the model protocol, but extra folds, bootstrap replicates or imputed rows cannot manufacture independent trajectory evidence. Broader acquisition or new regions require an explicit audited change and appropriate validation.

## Evidence and safe execution

Start with [the current release acceptance](../provenance/migrations/data_release_20261016/acceptance.md), [data guide](data_layout.md), [original readiness report](../provenance/frozen/preparation_v1/misc/READINESS_REPORT.md), [addendum](../provenance/frozen/handover_20261013/README.md) and [original handover](../archive/planning/preparation/MODELLING_HANDOVER.md). Their old relative paths are interpreted using [the historical path map](../configs/legacy_paths.json); old prose and hashes are retained, not rewritten.

Use `python -m data3001 pair` for read-only development label checks. Saving requires a new run ID. Do not invoke historical mutating scripts to verify this migration. They are protected in the live package because their output/checkpoint identities belong to frozen runs. Any future full recomputation must define a new version and validate its output boundaries first.
