# Step 4 E7 | Exact-position empirical transitions within 100 km

Date: 5 November 2026. Contract: [approved v2.1](exact_origin_s4_e7_plan.md).

Status: engineering verification complete; primary artifact audit and fresh source replay both passed. This record is not the protected research-stage ledger.

## Decision

Exact-coordinate neighbour selection improves seven-day Brier and actual nominal-90% coverage on the matched development cases. It also increases region size and wet area. The predeclared primary Brier test passes, but both quality-preservation gates fail. Retain the existing development default pending discussion; do not describe this result as an improvement without a search-area cost.

## Fixed method and population

For each recorded departure longitude/latitude, select historical departure pairs by exact WGS84 distance, with a fixed **100,000-metre cap**. Select one k from **500, 2,000, 8,000** using only the two training-period validation windows. All selected pairs receive equal votes. Retain original endpoints and the established absorbing first-exit state; do not translate trajectories or endpoints. The new predictor has no cell-membership restriction on donors and no B1/B2 mixture, Gaussian, distance weight or position-error envelope.

The chosen k is **8,000**. Both internal windows separately favor this candidate, and its pooled inner Brier is **0.9613728125**. This is the best of the three approved candidates, not proof of a globally optimal k. No search expansion followed inspection of outer results.

The canonical cleaned v7 release, 2001–2019 fit / 2020–2022 development split, whole-ID exclusions, boundary-label purges and qualification remain fixed. Outer fitting uses **265,393 pairs / 338 IDs**; scoring retains **33,971 pairs / 45 IDs / 36 original origin cells**. Evaluate equal times within ID/origin, equal IDs within origin, then equal origins. Training votes remain equal per selected pair.

All **120,344** inner and outer query starts have a donor within 100 km. No unsupported query was dropped or replaced by B2. The outer donor count ranges from **5,521 to 8,000**; median 8,000. Cap-limited cases represent **2.10% of raw query pairs**, or **5.16% under the evaluation weights**. Median independent donor support is 72 IDs; minimum 19. Median farthest-donor distance is 53.23 km, with a maximum below 100 km. Long-record donors can still have greater total training influence; the equal-ID rule applies to evaluation, not to donor voting.

The primary comparison uses the original 1° output grid. At 0.5°, both models count the same models' actual historical endpoints into finer cells; B2 is not uniformly spread across four child cells. These are matched comparisons within each resolution. Brier and cell counts should not be compared directly between resolutions as measures of improvement.

## Matched seven-day results

| Output / model | Brier ↓ | Actual H90 ↑ | Mean K90 ↓ | Mean wet area (km²) ↓ |
|---|---:|---:|---:|---:|
| 1° annual B2 | 0.995653 | 75.0145% | 18.1667 | 184,906.98 |
| 1° exact position | **0.953154** | **85.7511%** | 20.4273 | 207,827.57 |
| 0.5° B2 endpoint rebin | 1.007901 | 68.5495% | 56.1389 | 143,739.15 |
| 0.5° exact position | **0.989095** | **79.5531%** | 65.1775 | 166,528.72 |

The 1° Brier reduction is **0.042500 (4.27%)**; H90 improves **10.7366 percentage points**. K90 rises **2.2607 cells (12.44%)**, and wet area rises **22,920.59 km² (12.40%)**.

At 0.5°, Brier decreases **0.018807 (1.87%)** and H90 rises **11.0036 percentage points**. K90 rises **9.0386 cells (16.10%)**, and wet area rises **22,789.57 km² (15.85%)**. All regions still target the same nominal 90% probability. The improved observed hit rates remain below 90%; a nominal region is not a guarantee of empirical coverage.

The evaluation-weighted zero-probability rate at actual outcomes falls from **5.6900% to 0.4665%** at 1°, and from **9.7543% to 2.5350%** at 0.5°. The matched outer cases contain no observed absorbing exits, and both forecasts assign them zero exit mass; these results therefore do not establish exit-prediction skill.

## Paired uncertainty and acceptance

Differences are exact-position minus B2. Intervals use 10,000 shared whole-ID Exp(1) multiplier draws, seed 20261105, with fixed fitted models and the established evaluation hierarchy.

| Output | Delta Brier, conditional 95% interval | Delta H90, percentage points | Delta K90 |
|---|---:|---:|---:|
| 1° primary | −0.042500 [−0.048279, −0.036779] | +10.7366 [+8.0828, +13.8949] | +2.2607 [+1.9043, +2.6161] |
| 0.5° secondary | −0.018807 [−0.020763, −0.016823] | +11.0036 [+8.1050, +13.7097] | +9.0386 [+7.8699, +10.2149] |

The primary centered one-sided 95% upper Brier bound is **−0.037596**, below zero. This passes the predeclared primary test. The secondary interval is diagnostic, not a second primary hypothesis; its `brier_supported` CSV flag is false because only the 1° row is designated primary.

| Contract gate | Result | Reason |
|---|---|---|
| Supported primary Brier benefit | Pass | Lower Brier and negative one-sided upper bound |
| 1° quality preservation | Fail | K90 increases |
| 0.5° quality preservation | Fail | K90 and wet area increase |
| Replace current default | No | Both preservation gates are required |

The outer years were inspected in earlier development. These conditional intervals do not establish independent final-test performance, account for all historical model selection, or include all refitting/common-forcing uncertainty. Canonical final-test data remain locked.

## Interpretation and visual review

This supports the particular **exact-position neighbourhood estimator**, which changes donor selection as well as coordinate representation. It does not isolate a benefit caused solely by storing more precise coordinates. The estimator remains an empirical measure over observed endpoints, displayed as a union of cells; it does not produce a smooth density or novel unobserved endpoints.

Post-hoc descriptive checks, without changing the model or decision, show lower 1° Brier in **31/36 origins**, but lower H90 in **9/36** and larger K90 in **25/36**. At 0.5°, the corresponding counts are 28, 10 and 22. Gains are not uniform across release locations.

The identity `Brier = 1 + sum(p²) − 2p(observed)` helps interpret the primary result: mean squared probability concentration decreases from **0.098473 to 0.073009**, while mean probability on the observed cell increases from **0.051410 to 0.059927**. Both terms contribute to lower Brier. This is a descriptive decomposition, not a separate calibration test.

The [visual report](../results/deliverables/exact_origin_s4_e7/review.html) contains matched metrics, paired intervals, internal selection, origin-level differences and six forecast examples selected before outer endpoints were exposed. It includes different starts within the same old origin cell. Maps retain common scales, exact departure marks, actual seven-day endpoints and nominal-90% region outlines. A single endpoint on a map is not an observed conditional distribution.

## Engineering verification and provenance

The 16 targeted tests pass, including geodesic refinement, caps, ties, multiplicity, empty support, source joins, absorbing exits, nested grids, zero-probability outcomes, scoring and numerical-reduction regressions. The pilot checked indexed neighbours against exhaustive WGS84 selection for **109 real queries** across all roles and origins. The independent artifact audit reconstructed **135,884 forecast vectors**, scores, region masks, endpoint-count baselines, weights, k selection and multiplier decisions; it rehashed 31 frozen pre-score files.

Two primary attempts reached frozen predictions but exposed report/audit defects: boolean indicator subtraction and mixed-type weighted area reductions. These were corrected without changing probabilities, model inputs, selection or tolerances. A recovery-copy collision was also corrected. Failed attempts and resource receipts are retained. Exact comparison with the first attempt confirms unchanged probability arrays, region masks, states, choices, inner results and outer rosters/targets. First-attempt case scores were not persisted.

The independently audited primary reuses verified frozen artifacts from the second attempt. A separate fresh replay rebuilt from source data, including 383 permitted development drifter files, and passed. It matched 15 tables and eight sparse prediction/region artifacts: discrete decisions and state/lineage fields agree exactly, probabilities and scores within 1e-12, and wet-area summaries within 1e-9 km². Multiplier and resampling arrays agree exactly. Both sealed runs' artifact checksums were verified again before publication.

The fresh full run took **768.0 seconds (12.8 minutes)**, peaking at **1.36 GiB**. Cumulative accounted runtime, including all failed attempts and sealing reserves, is **2,622.92 seconds (43.72 minutes)** against 7,800 seconds approved. Phase totals are 289 seconds for pilots, 1,553.92 seconds for primary attempts, and 780 seconds for the fresh replay, within their respective caps. Retained run artifacts total approximately **268 MB**, below the 5-GiB cap. There were no denied data accesses or final-test reads.

All ten standalone figures were visually inspected, and every HTML image reference resolves to a local artifact. The in-app browser rejected the local-file URL under its protocol policy, so live HTML browser rendering was not verified; no alternate browser route was attempted.

- Audited primary: `exact_origin_s4_e7_primary_20261105T074326_829211Z`.
- Fresh replay: `exact_origin_s4_e7_replay_20261105T074735_038964Z` (passed).
- [Completion audit and resource receipts](../provenance/reviews/exact_origin_s4_e7_audit.json).
- [Test receipt](../provenance/reviews/exact_origin_s4_e7_tests.txt).
- [Reporting-fix invariance](../provenance/reviews/exact_origin_s4_e7_reporting_fix_invariance.json).
- [Post-hoc descriptive diagnostics](../provenance/reviews/exact_origin_s4_e7_posthoc_diagnostics.json).

The approved contract, thresholds, protected stage ledger and historical results have not been revised to accommodate the outcome.
