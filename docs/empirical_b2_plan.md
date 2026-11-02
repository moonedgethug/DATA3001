# Stage 1 — Independent Standard B2 Engineering Plan

**Version:** E2, 29 October 2026. **Status:** approved by the user, including unsupported-row treatment; development, execution and result audit authorised. Research-stage closure remains subject to user review.

The [Research Stage Ledger](research_stage_ledger.md) records approved decisions. The Data Contract and explicitly approved amendments govern scientific definitions. This is the single current detailed S1 implementation plan; older planning snapshots and experiment reports remain historical evidence.

## 1. Objective and locked scope

Estimate and evaluate cell-only empirical destination probabilities at 7 and 30 days. Deliver a reproducible benchmark with support and limitations; favourable scores are not a completion requirement.

| Item | Definition |
|---|---|
| Data | Final cleaned `per-drifter-cleaned-20261017-v7`; existing development pool only |
| Contract | English v1.0, SHA256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`, with approved subsequent amendments |
| Geometry | Frozen release polygon R, transport domain D and 1-degree state index |
| Scenario | Annual-pooled; retain existing qualification, without new drogue or seasonal conditioning |
| Inputs to B2 | Origin cell and requested horizon only; initial velocity is not a predictor |
| Horizons | Exactly 7 and 30 days, estimated separately |
| Target | Existing stopped target: first observed exit from D becomes E, including exit followed by re-entry; missing follow-up is not E |
| Weights | Equal eligible hourly pairs; grouped counts preserve their multiplicities |
| Estimator | `P_h(i,j) = N_h(i,j) / sum_k N_h(i,k)` for supported rows, using fitting IDs only |
| Main score | Standard, unnormalised multiclass Brier; no spatial score or combined loss |
| Validation | Existing five whole-ID development folds; no inner CV or parameter search |
| Final test | Locked; no final-test trajectories or outcomes may be opened |

No smoothing, pseudocounts, minimum-support filtering, B1 backoff, neighbour borrowing, velocity categories, environmental features, recursive propagation, M1/M1vcat/MDN fitting or other horizons are part of this experiment. Neither a daily kernel nor a matrix-power relationship between the two horizons is required.

## 2. Independent experiment and permitted reuse

Independence means a distinct scientific run, configuration, implementation entry point, fitted tables, predictions, scores and report. It does not mean a previously untouched statistical test sample: these are development data already used during research.

Permitted reused inputs are explicitly allowlisted:

- `configs/dataset_manifest.json`, `configs/assets.json`, approved geometry/state assets and the existing data qualification definitions.
- The data-only `release_counts_by_id.parquet` from `results/runs/markov_input_20261025T095949_830292Z/`, with its source-keyed release labels and provenance for validation. Select only 7/30-day R-origin stopped counts. This cache contains qualified counts, not fitted B2 probabilities.
- The data-only ID assignments in `results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv`. Copy the verified assignments into the new run for a self-contained validation record; do not import that run's experiment settings.
- Audited common utilities for paths, guarded read-only inputs, hashing, numerical validation, standard Brier arithmetic and basic map rendering. Record the actual imported source files and their hashes.

Before fitting, verify input hashes against their receipts, v7 source provenance, development-only ID membership, required columns, unique count keys, positive integral counts, valid states and qualification semantics. Reconcile the selected counts with the source-keyed eligible release labels. Current model code need not match old source hashes; historical receipts must remain unchanged. A missing or incompatible cache stops the run for an explicit repair proposal; it must not trigger an old multi-model pipeline.

Do not read historical fitted matrices, forecasts, scores, summaries or selected model parameters as new-run inputs. Do not call combined B1/B2, Markov or continuous experiment runners. In particular, do not inherit `common.experiment.SETTINGS`, which contains historical endpoint/blend settings. Do not use old numerical results as regression targets or tuning criteria. Numerical agreement may occur with identical definitions, but is not the acceptance test.

## 3. Matrix and unsupported-row definitions

Use the frozen 1-degree R-intersection index for source rows, including rows without observed support. Eligibility of actual release points still uses the frozen R polygon. Destination columns are the frozen 1-degree D cells plus physical exit state E; do not choose the destination universe from observed held-out outcomes. Export source and destination indexes separately: these R-to-D tables are direct horizon forecasts, not square D-to-D propagation operators.

For each fitting role and horizon, export sparse transition counts, row totals, empirical probabilities, contributing unique-ID counts, largest-ID contribution share and an explicit supported-row mask. An absent destination entry in a supported row means probability zero. Exported indexes make zero columns and unsupported rows reconstructible.

- If the row total is positive, preserve exact empirical zeros and normalise by that row total; unresolved mass is zero.
- If the row total is zero, the empirical distribution is undefined. Store the unsupported status and unresolved mass one; a zero-filled storage row is not a valid probability distribution. Do not invent a self-loop, uniform distribution or fallback.
- E is a physical outcome. Unresolved is support bookkeeping, stored separately from physical destination columns; do not count it twice.
- Reject unexplained probability deficits or excesses. Require finite nonnegative probabilities and `sum(physical probabilities) + unresolved = 1` within absolute tolerance `1e-12`.

## 4. Standard Brier and reporting denominators

For an evaluable forecast with observed state y:

`Brier(p,y) = sum_j (p_j - 1[j=y])^2 = 1 - 2*p_y + sum_j p_j^2`.

Here j includes all D-cell outcomes and E. Do not divide by the number of states, take a square root, clip zero probabilities or redistribute E/unresolved mass. No optimiser changes the empirical probabilities to reduce this score.

**Approved unsupported-row rule:** compute standard Brier only where a complete empirical forecast exists. Unsupported forecasts receive a missing Brier with reason `unsupported_origin`, not an automatic failure score of 2. Do not report or substitute the historical failure-penalised S metric; if a shared helper also returns legacy metrics, discard those fields. This makes the approved standard-Brier choice explicit while keeping failures visible.

Every horizon summary must show together:

- Total eligible held-out pair count and contributing ID count.
- Evaluable and unsupported pair counts and proportions, with their ID support.
- Pair-weighted mean Brier over evaluable cases, explicitly labelled as conditional on available support; never present it as an all-case score when failures exist.
- The number and fraction of evaluable cases with zero probability at the observed destination. Such cases still receive their ordinary finite Brier score; they are not unresolved.
- Support and Brier summaries by origin cell, together with observed/predicted E diagnostics. Absence of observed exits cannot establish exit calibration.

Combine held-out scores using pair counts, not an unweighted average of fold means. The two horizons have separate summaries and may have different eligible cases. No log-loss, spatial-distance, mean-location or weighted composite score is required in this S1 run. Probability maps are descriptive outputs, not spatial scoring. Document that Brier does not distinguish near and distant wrong cells.

## 5. Validation and execution sequence after confirmation

1. **Freeze inputs and configuration.** Record the approved plan version, contract/manifest/geometry/count/fold hashes, explicit scoring rules, source hashes, dirty-worktree state and runtime environment. Apply development-only access and immutable-output guards. No cleaning or source-data changes.
2. **Implement and check the estimator.** Add a B2-only count normalisation function and the minimal independent runner/report adapter. Use public common utilities without modifying legacy model behaviour. Verify synthetic mathematical cases before accessing experiment counts.
3. **Run five whole-ID folds.** For each fold, fit only the other four folds' IDs and generate new 7/30-day forecasts before scoring that fold's held-out outcomes. Every eligible case is evaluated exactly once. Produce ten fold-specific matrices. Do not search for a better fold assignment.
4. **Quantify development uncertainty.** Use 200 whole-ID bootstrap resamples of the saved out-of-fold cases, seed `20261029`. Resample development IDs with replacement, preserving each ID's eligible pairs and weights. Report 2.5/97.5 percentile intervals for mean Brier and forecast availability; disclose undefined resamples. Fits/folds remain fixed, so these are sampling intervals conditional on the fitted forecasts, not full refitting uncertainty or final-test evidence.
5. **Fit two development candidates.** Estimate 7/30-day matrices from all development IDs. Label them `all_development_candidate`, distinct from fold-evaluated matrices; do not score them on their fitting data as validation evidence.
6. **Produce and audit the report.** Reconcile outputs to counts and indexes, verify score arithmetic independently, inspect maps and provenance, and report limitations. Submit the result for the user's S1 closure review; do not automatically start S2.

For the two descriptive candidate maps, choose one common release cell by the largest minimum of its 7/30-day fitting unique-ID support, breaking ties by increasing cell ID. If no cell supports both horizons, report that limitation rather than selecting by held-out performance. Show the full relevant domain, cell support, target, horizon, E and unresolved mass without renormalising the displayed distribution. These are fitted candidate illustrations, not independent predictive validation.

## 6. Files and deliverables

Keep the existing repository layout; create no second checkout or data copy.

| Planned file/location | Responsibility |
|---|---|
| `src/data3001/modelling/baselines/empirical_b2.py` | Pure B2 count estimator, support metadata and evaluation adapter |
| `src/data3001/modelling/baselines/run_empirical_b2.py` | Guarded input validation, folds, new predictions/scores, bootstrap and candidate fits |
| `src/data3001/modelling/baselines/empirical_b2_report.py` | English report and descriptive 7/30-day maps from this run only |
| `configs/empirical_b2.json` | Explicit S1 settings and allowlisted source assets; no inherited legacy defaults |
| `tests/test_modelling_empirical_b2.py` | Independent semantic and workflow checks |
| `results/runs/empirical_b2_<UTC_run_id>/` | Immutable new experiment artifacts |
| `provenance/runs/empirical_b2_<UTC_run_id>/` | Input/code/environment identities, output hashes and verification receipts |

The new run must include the configuration snapshot, fold assignments, source/destination indexes, transition counts/probabilities and row support for all twelve matrices; held-out predictions and per-case scores with explicit status/weights; horizon and cell summaries; bootstrap settings/results; two descriptive maps; and `REPORT.md`. Preserve fold and candidate roles in filenames or explicit schema fields.

After a successful audit, add a stable `results/deliverables/empirical_b2/` entry to the new report and update current navigation only. Keep all old runs, stopped work, source-data assets and compatibility modules intact. Commit/push are not implied by approval of this implementation plan.

## 7. Acceptance, budget and approval gate

Acceptance checks must independently establish:

- Counts from a hand-built example `[A,B,B,B]` yield probabilities `0.25/0.75`; excluded pairs contribute nothing and held-out IDs cannot affect fitting counts.
- Prediction `A=0.25, B=0.75` with truth B has Brier `0.125`; a certain correct forecast scores `0`, a certain wrong forecast scores `2`; unsupported rows remain unevaluable and are included in availability accounting.
- An unseen destination with a supported origin is scored normally, without fallback. Nonfinite/negative probabilities, unexplained mass errors and leaked IDs are rejected.
- Approved first-exit/re-entry and missing-follow-up distinctions are preserved. Fixed indexes are not derived from held-out destinations.
- All ten fold matrices and two candidate matrices reconcile with their fitting counts; all eligible held-out cases reconcile with evaluable/unsupported totals. No scores or predictions were copied from older experiments.
- Focused new semantic tests, applicable existing probability/runtime tests and architecture/import checks pass. A deterministic replay reproduces numerical tables/scores within `1e-12`, excluding timestamps and run identifiers.
- The report distinguishes development validation, support failures, fixed-fit bootstrap uncertainty and candidate illustrations. It contains no unsupported claim of improved performance, calibrated exits, geographic accuracy or final-test validation.

Estimated engineering effort remains 0.5–1 working day. Set a 30-minute complete-run compute cap; if exceeded, stop and diagnose before resuming or expanding work. B2 requires no GPU training or hyperparameter search. Poor scores or sparse support are reportable findings, not reasons to alter the frozen experiment.

**Gate:** the user has approved this consolidated plan, including B2-only scope, standard Brier, unsupported-row scoring and denominators, and deferral of spatial/combined loss. Development, execution and audit may proceed. After implementation and audit, any S1 conclusion added to the ledger still requires the user's confirmation.
