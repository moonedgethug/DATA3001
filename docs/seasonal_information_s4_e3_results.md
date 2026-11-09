# Step 4 E3 | Does departure season improve forecasts?

Engineering complete. Development backtest dated 5 November 2026 (Australia/Sydney). [Approved study](seasonal_information_s4_e3_plan.md) · [Approval receipt](../provenance/reviews/seasonal_information_s4_e3_approval.json) · [Visual review](../results/deliverables/seasonal_information_s4_e3/review.html) · [Audit record](../provenance/reviews/seasonal_information_s4_e3_audit.json)

## Paired predictive test

Fit annual and seasonal B2 distributions to 2001–2019 qualified raw pairs. A separate seasonal weight per horizon was chosen using two training-internal forward windows. All comparisons use the same available 2020–2022 departures, with crossing training labels purged and disjoint drifter IDs. Every forecast, geographic region, sampling placement and case weight was frozen before scoring. The reference is annual B2. Negative adjusted-minus-annual Brier differences favor the seasonal adjustment.

The 7-day point estimate favors a small seasonal correction on all three operational metrics. The adjusted one-sided Brier upper bound is positive, so the primary test does not establish a predictive benefit. At 30 days the point Brier increases and the actual hit rate falls. Neither horizon passes the approved seasonal-benefit test. Annual B2 remains the working reference for this seasonal comparison. The small 7-day point benefit remains uncertain.

| Days | Training-selected c | Δ Brier | Conditional 95% interval | Adjusted one-sided upper | Brier benefit supported | Point quality gain |
| --- | --- | --- | --- | --- | --- | --- |
| 7 | 0.098574 | -0.0004646 | [-0.0012836, +0.0003378] | +0.0003544 | No | Yes |
| 30 | 0.114911 | +0.0000338 | [-0.0004374, +0.0004845] | +0.0005050 | No | No |

The two tests use the predeclared one-sided centered multiplier upper bound, with 10,000 shared whole-ID Exp(1) draws and per-horizon alpha 0.025. Each ID keeps one multiplier across all its origins and both horizons. The intervals condition on fitted forecasts and weights. Dependence between different drifters exposed to common ocean events, selection/refitting variation and prior exposure to the validation period limit generalization.

## Outer forecasts on identical cases

| Days | Forecast | Brier | Actual H90 | Mean K90 | Issued mass | Truth probability zero |
| --- | --- | --- | --- | --- | --- | --- |
| 7 | Annual | 0.995653 | 75.015% | 18.167 | 90.998% | 5.690% |
| 7 | HardSeason | 1.025687 | 61.413% | 14.190 | 91.547% | 16.186% |
| 7 | Adjusted | 0.995189 | 75.808% | 18.069 | 90.909% | 5.690% |
| 30 | Annual | 1.010730 | 49.422% | 61.029 | 90.731% | 26.856% |
| 30 | HardSeason | 1.057511 | 25.086% | 29.407 | 91.348% | 62.699% |
| 30 | Adjusted | 1.010764 | 47.781% | 60.335 | 90.530% | 26.856% |

| Days | Δ hit rate (pp), descriptive 95% interval | Δ region cells, descriptive 95% interval |
| --- | --- | --- |
| 7 | +0.793 [-0.175, +1.762] | -0.098 [-0.149, -0.049] |
| 30 | -1.641 [-3.662, -0.197] | -0.693 [-0.828, -0.563] |

Each 90% region retains tied endpoint probabilities at its boundary. Exit can be a hit but is not counted as a geographic cell. Metrics average departure times within ID/origin, IDs within origin, then origins equally. K90, H90 and their interval screens are descriptive.

- 7 days: 33,971 pairs, 45 drifters and 36 origins scored. 0 unsupported pairs. Seasonal fallback applies to 41 pairs (2.78% target weight). Full seasonal conditioning removes annual-positive probability at the observed truth for 10.50% of target weight.
- 30 days: 30,128 pairs, 42 drifters and 35 origins scored. 0 unsupported pairs. Seasonal fallback applies to 0 pairs (0.00% target weight). Full seasonal conditioning removes annual-positive probability at the observed truth for 35.84% of target weight.

## What the equal-sample comparison measures

For each of the 292 nonempty fitted seasonal tables, 200 endpoint-blind draws match the number of distinct IDs, annual contributor quotas, pair counts and within-year hour patterns. Mean matched Brier is the mean of separately scored forecasts. A positive sampling cost means the reduced-size annual table performs worse than full annual B2. Positive seasonal recovery means true-season pairs outperform equally supported records drawn without restricting departure season. Difference of cost and recovery equals the net hard-season penalty.

| Days | Roster | Target weight | Other-season pair share | Sampling cost [95%] | Season recovery [95%] | Net cost |
| --- | --- | --- | --- | --- | --- | --- |
| 7 | all | 100.0% | 22.0% | +0.036418 [+0.026274, +0.045666] | +0.006384 [+0.001688, +0.011106] | +0.030034 |
| 7 | nonempty | 97.2% | 22.6% | +0.037458 [+0.027024, +0.046971] | +0.006566 [+0.001736, +0.011423] | +0.030892 |
| 7 | informative | 39.6% | 34.0% | +0.019948 [+0.014687, +0.024857] | +0.006565 [-0.003400, +0.016064] | +0.013383 |
| 30 | all | 100.0% | 22.0% | +0.048049 [+0.042443, +0.053397] | +0.001268 [+0.000054, +0.002478] | +0.046781 |
| 30 | nonempty | 100.0% | 22.0% | +0.048049 [+0.042443, +0.053397] | +0.001268 [+0.000054, +0.002478] | +0.046781 |
| 30 | informative | 38.2% | 33.8% | +0.026913 [+0.017574, +0.035452] | +0.003831 [+0.001424, +0.006231] | +0.023082 |

- 7 days: Monte Carlo SE 0.000136 for cost and 0.000136 for recovery. Diagnostic cost sign resolved: True. Recovery sign resolved: True. Rows with ≥25% mean other-season share cover 39.58% of evaluation weight. The prespecified 80% population interpretation gate is not met.
- 30 days: Monte Carlo SE 0.000087 for cost and 0.000087 for recovery. Diagnostic cost sign resolved: True. Recovery sign resolved: True. Rows with ≥25% mean other-season share cover 38.22% of evaluation weight. The prespecified 80% population interpretation gate is not met.

The informative-subset estimates use original target weights renormalized to that subset. When the 80% gate fails, the all-case arithmetic still describes these matched draws, while a season-specific explanation is limited to the informative subset. Mixed draws can retain true-season pairs. Counts of distinct destinations, zero-truth rates, Monte Carlo errors and subset denominators appear in [matched diagnostics](../results/deliverables/seasonal_information_s4_e3/matched_diagnostic.csv).

The matched design has a clear sampling penalty at both horizons. Its all-case seasonal recovery is smaller than the cost: 0.006384 versus 0.036418 at 7 days and 0.001268 versus 0.048049 at 30 days. However, sufficiently mixed training rows cover only 39.58% and 38.22% of target weight. Within this subset the sampling penalty remains positive at both horizons. The seasonal-recovery interval includes zero at 7 days and is positive at 30 days. This supports sample fragmentation as an explanation of poor hard-season performance within the matched design, with limited scope for a population-wide seasonal attribution. It does not establish a physical absence of seasonal currents.

## Reproduction

| Stage | Run identity | Measured seconds before sealing | Charged seconds | Peak RSS GiB |
| --- | --- | --- | --- | --- |
| pilot | seasonal_information_s4_e3_pilot_20261104T142547_620739Z | 96.74 | 109 | 1.37 |
| primary | seasonal_information_s4_e3_primary_20261104T142729_626118Z | 83.08 | 96 | 1.31 |
| replay | seasonal_information_s4_e3_replay_20261104T142930_611975Z | 84.33 | 97 | 1.44 |

All three pre-score forecast manifests agree, including every sampled placement. Fresh replay compared 628 scientific artifacts with tolerance 10⁻¹² on numerical output and byte identity on the five figures. The reviewer verified 1957 sealed file digests. Annual forecasts, case weights and actual metrics reconcile to the S4 E2 C-block reference. Independent case and matched-score arithmetic, c selection, paired multipliers, the subset weighting and both cost decompositions passed. The final-test pool remained locked.

[Training c curves](../results/deliverables/seasonal_information_s4_e3/inner_curves.csv) · [Paired test and quality trade-offs](../results/deliverables/seasonal_information_s4_e3/primary_test.csv) · [Calendar and support slices](../results/deliverables/seasonal_information_s4_e3/slices.csv)
