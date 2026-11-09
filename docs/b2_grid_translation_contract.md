# B2 Grid Translation G1 — Engineering contract

## Material Passport

- Date: 7 November 2026, Australia/Sydney. Version: v1.
- Mode: experiment design; academic-research-suite / experiment-agent / plan.
- Status: **REVIEW_REQUIRED — no implementation or experiment is authorized by this document.**
- Scope: one additional baseline robustness comparison within the Markov research programme; not a new feature-selection round or Step 5 implementation.
- Verification: existing contracts, input receipts, geometry policy and B2 source inspected. No new offsets, transition counts, support statistics, forecasts or scores have been computed.
- This delivery adds this contract and a planning-review receipt only. The research-stage ledger and existing scientific artifacts are not revised.

## 审阅摘要

比较原始 1° B2、100 个预先随机平移的 1° B2，以及这 100 个预测的等权平均。每次同时重新划分起点和终点；真实坐标不动。公共评分网格固定为原来的 1° 网格。训练配对等权，评估仍为每条 drifter 内各时刻等权、再对 drifter 等权。

本合同提出并等待批准的具体定义：终点格内按“研究域内海域的实际面积”均匀分配；几何重映射守恒，不创造退出；无支撑不回退、不删样本，完整支撑检查失败时暂停正式评分；90% 区域按公共格概率排序并保留截止并列格，面积为区域在研究域内的海域面积。本轮 H90 是实际落点的**公共 cell 命中率**，不是上一轮连续椭圆的精确坐标命中率。

资源上限拟定为试跑 10 分钟、正式计算 60 分钟、独立复核 20 分钟、报告 10 分钟，累计 100 分钟；进程树内存 8 GiB、新增存储 5 GiB。以下所有规则需随合同一起确认，不能因结果不理想而修改。

## 1. Research question, estimand and scope

**Question:** For an already-qualified release in R, does averaging seven-day empirical forecasts across randomly translated spatial partitions improve prediction over the original fixed-grid B2, while preserving actual H90 and geographic search area?

The outcome is the existing stopped seven-day destination: a geographic endpoint in D, or absorbing observed exit E. This is a direct horizon kernel, not daily propagation or a matrix-power experiment. The query is an arbitrary qualified hourly departure, not first entry into a cell.

Separate the two questions:

1. **Sensitivity:** How much do forecasts and performance vary with grid placement?
2. **Predictive improvement:** Does the prespecified equal mixture outperform the original B2 on the same evaluation cases?

No improvement is assumed. A successful sensitivity analysis does not establish forecast improvement, and successful engineering does not require a positive scientific result.

Any improvement supports the complete specified estimator: changed source grouping, destination histogram/remapping and equal averaging. This design does not separately identify their contributions or establish that a smoother map is more physically accurate.

**Included:** original B2; exactly 100 translated B2 kernels; their equal-weight probability mixture; common-space Brier/H90/area and uncertainty; geometry/support/numerical diagnostics.

**Excluded:** H3 or rotations; different cell sizes; origin-only translation as an additional arm; seasons, velocity or other features; B1, Fixed or Adaptive blends; CI/error kernels; ExactPoint/B2Point as new comparison arms; 100-km or k=8,000 donor restrictions; drifter-equal training; path translation/checking; iterative transport; learned mixture weights; choosing the best shift; ES or a combined loss; new source data or final-test access.

B2 uses **all eligible fitting pairs in the query's current source cell**. The exact-position estimator's distance/candidate limits do not belong to this baseline. Physical R/D eligibility is unchanged when the grid moves.

## 2. Evidence and deliberate adaptations

O'Malley et al., *Estimating the travel time and the most likely path from Lagrangian drifters*, DOI [10.1175/JTECH-D-20-0134.1](https://doi.org/10.1175/JTECH-D-20-0134.1), §4.1 describes translating a two-dimensional square partition and uses whole-coordinate rotations for its global H3 application. Its main comparison reconstructs matrices for 100 rotations and aggregates travel-time results for fixed geographical tasks. It does not establish held-out seven-day Brier improvement. [Paper](https://arxiv.org/html/2002.07774), [figure code](https://github.com/MikeOMa/MLTravelTimesFigures/blob/master/FiguresForPaper.ipynb).

Our regional square-grid translations retain the re-partition/re-estimate principle. Averaging **destination probabilities**, rather than travel times, is our explicitly declared adaptation. The paper's five-day lag, global sample, H3 resolution and graph-path objective are not imported.

Brolly, DOI [10.1029/2023MS003718](https://doi.org/10.1029/2023MS003718), equation 18 represents a cell-transition probability as a constant density within its destination cell. [Paper](https://arxiv.org/html/2303.11480). Our uniformity is with respect to **WGS84 surface area over the wet, in-domain part of a cell**. Brolly's equation uses area in its chosen coordinate units; the wet-domain restriction and surface-area measure here are additional, explicit choices, not a verbatim replication.

Do not copy repository defaults blindly: the inspected `MakeRotations.py` uses 30/resolution 4, whereas the main figure notebook loads 100/resolution 3. Do not import the author's graph-node deletion routines: they are not a probability-preserving policy for this forecast task.

## 3. Immutable inputs and data roles

Use cleaned release `per-drifter-cleaned-20261017-v7` and the sealed E7 coordinate/role artifacts. No retracing, requalification, endpoint interpolation or revised split is authorized.

| Input | Identity / SHA256 |
|---|---|
| English Data Contract | `docs/contract/data_contract_v1.0.xlsx`; `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446` |
| Dataset manifest | `configs/dataset_manifest.json`; `c71a7ac3d0230b7489bcfc417d4caceb26ffc1230644a11300a642d7812e041e` |
| Source run | `exact_origin_s4_e7_primary_20261105T074326_829211Z` |
| `training_coordinates.parquet` | `8638434fb651d10737a2827350d5ff98a3a76a5f3427778748c17a3ddb68715d` |
| `query_coordinates.parquet` | `0b480d728e008444c493a228ebecb2505da21185aa70d0f07e8513fd6107fea5` |
| `roles.parquet` | `78da3c85f77e29b303d7137320c33a94580f4822712faace9a7f0a03ffc7fdac` |
| `outer_roster.parquet` | `8bd253f4d084744be5e19a95f5326a1315bf03b5362bdf0d5b732d9b8be4a3d4` |
| `outer_targets.parquet` — sealed until forecast freeze | `ac4d6dde254a4b785862e8d1de168e9c06690f1798e3463e14c956731627d342` |
| release R, via `configs/assets.json` | `2ce35bd03e941e57f1c98130dbf069419503624626c36f4739e9c8dd94d0ad9a` |
| transport D, via `configs/assets.json` | `57fcad5061e869e47f27b3a6f11041bd3e655ffd9dbab513e30473824b395da8` |
| GSHHG high-resolution land WKB, via `configs/assets.json` | `4f62ccdb9084d7f6e7f5ddc92b92c7da96f07665f77db0500f364a1678fe63e0` |
| Current `state_index`, via `configs/assets.json` | `5d7934a19221618b4102e8be40cb294774506d60856f85f606ad2178495ac24f` |

Coordinate files are under `results/runs/<source run>/`; receipt hashes above are planning references, to be reverified after approval. Freeze the state-index and grid-water-policy assets through the manifest/receipt before use. Do not substitute a moving deliverable symlink for a run identity.

Use the manifest's current `state_index`, not the separately named older `baseline_state_index`, for existing cell codes and boundary conventions. Recompute the explicitly approved clipped wet areas into new artifacts; do not replace any stored historical area columns. Predictor input column allowlists contain only fitting records, query source keys/starts and role metadata. Do not load historical outer scores or outer labels from a roster merely because the file is already available. Do not reuse the E8 input loader, which also joins error overlays irrelevant to this experiment.

| Role | Fit period / pairs / IDs | Held-out period / pairs / IDs | Use |
|---|---|---|---|
| C_T0 | 2001–2013 / 170,978 / 234 | 2014–2016 / 41,761 / 50 | Fixed numerical-pilot cases only |
| C_T1 | 2001–2016 / 209,934 / 280 | 2017–2019 / 44,612 / 58 | Fixed numerical-pilot cases only |
| C_outer | 2001–2019 / 265,393 / 338 | 2020–2022 / 33,971 / 45 | Sole main comparison |

Preserve ID reservations originally made across both horizons, even though this experiment uses seven days only. A fitting label whose required observation interval reaches the fitting cutoff is excluded. Whole IDs cannot occur in both roles. Seven days means exactly 604,800 seconds; departure year is the year of the qualified observation in R. Available 2022 data are part-year.

No inner model selection: the 100 shifts, weights and resolution are fixed. Pilot scores may check arithmetic but must not select shifts or change the mixture. Each role uses only its fitting endpoints to construct forecasts.

Keep `(id, origin_source_obs, horizon_days)` and endpoint provenance. Protect all 517 final-test IDs. Outer endpoint coordinates and labels are released to the scorer only after forecasts, support, numerical settings, regions and example keys are frozen. Reading previously published reports does not make this a new blinded validation: 2020–2022 is repeatedly inspected development evidence.

## 4. Grid generator and the 102 forecast objects

Use the original 1° longitude/latitude partition with origin (-180°, -90°) as G0. Retain the existing half-open convention and longitude normalization. Zero offset must invoke/reproduce the frozen `cells(..., res=1)` mapping exactly, including floating-point edge fixtures; do not snap recorded coordinates.

After approval, generate a `(100,2)` float64 array using **NumPy Generator(PCG64(20261107)).random((100,2))**, interpreted as degrees. Row m defines delta_m=(delta_lon, delta_lat), each in [0,1). Persist full-precision values, their hexadecimal representations, generator/version and file hash before fitting. Keep any coincident draws; do not select/resample shifts by support or results.

For shift m, longitude edges are -180+delta_lon+i and latitude edges -90+delta_lat+j, with longitude periodic. For the present mid-latitude region, the shifted source-cell indices are:

`ix=floor(((lon+180-delta_lon) mod 360)/1)` and `iy=floor((lat+90-delta_lat)/1)`.

Apply the **same shift to both endpoints of every non-exit training pair**, and to every query start. Physical coordinates, coastline and R/D stay fixed. E is never assigned a coordinate. Coordinate values are not rounded and no half-cell shift replaces a random draw.

| Object | Definition | Inferential role |
|---|---|---|
| B2Original | G0, original equal-pair empirical counts | Sole baseline |
| B2Shift001…100 | Each fixed translated partition, separately fitted | Placement sensitivity; all 100 reported |
| B2GridMean100 | Equal mean of the 100 mapped probability forecasts | Sole primary candidate |

There are 101 fitted count tables and 102 forecast objects, not 102 independently trained models. The original B2 is **not** a 101st mixture component.

## 5. Counts, support and equal-pair fitting

Let Y_r be a geographic stopped endpoint or E, and g_m the grid index. For a supported source row i:

\[
N^{(m)}_{ij}=\sum_{r\in T}\mathbf1\{g_m(x_r)=i,\ g_m(Y_r)=j\},\qquad
P^{(m)}_{ij}=N^{(m)}_{ij}/N^{(m)}_i.
\]

For E, replace the second indicator with `Y_r=E`. The denominator includes **all** eligible pairs in that source row, including E. Each hourly pair contributes one vote; repeated real pairs keep their multiplicity. No deduplication, pseudocount, support shrinkage or distance weighting is permitted.

Use actual-point R eligibility, not whether a shifted cell intersects R. A shifted cell can extend outside R, but this does not import observations from outside the frozen training pool. Export integer counts, row totals, unique training-ID counts, largest-ID vote share and destination counts for every needed source row.

### Zero-support rule and mandatory pre-scoring gate

- `N_i=0`: distribution undefined; store status `unsupported_origin`, geographic/E probabilities absent and bookkeeping U=1. U is not a physical destination and receives no invented truth label.
- `N_i>0`: retain the empirical row even if it has only one pair/ID. No minimum-ID backoff.
- A primary query is eligible for the complete mixture only if all 100 shifted rows are defined. The fixed 1/100 weights may **not** be renormalized over successful components.
- No B2/B1 fallback, self-loop, uniform prior, redraw, neighbourhood expansion or deletion of unsupported cases is authorized.
- Before outer outcomes are opened, check G0 and **all 100 shifts on all 33,971 starts**. If any row is unsupported, preserve and report the complete support table and stop formal prediction/scoring for review. Do not replace the main result with an easier common-support subset. A support failure is a feasibility finding, not a worse Brier score or a proof of no grid benefit.

This conservative gate retains the approved historical distinction between undefined rows and standard Brier. It is an explicit proposal for approval, not a claim that every shifted row is already supported.

## 6. Uniform-within-cell hypothesis, land and domain boundaries

Define the fixed wet domain W = D minus the frozen GSHHG L1 land mask. Use WGS84 surface-area measure mu in km². All disconnected wet components are retained; common cell membership is not evidence that those components are physically connected.

For destination cell C_j^(m), let A_j^(m)=C_j^(m) intersect W. Given geographic destination state j, assume uniform probability **per unit wet surface area**:

\[
F_m(B\mid x)=\sum_j P^{(m)}_{g_m(x),j}
\frac{\mu(B\cap A_j^{(m)})}{\mu(A_j^{(m)})}
\quad\text{for geographic sets }B,
\qquad F_m(\{E\}\mid x)=P^{(m)}_{g_m(x),E}.
\]

This is a histogram representation of the matrix, not a learned continuous-position estimator, Gaussian, CI or endpoint-error model. Uniformity is an added scientific assumption. It can assign probability to unobserved wet locations within a counted destination cell.

**Mass policy:** define the within-cell distribution on A_j from the outset. Preserve the entire empirical probability P_ij of that cell. Do not first spread over land and then discard mass, redistribute between destination cells, or renormalize the whole forecast. Wet fragments outside D get no geographic probability; this geometry operation does not create an exit event.

**Exit policy:** E means the existing observed first exit from D, including exit followed by re-entry. It is absorbing in the outcome definition and unchanged by grid translation. A geographical cell touching/straddling D, land-mask conflict, missing support, or a numerical failure is not E. Missing follow-up remains governed by the existing qualification.

**Geometry conflicts:** never delete, snap or relabel a qualified source observation because it falls on/near the coastline mask. Flag such records and preserve their original source labels. A non-exit observation must reproduce its sealed D/state provenance. If a positively counted destination cell has zero wet in-domain area, or an authoritative label conflicts with D membership, stop and report; do not invent an epsilon area or alter the mask. Boundary-only states remain in indexes with zero probability unless supported, in which case the same integrity gate applies.

The E7/E8 record reports zero observed exits in these roles. Reconcile this during execution at the proper outcome gate; do not infer that future physical exits are impossible. Synthetic E fixtures are still mandatory.

**Explicit differences from earlier reports:** E7 counted full-cell wet area, including any part outside D; this contract measures wet area **clipped to D**. E8/E9 used continuous ellipses and retained CI tails; neither representation applies here. These changes are offered for approval for this experiment only and do not overwrite historical results.

## 7. Common scoring space and conservative remapping

The primary scoring partition is the **original fixed 1° grid G0**, not each candidate's moving grid. Let Q_k be its geographic cells intersecting D, including the existing boundary-state conventions. Include all such fixed states, even those unobserved in training, plus E. No target-dependent state discovery.

For each shifted destination cell, define the sparse overlap matrix:

\[
M^{(m)}_{jk}=\frac{\mu(C_j^{(m)}\cap Q_k\cap W)}{\mu(C_j^{(m)}\cap W)},\qquad
q^{(m)}_k(x)=\sum_j P^{(m)}_{g_m(x),j}M^{(m)}_{jk},\qquad
q^{(m)}_E=P^{(m)}_{g_m(x),E}.
\]

For every positive-area row, M is nonnegative and sums to one. The identity-grid overlap is identity on positive-area states. Consequently B2Original's common-grid probabilities **must reproduce ordinary B2 exactly**; its within-cell hypothesis does not change its own 1° Brier predictions.

Do not use cell centres, equal shares among overlap cells, actual endpoint rebinning, or angular-area fractions as substitutes. A common-grid cell can have positive predicted probability despite no training endpoint in it, because a shifted histogram cell overlaps it; disclose this mechanism.

After remapping, the candidate is

\[
\bar q_k(x)=\frac1{100}\sum_{m=1}^{100}q^{(m)}_k(x),\qquad
\bar q_E(x)=\frac1{100}\sum_{m=1}^{100}q^{(m)}_E(x).
\]

Average probabilities, **not matrix indices, Brier scores, regions or hit indicators**. Independently rescore the mixture. All weights are exactly 1/100, regardless of sample counts or validation performance.

The scoring partition is anchored to the original B2, so inference concerns prediction of these fixed geographical events. It is not grid-free evidence or proof of optimal fine-scale density. Do not change scoring resolution/alignment after results. Maps use this same public 1° partition, with shifted training-grid boundaries overlaid for explanation.

## 8. Brier, nominal 90% regions and weights

For observed common-grid outcome y, including E:

\[
B(q,y)=\sum_{k\in\mathcal Q\cup\{E\}}(q_k-\mathbf1\{k=y\})^2
=1-2q_y+\sum_k q_k^2.
\]

Use standard unnormalised multiclass Brier. Lower is better. No division by state count, distance weighting, U penalty, square root, or fitted loss coefficient. Zero probability at the true destination remains an ordinary finite Brier case.

**Region definition:** sort positive common-state probabilities descending; take the smallest prefix whose mass is at least 0.90, then include every positive cutoff tie (probability tolerance 1e-12). Use stable state-ID order for storage, not to exclude tied states. Use accurately summed cumulative probabilities and independently check the 0.90 boundary; do not rely on an unverified floating `searchsorted` decision.

- H90 = 1 if the recorded outcome's common state is in that set; E counts as a hit only if E is selected.
- Geographic region = union of selected Q_k inside D. Main area = sum mu(Q_k intersect W) for selected geographic cells. E contributes no polygon or km².
- Report attained total mass, geographic mass, E mass/membership, number of geographic cells, and cutoff-tie overshoot. Do not condition on staying in D. The visible geographic polygon alone need not carry 90% if E is included.
- H90 is a **cell-event hit**, not an exact-coordinate wet-polygon/ellipse test. Coastal mask flags are reported separately; noisy recorded coordinates are not silently discarded.
- This probability-ranked cell region is not claimed to be the minimum-area region, particularly where cells differ in wet area. Do not switch to density ranking or remove small-probability cells to obtain a favourable area.
- Apply the same region construction to each individual shift **after remapping** and to the mixture after averaging. Do not average the 100 regions.

For D_v=45 held-out drifters with n_d eligible times, use w_dt=1/(D_v*n_d). Each ID contributes one total evaluation vote. There is no additional equal-origin-cell/season weighting and no change to equal-pair fitting. Keep all 33,971 cases. Report mean Brier, H90, mean wet area, weighted area median/10th/90th percentiles, zero-truth probability rate and support diagnostics.

Historical scores using different roles, cell weights, ES or ellipse/full-cell areas are context only. Recompute the baseline with this roster and weighting. Do not compare numerical Brier levels to ES.

## 9. Predeclared inference and decision criteria

**Sole primary contrast:** B2GridMean100 minus B2Original. Let Delta_B and Delta_H be the paired drifter-equal mean differences; R_A is the ratio of their drifter-equal mean areas.

Compute per-ID metric means first. Use 10,000 paired whole-ID bootstrap resamples with replacement, PCG64 seed **20261108**, common draws across metrics. Report two-sided percentile 95% intervals for Delta_B, Delta_H and R_A. The forecasts, shifts and training data remain fixed in this bootstrap. This estimates evaluation-ID uncertainty; it is not the author's training-trajectory bootstrap and does not capture all training/ocean-forcing uncertainty.

| Requirement for quality-preserving predictive improvement | Criterion |
|---|---|
| Engineering validity | Complete full roster/support; successful provenance, remapping, probability and independent checks |
| Brier evidence | Upper 95% bound of Delta_B < 0 |
| Practical size | Relative mean Brier reduction >= 0.1% of B2Original; if baseline Brier is zero, no relative-improvement pass |
| Observed H90 | Delta_H >= 0, resolved beyond numerical ambiguity |
| Observed area | R_A <= 1, resolved beyond numerical ambiguity |
| Uncertainty guardrails | Lower 95% Delta_H bound >= -0.01; upper 95% R_A bound <= 1.02 |
| Numerical separation | Error bound on Brier contrast <= one tenth of the 0.1% threshold; effect direction must exceed numerical error |

The 1 percentage-point/2% guardrails retain the recent E8/E9 decision scale. They **do not permit an observed hit decrease or area increase to be called no degradation**. No pass through rounding. Exact identity counts as unchanged.

For all 100 shifts report their individual metric values, differences from original, full spread/quantiles and where original lies within that distribution. These are descriptive: no 100 separate unadjusted significance claims, winning-shift selection or additional independent-data claims.

Prespecified diagnostics: independent-ID and pair support; largest-ID contribution; original-grid edge distance; year; zero-truth probability; leave-one-ID-out primary effects; and prefix mixtures at 25, 50 and 100 shifts. Prefix comparisons measure finite-shift stability and do not select a component count. Geometry/prediction convergence uses no validation outcomes. A nonzero prefix difference does not authorize more shifts.

Interpretation:

- All criteria pass: supported improvement of this particular 100-shift predictor on development data; no automatic baseline replacement.
- Lower Brier but lower H90/larger area: improvement with a trade-off, not quality-preserving success.
- Placement variation without primary improvement: evidence of grid sensitivity, not an effective remedy.
- No meaningful primary gain: retain original B2 and close this registered comparison; no automatic shape/size/weight search.
- Support, geometry, precision or budget gate fails: incomplete/inconclusive, with the blocking evidence retained; not a negative forecast-quality result.

## 10. Numerical geometry, invariants and independent audit

Use frozen coastline topology; no new land download, smoothing, simplification, buffer-based repair or ocean connectivity filter. Clip/cache local land tiles before repeated cell overlays; never intersect the full global coastline separately for every pair/query.

The normative area is WGS84 surface area. Construct overlap polygons in original coordinates, retaining native coastline vertices. Numerically integrate via WGS84 geodesic polygon area with sufficient edge subdivision to represent constant-latitude cell boundaries, rather than treating a long parallel as one geodesic chord. Initial maximum angular edge interval 0.01°, verify at 0.005°, refine only numerical approximation to 0.0025° if needed. Hole orientation/area and disconnected components must be independently checked. No scientific mask or grid changes are allowed during refinement.

For numerical conservation, compute a shifted cell's denominator as the accurately summed areas of its disjoint intersections with the complete common grid. Independently compare this with direct wet-cell area. This is an integration identity, not permission to drop a failed piece and renormalize what remains. Zero-area touching intersections contribute zero; no deletion of positive slivers by an arbitrary cutoff.

Required gates:

- Counts, roles and source-key mappings exact; zero-offset source/destination counts match independently tabulated B2.
- Remapping and forecast rows finite/nonnegative; mass and E preservation within 1e-12. Structural zeros are retained.
- Refined-versus-working common probability vectors have L1 error <=1e-6 for every distinct used forecast row and mixture signature, and satisfy the stricter contrast gate in section 9. Since Brier error is bounded by 4 times probability L1 error, record conservative bounds rather than ignoring geometry uncertainty.
- Direct versus partition-summed positive wet-cell areas agree within relative 1e-6; zero/very small areas get explicit absolute-error diagnostics and no floor. Unresolved discrepancies stop the run.
- Across numerical resolutions, total evaluation weight of cases whose 90% set changes is <=1e-4 **per reported arm**, bounding hit uncertainty by 0.01 percentage point without reading truth. Weighted mean area changes <=0.01%. Effects smaller than remaining bounds are inconclusive. Refine within the cap or stop; do not change tie policy to force agreement.
- Confirm 90% attained mass, all cutoff ties, E handling and rank order independently. Numerical refinement may not change samples, physical geometry or mixture weights.

After approval, independent verification means separate arithmetic/code paths, not merely rerunning the same helper or claiming a separate human reviewer. At minimum:

1. Reconstruct all 101 integer count tables from the sealed pair records with an alternative aggregation path; verify complete-role weights and input hashes.
2. Independently check geometry on all boundary/land-conflict fixtures and at least 128 preselected real shifted cells spanning interior/coastal/domain-edge/small-wet-area cases; selection uses geometry/training only.
3. Independently replay direct donor counting and remapping for 128 fixed outer starts and 10 shifts selected before outcomes (indices 1,12,23,34,45,56,67,78,89,100), plus G0. Audit the complete 100-component sum from stored mapped rows.
4. Recompute Brier, H90, area, weights and primary uncertainty from sealed predictions for **all** outer cases. Verify mixture Brier is not the average of component Briers; Jensen's inequality is a useful additional consistency check on the common probability vectors.
5. Test artificial zero-support, E-only, exit/re-entry, coastal, zero-wet-area, exact-grid-edge, positive-sliver, overlapping/disconnected-water, identical-component and 0.90-tie fixtures. Validate no public target access can change shifts, forecasts or regions.

The 128 outer audit keys are obtained after sorting the frozen roster by the source key and taking indices floor(j*(33971-1)/127), j=0…127. No outcome-selected maps or audit cases.

## 11. Architecture and resource-gated execution proposal

No files in this section exist as a result of contract drafting. After explicit approval, add isolated components under `src/data3001/modelling/baselines/`: `b2_grid_translation_inputs.py`, `b2_grid_translation.py`, `b2_grid_translation_geometry.py`, `b2_grid_translation_pipeline.py`, `b2_grid_translation_audit.py`, `b2_grid_translation_report.py`, and a small entry point. Keep config/test files separately named for this experiment. Reuse verified low-level input/Brier/provenance helpers, not legacy orchestration or exact-neighbour settings.

For a fitting role, each grid source row has one mapped forecast shared by all query starts in that row. Cache integer count tables, wet-overlap matrices and mapped source rows; do not redo geometry per query or per training pair. Group identical 100-source-row signatures when constructing mixtures. Stream individual-grid scoring and use bounded query batches for mixtures. Do not store a dense 102 x 33,971 x global-state tensor.

Outer scale, derived from frozen counts: 26,804,693 pair/grid classifications across 101 fits and 3,465,042 case/forecast metric records across 102 objects. These are not billions of path or pairwise-distance calculations. Main uncertainty is coastline overlay and numeric verification, not Brier arithmetic. **No measured runtime estimate exists yet.** A planning estimate of tens of minutes is provisional and cannot bypass the pilot.

| Phase | Hard cumulative allocation within that phase | Required content |
|---|---:|---|
| Preflight, synthetic checks and pilot | 10 min | Input/role verification; generate/freeze all shifts; full outer-training count/support pass for all 100 shifts using all query starts; numerical pilot described below |
| Formal predictions/scoring | 60 min | All 33,971 cases, original + 100 shifts + mean, no reduced sample or component count |
| Independent audit | 20 min | Full count/score audit plus fixed geometry/donor cross-checks and uncertainty |
| Report and visualization | 10 min | Complete tables, figures, HTML and final receipt |
| **Total** | **100 min** | Sum of wall time across all attempts; overlapping parallel work counted once; child CPU time reported separately |

Hard limits: **8 GiB aggregate process-tree RSS; 5 GiB incremental disk** including temporary/cache/audit/report files. Existing immutable source files referenced without copying do not count as new storage. Retain at least 1 GiB storage headroom in forecasts (project <=4 GiB); no waiver of the 5 GiB hard cap. Use one process initially; at most two geometry processes with private native objects and BLAS threads limited to one. Do not share mutable GEOS objects between threads/processes.

Pilot numerical sample: 64 deterministic evenly spaced held-out keys from each inner role (128 total), chosen by sorted key before labels; use each role's **complete fitting pool**, G0 plus the first eight approved shifts. Add the geometry fixtures in section 10. No reduced donor pool, new scientific grid, or outcome-driven sample choice. The all-100 outer support scan is input-only and does not open outer targets.

Before formal work, publish a pilot receipt with actual phase time, peak aggregate RSS, geometry throughput, distinct forecast/signature counts, support results, precision bounds and conservative full cost/storage projections. Use at least a 1.5x factor on measured extrapolated geometry cost, explicitly accounting for uncached coastal work, refinement, audits and mixture processing. Proceed only if the full-roster/all-shift support gate and all pilot-applicable scientific/numerical checks pass, projected formal time <=48 minutes (headroom within 60), projected incremental storage <=4 GiB, and total remaining allocations suffice. The complete-forecast numerical gates are checked during formal prediction generation, before outer outcomes are unsealed; passing a pilot does not waive them. Otherwise stop for review; do not quietly increase the budget or reduce work.

Check resource/progress counters at intervals <=60 seconds and between bounded work chunks. Persist atomic, restartable checkpoints. At a cap or integrity failure, stop scheduling new work, save the diagnostic and report. No automatic retry after an unexplained failure; retries need authorization and count against the same cumulative budget.

A future execution approval may authorize pilot then conditional formal execution under these gates. **The current request authorizes drafting only.**

## 12. Deliverables, audit and stopping boundary

Use a new timestamped run `results/runs/b2_grid_translation_<UTC>/` and matching provenance directory. Deliver only after verification to `results/deliverables/b2_grid_translation/`:

- `review.html` and `REPORT.md`, distinguishing engineering completion, grid sensitivity and predictive benefit;
- frozen contract/approval/source hashes; exact shift table and seed receipt; integer counts, row supports, remap cache/digests and replayable probability packets;
- full 102-object summary, per-ID/per-case metrics, primary paired intervals, all 100 shift diagnostics, geometry/exit/mass/support tables and resource ledger;
- baseline/mixture comparison plots; distribution of the 100 individual Brier/H90/area results with baseline and mixture marked; 25/50/100 convergence diagnostics;
- six fixed same-start maps, shared extent/colour scale: original, shift 1, shift 50 and the mean; original/shifted grid overlays, actual start/truth, common 90% boundary, land and D boundary. Reuse E7 example keys only after identity checks; do not choose better-looking examples after scoring;
- independent audit and final file inventory. No failed-run or unverified report is published as a completed experiment.

Freeze all definitions before outer scoring. A new shape, resolution, component count, fallback, land/domain policy, error construction, weighting, tolerance beyond the registered numerical refinement, or acceptance rule requires a revised contract and explicit approval. A negative or inconclusive result closes this registered comparison without launching another search. Research-stage ledger additions and baseline replacement remain separate user decisions.

**Approval requested:** the 100-shift joint source/destination design; wet in-domain surface-area uniformity; original 1° common scoring grid; no-support stop rule; probability-level 1/100 mixture; cell-based 90% wet-area evaluation; numerical/quality thresholds; and the proposed resource-gated execution budget. No development, model fitting, pilot or scoring has begun.
