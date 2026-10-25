# Pooled neighbourhood baseline — Completed pooled comparison with numerical caveats

This report asks whether borrowing nearby release-cell information helps 7/30-day endpoint forecasts, and whether moving neighbour displacements to the target cell changes that answer. It does not evaluate a one-year Markov model or a grounding predictor. No visualisation is part of this run.

## What was fitted

B0 predicts no cell change. B1 uses the whole-R destination frequencies. B2 uses the target cell's frequencies. Global mixes B2 with B1. Local-U mixes B2 with the original endpoints of the eight neighbouring origin cells. Local-A mixes B2 with neighbour displacements applied at the target cell's actual empirical fitting-origin positions. Grid and Analytic select the borrowing weight by two declared methods; a larger weight means more borrowing.

All donors start inside frozen R. Both local variants use the same equal-weight donor pairs. The aligned calculation uses WGS84 net displacement, not a reconstructed path. A cell centre is not substituted for the empirical release prior. Repeated balanced couplings preserve every donor and anchor's original marginal mass; they approximate independent pairing. Contributions are computational terms, not new observations or IDs.

## Held-out development performance

Lower comparison score is better. The score below is failure-penalised multiclass Brier. For complete forecasts it equals ordinary Brier; when synthetic positions are unresolved, ordinary Brier is not reported as though the physical distribution were complete. Brier is not a percentage accuracy.

| horizon_days | model | eligible_pairs | independent_ids | brier_failure_penalized | forecast_coverage | zero_probability_pairs | region90_hit_pct | mean_region90_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | B0 | 308312 | 387 | 1.711584 | 1.000000 | 263851 | 14.420782 | 1.000000 |
| 7 | B1 | 308312 | 387 | 0.979067 | 1.000000 | 182 | 89.396456 | 49.355377 |
| 7 | B2 | 308312 | 387 | 0.928878 | 1.000000 | 6196 | 87.484756 | 18.345634 |
| 7 | Global-Analytic | 308312 | 387 | 0.928845 | 1.000000 | 182 | 93.851683 | 27.696891 |
| 7 | Global-Grid | 308312 | 387 | 0.928597 | 1.000000 | 182 | 93.086549 | 25.387669 |
| 7 | Local-A-Analytic | 308312 | 387 | 0.928187 | 0.124322 | 72 | 92.456667 | 23.639907 |
| 7 | Local-A-Grid | 308312 | 387 | 0.928368 | 0.124322 | 72 | 92.481318 | 23.828067 |
| 7 | Local-U-Analytic | 308312 | 387 | 0.928477 | 1.000000 | 405 | 91.834246 | 22.563656 |
| 7 | Local-U-Grid | 308312 | 387 | 0.928536 | 1.000000 | 405 | 91.810893 | 22.517586 |
| 30 | B0 | 287004 | 358 | 1.929715 | 1.000000 | 276918 | 3.514237 | 1.000000 |
| 30 | B1 | 287004 | 358 | 0.991638 | 1.000000 | 2756 | 85.677203 | 138.937607 |
| 30 | B2 | 287004 | 358 | 0.994400 | 1.000000 | 47756 | 67.195579 | 64.864173 |
| 30 | Global-Analytic | 287004 | 358 | 0.989005 | 1.000000 | 2756 | 86.197753 | 128.407984 |
| 30 | Global-Grid | 287004 | 358 | 0.989051 | 1.000000 | 2756 | 86.133991 | 128.792285 |
| 30 | Local-A-Analytic | 287004 | 358 | 0.987525 | 0.016975 | 1117 | 88.512704 | 117.917816 |
| 30 | Local-A-Grid | 287004 | 358 | 0.987551 | 0.016975 | 1117 | 88.459394 | 118.082626 |
| 30 | Local-U-Analytic | 287004 | 358 | 0.987608 | 1.000000 | 8121 | 84.361890 | 103.170384 |
| 30 | Local-U-Grid | 287004 | 358 | 0.987593 | 1.000000 | 8121 | 84.463631 | 103.275428 |

`forecast_coverage` means the fraction of eligible pairs receiving a complete probability distribution, not the fraction whose destination has nonzero probability. `region90_hit_pct` is the observed fraction inside the model's at-least-90% region; unavailable regions remain in the denominator. Mean region size is calculated only when the region exists, so read it with region availability in probability_region_summary.csv. Raw log losses remain infinite wherever an observed outcome receives zero probability.

## Selected full-development candidate weights

| family | horizon_days | method | alpha_value | tuning_brier |
| --- | --- | --- | --- | --- |
| Global | 7 | Grid | 0.100000 | 0.928376 |
| Global | 7 | Analytic | 0.090942 | 0.928371 |
| Global | 30 | Grid | 0.600000 | 0.988854 |
| Global | 30 | Analytic | 0.585254 | 0.988851 |
| Local-A | 7 | Grid | 0.300000 | 0.927437 |
| Local-A | 7 | Analytic | 0.256719 | 0.927395 |
| Local-A | 30 | Grid | 0.700000 | 0.987441 |
| Local-A | 30 | Analytic | 0.725179 | 0.987432 |
| Local-U | 7 | Grid | 0.200000 | 0.927962 |
| Local-U | 7 | Analytic | 0.171568 | 0.927936 |
| Local-U | 30 | Grid | 0.800000 | 0.987593 |
| Local-U | 30 | Analytic | 0.763217 | 0.987577 |

These weights were selected using base out-of-fold predictions and the bases were then refitted on all development IDs. Their tuning scores are not independent assessments of the final refits. The main table assesses the corresponding nested selection procedure. Final-test trajectories remain locked.

## Paired differences and practical interpretation

| horizon_days | comparison | delta_brier | lower | upper |
| --- | --- | --- | --- | --- |
| 7 | Local-U-Grid - B2 | -0.000342 | -0.002004 | 0.001476 |
| 7 | Local-A-Grid - B2 | -0.000511 | -0.002318 | 0.001197 |
| 7 | Local-U-Analytic - B2 | -0.000402 | -0.002019 | 0.001267 |
| 7 | Local-A-Analytic - B2 | -0.000691 | -0.002418 | 0.000918 |
| 7 | Local-U-Grid - Global-Grid | -0.000061 | -0.000910 | 0.000942 |
| 7 | Local-A-Grid - Global-Grid | -0.000230 | -0.001294 | 0.000810 |
| 7 | Local-U-Analytic - Global-Analytic | -0.000368 | -0.001012 | 0.000326 |
| 7 | Local-A-Analytic - Global-Analytic | -0.000658 | -0.001634 | 0.000209 |
| 7 | Local-A-Grid - Local-U-Grid | -0.000169 | -0.001002 | 0.000661 |
| 7 | Local-A-Analytic - Local-U-Analytic | -0.000289 | -0.001169 | 0.000487 |
| 30 | Local-U-Grid - B2 | -0.006807 | -0.008363 | -0.005324 |
| 30 | Local-A-Grid - B2 | -0.006850 | -0.008744 | -0.005120 |
| 30 | Local-U-Analytic - B2 | -0.006792 | -0.008357 | -0.005308 |
| 30 | Local-A-Analytic - B2 | -0.006875 | -0.008770 | -0.005168 |
| 30 | Local-U-Grid - Global-Grid | -0.001459 | -0.002081 | -0.000863 |
| 30 | Local-A-Grid - Global-Grid | -0.001501 | -0.002095 | -0.000807 |
| 30 | Local-U-Analytic - Global-Analytic | -0.001397 | -0.001972 | -0.000821 |
| 30 | Local-A-Analytic - Global-Analytic | -0.001480 | -0.002068 | -0.000774 |
| 30 | Local-A-Grid - Local-U-Grid | -0.000042 | -0.000584 | 0.000525 |
| 30 | Local-A-Analytic - Local-U-Analytic | -0.000083 | -0.000638 | 0.000486 |

Negative differences favour the first model. The intervals use 200 paired whole-ID resamples within fixed outer folds. They condition on the saved fits and do not include training refits, weight-selection uncertainty, shared deployment conditions, or numerical integration uncertainty. These are exploratory comparisons, not multiplicity-adjusted confirmatory tests. An interval crossing zero does not establish a dependable improvement. A small score change alone does not establish practical value.

## Implementation and scientific audit

- All nine models were scored on exactly the same source-multiplicity cases. Independent arithmetic reproduced 206,775 score rows; maximum difference 4.44e-16.
- Independent calculations from saved inner models reproduced 72 weight selections, including the final candidate choices.
- Raw fitting pairs independently rebuilt 2444 unaligned local bases and representative aligned bases at both horizons. Saved score/weight artifacts were read back and verified. See fitted_basis_audit.json.
- Original B0/B1/B2 and both global controls reproduce the parent run per case, including probability-region diagnostics. Coordinate preparation independently reconciled the old pair counts and checked source keys and exact durations.
- No validation ID supplies fitted donors or anchors. No canonical rows/features were changed; no final-test trajectories were opened. Geometry and target definitions are unchanged.
- Numerical status: **PROVISIONAL_NUMERICAL_ROWS_REMAIN**; 34 fit rows failed the declared successive-approximation stability criterion. See numerical_audit.csv and final_numerical_audit.csv.
- Exact integration is used for small products. The large-product diagnostic compares the maximum possible blended score change across destinations and weights between successive balanced approximations. Passing it is stability evidence, not a certified bound on the unknown exact integral error.
- Synthetic land/unmappable mass remains unresolved and is not deleted, resampled away, renamed grounding, or renormalised into ocean cells. Known domain exits and unresolved support remain distinct.

## What the evidence can and cannot establish

Use scores_by_cell.csv and scores_by_ID.csv to check whether gains are broad or dominated by a few origins/instruments. Read probability-region coverage with size: a broad region can achieve a high hit rate without useful concentration, while a narrow region can be overconfident. Hourly pairs are correlated; their large row count is not a large count of independent experiments.

The aligned model assumes local transferability of net displacements and averages over subcell origins independently of those displacements. Neighbouring cells can lie on different flow branches or coastal components. Geometry checks do not demonstrate dynamical reachability. Complete-pair estimation conditions on observability. Neither variant includes season, origin velocity, wind, object leeway, or a validated grounding mechanism. The historical mixture cannot establish skill for every object or every release date.

## Next checkpoint

Review the pooled comparisons and any numerical/support limitations. Preserve useful controls even if neither neighbour hypothesis improves scores. Extend the agreed model families to constant-drogued and constant-undrogued intervals on the same ID assignment, with shared-case comparisons. Only after that stage review should the unified visualisation and short-lag Markov experiment proceed. No annual or object-specific accuracy is claimed here.

## Reproduction

Read the matching provenance/run.json for the sealed input run, code/input hashes, integration rule and fold digest. Re-run `.venv/bin/python -B -m data3001.modelling.run_neighbourhood --input-run <sealed-input-run>` to create a new immutable comparison. The same seed, inputs and software reproduce the fitted computation; a new run ID does not authorise overwriting old evidence.
