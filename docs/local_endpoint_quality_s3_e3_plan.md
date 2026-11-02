# Step 3 — E3 Neighbour Endpoint Information Quality

**Version:** S3 E3 v1, 31 October 2026 (Australia/Sydney).
**Status: USER APPROVED — INDEPENDENT DEVELOPMENT, EXECUTION AND AUDIT AUTHORISED.**

The user confirmed this S3 E3 v1 plan and authorised independent development, execution, audit and visual comparison. Its scientific definitions, finite grids, validation and acceptance rules are locked. Preserve earlier experiments and all existing uncommitted work. Scientific retention and stage closure remain later user decisions.

## 1. Question and proposed decision

**Where Things End Up:** given an object already in a specified 1-degree origin cell at an arbitrary qualified prediction time, predict its stopped destination distribution after 7 or 30 days, including absorbing E for first observed exit from the frozen transport domain D.

**Question:** does selectively allocating neighbour endpoint information improve held-out Brier, while preserving actual hits and a useful fixed-90% probability region?

The proposed model is **LocalEndpointQuality**. It changes the neighbour reference used by LocalEndpointAdaptive. It first gives more relative influence to neighbours with similar historical destination distributions. It then optionally reduces information about destinations that are simultaneously locally unseen, rare in the original neighbour distribution, and supported by fewer than three neighbour drifters. The total borrowing parameters are anchored to the freshly selected LocalEndpointAdaptive control in each training partition, rather than jointly expanded with the new parameters.

The user's three ideas become the following testable hypotheses:

| Historical evidence, using fitting IDs only | Proposed treatment | Interpretation limit |
|---|---|---|
| Local and neighbouring cells put substantial probability on shared endpoints | Increase the relative contribution of neighbours with greater distribution overlap | Agreement is evidence of relevance, not proof of a common current or correct probabilities |
| A locally rare endpoint also occurs in neighbours | Keep it eligible for borrowing; never suppress it merely because it is locally rare | It already has positive B2 probability; neighbouring evidence may strengthen or weaken its estimated probability |
| An endpoint is locally absent, rare in neighbours, and supported by only one or two neighbour IDs | Compare retaining, halving, and rejecting this particular borrowed contribution | Rarity does not prove an observation is spurious; held-out outcomes still count against a mistaken rejection |
| A locally absent endpoint has substantial neighbour probability OR at least three neighbour IDs | Keep it eligible, even though B2 has never seen it | Borrowing must retain a route for discovering new destinations |

The third rule is deliberately narrower than "ignore every locally unseen endpoint." There is no deletion of training records or evaluation outcomes. Rejection, when selected, changes the fitted probability estimator and may create additional zero probabilities; it is not cosmetic cropping of a map. The rejected mass has an explicit destination in the formula below.

## 2. Evidence motivating this proposal

Checked against [S3 E2 results](local_endpoint_adaptive_s3_e2_results.md), primary run `local_endpoint_adaptive_s3_e2_20261030T135819_234829Z`:

| Days | Model | Brier | Mean K90 | H90 |
|---|---|---:|---:|---:|
| 7 | LocalEndpoint | 0.958288 | 27.36 | 88.19% |
| 7 | LocalEndpointAdaptive | 0.959104 | 27.22 | 88.24% |
| 7 | Fixed | 0.962457 | 42.71 | 89.96% |
| 30 | LocalEndpoint | 0.993751 | 104.68 | 76.28% |
| 30 | LocalEndpointAdaptive | 0.993452 | 105.34 | 76.84% |
| 30 | Fixed | 0.994931 | 133.86 | 77.59% |

The existing adaptive rule changes how much to borrow, but leaves the raw pooled neighbour distribution unchanged. Its modest 30-day improvement does not establish that all neighbouring cells supply equally relevant information. The local models also still have lower point coverage than Fixed. Reducing rare borrowed destinations could worsen that deficit: smaller K90 alone would not establish success.

Step 2 E2's [Info arm](b2_b1_e2_plan.md) already reallocated global B1 probability between all locally seen/unseen destinations. This proposal is different: eight-neighbour sources, explicit between-neighbour similarity, distinct-ID support for a narrowly defined weak-unseen subset, and explicit return of reduced D mass to B2. It is still a related regularisation hypothesis, not independent corroborating evidence. Historical equal-pair scores are not directly comparable to the present equal-ID/equal-cell scores.

## 3. Frozen scope, inputs and output states

Keep cleaned release `per-drifter-cleaned-20261017-v7`, annual pooling, 1-degree states, qualified hourly observation pairs, frozen R/D geometry, and separate direct stopped 7/30-day targets. Keep raw pair-frequency training and equal-ID-within-cell, equal-cell evaluation. Do not introduce equal-ID training, velocity, seasons, environmental predictors, displacement, trajectory alignment, additional neighbour rings, new physical masks, or a three-way global-plus-neighbour mixture.

The English contract is `docs/contract/data_contract_v1.0.xlsx`; its SHA256 was rechecked during proposal preparation: `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`.

Future isolated input allowlist:

- Qualified counts: `results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet`.
- Source-keyed qualification/exit labels and provenance from that sealed input run, to verify eligible counts.
- Whole-ID folds: `results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv`.
- Current manifests, frozen state index, R/D and pinned land assets for integrity and descriptive maps.
- Sealed S3 E2 control artifacts for regression only after new outer predictions are frozen.

No hourly trajectory reconstruction or translated-path cache is needed. The 517 locked final-test IDs remain excluded from fitting, tuning, diagnostics and maps; do not read their trajectories. Do not resume the stopped M1-neighbour run or any MDN work.

Expected unchanged development populations:

| Days | Qualified pairs | Evaluation IDs | ID-cell units | Evaluated origins |
|---|---:|---:|---:|---:|
| 7 | 303,288 | 385 | 4,451 | 37 |
| 30 | 268,998 | 337 | 3,974 | 37 |

There are 3,224 development IDs and 54 indexed origins. Report origins without eligible evaluation cases, rather than treating them as successfully predicted. Stop on an unexplained population mismatch. Drifter transport remains the proxy; this experiment does not validate oil weathering, windage or object-specific beaching.

## 4. Counts, neighbours and support

Rebuild every quantity separately for each horizon h and fitting-ID set F. Let `n(d,i,j)` be the qualified pair count for fitting drifter d, origin i and stopped destination j in D plus E. Define:

- `N_ij = sum_{d in F} n(d,i,j)`; `N_i = sum_j N_ij`; `p_i(j) = N_ij/N_i` for supported B2 rows.
- `A(i)` is exactly the eight adjacent 1-degree cells, excluding i, intersected with the frozen R-origin index. Preserve longitude wrapping and latitude bounds. Donors must actually start in R and qualify at the same horizon.
- `q_i(j) = sum_{k in A(i)} N_kj / sum_{k in A(i)} N_k`: the original raw-pair pooled neighbour reference.
- `L_i`: distinct fitting drifters at i. `M_i`: distinct fitting drifters in the union of A(i), deduplicated across neighbour cells.
- `C_ij`: distinct fitting drifters reaching j from at least one cell in A(i), deduplicated across cells and repeated observations. Also record local endpoint-ID support and per-neighbour ID support.

A drifter producing 100 repeated pairs to j contributes 100 to the raw frequency count but only one to C_ij. An ID visiting several neighbours contributes only one to M_i or C_ij. Local/neighbour overlapping IDs are retained; their intersection, Jaccard overlap and largest-ID pair shares must be reported. These support counts are not formal independent sample sizes.

Keep the same B2 support mask for all six models. If N_i=0, report an unsupported row and unavailable standard Brier/K90/H90; do not rescue it with neighbours or global B1. If B2 is supported but no neighbour pairs exist, use q_i=p_i and actual borrowing zero.

## 5. Similarity and allocation among neighbours

Similarity compares complete **geographic destination distributions**, not whether there is just one common endpoint. Define the within-D counts and conditional distributions:

`N_iD = sum_{j in D} N_ij`; `p_iD(j) = N_ij/N_iD` when N_iD>0.

For each neighbour with N_kD>0, define p_kD similarly. Use overlap:

`S_ik = sum_{j in D} min(p_iD(j), p_kD(j))`, with `0 <= S_ik <= 1`.

S=1 means identical geographic endpoint probabilities; S=0 means no shared geographic support. Large shared probability contributes more than a tiny shared endpoint. E is excluded from this similarity calculation: shared exits alone should not make two geographic distributions appear similar. Conditional D distributions are internal calculations; the issued forecast still contains its full E probability.

"Shared endpoint" means the same frozen 1-degree destination cell. Adjacent but different destination cells do not count as shared in this experiment. No endpoint-distance smoothing is introduced implicitly.

The proposed relative neighbour weight is:

`w_ik(eta) = N_kD * [(1-eta) + eta*S_ik] / sum_{l in A(i), N_lD>0} N_lD * [(1-eta) + eta*S_il]`.

Use `eta in {0, 0.5, 0.9}`. Eta=0 preserves original pair pooling. Larger eta penalises less similar neighbours; eta never reaches 1, so a zero-overlap neighbour retains a positive weight if it has D pairs. If all neighbours have the same similarity, their relative weights remain the original pair weights. The rule does not create additional drifter balancing: N_kD remains the baseline contribution, with ID support used separately for borrowing and weak-endpoint classification.

For illustration, with equal pair totals and similarities 0.8 and 0.2, eta=0.5 gives weights 0.60 and 0.40; eta=0 gives 0.50 and 0.50. These are hand calculations, not experiment results.

Preserve the original neighbour exit mass `e_i=q_i(E)` exactly and build:

`q_iS(E)=e_i`; `q_iS(j)=(1-e_i)*sum_k w_ik(eta)*p_kD(j)` for j in D.

Thus eta=0 reproduces q_i including E, even if different donors have different exit frequencies. Changing geographic donor weights must not silently change the E mixture. If the local row has N_iD=0, or neighbours have no D pairs, bypass both quality modifications and retain q_i; record the reason. Empty donors retain the earlier B2 fallback.

Similarity is estimated from finite local history. It can mistakenly reward agreement with a noisy B2 row, and the raw-count baseline can still be dominated by a long record. The limited eta grid, neutral candidate and whole-ID validation test this risk; they do not prove it absent. No additional support shrinkage parameter, distance kernel or per-neighbour free coefficient is proposed in this first quality experiment.

## 6. Narrow weak-unseen endpoint rule and probability conservation

When both local and neighbour D distributions exist, classify endpoints using the **original** reference, before similarity reweighting:

`q_iD(j) = q_i(j)/(1-e_i)`.

The weak-unseen set is:

`W_i = {j in D : N_ij=0, 0<q_iD(j)<tau, C_ij<m}`,

with fixed proposed thresholds **tau=0.01** and **m=3**. A probability exactly 1% or support of exactly three IDs is retained. These are reviewable operational definitions, not statistically established noise cutoffs. They are fixed before execution and will not be tuned or revised after inspecting E3 results. Using the original q keeps endpoint membership independent of eta.

Many individually rare destinations can collectively carry substantial probability. Do not assume W_i has negligible total mass; report its full mass and the resulting delta_i. The retained-fraction grid tests this restriction, and a smaller region cannot excuse lost held-out coverage.

Consequences:

- Every locally observed endpoint is exempt from this gate, regardless of how rare it is or how few local IDs support it.
- A locally absent endpoint is exempt if its original neighbour D probability is at least 1%, OR at least three distinct neighbour IDs support it.
- An endpoint represented by one ID with many repeated observations is not automatically weak-unseen: it must also meet the probability threshold. Report such concentration rather than pretending this rule solves all sampling dependence.
- E is never in W_i. Missing, unsupported and E outcomes are not interchangeable.

Use `rho in {1, 0.5, 0}` as the retained fraction of the weak-unseen borrowed contribution. Set `g_ij=rho` on W_i and 1 on other D endpoints. Define:

`delta_i = sum_{j in D} (1-g_ij)*q_iS(j)`.

The quality reference is:

`q_iQ(E)=e_i`;

`q_iQ(j)=g_ij*q_iS(j) + delta_i*p_iD(j)` for j in D.

The reduced D mass goes back to the local B2 **conditional-D distribution**. It is not dropped, assigned to U, moved to E, or renormalised over a chosen display area. Nonnegativity, total mass one, original E mass and total D mass must all hold. Local-D-empty rows bypass the transformation as specified above, so no undefined conditional distribution is constructed.

This is explicit endpoint-specific shrinkage. Holding the nominal total borrowing weight fixed does not mean the effective donated D contribution is unchanged: delta_i is returned to local evidence. Save delta_i and its contribution after mixing, rather than attributing all effects solely to neighbour ranking.

At rho=1 there is no endpoint gate. At rho=0, weak-unseen destinations can have zero final forecast probability; this is a substantive prediction assumption, whose errors remain in Brier and H90. Shared rare endpoints are never directly gated, but their probabilities are not guaranteed to increase relative to the original pooled model: source reweighting and probability normalisation still matter.

Hand-check example without E: local B2 over A/B/C/T is `(0.700, 0.295, 0.005, 0)` and q_iS=q_i is `(0.600, 0.390, 0.005, 0.005)`. If T has two donor IDs, it is weak-unseen. With rho=0, delta=0.005 and q_iQ becomes `(0.603500, 0.391475, 0.005025, 0)`. The locally rare C remains; the sum is one. A held-out arrival at T is still scored and may reveal that rejecting it was wrong.

## 7. Total borrowing weight and controls

Preserve S3 E2's distinct-ID relative-support rule. For supported rows with M_i>0:

`r_i=M_i/L_i`; `r_med=median(r_i)` over all fitting-supported indexed origins with positive M_i at the same horizon; `z_i=r_i/r_med`.

`lambda_i(a,gamma)=a*z_i^gamma / [(1-a)+a*z_i^gamma]`.

Use the same exact branches: no donors gives actual lambda=0; a=0 gives B2; a=1 gives the reference; gamma=0 gives constant borrowing; z=1 gives lambda=a. If there are no positive ratios, record that case, use scale placeholder 1 and return B2. Invalid/nonfinite inputs are errors. Support and the scale are computed from the original fitting pool; do not recompute them after donor reweighting or endpoint gating.

The new forecast is:

`P_Quality(i,j)=(1-lambda_i)*p_i(j)+lambda_i*q_iQ(j)`.

Its a/gamma are the selected **LocalEndpointAdaptive control's parameters for that horizon and training partition**, as defined in Section 8. They are not copied from a historical all-development run. At matched a/gamma, quality adjustment preserves forecast E exactly.

| Model | Reference and weight | Parameter grid per horizon |
|---|---|---|
| B2 | Local raw-pair empirical row | One |
| Fixed | Original global B1; constant weight a | a=0,0.05,...,1 |
| Adaptive | Original global B1; original pair-support adaptive weight | Same 21 a values |
| LocalEndpoint | Original eight-neighbour reference; constant a | Same 21 a values |
| LocalEndpointAdaptive | Original neighbour reference; ID-relative-support lambda | 21 a values x gamma in {0,0.5,1,2} |
| LocalEndpointQuality | Quality reference q_iQ; anchor a/gamma inherited from the freshly selected LocalEndpointAdaptive | eta in {0,0.5,0.9} x rho in {1,0.5,0}: nine additional settings |

Global Adaptive remains `w_i=m_N*a/[(1-a)*N_i+m_N*a]`, where m_N is the fitting median positive local pair count. Do not replace its support with IDs. Global B1 still pools eligible R-origin raw pairs, including the target origin.

The quality grid contains the unchanged anchor at eta=0/rho=1. Fixing anchor parameters makes this a bounded test of reference quality under the existing borrowing rule; it does not find the best joint a/gamma/eta/rho model. Joint retuning, new thresholds and new feature sources are outside E3.

Two mandatory mechanism ablations use the selected anchor and selected quality parameters, with no additional selection: **similarity only** sets rho=1, and **weak-endpoint gate only** sets eta=0. Both are already represented in the nine-setting grid. Report them as diagnostics, not as extra post-hoc winners. They isolate the effect of removing one component at the selected settings, not its best possible separately tuned performance.

## 8. Nested whole-ID validation and parameter selection

Keep five outer whole-ID folds and four inner groups. At each horizon and outer fold k:

1. Exclude every ID in k from all fitting, thresholds, similarity, support and selection.
2. For each remaining group l, fit on IDs outside k and l. Rebuild counts, all reference rows, ID sets, E/D conditionals, similarities, weak-unseen sets and medians from these fitting IDs only.
3. Evaluate the original 148 control-grid identities on l. Pool all four inner ID-cell tables with the primary weighting before selection. Choose all five controls by minimum primary Brier; preserve their existing ties (smaller gamma then smaller a for LocalEndpointAdaptive; smaller a for other tuned controls).
4. Freeze the selected LocalEndpointAdaptive a/gamma as this outer training partition's anchor. Evaluate each of the nine quality settings on the same four inner validation groups using that anchor and each group's own fitted reference/support quantities. Select lowest pooled primary Brier; within absolute 1e-12 of the best, prefer smaller eta, then larger rho. No K90/H90 tuning or feasibility filter is added.
5. Refit on the four outer training groups. Apply the selected controls, the quality model and its two ablations to outer group k once. No own-outer outcome may choose a parameter or rule.

Anchor and quality selection reuse inner validation data, so inner improvements are selection results, not independent evidence. The untouched-for-that-fit outer fold evaluates the complete two-stage selection procedure. Nesting guarantees that the best inner quality candidate is no worse than its anchor up to tie tolerance; it makes no outer-performance guarantee.

All models use identical eligible cases and B2 support masks. Pool outer ID-cell outputs for the final development comparison. Freeze/hash outer forecasts, support/masks, selections, weights, scores and ablations before all-development illustration selection. Only then select an all-development anchor from the five base outer-fit validation tables, select nine quality settings using that anchor on those same tables, and refit on all development IDs. Those final maps are illustrations, not another held-out experiment.

There are 26 fitting roles (20 inner, five outer, one all-development) and 25 candidate-validation roles (20 inner and five for all-development selection). Per horizon/validation role: 148 unchanged control-grid identities plus nine anchor-conditioned quality identities = 157. Total: **7,850** identity/horizon/role evaluations. Under the unchanged roster, expect **6,613,625** candidate ID-cell records; verify rather than forcing the count. Selected outer scores and ablation summaries are separate outputs, not extra search candidates.

Freshly fit and select every control. After the outer freeze, regress all five controls against sealed S3 E2: 30 selected matrix files (six roles x five models), selections, common cases, primary weights and point metrics must agree within absolute 1e-12. A mismatch stops scientific interpretation until explained. Do not use old prediction files to manufacture regression success. New interval bounds need not match S3 E2 because the screening family and replicate count differ.

## 9. Primary evaluation and uncertainty

For each horizon, average qualified times within a held-out drifter/origin unit, average drifters equally within each evaluated origin, then average origins equally. An individual pair has weight `1/(number_of_evaluated_origins * held_out_IDs_in_origin * pairs_for_that_ID_origin)`, multiplied by multiplicity for compressed records. Use this same estimand for tuning, Brier, K90 and H90. An ID can have a vote in several cells; this is not one total vote over the entire ocean.

Use standard complete-distribution multiclass Brier on D plus E:

`BS(p,y)=1+sum_j p(j)^2-2*p(y)`.

No spatial or composite loss. Score every supported held-out observation, including all zero-probability truths and every weak-unseen outcome. Pair-weighted summaries remain secondary sensitivity descriptions, with no influence on selection or acceptance.

Use nominal mass **0.90** for every forecast. Sort the complete distribution, take the shortest prefix reaching 0.90, and include all cutoff ties under the existing 1e-12 convention. Retain complete fitted tails in stored forecasts and maps. E counts toward region mass and hits, but not geographic cell count.

- **K90:** primary-weighted mean number of geographic cells in the region, not square-kilometre area.
- **H90:** primary-weighted actual region hit rate, not the nominal probability mass. Show H90-0.90 descriptively.
- Also report issued region mass, all positive geographic cell counts, zero-truth-probability rate, E prediction/observations/inclusion, unsupported/U bookkeeping and the rate of truths outside the original B2-plus-neighbour support union.

Prespecified main contrasts: LocalEndpointQuality minus **LocalEndpointAdaptive, LocalEndpoint and Fixed**, at each horizon. B2/global Adaptive and the two component ablations remain descriptive comparisons.

Use **20,000 paired positive whole-ID multiplier replicates**, PCG64 Exp(1), seed **20261031**, over sorted development IDs. Share an ID's multiplier across all its cells, horizons and models. Keep fits and within-ID means fixed, renormalise IDs within each cell, and keep cells equally weighted. Use linear quantiles and save draw identity/hash. Report ordinary 95% intervals plus directional bounds across 18 prespecified screens (three references x three metrics x two horizons): upper quantile `1-0.05/18` for Delta Brier/K90, lower quantile `0.05/18` for Delta H90.

These are approximate conditional development screens, not a formal final-test superiority/non-inferiority guarantee. They omit refitting uncertainty, dependence from overlapping training sets, shared ocean forcing and repeated project decisions using this development set. The new run does not turn previously studied development data into an untouched test set. A confidence interval spanning zero is not proof of non-deterioration.

## 10. Acceptance, interpretation and stopping

Delta means new minus the named reference; U_B/U_K and L_H are the directional bounds above. Epsilon=1e-12 is arithmetic tolerance, not permission for scientific loss. Apply decisions separately at 7 and 30 days.

| Decision | Required evidence |
|---|---|
| Engineering complete | Input isolation, formulas/probability checks, five-control regressions, independent audit, outputs and fresh replay pass; no predictive win is required |
| Point Brier improvement | Delta Brier < -epsilon; report all other effects without claiming uncertainty support |
| Brier improvement supported by the conditional screen | Point improvement and U_B < -epsilon |
| Coverage-preserving information gain over LocalEndpointAdaptive | Brier support against LocalEndpointAdaptive; point Delta H90 >= -epsilon and L_H >= -epsilon; report any K90 increase as a trade-off |
| No-region-expansion quality gain over a named reference | Brier support; point Delta H90 >= -epsilon and L_H >= -epsilon; point Delta K90 <= epsilon and U_K <= epsilon |
| Strictly smaller 90% region without quality loss | Previous row plus point Delta K90 < -epsilon and U_K < -epsilon |
| Preferred overall candidate for user review | Meaningful quality-induced forecast changes; no-region-expansion quality gain against all three prespecified references: LocalEndpointAdaptive, LocalEndpoint and Fixed |
| Neutral or inconclusive | Neutral settings selected, no effective reference change, or bounds fail to establish the required directions; retain the result without inventing a benefit |
| Adverse trade-off | Smaller K90 accompanied by worse Brier or lower H90; quantify and do not call it a quality-preserving improvement |

The strict overall label protects both existing spatial controls and the retained Fixed quality baseline. An information gain that increases K90, or fails the Fixed coverage comparison, can still be scientifically useful; label its narrower achievement and do not call it an overall replacement. Improvements at one horizon do not establish improvement at the other.

No arbitrary allowed coverage loss, post-result threshold, best-fold claim or extra search is introduced. If the narrow weak-unseen rule harms hits, if neutral settings win, or if the grid boundary is selected, finish and report the bounded experiment. A negative result concerns these definitions and grids, not a proof that spatial information has reached its limit. Model retention and Step 3 closure remain user decisions.

## 11. Required mechanism diagnostics and visualisations

Save fitting-role/horizon/origin/neighbour diagnostics: N_i/N_iD, local and neighbour ID sets/counts, donor endpoint C_ij, overlap/Jaccard, largest-ID pair shares, S_ik, original and reweighted donor contributions, L/M/r/r_med/z, selected a/gamma/eta/rho, actual lambda, weak-unseen membership, delta_i, lambda_i*delta_i, fallback reasons and probability checks. Classification and support must always be fitted, never computed from held-out truth.

Use the following mutually exclusive geographic groups for diagnostic mass and observed frequency: locally seen shared (split local p_iD below/at least 1%); locally seen without neighbour support; weak-unseen W_i; other neighbour-only; and outside the local/neighbour support union. Handle unavailable D conditionals explicitly and report E separately. Reconcile these groups to the full distribution/outcome denominator.

Required views:

1. Six-model Brier/K90/H90 tables and difference plots at both horizons; K changes in cells and percent, H changes in percentage points, intervals and acceptance labels.
2. Two ablation comparisons, showing whether selected-setting changes arise from source similarity, weak-endpoint gating or their interaction. No causal claim beyond these controlled transformations.
3. Neighbour similarity versus reweighted contribution, with raw pairs and distinct-ID support visible; selection stability across outer folds; changed-row counts and total-variation distance from the anchor.
4. Weak-unseen probability before/after, redirected mass, held-out event frequency/hits, and additional zero-probability truths. Do not omit failures because they were predicted to be rare.
5. Shared locally rare endpoint probabilities and event scores before/after, including decreases as well as increases. Presence of shared history alone is not a successful prediction result.
6. Per-origin results and existing descriptive support bands (1-9/10-49/50+ fitting local IDs) and coastal/offshore strata. Use pinned geometry; report retained primary weight mass and renormalised stratum summaries. Strata do not select parameters or special rules.
7. Matched all-development full-probability maps for six models, common scale per horizon, fixed 90% outlines and explicit E/support captions. Retain the existing support/geometry-only illustration roster rule; expected origins are 44744/44742/44382. Do not substitute performance-selected cells. Include neighbour contribution and endpoint-category maps for the same origins.

No actual E outcomes occurred in the preceding eligible development comparison. Recheck and report the E denominator; if still zero, preserving exit bookkeeping does not validate exit calibration. No geographic success may be inferred solely from E hits.

## 12. Independent implementation and audit after approval

Use a new namespace **local_endpoint_quality_s3_e3**, distinct from Step 2 E3 and S3 E2. Proposed future files under `src/data3001/modelling/baselines/`: `local_endpoint_quality_s3_e3.py`, `local_endpoint_quality_s3_e3_audit.py`, `local_endpoint_quality_s3_e3_report.py`, and `run_local_endpoint_quality_s3_e3.py`; matching config, targeted tests, and `docs/local_endpoint_quality_s3_e3_results.md`.

Reuse audited pure count/reference/support/scoring/region utilities. Do not invoke an old experiment runner, rewrite old formulas, refactor unrelated modules, or overwrite sealed runs. Any minimal shared-helper change must preserve old interfaces and numeric controls. Preserve existing uncommitted work.

Pre-run checks must cover scientific boundaries as well as code structure:

- Raw multiplicities versus deduplicated ID unions and per-endpoint C; correct eight-neighbour/R/self rules; held-out-ID exclusion from every quantity.
- Similarity identity/disjointness, eta=0 exact pooled reference, equal-similarity baseline, unequal donor E rates, positive-weight floor and support-empty branches.
- Weak-unseen strict thresholds at 1% and three IDs, protection of local rare endpoints and strongly supported unseen endpoints, original-reference membership independent of eta, and validation-only endpoints remaining unseen.
- Rho=1 identity, eta=0/rho=1 exact anchor, rho=0 zeros, partial reduction, D/E preservation, redirected-mass identity, local-D-empty/all-E/no-donor cases, finite nonnegative sum-one rows.
- Hand-calculated examples; total-weight branches and inherited parameters; full zero-truth scoring; equal-ID/equal-cell aggregation; 90% ties/E semantics.
- Anchor-first selection, all nine settings, neutral tie preference, 157 candidate identities per role/horizon, 26/25 role counts and outer/all-development freeze separation.

Independently reconstruct counts/ID supports, similarities, gates, weights and candidate probabilities without calling the new production transform. Recompute candidate scores and both stages of selection; selected matrices/ablations; per-case scores/regions; weighted summaries; multiplier bounds and decision labels. Verify the 30 retained control matrices and all point metrics. Tests of structure alone do not establish valid scientific meanings.

Save immutable run IDs, proposed-then-approved plan/config snapshots, contract/input hashes, all relevant source snapshots and hashes **including the entrypoint**, environment, read allowlist/guard receipts, fit/evaluation IDs, every declared candidate result, selections, complete matrices, diagnostic tables, freezes, reports, figures, regression and audit/replay receipts. Update a stable deliverable alias only after successful audit. Do not modify existing result directories or the controlled ledger during proposal drafting.

Bounded execution proposal after approval: CPU only, at most two workers, peak RSS <=8 GiB, combined new primary/replay artifacts <=5 GiB; input/schema/resource preflight <=300 seconds; each full execution/evaluation/audit/report <=1,800 seconds and one separate fresh full replay <=1,800 seconds. Profile the first predetermined inner role for resource projection, not model success. Stream/free tables as needed without changing observations, arithmetic or candidates. Stop rather than silently reducing folds, grids or replicates when a limit or integrity check fails.

The fresh replay must reproduce numeric tables within absolute 1e-12 and figures under the pinned environment. Inspect the rendered maps and labels. Deliver the six-model comparison, ablations, mechanism findings, uncertainty, scope limits and explicit acceptance outcomes whether favourable or unfavourable.

## 13. Current review gate

The proposal asks the user to review: geographic distribution overlap; three eta values; the narrow 1%/three-ID weak-unseen definition; three retained fractions rho; explicit return of reduced D mass to B2 with E preserved; anchor-first nine-setting selection; unchanged evaluation; three-reference zero-loss screens; and bounded independent execution.

The user has approved these scientific and engineering definitions. Independent implementation, execution and audit are now authorised. The next gate is user review of audited results; no benchmark replacement, research-stage closure, final-test access, commit or push is authorised.
