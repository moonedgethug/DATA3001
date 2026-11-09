# S4-E1-SEA-001 — Seasonal Transition Forecast Engineering Contract

**Version:** 2.0 review draft, 2 November 2026 (Australia/Sydney).

**Status:** `REVIEW_REQUIRED`. The user confirmed the simplified scientific direction and requested this revision. Review of this document must precede implementation or execution; this request is not execution approval.

**Purpose:** compare annual B2 with departure-season B2 on later, disjoint drifters, using the same training window and validation cases. “MUST” describes implementation required **after approval**.

## C01 — Authority, changes and precedence

The user confirmed: 2012–2019 training; 2020–2022 validation; exclude training labels requiring observations across the cutoff; disjoint drifter IDs; annual B2 versus seasonal B2 with fixed `c=1`; annual fallback for missing seasonal support; unchanged drifter-balanced evaluation, standard Brier and fixed 90% regions.

This v2 draft replaces the active design in the [v1 contract snapshot](seasonal_conditioning_s4_e1_contract_v1.md), SHA256 `2cbff4361e95e4320c67c4a63a957078285b5aefa1c8ae26526771f12a714a77`. The [original E1 proposal](seasonal_conditioning_s4_e1_plan.md), SHA256 `b291f93f52627d0ae33e54bbd94ad0684e99ed2d181da2ef2b91d8af088c5787`, remains an unchanged historical planning snapshot. Its grids, nested CV, extra models, all-development refits and older budgets do not govern v2. The [architecture log](time_environment_s4_architecture.md) records the amendment.

The Data Contract v1.0 hash remains `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`; retain later approved direct-horizon, pooled-regime and equal-ID evaluation definitions. The new temporal cohort is explicit, not a change to the cleaned release or historical experiment results.

After approval, record the user's execution instruction, date and this file's hash in a separate receipt. Freeze config/source/environment hashes before real-data execution. Changed scientific terms require renewed review; changed source/config invalidates earlier execution fingerprints. No execution-approval receipt is created during this revision.

## C02 — Question and fixed scope

**Where Things End Up:** given an object already in origin cell i at known departure time t0, predict its stopped destination after exactly 7 or 30 days. Ask whether departure season improves later-period Brier while preserving actual hits and geographic region size.

| Item | Locked design for review |
|---|---|
| Dataset | `per-drifter-cleaned-20261017-v7`; development pool only |
| Origin / states | Arbitrary qualified time in frozen R; 1-degree cells; frozen D plus absorbing E=-2 |
| Targets | Existing stopped labels; first observed exit is absorbing; exact 7/30 days, zero matching tolerance |
| Training | Qualified departures in `[2012-01-01,2020-01-01)` UTC, with C04 exclusions |
| Validation | Qualified departures in `[2020-01-01,2023-01-01)` UTC, limited to sealed available data |
| Models | `B2Annual` and `B2SeasonalC1` only |
| Training weights | One raw count per eligible pair; no EqualID or partial-ID training reweighting |
| Evaluation weights | Equal times within ID/origin, equal IDs within origin, equal origins |
| Metrics | Standard unhalved multiclass Brier; H90 actual hit rate; K90 geographic cell count |

Season codes are 0=DJF (December/January/February), 1=MAM (March/April/May), 2=JJA (June/July/August), 3=SON (September/October/November), from **UTC departure time**. December belongs to the next DJF season-year for reporting only. A 30-day trajectory may cross a season boundary; its start season conditions the direct endpoint distribution, not constant weather along the path.

Both models use the same recent training records. “Annual” pools seasons within 2012–2019, not all historical years. The pooled drifter-regime scenario stays unchanged. Year determines roles and diagnostics, not a learned predictor. Exact coordinates do not condition this cell-level model.

No seasonal-weight search, B1/Fixed/Adaptive/neighbour comparison, nested CV, rolling-cutoff selection, all-development refit, new geometry, SST, velocity, wind/current, recursive propagation or new loss is included. Historical models remain research records, not fitted controls in this round. Historical scores are not directly comparable to this new validation cohort.

## C03 — Inputs, provenance and reproducible support

Allowlist the prepared development labels/count inventory under `results/runs/markov_input_20261025T095949_830292Z/`, its sealed provenance receipt, `source_ID_summary.csv`, current dataset manifest/schema/English contract and frozen state/R/D/pinned map assets. No canonical trajectory or final-test trajectory/label reads are permitted. The 517 locked test IDs remain excluded.

Verify hashes, development membership, source metadata and qualified masks: `reason_code=0`, `target=stopped`, `scenario=pooled`, `tolerance_hours=0`, h in {7,30}. Source key `(id,origin_source_obs,horizon_days)` must be unique and integral. Check UTC season decoding and `target_epoch=t0_epoch+86400*h`. Verify absorbing-exit evidence and required-interval semantics against the sealed labels; do not relabel.

Reconstruct all-development annual per-ID counts from original labels and compare exactly with the sealed count table **for integrity only**. Expected full populations at 7 / 30 days: 303,288 / 268,998 pairs, 385 / 337 IDs, 4,451 / 3,974 ID-origin units and 37 observed origins. This reconstruction is not a fitted full-history prior. Historical fold maps and historical fitted predictions are unnecessary and not execution inputs.

The [planning support audit](../provenance/reviews/seasonal_temporal_support_20261102/README.md) supplies expectations; its [audit JSON](../provenance/reviews/seasonal_temporal_support_20261102/audit.json) has SHA256 `66bb108eb05f87f98d77207bafdffa761b2464e65d41b568d18ef14c9939fbb1`. Verify its artifact manifest. Recompute roles from original keys, not from aggregated audit numbers.

| Expected roster / sequential exclusion | 7 days | 30 days |
|---|---:|---:|
| Training pairs excluded by required-label cutoff | 630 | 1,921 |
| Additional training pairs excluded by validation-ID union | 2,947 | 1,656 |
| Final training pairs / IDs / origins | 130,731 / 159 / 37 | 113,708 / 138 / 37 |
| Final training ID-origin units | 1,853 | 1,624 |
| Validation pairs / IDs / origins | 33,971 / 45 / 36 | 30,128 / 42 / 35 |
| Validation ID-origin units | 435 | 409 |
| Annual-unsupported validation cases | 0 | 0 |
| Seasonal-fallback validation cases / primary weight | 41 / 1/36 | 0 / 0 |

The union of validation IDs across both horizons contains 45 IDs. Last available qualified departures are 2022-10-24 00:00 UTC (7 days) and 2022-10-01 00:00 UTC (30 days); 2022 is incomplete. An unexpected count, key, date or fallback discrepancy stops execution for investigation. Never filter records to force expected totals.

## C04 — Chronological roles and leakage boundaries

Let `T=2020-01-01T00:00:00Z` and Q be the verified qualified development cases. Apply these rules in order:

1. Define `V_h={q in Q: horizon=h, T<=t0<2023-01-01 UTC}` using all available qualified cases in that window. Define `D_V=union_h IDs(V_h)` **before checking training support**.
2. Define training candidates `T0_h={q in Q: horizon=h, 2012-01-01 UTC<=t0<T}`.
3. Retain a training candidate only if `required_interval_end_epoch<T`. This is the end of the observation interval needed to establish the sealed label, normally t0+h; a sealed absorbing exit can establish its outcome earlier. Equality with T is excluded. A pre-2020 origin alone is insufficient. Do not shift the validation clock or t0 to rescue a pair.
4. Exclude every remaining training case whose ID belongs to `D_V`, at **both horizons**. Earlier records of validation drifters cannot fit either model. Do not remove those drifters from validation to regain training samples.
5. Fit both models from exactly these final training records. Support tables, probabilities and prediction caches derive from this training set alone. Pre-2012 data stay preserved and excluded from fits.

Label exclusion precedes ID exclusion so the reported sequential counts are disjoint. Also retain independent boolean reason flags; one record may trigger both original predicates. Validation eligibility is unchanged by seasonal support, endpoint surprise, a poor score or missing training destinations.

Save source-keyed roles/exclusion reasons, the validation-ID-union hash, per-horizon training-ID hashes and cutoff. Assert `IDs(training_7 union training_30) intersect D_V = empty` and the required-label-time bound. Cross-horizon exclusion applies even when an ID has valid validation cases at only one horizon.

Keep predictors (key, t0, origin, season, horizon) separate from targets/qualification. Preparation/audit may inspect targets to verify the sealed inventory and existing eligibility, but fit accepts training keys only; predict accepts no validation outcome or future path. Freeze all validation forecasts, masks, regions and original weights before scoring performance. No date/weight/fallback changes follow score inspection.

This is a **chronological development backtest**. Prior use of development data is not erased by a new split. It is neither untouched final-test evidence nor proof of performance after 2022. Time-aware and group-wise validation address different dependencies; see the [validation guidance](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-of-time-series-data).

## C05 — Two estimators and support rules

For each h, count final training pairs as `N_h(i,s,j)`, where j includes all frozen D destinations and E. Let `N_h(i,s)=sum_j N_h(i,s,j)`, `N_h(i,j)=sum_s N_h(i,s,j)`, and `N_h(i)=sum_j N_h(i,j)`.

`B2Annual_h(j|i) = N_h(i,j)/N_h(i)` when `N_h(i)>0`.

`B2SeasonalC1_h(j|i,s) = N_h(i,s,j)/N_h(i,s)` when `N_h(i,s)>0`; otherwise it equals `B2Annual_h(j|i)` if the annual row exists.

This is fixed `c=1` on supported rows. Missing-season fallback is an availability rule, not a fitted weight. A single supported pair still uses its raw seasonal row; report low support without a new minimum-ID cutoff, smoothing, probability floor or adaptive weight. Both models retain every permitted training pair and its multiplicity.

| Condition | Required action |
|---|---|
| Seasonal row exists | Full seasonal empirical distribution |
| Seasonal row absent, annual row exists | Identical annual vector; `annual_fallback=true`; retain case in primary evaluation |
| Annual row absent | Common unsupported status, no standard score; report counts/pre-mask weight. Expected zero here; unexpected cases trigger C03 investigation |
| Observed validation truth has zero probability | Keep and score the zero normally |

Issued vectors must be finite, nonnegative, bounded by one and sum to one within absolute 1e-12 on the same ordered D-plus-E states. Do not invent self-loops, exits or a U outcome, or truncate small probabilities. Seasonal counts summed over s must reproduce annual counts of the **final training set** exactly.

Fallback forecasts, Brier, H90 and K90 must equal annual B2 case by case. Report fallback case/ID/origin counts, raw-pair fraction and primary-weight fraction: 41/33,971 is about 0.121% of 7-day pairs but 2.778% of primary weight. Label fallback plots “annual fallback”; they are not estimated seasonal rows.

Two model families x two horizons give **four primary model/horizon results**, one chronological split and zero tuning candidates. Construct one annual and four season-indexed matrix views per horizon, allowing unsupported rows. No inner selection or post-validation refit is needed.

## C06 — Common evaluation and the 90% region

For each horizon, form the common validation roster using only the shared annual-support mask. Let C be its origins, `D_i` its validation IDs in origin i, and `n_di` the eligible validation times for d/i **across all validation seasons and years**:

`w[d,i,t] = 1 / (|C| * |D_i| * n_di)`.

Weights sum to one and are identical for both models. A compressed season/destination row with m cases has weight `m*w[d,i,t]`. A drifter gets one total vote **within each origin/horizon**, not one per season. Origins are equal; an ID visiting several origins appears in each origin-conditional task. This is not global one-ID-one-vote weighting. Training stays raw-pair counting.

`BS_case = sum_j (p_j - 1[j=y])^2 = 1 + sum_j p_j^2 - 2*p_y`.

`Brier = sum w*BS_case`; lower is better, not percentage accuracy. Score the full distribution, including zero-probability truths and E, without spatial distance or a combined loss.

Use unchanged `common/prediction_regions.py::probability_region`: sort positive probabilities descending, find the first cumulative sum reaching `0.90-1e-12`, include all positive entries at least `cutoff-1e-12`. Retain cutoff ties even if mass exceeds 0.90.

`H90=sum w*1[y in region90]`; `K90=sum w*(number of geographic D cells in region90)`. E contributes mass/hit membership but not geographic count. K90 is not physical area. Nominal 90% probability does not guarantee 90% actual hits; use the same nominal level for both models.

Report issued mass, predicted/observed E, zero-truth rate, unsupported/fallback counts and weights. For season/year/support/fallback slices and the optional common season-supported subset, condition the **original primary weights** on that subset; do not rebalance cells, IDs or seasons. Show original subset weight and ID count. Descriptive slices cannot replace the full-case decision.

## C07 — Uncertainty and acceptance

Freeze one contrast per horizon: `delta = SeasonalC1 minus Annual`. Desirable directions: Brier<0, H90>=0, K90<=0. Report absolute/relative Brier change, H90 percentage points and K90 cells/percent. Relative changes with zero reference denominator are NA.

Use 10,000 paired positive Exp(1) whole-ID multiplier replicates, NumPy PCG64 seed 20261102. Generate a float64 array in replicate-major order over the sorted **45-ID validation union**. Share each ID multiplier across its origins, seasons, models and both horizons. Save ID order, array hash and quantile method (`linear`). Do not resample hourly pairs as independent observations.

First average eligible times within each ID/origin. In each replicate, weight those means by ID multipliers normalised within the origin, then average origins equally. Apply identical multipliers to both models and compute paired differences. Fits remain fixed: intervals describe validation-ID uncertainty conditional on fitted models, not training/refitting uncertainty, shared ocean dependence or prior project adaptation.

Report ordinary central 95% intervals and six directional screens (one contrast x two horizons x three metrics). Conditional-evidence bounds use upper quantile `1-0.05/6` for Brier/K90 and lower quantile `0.05/6` for H90. This Bonferroni-adjusted resampling screen is approximate, not an exact finite-sample significance guarantee. Season/year/cell slices have no confirmatory tests. Do not add seeds, replicates or cutoffs after a borderline result.

Evaluate the following **separately for 7 and 30 days**, with `eps=1e-12` only for numerical equality. No practical degradation margin is introduced. An interval crossing zero does not establish non-deterioration or absence of seasonality.

| Status / conclusion | Required evidence |
|---|---|
| `ENGINEERING_COMPLETE` | Exact source/role/count reconciliation; leakage, probability, weight and region checks; complete outputs/visuals; independent audit, resources and fresh replay pass. Positive skill is not required |
| `BRIER_POINT_GAIN` | Delta Brier < -eps and positive primary weight of forecasts differing from annual by >eps in at least one state |
| `QUALITY_POINT_GAIN` | Brier point gain, delta H90 >= -eps and delta K90 <= eps on the full common validation roster |
| `BRIER_GAIN_SUPPORTED_CONDITIONALLY` | Brier point gain plus adjusted upper delta Brier < -eps |
| `QUALITY_GAIN_SUPPORTED_CONDITIONALLY` | Quality point gain plus adjusted upper Brier < -eps, lower H90 >= -eps and upper K90 <= eps |
| `BRIER_GAIN_WITH_QUALITY_TRADEOFF` | Brier point gain but an H90/K90 point condition fails; state the exact cost |
| `NO_BRIER_POINT_GAIN` | Brier point condition fails; show actual differences and intervals |
| `QUALITY_NOT_ESTABLISHED` | Quality point conditions pass but conditional evidence does not; no claim of demonstrated non-deterioration |

The primary model-improvement target is `QUALITY_POINT_GAIN`; only the supported flag warrants the stronger conditional claim. Tiny changes must be reported as tiny: eps is not a meaningful-effect threshold. There is no averaged 7/30-day pass; both must pass to claim improvement at both horizons.

Supported Brier benefit may motivate discussion of a separate SST proposal even if quality costs prevent replacement. It neither proves a physical seasonal mechanism nor attributes benefit to SST. Failure of raw c=1 does not prove seasons uninformative: sparse rows may be noisy. Retention, new smoothing/features, stage closure and final-test access require user review.

## C08 — Interfaces, isolation and implementation order

After approval, new code stays under `src/data3001/modelling/baselines/` with prefix `seasonal_conditioning_s4_e1`. Reuse hash/read guards, label verification, states and region/scoring primitives. Adapt verification to chronological roles; do not call old runners or inherit their folds. Preserve historical hashed code and runs.

| Proposed owner | Contract |
|---|---|
| `seasonal_conditioning_s4_e1_inputs.py` | Sources/seasons, roles/exclusions, separate predictors/targets, final training counts and validation denominators |
| `seasonal_conditioning_s4_e1.py` | Pure annual/seasonal estimators, prediction/fallback, grouped scoring and paired uncertainty; no selector |
| `run_seasonal_conditioning_s4_e1.py` | Approval/config/source freeze, guarded access, budgets, forecast freeze, audit and replay |
| `seasonal_conditioning_s4_e1_audit.py` | Independent source/role/count and probability/weight/metric/decision reconstruction |
| `seasonal_conditioning_s4_e1_report.py` | English report, HTML and predeclared figures from frozen evidence |
| Config / tests | `configs/seasonal_conditioning_s4_e1.json`, `tests/test_modelling_seasonal_conditioning_s4_e1.py`, only after approval |

Required tables: `origin_features`, `targets`, `role_membership` with exclusion flags, `training_counts_by_id_season`, `training_counts_by_id_annual`, `validation_denominators`, `training_support`, `predictions`, `regions`, `scores_by_id_origin`, `contrasts`, `uncertainty`, `acceptance_flags`. Compression must preserve exact integer keys and multiplicities.

Fit accepts final training keys/counts only; predict accepts a fitted model and origin/season/horizon; score joins validation targets. Cache identity includes source/config/contract hashes, training-key and validation-ID-union hashes, cutoff, state order, horizon and model definition. No incompatible-role or full-history fitted cache reuse.

Implement inputs/roles, then estimators/scoring, then runner/audit/report. One label pass and count aggregation avoid query-by-donor computation. Cache vectors/regions by `(model,horizon,origin,season)`; annual vectors can be shared across seasons. No unrelated generic framework refactor.

## C09 — Bounded execution after later approval

Lifecycle: `APPROVED -> SYNTHETIC_CHECKS -> INPUT_AND_PILOT -> PRIMARY -> FORECASTS_FROZEN -> SCORED_AND_AUDITED -> FRESH_REPLAY -> REVIEW_SUBMITTED`. Current state remains `REVIEW_REQUIRED`.

| Resource | Proposed v2 cap |
|---|---:|
| Complete source/role reconciliation, support preparation and resource pilot | 600 s |
| Complete primary fitting/scoring/uncertainty/audit/report | 900 s |
| Fresh preparation/fitting/scoring/uncertainty/audit/report replay | 900 s |
| Cumulative real-data execution | 2,400 s (40 minutes) |
| Processes / numerical-library threads | 1 / 1 |
| Combined RSS / total new artifacts | 8 GiB / 5 GiB |

These reduced-scope caps are stopping limits, not measured runtime promises. All real-data startup, verification, interrupted/failed attempts count. No automatic retry, budget transfer or expansion. Code preparation/small synthetic fixtures are outside the real-data clock. Do not change the science to fit a cap.

The pilot verifies **complete** source/chronological rosters, then times training-only aggregation and all declared validation forecast keys/regions at both horizons. It must not calculate or inspect validation skill. Time scoring, uncertainty and report costs with deterministic timing-only fixtures of the required dimensions. No favourable-cell or reduced-case substitution.

Save workload counts, measured rates, setup costs, output-size/RSS estimates and full-run projections with a 2x reserve. Primary/replay must each fit their cap; unmeasured material work cannot be assigned zero cost. Failed capacity stops before the complete experiment and returns evidence. Once later execution approval exists and the finite gate passes, finish that approved bounded experiment without an additional permission gate.

Persist access/resource progress, atomic outputs and receipts; enforce deadlines with a watchdog. Integrity/leakage/nonfinite failures stop immediately. Preserve partial evidence without completion claims or selective seasonal results. No repeat seed, alternate date window, final-test run or next feature experiment follows automatically.

## C10 — Conformance and independent review

| Test ID | Required evidence |
|---|---|
| SEA2-01 | UTC seasons, Dec/Jan, leap day, exact horizons and unique source keys |
| SEA2-02 | Exact full-source counts, manifest membership and checksum/forbidden-read rejection |
| SEA2-03 | Inclusive/exclusive dates; required label before/at/after T; sequential purge accounting |
| SEA2-04 | Cross-year/cross-horizon validation-ID union exclusion and disjoint fitting/validation IDs |
| SEA2-05 | Final seasonal-to-annual count identity, hand-calculated vectors, mass, fallback/unsupported status |
| SEA2-06 | No extra ID votes across seasons; compressed/atomic primary arithmetic agree; secondary slices condition original weights |
| SEA2-07 | Independent Brier examples with zero truth; 90% ties, E membership and K90 match shared helper |
| SEA2-08 | Audited cohorts/keys and 41/0 fallback cases with 1/36 / 0 weights reproduce; forecasts freeze before scoring |
| SEA2-09 | Independent Counter/set/vector reconstruction of both models and every validation key, region and metric |
| SEA2-10 | Paired 45-ID multipliers, six-screen quantiles and acceptance flags independently reproduce |
| SEA2-11 | Source/config/role identities, stale/partial-cache rejection, bounded resources and complete artifacts |
| SEA2-12 | Fresh replay: exact keys/counts/IDs/regions/fallback flags, numeric tables within absolute 1e-12, deterministic figure bytes identical |

Failures stop interpretation and are reported. Plausible aggregate scores cannot excuse discrepancies. Independent audit uses separate reconstruction arithmetic, not the production fit/scorer as its own oracle. Historical S3 scores are not regression targets because cohorts changed.

Freeze the replay equality inventory before execution. Scientific forecasts/matrices/masks/weights/scores/uncertainty belong in it. Run IDs, timings and resources differ legitimately and receive lineage/schema/budget checks, not equality tests. Deterministic figures must not embed changing timestamps/run IDs. Incomplete or failed replay blocks a successful deliverable alias.

## C11 — Deliverables and visual comparison

Create a new `seasonal_conditioning_s4_e1_<UTC timestamp>` namespace under `results/runs/` and `provenance/runs/`; preserve old experiments. User-facing dates use Australia/Sydney.

Required delivery:

1. Contract/approval/config/source/environment/input hashes; access/resource/pilot receipts; complete status and any failure evidence.
2. Original-key roles and purge reasons; training/validation ID sets; final annual/seasonal per-ID counts; common weights and support/year tables.
3. Training-only matrices and all validation forecast keys, vectors/regions/fallbacks; `validation_forecast_freeze.json` before scoring; no all-development refit.
4. Four-row model/horizon Brier/H90/K90 table; two paired contrasts, ordinary/adjusted intervals and flags; support, zero-truth, E, issued mass and fallback diagnostics.
5. English `REPORT.md`, local `review.html`, chart data and ten fixed PNG figures: metrics; paired differences/intervals; training cell-season support with validation fallback; train/validation year-season composition and descriptive seasonal scores; plus six map figures (origins 44744/44742/44382 x 7/30 days). Each map shows annual B2 and four seasonal rows with matched scales and 90% outlines. Label missing/fallback panels; do not select a nicer replacement origin. All maps use **2012–2019 training fits only** and are illustrative; skill uses 2020–2022 validation.
6. Independent conformance report, primary/replay comparison and hashes; visual inspection of plots, scales, missing panels, links and report values.

Separate engineering completion, Brier benefit, quality costs, uncertainty and support limitations. Show distinct 7/30-day conclusions. If c=1 fails, retain its actual full-case result; do not replace the model row with annual B2 after observing scores. Only missing-season case-level fallback is authorised.

Create `results/deliverables/seasonal_conditioning_s4_e1` only after complete audit/replay. No model replacement, new search, SST development, stage closure, commit or push is included.

## C12 — User review checkpoint

Review: fixed chronological windows; required-label-time and whole-ID exclusions; two untuned B2 models; c=1 where supported and explicit annual fallback; raw-pair fitting and unchanged hierarchical evaluation; full-case standard Brier/fixed 90% regions; point versus supported acceptance per horizon; six conditional screens; four result rows; training-only illustrations; 10+15+15-minute caps and fresh replay.

**Current outcome:** v2 contract and aligned planning records are ready for review. The earlier support audit is input evidence only. No S4 E1 implementation, config, execution approval, model fitting, forecast, pilot or replay has been created or run by this revision task.
