# Step 3 E3 — Neighbour endpoint information quality

**Status: independently executed and audited; scientific retention awaits user review.**

Where Things End Up: direct stopped 7/30-day destination distributions from an arbitrary qualified origin-cell time. Pooled v7, 1-degree cells, unchanged R/D and eight R-origin neighbours. Final test remains locked.

## Held-out results

| horizon_days | model | brier | region90_cells | region90_hit | region90_mass | zero_true_probability | outside_local_union | evaluable_ids | evaluable_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | Adaptive | 0.966486 | 37.552 | 0.885722 | 0.903166 | 0.00152198 | 0.00292746 | 385 | 303288 |
| 7 | B2 | 0.981297 | 17.5583 | 0.748378 | 0.91035 | 0.0634891 | 0.00292746 | 385 | 303288 |
| 7 | Fixed | 0.962457 | 42.7116 | 0.899558 | 0.902641 | 0.00152198 | 0.00292746 | 385 | 303288 |
| 7 | LocalEndpoint | 0.958288 | 27.3581 | 0.88191 | 0.904131 | 0.00292746 | 0.00292746 | 385 | 303288 |
| 7 | LocalEndpointAdaptive | 0.959104 | 27.2173 | 0.882367 | 0.904356 | 0.00292746 | 0.00292746 | 385 | 303288 |
| 7 | LocalEndpointQuality | 0.958162 | 26.4252 | 0.878366 | 0.904485 | 0.00292746 | 0.00292746 | 385 | 303288 |
| 30 | Adaptive | 0.995303 | 130.933 | 0.777365 | 0.90095 | 0.014935 | 0.0560436 | 337 | 268998 |
| 30 | B2 | 1.01781 | 56.5707 | 0.502761 | 0.908223 | 0.314331 | 0.0560436 | 337 | 268998 |
| 30 | Fixed | 0.994931 | 133.858 | 0.775861 | 0.900926 | 0.014935 | 0.0560436 | 337 | 268998 |
| 30 | LocalEndpoint | 0.993751 | 104.679 | 0.762831 | 0.90197 | 0.0560436 | 0.0560436 | 337 | 268998 |
| 30 | LocalEndpointAdaptive | 0.993452 | 105.34 | 0.768356 | 0.901701 | 0.0560436 | 0.0560436 | 337 | 268998 |
| 30 | LocalEndpointQuality | 0.993507 | 105.126 | 0.76747 | 0.90163 | 0.0560436 | 0.0560436 | 337 | 268998 |

Raw-pair training; equal eligible times within drifter/cell, equal drifters within cell, equal cells. Brier is not percentage accuracy. K90 counts geographic cells, not square-kilometre area. E contributes probability/hits but not a geographic cell. Full fitted distributions are retained; nominal 90% is not a promise of 90% observed hits.

## Model and selection

S=sum(min(local_D, donor_D)); donor weights are proportional to donor D pairs times (1-eta+eta*S). Original pooled E mass is preserved. Weak-unseen endpoints are absent locally, below 1% of original neighbour D mass and supported by fewer than three distinct neighbour IDs. Shared locally rare and strongly supported new endpoints are exempt. Rho retains 1, 0.5 or 0 of weak-unseen borrowed probability; removed D mass returns to local B2 conditional on D. This changes predictions, including possible zeros, without deleting observations.

Five controls are freshly tuned by primary Brier inside each outer training partition. LocalEndpointQuality inherits that partition's LocalEndpointAdaptive a/gamma and selects only nine eta/rho combinations. Eta=0/rho=1 exactly contains its anchor. Outer predictions are frozen before all-development illustration tuning. No held-out future endpoint enters a fitted similarity, gate or support count.

## Prespecified decisions

| horizon_days | meaningful_outer_forecast_change | coverage_preserving_information_gain | preferred_overall_candidate |
| --- | --- | --- | --- |
| 7 | True | False | False |
| 30 | True | False | False |

| horizon_days | model | reference | point_Brier_gain | conditional_Brier_support | conditional_coverage_preserving | conditional_quality_preserving | conditional_smaller_region | joint_point_benefit | application_tradeoff | delta_brier | delta_region90_cells | delta_region90_hit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | LocalEndpointQuality | Fixed | True | False | False | False | False | False | True | -0.00429474 | -16.2865 | -0.0211922 |
| 7 | LocalEndpointQuality | LocalEndpoint | True | False | False | False | False | False | True | -0.000125202 | -0.932972 | -0.00354373 |
| 7 | LocalEndpointQuality | LocalEndpointAdaptive | True | True | False | False | False | False | True | -0.000941101 | -0.792173 | -0.00400112 |
| 30 | LocalEndpointQuality | Fixed | True | True | False | False | False | False | True | -0.00142377 | -28.7314 | -0.0083902 |
| 30 | LocalEndpointQuality | LocalEndpoint | True | True | False | False | False | False | True | -0.000243528 | 0.446703 | 0.00463961 |
| 30 | LocalEndpointQuality | LocalEndpointAdaptive | False | False | False | False | False | False | True | 5.52221e-05 | -0.214069 | -0.000885991 |

| horizon_days | model | reference | metric | difference | lower_95 | upper_95 | adjusted_directional_bound | primary_comparison | defined_replicates |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | LocalEndpointQuality | B2 | brier | -0.0231341 | -0.0305546 | -0.0142094 | NA | False | 20000 |
| 7 | LocalEndpointQuality | B2 | region90_cells | 8.86689 | 8.80682 | 8.9257 | NA | False | 20000 |
| 7 | LocalEndpointQuality | B2 | region90_hit | 0.129988 | 0.115499 | 0.145607 | NA | False | 20000 |
| 7 | LocalEndpointQuality | Fixed | brier | -0.00429474 | -0.00757022 | -0.000649539 | 0.000728858 | True | 20000 |
| 7 | LocalEndpointQuality | Fixed | region90_cells | -16.2865 | -16.3752 | -16.1938 | -16.154 | True | 20000 |
| 7 | LocalEndpointQuality | Fixed | region90_hit | -0.0211922 | -0.0311151 | -0.010468 | -0.0352291 | True | 20000 |
| 7 | LocalEndpointQuality | Adaptive | brier | -0.00832333 | -0.010455 | -0.00618544 | NA | False | 20000 |
| 7 | LocalEndpointQuality | Adaptive | region90_cells | -11.1268 | -11.2428 | -11.0015 | NA | False | 20000 |
| 7 | LocalEndpointQuality | Adaptive | region90_hit | -0.00735596 | -0.0182877 | 0.00596588 | NA | False | 20000 |
| 7 | LocalEndpointQuality | LocalEndpoint | brier | -0.000125202 | -0.00125921 | 0.00128683 | 0.00184077 | True | 20000 |
| 7 | LocalEndpointQuality | LocalEndpoint | region90_cells | -0.932972 | -0.986378 | -0.885644 | -0.868325 | True | 20000 |
| 7 | LocalEndpointQuality | LocalEndpoint | region90_hit | -0.00354373 | -0.0067701 | -0.000682376 | -0.00839706 | True | 20000 |
| 7 | LocalEndpointQuality | LocalEndpointAdaptive | brier | -0.000941101 | -0.00149267 | -0.000342172 | -7.41784e-05 | True | 20000 |
| 7 | LocalEndpointQuality | LocalEndpointAdaptive | region90_cells | -0.792173 | -0.829585 | -0.749389 | -0.734936 | True | 20000 |
| 7 | LocalEndpointQuality | LocalEndpointAdaptive | region90_hit | -0.00400112 | -0.00694454 | -0.00152708 | -0.00857481 | True | 20000 |
| 7 | LocalEndpointQuality | QualitySimilarityOnly | brier | 0 | 0 | 0 | NA | False | 20000 |
| 7 | LocalEndpointQuality | QualitySimilarityOnly | region90_cells | 0 | 0 | 0 | NA | False | 20000 |
| 7 | LocalEndpointQuality | QualitySimilarityOnly | region90_hit | 0 | 0 | 0 | NA | False | 20000 |
| 7 | LocalEndpointQuality | QualityGateOnly | brier | -0.000941101 | -0.00149267 | -0.000342172 | NA | False | 20000 |
| 7 | LocalEndpointQuality | QualityGateOnly | region90_cells | -0.792173 | -0.829585 | -0.749389 | NA | False | 20000 |
| 7 | LocalEndpointQuality | QualityGateOnly | region90_hit | -0.00400112 | -0.00694454 | -0.00152708 | NA | False | 20000 |
| 30 | LocalEndpointQuality | B2 | brier | -0.0243071 | -0.0267968 | -0.0214822 | NA | False | 20000 |
| 30 | LocalEndpointQuality | B2 | region90_cells | 48.5555 | 48.3692 | 48.7297 | NA | False | 20000 |
| 30 | LocalEndpointQuality | B2 | region90_hit | 0.264709 | 0.246451 | 0.282659 | NA | False | 20000 |
| 30 | LocalEndpointQuality | Fixed | brier | -0.00142377 | -0.00242371 | -0.000501482 | -0.000161348 | True | 20000 |
| 30 | LocalEndpointQuality | Fixed | region90_cells | -28.7314 | -29.1172 | -28.2931 | -28.085 | True | 20000 |
| 30 | LocalEndpointQuality | Fixed | region90_hit | -0.0083902 | -0.0284893 | 0.0114534 | -0.0370166 | True | 20000 |
| 30 | LocalEndpointQuality | Adaptive | brier | -0.00179592 | -0.00280272 | -0.000843488 | NA | False | 20000 |
| 30 | LocalEndpointQuality | Adaptive | region90_cells | -25.8071 | -26.1503 | -25.4532 | NA | False | 20000 |
| 30 | LocalEndpointQuality | Adaptive | region90_hit | -0.0098947 | -0.029067 | 0.00920847 | NA | False | 20000 |
| 30 | LocalEndpointQuality | LocalEndpoint | brier | -0.000243528 | -0.00037044 | -0.000113579 | -4.99384e-05 | True | 20000 |
| 30 | LocalEndpointQuality | LocalEndpoint | region90_cells | 0.446703 | 0.321399 | 0.568207 | 0.61235 | True | 20000 |
| 30 | LocalEndpointQuality | LocalEndpoint | region90_hit | 0.00463961 | 0.00105569 | 0.00840442 | -0.000458021 | True | 20000 |
| 30 | LocalEndpointQuality | LocalEndpointAdaptive | brier | 5.52221e-05 | 9.46386e-06 | 0.000112294 | 0.000137415 | True | 20000 |
| 30 | LocalEndpointQuality | LocalEndpointAdaptive | region90_cells | -0.214069 | -0.307713 | -0.135962 | -0.112569 | True | 20000 |
| 30 | LocalEndpointQuality | LocalEndpointAdaptive | region90_hit | -0.000885991 | -0.00269619 | 0.000201029 | -0.00364766 | True | 20000 |
| 30 | LocalEndpointQuality | QualitySimilarityOnly | brier | 0 | 0 | 0 | NA | False | 20000 |
| 30 | LocalEndpointQuality | QualitySimilarityOnly | region90_cells | 0 | 0 | 0 | NA | False | 20000 |
| 30 | LocalEndpointQuality | QualitySimilarityOnly | region90_hit | 0 | 0 | 0 | NA | False | 20000 |
| 30 | LocalEndpointQuality | QualityGateOnly | brier | 5.52221e-05 | 9.46386e-06 | 0.000112294 | NA | False | 20000 |
| 30 | LocalEndpointQuality | QualityGateOnly | region90_cells | -0.214069 | -0.307713 | -0.135962 | NA | False | 20000 |
| 30 | LocalEndpointQuality | QualityGateOnly | region90_hit | -0.000885991 | -0.00269619 | 0.000201029 | NA | False | 20000 |

Differences are Quality minus reference. Ordinary 95% intervals and 18 directional screens use 20,000 paired PCG64 Exp(1) whole-ID multipliers, seed 20261031. Fits are held fixed. These conditional development screens omit refitting, shared-training dependence, ocean forcing and repeated research adaptation. Non-significance does not establish non-deterioration.

A coverage-preserving information gain requires supported Brier improvement and preserved hits against LocalEndpointAdaptive; region expansion is then reported as a trade-off. The overall candidate must additionally pass no-region-expansion quality rules against LocalEndpointAdaptive, LocalEndpoint and Fixed, and actually change forecasts. Smaller regions with lost coverage do not pass.

## Selection and component ablations

| role | horizon_days | model | parameter_a | parameter_gamma | parameter_eta | parameter_rho |
| --- | --- | --- | --- | --- | --- | --- |
| outer_0 | 7 | Fixed | 0.5 | 0 | 0 | 1 |
| outer_0 | 7 | Adaptive | 0.3 | 0 | 0 | 1 |
| outer_0 | 7 | LocalEndpoint | 0.7 | 0 | 0 | 1 |
| outer_0 | 7 | LocalEndpointAdaptive | 0.6 | 0.5 | 0 | 1 |
| outer_0 | 30 | Fixed | 0.85 | 0 | 0 | 1 |
| outer_0 | 30 | Adaptive | 0.75 | 0 | 0 | 1 |
| outer_0 | 30 | LocalEndpoint | 0.95 | 0 | 0 | 1 |
| outer_0 | 30 | LocalEndpointAdaptive | 0.85 | 2 | 0 | 1 |
| outer_0 | 7 | LocalEndpointQuality | 0.6 | 0.5 | 0.9 | 1 |
| outer_0 | 30 | LocalEndpointQuality | 0.85 | 2 | 0 | 1 |
| outer_0 | 7 | QualitySimilarityOnly | 0.6 | 0.5 | 0.9 | 1 |
| outer_0 | 30 | QualitySimilarityOnly | 0.85 | 2 | 0 | 1 |
| outer_0 | 7 | QualityGateOnly | 0.6 | 0.5 | 0 | 1 |
| outer_0 | 30 | QualityGateOnly | 0.85 | 2 | 0 | 1 |
| outer_1 | 7 | Fixed | 0.5 | 0 | 0 | 1 |
| outer_1 | 7 | Adaptive | 0.3 | 0 | 0 | 1 |
| outer_1 | 7 | LocalEndpoint | 0.7 | 0 | 0 | 1 |
| outer_1 | 7 | LocalEndpointAdaptive | 0.7 | 0 | 0 | 1 |
| outer_1 | 30 | Fixed | 0.9 | 0 | 0 | 1 |
| outer_1 | 30 | Adaptive | 0.8 | 0 | 0 | 1 |
| outer_1 | 30 | LocalEndpoint | 0.95 | 0 | 0 | 1 |
| outer_1 | 30 | LocalEndpointAdaptive | 0.9 | 2 | 0 | 1 |
| outer_1 | 7 | LocalEndpointQuality | 0.7 | 0 | 0.9 | 1 |
| outer_1 | 30 | LocalEndpointQuality | 0.9 | 2 | 0 | 1 |
| outer_1 | 7 | QualitySimilarityOnly | 0.7 | 0 | 0.9 | 1 |
| outer_1 | 30 | QualitySimilarityOnly | 0.9 | 2 | 0 | 1 |
| outer_1 | 7 | QualityGateOnly | 0.7 | 0 | 0 | 1 |
| outer_1 | 30 | QualityGateOnly | 0.9 | 2 | 0 | 1 |
| outer_2 | 7 | Fixed | 0.5 | 0 | 0 | 1 |
| outer_2 | 7 | Adaptive | 0.35 | 0 | 0 | 1 |
| outer_2 | 7 | LocalEndpoint | 0.7 | 0 | 0 | 1 |
| outer_2 | 7 | LocalEndpointAdaptive | 0.7 | 0 | 0 | 1 |
| outer_2 | 30 | Fixed | 0.8 | 0 | 0 | 1 |
| outer_2 | 30 | Adaptive | 0.75 | 0 | 0 | 1 |
| outer_2 | 30 | LocalEndpoint | 0.95 | 0 | 0 | 1 |
| outer_2 | 30 | LocalEndpointAdaptive | 0.9 | 2 | 0 | 1 |
| outer_2 | 7 | LocalEndpointQuality | 0.7 | 0 | 0.9 | 1 |
| outer_2 | 30 | LocalEndpointQuality | 0.9 | 2 | 0 | 1 |
| outer_2 | 7 | QualitySimilarityOnly | 0.7 | 0 | 0.9 | 1 |
| outer_2 | 30 | QualitySimilarityOnly | 0.9 | 2 | 0 | 1 |
| outer_2 | 7 | QualityGateOnly | 0.7 | 0 | 0 | 1 |
| outer_2 | 30 | QualityGateOnly | 0.9 | 2 | 0 | 1 |
| outer_3 | 7 | Fixed | 0.5 | 0 | 0 | 1 |
| outer_3 | 7 | Adaptive | 0.3 | 0 | 0 | 1 |
| outer_3 | 7 | LocalEndpoint | 0.7 | 0 | 0 | 1 |
| outer_3 | 7 | LocalEndpointAdaptive | 0.6 | 0.5 | 0 | 1 |
| outer_3 | 30 | Fixed | 0.85 | 0 | 0 | 1 |
| outer_3 | 30 | Adaptive | 0.7 | 0 | 0 | 1 |
| outer_3 | 30 | LocalEndpoint | 0.95 | 0 | 0 | 1 |
| outer_3 | 30 | LocalEndpointAdaptive | 0.9 | 2 | 0 | 1 |
| outer_3 | 7 | LocalEndpointQuality | 0.6 | 0.5 | 0.9 | 1 |
| outer_3 | 30 | LocalEndpointQuality | 0.9 | 2 | 0.5 | 1 |
| outer_3 | 7 | QualitySimilarityOnly | 0.6 | 0.5 | 0.9 | 1 |
| outer_3 | 30 | QualitySimilarityOnly | 0.9 | 2 | 0.5 | 1 |
| outer_3 | 7 | QualityGateOnly | 0.6 | 0.5 | 0 | 1 |
| outer_3 | 30 | QualityGateOnly | 0.9 | 2 | 0 | 1 |
| outer_4 | 7 | Fixed | 0.45 | 0 | 0 | 1 |
| outer_4 | 7 | Adaptive | 0.25 | 0 | 0 | 1 |
| outer_4 | 7 | LocalEndpoint | 0.65 | 0 | 0 | 1 |
| outer_4 | 7 | LocalEndpointAdaptive | 0.65 | 0 | 0 | 1 |
| outer_4 | 30 | Fixed | 0.8 | 0 | 0 | 1 |
| outer_4 | 30 | Adaptive | 0.75 | 0 | 0 | 1 |
| outer_4 | 30 | LocalEndpoint | 0.95 | 0 | 0 | 1 |
| outer_4 | 30 | LocalEndpointAdaptive | 0.85 | 2 | 0 | 1 |
| outer_4 | 7 | LocalEndpointQuality | 0.65 | 0 | 0.9 | 1 |
| outer_4 | 30 | LocalEndpointQuality | 0.85 | 2 | 0 | 1 |
| outer_4 | 7 | QualitySimilarityOnly | 0.65 | 0 | 0.9 | 1 |
| outer_4 | 30 | QualitySimilarityOnly | 0.85 | 2 | 0 | 1 |
| outer_4 | 7 | QualityGateOnly | 0.65 | 0 | 0 | 1 |
| outer_4 | 30 | QualityGateOnly | 0.85 | 2 | 0 | 1 |
| all_development_candidate | 7 | Fixed | 0.45 | 0 | 0 | 1 |
| all_development_candidate | 7 | Adaptive | 0.3 | 0 | 0 | 1 |
| all_development_candidate | 7 | LocalEndpoint | 0.65 | 0 | 0 | 1 |
| all_development_candidate | 7 | LocalEndpointAdaptive | 0.65 | 0 | 0 | 1 |
| all_development_candidate | 30 | Fixed | 0.8 | 0 | 0 | 1 |
| all_development_candidate | 30 | Adaptive | 0.7 | 0 | 0 | 1 |
| all_development_candidate | 30 | LocalEndpoint | 0.9 | 0 | 0 | 1 |
| all_development_candidate | 30 | LocalEndpointAdaptive | 0.85 | 2 | 0 | 1 |
| all_development_candidate | 7 | LocalEndpointQuality | 0.65 | 0 | 0.9 | 1 |
| all_development_candidate | 30 | LocalEndpointQuality | 0.85 | 2 | 0 | 1 |
| all_development_candidate | 7 | QualitySimilarityOnly | 0.65 | 0 | 0.9 | 1 |
| all_development_candidate | 30 | QualitySimilarityOnly | 0.85 | 2 | 0 | 1 |
| all_development_candidate | 7 | QualityGateOnly | 0.65 | 0 | 0 | 1 |
| all_development_candidate | 30 | QualityGateOnly | 0.85 | 2 | 0 | 1 |

| horizon_days | model | brier | region90_cells | region90_hit | region90_mass | zero_true_probability | outside_local_union | evaluable_ids | evaluable_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | LocalEndpointAdaptive | 0.959104 | 27.2173 | 0.882367 | 0.904356 | 0.00292746 | 0.00292746 | 385 | 303288 |
| 7 | LocalEndpointQuality | 0.958162 | 26.4252 | 0.878366 | 0.904485 | 0.00292746 | 0.00292746 | 385 | 303288 |
| 7 | QualityGateOnly | 0.959104 | 27.2173 | 0.882367 | 0.904356 | 0.00292746 | 0.00292746 | 385 | 303288 |
| 7 | QualitySimilarityOnly | 0.958162 | 26.4252 | 0.878366 | 0.904485 | 0.00292746 | 0.00292746 | 385 | 303288 |
| 30 | LocalEndpointAdaptive | 0.993452 | 105.34 | 0.768356 | 0.901701 | 0.0560436 | 0.0560436 | 337 | 268998 |
| 30 | LocalEndpointQuality | 0.993507 | 105.126 | 0.76747 | 0.90163 | 0.0560436 | 0.0560436 | 337 | 268998 |
| 30 | QualityGateOnly | 0.993452 | 105.34 | 0.768356 | 0.901701 | 0.0560436 | 0.0560436 | 337 | 268998 |
| 30 | QualitySimilarityOnly | 0.993507 | 105.126 | 0.76747 | 0.90163 | 0.0560436 | 0.0560436 | 337 | 268998 |

Similarity-only and gate-only ablations remove one selected component without retuning; they are not extra searched winners. A tie or neutral choice is a valid negative finding. No threshold or grid is expanded after the result.

## Mechanism and support

| role | horizon_days | cells | changed_rows | mean_total_variation | maximum_total_variation | mean_returned_mass | maximum_returned_mass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all_development_candidate | 7 | 37 | 37 | 0.034554 | 0.0906022 | 0 | 0 |
| all_development_candidate | 30 | 37 | 0 | 0 | 0 | 0 | 0 |
| outer_0 | 7 | 37 | 37 | 0.0342552 | 0.12244 | 0 | 0 |
| outer_0 | 30 | 37 | 0 | 0 | 0 | 0 | 0 |
| outer_1 | 7 | 37 | 37 | 0.0375527 | 0.08576 | 0 | 0 |
| outer_1 | 30 | 37 | 0 | 0 | 0 | 0 | 0 |
| outer_2 | 7 | 37 | 37 | 0.0381387 | 0.103118 | 0 | 0 |
| outer_2 | 30 | 37 | 0 | 0 | 0 | 0 | 0 |
| outer_3 | 7 | 37 | 37 | 0.0338801 | 0.152556 | 0 | 0 |
| outer_3 | 30 | 37 | 37 | 0.0139121 | 0.0552699 | 0 | 0 |
| outer_4 | 7 | 37 | 37 | 0.0350919 | 0.0993306 | 0 | 0 |
| outer_4 | 30 | 37 | 0 | 0 | 0 | 0 | 0 |

Mechanism summaries above are unweighted fitted-row descriptions. Mixed returned mass is lambda*delta; nominal lambda alone does not describe endpoint-specific shrinkage. Source similarity can reinforce sampling error; distinct IDs are support proxies, not independent sample sizes. Shared rare endpoints are protected from the gate but can still gain or lose probability after source reweighting.

| horizon_days | model | stratum | primary_weight_mass | ids | cells | brier | region90_cells | region90_hit | stratum_type |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | Adaptive | 1-9 fitting IDs | 0.0761671 | 20 | 3 | 0.930726 | 44.3825 | 0.874209 | support_stratum |
| 7 | Adaptive | 10-49 fitting IDs | 0.0946287 | 115 | 6 | 0.97636 | 44.1213 | 0.826651 | support_stratum |
| 7 | Adaptive | 50+ fitting IDs | 0.829204 | 385 | 31 | 0.968644 | 36.1749 | 0.893521 | support_stratum |
| 7 | B2 | 1-9 fitting IDs | 0.0761671 | 20 | 3 | 0.957777 | 4.18894 | 0.712758 | support_stratum |
| 7 | B2 | 10-49 fitting IDs | 0.0946287 | 115 | 6 | 1.03834 | 10.5561 | 0.58407 | support_stratum |
| 7 | B2 | 50+ fitting IDs | 0.829204 | 385 | 31 | 0.976947 | 19.5854 | 0.770401 | support_stratum |
| 7 | Fixed | 1-9 fitting IDs | 0.0761671 | 20 | 3 | 0.898567 | 37.6267 | 0.887285 | support_stratum |
| 7 | Fixed | 10-49 fitting IDs | 0.0946287 | 115 | 6 | 0.973164 | 41.4926 | 0.833412 | support_stratum |
| 7 | Fixed | 50+ fitting IDs | 0.829204 | 385 | 31 | 0.967104 | 43.3178 | 0.908235 | support_stratum |
| 7 | LocalEndpoint | 1-9 fitting IDs | 0.0761671 | 20 | 3 | 0.879911 | 22.1659 | 0.982398 | support_stratum |
| 7 | LocalEndpoint | 10-49 fitting IDs | 0.0946287 | 115 | 6 | 0.952824 | 24.1131 | 0.87213 | support_stratum |
| 7 | LocalEndpoint | 50+ fitting IDs | 0.829204 | 385 | 31 | 0.966111 | 28.2054 | 0.873796 | support_stratum |
| 7 | LocalEndpointAdaptive | 1-9 fitting IDs | 0.0761671 | 20 | 3 | 0.893877 | 22.7281 | 0.982398 | support_stratum |
| 7 | LocalEndpointAdaptive | 10-49 fitting IDs | 0.0946287 | 115 | 6 | 0.952292 | 24.4032 | 0.87213 | support_stratum |
| 7 | LocalEndpointAdaptive | 50+ fitting IDs | 0.829204 | 385 | 31 | 0.965872 | 27.9509 | 0.874347 | support_stratum |
| 7 | LocalEndpointQuality | 1-9 fitting IDs | 0.0761671 | 20 | 3 | 0.886762 | 20.0276 | 0.982398 | support_stratum |
| 7 | LocalEndpointQuality | 10-49 fitting IDs | 0.0946287 | 115 | 6 | 0.952545 | 23.2054 | 0.862702 | support_stratum |
| 7 | LocalEndpointQuality | 50+ fitting IDs | 0.829204 | 385 | 31 | 0.965362 | 27.3803 | 0.870598 | support_stratum |
| 7 | QualityGateOnly | 1-9 fitting IDs | 0.0761671 | 20 | 3 | 0.893877 | 22.7281 | 0.982398 | support_stratum |
| 7 | QualityGateOnly | 10-49 fitting IDs | 0.0946287 | 115 | 6 | 0.952292 | 24.4032 | 0.87213 | support_stratum |
| 7 | QualityGateOnly | 50+ fitting IDs | 0.829204 | 385 | 31 | 0.965872 | 27.9509 | 0.874347 | support_stratum |
| 7 | QualitySimilarityOnly | 1-9 fitting IDs | 0.0761671 | 20 | 3 | 0.886762 | 20.0276 | 0.982398 | support_stratum |
| 7 | QualitySimilarityOnly | 10-49 fitting IDs | 0.0946287 | 115 | 6 | 0.952545 | 23.2054 | 0.862702 | support_stratum |
| 7 | QualitySimilarityOnly | 50+ fitting IDs | 0.829204 | 385 | 31 | 0.965362 | 27.3803 | 0.870598 | support_stratum |
| 30 | Adaptive | 1-9 fitting IDs | 0.0810811 | 18 | 3 | 1.0005 | 135.111 | 0.78687 | support_stratum |
| 30 | Adaptive | 10-49 fitting IDs | 0.144507 | 158 | 6 | 0.997967 | 133.763 | 0.684007 | support_stratum |
| 30 | Adaptive | 50+ fitting IDs | 0.774412 | 336 | 31 | 0.994262 | 129.968 | 0.793791 | support_stratum |
| 30 | B2 | 1-9 fitting IDs | 0.0810811 | 18 | 3 | 1.09951 | 10.2148 | 0.315252 | support_stratum |
| 30 | B2 | 10-49 fitting IDs | 0.144507 | 158 | 6 | 1.0591 | 23.3472 | 0.270761 | support_stratum |
| 30 | B2 | 50+ fitting IDs | 0.774412 | 336 | 31 | 1.00156 | 67.6237 | 0.565685 | support_stratum |
| 30 | Fixed | 1-9 fitting IDs | 0.0810811 | 18 | 3 | 0.996259 | 128.333 | 0.753888 | support_stratum |
| 30 | Fixed | 10-49 fitting IDs | 0.144507 | 158 | 6 | 0.997507 | 130.822 | 0.674935 | support_stratum |
| 30 | Fixed | 50+ fitting IDs | 0.774412 | 336 | 31 | 0.994311 | 135.002 | 0.796994 | support_stratum |
| 30 | LocalEndpoint | 1-9 fitting IDs | 0.0810811 | 18 | 3 | 0.987538 | 97.2519 | 0.864572 | support_stratum |
| 30 | LocalEndpoint | 10-49 fitting IDs | 0.144507 | 158 | 6 | 0.9939 | 98.9477 | 0.724972 | support_stratum |
| 30 | LocalEndpoint | 50+ fitting IDs | 0.774412 | 336 | 31 | 0.994373 | 106.527 | 0.759243 | support_stratum |
| 30 | LocalEndpointAdaptive | 1-9 fitting IDs | 0.0810811 | 18 | 3 | 0.987979 | 98.4 | 0.864572 | support_stratum |
| 30 | LocalEndpointAdaptive | 10-49 fitting IDs | 0.144507 | 158 | 6 | 0.993574 | 99.4476 | 0.731188 | support_stratum |
| 30 | LocalEndpointAdaptive | 50+ fitting IDs | 0.774412 | 336 | 31 | 0.994002 | 107.166 | 0.765218 | support_stratum |
| 30 | LocalEndpointQuality | 1-9 fitting IDs | 0.0810811 | 18 | 3 | 0.988455 | 97.2963 | 0.855771 | support_stratum |
| 30 | LocalEndpointQuality | 10-49 fitting IDs | 0.144507 | 158 | 6 | 0.993701 | 99.2623 | 0.732142 | support_stratum |
| 30 | LocalEndpointQuality | 50+ fitting IDs | 0.774412 | 336 | 31 | 0.994 | 107.04 | 0.764818 | support_stratum |
| 30 | QualityGateOnly | 1-9 fitting IDs | 0.0810811 | 18 | 3 | 0.987979 | 98.4 | 0.864572 | support_stratum |
| 30 | QualityGateOnly | 10-49 fitting IDs | 0.144507 | 158 | 6 | 0.993574 | 99.4476 | 0.731188 | support_stratum |
| 30 | QualityGateOnly | 50+ fitting IDs | 0.774412 | 336 | 31 | 0.994002 | 107.166 | 0.765218 | support_stratum |
| 30 | QualitySimilarityOnly | 1-9 fitting IDs | 0.0810811 | 18 | 3 | 0.988455 | 97.2963 | 0.855771 | support_stratum |
| 30 | QualitySimilarityOnly | 10-49 fitting IDs | 0.144507 | 158 | 6 | 0.993701 | 99.2623 | 0.732142 | support_stratum |
| 30 | QualitySimilarityOnly | 50+ fitting IDs | 0.774412 | 336 | 31 | 0.994 | 107.04 | 0.764818 | support_stratum |
| 7 | Adaptive | coastal grid polygon | 0.189189 | 122 | 7 | 0.969667 | 45.7553 | 0.804921 | boundary_stratum |
| 7 | Adaptive | offshore grid polygon | 0.810811 | 384 | 30 | 0.965744 | 35.6379 | 0.904576 | boundary_stratum |
| 7 | B2 | coastal grid polygon | 0.189189 | 122 | 7 | 1.01996 | 10.1103 | 0.609992 | boundary_stratum |
| 7 | B2 | offshore grid polygon | 0.810811 | 384 | 30 | 0.972274 | 19.2961 | 0.780668 | boundary_stratum |
| 7 | Fixed | coastal grid polygon | 0.189189 | 122 | 7 | 0.953459 | 42.4869 | 0.818421 | boundary_stratum |
| 7 | Fixed | offshore grid polygon | 0.810811 | 384 | 30 | 0.964557 | 42.7641 | 0.918491 | boundary_stratum |
| 7 | LocalEndpoint | coastal grid polygon | 0.189189 | 122 | 7 | 0.934139 | 27.5574 | 0.904722 | boundary_stratum |
| 7 | LocalEndpoint | offshore grid polygon | 0.810811 | 384 | 30 | 0.963922 | 27.3116 | 0.876587 | boundary_stratum |
| 7 | LocalEndpointAdaptive | coastal grid polygon | 0.189189 | 122 | 7 | 0.939626 | 27.9115 | 0.904743 | boundary_stratum |
| 7 | LocalEndpointAdaptive | offshore grid polygon | 0.810811 | 384 | 30 | 0.963648 | 27.0554 | 0.877146 | boundary_stratum |
| 7 | LocalEndpointQuality | coastal grid polygon | 0.189189 | 122 | 7 | 0.937167 | 25.8215 | 0.900444 | boundary_stratum |
| 7 | LocalEndpointQuality | offshore grid polygon | 0.810811 | 384 | 30 | 0.963061 | 26.566 | 0.873215 | boundary_stratum |
| 7 | QualityGateOnly | coastal grid polygon | 0.189189 | 122 | 7 | 0.939626 | 27.9115 | 0.904743 | boundary_stratum |
| 7 | QualityGateOnly | offshore grid polygon | 0.810811 | 384 | 30 | 0.963648 | 27.0554 | 0.877146 | boundary_stratum |
| 7 | QualitySimilarityOnly | coastal grid polygon | 0.189189 | 122 | 7 | 0.937167 | 25.8215 | 0.900444 | boundary_stratum |
| 7 | QualitySimilarityOnly | offshore grid polygon | 0.810811 | 384 | 30 | 0.963061 | 26.566 | 0.873215 | boundary_stratum |
| 30 | Adaptive | coastal grid polygon | 0.189189 | 100 | 7 | 1.00198 | 134.682 | 0.672022 | boundary_stratum |
| 30 | Adaptive | offshore grid polygon | 0.810811 | 336 | 30 | 0.993746 | 130.059 | 0.801945 | boundary_stratum |
| 30 | B2 | coastal grid polygon | 0.189189 | 100 | 7 | 1.08582 | 18.1828 | 0.249475 | boundary_stratum |
| 30 | B2 | offshore grid polygon | 0.810811 | 336 | 30 | 1.00195 | 65.5278 | 0.561861 | boundary_stratum |
| 30 | Fixed | coastal grid polygon | 0.189189 | 100 | 7 | 1.00005 | 130.393 | 0.64517 | boundary_stratum |
| 30 | Fixed | offshore grid polygon | 0.810811 | 336 | 30 | 0.993737 | 134.666 | 0.806355 | boundary_stratum |
| 30 | LocalEndpoint | coastal grid polygon | 0.189189 | 100 | 7 | 0.992836 | 110.475 | 0.761995 | boundary_stratum |
| 30 | LocalEndpoint | offshore grid polygon | 0.810811 | 336 | 30 | 0.993964 | 103.327 | 0.763026 | boundary_stratum |
| 30 | LocalEndpointAdaptive | coastal grid polygon | 0.189189 | 100 | 7 | 0.992839 | 111.527 | 0.76021 | boundary_stratum |
| 30 | LocalEndpointAdaptive | offshore grid polygon | 0.810811 | 336 | 30 | 0.993595 | 103.897 | 0.770257 | boundary_stratum |
| 30 | LocalEndpointQuality | coastal grid polygon | 0.189189 | 100 | 7 | 0.993149 | 110.887 | 0.756439 | boundary_stratum |
| 30 | LocalEndpointQuality | offshore grid polygon | 0.810811 | 336 | 30 | 0.993591 | 103.782 | 0.770044 | boundary_stratum |
| 30 | QualityGateOnly | coastal grid polygon | 0.189189 | 100 | 7 | 0.992839 | 111.527 | 0.76021 | boundary_stratum |
| 30 | QualityGateOnly | offshore grid polygon | 0.810811 | 336 | 30 | 0.993595 | 103.897 | 0.770257 | boundary_stratum |
| 30 | QualitySimilarityOnly | coastal grid polygon | 0.189189 | 100 | 7 | 0.993149 | 110.887 | 0.756439 | boundary_stratum |
| 30 | QualitySimilarityOnly | offshore grid polygon | 0.810811 | 336 | 30 | 0.993591 | 103.782 | 0.770044 | boundary_stratum |

Support bands and coastal/offshore strata are descriptive and preserve/renormalise primary case weights. All endpoint category probability, outcome, hit and Brier contributions are exported in category_summary.csv. Zero-probability truths remain scored. E calibration is unvalidated if no E outcomes are observed.

## Pair-weighted sensitivity

| horizon_days | model | brier | region90_cells | region90_hit | region90_mass | zero_true_probability | outside_local_union | evaluable_ids | evaluable_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | Adaptive | 0.933234 | 33.342 | 0.948818 | 0.903161 | 0.000675925 | 0.00141779 | 385 | 303288 |
| 7 | B2 | 0.929001 | 18.2258 | 0.87439 | 0.908146 | 0.0208218 | 0.00141779 | 385 | 303288 |
| 7 | Fixed | 0.93824 | 42.0308 | 0.955188 | 0.902729 | 0.000675925 | 0.00141779 | 385 | 303288 |
| 7 | LocalEndpoint | 0.936574 | 26.8208 | 0.935705 | 0.9041 | 0.00141779 | 0.00141779 | 385 | 303288 |
| 7 | LocalEndpointAdaptive | 0.936236 | 26.5538 | 0.936094 | 0.904249 | 0.00141779 | 0.00141779 | 385 | 303288 |
| 7 | LocalEndpointQuality | 0.934896 | 25.8652 | 0.935339 | 0.904525 | 0.00141779 | 0.00141779 | 385 | 303288 |
| 30 | Adaptive | 0.98911 | 127.33 | 0.865839 | 0.900953 | 0.0109406 | 0.0335653 | 337 | 268998 |
| 30 | B2 | 0.994751 | 62.6083 | 0.663726 | 0.905589 | 0.174589 | 0.0335653 | 337 | 268998 |
| 30 | Fixed | 0.989841 | 133.549 | 0.869111 | 0.900895 | 0.0109406 | 0.0335653 | 337 | 268998 |
| 30 | LocalEndpoint | 0.987851 | 102.247 | 0.838805 | 0.901526 | 0.0335653 | 0.0335653 | 337 | 268998 |
| 30 | LocalEndpointAdaptive | 0.987517 | 102.384 | 0.84133 | 0.901286 | 0.0335653 | 0.0335653 | 337 | 268998 |
| 30 | LocalEndpointQuality | 0.98751 | 102.18 | 0.841226 | 0.90127 | 0.0335653 | 0.0335653 | 337 | 268998 |

These are the same forecasts under secondary weights; this table did not select models.

## Engineering verification

- Independent reconstruction: 26 fitting roles; 7850 candidate/horizon/role identities; 6613625 candidate ID-cell rows.
- Maximum absolute reconstruction errors: {'probability': 1.6653345369377348e-16, 'candidate': 6.661338147750939e-16, 'score': np.float64(4.440892098500626e-16), 'summary': np.float64(3.694822225952521e-13), 'support': 3.552713678800501e-15, 'weight': 3.3306690738754696e-16, 'category': np.float64(3.3306690738754696e-16)}.
- Five controls reproduce S3 E2: all 30 selected matrices, parameters, cases, weights and point metrics.
- Count/ID sets, L1-derived overlap, original-reference gates, E conservation, anchor-first selections, ablations, scores and decision bounds independently checked.
- Approved plan/config, source including entrypoint, inputs and outer predictions are hashed; no canonical or final-test trajectory reads.
- Fresh replay status and timing are recorded in the sealed provenance verification and later handoff.

## Visual comparison

Predetermined support/geometry roster: [('high_support', 44744), ('low_support', 44742), ('coastal', 44382)]. All-development maps show fitted distributions; held-out scores establish comparative performance.

![model_comparison.png](model_comparison.png)

![quality_and_region_differences.png](quality_and_region_differences.png)

![component_ablations.png](component_ablations.png)

![neighbour_weights_and_returned_mass.png](neighbour_weights_and_returned_mass.png)

![parameter_stability.png](parameter_stability.png)

![endpoint_category_diagnostics.png](endpoint_category_diagnostics.png)

![per_cell_brier.png](per_cell_brier.png)

![per_cell_region90_cells.png](per_cell_region90_cells.png)

![per_cell_region90_hit.png](per_cell_region90_hit.png)

![candidate_high_support_7d.png](candidate_high_support_7d.png)

![candidate_high_support_30d.png](candidate_high_support_30d.png)

![candidate_low_support_7d.png](candidate_low_support_7d.png)

![candidate_low_support_30d.png](candidate_low_support_30d.png)

![candidate_coastal_7d.png](candidate_coastal_7d.png)

![candidate_coastal_30d.png](candidate_coastal_30d.png)

![information_high_support_7d.png](information_high_support_7d.png)

![information_high_support_30d.png](information_high_support_30d.png)

![information_low_support_7d.png](information_low_support_7d.png)

![information_low_support_30d.png](information_low_support_30d.png)

![information_coastal_7d.png](information_coastal_7d.png)

![information_coastal_30d.png](information_coastal_30d.png)
