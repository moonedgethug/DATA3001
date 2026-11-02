# Step 3 E4 — Joint endpoint borrowing: results

**Engineering status:** independent implementation, execution, audit, visual review and fresh full replay complete. Scientific retention and Step 3 closure await user review.

**Primary:** `local_endpoint_joint_s3_e4_20261031T021237_761696Z`. **Replay:** `local_endpoint_joint_s3_e4_20261031T034349_606438Z`. Read the [approved plan](local_endpoint_joint_s3_e4_plan.md), [visual report](../results/deliverables/local_endpoint_joint_s3_e4/review.html), [sealed report](../results/runs/local_endpoint_joint_s3_e4_20261031T021237_761696Z/REPORT.md), [constraint records](../results/runs/local_endpoint_joint_s3_e4_20261031T021237_761696Z/constraint_summary.csv) and [paired differences](../results/runs/local_endpoint_joint_s3_e4_20261031T021237_761696Z/paired_differences.csv).

## Decision

**Neither horizon delivers a quality-preserving improvement.** All ten outer selections (five per horizon) and both all-development selections returned `fallback_no_feasible_candidate`. The constrained forecasts are exactly their freshly fitted LocalEndpointAdaptive anchors. The unconstrained diagnostic improves 7-day Brier but loses coverage; at 30 days its Brier is slightly worse than the local anchor.

| horizon_days | outer_fallbacks | outer_selections | meaningful_outer_forecast_change | preferred_overall_candidate | all_development_fallback |
|---|---|---|---|---|---|
| 7 | 5 | 5 | False | False | True |
| 30 | 5 | 5 | False | False | True |

The primary procedure is LocalEndpointJointConstrained. A fallback retains its LocalEndpointAdaptive anchor; it is not an improvement and does not establish that Fixed quality is preserved. LocalEndpointJoint remains the prespecified unconstrained diagnostic, not a post-hoc replacement candidate. Each horizon and reference must satisfy Brier, coverage and region-size requirements together.

- **7 days, Joint versus LocalEndpointAdaptive:** Brier -0.001049; K90 -0.407; hits -0.2211 percentage points.
- **30 days, Joint versus LocalEndpointAdaptive:** Brier +0.000055; K90 -0.214; hits -0.0886 percentage points.

## Common held-out comparison

| horizon_days | model | brier | region90_cells | region90_hit |
|---|---|---|---|---|
| 7 | Adaptive | 0.966486 | 37.55 | 88.57% |
| 7 | B2 | 0.981297 | 17.56 | 74.84% |
| 7 | Fixed | 0.962457 | 42.71 | 89.96% |
| 7 | LocalEndpoint | 0.958288 | 27.36 | 88.19% |
| 7 | LocalEndpointAdaptive | 0.959104 | 27.22 | 88.24% |
| 7 | LocalEndpointJoint | 0.958054 | 26.81 | 88.02% |
| 7 | LocalEndpointJointConstrained | 0.959104 | 27.22 | 88.24% |
| 7 | LocalEndpointQuality | 0.958162 | 26.43 | 87.84% |
| 30 | Adaptive | 0.995303 | 130.93 | 77.74% |
| 30 | B2 | 1.017814 | 56.57 | 50.28% |
| 30 | Fixed | 0.994931 | 133.86 | 77.59% |
| 30 | LocalEndpoint | 0.993751 | 104.68 | 76.28% |
| 30 | LocalEndpointAdaptive | 0.993452 | 105.34 | 76.84% |
| 30 | LocalEndpointJoint | 0.993507 | 105.13 | 76.75% |
| 30 | LocalEndpointJointConstrained | 0.993452 | 105.34 | 76.84% |
| 30 | LocalEndpointQuality | 0.993507 | 105.13 | 76.75% |

Annual pooled v7, 1-degree cells, direct stopped 7/30-day targets. Training retains raw hourly pair frequencies. Evaluation averages times within ID/origin, IDs within origin, then origins equally. All eight models use the same cases and nominal-90% definition; actual hits are separate. Brier is not percentage accuracy; K90 is a mean geographic cell count, not area.

## Joint model differences

| days | model | reference | Brier | K90 | H90_pp | Brier_95 | H90_95_pp |
|---|---|---|---|---|---|---|---|
| 7 | LocalEndpointJointConstrained | LocalEndpointAdaptive | +0.000000 | +0.000 | +0.0000 | [+0.000000, +0.000000] | [+0.0000, +0.0000] |
| 7 | LocalEndpointJointConstrained | Fixed | -0.003354 | -15.494 | -1.7191 | [-0.006468, +0.000191] | [-2.7052, -0.6419] |
| 7 | LocalEndpointJoint | LocalEndpointAdaptive | -0.001049 | -0.407 | -0.2211 | [-0.001761, -0.000386] | [-0.5220, +0.0337] |
| 7 | LocalEndpointJoint | Fixed | -0.004403 | -15.901 | -1.9402 | [-0.008044, -0.000450] | [-2.9276, -0.8720] |
| 30 | LocalEndpointJointConstrained | LocalEndpointAdaptive | +0.000000 | +0.000 | +0.0000 | [+0.000000, +0.000000] | [+0.0000, +0.0000] |
| 30 | LocalEndpointJointConstrained | Fixed | -0.001479 | -28.517 | -0.7504 | [-0.002451, -0.000589] | [-2.7314, +1.2034] |
| 30 | LocalEndpointJoint | LocalEndpointAdaptive | +0.000055 | -0.214 | -0.0886 | [+0.000009, +0.000112] | [-0.2696, +0.0201] |
| 30 | LocalEndpointJoint | Fixed | -0.001424 | -28.731 | -0.8390 | [-0.002424, -0.000501] | [-2.8489, +1.1453] |

Ordinary intervals above use paired whole-ID multipliers with fits fixed. The primary constrained model additionally faces twelve predeclared directional screens. These are conditional development comparisons, excluding refitting, overlapping training and prior project adaptation. A zero-crossing interval is not proof of non-deterioration.

| horizon_days | reference | metric | difference | adjusted_directional_bound |
|---|---|---|---|---|
| 7 | Fixed | brier | -0.00335364 | +0.00136954 |
| 7 | Fixed | region90_cells | -15.49430032 | -15.35356918 |
| 7 | Fixed | region90_hit | -0.01719111 | -0.03067352 |
| 7 | LocalEndpointAdaptive | brier | +0.00000000 | +0.00000000 |
| 7 | LocalEndpointAdaptive | region90_cells | +0.00000000 | +0.00000000 |
| 7 | LocalEndpointAdaptive | region90_hit | +0.00000000 | +0.00000000 |
| 30 | Fixed | brier | -0.00147899 | -0.00030660 |
| 30 | Fixed | region90_cells | -28.51731018 | -27.94821010 |
| 30 | Fixed | region90_hit | -0.00750421 | -0.03444768 |
| 30 | LocalEndpointAdaptive | brier | +0.00000000 | +0.00000000 |
| 30 | LocalEndpointAdaptive | region90_cells | +0.00000000 | +0.00000000 |
| 30 | LocalEndpointAdaptive | region90_hit | +0.00000000 | +0.00000000 |

| horizon_days | model | reference | conditional_Brier_support | conditional_coverage_preserving | conditional_quality_preserving | conditional_smaller_region | joint_point_benefit | delta_brier | delta_region90_cells | delta_region90_hit |
|---|---|---|---|---|---|---|---|---|---|---|
| 7 | LocalEndpointJointConstrained | Fixed | False | False | False | False | False | -0.0033536421547447 | -15.494300319832714 | -0.0171911096184721 |
| 7 | LocalEndpointJointConstrained | LocalEndpointAdaptive | False | False | False | False | False | 0.0 | 0.0 | 0.0 |
| 30 | LocalEndpointJointConstrained | Fixed | True | False | False | False | False | -0.0014789891165606 | -28.5173101804819 | -0.0075042096845419 |
| 30 | LocalEndpointJointConstrained | LocalEndpointAdaptive | False | False | False | False | False | 3.4416913763379853e-15 | 3.552713678800501e-13 | 2.220446049250313e-16 |

## Internal feasibility and fallback

| role | horizon_days | feasible_anchor | feasible_fixed | feasible_both | feasible_and_Brier | selection_status |
|---|---|---|---|---|---|---|
| outer_0 | 7 | 12 | 0 | 0 | 0 | fallback_no_feasible_candidate |
| outer_0 | 30 | 23 | 0 | 0 | 0 | fallback_no_feasible_candidate |
| outer_1 | 7 | 11 | 0 | 0 | 0 | fallback_no_feasible_candidate |
| outer_1 | 30 | 3 | 0 | 0 | 0 | fallback_no_feasible_candidate |
| outer_2 | 7 | 8 | 0 | 0 | 0 | fallback_no_feasible_candidate |
| outer_2 | 30 | 1 | 0 | 0 | 0 | fallback_no_feasible_candidate |
| outer_3 | 7 | 25 | 0 | 0 | 0 | fallback_no_feasible_candidate |
| outer_3 | 30 | 10 | 0 | 0 | 0 | fallback_no_feasible_candidate |
| outer_4 | 7 | 1 | 0 | 0 | 0 | fallback_no_feasible_candidate |
| outer_4 | 30 | 19 | 0 | 0 | 0 | fallback_no_feasible_candidate |
| all_development_candidate | 7 | 1 | 0 | 0 | 0 | fallback_no_feasible_candidate |
| all_development_candidate | 30 | 2 | 0 | 0 | 0 | fallback_no_feasible_candidate |

The binding obstacle is Fixed coverage: in every selection partition and horizon, all 252 joint candidates satisfy the Fixed size limit, but none satisfies its hit-rate floor. Even the highest-coverage candidate misses the inner Fixed hit rate by 0.21–1.23 percentage points across 7-day outer-training partitions and 0.18–4.95 points at 30 days. These are internal selection deficits, not outer performance estimates. The screen is not failing merely because size and coverage are required together. No `fallback_no_Brier_gain` occurred; feasibility failed first.

Each inner partition first reselects the legacy references. The candidate must preserve both references' H90 and K90. Among feasible candidates, minimum Brier is adopted only if it beats both references; otherwise the fresh local anchor is issued. No numeric historical score enters an inner threshold. Empty feasibility and no-Brier-gain have different recorded reasons. All-development choices are for illustrations, not independent validation.

## Parameters and mechanism

Relative to the E3 LocalEndpointQuality procedure, Joint increases a by 0.05 in all five 7-day outer fits while keeping their gamma and eta unchanged. This slightly strengthens borrowing after similarity reweighting: held-out Brier falls by 0.000108, K90 rises by 0.386 cells and hits recover 0.179 percentage points. That is a small recovery from E3, not preservation of LocalEndpointAdaptive or Fixed coverage. At 30 days Joint selects the same parameters and predictions as E3, so freeing the parameters adds no observed benefit.

| role | horizon_days | model | parameter_a | parameter_gamma | parameter_eta | parameter_rho | selection_status |
|---|---|---|---|---|---|---|---|
| outer_0 | 7 | LocalEndpointAdaptive | 0.6 | 0.5 | 0.0 | 1.0 | primary_Brier_then_smaller_gamma_then_smaller_a |
| outer_0 | 30 | LocalEndpointAdaptive | 0.85 | 2.0 | 0.0 | 1.0 | primary_Brier_then_smaller_gamma_then_smaller_a |
| outer_0 | 7 | LocalEndpointQuality | 0.6 | 0.5 | 0.9 | 1.0 | anchor_then_Brier_smaller_eta_larger_rho |
| outer_0 | 30 | LocalEndpointQuality | 0.85 | 2.0 | 0.0 | 1.0 | anchor_then_Brier_smaller_eta_larger_rho |
| outer_0 | 7 | LocalEndpointJoint | 0.65 | 0.5 | 0.9 | 1.0 | unconstrained_joint_Brier |
| outer_0 | 7 | LocalEndpointJointConstrained | 0.6 | 0.5 | 0.0 | 1.0 | fallback_no_feasible_candidate |
| outer_0 | 30 | LocalEndpointJoint | 0.85 | 2.0 | 0.0 | 1.0 | unconstrained_joint_Brier |
| outer_0 | 30 | LocalEndpointJointConstrained | 0.85 | 2.0 | 0.0 | 1.0 | fallback_no_feasible_candidate |
| outer_1 | 7 | LocalEndpointAdaptive | 0.7 | 0.0 | 0.0 | 1.0 | primary_Brier_then_smaller_gamma_then_smaller_a |
| outer_1 | 30 | LocalEndpointAdaptive | 0.9 | 2.0 | 0.0 | 1.0 | primary_Brier_then_smaller_gamma_then_smaller_a |
| outer_1 | 7 | LocalEndpointQuality | 0.7 | 0.0 | 0.9 | 1.0 | anchor_then_Brier_smaller_eta_larger_rho |
| outer_1 | 30 | LocalEndpointQuality | 0.9 | 2.0 | 0.0 | 1.0 | anchor_then_Brier_smaller_eta_larger_rho |
| outer_1 | 7 | LocalEndpointJoint | 0.75 | 0.0 | 0.9 | 1.0 | unconstrained_joint_Brier |
| outer_1 | 7 | LocalEndpointJointConstrained | 0.7 | 0.0 | 0.0 | 1.0 | fallback_no_feasible_candidate |
| outer_1 | 30 | LocalEndpointJoint | 0.9 | 2.0 | 0.0 | 1.0 | unconstrained_joint_Brier |
| outer_1 | 30 | LocalEndpointJointConstrained | 0.9 | 2.0 | 0.0 | 1.0 | fallback_no_feasible_candidate |
| outer_2 | 7 | LocalEndpointAdaptive | 0.7 | 0.0 | 0.0 | 1.0 | primary_Brier_then_smaller_gamma_then_smaller_a |
| outer_2 | 30 | LocalEndpointAdaptive | 0.9 | 2.0 | 0.0 | 1.0 | primary_Brier_then_smaller_gamma_then_smaller_a |
| outer_2 | 7 | LocalEndpointQuality | 0.7 | 0.0 | 0.9 | 1.0 | anchor_then_Brier_smaller_eta_larger_rho |
| outer_2 | 30 | LocalEndpointQuality | 0.9 | 2.0 | 0.0 | 1.0 | anchor_then_Brier_smaller_eta_larger_rho |
| outer_2 | 7 | LocalEndpointJoint | 0.75 | 0.0 | 0.9 | 1.0 | unconstrained_joint_Brier |
| outer_2 | 7 | LocalEndpointJointConstrained | 0.7 | 0.0 | 0.0 | 1.0 | fallback_no_feasible_candidate |
| outer_2 | 30 | LocalEndpointJoint | 0.9 | 2.0 | 0.0 | 1.0 | unconstrained_joint_Brier |
| outer_2 | 30 | LocalEndpointJointConstrained | 0.9 | 2.0 | 0.0 | 1.0 | fallback_no_feasible_candidate |
| outer_3 | 7 | LocalEndpointAdaptive | 0.6 | 0.5 | 0.0 | 1.0 | primary_Brier_then_smaller_gamma_then_smaller_a |
| outer_3 | 30 | LocalEndpointAdaptive | 0.9 | 2.0 | 0.0 | 1.0 | primary_Brier_then_smaller_gamma_then_smaller_a |
| outer_3 | 7 | LocalEndpointQuality | 0.6 | 0.5 | 0.9 | 1.0 | anchor_then_Brier_smaller_eta_larger_rho |
| outer_3 | 30 | LocalEndpointQuality | 0.9 | 2.0 | 0.5 | 1.0 | anchor_then_Brier_smaller_eta_larger_rho |
| outer_3 | 7 | LocalEndpointJoint | 0.65 | 0.5 | 0.9 | 1.0 | unconstrained_joint_Brier |
| outer_3 | 7 | LocalEndpointJointConstrained | 0.6 | 0.5 | 0.0 | 1.0 | fallback_no_feasible_candidate |
| outer_3 | 30 | LocalEndpointJoint | 0.9 | 2.0 | 0.5 | 1.0 | unconstrained_joint_Brier |
| outer_3 | 30 | LocalEndpointJointConstrained | 0.9 | 2.0 | 0.0 | 1.0 | fallback_no_feasible_candidate |
| outer_4 | 7 | LocalEndpointAdaptive | 0.65 | 0.0 | 0.0 | 1.0 | primary_Brier_then_smaller_gamma_then_smaller_a |
| outer_4 | 30 | LocalEndpointAdaptive | 0.85 | 2.0 | 0.0 | 1.0 | primary_Brier_then_smaller_gamma_then_smaller_a |
| outer_4 | 7 | LocalEndpointQuality | 0.65 | 0.0 | 0.9 | 1.0 | anchor_then_Brier_smaller_eta_larger_rho |
| outer_4 | 30 | LocalEndpointQuality | 0.85 | 2.0 | 0.0 | 1.0 | anchor_then_Brier_smaller_eta_larger_rho |
| outer_4 | 7 | LocalEndpointJoint | 0.7 | 0.0 | 0.9 | 1.0 | unconstrained_joint_Brier |
| outer_4 | 7 | LocalEndpointJointConstrained | 0.65 | 0.0 | 0.0 | 1.0 | fallback_no_feasible_candidate |
| outer_4 | 30 | LocalEndpointJoint | 0.85 | 2.0 | 0.0 | 1.0 | unconstrained_joint_Brier |
| outer_4 | 30 | LocalEndpointJointConstrained | 0.85 | 2.0 | 0.0 | 1.0 | fallback_no_feasible_candidate |
| all_development_candidate | 7 | LocalEndpointAdaptive | 0.65 | 0.0 | 0.0 | 1.0 | primary_Brier_then_smaller_gamma_then_smaller_a |
| all_development_candidate | 30 | LocalEndpointAdaptive | 0.85 | 2.0 | 0.0 | 1.0 | primary_Brier_then_smaller_gamma_then_smaller_a |
| all_development_candidate | 7 | LocalEndpointQuality | 0.65 | 0.0 | 0.9 | 1.0 | anchor_then_Brier_smaller_eta_larger_rho |
| all_development_candidate | 30 | LocalEndpointQuality | 0.85 | 2.0 | 0.0 | 1.0 | anchor_then_Brier_smaller_eta_larger_rho |
| all_development_candidate | 7 | LocalEndpointJoint | 0.7 | 0.0 | 0.9 | 1.0 | unconstrained_joint_Brier |
| all_development_candidate | 7 | LocalEndpointJointConstrained | 0.65 | 0.0 | 0.0 | 1.0 | fallback_no_feasible_candidate |
| all_development_candidate | 30 | LocalEndpointJoint | 0.85 | 2.0 | 0.0 | 1.0 | unconstrained_joint_Brier |
| all_development_candidate | 30 | LocalEndpointJointConstrained | 0.85 | 2.0 | 0.0 | 1.0 | fallback_no_feasible_candidate |

The joint family searches 252 triples with rho=1: a=0:0.05:1, gamma in {0,0.5,1,2}, eta in {0,0.5,0.9}. It changes borrowing strength and the existing overlap-based neighbour allocation together, with no rare-endpoint deletion, extra source, movement transfer or changed loss. Any observed effect must be interpreted as this finite family and selection procedure. An unsuccessful search does not prove all spatial information is exhausted.

## Engineering and visuals

- 26 fitting roles; 20,450 logical candidate identities; 17,229,125 ID-origin candidate records independently reconstructed in partitions.
- All six legacy controls reproduce the previous E3: 36 selected matrices, parameters, common cases, weights and point metrics.
- Maximum independent reconstruction error: 3.69e-13; uncertainty reconstruction error: 1.14e-13.
- Fresh replay: 332 numerical tables within absolute 1e-12, 17 PNG figures byte-identical. All figures visually reviewed and report links verified.
- 356 modelling tests passed, including 16 E4 checks; the 16 E4 tests also passed under the final configuration.
- Primary elapsed 940.32 seconds; replay 864.28 seconds; maximum peak RSS 2.88 GiB.
- Input, approved plan/config, source including entrypoint, and outer-freeze identities verified. Canonical/final-test trajectory reads were zero; no denied operation occurred.
- Fixed support/geometry illustration origins: 44744, 44742 and 44382. Full distributions and nominal-90% boundaries are retained. All-development maps show fitted examples, not held-out predictive proof.

No new grid, relaxed quality margin, candidate promotion, final-test access, scientific stage closure or Git publication was performed. The next decision is user review of the complete comparison and its limitations.
