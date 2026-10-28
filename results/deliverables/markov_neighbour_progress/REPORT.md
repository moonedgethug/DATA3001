# Neighbour Markov experiment: provisional first-fold result

**This is one completed outer fold out of five, not the final experiment result.** The user stopped the remaining computation on 2026-10-28 to move to continuous-state modelling; no complete five-fold result exists. Do not select, stop or change a model using this progress view. The final test is locked. These are adaptively inspected development results.

## Findings supported by this fold

At 7 days, the expanded neighbour search selected alpha=0 and exactly the same path and lambda as the independently tuned no-neighbour control. The issued predictions are identical. This fold provides no realised improvement from neighbour borrowing; it does not prove that neighbouring cells carry no information.

At 30 days, the selected neighbour procedure has a slightly worse held-ID S, slightly lower nominal-90% hit rate, and a slightly larger mean prediction region than the independently tuned self-cell control. The matched-path/lambda control is also retained to separate spatial borrowing from lambda retuning. This fold does not support declaring an improvement. It does not establish a general failure before the full CV and uncertainty analysis finish.

## Held-ID metrics

| horizon_days | model | eligible_pairs | independent_ids | S_integration | hit90_pct | region90_cells | available90_pct | U_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | self-CV | 53469 | 72 | 0.91583823 | 85.232565 | 17.36838 | 99.888721 | 0.098538405 |
| 7 | neighbour-CV | 53469 | 72 | 0.91583823 | 85.232565 | 17.36838 | 99.888721 | 0.098538405 |
| 7 | self-at-neighbour | 53469 | 72 | 0.91583823 | 85.232565 | 17.36838 | 99.888721 | 0.098538405 |
| 30 | self-CV | 47589 | 62 | 0.98386028 | 68.157557 | 68.661656 | 99.599697 | 0.27413274 |
| 30 | neighbour-CV | 47589 | 62 | 0.98424031 | 67.965286 | 69.385921 | 99.384312 | 0.35106918 |
| 30 | self-at-neighbour | 47589 | 62 | 0.98373268 | 68.439135 | 68.875914 | 99.566076 | 0.27378799 |

Lower S is better. S is the unchanged augmented-state Brier score, not percentage accuracy. Hit90 is the observed outcome's inclusion rate across all eligible cases; it is not the probability of an arbitrary future forecast being correct. Mean region size is conditional on region availability and counts 1-degree cells, not square kilometres. Larger regions can improve coverage without sharpening predictions. U is unresolved transport mass, not an observed grounding outcome. A finite-particle zero is not proof of a structural zero.

Hourly origins from one drifter are correlated: the independent ID counts are shown, and two simulation repeats do not double the number of observations. All metrics use the same cases for the three procedures within each horizon.

On the common subset where both procedures produce a nominal-90% region, the 30-day mean sizes are 68.7100 self-cell versus 69.3970 neighbour cells. The broader-region direction therefore also holds under this matched-availability diagnostic. This remains a single-fold observation.

## Inner-selected settings

| days | procedure | path | alpha | lambda | numerically_unresolved |
| --- | --- | --- | --- | --- | --- |
| 7 | neighbour | R3 | 0 | 0.2 | True |
| 7 | self | R3 | 0 | 0.2 | True |
| 30 | neighbour | R7 | 0.1 | 0.3 | True |
| 30 | self | R7 | 0 | 0.4 | True |

R3 means 1+3+3 days; R7 means 2+7+7+7+7 days. Alpha is the neighbour displacement borrowing weight; lambda is the velocity-category pooling weight. These are fold-specific selections with unresolved numerical near-ties, not unique or universal optimal parameters. Seven-day and thirty-day searches were independent and did not reuse historical winning settings.

## Probability maps

Each release-cell view averages the saved forecasts across that cell's held-out exact positions and initial velocity categories. The observed map uses exactly those same hourly origins. It is a cohort-average illustration, not a forecast from one newly specified point. The default cell is the largest held-out release cohort by count, chosen without looking at model skill; all cells are available. All panels share a fixed logarithmic colour scale for probability per 1-degree cell. E and U remain in the denominator and are listed separately. No mass is renormalised to create a more favourable image. Map probabilities are not continuous density or 90% prediction regions. A cell without an observed endpoint in this finite cohort is not proven impossible.

## Audit boundary

All completed-fold files match their checkpoint hashes. All 115 bound source/input/configuration hashes match. Complete fitting and held-ID rosters are disjoint. S, E/U mass, sampled-zero counts, nominal-90% availability, hits and region size were independently recomputed from the saved 128-particle arrays for each repeat and model alias. Cohort probability mass sums to one before display rounding. No fitting, parameter changes, new predictors or trajectory edits were performed for this report. No final-test trajectory was read. The full five-fold independent audit was not performed because the experiment was stopped before completion.

Source run: `markov_neighbour_cv_20261028T105824_991491Z`; source checkpoint: `outer_0`. Display source files and their hashes are recorded in `snapshot_audit.json`.
