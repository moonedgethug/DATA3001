# Scoring optimization ledger

Plan: docs/local_gmm_s5_e2_score_optimization_plan.md

User authorizes additive scoring implementation and <=600 seconds of checks within the original checks budget; full experiment remains paused.

Pre-flight: parameter packets expose saved Cholesky factors and fallback flags; scorer accepts them without fitting. Existing ES packets carry all eight replicate values. New modules must not modify active source hashes/configuration.

Ruling: remain in the current approved workspace and preserve all old/unrelated changes. No git actions. The old full-run pipeline remains frozen and the optimized scorer is opt-in until a later approval.

Task 1: numerical regression tests written before optimizer; RED pending.

Task 1: complete. Four regression tests failed before implementation and passed afterward. Two equivalence-gate tests failed before implementation and passed afterward; six focused tests green. Full project suite running under cumulative budget wrapper.

Task 2: independent read-only review found one important process-group cleanup issue. Added actual orphan-descendant regression (RED), fixed group-wide cleanup with three-second reserve, regression GREEN. Numerical scorer unchanged. Updated additive source manifest revision 2; original formal manifest unchanged.

Project suite after cleanup fix: 758 tests passed in 41.943 s (project_suite_retry.log). Earlier post-fix attempt stopped on resource-monitor PermissionError; all children terminated, 10.915 s charged. Added failure traceback recording; retry passed without bypassing resource monitoring. Root cause of that single transient was not captured. Cumulative executable checks so far 123.314 s. Formal run not resumed.

Task 3: complete. 128 fixed queries and all 2176 saved scores passed full ES/replicate/variance/ID aggregation checks. Serial/spawn outputs identical. All 5473 protected output/config files preserved. Final suite 758 passed. Matched speedup 1.069843; geometry remains 92.44% of scoring. Task 4: report delivered, full run remains paused. Total new checks 430.043/600 seconds; original checks phase 781.788/1800 seconds.
