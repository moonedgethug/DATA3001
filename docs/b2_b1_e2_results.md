# Step 2 E2: B1 allocation and support-weight comparison

**Status: implemented, independently audited and replayed; submitted for user review on 30 October 2026. S2 scientific closure is pending.**

Neither Info nor Weight achieved the approved joint objective: smaller nominal-90% regions with no deterioration in Brier or actual hits relative to Fixed. Both procedures reproduce Fixed at 7 days. At 30 days their regions shrink by less than 1%, with slightly lower Brier point estimates but also slightly lower hit rates. These are unsuccessful joint comparisons, not evidence that every form of regularisation must fail.

## Definition and evidence

The [approved E2 specification](b2_b1_e2_plan.md) fixes cleaned v7 data, annual pooling, 1-degree cells, direct 7/30-day stopped targets, equal eligible hourly-pair weights and the original whole-ID folds. All five models use the same B2-supported evaluation cases. B1 uses only eligible R-origin fitting pairs. No neighbouring cells, new predictors, tail clipping or lower probability-region level are introduced.

- **Fixed:** B2/B1 blend with a constant weight selected by inner Brier.
- **Info:** reallocates B1's D-state probability between destinations previously seen and unseen from the origin cell, preserving B1's exit probability. Its constant blend weight and allocation multiplier are selected jointly.
- **Weight:** leaves B1 unchanged and selects a blend scale plus the strength of its dependence on fitting pair count.
- **B2 and E1Adaptive:** independently reconstructed reference controls, outside the primary success comparison.

Each arm has the approved 105-candidate grid. Inner selection requires Brier and hits no worse than the inner Fixed anchor, then minimises the 90% region's cell count. Without a strictly smaller qualifying region, the arm falls back to Fixed. Five outer whole-ID folds evaluate this selection procedure; inner constraints do not guarantee outer non-deterioration.

The region retains the descending-probability prefix reaching 0.90 and all cutoff ties. All probabilities remain in the forecast, including those outside the displayed region. Exit E counts toward probability mass but is not a geographic cell. The reported cell count is an eligible-pair-weighted mean, not a single map's integer size or a physical area in square kilometres.

## Primary held-out results

| Days | Model | Standard Brier | Mean 90% cells | Actual hits |
|---|---|---:|---:|---:|
| 7 | Fixed | 0.928607423 | 25.6438 | 93.2912% |
| 7 | Info | 0.928607423 | 25.6438 | 93.2912% |
| 7 | Weight | 0.928607423 | 25.6438 | 93.2912% |
| 30 | Fixed | 0.988818546 | 126.4060 | 86.4285% |
| 30 | Info | 0.988796542 | 125.8267 | 86.4241% |
| 30 | Weight | 0.988746663 | 125.2130 | 86.3140% |

There are 303,288 evaluable hourly pairs from 385 IDs at 7 days and 268,998 pairs from 337 IDs at 30 days. No held-out pair has an unsupported origin in this run. Overlapping hourly windows are not independent instruments. There are no observed or predicted exits, so exit calibration is untested. Nominal 90% probability is not 90% actual coverage: the 30-day hit rate remains below 90% for every model.

| Days | Arm minus Fixed | Brier change | Cell change | Relative cell change | Hit change, percentage points | Joint outcome |
|---|---|---:|---:|---:|---:|---|
| 7 | Info | 0 | 0 | 0% | 0 | No change |
| 7 | Weight | 0 | 0 | 0% | 0 | No change |
| 30 | Info | -0.000022004 | -0.5793 | -0.4583% | -0.004461 | Does not pass |
| 30 | Weight | -0.000071883 | -1.1930 | -0.9438% | -0.114499 | Does not pass |

The 30-day hit differences correspond to 12 fewer hourly-pair hits for Info and 308 fewer for Weight. These are not counts of independent drifters. The approved quality margins are zero; neither point comparison passes. Their positive-probability cell counts also remain identical to Fixed: 123.6515 at 7 days and 291.4709 at 30 days. The small K90 reductions do not come from removing tail support.

## Uncertainty and selection

The 5,000 paired whole-development-ID resamples condition on saved outer fits. Every replicate is defined. Ordinary 95% intervals for the 30-day differences are:

| Arm | Brier difference interval | Cell-count difference interval | Hit difference interval, percentage points |
|---|---|---|---|
| Info | [-0.000117571, +0.000080661] | [-0.8015, -0.3773] | [-0.1039, +0.0874] |
| Weight | [-0.000270899, +0.000125537] | [-1.6067, -0.7906] | [-0.3127, +0.0888] |

Both Brier and hit intervals cross zero. A point decline in hits is not proof of population-level deterioration; equally, a small decline or a non-significant difference does not establish non-deterioration. The predeclared adjusted directional bounds for all 12 comparisons also fail the joint quality screen. See [paired differences](../results/deliverables/b2_b1_e2/paired_differences.csv). These conditional intervals omit model refitting, shared-training dependence across folds and the uncertainty from earlier experiments guiding E2. They are development evidence, not final-test validation.

At 7 days, Info and Weight fall back in all five outer folds. At 30 days, Info falls back in four folds; fold 3 selects a=0.75, c=0.75. Weight falls back in folds 2 and 4; folds 0, 1 and 3 select (a, beta)=(0.70, 0.50), (0.70, 0.25) and (0.65, 1.00). This limited and variable selection explains why aggregate changes are small. The outer data were not used to retune these choices.

The separate all-development candidate fit selects neutral fallback for both 7-day arms and 30-day Info. The 30-day Weight candidate selects a=0.60, beta=0.25. Its map is descriptive; it is not the model independently evaluated on all development IDs. In particular, the all-development Info map matches Fixed despite a small nonzero outer comparison.

## What this says about the mechanism

The implementation verifies the intended support direction: for beta > 0 and 0 < a < 1, borrowing decreases as fitting pair count increases. No arithmetic reversal of the weight rule was found. Pair counts still measure overlapping windows, not independent information or prediction reliability.

At 30 days, Fixed assigns 22.0759% probability to destinations unseen from the local fitting cell; their observed frequency is 17.4589%. Info changes the probability to 21.9251%; Weight changes it to 22.0901%. This aggregate diagnostic is consistent with excess mass in this category, but cannot identify which destinations deserve less probability or establish that B1 alone causes the shortfall. It also does not imply that deleting rare endpoints improves prediction.

Support strata reveal trade-offs hidden by the overall mean. At 30 days, Weight enlarges regions in the below-median pair-count stratum (135.49 to 137.16 cells) while slightly improving hits there; its overall reduction comes from the higher-support stratum, whose hits decline. Info's lower-support region size barely changes. These are descriptive diagnostics of the approved experiment, not new tuning criteria.

The secondary controls also retain the earlier trade-off: at 30 days B2 uses 62.61 cells but hits only 66.37%; E1Adaptive uses 122.19 cells with 85.84% hits. Neither substitutes for the Fixed quality requirement. E2 provides no basis to promote Info or Weight over Fixed or to attribute the problem exclusively to allocation or weighting.

## Reproducibility and artifacts

- Preflight: `b2_b1_e2_preflight_20261030T060603_930585Z`; 2.75 seconds, within the five-minute cap.
- Primary: `b2_b1_e2_20261030T060621_291294Z`; 159.51 seconds.
- Fresh replay: `b2_b1_e2_20261030T060917_279086Z`; 162.52 seconds; all 131 numerical tables reproduced within the declared 1e-12 tolerance.
- 56 targeted tests passed across E2, E1, S1, prediction regions and architecture/layout. The independent audit checked 26 fitting roles and all 12,600 candidate-score rows, separately reconstructed selected distributions, and verified Brier, regions, budget ties, bootstrap draws and outcome decisions.
- Outer predictions were hashed before all-development tuning and remained unchanged. Frozen S1/E1 artifacts and the three comparator outputs passed regression checks. Raw canonical trajectory reads and final-test trajectory reads were both zero.
- Six figures were visually inspected for readable labels, clipping, consistent probability scales and correct candidate-versus-held-out captions. No result artifact was edited after sealing.

Read the [sealed report](../results/deliverables/b2_b1_e2/REPORT.md), [visual review](../results/deliverables/b2_b1_e2/review.html), [verification receipt](../provenance/runs/b2_b1_e2_20261030T060621_291294Z/verification.json), [replay receipt](../provenance/runs/b2_b1_e2_20261030T060917_279086Z/verification.json) and [post-run audit](../provenance/reviews/b2_b1_e2_20261030T060621_291294Z_audit.json). Configuration and code are indexed in the [code guide](code_guide.md).

![Held-out differences and conditional uncertainty](../results/deliverables/b2_b1_e2/quality_and_region_differences.png)

The [7-day](../results/deliverables/b2_b1_e2/candidate_comparison_7d.png) and [30-day](../results/deliverables/b2_b1_e2/candidate_comparison_30d.png) candidate maps use the same training-support-selected origin cell 44744 and a shared colour scale within each horizon. They illustrate fitted distributions without replacing held-out evaluation.

**Review recommendation:** retain Fixed as the quality reference. Record E2 as an audited experiment that did not achieve its joint objective. Any further hypothesis, relaxed margin, combined arm or stage transition requires a new discussion; no additional search was run.
