# Architecture migration acceptance — 2026-10-14

**Accepted for the repository layout and retained-data identity scope.** Research Contract v1.0 remains unchanged. DEPTH-01 and long-horizon seasonal evidence limits remain pending; forecast accuracy has not been evaluated.

| Check | Fresh execution result |
|---|---|
| Complete independent backup | 78,343 original file/symlink entries and three external authoritative/deliverable files copied and verified |
| Final original-file identity | 78,343 entries / 16,150,474,468 file bytes; no mismatch |
| Source/cohort | 3,741 IDs / 39,107,061 hourly records; all assignments unchanged |
| R visitors | 463 IDs; 323 train / 73 validation / 67 locked test |
| Global acquired cohort split | 2,674 train / 550 validation / 517 locked test |
| Original scientific logic | 33 function AST comparisons plus pure-module constants unchanged |
| Five full real-track cleaning checks | Every saved logical column value matched exactly |
| Two real 365-day target checks | Qualified early exit remains stopped-outside; endpoint termination remains separate |
| Source/native package bytes | 9,536 original installed-package source/native files match in rebuilt environment |
| Fast rules/boundary suite | 62 passing tests |
| Minimal checkout | Same 62 tests pass without raw/processed/test data |
| CLI label integration | 399 candidates per target; fixed-drogued and pooled historical fields match; pooled has 231 qualified per target |
| Dependency consistency | `pip check` passes; all original distribution versions preserved |
| External originals | English/Chinese contracts and latest submission proposal remain unchanged |

## Evidence

- [Final full identity receipt](verification_accepted.json)
- [Accepted test log](tests_accepted.log) and [minimal-checkout log](no_data_checkout_final.log)
- [Full-track/early-exit/package-byte check](real_case_verification.json) and [fresh final execution](real_cases_final.log)
- [CLI fixed-scenario comparison](pair_cli_comparison.json) and [pooled comparison](pair_cli_pooled_comparison.json)
- [Inventory seal](inventory_seal.json), [execution ledger](progress.md), [plan](plan.md)
- [Environment rebuild record](environment_rebuild.json), [code adaptation](code_adaptation.json)

The complete local `baseline.json`, `path_map_initial.json`, `path_map.json` and `move_journal.jsonl` preserve the original/new paths and group-level recovery trail. The independent backup remains outside the repository at `../.migration_backups/architecture_20261014`. The initial map and receipt remain historical evidence; the later map relocates one already-existing historical test-support table into the locked test area without changing its bytes.

The independent reviewer requested three Important corrections: run-root symlink containment, safe temporary/no-clobber publication and resolved test-asset alias checks. Seven isolated-filesystem tests failed before the fixes; all 62 tests pass afterwards. No unresolved review finding remains.

## Rulings and preserved limitations

- Used the existing approved checkout with a local migration branch and complete backup; a new worktree would omit untracked research assets. Recovery restores the verified original tree and retains the migrated checkout/history.
- Rebuilt the Python environment while preserving installed scientific versions/bytes; added only bundled setuptools/wheel for editable packaging. Reproduction uses the recorded pins; the original environment is retained.
- Preserved old mutating algorithms but guarded their frozen run outputs. Future full recomputation requires a separately configured version; old checkpoint signatures were not rewritten.
- Did not execute acquisition, full rollback, imputation, depth-policy adoption or model fitting/scoring. These remain later explicit tasks, not migration acceptance claims.

Large scientific assets, environments and diagnostic datasets are excluded from Git. Historical code, source receipts and original documents retain their bytes; `.gitattributes` prevents automatic line-ending conversion. Current English usage guides are [README](../../../README.md), [architecture](../../../docs/architecture.md) and [preprocessing](../../../docs/preprocessing.md).

The full 60-field native-source audit was accepted prior evidence; it was not independently repeated against remote NOAA assets during migration. This migration verified retained file identity and adapted-code equivalence rather than asserting new observational or predictive validity.
