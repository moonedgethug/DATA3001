# Hourly preparation implementation plan

> For agentic workers: use superpowers:executing-plans inline. User authorization already covers execution; the stage prompt prohibits Git and external messaging.

**Goal:** Produce source-linked hourly annotations, distinct endpoint/stopped ledgers, and reconciled observational support under the final Excel.

**Architecture:** Open the existing complete selected Zarr read-only. Append derived partitions under `preparation/`, keyed by source observation index. Compute path event bounds once per trajectory and generate arbitrary integer-day labels on demand. No imputation or transport model fitting.

**Tech stack:** Python, Zarr 2, NumPy, Parquet, Shapely, WGS84 geodesics, versioned GSHHG 2.3.7.

**Spec:** Attached stage prompt and `metadata/contract_aspects.json`, extracted from the verified authoritative Excel; original hash `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`.

## Constraints

- Preserve original acquisition receipts, complete trajectories and frozen whole-ID splits.
- Every usable hourly R/D location is a candidate; equal eligible pairs remain the primary unit.
- UTC elapsed days, exact main matching; tolerance 1/2/3 hours, diagnostic 6 hours.
- Endpoint and stopped eligibility remain separate. A qualified early exit absorbs later horizons.
- Source-specific SST/uncertainty/velocity flags do not act as universal position rejection.
- Development evidence selects D. Freeze geometry and rules before processing separated test products.
- Document unresolved semantics and isolate their affected uses. Prediction accuracy is deferred.

## Review focus

1. Native invalid longitude must not become valid after normalization.
2. Equal flags across a gap cannot alone prove fixed regime.
3. Exit after a gap cannot become first-exit evidence; exit before later death remains eligible.
4. Negative anomaly and legitimate zero velocity remain usable; missing/negative uncertainty stays separate.
5. A resumed partition is reused only if configuration, code, input and output hashes agree.

## Executable batches

- [x] Authority and source verification: 31-aspect crosswalk, source dictionary, rule register, unresolved log; hash-bound read-only input audit.
- [x] Semantics prototype: failing synthetic regression suite, implement `prep_core.py`; verify the five specified source cases, actual-time geodesics and resource use.
- [x] Development hourly annotations: `prep_run.py clean --split development`, full R IDs first then downstream IDs; preserve all rows and raw references.
- [x] Candidate D audit and freeze: `prep_geometry.py`, nested domains, complete intermediate R paths, downstream support/exits/returns, mask and cost; retain an explicitly stopped-domain product if predictive boundary stability remains unperformed.
- [x] Ledgers and support: `prep_pairs.py`, compact origin/event ledgers, exact 7/30/90/180/365 R ledgers, D support and lag/remainder inputs, on-demand integer days 1–365, both grids and tolerances.
- [x] Frozen test application and independent verification: separate output tree, technical invariants only in main report; no test evidence feeds selection.
- [x] Handover: support figures, reconciliation, run/output hashes, reproducibility and explicit readiness limitations.

## File responsibilities

- `scripts/prep_core.py`: pure field, duplicate, regime, grid, visits, path and endpoint rules.
- `scripts/prep_io.py`: read-only source linkage and hash-bound checkpoints.
- `scripts/prep_geometry.py`: versioned ocean mask, nested domain evidence and wet state index.
- `scripts/prep_run.py`: per-ID cleaning, source-case audit, diagnostics.
- `scripts/prep_pairs.py`: reproducible origin/event and endpoint/path generation.
- `scripts/prep_support.py`: split-specific streamed aggregation and figures.
- `scripts/prep_verify.py`: independent reconciliation, artifacts and handover.
- `tests/test_preparation.py`: consequential semantics exercised independently of data volume.

The acquired-envelope candidates are reused as candidates, not adopted as D by default. GSHHG dependency acquisition is bounded and separate from drifter acquisition.
