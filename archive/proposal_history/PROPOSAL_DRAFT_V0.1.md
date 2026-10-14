# Where Things End Up: A Multiscale, Season-Aware Surface-Transport Operator for the Gulf Stream System

**Team:** Junxi Xiao, Han Wang, Ming Yue, and Yi Cheng Zhang  
**Status:** Initial proposal draft for group review

## 1. Research questions and objectives

This project asks whether historical surface-drifter observations can support calibrated destination probabilities after **7 days, 30 days, and approximately one year**. Model development will begin in a data-rich part of the southern U.S. East Coast Gulf Stream system, then test spatial refinement and adaptation to adjacent regions with weaker observational support.

1. What are the 7-day and 30-day destination distributions for releases from different origin cells?
2. Do season, recent velocity, sea-surface temperature (SST), and drogue status improve held-out probabilistic predictions over an annual transition baseline?
3. Can iterated short-horizon operators reproduce observed historical 365-day endpoint distributions?
4. How do grid resolution and reduced local data support affect calibration, uncertainty, and spatial transfer?

The objectives are to build a reproducible hourly-data pipeline; estimate annual and seasonal transport operators; compare 1° and 0.5° grids; measure the incremental predictive value of environmental and object-state variables; evaluate one-year predictions against historical endpoints; and produce probability and uncertainty maps rather than one deterministic route. The software will accept a configurable region rather than hard-code the Gulf Stream geometry.

## 2. Why the problem is significant; introduction and existing studies

Surface transport connects offshore waters, coasts, and the open Atlantic. Its destination distribution is relevant to search-area prioritisation, floating-object recovery, marine-debris transport, and preliminary spill-exposure assessment. A probabilistic product is required because releases from the same area can follow different current branches, enter eddies, or leave the model domain.

The NOAA Global Drifter Program (GDP) provides Lagrangian observations of position, derived velocity, SST, measurement uncertainty, and drogue status. Its hourly product retains more high-frequency variability than the older six-hour product [1,2]. Previous studies have mapped seasonal currents [3], modelled probabilistic debris pathways [4], and represented surface connectivity with transition matrices and Markov chains [5,6]. They also show that cell size, time step, uneven deployment, drogue loss, and artificial dispersion can change the result.

The proposed product is a **validated historical surface-transport operator**, not an operational forecast for a particular oil product, vessel, or life raft. The framework will accept available object-state inputs, initially drogue status, but validation claims will remain limited to states represented in the data. It will report both predictive skill and where sparse observations make the result unreliable.

## 3. Data/region, data description, and initial analysis

Formal modelling will use the current NOAA GDP **hourly** location, velocity, and temperature product, with version and access date recorded at retrieval. Required observation variables are longitude, latitude, time, eastward and northward velocity, SST, position and temperature uncertainty, and drogue status. Metadata will include drifter ID, experiment, deployment period, buoy type, and location system where available.

The pilot release region \(R_{pilot}\) is the audited southern Gulf Stream corridor, approximately 30.0–35.5°N and 82–73°W. A larger transport domain \(D\) is required for long-horizon propagation because probability rapidly leaves \(R_{pilot}\); an outside-domain state will prevent departures being treated as missing data. Cape Hatteras will be a dynamic stress test, while Florida–Bahamas and the North-Central Gulf are candidate lower-support adaptation regions.

Preliminary screening used the NOAA May 2025 six-hour product: 28,728 trajectories and 48,887,074 observations from 1979–2025. Within \(R_{pilot}\), 621 unique trajectories were observed; 605 and 561 had at least one valid 7-day and 30-day forward pair respectively, and 338 were drogued at both endpoints of a valid 30-day pair. At 0.5°, 109 of 137 observed origin cells had at least 50 valid 30-day trajectories. Seasonal splitting reduced median 30-day support from 84 per observed 0.5° cell to 18–31; at 1° the seasonal medians were 32–51. A preliminary screen found only 218 unique trajectories with an exact 365-day forward pair in \(R_{pilot}\). These results support starting at 1°, refining to 0.5°, and using direct 365-day observations for coarse validation rather than fine-cell training. All counts will be recomputed on the hourly product.

![Preliminary 0.5-degree and 1-degree 30-day trajectory support in three candidate Gulf Stream windows](../analysis/outputs/gulf-stream-segment-support-0p5-vs-1deg.png)

*Figure 1. Preliminary six-hour screening of unique trajectories with a valid 30-day forward position. The Southern Coastal Segment is the proposed pilot; colours measure data support, not predicted transport.*

## 4. Proposed method

| Stage | Design and decision rule |
|---|---|
| **Quality control** | Check coordinate and timestamp validity, duplicates, temporal gaps, implausible speeds, uncertainty, SST availability, land intersections, drogue changes, and concentration by year or experiment. For horizon \(h\), both \(t\) and \(t+h\) must exist on the same trajectory. Future endpoints may leave \(R_{pilot}\). |
| **Sampling and splits** | Control strongly overlapping hourly origins through fixed-stride sampling and trajectory weighting. Assign complete drifter IDs to train, validation, or test sets. Add a later-period temporal holdout and contiguous spatial holdout blocks; no future velocity or temperature may enter predictors. |
| **1° baselines** | Compare persistence, region-wide destination climatology, mean-flow displacement, and annual empirical transition matrices for 7 and 30 days. Estimate DJF, MAM, JJA, and SON operators using smoothing or shrinkage toward the annual operator where rows are sparse. |
| **Environmental model** | Estimate destination-cell probabilities from origin location, sine/cosine day of year, contemporaneous SST and local velocity when available, drogue status, and measurement uncertainty. If release-time conditions are unavailable, predictions will marginalise over their historical cell-season distribution. Compare regularised multinomial and gradient-boosted probabilistic models under identical splits. Sequential ablation tests will measure whether season, velocity, SST, and drogue status add predictive value. No prior track is required. |
| **0.5° refinement** | Repeat the validated pipeline at 0.5°. Retain finer cells only where held-out probability scores improve; otherwise pool neighbouring cells, apply regularisation, or retain 1° resolution. This distinguishes greater spatial detail from greater predictive accuracy. |
| **One-year prediction** | Compare season-appropriate 7-day operators iterated to about 364 days, 30-day operators iterated to about 360 days, and a coarser direct 365-day model where support permits. The expanded domain must include downstream states. Compare all three distributions with observed 365-day endpoint density to measure accumulated error and sensitivity to Markov and stationarity assumptions. |
| **Spatial adaptation** | First hide contiguous pilot-region cells to test geographical generalisation. Then transfer the workflow and model structure to an adjacent region, recalibrate with limited local data, and evaluate on its remaining trajectories. Fitted transition probabilities will not be copied directly between regions. |

The target will remain a potentially multimodal distribution so that one origin can feed several current branches. Probabilistic performance will be evaluated with held-out log loss, multiclass Brier score, calibration, and 50/80/95% probability-region coverage. Great-circle error will be secondary because one-point summaries can penalise valid multimodal predictions. One-year density comparisons will use Jensen–Shannon or Wasserstein distance. Confidence intervals will be obtained by resampling whole trajectories.

## 5. Initial analysis/visualisation and planned outputs

Figure 1 establishes the pilot-region data support and motivates the initial 1° grid. The next figure will replace the current trajectory overplot with origin density and log-scaled 365-day endpoint density. Final outputs will include 7-day, 30-day, and approximately one-year destination maps; annual-versus-seasonal comparisons; observed-versus-predicted long-horizon density; calibration and uncertainty maps; and support warnings for sparse cells. Historical observations, predictions, and uncertainty will be visually distinct.

## 6. Timeline and plan

| Course week | Work and review gate | Output |
|---|---|---|
| 3–4 | Freeze definitions, region/domain, and evidence | Proposal and modelling specification |
| 4–5 | Retrieve hourly data; audit quality, missingness, and sampling | Reproducible data subset and audit |
| 5–6 | Build 1° annual and seasonal 7/30-day baselines | Baseline operators and probability maps |
| 6–7 | Add environmental conditioning and ablation tests | Held-out model comparison |
| 7–8 | Test 0.5° refinement and adaptive regularisation | Resolution and uncertainty analysis |
| 8–9 | Expand domain; produce and validate one-year results | Long-horizon comparison |
| 9–10 | Spatial adaptation and final visualisation | Final product and presentation |
| 10–11 | Reproducibility audit and report integration | Modelling report package |

Junxi Xiao, Han Wang, and Ming Yue will jointly implement, tune, and cross-check the computational workflow, with rotating review of data definitions, leakage, and results. The four members will agree the allocation of visualisation and visual validation. Yi Cheng Zhang will lead significance, literature synthesis, citation control, and final text integration. Junxi Xiao will coordinate the architecture, technical decisions, schedule, and merged deliverables. Major numerical claims will require independent recomputation or code review.

## References

1. Elipot, S. et al. (2016). A global surface drifter data set at hourly resolution. *Journal of Geophysical Research: Oceans*, 121, 2937–2966. https://doi.org/10.1002/2016JC011716
2. Elipot, S. et al. (2022). A dataset of hourly sea surface temperature from drifting buoys. *Scientific Data*, 9, 567. https://doi.org/10.1038/s41597-022-01670-2
3. Lumpkin, R. & Johnson, G. C. (2013). Global ocean surface velocities from drifters: mean, variance, ENSO response, and seasonal cycle. *Journal of Geophysical Research: Oceans*, 118, 2992–3006. https://doi.org/10.1002/jgrc.20210
4. Maximenko, N., Hafner, J. & Niiler, P. (2012). Pathways of marine debris derived from trajectories of Lagrangian drifters. *Marine Pollution Bulletin*, 65, 51–62. https://doi.org/10.1016/j.marpolbul.2011.04.016
5. McAdam, R. & van Sebille, E. (2018). Surface connectivity and interocean exchanges from drifter-based transition matrices. *Journal of Geophysical Research: Oceans*, 123, 514–532. https://doi.org/10.1002/2017JC013363
6. Miron, P. et al. (2017). Lagrangian dynamical geography of the Gulf of Mexico. *Scientific Reports*, 7, 7021. https://doi.org/10.1038/s41598-017-07177-w
