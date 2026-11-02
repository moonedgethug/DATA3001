# Step 2 — E2 B1 Allocation and Weight-Control Engineering Proposal

**Version:** E2 v1, 30 October 2026. **Status: USER APPROVED — INDEPENDENT DEVELOPMENT, EXECUTION AND AUDIT AUTHORISED.**

The user confirmed this complete E2 engineering specification and authorised independent development, execution and result audit. This document preserves the approved scientific specification. It does not amend the approved [E1 plan](adaptive_b2_b1_plan.md) or close Step 2. Authorisation is recorded in the [research ledger](research_stage_ledger.md); scientific conclusions remain subject to user review.

## 1. Objective and decisions being reviewed

**Objective:** reduce the pair-weighted mean number of geographic cells needed to contain at least 90% of the model's predicted probability, without increasing standard Brier or decreasing actual region-hit rate relative to a freshly fitted Fixed B2/B1 control. Evaluate 7 and 30 days separately.

The 90% level is fixed. It is predicted probability, not a claim that observed coverage is already 90%. Retain the complete forecast distribution. Do not reduce the level to 80%/85%, clip tails, hide probability mass, delete observations, or condition the displayed distribution on selected cells.

| Decision | Proposed E2 specification |
|---|---|
| Main experimental arm | **Info:** reallocate B1 probability between destinations seen and unseen in the current origin's fitting data; use a weight constant across supported origin rows |
| Independent control arm | **Weight:** keep B1 unchanged; vary the strength of the count-dependent weight relation |
| Quality reference | **Fixed:** original B1 and a constant blend weight, selected by minimum inner-validation Brier |
| Secondary comparators | Fresh B2 and a fresh E1 Adaptive reproduction |
| Candidate grids | 21 blend weights; five allocation factors for Info; five support exponents for Weight |
| Selection change | Quality constraints first, then minimum 90% region size, inside training only |
| Quality margins | Zero allowed Brier deterioration and zero allowed hit-rate deterioration; numerical tolerance only |
| Exit handling | Info reallocates B1's D mass only; B1's E probability is preserved |
| Uncertainty | 5,000 paired whole-ID resamples of fixed outer forecasts; ordinary intervals plus a conservative joint development screen |
| Execution boundary | One independent run plus one replay after approval; 30-minute cap per complete run |

Info and Weight are not combined. The main question concerns Info versus Fixed; Weight versus Fixed is the separately reported diagnostic comparison. A favourable result is not required to complete E2.

## 2. Motivation and limits of the evidence

The [E1 result](adaptive_b2_b1_results.md) showed smaller Adaptive 90% regions with lower actual hits than Fixed. Neither horizon established a dependable Brier advantage over Fixed. This does not establish a software error or show that B1 has no useful information.

Post-hoc read-only accounting of the sealed E1 forecasts gave the following pair-weighted probabilities for the event "the destination was unseen in this origin's fitting data":

| Days | Model | Predicted event probability | Observed event frequency |
|---|---|---:|---:|
| 7 | Fixed | 4.99% | 2.08% |
| 7 | Adaptive | 2.29% | 2.08% |
| 30 | Fixed | 22.08% | 17.46% |
| 30 | Adaptive | 21.59% | 17.46% |

These descriptive calculations motivated E2; they are not new independent validation, causal proof, or parameter targets. Do not set c by dividing these observed and predicted percentages. Seven-day Adaptive already matched this aggregate event frequency more closely while losing region hits, so event-mass correction alone may fail.

For an unseen destination, the original blend assigns lambda_i*q_j. A scalar origin weight changes the total borrowed probability but cannot change the relative B1 probabilities of two such destinations. Info introduces one limited allocation adjustment; it still cannot distinguish every suitable and unsuitable unseen destination.

The general aim is concentration with reliable probabilities, consistent with the distinction between sharpness and calibration in [Gneiting and Raftery (2007)](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf). The specific E2 allocation rule and constrained selector below are project proposals, not methods validated by that paper.

## 3. Frozen task and input contract

Retain final cleaned `per-drifter-cleaned-20261017-v7`, annual pooled, 1-degree states, R-origin eligible hourly pairs, equal pair weights, separate direct 7/30-day stopped-first-exit targets, the original five whole-ID development folds, and the same D-plus-E destination index. Initial velocity is not a predictor. Do not change qualification, counts, trajectories, canonical fields, geometry, seasons or ID membership.

- English contract SHA256: `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`.
- Verified qualified-count source: `results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet`.
- Frozen fold source: `results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv`.
- Source qualification labels, inventories and geometry assets are the same allowlisted evidence used by E1. Reverify their identities; do not regenerate canonical trajectories.
- All 3,224 development IDs remain in the fold inventory, including IDs with no eligible evaluation pairs. Final-test trajectories remain inaccessible.
- Frozen S1: `empirical_b2_20261029T121555_976173Z`; frozen E1: `adaptive_b2_b1_20261030T044950_931787Z`. Their fitted outputs may be read only after fresh computation, for regression audit, never as fitting or tuning inputs.

No neighbour/distance/displacement borrowing, environmental predictors, velocity categories, M1 propagation, MDN, drifter reweighting, probability powers, physical reachability mask, or per-destination free parameters. Info is a data-dependent regularized point estimator, not an independently informed Bayesian prior or a claim of validated Bayesian credible intervals.

## 4. Common estimates and complete probability rows

For each fitting-ID set T and horizon h, compute qualified counts N_ij and N_i=sum_j N_ij over D plus E. For N_i>0:

`p_ij = N_ij/N_i` and `q_j = sum_i N_ij / sum_i N_i`.

B1 q pools only eligible R-origin pairs from fitting IDs, including the target origin, with the original multiplicities. Rebuild p, q, support masks and support medians inside every fit. A destination is "seen" only when its fitting count is strictly positive; rarity thresholds and held-out outcomes are not used.

Use the same B2-supported mask for every model and candidate. For N_i=0, report an unsupported row, unavailable Brier/region metrics and unresolved bookkeeping; issue no B1 fallback. Missing outcomes are not E. U is not a physical destination and is not used to absorb discarded probability.

Every supported forecast must be finite, nonnegative and sum to one across D plus E within absolute 1e-12. Existing empirical zeros may remain zero. No uniform floor or newly invented state is introduced. An empty fitting horizon is a diagnostic failure.

## 5. Models and exact finite parameter grids

Common blend grid: `A = {0, 0.05, 0.10, ..., 0.95, 1}` (21 values). Each horizon has its own selected parameter(s), shared across its origin rows in the manner specified below.

### 5.1 B2, Fixed and E1 Adaptive controls

- **B2:** p, without tuning.
- **Fixed:** `(1-a)*p_i + a*q`. Choose a using the minimum pooled inner-validation Brier; ties within 1e-12 choose smaller a. This is the quality anchor, not a hard-coded E1 parameter or score.
- **E1 Adaptive:** original q and `lambda_i=m*a/((1-a)*N_i+m*a)`, where m is the fitting median of positive N_i. Choose a by Brier only, exactly as E1. This provides a fresh historical-procedure comparator; it does not set E2's quality constraints.

### 5.2 Info: B1 allocation, main arm

For geographic destinations define `S_i={j in D : N_ij>0}`. Let `w_ij(c)=1` on S_i and c on D outside S_i, with:

`C = {0.5, 0.75, 1, 1.5, 2}`.

Let `Q_D=sum_{j in D} q_j` and `Z_i(c)=sum_{j in D} q_j*w_ij(c)`. Construct:

- `q_info(i,E)=q_E`;
- if Q_D>0, `q_info(i,j)=Q_D*q_j*w_ij(c)/Z_i(c)` for j in D;
- if Q_D=0, leave q unchanged (all mass is E).

Because c is positive, Z_i(c)>0 whenever Q_D>0. This is a fitted reference transformation that preserves the original total D mass and E probability; it is not D-only conditioning for display. If all positive D reference mass belongs to one of the two groups, the transformation leaves q unchanged.

The forecast is `p_Info(i)=(1-a)*p_i+a*q_info(i)`. The mixing weight a is constant across supported origins for a given fit and horizon. Only the allocation of B1's D mass depends on the origin's observed support.

- c<1 reduces B1's relative allocation to locally unseen cells; c>1 increases it; c=1 reproduces Fixed.
- All positive B1 cells remain positive in the reference; within either group their relative B1 probabilities are unchanged. No tail is deleted.
- a=0 reproduces B2 for every c. At a=1, the output is the **modified** reference; it is raw B1 only when c=1 or the adjustment is degenerate.
- At the same a, Info and Fixed have identical forecast E probability. Different selected a values may still change E, which must be reported.
- Search all 21 x 5 = **105 declared pairs** (a,c); no per-cell c and no post-result grid refinement.

### 5.3 Weight: unchanged B1, independent control arm

Keep q unchanged and use:

`lambda_i(a,beta)=a / [a+(1-a)*(N_i/m)^beta]`.

`Beta = {0, 0.25, 0.5, 0.75, 1}` (a five-point refinement of the discussed 0/0.5/1 pilot). Recompute m from positive fitting-row counts in each fit.

- beta=0 reproduces Fixed; beta=1 reproduces E1's weight family.
- At N_i=m, lambda_i=a. For interior a and positive beta, borrowing decreases with N_i.
- Implement a=0 and a=1 explicitly as B2 and B1 on supported rows.
- Search all 21 x 5 = **105 declared pairs** (a,beta). No hard cutoff, beta>1, negative beta, free per-cell weights or replacement of N_i by an unvalidated effective sample size.

N_i is a pair-count proxy, not independent evidence. Report distinct fitting IDs and largest-ID share as diagnostics. This arm tests the slope of the existing rule; it does not claim that pair counts fully measure reliability.

The two arms have the same number of declared candidates, not necessarily equal statistical flexibility. Equivalent endpoint predictions may be cached once, but retain every declared parameter identity in selection tables. The Fixed and E1 Adaptive candidates are embedded in these grids; Brier-only selections for the controls are still performed separately. Never search the joint (a,c,beta) space in E2.

## 6. Scores, 90% regions and selection policy

Keep standard unnormalised multiclass Brier: `BS=1+sum_j p_j^2-2*p_y`, over D plus E. Do not use historical failure-penalised S or a spatial/composite loss. Every eligible supported observation is scored, including zero-probability true outcomes.

Construct each 90% region exactly as E1: sort positive D-plus-E outcomes by probability, take the shortest prefix reaching 0.90 within absolute mass tolerance 1e-12, then include all cutoff ties within probability tolerance 1e-12. Never break ties using observed outcomes or geography. Record actual included mass and E inclusion. K counts D cells only; H is actual full-outcome region-hit frequency. Region cells need not form a connected polygon, and cell count is not physical area.

All selection statistics pool the same supported inner out-of-fold cases with original pair multiplicities: mean Brier B, mean cell count K, and hit fraction H. Do not average folds, IDs or origin cells equally. Record eligible/evaluable/unsupported pair and ID denominators; aggregate ID counts by set union.

**Proposed policy change from E1:** select each new arm by minimum region size subject to two quality constraints, instead of Brier alone. The metric itself is unchanged. This is a constrained selector, not a new proper scoring rule or a guarantee of population non-degradation.

For each outer-training selection role and horizon:

1. Fit the Fixed anchor's a by minimum pooled inner Brier. Save `(a_ref,B_ref,H_ref,K_ref)`.
2. Evaluate all candidates in Info and Weight independently on identical inner cases.
3. A candidate is quality-feasible if `B<=B_ref+1e-12` and `H>=H_ref-1e-12`. Practical deterioration margins are **zero**; 1e-12 only handles numerical arithmetic.
4. Require `K<K_ref-1e-12` to replace the anchor. If no candidate is both feasible and smaller, the arm returns the **exact Fixed parameter and forecast**, tagged `fallback_fixed`.
5. Among eligible replacements, minimise K. Resolve ties sequentially by lower B, higher H, less departure from the neutral family (Info: smaller abs(log(c)); Weight: smaller beta), smaller a, then smaller c/beta. At each numeric criterion retain values within absolute 1e-12 of that criterion's optimum before applying the next.
6. Save every candidate's statistics, constraint margins, feasibility, strict-size decision, selected parameter and fallback reason. A neutral/degenerate choice is identified as such, not attributed to the new mechanism.

The anchor is always a valid fallback because Info contains c=1 and Weight contains beta=0. Insufficient common supported validation data is an error, not permission to tune using the outer fold. Constraints apply to pooled cases at each horizon, not to every individual origin or fold; report subgroup trade-offs rather than implying uniform improvement.

## 7. Nested whole-ID validation and leakage controls

Use the unchanged five outer ID groups. For outer group k, its other four groups are the four inner validation groups. Inner fit (k,l) excludes all IDs in k and l; its validation uses only l. Within that fit rebuild counts, B2, B1, S_i, Q_D, Z_i and m. In particular, do not use all-development support to decide that an inner-validation endpoint was "seen".

Aggregate inner metrics, select Fixed, E1 Adaptive, Info and Weight by their declared rules, then refit on the four outer-training groups. Rebuild all support-dependent quantities there and apply the selected parameters to outer group k exactly once. An inner-valid candidate can fail outer quality constraints; report that failure and do not retune.

No outer outcome may choose c, beta, a, cutoffs, tie rules or fallback for that fold's own held-out predictions, or change the declared grids and illustration rule. Do not choose a combined Info/Weight predictor or the winning arm from outer results. Compare their independently selected procedures as planned.

After the nested outer predictions have been written and their hashes frozen, construct illustrative all-development candidates: use the five base out-of-fold fits to evaluate every declared candidate on the development pool, apply the same selector, and refit on all development IDs. This later use of the development outcomes is for all-development tuning only and must not feed back into any outer prediction. These candidate maps and tuning scores are not independent performance evidence. There are 20 inner fitting roles, five outer fitting roles and one all-development refit: **26 base roles**, with bases reused across candidate forecasts.

E1 outcomes have already influenced research design. E2 is therefore a new isolated development experiment on repeatedly examined data, not a newly untouched validation set. Final-test access remains locked.

## 8. Diagnostics that explain the mechanism

For all five reported models save the main three metrics, denominator/support tables, zero-true-probability fraction, positive-cell count, predicted/observed E and U/unsupported accounting. Report both total region hits and D-outcome conditional geographic hits if E occurs; never attribute exit-only gains to improved geographic localisation.

Prespecified explanations, not extra tuning objectives:

- Seen/unseen **D** event probability and observed frequency, using each forecast's fitting support; report E separately. The two D groups plus E must reconcile to the full distribution and outcome counts.
- Relative to Fixed and B2, cells added to and removed from each 90% region, their predicted masses and observed hit contributions. Reconcile net size and hit differences to the summary.
- Per-origin results and the two fitting-support strata `N_i<m` / `N_i>=m`, with distinct IDs, largest-ID share, selected parameters and actual borrowing weights. Strata are assigned inside each fitting role.
- Fixed-budget hit diagnostics at the unchanged E1 K grid `{1,5,10,20,50,100,200,500,1000,|D|}`; use the same expected boundary-tie inclusion and explicitly flag zero-probability ties. These do not replace or select the fixed 90% regions.
- Matched illustrative maps using the S1 support-only origin rule: maximise the minimum distinct-ID support across horizons, then smallest cell ID. Use the same colour scale per horizon and display all probabilities, with 90% outlines, E/U and support captions.

Do not retrospectively exclude difficult cells, IDs, rare outcomes or unfavourable support strata. If the reference allocation improves aggregate probability calibration but not the joint objective, say so.

## 9. Uncertainty and scientific acceptance

Prespecify four model/horizon comparisons: Info minus Fixed and Weight minus Fixed, separately at 7/30 days. B2 and E1 Adaptive comparisons remain secondary descriptive context; they do not change the reference or rescue a failed main comparison.

Use **5,000 paired whole-development-ID bootstrap resamples**, seed **20261030**, on the saved outer predictions. Draw from the complete development-ID inventory and apply each ID multiplicity identically to every model and horizon. Recompute the original pair-weighted statistics; do not bootstrap individual hourly pairs or average ID scores equally. Report empty-denominator replicates. Do not replace undefined replicates selectively; if any requested main comparison has fewer than 5,000 defined replicates, its uncertainty screen is unavailable and requires review.

Report ordinary 2.5/97.5 percentile intervals. For a conservative joint development screen across the four comparisons and three directional criteria (12 bounds), also use one-sided percentile bounds at `alpha/12=0.05/12`: lower quantile **0.0041666667**, upper quantile **0.9958333333**, using linear interpolation. This is a Bonferroni-style adjustment under the bootstrap approximation, not an exact finite-sample guarantee.

These resamples hold fitted forecasts and selections fixed. They omit refitting, overlapping-training and research-adaptation uncertainty; additional replicates improve numerical tail estimation, not those omissions. No result is a formal population non-inferiority proof or final-test confirmation.

| Outcome | Required interpretation |
|---|---|
| Engineering complete | All semantic, leakage, identity, regression, audit and replay checks pass; a negative scientific result is allowed |
| No improvement / trade-off | Outer delta B>1e-12, delta H<-1e-12, or delta K>=-1e-12; report the actual trade-off |
| Point-estimate candidate | Outer delta B<=1e-12, delta H>=-1e-12 and delta K<-1e-12, but the uncertainty screen is not fully satisfied |
| Conditional development support | Point criteria pass, adjusted upper bound for delta B<=1e-12, lower bound for delta H>=-1e-12, and upper bound for delta K<-1e-12 |
| Exact fallback | Forecast equals Fixed; valid baseline preservation, not an improvement |

Report 7 and 30 days separately; success at one horizon does not establish success at the other. Zero-exit data do not validate exit calibration. Point success with bounds allowing deterioration is **inconclusive**, not "equivalent" or "no deterioration because not significant". Do not relax margins or extend searches after seeing results. Retention, S2 closure and any later combined model remain user decisions.

## 10. Implementation ownership after approval

Reuse audited pure count/base functions, the common input guard and the existing probability-region semantics. Do not import or execute E1's runner as the E2 pipeline. Leave E1/S1 formulas and sealed artifacts unchanged; extract a genuinely shared helper only if necessary, preserving previous APIs and regression results.

| Proposed path | Responsibility |
|---|---|
| `src/data3001/modelling/baselines/b2_b1_e2.py` | Info/Weight probabilities, candidate tables and constrained selector |
| `src/data3001/modelling/baselines/run_b2_b1_e2.py` | Exact config validation, guarded inputs, nested roles, provenance and sealing |
| `src/data3001/modelling/baselines/b2_b1_e2_audit.py` | Independent count, probability, selector, score and region reconstruction |
| `src/data3001/modelling/baselines/b2_b1_e2_report.py` | English report, plots and browser review |
| `configs/b2_b1_e2.json` | Approved settings only; no inherited mutable E1 defaults |
| `tests/test_modelling_b2_b1_e2.py` | Scientific and validation semantics |
| `docs/b2_b1_e2_results.md` | One human-readable scientific result account, created after execution |

No new implementation belongs in `_compat/`. Use existing `.venv`, root/asset resolvers and package conventions; do not add libraries, notebooks, a parallel data tree or a large worktree for this task.

## 11. Required tests and independent audit

Before running data-dependent E2 selection, verify:

1. Hand-computable Info rows, preservation of E and total D mass, positive-support preservation, c=1, a=0, and the distinction between Info a=1 and raw B1.
2. All-seen D mass, all-unseen D mass, Q_D=0, unsupported origin, empty horizon and empirical-zero cases; no hidden divide-by-zero or fallback.
3. Weight beta=0/1 identities, endpoints, equality lambda=a at N_i=m, monotonicity and fitting-only median.
4. A destination occurring only in validation remains unseen in the fitting support. Neither outer IDs nor their outcomes affect reference, mask, median or selection.
5. Standard Brier, E accounting and exact zero-probability truth penalties; common masks and original pair-weighted denominators.
6. Unchanged 90% cutoff/tie semantics, full probability conservation and no truncation; matched-budget diagnostics retain E1 semantics.
7. Synthetic selector cases: lower K but worse Brier rejected; lower K but worse hits rejected; feasible improvement selected; ties deterministic; no strict gain returns the exact Fixed anchor.
8. Paired ID bootstrap uses identical draws across models, preserves pair weighting and handles undefined denominators explicitly; adjusted-bound classification is independent of ordinary intervals.
9. Relevant S1/E1 mathematical regression, shared-helper, architecture and import-layout tests. Do not run unrelated expensive pipelines.

After execution, independently rebuild counts/support for all 26 base roles, and candidate Brier, region size and hits from explicit vectors for every declared evaluation role/horizon (20 inner plus five base out-of-fold roles). The all-development refit has no independent evaluation score. Audit the full anchor/feasibility/tie/fallback decisions without calling the production selector. Reconcile event-group accounting, added/removed regions, all denominators and bootstrap classifications, and verify that later all-development tuning left the frozen outer predictions unchanged.

Only then perform allowlisted frozen-output audits: fresh B2 versus S1, fresh Fixed and E1 Adaptive versus E1, including selected Brier-only parameters and corresponding matrices/scores. Compare every numerical output in a fresh full replay within absolute 1e-12, excluding run IDs/timestamps. Verify all prior sealed hashes and inspect rendered figures. Passing engineering checks alone does not establish scientific improvement.

## 12. Deliverables, runtime and stop conditions

Use a unique `b2_b1_e2_<UTC_run_id>` under both `results/runs/` and `provenance/runs/`; fail if either destination already exists. Provide:

- Approved plan/config snapshots; input, source, environment and output hashes; all fitting/evaluation ID roles and access-guard audit.
- Shared B2/B1 bases, per-role seen-support evidence, Info normalisers/E checks, support/weights, all candidate metrics, selected parameters, anchor constraints and fallback reasons.
- Outer and all-development matrices for B2, Fixed, E1 Adaptive, Info and Weight, with clearly separated roles; held-out scores, summaries, diagnostics, paired bootstrap draws/bounds and outcome classification.
- English `REPORT.md`, `review.html`, maps and diagnostic figures; standalone independent audit and replay receipts; one concise Chinese decision summary to the user.

Expected implementation/audit effort is approximately 0.5–1 working day, subject to actual verification needs. E1's roughly one-minute run is only a reference: E2 evaluates region metrics across more candidates and must be profiled. After approval, run a bounded one-inner-role preflight across both horizons and all declared candidates; cap it at five minutes and record the runtime estimate. If it indicates that the complete run is likely to exceed 30 minutes, stop for a revised plan instead of silently reducing folds, grids or checks.

Limit each complete execution, including audit/bootstrap, to **30 minutes**. Plan one primary execution and one independent replay; no GPU is required. Stop on identity mismatch, leakage, probability/denominator inconsistency, empty required fitting horizon, unexplained regression failure, timeout or rejected access. Scientific non-improvement is a reportable result, not permission for automatic further searches.

After execution and audit, present results for user review. Update current navigation only when real deliverables exist. Do not auto-commit/push, access final test, combine Info and Weight, restart neighbour/MDN work, alter the research ledger's approved conclusions, close S2 or start S3.

## 13. Approval boundary

The user has confirmed this exact E2 specification, including the finite grids, D-only B1 reallocation with E preserved, constrained selector, zero quality margins, five-model output, whole-ID validation, uncertainty screen and bounded execution above. Implementation and independent execution may proceed. The next user gate is review of the audited results; any departure affecting scientific definitions returns for review before implementation.
