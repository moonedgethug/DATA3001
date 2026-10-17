# SST covariate reconstruction: method draft

**Historical design status:** Method design for team review. The external-SST-first priority is agreed; spatial matching, gap limits and validation details below are proposed. No external SST data have been downloaded, no imputed values generated, and no canonical records changed.

**Current execution:** The authorised, verified run and effective policies are recorded in the [SST reconstruction report](../results/runs/sst_reconstruction_20261016_v1/REPORT.md). The pre-execution statements above describe the historical draft stage.

**Approved incremental extension (17 October 2026):** The [three-corner method](sst_coastal_extension_plan.md)
and [verified extension report](../results/runs/sst_coastal_extension_20261017_v1/REPORT.md)
add inside-triangle linear interpolation and outside-triangle normalized-weight
estimation for qualified baseline coastal unknowns with exactly three source
temperatures. They do not alter this historical draft or the frozen baseline.
Read the current combined view through the entry in [data layout](data_layout.md#current-sparse-source-temperature-view).

**Pilot completion (17 October 2026):** The [corrected, verified pilot report](../results/runs/sst_pilot_completion_20261017_v2/REPORT.md)
adds the explicitly authorized 795 four-corner OISST estimates and 81
four-corner estimates from the official 0.05-degree CoralTemp v1.0 archive.
The earlier three-corner/baseline runs remain unchanged. R retains 15 unknowns
(13 high-temperature cases and two unqualified position/mapping records).
The daily background estimates retain their method, source and coastal-risk
annotations; they are not reconstructed hourly sensor measurements. A small
16-ID development check does not establish coastal or destination accuracy.
No grounding exclusion or new beaching state was implemented. This execution
entry supersedes historical draft statements about whether data were acquired.

**Current user-authorized source-count completion (17 October 2026):**
The [sparse-source method](sst_sparse_completion_plan.md) removes the extra
temperature land-path/hull vetoes and admits two-source inverse-distance and
one-source approximations alongside the existing four/three-source equations.
The [corrected verified run](../results/runs/sst_sparse_completion_20261017_v2/REPORT.md)
adds 24,810 working total temperatures, retaining 11,174 unknowns (13 in R).
All 36 original zero-OISST-corner cases found qualified finer official sources.
Official grounding/recovery last-good-date context is distinct from an exact
event hour. The 2,600 terminal-day estimates retain unknown event-time status.
No native fields, prior accepted values, frozen model qualifications or ID pools
are changed. These decisions supersede earlier temperature geometry refusals
in this historical draft; they do not establish prediction accuracy.

**Authority:** [Data Contract v1.0](contract/data_contract_v1.0.xlsx), especially clauses 23 and 26. This draft does not replace the contract, change position-pair eligibility, change equal-pair weighting, or establish predictive accuracy.

## 1. Quantity being constructed

Construct one sourced temperature covariate for existing observations with known position and time. Preserve native `sst`, `sst1`, `sst2`, their source flags and all existing annotations unchanged. Source flags remain available to preprocessing even when excluded from model inputs.

A daily external SST analysis is a background estimate, not a recovered GDP hourly sensor value. It cannot uniquely determine the GDP non-diurnal and diurnal components. OISST `anom` is an anomaly relative to climatology; it is not GDP `sst2`.

Keep valid native temperature first. Apply reconstruction only where native total SST is unavailable or has been rejected under an explicitly reviewed quality rule. Existing `sst_ok` is not by itself sufficient to approve the previously identified approximately 49 C cases; their source/context disposition is an execution prerequisite. Do not use unresolved suspect values as interpolation anchors. Do not replace a finite suspect value solely because an external product disagrees with it.

## 2. External background SST first

Candidate source: NOAA Daily OISST v2.1, AVHRR-only, final historical product, at 0.25-degree grid spacing. Resolution is not a guaranteed error bound.

Before acquisition, freeze the actual product/version, requested UTC dates, spatial subset, asset metadata and checksums. Decode the asset-specific fill values, scale factor, offset, units and coordinate arrays. Do not hard-code an ERDDAP fill value into a different packed NetCDF representation. Obtain only needed regional tiles/dates and their interpolation halo, not the full global archive.

### Proposed temporal matching

For an existing drifter observation at UTC time t, select the OISST field labelled with the same UTC calendar date d(t). Its coordinate is the centre time of a daily analysis, not an instantaneous measurement. Within-day spatial sampling follows the actual drifter position. This first design does not interpolate between daily fields or claim hourly temperature information from a daily product.

### Proposed spatial matching

Use the surrounding four grid centres from the source coordinate arrays. They are distinct from the project's 1-degree and 0.5-degree model-cell boundaries. Normalize longitude to the source convention before selecting neighbours.

For longitude lambda in [lambda_0, lambda_1] and latitude phi in [phi_0, phi_1], define

$$
u=\frac{\lambda-\lambda_0}{\lambda_1-\lambda_0},\qquad
v=\frac{\phi-\phi_0}{\phi_1-\phi_0}.
$$

The bilinear background estimate in source Celsius units is

$$
\widehat T_{\rm OI,C}=(1-u)(1-v)T_{00}+u(1-v)T_{10}+(1-u)vT_{01}+uvT_{11}.
$$

Here T_00 is at (lambda_0, phi_0), T_10 at (lambda_1, phi_0), and so on. Require a qualified drifter position and a valid, in-domain, all-water interpolation stencil with no unresolved land barrier or source fill. If the stencil is unavailable or coastal connectivity is unresolved, reject this match; do not silently choose a distant wet cell or blend across land. Record the four source indices, weights, date and source validity outcome. A nearest-wet-cell coastal alternative would require a separately reviewed distance/connectivity rule and validation.

Convert only the selected background estimate to the native GDP temperature convention:

$$
\widehat T_{\rm OI,K}=\widehat T_{\rm OI,C}+273.15.
$$

Unit conversion is necessary when combining sources; it does not require retaining duplicate predictor columns. Apply no bias correction by default. First measure OISST-versus-GDP bias on qualified development matches; any fitted correction is a separately validated training-fold-only extension.

## 3. Short, same-drifter linear interpolation second

Use this branch only when external matching is unavailable. Let t_a < t < t_b be the closest bracketing accepted native temperatures from the same GDP ID. Never use an already imputed value as an anchor.

$$
\widehat T_{\rm lin}(t)=
\frac{t_b-t}{t_b-t_a}T(t_a)+
\frac{t-t_a}{t_b-t_a}T(t_b).
$$

Use actual UTC timestamp differences, not row positions. The formula estimates temperature along the observed trajectory; it assumes approximately linear temperature change over the short interval, not a straight-line drifter path or constant physical ocean temperature.

Example: 298.15 K at 10:00 UTC and 300.15 K at 14:00 UTC give 299.15 K at 12:00 UTC. These are 25, 27 and 26 C respectively.

Proposed admission conditions:

1. Both anchors are native, accepted temperature estimates from the same ID, with no unresolved source/temperature issue.
2. Existing positions and timestamps are available at every intervening hour and pass relevant position/mapping checks. Fill temperature only; never create missing trajectory rows.
3. No unresolved trajectory jump or coastal-mapping issue affects the interval.
4. The consecutive missing-temperature run satisfies L <= L_max. For a regular hourly run, L = (t_b - t_a)/3600 - 1, so three missing hours span four hours between anchors.
5. No extrapolation at trajectory starts/ends or across long sensor outages. Do not bridge a rejected suspect-temperature record as if it were a routine missing value without an explicit disposition.

**Proposed starting limit:** L_max = 3 missing hours, subject to development validation. The pilot audit finds only three raw-missing R observations in closed gaps of at most three hours; allowing six hours adds none under the audited definition. This supports a simple initial limit, not a claim that every three-hour interpolation is accurate. Compare alternative limits on common validation masks and disclose any added coverage separately.

## 4. Explicit routing and provenance

For a model temperature covariate, use the following routing:

$$
T_{\rm use}=
\begin{cases}
T_{\rm native},&\text{native estimate accepted},\\
\widehat T_{\rm OI,K},&\text{external match accepted},\\
\widehat T_{\rm lin},&\text{short-gap conditions satisfied},\\
\mathrm{unknown},&\text{otherwise}.
\end{cases}
$$

An unknown result is allowed. Do not force zero, a long-period constant, or an unsupported seasonal mean to achieve numerical completeness. An otherwise qualified position pair remains available to the core model.

Keep method, reason and source references in an audit sidecar joined by `id` and `source_obs`; include the product/date/stencil or anchor references and configuration version. The prediction matrix need not contain all audit fields. Never overwrite source flags to imply an imputed value was an official observation.

## 5. Validation and interpretation

- Freeze a development-only masking experiment on qualified temperatures, stratified by season, location and ID, with contiguous gaps resembling observed missingness. Evaluate entire-ID holdouts for learned corrections. Do not use final-test temperatures to select limits, corrections or rules.
- Report coverage, refusals, MAE, RMSE and signed bias for reconstruction on the same masked cases; separate results by regime/season/location and gap length where support permits. Report added cases separately when eligibility differs.
- Artificial masking evaluates reconstruction where reference temperatures exist; it does not prove missing-at-random behaviour or accuracy for an entirely unobserved sensor record.
- OISST assimilates buoy observations and is not automatically independent truth. Report potential source overlap and distinguish reconstruction agreement from independent measurement validation.
- Compare the no-temperature core and the temperature-enhanced outcome model on the same held-out release population, including declared handling of temperature-unknown cases. Reconstruction accuracy alone does not establish better destination-probability forecasts.
- Use of final daily OISST or future native anchors is retrospective reconstruction. It does not establish operational availability at the release time. A live-forecast experiment requires version/release-time-aware external products and only information available when the forecast is issued; the two-sided fallback must not use future anchors there.

This method supplies a temperature covariate. It does not substitute for the project's destination-transition probability model, create new drifter trajectories, or increase independent 365-day support.

## 6. Evidence and open items

The pilot gap audit covers the 396 development IDs visiting R, read as complete trajectories: 15,403 raw-missing R observations; three in closed gaps of at most three or six missing hours under existing anchor gates; seven pilot IDs without raw SST anywhere in their acquired trajectory. See [the executable audit companion](../results/runs/feature_review_batch06_20261016.ipynb). These are qualification-screen counts, not approved reconstruction results.

Before execution: resolve suspect native-temperature disposition; freeze the actual OISST assets and coastal-stencil checks; confirm the three-hour candidate and development-validation protocol. Whether the optional temperature extension becomes part of the final selected predictor remains an empirical decision under the contract.

Sources:

- [NOAA NCEI OISST product and version description](https://www.ncei.noaa.gov/products/optimum-interpolation-sst).
- [NOAA ERDDAP OISST v2.1 final metadata](https://upwell.pfeg.noaa.gov/erddap/griddap/ncdcOisst21Agg_LonPM180.graph): daily centre time, Celsius SST, source metadata and release latency. Metadata were inspected; no gridded temperature values have yet been downloaded or matched.
