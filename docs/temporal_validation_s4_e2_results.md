# Step 4 E2 — Existing-model temporal validation results

Date: 3 November 2026 (Australia/Sydney). **Engineering complete; validation-policy decisions remain for user review.**

Calendar-mixed whole-ID CV and forward whole-ID-isolated CV sometimes choose different established models or borrowing parameters. Their subsequent-period performance differences vary in direction. Forward selection is not uniformly better, and the prespecified all-period equivalence criterion is not met. Only block C at 30 days supports equivalence: both policies select exactly the same estimator and parameters. No assessed block/horizon achieves the joint point criterion of lower Brier, no hit loss and no region expansion for T versus G.

This experiment implements a validation procedure, not a new transport estimator. It directly calls the existing S3 E2 fitting and prediction functions for B2, Fixed, Adaptive, LocalEndpoint and LocalEndpointAdaptive. Each historical matrix is rebuilt from its permitted fitting population; reusing an all-history matrix would violate the intended historical information boundary.

## Authority and evidence

- [Approved plan](temporal_validation_s4_e2_plan.md), SHA256 `3adc3f101656712002d4d3f9dbac1aa346c464862852e58c5e84ae993ad896b2`.
- [Subsequent execution approval](../provenance/reviews/temporal_validation_s4_e2_approval.json), [execution fingerprint](../provenance/reviews/temporal_validation_s4_e2_execution_freeze.json), [independent closeout audit](../provenance/reviews/temporal_validation_s4_e2_audit.json), [fault checks](../provenance/reviews/temporal_validation_s4_e2_fault_checks.json).
- [Visual review](../results/deliverables/temporal_validation_s4_e2/review.html), [all family results](../results/deliverables/temporal_validation_s4_e2/summary.csv), [selected parameters](../results/deliverables/temporal_validation_s4_e2/selections.csv), [paired intervals](../results/deliverables/temporal_validation_s4_e2/uncertainty.csv).
- Primary: `temporal_validation_s4_e2_primary_20261103T004920_642021Z`.
- Fresh replay: `temporal_validation_s4_e2_replay_20261103T005026_837238Z`.

The plan remains its original review snapshot; the separate receipt records the later explicit approval. No final-test access, new feature family, scientific stage closure or Git publication was performed.

## Matched design

Qualified development origin times are in 2001–2022 (available 2022 data are incomplete). Raw-pair training, annual pooling, 1-degree origins, direct 7/30-day stopped-first-exit targets, standard Brier and fixed 90% mass regions are unchanged. Scores average times within ID/origin, then IDs within origin, then origins. E remains an outcome in the distribution and hit calculation, not a geographic cell in K90.

G selects with the frozen five-fold whole-ID mapping, mixing calendar years only inside the permitted outer training history. T selects using the two prespecified expanding-window internal splits. Both refit on the same full outer training inventory, then face the same later validation cases. Every temporal fitting boundary excludes labels unavailable before its cutoff and all validation IDs across both horizons. All three outer forecast sets, selected parameters and evaluation weights were frozen before any actual outer scoring.

A trains in 2001–2013 and validates in 2014–2016; B trains in 2001–2016 and validates in 2017–2019; C trains in 2001–2019 and validates in 2020–2022. This compares model-selection procedures under a common future evaluation, not two unmatched raw CV averages.

| Block | Days | Training pairs / IDs | Validation pairs / IDs / origins | Unsupported pairs |
| --- | --- | --- | --- | --- |
| A | 7 | 170,978 / 234 | 41,761 / 50 / 36 | 0 |
| A | 30 | 151,045 / 204 | 35,035 / 40 / 35 | 0 |
| B | 7 | 209,934 / 280 | 48,189 / 64 / 37 | 0 |
| B | 30 | 183,256 / 240 | 44,700 / 60 / 37 | 0 |
| C | 7 | 265,393 / 338 | 33,971 / 45 / 36 | 0 |
| C | 30 | 235,177 / 294 | 30,128 / 42 / 35 | 0 |

All eligible outer cases, and all held-out inner cases for both policies, had B2 row support. No score improvement comes from dropping unsupported cases. Full source-key role membership, training counts, support, and [year/season composition](../results/deliverables/temporal_validation_s4_e2/validation_calendar_composition.csv) are retained. Pre-2001 exclusions remain 347/116 pairs and 2/1 IDs at 7/30 days; source data are preserved.

## Primary matched policy comparison

Arrows below mean **G → T**. Lower Brier is better; H90 is observed endpoint inclusion, distinct from the nominal 90% probability mass.

| Block | Days | Brier, G → T | Mean K90, G → T | Actual H90, G → T |
| --- | --- | --- | --- | --- |
| A | 7 | 0.969685 → 0.973466 | 25.500 → 25.639 | 81.645% → 81.071% |
| A | 30 | 0.996119 → 0.996606 | 123.800 → 123.171 | 71.304% → 69.537% |
| B | 7 | 0.972388 → 0.972152 | 26.595 → 27.459 | 80.080% → 80.845% |
| B | 30 | 0.997366 → 0.998000 | 100.162 → 129.622 | 71.711% → 73.871% |
| C | 7 | 0.964716 → 0.963748 | 27.139 → 27.611 | 89.742% → 89.856% |
| C | 30 | 0.995838 → 0.995838 | 106.000 → 106.000 | 74.795% → 74.795% |

- A, 7 days: T raises Brier by 0.003781 and lowers hits by 0.574 percentage points; its adjusted Brier interval is [0.001838, 0.005482]. This is adverse rather than evidence that chronological selection is always superior.
- A, 30 days: T raises Brier by 0.000487, lowers hits by 1.767 points, and reduces K90 by 0.629 cells. The adjusted Brier lower bound is only about 0.000000155; this borderline tail should not dominate the conclusion.
- B, 7 days: T lowers Brier by 0.000236 and raises hits by 0.765 points, with 0.865 additional cells. Conditional Brier and hit intervals cross zero.
- B, 30 days: T raises Brier by 0.000634 and hits by 2.161 points, while K90 expands by 29.459 cells (+29.41%). The increased coverage comes with a material expansion.
- C, 7 days: T lowers Brier by 0.000968 and raises hits by 0.114 points, with 0.472 additional cells (+1.74%). The adjusted Brier interval is [-0.001722, -0.000196], but hits are not resolved and the strict no-expansion condition is not met.
- C, 30 days: forecasts and scores are identical because the two selection procedures choose the same model and parameters. This is agreement for one assessed case, not a general equivalence result.

The fitted 90% regions retain at least 90% mass; mean mass across all evaluated family/policy/block/horizon combinations ranges from 90.085% to 91.178%. Actual hits can be substantially below 90%, especially at 30 days, so none of these results certifies full calibration.

## What the two procedures selected

| Block | Policy | Days | Family | a | gamma |
| --- | --- | --- | --- | --- | --- |
| A | G | 7 | LocalEndpointAdaptive | 0.60 | 0.5 |
| A | G | 30 | Fixed | 0.90 | 0 |
| A | T | 7 | LocalEndpoint | 0.65 | 0 |
| A | T | 30 | Adaptive | 0.90 | 0 |
| B | G | 7 | LocalEndpointAdaptive | 0.60 | 2 |
| B | G | 30 | LocalEndpointAdaptive | 0.85 | 2 |
| B | T | 7 | LocalEndpointAdaptive | 0.75 | 2 |
| B | T | 30 | Adaptive | 0.90 | 0 |
| C | G | 7 | LocalEndpoint | 0.60 | 0 |
| C | G | 30 | LocalEndpointAdaptive | 0.85 | 2 |
| C | T | 7 | LocalEndpoint | 0.65 | 0 |
| C | T | 30 | LocalEndpointAdaptive | 0.85 | 2 |

At 30 days in B, G selects LocalEndpointAdaptive, whereas T selects global Adaptive; this explains why the outer region changes substantially. In C at 7 days, both select LocalEndpoint, with a=0.60 versus 0.65. In C at 30 days, both select LocalEndpointAdaptive with a=0.85 and gamma=2.

B2 predictions are bitwise identical between G and T in every outer block. Any policy-dependent change in the primary forecasts therefore comes from selection, not a changed B2 definition. Inner selection scores are intentionally not compared as if they had common cases: G and T use different internal fitting sizes and held-out calendar mixtures. For example, C's 7-day G held-out roster contains 338 IDs, while T contains 104. This is a limitation on causal attribution to calendar order alone.

## All five established families on the most recent block

These are descriptive outer results after each family's parameters were selected internally. A family with a slightly better realised outer score is not substituted for the preselected winner.

| Days | Policy | Family | Brier | Mean K90 | Actual H90 |
| --- | --- | --- | --- | --- | --- |
| 7 | G | Adaptive | 0.970094 | 36.139 | 88.843% |
| 7 | G | B2 | 0.995653 | 18.167 | 75.015% |
| 7 | G | Fixed | 0.971790 | 42.361 | 89.904% |
| 7 | G | LocalEndpoint | 0.964716 | 27.139 | 89.742% |
| 7 | G | LocalEndpointAdaptive | 0.964716 | 27.139 | 89.742% |
| 7 | T | Adaptive | 0.970094 | 36.139 | 88.843% |
| 7 | T | B2 | 0.995653 | 18.167 | 75.015% |
| 7 | T | Fixed | 0.971059 | 44.861 | 90.211% |
| 7 | T | LocalEndpoint | 0.963748 | 27.611 | 89.856% |
| 7 | T | LocalEndpointAdaptive | 0.963748 | 27.611 | 89.856% |
| 30 | G | Adaptive | 0.996642 | 130.143 | 76.545% |
| 30 | G | B2 | 1.010730 | 61.029 | 49.422% |
| 30 | G | Fixed | 0.995790 | 134.057 | 77.458% |
| 30 | G | LocalEndpoint | 0.995798 | 105.543 | 74.521% |
| 30 | G | LocalEndpointAdaptive | 0.995838 | 106.000 | 74.795% |
| 30 | T | Adaptive | 0.996730 | 133.543 | 77.433% |
| 30 | T | B2 | 1.010730 | 61.029 | 49.422% |
| 30 | T | Fixed | 0.996014 | 135.371 | 78.121% |
| 30 | T | LocalEndpoint | 0.995798 | 105.543 | 74.521% |
| 30 | T | LocalEndpointAdaptive | 0.995838 | 106.000 | 74.795% |

Relative to B2, borrowing families generally recover more endpoint support and improve Brier/hits while issuing larger regions. These trade-offs remain visible after chronological outer validation. They are not evidence that adding borrowing always yields the strict three-metric improvement criterion.

## Conditional uncertainty and decision limits

There are 10,000 shared whole-ID Exp(1) multiplier draws, PCG64 seed 20261103. Each ID keeps the same multiplier across origins, horizons and periods; weights are renormalised within origin, followed by equal-origin averaging. Fits and selected parameters are held fixed. Both ordinary 95% and the prespecified 18-screen adjusted intervals are reported.

The approved equivalence margins are Brier ±0.001, H90 ±1 percentage point, and K90 ±5% relative to G. Only C/30 meets all margins with adjusted intervals. The required all-six-comparison equivalence claim fails. No T-versus-G contrast meets strict point or supported quality-preserving superiority.

K90 intervals collapse to the point difference under this conditional design: each fitted annual model issues one region per origin/horizon, and equal-origin averaging makes the mean K90 independent of the within-origin ID multipliers. This is expected arithmetic, **not** proof that training or model-selection uncertainty in region size is zero. Refitting and selection uncertainty, shared ocean forcing and repeated project exposure are not fully represented. All periods remain development evidence.

These results do not identify a physical change point, prove stationary or nonstationary transition probabilities, or establish that data before a particular year are useless. They show that the chosen validation policy can change a practical model decision, with period-dependent gains and losses.

## Existing S4 E1 context: extending history helps some metrics

This is a descriptive comparison of already available runs, not another fit or prespecified primary contrast. The audit verified identical 64,099 validation source keys, endpoint labels and scoring weights in S4 E1 and block C. Both comparisons below use annual B2; the earlier fit began in 2012, while the current fit begins in 2001.

| Days | Brier, 2012-start → 2001-start | H90, 2012-start → 2001-start | K90, 2012-start → 2001-start |
| --- | --- | --- | --- |
| 7 | 0.996224 → 0.995653 | 72.597% → 75.015% | 16.306 → 18.167 |
| 30 | 1.017031 → 1.010730 | 38.810% → 49.422% | 42.829 → 61.029 |

The additional history is associated with improved Brier and hits, alongside larger regions. In this tested setting, dismissing all older permitted observations as obsolete is not supported. This does not isolate physical drift from sample support and does not choose an optimal history window. The sharp c=1 seasonal deterioration cannot be attributed to chronological validation alone from these comparisons.

## Engineering audit and resource record

Seven new semantic tests and fourteen existing-model regression tests passed. Independent counters and direct squared errors reconstructed all 24 role definitions, all 148 candidate variants per inner role, selections, outer probabilities, regions, scores and decision arithmetic. Maximum score discrepancy was 6.66e-16; the independent multiplier calculation differed by at most 8.53e-14. Changed code/config/environment, altered replay scores/IDs/vectors/figures and incomplete parent receipts are rejected by the fault checks.

The initial pilot was stopped after 197.22 seconds when profiling located redundant per-case region recounting in the audit. Its files and source fingerprint were preserved, and its time is charged. Region and destination-score checks were then reused per identical forecast; all cases still receive arithmetic verification. The 97 frozen scientific artifacts produced before scoring are byte-identical before and after this audit-only optimization. A new code fingerprint and full-roster pilot were required before primary execution.

| Stage | Measured seconds before sealing | Conservative budget charge |
| --- | --- | --- |
| Stopped first pilot | 197.22 | 197.22 |
| pilot | 73.80 | 84.00 |
| primary | 53.75 | 64.00 |
| replay | 60.00 | 70.00 |

Cumulative charged time is 415.22 seconds (6 min 55 sec), below the 65-minute total cap. Both pilot attempts together charge 281.22 seconds, below their cumulative 5-minute cap. Peak RSS across all attempts was approximately 3.13 GiB, below 8 GiB. Storage remains below 5 GiB. One process and one numerical thread were used for each run; no raw canonical trajectory or final-test label was opened.

Fresh replay matches 115 scientific files numerically within 1e-12, with all ten PNGs byte-identical. All 754 sealed files across the three completed runs were checksum-verified, along with the pre-score forecast freezes and current source identity. All ten primary figures were visually inspected and all eleven local HTML references resolve. Local HTML was not browser-rendered because the existing browser security policy blocks file URLs; the PNGs were inspected directly.

## Review recommendation

Retain forward, whole-ID-isolated outer validation as the main evidence for predicting subsequent periods, because that matches the deployment question. Keep calendar-mixed whole-ID CV as a diagnostic or training-internal comparator; the observed results do not establish its interchangeability with forward selection. Forward internal selection should not be advertised as a universally more accurate algorithm.

Do not select a new year cutoff, substitute the best realised outer family, or launch another feature round from this result automatically. The next user decision concerns the validation standard to retain. There is no additional model development or physical-stationarity conclusion in this experiment.
