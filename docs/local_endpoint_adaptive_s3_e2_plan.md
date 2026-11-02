# Step 3 — E2 Adaptive LocalEndpoint Borrowing

**Version:** S3 E2 v1, 31 October 2026.
**Status: USER APPROVED — INDEPENDENT DEVELOPMENT, EXECUTION AND AUDIT AUTHORISED.**

The user confirmed S3 E2 v1 and authorised independent development, execution, audit and visual comparison. The mathematical design, parameter grids, evaluation and acceptance rules below are locked. Preserve the approved S3 E1 plan, its sealed results, and all existing uncommitted work. Scientific retention and stage closure remain later user decisions.

## 1. Research question and the change under test

**Where Things End Up:** given an object already in a specified 1-degree origin cell at a qualified prediction time, estimate its destination distribution after 7 or 30 days, including absorbing E for the first observed exit from the frozen transport domain D.

**Question:** can a fitting-support-dependent borrowing weight improve LocalEndpoint's held-out probability estimates, while preserving actual coverage and a useful nominal-90% region size?

Keep the original B2 row and the original LocalEndpoint neighbour reference. Change only the rule allocating weight between them. The new family is named **LocalEndpointAdaptive**; the retained name **Adaptive** continues to mean Step 2 B2/global-B1 adaptive fusion.

The latest completed comparison, S3 E1, establishes the motivation:

| Days | Model | Brier | Mean K90 | H90 |
|---|---|---:|---:|---:|
| 7 | LocalEndpoint | 0.958288 | 27.36 | 88.19% |
| 7 | Fixed | 0.962457 | 42.71 | 89.96% |
| 30 | LocalEndpoint | 0.993751 | 104.68 | 76.28% |
| 30 | Fixed | 0.994931 | 133.86 | 77.59% |

These are checked historical development results, not E2 outputs or target values to force. LocalEndpoint has better Brier and smaller regions, but lower actual coverage than Fixed. More local support does not by itself prove that B2 is the better distribution, and the earlier global Adaptive did not consistently outperform Fixed. A support-driven spatial weight is a hypothesis to test, not an established improvement.

Two references have distinct roles: LocalEndpoint tests the benefit of changing the weight rule; Fixed tests the overall quality/region trade-off against the retained Step 2 reference. B2 and global Adaptive remain visible controls.

## 2. Frozen scope and inputs

Retain cleaned release `per-drifter-cleaned-20261017-v7`, annual pooling, qualified hourly observation pairs, the frozen R/D geometry and 1-degree state index, and separate direct stopped targets at 7 and 30 days. The starting time is arbitrary among qualified times, not first entry into the cell. Initial velocity and exact subcell position are not additional predictors in this experiment.

Retain raw observation-pair training and E3/E4/S3 E1 equal-ID-within-cell, equal-cell evaluation. Do not introduce EqualID/PartialID training, additional spatial rings, distance kernels, seasons, environmental covariates, local velocity, displacement translation, a B1-plus-neighbour three-way mixture, sharpened probabilities, or tail removal.

Authoritative contract: `docs/contract/data_contract_v1.0.xlsx`, SHA256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`, verified during proposal preparation.

Approved-source candidates for the later isolated read allowlist:

- Counts: `results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet`.
- Source-keyed qualification/exit labels and provenance from that same sealed input run.
- Folds: `results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv`.
- Current manifest, state index, R/D and pinned land-mask assets, for integrity checks and descriptive maps.
- Frozen S3 E1 run `spatial_borrowing_s3_e1_20261030T114538_900248Z`, for post-freeze control regression only.

No new hourly trajectory preparation is necessary: LocalEndpoint uses the already-qualified stopped destinations. Do not invoke the S3 E1 runner, read its translated-path cache, resume the stopped M1-neighbour run, or read the 517 locked final-test trajectories. The development inventory remains 3,224 IDs; only a subset has qualified R-origin cases.

Recheck these input expectations and stop on an unexplained mismatch; do not modify data to make counts agree:

| Days | Qualified pairs | Evaluation IDs | ID-cell units | Evaluated origins |
|---|---:|---:|---:|---:|
| 7 | 303,288 | 385 | 4,451 | 37 |
| 30 | 268,998 | 337 | 3,974 | 37 |

Report all 54 indexed origins, including those without eligible evaluation cases. The research target remains drifter-based transport; this experiment does not validate oil weathering, windage, or object-specific beaching.

## 3. Unchanged fitted distributions and neighbourhood

All quantities below are rebuilt separately for each horizon h and fitting-ID role F. Suppress h/F subscripts where unambiguous. Let n(d,i,j) be the integer number of qualified pairs for fitting drifter d, origin i and stopped destination j. Destinations include the indexed D cells and E.

Define N(i,j) = sum over d in F of n(d,i,j), and N(i) = sum over j of N(i,j). On supported rows:

`p_i(j) = P_B2(i,j) = N(i,j) / N(i)`.

Let A(i) contain exactly the eight adjacent 1-degree grid cells, excluding i, intersected with the existing R-origin index. Preserve the existing longitude wrapping and latitude bounds. Donors must actually start in R, belong to F, and qualify at the same horizon. No D-wide donor expansion is allowed.

The neighbour reference is unchanged:

`q_i(j) = sum_{k in A(i)} N(k,j) / sum_{k in A(i)} N(k)`.

Pool raw pair multiplicities, including repeated qualified starts of one drifter. Do not balance donor cells or donor IDs inside q. If i is supported but there are no donor pairs, set q_i = p_i and the actual neighbour weight to zero.

For the retained global controls, `q_G(j) = sum_i N(i,j) / sum_i N(i)`, including the target origin in the global pool, exactly as before.

LocalEndpoint uses original observed stopped destinations. No paths are moved, no new synthetic land/exit classifications are made, and no endpoint is snapped or discarded. E is retained. A malformed input distribution or inconsistent source record is an integrity failure, not a reason to fall back silently.

All five models share the raw-B2 support mask. If N(i)=0, do not score standard Brier, K90 or H90 for that row in any model. Report unsupported counts/fractions and unresolved bookkeeping separately. Neighbour-only rescue of completely unsupported origins is outside this experiment.

## 4. Support definition: distinct fitting drifters

Define the sets:

`I_i = {d in F : sum_j n(d,i,j) > 0}`;

`J_i = union_{k in A(i)} {d in F : sum_j n(d,k,j) > 0}`.

Use **L_i = |I_i|** as local support and **M_i = |J_i|** as neighbour support.

- Repeated hourly starts do not create additional IDs in L or M.
- One ID visiting several neighbour cells is counted once in the neighbour union M, not once per cell.
- An ID present locally and in neighbours is counted once in each context. Keep its eligible donor pairs; report the intersection size and Jaccard overlap. Do not claim L+M is an independent sample size.
- Neither support uses held-out IDs, their destinations, nor all-development counts during an inner or outer fit.
- Raw pair-frequency training is unchanged. ID support changes the mixture weight only; it does not give every drifter one training vote.

Distinct-ID counts are support proxies, not formal effective sample sizes or measurements of reference bias. Temporal dependence, common ocean forcing, local/neighbour overlap and unequal raw contributions remain. Save pair totals, distinct IDs and largest-ID pair share for both local and donor pools so a large M cannot hide a donor distribution dominated by one ID.

## 5. Proposed adaptive weight

For fitting-supported indexed rows with M_i > 0, define the relative support:

`r_i = M_i / L_i`.

Let `r_med` be the ordinary, unweighted median of these positive ratios over the fitting-supported indexed origins at this horizon. Do not restrict its roster using held-out case availability. Define:

`z_i = r_i / r_med`.

Normalisation accounts for a neighbour pool naturally containing more IDs than one cell. The two shared parameters are a, the borrowing weight at typical relative support, and gamma, the strength of adaptation:

`lambda_i(a,gamma) = a * z_i^gamma / ((1-a) + a * z_i^gamma)`.

The forecast is:

`P_LocalEndpointAdaptive(i,j) = (1-lambda_i)*p_i(j) + lambda_i*q_i(j)`.

For 0<a<1 and gamma>0, holding the fitting scale fixed, more local IDs with the same donor support reduce borrowing; more donor IDs with the same local support increase it. This is a relative-support rule. If both supports are small, or both large in the same proportion, it need not distinguish them; report absolute supports and do not interpret the weight as a certainty probability.

Required exact branches:

| Condition | Definition |
|---|---|
| Unsupported B2 row | Common unsupported mask; no standard forecast score |
| Supported B2, M_i=0 | q_i=p_i and actual lambda_i=0 for every parameter setting |
| a=0 | B2 exactly |
| a=1 and M_i>0 | q_i exactly |
| gamma=0 and M_i>0 | lambda_i=a; original LocalEndpoint exactly |
| z_i=1 | lambda_i=a |

If no fitting-supported origin has donors, record `no_positive_support_ratio`, use a documented scale placeholder of 1, and return B2 throughout; tie-breaking then selects gamma=0, a=0. Never add fake donor counts, use validation support, or expand the neighbourhood to avoid this case. Nonfinite or nonpositive ratios outside the documented branches are errors.

Illustration only: with r_med=2, a=0.5, gamma=1, a cell with L=5/M=40 borrows 80%; L=20/M=40 borrows 50%; L=80/M=40 borrows 20%. These are hand calculations, not fitted results.

This bounded rule is a project hypothesis, not a formal Dirichlet posterior. It cannot establish that more drifters imply a more relevant reference. It adds no destination outside the union of B2 and the neighbour reference. Report the held-out true-destination rate outside that union as a diagnostic of what no choice of this weight can fix.

## 6. Controls, parameter grid and selection

| Family | Definition | Candidate parameters per horizon |
|---|---|---|
| B2 | p_i | One |
| Fixed | (1-a)*p_i + a*q_G | 21 values of a |
| Adaptive | (1-w_i)*p_i + w_i*q_G | 21 values of a |
| LocalEndpoint | (1-a)*p_i + a*q_i | 21 values of a |
| LocalEndpointAdaptive | (1-lambda_i)*p_i + lambda_i*q_i | 21 a values x 4 gamma values |

Retained global Adaptive uses its original **pair-count** support: `w_i = m*a / ((1-a)*N(i) + m*a)`, with m the median positive fitting N(i), and explicit a endpoints. Do not replace its support with IDs when introducing the new model.

Proposed finite grid:

- `a in {0, 0.05, 0.10, ..., 0.95, 1}`.
- `gamma in {0, 0.5, 1, 2}` for LocalEndpointAdaptive only.
- Separate parameter selection at 7 and 30 days. Each selection uses one a/gamma pair shared across all cells; no per-cell or coast-specific fitted parameters.

There are 84 new-family candidates, including the complete 21-candidate constant-LocalEndpoint grid at gamma=0. Across all five families there are 148 declared identities per horizon and validation role. Equivalent forecasts may be cached, but audit tables retain every declared identity.

Nesting prevents the best inner candidate from being worse than the constant grid beyond tie tolerance; it does not guarantee better outer performance. Additional parameter selection can overfit the inner data. Outer whole-ID validation, rather than the minimum inner score, determines the reported benefit.

Select each family using the lowest pooled inner **primary Brier only**. For a tie within absolute 1e-12, the new family chooses smaller gamma first, then smaller a; the other families retain smaller-a tie-breaking. The rule deliberately favours the constant model when extra adaptation does not improve validation Brier. Do not tune K90/H90, reject candidates using outer outcomes, or change the grid after seeing performance. Quality acceptance below is a separate held-out screen, not another tuning objective.

Report all gamma=0 candidates as a built-in equivalence check against LocalEndpoint. Gamma>0 alone is not proof of meaningful adaptation: a=0/1, constant ratios, absent donors, or q_i=p_i can produce no effective forecast change. Save applied weights, their spread, and forecast differences from the matching constant-a candidate.

## 7. Unified evaluation and validation isolation

Keep the existing five outer whole-ID folds and four inner groups. For each outer fold k:

1. Exclude every ID in k from fitting and inner selection.
2. For each remaining group l, fit on IDs outside k and l; rebuild B2, B1, neighbours, L/M and both support medians using only those fitting IDs.
3. Evaluate every candidate on l. Pool the four inner ID-cell tables before applying the primary equal-ID/equal-cell aggregate; do not average four fold means.
4. Select each family's parameters, refit on the four outer-training groups, and score all five models on k using the same cases and weights.

For each horizon, average eligible times within an ID/origin cell, average those ID means equally within that cell, and average the evaluable cells equally. If cell i contains D_i held-out IDs and ID d has t_di eligible times there, its individual pair weight is `1/(number_of_cells * D_i * t_di)`. Multiply by pair multiplicity for compressed records. Use this same primary weighting for Brier, K90, H90 and parameter selection. An ID appearing in several cells has one vote within each of them; this is not one vote for the entire ocean.

Pool the five outer held-out ID-cell tables with this same rule for the main result. Save availability and weights explicitly; no model may exclude zero-probability truths or difficult cells. Pair-weighted summaries are secondary sensitivity descriptions of the same forecasts and never determine the winner.

Freeze/hash outer forecasts, selections, support/masks, applied weights and score records before all-development illustration selection. Then use the five base outer fits to select illustrative all-development parameters and refit on all development IDs. These maps are not new held-out evidence.

The design has 26 fitting roles (20 inner, 5 outer, 1 all-development) and 25 validation roles (20 inner, 5 for all-development selection). With two horizons it yields 7,400 candidate identity/horizon/role evaluations. Under the unchanged population, expect 6,234,500 candidate ID-cell records; verify rather than force this count.

Freshly fit and tune the four controls; do not import their old predictions as the experiment's controls. After outer freeze, regress against S3 E1: all 24 selected control matrix files (6 roles x 4 models), selected parameters, common cases, primary weights and held-out metrics must reproduce within absolute 1e-12. An unexplained mismatch stops interpretation of the new result.

## 8. Metrics and uncertainty

Use standard multiclass Brier over indexed D cells plus E:

`BS(p,y) = sum_j (p_j - 1[j=y])^2 = 1 + sum_j p_j^2 - 2*p_y`.

All supported distributions must sum to one. There is no spatial or combined loss. Zero-probability truths receive their ordinary score.

Keep nominal probability **0.90** for every model. Sort the complete probabilities, take the shortest prefix reaching the target mass, and include all cutoff ties using the existing 1e-12 convention. Do not drop/renormalise the tail. E contributes to mass and outcome hits but not geographic cell count.

- **K90:** number of geographic cells in that region, averaged under the primary weights.
- **H90:** actual stopped outcome in the region, averaged under the same weights.
- Also report issued region mass, E probability/inclusion/observations, positive-probability cell count, zero-truth-probability rate, unsupported availability, and truth outside the B2/neighbour support union.

Nominal 90% is not a promise of 90% observed hits. Show H90-0.90 descriptively, but this round's non-deterioration screen compares models on common cases; it does not certify absolute calibration.

Two prespecified contrast sets are LocalEndpointAdaptive minus LocalEndpoint and LocalEndpointAdaptive minus Fixed, separately at each horizon. Differences against B2 and global Adaptive remain descriptive.

Use **10,000 paired positive whole-ID multiplier replicates**, PCG64 Exp(1), seed **20261031**, over sorted development IDs. Share the same ID multiplier across all cells, horizons and models. Keep fitted forecasts and within-ID means fixed; renormalise ID weights within each cell and keep cells equally weighted. Save draw identity/hash, quantile method and undefined counts; use linear quantiles. The increased replicate count improves numerical resolution of the more extreme screen tails; it does not change the evaluation estimand or refit models.

Show ordinary 95% intervals. For the prespecified directional screens, use 12 comparisons (2 references x 3 metrics x 2 horizons): upper quantile `1-0.05/12` for Delta Brier/K90 and lower quantile `0.05/12` for Delta H90. No additional screens are added after results. Historical 5,000-draw intervals need not reproduce; control point forecasts/metrics must.

These are approximate conditional development screens. They omit fitting uncertainty, dependence from overlapping training sets, prior project adaptation and shared ocean forcing. LocalEndpoint was chosen for further study after earlier development results; a new run does not make the reused development set an untouched final test. Do not claim a formal final-test superiority or non-inferiority guarantee.

## 9. Acceptance and stopping decisions

Let Delta mean new minus the named reference; U_B/U_K are the adjusted upper bounds and L_H the adjusted lower bound. Epsilon=1e-12 is arithmetic tolerance only, not an allowed scientific loss margin.

| Decision, separately per horizon | Prespecified rule |
|---|---|
| Engineering complete | Inputs/roles/semantics, probability accounting, all four control regressions, independent audit, report and fresh replay pass; a predictive win is not required |
| Point Brier improvement over a reference | Delta Brier < -epsilon |
| Conditional Brier support over a reference | Point improvement and U_B < -epsilon |
| Coverage-preserving adaptation gain over LocalEndpoint | Brier support over LocalEndpoint and both point Delta H90 >= -epsilon and L_H >= -epsilon; report K90 trade-off |
| No-region-expansion gain over LocalEndpoint | Previous row plus point Delta K90 <= epsilon and U_K <= epsilon |
| Overall quality/region upgrade over Fixed | Brier support over Fixed; point Delta H90 >= -epsilon and L_H >= -epsilon; point Delta K90 <= epsilon and U_K <= epsilon |
| Strictly smaller region without quality loss over a reference | The corresponding Brier/H90/K90 quality rules pass and U_K < -epsilon |
| Preferred adaptive candidate for user review | Meaningful adaptive forecast changes are used; coverage-preserving adaptation gain over LocalEndpoint AND overall quality/region upgrade over Fixed pass |
| No adaptive benefit selected | Constant gamma=0 wins throughout, or the applied rule gives no adaptive forecast changes; retain this as a valid negative finding |
| Trade-off / inconclusive | Quantify Brier/H90/K90 changes and bounds; do not call a loss of coverage a success because K90 shrank, or a nonsignificant difference proof of preservation |

No coverage-loss allowance or arbitrary minimum Brier benefit is introduced. Report effect sizes and uncertainty; scientific retention remains the user's decision. Passing at 7 days does not pass at 30 days.

The main acceptance rule does **not** require K90 to shrink below the already compact LocalEndpoint region: recovering coverage may need some additional cells. Such a result is acceptable as a proposed overall upgrade only if it still meets the Fixed-based non-expansion and quality rules. A claim of improving all three metrics over LocalEndpoint requires the stronger LocalEndpoint rule above. State explicitly which reference each claim uses.

If the grid selects constant borrowing, produces an unresolved trade-off, or fails Brier improvement, finish the bounded experiment and report that result. Do not automatically enlarge gamma, invent local gates, or run another search. The support-union diagnostic may motivate a later information-source proposal, but it must not alter this run.

## 10. Mechanism diagnostics and visual comparison

Save per fitting role/horizon/origin: local and neighbour pair counts, distinct-ID sets/counts, donor-cell count, intersection/Jaccard overlap, largest-ID shares, r_i, r_med, z_i, a/gamma, applied neighbour weight, B2 weight, support mask and no-donor flag.

Report weight variation, endpoint weights, selected parameters across outer folds, and distance between adaptive and same-a constant forecasts. Split by the existing descriptive local-support bands 1-9 / 10-49 / 50+ fitting IDs and coastal/offshore grid polygons under the pinned high land mask. Strata use the actual outer fitting-role supports; retain and renormalise primary case weights and report stratum weight masses. No stratum selects parameters or triggers special borrowing.

Required outputs:

1. Five-model Brier/K90/H90 table at both horizons; absolute/relative K90 changes and H90 changes in percentage points.
2. Difference plots against LocalEndpoint and Fixed with ordinary intervals and declared directional screens.
3. Applied neighbour weight versus local support and neighbour/local support ratio, with donor support/overlap visible; constant LocalEndpoint reference alongside it.
4. Per-cell Brier, K90 and H90 differences with support/availability, without selecting only favourable cells.
5. Matched probability maps for the same five models and fixed 90% outlines, common scales, complete stored tails, and explicit all-development labels.

Select illustration cells by the unchanged S3 E1 fitting-support/geometry rule: positive local support at both horizons; highest minimum-across-horizons ID support, lowest positive support among other cells, then highest-support remaining coastal cell; ties by smallest cell ID. Freeze before inspecting improvements. The current S3 E1 roster is 44744 / 44742 / 44382; identical inputs should reproduce it. No performance-selected substitutes. This round needs no translated-path diagrams.

## 11. Engineering layout, audits and bounded execution after approval

Use a new namespace `local_endpoint_adaptive_s3_e2`. Proposed future files under `src/data3001/modelling/baselines/` are `local_endpoint_adaptive_s3_e2.py`, `local_endpoint_adaptive_s3_e2_audit.py`, `local_endpoint_adaptive_s3_e2_report.py`, and `run_local_endpoint_adaptive_s3_e2.py`, with matching config, targeted tests, and `docs/local_endpoint_adaptive_s3_e2_results.md`. These files are authorised for this experiment.

Reuse audited raw B2/B1/global-Adaptive, qualification, prediction-region and E3 scoring utilities where semantics match. The spatial reference must be constructible from counts without requesting displacement transfers. Do not import a prior runner or refactor unrelated code. Any necessary shared-helper extraction must be minimal and preserve prior results.

Targeted pre-run checks cover:

- Distinct-ID set unions, repeated origins/endpoints, multi-neighbour duplicate IDs, local/donor overlap and unchanged raw pair fitting.
- Fitting-only medians and references; held-out-ID exclusion; eight-neighbour/self/R rules.
- Weight endpoints, gamma=0 exact nesting, typical-ratio value, monotonicity with fixed scale, empty donors, all-empty ratio scale, unsupported rows, and invalid/nonfinite input rejection.
- Hand-calculated mixture/weight examples, mass conservation, unchanged E semantics, and the B2/neighbour support-union limit.
- Equal-ID/equal-cell aggregation, common availability, zero-probability truths, region ties/E, candidate counts and tie priority favouring constant borrowing.
- Full identity of retained controls and gamma=0 candidates, seed/replicate/screen metadata, and report interface compatibility.

After fitting, an independent audit must reconstruct counts and ID sets without calling the new fit/weight helpers; recalculate references, medians, every candidate score/selection, selected matrices, applied weights, per-case Brier/regions and aggregate metrics. Independently reproduce multiplier summaries and acceptance decisions. Structural tests alone do not validate the scientific meanings.

Save immutable run IDs prefixed `local_endpoint_adaptive_s3_e2_`. Include approved-plan/config snapshots, all relevant source hashes and source snapshots **including the entrypoint**, input/contract hashes, environment, roles, support diagnostics, full candidate records, selected parameters, complete forecasts, freezes, scores, intervals, control-regression receipts and audit/replay reports. Update a stable deliverable alias only after a successful audit. Preserve all old runs.

Resource proposal: CPU only, at most two workers, peak RSS <=8 GiB, combined new primary/replay artifacts <=5 GiB. A count/schema/resource preflight is capped at 300 seconds. Profile the first predetermined inner fitting/validation role for resource use, not model success; proceed only if projected complete execution fits the cap. Cap each complete CV/evaluation/audit/report run at 1,800 seconds, with a separate fresh full replay capped at 1,800 seconds. These are stop limits, not runtime promises.

Stream/free candidate tables as needed without changing arithmetic, candidates or observations. A fresh replay must reproduce numeric tables within absolute 1e-12 and matching figures under the pinned environment. Stop on a resource/integrity failure; do not silently reduce folds, donors, candidates or interval replicates.

## 12. Review gate

This proposal fixes the prospective choices to review: distinct-ID relative support; the normalised two-parameter weight with gamma=0 nesting; raw-pair training and unchanged evaluation; Brier-only inner selection; two reference comparisons with zero coverage-loss margin; and bounded independent execution/audit.

At approval, source/contract/result review and this plan were complete. Independent implementation, execution and audit are now authorised. Record results in separate immutable runs and the E2 results document. No benchmark replacement, final-test access, commit or push is authorised. The next gate is user review of the audited E2 results; research-stage closure and any additional experiment remain later decisions.
