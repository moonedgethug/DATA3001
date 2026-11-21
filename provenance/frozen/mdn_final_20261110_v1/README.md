# Frozen MDN models — 10 November 2026

Final recommendation: **MDN22**. Comparator: **MDN1**. Further K search is closed by explicit user decision.

`decision.json` gives exact, checksum-bound checkpoint paths for both models and all twelve retained candidates. Paths in these JSON records are relative to the repository root. `manifest.json` seals the complete E4 results/provenance runs in place and the before/after documentation/source snapshots; `manifest.sha256` is its detached digest. `verification.json` records the subsequent complete independent hash/mode/roster/inference check.

The original experiment remains unchanged: provisional K=3, contract-selected K=1, original primary overall acceptance false. The final MDN22 choice was approved after reviewing development validation; it is not a retrospective pass or independent final-test result. The historical `load_selected_model` still loads contract-selected MDN1. Use the explicit-checkpoint API and the MDN22 pointer in `decision.json` for the final recommendation.

The old audit binds the pre-amendment research ledger. Its exact bytes are preserved under `records_before/docs/research_stage_ledger.md`; the approved live-ledger update is preserved under `records_after`. The decision records both hashes. Original audit/selection/acceptance files were not rewritten.

Files are read-only, with every sealed payload file hashed. This is a local versioned freeze, not a remote backup or a cryptographic signature. Future authorised changes must use a new version and preserve this one. No training, rescoring, visualization, Git publication, or final-test access is part of this freeze.
