# DATA3001 — Where Things End Up

**Status: Markov Transition Model Completed. Next stage: continuous-state model design.**

We estimate where a drifting object may be found after release in the southern Gulf Stream Corridor. The implemented models produce **1° destination-cell probability distributions at 7 or 30 days**, with whole-drifter development cross-validation. The Markov experiments model a stopped-domain process, including first exit from D. Exact-position variants additionally use the known release coordinates and initial velocity category. The research goal remains distributions at integer days **1–365**, seasonal analysis, finer grids and a separately validated grounding capability.

The milestone closes the implemented discrete/empirical Markov stage; it does not mean every exploratory extension completed. **The final neighbour-displacement extension was stopped by the project lead after one of five outer folds**, with its checkpoints and partial results retained. Continuous-state modelling has not started. Annual, seasonal, new-region, operational or object-specific accuracy is unestablished. The [Data Contract v1.0](docs/contract/data_contract_v1.0.xlsx) remains the scientific source of truth; this README summarises implementation and progress.

## Research question and scope

Given a release location in **R**, available initial-state information and a future time, what probability belongs to each destination cell, and how much is assigned to domain exit or remains unresolved?

- **Release region R:** the frozen southern Gulf Stream Corridor polygon, whose actual bounds are `[-81, 30, -73, 35.5]` in longitude/latitude. The GeoJSON polygon, rather than this rectangular envelope, determines membership.
- **Transport domain D:** the frozen rectangle `20–55°N, 81–8°W`. D contains the model's transport states and is larger than the release region.
- **Current resolution and horizons:** aligned 1° cells; exact 7/30-day endpoint matching; every eligible hourly origin–endpoint pair has equal weight.
- **Applications motivating the work:** search planning and surface-material transport near the US East Coast, Florida–Bahamas and the northern Gulf. Drifter observations alone do not validate oil, container or life-raft forecasts. Object-specific behaviour requires additional evidence.

The direct baseline conditions on the release **cell**, with its empirical within-cell origin distribution. Markov refinements retain velocity categories and, later, exact coordinates during propagation. They still select historical donor movements using cells/categories; they do not learn a continuous response function of velocity or departure weather. Regional expansion requires a separate support and validation audit.

## Data and research boundaries

The canonical release is **`per-drifter-cleaned-20261017-v7`**: **3,741 IDs, 39,099,193 hourly records and 62 columns**. Its source is the pinned official NOAA GDP v2.01.1 hourly asset. The acquired snapshot contained 39,107,061 records; the approved cleaning removed vessel-recovery tails.

| Location | Contents | Role |
|---|---|---|
| `data/train/<id>.parquet` | 3,224 complete development drifter files | Fitting, tuning and whole-ID cross-validation |
| `data/test/<id>.parquet` | 517 complete final-test drifter files | Locked during development model selection |
| `provenance/qualification/v7/` | Source-keyed qualification evidence | Reuse approved predicates without adding canonical columns |

The original 2,674 train / 550 validation / 517 test membership is preserved. Original train and validation share the development directory; the modelling folds operate within that pool. All observations of an ID stay together in each fold. Of 463 R-visiting IDs, 396 belong to development and 67 to final test.

Cleaned `drogue_status` is **1 drogued, 0 undrogued, −1 unknown**; cleaned total temperature remains in `sst` in Kelvin. Intentional NA values, unresolved metadata and source restrictions are documented in the [data dictionary](docs/data_dictionary.md), [preprocessing guide](docs/preprocessing.md) and [data layout](docs/data_layout.md). The baseline stage changed no canonical rows, columns, labels or split membership and read no final-test trajectories.

## Completed baseline experiment

The direct estimators learn endpoint frequencies, not a short-step dynamical operator. Each horizon is fitted separately. The same nine configurations are evaluated in three scenarios: pooled, fixed-drogued and fixed-undrogued.

| Family | What it predicts or borrows |
|---|---|
| **B0 — persistence** | All probability remains in the origin cell. |
| **B1 — whole-R endpoint frequencies** | One training destination distribution per horizon, shared by every origin cell in R. |
| **B2 — origin-cell endpoint frequencies** | A separate training destination distribution for each origin cell and horizon. |
| **Global — B2/B1 blend** | Borrows whole-R endpoint information to regularise B2. |
| **Local-U — unaligned neighbourhood blend** | Borrows the original endpoint distributions of the eight adjacent origin cells. |
| **Local-A — displacement-aligned neighbourhood blend** | Transfers neighbour net displacements to the target cell's actual empirical training-origin positions. |

For the three borrowing families,

`forecast = (1 − weight) × B2 + weight × borrowing_distribution`.

Each family/horizon selects its own weight, shared across origin cells. **Grid** evaluates `0, 0.1, ..., 1`; **Analytic** minimises the same quadratic comparison score continuously on `[0, 1]`. These six variants plus B0–B2 give nine configurations per scenario. Donors and alignment anchors come only from fitting IDs and eligible R-origin pairs. Neighbour pairs receive equal weights; there is no equal-cell weighting or extension of donors beyond R.

**Pooled** represents the historical mixture of recorded states. **Fixed-drogued / fixed-undrogued** require the approved official evidence to support that state throughout the requested interval. Unknown or switching intervals remain in the pooled data but do not enter fixed-state fits. This is retrospective interval qualification, not a forecast of future drogue loss. Attachment alone does not establish a homogeneous drogue depth; **DEPTH-01 remains unresolved**.

### Validation and score

- Use the unchanged **five outer / four inner whole-ID folds**. Every outer holdout remains absent from that fold's fitting, donors, anchors and inner tuning.
- Compare all configurations on identical eligible source-multiplicity cases. Repeated hourly windows are not independent drifters.
- Select weights using inner out-of-fold predictions; assess the complete selection procedure on outer held-out IDs.
- Select final candidate weights from all-development **base outer-OOF** predictions, then refit the bases on development IDs. Their tuning losses are not independent estimates of final-refit performance.
- Use failure-penalised multiclass Brier: `S = 1 + sum(p_j²) + u² − 2p_observed`, where `u` is unresolved probability. Lower is better. When `u = 0`, this equals ordinary multiclass Brier; it is not percentage accuracy.
- Retain known OUTSIDE outcomes, unresolved mass and raw zero-probability failures. Never renormalise missing mass into supported cells. Raw log loss remains infinite when a complete forecast assigns zero probability to an observed destination.
- Report probability-region coverage together with size and availability. Cutoff ties are retained. Use 200 paired whole-ID bootstrap resamples within outer folds; intervals condition on saved fits and omit refitting, selection and numerical-integration uncertainty.
- Compare fixed-state models against **frozen pooled forecasts on the exact same fixed-state cases**, replacing only case multiplicities. Raw scores from different regime populations are not a fair test of the value of state conditioning.

### Evidence and main findings

| Scenario | Horizon | Eligible hourly pairs | Independent IDs |
|---|---:|---:|---:|
| Pooled | 7 days | 308,312 | 387 |
| Pooled | 30 days | 287,004 | 358 |
| Fixed-drogued | 7 days | 178,082 | 253 |
| Fixed-drogued | 30 days | 155,188 | 226 |
| Fixed-undrogued | 7 days | 122,123 | 157 |
| Fixed-undrogued | 30 days | 116,505 | 142 |

All three scenarios have eligible development origins in 37 cells, but support is uneven and some cells have very few independent IDs. Model rows without support remain explicitly unresolved.

The table below shows **outer held-out failure-penalised Brier**, using Analytic borrowing weights. Grid variants and all controls remain in the linked reports.

| Scenario | Days | B2 | Global | Local-U | Local-A* |
|---|---:|---:|---:|---:|---:|
| Pooled | 7 | 0.928878 | 0.928845 | 0.928477 | 0.928187 |
| Pooled | 30 | 0.994400 | 0.989005 | 0.987608 | 0.987525 |
| Drogued | 7 | 0.929807 | 0.929955 | 0.928774 | 0.926831 |
| Drogued | 30 | 1.001880 | 0.989088 | 0.987617 | 0.987952 |
| Undrogued | 7 | 0.951184 | 0.946781 | 0.943511 | 0.940892 |
| Undrogued | 30 | 1.011088 | 0.991882 | 0.992441 | 0.990626 |

- **Neighbour borrowing can help, but neither U nor A is a universal winner.** In pooled 30-day evaluation, U improves over Global under the declared conditional-ID bootstrap; pooled A-versus-U intervals cross zero. Fixed-state results show different rankings. Point estimates must be read with paired intervals and A's numerical limitations.
- **Hard state partitioning did not improve these fitted baselines.** Across the twelve matched-case Analytic Global/U/A comparisons, fixed-state scores exceed their corresponding pooled scores, with the reported conditional intervals above zero. This does not establish that drogue is irrelevant or that reduced sample size alone causes the difference.
- **Coverage and concentration remain different objectives.** Pooled 30-day U hits 84.36% of endpoints inside its nominal-90% region, averaging 103.17 cells; Global hits 86.20% over 128.41 cells. Fixed-state U's corresponding hits are 80.40% drogued and 74.62% undrogued. The baseline is not yet a calibrated 90% search product.
- **Local-A is numerically provisional.** Exact small products and balanced large-product approximations retain donor/anchor marginals, but successive stability is not a certified exact-integral error bound. Unsettled fit rows total 34 pooled, 130 drogued and 295 undrogued; final refits have 0, 1 and 9 unsettled rows respectively. Inner instability can affect weight selection beyond directly unstable outer rows. Global and U do not use A's numerical integration.
- **Unresolved mass is not the same as exact-complete forecast coverage.** A can retain small unresolved mass on many forecasts; rare cases can be wholly unsupported. Read the per-run mass diagnostics rather than interpreting an exact-complete fraction as prediction accuracy. There are no observed OUTSIDE endpoints in these evaluation cases, so outside-state calibration is unestablished.

The baseline comparison stage is complete **with these limitations recorded**. The final model family has not been selected using final-test outcomes.

## Markov experiments: completed results and stopped extension

All Markov experiments here are annual-pooled and drogue-pooled. Operators use qualified origins throughout **D**; primary forecasts start in **R**. Entire held-out IDs are excluded from fitting across both regions. Every eligible hourly pair retains equal weight. The final test remains locked.

| Stage | Method and status | Evidence |
|---|---|---|
| M1 fixed 1-day prototype | Cell transition frequencies, iterated to 7/30 days; completed | [Report and maps](results/runs/markov_m1_1d_20261025T100248_328450Z/REPORT.md) |
| M1 diagnosis and lag selection | Diagnose propagation error; independently select lag from 1/3/5/7 days with exact remainder handling; completed | [Lag-CV report](results/runs/markov_lag_cv_20261025T114838_137131Z/REPORT.md) |
| M1vcat | Joint cell/velocity-category transitions, with CV-selected velocity pooling; completed | [Report and maps](results/runs/markov_vcat_cv_20261026T155955_651594Z/REPORT.md) |
| Exact-position refinement | Transfer observed geodesic displacements to each particle's exact location, retaining destination velocity category; completed at frozen parent settings | [Report and maps](results/runs/markov_position_cv_20261027T094335_386746Z/REPORT.md) |
| 30-day schedule/weight comparison | Independently tune coarse and exact-position models over nine schedules and eleven weights; completed | [Report, parameters and map](results/runs/markov_iteration_cv_20261027T120356_034230Z/REPORT.md) |
| Eight-neighbour displacement extension | Joint spatial/velocity weights and schedules; **stopped incomplete**, one outer fold and 40 inner checkpoints retained locally | [Partial report](results/deliverables/markov_neighbour_progress/REPORT.md), [stop receipt](provenance/runs/markov_neighbour_cv_20261028T105824_991491Z/STOPPED_BY_USER.json) |

### Mathematical and evaluation boundaries

The cell model estimates `P_d(i,j) = N_d(i,j) / sum_j N_d(i,j)` and composes short-step operators. M1vcat augments each cell with nine velocity labels: one exact-zero label and four direction quadrants split by a fitting-only positive-speed median. Its local joint law is mixed with a source-cell law pooled over velocities, using `K = (1 − lambda) L + lambda B`. Future held-out velocities and positions are never supplied to propagation.

Exact-position variants carry WGS84 coordinates between steps and apply sampled donor displacements at the current coordinate. They still output cell probabilities. **E** is first observed-hour exit from D and is absorbing, including subsequent re-entry. **U** is unsupported or invalid synthetic transport and is also absorbing. U is not a confirmed grounding label; neither state is silently removed or renormalised away. These stopped predictions differ from endpoint occupancy, so the original baseline results above must not be compared across targets without matching labels and cases.

Primary selection uses the unchanged augmented-state Brier/S. The auxiliary linear-plus-quadratic reference is Energy/100 km plus squared mean error/10,000 km² on its declared evaluable subset; it is not a replacement selection loss. Particle versions separately record issued-ensemble scores and numerical bias-corrected integration estimates. Coverage, region size, availability, independent-ID support and Monte Carlo uncertainty must be interpreted together.

### What the evidence supports

- **Categorical velocity improved S in the completed matched-case comparison:** M1 versus M1vcat-selected is 0.927354 versus 0.921873 at 7 days and 0.985785 versus 0.985249 at 30 days. The reported fixed-fit paired-ID intervals favour M1vcat, but its nominal-90% regions also grew. This is not a claim of tighter forecasts or independent final-test validity.
- **Exact positions helped the 7-day score at frozen settings; the 30-day gain remained uncertain.** The respective primary population sizes are 303,288 origins / 385 IDs and 268,998 origins / 337 IDs. Particle repeat counts do not increase these sample sizes.
- **Retuning 30-day schedules did not establish a reliable additional exact-position benefit.** Independently selected exact-position S is 0.985134 versus coarse S 0.985255; their paired-ID difference interval crosses zero. Numerical near-ties remain recorded rather than presented as unique optima.
- **The neighbour experiment is partial evidence only.** In its completed fold, the 7-day selection chose no borrowing; the selected 30-day neighbour procedure scored slightly worse. Remaining folds were intentionally stopped before completion. This cannot establish a general failure of neighbour borrowing or the Markov assumption.

These are adaptive development experiments: earlier results informed later research choices. The completed empirical models remain comparison controls for the next continuous-state stage. Seasonal, 365-day, grounding and general-object performance have not been validated.

## Project architecture

```text
src/data3001/
  preprocessing/   approved qualification, labels and source-aware cleaning rules
  modelling/       estimators, nested CV, scoring, audits and presentation exporters
configs/           asset catalog, canonical manifests, dataset index, dependency pins
data/train/        one complete Parquet file per development drifter
data/test/         one complete Parquet file per locked final-test drifter
docs/              controlled contract, current stage guides and team instructions
results/runs/      selected immutable model runs, fitted models, tables and reports
results/deliverables/  submission documents and presentation exports
provenance/        source/qualification evidence, run hashes and migration receipts
tests/             scientific fixtures and architecture boundary checks
archive/           historical assets and retained local recovery material
```

The team download contains the approximately 3.75 GB canonical data release, selected complete baseline and Markov result runs, and the unchanged high/intermediate land masks required by their code. This milestone adds approximately 596 MB of selected Markov run files and receipts. Multi-gigabyte exact-position/geometry caches, full cleaning backups, incomplete neighbour computation checkpoints and private runtime logs remain local. The neighbour partial report and stop receipt are published. Published receipts preserve exact output bytes and historical source/input hashes; new runs receive new IDs. See the [Markov publication guide](docs/markov_results.md) for what is included and what a fresh checkout must rebuild.

| Implemented module | Responsibility |
|---|---|
| `experiment.py`, `cv.py`, `blend.py` | Whole-ID folds, B0–B2/global models, score regions and weight selection |
| `neighbourhood.py`, `neighbourhood_cv.py` | U/A distributions, bounded alignment integration and nine-model nested evaluation |
| `regimes.py`, `run_regimes.py` | Fixed-interval qualification, matched pooled comparisons and scenario orchestration |
| `run_neighbourhood.py` | Verified coordinate preparation and guarded pooled/scenario model runs |
| `neighbourhood_report.py` | Independent reconstruction of saved fits, scores, selections and report tables |
| `showcase.py`, `report.py` | Existing global-blend presentation export and plotting; not a new U/A/state visualisation |
| `markov.py`, `markov_inputs.py`, `markov_scoring.py` | Stopped-domain operators, matching input qualification and primary/spatial scoring |
| `markov_diagnostics.py`, `markov_velocity*.py` | Propagation diagnostics, lag selection and velocity-category comparisons |
| `markov_position*.py`, `markov_iteration*.py` | Exact-coordinate displacement propagation, same-case checks and joint schedule/weight selection |
| `markov_neighbour*.py`, `_neighbour_scoring.cpp` | Stopped exploratory neighbour experiment; source retained, full CV incomplete |

The module paths above are under `src/data3001/modelling/`. The [asset catalog](configs/assets.json) resolves data and geometry locations; the [architecture guide](docs/architecture.md) explains repository conventions. The [current modelling guide](docs/modelling_round1_plan.md) records experiment definitions, results, caveats and the next-stage entry.

## Experimental roadmap and present status

| Stage | Current status | Deliverable / next checkpoint |
|---|---|---|
| Data audit and preparation | Completed release; documented unknowns remain | Canonical files, official-state evidence, frozen geometry and source-keyed labels |
| Direct endpoint baseline | Completed and audited | B0–B2, Global/U/A, Grid/Analytic weights, pooled and two fixed-state comparisons |
| Empirical Markov M1 and refinements | Completed core comparisons; neighbour extension stopped incomplete | Saved operators, reports, matched-case scores, maps and audit evidence |
| Continuous-state transition modelling | Next stage; design not yet frozen | Define joint position/velocity output, model family, objective and bounded computational budget |
| Seasonal operators M2/M3 | Planned | Calendar-aware propagation, seasonal support audit and reviewed regularisation |
| 1–365-day distributions and 0.5° refinement | Planned | Long-horizon validation, exact-duration handling, resolution/support comparison |
| Grounding and object-specific extensions | Planned | Separate defensible labels and validation; future hardware/object information is not an origin-time predictor |

### Next-stage boundary

The next planned comparison will learn how transition distributions depend on continuous position and velocity. A continuous-state model can retain the Markov assumption; it need not use a finite lookup table. No specific continuous model, new feature or new training objective is approved by this publication alone.

Before fitting, agree on the joint next-position/next-velocity distribution, D-exit handling, training objective, held-ID comparisons and a practical compute budget. Retain the completed empirical models as controls. Code and experiment definitions must continue to distinguish a single-step fit from long-horizon predictive validation.

Under the contract, the implemented finite-D prototype is a **stopped-domain process**. Endpoint occupancy, which allows exit followed by return, remains a different target. Unknown disappearance is neither exit nor grounding. The transition to the eventual endpoint product, seasonal operators and 365-day outputs requires explicit support and validation rather than assumed successful iteration.

## Read, reproduce and contribute

Start with [team download/setup](docs/getting_started.md), then the [contract](docs/contract/data_contract_v1.0.xlsx) ([Chinese translation](docs/contract/data_contract_v1.0_zh.xlsx)) and [current modelling guide](docs/modelling_round1_plan.md). The controlled English contract SHA256 is `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`.

| Need | Published entry |
|---|---|
| Markov milestone, result index and reproducibility limits | [Markov publication guide](docs/markov_results.md) |
| Latest pooled U/A comparison and audit | [Pooled neighbourhood report](results/runs/baseline_neighbour_cv_20261024T065917_879042Z/REPORT.md) |
| Latest two-state comparison and matched pooled evidence | [Fixed-regime combined report](results/runs/baseline_regime_comparison_20261024T085357_553047Z/REPORT.md) |
| Detailed fixed-state fits, scores and diagnostics | [Drogued report](results/runs/baseline_drogued_cv_20261024T080519_204788Z/REPORT.md), [undrogued report](results/runs/baseline_undrogued_cv_20261024T083230_432963Z/REPORT.md) |
| Full-development candidate weights | [Pooled weights](results/runs/baseline_neighbour_cv_20261024T065917_879042Z/final_alpha_selection.csv), [fixed-state weights](results/runs/baseline_regime_comparison_20261024T085357_553047Z/final_weights.csv) |
| Earlier global-blend interactive demonstration | [Offline page](results/deliverables/baseline_optimized/index.html) and [guide](docs/baseline_presentation.md); this predates U/A and fixed-state results |
| Canonical schema and provenance | [Data dictionary](docs/data_dictionary.md), [dataset index](configs/dataset_index.csv), [data layout](docs/data_layout.md) |
| Submitted proposal overview | [Proposal](results/deliverables/proposal/proposal_final.docx) |

After preparing Python 3.12.14 and pinned dependencies, run the development-safe checks:

```bash
.venv/bin/python -B -m unittest discover -s tests -p 'test_modelling*.py' -v
.venv/bin/python -B -m unittest discover -s tests -p 'test_architecture.py' -v
```

The current publication test counts are recorded in [the test receipt](provenance/reviews/markov_publication_20261028_tests.json). The optional neighbour native scorer must be compiled locally before its numerical tests; see the Markov publication guide. These tests and artifact audits verify implementation and reproducibility, not annual or operational predictive validity.

Re-fit the approved comparisons from the published, sealed inputs:

```bash
# Pooled: uses the verified coordinate cache; creates a new immutable run.
.venv/bin/python -B -m data3001.modelling.run_neighbourhood \
  --input-run neighbour_input_20261024T062737_251970Z

# Fixed states: fits both scenarios and produces a new combined report.
.venv/bin/python -B -m data3001.modelling.run_regimes \
  --input-run regime_input_20261024T080243_439468Z
```

These commands perform numerical fitting and can take substantial time. They use existing selected features and qualifications, keep final test locked, and do not overwrite canonical data or accepted runs. To inspect one development file, use `data3001.dataset.read_track(id)`; all stored columns remain available for later, explicitly reviewed feature selection.

The current team is **Junxi Xiao, Han Wang, Ming Yue and Yi Cheng Zhang**. Coordinate research definitions, implementation, validation and writing through the current stage guide. Review any target, eligibility, feature or boundary change against the Data Contract before implementation.
