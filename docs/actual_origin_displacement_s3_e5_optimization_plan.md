# Step 3 E5 O1 — Exact Geometry Optimisation and a Bounded Resource Trial

**Version:** E5 O1 v1, 1 November 2026 (Australia/Sydney).
**Status: PROPOSAL FOR USER REVIEW. No optimisation implementation, profiling run or rerun is authorised by preparing this document.**

This is an engineering amendment to [E5 v2](actual_origin_displacement_s3_e5_plan.md), whose SHA256 remains `67afaa77db68bb66e924741cda3c760188be96b4b1843aa78309df11bf4d3fe3`. The original plan, code, failed pilot, results and research-stage ledger remain unchanged. The user is willing to accept longer computation when it has a credible completion estimate; the former one-hour full-preparation limit is therefore a constraint to reconsider, not a scientific reason to abandon E5.

The immediate objective is to make the **same forecasts and evaluation** affordable and auditable. An exact engineering acceleration does not itself improve Brier. It enables the previously unperformed comparison of Fixed grid/analytic and Adaptive grid/continuous selection. The ultimate claim remains best supported performance within the declared model families and validation design, not a guaranteed globally best ocean model.

## 1. What the existing evidence establishes

Sources: [resource result](actual_origin_displacement_s3_e5_results.md), pilot `actual_origin_disp_s3_e5_pilot_20261031T123704_492621Z`, and its sealed source snapshot. This review read code, existing CSV/JSON receipts and registered polygon definitions. It did not classify any new trajectory, fit a model or run a timing experiment.

| Item | Verified observation | Interpretation limit |
|---|---|---|
| Completed pilot queries | 7 of 50; all 7-day, cell 43663, query fold 1 | No measured 30-day or coastal timing coverage |
| Donors per completed query | 67,042 across donor folds 0, 2, 3, 4 | Includes the extra block needed for outer-cache reuse; inner fitting uses only 2, 3, 4 |
| Per-query timed call | Mean 37.84965 s; range 37.45857–38.07510 s | Timer surrounds `classify`, including donor validation and certificates; it does not isolate GEOS work |
| Hourly donor-step count | 651,168–1,093,607 per query, a 67.95% range increase | Counts of operations, not stage elapsed times |
| Timed-call range increase | 1.65% | Suggests a substantial common/fixed cost; does not identify its cause |
| Rectangle certificates | 434,332 / 469,294 donor transfers, 92.55% | Certificate success is not a measured 92.55% time saving |
| Literal work remaining | 34,962 donor transfers, 5,870,929 hourly donor steps | These still require exact chronological decisions |
| Peak RSS | 0.892 GiB against the 8-GiB cap | Time, rather than this measured memory usage, triggered the stop |
| Stop | 300-second alarm; process returned after 300.58 s | The eighth query was interrupted; exclude it from completed-query averages |
| Solver capacity profiles | None reached | No measured cost for real-data four-solver search, region scoring or full uncertainty |

The current ledger contains 15,179,967,338 seven-day and 12,193,653,838 thirty-day query–donor combinations across outer roles, approximately 27.37 billion combined. These counts already include the proposed fold-block reuse; do not promise another fourfold reduction on top of this denominator.

The earlier 154.33-hour extrapolation concerns only the measured 7-day cell, uses an incomplete seven-query sample, and combines a factor-two reserve with ideal two-worker speedup. It is a scale warning, not a measured runtime, confidence bound or defensible total-project estimate. The whole experiment cannot be priced reliably from this one cell.

## 2. Why this is expensive, and what is still unknown

### 2.1 Scientific workload that remains real

An exact query start changes the translation applied to each donor. Two starts inside one 1-degree cell can have different destinations and land/exit decisions. E1's eight integer-offset event caches cannot simply replace these query-dependent outcomes. Each donor contributes its complete qualified pair weight; removing difficult donors or using only endpoints would change the estimator.

The calculation must also distinguish a valid first observed exit from a failed transfer. Chronological order matters: a land intersection before an exit cannot be replaced by an endpoint-only test. Geometry checks are guards on the specified straight hourly segments, not a proof of physical ocean reachability.

### 2.2 Confirmed implementation repetitions

In `actual_origin_displacement_s3_e5_inputs.py`:

- `load_prepared` already checks source keys, required paths and original R/D starts. `classify` then rebuilds fitting-ID sets, scans donor membership and rechecks every original donor start against R and D for every query. For a fixed origin/horizon/fitting context, these facts are unchanged.
- Each 2,048-donor batch repeats DataFrame slicing and column-to-array access. Each active hour reconstructs `list(g.states)` and calls `np.isin`, although the state index is fixed.
- Every eligible donor rectangle still requires construction and predicates against the domain and both land-mask objects. A successful certificate may itself be expensive.
- Uncertified paths repeatedly allocate translated-coordinate arrays and LineStrings, then call point and segment predicates for the two masks.
- The runner filters the complete donor table per query. This filtering is outside the saved `classify` timer, so optimising it can help total runtime but cannot explain the recorded 38 seconds by itself.
- The pilot processes queries sequentially. Two workers were permitted, but no parallel query executor was used.

These repetitions are observable in source. Their share of the 38 seconds is **not measured**. The nearly constant timing despite varying hourly counts makes invariant validation, certificate work and per-batch overhead high-priority suspects. It does not prove that any one of them dominates.

### 2.3 Optimisations already present

The implementation already prepares geometry objects, uses vectorised predicates, stores original paths once, precomputes forward path bounds, uses a registered-state prefix table for certificates, and stops failed/exited donors early. Geometry preparation must not be sold as a new discovery. Shapely documents prepared predicates and their role in speeding repeated spatial tests, but this is already enabled in `Geometry.__post_init__`. [Shapely prepare](https://shapely.readthedocs.io/en/stable/reference/shapely.prepare.html)

Neither “the ocean geometry is intrinsically this slow” nor “we only need more CPU” follows from this pilot. Exclusive stage timings are missing. A long run of the same unprofiled implementation is not yet justified.

## 3. Scientific and numerical invariants

Retain all E5 v2 definitions:

- The cleaned v7 release, qualified source-keyed observations, annual pooling, exact 7/30-day horizons, original R, D and both shoreline masks.
- Actual query coordinates and `x0 + [z_d(t)-z_d(0)]`, with the same longitude normalisation and floating-point operation order. No coordinate rounding, interpolation, path thinning, donor sampling, endpoint clipping or neighbour extension.
- All eligible hourly donor pairs and their original multiplicity. Primary evaluation remains equal times within ID/origin, equal IDs within origin, equal origins, with the common B2 support mask.
- Every hourly vertex and connecting segment is either evaluated or covered by a conservative proof that the entire segment interval has the same valid result. A proof-based shortcut is not permission to ignore hours.
- Original event precedence, boundary inclusion, first **observed** exit E, and exact failed-donor mass returned to B2. Keep the two masks' decisions separate so disagreement reasons remain reproducible.
- Five-outer/four-inner whole-ID CV; fitting-only support medians and thresholds; the six controls; standard Brier; the fixed 90% region with existing ties/E treatment.
- All four solver procedures, parameter domains and finite budgets: 21/84 grids, up to 114 Fixed quality points, up to 252 shared full-metric points, 11 continuous starts, 2,000 calls per start, 50,000 multiplier draws and 72 primary directional contrasts.
- Locked final-test trajectories, immutable prior runs and the outer-freeze rule before all-development tuning.

Discrete donor destination/reason/count outputs must match exactly. Probabilities, Brier and aggregate metrics must match within absolute 1e-12, with identical region membership and selection decisions under the frozen tie rule. Matching average Brier alone is insufficient.

## 4. Exact reuse and acceleration, in priority order

### G1 — Remove repeated invariants and use the verified rectangular domain

Create immutable donor-context arrays keyed by source identity, horizon, origin-neighbour set and donor-fold block. Validate source keys, R eligibility and membership once when constructing each context. At each query, still verify its own coordinate and use a constant-time check that the requested context excludes its entire ID/fold. Cache validity must fail on changed input, geometry, fitting IDs or transformation version.

Replace per-hour rebuilding of state lists with a precomputed 64,800-entry boolean lookup, including explicit invalid-index handling. Store source starts, track ends, timestamps, flags, endpoints and bounds in typed arrays; preserve all records and their multiplicities. Do not materialise every overlapping donor window as a separate dense 720-hour array.

The registered D GeoJSON was inspected and hash-checked in this review. It is exactly the closed rectangle `[-81,-8] x [20,55]`, without holes. Consequently finite normalised point membership and padded-rectangle containment can use inclusive numeric bounds rather than general polygon predicates. Enable this only after asserting the pinned polygon identity and shape. R is a nonrectangular corridor and must retain its polygon semantics. D-clipped segment/land checks remain exact; this shortcut changes neither coastlines nor exit rules.

Expected structural benefit: invariant validation falls from once per query over all donors to once per reusable context, and state/domain tests become array lookups/comparisons. Total speedup is unknown until its time fraction is measured. Retain source qualification checks; move them out of the hot loop rather than removing them.

### G2 — Index exact land components and avoid impossible intersections

Build read-only spatial indexes once for the exact components of each original land mask and each D-clipped segment mask. Preserve holes and coordinates. Query the indexes with the actual rectangle, point or segment bounding box; perform the original precise predicate only on components that could intersect. Empty bounding-box candidate sets certify no intersection. A bounding-box overlap is never itself a land hit.

Use individual components rather than indexing one world-scale MultiPolygon bounding box. Shapely's STRtree documentation specifically distinguishes the efficiency of these representations. The tree is an exact candidate filter, not a replacement shoreline or a nearest-land heuristic. [Shapely STRtree](https://shapely.readthedocs.io/en/stable/strtree.html)

Keep a predicate-equivalence fallback for unsupported/ambiguous geometry representations. No simplification, raster land approximation, coastline buffering, changed resolution or coordinate snapping is allowed. Do not introduce a new union operation that alters original predicate coordinates merely to accelerate the index.

Expected benefit: reduce expensive exact predicates where most components are irrelevant, especially for water-only certificates. This is a plausible substantial saving, not a demonstrated factor. Build G2 only if measured certificate/point/segment predicates account for at least 30% of G1's timed kernel or its resource projection remains unacceptable; record the trigger before implementation.

### G3 — Certify safe time blocks before descending to individual hours

If G2's unresolved hourly processing still accounts for at least 20% of its kernel time, add conservative temporal blocks with a fixed initial maximum length of 32 hours. Precompute bounds and continuity/validity summaries on the shared source-track representation. Each node includes all vertices and connecting segments in its interval, including the shared endpoint with the preceding interval.

A node can be skipped only when its full translated envelope is inside D, touches no land in either mask, maps only to registered states, and has complete valid hourly support. Otherwise split chronologically until the original hourly/segment rule is applied. Inspect the earlier child first and stop at the same first decisive event. An envelope touching land is a reason to descend, not a failed donor. Original-source E labels cannot substitute for the relocated event.

This targets the 7.45% of pilot transfers whose whole-path rectangles were not certified. Many may contain long safe intervals even when their full envelope overlaps land. The actual reduction is unknown; certification rate alone cannot predict wall-time gain. Include gap, unavailable continuation, longitude-wrap and boundary cases in parity checks. Unsupported wrap cases use the old exact path rule.

If the trigger is not met, record G3 as not attempted and keep the simpler exact version. Do not add a fourth geometry algorithm during this trial.

### Reuse across models, folds, horizons and identical coordinates

| Reusable item | Exact reuse rule | Limit on claimed saving |
|---|---|---|
| Geometry versus weights | Compute donor outcomes once; reuse them for all four solver procedures and all candidate weights | This was already intended in v2; not a new measured fourfold gain |
| Inner/outer roles | Persist separate donor-fold counts; combine only permitted blocks for each role | Avoids roughly fourfold repeated inner classification relative to a naive implementation; already included in the 27.37-billion ledger |
| Query coordinates | Reuse a geometry block for bit-identical coordinates and the same donor-block/geometry/target identity; retain each time's truth and evaluation weight | Never reuse a cell-average outcome for different coordinates; frequency of exact duplicate coordinates is unknown |
| 7/30-day common prefixes | For exactly matching query and donor source starts eligible at both horizons, retain the 7-day result/prefix while continuing to day 30 as needed | For a fully checked shared pair, 168+720 becomes at most 720 hourly steps: up to 18.9% fewer steps, about 1.23x, not a 2x whole-run claim |
| Brier optimisation | Reuse fitting-role/origin coefficient blocks and support values | Already implemented in principle; full H90/K90 still requires query distributions |
| Region evaluation | Cache sparse support, truth index and block-specific weights; batch exact mixtures/rankings with fixed tie handling | This stage was not reached in the pilot; its possible cost must be measured, not assumed negligible |

The same-coordinate cache is keyed by coordinate bits, donor fold and versioned inputs rather than query future labels. Every access still checks fold/ID eligibility. Cross-horizon sharing retains **both** full eligible populations: a pair qualified only at one horizon remains in that horizon. A 7-day event or checkpoint may be reused; an unresolved future must never be silently imputed.

Persist per-query/per-donor-fold sparse destination/reason counts, support information and lineage. Use atomic chunk commits and a manifest so a deliberate pause can resume identical work without recomputing completed chunks. A resume is not permission to change code, source identity or fitting roles. Incremental checkpoints reduce wasted work; they do not reduce the underlying estimator's workload.

### Concurrency

Keep the initial limit of two workers and one numerical-library thread per worker. Measure serial and two-worker throughput on the same frozen workload after geometry/index construction. Share only immutable arrays/indexes; do not prepare or mutate shared geometry while workers use it. Shapely generally releases the GIL during GEOS operations, making threading worth measuring, but Python overhead and memory bandwidth can prevent ideal scaling. [Shapely multithreading](https://shapely.readthedocs.io/en/stable/index.html#multithreading)

Use whichever allowed worker mode is demonstrably faster; within 5% choose the simpler single-worker mode. No assumption of ideal twofold speedup in the new runtime projection. Additional cores, a GPU, cloud expenditure, new low-level compiled kernels or a changed machine are outside this first amendment.

## 5. Expected benefit: structural savings, targets and uncertainty

No new benchmark was run, so no proposed speedup is a measured result. The first milestone is a **10x end-to-end kernel acceleration on the paired calibration workload**, subject to exact equality. It is an engineering target, not a promise or the sole acceptance criterion. A smaller gain can still be useful if a complete conservative run estimate fits the agreed longer budget; a 10x gain is insufficient if total cost remains excessive.

Illustrative sensitivity using only the earlier 154.33-hour single-cell diagnostic:

| Hypothetical achieved acceleration | That diagnostic divided by the factor |
|---|---:|
| 2x | 77.16 hours |
| 10x | 15.43 hours |
| 50x | 3.09 hours |
| 100x | 1.54 hours |

This table is not a full-runtime forecast and excludes other cells, 30-day work, scoring and replay. It shows why merely extending a five-minute pilot or doubling workers may be insufficient. Do not multiply speculative gains from overlapping optimisations.

Use the measured stage fraction f and stage speedup s to assess the ceiling `S_total=1/[(1-f)+f/s]`. For example, a tenfold speedup of a stage occupying half the original time only gives about 1.82x overall. The nearly constant observed per-query times are a reason to profile those fractions before investing heavily in an hourly-loop rewrite.

If G1–G3 remain too slow, return a measured engineering result. More advanced exact bulk counting or spatially certified grouping of donor outcomes could avoid visiting every query–donor pair separately, but requires a separate proof and proposal. It is not included as an unbounded fallback in this trial.

## 6. Instrumentation and the new two-hour trial

**Proposed cumulative real-data execution cap: 7,200 seconds**, including new source verification, index construction, old-kernel reference calls, optimisation benchmarks, paired validation, real-data audit and scoring-capacity work. No real-data run occurs before user approval. Code preparation and small synthetic semantic tests are separate engineering time; this is not a promise to deliver the implementation in two hours. Conditional G2/G3 development may occur between stages, but all real-data executions, including interrupted or failed attempts and repeated startup, count towards the same budget. Engineering time does not authorise extra real-data benchmark cycles.

Record exclusive timers and counters for: input load/hash checks; context building; original-donor checks; query checks; domain/registered-state tests; rectangle construction; each mask's certificate predicates; hourly translation; point predicates; segment construction; each segment predicate; aggregation; guard/checkpoint overhead; disk I/O; control fits; Brier objective/gradients; region scoring; multiplier aggregation; and independent audit. Record cold setup separately from steady throughput, CPU time as well as wall time, cache hit rates, tree candidate counts, peak combined RSS and artifact size.

Instrument at batch/stage granularity rather than timing every scalar coordinate. Compare an instrumented and uninstrumented reference call on the same calibration query, with geometry caches disabled for that comparison. If overhead exceeds 5%, report it and use uninstrumented wall times for capacity estimates; do not subtract an unverified constant from timings. Timer categories must reconcile to total elapsed time, with any residual disclosed.

| Stage | Maximum elapsed time | Required output |
|---|---:|---|
| A: source checks and reference profiling | 20 minutes | Stage shares on the paired calibration cases, current expensive operations, cold setup cost |
| B: bounded exact optimisation comparison | 50 minutes | G1, conditional G2/G3; correctness and measured speed; fixed configuration choice |
| C: frozen validation, fold-block and scalar checks | 35 minutes | Coverage beyond the original 7-day cell, outcome equality and serial/two-worker evidence |
| D: scoring/control/uncertainty capacity and projection | 15 minutes | Four solver cost profiles, actual 90% region costs, complete runtime/storage projection |

Each stage has its stated execution cap, and all stages share the overall two-hour limit. No extra attempt, model grid or new geometry variant is added after a failure. A stage that cannot complete its required evidence returns `CAPACITY_NOT_ESTABLISHED` or the appropriate integrity failure. Do not infer feasibility from a successful fast subset.

### Frozen query roster and configuration selection

Keep all 50 original outcome-independently selected pilot queries. From that roster choose eight calibration queries: for each horizon, the first and last source-key-sorted queries in its largest-work offshore cell and largest-work coastal cell. Rank cells by the saved `pilot_work_product`, with ascending cell-code ties; the saved table selects offshore cell 43663 and coastal cell 44382 at both horizons, each represented by eight frozen queries. Order query source keys by `(id, origin_source_obs)`. De-duplicate identical selections and document any unavailable category; do not replace a missing category with a convenient low-cost case.

Add one outcome-independently selected query per horizon from each of the other four query folds, eight additional queries. For each role use its largest-work origin with positive local and neighbour fitting support, with ascending origin/source-key ties. Freeze/hash these additions before timing. The proposed maximum roster is therefore 58 queries. The remaining 50 are engineering validation cases; they are not a new model-performance test set.

Every chosen query uses **all** eligible donors in its four allowed outer donor-fold blocks. Inner comparisons combine three of those blocks. Never reduce donor count to make a slow query fit. The eventual scientific experiment retains all qualified cases (303,288 and 268,998 before the unchanged common support handling), not only these pilot queries.

Compare at most three cumulative geometry variants G1/G2/G3 and two donor batch sizes, 2,048 and 8,192. Select by exact parity, capacity and elapsed time on calibration only; within 5% choose the earlier/simpler variant and then the smaller batch. Freeze that choice before validation. Measure at most the two allowed worker modes. No Brier, hit-rate improvement, favourable endpoint map or outer performance determines the engineering configuration.

Obtain full old/new donor-outcome parity on all calibration queries and four predetermined non-calibration validation queries, one per horizon/coastal category. Select each of these four as the first remaining original-roster query sorted by `(origin_cell_1, id, origin_source_obs)` in that category; freeze them before any timing. For the remaining validation cases require deterministic aggregate reconciliation, fold-block reconstruction and at least 5,000 independent scalar query–donor checks over the complete pilot, stratified across both horizons, observed decision reasons, coastal classes and query folds. Include at least one case of every observed reason; synthetic fixtures cover absent rare branches. This is a sampled real-data geometric cross-check, not independent inspection of all donor combinations.

The scalar-check sample is an audit only. It does not replace any donor distribution or evaluation population. Stop on any mismatch in destination, failure reason, first-event ordering, probability, region membership, weight, candidate choice or cache lineage.

## 7. Validation beyond speed

Retain and extend the existing semantic suite before new real-data execution. Test:

- True-start identity, distinct same-cell starts and source-key/time reconciliation; numeric rectangular-D tests against the frozen polygon on edges, corners and adjacent representable floats.
- Source and role-context mutation rejection, whole-ID exclusion, exact-coordinate cache aliases, donor-fold combination versus direct fitting-ID filtering, no-neighbour and unsupported rows.
- Both masks separately, land contact at a segment interior or endpoint, mask disagreement, first exit then return, land before exit, and land outside D after exit.
- Full-path versus time-block traversal, block-boundary segments, gaps, missing continuation, invalid positions, unindexed cells and longitude wrapping. A failed certificate must fall through, not become a failed donor by itself.
- 7/30 shared prefixes only on common eligible source starts; all one-horizon-only pairs retained; independent horizon computations reproduce the shared computation.
- Exact aggregate donor mass, failed-weight B2 return, source support IDs, standard Brier including zero-probability truths, fixed-90% ties/E and query-before-ID aggregation.
- The four v2 solver procedures and selection decisions unchanged by batching/caching. Optimiser mathematical bounds, candidate containment and rejection statuses remain audited.
- Serial/two-worker integer output identity, deterministic final reduction order, checkpoint interruption/resume equality and rejection of stale/incomplete chunks.

Keep the v2 kernel unchanged as a reference. Add the optimised kernel/context under a distinct E5 engineering module and a new run/config namespace. Preserve all original snapshots, failed pilot receipts and the original plan hash. A performance rewrite must not overwrite the reference implementation needed to establish equivalence.

## 8. Runtime projection and a longer full-run budget

The new estimate must cover the **whole pipeline**:

`T_primary = setup + exact geometry/cache + fitting + candidate Brier/regions + controls + uncertainty + audit + output I/O`.

`T_total = T_primary + fresh geometry replay + fresh scoring/report replay`.

Estimate geometry by horizon, coastal status, donor workload and certificate/literal-work fractions, using the full saved workload counts and measured validation rates. Report both a central workload-weighted estimate and a conservative estimate using the slowest relevant measured rate with a factor-two reserve. Use actual measured parallel throughput; do not divide by two automatically. A materially uncovered class yields an unknown estimate, not a zero cost. The user receives measured coverage and sensitivity ranges, not a falsely precise completion time.

Region-score projection must cover the v2 upper bound of 721,080,360 query–candidate evaluations before exact sharing, the 12 selection tasks, all six controls and the 50,000 multiplier draws. Time the expensive stages separately. Do not treat total solver time minus region time as a pure coefficient measurement when it also contains controls/audit, or cover unmeasured full controls with an arbitrary fixed allowance. Include complete replay and checkpoint/storage overhead once each, without double counting overlapping timers.

The user's time flexibility supports replacing the old one-hour requirement with a **provisional 72-hour end-to-end planning envelope**, including fresh replay. This is a proposed budget for discussion, not an authorised long run or a promise:

| Conservative estimated total | Proposed interpretation |
|---|---|
| Up to 24 hours | Plausible overnight/full-day execution, subject to exactness and resource checks |
| 24–72 hours | Reasonable multi-day option if the measured completion estimate is credible and the user approves that budget |
| 72 hours to 7 days | Return the detailed cost and scientific value for an explicit longer-run decision; do not call the method invalid |
| More than 7 days or major unknown cost | Revisit exact algorithm design or computing resources before committing; do not automatically retry |

For this trial keep **combined peak RSS <=8 GiB, at most two workers and one numeric-library thread per worker**. Propose **20 GiB of combined new-run artifacts** for the optimisation trial and any later primary/replay, replacing the former 5-GiB storage cap only if this amendment is approved. Check free disk before starting and report the projected cache footprint; use lossless sparse storage and atomic chunks. The memory cap is combined across workers, not 8 GiB per process. No paid/external computation is included.

A long run should emit periodic completed-work/ETA receipts and use resume-safe immutable checkpoints. Observed throughput deterioration must update the estimate. Reaching an approved resource cap stops at a checkpoint for review; an unfinished fold is never dropped from the eventual scientific comparison.

## 9. Acceptance and deliverables

| Decision | Requirement |
|---|---|
| Correct acceleration | Declared pair-level and aggregate parity, scalar/semantic audits, whole-ID exclusion and region/selection equality pass |
| Useful engineering improvement | Measured representative total throughput improves, including setup/serialization; identical forecasts alone do not imply faster execution |
| Capacity established | Both horizons and relevant geometry/workload classes covered; full solver/scoring/control/uncertainty costs measured; conservative time/storage estimates fit a subsequently approved full-run budget |
| Capacity not established | Missing stage coverage, trial timeout, unstable projection or footprint overrun; report the reason rather than a model-quality verdict |
| Ready for scientific comparison | Correctness and capacity pass, code/config/source identities freeze, and the full-run budget is approved |
| Scientific quality improvement | Still determined only by E5 v2's complete outer Brier/H90/K90 comparisons, uncertainty screen and controls; optimisation timings provide no evidence of improved prediction |

Deliver an English optimisation audit and local HTML review with: exclusive stage-time bars; current/optimised paired times; certificate/tree-candidate and cache-reuse counts; coverage by horizon/coast/fold; serial/two-worker throughput; cold setup and storage; pair-level parity receipts; solver/scoring cost profiles; and central/conservative end-to-end estimates including replay. Clearly distinguish measured speed, extrapolation, unmeasured work and scientific results not yet run. The Chinese summary should state whether spending one to three days is now justified by measured evidence.

## 10. Review decision requested

Approve or revise the scientific invariants, G1 plus the conditional G2/G3 sequence, 58-query maximum engineering roster with complete donors, finite configuration comparison, two-hour real-data trial, 8-GiB combined memory and proposed 20-GiB artifact budget. Approval of this optimisation/trial proposal alone would **not** start a multi-day full experiment: return the resulting whole-pipeline estimate and parity report first, then confirm the full-run budget.

No source/config changes, profiling, new trajectory classification, training or rerun were performed while preparing this proposal. The stage ledger remains unchanged.
