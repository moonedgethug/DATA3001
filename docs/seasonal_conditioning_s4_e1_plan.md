# Step 4 E1 — Departure-Season Information in Direct Transition Forecasts

**Version:** S4 E1 v1, 2 November 2026 (Australia/Sydney).  
**Status: ENGINEERING PROPOSAL FOR USER REVIEW — NOT APPROVED FOR DEVELOPMENT OR EXECUTION.**

The user approved Step 4 direction and requested planning. This document proposes the first finite experiment; its formulas, selection rules, budgets and acceptance criteria require confirmation before implementation. Read the [architecture and decision log](time_environment_s4_architecture.md). Old experiment files and final-test isolation remain intact.

## 1. Questions and limits

1. Do qualified destination distributions differ descriptively across departure seasons, with enough independent drifter support to interpret those differences?
2. Does knowing departure season improve held-out Brier relative to a matched annual estimator?
3. Does a selected seasonal forecast preserve actual H90 and geographic K90 relative to retained benchmarks?

These are different questions. Different fitted maps are not by themselves evidence of a real seasonal effect, and a small Brier gain is not automatic quality-preserving replacement.

Keep direct 7/30-day predictions, annual versus seasonal conditioning of the same qualified pairs, 1-degree cell-conditioned origins, pooled drifter regimes, frozen R/D/E, raw-pair fitting and equal-ID/equal-origin evaluation. No new environmental data, velocity, exact-point displacement, path translation, recursive propagation or new score is included in E1.

## 2. Inputs, seasonal definition and information separation

Reuse these sealed development-only sources:

- `results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet` and its `release_labels/` source-key tables, source summaries and provenance receipt.
- `results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv` and its provenance.
- Current contract/manifest/schema and frozen state/R/D/land assets required for source identity, support strata and reporting.
- S3 E2 frozen outputs for control regression **after new outer predictions are frozen**, not for fitted probabilities or numerical tuning thresholds.

The existing release-label schema includes origin time and departure season. Read and hash every relevant file after approval; recompute season from `origin_time_UTC` and verify the stored value. Require `target_epoch = origin_epoch + horizon*86400`. A mismatch stops execution. The t0 value is the predictor; target timing is only a source-consistency check.

Use UTC meteorological seasons: DJF = December/January/February, MAM = March/April/May, JJA = June/July/August, SON = September/October/November; retain stored codes 0/1/2/3. Test UTC boundaries and leap years. Year remains an audit field, not a predictor. DJF spans calendar years; a DJF season-year identifier for reporting assigns December to the following winter year. No monthly bins or cyclic splines are searched.

Separate predictor keys `(id, origin_source_obs, horizon, origin_cell, origin_time, season)` from target/qualification fields. Use the existing qualified target rather than regenerating it. Create conditional counts by `(id, h, i, s, j)`; summing out s must reproduce every annual per-ID count exactly. Source-key uniqueness and multiplicities must also reconcile.

The common qualified populations remain 303,288/268,998 times and 385/337 evaluation IDs at 7/30 days. All controls and candidates use the same fitting-B2 support mask. No local seasonal row does **not** mean an unevaluable case: use the declared annual fallback. A completely annual-unsupported origin retains the existing common unsupported-score rule and separate reporting. Never invent a self-loop or remove a case because the season is sparse.

Only existing allowlisted prepared data are needed. No canonical train/test trajectory reads, new SST/velocity extraction or input mutation are proposed for E1. Date/season missingness in this mandatory source is an integrity error, not permission to assign a convenient season.

## 3. Models and mathematical definitions

All counts below use only the current fitting IDs, separately for each horizon h. Let i be origin cell, s departure season and j destination including E. Denote raw counts `N[i,s,j]`, row total `N[i,s]`, and annual sums `N[i,j]`, `N[i]`.

Annual B2: `A_i(j) = N[i,j] / N[i]`.

Seasonal local row: `L_i,s(j) = N[i,s,j] / N[i,s]` when supported; otherwise set `L_i,s = A_i` for a supported annual origin.

Annual global B1: `G(j) = sum_i N[i,j] / sum_i N[i]`, using the same permitted R-origin pairs as the original Fixed model.

Seasonal global row: `G_s(j) = sum_i N[i,s,j] / sum_i N[i,s]`; if there are no fitting pairs at all for s/h, set `G_s = G`.

Let c be the strength of departure-season conditioning, with c=0 annual and c=1 unpooled seasonal where available:

`A_i,s(c) = (1-c) A_i + c L_i,s`  
`G_s(c) = (1-c) G + c G_s`.

The new models are:

| Model | Forecast | Role |
|---|---|---|
| SeasonalB2 | `A_i,s(c)` | Matched information test against annual B2 |
| SeasonalFixed | `(1-a) A_i,s(c) + a G_s(c)` | Primary practical candidate; matched information test against Fixed |

Retain annual B2, Fixed, global Adaptive, LocalEndpoint and LocalEndpointAdaptive with their existing definitions and grids. `SeasonalFixed(c=0,a)` must be exactly the corresponding annual Fixed forecast; `SeasonalFixed(a=0,c)` must equal SeasonalB2. At c=1 report the raw seasonal-endpoint model as a prespecified diagnostic, not a separately selected winner.

Both local and global components are conditioned so that the retained B1 component does not automatically wash out season information. One shared c per horizon applies to both. The global contribution remains visible and is tested through coverage/size as before; its seasonal version is not presumed superior. Joint a/c selection and the SeasonalB2 comparison reveal whether the global reference changes the outcome.

The seasonal support fallback is component-specific: absent local seasonal support returns the local component to annual B2, while a supported global seasonal component may still vary with s. If the entire season is absent, both components are annual. Report these cases separately. There is no neighbour-only rescue of an annually unsupported row.

Use original pair counts for distributions. Distinct fitting IDs, dominant-ID shares and year composition are diagnostics, not new training weights or estimated effective sample sizes. Avoid adding another adaptive-support formula in this first seasonal experiment; annual shrinkage and fallback address sparse rows with a finite global parameter. A support-adaptive seasonal extension would be a later reviewed proposal.

## 4. Frozen parameter budget and selection policy

- `c in {0, 0.25, 0.5, 0.75, 1}`. This is seasonal weight; the contract's annual shrinkage weight is `1-c`.
- Existing Fixed weight `a in {0, 0.05, ..., 1}`.
- SeasonalB2: 5 identities per horizon/task. SeasonalFixed: 105 identities per horizon/task. Annual Fixed is nested at c=0.
- Retained controls keep B2=1, Fixed=21, Adaptive=21, LocalEndpoint=21 and LocalEndpointAdaptive=84 identities. No new neighbour/gamma grid.
- At most 258 declared model/candidate identities per horizon/task including controls; cache exact duplicate probabilities/scores without losing identity/membership records.

Select each model by pooled inner out-of-fold primary Brier. Resolve differences within absolute 1e-12 by smaller c, then smaller a for the new models. Retain original control tie rules. c and a are shared over origins and seasons within a horizon; do not fit a separate parameter in every sparse cell-season.

This first information experiment uses **Brier-only internal selection**, followed by explicit quality acceptance. It does not repeat S3 E4's joint constrained search or automatically replace a rejected seasonal forecast with an anchor in the reported seasonal row. Report the selected candidate even if quality fails. Do not switch post hoc to another outer-scored candidate or widen the grid to force a win.

Expose two mechanism diagnostics without additional tuning: c=1 SeasonalB2, and annual Fixed at the SeasonalFixed-selected a. The latter distinguishes the direct effect of using season at a fixed a from improvement associated with changing a. These diagnostics are not new selection opportunities or additional primary claims.

## 5. Whole-ID validation and exact evaluation weights

Use the existing five outer ID groups. For outer k, pool held-out predictions across its four inner validation groups; train each inner fit on the other three groups. All local/global rows and any support diagnostics for that fit use those fitting IDs only. Refit selected settings on the four outer-training groups and evaluate outer k. Never fit or choose a seasonal rule on the outer labels.

There are 20 inner fitting roles, five outer refits and one all-development refit. After all outer results are frozen, use the five training-four/held-one base folds for all-development parameter selection, then refit on all development IDs for illustrations. All-development maps are not held-out evidence.

For horizon h, a supported evaluation case from ID d/origin i receives

`w[d,i,t] = 1 / (number_of_evaluated_origins * IDs_in_origin_i * times_for_ID_d_in_origin_i)`.

For compressed destination/season rows multiply this weight by their integer pair count. **The time denominator covers all seasons together.** Do not give an ID one new full vote in each season or weight every season equally in the primary score. Outer fold means must not be averaged equally; assemble the pooled case roster and apply the original hierarchy. Candidate scoring within an outer-training task uses that task's common held-out roster and the same hierarchy.

Metrics:

- `Brier = sum_cases w * (1 + sum_j p_j^2 - 2*p_true)` on the complete state space.
- K90: weighted mean geographic cell count in the existing nominal-0.90 region, including all cutoff ties under the existing 1e-12 rule.
- H90: weighted actual membership of the observed destination in that region. E enters probability/membership and is excluded from geographic K90.

Keep zero-probability truths and full tails. Report issued region mass, zero-probability truth rates, unsupported mass/counts and annual fallback fractions alongside the three primary metrics. Do not call Brier percentage accuracy or K90 physical area.

## 6. Seasonal evidence and interpretation

Before performance claims, report raw pair counts, distinct IDs, source-year coverage, overlapping IDs across seasons, dominant-ID contribution, destination diversity and empty seasonal rows by fitting role/horizon/origin/season. Label small-ID rows; no universal support cutoff removes them.

Describe fitted differences using matched season maps and `TV(P_s,P_r) = 0.5 * sum_j |P_s(j)-P_r(j)|`. This is a distribution-distance description, not a significance test. Report six fixed season pairs where both raw rows exist; unavailable pairs stay unavailable, and fallback-equal maps are not evidence of no seasonal effect. Do not attach naive multinomial p-values to dependent hourly counts.

Seasonal predictive information is evaluated by two matched contrasts, separately at each horizon:

1. SeasonalB2 minus B2.
2. SeasonalFixed minus Fixed.

The practical benchmark contrast is SeasonalFixed minus LocalEndpointAdaptive. All three contrasts report Brier/K90/H90. Annual LocalEndpoint and global Adaptive remain full table controls. This separates information value from whether an already strong spatial comparator is surpassed.

Use 10,000 paired whole-ID positive Exp(1) multiplier draws, PCG64 seed 20261102, with one ID multiplier shared across its cells, seasons, horizons and models. Renormalise the ID weights within each origin using the unchanged evaluation hierarchy. Fits and inner-selected parameters stay fixed. Report ordinary 95% conditional intervals and a family of **18 directional screens** (3 contrasts x 2 horizons x 3 metrics), using upper quantile `1-0.05/18` for Brier/K90 and lower quantile `0.05/18` for H90.

These are conditional development intervals; they omit refitting uncertainty, common ocean forcing, overlapping-training dependence and prior research adaptation. They do not prove a causal seasonal mechanism or independence of seasons from deployment/year composition. An interval crossing zero does not prove equivalence or non-deterioration. No extra seeds/draws or searches are added after observing a borderline outcome; label it uncertain.

## 7. Acceptance, feature gate and model retention

Use absolute 1e-12 only as a numerical equality tolerance, not an allowance for scientifically meaningful degradation.

| Conclusion | Requirement |
|---|---|
| Engineering complete | Full input/count reconciliation, no leakage, finite search, common controls/masks, independent audit, resources, outputs and fresh replay pass |
| Descriptive seasonal difference | Different supported distributions with support/composition reported; no significance claim from maps alone |
| Point seasonal predictive benefit | At least one matched seasonal-vs-annual contrast has delta Brier < -1e-12 with genuinely season-dependent held-out forecasts |
| Conditionally supported seasonal predictive information | The matched contrast also has adjusted upper delta Brier < -1e-12; disclose actual c selections, fold variation and a-retuning diagnostic |
| Quality-preserving point improvement versus a reference | Delta Brier < -1e-12, delta H90 >= -1e-12, delta K90 <= 1e-12 |
| Conditionally supported quality-preserving improvement | Point conditions plus adjusted upper Brier < -1e-12, adjusted lower H90 >= -1e-12 and adjusted upper K90 <= 1e-12 |
| Strong practical upgrade | SeasonalFixed passes the quality screen against both Fixed and LocalEndpointAdaptive; otherwise name the specific reference/trade-off and do not claim an overall replacement |
| SST priority gate | Supported seasonal predictive information at that horizon; advance only to a separately reviewed SST plan, not automatic execution |
| No supported signal / insufficient evidence | c collapses to zero, no real forecast change, intervals fail, or support is too weak; state which finding applies |

Brier-only benefit can motivate an SST proposal even if the seasonal model is not ready to replace the current forecast; these are distinct decisions. If neither horizon supplies supported seasonal information, defer SST under the user's stated priority and consider the separately reviewed initial-movement round. Do not claim SST is thereby useless.

Full-case quality remains primary. Seasonal breakdowns preserve the original case weights and normalise within the reported subset; also show their contribution to the primary aggregate. Per-season/per-cell improvements are descriptive unless a separate inference family was frozen. Do not promote an attractive season after inspecting all four.

## 8. Implementation plan and audit

After approval, implement in this order:

1. Isolated input adapter and source-keyed season/count cache. Reconcile qualification, years, boundaries and annual collapse; keep query predictors and targets separate.
2. Pure annual/seasonal count estimators, component fallbacks and finite identities. Verify probability conservation and all nesting endpoints by hand-calculated fixtures.
3. Nested runner and exact grouped scorer using existing weights/regions, then the independent audit and proposed reports. Preserve all old code and result namespaces.
4. Bounded pilot, resource review under the locked gate, complete run and one fresh replay if the gate passes.

Required semantic tests include UTC season/year boundaries; independent season decoding; no future-time predictor; source-key uniqueness; exact annual count reconstruction; one ID spanning several seasons; uneven fold sizes; c=0/c=1 and a=0/a=1; no seasonal-local/global support; annually unsupported rows; unseen outcomes and E; 90% ties; shared ID multiplier identity; fit/held-ID exclusions; deterministic ties; cache/hash corruption; immutable output boundaries and forbidden test access.

Independent audit reconstructs fitting counts and forecasts with separate Counter/set/vector arithmetic, computes weighted scores independently, and rederives selected parameters from saved inner candidate tables. It must not call the production selector to audit itself. Verify all roles; hash fitting/held-ID sets, source/config/environment and frozen outer predictions.

Reproduce annual control predictions and point metrics from S3 E2 within absolute 1e-12 after the new outer freeze, including per-ID/origin weights and selected parameters. Different uncertainty multiplicity is expected; unexplained probability/score/selection drift blocks interpretation.

## 9. Computation and finite budget proposal

Preparation is one pass over existing eligible labels. Conditional aggregation has at most four times as many rows as the corresponding annual grouped counts, and never more rows than the qualified atomic cases. Forecasts and sorted 90% regions are cached per fitting role/horizon/origin/season/candidate; score destination-count rows without recomputing a full vector for each hourly case. Do not cache fitted information across incompatible ID roles.

This avoids E5's query-by-donor geometry product. It does not promise a runtime before profiling.

Proposed limits after execution approval:

| Stage | Wall-time cap |
|---|---:|
| Full source reconciliation, support/cache preparation and one finite resource pilot | 600 s |
| Complete primary fitting/scoring/audit/report | 2,700 s |
| One fresh preparation/fitting/scoring/audit/report replay | 2,700 s |
| Cumulative real-data execution | 6,000 s (100 minutes) |

All repeated startup, interrupted work and failures count against the corresponding stage and cumulative caps. No automatic retries, grid expansion or use of a partial experiment as final evidence. These are stopping limits, not expected runtimes or a delivery-time promise.

Use one process and one numeric-library thread; combined RSS <=8 GiB and total new preparation/primary/replay artifacts <=5 GiB. No concurrent GEOS calls or external data acquisition. Existing geometry may be read for identical presentation/support strata only.

The pilot reconciles the complete case/cache inventory, then exercises both horizons, all four seasons, the full declared candidate identities and all held-out cases in the fixed first inner role (outer 0, inner 1, fitting 2/3/4). Do not choose a favourable cell or reduced donor sample. Time candidate scoring, control fitting, uncertainty, output size and report construction separately; a representative bounded uncertainty/report timing may use fixed deterministic fixtures and must be labelled timing-only.

Proceed to the primary run only if the fixed pilot passes semantic checks and its conservative full-workload projection, including 2x reserve, fits both 2,700-second complete-run caps, memory and storage. Otherwise return the bottleneck/estimate for review; do not simplify the scientific task. E1 execution approval would authorise this bounded gate, not an expensive open-ended run. E2/E3/E4 still require separate approval.

## 10. Deliverables and report structure

Proposed run prefix: `seasonal_conditioning_s4_e1_<UTC timestamp>`; the user-facing date/time uses Australia/Sydney. Store immutable results and provenance in their existing roots, and publish a new S4 E1-only deliverable alias after audit/replay. No historical alias is overwritten.

Deliver:

- Verified predictor/target key inventory, seasonal and annual per-ID count tables, fit-role support/ID/year tables and explicit source availability records.
- Complete inner candidate/selection tables, role-specific seasonal/annual matrices, frozen outer forecasts/scores and all-development illustrative matrices.
- Seven-model Brier/K90/H90 table, three predeclared paired contrasts, ordinary/adjusted uncertainty, raw-season and fixed-a mechanism diagnostics, fallback/zero-probability/issued-mass tables.
- Seasonal support heatmaps, year/ID-composition panels, per-season scores, delta/interval plots and matched four-season probability maps with common colours and 90% outlines. Reuse illustration origins 44744, 44742 and 44382 where supported; show unavailable support rather than picking nicer examples. Label all-development maps accordingly.
- English report and local HTML explaining the difference between descriptive seasonality, predictive value and quality-preserving replacement; complete provenance/audit/replay and resource receipts.

Fresh replay recomputes input features/counts and the declared model-selection sequence. Integer keys/counts/IDs must agree exactly, numeric tables within absolute 1e-12 and fixed-environment figures byte-for-byte. Inspect all plots/links. Use new output artifacts for results; update the protected research-stage ledger with approved conclusions only after user review.

**Next gate:** review the two seasonal models, five seasonal strengths, original 21 Fixed weights, matched controls, Brier-only internal selection with separate quality acceptance, UTC definition, common weighting, conditional uncertainty, SST advancement rule and 100-minute capped protocol. No development or execution has started.
