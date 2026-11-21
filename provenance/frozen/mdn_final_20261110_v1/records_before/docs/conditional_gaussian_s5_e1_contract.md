# Step 5 E1 — Local conditional Gaussian transition model

## Material Passport

- Date: 7 November 2026, Australia/Sydney. Version: engineering review draft v1.
- Mode: experiment design; academic-research-suite / experiment-agent / plan.
- Status: **REVIEW_REQUIRED. No model implementation, pilot, fitting or scoring is authorised by this document.**
- Approved stage definition: continuous-space parametric estimation of transition distributions. This supersedes the earlier S5 heading “Memory / latent states”; it does not authorise those extensions or restart old Gaussian/MDN code.
- Verified for planning: Brolly paper and repository, current E7/E8 contracts, corrected E8 release/audit and existing scoring/geometry interfaces. No new observations, donor searches, parameters, predictions or performance statistics were computed.
- Authorised document changes: this proposal, a planning-review receipt, and the explicitly approved S5 amendment to the research-stage ledger. Historical contracts/results remain unchanged.

## 审阅摘要

问题只有一个：**同样的起点、同样的历史参考记录，把经验落点分布拟合成一个高斯分布，能否改善七天预测？**

建议首轮比较 LocalGaussian、ExactPoint、EndpointCI。固定现有 100 km / k=8,000 近邻规则、逐配对等权训练、2001–2019 训练和 2020–2022 开发验证、drifter 等权评估。高斯的中心与完整协方差由解析公式估计；不同时加入神经网络、季节、速度、模型融合或新的训练权重。

这是 **局部条件高斯**：每个查询位置的参考记录由精确距离确定，再估计五个高斯参数。条件分布是参数化的，但位置到参数的映射仍由近邻决定，不是一个已经学会在任意地点外推的全局神经网络。

研究对象仍是 Markov 转移核。单高斯能填充历史落点之间的空间，但可能把不同去向挤成一团；不预设它一定改善预测。0.5° cell 仅用于展示。主评分为 ES，实际命中率和面积仍按连续 90% 分布分位椭圆计算。

## 1. Research question and alternatives

For a qualified current position x, estimate the direct seven-day conditional destination law K7(x,A). Annual pooling and current-position conditioning remain working assumptions. Fitting a conditional law does not prove that position alone is physically Markovian, or validate repeated seven-day propagation.

**Primary contrast:** LocalGaussian minus ExactPoint in drifter-equal Energy Score. **Required companion contrast:** LocalGaussian minus EndpointCI. Same cases, reference records and evaluation weights in all comparisons.

Three approaches were considered:

| Approach | What changes | Decision for this draft |
|---|---|---|
| Local Gaussian fitted to the existing exact-position reference endpoints | Conditional distribution family, with explicit metric-coordinate construction | Recommended: the smallest matched test of the Gaussian approximation |
| Brolly-style GTGP on origin cells | Source grouping, displacement transfer and Gaussian family | Not proposed: reintroduces training cells and changes more than one ingredient |
| Position-dependent neural single Gaussian, analogous to MDN1 | Globally learned parameter functions, optimisation and regularisation | Deferred: useful later, but would not isolate the first distribution-family comparison |

These are design alternatives, **not three extra experimental arms**. The user has approved the stage and requested this proposal; selection of the recommended estimator and all detailed terms below remains subject to review.

## 2. What is borrowed from Brolly, and what is deliberately different

Brolly §4.3.2 models conditional displacement by a Gaussian, estimating a mean and covariance in each source bin; §4.2 also considers learned position-dependent Gaussian-mixture parameters. These are transition representations within a Markov framework, not proof that Gaussianity is appropriate everywhere. [Paper, v2, §§4.2–4.3](https://arxiv.org/html/2303.11480v2)

The author's `GTGP.fit` computes displacement means and `np.cov`, and falls back to global estimates when a bin has fewer than three records. We inspected [grids.py](https://github.com/mtbrolly/transition_density/blob/master/grids.py), Git blob `76c2d34d3431e9d53d945492e72b7116e3cf6bae`; [model_comparison.py](https://github.com/mtbrolly/transition_density/blob/master/model_comparison.py), blob `bf8855d01c7eccd953ec257939dbc9b03c3b49dc`, supplies the lag/grid-search comparison workflow. Public files were read, not executed or imported.

| Item | Paper / inspected code | Proposed DATA3001 E1 |
|---|---|---|
| Horizon | Four days | Existing seven days; no new lag search |
| Parameter localisation | Source bins in GTGP; network in MDN1 | Existing exact-position neighbour set |
| Gaussian variable | Donor's displacement from its own origin | Donor's unchanged endpoint expressed relative to the query, defined below |
| Covariance divisor | Sample covariance, n−1 | n, the exact local Gaussian maximum-likelihood solution |
| Sparse support | Global parameter fallback in inspected GTGP code | Stop/report unsupported or rank-deficient Gaussian fits; no unapproved global prior |
| Validation | Paper's held-out trajectory split/log score | Existing chronological, whole-ID split; ES and continuous region guardrails |

This is a **method-inspired adaptation**, not a replication of GTGP or MDN1. In particular, replacing a donor's endpoint by “query + donor displacement” would introduce a motion-sharing intervention; that is excluded here. Fitting in degrees or silently changing to a grid-based Gaussian is also excluded.

## 3. Frozen data, support and controls

Keep cleaned release `per-drifter-cleaned-20261017-v7`, Data Contract v1.0, R/D geometry, qualification, observation pairing and original whole-ID reservations. Seven days is exactly 604,800 seconds. No thinning of hourly pairs or reconsideration of ID exclusions.

| Role | Fitting period / pairs / IDs | Held-out period / pairs / IDs | Use |
|---|---|---|---|
| C_T0 | 2001–2013 / 170,978 / 234 | 2014–2016 / 41,761 / 50 | Engineering and numerical pilot only |
| C_T1 | 2001–2016 / 209,934 / 280 | 2017–2019 / 44,612 / 58 | Engineering and numerical pilot only |
| C_outer | 2001–2019 / 265,393 / 338 | 2020–2022 / 33,971 / 45 | Full development comparison |

Cross-boundary training labels remain purged using required observation-interval end, not merely departure year. Fit and validation IDs remain disjoint. The 517 final-test IDs stay locked. No validation endpoint errors are read. The repeatedly inspected 2020–2022 period is development evidence, not a fresh confirmatory test.

Pin these existing sources before approved execution:

| Source | Identity / SHA256 |
|---|---|
| E7 run | `exact_origin_s4_e7_primary_20261105T074326_829211Z` |
| Training coordinates | `8638434fb651d10737a2827350d5ff98a3a76a5f3427778748c17a3ddb68715d` |
| Query coordinates | `0b480d728e008444c493a228ebecb2505da21185aa70d0f07e8513fd6107fea5` |
| Roles | `78da3c85f77e29b303d7137320c33a94580f4822712faace9a7f0a03ffc7fdac` |
| Data Contract v1.0 | `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446` |
| Dataset manifest | `c71a7ac3d0230b7489bcfc417d4caceb26ffc1230644a11300a642d7812e041e` |
| Accepted repair release | `position_error_repair_20261106T073218_242005Z` |
| Repair manifest / overlay | `d95864f397e21c4a770605f44555cfaf19d7fae24289916f07d0667e857c2c94` / `cf77af02d7af69b255d84b40f49bd5d7c4ad41f35816e00a58926ad6f47dd8f3` |
| Corrected E8 results | `results/runs/position_error_s4_e8_20261106T095423_445879Z/numerical_revision_v1` |
| Corrected E8 audit | `851e95ae6bf69856e3106548c4593e2410a9e819eb6d651d1ce2540e39259fff` |

Coordinate filenames are within the pinned E7 run; repair files are within `provenance/migrations/<repair release>`. Resolve geometry through the pinned asset catalog and record hashes. Use immutable run paths, not moving deliverable links. Check the full SHA256 strings against live sources before execution; any mismatch stops work.

For every query x, N(x) is exactly the E7/E8 WGS84 nearest-origin set: at most the nearest 8,000 fitting pairs within 100,000 m, including original kth-distance ties; if fewer exist, use all. Distance tolerances and source-key sorting are inherited, without rounding coordinates. The 100 km limit applies to **historical starts**, not endpoints. Preserve repeated genuine pair observations. Each selected record has weight 1/n(x); training is not drifter-equal.

The three arms:

| Model | Distribution |
|---|---|
| ExactPoint, A | Equal empirical point masses at unchanged selected endpoints |
| EndpointCI, C | E8 endpoint-error kernels for usable records; original point mass and full vote otherwise |
| LocalGaussian, G | One fitted full-covariance Gaussian in query-centred metric coordinates, mapped back to Earth |

EndpointCI inherits accepted 95% marginal CI half-widths, WGS84 conversion, division by 1.9599639845, rho=0, width multiplier=1, and geodesic perturbation. No repair, clipping, extra variance, origin uncertainty, or error-based training weights. Error-unavailable records are retained in all arms. LocalGaussian learns transport spread from recorded endpoints; it neither adds nor subtracts measurement-error covariance.

## 4. Exact Gaussian definition and analytic training

### 4.1 A valid geographic construction

Let y_r be donor r's original recorded endpoint. From the **query x** to y_r compute WGS84 inverse-geodesic distance d_r in km and initial azimuth alpha_r, clockwise from north. Define

\[
v_r(x)=T_x(y_r)=d_r(\sin\alpha_r,\cos\alpha_r)^T.
\]

This is a coordinate representation of the original endpoint; it is **not** the donor displacement T_(x_r)(y_r). Reversing T_x with WGS84 direct geodesics returns y_r. The conversion therefore does not translate any observed endpoint or path.

Fit the local working law

\[
V\mid X_t=x\sim N_2(\mu(x),\Sigma(x)),\quad
Y=G_x(V),
\]

where G_x(v) starts at x and follows a WGS84 direct geodesic with azimuth atan2(v_E,v_N) and distance ||v|| km. G_x(0)=x. This defines geographic probability as the distribution of G_x(V), not as a Gaussian density in longitude/latitude degrees. Full finite draws, including distant tails, are mapped; none are rejected for lying on land, outside D, or far from x. Any nonfinite transformation stops execution.

The normal law is exact in the defined metric vector coordinates; its mapped surface distribution is not globally a Euclidean Gaussian. This distinction, the coordinate convention and geographic tails must be disclosed. The round isolates this specified Gaussian approximation, not a coordinate-invariant claim about all Gaussian models.

### 4.2 Loss and closed-form solution

For n selected pairs, the local average negative log working likelihood is

\[
\ell_x(\mu,\Sigma)=\log(2\pi)+\tfrac12\log|\Sigma|
+\frac{1}{2n}\sum_{r\in N(x)}(v_r-\mu)^T\Sigma^{-1}(v_r-\mu).
\]

For a full-rank empirical covariance, its analytic minimisers are

\[
\hat\mu(x)=\frac1n\sum_r v_r(x),\qquad
\hat\Sigma(x)=\frac1n\sum_r(v_r-\hat\mu)(v_r-\hat\mu)^T.
\]

Retain the off-diagonal covariance: forcing independence or a circular spread is not authorised. There are two means and three distinct covariance entries per query. Use stable centred float64 accumulation, symmetrise roundoff only, and Cholesky-factor the resulting positive-definite matrix. Sampling is V=mu+Lz for z~N2(0,I), LL'=Sigma.

There are **no epochs, learning-rate search, optimisation restarts, covariance inflation, ridge/shrinkage or new hyperparameters** in E1. The likelihood is a local fitting objective, not an assertion that overlapping hourly observations are independent. Report distinct donor IDs and largest-ID contribution.

If n=0, n<3, either eigenvalue is nonpositive, or condition number exceeds 1e12, preserve diagnostics and stop before formal scoring. No silent floor, global fallback or omission of affected cases. A tolerance may diagnose arithmetic error but may not create positive variance. A meaningful regularisation remedy would require a reviewed amendment.

The experiment is locally parametric, not a globally finite-parameter spatial model. Neighbour changes may cause parameter discontinuities. A failure does not rule out a neural single Gaussian or a mixture; those would be separate proposals.

## 5. Validation and information boundaries

No model selection is needed: k/radius, Gaussian family and covariance estimator are fixed. Do not run full inner-window performance experiments just to choose a winner. Within each inner role select 64 pilot queries by sorted source keys at indices floor(j*(N−1)/63), j=0…63. This creates 128 fixed engineering cases, each using its complete fitting pool. Pilot results determine numerical feasibility only.

After approval and successful source/inner-pilot gates, begin the formal allocation with a full outer-start support/rank diagnostic using fitting endpoints and query origins only. Charge that full parameter scan to the formal phase, including a scan that discovers a stop condition. Freeze for all 33,971 queries the ordered donor keys, votes, Gaussian parameters, continuous-region definitions, source/parameter hashes and numerical stream keys before opening outer target coordinates for scoring. No outer endpoint participates in fitting, neighbour selection or region construction.

Evaluate each metric L by

\[
\bar L=\frac1{45}\sum_{d=1}^{45}\frac1{n_d}\sum_t L_{dt}.
\]

Weights depend on original ID/time rosters, never a cell, model support subset, CI availability or predicted region. Preserve the complete case roster. Do not revive E7's earlier equal-origin hierarchy. No tuning, model revision or shift in the primary comparison after outer scoring.

## 6. Scores and common 90% region

### Energy Score — primary, kilometres, lower is better

Let psi map lon/lat at zero height to WGS84 ECEF coordinates in km. For independent draws Y,Y' from the forecast,

\[
ES(F,y)=E\|\psi(Y)-\psi(y)\|-\tfrac12E\|\psi(Y)-\psi(Y')\|.
\]

Use this same distance, target and exponent for all three models. Do not replace it by projected-plane distance, geodesic distance, Brier or squared error. The full-distribution score is applicable to both empirical point measures and continuous forecasts. ExactPoint has no ordinary surface density, so continuous log likelihood is **not** a common primary ranking score. The Gaussian fitting likelihood and ES validation serve different purposes.

Retain the old auxiliary diagnostic, without selection authority:

\[
L_{aux}=ES/(100\,km)+\|E\psi(Y)-\psi(y)\|^2/(100\,km)^2.
\]

Verify numerical mean accuracy or use independent mean estimates to avoid squared simulation bias. Do not infer Gaussian ECEF means by simply transforming mu.

### Same continuous region rule for every arm

In the existing WGS84 LAEA projection centred at lon=−75°, lat=35° (km), calculate each full forecast's mean m and covariance S. Define

\[
q_{.9}=\inf\{q:P_F[(U-m)^TS^{-1}(U-m)\le q]\ge .90\},\quad
R_{.9}=\{u:(u-m)^TS^{-1}(u-m)\le q_{.9}\}.
\]

Area is pi*q_.9*sqrt(det(S)) km² for rank two. Actual hit uses the **recorded exact validation coordinate** inside this region. Keep atom/tie overshoot and the corrected exact-CDF arithmetic from E8. This is a distribution-quantile ellipse, not a minimum-area/HDR region.

For LocalGaussian, q_.9 in LAEA must be computed from its mapped distribution; it is **not automatically** the chi-square quantile from its fitting chart. Apply the same moment/quantile definition to all arms, rather than granting only the Gaussian a different region rule. E8's documented geometric rank handling applies; unexpected nonfinite geometry stops work, and genuine degenerate regions cannot establish an area advantage.

Report drifter-equal ES, actual H90, mean area, area quantiles, attained probability, calibration gap H90−.90, land mass and outside-D mass. The 0.5° map aggregates the full forecast for display only; it determines none of these metrics.

### Geographic and exit semantics

Retain all Gaussian/CI probability on land or outside D and report it; no rejection, coastline repair, clipping, resampling or mass redistribution. Gaussian mass outside D is not automatically observed first-exit E and land mass is not confirmed grounding. Current pinned fitting roles have no observed E; reverify the established cohort exit status after approval. An unexpected E/role discrepancy pauses the run for reconciliation rather than silently changing denominators. E is never assigned an invented coordinate. General mixed exit/geographic scoring is not being redesigned here.

## 7. Numerical precision and reuse

The experiment compares a new Gaussian with an empirical law, so the tiny numerical uncertainty of E8's CI-minus-point increment does **not** imply accurate Gaussian-minus-point scores. Estimate both contrasts' numerical uncertainty explicitly.

1. Reuse verified E7 neighbour search, original point ECEF/LAEA coordinates, exact-CDF arithmetic and corrected E8 region packets when role/key/donor/parameter hashes match. No reuse of obsolete pre-correction regions. Recompute scores under a common declared numerical protocol; old displayed ES values are reconciliation references, not exact constants to subtract.
2. For A/C, reuse the mathematically unchanged E9 ES estimator: exact finite-sum observation-distance term for A; sampled independent donor pairs with replacement, including equal-index pairs; the independently calibrated 1,024-draw squared-distance control variate; and the complete CI-minus-point increment with its covariance. Numerical control coefficients are not model weights. Do not execute the old E9 pipeline or rerun its seasonal arms.
3. For G, propose scrambled Sobol integration in four independent normal coordinates for (V,V'). Use `random_base2`, scramble=True, no optimisation/thinning. Eight independent scrambles per query, each with 1,024 / 2,048 / 4,096 / 8,192 points; corresponding total draw levels 8,192 / 16,384 / 32,768 / 65,536. Convert each pair of uniforms to two independent normals by Box–Muller using −log(1−u), which is finite for u in [0,1). Do not clip inverse-normal tails. This is numerical integration of the frozen law, not eight Gaussian models. [SciPy Sobol documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html)
4. At each level, give A/C that same total donor-pair count. A/C share their appropriate paired streams; G streams are independent of A/C. Estimate G variance from the eight independent replicate means, not from treating Sobol points as IID. Query streams are independent; propagate weighted numerical variances with squared evaluation weights. Use direct paired A/C variance where applicable. A separate full numerical replication uses distinct stream namespaces.
5. SHA256-derived per-query stream seeds include `s5_e1_v1`, fitting role, `(id, origin_source_obs, horizon_days)`, model/numerical task and replicate index; use the first 128 bits little-endian with PCG64. Bootstrap seed is 20261109. Freeze installed numerical-library versions and all keys.
6. Region integration levels M are 16,384 / 32,768 / 65,536 **per reconstruction packet**, not split across replicates. A is exact over all donors; C retains E8 component-stratified weights; G uses a separate two-normal scrambled Sobol sequence. Replicate 0 defines the published region; replicate 1 independently reconstructs it. Never select the more favourable packet. A third stream draws M independent IID samples from the complete C/G law to check the fixed primary region, land and outside-D indicators; a sampled C component uses its original vote, including fallback atoms. Thus a non-point arm costs up to two M-point reconstructions plus an M-draw checker, all charged to the budget. Region-fit, check and ES streams are distinct. Preserve complete component weights even at kth-distance ties; if the maximum level cannot represent them or attain precision, stop.
7. Report each case's check probability and Wilson 95% binomial interval (z=1.9599639845). Define h_q as the larger distance from p_hat_q to either interval endpoint; require h_q<=0.005. The checker is IID, unlike Sobol nodes. Compute true boundary-atom mass b_q from original ExactPoint/C fallback atoms on the frozen region boundary using the inherited 1e−12 Mahalanobis cutoff tolerance; G has b_q=0 even when quadrature nodes tie. For each C/G arm require sum(w_q * (distance(p_hat_q, [.90,.90+b_q]) + h_q))<=0.005. This weighted absolute-distance diagnostic prevents under- and overshoot from cancelling. Also report the signed weighted mass and per-case outliers/intervals. Apply the declared diagnostic on the pilot and formal roster. It is an estimated numerical diagnostic, **not** a simultaneous guarantee that every case has mass within 0.005 of 0.90. Do not require every noisy case interval to lie inside [0.895,0.905], which would reject many correct regions by checker noise alone. Independent packet/refinement and hit/area checks below remain mandatory.

Required numerical gates, applied to **both** G−A and G−C:

- Exact roster/weights/donor identities; empirical weights sum to one within 1e−10. Geographic transform round trips on fitting endpoints within 1e−6 km; otherwise diagnose, not move observations.
- Three estimated numerical SE of each aggregate ES contrast <= 0.0001 times the corresponding baseline mean ES (one tenth of the 0.1% practical-effect threshold). Use inner pilot baseline means for projections and verify again on the formal cohort. Claim-specific replication drift must also be <=10% of the claimed ES improvement.
- Region mass must pass the explicit per-case interval-width and aggregate-mass checks above; true atom overshoot is reported separately. Between independent region packets, weighted validation membership-disagreement rate <=0.001 and mean-area relative change <=0.005. If a claimed hit/area improvement is smaller, numerical uncertainty must be <=10% of that improvement; otherwise call its direction unresolved. These checks cannot select a better-looking packet.
- Separate aggregate land/outside-D numerical uncertainty <=0.001; marginal guardrail decisions unresolved at that precision remain inconclusive.
- At the registered maximum, an unresolved numerical gate means stop/inconclusive. No reduced roster, lowered accuracy or new numerical estimator without review.

For pilot engineering summaries, pool the 128 selected records across the two roles, average their times within each ID and then give IDs equal weight; these are not full-window performance estimates. For each ES contrast, project full-roster numerical variance as max(v_q over the 128 pilot cases) times sum(w_outer^2), where v_q is that paired contrast's numerical variance estimate and w_outer is the unchanged 33,971-case evaluation weight. This is a conservative pilot-based projection, not a guaranteed bound on unseen cases. Verify actual numerical variance over the entire formal roster.

The smallest common passing ES level and smallest common passing region level are fixed by the pilot, solely on precision/cost. Region level selection also requires passing primary-versus-independent reconstruction and M-versus-next-registered-level checks on all 128 pilot cases. The 65,536 level is checked against 32,768 plus independent 65,536 reconstruction; there is no unregistered 131,072 level. The formal verification replicate repeats selected levels with new streams; the fixed 128 outer audit keys are sorted-roster indices floor(j*(33971−1)/127), j=0…127. At formal scoring, a failed precision gate pauses for review; it does not authorise outcome-driven extra levels. All quadrature samples approximate full probability laws; they are not new training observations.

## 8. Statistical analysis and acceptance

Compute each drifter's paired differences first. Resample the 45 whole IDs with replacement 10,000 times, retaining each selected ID's full within-ID average and pairing all models. Forecasts remain fixed. Use percentile two-sided 95% intervals for ES differences, H90 differences and ratios of drifter-equal mean areas. Report year strata, support/ID-share strata and leave-one-ID-out sensitivity descriptively; no post-hoc subgroup becomes the primary result.

Primary H0 is E_ID[ES_G−ES_A]>=0. Test G−A first; only if it passes the prespecified ES criterion can G−C be used for an additional superiority claim. Always report both effects/intervals, but do not choose whichever baseline gives the favourable answer. A joint claim of benefit over both requires both to pass. These development intervals omit refitting uncertainty and do not eliminate dependence from common ocean forcing.

| Decision | Prespecified criterion |
|---|---|
| Engineering complete | All 33,971 cases retained; support/rank, mass, provenance, numerical and audit checks pass |
| Supported useful ES benefit vs a baseline | Upper 95% paired ES bound <0, mean relative reduction >=0.1%, and numerical gates pass |
| Observed quality preservation vs that baseline | H90_G>=H90_baseline and mean area_G<=mean area_baseline, with numerical uncertainty unable to reverse a claimed direction |
| Statistical guardrails | Lower 95% H90 difference >=−0.01; upper 95% mean-area ratio <=1.02 |
| Geographic guardrails | Added mean land mass <=0.01 and added mean outside-D mass <=0.01, separately and numerically resolved |
| Candidate for default-model discussion | Useful ES benefit and all quality/geographic criteria against **both** A and C |

The 1-percentage-point/2% margins quantify tolerated statistical uncertainty, not permission to label an observed degradation as “unchanged”. A smaller region with lower actual coverage is a trade-off. No useful gain is a completed negative/inconclusive comparison, not a reason to add components, widen support or retune covariance. A support or resource failure is incomplete engineering evidence, not evidence against Gaussian prediction.

## 9. Architecture, verification and budget after approval

Use a new `conditional_gaussian_s5_e1_<UTC>` result/provenance identity. Proposed new modules under `src/data3001/modelling/continuous_models/` cover E1 inputs, local parameter fitting/distribution sampling, numerical scoring, pipeline, independent audit and reporting; a separately named config and test module accompany them. Reuse verified low-level helpers without changing historical implementations. Do not call the historical continuous-model trainers, restore their checkpoints, or treat this approval as permission to restart paused experiments.

Store role/source hashes, complete donor lineage, parameters and condition diagnostics, frozen region packets, numerical keys, support/error fallback summaries, per-case/per-ID scores and paired uncertainty. Cache only computations whose exact inputs match; different queries generally need different geodesic coordinate transforms. No global query-by-training matrix or dense per-query donor-distance matrix. Stream bounded batches; do not retain all integration draws.

Meaningful implementation checks after approval:

1. Independent two-pass versus reference-array mean/covariance and n-divisor checks; full covariance/rotation fixtures; identical, two-point, collinear and ill-conditioned support stops.
2. WGS84 inverse/direct round trips, azimuth-axis conventions, zero-distance case and distant-tail mapping; land/outside draws retained.
3. Exact three-arm donor identity, CI fallback full votes, immutable role/ID boundaries and target-access guards.
4. Small empirical ES versus exhaustive sums; isotropic Gaussian planar analytic ES fixture; full geographic G ES versus independent IID integration on the fixed 128 audit cases. Planar fixture formula must not replace geographic formal scoring.
5. Exact 90% rational-CDF/tie regression, Gaussian chart-versus-LAEA distinction, independent area and membership checks; all three arms use one region definition.
6. Independently reconstruct **all** outer Gaussian parameter sets and all three per-ID aggregates; replay all outer regions from frozen probability definitions with separate numerical seeds and compare all outer ES aggregates. Independent arithmetic paths, not merely the same helper called twice.

| Phase | Proposed cumulative cap |
|---|---:|
| Input checks, numerical fixtures and 128-case resource pilot | 10 minutes |
| Full support/parameter freeze and all-three-arm formal forecasts/scores | 120 minutes |
| Independent audit / numerical replication | 30 minutes |
| Report and visual QA | 10 minutes |
| **Total, including failed attempts** | **170 minutes** |

Hard memory cap: 8 GiB aggregate process-tree RSS. New disk cap: 5 GiB including temporary/checkpoint/audit outputs. Start with one process; at most two isolated processes after parity checks, private geometry objects, BLAS threads=1. Preserve source data by reference.

Before formal scoring, require pilot precision pass, twice the conservatively projected formal cost <=120 min, projected peak memory <=4 GiB and new storage <=2.5 GiB. Projection must charge all 33,971 cases, all arms, Gaussian geodesic transforms, complete controls, region checks and I/O; use the larger of p95-based and component-based estimates with explicit cold-start cost. Audit cost must fit its own cap. Report stage counters at <=60-second intervals and save bounded atomic checkpoints.

The existing E8 run took approximately 78 minutes including its audit/corrections; this is historical context only. The new Gaussian-minus-point precision and geographic integration cost are **not benchmarked**, so no speedup or final-runtime promise is made. If the pilot cannot establish the required accuracy within budget, stop and report before a full run. Do not force a model change to satisfy the clock.

## 10. Deliverables and stopping boundary

After a separately approved, completed and verified experiment, deliver:

- English technical report and Chinese review HTML with a three-arm table, both paired contrasts and separate engineering/scientific conclusions.
- ES, H90 and mean-area comparison plots with intervals; per-ID effects; land/outside mass, parameter conditioning and CI fallback diagnostics.
- Six outcome-independent example keys from the pinned E8/E7 release, verified before scoring: identical extents/colour scales, exact start/truth, continuous 90% boundary and 0.5° display probabilities for A/C/G. Do not pick successful examples after scoring.
- Frozen contract/approval, source/role/repair hashes, parameters, prediction packets, complete metric tables, resource ledger, independent audit and final file inventory.

Freeze distributions before new outer scoring; do not access final-test data. A new donor rule, displacement borrowing, covariance regulariser, neural network, multiple Gaussian components, CI addition to G, environmental variable, target/score/region change or iteration requires a separate proposal. No automatic default replacement or further stage expansion follows E1.

**For this review:** approve or revise the local same-endpoint Gaussian construction, analytic full-covariance fit, unchanged A/C controls, ES/region definitions, support/rank stopping rules, numerical plan and proposed budget. This document creates no model code or experimental result.
