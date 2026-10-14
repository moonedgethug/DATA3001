# Data preparation handover addendum — 2026-10-13

The architecture audit accepted the core preprocessing. This addendum supplies the requested regional release areas, depth/hardware evidence, short-lag ID support and corrected failure attribution. The authoritative Excel remains Data Contract v1.0; this is an implementation revision, not a new research contract. **Primary depth-mixture policy remains pending architecture decision DEPTH-01. Prediction accuracy has not been evaluated.**

Read the [execution specification](../docs/ARCHITECTURE_AUDIT_REMEDIATION_SPEC_20261013.md), [verification receipt](audit/verification.json) and [versioned manifest](handover_manifest.json) alongside the original readiness report. The original frozen index, ledgers, support tables and verification receipts remain historical artifacts. Use the augmented index in this directory for whole-R release preparation.

## Delivered additions

| Architecture finding | Implementation and evidence | Status |
|---|---|---|
| Whole-R weights require water inside R | `geometry/state_index.parquet`, `geometry/area_policy.json` | Regional areas and unit-mass weights prepared |
| Drogued does not guarantee recorded 15 m depth | `support/depth_*`, `audit/depth_findings.json` | Stratification complete; DEPTH-01 pending |
| Short-lag counts need IDs/concentration/seasons | `support/lag_support.parquet`, `lag_annual_support.parquet`, `lag_seasonal_coverage.parquet`, `D_lag_*_totals.csv` | Completed without selecting a lag |
| 365-day support remains sparse even in five folds | `R_365_cell_season_support.parquet`, `R_grouped_fold_coverage.csv`, `audit/annual_support_limits.json` | Empty groups explicitly not evaluable |
| Source failure was labelled geometry uncertainty | Current generator, new regression cases, `audit/source_reason_correction.json` | Corrected; no existing snapshot eligibility effect |

## Regional areas and release prior

The augmented state index preserves every baseline column and every cell ID. New `wet_area_in_R` and `wet_area_in_D` values are in **km²** and measure `cell ∩ region ∩ water`. `R_boundary_only` means contact without positive geometric area; `R_positive_area`/`D_positive_area` concern polygon overlap, which can still contain no water.

For each resolution, `whole_R_release_weight` is R water area divided by the sum of R water areas. Zero-area cells receive zero weight. Do not substitute full-cell `wet_area_km2`, normalize only supported cells, or turn these weights into a uniform subcell prior. Empirical within-cell origin sampling remains the contracted prior; unsupported operator mass remains visible downstream.

| Resolution | States | R-intersecting cells | R boundary-only cells | Full-cell water summed over R contacts | Water inside R |
|---|---:|---:|---:|---:|---:|
| 1° | 2,664 | 54 | 13 | 508,201.93 km² | 334,501.77 km² |
| aligned 0.5° | 10,437 | 180 | 36 | 433,101.75 km² | 334,503.06 km² |

WGS84 polygon areas use correctly oriented exteriors/holes. Clipping adds vertices to degree-coordinate boundaries, so geodesic edge approximations produce a small cross-resolution difference; each resolution normalizes its own partition. Preparing 0.5° geometry does not promote 0.5° modelling.

## Depth and hardware evidence

Native `DrogueCenterDepth`, `typebuoy` and `location_type` are preserved. No depth is inferred from a hardware name. Audit strata distinguish recorded 15 m, recorded 10 m, other positive depth, missing depth and unresolved nonpositive/nonfinite depth.

The supplied finding is reproduced: 17 development IDs with recorded 10 m or missing depth contribute **41,879** usable instantaneous drogued D origins. Additionally, IDs **7706157 and 7706158** record depth **0 m** and contribute **3,022** such origins. The source field dictionary documents metres and NaN fill, but does not establish a physical interpretation for zero. Retain and isolate it; do not replace it with 15 m. None of these non-15 m/unresolved usable drogued origins lie in R.

Origin counts describe usable mapping and confirmed instantaneous state. The anchor and lag tables separately audit **constant-regime interval eligibility** for endpoint and stopped targets. A source-origin count is not an eligible transition count.

DEPTH-01 requires architecture to state the primary allowed depth/hardware mixture, the treatment of missing/nonpositive depth, and the sensitivity comparisons. Both a recorded-15 m restriction and a declared mixed-depth scenario need an explicit protocol decision before changing primary model inputs. All existing data and labels remain retained; no physical equivalence or predictive benefit has been asserted.

## Short-lag and remainder evidence

The new lag table is **long format with an explicit `target` column**; the baseline lag table remains its original wide format. Grain is split × D-source 1° cell × departure season × scenario × exact days × target. It includes days 1–7 and memory-check days 9/10/14/15/21, distinct candidate/eligible IDs, dominant-ID count/share and availability. All four seasons are shown for every cell with annual candidates, including zero-candidate seasons.

Annual concentration first sums each ID over seasons and cells in the selected reporting unit, then takes the maximum. ID counts use unions; they must not be summed across seasonal or cell tables. Zero eligibility has undefined dominant share. `support_status` describes observed support only and is not a scientific sufficiency threshold.

`exact_duration_kernel_requirements.csv` enumerates all 1–365-day outputs for lag 1/3/5/7 with `h=q*lag+r`. Remainder zero requires no extra kernel. This is an input requirement list, not fitted kernels or forecasts. Regional totals in `D_lag_annual_totals.csv` have low regional concentration but do not establish adequate support for each local cell/season.

## 365-day evidence and modelling handover

The independent audit's R 7/30/365-day eligible-hour and ID totals reconcile exactly. Training fixed-drogued stopped support has **145** cell–season combinations with candidates: **55** with no eligible ID and **45** with one ID. Median dominant-ID share in supported combinations is **97.73%**. Of the five grouped development folds, **two DJF** and **three MAM** stopped folds have zero evaluable 365-day cases. SON also has two empty stopped folds.

The complete 750-row grouped-fold table includes annual and all four seasons for all three scenarios, both targets and 7/30/90/180/365 days. `not_evaluable` means no eligible held-out cases; it is not a score of zero. No score is calculated in this batch.

The next model stage remains the 1° annual and seasonal core with development-selected lag, annual shrinkage and whole-ID validation. Assess probability distributions and calibration at 7/30 days on common target/cases, retain 365-day annual/seasonal analysis and explicitly report unavailable combinations. More bootstrap replicates, five-fold regrouping or generated daily output cannot create independent seasonal evidence. Final test remains locked for selection.

## Failure attribution and schema compatibility

The corrected source-position failure predicate is `~position_ok`; pure geometry failure is `position_ok & ~mapping_ok`. Separate event bounds retain both failures. Source invalidity alone before the required stopping time is reason 6 (`incomplete_path`), while pure mapping failure is reason 9. Simultaneous predicates remain visible; geometry-before-incomplete-path primary precedence is retained. A qualified early exit still absorbs later source failures, death and state changes.

Newly generated labels expose source/geometry booleans; newly generated compact events expose separate failure times. Historical compact events and R anchor ledgers retain their original schema. The generator recomputes event bounds from cleaned records; it does not consume old compact-event files as a replacement for those calculations.

The technical census checked all **39,107,061** positions and found no unusable source positions or invalid native coordinates. Old/new code was compared on **17 development IDs, 306 label calls and 435,528 target eligibility cases**; all pre-existing label fields matched. This comparison is a sample of labels, not full independent semantic recalculation. The regression suite has **41 passing tests** including actual bug reproductions and area/ID-union cases.

## Reproduction and version control

From `work_place/data_preprocessing`, use the existing environment:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/prep_handover.py areas
.venv/bin/python scripts/prep_handover.py lags
.venv/bin/python scripts/prep_handover.py depths
.venv/bin/python scripts/prep_handover.py coverage
.venv/bin/python scripts/prep_handover.py source_reason
.venv/bin/python scripts/verify_handover.py
```

Run support actions sequentially on a laptop. The lag/depth aggregation is batched by duration, with a 1,500 MB DuckDB limit and two threads; Python/DataFrame memory is additional. Measured lag/depth processes use approximately 2–3.4 GB maximum resident memory; see final run logs for times and measured memory. No acquisition constructor or network call is involved. Rerunning produces a new receipt and may change file byte ordering; renew the handover manifest after a rerun rather than reuse stale checksums.

The original `frozen_before_test.json` and package manifest were not rewritten. Exact previous core/pair code and test bytes are retained under `baseline/`, matching their recorded SHA-256 values. The old `prep_verify.py` checks that historical current-code freeze and will reject updated current code; use the new `verify_handover.py` for this addendum. Do not manipulate old hashes to make it pass. Original pair checkpoints remain bound to their historical code signature; a default full pair resume with updated code would regenerate partitions and is unnecessary for this addendum.

`input_partition_hashes.json` binds all consumed per-ID aggregates and source-linked origin inputs to their existing checkpoints. `handover_manifest.json` binds the additions, current code, archived baseline, authority and geometry. Read `audit/verification.json` for exact verification scope. The prior full raw-field comparison is accepted baseline evidence and has not been misrepresented as repeated by this narrower audit.
