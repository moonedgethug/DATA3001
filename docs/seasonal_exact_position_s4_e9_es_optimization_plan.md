# Step 4 E9 — ES computation optimization and bounded pilot proposal

## Material Passport

- Date: 7 November 2026, Australia/Sydney.
- Version: proposal v1. Status: **REVIEW_REQUIRED**.
- Scope: computational diagnosis and an implementation/pilot proposal only. No implementation, new prediction, new random draw, model replay or formal experiment was performed to prepare this document.
- Current evidence: source inspection and read-only aggregation of the stopped E9 pilot's saved scores, timings, support tables and receipts.
- Authority: the approved scientific contract remains `docs/seasonal_exact_position_s4_e9_contract.md`, SHA256 `dd6ba68f48359440b84fa2d4ba847925891ffed0f1ce96333034de16e9993f69`. This proposal adds a numerical estimator only if separately approved; it does not overwrite that contract.
- Original run: `seasonal_exact_position_s4_e9_20261106T124835_392309Z`.
- Verified at planning: 498 protected/input and E9 source hashes agree with the prior receipts. No ledger, model code, configuration, data or historical output was edited.

## 1. Decision in plain terms

Do not simply increase the number of random pairs. First eliminate repeated work. Then use a known-mean numerical control variate to reduce the noise of the same Energy Score integral. These are two engineering stages, not additional forecast models.

The statistical hypothesis remains the same four-arm seasonal comparison. A failed computational pilot does not reject that hypothesis. The numerical improvement and runtime estimates below are unmeasured until the proposed pilot; they are not promised speedups.

Approval of this proposal would authorize isolated development and one bounded internal pilot only. It would **not** authorize the formal experiment automatically, even if the pilot passes. Report the pilot and obtain the user's decision first.

## 2. Scientific invariants

Retain AnnualExactPoint, AnnualEndpointCI, SeasonalExactPoint and SeasonalEndpointCI exactly. No extra candidate, fusion, adaptive borrowing or training-weight change.

- Seven elapsed UTC days; majority-season assignment, with exact ties assigned to departure season; identical assignment for historical pairs and queries.
- Seasonal filtering before exact WGS84 nearest-neighbour selection: 100 km, k=8,000, all cutoff ties, all selected original endpoint records and their existing equal votes.
- Original repaired endpoint errors, scale, zero-correlation working CI construction, unusable-error point fallback and empty-season annual fallback.
- Frozen 2001–2019/2020–2022 data roles, ID exclusions and boundary-label purges. The eventual formal experiment still contains all 33,971 queries/45 IDs.
- Equal observations within each evaluation ID, then equal IDs. Training votes remain equal selected pairs.
- ES exponent one, ECEF Euclidean chord distance in km; the observed endpoint, not an observation CI, is the target.
- The same continuous 90% region construction, actual hit definition, total area and land/domain diagnostics; no clipping or geographic reallocation. The 0.5-degree display grid remains display-only.
- Forecast definitions, donor lineage, region packets and numerical keys must be frozen before formal endpoint access. Locked final-test data remain inaccessible.
- Original acceptance criteria, numerical thresholds and hard resource caps remain in force.

The proposed control coefficient is a numerical integration parameter. It never enters donor selection, probability mass, CI widths, season assignment, forecast regions or evaluation weights. In particular, the squared-distance auxiliary calculation below does **not** replace ES with a quadratic or combined loss.

## 3. What the existing evidence establishes

### 3.1 Precision and runtime

The table reproduces the primary SeasonalEndpointCI-minus-AnnualEndpointCI projection. The point comparison is almost identical. Runtime includes both pools and four arms for a primary numerical replicate, not the independent verification replicate.

| ES pairs/query | Projected aggregate 3 SE, m | Approximate threshold, m | Tail-based formal projection, min | With required 2x reserve, min |
|---:|---:|---:|---:|---:|
| 4,096 | 81.633 | 15.065 | 67.48 | 134.96 |
| 8,192 | 57.495 | 15.066 | 75.25 | 150.51 |
| 16,384 | 40.671 | 15.073 | 97.33 | 194.66 |
| 32,768 | 28.694 | 15.066 | 123.74 | 247.48 |
| 65,536 | 20.300 | 15.062 | 200.37 | 400.73 |

The 20.3 m value is a conservative planning estimate of **aggregate score numerical uncertainty**, not an observed position error and not a measured full-validation numerical error. It applies each pilot season's maximum observed per-query variance to the full query weights. It is not a guaranteed upper bound. Retain this projection for the next pilot rather than replacing the maximum with an average to obtain a pass.

The variance trend is consistent with ordinary Monte Carlo: doubling draws reduces standard error by approximately sqrt(2). Continuing this same method would require about 119,000 draws/query to reach the current approximate threshold, beyond the approved 65,536 maximum and with higher cost. This extrapolation is not a recommendation to add another level.

### 3.2 Located redundant work

1. `predict_pool` and `score_pool` both call `draws` using the same key/count. Each repeats donor draws, two sets of geodesic CI perturbations, coordinate transformations and pair distances. This duplication is confirmed in source; it is not an estimate from a profiler.
2. `e8.coordinates` calculates both ECEF and LAEA coordinates. ES discards LAEA; region construction discards ECEF. Those unused transforms are avoidable without changing either metric.
3. Original donor coordinates, original-point land/domain membership and their transformations are invariant. They are recalculated across overlapping donor lists and can be precomputed once per immutable training source.
4. Each ES ladder level currently rebuilds CI region clouds, fitted regions and geographic diagnostics although the cloud key and region budget are unchanged. These can be reused between ES levels after checking exact identity.
5. ES work grows with the numerical draw count. Increasing 4,096 to 65,536 raised measured p95 case time from 0.1066 to 0.3200 s. Neighbour search alone had p95 0.0107 s, so search alone does not explain that growth.

There is no component-level profile yet: the saved timer combines search, ES, regions, geography and serialization. It would be unjustified to claim that a particular fraction of total time is geodesic computation. Component timings are a required pilot output.

### 3.3 Where the numerical noise is

At 65,536 draws, the median per-query standard error for SeasonalEndpointCI was 0.38544 km; the median standard error of its paired CI-minus-point increment was 0.001138 km. The median per-query ratio was 0.00343 (about 0.34%). These are conditional Monte Carlo standard errors, not statistical uncertainty across drifters.

This supports targeting the base point-distribution self-distance term. It does not imply that CI increments may be dropped, or that seasonal and annual distributions may be forced to share probability masses. The complete CI increment and all its covariance with the point term must remain in the score/variance calculation.

The existing 16,384-point region calculation passed its separate stability gates. ES optimization should leave it unchanged.

## 4. Stage A — exact reuse and profiling

Implement in a new E9 numerical-revision module/runner; keep the original source and run available as references.

| Change | Boundary and verification |
|---|---|
| Precompute original endpoint ECEF/LAEA arrays and original-point geographic membership | Same frozen coordinates, CRS, geodesic definitions, dtype and ordering; index into these arrays without rounding or deduplicating votes |
| Separate ECEF-only and LAEA-only transformation paths | Compare each retained transform with the current corresponding output; preserve the geodesic CI construction |
| Compute ES draws once per query/pool/replicate | Freeze the forecast probability law and region first. ES numerical integration occurs once in the scoring stage; no need to calculate the ES self-term in the forecast stage and repeat it later |
| Retain point/CI pairing within each pool | One pair of donor index streams and normal streams feeds both scores; include the full CI correction and covariance |
| Reuse CI cloud/region/geographic packets across ES ladder levels | Same query key, region budget, input hashes and ordered donor keys; no approximation from nearby cases |
| Bounded per-query work buffers | Release buffers after scoring; do not retain every perturbed sample for all queries |

This stage must match the original estimator with the same random streams. Region packets and H90 must agree; transformed coordinates and ES calculations must agree to declared floating-point tolerances (ES absolute 1e-10 km, coordinate relative/absolute checks at machine-scale, existing exact integer-CDF tests retained). Do not allow a tolerance to conceal a changed boundary membership or fallback.

Forecast freezing refers to the immutable probability distribution, donor keys/weights, CI parameters, regions, source hashes and numerical keys/settings. ES arithmetic is evaluation, not information needed to define the forecast. Moving it after this freeze preserves the outcome-access boundary. No outer endpoint is available in the bounded pilot.

Keep annual and seasonal numerical streams independent for nonfallback pools. Do not introduce new cross-query shared random clouds or annual/seasonal coupling: either would need additional covariance analysis. Annual fallback reuses the exact corresponding packet and stream, as before.

Each timing must include cold initialization amortization, searches, transformations, CI perturbations, ES, region/geography work and actual bounded output serialization/I/O. Cached region cost must be charged once in the eventual formal projection, not treated as zero because a later ladder level reuses it.

## 5. Stage B — one known-mean control variate

### 5.1 Unchanged mathematical target

For the selected point distribution with equal votes, let x_i be original endpoint ECEF coordinates in km, and y the observed endpoint in the same coordinates. Draw A and B independently and uniformly from all n donor records, with replacement, including A=B.

Define

    a(y) = (1/n) sum_i ||x_i-y||,
    D = ||x_A-x_B||,
    ES_point = a(y) - (1/2) E[D].

The first term already uses all donors exactly. Only the self-distance expectation needs the proposed correction.

### 5.2 An auxiliary quantity with an exactly known mean

Let C=D^2 and x_bar=(1/n)sum_i x_i. Independence gives

    mu_C = E[C] = (2/n) sum_i ||x_i-x_bar||^2.

Compute this centered expression in O(n) time; avoid subtracting two large ECEF squared moments. It uses every donor and needs no n-by-n matrix.

For a fixed coefficient b, define

    D_controlled = D - b (C - mu_C).

Because E[C-mu_C]=0, E[D_controlled]=E[D]. Hence

    ES_point_hat = a(y) - (1/2) mean(D_controlled)

estimates exactly the same ES. A numerical realization can differ from the old random estimate; the mathematical score and forecast do not change.

### 5.3 Coefficient fitting is independent of scoring draws and outcomes

- Use exactly 1,024 additional point-only donor-pair draws for each query/pool to estimate b=sample_cov(D,C)/sample_var(C). This is a small numerical calibration, not another forecast model or a data split.
- The calibration uses the frozen donor coordinates only, never y or any model-performance result. It gets a separate deterministic SHA256 stream tag `e9_es_control_calibration_v1`.
- Freeze b before scoring draws; keep the original scoring donor/normal streams for direct comparison with the prior computation. Reuse the frozen b across registered ES ladder levels. Both independent scoring replicates use this same frozen b.
- For an exactly degenerate sampled C variance, use b=0 and report the count. Nonfinite coefficients or arithmetic failures stop the pilot. No coefficient/range search is authorized.
- The point and CI arms within a pool share b. Annual and seasonal pools have their own donor-derived coefficients; these affect numerical integration only.

Conditional on the independent calibration, the correction has expectation zero. Thus estimating b does not create same-sample fitting bias. Its realized variance reduction is measured, not assumed. The calibration draws and main draws must not overlap by RNG construction.

### 5.4 Preserve the complete EndpointCI score

Let x_tilde_A and x_tilde_B be the existing independent geodesic error perturbations of the original sampled donors. For each draw retain the existing increment

    delta(y) = ||x_tilde_A-y|| - ||x_A-y||
               - (1/2) (||x_tilde_A-x_tilde_B|| - D).

Then compute

    ES_CI_hat = a(y) + mean[-D_controlled/2 + delta(y)].

Use the sample variance of the **whole bracket** for CI numerical SE. Do not use only the tiny increment variance. Point fallback retains its full vote; all-unusable CI equals point exactly. Empty-season fallback must yield a zero seasonal-minus-annual contrast and zero numerical contrast variance.

For each query, annual and seasonal pools remain independent unless they are exact fallback copies. Aggregate variance uses the original drifter weights squared and both pools' residual variances. For diagnostics involving correlated point/CI arms, use paired sample differences, not an independence assumption.

### 5.5 Expected precision, with explicit conditions

With a population-optimal scalar control coefficient, the variance factor is 1-rho^2, where rho is the correlation between D and D^2. We have not measured this correlation for the current donors. Finite independent calibration may perform worse than that ideal. The next pilot will report actual residual variance ratios by query, season and pool.

| ES pairs/query | Old projected 3 SE, m | Maximum residual variance fraction needed to pass approximately | If actual variance fraction were 10%, projected 3 SE, m |
|---:|---:|---:|---:|
| 4,096 | 81.633 | 3.41% | 25.81 |
| 8,192 | 57.495 | 6.87% | 18.18 |
| 16,384 | 40.671 | 13.73% | 12.86 |
| 32,768 | 28.694 | 27.57% | 9.07 |
| 65,536 | 20.300 | 55.05% | 6.42 |

The 10% column is a conditional calculation, not a measured result or a predicted probability of success. A useful engineering target is a passing common level at 16,384 or below. Every proposed estimator still has to pass the original absolute aggregate gate; a favorable average variance ratio is insufficient.

General control-variate unbiasedness and the ideal variance formula are documented in Sandia's [Control Variate Monte Carlo: Analysis](https://sandialabs.github.io/pyapprox/control_variate_analysis.html), sections on unbiasedness and minimum variance. The particular squared-ECEF-distance identity, independent-calibration design and CI decomposition here are derived for this experiment. No library adoption or package upgrade is proposed.

## 6. Runtime expectations and uncertainties

At the same draw count, removal of duplicate ES work and unused transforms should reduce work, but it cannot halve the entire runtime: region construction, geography, neighbour searches and I/O remain. No component-level speed factor has yet been measured.

An illustrative 16,384-draw scenario uses 0.060–0.090 s of remaining fixed per-query work and 0.020–0.030 s of ES work after reuse, or 0.080–0.120 s total. With the old projection formula this gives about **51–76 minutes** for formal processing. These inputs are engineering assumptions informed by the old timing curve, not benchmarked constants. Full support/lineage and audit projections may change the range.

The target remains **projected formal time <=60 minutes**, so the required 2x reserve fits the unchanged 120-minute cap. Under the old formula, this requires roughly p95 <=0.0946 s/query including the charged work. The planning range straddles that gate: success is plausible but not established. An optimization that fixes precision but still projects 70 minutes does not pass.

The existing formula is `(33971 * p95_case_seconds + 60) * 1.1`. Preserve its conservatism and use the larger of this projection and a measured component-plus-I/O projection. Report max costs and season strata as well as p95. Do not reduce the 2x multiplier or substitute average case time for the tail gate.

## 7. Bounded pilot after approval

### 7.1 Roster, numerical levels and sequencing

- Same frozen 128 inner queries, 64 per role, all four arms and every donor in each defined pool. No easy-case subset, replacement query or reduced donor cap.
- Existing region budget remains 16,384 unless the original registered region ladder is needed to satisfy the original gate; any increase counts in the same time budget. Region clouds/keys and geometry are unchanged and reused across ES-only levels.
- ES levels remain 4,096 / 8,192 / 16,384 / 32,768 / 65,536. Two independent scoring replicates per level, distinct per query. No 131,072 level and no data-dependent sample count per validation case.
- First verify the exact-reuse version against the original on the fixed pilot at the first ES level. Then apply only the one predeclared control variate, increasing the common ES budget solely for precision, never for candidate performance.
- Select the smallest complete common level passing both seasonal comparisons' numerical checks. Check runtime at that level; if it fails, stop rather than search for a favorable faster machine episode. If time ends during a level, it is incomplete and cannot pass.
- Keep the current conservative maximum-per-season uncertainty projection. Independent-seed consistency must also be checked; a passing projected variance alone is insufficient.

### 7.2 Budget, including earlier work

The prior pilot/check receipts total **167.2495 seconds** against the original 600-second cap, leaving **432.7505 seconds**. Allocate at most **420 additional seconds** for this proposal's new pilot/check work. Thus the cumulative pilot is at most 587.2495 seconds, leaving approximately 12.75 seconds for bounded shutdown. No cap reset or hidden extra attempt.

| New phase | Hard allocation | Required output |
|---|---:|---|
| Semantic fixtures, exact-reuse parity, initial component profile | 60 s | Probability/region invariance; paired baseline parity; timer breakdown |
| Fixed 128-case two-seed numerical ladder, including calibration and cold-cache charges | 240 s | Four-arm SE, paired contrast SE, variance reduction, time/RAM/storage by level |
| Independent reconstruction, checks, checkpoint and bounded report | 120 s | Audit receipt, all attempts, precision/runtime decision and visualization |
| Total new execution/check work | 420 s | Stop and report; no formal experiment |

These are upper bounds, not an obligation to consume them. Failed checks stop immediately. Failed/crashed work counts toward the cumulative budget; no autonomous retries. Monitor at <=30-second intervals and checkpoint before the cutoff. If a component cannot fit its allocation, return a partial receipt rather than use another phase's spare time without reporting it.

One worker; no GPU or package/network changes. Retain the original 8-GiB hard RAM and 5-GiB new-artifact caps. Use bounded query-local buffers and a <=512-MiB explicit cache budget. Target observed/projected RAM <=4 GiB and new pilot artifacts <=100 MiB; the eventual formal preflight retains its <=2.5-GiB storage safety gate. Do not persist all MC particle arrays. Any reduction in stored scratch must preserve audit reproducibility through hashes, keys and deterministic recomputation.

The old full-run caps remain formal 120 minutes, audit/presentation 30 minutes, whole execution 160 minutes. The conservative 420-second allocation above includes the new review/report computation rather than quietly excluding it from resource use.

## 8. Verification and stop rules

1. **Probability-law invariance:** same role/query keys, majority labels, ordered donor keys and ties, repaired errors, per-donor weights, all fallbacks, region keys/packets and actual hits. Exact-reuse parity precedes control-variate activation.
2. **Finite mathematical fixtures:** enumerate all donor pairs for small distributions, including duplicates, unequal geographic locations, one atom and diagonal pairs. Verify the centered mu_C identity and exact mean of the zero-mean correction for fixed b. Verify mixed usable/unusable CI identities and all-unusable equality.
3. **Independent calibration:** audit distinct RNG tags and no endpoint dependence; test conditional centering for calibration-derived fixed coefficients on finite fixtures. Do not fit b on the production scoring samples.
4. **SE accounting:** independently recompute residual and paired-difference variances, drifter weights and aggregate variances from retained summaries. Include annual uncertainty and full CI covariance. Never use corrected-score sample variance across IDs as numerical MC variance.
5. **Independent seed check:** recompute both internal replicates at every completed level. Their aggregate seasonal contrast difference must be consistent with the combined numerical SE (absolute difference <=3 times the combined SE); investigate failure rather than choose the favorable seed. The original <=10%-of-claimed-effect rule still applies to any eventual scientific claim, not to choosing a better pilot performance result.
6. **Original precision gates:** 3 SE <=0.0001 of the corresponding annual reference mean; region mass discrepancy <=0.005, weighted H90 numerical change <=0.001, mean-area numerical change <=0.005. Actual thresholds are recomputed from the specified reference; 15.06 m is only the current planning approximation.
7. **No region shortcuts:** check unchanged covariance/quantile, geodesic mapping, polygon diagnostics, point/CI weights, missing-error and empty-season fallback. The old 24 tests remain required; add tests only for the new numerical identity, independence, freezing and cache behavior.
8. **Protected sources and access:** original contract, data/error overlay, ledger and historical sources remain untouched. Isolated revision files only; no outer endpoints or final-test data during this pilot. Write run/source fingerprints and lineage evidence, including seasonal donor reconstruction receipts missing from the old pilot.

If the maximum level, time cap, identity checks or memory/storage gates fail, stop and report numerical/resource insufficiency. No switch to a different control variate, QMC, coupling, smoothing, lower precision or an enlarged budget is authorized by this proposal.

## 9. What passing this pilot would and would not establish

Passing would establish a candidate computational implementation with observed internal precision and runtime evidence. It would not establish seasonal benefit, full-validation precision, or final permission to run the experiment.

Before any later formal authorization, the original full-roster outcome-blind support/storage/audit preflight remains required: every season's pairs/IDs, all 33,971 query keys, support/ties/fallbacks, degeneracies, error availability and actual lineage storage. The pilot projection must charge this work, including initialization and output, without counting cached searches twice. It is not silently included as new full-population work in the 420-second internal pilot. If it remains unmeasured, mark formal readiness provisional.

Forecast definitions and numerical budgets must then freeze before outer outcome access. Formal ES variance must be computed from the full scored roster; if it fails the original frozen precision gate, report inconclusive rather than retuning after seeing outcomes. Scientific acceptance, all-ID bootstrap and matched map examples remain exactly those in the original contract.

## 10. Deliverables and decision requested

After approval and the bounded pilot, deliver: old-versus-reused arithmetic parity; component timings; every completed ES level and both seeds; coefficient and variance-reduction diagnostics; unchanged region/fallback evidence; cumulative resources including previous attempts; full-run conditional time/storage/audit estimates; and a concise visual report with a pass/stop/provisional distinction.

The requested decision is whether to approve **exact computation reuse plus this single known-mean control variate**, with the 420-second additional pilot cap and no automatic formal run. No scientific model amendment is requested.

## Evidence pointers

- Model implementation: `src/data3001/modelling/baselines/seasonal_exact_position_s4_e9.py`, especially `draws`, `predict_pool`, `score_pool`.
- Shared geometry: `src/data3001/modelling/baselines/position_error_s4_e8.py` and `position_error_s4_e8_geometry.py`.
- Gate calculation: `src/data3001/modelling/baselines/seasonal_exact_position_s4_e9_pipeline.py`.
- Pilot receipt: `provenance/runs/seasonal_exact_position_s4_e9_20261106T124835_392309Z/pilot_gate.json` and `*_resources.json`.
- Saved evidence: `results/runs/seasonal_exact_position_s4_e9_20261106T124835_392309Z/pilot/` and `pilot_audit/`.
- Prior independent review: the matching provenance run's `pilot_independent_review.json` and `stopped_delivery.json`.
