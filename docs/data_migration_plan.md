# Per-drifter data release implementation plan

> Execute inline under the user's 16 October 2026 migration authorisation. Preserve the shared checkout and existing uncommitted work. No commit, push, download, imputation, feature selection or model fitting is part of this migration.

**Goal:** Make `data/` contain only `train/` and `test/`, with one complete current Parquet per acquired drifter and a fully recoverable original corpus.

**Architecture:** Preserve the complete old data directory byte-for-byte at `archive/data_before_release_20261016/`. Build the replacement in a staging directory under the migration receipt. Preserve all hourly observations, all native trajectory metadata, every existing prepared column and the approved official corrections. Current readers select the consolidated release; historical readers retain registered archive paths.

**Tech stack:** Existing Python 3.12, pandas, NumPy, PyArrow, Zarr and unittest. No new dependencies.

## Binding requirements

- Preserve 3,741 IDs and 39,107,061 retained observations.
- New `train` is the development pool: original train plus validation, 3,224 IDs. Test remains exactly the existing 517 IDs.
- Preserve original split and fold manifests, plus per-ID historical split annotations. No new validation allocation occurs during migration. Future experiments must save grouped ID splits before fitting, with the final test unchanged.
- Preserve Data Contract v1.0 and its hash. This release changes storage and exposes the development pool; future validation choices must be declared against clause 10 and the user's authorised development-pool protocol.
- Preserve all 62 source arrays: 20 hourly variables and 42 trajectory/provenance variables. Repeat ID-level metadata as typed constant columns. Preserve all 67 current prepared columns. Their union contains 109 fields before additional annotation/provenance columns.
- Retain native bytes for fixed-byte metadata, rather than guessing encodings. Supply readable decoded companions only when exact decoding succeeds and retain the bytes either way.
- Preserve row order, source observation keys, data types, null masks, special values and source attributes. Retain the 496,247 currently unknown regime hours without imputation.
- Preserve all old data objects and historical evidence. Geometry, splits, inventories and metadata remain available outside the active data directory.
- No current file is overwritten. Build, verify, archive, activate, verify again. Record all renames and reversible configuration changes.

## Review focus

1. Metadata stored outside hourly files must not disappear: test source/prepared field union, scalar dtypes, byte strings and missing values.
2. Final-test access must remain denied through direct readers, aliases and historical paths.
3. Current interval semantics must preserve the official-fill and boundary refinements; compare canonical readers against pre-migration results.
4. File names are insufficient identity: store int64 ID and source keys in each file and verify filename, row count and per-ID hashes.
5. A failed switch must not leave misleading active paths: no-clobber staging, original byte inventory, recorded moves and recovery instructions.

## Task 1 — Freeze and build lossless records

Files: `src/data3001/data_release.py`, `tests/test_data_release.py`, migration receipts.

- Freeze hashes of every original data file and archive current code/configuration/guide copies.
- Write failing tests for lossless field union, metadata type/byte preservation, unknown reasons and source/prepared conflicts.
- Implement pure assembly and a one-ID-at-a-time staged writer.
- Verify every output column against the approved current frame and every native hourly value against the frozen Zarr source. Verify every metadata scalar against its source array.
- Record the exact schema, source attributes, per-ID manifest, current regime census and representative paired-label fingerprints.

## Task 2 — Activate two-directory layout and compatible readers

Files: `src/data3001/dataset.py`, current preprocessing readers, `paths.py`, catalog and historical path map.

- Test locked test paths and canonical release loading, including original validation IDs in the development directory.
- Register canonical train/test, manifest, schema and index assets. Translate old asset and legacy paths to the archive without rewriting historical receipts.
- Archive the old data directory and activate verified staging by same-filesystem renames. Update configuration after both data locations exist.
- Current readers consume consolidated files directly and retain proof-aware interval semantics. Preserve legacy fallback for historical/minimal fixtures.

## Task 3 — Full acceptance and documentation

Files: README, preprocessing and architecture guides, `docs/data_layout.md`, migration acceptance.

- Independently compare all 3,741 current files with archived expected values and metadata; verify every archived file hash.
- Reproduce representative endpoint/stopped labels at 7/30/90/180/365 days across correction groups and partitions. Retain pooled invariance and test locks.
- Run the complete unittest suite, safe CLI integration and catalog/path checks.
- Publish a human-readable guide, complete column dictionary, data index, manifest and acceptance report. Historical support tables remain explicitly labelled as historical rather than silently treated as current.
- Perform one final independent read-only review; fix material findings and rerun affected checks.

## Progress

- Planning and baseline tests: complete (77 passing tests).
- Baseline hash inventory: complete; 52,383 files / 15,560,595,003 bytes frozen before renaming.
- Staged record generation: complete; 3,741 files / 39,107,061 rows / 130 fields, with first-pass field comparison.
- Activation: complete; original tree retained at the recorded archive path; only train/test remain under data.
- Independent data acceptance: complete; every archived hash, every native/prepared field and 300 paired-label fingerprints checked. See `provenance/migrations/data_release_20261016/full_verification.json`.
- Reader/CLI checks: complete; canonical paths, test guards and release-aware run receipts verified; unittest suite 90/90 passing.
- Human guides: data layout, complete column dictionary and current architecture/preprocessing entry points updated.
- Final independent review: complete; no Critical, Important or Minor issues. Review boundaries and decisions are in `provenance/migrations/data_release_20261016/final_review.md`.
- Closure: evidence and final checks recorded in `provenance/migrations/data_release_20261016/closure.json`.

## Execution decisions and evidence

- Resume decision: activation had completed before interruption. Continue verification/documentation; do not repeat the build or rename operations.
- The current verifier dispatches on the active layout. The 2026-10-14 verifier remains a historical fallback; comparing its older pre-correction scientific reference as though it were current would conflate approved drogue corrections with this storage migration. Dispatch regression observed RED then GREEN; the complete suite passes.
- Original data is retained by an intact directory rename, not deletion. Code/configuration/guide backups and original inventories remain local because no Git publication is authorised.
- No research rule, feature, observation, validation allocation or drogue inference was added. Existing official corrections are materialised once, with their baseline labels and evidence retained.
