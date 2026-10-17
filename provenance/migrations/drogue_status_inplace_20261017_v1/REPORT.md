# Cleaned drogue state consolidated into drogue_status

**Completed and verified.** Active release: `per-drifter-cleaned-20261017-v5`.
Every existing approved `regime` value was copied **without alteration** into
`drogue_status`, and `regime` was physically removed from every active train/test
file. Ordinary readers return the stored 129-column data and do not recreate the
removed column. This task does not estimate or reclassify any drogue state.

## Current interpretation

| drogue_status | Meaning | Retained hourly records |
|---|---|---:|
| 1 | Drogued | 19,267,484 |
| 0 | Undrogued | 19,335,559 |
| -1 | Unknown | 496,150 |

The field is an int8 categorical state with no nulls. Its previous binary source
flags are archived; original source attributes describe those original flags,
while explicit cleaned attributes describe the current three-state column.
Do not interpret the cleaned state as a Boolean. The contract's previous
implementation term `regime` now maps to `drogue_status`; the scientific state
meanings, eligibility rules and unknown intervals did not change.

## Preservation and validation

- All **3,741 IDs and 39,099,193 observations** are retained, in the same order.
- Columns per file decrease from **130 to 129**; `regime` is the sole removal.
- Every stored `drogue_status` equals the corresponding parent `regime` value,
  including all -1 values. No interpolation, inference or new labels were added.
- **All other 128 columns**, including SST and `drogue_lost_date`, retain their
  exact values, types and nulls. Source and row keys and train/test assignments
  remain unchanged (3,224 development IDs / 517 final-test IDs).
- The 16,059 approved SST NA values, including 47 in R, remain unchanged;
  vessel-recovery tails remain absent.
- **169 regression tests passed.** All **180 representative endpoint/stopped
  outputs** are identical before/after for 7/30/365-day horizons, drogued,
  undrogued and pooled scenarios, and R/D origin populations. Cases cover
  nominal loss, attached-at-end evidence, the 44-ID correction, unknown status
  and vessel-recovery censoring.
- Reading and pairing use the declared cleaned `drogue_status`. A local algorithm
  may still use a variable called regime; no such feature is added to a frame.
- The Data Contract contents are unchanged. No prediction-accuracy claim is made.

The former binary `drogue_status` differs from the approved labels on 532,150
rows. These are previously established corrections/unknown states now placed
in the requested column, not new scientific state changes. `changes.parquet`
records those keys and the before/after values outside active data.

## Evidence and recovery

`verification.json` independently checks every current ID file against its
archived predecessor. `receipt.json`, `staging.jsonl` and `activation.jsonl`
record identities and resumable publication. `pairs_before.json` and
`pairs_after.json` preserve the 180-output equivalence checks. `tests.txt` holds
the complete test result; `ledger_verification.json` verifies changed keys.

Original v4 files and prior configurations/runtime code are preserved at
`archive/drogue_status_inplace_20261017_v1/`. Earlier raw sources also remain
archived. Current README, data guide/dictionary, schema, manifest and review
registry use the consolidated representation. The registry retains a removed
`regime` entry as decision history; it is not an active data column.

Other previously agreed drop-list fields remain deferred; none were silently
removed here. No new feature, training, Git commit or push was performed.
