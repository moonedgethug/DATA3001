# Step 5 E2 scoring optimization — approved bounded implementation

Authority: user approval on 2026-11-08, following the chat proposal. Implement and validate scoring optimization only. Do not resume the full experiment. Scientific authority remains `local_gmm_s5_e2_contract.md` and the frozen direct-full-run amendment.

## Fixed scope

- Keep all fitted parameters, donor weights, complete cohorts, K=1/2/3, seeds, eight replicate streams, N=M=65,536, WGS84 mapping, ECEF chord distances, and all K-squared terms including independent diagonal draws.
- Preserve the current run and all existing results. The active full-run implementation/configuration remains frozen. New code is an opt-in scoring module, not connected to the formal runner yet.
- Reuse each query/replicate's exact normal nodes across candidates; prepare parameter arrays once; batch identical geodesic operations; fuse distance arithmetic in double precision without fast-math.
- A lightweight validation runner reads frozen parameters and inner targets only; it does not initialize neighbour search, training geometry or donor lineage for ES.
- Independent arithmetic audit stays separate. No reduced sample count, changed metric, discarded component, score-based tuning, or new model fitting.

## Tasks and acceptance

1. Add failing numerical tests for complete mixture terms, shared streams, fallbacks, tail/polar/zero-displacement geometry, determinism, and input immutability. Implement until green.
2. Measure original step costs on the fixed 128 inner queries. Compare old/new scoring on these keys, then all 2,176 already-scored queries. Preserve all eight replicate means and numerical variances. Maximum absolute replicate/ES discrepancy 1e-9 km; precision and decision checks unchanged.
3. Verify one-worker versus two-spawn-worker outputs. No more than two workers, BLAS threads one. Keep 8 GiB memory, 8 GiB E2 storage and 10 GiB experiment-family storage limits.
4. Run relevant tests and full project tests; obtain a fresh read-only code review. Verify frozen input/output/source hashes, then report measured speed, step profile, equivalence and revised runtime estimates. Do not produce scientific model-selection conclusions from the subset.

## Budget

All new executable checks, compilation, validation and tests together: at most 600 seconds of active wall time, additionally bounded by the original checks phase and cumulative experiment budget. Coding and user waiting are excluded, as in the contract. Each command writes a checks receipt into the existing run. No resource-limit extension is authorized. Budget exhaustion stops checks and is reported honestly.

## Implementation rulings

- Continue in the explicitly approved existing workspace; additive modules and separate validation outputs avoid disturbing the extensive uncommitted research work. No git publication, branch change, stage-ledger edit or full-run resumption.
- Exact numerical equivalence, not speed, is the release gate. No promise of a particular speed-up before measurement.
- Production resource accounting is left frozen. The validation runner uses bounded command monitoring; any formal-run accounting optimization requires its own safety checks before later activation.

## Review focus

Preserve all cross-component and diagonal terms, independent halves and all replicate nodes. Check component ordering, fallback identity, in-place buffer aliasing, double precision and summation order. Ensure the 600-second cap includes failed checks, child workers terminate on timeout, protected original files remain unchanged, outer targets stay sealed, and speed comparisons use the same workload.
