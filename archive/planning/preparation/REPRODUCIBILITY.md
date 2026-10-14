# Reproducing and resuming the preparation package

## Authority and inputs

Use the authoritative Excel and preserved authorized stage prompt. `metadata/stage_authority.json`, `config/frozen_before_test.json` and `docs/contract_crosswalk.csv` bind the scope. Original acquisition records remain in the parent `manifests/`, `metadata/`, `geometry/` and `audit/` directories. Do not initialize the acquisition `Snapshot` class or reopen `raw/source_objects` as a complete global Zarr: the cached global source is intentionally partial. The selected `raw/hourly_subset_v2.01.1.zarr` is complete and read-only.

The actual local runtime is `../.venv/bin/python` from this package root, with a new preparation environment lock in `metadata/environment_lock.txt`. The acquisition environment lock was preserved. Source values, source-native QC flags and original metadata are unchanged.

## Read the prepared data

Hourly partitions: `cleaned/<GDP_ID>.parquet`; test counterparts: `restricted_test/cleaned/`.

All source observation fields remain columns. Derived normalized longitude, timestamps, field flags, instantaneous confirmed regime, cell, visit and displacement annotations are separate columns. Join `source_obs` to the frozen raw snapshot and `original_within_traj_obs`; obtain original trajectory index from the parent acquired-ID manifest or raw `source_traj_index`. The dataset-level snapshot hash in the run/checkpoint manifest completes the stable key. Do not interpret a row from a different snapshot as the same source observation.

`origins/` contains all usable D-source hourly positions, retaining actual `in_R`. Mapping and regime uncertainty remain eligible-origin audit inputs, then target/scenario eligibility excludes their affected uses. `events/` contains compact **retrospective** next-event bounds. An observed outside bound is not itself an eligible exit; apply the path/regime predicates in the generator.

Exact R anchor endpoint and stopped ledgers are under distinct directories. Invalid destinations use a null/sentinel index and a reason; they are not outside or observed unresolved-support transitions. Source-linked original rows remain available for every exclusion.

## On-demand integer-day generation

From `/Users/moonedgethug/Documents/UNSW/DATA3001/work_place/data_preprocessing`:

```bash
.venv/bin/python scripts/prep_pairs.py --id 17503 --days 7 --scenario drogued --population R --tolerance 0
.venv/bin/python scripts/prep_pairs.py --id 17503 --days 31 --scenario pooled --population D --tolerance 0
```

`--days` accepts integer days 1–365. Scenarios: drogued, undrogued, pooled. Tolerances: 0 main; 1/2/3 hours sensitivity; 6 diagnostic. Both targets are generated separately. Test IDs automatically route to the restricted output tree. These files supply observed labels, not forecasts.

For lag candidates 1/3/5/7, use the same generator at the required lag and remainder days 1–6. Additional 2tau/3tau diagnostics 2/6/9/10/14/15/21 are supported. Propagation and row normalization belong to modelling, with actual UTC dates advanced at each step.

## Resume complete partitions

Do not rerun acquisition. Cleaning and pair outputs are atomically replaced per ID. Hash-checked checkpoints prevent duplicates. A changed input/config/dependency signature causes the affected partition to be regenerated. The complete source and all source-linked annotations remain intact.

```bash
.venv/bin/python scripts/prep_run.py prototype
.venv/bin/python scripts/prep_run.py clean --split development
.venv/bin/python scripts/prep_support.py process --split development
.venv/bin/python scripts/prep_support.py aggregate --split development
```

A default clean resume checks the entire geometry-module hash. Historical exact geometry/core files are archived under `metadata/code_revisions/`; subsequent changes to tiled area computation, boundary inventory and label annotations leave the source-field cleaning predicates unchanged. Regeneration with current code is reversible and should reproduce the same hourly values/flags. Do not silently modify the authoritative Excel, R, split or target to make a checkpoint match.

For independent disjoint ID batches, use `--ids` on `prep_support.py process`; each writes a distinct run receipt. Combine only identical input/config/D/code signatures, then aggregate. Four workers were used for development; final test used two. No dense observation-by-365-horizon table is required.

Prototype and full-run resource receipts are in `audit/`; per-ID durations are in cleaning profiles/checkpoints. Preparation uses a bounded source-chunk cache, compressed per-ID Parquet and disk-backed aggregation. The state index uses exact cached 5-degree geometry clips for efficiency; it does not approximate or simplify the shoreline.

## Verification

```bash
.venv/bin/python -m unittest discover -s tests -p test_preparation.py -v
.venv/bin/python scripts/prep_verify.py
```

Save a new verification log instead of overwriting a log already bound in a freeze record. The final audit compares all original observation fields against every cleaned row, checks source indices, output hashes, recovered code dependencies, admissible state indices, candidate reconciliation and exclusion of held-out/self peer references. `audit/source_values_reverified.json` separately records fresh checks of all cached source objects and all 60 selected source field value hashes.

`audit/annotation_correction_reconciliation.json` verifies corrected candidate, eligible, outside, return and unique-ID totals equal their pre-correction values. Primary exclusion precedence and secondary predicate counts were correctly recomputed. This correction was driven by synthetic semantic tests, not test outcomes.

## Test isolation and refitting

Keep `restricted_test/` unavailable to tuning and illustration selection. No test outcome selected R/D/grid/scenario/thresholds. Source-based rules and frozen review thresholds were applied only after freezing. The independent verification reads technical invariants, not predictive scores.

`manifests_development_folds.csv` prepares whole-ID five-fold development validation. Within any adopted fold, refit learned references only on allowed training IDs excluding the held-out fold and target ID. The global speed/peer diagnostics are retrospective review outputs; they never changed primary labels and must not be reused as held-out-fold fitted features.

## Optional reconstruction

No reconstruction dependency was introduced. Any future masking/reconstruction diagnostic needs a separate method, uncertainty, provenance and grouped validation record. It cannot overwrite these source-supported labels, add independent drifters or enter primary transition counts without a versioned architecture decision.
