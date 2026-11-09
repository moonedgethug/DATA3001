# E8 execution notes

The user approved E8 v2. This note records implementation decisions; it does not revise the approved scientific contract or research ledger.

## Bounded pilot history

| Attempt | Runtime (s) | Numerical gate | Resource gate | Twice projected formal time (s) |
|---|---:|---|---|---:|
| 1 | 43.413 | True | False | 11557.63 |
| 2 | 36.597 | True | False | 8018.26 |
| 3 | 40.725 | True | False | 8960.19 |
| 4 | 31.585 | True | True | 5537.14 |

All attempts are preserved. Attempt 3 added profiling and included neighbour-search/diagnostic overhead in the timing projection. Acceleration uses spatial indexing, bounded exact coastline intersections, and prepared local coastline predicates with a global fallback. It does not simplify coastlines, remove draws, alter neighbours, or change scores. All 128 original and accelerated pilot outputs reconcile; the largest land-area roundoff difference is below 1.5e-10 km².

The original pilot gate receipt recorded time and RAM reserve but omitted an explicit storage-reserve field. Supplemental checks during outcome-sealed prediction verified storage separately using the complete frozen E7 donor counts. The projected twofold storage requirement is approximately 3.27 GB, below the 5 GiB cap. The hard run storage limit remains enforced.

## Nonzero-correlation sensitivity correction

Main rho=0 forecasts are unchanged and remain frozen. Code review identified that the original supplementary MatchedSpread runs at rho=±0.5 matched average marginal variance but used the same rho, which generally fails to match average cross-covariance. The corrected common correlation is rho * mean(s_E*s_N) / sqrt(mean(s_E²)*mean(s_N²)). The original diagnostic table is retained as superseded; rho_sensitivity_corrected.parquet is authoritative. EndpointCI sensitivity rows are unchanged. The correction uses the same 128 inner queries and consumes the remaining pilot allowance; it uses no outer outcomes and selects no parameter.

## Independence and reproducibility

Primary predictions use the original E7 starts, roles, 100-km cap, k=8,000 plus ties, and full donor votes. Forecasts, donor arrays and regions are sealed before the outer endpoint allowlist is read. No outer endpoint errors or locked final-test records are read.

Independent verification is a separate process and code path. It uses manual WGS84 ECEF formulas, independently computed covariance/quantile regions, independent random streams, complete-roster region replication, fixed-case score replication, original E7 donor hashes, half-degree display probability reconciliation, and independent whole-ID bootstrap reconciliation. A failed numerical gate is reported as inconclusive rather than silently relaxed.

No model has been promoted and no new scientific phase has been opened.
