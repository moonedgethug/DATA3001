# Stage 2 — Adaptive B2/B1 Shrinkage Engineering Proposal

**Version:** E1, 30 October 2026. **Status:** user approved the complete E1 engineering plan and authorised independent development, execution and result audit. Stage closure remains subject to user review.

The user explicitly chose to reintroduce B1 as the common reference and compare a weight shared across origin cells with a weight varying with origin-cell support. This supersedes the earlier preference against using B1 for this comparison only. It does not approve neighbour sharing, probability sharpening or drifter reweighting. The [Research Stage Ledger](research_stage_ledger.md) records approved decisions; this document is the approved E1 implementation specification.

## 1. Question, comparators and unchanged scope

**Question:** relative to a newly fitted fixed-weight B2/B1 control, can support-adaptive borrowing improve held-out probability predictions while reducing the number of cells in a useful prediction region?

Use three prespecified estimators: B2, Fixed-B2/B1 and Adaptive-B2/B1. Retain B2 as the frozen scientific baseline. Recompute all three estimators on the same data and evaluation cases; do not compare new scores directly with old unrestricted-endpoint experiments.

Continue S1's final cleaned v7 data, frozen R/D geometry and 1-degree indexes, annual-pooled scenario, independent 7/30-day predictions, stopped first-observed-exit target E, equal eligible hourly-pair weighting, whole-ID development validation and locked final test. No predictors other than origin cell and horizon are introduced.

No neighbour/distance/displacement borrowing, time/environmental conditioning, velocity categories, M1 propagation, MDN, destination-dependent training weights, probability-power transformations, new physical reachability assumptions or canonical-data edits. The models remain direct R-to-D-plus-E horizon tables.

## 2. Reference distribution and adaptive rule

For each fitting-ID set T and horizon h, let N_ij be the qualified count from origin i to destination j, and N_i its row total. All counts below come only from T.

For supported rows, B2 is p_ij = N_ij / N_i. The common B1 reference is

`q_j = sum_i N_ij / sum_i N_i`.

The sums include all eligible R origins in the fitting set, including the target origin, with original pair multiplicities. B1 uses exactly the same stopped outcomes and destination index as B2. It is not reconstructed from historical fitted B1 outputs. Its empirical zeros remain zero; no uniform floor is added.

Both blends take the form

`p_blend(i,j) = (1 - lambda_i) * p_ij + lambda_i * q_j`.

- **Fixed:** lambda_i = a, shared across supported origins for the given horizon and fit.
- **Adaptive:** lambda_i = tau / (N_i + tau). Smaller N_i gives greater borrowing at a fixed positive finite tau. This relation is a hypothesis to test, not an established reliability rule.

For a reproducible, equally sized parameter search, use a in `{0, 0.05, ..., 1}` for each family. For Adaptive, calculate m as the median positive N_i over fitting origins at that horizon and set `tau = m*a/(1-a)` for 0 < a < 1. Thus a is Adaptive's borrowing weight at a median-support row. Recompute m inside every inner, outer and all-development fitting role; never use held-out support to set it.

Implement Adaptive endpoints explicitly: a=0 is B2; a=1 is B1 on supported rows. For interior a, the equivalent numerically stable rule is

`lambda_i = m*a / ((1-a)*N_i + m*a)`.

The reference-support scaling keeps the parameter grid interpretable as training-set size changes. Each family/horizon has one selected scalar; Adaptive does not fit a separate free parameter for every cell. This is a bounded pilot search, not proof of a continuous global optimum. No post-result grid expansion is included.

N_i is a pair-count scale, not an independent sample size. Report distinct fitting-ID count and largest-ID share alongside N_i and lambda_i. Overlapping hourly pairs and a reference learned from the same fitting data preclude treating this procedure as an independently informed, fully specified Bayesian posterior. It is a regularized point estimator with a Dirichlet posterior-mean form, not a claim of calibrated Bayesian credible intervals. Zero q_j also requires care before assigning it a proper full-state Dirichlet interpretation. See the [UW transition-matrix inference notes](https://faculty.washington.edu/yenchic/26A_stat516/Lec6_MC_Inf.html).

## 3. Unsupported rows and conserved probability

To isolate the effect of weight allocation, all three estimators use the same B2-supported-row mask. When N_i=0, mark the prediction unsupported and omit standard Brier for every estimator, including the a=1 endpoint. Report its pair/ID counts and proportions. B1-only fallback for an entirely unsupported row is explicitly outside this comparison, even though the global reference may exist.

For supported rows require finite, nonnegative probabilities and total D-plus-E mass one within 1e-12. Unresolved is bookkeeping for unsupported rows, not an additional physical destination. Reject unexplained mass errors. If an entire fitting horizon has no eligible counts, stop with a diagnostic rather than inventing a reference distribution.

No small-probability clipping, top-K truncation, renormalization of displayed cells or new tail deletion is allowed. At an interior positive blend weight, the positive-probability support is the union of the B2 and B1 supports. Adaptive weights therefore need not reduce the number of all positive-probability cells.

## 4. Nested whole-ID validation and selection

Reuse the five S1 outer-fold ID assignments without alteration. For outer holdout k, the other four original fold groups form four inner validation groups: for each l != k, fit excluding both k and l, and validate on l. Rebuild both B2 and B1 and Adaptive's m inside each fitting set. Save fitting and evaluation ID memberships.

Evaluate the 21 prespecified parameter values for each family and horizon on the same eligible, supported inner out-of-fold cases. Select the minimum pair-weighted standard Brier; ties within 1e-12 select the smaller a. Count unsupported inner cases explicitly and verify the common mask across all candidate values and families. Region size, region hits and outer outcomes do not select parameters.

Refit bases on the four outer-training groups, recompute m there, apply the selected parameter and evaluate only the held-out group. Save B2, Fixed and Adaptive forecasts for each of the five outer folds at both horizons. All eligible outer cases are accounted for exactly once.

For all-development illustrative candidates, select parameters using five-fold base out-of-fold predictions on development IDs, then refit B2/B1 on all development IDs. This final tuning score is not an independent estimate of the refitted candidates' performance. Report the nested outer evaluation separately. There is no final-test access.

## 5. Scores, region definitions and comparison denominators

**Selection and primary evaluation:** standard unnormalised multiclass Brier,

`BS(p,y) = 1 - 2*p_y + sum_j p_j^2`,

including all D states and E. Do not import or substitute historical failure-penalised S, geographic loss or a composite loss. Aggregate with original eligible-pair multiplicities, not equal fold, ID or origin weights. Report eligible, evaluable and unsupported counts together.

**Main size diagnostic:** the 90% probability region. Sort positive-probability physical outcomes, including E, by decreasing probability; take the shortest prefix reaching at least 0.90 and retain all outcomes tied at the cutoff within the declared absolute probability tolerance 1e-12. Report actual included probability, observed region-hit rate, pair-weighted mean number of D cells, and whether E is included. E is scored as an outcome but never counted as a geographic cell. If E is present in any outcome/region, report that contribution separately so a zero-cell exit region is not claimed as concentrated geographic localization. No renormalization to D-only mass is allowed.

**Matched-budget diagnostic:** expected held-out hit rate for the highest-ranked K D cells, for K in `{1, 5, 10, 20, 50, 100, 200, 500, 1000, number_of_D_cells}`, deduplicated and bounded by the frozen D index. Evaluate on available cases whose true state is in D; report E cases separately and retain them in primary Brier. These curves are diagnostics, not parameter-selection criteria.

Keep K exact without selecting ties using held-out truth or arbitrary geographic order: select all cells strictly above the Kth-probability tie group, and treat the remaining slots as a uniform random subset of that group. Compute the analytical inclusion probability for a true cell in that tie group; no random model fit is needed. Include the frozen zero-probability D cells when K reaches them, and flag those points as involving an uninformed zero-probability tie. This convention changes neither the forecast probabilities nor Brier. It prevents arbitrary zero-tie ordering from creating apparent localization skill. Save the boundary probability, tie size and remaining slots so the calculation is auditable.

Also report positive-probability cell count, true-outcome zero-probability fraction, predicted/observed E, and per-origin support, weight, Brier and region diagnostics. Distinguish probability-region cell count from geographic area: equal-degree cells are not equal-area cells. No geodesic-distance score is introduced.

## 6. Uncertainty and scientific conclusions

Primary contrast: Adaptive minus Fixed. Secondary contrast: Adaptive minus B2. Report each horizon separately; the two horizons have different eligible populations.

Use 200 paired whole-ID bootstrap resamples of the saved outer out-of-fold predictions, seed 20261030, with the same ID multiplicities applied to all three estimators. Recompute pair-weighted Brier, region-hit rate, mean region cell count and prespecified budget-hit diagnostics in each resample. Preserve the common comparison denominators; report undefined resamples. Report differences and 2.5/97.5 percentile intervals. These condition on saved fits and omit refitting, parameter-selection and research-selection uncertainty; they are exploratory development evidence, not multiplicity-adjusted confirmatory tests.

Do not call fewer region cells alone an improvement. The proposed practical screen for the stated goal is lower Brier, a smaller mean 90% region, and no decrease in the observed region-hit point estimate relative to Fixed, assessed separately at 7/30 days. Matched-budget curves show whether endpoint ranking also improves. Report trade-offs if any condition fails; do not invent an acceptable coverage-loss margin after seeing results. Point-estimate success with uncertain differences remains tentative. B2 comparisons must remain visible even if Adaptive improves on Fixed.

The experiment can be completed with a null or negative result. Its conclusion concerns this reference, adaptive rule, parameter grid and validation population only; it cannot establish that adaptive borrowing generally succeeds or fails. User review is required before recording S2 closure or expanding to S3.

## 7. Independent run, reuse and implementation boundaries

Create a distinct `adaptive_b2_b1_<UTC_run_id>` result/provenance run. Retain the sealed S1 run `empirical_b2_20261029T121555_976173Z` and all historical artifacts unchanged.

Reuse only the verified v7 qualification/count cache and fixed ID assignments already allowlisted in S1, frozen indexes/geometry/contracts, and audited pure utilities. The core count input remains `results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet`; folds remain `results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv`. Repeat source/hash/development-ID and qualification checks. Do not read historical fitted outputs or selected weights as fitting/tuning inputs, inherit old combined-run settings, or launch old model pipelines.

Fresh B2 predictions may be checked against frozen S1 only in a separate, explicitly allowlisted post-computation regression audit, after they have been generated from counts; S1 predictions do not supply model inputs. An incompatibility must be investigated rather than reconciled by modifying sealed S1 outputs.

Keep pure estimation/selection separate from input guards, run I/O and reporting. Reuse `baselines/empirical_b2.py`'s pure mathematical functions where appropriate. If shared read-only input verification is extracted from the S1 runner, keep it under `common/`, preserve S1 behavior and run its regression tests; do not let the new runner depend on or execute the old runner. Do not reorganise unrelated modules or add implementations to `_compat/`.

| Proposed location | Responsibility |
|---|---|
| `src/data3001/modelling/baselines/adaptive_b2_b1.py` | B1 reference, fixed/adaptive blends and parameter selection |
| `src/data3001/modelling/baselines/run_adaptive_b2_b1.py` | Guarded inputs, nested ID roles, evaluation and immutable run |
| `src/data3001/modelling/baselines/adaptive_b2_b1_report.py` | English report, matched maps, weights and budget curves |
| `src/data3001/modelling/common/prediction_regions.py` | Pure region/budget diagnostics if not already provided by an audited helper |
| `src/data3001/modelling/common/qualified_count_inputs.py` | Shared input verification only if extraction is required |
| `configs/adaptive_b2_b1.json` | Explicit approved settings, grid, masks, tie rules and assets |
| `tests/test_modelling_adaptive_b2_b1.py` | Independent scientific/validation semantics |
| `tests/test_modelling_prediction_regions.py` | Region size, exact budget and tie semantics |
| `docs/adaptive_b2_b1_results.md` | One human-readable scientific results account after execution |

## 8. Deliverables, checks and bounded execution

Deliver configuration and approved-plan snapshots, input/code/environment identities, all inner/outer ID roles, inner candidate scores, selected parameters, B1/B2 bases, outer/final blended matrices, fitting support and applied weights, held-out scores/regions, horizon/origin summaries, paired uncertainty and audits. All outputs distinguish inner tuning, outer evaluation and all-development candidates.

Provide matched maps for all three models at 7/30 days using one origin chosen solely from fitting support with the S1 rule: largest minimum distinct-ID support across both horizons, then smallest cell ID. Use the same probability colour scale across the compared models at a horizon and show 90% regions, E/unresolved mass and support. Also provide weight-versus-support and matched-budget-hit plots. Maps illustrate fitted candidates; numerical skill claims come from held-out evaluation.

Before experiment execution, verify hand-computable blends/Brier; a=0 and a=1 endpoints; Adaptive monotonicity in N_i and equality to a at N_i=m; reference and median isolation from held-out IDs; absence of new states/floors; common unsupported masks; equal-pair aggregation; region cutoff ties; exact-budget expected tie hits including zero ties; and E accounting. Run relevant S1/shared semantic tests, not unrelated expensive model training.

After execution, independently reconstruct selected parameters, representative matrices and score differences from exported counts/roles; reconcile every eligible case and probability row; compare freshly generated B2 to frozen S1; inspect final maps and tables; and replay with the same inputs/configuration to check deterministic numerical outputs within 1e-12, excluding run IDs/timestamps. Do not treat a passing structural check as proof of predictive benefit.

Set a 30-minute compute cap for each complete execution. Stop and diagnose if exceeded rather than expanding the search or resuming old work. No GPU training is required. No commit/push, final-test access, stopped-neighbour restart, S2 closure or next-stage execution is implied.

**Authorisation:** the user confirmed this complete E1 plan, including the pair-count support schedule, 21-value searches, shared unsupported mask and region/budget diagnostics. Development, independent execution and audit may proceed. The next user gate is review of the results and any proposed S2 conclusion or expansion.
