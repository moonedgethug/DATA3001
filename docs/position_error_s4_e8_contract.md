# Step 4 E8 v2 — Does verified position uncertainty improve seven-day destination forecasts?

## Material Passport

- Date: 6 November 2026, Australia/Sydney.
- Origin: academic-research-suite / experiment-agent / plan.
- Status: **REVIEW_REQUIRED — model development, pilot and experiments are not authorized.**
- Data readiness: the user accepted the verified training-only error overlay. Its usable subset passes the source/scale gate; unavailable records remain unavailable.
- This revision supersedes the [unexecuted v1 proposal](position_error_s4_e8_contract_v1_superseded.md). It does not change the research-stage ledger, base data, repair release, E7 implementation or historical results.

## 1. Question, scope and changes from v1

**Question:** With the same exact release position, historical neighbours and equal pair votes, does representing each usable historical endpoint by its verified positional uncertainty improve the seven-day destination distribution?

The estimand remains a fixed-lag Markov transition kernel, K_7(x,A): the probability of a destination in geographic set A given the recorded current position x. A continuous state space and a mixture of local observation-error distributions are compatible with this Markov framework. This round neither proves the Markov assumption nor introduces a learned Gaussian transport model, MDN, latent state or Step 5 estimator search.

| Item | Proposed v2 definition |
|---|---|
| Horizon and scenario | Seven days only; pooled; existing qualification, release region R and stopped transport domain D |
| Fitting / development validation | 2001–2019 / 2020–2022; frozen whole-ID exclusions and cross-boundary label purges |
| Origin and neighbours | Recorded exact lon/lat; WGS84 distance; fixed 100-km cap; E7-selected k=8,000 with original cutoff ties |
| Training vote | Every selected historical pair keeps weight 1/n; no error-based reliability weighting |
| Intervention | Historical **endpoint** positional uncertainty only |
| Origin error | Retained and audited, but not used to move the query, change neighbours or alter weights |
| Main outcome | Energy Score against the recorded exact validation endpoint |
| Other outcomes | Legacy combination loss; actual hit rate and area of the same nominal 90% region construction |
| Map | 0.5-degree aggregation for display only; no cell-based main score, hit, area or evaluation weighting |

Changes from v1:

1. Replace the unresolved scale gate with an explicit, hash-pinned repair overlay and per-record usability rules. Do not use the corrupted original errors as an experimental control.
2. Remove validation-endpoint-CI scoring from this round: those errors were not repaired or approved for use. No outer endpoint error is read. Repairing and evaluating them would be a separate proposal.
3. Keep the proposed direct drifter-equal evaluation, explicitly distinguished from E7's ID-by-origin-cell hierarchy. Recompute all controls under the same new score and weights.
4. Do not rerun full inner-window model selection: there is no new hyperparameter to select. Use 128 predetermined inner queries for engineering/numerical checks; evaluate **all 33,971 outer cases** once. This avoids repeating 86,373 inner forecasts without a selection purpose. Inner checks are not estimates of full-window predictive performance.

Using only endpoint uncertainty isolates one intervention and avoids assuming that the retrospective hourly product's origin CI would be available at release time. The broader prediction goal remains where things end up; neither an individual location CI nor its radius is a seven-day transport forecast.

## 2. Frozen evidence and availability

Base release: **per-drifter-cleaned-20261017-v7**.

| Artifact | Required SHA256 |
|---|---|
| English Data Contract v1.0 | 6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446 |
| Dataset manifest | c71a7ac3d0230b7489bcfc417d4caceb26ffc1230644a11300a642d7812e041e |
| E7 training_coordinates.parquet | 8638434fb651d10737a2827350d5ff98a3a76a5f3427778748c17a3ddb68715d |
| Accepted repair manifest | d95864f397e21c4a770605f44555cfaf19d7fae24289916f07d0667e857c2c94 |
| Accepted error_overlay.parquet | cf77af02d7af69b255d84b40f49bd5d7c4ad41f35816e00a58926ad6f47dd8f3 |

Resolved E7 run: results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z.

Repair release: provenance/migrations/position_error_repair_20261106T073218_242005Z. Read its manifest and full/error_overlay.parquet explicitly; a moving deliverable link is insufficient. The [repair report](../provenance/migrations/position_error_repair_20261106T073218_242005Z/REPORT.md) and [source trace](position_error_s4_e8_source_trace.md) provide the evidence chain.

The repair accounts for 355,247 unique observations from 338 training IDs. Both axes are usable for 332,770 observations (93.673%). This is an observation-level availability rate, not forecast coverage.

A read-only join of frozen E7 roles to the accepted overlay gives:

| Fitting role | Pairs / IDs | Usable endpoint-error pairs | Point-fallback pairs | Usable share |
|---|---:|---:|---:|---:|
| 2001–2013 | 170,978 / 234 | 170,965 | 13 | 99.9924% |
| 2001–2016 | 209,934 / 280 | 209,277 | 657 | 99.6870% |
| 2001–2019 | 265,393 / 338 | 249,577 | 15,816 | 94.0405% |

All these fitting endpoint keys exist in the overlay; all fitting exit counts are zero. The inner fitting sets are subsets of the frozen outer-training pool. A missing overlay key during implementation is therefore an integrity failure, not an ordinary error-unavailable record.

The usable-field median amplitudes are approximately 227 m east–west and 174 m north–south. They are not millimetres; they are also not seven-day transport radii. Usable amplitudes have long tails (about 11.2 km / 9.9 km maxima by axis). Preserve them without clipping or inflation. Availability is lower in the later fitting pool, so report query-level availability and its period/location-system distribution; do not assume missingness is random.

The original repair release stays immutable. E8 may read its values but may not revise classifications, repair more IDs, combine versions, multiply original values by 100,000, or alter base tracks.

## 3. From repaired marginal CI to a working spatial distribution

### 3.1 What is known and what is assumed

For accepted records, the native-source fields have support as **95% marginal location-CI amplitudes in degrees**, rather than variances or raw standard errors. The [author's GPS estimation code](https://github.com/selipot/hourly-drifters/blob/714b15e871f23ccabe5be01fdf3227a818ea1160/LatLonLocalWess.m#L118-L139) applies a quantile to estimated standard errors and outputs coordinate offsets. That supports the half-width interpretation; it does not establish Gaussian shape, axis independence, or empirical joint coverage.

Define h_lon and h_lat from the accepted repaired columns, never from the original columns. At endpoint latitude phi, convert to local east/north half-widths in kilometres using WGS84 curvature radii N(phi) and M(phi):

$$
h_E=N(\phi)\cos\phi\,{\pi h_{lon}\over180\times1000},\qquad
h_N=M(\phi)\,{\pi h_{lat}\over180\times1000}.
$$

N and M are in metres. This is a local metric conversion; validate its small-angle approximation against WGS84 distances at the observed extreme widths.

The fixed working observation-error kernel is

$$
s_E={h_E\over1.9599639845},\quad s_N={h_N\over1.9599639845},\qquad
R_r=\begin{pmatrix}s_E^2&0\\0&s_N^2\end{pmatrix},\quad
\epsilon_r\sim N_2(0,R_r).
$$

Dividing by 1.96 **matches the repaired 95% marginal width to a proposed normal kernel**. It does not claim to recover the original estimator's exact standard deviation or degrees of freedom; the historical source sometimes used a t quantile. Main rho=0 and width multiplier=1 are fixed working assumptions, not inferred facts or tunable parameters.

Map epsilon from endpoint y_r by WGS84 geodesic direct mapping: distance equals its local Euclidean length and azimuth equals atan2(east,north). The resulting geographic measure is Q_r. No square root of an error field, extra scale conversion, minimum width, truncation at 95%, or rejection/resampling over land is allowed.

Under this working normal model, an individual local 95% ellipse is

$$
\{\epsilon:\epsilon^TR_r^{-1}\epsilon\le-2\log(0.05)\}.
$$

This ellipse is only an optional location-uncertainty illustration. It is not the final predictive region. Two separate 95% marginal intervals also do not imply 95% joint coverage.

### 3.2 Interpretation limit

Each usable endpoint becomes a small probability cloud with higher central density. The full forecast remains a weighted collection of historical destinations and can be multimodal. The transport distribution is not assumed to be one Gaussian.

The recorded endpoints already contain estimation error. Adding Q_r is a test of **CI-assisted empirical smoothing**, not an identified deconvolution or a proven posterior distribution of latent true locations. Success against recorded endpoints supports prediction of those observed locations. It does not by itself prove better prediction of unobserved physical truth. [Ferro (2017)](https://doi.org/10.1002/qj.3115) discusses this distinction for forecast verification with observation error.

## 4. Unavailable errors: retain their observations and votes

Join by base version, ID and source_obs; verify time, coordinates, repair manifest and provenance. Only ci_2d_usable=true permits the two-dimensional kernel.

| Overlay condition | E8 action |
|---|---|
| Both axes accepted | Use repaired amplitudes once to construct Q_r |
| One axis accepted | Preserve its provenance, but use the original endpoint point mass in this round |
| Unresolved zero, missing source, coordinate/version conflict, unexplained difference | Use the original endpoint point mass; retain its original vote and reason |
| Missing key, duplicate join, base/hash mismatch | Stop as an integrity failure; do not call it scientific missingness |

A point fallback means **no justified extra spreading**, not a claim of zero measurement error. Do not delete pairs/IDs, renormalize only over usable-error donors, impute typical GPS accuracy, borrow another record's error, or fall back to the corrupt original error. Unavailable error is not an unresolved transport state U.

For every query save

$$
a(x)={\#\{r\in N(x):\mathrm{ci\_2d\_usable}_r\}\over n(x)}.
$$

Report donor counts, independent IDs, largest-ID vote share, a(x), point-fallback mass and reasons. Predeclare diagnostic a(x) strata: zero, (0,0.5), [0.5,0.9), [0.9,1), one. These strata do not change the full-roster primary result. If a(x)=0, the candidate must equal the point baseline exactly.

## 5. Four matched forecasts; no fusion or parameter search

Let N(x) be the frozen E7 neighbours and V(x) their usable-error subset. All A/B/C donors and their 1/n votes are identical. The 100-km cap applies to **historical starts**, not to endpoint locations or artificial clipping of a position-error kernel.

| Label | Definition | Purpose |
|---|---|---|
| A — ExactPoint | Original empirical endpoint point masses | Primary control |
| B — EndpointCI | Each usable endpoint uses its own Q_r; remaining endpoints stay points | Only primary candidate |
| C — MatchedSpread | Same usable subset, but give every usable endpoint the same local covariance R_bar(x) | Separate record-specific error information from generic spreading |
| B2Point | Original annual B2 donor rule, represented by exact historical endpoints | Secondary historical anchor, rescored fairly |

$$
F_A={1\over n}\sum_{r\in N(x)}\delta_{y_r},\qquad
F_B={1\over n}\left[\sum_{r\in V(x)}Q_r+\sum_{r\notin V(x)}\delta_{y_r}\right],
$$

$$
\overline R(x)={1\over |V(x)|}\sum_{r\in V(x)}R_r.
$$

For C, use Q_r with R_bar at each usable donor's own endpoint. This preserves average added east/north covariance and point-fallback mass, while removing the association between a particular endpoint and its uncertainty width. It does not promise identical global-coordinate moments after geographic mapping. If |V|=0, C=A; if |V|=1, C=B.

No model is selected after seeing outer results. The primary contrast is B−A. B−C diagnoses attribution. B2Point retains its original 1-degree **conditioning rule** but uses exact endpoints for scoring and continuous regions; 0.5-degree cells are never a training or scoring target.

## 6. Data roles and evaluation population

Preserve the E7 temporal and whole-ID rules, including the historical ID reservations made across both original horizons. Do not rebuild a more permissive seven-day-only split.

| Role | Historical fitting | Held-out period | Held-out pairs / IDs | E8 use |
|---|---|---|---:|---|
| C_T0 | 2001–2013 | 2014–2016 | 41,761 / 50 | Engineering/numerical pilot pool |
| C_T1 | 2001–2016 | 2017–2019 | 44,612 / 58 | Engineering/numerical pilot pool |
| C_outer | 2001–2019 | 2020–2022 | 33,971 / 45 | Complete formal development comparison |

Only the fitting role's endpoints and error rows may construct its predictor. Do not compute covariance summaries or availability thresholds across a held-out ID. The globally repaired table is a source repository, not authorization to feed all its rows to every role.

Freeze outer donor definitions, all distributions, numerical settings, regions and example keys before exposing outer endpoint coordinates to scoring. Outer endpoint errors remain unread. The main validation target is the recorded exact coordinate; it need not be turned into a CI to evaluate a continuous probabilistic forecast.

Use equal times within each drifter, then equal drifters, for every primary metric:

$$
\bar L={1\over D}\sum_{d=1}^{D}{1\over n_d}\sum_t L_{dt}.
$$

This explicitly replaces E7's ID-by-origin-cell aggregation for this experiment. Training still uses equal selected-pair votes. All four forecasts share the same cases and new evaluation weights. Old E7 Brier/H90/area tables cannot be subtracted from the new scores; any legacy cell-weighted table is labelled supplementary.

The final-test pool stays locked. The 2020–2022 period has been repeatedly inspected in development; it is not fresh confirmatory evidence. The source hourly positions/CI are retrospectively processed, so this experiment also does not establish operational real-time information availability.

## 7. Main and auxiliary scores

Map each geographic position to zero-height WGS84 geocentric coordinates psi(y), in kilometres. Use Euclidean chord distance in that space for all groups; do not compute distance in degrees or silently substitute geodesic distance in the proper-score proof.

$$
ES(F,y)=E\|Z-\psi(y)\|-\tfrac12 E\|Z-Z'\|,\qquad Z,Z'\overset{iid}{\sim}\psi_\#F.
$$

**Lower is better.** This is the loss orientation of the Energy Score with exponent one; its distributional propriety follows from [Gneiting and Raftery (2007), section 4.3](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf). It applies to both point-supported and continuous forecasts. All legitimate low-probability/zero-mass observed outcomes remain scored.

The existing auxiliary formula in [markov_scoring.py](../src/data3001/modelling/common/markov_scoring.py) is preserved mathematically:

$$
L_{aux}={ES\over100\ \mathrm{km}}+{\|E(Z)-\psi(y)\|^2\over(100\ \mathrm{km})^2}.
$$

Use exact coordinates instead of cell centres. Report both terms and their sum. This is not E[d+d^2]; it combines the full-distribution ES with a mean-location penalty. No coefficient tuning, candidate selection or reversal of the ES conclusion is permitted through this auxiliary result.

The main score targets recorded observations. No ES_soft, overlap-of-CIs hit test, validation-error spreading, or claimed observation-error correction is included in v2.

## 8. A common, cell-free nominal 90% predictive region

A finite empirical point measure can put 90% mass on a zero-area set. Comparing that directly with a continuous density's highest-density region would reward a representation difference. Use a **common distribution-quantile ellipse** for every forecast instead.

1. Project the full geographic prediction into fixed WGS84 Lambert azimuthal equal-area coordinates, centred at lon=-75, lat=35, in km. Specify WGS84 explicitly; [PROJ documentation](https://proj.org/en/stable/operations/projections/laea.html) describes the equal-area projection. Verify valid forward/inverse geometry for the relevant domain and computed boundaries.
2. Obtain distribution mean m and covariance S. For full-rank S define D²=(u−m)' S^(-1)(u−m).
3. Let q90=inf{q: P_F(D²≤q)≥0.90}; use the forecast's own distribution, not validation outcomes and not a fixed Gaussian chi-square cutoff.
4. Define R90 by D²≤q90. Its area is pi*q90*sqrt(det(S)) km². Numerical polygon/intersection calculations must converge to the analytic equal-area ellipse area.
5. Keep all cutoff atoms/ties and report attained mass, which can exceed 0.90. For a mixture, include fallback atoms and continuous mass together. Do not build separate 90% sets and union them without checking total mass.

This is not a minimum-area/HDR region. It may include low-probability space between modes; the same limitation applies to all controls. It is chosen to make this first comparison interpretable without adding a density-bandwidth search.

For genuine rank deficiency, use the forecast's point/line support and the corresponding quantile set; report area zero and degeneracy explicitly. A pseudoinverse alone must not create an unbounded strip. Use a documented machine-precision rank rule, not a physical variance floor. Degenerate rows remain scored and cannot establish an area benefit. Unexpected numerical degeneracy is an engineering failure; a genuine degeneracy rate above 1% requires review of region comparability before a quality-preservation claim.

For each model report:

- Actual point hit 1{psi_LAEA(y) in R90}; drifter-equal H90 and its gap from nominal 0.90.
- Drifter-equal mean area (primary area guardrail), weighted median and 10th/90th percentiles in km².
- Attained model probability, its excess/shortfall relative to 0.90, degeneracy and numerical uncertainty.
- Total geographic area as primary; wet, land and outside-D intersection areas as supplementary quantities, without clipping and relabelling the result as another 90% region.

Maps aggregate the complete distribution into 0.5-degree cells and overlay the continuous R90 boundary and exact observed point. No cell count determines area; no cell-membership lookup determines a hit. An optional individual CI illustration must be labelled separately from R90.

## 9. Land, exit and unavailable transport support

Preserve E as the existing absorbing first-exit label; never give it a fictitious coordinate. A position-error draw on land or outside D is an observation-uncertainty draw, not evidence of a trajectory exit or grounding. Retain and report this probability; do not reject, truncate or redistribute it.

All frozen fitting roles currently have E=0. Confirm that the frozen formal cohort retains its existing exit status during approved execution. If unexpected E or unsupported cases appear, stop and reconcile identity/roles rather than deleting them. If a legitimate E exists in the locked definition, report exit Brier and E mass separately, and label geographic ES/regions as conditional on non-E with explicit denominators. A/B/C must have identical p_E.

No donor remains a transport-support failure; it is distinct from unavailable error, for which point fallback is defined. New U, NaN, unaccounted tails or missing queries fail engineering acceptance. The proposed spatial-quality guardrail also limits B−A's mean land-mass increase and mean outside-D-mass increase separately to at most one percentage point; do not double-count their overlap into a new metric.

## 10. Statistical comparison and decision rules

For each outer ID retain the paired mean ES difference B−A. The primary hypothesis is a lower drifter-equal ES for B. Resample whole IDs with replacement 10,000 times using PCG64 seed 20261106; retain all times of each drawn ID, fixed forecasts and paired models. Report percentile two-sided 95% intervals for ES differences, H90 differences and ratios of drifter-equal mean areas.

These are conditional development intervals. They exclude refitting/model-selection uncertainty and do not remove dependence from shared ocean forcing. They are not precision based on 33,971 independent hourly cases. Also report year strata, per-ID effects and leave-one-ID-out summaries; these are diagnostics, not additional routes to claim success.

| Decision component | Predeclared requirement for B versus A |
|---|---|
| Engineering valid | All cases and weights retained; input/provenance, mass and numerical checks pass |
| Supported ES benefit | Upper endpoint of the paired 95% interval is below zero |
| Practically resolved ES benefit | Relative mean ES reduction at least 0.1%, and estimated numerical uncertainty no more than one tenth of that minimum effect |
| Observed quality preservation | H90_B≥H90_A and mean_area_B≤mean_area_A, with direction resolved beyond numerical uncertainty |
| Statistical noninferiority guardrails | Lower 95% bound of H90_B−H90_A≥−0.01; upper 95% bound of mean_area_B/mean_area_A≤1.02 |
| Geographic guardrails | Both additional land mass and additional outside-D mass≤0.01 |
| Error-specific attribution | B−C reported; only a supported lower ES versus C supports added value of record-specific error allocation |

The one-percentage-point and 2% margins are proposed noninferiority tolerances, not proof of exact equality or zero degradation. Keep both the point-estimate direction and interval criteria. A minor area increase is a trade-off even if it lies inside the statistical margin. If numerical uncertainty straddles a decision boundary, classify the result as numerically inconclusive rather than passing it with rounding.

Report one of: supported benefit with guardrails met; benefit with trade-off; practically tiny effect; evidence insufficient; worse performance; numerical/engineering inconclusive. A B−A benefit without B−C evidence supports this spreading construction, not unique value of each record's uncertainty. Failure to demonstrate benefit does not prove that location uncertainty is irrelevant.

No automatic default-model replacement, post-hoc width inflation, extra kernel-family search, or Step 5 transition follows this experiment.

## 11. Proposed implementation, numerical controls and resource gates

After approval only, create an isolated E8 config, overlay adapter, empirical distribution builder, continuous score/region modules, runner and audit under the existing modelling/baselines structure. Reuse E7 role construction and exact neighbour search. Preserve historical scorers and outputs; the old cell-matrix scorer is a formula reference, not a suitable continuous implementation to call unchanged.

Store donor lineage, per-query usable fractions, frozen kernel definitions and numerical seeds; do not materialize every Monte Carlo draw for every query. A/B/C reuse the same selected neighbours and weights. No global query-by-training matrix or per-query n-by-n donor-distance matrix is permitted. Stream query batches; numerical sampling does not remove training donors from the defined model.

ES estimation uses independent donor pairs for Z,Z', common random numbers across models, and directly coupled B−A/B−C differences to reduce noise. Start with 4,096 pairs per query; predeclared increases are 8,192, 16,384, 32,768 and 65,536. Use exact first moments/finite sums where inexpensive; do not drop finite-ensemble diagonal terms by accident or clip noisy negative estimates to hide numerical error. The auxiliary squared-mean term needs either a sufficiently verified mean or two independent mean estimates whose cross-product avoids simulation bias.

Regions start with 16,384 quadrature/simulation points and may increase to 32,768 or 65,536. Preserve donor/component weights and point masses explicitly; use shared draws across comparisons and independent replication for error assessment. Estimate moments/quantiles against the same mathematical distribution. Cache deterministic endpoint transformations where valid. A particle approximation must not silently become the scientific model or lose tails.

| Phase | Work and proposed limit |
|---|---|
| Source/implementation gate | Verify pinned overlay, all role joins, CI conversion, fallback and score/geometry fixtures; no new downloads |
| Resource/numerical pilot | 128 fixed inner queries, 64 per window, selected by sorted keys with deterministic support/error-availability strata; no outcome-based selection; all attempts together≤10 min |
| Formal comparison | All 33,971 outer cases, all four forecasts and complete scores/regions;≤120 min |
| Independent audit |≤30 min; separate score calculations, independent integration seeds, fixed audited cases and complete aggregate reconciliation |
| Whole run |≤160 min resource runtime including failed attempts;≤8 GiB peak combined RAM;≤5 GiB new retained output; at most two isolated processes |

These are proposed caps, not measured runtime claims. Proceed after the pilot only if twice the projected formal runtime fits its cap and memory/storage have a twofold reserve. Full execution is not authorized by this document. Reaching a limit means preserve receipts and report a bounded partial result; do not shrink the case roster, cap, donor count or accuracy requirement to finish.

Numerical acceptance:

- Defined mixture weights sum to one within 1e-10; A/B/C have exactly identical donor lists, votes and exit mass.
- ExactPoint reproduces E7's selected donor lineage, including cap and ties; compatible 0.5-degree display probabilities reconcile as an engineering check only.
- Small discrete fixtures match exact ES sums; independent score paths agree; fitted outcomes cannot affect neighbour construction or frozen regions.
- Main mean ES contrast's numerical uncertainty≤0.1 times the 0.1% practical-effect threshold. For a claimed effect, repeat-seed changes must also be≤10% of its magnitude.
- Continuous/mixture region probability has verified integration uncertainty≤0.005; report overshoot from atoms separately. Boundary-error estimates must support≤0.1 percentage-point uncertainty in H90 and≤0.5% in mean area, with stricter convergence if needed to decide a claimed smaller effect.
- Area/intersection calculations converge, no hidden land rejection or tail renormalization occurs, and rank/tie handling is reproducible.
- Serial and isolated-process runs reproduce deterministic lineage/definitions exactly; stochastic outputs agree within predeclared numerical bounds.

Freeze random streams by experiment, role, query key, model coupling and replicate; do not use process-dependent default hashes. Numerical refinements follow the registered precision ladder, never whether B appears to win. Use the same 128 inner cases for a labelled rho=−0.5/+0.5 sensitivity check only, without selecting rho or claiming full-period robustness. Unknown correlation remains a limitation even if these examples look stable.

## 12. Required delivery and approval boundary

A timestamped E8 run must contain the approved contract/config hashes, base and repair fingerprints, case/role rosters, donor lineage, fallback reasons, frozen predictions/regions, per-case scores, per-ID paired summaries, bootstrap draws, numerical/resource receipts and independent audit.

Deliver an English report and local review.html with:

1. A/B/C/B2Point ES, auxiliary components, H90 and continuous area on identical cases/weights, with paired uncertainty.
2. Endpoint-error availability and fallback mass, stratified by period, source location system and query availability; no complete-case-only headline.
3. Attained 90% model mass, absolute empirical coverage, geographic spill, unsupported/degenerate cases and numerical uncertainty.
4. Same-start, same-scale 0.5-degree maps with continuous boundaries and exact observed endpoints; reuse the six frozen E7 example keys, without selecting successful examples.
5. A precise conclusion separating a CI-kernel effect, generic spreading, record-specific error allocation and unresolved physical calibration.

A completed experiment may show no useful gain. Preserve the point estimator if the proposed decision criteria are not met; do not keep adjusting error widths until a gain appears.

**Approval requested for the scientific choices:** endpoint-only uncertainty; the fixed normal working kernel with rho=0; point fallback with full votes; A/B/C plus B2Point; direct drifter-equal continuous evaluation; the common quantile ellipse; the declared quality margins and pilot-gated resource limits. The accepted repair does not itself authorize these model choices. No model code, pilot, fitting, forecasting or scoring has been run for E8 v2.
