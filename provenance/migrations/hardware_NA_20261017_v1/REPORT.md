# Hardware missing-value normalization — acceptance report

Only the seven approved existing hardware columns were changed. No hardware values were estimated or imputed. No feature column was added or removed.

## Result

- Release: `per-drifter-cleaned-20261017-v6`; layout `per-drifter-cleaned-1.4`.
- 3,741 IDs and 39,099,193 rows retained, with 129 columns per file.
- 210 affected ID files (181 train; 29 test).
- 3,533,591 existing NaN cells became typed Arrow null. This is a missing-value representation change, not new missing observations.
- All seven fields were read from every current ID. No infinity, negative numeric value or residual finite missing code was found.
- All existing zero codes and finite hardware values were preserved. Zeros are not automatically interpreted as missing or hourly drogue states.

| Existing column | Numeric NA cells after normalization | IDs with NA |
|---|---:|---:|
| `DragAreaAboveDrogue` | 682,604 | 95 |
| `DragAreaOfDrogue` | 700,127 | 101 |
| `DragAreaRatio` | 700,127 | 101 |
| `DrogueBallast` | 1,371,415 | 164 |
| `DrogueCenterDepth` | 17,763 | 4 |
| `DrogueLength` | 35,286 | 10 |
| `FloatDiameter` | 26,269 | 6 |

## Storage meaning

NA is a real nullable numeric value in the original field, not the literal text "NA". Depending on the reader, the same missing value may display as NA, NaN or an empty cell; use `isna()` to test it. Every original column remains numeric and no parallel cleaned column is created.

## Preservation and scope

- Every current file hash was checked against the current manifest. Unaffected file bytes retain their parent hashes.
- Each affected file was compared with its exact archived parent: all 122 other columns, schema and field metadata, record count, order and keys were unchanged.
- Finite hardware values and their row positions were independently compared; all zeros and positives are unchanged.
- `sst`, cleaned `drogue_status`, `drogue_lost_date`, source positions/times and complete-ID train/test assignments are unchanged.
- `regime` remains absent. There are exactly 129 columns and no new feature columns.
- The final Excel Data Contract is unchanged (SHA-256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`).
- The full suite passed: 172 tests. The full-cohort acceptance check passed.
- The source annotation that calls the drag-area ratio unit "m" remains a documented metadata interpretation issue. This normalization does not change units or claim every finite value is physically validated.
- Predictor selection remains pending. No row was excluded because its hardware metadata is missing, and no forecast-accuracy claim is made.

## Reproduction and evidence

- [Exact execution script](execute.py), [policy/plan](PLAN.md), [per-ID receipt](receipt.json), [full verification](verification.json), [test output](tests.txt).
- Re-run the project verifier or `data3001.hardware_missing.verify_hardware_release()` for the current release.
- Parent files and configs remain in `archive/hardware_NA_20261017_v1/`; the frozen source snapshots were not modified.
- Current canonical checksums are in `configs/dataset_manifest.json` and `configs/dataset_index.csv`. Data remain in `data/train/` and `data/test/`.

Independent scoped review accepted the migration with no material current-cohort findings and reproduced the full-cohort verifier.
