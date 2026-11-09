# Step 4 E2 — Historical scope and validation-policy comparison

Date: 3 November 2026 (Australia/Sydney).

**Status: REVIEW DRAFT — NOT EXECUTABLE.** The user proposed the 2001–2022 research scope and requested an experiment to assess the importance of temporal validation. This document makes that comparison concrete under the established plan-review-before-development workflow. The earlier S4 E1 execution approval does not approve this new implementation, candidate comparison, equivalence margin or budget. No new model has been fitted. Historical contracts, results and the research-stage ledger are unchanged.

## 1. Objective and the claim this design can support

Predict where an object already in a qualified 1-degree origin cell will end up after 7 or 30 days. Assess whether selecting a model and its borrowing parameters with whole-ID, calendar-mixed CV instead of forward, whole-ID-isolated CV materially affects subsequent-period predictions.

The operational alternatives are:

- Temporal selection matters: the two selection policies produce a meaningful difference in later-period performance or model choice.
- Calendar-mixed selection is practically comparable: differences in later-period Brier, hits and region size are contained within preapproved equivalence margins for the assessed periods.
- Evidence is insufficient: intervals or period-to-period variation do not resolve the alternatives.

This is not a test that the ocean is or is not Markov, a proof that transition probabilities are stationary, or a universal permission to train on future observations. It evaluates two model-selection procedures for this prediction task. Their internal fitting populations differ as part of those procedures; final training and outer validation are matched. No causal attribution of all differences to physical ocean drift is intended.

## 2. Proposed common population and unchanged definitions

- Final cleaned release v7; existing qualified development labels only. Locked final-test IDs remain excluded.
- Origin time in [2001-01-01, 2023-01-01) UTC, limited to actually available qualified records. This is an origin-observation-time filter, not a deployment-year filter. The year 2022 is incomplete.
- Preserve earlier records and previous results. Exclusion from this experiment does not declare earlier observations invalid or physically obsolete.
- Retain R/D, 1-degree cells, pooled drifter scenario, annual pooling, direct 7/30-day stopped-first-exit targets, exact matching and existing eligibility.
- Raw qualified-pair training counts; equal times within ID/origin, equal IDs within origin, then equal origins for primary evaluation.
- Standard complete-distribution Brier; 90% mass regions with existing cutoff ties; no probability clipping, altered exit semantics, spatial loss or added season/environment feature.

Read-only inventory, before any fold-specific exclusions:

| Horizon | Pre-2001 excluded pairs / IDs | Fraction of original pairs | Remaining pairs / IDs / origins |
|---|---:|---:|---:|
| 7 days | 347 / 2 | 0.1144% | 302,941 / 383 / 37 |
| 30 days | 116 / 1 | 0.0431% | 268,882 / 336 / 37 |

The exclusions consist of 231 seven-day pairs from one ID in 1998, and 116 pairs at each horizon from another ID in 2000. These counts do not describe the entire raw database. They were recomputed from [saved source-keyed origin features](../results/deliverables/seasonal_conditioning_s4_e1/origin_features.parquet). Formal execution must verify and reconstruct roles from the sealed source labels.

## 3. Why two raw CV averages are not the main contrast

An all-history grouped-CV average and a 2020–2022 forward-validation average use different targets, fitting sizes and sampled conditions. Subtracting them does not isolate a temporal effect.

Instead, both selection policies receive the same outer training inventory. Each selects parameters and a model using only that inventory. Every selected model is refitted on the identical complete outer training set and evaluated on the identical later-period cases and weights. This controls final fitting data and evaluation difficulty.

B2 has no tuning parameter. Its final forecasts must be identical under both selection policies for the same outer block. This is an important semantic check. Only a change in selected family or borrowing parameters can change the primary policy-selected forecasts.

## 4. Outer forward blocks

Use three prespecified development backtests, not only the previously inspected 2020–2022 block:

| Block | Outer training origin years | Outer validation origin years | Validation pairs / IDs, 7 days | Validation pairs / IDs, 30 days |
|---|---|---|---:|---:|
| A | 2001–2013 | 2014–2016 | 41,761 / 50 | 35,035 / 40 |
| B | 2001–2016 | 2017–2019 | 48,189 / 64 | 44,700 / 60 |
| C | 2001–2019 | 2020–2022 | 33,971 / 45 | 30,128 / 42 |

These validation counts are read-only inventory expectations before support masking, not evidence of adequate training support. Distinct IDs can occur in more than one validation block, so their counts must not be summed as independent individuals.

For each block, form the union of outer validation IDs across both horizons before checking support. Remove all their records from outer training at both horizons. Retain a training label only if its required observation interval ends strictly before the outer cutoff; preserve the approved earlier-established absorbing-exit exception. No record later than the outer cutoff can fit, tune, define a prior or set a support scale for that block.

The outcome window for an outer validation origin may extend past the end of its nominal calendar block if the existing label is qualified. Calendar blocks classify departure time. Any later fitting role still applies its own label cutoff and ID exclusion. Cross-block dependence is retained in uncertainty handling.

Earlier validation blocks can subsequently be historical training data for later blocks, as in an expanding-window forecast. All blocks, candidate grids and selection rules must be frozen before scoring; earlier scores cannot change later designs. All periods have prior project exposure and remain development evidence.

## 5. Two internal selection policies

### G: Calendar-mixed whole-ID CV

Use five whole-ID folds from the existing frozen mapping, restricted to the eligible outer-training ID roster. Preserve each ID's fold across horizons. A held-out ID contributes no fitting record, B1 prior information, donor distribution or support statistic within that fold. Calendar years may mix within a fold, but all records remain inside the outer information boundary.

### T: Forward whole-ID-isolated CV

Use these two internal forward blocks for each outer block:

| Outer block | Internal fit → validation 1 | Internal fit → validation 2 |
|---|---|---|
| A | 2001–2007 → 2008–2010 | 2001–2010 → 2011–2013 |
| B | 2001–2010 → 2011–2013 | 2001–2013 → 2014–2016 |
| C | 2001–2013 → 2014–2016 | 2001–2016 → 2017–2019 |

At every internal boundary, purge crossing training labels and the union of internal validation IDs across horizons. Internal validation labels must themselves lie within the already eligible outer training inventory. No outer validation information enters internal folds.

For each policy, concatenate its held-out inner predictions and recompute the existing equal-origin/equal-ID/equal-time hierarchy over that policy's evaluable inner roster, rather than giving each fold an arbitrary full vote. All candidate models within a policy use the same B2-supported inner cases. Report the policy-specific training sizes, distinct-ID support, scored fractions and validation season/year mix. Internal CV averages are not directly comparable matched scores; the primary comparison is their selected forecasts on the common outer roster.

## 6. Model families and locked selection rule

Retain the established S3 E2 definitions of B2, Fixed, Adaptive, LocalEndpoint and LocalEndpointAdaptive. Rebuild their counts, priors and donor distributions from the current fitting role. Do not reuse old fitted matrices or all-history chosen parameters.

- Fixed and global Adaptive retain their documented B2/B1 definitions.
- LocalEndpoint retains the eight adjacent eligible R cells, excluding self, original endpoint borrowing and established no-donor fallback.
- LocalEndpointAdaptive retains distinct-local-ID and distinct-neighbour-ID support definitions and its original adaptive formula.
- Borrowing parameter a: 0, 0.05, ..., 1. Local adaptive gamma: 0, 0.5, 1, 2.
- Source definition reference: [S3 E2 plan](local_endpoint_adaptive_s3_e2_plan.md), [configuration](../configs/local_endpoint_adaptive_s3_e2.json). Any implementation ambiguity is resolved against those definitions before real-data execution.

Within each family, select by inner primary Brier, retaining the established deterministic parameter ties. Each policy also selects one family per horizon by lowest inner Brier. For a family tie within 1e-12 use this frozen preference: B2, Fixed, Adaptive, LocalEndpoint, LocalEndpointAdaptive. Report all families and selected parameters; use the policy-selected winner for the primary G-versus-T comparison. Refit all selected family variants on the same outer training inventory for secondary matched comparisons.

No parameter-grid expansion, seasonal conditioning, geometry transfer, window-length search or post-score model substitution is included.

## 7. Evaluation and proposed decision criteria

Primary contrast: T-selected minus G-selected on the common outer B2-supported cases, separately for each horizon and each block. Report unsupported origins/cases/IDs and fractions against all eligible cases; never hide a support loss. Final B2 support is identical across the two policies because their outer training inventory is identical.

Report Brier, K90, H90, region probability mass, zero-probability truth fraction, E, fitting support, model selections, parameter stability, and cost. Keep pair-weighted summaries secondary and distinctly labelled.

Use 10,000 shared positive whole-ID multiplier draws, PCG64 seed 20261103, with fitted forecasts fixed. An ID receives the same multiplier across all its origin cells, horizons and outer blocks. Renormalise ID weights within origin and retain equal-origin aggregation. Record conditional intervals and limits: refitting, model-selection uncertainty and shared ocean events are not fully covered.

Quality-preserving superiority retains the existing directions: lower Brier, no reduction in H90, no increase in K90. Report both point results and supported results. With six block/horizon contrasts and three primary metrics, use simultaneous conservative two-sided intervals with per-tail probability 0.05/(2*18) for supported screens; ordinary 95% intervals are also shown. Family-specific secondary comparisons are descriptive.

To claim practical similarity, proposed margins requiring explicit approval are:

- absolute Brier difference within ±0.001;
- H90 difference within ±1 percentage point;
- relative K90 difference within ±5%, using G as denominator.

These margins are engineering proposals, not literature-derived physical constants and not a relaxation of the quality-preserving-superiority criterion. Similarity requires the adjusted intervals to lie within all three margins in all assessed block/horizon combinations. If a K90 denominator is zero, relative equivalence is undefined and no such claim is made. An interval crossing zero or a nonsignificant test alone never establishes equivalence. If these margins are not approved, remove the equivalence decision and report differences/uncertainty only.

Improvement or equivalence limited to one period or horizon is labelled accordingly. Do not average away an adverse block. Differences between periods are descriptive unless supported by the prespecified paired policy contrast; they cannot independently prove an oceanic change point.

## 8. Resource gates and verification

Proposed cumulative real-data cap: 65 minutes, consisting of a 5-minute resource pilot, a 30-minute primary run and a 30-minute fresh replay. One process/one numerical thread, maximum 8 GiB RSS and 5 GiB new artifacts. Pilot timing should use verified full-role counts and synthetic targets for scoring-capacity checks; do not inspect outer skill to choose the execution scope. Reuse count aggregation and candidate forecasts within fitting roles. Stop and report if projected remaining work exceeds the cap; do not reduce samples or silently drop a block.

Before execution, verify source hashes, exact population filters, boundary cases, cross-horizon ID exclusions, inner/outer information boundaries, model nesting, weight normalisation and common support masks. Synthetic checks must include B2 equality across G/T, hand-calculated score/region examples, winner-selection isolation, and deterministic replay.

Freeze all outer forecasts, selections and weights before scoring any outer outcomes. Save independent role tables and fitting/validation keys, candidate scores, selected parameters, prediction matrices, case scores and uncertainty. A separate arithmetic audit must reconstruct counts, Brier, regions and weighted summaries. Replay must match numeric artifacts within 1e-12 and figure identities under the frozen environment.

## 9. Deliverables and approval boundary

Deliver an independent run and review page with: the three time-block diagrams, G/T model and parameter selections, per-block 7/30-day Brier/K90/H90 comparisons, paired uncertainty, support/zero-truth diagnostics and matched probability maps chosen by a support rule frozen before scoring. Preserve existing historical results with their original evaluation labels.

The next approval must cover this specific operational question, outer/inner blocks, five model families, selection rule, proposed equivalence margins, and resource cap. Until then, only the inventory and this review draft are complete. No new model execution, research-stage closure, Git publication or locked-final-test access is authorised by this document.

Background: [evidence review](temporal_validation_evidence_review.md); [official grouped and temporal validation discussion](https://scikit-learn.org/stable/modules/cross_validation.html).
