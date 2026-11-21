# Step 5 E4 — MDN K refinement, approved execution record

Date: 2026-11-09 (Australia/Sydney). Status: APPROVED FOR FULL EXECUTION by the user's instruction to add K=3,6,12,18,20,22 and train on the complete data. This records the agreed refinement; it does not reopen E3 or change its results.

## Scientific definition

The governing scientific definition is [E3](conditional_mdn_s5_e3_contract.md), SHA256 `13f9a5f8cd17dc7f5de0fe1ee54cac87a9eeb9d5efdca00aae2bfd8a9521fea4`. The only model-search change is the candidate roster:

- Existing, read-only reuse: **1, 2, 4, 8, 16, 32**.
- Newly fitted: **3, 6, 12, 18, 20, 22**.
- Final registered roster: **1, 2, 3, 4, 6, 8, 12, 16, 18, 20, 22, 32**.

This is an adaptively motivated development refinement, not a new independent test. The result is the selected model within these candidates and the unchanged architecture, not a global optimum. K is not a guaranteed number of geographical modes.

Preserve seven-day own-pair displacement, exact longitude/latitude inputs, 2→64 tanh→64 tanh→6K architecture, CPU float64, covariance floor 0.001, AdamW settings, pair-equal NLL fitting, whole-ID early stopping, all three registered seeds, 500-epoch cap semantics, and fresh full-pool refitting at the training-only selected epoch/seed. NLL is the training loss; ES is the comparison score. No thinning, new features, coastal correction, model blending, seed ensemble or additional hyperparameter search.

## Complete roles and selection

| Role | Training pairs / IDs | Evaluation pairs / IDs |
|---|---:|---:|
| C_T0 | 170,978 / 234 (2001–2013) | 41,761 / 50 (2014–2016) |
| C_T1 | 209,934 / 280 (2001–2016) | 44,612 / 58 (2017–2019) |
| C_outer | 265,393 / 338 (2001–2019) | 33,971 / 45 (2020–2022) |

Use the existing frozen source keys, no overlapping fit/query IDs and no cross-boundary fit labels. Preserve accepted source-boundary exceptions. The 517 final-test IDs stay locked. Do not use outer outcomes to select K, epochs, seeds, thresholds or region shapes.

All 12 K enter the unchanged E3 selection: two-window ES no worse than MDN1, pooled relative ES gain at least 0.1%, numerical resolution, paired-ID one-SE preference for smaller K, then the original region/geographic gate for the provisional candidate only. If it fails, select K=1, without trying successive runners-up. Recompute selection across the expanded roster, not just the new candidates. Report all candidates; no outer reselection.

## Scoring and acceptance

Keep drifter-equal aggregation, identical cross-window ID handling, WGS84 ECEF chord ES, full mass including land/tails, and the single LAEA distribution-quantile 90% ellipse. Keep the auxiliary loss unchanged. Retain ExactPoint, EndpointCI and LocalGaussian with exact source-key alignment. No B2 ES addition in this run.

Start at the already-validated 65,536 ES nodes (eight scrambles), 65,536 region nodes; preserve independent all-query numerical streams, fixed 128-query IID/density checks and registered escalation to 131,072/262,144 only when required. ES precision, region precision and all statistical/quality acceptance conditions remain exactly those in E3 §§8–11. Negative findings are a completed research result; incomplete or numerically invalid scoring is not.

## Reuse, implementation and integrity

Parent: `conditional_mdn_s5_e3_20261108T055830_797628Z/formal_v1`. Verify its complete passing audit, hashes, frozen cohorts, parameter arrays, stream identities and scoring levels. Existing checkpoint and manifest bytes remain unchanged and retain their E3 provenance. Import copies into the new run only with an explicit source receipt; never rewrite them to imply E4 fitting. New K have 6 × 3 roles × (3 early-stop fits + 1 full refit) = **72 new fits**; 72 parent fits are reused.

Reuse parent score rows only after the new role's complete 12-model forecast and scoring freezes, with exact parameter, query, mode, node-level and stream compatibility. If a registered precision escalation needs unavailable parent rows, compute those rows at the required level without changing the forecast. No scalar-table-only reuse.

Use an independently named E4 engine and run. Preserve frozen E3 source files, contracts, data, weights and results. The E4 engine is a documented derivative of E3's verified implementation, with mechanical experiment-path/identity changes, explicit candidate registry expansion and narrowly scoped reuse handling. Mathematical kernels and seed namespaces remain unchanged. Prove shared-K numerical/training equivalence and provenance rejection cases before full execution.

## Resources, delivery and stopping

Continue the user's explicit full-MDN resource waiver: no arbitrary elapsed-time cutoff or sample/precision reduction. Keep CPU training ≤4 threads, scoring ≤2 spawn workers with single-thread BLAS, resource monitoring, atomic resumable shards and a physical free-disk floor of 2 GiB. Report nonfinite parameters, selected near-cap epochs, source drift, storage availability or unresolved maximum-precision failures; preserve progress. No paid/cloud compute is authorized or required.

Deliver complete model/checkpoint registry, internal choice, full outer per-query/per-ID tables, ES/H90/area comparisons and intervals, resource ledger, independent audit and inference entry point. Defer visualization, dashboard edits, baseline ES extension, coastal diagnostics and presentation/report authoring as requested. Do not modify the protected research stage ledger or publish to GitHub during this execution.

After this registered roster is complete, do not add more K or change the training configuration without a new user decision.
