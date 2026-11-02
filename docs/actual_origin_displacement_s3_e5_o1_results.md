# Step 3 E5 O1 — Exact optimisation trial

**Date:** 1 November 2026 (Australia/Sydney).  
**Status:** CAPACITY_NOT_ESTABLISHED. Calibration acceleration succeeded; extended validation did not complete. The full experiment has not started.

The approved O1 plan remains unchanged. Run: `actual_origin_disp_s3_e5_o1_20261031T131701_288861Z`. [Visual review](../results/deliverables/actual_origin_displacement_s3_e5_o1/review.html).

## Measured bottleneck and acceleration

The eight frozen calibration queries cover 7/30 days and coastal/offshore categories. Instrumentation added 0.55% aggregate elapsed time. The original instrumented kernel spent 40.7% on whole-path land certificates, 37.0% on hourly land-point predicates, 13.8% on hourly land-segment predicates and 8.4% elsewhere.

All numbers below use the same eight queries, complete donor populations and a 2,048-donor batch. These are kernel timings, excluding common input verification, setup, auditing and model selection.

| Implementation | Total seconds | Relative acceleration |
|---|---:|---:|
| Original E5 | 334.395 | 1.00x |
| G1: invariant contexts / numeric domain | 324.138 | 1.03x |
| G2: exact land-component indexes | 111.581 | 3.00x |
| G3: additional conservative time-block proofs | 21.721 | 15.39x |

G2 was triggered by a measured 94.1% predicate share after G1. G3 was triggered by an 86.3% hourly-processing share after G2. The 8,192 batch was also tested, without changing outcomes. The frozen selection is G3 with batch 2,048: its total calibration cost was within 5% of the fastest alternative, so the approved smaller-batch tie rule applied.

True coordinates, all donor pairs and their multiplicities, full-path event ordering, both land masks and failed-donor B2 return are retained. Time-block certificates prove that every included vertex and connecting segment is safe; they do not discard hours. Source arrays and block bounds are reused across horizons, but cross-horizon outcome-prefix reuse was not activated or credited in these timings.

## What matched, and what remains unverified

Each of the six variant/batch combinations compared all **355,418 query–donor outcomes and reason codes** with the original across the eight calibration queries. Every completed comparison matched in process. These are repeated comparisons of the same calibration population, not six independent datasets.

The optimized arrays were still in memory when the later native crash occurred. Consequently the saved-artifact audit cannot independently recompare those optimized arrays. It verifies completed timing records and the code ordering that requires array equality before publishing each record.

47 targeted semantic tests passed: 27 E5/O1 tests, six probability-region tests and 14 E1 input/geometry tests. Fixtures cover true-start differences, block boundaries, full-path certificates, land contact, first exit, missing hours/continuation, invalid/unindexed states, context integrity, cached-score/search parity and checkpoint rejection. These tests do not establish predictive accuracy.

The remaining 50 engineering-validation queries, four additional complete real-data parity comparisons, at least 5,000 independent scalar transfers, real-data score/selection parity, and scoring/control/uncertainty capacity profiling **did not complete**. No full CV Brier, H90 or K90 results are available.

## Native concurrency failure and stop

At 00:57 on 1 November, the process received SIGSEGV during the two-thread comparison. Both worker stacks contain `GEOSPreparedIntersects_r`; the faulting stack includes `MCIndexSegmentSetMutualIntersector` and `SegmentIntersectionDetector`.

The trial used Shapely 2.2.0 / GEOS 3.14.1. Sharing prepared land geometry between these threads was an engineering design error: read-only Python arrays do not make the underlying prepared geometry thread-safe. The native stack is consistent with the upstream documented limitation, [GEOS issue 825](https://github.com/libgeos/geos/issues/825). No post-failure reproduction or geometry retry was attempted.

The approved plan states: “No extra attempt, model grid or new geometry variant is added after a failure.” This rule ended the attempt. A new real-data execution requires a reviewed continuation protocol; the live entry point now rejects accidental replay of this closed approval. The failed version remains in the immutable stage source snapshots. No measured geometry kernel was changed after its benchmarks.

Stage A used 677.18 seconds and stage B used 1,335.17 seconds. The native crash prevented a final monotonic timer flush for C; filesystem/crash timestamps indicate about 22 seconds. C is conservatively charged 60 seconds, giving **34.54 minutes of accounted execution**, below the two-hour cap. Final peak RSS and access counters were not flushed; they are recorded as unavailable, rather than fabricated. Development-only input guards were active throughout the process. The last resource checks did not trigger a memory or storage limit.

## Geometry-only scale estimate

The ledger still contains about 27.37 billion outer query–donor combinations after fold reuse. Applying the selected serial rates to the four horizon/coastal strata gives:

| Scope | Pooled mean-rate diagnostic | Slowest sampled rate plus 2x reserve |
|---|---:|---:|
| Primary geometry only | 250.1 hours | 635.1 hours |
| Geometry plus one fresh geometry replay | 500.1 hours | 1,270.3 hours |

These are coarse extrapolations from **two calibration queries and one origin per horizon/coastal category**. They are not confidence intervals, measured total runtimes or proven lower bounds. Additional origin validation did not complete. Candidate scoring, controls, uncertainty, independent audit, checkpoint I/O and orchestration/reporting are unmeasured and excluded. A defensible complete-run estimate is therefore still unavailable; there is no evidence supporting a one-to-three-day complete run under this implementation.

The immediate engineering recommendation is to retain the demonstrated exact serial optimizations, avoid shared prepared-geometry threads, and review a bounded continuation that persists outcome arrays before concurrency checks. Isolated geometry instances/processes would need their own resource measurement. More substantial exact batching/counting may be needed before committing to full execution. None of these observations establishes that the displacement model improves or worsens prediction.

## Audit and artifacts

- [Sealed trial evidence](../provenance/runs/actual_origin_disp_s3_e5_o1_20261031T131701_288861Z/outputs.json): 231 artifacts verified.
- [Native crash evidence](../provenance/runs/actual_origin_disp_s3_e5_o1_20261031T131701_288861Z/native_crash_evidence.json).
- [Timing table](../results/runs/actual_origin_disp_s3_e5_o1_20261031T131701_288861Z/timings.csv).
- [Geometry-only projection](../results/runs/actual_origin_disp_s3_e5_o1_20261031T131701_288861Z/geometry_only_projection.json).
- [Execution closure](../provenance/reviews/actual_origin_displacement_s3_e5_o1_execution_closed.json).

All 405 pre-existing protected source/configuration/document/test/review files matched their pre-development hashes. The research-stage ledger and previous runs remain unchanged. No commit, push, model promotion or research-stage closure was performed.
