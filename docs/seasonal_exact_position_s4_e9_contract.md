# Step 4 E9 — Final seasonal comparison at exact release positions

## Material Passport

- Date: 6 November 2026, Australia/Sydney.
- Mode: experiment planning; version: v1.
- Status: **REVIEW_REQUIRED. This document authorizes no implementation, pilot, fitting, forecasting or scoring.**
- Scientific design: the user's confirmed four-arm comparison, recorded below without additional models or fusion.
- Verification: existing E7/E8 sources, corrected E8 release and accepted error-repair fingerprints checked. Seasonal support and resource feasibility have not yet been measured.
- Scope of this delivery: this contract and its planning-review receipt only. The research-stage ledger, existing contracts, data, code, configurations and results remain unchanged.

## 1. Question and strict change boundary

**Question:** With the existing exact-position, seven-day empirical Markov predictor, does restricting historical reference pairs to the matching majority season improve destination forecasts, with and without the already defined endpoint-CI treatment?

The four experimental arms are AnnualExactPoint, AnnualEndpointCI, SeasonalExactPoint and SeasonalEndpointCI. SeasonalEndpointCI is the user's primary candidate; SeasonalExactPoint separates season conditioning from CI spreading. The annual arms reproduce the corresponding E8 controls.

There are four season-indexed training pools, not four cell-state matrices. Predictions remain probability measures over geographic positions. The model is a direct seven-day conditional Markov kernel; it does not propagate daily or compose seasonal matrices. A 0.5-degree grid is used only for visualization.

| Confirmed item | Locked definition |
|---|---|
| Horizon | Seven days, exactly 604,800 seconds |
| Time/data roles | Existing 2001–2019 training and 2020–2022 development validation, with the frozen ID exclusions and label-availability purges |
| Scientific intervention | Match the query's seven-day majority season when selecting historical reference pairs |
| Spatial conditioning | Recorded exact release lon/lat; existing WGS84 100-km radius and k=8,000 rule, including cutoff ties |
| Training weights | Equal votes for selected observation pairs; no drifter-level training reweighting |
| Endpoint representation | Original endpoint point masses, or precisely the E8 verified endpoint-error construction |
| Evaluation | Equal times within each drifter, then equal drifters; Energy Score, actual H90 and mean continuous area |
| Fallback | Empty seasonal support only: corresponding annual exact-position predictor. Unusable endpoint error only: original point with its full vote |

**Forbidden without a revised contract and explicit user approval:** annual/seasonal blending; adaptive weights; distance weighting; minimum-ID fallback thresholds; changing k, radius, season boundaries or CI width; expanding support; moving the query; shifting or rotating trajectories/endpoints; learning displacements; correcting origin uncertainty; changing training votes or validation weights; dropping difficult cases; clipping, rejecting or reallocating geographic probability; new predictors; new loss combinations; new region families; grid experiments; learned Gaussian transport or MDN; daily iteration; post-result tuning.

Engineering details supplied for approval in this draft are explicitly limited to: the exact half-season tie rule, numerical seeds and tolerances, audit selection, resource caps, and decision thresholds. They do not become approved by being written here. After approval, code must implement this document rather than reinterpret its intent. Discovery of a conflict requires a written discrepancy report and a pause; it does not authorize a substitute model.

## 2. Immutable inputs and authority

Use the existing cleaned release `per-drifter-cleaned-20261017-v7`. Read the frozen coordinate/role artifacts; do not reconstruct a more permissive sample or download new data.

| Source | Identity / required SHA256 |
|---|---|
| English Data Contract | `docs/contract/data_contract_v1.0.xlsx`; `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446` |
| Dataset manifest | `configs/dataset_manifest.json`; `c71a7ac3d0230b7489bcfc417d4caceb26ffc1230644a11300a642d7812e041e` |
| E7 source run | `exact_origin_s4_e7_primary_20261105T074326_829211Z` |
| E7 training coordinates | `training_coordinates.parquet`; `8638434fb651d10737a2827350d5ff98a3a76a5f3427778748c17a3ddb68715d` |
| Repair release | `position_error_repair_20261106T073218_242005Z` |
| Repair manifest | `d95864f397e21c4a770605f44555cfaf19d7fae24289916f07d0667e857c2c94` |
| Repair endpoint overlay | `full/error_overlay.parquet`; `cf77af02d7af69b255d84b40f49bd5d7c4ad41f35816e00a58926ad6f47dd8f3` |
| Authoritative E8 result | `position_error_s4_e8_20261106T095423_445879Z/numerical_revision_v1` |
| E8 completion receipt | `authoritative_release.json` in the parent provenance run; `5650fb5859582cfbe688f28fbeebfa6d9c87838b7588ebef033ced1b49334abd` |
| E8 independent audit | `numerical_revision_v1/audit.json`; `851e95ae6bf69856e3106548c4593e2410a9e819eb6d651d1ce2540e39259fff` |
| E8 final output inventory | `numerical_revision_v1/outputs_verified.json`; `57164a8ce4f665d8d451e08884c42f19d764c0ccc352bab7f507efdebe5c1043` |

The corrected E8 region implementation is authoritative. Do not reuse the superseded floating cumulative-probability results or the earlier uncorrected output inventory. Reuse requires a content hash and an exact case/model/definition match, not merely a moving deliverable link.

Links: [E8 scientific contract](position_error_s4_e8_contract.md), [corrected E8 report](../results/deliverables/position_error_s4_e8/REPORT.md), [accepted repair report](../provenance/migrations/position_error_repair_20261106T073218_242005Z/REPORT.md), [historical seasonal results](seasonal_information_s4_e3_results.md).

## 3. Data roles and unchanged evaluation population

| Role | Fitting period / pairs / IDs | Held-out period / pairs / IDs | Purpose |
|---|---|---|---|
| C_T0 | 2001–2013 / 170,978 / 234 | 2014–2016 / 41,761 / 50 | Source of fixed engineering-pilot queries only |
| C_T1 | 2001–2016 / 209,934 / 280 | 2017–2019 / 44,612 / 58 | Source of fixed engineering-pilot queries only |
| C_outer | 2001–2019 / 265,393 / 338 | 2020–2022 / 33,971 / 45 | Complete development comparison |

Preserve the E7 role ledger, including ID reservations made across the original 7/30-day study. A training label requiring observations at/after its cutoff is excluded, and a held-out ID cannot contribute any training pair. Assigning a season never changes these roles. Available 2022 observations are not a complete calendar year.

No inner model selection or new cross-validation search is required: k, radius, CI construction and calendar rule are fixed. The inner periods serve engineering and numerical checks, not selection of a winning season definition.

Each pair retains its original `(id, origin_source_obs, horizon_days)` key, actual departure time, start coordinates and endpoint provenance. The same drifter may contribute pairs to multiple seasons within its permitted fitting role. Do not assign an entire drifter to its deployment season, deduplicate its real hourly pairs or count it as four independent validation IDs.

All 33,971 outer cases remain in all four arms. Freeze donor definitions, numerical settings, predictions, regions and figure cases before the new runner opens outer endpoint coordinates for scoring. Prior E8 outcomes have already been inspected; this remains development evidence, not a fresh blinded or final-test experiment. Outer endpoint errors and the 517-ID final-test pool remain inaccessible.

## 4. Exact seven-day majority-season rule

Use the existing UTC meteorological calendar: DJF = December–February; MAM = March–May; JJA = June–August; SON = September–November. Boundaries are 00:00:00 UTC on 1 March, 1 June, 1 September and 1 December. December and the following January/February share the DJF label.

For every training pair and prediction query with recorded departure time t, define the half-open interval W(t) = [t, t + 604800 seconds). Let L_s(t) be the number of elapsed seconds in W(t) belonging to season s. Define

$$
s^*(t)=\operatorname*{argmax}_{s\in\{DJF,MAM,JJA,SON\}} L_s(t).
$$

- If exactly two seasons each occupy 302,400 seconds, choose the **departure season**. This explicit tie convention is an engineering detail awaiting approval with this contract.
- Compute elapsed time from UTC calendar boundaries, with leap years handled by the calendar. Do not count observed rows, rounded days, endpoints or trajectory locations to determine the season.
- A start exactly on a boundary belongs to the new season. The open right endpoint contributes no duration to a later season.
- Use the same full seven-day interval for fitting and prediction; no actual future trajectory, observed endpoint, exit time or data completeness changes its season.
- Save departure season, majority season, durations, cross-season flag and tie flag. A year boundary inside DJF is not a season boundary.

| Example interval | Decision |
|---|---|
| 2021-02-26 00:00 to 2021-03-05 00:00 | 3 days DJF + 4 days MAM: MAM |
| 2021-02-25 00:00 to 2021-03-04 00:00 | 4 days DJF + 3 days MAM: DJF |
| 2021-02-25 12:00 to 2021-03-04 12:00 | 3.5 days each: DJF by the departure tie rule |
| 2020-02-27 00:00 to 2020-03-05 00:00 | Leap year; 3 days DJF + 4 days MAM: MAM |
| A seven-day interval spanning 1 January only | DJF throughout |

This is a single dominant-season approximation for a direct seven-day forecast. It is not a three-day/four-day transport composition. There is no extra departure-season model, seasonal weighted average or post-hoc calendar search in this experiment.

## 5. Exact neighbour selection and equal pair votes

For a role's permitted training pool T and query position x:

1. Annual arms search all of T. Seasonal arms first restrict T to pairs with `s*(training departure) = s*(query departure)`.
2. Compute WGS84 geodesic distance from the recorded query start to each candidate's recorded start. The radius is 100,000 metres; inherit the E7 numerical distance tolerance of 0.000001 metres.
3. Among candidates within that radius, retain the nearest 8,000 pairs, plus every pair within the inherited tolerance of the 8,000th distance. When fewer than 8,000 exist, retain all. The radius cap still applies to cutoff ties.
4. Sort deterministically by distance and original source identity. Preserve distinct pairs with duplicate coordinates. Record global source keys and the exact ordered donor digest.
5. Every selected pair has weight 1/n. No distance, error, season-duration, endpoint-frequency or drifter-count multiplier is applied.

**Season filtering precedes the k-nearest selection.** Filtering the already selected annual 8,000 neighbours is not equivalent and is prohibited. The seasonal set can contain more distant same-season records than the annual selection, but none outside the unchanged 100-km cap. A candidate is never selected using its endpoint or observed validation outcome.

Denote the annual selected set by N_A(x), and the same-season selected set by N_S(x,t). These are identical within each point/CI pair of arms. The 100-km restriction concerns historical **starts** only. Endpoints are neither restricted to 100 km nor translated to the new release point.

## 6. Exactly four probability models

Let y_r be donor r's original recorded endpoint. Let Q_r be precisely the E8 endpoint-error distribution when usable, and the point mass delta(y_r) otherwise. Define N_eff = N_S when N_S is nonempty, and N_eff = N_A only when N_S is empty.

| Code | Model | Definition |
|---|---|---|
| AP | AnnualExactPoint | Equal mixture of delta(y_r), r in N_A |
| AC | AnnualEndpointCI | Equal mixture of Q_r, r in N_A |
| SP | SeasonalExactPoint | Equal mixture of delta(y_r), r in N_eff |
| SC | SeasonalEndpointCI | Equal mixture of Q_r, r in N_eff |

For example,

$$
F_{SC}(\cdot\mid x,t)={1\over|N_{eff}(x,t)|}\sum_{r\in N_{eff}(x,t)}Q_r(\cdot).
$$

This sum combines individual historical votes exactly as approved; it is not a learned blend of annual and seasonal models. Only AP/AC and SP/SC share donor lists. Across annual and seasonal arms, donor lists are expected to differ.

### Endpoint CI: inherited intact from E8

Use only the accepted repair overlay joined to the donor's endpoint by ID/source observation, with matching time, coordinates and base version. Usable native fields are 95% marginal longitude/latitude CI half-widths in degrees. Convert to local east/north kilometres at that donor endpoint using the same WGS84 curvature formula and divide by 1.9599639845. The working local normal distribution has covariance diag(s_E^2, s_N^2), rho=0 and width multiplier=1. Map its offsets around that donor's original endpoint by the same WGS84 geodesic construction.

This is the existing observation-error construction, not a newly fitted Gaussian transport law. No width inflation, clipping, new covariance, correlation sensitivity sweep, MatchedSpread or B2Point arm is added. Origin errors and validation-endpoint errors are not used. A location CI is not the seven-day prediction region; the full historical endpoint mixture defines that forecast.

Coordinate conversion for scoring/area and local CI offsets are the already specified E8 calculations. They do not authorize movement-pattern translation, coordinate reassignment, grid-centre substitution or a change of model representation.

## 7. Two separate fallback rules

| Condition | Required action |
|---|---|
| At least one same-season donor within 100 km | Use that seasonal set, even if its pair/ID support is small; report support without changing weights |
| No same-season donor, annual set nonempty | SP equals AP and SC equals AC exactly for that query, including numerical packets; record seasonal-support fallback |
| Selected endpoint has both accepted error axes | Use its unchanged Q_r in the CI arm |
| Endpoint error missing, zero/unresolved, one-axis-only or otherwise classified unusable by the accepted repair | Use the original endpoint point mass with the full 1/n vote; record endpoint-error fallback |
| Every selected endpoint error unusable | CI arm equals its matched point arm exactly; this does not trigger annual fallback |
| Empty annual set, inconsistent source join, missing/duplicate key or hash/coordinate mismatch | Stop as an integrity/support discrepancy; do not invent a prior, drop the query or relabel it as an ordinary CI fallback |

There is no minimum pair/ID threshold other than zero. In particular, one ID or one pair does not authorize blending with annual data. It may produce a degenerate region, handled under section 9.

Report seasonal fallback as raw query count, fraction, original evaluation-weight share, distinct IDs and seasons. Report endpoint-error fallback as selected donor count, 1/n probability mass, and drifter-equal average mass, separately for annual and seasonal arms. Also report their overlap; do not add the two percentages as if they were disjoint events. No sample is removed and no usable-error-only renormalization is allowed.

The previous 5.959462% error-unavailable training-pair fraction is an E8 pool statistic, not a predicted seasonal fallback rate. Seasonal rates remain unmeasured until approved execution.

## 8. Evaluation and matched comparisons

For D validation drifters, with n_d eligible departure times for ID d, give query (d,t) weight w_dt = 1/(D*n_d). For every metric L:

$$
\bar L={1\over D}\sum_{d=1}^{D}{1\over n_d}\sum_t L_{dt}.
$$

Training remains equal-pair; evaluation remains equal-ID. Do not restore equal-origin-cell weighting, equalize seasons/years or give an ID another full vote in each season. Subgroup tables use these original weights renormalized within the displayed subgroup, with its weight share shown.

**Energy Score:** retain E8's exponent-one loss using zero-height WGS84 ECEF coordinates psi(y) in kilometres:

$$
ES(F,y)=E\|Z-\psi(y)\|-\tfrac12E\|Z-Z'\|,\qquad Z,Z'\overset{iid}{\sim}\psi_\#F.
$$

Lower is better. Use the recorded exact validation endpoint. Do not use degree distances, geodesic distances as an unannounced substitute, cell centres, CI overlap or a smoothed validation target. The score applies to both point-supported and continuous forecasts. [Gneiting and Raftery (2007), section 4.3](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf).

| Contrast | Role |
|---|---|
| SC − AC | Primary: season effect with the user's CI construction retained |
| SP − AP | Prespecified supporting season test without CI |
| SC − SP | Diagnostic: incremental CI effect within the seasonal pool |
| AC − AP | Replication anchor for the completed E8 comparison |
| SC − AP | Practical check against the simpler existing annual point predictor |

All contrasts use identical cases and weights. No new combined loss or model-selection objective is introduced. Historical cell-Brier values cannot be compared numerically to this ES experiment.

## 9. Nominal 90% regions, hits and area

Use the **corrected E8 distribution-quantile ellipse**, unchanged in all four arms:

1. Map the complete forecast to WGS84 LAEA at lon_0=-75, lat_0=35, in kilometres, using the identical projection definition. [Projection definition](https://proj.org/en/stable/operations/projections/laea.html).
2. Compute its mean m and covariance S. For full rank, D²(u)=(u−m)'S^(-1)(u−m).
3. Let q90 be the smallest threshold with model probability P_F(D²≤q90)≥0.90. Use the distribution's own quantile, not a fixed Gaussian chi-square cutoff.
4. R90={u:D²(u)≤q90}; area=pi*q90*sqrt(det(S)) km². Actual hit is membership of the exact observed endpoint in R90.

Retain all boundary atoms/ties and report attained model mass. In mixtures, include original point-fallback mass together with continuous mass. Use corrected integer/rational cumulative-weight arithmetic where applicable; preserve the E8 rank/tolerance rules. No unapproved bandwidth, variance floor or covariance ridge is permitted.

For genuine rank deficiency, keep the corresponding bounded point/line quantile region and report zero area and degeneracy. Do not make a pseudoinverse produce an infinite strip. These cases remain in all scores; zero area cannot by itself establish improvement. If degeneracy exceeds 1% of evaluation weight in any arm, report region comparison as requiring review rather than replacing the region construction.

Report drifter-equal H90, gap from 90%, mean area, weighted area median/10th/90th percentiles, attained probability and numerical uncertainty. This common ellipse is not a minimum-area region or a fitted Gaussian transport model; it can enclose low-density gaps between modes.

Keep frozen release/transport geometry and first-exit semantics. All current fitting/validation cases have zero recorded exit; verify identity after the appropriate scoring gate. Unexpected exits stop the run for reconciliation; do not silently introduce conditional scoring. CI draws over land or outside D are retained and reported, not rejected, turned into exit events or redistributed. Total region area is primary; land, water and outside-D components are diagnostics, not replacement regions.

## 10. Statistical acceptance and scientific stopping

Aggregate paired differences within each whole ID. Use 10,000 paired whole-ID bootstrap draws with replacement, PCG64 seed 20261106, shared across all arms. Keep every time of a sampled ID and the fitted forecasts fixed. Report two-sided percentile 95% intervals for ES differences, H90 differences and ratios of mean area. The two prespecified season-benefit claims, SC−AC and SP−AP, each require a negative 95% upper endpoint (nominal one-sided 0.025 each); together these form a nominal Bonferroni 0.05 family. Remaining contrasts are attribution/practical diagnostics, not extra significance searches.

The following numerical thresholds retain the E8 decision scale and are offered explicitly for approval. None changes a forecast or allows tuning toward a result.

| Requirement | Criterion for a seasonal candidate versus its matched annual reference |
|---|---|
| Engineering validity | Complete identical roster/weights, intact inputs and successful mass/numerical/audit checks |
| Supported ES reduction | Paired 95% interval upper endpoint below zero |
| Useful size | Mean ES reduction at least 0.1% relative to its annual reference |
| Numerical resolution | ES contrast uncertainty at most one tenth of the 0.1% threshold; any claimed effect must also exceed numerical uncertainty sufficiently under section 11 |
| Observed quality preservation | H90 does not decrease and mean area does not increase, with the direction resolved numerically |
| Conditional uncertainty guardrails | Lower 95% H90-difference bound ≥ −0.01; upper 95% mean-area-ratio bound ≤ 1.02 |

The last row retains E8's one-percentage-point/2% uncertainty margins. **It does not override the observed no-degradation row.** A small observed area increase or hit decrease remains a trade-off even if inside those margins. Exact equality from an identical forecast counts as unchanged; an unresolved noisy difference does not. No pass is created by rounding or changing decimal precision.

Decision table:

- **SC passes versus AC:** support for the defined seasonal-CI construction. Also report SC versus AP; if it fails to improve ES practically or sacrifices H90/area against AP, do not recommend replacing AP with SC.
- **SP passes versus AP, SC fails:** retain the evidence for seasonal point conditioning; CI has not earned retention merely because it was part of the proposed candidate. Report the SC−SP contrast without claiming CI benefit from an unadjusted diagnostic alone.
- **Both pass:** report both; if CI's additional benefit is unresolved, prefer the simpler passing point representation as a recommendation, with no automatic production replacement.
- **Lower ES with worse H90 or larger area:** report benefit with trade-off, not quality-preserving success.
- **Neither seasonal arm passes:** close this seasonal route for the present data/design. Retain the existing annual results. No radius/k/season/CI-width/weight follow-up search is authorized.
- **Numerically or technically inconclusive:** report that the experiment could not decide; do not describe it as evidence that seasons have no effect. Stop at the approved budget rather than weakening the definition.

A failed seasonal result does not prove that ocean dynamics lack seasonality. Bootstrap intervals condition on the trained forecasts and do not account for all training variation, shared ocean forcing or repeated development-data inspection. Year, season, cross-season, support and leave-one-ID-out tables are diagnostics only. Completion, including a negative result, ends this registered comparison. Grid experiments and Gaussian-model development require their own later decisions; no such work starts automatically.

## 11. Numerical implementation boundary and verification

After approval, use an isolated E9 adapter/config/runner. Reuse read-only E7 exact neighbour search and the corrected E8 point/CI probability and evaluation definitions. Do not call the E8 orchestration unchanged if it would run MatchedSpread or B2Point; only the two approved representations are needed per pool. Existing scientific functions/configurations and historical artifacts must not be edited in place to implement E9.

Outcome-independent caches may store coordinate transforms, candidate distances, frozen donor keys or verified annual forecast packets. They must preserve probabilities and pass parity checks. Annual AP/AC definitions and donor lineage must exactly reconcile to E8. Existing corrected annual packets can be referenced by hash after identity checks; rescore all four arms into the same E9 table and weights. A fresh numerical annual replay is a reproducibility check, not a new model.

Do not build a full query-by-training distance array or dense per-query n-by-n endpoint-distance matrix. Stream all queries and retain the full defined donor mixture. Numerical quadrature samples approximate the existing measure; they do not replace its training records or define a smaller model.

Inherit the finite numerical ladders: 4,096 / 8,192 / 16,384 / 32,768 / 65,536 independent donor pairs for ES; 16,384 / 32,768 / 65,536 quadrature points for CI regions. Point regions use every selected endpoint. Preserve exactly 1/n total component weight, including ties and point fallbacks. If the largest budget cannot represent every component at the required precision, stop; never truncate cutoff ties.

Share random streams within each pool's point/CI pair. Any annual/seasonal coupling must preserve each marginal donor law and must be checked separately, because those donor lists differ. E8's tiny CI-minus-point Monte Carlo error is not an estimate of the new seasonal-minus-annual error. Use deterministic SHA256-derived stream keys containing experiment, role, original query key, pool and replicate; never process-default hashes. All queries have distinct numerical streams. Report full weighted contrast uncertainty, including annual-packet Monte Carlo uncertainty.

Precision gates:

- Probability sums within 1e-10; exact donor/vote equality within AP/AC and SP/SC; exact annual fallback identity.
- Separate ES first-term and self-distance checks on finite fixtures; correct independent draws with replacement, including diagonal self-pairs; no clipping a noisy score to hide error.
- Aggregate ES numerical uncertainty (3 standard errors) ≤ 0.0001 times the reference mean ES. For a claimed seasonal effect, independent-seed changes must also be ≤10% of its magnitude.
- Independent integration verifies nominal region mass within 0.005; atom overshoot is separately recorded. H90 numerical uncertainty ≤0.1 percentage point and mean-area uncertainty ≤0.5%; stricter resolution is required if a smaller claimed effect depends on the boundary.
- Existing exact 90% integer-CDF regression fixtures remain valid. Rank, projection and polygon calculations reconcile; no physical variance floor or clipping is introduced.

Choose common ES and CI-region budgets before outer scoring using the fixed pilot and outcome-independent outer geometry checks: the smallest registered level passing the precision gates, shared across applicable arms and queries. Move only up the registered numerical ladder to meet precision, not because a candidate loses. Cached annual packets must have the matching frozen numerical settings and pass the new contrast-precision check; otherwise recompute that same annual definition with the common budget and record the numerical change. An unresolved outer decision at the frozen maximum is reported as such. Any unlisted computational approximation or implementation defect affecting definitions is a stop-and-review event; no autonomous replacement or hidden rerun is permitted.

Required independent audit after the formal pass: recompute majority-season labels and compare every selected donor's season/radius/vote; reproduce exact nearest-neighbour sets by an independent full-distance calculation on the fixed 128 pilot cases and fixed audited outer cases; replay all 33,971 region hit/area records from sealed definitions; check ES by a separate calculation on 128 preselected outer cases with independent seeds and the 65,536-pair budget; independently reconstruct all weights, summaries, contrasts and bootstrap intervals. This is computational verification, not a claim of review by a separate human.

For the outer audit, sort the frozen 33,971 query keys by `(id, origin_source_obs, horizon_days)` and select the 128 zero-based positions `floor(j*(33971-1)/127)`, j=0,...,127. Save their full keys before scoring. Boundary/fallback fixtures are additional semantic tests, not outcome-selected validation cases. Pilot source: the E8 parent's `pilot_attempt_4/roster.parquet`, joined by role and query position to the identical frozen inner-role query ordering and then recorded by full keys. If that identity check fails, stop instead of silently choosing another pilot roster.

## 12. Pilot, budget and resource stopping

The measured E8 reference was 78.33 minutes total resource runtime, 56.80 minutes formal processing (including recorded correction/recovery), 18.71 minutes audit, and 1.06 GiB peak process RSS. These figures motivate retaining its caps; they are **not** an E9 runtime forecast. E9 replaces two old arms with two seasonal arms and may reuse the annual packets, but seasonal support, geometry and numerical cost must be measured.

| Phase | Work | Hard cumulative cap |
|---|---|---|
| Source/semantic checks | After implementation approval: input checks and hand-computable tests; no formal outcome scoring | Included in the total and charged to pilot |
| Pilot | Same 128 E8 fixed inner queries, 64 per role, all four arms; use keys from the frozen E8 pilot selection | 10 min, including any failed attempt |
| Formal | All 33,971 cases, all four arms, forecast freeze, scores and required resource/geometry records | 120 min |
| Independent audit and presentation | Independent checks, uncertainty, English report, figures and local review page | 30 min |
| Whole execution | All compute phases above, including failures, corrections and approved retries | 160 min; 8 GiB combined peak RAM; 5 GiB new retained artifacts |

Use one experiment worker. No GPU, remote service, network data acquisition, package upgrade or parallel-worker expansion is required. Shared immutable source files referenced in place are not duplicated; all new output/copies count toward storage. Measure elapsed phase time and cumulative execution time, and check memory/storage at bounded query batches. Keep process-liveness/timeout checks and user progress updates at intervals no longer than 60 seconds.

Before the formal phase, require all semantic/precision gates to pass and **twice the projected full formal time ≤120 minutes**, projected combined RAM ≤4 GiB and projected new storage ≤2.5 GiB. Forecast projection must include all cases, both neighbour searches, both seasonal predictions, annual verification/reuse costs, scoring, lineage and output overhead. Also project audit/report work to fit its own cap. Use maximum/tail costs from the pilot and a full-roster outcome-blind season/support inventory; do not infer cost solely from a fast average case.

The full-roster inventory reports each season's training pairs/IDs, query counts/IDs, cross-season and tie counts, donor/support ranges, empty-season cases, likely degeneracies and CI availability. Freeze it before any formal scores. Its production is part of the formal budget/projection accounting. Counts are descriptive and cannot activate extra smoothing or fallback thresholds.

At a failed gate or exhausted cap, checkpoint completed artifacts and issue a bounded report. Do not lower numerical precision, change k/radius, drop times/IDs, limit the season pool, switch to a cheaper model or automatically expand the budget. Crash retries or corrections require a documented cause and renewed permission when necessary to resume; a resource overrun is not a scientific negative result.

## 13. Semantic fixtures, output contract and review gate

After approval, tests must include: all four calendar boundaries; leap day; exact 3.5/3.5 tie; a year boundary within DJF; query labels independent of endpoints; unchanged chronological/ID roles; season-before-neighbour filtering with a counterexample to annual-k-then-filter; exact 100-km and kth-distance ties; duplicate-coordinate votes; nonempty low-ID support with no annual blending; empty-season paired fallback; partially/all unavailable CI and bad joins; zero-error identity; complete-case weights; independent finite-sum ES; 90% CDF ties; degenerate bounded regions; source immutability and access denial for locked inputs. These are future tests, not tests claimed to have run during contract drafting.

Proposed isolated names after approval: `configs/seasonal_exact_position_s4_e9.json`, `src/data3001/modelling/baselines/seasonal_exact_position_s4_e9*.py`, a dedicated E9 runner/audit, and `tests/test_modelling_seasonal_exact_position_s4_e9.py`. Use unique immutable `results/runs/seasonal_exact_position_s4_e9_<UTC>/` and matching provenance, with a human entry at `results/deliverables/seasonal_exact_position_s4_e9/`. No implementation files are created by this planning document.

Required outputs:

1. Approved contract/config hashes, base/repair/source fingerprints, environment versions, protected-file before/after checks and exact role rosters.
2. Pair/query majority-season records; season durations and tie flags; donor keys/distances/votes/digests; frozen model definitions, random streams and regions; separate fallback reasons.
3. Complete per-case/per-ID scores, the four-arm table, all registered contrasts, paired intervals and numerical uncertainty; support and cross-season diagnostics with denominators. No successful-subset headline.
4. Pilot projection/gate, actual time/RAM/storage, all attempts, independent verification, and a completed/partial/invalid status.
5. English report and local HTML review. Overview ES/H90/area plot; paired effects; seasonal support/fallback panels; six same-start, same-extent, same-colour-scale four-arm maps. Reuse E7's outcome-independent example positions `[26952, 6475, 24032, 23714, 11213, 28115]` after validating their source keys. Overlay exact release/truth points and the common continuous 90% boundary. 0.5-degree cells display mass only. If these examples omit a season/cross-season case, state that rather than choosing attractive replacements after results.
6. A closing decision distinguishing seasonal gain, CI gain, trade-off, no useful benefit and numerical insufficiency. No stage-ledger amendment, publication or automatic model replacement.

**Approval boundary:** the user requested an engineering contract for review. The scientific design is the agreed four-arm experiment. This draft makes its edge cases, inherited numerical operations and stop rules inspectable; it does not grant permission to implement or execute them. Await explicit approval of this version before development. Any later requested scientific change receives a written amendment and separate approval before it affects code or results.
