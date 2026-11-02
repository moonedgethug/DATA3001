# Step 3 E4 — Joint endpoint allocation with dual-reference constraints

**Status: independently executed and audited; scientific retention awaits user review.**

Where Things End Up: separate direct stopped 7/30-day distributions from an arbitrary qualified origin time. Annual pooled v7, 1-degree grid, eight R-origin neighbours. Raw-pair fitting, equal drifters within origin and equal origins for evaluation. Final test remains locked.

## Held-out comparison

| horizon_days | model | brier | region90_cells | region90_hit | region90_mass | zero_true_probability | outside_local_union | evaluable_ids | evaluable_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | Adaptive | 0.966486 | 37.552 | 0.885722 | 0.903166 | 0.00152198 | 0.00292746 | 385 | 303288 |
| 7 | B2 | 0.981297 | 17.5583 | 0.748378 | 0.91035 | 0.0634891 | 0.00292746 | 385 | 303288 |
| 7 | Fixed | 0.962457 | 42.7116 | 0.899558 | 0.902641 | 0.00152198 | 0.00292746 | 385 | 303288 |
| 7 | LocalEndpoint | 0.958288 | 27.3581 | 0.88191 | 0.904131 | 0.00292746 | 0.00292746 | 385 | 303288 |
| 7 | LocalEndpointAdaptive | 0.959104 | 27.2173 | 0.882367 | 0.904356 | 0.00292746 | 0.00292746 | 385 | 303288 |
| 7 | LocalEndpointJoint | 0.958054 | 26.8108 | 0.880156 | 0.904329 | 0.00292746 | 0.00292746 | 385 | 303288 |
| 7 | LocalEndpointJointConstrained | 0.959104 | 27.2173 | 0.882367 | 0.904356 | 0.00292746 | 0.00292746 | 385 | 303288 |
| 7 | LocalEndpointQuality | 0.958162 | 26.4252 | 0.878366 | 0.904485 | 0.00292746 | 0.00292746 | 385 | 303288 |
| 30 | Adaptive | 0.995303 | 130.933 | 0.777365 | 0.90095 | 0.014935 | 0.0560436 | 337 | 268998 |
| 30 | B2 | 1.01781 | 56.5707 | 0.502761 | 0.908223 | 0.314331 | 0.0560436 | 337 | 268998 |
| 30 | Fixed | 0.994931 | 133.858 | 0.775861 | 0.900926 | 0.014935 | 0.0560436 | 337 | 268998 |
| 30 | LocalEndpoint | 0.993751 | 104.679 | 0.762831 | 0.90197 | 0.0560436 | 0.0560436 | 337 | 268998 |
| 30 | LocalEndpointAdaptive | 0.993452 | 105.34 | 0.768356 | 0.901701 | 0.0560436 | 0.0560436 | 337 | 268998 |
| 30 | LocalEndpointJoint | 0.993507 | 105.126 | 0.76747 | 0.90163 | 0.0560436 | 0.0560436 | 337 | 268998 |
| 30 | LocalEndpointJointConstrained | 0.993452 | 105.34 | 0.768356 | 0.901701 | 0.0560436 | 0.0560436 | 337 | 268998 |
| 30 | LocalEndpointQuality | 0.993507 | 105.126 | 0.76747 | 0.90163 | 0.0560436 | 0.0560436 | 337 | 268998 |

Brier is not percentage accuracy. K90 counts geographic cells, not area. All models use complete nominal-90% regions with ties; actual hits are measured independently. E contributes probability/hits but no geographic cell.

## Primary acceptance and fallback

| horizon_days | outer_fallbacks | outer_selections | meaningful_outer_forecast_change | preferred_overall_candidate | all_development_fallback |
| --- | --- | --- | --- | --- | --- |
| 7 | 5 | 5 | False | False | True |
| 30 | 5 | 5 | False | False | True |

| horizon_days | model | reference | conditional_Brier_support | conditional_coverage_preserving | conditional_quality_preserving | conditional_smaller_region | joint_point_benefit | delta_brier | delta_region90_cells | delta_region90_hit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | LocalEndpointJointConstrained | Fixed | False | False | False | False | False | -0.00335364 | -15.4943 | -0.0171911 |
| 7 | LocalEndpointJointConstrained | LocalEndpointAdaptive | False | False | False | False | False | 0 | 0 | 0 |
| 30 | LocalEndpointJointConstrained | Fixed | True | False | False | False | False | -0.00147899 | -28.5173 | -0.00750421 |
| 30 | LocalEndpointJointConstrained | LocalEndpointAdaptive | False | False | False | False | False | 3.44169e-15 | 3.55271e-13 | 2.22045e-16 |

The primary candidate must improve Brier while preserving hits and size against BOTH LocalEndpointAdaptive and Fixed. Twelve directional screens across two references, three metrics and two horizons use 20,000 paired whole-ID multipliers. A zero-crossing interval is not evidence of non-deterioration.

| horizon_days | model | reference | metric | difference | lower_95 | upper_95 | adjusted_directional_bound | primary_comparison | defined_replicates |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | LocalEndpointJointConstrained | B2 | brier | -0.022193 | -0.0297004 | -0.0131753 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | B2 | region90_cells | 9.65907 | 9.59798 | 9.72042 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | B2 | region90_hit | 0.13399 | 0.119269 | 0.149854 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | Fixed | brier | -0.00335364 | -0.00646806 | 0.000191294 | 0.00136954 | True | 20000 |
| 7 | LocalEndpointJointConstrained | Fixed | region90_cells | -15.4943 | -15.5961 | -15.389 | -15.3536 | True | 20000 |
| 7 | LocalEndpointJointConstrained | Fixed | region90_hit | -0.0171911 | -0.0270525 | -0.00641927 | -0.0306735 | True | 20000 |
| 7 | LocalEndpointJointConstrained | Adaptive | brier | -0.00738223 | -0.00921232 | -0.00548342 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | Adaptive | region90_cells | -10.3347 | -10.4687 | -10.1952 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | Adaptive | region90_hit | -0.00335485 | -0.0144511 | 0.0099383 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | LocalEndpoint | brier | 0.000815899 | -0.000106334 | 0.00211472 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | LocalEndpoint | region90_cells | -0.140799 | -0.189023 | -0.0913289 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | LocalEndpoint | region90_hit | 0.000457382 | -0.000683833 | 0.00193516 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | LocalEndpointAdaptive | brier | 0 | 0 | 0 | 0 | True | 20000 |
| 7 | LocalEndpointJointConstrained | LocalEndpointAdaptive | region90_cells | 0 | 0 | 0 | 0 | True | 20000 |
| 7 | LocalEndpointJointConstrained | LocalEndpointAdaptive | region90_hit | 0 | 0 | 0 | 0 | True | 20000 |
| 7 | LocalEndpointJointConstrained | LocalEndpointQuality | brier | 0.000941101 | 0.000342172 | 0.00149267 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | LocalEndpointQuality | region90_cells | 0.792173 | 0.749389 | 0.829585 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | LocalEndpointQuality | region90_hit | 0.00400112 | 0.00152708 | 0.00694454 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | LocalEndpointJoint | brier | 0.00104934 | 0.00038622 | 0.00176108 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | LocalEndpointJoint | region90_cells | 0.406553 | 0.363444 | 0.442487 | NA | False | 20000 |
| 7 | LocalEndpointJointConstrained | LocalEndpointJoint | region90_hit | 0.00221117 | -0.000336548 | 0.00521998 | NA | False | 20000 |
| 7 | LocalEndpointJoint | B2 | brier | -0.0232423 | -0.0310294 | -0.0139574 | NA | False | 20000 |
| 7 | LocalEndpointJoint | B2 | region90_cells | 9.25251 | 9.1941 | 9.3102 | NA | False | 20000 |
| 7 | LocalEndpointJoint | B2 | region90_hit | 0.131778 | 0.117124 | 0.147455 | NA | False | 20000 |
| 7 | LocalEndpointJoint | Fixed | brier | -0.00440298 | -0.00804384 | -0.000449642 | NA | False | 20000 |
| 7 | LocalEndpointJoint | Fixed | region90_cells | -15.9009 | -15.9941 | -15.8027 | NA | False | 20000 |
| 7 | LocalEndpointJoint | Fixed | region90_hit | -0.0194023 | -0.0292764 | -0.00872009 | NA | False | 20000 |
| 7 | LocalEndpointJoint | Adaptive | brier | -0.00843157 | -0.0108477 | -0.00607592 | NA | False | 20000 |
| 7 | LocalEndpointJoint | Adaptive | region90_cells | -10.7412 | -10.8613 | -10.613 | NA | False | 20000 |
| 7 | LocalEndpointJoint | Adaptive | region90_hit | -0.00556602 | -0.0165219 | 0.00782259 | NA | False | 20000 |
| 7 | LocalEndpointJoint | LocalEndpoint | brier | -0.000233436 | -0.00160514 | 0.00143954 | NA | False | 20000 |
| 7 | LocalEndpointJoint | LocalEndpoint | region90_cells | -0.547352 | -0.598026 | -0.501584 | NA | False | 20000 |
| 7 | LocalEndpointJoint | LocalEndpoint | region90_hit | -0.00175379 | -0.00478461 | 0.000900786 | NA | False | 20000 |
| 7 | LocalEndpointJoint | LocalEndpointAdaptive | brier | -0.00104934 | -0.00176108 | -0.00038622 | NA | False | 20000 |
| 7 | LocalEndpointJoint | LocalEndpointAdaptive | region90_cells | -0.406553 | -0.442487 | -0.363444 | NA | False | 20000 |
| 7 | LocalEndpointJoint | LocalEndpointAdaptive | region90_hit | -0.00221117 | -0.00521998 | 0.000336548 | NA | False | 20000 |
| 7 | LocalEndpointJoint | LocalEndpointQuality | brier | -0.000108234 | -0.000512056 | 0.000275575 | NA | False | 20000 |
| 7 | LocalEndpointJoint | LocalEndpointQuality | region90_cells | 0.38562 | 0.370429 | 0.399659 | NA | False | 20000 |
| 7 | LocalEndpointJoint | LocalEndpointQuality | region90_hit | 0.00178994 | -0.000191669 | 0.00389273 | NA | False | 20000 |
| 7 | LocalEndpointJoint | LocalEndpointJointConstrained | brier | -0.00104934 | -0.00176108 | -0.00038622 | NA | False | 20000 |
| 7 | LocalEndpointJoint | LocalEndpointJointConstrained | region90_cells | -0.406553 | -0.442487 | -0.363444 | NA | False | 20000 |
| 7 | LocalEndpointJoint | LocalEndpointJointConstrained | region90_hit | -0.00221117 | -0.00521998 | 0.000336548 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | B2 | brier | -0.0243623 | -0.0268723 | -0.0215186 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | B2 | region90_cells | 48.7696 | 48.5705 | 48.9567 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | B2 | region90_hit | 0.265595 | 0.247302 | 0.283486 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | Fixed | brier | -0.00147899 | -0.00245093 | -0.000588831 | -0.000306603 | True | 20000 |
| 30 | LocalEndpointJointConstrained | Fixed | region90_cells | -28.5173 | -28.89 | -28.1081 | -27.9482 | True | 20000 |
| 30 | LocalEndpointJointConstrained | Fixed | region90_hit | -0.00750421 | -0.027314 | 0.0120337 | -0.0344477 | True | 20000 |
| 30 | LocalEndpointJointConstrained | Adaptive | brier | -0.00185114 | -0.00282704 | -0.000939242 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | Adaptive | region90_cells | -25.593 | -25.9343 | -25.2563 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | Adaptive | region90_hit | -0.00900871 | -0.0280203 | 0.00994139 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | LocalEndpoint | brier | -0.00029875 | -0.000422888 | -0.00016212 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | LocalEndpoint | region90_cells | 0.660773 | 0.597685 | 0.739073 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | LocalEndpoint | region90_hit | 0.0055256 | 0.00219143 | 0.00911658 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | LocalEndpointAdaptive | brier | 3.44169e-15 | 0 | 0 | 0 | True | 20000 |
| 30 | LocalEndpointJointConstrained | LocalEndpointAdaptive | region90_cells | 3.55271e-13 | 0 | 0 | 0 | True | 20000 |
| 30 | LocalEndpointJointConstrained | LocalEndpointAdaptive | region90_hit | 2.22045e-16 | 0 | 0 | 0 | True | 20000 |
| 30 | LocalEndpointJointConstrained | LocalEndpointQuality | brier | -5.52221e-05 | -0.000112294 | -9.46386e-06 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | LocalEndpointQuality | region90_cells | 0.214069 | 0.135962 | 0.307713 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | LocalEndpointQuality | region90_hit | 0.000885991 | -0.000201029 | 0.00269619 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | LocalEndpointJoint | brier | -5.52221e-05 | -0.000112294 | -9.46386e-06 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | LocalEndpointJoint | region90_cells | 0.214069 | 0.135962 | 0.307713 | NA | False | 20000 |
| 30 | LocalEndpointJointConstrained | LocalEndpointJoint | region90_hit | 0.000885991 | -0.000201029 | 0.00269619 | NA | False | 20000 |
| 30 | LocalEndpointJoint | B2 | brier | -0.0243071 | -0.0267968 | -0.0214822 | NA | False | 20000 |
| 30 | LocalEndpointJoint | B2 | region90_cells | 48.5555 | 48.3692 | 48.7297 | NA | False | 20000 |
| 30 | LocalEndpointJoint | B2 | region90_hit | 0.264709 | 0.246451 | 0.282659 | NA | False | 20000 |
| 30 | LocalEndpointJoint | Fixed | brier | -0.00142377 | -0.00242371 | -0.000501482 | NA | False | 20000 |
| 30 | LocalEndpointJoint | Fixed | region90_cells | -28.7314 | -29.1172 | -28.2931 | NA | False | 20000 |
| 30 | LocalEndpointJoint | Fixed | region90_hit | -0.0083902 | -0.0284893 | 0.0114534 | NA | False | 20000 |
| 30 | LocalEndpointJoint | Adaptive | brier | -0.00179592 | -0.00280272 | -0.000843488 | NA | False | 20000 |
| 30 | LocalEndpointJoint | Adaptive | region90_cells | -25.8071 | -26.1503 | -25.4532 | NA | False | 20000 |
| 30 | LocalEndpointJoint | Adaptive | region90_hit | -0.0098947 | -0.029067 | 0.00920847 | NA | False | 20000 |
| 30 | LocalEndpointJoint | LocalEndpoint | brier | -0.000243528 | -0.00037044 | -0.000113579 | NA | False | 20000 |
| 30 | LocalEndpointJoint | LocalEndpoint | region90_cells | 0.446703 | 0.321399 | 0.568207 | NA | False | 20000 |
| 30 | LocalEndpointJoint | LocalEndpoint | region90_hit | 0.00463961 | 0.00105569 | 0.00840442 | NA | False | 20000 |
| 30 | LocalEndpointJoint | LocalEndpointAdaptive | brier | 5.52221e-05 | 9.46386e-06 | 0.000112294 | NA | False | 20000 |
| 30 | LocalEndpointJoint | LocalEndpointAdaptive | region90_cells | -0.214069 | -0.307713 | -0.135962 | NA | False | 20000 |
| 30 | LocalEndpointJoint | LocalEndpointAdaptive | region90_hit | -0.000885991 | -0.00269619 | 0.000201029 | NA | False | 20000 |
| 30 | LocalEndpointJoint | LocalEndpointQuality | brier | 0 | 0 | 0 | NA | False | 20000 |
| 30 | LocalEndpointJoint | LocalEndpointQuality | region90_cells | 0 | 0 | 0 | NA | False | 20000 |
| 30 | LocalEndpointJoint | LocalEndpointQuality | region90_hit | 0 | 0 | 0 | NA | False | 20000 |
| 30 | LocalEndpointJoint | LocalEndpointJointConstrained | brier | 5.52221e-05 | 9.46386e-06 | 0.000112294 | NA | False | 20000 |
| 30 | LocalEndpointJoint | LocalEndpointJointConstrained | region90_cells | -0.214069 | -0.307713 | -0.135962 | NA | False | 20000 |
| 30 | LocalEndpointJoint | LocalEndpointJointConstrained | region90_hit | -0.000885991 | -0.00269619 | 0.000201029 | NA | False | 20000 |

## Selection method

All 252 combinations of a=0:0.05:1, gamma={0,0.5,1,2}, eta={0,0.5,0.9} are evaluated; rho=1 in both new arms. Joint minimises inner Brier. JointConstrained requires inner H90>=each reference and K90<=each reference, then adopts the best feasible candidate only if its Brier is below both references. Otherwise it issues the freshly fitted LocalEndpointAdaptive anchor with an explicit failure status. Such fallback does not establish that Fixed quality was preserved.

Each reference threshold is recomputed inside the outer training partition. Inner values are selection data, not independent proof. No selected triple, feasibility condition or denominator changes after observing outer outcomes.

| horizon_days | selection_status | fallback | feasible_anchor | feasible_fixed | feasible_both | feasible_and_Brier | best_rejected_Brier | best_feasible_Brier | issued_parameter_a | issued_parameter_gamma | issued_parameter_eta | issued_parameter_rho | anchor_brier | delta_anchor_brier | anchor_region90_cells | delta_anchor_region90_cells | anchor_region90_hit | delta_anchor_region90_hit | pass_anchor_hit | pass_anchor_size | pass_anchor | fixed_brier | delta_fixed_brier | fixed_region90_cells | delta_fixed_region90_cells | fixed_region90_hit | delta_fixed_region90_hit | pass_fixed_hit | pass_fixed_size | pass_fixed | role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | fallback_no_feasible_candidate | True | 12 | 0 | 0 | 0 | 0.95821 | NA | 0.6 | 0.5 | 0 | 1 | 0.959507 | 0 | 26.4039 | 0 | 0.869257 | 0 | True | True | True | 0.964552 | -0.00504431 | 42.3943 | -15.9904 | 0.889122 | -0.0198649 | False | True | False | outer_0 |
| 30 | fallback_no_feasible_candidate | True | 23 | 0 | 0 | 0 | 0.994838 | NA | 0.85 | 2 | 0 | 1 | 0.994838 | 0 | 98.7875 | 0 | 0.734104 | 0 | True | True | True | 0.995537 | -0.000699216 | 130.184 | -31.3963 | 0.770034 | -0.0359306 | False | True | False | outer_0 |
| 7 | fallback_no_feasible_candidate | True | 11 | 0 | 0 | 0 | 0.957207 | NA | 0.7 | 0 | 0 | 1 | 0.958236 | 0 | 27.0665 | 0 | 0.880285 | 0 | True | True | True | 0.963685 | -0.00544886 | 42.0398 | -14.9733 | 0.885442 | -0.00515665 | False | True | False | outer_1 |
| 30 | fallback_no_feasible_candidate | True | 3 | 0 | 0 | 0 | 0.995388 | NA | 0.9 | 2 | 0 | 1 | 0.995388 | 0 | 99.2086 | 0 | 0.723423 | 0 | True | True | True | 0.9957 | -0.000311902 | 132.782 | -33.5735 | 0.77374 | -0.0503173 | False | True | False | outer_1 |
| 7 | fallback_no_feasible_candidate | True | 8 | 0 | 0 | 0 | 0.958039 | NA | 0.7 | 0 | 0 | 1 | 0.958784 | 0 | 27.077 | 0 | 0.872772 | 0 | True | True | True | 0.963413 | -0.00462967 | 42.7197 | -15.6427 | 0.890099 | -0.0173272 | False | True | False | outer_2 |
| 30 | fallback_no_feasible_candidate | True | 1 | 0 | 0 | 0 | 0.994074 | NA | 0.9 | 2 | 0 | 1 | 0.994074 | 0 | 97.8474 | 0 | 0.743583 | 0 | True | True | True | 0.995294 | -0.00122005 | 127.784 | -29.9363 | 0.747069 | -0.00348694 | False | True | False | outer_2 |
| 7 | fallback_no_feasible_candidate | True | 25 | 0 | 0 | 0 | 0.959744 | NA | 0.6 | 0.5 | 0 | 1 | 0.960674 | 0 | 27.0355 | 0 | 0.873737 | 0 | True | True | True | 0.96601 | -0.00533605 | 43.1171 | -16.0816 | 0.894651 | -0.0209142 | False | True | False | outer_3 |
| 30 | fallback_no_feasible_candidate | True | 10 | 0 | 0 | 0 | 0.99403 | NA | 0.9 | 2 | 0 | 1 | 0.994051 | 0 | 100.128 | 0 | 0.734733 | 0 | True | True | True | 0.995338 | -0.0012861 | 132.925 | -32.7967 | 0.764084 | -0.0293515 | False | True | False | outer_3 |
| 7 | fallback_no_feasible_candidate | True | 1 | 0 | 0 | 0 | 0.959001 | NA | 0.65 | 0 | 0 | 1 | 0.959444 | 0 | 27.0148 | 0 | 0.875641 | 0 | True | True | True | 0.962549 | -0.00310541 | 40.6616 | -13.6467 | 0.882782 | -0.00714031 | False | True | False | outer_4 |
| 30 | fallback_no_feasible_candidate | True | 19 | 0 | 0 | 0 | 0.993728 | NA | 0.85 | 2 | 0 | 1 | 0.993728 | 0 | 99.1571 | 0 | 0.729827 | 0 | True | True | True | 0.99517 | -0.00144194 | 126.662 | -27.5047 | 0.750919 | -0.0210922 | False | True | False | outer_4 |
| 7 | fallback_no_feasible_candidate | True | 1 | 0 | 0 | 0 | 0.957161 | NA | 0.65 | 0 | 0 | 1 | 0.95811 | 0 | 27.0654 | 0 | 0.881609 | 0 | True | True | True | 0.962333 | -0.00422298 | 41.5691 | -14.5037 | 0.895274 | -0.0136648 | False | True | False | all_development_candidate |
| 30 | fallback_no_feasible_candidate | True | 2 | 0 | 0 | 0 | 0.993448 | NA | 0.85 | 2 | 0 | 1 | 0.993448 | 0 | 105.019 | 0 | 0.766614 | 0 | True | True | True | 0.994816 | -0.00136724 | 132.485 | -27.4654 | 0.777743 | -0.0111294 | False | True | False | all_development_candidate |

| role | horizon_days | model | parameter_a | parameter_gamma | parameter_eta | parameter_rho | selection_status | fallback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| outer_0 | 7 | Fixed | 0.5 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_0 | 7 | Adaptive | 0.3 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_0 | 7 | LocalEndpoint | 0.7 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_0 | 7 | LocalEndpointAdaptive | 0.6 | 0.5 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_0 | 30 | Fixed | 0.85 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_0 | 30 | Adaptive | 0.75 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_0 | 30 | LocalEndpoint | 0.95 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_0 | 30 | LocalEndpointAdaptive | 0.85 | 2 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_0 | 7 | LocalEndpointQuality | 0.6 | 0.5 | 0.9 | 1 | anchor_then_Brier_smaller_eta_larger_rho | NA |
| outer_0 | 30 | LocalEndpointQuality | 0.85 | 2 | 0 | 1 | anchor_then_Brier_smaller_eta_larger_rho | NA |
| outer_0 | 7 | LocalEndpointJoint | 0.65 | 0.5 | 0.9 | 1 | unconstrained_joint_Brier | False |
| outer_0 | 7 | LocalEndpointJointConstrained | 0.6 | 0.5 | 0 | 1 | fallback_no_feasible_candidate | True |
| outer_0 | 30 | LocalEndpointJoint | 0.85 | 2 | 0 | 1 | unconstrained_joint_Brier | False |
| outer_0 | 30 | LocalEndpointJointConstrained | 0.85 | 2 | 0 | 1 | fallback_no_feasible_candidate | True |
| outer_1 | 7 | Fixed | 0.5 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_1 | 7 | Adaptive | 0.3 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_1 | 7 | LocalEndpoint | 0.7 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_1 | 7 | LocalEndpointAdaptive | 0.7 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_1 | 30 | Fixed | 0.9 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_1 | 30 | Adaptive | 0.8 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_1 | 30 | LocalEndpoint | 0.95 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_1 | 30 | LocalEndpointAdaptive | 0.9 | 2 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_1 | 7 | LocalEndpointQuality | 0.7 | 0 | 0.9 | 1 | anchor_then_Brier_smaller_eta_larger_rho | NA |
| outer_1 | 30 | LocalEndpointQuality | 0.9 | 2 | 0 | 1 | anchor_then_Brier_smaller_eta_larger_rho | NA |
| outer_1 | 7 | LocalEndpointJoint | 0.75 | 0 | 0.9 | 1 | unconstrained_joint_Brier | False |
| outer_1 | 7 | LocalEndpointJointConstrained | 0.7 | 0 | 0 | 1 | fallback_no_feasible_candidate | True |
| outer_1 | 30 | LocalEndpointJoint | 0.9 | 2 | 0 | 1 | unconstrained_joint_Brier | False |
| outer_1 | 30 | LocalEndpointJointConstrained | 0.9 | 2 | 0 | 1 | fallback_no_feasible_candidate | True |
| outer_2 | 7 | Fixed | 0.5 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_2 | 7 | Adaptive | 0.35 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_2 | 7 | LocalEndpoint | 0.7 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_2 | 7 | LocalEndpointAdaptive | 0.7 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_2 | 30 | Fixed | 0.8 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_2 | 30 | Adaptive | 0.75 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_2 | 30 | LocalEndpoint | 0.95 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_2 | 30 | LocalEndpointAdaptive | 0.9 | 2 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_2 | 7 | LocalEndpointQuality | 0.7 | 0 | 0.9 | 1 | anchor_then_Brier_smaller_eta_larger_rho | NA |
| outer_2 | 30 | LocalEndpointQuality | 0.9 | 2 | 0 | 1 | anchor_then_Brier_smaller_eta_larger_rho | NA |
| outer_2 | 7 | LocalEndpointJoint | 0.75 | 0 | 0.9 | 1 | unconstrained_joint_Brier | False |
| outer_2 | 7 | LocalEndpointJointConstrained | 0.7 | 0 | 0 | 1 | fallback_no_feasible_candidate | True |
| outer_2 | 30 | LocalEndpointJoint | 0.9 | 2 | 0 | 1 | unconstrained_joint_Brier | False |
| outer_2 | 30 | LocalEndpointJointConstrained | 0.9 | 2 | 0 | 1 | fallback_no_feasible_candidate | True |
| outer_3 | 7 | Fixed | 0.5 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_3 | 7 | Adaptive | 0.3 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_3 | 7 | LocalEndpoint | 0.7 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_3 | 7 | LocalEndpointAdaptive | 0.6 | 0.5 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_3 | 30 | Fixed | 0.85 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_3 | 30 | Adaptive | 0.7 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_3 | 30 | LocalEndpoint | 0.95 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_3 | 30 | LocalEndpointAdaptive | 0.9 | 2 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_3 | 7 | LocalEndpointQuality | 0.6 | 0.5 | 0.9 | 1 | anchor_then_Brier_smaller_eta_larger_rho | NA |
| outer_3 | 30 | LocalEndpointQuality | 0.9 | 2 | 0.5 | 1 | anchor_then_Brier_smaller_eta_larger_rho | NA |
| outer_3 | 7 | LocalEndpointJoint | 0.65 | 0.5 | 0.9 | 1 | unconstrained_joint_Brier | False |
| outer_3 | 7 | LocalEndpointJointConstrained | 0.6 | 0.5 | 0 | 1 | fallback_no_feasible_candidate | True |
| outer_3 | 30 | LocalEndpointJoint | 0.9 | 2 | 0.5 | 1 | unconstrained_joint_Brier | False |
| outer_3 | 30 | LocalEndpointJointConstrained | 0.9 | 2 | 0 | 1 | fallback_no_feasible_candidate | True |
| outer_4 | 7 | Fixed | 0.45 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_4 | 7 | Adaptive | 0.25 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_4 | 7 | LocalEndpoint | 0.65 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_4 | 7 | LocalEndpointAdaptive | 0.65 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_4 | 30 | Fixed | 0.8 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_4 | 30 | Adaptive | 0.75 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_4 | 30 | LocalEndpoint | 0.95 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_4 | 30 | LocalEndpointAdaptive | 0.85 | 2 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| outer_4 | 7 | LocalEndpointQuality | 0.65 | 0 | 0.9 | 1 | anchor_then_Brier_smaller_eta_larger_rho | NA |
| outer_4 | 30 | LocalEndpointQuality | 0.85 | 2 | 0 | 1 | anchor_then_Brier_smaller_eta_larger_rho | NA |
| outer_4 | 7 | LocalEndpointJoint | 0.7 | 0 | 0.9 | 1 | unconstrained_joint_Brier | False |
| outer_4 | 7 | LocalEndpointJointConstrained | 0.65 | 0 | 0 | 1 | fallback_no_feasible_candidate | True |
| outer_4 | 30 | LocalEndpointJoint | 0.85 | 2 | 0 | 1 | unconstrained_joint_Brier | False |
| outer_4 | 30 | LocalEndpointJointConstrained | 0.85 | 2 | 0 | 1 | fallback_no_feasible_candidate | True |
| all_development_candidate | 7 | Fixed | 0.45 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| all_development_candidate | 7 | Adaptive | 0.3 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| all_development_candidate | 7 | LocalEndpoint | 0.65 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| all_development_candidate | 7 | LocalEndpointAdaptive | 0.65 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| all_development_candidate | 30 | Fixed | 0.8 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| all_development_candidate | 30 | Adaptive | 0.7 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| all_development_candidate | 30 | LocalEndpoint | 0.9 | 0 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| all_development_candidate | 30 | LocalEndpointAdaptive | 0.85 | 2 | 0 | 1 | primary_Brier_then_smaller_gamma_then_smaller_a | NA |
| all_development_candidate | 7 | LocalEndpointQuality | 0.65 | 0 | 0.9 | 1 | anchor_then_Brier_smaller_eta_larger_rho | NA |
| all_development_candidate | 30 | LocalEndpointQuality | 0.85 | 2 | 0 | 1 | anchor_then_Brier_smaller_eta_larger_rho | NA |
| all_development_candidate | 7 | LocalEndpointJoint | 0.7 | 0 | 0.9 | 1 | unconstrained_joint_Brier | False |
| all_development_candidate | 7 | LocalEndpointJointConstrained | 0.65 | 0 | 0 | 1 | fallback_no_feasible_candidate | True |
| all_development_candidate | 30 | LocalEndpointJoint | 0.85 | 2 | 0 | 1 | unconstrained_joint_Brier | False |
| all_development_candidate | 30 | LocalEndpointJointConstrained | 0.85 | 2 | 0 | 1 | fallback_no_feasible_candidate | True |

## Attribution and limitations

The unconstrained Joint arm is diagnostic and cannot be promoted post hoc. Comparing it with E3 tests joint retuning; comparing the constrained procedure with Joint tests the added feasibility/adoption policy on the same candidates. Report constraint-induced failure honestly. No new movement information, rare-endpoint deletion or wider search is introduced.

Intervals keep fits fixed and omit refitting uncertainty, shared training, ocean forcing and prior development-set research adaptation. Nested ID exclusion does not make these data an untouched final test. All-development maps are fitted illustrations; outer scores establish comparative evidence.

## Support and geographic strata

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
| 7 | LocalEndpointJoint | 1-9 fitting IDs | 0.0761671 | 20 | 3 | 0.887391 | 20.6359 | 0.982398 | support_stratum |
| 7 | LocalEndpointJoint | 10-49 fitting IDs | 0.0946287 | 115 | 6 | 0.95084 | 23.7219 | 0.866569 | support_stratum |
| 7 | LocalEndpointJoint | 50+ fitting IDs | 0.829204 | 385 | 31 | 0.965368 | 27.7305 | 0.872315 | support_stratum |
| 7 | LocalEndpointJointConstrained | 1-9 fitting IDs | 0.0761671 | 20 | 3 | 0.893877 | 22.7281 | 0.982398 | support_stratum |
| 7 | LocalEndpointJointConstrained | 10-49 fitting IDs | 0.0946287 | 115 | 6 | 0.952292 | 24.4032 | 0.87213 | support_stratum |
| 7 | LocalEndpointJointConstrained | 50+ fitting IDs | 0.829204 | 385 | 31 | 0.965872 | 27.9509 | 0.874347 | support_stratum |
| 7 | LocalEndpointQuality | 1-9 fitting IDs | 0.0761671 | 20 | 3 | 0.886762 | 20.0276 | 0.982398 | support_stratum |
| 7 | LocalEndpointQuality | 10-49 fitting IDs | 0.0946287 | 115 | 6 | 0.952545 | 23.2054 | 0.862702 | support_stratum |
| 7 | LocalEndpointQuality | 50+ fitting IDs | 0.829204 | 385 | 31 | 0.965362 | 27.3803 | 0.870598 | support_stratum |
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
| 30 | LocalEndpointJoint | 1-9 fitting IDs | 0.0810811 | 18 | 3 | 0.988455 | 97.2963 | 0.855771 | support_stratum |
| 30 | LocalEndpointJoint | 10-49 fitting IDs | 0.144507 | 158 | 6 | 0.993701 | 99.2623 | 0.732142 | support_stratum |
| 30 | LocalEndpointJoint | 50+ fitting IDs | 0.774412 | 336 | 31 | 0.994 | 107.04 | 0.764818 | support_stratum |
| 30 | LocalEndpointJointConstrained | 1-9 fitting IDs | 0.0810811 | 18 | 3 | 0.987979 | 98.4 | 0.864572 | support_stratum |
| 30 | LocalEndpointJointConstrained | 10-49 fitting IDs | 0.144507 | 158 | 6 | 0.993574 | 99.4476 | 0.731188 | support_stratum |
| 30 | LocalEndpointJointConstrained | 50+ fitting IDs | 0.774412 | 336 | 31 | 0.994002 | 107.166 | 0.765218 | support_stratum |
| 30 | LocalEndpointQuality | 1-9 fitting IDs | 0.0810811 | 18 | 3 | 0.988455 | 97.2963 | 0.855771 | support_stratum |
| 30 | LocalEndpointQuality | 10-49 fitting IDs | 0.144507 | 158 | 6 | 0.993701 | 99.2623 | 0.732142 | support_stratum |
| 30 | LocalEndpointQuality | 50+ fitting IDs | 0.774412 | 336 | 31 | 0.994 | 107.04 | 0.764818 | support_stratum |
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
| 7 | LocalEndpointJoint | coastal grid polygon | 0.189189 | 122 | 7 | 0.93618 | 26.4943 | 0.904288 | boundary_stratum |
| 7 | LocalEndpointJoint | offshore grid polygon | 0.810811 | 384 | 30 | 0.963158 | 26.8846 | 0.874525 | boundary_stratum |
| 7 | LocalEndpointJointConstrained | coastal grid polygon | 0.189189 | 122 | 7 | 0.939626 | 27.9115 | 0.904743 | boundary_stratum |
| 7 | LocalEndpointJointConstrained | offshore grid polygon | 0.810811 | 384 | 30 | 0.963648 | 27.0554 | 0.877146 | boundary_stratum |
| 7 | LocalEndpointQuality | coastal grid polygon | 0.189189 | 122 | 7 | 0.937167 | 25.8215 | 0.900444 | boundary_stratum |
| 7 | LocalEndpointQuality | offshore grid polygon | 0.810811 | 384 | 30 | 0.963061 | 26.566 | 0.873215 | boundary_stratum |
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
| 30 | LocalEndpointJoint | coastal grid polygon | 0.189189 | 100 | 7 | 0.993149 | 110.887 | 0.756439 | boundary_stratum |
| 30 | LocalEndpointJoint | offshore grid polygon | 0.810811 | 336 | 30 | 0.993591 | 103.782 | 0.770044 | boundary_stratum |
| 30 | LocalEndpointJointConstrained | coastal grid polygon | 0.189189 | 100 | 7 | 0.992839 | 111.527 | 0.76021 | boundary_stratum |
| 30 | LocalEndpointJointConstrained | offshore grid polygon | 0.810811 | 336 | 30 | 0.993595 | 103.897 | 0.770257 | boundary_stratum |
| 30 | LocalEndpointQuality | coastal grid polygon | 0.189189 | 100 | 7 | 0.993149 | 110.887 | 0.756439 | boundary_stratum |
| 30 | LocalEndpointQuality | offshore grid polygon | 0.810811 | 336 | 30 | 0.993591 | 103.782 | 0.770044 | boundary_stratum |

These descriptive strata do not select models. Endpoint category probability, event, hit and Brier contributions reconcile with complete outcomes. Rho=1 does not guarantee rare endpoints remain inside the region. All zero-probability truths are scored.

## Pair-weighted sensitivity

| horizon_days | model | brier | region90_cells | region90_hit | region90_mass | zero_true_probability | outside_local_union | evaluable_ids | evaluable_pairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | Adaptive | 0.933234 | 33.342 | 0.948818 | 0.903161 | 0.000675925 | 0.00141779 | 385 | 303288 |
| 7 | B2 | 0.929001 | 18.2258 | 0.87439 | 0.908146 | 0.0208218 | 0.00141779 | 385 | 303288 |
| 7 | Fixed | 0.93824 | 42.0308 | 0.955188 | 0.902729 | 0.000675925 | 0.00141779 | 385 | 303288 |
| 7 | LocalEndpoint | 0.936574 | 26.8208 | 0.935705 | 0.9041 | 0.00141779 | 0.00141779 | 385 | 303288 |
| 7 | LocalEndpointAdaptive | 0.936236 | 26.5538 | 0.936094 | 0.904249 | 0.00141779 | 0.00141779 | 385 | 303288 |
| 7 | LocalEndpointJoint | 0.936242 | 26.2302 | 0.935932 | 0.904212 | 0.00141779 | 0.00141779 | 385 | 303288 |
| 7 | LocalEndpointJointConstrained | 0.936236 | 26.5538 | 0.936094 | 0.904249 | 0.00141779 | 0.00141779 | 385 | 303288 |
| 7 | LocalEndpointQuality | 0.934896 | 25.8652 | 0.935339 | 0.904525 | 0.00141779 | 0.00141779 | 385 | 303288 |
| 30 | Adaptive | 0.98911 | 127.33 | 0.865839 | 0.900953 | 0.0109406 | 0.0335653 | 337 | 268998 |
| 30 | B2 | 0.994751 | 62.6083 | 0.663726 | 0.905589 | 0.174589 | 0.0335653 | 337 | 268998 |
| 30 | Fixed | 0.989841 | 133.549 | 0.869111 | 0.900895 | 0.0109406 | 0.0335653 | 337 | 268998 |
| 30 | LocalEndpoint | 0.987851 | 102.247 | 0.838805 | 0.901526 | 0.0335653 | 0.0335653 | 337 | 268998 |
| 30 | LocalEndpointAdaptive | 0.987517 | 102.384 | 0.84133 | 0.901286 | 0.0335653 | 0.0335653 | 337 | 268998 |
| 30 | LocalEndpointJoint | 0.98751 | 102.18 | 0.841226 | 0.90127 | 0.0335653 | 0.0335653 | 337 | 268998 |
| 30 | LocalEndpointJointConstrained | 0.987517 | 102.384 | 0.84133 | 0.901286 | 0.0335653 | 0.0335653 | 337 | 268998 |
| 30 | LocalEndpointQuality | 0.98751 | 102.18 | 0.841226 | 0.90127 | 0.0335653 | 0.0335653 | 337 | 268998 |

Secondary weights did not influence selection.

## Engineering verification

- Independent audit: 26 fitting roles; 20450 candidate identities; 17229125 candidate ID-origin records.
- Reconstruction errors: {'probability': 1.6653345369377348e-16, 'candidate': 6.661338147750939e-16, 'score': np.float64(4.440892098500626e-16), 'summary': np.float64(3.694822225952521e-13), 'support': 3.552713678800501e-15, 'weight': 3.3306690738754696e-16, 'category': np.float64(4.440892098500626e-16)}.
- Six legacy controls reproduce S3 E3 selected matrices, parameters, common cases, weights and point metrics.
- All candidate results are persisted in per-role partitions; constraints, rejection reasons and both fallback branches are explicit.
- Plan/config, input/source including entrypoint and outer predictions are fingerprinted. Final-test/canonical trajectory reads are zero.
- Fresh replay receipt records numerical and image identity separately from predictive acceptance.

## Visual comparison

Fixed support/geometry illustration roster: [('high_support', 44744), ('low_support', 44742), ('coastal', 44382)].

![model_comparison.png](model_comparison.png)

![quality_and_region_differences.png](quality_and_region_differences.png)

![inner_feasible_candidates_7d.png](inner_feasible_candidates_7d.png)

![inner_feasible_candidates_30d.png](inner_feasible_candidates_30d.png)

![constraints_and_fallback.png](constraints_and_fallback.png)

![parameter_stability.png](parameter_stability.png)

![actual_borrowing_weights.png](actual_borrowing_weights.png)

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
