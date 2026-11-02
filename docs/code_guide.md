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

Direct B2 estimates a separate transition distribution for each horizon and is the current Stage 1 empirical Markov model. M1 composes shorter transition kernels and is deferred to a later stage. Both use empirical frequency estimation. The `baselines/` package describes B2's benchmark role, not a claim that it is non-Markov. Gaussian and MDN models share an implementation with different mixture counts; placing them together avoids duplicate code. Continuous/discrete state and the Markov assumption are separate modelling choices.

## Shared functions

| Location | Main reusable functions/classes | Boundary |
|---|---|---|
| `common/runtime.py` | `ReadOnlyInputs`, `save_frame`, `save_json`, `verified_run`, `_source_hashes`, `_seal` | Development-only read guards, immutable outputs and receipts; no fitting |
| `common/qualified_count_inputs.py` | `ExperimentGuard`, `load_inputs`, `counts_from_labels`, `validate_counts` | Verified v7 qualified counts/labels and frozen indexes; no fitted model inputs |
| `common/prediction_regions.py` | `probability_region`, `budget_inclusion` | 90% regions with cutoff ties and exact-budget expected inclusion; no fitting or renormalisation |
| `common/experiment.py` | `make_folds`, `make_nested_folds`, `fold_digest` | Whole-ID assignments and metadata preview |
| `common/probability.py` | `score_distribution`, `check_scoring` | Categorical probability scores, including unresolved mass |
| `common/markov_scoring.py` | `SpatialScorer`, `cell_coordinates_km` | Conditional geographic scores; filename retained for traceability |
| `common/markov_position_scores.py` | `ensemble_scores`, `aggregate_scores`, `paired_intervals` | Particle-based S and issued-region diagnostics shared with continuous reports |
| `common/geometry.py` | `EndpointMapper`, `mapper_for` | Frozen land/domain geometry; mapper sentinel -1 is not the Markov U state -3 |
| `common/plotting.py` | `map_svg`, `markdown_table`, `_rings` | Presentation only; does not change distributions or weights |

The root `dataset.py` and `paths.py` remain authoritative for data access and output placement. Some historical runners still expose shared functions as re-exports so old scripts continue to work. New code imports their `common/` owners directly.

The continuous workflow still uses the historical Markov input/cache identity helpers. This preserves its original source contract; it does not train a discrete Markov model. Changing that experiment's input identity is separate work. Baseline fitting helpers are also reused as comparison controls by Markov experiments.

## Stage 1: B2 empirical-matrix reading order

S1 is complete and frozen. Read the [scientific closing record](empirical_b2_results.md) for model assumptions, Brier formulas, validation results and maps. S2 has separately approved E1–E4 experiments; the code below remains the S1 benchmark.

1. [Approved E2 plan](empirical_b2_plan.md), [configuration](../configs/empirical_b2.json) and [stage ledger](research_stage_ledger.md): fixed scientific definitions and the approved unsupported-row rule.
2. [`baselines/empirical_b2.py`](../src/data3001/modelling/baselines/empirical_b2.py): B2-only frequency estimation, support metadata, standard Brier and whole-ID bootstrap. Unsupported forecasts retain missing Brier and explicit availability accounting.
3. [`baselines/run_empirical_b2.py`](../src/data3001/modelling/baselines/run_empirical_b2.py): development folds, twelve new matrices, independent arithmetic audit and immutable outputs. Qualified input verification is shared through `common/qualified_count_inputs.py`; old public helper imports remain available. It does not import old model runners or `common.experiment.SETTINGS`.
4. [`baselines/empirical_b2_report.py`](../src/data3001/modelling/baselines/empirical_b2_report.py) and the [independent report](../results/deliverables/empirical_b2/REPORT.md): results, denominator disclosure, support and descriptive maps. No spatial or composite score is used.

The current deliverable is two directly estimated tables, `P_7d` and `P_30d`, using final cleaned v7 data, one-degree cells and annual pooling. Each supported row uses `P_h(i,j) = N_h(i,j) / sum_k N_h(i,k)`. Available initial velocity is not a B2 predictor. Source/destination mappings, counts, independent-ID support, unsupported-row treatment and held-out B2 scores must be auditable. No daily kernel, recursive rollout or cross-horizon matrix-power identity is required.

Run the independent experiment with `.venv/bin/python -B -m data3001.modelling.baselines.run_empirical_b2`; each invocation creates a new run. Use `--replay-of <empirical_b2_run_id>` to compare its numerical tables against a prior run of this independent experiment. Historical `baselines/cv.py`, Markov comparisons and their S scores remain preserved for historical inspection; they are not this experiment's inputs or acceptance targets.

## Stage 2 E1: fixed versus adaptive B2/B1

Read the [approved E1 plan](adaptive_b2_b1_plan.md), [explicit configuration](../configs/adaptive_b2_b1.json) and [audited results](adaptive_b2_b1_results.md). The models share B1, the supported-row mask, stopped targets and equal-pair standard Brier; only the weight schedule differs. Each family/horizon selects one scalar from 21 values using four inner whole-ID groups. Five outer groups assess the full procedure.

| Module | Responsibility |
|---|---|
| [`baselines/adaptive_b2_b1.py`](../src/data3001/modelling/baselines/adaptive_b2_b1.py) | Pure bases, fixed/adaptive weights, candidate selection, evaluation and paired-ID uncertainty |
| [`baselines/run_adaptive_b2_b1.py`](../src/data3001/modelling/baselines/run_adaptive_b2_b1.py) | Guarded independent runner, fitting roles, exports, post-computation S1 regression and replay |
| [`baselines/adaptive_b2_b1_audit.py`](../src/data3001/modelling/baselines/adaptive_b2_b1_audit.py) | Independent counter/vector arithmetic and selection/region/budget audit |
| [`baselines/adaptive_b2_b1_report.py`](../src/data3001/modelling/baselines/adaptive_b2_b1_report.py) | English report, matched candidate maps and held-out diagnostic curves |

Run `.venv/bin/python -B -m data3001.modelling.baselines.run_adaptive_b2_b1`. Add `--replay-of <adaptive_b2_b1_run_id>` for a fresh numerical replay. Each execution has a 30-minute cap and a new immutable run. The frozen S1 predictions are accessed only after new fitting/scoring, for regression audit. No legacy combined-model runner is imported. Research closure remains governed by the stage ledger.

## Stage 2 E2: B1 allocation versus support-weight adjustment

Read the [approved E2 plan](b2_b1_e2_plan.md), [configuration](../configs/b2_b1_e2.json) and [audited results](b2_b1_e2_results.md). Info and Weight have separate 105-candidate grids and a constrained selector: retain Fixed's inner Brier and actual hits, then seek fewer cells in the unchanged 90% probability region. Exact Fixed fallback is mandatory when no candidate qualifies. Their combined form is outside scope.

| Module | Responsibility |
|---|---|
| [`baselines/b2_b1_e2.py`](../src/data3001/modelling/baselines/b2_b1_e2.py) | Pure B1 allocation, support-exponent weights, constrained selection, diagnostics and paired-ID uncertainty |
| [`baselines/run_b2_b1_e2.py`](../src/data3001/modelling/baselines/run_b2_b1_e2.py) | Independent guarded runner, bounded preflight, outer-prediction freeze, candidate refit, audit, replay and sealing |
| [`baselines/b2_b1_e2_audit.py`](../src/data3001/modelling/baselines/b2_b1_e2_audit.py) | Independent count/vector reconstruction, every candidate, selector, predictions, bootstrap and frozen-reference regression |
| [`baselines/b2_b1_e2_report.py`](../src/data3001/modelling/baselines/b2_b1_e2_report.py) | English report, candidate maps and held-out quality/region/support diagnostics |

The [E2 tests](../tests/test_modelling_b2_b1_e2.py) check hand-calculated allocations, support and exit handling, grid scoring, trade-off rejection, fallback and corruption detection. E2 reuses pure base/evaluation helpers from E1 and shared input/region utilities; it does not import E1's runner or fit from historical model outputs.

For reproduction, run `.venv/bin/python -B -m data3001.modelling.baselines.run_b2_b1_e2 --preflight`, then pass its run ID with `--preflight-run <preflight_id>`. Add `--replay-of <b2_b1_e2_run_id>` for the fresh replay. The preflight/code/input identity is checked before a complete execution. Each run writes to its own immutable namespace; [the deliverable alias](../results/deliverables/b2_b1_e2/REPORT.md) identifies the audited primary execution.

## Stage 2 E3 v2: equal-drifter destination estimation

Read the [approved plan](drifter_shrinkage_e3_plan.md), [configuration](../configs/drifter_shrinkage_e3.json) and [audited results](drifter_shrinkage_e3_results.md). EqualID averages local per-ID destination distributions. All models are evaluated with equal IDs within cell and equal cells overall. Fixed retains raw B1/B2 training but selects its blend weight on this new Brier target. The original pair-weighted score is secondary only.

The four E3 modules own the estimator/aggregation, guarded runner, independent audit and report. Existing B2/B1 bases, input guards and region utilities are reused; historical scorer defaults are unchanged. The config's weighting field describes raw qualified-cache provenance; separate training_weighting, primary_weighting and secondary_weighting fields define E3.

Reproduce with `.venv/bin/python -B -m data3001.modelling.baselines.run_drifter_shrinkage_e3 --preflight`, then `--preflight-run <successful_preflight_id>`; use `--replay-of <primary_run_id>` for the fresh replay. Source/input identities must match the successful preflight. The [deliverable alias](../results/deliverables/drifter_shrinkage_e3/REPORT.md) points to the audited primary run.

The [E3 tests](../tests/test_modelling_drifter_shrinkage_e3.py) cover ID contribution invariance, conditioning/denominators, new-target selection, support/exit semantics, independent reconstruction and paired positive ID resampling. The run audit reconstructs all 26 fits and 1,150 candidate identities. Test coverage and numerical reproducibility do not by themselves establish scientific improvement.

## Stage 2 E4: partial drifter contribution weighting

Read the [approved E4 v1 plan](partial_weighting_e4_plan.md), [configuration](../configs/partial_weighting_e4.json) and [results and audit status](partial_weighting_e4_results.md). Every qualified pair is retained. The fixed beta arms give each pair weight `n_id^(-beta)` within its fitting ID/origin/horizon: beta 0 is B2, beta 0.5 is PartialID, and beta 1 is EqualID. E3's equal-ID/equal-cell evaluation remains unchanged. Fixed retains raw B2/B1 and selects only its blend weight; beta is not selected.

| Module | Responsibility |
|---|---|
| [`baselines/partial_weighting_e4.py`](../src/data3001/modelling/baselines/partial_weighting_e4.py) | Partial weights, candidate identities, six main contrasts and region-change diagnostics |
| [`baselines/run_partial_weighting_e4.py`](../src/data3001/modelling/baselines/run_partial_weighting_e4.py) | Locked definitions, input/population checks, roles, freeze, audits and replay |
| [`baselines/partial_weighting_e4_audit.py`](../src/data3001/modelling/baselines/partial_weighting_e4_audit.py) | Independent counters/vectors/scores, uncertainty and E3 control regressions |
| [`baselines/partial_weighting_e4_report.py`](../src/data3001/modelling/baselines/partial_weighting_e4_report.py) | Four-model English report, maps and seven comparison figures |

E4 directly reuses E3's pure fit endpoints, ID/cell aggregation, explicit evaluation weights, diagnostics and Fixed selector. E3 source files, config, plan hash and outputs remain unchanged. E4-specific candidate and uncertainty code includes PartialID and the six-comparison Brier correction; no legacy three-model registry or four-comparison bound is used. Input guards, regions, fitting bases and immutable I/O retain their existing owners.

Reproduce with `.venv/bin/python -B -m data3001.modelling.baselines.run_partial_weighting_e4 --preflight`, then pass `--preflight-run <successful_preflight_id>` for a full run. Add `--replay-of <primary_run_id>` for a fresh full comparison. Code/input identities must match the successful preflight. The [deliverable alias](../results/deliverables/partial_weighting_e4/REPORT.md) identifies the audited primary run. Reproduction commands do not authorise broader searches or final-test access.

The [28 E4 tests](../tests/test_modelling_partial_weighting_e4.py) cover the 90/10 example, power-versus-linear weighting, local count boundaries, replication properties, fixed evaluation weights, six-contrast resampling and unchanged Fixed selection. The full audit reconstructs 26 fitting roles, 1,200 candidate identities and all outer forecasts, then checks 158 corresponding E3 control tables. Scientific retention remains subject to user review.

## Step 3 E1: local spatial borrowing

Read the [approved S3 E1 plan](spatial_borrowing_s3_e1_plan.md), [configuration](../configs/spatial_borrowing_s3_e1.json) and [results](spatial_borrowing_s3_e1_results.md). This independent direct-horizon experiment compares B2, Fixed, Adaptive, LocalEndpoint and LocalDisplacement. It does not resume the stopped M1 neighbour extension.

1. [Input preparation](../src/data3001/modelling/baselines/spatial_borrowing_s3_e1_inputs.py) verifies development-only source records, retains the union of required hourly windows and classifies each of the eight adjacent-cell translations. Grid shifts preserve subcell offsets and angular increments. Every failed donor retains its weight and contributes target B2; first observed exits remain absorbing E.
2. [Estimators](../src/data3001/modelling/baselines/spatial_borrowing_s3_e1.py) aggregate raw fitting pairs, construct the two neighbour references, tune the four 21-value grids and evaluate the unchanged E3/E4 target. Only qualified fitting origins within R contribute. Neighbourhood geometry is cached per ID; held-out contributions never enter a fitted reference.
3. [Runner](../src/data3001/modelling/baselines/run_spatial_borrowing_s3_e1.py) enforces the approved configuration, 26 isolated fitting roles, the outer-prediction freeze, resource caps, source snapshots, E4 control regression and deterministic replay.
4. [Independent audit](../src/data3001/modelling/baselines/spatial_borrowing_s3_e1_audit.py) uses literal chronological path loops and separate count/probability/score reconstruction. It verifies 4,250 candidate identities and the paired whole-ID multiplier draws.
5. [Report builder](../src/data3001/modelling/baselines/spatial_borrowing_s3_e1_report.py) produces matched maps, held-out metrics, support/boundary strata, fallback and effective-weight diagnostics. Candidate illustration origins are selected only by fitting-ID support and coastline geometry. Strata preserve the original primary case weights and are not selection objectives.

The [path tests](../tests/test_modelling_spatial_borrowing_s3_e1_inputs.py) cover temporal ordering, absorbing exits, source gaps, land/segment disagreement, coordinate alignment and complete source inventory. The [estimator tests](../tests/test_modelling_spatial_borrowing_s3_e1.py) cover donor isolation, probability-preserving fallback, unsupported/no-neighbour rows and candidate selection. Existing B2, Adaptive, prediction-region, E3 and E4 tests remain applicable. Numerical success and passing tests do not establish a predictive improvement; consult the held-out results and uncertainty.

## Step 3 E2: adaptive LocalEndpoint borrowing

Read the [approved plan](local_endpoint_adaptive_s3_e2_plan.md), [configuration](../configs/local_endpoint_adaptive_s3_e2.json), [results](local_endpoint_adaptive_s3_e2_results.md) and [visual comparison](../results/deliverables/local_endpoint_adaptive_s3_e2/review.html).

| Module | Responsibility |
|---|---|
| [Estimator](../src/data3001/modelling/baselines/local_endpoint_adaptive_s3_e2.py) | Unchanged raw B2/neighbour frequencies, distinct-ID support unions, normalised support-ratio weights and gamma-zero nesting |
| [Runner](../src/data3001/modelling/baselines/run_local_endpoint_adaptive_s3_e2.py) | Input/resource preflight, locked configuration, 26 whole-ID fitting roles, prediction freeze, four-control regression and fresh replay |
| [Independent audit](../src/data3001/modelling/baselines/local_endpoint_adaptive_s3_e2_audit.py) | Separate Counter/set reconstruction, direct rational weights, all candidate scores, selected probabilities, uncertainty and acceptance checks |
| [Report](../src/data3001/modelling/baselines/local_endpoint_adaptive_s3_e2_report.py) | Five-model metrics, support/weight diagnostics, interval/per-cell plots and matched probability maps |
| [Tests](../tests/test_modelling_local_endpoint_adaptive_s3_e2.py) | Fourteen new semantic/identity tests, alongside shared regression tests |

This experiment reuses qualified count/label inputs, raw B2/B1/global-Adaptive, common probability-region logic, E3 equal-ID/equal-cell scoring, immutable I/O, and pure geometry/report utilities. It never requests displacement transfers or canonical tracks. Previous source modules and sealed experiments remain unchanged. The two spatial families share the same neighbour reference; ID counts affect the new borrowing weight, not training contributions. Candidate selection is Brier-only; acceptance separately screens Brier, K90 and H90.

Run `run_local_endpoint_adaptive_s3_e2 --preflight`, then `--pilot-run <successful_pilot_id>`; add `--replay-of <primary_run_id>` for a complete fresh replay. Use the project `.venv` and thread-limit environment shown in the results document. The stable deliverable alias points to the audited primary run. Reproduction does not authorise a wider search or final-test access.

## Step 3 E3: neighbour endpoint information quality

The [approved plan](local_endpoint_quality_s3_e3_plan.md) and [locked configuration](../configs/local_endpoint_quality_s3_e3.json) define a separate experiment. See the [audited results](local_endpoint_quality_s3_e3_results.md) and [visual comparison](../results/deliverables/local_endpoint_quality_s3_e3/review.html). It keeps all five S3 E2 controls and adds LocalEndpointQuality; it does not change earlier model implementations or resume trajectory borrowing.

| Module | Responsibility |
|---|---|
| [Estimator](../src/data3001/modelling/baselines/local_endpoint_quality_s3_e3.py) | Geographic distribution overlap, deduplicated endpoint-ID evidence, exact 1%/three-ID weak-unseen gates, E-preserving mass return, anchor-first quality selection and endpoint-category diagnostics |
| [Runner](../src/data3001/modelling/baselines/run_local_endpoint_quality_s3_e3.py) | Frozen config/inputs, 26 whole-ID fitting roles, nine quality settings after each adaptive anchor selection, outer freeze, five-control regression and complete replay |
| [Independent audit](../src/data3001/modelling/baselines/local_endpoint_quality_s3_e3_audit.py) | Separate Counter/set reconstruction, L1-derived overlap, candidate/selection/probability/category checks and 18 directional uncertainty screens |
| [Report](../src/data3001/modelling/baselines/local_endpoint_quality_s3_e3_report.py) | Six-model comparison, two selected-setting ablations, donor/category maps, endpoint-group accounting and matched 90% probability maps |
| [Tests](../tests/test_modelling_local_endpoint_quality_s3_e3.py) | Thirteen new semantic, leakage, neutral-identity, independent-reconstruction and configuration checks |

Reused public functions retain raw-pair B2/B1/LocalEndpoint estimates, the original local/global adaptive schedules, qualification guards, prediction regions, and equal-ID/equal-cell evaluation. A rejected weak-unseen contribution is explicitly returned to local B2 conditional on D; E is unchanged. Nominal lambda and lambda-times-returned-mass are both reported. Ablations are not separately tuned winners.

Run with the project `.venv`, setting `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1`. The module `data3001.modelling.baselines.run_local_endpoint_quality_s3_e3` accepts `--preflight`, then `--pilot-run <sealed_pilot_id>`, and `--replay-of <primary_run_id>` for fresh reproduction. Configuration and source changes invalidate an old pilot. Experiment completion is not model replacement, stage closure or permission to expand the grid.

## Later propagation references

[`markov.py`](../src/data3001/modelling/markov_models/markov.py) contains cell-only empirical operators and exact-remainder propagation. [`markov_velocity.py`](../src/data3001/modelling/markov_models/markov_velocity.py) extends the state to cell plus velocity category through `fit_joint_operator`; [`markov_velocity_cv.py`](../src/data3001/modelling/markov_models/markov_velocity_cv.py) contains its existing candidate selection. These implementations and results remain intact for later stages. They are not prerequisites for the current B2 deliverable.

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
| [prediction_regions.py](../src/data3001/modelling/common/prediction_regions.py) | Probability regions and analytical exact-budget tie inclusion; no model fitting. |
| [qualified_count_inputs.py](../src/data3001/modelling/common/qualified_count_inputs.py) | Shared qualified-cache validation, indexes, source reconciliation and read allowlists. |
| [runtime.py](../src/data3001/modelling/common/runtime.py) | Shared read guards and immutable run I/O; no model fitting. |

### Direct horizon baselines

| Module | Responsibility |
|---|---|
| [empirical_b2.py](../src/data3001/modelling/baselines/empirical_b2.py) | Independent S1 B2 estimator, standard Brier and support-aware summaries |
| [run_empirical_b2.py](../src/data3001/modelling/baselines/run_empirical_b2.py) | Verified data-only inputs, five-fold experiment, arithmetic audit and deterministic replay |
| [empirical_b2_report.py](../src/data3001/modelling/baselines/empirical_b2_report.py) | S1 English report and descriptive candidate maps; no spatial loss |
| [adaptive_b2_b1.py](../src/data3001/modelling/baselines/adaptive_b2_b1.py) | S2 pure bases, fixed/adaptive shrinkage, candidate selection and paired-ID evaluation |
| [run_adaptive_b2_b1.py](../src/data3001/modelling/baselines/run_adaptive_b2_b1.py) | Independent E1 runner, nested roles, immutable output and replay |
| [adaptive_b2_b1_audit.py](../src/data3001/modelling/baselines/adaptive_b2_b1_audit.py) | Independent counts, selection and probability/region/budget arithmetic |
| [adaptive_b2_b1_report.py](../src/data3001/modelling/baselines/adaptive_b2_b1_report.py) | English S2 report, matched candidate maps and support/budget charts |
| [b2_b1_e2.py](../src/data3001/modelling/baselines/b2_b1_e2.py) | E2 allocation and support-weight arms, constrained selection and diagnostics |
| [run_b2_b1_e2.py](../src/data3001/modelling/baselines/run_b2_b1_e2.py) | E2 bounded preflight, independent runs, freeze, audit and replay |
| [b2_b1_e2_audit.py](../src/data3001/modelling/baselines/b2_b1_e2_audit.py) | Independent all-candidate, forecast, uncertainty and frozen-reference audit |
| [b2_b1_e2_report.py](../src/data3001/modelling/baselines/b2_b1_e2_report.py) | E2 English report, matched candidate maps and held-out diagnostic plots |
| [drifter_shrinkage_e3.py](../src/data3001/modelling/baselines/drifter_shrinkage_e3.py) | EqualID estimates, ID/cell score aggregation, Fixed selection and positive-ID uncertainty |
| [run_drifter_shrinkage_e3.py](../src/data3001/modelling/baselines/run_drifter_shrinkage_e3.py) | Locked E3 v2 config, guarded preflight, nested execution, freeze, audit and replay |
| [drifter_shrinkage_e3_audit.py](../src/data3001/modelling/baselines/drifter_shrinkage_e3_audit.py) | Independent counts, candidate/outer scores, weighting, resampling and historical formula checks |
| [drifter_shrinkage_e3_report.py](../src/data3001/modelling/baselines/drifter_shrinkage_e3_report.py) | English E3 scientific report, complete maps and diagnostic figures |
| [partial_weighting_e4.py](../src/data3001/modelling/baselines/partial_weighting_e4.py) | Fixed beta contribution weighting with unchanged E3 aggregation and controls |
| [run_partial_weighting_e4.py](../src/data3001/modelling/baselines/run_partial_weighting_e4.py) | Isolated E4 preflight, execution, frozen outer predictions and replay |
| [partial_weighting_e4_audit.py](../src/data3001/modelling/baselines/partial_weighting_e4_audit.py) | Independent power-weight, forecast, uncertainty and E3 regression audit |
| [partial_weighting_e4_report.py](../src/data3001/modelling/baselines/partial_weighting_e4_report.py) | E4 English account, four-model metrics, full maps and contribution diagnostics |
| [spatial_borrowing_s3_e1_inputs.py](../src/data3001/modelling/baselines/spatial_borrowing_s3_e1_inputs.py) | S3 guarded hourly path preparation, grid translation, event precedence and sealed donor ledger |
| [spatial_borrowing_s3_e1.py](../src/data3001/modelling/baselines/spatial_borrowing_s3_e1.py) | S3 five estimators, eight-neighbour references, fallback, finite tuning and paired uncertainty |
| [run_spatial_borrowing_s3_e1.py](../src/data3001/modelling/baselines/run_spatial_borrowing_s3_e1.py) | S3 isolated nested validation, frozen outputs, complete source snapshots, controls and replay |
| [spatial_borrowing_s3_e1_audit.py](../src/data3001/modelling/baselines/spatial_borrowing_s3_e1_audit.py) | Independent scalar paths, donor counts, model probabilities, all candidates, scores and uncertainty |
| [spatial_borrowing_s3_e1_report.py](../src/data3001/modelling/baselines/spatial_borrowing_s3_e1_report.py) | S3 English account, five-model maps, quality differences, strata and transfer safeguards |
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

## Step 3 E4: joint endpoint borrowing

Read the [approved plan](local_endpoint_joint_s3_e4_plan.md), [results](local_endpoint_joint_s3_e4_results.md) and [visual comparison](../results/deliverables/local_endpoint_joint_s3_e4/review.html).

| File under `modelling/baselines/` | Responsibility |
|---|---|
| `local_endpoint_joint_s3_e4.py` | 252-triple grid, unchanged reference reuse, both-reference feasibility, Brier adoption, explicit fallback and evaluation |
| `local_endpoint_joint_s3_e4_audit.py` | Independent probability/selection reconstruction, partitioned candidate checks and uncertainty decisions |
| `local_endpoint_joint_s3_e4_report.py` | Eight-model report, constraint/fallback diagrams and matched probability maps |
| `run_local_endpoint_joint_s3_e4.py` | Approved hashes, input isolation, partitioned execution, six-control regression and sealed replay |

Configuration: `configs/local_endpoint_joint_s3_e4.json`. Focused tests: `tests/test_modelling_local_endpoint_joint_s3_e4.py` (16). Candidate ID-origin tables are persisted per fitting role in `candidate_parts/` with a manifest; no complete 17-million-row table is required in memory. Earlier Step 2/3 implementations and results remain untouched.
