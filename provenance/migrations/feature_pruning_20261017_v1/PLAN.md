# Approved feature projection

Authority: the user explicitly approved physical deletion from both train and
test of the current drop list, except `err_lat`, `err_lon`, `err_ve`, `err_vn`.
The follow-up answer selected these four numeric uncertainty fields only.
The scientific authority remains the unchanged final Excel Data Contract.

## Scope

- Parent: per-drifter-cleaned-20261017-v6, 3,741 IDs, 39,099,193 records,
  129 columns. Development 3,224 IDs; final test 517 IDs.
- Remove exactly 67 existing registered fields. Historical `regime` is already
  absent. The four approved uncertainty values remain byte-value equivalent.
- Result: 62 existing columns in their original order, with unchanged types,
  field metadata, null positions, record keys, values, row order and pools.
- No new feature, imputation, row deletion, split, model fitting or test scoring.
- Fields not in the approved drop list remain untouched, including existing
  temperature uncertainty and flags. The four-field exception applies only to
  the previously listed position/velocity uncertainty group.

## Execution and acceptance

1. Freeze parent configurations, registry, reader code and affected documents.
   Verify contract and catalog hashes. Save representative pre-change endpoint
   and stopped-process labels for three development IDs, three horizons and
   all three drogue scenarios. Never select policy using final-test outcomes.
2. Test projection preservation, metadata consistency and rejection of an
   accidental deletion of any protected uncertainty field.
3. Hard-link each unchanged parent file into the archive (test backups under
   `restricted_test`); write a separately staged projected file. Re-read and
   compare every retained value, null, type and field attribute before activation.
4. Stage all files before activation. Journal staging and activation so an
   interruption can be resumed. Atomically replace each file, then publish
   manifest, index, schema and catalog. Readers fail closed on a hash mismatch
   during the short activation window.
5. Qualification rules continue to use archived, exact source-observation-keyed
   annotations in memory; these fields are not recreated in active data files
   or in the normal read_track result. The mathematical labeling rules remain
   unchanged. Update only the input adapter and release verification dispatch.
6. Independently verify all 3,741 active files against archived parents, fixed
   ID assignments, all 62 retained values and metadata. Compare pre/post labels,
   run the test suite and update the existing reader documentation and registry.

## Recovery

Full parent Parquet files and configurations remain under
`archive/feature_pruning_20261017_v1/`. Backups are hard links to the original
files; active files are replaced, never modified through an existing inode.
Restoration must copy or replace files and restore the parent configurations,
not mutate hard-linked backups. No Git operation is part of this task.

## Workspace ruling

The existing checkout contains substantial authorized, uncommitted data-cleaning
work and the local data bundle. Execute this data migration in that checkout;
do not switch branches, create another incomplete checkout, or modify unrelated
dirty files. This is a storage projection, not a new research method.
