# Step 3 E4 — Joint Neighbour Allocation and Borrowing with Quality Constraints

**Version:** S3 E4 v1, 31 October 2026 (Australia/Sydney).
**Status: USER APPROVED — INDEPENDENT DEVELOPMENT, EXECUTION AND AUDIT AUTHORISED.**

The user confirmed this complete S3 E4 v1 plan and authorised independent development, execution, audit and visual comparison. Its scientific definitions, constraints, fallback, finite search, validation and acceptance are locked. Preserve earlier experiments and existing uncommitted work. Scientific retention and stage closure remain later user decisions.

## 1. Research question and interpretation

**Where Things End Up:** predict the stopped destination distribution after 7 or 30 days for an object already in a specified 1-degree origin cell at an arbitrary qualified prediction time. First observed exit from the frozen transport domain D is absorbing E. Drifters remain the transport proxy.

**Question:** can jointly choosing the neighbour endpoint allocation and the total borrowing strength improve standard Brier while preserving actual nominal-90% region hits and geographic cell counts relative to both LocalEndpointAdaptive and Fixed?

Two issues are tested separately:

1. E3 changed the neighbour distribution after fixing the adaptive borrowing parameters. A different reference may need a different borrowing strength.
2. E3 selected by inner Brier alone, then checked coverage and size after selection. E4 makes coverage and size explicit internal feasibility conditions, while retaining Brier as the optimisation objective.

This is a bounded extension of endpoint borrowing. It introduces no movement transfer, new similarity measure, donor expansion, endpoint deletion rule, combined loss, or model-specific evaluation population. A constrained search may return no acceptable improvement. Reproducibility and successful constraint implementation do not establish predictive superiority.

## 2. Verified starting evidence

The [E3 result](local_endpoint_quality_s3_e3_results.md), primary run `local_endpoint_quality_s3_e3_20261031T005527_091650Z`, reproduces the earlier controls. Relevant held-out development points are:

| Days | Model | Brier | Mean K90 | H90 |
|---|---|---:|---:|---:|
| 7 | LocalEndpointAdaptive | 0.959104 | 27.22 | 88.24% |
| 7 | Fixed | 0.962457 | 42.71 | 89.96% |
| 7 | LocalEndpointQuality | 0.958162 | 26.43 | 87.84% |
| 30 | LocalEndpointAdaptive | 0.993452 | 105.34 | 76.84% |
| 30 | Fixed | 0.994931 | 133.86 | 77.59% |
| 30 | LocalEndpointQuality | 0.993507 | 105.13 | 76.75% |

E3 selected rho=1 in all outer fits and both all-development fits. Its observed incremental effect was neighbour similarity reweighting, not weak-endpoint removal. Its 7-day Brier gain came with a coverage loss. These historical numbers motivate the proposal; **they must never become numerical inner-selection thresholds**. Every new inner reference is freshly fitted and selected without its outer evaluation IDs.

The development set has already informed this research direction. Reusing nested folds preserves the exclusion of each outer ID from its own model fitting and parameter selection; it does not make this round an untouched final evaluation.

## 3. Frozen scope and inputs

Retain cleaned release `per-drifter-cleaned-20261017-v7`, annual pooling, 1-degree R-origin/D-destination geometry, qualified hourly pairs and separate direct 7/30-day stopped targets. Keep **raw equal-pair training**, **equal-ID-within-origin and equal-origin evaluation**, and the same supported-case mask. Do not reinterpret equal-ID evaluation as equal-ID training.

The contract remains `docs/contract/data_contract_v1.0.xlsx`, SHA256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`, verified during proposal preparation.

Allowlisted inputs after approval:

- Qualified counts: `results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet`, with the sealed qualification/exit evidence and input receipt.
- Whole-ID folds: `results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv`.
- Frozen state/R/D/land assets, manifests and contract for integrity and descriptive geometry.
- Sealed S3 E3 outputs for post-freeze control regression only.

Expected unchanged development population:

| Days | Qualified pairs | Evaluation IDs | ID-origin units | Evaluated origins |
|---|---:|---:|---:|---:|
| 7 | 303,288 | 385 | 4,451 | 37 |
| 30 | 268,998 | 337 | 3,974 | 37 |

There are 3,224 development IDs, 517 locked final-test IDs and 54 indexed origins. Report the 17 origins without eligible evaluation cases; their skill is unknown. An unexplained roster mismatch is a stop condition. No final-test trajectories, canonical trajectory reconstruction, translated-path cache, new cleaning, stopped-run restart, velocity, season, finer grid or recursive propagation is needed or authorised.

## 4. Models and attribution

| Role | Name | Definition |
|---|---|---|
| Primary candidate | **LocalEndpointJointConstrained** | Joint finite parameter search; inner H90/K90 constraints against both named references; require inner Brier improvement before adopting a new candidate |
| Selection diagnostic | **LocalEndpointJoint** | Exactly the same joint candidate distributions; minimum inner Brier without the H90/K90 constraints or adoption gate |
| Retained control | LocalEndpointQuality | Exact E3 anchor-first nine-setting procedure, including its original rho grid and tie rules |
| Retained control | LocalEndpointAdaptive | Exact E2 adaptive borrowing of the original pooled neighbour distribution |
| Retained control | LocalEndpoint | Original constant-weight neighbour endpoint borrowing |
| Retained controls | B2, Fixed, Adaptive | Original local counts, constant B2/B1 mixture, pair-support-adaptive B2/B1 mixture |

Eight models receive the same outer cases, scoring and plots. Only LocalEndpointJointConstrained is the prespecified primary candidate. Do not promote LocalEndpointJoint after inspecting its outer score; it explains the cost or benefit of the constraints.

LocalEndpointJoint versus E3 tests freeing the borrowing parameters under the same similarity family. Verify that the reproduced E3 selected rho=1, as expected, before describing this as the observed joint-tuning contrast. LocalEndpointJointConstrained versus LocalEndpointJoint isolates the selection/adoption policy on an identical candidate family. These are controlled algorithm comparisons, not proof of a physical ocean mechanism.

Historical LocalDisplacement remains in the S3 E1 benchmark with its original evidence; it is not refitted or added to the primary testing family in this endpoint-only round.

## 5. Counts, support and neighbour information

All definitions below are rebuilt separately for each horizon h and fitting-ID set F. Let N_ij be the number of qualified fitting pairs from origin i to destination j in D plus E. Set N_i=sum_j N_ij and p_i(j)=N_ij/N_i for supported B2 rows.

- A(i): the eight adjacent 1-degree cells, excluding self, intersected with the frozen R-origin index. Preserve longitude wrapping and latitude bounds.
- q_i(j)=sum_{k in A(i)}N_kj / sum_{k in A(i)}N_k: the original raw-pair pooled neighbour reference.
- L_i: distinct local fitting drifters; M_i: distinct fitting drifters in the union of neighbouring cells. Deduplicate M across cells and repeated observations.
- Record local/neighbour ID overlap, per-neighbour ID support, per-endpoint ID unions and largest-ID pair shares. These are support diagnostics, not claims of independent ocean samples.

For geographic states, N_iD=sum_{j in D}N_ij and p_iD(j)=N_ij/N_iD when defined. The existing E3 overlap is:

`S_ik = sum_{j in D} min(p_iD(j), p_kD(j))`.

For donors with N_kD>0:

`w_ik(eta) = N_kD * (1-eta+eta*S_ik) / sum_l[N_lD * (1-eta+eta*S_il)]`.

Let e_i=q_i(E). Preserve this original neighbour exit mass:

`q_i_eta(E)=e_i`;

`q_i_eta(j)=(1-e_i)*sum_k[w_ik(eta)*p_kD(j)]`, for j in D.

Eta=0 must reproduce the original pooled reference, including E, exactly within numerical tolerance. Eta remains below 1, so an in-D donor with zero overlap retains positive source weight. Shared endpoints mean the same indexed destination cell, with no distance smoothing. Similarity can favour noisy local estimates; no claim that similarity itself measures physical relevance is added.

**For the two new arms, rho is fixed to 1.** There is no weak-endpoint suppression or mass return. Keep rare/shared/unseen categories as diagnostics only. Fixing rho does not guarantee that a rare endpoint retains its previous probability or stays inside the 90% region. Changing the final mixture weight can still change support, especially at a=0 or a=1; all resulting zero-probability truths remain scored.

Boundary/support cases retain E2/E3 semantics:

- Unsupported B2 row: unavailable standard scores for every model, separately counted; do not rescue with neighbours or global B1.
- Supported B2 but no neighbouring pairs: return B2 and set actual borrowing to zero.
- Local D distribution empty, or neighbour D distribution empty: bypass similarity and use q_i; preserve E and record the reason.
- No transformed coordinates or new land/exit rejection rule is introduced. Reweighting q preserves its E mass; changing the final borrowing strength may legitimately change final forecast E mass and must be reported.

## 6. Joint borrowing formula and finite parameter grid

For each fitting role and horizon, calculate r_i=M_i/L_i for supported origins. Let m_h be the unweighted median of positive r_i over those fitting-supported origins, and z_i=r_i/m_h. If no positive r_i exists, record it and use the established median placeholder 1; all such no-donor weights remain zero.

`lambda_i(a,gamma) = a*z_i^gamma / (1-a+a*z_i^gamma)`.

Use explicit branches: no neighbours or a=0 gives lambda=0; a=1 with neighbours gives lambda=1; gamma=0 gives lambda=a. Preserve the audited log-odds numerical evaluation for the interior.

`P_i(theta) = (1-lambda_i)*p_i + lambda_i*q_i_eta`, where `theta=(a,gamma,eta)`.

| Parameter | Proposed values | Interpretation |
|---|---|---|
| a | 0, 0.05, ..., 1.00 (21 values) | Borrowing at z=1 |
| gamma | 0, 0.5, 1, 2 (4 values) | Sensitivity to relative neighbour/local ID support |
| eta | 0, 0.5, 0.9 (3 values) | Strength of neighbour similarity reweighting |
| rho | 1, fixed in new arms | No weak-endpoint gate |

This gives **252 logical parameter triples per horizon and fitting/validation role**. The ranges are unchanged from earlier component grids; E4 tests their joint combinations. No new range, endpoint threshold or source-specific free coefficient is searched. A horizon has one selected triple for all its origins; lambda still varies by fitting support. No cell-by-cell outer-result switching is allowed.

The family contains B2 (a=0), LocalEndpoint (gamma=0, eta=0), and the complete LocalEndpointAdaptive grid (eta=0). It does not contain general Fixed, whose B1 source remains a separate reference. Containment guarantees an available local anchor candidate, **not** that the intersection of the Fixed and local quality constraints is feasible.

Numerically duplicate triples remain identified in the candidate ledger. Computation may be deduplicated with an explicit identity map; ties must not depend on iteration order. All Brier ties within absolute 1e-12 prefer smaller eta, then smaller gamma, then smaller a.

## 7. Internal references, constraints and fallback

For each outer training partition and each horizon, first fit and select the six retained controls using their unchanged inner procedures. On the same pooled inner held-out ID-origin units, obtain reference metrics `(B_A,H_A,K_A)` for LocalEndpointAdaptive and `(B_F,H_F,K_F)` for Fixed. A and F are freshly selected inside this partition; no sealed historical metric or own-outer outcome enters these thresholds.

For every joint triple theta, calculate `(B_theta,H_theta,K_theta)` on exactly those common inner units. Pool units before aggregation; do not average four fold means equally. Define epsilon=1e-12 solely for arithmetic tolerance.

The proposed primary feasible set satisfies **all four** conditions:

`H_theta >= H_A-epsilon` and `K_theta <= K_A+epsilon`;

`H_theta >= H_F-epsilon` and `K_theta <= K_F+epsilon`.

Equivalently, require H_theta at least max(H_A,H_F) and K_theta at most min(K_A,K_F), with the stated arithmetic tolerance. This is a deliberate intersection of both complete reference comparisons, not a choice of whichever reference is easier for each metric. It is stricter than constraining only against the local anchor.

Use pooled-inner **point metrics** for this feasibility screen, not confidence bounds. The screen aligns selection with the practical target; it does not prove population non-deterioration. Do not add internal bootstrap thresholds, percentage-point allowances, per-fold/per-cell constraints or soft penalty weights in this round. Save fold/cell diagnostics separately.

Selection policy:

1. LocalEndpointJoint selects minimum Brier over all 252 triples, using the fixed tie rule.
2. LocalEndpointJointConstrained selects minimum Brier over the feasible set, with the same tie rule.
3. Adopt that constrained choice only if `B_theta < min(B_A,B_F)-epsilon`, i.e. its inner Brier is strictly lower than both references. This avoids accepting a coverage/size trade for a worse primary score. There is no separately tuned minimum-effect threshold.
4. If the feasible set is empty, issue the freshly selected LocalEndpointAdaptive forecast and record `fallback_no_feasible_candidate`.
5. If feasible candidates exist but the best has no strict inner Brier gain over both references, issue LocalEndpointAdaptive and record `fallback_no_Brier_gain`.

Fallback is a declared no-new-model decision. It does **not** assert that LocalEndpointAdaptive satisfies Fixed's coverage/size requirements. Save those deficits and never label a fallback a successful constrained improvement. Do not switch to Fixed after failure, relax constraints, discard a difficult fold or expand the grid. Fallback is selected once per horizon/outer partition, not separately for each held-out origin.

Save all candidate reference deltas, four constraint flags, local-only/Fixed-only/intersection feasibility counts, Brier adoption status, selected parameter identity, best rejected Brier and reasons for rejection. This shows which requirement binds without introducing another selected forecast arm.

## 8. Nested whole-ID validation and illustration separation

Retain five outer groups and four inner groups within each outer training partition. For outer group k:

1. Exclude every ID in k from all fitting, support, medians, similarity, threshold setting and selection.
2. For each inner group l, fit counts and references on IDs outside k and l; evaluate only l. Use the common supported-case mask for all candidates and controls within that role.
3. Pool the four inner candidate ID-origin tables using the declared primary weights. Select the original five E2 controls, then the original E3 anchor-first quality control, unchanged.
4. Apply the two E4 selection policies to the same 252-triple metric table. Compute all constraints from the pooled inner references, never from outer scores.
5. Refit on all four outer training groups. Recompute support/medians/similarities from this fitting set, apply the already selected control/arm parameters or declared fallback, and evaluate group k once.
6. Save candidate grids, reference thresholds, flags, selected/fallback identities and held-out forecasts. Do not alter decisions after seeing any outer fold.

Repeat for all five outer groups, then pool held-out ID-origin outputs using the same estimand as selection. Unsupported units remain reported and excluded identically from standard scoring; no candidate may improve apparent feasibility by changing the denominator. Stop on unexplained differences in eligibility/support between controls and candidates.

Freeze/hash outer predictions, support, cases, weights and selections **before** all-development illustration selection. Then use the five outer-fit candidate validation tables as development-only tuning data to select each final illustration model, including its references and identical constraints/fallback. Refit once on all development IDs. These maps are illustrative fitted candidates, not a second independent performance estimate.

There are 26 fitting roles (20 inner, five outer, one all-development) and 25 candidate-validation roles. Per horizon/role, retain 148 original-control identities, nine E3 anchor-conditioned identities and 252 joint identities: **409 logical candidate views**, or **20,450** across 25 roles and two horizons. The two new arms share one joint table. At the unchanged roster, the corresponding upper-bound ledger has **17,229,125 ID-origin candidate records** before explicitly mapped reuse. Do not treat these as independent statistical samples. Verify counts against source units rather than forcing the expected number.

## 9. Evaluation and uncertainty

Within an evaluated origin, average each drifter's eligible prediction times, give drifters equal weight, then average origins equally. In an aggregated evaluation table, a pair's weight is:

`1 / (number_of_evaluated_origins * eligible_IDs_in_its_origin * eligible_pairs_for_its_ID_origin)`.

Use pair multiplicity for compressed records. An ID may contribute to several origins; this is not one vote across the entire ocean. Use this same target for Brier, K90, H90, selection and uncertainty. Raw pair-weighted results remain labelled secondary sensitivity summaries only.

- Standard multiclass Brier: `BS(P,y)=1+sum_j P(j)^2-2*P(y)` over D plus E. Lower is better; it is not percentage accuracy.
- Fixed nominal region: sort the complete distribution, take the shortest descending prefix reaching 0.90, and include all cutoff ties using the existing 1e-12 convention.
- K90: geographic cell count in that region; E is excluded from cell count but included in probability and hits. A mean cell count is not square-kilometre area.
- H90: weighted actual membership of the observed destination in the region. Nominal 90% does not guarantee actual 90% hits.
- Keep every supported true destination, including zero-probability and rare endpoints. Report issued mass, zero-truth rate, E, unsupported/U accounting, full positive support and outside-union truth rates.

Primary contrasts: **LocalEndpointJointConstrained minus LocalEndpointAdaptive**, and **minus Fixed**, separately at 7 and 30 days.

Use 20,000 positive whole-ID Exp(1) multiplier replicates, PCG64 seed 20261031, with sorted development IDs. Share each ID's multiplier across all its origins, horizons and models. Keep fits and within-ID averages fixed; renormalise ID weights within origins and keep the evaluated origin set equally weighted. Save the multiplier identity/hash and use linear quantiles.

Report ordinary 95% paired intervals. The primary directional screening family contains **12 comparisons** (two references x three metrics x two horizons): upper quantile `1-0.05/12` for Brier and K90; lower quantile `0.05/12` for H90. Diagnostic arm/control contrasts receive descriptive intervals and no alternative primary-win designation. Do not change the family because some contrasts look favourable.

These are approximate conditional development screens. They omit refitting uncertainty, overlapping training dependence, common ocean forcing and earlier research adaptation. A confidence interval crossing zero is not evidence of non-deterioration. Constraints applied in inner validation need not remain satisfied after refitting or on outer IDs.

## 10. Acceptance and permitted conclusions

For each reference and horizon separately, let Delta be new minus reference. Let U_B and U_K be the adjusted upper bounds and L_H the adjusted lower bound.

| Label | Required evidence |
|---|---|
| Engineering complete | Isolation, formula/selection audits, six-control regression, required outputs and fresh replay pass; a predictive win is not required |
| Point improvement without observed deterioration | Delta Brier < -epsilon, Delta H90 >= -epsilon, Delta K90 <= epsilon |
| Conditionally supported quality-preserving improvement against one reference | Previous row, plus U_B < -epsilon, L_H >= -epsilon and U_K <= epsilon |
| Strictly smaller region without quality loss against one reference | Previous row, plus Delta K90 < -epsilon and U_K < -epsilon |
| Preferred E4 candidate at a horizon | Meaningful forecast change and the supported quality-preserving conditions against **both LocalEndpointAdaptive and Fixed** |
| Improvement only against local anchor | Passes against LocalEndpointAdaptive but not Fixed; report the narrower result without calling it an overall replacement |
| Neutral/inconclusive | Fallback/identical forecasts, no Brier gain, or required uncertainty bounds not met |
| Adverse trade-off | Brier improves but H90 decreases or K90 increases; report explicitly, including whether intervals distinguish the change from zero |

No positive scientific non-inferiority margin is proposed. Epsilon is numerical tolerance, not permission to lose coverage or increase size. A small point benefit can remain inconclusive under the strict bounds. Do not loosen the criteria after observing the experiment.

Partial fallback across outer folds does not invalidate evaluating the declared selection procedure, but fallback frequency and where gains occur must be visible. If every outer choice at a horizon falls back, classify it as no new predictor, not an improvement. A 7-day success does not establish a 30-day success, and vice versa. Retention, model replacement, Step 3 closure and final-test access remain later user decisions.

## 11. Required diagnostics and visual deliverables

1. Eight-model Brier/K90/H90 table; paired primary differences, adjusted bounds and explicit acceptance flags; K changes in cells/percent and H changes in percentage points.
2. Inner candidate feasible-set plots showing Brier versus H90 and K90, both reference boundaries, rejected candidates, and the two selected arms. Clearly label these as selection data, not held-out proof.
3. Constraint/fallback table for all five outer selections per horizon and final illustrations: reference thresholds, feasible counts, binding requirements, selected parameters, fallback reasons and adoption status.
4. Joint-tuning versus constrained-selection comparison; parameter stability and actual per-origin lambda changes, not only nominal a.
5. Changed-row counts and total-variation distance; rare/shared/neighbour-only probability and hit changes; new/lost region hits; zero-probability truths; E and outside-union diagnostics. All categories must come from fitting data and reconcile with complete totals.
6. All-origin Brier/K90/H90 differences and the existing fitting-support/coastal strata. These are descriptive checks, not post-result rules for selecting a winner in particular cells.
7. Matched all-development full-distribution maps for the existing support/geometry roster (origins 44744, 44742, 44382), at both horizons. Compare primary candidate, Joint diagnostic, LocalEndpointAdaptive and Fixed directly; retain the remaining models in the report. Use common scales, complete tails, 90% boundaries, E/support captions and explicit illustration labels. Do not select cases based on performance.

Deliver an English results document and HTML review, complete matrix/score/selection/diagnostic tables, uncertainty draws and audit/replay receipts, plus a Chinese user summary explaining whether any improvement preserved both coverage and size.

## 12. Engineering isolation, tests and independent audit

Proposed namespace: **local_endpoint_joint_s3_e4**, distinct from Step 2 partial-weighting E4. After approval only, create the independent model, audit, report and runner modules under `src/data3001/modelling/baselines/`, a matching config, focused tests and `docs/local_endpoint_joint_s3_e4_results.md`.

Reuse audited pure count, E3 similarity/reference, E2 support/weight, scoring and region helpers. Do not call historical experiment runners, change old model formulas, refactor unrelated modules or overwrite sealed outputs. Preserve all existing uncommitted work. Legacy controls must retain their own parameter selection; applying the new feasibility screen to them would change the baselines and is prohibited.

Required tests include:

- Count/ID distinction, whole-ID exclusions, neighbour union/overlap, fitting-only medians and geographic/E probability conservation.
- Hand calculations for overlap, eta-zero identity, joint mixing and all support/endpoint branches; reproduction of B2/LocalEndpoint/LocalEndpointAdaptive subfamilies.
- Standard Brier on zero-probability truths; equal-ID/equal-origin aggregation; 90% ties/E handling; identical candidate/reference case masks.
- Exactly 252 parameter triples, duplicate identity mapping and deterministic eta/gamma/a ties; unchanged six-control selectors.
- A better-Brier candidate rejected separately for each reference's H or K condition; candidates satisfying only one reference; exact-tolerance boundaries; empty feasible set; feasible set without strict Brier gain; both fallback reasons; a valid improving candidate.
- Fallback exactly equals the freshly fitted local anchor, while still exposing any failed Fixed requirement. No fallback may be labelled a passed constraint screen.
- Pooled ID-origin inner metrics rather than mean fold scores; no outer-score thresholding; all-development separation; primary directional-family count and decision reconstruction.

Independently reconstruct counts, reference probabilities, support, similarities, mixtures, all candidate metrics, reference selection, feasible flags, ties, fallback and final decisions without using the new production selector to audit itself. Recompute selected matrices, per-case regions/scores, summaries and multiplier bounds. Inspect every diagnostic table for denominator reconciliation.

After the new outer freeze, verify all **six retained controls** against sealed S3 E3: 36 selected matrix files (five outer roles plus all-development role, six controls), selected parameters, common cases/weights, and point metrics within absolute 1e-12. New uncertainty bounds need not reproduce E3 because the primary testing family is different. An unexplained control mismatch blocks interpretation.

Save immutable run IDs, approved plan/config and contract/input hashes, all relevant source snapshots **including the entrypoint**, environment, allowlist/guard receipts, fitting/evaluation IDs, candidate identity maps, complete candidate tables, selected matrices and forecasts, outer freeze, reports/figures and independent audit receipts. Old source hashes must remain unchanged. Update the stable deliverable alias only after successful audit and fresh replay.

## 13. Execution budget and stopping rules after approval

Proposed limits: CPU only, at most two workers, numerical-library threads pinned to one per worker, peak RSS <=8 GiB, combined new primary/replay artifacts <=5 GiB. Resource/schema pilot <=300 seconds; each full fitting/evaluation/audit/report execution <=3,600 seconds, with one separate fresh replay under the same cap. E3 used about 533 seconds; E4 has about 2.61 times as many logical candidate views, which is not a guaranteed runtime ratio.

Profile the first predetermined inner fitting role across both horizons and all declared candidates to project runtime/storage. This pilot is for engineering capacity, not choosing a scientific method. Do not inspect pilot wins to alter parameters. Use bounded batches and persisted candidate tables; do not hold the full experiment's ID-origin grid in memory. Audit candidate results in chunks.

Stop if input/source identity changes, final-test isolation fails, probability/case/control checks fail, the projected/full resource cap is exceeded, or an independent audit cannot reconstruct the selection. Do not silently reduce folds, candidates, cases, multipliers or required controls to finish. No-feasible-candidate is an expected scientific outcome and must not trigger extra search.

A fresh full replay must reproduce numerical tables within absolute 1e-12 and figures under the pinned environment. Visually inspect plots/maps and verify local report links. Deliver negative, neutral or favourable findings under the same reporting standard. No commit/push is included.

## 14. Requested review decision

The proposed decision is whether to approve: the 252-triple joint grid with rho fixed to 1; both-reference H90/K90 internal constraints; strict inner Brier adoption check; explicit local-anchor fallback without a success claim; the unconstrained Joint diagnostic; unchanged controls/evaluation; two-reference zero-loss outer acceptance; and the bounded independent implementation, execution, audit and replay.

**The user approved this plan. Independent implementation, execution, audit and replay are authorised. The next gate is user review of audited results; no automatic model replacement, research-stage closure, final-test access, commit or push is authorised.**
