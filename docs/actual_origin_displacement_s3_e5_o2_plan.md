# Step 3 E5 O2 — Exact Group Counting, Process Isolation and Completed Validation

**Version:** O2 v1, 1 November 2026 (Australia/Sydney).  
**Status: PROPOSAL FOR USER REVIEW. NO DEVELOPMENT OR REAL-DATA EXECUTION AUTHORISED BY THIS DOCUMENT.**

This proposal responds to the excessive projected runtime and the O1 concurrency failure. It proposes a different exact computation of the already approved E5 estimator, not a new statistical model. This turn reads existing code and sealed results and performs arithmetic on saved timing/workload tables only. The original E5/O1 plans, execution closures, source, results and research-stage ledger remain unchanged.

Approval would cover implementation, synthetic verification and one new bounded engineering trial. It would not authorise full nested CV, a full replay, final-test access, model replacement, stage closure, a Git commit/push or external compute. The closed O1 execution must not be reopened.

## 1. Decision and evidence

Prioritise **exact aggregation of groups of donors**, including group-level time-block proofs, rather than another round of per-pair predicate tuning. Retain serial G3 as the exact fallback. Repair process ownership and durable verification before any concurrent real-data work.

Evidence: [O1 results](actual_origin_displacement_s3_e5_o1_results.md), [saved timings](../results/runs/actual_origin_disp_s3_e5_o1_20261031T131701_288861Z/timings.csv), [workload](../results/runs/actual_origin_disp_s3_e5_o1_20261031T131701_288861Z/workload.csv), and [geometry projection](../results/runs/actual_origin_disp_s3_e5_o1_20261031T131701_288861Z/geometry_only_projection.json).

| Verified observation | Implication |
|---|---|
| Original kernel 334.395 s; selected G3 21.721 s on the same eight calibration queries | A 15.39x kernel gain was measured; it is not an end-to-end gain |
| 27,373,621,176 outer query-donor combinations remain after fold reuse | Reducing hourly work alone leaves an enormous pair-enumeration workload |
| About 83.2% of the central geometry extrapolation comes from 30-day offshore queries | That category is the main capacity target, though its rate was measured at only one origin |
| Two 30-day offshore queries use 122,042 donors, 1,116,281 block attempts and 9,484 literal hourly steps | Many costs are repeated safety proofs; a failed whole-path box often does not imply an unsafe path |
| Those two queries certify only 74,143 donors with a whole-path box | Grouping only already-easy whole-path boxes is insufficient; group time-block proofs are necessary |
| Eight calibration queries matched 355,418 original outcomes/reasons in process | Useful preliminary correctness evidence, but optimized arrays were not persisted before the crash |
| O1 extended validation, 5,000 scalar checks and scoring/control capacity work did not complete | O2 must complete these obligations before making a capacity claim |

Existing fold/model reuse must not be advertised as a new gain: geometry already need not repeat across four weight-selection procedures or across the three-fold inner unions. Likewise, a reduction in computation does not remove observations or reduce the statistical sample size.

## 2. Frozen scientific contract

Inherit [E5 v2](actual_origin_displacement_s3_e5_plan.md) and its approval, with the O1 resource amendments only where explicitly renewed below:

- Cleaned v7 development release, original qualified hourly source keys, annual pooling, 7/30 days, 1-degree destination cells plus E, unchanged R/D and both land masks.
- Actual query coordinate `x0`; each donor follows `x0 + [z_d(t) - z_d(0)]` with the original floating-point operation order and longitude normalisation. No rounded anchors, common cell-centre start, path thinning or endpoint-only validity check.
- Original eligible donors in the eight neighbouring cells, actual starts in R/D, raw pair multiplicities, complete normalisation denominator. No donor/query subsampling in a forecast, outside-region donors or outcome-based donor removal.
- Every hourly point and connecting segment is checked directly or covered by a conservative proof. Preserve chronological missing-data checks, segment/point precedence, first observed exit E, and failed-donor return to B2. An inconclusive certificate is not a physical failure.
- Five outer/four inner whole-ID roles, fitting-only support and medians, original common supported-case mask. Training remains pair-frequency based. Evaluation averages times within ID/origin, IDs within origin, then origins equally.
- Full scientific populations remain 303,288/268,998 qualified times before unchanged common-support handling. The engineering roster below measures capacity; it does not replace those populations.
- Standard Brier, fixed 90% regions and the existing tie rule, H90/K90 gates, all controls, four E5 selection procedures, parameter domains and finite search budgets remain unchanged.
- No query-future information enters a prediction or engineering configuration choice. Locked final-test and canonical raw trajectory reads remain denied.

An exact acceleration must reproduce probabilities and scores. It is not expected to improve Brier relative to the same estimator executed slowly.

## 3. What must be calculated, rather than individually enumerated

For query q and an allowed donor-fold block g, retain integer counts by destination and failure reason:

`C[q,g,j] = sum over eligible donors d in g of 1{transfer(q,d) = j}`.

Also retain failure counts F, complete donor count N, and the ID membership needed for exact support diagnostics. For any allowed union of donor folds, the reference distribution is

`Q[j] = (C[j] + F * P_B2[j]) / N`.

E is a destination in C. Failure is not E and is not discarded. With no donors, use the existing B2 rule. Preserve the original numeric reconstruction order after integer aggregation. The final fixed/adaptive mixture and its support formula are unchanged.

The estimator needs these exact counts; it does not require a separate GEOS call or stored outcome row for every pair. If a node represents 1,000 original donor pairs, and a proof establishes that all are valid and land in cell j, add **1,000**, not one. This is compression of arithmetic, not equal-ID reweighting or a representative-trajectory approximation.

## 4. Proposed exact algorithm

### 4.1 Build immutable donor trees once

Partition donors by `(horizon, original donor cell, donor outer fold)`. Each node therefore belongs to one fold and one permitted neighbour cell. Query/fit-role access selects only allowed trees; never aggregate a prohibited fold and later subtract only the query ID.

Store original source-key membership, raw multiplicity, distinct-ID bitsets, endpoint-displacement bounds and conservative relative-path bounds. Complete, continuous and valid source windows may enter the bulk-proof trees. Incomplete windows remain present and use G3: they cannot simply be marked failed, because a valid earlier exit may precede missing continuation.

Use a balanced deterministic binary tree with leaf capacity **64**. Compare only two layouts:

| Layout | Split features |
|---|---|
| BulkEndpointTree | Relative final longitude and latitude |
| BulkEnvelopeTree | The two endpoint features plus full-path relative x/y minima and maxima |

For each layout choose the feature with greatest finite span in the original degree units, split at the median, resolve feature ties in the listed order and record ties by source key. These are engineering layouts, unrelated to the scientific B1/B2 models. Do not tune scaling, leaf sizes or extra layouts in this trial.

Store both whole-window bounds and the original **32-hour block bounds**, including each block's starting vertex and the shorter final block (8 hours for day 7; 16 for day 30). Form node envelopes from every member's corresponding bounds. Stream leaf construction using the existing source/block arrays; do not materialise a donor-by-720-hour path tensor. Charge index construction and storage explicitly. Query-specific translated geometry is not cached across merely similar starts.

### 4.2 Prove validity for a group at the actual query location

For each node, translate its enclosing bounds using the query's unmodified coordinate. A group can be certified only if all its source windows are complete/valid, the conservative envelope is inside D, disjoint from both exact land masks, and entirely covered by registered states.

Try the whole-window envelope first. If inconclusive, try the 32-hour envelopes, in chronological order. Their union covers every hourly vertex and connecting segment. Successful block proofs can be inherited by child nodes. A failed block proof causes donor-tree descent, not a donor failure; test remaining blocks on smaller groups. At an unresolved leaf call the existing serial G3 rule on **every** member, preserving its hourly event ordering. Recompute from the start at such leaves initially; resuming partially checked G3 state is outside O2.

A successful group proof establishes no land event, no missing/invalid hour, no unindexed state and no exit before the horizon. O2 does not introduce a group-level early-exit or failure certificate, except the already established query-wide unsafe-start rule. Potential exits, land crossings and ambiguous numerical cases descend to G3. This keeps the new proof obligation narrow.

### 4.3 Count destinations without revisiting every safe donor

For a safe node, propagate its endpoint bounds through the **same** coordinate operations and cell mapping as the reference. If the entire conservative range maps to one destination cell, add the node count and ID bitset directly. If it straddles cell boundaries, descend the tree while inheriting the valid-path proof; do not repeat land checks. At a safe leaf whose endpoints still occupy multiple cells, compute the exact original endpoint expression for its at-most-64 members and accumulate their integer histogram.

Thus a safe group may contribute to multiple destination cells without assigning its members a common endpoint. Distinct real query starts remain distinct. Boundary cases cost more; they do not receive approximate outcomes.

Record a disjoint traversal cover: bulk-certified nodes plus individually classified leaf members must contain every eligible source key exactly once. Counts must sum to N in every donor fold. For audit queries, expand node decisions back to per-donor outcomes/reasons in original source order; this expansion is not timed as production geometry.

### 4.4 Floating-point and geometry proof conditions

This is an engineering proof obligation, not an assumption that real-number algebra preserves floating-point classification. Precompute donor-relative quantities using the same subtraction as the original. Propagate outward-enclosing bounds through addition, longitude normalisation and cell conversion; include representable-neighbour checks and the existing conservative certificate padding. Never reassociate `x0 + (end - start)` as `(x0 - start) + end`.

A modulo discontinuity, uncertain enclosure, nonfinite value or cell-edge ambiguity causes descent or exact leaf evaluation. Padding may make a shortcut fail; it must not change a trajectory, shoreline, cell boundary or event tolerance. Prove bound enclosure independently on synthetic adversarial floats and actual sampled members. Preserve polygon components, holes and both masks; a rectangle touching land is not certified safe.

### 4.5 Complexity and limitations

The desired cost is closer to `visited group nodes + exact ambiguous leaves + sparse output size` than to `all query-donor pairs`. In the worst case every node is ambiguous, and the method still has pair-scale work plus tree overhead. Similar endpoints do not guarantee similar paths, and nearshore paths can remain expensive. No subquadratic worst-case guarantee or 10x measured gain is claimed.

Measure separately: donors counted without individual endpoint evaluation; donors avoiding individual geometry; visited nodes; whole-window/block certificates; inherited block proofs; unresolved leaf pairs; literal hourly steps; index/setup cost and output expansion cost. A large certificate percentage alone is not a speed result.

Keep existing exact role/model sharing and bit-identical-coordinate reuse with full role lineage. Do not credit new gains for them. Cross-horizon outcome-prefix reuse, query-group/dual-tree algorithms, approximate raster/convolution methods, GPU rewrites and library upgrades are deferred from this bounded round.

## 5. Parallel safety and failure containment

O1's code shared prepared GEOS geometry and STRtrees through one kernel across two threads. Its native stacks are consistent with mutable prepared-intersector state documented in [GEOS issue 825](https://github.com/libgeos/geos/issues/825). The issue remains open; read-only NumPy arrays or a warm-up call do not establish prepared-object safety.

Use a serial reference first. If later testing two workers, use explicit **spawned processes**, each reconstructing its own geometry, prepared objects, component indexes, contexts and transient buffers. No GEOS object, pointer, prepared object or tree crosses the worker boundary. Python documents that [spawn starts a fresh interpreter and that fork is unsafe on macOS](https://docs.python.org/3.12/library/multiprocessing.html#contexts-and-start-methods). Do not rely on inherited native state or an implicit start-method default.

Only immutable numeric source/tree arrays may be shared through read-only file mappings. Each process opens its own mapping and installs the development-input guard before input access. Build source identities from content hashes, schema, environment, algorithm, geometry, donor fold/cell/horizon and source keys, not Python object addresses. Runtime owner tokens remain process-local.

A lightweight parent supervises workers, cumulative wall budget, access receipts and combined memory. Workers return keyed results, not mutable shared counters. The parent alone commits manifests and reduces counts in canonical order. Every completed serial query is atomically saved with outcomes, reason codes, source order and hashes **before** concurrency starts. For production-sized outputs, use bounded sparse chunks rather than a large file count or the full Cartesian product.

Write chunk data to a unique temporary file, flush, rename atomically, then commit its hash/receipt. Uncommitted chunks are not resumable evidence. Persist stage and access events while running, rather than only at normal interpreter exit. A child native crash must leave the parent alive to record its exit status and close the attempt. Termination/join must be bounded, with cleanup of owned mappings and child processes.

Synthetic fault injection checks supervisor survival and checkpoint rejection before real-data work. An unexpected real-data crash, mismatch, forbidden access or budget overrun stops the O2 attempt; no automatic restart or extra variant. A correctly completed two-process probe that is merely slower may select serial mode under the predeclared rule. That is not a crash recovery attempt.

## 6. Complete verification, in this order

### A. Synthetic correctness and supervisor checks before data execution

Retain the existing semantic suite and add tests for group proofs, incomplete windows, disjoint source coverage, integer multiplicity, ID-bitset unions, child proof inheritance, same-cell distinct query starts, translated grid-edge floats and wrapping, and all previously declared land/exit/missing-data precedence cases. A fixture whose envelope intersects land but whose paths are safe must descend and still succeed.

Verify arbitrary allowed donor-fold unions against direct member filtering, reject excluded-fold access before prediction, and confirm fit-only support medians. Test stale hashes, swapped source order, altered query hex coordinates, truncated chunks and intentional worker exit without losing previously committed output. These are meaningful semantic/ownership tests, not merely tests of private helper structure.

### B. Serial real-data parity, saved before concurrency

- Reuse and verify the eight sealed original reference arrays. Recompute G3 and both bulk layouts on those same full donor populations; save all optimized outputs before publishing parity/timing receipts.
- Retain the 50 other O1 roster queries. Obtain original-kernel parity on the four already frozen additional parity queries. This completes the original 12-query exhaustive reference obligation.
- Expand the frozen engineering roster for capacity coverage: add one predictor-only/source-key-selected query for each positive-work `(horizon, origin)` not represented in the existing roster. Select the eligible fold with greatest query-count times donor-count product, then its smallest source key, with ascending fold ties. Require unchanged B2 and neighbour support. Freeze source keys before timing or reading outcomes. The saved roster covers 15 of 74 horizon-origin pairs, so the proposed maximum is **117 queries** (58 + 59). Report unavailable roles rather than substituting convenient cases. The 17 indexed origins without evaluation times remain unmeasured.
- On every final-roster query, compare the frozen bulk winner against serial G3 using **all eligible donors** and persisted expanded destination/reason arrays. If G3 wins configuration selection, validate it and report that bulk acceleration failed to establish value; do not substitute a new layout.
- Complete at least **5,000 distinct independent scalar query-donor checks**, stratified across horizon, origin/coastal class, query fold, observed reasons and bulk-certified versus exact-leaf routes. Cover every observed reason, enforce at least 1,000 checks from bulk-certified nodes if that many exist, and report any unavailable category. Freeze the deterministic sampling rule/seed before execution; audit sampling never replaces a forecast donor population. Cap this audit at 10,000 combinations. Use literal chronological geometry, not the new certificates, as the oracle.
- Audit the new bounds independently, and compare per-fold destination/reason counts, denominator, support IDs, inner/outer unions, failed mass and Q. Require integer/ID identity; probabilities, Brier and floating score tables must agree within absolute 1e-12. Region membership, candidate pools, selections and statuses must agree exactly under the existing rules.

Per-donor expansion for audit does not need to be the production representation. Report its time separately so that both the real verification cost and the production savings are visible.

### C. Isolated parallel probe only after serial correctness passes

Use the same eight calibration queries, including coastal and 30-day cases, for three predeclared repetitions in each mode: one spawned worker and two spawned workers. Each worker owns its native geometry. Persist and compare every result to the serial artifacts; test cold startup as well as steady-state throughput. Freeze no further algorithm changes after serial validation.

Select two workers only if all repetitions preserve counts/outcomes and measured total throughput including worker setup, serialisation and commits improves by more than 5%, within combined memory limits. Otherwise retain one worker. Do not assume a factor of two or tune concurrency on Brier. The probe is evidence of correct isolation and observed stability, not proof that native software can never crash.

### D. Score, checkpoint and capacity checks

Complete the O1 real-data cached/original scorer and four-solver parity checks on both horizons. Verify analytic coefficients/gradient/selection arithmetic independently and compare full candidate memberships, H90/K90 and selected parameters, including rejected candidates. These small-roster selections are capacity checks only, not scientific model results.

Measure all six controls, fit-role setup, full-region scoring, 50,000-by-72 multiplier arithmetic, index construction, checkpoint write/read, cold reconstruction and audit costs. Synthetic multiplier values may measure capacity only and must not be labelled uncertainty results. Include support-size variation in region timing; do not extrapolate only the easiest distribution.

Perform one clean serial reconstruction of the trial's saved counts/probabilities and a cold rebuild on the eight calibration cases, without trusting cached output hashes alone. Full pipeline replays remain part of the later full experiment, subject to separate approval.

## 7. Bounded execution proposal

**New cumulative real-data cap: 7,200 seconds (two hours).** This is a fresh, explicitly reviewed budget, not reuse of the closed O1 balance. Include input verification, index construction, references, all finite benchmarks/repetitions, real-data audits, scoring and failed/interrupted execution. Code development and small synthetic tests are separate engineering time; two hours is not a development delivery promise.

| Stage | Cap | Output/gate |
|---|---:|---|
| A: guarded startup, reference restoration, index construction | 15 min | Immutable inputs/roles, bounded memory, durable supervisor |
| B: eight-query serial calibration, G3 and two layouts | 25 min | Saved exact parity, node/pair work and finite configuration choice |
| C: frozen expanded roster, full parity and scalar audit | 50 min | Complete correctness/coverage receipts before concurrency |
| D: one/two-process probe | 10 min | Stable output identity and measured worker selection |
| E: scorer/control/cost accounting and replay checks | 20 min | Whole-pipeline projection with explicit unknowns |

Do not silently transfer a stage overrun to another stage or extend the overall budget. A required stage that does not finish returns `CAPACITY_NOT_ESTABLISHED`; partial success remains useful but is not a completed verification. Offline report preparation from sealed outputs adds no real-data retry.

Compare only G3 (batch 2,048), BulkEndpointTree and BulkEnvelopeTree (leaf 64, block 32, exact fallback batch 2,048). Use the eight calibration queries only to choose the layout by projected workload-weighted serial cost including index construction. The frozen ranking statistic is `all-required-tree setup seconds + sum over horizon/coast strata of [saved full pair workload * (summed calibration query seconds / summed calibration donor counts)]`. Include native setup and contexts once; separate shared input loading from layout cost. Construct each required donor-cell/fold/horizon tree once, and never double-charge it for different query neighbours. This rough calibration statistic selects the engineering configuration only; the expanded roster supplies the later estimate. Within 5%, prefer G3, then BulkEndpointTree, then BulkEnvelopeTree. If either new layout mismatches, stop for diagnosis instead of choosing the other and hiding the failure.

The larger validation roster estimates coverage and cost; it must not choose another layout or change its parameters. Persist both cold totals and rates with amortisation assumptions. No local benchmark success justifies dropping a slow origin from the final population.

At most **two worker processes**, one numeric-library thread each, **8 GiB combined RSS** including the parent, and **20 GiB combined new artifacts**. Conservatively account for mappings shared by processes, preflight allocations, record sampled RSS plus per-process high-water evidence, and enforce the cap with a parent watchdog. Check disk capacity before construction. No paid/cloud job, GPU use or library upgrade is proposed.

## 8. Expected benefits and honest runtime projection

Measured O1 central geometry time is about 250.1 h; with one fresh geometry replay it is about 500.1 h. The slower sampled rates with a 2x reserve give 635.1/1,270.3 h. These estimates use only two calibration queries and one origin per horizon/coastal category; they are neither confidence intervals nor established complete runtimes.

The new algorithm targets a **further 10x serial geometry improvement over G3**, with 20x desirable for a multi-day complete run. These are engineering targets, not measured/predicted gains. Group separability and residual hard leaves have not been measured. Two processes alone cannot plausibly remove the present order-of-magnitude problem.

| Hypothetical net geometry gain over G3 | Central geometry plus fresh replay | Slower-rate/reserve geometry plus fresh replay |
|---|---:|---:|
| 5x | 100.0 h | 254.1 h |
| 10x | 50.0 h | 127.0 h |
| 20x | 25.0 h | 63.5 h |

This table is arithmetic sensitivity, not a forecast. It excludes scoring, controls, uncertainty, audit, index/startup and I/O. A 90% reduction in individual visits does not imply a 10x total gain: tree traversal, certificates, remaining hard paths and fixed costs still consume time. Do not divide this table by two before measuring process throughput.

The previous 72-hour envelope remains a planning reference, not a full-run approval. Even ignoring non-geometry work, it requires about **6.95x** improvement against the central replay estimate and **17.64x** against the reserved estimate. The actual requirement is higher once other work is counted. Do not choose a generous runtime claim merely to fit that envelope.

After the trial, project separately by horizon/origin using observed donor-node visits, ambiguous leaves, donor counts and output support. Report coverage and time variation, a central scenario and a slow-rate-plus-reserve scenario. A single query per added origin supplies capacity coverage, not a confident estimate of every within-cell geometry regime. Unmeasured costly regimes remain explicit uncertainty.

The complete estimate must include:

`primary index/setup + geometry/counts + fitting + candidate Brier/regions + controls + uncertainty + audits + checkpoint/report I/O + fresh geometry and scoring replays`.

Retain the upper workload of 721,080,360 query-candidate metric evaluations before exact sharing, 12 selection tasks, six controls and the frozen multiplier workload. Report CPU and wall time separately and include only measured parallel gains in affected components. A full estimate with major unmeasured components is unavailable, not zero. Do not claim capacity established merely because geometry fits a chosen budget.

## 9. Acceptance and handoff

| Decision | Requirement |
|---|---|
| Exact implementation | Complete declared saved parity, scalar/bound checks, role/mass/support checks and unchanged scoring/selection |
| Parallel correction verified | Process-local native ownership, durable parent receipts, completed repetition parity and memory/accounting checks |
| Substantial pair-work reduction | Bulk donor-count fractions and visited-node/leaf work demonstrate reduced enumeration on the frozen validation roster, especially 30-day offshore; report measured total gain |
| Capacity estimate usable | Both horizons/origin workload covered, missing cost stages completed, index/storage/serialisation/replay included, uncertainty and uncovered regimes disclosed |
| Full run worth proposing | Correctness passes and the conservative complete-cost estimate fits a separately proposed budget with a defensible scientific payoff |
| Not established | Any missing required verification, mismatch, crash, overrun, large unexplained estimate instability or material unknown cost |

Do not make a favourable Brier claim from this engineering trial. Scientific quality still depends on complete E5 held-out Brier/H90/K90 comparisons with the unchanged controls and uncertainty screen. Exact compression proves computational equivalence, not that displacement borrowing is physically appropriate or predictively better.

Deliver a new immutable O2 run/config/approval namespace, separate implementation modules, saved reference/optimized arrays and node-cover receipts, a semantic/parallel audit, English report and local HTML/plots. Visuals must distinguish pair visits avoided from speed, cold from warm cost, measured from extrapolated time, and certified groups from literal fallback. Preserve earlier run aliases unless a new O2-only deliverable is explicitly named.

**Review request:** approve or revise the two deterministic group-tree layouts with group time-block proofs, conservative exact leaf fallback, process isolation, expanded engineering roster, complete verification and the new two-hour trial. Approval would stop at the evidence/capacity report. The complete scientific experiment would still wait for the user's later review.
