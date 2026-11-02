# Markov milestone: results and reproduction

**Latest publication: `Markov Step 1 - 3done` — 2 November 2026.**

The [five-step roadmap](../README.md) identifies the current programme: **(1)** empirical matrices, **(2)** regularisation / Bayesian estimation, **(3)** spatial information, **(4)** time/environmental conditioning, and **(5)** memory/latent states. Step numbers identify research directions, not forecast horizons or older M1/M1vcat versions.

This milestone publishes the completed S1, S2 E1–E4 and S3 E1–E4 comparisons, their code, configurations, tests, reports, probability maps and audit evidence. **Step 3** tests borrowing from the eight adjacent origin cells, comparing shared endpoints with translated displacements and then refining borrowing weights and information quality. Completion records the experiments and their limitations; it does not imply that every extension improved prediction or that a Bayesian posterior model has been fitted.

The additional S3 E5 exact-coordinate displacement comparison is deferred. Its [O1 trial](actual_origin_displacement_s3_e5_o1_results.md) did not establish complete-run capacity, and no full-CV forecast scores exist. The O2 continuation remains a proposal. [Step 4 planning](time_environment_s4_architecture.md) and its [seasonal contract draft](seasonal_conditioning_s4_e1_contract.md) are included for review; no Step 4 execution is represented. Step 5 has not started. Final-test trajectories remain locked.

### Current results to read

| Step | Completed evidence |
|---|---|
| 1 | [Empirical B2](empirical_b2_results.md) |
| 2 | [Fixed/adaptive shrinkage](adaptive_b2_b1_results.md), [information/weight refinements](b2_b1_e2_results.md), [equal-ID comparison](drifter_shrinkage_e3_results.md), [partial ID weighting](partial_weighting_e4_results.md) |
| 3 | [Spatial endpoint/displacement benchmark](spatial_borrowing_s3_e1_results.md), [adaptive local weights](local_endpoint_adaptive_s3_e2_results.md), [neighbour quality](local_endpoint_quality_s3_e3_results.md), [joint selection with fallback](local_endpoint_joint_s3_e4_results.md) |

S1/S2 E1–E2 use their original pair-weighted evaluations. S2 E3–E4 and S3 use equal-ID-within-cell and equal-cell primary evaluation. Compare models within a matched experiment; scores from these different targets are not one leaderboard. Read standard Brier together with actual nominal-90% hits, region size, unsupported cases and uncertainty.

### Publication and reproduction scope

The [publication inventory](../provenance/reviews/markov_steps_1_3_publication_20261102.json) records included runs, output-hash verification and omitted caches. Selected primary runs and the spatial input bundle are published with provenance; duplicate replay result bundles and multi-gigabyte caches remain local. Replay provenance and existing audit receipts preserve the distinction. Continuous-model results and diagnostics are included as historical evidence, with optimisation still paused.

Publication checks passed **398 tests** with no failures, errors or skips, and **3,711 frozen output hashes** matched. The [test receipt](../provenance/reviews/markov_steps_1_3_publication_20261102_tests.json) records the checked scope. These checks verify implementation/artifact integrity; they do not constitute new predictive validation.

Download the repository before opening saved `review.html` files; GitHub shows HTML source. Stable deliverable links resolve to published run directories. Reproduction of experiments that require omitted continuous/exact-position caches still requires those matching inputs or a separately approved rebuild. No data cleaning, fitting, final-test evaluation or interrupted-run resumption is part of this publication.

## Earlier publication: Markov Transition Model Completed — 28 October 2026

**Independent S1 entry (29 October):** S1 is completed and accepted. The [scientific closing record](empirical_b2_results.md) supplements the sealed [run report](../results/deliverables/empirical_b2/REPORT.md), [browser view](../results/deliverables/empirical_b2/review.html) and unchanged [approved plan](empirical_b2_plan.md). Standard Brier, unsupported-forecast reporting and the exclusion of spatial/combined loss define this frozen baseline. Its development results and artifact identity remain separate from all historical comparisons below.

**Recorded finding (31 October):** the independent [Step 3 E4 joint endpoint experiment](local_endpoint_joint_s3_e4_results.md) is executed, audited and replayed. Neither horizon achieves a quality-preserving improvement; every constrained selection falls back to LocalEndpointAdaptive because no candidate meets the inner Fixed hit-rate floor. The report separates unconstrained joint tuning, constrained selection, fallback and outer quality acceptance. [E3](local_endpoint_quality_s3_e3_results.md), [E2](local_endpoint_adaptive_s3_e2_results.md) and the [E1 benchmark](spatial_borrowing_s3_e1_results.md) remain unchanged. No automatic model replacement or scientific closure follows.

The publication records the completed empirical Markov comparisons. The neighbour extension
was stopped by the user after one of five outer folds; it is not a completed
comparison. No new training
or final-test evaluation was performed for this publication.

## Read the results

The reports explain the target, case population, fitting procedure, selected
parameters, scores and limitations. Download the repository before opening a
`review.html` file in a browser; GitHub's file view shows HTML source.

| Experiment | Report | Saved probability maps / browser view |
|---|---|---|
| Fixed 1-day M1 | [M1 report](../results/runs/markov_m1_1d_20261025T100248_328450Z/REPORT.md) | [Browser view](../results/runs/markov_m1_1d_20261025T100248_328450Z/review.html) |
| Error diagnosis | [Diagnostic scores](../results/runs/markov_diagnosis_20261025T114721_490747Z/summary.csv) | [Bias by horizon](../results/runs/markov_diagnosis_20261025T114721_490747Z/bias_by_horizon.svg) |
| Lag selection | [Lag-CV report](../results/runs/markov_lag_cv_20261025T114838_137131Z/REPORT.md) | [Browser view](../results/runs/markov_lag_cv_20261025T114838_137131Z/review.html) |
| Categorical velocity | [M1vcat report](../results/runs/markov_vcat_cv_20261026T155955_651594Z/REPORT.md) | [Browser view](../results/runs/markov_vcat_cv_20261026T155955_651594Z/review.html) |
| Exact release coordinates | [Position report](../results/runs/markov_position_cv_20261027T094335_386746Z/REPORT.md) | [7-day map](../results/runs/markov_position_cv_20261027T094335_386746Z/probability_7d.svg), [30-day map](../results/runs/markov_position_cv_20261027T094335_386746Z/probability_30d.svg), [browser view](../results/runs/markov_position_cv_20261027T094335_386746Z/review.html) |
| Joint 30-day schedule / weight selection | [Iteration report](../results/runs/markov_iteration_cv_20261027T120356_034230Z/REPORT.md) | [30-day map](../results/runs/markov_iteration_cv_20261027T120356_034230Z/probability_30d.svg), [browser view](../results/runs/markov_iteration_cv_20261027T120356_034230Z/review.html) |
| Neighbour displacement borrowing — stopped, partial | [First-fold report](../results/deliverables/markov_neighbour_progress/REPORT.md) | [Display data](../results/deliverables/markov_neighbour_progress/display_data.json), [stop receipt](../provenance/runs/markov_neighbour_cv_20261028T105824_991491Z/STOPPED_BY_USER.json) |

These are development results. Entire drifter IDs separate fitting from held-out
evaluation. Hourly origins within an ID are correlated. A lower S is better;
S is not percentage accuracy. Nominal-90% hit rate and prediction-region size
must be read together. Probability per grid cell is not continuous density, and
an unobserved cell in a finite validation cohort is not necessarily impossible.

M1 uses a stopped-domain target: first observed exit from D is absorbing.
Unresolved mass is retained, not relabelled as grounding. Direct endpoint
baselines and stopped-domain forecasts are different targets unless explicitly
compared on matched cases. Annual-pooled 7/30-day results do not establish
seasonal, 365-day, grounding or object-specific predictive validity.

## What this publication contains

- Markov source, configurations and tests under `src/data3001/modelling/`,
  `configs/` and `tests/`.
- Nine selected complete input/result runs and their provenance, approximately
  596 MB in total before Git compression. The [publication receipt](../provenance/reviews/markov_publication_20261028.json)
  lists each run, verified output count and size.
- Reports, numerical scores, selected settings, operators where produced,
  probability maps and independent audit evidence. The existing cleaned data
  and qualification files are unchanged.
- The stopped neighbour experiment's first-fold summary, display data, snapshot
  audit and stop receipt. Remaining computation is intentionally incomplete.

The multi-gigabyte exact-position input cache
`markov_position_input_20261027T093543_211496Z` and geometry cache
`markov_iteration_geometry_20261027T114759_607891Z` are retained locally.
Their provenance is published, but their large result arrays are not included
in the team download. Interrupted neighbour checkpoints and runtime process logs
also remain local. No checkpoint was deleted to prepare this publication.

Consequently, published summaries can be inspected immediately, but reproducing
every particle-level audit requires rebuilding the omitted caches or obtaining
the matching local checkpoint bundle. In particular,
`provenance/reviews/build_neighbour_progress.py` needs the local partial run's
raw particle files; the published display JSON is not a substitute for them.

## Environment and checks

Follow [the setup guide](getting_started.md) for Python 3.12.14, the pinned
dependencies and an editable installation. No training is needed to read reports
or open the saved maps. The publication checks passed 202 modelling and
architecture tests; [the test receipt](../provenance/reviews/markov_publication_20261028_tests.json)
records zero failures, errors, skipped tests or final-test open attempts.

The optional neighbour scoring backend is compiled locally from the published
C++ source. The current loader retains its historical build-cache path; that
directory name is not a requirement to install or run a workflow plugin.
On the tested macOS toolchain, compile it before running the full modelling
suite, which includes native-neighbour tests:

```bash
mkdir -p .superpowers/native
clang++ -O3 -std=c++17 -shared -fPIC -ffp-contract=off \
  src/data3001/modelling/markov_models/_neighbour_scoring.cpp \
  -o .superpowers/native/neighbour_scoring.dylib

.venv/bin/python -B -m unittest discover -s tests -p 'test_modelling*.py' -v
.venv/bin/python -B -m unittest discover -s tests -p 'test_architecture.py' -v
```

The compiled binary is not committed. Porting this native backend to another
toolchain requires numerical checks; cross-platform binary compatibility has
not been established.

## Reproduction boundaries

Each accepted run has immutable output hashes and historical input/source
bindings under `provenance/runs/<run>/`. Those source hashes describe the code
used at that stage; later source additions mean they should not all be expected
to equal the current checkout. Do not rewrite an old receipt to make a new run
look identical to it.

The position runner's `--prepare-only` option rebuilds its input cache from the
published development inputs and produces a new run ID. Its `--input-run`
option then fits the frozen-coordinate comparison. The iteration runner's
`--prepare-geometry` option builds geometry for the input run named in its
configuration; `--geometry-run` starts its schedule comparison. Before any
recomputation, review the configuration's parent/input IDs and point it at the
appropriate verified regenerated cache. Geometry and donor row identities must
agree. These are expensive computations, not setup checks.

The archived [iteration reproduction bundle](../provenance/reviews/markov_iteration_cv_20261027T120356_034230Z_reproduction.zip)
preserves source and supporting evidence from that experiment; it does not
include the multi-gigabyte caches. Exact historical reproduction requires its
matching inputs, environment and seeds. A new experiment should create new
run IDs rather than overwrite previous results. Resume guards intentionally
reject mismatched source, configuration or input hashes.

The stopped neighbour calculation must not restart automatically. Its remaining
checkpoints are retained only for a future explicitly approved resumption.
The current next step is review of the [Step 4 seasonal contract](seasonal_conditioning_s4_e1_contract.md); empirical consolidation and the completed spatial comparisons are preserved in the [modelling plan](modelling_round1_plan.md). The source layout migration preserves old import commands but changes source hashes; it does not authorise resuming historical computations.
