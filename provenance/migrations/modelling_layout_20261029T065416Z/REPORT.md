# Modelling source organisation

The user approved organising code by responsibility while entering the empirical-matrix consolidation stage. The scientific workbench remains pooled with known initial velocity. This operation did not fit a new model or change a scientific definition.

## Changes

- Moved 53 formerly flat Python modules into family/shared packages: 31 Markov, 6 continuous Gaussian/MDN, 13 direct-baseline and 3 shared modules.
- Extracted 14 existing shared classes/functions into four additional common modules: runtime, probability, geometry and plotting. Their original bodies are preserved.
- Added package-local compatibility forwards for all 53 historical module paths. Imports resolve to the same implementation objects; old module commands forward through `runpy`.
- Adapted the vendored chart resource, native-source location and continuous source-identity paths to the new locations. The native binary cache remains at its historical local location; no workflow plugin was invoked.
- Updated current documentation and added one code guide with a complete active-module inventory. Historical experiment reports and receipts remain unchanged.

## Verification

`verification.json` records 219 passing tests, zero failures/errors/skips, 53 checked legacy aliases, package discovery, verified pre-change snapshots and 943 reverified sealed output entries. Tests include five new checks covering module identity, shared ownership, optional-dependency isolation, CLI compatibility and resources. The test process denied access to the actual final-test directory.

An AST comparison of every migrated top-level class/function found 350 unchanged definitions after normalising imports and relocated module/path strings. The only other function change is `showcase._document`, whose asset lookup now reaches the same pinned chart library from its new directory. Existing scoring, transition, boundary, numerical-integration and frozen-diagnostic semantic tests pass. These checks establish layout compatibility, not additional predictive validity.

## Preservation and recovery

The local `before/` directory preserves 112 pre-change source/document/config files, including the actual uncommitted continuous-model code and modelling plan. `migration.json` lists their SHA256 values, the old-to-new module map and extracted symbols. The snapshot is small source-only recovery evidence; no data tree or large cache was copied. The original reorganisation did not stage, commit, push or reset Git.

The subsequent user-authorised architecture publication includes the reorganised source, supporting configuration/tests, guides and this compact migration record. The recovery snapshot, runtime logs and continuous experiment result bundles remain local. Published snapshot-verification fields describe the local audit; a fresh clone does not contain `before/` and cannot repeat that part without the retained snapshot. Publishing the architecture does not resume any model experiment.

Historical run checksums must not be replaced with the new source hashes. Matching old import names does not imply that current source bytes reproduce a historical run identity. Stopped-run resume guards remain effective. If recovery is required, compare the snapshot with current work before restoring individual files; do not overwrite subsequent edits or execute the one-time migration again.

The current guide is `docs/code_guide.md`, with scientific stage boundaries in `docs/modelling_round1_plan.md`. No new shrinkage, seasonal, hidden-state, grid or regional experiment was run.
