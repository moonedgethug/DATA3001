# Drogued neighbourhood baseline — Completed comparison with numerical caveats

This report asks whether borrowing nearby release-cell information helps 7/30-day endpoint forecasts, and whether moving neighbour displacements to the target cell changes that answer. It does not evaluate a one-year Markov model or a grounding predictor. No visualisation is part of this run.

## What was fitted

B0 predicts no cell change. B1 uses the whole-R destination frequencies. B2 uses the target cell's frequencies. Global mixes B2 with B1. Local-U mixes B2 with the original endpoints of the eight neighbouring origin cells. Local-A mixes B2 with neighbour displacements applied at the target cell's actual empirical fitting-origin positions. Grid and Analytic select the borrowing weight by two declared methods; a larger weight means more borrowing.

All donors start inside frozen R. Both local variants use the same equal-weight donor pairs. The aligned calculation uses WGS84 net displacement, not a reconstructed path. A cell centre is not substituted for the empirical release prior. Repeated balanced couplings preserve every donor and anchor's original marginal mass; they approximate independent pairing. Contributions are computational terms, not new observations or IDs.

## Held-out development performance

Lower comparison score is better. The score below is failure-penalised multiclass Brier. For complete forecasts it equals ordinary Brier; when synthetic positions are unresolved, ordinary Brier is not reported as though the physical distribution were complete. Brier is not a percentage accuracy.

| horizon_days | model | eligible_pairs | independent_ids | brier_failure_penalized | forecast_coverage | zero_probability_pairs | region90_hit_pct | mean_region90_cells |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | B0 | 178082 | 253 | 1.693613 | 1.000000 | 150801 | 15.319347 | 1.000000 |
| 7 | B1 | 178082 | 253 | 0.979224 | 1.000000 | 595 | 89.728889 | 47.586651 |
| 7 | B2 | 178082 | 253 | 0.929807 | 1.000000 | 7271 | 84.590806 | 17.346964 |
| 7 | Global-Analytic | 178082 | 253 | 0.929955 | 1.000000 | 595 | 93.405285 | 32.207798 |
| 7 | Global-Grid | 178082 | 253 | 0.930171 | 1.000000 | 595 | 93.211554 | 31.631299 |
| 7 | Local-A-Analytic | 178082 | 253 | 0.926831 | 0.199543 | 106 | 92.121045 | 25.027779 |
| 7 | Local-A-Grid | 178082 | 253 | 0.926922 | 0.199543 | 106 | 92.071630 | 25.004431 |
| 7 | Local-U-Analytic | 178082 | 253 | 0.928774 | 1.000000 | 764 | 91.407329 | 23.420874 |
| 7 | Local-U-Grid | 178082 | 253 | 0.928813 | 1.000000 | 764 | 91.448883 | 23.469559 |
| 30 | B0 | 155188 | 226 | 1.923963 | 1.000000 | 149288 | 3.801840 | 1.000000 |
| 30 | B1 | 155188 | 226 | 0.991697 | 1.000000 | 3762 | 83.011573 | 137.453521 |
| 30 | B2 | 155188 | 226 | 1.001880 | 0.998595 | 43558 | 56.135139 | 49.195012 |
| 30 | Global-Analytic | 155188 | 226 | 0.989088 | 0.998595 | 3762 | 84.061912 | 129.377873 |
| 30 | Global-Grid | 155188 | 226 | 0.989152 | 0.998595 | 3762 | 83.753254 | 128.418003 |
| 30 | Local-A-Analytic | 155188 | 226 | 0.987952 | 0.035177 | 1658 | 86.243782 | 111.335852 |
| 30 | Local-A-Grid | 155188 | 226 | 0.987838 | 0.035177 | 1658 | 86.140681 | 110.562973 |
| 30 | Local-U-Analytic | 155188 | 226 | 0.987617 | 0.998595 | 8801 | 80.401191 | 93.556624 |
| 30 | Local-U-Grid | 155188 | 226 | 0.987705 | 0.998595 | 8801 | 80.300023 | 93.274653 |

`forecast_coverage` means the fraction of eligible pairs receiving a complete probability distribution, not the fraction whose destination has nonzero probability. `region90_hit_pct` is the observed fraction inside the model's at-least-90% region; unavailable regions remain in the denominator. Mean region size is calculated only when the region exists, so read it with region availability in probability_region_summary.csv. Raw log losses remain infinite wherever an observed outcome receives zero probability.

## Selected full-development candidate weights

| family | horizon_days | method | alpha_value | tuning_brier |
| --- | --- | --- | --- | --- |
| Global | 7 | Grid | 0.200000 | 0.928274 |
| Global | 7 | Analytic | 0.153718 | 0.928121 |
| Global | 30 | Grid | 0.700000 | 0.988836 |
| Global | 30 | Analytic | 0.680719 | 0.988825 |
| Local-A | 7 | Grid | 0.400000 | 0.925365 |
| Local-A | 7 | Analytic | 0.376422 | 0.925347 |
| Local-A | 30 | Grid | 0.800000 | 0.987838 |
| Local-A | 30 | Analytic | 0.768898 | 0.987815 |
| Local-U | 7 | Grid | 0.300000 | 0.927222 |
| Local-U | 7 | Analytic | 0.251689 | 0.927123 |
| Local-U | 30 | Grid | 0.800000 | 0.987548 |
| Local-U | 30 | Analytic | 0.787066 | 0.987544 |

These weights were selected using base out-of-fold predictions and the bases were then refitted on all development IDs. Their tuning scores are not independent assessments of the final refits. The main table assesses the corresponding nested selection procedure. Final-test trajectories remain locked.

## Paired differences and practical interpretation

| horizon_days | comparison | delta_brier | lower | upper |
| --- | --- | --- | --- | --- |
| 7 | Local-U-Grid - B2 | -0.000994 | -0.004283 | 0.002679 |
| 7 | Local-A-Grid - B2 | -0.002885 | -0.005686 | 0.001159 |
| 7 | Local-U-Analytic - B2 | -0.001033 | -0.004252 | 0.002478 |
| 7 | Local-A-Analytic - B2 | -0.002976 | -0.005766 | 0.001024 |
| 7 | Local-U-Grid - Global-Grid | -0.001358 | -0.002598 | 0.000099 |
| 7 | Local-A-Grid - Global-Grid | -0.003249 | -0.005123 | -0.000942 |
| 7 | Local-U-Analytic - Global-Analytic | -0.001181 | -0.002343 | 0.000361 |
| 7 | Local-A-Analytic - Global-Analytic | -0.003124 | -0.005096 | -0.000687 |
| 7 | Local-A-Grid - Local-U-Grid | -0.001891 | -0.004006 | 0.000066 |
| 7 | Local-A-Analytic - Local-U-Analytic | -0.001943 | -0.004100 | -0.000018 |
| 30 | Local-U-Grid - B2 | -0.014174 | -0.020524 | -0.009601 |
| 30 | Local-A-Grid - B2 | -0.014041 | -0.018552 | -0.010183 |
| 30 | Local-U-Analytic - B2 | -0.014263 | -0.020615 | -0.009658 |
| 30 | Local-A-Analytic - B2 | -0.013928 | -0.018432 | -0.010004 |
| 30 | Local-U-Grid - Global-Grid | -0.001447 | -0.002796 | -0.000268 |
| 30 | Local-A-Grid - Global-Grid | -0.001313 | -0.002977 | 0.001154 |
| 30 | Local-U-Analytic - Global-Analytic | -0.001471 | -0.002939 | -0.000303 |
| 30 | Local-A-Analytic - Global-Analytic | -0.001137 | -0.002756 | 0.001242 |
| 30 | Local-A-Grid - Local-U-Grid | 0.000133 | -0.001777 | 0.003155 |
| 30 | Local-A-Analytic - Local-U-Analytic | 0.000335 | -0.001530 | 0.003311 |

Negative differences favour the first model. The intervals use 200 paired whole-ID resamples within fixed outer folds. They condition on the saved fits and do not include training refits, weight-selection uncertainty, shared deployment conditions, or numerical integration uncertainty. These are exploratory comparisons, not multiplicity-adjusted confirmatory tests. An interval crossing zero does not establish a dependable improvement. A small score change alone does not establish practical value.

## Implementation and scientific audit

- All nine models were scored on exactly the same source-multiplicity cases. Independent arithmetic reproduced 116,802 score rows; maximum difference 4.44e-16.
- Independent calculations from saved inner models reproduced 72 weight selections, including the final candidate choices.
- Raw fitting pairs independently rebuilt 2444 unaligned local bases and representative aligned bases at both horizons. Saved score/weight artifacts were read back and verified. See fitted_basis_audit.json.
- Original B0/B1/B2 and both global controls independently reproduce the existing five-model procedure on this regime-specific population, including probability-region diagnostics. Source-keyed interval preparation checked exact pooled coordinates/endpoints before fixed-state qualification.
- In every outer/inner fit, its held-out IDs supply no fitted donors or anchors. No canonical rows/features were changed; no final-test trajectories were opened. Geometry and target definitions are unchanged.
- Numerical status: **PROVISIONAL_NUMERICAL_ROWS_REMAIN**; 130 fit rows failed the declared successive-approximation stability criterion. See numerical_audit.csv and final_numerical_audit.csv.
- Exact integration is used for small products. The large-product diagnostic compares the maximum possible blended score change across destinations and weights between successive balanced approximations. Passing it is stability evidence, not a certified bound on the unknown exact integral error.
- Synthetic land/unmappable mass remains unresolved and is not deleted, resampled away, renamed grounding, or renormalised into ocean cells. Known domain exits and unresolved support remain distinct.

## What the evidence can and cannot establish

Use scores_by_cell.csv and scores_by_ID.csv to check whether gains are broad or dominated by a few origins/instruments. Read probability-region coverage with size: a broad region can achieve a high hit rate without useful concentration, while a narrow region can be overconfident. Hourly pairs are correlated; their large row count is not a large count of independent experiments.

The aligned model assumes local transferability of net displacements and averages over subcell origins independently of those displacements. Neighbouring cells can lie on different flow branches or coastal components. Geometry checks do not demonstrate dynamical reachability. Complete-pair estimation conditions on observability. Neither variant includes season, origin velocity, wind, object leeway, or a validated grounding mechanism. The historical mixture cannot establish skill for every object or every release date.

## Next checkpoint

Review scores, numerical/support limitations and the combined fixed-regime report before the unified visualisation and short-lag Markov experiment. Status-only qualification does not establish homogeneous drogue depth. Fixed-regime intervals condition on persistence through the horizon and are not operational guarantees about future drogue loss. No annual, causal or object-specific accuracy is claimed here.

## Reproduction

Read provenance/run.json for the input run, code/input hashes, scenario, integration rule and fold digest. The matching runner is run_neighbourhood for pooled and run_regimes for fixed regimes (see --help). Reproduction creates a new immutable run; old evidence cannot be overwritten.
