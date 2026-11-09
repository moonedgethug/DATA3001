# Step 4 E7 | Superseded exact-origin proposal v1

**SUPERSEDED — never approved or executed.** The user rejected the default B2 fusion and subsequently confirmed exact-coordinate empirical transitions, equal votes among selected nearby records, and 0.5-degree output aggregation. See [the current v2 contract](exact_origin_s4_e7_plan.md). The text below is retained only as proposal history.

## Material Passport

- Origin Skill / Mode: academic-research-suite, experiment-agent / plan
- Date: 5 November 2026, Australia/Sydney
- Version: engineering contract v1, submitted for user review
- Verification Status: design only; historical schemas, rosters and baseline output inspected
- Execution status: NOT APPROVED. No E7 feature extraction, fitting or experiment has run.

E5 identifies the existing speed proposal and E6 the wind proposal. E7 is a new, independent experiment. This document does not amend the approved stage ledger. The user's current division is Step 4 for testing precise location information and Step 5 for subsequent estimator improvements.

## 1. Research question and scope

Given a qualified departure at its recorded longitude and latitude, does using its position **within the existing 1-degree origin cell** improve the direct seven-day destination distribution relative to annual B2?

Compare exactly two primary forecasts:

| Forecast | Historical records used | How records vote |
|---|---|---|
| Annual B2 | All eligible seven-day pairs from the query's origin cell | One vote per observation pair |
| ExactOrigin B2 | The identical pairs, with their unchanged destination labels | Nearby historical starts receive larger positive weights; the adjustment strength is selected inside the training period |

The estimand remains the stopped seven-day destination on the existing D grid plus absorbing exit E. It is not the entire transport trajectory. A drifter may supply multiple qualified departure times. Training preserves the established raw-pair B2 counts; scoring and parameter selection preserve equal-ID/equal-origin weighting. These are deliberately different operations, not a new equal-ID training experiment.

Only departure position changes the forecast. No Gaussian distribution, MDN, neighbour borrowing, endpoint translation, trajectory translation, environmental predictor, heading or speed enters E7. Seven days is predicted directly, without repeated short-step propagation. Four- and thirty-day extensions require a separate decision.

The local weighting rule is a proposed minimal estimator for testing position, not a reproduction of Brolly's continuous-density models. Adding coordinates to an input table alone would leave B2 unchanged; some explicit rule must connect coordinates to probabilities. The existing [method audit](transport_experiment_design_audit.md) remains background, not evidence that this new rule will work.

**Interpretation boundary.** E7 tests this bounded within-cell adjustment. It cannot create an endpoint absent from the annual B2 row, remove cell-boundary discontinuities, or establish that every position-based model helps or fails. Geographic proximity across a coastline need not imply dynamical similarity. We retain the original observed endpoint labels rather than asserting a new physical route.

## 2. Frozen data, target and temporal roles

Use the manifest-owned cleaned v7 development pool, pooled drifter scenario, existing R/D masks, one-degree cells and the sealed stopped-first-exit labels. A year refers to the qualified departure time in the research region, not deployment year. The available 2022 records cover only part of that year.

Reconstruct the exact E4 seven-day roles. Retain E4's outer validation-ID reservation across **both historical horizons**, even though E7 scores only seven days. This preserves the established roster instead of admitting additional training IDs. Construct the two inner roles inside eligible outer training, retaining their existing cross-horizon ID purges. The full observation interval required to establish a fitting label must end strictly before its cutoff, including the existing early-exit rule. No ID may occur on both sides of a given split.

| Role | Fitting departures | Held-out departures | Fitting pairs / IDs | Held-out pairs / IDs |
|---|---|---|---:|---:|
| Inner 1 | 2001–2013 | 2014–2016 | 170,978 / 234 | 41,761 / 50 |
| Inner 2 | 2001–2016 | 2017–2019 | 209,934 / 280 | 44,612 / 58 |
| Outer development validation | 2001–2019 | 2020–2022 | 265,393 / 338 | 33,971 / 45 |

These are historical reconciliation targets, not E7 results. Outer validation has 36 origin cells, all with annual B2 support. The current reference is [E4's plan](departure_direction_s4_e4_plan.md), [saved roster](../results/deliverables/departure_direction_s4_e4/outer_roster.parquet) and [saved metrics](../results/deliverables/departure_direction_s4_e4/summary.csv). Pin their resolved run paths and hashes before implementation; a moving deliverable link is not a reproducibility identifier.

The 2020–2022 period has already informed earlier research decisions. E7 is a controlled development comparison, not a new independent final test. Keep the canonical final-test pool locked.

## 3. Exact coordinates and prediction-time information

Join each donor/query key `(id, origin_source_obs)` to its manifest-owned development track. Read `lon_normalized`, `lat`, time and `cell_1`, plus the existing analytical-row, position and mapping qualification flags. Preserve stored coordinate precision. Check the key, ID, UTC departure time and cell against the sealed role. Use the existing grid mapper and longitude convention, including boundary conventions.

Only the position at departure time t0 is an input. No preceding velocity interval or subsequent position is required. Missing predecessors therefore do not cause E7 fallback. Historical GDP coordinates are processed observations; this experiment assumes an equivalent usable release coordinate is available when a forecast is issued.

Duplicate source keys, missing joins, invalid declared-qualified coordinates, failed hashes or inconsistent cells/times stop the run. They must not silently delete cases, move starts to cell centres or trigger an outcome-dependent fallback. An unsupported annual row retains the established common support mask and is reported separately; it is not assigned E. No new unresolved state is introduced by this estimator.

Future position-only API requests with an unavailable exact coordinate may receive annual B2 when a valid origin cell is supplied. This is distinct from repairing a broken research input. The E7 research roster is expected to have all exact origins available.

## 4. A single, bounded distance rule

For query start x and donor start x_r in the same origin cell i, compute WGS84 shortest geodesic distance d_r in metres using the existing geodesic implementation. This distance defines statistical similarity, not an over-water route or travel time.

Propose one fixed distance scale **b = 100,000 metres** and the non-Gaussian rule

$$
K_r(x)=\tfrac12+\max\left(0,1-\frac{d_r}{b}\right).
$$

| Distance between starts | Raw donor weight |
|---:|---:|
| 0 km | 1.5 |
| 50 km | 1.0 |
| At least 100 km | 0.5 |

The proposed scale is comparable to the grid's spatial resolution. It is a design convention, not an inferred ocean correlation length. Fix it before execution; do not search distances after viewing outer results. Every donor retains a positive vote, with a maximum raw ratio of 3:1. Records at exactly the same start remain separate observations unless their identical weighted contributions are combined with their original multiplicities.

Let N_i be the number of eligible fitting pairs in origin i, Y_r their original destination labels including E, and A_ij the annual B2 row. Form

$$
A_{ij}=\frac{\sum_{r\in i}\mathbf1\{Y_r=j\}}{N_i},\qquad
S_j(x)=\frac{\sum_{r\in i}K_r(x)\mathbf1\{Y_r=j\}}
                  {\sum_{r\in i}K_r(x)},
$$

$$
P_j(x;\beta_7)=(1-\beta_7)A_{ij}+\beta_7 S_j(x),
\qquad 0\leq\beta_7\leq1.
$$

Here S is the full proposed location adjustment. Beta controls how much of it to retain. Zero gives annual B2 exactly; one gives S. One beta applies to every origin cell at seven days. This is not an adaptive sample-count formula and does not fit one parameter per cell.

All probabilities stay nonnegative and sum to one. The positive endpoint support is **exactly** annual B2's for every beta. Consequently, annual zero-probability truths remain zero-probability truths, and the total number of positive destination cells cannot fall. The nominal 90% region may change because probabilities are redistributed. A different zero-truth rate would be an implementation error on this matched roster.

## 5. Select beta inside the training period

Fit A and compute S separately for each inner role using only that role's fitting donors. Generate forecasts on its held-out starts. Pool both inner held-out windows on their common annual-supported roster. Average times equally within `(ID, origin)`, IDs equally within origin, then origins equally. If an ID/origin appears in both windows, pool its times before assigning that ID's contribution. Include every supported case, including those for which S equals A.

For normalized case weights a_t, one-hot truth y_t and delta_t = S_t - A_t, compute

$$
U=\sum_t a_t\|\delta_t\|^2,\qquad
V=\sum_t a_t(y_t-A_t)^\top\delta_t,
$$

$$
L(\beta)=L(0)-2\beta V+\beta^2U,\qquad
\widehat\beta_7=\operatorname{clip}_{[0,1]}(V/U).
$$

Use beta zero if U is zero, or if the improvement over zero is at most 1e-12 Brier. This is a closed-form minimizer of the specified inner Brier, not proof of a globally optimal transport model. Save full-precision coefficients, both per-window curves, the pooled curve and boundary losses. Independently check direct Brier at the solution and on a 0.01 grid. The grid verifies arithmetic; it does not add another model search.

Select beta on Brier alone. Outer hit rate and region size are acceptance checks, not tuning feedback. Refit A and donor summaries on all eligible outer training; retain the selected beta. Freeze outer keys, coordinates, probabilities, weights, 90% masks and their hashes before joining held-out destination labels for scoring. Outer queries may supply their known coordinates to issue predictions, but neither their coordinates nor outcomes may alter the distance scale or selected beta.

## 6. Matched scoring, uncertainty and decisions

Use standard unhalved multiclass Brier over all D states plus E:

$$
BS_t=\sum_j(P_{tj}-\mathbf1\{Y_t=j\})^2.
$$

Use the same hierarchical evaluation weights for Brier, H90 and K90. Construct the nominal 90% region with the established positive-state sorting, 1e-12 cumulative tolerance and inclusion of all positive ties at the cutoff. H90 is observed membership, including E if admitted. K90 counts geographic cells only. Report attained probability mass, since discrete ties can make it exceed 90%.

Reconcile annual source keys, probabilities, weights and masks to E4, and its unrounded aggregate scores to absolute tolerance 1e-12. The historical seven-day targets are Brier **0.9956533528969523**, H90 **0.7501452117911112**, and K90 **18.166666666666572**. The weighted zero-truth rate is **0.05690042255185551**. These are baseline checks, not the expected E7 improvement.

The primary contrast is paired mean Delta Brier = ExactOrigin minus annual B2. Test H0: Delta >= 0 against H1: Delta < 0. Use 10,000 whole-ID Exp(1) multiplier draws, PCG64 seed 20261105. Each ID receives the same multiplier across all of its origins; renormalize IDs within each origin and keep origins equally weighted. This preserves the existing inference convention rather than pretending overlapping hourly pairs are independent.

For observed difference d and bootstrap difference d*, report the ordinary two-sided 95% conditional interval. The centered one-sided upper bound is `d - quantile_0.05(d* - d)`, using linear quantiles. E7 has one primary horizon and contrast, so its within-experiment level is 5%, unlike E4's two-horizon correction. This does not erase the broader history of adaptive development. Report paired 95% intervals for H90 and K90 as diagnostics, without claiming joint noninferiority from nonsignificant differences. These intervals condition on the fitted models and observed origins; they do not capture refitting or all shared ocean-forcing uncertainty.

| Decision | Predeclared criterion |
|---|---|
| Engineering valid | Roster, leakage, probability, baseline reconciliation and independent numerical audits all pass |
| Brier benefit supported in this development comparison | Delta Brier < -1e-12 and its one-sided upper bound < 0 |
| Point-estimate quality preserved | Delta H90 >= -1e-12 and Delta K90 <= 1e-12, together with lower Brier |
| Recommend retaining ExactOrigin for seven-day development use | Supported Brier benefit and point-estimate quality preservation both hold |
| Improvement with a trade-off | Brier improves but hits decrease or the region grows; report the cost and retain the existing default pending discussion |
| Benefit unestablished | Beta is zero, forecasts are unchanged, Brier does not improve, or uncertainty does not support a benefit |

A point-estimate pass is not proof that population hit rate and region size cannot worsen. Report absolute and relative Brier change, hit change in percentage points and cell change alongside intervals. A statistically detectable but negligible benefit must be described as small. There is no defensible preset power claim for this design; the fixed outer sample contains only 45 independent IDs, not 33,971 independent experiments.

Report unsupported counts and target weights; E mass and observed exits; zero-truth rate; per-origin pair and independent-ID support; and no-change cases. For the location weights, report donor effective sample size `(sum w)^2 / sum(w^2)` and largest ID share, using effective donor weights `w_r=(1-beta)+beta*K_r/mean(K)`. These are diagnostics, not new rejection thresholds or weights.

## 7. Engineering architecture and resource gates

Reuse the existing qualification adapter, temporal roles, annual B2, grid/state ordering, region construction, hierarchical scorer and ID-multiplier routines. Add isolated E7 coordinate extraction, distance-vote calculation, pipeline/report and audit modules under the current Markov baselines. Do not modify the meaning of shared historical routines to accommodate E7.

Proposed files after approval:

- `configs/exact_origin_s4_e7.json`
- `src/data3001/modelling/baselines/exact_origin_s4_e7{,_inputs,_pipeline,_audit,_report}.py`
- `src/data3001/modelling/baselines/run_exact_origin_s4_e7.py`
- `tests/test_modelling_exact_origin_s4_e7.py`
- isolated timestamped `results/runs/exact_origin_s4_e7_*` runs and provenance receipts
- `results/deliverables/exact_origin_s4_e7/` and `docs/exact_origin_s4_e7_results.md` after review

Use the existing project Python environment, NumPy/Pandas/Parquet and WGS84 geodesic dependency. Proposed runner phases are pilot, primary and replay, with explicit config and receipt arguments. Final command syntax is an implementation detail recorded with the execution freeze.

**Known workload, measured from saved counts only.** Summing held-out pairs times training pairs within origin gives 264,729,979 distance evaluations for inner 1, 287,650,395 for inner 2 and 323,550,082 for outer prediction: **875,930,456** before exact duplicate reuse. The largest fitting row has 17,376 donors. This inventory did not extract coordinates or calculate E7 forecasts.

Compute distances in bounded batches of at most 1,000,000 query-donor combinations, accumulate destination weights and immediately release temporary arrays. Never materialize the complete query-by-donor matrix. Exact duplicate coordinates may share distances; repeated observations retain their multiplicities and labels. Cache the A and S vectors once for each role/query; beta selection, grid arithmetic checks, regions and resampling do not recompute distances. Do not round coordinates, subsample records or replace geodesic distances with unapproved approximations for speed. No synthetic path or hourly path-validity calculation is required.

| Phase | Proposed wall-clock cap | Gate/output |
|---|---:|---|
| Cumulative pilot attempts | 600 seconds | Full roster/coordinate integrity checks, representative distance workload, small independent calculation checks, measured runtime/RSS/storage projection |
| Primary experiment | 3,600 seconds | All inner and outer samples, prediction freeze before held-out scoring, complete report |
| Independent audit and fresh replay | 3,600 seconds | Rebuild forecasts from source inputs in a new run; independently recover metrics and inference flags |
| Total | 7,800 seconds (130 minutes) | Failed attempts count toward the budget |

Use one process and one numerical thread, at most 8 GiB peak RSS and 5 GiB new retained artifacts. The pilot takes a deterministic sample of at most 4,096 query keys across all three roles and every represented origin, including queries from the largest donor row. Record which pairs were benchmarked and project each role using its workload and conservative measured throughput. It may use outer coordinates with synthetic target labels; it must not score actual outer outcomes or select beta. The full experiment still includes every qualified pair.

No runtime has been measured for E7. At a **hypothetical** sustained 1 million comparisons/second the raw distance workload alone takes about 14.6 minutes; at 0.5 million it takes 29.2 minutes, before input, aggregation and audit overhead. These are sizing scenarios, not promised performance. Proceed automatically after approval only if the pilot and integrity checks pass and twice the projected total phase runtime fits each 3,600-second cap, with the same 2x reserve for storage and memory projections. Otherwise stop with the measured bottleneck and a revised proposal. Do not exchange accuracy or sample completeness for meeting the cap.

Write progress, role/query counts, elapsed time, peak RSS and projected remaining time to the run receipt; check progress at intervals no longer than 60 seconds. Existing shared output links are updated only after successful audit, using separate run directories for primary and replay.

## 8. Required checks and deliverables

Before formal execution, test and independently verify:

1. Source-key and time/cell reconciliation, interval-boundary exclusion, whole-ID role separation and final-test access protection. Changing outer outcomes cannot change features, beta, predictions or region masks.
2. Identical-coordinate distance zero; 0/50/100-km weight examples; distance symmetry; cell-edge mapping; repeated observations retaining multiplicity; probability normalization; E handling; beta zero recovering B2; constant weights recovering B2; support and zero-truth invariance.
3. A simple literal donor-vote reference agrees with the batched implementation on synthetic examples and deterministic real queries from every role. Require probability agreement within 1e-12; do not waive discrepancies as speed optimizations.
4. Direct and quadratic Brier calculations agree; the selected beta minimizes the checked curve. Independently reconstruct hierarchical weights, H90/K90, paired changes and multiplier decisions from frozen predictions.
5. Fresh replay reproduces source-key ordering, role membership, beta, vectors, masks and aggregate metrics, with floating-point tolerance 1e-12 and identical discrete decisions. Compare immutable input hashes before and after.

Deliver an English review page with a two-model score table, paired intervals, the inner beta-loss curves, per-origin changes and training-support diagnostics. Provide matched forecast maps with shared scales and the same nominal 90% rule. Fix examples from training support and query coordinates before viewing outcomes: choose three eligible origins nearest the 25th/50th/75th percentiles of training independent-ID counts, resolving ties by cell ID; in each show held-out starts nearest its longitude quartiles, resolving ties by source key. Deduplicate examples if necessary. Overlay the actual held-out endpoint only after forecast freezing. One observed endpoint is not an observed conditional probability distribution.

Archive the approved contract/config, input inventory, role roster, coordinate provenance, full-precision beta/curves, forecast vectors, masks, case scores, support diagnostics, resource receipts and audit result. Report a null or trade-off result as a completed experiment. Do not repeatedly retune this contract until it wins. Any subsequent bandwidth, neighbour or distribution-model experiment returns to user review.

## 9. Review items

Approval of this v1 contract would authorize: seven days only; the exact existing E4 roster; within-cell geodesic weighting with fixed 100-km scale and maximum 3:1 raw contrast; one training-selected beta; annual B2 as the primary control; the stated development inference and quality criteria; and pilot-gated execution within the stated budget. Until that approval, this file is the sole E7 deliverable.
