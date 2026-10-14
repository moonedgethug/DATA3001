# DATA3001 Where Things End Up

# Data Contract and Analysis Method v1.0

Date: 2026-10-04. Status: implementation protocol.

The study uses the Southern Gulf Stream pilot and a reusable, season-aware probabilistic transport operator. This protocol fixes scientific definitions and the procedure for selecting empirical settings. It does not claim that formal hourly support, accuracy or a globally optimal model has already been demonstrated. Communication may be in Chinese; project artifacts are in English.

## Aspect-by-aspect decisions

### 01 Pilot Region (R)

**Decision.** Retain the Southern Gulf Stream pilot. R is the existing Gulf Stream Corridor polygon intersected with the window 30.0–35.5°N, 82–73°W. The rectangle alone is not R. Florida–Bahamas, the northern Gulf and the wider US East Coast remain later application regions.

**Explanation and evidence.** R defines permitted initial releases. The current choice follows the team's agreed pilot and preliminary six-hour screening. It is not proof of adequate hourly, seasonal or 365-day support. Preserve the corridor vertices from the existing screening definition rather than redraw an approximate map. [S01, S02; project decision]

**Implementation and acceptance.** Serialize R as GeoJSON, record coordinate order, CRS, inclusion of its polygon boundary and a checksum. Use point-in-polygon membership. Recompute all support on the frozen hourly snapshot. If support fails, document a versioned change before modelling rather than silently move R.

### 02 Transport Domain (D)

**Decision.** Choose D using development trajectories from R through day 365, including intermediate paths and downstream training support. Retrieve additional drifters that visit D even if they never visit R. Freeze D before final testing. Include an explicit outside state and an unresolved-support state.

**Explanation and evidence.** A release region is smaller than a transport domain. R-only training cannot estimate downstream rows after probability leaves R. Endpoint coverage alone misses exit and return. A finite historical domain cannot guarantee unrestricted one-year transport. [S01, S05–S07; project selection rule]

**Implementation and acceptance.** Compare nested development domains, outside mass, observed return mass, anchor maps and laptop cost. Expand D until maps stabilize or retain a clearly labelled stopped-domain product. Do not tune D using final-test endpoints. Record every candidate geometry, support map and boundary sensitivity.

### 03 Origin Sampling Rule

**Decision.** Use every QC-valid hourly location as a candidate origin for fixed-duration transitions. Estimate the main operator from equal-weight valid origin–endpoint pairs. First entry into R is a separate demonstration cohort. Cell-boundary entry is not required for a transition origin.

**Explanation and evidence.** The main estimator describes transitions from the within-cell locations and times actually sampled by GDP. First-entry-only sampling creates a boundary-conditioned target. Equal pairs are not independent evidence and do not represent a uniform release population. Weighting and thinning change the sampled target. [S06, S07; estimand decision]

**Implementation and acceptance.** Keep all candidates and their eligibility outcomes. Store cell, visit and drifter identifiers. Compare daily thinning and equal-drifter/visit weighting as separately labelled sensitivity analyses. Use whole-drifter inference. Never claim that AI labels remove serial dependence or sampling bias.

### 04 Forecast Horizons

**Decision.** Provide distributions for integer days 1–365. Validate 7, 30 and 365 days as mandatory primary horizons. Audit and evaluate 90 and 180 days as intermediate anchors where eligible endpoints exist. A year means exactly 365 × 24 hours.

**Explanation and evidence.** The uploaded project explicitly includes a week, a month and a year. One-year analysis must be attempted and reported even if precision is poor. Software output at every day does not prove accuracy at every day. Different horizons need their own eligible samples. [S01; project decision]

**Implementation and acceptance.** Generate separate horizon ledgers and direct endpoint references. Report independent drifter support and uncertainty at every anchor, including an explicit insufficiency finding if needed. Do not restrict short-horizon learning to 365-day survivors. Assess intermediate outputs as generated or validated, as appropriate.

### 05 Time Tolerance

**Decision.** Use exact target timestamps in the main hourly analysis. Run endpoint-match sensitivities at ±1, ±2 and ±3 hours. Use ±6 hours only as a gap diagnostic. A tolerance of 0.5 hour is relevant only if the selected source genuinely has sub-hour timestamps.

**Explanation and evidence.** Tolerance repairs endpoint matching; it does not increase spatial or temporal information. A regular hourly product usually offers no extra endpoint at a half-hour setting. A wider window changes the effective horizon and may add different cases. [S02, S03; engineering rule]

**Implementation and acceptance.** Select the closest QC-valid endpoint within the active window, breaking equal-distance ties toward the earlier time. Save signed time error and the matching rule. Compare tolerances on matched cases and disclose added cases separately. Use timestamp arithmetic, never fixed row-index offsets.

### 06 Grid Convention

**Decision.** Start with a longitude–latitude grid of 1°. Anchor it at 180°W, 90°S and use half-open intervals with longitude normalized to [−180°, 180°). Align the 0.5° refinement to the same origin. Keep physical cell areas and wet areas explicit.

**Explanation and evidence.** Coarse cells generally pool more evidence, but neither 1° nor 0.5° is automatically optimal. Refinement changes statistical support, coastal topology and categorical scores. Unequal area matters for density maps and release priors. [S05–S07, S10; project decision]

**Implementation and acceptance.** Freeze indexing and wet masks before model comparison. Compare resolutions on identical held-out origins and common outcome partitions. Refine only after the core runs successfully and development validation supports the added detail. Re-audit all cell-season-regime support after refinement.

### 07 Seasons and Time Conditioning

**Decision.** Build an annual baseline and DJF, MAM, JJA and SON departure-season operators using UTC. During propagation, advance the actual date and update the applicable operator. Compare unpooled seasons with shrinkage toward the corresponding annual regime model.

**Explanation and evidence.** Seasonal structure is a plausible, testable conditioning choice. Four separate samples can be sparse; retaining the starting season for a whole year is incorrect. An Indian Ocean seasonal precedent supports the architecture, not these exact Atlantic bins or an Atlantic effect size. [S07; project hypothesis]

**Implementation and acceptance.** Audit every season. Select one global shrinkage weight per regime/lag from 0, 0.25, 0.5, 0.75 and 1 using development validation. Record intervals crossing season boundaries. Monthly or sine/cosine day-of-year conditioning is a later challenger if four-season results justify it.

### 08 Drogue Rule

**Decision.** Use constant-regime trajectory intervals. The primary scenario uses drogued intervals as a near-15 m water-following proxy. Analyse undrogued intervals separately as a wind-slip-sensitive transport proxy. Keep a pooled historical-mixture baseline. Exclude unknown or switching intervals only from fixed-regime estimates.

**Explanation and evidence.** Fixed-regime interval analysis is defensible for a transport scenario. It does not assume that an actual drifter's future hardware status is known. Undrogued data are useful, but the two regimes are neither universal object labels nor proven physical bounds. [S02, S07, S13]

**Implementation and acceptance.** Decode loss dates and unknown conventions from frozen metadata. For endpoint occupancy require unchanged status through h; for the stopped target require it only through min(h, first observed exit). Later loss after exit does not invalidate that absorbing outcome. Keep switching tracks. Actual hardware-state forecasting is a different-target extension.

### 09 Domain Exit and Censoring

**Decision.** Separate observed outside-D motion, first exit, later re-entry, unknown disappearance, administrative immaturity and fixed-regime ineligibility. The minimal finite-domain operator has an absorbing first-exit state and predicts a stopped process. It must not be presented as unrestricted endpoint occupancy when return is possible.

**Explanation and evidence.** Instrument termination is not proof of physical exit or beaching. An absorbing state loses the ability to represent later return. Boundary handling therefore changes the target being predicted. Missing future labels are not an estimated transport destination. [S05, S08; target definition]

**Implementation and acceptance.** Keep endpoint-occupancy and first-exit ledgers distinct. A QC-valid hourly path through first exit makes later stopped labels outside, even after return or subsequent track termination. Missing hours before classification make that path unknown. This is first exit observed hourly, not exact inter-hour exit. Never renormalize away outside or unresolved mass.

### 10 Data Splits

**Decision.** Assign complete drifter IDs globally across R and D to approximately 70% train, 15% validation and 15% locked test. Use the same ID manifest for all horizons, regimes and models. Add chronological and spatial stress tests after the primary experiment.

**Explanation and evidence.** Observation-level random splitting leaks correlated segments of one trajectory. ID separation is necessary but does not remove shared deployment conditions. Ratios and seed are reproducibility choices, not scientifically optimal constants. Time and regional tests answer different generalization questions. [S11, S16]

**Implementation and acceptance.** Use seed 20261004 and a specified stable SHA-256 ID assignment. Save the manifest before tuning. If validation support is weak, use five grouped folds within the 85% development pool, keeping test IDs untouched. For temporal tests purge crossing labels through 365 days. Exclude entire IDs crossing a spatial holdout from training.

### 11 Valid Origin–Endpoint Pair

**Decision.** Define eligibility by origin, horizon, tolerance, scenario and target. Endpoint occupancy requires a valid matched endpoint and unchanged regime through h. For a stopped target, a complete QC-valid hourly path through min(h, first observed exit) suffices; after known exit, no h endpoint or later regime status is required.

**Explanation and evidence.** Endpoint eligibility differs from path-event eligibility. An endpoint pair may be valid despite an intervening gap, while first exit is then uncertain. Valid-30-day pairs are not universally a subset of valid-7-day pairs. Changing drogue is scenario ineligibility rather than bad data. [S02, S03; design rule]

**Implementation and acceptance.** Require every expected hourly position through the relevant stopping time for main first-exit/hitting labels. Gaps make path labels unresolved, although endpoint-only labels may remain valid. Known exit overrides later administrative immaturity for the stopped target. Reconcile outcomes and match cases across models. Never fill missing targets with the last location.

### 12 Retention and Weighting

**Decision.** Keep immutable source data and all cleaned hourly observations with flags. Use equal valid pairs for the main observed-origin estimator. Treat thinning, per-drifter, per-day and per-visit weights as alternative target definitions, not mandatory corrections to a universally wrong estimator.

**Explanation and evidence.** Long residence produces many records, which is consistent with occupancy sampling but differs from equal-release or equal-drifter sampling. Correlation affects uncertainty. Choosing weights merely because their score improves can silently change the research question. [S06, S07, S16; estimand decision]

**Implementation and acceptance.** Publish pair counts alongside unique IDs and dependence diagnostics. Describe the population represented by every sensitivity estimate. When comparing estimates with different priors, use an explicitly shared release/validation target or present results separately. Never equate rows with independent sample size.

### 13 Velocity, Direction and Dispersion

**Decision.** Use official hourly eastward/northward velocity for retrospective description and QC. Summarize vector distributions by cell, season and regime. Coordinate differences are a cross-check. Do not make velocity reconstruction or a stochastic velocity model a prerequisite for estimating endpoint transitions.

**Explanation and evidence.** A probability matrix can be estimated directly from paired positions. Mean velocity alone loses branch structure. Velocity covariance has units m²/s² and is not diffusivity in m²/s. An SDE needs a defensible temporal closure and, where relevant, spatial diffusivity terms. [S03, S14]

**Implementation and acceptance.** Store velocity units, uncertainty and gap flags. Use circular/vector treatment for direction. Flag extreme speeds rather than automatically remove fast-current observations. Build stochastic advection only as a justified challenger after estimating its memory and diffusivity assumptions.

### 14 Boundaries and Cell Visits

**Decision.** Assign cells at observed hourly timestamps. Define a visit as a maximal consecutive observed run in one cell, breaking at missing-time gaps or re-entry. Keep unsmoothed assignments as the main rule. Record boundary-adjacent reversals and uncertain crossing intervals.

**Explanation and evidence.** A cell entry time lies between the last observation in the previous cell and the first in the next. It is not automatically the latter timestamp or an exactly known crossing. Position uncertainty may create jitter, but real short reversals also occur. [S02, S03, S15; geometry rule]

**Implementation and acceptance.** Retain visit diagnostics without using them to force transition origins. Test a documented hysteresis rule only as sensitivity if jitter is material. Use a versioned GSHHG wet mask and check disconnected wet pieces inside cells. Do not discard a pair merely because its straight endpoint segment crosses land.

### 15 Model Families and Order

**Decision.** Core: annual and seasonal empirical transport operators, with direct 7/30/365-day conditional endpoint references. Compare persistence and destination climatology baselines. First optional challenger: a continuous-space probabilistic mixture-density network. Stochastic advection is a later diagnostic, not a compulsory parallel build.

**Explanation and evidence.** The core directly delivers the iterable operator required by the project. Published GDP work supports a probabilistic neural challenger but does not establish superiority for this seasonal pilot or laptop budget. A compulsory second simulation pipeline adds untested closure assumptions. [S01, S05–S07, S09]

**Implementation and acceptance.** Complete the interpretable core and common evaluation first. Admit MDN, environmental conditioning or ensembles only with held-out gain, calibrated uncertainty and feasible computation. Keep direct endpoint references separate from the short-lag propagation model. Report unsuccessful challengers without retuning against test outcomes.

### 16 Support and Quality Audit

**Decision.** Report support by cell × departure season × regime × horizon: candidate origins, unique IDs, visits, drifter-days, valid pairs, availability, destination diversity and dominant-ID share. Recompute formal counts from hourly data. Do not assert one universal minimum count or effective sample size.

**Explanation and evidence.** The number of independent trajectories, their diversity and endpoint availability matter more than nominal rows. Effective sample size depends on a particular statistic and dependence model. Preliminary six-hour counts and first-entry summaries cannot certify hourly seasonal rows. [S02, S05; audit decision]

**Implementation and acceptance.** Produce 1° and aligned 0.5° support maps. Count IDs uniquely within each reporting unit and disclose overlap across units. Report administrative versus other losses separately. Use held-out scores, cluster uncertainty and learning curves to identify supported versus unresolved states.

### 17 Evaluation and Acceptance

**Decision.** Use common-1° log loss and Brier score on identical cases for complete distributions. Preserve all incomplete outputs and zero-probability failures. For unresolved-support mass, report probability/loss bounds, failure coverage and an explicitly labelled algorithmic failure-penalized Brier score. Assess probability-region coverage and outside-state calibration.

**Explanation and evidence.** Raw log loss is not comparable across different category partitions. Calibration and concentration measure different properties. Omitting unseen destinations makes a model appear stronger than it is. Closer average positions are not enough to verify a probability distribution. [S10; evaluation decision]

**Implementation and acceptance.** Aggregate fine predictions to the common grid. Report paired whole-ID uncertainty. Do not renormalize unresolved mass. For observed j, log-loss bounds are −log(p_j + unresolved_mass) to −log(p_j). If all candidates have infinite raw loss, select by declared Brier/calibration fallback and report its trigger. Lock selection before the final test.

### 18 Object Scope and Significance

**Decision.** Deliver a reusable historical drifter-based transport prior relevant to pollution pathways, debris searches and rescue planning. Keep object type outside the validated core. Provide an extension interface for windage, buoyancy, immersion, shape, waves and weathering when supported by additional data.

**Explanation and evidence.** A transferable software interface is feasible. Universally accurate prediction of oil, containers and people from GDP alone is not established. Mass alone does not determine drift. Drogued and undrogued comparisons demonstrate regime sensitivity without proving object-specific equivalence. [S07, S13]

**Implementation and acceptance.** Label applications as motivations or illustrative scenarios. Distinguish ocean-cell occupancy, entering a coastal zone and confirmed beaching. Do not call the core an operational spill or rescue forecast. Object calibration and forcing would require a separate validated experiment.

### 19 Evidence and Decision Status

**Decision.** Freeze v1.0 as the implementation protocol. Distinguish verified source facts, fixed study rules, hypotheses and settings selected by the declared development procedure. The document replaces conflicting technical rules in the earlier audit workbook. It does not certify empirical accuracy or global optimality.

**Explanation and evidence.** Literature establishes precedents and known risks, not the best parameter values for unprocessed regional data. A finite audit cannot prove that no superior method exists. Fixing reproducible selection rules provides a defensible endpoint to planning. [S01–S16; evidence policy]

**Implementation and acceptance.** Keep the old workbook as history. Record selected values in a configuration manifest with data, geometry and split hashes. Version any target, eligibility, boundary or evaluation change before renewed testing. Proposal and README remain historical snapshots until a separate update.

### 20 Prediction Target and Release Prior

**Decision.** Estimate historical destination distributions conditional on origin cell, departure date/season, declared transport regime and usable observation intervals. A selected cell is the finest core release location. Its subcell prior follows eligible historical origins, not an exactly known point or a uniform area prior.

**Explanation and evidence.** A gridded conditional operator averages over locations and histories inside a cell. Calling it an exact-point forecast overstates its resolution. Complete-pair estimates also condition on observability; they do not identify outcomes for all missing or terminated trajectories. [S06, S07; target decision]

**Implementation and acceptance.** Every output carries target, regime, grid, prior, boundary semantics, snapshot and validation status. A whole-R release assigns unit total mass proportional to wet area across cells, while explicitly retaining the empirical within-cell prior. Exact-point or uniform-subcell prediction requires a separately evaluated model.

### 21 Snapshot and Provenance

**Decision.** Use the official NOAA GDP hourly product and its documented metadata as the core source. Freeze the exact accessed asset, release, time range and checksum. Documented v2.01.1 is a starting candidate, not an assumption that every live endpoint currently serves that release.

**Explanation and evidence.** Different releases, hourly versus six-hour products and revised live trajectories can produce different counts. The official page documents corrections and a v2.01 time span ending in 2022. Earlier project screening used a different six-hour snapshot. [S02–S04]

**Implementation and acceptance.** Save source URL/DOI, access date, version attributes, dataset cutoff, ID list, query, units, flags, checksums and software versions. If a server offers only mutable data, preserve retrieved immutable subsets and metadata. Cite the dataset and relevant processing papers.

### 22 Data Access and Laptop Storage

**Decision.** Use official ERDDAP or cloud access with lazy/chunked retrieval. Discover relevant IDs spatially, then retrieve full required trajectory intervals, not only rows inside R. Store cleaned/pair data in partitioned local files and operators in sparse form where beneficial.

**Explanation and evidence.** Spatially clipping a download to R discards precisely the future locations needed for Where Things End Up. A global hourly table need not be materialized in laptop memory. CloudDrift supports ragged trajectory subsetting, but does not replace source-version control. [S02, S12]

**Implementation and acceptance.** Profile a small download for memory, disk and runtime before expansion. Record chunking and retries. Keep raw data immutable and out of ordinary Git commits. Store manifests, methods and small figures in the repository. Retrieve downstream D training IDs, including IDs without an R visit.

### 23 QC, Missing Fields and Schema

**Decision.** Apply source-specific units, fill values and QC rules. Enforce unique drifter/time keys and sorted UTC timestamps. Retain source flags and derived flags separately. Missing SST alone does not invalidate an otherwise valid position pair for the core model.

**Explanation and evidence.** QC flag meanings vary by variable and product version. One universal rule such as dropping every nonzero flag would be unsupported. Hourly estimates are processed values and may span poor original sampling. Rapid motion and branch changes are not automatically data errors. [S02–S04]

**Implementation and acceptance.** Create a metadata dictionary before cleaning. Quarantine conflicting duplicate keys. Preserve uncertainty, location type, experiment, death and drogue metadata. Add jump, gap and geometry flags with recorded reasons. Log exclusions by rule, region, season and regime.

### 24 Lag and Memory Diagnostics

**Decision.** Prototype a one-day kernel and compare lags of 1, 3, 5 and 7 days on the 1° grid. These are engineering candidates. Select grid and lag jointly using direct-versus-composed distributions, held-out scores, boundary artifacts and memory diagnostics.

**Explanation and evidence.** Hourly input does not imply an hourly Markov operator is better. Coarse states may retain subcell position, incoming-direction and residence-time memory. Smaller lags can amplify numerical dispersion. A successful diagnostic at one short horizon does not prove one-year Markov validity. [S05, S07]

**Implementation and acceptance.** Compare direct 2τ/3τ kernels with calendar-aware composition and test retained history. If memory or long-horizon bias is material, test incoming-direction/state augmentation or a probabilistic continuous model before increasing complexity. Choose from development evidence and retain simpler settings when gains are unclear.

### 25 Exact-Duration Propagation

**Decision.** For horizon h and selected integer-day lag τ, propagate q full steps and one estimated remainder kernel r, where h = qτ + r and 0 ≤ r < τ. Advance UTC calendar time after every step. Estimate required remainder kernels from corresponding hourly position pairs.

**Explanation and evidence.** Repeated seven-day or thirty-day steps do not end exactly at 365 days. Remainder composition preserves elapsed time but may expose short-lag memory. Fractional matrix powers and a matrix logarithm do not automatically define a valid stochastic transport process. [S05; exact-time arithmetic]

**Implementation and acceptance.** Verify timestamps and nonnegative unit-sum probabilities. Compare direct and composed predictions at exact anchors and available remainder horizons. If a remainder is unsupported, return an unvalidated/unsupported label rather than round h. Do not interpret all generated daily outputs as individually validated.

### 26 Information and Annotation Rules

**Decision.** Use authoritative metadata and deterministic derived labels for cell, season, gaps, visits and regime. Keep retrospective variables distinct from variables available at forecast time. Origin SST conditioning is an optional tested extension. Do not use future observed SST or future drogue loss as an operational feature.

**Explanation and evidence.** Hourly velocity and temperature estimates can use information around the timestamp. This is acceptable for retrospective climatology but does not prove real-time causality. AI assistance cannot create missing physical measurements or reveal future labels. Spatial and seasonal kernels can encode multiple currents without naming each one. [S02–S04]

**Implementation and acceptance.** Maintain feature provenance and an availability-time field. Label AI suggestions as hypotheses until checked. Avoid conditioning only on complete-SST cases without an attrition audit. Future environmental forcing, if added, needs a separate forecast source and validation; never hold initial temperature fixed for a year by assumption.

### 27 Operator Estimation and Regularization

**Decision.** Count eligible origin–destination transitions and normalize rows. Compare raw annual/seasonal rows with declared seasonal pooling and weak regularization. Never invent a stationary self-loop for an unobserved row. Use an available annual same-regime fallback, otherwise transfer mass to unresolved support.

**Explanation and evidence.** Sparse rows and unseen destinations create unstable or zero probabilities. Pooling can reduce variance but may erase real structure. Positive smoothing can also introduce artificial pathways. Unsupported states are epistemic uncertainty, not an observed physical exit. [S05–S07, S10]

**Implementation and acceptance.** Validate annual-shrinkage weight and optional destination-prior mixing ε in {0, 0.0001, 0.001, 0.01}. Build the prior from training data, respect wet connectivity and report its mass separately. Keep raw zero-probability failures visible. Do not impose a nearest-neighbour restriction or a rigid current direction.

### 28 Uncertainty and Dependence

**Decision.** Use whole-drifter cluster resampling for transition estimation and paired validation/test score intervals. Start with 200 replicates for development and 500 for final summaries, checking stability across seeds. Add deployment/experiment or year-block sensitivity where group structure is available.

**Explanation and evidence.** Nearby hourly windows overlap and are correlated. Resampling individual rows creates falsely narrow intervals. Separate transport spread, parameter uncertainty, measurement/interpolation uncertainty and structural error. More bootstrap replicates cannot repair sparse independent support. [S03, S16; engineering defaults]

**Implementation and acceptance.** Cache per-ID sufficient transition counts for efficient resampling. Refit seasonal pooling within the resampling protocol or declare selected settings fixed. Report whether intervals include training-fit uncertainty, held-out sampling uncertainty or both. Use learning curves and sensitivity checks alongside intervals.

### 29 Regional Transfer and Adaptation

**Decision.** Expand in stages from R to supported adjacent Atlantic cells, then Florida–Bahamas/northern Gulf and the broader East Coast when data permit. Re-estimate supported local rows and evaluate any parameter-sharing model. A learned empirical row cannot be assumed accurate in an unobserved new cell.

**Explanation and evidence.** A portable modelling method differs from a numerically portable transition matrix. Sparse regions can share regularization or representations, but different branches, seasons and coast geometry require evidence. Complexity-first is not a demonstrated easier route. [S05, S09; project hypothesis]

**Implementation and acceptance.** Use contiguous spatial stress tests with complete-ID exclusions. Compare zero-local-data output, pooled fallback and locally adapted estimates on held-out new-region IDs. Plot learning curves at declared fractions of local development IDs. Keep unresolved regions visible and require common-horizon, common-target validation.

### 30 Whole-Region and Coastal Outputs

**Decision.** Deliver selected-cell release maps and a whole-R unit-mass release experiment, with occupancy, density, retention and export summaries. For external inflow into R, run a separately declared D-source experiment. Distinguish endpoint presence from ever entering a zone and first exit.

**Explanation and evidence.** The lecture asks where R gathers material and where it loses it. Releases only inside R cannot establish which external locations feed R. Probability mass per cell and probability density per wet area have different meanings. Nearshore occupancy is not confirmed beaching or damage. [S01, S07; output definition]

**Implementation and acceptance.** Choose illustrative cells using development support and branch structure, not attractive test results. Use shared map scales, wet-area definitions and visible outside/unresolved totals. Confirm probability sums, label release priors and publish the reusable operator, state index and propagation instructions.

### 31 Execution and Change Control

**Decision.** Begin formal work with the frozen source/metadata manifest and QC/support audit. Then build the 1° annual and seasonal core, exact-time evaluation and 365-day analysis. Add refinements only after the relevant development checks. All team members may overlap technically with clear review ownership.

**Explanation and evidence.** The contract fixes the question and method before model experimentation. Implementation evidence must replace planning claims. A failed gate is a result to diagnose, not permission to change targets or inspect the final test repeatedly. This controls scope within the course timeline. [S01; project governance]

**Implementation and acceptance.** The project team consists of Junxi Xiao, Han Wang, Ming Yue and Yi Cheng Zhang. Junxi coordinates target/configuration; Han Wang and Ming Yue implement and cross-check data/model work; Yi Cheng Zhang leads significance and text. The four members will agree the allocation of support maps, visualization and verification. Record issues, selected settings and deviations. Update the contract version when the estimand, splits, eligibility or domain semantics change.

## Implementation specification

### Prediction notation and limitations

The core quantity is a historical conditional destination distribution for a chosen cell, UTC departure time and transport regime. Its within-cell origin distribution is the distribution of eligible GDP observations. It is conditional on available, valid observation intervals. A fixed-regime scenario is a physical-proxy analysis, not a forecast of whether an instrument will lose its drogue. The sample of observed constant-regime 365-day intervals may be selective. Always report that selection and compare it with the pooled historical-mixture reference using explicitly different labels.

For row-vector probability p, propagation uses p_next = p P, with nonnegative entries and row sums equal to one including outside and unresolved-support states. In the minimal domain implementation, outside means the first observed exit from D, after which mass remains in the outside state. This is a stopped process. For unrestricted occupancy, a supported exterior representation or a sufficiently expanded domain is needed. Merely checking the last endpoint is insufficient to validate stopped-process labels.

Historical short-lag kernels may be informed by many drifters without long complete records. A composed annual distribution is therefore a model implication, not an empirical 365-day endpoint frequency. Compare it with direct 365-day evidence. Direct references and propagated forecasts must share the same scenario, origin cohort and boundary target in each scored comparison.

### Source and geometry manifests

Create an immutable source manifest with dataset DOI, asset URL, access timestamp, release attributes, temporal cutoff, coordinate/velocity units, calendars, variable-specific fill values and QC meanings, drogue conventions, death-code dictionary, retrieved ID list, query and file hashes. Save the source's original attributes alongside each retrieved subset. Freeze the corridor polygon from the existing screening code, its intersection R, candidate/selected D, grid origin and shoreline/wet-mask definition as machine-readable geometry with hashes. A missing convention is an input to resolve from metadata, not a value to invent.

The formal support report must replace six-hour screening values. It must state which product, dates, tolerance, origin population, regime and polygon produced each count. No single regional total substitutes for cell × season × regime × horizon support.

### Minimum data layers

1. Source observations and original metadata: immutable.
2. Cleaned observations: original identifiers and timestamps, latitude/longitude, u/v and their uncertainties where present, SST and flags, experiment, location type, official drogue/death metadata, source/QC/gap flags, cell and visit IDs, season and availability classification.
3. Candidate and pair ledger: origin identifier/time/location/cell/visit, horizon, target time, selected endpoint time/location/cell, signed matching error, origin and endpoint QC, scenario, interval regime/path status, administrative maturity, termination cause, observed exit/return status, eligibility outcome, weight and source/configuration hashes.
4. Operators: grid/state index, source row support, annual/seasonal/regime/lag, transition counts, probability rows, fallback/regularization contribution, outside/unresolved states, fitted settings and training-ID manifest.
5. Evaluation: immutable forecast-case IDs, observed target, full distribution or reproducible distribution reference, score, coverage, region area, selection/failure status, uncertainty procedure and model/configuration hashes.

Administrative immaturity means that the dataset cutoff occurs before the requested target time. It is different from a drifter terminating before a target that falls inside the dataset period. For an absorbing stopped target, a valid known exit already identifies all subsequent outside labels, even beyond track termination or the source cutoff. Evaluate QC, regime constancy and path completeness only through min(h, first observed exit). Without an exit, require every expected hourly position through h for the main stopped label; otherwise mark path classification unknown. Endpoint-only references can have a different, explicitly matched eligibility rule. The target is first exit observed on hourly timestamps, not a proven physical first exit between them. Origin counts should reconcile to mutually exclusive eligibility outcomes; additional flags may explain multiple issues. Unknown metadata are never guessed to mean undrogued, still drogued, stranded or outside.

### Frozen development settings

| Item | Protocol setting | Status |
|---|---|---|
| Core source | Official NOAA GDP hourly asset, actual version and cutoff recorded | Source selection fixed; exact asset pinned during collection |
| R | Existing corridor polygon intersected with 30.0–35.5°N, 82–73°W | Fixed geometry, serialize before use |
| Initial grid | 1°, globally anchored, half-open boundaries | Fixed core |
| Refinement | Aligned 0.5° | Conditional extension |
| Main endpoint tolerance | Exact timestamp | Fixed primary; sensitivity at ±1/2/3 h |
| Forecast output | Integer day 1 through 365 | Fixed duration range; generated is not validated |
| Primary validation | 7, 30, 365 days | Fixed; report insufficient support explicitly |
| Intermediate anchors | 90, 180 days | Required audit and evaluation when eligible labels exist |
| Seasons | DJF/MAM/JJA/SON, UTC departure time | Fixed baseline architecture |
| Lag candidates | 1, 3, 5, 7 days | Engineering search set, not proven optima |
| Seasonal annual-mixing weight | 0/0.25/0.5/0.75/1 | Selected on development data, common within regime/lag |
| Destination-prior mixing | 0/0.0001/0.001/0.01 | Optional development-selected regularization |
| Whole-ID split | Approximate 70/15/15 with seed 20261004 | Fixed primary assignment procedure |
| Weak-validation fallback | Five ID-grouped development folds | Test remains locked |
| Bootstrap replicates | 200 development, 500 final, stability check | Engineering default |

The stable ID assignment is u = the integer represented by the first 13 hexadecimal digits of SHA-256 of the UTF-8 string 'DATA3001-v1|20261004|' followed by the canonical official ID, divided by 16^13. Assign u < 0.70 to training, 0.70 ≤ u < 0.85 to validation and the rest to test. Define canonical IDs from source metadata before hashing. Save the actual assignment file. Fractions will be approximate rather than forced exact. Include the source snapshot hash in the manifest, not the hashed assignment string, so that retrieving additional IDs does not reshuffle existing ones.

For temporal stress testing, specify a cutoff from the development date/support audit before fitting that experiment. All training/validation target timestamps must precede the cutoff. Test origins follow the cutoff on IDs excluded from training; a stricter new-deployment subset uses the official first-good date after cutoff. Require administrative label maturity. Do not call a retrospective hourly-data test a causal operational forecast. Spatial holdouts exclude every trajectory ID touching the held-out block from training, including its observations outside that block. Report how that exclusion changes support.

### Selection and failure rules

Choose candidates on development results using common forecast cases and the primary common-grid log loss when finite comparisons exist. Examine Brier scores and coverage, and preserve raw zero-probability failures. A training-derived prior can still assign zero probability to an unseen validation destination. If every candidate has infinite loss on the matched cases, select using common-grid Brier score and calibration, disclose that fallback and retain the zero-probability failure count. Never omit those cases or introduce an unrecorded probability floor. Use paired whole-ID uncertainty. Prefer the simpler candidate when a gain is not distinguishable from sampling variability or calibration materially deteriorates. Any quantitative calibration margin must be recorded before final-test results; it is a project choice rather than a literature fact.

Unresolved-support mass m is incomplete model knowledge, not a physical destination. Do not score it silently as a normal ocean state. For observed destination j, allocating none or all of m to j gives log-loss bounds from −log(p_j + m) to −log(p_j). Report these bounds, m, the affected-case count and unconditional algorithmic failure coverage. An optional failure-penalized Brier score is sum over physical states j of (p_j − indicator[j = observed])², plus m². Label that score as algorithmic failure-penalized when m > 0. Fully specified outputs with m = 0 retain ordinary probabilistic scores. Preserve all forecast cases in the accounting, and show any common fully resolved subset alongside, never instead of, incomplete-output results. Probability regions with m > 0 report partial/unresolved coverage rather than claim a complete calibrated physical distribution.

For an observed seasonal row, define P_season_pooled = (1 − λ) P_season_raw + λ P_annual_same_regime, with λ selected from the declared set. If the seasonal row is absent and an annual row exists, use λ = 1 for that row and flag the fallback. If both are absent, send its mass to unresolved support. Optional regularization uses (1 − ε) P_season_pooled + ε Q, where Q is the training destination-frequency prior for that regime and lag, renormalized over the permissible wet connected component and outside state for the source. It need not give positive probability to unseen destinations. Declare and inspect this prior; do not quietly replace it with a uniform global floor. Apply the same pooling and regularization definition to remainder kernels.

Grid/lag selection also requires physical-connectivity and memory checks. Compare direct and composed transitions at exact timestamps, not just eigenvalues. Test whether incoming direction, within-cell position or visit age systematically predicts residuals. A candidate passing a short test can still fail at 365 days. A fixed-regime seasonal kernel learned from short intervals can produce a biased annual scenario because conditioning on long-term survival/regime persistence selects different tracks. Report the matched direct annual reference and this structural limitation instead of treating bootstrap bands as complete uncertainty.

Unobserved seasonal rows fall back to an observed annual row for the same regime. A row with no such support sends probability to the unresolved state rather than to itself. Unresolved mass means insufficient empirical knowledge. It is neither ocean export nor instrument death. Destination-prior smoothing must not manufacture land connectivity; evaluate its effect on paths and distributions. Split disconnected wet components inside a grid cell when the topology audit shows that a single state creates artificial exchange. Do not infer the path between distant endpoints by a straight segment.

For h = qτ + r, use calendar-aware full-lag transitions followed by a directly estimated r-day kernel when r > 0. Remainder kernels use the same declared source, origin estimator, regime and grid. Report checks at anchors with and without remainders. If short remainders fail a memory/support check, affected daily products remain explicitly unvalidated until a suitable continuous-time or finer-state model is tested. Neither rounding the horizon nor a fractional matrix power is the default repair.

Evaluate 1° and 0.5° on the same held-out origins. Aggregate fine predictions to the common 1° wet-state partition for the primary score. A secondary common 0.5° check may disaggregate the coarse probability by wet area; label that assumed within-cell destination prior and compare both models on that same fine partition. Such a test measures spatial detail under a declared prior. Do not compare raw coarse and fine categorical losses as if their categories were identical. Probability regions should be ranked by density when aiming for compact area, include all tied cells deterministically, and report achieved rather than nominal included mass.

### Alternative-method audit and scope

The selected core is the most defensible first implementation for this project's iterable-operator requirement, auditability and time budget. It is not a claim of universal best prediction. The MDN paper [S09] is a relevant counterexample to assuming grids are always best. Its annual global setup and reported hardware are different from a local season-conditioned laptop study. A smaller reproducible challenger is appropriate after the core; its land mass, conditioning, scoring population and computation must be checked. Kaggle/community examples may supply implementation ideas but do not override official source definitions or validated primary research.

Temperature and multiple current branches are not ignored: the empirical spatial-seasonal transition distribution can represent their aggregate historical effects. Explicit SST or incoming-direction conditioning is added only with observed support, an availability audit and out-of-sample benefit. It does not grant knowledge of future weather or SST. Stochastic advection requires drift/dispersion closure; it is not automatically more physical merely because it uses velocity. A joint cell/drogue-status model addresses actual drifter hardware evolution and is deliberately a different question from fixed physical-proxy scenarios.

Do not promise to infer oil weathering, injury risk, search success, container recovery or confirmed beaching from endpoint occupancy. The core's practical contribution is a quantified transport prior and reusable method, with uncertainty and a documented path for application-specific calibration.

### Execution order and concrete handoffs

1. **Source collection:** data/metadata manifest, R GeoJSON and initial lazy download profile. Resolve variable and drogue conventions from the actual source.
2. **QC and support:** cleaned observation layer, reconciliation ledger, 1°/0.5° maps, seasonal/regime/365-day support and candidate D/path coverage. Freeze split IDs before model selection.
3. **Core modelling:** annual and seasonal 1° kernels, persistence/climatology baselines, direct endpoint references, outside/unresolved semantics and exact-duration propagation.
4. **Development verification:** memory/connectivity tests, lag/regularization selection, matched-case probability scores, calibration, dependence uncertainty and long-horizon feasibility. Freeze the chosen configuration.
5. **Justified extensions:** 0.5°, environmental/history conditioning, MDN or regional adaptation in that order of demonstrated need, rather than as compulsory simultaneous pipelines.
6. **Final evaluation and reporting:** locked-ID test, chronological/spatial stress tests, 7/30/365-day findings, whole-R gathers/loses experiments, source receipts and reproducible operator package. Failed or unsupported cases remain part of the report.

The project team consists of Junxi Xiao, Han Wang, Ming Yue and Yi Cheng Zhang. Junxi Xiao coordinates the scientific target, configuration and progress. Han Wang and Ming Yue implement and independently cross-check data/model work. Yi Cheng Zhang leads application significance, literature interpretation and final text. The four members will agree the allocation of coverage, visualization and verification responsibilities. Overlapping computation is expected; every reported result needs a named reviewer and a reproducible run/configuration reference.

This contract supersedes technical rules in the previous planning workbook. It does not modify the proposal, README, Git history or any empirical result. Target-changing decisions require a new version with an explanation and affected checks. Values chosen by the procedure are recorded once in the configuration manifest before the final test. Formal data collection and modelling have not been performed as part of this contract-authoring task.

## Evidence register

Source pages checked on 2026-10-04. Scientific primary sources, official dataset/software documentation, uploaded course material and study choices are distinguished. Numerical defaults and proposed rules are not presented as literature-proven optima.

**S01 — Uploaded course material and team decisions.** gdp-overview.pdf, pp. 3–4, Section 3.2.2; lecturer slide supplied by user; team planning messages

Uploaded material / user instructions. Supports week/month/year, iterable operator and R gathers/loses. It is not the complete public Course Outline. Proposal requirements remain those supplied by the user.

**S02 — NOAA GDP official hourly dataset.** https://www.aoml.noaa.gov/phod/gdp/hourly_data.php

Official public source. Hourly estimates, variables, metadata, access routes, citations and release notes. Freeze the actual asset; do not infer its version from a page alone.

**S03 — Elipot et al. 2016, hourly drifter processing.** https://doi.org/10.1002/2016JC011716

Primary paper. Processed hourly position/velocity estimates and interpolation uncertainty. Retrospective processing does not automatically supply causal forecast features.

**S04 — Elipot et al. 2022, hourly SST.** https://doi.org/10.1038/s41597-022-01670-2

Primary paper. SST estimation and uncertainty. Apply NOAA release corrections to variable-specific flags.

**S05 — McAdam and van Sebille 2018, surface connectivity.** https://doi.org/10.1002/2017JC013363

Primary paper. Grid/lag trade-offs, artificial dispersion and connectivity artifacts. These are risks to audit, not proof that this pilot exhibits them.

**S06 — Miron et al. 2017, Lagrangian dynamical geography.** https://doi.org/10.1038/s41598-017-07177-w

Primary paper. Empirical cell transitions and dynamical geography. A methodological precedent, not a region-specific optimal grid or lag.

**S07 — Miron et al. 2019, Markov-chain-inspired search for MH370.** https://arxiv.org/html/1903.06165

Primary author paper; journal DOI 10.1063/1.5092132. Undrogued trajectory portions, seasonal composition and limitations for debris-specific physics. Indian Ocean settings are not copied as Atlantic optima.

**S08 — Lumpkin et al. 2012, evaluating drifter deaths.** https://www.aoml.noaa.gov/phod/docs/Lumpkin_2012.pdf

Primary paper. Termination and inferred beaching/pickup distinctions. Disappearance alone does not establish physical fate.

**S09 — Brolly 2023, Inferring Ocean Transport Statistics With Probabilistic Neural Networks.** https://doi.org/10.1029/2023MS003718

Primary paper. A mixture-density-network alternative to gridded transitions in its reported global experiment. It does not establish optimality for this pilot. Author code: https://github.com/mtbrolly/transition_density

**S10 — Gneiting and Raftery 2007, proper scoring rules.** https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf

Primary methods paper. Proper probabilistic scores, calibration and sharpness. Common outcome partitions and paired cases are project evaluation requirements.

**S11 — scikit-learn official grouped validation guidance.** https://scikit-learn.org/stable/modules/cross_validation.html

Official software documentation. Group-aware splitting. The project's ratios, seed and temporal label purging are explicit design choices.

**S12 — CloudDrift official usage documentation.** https://clouddrift.org/usage.html

Official project documentation. Lazy hourly-data access and ragged trajectory subsetting. Data access tooling, not an independent data authority.

**S13 — OpenDrift official model-selection guide.** https://opendrift.github.io/choosing_a_model.html

Official project documentation. Object-specific oil, leeway and other drift models need distinct assumptions and forcing.

**S14 — OceanParcels official stochastic diffusion guide.** https://docs.oceanparcels.org/en/latest/user_guide/examples/tutorial_diffusion.html

Official project documentation. Stochastic advection/diffusion formulation. Velocity covariance is not automatically a diffusivity estimate.

**S15 — GSHHG official shoreline dataset.** https://www.soest.hawaii.edu/pwessel/gshhg/

Official dataset/project site. Freeze coastline version and resolution before wet masks and topology diagnostics.

**S16 — Deen and de Rooij, cluster bootstrap for repeated observations.** https://pmc.ncbi.nlm.nih.gov/articles/PMC7148287/

Primary statistical methods paper. Cluster-resampling rationale. Applied here by analogy to drifter groups, not proof of one optimal bootstrap count.

