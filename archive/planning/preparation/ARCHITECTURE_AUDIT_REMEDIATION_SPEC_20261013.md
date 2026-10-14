# Architecture audit remediation implementation plan

> For agentic workers: execute these data-preparation tasks in order, with regression evidence and a durable progress receipt. Existing user authorization permits reversible preparation without repeated confirmation. Git, prediction-model fitting, contract edits, publishing and cross-chat messages remain outside this stage.

**Goal:** complete the architecture audit's data handover requirements without changing the research definitions or claiming predictive accuracy.

**Architecture:** retain the audited preparation as a historical baseline. Add versioned geometry and support outputs under `preparation/remediation_20261013/`; correct source-position versus geometry attribution in the on-demand label generator. Keep depth-policy-dependent changes pending an explicit architecture decision.

**Tech stack:** existing Python environment, NumPy, pandas, DuckDB, PyArrow, Shapely and WGS84 geodesic areas.

**Authority:** `outputs/01a09d9c-2168-7d51-8b63-87eb559bf139/data_contract_v1.0.xlsx`, verified SHA-256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`; preserved `docs/AUTHORIZED_STAGE_PROMPT.txt`; architecture findings supplied on 2026-10-13 and preserved independent audit JSON. This plan is a contract implementation crosswalk, not a parallel research contract.

## Constraints and review focus

- Preserve source records, all acquired IDs, R/D polygons, native grid indices and global split; no acquisition restart or label reconstruction.
- Keep train and validation separate. Test support, if technically refreshed, belongs only under `restricted_test/`; it cannot select settings. This batch uses development support only; a source-coordinate census may read test technical invariants.
- Preserve the original freeze and receipts. Archive exact pre-correction code, bind all new dependencies and explain that the old verifier's current-code hash check applies to its historical revision.
- Many hourly labels are overlapping observations, not independent measurements. ID counts must be distinct unions; dominant-ID share must use each ID's total in the reporting unit.
- Cover boundary-only R/D contact, land-only overlap, polygon holes, invalid coordinates with mapping false, independent simultaneous failures, and failures after a qualified exit.

## Task 1: regional wet areas and whole-R release weights

**Contract:** 01/02/06/14/20/30. **Input fields:** frozen cell bounds, R/D polygons and high-resolution GSHHG L1 water complement.

**Outputs:** versioned `state_index.parquet` retaining all baseline columns, plus `wet_area_in_R`, `wet_area_in_D` (km²), `R_boundary_only`, `R_positive_area`, `D_positive_area`, and `whole_R_release_weight`. `D_boundary_only` remains explicit.

**Predicate:** clip water geometrically to `cell ∩ R` and `cell ∩ D`; line/point contact has zero area. Region contact and usable positive water area are different predicates. Weight = positive R wet area / sum of R wet areas within that resolution, otherwise zero. Unsupported operator cells retain their assigned release mass for downstream unresolved-support treatment.

**Boundaries:** a boundary-touching cell can carry an observed boundary point yet receives zero area release mass. Land-only overlap receives zero water release mass. Preserve component counts and within-cell empirical prior; area weighting does not create uniform subcell observations.

- [x] Add meaningful area/contact and normalization regression fixtures, then implement regional clipping helpers in `scripts/prep_handover.py`.
- [x] Produce 1° and aligned 0.5° augmented indices without replacing the baseline index.
- [x] Audit nonnegative areas, positive-area weights, unit mass, unchanged cell inventory, and R/D area totals. WGS84 geodesic polygon edges approximate latitude-parallel edges; report resolution/direct-geometry discrepancies rather than require false exact additivity.

## Task 2: short-lag/remainder support with independent-ID evidence

**Contract:** 03/12/16/24/25/28. **Inputs:** existing `support/lags/<ID>.parquet`, actual per-ID eligible counts, frozen split and 1° state index.

**Reporting grain:** split × D-source cell × departure season × scenario × days × target; annual summaries omit season before aggregating each ID. Endpoint and stopped remain separate.

**Fields:** candidates, eligible, candidate_IDs, eligible_IDs, dominant_ID_pairs, dominant_ID_share, availability; annual summaries add number/list of seasons with eligible IDs. Include days 1–7 and 9/10/14/15/21. Enumerate `h=q*tau+r` for tau 1/3/5/7 and all integer horizons 1–365; r=0 needs no extra kernel.

**Boundaries:** zero eligibility yields zero eligible IDs and undefined concentration, not zero concentration. An ID spanning seasons counts once annually. Show all four seasons for cells with annual candidates, including zero-candidate seasons. No ID minimum certifies predictive validity; no lag is selected in this batch.

- [x] Add distinct-union/concentration and zero-support regression fixtures.
- [x] Reuse per-ID aggregates to write seasonal, annual and coverage tables and exact-duration requirements.
- [x] Reconcile existing candidate/eligible totals exactly and verify each per-ID input's grain and split. Save input hashes.

## Task 3: depth and hardware stratification; architecture decision boundary

**Contract:** 08/16/19/23/26/31. **Inputs:** native `DrogueCenterDepth`, `typebuoy`, `location_type`, GDP ID/split; actual D/R origins and per-ID anchor/lag support.

**Strata:** exact recorded 15 m; exact recorded 10 m; other positive recorded depth; missing depth; zero/nonpositive/nonfinite depth recorded but unresolved. Preserve native values and hardware spelling; do not infer depth from an SVP name or recode zero to 15 m. A recorded depth is metadata, not proof of actual operating immersion.

**Outputs:** per-ID and depth/hardware/location-stratified origin, 7/30/90/180/365 anchor, and short-lag support; counts and distinct-ID concentration separated by split/population/target/scenario. Origin-state support (`regime=1`, usable mapping) is different from fixed-drogued interval eligibility.

**Architecture issue DEPTH-01:** decide which recorded depths/hardware may enter the primary near-15 m scenario, how unknown/nonpositive depth is handled, and which comparison scenarios are required. Retain all records and the existing labels. No primary filter changes until this decision is recorded and versioned. A sensitivity cohort is a different declared mixture, not independent new observations.

- [x] Audit origin and interval support, preserving source metadata and all ID strata.
- [x] Reconcile the supplied 17-ID/41,879-origin finding; separately investigate nonpositive depth, which that finding may not include.
- [x] Publish the exact architecture decision inputs and pending policy status; do not fit a mixed-depth operator or claim equivalence.

## Task 4: explicit 365-day and grouped-fold coverage

**Contract:** 04/07/10/16/17/27/28. **Inputs:** existing R per-ID anchor summaries and frozen five-fold manifest.

**Outputs:** train/validation 365-day cell-season support including zero/single-ID cells and dominant shares; complete 5-fold × 4-season × target/scenario R coverage grid, plus annual coverage. Zero-case held-out folds are `not_evaluable`; loss/calibration remain uncomputed, never zero.

**Boundaries:** union IDs across cells; preserve all five folds even when empty. Annual pooling or bootstrap replication does not establish missing seasonal evidence. The modelling stage must retain 365-day annual/seasonal-shrinkage analysis and report unevaluable groups; choose settings on development evidence and evaluate 7/30 days on common target/cases.

- [x] Build coverage from existing per-ID sufficient counts, including empty folds.
- [x] Reconcile the independent audit's R anchor totals and empty winter/spring stopped folds.
- [x] Report sparse 365-day cell support without turning it into a correctness/accuracy percentage.

## Task 5: source-position reason branch correction

**Contract:** 09/11/23. **Files:** modify `scripts/prep_core.py` and `scripts/prep_pairs.py`; add regressions to `tests/test_preparation.py`.

**Fields/predicates:** source path failure = `~position_ok`; pure geometry failure = `position_ok & ~mapping_ok`; missing expected timestamp remains separate. Store independent next failure times and per-label booleans. Preserve the combined first-bad bound for eligibility compatibility.

**Reasons:** an invalid source position alone before the required stopping time gives `incomplete_path` (6), not `geometry_uncertain` (9). Pure geometry failure gives 9. Both retain both explicit predicates; published geometry-before-incomplete-path primary precedence remains deterministic. Invalid origin gives 1. Endpoint-only eligibility remains independent of intermediate position gaps when regime is confirmed. Failures strictly after qualified exit do not cancel stopped outside.

- [x] Reproduce the old branch with a failing invalid-coordinate/mapping-false regression; add pure-geometry, simultaneous-failure, post-exit and endpoint-only cases.
- [x] Add separate event bounds and label annotations; expose them in newly generated pair/event outputs. Historical compact events remain their original schema and are not direct inputs to the generator.
- [x] Run the entire preparation test suite and a full source-position technical census. Compare old/new labels on development cases with existing valid-source conditions; verify unchanged eligibility/outside counts.

## Acceptance and handover

- [x] Write one versioned freeze/manifest binding authority, geometry, configuration, archived baseline code, new code, input partitions and output checksums.
- [x] Independently verify totals, schemas, release weights, ID unions, zero-support groups and unchanged protected files; record measured resource cost.
- [x] Deliver a readiness addendum identifying completed additions, DEPTH-01 awaiting architecture policy, and predictive validation still unperformed. The accepted core is not withdrawn by a semantic reason correction with no affected snapshot coordinates.

The next modelling gate is 1° annual and seasonal short-lag operators with 7/30-day probability scores/calibration and explicit 365-day limits. 0.5° modelling, broader regional transfer and object-specific claims remain later validated work. This preparation batch supplies evidence and release priors, not predictions.

## Execution record

Completed data additions on 2026-10-13 (Australia/Sydney). Verification: `remediation_20261013/audit/verification.json`; 41 tests pass. DEPTH-01 is still pending: the checked depth tasks above concern evidence preparation, not adoption of a primary depth policy. No model was fitted. Existing labels and the global split remain unchanged.

Resource adjustment: initial unbatched duration aggregations exceeded the configured DuckDB memory budget. Batched aggregation by duration completed with identical count definitions; measured process memory includes Python and exceeds the DuckDB-only budget. Empty native Parquet partitions require name-based schema union in verification.
