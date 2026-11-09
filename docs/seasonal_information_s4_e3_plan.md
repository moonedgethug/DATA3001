# Step 4 E3 | Does departure season improve destination forecasts?

**Engineering proposal for review · 5 November 2026 (Australia/Sydney).** Implementation and real-data execution await separate user approval. This document records the proposed decisions. The study uses the existing 2001–2019 / 2020–2022 development split.

## 1. What the experiment measures

Given a drifter in a known 1° origin cell at a qualified departure time, predict the distribution of its stopped destination 7 or 30 days later. The primary question is whether a seasonal adjustment chosen from past data lowers expected Brier loss for later drifters. The secondary question is how much predictive performance is lost when an empirical table is restricted to the support available in a single season, and how much using the correct season recovers.

The earlier E1 fitted on 2012–2019. On its 2020–2022 validation cases, true endpoints assigned positive annual probability and zero seasonal probability accounted for 21.42% / 31.74% of the evaluation weight at 7 / 30 days. New E3 fits use the longer history. The earlier inspection, including the exploratory direction of the Brier curve at zero seasonal weight, motivates the question. It cannot set the E3 weight or count as independent confirmation. Interpretation is predictive, conditional on this backtest and the fitted forecasts. [E1 evidence](seasonal_conditioning_s4_e1_results.md) · [E2 chronology and limitations](temporal_validation_s4_e2_results.md)

## 2. Common records and time boundaries

Use sealed v7 development labels on the existing R/D grid, pooled drifter scenario, exact direct horizons, and the existing first-exit absorbing outcome E. Season is DJF, MAM, JJA or SON from UTC **departure** month. Training counts every qualified observation pair once. The inferential population gives equal weight to drifters within each origin and equal weight to origins. The 2022 record is incomplete. Final-test data remain locked.

| Role | Fitting departures | Validation departures | Expected validation pairs / distinct IDs, 7 days | Expected validation pairs / distinct IDs, 30 days |
|---|---|---|---:|---:|
| Inner 1 | 2001–2013 | 2014–2016 | 41,761 / 50 | 35,035 / 40 |
| Inner 2 | 2001–2016 | 2017–2019 | 44,612 / 58 | 41,123 / 54 |
| Outer | 2001–2019 | 2020–2022 | 33,971 / 45 | 30,128 / 42 |

Define the outer validation-ID union across both horizons before support checks. Remove its IDs from all fitting and internal validation records. A fitting label must be established strictly before its cutoff using the sealed required observation end, including earlier-established exits. Construct each inner split **inside eligible outer training**, then apply its own label cutoff and cross-horizon validation-ID purge. Years refer to departure time in the study, including repeat visits. Outer training should reproduce 265,393 pairs / 338 IDs at 7 days and 235,177 / 294 at 30 days. Counts above are review expectations from the existing C block. Reconcile original keys and weights, investigate any discrepancy before scoring. [E2 role roster](../results/deliverables/temporal_validation_s4_e2/role_roster.csv)

## 3. Three forecasts and the training-only choice of seasonal weight

For each horizon and origin, let **A** be the full annual destination distribution and **S** the empirical distribution restricted to the query season. Estimate both by raw pair counts on the same fitting role. If S has no training pairs, use A and flag the fallback. If A is unsupported, all variants share the same unsupported mask. Report omitted cases, IDs, origins and pre-mask target weight. If even the expected outer B2 roster differs, investigate before making performance claims.

| Forecast | Distribution | Role |
|---|---|---|
| Annual B2 | A | Primary reference |
| Hard seasonal B2 | S | Fixed c=1 control and endpoint-support diagnostic |
| Seasonally adjusted B2 | A + cₕ(S − A) | Primary candidate, one scalar cₕ per horizon, shared across origins and seasons |

Choose each cₕ on the closed interval [0,1]. A weight of zero is a valid outcome. For 0≤cₕ<1, every annual-positive destination retains positive probability. The model family cannot add an endpoint absent from the entire fitted annual origin row.

1. Fit A and S separately in each inner fitting role. Make out-of-fold predictions for its own held-out drifters. Concatenate the two internal validation windows. For a recurring (origin, ID), combine all its supported departure times across the windows before assigning its single ID vote. Give every candidate the same cases and weights. The original calendar order is preserved.
2. Let yₜ be the observed one-hot outcome including E, qₜ = Sₜ − Aₜ, and wₜ the resulting normalized weights at that horizon. Define U = Σ wₜ‖qₜ‖² and V = Σ wₜ(yₜ − Aₜ)·qₜ. The inner Brier curve is L(c) = L(0) − 2cV + c²U. For U>0 choose the bounded analytic minimizer cₕ = clip(V/U, 0, 1). If U=0 or the optimum gains at most 10⁻¹² Brier over zero, choose zero. Save U, V, the unrounded cₕ, both boundary scores and the per-window curve. Verify against direct Brier calculations at the optimum and on a 0.01 grid. The grid is an audit of the analytic solution.
3. Freeze both cₕ values. Refit A and S on all eligible 2001–2019 records. Freeze outer probabilities, support flags, regions, case weights, and all diagnostic samples before joining 2020–2022 endpoints for scoring. Inner windows may select weights but outer scores may never do so. No post-validation choice among A, S and the primary candidate is part of the test.

## 4. Primary hypothesis, uncertainty and quality

For each horizon let Δₕ be the expected **paired** Brier difference, seasonally adjusted B2 minus annual B2. Test H₀: Δₕ ≥ 0 against H₁: Δₕ < 0. A negative difference is a gain. Score each complete probability vector with the existing unhalved multiclass Brier Σⱼ(pⱼ − yⱼ)² on the exact same held-out source key. Brier evaluates the entire probability distribution. [Gneiting and Raftery, 2007](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf)

Within a horizon, average the paired differences over times in each (origin, ID), then equally over IDs within origin, then equally over supported origins. An ID does not acquire extra votes by appearing in several seasons. Record eligible and supported denominators separately.

- Generate 10,000 Exp(1) whole-ID multiplier draws, PCG64 seed 20261105, with shared multipliers for a given ID across origins, variants and horizons. Renormalize IDs within each origin and retain equal origins. For the primary test use a one-sided **centered multiplier** bound. With observed difference d and draw d*, let r=d*−d and upper bound u=d−quantile(r,0.025), using linear quantiles. The per-horizon 2.5% lower-tail test gives nominal family-wise 5% across the two horizons by Bonferroni. Declare evidence of improvement only if u<0. Report d, u and ordinary two-sided 95% conditional intervals. If the trained c is zero or forecasts coincide, report identical forecasts and no demonstrated gain.
- Report actual H90 hits, mean geographic K90 cells and issued region mass for all three forecasts. Use the shared 90% helper with cutoff ties. E counts for probability and hits when included, and contributes zero geographic cells. Report paired H90 and K90 changes with descriptive uncertainty. Also report zero-probability truth, annual-positive/seasonal-zero truth, E mass and observed exits, seasonal fallback, and year/season/support slices using original evaluation weights.
- Report **predictive evidence** and **operational trade-offs** separately. A seasonal Brier benefit requires the primary test above. Call it a point-level quality-preserving gain only when Brier is lower, H90 is no lower and K90 is no greater than annual B2 (numerical tolerance 10⁻¹²). A Brier gain that costs hits or cells keeps its actual label. Each horizon gets its own decision. Failure to reject H₀ establishes insufficient evidence for this adjustment.
- These are approximate conditional tests over validation drifters. The shared weights preserve repeated observations and cross-horizon ID dependence. They do not represent uncertainty from refitting, searching c, common ocean events, or having inspected this period in prior rounds. Year-specific results show stability descriptively.

## 5. Equal-sample control for the cost of splitting

For each nonempty outer-training (origin, horizon, season) table, construct **200** season-blind matched annual subsamples using training inputs alone. For a summer query, for example, the shape of the summer sample sets the target size, while qualified donor records may come from any month. Score each subsample on the same outer cases as the real seasonal row. This estimates loss in Brier points and probability support under a specific sampling design.

**What each draw matches.** Require the exact number of pairs and distinct drifters in the true seasonal table. Match each contributor's pair counts by UTC calendar year and preserve runs of adjacent hourly departures. This also preserves the distribution of per-ID contributions and total year counts. Match on source identity/time, availability and origin. Destination, path direction, exit and validation performance are unavailable to the sampler. The chosen records then provide the usual raw endpoint counts.

**Reproducible sampler.** Within one table, use each contributing seasonal ID as a template. For each calendar year of that ID, store its set of eligible departure times as hour offsets from its first time. A candidate annual donor ID is feasible if, in every required year, that year's template can be translated by a whole-hour offset into available training departure keys for that same donor and origin. This preserves contiguous runs and within-year gap lengths. Form a one-to-one template-to-donor assignment. For each draw assign independent uniform random costs to feasible edges, use the minimum-total-cost full assignment, then sample one feasible time placement uniformly in each donor/year. Sort stable keys and resolve ties lexicographically. The original IDs and times always supply a feasible assignment. Donor selection is random under this defined scheme, with no claim of uniform sampling over all possible matched tables. Check distinct IDs, unique source keys, year counts, multiplicities and continuity for every draw. Match separately by horizon and table. Use PCG64, master seed 20261106 and deterministic child streams per (replicate, origin, horizon, season), separate from the uncertainty draws.

**Where matching has little power.** Permit true-season observations to reappear naturally. Log how many draws use identical keys, the share of pairs from other seasons, donor diversity and the variation in real and predicted endpoint support. If the true season is empty, both hard seasonal and matched-control forecasts use the annual fallback for the all-case accounting. Show nonempty rows separately. A row with no feasible other-season observations is uninformative for a season-specific interpretation. Prespecify a sensitivity subset with mean other-season share ≥25% across the 200 draws, determined from training alone. Report its outer case count and original evaluation weight. If it covers less than 80% of that horizon's evaluation weight, describe its contrasts as subset evidence, with inadequate design contrast for a population-wide explanation. These proposed thresholds are interpretation rules, not empirical findings.

**How to read the result.** Let L_A be mean annual Brier, L_S mean hard-seasonal Brier, and L_R the mean of the 200 individually scored matched controls. Average losses across draws **after scoring**. Averaging probability vectors first would create a new ensemble that benefits from extra data across draws. All three summaries use the same cases and weights.

| Reported contrast | Meaning of a positive value |
|---|---|
| L_R − L_A | Brier cost of reducing the full annual table to matched seasonal support |
| L_R − L_S | Using the correct season recovers Brier performance relative to a table of equal sample size |
| L_S − L_A | Net cost of the actual hard seasonal split, equal to the first contrast minus the second |

Give both diagnostic contrasts, their descriptive paired-ID intervals and Monte Carlo standard errors from the 200 complete-replicate contrasts (SD/√200). Also report positive-probability destination counts and weighted zero-truth differences, with the same three-way comparison. Mark a sign unresolved if its descriptive interval contains zero or if the Monte Carlo error band of ±1.96 MCSE crosses zero. Show full-roster results first and the informative subset separately, using original weights normalized to that subset. A positive sampling cost and positive seasonal recovery smaller than that cost support the proposed explanation for c=1. The quantities are conditional on the date/ID matching scheme. They measure predictive cost rather than physical causality or information in bits. The matched draws neither choose c nor enter the two primary hypothesis tests.

## 6. Execution and deliverables after approval

Reuse the verified E1 seasonal counts, departure-season encoding, D-plus-E state order and region helper, and the E2 chronological role logic. Rebuild each fitting role from the sealed development keys. Keep E3-specific selection, matched sampling, paired inference and independent audit under a new E3 namespace in the Markov baselines. Reuse old outputs as read-only reconciliation targets. The new annual B2 row on the outer block must reproduce E2 C forecasts and scores to absolute 10⁻¹² with aligned state order and identical case weights.

| Gate | Required evidence |
|---|---|
| Synthetic and lineage checks | Strict cutoff and earlier-exit fixtures, whole-ID isolation across horizons, season decoding, repeated-ID weights, fallback, flat/interior/boundary c solutions, direct score-vs-quadratic agreement, ties/E, valid matched keys, unit example for the loss decomposition. Perturbing outer endpoints must leave c, donors and forecasts unchanged. |
| Bounded pilot | Full role/row inventory and matching feasibility, timing with synthetic outer targets, end-to-end cost projections with a 2× reserve. Proposed cumulative stage caps are 600 s pilot, 1,200 s primary and 1,200 s fresh replay, 50 minutes total, one process / one numerical thread, peak 8 GiB RSS and 5 GiB combined artifacts. Charge previous attempts. Stop for review if capacity fails rather than reducing pairs or draws. |
| Primary and replay | Freeze training selections, donor manifests and predictions before actual outer scores. Independently verify raw counts, support, direct Brier, regions, weights, matched quotas, decomposition, intervals and flags. Record seeds, hashes, peak resources and access boundaries. Reproduce discrete identities exactly, numeric results within 10⁻¹² and deterministic figures byte-for-byte. |
| Review package | English report and local visual review with 7/30-day three-model metric tables, both c curves and chosen weights, paired Brier intervals, H90/K90 changes, matched-control cost/recovery with uncertainty, donor mixing, endpoint support and fallback. Preserve source-keyed roles, sampled keys, forecast/region tables, scoring denominators and audit receipts. |

The review decision concerns the analytic training-only weight, two-horizon paired test, equal-sample diagnostic, its interpretability rules and the resource limits. E3 development, fitting, sampling and scoring require confirmation of this proposal.
