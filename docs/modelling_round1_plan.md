# Round 1 Probability Transport Modelling — Implementation Plan

**Current stage status:** S1 is completed and frozen; Fixed and Adaptive remain Step 2 research outcomes. The [S3 E1 benchmark](spatial_borrowing_s3_e1_results.md), [E2 adaptive local comparison](local_endpoint_adaptive_s3_e2_results.md), [E3 neighbour-quality comparison](local_endpoint_quality_s3_e3_results.md) and [E4 joint constrained comparison](local_endpoint_joint_s3_e4_results.md) have been independently executed, audited and replayed. E4 does not establish a quality-preserving upgrade: all constrained selections fall back to LocalEndpointAdaptive. The [locked E4 plan](local_endpoint_joint_s3_e4_plan.md) retains raw-pair training, equal-ID/equal-cell standard Brier, fixed 90% regions and whole-ID validation. The `Markov Step 1 - 3done` publication milestone records this bounded sequence; E5 exact-coordinate work is deferred without full-CV results. [Step 4 seasonal planning](time_environment_s4_architecture.md) is now the next review task; its contract remains a draft, not execution authority. Historical definitions below retain their own targets. The [stage ledger](research_stage_ledger.md) records approvals; final-test access remains a separate decision.

## Earlier S1 planning snapshot: B2 empirical transition matrices, 7/30 days (2026-10-29; superseded where amended above)

The user's latest decision narrows Stage 1 to B2 alone. This supersedes the earlier suggestion to require M1/M1vcat propagation, velocity-state support or seasonal/long-horizon diagnostics in the first-stage deliverable. Existing M1, M1vcat and continuous results remain preserved; their implementation or refitting is not needed to complete this stage.

| Decision | Approved Stage 1 scope |
|---|---|
| Data | Final cleaned `per-drifter-cleaned-20261017-v7`; reuse existing qualified inputs and fitting roles |
| Development boundary | Existing development IDs only; final test remains locked |
| Spatial state | One-degree release cell; existing R and D geometry retained |
| Horizons | Exactly 7 and 30 days, estimated independently |
| Scenario | Annual-pooled; no new seasonal or fixed-drogue conditioning |
| Model | B2 direct empirical Markov transition model at each fixed horizon |
| Predictors | Release cell and requested horizon; available initial velocity is unused by B2, not deleted from the dataset |
| Target and weights | Existing stopped first-exit target, E/U treatment and equal eligible-pair weights retained |

For each supported release-cell row, `P_h(i,j) = N_h(i,j) / sum_k N_h(i,k)`, for `h in {7,30}`. Counts use only that fitting role's qualified pairs. Outcomes use the existing D-cell/E mapping; unsupported release rows retain the existing unresolved forecast treatment. B2 can be described as a fixed-horizon empirical Markov transition model, using the current cell as the predictive state. This is a modelling assumption, not an empirical proof that the observed ocean process is Markovian. Stage 1 neither composes the two tables nor requires a daily kernel or consistency with powers of one common matrix.

The term empirical also applies to the count estimates in M1/M1vcat. They are deferred because their iterative propagation or richer state is outside the chosen Stage 1 scope, not because empirical estimation excludes them mathematically. The `baselines/` package name identifies B2's benchmark role and does not assert that B2 is non-Markov.

Stage 1 completion criteria:

1. Reuse the B2 component of existing sealed stopped-target comparisons and the existing whole-ID fitting/evaluation assignments. The B2 records in `markov_vcat_cv_20261026T155955_651594Z` are reusable evidence; reading them does not require running M1vcat. Do not silently substitute the earliest endpoint-occupancy B2 labels.
2. Produce or reconstruct the two B2 empirical tables with explicit source/destination indexes, counts, row totals, fitting IDs and data/qualification provenance. Label outer-fold matrices and an all-development candidate separately; a full-development fit is not independently evaluated by its own data.
3. Check nonnegativity, supported-row sums, zero-support treatment, E/U conventions, qualified first-exit labels and whole-ID exclusion. No recursive propagation, velocity thresholds or exact remainder kernel is required.
4. Report independent-ID support and dominant-ID contribution per release cell and horizon. Link row support and unseen destinations to held-out B2 error; overlapping hourly pairs are not independent instruments.
5. Reuse or reconstruct B2's held-out S, actual issued region mass, coverage/size, E/U and whole-ID uncertainty, with explicit sample counts and maps. Keep zero empirical probabilities visible; absence from a finite count table is not proof of physical impossibility.
6. Deliver a clear English method/result account and a reproducible B2 artifact entry. Record what already exists, what was reconstructed and what has not been run. Completion does not require demonstrating superiority to a model with different information or a different purpose.

Smoothing, neighbour borrowing, M1/M1vcat propagation, extra history/latent states, seasonal modelling, other horizons and grid/region expansion are later decisions. MDN optimisation and the stopped neighbour run remain paused. The existing [code guide](code_guide.md) provides B2-first navigation. Historical continuous-model report links below refer to retained local runs, not result bundles published with the architecture. This scope update changes current planning; historical configurations, reports and receipts remain unchanged.

## Completed previous stage: frozen continuous-model diagnostic audit (2026-10-29)

The user requested diagnosis before the next engineering changes: velocity
learning, completeness-based training attention, and excessive dispersion.
The completed audit uses the frozen one-hour Gaussian/MDN fits and does not
retrain, reweight, clip probabilities, add features, or access final test.

Human entry point: [continuous diagnostic report](../results/deliverables/continuous_diagnostics/REPORT.md).
Evidence runs: `continuous_diagnostics_20261029T054731_635202Z` and
`continuous_diagnostic_report_20261029T055315_213458Z`.

- One-step diagnostics cover all 4,598,829 eligible hourly transitions from 440
  historical-validation IDs. MDN velocity-vector RMSE is slightly better than
  persistence in each reported region/speed stratum. Fast R origins nevertheless
  have excess along-initial-direction velocity damping: predicted -0.03216 versus
  observed -0.01798 m/s per hour; bias -0.01417, whole-ID 95% interval
  [-0.01807,-0.01027], 70 IDs. This is exploratory frozen-model uncertainty.
- Multi-step diagnosis uses 953 seeded, ID-stratified origins from 60 IDs in the
  common complete 7/30-day cohort, inverse-inclusion weights and two 32-particle
  seeds. Real-previous-state controls diagnose local predictions and are NOT
  release-time forecasts. At 72 hours: observed mean speed 0.51274 m/s,
  observed-state control 0.50079, free rollout 0.37545. Rollout speed/position
  summaries condition on surviving predictions and disclose failure mass.
- About 94.90% of training pairs are in uninterrupted eligible segments of at
  least 720 hours. This does not establish raw measurement quality. Equal pairs
  already give long trajectories greater influence. R accounts for 1.208% of
  D-origin training pairs; this is a learning-balance hypothesis, not proof of
  failure or permission to discard D transitions.
- In these sampled traces, every U event is a finite generated hourly location
  rejected by the frozen land mask. No nonfinite/invalid-latitude failure occurred.
  Weighted 30-day MDN U is 9.70% (two seeds 9.47--9.93%). This is not observed
  grounding. Do not hide it by redraw, clipping, or survival renormalization.
- Five focused diagnostic tests passed, including exact reproduction of the
  production particle rollout, exclusive first-failure attribution, correct
  mixture variance, no continuity across gaps, and sampling-weight reconciliation.
  Parent and child output hashes were independently verified.

Next proposals for review: training adequacy and local dynamics first, then
declared longer-lag and/or multi-step-learning comparisons. A longer lag must
retain hourly first-exit semantics; land-aware kernels and quality weights are
separate model/estimand changes. The current equal-pair objective, four predictors,
annual pooling, B2 controls, and final-test boundary remain the reference.
Reproduce diagnostics with `python -B -m data3001.modelling.continuous_diagnostics`;
render a sealed run with `python -B -m data3001.modelling.continuous_diagnostic_report --run <diagnostic-run>`.

## Frozen first continuous experiment

The user authorized implementation and selected **one hour fixed**, with CV
restricted to model parameters. Longer-step exit branches, seasonal predictors,
grounding, new environmental features and 365-day claims are outside this round.
The input variables remain exactly lon, lat, ve, vn. The authoritative contract
and the canonical 62-column development data remain unchanged; final test is locked.

### Frozen first implementation

- State: fixed angular-metre chart x/y and official east/north velocity. The
  invertible chart has centre (-44.5, 37.5), with the WGS84 local velocity Jacobian.
  This is a numerical coordinate system, not a claim that map distances are geodesic.
- One-hour target: joint 4-vector `(x_next - x - 3600 Jv, v_next - v)`.
  Learn a continuous conditional density and generate BOTH the next position and
  next velocity. Subsequent steps never use future observed velocity.
- Control: a conditional full-covariance Gaussian (K=1). Challenger: a conditional
  full-covariance three-component MDN (K=3). Two tanh layers of width 32, fitted
  standardization, covariance `LL^T + 0.03^2 I` in standardized target units.
- Training objective: equal-pair negative log likelihood plus gamma times the
  squared network weights (biases excluded); gamma candidates 0 and 0.0001 in
  BOTH families. Adam lr 0.001, batch 32768, gradient norm cap 10, CPU float32.
  Eight-epoch ceiling, patience two, held NLL improvement threshold 0.001.
  These are bounded first-experiment settings, not proven optimal capacities.
- Three deterministic whole-ID folds within the historical 2,674 training IDs.
  CV held IDs select the epoch by joint NLL and the gamma separately for 7/30d
  by free-rollout S. Thus CV is tuning evidence, not nested unbiased evaluation.
  Refit on all historical training IDs for the median selected CV epoch count.
  The 550 historical validation IDs supply the model comparison; that pool has
  already influenced earlier project design, so it is development evidence.
- Every eligible D hourly pair has equal training weight, including observed
  one-hour exits. Every eligible R release in the relevant ID role is scored.
  No hourly thinning or release subsampling. Cached source indices retain ID,
  time and original row provenance without adding canonical data columns.
- Forecast 7/30d by 168/720 generated hourly steps. First observed hourly domain
  exit is absorbing E. Geometric/nonfinite forecast failure is absorbing U;
  retain its probability and denominator. U is not grounding. No resampling or
  renormalization to hide failed particles. Within-hour exit/reentry is unobserved
  and not claimed to be resolved by this hourly definition.
- Numerical integration: 8 particles/query during CV, 32 during historical
  validation, with frozen seeds. Unbiased collision-count S estimates the same
  limiting categorical score. A zero sample count does not prove zero model
  probability. Coverage and region area describe finite issued ensembles and
  must be labelled accordingly. Monte Carlo and independent-ID uncertainty are
  distinct; inspect close selections before claiming a meaningful winner.
- Runtime pilot and mathematical tests precede formal CV. Record epoch caps,
  early stopping, failures and all candidates; never present a capped search as
  proof that the density family cannot work. Current input snapshot:
  `continuous_input_20261028T143429_995267Z`, 25,208,045 one-hour pairs.
  The earlier resource-pilot cache is superseded: one outside endpoint lacked
  the frozen global mapping qualification. It was removed before formal fitting;
  no canonical source record was modified. 2,001 qualified observed exit pairs
  remain in the final hourly cache.

Sources motivating, not validating, this implementation: Brolly (2023),
https://doi.org/10.1029/2023MS003718 (oceanic displacement MDN; our joint
position/velocity target is an extension); NOAA/Elipot et al. hourly GDP product
(processed historical velocities may use local fitting on both sides of time).
Results therefore concern processed historical-state prediction, not certified
real-time maritime rescue. The project still predicts drifter transport; no
unverified transfer to arbitrary floating object properties is claimed.

### Completed first comparison

Formal model run: `continuous_cv_20261028T143556_027911Z`.
The human entry point is `results/deliverables/continuous_hourly/review.html`
and the accompanying `REPORT.md`. Model checkpoints and all CV candidates are
retained in the formal run. Canonical data and final test were not changed/read.

| Model | 7-day S | 30-day S | Selected L2 gamma (7d / 30d) |
| --- | ---: | ---: | --- |
| Matched stopped B2 | 0.924456 | 0.996241 | Not applicable |
| Conditional Gaussian | 0.978846 | 1.029394 | 0 / 0 |
| Three-component MDN | 0.972575 | 1.028137 | 0.0001 / 0 |

Lower S is better. MDN minus Gaussian whole-ID intervals cross zero at both
horizons; the small point-estimate improvement is not a stable demonstrated gain.
Both continuous models underperform matched B2 in this development comparison.
Ten of twelve CV fits reached the eight-epoch ceiling; this bounded experiment
cannot establish convergence or the best possible performance of either family.
The 7-day MDN gamma ranking changes between independent particle halves, so its
selected value must not be called a resolved optimum. Main map coverage uses
release-cell cohort distributions; individual 32-particle coverage is only a
coarse numerical diagnostic. The final test remains locked.

Next review should inspect the training histories and the failure to reproduce
sustained transport in free rollouts before expanding to seasons or 365 days.
Additional training or architecture changes need a separately specified experiment.

### Retained previous stage record

**Historical decision before the continuous experiment:** the user explicitly chose to stop the current neighbour computation, preserve completed checkpoints, and move to analysis and experiments for a continuous-state model. The training process and completion watcher are stopped. The neighbour experiment has only one completed outer fold and must remain labelled incomplete; no five-fold result, universally optimal parameter or general failure of Markov modelling is established. See the resumed run's `STOPPED_BY_USER.json` for verified retained-checkpoint counts. At that historical checkpoint, continuous-model specification and training were pending; the current completed experiment is documented above.

> Current user instruction: do not use Superpowers. Resume the approved experiment from verified checkpoints without reopening completed planning or review cycles. This is the single current specification/implementation plan; completed sections below are historical evidence. Implementation and execution are authorised. No Git publication is authorised.

**Recovery status, 2026-10-28:** the interrupted run `markov_neighbour_cv_20261028T021012_881592Z` preserved one complete outer fold and 39 complete inner-role checkpoints. All 99 bound source hashes, 16 input/configuration hashes and completed checkpoint hashes were verified before resuming as `markov_neighbour_cv_20261028T105824_991491Z`. Completed outer-fold selection and inner-role evidence were copied unchanged and recorded in `provenance/runs/markov_neighbour_cv_20261028T105824_991491Z/recovered_outer_evidence.json`. The scientific source, parameters and data remain unchanged. Full five-fold results and the saved-artifact audit are pending; a single completed fold is not the final comparison. Runtime progress is recorded in `provenance/runtime/markov_neighbour_resume_20261028.log` and `provenance/runtime/markov_neighbour_completion_status.json`.

**Goal:** compare freshly tuned no-neighbour and eight-neighbour displacement Markov procedures at 7 and 30 days, without new features or historical winning settings.

**Scope ruling:** the user's final sentence selects displacement borrowing only, superseding the earlier request in the same message to compare two hypotheses. Original-endpoint borrowing is excluded. A previous small difference does not prove the displacement hypothesis universally superior.

**Scientific constants:** Data Contract v1.0; dataset per-drifter-cleaned-20261017-v7; annual pooled; exact hourly eligibility and pairing; R-release stopped outcomes; frozen D/grid/water geometry; all eligible origins equally weighted; lon/lat/ve/vn only; the existing nine velocity labels with fitting-role thresholds; final test locked. Preserve canonical data, old runs and all unrelated files. Work on existing codex/markov-m1 checkout with new modules and immutable result runs; do not duplicate the large registered research checkout.

### Model

A live state is exact WGS84 position x and velocity category b. For lag d, L_self samples equal eligible donor pairs from the current cell with matching source velocity; B_self samples all source velocities in that cell. If L_self has no pairs, it equals B_self; a completely unsupported self cell yields U.

L_neighbour and B_neighbour use the union of the eight adjacent source cells, excluding self, within the existing D-origin fitting data. Each eligible pair has equal probability within the appropriate union (not equal weight per cell or ID). Missing neighbour conditional support falls back to the neighbour pooled union; an empty union yields U, without automatic self replacement or renormalisation.

K(d,alpha,lambda)=(1-alpha)*[(1-lambda)*L_self+lambda*B_self]+alpha*[(1-lambda)*L_neighbour+lambda*B_neighbour]. One global alpha/lambda pair is shared across substeps/cells for a candidate. Each horizon selects its own values. A source donor's geodesic displacement is applied at the particle's current actual position, preserving donor endpoint velocity. The original first-observed-hour translated-exit tests, empirical source-E branch, synthetic invalid/land U rule and absorption remain unchanged. This estimates transferability, not verified physical connectivity. Alpha=0 must recover the old transition law bitwise on matched random inputs.

### Predeclared search and fair controls

Both grids are 0,0.1,...,1. Seven-day paths: D1=(1,1,1,1,1,1,1), D2=(2,2,2,1), R2=(1,2,2,2), D3=(3,3,1), R3=(1,3,3), D5=(5,2), R5=(2,5), D7=(7). Thirty-day paths are the same nine candidate sequences used by the completed schedule experiment, without inheriting any selected sequence/weight. This is a bounded declared family, not all integer compositions or a global-real-parameter optimum. No longer-lag data or new features are added.

The neighbour procedure searches all 8x121=968 candidates at 7d and 9x121=1089 at30d. The no-neighbour procedure independently selects from the alpha=0 subset on the same inner cases. Historical models are references only. A model chosen at one horizon never determines the other horizon's settings.

Use the existing five outer/four inner whole-ID manifests; exclude complete held IDs throughout D, not only R. Fit donor pools/velocity thresholds only on fitting IDs. Pool inner losses by eligible-pair counts. Lock choices before each outer evaluation. Report adaptive-development evidence, not new confirmatory/final-test performance. Old outer results have informed the research direction.

### Numerical integration (independently checked exact-law design)

The initial iid-mixture proposal was rejected before formal execution: rare label patterns at the alpha/lambda corners give excessive variance despite bounded weights. The independent mathematical builder check verified the replacement below.

Use deterministic-mixture multiple-importance integration. For each query, each evaluated joint(alpha,lambda) proposal has r>=2 independent trajectories. Labels are independent at each ordered substep conditional on that proposal. Count intended labels, including dummy labels after absorption/fallback. For k neighbour and l pooled labels over msteps, the likelihood ratio is target_label_probability divided by the mean JOINT proposal probability. Do not factor an irregular proposal set into marginal means. The initial numerical proposal lattice is the Cartesian7x7 grid at0,.1,.3,.5,.7,.9,1; it still scores ALL11x11 target weights. Target membership is unnecessary when proposal support is positive. Exhaustive count-table checks over1..30steps give maximum joint ratio92.1738738221. Refined proposal sets include their evaluated targets. Neither a bounded ratio nor fewer trajectories proves a variance improvement; report estimated precision.

The uncentred score is 1-2*p_hat_truth+norm(p_hat)^2 minus the within-component variance correction. The centred alternative applies the same correction to importance-weighted(e_destination-e_truth). Both estimate the SAME S without renormalisation/clipping; neither integration vector is an issued forecast. The correction is sum_s eta_s^2*(mean||z||^2-||mean z||^2)/(r_s-1). The independent builder verified both formulae; exact enumeration tests and a separately derived two-step production-sampler law check their implementation. A fitting-only dummy-outcome pilot compares repeated numerical variances over the entire declared grids and both horizons to freeze one algebra; smaller model scores never determine that choice.

Initial r=2 for49 numerical proposals per path (98 trajectories/query/path/repeat), scoring all121 targets. This lattice was selected by data-independent positive-support/bounded-ratio calculations, not held scores. Refinement nominalr=4,8,16 uses actual per-path r=max(nominalr,ceil(64*nominalr/number_of_proposals)), ensuring at least256/512/1024 trajectories after focusing the proposal set. Otherwise fewer retained proposals could accidentally reduce precision. Every changed grid/precision/nonce uses fresh independent query-keyed streams, invariant to batch/worker partition. Refine the union of both procedures' contenders, rescreen all original candidates after every update, and retain all initial candidate records. Estimated SE sums are conservative covariance-free comparisons of estimated SEs, not certified error bounds. Empirical zero-SE rows without analytic proof remain unverified contenders. Maximum-precision ties use fewer steps, smaller alpha, larger lambda, path ID and remain flagged.

Outer predictions use ordinary target-law iid particles,128 per repeat and two repeats; their frequencies sum1. No importance vector is used as a map. E/U participate in scoring, never renormalise away. A literal local C++ scorer only accelerates arithmetic; a separate NumPy reference verifies it at multiple r values. Bind Python/C++ source and compiled-library hashes; compile with clang++ -O3 -std=c++17 -shared -fPIC -ffp-contract=off, no fast-math. Deterministic neighbour cumulative-count caches must reproduce every donor choice before enabling worker threads. These are computational objects, not canonical or learned features.

The fitting-only resource/precision profile cannot select model parameters, prune candidates or remove cases. All scientific sources are frozen during formal execution. Immutable checkpoints bind source/config/contracts/input caches and fit/held roles. Resume only matching identities. No publication/installs/data changes.

### Evaluation and outputs

Primary: same S (unbiased collision integration) on all matching outer cases, separately by horizon. Secondary: issued S, nominal90% hit/area/availability, true-outcome probability, finite-ensemble zero frequency (not structural zero), E/U mass and causes, per-ID/cell heterogeneity, fitting donor support. Spatial Energy/mean-square diagnostics retain their declared subset limitations. Keep all failures/cases; never increase a score by dropping difficult IDs. Paired whole-ID200-bootstrap intervals conditional on fixed fits and numerical MC uncertainty are distinct.

A single English REPORT.md must explain the research question, math, selected per-fold settings, same-case comparison, uncertainty, support/failure causes, numerical limitations and what the evidence cannot establish. Save candidate tables, choices, roles/source keys, per-ID/cell results, hashes/runtime/tests and reproduction recipes. This stage does not establish seasonal,365-day,grounding or arbitrary-object accuracy. No publication requested.

### Implementation tasks and review focus

- [x] N1 — Create markov_neighbour.py and test_modelling_markov_neighbour.py: eight-cell indexing; exact equal-pair donor selection; source velocity/fallback; actual coordinate transfer; joint velocity; alpha0 rollback; empty-neighbour U; E absorption. Watch tests fail then pass.
- [x] N2 — Create markov_neighbour_integration.py and its tests: full candidate grids; exact importance ratios; independently enumerated weighted-collision unbiasedness; all endpoints/fallback/absorbing labels; independent repeat streams; selection without historical settings; horizon-specific control choices; numerical tie disclosure.
- [x] N3 — Create markov_neighbour_cv.py, run_markov_neighbour.py and configs/markov_m1_neighbour.json, with orchestration tests: all candidates/cases, guarded immutable caches/checkpoints, complete fit/held-ID exclusion, fit-only profile, all7/30 roles and separately locked choices; no data/test access.
- [ ] N4 — Stopped incomplete by explicit user instruction. Preflight, mathematical review and implementation tests were completed; one outer fold finished. Do not resume the remaining folds without a new user instruction.
- [ ] N5 — Partial first-fold report and particle-level score audit completed in `results/deliverables/markov_neighbour_progress`. Full five-fold reporting and auditing are not completed and are no longer active work. Retain all existing evidence.

Review focus: donor count imbalance must not become equal-cell weighting; neighbour borrowing must retain the current anchor; fallback/dummy labels must preserve exact path probabilities; nested selection must not consume outer outcomes; finite numerical integration uncertainty must not become a spurious accuracy claim. Every item has an explicit N1-N3 test and N5 audit.

---

## Completed stage: 30-day schedule/lambda CV (execution authorised 2026-10-27)

**User decision:** execute CV of lambda and alternative iteration schedules to assess exact-position30-day skill. Latest clarification supersedes fixed-lambda elimination: StageA is diagnostic only; all nine schedules and all eleven lambdas remain in formal inner CV. Work inline with TDD and one fresh whole-change review. Keep this single guide/ledger and existing codex/markov-m1 checkout; no data edits, final test, installs or Git publication.

**Execution status: completed and independently audited.** Formal run `markov_iteration_cv_20261027T120356_034230Z` uses sealed geometry run `markov_iteration_geometry_20261027T114759_607891Z`. The full run and all inner checkpoints are immutable. Source code, experiment configuration, canonical data and final-test isolation were preserved throughout execution.

### Outcome and verified handoff

**The mean score improves slightly, but this experiment does not establish a reliable 30-day benefit from the exact-position method.** All 268,998 eligible origins / 337 IDs were evaluated. Both representations independently searched all nine schedules and eleven lambdas in each of the 20 whole-ID inner roles; no origin or candidate was thinned. S is a probability score, not percentage accuracy.

| Held-ID procedure | Mean S, lower is better | Mean unresolved mass |
| --- | ---: | ---: |
| Independently selected coarse model | 0.985255 | approximately 0.00000147% |
| Independently selected exact-position model | 0.985134 | 0.511159% |
| Exact-position model at old frozen settings | 0.985219 | 0.527484% |

Exact-position CV minus coarse CV is -0.000121280; its paired whole-ID 95% interval is [-0.00121284, +0.00125367]. The comparison with frozen exact-position settings is -0.0000850950, interval [-0.000235736, +0.000103668]. Both intervals cross zero. Numerical MC uncertainty is reported separately; a small numerical MC interval cannot replace the much wider ID-level uncertainty. These are fixed-fit, adaptive development comparisons, not final-test or prospective validation.

| Outer fold, one-based | Exact-position selected schedule | Selected lambda | Numerical ranking |
| --- | --- | ---: | --- |
| 1 | 2, 7, 7, 7, 7 | 0.3 | unresolved competitors; declared tie rule |
| 2 | 2, 7, 7, 7, 7 | 0.3 | unresolved competitors; declared tie rule |
| 3 | 2, 7, 7, 7, 7 | 0.6 | unresolved competitors; declared tie rule |
| 4 | 2, 7, 7, 7, 7 | 0.2 | unresolved competitors; declared tie rule |
| 5 | 2, 7, 7, 7, 7 | 0.4 | unresolved competitors; declared tie rule |

All five choices use the 2-day remainder first, but this does not prove a unique optimal route or lambda. Every selected lambda retains numerically unresolved competitors at the maximum declared precision. No average lambda or global deployment model was chosen from outer outcomes. The reconstruction archive contains the evaluated per-outer fit recipes; an all-development refit remains a separate, unscored step.

Point differences are heterogeneous: 30/37 origin cells improve, but only 166/337 IDs improve. Positive ID loss contributions total +395.294 and negative contributions -427.918, leaving a small net -32.6242 across all pairs. Individual ID contributions can exceed this net gain. Do not remove or downweight unfavourable IDs to improve the result. Whole-path unresolved mass is 0.142796% from unsupported cells and 0.368364% from synthetic endpoint geometry. This is model uncertainty/failure, not confirmed grounding or an instruction to delete observations.

Independent artifact auditing verifies 530 output hashes and 108 current input/source hashes, all 20 initial grids, common outer cases/truth, the collision-score identity, original coarse grouped scores, E/U cause conservation, paired-ID intervals and separate MC calculations. Fresh checks pass: 166 modelling + 10 architecture + 22 preparation tests. The observed-cohort figure uses 1,053 pairs / 38 held IDs, selected by fitting support; panel probability sums, common colour scale and the rendered image were checked. It is a cohort illustration, not a single-point forecast or proof of sharper calibrated regions.

Readable evidence: [experiment report](../results/runs/markov_iteration_cv_20261027T120356_034230Z/REPORT.md), [static review](../results/runs/markov_iteration_cv_20261027T120356_034230Z/review.html), [independent audit](../provenance/reviews/markov_iteration_cv_20261027T120356_034230Z_independent_audit.json), [cell differences](../provenance/reviews/markov_iteration_cv_20261027T120356_034230Z_cell_differences.csv), [ID differences](../provenance/reviews/markov_iteration_cv_20261027T120356_034230Z_ID_differences.csv), [source/config/tests and reconstruction recipes](../provenance/reviews/markov_iteration_cv_20261027T120356_034230Z_reproduction.zip).

Scope limits: annual-pooled, known-initial-velocity forecasts on the existing 1-degree pilot R/D and stopped target. No new CK distribution-consistency or intermediate-outcome error scoring was executed; support traces do not identify when predictive error begins. No seasonal, 365-day, grounding, other-object or new-region skill is established. Final test remains unread and no Git publication was performed.

### Question, authority and scope

Can a different composition of the existing empirical displacement kernels improve 30-day stopped destination distributions? The previous exact-position run froze old hyperparameters: S30=0.985268 versus old M1vcat0.985249, paired-ID difference interval[-0.000995,+0.001306]. This does not identify an optimal schedule or demonstrate equivalence.

Data Contract v1.0 remains authoritative, SHA6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446. Keep the existing R/D, 1-degree outcome grid, annual/drogue pooled scenario, nine velocity classes, fit-ID-only speed median, source E and transferred-hourly first exit, U/backoff rules, exact timestamps and equal eligible hourly-pair weighting. Reuse position input markov_position_input_20261027T093543_211496Z and existing source/velocity parents. Final test remains locked. No canonical data/feature edits, new environmental or historical predictor, seasonal/regime/365-day experiment, MDN, new lag kernel or Git publication.

### Approaches considered

1. Compare fixed schedules only: cheapest and isolates composition; does not optimise lambda for the new model.
2. Search schedule/lambda simultaneously from the outset: wider search, but obscures why forecasts change and has a large laptop cost.
3. **Current two-stage ruling:** fixed-lambda schedule diagnosis, followed by joint selection across all99 path/lambda candidates. The earlier bounded-shortlist proposal is superseded because it could exclude a route that improves at another lambda. StageA remains explanatory and never eliminates a route. The nine predeclared paths are still a bounded family, not an exhaustive search of all integer partitions of30days.

### State and propagation

The carried state is exact WGS84 position plus the existing velocity category, or E/U. Let K[d,lambda] denote the already defined empirical donor transition kernel at d days. For schedule s=(d1,...,dm), with positive integer entries summing exactly30, propagate q0=point_mass(x0,b0) and q[k+1]=q[k]K[dk,lambda]. Only the final map marginalises velocity and bins positions into cells. Never chain a cell-only 7-day probability picture: that loses the within-cell coordinates and velocity needed by the next step. A macro 7-day block is an explicit sequence of existing kernels, not a newly learned direct7-day kernel.

Every kernel is estimated from eligible fitting-ID D-origin pairs at its own lag. Do not construct a longer-lag kernel by renaming a power of a short one. No held-out future position/velocity enters propagation. Source E/U absorb at every substep, and transferred observed-hour path checks remain unchanged. The same lambda is used at every step in a candidate; no per-step, per-cell or per-particle lambda search.

### Predeclared schedules (nine; no exhaustive search of integer partitions)

Read sequences left to right. Repetition means repeating the listed kernel sequence.

| ID | Sequence, total30days | Steps | Hypothesis |
| --- | --- | ---: | --- |
| D1 | 1 repeated30 | 30 | Short transitions versus accumulated composition error |
| D2 | 2 repeated15 | 15 | Intermediate short lag, already cached |
| D3 | 3 repeated10 | 10 | Moderate fixed lag |
| D5 | 5 repeated6 | 6 | Transfer the short-horizon base-lag idea to30days |
| D7 | 7,7,7,7,2 | 5 | Existing long-step reference sequence |
| R7 | 2,7,7,7,7 | 5 | Same kernel counts as D7, changed remainder placement |
| W3 | (3,3,1) repeated4, then2 | 13 | Repeat the actual3+3+1 seven-day procedure |
| W5 | (5,2) repeated4, then2 | 9 | Repeat the actual5+2 seven-day procedure |
| W5R | (2,5) repeated4, then2 | 9 | Same counts as W5, changed ordering |

D7/R7 and W5/W5R isolate order with equal component counts. D1/D2/D3/D5/D7 compare lag policies, not iteration number alone: lag length also changes donor support and fitted laws. There is no assumption that fewer steps must be better. Kernels4/10/15/30 are deliberately excluded from this round; direct B2 remains a terminal reference, not a composable D-wide kernel.

### Exact two-stage selection protocol (latest user clarification takes precedence)

For each existing outer whole-ID fold, its entire evaluation population stays outside all inner selection. Reuse the four existing inner folds and fit-role thresholds.

1. StageA diagnoses all nine paths at the original coarse-model30-day lambda chosen from that outer training pool's historical inner CV. This is a frozen CV-derived reference, not manual0.2 and not a claim of a precision-model optimum. **No path is eliminated.** Compute a valid lower-allocation target16 subensemble within each conditional stratum of StageB target32; label the stratified diagnostic and do not select from it.
2. StageB scores the full9x11 path/lambda grid using all eligible30-day inner origins at numerical target32 x2repeats using the exact conditional-stratum identity below. No ID or observation thinning. A candidate uses one lambda across its entire sequence. Reuse fitting pools and random inputs; selection uses collision S only.
3. Within each outer training pool, select the smallest pooled four-inner-OOF S. If the gap to a rival is within twice paired MCSE, refine the near-best set at64x2, then128x2, using common precision and all inner cases. Rescreen all original candidates against current-best mean and uncertainty before locking; a low-precision discarded candidate must not become unexamined merely because the best was refined. At maximum resolution unresolved competitors use economy tie rule: fewer substeps, larger lambda, ascending pathID, with explicit unresolved flag. No assertion of global optimality.
4. Separately optimise the coordinate-discarded/coarse representation over the **same99 candidates**, with exact sparse joint-state multiplication and identical fitting/inner cases. This is required to distinguish the coordinate effect from extra tuning opportunity. These are the existing two representations, not a new statistical family. Retain coarse at precision-selected settings and precision at coarse-selected settings as matched-setting controls, plus both historical frozen controls and B2 direct30-day reference.
5. Save each outer's choices before evaluating its held IDs. Refit on all outer-fitting IDs with the role's threshold. Score every original eligible outer30-day origin (expected pooled268998pairs/337IDs). Precise arms start64x2; analytic coarse arms need no particle integration. All comparisons use the same source cases. Report both the optimised-procedure difference and same-setting position effects; never attribute a tuned-versus-frozen gain entirely to coordinates.
6. All pool construction filters complete fitting IDs across R and D. No outer outcome selects paths/lambda or refinements. More favourable inner scores are not performance claims. Historical outer observations have informed this research direction, so the new nested comparison remains adaptive development evidence, not a fresh confirmatory or final-test evaluation.
7. A reconstructible full-development candidate may select from pooled training-side inner OOF scores (each query appears in four distinct outer-training searches) and refit all development IDs; label this repeated development selection and the refit as unscored. Never use its inner score as an independent accuracy estimate.

### Numerical precision and laptop feasibility

First run a deterministic fitting-only engineering profile that covers near-D-boundary and ordinary D paths, all kernel lengths, memory and donor/path-check costs. Do not inspect new outer scores in this profile. The last frozen comparison took2127seconds; nine routes times eleven lambdas times twenty inner roles must not be launched as an unprofiled Cartesian job. Publish projected time/memory and cache reuse before full execution; if infeasible, revise the search scope with the user rather than silently drop records/candidates or open test.

Integration levels: formal StageB starts32x2 on all inner origins; fixed-reference StageA uses first-target16 subensembles within each stratum only for diagnosis. Near-best contenders refine64x2/128x2 when MC can change selection. Outer comparisons start64x2. Record per-candidate precision, all scores and paired MC differences; use common precision for the final competing set. No manual lambda, hard shortlist, observation thinning, silent grid reduction or outer-driven refinement.

Keep all canonical records and main analysis origins; smaller particle counts change numerical integration, not statistical sample weights. Use independent repeat streams and documented common random inputs between candidates. Save seeds, per-origin scores, source/fit identity and component donor support. Preserve ordinary issued-ensemble S alongside the unbiased collision estimate; never clip a negative individual collision estimate to zero. Zero sampled probabilities are numerical observations, not proven structural zeros. Reuse existing empirical pools and duplicate prefixes only where the full joint particle state and RNG semantics are identical; otherwise recompute.

### Exact shared-lambda integration (engineering ruling, independently checked)

For m ordered affine substeps, condition on k pooled-component labels. Sample each label pattern uniformly given k; do not commute the kernels. Each stratum's exact weight at lambda is w[k]=choose(m,k)*lambda^k*(1-lambda)^(m-k). The mixture of conditional endpoint laws is the original model. Missing rows L=B and E/U dummy labels preserve this identity.

Use N[k]>=max(2,ceil(target*max_tested_lambda w[k])) for active strata. This bounds each target category probability estimator's variance by its iid-target counterpart, without claiming a universal bound for nonlinear score variance. The issued distribution is the normalised weighted sum of stratum frequencies. Compute unbiased S by subtracting sum_k w[k]^2*(1-sum_j(p_hat[k,j]^2))/(N[k]-1) from ordinary issued S. Cross-stratum products are independent; within-stratum terms are U-statistics. All origins retain equal statistical weight. Target32 is a precision allocation parameter, not32total particles or an iid estimator; actual counts are saved per path. Final outer evaluation remains the old iid64x2 estimator.

Different paths and allocation layouts have separate keyed streams, preventing cross-query random-number overlap when particle layouts differ. Lambda targets within one path share the conditional samples. Scope paired covariance by evaluation call; old covariance cannot follow a recomputed same-level score. Different-precision calls are independently keyed; unknown same-level cross-call covariance uses the conservative Cauchy bound.

Fresh reviewer independently exercised the production sampler/scorer on a noncommuting two-state example for all eleven lambdas/2000origins, with maximum error1.12estimated MC standard errors. Unit tests independently enumerate the score identity, recover the original single-stratum estimator and check all99targets/serial-thread equality. This is numerical integration, not a new predictor/model family or changed origin weights.

### Explanatory diagnostics

- Borrow the Chapman-Kolmogorov consistency idea: compare K1K2 with K3, K2K3 with K5, and K5K2/K2K5 with K7 on identical query states, along with held-out short-horizon outcomes where eligible. Same state representation, fit IDs, lambda and E/U accounting are required. Location marginals plus E/U can be compared without renormalisation, with MC uncertainty. This diagnoses empirical composition consistency; it does not prove the true process is Markov or make all kernels equally well estimated. Different lag eligibility populations, finite sample support, velocity categorisation, source-E handling and synthetic geometry can all contribute.
- Record U/E mass and missing-row/whole-cell/geometry failure counts after each actual substep. Trace how support failures accumulate rather than attributing every difference to numerical iteration error.
- Score intermediate outcomes only at each route's actual cumulative boundaries using source-traceable stopped labels. Existing parent R labels cover1/2/3/5/7/30; other times require a derived label ledger with the same contract rules and no canonical edits. If not generated, intermediate error remains unscored. Compare errors only at matched days/cases; never fabricate an observation or alter a30-day route to manufacture a common checkpoint. Intermediate comparisons cannot silently change the primary30-day population or decide the winner using outer outcomes.
- Report per-cell and per-ID S changes and support; a mean gain dominated by one ID/cell is disclosed. Changing the weighting to hide it is outside scope.

### Scoring, acceptance and handoff

Primary selection remains all-case S=1-2p_truth+sum_physical_or_E(p^2)+u^2. **All StageA ranking, StageB selection, MC comparisons/ties and outer acceptance use the unbiased collision estimate `S_integration`, not `S_issued`.** For M particles and state counts n[k] including U, estimate it as `1 - 2*n[truth]/M + sum_k(n[k]*(n[k]-1))/(M*(M-1))`, then average equally over eligible origins and independent repeats. Ordinary finite-issued-ensemble `S_issued` is secondary throughout; its precision-dependent upward bias must never select a route/lambda. Changing the numerical estimator does not change the underlying probability-score definition. Existing Energy/100km+squared ECEF-mean error/10000 stays auxiliary with explicit availability/common-subset limits; no new loss weights or per-route score. Report E/U, distribution coverage/size, independent IDs and MC uncertainty separately. Formal spatial/region superiority is unavailable until the relevant particle-resolution and support conditions are met; 16/32-particle region sizes do not establish sharpness. High-particle illustrations can be produced for fitting-support-selected examples without implying full-population coverage calibration.

Publish paired whole-ID95% intervals for the selected procedure versus both frozen controls, and numerical uncertainty separately. Reuse the original200bootstrap replicates for comparability; selection/refit/researcher-adaptation uncertainty remains outside that conditional interval. Claim a supported development gain only when the primary difference is stable to numerical resolution and its paired-ID interval excludes zero; a lower mean with a crossing-zero interval is tentative, not a confirmed replacement. Do not infer equivalence from no significant difference. More U must remain visible and cannot be hidden by renormalisation or favourable spatial-only subsets.

Deliver one English report/review with the frozen schedule table, complete StageA and StageB score/precision tables, per-fold shortlists/choices/ID roles, matched outer scores and paired intervals, cumulative support diagnostics, source-backed maps, resource profile and a reproducible candidate recipe. Keep this single guide and the existing execution ledger updated in place. Do not overwrite old runs or commit/push. User explicitly authorised the corrected CV/composition implementation on2026-10-27; continue without repeated approvals inside this scope.

### Engineering implementation plan and task checks

- [x] I1: test-first arbitrary schedule validation/propagation, vectorised collision-score identity, all99candidate enumeration, same-case CV aggregation/MC uncertainty and score ties. Preserve existing model defaults and reference semantics.
- [x] I2: test-first optional acceleration with cached native WGS84 donor azimuth/distance and a conservative directional hourly-path certificate. This is computational metadata only, not a model feature. Cache last west/east source-hour offsets; directional path-length bounds can prove a transfer stays inside D using conserved geodesic longitude direction plus the original north/south distance bound. Uncertified paths still use the original full hourly scan. Verify exact states against unaccelerated steps and independent boundary challenges; no interpolation/approximate geometry. Prepare a new immutable auxiliary run from the sealed development cache.
- [x] I3: test-first guarded nested runner, all99 search for both representations, role/fold/case identity, no hard pruning, checkpoint/resume and common precision refinement. Vectorise inner scores, reuse donor pools, use at most4 numerical worker threads with private GEOS mappers and deterministic streams. Full code/source sealed during active runs; recover completed role outputs without rewriting artifacts.
- [x] I4: fitting-only profile before formal launch; verify acceleration/control identities and forecast/memory/runtime scaling. If cost makes the unchanged search infeasible, report the actual profile before any scope change. Execute all required folds/choices/outer scores, preserve failed/negative results and produce one English report/maps/recipe.
- [x] I5: one fresh whole-change reviewer, independent saved-artifact audit, focused model/architecture/preparation tests, SVG render/inspection and single-guide/ledger update. No Git action.

Review focus: held-ID leakage across wideD donor pools, changing score bias across particle levels, source E versus additional transferred first exit, exact ordering/remainder arithmetic, same-setting versus independently optimised interpretation, and preservation of all268998primary30-day cases.

Rulings implementing the latest authorisation: all99candidates retained; no manuallambda_ref.2; StageA cannot prune. Fair coarse optimisation is necessary to attribute position gains. Cache acceleration and four-thread evaluation must produce the original law, not a changed model. Existing checkout and single ledger override skill-default new worktree/document copies/commits.

### Primary references and applicability

- O'Malley et al. (2021), *Estimating the Travel Time and the Most Likely Path from Lagrangian Drifters*: https://doi.org/10.1175/JTECH-D-20-0134.1 ; author-hosted manuscript https://arxiv.org/abs/2002.07774 . Published lag sensitivity motivates testing, not choosing5days as Atlantic truth or as optimal for our velocity-conditioned state.
- deeptime CK validation: https://deeptime-ml.github.io/latest/api/generated/deeptime.markov.msm.MarkovStateModelCollection.html . Borrow the validation principle, not its metastable/reversible modelling assumptions or package implementation.
- scikit-learn nested-CV guidance: https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html . Inner selection versus outer evaluation is the relevant principle; all splitting here remains whole drifterID.

### Preparation, review and profile evidence

Geometry run `markov_iteration_geometry_20261027T114759_607891Z` sealed:33,935,812native development rows, five deterministic cache files,269.4seconds,peakRSS5.44GB. No canonical reads/writes or final-test reads. Profile `markov_iteration_profile_20261027T115707_492026Z` sealed:1024fitting-only queries with dummy outcomes used only for runtime, all99targets, peakRSS7.40GB. Five paths at lambda0/.3/1 match cached/uncached forecasts exactly; endpoint lambda strata match the original sampler.320independent D-side stress cases include222exits and match brute-hourly geodesics.

Profile target32 all99 exact-position computation13.02seconds/1024queries; crude linear fine-query extrapolation to all20inner roles is13,677seconds before refinement/setup. Coarse time23.0seconds includes pool construction and sparse propagation: its query-linear extrapolation is not a reliable runtime forecast because propagation scales mainly with distinct joint origin states. Actual per-role timing will be retained. The unchanged complete search is feasible as a multi-hour local calculation; no candidate/data reduction is authorised.

Fresh whole-change reviewer found no model/math/leakage blocker. Three important items regraded confirmed and repaired test-first: stale same-level covariance, missing saved outerMC contrasts, missing per-substep failure causes. All now have RED->GREEN regressions. Report/guide updated to distinguish target allocations from iid particles. Outer work is deliberately recomputed on fresh-namespace resume; completed hash-verified inner computations are reused. Source/cache/contract identity remains frozen during each active run.

## Completed stage: exact-position M1vcat refinement (approved 2026-10-27)

**Completed-stage goal:** test whether preserving within-cell coordinates during empirical displacement propagation improves the frozen M1vcat 7/30-day forecasts. The user explicitly authorised that bounded comparison. This section preserves its completed plan; the current schedule/lambda CV protocol is above.

**Authority:** the latest architecture conversation and unchanged Data Contract v1.0 (SHA `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`). Exact point is an evaluated extension. Work locally on `codex/markov-m1`; retain the single execution ledger. No canonical data/feature change, final-test access, new worktree, dependency installation, Git publication, MDN, kernel weighting, continuous-velocity regression, new history/season/regime feature or hyperparameter search.

**Fixed comparison:** reuse `markov_vcat_input_20261026T155040_667626Z` and `markov_vcat_cv_20261026T155955_651594Z`. Every outer fold retains its original fitting IDs, fitting-only speed median and selected per-horizon lag/lambda. Retain the development-candidate settings 5/.3 (7d) and 7/.1 (30d) for an unscored reusable refit. All 303288/268998 held-ID R pairs remain in primary scoring. No new inner selection is needed because all parameters are frozen.

**Mathematical refinement:** a qualified survivor donor supplies WGS84 inverse-geodesic azimuth/distance from its actual origin to its actual endpoint, jointly with the existing endpoint velocity class. Source first-exit donors supply E directly. Estimate the local and cell-pooled empirical donor laws by the same equal-pair frequencies as M1vcat. Sample their mixture `(1-lambda)*local+lambda*pooled`; missing conditional rows use pooled, wholly unsupported cells use U. At a survivor draw, apply its azimuth/distance at the particle's current exact coordinate, retain the new coordinate and donor endpoint class, and re-bin that new coordinate before the next step. E/U absorb. Do not reset particles to cell centres or reuse held-out future states. At the original donor anchor, recover the exact original endpoint rather than introduce roundoff.

**Boundary rulings:** the source E branch remains the original cell/class-conditioned empirical exit probability; it is not counterfactually reclassified after moving an anchor. A translated survivor may create additional first exits: transfer its observed hourly displacement shape relative to its source origin and check actual D membership at every corresponding hour. Any exit remains E after later return. For paths proven interior by a conservative WGS84 geodesic-ball bound, skip the expensive scan with identical results. Nonfinite/land synthetic endpoints use the already frozen high-resolution GSHHG lookup and become U, never beaching or source exclusions. Do not infer beaching or reject a straight segment merely because it crosses land. The transferred intermediate shape is used for observed-hour D exit semantics; no new synthetic coastal-fate model is introduced. Record all endpoint geometry and support failures separately.

**Resource architecture:** stream one compact memory-mappable hourly source array, per-ID ranges and per-lag donor origin/endpoint index arrays; every donor retains its source ID/key. Do not materialise a full hourly path per donor or an observation-by-donor matrix. Derive geodesics only for sampled survivors. A prefix sum of native hourly path lengths provides a conservative transferred-path radius. Use vectorised uniform donor sampling from cell/class groups. All caches live under new immutable results/provenance runs. Preserve exact counts and source-reason digests against the parent cache.

**Numerical comparison:** old analytical M1vcat is the reference. Run both a coordinate-discarded donor sampler (must reproduce old M1vcat in expectation) and the position-preserving sampler with common random inputs, at identical particles/seeds/cases. Preserve ordinary Brier/S for the issued ensembles and report an unbiased collision-count estimate of the same underlying S as an integration diagnostic. Report Monte Carlo variation independently from paired whole-ID uncertainty. Do not call a zero sampled probability a proven structural zero. Start with a deterministic engineering pilot; full evaluation uses a predeclared 32-particle initial level and an independent repeated level, increasing integration only when needed to resolve the comparison. Coverage/area and spatial scores of finite issued ensembles are explicitly approximate; no-hit U does not certify zero U in the limiting operator. Keep formal spatial results unavailable where completeness cannot be established, with separately labelled finite-ensemble diagnostics.

### Task P1: empirical donor sampler and WGS84 position update

Create `src/data3001/modelling/markov_position.py`, `tests/test_modelling_markov_position.py`.

- [x] RED: same-cell different offsets produce different re-binned outcomes; identity anchors/zero displacement recover exact endpoints; velocity class remains joint with displacement; local/pooled lambda endpoints, missing row/U and E absorption match old counts; a cosmetic coordinate attachment leaves cell probabilities unchanged.
- [x] Implement compact donor pools, vectorised common-random sampling and exact-coordinate update. Implement hourly transferred D first-exit checking plus an independently testable conservative interior certificate. Pin prefix interval validation, exit/re-entry, endpoint-land/U and no-renormalisation edge cases.
- [x] GREEN: pure numerical/semantic fixtures and old-M1vcat marginal identity on the donor pools. Do not require lambda=1 to reproduce old location forecasts after geometry is changed: it is then the position-refined pooled displacement law.

### Task P2: source-preserving displacement cache

Create `src/data3001/modelling/markov_position_inputs.py`, focused input tests and `configs/markov_m1_position.json`.

- [x] RED: exact source-key/end-time pairing, memory-mapped cache round trip, ID boundaries, source first exits without horizon endpoints, zero-eligible R files and parent count/digest reconciliation.
- [x] Stream all development records/qualified donor indices with native coordinates/atoms, hourly path-length prefix and traceable R origin/label rows. Use fixed parent cuts and thresholds; no source cleaning or reclassification. Compare every per-ID lag marginal to the sealed parent.
- [x] Pilot before full preparation; record memory/disk/time and no-test/no-mutation guard evidence. No source edits while a sealed-run writer is executing.

### Task P3: frozen-fold comparison and readable results

Create `src/data3001/modelling/run_markov_position.py`, `markov_position_report.py` and focused runner/score tests.

- [x] RED: frozen fold choices/medians, no fitting/held-ID overlap, exact remainders, matched all-case scoring, collision-estimator arithmetic, shared-random coarse control, finite-ensemble versus limiting-law scope and probability conservation.
- [x] Profile on the small cache, then score every original outer R origin at the original frozen lag/lambda. Save per-ID aggregate losses, optional compact per-origin diagnostics, prediction examples, settings, donor-pool support and source identities. Old exact score denominators/values must reproduce the parent.
- [x] Produce one English REPORT/review page with S, Monte Carlo error, coverage/area tradeoff, paired-ID uncertainty and spatial-reference availability; select illustrated origins using fitting support only. Preserve existing outputs and honest negative results.

### Task P4: independent review and artifact verification

- [x] One fresh whole-change reviewer; re-grade and fix important findings with observed RED->GREEN tests. No implementation delegation.
- [x] Independently reproduce source counts, selected WGS84 paths, old-control probabilities, saved scores and conservation; render and inspect figures. Run focused modelling/architecture/synthetic preparation tests, update this guide and the existing ledger in place, and stop at the result-review checkpoint.

### Verified exact-position outcome and review checkpoint (2026-10-27)

**Status: completed development comparison; user result-review checkpoint.** Full input: `markov_position_input_20261027T093543_211496Z`. Comparison: `markov_position_cv_20261027T094335_386746Z`. No canonical data or feature columns changed; no final-test access or Git publication. All original whole-ID roles and 303,288/268,998 R cases are retained. The comparison took 2,127.2 seconds with 7.97 GB peak RSS.

| Horizon | Old analytic M1vcat S | Exact-position S estimate | Difference (new minus old) | Fixed-fit paired-ID 95% interval |
| --- | ---: | ---: | ---: | --- |
| 7 days | 0.921873 | 0.914248 | -0.007625 | [-0.010663, -0.004724] |
| 30 days | 0.985249 | 0.985268 | +0.000019 | [-0.000995, +0.001306] |

Lower S is better. The new values average two independent 32-particle collision estimates of the same S; ordinary finite-ensemble S remains separately visible. Seven-day S improves in all five outer folds. Thirty-day S improves in two folds and worsens in three: no stable gain is established. The 0.827% relative decrease in 7-day S is not a percentage-point increase in forecast accuracy.

The coordinate-discarded sampler differs from the old analytic S by -0.000037 (7d) and +0.000087 (30d), consistent with its integration error. Case-wise paired Monte Carlo SE for new minus old is 0.000121/0.000060; approximate MC-only intervals are [-0.007861,-0.007388] and [-0.000097,+0.000136]. This uses `sqrt(sum_i((delta_i_repeat0-delta_i_repeat1)^2))/(2*N)`, conditional on fixed queries/fits and independent query RNG streams. All 5,140/4,566 batch-repeat seeds are unique within each horizon. These intervals describe numerical integration, not generalisation to new IDs.

**Numerical ruling:** the initial level resolves the substantial 7-day effect. Thirty-day data-level uncertainty spans zero by much more than numerical uncertainty; report an inconclusive near tie rather than run more particles to claim superiority. The optional `--integration-level 1/2` changes particles to64/128 per repeat without retuning. This round does not establish convergence, equivalence or limiting-law region calibration.

Mean unresolved mass increases to about0.328%/0.530%. E/U remain visible and absorb; source pairs are never dropped or renormalised after synthetic geometry/support failures. Do not call the smaller issued32-particle regions sharper than the analytic old model: their support/coverage are under-resolved. Formal limiting-law spatial completeness remains unverified; saved Energy/quadratic values are finite-issued-ensemble diagnostics on their stated available subsets.

The evidence supports retaining exact-position propagation as a useful **7-day development refinement**, not replacing the30-day reference on a claimed accuracy gain. No default model registry was changed. Exact coordinates preserve offsets and change re-binning; they do not yet learn a continuously varying within-cell flow function. No annual/seasonal/grounding/universal-object claim is made.

**Verified artifacts:**37 sealed comparison files;2,861,430 score rows; all per-ID S sums and six paired bootstrap contrasts independently reproduced;304 old joint rows checked within2.23e-16 plus all donor row counts; all3224source ranges/digests reconcile. Five source IDs/63,061native records match exactly.399independent transferred-path checks include145boundary exits. Both1200x800SVGs rendered and inspected; maps use fitting-selected cell44384/class8, matching1138pairs/43IDs and1053pairs/38IDs. Fresh review's two important findings were repaired and regression-tested. Final checks:139modelling+10architecture+22preparation tests pass. Audit: `provenance/reviews/m1vcat_position_20261027.json`.

Human review page and full English method report: `results/runs/markov_position_cv_20261027T094335_386746Z/review.html` and `REPORT.md`. Reproduce with `.venv/bin/python -B -m data3001.modelling.run_markov_position --input-run markov_position_input_20261027T093543_211496Z`; outputs go into a new immutable run. Do not retune or open final test as part of this comparison.

## Completed stage: M1vcat development comparison (2026-10-27)

> **For agentic workers:** implement inline using `superpowers:executing-plans`, test-first steps and one fresh whole-change review. This is the single live design/plan. The user approved the preceding conversational specification and explicitly authorised implementation after the final audit; do not request the same approval again. Historical sections below remain evidence.

**Goal:** test whether a compact categorical velocity state improves annual-pooled, 1-degree, 7/30-day stopped-domain forecasts over the frozen position-only M1. This does not learn continuous velocity functions or establish seasonal/year/grounding skill.

**Architecture:** source-qualified per-ID sufficient counts -> fitting-ID-only speed threshold -> sparse joint cell/velocity operators -> nested whole-ID lag/lambda selection -> location-marginal scoring and a human-readable report. Reuse the existing data access/qualification, fold, scoring, provenance and run-sealing APIs. Preserve all old source/result files and canonical columns/values. Work on the existing `codex/markov-m1` branch; no new checkout, Git commit/push/merge, dependency installation or final-test access.

**Spec and authority:** Data Contract v1.0 SHA `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446` and the user-approved M1vcat conversational design. Retain R/D/state grid, exact matching, all qualified hourly pairs at equal weight, stopped first observed exit, separate E=-2/U=-3, annual and drogue pooled, primary all-case Brier/S and unchanged auxiliary spatial scoring. Official ve/vn are finite and are retained without clipping or re-imputation.

### Approved model and bounded implementation choices

- Velocity labels: zero vector is class 0 and is not absorbing. For nonzero `(ve,vn)`, quadrant `q=2*(vn>=0)+(ve>=0)` is SW/SE/NW/NE. The class is `1+2*q+int(speed>m)`, with speed=hypot(ve,vn). Equality to m is the lower-speed class; exact axes follow the >= rule. Thus there are nine possible labels. No alternative direction resolution is selected in this run.
- The threshold m is the exact median of positive speeds at position/mapping-qualified D hourly observations from fitting IDs only, independent of lag and target follow-up. All-zero fitting observations use m=0; absent fitting origins fail. All kernels in the same fit share this mapping. Excluding the exact zero vector from the median is the executor's explicit clarification of the separate-zero-class rule, not a change to row eligibility or weights.
- Estimate local joint counts N[(i,a),z] and the cell-pooled joint law B[i,z]=sum_a N[(i,a),z]/sum_(a,z) N[(i,a),z]. z is either a future cell/velocity state or E. There are no observed U training destinations. Blend supported rows as `(1-lambda)*local+lambda*B`. A missing conditional row falls back to B; a cell without any fitting pairs goes to U. E/U absorb. Every eligible source pair remains counted.
- Candidate primary lags: 1/3/5/7 days, with exact remainder kernels (1/2/3/5/7). Lambda grid: 0,.1,...,1. Select independently at day 7 and day 30 by pair-weighted inner-OOF S. Ties within 1e-12 prefer shorter lag, then larger lambda (less velocity conditioning). No old closed-form lambda is applicable to matrix powers.
- Initial query in this experiment includes the observed origin cell and velocity label. Held-out trajectories are never consulted between origin and target. Maps/scores marginalise future velocity only after propagation. Claims apply to the known-initial-velocity historical query, not an unspecified-velocity release query.
- Fit empirical rows by multinomial likelihood; CV chooses smoothing/lag. The smoothed law is not claimed to maximise the original unpenalised likelihood. Selection remains S; Energy/100 + squared-mean-error/10000 remains auxiliary on unchanged common complete in-D cases. Keep unavailable spatial scores and all U cases visible.
- Main comparisons: M1vcat-selected, its lambda=0 lag-selected control, and an exactly reproduced old M1-selected. The old stopped B0/B1/B2 controls remain on identical cases. At each fixed lag, lambda=1 must reproduce old M1 locations within 1e-12. Nested folds are the original outer-five/inner-four ID maps. Final development refits are candidates, not final-test evaluations.

For a supported joint source state `s=(i,a)`, the local estimate is `L_delta[s,z]=N_delta[s,z]/sum_z N_delta[s,z]`. The cell-pooled estimate is `B_delta[i,z]=sum_a N_delta[(i,a),z]/sum_(a,z) N_delta[(i,a),z]`. Propagate the row vector as `p_H=one_hot(i,a) T_delta^q T_r`, where `H=q*delta+r`; omit `T_r` when `r=0`. The location map is `P(C_H=j)=sum_b p_H[(j,b)]`, retaining E and U separately. The primary score is `S(p,y)=sum_(k in D cells or E) (p_k-1[k=y])^2+u^2`. Thus categorisation changes the predictive state and its propagation, while leaving the observed destination and primary scoring target unchanged.

### Input cache and resource boundary

The old aggregated counts cannot recover origin/endpoint velocities. Read the current development tracks once for source velocity observations and once for qualified D pairing, without changing any file. Reuse sealed R label/source keys from `markov_diagnostic_input_20261025T113812_255111Z`; compare all D lag and R target counts to this parent.

For exact fitting-only thresholds without duplicating 100M raw pair rows across folds, prepare the predeclared 20 inner, five outer and full-development medians from fitting D origins. The sorted unique median values define **lossless cache-only speed intervals**. Store per-ID counts by origin/destination cell, quadrant/interval (plus zero/E), and lag. In any fit, merge these intervals using only that fit's own median. Adding another cache cut must leave a fit's coarse counts unchanged; other folds' cuts have no statistical effect. Preserve threshold fitting-ID records and candidate/reason/digest receipts. This is a computational encoding, not a shared full-development model threshold.

Use sparse matrices and batch only the distinct held-out origin joint states; never allocate a dense joint-state distance matrix or silently prune small probabilities. Score after marginalising to the original cell index. A deterministic 20-ID engineering pilot must pass reconciliation and a resource profile before the full cache. Store outputs under results/runs and provenance/runs, not data/train or data/test.

### Review focus

1. Fitting-only medians and exact-zero/equal-threshold/axis conventions remain consistent across remainder kernels and serialisation.
2. Exit then re-entry remains E, E requires no fabricated future velocity, and missing follow-up does not become an observed U.
3. Conditional velocity groups must survive validation aggregation; a cell-only grouped validation table is insufficient.
4. Cache-only extra cutpoints cannot change a fit; summing velocity counts exactly restores the parent's ID/lag/cell counts.
5. Lambda=1 restores the old M1 at every tested horizon, including missing conditional rows and unsupported cells; probability and ID boundaries remain intact.

### Task V1: pure joint model and independent mathematics

Files: create `src/data3001/modelling/markov_velocity.py`, `tests/test_modelling_markov_velocity.py`.

- [x] RED: nine-class encoding, threshold equality/axes/zero/extremes, cache-cut invariance, local/pooled counts, missing-row backoff, E/U absorption and exact remainders.
- [x] Implement `velocity_atoms`, `coarse_velocity`, `fit_joint_operator`, `joint_forecasts` and `location_forecasts`; explicit cells/bins/threshold/fitting IDs/lag metadata and sparse matrix storage.
- [x] GREEN: independent two-step velocity-memory fixture, marginal count identity and lambda=1 old-M1 equality. Reject nonfinite inputs, mismatched bin maps/IDs and missing remainder operators.

### Task V2: auditable development-only source adapter

Files: create `src/data3001/modelling/markov_velocity_inputs.py`, `tests/test_modelling_markov_velocity_inputs.py`; config and runner belong to V3.

- [x] RED: source-key matching, stopped E without a velocity endpoint, fitting-only median role sets, zero and partial/no-exit cases, unchanged pair denominators.
- [x] Implement compact per-ID atomic counts, exact median records, per-ID audit/digests and parent reconciliation using existing qualification helpers. No velocity filtering.
- [x] GREEN: synthetic reconciliation; pilot then full source cache with all guards, hashes and input identities checked.

### Task V3: nested evaluation, reusable candidates and reporting

Files: create `markov_velocity_cv.py`, `run_markov_velocity.py`, `markov_velocity_report.py` in the modelling package; create `configs/markov_m1_vcat.json` and focused tests.

- [x] RED: all 44 lag/lambda candidates share identical held-out cases, correct tie rule, outer/inner-ID separation, location-marginal scores, lambda=1 comparisons and complete all-U exports.
- [x] Implement the original nested folds, compact per-fit candidate scoring, selected and no-shrink outer forecasts, per-cell/velocity support, fitted-operator export and fixed-fit paired held-ID intervals. Save all choices, thresholds, fitting IDs and source-code identities.
- [x] Run a deterministic small engineering pilot then the full predeclared comparison; profile before scaling. Produce one English REPORT with 7/30-day scores, conditional coverage/size/zeros/U, comparisons and limitations. If a map is produced, select the cell/velocity example using fitting support only and use matched held-out velocity groups.
- [x] Final development candidate uses fixed-candidate outer-OOF selection followed by an unscored development refit. No final-test claim and no seasonal/continuous extension.

### Task V4: independent audit and delivery

- [x] One fresh whole-change review, re-grade findings and one test-first repair pass for important issues.
- [x] Independently reproduce selected source pair/count examples, lambda=1 degeneration, saved forecasts and grouped S; reconcile all source/contract identities.
- [x] Run focused modelling, architecture and synthetic preparation tests; no broad test discovery that opens final-test files. Update this guide and the existing execution ledger in place with actual evidence. Do not publish or overwrite historical runs.

### Verified M1vcat outcome and review checkpoint (2026-10-27)

Full input: `markov_vcat_input_20261026T155040_667626Z`. Formal comparison: `markov_vcat_cv_20261026T155955_651594Z`. The comparison completed 20 inner fits and five outer refits in 1,375.8 seconds, with 5.25 GB peak RSS. The original 7/30-day R denominators remain 303,288 pairs/385 IDs and 268,998 pairs/337 IDs. Parent source keys, reasons and position-only counts are unchanged.

| Horizon | Model | Outer held-ID S | Nominal-90% region hit | Mean region cells |
| --- | --- | ---: | ---: | ---: |
| 7 days | M1-selected | 0.927354 | 89.54% | 19.92 |
| 7 days | M1vcat-raw | 0.921776 | 92.22% | 20.80 |
| 7 days | M1vcat-selected | 0.921873 | 92.12% | 20.79 |
| 30 days | M1-selected | 0.985785 | 87.35% | 96.23 |
| 30 days | M1vcat-raw | 0.985275 | 89.78% | 102.91 |
| 30 days | M1vcat-selected | 0.985249 | 89.62% | 101.77 |

The selected categorical procedure lowers S in every outer fold at both horizons. Its pooled S differences from M1 are -0.005481 at 7 days and -0.000536 at 30 days. Conditional paired-ID 95% intervals are [-0.006672,-0.004366] and [-0.000927,-0.000257]. These fixed-fit intervals omit refitting, selection and repeated-research uncertainty. The 30-day gain is small. At the same inner-selected lag, removing velocity conditioning gives S=0.928231/0.985785, so the result is not explained solely by choosing a different lag.

Coverage improves with a slightly larger footprint, approximately +4.3%/+5.8% more cells. This does not demonstrate a tighter search region or exact calibration. Common-case spatial Energy also declines, from 124.57 to 117.51 km at 7 days and 318.50 to 311.53 km at 30 days; those are distribution scores, not mean endpoint distances. Spatial support is 303,288/263,137 pairs. Exact positive U remains excluded from formal spatial scoring, including tiny masses; it remains in primary S. Zero-probability outcomes persist: 0.02473%/0.15390% for selected M1vcat. Raw infinite log loss is not repaired with an unapproved floor.

The raw and selected categorical versions are not clearly separated: selected-minus-raw intervals include zero at both horizons. Raw classification has slightly lower 7-day S; smoothing has slightly lower 30-day S. Retain both. This comparison supports useful categorical velocity information under the present historical query, without establishing optimal binning or continuous-velocity learning.

Full-development candidates selected from fixed-candidate outer-OOF scores and then refitted:

| Forecast horizon | Primary lag | Lambda | Supported-row mixture | Exact propagation |
| --- | ---: | ---: | --- | --- |
| 7 days | 5 days | 0.3 | 70% local velocity law + 30% cell-pooled law | T5 T2 |
| 30 days | 7 days | 0.1 | 90% local velocity law + 10% cell-pooled law | T7^4 T2 |

The shared development speed threshold is 0.21989463629325104 m/s. These particular refits are not independently scored; the table above evaluates the nested selection procedure, whose choices vary by outer fold.

Independent audit: 177 sealed files verified; all 26 threshold/ID roles reconciled; ten kernels independently re-estimated from atomic counts; all 16,696 saved forecast distributions and 324,486 score groups reproduced; all six bootstrap contrasts reproduced. Maximum probability/S differences are below 1e-15. Sixty spatial examples were independently checked. Both full-size SVGs were rendered and inspected; observed panels match the held-out origin cell and initial velocity class. The fitting-selected illustration is cell 44384/class 8 (NE, faster), not a selected best-performing validation case. Native-source audit verified all 3,224 development track checksums, all 26 median values and 90 source examples. Focused tests: 115 modelling + 10 architecture + 22 preparation = 147 passing. Canonical data and the contract are unchanged; no final-test trajectory was read.

Human-readable output: [method, tables and limitations](../results/runs/markov_vcat_cv_20261026T155955_651594Z/REPORT.md), [local review page and probability maps](../results/runs/markov_vcat_cv_20261026T155955_651594Z/review.html). Audit evidence: [saved-artifact audit](../provenance/reviews/markov_vcat_cv_20261026T155955_651594Z_independent_audit.json), [native-source audit](../provenance/reviews/markov_vcat_input_20261026T155040_667626Z_source_audit.json).

**Checkpoint:** M1vcat is implemented and the bounded development comparison is complete. Review these results before approving another model. Seasonal, continuous-velocity, regime-specific, grounding and 365-day validation remain separate stages. No Git publication was performed.

## Completed stage: bounded M1 diagnosis and one lag optimisation (2026-10-25)

The user authorised implementation, initial diagnosis and one optimisation before reviewing additional features. This was the execution plan for that completed stage, using `superpowers:executing-plans` inline with test-first steps and one fresh whole-change code review; prior fixed-prototype evidence below remains unchanged.

**Goal:** locate the development-only onset of daily-kernel forecast bias, screen coarse-state/lag consistency and evaluate one bounded lag-selection procedure. Do not attempt to make this benchmark a complete ocean simulator.

**Spec and constraints:** Data Contract v1.0 (SHA `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`) and the user-approved diagnosis sequence. Retain R/D/grid, pooled scenario, all eligible hourly starts, exact timestamps, stopped first-exit target, separate E/U, existing whole-ID folds and Brier/S primary metric. No canonical changes, added predictors, new cleaning, final-test reads, Git commit/push/merge or annual/seasonal/grounding claim. Work locally on the existing `codex/markov-m1` branch; do not duplicate the dataset.

**Bounded choices made for this execution:** diagnose days 1/2/3/5/7/30; candidate lags 1/3/5/7 with independently fitted exact remainder kernels (2 days is needed). Select each of 7 and 30 days independently using pair-weighted S on inner held-out IDs; no cross-horizon objective is invented. Ties within 1e-12 retain the shortest lag. Outer evaluation scores the selection procedure and all fixed candidates on unchanged eligible cases. Full-development candidates may be selected from fixed-candidate outer-OOF terms and refitted, but are not independently scored final-test models. These are the best of four tried lags, not globally optimal models.

**Diagnostic cohorts:** retain unrestricted qualified R counts at each horizon for the main leaderboard. Separately intersect source keys across all six horizons to obtain a fixed 30-day-qualified R-start cohort; fit direct B1/B2 references on its fitting IDs and score all six horizons on identical held-out starts. This retrospective cohort diagnoses propagation and cannot establish skill for censored releases. Build a separate matched three-day D-start cohort with phase 0->1, 1->2, 2->3, direct 0->2 and 0->3 counts. Absorbed E remains E at every later phase, even after observed re-entry. Phase-specific versus pooled-step compositions screen Chapman-Kolmogorov inconsistency; cohort filtering, finite support and heterogeneity prevent treating a discrepancy as proof of physical non-Markovianity.

**Scores and interpretation:** preserve all-case S and existing exact-U=0 spatial scoring. Show centre bias, RMS spread and tiny-tail mass as labelled descriptive, known-in-domain-mass-conditioned diagnostics with E/U disclosed; they do not replace proper scores or quietly relax spatial eligibility. Daily self-transition is endpoint occupancy, not proof of uninterrupted within-cell residence. Preserve independent-ID support, candidate/exclusion accounting and fitting-ID-only weights. Existing linear/quadratic scores do not modify frequency estimation.

### D1: expanded source-qualified input cache

Files: new `src/data3001/modelling/markov_diagnostic_inputs.py`; new synthetic `tests/test_modelling_markov_diagnostics.py`; existing qualification helpers reused unchanged.

- [x] RED: synthetic exit/re-entry remains E in later phases; missing intermediate hours cannot enter matched cohorts; differing horizon eligibility yields a source-key intersection, not row-position alignment; every phase and horizon conserves eligible counts.
- [x] Implement `matched_release_counts(ledgers)` and `controlled_counts(stopped_by_day, in_R)` plus guarded streaming of D lags 1/2/3/5/7 and R horizons 1/2/3/5/7/30. Preserve per-ID reasons, secondary predicates, traceable labels and support/dominant-ID inputs.
- [x] Pilot on deterministic development IDs, then prepare the full cache if checks pass. Require exact agreement of daily D counts and 7/30 R counts with `markov_input_20261025T095949_830292Z`; source/data/contract hashes unchanged and final-test reads zero.

### D2: reusable scoring and bounded selection

Files: new `src/data3001/modelling/markov_diagnostics.py` and `run_markov_diagnostics.py`; narrow extraction in `run_markov.py` for shared score calculation; new tests. Add `configs/markov_m1_diagnostics.json` without altering the frozen prototype config.

- [x] RED: exact remainders, unknown rows/absorption, hand-calculated multistep scores, inner fitting/validation/outer-ID separation, per-horizon selection/ties, unchanged held-out denominators and missing-support penalties.
- [x] Extract `score_forecast` and common-case tagging without changing old `evaluate_fold` outputs. Implement pure kernel fitting, lag forecasts and candidate S tables. Existing categorical/spatial algebra remains authoritative.
- [x] Retain all six diagnostic horizons and all fixed/selected outer forecasts, plus inner choices and support. Use the existing fold maps and deterministic seeds. Selection never reads outer labels or final test; diagnostics never feed future observations back into a forecast.

### D3: initial diagnosis then one lag-comparison run

- [x] Evaluate daily versus direct predictions on matched starts and compute phase-composition diagnostics, per-cell/ID support and exclusions. Independently reproduce the frozen daily prototype on unchanged 7/30 cases.
- [x] Inspect the diagnostic outputs before launching the predeclared four-lag nested comparison; if a data/code defect appears, repair and test it first. Do not add candidates in response to held-out scores.
- [x] Evaluate one nested selection procedure separately at each target horizon, with per-horizon fixed-candidate tables and conditional paired whole-ID bootstrap intervals. Save final development-only candidate operators and selected-lag metadata without claiming final-test accuracy.

### D4: human-readable delivery and review

Files: new `src/data3001/modelling/markov_diagnostic_report.py`; no competing live plan or overwritten sealed outputs.

- [x] Produce one English combined diagnosis/optimisation report: where deviation is first measured, direct/composed differences, selected lags by fold, before/after S, probability-region coverage/size, mass failures and limitations. Use shared-scale B2/daily/selected/observed maps and one bias-over-horizon chart.
- [x] Fresh code review after source implementation; one test-first fix pass if needed. Focus on source-key alignment, E after re-entry, exact remainder timing, nested-ID isolation, and empty/all-U outputs. Independently recompute real forecasts/choices/scores, verify receipts and render charts.
- [x] Run focused modelling, architecture and synthetic preparation tests; update this guide in place with actual runs/results and a bounded recommendation for the next feature discussion. No publication or automatic feature change.

### Verified outcome and feature-review checkpoint

This one optimisation is complete. It does not establish complete M1/year-scale skill, and no feature was automatically added. The next decision belongs to the user: review one compact current-motion state (velocity/direction) before any further modelling. Do not continue an open-ended lag search or add weather/regime/seasonal fields merely to make the maps look sharper.

Verified runs:
- Expanded preparation: `markov_diagnostic_input_20261025T113812_255111Z`; 3,224 development IDs / 33,935,812 retained rows. 2,103,457 lag-count groups, 268,998 matched starts from 337 IDs. Preparation 517.9 seconds, peak RSS 1,902,936,064 bytes. Daily D and 7/30 R counts exactly reproduce the original cache; all phase/horizon and secondary denominators reconcile. Final-test reads zero; canonical rows/fields/values unchanged.
- Initial diagnosis: `markov_diagnosis_20261025T114721_490747Z`; 240,664 score groups over five original folds, 30.5 seconds. No canonical trajectory reads during scoring.
- Optimisation: `markov_lag_cv_20261025T114838_137131Z`; original outer-five/inner-four ID maps; 20 inner fits and five outer refits, 29.6 seconds. The complete original fixed daily/control scores were reproduced before completion. No final-test access or canonical change.
- Human-facing [combined report](../results/runs/markov_lag_cv_20261025T114838_137131Z/REPORT.md), [visual review](../results/runs/markov_lag_cv_20261025T114838_137131Z/review.html) and [independent audit](../provenance/reviews/markov_lag_cv_20261025T114838_137131Z_independent_audit.json).

**Where deviation begins:** on the same 30-day-qualified starts, daily M1 versus direct B2 centre differences are small at day 1 and grow with horizon. Pair-weighted mean distances from predicted to observed group centres: day 1, 9.56 vs 8.66 km; day 3, 24.77 vs 20.39; day 7, 59.84 vs 43.48; day 30, 193.37 vs 141.75. These are descriptive ECEF grid-centre comparisons, not individual RMSE or causal evidence. Daily M1's day-30 RMS spread is 472.52 km versus observed 509.51 km: a blanket over-dispersion explanation is inadequate. No single discrete failure day was established.

The matched three-day screen has 310,556 R starts from 388 IDs. Direct two/three-day S is 0.757813/0.834799; phase-composed is 0.760698/0.838979; pooled-composed is 0.760664/0.838967. Phase-specific and pooled compositions are very similar, so phase pooling alone does not explain the gap in this screen. Mean total variation from direct is about 0.077 / 0.126 at 2 / 3 days. These exploratory discrepancies support testing time-scale/state adequacy, not a proof of physical non-Markovianity.

| Days | B2 S | Daily M1 S | Nested selected M1 S | Daily -> selected nominal-90% hits | Daily -> selected mean region cells |
|---|---:|---:|---:|---|---|
| 7 | 0.929001 | 0.932844 | 0.927354 | 89.03% -> 89.54% | 21.77 -> 19.92 |
| 30 | 0.994751 | 0.988099 | 0.985785 | 83.37% -> 87.35% | 95.91 -> 96.23 |

Full-development candidate selection is **lag 5 for day 7** (`P5 @ P2`) and **lag 7 for day 30** (`P7^4 @ P2`). Four of five outer folds select each of these; fold 1 selects lag 3 / lag 5. The table evaluates the nested selection procedure, not the final all-development refit. The final candidate is the best of four tried lags by the declared per-horizon criterion, not globally optimal or independently final-tested.

Selected-minus-daily S is -0.005490 / -0.002313 at 7 / 30 days, with conditional paired-ID 95% intervals [-0.007855, -0.003573] / [-0.003565, -0.001196]. Selected-minus-B2 at day 7 is -0.001647, interval [-0.003133, 0.000373], so a reliable advantage over B2 is not established there. The day-30 comparison is -0.008965, interval [-0.010729, -0.007091]. Intervals condition on saved fits/choices and are exploratory, without refitting/selection/multiplicity uncertainty.

On the original eligible cases, mean centre bias falls from 57.55 to 43.44 km at 7 days and 193.37 to 151.97 km at 30 days; descriptive width moves closer to observed. At the fitting-selected illustration cell 44744/fold0, centre distances fall 250.47 -> 118.31 km and 379.74 -> 119.82 km. This is a useful local illustration, not a replacement for the all-case scores. Day-7 Energy improves from 128.84 to 124.57 km but remains slightly above B2's 123.91 km.

Remaining limitations: selected day-30 nominal-90% regions cover 87.35%, below their mean issued mass of 90.13%; raw zero-probability failures persist (0.032% / 0.154% at 7 / 30 days). Formal common day-30 spatial scores remain NA under the unchanged exact-U=0 rule. Selected day-30 mean U is about 1.13e-8, maximum 8.39e-7; descriptive conditioning must not be mislabelled as formal complete-distribution scoring. No observed eligible exit event supports exit calibration. Year, seasons, drogue-specific and grounding outcomes remain unvalidated.

Final independent audit verified 889 sealed files, all 30 operators, 25 ID-role records, every inner/final lag choice, 2,920 forecasts and 175,032 score groups, all six paired-ID intervals and descriptive centres/spreads. Maximum errors: kernels <8e-16, forecasts <7e-16, S <3e-16, centre/spread <3e-12 km. One fresh code review identified three edge failures (all-absorbed phase, missing illustrative held-out support, unavailable SVG coordinates); all were reproduced RED and fixed in one pass. Maps/chart rendered and visually checked. Final focused verification: 98 modelling + 10 architecture + 22 synthetic preparation tests = 130 passing. Code and results remain local; no Git publication.

## Completed stage: fixed one-day M1 prototype evaluated (2026-10-25)

> **For agentic workers:** implement the reviewed specification task by task using `superpowers:executing-plans`. This is the single current stage guide; the completed baseline sections below retain historical scope and evidence. They do not override this section or Data Contract v1.0.

**Goal:** build and validate a reproducible 1-degree, annual-pooled, position-only Markov transport prototype before selecting a lag or adding seasonal, regime or environmental conditioning.

**Architecture:** reuse the existing source-keyed trajectory qualifications and separate stopped labels. Cache per-ID transition counts, fit a row-stochastic operator from fitting IDs only, and propagate probability vectors without reading future held-out positions. Evaluate against newly fitted, target-matched stopped B0/B1/B2 controls.

**Tech stack:** existing Python 3.12 environment, NumPy, pandas, PyArrow, Shapely/PyProj and SciPy sparse operators. The already installed SciPy is now explicitly declared in `pyproject.toml`; no dependency installation was required.

**Scientific authority:** [Data Contract v1.0](contract/data_contract_v1.0.xlsx), SHA-256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`. The user retains experimental-definition, feature and interpretation review. The latest instruction authorises implementing the distance-sensitive scoring addition and entering formal modelling. The assistant is implementing the fixed one-day prototype on local branch `codex/markov-m1`; model-fit status and actual runs are recorded below after verification.

### Confirmed definitions

| Item | Definition |
|---|---|
| Input | `per-drifter-cleaned-20261017-v7`: 3,224 development IDs; 517 final-test IDs remain locked. |
| Data protection | No canonical row/value/column changes; all 62 stored fields remain. Existing data cleaning is reused. |
| Release R | Frozen Southern Gulf Stream polygon, not its clipping rectangle. Actual saved polygon bounds are 81-73 W, 30-35.5 N. |
| Transport D | Frozen 81-8 W, 20-55 N rectangle; actual geometry includes its boundary and covers R. |
| Grid | Existing globally anchored, half-open 1-degree cell IDs and frozen state index. A point, not its cell centre, determines D membership. |
| Scenario | Annual pooling of departure seasons and pooled historical drogue states. Unknown/switching drogue intervals are not excluded solely for that reason. |
| Predictive state | Current cell only. ID, time, coordinates, source keys and existing qualifications support sampling/audit; velocity, SST, wind, loss dates and eventual death metadata are not predictors. |
| Origins and weights | Every eligible hourly D origin from fitting IDs; equal eligible-pair weights. Include D-only IDs. Keep observed self-transitions. |
| Pair timing | Timestamp arithmetic and exact matching, tolerance zero. Do not use row offsets or fabricate missing targets. |
| Path use | Intermediate hourly positions determine path completeness and observed first exit. They are not additional predictors of the release's future location. Each eligible hour can also start another training pair. |
| Target | Stopped process: the first QC-valid observed exit from D is absorbing for that release, including if the trajectory later returns. This is not unrestricted endpoint occupancy. |
| Missing observations | Keep existing reason predicates. Missing paths/outcomes are not observed OUTSIDE or grounding outcomes and do not supply fabricated transition counts. |
| Unsupported model row | Transfer its probability to unresolved support U; never invent a persistence row. U is algorithmic support uncertainty, not an observed physical destination. |
| Validation | Reuse the existing outer-five/inner-four whole-ID assignments. All counts, priors and any fitted choices exclude the relevant held-out IDs. |
| Main evaluation | Complete-distribution Brier plus all-case failure-penalised S, raw log loss/bounds, zero failures, unresolved mass, region coverage/concentration and independent-ID support. Preserve all eligible evaluation cases. |
| Long-term obligation | Audit 90/180/365-day development support early. Initial 7/30-day success does not establish year-scale skill. |

### First runnable scope and remaining decisions

The first runnable prototype fixes **lag = 1 day** and **destination-prior mixing epsilon = 0**. It estimates raw transition frequencies and produces exact 7/30-day stopped forecasts. There is no hyperparameter selection in this fixed prototype. The machine-readable settings are [markov_m1.json](../configs/markov_m1.json); preserve the separate human review of later feature or selection-rule changes.

After the prototype passes semantic and real-data checks, compare lags **1, 3, 5 and 7 days**, using explicitly estimated remainder kernels and the same evaluation cases. Nested selection then becomes necessary: choose settings on inner held-out predictions and evaluate the selection procedure on outer held-out IDs. Keep per-horizon leaderboards. **The cross-horizon selection rule is not frozen:** equal mean S at 7/30 days remains a proposal, not an approved rule. Do not announce an optimal lag before that decision.

The user requested linear plus quadratic spatial penalties. This implementation preserves the contract's Brier/S primary scores and adds two separately reported spatial components: `ES(F,y)` in km and `||mean(F)-y||^2` in km squared. The auxiliary reference `ES/100 + squared_mean_error/10000` uses a declared 100-km scale and equal weights as an engineering reference, not a claimed optimal scale or a newly approved primary selection criterion. Under finite Euclidean spatial moments this is a positive combination of a strictly proper energy score and a proper mean score. Direct expected `distance + squared_distance` is not used: it can reward a false central point instead of two real transport branches. Brier is probability-sensitive, not zero-one loss; adding a quadratic score does not guarantee better convergence of a count-estimated operator.

Use WGS84 ECEF coordinates of fixed cell centres and Euclidean chord distances in km, not raw-degree distances or claimed great-circle distances. This is a declared coarse-grid scoring representation, not a change to the historical within-cell release prior or physical shoreline geometry. Spatial scores condition on observed in-D outcomes and the forecast's in-D distribution only when the forecast is complete (`u=0`) and has positive in-D mass. OUTSIDE and unresolved have no fictitious coordinates. Publish both individual availability and the identical common spatial case subset across B0/B1/B2/M1. Missing spatial scores remain visible; they are not dropped from primary scoring. Quadratic mean error cannot identify different spreads at the same mean. Weights and scale are not tuned against the same metric or used to announce a best lag.

Optional epsilon values `{0, 0.0001, 0.001, 0.01}`, seasonal operators, regime partitioning, alternative weights and environmental state augmentation remain later declared comparisons. No new universal minimum-ID threshold or donor fallback is introduced.

### Mathematical and interface contract

For eligible D-origin stopped pairs of lag tau, count `N_tau[i,j]` over the fitting IDs. On a supported row, `P_tau[i,j] = N_tau[i,j] / sum_j N_tau[i,j]`. Include observed geographic self-transitions and observed first exits. On an unsupported geographic row, set `P_tau[i,U] = 1`. Set `P_tau[E,E] = P_tau[U,U] = 1`; E and U must retain separate labels and semantics.

For release cell i use `p0 = e_i`. Propagate `p_next = p_current @ P_tau`. For `h = q*tau + r`, apply q full steps and, if r is nonzero, an independently estimated r-day operator. Do not substitute fractional matrix powers, round the horizon, or read the held-out trajectory between steps. Unit cell mass represents the historical eligible within-cell release prior, not a uniform subcell or exact-point forecast.

Implemented focused files:

| File | Responsibility and interface |
|---|---|
| `src/data3001/modelling/markov.py` | Pure `fit_operator(counts, fitting_ids, state_cells, lag_days)` and `propagate(operator, origin_cell, horizon_days, remainder=None)`; explicit ordered state index and physical/U mass accounting. |
| `src/data3001/modelling/markov_scoring.py` | Preserve existing categorical scores; compute conditional linear Energy, squared mean error and the explicitly labelled auxiliary reference. |
| `src/data3001/modelling/markov_inputs.py` | `collect_inputs(paths, run, development_ids, durations)`: stream tracks via existing qualified `load_track/origin_indices/generate`, save per-ID counts, R labels, reason/support summaries and source-keyed examples. No relabelling. |
| `src/data3001/modelling/run_markov.py` | Guarded configuration, small-batch profiling, fixed-lag outer evaluation, matched controls, model/output sealing and English report. Reuse existing score/fold/run helpers. |
| `configs/markov_m1.json` | Reviewed machine-readable settings; created only with the implementation, bound into each run's receipt. |
| `tests/test_modelling_markov.py` | Independent numerical/state/fold fixtures; no real final-test access. |
| `tests/test_modelling_markov_inputs.py` | Synthetic label reconciliation, exit/re-entry, missing paths and source-key conservation. |

### Task 1: qualified input and count-cache adapter

- [x] Write tests first and confirm assertion failures for missing functionality. Reconcile generated stopped labels with the existing helper on identical synthetic inputs, not a rewritten eligibility rule.
- [x] Test a complete exit/re-entry path: endpoint returns to a geographic cell, stopped remains E. A missing hour before a putative exit must not establish exit. A known exit before subsequent termination remains a valid stopped outcome. Test actual point membership and boundary-only cells.
- [x] Implement `collect_inputs` using `PreparedSource(allow_test=False)` and the existing qualification adapter. Preserve `(id, source_obs, time)` identities and all candidate reasons; use only eligible pairs as transition counts.
- [x] Stream a deterministic small development-ID batch first. Record actual elapsed time, peak memory and output bytes. No arbitrary random ID reseeding or test access. Scale only after checking reconciliations and the resource profile.
- [x] Cache per-ID one-day D counts and R-origin 7/30-day stopped evaluation/count tables. Audit longer-horizon support without requiring long survival for one-day learning. Save compact trace examples and ledger checksums rather than duplicating all hourly rows across model settings.
- [x] Verify `candidate = eligible + all primary exclusion reasons` for each ID/population/duration and reconcile cached source keys/counts against generated records. Keep secondary predicates separately; do not count them as disjoint exclusions.

### Task 2: fixed one-day operator and exact propagation

- [x] Write independent fixtures before implementation. Counts A-to-A=2, A-to-B=1, A-to-E=1 must yield probabilities 0.5/0.25/0.25. Holding out an ID removes all its contributions. An unobserved B row goes entirely to U.
- [x] Independently test a complete two-cell matrix `[[0.7,0.3],[0.2,0.8]]`: A release yields `[0.7,0.3]` after one step and `[0.55,0.45]` after two. Separately test absorbing E/U, legitimate self-transitions, unknown origin cells, nonnegative values and total mass one.
- [x] Implement the pure fitting/propagation interfaces. Store sparse operators plus stable global-cell-to-row mapping. Do not confuse raw unobserved destination zeros with an entirely unsupported origin row.
- [x] Verify 7/30-day forecasts use exactly 7/30 daily steps; no intermediate validation position is read. Freeze selected example cells using fitting support, never their held-out score or visual appeal.
- [x] Run focused existing modelling regressions and new synthetic Markov tests. Numerical correctness is a gate for real-data fitting, not evidence of predictive skill.

### Task 3: first real-data forecasts and whole-ID evaluation

- [x] First check one existing outer fold end to end: all other development IDs supply D transition learning; the held-out fold supplies R release evaluation only. Test-ID reads must be zero.
- [x] Fit stopped B0/B1/B2 controls from R-origin fitting cases at each exact horizon, using the same target/scenario as M1. Old endpoint scores remain a separate historical result. Describe that M1 also uses D-only downstream information; a gain cannot be attributed solely to iteration.
- [x] Once the fold check passes, evaluate the fixed one-day configuration over all five original outer folds. No inner optimisation is needed for a genuinely fixed configuration; do not label its evaluation as lag-selected nested CV.
- [x] Report each model on all identical eligible stopped cases at each horizon, including unsupported forecast cases. Show complete Brier and all-case S with their denominators, log-loss bounds/raw infinities, zero failures, mean/max U and OUTSIDE, and per-cell/ID support. Do not discard failures or turn S into percentage accuracy.
- [x] Report nominal probability-region mass, coverage and wet area/cell count. If known mass cannot form the requested region, label it unavailable. OUTSIDE/U are displayed separately; any domain-conditional map must say so.
- [x] Use 200 paired whole-ID validation resamples for fixed-fit uncertainty, labelled explicitly as conditional on fitted operators. Kernel-refit uncertainty requires an additional whole-fitting-ID resampling analysis; the former cannot substitute for the latter.
- [ ] Compare direct 2-day/3-day stopped estimates with one-day composition on declared common diagnostic cohorts. Audit retained incoming direction, subcell position and residence information without adding predictors. Separate availability/cohort differences from evidence against the Markov approximation.

### Task 4: human review and extension checkpoint

- [x] Produce one English `REPORT.md` per immutable run with formulas, exact configuration, support, direct-control comparison, 7/30-day prediction-versus-held-out maps, uncertainty scope, failures and proposed next action. It is evidence for this run, not a competing live plan.
- [x] Seal data/contract/geometry/fold/code/environment identities and output hashes with the existing run helpers; keep receipts/progress under provenance and numerical products under results.
- [x] Hand over the operator/state index and a reproducible forecast example. Passing mathematics or a narrow map alone is not a successful accuracy claim.
- [ ] Obtain review of the cross-horizon lag-selection rule and the concrete spatial-score protocol before the multi-lag selection extension. That extension estimates required 1-6-day remainder kernels and 2*tau/3*tau memory references without changing primary grid/eligibility.
- [x] Do not declare M1 complete merely after a fixed one-day prototype. Distinguish prototype implementation, fixed-lag validation, multi-lag selection and long-horizon evidence. Seasonal/regime/object-specific/grounding performance remains unvalidated.

**Verification commands:** `.venv/bin/python -B -m unittest discover -s tests -p 'test_modelling*.py' -v`, `.venv/bin/python -B -m unittest discover -s tests -p 'test_architecture.py' -v` and the synthetic `test_preparation.py` suite. Inspect targeted scientific regressions for side effects before running them. Do not run indiscriminate discovery: some existing data-release tests intentionally open final-test files. The Markov entry point is `python -B -m data3001.modelling.run_markov`.

**Execution boundary:** implement and test the fixed one-day prototype, profile a deterministic development-only pilot, then prepare/fold-evaluate full development data if the pilot checks pass. No canonical changes, final-test access, lag selection, new environmental predictor, main-criterion replacement, Git commit/push or main merge is included. Completed baseline work was already published with commit subject `baseline model Completed`; accepted runs below remain unchanged.

### Verified prototype delivery and interpretation

The fixed one-day prototype is implemented and evaluated; the broader M1 lag-selection and memory-diagnostic programme is **not complete**. The checklist above defines both delivered prototype work and extension obligations. Direct 2/3-day versus composed memory diagnostics, lag comparison, full-development final refitting and seasonal/regime modelling remain outstanding. The five saved outer operators support reproducible held-out examples; they are not a selected final production fit.

- Corrected input: `markov_input_20261025T095949_830292Z`. Read all 3,224 development IDs and 33,935,812 retained rows; 25,221,906 D hourly origins supply 24,991,553 eligible daily stopped pairs. Preparation took 139.7 seconds, peak RSS 734,789,632 bytes. A deterministic 20-ID pilot preceded it.
- Evaluation: `markov_m1_1d_20261025T100248_328450Z`. Five original whole-ID outer folds; 1,460 saved forecast distributions and 87,516 score groups. Evaluation took 7.1 seconds, peak RSS 572,882,944 bytes. No final-test trajectory was read; no canonical input was modified.
- Human-facing [method, evidence and results report](../results/runs/markov_m1_1d_20261025T100248_328450Z/REPORT.md), [probability-map review](../results/runs/markov_m1_1d_20261025T100248_328450Z/review.html), and [independent numerical audit](../provenance/reviews/markov_m1_1d_20261025T100248_328450Z_independent_audit.json).
- A fresh code review identified floating upper-bound roundoff, missing all-U export rows and absent compact secondary-predicate audit. All three were reproduced by failing tests and repaired. The corrected cache has exactly the same transition/release counts and every-ID label digest as its first full predecessor; 48,610 non-disjoint secondary/path audit groups were added. The earlier sealed cache remains historical evidence and is not the evaluation parent.
- Independent artifact recomputation checked 426 sealed files, all five operators and ID exclusions, every saved forecast and S score, matching held-out denominators and independently calculated WGS84 ECEF spatial scores. Maximum discrepancies: transition probabilities 7.8e-16, forecasts 6.9e-16, S 2.3e-16 and Energy 1.8e-12 km. These numerical checks establish implementation consistency, not general predictive accuracy. All six paired whole-ID bootstrap contrasts were also independently reproduced. Final targeted verification: 87 modelling, 10 architecture and 22 synthetic preparation tests passed (119 total); no final-test files were opened by these suites.

| Days | Eligible stopped pairs / IDs | B1 S | B2 S | M1 S | M1 nominal-90% region hit rate |
|---|---|---:|---:|---:|---:|
| 7 | 303,288 / 385 | 0.979073 | 0.929001 | 0.932844 | 89.03% |
| 30 | 268,998 / 337 | 0.991465 | 0.994751 | 0.988099 | 83.37% |

Lower S is better and is not percentage accuracy. M1 is worse than B2 at 7 days (delta +0.003844; conditional paired-ID 95% interval [0.000619, 0.007649]) and better at 30 days (delta -0.006652; interval [-0.008507, -0.004700]). These intervals condition on fixed fits and are exploratory. M1 uses D-origin downstream information in addition to R, so this comparison does not isolate iteration as the cause of any improvement.

At 7 days all models share 303,288 spatial cases. M1 Energy is 128.84 km versus B2 123.91 km; the corresponding squared mean errors are 51,642.38 versus 48,463.83 km squared, and auxiliary references are 6.452663 versus 6.085461. The distance-sensitive metrics therefore also do not establish a 7-day improvement over B2.

At 30 days M1 has positive U in every issued release-cell forecast, ranging from 2.36e-27 to 6.19e-12, with pair-weighted mean 1.56e-13. This is tiny support mass propagated through low-probability paths, not evidence that most of the forecast is unknown. The declared **exact U=0** spatial-completeness rule nevertheless makes the common 30-day spatial subset empty. Spatial metrics remain NA for this comparison. No small U was dropped or renormalised, and no tolerance was tuned after seeing these results. Any tolerance-aware or partial-support spatial protocol requires a separately documented decision.

M1 reduces zero-probability observed destinations to 0.0073% / 0.1539% at 7 / 30 days, but raw log-loss upper scores remain infinite. Nominal 90% regions cover 89.03% / 83.37%; mean issued mass is 90.52% / 90.12%, so 30-day undercoverage remains. No eligible observed exits occur at either horizon; positive exit-event calibration is not established. The 365-day pooled support audit contains 91,265 pairs from 106 IDs, not a validated annual forecast.

The maps use origin cell 44744 in outer fold 0, selected solely by fitting-ID support, with shared colour scales and matching held-out observations. They have been rendered and visually checked. Final-test, year-scale, seasonal, object-specific and grounding skill are unvalidated. Next: review these results and the primary cross-horizon selection rule; then complete declared memory diagnostics and compare lags before adding new predictors.


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
