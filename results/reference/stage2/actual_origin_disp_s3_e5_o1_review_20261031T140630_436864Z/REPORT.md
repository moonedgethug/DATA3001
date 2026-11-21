# Step 3 E5 O1: optimisation trial

Trial status: **CAPACITY_NOT_ESTABLISHED**. Full experiment: **not started**.

Source: `actual_origin_disp_s3_e5_o1_20261031T131701_288861Z`. This review contains computational evidence only; it does not establish improved Brier, hit rate or prediction-region size.

## Execution budget

| stage | seconds | minutes |
| --- | --- | --- |
| A | 677.18428 | 11.2864 |
| B | 1335.16638 | 22.25277 |
| C | 60.0 | 1.0 |
| D | 0.0 | 0.0 |

## Bottleneck and acceleration

| component | seconds |
| --- | --- |
| Whole-path land certificates | 136.91285 |
| Hourly land points | 124.45531 |
| Hourly land segments | 46.522 |
| Other / overhead | 28.35249 |

| query_index | horizon | coastal | seconds_old | seconds_new | speedup |
| --- | --- | --- | --- | --- | --- |
| 0 | 7 | False | 41.3604 | 0.21316 | 194.03371 |
| 7 | 7 | False | 38.8725 | 0.57251 | 67.89857 |
| 16 | 7 | True | 14.08006 | 1.91107 | 7.36763 |
| 23 | 7 | True | 14.01578 | 2.0297 | 6.90533 |
| 25 | 30 | False | 69.5274 | 2.78151 | 24.99626 |
| 32 | 30 | False | 75.31138 | 4.83764 | 15.56779 |
| 41 | 30 | True | 40.19599 | 4.63462 | 8.67299 |
| 48 | 30 | True | 41.03153 | 4.74087 | 8.65485 |

Aggregate paired acceleration: 15.395x. This excludes cold setup and includes only matched complete calls; whole-run projections include other measured components.

## Integrity and limitations

Validation evidence (extended validation incomplete): `{"all_completed_calibration_comparisons_matched": true, "calibration_queries": 8, "in_process_full_pair_comparisons_per_variant_batch": 355418, "independent_real_scalar_checks_completed": 0, "limitation": "Completed benchmark records are written only after in-process array equality assertions. Optimized arrays remained in RAM and were lost; no independent saved-array comparison is claimed.", "optimized_raw_arrays_persisted": false, "real_data_region_and_selection_parity_completed": false, "remaining_engineering_validation_queries": 50, "status": "INCOMPLETE", "variant_batch_comparisons": 6}`.

Serial / two-worker comparison: `null`.

True starts, all donor pairs, full-path semantics, failed-mass B2 return and fixed 90% regions are retained. A subset of query starts is used for engineering capacity testing only; the full scientific case population is unchanged. Development-only read guards were enabled. The final access-counter log was not flushed after the native crash.

The complete-run projection was not established. Unmeasured stages are not assigned zero cost.

## Geometry-only scale warning

Serial primary geometry extrapolation from eight calibration queries: **250.1 hours** at pooled mean rates, or **635.1 hours** at the slowest sampled rates plus a factor-two reserve.

Including one fresh geometry replay: **500.1 / 1270.3 hours**. Scoring, controls, uncertainty, complete audit and I/O are unmeasured and excluded. These values are neither a confidence interval nor a proven lower bound; engineering validation did not complete.

## Native concurrency failure

The process received SIGSEGV while two workers called GEOSPreparedIntersects_r on shared prepared land geometry. The faulting stack includes MCIndexSegmentSetMutualIntersector and SegmentIntersectionDetector. Python-level read-only arrays do not make these GEOS objects thread-safe. This is an engineering design error in the shared-object concurrency experiment. The stack is consistent with the upstream documented limitation: [GEOS issue 825](https://github.com/libgeos/geos/issues/825). No post-failure replay was attempted. The approved stop rule ended the bounded attempt.

All eight calibration queries matched the reference during execution, covering 355,418 donor pairs per variant/batch. Optimised arrays had not yet been persisted; no independent saved-array parity audit is claimed. The remaining 50 engineering queries, 5,000-scalar-transfer target, real-data scorer/selection parity and complete-run capacity gate remain unfinished.

## Source artifacts

- [Trial receipt](/Users/moonedgethug/Documents/UNSW/DATA3001/work_place/results/runs/actual_origin_disp_s3_e5_o1_20261031T131701_288861Z/trial.json)
- [Raw timings](/Users/moonedgethug/Documents/UNSW/DATA3001/work_place/results/runs/actual_origin_disp_s3_e5_o1_20261031T131701_288861Z/timings.csv)
- [Frozen roster](/Users/moonedgethug/Documents/UNSW/DATA3001/work_place/results/runs/actual_origin_disp_s3_e5_o1_20261031T131701_288861Z/roster.csv)
- [Sealed outputs](/Users/moonedgethug/Documents/UNSW/DATA3001/work_place/provenance/runs/actual_origin_disp_s3_e5_o1_20261031T131701_288861Z/outputs.json)
