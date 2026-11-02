# Step 3 E3 — Neighbour Endpoint Quality: results

**Engineering status:** independent development, primary run, audit, visual inspection and fresh full replay complete. All 258 numeric tables reproduce within absolute 1e-12; all 21 PNG figures are byte-identical. Scientific retention and Step 3 closure remain user decisions.

**Primary:** `local_endpoint_quality_s3_e3_20261031T005527_091650Z`. **Replay:** `local_endpoint_quality_s3_e3_20261031T010534_834079Z`. **Pilot:** `local_endpoint_quality_s3_e3_pilot_20261031T005510_842345Z`.

Read the [approved plan](local_endpoint_quality_s3_e3_plan.md), [full report](../results/runs/local_endpoint_quality_s3_e3_20261031T005527_091650Z/REPORT.md), [visual comparison](../results/runs/local_endpoint_quality_s3_e3_20261031T005527_091650Z/review.html), [primary metrics](../results/runs/local_endpoint_quality_s3_e3_20261031T005527_091650Z/summary.csv), [difference intervals](../results/runs/local_endpoint_quality_s3_e3_20261031T005527_091650Z/paired_differences.csv), and [handoff audit](../provenance/reviews/local_endpoint_quality_s3_e3_20261031T005527_091650Z_audit.json).

## 1. Decision supported by the experiment

**E3 does not establish a quality-preserving upgrade at either horizon.**

- **7 days:** relative to LocalEndpointAdaptive, Brier improves by 0.000941 and K90 falls by 0.7922 cells (2.91%), but H90 falls by 0.4001 percentage points. Brier passes the prespecified conditional screen; coverage preservation fails. Against LocalEndpoint, the point Brier gain is only 0.000125 and is not supported by the prespecified bound; hits fall by 0.3544 pp. Against Fixed, the region is 38.13% smaller but hits fall by 2.1192 pp.
- **30 days:** relative to LocalEndpointAdaptive, Brier increases by 0.000055 and H90 falls by 0.0886 pp, while K90 falls by just 0.2141 cells (0.20%). There is no incremental information-quality gain. Better point Brier/hits than LocalEndpoint do not establish an E3 benefit: the unchanged adaptive anchor is better still on those two metrics. Relative to Fixed, hits are 0.8390 pp lower.
- All six reference/horizon comparisons fail the complete quality-preserving screen. Neither horizon qualifies as the preferred overall candidate. Preserve the earlier benchmarks; this experiment does not authorise their replacement or a wider search.

This is a completed finite development experiment, not evidence that all spatial information or endpoint-quality methods have reached a limit.

## 2. Frozen prediction and evaluation definitions

Where Things End Up: predict a stopped destination distribution from an arbitrary qualified time when the object is already in the origin cell. Retain cleaned v7, annual pooling, 1-degree cells, separate direct 7/30-day estimates, eight R-origin neighbours and absorbing first-observed-exit E.

Training retains raw pair frequencies. Primary evaluation averages eligible times within each held-out drifter/origin, gives drifters equal weight within an origin, and gives origins equal weight. Every model uses the same cases and B2 support mask. Seven-day data: 303,288 pairs, 385 IDs and 4,451 ID-cell units. Thirty-day data: 268,998 pairs, 337 IDs and 3,974 units. There are 37 evaluated origins; 17 other indexed origins have no eligible evaluation cases. No supported case was removed for a zero-probability truth.

Standard Brier is `1 + sum_j p_j^2 - 2*p_y` on D plus E. Every region uses nominal mass 0.90 and includes cutoff ties. K90 counts geographic cells, not square-kilometre area; H90 measures actual hits. E participates in probability/hits but not geographic cell count. Complete fitted probabilities are retained. No E outcomes occur in the eligible comparison, so exit calibration remains unvalidated. The final test is unread.

## 3. Six-model held-out results

| Days | Model | Brier | Mean K90 | H90 |
|---|---|---:|---:|---:|
| 7 | B2 | 0.981297 | 17.56 | 74.84% |
| 7 | Fixed | 0.962457 | 42.71 | 89.96% |
| 7 | Adaptive | 0.966486 | 37.55 | 88.57% |
| 7 | LocalEndpoint | 0.958288 | 27.36 | 88.19% |
| 7 | LocalEndpointAdaptive | 0.959104 | 27.22 | 88.24% |
| 7 | LocalEndpointQuality | 0.958162 | 26.43 | 87.84% |
| 30 | B2 | 1.017814 | 56.57 | 50.28% |
| 30 | Fixed | 0.994931 | 133.86 | 77.59% |
| 30 | Adaptive | 0.995303 | 130.93 | 77.74% |
| 30 | LocalEndpoint | 0.993751 | 104.68 | 76.28% |
| 30 | LocalEndpointAdaptive | 0.993452 | 105.34 | 76.84% |
| 30 | LocalEndpointQuality | 0.993507 | 105.13 | 76.75% |

Brier is not percentage accuracy. These are nested whole-ID development scores, not all-development map scores or locked-final-test performance.

## 4. Differences and uncertainty

Every difference is LocalEndpointQuality minus the named reference. Negative Brier/K90 and positive H90 are the preferred directions.

| Days | Reference | Delta Brier | Delta K90 | Relative K90 | Delta H90, pp |
|---|---|---:|---:|---:|---:|
| 7 | LocalEndpointAdaptive | -0.000941 | -0.7922 | -2.91% | -0.4001 |
| 7 | LocalEndpoint | -0.000125 | -0.9330 | -3.41% | -0.3544 |
| 7 | Fixed | -0.004295 | -16.2865 | -38.13% | -2.1192 |
| 30 | LocalEndpointAdaptive | +0.000055 | -0.2141 | -0.20% | -0.0886 |
| 30 | LocalEndpoint | -0.000244 | +0.4467 | +0.43% | +0.4640 |
| 30 | Fixed | -0.001424 | -28.7314 | -21.46% | -0.8390 |

| Days | Reference | Delta Brier [ordinary 95% interval] | Delta H90 [ordinary 95% interval], pp |
|---|---|---:|---:|
| 7 | LocalEndpointAdaptive | -0.000941 [-0.001493, -0.000342] | -0.4001 [-0.6945, -0.1527] |
| 7 | LocalEndpoint | -0.000125 [-0.001259, +0.001287] | -0.3544 [-0.6770, -0.0682] |
| 7 | Fixed | -0.004295 [-0.007570, -0.000650] | -2.1192 [-3.1115, -1.0468] |
| 30 | LocalEndpointAdaptive | +0.000055 [+0.000009, +0.000112] | -0.0886 [-0.2696, +0.0201] |
| 30 | LocalEndpoint | -0.000244 [-0.000370, -0.000114] | +0.4640 [+0.1056, +0.8404] |
| 30 | Fixed | -0.001424 [-0.002424, -0.000501] | -0.8390 [-2.8489, +1.1453] |

Twenty thousand paired positive Exp(1) whole-ID multipliers, PCG64 seed 20261031, share ID weights across cells/horizons/models; fits and within-ID means remain fixed. The 18 prespecified directional screens use upper quantile `1-0.05/18` for Brier/K90 and lower quantile `0.05/18` for H90. Numerical tolerance 1e-12 is not an allowed coverage-loss margin.

At 7 days versus LocalEndpointAdaptive, the adjusted upper Brier bound is -0.000074, but the lower H90 bound is -0.8575 pp. Against LocalEndpoint, the adjusted upper Brier bound is +0.001841. At 30 days versus LocalEndpoint, the positive point H90 change does not pass the stricter declared screen (lower bound -0.0458 pp), and K90 expands. Full bounds and decisions are in the linked CSV files.

These approximate conditional development intervals omit refitting, overlapping-training dependence, common ocean forcing and prior research adaptation. A zero-crossing interval is not proof of non-deterioration. Engineering reproducibility is not final-test validation.

## 5. What the model actually selected

| Training partition | Days | a | gamma | eta | rho |
|---|---:|---:|---:|---:|---:|
| all_development_candidate | 7 | 0.65 | 0 | 0.9 | 1 |
| all_development_candidate | 30 | 0.85 | 2 | 0 | 1 |
| outer_0 | 7 | 0.6 | 0.5 | 0.9 | 1 |
| outer_0 | 30 | 0.85 | 2 | 0 | 1 |
| outer_1 | 7 | 0.7 | 0 | 0.9 | 1 |
| outer_1 | 30 | 0.9 | 2 | 0 | 1 |
| outer_2 | 7 | 0.7 | 0 | 0.9 | 1 |
| outer_2 | 30 | 0.9 | 2 | 0 | 1 |
| outer_3 | 7 | 0.6 | 0.5 | 0.9 | 1 |
| outer_3 | 30 | 0.9 | 2 | 0.5 | 1 |
| outer_4 | 7 | 0.65 | 0 | 0.9 | 1 |
| outer_4 | 30 | 0.85 | 2 | 0 | 1 |

- Every outer selection and both all-development selections use **rho=1**. Halving/removing the weak-unseen contribution was not selected by inner Brier on this grid. It is therefore incorrect to describe this result as an experiment that won by deleting rare new endpoints.
- All five 7-day outer selections use eta=0.9. At 30 days, only outer fold 3 uses eta=0.5; the other four use eta=0. The anchor a/gamma are inherited exactly from the freshly tuned LocalEndpointAdaptive control.
- The selected combined model equals its similarity-only ablation. The gate-only ablation equals the unchanged anchor within numerical tolerance. The observed incremental effect is source similarity reweighting.
- The 30-day all-development illustrative fit uses eta=0/rho=1, reproducing LocalEndpointAdaptive exactly. Its maps can be identical even though the nested validation scores differ: one outer fit used a nonneutral eta.
- Eta=0.9 being selected at 7 days is a grid-boundary observation, not permission to extend the grid or evidence that stronger concentration would preserve coverage.

## 6. Why the smaller region is not a quality-preserving improvement

The similarity rule favours neighbours whose distributions resemble the local empirical row. In the 7-day outer forecasts, relative to the adaptive anchor, the primary-weighted probability assigned to shared common endpoints rises by **2.2822 percentage points**. Shared locally rare endpoints lose **0.6939 pp**, other neighbour-only endpoints lose **1.5170 pp**, and weak-unseen endpoints lose **0.0712 pp** through source reweighting despite rho=1. Local-only mass is unchanged.

The 7-day change gains 0.3625 pp of region hits but loses 0.7626 pp of previous hits, producing the net loss of 0.4001 pp. Shared-rare endpoint hits contribute -0.3038 pp, other neighbour-only hits -0.1781 pp, and shared-common hits +0.0819 pp. At 30 days, gained and lost hits are 0.0305 and 0.1191 pp, respectively. These are weighted event contributions, not percentages of independent drifters.

There are **no additional zero-probability true outcomes** relative to LocalEndpointAdaptive at either horizon. The incremental hit loss comes from which cells lie inside the fixed-90% region after probability redistribution, not newly discarded evaluation cases or a reduced nominal level. Keeping a shared rare endpoint eligible does not guarantee its probability rises after donor reweighting.

This mechanism supports a limited interpretation: the tested overlap rule makes the 7-day forecast more concentrated and improves average Brier, but it does not preserve search-region coverage. The audit found no mismatch between the locked mathematical definitions and their implementation. That finding does not prove the similarity hypothesis is scientifically optimal.

The descriptive 1-9-fitting-ID stratum has a 7-day Brier change of -0.007115 with unchanged point hits, but represents only 7.62% of primary weight. At 30 days the same support band has Brier +0.000475 and hits -0.8801 pp. These are diagnostic subsets, not separately selected models or evidence for a new support-specific rule. Full strata remain in the report and CSV outputs.

## 7. Visual review and reproducibility

The HTML report includes six-model comparisons, difference bounds, selected-setting ablations, parameter stability, neighbour weights, endpoint-category probability/Brier diagnostics, all-origin difference maps and matched complete-distribution maps. The illustration roster remains 44744 / 44742 / 44382, chosen by the previous support/geometry rule. All 21 figures were visually reviewed; all 25 local HTML links resolve.

- **136 relevant tests passed**, including 13 new E3 checks.
- Independent reconstruction checked 26 fitting roles, 7,850 candidate/horizon/role identities, 6,613,625 candidate ID-cell records and 175,032 grouped held-out cases.
- All five retained controls reproduce S3 E2: 30 selected matrices, parameters, common cases, primary weights and point metrics within 1e-12.
- Primary maximum reconstruction error is 3.69e-13; uncertainty reconstruction error is 1.14e-13.
- Primary execution/audit/report: 533.35 seconds. Fresh full replay: 543.97 seconds. Peak RSS: 3.27 GiB. Primary/replay artifacts together: 246.04 MiB, within approved caps.
- Source snapshots include the entrypoint; source, config, approved-plan and input hashes remain unchanged. Outer predictions were frozen before all-development tuning. No canonical/final-test trajectories were read; there were no denied operations.

Reproduce using the project `.venv` and `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1`:

```sh
.venv/bin/python -m data3001.modelling.baselines.run_local_endpoint_quality_s3_e3 --preflight
.venv/bin/python -m data3001.modelling.baselines.run_local_endpoint_quality_s3_e3 --pilot-run <sealed_pilot_id>
.venv/bin/python -m data3001.modelling.baselines.run_local_endpoint_quality_s3_e3 --pilot-run <sealed_pilot_id> --replay-of <primary_run_id>
```

Run IDs and numerical provenance are immutable. The stable deliverable alias points to the audited primary run. No commit/push, final-test access, model replacement or stage closure was performed. The next decision is user review of this trade-off and of whether to retain this candidate as research evidence.
