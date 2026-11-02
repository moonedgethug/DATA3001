# Step 3 — E1 Local Spatial Borrowing

**Version:** S3 E1 v1, 30 October 2026.
**Status: USER APPROVED — INDEPENDENT DEVELOPMENT, PREPARATION, EXECUTION AND AUDIT AUTHORISED.**

The user confirmed the complete S3 E1 v1 plan, explicitly including grid-relative whole-path translation and probability-preserving B2 fallback, and authorised independent development, preparation, execution, audit and visual comparison. This is the first Step 3 benchmark comparison. Historical favourable results motivate the experiment but do not predetermine its outcome. The stopped Markov-neighbour run, final test and scientific closure remain outside this authorisation.

## 1. Research question and proposed decisions

**Where Things End Up:** for an object already in a specified 1-degree origin cell at a qualified prediction time, estimate its distribution after 7 or 30 days, with first observed exit from the transport domain represented by absorbing E.

**Primary question:** does borrowing nearby movement patterns improve the held-out destination distribution relative to Fixed B2/B1 under the current evaluation target?

**Mechanism comparison:** compare displacement-aligned borrowing with borrowing the same neighbourhood's original destinations. Nearby origins are hypothesised to share some motion statistics; proximity does not establish this assumption.

| Item | Proposed first-round decision |
|---|---|
| Primary spatial candidate | LocalDisplacement: deterministic grid-relative translation of neighbouring hourly paths, with explicit B2 fallback for unusable transfers |
| Spatial control | LocalEndpoint: neighbouring observed stopped destinations, without translation |
| Retained controls | Raw B2; Fixed B2/B1; support-adaptive B2/B1 |
| Neighbourhood | Exactly the eight adjacent 1-degree cells, excluding self; only existing R-origin qualified fitting pairs |
| Alignment | Translate the complete observed hourly path by the difference between the two cell centres in longitude and latitude |
| New boundary safeguard | Validate translated positions and intervening segments; do not accept an identified in-domain land crossing |
| Failed transfer | Preserve its weight by assigning it to the target cell's fitted B2 distribution; no rejection-resampling or renormalisation of surviving transfers |
| Spatial fusion | One constant borrowing parameter per horizon/fitting selection, shared across cells; no new adaptive spatial weight |
| Parameter grid | Exactly 0, 0.05, ..., 1 for each of the four tunable families |
| Training / evaluation | Retain raw pair-frequency training; use E3/E4 equal-ID-within-cell and equal-cell primary evaluation |
| Main outcome | Standard Brier; fixed nominal-90% cell count and observed coverage reported together |
| Interpretation | Separate engineering completion, predictive improvement, and quality-preserving concentration |

The user explicitly approved both the grid-relative alignment approximation and the B2 fallback rule. Neither was part of the old WGS84 endpoint-transfer experiment. All scientific definitions below are now locked for this experiment.

## 2. Frozen scope and information available at prediction

Retain cleaned release per-drifter-cleaned-20261017-v7, annual pooling, original qualified hourly pairs, the frozen R and D polygons, the frozen 1-degree state index, and direct 7/30-day estimates. Exact input coordinates identify a cell; they do not change predictions within that cell in this experiment.

Do not change pair qualification, source records, drifter contributions, the prediction target, grid size, region, or evaluation population. No first-entry restriction, seasons, environmental fields, current velocity predictor, hidden state, daily propagation, new physical diffusivity, probability sharpening, or tail truncation is included.

The historical drifter population is a transport proxy. Results do not establish oil weathering, object-specific windage, beaching, or predictions at untested horizons.

B2 already uses origin cell. The new mechanism is sharing information according to the relationship between origin cells. This remains a regularised transition estimator; the research stages are experimental distinctions, not disjoint mathematical model classes.

## 3. Inputs, provenance and historical evidence

Authoritative contract: docs/contract/data_contract_v1.0.xlsx; expected SHA256:
6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446.

Reuse:

- Qualified stopped counts: results/runs/markov_input_20261025T095949_830292Z/release_counts_by_id.parquet.
- Source-keyed eligibility and exit labels: the same run's release_labels directory.
- Whole-ID folds: results/runs/markov_m1_1d_20261025T100248_328450Z/folds.csv.
- Manifest, frozen R/D geometry, state index, and pinned high/intermediate GSHHG land masks through the current asset registry.
- E4/E3 outputs only for post-freeze regression of freshly computed B2 and Fixed controls.

The current count cache has no hourly coordinates. The old neighbourhood cache stores starts and endpoints, not complete paths, and was prepared for endpoint occupancy. It cannot establish translated first-exit outcomes. Do not reuse its eligibility roster, fitted kernels, or selected weights.

**Approved preparation permission:** read only manifest-verified development tracks referenced by qualified R-origin labels, and the existing qualification sidecars required to interpret source records. Extract source ID, source observation key, UTC time, longitude, latitude and the existing validity flags. No new data cleaning or qualification decision is permitted. Do not open the 517 final-test trajectories.

Store a minimal, source-keyed coordinate/path view for the union of required windows; do not duplicate a complete 720-hour sequence for every overlapping start. Verify track hashes against the manifest and before/after reads. Fitting processes subsequently read only the sealed prepared view and counts.

Data-only preparation may cover development IDs once. It must remain ID-separable: a fitting role can aggregate only its fitting IDs. Held-out trajectories supply labels for scoring, never donors, reference distributions, support scales, or selected parameters.

Integrity expectations from E4, to reverify rather than force:

| Horizon | Qualified pairs | Distinct evaluation IDs | ID-cell units | Evaluated cells |
|---|---:|---:|---:|---:|
| 7 days | 303,288 | 385 | 4,451 | 37 |
| 30 days | 268,998 | 337 | 3,974 | 37 |

Retain all 54 indexed origins in support reporting. The other cells do not acquire measured predictive performance by being present in the index.

Historical Local-U/Local-A results remain evidence under their own endpoint target and pair-weighted evaluation. Local-U meant unaligned, not unresolved. New names avoid that ambiguity. The stopped M1-neighbour calculation is a different experiment and remains stopped.

## 4. Neighbourhood and donor weighting

For target cell i, take cells whose integer longitude/latitude grid-index offsets are in {-1, 0, 1} squared, excluding (0, 0). Use the frozen cell-index convention, including longitude wrapping and valid latitude bounds.

Intersect this geometric set with the existing origin index. A donor record must:

1. Belong to a fitting ID for the current role.
2. Start at an actual permitted R location in a neighbouring cell.
3. Be qualified by the frozen stopped ledger for the same horizon.

No D-wide donors, second ring, radius search, expanded R buffer, same-cell donors in the neighbour reference, or choice based on validation destinations is allowed.

Pool all donor pairs with their original multiplicities. Each eligible hourly donor pair has one contribution. Do not first normalise each neighbouring cell to equal weight or balance donor IDs. A neighbour with more qualified records therefore contributes more; this limitation remains explicit.

The same source pair may inform several target cells, but this creates no new observation or independent ID. Report distinct donor-ID unions, donor cell counts, pair counts, largest-ID contribution, and overlap between local and neighbour ID sets.

If target B2 is supported but the neighbourhood has no fitting donor pairs, set both local references equal to that target B2 row. This preserves the comparison population without expanding the neighbourhood.

## 5. Deterministic grid-relative displacement alignment

For donor origin cell k and target cell i, define the one-cell translation:

Delta_lon = centre_lon(i) - centre_lon(k)

Delta_lat = centre_lat(i) - centre_lat(k).

Use the local wrapped longitude difference. For each observed donor path point at elapsed hour s, transform:

lon'(s) = normalise_lon(lon(s) + Delta_lon)

lat'(s) = lat(s) + Delta_lat.

Transform the complete required path, including its start, not only the destination. A donor starting 20% across and 70% up its cell starts at the corresponding relative position in the target cell. There is no collapse to the target centre, empirical-anchor Cartesian product, or conditioning on a held-out subcell position.

This preserves relative movement in the longitude-latitude grid and the temporal ordering of the hourly path. It does **not** exactly preserve WGS84 distance in kilometres or geodesic azimuth under a latitude shift. The tested hypothesis is local similarity of grid-relative motion, not an exact physical transport symmetry. The transferred subcell release distribution is inherited from neighbouring origins, not the local empirical anchor distribution.

This bounded first-round approximation is chosen to make all donor contributions deterministic and auditable. It differs from the historical WGS84 net-displacement/empirical-anchor integral. Do not switch between these definitions during implementation. A later geodesic-anchor comparison would be a separate proposal.

Compute and report descriptive WGS84 net-distance and azimuth changes induced by the fixed translation on resolved in-domain transfers; do not use them to select donors, thresholds, or the winning model. Zero-distance cases have no directional angle and must be counted separately. No distance-distortion cutoff is tuned.

Because the shift has only eight possible values, preparation can transform each required source track portion once per offset and use event/range indexes to classify overlapping windows. This is an optimisation of the exact rule, not a subsampling scheme.

## 6. Transferred-path validity, land and absorbing exit

The observed evaluation labels remain untouched. The following rules classify synthetic borrowed paths only.

### 6.1 Initial point and geometry

The transferred start must map to target cell i, lie in R and D under the frozen membership conventions, and be unambiguously water. An invalid start returns that donor's contribution to B2.

Use the pinned high and intermediate shoreline masks conservatively: land indicated by either mask, or disagreement/uncertain mapping, cannot certify a transferable water path. Record land and mask-disagreement reasons separately. Boundary contacts count as unsafe for transfer. These are model guards, not new observed beaching labels.

### 6.2 Hourly ordering and segment guard

Inspect consecutive hourly timestamps from the transferred start toward h. No temporal interpolation fills a missing hour. Missing, nonfinite or unusable source positions before a decisive transferred exit make the transfer unresolved by this borrowing rule.

For each consecutive observed pair, use a straight segment in the same unwrapped longitude-latitude representation as the translation. Test its portion within D against the pinned land masks. A land intersection or ambiguous in-domain geometry triggers fallback before accepting that interval's endpoint. This is a conservative guard on the piecewise-linear representation, not proof that the real subhourly trajectory followed that line.

An outside-D observation is E only after all earlier required points and guarded segments are usable. At the first such hourly observation, assign all of this donor's contribution to E and stop. Later re-entry, missing follow-up, or land outside D does not reverse that recorded exit.

Do not create E merely because an interpolated segment briefly leaves and returns to D between two in-domain hourly observations. The target remains first **observed** exit. Segment checks guard land crossings, not continuous-time exit estimation.

If no exit is observed and the complete transferred hourly path is usable through h, assign the contribution to the frozen cell containing the transferred endpoint. A within-D endpoint absent from the frozen state index is a failed transfer, not a new state.

### 6.3 Original donor exits and incomplete continuation

Do not blindly copy the original donor's E label into LocalDisplacement: translation can change domain crossing. Recompute the transferred event from available source-keyed coordinates.

An original qualified E donor may legitimately have no usable continuation through h. If the transferred path has already reached a valid observed exit, E is sufficient. If it has not, and continuation is missing or unusable, return the contribution to B2. Do not exclude that donor, fabricate its continuation, or treat missingness as E.

By contrast, LocalEndpoint uses the original qualified stopped destination, including its observed E. An unexpected missing source key or corrupted coordinate before the original ledger's required interval is an integrity failure that stops preparation, not an ordinary fallback.

### 6.4 Probability-preserving fallback

For a supported target row, let v_i(j) be the fraction of all neighbour donor pairs successfully transferred to outcome j, including E. Let r_i be the fraction that cannot be transferred. The denominator includes **every** qualified neighbour pair.

sum_j v_i(j) + r_i = 1.

Define the complete LocalDisplacement reference:

Q_D(i,j) = v_i(j) + r_i * P_B2(i,j).

Thus an unusable donor contributes its original weight to the target's fitted B2 distribution. It is not removed, redistributed over successful donors, snapped to nearby water, resampled, or called a physical exit or grounding.

This is an explicit predictive fallback assumption. It resolves an algorithmic proposal by choosing B2; it does not establish that the failed path physically ended according to B2. Report r_i and its causes prominently. Supported final forecasts have no unresolved mass because they issue this declared complete fallback forecast, not because unresolved probability was silently discarded.

For a mixture weight a, actual successful spatial contribution is a*(1-r_i), and total B2 contribution is 1-a+a*r_i. Save both alongside nominal a. If no donors exist, r_i=1 and the reference is B2.

LocalEndpoint does not need translated-path validity: it uses observed stopped destinations. Therefore a LocalDisplacement versus LocalEndpoint difference concerns **alignment plus the declared geometry safeguard**, not a pure causal estimate of alignment alone. Do not claim otherwise or add a post-hoc ablation.

### 6.5 Completely unsupported target rows

All five models retain the same raw-B2 support mask. If target N_i=0, issue no standard Brier/region score for any model and report unsupported counts, fractions and bookkeeping U. No neighbour-only or global-only rescue is included in this first round.

## 7. Models and finite parameter space

For each horizon and fitting role, construct from fitting IDs only:

- P_B2(i,j) = N_ij / N_i.
- Q_G(j) = sum_i N_ij / sum_i N_i, including the target origin in global B1.
- Q_E(i,j): raw observed stopped outcome frequencies among neighbour donor pairs, or B2 if no donors.
- Q_D(i,j): the guarded displacement reference defined above.

The five reported models are:

| Model | Forecast on a supported row |
|---|---|
| B2 | P_B2 |
| Fixed | (1-a)*P_B2 + a*Q_G |
| Adaptive | (1-lambda_i)*P_B2 + lambda_i*Q_G |
| LocalEndpoint | (1-a)*P_B2 + a*Q_E |
| LocalDisplacement | (1-a)*P_B2 + a*Q_D |

For Adaptive, lambda_i = m*a / ((1-a)*N_i + m*a), where m is the median positive fitting row count at that horizon. Preserve explicit endpoints a=0 -> B2 and a=1 -> Q_G on supported rows.

Each tunable family independently selects a from exactly A={0,0.05,...,1}, separately at 7 and 30 days. For Fixed and the two spatial families, selected a is shared across supported target cells. Adaptive alone varies the applied weight by local pair count.

Select by the lowest inner primary Brier; ties within absolute 1e-12 prefer smaller a. No individual-cell parameter, hard support cutoff, stronger support exponent, donor-radius parameter, distance weighting, simultaneous B1-plus-neighbour mixture, or outer-result retuning is included.

The spatial search contains B2 at a=0; it does not contain general Fixed B1 as a fallback candidate. A spatial model that loses to Fixed remains a negative result. Do not add a post-result switch to Fixed and score it as if prospectively selected.

These are frequency estimates and finite parameter searches, with no gradient optimiser, epochs, neural training or fitted spatial loss.

## 8. Unified evaluation and validation isolation

Keep E3/E4's evaluation target:

1. Average each metric over eligible times within each held-out ID and origin cell.
2. Average ID means equally within that cell.
3. Average cell means equally over the common evaluable cells.

If an evaluation cell has M_i IDs and an ID has m_id eligible pairs there, each pair's weight is 1/(|C|*M_i*m_id). Apply exactly the same weights to all five models, all candidates and all main metrics. For compressed rows, multiply by the integer pair multiplicity.

Raw pair-frequency fitting remains deliberate. Do not reintroduce EqualID/PartialID training or mistake this evaluation population for the fitting weights.

Use the existing five outer whole-ID folds and four inner groups:

1. Exclude outer k in full.
2. For each inner l, construct every base and support quantity from IDs excluding k and l.
3. Score all 85 candidate identities per horizon: B2 plus four families times 21 a values.
4. Pool inner ID-cell records before the equal-ID/equal-cell aggregate and select each family's a.
5. Refit on the four outer-training groups and score all five models on outer k.

There are 26 fitting roles: 20 inner, five outer and one all-development refit. The 25 validation roles contain 4,250 candidate identity/horizon evaluations. Equivalent numerical predictions may be cached but their declared identities remain in audit tables.

Every reference, spatial count, fallback fraction and support median must be recomputed from fitting contributions. A geometry transform may be cached per ID independently; aggregating held-out donor contributions into a fitting reference is forbidden.

Freeze and hash outer predictions, masks, selections, weights and score records before all-development selection. All-development illustrative fits select a using the five base outer out-of-fold groups, then refit; their maps are not independent evaluation.

Rebuild B2 and Fixed under this target and reproduce the corresponding E3/E4 controls. Adaptive is newly selected under the same target: its old E1 scores and selected a are not expected to reproduce. The complete development-ID inventory, qualification and fold roles remain fixed.

Report original pair-weighted metrics as secondary sensitivity summaries of these same forecasts. They do not select parameters or determine success.

## 9. Metrics, uncertainty and acceptance

Standard multiclass Brier remains:

BS(p,y) = 1 + sum_{j in D plus E} p_j^2 - 2*p_y.

Do not add spatial distance, linear/quadratic loss or a failure-penalty term to supported complete forecasts. A zero-probability truth receives its ordinary Brier; it is not excluded.

For the 90% region, preserve the existing shortest descending-probability prefix, include cutoff ties under the existing 1e-12 rule, and keep all forecast probabilities outside the displayed region. E counts toward mass and outcome coverage, but is not a geographic cell.

Report:

- Brier, K90 (geographic cells), H90 (actual stopped-outcome coverage), issued region mass and E inclusion.
- Predicted/observed E, true-outcome zero-probability rate, positive-probability cells and unsupported-case availability.
- Nominal and effective borrowing weights, no-donor and failed-transfer fractions, causes, local/neighbour ID support.
- Per-cell, support-stratum and boundary-stratum results; these are descriptive, not new parameter-selection targets.

Primary contrasts: LocalDisplacement minus Fixed, separately at 7 and 30 days. LocalDisplacement minus LocalEndpoint is the prespecified mechanism comparison. Comparisons with B2/Adaptive and LocalEndpoint minus Fixed remain visible but descriptive.

Use 5,000 paired positive whole-ID multiplier replicates, seed 20261030, PCG64 Exp(1) weights over sorted development IDs, shared across all cells, horizons and models. Hold fitted predictions and within-ID metric means fixed; reweight IDs inside each cell and retain equal cell weighting. Save draw identity/hash, undefined counts and ordinary 95% intervals using linear quantiles.

For the primary quality screen, predeclare six directional comparisons: three metrics times two horizons. Use upper percentile 1-0.05/6 for Delta Brier and Delta K90, and lower percentile 0.05/6 for Delta H90. This is a conservative conditional development screen, not a final-test non-inferiority guarantee. Mechanism/other comparisons use descriptive 95% intervals without an additional formal superiority claim.

With epsilon=1e-12 as arithmetic tolerance only:

| Decision | Rule and interpretation |
|---|---|
| Engineering complete | Source identity, semantics, common-case scoring, independent audit, figures and deterministic replay pass; predictive improvement is not required |
| Point Brier improvement | Delta Brier < -epsilon |
| Conditional Brier support over Fixed | Point improvement and adjusted upper Delta Brier bound < -epsilon |
| Descriptive quality-preserving result | Point Brier improves, Delta H90 >= -epsilon, Delta K90 <= epsilon |
| Conditional quality-preserving upgrade candidate | Brier criterion above; adjusted lower Delta H90 bound >= -epsilon; adjusted upper Delta K90 bound <= epsilon |
| Conditional smaller region | Quality screen passes and adjusted upper Delta K90 bound < -epsilon |
| Trade-off | Brier improves but H90 falls or K90 expands; quantify and submit for review rather than declaring an overall win |
| Inconclusive | Bounds fail the declared screen; a nonsignificant difference is not evidence of non-deterioration |
| No spatial mechanism selected | Selected a=0 or effective borrowing=0 on all evaluated rows; do not label an identical baseline as a spatial success |

No allowable scientific coverage loss is introduced: the proposed margin is zero. No minimum meaningful Brier gain has been invented; report effect sizes as well as screens and leave retention to user review. Passing at one horizon does not pass the other.

The multiplier intervals condition on saved fits and omit refitting, shared-training dependence, prior research adaptation and common ocean forcing across IDs. Even a screen-passing result is development evidence. Engineering completion, scientific retention and stage closure are separate decisions.

## 10. Independent audits and targeted tests

Before fitting, test:

- Eight-neighbour indexing, exclusion of self, R-only actual donor starts, horizon and ID-role isolation.
- A hand-worked coordinate translation; identity at zero shift; preserved subcell offset and grid increments; no centre snapping or geodesic claim.
- Complete in-domain path, shifted exit then return, source E becoming unresolved after transfer, translated land before exit, land after resolved exit, mask disagreement, segment land crossing, missing timestamp, and endpoint without an indexed state.
- Event precedence and no endpoint-only inference of stopped outcomes.
- Probability conservation for valid, failed and mixed donor contributions; no renormalisation; no-donor Q=B2; target unsupported for all models.
- Alpha endpoints and ties; Adaptive endpoint/median/monotonicity; effective borrowing equals a*(1-r).
- E3 evaluation weights, pooled ID-cell aggregation, regions/ties/E accounting and unchanged denominators.
- Small explicit per-window event loops versus the optimised prefix/range implementation.

After fitting, independently reconstruct transferred outcomes on small complete fixtures and a deterministic real sample, rebuild ID/origin counts and all selected matrices, verify probabilities and all score/region summaries, reproduce parameter selection and multiplier draws, and compare controls only after predictions are frozen.

The real audit sample is fixed by source keys/support before looking at model improvements and must include every transfer outcome/reason present. Verify source/output hashes and inaccessible final-test boundaries. Do not accept a model solely because structural tests pass.

## 11. Bounded execution after approval

No runtime performance has been measured for this proposed method. The following are stop limits, not promised durations.

- Use CPU only, at most two workers, 8 GiB resident-memory limit and 5 GiB of new derived artifacts.
- A preparation/resource pilot is capped at five minutes. Choose cases by fitting support and geometry complexity from the first inner fitting role, never by validation improvement. Cover all eight offsets and both horizons.
- Project full coordinate/event preparation cost from the pilot. Do not begin if the estimated preparation exceeds 30 minutes, peak memory exceeds the cap, or projected artifacts exceed the cap.
- Cap complete preparation at 30 minutes and a full CV/evaluation/audit run at 30 minutes. A fresh deterministic replay has the same limits. Do not continue hours of unbounded calculation.
- Stop and report if the cap is exceeded or semantics cannot be preserved. Do not silently shorten paths, reduce the folds, sample donors, thin hourly pairs, switch alignment methods, change the grid, or resume the old stopped computation.

Preprocessing uses source-keyed unique observations and repeated-offset event indexes. No particle or donor-anchor Monte Carlo error enters the proposed forecast. Roundoff tolerances remain 1e-12; an independent replay must reproduce numerical tables within that tolerance.

## 12. Deliverables and workspace organisation

Create only one current English engineering plan at this path. Future approved implementation is proposed under the existing baselines package:

| Planned file | Responsibility |
|---|---|
| spatial_borrowing_s3_e1.py | Five model definitions, neighbour aggregation, fallback and candidate interfaces |
| spatial_borrowing_s3_e1_inputs.py | Guarded source-key preparation, translated event records and sealed minimal path view |
| spatial_borrowing_s3_e1_audit.py | Independent scientific/count/selection/score checks |
| spatial_borrowing_s3_e1_report.py | English results, figures and review HTML |
| run_spatial_borrowing_s3_e1.py | Resource pilot, isolated roles, freezes, execution and replay |
| configs/spatial_borrowing_s3_e1.json | Approved choices, parameter grid, paths, geometry identities and resource caps |
| tests/test_modelling_spatial_borrowing_s3_e1*.py | Mathematical semantics, guards and comparison regression |
| docs/spatial_borrowing_s3_e1_results.md | One continuing scientific results account after execution |

Reuse audited B2/B1 and Adaptive estimators, prediction-region logic, E3 evaluation and multiplier utilities when semantics match. Do not import old run orchestration, copy an old scoring population, or refactor unrelated modules. Necessary shared extraction requires regression checks and must preserve old results.

Use new immutable preparation and experiment run IDs beginning spatial_borrowing_s3_e1. Save approved-plan/configuration snapshots, code/input hashes, ID roles, donor and fallback diagnostics, raw and effective weights, matrices, all candidate/selected scores, held-out predictions, uncertainty tables, replay receipts and an independent audit.

Human outputs:

- A five-model 7/30-day Brier/K90/H90 table and primary/secondary difference intervals.
- Matched candidate probability maps with a common scale and fixed 90% outlines.
- A donor-neighbour and path-transfer illustration, including rejected transfers and reasons.
- Actual hit/region-size comparisons and per-cell improvement maps with support/availability.
- Fallback and effective-borrowing plots so concentrated results cannot hide absent spatial contribution.

Select illustration cells from origins with positive all-development fitting support at both horizons. Define support as the minimum distinct local fitting-ID count over 7/30 days. Choose (1) the largest-support cell, ties by smallest cell ID; (2) the smallest-positive-support different cell, ties by smallest cell ID; and (3) a remaining cell whose grid polygon intersects the pinned high-resolution land mask, ordered by largest support then smallest cell ID. If a category is empty, report that it is unavailable; do not substitute a performance-selected case. Freeze this roster before inspecting model improvements. Explain that illustrations are all-development fits.

Preserve all existing uncommitted work, sealed runs, Step 2 results and the controlled stage ledger. After approval, add only the authorised stage entry and new artifact links. No Git commit/push or messages to other chats are included.

## 13. Evidence boundary and next gate

The gridded transfer and explicit fallback are proposed project choices, not methods established as superior by the literature. McAdam and van Sebille (2018), [Surface Connectivity and Interocean Exchanges From Drifter-Based Transition Matrices](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2017JC013363), documents sensitivity to gridding and spurious connections near transport/land barriers; this motivates testing spatial sharing and auditing boundaries rather than assuming nearby records are exchangeable.

At authorisation, only source/contract/schema review and this engineering plan had been completed. Subsequent implementation and results must be recorded in separate immutable runs and the scientific results document.

**Next gate:** user review of the audited five-model results, uncertainty and visualisations. Model retention, scientific stage closure and subsequent expansions require a new decision.
