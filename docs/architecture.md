# Repository architecture and research workflow

## Responsibilities

The Data Contract governs scientific definitions. This document governs file ownership, execution boundaries and reproducibility. Architecture changes do not authorise changes to cohort eligibility, source values, labels, geography, weighting or validation policy.

| Location | Responsibility |
|---|---|
| `README.md` | Current project status and reading/usage entry points |
| `docs/` | One current guide per stage and controlled contract copies |
| `src/data3001/` | Shared Python logic and explicit I/O boundaries |
| `configs/` | Asset/version locations and pinned environment; no alternative scientific authority |
| `data/train/`, `data/test/` | One complete current Parquet per ID; no logs, geometry or sidecar files |
| `results/runs/<run_id>/` | New derived outputs, models, metrics and figures |
| `results/deliverables/` | Versioned proposal/poster/report copies, with draft status preserved |
| `tests/` | Scientific semantic tests and architecture boundary tests |
| `provenance/frozen/` | Exact original code, receipts, configurations and checkpoints |
| `provenance/runs/<run_id>/` | Run parameters, inputs, code/environment identity and logs |
| `provenance/migrations/` | Layout change evidence, path mapping and recovery journal |
| `archive/` | Complete previous data tree, superseded plans, six-hour screening and report sources |

Add modelling/prediction/evaluation modules when real work starts. Exploration notebooks, if needed, call shared package functions rather than carry competing implementations. Do not introduce a second workflow framework or regenerate data just to accommodate a directory change.

## Asset identity and location

`configs/assets.json` selects assets by stable logical name. Each entry identifies its version/role, split and file checksum or full directory inventory. Baseline/addendum tables stay separate. `configs/legacy_paths.json` resolves original acquisition-relative paths to their new locations; it does not edit old receipts.

The current layout is **per-drifter-cleaned-1.5**, release **per-drifter-cleaned-20261017-v7**, with 62 existing fields per ID. [The data guide](data_layout.md) is the reading entry point. `configs/dataset_manifest.json` pins each ID file; the index and schema are separate lightweight configuration assets. Canonical readers use `data3001.dataset`, check the manifest/file identity and deny final-test access by default. Geometry, source snapshots and historical split manifests are registered archive assets. They do not belong inside the two active data directories.

`data3001.paths` is the only root/asset resolver. New code calls `asset_path()` or `project_paths().asset()`. The preserved modules use `legacy_path()` at their adapted I/O boundaries. These return ordinary `Path` objects, not virtual directory proxies. Do not add ad-hoc `sys.path` insertion or machine-specific paths to active configs.

`DATA3001_PROJECT_ROOT` can select another checkout. `DATA3001_DATA_ROOT` can locate the same verified active `train/` and `test/` tree elsewhere. Archived assets remain relative to the project root. These settings change location, not version or research scope; a machine override must still pass asset checks.

## Environment

The local migrated environment is `.venv/`, rebuilt with Python **3.12.14**. All 48 original installed distribution versions were preserved; original package source/native bytes were compared separately. Only setuptools 84.0.0 and wheel 0.48.0 were added from the bundled runtime for editable packaging. The original environment is retained in archive and in the verified external backup; its old absolute shebangs make it unsuitable for execution from its archived location.

For a fresh machine with Python 3.12.14:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r configs/requirements.lock.txt
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m data3001 inspect
```

Pins preserve the current research environment. Do not upgrade scientific libraries silently. The repository package is installed separately from the locked third-party dependencies. Full datasets are not required for the fast semantic suite; they are required for data-dependent inspection/generation and migration identity checks.

## Runs and frozen inputs

Use a unique run ID; both the results and provenance directories must be absent before creating it. The run receipt records parameters and input/code/environment identities. Derived pair runs record the actual source snapshot, canonical track hash and dataset release/manifest identity, alongside applicable correction evidence. Future modelling must additionally record features, training/validation IDs, fitted preprocessing, metrics and model artifacts; those are not yet implemented or claimed.

Frozen raw/processed data and historical receipts cannot be overwritten by the shared output helpers. Legacy actions that would rewrite frozen preparation, masks, summaries, source downloads or verification receipts are guarded. Their implementations remain preserved for reference; starting a new processing version requires configuring and auditing that new output contract. Scientific pure functions and read-only label generation remain available.

Examples:

```bash
.venv/bin/python -m data3001 --help
.venv/bin/python -m data3001 inspect
.venv/bin/python -m data3001 pair --id <development-ID> --days 30 --population R
.venv/bin/python -m data3001 pair --id <development-ID> --days 30 --population R --run-id <unique-ID>
```

Without `--run-id`, paired labels are evaluated in memory and only qualification counts are printed. They are not probability forecasts or model scores. Final test remains locked in this development interface.

## Git and collaboration

Track shared code, tests, contracts, configs, guides, lightweight reference files
and acceptance evidence. The user-approved team distribution also tracks the
current `data/train/*.parquet` and `data/test/*.parquet` files directly on main,
with their existing exact checksums, plus small portable qualification
projections. Source-object caches, full historical data backups, environments,
temporary files, per-ID checkpoint collections and routine runs remain ignored.
Do not use a blanket force-add for those excluded artifacts. See
[team download and setup](getting_started.md).

The four-member team reviews research changes against the Data Contract and keeps experiment changes separate from layout changes. Record code identity even for an uncommitted experiment, including the actual changed source hash/diff. Publishing, remote pushes and merging into a shared branch are separate actions.

The current data and portable qualification evidence are sufficient for normal
reading, `verify-data`, and the existing pair-label command after cloning.
The original full migration inventory also includes the old environment and
historical parents, so `verify-migration` remains specific to a fully retained
migration checkout; it is not required to start using the distributed data.

## Migration acceptance and retained identity

The latest data migration is **feature_pruning_20261017_v1**. Its [report](../provenance/migrations/feature_pruning_20261017_v1/REPORT.md) and [verification](../provenance/migrations/feature_pruning_20261017_v1/verification.json) document the approved 67-column removal, preserved values and unchanged pair labels. `verify-migration` dispatches to that full current release audit. The earlier **data_release_20261016** [acceptance](../provenance/migrations/data_release_20261016/acceptance.md), [full verification](../provenance/migrations/data_release_20261016/full_verification.json), original inventory and move journal remain historical evidence for the lossless consolidation and official corrections.

The previous data root is retained at `archive/data_before_release_20261016/`; migration configuration/code/guide backups are under `provenance/migrations/data_release_20261016/before/`. These backups and the full data remain local. No deletion or Git publication is part of this operation.

The earlier migration **architecture_20261014** remains historical: [plan](../provenance/migrations/architecture_20261014/plan.md), [ledger](../provenance/migrations/architecture_20261014/progress.md) and [first acceptance](../provenance/migrations/architecture_20261014/verification.json).

The full local `baseline.json` and `path_map.json` inventories are retained in the migration directory but excluded from Git. The independent complete backup is at `../.migration_backups/architecture_20261014/work_place` relative to the repository. Both external contract originals and `../submission_proposal/proposal_final.docx` were backed up separately; published copies retain their original bytes. The original external authority files remain in place.

Check the complete retained inventory without changing receipts:

```bash
.venv/bin/python -m data3001 verify-migration
```

Original checkpoints stay bound to their old code signatures. The adapted live code has a different identity; no old hash was changed to pretend otherwise. File-level identity proves preserved data/schema/receipts. Scientific-function AST comparisons and real-case regressions check the adapted code behaviour separately. Preparation/migration QA does not establish predictive accuracy.

## Recovery procedure

Do not run recovery while acquisition, preparation or modelling is writing to this checkout.

For the current data consolidation, preserve the active `data/` and current configuration/code in a separate recovery directory first. Verify the archived old tree against `original_data_inventory.jsonl`; rename that old tree back to `data/` only when the destination is absent, then restore matching files from this migration's `before/` backup. The two renames are recorded in `moves.jsonl`. Keep the preserved consolidated tree and all receipts. Never rerun `build.py` or `activate.py` over an already activated release. Recheck the corresponding catalog, whole-ID assignments and scientific tests before resuming work.

The following steps describe recovery of the **earlier architecture migration**, not a shortcut for undoing later research changes.

For a single interrupted move, use the `before`/`after` entries in `move_journal.jsonl` and the per-file old/new map. Verify the affected bytes against the independent backup before returning them to their original location. Never overwrite a later research result to restore an earlier path.

For a complete rollback:

1. Verify the external backup against its original `baseline.json`, including files and symlink targets. Check adequate disk space.
2. Copy the complete backup tree to a new sibling staging directory, preserving symlinks; verify the staged original inventory before switching.
3. Preserve the entire current migrated checkout in a separate sibling directory, including its Git history and any new results. Do not delete it.
4. Rename the verified staging directory to the original `work_place` location. If the second rename fails, restore the preserved migrated directory to that location.
5. Recheck the original environment, branch, 41 baseline tests and original asset identities before resuming work.

The backup includes original Git metadata; any new migration commit remains recoverable in the preserved migrated checkout. No historical data/cache deletion is part of this migration. Retire backups only through a later explicit retention decision.

## Historical documents and reports

Archived documents retain old links and paths as historical evidence. Current instructions live in `docs/` and the asset catalog. Resolve old paths with the recorded map; do not silently revise historical scientific statements.

The report authoring bundle and its AGENTS.md/runtime/assets remain together under `archive/report_sources/`. Existing report exports are copied byte-identically into `results/deliverables/`. No rebuild, publication or report-content edit is included. Poster versions retain their draft status; the current proposal copy is taken from the actual submission workspace rather than guessed from an older filename.
