# Code guide

This is the current navigation and ownership guide. Scientific decisions remain in the Data Contract and [modelling plan](modelling_round1_plan.md). The 29 October 2026 reorganisation changes source layout, not a model or experiment definition.

## Start here

```text
src/data3001/
  dataset.py, paths.py       Canonical readers, asset identity and write boundaries
  acquisition/              Source acquisition utilities
  preprocessing/            Frozen preparation and qualification logic
  modelling/
    common/                 Shared folds, scores, geometry, I/O and plotting
    baselines/              Direct horizon B0/B1/B2 and their refinements
    markov_models/          Empirical transition operators and propagation
    continuous_models/     Conditional Gaussian and MDN kernels and diagnostics
    _compat/                Forwarding entries for historical imports/commands
    assets/                 Pinned presentation resources
```

Direct B2 estimates a separate endpoint distribution for each horizon. M1 composes shorter transition kernels. Both are learned statistical models. Gaussian and MDN models share an implementation with different mixture counts; placing them together avoids duplicate code. Continuous/discrete state and the Markov assumption are separate modelling choices.

## Shared functions

| Location | Main reusable functions/classes | Boundary |
|---|---|---|
| `common/runtime.py` | `ReadOnlyInputs`, `save_frame`, `save_json`, `verified_run`, `_source_hashes`, `_seal` | Development-only read guards, immutable outputs and receipts; no fitting |
| `common/experiment.py` | `make_folds`, `make_nested_folds`, `fold_digest` | Whole-ID assignments and metadata preview |
| `common/probability.py` | `score_distribution`, `check_scoring` | Categorical probability scores, including unresolved mass |
| `common/markov_scoring.py` | `SpatialScorer`, `cell_coordinates_km` | Conditional geographic scores; filename retained for traceability |
| `common/markov_position_scores.py` | `ensemble_scores`, `aggregate_scores`, `paired_intervals` | Particle-based S and issued-region diagnostics shared with continuous reports |
| `common/geometry.py` | `EndpointMapper`, `mapper_for` | Frozen land/domain geometry; mapper sentinel -1 is not the Markov U state -3 |
| `common/plotting.py` | `map_svg`, `markdown_table`, `_rings` | Presentation only; does not change distributions or weights |

The root `dataset.py` and `paths.py` remain authoritative for data access and output placement. Some historical runners still expose shared functions as re-exports so old scripts continue to work. New code imports their `common/` owners directly.

The continuous workflow still uses the historical Markov input/cache identity helpers. This preserves its original source contract; it does not train a discrete Markov model. Changing that experiment's input identity is separate work. Baseline fitting helpers are also reused as comparison controls by Markov experiments.

## Empirical-matrix reading order

1. [`markov_inputs.py`](../src/data3001/modelling/markov_models/markov_inputs.py): turn qualified development trajectories into source-keyed stopped counts. Existing eligibility and observed-hour first-exit definitions are reused.
2. [`markov.py`](../src/data3001/modelling/markov_models/markov.py): `fit_operator` normalises each supported count row; unsupported rows send mass to U. `propagate` and `forecast` compose kernels and exact remainders with absorbing E/U.
3. [`markov_velocity.py`](../src/data3001/modelling/markov_models/markov_velocity.py): `coarse_velocity`, `fit_joint` and joint propagation extend the state to cell plus nine velocity categories. Thresholds and counts use fitting IDs only.
4. [`markov_velocity_cv.py`](../src/data3001/modelling/markov_models/markov_velocity_cv.py): compare the existing lag/weight candidates on matched whole-ID cases. Reading this code does not authorise a new search.
5. [M1vcat report](../results/runs/markov_vcat_cv_20261026T155955_651594Z/REPORT.md), its `summary.csv`, `operators/`, `scores.parquet` and `provenance/runs/<run_id>/`: inspect saved evidence before deciding to recompute.

For lag tau, the empirical estimate is `P_tau(i,j) = N_tau(i,j) / sum_j N_tau(i,j)`. Counts include only qualified fitting-role pairs, with each eligible pair equally weighted. For a one-day operator, a release distribution propagates as `p_h = p_0 P_1^h`. Other lags need a separately fitted exact remainder kernel. B2 instead estimates `P(X_h=j | release cell=i)` directly for each h.

With known initial velocity, the richer empirical state is `(cell, velocity category)`; the propagated joint distribution is marginalised over velocity at the requested horizon. Raw and selected-shrinkage variants remain distinct controls. The accepted workbench is annual-pooled, not a claim of validated year-long predictions.

Stage 1 reuses these fitted counts, operators, role assignments and same-case results. Remaining work is to connect independent-ID support and dominant-ID contribution to forecast visitation and held-out error, check the agreed invariants, and make the existing evidence easy to review. Shrinkage, seasonality and additional memory are later bounded experiments, not changes bundled with this layout.

## Commands and compatibility

The following are safe help checks, not training commands:

```bash
.venv/bin/python -B -m data3001.modelling.markov_models.run_markov --help
.venv/bin/python -B -m data3001.modelling.markov_models.run_markov_velocity --help
.venv/bin/python -B -m data3001.modelling.continuous_models.run_continuous --help
```

Historical commands such as `data3001.modelling.run_markov` still forward to the canonical implementation. The package-local `_compat/` directory is deliberately separate from active code. It aliases the same module objects, including private helpers needed by historical callers. It does not load all model families at startup. Markov/common imports do not require PyTorch.

Source hashes change when imports and locations change. Old run receipts, fitted outputs and checkpoints stay untouched. Never replace their hashes or bypass resume guards to make a historical run appear identical. The migration's local `before/` snapshot and `migration.json` preserve the pre-change source and path/symbol mapping, including pre-existing uncommitted work. That snapshot is recovery evidence, not another active code tree.

## Maintenance rules

- Put reusable functions in `common/`; keep model-specific estimators, inputs, runners and reports in their family.
- Preserve one implementation of each function. Compatibility files only forward; do not edit scientific logic there.
- Keep model mathematics and pure transformations separate from file I/O and experiment selection.
- Add modules only for a clear responsibility. Do not split an existing family into speculative frameworks.
- Keep configs, tests and immutable results in their established locations. Existing descriptive test filenames still map directly to the family modules.
- Record a new run ID for new scientific experiments. Layout checks and unit tests are not evidence of predictive improvement.
- Preserve pooled/fixed-state distinctions, E/U, whole-ID splits and the locked final test in every future change.

## Complete active module inventory

The inventory below is grouped by owner. `_compat/` contains one forwarding file for each migrated flat module and has no additional scientific implementation.

### Shared services

| Module | Responsibility |
|---|---|
| [experiment.py](../src/data3001/modelling/common/experiment.py) | Deterministic whole-ID folds; metadata-only experiment preview. |
| [geometry.py](../src/data3001/modelling/common/geometry.py) | Shared endpoint geometry; mapper sentinels are distinct from model states. |
| [markov_position_scores.py](../src/data3001/modelling/common/markov_position_scores.py) | Numerical integration of the unchanged categorical S, plus issued-ensemble diagnostics. |
| [markov_scoring.py](../src/data3001/modelling/common/markov_scoring.py) | Separate categorical and conditional spatial scores; canonical data unchanged. |
| [plotting.py](../src/data3001/modelling/common/plotting.py) | Shared static map and table rendering; no fitting or trajectory access. |
| [probability.py](../src/data3001/modelling/common/probability.py) | Shared categorical probability scores, including unresolved mass. |
| [runtime.py](../src/data3001/modelling/common/runtime.py) | Shared read guards and immutable run I/O; no model fitting. |

### Direct horizon baselines

| Module | Responsibility |
|---|---|
| [blend.py](../src/data3001/modelling/baselines/blend.py) | Fixed-base probability mixing and Brier-based lambda selection |
| [cv.py](../src/data3001/modelling/baselines/cv.py) | Whole-instrument nested CV for a fixed B2/B1 probability blend. |
| [evaluate.py](../src/data3001/modelling/baselines/evaluate.py) | Historical baseline evaluation; shared scoring is re-exported from common. |
| [neighbourhood.py](../src/data3001/modelling/baselines/neighbourhood.py) | Local endpoint sharing and empirical-prior WGS84 displacement transfer. |
| [neighbourhood_cv.py](../src/data3001/modelling/baselines/neighbourhood_cv.py) | Whole-ID nested development evaluation of two local-sharing hypotheses. |
| [neighbourhood_report.py](../src/data3001/modelling/baselines/neighbourhood_report.py) | Independent saved-forecast checks and one readable, non-visual report. |
| [regimes.py](../src/data3001/modelling/baselines/regimes.py) | Contract-preserving fixed-state qualification and matched development comparisons. |
| [report.py](../src/data3001/modelling/baselines/report.py) | Source-backed review of saved developmental nested-CV predictions. |
| [run_blend_cv.py](../src/data3001/modelling/baselines/run_blend_cv.py) | Reproducible development-only nested CV and final candidate refitting. |
| [run_neighbourhood.py](../src/data3001/modelling/baselines/run_neighbourhood.py) | Guarded, no-visualisation pooled neighbourhood baseline experiment. |
| [run_regimes.py](../src/data3001/modelling/baselines/run_regimes.py) | Fixed-regime development baselines. No final-test access or visualisation. |
| [run_round1.py](../src/data3001/modelling/baselines/run_round1.py) | Initial direct baseline fitting and pair preview. |
| [showcase.py](../src/data3001/modelling/baselines/showcase.py) | Export an offline presentation from a sealed development experiment. |

### Empirical Markov models

| Module | Responsibility |
|---|---|
| [markov.py](../src/data3001/modelling/markov_models/markov.py) | Empirical stopped-domain Markov operators; no data access or fitting choices. |
| [markov_diagnostic_inputs.py](../src/data3001/modelling/markov_models/markov_diagnostic_inputs.py) | Qualified lag counts and retrospective matched cohorts; no new cleaning. |
| [markov_diagnostic_report.py](../src/data3001/modelling/markov_models/markov_diagnostic_report.py) | One human-facing diagnosis/optimisation report, source-backed static maps. |
| [markov_diagnostics.py](../src/data3001/modelling/markov_models/markov_diagnostics.py) | Fixed-cohort diagnostics and whole-ID nested lag selection; no file access. |
| [markov_inputs.py](../src/data3001/modelling/markov_models/markov_inputs.py) | Source-keyed stopped labels and sufficient counts; no new cleaning rules. |
| [markov_iteration.py](../src/data3001/modelling/markov_models/markov_iteration.py) | Same empirical transport law; explicit schedules and unbiased CV scoring. |
| [markov_iteration_coarse.py](../src/data3001/modelling/markov_models/markov_iteration_coarse.py) | Exact coordinate-discarded control from the same fitting donor frequencies. |
| [markov_iteration_cv.py](../src/data3001/modelling/markov_models/markov_iteration_cv.py) | All-path lambda CV; no fixed-lambda elimination or held-ID tuning. |
| [markov_iteration_geometry.py](../src/data3001/modelling/markov_models/markov_iteration_geometry.py) | Exact numerical cache; not model predictors or altered statistical weights. |
| [markov_iteration_outer.py](../src/data3001/modelling/markov_models/markov_iteration_outer.py) | Untouched outer-case evaluation after schedule/lambda choices are locked. |
| [markov_iteration_report.py](../src/data3001/modelling/markov_models/markov_iteration_report.py) | One English account of selection, coordinate ablation and held-ID evidence. |
| [markov_iteration_strata.py](../src/data3001/modelling/markov_models/markov_iteration_strata.py) | Stratified integration of the UNCHANGED affine empirical transition law. |
| [markov_neighbour.py](../src/data3001/modelling/markov_models/markov_neighbour.py) | Equal-pair adjacent-cell displacement kernels; no new predictors. |
| [markov_neighbour_cv.py](../src/data3001/modelling/markov_models/markov_neighbour_cv.py) | Same-case grouped-ID CV with fresh joint proposals at every precision call. |
| [markov_neighbour_integration.py](../src/data3001/modelling/markov_models/markov_neighbour_integration.py) | Exact-law deterministic-mixture quadrature for joint alpha/lambda CV. |
| [markov_neighbour_native.py](../src/data3001/modelling/markov_models/markov_neighbour_native.py) | Optional local compiled arithmetic; independent NumPy reference remains tested. |
| [markov_neighbour_report.py](../src/data3001/modelling/markov_models/markov_neighbour_report.py) | Readable same-case results; fixed-fit ID uncertainty is separate from MC. |
| [markov_position.py](../src/data3001/modelling/markov_models/markov_position.py) | M1vcat empirical displacement refinement. No new statistical estimator. |
| [markov_position_inputs.py](../src/data3001/modelling/markov_models/markov_position_inputs.py) | Immutable source-keyed donor cache for exact-position M1vcat. |
| [markov_position_report.py](../src/data3001/modelling/markov_models/markov_position_report.py) | Human-readable exact-position comparison, with shared-scale cohort maps. |
| [markov_report.py](../src/data3001/modelling/markov_models/markov_report.py) | English, source-backed report and shared-scale static probability maps. |
| [markov_velocity.py](../src/data3001/modelling/markov_models/markov_velocity.py) | Pure categorical-velocity joint Markov operators; no trajectory access. |
| [markov_velocity_cv.py](../src/data3001/modelling/markov_models/markov_velocity_cv.py) | Same-case, location-marginal selection for categorical velocity kernels. |
| [markov_velocity_inputs.py](../src/data3001/modelling/markov_models/markov_velocity_inputs.py) | Lossless per-ID velocity count cache; fitting-only median definitions. |
| [markov_velocity_report.py](../src/data3001/modelling/markov_models/markov_velocity_report.py) | One English report and velocity-matched probability-map illustrations. |
| [run_markov.py](../src/data3001/modelling/markov_models/run_markov.py) | Guarded fixed-one-day M1 preparation and outer-ID validation. |
| [run_markov_diagnostics.py](../src/data3001/modelling/markov_models/run_markov_diagnostics.py) | Guarded diagnosis -> bounded nested lag optimisation. |
| [run_markov_iteration.py](../src/data3001/modelling/markov_models/run_markov_iteration.py) | Guarded, resumable all99 schedule/lambda development comparison. |
| [run_markov_neighbour.py](../src/data3001/modelling/markov_models/run_markov_neighbour.py) | Guarded, resumable 7/30-day neighbour joint CV; final-test access absent. |
| [run_markov_position.py](../src/data3001/modelling/markov_models/run_markov_position.py) | Guarded frozen-fold exact-position M1vcat experiment. Final test is locked. |
| [run_markov_velocity.py](../src/data3001/modelling/markov_models/run_markov_velocity.py) | Guarded preparation, pilot and nested M1vcat comparison. Never reads test. |

### Continuous Gaussian / MDN models

| Module | Responsibility |
|---|---|
| [continuous.py](../src/data3001/modelling/continuous_models/continuous.py) | One-hour continuous-state Gaussian mixtures. No data access or fitted globals. |
| [continuous_diagnostic_report.py](../src/data3001/modelling/continuous_models/continuous_diagnostic_report.py) | Human-facing frozen-model diagnostic report and observed-state control. |
| [continuous_diagnostics.py](../src/data3001/modelling/continuous_models/continuous_diagnostics.py) | Frozen-model diagnostics; no fitting, new predictors, or final-test access. |
| [continuous_inputs.py](../src/data3001/modelling/continuous_models/continuous_inputs.py) | Reproducible one-hour cache; source records and final test remain untouched. |
| [continuous_report.py](../src/data3001/modelling/continuous_models/continuous_report.py) | Matched development comparison and source-backed continuous-model figures. |
| [run_continuous.py](../src/data3001/modelling/continuous_models/run_continuous.py) | Fit Gaussian/MDN one-hour kernels with whole-ID parameter CV. |
