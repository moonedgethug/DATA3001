# Modelling handover: Where Things End Up

## What is ready

The verified official hourly cohort, source-linked field annotations, fixed geometry, split manifests, origin/event ledgers, distinct anchor labels and observational support are prepared. The authoritative Excel remains the research specification. Read `READINESS_REPORT.md` and `audit/preparation_verification.json` before interpreting support.

The package contains every available acquired trajectory. R-source origins and D-source origins are distinguishable, and downstream IDs without R visits provide supported local operator inputs. Primary sampling uses every QC-valid hourly point and equal eligible pairs. Cell entry, first-R entry, daily thinning and equal-ID weights are alternative definitions, not primary replacements.

## Choose the same target and cases when comparing methods

The selected finite D is an explicitly stopped-domain product. A qualified observed first exit is absorbing for that target. Endpoint occupancy uses the matched true endpoint and permits returns. Compare models on identical target/scenario/horizon cases; never compare a stopped label with an unrestricted endpoint prediction as if the outcomes were equivalent.

Use exact UTC elapsed days. Anchors 7/30/365 are mandatory; 90/180 audit support. Integer days1–365 are supplied on demand. Candidate lag/remainder input generation supports 1/3/5/7 days, remainder1–6, and 2tau/3tau diagnostics. During composed propagation, advance the actual date and applicable season after every step. Hourly input does not require an hourly-step model.

## Critical support limits

Development fixed-drogued 365-day validation has no eligible DJF endpoint or stopped observations; MAM has no stopped observations. Other seasonal groups depend on few whole IDs. Many hourly windows from one drifter do not validate one-year seasonal accuracy. Use the contract's grouped development procedure if appropriate, with locked test unchanged; report missing evaluable cells/seasons. Do not replace primary regime/target, move R, rebalance IDs or claim validated daily predictions to fill these gaps.

D covers observed development R paths through365, but this does not demonstrate predictive boundary-map stability or unrestricted ocean transport. Downstream exits and returns remain important; the support report documents their availability. Any new region/geometry/scenario or primary eligibility change requires the architecture's versioned decision.

## Forecast-time information

Permitted core inputs include origin cell, actual departure date/season and declared scenario. The finest core release is a cell; its subcell prior follows eligible historical origins. Do not silently use an exactly known point or uniform wet-area prior as the same estimand.

Future endpoint, future observed SST, drogue loss/death metadata, next gap/exit, label eligibility and within-track future context are retrospective annotations. Keep them out of operational forecast features. Optional origin-SST conditioning must use origin-only temperature flags and be evaluated as an extension. Missing SST never removes core position pairs.

## Estimation and evaluation still to perform

Fit annual and seasonal empirical rows from eligible source-supported pairs, then assess declared seasonal pooling/weak regularization. Unobserved rows need a same-regime supported fallback or explicit unresolved-support mass. Never invent a stationary self-loop or count missing outcomes as observed unresolved-support destinations. Do not normalize support summaries that mix targets, scenarios or incompatible case sets into a single operator.

Retain all zero-probability/incomplete failures when scoring common1-degree full distributions. Implement the contracted log loss, Brier, probability-region coverage, outside calibration and unresolved-support bounds/failure reporting. Whole-ID paired bootstrap starts at the declared200/500 replicates, with deployment/year sensitivity. Prepare chronological/spatial stress tests with appropriate purging/ID exclusion. No such predictive score or bootstrap result has been produced in preparation.

## Dependence, concentration and missingness

`support/cell_support.parquet` gives candidate/eligible hourly counts, distinct IDs, observed cell visits, drifter-days, destination diversity, dominant-ID/year/experiment shares, geometry/regime uncertainty, primary attrition and nonexclusive secondary predicates. Seasonal unique IDs and visits can overlap. Do not sum them to obtain independent annual support. `R_annual_counts_and_IDs.csv` calculates the annual union of distinct IDs correctly; annual visit counts must likewise be recomputed from origin/label ledgers rather than summing seasonal visits.

The observed-origin estimator conditions on usable constant-regime intervals. It cannot identify every disappeared or immature trajectory's destination. Report selection/availability rather than silently imputing outcomes. Source uncertainty conventions that remain unresolved are isolated in `metadata/unresolved_questions.json`.

## Data quality and learned references

Use field-specific source and derived flags. Source SST/velocity/uncertainty rejection is distinct from position rejection. GSHHG mismatches and resolution disagreement are mapping uncertainties, not beaching or physical outside. Cell reversals stay unsmoothed. A line segment crossing land does not itself invalidate a pair.

The bounded peer diagnostics are descriptive, use training IDs only and exclude the target ID. They preserve vectors and measurement context, including peer-unavailable events. They do not repair positions or certify independence. Refit learned QC/peer/reconstruction references within each grouped validation fold if they become part of modelling. Global retrospective review statistics cannot become fold-fitted forecast features.

## Readiness ownership

Acquisition integrity and deterministic eligibility have been audited. Observational support is explicitly limited; predictive validity is unperformed. The core is a historical drifter transport prior under declared proxies, not a universal simulator for oil, people, vessels or containers. Object physics, transfer/adaptation, whole-R release maps, external inflow experiments and optional reconstruction remain separate evaluated stages.

This handover is a local artifact for the architecture chat to inspect. It was not sent to another chat or person.
