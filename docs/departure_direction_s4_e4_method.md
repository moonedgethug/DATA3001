# Step 4 E4 | Does departure heading improve destination forecasts?

**Scientific method for review, 5 November 2026.** The proposed E4 comparison is annual B2 versus a direction-adjusted B2. This is a method definition, with implementation and execution subject to subsequent engineering review.

## Question and evidence

For a drifter already in a given 1° cell at a chosen time, does its direction over the immediately preceding hour improve the predicted stopped destination distribution 7 or 30 days later? The two horizons have separate estimates and decisions. The working assumption is local: within an origin cell, departures with similar headings may sample a similar transport branch. Their eventual endpoints may still differ substantially. An improvement would establish the predictive value of this heading proxy on the assessed roster, including any association with subcell location.

The historical iterative M1vcat run reduced Brier relative to M1 by 0.005481 at 7 days and 0.000536 at 30 days, while increasing the geographic footprint. It combined speed and direction, retained the velocity category during propagation and scored observation pairs under calendar-mixed grouped CV. This motivates a separate direct, direction-only test under forward validation. [Historical experiment](../results/runs/markov_vcat_cv_20261026T155955_651594Z/REPORT.md)

## Heading available to the forecast

At t₀ use the east/north geodesic interval velocity from the previous position to the current position of the same drifter. Require exactly one elapsed hour, finite components and two qualified positions with reliable mapping. The previous position may be outside the release cell. Normalize the interval vector to unit length. A query pointing northeast has the same input direction at 0.2 m/s and 0.6 m/s when both speeds meet the reliability rule. Speed magnitude does not otherwise enter the forecast.

Proposed low-speed rule: within each fitting role, pool its unique eligible (ID, origin source observation) keys across horizons and cells. Compute the 10th percentile (linear quantile) of strictly positive valid one-hour speeds. Treat speeds at or below that threshold, exact zero, missing intervals and intervals failing quality checks as having unavailable heading. Recompute the threshold inside each inner fit; freeze the outer threshold from outer training only. This is a proposed noise screen, not a physical minimum speed. If there are no positive fitting speeds, the role issues annual B2. Report missing, gap, quality and low-speed reasons separately with case, ID and evaluation-weight coverage.

The v7 interval components derive from WGS84 displacement and actual elapsed time. GDP hourly positions are processed historical estimates. A retrospective last-hour vector from the archived product and a measured vector actually available at release are distinct input scenarios. Record source-time provenance before making live-use claims. A release with location alone receives annual B2. [Interval construction](../src/data3001/preprocessing/prep_core.py) · [NOAA hourly GDP](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php)

## Estimator

Fix an origin i and horizon h. Let r index every qualified training pair in that row, N its raw pair count, Yᵣ its destination (a geographic cell or exit E), and V the subset with usable heading. Annual B2 assigns destination j its observed frequency Aⱼ = Σᵣ 1{Yᵣ=j}/N.

For unit query direction q and usable unit donor direction uᵣ, propose

$$
K_r(q)=1+\tfrac12 q^\top u_r
      =1+\tfrac12\cos(\theta_q-\theta_r).
$$

The raw weights are 1.5 for aligned, 1 for perpendicular and 0.5 for opposite departures. The angular difference wraps correctly at north. The coefficient one-half is a fixed engineering choice for a conservative first comparison: even at full adjustment the aligned/opposite ratio is three. The general statistical idea is local averaging on a circle; this specific kernel and cap are project choices. [Di Marzio, Panzera & Taylor, 2009](https://www.sciencedirect.com/science/article/abs/pii/S0167715209002417)

Let K̄ be the mean of K among V. Define wᵣ=Kᵣ/K̄ for usable donors and wᵣ=1 for other donors. Then the total weight of usable donors stays |V| and the total weight of all records stays N. The direction-only reference and issued forecast are

$$
D_j(q)=\frac{1}{N}\sum_r w_r(q)\,\mathbf 1\{Y_r=j\},\qquad
P_j(q)=(1-\lambda_h)A_j+\lambda_h D_j(q),\quad 0\le\lambda_h\le1.
$$

Use A directly for a missing query heading or empty V. An unsupported annual row retains the existing common unsupported status. Vectors sum to one. Every destination observed in the annual row retains positive probability even at λ=1. If all usable donors have identical headings, or their endpoint distributions do not vary with heading, the adjustment leaves the row at A. The adjustment redistributes support across observed destinations. It cannot introduce a destination absent from this annual row.

The calculation can aggregate counts and the sums of east/north unit components by (origin, horizon, destination) once per fitting role. The sum of kernel weights for usable donors reaching j is their count plus one-half the dot product of q and their summed unit vectors. This gives exactly the pair-level formula with no query-by-trajectory search.

**Illustration.** In a hypothetical row, five departures face east and five west. Among the eastward departures, four reach A and one reaches B. Among the westward departures, one reaches A and four reach B. Annual B2 gives A 50%. For an eastward query the full direction reference gives A (4×1.5+1×0.5)/10 = 65%. If training chose λ=0.4, the issued probability of A would be 56%. These values illustrate the rule and are not empirical E4 results.

## Selection, inference and acceptance

Use the S4 E2/E3 temporal roles: 2001–2013 fit → 2014–2016 inner validation, then 2001–2016 fit → 2017–2019 inner validation, inside the eligible 2001–2019 outer fit. Purge crossing labels including the strict required-observation cutoff, retain the established absorbing-exit semantics and isolate held-out drifter IDs across both horizons at every boundary. Fit the direct 7/30-day tables independently. Score the fixed forecasts on the original available 2020–2022 validation roster, including cases using the fallback.

Choose one λ per horizon from the pooled inner held-out predictions. For each case t, let dₜ=Dₜ−Aₜ and let yₜ be its observed one-hot outcome. Give times equal weight within ID/origin, IDs equal weight within origin, and origins equal weight. Combine repeated ID/origin units across the windows before assigning their vote. With these weights aₜ, set

$$
\lambda_h = \operatorname{clip}_{[0,1]}
\left(\frac{\sum_t a_t (y_t-A_t)^\top d_t}{\sum_t a_t\Vert d_t\Vert^2}\right).
$$

This is the bounded Brier minimizer because the score is quadratic in λ. Choose zero for a flat curve or an inner Brier improvement at most 10⁻¹². Freeze the selected weights, fitting-only cutoffs, predictions, regions and fallback flags before outer scoring. Use raw pairs in training and the existing drifter/origin balance in evaluation.

The primary contrast is adjusted minus annual Brier. Reuse E3's paired whole-ID procedure with 10,000 shared multipliers, one-sided family-wise 5% across two horizons, and require the adjusted upper bound below zero for supported benefit. Report actual H90 and mean geographic K90 from fixed 90% regions with existing tie and E rules. Mark point-level quality preservation only if Brier improves, H90 does not fall and K90 does not expand. Report the full roster first, with available-direction and fallback strata as diagnostics. Carry forward the limits from shared ocean events, fixed-fit uncertainty and previous inspection of the development period.

The review decision is whether to adopt this single cosine weighting rule, the low-speed screen and the two-horizon comparison as the basis for an engineering contract. Speed-only and combined motion predictors remain separate research questions. [Existing data and time-key inventory](time_environment_s4_architecture.md#12-departure-season-decision-and-next-predictor) · [E3 inference reference](seasonal_information_s4_e3_plan.md)
