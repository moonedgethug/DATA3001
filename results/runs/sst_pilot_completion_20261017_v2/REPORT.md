# Pilot SST completion (corrected replay)

This run supersedes `sst_pilot_completion_20261017_v1` for reading. The earlier
fine-source stage hit a local read-only-array error; its 23 errors were not
evidence of missing official data. V1 and all earlier sources remain unchanged.
The decoder now owns its validity-mask array and fails loudly on unexpected
metadata or programming errors. All scientific interpolation rules are unchanged.

The user authorized four-corner OISST estimates for exactly 795 pilot-R
unknowns and a fine-source investigation for the remaining 81 coastal rows.
Data Contract v1.0, canonical fields and all prior temperature runs are preserved.

## Added temperatures

| Method | Added pilot hours |
|---|---:|
| CoralTemp_archive_v1.0, code 8 | 81 |
| OISST_v2.1, code 6 | 795 |

Total added: **876**. Remaining unknowns: **35,984**
across retained trajectories, **15** in R. Fine-grid unresolved
coastal rows: **0**. The 13 pilot high-temperature quarantines
and two position-mapping cases have not been changed. Current additions are all
development IDs; final-test assignments and temperature values are unchanged.

The 795 OISST estimates use the existing four weights and four finite source
temperatures. The previous geometric refusal is explicitly waived for these
keys, as authorized, rather than relabelled as proof of geometry validity.
`coarse_795_decisions.parquet` retains source-centre mask conflicts, cross-land
segments and rectangle-only intersections. No native position or temperature
QC flag was rewritten.

## Finer official source

The delivered source is the **NOAA OceanWatch CoralTemp v1.0 archive**, dataset
`CRW_sst_v1_0`, variable `analysed_sst`, 0.05-degree daily nighttime background
SST. The endpoint declares coverage 1985-01-01 through 2021-03-08, which includes
the requested dates. It is not silently relabelled as a verified current v3.1
asset. Same UTC-date matching uses the actual noon reference coordinate of a
daily analysis, not an instantaneous noon observation. Actual response axes,
units, bounds, fill handling and all returned times were checked.

Raw metadata and small-window JSON responses, exact query URLs, UTC retrieval
times and checksums are in `sources/` and `source_receipts.json`. Source failures
remain explicit in `source_failures.json`. No global temperature archive was
downloaded. Three-corner fine-grid values retain the previous no-cross-land
support gate; four finite source corners retain geometry-risk annotations.
No maximum-corner fill, large-neighbour search or temporal extrapolation occurs.

## Development diagnostic and limitations

| Source | Common development cases | IDs | MAE K | RMSE K | Bias K |
|---|---:|---:|---:|---:|---:|
| sst_use_K | 16 | 16 | 0.5248 | 0.7097 | -0.1698 |
| oisst_K | 16 | 16 | 0.3041 | 0.3818 | -0.0914 |

Sixteen known-temperature references were chosen deterministically from the
existing development masking cohort, four per season, before querying fine SST.
Only common qualified comparisons are scored. This small diagnostic is not an
independent coastal accuracy validation: source observations can overlap, the
fine product represents nighttime background, and the missing cases need not
follow the reference distribution. No correction or threshold was fitted from
the scores, and no final-test temperatures were used for selection or scoring.
Additional coverage does not establish better destination forecasts.

## Uncertainty, preservation and reading

Code 6 is the authorized coastal four-corner OISST estimate. Codes 7/8/9/10
denote fine exact-point/bilinear/triangle/outside-normalized routes. OISST retains
a source-only propagated SD bound. Fine-source uncertainty is unavailable from
this source and remains unknown; total reconstruction SE remains unknown.
GDP `sst`, `sst1`, `sst2`, error fields and flags are untouched.

All 3,741 ID files, all 130 original fields and all 39,107,061 rows retain their
hashes. Updated temperature sidecars contain every row for their affected IDs;
other IDs inherit the verified parent view without creating duplicated data.

```python
from data3001.sst_completion import read_sst_track
frame = read_sst_track(9825497, run='sst_pilot_completion_20261017_v2')
# Native sst is retained; reconstructed working temperature is sst_use_K.
```

`verification.json` and `changed_keys.parquet` reconcile the added values;
`output_manifest.json` pins per-ID outputs and parents. No source rows, labels
or features were deleted, and no Git commit or push was performed.

## Grounding policy: discussion only

`typedeath = 1` describes an ID's eventual termination, not its state at every
hour. `end_date` is a last-good metadata date and is not a verified grounding
hour. `termination_context.json` shows why a midnight cutoff would be unsafe.
Retain valid pre-grounding drift and the termination evidence. Confirmed
post-grounding rows should not be ordinary free-drift training samples, while
grounding itself can inform an explicitly defined coastal-outcome extension.
No new beaching state or training exclusion has been implemented here; the
contract distinguishes coastal occupancy, confirmed grounding and disappearance.
