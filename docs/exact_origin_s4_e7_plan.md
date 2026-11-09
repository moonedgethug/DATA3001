# Step 4 E7 | Exact-coordinate empirical Markov transition contract

## Material Passport

- Origin Skill / Mode: academic-research-suite, experiment-agent / plan
- Date: 5 November 2026, Australia/Sydney
- Version: engineering contract v2.1, user-approved with a 100-km donor cap
- Verification Status: design only; existing source schemas, roles, geometry code and baseline artifacts inspected
- Execution status: APPROVED for development, pilot and conditional primary/replay execution. Approval does not imply a completed experiment.

The user approved this contract and execution, replacing the proposed 150-km cap with 100 km; all other scientific choices remain unchanged. This contract supersedes the [unexecuted v1 proposal](exact_origin_s4_e7_plan_v1_superseded.md). E5 and E6 remain the separately named speed and wind proposals. The stage ledger is unchanged pending approval of finalized content.

## 1. Objective and agreed boundaries

For a qualified drifter at its recorded departure longitude and latitude, estimate its stopped destination distribution seven days later. Compare a local empirical Markov transition estimator using exact coordinates with the existing annual B2. The research question is whether this estimator improves forecast quality relative to the existing cell-conditioned baseline.

| Item | Contract definition |
|---|---|
| State supplied to the new predictor | Exact departure longitude and latitude; seven-day horizon |
| Learning records | Exact historical start and seven-day endpoint coordinates, or the established absorbing exit E |
| Estimator | Nearby historical starts selected by distance; all selected observation pairs contribute equally |
| Final map | Probabilities aggregated into aligned 0.5-degree cells and a nominal 90% probability region |
| Primary control | Annual B2, retained as a separate forecast |
| Primary comparison | Matched Brier, H90 and K90 on the original 1-degree output grid |
| Fine-output comparison | Both forecasts re-tabulated at 0.5 degrees from their actual historical endpoint records |

No Gaussian, MDN, B1/B2 fusion, beta shrinkage, distance-dependent vote strength, error-envelope spreading, heading, speed or environmental predictor enters this round. Initial cell membership does not select or restrict donors for the new model. Existing cell labels remain for baseline construction, evaluation strata and common scoring.

There is no endpoint or path translation: a donor's observed endpoint stays at its original geographic location. A nearby donor is evidence about a possible endpoint, not a trajectory replayed from the query. No new hourly route simulation is needed. Existing first-exit labels and qualification remain authoritative.

This is a continuous-input, nonparametric empirical transition **measure**, not a smooth probability density. Its mass is on observed endpoints and E. The displayed region is the union of selected 0.5-degree cells, not a grid-free confidence contour. It can assign mass to endpoints absent from the query's old B2 row by admitting nearby starts, but cannot invent endpoints absent from all selected historical observations.

Markov conditioning is a modelling assumption, not something demonstrated by one successful seven-day backtest. A positive result would support this exact-coordinate neighbourhood estimator. It would not isolate coordinate precision from the accompanying change in donor selection, or prove that every continuous-state model is better. Step 5 can subsequently compare estimators; this round fixes one estimator family.

## 2. Data, roles and information timing

Use cleaned release `per-drifter-cleaned-20261017-v7`, the pooled development scenario, qualified exact seven-day pairs, frozen release region R, transport domain D and absorbing first exit E. Years classify departure times inside R; 2022 is only the available part-year. Keep the current whole-ID temporal split and cross-boundary label exclusions.

| Role | Fitting departures | Held-out departures | Fitting pairs / IDs | Held-out pairs / IDs |
|---|---|---|---:|---:|
| Inner 1 | 2001–2013 | 2014–2016 | 170,978 / 234 | 41,761 / 50 |
| Inner 2 | 2001–2016 | 2017–2019 | 209,934 / 280 | 44,612 / 58 |
| Outer development validation | 2001–2019 | 2020–2022 | 265,393 / 338 | 33,971 / 45 |

Reproduce the exact [E4 role definition](departure_direction_s4_e4_plan.md), including validation-ID reservations across both historical horizons before retaining only seven-day cases. This avoids quietly expanding training because E7 has only one horizon. Every inner role lies inside eligible outer training, removes its own held-out ID union, and excludes labels whose required observation interval reaches its fitting cutoff. Whole IDs are disjoint between fit and holdout in each split.

Pin resolved run paths and checksums for the E4 roster and metrics, the E2 role receipts, the sealed `markov_input_20261025T095949_830292Z/release_labels` and the manifest-owned tracks/qualification. Do not use a moving deliverable link as a run identifier. The 2020–2022 years have been inspected in earlier development; this is not a fresh final test. The canonical final-test pool remains inaccessible.

Extract starts by `(id, origin_source_obs)` and non-exit endpoints by `(id, endpoint_source_obs)`. Verify the source timestamp, exact 604,800-second lag, stored origin/destination cells and existing qualification. Use `lon_normalized` and `lat` at full stored precision. Reject duplicate keys, failed joins/hashes, inconsistent times/cells or invalid declared-qualified coordinates as integrity failures. No rounding, snapping, additional interpolation, changed exclusions or missing-case deletion is permitted.

For a donor labelled E, retain E and its first-exit provenance; do not substitute its later position or invent an exit coordinate. This preserves stopped-domain semantics and possible re-entry handling.

The feature interface receives only held-out starts. Historical fitting endpoints are training labels. Outer endpoints are exposed to scoring only after all selected-model forecasts, weights, support flags and region masks have been frozen. Opening a track for source-key extraction does not authorize future rows as predictor inputs.

`err_lon` and `err_lat` describe uncertainty of recorded positions, not future transport spread. Preserve their source/QC status; do not use them as input features, donor weights, smoothing widths or forecast-region extents. Missing uncertainty alone creates no new exclusion. See the [local data dictionary](data_dictionary.md) and [NOAA variable definitions](https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html).

## 3. ExactPositionEmpirical estimator

Let x be the exact query start. Each fitting record r contains its exact start x_r and stopped endpoint Y_r, where Y_r is either a geographic coordinate or E. Candidate donors are all eligible seven-day fitting pairs whose actual starts lie in R. Starts outside R, outside D, from held-out IDs, or failing the existing qualification are excluded by the frozen input contract.

Use WGS84 shortest geodesic distance between x and x_r. This is a statistical proximity measure, not a claim of an unobstructed ocean route. No new land-barrier neighbour filter is introduced in this first round; coastal examples and donor distances will expose this limitation.

Approved parameters:

| Parameter | Approved setting | Purpose |
|---|---|---|
| Neighbour counts k | **500, 2,000, 8,000** observation pairs | Three predeclared local sample sizes; select one shared k for seven days |
| Maximum donor distance | **100,000 metres**, fixed | Prevent a sparse location from borrowing arbitrarily far away |
| Voting | One equal vote per selected pair | No distance weights or model fusion |
| Geodesic threshold/tie tolerance | 1e-6 metre | Deterministic numerical handling, unrelated to measurement uncertainty |

These settings are design choices, not inferred ocean correlation scales. The k values span a sixteenfold sample-size range without a broad tuning search. The user-selected 100-km cap limits reference information to nearby starts; it is not learned from outer outcomes.

For each x, retain fitting starts within the distance cap. If there are at least k, find their kth smallest distance and include all records at or within that distance, including ties. If fewer than k are available, use all within the cap. Never break a distance tie using endpoint labels. Keep repeated observations and their multiplicities; k counts pairs, not independent drifters.

For selected set N_k(x), with n_k(x) records, define the empirical transition probability of any destination set A as

$$
\widehat K_7(x,A)=\frac{1}{n_k(x)}\sum_{r\in N_k(x)}\mathbf1\{Y_r\in A\}.
$$

This explicitly states how coordinates affect learning: they select comparable historical starts. Once selected, every pair contributes equally. The denominator normalizes a frequency distribution; it is not a mixture of models. Uniform neighbour voting is a standard nonparametric construction; see the [nearest-neighbour method documentation](https://scikit-learn.org/stable/modules/neighbors.html). The precise metric, cap, k candidates and empirical-measure interpretation here are our proposed contract.

Report actual n, unique donor IDs, farthest donor distance, largest ID share, ties and cap-limited cases for every query. Long records can still dominate selected pairs; this is explicitly preserved from raw-pair B2 training rather than silently replaced by equal-ID training.

If no donor is available, mark the new forecast unsupported, with no B2 substitution, invented E mass or expanded radius. Audit this before any outer scoring. All current outer B2 cases are supported, so any additional unsupported E7 case blocks a quality-preserving comparison under this contract and requires review. Do not obtain a better result by scoring a smaller subset. Inner selection likewise requires every B2-supported inner query to have at least one donor under the common cap. Existing B2-unsupported cases retain their original eligibility accounting and are not newly added to the primary comparison.

## 4. Output aggregation, baseline and geographic policy

Keep exact endpoint atoms as the model's probability representation. For grid size g, compute

$$
p^{(g)}_j(x)=\widehat K_7(x,C^{(g)}_j),\qquad
p_E(x)=\widehat K_7(x,\{E\}).
$$

Use the existing grid origin (-180, -90), half-open cells, longitude normalization and `cells(..., res=g)` convention. The 0.5-degree grid is nested inside the 1-degree grid. Verify that summing four child-cell probabilities reproduces the direct 1-degree forecast, with E unchanged. Boundary-only states and precise domain membership follow the frozen grid policy rather than cell-centre tests.

Reuse manifest-owned state indexes and masks, including their existing 0.5-degree records. Do not regenerate masks or remove probability because a cell is partly land. Historical qualified observations and first-exit labels remain authoritative. A conflict between coordinate mapping and a sealed label stops the run. No new beaching classification, probability redistribution or conditioning on staying inside D is allowed.

Construct **B2EndpointRebin** solely as the finer output view of the original B2: for the query's original 1-degree origin cell, take the same complete set of B2 donor pairs and count their actual endpoint coordinates into 0.5-degree destination cells. At 1 degree it must reproduce annual B2 exactly. It has no new fitted parameter and is not a third estimator. Never split a coarse cell's mass equally among four children or assign endpoints to cell centres.

For either forecast and resolution, form the nominal 90% region by sorting positive state probabilities, accumulating to 0.90 with the existing 1e-12 tolerance, and including all positive cutoff ties. H90 counts the actual outcome, including E when selected; K90 counts geographic cells only. Show E separately, never as a polygon. When E is in the region, the visible map need not itself contain 90% probability. Report total attained mass, geographic mass and E membership separately.

Report geographic area as the sum of the selected cells' frozen `wet_area_km2`, with a mask overlay on the map. This is the established full-cell wet-area convention, not a newly clipped-to-D area. Use the same convention for both models. Do not compare 0.5-degree K90 numerically with 1-degree K90 as though cell sizes were equal.

## 5. Training-period selection and matched evaluation

Build an independent neighbour index for each inner fitting role. Generate all three candidates on the same held-out starts, without using held-out endpoints in neighbour selection. Select one k by minimum pooled **1-degree standard Brier** over the two inner held-out windows. If losses differ by at most 1e-12, select the larger k. The distance cap is fixed and not tuned. Save every candidate's per-window and pooled Brier, H90, K90, support and distances. Do not combine candidate forecasts.

Use the established evaluation hierarchy for inner selection and outer reporting: equal times within `(ID, original 1-degree origin)`, equal IDs within origin, then equal origins. Pool repeated ID/origin times across inner windows before assigning weights. Retain these original strata even for 0.5-degree output; changing the reporting grid must not change the target population's weighting. Training votes remain equal per selected pair.

Freeze the selected k before rebuilding on all outer fitting records. Freeze outer predictions at both resolutions, source keys, masks and weights before scoring actual endpoints. No cap, k, quality threshold, example choice or distribution adjustment may be changed after seeing outer results.

Use standard unhalved Brier over the chosen grid's full state space plus E:

$$
BS_t^{(g)}=\sum_j\left(p_{tj}^{(g)}-\mathbf1\{Y_t\in C_j^{(g)}\}\right)^2,
$$

where the sum also includes the E state. All true outcomes assigned zero probability retain their full score. Unlike v1, the new estimator's positive endpoint support and zero-truth rate may differ from B2 because its donors differ.

At 1 degree reconcile annual B2 vectors, keys, weights, regions and aggregate scores with [E4](../results/deliverables/departure_direction_s4_e4/summary.csv), at absolute tolerance 1e-12. Historical seven-day values are Brier **0.9956533528969523**, H90 **0.7501452117911112**, K90 **18.166666666666572**, and zero-truth rate **0.05690042255185551**, on 33,971 cases, 45 IDs and 36 origins. These are checks, not new results.

At 0.5 degrees report matched Brier, H90, K90, wet area, attained probability mass, exit statistics and zero-truth rate for ExactPositionEmpirical and B2EndpointRebin. No historical fine-grid score is assumed. A finer map alone is not evidence of predictive improvement.

## 6. Inference and acceptance

The single primary hypothesis concerns paired 1-degree mean Delta Brier, new model minus B2: H0 Delta >= 0 versus H1 Delta < 0. Use the existing 10,000 whole-ID Exp(1) multiplier procedure, PCG64 seed 20261105, one multiplier per ID shared across origins and models, renormalization within origin and equal origins. Keep fitted models fixed during resampling.

For observed difference d and replicate d*, report a two-sided 95% conditional interval and centered one-sided upper bound `d - quantile_0.05(d* - d)` using linear quantiles. The one-horizon primary level is 5%. This is development evidence conditional on fitted models and observed origins, not independent evidence after all historical research choices, or a complete accounting of common forcing and refitting uncertainty.

Report paired 95% diagnostic intervals for hits, size and area at both resolutions. The 0.5-degree comparison is secondary, not another route to declaring the primary hypothesis successful. Point-estimate preservation is not statistical proof of noninferiority.

| Decision | Predeclared requirement |
|---|---|
| Engineering-valid completion | All input, role, support, mapping, baseline, numerical and replay checks pass; complete roster retained |
| Supported primary Brier benefit | 1-degree Delta Brier < -1e-12 and one-sided upper bound < 0 |
| Legacy-compatible quality preservation | Lower 1-degree Brier, Delta H90 >= -1e-12 and Delta K90 <= 1e-12 |
| Fine-output quality preservation | At 0.5 degrees, Delta Brier <= 1e-12, Delta H90 >= -1e-12, Delta K90 <= 1e-12 and Delta wet area <= 1e-9 km2 |
| Recommend replacing the current seven-day development default | Supported primary benefit plus both quality-preservation checks |
| Trade-off | A gain accompanied by worse hits, size, area or finer-grid probability quality; state the cost and retain the current default pending discussion |
| Benefit unestablished | No supported primary gain, including an uncertain apparent improvement |

A failed improvement criterion is still a completed experiment. Report absolute/relative Brier change, hit changes in percentage points and area changes with intervals. No power claim is inferred from the number of overlapping hourly records; there are 45 outer IDs. Do not broaden the k search or redesign the score after a disappointing result.

## 7. Engineering separation and bounded execution after approval

Reuse immutable input guards, temporal-role construction, source-key extraction conventions, WGS84 geometry, state indexes, Brier/region functions, hierarchical aggregation and whole-ID inference. Add E7-only coordinate inputs, neighbour estimator, pipeline, report and independent audit modules under `src/data3001/modelling/baselines/`, plus an E7 config, runner and meaningful tests. Do not invoke the historical position/velocity rollout pipeline or change shared historical results.

Use exact spatial search rather than all-pairs distances. Build a `cKDTree` on WGS84 geocentric coordinates at zero height. For each query, retrieve up to the largest k by chord distance, evaluate those candidates' WGS84 geodesic distances and obtain an upper bound on the kth geodesic distance. Query the tree again with the smaller of that upper bound and the 100-km cap, including numerical padding, then filter and order candidates by exact geodesic distance. With fewer fitting records than k, use all. Since chord distance is no greater than surface distance, this refinement cannot omit a geodesically closer eligible donor. Include cutoff ties. Validate this claim against exhaustive geodesic search before use.

Cache each query's refined neighbour order within its fitting role and reuse it for all k candidates and both output grids. Bound temporary batches to 1,000,000 candidate distances and stream query batches; never allocate a full query-by-fit matrix. Repeated coordinates may share distance computations but retain record multiplicities. Do not quantize coordinates, approximate rankings or subsample final fitting/scoring records for speed.

The three roles contain 120,344 held-out queries. A naive all-training comparison would require **25,521,453,469** pair distances. Initial 8,000-neighbour retrieval bounds the seed set at **962,752,000** records across these queries; exact refinement adds work and can become broad for sparse queries or ties. These are arithmetic workload bounds from saved role sizes, not a measured runtime or a speedup claim. Monitor candidate counts and reuse geodesic distances already computed for seed records.

| Phase | Cumulative cap | Required outcome |
|---|---:|---|
| Pilot attempts | 600 seconds | Complete input/role/coordinate checks; deterministic representative query benchmark; independent neighbour correctness checks; runtime/RSS/storage projection |
| Primary | 3,600 seconds | All inner candidates, selected outer forecast, frozen predictions, complete scoring and reports |
| Independent audit and fresh replay | 3,600 seconds | Rebuild from sources, reconcile predictions, independently recover scores and inference |
| Total | 7,800 seconds / 130 minutes | Failed attempts included |

Use one process and one numerical thread; peak RSS <= 8 GiB and new retained artifacts <= 5 GiB. Pilot up to 4,096 query keys deterministically stratified across roles and original origins, including sparse and dense local workloads. Outer queries may supply coordinates but use synthetic outcomes during the pilot; do not score true outer outcomes. Do not select k during pilot work.

Proceed to formal execution under the eventual approval only if integrity checks pass, no new common-roster unsupported cases appear, and twice the measured projected phase runtime fits its cap, with 2x memory/storage reserve. No E7 runtime has yet been measured. Stop for review on a failed gate; do not silently reduce k, samples, accuracy or the audit. Record progress, candidates/query, elapsed time, peak RSS and projections at intervals <= 60 seconds.

Keep donor indexes role-specific and immutable; avoid shared native-geometry worker objects. Persist source-key tables, selected-neighbour counts/distances and per-query lineage digests, with complete donor listings for audited examples; deterministic neighbour reconstruction must be possible from pinned sources. Forecast storage may be sparse, but must reproduce full-state scores exactly. Use separate timestamped primary and replay runs. Publish the E7 deliverable link only after audit passes.

## 8. Required verification and delivery

Before formal scoring, verify:

1. Whole-ID separation, cutoff-label purges, exact role counts, source/endpoint key and time reconciliation, immutable hashes and final-test exclusion. Changing outer outcomes cannot change selected k, donor sets, predictions or region masks.
2. Indexed neighbours equal exhaustive WGS84 selection on synthetic fixtures and deterministic real queries from each role and origin. Include duplicate coordinates, kth-distance ties, cap boundaries, fewer-than-k donors, one/no donor and points across an old cell boundary. Verify equal pair votes and unchanged original endpoints.
3. Both grid mappings use exact endpoints; nested probabilities reconcile; nonnegative rows sum to one; E stays E; partial land and boundary states follow the frozen policy. B2EndpointRebin coarsens to the original B2 with exact counts.
4. Independent calculations reproduce Brier, zero-truth rates, ties in regions, H90/K90/area, evaluation weights, parameter selection and multiplier decisions. Retain unsupported-case accounting rather than hiding it in score denominators.
5. Fresh replay reproduces input hashes, donor selection digests, selected k and discrete masks exactly; probabilities and aggregate scores agree within 1e-12, and area summaries within 1e-9 km2. Investigate any discrepancy rather than waiving it as an optimization.

Deliver `results/deliverables/exact_origin_s4_e7/review.html` with separate 1-degree primary and 0.5-degree secondary comparison tables, uncertainty, inner candidate curves and neighbour-support diagnostics. Show actual endpoint dots, matched forecast maps and 90% cell-union regions with common scales. Show two query starts within the same old origin cell to illustrate whether predictions differ.

Choose examples before seeing outer outcomes: take three origins nearest the 25th/50th/75th percentiles of training independent-ID counts, breaking ties by cell ID; in each select held-out starts nearest its longitude quartiles, breaking ties by source key and deduplicating. Actual endpoints are overlaid only after freeze. One held-out endpoint is not an observed conditional distribution.

Archive approval/config, source inventory, role rosters, coordinate provenance, k-selection table, neighbour diagnostics/lineage, both-resolution forecasts and masks, case scores, resource receipts and independent audit. Write an English results/method record and a concise Chinese interpretation. Update the protected stage ledger only through its separately approved recording process.

## 9. Execution authorization

The user approved v2.1 and authorized the exact-coordinate empirical Markov design, seven-day scope, equal selected-pair votes, k in {500, 2,000, 8,000}, fixed 100-km cap, existing temporal/ID roles, 0.5-degree endpoint aggregation, independent B2 control and finer endpoint rebin, the stated common evaluation and decision rules, and pilot-gated execution within the cumulative budget. Development and execution may now proceed within these limits. Resource and integrity failures still require the specified stop and review.
