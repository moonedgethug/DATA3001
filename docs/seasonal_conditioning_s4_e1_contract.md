# S4-E1-SEA-001 — Seasonal Transition Forecast Engineering Contract

**Version:** 1.0 review draft, 2 November 2026 (Australia/Sydney).  
**Status:** `REVIEW_REQUIRED`. Contract design is authorised; implementation and execution are not yet authorised.

**Purpose:** make the first Step 4 seasonal experiment unambiguous, bounded and independently auditable. “MUST” below describes the implementation required **if this draft is approved**; it does not grant execution authority.

## C01 — Authority, lineage and change control

This contract consolidates the [S4 E1 proposal](seasonal_conditioning_s4_e1_plan.md), SHA256 `b291f93f52627d0ae33e54bbd94ad0684e99ed2d181da2ef2b91d8af088c5787`, under the [Step 4 architecture log](time_environment_s4_architecture.md). The proposal remains an unchanged planning snapshot. This contract becomes the single implementation specification after user approval; an ambiguity is not permission to choose a new scientific definition.

The Data Contract v1.0 hash remains `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`. Retain the user's later approved direct-horizon, pooled-regime and equal-ID evaluation definitions. This contract supplies the proposed seasonal predictor amendment, not a replacement dataset contract.

Clarifications added to the proposal are: explicit API/data schemas; control/candidate accounting; proof of season-induced forecast changes; common support/weight denominators; durable resource and freeze receipts; precise output and conformance requirements. No new feature, candidate grid, model family, horizon or resampling family is added.

Approval MUST be recorded separately with the user's instruction, date and this file's hash. Config/source/environment hashes are frozen before the real-data pilot. A changed scientific specification invalidates the prior approval. A changed executable source/config invalidates prior execution fingerprints and pilot receipts; it must not be relabelled as the already measured version. No approval receipt is created during contract drafting.

## C02 — Scientific task and explicit scope

**Where Things End Up:** given an object's origin cell and known departure date, estimate its stopped destination distribution after exactly 7 or 30 days. The conditional output is `P_h(j | origin_cell=i, departure_season=s)` on the frozen D cell index plus E.

E1 MUST answer separately:

1. How different are supported fitted destination distributions across seasons?
2. Does knowing departure season improve held-out Brier over matched annual models?
3. Does the improvement preserve H90 and K90 relative to retained references?

| Item | Required definition |
|---|---|
| Data | `per-drifter-cleaned-20261017-v7`; development pool only |
| Origin | Arbitrary qualified time already in an R-origin cell; not first entry |
| Spatial resolution | Frozen 1-degree cells and empirical within-cell release prior |
| Time | Exact 7/30 days; UTC departure seasons; zero matching tolerance |
| Drifter scenario | Existing pooled historical drifter-regime mixture |
| Boundary/labels | Existing stopped labels; first observed exit is absorbing E |
| Fitting | Every eligible pair retains one raw count |
| Evaluation | Equal eligible times within ID/origin, equal IDs within origin, equal origins |
| Loss/region | Standard unhalved multiclass Brier; fixed 90% region with existing ties |

Same-cell/same-season/horizon cases receive the same fitted forecast in one fitting role. Exact coordinates, departure year and day-within-season are not E1 predictors. Direct 30-day seasonal estimates include observed cross-season trajectories; they do not assume that actual weather stays fixed for 30 days. This is not short-step calendar propagation.

SST, velocity, wind/current products, monthly/cyclic time features, new drogue regimes, finer grids, E5 path transfers, MDN and latent states are out of scope. No new geometry qualification is performed. E5 remains deferred and uncompleted, not rejected on predictive performance.

## C03 — Input contract, source keys and integrity

Allowlist only the required files and their sealed receipts:

| Input | Location / rule |
|---|---|
| Annual per-ID counts | `results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet` |
| Original labels | The same run's `release_labels/`, `source_ID_summary.csv`, config and provenance |
| ID folds | `results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv` and provenance |
| Dataset/geometry identity | Current manifest/schema, English contract, frozen R/D/state index and pinned land assets |
| Control regression | Explicitly named outputs of `local_endpoint_adaptive_s3_e2_20261030T135819_234829Z`, opened only after new outer predictions freeze |

The existing `load_inputs` reconciliation MUST remain effective. The new adapter MUST verify each label checksum and its qualified subset; it cannot trust a same-named file or use an old fitted matrix as training information. No canonical trajectory or locked-test data read is permitted. Test IDs may be counted from the manifest but their trajectories/labels must remain inaccessible.

Derived tables:

| Table | Key / required fields | Invariants |
|---|---|---|
| `origin_features` | `(id:int64, origin_source_obs:int64, horizon_days:int16)`; origin cell, UTC t0, season code, outer fold | One row per qualified prediction; no destination/future path in the predictor view |
| `targets` | Same source key; destination cell, outside/E evidence and qualification lineage | Label comes from the existing stopped-target ledger; no relabelling |
| `seasonal_counts_by_id` | `(id,horizon,origin,season,destination)`; positive `pair_count:int64` | Unique keys; no zero/negative counts or extra states |
| `annual_counts_by_id` | Existing `(id,horizon,origin,destination)` | Exact integer equality to seasonal counts summed over season |
| `evaluation_denominators` | `(horizon,origin,id)`; eligible-time total; origin ID total; evaluated-origin total | Totals span all seasons and use the relevant common scoring roster |
| `support_by_role` | `(fit_role,horizon,origin,season)` | Pair count, unique ID/year counts, dominant-ID share, ID overlaps and fallback flags |

IDs/source keys MUST NOT pass through floating point or spreadsheet formatting. Do not group by endpoint before retaining the source multiplicities and original evaluation denominators.

UTC seasons MUST decode as 0=DJF (12/1/2), 1=MAM (3/4/5), 2=JJA (6/7/8), 3=SON (9/10/11). Recompute from t0 and match `departure_season`. Require timezone-valid UTC, valid horizon and `target_epoch = t0_epoch + 86400*h`. Future timing is a reconciliation check, never a feature. DJF reporting assigns December to the following season-year; that identifier is audit-only.

Reconcile the 3,224-ID fold map and the qualified 7/30-day populations: 303,288/268,998 pairs, 385/337 evaluation IDs, 4,451/3,974 ID-origin units and 37 observed origins. Seventeen additional indexed origins are unevaluated. Unexpected differences MUST stop execution for investigation; never trim or add records to make totals match. Report seasonal support as a new result after approval, not as presumed adequate support.

## C04 — Probability estimators, normalisation and fallbacks

All following quantities are fitted separately by horizon using **only current fitting IDs**. Let `N[i,s,j]` count eligible pairs and `N[i,s]` be its row sum. Annual counts sum over s. All vectors use the identical destination order, including E=-2.

`A_i(j) = N[i,j] / N[i]` — annual B2.  
`L_i,s(j) = N[i,s,j] / N[i,s]` — seasonal local row when available.  
`G(j) = sum_i N[i,j] / sum_i N[i]` — annual B1 over qualified R-origin pairs.  
`G_s(j) = sum_i N[i,s,j] / sum_i N[i,s]` — seasonal B1 when available.

Use unambiguous names for the shrunken components:

`A_tilde[i,s;c] = (1-c)*A_i + c*L_i,s`  
`G_tilde[s;c] = (1-c)*G + c*G_s`.

| New model | Required probability vector |
|---|---|
| SeasonalB2 | `A_tilde[i,s;c]` |
| SeasonalFixed | `(1-a)*A_tilde[i,s;c] + a*G_tilde[s;c]` |

The same c applies to local/global components and all cells/seasons for one horizon. It is a validation-selected **global seasonal weight**, not an adaptive function of local sample size. Distinct-ID counts are support diagnostics, not training reweights or a new effective-sample-size formula.

| Condition | Required action |
|---|---|
| Annual local row absent | All models use the existing common unsupported-row status; no standard score, no neighbour/global rescue; report counts and primary-weight coverage |
| Annual row supported, local seasonal row absent | Set `L_i,s=A_i`; retain the case |
| Global seasonal row absent | Set `G_s=G`; retain the case |
| Local seasonal row absent but global seasonal row present | Only the local component falls back; SeasonalFixed can still vary with season through `G_s` |
| Positive but small seasonal support | Use its raw row and the declared c; flag support without inventing a minimum-count cutoff |
| Zero-probability observed truth | Keep and score normally; no probability floor or renormalisation |

Every issued vector MUST be finite, nonnegative, no entry above one, and sum to one within absolute 1e-12. Unsupported bookkeeping U is not appended as an extra outcome to otherwise supported E1 vectors. Missing rows are not turned into observed exits or self-loops.

Required identities: `SeasonalB2(c=0)=B2`; `SeasonalFixed(c=0,a)=Fixed(a)`; `SeasonalFixed(a=0,c)=SeasonalB2(c)`; absent entire-season support gives the corresponding annual forecast. Exact keys/counts must match; vector arithmetic uses the established numeric tolerance and region membership must remain unchanged for nested controls.

## C05 — Comparators, search budget and tie rules

Retain the five annual controls: B2, Fixed, Adaptive, LocalEndpoint and LocalEndpointAdaptive. Their mathematics, training support, grids, tie rules and no-neighbour behaviour are unchanged; no seasonal filtering enters their fits.

| Family | Grid | Identities per horizon/validation role |
|---|---|---:|
| B2 | None | 1 |
| Fixed / Adaptive / LocalEndpoint | Their original `a=k/20`, k=0,...,20 | 21 each |
| LocalEndpointAdaptive | Original a grid x gamma `{0,0.5,1,2}` | 84 |
| SeasonalB2 | c `{0,0.25,0.5,0.75,1}` | 5 |
| SeasonalFixed | Original a grid x c grid | 105 |
| Total | Seven model families | 258 |

Select each new model by pooled inner OOF primary Brier. Find the minimum; among candidates within absolute 1e-12, prefer smaller c, then smaller a. Annual controls retain their existing tie rules. No different a/c per cell or season and no continuous optimisation, extra grid, repeated random search or feature selection after outer inspection.

Selection is Brier-only. H90/K90 determine the separate acceptance decision; a failed quality screen does not replace the displayed seasonal candidate with a reference. No post-hoc outer winner is substituted. This preserves the first-round information question instead of hiding a negative result behind a selection fallback.

Include two untuned mechanism diagnostics: SeasonalB2 at c=1, and Fixed at each SeasonalFixed-selected a with c=0. Their results are not new selection opportunities. Record `season_induced_change_weight`: the primary weight of cases whose selected vector differs by more than 1e-12 in any coordinate from its same-parameter c=0 counterpart. This distinguishes an active seasonal contribution from c>0 with numerically identical forecasts. It does not itself prove a physical seasonal cause.

## C06 — Whole-ID roles and evaluation contract

Use existing outer groups 0,...,4. For outer k and inner validation v!=k, fit on the remaining three groups. Pool the four inner validation rosters for each model/horizon before choosing its parameters. Refit on four outer-training groups, then score outer k once. The complete query ID is absent from every fitting count, including all its other visits and seasons.

There are 20 inner fits, five outer fits and one all-development refit. The six selection tasks per horizon (five outer-training tasks plus one all-development task) give 12 tasks. Up to 25 validation roles x 2 horizons x 258 identities = **12,900 candidate/role/horizon score identities**; equivalent vectors can share calculations but must retain their membership records. Up to 12 x 258 = **3,096 task-level aggregated candidate identities** are available for selection. These counts are not observation counts or runtime forecasts.

Freeze selected outer forecasts, parameters, masks, weights and point scores before evaluating the full candidate grids on the five training-four/held-one base fits for all-development selection. The latter uses all development labels for choosing illustrative parameters and cannot retroactively change the frozen outer comparison. Refit illustrations on all development IDs afterward.

For each horizon/common scoring roster, let C be its evaluated origin set, `D_i` its eligible IDs in origin i, and `n_di` the eligible times for ID d in i **across all seasons**:

`w[d,i,t] = 1 / (|C| * |D_i| * n_di)`.

A compressed row with m identical feature/outcome cases has weight `m*w[d,i,t]`. One ID visiting four seasons does not receive four full votes. Primary scores are not averages of equally weighted season or fold means. Apply the same hierarchy to the pooled inner validation roster for each selection task. All seven models share masks and weights.

Per-case Brier MUST be `1 + sum_j p_j^2 - 2*p_truth`. H90 is membership of truth in the nominal-90% set; K90 counts its geographic cells. Use the existing `probability_region` implementation: positive probabilities sorted descending, first cumulative mass reaching `0.90-1e-12`, include all positive entries at least `cutoff-1e-12`. E contributes probability and membership but not K90. Do not use the optional fixed-cell-budget region helper.

Report issued region mass, E probability, true-outcome zeros, empty seasonal rows, component fallback fractions and common unsupported counts/weights. Per-season breakdowns condition the original weights on that subset and display subset weight. They do not redefine the aggregate estimand.

## C07 — Seasonal evidence, uncertainty and decision rules

Support tables MUST include fitting pairs, unique IDs/years, dominant-ID shares, destination diversity and cross-season ID overlap. Descriptive maps and six pairwise seasonal total-variation distances `0.5*sum_j|P_s-P_r|` require supported raw rows; absent comparisons are NA, not zero. Do not treat all hourly pairs as independent replicates in a significance test.

Freeze three contrasts per horizon:

1. SeasonalB2 minus B2 — matched local information test.
2. SeasonalFixed minus Fixed — primary practical information test.
3. SeasonalFixed minus LocalEndpointAdaptive — retained spatial benchmark.

Report Brier, H90 and K90 for each: 18 directional screens in total. Use 10,000 paired Exp(1) whole-ID multiplier replicates, NumPy PCG64 seed 20261102, in sorted development-ID order; share each ID multiplier across its seasons, origins, models and horizons. First average original eligible times within ID/origin; within an origin normalise ID multipliers to sum one; then average origins equally. Record the float64 multiplier digest and linear quantile method.

Fits/selected parameters remain fixed. Report ordinary 95% intervals and adjusted upper bounds at `1-0.05/18` for Brier/K90, adjusted lower bounds at `0.05/18` for H90. These are conditional development comparisons, not full refitting uncertainty, causal seasonal tests or final-test evidence. Prior research adaptation and shared ocean conditions remain limitations. A zero-crossing interval does not establish non-deterioration. Do not add replications/seeds after a borderline result.

| Decision flag | Required evidence |
|---|---|
| `ENGINEERING_COMPLETE` | All conformance, resource, audit, freeze and fresh-replay checks pass; favourable prediction is not required |
| `SEASONAL_POINT_GAIN` | A matched contrast has delta Brier < -1e-12 and positive season-induced-change weight |
| `SEASONAL_SIGNAL_SUPPORTED_CONDITIONALLY` | Matched point gain plus adjusted upper delta Brier < -1e-12; report selected c/fold stability and Fixed-at-same-a diagnostic |
| `QUALITY_POINT_GAIN_VS_REFERENCE` | Delta Brier < -1e-12, delta H90 >= -1e-12 and delta K90 <= 1e-12 |
| `QUALITY_SUPPORTED_CONDITIONALLY_VS_REFERENCE` | Point conditions plus adjusted upper Brier < -1e-12, lower H90 >= -1e-12, upper K90 <= 1e-12 |
| `STRONG_UPGRADE_CANDIDATE` | SeasonalFixed passes the supported quality screen against both Fixed and LocalEndpointAdaptive at that horizon |
| `SST_PLAN_ELIGIBLE` | A matched seasonal signal is conditionally supported; user review may then prioritise a separate SST proposal for that horizon |
| `NO_SUPPORTED_GAIN` / `INSUFFICIENT_EVIDENCE` | Report the actual reason: annual collapse, no forecast change, failed uncertainty/quality screen, sparse support or unstable results |

Numerical tolerance is not a practical benefit threshold. Always report absolute/relative Brier change, H90 percentage points, K90 cells/percentage and added compute/input burden; do not promote a negligible gain solely because it passes a numeric screen. Retention is a user decision. Seasonal support does not prove SST causes the difference; E2 is not automatically executed.

## C08 — Interfaces and source ownership

New code belongs under `src/data3001/modelling/baselines/` with the `seasonal_conditioning_s4_e1` prefix. Reuse `common/runtime.py`, `common/qualified_count_inputs.py`, `common/prediction_regions.py`, existing whole-ID manifests and verified annual-model/scoring primitives. Do not invoke old runners or alter historical hashed modules to make this experiment work.

| Boundary | Contract |
|---|---|
| `prepare_inputs` | Verified allowlist -> separate predictors/targets, conditional counts, denominators and inventory; no fitting or season-support filtering |
| `fit` | Conditional counts + explicit fitting IDs + frozen states -> annual/seasonal distributions and support; assert no query/held-ID access |
| `predict` | Fitted role + `(origin,horizon,season)` + model/parameters -> complete vector or common unsupported status; no truth or future path arguments |
| `score` | Predictions + held targets + explicit common weights -> per-ID/origin and aggregate metrics; no refitting |
| `select` | Saved pooled inner metrics + frozen candidate/tie rules -> parameter/status; no outer scores |
| `audit` | Saved sources/counts/roles/forecasts/candidates -> independent reconstruction; do not reuse the selector as its own oracle |

Cache identity MUST cover input hashes, fitting-ID hash, horizon, origin/season, state order, model/parameters, definition/version and source fingerprint. Never share fitted rows between incompatible roles. Derive c/a identities from grid indices, not approximate rounded float cache keys. Source files are split into inputs, estimator/selection, runner, audit and report as specified in the architecture; avoid an unrelated framework refactor.

## C09 — Execution gates and resource contract

Future approved lifecycle:

`APPROVED -> SYNTHETIC_CHECKS -> PILOT -> PRIMARY -> OUTER_FROZEN -> ALL_DEV_AND_AUDIT -> FRESH_REPLAY -> REVIEW_SUBMITTED`.

Current state remains `REVIEW_REQUIRED`. The pilot may begin only after implementation passes meaningful synthetic checks and the approval/config/source fingerprints are sealed. Production primary/replay may proceed within a later execution approval only if the pilot passes the following finite gate; they never trigger E2/E3/E4.

| Resource | Limit |
|---|---:|
| Reconciliation, input cache and one resource pilot | 600 s |
| Complete primary, including startup/scoring/audit/report | 2,700 s |
| Fresh preparation, fitting, scoring, audit/report replay | 2,700 s |
| Cumulative real-data execution | 6,000 s (100 minutes) |
| Processes / numeric-library threads | 1 / 1 |
| Combined RSS / all new artifacts | 8 GiB / 5 GiB |

These are caps, not runtime promises. Code preparation/small synthetic fixtures are outside the real-data clock; all real-data startup, interrupted/failed work, verification and repeated work are inside it. Unused time in one stage does not silently extend another. No automatic retries, new variant or budget expansion follows a failure.

The pilot MUST reconcile the complete qualified inventory/cache, then exercise both horizons and all declared candidates on **all** held-out cases in the fixed role: excluded outer group 0, validation group 1, fitting groups 2/3/4. Enumerate all four season labels; report empty strata rather than substituting other records. No favourable-cell pilot or new scientific subsampling is allowed.

Before timing, enumerate full metadata workloads for 26 fits, 25 validation roles, 12 selection tasks, selected/diagnostic scores, 10,000 multipliers, independent audits, all outputs and replay. Save, per stage: timed units, exclusive seconds, full workload, scaling rule, setup cost, uncertainty and measured or unmeasured status. Time source verification, conditional/annual fitting, vector/region work and grouped scoring separately. Output and uncertainty fixtures may be used for capacity only, with their sizes and timing-only status explicit.

Project each complete run from measured component rates and the full enumerated workload, including fitting/control/audit/output overhead, with a 2x reserve. No missing cost is assigned zero. If a material component cannot be timed or bounded within the pilot, set `CAPACITY_NOT_ESTABLISHED`. Primary and replay must each fit their own cap and combined memory/storage cap. The reserve is a planning allowance, not a confidence interval; the hard runtime limits still apply.

Keep source-key/count caches immutable and stream bounded outputs. Write data atomically, then its committed receipt. Persist budget/resource/access progress before normal exit, and use a watchdog for deadlines. No worker shares native prepared geometry because there is no parallel geometry work. An integrity/leakage/semantic failure stops immediately; a timeout preserves partial evidence without claiming a completed experiment or dropping an unfinished fold. Continue only offline closure/reporting of existing evidence after such a stop.

## C10 — Mandatory conformance and independent verification

| Test ID | Required evidence | Failure action |
|---|---|---|
| SEA-01 | Independent UTC season decoding at every boundary, Dec/Jan, leap day and exact target duration | Stop |
| SEA-02 | Source keys, qualified masks, populations and every annual count exactly reconstructed | Stop |
| SEA-03 | c/a endpoint identities, component-specific empty-season fallback, complete probability mass and no invented exit/self-loop | Stop |
| SEA-04 | Entire query ID/fold absent from fit counts; forbidden-read and stale-cache tests fail closed | Stop |
| SEA-05 | One ID across four seasons keeps its original total influence; uneven fold/season populations reproduce direct weighted arithmetic | Stop |
| SEA-06 | Full Brier including zero truth, exact 90% cutoff ties and E handling match independent examples and shared helper | Stop |
| SEA-07 | 258-identity registry, 105/5 new grids, pooled-inner/tie decisions and all-development-after-freeze order reconcile | Stop |
| SEA-08 | Independent Counter/set counts and probability/score reconstruction for every fitting/validation role; no selector self-audit | Stop |
| SEA-09 | Annual controls reproduce sealed S3 E2 parameters, predictions, masks and point metrics within absolute 1e-12 | Stop interpretation and investigate; do not force historical values |
| SEA-10 | Paired ID multipliers, 18-screen accounting, conditional interval and decision flags independently reproduce | Stop |
| SEA-11 | Atomic/incomplete/stale checkpoint rejection, access/resource logs, fixed output inventory and source preservation pass | Stop |
| SEA-12 | Fresh replay: exact scientific integer/ID equality, scientific numeric tables within 1e-12, fixed-environment figure bytes identical | Stop; do not publish successful deliverable alias |

All exact schema/key/ID/count checks require exact equality. Nonfinite numeric scores or incomplete case/role output are failures. Changed uncertainty bounds versus old rounds are expected because the comparison family differs; unexplained old-control point forecast changes are not.

Freeze the replay comparison inventory before execution. Scientific forecasts, counts, parameters, masks, scores and uncertainty belong in the equality inventory. Operational timestamps, run IDs, elapsed times and resource measurements are audited for valid lineage/schema/budgets and are expected to differ; they are not scientific-equality failures. Deterministic PNGs must not embed changing run IDs, timestamps or runtime annotations. Preserve such operational information in report/provenance text instead.

Independent auditing MUST reconstruct the estimators, standard Brier, evaluation hierarchy, region membership, parameter selection and acceptance flags from saved evidence. Source/semantics tests do not establish predictive superiority; predictive claims require the full frozen outer results.

## C11 — Required artifacts and visual review

Create a new `seasonal_conditioning_s4_e1_<UTC timestamp>` namespace under `results/runs/` and `provenance/runs/`; never edit earlier results. User-facing dates use Australia/Sydney. Proposed config/entrypoint names follow the existing E1 architecture and are created only after approval.

Required deliverables:

1. Contract/config/approval/source/environment/input fingerprints; guarded-access and cumulative resource receipts; stage/failure status.
2. Source-keyed predictors and targets, conditional and annual counts, common denominators, support and source-year/ID composition, explicit annual fallback evidence.
3. Complete role/candidate membership and inner scores/selections, selected outer forecasts with original weights, `outer_freeze.json`, then all-development selections/matrices.
4. Seven-model Brier/H90/K90 table; three declared contrasts at both horizons, ordinary/adjusted intervals and flags; raw-season/fixed-a diagnostics; zeros, E, issued mass and seasonal-change/fallback weights.
5. English `REPORT.md`, local `review.html`, numeric chart data and twelve fixed PNG figures: six summary figures (metrics; paired differences; seasonal support; year/ID composition; seasonal scores; selected weights/fallbacks), plus six map figures (origins 44744/44742/44382 x 7/30 days). Each map compares annual Fixed, the four SeasonalFixed seasons and annual LocalEndpointAdaptive using matched scales/90% outlines. Show missing support or annual fallback explicitly; do not choose a replacement cell for a better-looking result. Seasonal TV values are provided as a table.
6. Independent conformance/audit report, primary/replay comparison and hashes; all figure/report links visually checked.

Maps use all-development fits and must be labelled illustrative. Scores use frozen outer-held-ID forecasts. Report separately: engineering completion, descriptive seasonal variation, conditional predictive evidence, quality trade-offs and unknowns. No claim of 90% actual coverage merely because a region contains 90% fitted mass.

Only after all required audits/replay pass may a new `results/deliverables/seasonal_conditioning_s4_e1` alias be created. Model replacement, Step 4 closure, SST execution and Git publication remain later user decisions.

## C12 — Review checkpoint

The implementation review must confirm: UTC four-season conditioning; raw-pair training/common drifter-balanced evaluation; two seasonal models and annual fallbacks; five c values and 21 a values; the five retained controls; nested whole-ID selection; Brier-only internal selection with separate quality acceptance; 18 conditional screens; unchanged complete cases and fixed 90% regions; 10+45+45-minute caps and fresh replay.

**Current outcome:** engineering contract drafted for review. No config/approval receipt, model implementation, data extraction, training, pilot or replay has been created or executed as part of this contract-design task.
