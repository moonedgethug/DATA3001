# SST stored directly in the existing column

**Status: verified.** The current release is `per-drifter-cleaned-20261017-v3`.
All approved total-temperature fills and corrections are now physically stored
in **`sst`** in `data/train/<id>.parquet` and `data/test/<id>.parquet`.
Ordinary reads require no temperature merge and add no feature columns.

## What changed

| Check | Verified result |
|---|---:|
| Drifter IDs | 3,741, unchanged |
| Retained hourly records | 39,099,193, unchanged |
| Columns per file | 130, unchanged |
| Other columns' values, types and missingness | All 129 unchanged |
| Missing original SST values filled | 1,354,245 |
| Finite original SST values replaced by previously approved results | 14,893 |
| Total stored SST value changes | 1,369,138 |
| Remaining numeric SST NA values | 5,547, unchanged from the prior working view |
| Train / final-test IDs | 3,224 / 517, unchanged |
| Regression tests | 164 passed |

Only `sst` values and its storage type/cleaning metadata changed. SST remains in
Kelvin; float64 storage preserves previously approved estimates without a
float32 rounding step. Current files and the default compatibility reader have
no `sst_use_K` column. The earlier reconstruction files are historical audit
evidence only and are not additional active datasets or model features.

This migration introduces **no new filling method, anomaly decision, sample,
split or grounding rule**. The 14,893 finite-value changes include earlier QC
fallback decisions as well as anomaly repairs; they are not newly discovered
anomalies. Accepted original values are retained exactly. Existing unresolved
quality-review points remain unresolved: 2,584 overall, including 213 in R.
The 5,547 remaining NA values are on eventual-grounding IDs after their official
last-good time; that time is not asserted to be the first grounding hour.
No additional finite temperatures in that context were blanked.

Original `flg_sst`, `err_sst` and older derived audit fields remain unchanged.
They describe original GDP estimates, not quality or uncertainty of the new
replacement values. The cleaned `sst` combines accepted original estimates
and approved reconstructions; it must not be described as all directly observed
GDP values. Per-record provenance is available in the external change ledgers.
Components `sst1` and `sst2`, geometry, drogue labels, endpoint definitions,
Data Contract contents and ID pool assignments remain unchanged. Previously
removed vessel-recovery tails remain absent. No predictive accuracy is claimed.

## Evidence and recovery

- `verification.json`: full comparison of all 3,741 files with archived originals and frozen approved temperature decisions.
- `acceptance.json`: checksums, test result and preservation summary.
- `changes/train/` and `changes/test/`: only changed record keys, old/new SST and the existing method/source decisions; these are audit tables outside active data.
- `approved_sources.json`: the exact historical reconstruction inputs and hashes.
- `receipt.json`, `staging.jsonl`, `activation.jsonl`: source links and resumable publication records.
- `archive/sst_inplace_20261017_v1/data/`: original pre-write files, with their pre-write manifest, schema and index alongside them.

Read a cleaned development trajectory directly:

```python
from data3001.dataset import read_track
frame = read_track(22165)
print(frame[['id', 'time_UTC', 'sst']].head())
```

The final-test opt-in guard remains enforced by the reader. Historical
reconstruction evidence remains in `results/runs/`; it does not need to be joined
to current data. Git has not been committed or pushed for this change.
