# E9 numerical optimization: delivery note

Independent development, bounded pilot and independent numerical review are complete. The formal experiment remains paused.

- 32 semantic/regression tests passed; 128 complete pilot cases; 1,024 independent score/region checks.
- Exact reuse has zero observed ES discrepancy at matched draws and unchanged forecast regions.
- Controlled integration passes at 16,384 draws: seasonal point contrast projected 3 SE = 11.7563 m; seasonal CI = 11.7566 m; threshold approximately 15.0596 m. Both independent-seed checks pass.
- Same-session 4,096-draw p95 speedup from exact reuse: 1.147x.
- Full-sample prediction/scoring projection: 73.40 minutes; required 2x reserve: 146.81 minutes, exceeding the 120-minute phase cap. This is a provisional projection; complete support/storage/audit feasibility is still pending.
- Remaining mean time shares: geographic land/domain diagnostics 37.6%; CI geodesic mapping 22.0%. Shares are from measured mean component times, not p95 sums.
- Before final delivery QA: 59.0331 new compute/check seconds; 226.2827 cumulative pilot seconds. The delivery_qa resource receipt includes the final small verification cost. Caps are unchanged at 420 new and 600 cumulative seconds.
- Models, votes, complete donor pools, errors, fallbacks and evaluation definitions were preserved. The optimization changes the numerical ES estimator only.
- The chart was visually inspected and HTML links/table structure were checked. No browser rendering check was performed.

No full experiment, additional optimization or budget expansion was started.
