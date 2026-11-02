# Step 2 — E4 Partial Drifter Contribution Weighting

**Version:** E4 v1, 30 October 2026. **Status: USER APPROVED — DEVELOPMENT, EXECUTION AND AUDIT AUTHORISED.**

The user confirmed this E4 v1 plan and authorised independent development, execution, audit and visual comparison. Compare beta = 0, 0.5 and 1, with original Fixed B2/B1 as a control and E3's evaluation target unchanged. Moderate long-record influence while retaining every qualified hourly pair. The definitions below are locked by this approval. This document is the single current E4 plan. It replaces the earlier conversational E4 suggestion of EqualID plus B1; that combined model is not included here. E3 and its sealed artifacts remain unchanged.

## 1. Question and scope

**Where Things End Up:** given an object already in a specified origin cell at a qualified prediction time, estimate its destination distribution after 7 or 30 days. A start is not restricted to first entry. Exact coordinates map to the existing 1-degree cell. The two horizons are direct estimates, not a daily propagation model or evidence for every intermediate duration.

**E4 question:** does partially reducing the influence of drifters with many local hourly pairs improve held-out probability prediction under the fixed E3 evaluation target, relative to both raw B2 and full EqualID, and how does it compare with Fixed B2/B1?

Only the local training contribution rule changes. Preserve all pairs, their integer multiplicities, and each ID's internal endpoint frequencies. There is no endpoint deduplication, one-record-per-ID sampling, tail deletion, new input feature, spatial borrowing, B1 reweighting, adaptive fusion weight, or partially weighted B1 fusion.

This is a regularisation-style sensitivity experiment on an empirical estimator. It adds neither observations nor independent prior information and is not a fully Bayesian inference procedure. Partial weighting changes the fitting population away from the equal-ID evaluation population: it is a finite-data bias/variance hypothesis, not an assertion that all beta values estimate exactly the same sampling target. Longer records are neither declared erroneous nor assumed proportionally more informative.

Keep the existing stopped target: first observed exit from D within the horizon is absorbing outcome E, even after re-entry. U denotes unavailable model support/bookkeeping, not a physical destination or grounding. Missing follow-up is not E. The drifter model remains a transport proxy; this experiment does not validate spill weathering, windage, physical diffusion or subcell dynamics.

## 2. Approved decision register

| Item | Proposal |
|---|---|
| New scientific mechanism | Power weighting of qualified pairs within each fitting ID/origin/horizon |
| Fixed beta values | Exactly 0, 0.5 and 1; three separate arms, no beta selection |
| Main candidate | PartialID, beta = 0.5 |
| Controls | B2, beta = 0; EqualID, beta = 1; original Fixed B2/B1 |
| Fixed tuning | a in {0, 0.05, ..., 1}, selected by inner E3-primary Brier |
| Primary evaluation | Within-ID eligible times, then IDs within cell, then cells equally |
| Metrics | Standard Brier primary; K90 and H90 always reported alongside it |
| Validation | Same five outer/four inner whole-ID groups as E3 |
| Main contrasts | PartialID minus each of B2, EqualID and Fixed, separately at 7/30 days |
| Uncertainty | E3's 5,000 paired positive whole-ID multiplier replicates; six-contrast Brier adjustment |
| Deliverable | Isolated experiment, reproducible controls, complete diagnostics and user-reviewed conclusion |
| Current permission | Independent development, bounded execution, audit and visual comparison |

Training beta does not change evaluation weights, inclusion rules, folds, outcome definitions or region levels. No model is selected using the outer results and then presented as independently validated.

## 3. Frozen inputs and isolation

Reuse cleaned release `per-drifter-cleaned-20261017-v7`, annual pooling, qualified R-origin hourly pairs, the frozen 1-degree origin/destination indexes, and direct 7/30-day horizons with exact existing pairing qualification.

- Contract: `docs/contract/data_contract_v1.0.xlsx`; expected SHA256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`.
- Counts: `results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet`.
- Folds: `results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv`.
- Development inventory: 3,224 IDs, including IDs with no qualified cases; 517 final-test IDs remain locked.
- Regression anchor: E3 primary `drifter_shrinkage_e3_20261030T074159_751985Z`, with its provenance and successful replay. S1/E1/E2 remain historical references under their own targets.

Before execution, verify source identities, count qualification, geometry and whole-ID memberships against the E3 allowlist. Recompute fitted quantities from qualified raw counts within each role; do not reuse historical forecasts or selected a as fitting inputs. Historical artifacts are available only for sealed-input checks and post-freeze regression. Do not read raw trajectories, regenerate pairs, or access final-test trajectories.

Preserve the integer `pair_count` field. Export fractional weights separately. Configuration must distinguish raw-cache provenance weighting from model fitting weights and evaluation weights; an old `equal_eligible_pairs` cache label must not silently control the primary score.

E3's evaluated totals provide an integrity expectation, not a reason to force matching scores: 37 origin cells at each horizon; 303,288 pairs/385 distinct IDs at 7 days and 268,998 pairs/337 IDs at 30 days. E3 had 4,451 and 3,974 ID-cell units respectively and full support on eligible cases. Reverify these from E4 inputs; investigate any mismatch before proceeding. Retain all 54 indexed origin cells in support reporting, including the 17 without E3 evaluation cases.

## 4. Training definition

For a given fitting-ID set T, origin i and horizon h, let n_idj be the integer count from drifter d to outcome j, where j includes D and E. Suppress T and h below and define:

`n_id = sum_j n_idj`, `r_idj = n_idj/n_id`, and `I_i = {d in T : n_id > 0}`.

Only positive local counts enter the calculation. The count is local to this origin and horizon, not an ID's entire lifetime, total R exposure, another fold, or another horizon.

For beta in {0, 0.5, 1}:

**Per-pair unnormalised weight:** `w_id(beta) = n_id^(-beta)`.

**Row normaliser:** `Z_i(beta) = sum_d n_id^(1-beta)`.

**Estimated transition probability:**

`P_beta(i,j) = [sum_d n_idj * n_id^(-beta)] / Z_i(beta)`

`             = sum_d s_id(beta) * r_idj`, where `s_id(beta) = n_id^(1-beta)/Z_i(beta)`.

Thus every hourly pair still contributes; the normalized weight of one pair is `n_id^(-beta)/Z_i(beta)`. A compressed ID/origin/destination row contributes `n_idj` times that amount. An ID's internal distribution r_idj is unchanged.

| Model label | Beta | Total local ID contribution before normalization |
|---|---:|---|
| B2 | 0 | n_id |
| PartialID | 0.5 | sqrt(n_id) |
| EqualID | 1 | 1 |

For 90 versus 10 pairs, the ID contribution ratios are 9:1, 3:1 and 1:1. For a mixed-endpoint example, let A have 60 outcomes at X and 30 at Y, and B have 10 at Y. Then P(X) is 0.6, 0.5 and 1/3, respectively. All 100 pairs remain represented.

This beta is the exponent above. It is not the linear mixing coefficient gamma from E3 v1; beta = 0.5 is generally not `(B2 + EqualID)/2`.

Apply the same weighting to E as to D outcomes. Supported rows must be finite, nonnegative and sum to one within absolute 1e-12. All three beta arms must have exactly B2's strictly positive support, positive-D-cell count, and zero-probability truth indicators. They may change E mass, Brier, rank order, K90 and H90. Empirical zeros remain zeros: this experiment cannot repair missing local destination support.

The estimator is a weighted-frequency calculation; no optimizer, epochs, neural network or new training loss is needed.

### Fixed B2/B1 control

Rebuild raw B1 from all qualified fitting-ID R-origin pairs, including the target origin:

`Q_B1(j) = sum_i,d n_idj / sum_i,d n_id`.

`P_Fixed(i,j;a) = (1-a)*P_B2(i,j) + a*Q_B1(j)`.

Choose one a per horizon/selection role, shared across supported origins, from exactly `{0,0.05,...,1}`. Minimize the pooled inner E3-primary Brier; ties within absolute 1e-12 select the smallest a. B1 and B2 are not reweighted in this control. The chosen a should reproduce E3 on identical roles, data and evaluation; reproduce it by fresh selection, not by hard-coding old values.

### Unsupported origins

All four models use the same raw-B2 fitting-support mask. For zero-support origins, issue no standard Brier or region score and no Fixed/B1 fallback. Record availability, counts, fractions and U/bookkeeping separately. Supported rows have U = 0. A supported forecast assigning zero probability to an observed destination is scored normally, not excluded or relabelled U.

## 5. Evaluation fixed to E3

Let m_id be an evaluation ID's eligible pair count in origin i, M_i the number of evaluable IDs in that cell, and C the set of evaluable origin cells. These are evaluation quantities, not fitting n_id or fitting ID counts.

For any per-case metric z:

1. Average z across all eligible hourly pairs within each evaluation ID/cell.
2. Average these ID means equally within the cell.
3. Average cell means equally across C.

An individual hourly pair therefore has primary weight `1/(|C| * M_i * m_id)`. Multiply by the integer multiplicity for compressed count rows. Keep these weights identical for all beta arms and every Fixed candidate. They do not depend on beta, predicted probability, endpoint popularity or whether a prediction succeeded.

Pool ID-cell records across inner groups or outer groups before the cell/ID aggregate. Do not average fold summary scores or substitute pair-weighted totals. Keep the fit assignment of each held-out ID; the same cell can receive different fitted rows in different outer folds.

This target remains a location-balanced, equal-ID evaluation proxy. It does not assert that actual spills occur uniformly across cells or that every observed ID represents all future objects. Different training rules are allowed to compete under this one fixed target; partial weighting does not silently amend it.

Retain E3's eligible/evaluable memberships and both raw and target-weighted availability reporting. Conditional diagnostics must use the fixed primary base weights before conditioning; do not silently re-equalize IDs after removing E outcomes. A completely unevaluable role is an error, not a zero loss.

Also report the original pair-weighted scores for the same new predictions as a labelled secondary sensitivity view. They never choose a, determine success, or replace the primary target. Disclose any ranking reversal.

## 6. Scores and regions

**Primary score:** standard unnormalised multiclass Brier,

`BS(p,y) = 1 + sum_{j in D plus E} p_j^2 - 2*p_y`.

Lower is better. It is not an accuracy percentage. Do not divide by state count or introduce a spatial/combined loss.

**Region:** sort strictly positive D-plus-E probabilities, take the shortest prefix reaching 0.90 within mass tolerance 1e-12, then include all positive cutoff ties within probability tolerance 1e-12. Keep the complete distribution, including mass outside the region. No truth-based tie breaking, tail truncation, probability floor, E removal or D-only renormalization.

- **K90:** number of geographic D cells in the region; E is not a geographic cell. Aggregate with the same primary weights. The mean need not be an integer or correspond to square kilometres.
- **H90:** weighted frequency with which the held-out stopped outcome belongs to that region. This is actual coverage, not necessarily 90%.
- Always report issued probability mass, E membership, predicted/observed E and availability/U alongside applicable conditional diagnostics.

## 7. Nested roles and parameter handling

Keep E3's five outer whole-ID groups. For each outer group k:

1. Hold out all IDs in k completely.
2. For each of the remaining four groups l, fit using IDs outside k and l; validate on l.
3. Recompute local counts, the three beta estimates, raw B1/B2 and support inside each fitting set.
4. Evaluate all three fixed beta arms and 21 Fixed candidates on the same inner cases. Pool ID-cell records and select only Fixed's a by the primary Brier.
5. Refit on the four outer-training groups and evaluate B2, PartialID, EqualID and the selected Fixed on outer k.
6. Save all results, including unfavourable ones. Do not select beta, substitute a model, or apply a post-hoc fallback using outer outcomes.

Inner scores for beta arms are audit/diagnostic records, not a beta-selection procedure. The scientific question is the prespecified PartialID comparison, not the out-of-sample performance of an automatically selected beta.

There are 26 fitting roles: 20 inner, five outer, one all-development refit. At the 25 validation roles, audit 24 candidate identities per horizon (three beta arms plus 21 Fixed candidates), totaling **1,200 role/horizon/identity evaluations**. Numerically identical identities, such as Fixed(a=0) and B2, may share calculation but retain labels and audit records. Four final reported models yield eight horizon/model summary rows.

Freeze/hash outer forecasts, masks, ID-cell scores, selected a and evaluation weights before all-development tuning. Then select an illustrative all-development a using the five base outer out-of-fold fits as in E3 and refit all four models on all development IDs. All-development maps are illustrations, not independently validated forecasts. This stage cannot change the outer freeze.

## 8. Prespecified contrasts and uncertainty

For each horizon, define PartialID minus each of B2, EqualID and Fixed for Brier, K90 and H90. Negative differences favour PartialID for Brier/K90; positive differences favour PartialID for H90. All other model pair comparisons are descriptive.

Reuse E3's uncertainty construction:

- 5,000 positive whole-ID multiplier replicates; seed 20261030; NumPy Generator PCG64; Exp(1) draws over the sorted complete development-ID inventory.
- One multiplier per ID in each replicate, shared across all its cells, horizons, metrics and models.
- Keep each within-ID score mean and fitted prediction fixed. Within each cell, form the multiplier-weighted ID mean, then average the same original cells equally.
- Save the ID inventory, draw identity/hash, replicate summaries and ordinary 95% percentile intervals; use linear interpolation for quantiles.

There are **six primary Brier contrasts**, not E3's four. The prespecified one-sided upper percentile for their Bonferroni-style conditional screen is `1 - 0.05/6 = 0.9916666666666667`. E3's 0.9875 must not be copied silently. This changes the comparison-count adjustment, not the scoring population or resampling method.

K90/H90 ordinary 95% intervals are descriptive, not multiplicity-adjusted non-inferiority tests. A joint favourable point pattern must not be promoted into a formal quality-non-inferiority claim. If a formal application non-inferiority study is needed, it needs a separately approved margin and testing design before execution, not a post-result reinterpretation.

These are conditional development screens, not exact inferential guarantees. They omit refitting variability, dependence from overlapping training sets and prior research adaptation; cross-ID common ocean conditions are not modelled by resampling. Do not present them as final-test confirmation, complete calibration evidence or Bayesian credible intervals.

## 9. Interpretation and acceptance

Let epsilon = 1e-12, and evaluate each horizon/reference separately.

| Outcome | Required interpretation |
|---|---|
| Engineering completion | Input identity, mathematical semantics, evaluation, independent audit and replay pass; predictive improvement is not required |
| No measurable Brier gain | Delta Brier >= -epsilon; distinguish a tie from deterioration |
| Point Brier gain | Delta Brier < -epsilon but adjusted upper bound is not < -epsilon |
| Conditional Brier support | Delta Brier and its adjusted upper bound are both < -epsilon, under the stated development assumptions |
| Useful intermediate weighting | PartialID improves Brier against both B2 and EqualID for that horizon; specify point-only versus conditional support for each comparison |
| Brier/application trade-off | Brier improves but hits fall or K90 grows; report the magnitudes and intervals, not an overall win |
| Descriptive joint benefit over Fixed | Delta Brier < -epsilon, Delta H90 >= -epsilon and Delta K90 < -epsilon at the point level; not proof of population non-inferiority |

The numerical epsilon is an arithmetic tolerance, not a practically acceptable loss margin. No scientific non-inferiority margin is silently introduced. Report absolute Brier changes, relative K90 changes and H90 percentage-point changes. Positive outcomes at 7 days do not imply positive outcomes at 30 days. Beating EqualID alone does not establish improvement over B2 or justify replacing Fixed.

Do not require K90 reduction for the probability-estimation experiment to be informative. Conversely, a smaller region with worse Brier or lower hits is not an unqualified improvement in Where Things End Up. If PartialID has no reliable advantage, retain the negative/inconclusive result. Do not add beta values, change the target, blend PartialID with B1 or move to Step 3 automatically. Retention and stage closure remain user decisions.

## 10. Diagnostics and figures

Export each fitting ID/origin/horizon's n_id, r_idj and the normalized contribution s_id for all three beta values. Include raw pair count, distinct-ID count and maximum ID contribution per origin. Show how record influence changes without treating these counts as an independent effective sample size.

Report per-origin and per-fold Brier/K90/H90 with explicit denominators, plus zero-truth probability frequency, positive destination counts, mean sum(p_j^2), mean p_y, support/availability and E/U. The three beta arms' zero-truth indicators and support must match exactly. Unseen local destinations remain an explicitly reported limitation.

Retain descriptive matched-budget hit curves at E3's fixed budgets `{1,5,10,20,50,100,200,500,1000,|D|}` and its tie conventions. They do not select beta or a. Reconcile additions/removals of 90% regions with changes in K90 and hits for the three main contrasts.

Figures: the four-model metric comparison and paired differences; ID-contribution changes; per-cell Brier differences; complete-probability maps with 90% outlines; matched-budget curves. Choose the illustration origin by maximum minimum all-development distinct-ID support across horizons, breaking ties by smallest cell ID, as in E3. Match colour scales within horizon and retain all positive probabilities. No favourable-cell selection after inspecting performance. Label maps as all-development illustrations.

## 11. Implementation layout after approval

Keep one current plan and one results account for E4. Use the existing environment, package and common asset/qualification/region/runtime helpers. Preserve E3's defaults, plan/config hashes and scientific behaviour. Reuse its pure functions where their interfaces genuinely support the new experiment; do not copy a hard-coded E3 model registry or uncertainty comparison count into E4. Any necessary generic extraction must preserve prior behaviour and be regression-checked; avoid unrelated architecture refactoring.

| Planned path | Responsibility |
|---|---|
| `src/data3001/modelling/baselines/partial_weighting_e4.py` | Local power-weighted estimates, explicit model identities, evaluation adapters and contrast definitions |
| `src/data3001/modelling/baselines/run_partial_weighting_e4.py` | Locked config, guards, roles, selection, outer freeze, exports and bounded execution |
| `src/data3001/modelling/baselines/partial_weighting_e4_audit.py` | Independent count/vector/weight/score/selection/uncertainty reconstruction |
| `src/data3001/modelling/baselines/partial_weighting_e4_report.py` | English report, review HTML and figures |
| `configs/partial_weighting_e4.json` | Explicit beta arms, Fixed grid, training/evaluation separation, contrast count and limits |
| `tests/test_modelling_partial_weighting_e4.py` | Mathematical semantics, integration and regression checks |
| `docs/partial_weighting_e4_results.md` | Current result account, created only after execution |

Use unique `partial_weighting_e4_<UTC_run_id>` results/provenance directories and a separate preflight namespace; reject overwrites. Preserve uncommitted work and prior immutable artifacts. No automatic commit, push, dependency update or restart of other models.

## 12. Tests, independent audit and replay

Required semantic checks after approval:

1. The 90/10 contribution example and mixed-endpoint probabilities above; direct hourly weighting equals compressed-count weighting.
2. Beta = 0 reproduces B2; beta = 1 reproduces EqualID; beta = 0.5 is the exponent estimator, not linear interpolation.
3. One-ID rows, equal local ID counts and identical internal endpoint distributions make all beta arms coincide.
4. Absent IDs do not enter denominators; repeated visits aggregate within ID/origin/horizon; counts for other cells/horizons cannot affect the local weighting.
5. Multiplying every local ID's counts by the same factor leaves all estimates unchanged. Multiplying one ID's entire local count vector by k changes its unnormalised total contribution by k^(1-beta), leaving its r_idj unchanged; EqualID is invariant to this single-ID replication.
6. Mass, finite values, E treatment, exact positive support, zero-truth cases, unsupported rows and shared masks. No synthetic example mistakes missing follow-up for E.
7. Explicit case-by-case three-level evaluation agrees with compressed arithmetic under unequal ID sizes/cell sizes/fold sizes; training beta never changes evaluation weights.
8. Fixed selection recomputes raw B1/B2, uses inner E3-primary Brier and resolves numerical ties toward smaller a; no outside-role counts or historical a are used.
9. Standard Brier, 90% ties, issued mass, K90, E-inclusive H90 and matched-budget semantics match independent enumeration.
10. Paired whole-ID multipliers, fixed cell membership, six-contrast correction and acceptance classification; no beta-selection output exists.
11. Relevant E3 and underlying S1/E1/E2, region and architecture regressions, without unrelated data pipelines.

Independently reconstruct all 26 bases and 1,200 candidate evaluation identities using alternate counters/explicit vectors and stable summation; audit selections, outer model scores, aggregation weights, region membership, uncertainty draws and decision labels without calling the production selector/aggregator. Use unchanged absolute numerical tolerance 1e-12; an arithmetic failure is investigated rather than resolved by loosening the tolerance.

After outer freeze, compare fresh B2, EqualID, raw B1 and selected Fixed forecasts/metrics against matching E3 artifacts within 1e-12; ID/cell memberships and masks must agree exactly. Check original pair-weighted B2 against the S1 reference where applicable. E4 comparison-adjusted bounds need not equal E3's because the comparison family changed. Historical hashes must remain unchanged.

Run one fresh full replay with unchanged code/config/input identities and a new run ID. Verify every numerical table within absolute 1e-12, excluding timestamps, run IDs and image encoding; visually inspect generated figures. Record source, environment, input, plan, outer-freeze and sealed-output hashes and zero raw/final-test trajectory access. A test pass validates implementation, not a predictive claim.

## 13. Budget, deliverables and approval boundary

E3's recorded primary/replay compute times were about 182/187 seconds. E4 increases declared candidate identities from 23 to 24 per role/horizon and reported models from three to four; full cost is not guaranteed to scale linearly because audit, reporting and uncertainty also change. Provisional compute expectation is minutes per run, to be checked by preflight; engineering and review effort is approximately 0.5-1 working day.

After approval, permit one preflight covering one inner role at both horizons and all 24 identities, with an independent audit and a five-minute cap. Require unchanged input/code identities between a successful preflight and the full run. Cap each primary/replay run at 30 minutes. Stop on projected/actual overrun or input, leakage, support, semantic or regression failure. Retain failed receipts, repair within approved definitions, and reverify before a fresh run; material scope/definition changes return for approval. Do not reduce audits or expand the grid to obtain a favourable result.

Deliver approved-plan/config snapshots; raw counts and fitting-contribution tables; all four sets of matrices; candidate and selected-a tables; held-out forecasts and ID-cell scores; primary/secondary summaries; paired differences and conditional uncertainty; support and mechanism diagnostics; English report/HTML/figures; independent audit and replay receipts; a concise Chinese review against the research question.

**Approved execution boundary:** implement the specified E4 experiment, bounded preflight, primary run, full replay, independent audit and visual comparison. Record the approved execution scope in the research-stage ledger. Scientific retention and stage closure await user review; final-test access, other models, Step 3 execution and Git publication remain outside this approval.
