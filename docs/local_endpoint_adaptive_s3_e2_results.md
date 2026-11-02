# Step 3 E2 — Adaptive LocalEndpoint: results

**Engineering status:** independent development, primary execution, audit, visual review and fresh full replay complete. All 186 numerical tables reproduced within absolute 1e-12 and all 13 PNG figures were byte-identical. Scientific retention and Step 3 closure remain user decisions.

**Primary:** `local_endpoint_adaptive_s3_e2_20261030T135819_234829Z`. **Replay:** `local_endpoint_adaptive_s3_e2_20261030T140527_283926Z`. **Resource pilot:** `local_endpoint_adaptive_s3_e2_pilot_20261030T135749_412099Z`.

Read the [approved plan](local_endpoint_adaptive_s3_e2_plan.md), [sealed full report](../results/runs/local_endpoint_adaptive_s3_e2_20261030T135819_234829Z/REPORT.md), [visual comparison](../results/runs/local_endpoint_adaptive_s3_e2_20261030T135819_234829Z/review.html), [primary metrics](../results/runs/local_endpoint_adaptive_s3_e2_20261030T135819_234829Z/summary.csv) and [difference intervals](../results/runs/local_endpoint_adaptive_s3_e2_20261030T135819_234829Z/paired_differences.csv).

## 1. Decision supported by this experiment

The adaptive weight is correctly implemented and changes forecasts, but it does not establish an overall quality-preserving replacement for the retained models at both horizons.

- **7 days:** no Brier benefit over LocalEndpoint. Brier increases by 0.000816; K90 decreases by only 0.14 cell and H90 increases by 0.046 percentage points, with no supported coverage improvement. Three of five outer selections choose gamma=0. The all-development illustrative fit chooses the original constant LocalEndpoint exactly.
- **30 days:** a small Brier and coverage improvement over LocalEndpoint is supported by the predeclared conditional screens: Brier decreases by 0.000299 and actual hits increase by 0.553 percentage points. Mean K90 increases by 0.66 cell (0.63%). This passes the coverage-preserving adaptation-gain criterion, but not the stronger no-region-expansion criterion against LocalEndpoint.
- **Relative to Fixed:** the 30-day adaptive local model improves Brier and uses 21.30% fewer cells, but its point hit rate is 0.750 percentage points lower. Coverage non-deterioration is not established. At 7 days the point hit deficit is 1.719 percentage points and the adjusted Brier support screen also fails.

Neither horizon passes the full Fixed-based quality/region upgrade screen, so neither passes the combined preferred-adaptive-candidate criterion. Retain the complete E2 result for review, including the modest 30-day trade-off and the negative 7-day result. Do not automatically replace both LocalEndpoint models or expand the parameter search.

## 2. Frozen prediction and evaluation target

Where Things End Up: a future destination distribution from an arbitrary qualified time when the object is already inside the specified origin cell. Retain cleaned v7, annual pooling, 1-degree cells, separate 7/30-day direct estimates, R-origin donors and absorbing E for first observed exit from D. No new hourly path transfer, new land rule, cleaning or eligibility change was made.

B2 and the neighbour/global references retain raw qualified-pair frequencies. Primary scoring averages times within each held-out drifter/cell, gives drifters equal weight within the cell, then gives evaluated cells equal weight. This remains the E3/E4/S3 E1 target, rather than the historical pair-weighted evaluation.

Standard complete-distribution Brier is `1 + sum_j p_j^2 - 2*p_y`. All models use the same 90% nominal region with cutoff ties included, complete tails retained, and E included in probability/hits but excluded from geographic K90. Unsupported rows have no standard score and are reported separately. A nominal 90% mass is not a promise of 90% actual hits.

The 7-day population is 303,288 pairs, 385 IDs and 4,451 ID-cell units; the 30-day population is 268,998 pairs, 337 IDs and 3,974 units. The common evaluated set has 37 origin cells, all supported. Seventeen other indexed origins have no eligible evaluation cases; their performance remains unknown.

## 3. Five-model held-out comparison

| Days | Model | Brier | Mean K90 | H90 |
|---|---|---:|---:|---:|
| 7 | B2 | 0.981297 | 17.56 | 74.84% |
| 7 | Fixed | 0.962457 | 42.71 | 89.96% |
| 7 | Adaptive | 0.966486 | 37.55 | 88.57% |
| 7 | LocalEndpoint | 0.958288 | 27.36 | 88.19% |
| 7 | LocalEndpointAdaptive | 0.959104 | 27.22 | 88.24% |
| 30 | B2 | 1.017814 | 56.57 | 50.28% |
| 30 | Fixed | 0.994931 | 133.86 | 77.59% |
| 30 | Adaptive | 0.995303 | 130.93 | 77.74% |
| 30 | LocalEndpoint | 0.993751 | 104.68 | 76.28% |
| 30 | LocalEndpointAdaptive | 0.993452 | 105.34 | 76.84% |

These are nested whole-ID development results. Brier is not percentage accuracy. K90 is a weighted mean count of geographic cells, not a single map's integer footprint or square-kilometre area.

## 4. Differences, uncertainty and declared acceptance

All differences are LocalEndpointAdaptive minus reference. Hit differences use percentage points. Intervals below are ordinary 95% conditional paired-ID intervals.

| Days | Reference | Delta Brier [95% interval] | Delta K90 | Relative K90 | Delta H90 [95% interval], pp |
|---|---|---|---:|---:|---|
| 7 | LocalEndpoint | +0.000816 [-0.000112, +0.002130] | -0.1408 | -0.51% | +0.0457 [-0.0670, +0.1905] |
| 7 | Fixed | -0.003354 [-0.006458, +0.000218] | -15.4943 | -36.28% | -1.7191 [-2.7125, -0.6304] |
| 30 | LocalEndpoint | -0.000299 [-0.000425, -0.000159] | +0.6608 | +0.63% | +0.5526 [+0.2178, +0.9131] |
| 30 | Fixed | -0.001479 [-0.002449, -0.000593] | -28.5173 | -21.30% | -0.7504 [-2.7536, +1.1994] |

The 10,000 positive whole-ID multiplier draws use PCG64 Exp(1), seed 20261031, shared across cells/horizons/models, with fits fixed. The 12 prespecified directional screens use upper quantile 1-0.05/12 for Brier/K90 and lower quantile 0.05/12 for H90. No tolerated scientific coverage loss was introduced.

| Days | Reference | Adjusted upper Delta Brier | Adjusted upper Delta K90 | Adjusted lower Delta H90, pp |
|---|---|---:|---:|---:|
| 7 | LocalEndpoint | +0.002569 | -0.0770 | -0.1035 |
| 7 | Fixed | +0.001438 | -15.3543 | -3.0465 |
| 30 | LocalEndpoint | -0.000099 | +0.7694 | +0.1085 |
| 30 | Fixed | -0.000327 | -27.9473 | -3.4011 |

The 30-day LocalEndpoint contrast passes the Brier and H90 conditions but expands K90. The 30-day Fixed contrast passes Brier and K90, but fails H90. A coverage interval crossing zero is not proof of non-deterioration. The 7-day contrast does not support improvement over LocalEndpoint; its positive point Brier difference should not be called proven harm because its interval crosses zero.

These approximate conditional screens omit model refitting, overlapping-training dependence, previous development-set adaptation and common ocean forcing. The final-test set remains locked, so the result is development evidence rather than an independent deployment claim.

## 5. Did the adaptive mechanism actually operate?

The fitted neighbour reference is unchanged. For each fitting role/horizon/cell, L is the number of distinct local IDs; M is the union of distinct neighbour IDs. Repeated pairs and visits to several neighbouring cells do not increase either ID count beyond one within that context. Local/donor overlap is retained and reported, not treated as independent observations.

The weight is `lambda = a*z^gamma/(1-a+a*z^gamma)`, where `z=(M/L)/median(M/L)` uses fitting IDs only. Raw pairs still determine both probability distributions. The retained global Adaptive remains the old pair-count-based B2/B1 model.

| Days | Outer a values | Outer gamma values | All-development a / gamma |
|---|---|---|---|
| 7 | 0.60, 0.70, 0.70, 0.60, 0.65 | 0.5, 0, 0, 0.5, 0 | 0.65 / 0 |
| 30 | 0.85, 0.90, 0.90, 0.90, 0.85 | 2, 2, 2, 2, 2 | 0.85 / 2 |

At 30 days the all-development actual neighbour weights range from 59.16% to 99.95%, rather than the original constant 90%. Thirty-six of 37 supported rows differ from the constant model with the same a. At 7 days the illustrative model has gamma=0 and exactly matches LocalEndpoint, explaining why its maps are identical even though the outer validation scores differ: two outer folds selected gamma=0.5.

The 30-day gamma lies at the upper edge of the approved grid. This does not prove that a larger gamma would help or identify a global optimum. No post-result grid expansion was performed.

## 6. Where the changes occurred and what weights cannot fix

The predeclared descriptive strata do not show a universal gain for low-support cells. At 7 days, the 1-9 fitting-ID stratum's Brier rises from 0.879911 to 0.893877; the middle/high-support strata improve slightly. The coastal stratum also worsens in Brier. These subsets explain the aggregate trade-off; they are not new tuning rules or independent causal tests.

At 30 days, offshore Brier decreases from 0.993964 to 0.993595 and hits increase from 76.30% to 77.03%; coastal Brier is almost unchanged and hits decrease from 76.20% to 76.02%. The positive aggregate result therefore does not mean every spatial/support category benefits.

The held-out truth lies outside the union of local B2 and neighbour support for 0.293% of primary weight at 7 days and 5.604% at 30 days. No mixing weight between these two distributions can give those missing destinations positive probability. This diagnostic identifies a limit of the information available to this estimator; those cases remain in scoring and do not authorise a new model or donor expansion.

## 7. Visual outputs

The [browser report](../results/runs/local_endpoint_adaptive_s3_e2_20261030T135819_234829Z/review.html) includes 13 inspected figures: the five-model comparison, differences/intervals, applied weights, three per-cell metric comparisons, parameter stability, and six five-model probability maps.

Illustration cells were fixed from fitting support and geometry before outer fitting: high support 44744, low support 44742, coastal 44382. All candidate maps use complete distributions, common colour scales and unchanged 90% outlines. They show all-development fits and cannot replace held-out performance. The 7-day LocalEndpoint and adaptive-local maps coincide because the final illustrative selection chose gamma=0.

## 8. Engineering evidence and reproduction

- Fresh replay `local_endpoint_adaptive_s3_e2_20261030T140527_283926Z` took 392.80 seconds; all 186 numeric tables and 13 figure hashes matched the primary run. See the [replay verification](../provenance/runs/local_endpoint_adaptive_s3_e2_20261030T140527_283926Z/verification.json).
- 123 relevant tests passed, including 14 new E2 tests. The synthetic tests check exact gamma-zero nesting, hand-calculated weights, support unions/overlap, raw-count preservation, no-donor/unsupported branches, fold isolation, candidate scores, region/E semantics and retained-control equivalence.
- The independent audit reconstructs 26 fitting roles, 7,400 candidate identity/horizon/role entries, 6,234,500 candidate ID-cell rows and 109,395 grouped held-out cases using separate Counter/set and probability calculations.
- Maximum independent numerical discrepancy is below 1e-12; the largest aggregate difference is approximately 3.7e-13.
- All 24 selected matrix files for B2, Fixed, Adaptive and LocalEndpoint reproduce S3 E1, alongside their selected parameters, case weights and held-out metrics.
- The primary run took 392.28 seconds, peaked at 2.55 GiB RSS and generated about 82.65 MB before the final seal. Resource limits were respected.
- Approved plan/config, relevant source including the entrypoint, inputs, ID roles and outer predictions/support are hashed and snapshotted. No canonical or final-test trajectories were read, and no read/write guard denial occurred.

Reproduce using the project `.venv`, with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1`:

```sh
.venv/bin/python -m data3001.modelling.baselines.run_local_endpoint_adaptive_s3_e2 --preflight
.venv/bin/python -m data3001.modelling.baselines.run_local_endpoint_adaptive_s3_e2 --pilot-run <successful_pilot_id>
.venv/bin/python -m data3001.modelling.baselines.run_local_endpoint_adaptive_s3_e2 --pilot-run <successful_pilot_id> --replay-of <primary_run_id>
```

The runner verifies the locked plan/config/source identities and input receipts. A new command creates a new immutable run; do not edit sealed artifacts. Code, audit and report live in the isolated `local_endpoint_adaptive_s3_e2` modules. No unrelated refactor, old stopped-run restart, final-test evaluation, commit or push was performed.
