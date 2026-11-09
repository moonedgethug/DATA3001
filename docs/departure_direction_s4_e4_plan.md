# Step 4 E4 | Engineering plan for departure-heading validation

**Review draft · 5 November 2026 (Australia/Sydney).** The user confirmed the 3:1 maximum aligned/opposite donor ratio and the fitting-period bottom-decile speed screen. This draft defines implementation, validation and acceptance for a subsequent approval. [Scientific definition and worked example](departure_direction_s4_e4_method.md)

## 1. Decision and matched population

Does the direction of travel over the hour ending at an arbitrary qualified departure improve the predicted stopped destination at 7 or 30 days? Compare annual B2 with direction-adjusted B2. The inputs are the 1° origin cell, horizon, and a release-time heading when available. Both forecasts use annual pooling, raw qualified-pair training, frozen R/D and the absorbing first exit E. The user-facing output is a probability distribution on the same D cells plus E.

Use the cleaned v7 development pool and existing exact 7/30-day labels. Reconstruct E2 block C and its two internal forward windows. First reserve the outer validation-ID union across both horizons, before checking support or headings. Exclude those IDs from all internal roles and final fitting. At each temporal fitting boundary the sealed required-observation end must be strictly earlier than the cutoff, including exits established before the nominal horizon. Construct inner roles inside eligible outer training and apply their own cross-horizon ID exclusion. A year classifies the departure in the study region. Available 2022 records cover part of the year.

| Role | Fit years | Held-out years | Fitting pairs / IDs, 7d | Held-out pairs / IDs, 7d | Fitting pairs / IDs, 30d | Held-out pairs / IDs, 30d |
|---|---|---|---:|---:|---:|---:|
| Inner 1 | 2001–2013 | 2014–2016 | 170,978 / 234 | 41,761 / 50 | 151,045 / 204 | 35,035 / 40 |
| Inner 2 | 2001–2016 | 2017–2019 | 209,934 / 280 | 44,612 / 58 | 183,256 / 240 | 41,123 / 54 |
| Outer | 2001–2019 | 2020–2022 | 265,393 / 338 | 33,971 / 45 | 235,177 / 294 | 30,128 / 42 |

Reconcile source keys, exclusion flags and weights with the sealed E2/E3 products. The outer evaluation contains 36 / 35 origin cells at 7 / 30 days. All currently have annual training support. Treat roster mismatches as integrity failures. [E2 role evidence](../results/deliverables/temporal_validation_s4_e2/role_roster.csv) · [E3 reference metrics](../results/deliverables/seasonal_information_s4_e3/summary.csv)

## 2. Heading extraction and time provenance

1. Join each eligible departure to its v7 row by (development ID, origin source observation). Check ID, UTC time and origin cell against the sealed label key. Deduplicate (ID, origin source observation) for feature extraction across horizons. Resolve the immediately preceding retained row of the **same ID** in time order, even when it lies outside the release cell or is not itself a qualified 7/30-day departure. A predecessor immediately before a role's starting year may supply past feature context. It creates no training label.
2. Require that the two timestamps differ by exactly 3,600 seconds and agree with the stored elapsed interval. Both positions must have valid coordinates and the existing analytical-row, position and mapping flags. Read the verified qualification sidecar through the existing source-key/time adapter. Use endpoint point flags for this past segment. Source-key collisions, broken joins, checksum failures or incompatible timestamps/fields stop the run. A legitimate first row or time gap is a feature fallback.
3. Recompute the v7 WGS84 inverse geodesic from the previous to the current point. For distance ℓ in metres and initial azimuth α clockwise from north, the east/north interval components are (ℓ sin α, ℓ cos α)/3,600 m/s. Verify the stored `interval_net_ve`, `interval_net_vn` on valid segments against this calculation (component absolute tolerance 10⁻⁹ m/s, relative tolerance 10⁻¹⁰). Record both source keys and timestamps. Feature values see at most t₀. The native `ve`/`vn` fields and subsequent positions are outside this predictor. GDP positions are processed estimates, so this validates historical known-heading forecasts. Live release use requires an equivalent available vector. [Preparation logic](../src/data3001/preprocessing/prep_core.py) · [Qualification adapter](../src/data3001/feature_pruning.py) · [NOAA hourly product](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php)
4. Compute speed s=√(vₑ²+vₙ²). Within **each fitting role independently**, collect one speed per unique eligible origin key across both horizons and all cells. Fit the linear-interpolated 10th percentile τ of strictly positive speeds from valid one-hour segments, one vote per origin key. Apply that fitting role's τ to its donors and held-out queries. Exact zero, s≤τ including ties, or an invalid segment means unavailable heading. For s>τ use u=(vₑ,vₙ)/s. With no positive fitting speeds the entire role falls back to annual B2. Report the actual fraction screened. Ties and the held-out speed distribution can make it different from 10%.
5. Keep source extraction separate from destination labels, threshold fitting and scoring. Allowlist the sealed development labels, the necessary manifest-owned development track/qualification files, and specific reference receipts. Log digests, opened files and feature source keys. The final-test pool stays locked. The earlier time-key inventory found a preceding key for 33,847 / 33,971 and 30,019 / 30,128 outer cases, equivalent to 96.89% / 97.25% of target weight. These figures measure timestamps only. Actual usable-heading rates will be measured after quality checks and the role-specific cutoff. [Time-key inventory](time_environment_s4_architecture.md#12-departure-season-decision-and-next-predictor)

## 3. Fit and issue two forecasts

Fix fitting origin i and horizon h. For its N training pairs let Yᵣ be the destination of donor r, including E. The annual forecast Aⱼ is its raw endpoint frequency. When the query and donors have usable unit headings q and uᵣ, let V be the usable donor set. Use the confirmed kernel and weights

$$
K_r=1+\tfrac12 q^\top u_r,\qquad
\bar K=|V|^{-1}\sum_{r\in V}K_r,\qquad
w_r=\begin{cases}K_r/\bar K&r\in V,\\1&r\notin V.\end{cases}
$$

Thus aligned, perpendicular and opposite directions have raw weights 1.5, 1 and 0.5. Usable donors retain |V| total votes, other donors keep one vote each and total votes remain N. Form Dⱼ=Σᵣwᵣ1{Yᵣ=j}/N, then issue Pⱼ=Aⱼ+λₕ(Dⱼ−Aⱼ). Keep λ=1 as the mathematical basis for tuning; the two outer headline rows are annual and training-selected.

| Condition | Action |
|---|---|
| Valid query and at least one usable donor in the annual row | Use the normalized direction adjustment |
| Missing, gapped, poor-quality, zero or low-speed query heading | Return A exactly and retain the case |
| Valid query, no usable donor headings | Return A exactly and retain the case |
| Donor without usable heading inside a supported row | Count its observed destination with weight one |
| Annual training row unsupported | Common mask for both methods, exclude from Brier and region metrics, report counts and original target weight |

Implement an exact count-based calculation. Store per destination the unusable donor count, usable donor count nⱼ and sum mⱼ of usable unit vectors. The usable kernel mass at j is nⱼ + ½qᵀmⱼ. Compute only on the annual row's positive states and use the full D-plus-E state order for scoring. Positive donor weights preserve all annual-positive destinations. Every prediction must sum to one within 10⁻¹². This avoids a historical-pair search for every query. Cache keys include the role, threshold, row, source key and query heading. Forecasts for different headings in the same cell may differ.

## 4. Choose λ₇ and λ₃₀ using only the inner predictions

Fit annual counts, thresholds and direction summaries independently on each inner fit. Generate Aₜ and Dₜ for its own held-out keys, including fallback cases with Dₜ=Aₜ. Concatenate the two inner held-out windows. For each horizon, weight times equally within each (ID, origin), IDs equally within origin and origins equally. If an ID/origin recurs across windows, pool all its eligible scored times before assigning its single vote. Use the common annual-supported roster.

For yₜ the one-hot endpoint, dₜ=Dₜ−Aₜ and normalized evaluation weights aₜ, compute

$$
U_h=\sum_t a_t\|d_t\|^2,\quad
V_h=\sum_t a_t(y_t-A_t)^\top d_t,\quad
L_h(\lambda)=L_h(0)-2\lambda V_h+\lambda^2U_h .
$$

Each horizon selects one λ shared by all origin cells. If Uₕ>0, clip Vₕ/Uₕ to [0,1]. Use zero for a flat curve or a gain of at most 10⁻¹² Brier over zero. Save both fold curves, pooled coefficients, unrounded selections, boundary scores and fallback weights. Independently evaluate Brier at the analytic solution and on a 0.01 grid as an arithmetic check. Freeze both selections, then rebuild the annual counts, threshold and direction summaries on the entire eligible 2001–2019 outer fit. Freeze all outer feature keys, probabilities, fallback flags, masks and weights **before** joining actual outer destinations to score.

## 5. Matched evaluation and decision

On each supported validation source key, compute standard unhalved Brier Σⱼ(pⱼ−yⱼ)². Build the nominal 90% region with the shared function: sort positive state probabilities, accumulate to 0.90 with the existing 10⁻¹² tolerance, and include all positive ties at the cutoff. H90 is membership of the actual endpoint, including E when admitted. K90 counts only geographic cells. Use the same equal-time / equal-ID / equal-origin weights for Brier, hits and mean size. Zero-probability truths receive their full Brier score.

| Horizon | Annual B2 Brier | Actual H90 | Mean K90 |
|---|---:|---:|---:|
| 7 days | 0.995653 | 75.015% | 18.167 |
| 30 days | 1.010730 | 49.422% | 61.029 |

The displayed values are rounded historical reconciliation targets. Check annual vectors, regions, source keys and score weights against E2/E3, and unrounded Brier/H90/K90 to absolute 10⁻¹². The full roster is primary. Also report reliable query versus fallback (reason, cases, IDs, cells and original weight), empty donor rows, missing-direction donor share, zero-truth rate, exit probability, observed exit, region mass and support. Diagnostic subsets retain original weights renormalized within the subgroup; a subgroup improvement cannot replace the full-roster result.

Define Δₕ as mean paired Brier of the direction-adjusted forecast minus annual B2. Test H₀: Δₕ≥0 against H₁: Δₕ<0. Use 10,000 shared whole-ID Exp(1) multipliers, PCG64 seed 20261105 as in E3, with the same multiplier across all origins and both horizons for each ID. Renormalize ID weights within origin and keep equal origins. With observed difference d and replicate d*, use the centered one-sided upper bound d−quantile₀.₀₂₅(d*−d) (linear quantile). The two horizon-specific one-sided tests use Bonferroni family-wise 5%. Report ordinary two-sided 95% conditional intervals for the paired changes as well. [E3 inference reference](seasonal_information_s4_e3_plan.md)

- **Supported directional benefit** requires the corrected Brier upper bound below zero for that horizon. A λ of zero or identical forecasts gives no demonstrated gain.
- **Point-level quality preservation** requires ΔBrier<−10⁻¹², ΔH90≥−10⁻¹² and ΔK90≤10⁻¹². Report a statistically supported Brier gain and a footprint/hit trade-off separately if their judgments differ. Consider retention per horizon on the two criteria together.
- Interpret the result as a development backtest on already inspected periods, conditional on the two fits and this fixed kernel. ID resampling handles repeated cases within drifters; uncertainty from refitting, model selection and shared ocean events is additional. Heading may also proxy for within-cell location. An inconclusive result leaves this predictor unresolved on the assessed design.

## 6. Execution gates and review artifacts

| Gate | Required evidence after approval |
|---|---|
| Source and synthetic checks | Verify origin-key joins, qualification sidecars, previous interval across a cell/year boundary, first row/gap/invalid flags, zero and tied threshold speeds, threshold deduplication across horizons, and strict whole-ID/label-time isolation. With origin keys fixed, altering coordinates after a query time must leave its extracted heading unchanged. With all inner records fixed, perturb outer endpoints and query speeds: fitting thresholds and selected λ must be identical. Changing only outer endpoints must also leave outer predictions, masks and fallback decisions identical. |
| Arithmetic checks | Aligned/perpendicular/opposite ratio, angular wrap at north, missing donors retaining one vote, identical-direction neutrality, exit, no new or lost support and λ=0/1. Verify the direct donor calculation on prespecified fixtures and representative observed rows against the sufficient-statistic calculation. Independently rebuild counts/sums and verify normalization, raw-key Brier, regions, hierarchical aggregates and the inference flags. |
| Bounded pilot | Proposed caps of 600 s pilot, 1,200 s primary, 1,200 s fresh replay (50 minutes cumulative), one process / one numerical thread, peak 8 GiB RSS and 5 GiB cumulative new artifacts. Charge failed attempts. Full role/feature and forecast inventory; synthetic outer targets for scoring/report timing. Measure canonical/sidecar I/O and full forecast sizes. Require projections with 2× reserve before primary/replay. Stop for review on failed capacity or integrity; keep full samples and the fixed study. |
| Reproducibility | Bind explicit later approval to the plan hash. Freeze source/config/environment and immutable input hashes. Record thresholds, coverage and reasons per role, donor summaries, inner curves and selected λ, source-keyed predictions/regions, case scores, within-ID differences, multipliers and decisions. Store compressed forecasts over annual-positive states with a shared state index. Reconstruct full vectors losslessly. Use source- and role-specific caches and record resource/access receipts. |
| Publication for review | Create a separate `departure_direction_s4_e4` run namespace, English results, local HTML, metric and paired-interval figures, inner curves and coverage/fallback plots. Verify a fresh replay with exact keys/masks/labels, numerical identity within 10⁻¹² and byte-identical figures. Create the local deliverable alias only after checks pass. |

Proposed components reuse chronological roles, sealed labels, the qualification adapter, annual B2, probability regions, scoring and multiplier conventions. Isolate E4 past-motion extraction, direction sufficient statistics and audit/report adapters under the Markov baselines. E4 keeps the approved dataset intact. This draft was prepared from existing code, schema and historical outputs; E4 feature extraction, development and fitting await engineering confirmation.
