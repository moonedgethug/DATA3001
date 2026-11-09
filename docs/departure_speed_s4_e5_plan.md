# Step 4 E5 | Does departure speed improve destination forecasts?

**Engineering design for review · 5 November 2026 (Australia/Sydney).** The user accepted the sequence: hold the E4 heading model fixed and test speed magnitude on its own. Approval of this document will authorize a separate development and execution round. The voting curve, speed scale and resource limits below are E5 proposals.

## 1. Decision to make

For an object already in a known 1° origin cell, does its net speed over the immediately preceding hour help predict its stopped destination 7 or 30 days later? Slow departures might concentrate near the origin or favor a different branch. Fast departures might lead to another distribution. Historical endpoints determine the answer; the estimator imposes no relationship between speed and distance traveled.

| Forecast | Information supplied at departure | Use in E5 |
|---|---|---|
| Annual B2 | Origin cell and horizon | Primary matched reference |
| Speed B2 | Same origin and horizon, plus scalar past-hour speed when available | Sole fitted candidate |
| Sealed E4 Heading B2 | Origin, horizon and usable heading under the original E4 rules | Descriptive reference on the same cases. Reuse frozen results and weights. |

The primary contrast is Speed B2 minus annual B2. A future joint experiment would compare heading + speed against heading alone. Comparing E5 with E4 as two separate forecasts cannot establish that conditional gain. E4's corrected Brier test supported heading at 7 days and was inconclusive at 30 days. [E4 results](departure_direction_s4_e4_results.md)

## 2. One input and a fixed population

Use sealed release v7, pooled drifter scenario, arbitrary qualified origin times in R, direct exact 7/30-day stopped labels on D plus absorbing exit E. Fit raw observation-pair frequencies, and evaluate with the existing equal-time-within-ID/origin, equal-ID-within-origin, equal-origin hierarchy. Reconstruct E2 block C and its two internal forward windows. Reserve the union of outer validation IDs across both horizons before support checks; keep those IDs out of all training and internal validation. Each internal split is constructed inside eligible outer training and removes its own held-out IDs across horizons. At each fitting boundary the observation interval required to establish the label must end strictly before cutoff, including the earlier-established exit rule.

| Role | Fitting departures | Held-out departures | Fitting pairs / IDs, 7d | Held-out pairs / IDs, 7d | Fitting pairs / IDs, 30d | Held-out pairs / IDs, 30d |
|---|---|---|---:|---:|---:|---:|
| Inner 1 | 2001–2013 | 2014–2016 | 170,978 / 234 | 41,761 / 50 | 151,045 / 204 | 35,035 / 40 |
| Inner 2 | 2001–2016 | 2017–2019 | 209,934 / 280 | 44,612 / 58 | 183,256 / 240 | 41,123 / 54 |
| Outer | 2001–2019 | 2020–2022 | 265,393 / 338 | 33,971 / 45 | 235,177 / 294 | 30,128 / 42 |

Use the verified E4 past-hour feature table, pinned through the completed primary run receipt. Join features by (ID, origin source observation) and reconcile origin time and cell, then join role-specific cases by (ID, origin source observation, horizon). A valid speed is the nonnegative magnitude of the WGS84 net displacement between two qualified positions of the same ID divided by exactly 3,600 seconds. It describes historical net motion over that hour. The previous position may be outside the release cell. Keep provenance keys and the existing interval-quality flags. Consume only the scalar speed for prediction. Valid zero and small positive speeds carry information. Missing first rows, time gaps and failed position quality give an unavailable feature. Broken joins, inconsistent metadata or a negative/nonfinite value on a declared valid interval are integrity failures. The locked final-test pool stays excluded. [E4 feature definition](departure_direction_s4_e4_plan.md#2-heading-extraction-and-time-provenance) · [E2 role roster](../results/deliverables/temporal_validation_s4_e2/role_roster.csv)

Existing E4 evidence, reconciled without scoring E5, gives the following expectations:

| Days | Valid speed but E4 flagged low speed | Weight of those cases | Missing speed | Weight missing speed |
|---|---:|---:|---:|---:|
| 7 | 4,582 | 8.330% | 11 (9 first rows, 2 gaps) | 0.124% |
| 30 | 3,310 | 5.376% | 10 (8 first rows, 2 gaps) | 0.127% |

These are input-availability counts. They do not measure speed's predictive value. In reporting, use the E4 fitting-role speed decile only to describe the low-speed stratum. It must never suppress a speed vote, set the bandwidth or select a model. [E4 fallback evidence](../results/deliverables/departure_direction_s4_e4/fallback.csv)

## 3. Proposed speed votes

Choose a single transparent local averaging rule. Use a fitting-only speed scale b = Q₇₅ − Q₂₅ (m/s), computed with linear quantiles over valid speeds including zero. Each distinct eligible fitting (ID, origin source observation) contributes once across horizons and origin cells. One b applies to both horizons in that role. The scale follows the central spread of past speeds, so a few unusually fast records cannot set the width through the sample maximum. No bandwidth search is needed. Applying a local weighted average to an endpoint indicator estimates a conditional destination probability. The choice of an IQR and the particular bounded weights is proposed here. [Nadaraya, *On Estimating Regression*](https://doi.org/10.1137/1109020)

For a query speed s and a usable historical donor speed sᵣ in the same origin/horizon row, set

$$
K_r(s)=\tfrac12+\max\!\left(0,\;1-\frac{|s_r-s|}{b}\right).
$$

Equal speeds receive 1.5 raw votes, a difference of b/2 gives 1 vote, and differences of b or more give 0.5 vote. This keeps the same maximum 3:1 contrast as E4 for interpretability. The speed formula is a new proposal. Observations are not placed in fast/slow bins.

Prior to E5 scoring, the sealed training speed inventory gives b≈0.429294, 0.434826 and 0.424621 m/s in inner 1, inner 2 and outer training respectively. Verify at full precision within each future fitting role. For example, with the outer scale and a 0.20 m/s query, donors at 0.20, approximately 0.41 and at least 0.625 m/s receive roughly 1.5, 1 and 0.5 raw votes respectively. The same rule applies when a donor is slower than the query.

Let V be donors in the annual row with usable speeds, N the count of all qualified training pairs in it, Aⱼ the annual B2 probability and Yᵣ donor r's endpoint. For V nonempty, divide each usable donor's K by the mean K in V; donors with unavailable speed keep weight one. With these normalized weights wᵣ define

$$
 S_j(s)=\frac{1}{N}\sum_r w_r(s)\,\mathbf 1\{Y_r=j\},\qquad
 P_{h,j}(s)=A_j+\beta_h\,[S_j(s)-A_j],\quad 0\le\beta_h\le1 .
$$

The usable group retains |V| total votes, all records together retain N, and every annual-positive destination stays positive. Use A for an unavailable query speed, empty V, fewer than two valid fitting keys, or a nonpositive fitting IQR. Report feature fallback by reason separately from valid but neutral adjustments (e.g., all K equal or β=0). An unsupported annual origin row has the common unsupported mask, contributes no Brier or region score, and remains in the eligibility report. Do not assign an exit or invent a cell for this case.

**Implementation after approval.** For each fitting origin, horizon and observed destination, sort the usable donor speeds once. The base kernel mass is 0.5 times the usable count. The triangular bonus on [s−b,s] and (s,s+b] can be obtained by binary searches, prefix counts and prefix sums of speed. Keep exact repeated pairs/ties, invalid-donor counts and exit. Normalize the total usable mass and reconstruct complete vectors over the annual-positive states. This matches direct donor voting without materializing a query-by-donor matrix. Check boundary ties, nonnegative masses and numerical agreement with literal donor votes.

## 4. Train β₇ and β₃₀, then freeze

Fit counts, valid-donor summaries and b independently in each inner fitting role. For every held-out case, obtain Aₜ and Sₜ from its own fit. Concatenate both windows. Combine repeated times for an (ID, origin) across windows before allocating that ID's vote. Use all common B2-supported cases with their normalized weights aₜ, including fallback cases where Sₜ=Aₜ.

Let dₜ=Sₜ−Aₜ and yₜ be the observed one-hot destination on D plus E. For each horizon,

$$
 U_h=\sum_t a_t\Vert d_t\Vert^2,\quad
 V_h=\sum_t a_t(y_t-A_t)^\top d_t,\quad
 \widehat\beta_h=\operatorname{clip}_{[0,1]}(V_h/U_h).
$$

This minimizes pooled inner Brier, L(β)=L(0)−2βVₕ+β²Uₕ. Choose zero for Uₕ=0 or a gain of at most 10⁻¹² over zero. Save U, V, the unrounded β, both boundary scores and per-window curves. Verify by independently calculating direct Brier at the solution and on a 0.01 grid. Freeze both selected weights. Rebuild annual counts, b and speed summaries on the complete outer training role; freeze outer source keys, predictions, fallback flags, 90% masks and case weights before joining actual 2020–2022 endpoints. Do not use outer results to choose the kernel, scale, subgroup or β.

## 5. What counts as a result

Give the full roster first. Within each horizon all variants face the same source keys, observed labels, support mask and weights. Reconcile the unrounded annual vectors, weights, H90/K90 and Brier to E4 at absolute tolerance 10⁻¹². Expected annual B2 metrics are 0.995653 / 1.010730 Brier, 75.015% / 49.422% hits and 18.167 / 61.029 cells for 7 / 30 days. E4 heading figures may be displayed in a separate descriptive column with their original labels.

The two primary hypotheses use Δₕ = mean paired Brier(Speed B2) − mean paired Brier(annual B2), separately for 7 and 30 days. Test H₀: Δₕ ≥ 0 against H₁: Δₕ < 0. Use the standard unhalved multiclass Brier on all states. Reuse the E4 whole-ID multiplier procedure with 10,000 shared Exp(1) draws, PCG64 seed 20261105, renormalization within each origin and equal origins. For observed difference d and replicate d*, report the ordinary conditional 95% interval and centered upper bound d−quantile₀.₀₂₅(d*−d). The two lower-tail tests use Bonferroni family-wise 5%. Evidence of Brier benefit requires a negative corrected upper bound.

Use the established nominal 90% probability region including positive ties at the cutoff. H90 measures observed membership, including E when admitted. K90 counts geographic cells. Report both paired changes and descriptive 95% intervals. Point-level quality preservation requires lower Brier (Δ<−10⁻¹²), H90 at least as high and K90 no larger (numerical tolerance 10⁻¹²). Report Brier evidence separately from operational trade-offs. Report region mass, true endpoints assigned zero probability, exit probability and observed exits.

**Diagnostics only.** Report (a) valid low speeds at or below the outer E4 threshold, including any valid zeros, (b) other valid speeds and (c) unavailable speed. In each group give cases, IDs, origins, original target weight and matched performance using original weights renormalized to the group. Separate zero, query missing, no usable donors, zero scale and no-change cases, with both pair fractions and weight fractions. Distinct IDs may occur in multiple strata. A subgroup gain does not replace the primary result. These are fixed-fit development backtests on previously inspected years. Common forcing and refitting uncertainty limit generalization.

**Decision per horizon.** A supported Brier gain with point-level quality preservation makes speed a candidate for the separately reviewed incremental heading-plus-speed comparison. A gain with an operational cost is reported as a trade-off. Otherwise mark speed-only benefit unestablished for this design. This round cannot settle interactions with direction or establish a physical speed effect. For location-only releases, the applicable forecast remains annual B2.

## 6. Engineering gates and deliverables after approval

1. Verify the approved plan identity, manifest, E4 input receipt and pre-score hashes for the past-hour feature table and role roster. Verify source-key joins and E4 baselines before interpretation. Use sealed projected inputs, with explicit allowlists and final-test isolation. Keep the existing E4 run immutable.
2. Synthetic fixtures cover equal/zero/low/missing speeds, ties at the triangle midpoint and boundary, degenerate IQR, unavailable donors retaining one vote, β=0/1, flat/interior optima, support conservation and exit. Check prefix sums against literal votes on fixtures and representative rows in every role. Changing held-out speeds cannot change training b; changing outer features/endpoints cannot change selected β. Changing only outer outcomes must leave forecasts and masks identical. Independently recover the Brier, region membership/size, ID weights, bootstrap decisions and fallback accounting.
3. Proposed budget is 600 s cumulative pilot, 1,200 s primary and 1,200 s fresh replay (50 min total), one process / one numerical thread, 8 GiB peak RSS and 5 GiB new artifacts. Pilot the complete roster and kernel workload, with synthetic outer targets for scoring. Require 2× reserved runtime/storage projection before formal execution. Charge unsuccessful attempts and preserve their receipts. Stop for review on capacity or integrity failure.
4. Use a new `departure_speed_s4_e5` namespace. Save feature/role identities, quantiles/scales, donor summaries, selection curves, case-level probabilities and 90% regions, denominators and paired draws. Deliver an English report, local HTML and figures for the weight curve in m/s, inner β selection, paired metrics, low-speed/other/missing diagnostics and fallback. Require fresh replay with exact keys, labels, masks and flags, numerical agreement within 10⁻¹² and byte-identical figures.

This is the design checkpoint. No E5 fitting, outcome testing or model execution has occurred.
