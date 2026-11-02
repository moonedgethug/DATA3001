# Step 2 — E3 Equal-drifter Destination Estimation

**Version:** E3 v2, 30 October 2026. **Status: USER APPROVED — DEVELOPMENT, EXECUTION AND AUDIT AUTHORISED.**

The user confirmed E3 v2 on 30 October, including within-cell equal-drifter contributions, equal-cell aggregation and the unified evaluation design, and authorised independent development, execution and audit. An object is already located in an origin cell at a chosen prediction time; each historical drifter has one total contribution within that origin/horizon, while retaining its internal destination information. This approval locks the v2 specification below. Scientific closure remains subject to result review.

This document supersedes E3 v1's partial-shrinkage search and original pair-weighted primary evaluation. It is the single current E3 plan; its historical filename is retained to avoid competing plan files. [The research stage ledger](research_stage_ledger.md) records approved scope separately from proposed engineering details. S1/E1/E2 artifacts and conclusions remain historical evidence under their original definitions.

## 1. Purpose: Where Things End Up

**Application question:** given an object or hypothetical release already at a specified location/cell, where could it be after the requested elapsed time, and with what probabilities?

E3 serves that question by estimating complete destination distributions at **7 and 30 days**, rather than maximising hits alone or minimising the number of displayed cells. These are two separately estimated horizons, not evidence for every day between 7 and 30 or a daily propagation operator.

Current inputs are the origin's **1-degree cell** and horizon. An exact coordinate maps to its cell; E3 does not distinguish subcell starting positions, condition on start date, velocity, season, object type or future environment. A time origin may be any existing qualified hourly observation in the cell, not necessarily first entry, first passage or physical deployment.

Drifter trajectories provide a transport proxy. Applying this proxy to a new spill or drifting object assumes adequate similarity to the retained drifter population and initial conditions. E3 does not validate oil spreading/weathering, windage differences, beaching, or arbitrary new regions. Keep these application assumptions visible without adding those mechanisms to this experiment.

The existing **stopped-process** outcome is retained: a first observed exit from D within the horizon is E, including a later re-entry. Consequently, the output means destination inside D or prior exit from D, not the exact eventual location after exit. Missing follow-up is not an exit.

## 2. Scientific amendment and proposed decisions

**Research question:** for the newly confirmed equal-drifter, within-cell sampling target, does fully balancing historical drifter contributions improve held-out standard Brier relative to raw B2 and to a fairly retuned Fixed B2/B1 control?

| Element | E3 v2 |
|---|---|
| Confirmed prediction situation | Already in the cell; start at a qualified time, not first entry |
| Confirmed contribution principle | Each fitting drifter has one total vote per origin/horizon; retain its internal endpoint frequencies |
| New estimator | EqualID: average the within-cell destination distributions of fitting drifters |
| Gamma | Fixed at 1 in v1 notation; **no gamma search** |
| Reported models | Raw B2, EqualID, Fixed B2/B1 |
| Fixed control | Original raw B2/B1 bases; retune constant a on {0, 0.05, ..., 1} using the new primary score |
| Primary cell score | Average a drifter's scores over its eligible origins in that cell, then average drifters equally |
| Proposed cross-cell summary | Average evaluable origin-cell scores equally; no inferred deployment-frequency weighting |
| Region diagnostic | Unchanged 90% probability mass, with geographic cell count, issued mass and actual hits |
| Validation | Existing five outer / four inner whole-ID folds |
| Uncertainty proposal | 5,000 paired positive whole-ID multiplier resamples of fixed outer predictions |
| Current permission | Independent implementation, bounded execution and audit authorised |

The equal-cell summary and revised resampling method are approved as part of E3 v2. Cells need a summary rule because no deployment-frequency distribution has been specified. Equal cell weight makes the assessment location-balanced; it does not assert that real spills are uniformly distributed or cells have equal physical area.

This is a declared amendment to the former equal-pair estimand. It cannot be presented as an unchanged-task leaderboard. The Data Contract still governs data, qualification and boundary semantics; the approved target clarification and the eventual approved E3 specification govern this experiment's weighting amendment. Do not rewrite contract workbooks or historical records.

Scientifically, EqualID is a reweighted empirical estimator. It equals the full endpoint of v1's contribution shrinkage, but it is not a newly independent prior or a fully Bayesian model. E3 remains a bounded Step 2 investigation of probability reliability and sampling influence. It adds no spatial information or new endpoint support.

## 3. Population and weighting interpretation

For each origin i and horizon h, the intended empirical reference is:

1. Select a qualified historical drifter with equal probability among IDs represented in that cell/horizon.
2. Within that drifter, select one of its qualified hourly start times in that cell/horizon uniformly.
3. Observe its stopped destination at h.

Using every eligible origin with reciprocal within-ID count weights computes the average over this hypothetical random selection without discarding records. These repeated origins are not independent drifters.

"One drifter, one vote" is **conditional on origin and horizon**. An ID that visits several cells can inform several conditional distributions; it is not split into independent IDs. Whole-ID validation and resampling preserve that linkage. Equal votes do not mean equal probabilities for every distinct destination.

This definition retains the historical within-cell mixture of positions, times and motion for each ID. It neither makes start positions spatially uniform nor proves that the retained IDs represent every future object. Eligibility remains horizon-specific; different 7/30-day populations must be disclosed. No weights use which destination is popular, remote, favourable or rare.

The distinction between selecting a pooled observation and selecting a cluster followed by an observation is discussed in [Nevalainen, Datta and Oja, Remark 2](https://arxiv.org/html/1803.01175v1). That supports careful target definition; it does not establish that equal-ID weighting is optimal for these ocean data.

## 4. Frozen data, outcomes and access

Retain final cleaned release per-drifter-cleaned-20261017-v7, annual pooling, 1-degree states, qualified R-origin hourly pairs, direct 7/30-day horizons, existing R/D geometry and D-plus-E outcomes. Velocity remains unused. There is no trajectory deduplication, endpoint-presence counting, new eligibility threshold, first-entry selection, date feature, or removal of low-probability outcomes.

- English contract: docs/contract/data_contract_v1.0.xlsx; SHA256 6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446, verified during this revision.
- Qualified ID-level count asset: results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet.
- Whole-ID folds: results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv.
- Reverify E2's sealed qualification/inventory/geometry allowlist; do not regenerate pairs or read raw trajectories.
- Keep the 3,224 development IDs in the role/resampling inventory, including IDs without eligible pairs. The 517 final-test IDs remain locked.
- Preserve frozen S1 empirical_b2_20261029T121555_976173Z, E1 adaptive_b2_b1_20261030T044950_931787Z and E2 b2_b1_e2_20261030T060621_291294Z.

Raw integer counts are preserved. Fractional weights are new derived fields, never replacements for pair_count. Historical fitted predictions, selected parameters and scores are not training/tuning inputs; allowlisted regression access follows fresh computation and the outer freeze.

## 5. Estimators and fitting weights

All quantities are rebuilt within the current fitting-ID set T, origin i and horizon h. Suppress T and h below.

Let n_idj count qualified pairs from drifter d, origin i, to outcome j in D plus E. Define n_id=sum_j n_idj, I_i={d in T:n_id>0}, M_i=|I_i| and N_i=sum_d n_id.

### 5.1 EqualID: proposed primary estimator

For M_i>0, form each drifter's distribution r_idj=n_idj/n_id, then:

**P_EqualID(i,j) = (1/M_i) sum_{d in I_i} r_idj.**

A single hourly pair has fitting probability weight 1/(M_i*n_id). Every represented ID therefore contributes exactly 1/M_i of the row. An absent ID contributes neither a zero vector nor a denominator. Repeated visits by one ID remain within one origin/horizon contribution.

Equivalently, use unnormalised pair weight 1/n_id, then normalise the row by M_i. This is also the minimiser of within-cell ID-balanced empirical Brier: that risk is 1+sum_j p_j^2-2*sum_j P_EqualID(i,j)*p_j. This algebra connects the estimator to the proposed score; it is not a claim of held-out improvement.

Apply balancing to all physical outcomes, including E. Do not preserve E probability artificially or condition the map on staying inside D.

Properties to verify:

- Same strictly positive destination support as B2; no new endpoints and no discarded positive probabilities.
- Same positive-cell count and zero-true-probability indicator as B2 on identical held-out cases.
- Probability mass sums to one; Brier, E mass and 90% regions may change.
- If only one ID is present, all local counts are equal across IDs, or their internal distributions coincide, EqualID equals B2.
- Multiplying every count of one ID within a cell/horizon by a positive integer leaves EqualID unchanged, provided its internal distribution is unchanged. This is a synthetic weighting invariant, not permission to duplicate real data.

Example: A contributes (6,2), B contributes (0,2). B2=(0.6,0.4); EqualID=((0.75,0.25)+(0,1))/2=(0.375,0.625). Counts are retained, and neither endpoint is declared equiprobable merely because it occurred.

### 5.2 Raw B2 control

P_B2(i,j)=sum_d n_idj/N_i.

Its original fitting rule is deliberately unchanged. It tests the predictive consequence of pair weighting relative to full ID balancing. Renaming a reweighted estimator as the historical B2 baseline would erase this contrast.

### 5.3 Fixed B2/B1 control

Fit raw B1 from qualified fitting-ID R-origin pairs:

Q_B1(j)=sum_i sum_d n_idj / sum_i N_i.

P_Fixed(i,j;a)=(1-a)*P_B2(i,j)+a*Q_B1(j).

Search exactly a in {0,0.05,...,1}, separately for each horizon and selection role, using the new primary inner-validation Brier. One a is shared across supported origins. Ties within absolute 1e-12 choose the smallest a. Do not import historical selected a.

B1 and B2 retain their original count weights in this control. Reweighting B1 or mixing EqualID with B1 would introduce another mechanism; neither is included. Fairness means the same target, cases, selection objective, support mask and reporting for all procedures, not identical fitting rules.

### 5.4 Availability

All three models use the fitting B2 support mask. With N_i=0, issue no standard Brier or region score and no B1 fallback; report unsupported status/U bookkeeping. A supported forecast has U=0, nonnegative finite D-plus-E probabilities summing to one within absolute 1e-12.

Zero probability for an observed supported outcome is scored normally. Missing follow-up is not converted into E. Tiny positive probabilities are not clipped.

## 6. Primary evaluation: the same sampling rule on held-out IDs

Use evaluation-ID counts, separately from fitting counts, to construct evaluation weights. Never reuse training n_id or M_i as validation denominators.

For one horizon and a specified evaluation pool, each ID's predictions come from a fit excluding that whole ID. Let V_i^S be the IDs with eligible pairs at i and a supported forecast from their assigned fit. Define m_id as that ID's eligible evaluation-pair count at i and M_i^V=|V_i^S|.

For any pair metric z, calculate:

1. **Within ID/cell:** L_id(z)=sum_j [m_idj/m_id]*z(p_i from that ID's assigned fit,j).
2. **Within cell:** L_i(z)=sum_{d in V_i^S} L_id(z)/M_i^V.
3. **Across cells:** L(z)=sum_{i in C^S} L_i(z)/|C^S|, where C^S contains the fixed-index cells with at least one evaluable ID.

Thus an individual hourly case has primary weight **1/(|C^S|*M_i^V*m_id)**. The weight of a compressed ID-origin-destination row includes its multiplicity m_idj. This weight is identical across models and candidates.

Evaluation denominators use held-out eligibility/ID/cell membership, not predicted probabilities or favourable destinations. All models use the same cells, ID-cell units and masks. These weights define the target distribution; they do not fit a prediction using held-out outcomes.

Use this exact three-level aggregation for inner selection, outer performance, main Brier, H90, K90, issued region mass, true-probability diagnostics and applicable support diagnostics. A drifter with 100 eligible starts has the same within-cell total evaluation influence as one with 10.

**Pool ID-cell records before aggregation.** Do not average precomputed fold means or concatenate pair-weighted totals. Inner groups and outer groups have different supports and ID counts; averaging fold summaries can implement another target. Retain the assigned fit for each ID when pooling.

K90 is constant across the records receiving the same fitted row, but outer fits can produce different row sizes. Apply the same ID/cell weights rather than counting each fitted row once.

### Support accounting

The scored summary is conditional on supported cases, as in prior approved experiments. Report the complete 54-row origin index, eligible/evaluable/unsupported cells, distinct IDs, ID-cell units and raw pair counts for every horizon/role. Distinct-ID counts use unions and are not additive across cells.

For the eligibility-only cell set C^elig, report target-weighted availability:

A=(1/|C^elig|)*sum_i [M_i^supported/M_i^eligible].

Report raw pair availability too. A cell with no eligible evaluation ID has no estimated error; a cell with eligible IDs but no supported forecasts is unavailable, not successful. If C^S is empty, the score/selection fails. No model-specific exclusion or probability floor is allowed.

The macro score averages C^S, whereas availability describes C^elig; save both memberships and denominators explicitly. Scores from different horizons or selection pools need not describe identical populations. These limitations do not affect within-pool model comparability.

### Historical-pair secondary summary

On the **same new outer predictions**, also compute the original pair-weighted Brier/K90/H90 as a labelled secondary sensitivity view. It neither selects a nor changes the acceptance decision. It is not a second search or a fourth model.

If the two reporting populations disagree, report the reversal. Do not pick whichever metric makes EqualID look better. Old published scalars cannot be subtracted from new primary scores.

## 7. Score, region and application interpretation

Use standard unnormalised multiclass Brier:

**BS(p,y)=1+sum_{j in D plus E}p_j^2-2*p_y.**

No division by state count, geographic-distance penalty, linear/quadratic combination or new loss is introduced. Only the sampling/aggregation weights change.

Retain the common 90% region algorithm: sort positive D-plus-E probabilities; take the shortest prefix reaching 0.90 within mass tolerance 1e-12; include all positive cutoff ties within probability tolerance 1e-12. Do not use outcomes or geography to break ties.

- K90 counts geographic D cells; E is not a geographic cell.
- H90 is actual full-outcome region membership under the primary evaluation weights.
- Report issued mass, E membership, predicted/observed E and D-outcome conditional hits separately when exits occur.
- A nominal 90% region is not guaranteed to achieve 90% observed coverage. Including ties can issue more than 90% mass.
- Retain complete probability maps and empirical-zero cases. No smaller probability interval, tail deletion or D-only renormalisation is allowed.
- Cell count is a resolution-specific footprint, not area in square kilometres.

Brier is the primary prediction-quality criterion. Smaller K90 is helpful only in the context of probability quality and actual hits; equal-ID balancing is not expected or required to shrink every region.

## 8. Nested validation and fair control selection

Keep the existing five whole-ID outer groups. For outer group k, each remaining group l is inner validation; fit only IDs outside k and l. Recompute raw counts, local ID totals, EqualID, raw B2/B1 and support inside each fitting role.

For each horizon:

1. Score B2, EqualID and all 21 Fixed candidates on identical supported inner cases.
2. Pool the four inner groups at ID-cell level and compute Section 6's primary Brier.
3. Select Fixed's a by minimum primary Brier, tolerance 1e-12 then smaller a. B2 and EqualID have no selected parameter.
4. Refit bases on the four outer-training groups and evaluate all three models on outer k once.
5. Retain the prescribed procedures even if an outer result is unfavourable; no retrospective fallback, reweighting, gamma search or model winner selection.

The a=0 candidate equals B2, so the chosen Fixed inner score cannot exceed B2 beyond numerical tolerance. This does not guarantee better outer results.

Freeze/hash all outer predictions, masks, scores and selected a values before all-development tuning. Then use the five base outer fits as ordinary base out-of-fold predictions to select an illustrative all-development a by the same cell/ID score. Refit all three models on all development IDs. These later maps/tuning results are not independent evaluation and cannot alter the nested outer results.

There are **26 base fitting roles**: 20 inner, five outer, one all-development refit. Audit 25 candidate-evaluation roles, two horizons and 23 declared identities (B2, EqualID, 21 Fixed candidates): 1,150 role/horizon/identity evaluations. Equivalent a=0 forecasts may share computations but retain identities. Pooled selection summaries are additional derived tables.

This is a new isolated experiment on repeatedly examined development data, not an untouched validation set. Whole-ID nesting prevents direct within-fold fitting/selection leakage; it does not remove prior research adaptation. No final-test access is authorised.

## 9. Uncertainty proposal for the new macro score

A conventional whole-ID draw can omit every observed ID from a sparse cell. Silently dropping that cell would change the equal-cell target. To keep the same cell set in every resample, propose **positive whole-ID multiplier resampling**, replacing v1's multinomial ID bootstrap.

For each of 5,000 replicates, seed 20261030, generate one independent Exp(1) multiplier b_d per sorted development ID. Apply the same b_d to every occurrence of that ID across cells, horizons, metrics and models. Replace the within-cell ID mean by:

**L_i^b(z)=sum_d b_d*L_id(z)/sum_d b_d**, then average the original C^S cells equally.

Retain the original within-ID time means, fitted predictions, masks and cell membership. Do not resample hours or ID-cell units independently. Export the draw identity/hash and deterministic generator specification (NumPy Generator with PCG64); reject a nonpositive/nonfinite generated weight as an implementation fault. Empty base cells remain unavailable.

This is an application of positive weighted-bootstrap ideas; see [Præstgaard and Wellner (1993)](https://faculty.washington.edu/jonw/JAW-papers/jaw-praest-93AP.pdf). It is a proposal for conditional development uncertainty, not a newly fitted Bayesian transition model, posterior credible interval, or proof of finite-sample coverage. Positive weights preserve observed cells but cannot create independent evidence in a cell supported by only one ID.

Prespecify four Brier contrasts: EqualID minus B2 and EqualID minus Fixed, separately at 7/30 days. Report ordinary 95% percentile intervals for all three metrics and paired differences. For a conservative four-contrast Brier screen, report one-sided upper percentile bounds at 0.9875, using linear interpolation. Fixed minus B2 is descriptive context.

Keep selected fits fixed. Intervals omit retraining variability, overlapping training-set dependence and earlier research adaptation, and assume ID clusters are sufficiently independent for this approximation. Cross-ID shared ocean conditions are not modelled by ID resampling. Report per-cell ID counts and uncertainty limitations, especially sparse cells. No calibration or population non-inferiority claim follows from a non-significant difference.

## 10. Diagnostics and acceptance

Save per-origin/horizon raw N_i, distinct M_i, largest original ID share, each local n_id, r_id, old contribution n_id/N_i and new contribution 1/M_i. Explain where distributions changed without declaring long records erroneous.

Report primary and secondary summaries, per-origin/per-fold metrics, eligible/support denominators, zero-true-probability fractions, positive-cell counts, predicted/observed E, U/availability and Brier components mean(sum p_j^2) and mean(p_y). Grouped diagnostics must state their own denominators and never determine exclusions or selection.

Retain descriptive matched-budget curves at {1,5,10,20,50,100,200,500,1000,|D|}, using existing boundary-tie semantics and zero-tie flags; aggregate with the new weights. Reconcile changes in the 90% region and actual hits relative to both controls.

Select the illustration origin using the existing training-support rule: maximise the minimum all-development distinct-ID support across horizons, then smallest cell ID. Show complete distributions, matched colour scales per horizon, 90% outlines and E/U/support captions. Candidate maps are illustrative, not held-out skill evidence. No favourable-origin or favourable-horizon selection after seeing results.

For each horizon/reference, let delta B=EqualID primary Brier minus reference primary Brier; epsilon=1e-12.

| Outcome | Required interpretation |
|---|---|
| Engineering complete | All identity, weighting, support, role-isolation, audit, preservation and replay checks pass; scientific gains are not required |
| No measurable Brier gain | delta B >= -epsilon; distinguish equality from deterioration |
| Point-estimate improvement | delta B < -epsilon, but adjusted upper bound is not below -epsilon |
| Conditional development Brier support | delta B < -epsilon and adjusted upper bound < -epsilon; limited to the stated target, comparator and horizon |
| Exact equality | EqualID and B2 coincide; valid estimator identity, not a gain |

Always show delta K90 and delta H90 alongside delta B. A smaller region with worse Brier is not success under E3. Better Brier with reduced hits or a larger region is a disclosed application trade-off. Brier improvement plus non-worse hit/size point estimates is a descriptive joint benefit, not formal non-inferiority.

Beating B2 alone does not justify replacing Fixed. Improvement at 7 days does not imply improvement at 30 days. The number of small-probability cells is not an acceptance objective. No new hyperparameter search follows a null result. Retention, Step 2 closure and Step 3 entry remain user decisions.

## 11. Implementation after approval

Keep the existing historical E3 filename stem, but use explicit EqualID model labels and v2 weighting metadata. No E3 files below are created until approval.

| Planned path | Responsibility |
|---|---|
| src/data3001/modelling/baselines/drifter_shrinkage_e3.py | Per-ID distributions, fixed EqualID estimator, ID/cell aggregation, Fixed selection |
| src/data3001/modelling/baselines/run_drifter_shrinkage_e3.py | Exact config, guarded inputs, nested roles, outer freeze, bounded execution and exports |
| src/data3001/modelling/baselines/drifter_shrinkage_e3_audit.py | Independent count/vector/weight, score, selection and uncertainty reconstruction |
| src/data3001/modelling/baselines/drifter_shrinkage_e3_report.py | English report, contribution diagnostics and maps |
| configs/drifter_shrinkage_e3.json | Explicit v2 target, per-model fit weights, primary/secondary score rules and resampling definition |
| tests/test_modelling_drifter_shrinkage_e3.py | Scientific semantics and integration checks |
| docs/drifter_shrinkage_e3_results.md | One current results account, only after execution |

Reuse pure base estimators, qualification guards, geometry, fixed folds, region helpers and I/O conventions. The existing E1/E2 scorers pool pair counts; they must not silently act as E3's primary aggregator. Avoid changing old scorer defaults. Any truly shared extraction must preserve old APIs and pass relevant regression checks.

Use the existing environment and package layout. No notebook, dependency, compatibility implementation, new data tree or unnecessary worktree. Preserve uncommitted work. No automatic commit/push.

## 12. Required tests and independent audit

Before data-dependent selection, verify:

1. Hand-computed EqualID examples, row sums, one-ID/equal-count/identical-distribution cases and changed E mass.
2. Per-ID total weight exactly 1/M_i; raw multiplicities remain integers and are never overwritten.
3. Repeated visits aggregate per ID/origin/horizon; absent IDs do not enter denominators; no destination-presence deduplication.
4. Synthetic replication of all one-ID/cell counts leaves EqualID and its corresponding held-out ID mean unchanged, but may change raw B2.
5. Brier minimisation identity, positive-support equality and exact B2/EqualID zero-truth indicators, including held-out-only destinations.
6. Unequal cell, ID and hourly counts: explicit three-level score equals compressed weighted-row arithmetic. Swapping fold sizes cannot turn it into a mean of fold means.
7. Held-out ID-cell weights depend on evaluation eligibility, not fitting counts; fitting distributions use fitting IDs only.
8. A synthetic case where pair-weighted and new primary Brier select different Fixed a: the new selector chooses the primary optimum.
9. Common supported masks, target-weighted availability, completely unavailable cells, empty roles and raw/ID-cell/ID denominators.
10. Standard Brier, true-zero penalty, full 90% cutoff ties, E inclusion and unchanged matched-budget semantics.
11. Identical positive multiplier per ID across all cells/models/horizons; fixed cell set; explicit paired-ratio calculation; sparse-cell limitations and adjusted-bound classification.
12. Relevant S1/E1/E2 semantic, region and architecture regressions; no unrelated expensive pipelines.

Independently reconstruct all 26 fitting bases with alternative counters/explicit vectors. Recalculate all 1,150 declared validation identities, pool selection records at ID-cell level, and audit masks, a selections, per-origin/aggregate metrics, multiplier draws and classifications without calling the production selector/aggregator. Verify the all-development stage did not change the outer freeze.

Regression expectations must reflect the target amendment:

- Fresh raw B2 matrices and original-pair secondary metrics reproduce matching frozen S1 values.
- Fresh raw B1/B2 bases and Fixed forecasts at any matched a reproduce the historical formula. **Newly selected a, new primary scores and the resulting selected Fixed forecasts need not reproduce E1/E2.**
- Historical parameters may be read only for post-freeze regression, never selected or preferred because of historical performance.
- Hash-check prior sealed artifacts unchanged. Verify no raw/final-test trajectory access.
- One fresh full replay reproduces every numerical table within absolute 1e-12; timestamps/run IDs/image encoding are excluded. Review rendered figures. Tests establish implementation correctness, not predictive success.

## 13. Deliverables, budget and review gate

After approval, create unique drifter_shrinkage_e3_<UTC_run_id> directories under results/runs/ and provenance/runs/; refuse overwrite. Use a separate preflight namespace. Deliver:

- Approved plan/config snapshots, target identifier, before/after definition table, input/source/environment hashes and read guards.
- Raw ID counts, B2/B1/EqualID matrices, training contributions, held-out ID-cell means, explicit score weights, cell memberships and availability.
- Fixed candidate/selection tables, frozen outer forecasts, all-development candidates, primary/secondary summaries and paired uncertainty.
- English REPORT.md, review.html, complete-distribution maps and diagnostics; independent audit/replay receipts; concise Chinese findings for review.

After approval, allow one five-minute inner-role preflight at both horizons with all declared identities and independent checks. Cap each full primary/replay execution at 30 minutes; if projected cost exceeds the cap, review the plan rather than reducing checks or changing definitions. One primary run and one fresh replay, no GPU and no extra search. Approximate engineering/audit effort: 0.5–1 working day, not a runtime promise.

Stop for review on identity/leakage/mass/support/weighting failures, semantic regression mismatch, access denial or timeout. An unfavourable scientific result is reported, not treated as permission for more tuning.

**Approved execution boundary:** implement this locked v2 estimator/control design, equal-cell aggregation, matched inner/outer evaluation, ID-level uncertainty and acceptance rules as one bounded experiment. Report audited results for user review. This approval does not change old results, close Step 2, start Step 3, restart neighbour/MDN work, access final test or publish Git changes.
