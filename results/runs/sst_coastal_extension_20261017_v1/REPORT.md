# Three-corner coastal SST extension

This run executes the user-approved inside-triangle linear / outside-triangle
normalized-weight policy. It is retrospective temperature reconstruction,
not a destination forecast or proof of an optimal imputation method.
Data Contract v1.0 and the canonical release are unchanged.

## Coverage

| Pool | Route | Added temperatures | Added in R |
|---|---|---:|---:|
| test | Outside normalized | 6 | 0 |
| test | Triangle linear | 31 | 0 |
| train | Outside normalized | 807 | 36 |
| train | Triangle linear | 282 | 85 |

Added **1,126** temperature estimates, including **121**
in pilot R. Remaining unknowns: **36,860** across retained tracks,
including **891** in R. Only exactly-three-corner
baseline coastal unknowns were considered. Other unresolved classes remain.
`coverage.csv` and `candidate_decisions.parquet` distinguish accepted estimates,
land/mask refusals, geometry, original available weight and centroid displacement.
`coastal_scope.parquet` also records cases outside the three-corner scope.

The target plus its three source centres must have an all-water convex hull
under both frozen masks. This replaces the old full-rectangle test only for
this extension. No cross-land blend, new neighbour search, maximum-temperature
fill or second source acquisition was performed. Boundary points use triangular
weights. Outside estimates use only the original available bilinear weights;
renormalization does not recreate missing spatial information.

## Development diagnostic

| Route | Method | Simulated cases | IDs | MAE K | RMSE K | Bias K |
|---|---|---:|---:|---:|---:|---:|
| inside | hybrid_K | 5,442 | 479 | 0.3114 | 0.5039 | -0.0260 |
| inside | normalized_K | 5,442 | 479 | 0.3108 | 0.5023 | -0.0251 |
| inside | full_stencil_K | 5,442 | 479 | 0.3112 | 0.5035 | -0.0261 |
| inside | maximum_fill_K | 5,442 | 479 | 0.3111 | 0.5016 | -0.0100 |
| outside | hybrid_K | 5,442 | 479 | 0.3275 | 0.5284 | -0.0302 |
| outside | normalized_K | 5,442 | 479 | 0.3275 | 0.5284 | -0.0302 |
| outside | full_stencil_K | 5,442 | 479 | 0.3112 | 0.5035 | -0.0261 |
| outside | maximum_fill_K | 5,442 | 479 | 0.3368 | 0.5426 | 0.0463 |

Each eligible frozen development mask is evaluated under four artificial corner
removals. These variants share source hours and IDs and are **not independent
samples**. The references are accepted GDP temperatures; OISST may assimilate
buoys, so they are not independent physical truth. The original stencils pass
the old all-water rule, meaning this diagnostic does **not** reproduce real
coastal land masking, validate all real missing cases or establish coastal
forecast accuracy. Method differences are compared on identical cases within
each route. Seasonal and R strata are in `validation_strata.json`. Final-test
temperatures were not scored or used to select methods or thresholds.

The two routes remain distinctly labelled. A numerical completion is not an
accuracy guarantee; small available weight or displaced weighted centroids
identify weak support for later sensitivity analysis. No fitted bias correction
or post-hoc method selection was made from these diagnostics.

## Preservation, uncertainty and reading

All 3,741 original ID files, all 130 fields and all 39,107,061 records retain
their original hashes. Every baseline temperature-sidecar file retains its
hash. Complete replacement temperature sidecars exist only for the 49
changed IDs; their other rows, keys, fields and pool assignments are exact.
Other IDs inherit their explicitly named baseline sidecar.

Methods 0--3 retain baseline meanings; 4 is three-corner triangular linear and
5 is three-corner outside normalized. Source-only SD upper bounds use the same
three weights. They omit representation/interpolation error. Total reconstructed
SE remains unknown. Original GDP temperatures, components, QC and errors are
never overwritten, and source-only bounds are not relabelled as total SE.
Temperature unknowns do not by themselves disqualify core position pairs.

```python
from data3001.sst_coastal import read_sst_track
track = read_sst_track(22165)
# For authorized fixed-rule inspection only: allow_test=True.
```

This returns every original feature plus the chosen sidecar without requiring
users to select between versions manually. It does not authorize all fields as
forecast-time predictors. Daily final OISST remains retrospective.

`config.json` pins inputs, code, tolerance, source masks and the baseline.
`source_receipts.json` identifies checksum-verified original cached objects;
used node temperatures and source errors were independently decoded offline.
`verification.json`, `changed_keys.parquet`, `output_manifest.json` and
`worked_examples.json` supply preservation and equation checks. No Git commit
or push was performed.
