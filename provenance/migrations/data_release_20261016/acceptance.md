# Per-drifter release acceptance — 16 October 2026

Release: **per-drifter-20261016-v1**. Scope: the approved local storage migration. No model fitting, missing-state inference, source download, Git commit or push was performed.

## Result

The active `data/` directory contains only `train/` and `test/`. Every ID has one complete Parquet file with **130 columns**. No acquired observation or existing feature was removed. Approved official drogue corrections were consolidated once, retaining their prior labels and evidence.

| Item | Verified result |
|---|---:|
| Development files (`train`, original train + validation) | 3,224 |
| Final-test files, original membership unchanged | 517 |
| Total drifter IDs | 3,741 |
| Total hourly records | 39,107,061 |
| Acquired source arrays retained | 62 |
| Existing prepared columns retained | 67 |
| Distinct source/prepared union | 109 |
| Added readable metadata companions | 12 |
| Added release/provenance annotations | 9 |
| Final columns per file | 130 |
| Archived original files, each hash verified | 52,383 |
| Archived original file bytes | 15,560,595,003 |
| Representative paired-label fingerprints unchanged | 300 |
| Unit/semantic/boundary tests passing | 90 |
| Registered asset locations/checksums checked | 66 |

The original data tree remains intact at `archive/data_before_release_20261016/`. Its exact original inventory is retained locally in `original_data_inventory.jsonl`, with SHA256 `45466d1f6df27b2cbd936fd46c617f270501392a2a30602010442ac2766dad81`. There were **zero original data file deletions**. Historical configuration, code and guide copies remain in `before/`; directory renames are recorded in `moves.jsonl`.

## What was checked

The staged build first compared each output with the approved pre-migration frame. After activation, a separate verifier reconstructed the expected frame from archived baseline/correction evidence for **every ID**, checked all 67 prepared columns exactly, and independently compared every native hourly value and all repeated trajectory metadata with the frozen Zarr source. It checked dtypes, source indices, original-order correspondence, missing values, raw byte metadata, text companions, per-field source attributes, pool membership and each file hash.

The verifier also checked every archived file's size/hash and the exact archived object set. It reproduced **300 fingerprints** across 10 representative IDs, five anchor horizons (7/30/90/180/365 days), three scenarios (drogued/undrogued/pooled) and the two independent endpoint/stopped targets. This is representative semantic regression, not exhaustive enumeration of all possible pair horizons. The core scientific rule modules remain byte-identical to this migration's baseline copies.

The complete test suite passed **90/90**. The CLI integration used ID **22165**, exact 7-day drogued R origins: **458 candidates**, **290 eligible endpoint** and **290 eligible stopped** labels. Its receipt records the canonical track checksum, release version, manifest checksum, contract, source snapshot, code and environment. A canonical final-test read without explicit opt-in was refused. All 66 registered asset locations and file checksums were checked.

Evidence:

- [Full independent verification](full_verification.json)
- [Build summary](build_summary.json)
- [Activation receipt](activation.json)
- [Integration verification](integration_verification.json)
- [Complete test output](unit_tests.log)
- [Implementation plan and progress](../../../docs/data_migration_plan.md)

## Research definitions and limits

Data Contract v1.0 remains unchanged, SHA256 **`6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`**. R, D, source fields, eligibility rules, missing-value meanings, source record keys and all historical split/fold assignments are retained.

`train` now exposes the combined development pool; it is not a new random split. No model-stage validation allocation has been generated. Future allocations must group complete IDs, save their manifests before fitting, and declare their protocol against contract clause 10. The final 517 test IDs remain unchanged and outside selection.

The current historical regime census remains **19,268,207 drogued / 19,342,607 undrogued / 496,247 unknown hours**. Unknown reasons remain distinct: 495,555 uncertain-from-start, nine unresolved boundary and 683 beyond proven attachment. Original native drogue flags/loss metadata remain present alongside approved derived labels. No unknown status was inferred during migration.

Frozen global support tables are historical and were not silently relabelled as current. DEPTH-01 remains pending, and annual/seasonal support limitations remain. This acceptance establishes data and interface preservation; it does **not** establish prediction accuracy, calibration, or suitability of every stored field as a forecast input.

## Use and recovery

Start with [the data guide](../../../docs/data_layout.md), [all column definitions](../../../docs/data_dictionary.md) and [the ID index](../../../configs/dataset_index.csv). Machine-readable file identities are in `configs/dataset_manifest.json`.

The full local checkout can repeat the read-only audit with `.venv/bin/python -m data3001 verify-migration`. It requires the retained data/archive bundle. Do not rerun migration build/activation scripts over an activated release. Preserve the current tree before any rollback; see [recovery instructions](../../../docs/architecture.md#recovery-procedure).

The [fresh independent review](final_review.md) found no Critical, Important or Minor issues. Its review boundaries and executor decisions are recorded explicitly. [The final closure receipt](closure.json) pins the final code/configuration/guide evidence and records the last integrity checks. No additional scientific claim or Git publication is authorised by this acceptance.
