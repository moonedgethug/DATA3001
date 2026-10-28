# Markov milestone: results and reproduction

**Publication: Markov Transition Model Completed — 28 October 2026.**

This closes the completed empirical Markov comparisons. The neighbour extension
was stopped by the user after one of five outer folds; it is not a completed
comparison. Continuous-state modelling is the next design stage. No new training
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
  src/data3001/modelling/_neighbour_scoring.cpp \
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
The current next step is to agree on the continuous-state model, loss,
comparison design and compute budget in the [modelling plan](modelling_round1_plan.md).
