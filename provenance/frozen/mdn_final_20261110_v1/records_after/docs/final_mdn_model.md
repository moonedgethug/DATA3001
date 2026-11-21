# Final MDN model decision — 10 November 2026

**Status: user-approved final recommendation and frozen MDN candidate set.**

The user approved MDN22 as the final recommended model, MDN1 as the comparator, and closure of further K search. This document records that decision; it does not change the completed experimental contract or its acceptance result.

## Final choice and historical contract are separate records

| Record | Preserved conclusion |
|---|---|
| Final recommendation after development-validation review | **MDN22** |
| Retained simple comparator | **MDN1** |
| Original E4 training-only provisional ES choice | K=3 |
| Original E4 contract-selected primary | K=1, after K=3 failed the quality gate |
| Original primary model's strict overall acceptance | **Not passed** (`overall_retention=false`) |
| Current action | Freeze saved models/results and stop K search; no refitting or revised acceptance test |

The final choice accepts a modest area increase relative to MDN16 in exchange for lower average ES and higher actual coverage. It is a documented decision made after examining development validation. It is not a claim that MDN22 won the original training-only procedure, passed the original strict acceptance, is statistically significantly better, or is globally optimal.

## Frozen numerical evidence

Run: `conditional_mdn_s5_e4_20261109T082930_653149Z`. The final full fits use 265,393 pairs from 338 training drifters (2001–2019); evaluation uses all 33,971 pairs from 45 drifters (2020–2022). Prediction horizon is seven days. Training remains pair-equal NLL; evaluation remains drifter-equal ES and the original single-ellipse 90% region. There are no excluded evaluation queries.

| Model | ES (km), lower is better | Actual H90 | Mean 90% area (km²) |
|---|---:|---:|---:|
| **MDN22 — final recommendation** | **128.245036** | **90.1769%** | **184,803.369** |
| MDN1 — retained comparator | 128.701716 | 87.6301% | 175,929.087 |
| MDN16 — historical comparison | 128.783605 | 89.6214% | 181,776.207 |

Relative to MDN16, MDN22 has 0.4182% lower ES, 0.5555 percentage points higher H90 and 1.6653% larger area. Relative to MDN1, the corresponding changes are −0.3548%, +2.5468 percentage points and +5.0442%. Among the MDN candidates whose observed mean H90 is at least 90%, MDN22 has the lowest average ES and smallest mean area on this development cohort. This is a descriptive comparison, not a newly preregistered selection rule or proof of calibration.

All **12 candidates** are retained: K = **1, 2, 3, 4, 6, 8, 12, 16, 18, 20, 22, 32**. The freeze includes all three roles (C_T0, C_T1, C_outer), 144 checkpoints (72 new fits and 72 verified reused parent fits), forecasts, score tables, original controls and audit evidence. The original contract, experiment registry, selection and acceptance files remain byte-identical.

- [All candidate and control results](../results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1/summary.csv)
- [Original internal selection](../results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1/selection.json)
- [Original acceptance](../results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1/acceptance.json)
- [Passing independent engineering audit](../provenance/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1/final_audit.json)
- [Final-choice checkpoint pointers](../provenance/frozen/mdn_final_20261110_v1/decision.json)
- [Frozen file inventory](../provenance/frozen/mdn_final_20261110_v1/manifest.json) and [freeze verification](../provenance/frozen/mdn_final_20261110_v1/verification.json)

## Using the intended saved model

The final recommendation is the existing full-refit checkpoint at `results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1/C_outer/K22/full_refit/checkpoint.pt`; no training is required. Its SHA256 is `216f92b678e25b1c804a7f0a1928779b9233ff22f7140536e825969df6d176b0`.

Use the existing `conditional_mdn_s5_e4_inference.from_checkpoint(path, sha256=...)` API with the checksum-bound path in the final-choice record. `load_selected_model(run)` intentionally continues to load the **original contract-selected MDN1**. It is not the loader for the later MDN22 recommendation. Both pointers are explicit in `decision.json`; predictions still return the complete seven-day displacement distribution without clipping or reweighting.

## Freeze and interpretation boundaries

Payload files and directories are read-only and bound to SHA256 digests; the original complete run is sealed in place rather than duplicated. A detached manifest digest and a full re-read verification record accompany the freeze. Snapshots retain the audit-era ledger/source documents and the newly approved records. Updating the live ledger therefore does not erase the original audit-era bytes; historical audit reconstruction uses the recorded before-snapshot mapping for this authorised documentation amendment.

The 2020–2022 data are repeatedly examined development validation. The 517 final-test IDs remain locked. Keep the historical strict-acceptance failure in the report alongside the user-approved final choice. Further changes require a new explicit decision and a new version; preserve this freeze. Visualization and publication are deferred. This closes MDN K search, without claiming that all remaining research or reporting tasks are complete.
