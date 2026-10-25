# Round 1 Probability Transport Modelling — Implementation Plan

## Current stage: baseline publication and Markov definition review (2026-10-25)

The user authorised publishing the completed baseline work to main with commit subject `baseline model Completed`, an English README refresh, and entry into Markov construction. The README is the current project/implementation entry. All scientific authority remains in Data Contract v1.0. Completed direct endpoint evidence is retained below; new Markov numerical fitting has not started.

The first Markov definition checkpoint follows the existing contract: 1-degree D-origin short-lag kernel; R-origin release evaluation; fitting-only IDs; separate stopped-target comparators; first observed exit absorbing in the initial finite-D prototype; unresolved disappearance distinct from exit/grounding. The 1/3/5/7-day candidates, seasonal regularisation, remainder handling and support thresholds still require explicit review before fitting. Existing whole-ID folds and final-test lock persist. No new feature selection is implied by publication.

## Completed extension: fixed drogue regimes (final audit 2026-10-25)

User-authorised scope: fit all nine established baseline variants separately on **fixed-drogued** and **fixed-undrogued** 7/30-day endpoint intervals; retain both U and A. No canonical changes, final-test access, visualisation or Git publication. The existing contract and source-audited interval predicates remain authoritative. Fixed state is a retrospective interval qualification, not a future-state predictor; attached status does not establish homogeneous depth (DEPTH-01 remains open).

Execution sequence:
- [x] R1: test interval qualification, source-key joins, mutually exclusive subsets, exact pooled-case matching and paired inference. Reuse official corrections and boundary evidence without imputation.
- [x] R2: prepare new immutable scenario ledgers from the sealed pooled-coordinate input; revalidate pooled eligibility and all matched endpoints against canonical development tracks. Count exclusions against the pooled-eligible denominator, retain secondary predicates, and verify unchanged inputs.
- [x] R3: preflight each scenario/horizon across the unchanged outer-five/inner-four whole-ID assignments. If a required fit/tuning population is empty, report not evaluable rather than resplitting. Unsupported cells preserve unresolved mass.
- [x] R4: run unchanged nine-model nested selection separately per regime. Independently reproduce the five original controls from regime-specific counts, all saved scores and weight choices, U bases and representative A bases. Save numerical stability failures explicitly.
- [x] R5: reweight the frozen pooled OOF predictions onto each identical fixed-regime case population; compare fixed minus pooled for the same model with 200 paired whole-ID resamples within the original outer folds. No raw cross-population ranking. Intervals condition on saved fits, without refitting or selection/numerical uncertainty.
- [x] R6: independent code/artifact review and one combined English report with support, weights, scores, regions, matched comparisons and limitations. Existing per-run audit reports remain evidence, not alternative plans. No annual, seasonal, object-specific or grounding claim.

Preparation `regime_input_20261024T080243_439468Z` verified all 595,316 pooled source pairs against 387 canonical development tracks. Drogued support: 178,082 / 155,188 pairs and 253 / 226 IDs at 7 / 30 days; undrogued: 122,123 / 116,505 pairs and 157 / 142 IDs. Both retain 37 origin cells. All required fold-role-horizon populations are non-empty. Final regression: 67 modelling and 10 architecture tests passed, including an end-to-end nested-control and matched-case fixture.

A fresh reviewer identified misleading pooled-parent wording in the shared report template; the initial fixed run `baseline_drogued_cv_20261024T080432_184210Z` was stopped during its first inner fit and marked FAILED. Corrected text distinguishes regime-specific independent controls from the pooled-parent reference; no incomplete run is evidence.

All source and asset hashes are frozen before fitting. Each new run seals its own outputs and binds its input receipts. Changing model/source code mid-run invalidates completion. The pooled reference is `baseline_neighbour_cv_20261024T065917_879042Z`; coordinate preparation is `neighbour_input_20261024T062737_251970Z`. Prior pooled numerical caveats remain applicable to matched reference predictions. No model variant is preselected as superior.

### Fixed-regime results and current interpretation

The completed scenario runs are `baseline_drogued_cv_20261024T080519_204788Z` and `baseline_undrogued_cv_20261024T083230_432963Z`. Their unified human-facing report is [Fixed-regime baseline comparison](../results/runs/baseline_regime_comparison_20261024T085357_553047Z/REPORT.md). Final independent review passed for both scenario runs and the combined report. Per scenario, all 26 saved fits, 72 weight choices and 18 matched-pool bootstrap comparisons were independently reproduced. The independent review verified 116,802 drogued and 81,666 undrogued score rows, exact sealed inventories, input/source hashes, and development-only whole-ID membership. Every B1/B2/U fitted distribution reconstructed from raw qualified pairs with zero probability discrepancy. The combined report's six tables and concatenated CSVs match their source artifacts. No canonical/test trajectories were modified; final-test reads were zero.

Report wording clarification: the combined report's phrase "All selection uses inner OOF predictions" describes weights used for outer evaluation. Final candidate weights instead use all-development **base outer-OOF** terms, followed by a full-development refit; they are tuning candidates, not independently scored final-refit models. This is documented here without altering sealed report evidence.

Failure-penalised Brier from nested held-out IDs (Analytic variants; lower is better, not percentage accuracy):

| Scenario | Days | Global | Local-U | Local-A |
|---|---:|---:|---:|---:|
| Drogued | 7 | 0.929955 | 0.928774 | 0.926831 |
| Drogued | 30 | 0.989088 | 0.987617 | 0.987952 |
| Undrogued | 7 | 0.946781 | 0.943511 | 0.940892 |
| Undrogued | 30 | 0.991882 | 0.992441 | 0.990626 |

Interpretation:
- The earlier pooled comparison did not prove U superior to A. These fixed-state results reinforce the need to retain both hypotheses: A has lower point scores at 7 days in both scenarios and at 30 days undrogued; U is lower at 30 days drogued, where its A-versus-U interval crosses zero. Conditional A-versus-U intervals exclude zero in the other three comparisons, but A's numerical caveats prevent unqualified superiority claims.
- Local-U versus Global improves conditionally at 30 days drogued (delta -0.001471, interval [-0.002939, -0.000303]) and 7 days undrogued (-0.003270, [-0.004775, -0.001918]). Drogued 7-day and undrogued 30-day intervals cross zero. These are exploratory fixed-fit ID-bootstrap intervals, not final-test or refitting-based uncertainty.
- On exactly matched fixed-state cases, all twelve Global/U/A Analytic fixed-minus-pooled differences are positive, with conditional intervals above zero. Hard state partitioning did not improve these baselines over their corresponding frozen pooled forecasts. This establishes an empirical training-policy comparison, not proof that drogue is irrelevant or that sample size alone causes the difference. Regime-specific support is lower and remains a plausible mechanism requiring separate analysis.
- U's 30-day nominal-90% regions cover 80.40% drogued and 74.62% undrogued, with mean sizes 93.56 and 85.12 cells. Better Brier than B2 does not establish calibrated 90% coverage. A's corresponding coverage is 86.24% / 83.15%, over 111.34 / 104.24 cells. Region availability and unresolved mass remain separate diagnostics.
- A failed the declared numerical stability check in 130/2,444 drogued and 295/2,444 undrogued fit rows, including 1 / 9 final-refit rows. Unsettled inner fits can affect weight selection beyond directly unsettled outer rows. The finite estimator and mass accounting are audited; exact-product integration error is not certified. Global and U do not depend on A's numerical integration.
- A-Analytic mean unresolved mass is 0.155% / 0.306% at drogued 7/30 days and 0.208% / 0.163% undrogued. A drogued 30-day maximum of 100% arises from 218 wholly unsupported cases; mean values cannot imply every case is safe. Exact-complete fractions are not prediction accuracy.

The baseline comparison stage is now computationally complete. Preserve pooled and fixed-state controls and both local hypotheses. Review short-lag Markov target/eligibility and support next; do not silently replace the contract's fixed-state scientific scenarios with pooled transport. Any partial parameter sharing across states is a separate reviewed experiment. Status-only grouping does not resolve DEPTH-01, and annual, seasonal, grounding or arbitrary-object skill remains unvalidated. No visualisation or Git publication is part of this stage.

## Completed implementation: pooled neighbourhood comparison (2026-10-24)

The user approved both neighbourhood hypotheses and authorised direct code implementation, tests, fitting, nested development cross-validation and a readable audit/results report. **No visualisation, Git commit/push, Markov fit or fixed-regime extension is included in this execution.** The Excel Data Contract remains the scientific authority; the approved architecture-conversation specification fixes the neighbourhood experiment below.

**Goal:** Compare raw B0/B1/B2 and the existing global shrinkage against unaligned and displacement-aligned local shrinkage at 7/30 days, using exactly the existing pooled endpoint cases and whole-ID folds.

**Architecture:** Reuse the sealed parent run's source-keyed eligible ledgers and verify them against the current manifest-backed coordinates. Implement local distributions as pure functions, reusing existing mixture/scoring algebra. Build all fitted distributions and alignment anchors from fitting IDs only. New immutable run outputs carry numerical integration diagnostics, training support, predictions and scores. One English report is the human-facing result; this stage guide remains the single implementation guide.

**Scientific constants:** dataset `per-drifter-cleaned-20261017-v7`; contract SHA `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`; pooled endpoint target; R-only actual origins; frozen D and GSHHG high-resolution mapping; aligned 1-degree grid; exact 7/30-day pairing; all eligible pairs equally weighted; development IDs only; existing outer-five/inner-four manifests; no final-test reads or canonical modifications.

**Neighbour definition:** the eight grid-adjacent origin cells, excluding self. Only R-origin eligible fitting pairs are donors. Combine donor pairs equally (not equal cell weights), retain all destination distances, and report neighbour availability and the union of donor IDs. There is no distance/velocity/seasonal weighting and no R-buffer extension.

**Two fitted local bases:** `Local-U` uses the original donor endpoint; `Local-A` takes each donor's WGS84 inverse-geodesic net displacement and applies its initial north-referenced azimuth and distance at the target cell's empirical fitting-origin positions. No rotation, time scaling, centre-point release assumption or synthetic path is introduced. Endpoints outside D map to OUTSIDE; invalid/land synthetic positions map to unresolved mass. No rejected mass is renormalised. Local bases absent due to no donors/anchors are unresolved. Mixtures retain `(1-alpha)*u_B2 + alpha*u_local`.

**Integration ruling:** exact Cartesian integration is used for small donor/anchor products. Large products use repeated random balanced couplings: each coupling preserves *every donor's equal marginal weight and every empirical anchor's equal marginal weight exactly*, while its expectation is the full independent product. Average couplings to approximate that product; record seeds, coupling counts and mass/marginal checks. Increase coupling batches by a fixed training-only numerical rule, comparing the maximum possible change in blended failure-penalised Brier over alpha and destination states. This is a numerical stability diagnostic, not a certified bound on the infinite-product error. Any unresolved numerical rows must be reported and cannot support an unqualified superiority claim. Source observations and independent-ID counts never increase when integration contributions multiply.

**Weight selection:** each local variant/horizon has its own global-across-cells alpha. Retain both the 0.1 grid and clipped analytic optimum on identical inner OOF cases. Ties use the smaller grid value; non-unique analytic optima use zero. Preserve outer fixed-alpha curves as declared diagnostics only, not a new selection set. Final candidate weights use base OOF terms then bases are refitted to all development IDs; final tuning scores are not independent evaluation scores.

### Implementation tasks and review focus

- [x] Task N1 — `neighbourhood.py`, `tests/test_modelling_neighbourhood.py`: failing tests first for eight-cell indexing, WGS84 round trips, equal-pair U, exact empirical-anchor A, land/outside/unresolved mass, balanced marginal preservation and mixture-score convergence envelopes. Implement only after the RED run; check GREEN and old modelling regressions.
- [x] Task N2 — `neighbourhood_cv.py`, `tests/test_modelling_neighbourhood_cv.py`: fit-only donors and anchors; nested selection and all-case scoring; unsupported rows and alpha endpoints; independent direct scoring fixtures; per-cell/ID and probability-region diagnostics. Reuse old Brier and folds without modifying them.
- [x] Task N3 — `run_neighbourhood.py`, orchestration tests: manifest/contract/parent-output identity, source-key join and exact parent counts, guarded read-only inputs, resumable numerical preparation only within a new run, scientific code hashes, no visualisation or test access. Run training-only numerical/resource checks, then the complete pooled comparison.
- [x] Task N4 — `neighbourhood_report.py`, independent saved-artifact audit: reproduce counts, alpha selections and representative distributions/scores; verify all sealed inputs and outputs; paired whole-ID intervals conditional on saved OOF fits; one English `REPORT.md` explaining results, limitations and next steps. Complete a fresh-context whole-change review and fixes before the final claim.

Review focus: target anchors are not cell centres or heldout positions; donor endpoint coordinates remain available even for OUTSIDE; synthetic land cannot become grounding or disappear; unsupported rows keep mass; hourly observations and integration contributions do not become independent IDs; selection and numerical convergence never use outer truths; fixed-alpha diagnostics are not final tuning; no canonical or final-test access.

### Execution ledger

- Pre-flight: original 29 modelling tests passed on 2026-10-24; baseline main was `4f35bf7`. Unrelated untracked `results/deliverables/poster/` is preserved.
- Ruling: use local branch `codex/baseline-neighbour` in the existing research checkout. Native worktree creation failed because the app's parent folder is not the nested Git repository. A separate data/environment checkout would duplicate or break the registered research assets. New modules and immutable run directories isolate this change; main's committed history, data, old results and unrelated files are unchanged. No commit/push is authorised.
- Interfaces: N1 emits `(physical_probabilities, unresolved, numerical_audit)` consumed by N2; N2 emits source-multiplicity score groups and selected weights consumed by N3/N4. N3 verifies parent ledgers and canonical positions before N1/N2; no global fit is reused across folds.
- N1/N2: RED import failures observed before implementation; 16 scientific/CV fixtures then passed. Debugged an accumulation overshoot at probability 1, a tuple-initialisation typo, and representation-only zero entries at mixture endpoints. Numerical overshoot is bounded by the existing 1e-10 mass tolerance; no physical mass is removed or renormalised.
- N3 preparation complete: `neighbour_input_20261024T062737_251970Z`; 396 development R-visitor canonical IDs read, before/after hashes verified, exact parent pair counts reconciled; no final-test track read. Source-key joining has four additional passing tests. The final model run reuses these sealed coordinates.
- Numerical engineering rule: exact Cartesian products up to 2,000,000 contributions; otherwise coupling levels 8,32,128,512, with a 0.0005 maximum blended-score change between successive approximations (across all outcomes/alpha). Every marginal retains every original record. This threshold is a declared computational stability diagnostic, not statistical accuracy or a certified integral error bound. Unsettled rows are reported rather than hidden.
- Resource pilot: the largest outer-training product involved about 874 million donor/anchor combinations. A balanced approximation preserved both empirical marginals and passed the declared stability check. Use four bounded numeric threads across independent cell rows, with separate WGS84 handles **and separate GEOS geometry/index objects** per worker; sorted collection and unchanged seeds preserve deterministic results. Cache each row's integer coupling partition only. Serial/parallel equality is covered by a scientific fixture. This changes computation scheduling, not the fitted population, weighting, model or precision rule. Shapely documents GIL-releasing numeric operations: https://shapely.readthedocs.io/en/stable/index.html#multithreading
- Independent review identified two Minor audit gaps, corrected before fitting: independently reconstruct every reported local score/region/log diagnostic and raw-pair representative bases, reread saved score/weight artifacts, and record NumPy/pandas/PyArrow/Shapely/GEOS/pyproj/PROJ versions. Deliberately corrupted diagnostic fixtures first failed, then passed with the repair. All 56 modelling tests and 10 synthetic architecture tests pass; no canonical test tracks were read.
- Native-index debugging: initial full-run attempts `baseline_neighbour_cv_20261024T064709_050140Z` and `baseline_neighbour_cv_20261024T064758_936798Z` crashed before producing fits/scores. Faulthandler and macOS native frames pinpointed concurrent lazy construction of the shared GEOS prepared-land index. Preserve both incomplete attempts; they are not scientific results. Worker-owned geometries loaded from immutable WKB replace shared prepared geometry, with unchanged classification rules. Verify against the actual high-resolution map before restarting.
- Runtime acceleration: attempt `baseline_neighbour_cv_20261024T064946_746071Z` was deliberately stopped for excessive repeated native land queries, without producing a scored comparison. An exact closed-cell spatial index now proves a cell wholly water, wholly land or mixed; only mixed cells require the unchanged point predicate. This does not approximate coastlines or alter destination labels. Independent direct predicates matched all 12 million concurrent real-map checks; boundary fixtures use the frozen longitude normalisation convention. The indexed predicate took 0.17 s versus 2.50 s for the independent direct million-point check in this environment. All 58 modelling tests pass after the change.
- Independent boundary review caught a non-random edge missed by that stress: `floor(lat+90)` can round a nextafter-below-integer latitude into the next scientific cell. Attempt `baseline_neighbour_cv_20261024T065630_949699Z` was stopped before acceptance. The exact geometry lookup now uses `floor(lat)+90` and `floor(normalised_lon)+180`, while scientific destination labels remain the original `cells()` convention. A failing nextafter land-boundary reproducer now passes, along with all 59 modelling tests. This separates a computational index from frozen model state labels; it does not redefine the scientific grid.
- Accepted computational run: `baseline_neighbour_cv_20261024T065917_879042Z` completed and sealed (1,970 s; peak process RSS 1.70 GB). All 59 modelling and 10 architecture tests pass after fitting. Current-code map checks additionally matched 12,015,012 independent direct classifications, including sampled actual coastline vertices. Source/input/output checksums were verified; no canonical trajectories were reopened during fitting and no final-test trajectory was read.
- Independent saved-artifact arithmetic reproduced 206,775 score groups, 72 weight choices, 2,444 unaligned bases and two representative final aligned bases. All nine forecasts have the same 22,975 source-multiplicity groups; the five parent controls reproduce per case. See the sealed run's `REPORT.md`, `verification.json` and source tables.
- Evidence interpretation: 30-day neighbour sharing improves the declared comparison score against both B2 and global sharing, with conditional paired-ID intervals below zero. Seven-day differences remain uncertain. Aligned-versus-unaligned intervals cross zero at both horizons; the small point-score advantage does not establish an aligned winner. All 37 cells are evaluated; both local variants improve on B2 in 36 of 37 cells at 30 days, but not on every ID.
- Numerical/physical limits remain explicit: 34 fit rows fail the successive-integration stability criterion (including inner selection fits); final all-development rows pass that criterion, which is still not a certified exact-integral error bound. Aligned forecasts retain mean unresolved mass about 0.15%/0.19% at 7/30 days, with larger local maxima. This is synthetic endpoint uncertainty, not missing raw temperature/drogue data or a grounding label. There are no observed OUTSIDE endpoint truths in this 7/30-day evaluation, so exit calibration is not established. The locked test, seasonal/annual claims and fixed-regime extensions remain outside this completed comparison.
- Final independent review passed with those declared scientific caveats: 146 output/input/source hashes and the 74-file sealed inventory verified; all scores, 72 weights, 20 paired intervals and raw-count bases reproduced. Both actual final aligned representatives were replayed independently with direct point predicates and separate integer-partition walking, with zero probability discrepancy. No Critical or Important review finding remains.
- Handoff wording clarification: in the sealed report, “No validation ID supplies fitted donors or anchors” means **each fold's held-out IDs do not enter that fold's fitting or selection**. Historical validation IDs belong to the development pool and intentionally train other folds; the final candidate uses all 3,224 development IDs. This clarification leaves sealed evidence unchanged. The final test is a separate locked population.

> Current execution authority (2026-10-23): the user explicitly authorised the assistant to complete the agreed B2/B1 blend code, tests, nested cross-validation, candidate refitting and visual comparison. This supersedes the earlier manual-entry workflow described in the historical baseline notes below. Canonical data, all 62 stored fields, old model runs and the locked final test remain unchanged. No Git commit or push is included. Further predictor/feature changes still require the user's review.

**Goal:** Produce genuine 7/30-day release-cell probability forecasts, evaluate them on unseen development drifter IDs, and compare annual, seasonal and shrinkage Markov operators before extending the analysis to one year.

**Architecture:** Reuse the manifest-backed trajectory reader and existing independent endpoint/stopped label generator. Stream trajectories into derived samples and per-ID transition counts; fit models from training-fold counts, forecast from declared release conditions, and evaluate out-of-fold predictions on common cases. Keep one human-readable report per run.

**Tech stack:** Existing Python 3.12 environment and pinned NumPy, pandas, PyArrow, SciPy, Matplotlib, Shapely and pyproj. No neural-network dependency is needed for this round.

**Spec:** `docs/contract/data_contract_v1.0.xlsx`, especially aspects 02–12, 15–20 and 24–31; the model list agreed in the architecture conversation; `docs/architecture.md`.

## Material Passport

- Origin: architecture conversation; academic-research-suite experiment planning and writing-plans.
- Date: 2026-10-18, Australia/Sydney.
- Current checkpoint updated: 2026-10-23, Australia/Sydney.
- Status: historical pooled B0/B1/B2 fitting and validation are complete. The current authorised implementation compares global B2/B1 mixing weights using whole-ID nested development cross-validation, with final candidate weights selected on all-development base out-of-fold predictions. See the current run report for actual results and independent verification; do not infer accuracy from setup tests.
- Authority: the final Excel contract remains authoritative. This document does not amend it.
- Contract SHA-256: `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`.

## Current experiment: pooled B2/B1 shrinkage

Keep the frozen pooled, endpoint, R-origin, aligned 1-degree, exact 7/30-day and equal-eligible-hourly-pair definitions. The sole model change is `p_lambda = (1-lambda) * B2 + lambda * B1`, with unresolved mass mixed by the same weights. B0, B1 and raw B2 remain controls. A missing B2 row is unresolved; there is no automatic fallback or fabricated self-transition.

Use all 3,224 development IDs for the frozen outer five-fold assignment, not only R visitors. For each outer fold, use four inner whole-ID folds to select two weights per horizon on identical inner out-of-fold cases: grid search over 0, 0.1, ..., 1 and the clipped quadratic Brier minimiser. Refit B1/B2 on the complete outer-training pool and score all five forecasts on the same outer-held-out cases. Pool scores by original pair counts, not by unweighted fold means. The scientific score is ordinary unhalved multiclass Brier for complete forecasts; preserve and explicitly label the existing failure penalty when support is unresolved. Raw zero-probability log losses remain infinite.

The final Grid and Analytic weights are selected separately per horizon using all-development base out-of-fold quadratic terms. Then refit the two bases on all eligible development counts. This final tuning loss is not an independent performance estimate for the selected weight. The nested outer score assesses the corresponding tuning procedure; final-test trajectories remain locked. Retain both candidate families rather than selecting a favourable fold or rounding the analytic result into the grid result.

Report the probability-region hit rate together with its mean geographic cell count and availability. Rank OUTSIDE with other physical outcomes, retain all cutoff ties and never renormalise unresolved mass. Report paired whole-ID uncertainty using 200 resamples within fixed outer folds; these intervals are conditional on the saved OOF predictions and do not include refitting/selection uncertainty. Every interactive map compares a single outer-fit forecast with endpoints from that same outer heldout pool, never with the training outcomes of a full-development refit.

Implementation is in `experiment.py` (folds), `blend.py` (mixing and exact Brier polynomial), `cv.py` (nested fitting/scoring), `run_blend_cv.py` (read-only-input orchestration and provenance), and `report.py` (saved-artifact reports/maps). Existing data and label modules retain authority over qualification and pairing. Fresh paired counts must exactly reproduce both old historical training and validation counts before comparing models. Scientific changes receive a new immutable run; the current comparison report is the human-facing entry point.

Current completed comparison: [run report](../results/runs/baseline_blend_cv_20261022T160806_056571Z/REPORT.md), [matched interactive probability maps](../results/runs/baseline_blend_cv_20261022T160806_056571Z/comparison.html). Reproduce with `.venv/bin/python -B -m data3001.modelling.run_blend_cv`; it creates a fresh immutable run. The final candidate bases and both sets of selected horizon-specific weights are saved in that run. The interactive weights are deliberately the corresponding outer-fold weights, not the all-development final candidate weights.

The [offline class presentation](../results/deliverables/baseline_optimized/index.html) is a reusable rendering of that sealed evidence. [The presentation guide](baseline_presentation.md) gives the class walkthrough and export command. `showcase.py` verifies a completed run's hashes and refreshes the fixed presentation entry without retraining or modifying scientific inputs.

## Historical checkpoint: minimal pooled baseline workspace

The user has selected a pooled first baseline to obtain an interpretable reference promptly. The immediate scope is B0, B1 and B2 at 7 and 30 days on the existing 1-degree grid. Annual propagation, seasonal conditioning, finer grids, grounding prediction and environmental extensions are later checkpoints, not prerequisites for the first maps.

Data preparation is accepted as completed for this stage. Treat the current v7 release as the fixed modelling input; do not reopen a general cleaning or imputation programme. Proceed to baseline implementation, reviewed model-input construction and whole-ID validation. Mapping approved origin/endpoint records into model samples is modelling work and reuses the existing qualification rules. The first entry script is entered and run by the user; its initial block establishes the environment and dataset identity before model code is added to the same file.

The initial model uses origin cell only as its spatial predictor. Departure time is needed to construct samples and match outcomes; it does not condition the first baseline probabilities. The 7-day and 30-day distributions are estimated separately. Pooled means no drogue-state conditioning or fixed-regime exclusion; otherwise qualified unknown and switching histories remain eligible. It does not mean mixing development and final-test IDs or pooling different horizons.

### Minimal workspace

Reuse the existing repository and verified dataset in place. Do not create a second train/test copy, a second environment, a second planning guide or placeholder models/results. The approved workspace preparation may create the empty `src/data3001/modelling/` directory; it must not create or edit formal experiment code or configuration on the user's behalf.

| Location | Current role / creation boundary |
|---|---|
| `docs/modelling_round1_plan.md` | Single current modelling guide; this document. |
| `configs/modelling_round1.json` | Proposed single experiment configuration; the user creates it after reviewing the configuration and validation details. Not created by workspace preparation. |
| `src/data3001/modelling/` | User-entered baseline fitting and validation code; later modelling modules are added only after review. |
| `src/data3001/modelling/__init__.py` | User-created package marker when the first module is written. |
| `src/data3001/modelling/run_round1.py` | Proposed single execution entry; implement the baseline stage first. Existing label logic is reused, not copied into a competing workflow. |
| `data/train/` | Existing complete development trajectories; read through `data3001.dataset`. |
| `data/test/` | Existing final-test trajectories; remain locked in development. |
| `results/runs/<run_id>/` | Derived samples/counts, fitted baselines, predictions, scores, figures and one report; generated only by an authorised user-run experiment. |
| `provenance/runs/<run_id>/` | Matching configuration, input/code identities and execution records. |

Do not create all proposed helper modules below in advance. Add each only when its code has been discussed and the user is ready to implement it. No notebook dependency or additional notebook workflow is required for this minimal layout.

### Baseline field roles

This is a model-input selection, not another physical feature-pruning migration. All 62 canonical fields remain unchanged. The existing qualification helpers may read the metadata and audit evidence they require; their input requirements must not be reduced to the predictor list.

The user has explicitly prohibited data deletion during modelling. Treat the current train/test files as read-only inputs: do not delete files, overwrite trajectories, prune stored columns or mutate the loaded complete trajectory in place. Select the required fields and qualified samples into a separate derived modelling view. Qualification may exclude a sample from a particular fit, but its source record and exclusion reason remain traceable. Do not apply a blanket missing-value row deletion across unused columns; a missing SST or hardware value alone does not disqualify a position-based baseline pair. Write only new derived run outputs under the existing results/provenance boundaries.

| Role | Existing fields | First-baseline use |
|---|---|---|
| Spatial predictor | Origin `cell_1`, exposed by the existing pair ledger as `origin_cell_1` | B2 conditions on this category. B0 places unit mass there; B1 pools origin cells. Cell IDs are categories, not a numeric distance variable. |
| Spatial construction | Origin/endpoint `lat`, `lon`, `lon_normalized`, `cell_1`; frozen R and D | Establish exact origin membership and mapped destination; raw coordinates are not extra continuous predictors in this 1-degree baseline. |
| Temporal construction | `time`, `time_UTC`; `horizon_days` = 7 or 30 | Match each origin to the required future timestamp using the existing endpoint rules. Fit separate horizon-specific distributions. |
| Grouping and traceability | `id`, `source_obs`; ledger `origin_source_obs`, `endpoint_source_obs` | Whole-ID validation and source-keyed sample audit; never physical predictors. |
| Scenario evidence | `drogue_status`, `drogue_lost_date` and existing official correction evidence | Preserve interpretation and composition audits. Neither field conditions the initial pooled forecast; no drogue-based exclusion is added to this scenario. |
| Training truth | Existing ledger `destination_cell_1`, `outside`, `target`, `reason_code` and time-match evidence | Count only eligible endpoint outcomes. Keep eligible outside-D endpoints. Matched future position/time are labels, not forecast inputs. |
| Retained for later comparisons | `sst`, `ve`, `vn`, `season`, hardware fields and error values | No conditioning, inverse-error weighting or new transformations in this baseline. Future wind/wave/current products are not current predictors. |

For the scientific endpoint target, an eligible observed outside-D endpoint is `OUTSIDE`. A missing/unqualified endpoint is an exclusion with an explicit reason, not an observed destination. An unsupported model origin row is `UNRESOLVED_SUPPORT`, not physical exit. No missing path/endpoint is interpolated to create baseline truth.

### Current baseline scope

The first configuration will declare: dataset `per-drifter-cleaned-20261017-v7`; frozen R origins and D mapping; `scenario=pooled`; `target=endpoint`; 1-degree grid; horizons `[7, 30]`; exact endpoint matching (`tolerance_hours=0`); models `[B0, B1, B2]`; B2 predictor `[origin_cell_1]`; equal weight per eligible hourly pair; whole-ID development validation; final-test access disabled.

The user has approved the existing historical whole-ID train/validation assignment for the first baseline: 2,674 historical training IDs and 550 historical validation IDs, both physically in `data/train/`. Select membership from the manifest's `historical_split`; directory membership alone does not identify the fitting set. The 517 final-test IDs remain locked. Fit counts and any fitted preprocessing on historical training IDs only; use historical validation IDs for initial scoring. A later whole-ID cross-validation experiment remains a separate reviewed extension. No new split, nonzero smoothing, feature expansion or illustrative release cell is approved by this checkpoint. Report independent-ID support separately from pair counts.

The user has run the entry script successfully and reported the expected project Python, root, v7 release, 62 stored columns, 3,224 development IDs and disabled final-test access. The user subsequently reported that the pooled R-origin endpoint preview for historical training ID 22165 ran normally after local transcription fixes. Exact preview totals have not been independently inspected in this conversation. These checkpoints establish startup and sample construction, not predictive performance. ID 22165 is a source-keyed demonstration, not a selected release cell or a model trained on one ID.

The user completed pooled B1/B2 fitting in `baseline_pooled_20261018T150758_752931Z`: 242,327 eligible 7-day pairs from 315 independent training IDs and 226,632 eligible 30-day pairs from 292 IDs. The saved probability tables, per-ID counts, support and qualification tables are under that results run; its matching provenance receipt records the v7 input, endpoint target, equal-pair weighting and no validation/test contribution. These are fitted empirical distributions; the first held-out validation is recorded below. B0 requires no fitted parameters.

The checksum-bound dataset index identifies 323 historical training IDs that visit R; reading their complete retained trajectories is a prescreen for the R-origin direct baselines. It does not crop trajectories to R, alter membership or exclude D-only training IDs from the later D-origin Markov experiment. No smoothing or environmental predictor was introduced. Subsequent validation reads the saved tables instead of fitting them again. Keep the fitting entry intact and put reusable scoring functions in the proposed `evaluate.py` module, entered by the user.

Before held-out scoring, check the scoring function on known distributions. For complete physical distributions, use natural-log loss and the unhalved multiclass Brier score. Preserve zero-probability outcomes as infinite raw log loss. For unresolved mass u, retain log-loss bounds and report coverage. The proposed explicit algorithmic failure penalty treats unresolved support as an additional, always-unobserved outcome: Brier_failure = 1 - 2*p_true + sum(p_known**2) + u**2. This is labelled an algorithmic failure-penalized score; it is not presented as the ordinary physical-outcome Brier score for an incomplete distribution or as a bound. Completely unresolved output has loss bounds [0, infinity] and penalty 2. Do not silently replace unsupported B2 rows with B1 or discard their validation cases. This precise penalty implementation is presented for human review before any held-out results are examined.

Completed validation: the user ran `evaluate.py` in `baseline_validation_20261019T052149_527052Z`, reading the frozen parent tables without refitting and leaving final-test access disabled. The source-keyed endpoint ledger retains ineligible reasons. Identical `(id, horizon, origin cell, destination cell)` cases are grouped only to avoid repeated scoring; their multiplicities restore equal-pair weighting. Read-only reconciliation confirmed all four output hashes, identical source-group cases and multiplicities across B0/B1/B2, exact agreement with the eligible ledger, and the reported weighted scores. Grouping does not create independent samples or change the target population.

| Horizon | Eligible pairs | Independent validation IDs | B0 Brier | B1 Brier | B2 Brier | B2 zero-probability pairs |
|---|---:|---:|---:|---:|---:|---:|
| 7 days | 65,985 | 72 | 1.685989 | 0.978698 | 0.924300 | 1,262 (1.9126%) |
| 30 days | 60,372 | 66 | 1.915954 | 0.991089 | 0.995367 | 8,612 (14.2649%) |

All three models have complete forecast rows on these eligible cases: coverage 1, unresolved pairs 0. Every model nevertheless has at least one zero-probability observed outcome, so all raw mean log losses are infinite. Ordinary and failure-penalized Brier coincide here because unresolved mass is zero. B2's pair-weighted Brier is 5.5583% lower than B1 at 7 days and 0.4317% higher at 30 days. These are descriptive development comparisons, not percentage accuracy or a significance claim. The largest ID supplies 11.6633%/12.9033% of eligible 7/30-day pairs; whole-ID uncertainty analysis remains pending. There are no eligible outside-D endpoints in this validation batch, so it does not establish outside-state calibration. Annual, seasonal, grounding and object-specific performance remain unvalidated.

Read-only visual review: the conversation demonstration now displays saved 7/30-day B0/B1/B2 distributions alongside empirical validation endpoints for any of the 37 supported release cells. It does not retrain, modify formal experiment artifacts, read final-test trajectories, interpolate unsupported horizons or display synthetic trajectories. The proposed training-only default rule (maximize the minimum independent-ID support across the two horizons, tie by ascending cell ID) selects cell 44744, spanning 34–35 N and 76–75 W. Its training support is 5,819 pairs/204 IDs at 7 days and 5,560 pairs/196 IDs at 30 days. This is an illustrative default rather than a frozen scientific release location, and was not selected by validation performance. Both maps use the same per-cell probability scale; outside/unresolved quantities remain separate. Coastline simplification is display-only and never alters frozen R, D, masks, eligibility or training states.

Presentation diagnostic definitions: the most-likely destination is selected using training probability, with ties broken by ascending global cell ID. A target-mass region ranks frozen training probabilities and includes destinations until at least 50%, 80% or 90% mass is reached; include all destinations tied at the cutoff. OUTSIDE participates as a destination state when relevant but is reported separately from geographic cells. Validation outcomes are used only to measure hits, never to choose these regions. Pool hits with the original equal-hourly-pair weights, and distinguish selected-origin statistics from all-R summaries. These diagnostics are derived from the saved models and saved validation groups; no new model run or interval estimate is implied. Repository plotting/evaluation code implementing these reviewed definitions remains user-controlled.

| Horizon | Model | Most-likely-cell hit | At-least-90% region validation hit | Mean model mass in region | Mean geographic cells in region |
|---|---|---:|---:|---:|---:|
| 7 days | B1 | 2.3505% | 92.7984% | 90.1798% | 50.0 |
| 7 days | B2 | 15.3596% | 88.8778% | 90.7028% | 18.6 |
| 30 days | B1 | 1.3500% | 90.4376% | 90.0967% | 144.0 |
| 30 days | B2 | 2.7148% | 67.4071% | 90.5188% | 66.0 |

The region's assigned mass is not exactly 90% because cells are discrete and cutoff ties are retained. These are empirical, pair-weighted development diagnostics over 72/66 independent IDs, without uncertainty intervals. A smaller set is not automatically better: B2's 30-day regions substantially under-cover the held-out endpoints. Do not treat nonzero-support coverage, most-likely-cell hits, region coverage and Brier skill as interchangeable accuracy measures.

## What success means

The first checkpoint is a fitted direct endpoint model, two 7/30-day maps and held-out development scores. A histogram of starting positions or all observed tracks is not this deliverable. Success at this checkpoint establishes a working prediction-and-validation pipeline, not good accuracy or a validated annual model.

The full round compares B0–B2 and M1–M3, reports short- and long-horizon evidence, and identifies the next justified improvement. A negative result or insufficient support is an admissible finding. No numerical accuracy threshold is invented before evidence exists.

## Global constraints

- Current input: `per-drifter-cleaned-20261017-v7`, 3,741 IDs, 39,099,193 hourly records and 62 columns. The 3,224 development IDs live in `data/train`; 517 locked final-test IDs live in `data/test`.
- Do not overwrite trajectories, add canonical feature columns, redo imputation, remove more features or alter official labels. Derived sample fields and model state indices belong only in new run outputs.
- Read through `data3001.dataset` and the existing qualification evidence. Keep all existing endpoint/stopped eligibility predicates, source keys, exact timestamp matching and drogue interval meanings.
- R is the frozen southern corridor polygon. D is the frozen 20–55 N, 81–8 W rectangle. Resolve both through the asset catalogue; do not substitute a bounding box for R or change D silently.
- First grid: existing aligned 1-degree cells. All eligible hourly origin–destination pairs have equal weight in main estimation. Retain self-transitions. Alternative thinning and weighting are separately labelled sensitivities.
- Use R origins for release demonstrations and primary release evaluation. Use all qualifying training-ID origins in D for downstream short-lag operator estimation; do not limit those kernels to R visitors.
- Keep pooled, fixed-drogued and fixed-undrogued scenarios separate. Unknown/switching intervals remain available to the pooled historical-mixture baseline under existing eligibility rules. Do not impute a future hardware state.
- Start the first engineering demonstration with the explicitly labelled pooled historical-mixture baseline. Fixed-regime comparisons follow as separately labelled experiments. DEPTH-01 must be resolved and recorded before claiming a homogeneous near-15-m primary scenario; drogue status alone does not establish depth.
- First-baseline probabilities condition on release cell only, separately for each horizon. Departure date is retained for matching and audit; seasonal conditioning comes later. Scenario is a declared experiment setting. `end_date`, `end_lat`, `end_lon`, eventual `typedeath` and future observed SST/velocity are not origin-time predictors. SST/velocity/wind conditioning requires a later reviewed comparison.
- No final-test outcomes, models or scores are opened for this development round. Do not change the existing development/test membership.
- Primary anchors: 7, 30 and 365 days; intermediate anchors: 90 and 180 where evaluable. Do not restrict short-lag learning to drifters with 365-day follow-up.
- Outputs use new `results/runs/<run_id>/` and `provenance/runs/<run_id>/` directories through existing no-overwrite run helpers. No Git operation is included.

## Target and boundary decisions

The scientific destination question is endpoint occupancy at a specified day. B0–B2 must support this target and preserve observed outside-D endpoints as outside outcomes.

The first finite-D Markov propagation is a **stopped-domain prototype**: first observed exit is absorbing. Its evaluation uses the separate stopped ledger and stopped versions of the baselines. It must not be scored as endpoint occupancy or presented as the complete endpoint product. Exit followed by return is the distinguishing test case.

If boundary behaviour materially limits the endpoint goal, compare development-only domain/boundary alternatives under versioned change control. Do not invent return probabilities from one undifferentiated outside state. Until that extension is validated, publish endpoint baseline forecasts and stopped Markov forecasts under different target labels; do not rank their scores against each other.

Grounding is a required eventual capability, not a solved label problem. The current first-round transport product has no validated grounding predictor. Audit official grounding evidence, event locations and time intervals in parallel. Eventual `typedeath=1` and last-good `end_date` are not exact per-hour grounding labels; stopped transmission and recovery are not grounding. Unresolved event timing stays unresolved. A grounding-state experiment needs a separate event-label protocol before fitting.

## Review focus

1. A trajectory exits and returns: endpoint and stopped results must differ correctly.
2. A row, destination or cell-season is unseen in training: retain outside/unresolved mass, raw zero-probability failures and evaluation coverage.
3. One ID contributes overlapping hourly windows: exclude it wholly from training when validating it; bootstrap IDs, not rows.
4. A forecast crosses seasons or needs a remainder step: advance the actual UTC date and preserve exact duration.
5. Data termination, drogue switching and grounding uncertainty: maintain their distinct qualifications; no fabricated fixed-horizon endpoint.

## Model and experiment specification

| ID | Model | Estimation / purpose |
|---|---|---|
| B0 | Persistence | Unit mass in the origin cell; no fitting. Preserve its legitimate infinite raw log losses. |
| B1 | Destination climatology | Training R-origin destination frequencies at the same target/horizon/scenario, pooling origin cells; tests the value of origin information. |
| B2 | Direct endpoint/target distribution | Training origin-cell conditional destination frequencies at each anchor. Endpoint and stopped variants are independent fits. |
| M1 | Annual Markov | Equal-pair short-lag row frequencies, pooling departure seasons. |
| M2 | Seasonal Markov | Independent DJF/MAM/JJA/SON short-lag rows, propagated with the calendar. |
| M3 | Shrinkage seasonal Markov | `(1-lambda) * seasonal + lambda * annual`, using the same regime and lag. M2 and M1 are lambda=0 and lambda=1. |

Candidate lags are 1, 3, 5 and 7 days. Lambda candidates are 0, 0.25, 0.5, 0.75 and 1, shared across seasons/cells for each regime/lag. Compare the declared destination-prior mixing epsilon values 0, 0.0001, 0.001 and 0.01; build priors from training data only, inspect wet connectivity and keep added prior mass identifiable. Missing seasonal rows may use an available annual same-regime row; otherwise send mass to unresolved support. Do not invent self-loops or universal pseudocounts.

Implemented and retained from the completed baseline: five development-only ID folds, with deterministic assignment `int.from_bytes(sha256(f"20261004:round1-cv:{id}".encode()).digest()[:8], "big") % 5`. The user approved this map for the baseline; the saved nested assignments and disjointness checks remain frozen. Reuse them for controlled comparisons unless a separately reviewed protocol changes them. A modelling fold map is not a replacement for the historical split manifest. Early stopping/selection on a validation ID never permits using that ID in a fitted count, prior or smoothing estimate.

Report per-horizon development leaderboards, paired score differences and uncertainty rather than announcing a universally best model. The first 7/30-day shortlist is preliminary. A final cross-horizon model-selection rule and the chosen primary depth scenario must be frozen before final-test access; this plan does not authorise selecting that rule after inspecting final-test outcomes.

## Planned files and interfaces

The table below is the original round-1 interface proposal, not the current implementation inventory. The README lists the modules actually implemented. The user subsequently authorised direct code implementation and execution; feature/target choices remain subject to review. Keep current data/label rules unchanged unless an explicitly reviewed repair requires a change.

| File | Responsibility / public interface |
|---|---|
| `configs/modelling_round1.json` | Run settings, target/scenario/model grid and input identities; no new scientific authority. |
| `src/data3001/modelling/experiment.py` | `make_folds(ids: list[int]) -> dict[int, int]`; validate development-only experiment settings. |
| `src/data3001/modelling/pairs.py` | `iter_pairs(ids: list[int], *, population: str, days: int, scenario: str, target: str)` yields existing label frames per ID. |
| `src/data3001/modelling/counts.py` | `count_pairs(frames) -> pandas.DataFrame`, keyed by ID, population, target, scenario, horizon, season, origin and destination. |
| `src/data3001/modelling/models.py` | `fit_model(counts, *, train_ids, settings) -> dict`; fitted object contains metadata, state index and probability rows. |
| `src/data3001/modelling/forecast.py` | `forecast(model: dict, *, origin_cell: int, origin_time_utc: str, horizon_days: int) -> dict[str, float]`. |
| `src/data3001/modelling/evaluate.py` | `evaluate(rows: pandas.DataFrame) -> pandas.DataFrame`; rows contain ID, case keys, target, truth and a probability mapping. |
| `src/data3001/modelling/report.py` | `write_report(*, run_paths: dict, summaries: dict, maps: dict) -> None`; one English report with linked figures/tables. |
| `src/data3001/modelling/run_round1.py` | Stage orchestration; no automatic final-test switch or publication. |
| `tests/test_modelling_*.py` | Small independent semantic fixtures plus narrowly scoped existing-data regression checks. |

Create `modelling/__init__.py` with the first modelling module. A forecast probability mapping uses `cell:<global_cell_id>`, `OUTSIDE` and `UNRESOLVED_SUPPORT`. Label sentinel `-1` is not a physical destination; `reason_code != 0` is not a destination count. Preserve eligible outside label `-2` as `OUTSIDE`.

## Task 1 — Freeze a runnable experiment and demonstrate sample construction

**Files:** create `experiment.py`, `pairs.py`, configuration and `tests/test_modelling_experiment.py`, `tests/test_modelling_pairs.py`.

**Consumes:** current manifests; `PreparedSource`; existing `load_track`, `origin_indices`, `generate`; existing run/path helpers.

**Produces:** immutable run specification, ID-fold map, sample/reason summaries and a small source-keyed sample table. All outputs are derived run artifacts, never canonical feature columns.

- [ ] Write meaningful semantic tests first: test IDs are refused; all appearances of an ID receive one fold; changing the input ID order does not change assignments; both targets match existing label generation exactly on the same fixtures; exit/re-entry remains different between targets.
- [ ] Verify test discovery fails for the missing new functionality, then implement the thin adapter. Do not rewrite label predicates.
- [ ] Validate catalogue/contract/geometry/manifest identities and existing data integrity. Stream one ID at a time; profile a small development-only batch before cohort-wide processing. Save runtime, peak memory, output bytes and reason counts, without promising an unmeasured laptop budget.
- [ ] Generate R-origin 7/30-day examples and short-lag D-origin examples. Check `target_epoch = origin_epoch + days * 86400`, source-key alignment and exact-time matching. Ineligible cases keep their reasons and are not last-position-filled.
- [ ] Run `.venv/bin/python -m unittest discover -s tests -p 'test_modelling_*.py' -v`; require all implemented semantic assertions to pass.

Acceptance: a human can inspect an origin, matched future position or exclusion reason, scenario and target, and trace it back to the retained observation. No model has yet been claimed.

## Task 2 — Fit the first baselines, score unseen IDs and draw real probability maps

**Files:** create `counts.py`, baseline functions in `models.py`, direct forecast functions in `forecast.py`, basic `evaluate.py`/`report.py`, and corresponding modelling tests.

**Consumes:** Task 1 samples and fold map. **Produces:** B0–B2 models, held-out scores, support tables and 7/30-day maps.

- [ ] Before implementation, add an independent count fixture: eligible A-origin destinations `[A,B,B,B]` imply probabilities A=0.25/B=0.75; an additional ineligible row changes neither count. Holding out an ID removes all its counts and prior contributions. An unseen row produces unresolved mass 1 rather than a self-loop.
- [ ] After the user reviews and selects the validation design, use its initial held-out development IDs for the first end-to-end demonstration. If the five-fold proposal is adopted, use fold 0 and fit on the other four folds only. Choose the illustrated cell from the selected training IDs by maximum `min(unique_7d_IDs, unique_30d_IDs)` for pooled endpoint pairs, breaking ties by ascending global cell ID. Never choose it by validation score or visual appearance. Record this proposed selection rule for review and the annually pooled nature of the first model.
- [ ] Fit B1 and B2 from training R-origin counts; generate forecast probabilities before scoring held-out outcomes. Evaluate all available held-out R-origin cases, not just the illustrated cell. Keep cases with unsupported training rows in failure/coverage reporting.
- [ ] Verify exact score fixtures: prediction `{A:0.25,B:0.75}` with truth B has log loss `-log(0.75)` and unnormalised multiclass Brier score 0.125; B0 predicting A with truth B has raw infinite log loss and Brier score 2. Preserve these outcomes rather than post-hoc clipping.
- [ ] Produce 7/30-day prediction maps from the fitted B2 model, with release-cell geometry, support, target/scenario/horizon, outside/unresolved totals and validation status. A separately labelled held-out endpoint map may be shown alongside it. Starting-position density is not a substitute.
- [ ] Re-run the focused modelling suite. Inspect both figures and the score/support tables before scaling.

Acceptance: **first review checkpoint** — fitted 7/30-day endpoint forecasts, genuine held-out development scores, traceable support and a brief English method/results explanation. A poor score is reported, not hidden.

## Task 3 — Implement and check annual/seasonal Markov propagation

**Files:** extend `models.py`, `forecast.py`, `counts.py`; add `tests/test_modelling_markov.py`.

**Consumes:** per-ID D-origin short-lag stopped counts, state index, scenario, calendar and lag settings. **Produces:** M1–M3 probability operators and exact-duration stopped forecasts; direct stopped B0–B2 provide comparable references.

- [ ] Test the explicit matrix `[[0.2,0.6,0.2],[0.1,0.6,0.3],[0.1,0.2,0.7]]`: A release gives `[0.2,0.6,0.2]` after one step and `[0.12,0.52,0.36]` after two. Test self-transitions, nonnegative unit-sum rows and unresolved rows separately.
- [ ] Test calendar switching with a 2026-02-28 release: a winter A-to-B rule and spring B-to-C rule must place all mass in C after two daily steps. A 365-day, seven-day-lag forecast must apply 52 seven-day steps and one estimated one-day remainder, not stop at day 364.
- [ ] Test shrinkage endpoints: lambda=0 equals the available seasonal row; lambda=1 equals the annual row. Missing seasonal and annual rows yield unresolved support. Preserve a separate source for each fallback/prior contribution.
- [ ] Test boundary semantics: stopped `OUTSIDE` is absorbing; the first prototype refuses to label its propagated forecast as unrestricted endpoint occupancy. Unresolved algorithmic mass is reported separately from observed physical exit.
- [ ] Implement sparse operators and streaming per-ID sufficient counts. Derive each fold's fit and priors only from training IDs; do not create a global fitted matrix and subtract validation scores afterwards.
- [ ] Compare direct 2-lag/3-lag stopped distributions against calendar-aware composition on common eligible origins. Diagnose retained incoming-direction/subcell/residence information before adding state features. Any augmentation is a separately named model experiment, not a silent canonical data change.
- [ ] Run the focused semantic tests and an end-to-end small development batch. Inspect map artefacts, row sums, outside/unresolved mass and differences from direct target references.

Acceptance: independently checked propagation mathematics and explicit target semantics, plus initial real-data forecasts. Passing numerical tests does not establish oceanographic accuracy.

## Task 4 — Run the development comparison and hand over a readable result

**Files:** complete `evaluate.py`, `report.py`, `run_round1.py` and their tests; update only this stage guide with actual usage after implementation.

**Consumes:** verified sample/count caches, all five ID folds and fitted model settings. **Produces:** an auditable development comparison, shortlist, uncertainty summaries and the next-step recommendation.

- [ ] Score only identical target/horizon/scenario/case sets within each comparison. Aggregate every model to the common 1-degree partition. Retain unseen destinations, raw infinite losses, coverage failures and missing/unresolved outputs. For unresolved mass u and observed destination probability p, preserve log-loss bounds `[-log(p+u), -log(p)]` and the contract's labelled failure-penalised Brier treatment.
- [ ] Add a test that endpoint and stopped scores cannot be pooled into one leaderboard. Add tests for all-unresolved outputs, zero probabilities and an unevaluable cell-season rather than forcing a numeric success.
- [ ] Complete B0–B2 and M1–M3 five-fold comparisons, reusing per-ID counts. Report pair-weighted scores together with independent-ID support and dominance. Keep the same cases when comparing tolerances/variants; label newly added cases separately.
- [ ] Evaluate 7/30/365-day anchors and, where supported, 90/180 days. Generate integer-day 1–365 forecasts only where the lag/remainder machinery is supported, labelling generated versus validated output. Complete-pair selection and regime availability can also cause direct/composed differences; do not attribute every difference solely to Markov memory.
- [ ] Check probability-region coverage, concentration, outside calibration and boundary sensitivity. Do not renormalise away outside/unresolved mass. A conditional-on-in-domain contour must be explicitly labelled conditional. A narrow map is not automatically accurate.
- [ ] Apply whole-ID cluster bootstrap to the small shortlist: start with 200 development replicates; preserve the contract's 500-replicate final-summary setting for later. State whether settings are fixed or retuned and whether intervals include fitting uncertainty, held-out sampling uncertainty or both. More replicates do not fix few annual IDs.
- [ ] Write `ROUND1_REPORT.md` as the single human entry point, containing question, inputs/target, formulas, actual fitted settings, validation design, prediction maps, baseline comparisons, independent support, limitations and next action. Include failures and results that do not beat baselines. No unsupported object-specific, grounding or exact-point accuracy claims.
- [ ] Verify the completed modelling suite and relevant existing scientific regressions, check figures, and record all input/code/environment identities. Do not reopen the final test or publish to Git as an implicit last step.

Acceptance: a reader can explain what was fitted, which IDs were unseen, which model/target performed better, how uncertain the comparison is, and what remains unsupported. The 365-day fixed-drogued evidence remains subject to the documented small-ID limitation.

## Output and compute discipline

Use one new run ID per stage/attempt; child runs reference and hash parent caches instead of overwriting them. A future entry point may be `.venv/bin/python -m data3001.modelling.run_round1 --stage baseline --config configs/modelling_round1.json --run-id <new-id>`; **it is not available before implementation**. Supported stage names will be `baseline`, `markov`, and `compare`; baseline may create its required sample cache internally.

Keep canonical tracks unchanged. Put samples, per-ID counts, models, metrics and figures in the run's results directory, and receipts/progress in its provenance directory. Cache D short-lag sufficient counts; retain source-keyed R evaluation labels and small diagnostic examples. Do not expand D hourly records across every horizon, model and hyperparameter into one enormous table. Memoise repeated forecast queries and save full probability vectors for selected maps/shortlisted results rather than every candidate-hour combination.

Record progress by IDs completed, cases/counts processed, elapsed time, peak resident memory and bytes written. Profile before scaling; adjust chunk size and caching, not scientific eligibility, to fit the laptop. An interrupted stage resumes only after validating cache identities and completion records. Record a failed attempt rather than silently retrying altered settings.

## What follows this round

- Add MDN as the first continuous-space challenger only after common scoring and boundary tests exist. Network size, mixture count and feature availability require their own recorded configuration.
- Resolve the grounding-event protocol before training a grounding-state/risk module. Keep this requirement visible even if first-round transport maps are useful.
- Resolve DEPTH-01 and any necessary endpoint-boundary extension before declaring the final primary model.
- Treat 0.5-degree refinement, SST/velocity conditioning, different weight targets and regional transfer as separately evaluated changes. Do not quietly replace the 1-degree main study.
- Freeze the final selection rule and chosen model before one authorised final-test evaluation. A development shortlist is not a final-test performance claim.

## Human review checkpoints

1. Task 1: agree that one derived sample means exactly the contracted research question.
2. Task 2: inspect the first genuine 7/30-day forecasts and held-out baseline evidence.
3. Task 3: inspect transport assumptions, exact duration, seasons and target/boundary semantics.
4. Task 4: decide what the evidence supports and whether the next change should address data support, memory, boundaries, grounding or continuous space.

Keep the first checkpoint brief enough that work reaches Task 2 promptly. Do not turn this plan into another open-ended preparation phase.
