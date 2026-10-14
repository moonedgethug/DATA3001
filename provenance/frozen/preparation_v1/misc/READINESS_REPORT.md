# Data preparation readiness report

Status: **prepared with explicit observational-support limitations**. Integrity, source preservation, field-specific cleaning, distinct target eligibility and count reconciliation passed. Predictive modelling and predictive acceptance have not been performed.

## Authority and source

The authoritative Excel remains unchanged: SHA-256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`. The authorized stage prompt is preserved in `docs/AUTHORIZED_STAGE_PROMPT.txt`; all 31 aspects are mapped in `docs/contract_crosswalk.csv`. Neither this report nor the rule register creates a new research contract.

Official NOAA hourly v2.01.1, DOI [10.25921/x46c-3620](https://doi.org/10.25921/x46c-3620), is pinned through metadata, object receipts and checksums. A `latest` URL is not an immutable release guarantee. Fresh verification checked 8,075 downloaded source objects and all 60 source field value hashes. Original values of all 20 observation fields were also compared against every cleaned row. The 40 source trajectory metadata fields and two provenance fields remain in the read-only raw subset.

The measured full source spans 1987-10-02 13:00 UTC to 2022-10-31 00:00 UTC; public release prose reports 1987-10-03 13:00 to 2022-10-31 23:00. Stored attributes and the measured source timestamps are preserved separately. Maturity uses the measured global cutoff. Downloaded cohort coverage is 1990-07-06 20:00:00+00:00 to 2022-10-31 00:00:00+00:00.

The [NOAA hourly documentation](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php) describes processed estimates following QC. These are not independent hourly instrument fixes. [Position/velocity methods](https://doi.org/10.1002/2016JC011716), [SST methods](https://www.nature.com/articles/s41597-022-01670-2), and [GSHHG documentation](https://www.soest.hawaii.edu/pwessel/gshhg/) are saved with retrieval receipts. Current ERDDAP documentation supplied conventions, never substitute trajectory records.

## Cohort and preservation

- 3,741 IDs and 39,107,061 source hourly estimates retained, with complete available trajectories and all original observation values.
- 463 R-visiting IDs: 323 train, 73 validation, 67 locked test; R-track records total 6,243,277.
- Actual R origins: train 249,125, validation 68,983; locked-test products stay under `restricted_test/`.
- 13,276 non-hourly intervals and 730,371 absent expected hours remain explicit. They are not physical exits.
- 1,366,330 missing-SST records keep their usable positions. 1,521 rows with negative position uncertainty are retained and isolated from uncertainty use.

The frozen whole-ID assignment uses full SHA-256 of ASCII `20261004:<canonical GDP ID>` with exact integer thresholds. The auxiliary Markdown uses a different `DATA3001-v1|20261004|<ID>` construction and the first 13 hex digits. That discrepancy is documented; the existing global manifest was preserved and all 19,396 assignments verified. No six-hour records or ID whitelist entered this hourly preparation.

## Domain, states and targets

Frozen R is the corridor/window intersection polygon, not its rectangle. D is [-81.0, 20.0, -8.0, 55.0], selected from three documented development candidates. All 2,518,385 observed intermediate R-development positions within the union of 365-day windows are covered. Candidate 0 uses the smallest covered interior grid. Downstream adjacent exits/returns were also audited. The selected product is explicitly a **finite stopped-domain product**; no model boundary-map stability or unrestricted one-year transport has been established.

The 1-degree grid remains primary; aligned 0.5-degree diagnostics use identical eligibility. GSHHG 2.3.7 high-resolution L1 provides ocean/land mapping, with high/intermediate disagreement isolated. Wet cell areas, disconnected component counts and checksums are saved. Actual points decide R/D membership. Inclusive north/east D boundaries require adjacent half-open grid cells; the state inventory includes them, including boundary-only intersections. No point was snapped or recoded as outside because of a coastline mismatch.

Endpoint occupancy and stopped-first-exit ledgers are separate. Endpoint pairs can survive a position gap if recorded metadata independently confirms regime constancy. Stopped labels require every expected usable hour and the scenario through the first eligible observed exit or the nominal horizon. An outside observation after a gap cannot shorten that requirement. A qualified exit absorbs later death, loss, return or cutoff. Unknown and recorded-switch/mismatched-scenario predicates remain separate secondary evidence. Missingness never becomes physical outside or an observed unresolved-support destination.

Real training example: ID 7706157, origin 1990-09-06 05:00 UTC, eligible observed exit 1990-09-07 02:00 UTC, track termination 1991-01-09 19:00 UTC. It supplies a 365-day stopped-outside label while its 365-day endpoint is unavailable. The contiguous path to exit was independently checked. This D-source example is not presented as an R-origin case.

## 365-day evidence and limitations

Values below are **eligible hourly pairs / distinct eligible IDs**. Distinct IDs overlap across seasons and cells; they must not be summed as independent trajectories.

| UTC departure season | Train endpoint | Train stopped | Validation endpoint | Validation stopped |
|---|---:|---:|---:|---:|
| DJF | 818 / 5 | 635 / 4 | 0 / 0 | 0 / 0 |
| MAM | 2,197 / 6 | 1,109 / 3 | 203 / 1 | 0 / 0 |
| JJA | 5,304 / 12 | 4,521 / 8 | 1,115 / 3 | 1,115 / 3 |
| SON | 2,403 / 4 | 2,403 / 4 | 195 / 2 | 30 / 1 |

DJF has no fixed-drogued 365-day validation endpoints or stopped labels. MAM has no such stopped labels. Other seasonal supports depend on few IDs and overlapping windows. These data cannot certify seasonal one-year predictive accuracy. Whole-ID grouped five-fold development assignments and refitting instructions are prepared; the locked test split is unchanged. Annual pooling, uncertainty intervals, scoring and any decision to change the research definition belong to modelling/architecture.

![Distinct seasonal ID support](/Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/figures/R_365_seasonal_ID_support.png)

![Aligned grid support diagnostics](/Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing/preparation/figures/R_365_grid_availability.png)

The main distribution remains conditional on usable observed constant-regime pairs. Available records do not identify the destinations of every missing or terminated trajectory. No universal adequate-count threshold or effective sample size was invented.

## Field and diagnostic results

Temperature components, official velocity, interval-net velocity, each uncertainty, geometry and regime have separate flags. Absolute SST converts Kelvin to Celsius; anomalies remain unchanged. Total/non-diurnal SST uses flags 4/5 and the declared range; diurnal use requires flag 5. Source ID17503 has a negative legitimate anomaly but source flag2, so it remains preserved and is unavailable to that temperature extension. Missing or rejected SST never removes an otherwise usable position.

Zero loss dates are documented as uncertain from the beginning. Generic NaN conversion origin is not proven universally; affected fixed-regime uses stay isolated and pooled records remain. Negative uncertainty codes and upstream `gap` interpretation remain documented questions. No absolute-value repair or uncertainty-to-zero replacement occurred.

Development speed review flagged 6,007 rows in 2,684 contiguous review events; 424 events had comparable contemporaneous peers. Training-only thresholds prioritize review, never deletion. Other-ID selection, actual distance/time, known regime, recorded depth/hardware, bounded wet connectivity, vector/circular statistics and source context are preserved. No peer absence/disagreement generated an observation or removed a position. Global screening statistics are retrospective diagnostics and cannot be reused as held-out-fold fitted features.

## Verification and remaining work

The consequential suite includes native invalid coordinates, duplicate provenance, zero velocity, missing uncertainty, tolerance ties/late selected endpoints, independent regime confirmation, early exit/termination, gap-before-exit, inclusive grid boundaries, simultaneous secondary predicates, and randomized comparison with an independent chronological scanner. Five named real source cases and integer-day generation through 365 were verified. Every candidate reconciles to eligible or exactly one primary exclusion; secondary predicates remain nonexclusive.

Routine implementation corrections were versioned: exact tiled water-area computation; inclusive boundary cell inventory; independent secondary predicates; and nominal-window retention after an unqualified outside observation. Historical code hashes are recoverable. Raw acquisition objects and receipts remain unchanged. Corrected candidate and eligible totals are compared with pre-correction totals, and frozen rules are reapplied to separated test partitions.

A checkpoint ownership audit also corrected an overbroad filename prefix: ID7647 must not claim ID107647's ledger files. Only checkpoint metadata was repaired; all original checkpoint versions and actual data-generation signatures are retained. No Parquet source or scientific label values changed in that repair. All corrected owned output hashes passed the final audit.

Optional reconstruction was deferred; no reconstructed primary endpoint, exit, independent drifter or transition was created. No transport model, forecast, predictive score, bootstrap interval or regional transfer claim has been produced. Preparation is usable for the next modelling stage subject to the reported support and isolated-semantics limits.

## Package navigation

- `metadata/`, `docs/QC_RULE_REGISTER.csv`, `config/`: source conventions, decisions, unresolved uses and frozen implementation.
- `cleaned/`: all development hourly source fields plus annotations; source linkage through `source_obs`, original within-trajectory index and frozen manifest.
- `origins/`, `events/`: all D-source origins, R membership and compact retrospective bounds.
- `ledgers/endpoint/`, `ledgers/stopped/`: exact R anchor ledgers, distinct targets and all scenarios.
- `support/`: development cell/season support, attrition, destinations, concentration, lag/remainder support, endpoint sensitivities and vector descriptions.
- `geometry/`, `figures/`: R/D/grid/water states and development-only support figures.
- `restricted_test/`: frozen test application; keep separate from tuning and illustrations.
- `audit/preparation_verification.json`: final source preservation, frozen settings, reference isolation and candidate reconciliation.

See `docs/REPRODUCIBILITY.md` and `docs/MODELLING_HANDOVER.md` before modelling.
