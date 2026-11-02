# Step 3 E1 — Local Spatial Borrowing: Results

**Engineering status:** independent development, primary execution, audit, visual review and fresh full replay complete. All 212 numerical tables reproduced within absolute 1e-12. Scientific retention and stage closure await user review.

**Primary run:** `spatial_borrowing_s3_e1_20261030T114538_900248Z`. **Replay:** `spatial_borrowing_s3_e1_20261030T115158_511096Z`. **Prepared input:** `spatial_borrowing_s3_e1_input_20261030T113714_822569Z`. Read the [approved plan](spatial_borrowing_s3_e1_plan.md), [full report](../results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/REPORT.md), [visual comparison](../results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/review.html), [primary verification](../provenance/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/verification.json) and [handoff audit](../provenance/reviews/spatial_borrowing_s3_e1_20261030T114538_900248Z_audit.json).

## 1. Finding for Where Things End Up

LocalEndpoint has the lowest primary Brier of the five models at both horizons. Compared with Fixed, it reduces the mean number of cells in the unchanged nominal-90% region by 35.95% at 7 days and 21.80% at 30 days. Actual hits, however, fall by 1.76 and 1.30 percentage points. It is a promising probability-estimation comparison, not an established improvement without loss of coverage.

LocalDisplacement improves on raw B2, but has worse Brier and fewer actual hits than Fixed, Adaptive and LocalEndpoint at both horizons. Its smaller region does not pass the approved quality screen. The main spatial hypothesis is not supported as an upgrade over Fixed under this definition.

Retain the complete five-model comparison as the first Step 3 benchmark, including the negative result. A benchmark records the experiment and its reproducible reference results; it does not imply that its primary candidate won. Model selection and Step 3 closure remain separate user decisions.

## 2. Model and evaluation definitions

The prediction starts at an arbitrary qualified time when an object is already in its origin cell. Inputs remain cleaned v7 annual-pooled data, the frozen R/D geometry, 1-degree cells, and separate direct 7/30-day stopped targets. Every eligible hourly pair is retained for raw-frequency fitting. Initial velocity, season, finer grids and recursive propagation are outside this comparison.

Let `p_i` be the fitted B2 row and `q_global` the raw B1 reference. Each horizon and selection role uses the same finite grid `a = 0, 0.05, ..., 1`:

- B2: `p_i`.
- Fixed: `(1-a)*p_i + a*q_global`.
- Adaptive: `(1-lambda_i)*p_i + lambda_i*q_global`, where `lambda_i = m*a / ((1-a)*N_i + m*a)`; `N_i` is the local fitting-pair count and `m` its fitting-only positive-row median. Endpoint values are defined explicitly.
- LocalEndpoint: `(1-a)*p_i + a*q_endpoint_i`, pooling raw qualified fitting pairs from the eight adjacent cells, excluding self. Donors must actually start in R.
- LocalDisplacement: `(1-a)*p_i + a*(v_i + r_i*p_i)`. Translate each donor's whole hourly path by the donor-to-target cell-centre offset. The vector `v_i` contains valid translated outcomes with their original donor weights; `r_i` is the failed-transfer fraction. Thus `sum(v_i)+r_i=1` and the effective spatial weight is `a*(1-r_i)`.

The translation preserves subcell offsets and longitude/latitude increments, not exact geodesic distance or azimuth. Both land masks and every intervening hourly segment inside D are checked. The first observed outside-D point is absorbing E after a valid preceding path. Invalid transfer weights return to B2 without deleting donors or renormalising survivors. An unsupported target B2 row remains unsupported for every model; neighbouring information does not rescue it. No-neighbour supported rows use B2.

The loss is unchanged standard multiclass Brier:

`BS(p,y) = 1 + sum_j(p_j^2) - 2*p_y`, with outcomes covering indexed D cells and E.

There is no spatial penalty or combined loss. A zero-probability true outcome is scored normally. Primary evaluation averages eligible times within each ID/cell, IDs equally within cell, then cells equally. All five models and inner parameter searches use this same E3/E4 target. Original-pair-weighted scores remain a secondary sensitivity view.

Five outer whole-ID groups and four inner groups give 26 fitting roles and 4,250 candidate/horizon identities. All support statistics and references use fitting IDs only. Outer predictions are frozen before all-development illustration tuning. The 517 locked final-test trajectories remain unread.

## 3. Held-out benchmark

| Days | Model | Brier, lower is better | Mean 90% geographic cells | Actual hits |
|---|---|---:|---:|---:|
| 7 | B2 | 0.981297 | 17.56 | 74.84% |
| 7 | Fixed | 0.962457 | 42.71 | 89.96% |
| 7 | Adaptive | 0.966486 | 37.55 | 88.57% |
| 7 | LocalEndpoint | 0.958288 | 27.36 | 88.19% |
| 7 | LocalDisplacement | 0.975131 | 23.13 | 82.20% |
| 30 | B2 | 1.017814 | 56.57 | 50.28% |
| 30 | Fixed | 0.994931 | 133.86 | 77.59% |
| 30 | Adaptive | 0.995303 | 130.93 | 77.74% |
| 30 | LocalEndpoint | 0.993751 | 104.68 | 76.28% |
| 30 | LocalDisplacement | 1.007012 | 96.17 | 69.96% |

Source: [summary.csv](../results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/summary.csv). These are weighted averages, not the integer size of one displayed map or square-kilometre area. Brier is not percentage accuracy. E contributes probability and outcome coverage but is not a geographic cell.

The same 37 origin cells are evaluated for every model. At 7 days the population is 385 IDs, 4,451 ID-cell units and 303,288 hourly pairs; at 30 days it is 337 IDs, 3,974 units and 268,998 pairs. All eligible validation cases have training support. Seventeen of the 54 indexed origins have no eligible evaluation cases, so their predictive performance is unknown.

The nominal region level remains 90% throughout; complete probability tails remain stored. LocalEndpoint's issued masses average 90.41% / 90.20%, while actual hits are 88.19% / 76.28%. LocalDisplacement's issued masses average 90.55% / 90.16%, while actual hits are 82.20% / 69.96%. Concentration alone is not calibration.

## 4. Differences and acceptance

All differences below are spatial model minus Fixed. Intervals are ordinary conditional 95% paired whole-ID multiplier intervals.

| Days | Model | Brier difference [95% interval] | Cell-count change | Relative cell-count change | Hit change [95% interval], percentage points |
|---|---|---|---:|---:|---|
| 7 | LocalEndpoint | -0.004170 [-0.006613, -0.001765] | -15.35 | -35.95% | -1.76 [-2.75, -0.68] |
| 30 | LocalEndpoint | -0.001180 [-0.002165, -0.000310] | -29.18 | -21.80% | -1.30 [-3.32, +0.70] |
| 7 | LocalDisplacement | +0.012674 [+0.007455, +0.017127] | -19.58 | -45.85% | -7.75 [-9.10, -6.45] |
| 30 | LocalDisplacement | +0.012081 [+0.009780, +0.014137] | -37.68 | -28.15% | -7.63 [-9.52, -5.79] |

LocalEndpoint's Brier improvement has descriptive interval support. Its 7-day coverage loss also has descriptive support. At 30 days the hit-difference interval crosses zero; this is not proof of non-deterioration. LocalEndpoint was a secondary comparison, so these are not the primary multiplicity-adjusted upgrade tests.

For the primary LocalDisplacement-minus-Fixed screen, adjusted upper Brier bounds are +0.017831 / +0.014559; adjusted lower hit bounds are -9.42 / -9.98 percentage points. Both horizons fail the Brier and coverage requirements despite clearly smaller regions. Neither qualifies as a quality-preserving or smaller-region upgrade.

The prespecified mechanism comparison also favours LocalEndpoint over LocalDisplacement: displacement-minus-endpoint Brier is +0.016843 [0.009555, 0.023067] at 7 days and +0.013261 [0.010904, 0.015378] at 30 days. Actual hits fall by 5.99 / 6.32 percentage points. This contrast includes both alignment and its geometry/fallback safeguard; it does not isolate a pure physical mechanism.

All intervals use 5,000 paired PCG64 Exp(1) whole-ID multipliers, seed 20261030, with fits fixed. Primary screens use directional 0.05/6 tails for three metrics at two horizons. They omit refitting, overlapping-training dependence, prior research adaptation and shared ocean forcing. These remain development results.

## 5. What happened inside the spatial models

The spatial models used nonzero borrowing. Outer LocalEndpoint weights are 0.65-0.70 at 7 days and 0.95 at 30 days. LocalDisplacement uses 0.60-0.70 at 7 days and 1.00 at 30 days. All-development illustration weights are 0.65 / 0.90 for LocalEndpoint and 0.60 / 1.00 for LocalDisplacement. These illustration weights do not replace outer fitted predictions.

Under the primary held-out weights, LocalDisplacement's failed-transfer fraction averages 19.12% / 24.48%; effective spatial borrowing averages 52.98% / 75.52%. Failed weight really returns to B2. Initial R/D exclusion contributes approximately 9.28% / 9.23%, common-mask land-segment crossings 5.96% / 10.13%, and segment-mask disagreement 1.68% / 3.07%. The remaining failures are land points or point-mask disagreement. Source gaps and missing continuation do not occur in this prepared empirical set, although their semantics are tested.

Whole-cell mean all-development fallback tables in the run use a different descriptive weighting; they must not be substituted for these held-out-weighted numbers.

LocalDisplacement improves Brier versus Fixed in only 6/37 cells at each horizon; LocalEndpoint improves in 23/37 and 21/37. Low-support and coastal strata show particularly weak displacement results. For coastal grid polygons at 30 days, Brier is 1.052452 for LocalDisplacement, 1.000048 for Fixed and 0.992836 for LocalEndpoint. This locates the difficulty; it does not prove fallback is its sole cause.

The Brier decomposition explains why a visibly concentrated map can lose. At 7 days versus Fixed, LocalDisplacement increases mean probability assigned to the realised outcome by 0.015080, but increases mean `sum(p_j^2)` by 0.042833. The latter exceeds twice the former, producing a net Brier increase of 0.012674. At 30 days the corresponding terms are +0.003277 and +0.018635, producing +0.012081. This is an arithmetic explanation, not an independently identified causal mechanism.

The true-outcome zero-probability rates are 0.65% / 8.32% for LocalDisplacement, 0.29% / 5.60% for LocalEndpoint, and 0.15% / 1.49% for Fixed. All such cases are retained in scoring. The observed targets contain no E, but translations generate 49 / 627 donor exit records before fitting-role aggregation. Their mean predicted E probability under validation weights is approximately 0.0044% / 0.0517%. Exit calibration therefore remains empirically unvalidated.

The historical favourable motion-borrowing result used a different alignment/guarding formulation and an earlier evaluation target. The current result neither reproduces that old experiment nor proves spatial motion sharing can never work. It rejects treating this particular guarded grid-transfer estimator as an automatic improvement over Fixed.

## 6. Visual review

- [Five-model comparison](../results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/model_comparison.png) and [paired differences](../results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/quality_and_region_differences.png).
- [Per-cell Brier changes](../results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/per_cell_brier.png) and [effective borrowing](../results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/effective_borrowing.png).
- Six five-model maps: high-support origin 44744, low-support origin 44742, and coastal origin 44382 at both horizons. The minimum 7/30-day fitting-ID supports are 223, 5 and 68. The roster was frozen before score-result review using the approved support/coastline rules.
- [Path-transfer examples](../results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/path_transfer_examples.png) illustrate the geometry operation, not a physical simulation. The deterministic outside-R example has an unsupported target row; it demonstrates rejection, not an issued B2 fallback forecast. B2 fallback applies only to supported target rows. The real audit separately checks resolved in-D, resolved E and every failure class present.

Maps show all-development illustrative fits with a common scale within each comparison and fixed 90% outlines. Held-out scores establish predictive evidence. Full low-probability tails are drawn/stored; no tail clipping improves the reported metrics.

## 7. Engineering audit and reproduction

The numerical experiment, provenance, rendering and replay receipts are recorded separately. No model grid, data selection or outcome definition was changed in response to results. An initial attempt was stopped to fix the missing command-entry source fingerprint; another reached numerical audit but failed at the Markdown report interface. Those attempts remain excluded from the benchmark and retained for traceability.

Verification passed:

- 96 targeted and shared-regression tests passed, including 20 new S3 tests. Report-table rendering was separately checked after repairing its interface.
- Independent reconstruction checked 26 fitting roles, 4,250 candidate identities, 3,580,625 candidate ID-cell rows and 109,395 grouped held-out cases. Maximum probability/score errors were below 7e-16; the largest summary aggregation difference was 3.70e-13.
- Literal chronological path checks matched 53 real examples, including six translated exits, every observed outcome/reason class, and synthetic event-ordering cases. All 149,482 grouped donor-count rows reconciled with individual transfer records.
- Twelve selected B2/Fixed matrices and all corresponding held-out weights/metrics reproduced E4. Adaptive was independently retuned under the current target. The saved outer predictions did not change during all-development tuning.
- The 5,000 multiplier draws and difference bounds were independently reproduced. Post-run checks reconstructed common case weights, decision rules, ordinary intervals and the support/boundary-stratum mixture.
- The fresh replay reproduced all 212 numerical tables within absolute 1e-12 and all 11 PNGs byte-for-byte. Final images match the inspected renders. The support-only illustration roster matches its pre-result freeze; local HTML and documentation links resolve.
- Complete source fingerprints include the executable entry point, and 26 source snapshots are retained. Input/code hashes stayed unchanged. No final-test trajectories were read and no guard-denied operation occurred in the successful runs.
- Complete preparation took 36.63 seconds. Primary fitting/evaluation/audit/reporting took 304.53 seconds; replay took 302.01 seconds. Primary peak RSS was about 2.12 GiB and its artifacts about 47.7 MiB, within all approved caps.

The implementation remains under the direct-horizon baselines package, with shared B2/B1/Adaptive and E3 evaluation utilities reused. The old stopped M1 neighbour computation and continuous-model work remain untouched. The [code guide](code_guide.md) explains the reading order; [post-run audit code](../provenance/reviews/audit_spatial_borrowing_s3_e1.py) records the handoff checks.

Reproduce from the sealed prepared input in the project root:

```sh
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 VECLIB_MAXIMUM_THREADS=2 .venv/bin/python -B -m data3001.modelling.baselines.run_spatial_borrowing_s3_e1 --input-run spatial_borrowing_s3_e1_input_20261030T113714_822569Z --replay-of spatial_borrowing_s3_e1_20261030T114538_900248Z
```

This creates a new immutable run; it does not overwrite the benchmark. The matching configuration and source hashes are enforced. Fresh coordinate preparation starts with the input module's `--pilot`, followed by `--pilot-run <new-pilot-id>` under the same caps.

**Next gate:** review the complete benchmark and decide what to retain. No new spatial weighting, alternate alignment, relaxed land rule, additional parameter search or final-test experiment is authorised by these results.
