# Step 4 E4 | Predictive value of departure heading

**5 November 2026, Australia/Sydney.** The 7-day directional adjustment passed the predeclared paired Brier test on the 2020–2022 development backtest. Hits increased and the mean 90% region shrank slightly. At 30 days, all three point estimates improved, but the Brier test was inconclusive. The evidence supports considering heading when available for 7-day forecasts. It gives insufficient grounds for replacing annual B2 at 30 days. [Approved plan](departure_direction_s4_e4_plan.md) · [Visual review](../results/deliverables/departure_direction_s4_e4/review.html) · [Independent audit](../provenance/reviews/departure_direction_s4_e4_audit.json)

## Fitting and selection

The 2001–2019 outer fit contains 265,393 qualified 7-day pairs (338 drifters) and 235,177 30-day pairs (294 drifters). The two inner forward windows held out 2014–2016 and 2017–2019. Both temporal boundaries purge crossing labels and exclude the union of held-out drifters at both horizons. Each distinct eligible origin key contributes once to the fitting role's speed threshold. The thresholds were 0.142474, 0.144028 and 0.140774 m/s for inner 1, inner 2 and outer training, respectively. The outer threshold used 265,328 strictly positive valid speeds. The archived position pair ending at departure supplies the heading. Two identical coordinates yield zero speed, including when the inverse geodesic routine produces a negligible floating-point residual.

| Days | Selected λ | Inner annual Brier | Inner selected Brier |
|---|---:|---:|---:|
| 7 | 1.000 | 1.000816 | 0.998956 |
| 30 | 1.000 | 1.034909 | 1.034276 |

Both estimates reached the upper boundary of the approved interval. This applies the full *bounded* heading adjustment. Aligned versus opposite donors still have at most a 3:1 vote ratio. Unusable donors retain one vote, and every annual-positive destination remains possible. Unknown query headings return annual B2. The 0.01 grid and the analytic inner solution agree. [Training choices](../results/deliverables/departure_direction_s4_e4/choices.csv) · [Thresholds](../results/deliverables/departure_direction_s4_e4/thresholds.csv)

## Matched outer results

The full roster includes 33,971 pairs / 45 drifters / 36 origins at 7 days and 30,128 pairs / 42 drifters / 35 origins at 30 days. Every case had annual support. Scores average times within each ID/origin, then IDs within origin, then origins equally. Both models use the same complete stopped-destination outcomes, including exit.

| Days | Forecast | Brier | Actual H90 | Mean geographic K90 |
|---|---|---:|---:|---:|
| 7 | Annual B2 | 0.995653 | 75.015% | 18.167 |
| 7 | Heading B2 | 0.992948 | 76.478% | 18.057 |
| 30 | Annual B2 | 1.010730 | 49.422% | 61.029 |
| 30 | Heading B2 | 1.010227 | 49.903% | 60.294 |

| Days | Δ Brier [ordinary conditional 95% interval] | Adjusted one-sided upper bound | Δ hits, pp [descriptive 95%] | Δ cells [descriptive 95%] |
|---|---:|---:|---:|---:|
| 7 | −0.002705 [−0.003677, −0.001677] | −0.001733 | +1.463 [+0.497, +2.495] | −0.110 [−0.149, −0.072] |
| 30 | −0.000504 [−0.001035, +0.000047] | +0.000027 | +0.481 [−0.788, +1.822] | −0.734 [−0.861, −0.619] |

The primary criterion requires a negative corrected upper bound. Only 7 days passes. Both horizons meet the separate three-metric point screen. The 30-day direction forecast still hits fewer than half the actual endpoints. Its smaller regions alone would be insufficient evidence of better probabilities. The annual-positive support is conserved. True endpoints assigned zero probability therefore have the same evaluation weight as under annual B2, 5.69% and 26.86% at 7 and 30 days. [Paired test](../results/deliverables/departure_direction_s4_e4/primary_test.csv) · [Complete metrics](../results/deliverables/departure_direction_s4_e4/summary.csv)

## Fallback exposure

| Days | Fallback / eligible pairs | Pair share | Original evaluation weight | Causes | Distinct fallback IDs / origins |
|---|---:|---:|---:|---|---:|
| 7 | 4,593 / 33,971 | 13.52% | 8.45% | 4,582 low speed, 9 first rows, 2 gaps | 41 / 29 |
| 30 | 3,320 / 30,128 | 11.02% | 5.50% | 3,310 low speed, 8 first rows, 2 gaps | 38 / 28 |

All these cases remained in primary scoring, with identical annual and adjusted probabilities, regions and scores. No additional outer case reverted because the origin had zero usable training donors. The remaining 91.55% / 94.50% of target weight received the directional forecast. The different case and weight percentages follow from the equal-ID/equal-origin evaluation. [Fallback reasons](../results/deliverables/departure_direction_s4_e4/fallback.csv)

## Verification and interpretation

The complete pilot used synthetic outer targets. All three stages produced the same 438 pre-score artifact hashes. Annual B2 reproduced the E2/E3 references. Direct donor votes on representative rows and independently reconstructed outer probabilities agreed with the production calculation, with maximum difference 1.11×10⁻¹⁶ for the latter check. A separate reconstruction reproduced the source-keyed scores, evaluation hierarchy, eligibility, thresholds and selected weights. The fresh replay matched 453 scientific artifacts and all four figures were byte-identical. Resource charges were 29 s for the pilot, 28 s for primary and 29 s for replay, within the cumulative 3,000 s cap. Peak RSS was 1.33 GiB or less. The locked final-test pool was not opened.

Inference uses 10,000 shared Exp(1) whole-drifter multipliers, conditional on the fitted forecasts, with two-horizon multiplicity correction. This historical comparison has prior development-period exposure. Shared ocean conditions, refitting variation and the possibility that heading reflects finer within-cell location limit interpretation. Effective input is the historical last-hour motion estimate. A release with location alone receives annual B2.
