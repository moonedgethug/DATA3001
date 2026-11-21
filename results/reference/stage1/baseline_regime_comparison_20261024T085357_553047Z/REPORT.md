# Fixed drogue-regime baseline comparison

This development experiment asks whether conditioning on a known, sustained drogue state improves 7/30-day endpoint probabilities. All nine pre-agreed models were fitted independently in both regimes, including both unaligned U and displacement-aligned A. No final-test trajectories were accessed, canonical data changed, visualisations generated, or Git publication performed.

## Population and qualification

Drogued means the approved official evidence supports attachment throughout the requested interval; undrogued means a known detached state throughout. Unknown or switching intervals enter neither fixed scenario and remain in the pooled data. Qualification uses the unchanged source-aware contract rules, including official attached-fill restoration, audited boundary dates and precision guards. The denominator below is the previously pooled-eligible endpoint population, not every raw R origin. One ID may contribute to both scenarios at different times; its entire history retains the same fold.

| scenario | horizon_days | eligible_pairs | independent_ids | origin_cells | pooled_pairs | retained_pct |
| --- | --- | --- | --- | --- | --- | --- |
| drogued | 7 | 178082 | 253 | 37 | 308312 | 57.760321 |
| drogued | 30 | 155188 | 226 | 37 | 287004 | 54.071720 |
| undrogued | 7 | 122123 | 157 | 37 | 308312 | 39.610200 |
| undrogued | 30 | 116505 | 142 | 37 | 287004 | 40.593511 |

This is a retrospective sustained-state estimand conditional on endpoint observability. It is not an operational guarantee that a currently attached drogue will stay attached. DEPTH-01 remains unresolved: attached-state qualification does not prove homogeneous 15 m drogue depth. These subsets cannot directly validate predictions for oil, containers or people.

## Held-out development results

Lower failure-penalised Brier is better; it is not percentage accuracy. Complete distributions use ordinary multiclass Brier. Unresolved probability remains in the failure penalty, never renormalised away. Region coverage must be read with region size and availability; zero-probability failures and raw infinite log losses remain visible. Raw scores across different regime populations do not establish which physical regime is easier.

| scenario | horizon_days | model | brier_failure_penalized | zero_probability_pairs | region90_hit_pct | mean_region90_cells |
| --- | --- | --- | --- | --- | --- | --- |
| drogued | 7 | B0 | 1.693613 | 150801 | 15.319347 | 1.000000 |
| drogued | 7 | B1 | 0.979224 | 595 | 89.728889 | 47.586651 |
| drogued | 7 | B2 | 0.929807 | 7271 | 84.590806 | 17.346964 |
| drogued | 7 | Global-Analytic | 0.929955 | 595 | 93.405285 | 32.207798 |
| drogued | 7 | Global-Grid | 0.930171 | 595 | 93.211554 | 31.631299 |
| drogued | 7 | Local-A-Analytic | 0.926831 | 106 | 92.121045 | 25.027779 |
| drogued | 7 | Local-A-Grid | 0.926922 | 106 | 92.071630 | 25.004431 |
| drogued | 7 | Local-U-Analytic | 0.928774 | 764 | 91.407329 | 23.420874 |
| drogued | 7 | Local-U-Grid | 0.928813 | 764 | 91.448883 | 23.469559 |
| drogued | 30 | B0 | 1.923963 | 149288 | 3.801840 | 1.000000 |
| drogued | 30 | B1 | 0.991697 | 3762 | 83.011573 | 137.453521 |
| drogued | 30 | B2 | 1.001880 | 43558 | 56.135139 | 49.195012 |
| drogued | 30 | Global-Analytic | 0.989088 | 3762 | 84.061912 | 129.377873 |
| drogued | 30 | Global-Grid | 0.989152 | 3762 | 83.753254 | 128.418003 |
| drogued | 30 | Local-A-Analytic | 0.987952 | 1658 | 86.243782 | 111.335852 |
| drogued | 30 | Local-A-Grid | 0.987838 | 1658 | 86.140681 | 110.562973 |
| drogued | 30 | Local-U-Analytic | 0.987617 | 8801 | 80.401191 | 93.556624 |
| drogued | 30 | Local-U-Grid | 0.987705 | 8801 | 80.300023 | 93.274653 |
| undrogued | 7 | B0 | 1.745634 | 106591 | 12.718325 | 1.000000 |
| undrogued | 7 | B1 | 0.978958 | 304 | 87.083514 | 47.594401 |
| undrogued | 7 | B2 | 0.951184 | 7935 | 81.553024 | 16.259533 |
| undrogued | 7 | Global-Analytic | 0.946781 | 304 | 92.717997 | 35.396346 |
| undrogued | 7 | Global-Grid | 0.946465 | 304 | 92.732737 | 34.985687 |
| undrogued | 7 | Local-A-Analytic | 0.940892 | 254 | 91.987586 | 23.999083 |
| undrogued | 7 | Local-A-Grid | 0.940912 | 254 | 91.943369 | 24.121533 |
| undrogued | 7 | Local-U-Analytic | 0.943511 | 1222 | 91.420126 | 23.946816 |
| undrogued | 7 | Local-U-Grid | 0.943416 | 1222 | 91.410299 | 23.633091 |
| undrogued | 30 | B0 | 1.935402 | 112742 | 3.229904 | 1.000000 |
| undrogued | 30 | B1 | 0.992492 | 4045 | 83.312304 | 120.510845 |
| undrogued | 30 | B2 | 1.011088 | 41385 | 48.960130 | 44.761650 |
| undrogued | 30 | Global-Analytic | 0.991882 | 4045 | 83.508862 | 117.482623 |
| undrogued | 30 | Global-Grid | 0.991934 | 4045 | 83.352646 | 118.042384 |
| undrogued | 30 | Local-A-Analytic | 0.990626 | 2966 | 83.148363 | 104.240376 |
| undrogued | 30 | Local-A-Grid | 0.990558 | 2966 | 83.219604 | 104.477293 |
| undrogued | 30 | Local-U-Analytic | 0.992441 | 9914 | 74.621690 | 85.117291 |
| undrogued | 30 | Local-U-Grid | 0.992419 | 9914 | 74.991631 | 85.344638 |

## Does regime-specific fitting improve over pooled fitting?

The pooled forecasts and selected weights are frozen from the completed pooled experiment. They are scored again on exactly the same fixed-regime source groups and multiplicities, with the same held-out ID folds; no pooled forecast is retrained or selected on these truths. The following differences compare each fixed model with its corresponding pooled model on those matched cases. Negative differences favour fixed-regime fitting.

| scenario | horizon_days | model | delta_brier | lower | upper |
| --- | --- | --- | --- | --- | --- |
| drogued | 7 | B0 | 0.000000 | 0.000000 | 0.000000 |
| drogued | 7 | B1 | 0.000531 | -0.000034 | 0.001063 |
| drogued | 7 | B2 | 0.006306 | 0.002829 | 0.010929 |
| drogued | 7 | Global-Analytic | 0.005268 | 0.002670 | 0.008935 |
| drogued | 7 | Global-Grid | 0.005901 | 0.003156 | 0.009443 |
| drogued | 7 | Local-A-Analytic | 0.002529 | 0.000933 | 0.005249 |
| drogued | 7 | Local-A-Grid | 0.002397 | 0.000818 | 0.005022 |
| drogued | 7 | Local-U-Analytic | 0.004055 | 0.001870 | 0.007356 |
| drogued | 7 | Local-U-Grid | 0.004141 | 0.001994 | 0.007431 |
| drogued | 30 | B0 | 0.000000 | 0.000000 | 0.000000 |
| drogued | 30 | B1 | 0.000542 | 0.000138 | 0.000957 |
| drogued | 30 | B2 | 0.010204 | 0.007068 | 0.015130 |
| drogued | 30 | Global-Analytic | 0.001241 | 0.000722 | 0.001827 |
| drogued | 30 | Global-Grid | 0.001230 | 0.000705 | 0.001770 |
| drogued | 30 | Local-A-Analytic | 0.001818 | 0.000006 | 0.004507 |
| drogued | 30 | Local-A-Grid | 0.001668 | -0.000149 | 0.004354 |
| drogued | 30 | Local-U-Analytic | 0.001473 | 0.000678 | 0.002123 |
| drogued | 30 | Local-U-Grid | 0.001587 | 0.000793 | 0.002292 |
| undrogued | 7 | B0 | 0.000000 | 0.000000 | 0.000000 |
| undrogued | 7 | B1 | 0.000392 | -0.000184 | 0.001117 |
| undrogued | 7 | B2 | 0.010893 | 0.006722 | 0.016877 |
| undrogued | 7 | Global-Analytic | 0.008602 | 0.005505 | 0.012487 |
| undrogued | 7 | Global-Grid | 0.008140 | 0.005233 | 0.011917 |
| undrogued | 7 | Local-A-Analytic | 0.004462 | 0.002083 | 0.007242 |
| undrogued | 7 | Local-A-Grid | 0.004451 | 0.002193 | 0.007090 |
| undrogued | 7 | Local-U-Analytic | 0.006687 | 0.003790 | 0.010185 |
| undrogued | 7 | Local-U-Grid | 0.006572 | 0.003662 | 0.010035 |
| undrogued | 30 | B0 | 0.000000 | 0.000000 | 0.000000 |
| undrogued | 30 | B1 | 0.000636 | -0.000060 | 0.001422 |
| undrogued | 30 | B2 | 0.014173 | 0.009184 | 0.020312 |
| undrogued | 30 | Global-Analytic | 0.001745 | 0.000728 | 0.002970 |
| undrogued | 30 | Global-Grid | 0.001789 | 0.000771 | 0.002965 |
| undrogued | 30 | Local-A-Analytic | 0.001654 | 0.000563 | 0.002963 |
| undrogued | 30 | Local-A-Grid | 0.001572 | 0.000447 | 0.002906 |
| undrogued | 30 | Local-U-Analytic | 0.003265 | 0.002051 | 0.004827 |
| undrogued | 30 | Local-U-Grid | 0.003244 | 0.001990 | 0.004799 |

Intervals use 200 paired whole-ID resamples within fixed outer folds, conditional on saved fits. They omit training-refit, model-selection, shared-environment and numerical-integration uncertainty. Comparisons are exploratory without multiplicity correction. Crossing zero means the evidence does not resolve the sign of the difference. Sustained-state selection and incomplete follow-up can bias the observed population; these results do not identify a causal drogue effect.

## U versus A and existing controls

U borrows the neighbours' original endpoint distributions. A transfers neighbour net displacements onto the target cell's empirical training origins. Neither is selected as correct on intuition. The tables below compare the fitted selection procedures within each regime on identical cases.

| scenario | horizon_days | comparison | delta_brier | lower | upper |
| --- | --- | --- | --- | --- | --- |
| drogued | 7 | Local-U-Analytic - Global-Analytic | -0.001181 | -0.002343 | 0.000361 |
| drogued | 7 | Local-A-Analytic - Global-Analytic | -0.003124 | -0.005096 | -0.000687 |
| drogued | 7 | Local-A-Analytic - Local-U-Analytic | -0.001943 | -0.004100 | -0.000018 |
| drogued | 30 | Local-U-Analytic - Global-Analytic | -0.001471 | -0.002939 | -0.000303 |
| drogued | 30 | Local-A-Analytic - Global-Analytic | -0.001137 | -0.002756 | 0.001242 |
| drogued | 30 | Local-A-Analytic - Local-U-Analytic | 0.000335 | -0.001530 | 0.003311 |
| undrogued | 7 | Local-U-Analytic - Global-Analytic | -0.003270 | -0.004775 | -0.001918 |
| undrogued | 7 | Local-A-Analytic - Global-Analytic | -0.005889 | -0.008123 | -0.004045 |
| undrogued | 7 | Local-A-Analytic - Local-U-Analytic | -0.002619 | -0.004748 | -0.000320 |
| undrogued | 30 | Local-U-Analytic - Global-Analytic | 0.000559 | -0.000658 | 0.001549 |
| undrogued | 30 | Local-A-Analytic - Global-Analytic | -0.001257 | -0.002500 | -0.000043 |
| undrogued | 30 | Local-A-Analytic - Local-U-Analytic | -0.001815 | -0.002853 | -0.000832 |

## Candidate refit weights

| scenario | family | horizon_days | method | alpha_value | tuning_brier |
| --- | --- | --- | --- | --- | --- |
| drogued | Global | 7 | Grid | 0.200000 | 0.928274 |
| drogued | Global | 7 | Analytic | 0.153718 | 0.928121 |
| drogued | Global | 30 | Grid | 0.700000 | 0.988836 |
| drogued | Global | 30 | Analytic | 0.680719 | 0.988825 |
| drogued | Local-A | 7 | Grid | 0.400000 | 0.925365 |
| drogued | Local-A | 7 | Analytic | 0.376422 | 0.925347 |
| drogued | Local-A | 30 | Grid | 0.800000 | 0.987838 |
| drogued | Local-A | 30 | Analytic | 0.768898 | 0.987815 |
| drogued | Local-U | 7 | Grid | 0.300000 | 0.927222 |
| drogued | Local-U | 7 | Analytic | 0.251689 | 0.927123 |
| drogued | Local-U | 30 | Grid | 0.800000 | 0.987548 |
| drogued | Local-U | 30 | Analytic | 0.787066 | 0.987544 |
| undrogued | Global | 7 | Grid | 0.300000 | 0.946158 |
| undrogued | Global | 7 | Analytic | 0.281677 | 0.946137 |
| undrogued | Global | 30 | Grid | 0.800000 | 0.991891 |
| undrogued | Global | 30 | Analytic | 0.844292 | 0.991838 |
| undrogued | Local-A | 7 | Grid | 0.600000 | 0.940468 |
| undrogued | Local-A | 7 | Analytic | 0.622625 | 0.940454 |
| undrogued | Local-A | 30 | Grid | 0.900000 | 0.990558 |
| undrogued | Local-A | 30 | Analytic | 0.902079 | 0.990558 |
| undrogued | Local-U | 7 | Grid | 0.500000 | 0.943065 |
| undrogued | Local-U | 7 | Analytic | 0.471498 | 0.943035 |
| undrogued | Local-U | 30 | Grid | 0.900000 | 0.992419 |
| undrogued | Local-U | 30 | Analytic | 0.881496 | 0.992411 |

Each family/horizon has its own globally shared borrowing weight. Grid searches 0, 0.1, ..., 1; Analytic minimises the same quadratic score. All selection uses inner OOF predictions; outer scores assess the complete selection procedure. Full-development weights below are deployment candidates, not independent evidence of their own final-refit accuracy.

## Engineering and numerical audit

| scenario | fit_rows | unsettled_fit_rows | final_unsettled |
| --- | --- | --- | --- |
| drogued | 2444 | 130 | 1 |
| undrogued | 2444 | 295 | 9 |

Each model run independently reproduces all five original controls from regime-specific counts, every saved outer score and weight choice, all U bases, and representative A bases from raw fitting pairs. The same outer-five/inner-four ID assignment, frozen R/D/grid, exact timestamps, equal pair weights, target and integration rule are retained. All subsets passed a fit/tuning support preflight; this guarantees computability, not sufficient statistical support in every cell. See per-run support, cell/ID scores, numerical audits and verification receipts.

For A, exact small products and balanced large-product approximations retain original donor and anchor marginals. The stability threshold is a successive-approximation diagnostic, not a certified error bound. Any unsettled inner fit can influence selected weights; unsettled outer fits affect the corresponding predictions. Matched pooled A predictions inherit the pooled run's numerical caveats. Synthetic land positions stay unresolved, not inferred grounding. No observed outside-D endpoint support implies no established outside calibration.

## Scope and next decision

This completes the requested fixed-state baseline comparison only. Review matched differences, interval support, coverage/size and numerical stability before choosing controls for the short-lag Markov stage. One-year, seasonal, arbitrary-object and grounding performance remain unvalidated. Negative or inconclusive effects are valid findings.

## Reproduction and evidence

- Input: `regime_input_20261024T080243_439468Z`
- Pooled reference: `baseline_neighbour_cv_20261024T065917_879042Z`
- drogued: `baseline_drogued_cv_20261024T080519_204788Z`
- undrogued: `baseline_undrogued_cv_20261024T083230_432963Z`

Run `.venv/bin/python -B -m data3001.modelling.run_regimes --input-run <input>` for new fixed fits and a new combined report. Existing sealed fits may be combined using --completed-runs. Run manifests bind data/contract/code hashes, input receipts and fold digests; outputs.json seals every delivered artifact.
