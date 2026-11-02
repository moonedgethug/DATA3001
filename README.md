# DATA3001 — Where Things End Up

**Current milestone: `Markov Step 1 - 3done` — 2 November 2026. Step 1 is frozen, Step 2 comparisons and Step 3 E1–E4 are complete, and Step 4 is in planning.**

Start with the [Step 3 E4 results](docs/local_endpoint_joint_s3_e4_results.md), [visual comparison](results/deliverables/local_endpoint_joint_s3_e4/review.html) and [approved plan](docs/local_endpoint_joint_s3_e4_plan.md). E4 jointly adjusts neighbour information and borrowing strength, comparing unconstrained Brier selection with dual-reference coverage/size constraints and explicit fallback. Neither horizon achieves a quality-preserving improvement; all constrained selections return the LocalEndpointAdaptive anchor because no candidate reaches the inner Fixed hit-rate floor. Engineering completion is not model replacement. The [E3 result](docs/local_endpoint_quality_s3_e3_results.md), [E2 comparison](docs/local_endpoint_adaptive_s3_e2_results.md) and [E1 benchmark](docs/spatial_borrowing_s3_e1_results.md) remain preserved. The additional [E5 exact-coordinate displacement trial](docs/actual_origin_displacement_s3_e5_o1_results.md) is deferred for computational cost and incomplete capacity validation; no full-CV predictive result exists. This milestone does not label that extension complete or declare a universally superior model.

The accepted [S1 baseline](docs/empirical_b2_results.md), [S2 E1](docs/adaptive_b2_b1_results.md), [E2](docs/b2_b1_e2_results.md), [E3](docs/drifter_shrinkage_e3_results.md) and [E4](docs/partial_weighting_e4_results.md) remain preserved. E3/E4/S3 share one evaluation target; it differs from S1/E1/E2's original pair-weighted target. Original-pair results remain secondary sensitivity views. Standard Brier and nominal-90% regions are unchanged. Unsupported rows receive no Brier and are reported separately. The [research stage ledger](docs/research_stage_ledger.md) records approved decisions; final-test access requires a separate decision.

**Our research priority remains the Markov transport framework, with B2 as its first-stage baseline.** The five steps below describe the current research programme, not five mandatory upgrades or the numbering of the older M1 experiments.

| Step | Research question and method | Current status and evidence |
|---|---|---|
| **1 — Empirical transition matrices** | Estimate destination probabilities from qualified historical start/end pairs for each origin cell, separately at 7 and 30 days. | B2 completed and frozen; [method and results](docs/empirical_b2_results.md). |
| **2 — Regularisation / Bayesian estimation** | Test borrowing a broader reference distribution and controlling unequal drifter influence. Implemented comparisons use fixed/adaptive B2–B1 shrinkage and full/partial ID weighting; this does not claim a completed Bayesian posterior model. | E1–E4 completed; Fixed and Adaptive retained as research outcomes. [E1](docs/adaptive_b2_b1_results.md), [E2](docs/b2_b1_e2_results.md), [E3](docs/drifter_shrinkage_e3_results.md), [E4](docs/partial_weighting_e4_results.md). |
| **3 — Spatially informed transition matrices** | Borrow evidence from the eight adjacent origin cells: compare shared destinations with translated displacements, then test adaptive borrowing, neighbour-information quality and joint weight selection. | E1–E4 completed, audited and replayed; narrower regions can lose observed coverage. [Benchmark](docs/spatial_borrowing_s3_e1_results.md), [adaptive](docs/local_endpoint_adaptive_s3_e2_results.md), [quality](docs/local_endpoint_quality_s3_e3_results.md), [joint selection](docs/local_endpoint_joint_s3_e4_results.md). E5 exact-coordinate extension is deferred. |
| **4 — Time / environmental conditioning** | Test departure season first, followed by separately reviewed SST, initial velocity and external environmental information. | [Architecture](docs/time_environment_s4_architecture.md) and [seasonal contract draft](docs/seasonal_conditioning_s4_e1_contract.md) prepared; implementation and execution await approval. |
| **5 — Memory / latent states** | Test whether past movement or an inferred transport state adds information beyond the current state. | Not started; scope and feasibility require review. |

**Step 3 means spatial information sharing, not a three-day forecast.** Steps 1–3 currently estimate direct 7/30-day distributions; their completion does not establish recursive, seasonal or 365-day predictive accuracy. See the [Markov results index and publication scope](docs/markov_results.md) for downloadable evidence and local-only caches.

The scenario remains annual-pooled. B2 conditions only on the release cell and requested horizon; available initial velocity is not a B2 predictor, and its fields remain in the data. B2 is treated as the fixed-horizon empirical Markov transition model for this stage. The 7-day and 30-day tables are estimated separately, with no matrix-power consistency or recursive rollout required. Start with the [code guide](docs/code_guide.md) for the B2 reading order and the [current modelling plan](docs/modelling_round1_plan.md) for the approved scope.

We estimate where a drifting object may be found after release in the southern Gulf Stream Corridor. The implemented models produce **1° destination-cell probability distributions at 7 or 30 days**, with whole-drifter development cross-validation. The Markov experiments model a stopped-domain process, including first exit from D. Exact-position variants additionally use the known release coordinates and initial velocity category. The research goal remains distributions at integer days **1–365**, seasonal analysis, finer grids and a separately validated grounding capability.

The published Markov milestone records completed comparisons, not the completion of every possible improvement. **The older M1 neighbour-displacement extension remains stopped after one of five outer folds**; S3 E1 is a separate direct-horizon experiment. The first continuous Gaussian/MDN experiment and frozen-model diagnostics are complete; further continuous-model optimisation is paused. Year-scale, seasonal, new-region, operational or object-specific accuracy is unestablished. The [Data Contract v1.0](docs/contract/data_contract_v1.0.xlsx) remains the scientific source of truth; this README summarises implementation and progress.

## Research question and scope

Given a release location in **R**, available initial-state information and a future time, what probability belongs to each destination cell, and how much is assigned to domain exit or remains unresolved?

- **Release region R:** the frozen southern Gulf Stream Corridor polygon, whose actual bounds are `[-81, 30, -73, 35.5]` in longitude/latitude. The GeoJSON polygon, rather than this rectangular envelope, determines membership.
- **Transport domain D:** the frozen rectangle `20–55°N, 81–8°W`. D contains the model's transport states and is larger than the release region.
- **Current resolution and horizons:** aligned 1° cells; exact 7/30-day endpoint matching; every qualified hourly pair is retained. Fitting weights follow each declared model; E3/E4/S3 primary evaluation gives equal weight to IDs within cells and cells overall. Historical analyses retain their own weights.
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

In these historical Markov comparisons, primary selection used augmented-state Brier/S. The auxiliary linear-plus-quadratic reference was Energy/100 km plus squared mean error/10,000 km² on its declared evaluable subset; it was not a replacement selection loss. Particle versions separately record issued-ensemble scores and numerical bias-corrected integration estimates. Coverage, region size, availability, independent-ID support and Monte Carlo uncertainty must be interpreted together. These historical metrics do not override the current S1 standard-Brier-only protocol.

### What the evidence supports

- **Categorical velocity improved S in the completed matched-case comparison:** M1 versus M1vcat-selected is 0.927354 versus 0.921873 at 7 days and 0.985785 versus 0.985249 at 30 days. The reported fixed-fit paired-ID intervals favour M1vcat, but its nominal-90% regions also grew. This is not a claim of tighter forecasts or independent final-test validity.
- **Exact positions helped the 7-day score at frozen settings; the 30-day gain remained uncertain.** The respective primary population sizes are 303,288 origins / 385 IDs and 268,998 origins / 337 IDs. Particle repeat counts do not increase these sample sizes.
- **Retuning 30-day schedules did not establish a reliable additional exact-position benefit.** Independently selected exact-position S is 0.985134 versus coarse S 0.985255; their paired-ID difference interval crosses zero. Numerical near-ties remain recorded rather than presented as unique optima.
- **The neighbour experiment is partial evidence only.** In its completed fold, the 7-day selection chose no borrowing; the selected 30-day neighbour procedure scored slightly worse. Remaining folds were intentionally stopped before completion. This cannot establish a general failure of neighbour borrowing or the Markov assumption.

These are adaptive development experiments: earlier results informed later research choices. The completed empirical models form the starting point for the current Markov consolidation stage. Seasonal, 365-day, grounding and general-object performance have not been validated.

## Project architecture

```text
src/data3001/
  preprocessing/   approved qualification, labels and source-aware cleaning rules
  modelling/
    common/             shared folds, scores, geometry, run I/O and plotting
    baselines/          direct-horizon B0/B1/B2 and their refinements
    markov_models/      empirical operators, propagation and Markov experiments
    continuous_models/  retained Gaussian/MDN code and diagnostics; development paused
    _compat/            historical imports and commands, forwarding only
    assets/             pinned presentation resources
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

| Active package | Responsibility |
|---|---|
| [`common/`](src/data3001/modelling/common) | Whole-ID folds, categorical/particle/spatial scores, endpoint geometry, immutable run I/O and rendering |
| [`baselines/`](src/data3001/modelling/baselines) | B0–B2, global/local sharing, fixed-regime comparisons and their reports |
| [`markov_models/`](src/data3001/modelling/markov_models) | Cell/velocity matrices, first-exit inputs, propagation, exact-position and schedule comparisons; stopped neighbour code retained |
| [`continuous_models/`](src/data3001/modelling/continuous_models) | Shared conditional Gaussian/MDN implementation and frozen diagnostics, retained for comparison |
| [`_compat/`](src/data3001/modelling/_compat) | Old module names and commands forwarding to the same canonical implementations |

The [code guide](docs/code_guide.md) provides the complete module inventory and empirical-matrix reading order. The [asset catalog](configs/assets.json) resolves data and geometry locations; the [architecture guide](docs/architecture.md) explains repository conventions. The [current modelling guide](docs/modelling_round1_plan.md) records experiment definitions, results, caveats and the next-stage entry.

This architecture update publishes reorganised source, supporting configuration/tests, current guides and the compact [migration record](provenance/migrations/modelling_layout_20261029T065416Z/REPORT.md). The pre-change source snapshot, runtime logs and continuous-model result runs remain local. Continuous-report links in historical plan sections therefore require the retained local workspace. No new model fitting or predictive improvement is claimed by this update.

## Experimental roadmap and present status

| Stage | Current status | Deliverable / next checkpoint |
|---|---|---|
| Data audit and preparation | Completed release; documented unknowns remain | Canonical files, official-state evidence, frozen geometry and source-keyed labels |
| Direct endpoint baseline | Completed and audited | B0–B2, Global/U/A, Grid/Analytic weights, pooled and two fixed-state comparisons |
| B2 empirical transition matrices | Completed and accepted; frozen S1 baseline | Direct 7/30-day tables, support, standard Brier, provenance and maps |
| Fixed versus adaptive B2/B1 | Retained as S2 research outcomes | E1's original target remains preserved; both controls are freshly fitted under the S3 target |
| B1 allocation versus support weights | E2 executed and audited; scientific review pending | Fixed-quality constraints and 131-table replay |
| Equal-drifter destination estimation | E3 v2 executed and audited; scientific review pending | Equal-cell/equal-ID target, three matched models and 199-table replay |
| Partial drifter contribution weighting | E4 executed, audited and replayed | Fixed beta comparison and 231-table replay; retain the disclosed coverage trade-offs |
| Local spatial borrowing | S3 E1 executed, audited and replayed; awaiting scientific review | Five-model benchmark and 212-table replay; LocalEndpoint Brier benefit with hit trade-off, LocalDisplacement fails the quality screen |
| Adaptive local borrowing | S3 E2 executed, audited and replayed | Modest 30-day Brier/coverage benefit with slight region expansion; full Fixed-quality screen fails |
| Neighbour endpoint quality | S3 E3 executed, audited and replayed | Six models and two ablations; 7-day concentration/coverage trade-off, no 30-day incremental gain |
| Empirical Markov M1 and refinements | Completed comparisons retained; outside the current S2 experiment | Revisit propagation and richer states later; neighbour extension remains stopped |
| Continuous-state transition modelling | First Gaussian/MDN experiment and frozen diagnostics completed; **further development paused** | Retain code and evidence as comparisons; no current move to more complex model families |
| Seasonal Markov operators | Subsequent bounded extension | Calendar-aware propagation, seasonal support audit and reviewed sharing/regularisation |
| 1–365-day distributions | Research goal; long-horizon predictive validation remains incomplete | Exact-duration propagation with explicit horizon-specific support and uncertainty |
| 0.5° grid or additional release regions | Deferred until core validation is complete | Separate resolution/support or regional comparison, not simultaneous expansion |
| Grounding and object-specific extensions | Planned | Separate defensible labels and validation; future hardware/object information is not an origin-time predictor |

### Next-stage boundary

The immediate checkpoint is user review of the completed S3 E3 comparison. Its 7-day Brier/region-size benefit comes with lower actual hits, and its 30-day results do not improve the adaptive local anchor. Earlier S3 benchmarks remain preserved. These results do not automatically promote a model or close Step 3; any further search or information source needs a separate bounded decision.

Any further regularisation or spatial/seasonal sharing requires a new bounded decision after this review. Additional model families and neural-model optimisation are not current priorities. A single-step fit, numerical propagation and validated long-horizon predictions remain distinct achievements.

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

The layout verification records [219 passing tests](provenance/migrations/modelling_layout_20261029T065416Z/verification.json); the earlier Markov publication has a separate [test receipt](provenance/reviews/markov_publication_20261028_tests.json). The full suite includes continuous-model tests and requires the optional dependencies declared by `.[continuous]`; Markov-only imports do not require PyTorch. The optional neighbour native scorer must be compiled locally before its numerical tests; see the Markov publication guide. These tests and artifact audits verify implementation and reproducibility, not annual or operational predictive validity.

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
