# Undrogued neighbourhood baseline — Completed comparison with numerical caveats

This report asks whether borrowing nearby release-cell information helps 7/30-day endpoint forecasts, and whether moving neighbour displacements to the target cell changes that answer. It does not evaluate a one-year Markov model or a grounding predictor. No visualisation is part of this run.

## What was fitted

B0 predicts no cell change. B1 uses the whole-R destination frequencies. B2 uses the target cell's frequencies. Global mixes B2 with B1. Local-U mixes B2 with the original endpoints of the eight neighbouring origin cells. Local-A mixes B2 with neighbour displacements applied at the target cell's actual empirical fitting-origin positions. Grid and Analytic select the borrowing weight by two declared methods; a larger weight means more borrowing.

All donors start inside frozen R. Both local variants use the same equal-weight donor pairs. The aligned calculation uses WGS84 net displacement, not a reconstructed path. A cell centre is not substituted for the empirical release prior. Repeated balanced couplings preserve every donor and anchor's original marginal mass; they approximate independent pairing. Contributions are computational terms, not new observations or IDs.

## Held-out development performance

Lower comparison score is better. The score below is failure-penalised multiclass Brier. For complete forecasts it equals ordinary Brier; when synthetic positions are unresolved, ordinary Brier is not reported as though the physical distribution were complete. Brier is not a percentage accuracy.

| horizon_days | model | eligible_pairs | independent_ids | brier_failure_penalized | forecast_coverage | zero_probability_pairs | region90_hit_pct | mean_region90_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | B0 | 122123 | 157 | 1.745634 | 1.000000 | 106591 | 12.718325 | 1.000000 |
| 7 | B1 | 122123 | 157 | 0.978958 | 1.000000 | 304 | 87.083514 | 47.594401 |
| 7 | B2 | 122123 | 157 | 0.951184 | 1.000000 | 7935 | 81.553024 | 16.259533 |
| 7 | Global-Analytic | 122123 | 157 | 0.946781 | 1.000000 | 304 | 92.717997 | 35.396346 |
| 7 | Global-Grid | 122123 | 157 | 0.946465 | 1.000000 | 304 | 92.732737 | 34.985687 |
| 7 | Local-A-Analytic | 122123 | 157 | 0.940892 | 0.202214 | 254 | 91.987586 | 23.999083 |
| 7 | Local-A-Grid | 122123 | 157 | 0.940912 | 0.202214 | 254 | 91.943369 | 24.121533 |
| 7 | Local-U-Analytic | 122123 | 157 | 0.943511 | 1.000000 | 1222 | 91.420126 | 23.946816 |
| 7 | Local-U-Grid | 122123 | 157 | 0.943416 | 1.000000 | 1222 | 91.410299 | 23.633091 |
| 30 | B0 | 116505 | 142 | 1.935402 | 1.000000 | 112742 | 3.229904 | 1.000000 |
| 30 | B1 | 116505 | 142 | 0.992492 | 1.000000 | 4045 | 83.312304 | 120.510845 |
| 30 | B2 | 116505 | 142 | 1.011088 | 1.000000 | 41385 | 48.960130 | 44.761650 |
| 30 | Global-Analytic | 116505 | 142 | 0.991882 | 1.000000 | 4045 | 83.508862 | 117.482623 |
| 30 | Global-Grid | 116505 | 142 | 0.991934 | 1.000000 | 4045 | 83.352646 | 118.042384 |
| 30 | Local-A-Analytic | 116505 | 142 | 0.990626 | 0.049775 | 2966 | 83.148363 | 104.240376 |
| 30 | Local-A-Grid | 116505 | 142 | 0.990558 | 0.049775 | 2966 | 83.219604 | 104.477293 |
| 30 | Local-U-Analytic | 116505 | 142 | 0.992441 | 1.000000 | 9914 | 74.621690 | 85.117291 |
| 30 | Local-U-Grid | 116505 | 142 | 0.992419 | 1.000000 | 9914 | 74.991631 | 85.344638 |

`forecast_coverage` means the fraction of eligible pairs receiving a complete probability distribution, not the fraction whose destination has nonzero probability. `region90_hit_pct` is the observed fraction inside the model's at-least-90% region; unavailable regions remain in the denominator. Mean region size is calculated only when the region exists, so read it with region availability in probability_region_summary.csv. Raw log losses remain infinite wherever an observed outcome receives zero probability.

## Selected full-development candidate weights

| family | horizon_days | method | alpha_value | tuning_brier |
| --- | --- | --- | --- | --- |
| Global | 7 | Grid | 0.300000 | 0.946158 |
| Global | 7 | Analytic | 0.281677 | 0.946137 |
| Global | 30 | Grid | 0.800000 | 0.991891 |
| Global | 30 | Analytic | 0.844292 | 0.991838 |
| Local-A | 7 | Grid | 0.600000 | 0.940468 |
| Local-A | 7 | Analytic | 0.622625 | 0.940454 |
| Local-A | 30 | Grid | 0.900000 | 0.990558 |
| Local-A | 30 | Analytic | 0.902079 | 0.990558 |
| Local-U | 7 | Grid | 0.500000 | 0.943065 |
| Local-U | 7 | Analytic | 0.471498 | 0.943035 |
| Local-U | 30 | Grid | 0.900000 | 0.992419 |
| Local-U | 30 | Analytic | 0.881496 | 0.992411 |

These weights were selected using base out-of-fold predictions and the bases were then refitted on all development IDs. Their tuning scores are not independent assessments of the final refits. The main table assesses the corresponding nested selection procedure. Final-test trajectories remain locked.

## Paired differences and practical interpretation

| horizon_days | comparison | delta_brier | lower | upper |
| --- | --- | --- | --- | --- |
| 7 | Local-U-Grid - B2 | -0.007768 | -0.014032 | -0.003345 |
| 7 | Local-A-Grid - B2 | -0.010272 | -0.017159 | -0.005905 |
| 7 | Local-U-Analytic - B2 | -0.007673 | -0.014288 | -0.003255 |
| 7 | Local-A-Analytic - B2 | -0.010292 | -0.017052 | -0.005965 |
| 7 | Local-U-Grid - Global-Grid | -0.003049 | -0.004173 | -0.001847 |
| 7 | Local-A-Grid - Global-Grid | -0.005553 | -0.007463 | -0.003633 |
| 7 | Local-U-Analytic - Global-Analytic | -0.003270 | -0.004775 | -0.001918 |
| 7 | Local-A-Analytic - Global-Analytic | -0.005889 | -0.008123 | -0.004045 |
| 7 | Local-A-Grid - Local-U-Grid | -0.002504 | -0.004531 | -0.000304 |
| 7 | Local-A-Analytic - Local-U-Analytic | -0.002619 | -0.004748 | -0.000320 |
| 30 | Local-U-Grid - B2 | -0.018668 | -0.026181 | -0.012746 |
| 30 | Local-A-Grid - B2 | -0.020529 | -0.027938 | -0.013949 |
| 30 | Local-U-Analytic - B2 | -0.018647 | -0.026120 | -0.012759 |
| 30 | Local-A-Analytic - B2 | -0.020462 | -0.027848 | -0.013937 |
| 30 | Local-U-Grid - Global-Grid | 0.000485 | -0.000741 | 0.001528 |
| 30 | Local-A-Grid - Global-Grid | -0.001376 | -0.002599 | -0.000138 |
| 30 | Local-U-Analytic - Global-Analytic | 0.000559 | -0.000658 | 0.001549 |
| 30 | Local-A-Analytic - Global-Analytic | -0.001257 | -0.002500 | -0.000043 |
| 30 | Local-A-Grid - Local-U-Grid | -0.001861 | -0.002916 | -0.000862 |
| 30 | Local-A-Analytic - Local-U-Analytic | -0.001815 | -0.002853 | -0.000832 |

Negative differences favour the first model. The intervals use 200 paired whole-ID resamples within fixed outer folds. They condition on the saved fits and do not include training refits, weight-selection uncertainty, shared deployment conditions, or numerical integration uncertainty. These are exploratory comparisons, not multiplicity-adjusted confirmatory tests. An interval crossing zero does not establish a dependable improvement. A small score change alone does not establish practical value.

## Implementation and scientific audit

- All nine models were scored on exactly the same source-multiplicity cases. Independent arithmetic reproduced 81,666 score rows; maximum difference 4.44e-16.
- Independent calculations from saved inner models reproduced 72 weight selections, including the final candidate choices.
- Raw fitting pairs independently rebuilt 2444 unaligned local bases and representative aligned bases at both horizons. Saved score/weight artifacts were read back and verified. See fitted_basis_audit.json.
- Original B0/B1/B2 and both global controls independently reproduce the existing five-model procedure on this regime-specific population, including probability-region diagnostics. Source-keyed interval preparation checked exact pooled coordinates/endpoints before fixed-state qualification.
- In every outer/inner fit, its held-out IDs supply no fitted donors or anchors. No canonical rows/features were changed; no final-test trajectories were opened. Geometry and target definitions are unchanged.
- Numerical status: **PROVISIONAL_NUMERICAL_ROWS_REMAIN**; 295 fit rows failed the declared successive-approximation stability criterion. See numerical_audit.csv and final_numerical_audit.csv.
- Exact integration is used for small products. The large-product diagnostic compares the maximum possible blended score change across destinations and weights between successive balanced approximations. Passing it is stability evidence, not a certified bound on the unknown exact integral error.
- Synthetic land/unmappable mass remains unresolved and is not deleted, resampled away, renamed grounding, or renormalised into ocean cells. Known domain exits and unresolved support remain distinct.

## What the evidence can and cannot establish

Use scores_by_cell.csv and scores_by_ID.csv to check whether gains are broad or dominated by a few origins/instruments. Read probability-region coverage with size: a broad region can achieve a high hit rate without useful concentration, while a narrow region can be overconfident. Hourly pairs are correlated; their large row count is not a large count of independent experiments.

The aligned model assumes local transferability of net displacements and averages over subcell origins independently of those displacements. Neighbouring cells can lie on different flow branches or coastal components. Geometry checks do not demonstrate dynamical reachability. Complete-pair estimation conditions on observability. Neither variant includes season, origin velocity, wind, object leeway, or a validated grounding mechanism. The historical mixture cannot establish skill for every object or every release date.

## Next checkpoint

Review scores, numerical/support limitations and the combined fixed-regime report before the unified visualisation and short-lag Markov experiment. Status-only qualification does not establish homogeneous drogue depth. Fixed-regime intervals condition on persistence through the horizon and are not operational guarantees about future drogue loss. No annual, causal or object-specific accuracy is claimed here.

## Reproduction

Read provenance/run.json for the input run, code/input hashes, scenario, integration rule and fold digest. The matching runner is run_neighbourhood for pooled and run_regimes for fixed regimes (see --help). Reproduction creates a new immutable run; old evidence cannot be overwritten.
