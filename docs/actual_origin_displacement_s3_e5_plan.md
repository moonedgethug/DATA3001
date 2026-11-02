# Step 3 E5 — Actual-Origin Displacement: Grid, Analytic and Continuous Weight Selection

**Version:** S3 E5 v2, 31 October 2026 (Australia/Sydney).
**Status: ENGINEERING PROPOSAL FOR USER AUDIT — NOT APPROVED FOR DEVELOPMENT OR EXECUTION.**

The user has authorised revision of the proposal to compare Fixed grid versus analytic weight selection and Adaptive grid versus continuous optimisation. Both model families start at the prediction object's own known coordinates and share identical neighbour information, geometry and fallback. This document specifies four selection procedures within those two families. Preparing this document does not authorise implementation, a pilot, training, new predictions or final-test access.

**Changes from v1:** retain both original grids; add the closed-form unconstrained Fixed Brier optimum and bounded continuous Adaptive optimisation; specify a separate finite quality-feasibility search; retain five-outer/four-inner whole-ID CV; share geometry and Brier sufficient statistics; expand the declared comparison family and bound all added work. A closed-form Brier optimum is not a closed-form quality-constrained optimum. No parameter-domain expansion, loss change or prediction-region relaxation is proposed.

The research-stage ledger and earlier plans, source files and sealed runs remain unchanged. No automatic model replacement, Step 3 closure, restart of the stopped Markov-neighbour run, Git commit or publication is included.

## 1. Research question and input amendment

**Where Things End Up:** given an object's actual location x0=(longitude, latitude) inside the frozen release region R at an arbitrary qualified prediction time, predict its stopped destination distribution after exactly 7 or 30 days. First observed exit from transport domain D is absorbing E. A first-entry restriction is not introduced. Drifters remain the transport proxy.

Three questions are separated:

1. Does displacement borrowing anchored at the actual query location improve on the E1 grid-relative transfer procedure?
2. With the actual query location, donor distribution, geometry and fallback held identical, does adaptive borrowing improve on a constant nominal weight?
3. Within each family, did the original grid materially limit weight selection, and do off-grid choices improve held-out prediction while preserving quality?

For the first mechanism comparison, use the new Fixed **grid** procedure's always-unconstrained Brier winner against E1's unchanged Brier-only grid selection. This holds the selection objective and weight grid constant. The contrast changes available within-cell position information and its alignment together; it is not a pure coordinate-arithmetic effect. Using the new analytic procedure instead would also change the solver. Quality-guided comparisons additionally change selection policy and must be labelled accordingly.

For the second question, compare Adaptive grid with Fixed grid, and Adaptive continuous with Fixed analytic-assisted selection. The latter compares the declared enhanced procedures, whose search spaces and finite budgets differ; it is not a proof about all possible adaptive rules. For the third question, compare each enhanced procedure with its grid counterpart. Preserve Brier-only diagnostics to separate weight-optimisation gains from the effects of the additional quality search.

**Predictor amendment for approval:** use the known prediction-time longitude and latitude, not just the origin-cell index. The output remains probabilities over the frozen 1-degree destination cells plus E. The new model is a location-conditioned transition kernel P_h(j|x0), not one invariant probability row per origin cell. Same-cell queries may have different forecasts. Do not export an averaged cell matrix as if it were the actual-location model.

No averaging over local historical start positions, cell-centre substitution, inherited donor subcell start, query-coordinate rounding, new velocity/season/drogue predictor, environmental input, recursive propagation or learned trajectory generator is included. Prediction-time coordinates may come from a held-out ID; that ID's future path, other observations and labels may not inform its forecast.

## 2. Starting evidence and its limits

Read the [E1 benchmark](spatial_borrowing_s3_e1_results.md), [E2 adaptive endpoint result](local_endpoint_adaptive_s3_e2_results.md), [E3 information-quality result](local_endpoint_quality_s3_e3_results.md), and [E4 joint result](local_endpoint_joint_s3_e4_results.md).

| Days | Model | Brier | Mean K90 | H90 |
|---|---|---:|---:|---:|
| 7 | E1 LocalDisplacement | 0.975131 | 23.13 | 82.20% |
| 7 | LocalEndpointAdaptive | 0.959104 | 27.22 | 88.24% |
| 7 | Fixed B2/B1 | 0.962457 | 42.71 | 89.96% |
| 30 | E1 LocalDisplacement | 1.007012 | 96.17 | 69.96% |
| 30 | LocalEndpointAdaptive | 0.993452 | 105.34 | 76.84% |
| 30 | Fixed B2/B1 | 0.994931 | 133.86 | 77.59% |

E1's held-out-weighted transfer failure fractions were about 19.12%/24.48%; initial R/D exclusion contributed 9.28%/9.23%. These are failures of translated proposals, not evidence that original donors outside R were included. Actual-coordinate anchoring may change failure reasons and outcome probabilities, but reduced failure alone would not establish better forecasts.

The historical Local-A procedure used WGS84 net displacement integrated over local empirical start positions, endpoint-occupancy targets and pair-weighted evaluation. Its pooled A-minus-U Brier intervals crossed zero, and 34 fitting rows failed its numerical stability criterion. It is a motivation, not an apples-to-apples reference or a guaranteed success.

E4 found no candidate satisfying the inner Fixed hit-rate floor in its finite endpoint family. That does not prove all spatial methods are exhausted. Existing development evidence has informed E5; nested exclusion remains necessary but does not turn this round into untouched final-test evidence.

## 3. Frozen data, geometry and evaluation population

Retain cleaned release `per-drifter-cleaned-20261017-v7`, annual pooling, qualified hourly records, exact 7/30-day horizons, original source keys and stopped labels, 1-degree output cells, and the frozen R/D/shoreline assets.

The English Data Contract remains `docs/contract/data_contract_v1.0.xlsx`, SHA256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`, reverified during this proposal. Approval of this plan would explicitly amend the cell-only predictor definition; it would not change target eligibility, output geography or evaluation weights.

| Horizon | Qualified prediction times | Evaluation IDs | ID-origin units | Evaluated origins |
|---|---:|---:|---:|---:|
| 7 days | 303,288 | 385 | 4,451 | 37 |
| 30 days | 268,998 | 337 | 3,974 | 37 |

There are 3,224 development IDs, 517 locked final-test IDs and 54 indexed origins. Report the 17 indexed origins without evaluation cases as unmeasured. Reconcile these counts; never force them by dropping records.

**Training:** retain raw eligible-pair frequencies. **Evaluation:** average times within each drifter/origin, then drifters equally within origin, then origins equally. Equal-ID evaluation does not turn training into equal-ID fitting.

All models use the same cases and fitting-B2 support mask. Unsupported origin rows have unavailable standard scores and separately reported counts/proportions. No neighbour-only rescue is introduced. A missing/corrupt required prediction-time coordinate is an integrity failure, not permission to remove a difficult case.

## 4. Input sources and prediction-time information separation

Allowlisted sources after approval:

- Counts and qualification evidence: `results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet` and its source-keyed label receipts.
- Whole-ID folds: `results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv`.
- Sealed E1 prepared input: `results/runs/spatial_borrowing_s3_e1_input_20261030T113714_822569Z/`, including `paths/`, `labels/`, counts, source index and provenance.
- Registered contract, manifest/schema, R/D, origin/destination indexes and high/intermediate land masks.
- Earlier outputs only for source integrity and post-freeze control regression, never as fitted information or numerical selection thresholds.

The prepared path schema already contains ID, source observation key, time, longitude, latitude and frozen validity flags. It stores the union of required windows through each horizon where coordinates exist. Prefer this audited view; do not reread canonical `data/train` trajectories or reconstruct a second cleaning release. Missing required prepared evidence blocks execution pending a separately reviewed input amendment. All `data/test` trajectories remain denied.

Create an explicit predictor-only query view containing `(query ID, source observation key, origin time, horizon, actual lon/lat, origin cell, fold)`. Keep query truth and future coordinates in a separate scoring-only view. The prediction API receives x0 and fitting-role objects, never a query future track or destination.

Every donor must belong to the current fitting set. The whole query ID, including all its observations and future intervals, is excluded from that fitting set. Data preparation may inspect a development path as a donor in another role, but that cannot let it influence its own held-out forecasts. Assert exclusions at cache access and aggregation, not merely in the final evaluator.

## 5. Reference-neighbour eligibility

For query cell i, use its eight adjacent 1-degree grid cells, excluding i, intersected with the frozen R-origin index. Retain the existing longitude wrapping and latitude bounds.

A donor is a qualified same-horizon fitting record whose **actual original start** lies in permitted R in one of these neighbour cells. The R polygon, not its bounding box, decides eligibility. A boundary cell may contribute its eligible in-R records; its out-of-R records cannot contribute. Cells without any eligible fitting donors supply no information.

No outside-R/D donor extension, second ring, equal-neighbour-cell weighting, endpoint matching, neighbour similarity reweighting or outcome-based donor filtering is included. Each eligible donor pair retains its original multiplicity. All eligible donors remain in the normalisation denominator, including those whose counterfactual transfer later fails.

Excluding an ineligible original reference and handling a synthetic translated exit are different operations. A valid transferred first exit is E, not a deleted donor or failed-transfer label.

## 6. Actual-location path alignment

Let a donor's actual initial coordinate be z_d(0), its hourly path be z_d(t), and the query's known initial coordinate be x0. Use the same longitude-latitude displacement representation as E1, with the existing consistent longitude branch/normalisation convention:

`translated_d(t; x0) = x0 + [z_d(t) - z_d(0)]`, for t=0,...,24h.

Consequently `translated_d(0; x0)=x0` for every donor. Both new models call the same transfer kernel and receive exactly the same reference distribution for a fixed fitting role, horizon and x0.

This preserves the donor's grid-coordinate increments and hourly ordering. It does not claim exact preservation of WGS84 distances, bearings, step lengths or ocean dynamics. Changing the metric, rotating trajectories, scaling movement with time or using local empirical anchor averaging is outside this first comparison. Identity at the original donor anchor must reproduce source coordinates; identity of stopped labels is required on cases passing the common geometry rules.

The scientific assumption is approximate transferability of neighbour relative-motion histories to a different permitted origin at the same horizon under annual pooling. Actual-coordinate anchoring does not establish that the query and donor occupy the same flow branch. Geometry checks cannot prove dynamic reachability. Both new families share this assumption; adaptive support does not measure or guarantee its validity.

The old E1 per-cell translated-count table cannot substitute for this operation: its shift depends on cell offsets, while the new shift depends on x0 and the individual donor's initial position. E1's raw prepared paths can be reused; its synthetic outcomes cannot stand in for the new outcomes.

## 7. Geometry, exits and donor-level fallback

Keep E1's event ordering and safeguards:

1. The query must be finite, mapped to its recorded cell and in permitted R/D. A source-key/cell inconsistency is an integrity error. If a valid observed query coordinate is unsafe under the conservative land-mask rule, retain the query, mark `unsafe_query_geometry`, and return its supported B2 forecast for both new models.
2. Check translated hourly points using both pinned land masks. Land under either mask or an ambiguous mask disagreement cannot certify a transferable path.
3. Check each intervening straight longitude-latitude segment's portion inside D. A land intersection or ambiguity makes the transfer fail before accepting the interval endpoint. This guards the chosen piecewise-linear representation; it is not a verified subhourly physical path.
4. After a valid prefix, the first observed outside-D point gives E and stops the transfer. Later re-entry, missing continuation or land outside D does not undo E.
5. A segment that leaves and re-enters D between two inside-D observations does not itself create E; the target remains first **observed** exit.
6. Without an exit, a usable full interval yields the indexed translated destination at h. An unindexed within-D destination, missing required hour, invalid source continuation or other transfer failure returns its weight to B2. Corruption inside an originally qualified required source interval instead stops the run.
7. Do not copy a donor's original E label: relocating its path can change exit. If the original source exited but the relocated path has not, inspect available continuation; if it is unavailable before a new decisive event, return the weight to B2.

For N neighbour donor pairs, define v(j|x0) as the fraction of **all N** pairs that transfer successfully to destination j (D or E), and r(x0) as the failed fraction:

`sum_j v(j|x0) + r(x0) = 1`;

`Q_disp(j|x0) = v(j|x0) + r(x0)*B2_i(j)`.

No failed weight is removed, redistributed only among successful donors, snapped to water, resampled away or relabelled as observed grounding. No donors gives Q_disp=B2 and zero effective motion contribution. Supported forecasts remain complete because of this explicit predictive fallback assumption, not because all proposed paths were physically resolved.

Record original eligibility exclusions, transfer-failure reasons, valid E, nominal weight, effective motion weight and total B2 weight separately. Donor-level B2 fallback is common to both new models and is distinct from rejecting an entire model candidate at selection.

## 8. The only difference between the two new families

For each fitting-ID set F and horizon, compute:

- L_i: number of distinct fitting drifters with qualified local-origin pairs.
- M_i: number of distinct fitting drifters in the union of the eligible eight-neighbour donor sets; deduplicate across records and neighbours.
- s_i=M_i/L_i on B2-supported origins with M_i>0.
- m: unweighted median of positive s_i over **all fitting-supported indexed origins**, without filtering by held-out query availability.
- z_i=s_i/m.

The adaptive support proxy uses eligible fitting IDs before transfer, matching the audited E2 rule. It does not change with query truth or query sample density. Query-specific geometry already reduces effective borrowing through r(x0); this round does not add a second tuned validity multiplier or a new support formula.

Support is a proxy, not an effective independent sample size or certainty measure. Report local/neighbour ID overlap, raw pair totals, dominant-ID pair shares, successful donor IDs at each query, and successful mass fraction; many nominal IDs can still yield little transferable information. Do not tune a rule from these diagnostics after examining outer results.

| Model | Nominal neighbour weight |
|---|---|
| `ActualOriginDisplacementFixed` | lambda_i=a |
| `ActualOriginDisplacementAdaptive` | lambda_i=a*z_i^gamma/(1-a+a*z_i^gamma) |

Both issue:

`P(j|x0) = (1-lambda_i)*B2_i(j) + lambda_i*Q_disp(j|x0)`

`= [1-lambda_i*(1-r(x0))]*B2_i(j) + lambda_i*v(j|x0)`.

The actual successful motion contribution is `lambda_i*(1-r(x0))`. Thus Fixed has constant **nominal** a within a horizon/fit, but its effective motion contribution may vary by query geometry. Adaptive changes only the nominal rule. Its nominal weight may be constant within a cell even though its final forecasts vary with x0.

Exact branches: a=0 returns B2; gamma=0 returns the Fixed family; z=1 gives lambda=a; a=1 and available donors gives lambda=1; no donors gives actual lambda=0. Unsupported B2 rows remain unavailable for all models. If all ratios are zero, record the condition, use the existing placeholder median 1 and issue B2. Use the audited stable interior log-odds calculation, not an ad-hoc clipped formula.

## 9. Four weight-selection procedures and unchanged controls

Use these short identifiers in every table. `F_*` means the new displacement Fixed family; the historical **Fixed B2/B1** control must always be labelled separately.

| Procedure | Brier optimisation | Quality search |
|---|---|---|
| `F_grid` | a in {0,0.05,...,1}, gamma=0: 21 points | Those same 21 points only |
| `F_analytic` | Closed-form minimum over a in [0,1] | Original grid, exact optimum and bounded one-dimensional refinement; at most 114 points |
| `A_grid` | Same 21 a values; gamma in {0,0.5,1,2}: 84 points | Those same 84 points only |
| `A_continuous` | Bounded multi-start optimisation over a in [0,1], gamma in [0,2] | Contains both grids, the complete F_analytic pool, optimiser candidates and bounded two-dimensional refinement; at most 252 points in total |

The continuous domain has the same endpoints as v1; it fills gaps rather than widening the range. No per-cell fitted parameter, new support formula, extra random restart, new CV split or outcome-driven range expansion is permitted. Repeated boundary choices are diagnostics for a later discussion, not permission to expand gamma above 2.

There are two model families, four new selection procedures and six retained controls: **B2, Fixed B2/B1, Adaptive B2/B1, LocalEndpoint, LocalEndpointAdaptive, and E1 LocalDisplacement**. The ten main rows use common data and evaluation. Controls retain their formulas, grids and own inner-selection rules; refit/reselect them within each permitted role without applying the new quality screen to them. Endpoint controls never enter the new displacement forecast or donor fallback. E3 Quality, E4 Joint, historical Local-A and the stopped M1-neighbour run remain historical evidence, not additional E5 searches.

### 9.1 Inner out-of-fold Brier coefficients

For each supported inner held-out query n, obtain two forecasts fitted without that query's whole ID: p_n=B2 and q_n=Q_disp. Include all D destinations and E in their common sparse support. Let d_n=q_n-p_n and y_n be the scoring-only truth. Then:

`BS_n(lambda)=A_n*lambda^2+B_n*lambda+C_n`, where

`A_n=sum_j d_n(j)^2`;

`B_n=2*(sum_j p_n(j)*d_n(j)-d_n(y_n))`;

`C_n=1+sum_j p_n(j)^2-2*p_n(y_n)`.

With the normalised query weights w_n from Section 11, aggregate A=sum(w_n*A_n), B=sum(w_n*B_n), C=sum(w_n*C_n). Fixed has pooled inner loss `L(a)=A*a^2+B*a+C`. Coefficients are computed from **inner out-of-fold** predictions, never the same records used to fit their p_n and q_n. No independence assumption about hourly records is needed for this algebra; uncertainty still respects whole IDs.

For Adaptive, aggregate weighted coefficients by `(inner fitting role, origin)` to exploit constant nominal lambda within that block. Retain each block's fitting-only z and its weight; do not average z across roles or re-normalise blocks to equal weight. These sufficient statistics accelerate Brier and gradients exactly. They cannot determine H90/K90, which require the full query-specific probabilities and rankings.

The historical implementation in `src/data3001/modelling/baselines/blend.py` already contains this quadratic algebra. Its grid is 0.1 and it also supports unresolved mass; do not silently inherit that grid or change the E5 complete D-plus-E score. Reuse only audited pure algebra, with independent direct-score checks.

### 9.2 Fixed analytic optimum

For A>0, `a_star=clip(-B/(2*A),0,1)`. This is the global minimum of the **unconstrained inner Brier objective over the declared Fixed interval**. It is not the best unknown population weight, an outer-data solution, or the quality-constrained optimum.

If A=0, all positive-weight case forecasts must have d_n=0; verify B=0 within numerical tolerance and select a_star=0. Do not replace a small positive A by zero using the score tie tolerance. A nonfinite coefficient, negative A, or an inconsistent degenerate case stops the audit; B may legitimately be negative. Check endpoints, stationarity when interior, coefficient/direct-score equality and `L(a_star)<=min_grid_L+1e-12`. Save a_star and its exact loss even when another candidate is equivalent under the selection tie rule.

### 9.3 Adaptive continuous Brier search

Minimise `L(a,gamma)=sum_blocks[A_b*lambda_b^2+B_b*lambda_b+C_b]` in the closed box [0,1] x [0,2], using deterministic L-BFGS-B with analytic derivatives. For a positive-support block, set t=z^gamma and D=1-a+a*t:

`d(lambda)/da=t/D^2`;

`d(lambda)/d(gamma)=lambda*(1-lambda)*log(z)`;

`dL/dtheta=sum_blocks[(2*A_b*lambda_b+B_b)*d(lambda_b)/dtheta]`.

Use the stable probability implementation in Section 8, explicit boundary limits and zero derivatives for no-donor branches; verify derivatives independently in the interior and at boundaries. This is generally not a quadratic problem in the two parameters and no global continuous optimum is claimed.

Freeze at most 11 starts: the nine Cartesian points a in {0.1,0.5,0.9}, gamma in {0.25,1,1.75}; the minimum-Brier A_grid point; and (a_star,0). Remove exact duplicate starts, sort by gamma then a, and do not replace duplicates with new starts. Per start: `maxiter=200`, a hard wrapper limit of 2,000 joint objective/gradient calls, `maxls=20`, `maxcor=10`, `ftol=1e-12`, `gtol=1e-8`. Pin the installed SciPy/runtime version before running; no automatic upgrade. The [SciPy L-BFGS-B documentation](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-lbfgsb.html) defines these stopping controls; a success flag is not a global-optimality certificate.

Log every coefficient-only evaluation and retain the finite lowest-loss evaluated point from each start, at most 11 points, including the initial point if it is best. A bounded nonconvergence returns its best finite point with an explicit status, without extra restarts; nonfinite math or an invalid gradient stops the run. Do not label an unsuccessful run converged. Recompute full metrics for retained points and keep all A_grid candidates plus (a_star,0) regardless of optimiser success. Thus the best retained inner Brier cannot be worse than either guaranteed seed within tolerance. Report convergence flags, projected gradients, budget stops, boundary choices and cross-start spread separately from predictive performance.

## 10. Quality-feasibility search and selection

Use freshly fitted/reselected **LocalEndpointAdaptive and Fixed B2/B1** as references on the same pooled inner cases. Set `H_min=max(H_LocalEndpointAdaptive,H_Fixed)` and `K_max=min(K_LocalEndpointAdaptive,K_Fixed)`. A candidate is feasible when:

`H_candidate >= H_min-epsilon` and `K_candidate <= K_max+epsilon`, with epsilon=1e-12 for arithmetic only.

This enforces both references, not a choice of whichever one is easier. Selection uses inner point metrics, not historical thresholds, outer labels or an inner bootstrap. Brier remains the objective; no weighted H/K penalty is added. Within the feasible pool, form the improving subset satisfying `B_candidate < min(B_LocalEndpointAdaptive,B_Fixed)-epsilon`. If nonempty, choose its minimum-Brier candidate and mark it internally admissible. Score ties within epsilon use smaller gamma, then smaller a, **after** the strict gate so a numerical tie cannot discard an admissible seed. Log exact binary parameter values; do not round continuous weights onto the grid.

**Why a second search is needed:** the 90% set changes when destination ranks or the cumulative-probability cutoff change. H90/K90 are not smooth functions of the weights; checking only the Brier optimum, applying gradient constraints, or assuming monotonic coverage would be invalid. The following bounded search tests actual regions at every retained point. It can miss a narrow feasible interval and is not a certificate of continuous infeasibility or constrained global optimality.

### 10.1 Fixed analytic-assisted quality search

1. Evaluate the 21 original points and a_star; preserve these as the Brier-solver seed stage.
2. Add all a=k/80, k=0,...,80, gamma=0. This contains the original grid and, with a_star, gives at most 82 points.
3. Add at most 32 sequential interval midpoints. Sort current a values. Eligible adjacent intervals have width >1e-6 and fewer than eight additional midpoint subdivisions along a branch from the step-2 intervals before the proposed split. Prioritise intervals whose endpoints differ in feasibility, then intervals with a_star as an endpoint, then all others. Within a class choose larger width, lower minimum endpoint Brier, then lower left endpoint. Recompute metrics and interval priorities after each addition. Stop when the 32-point allowance or eligible intervals are exhausted; do not spend unused allowance elsewhere.

The pool has at most 114 points. Run this rule even if a_star is feasible so candidate discovery is not changed after a favourable result. The additional mesh/refinement is a **quality-feasibility search**, not a claim that analytic optimisation itself needed a finer grid. Keep seed-stage and final-pool decisions separately.

### 10.2 Adaptive continuous-assisted quality search

Begin with the union of A_grid (84), the entire F_analytic pool (at most 114, all at gamma=0), and at most 11 optimiser points. Because the grids share 21 points, this is at most 188 unique points. Every F_analytic candidate remains eligible even if its optimiser start was unsuccessful.

Add at most 64 quality probes using a fixed four-level pattern search in normalised coordinates (a,u=gamma/2). At each level with step size 0.1, 0.05, 0.025, then 0.0125:

1. Freeze up to two anchors from the current pool: the minimum-Brier feasible point, or the least-violating point if none is feasible; and the overall minimum-Brier point. Deduplicate identical anchors.
2. For each anchor, propose all eight offsets in {-step,0,+step} squared except (0,0), clipped to [0,1] squared, then map back to gamma=2u. Evaluate new exact parameter pairs in ascending gamma then a order. Deduplicate/clipped repeats use no extra replacement probes. Add the complete level before choosing the next anchors.
3. Define least violation solely for search priority as `V=max(0,H_min-epsilon-H,(K-K_max-epsilon)/max(1,K_max))`; ties use lower Brier, then the common parameter tie rule. V does not enter final selection, relax a constraint or become a new loss.

At most 2 x 8 x 4=64 new probes gives a final maximum of 252 unique full-metric points per horizon/selection task across all four procedures. This local pattern can miss disconnected feasible regions. Report that limitation, the visited points and which constraint binds; do not silently extend the search after failure. Broadening a domain or adding a new solver requires a new reviewed proposal.

### 10.3 Selection statuses, diagnostics and containment

- `inner_admissible`: a feasible candidate has strict inner Brier gain over both references; evaluate that candidate on the outer group.
- `no_feasible_candidate_in_searched_pool`: no tested candidate passes H/K; evaluate the procedure's minimum-Brier pool candidate solely as a rejected diagnostic.
- `no_inner_Brier_gain`: feasible candidates exist but none passes the strict Brier gate; likewise evaluate the minimum-Brier pool candidate as a rejected diagnostic.
- For either rejection, `eligible_for_replacement=false`; retain **all** outer cases and disclose the status in every summary. These are scientific outcomes of the bounded procedure, not permission to skip folds or run more candidates.

Save the analytic a_star, the two grid minima, the continuous Brier-solver seed minimum, each procedure's final-pool unconstrained minimum and its quality-guided choice. Evaluate the solver-only/unconstrained choices on the frozen outer cases as labelled diagnostics; they cannot be promoted after inspecting outcomes. A change appearing only after quality refinement must not be attributed solely to the analytic formula or numerical optimiser.

There is **no whole-model substitution** to Endpoint, Fixed B2/B1 or B2 after rejection. Donor-level B2 fallback remains unchanged. An a=0 winner is `zero_spatial_weight`, not successful motion borrowing. Compared with E4, this explicitly evaluates rejected forecasts instead of substituting the endpoint anchor.

Test candidate containment: F_grid is a subset of F_analytic and A_grid; both F_analytic and A_grid are subsets of A_continuous. Consequently the enhanced procedure cannot lose an available feasible/admissible seed, nor have a worse best inner Brier on its superset beyond tolerance. **No such guarantee applies to outer Brier, H90 or K90.** If A_continuous selects gamma=0, report collapse to Fixed; that is not evidence of incremental adaptivity. If all optimisers stop early and the winner is an inherited seed, report no demonstrated continuous-solver contribution.

## 11. Whole-ID validation and common aggregation

Use the existing five whole-ID outer groups. **CV defines where the weights are estimated and where they are judged; it is not a check added after optimising on all development labels.** For each outer group k and horizon:

1. Lock every ID in k out of fitting, support estimation, Brier coefficients, optimiser starts selected from metrics, reference thresholds, quality searches and parameter selection.
2. For each inner group l among the other four, fit p, q, support medians and controls using only the three groups outside k and l. Predict l and save its query bases and scoring-only labels separately. These four roles supply inner out-of-fold predictions.
3. Pool those inner cases with the declared weights, reselect the six controls by their frozen recipes, calculate the two reference thresholds, and run all four new procedures from Sections 9-10. A single a, or (a,gamma), is selected per procedure/horizon/outer-training partition, not independently per cell or inner fold. Reference selection shares these inner data; it is a tuning screen, not an unbiased performance estimate. No third CV layer is claimed.
4. Freeze all choices, statuses and diagnostics, refit each model on the four permitted outer-training groups, recompute its training support/median, and evaluate the untouched outer group k. Do not optimise weights again on k or change a failed choice using its results.
5. Repeat for all five outer groups, then aggregate every held-out case once. Report per-fold stability without using it to select a favourable split or restart the search.

The separation of inner selection and outer evaluation follows the [nested-CV distinction](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html). Whole-ID exclusion applies to all observations of an ID, not just the current window. The known query start is available at prediction time; its future information remains scoring-only.

Evaluate each outer query once using its exact known coordinates and selected fitting-role kernel. Score each prediction time before aggregation: count-only compression by `(ID, origin, destination)` cannot replace these calculations when x0 changes the forecast. Exact identical-predictor caching may retain multiplicity; approximate position binning may not.

For a case from ID d and cell i, primary weight is:

`1 / (number_of_evaluated_origins * eligible_IDs_in_i * eligible_times_for_d_in_i)`.

Use the same weights for Brier, K90, H90, selection and paired differences. Give an ID one total contribution **within each origin/horizon**; do not reinterpret this as one vote across the ocean. Preserve a separately labelled equal-pair sensitivity summary.

There are 20 inner fitting roles, five outer fitting roles and one all-development fit. Four solvers reuse these same roles; they do not multiply the geometry preparation by four. There are **12 weight-selection tasks**: (five outer-training partitions plus one all-development tuning task) x two horizons.

Freeze/hash all outer selected and diagnostic predictions, selections, cases and weights before all-development tuning. For that later tuning task, pool the five outer-fit **base p/q predictions and coefficients** as five-fold development out-of-fold data, then run the same four solver/quality procedures. Previously saved candidate tables alone are insufficient for new continuous weights: derive additional candidate metrics from those frozen base predictions, without new path classification. This use of development labels chooses illustration parameters only; it must not change frozen outer choices or be described as a second independent outer test. Finally fit on all development IDs for the predetermined illustrative queries.

All-development illustrations may use historical training starts but are fitted examples, not held-out validation. No final-test selection or trajectory access is included. Existing project-level adaptation and repeated development use remain disclosed.

## 12. Loss, regions, uncertainty and acceptance

**Primary loss remains standard multiclass Brier:**

`BS(P,y)=1+sum_{j in D plus E}P(j)^2-2*P(y)`.

It is a probability score, not geographic squared distance or percentage accuracy. Do not add linear/quadratic distance terms, Energy Score, probability sharpening, tail clipping, extra smoothing or a combined objective in E5. Spatial scoring can be a later separately defined change; this proposal preserves a clean actual-position/adaptive comparison.

For each full forecast, use the existing nominal 0.90 region: smallest descending prefix reaching 0.90 with cutoff ties included under 1e-12. E contributes probability and actual membership, but not the geographic cell count K90. Report actual H90 separately from issued mass. Retain every zero-probability truth and all probability tails. Mean grid-cell count is not physical area.

Report ordinary 95% paired whole-ID multiplier intervals. Use **50,000** Exp(1) replicates, NumPy PCG64 seed 20261031, sorted development IDs, shared multipliers across origins/models/horizons, fixed fits/within-ID averages, renormalised ID weights within each origin and fixed equal origin weights. Stream bounded batches; save draw identity/hash and linear quantiles. The increase from v1's 20,000 supports the larger declared contrast family within the unchanged wall-time/memory caps; extreme-tail Monte Carlo error still remains and must be disclosed.

The predeclared primary directional family has **72 contrasts**:

- Four selected procedures x two quality references x three metrics x two horizons = 48.
- F_analytic minus F_grid and A_continuous minus A_grid: two solver contrasts x three metrics x two horizons = 12.
- A_grid minus F_grid and A_continuous minus F_analytic: two adaptive-versus-fixed procedure contrasts x three metrics x two horizons = 12.

Use upper quantile `1-0.05/72` for Brier/K90 and lower quantile `0.05/72` for H90. Identical predictions do not shrink this predeclared family. The F_grid unconstrained winner versus E1 LocalDisplacement receives ordinary descriptive intervals as the matched-grid, matched-objective mechanism diagnostic. Other solver-only/unconstrained contrasts are descriptive too, not extra routes to declaring a primary win. Quality-guided new-versus-E1 comparisons describe whole procedures. Do not promote a diagnostic winner or select the best horizon after viewing outer results.

These are approximate conditional development intervals, excluding refitting/selection uncertainty, dependence from overlapping training, common ocean forcing and earlier research adaptation. Crossing zero does not prove non-deterioration. Numerical tolerance is not a scientific allowance for lost coverage or increased size.

| Conclusion | Required evidence |
|---|---|
| Engineering complete | Reconciled inputs, correct math/geometry/selection, bounded solver statuses, audit, control regression, resource limits, deliverables and fresh replay; favourable predictive results or convergence of every start are not required |
| Point improvement versus a reference | Delta Brier < -epsilon, Delta H90 >= -epsilon, Delta K90 <= epsilon |
| Conditionally supported quality-preserving improvement | Point conditions plus adjusted upper Brier < -epsilon, lower H90 >= -epsilon and upper K90 <= epsilon |
| Preferred new procedure at a horizon | Positive held-out-weighted effective motion and a forecast difference from B2 beyond epsilon, all five outer-training selections internally admissible, and supported quality-preserving improvement versus **both** LocalEndpointAdaptive and Fixed B2/B1 |
| Enhanced weight-selection benefit | The corresponding F_analytic-minus-F_grid or A_continuous-minus-A_grid contrast passes the point and adjusted quality-preserving conditions; also report whether the gain came from solver seeds or later quality refinement |
| Adaptive incremental benefit | The corresponding A_grid-minus-F_grid or A_continuous-minus-F_analytic contrast passes those conditions, with genuinely differing effective forecasts; gamma=0 throughout does not demonstrate adaptivity |
| Actual-location mechanism signal | F_grid's unconstrained winner improves on old E1 under matched grid/Brier-only selection/evaluation; an input-position/alignment signal, not proof of adaptive benefit or Fixed-quality replacement |
| Final candidate readiness | The corresponding all-development tuning selection is also internally admissible; otherwise no final candidate is recommended despite other diagnostics |
| Rejected / neutral / inconclusive | Failed inner gates, zero effective motion, no Brier gain or insufficient uncertainty support; report which condition failed |

Evaluate 7 and 30 days separately. A horizon-specific result does not justify a two-horizon claim. Scientific retention, deployment and Step 3 closure remain later user decisions even if every screen passes.

Interpret grid adequacy using both layers: a lower inner analytic/continuous Brier demonstrates a grid-resolution gap on those tuning data, but only outer evidence can support predictive benefit. Tiny inner gaps with no outer gain suggest limited value from finer weight selection **within this formula and domain**. Boundary solutions, solver disagreements or failed quality screens do not establish that the entire displacement idea has reached its limit.

## 13. Computational feasibility: exact target and compulsory pilot

Planning-only count arithmetic on the existing 21,879 grouped count rows found:

| Horizon | Outer query-donor combinations | All nested-inner combinations |
|---|---:|---:|
| 7 days | 15,179,967,338 | 45,539,902,014 |
| 30 days | 12,193,653,838 | 36,580,961,514 |

These are raw eligible-pair Cartesian counts before source-key/geometry reuse, early stopping or exact certificates, not measured runtime or independent sample counts. A literal all-hours implementation would be expensive. Do not infer a runtime from E4's cell-count-only execution.

The proposed estimator uses the **complete empirical donor distribution**, not Monte Carlo donor sampling. This makes Fixed and Adaptive comparable without an additional sampling approximation. Any future need for donor subsampling, query subsampling, rounded anchors, approximate geometry or fewer validation folds requires a new reviewed amendment; none is silently authorised here.

Allowed exact optimisations:

1. Store original paths once as their verified union view; retain source-keyed windows and shared relative-coordinate metadata.
2. For a validation query in outer group v, classify donor contributions separately by donor outer group g != v. A query-donor transfer is independent of a/gamma and of the other excluded outer group. Cache aggregate destination/failure counts and distinct-ID support per `(query, horizon, donor fold)`.
3. An outer fit combines four donor-fold blocks; an inner fit excluding v and k combines the other three. All-development parameter tuning reuses frozen outer base forecasts and coefficients, including for newly proposed continuous weights. No same-query-fold donor block is needed for held-out evaluation. This can reuse the approximately 27.37 billion outer-query/donor combinations rather than repeating their classification in every inner role; it remains a large workload.
4. Use conservative exact bounding certificates, spatial indexes, event ordering and early termination. A shortcut may certify an outcome only when it is provably identical to the literal path rule. Ambiguous cases execute the literal rule. Verify any adapted E1 event-index optimisation under variable real-valued offsets; its eight-offset assumption cannot be reused unchanged.
5. Stream bounded chunks, aggregate to sparse integer counts, and build query Brier coefficients once per permitted role. Optimiser calls use weighted block coefficients, not repeated path transfers, distributions or region sorting. Full H90/K90 scoring runs only for retained/probed candidates, cached by exact parameter identity and fitting/query role. Share results across the four procedures with explicit membership maps. Do not materialise the full query-by-donor-by-hour product or repeat geometry per weight.

Cache lineage must separate donor fold/IDs, query predictors, geometry and target version. Never sum a prohibited fold then try to repair leakage by subtracting only the query ID. Independent reconstruction must verify inner/outer exclusions. For full-development illustration points, prepare the additional donor contributions needed for their all-development fit, separately from the held-out cache.

**Proposed resource gates after approval:** CPU only; at most two workers, one numeric-library thread each; peak RSS <=8 GiB; all new pilot/preparation/primary/replay artifacts together <=5 GiB. Pilot <=300 seconds. Exact geometry preparation <=3,600 seconds. Primary fitting/scoring/audit/report <=3,600 seconds. One fresh geometry replay and one fresh scoring/report replay under the same respective caps. These are stopping limits, not runtime promises; the user is not approving an unbounded run.

Additional solver/search budgets are fixed in advance:

| Work per horizon/selection task | Maximum |
|---|---:|
| F_grid full-metric candidates | 21 |
| A_grid full-metric candidates | 84, including F_grid |
| F_analytic complete quality pool | 114, including F_grid and a_star |
| Continuous Brier starts / objective-gradient calls | 11 / 22,000 |
| Retained optimiser points requiring full metrics | 11 |
| Additional Adaptive quality probes | 64 |
| Unique full-metric union across all four procedures | 252 |
| All 12 selection tasks | At most 264,000 coefficient-only calls and 3,024 task-specific full-metric parameter points |

The 252 maximum already contains the 84 grid and 114 Fixed points; do not add those counts a second time. Each point must still be scored on every common query in its tuning task. A planning upper bound is `252*5*(303288+268998)=721,080,360` query-candidate metric evaluations across nested and all-development tuning, before exact sharing and support masks. This excludes control work, selected/diagnostic outer scoring, illustrations, uncertainty and audit/replay, which must also fit the stated caps. It is not a count of independent observations or a runtime estimate. Analytic Brier evaluation removes repeated scalar searches; it does not remove region computation or the geometry bottleneck.

Optimiser per-start limits are declared termination rules, not a reason to spend extra calls or restart. A full pipeline wall-time/storage/memory overrun instead stops execution without reporting a partial run as complete. If a mandatory search pool cannot be fully evaluated within budget, return a capacity failure; do not quietly omit expensive candidates or lower the 90% mass. Both replays retain the same candidate/call caps. Combined wall time is capped at 14,700 seconds (4 hours 5 minutes), including the pilot, with no automatic retries or enlarged budgets.

Pilot roster is selected without outcomes: use the first inner role (query group 1, fitting groups 2/3/4, excluded outer group 0); per horizon use query cells of largest work product, lowest positive local-ID support and a coastal polygon with largest work product, de-duplicated with ascending cell-ID ties. Each pilot cell must have at least one query and positive local and neighbour fitting support; report a missing stratum rather than silently substituting an easy one. Take up to eight evenly spaced source-key-sorted queries per selected cell and their **complete** fitting donor sets. Add the predetermined illustration cells if available and absent, with one query each. Freeze/hash the roster before timing. Exercise the four procedures, coefficient path and full region scorer for capacity only; pilot parameter choices are discarded and cannot tune the scientific protocol. Project to the **maximum** 252 full-metric points, 11 starts and 50,000 multiplier draws, even if pilot deduplication or early termination uses fewer.

Profile cached counts, geometry/early-exit fractions, unresolved literal work, coefficient optimisation, query-region sorting, multiplier aggregation, controls and audit/report costs separately. Include the query/donor-role combinations required by the four-block outer cache; a role-specific timing sample must not omit a missing high-cost donor block from its projection. Project full work and storage by query-cell/donor/support-size strata with a factor-of-two reserve; any materially uncovered high-cost stratum requires bounded pilot coverage within the same cap or a stop. Do not extrapolate only from offshore fast cases. A cap overrun, failed exactness check or resource projection above a limit stops the attempt before full execution. Return the measured bottleneck for user review; do not substitute an approximation to claim completion.

## 14. Diagnostics and visual deliverables

Keep the primary denominators unchanged. Report:

- Brier/K90/H90, issued 90% mass, complete support size, zero-probability truths, predicted/observed E, common unsupported rows and source availability.
- Nominal and effective borrowing, valid donor-ID counts, original donor support/dominance and overlap, all transfer failure classes and no-neighbour cases.
- Brier decomposition into squared probability norm and probability assigned to the realised outcome; gained and lost 90% hits; newly supported versus still unsupported true destinations.
- Per-fold and per-origin differences; frozen E1 support/coastal strata. No post-hoc cell-specific model switching.
- Every scored candidate's inner metrics, references, feasible flags, tie decisions, diagnostic/admissible selection, discovery stage and all-development status; coefficient-only trial points are logged separately and must not be presented as fully quality-tested.
- Grid-to-analytic/continuous inner Brier gaps versus their outer differences; analytic a_star and selected constrained a; all continuous start statuses, evaluated minima, gradients, call counts and boundary choices; inherited grid winners and gamma=0 collapses.
- Feasible counts before/after refinement, H/K violations against each reference, and the difference between solver-only, final-pool unconstrained and quality-selected forecasts. Plot the visited parameter set without implying the entire continuous domain was checked.

Figures: ten-row metric comparison; solver-pair and adaptive-versus-fixed paired differences with uncertainty; Fixed quadratic curves marking grid/analytic/feasible choices; Adaptive visited-point plots with constraint flags; parameter stability; nominal versus effective weights; failure causes; gained/lost hits; per-origin differences; and matched actual-coordinate probability maps. Inner search plots are tuning evidence, not outer validation. Never smooth a feasibility plot into an unobserved feasible boundary.

Use the existing geometry/support origin roster 44744, 44742 and 44382. Within each cell select the smallest `(ID, source observation key)` common qualified 7/30-day start as the primary map point. A second point for an intra-cell location diagnostic is the farthest distinct common start from it by WGS84 distance, ties by source key. This distance is only a display-roster rule, not a model feature. Freeze the points before fitting/result review. If a cell has no common start or distinct second point, report that absence; do not choose a substitute based on performance.

Show the actual coordinate marker and cell boundary, full distributions, common colour scales, nominal-90% outlines and E/fallback captions. Match query points across the new models and controls. Separate all-development illustration maps from held-out evidence; report both selection rejection status and support in captions.

Deliver an English results document and HTML review, source-keyed selected/diagnostic predictions, candidate ID-origin metrics for every fully scored point, coefficient/optimiser trace files, query/fold reference counts, support/reason tables, decision/uncertainty tables and audit/replay receipts. Share stored identical candidates through identity maps to respect the storage cap. The Chinese summary must state whether actual-position, adaptivity and enhanced weight search helped separately; whether each procedure preserved quality versus both references; and whether capacity stopped the run, a solver did not converge, selection was rejected, or donor fallback occurred.

## 15. Engineering layout and verification requirements

Proposed namespace: `actual_origin_displacement_s3_e5`. After approval only:

| Proposed file under `src/data3001/modelling/baselines/` | Responsibility |
|---|---|
| `actual_origin_displacement_s3_e5_inputs.py` | Guarded source-keyed predictor/path views, query/donor-fold cache and resource pilot |
| `actual_origin_displacement_s3_e5.py` | Exact-location kernel, support schedule, both families and four selection procedures |
| `actual_origin_displacement_s3_e5_selection.py` | Weighted Brier coefficients, analytic/continuous solvers, bounded quality search and traces |
| `actual_origin_displacement_s3_e5_audit.py` | Independent geometry checks, counts, exclusions, probabilities, scoring and decisions |
| `actual_origin_displacement_s3_e5_report.py` | Actual-query figures, complete comparisons and rejection/fallback reporting |
| `run_actual_origin_displacement_s3_e5.py` | Approved identities, staged execution, control regression, sealing and replay |

Use a matching config, focused semantic tests and one results document under existing directories. Shared pure score/region/geometry helpers may be reused without editing older experiment definitions. Do not create a duplicate data workspace, import an old runner to execute it, or put new scientific code in `_compat/`.

Development order after approval: first implement the minimum exact transfer/cache kernel, coefficient/solver/quality-search routines needed for timing, semantic fixtures and the resource pilot. Only after the capacity gate passes, complete the full orchestration, uncertainty and reporting pipeline. The successful pilot binds tested kernel/input/solver identities; changed transfer or scoring logic requires renewed verification and a reviewed timing allowance if the original pilot budget is exhausted. Later routine report work must not silently alter the estimator. This establishes whether exact geometry and the larger region search are affordable before building the complete deliverable pipeline.

Required semantic checks include:

- Actual t=0 query identity, two distinct positions in one cell, donor-self coordinate identity, E1 per-donor offset equivalence where applicable, longitude wrapping and source-key/time reconciliation.
- Qualified in-R donor starts, partial boundary cells, no outside-R extension, whole-ID exclusion, query predictor/future separation, fold-block union equivalence to direct fitting-ID filtering.
- Valid full path, valid first exit then return, land before exit, land outside after exit, intervening segment crossing, mask disagreement, missing continuation, unsafe query geometry and no-donor/unsupported branches.
- Exact original donor mass including failures, v+r conservation, identical Q for both new models, a=0/1, gamma=0, z=1, fitting-only medians and fixed/adaptive subfamily containment.
- Complete Brier for zero-probability truth, per-time-before-ID aggregation, region ties/E, equal evaluation masks and no misuse of cell/destination grouped counts for changing x0.
- Coefficient/direct Brier equivalence; correct pooled query weights rather than mean fold losses; analytic endpoint/interior/degenerate/tiny-positive-A cases; exact analytic optimum no worse than the 0.05 grid; fitting-role-specific z blocks.
- Analytic gradients versus independent differences; all closed-box branches; deterministic start roster, hard evaluation caps, unsuccessful-start retention, nonfinite failure, exact parameter identity and continuous/grid seed containment.
- Quality refinement in nonmonotone/disconnected synthetic feasible sets; rejection of a Brier-optimal but infeasible point; a feasible off-grid point found by the frozen search; narrow feasible regions deliberately missed without claiming infeasibility; midpoint depth, pattern clipping/deduplication and 114/252 limits.
- Feasible and infeasible candidates for each reference and metric, strict Brier gate, deterministic ties, both rejection reasons, diagnostic forecasts without model substitution and no missing-fold score summary.
- Separation of solver-seed and post-refinement winners, inherited-grid/gamma=0 status, all-development reuse after outer freeze, 12-task/72-contrast accounting and identical-case comparisons for all four procedures.
- Exact shortcut certificates versus literal chronological checking; corrupted cache/source/config and forbidden-ID access must fail closed.

Independently reconstruct all selected/diagnostic forecast probabilities and score/aggregation/selection tables from saved fitting-role sufficient statistics without calling the production selector to audit itself. Check candidate metric identities in bounded partitions, derive a_star independently, audit continuous traces/derivatives and reconstruct every proposed quality probe and tie decision. This verifies the declared bounded search, not global optimality of Adaptive or constrained Fixed. Geometry verification combines exhaustive small fixtures, independent certificate checks and a deterministic real query-donor sample (at least 5,000 available combinations, stratified across horizons, origins and every observed event/failure class). Explicitly label this as sampled geometric cross-checking; do not claim all billions of transfers were independently inspected. Fresh replay recomputes the complete proposed pipeline, including the solver/search sequence.

After the new outer freeze, regress five endpoint/global controls against sealed S3 E4 and old LocalDisplacement against sealed E1: selected parameters, 36 control matrix files (six controls x five outer plus one all-development role), cases, weights and point metrics within absolute 1e-12. New family uncertainty bounds need not equal old rounds. An unexplained control mismatch blocks interpretation.

Seal approved plan/config, source hashes including entrypoints, input/geometry/environment identities, query/fitting IDs, resource receipts, cache lineage, outer freeze and all outputs in new immutable run IDs. Verify previous source hashes remain unchanged. Fresh geometry replay must match integer outcome/failure/support counts exactly; scoring replay must match numeric tables within absolute 1e-12 and PNGs byte-for-byte in the pinned environment. Inspect every figure and local report link. Update the deliverable alias only after these checks pass.

## 16. Approval requested

This revised proposal asks approval for:

- The known-coordinate predictor amendment and identical actual-origin displacement kernels, with unchanged R-only donors, full-path geometry, E and donor-level B2 fallback.
- Four procedures: original 21/84 grids; Fixed analytic Brier solution with at most 114 quality-search points; bounded Adaptive continuous search with at most 11 starts and a shared total of 252 fully scored points per task. The adaptive support formula and parameter domain remain unchanged.
- Five-outer/four-inner whole-ID CV, weights solved on inner out-of-fold predictions, fit-only support/medians, and all-development illustration tuning strictly after the outer freeze.
- Fixed 90% regions, standard Brier, both-reference H/K feasibility and strict Brier gates, with explicit rejected diagnostics and no whole-model substitution or claim that a finite failure proves continuous infeasibility.
- Six unchanged controls, four new comparison rows, the 72-contrast conditional screen and 50,000 multiplier replicates.
- Exact shared geometry/coefficient reuse, the maximum candidate/solver budgets, a compulsory 300-second pilot and the unchanged 8-GiB/5-GiB and four one-hour execution/replay caps.

**No development or pilot has started.** Approval would authorise bounded implementation, resource testing and, only if those gates pass, independent execution/audit/replay. If exact computation is infeasible within the caps, the authorised outcome is a measured feasibility report and a new proposal, not an unapproved sampled experiment.
